# core/analyst_store.py
# ─────────────────────────────────────────────────────────────────────────────
# AnalystStore — persist and retrieve autonomous analysis reports in Supabase.
#
# Table: kh_analyses (created by setup/supabase_migration_kh_analyses.sql)
#
# Public API:
#   save_analysis(project_id, report, created_by) -> str | None  (returns id)
#   get_analyses(project_id, limit) -> list[dict]
#   get_analysis(analysis_id) -> dict | None
#   analyses_table_exists() -> bool
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import logging

_log = logging.getLogger(__name__)


def _db():
    from modules.supabase_client import get_supabase_client
    return get_supabase_client()


def _ok(response) -> list[dict]:
    return response.data or []


# ── Table existence check ─────────────────────────────────────────────────────

def analyses_table_exists() -> bool:
    """Return True when the kh_analyses table is accessible."""
    db = _db()
    if not db:
        return False
    try:
        db.table("kh_analyses").select("id").limit(1).execute()
        return True
    except Exception:
        return False


# ── Save ─────────────────────────────────────────────────────────────────────

def save_analysis(
    project_id: str,
    report,                  # AnalysisReport (imported lazily to avoid circular)
    created_by: str = "",
) -> str | None:
    """
    Persist an AnalysisReport to kh_analyses.
    Returns the new row UUID or None on failure.
    """
    db = _db()
    if not db:
        return None
    try:
        steps_json  = json.dumps([s.to_dict() for s in report.steps], ensure_ascii=False)
        tables_json = json.dumps(report.tables, ensure_ascii=False)

        row = {
            "project_id":  project_id,
            "objective":   report.objective[:2000],
            "conclusion":  report.conclusion[:10000] if report.conclusion else None,
            "steps_json":  steps_json,
            "tables_json": tables_json,
            "tokens_used": report.tokens_used,
            "duration_s":  round(report.duration_s, 2),
            "step_count":  len(report.steps),
            "created_by":  created_by or None,
            "success":     report.success,
            "error_msg":   report.error[:500] if report.error else None,
        }
        res = db.table("kh_analyses").insert(row).execute()
        rows = res.data or []
        return rows[0]["id"] if rows else None
    except Exception as exc:
        _log.error("save_analysis(%s): %s", project_id, exc)
        return None


# ── Read ──────────────────────────────────────────────────────────────────────

def get_analyses(
    project_id: str,
    limit: int = 20,
    success_only: bool = True,
) -> list[dict]:
    """Return recent analysis records for a project (most recent first)."""
    db = _db()
    if not db:
        return []
    try:
        q = (
            db.table("kh_analyses")
            .select("id, objective, conclusion, step_count, tokens_used, duration_s, "
                    "created_by, created_at, success")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .limit(limit)
        )
        if success_only:
            q = q.eq("success", True)
        return _ok(q.execute())
    except Exception as exc:
        _log.error("get_analyses(%s): %s", project_id, exc)
        return []


def get_analysis(analysis_id: str) -> dict | None:
    """Return a single analysis record with full steps and tables."""
    db = _db()
    if not db:
        return None
    try:
        rows = _ok(
            db.table("kh_analyses")
            .select("*")
            .eq("id", analysis_id)
            .limit(1)
            .execute()
        )
        if not rows:
            return None
        row = rows[0]
        # Deserialize JSON columns
        for col in ("steps_json", "tables_json"):
            if isinstance(row.get(col), str):
                try:
                    row[col] = json.loads(row[col])
                except Exception:
                    row[col] = []
        return row
    except Exception as exc:
        _log.error("get_analysis(%s): %s", analysis_id, exc)
        return None
