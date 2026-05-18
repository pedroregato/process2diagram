# core/knowledge_store.py
# ─────────────────────────────────────────────────────────────────────────────
# KnowledgeStore — persistent cross-session knowledge for Process2Diagram.
#
# Stores entities, processes, facts and contradictions extracted from meeting
# transcripts. Acts as cross-session memory that enriches assistant responses
# over time.
#
# Tables: kh_entities, kh_processes, kh_facts, kh_contradictions
# Schema: setup/supabase_schema_knowledge_hub.sql
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import logging
from typing import Any

_log = logging.getLogger(__name__)


def _db():
    from modules.supabase_client import get_supabase_client
    return get_supabase_client()


def _ok(response) -> list[dict]:
    return response.data or []


# ── Entities ──────────────────────────────────────────────────────────────────

def get_entities(
    project_id: str,
    entity_type: str | None = None,
    limit: int = 100,
) -> list[dict]:
    """Return entities for a project, optionally filtered by type."""
    db = _db()
    if not db:
        return []
    try:
        q = (
            db.table("kh_entities")
            .select("id, entity_type, canonical_name, aliases, occurrence_count, "
                    "first_seen_meeting_id, last_seen_meeting_id, metadata, updated_at")
            .eq("project_id", project_id)
            .order("occurrence_count", desc=True)
            .limit(limit)
        )
        if entity_type:
            q = q.eq("entity_type", entity_type)
        return _ok(q.execute())
    except Exception as exc:
        _log.error("get_entities(%s): %s", project_id, exc)
        return []


def upsert_entity(project_id: str, entity: dict) -> dict | None:
    """
    Create or update an entity. On conflict (project_id, canonical_name, entity_type),
    increments occurrence_count and merges aliases and meeting_ids.
    entity keys: entity_type, canonical_name, aliases[], meeting_id, metadata{}
    """
    db = _db()
    if not db:
        return None
    try:
        canonical = (entity.get("canonical_name") or "").strip()
        etype = (entity.get("entity_type") or "other").strip()
        if not canonical:
            return None

        # Check for existing
        existing = _ok(
            db.table("kh_entities")
            .select("id, occurrence_count, aliases, first_seen_meeting_id, meeting_ids")
            .eq("project_id", project_id)
            .eq("canonical_name", canonical)
            .eq("entity_type", etype)
            .limit(1)
            .execute()
        )

        meeting_id = entity.get("meeting_id") or None
        new_aliases = list(entity.get("aliases") or [])

        if existing:
            row = existing[0]
            merged_aliases = list(set((row.get("aliases") or []) + new_aliases))
            # Merge meeting_ids — append new meeting if not already tracked
            existing_mids = list(row.get("meeting_ids") or [])
            if meeting_id and meeting_id not in existing_mids:
                existing_mids.append(meeting_id)
            patch = {
                "occurrence_count":    (row.get("occurrence_count") or 1) + 1,
                "aliases":             merged_aliases,
                "last_seen_meeting_id": meeting_id,
                "meeting_ids":         existing_mids,
                "metadata":            entity.get("metadata") or {},
            }
            result = (
                db.table("kh_entities")
                .update(patch)
                .eq("id", row["id"])
                .execute()
            )
        else:
            mids = [meeting_id] if meeting_id else []
            payload = {
                "project_id":            project_id,
                "entity_type":           etype,
                "canonical_name":        canonical,
                "aliases":               new_aliases,
                "first_seen_meeting_id": meeting_id,
                "last_seen_meeting_id":  meeting_id,
                "meeting_ids":           mids,
                "occurrence_count":      1,
                "metadata":              entity.get("metadata") or {},
            }
            result = db.table("kh_entities").insert(payload).execute()

        return result.data[0] if result.data else None
    except Exception as exc:
        _log.error("upsert_entity(%s, %s): %s", project_id, entity.get("canonical_name"), exc)
        return None


def merge_entities(project_id: str, keep_id: str, discard_ids: list[str]) -> bool:
    """
    Merge duplicate entities: absorb aliases/meeting_ids/occurrence_count from
    discard_ids into keep_id, then delete the discarded rows.
    Returns True if successful.
    """
    db = _db()
    if not db or not discard_ids:
        return False
    try:
        # Fetch all rows
        all_ids = [keep_id] + discard_ids
        rows = _ok(
            db.table("kh_entities")
            .select("id, aliases, meeting_ids, occurrence_count")
            .in_("id", all_ids)
            .execute()
        )
        if not rows:
            return False

        keep_row = next((r for r in rows if r["id"] == keep_id), None)
        if not keep_row:
            return False

        # Merge aliases and meeting_ids from all discarded rows
        merged_aliases  = list(set(keep_row.get("aliases") or []))
        merged_mids     = list(keep_row.get("meeting_ids") or [])
        merged_count    = keep_row.get("occurrence_count") or 1

        for row in rows:
            if row["id"] == keep_id:
                continue
            for a in (row.get("aliases") or []):
                if a not in merged_aliases:
                    merged_aliases.append(a)
            for m in (row.get("meeting_ids") or []):
                if m not in merged_mids:
                    merged_mids.append(m)
            merged_count += (row.get("occurrence_count") or 1)

        # Update keep_id
        db.table("kh_entities").update({
            "aliases":         merged_aliases,
            "meeting_ids":     merged_mids,
            "occurrence_count": merged_count,
        }).eq("id", keep_id).execute()

        # Delete discarded rows
        db.table("kh_entities").delete().in_("id", discard_ids).execute()

        _log.info(
            "merge_entities: merged %d duplicates into %s (count=%d)",
            len(discard_ids), keep_id, merged_count,
        )
        return True
    except Exception as exc:
        _log.error("merge_entities(%s): %s", project_id, exc)
        return False


# ── Processes ─────────────────────────────────────────────────────────────────

def get_processes(project_id: str, status: str | None = None) -> list[dict]:
    """Return known processes for a project."""
    db = _db()
    if not db:
        return []
    try:
        q = (
            db.table("kh_processes")
            .select("id, process_name, description, version_count, status, "
                    "first_meeting_id, last_meeting_id, updated_at")
            .eq("project_id", project_id)
            .order("version_count", desc=True)
        )
        if status:
            q = q.eq("status", status)
        return _ok(q.execute())
    except Exception as exc:
        _log.error("get_processes(%s): %s", project_id, exc)
        return []


def upsert_process(project_id: str, process: dict) -> dict | None:
    """Create or update a known process (upsert on project_id + process_name)."""
    db = _db()
    if not db:
        return None
    try:
        name = (process.get("process_name") or "").strip()
        if not name:
            return None
        meeting_id = process.get("meeting_id") or None

        existing = _ok(
            db.table("kh_processes")
            .select("id, version_count, meeting_ids")
            .eq("project_id", project_id)
            .eq("process_name", name)
            .limit(1)
            .execute()
        )

        if existing:
            row = existing[0]
            ids = list(row.get("meeting_ids") or [])
            if meeting_id and meeting_id not in ids:
                ids.append(meeting_id)
            patch = {
                "description":      process.get("description") or row.get("description"),
                "version_count":    (row.get("version_count") or 1) + 1,
                "last_meeting_id":  meeting_id,
                "meeting_ids":      ids,
            }
            result = db.table("kh_processes").update(patch).eq("id", row["id"]).execute()
        else:
            ids = [meeting_id] if meeting_id else []
            payload = {
                "project_id":       project_id,
                "process_name":     name,
                "description":      process.get("description") or "",
                "version_count":    1,
                "first_meeting_id": meeting_id,
                "last_meeting_id":  meeting_id,
                "meeting_ids":      ids,
                "status":           "active",
            }
            result = db.table("kh_processes").insert(payload).execute()

        return result.data[0] if result.data else None
    except Exception as exc:
        _log.error("upsert_process(%s, %s): %s", project_id, process.get("process_name"), exc)
        return None


# ── Facts ─────────────────────────────────────────────────────────────────────

def get_facts(
    project_id: str,
    fact_type: str | None = None,
    active_only: bool = True,
    limit: int = 50,
) -> list[dict]:
    """Return consolidated facts for a project."""
    db = _db()
    if not db:
        return []
    try:
        q = (
            db.table("kh_facts")
            .select("id, fact_type, content, source_meeting_ids, confidence, "
                    "superseded_by, is_active, updated_at")
            .eq("project_id", project_id)
            .order("confidence", desc=True)
            .limit(limit)
        )
        if active_only:
            q = q.eq("is_active", True)
        if fact_type:
            q = q.eq("fact_type", fact_type)
        return _ok(q.execute())
    except Exception as exc:
        _log.error("get_facts(%s): %s", project_id, exc)
        return []


def insert_fact(project_id: str, fact: dict) -> dict | None:
    """Insert a new fact. Caller is responsible for deduplication logic."""
    db = _db()
    if not db:
        return None
    try:
        content = (fact.get("content") or "").strip()
        if not content:
            return None
        meeting_id = fact.get("meeting_id") or None
        payload = {
            "project_id":        project_id,
            "fact_type":         fact.get("fact_type") or "decision",
            "content":           content,
            "source_meeting_ids": [meeting_id] if meeting_id else [],
            "confidence":        float(fact.get("confidence", 1.0)),
            "is_active":         True,
        }
        if fact.get("dialogue_act"):
            payload["dialogue_act"] = fact["dialogue_act"]
        if fact.get("utterance_speaker"):
            payload["utterance_speaker"] = fact["utterance_speaker"]
        result = db.table("kh_facts").insert(payload).execute()
        return result.data[0] if result.data else None
    except Exception as exc:
        _log.error("insert_fact(%s): %s", project_id, exc)
        return None


def mark_fact_superseded(fact_id: str, new_fact_id: str) -> bool:
    db = _db()
    if not db:
        return False
    try:
        db.table("kh_facts").update({"is_active": False, "superseded_by": new_fact_id}).eq("id", fact_id).execute()
        return True
    except Exception as exc:
        _log.error("mark_fact_superseded(%s): %s", fact_id, exc)
        return False


# ── Contradictions ────────────────────────────────────────────────────────────

def get_contradictions(
    project_id: str,
    status: str | None = "open",
    limit: int = 50,
) -> list[dict]:
    """Return detected contradictions for a project."""
    db = _db()
    if not db:
        return []
    try:
        q = (
            db.table("kh_contradictions")
            .select("id, process_name, description, meeting_a_id, meeting_b_id, "
                    "severity, status, resolved_by, resolution_note, "
                    "relation_type, confidence, clarifying_question, suggested_rewrite, "
                    "updated_at")
            .eq("project_id", project_id)
            .order("updated_at", desc=True)
            .limit(limit)
        )
        if status:
            q = q.eq("status", status)
        return _ok(q.execute())
    except Exception as exc:
        _log.error("get_contradictions(%s): %s", project_id, exc)
        return []


def insert_contradiction(project_id: str, contradiction: dict) -> dict | None:
    db = _db()
    if not db:
        return None
    try:
        desc = (contradiction.get("description") or "").strip()
        if not desc:
            return None

        relation_type = contradiction.get("relation_type") or None
        # Only store real contradictions and noteworthy relations
        _VALID_RELATIONS = {
            "contradiction_direct", "contradiction_conditional",
            "contradiction_temporal", "contradiction_responsibility",
            "exception", "superseded", "ambiguous",
        }
        if relation_type and relation_type not in _VALID_RELATIONS:
            relation_type = None

        confidence = contradiction.get("confidence")
        try:
            confidence = float(confidence) if confidence is not None else None
        except (TypeError, ValueError):
            confidence = None

        payload = {
            "project_id":          project_id,
            "process_name":        contradiction.get("process_name") or None,
            "description":         desc,
            "meeting_a_id":        contradiction.get("meeting_a_id") or None,
            "meeting_b_id":        contradiction.get("meeting_b_id") or None,
            "severity":            contradiction.get("severity") or "medium",
            "status":              "open",
            "relation_type":       relation_type,
            "confidence":          confidence,
            "clarifying_question": (contradiction.get("clarifying_question") or "").strip() or None,
            "suggested_rewrite":   (contradiction.get("suggested_rewrite") or "").strip() or None,
        }
        result = db.table("kh_contradictions").insert(payload).execute()
        return result.data[0] if result.data else None
    except Exception as exc:
        _log.error("insert_contradiction(%s): %s", project_id, exc)
        return None


def resolve_contradiction(
    contradiction_id: str,
    resolved_by: str,
    resolution_note: str,
    status: str = "resolved",
) -> bool:
    db = _db()
    if not db:
        return False
    try:
        db.table("kh_contradictions").update({
            "status": status,
            "resolved_by": resolved_by,
            "resolution_note": resolution_note,
        }).eq("id", contradiction_id).execute()
        return True
    except Exception as exc:
        _log.error("resolve_contradiction(%s): %s", contradiction_id, exc)
        return False


# ── Summary / context injection ───────────────────────────────────────────────

def get_kh_context_summary(project_id: str, max_chars: int = 1500) -> str:
    """
    Build a compact knowledge context block for injection into LLM prompts.
    Returns an empty string if tables don't exist or data is unavailable.
    """
    db = _db()
    if not db:
        return ""
    try:
        entities = get_entities(project_id, limit=20)
        facts    = get_facts(project_id, active_only=True, limit=15)
        contras  = get_contradictions(project_id, status="open", limit=5)
        procs    = get_processes(project_id, status="active")[:10]

        if not any([entities, facts, contras, procs]):
            return ""

        lines = ["## Conhecimento Acumulado do Projeto\n"]

        if procs:
            lines.append(f"**Processos identificados ({len(procs)}):** " +
                         " · ".join(p["process_name"] for p in procs[:8]))

        if entities:
            by_type: dict[str, list] = {}
            for e in entities:
                by_type.setdefault(e["entity_type"], []).append(
                    f"{e['canonical_name']} ({e['occurrence_count']}x)"
                )
            for etype, names in by_type.items():
                lines.append(f"**{etype.capitalize()}s:** " + ", ".join(names[:8]))

        if facts:
            lines.append("\n**Fatos e decisões consolidados:**")
            for f in facts[:10]:
                conf = f.get("confidence", 1.0)
                conf_label = "" if conf >= 0.9 else f" [conf: {conf:.0%}]"
                lines.append(f"- [{f['fact_type']}] {f['content']}{conf_label}")

        if contras:
            lines.append(f"\n**⚠️ Contradições abertas ({len(contras)}):**")
            for c in contras[:3]:
                sev = c.get("severity", "medium")
                lines.append(f"- [{sev}] {c['description'][:150]}")

        result = "\n".join(lines)
        if len(result) > max_chars:
            result = result[:max_chars] + "\n...[contexto truncado]"
        return result
    except Exception as exc:
        _log.warning("get_kh_context_summary(%s): %s", project_id, exc)
        return ""


def kh_tables_exist() -> bool:
    """Return True if the Knowledge Hub tables have been created in Supabase."""
    db = _db()
    if not db:
        return False
    try:
        db.table("kh_entities").select("id").limit(1).execute()
        return True
    except Exception:
        return False
