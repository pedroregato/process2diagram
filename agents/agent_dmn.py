# agents/agent_dmn.py
# ─────────────────────────────────────────────────────────────────────────────
# AgentDMN — extrai decisoes formalizadas como tabelas DMN (OMG DMN 1.4).
#
# Reads:  hub.transcript_clean, hub.minutes.decisions (contexto)
# Writes: hub.dmn (DMNModel)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from agents.base_agent import BaseAgent
from core.knowledge_hub import (
    KnowledgeHub, DMNModel, DMNDecision, DMNInput, DMNOutput, DMNRule,
)
from core.output_schemas import DMNOutputSchema


class AgentDMN(BaseAgent):

    name                 = "dmn"
    skill_path           = "skills/skill_dmn.md"
    required_hub_fields  = ["transcript_clean"]
    output_schema        = DMNOutputSchema

    # ── Prompt ────────────────────────────────────────────────────────────────

    def build_prompt(
        self, hub: KnowledgeHub, output_language: str = "Auto-detect"
    ) -> tuple[str, str]:
        lang   = self._language_instruction(output_language)
        system = self._skill.replace("{output_language}", lang)

        if getattr(hub, "context_skill", "").strip():
            system += f"\n\n## Conhecimento do Contexto\n\n{hub.context_skill.strip()}"
        if getattr(hub, "context_files_text", "").strip():
            system += f"\n\n## Documentos de Referência do Contexto\n\n{hub.context_files_text.strip()}"

        # Provide extracted decisions as additional context
        decisions_ctx = ""
        if hub.minutes and hub.minutes.ready and hub.minutes.decisions:
            bullets = "\n".join(f"- {d}" for d in hub.minutes.decisions[:20])
            decisions_ctx = f"\n\n## Decisoes ja identificadas na ata\n{bullets}"

        user = (
            "Formalize as decisoes de negocio desta transcricao como tabelas DMN."
            f"{decisions_ctx}\n\n"
            f"## Transcricao\n\n{hub.transcript_clean}"
        )
        return system, user

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(
        self, hub: KnowledgeHub, output_language: str = "Auto-detect"
    ) -> KnowledgeHub:
        system, user = self.build_prompt(hub, output_language)
        data = self._call_with_retry(system, user, hub)
        hub.dmn = self._build_model(data)
        hub.mark_agent_run(self.name)
        hub.bump()
        return hub

    # ── Model builder ─────────────────────────────────────────────────────────

    def _build_model(self, data: dict) -> DMNModel:
        decisions = []
        for i, d in enumerate(data.get("decisions") or []):
            if not (d.get("name") or "").strip():
                continue

            inputs = [
                DMNInput(
                    label=inp.get("label", "").strip(),
                    expression=inp.get("expression", "").strip(),
                )
                for inp in (d.get("inputs") or [])
                if inp.get("label", "").strip()
            ]

            outputs = [
                DMNOutput(
                    label=out.get("label", "").strip(),
                    value=out.get("value", "").strip(),
                )
                for out in (d.get("outputs") or [])
                if out.get("label", "").strip()
            ]

            rules = [
                DMNRule(
                    inputs=r.get("inputs") or [],
                    output=r.get("output", ""),
                    annotation=r.get("annotation", ""),
                )
                for r in (d.get("rules") or [])
            ]

            try:
                confidence = float(d.get("confidence", 1.0))
            except (TypeError, ValueError):
                confidence = 1.0

            decisions.append(DMNDecision(
                id=d.get("id", f"D{i + 1}"),
                name=d["name"].strip(),
                question=d.get("question", "").strip(),
                rationale=d.get("rationale", "").strip(),
                decided_by=d.get("decided_by") or [],
                inputs=inputs,
                outputs=outputs,
                rules=rules,
                hit_policy=d.get("hit_policy", "U"),
                confidence=confidence,
            ))

        return DMNModel(decisions=decisions, ready=bool(decisions))
