# modules/extract_llm.py
# ─────────────────────────────────────────────────────────────────────────────
# Multi-provider LLM extraction layer.
#
# Architecture:
#   1. build_prompt()          → prompt for Mermaid/Draw.io (original, unchanged)
#   2. build_bpmn_prompt()     → prompt for advanced BPMN extraction (new)
#   3. call_llm()              → routes to correct SDK (shared by both)
#   4. parse_response()        → raw JSON → Process  (original, unchanged)
#   5. parse_bpmn_response()   → raw JSON → BpmnProcess (new)
#   6. extract_process_llm()   → public entry for Mermaid/Draw.io (unchanged)
#   7. extract_process_bpmn()  → public entry for BPMN (new)
#
# To add a new provider: add it to config.py + handle its client_type here
# if it uses a non-OpenAI-compatible API (otherwise it works automatically).
# ─────────────────────────────────────────────────────────────────────────────

import json
import re

# Core schema — always required
from modules.schema import Process, Step, Edge

# BPMN schema — imported lazily to avoid boot-time ImportError
# if an older schema.py without BPMN classes is deployed.
def _bpmn_imports():
    from modules.schema import BpmnProcess, BpmnElement, BpmnLane, BpmnPool, SequenceFlow
    return BpmnProcess, BpmnElement, BpmnLane, BpmnPool, SequenceFlow


# ════════════════════════════════════════════════════════════════════════════
#  ORIGINAL PROMPT — Mermaid / Draw.io  (unchanged)
# ════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a business process analyst. Your job is to extract a structured process from a meeting transcript or description.

Return ONLY a valid JSON object — no markdown, no explanation, no code fences.

JSON schema:
{
  "name": "<process name>",
  "steps": [
    {
      "id": "S01",
      "title": "<short action label — NO actor name here>",
      "description": "<full description>",
      "actor": "<who performs this step, or null>",
      "is_decision": false
    }
  ],
  "edges": [
    { "source": "S01", "target": "S02", "label": "" }
  ]
}

Rules:
- Step IDs must be S01, S02, S03... in order.
- CRITICAL: The "title" field must contain ONLY the action label (e.g. "Register ticket").
  NEVER include the actor name in the title. WRONG: "system: Register ticket". RIGHT: "Register ticket".
  The actor belongs ONLY in the "actor" field.
- For decision steps set is_decision=true and create two outgoing edges with labels "sim"/"não" or "yes"/"no".
- Keep titles SHORT (3-6 words max) — they appear inside diagram nodes.
- Decision step titles must be questions or conditions (e.g. "Prioridade alta?", "Resolved in 2h?").
- Descriptions can be longer and may include the actor context.
- Detect actors from context (e.g. "the team", "the system", "manager", "analista nível 1").
- Normalize actor names consistently: if the same role is mentioned multiple ways, use one canonical name.
- Output language: {output_language}
- Return ONLY the JSON. Nothing else."""


def build_prompt(text: str, output_language: str) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt) for Mermaid/Draw.io extraction."""
    system = SYSTEM_PROMPT.replace("{output_language}", output_language)
    user = f"Extract the process from this transcript:\n\n{text}"
    return system, user


# ════════════════════════════════════════════════════════════════════════════
#  BPMN PROMPT — advanced extraction
# ════════════════════════════════════════════════════════════════════════════

BPMN_SYSTEM_PROMPT = """You are a certified BPMN 2.0 process analyst.
Your job is to extract a complete, advanced BPMN process model from a meeting transcript.

Return ONLY a valid JSON object. No markdown, no explanation, no code fences.

─── JSON SCHEMA ───────────────────────────────────────────────────────────────

{
  "name": "<process name>",
  "documentation": "<brief process description>",
  "lanes": ["Actor A", "Actor B"],
  "elements": [
    {
      "id": "SE1",
      "type": "startEvent",
      "name": "<short label>",
      "actor": "<lane name or null>",
      "event_type": "none",
      "documentation": ""
    },
    {
      "id": "T01",
      "type": "userTask",
      "name": "<short label>",
      "actor": "<lane name or null>",
      "is_loop": false,
      "is_parallel_multi": false,
      "is_sequential_multi": false,
      "documentation": "<full description>"
    },
    {
      "id": "GW1",
      "type": "exclusiveGateway",
      "name": "<decision label>",
      "actor": null
    },
    {
      "id": "EE1",
      "type": "endEvent",
      "name": "End",
      "actor": null,
      "event_type": "terminate"
    },
    {
      "id": "BE1",
      "type": "boundaryEvent",
      "name": "Timeout",
      "attached_to": "T01",
      "is_interrupting": true,
      "event_type": "timer",
      "actor": null
    },
    {
      "id": "SP1",
      "type": "subProcess",
      "name": "<subprocess label>",
      "actor": "<lane or null>",
      "is_expanded": true,
      "children": [
        {"id": "SP1_T1", "type": "task", "name": "Inner Task", "actor": null}
      ]
    }
  ],
  "flows": [
    {"id": "F01", "source": "SE1", "target": "T01", "name": ""},
    {"id": "F02", "source": "GW1", "target": "T02", "name": "Yes", "condition": "${approved == true}"},
    {"id": "F03", "source": "GW1", "target": "EE1", "name": "No", "is_default": false}
  ]
}

─── ELEMENT TYPE REFERENCE ────────────────────────────────────────────────────

Events:
  startEvent             — process start (plain, message, timer, signal, conditional)
  endEvent               — process end (plain, terminate, error, message, signal, escalation, cancel)
  intermediateThrowEvent — throws message, signal, escalation, compensation, link
  intermediateCatchEvent — catches message, timer, signal, conditional, link
  boundaryEvent          — attached to a task; event_type: timer, error, message, escalation, signal, cancel, compensation

Tasks:
  userTask         — human performs the activity
  serviceTask      — automated / system activity
  scriptTask       — script execution
  sendTask         — sends a message
  receiveTask      — waits for a message
  manualTask       — physical/manual activity (no system)
  businessRuleTask — evaluates a business rule
  callActivity     — calls a reusable process (set called_element)
  task             — generic task (use when type is unclear)

Gateways:
  exclusiveGateway   — XOR: exactly one path taken
  parallelGateway    — AND: all paths taken simultaneously
  inclusiveGateway   — OR: one or more paths taken
  eventBasedGateway  — next event determines path
  complexGateway     — custom complex merge/split conditions

Sub-processes:
  subProcess       — collapsed or expanded sub-process
  adHocSubProcess  — activities in any order

event_type values (for events only):
  none | message | timer | error | escalation | cancel | compensation | signal | terminate | conditional | link

─── RULES ─────────────────────────────────────────────────────────────────────

1. ALWAYS start with a startEvent and end with at least one endEvent.
2. Every decision (if/when/otherwise) → exclusiveGateway with named outgoing flows.
3. Parallel activities → parallelGateway split + join pair.
4. Error / timeout handling → boundaryEvent attached to the relevant task.
5. Complex reusable blocks → subProcess.
6. Detect actors from context; map each actor to a lane name.
7. Flow IDs: F01, F02, F03 …
8. Element IDs: SE1 (start), T01…T99 (tasks), GW1… (gateways), EE1… (end), BE1… (boundary), SP1… (sub-process)
9. Keep names SHORT (≤6 words) — they appear inside nodes.
10. Output language: {output_language}
11. Return ONLY the JSON. Nothing else.
"""


def build_bpmn_prompt(text: str, output_language: str) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt) for BPMN advanced extraction."""
    system = BPMN_SYSTEM_PROMPT.replace("{output_language}", output_language)
    user = f"Extract the BPMN process from this transcript:\n\n{text}"
    return system, user


# ════════════════════════════════════════════════════════════════════════════
#  LLM ROUTING  (shared — unchanged)
# ════════════════════════════════════════════════════════════════════════════

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


def _call_openai_compatible(
    system: str, user: str, api_key: str, model: str, provider_cfg: dict
) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=provider_cfg.get("base_url"))
    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        max_tokens=4096,   # BPMN JSON can be larger
        temperature=0.1,
    )
    if provider_cfg.get("supports_json_mode"):
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def _call_anthropic(system: str, user: str, api_key: str, model: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        temperature=0.1,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text


# ════════════════════════════════════════════════════════════════════════════
#  RESPONSE PARSING — original (unchanged)
# ════════════════════════════════════════════════════════════════════════════

def _clean_json(raw: str) -> dict:
    """Strips LLM noise and returns parsed dict. Raises ValueError on failure."""
    clean = re.sub(r"```(?:json)?", "", raw).strip().rstrip("```").strip()
    start = clean.find("{")
    end   = clean.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON found in LLM response:\n{raw[:300]}")
    return json.loads(clean[start:end])


def parse_response(raw: str) -> Process:
    """Parses LLM response into a Process (Mermaid/Draw.io model)."""
    data = _clean_json(raw)

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
        Edge(source=e["source"], target=e["target"], label=e.get("label", ""))
        for e in data.get("edges", [])
    ]
    return Process(name=data.get("name", "Process"), steps=steps, edges=edges)


# ════════════════════════════════════════════════════════════════════════════
#  RESPONSE PARSING — BPMN (new)
# ════════════════════════════════════════════════════════════════════════════

def _parse_element(raw: dict):
    """Converts one element dict from the LLM into a BpmnElement."""
    _, BpmnElement, _, _, _ = _bpmn_imports()
    children = [_parse_element(c) for c in raw.get("children", [])]
    return BpmnElement(
        id=raw["id"],
        type=raw.get("type", "task"),
        name=raw.get("name", ""),
        actor=raw.get("actor") or None,
        lane=raw.get("lane") or raw.get("actor") or None,
        event_type=raw.get("event_type", "none"),
        attached_to=raw.get("attached_to") or None,
        is_interrupting=raw.get("is_interrupting", True),
        is_expanded=raw.get("is_expanded", True),
        children=children,
        is_loop=raw.get("is_loop", False),
        is_parallel_multi=raw.get("is_parallel_multi", False),
        is_sequential_multi=raw.get("is_sequential_multi", False),
        is_compensation=raw.get("is_compensation", False),
        called_element=raw.get("called_element") or None,
        documentation=raw.get("documentation", ""),
    )


def parse_bpmn_response(raw: str):
    """
    Parses the LLM BPMN JSON response into a BpmnProcess.

    Builds pools/lanes automatically from the 'lanes' list and the
    actor field on each element.
    """
    BpmnProcess, _, BpmnLane, BpmnPool, SequenceFlow = _bpmn_imports()
    data = _clean_json(raw)

    # ── Elements ──────────────────────────────────────────────────────────────
    elements = [_parse_element(e) for e in data.get("elements", [])]

    # ── Flows ─────────────────────────────────────────────────────────────────
    flows = [
        SequenceFlow(
            id=f["id"],
            source=f["source"],
            target=f["target"],
            name=f.get("name", ""),
            condition=f.get("condition", ""),
            is_default=f.get("is_default", False),
        )
        for f in data.get("flows", [])
    ]

    # ── Pools / Lanes ─────────────────────────────────────────────────────────
    lane_names: list[str] = data.get("lanes", [])

    # Also collect actor names from elements that weren't in the lanes list
    for el in elements:
        actor = el.actor or el.lane
        if actor and actor not in lane_names:
            lane_names.append(actor)

    pools = []
    if lane_names:
        pool = BpmnPool(id="pool_1", name=data.get("name", "Process"))
        for i, lane_name in enumerate(lane_names):
            lane_id = f"lane_{i + 1}"
            member_ids = [
                el.id for el in elements
                if (el.actor == lane_name or el.lane == lane_name)
                and el.type != "boundaryEvent"   # boundary events follow their host
            ]
            pool.lanes.append(BpmnLane(id=lane_id, name=lane_name, element_ids=member_ids))
        pools.append(pool)

    return BpmnProcess(
        name=data.get("name", "Process"),
        documentation=data.get("documentation", ""),
        elements=elements,
        flows=flows,
        pools=pools,
    )


# ════════════════════════════════════════════════════════════════════════════
#  PUBLIC ENTRY POINTS
# ════════════════════════════════════════════════════════════════════════════

def _lang_instruction(output_language: str) -> str:
    return {
        "Auto-detect":      "same language as the input transcript",
        "English":          "English",
        "Portuguese (BR)":  "Brazilian Portuguese",
    }.get(output_language, "same language as the input transcript")


def extract_process_llm(
    text: str,
    client_info: dict,
    provider: str,
    provider_cfg: dict,
    output_language: str = "Auto-detect",
) -> Process:
    """
    Original entry point — Mermaid / Draw.io.
    Unchanged interface; called by app.py as before.
    """
    system, user = build_prompt(text, _lang_instruction(output_language))
    raw = call_llm(system, user, client_info, provider_cfg)
    return parse_response(raw)


def extract_process_bpmn(
    text: str,
    client_info: dict,
    provider: str,
    provider_cfg: dict,
    output_language: str = "Auto-detect",
):
    """
    New entry point — BPMN 2.0 advanced extraction.
    Called by app.py when the user requests BPMN output.
    """
    system, user = build_bpmn_prompt(text, _lang_instruction(output_language))
    raw = call_llm(system, user, client_info, provider_cfg)
    return parse_bpmn_response(raw)
