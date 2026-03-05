# modules/extract_llm.py

import json
import re
from modules.schema import Process, Step, Edge


# ── BPMN classes loaded lazily to avoid ImportError if schema is old ──────────

def _bpmn_imports():
    from modules.schema import BpmnProcess, BpmnElement, BpmnLane, BpmnPool, SequenceFlow
    return BpmnProcess, BpmnElement, BpmnLane, BpmnPool, SequenceFlow


# ══════════════════════════════════════════════════════════════════════════════
#  PROMPT — Mermaid / Draw.io
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """You are a business process analyst. Extract a structured process from a meeting transcript.

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
- Step IDs: S01, S02, S03 in order.
- CRITICAL: "title" must contain ONLY the action. NEVER include actor name in title.
  WRONG: "sistema: Registrar chamado"  RIGHT: "Registrar chamado"
- For decision steps set is_decision=true and create two edges labeled "sim"/"nao" or "yes"/"no".
- Titles SHORT (3-6 words). Decision titles must be questions (e.g. "Prioridade alta?").
- actor field: detect from context. Normalize consistently (one canonical name per role).
- Output language: {output_language}
- Return ONLY the JSON."""


def build_prompt(text: str, output_language: str) -> tuple[str, str]:
    system = SYSTEM_PROMPT.replace("{output_language}", output_language)
    user = f"Extract the process from this transcript:\n\n{text}"
    return system, user


# ══════════════════════════════════════════════════════════════════════════════
#  PROMPT — BPMN 2.0
# ══════════════════════════════════════════════════════════════════════════════

BPMN_SYSTEM_PROMPT = """You are a certified BPMN 2.0 process analyst.
Extract a complete BPMN process model from a meeting transcript.

Return ONLY a valid JSON object. No markdown, no explanation, no code fences.

JSON schema:
{
  "name": "<process name>",
  "documentation": "<brief description>",
  "lanes": ["Actor A", "Actor B"],
  "elements": [
    {"id": "SE1", "type": "startEvent", "name": "Start", "actor": null, "event_type": "none"},
    {"id": "T01", "type": "userTask", "name": "<label>", "actor": "<lane or null>",
     "is_loop": false, "is_parallel_multi": false, "is_sequential_multi": false, "documentation": ""},
    {"id": "GW1", "type": "exclusiveGateway", "name": "<question>", "actor": null},
    {"id": "EE1", "type": "endEvent", "name": "End", "actor": null, "event_type": "terminate"},
    {"id": "BE1", "type": "boundaryEvent", "name": "Timeout", "attached_to": "T01",
     "is_interrupting": true, "event_type": "timer", "actor": null},
    {"id": "SP1", "type": "subProcess", "name": "<label>", "actor": null, "is_expanded": true,
     "children": [{"id": "SP1_T1", "type": "task", "name": "Inner Task", "actor": null}]}
  ],
  "flows": [
    {"id": "F01", "source": "SE1", "target": "T01", "name": ""},
    {"id": "F02", "source": "GW1", "target": "T02", "name": "Yes", "condition": ""},
    {"id": "F03", "source": "GW1", "target": "EE1", "name": "No", "is_default": false}
  ]
}

Element types:
  Events: startEvent, endEvent, intermediateThrowEvent, intermediateCatchEvent, boundaryEvent
  Tasks: userTask, serviceTask, scriptTask, sendTask, receiveTask, manualTask, businessRuleTask, callActivity, task
  Gateways: exclusiveGateway, parallelGateway, inclusiveGateway, eventBasedGateway, complexGateway
  Sub-processes: subProcess, adHocSubProcess

event_type values: none | message | timer | error | escalation | cancel | compensation | signal | terminate | conditional | link

Rules:
1. Always start with startEvent, end with endEvent.
2. Every decision -> exclusiveGateway with named outgoing flows.
3. Parallel activities -> parallelGateway split + join.
4. Error/timeout -> boundaryEvent on the task.
5. Detect actors; map each to a lane.
6. IDs: SE1, T01-T99, GW1+, EE1+, BE1+, SP1+, F01+
7. Names SHORT (max 6 words).
8. Output language: {output_language}
9. Return ONLY the JSON."""


def build_bpmn_prompt(text: str, output_language: str) -> tuple[str, str]:
    system = BPMN_SYSTEM_PROMPT.replace("{output_language}", output_language)
    user = f"Extract the BPMN process from this transcript:\n\n{text}"
    return system, user


# ══════════════════════════════════════════════════════════════════════════════
#  LLM ROUTING
# ══════════════════════════════════════════════════════════════════════════════

def call_llm(system: str, user: str, client_info: dict, provider_cfg: dict) -> str:
    client_type = provider_cfg["client_type"]
    api_key = client_info["api_key"]
    model = provider_cfg["default_model"]

    if client_type == "openai_compatible":
        return _call_openai_compatible(system, user, api_key, model, provider_cfg)
    elif client_type == "anthropic":
        return _call_anthropic(system, user, api_key, model)
    else:
        raise ValueError(f"Unknown client_type: {client_type}")


def _call_openai_compatible(system, user, api_key, model, provider_cfg):
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=provider_cfg.get("base_url"))
    kwargs = dict(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        max_tokens=4096,
        temperature=0.1,
    )
    if provider_cfg.get("supports_json_mode"):
        kwargs["response_format"] = {"type": "json_object"}
    response = client.chat.completions.create(**kwargs)
    return response.choices[0].message.content


def _call_anthropic(system, user, api_key, model):
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model, max_tokens=4096, temperature=0.1,
        system=system, messages=[{"role": "user", "content": user}],
    )
    return message.content[0].text


# ══════════════════════════════════════════════════════════════════════════════
#  RESPONSE PARSING — Mermaid / Draw.io
# ══════════════════════════════════════════════════════════════════════════════

def _clean_json(raw: str) -> dict:
    clean = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    start = clean.find("{")
    end = clean.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON in LLM response:\n{raw[:300]}")
    return json.loads(clean[start:end])


def parse_response(raw: str) -> Process:
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


# ══════════════════════════════════════════════════════════════════════════════
#  RESPONSE PARSING — BPMN
# ══════════════════════════════════════════════════════════════════════════════

def _parse_element(raw: dict):
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
    BpmnProcess, _, BpmnLane, BpmnPool, SequenceFlow = _bpmn_imports()
    data = _clean_json(raw)

    elements = [_parse_element(e) for e in data.get("elements", [])]

    flows = [
        SequenceFlow(
            id=f["id"], source=f["source"], target=f["target"],
            name=f.get("name", ""), condition=f.get("condition", ""),
            is_default=f.get("is_default", False),
        )
        for f in data.get("flows", [])
    ]

    lane_names = list(data.get("lanes", []))
    for el in elements:
        actor = el.actor or el.lane
        if actor and actor not in lane_names:
            lane_names.append(actor)

    pools = []
    if lane_names:
        pool = BpmnPool(id="pool_1", name=data.get("name", "Process"))
        for i, lane_name in enumerate(lane_names):
            member_ids = [
                el.id for el in elements
                if (el.actor == lane_name or el.lane == lane_name)
                and el.type != "boundaryEvent"
            ]
            pool.lanes.append(BpmnLane(id=f"lane_{i+1}", name=lane_name, element_ids=member_ids))
        pools.append(pool)

    return BpmnProcess(
        name=data.get("name", "Process"),
        documentation=data.get("documentation", ""),
        elements=elements, flows=flows, pools=pools,
    )


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC ENTRY POINTS
# ══════════════════════════════════════════════════════════════════════════════

def _lang_instruction(output_language: str) -> str:
    return {
        "Auto-detect": "same language as the input transcript",
        "English": "English",
        "Portuguese (BR)": "Brazilian Portuguese",
    }.get(output_language, "same language as the input transcript")


def extract_process_llm(
    text: str,
    client_info: dict,
    provider: str,
    provider_cfg: dict,
    output_language: str = "Auto-detect",
) -> Process:
    """Entry point for Mermaid / Draw.io extraction. Called by app.py."""
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
    """Entry point for BPMN 2.0 extraction. Called by app.py."""
    system, user = build_bpmn_prompt(text, _lang_instruction(output_language))
    raw = call_llm(system, user, client_info, provider_cfg)
    return parse_bpmn_response(raw)
