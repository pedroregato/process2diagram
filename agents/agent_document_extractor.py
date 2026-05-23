# agents/agent_document_extractor.py
# ─────────────────────────────────────────────────────────────────────────────
# DocumentExtractorAgent — extracts structured artifacts from a document.
#
# This agent is NOT part of the automatic pipeline.
# Called on-demand from pages/DocumentManager.py.
#
# extract() returns a plain dict with keys:
#   requirements, sbvr_terms, sbvr_rules, bmm_goals, bmm_strategies,
#   bmm_policies, dmn_decisions
# The caller persists results via core.project_store.save_artifacts_from_document().
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from typing import Optional

from agents.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub


class DocumentExtractorAgent(BaseAgent):
    name = "document_extractor"
    skill_path = "skills/skill_document_extractor.md"

    # build_prompt() and run() satisfy the abstract interface but are not used
    # directly. Use extract() instead.

    def build_prompt(self, hub: KnowledgeHub) -> tuple[str, str]:  # type: ignore[override]
        """Not used directly — use extract() instead."""
        return self._skill, ""

    def run(self, hub: KnowledgeHub) -> KnowledgeHub:  # type: ignore[override]
        """Not used in pipeline — call extract() instead."""
        return hub

    # ─────────────────────────────────────────────────────────────────────────

    def extract(
        self,
        doc_title: str,
        doc_content: str,
        output_language: str = "Auto-detect",
    ) -> Optional[dict]:
        """Extract artifacts from a document text.

        Returns a dict with keys: requirements, sbvr_terms, sbvr_rules,
        bmm_goals, bmm_strategies, bmm_policies, dmn_decisions (all optional).
        Returns None on failure.
        """
        system = self._load_skill()

        # Truncate very long documents: keep head + tail to stay within limits
        MAX_HEAD = 8000
        MAX_TAIL = 2000
        if len(doc_content) > MAX_HEAD + MAX_TAIL:
            content_trimmed = (
                doc_content[:MAX_HEAD]
                + f"\n\n[… {len(doc_content) - MAX_HEAD - MAX_TAIL:,} characters omitted …]\n\n"
                + doc_content[-MAX_TAIL:]
            )
        else:
            content_trimmed = doc_content

        lang_note = (
            ""
            if output_language in ("Auto-detect", "")
            else f"\nRespond in: {output_language}\n"
        )

        user = (
            f"# Document: {doc_title}\n"
            f"{lang_note}"
            f"\n---\n\n"
            f"{content_trimmed}"
        )

        # Use a minimal stub hub for _call_with_retry
        hub = _MinimalHub()

        try:
            raw = self._call_with_retry(system, user, hub)
        except Exception:
            return None

        return raw if isinstance(raw, dict) else None


# ── Minimal hub stub ──────────────────────────────────────────────────────────

class _MinimalHub:
    """Minimal object satisfying BaseAgent._call_with_retry() hub interface."""

    class _Meta:
        total_tokens_used  = 0
        processing_time_ms = 0
        cache_hits         = 0
        tokens_saved       = 0
        long_context_calls = 0
        llm_provider       = "unknown"
        llm_model          = "unknown"

    meta             = _Meta()
    transcript_clean = ""

    def bump(self):
        pass

    def mark_agent_run(self, name: str):
        pass
