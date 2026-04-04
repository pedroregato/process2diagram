# agents/agent_bpmn.py
# ─────────────────────────────────────────────────────────────────────────────
# BPMN Agent — expert em BPMN 2.0 (OMG / ISO-IEC 19510).
#
# Reads:  hub.transcript_clean, hub.nlp (actors, segments)
# Writes: hub.bpmn  (BPMNModel — steps, edges, lanes, mermaid,
#                                bpmn_xml via bpmn_generator)
#
# Supports two LLM output formats:
#   Flat  (single-pool): { "name", "steps", "edges", "lanes" }
#   Multi-pool:          { "name", "pools": [...], "message_flows": [...] }
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re as _re
import unicodedata as _ud

from agents.base_agent import BaseAgent
from core.knowledge_hub import (
    KnowledgeHub, BPMNModel, BPMNStep, BPMNEdge,
    BPMNPoolData, BPMNMessageFlow,
)


def _ascii_id(s: str) -> str:
    """Normalize a string to a safe ASCII XML id segment."""
    nfkd = _ud.normalize("NFKD", s)
    return "".join(c for c in nfkd if _ud.category(c) != "Mn").lower().replace(" ", "_")


def _infer_lane_name(generic_name: str, model: BPMNModel,
                     nlp_actors: list | None = None) -> str:
    """
    Infer a real organizational lane name from three sources, in priority order:

    Priority 1 — step.actor fields for steps in the generic lane.
        If a step already has a non-generic actor assigned by the LLM, that
        actor is the most direct answer.  Prefer NLP-normalized form when
        there is a close match.

    Priority 2 — NLP actors that appear verbatim in step texts for this lane.
        Uses hub.nlp.actors (named entities detected before the LLM call).

    Priority 3 — regex over step titles/descriptions (original heuristic).
    """
    from collections import Counter

    _GENERIC_SET = {
        "usuário", "usuario", "user", "utilizador",
        "validador", "validator", "revisor", "reviewer",
        "sistema", "system", "automático", "automatic",
        "ator", "actor", "papel", "role", "pessoa", "person",
        "participante", "participant",
    }

    # ── Priority 1: step actor fields ────────────────────────────────────────
    actor_candidates = [
        s.actor for s in model.steps
        if s.lane == generic_name
        and s.actor
        and s.actor.lower().strip() not in _GENERIC_SET
    ]
    if actor_candidates:
        best = Counter(actor_candidates).most_common(1)[0][0]
        if nlp_actors:
            for nlp_actor in nlp_actors:
                if (nlp_actor.lower() in best.lower()
                        or best.lower() in nlp_actor.lower()):
                    return nlp_actor   # prefer NLP-normalized form
        return best

    # ── Priority 2: NLP actors appearing in step texts ───────────────────────
    if nlp_actors:
        lane_text = " ".join(
            (s.title or "") + " " + (s.description or "")
            for s in model.steps if s.lane == generic_name
        )
        nlp_hits = Counter(a for a in nlp_actors if a in lane_text)
        if nlp_hits:
            return nlp_hits.most_common(1)[0][0]

    # ── Priority 3: regex heuristic (original) ───────────────────────────────
    texts = []
    for step in model.steps:
        if step.lane == generic_name:
            texts.append(step.title)
            texts.append(step.description)
    combined = " ".join(texts)

    org_patterns = [
        r'\b(Equipe\s+de\s+[A-ZÁÉÍÓÚÃÕ][a-záéíóúãõ]+(?:\s+[A-ZÁÉÍÓÚÃÕ][a-záéíóúãõ]+)*)\b',
        r'\b(Gestores?\s+[A-ZÁÉÍÓÚÃÕ][a-záéíóúãõ]+(?:\s+[A-ZÁÉÍÓÚÃÕ][a-záéíóúãõ]+)*)\b',
        r'\b([A-ZÁÉÍÓÚÃÕ][a-záéíóúãõ]+(?:\s+[A-ZÁÉÍÓÚÃÕ][a-záéíóúãõ]+){1,3})\b',
    ]
    _STOP_WORDS = {
        "cadastrar", "cadastro", "enviar", "validar", "processar",
        "organograma", "escola", "unidade", "após", "para", "com",
        "início", "iniciar", "ajustar", "devolvido",
    }
    candidates: list[str] = []
    for pattern in org_patterns:
        for match in _re.finditer(pattern, combined):
            phrase = match.group(1).strip()
            words = phrase.lower().split()
            if any(w in _STOP_WORDS for w in words):
                continue
            if 2 <= len(phrase.split()) <= 4:
                candidates.append(phrase)
    if candidates:
        return Counter(candidates).most_common(1)[0][0]

    return generic_name


# ── Event task_type constants ─────────────────────────────────────────────────

# New event task_types introduced in skill v3.0 that map to BPMN element types.
_EVENT_TASK_TYPE_MAP: dict[str, tuple[str, str]] = {
    "noneStartEvent":               ("startEvent",             "none"),
    "startMessageEvent":            ("startEvent",             "message"),
    "startTimerEvent":              ("startEvent",             "timer"),
    "noneEndEvent":                 ("endEvent",               "none"),
    "endMessageEvent":              ("endEvent",               "message"),
    "errorEndEvent":                ("endEvent",               "error"),
    "intermediateTimerCatchEvent":  ("intermediateCatchEvent", "timer"),
    "intermediateMessageCatchEvent":("intermediateCatchEvent", "message"),
    "intermediateMessageThrowEvent":("intermediateThrowEvent", "message"),
    # Legacy / generic event types that the LLM still sometimes emits
    "startEvent":                   ("startEvent",             "none"),
    "endEvent":                     ("endEvent",               "none"),
    "start":                        ("startEvent",             "none"),
    "end":                          ("endEvent",               "none"),
}

# task_types that represent start events (generator adds its own for single-pool)
_START_TYPES = {"noneStartEvent", "startMessageEvent", "startTimerEvent", "startEvent", "start"}
# task_types that represent end events
_END_TYPES   = {"noneEndEvent", "endMessageEvent", "errorEndEvent", "endEvent", "end"}

_TASK_TYPE_MAP = {
    "userTask":         "userTask",
    "serviceTask":      "serviceTask",
    "scriptTask":       "scriptTask",
    "manualTask":       "manualTask",
    "businessRuleTask": "businessRuleTask",
    "parallelGateway":  "parallelGateway",
    "exclusiveGateway": "exclusiveGateway",
    "inclusiveGateway": "inclusiveGateway",
}


class AgentBPMN(BaseAgent):

    name = "bpmn"
    skill_path = "skills/skill_bpmn.md"

    # ── Prompt ────────────────────────────────────────────────────────────────

    def build_prompt(self, hub: KnowledgeHub, output_language: str = "Auto-detect") -> tuple[str, str]:
        lang = self._language_instruction(output_language)
        system = self._skill.replace("{output_language}", lang)

        actor_hint = ""
        if hub.nlp.actors:
            actor_hint = f"\nActors identified by NLP pre-processing: {', '.join(hub.nlp.actors)}"

        user = (
            f"Extract the BPMN 2.0 process from this transcript:{actor_hint}\n\n"
            f"{hub.transcript_clean}"
        )
        return system, user

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self, hub: KnowledgeHub, output_language: str = "Auto-detect") -> KnowledgeHub:
        system, user = self.build_prompt(hub, output_language)
        data = self._call_with_retry(system, user, hub)

        hub.bpmn = self._build_model(data)
        self._enforce_rules(hub.bpmn, getattr(hub.nlp, "actors", None))
        try:
            from modules.bpmn_auto_repair import repair_bpmn
            repair_bpmn(hub.bpmn)
        except Exception:
            pass
        hub.bpmn.mermaid  = self._generate_mermaid(hub.bpmn)
        hub.bpmn.bpmn_xml = self._generate_bpmn_xml(hub.bpmn)
        hub.bpmn.ready = True
        hub.mark_agent_run(self.name)
        hub.bump()
        return hub

    # ── Model building ────────────────────────────────────────────────────────

    @staticmethod
    def _build_model(data: dict) -> BPMNModel:
        """Dispatch to flat or multi-pool builder based on JSON structure."""
        if not isinstance(data, dict):
            return BPMNModel(name="Process")
        pools_val = data.get("pools")
        # Use multi-pool only when "pools" is a non-empty list of dicts
        if isinstance(pools_val, list) and pools_val and isinstance(pools_val[0], dict):
            return AgentBPMN._build_model_multi(data)
        return AgentBPMN._build_model_flat(data)

    @staticmethod
    def _build_model_flat(data: dict) -> BPMNModel:
        """Parse flat single-pool format: { steps, edges, lanes }."""
        steps = [
            BPMNStep(
                id=s["id"],
                title=s.get("title", "Step"),
                description=s.get("description", ""),
                actor=s.get("actor") or None,
                is_decision=s.get("is_decision", False),
                task_type=s.get("task_type", "userTask"),
                lane=s.get("lane") or None,
            )
            for s in data.get("steps", [])
        ]
        edges = [
            BPMNEdge(
                source=e["source"],
                target=e["target"],
                label=e.get("label", ""),
                condition=e.get("condition", ""),
            )
            for e in data.get("edges", [])
        ]
        return BPMNModel(
            name=data.get("name", "Process"),
            steps=steps,
            edges=edges,
            lanes=data.get("lanes", []),
        )

    @staticmethod
    def _build_model_multi(data: dict) -> BPMNModel:
        """
        Parse multi-pool format:
          { "name", "pools": [{ "id", "name", "process": { steps, edges, lanes } }],
            "message_flows": [{ "id", "name", "source": {pool,step}, "target": {pool,step} }] }

        Step IDs are namespaced with a pool prefix (p1_, p2_...) in the
        flattened model.steps/edges so that enforce_rules works across pools
        without ID collisions.
        """
        pool_models: list[BPMNPoolData] = []
        all_steps:  list[BPMNStep] = []
        all_edges:  list[BPMNEdge] = []
        all_lanes:  list[str] = []

        for i, pool_data in enumerate(data.get("pools", [])):
            if not isinstance(pool_data, dict):
                continue   # skip malformed pool entries
            prefix   = f"p{i + 1}_"
            pool_id  = pool_data.get("id", f"pool_{i + 1}")
            pool_name = pool_data.get("name", f"Pool {i + 1}")
            proc     = pool_data.get("process", {})

            raw_steps = proc.get("steps", [])
            raw_edges = proc.get("edges", [])
            raw_lanes = proc.get("lanes", [])

            orig_steps = [
                BPMNStep(
                    id=s["id"],
                    title=s.get("title", "Step"),
                    description=s.get("description", ""),
                    actor=s.get("actor") or None,
                    is_decision=s.get("is_decision", False),
                    task_type=s.get("task_type", "userTask"),
                    lane=s.get("lane") or None,
                )
                for s in raw_steps
            ]
            orig_edges = [
                BPMNEdge(
                    source=e["source"],
                    target=e["target"],
                    label=e.get("label", ""),
                    condition=e.get("condition", ""),
                )
                for e in raw_edges
            ]

            pool_models.append(BPMNPoolData(
                pool_id=pool_id,
                name=pool_name,
                steps=orig_steps,
                edges=orig_edges,
                lanes=list(raw_lanes),
            ))

            # Flatten into model with prefixed IDs
            for s in orig_steps:
                all_steps.append(BPMNStep(
                    id=prefix + s.id,
                    title=s.title,
                    description=s.description,
                    actor=s.actor,
                    is_decision=s.is_decision,
                    task_type=s.task_type,
                    lane=s.lane,
                ))
            for e in orig_edges:
                all_edges.append(BPMNEdge(
                    source=prefix + e.source,
                    target=prefix + e.target,
                    label=e.label,
                    condition=e.condition,
                ))
            for lane_name in raw_lanes:
                if lane_name not in all_lanes:
                    all_lanes.append(lane_name)

        # Message flows
        mf_list: list[BPMNMessageFlow] = []
        for mf in data.get("message_flows", []):
            src = mf.get("source", {})
            tgt = mf.get("target", {})
            mf_list.append(BPMNMessageFlow(
                id=mf.get("id", f"mf_{len(mf_list) + 1}"),
                source_pool=src.get("pool", ""),
                source_step=src.get("step", ""),
                target_pool=tgt.get("pool", ""),
                target_step=tgt.get("step", ""),
                name=mf.get("name", ""),
            ))

        return BPMNModel(
            name=data.get("name", "Process"),
            steps=all_steps,
            edges=all_edges,
            lanes=all_lanes,
            is_collaboration=True,
            pool_models=pool_models,
            message_flows_data=mf_list,
        )

    # ── Post-extraction rule enforcement ─────────────────────────────────────

    @staticmethod
    def _enforce_rules(model: BPMNModel, nlp_actors: list | None = None) -> None:
        """
        Deterministic post-processing. Mutates the model in-place.

        Rule 0  — remove steps the LLM declared as start/end events
                  (single-pool only; multi-pool handles events explicitly)
        Rule 1  — serviceTask with unnamed system actor → lane = None
        Rule 1b — generic lane names → infer from step descriptions
        Rule 2  — correction loop pointing back to gateway → redirect to
                  the upstream work step that feeds the gateway
        """
        # ── Rule 0: strip redundant start/end event steps (single-pool) ──────
        if not model.is_collaboration:
            event_step_ids = {
                s.id for s in model.steps
                if s.task_type in (_START_TYPES | _END_TYPES)
            }
            if event_step_ids:
                model.steps = [s for s in model.steps if s.id not in event_step_ids]
                model.edges = [
                    e for e in model.edges
                    if e.source not in event_step_ids and e.target not in event_step_ids
                ]

        # ── Rule 1b: generic lane names → infer from step descriptions ───────
        _GENERIC_LANE_NAMES = {
            "usuário", "usuario", "user", "utilizador",
            "validador", "validator", "revisor", "reviewer",
            "sistema", "system", "automático", "automatic",
            "ator", "actor", "papel", "role", "pessoa", "person",
            "participante", "participant",
        }
        lane_replacement: dict[str, str] = {}
        for lane_name in list(model.lanes):
            if lane_name.lower().strip() in _GENERIC_LANE_NAMES:
                candidate = _infer_lane_name(lane_name, model, nlp_actors)
                if candidate and candidate != lane_name:
                    lane_replacement[lane_name] = candidate

        if lane_replacement:
            model.lanes = [lane_replacement.get(ln, ln) for ln in model.lanes]
            for step in model.steps:
                if step.lane in lane_replacement:
                    step.lane = lane_replacement[step.lane]
            for pm in model.pool_models:
                pm.lanes = [lane_replacement.get(ln, ln) for ln in pm.lanes]
                for step in pm.steps:
                    if step.lane in lane_replacement:
                        step.lane = lane_replacement[step.lane]

        _GENERIC_ACTORS = {
            "sistema", "system", "automático", "automatic",
            "automaticamente", "auto", None,
        }

        step_map = {s.id: s for s in model.steps}

        # ── Rule 1: serviceTask with unnamed system → lane = None ─────────────
        for step in model.steps:
            if step.task_type == "serviceTask":
                actor_lower = (step.actor or "").lower().strip()
                if actor_lower in _GENERIC_ACTORS or not actor_lower:
                    step.lane = None

        # ── Rule 2: correction loop pointing back to a gateway ─────────────────
        outgoing: dict[str, list] = {s.id: [] for s in model.steps}
        for edge in model.edges:
            if edge.source in outgoing:
                outgoing[edge.source].append(edge)

        incoming: dict[str, list[str]] = {s.id: [] for s in model.steps}
        for edge in model.edges:
            if edge.target in incoming:
                incoming[edge.target].append(edge.source)

        _ALL_GW_TYPES = {
            "exclusiveGateway", "parallelGateway", "inclusiveGateway",
            "eventBasedGateway", "complexGateway", "gateway",
        }
        gateway_ids = {
            s.id for s in model.steps
            if s.is_decision or s.task_type in _ALL_GW_TYPES
        }

        for edge in model.edges:
            if edge.target not in gateway_ids:
                continue

            gw_id         = edge.target
            correction_id = edge.source
            gw_step        = step_map.get(gw_id)
            correction_step = step_map.get(correction_id)
            if not gw_step or not correction_step:
                continue

            gw_out_targets = {e.target for e in outgoing.get(gw_id, [])}
            if correction_id not in gw_out_targets:
                continue

            upstream_candidates = [
                src for src in incoming.get(gw_id, [])
                if src != correction_id and src in step_map
            ]
            if not upstream_candidates:
                continue

            same_lane = [
                c for c in upstream_candidates
                if step_map[c].lane == correction_step.lane
            ]
            best = same_lane[0] if same_lane else upstream_candidates[0]
            edge.target = best

    # ── BPMN XML generation ───────────────────────────────────────────────────

    @staticmethod
    def _generate_bpmn_xml(model: BPMNModel) -> str:
        try:
            from modules.schema import (
                BpmnProcess, BpmnElement, BpmnPool, BpmnLane,
                SequenceFlow, MessageFlow,
            )
            from modules.bpmn_generator import generate_bpmn_xml

            if model.is_collaboration:
                return AgentBPMN._generate_bpmn_xml_multi(
                    model, BpmnProcess, BpmnElement, BpmnPool,
                    BpmnLane, SequenceFlow, MessageFlow, generate_bpmn_xml,
                )
            return AgentBPMN._generate_bpmn_xml_single(
                model, BpmnProcess, BpmnElement, BpmnPool,
                BpmnLane, SequenceFlow, generate_bpmn_xml,
            )
        except Exception:
            return ""

    # ── Single-pool BPMN XML bridge ───────────────────────────────────────────

    @staticmethod
    def _generate_bpmn_xml_single(model, BpmnProcess, BpmnElement, BpmnPool,
                                  BpmnLane, SequenceFlow, generate_bpmn_xml) -> str:
        elements = []
        for i, step in enumerate(model.steps):
            if step.is_decision:
                el_type = "exclusiveGateway"
            elif step.task_type in _EVENT_TASK_TYPE_MAP:
                # Intermediate events are kept; start/end already stripped by Rule 0
                el_type_str, ev_type = _EVENT_TASK_TYPE_MAP[step.task_type]
                if "intermediate" in el_type_str.lower():
                    elements.append(BpmnElement(
                        id=step.id, name=step.title,
                        type=el_type_str, event_type=ev_type,
                        lane=step.lane, actor=step.actor,
                        documentation=step.description or "",
                    ))
                    if i == 0:
                        elements.insert(0, BpmnElement(
                            id="ev_start", name="Início", type="startEvent",
                            lane=step.lane, actor=None,
                        ))
                    if i == len(model.steps) - 1:
                        source_ids = {e.source for e in model.edges}
                        terminal = [s for s in model.steps if s.id not in source_ids]
                        end_lane = terminal[-1].lane if terminal else step.lane
                        elements.append(BpmnElement(
                            id="ev_end", name="Fim", type="endEvent",
                            lane=end_lane, actor=None,
                        ))
                    continue
                else:
                    el_type = _TASK_TYPE_MAP.get(step.task_type, "userTask")
            else:
                el_type = _TASK_TYPE_MAP.get(step.task_type, "userTask")

            if i == 0:
                elements.append(BpmnElement(
                    id="ev_start", name="Início", type="startEvent",
                    actor=None, lane=step.lane,
                ))

            elements.append(BpmnElement(
                id=step.id, name=step.title, type=el_type,
                actor=step.actor, lane=step.lane,
                documentation=step.description or "",
            ))

            if i == len(model.steps) - 1:
                source_ids = {e.source for e in model.edges}
                terminal = [s for s in model.steps if s.id not in source_ids]
                end_lane = terminal[-1].lane if terminal else step.lane
                elements.append(BpmnElement(
                    id="ev_end", name="Fim", type="endEvent",
                    actor=None, lane=end_lane,
                ))

        flows = []
        if model.steps:
            flows.append(SequenceFlow(id="sf_start", source="ev_start",
                                      target=model.steps[0].id))
        for i, edge in enumerate(model.edges):
            flows.append(SequenceFlow(
                id=f"sf_{i + 1:03d}",
                source=edge.source, target=edge.target,
                name=edge.label or "", condition=edge.condition or "",
            ))
        if model.steps:
            source_ids = {e.source for e in model.edges}
            terminal = [s for s in model.steps if s.id not in source_ids]
            if not terminal:
                terminal = [model.steps[-1]]
            for _j, _term in enumerate(terminal):
                _fid = "sf_end" if _j == 0 else f"sf_end_{_j}"
                flows.append(SequenceFlow(id=_fid, source=_term.id,
                                          target="ev_end"))

        pools = []
        if model.lanes:
            lane_objects = []
            for lane_name in model.lanes:
                lane_id = "lane_" + _ascii_id(lane_name)
                member_ids = [
                    s.id for s in model.steps
                    if s.lane and s.lane.lower() == lane_name.lower()
                ]
                lane_objects.append(BpmnLane(
                    id=lane_id, name=lane_name, element_ids=member_ids,
                ))
            pools.append(BpmnPool(id="pool_1", name=model.name,
                                  lanes=lane_objects))

        bpmn_process = BpmnProcess(
            name=model.name,
            elements=elements,
            flows=flows,
            pools=pools,
        )
        return generate_bpmn_xml(bpmn_process)

    # ── Multi-pool BPMN XML bridge ────────────────────────────────────────────

    @staticmethod
    def _generate_bpmn_xml_multi(model, BpmnProcess, BpmnElement, BpmnPool,
                                 BpmnLane, SequenceFlow, MessageFlow,
                                 generate_bpmn_xml) -> str:
        """
        Build a BpmnProcess with one BpmnPool per pool_model, each pool
        carrying its own elements and flows.  Message flows are added as
        MessageFlow objects referencing prefixed element IDs.
        """
        pools = []

        # Map pool_id → (xml_pool_id, prefix) for message flow resolution
        pool_id_to_xml:    dict[str, str] = {}
        pool_id_to_prefix: dict[str, str] = {}

        for i, pm in enumerate(model.pool_models):
            prefix       = f"p{i + 1}_"
            xml_pool_id  = f"pool_{i + 1}"
            pool_id_to_xml[pm.pool_id]    = xml_pool_id
            pool_id_to_prefix[pm.pool_id] = prefix

            elements = _build_pool_elements(pm, prefix, BpmnElement)
            flows    = _build_pool_flows(pm, prefix, elements, SequenceFlow)
            lanes    = _build_pool_lanes(pm, prefix, xml_pool_id, elements, BpmnLane)

            pools.append(BpmnPool(
                id=xml_pool_id,
                name=pm.name,
                lanes=lanes,
                elements=elements,
                flows=flows,
            ))

        # Build MessageFlow objects (resolve pool aliases and "start"/"end")
        schema_mf = []
        for mf in model.message_flows_data:
            src_prefix = pool_id_to_prefix.get(mf.source_pool, "p1_")
            tgt_prefix = pool_id_to_prefix.get(mf.target_pool, "p2_")

            src_id = _resolve_mf_step(mf.source_step, src_prefix, "throw")
            tgt_id = _resolve_mf_step(mf.target_step, tgt_prefix, "catch")

            schema_mf.append(MessageFlow(
                id=mf.id,
                source=src_id,
                target=tgt_id,
                name=mf.name,
            ))

        bpmn_process = BpmnProcess(
            name=model.name,
            elements=[],    # elements are owned by each pool
            flows=[],       # flows are owned by each pool
            pools=pools,
            message_flows=schema_mf,
        )
        return generate_bpmn_xml(bpmn_process)

    # ── Mermaid generator ─────────────────────────────────────────────────────

    @staticmethod
    def _generate_mermaid(model: BPMNModel) -> str:
        if model.is_collaboration:
            return AgentBPMN._generate_mermaid_multi(model)
        return AgentBPMN._generate_mermaid_single(model)

    @staticmethod
    def _generate_mermaid_single(model: BPMNModel) -> str:
        lines = ["flowchart TD"]
        for step in model.steps:
            label = step.title.replace('"', "'")
            if step.is_decision:
                lines.append(f'    {step.id}{{"{label}"}}')
            elif step.task_type in _EVENT_TASK_TYPE_MAP:
                lines.append(f'    {step.id}(("{label}"))')
            else:
                lines.append(f'    {step.id}["{label}"]')
        for edge in model.edges:
            if edge.label:
                safe = edge.label.replace('"', "'").replace("|", "/")
                lines.append(f"    {edge.source} -->|{safe}| {edge.target}")
            else:
                lines.append(f"    {edge.source} --> {edge.target}")
        for step in model.steps:
            if step.is_decision:
                lines.append(f"    style {step.id} fill:#fff3cd,stroke:#f59e0b")
        return "\n".join(lines)

    @staticmethod
    def _generate_mermaid_multi(model: BPMNModel) -> str:
        lines = ["flowchart TD"]

        for i, pm in enumerate(model.pool_models):
            prefix    = f"p{i + 1}_"
            pool_name = pm.name.replace('"', "'")
            lines.append(f'    subgraph {prefix}pool["{pool_name}"]')
            for step in pm.steps:
                sid   = prefix + step.id
                label = step.title.replace('"', "'")
                if step.is_decision:
                    lines.append(f'        {sid}{{"{label}"}}')
                elif step.task_type in _EVENT_TASK_TYPE_MAP:
                    lines.append(f'        {sid}(("{label}"))')
                else:
                    lines.append(f'        {sid}["{label}"]')
            for edge in pm.edges:
                src = prefix + edge.source
                tgt = prefix + edge.target
                if edge.label:
                    safe = edge.label.replace('"', "'").replace("|", "/")
                    lines.append(f"        {src} -->|{safe}| {tgt}")
                else:
                    lines.append(f"        {src} --> {tgt}")
            lines.append("    end")

        # Message flows as dashed arrows
        pool_prefix: dict[str, str] = {
            pm.pool_id: f"p{i + 1}_"
            for i, pm in enumerate(model.pool_models)
        }
        for mf in model.message_flows_data:
            src_pfx = pool_prefix.get(mf.source_pool, "p1_")
            tgt_pfx = pool_prefix.get(mf.target_pool, "p2_")
            src_id  = _resolve_mf_step(mf.source_step, src_pfx, "throw")
            tgt_id  = _resolve_mf_step(mf.target_step, tgt_pfx, "catch")
            label   = mf.name or "msg"
            lines.append(f"    {src_id} -. {label} .-> {tgt_id}")

        return "\n".join(lines)


# ── Pool builder helpers (module-level for readability) ───────────────────────

def _resolve_mf_step(step_ref: str, prefix: str, direction: str) -> str:
    """
    Resolve a message-flow step reference to a prefixed element ID.
    - "start" → ev_start of that pool
    - "end"   → ev_end of that pool
    - anything else → prefixed step id
    direction = "throw" | "catch" (used only to pick ev_end vs ev_start
    when the reference is ambiguous)
    """
    if step_ref in ("start", "ev_start"):
        return prefix + "ev_start"
    if step_ref in ("end", "ev_end"):
        return prefix + "ev_end"
    return prefix + step_ref


def _build_pool_elements(pm: BPMNPoolData, prefix: str, BpmnElement) -> list:
    """
    Build the BpmnElement list for one pool.
    Handles the new event task_types from skill v3.0.
    If no explicit start/end event step is present, synthetic ones are injected.
    """
    from modules.schema import BpmnElement as _BE  # noqa: F401 (type alias)

    steps = pm.steps
    if not steps:
        return []

    has_start = any(s.task_type in _START_TYPES for s in steps)
    has_end   = any(s.task_type in _END_TYPES   for s in steps)

    elements = []

    # Inject synthetic startEvent before first step if needed
    if not has_start:
        elements.append(BpmnElement(
            id=prefix + "ev_start",
            name="Início",
            type="startEvent",
            event_type="none",
            lane=steps[0].lane,
            actor=None,
        ))

    for step in steps:
        if step.task_type in _EVENT_TASK_TYPE_MAP:
            el_type_str, ev_type = _EVENT_TASK_TYPE_MAP[step.task_type]
            elements.append(BpmnElement(
                id=prefix + step.id,
                name=step.title,
                type=el_type_str,
                event_type=ev_type,
                lane=step.lane,
                actor=step.actor,
                documentation=step.description or "",
            ))
        elif step.is_decision:
            elements.append(BpmnElement(
                id=prefix + step.id,
                name=step.title,
                type="exclusiveGateway",
                lane=step.lane,
                actor=step.actor,
            ))
        else:
            el_type = _TASK_TYPE_MAP.get(step.task_type, "userTask")
            elements.append(BpmnElement(
                id=prefix + step.id,
                name=step.title,
                type=el_type,
                lane=step.lane,
                actor=step.actor,
                documentation=step.description or "",
            ))

    # Inject synthetic endEvent after last step if needed
    if not has_end:
        source_ids  = {e.source for e in pm.edges}
        terminal    = [s for s in steps if s.id not in source_ids]
        end_lane    = terminal[-1].lane if terminal else (steps[-1].lane if steps else None)
        elements.append(BpmnElement(
            id=prefix + "ev_end",
            name="Fim",
            type="endEvent",
            event_type="none",
            lane=end_lane,
            actor=None,
        ))

    return elements


def _build_pool_flows(pm: BPMNPoolData, prefix: str, elements: list,
                      SequenceFlow) -> list:
    """Build SequenceFlow list for one pool, including start/end connectors."""
    steps    = pm.steps
    if not steps:
        return []

    has_start = any(s.task_type in _START_TYPES for s in steps)
    has_end   = any(s.task_type in _END_TYPES   for s in steps)

    el_ids = {el.id for el in elements}

    flows = []

    # Connect synthetic ev_start → first non-start-event step
    if not has_start:
        first_real = next(
            (s for s in steps if s.task_type not in _START_TYPES), steps[0]
        )
        flows.append(SequenceFlow(
            id=prefix + "sf_start",
            source=prefix + "ev_start",
            target=prefix + first_real.id,
        ))

    for k, edge in enumerate(pm.edges):
        src = prefix + edge.source
        tgt = prefix + edge.target
        if src in el_ids and tgt in el_ids:
            flows.append(SequenceFlow(
                id=prefix + f"sf_{k + 1:03d}",
                source=src,
                target=tgt,
                name=edge.label or "",
                condition=edge.condition or "",
            ))

    # Connect ALL terminal (leaf) steps → synthetic ev_end
    if not has_end:
        source_ids = {e.source for e in pm.edges}
        terminal   = [s for s in steps if s.id not in source_ids
                      and s.task_type not in _END_TYPES]
        for _j, _term in enumerate(terminal):
            _fid = prefix + ("sf_end" if _j == 0 else f"sf_end_{_j}")
            flows.append(SequenceFlow(
                id=_fid,
                source=prefix + _term.id,
                target=prefix + "ev_end",
            ))

    return flows


def _build_pool_lanes(pm: BPMNPoolData, prefix: str, xml_pool_id: str,
                      elements: list, BpmnLane) -> list:
    """Build BpmnLane list for one pool, assigning elements to lanes."""
    if not pm.lanes:
        return []

    el_map: dict[str, object] = {el.id: el for el in elements}
    lanes  = []

    for lane_name in pm.lanes:
        lane_id    = f"lane_{xml_pool_id}_" + _ascii_id(lane_name)
        member_ids = [
            el.id for el in elements
            if (getattr(el, "lane", None) or "").lower() == lane_name.lower()
        ]
        lanes.append(BpmnLane(id=lane_id, name=lane_name,
                               element_ids=member_ids))

    return lanes
