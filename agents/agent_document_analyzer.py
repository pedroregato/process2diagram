# agents/agent_document_analyzer.py
# ─────────────────────────────────────────────────────────────────────────────
# DocumentAnalyzerAgent — cross-references a document with meeting artifacts.
#
# This agent is NOT part of the automatic pipeline.
# It is called on-demand from pages/DocumentManager.py and optionally
# from assistant tools.
#
# run() returns a plain dict (the cross-reference report), not a modified hub.
# The caller is responsible for displaying / storing the result.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from typing import Optional

from agents.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub


class DocumentAnalyzerAgent(BaseAgent):
    name = "document_analyzer"
    skill_path = "skills/skill_document_analyzer.md"

    # build_prompt and run have different signatures from the pipeline convention
    # because this agent works standalone (returns dict, not modified hub).

    def build_prompt(self, hub: KnowledgeHub) -> tuple[str, str]:  # type: ignore[override]
        """Not used directly — use build_prompt_for_doc() instead."""
        return self._skill, ""

    def build_prompt_for_doc(
        self,
        document_title: str,
        document_content: str,
        hub: KnowledgeHub,
        output_language: str = "Auto-detect",
    ) -> tuple[str, str]:
        """Build system + user prompt for cross-reference analysis."""
        system = self._skill

        # ── Meeting minutes ────────────────────────────────────────────────
        minutes_text = "(não disponível)"
        if hub.minutes and hub.minutes.summary:
            parts = [f"**Resumo:** {hub.minutes.summary}"]
            if hub.minutes.decisions:
                parts.append("**Decisões:**\n" + "\n".join(
                    f"- {d}" for d in hub.minutes.decisions[:15]
                ))
            if hub.minutes.action_items:
                parts.append("**Itens de Ação:**\n" + "\n".join(
                    f"- {a.description} ({a.responsible})"
                    for a in hub.minutes.action_items[:15]
                ))
            minutes_text = "\n".join(parts)

        # ── Requirements ───────────────────────────────────────────────────
        reqs_text = "(não disponível)"
        if hub.requirements and hub.requirements.requirements:
            reqs_text = "\n".join(
                f"- [{r.req_id}] ({r.req_type}) {r.title}: {r.description[:150]}"
                for r in hub.requirements.requirements[:25]
            )

        # ── BPMN steps ─────────────────────────────────────────────────────
        bpmn_text = "(não disponível)"
        if hub.bpmn and hub.bpmn.steps:
            bpmn_text = "\n".join(
                f"- [{s.step_id}] {s.name} (lane: {s.lane}, type: {s.task_type})"
                for s in hub.bpmn.steps[:30]
            )

        # ── Document content (cap at 6 000 chars; preserve head + tail) ────
        if len(document_content) > 6000:
            doc_excerpt = document_content[:4500] + "\n\n[...]\n\n" + document_content[-1000:]
        else:
            doc_excerpt = document_content

        user = f"""# DOCUMENTO PARA ANÁLISE
Título: {document_title}

{doc_excerpt}

---
# ARTEFATOS DA REUNIÃO

## Ata / Minutos
{minutes_text}

## Requisitos Extraídos
{reqs_text}

## Etapas do Processo BPMN
{bpmn_text}

---
output_language: {output_language}
"""
        return system, user

    def run(self, hub: KnowledgeHub) -> KnowledgeHub:  # type: ignore[override]
        """Not used directly — use analyze() instead."""
        return hub

    def analyze(
        self,
        document_title: str,
        document_content: str,
        hub: KnowledgeHub,
        output_language: str = "Auto-detect",
    ) -> Optional[dict]:
        """
        Cross-reference document against meeting artifacts.

        Returns the structured report dict or None on failure.
        Does NOT modify the hub — this is a read-only analysis.
        """
        system, user = self.build_prompt_for_doc(
            document_title, document_content, hub, output_language
        )
        try:
            raw = self._call_llm(system, user, hub)
            result = self._parse_json(raw)
            if not isinstance(result, dict):
                return None
            # Ensure alignment_score is in range
            if "alignment_score" in result:
                result["alignment_score"] = max(0, min(100, int(result["alignment_score"])))
            return result
        except Exception:
            return None
