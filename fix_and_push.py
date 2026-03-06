"""
fix_and_push.py
───────────────
Fixes extract_llm.py and diagram_mermaid.py, then commits and pushes.

Run from the ROOT of your process2diagram repository:

    python fix_and_push.py

Requirements: git must be configured with push access to the repo.
"""

import ast
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(".")


# ══════════════════════════════════════════════════════════════════════════════
#  FILE CONTENTS
# ══════════════════════════════════════════════════════════════════════════════

EXTRACT_LLM = r'''# modules/extract_llm.py

import json
import re
from modules.schema import Process, Step, Edge


def _bpmn_imports():
    from modules.schema import BpmnProcess, BpmnElement, BpmnLane, BpmnPool, SequenceFlow
    return BpmnProcess, BpmnElement, BpmnLane, BpmnPool, SequenceFlow


SYSTEM_PROMPT = """You are a business process analyst. Extract a structured process from a meeting transcript.

Return ONLY a valid JSON object, no markdown, no explanation, no code fences.

JSON schema:
{
  "name": "<process name>",
  "steps": [
    {
      "id": "S01",
      "title": "<short action label, NO actor name here>",
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
- CRITICAL: title must contain ONLY the action. NEVER include actor name in title.
  WRONG: sistema: Registrar chamado   RIGHT: Registrar chamado
- Decision steps: is_decision=true, two edges labeled sim/nao or yes/no.
- Titles SHORT 3-6 words. Decision titles must be questions.
- actor field: detect from context, normalize consistently.
- Output language: {output_language}
- Return ONLY the JSON."""


def build_prompt(text, output_language):
    system = SYSTEM_PROMPT.replace("{output_language}", output_language)
    user = "Extract the process from this transcript:\n\n" + text
    return system, user


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
  event_type: none | message | timer | error | escalation | cancel | compensation | signal | terminate | conditional | link

Rules:
1. Always start with startEvent, end with endEvent.
2. Every decision -> exclusiveGateway with named outgoing flows.
3. Parallel activities -> parallelGateway split + join.
4. Error/timeout -> boundaryEvent on the task.
5. Detect actors; map each to a lane.
6. IDs: SE1, T01-T99, GW1+, EE1+, BE1+, SP1+, F01+
7. Names SHORT max 6 words.
8. Output language: {output_language}
9. Return ONLY the JSON."""


def build_bpmn_prompt(text, output_language):
    system = BPMN_SYSTEM_PROMPT.replace("{output_language}", output_language)
    user = "Extract the BPMN process from this transcript:\n\n" + text
    return system, user


def call_llm(system, user, client_info, provider_cfg):
    client_type = provider_cfg["client_type"]
    api_key = client_info["api_key"]
    model = provider_cfg["default_model"]
    if client_type == "openai_compatible":
        return _call_openai_compatible(system, user, api_key, model, provider_cfg)
    elif client_type == "anthropic":
        return _call_anthropic(system, user, api_key, model)
    else:
        raise ValueError("Unknown client_type: " + client_type)


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


def _clean_json(raw):
    clean = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    start = clean.find("{")
    end = clean.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON in LLM response:\n" + raw[:300])
    return json.loads(clean[start:end])


def parse_response(raw):
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


def _parse_element(raw):
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


def parse_bpmn_response(raw):
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
            pool.lanes.append(BpmnLane(id="lane_" + str(i + 1), name=lane_name, element_ids=member_ids))
        pools.append(pool)
    return BpmnProcess(
        name=data.get("name", "Process"),
        documentation=data.get("documentation", ""),
        elements=elements, flows=flows, pools=pools,
    )


def _lang_instruction(output_language):
    return {
        "Auto-detect": "same language as the input transcript",
        "English": "English",
        "Portuguese (BR)": "Brazilian Portuguese",
    }.get(output_language, "same language as the input transcript")


def extract_process_llm(text, client_info, provider, provider_cfg, output_language="Auto-detect"):
    """Entry point for Mermaid / Draw.io extraction."""
    system, user = build_prompt(text, _lang_instruction(output_language))
    raw = call_llm(system, user, client_info, provider_cfg)
    return parse_response(raw)


def extract_process_bpmn(text, client_info, provider, provider_cfg, output_language="Auto-detect"):
    """Entry point for BPMN 2.0 extraction."""
    system, user = build_bpmn_prompt(text, _lang_instruction(output_language))
    raw = call_llm(system, user, client_info, provider_cfg)
    return parse_bpmn_response(raw)
'''

DIAGRAM_MERMAID = r'''# modules/diagram_mermaid.py

import re
import unicodedata
from modules.schema import Process, Step


def _sanitize(text):
    """Escape characters that break Mermaid labels."""
    return (
        text
        .replace('"', "'")
        .replace("\n", " ")
        .replace("[", "(")
        .replace("]", ")")
        .replace("{", "(")
        .replace("}", ")")
        .strip()
    )


def _safe_id(actor):
    """
    Convert actor name to a valid Mermaid subgraph ID (ASCII only).
    Mermaid 10.x rejects non-ASCII characters in subgraph IDs.
    """
    normalized = unicodedata.normalize("NFD", actor)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^\w]", "_", ascii_only)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return "lane_" + slug if slug else "lane_misc"


def _node(step):
    label = _sanitize(step.title)
    if step.is_decision:
        return '    ' + step.id + '{{ "' + label + '" }}'
    else:
        return '    ' + step.id + '["' + label + '"]'


def _has_actors(process):
    return any(s.actor for s in process.steps)


def generate_mermaid(process):
    if _has_actors(process):
        return _generate_with_swimlanes(process)
    return _generate_plain(process)


def _generate_plain(process):
    lines = ["flowchart TD"]
    for step in process.steps:
        lines.append(_node(step))
    lines.append("")
    for edge in process.edges:
        if edge.label:
            lines.append("    " + edge.source + " -->|" + _sanitize(edge.label) + "| " + edge.target)
        else:
            lines.append("    " + edge.source + " --> " + edge.target)
    return "\n".join(lines)


def _generate_with_swimlanes(process):
    actors_seen = []
    for step in process.steps:
        actor = step.actor or "Unassigned"
        if actor not in actors_seen:
            actors_seen.append(actor)

    lanes = {a: [] for a in actors_seen}
    for step in process.steps:
        actor = step.actor or "Unassigned"
        lanes[actor].append(step)

    lines = ["flowchart TD", ""]

    for actor in actors_seen:
        safe_id = _safe_id(actor)
        display = _sanitize(actor)
        lines.append('    subgraph ' + safe_id + '["' + display + '"]')
        lines.append("    direction TB")
        for step in lanes[actor]:
            lines.append("  " + _node(step))
        lines.append("    end")
        lines.append("")

    for edge in process.edges:
        if edge.label:
            lines.append("    " + edge.source + " -->|" + _sanitize(edge.label) + "| " + edge.target)
        else:
            lines.append("    " + edge.source + " --> " + edge.target)

    lane_colors = [
        "#EFF6FF", "#F0FDF4", "#FFF7ED", "#FAF5FF",
        "#FFF1F2", "#F0F9FF", "#FEFCE8", "#F7F7F7",
    ]
    lines.append("")
    for i, actor in enumerate(actors_seen):
        safe_id = _safe_id(actor)
        color = lane_colors[i % len(lane_colors)]
        lines.append(
            "    style " + safe_id +
            " fill:" + color + ",stroke:#CBD5E1,stroke-width:1px,color:#1e293b"
        )

    return "\n".join(lines)
'''


# ══════════════════════════════════════════════════════════════════════════════
#  WRITE + VALIDATE + COMMIT
# ══════════════════════════════════════════════════════════════════════════════

files = {
    "modules/extract_llm.py":    EXTRACT_LLM,
    "modules/diagram_mermaid.py": DIAGRAM_MERMAID,
}

print("\n── Writing files ────────────────────────────────────────")
for path_str, content in files.items():
    p = ROOT / path_str
    if not p.parent.exists():
        print(f"  ERROR: {p.parent} not found. Run from repo root.")
        sys.exit(1)
    # Validate syntax before writing
    try:
        ast.parse(content)
    except SyntaxError as e:
        print(f"  SYNTAX ERROR in {path_str}: {e}")
        sys.exit(1)
    p.write_text(content, encoding="utf-8")
    lines = content.count("\n")
    funcs = [l.strip()[:60] for l in content.splitlines() if l.startswith("def ")]
    print(f"  ✅ {path_str} ({lines} lines, {len(funcs)} functions)")

print("\n── Verifying key functions ──────────────────────────────")
extract_content = (ROOT / "modules/extract_llm.py").read_text()
mermaid_content = (ROOT / "modules/diagram_mermaid.py").read_text()

checks = [
    ("extract_llm.py",    "def extract_process_llm(",  extract_content),
    ("extract_llm.py",    "def extract_process_bpmn(", extract_content),
    ("diagram_mermaid.py","def generate_mermaid(",     mermaid_content),
    ("diagram_mermaid.py","def _safe_id(",             mermaid_content),
    ("diagram_mermaid.py","unicodedata",               mermaid_content),
]
for fname, token, content in checks:
    ok = token in content
    print(f"  {'✅' if ok else '❌'} {fname}: {token}")
    if not ok:
        sys.exit(1)

print("\n── Git commit & push ────────────────────────────────────")
cmds = [
    ["git", "add", "modules/extract_llm.py", "modules/diagram_mermaid.py"],
    ["git", "commit", "-m", "fix: restore extract_llm + ASCII-safe mermaid swimlane IDs"],
    ["git", "push"],
]
for cmd in cmds:
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout.strip():
        print("   ", result.stdout.strip())
    if result.returncode != 0:
        if "nothing to commit" in result.stderr or "nothing to commit" in result.stdout:
            print("   (nothing new to commit — files already up to date)")
        else:
            print(f"  ERROR: {result.stderr.strip()}")
            sys.exit(1)

print("\n✅  Done. Streamlit Cloud will redeploy automatically.")
