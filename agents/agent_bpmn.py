# agents/agent_bpmn.py
# ─────────────────────────────────────────────────────────────────────────────
# BPMN Agent — expert em BPMN 2.0 (OMG / ISO-IEC 19510).
#
# Reads:  hub.transcript_clean, hub.nlp (actors, segments)
# Writes: hub.bpmn  (BPMNModel — steps, edges, lanes, mermaid, drawio_xml,
#                                bpmn_xml via bpmn_generator)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from agents.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub, BPMNModel, BPMNStep, BPMNEdge


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
        hub.bpmn.mermaid    = self._generate_mermaid(hub.bpmn)
        hub.bpmn.drawio_xml = self._generate_drawio(hub.bpmn)
        hub.bpmn.bpmn_xml   = self._generate_bpmn_xml(hub.bpmn)
        hub.bpmn.ready = True
        hub.mark_agent_run(self.name)
        hub.bump()
        return hub

    # ── Model building ────────────────────────────────────────────────────────

    @staticmethod
    def _build_model(data: dict) -> BPMNModel:
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

    # ── BPMN XML (OMG 2.0) via bpmn_generator ────────────────────────────────

    @staticmethod
    def _generate_bpmn_xml(model: BPMNModel) -> str:
        """
        Bridge BPMNModel → BpmnProcess (modules/schema.py) → generate_bpmn_xml().
        Falls back gracefully to empty string if modules/schema or bpmn_generator
        are not available (e.g. during unit tests without full project).
        """
        try:
            from modules.schema import (
                BpmnProcess, BpmnElement, BpmnPool, BpmnLane, SequenceFlow
            )
            from modules.bpmn_generator import generate_bpmn_xml

            # ── Map task_type → BPMN element type ────────────────────────────
            _TASK_TYPE_MAP = {
                "userTask":         "userTask",
                "serviceTask":      "serviceTask",
                "scriptTask":       "scriptTask",
                "manualTask":       "manualTask",
                "businessRuleTask": "businessRuleTask",
                "parallelGateway":  "parallelGateway",
                "exclusiveGateway": "exclusiveGateway",
            }

            elements = []
            for i, step in enumerate(model.steps):
                if step.is_decision:
                    el_type = "exclusiveGateway"
                else:
                    el_type = _TASK_TYPE_MAP.get(step.task_type, "userTask")

                # Add startEvent before first step and endEvent after last
                if i == 0:
                    elements.append(BpmnElement(
                        id="ev_start",
                        name="Início",
                        type="startEvent",
                        actor=None,
                        lane=step.lane,
                    ))

                elements.append(BpmnElement(
                    id=step.id,
                    name=step.title,
                    type=el_type,
                    actor=step.actor,
                    lane=step.lane,
                    documentation=step.description or "",
                ))

                if i == len(model.steps) - 1:
                    elements.append(BpmnElement(
                        id="ev_end",
                        name="Fim",
                        type="endEvent",
                        actor=None,
                        lane=step.lane,
                    ))

            # ── Sequence flows ────────────────────────────────────────────────
            flows = []

            # Connect startEvent to first step
            if model.steps:
                flows.append(SequenceFlow(
                    id="sf_start",
                    source="ev_start",
                    target=model.steps[0].id,
                ))

            for i, edge in enumerate(model.edges):
                flows.append(SequenceFlow(
                    id=f"sf_{i+1:03d}",
                    source=edge.source,
                    target=edge.target,
                    name=edge.label or "",
                    condition=edge.condition or "",
                ))

            # Connect last step to endEvent
            if model.steps:
                flows.append(SequenceFlow(
                    id="sf_end",
                    source=model.steps[-1].id,
                    target="ev_end",
                ))

            # ── Pools / Lanes ─────────────────────────────────────────────────
            pools = []
            if model.lanes:
                lane_objects = []
                for lane_name in model.lanes:
                    lane_id = "lane_" + lane_name.lower().replace(" ", "_")
                    member_ids = [
                        s.id for s in model.steps
                        if s.lane and s.lane.lower() == lane_name.lower()
                    ]
                    lane_objects.append(BpmnLane(
                        id=lane_id,
                        name=lane_name,
                        element_ids=member_ids,
                    ))
                pools.append(BpmnPool(
                    id="pool_1",
                    name=model.name,
                    lanes=lane_objects,
                ))

            bpmn_process = BpmnProcess(
                name=model.name,
                elements=elements,
                flows=flows,
                pools=pools,
            )

            return generate_bpmn_xml(bpmn_process)

        except Exception:
            # bpmn_generator not available or bridge error — degrade gracefully
            return ""

    # ── Mermaid generator ─────────────────────────────────────────────────────

    @staticmethod
    def _generate_mermaid(model: BPMNModel) -> str:
        lines = ["flowchart TD"]

        for step in model.steps:
            label = step.title.replace('"', "'")
            if step.is_decision:
                lines.append(f'    {step.id}{{"{label}"}}')
            else:
                lines.append(f'    {step.id}["{label}"]')

        for edge in model.edges:
            arrow = f"-- {edge.label} -->" if edge.label else "-->"
            lines.append(f"    {edge.source} {arrow} {edge.target}")

        decision_ids = [s.id for s in model.steps if s.is_decision]
        for did in decision_ids:
            lines.append(f"    style {did} fill:#fff3cd,stroke:#f59e0b")

        return "\n".join(lines)

    # ── Draw.io generator ─────────────────────────────────────────────────────

    @staticmethod
    def _generate_drawio(model: BPMNModel) -> str:
        cells = []
        x, y = 160, 80
        step_positions: dict[str, tuple[int, int]] = {}
        W, H, GAP = 160, 60, 40

        for i, step in enumerate(model.steps):
            cx = x + (i % 4) * (W + GAP)
            cy = y + (i // 4) * (H + GAP * 3)
            step_positions[step.id] = (cx, cy)

            if step.is_decision:
                style = "rhombus;whiteSpace=wrap;html=1;fillColor=#fff3cd;strokeColor=#f59e0b;"
                w, h = 120, 80
            else:
                style = "rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;"
                w, h = W, H

            label = step.title.replace("<", "&lt;").replace(">", "&gt;")
            cells.append(
                f'<mxCell id="{step.id}" value="{label}" style="{style}" '
                f'vertex="1" parent="1">'
                f'<mxGeometry x="{cx}" y="{cy}" width="{w}" height="{h}" as="geometry"/>'
                f"</mxCell>"
            )

        for i, edge in enumerate(model.edges):
            label = edge.label or ""
            cells.append(
                f'<mxCell id="e{i}" value="{label}" edge="1" '
                f'source="{edge.source}" target="{edge.target}" parent="1">'
                f'<mxGeometry relative="1" as="geometry"/>'
                f"</mxCell>"
            )

        inner = "\n  ".join(cells)
        return (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<mxGraphModel><root>\n'
            '  <mxCell id="0"/><mxCell id="1" parent="0"/>\n'
            f"  {inner}\n"
            "</root></mxGraphModel>"
        )