# agents/agent_query_summarizer.py
# ─────────────────────────────────────────────────────────────────────────────
# AgentQuerySummarizer — Fase F: automatic post-pipeline multi-perspective summary.
#
# Reads:  hub.minutes, hub.requirements, hub.bpmn, hub.sbvr, hub.bmm, hub.dmn
# Writes: hub.query_summary  (QuerySummaryModel — 4 perspectives)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from agents.base_agent import BaseAgent
from core.knowledge_hub import (
    KnowledgeHub, QuerySummaryModel, PerspectiveSummary,
)


class AgentQuerySummarizer(BaseAgent):

    name = "query_summarizer"
    skill_path = "skills/skill_query_summarizer.md"

    # ── Prompt ────────────────────────────────────────────────────────────────

    def build_prompt(
        self, hub: KnowledgeHub, output_language: str = "Auto-detect"
    ) -> tuple[str, str]:
        lang = self._language_instruction(output_language)
        system = self._skill.replace("{output_language}", lang)

        # Build a structured digest of all available artefacts
        sections: list[str] = []

        # Meeting minutes
        if hub.minutes.ready:
            m = hub.minutes
            sections.append(f"## Meeting Title\n{m.title}")
            if m.participants:
                sections.append(f"## Participants\n" + "\n".join(f"- {p}" for p in m.participants))
            if m.decisions:
                sections.append("## Decisions\n" + "\n".join(f"- {d}" for d in m.decisions))
            if m.action_items:
                lines = [f"- [{a.responsible}] {a.task}" + (f" (deadline: {a.deadline})" if a.deadline else "")
                         for a in m.action_items]
                sections.append("## Action Items\n" + "\n".join(lines))
            if m.assumptions:
                sections.append("## Assumptions\n" + "\n".join(f"- {a}" for a in m.assumptions))
            if m.open_questions:
                sections.append("## Open Questions\n" + "\n".join(f"- {q}" for q in m.open_questions))
            if m.risks_identified:
                sections.append("## Risks Identified\n" + "\n".join(f"- {r}" for r in m.risks_identified))
            if m.dependencies:
                sections.append("## Dependencies\n" + "\n".join(f"- {d}" for d in m.dependencies))
            if getattr(m, "summary", []):
                parts = "\n".join(f"- [{s.get('topic','')}] {s.get('content','')}" for s in m.summary)
                sections.append(f"## Discussion Summary\n{parts}")

        # Requirements
        if hub.requirements.ready and hub.requirements.requirements:
            lines = []
            for r in hub.requirements.requirements[:30]:   # cap at 30 to control token usage
                lines.append(f"- [{r.type}] [{r.priority}] {r.title}: {r.description[:120]}")
            sections.append("## Requirements\n" + "\n".join(lines))

        # BPMN process
        if hub.bpmn.ready:
            b = hub.bpmn
            sections.append(f"## Process Name\n{b.name}")
            if b.lanes:
                sections.append(f"## Swim Lanes\n" + ", ".join(b.lanes))
            if b.steps:
                step_lines = [f"- [{s.task_type}] {s.title}" for s in b.steps[:20]]
                sections.append("## Process Steps\n" + "\n".join(step_lines))

        # SBVR
        if hub.sbvr.ready:
            if hub.sbvr.rules:
                rule_lines = [f"- [{r.rule_type}] {r.statement[:100]}" for r in hub.sbvr.rules[:15]]
                sections.append("## Business Rules (SBVR)\n" + "\n".join(rule_lines))

        # BMM
        if hub.bmm.ready:
            bm = hub.bmm
            if bm.vision:
                sections.append(f"## Vision\n{bm.vision}")
            if bm.mission:
                sections.append(f"## Mission\n{bm.mission}")
            if bm.goals:
                goal_lines = [f"- [{g.goal_type}] {g.name}" for g in bm.goals[:8]]
                sections.append("## Goals\n" + "\n".join(goal_lines))
            if bm.policies:
                pol_lines = [f"- {p.statement[:100]}" for p in bm.policies[:8]]
                sections.append("## Policies\n" + "\n".join(pol_lines))

        # DMN decisions
        if getattr(hub, "dmn", None) and hub.dmn.ready and hub.dmn.decisions:
            dec_lines = [f"- {d.name}: {d.question}" for d in hub.dmn.decisions[:10]]
            sections.append("## Formal Decisions (DMN)\n" + "\n".join(dec_lines))

        knowledge_base = "\n\n".join(sections) if sections else "(No structured artefacts available — use transcript fallback)"

        user = (
            "Generate a 4-perspective meeting summary from the following structured knowledge base.\n\n"
            f"{knowledge_base}"
        )
        return system, user

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(
        self, hub: KnowledgeHub, output_language: str = "Auto-detect"
    ) -> KnowledgeHub:
        system, user = self.build_prompt(hub, output_language)
        data = self._call_with_retry(system, user, hub)
        hub.query_summary = self._build_model(data)
        hub.mark_agent_run(self.name)
        hub.bump()
        return hub

    # ── Model builder ─────────────────────────────────────────────────────────

    def _build_model(self, data: dict) -> QuerySummaryModel:
        perspectives = []
        for p in data.get("perspectives", []):
            key = p.get("perspective", "").strip()
            if not key:
                continue
            perspectives.append(PerspectiveSummary(
                perspective=key,
                label=p.get("label", key).strip(),
                headline=p.get("headline", "").strip(),
                highlights=[h.strip() for h in p.get("highlights", []) if str(h).strip()],
                open_items=[o.strip() for o in p.get("open_items", []) if str(o).strip()],
                recommended_actions=[a.strip() for a in p.get("recommended_actions", []) if str(a).strip()],
            ))
        return QuerySummaryModel(perspectives=perspectives, ready=bool(perspectives))
