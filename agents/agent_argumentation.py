# agents/agent_argumentation.py
# ─────────────────────────────────────────────────────────────────────────────
# AgentArgumentation — extrai o mapa argumentativo IBIS da transcrição.
#
# Reads:  hub.transcript_clean
# Writes: hub.argumentation (ArgumentationMap)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from agents.base_agent import BaseAgent
from core.knowledge_hub import (
    KnowledgeHub, ArgumentationMap,
    IBISQuestion, IBISAlternative, IBISResolution,
)
from core.output_schemas import ArgumentationOutputSchema


class AgentArgumentation(BaseAgent):

    name                 = "argumentation"
    skill_path           = "skills/skill_argumentation.md"
    required_hub_fields  = ["transcript_clean"]
    output_schema        = ArgumentationOutputSchema

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

        user = (
            "Extraia o mapa argumentativo IBIS desta transcricao de reuniao.\n\n"
            f"## Transcricao\n\n{hub.transcript_clean}"
        )
        return system, user

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(
        self, hub: KnowledgeHub, output_language: str = "Auto-detect"
    ) -> KnowledgeHub:
        system, user = self.build_prompt(hub, output_language)
        data = self._call_with_retry(system, user, hub)
        hub.argumentation = self._build_model(data)
        hub.mark_agent_run(self.name)
        hub.bump()
        return hub

    # ── Model builder ─────────────────────────────────────────────────────────

    def _build_model(self, data: dict) -> ArgumentationMap:
        questions = []
        for i, q in enumerate(data.get("questions") or []):
            if not (q.get("statement") or "").strip():
                continue

            alternatives = []
            for a in (q.get("alternatives") or []):
                if not (a.get("description") or "").strip():
                    continue
                alternatives.append(IBISAlternative(
                    id=a.get("id", f"A{i}"),
                    description=a["description"].strip(),
                    proposed_by=a.get("proposed_by", ""),
                    pros=a.get("pros") or [],
                    cons=a.get("cons") or [],
                    supported_by=a.get("supported_by") or [],
                    opposed_by=a.get("opposed_by") or [],
                    was_chosen=bool(a.get("was_chosen", False)),
                ))

            res_raw = q.get("resolution") or {}
            resolution = IBISResolution(
                type=res_raw.get("type", "unresolved"),
                chosen_alternative_id=res_raw.get("chosen_alternative_id", ""),
                rationale=res_raw.get("rationale", ""),
                with_caveats=res_raw.get("with_caveats") or [],
            )

            questions.append(IBISQuestion(
                id=q.get("id", f"Q{i + 1}"),
                statement=q["statement"].strip(),
                raised_by=q.get("raised_by", ""),
                alternatives=alternatives,
                resolution=resolution,
            ))

        return ArgumentationMap(questions=questions, ready=bool(questions))
