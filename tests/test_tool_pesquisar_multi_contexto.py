# tests/test_tool_pesquisar_multi_contexto.py
"""
Tests for AssistantToolExecutor.pesquisar_multi_contexto() — melhoria
"assistente-20260711.md" item #6: search across ALL contexts of the same
tenant instead of just the active project_id. Reuses the PC165
(list_all_business_assets_for_domain) cross-context pattern — resolves
tenant_id from the current context, loops list_contexts(), queries each
context directly (no multiple AssistantToolExecutor instances).

_extract_keywords/_extract_passages are pure functions (no DB access) — run
for real. get_context/list_contexts and the Supabase client are mocked.
"""

from unittest.mock import MagicMock, patch

from core.assistant_tools import AssistantToolExecutor


def _executor():
    return AssistantToolExecutor("proj-1", {})


def _fake_db(meetings_by_project: dict[str, list[dict]]):
    """Builds a MagicMock chain mimicking db.table("meetings").select(...)
    .eq("project_id", cid).order(...).execute().data — keyed per project_id."""
    db = MagicMock()

    def _table(name):
        assert name == "meetings"
        query = MagicMock()

        def _eq(field, value):
            assert field == "project_id"
            result = MagicMock()
            result.data = meetings_by_project.get(value, [])
            ordered = MagicMock()
            ordered.execute.return_value = result
            query.order.return_value = ordered
            return query

        query.select.return_value = query
        query.eq.side_effect = _eq
        return query

    db.table.side_effect = _table
    return db


class TestPesquisarMultiContexto:
    def test_no_keywords_returns_guidance_message(self):
        ex = _executor()
        result = ex.pesquisar_multi_contexto("   ")
        assert "palavras-chave" in result.lower()

    def test_db_unavailable_reported_without_raising(self):
        with patch("modules.supabase_client.get_supabase_client", return_value=None):
            ex = _executor()
            result = ex.pesquisar_multi_contexto("integração")
        assert "não disponível" in result.lower()

    def test_no_contexts_found_reports_clearly(self):
        with patch("modules.supabase_client.get_supabase_client", return_value=MagicMock()), \
             patch("core.project_store.get_context", return_value=None), \
             patch("core.project_store.list_contexts", return_value=[]):
            ex = _executor()
            result = ex.pesquisar_multi_contexto("core banking")
        assert "nenhum contexto" in result.lower()

    def test_finds_hits_across_multiple_contexts_and_labels_them(self):
        meetings_by_project = {
            "ctx-a": [{
                "meeting_number": 1, "title": "Reunião A",
                "transcript_clean": "Discutimos a integração com Core Banking amplamente nesta reunião.",
            }],
            "ctx-b": [{
                "meeting_number": 5, "title": "Reunião B",
                "transcript_clean": "Nada relevante aqui sobre o assunto pesquisado hoje.",
            }],
        }
        db = _fake_db(meetings_by_project)
        with patch("modules.supabase_client.get_supabase_client", return_value=db), \
             patch("core.project_store.get_context", return_value={"id": "ctx-a", "tenant_id": "t1"}), \
             patch("core.project_store.list_contexts", return_value=[
                 {"id": "ctx-a", "name": "Contexto Aurora"},
                 {"id": "ctx-b", "name": "Contexto SDEA"},
             ]):
            ex = _executor()
            result = ex.pesquisar_multi_contexto("Core Banking")

        assert "Contexto Aurora" in result
        assert "Reunião 1" in result
        assert "Contexto SDEA" not in result  # no hits there — not listed

    def test_no_hits_anywhere_reports_clearly(self):
        meetings_by_project = {
            "ctx-a": [{"meeting_number": 1, "title": "R1", "transcript_clean": "Texto qualquer sem relação."}],
        }
        db = _fake_db(meetings_by_project)
        with patch("modules.supabase_client.get_supabase_client", return_value=db), \
             patch("core.project_store.get_context", return_value={"id": "ctx-a", "tenant_id": "t1"}), \
             patch("core.project_store.list_contexts", return_value=[{"id": "ctx-a", "name": "Contexto Aurora"}]):
            ex = _executor()
            result = ex.pesquisar_multi_contexto("blockchain quantum")
        assert "nenhuma menção" in result.lower()

    def test_registered_in_dispatch_and_schema(self):
        from core.assistant_tools import get_tool_schemas_openai
        names = [s["function"]["name"] for s in get_tool_schemas_openai()]
        assert "pesquisar_multi_contexto" in names

    def test_not_admin_only(self):
        from core.assistant_tools import _ADMIN_TOOLS
        assert "pesquisar_multi_contexto" not in _ADMIN_TOOLS
