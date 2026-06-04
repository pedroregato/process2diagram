# agents/agent_communication_noise.py
# ─────────────────────────────────────────────────────────────────────────────
# AgentCommunicationNoise — detects ambiguities and communication gaps in
# meeting transcripts.
#
# Reads:  hub.transcript_clean, hub.nlp.actors, hub.minutes (participants,
#         decisions, open_questions for context)
# Writes: hub.communication_noise  (CommunicationNoiseModel)
#
# Optional — default OFF. Non-fatal: pipeline continues on failure.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from agents.base_agent import BaseAgent
from core.knowledge_hub import (
    KnowledgeHub,
    CommunicationNoiseModel,
    AmbiguityItem,
    CommunicationGap,
)


class AgentCommunicationNoise(BaseAgent):

    name = "communication_noise"
    skill_path = "skills/skill_communication_noise.md"

    # ── Prompt ────────────────────────────────────────────────────────────────

    def build_prompt(
        self, hub: KnowledgeHub, output_language: str = "Auto-detect"
    ) -> tuple[str, str]:
        lang = self._language_instruction(output_language)
        system = self._skill.replace("{output_language}", lang)

        if getattr(hub, "context_skill", "").strip():
            system += f"\n\n## Conhecimento do Contexto\n\n{hub.context_skill.strip()}"

        # Build context block from prior agents
        context_lines: list[str] = []

        actors = getattr(hub.nlp, "actors", [])
        if actors:
            context_lines.append(f"Participants identified: {', '.join(actors)}")

        if hub.minutes.ready:
            if hub.minutes.participants:
                context_lines.append(
                    f"Participants from minutes: {', '.join(hub.minutes.participants)}"
                )
            if hub.minutes.decisions:
                decisions_txt = "; ".join(hub.minutes.decisions[:10])
                context_lines.append(f"Decisions recorded: {decisions_txt}")
            if hub.minutes.open_questions:
                oq_txt = "; ".join(hub.minutes.open_questions[:5])
                context_lines.append(
                    f"Open questions already flagged in minutes: {oq_txt}"
                )

        context_block = ""
        if context_lines:
            context_block = "\n\n## Meeting Context\n\n" + "\n".join(
                f"- {line}" for line in context_lines
            )

        user = (
            f"Analyse the transcript below for communication noise "
            f"(ambiguities and gaps).{context_block}\n\n"
            f"## Transcript\n\n{hub.transcript_clean}"
        )
        return system, user

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(
        self, hub: KnowledgeHub, output_language: str = "Auto-detect"
    ) -> KnowledgeHub:
        system, user = self.build_prompt(hub, output_language)
        data = self._call_with_retry(system, user, hub)

        hub.communication_noise = self._build_model(data)
        hub.communication_noise.ready = True
        hub.mark_agent_run(self.name)
        hub.bump()
        return hub

    # ── Model building ────────────────────────────────────────────────────────

    @staticmethod
    def _build_model(data: dict) -> CommunicationNoiseModel:
        ambiguities = [
            AmbiguityItem(
                text=a.get("text", ""),
                ambiguity_type=a.get("ambiguity_type", "lexical"),
                speaker=a.get("speaker", ""),
                possible_interpretations=a.get("possible_interpretations", []),
                suggestion=a.get("suggestion", ""),
                confidence=float(a.get("confidence", 0.8)),
            )
            for a in data.get("ambiguities", [])
            if a.get("text")
        ]

        gaps = [
            CommunicationGap(
                gap_type=g.get("gap_type", "missing_info"),
                description=g.get("description", ""),
                raised_by=g.get("raised_by", "–"),
                topic=g.get("topic", ""),
                evidence_quote=g.get("evidence_quote", ""),
                impact=g.get("impact", ""),
                recommendation=g.get("recommendation", ""),
            )
            for g in data.get("gaps", [])
            if g.get("description")
        ]

        raw_score = data.get("noise_score", 0.0)
        try:
            noise_score = float(raw_score)
        except (TypeError, ValueError):
            noise_score = 0.0
        noise_score = max(0.0, min(10.0, noise_score))

        return CommunicationNoiseModel(
            ambiguities=ambiguities,
            gaps=gaps,
            noise_score=noise_score,
            summary=data.get("summary", ""),
        )
