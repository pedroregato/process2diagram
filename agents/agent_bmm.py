# agents/agent_bmm.py
# ─────────────────────────────────────────────────────────────────────────────
# BMM Agent — extrai o Modelo de Motivação de Negócio (OMG BMM).
#
# Reads:  hub.transcript_clean
# Writes: hub.bmm  (BMMModel — vision, mission, goals, strategies, policies)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from agents.base_agent import BaseAgent
from core.knowledge_hub import (
    KnowledgeHub, BMMModel, BMMGoal, BMMStrategy, BMMPolicy,
)


class AgentBMM(BaseAgent):

    name = "bmm"
    skill_path = "skills/skill_bmm.md"

    # ── Prompt ────────────────────────────────────────────────────────────────

    def build_prompt(
        self, hub: KnowledgeHub, output_language: str = "Auto-detect"
    ) -> tuple[str, str]:
        lang = self._language_instruction(output_language)
        system = self._skill.replace("{output_language}", lang)
        user = (
            "Extract the business motivation model from this transcript:\n\n"
            f"{hub.transcript_clean}"
        )
        return system, user

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(
        self, hub: KnowledgeHub, output_language: str = "Auto-detect"
    ) -> KnowledgeHub:
        system, user = self.build_prompt(hub, output_language)
        data = self._call_with_retry(system, user, hub)
        hub.bmm = self._build_model(data)
        hub.mark_agent_run(self.name)
        hub.bump()
        return hub

    # ── Model builder ─────────────────────────────────────────────────────────

    def _build_model(self, data: dict) -> BMMModel:
        goals = [
            BMMGoal(
                id=g.get("id", f"G{i + 1}"),
                name=g.get("name", "").strip(),
                description=g.get("description", "").strip(),
                goal_type=g.get("goal_type", "strategic"),
                horizon=g.get("horizon", "medium"),
            )
            for i, g in enumerate(data.get("goals", []))
            if g.get("name", "").strip()
        ]

        strategies = [
            BMMStrategy(
                id=s.get("id", f"S{i + 1}"),
                name=s.get("name", "").strip(),
                description=s.get("description", "").strip(),
                supports=s.get("supports", []),
            )
            for i, s in enumerate(data.get("strategies", []))
            if s.get("name", "").strip()
        ]

        policies = [
            BMMPolicy(
                id=p.get("id", f"P{i + 1}"),
                statement=p.get("statement", "").strip(),
                category=p.get("category", ""),
            )
            for i, p in enumerate(data.get("policies", []))
            if p.get("statement", "").strip()
        ]

        return BMMModel(
            vision=data.get("vision") or "",
            mission=data.get("mission") or "",
            goals=goals,
            strategies=strategies,
            policies=policies,
            ready=True,
        )
