# tests/test_meeting_processing_log.py
"""
Tests for PC152 — meeting_processing_log auxiliary table, its
core/project_store.py helpers (log_meeting_processing,
get_meeting_processing_history, count_meeting_processings), and the
corresponding Assistant tool get_meeting_processing_history.

Motivation: after PC151 (silent data-loss bug — pipeline ran but nothing
was persisted), the user asked for an auxiliary table recording the
effective processing date of every transcript processing/reprocessing
event, so the count and dates of reprocessing are always knowable.

No real DB calls — Supabase mocked via a small fake client.
"""

from unittest.mock import patch, MagicMock

from core.project_store import (
    log_meeting_processing,
    get_meeting_processing_history,
    count_meeting_processings,
)
from core.assistant_tools import AssistantToolExecutor

_LLM_CONFIG = {
    "api_key": "fake-key",
    "model": "fake-model",
    "provider_cfg": {"client_type": "openai_compatible", "default_model": "fake-model"},
}


class _FakeInsertQuery:
    def __init__(self, store: list[dict]):
        self._store = store
        self._payload = None

    def insert(self, payload):
        self._payload = payload
        return self

    def execute(self):
        self._store.append(self._payload)
        resp = MagicMock()
        resp.data = [self._payload]
        return resp


class _FakeSelectQuery:
    def __init__(self, rows: list[dict]):
        self._rows = rows
        self._count_exact = False

    def select(self, *a, count=None, **k):
        if count == "exact":
            self._count_exact = True
        return self

    def eq(self, col, val):
        self._rows = [r for r in self._rows if r.get(col) == val]
        return self

    def order(self, col, desc=False):
        self._rows = sorted(self._rows, key=lambda r: r.get(col) or "", reverse=desc)
        return self

    def limit(self, n):
        return self

    def execute(self):
        resp = MagicMock()
        resp.data = self._rows
        resp.count = len(self._rows) if self._count_exact else None
        return resp


class _FakeDB:
    """Routes .table('meeting_processing_log') to insert or select fakes
    depending on which method is called first, using a shared backing list."""

    def __init__(self, rows: list[dict] | None = None):
        self.rows = rows if rows is not None else []

    def table(self, name):
        return _FakeTableProxy(self)


class _FakeTableProxy:
    def __init__(self, db: _FakeDB):
        self._db = db

    def insert(self, payload):
        q = _FakeInsertQuery(self._db.rows)
        return q.insert(payload)

    def select(self, *a, **k):
        q = _FakeSelectQuery(list(self._db.rows))
        return q.select(*a, **k)


class TestLogMeetingProcessing:
    def test_no_supabase_returns_false(self):
        with patch("core.project_store._db", return_value=None):
            assert log_meeting_processing("m1", "p1") is False

    def test_success_returns_true_and_stores_payload(self):
        db = _FakeDB()
        with patch("core.project_store._db", return_value=db):
            ok = log_meeting_processing(
                meeting_id="m1", project_id="p1", processing_type="new",
                llm_provider="DeepSeek", total_tokens=1234,
            )
        assert ok is True
        assert len(db.rows) == 1
        assert db.rows[0]["meeting_id"] == "m1"
        assert db.rows[0]["processing_type"] == "new"
        assert db.rows[0]["total_tokens"] == 1234
        assert db.rows[0]["success"] is True

    def test_reprocess_agent_stores_agent_name(self):
        db = _FakeDB()
        with patch("core.project_store._db", return_value=db):
            log_meeting_processing(
                meeting_id="m1", project_id="p1",
                processing_type="reprocess_agent", agent_name="bpmn",
            )
        assert db.rows[0]["agent_name"] == "bpmn"

    def test_failure_event_stores_error_message(self):
        db = _FakeDB()
        with patch("core.project_store._db", return_value=db):
            log_meeting_processing(
                meeting_id="m1", project_id="p1", processing_type="reprocess_full",
                success=False, error_message="timeout",
            )
        assert db.rows[0]["success"] is False
        assert db.rows[0]["error_message"] == "timeout"

    def test_exception_during_insert_returns_false(self):
        class _BoomDB:
            def table(self, name):
                raise RuntimeError("network down")
        with patch("core.project_store._db", return_value=_BoomDB()):
            assert log_meeting_processing("m1", "p1") is False


class TestGetMeetingProcessingHistory:
    def test_no_supabase_returns_empty(self):
        with patch("core.project_store._db", return_value=None):
            assert get_meeting_processing_history("m1") == []

    def test_returns_rows_for_meeting(self):
        db = _FakeDB(rows=[
            {"meeting_id": "m1", "processing_type": "new", "processed_at": "2026-06-01T10:00:00"},
            {"meeting_id": "m1", "processing_type": "reprocess_full", "processed_at": "2026-06-05T10:00:00"},
            {"meeting_id": "m2", "processing_type": "new", "processed_at": "2026-06-02T10:00:00"},
        ])
        with patch("core.project_store._db", return_value=db):
            rows = get_meeting_processing_history("m1")
        assert len(rows) == 2
        assert all(r["meeting_id"] == "m1" for r in rows)

    def test_exception_returns_empty(self):
        class _BoomDB:
            def table(self, name):
                raise RuntimeError("boom")
        with patch("core.project_store._db", return_value=_BoomDB()):
            assert get_meeting_processing_history("m1") == []


class TestCountMeetingProcessings:
    def test_no_supabase_returns_zero(self):
        with patch("core.project_store._db", return_value=None):
            assert count_meeting_processings("m1") == 0

    def test_counts_only_matching_meeting(self):
        db = _FakeDB(rows=[
            {"meeting_id": "m1"}, {"meeting_id": "m1"}, {"meeting_id": "m1"},
            {"meeting_id": "m2"},
        ])
        with patch("core.project_store._db", return_value=db):
            assert count_meeting_processings("m1") == 3
            assert count_meeting_processings("m2") == 1
            assert count_meeting_processings("m3") == 0


# ── Assistant tool ────────────────────────────────────────────────────────────

def _executor():
    return AssistantToolExecutor("proj-1", llm_config=_LLM_CONFIG)


class _FakeMeetingChain:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def execute(self):
        resp = MagicMock()
        resp.data = self._rows
        return resp


class _FakeMeetingDB:
    def __init__(self, meetings):
        self._meetings = meetings

    def table(self, name):
        if name == "meetings":
            return _FakeMeetingChain(self._meetings)
        raise AssertionError(f"unexpected table {name}")


_MEETING_ROW = {
    "id": "m1", "meeting_number": 5, "title": "Kickoff",
    "minutes_md": "", "transcript_clean": "x", "transcript_raw": "",
}


class TestGetMeetingProcessingHistoryTool:
    def test_meeting_not_found(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_FakeMeetingDB([])):
            result = ex.get_meeting_processing_history(meeting_number=99)
        assert "não encontrada" in result

    def test_no_history_recorded(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_FakeMeetingDB([_MEETING_ROW])):
            with patch("core.project_store.get_meeting_processing_history", return_value=[]):
                result = ex.get_meeting_processing_history(meeting_number=5)
        assert "Nenhum registro" in result

    def test_formats_multiple_events(self):
        ex = _executor()
        history = [
            {"processing_type": "reprocess_agent", "agent_name": "bpmn",
             "processed_at": "2026-06-10T14:30:00", "success": True, "total_tokens": 500},
            {"processing_type": "new", "processed_at": "2026-06-01T10:00:00",
             "success": True, "total_tokens": 12000},
        ]
        with patch("modules.supabase_client.get_supabase_client", return_value=_FakeMeetingDB([_MEETING_ROW])):
            with patch("core.project_store.get_meeting_processing_history", return_value=history):
                result = ex.get_meeting_processing_history(meeting_number=5)
        assert "2 evento(s)" in result
        assert "Processamento inicial" in result
        assert "Reprocessamento de agente (bpmn)" in result
        assert "12,000 tokens" in result or "12000" in result

    def test_formats_failed_event(self):
        ex = _executor()
        history = [
            {"processing_type": "reprocess_full", "processed_at": "2026-06-10T14:30:00",
             "success": False, "error_message": "timeout", "total_tokens": 0},
        ]
        with patch("modules.supabase_client.get_supabase_client", return_value=_FakeMeetingDB([_MEETING_ROW])):
            with patch("core.project_store.get_meeting_processing_history", return_value=history):
                result = ex.get_meeting_processing_history(meeting_number=5)
        assert "❌" in result
        assert "timeout" in result


class TestDispatchAndCategory:
    def test_dispatch_wired(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_FakeMeetingDB([_MEETING_ROW])):
            with patch("core.project_store.get_meeting_processing_history", return_value=[]):
                result = ex.execute("get_meeting_processing_history", {"meeting_number": 5})
        assert isinstance(result, str)

    def test_not_admin_gated(self):
        from core.assistant_tools import _ADMIN_TOOLS
        assert "get_meeting_processing_history" not in _ADMIN_TOOLS

    def test_categorized_as_consulta(self):
        from core.assistant_tools import _TOOL_CATEGORIES
        assert _TOOL_CATEGORIES.get("get_meeting_processing_history") == "consulta"
