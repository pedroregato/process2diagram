# agents/agent_requirements.py
# ─────────────────────────────────────────────────────────────────────────────
# Requirements Agent — extrai requisitos funcionais, regras de negócio,
# campos de tela, validações e restrições de qualidade de transcrições.
#
# Reads:  hub.transcript_clean, hub.nlp (actors)
# Writes: hub.requirements  (RequirementsModel — requirements list, markdown)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from agents.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub, RequirementsModel, RequirementItem


# Emoji badge per requirement type — used in Markdown output
_TYPE_BADGE = {
    "ui_field":       "🖥️  Campo de tela",
    "validation":     "✅  Validação",
    "business_rule":  "📋  Regra de negócio",
    "functional":     "⚙️  Funcional",
    "non_functional": "📊  Não-funcional",
}

_PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2, "unspecified": 3}


class AgentRequirements(BaseAgent):

    name = "requirements"
    skill_path = "skills/SKILL_REQUIREMENTS.md"

    # ── Prompt ────────────────────────────────────────────────────────────────

    def build_prompt(self, hub: KnowledgeHub, output_language: str = "Auto-detect") -> tuple[str, str]:
        lang = self._language_instruction(output_language)
        system = self._skill.replace("{output_language}", lang)

        actor_hint = ""
        if hub.nlp.actors:
            actor_hint = f"\nActors identified by NLP pre-processing: {', '.join(hub.nlp.actors)}"

        user = (
            f"Extract all requirements from this transcript:{actor_hint}\n\n"
            f"{hub.transcript_clean}"
        )
        return system, user

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(self, hub: KnowledgeHub, output_language: str = "Auto-detect") -> KnowledgeHub:
        system, user = self.build_prompt(hub, output_language)
        data = self._call_with_retry(system, user, hub)

        hub.requirements = self._build_model(data)
        hub.requirements.markdown = self._generate_markdown(hub.requirements)
        hub.requirements.ready = True
        hub.mark_agent_run(self.name)
        hub.bump()
        return hub

    # ── Model building ────────────────────────────────────────────────────────

    @staticmethod
    def _build_model(data: dict) -> RequirementsModel:
        items = [
            RequirementItem(
                id=r["id"],
                title=r.get("title", "Requisito"),
                description=r.get("description", ""),
                type=r.get("type", "functional"),
                actor=r.get("actor") or None,
                priority=r.get("priority", "unspecified"),
                process_step=r.get("process_step") or None,
                source_quote=r.get("source_quote", ""),
                speaker=r.get("speaker") or None,
            )
            for r in data.get("requirements", [])
        ]
        return RequirementsModel(
            name=data.get("name", "Processo"),
            requirements=items,
        )

    # ── Markdown generator ────────────────────────────────────────────────────

    @staticmethod
    def _generate_markdown(model: RequirementsModel) -> str:
        lines: list[str] = []

        lines.append(f"# Especificação de Requisitos — {model.name}")
        lines.append("")
        lines.append(f"**Total de requisitos:** {len(model.requirements)}")
        lines.append("")

        # Summary table by type
        from collections import Counter
        type_counts = Counter(r.type for r in model.requirements)
        lines.append("## Resumo por Tipo")
        lines.append("")
        lines.append("| Tipo | Quantidade |")
        lines.append("|------|-----------|")
        for t, badge in _TYPE_BADGE.items():
            if type_counts[t]:
                lines.append(f"| {badge} | {type_counts[t]} |")
        lines.append("")

        # Group by type, sorted by priority within each group
        type_order = list(_TYPE_BADGE.keys())
        grouped: dict[str, list[RequirementItem]] = {t: [] for t in type_order}
        for r in model.requirements:
            grouped.setdefault(r.type, []).append(r)

        for t in type_order:
            items = grouped.get(t, [])
            if not items:
                continue
            items_sorted = sorted(items, key=lambda x: _PRIORITY_ORDER.get(x.priority, 3))
            lines.append(f"## {_TYPE_BADGE[t]}")
            lines.append("")
            for r in items_sorted:
                priority_label = {
                    "high": "🔴 Alta",
                    "medium": "🟡 Média",
                    "low": "🟢 Baixa",
                    "unspecified": "⚪ N/D",
                }.get(r.priority, "⚪ N/D")

                lines.append(f"### {r.id} — {r.title}")
                lines.append("")
                lines.append(f"**Prioridade:** {priority_label}")
                if r.actor:
                    lines.append(f"  **Ator:** {r.actor}")
                if r.process_step:
                    lines.append(f"  **Etapa do processo:** {r.process_step}")
                lines.append("")
                lines.append(r.description)
                if r.source_quote:
                    lines.append("")
                    speaker_tag = f"**[{r.speaker}]** " if r.speaker else ""
                    lines.append(f"> {speaker_tag}*\"{r.source_quote}\"*")
                lines.append("")

        return "\n".join(lines)
