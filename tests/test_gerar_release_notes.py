# tests/test_gerar_release_notes.py
"""
Tests for core/tools/tools_executive_advanced.py::gerar_release_notes()
(melhorias/avaliacao-proposta-assistente-20260708.md, proposta #6):
consolidates requirement_versions changes between two meeting milestones
into LLM-written release notes.

No real DB/LLM calls.
"""

from unittest.mock import patch, MagicMock

from core.assistant_tools import AssistantToolExecutor

_LLM_CONFIG = {
    "api_key": "fake-key",
    "model": "fake-model",
    "provider_cfg": {"client_type": "openai_compatible", "default_model": "fake-model"},
}

_MEETINGS = [
    {"id": "m1", "meeting_number": 1, "meeting_date": "2026-06-01"},
    {"id": "m2", "meeting_number": 2, "meeting_date": "2026-06-15"},
    {"id": "m3", "meeting_number": 3, "meeting_date": "2026-07-01"},
]

_VERSIONS = [
    {"requirement_id": "r1", "version": 1, "change_type": "new",
     "change_summary": "Requisito criado", "title": "Login SSO", "created_at": "2026-06-15T10:00:00"},
    {"requirement_id": "r2", "version": 2, "change_type": "revised",
     "change_summary": "Prazo ajustado", "title": "Exportar relatório", "created_at": "2026-07-01T09:00:00"},
]

_REQS = [
    {"id": "r1", "req_number": 5, "title": "Login SSO"},
    {"id": "r2", "req_number": 3, "title": "Exportar relatório"},
]


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def execute(self):
        resp = MagicMock()
        resp.data = self._rows
        return resp


class _FakeDB:
    def __init__(self, tables: dict):
        self._tables = tables

    def table(self, name):
        return _FakeQuery(self._tables.get(name, []))


def _executor(meetings=_MEETINGS, tables=None):
    ex = AssistantToolExecutor(project_id="proj-1", llm_config=_LLM_CONFIG)
    ex._get_meetings = lambda: meetings
    ex._llm_call = lambda system, user, max_tokens=3000: "## Resumo\nNotas geradas com sucesso."
    db = _FakeDB(tables or {})
    patcher = patch("modules.supabase_client.get_supabase_client", return_value=db)
    patcher.start()
    return ex, patcher


class TestGerarReleaseNotes:
    def test_no_meetings_in_range(self):
        ex, patcher = _executor(meetings=[])
        try:
            result = ex.gerar_release_notes(1, 2)
        finally:
            patcher.stop()
        assert "nenhuma reunião" in result.lower()

    def test_no_requirement_changes_in_range(self):
        ex, patcher = _executor(tables={"requirement_versions": []})
        try:
            result = ex.gerar_release_notes(1, 2)
        finally:
            patcher.stop()
        assert "nenhuma alteração" in result.lower()

    def test_generates_notes_grouped_by_change_type(self):
        ex, patcher = _executor(tables={"requirement_versions": _VERSIONS, "requirements": _REQS})
        captured = {}

        def _fake_llm_call(system, user, max_tokens=3000):
            captured["user"] = user
            return "## Resumo\nNotas geradas com sucesso."

        ex._llm_call = _fake_llm_call
        try:
            result = ex.gerar_release_notes(1, 3)
        finally:
            patcher.stop()

        # The raw grouped data (REQ numbers, change types) is what gets fed
        # to the LLM as the user prompt — verify assembly there.
        assert "REQ-005" in captured["user"]
        assert "REQ-003" in captured["user"]
        assert "Novos requisitos" in captured["user"]
        assert "Requisitos revisados" in captured["user"]

        # The final returned text is the LLM's own prose plus the header/footer.
        assert "2 mudança" in result
        assert "Notas geradas com sucesso" in result

    def test_swaps_reversed_meeting_range(self):
        ex, patcher = _executor(tables={"requirement_versions": _VERSIONS, "requirements": _REQS})
        try:
            result = ex.gerar_release_notes(3, 1)  # reversed on purpose
        finally:
            patcher.stop()
        assert "Reunião 1 → 3" in result

    def test_llm_failure_returns_error_not_exception(self):
        ex, patcher = _executor(tables={"requirement_versions": _VERSIONS, "requirements": _REQS})
        ex._llm_call = MagicMock(side_effect=RuntimeError("timeout"))
        try:
            result = ex.gerar_release_notes(1, 3)
        finally:
            patcher.stop()
        assert "❌" in result
