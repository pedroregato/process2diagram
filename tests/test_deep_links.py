# tests/test_deep_links.py
"""
NAV-12 (melhorias/parciais/navegabilidade.md): deep links entre páginas via
?ctx=&meeting=&process=&v= (compartilháveis/favoritáveis) + session_state
"_pending_*" (navegação dentro da mesma sessão via st.switch_page, usado
pelos cards de "Reuniões recentes" da Central).

Testes unitários puros sobre ui/components/deep_links.py — st.query_params
e st.session_state funcionam em "modo bare" (fora de um ScriptRunContext
real, como confirmado manualmente: aceitam leitura/escrita normalmente,
só emitem warnings). core.project_store.list_contexts e
ui.project_selector.activate_context são mockados via monkeypatch — sem
tocar Supabase de verdade.
"""

import streamlit as st

from ui.components.deep_links import (
    resolve_context_from_query_params,
    get_query_param_int,
    get_query_param_str,
    pop_pending,
    active_context_sigla,
)


def _clear_query_params():
    for k in list(st.query_params.keys()):
        del st.query_params[k]


def _clear_session_state():
    for k in list(st.session_state.keys()):
        del st.session_state[k]


class TestResolveContextFromQueryParams:
    def setup_method(self):
        _clear_query_params()
        _clear_session_state()

    def test_no_ctx_param_is_a_noop(self, monkeypatch):
        called = {"list_contexts": False}

        def _fake_list_contexts(tenant_id=None):
            called["list_contexts"] = True
            return []

        monkeypatch.setattr("core.project_store.list_contexts", _fake_list_contexts)
        resolve_context_from_query_params()
        assert called["list_contexts"] is False
        assert "active_project_id" not in st.session_state

    def test_matching_sigla_in_tenant_activates_context(self, monkeypatch):
        st.query_params["ctx"] = "sdea"
        st.session_state["_tenant_id"] = "tenant-1"

        activated = {}

        def _fake_list_contexts(tenant_id=None):
            assert tenant_id == "tenant-1"
            return [{"id": "ctx-1", "name": "SDEA Contexto", "sigla": "SDEA"}]

        def _fake_activate_context(ctx):
            activated["ctx"] = ctx

        monkeypatch.setattr("core.project_store.list_contexts", _fake_list_contexts)
        monkeypatch.setattr("ui.project_selector.activate_context", _fake_activate_context)

        resolve_context_from_query_params()

        assert activated["ctx"]["id"] == "ctx-1"

    def test_sigla_not_found_in_tenant_is_ignored_and_logged(self, monkeypatch, caplog):
        st.query_params["ctx"] = "OUTRO-TENANT"
        st.session_state["_tenant_id"] = "tenant-1"

        activated = {"called": False}

        def _fake_list_contexts(tenant_id=None):
            # Sigla pertence a outro tenant — nunca aparece na lista do
            # tenant atual (reforça NAV-01: isolamento por tenant).
            return [{"id": "ctx-1", "name": "SDEA Contexto", "sigla": "SDEA"}]

        def _fake_activate_context(ctx):
            activated["called"] = True

        monkeypatch.setattr("core.project_store.list_contexts", _fake_list_contexts)
        monkeypatch.setattr("ui.project_selector.activate_context", _fake_activate_context)

        import logging
        with caplog.at_level(logging.WARNING):
            resolve_context_from_query_params()

        assert activated["called"] is False
        assert "active_project_id" not in st.session_state
        assert any("NAV-12" in r.message for r in caplog.records)

    def test_already_active_context_is_not_reactivated(self, monkeypatch):
        st.query_params["ctx"] = "SDEA"
        st.session_state["_tenant_id"] = "tenant-1"
        st.session_state["active_project_id"] = "ctx-1"

        activated = {"called": False}

        def _fake_list_contexts(tenant_id=None):
            return [{"id": "ctx-1", "name": "SDEA Contexto", "sigla": "SDEA"}]

        def _fake_activate_context(ctx):
            activated["called"] = True

        monkeypatch.setattr("core.project_store.list_contexts", _fake_list_contexts)
        monkeypatch.setattr("ui.project_selector.activate_context", _fake_activate_context)

        resolve_context_from_query_params()

        assert activated["called"] is False


class TestQueryParamHelpers:
    def setup_method(self):
        _clear_query_params()

    def test_get_query_param_int_parses_valid_int(self):
        st.query_params["meeting"] = "12"
        assert get_query_param_int("meeting") == 12

    def test_get_query_param_int_returns_none_when_absent(self):
        assert get_query_param_int("meeting") is None

    def test_get_query_param_int_returns_none_when_non_numeric(self):
        st.query_params["meeting"] = "abc"
        assert get_query_param_int("meeting") is None

    def test_get_query_param_str_returns_none_when_absent(self):
        assert get_query_param_str("process") is None

    def test_get_query_param_str_returns_value(self):
        st.query_params["process"] = "abc-123"
        assert get_query_param_str("process") == "abc-123"


class TestPendingSessionState:
    def setup_method(self):
        _clear_session_state()

    def test_pop_pending_returns_and_clears_value(self):
        st.session_state["_pending_meeting_number"] = 12
        assert pop_pending("meeting_number") == 12
        assert "_pending_meeting_number" not in st.session_state

    def test_pop_pending_returns_none_when_absent(self):
        assert pop_pending("meeting_number") is None


class TestActiveContextSigla:
    def setup_method(self):
        _clear_session_state()

    def test_returns_sigla_without_trailing_underscore(self):
        st.session_state["prefix"] = "SDEA_"
        assert active_context_sigla() == "SDEA"

    def test_returns_empty_string_when_no_prefix_set(self):
        assert active_context_sigla() == ""
