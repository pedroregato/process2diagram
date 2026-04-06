# agents/agent_sbvr.py
# ─────────────────────────────────────────────────────────────────────────────
# SBVR Agent — extrai vocabulário de negócio e regras de negócio (OMG SBVR).
#
# Reads:  hub.transcript_clean
# Writes: hub.sbvr  (SBVRModel — domain, vocabulary, rules)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from agents.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub, SBVRModel, BusinessTerm, BusinessRule


class AgentSBVR(BaseAgent):

    name = "sbvr"
    skill_path = "skills/skill_sbvr.md"

    # ── Prompt ────────────────────────────────────────────────────────────────

    def build_prompt(
        self, hub: KnowledgeHub, output_language: str = "Auto-detect"
    ) -> tuple[str, str]:
        lang = self._language_instruction(output_language)
        system = self._skill.replace("{output_language}", lang)
        user = (
            "Extract the business vocabulary and rules from this transcript:\n\n"
            f"{hub.transcript_clean}"
        )
        return system, user

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(
        self, hub: KnowledgeHub, output_language: str = "Auto-detect"
    ) -> KnowledgeHub:
        system, user = self.build_prompt(hub, output_language)
        data = self._call_with_retry(system, user, hub)
        hub.sbvr = self._build_model(data)
        hub.mark_agent_run(self.name)
        hub.bump()
        return hub

    # ── Model builder ─────────────────────────────────────────────────────────

    def _build_model(self, data: dict) -> SBVRModel:
        vocabulary = [
            BusinessTerm(
                term=t.get("term", "").strip(),
                definition=t.get("definition", "").strip(),
                category=t.get("category", "concept"),
            )
            for t in data.get("vocabulary", [])
            if t.get("term", "").strip()
        ]

        rules = [
            BusinessRule(
                id=r.get("id", f"BR{i + 1:03d}"),
                statement=r.get("statement", "").strip(),
                rule_type=r.get("rule_type", "constraint"),
                source=r.get("source") or "",
            )
            for i, r in enumerate(data.get("rules", []))
            if r.get("statement", "").strip()
        ]

        return SBVRModel(
            domain=data.get("domain", "").strip(),
            vocabulary=vocabulary,
            rules=rules,
            ready=True,
        )
