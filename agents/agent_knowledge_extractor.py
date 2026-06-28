# agents/agent_knowledge_extractor.py
# ─────────────────────────────────────────────────────────────────────────────
# AgentKnowledgeExtractor — extracts entities, processes, facts and
# contradictions from a meeting transcript and persists them in the
# Knowledge Hub (Supabase kh_* tables).
#
# Called non-fatally at the end of the pipeline (after all other agents).
# Failure is logged but never blocks the main pipeline result.
#
# PC9-A · Maio 2026
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import logging

from agents.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub
from core.output_schemas import KnowledgeExtractorOutputSchema

_log = logging.getLogger(__name__)


class AgentKnowledgeExtractor(BaseAgent):
    """
    Extracts structured knowledge from hub.transcript_clean and persists it
    in the Knowledge Hub tables (kh_entities, kh_processes, kh_facts,
    kh_contradictions) via core/knowledge_store.py.

    This agent is always non-fatal — any exception is caught and stored in
    hub.meta.kh_ingest_error so the main pipeline result is never affected.
    """

    name                 = "knowledge_extractor"
    skill_path           = "skills/skill_knowledge_extractor.md"
    required_hub_fields  = ["transcript_clean"]
    output_schema        = KnowledgeExtractorOutputSchema

    def build_prompt(
        self,
        hub: KnowledgeHub,
        output_language: str = "Auto-detect",
    ) -> tuple[str, str]:
        system = self._skill
        transcript = (hub.transcript_clean or hub.transcript_raw or "")[:12000]
        minutes_ctx = ""
        if hub.minutes and hub.minutes.ready:
            decisions = "\n".join(f"- {d}" for d in (hub.minutes.decisions or [])[:10])
            minutes_ctx = f"\n\n## Decisões registradas em ata\n{decisions}" if decisions else ""

        user = (
            f"Analise a seguinte transcrição de reunião e extraia o conhecimento estruturado "
            f"conforme as instruções do sistema.{minutes_ctx}\n\n"
            f"## Transcrição\n\n{transcript}"
        )
        return system, user

    def run(
        self,
        hub: KnowledgeHub,
        output_language: str = "Auto-detect",
        meeting_id: str | None = None,
        project_id: str | None = None,
    ) -> KnowledgeHub:
        """
        Extract and persist knowledge. Always returns hub unchanged on failure.

        Args:
            meeting_id:  Supabase meeting UUID (for source tracking)
            project_id:  Supabase project UUID
        """
        if not project_id:
            _log.warning("AgentKnowledgeExtractor: no project_id — skipping")
            return hub

        transcript = hub.transcript_clean or hub.transcript_raw or ""
        if len(transcript.strip()) < 100:
            _log.info("AgentKnowledgeExtractor: transcript too short — skipping")
            return hub

        try:
            system, user = self.build_prompt(hub, output_language)
            data = self._call_with_retry(system, user, hub)
            self._ingest(data, project_id, meeting_id)
            hub.mark_agent_run(self.name)
            hub.bump()
            _log.info(
                "AgentKnowledgeExtractor: ingested %d entities, %d processes, "
                "%d facts, %d contradictions",
                len(data.get("entities", [])),
                len(data.get("processes", [])),
                len(data.get("facts", [])),
                len(data.get("contradictions", [])),
            )
        except Exception as exc:
            _log.error("AgentKnowledgeExtractor failed (non-fatal): %s", exc)
            if hasattr(hub, "meta") and hub.meta:
                hub.meta.__dict__.setdefault("kh_ingest_error", str(exc))

        return hub

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _ingest(
        self,
        data: dict,
        project_id: str,
        meeting_id: str | None,
    ) -> None:
        """Persist extracted knowledge to Supabase kh_* tables."""
        from core.knowledge_store import (
            upsert_entity,
            upsert_process,
            insert_fact,
            insert_contradiction,
        )

        for entity in data.get("entities") or []:
            if entity.get("canonical_name"):
                upsert_entity(project_id, {**entity, "meeting_id": meeting_id})

        for process in data.get("processes") or []:
            if process.get("process_name"):
                upsert_process(project_id, {**process, "meeting_id": meeting_id})

        for fact in data.get("facts") or []:
            if fact.get("content"):
                insert_fact(project_id, {**fact, "meeting_id": meeting_id})

        for contradiction in data.get("contradictions") or []:
            if contradiction.get("description"):
                insert_contradiction(project_id, {
                    **contradiction,
                    "meeting_a_id": meeting_id,
                })
