# tests/test_diff_requirement_columns.py
"""
Regression test for a real bug found while building Onda 2 (melhorias/
avaliacao-proposta-assistente-20260708.md): diff_requirement()
(core/tools/tools_knowledge_requirements2.py) selected columns
"status, changed_at, change_note" from requirement_versions — none of
which exist on that table (confirmed against the live Supabase schema:
real columns are change_summary/created_at, no status column at all —
status lives on requirements, not requirement_versions). Every call
failed with a PostgREST 42703 "column does not exist" error, caught by
diff_requirement's own try/except and surfaced as a generic error
message — no test ever exercised this path to catch it.

No real DB calls — Supabase client mocked via a small fake keyed by
select() call signature (this test intentionally checks the fix DOESN'T
silently regress to selecting non-existent columns again).
"""

from unittest.mock import patch, MagicMock

from core.assistant_tools import AssistantToolExecutor

_LLM_CONFIG = {
    "api_key": "fake-key",
    "model": "fake-model",
    "provider_cfg": {"client_type": "openai_compatible", "default_model": "fake-model"},
}

# The real requirement_versions schema (verified against the live DB) —
# no "status", "changed_at" or "change_note" columns.
_REAL_COLUMNS = {"version", "title", "description", "change_type", "change_summary", "created_at"}


class _FakeQuery:
    def __init__(self, rows, real_columns=None):
        self._rows = rows
        self._real_columns = real_columns
        self._select_cols = None

    def select(self, cols):
        if self._real_columns is not None:
            requested = {c.strip() for c in cols.split(",")}
            unknown = requested - self._real_columns
            if unknown:
                raise Exception(f"column requirement_versions.{sorted(unknown)[0]} does not exist")
        return self

    def eq(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        resp = MagicMock()
        resp.data = self._rows
        return resp


class _FakeDB:
    def __init__(self, requirements_rows, versions_rows):
        self._requirements_rows = requirements_rows
        self._versions_rows = versions_rows

    def table(self, name):
        if name == "requirements":
            return _FakeQuery(self._requirements_rows)
        if name == "requirement_versions":
            return _FakeQuery(self._versions_rows, real_columns=_REAL_COLUMNS)
        return _FakeQuery([])


_REQ_ROW = [{"id": "req-1", "req_number": 7, "title": "Requisito de Teste"}]
_VERSION_ROWS = [
    {"version": 1, "title": "Versão 1", "description": "Descrição original",
     "change_type": "new", "change_summary": "Criado", "created_at": "2026-07-01T10:00:00"},
    {"version": 2, "title": "Versão 2 revisada", "description": "Descrição atualizada",
     "change_type": "revised", "change_summary": "Ajuste de escopo", "created_at": "2026-07-05T10:00:00"},
]


class TestDiffRequirementUsesRealColumns:
    def test_diff_requirement_does_not_query_nonexistent_columns(self):
        """Would have raised on the pre-fix column list — the _FakeQuery
        stub deliberately reproduces the real schema's constraint."""
        db = _FakeDB(_REQ_ROW, _VERSION_ROWS)
        ex = AssistantToolExecutor(project_id="proj-1", llm_config=_LLM_CONFIG)
        with patch("modules.supabase_client.get_supabase_client", return_value=db):
            result = ex.diff_requirement(req_number=7)
        assert "❌" not in result
        assert "renderizado" in result.lower()

    def test_diff_html_widget_uses_created_at_and_change_summary(self):
        import streamlit as st
        st.session_state.clear()
        db = _FakeDB(_REQ_ROW, _VERSION_ROWS)
        ex = AssistantToolExecutor(project_id="proj-1", llm_config=_LLM_CONFIG)
        with patch("modules.supabase_client.get_supabase_client", return_value=db):
            ex.diff_requirement(req_number=7)
        html = st.session_state["_pending_widgets"][0]["html"]
        assert "2026-07-01" in html
        assert "2026-07-05" in html
        assert "Ajuste de escopo" in html  # change_summary of the target version
