# agents/agent_minutes.py
# ─────────────────────────────────────────────────────────────────────────────
# Minutes Agent — produces structured meeting minutes from transcript.
#
# Reads:  hub.transcript_clean, hub.nlp.actors (optional enrichment)
# Writes: hub.minutes  (MinutesModel)
# Exports (via to_markdown): Markdown string ready for DOCX/PDF rendering
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from datetime import datetime

from agents.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub, MinutesModel, ActionItem


class AgentMinutes(BaseAgent):

    name = "minutes"
    skill_path = "skills/skill_minutes.md"

    # ── Prompt ────────────────────────────────────────────────────────────────

    def build_prompt(self, hub: KnowledgeHub, output_language: str = "Auto-detect") -> tuple[str, str]:
        lang = self._language_instruction(output_language)
        system = self._skill.replace("{output_language}", lang)

        actor_hint = ""
        if hub.nlp.actors:
            actor_hint = f"\nParticipants identified by NLP: {', '.join(hub.nlp.actors)}"

        # Pass full transcript — truncation to 12k was causing severe quality loss
        # (only ~5% of a 2h meeting visible). DeepSeek context window supports ~80k chars.
        transcript = hub.transcript_clean

        user = (
            f"Produce the structured meeting minutes from this transcript:{actor_hint}\n\n"
            f"{transcript}"
        )
        return system, user

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self, hub: KnowledgeHub, output_language: str = "Auto-detect") -> KnowledgeHub:
        system, user = self.build_prompt(hub, output_language)
        data = self._call_with_retry(system, user, hub)

        hub.minutes = self._build_model(data)
        hub.minutes.ready = True
        hub.mark_agent_run(self.name)
        hub.bump()
        return hub

    # ── Model building ────────────────────────────────────────────────────────

    @staticmethod
    def _build_model(data: dict) -> MinutesModel:
        action_items = [
            ActionItem(
                task=ai.get("task", ""),
                responsible=ai.get("responsible", "A definir"),
                deadline=ai.get("deadline") or None,
                priority=ai.get("priority", "normal"),
                raised_by=ai.get("raised_by") or None,
            )
            for ai in data.get("action_items", [])
        ]
        return MinutesModel(
            title=data.get("title", "Reunião"),
            date=data.get("date") or "",
            location=data.get("location") or "",
            participants=data.get("participants", []),
            agenda=data.get("agenda", []),
            summary=data.get("summary", []),
            decisions=data.get("decisions", []),
            action_items=action_items,
            next_meeting=data.get("next_meeting") or None,
        )

    # ── Markdown export ───────────────────────────────────────────────────────

    @staticmethod
    def to_markdown(minutes: MinutesModel) -> str:
        """Render MinutesModel as a structured Markdown document."""
        lines: list[str] = []
        now = datetime.now().strftime("%d/%m/%Y")

        # Header
        lines += [
            f"# {minutes.title}",
            "",
            f"**Data:** {minutes.date or 'Não informada'}  ",
            f"**Local/Modalidade:** {minutes.location or 'Não informada'}  ",
            f"**Gerado em:** {now}",
            "",
        ]

        # Participants
        if minutes.participants:
            lines += ["## Participantes", ""]
            for p in minutes.participants:
                lines.append(f"- {p}")
            lines.append("")

        # Agenda
        if minutes.agenda:
            lines += ["## Pauta", ""]
            for i, item in enumerate(minutes.agenda, 1):
                lines.append(f"{i}. {item}")
            lines.append("")

        # Summary
        if minutes.summary:
            lines += ["## Resumo da Reunião", ""]
            for block in minutes.summary:
                topic = block.get("topic", "")
                content = block.get("content", "")
                if topic:
                    lines.append(f"### {topic}")
                lines.append(content)
                lines.append("")

        # Decisions
        if minutes.decisions:
            lines += ["## Decisões Tomadas", ""]
            for d in minutes.decisions:
                lines.append(f"- {d}")
            lines.append("")

        # Action Items
        if minutes.action_items:
            lines += ["## Encaminhamentos / Action Items", ""]
            lines += [
                "| # | Tarefa | Levantado por | Responsável | Prazo | Prioridade |",
                "|---|--------|---------------|-------------|-------|------------|",
            ]
            priority_labels = {"high": "🔴 Alta", "normal": "🟡 Normal", "low": "🟢 Baixa"}
            for i, ai in enumerate(minutes.action_items, 1):
                prio = priority_labels.get(ai.priority, ai.priority)
                deadline = ai.deadline or "—"
                raised = f"**{ai.raised_by}**" if ai.raised_by else "—"
                lines.append(f"| {i} | {ai.task} | {raised} | {ai.responsible} | {deadline} | {prio} |")
            lines.append("")

        # Next meeting
        if minutes.next_meeting:
            lines += ["## Próxima Reunião", "", f"**{minutes.next_meeting}**", ""]

        lines += [
            "---",
            f"*Ata gerada automaticamente pelo Process2Diagram — {now}*",
        ]

        return "\n".join(lines)
