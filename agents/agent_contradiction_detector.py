# agents/agent_contradiction_detector.py
# ─────────────────────────────────────────────────────────────────────────────
# AgentContradictionDetector — cross-meeting contradiction analysis for the
# Knowledge Hub.  Compares kh_facts entries to find contradictions that the
# single-transcript extractor cannot detect (different meetings, different
# contexts).
#
# Two operating modes:
#   • pipeline  — called after AgentKnowledgeExtractor with a specific
#                 meeting_id; compares facts from that meeting against the
#                 rest of the project's stored facts.
#   • full_scan — called on-demand (Assistente tool / maintenance); analyses
#                 ALL project facts grouped by fact_type.
#
# Always non-fatal: exceptions are logged but never propagate to callers.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import logging
import re
from typing import Any

from agents.base_agent import BaseAgent

_log = logging.getLogger(__name__)

# Maximum facts sent to LLM in one call to stay inside context window
_BATCH_SIZE = 40

# Minimum facts in a group before we bother calling the LLM
_MIN_GROUP_SIZE = 2


def _keyword_overlap(a: str, b: str) -> int:
    """Return count of significant words shared between two strings."""
    stop = {
        "de", "da", "do", "das", "dos", "e", "o", "a", "os", "as", "um",
        "uma", "que", "para", "com", "em", "por", "se", "no", "na",
        "the", "of", "is", "to", "in", "and", "or", "a",
    }
    words_a = {w.lower() for w in re.findall(r"\b\w{3,}\b", a) if w.lower() not in stop}
    words_b = {w.lower() for w in re.findall(r"\b\w{3,}\b", b) if w.lower() not in stop}
    return len(words_a & words_b)


class AgentContradictionDetector(BaseAgent):
    """
    Specialised agent that detects cross-meeting contradictions in kh_facts.

    Unlike AgentKnowledgeExtractor (which only sees one transcript at a time),
    this agent compares structured facts already stored in the Knowledge Hub,
    enabling detection of contradictions that span multiple meetings.
    """

    name       = "contradiction_detector"
    skill_path = "skills/skill_contradiction_detector.md"

    # ── Public entry points ───────────────────────────────────────────────────

    def run_for_meeting(
        self,
        project_id: str,
        meeting_id: str,
    ) -> int:
        """
        Pipeline mode: compare facts from meeting_id against existing facts.
        Returns the number of contradictions inserted.  Never raises.
        """
        try:
            return self._run_compare_mode(project_id, meeting_id)
        except Exception as exc:
            _log.error("AgentContradictionDetector.run_for_meeting failed: %s", exc)
            return 0

    def run_full_scan(self, project_id: str) -> int:
        """
        Full-scan mode: analyse ALL project facts for contradictions.
        Returns the number of contradictions inserted.  Never raises.
        """
        try:
            return self._run_fullscan_mode(project_id)
        except Exception as exc:
            _log.error("AgentContradictionDetector.run_full_scan failed: %s", exc)
            return 0

    # ── Compare mode (pipeline) ───────────────────────────────────────────────

    def _run_compare_mode(self, project_id: str, meeting_id: str) -> int:
        from core.knowledge_store import get_facts, insert_contradiction

        all_facts = get_facts(project_id, active_only=True, limit=300)
        if not all_facts:
            return 0

        new_facts      = [f for f in all_facts
                          if meeting_id in (f.get("source_meeting_ids") or [])]
        existing_facts = [f for f in all_facts
                          if meeting_id not in (f.get("source_meeting_ids") or [])]

        if not new_facts or not existing_facts:
            _log.info(
                "AgentContradictionDetector: nothing to compare "
                "(new=%d, existing=%d)", len(new_facts), len(existing_facts)
            )
            return 0

        # Pre-filter: for each new fact, keep only existing facts of the same
        # type that share at least 2 keywords — drastically reduces LLM tokens.
        candidates: list[tuple[dict, dict]] = []
        for nf in new_facts:
            nf_type    = nf.get("fact_type", "")
            nf_content = nf.get("content", "")
            for ef in existing_facts:
                if ef.get("fact_type") != nf_type:
                    continue
                if _keyword_overlap(nf_content, ef.get("content", "")) >= 2:
                    candidates.append((nf, ef))

        if not candidates:
            _log.info("AgentContradictionDetector: no keyword-overlapping candidates.")
            return 0

        _log.info(
            "AgentContradictionDetector (compare): %d candidate pair(s) → LLM",
            len(candidates)
        )

        # Deduplicate facts sent to LLM
        seen_ids: set[str] = set()
        batch_new, batch_existing = [], []
        for nf, ef in candidates:
            if nf["id"] not in seen_ids:
                batch_new.append(nf)
                seen_ids.add(nf["id"])
            if ef["id"] not in seen_ids:
                batch_existing.append(ef)
                seen_ids.add(ef["id"])

        return self._call_and_store(
            project_id=project_id,
            meeting_id=meeting_id,
            new_facts=batch_new[:_BATCH_SIZE],
            existing_facts=batch_existing[:_BATCH_SIZE],
        )

    # ── Full-scan mode (on-demand) ────────────────────────────────────────────

    def _run_fullscan_mode(self, project_id: str) -> int:
        from core.knowledge_store import get_facts

        all_facts = get_facts(project_id, active_only=True, limit=500)
        if len(all_facts) < _MIN_GROUP_SIZE:
            return 0

        # Group by fact_type and process batches
        by_type: dict[str, list[dict]] = {}
        for f in all_facts:
            by_type.setdefault(f.get("fact_type", "other"), []).append(f)

        total_inserted = 0
        for ftype, group in by_type.items():
            if len(group) < _MIN_GROUP_SIZE:
                continue

            _log.info(
                "AgentContradictionDetector (full scan): type=%s, %d facts",
                ftype, len(group)
            )

            # Slide a window if group is larger than batch size
            for i in range(0, len(group), _BATCH_SIZE):
                batch = group[i: i + _BATCH_SIZE]
                if len(batch) < _MIN_GROUP_SIZE:
                    continue
                n = self._call_and_store(
                    project_id=project_id,
                    meeting_id=None,
                    new_facts=batch,
                    existing_facts=[],
                )
                total_inserted += n

        return total_inserted

    # ── LLM call + persistence ────────────────────────────────────────────────

    def _call_and_store(
        self,
        project_id: str,
        meeting_id: str | None,
        new_facts: list[dict],
        existing_facts: list[dict],
    ) -> int:
        from core.knowledge_store import insert_contradiction

        system = self._skill

        def _fmt(facts: list[dict]) -> str:
            return json.dumps(
                [{"id": f["id"], "fact_type": f.get("fact_type"),
                  "content": f.get("content")} for f in facts],
                ensure_ascii=False, indent=2,
            )

        if existing_facts:
            user = (
                "Analise os fatos abaixo e identifique contradições entre "
                "`new_facts` e `existing_facts`.\n\n"
                f"## new_facts\n{_fmt(new_facts)}\n\n"
                f"## existing_facts\n{_fmt(existing_facts)}"
            )
        else:
            user = (
                "Analise os fatos abaixo e identifique contradições internas "
                "entre eles.\n\n"
                f"## facts\n{_fmt(new_facts)}"
            )

        # Use a minimal hub stub — base_agent needs it for token tracking
        from core.knowledge_hub import KnowledgeHub
        stub = KnowledgeHub()

        try:
            data = self._call_with_retry(system, user, stub)
        except Exception as exc:
            _log.error("AgentContradictionDetector LLM call failed: %s", exc)
            return 0

        contradictions = data.get("contradictions") or []
        inserted = 0

        # Build a fast lookup: fact_id → first source_meeting_id
        all_facts_idx: dict[str, str | None] = {}
        for f in new_facts + existing_facts:
            src = f.get("source_meeting_ids") or []
            all_facts_idx[f["id"]] = src[0] if src else None

        for c in contradictions:
            desc = (c.get("description") or "").strip()
            if not desc:
                continue

            # Skip very low-confidence detections
            conf = c.get("confidence")
            try:
                conf = float(conf) if conf is not None else None
            except (TypeError, ValueError):
                conf = None
            if conf is not None and conf < 0.50:
                continue

            # Skip purely positive relations — not worth storing
            relation_type = c.get("relation_type") or ""
            if relation_type in ("equivalent", "complementary", "more_specific"):
                continue

            # Resolve meeting_b_id from fact_b_id
            fact_b_id    = c.get("fact_b_id")
            meeting_b_id = all_facts_idx.get(fact_b_id) if fact_b_id else None

            payload = {
                "description":         desc,
                "process_name":        c.get("process_name") or None,
                "severity":            c.get("severity") or "medium",
                "meeting_a_id":        meeting_id,
                "meeting_b_id":        meeting_b_id,
                "relation_type":       relation_type or None,
                "confidence":          conf,
                "clarifying_question": c.get("clarifying_question") or None,
                "suggested_rewrite":   c.get("suggested_rewrite") or None,
            }
            result = insert_contradiction(project_id, payload)
            if result:
                inserted += 1

        _log.info(
            "AgentContradictionDetector: inserted %d contradiction(s)", inserted
        )
        return inserted

    # ── build_prompt (required by BaseAgent, unused directly) ─────────────────

    def build_prompt(self, hub: Any, output_language: str = "Auto-detect"):  # type: ignore[override]
        raise NotImplementedError(
            "Use run_for_meeting() or run_full_scan() instead."
        )
