# agents/agent_transcript_quality.py
# ─────────────────────────────────────────────────────────────────────────────
# Transcript Quality Agent — evaluates ASR transcript quality before the
# main pipeline runs.
#
# Reads:  hub.transcript_raw
# Writes: hub.transcript_quality  (TranscriptQualityModel)
#
# Criteria (weights sum to 1.0):
#   Inteligibilidade Léxica   20%
#   Atribuição de Falantes    20%
#   Coerência Semântica       20%
#   Completude do Conteúdo    15%
#   Vocabulário de Domínio    15%
#   Qualidade da Pontuação    10%
#
# Grade scale: A (90–100), B (75–89), C (60–74), D (45–59), E (0–44)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from agents.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub, TranscriptQualityModel, CriterionScore


# Canonical criterion names exactly as the LLM is instructed to return them,
# paired with their weights.  Order matches the skill file.
_CRITERIA_WEIGHTS: list[tuple[str, float]] = [
    ("Inteligibilidade Léxica",  0.20),
    ("Atribuição de Falantes",   0.20),
    ("Coerência Semântica",      0.20),
    ("Completude do Conteúdo",   0.15),
    ("Vocabulário de Domínio",   0.15),
    ("Qualidade da Pontuação",   0.10),
]


def _grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 45:
        return "D"
    return "E"


class AgentTranscriptQuality(BaseAgent):

    name = "transcript_quality"
    skill_path = "skills/skill_transcript_quality.md"

    # ── Prompt ────────────────────────────────────────────────────────────────

    def build_prompt(self, hub: KnowledgeHub, output_language: str = "Auto-detect") -> tuple[str, str]:
        lang = self._language_instruction(output_language)
        system = self._skill.replace(
            "{output_language}",
            f"Write all justifications and narrative text in {lang}.",
        )

        user = (
            "Evaluate the quality of the following meeting transcript "
            "using the six criteria defined in your instructions.\n\n"
            f"{hub.transcript_raw}"
        )
        return system, user

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self, hub: KnowledgeHub, output_language: str = "Auto-detect") -> KnowledgeHub:
        system, user = self.build_prompt(hub, output_language)
        data = self._call_with_retry(system, user, hub)

        hub.transcript_quality = self._build_model(data)
        hub.transcript_quality.ready = True
        hub.mark_agent_run(self.name)
        hub.bump()
        return hub

    # ── Model building ────────────────────────────────────────────────────────

    @classmethod
    def _build_model(cls, data: dict) -> TranscriptQualityModel:
        # Build a lookup from criterion name → score + justification
        llm_criteria: dict[str, dict] = {
            c["criterion"]: c
            for c in data.get("criteria", [])
            if isinstance(c, dict) and "criterion" in c
        }

        criteria_scores: list[CriterionScore] = []
        weighted_sum = 0.0

        for criterion_name, weight in _CRITERIA_WEIGHTS:
            entry = llm_criteria.get(criterion_name, {})
            raw_score = entry.get("score", 0)
            # Clamp to [0, 100] and cast to int
            score = max(0, min(100, int(raw_score)))
            justification = entry.get("justification", "")

            criteria_scores.append(CriterionScore(
                criterion=criterion_name,
                score=score,
                weight=weight,
                justification=justification,
            ))
            weighted_sum += score * weight

        overall = round(weighted_sum, 1)

        return TranscriptQualityModel(
            criteria=criteria_scores,
            overall_score=overall,
            grade=_grade(overall),
            overall_summary=data.get("overall_summary", ""),
            recommendation=data.get("recommendation", ""),
        )
