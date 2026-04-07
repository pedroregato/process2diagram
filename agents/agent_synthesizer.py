# agents/agent_synthesizer.py
# ─────────────────────────────────────────────────────────────────────────────
# AgentSynthesizer — reads all hub artifacts and synthesizes an executive
# narrative (JSON) that is then turned into a self-contained HTML report.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from agents.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub, SynthesizerModel


class AgentSynthesizer(BaseAgent):
    name = "synthesizer"
    skill_path = "skills/SKILL_SYNTHESIZER.md"

    # ── Prompt builder ────────────────────────────────────────────────────────

    def build_prompt(
        self, hub: KnowledgeHub, output_language: str = "Auto-detect"
    ) -> tuple[str, str]:

        lang = self._language_instruction(output_language)
        system = self._skill.replace("{output_language}", lang)

        # ── BPMN summary ──────────────────────────────────────────────────────
        bpmn = hub.bpmn
        bpmn_lines: list[str] = []
        if bpmn.ready:
            bpmn_lines.append(f"Process name: {bpmn.name}")
            bpmn_lines.append(f"Lanes: {', '.join(bpmn.lanes) if bpmn.lanes else 'none'}")
            bpmn_lines.append(f"Total tasks: {len(bpmn.steps)}")
            decisions = [s for s in bpmn.steps if s.is_decision]
            bpmn_lines.append(f"Decision gateways: {len(decisions)}")
            # List up to 10 tasks with actor
            for s in bpmn.steps[:10]:
                actor_tag = f" [{s.actor}]" if s.actor else ""
                bpmn_lines.append(f"  - {s.title}{actor_tag}")
            if len(bpmn.steps) > 10:
                bpmn_lines.append(f"  ... and {len(bpmn.steps) - 10} more tasks")

        # ── Minutes summary ───────────────────────────────────────────────────
        minutes = hub.minutes
        min_lines: list[str] = []
        if minutes.ready:
            min_lines.append(f"Meeting title: {minutes.title}")
            min_lines.append(f"Date: {minutes.date}  Location: {minutes.location}")
            min_lines.append(f"Participants: {', '.join(minutes.participants[:15])}")
            if minutes.decisions:
                min_lines.append(f"Decisions ({len(minutes.decisions)}):")
                for d in minutes.decisions[:8]:
                    min_lines.append(f"  - {d}")
            if minutes.action_items:
                min_lines.append(f"Action items ({len(minutes.action_items)}):")
                for a in minutes.action_items[:8]:
                    dl = f" | deadline: {a.deadline}" if a.deadline else ""
                    min_lines.append(f"  - [{a.priority}] {a.task} → {a.responsible}{dl}")

        # ── Requirements summary ──────────────────────────────────────────────
        reqs = hub.requirements
        req_lines: list[str] = []
        if reqs.ready:
            from collections import Counter
            type_counts = Counter(r.type for r in reqs.requirements)
            req_lines.append(f"Total requirements: {len(reqs.requirements)}")
            req_lines.append(f"By type: {dict(type_counts)}")
            high_prio = [r for r in reqs.requirements if r.priority == "high"]
            req_lines.append(f"High priority: {len(high_prio)}")
            for r in reqs.requirements[:10]:
                req_lines.append(f"  - [{r.type}|{r.priority}] {r.title}")
            if len(reqs.requirements) > 10:
                req_lines.append(f"  ... and {len(reqs.requirements) - 10} more")

        # ── Quality summary ───────────────────────────────────────────────────
        quality = hub.transcript_quality
        qual_lines: list[str] = []
        if quality.ready:
            qual_lines.append(
                f"Transcript quality: grade={quality.grade}, score={quality.overall_score:.0f}/100"
            )
            qual_lines.append(f"Summary: {quality.overall_summary}")
            if quality.recommendation:
                qual_lines.append(f"Recommendation: {quality.recommendation}")

        # ── SBVR summary ──────────────────────────────────────────────────────
        sbvr = getattr(hub, "sbvr", None)
        sbvr_lines: list[str] = []
        if sbvr and sbvr.ready:
            sbvr_lines.append(f"Domain: {sbvr.domain}")
            sbvr_lines.append(f"Vocabulary terms ({len(sbvr.vocabulary)}):")
            for t in sbvr.vocabulary[:8]:
                sbvr_lines.append(f"  - [{t.category}] {t.term}: {t.definition}")
            if len(sbvr.vocabulary) > 8:
                sbvr_lines.append(f"  ... and {len(sbvr.vocabulary) - 8} more terms")
            sbvr_lines.append(f"Business rules ({len(sbvr.rules)}):")
            for r in sbvr.rules[:8]:
                src = f" (source: {r.source})" if r.source else ""
                sbvr_lines.append(f"  - [{r.rule_type}] {r.statement}{src}")
            if len(sbvr.rules) > 8:
                sbvr_lines.append(f"  ... and {len(sbvr.rules) - 8} more rules")

        # ── BMM summary ───────────────────────────────────────────────────────
        bmm = getattr(hub, "bmm", None)
        bmm_lines: list[str] = []
        if bmm and bmm.ready:
            if bmm.vision:
                bmm_lines.append(f"Vision: {bmm.vision}")
            if bmm.mission:
                bmm_lines.append(f"Mission: {bmm.mission}")
            if bmm.goals:
                bmm_lines.append(f"Goals ({len(bmm.goals)}):")
                for g in bmm.goals[:6]:
                    bmm_lines.append(f"  - [{g.goal_type}|{g.horizon}] {g.name}: {g.description}")
            if bmm.strategies:
                bmm_lines.append(f"Strategies ({len(bmm.strategies)}):")
                for s in bmm.strategies[:4]:
                    supports = ", ".join(s.supports[:3]) if s.supports else "—"
                    bmm_lines.append(f"  - {s.name} → supports: {supports}")
            if bmm.policies:
                bmm_lines.append(f"Policies ({len(bmm.policies)}):")
                for p in bmm.policies[:4]:
                    bmm_lines.append(f"  - [{p.category}] {p.statement}")

        # ── Assemble user prompt ──────────────────────────────────────────────
        sections: list[str] = []
        if bpmn_lines:
            sections.append("## BPMN Process\n" + "\n".join(bpmn_lines))
        if min_lines:
            sections.append("## Meeting Minutes\n" + "\n".join(min_lines))
        if req_lines:
            sections.append("## Requirements\n" + "\n".join(req_lines))
        if qual_lines:
            sections.append("## Transcript Quality\n" + "\n".join(qual_lines))
        if sbvr_lines:
            sections.append("## Business Vocabulary & Rules (SBVR)\n" + "\n".join(sbvr_lines))
        if bmm_lines:
            sections.append("## Business Motivation Model (BMM)\n" + "\n".join(bmm_lines))

        user = (
            "Synthesize the following meeting artifacts into an executive report.\n\n"
            + "\n\n".join(sections)
        )
        return system, user

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(
        self, hub: KnowledgeHub, output_language: str = "Auto-detect"
    ) -> KnowledgeHub:
        system, user = self.build_prompt(hub, output_language)
        data = self._call_with_retry(system, user, hub)

        hub.synthesizer = SynthesizerModel(
            executive_summary=data.get("executive_summary", ""),
            process_narrative=data.get("process_narrative", ""),
            key_insights=data.get("key_insights", []),
            recommendations=data.get("recommendations", []),
        )

        # Generate the HTML report
        from modules.executive_html import generate_executive_html
        hub.synthesizer.html = generate_executive_html(hub, hub.synthesizer)
        hub.synthesizer.ready = True

        hub.mark_agent_run(self.name)
        hub.bump()
        return hub
