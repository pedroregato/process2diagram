# modules/compliance/audit.py
# ─────────────────────────────────────────────────────────────────────────────
# LGPD audit trail writer (PC81).
#
# Writes to compliance_audit table asynchronously via daemon thread.
# Fail-open: never raises, never blocks caller.
#
# Supported event_type values:
#   pipeline_run      — new meeting processed through pipeline
#   consent_granted   — LGPD consent form submitted
#   data_accessed     — sensitive artifact retrieved by user
#   data_deleted      — meeting data purged (TTL or manual)
#   pii_detected      — PII classification result logged
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Optional


def log_audit_event(
    event_type: str,
    *,
    meeting_id: Optional[str] = None,
    project_id: Optional[str] = None,
    user_login: Optional[str] = None,
    details: Optional[dict] = None,
) -> None:
    """
    Asynchronously write an event to compliance_audit.

    Parameters
    ----------
    event_type : str
        One of: pipeline_run, consent_granted, data_accessed, data_deleted, pii_detected
    meeting_id : str, optional
        UUID of the associated meeting (nullable for pre-meeting events).
    project_id : str, optional
        UUID of the project context.
    user_login : str, optional
        Username from auth.get_current_user().
    details : dict, optional
        Arbitrary JSONB payload stored alongside the event.
    """

    def _write() -> None:
        try:
            from modules.supabase_client import get_supabase_client
            sb = get_supabase_client()
            if not sb:
                return
            row: dict = {
                "event_type": event_type,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            if meeting_id:
                row["meeting_id"] = meeting_id
            if project_id:
                row["project_id"] = project_id
            if user_login:
                row["user_login"] = user_login
            if details:
                row["details"] = details
            sb.table("compliance_audit").insert(row).execute()
        except Exception:
            pass  # audit must never raise

    threading.Thread(target=_write, daemon=True).start()
