# modules/extract_llm.py
# ─────────────────────────────────────────────────────────────────────────────
# Multi-provider LLM extraction layer.
#
# Architecture:
#   1. build_prompt()     → single prompt used for ALL providers
#   2. call_llm()         → routes to the right SDK based on client_type
#   3. parse_response()   → converts raw JSON string → Process object
#   4. extract_process_llm() → public entry point
#
# To add a new provider: add it to config.py + handle its client_type here
# if it uses a non-OpenAI-compatible API (otherwise it works automatically).
# ─────────────────────────────────────────────────────────────────────────────

import json
import re
from modules.schema import Process, Step, Edge


# ── Prompt ────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a business process analyst. Your job is to extract a structured process from a meeting transcript or description.

Return ONLY a valid JSON object — no markdown, no explanation, no code fences.

JSON schema:
{
  "name": "<process name>",
  "steps": [
    {
      "id": "S01",
      "title": "<short action label>",
      "description": "<full description>",
      "actor": "<who performs this, or null>",
      "is_decision": false
    }
  ],
  "edges": [
    { "source": "S01", "target": "S02", "label": "" }
  ]
}

Rules:
- Step IDs must be S01, S02, S03... in order.
- For decision steps set is_decision=true and create two edges with label "yes" and "no".
- Keep titles SHORT (3-6 words max) — they appear inside diagram nodes.
- Descriptions can be longer.
- Detect actors from context (e.g. "the team", "the system", "manager").
- Output language: {output_language}
- Return ONLY the JSON. Nothing else."""


def build_prompt(text: str, output_language: str) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt)."""
    system = SYSTEM_PROMPT.replace("{output_language}", output_language)
    user = f"Extract the process from this transcript:\n\n{text}"
    return system, user


# ── LLM Routing ───────────────────────────────────────────────────────────────

def call_llm(system: str, user: str, client_info: dict, provider_cfg: dict) -> str:
    """
    Routes the request to the correct SDK based on provider client_type.
    Returns the raw text response from the model.
    """
    client_type = provider_cfg["client_type"]
    api_key = client_info["api_key"]
    model = provider_cfg["default_model"]

    if client_type == "openai_compatible":
        return _call_openai_compatible(system, user, api_key, model, provider_cfg)

    elif client_type == "anthropic":
        return _call_anthropic(system, user, api_key, model)

    else:
        raise ValueError(f"Unknown client_type: {client_type}")


def _call_openai_compatible(system: str, user: str, api_key: str, model: str, provider_cfg: dict) -> str:
    """
    Handles DeepSeek, OpenAI, Groq, Gemini — all use the OpenAI SDK
    with a custom base_url. This is the zero-overhead multi-provider trick.
    """
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url=provider_cfg.get("base_url"),
    )

    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        max_tokens=2048,
        temperature=0.1,   # low temp → deterministic JSON
    )

    # Enable JSON mode when supported (DeepSeek, OpenAI, Groq)
    if provider_cfg.get("supports_json_mode"):
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def _call_anthropic(system: str, user: str, api_key: str, model: str) -> str:
    """Handles native Anthropic SDK (Claude models)."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=2048,
        temperature=0.1,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text


# ── Response Parsing ──────────────────────────────────────────────────────────

def parse_response(raw: str) -> Process:
    """
    Parses the raw LLM response into a Process object.
    Handles common LLM quirks: markdown fences, leading text, etc.
    """
    # Strip markdown code fences if present
    clean = re.sub(r"```(?:json)?", "", raw).strip().rstrip("```").strip()

    # Find JSON object boundaries
    start = clean.find("{")
    end = clean.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON found in LLM response:\n{raw[:300]}")

    data = json.loads(clean[start:end])

    steps = [
        Step(
            id=s["id"],
            title=s.get("title", "Step"),
            description=s.get("description", ""),
            actor=s.get("actor") or None,
            is_decision=s.get("is_decision", False),
        )
        for s in data.get("steps", [])
    ]

    edges = [
        Edge(
            source=e["source"],
            target=e["target"],
            label=e.get("label", ""),
        )
        for e in data.get("edges", [])
    ]

    return Process(
        name=data.get("name", "Process"),
        steps=steps,
        edges=edges,
    )


# ── Public Entry Point ────────────────────────────────────────────────────────

def extract_process_llm(
    text: str,
    client_info: dict,
    provider: str,
    provider_cfg: dict,
    output_language: str = "Auto-detect",
) -> Process:
    """
    Main extraction function. Called by app.py.
    Builds prompt → calls LLM → parses → returns Process.
    """
    lang_instruction = {
        "Auto-detect": "same language as the input transcript",
        "English": "English",
        "Portuguese (BR)": "Brazilian Portuguese",
    }.get(output_language, "same language as the input transcript")

    system, user = build_prompt(text, lang_instruction)
    raw = call_llm(system, user, client_info, provider_cfg)
    return parse_response(raw)
