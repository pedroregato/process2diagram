# tests/test_artefatos_sbvr_pagination.py
"""
Regression test for SBVR pagination in pages/Artefatos.py (PC178).

Production incident: a context with 751 SBVR terms + 502 SBVR rules made
Artefatos.py render 1253 st.expander() widgets (each with a nested
render_promote_button()) unconditionally on every page load — st.tabs()
executes the body of every tab on every rerun regardless of which tab is
visible, so this happened even when the user wasn't looking at the SBVR
tab. Correlated with intermittent backend crashes (segfault) and frontend
"Bad 'setIn' index" errors in that account.

Fix: SBVR Termos and Regras columns now paginate at 25 items/page each,
mirroring the pattern already used in the Requisitos tab. This test seeds
60 synthetic terms/rules and asserts only <= 25 expanders render per
column, with working Anterior/Próximo navigation.
"""

from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

# AppTest.from_file() runs a single page outside app.py's multi-page nav —
# st.page_link("pages/Home.py", ...) can't resolve a sibling page in that
# context and raises StreamlitPageNotFoundError. Known project workaround
# (see memory/engineering notes): no-op it for tests.
st.page_link = lambda *a, **k: None


def _fake_terms(n):
    return [
        {
            "id": f"term-{i}",
            "term": f"Termo Sintético {i:03d}",
            "definition": f"Definição do termo {i}",
            "category": "concept",
            "origin": "transcricao",
            "meeting_id": None,
            "meetings": {},
        }
        for i in range(n)
    ]


def _fake_rules(n):
    return [
        {
            "id": f"rule-{i}",
            "rule_id": f"BR-{i:03d}",
            "statement": f"Regra sintética número {i}",
            "rule_type": "operational",
            "origin": "transcricao",
            "meeting_id": None,
            "meetings": {},
            "nucleo_nominal": None,
            "source": None,
        }
        for i in range(n)
    ]


def _base_app():
    at = AppTest.from_file("pages/Artefatos.py", default_timeout=30)
    # is_authenticated() (modules/auth.py) checks _autenticado, not
    # "authenticated" — a wrong key here silently renders the login page
    # instead of the target page, and boot-smoke checks trivially "pass"
    # against the login page's own markup.
    at.session_state["_autenticado"] = True
    at.session_state["_usuario_login"] = "teste"
    at.session_state["_usuario_nome"] = "Teste"
    at.session_state["_role"] = "admin"
    at.session_state["active_project_id"] = "p1"
    at.session_state["active_project_name"] = "Projeto Teste"
    return at


_PATCH_TARGETS = dict(
    supabase_configured=lambda: True,
    list_meetings=lambda pid: [],
    list_requirements_light=lambda pid: [],
    list_contradictions=lambda pid: [],
    list_bpmn_processes=lambda pid: [],
    bpmn_tables_exist=lambda: False,
    get_asset_metadata_map=lambda pid: {},
    list_documents=lambda pid, **_: [],
)


class TestSbvrPaginationCapsRenderedExpanders:
    def test_60_terms_and_60_rules_render_at_most_25_expanders_each(self):
        with patch("modules.supabase_client.supabase_configured", _PATCH_TARGETS["supabase_configured"]), \
             patch("core.project_store.list_meetings", _PATCH_TARGETS["list_meetings"]), \
             patch("core.project_store.list_requirements_light", _PATCH_TARGETS["list_requirements_light"]), \
             patch("core.project_store.list_contradictions", _PATCH_TARGETS["list_contradictions"]), \
             patch("core.project_store.list_bpmn_processes", _PATCH_TARGETS["list_bpmn_processes"]), \
             patch("core.project_store.bpmn_tables_exist", _PATCH_TARGETS["bpmn_tables_exist"]), \
             patch("core.project_store.get_asset_metadata_map", _PATCH_TARGETS["get_asset_metadata_map"]), \
             patch("core.project_store.list_sbvr_terms", lambda pid: _fake_terms(60)), \
             patch("core.project_store.list_sbvr_rules", lambda pid: _fake_rules(60)), \
             patch("modules.document_store.list_documents", _PATCH_TARGETS["list_documents"]):
            at = _base_app()
            at.run()

        assert not at.exception
        # SBVR expanders share the tree with other tabs' static expanders
        # (📦 Exportar Relatório, 🔍 Diagnóstico DMN — always present
        # regardless of data, since all tab bodies execute every rerun) —
        # isolate just the term/rule expanders by label to check the cap.
        term_expanders = [e for e in at.expander if "Sintético" in e.label]
        rule_expanders = [e for e in at.expander if e.label.startswith("**BR-")]
        assert len(term_expanders) <= 25, (
            f"expected pagination to cap terms at 25, got {len(term_expanders)} "
            "— SBVR Termos may be rendering unpaginated again"
        )
        assert len(rule_expanders) <= 25, (
            f"expected pagination to cap rules at 25, got {len(rule_expanders)} "
            "— SBVR Regras may be rendering unpaginated again"
        )

    def test_next_page_button_advances_without_exceeding_page_size(self):
        with patch("modules.supabase_client.supabase_configured", _PATCH_TARGETS["supabase_configured"]), \
             patch("core.project_store.list_meetings", _PATCH_TARGETS["list_meetings"]), \
             patch("core.project_store.list_requirements_light", _PATCH_TARGETS["list_requirements_light"]), \
             patch("core.project_store.list_contradictions", _PATCH_TARGETS["list_contradictions"]), \
             patch("core.project_store.list_bpmn_processes", _PATCH_TARGETS["list_bpmn_processes"]), \
             patch("core.project_store.bpmn_tables_exist", _PATCH_TARGETS["bpmn_tables_exist"]), \
             patch("core.project_store.get_asset_metadata_map", _PATCH_TARGETS["get_asset_metadata_map"]), \
             patch("core.project_store.list_sbvr_terms", lambda pid: _fake_terms(60)), \
             patch("core.project_store.list_sbvr_rules", lambda pid: _fake_rules(0)), \
             patch("modules.document_store.list_documents", _PATCH_TARGETS["list_documents"]):
            at = _base_app()
            at.run()
            assert not at.exception
            term_expanders = [e for e in at.expander if "Sintético" in e.label]
            assert len(term_expanders) <= 25

            next_btn = [b for b in at.button if b.key == "sbvr_t_next"]
            assert next_btn, "Próximo button not found — pagination controls missing"
            next_btn[0].click().run()

        assert not at.exception
        term_expanders = [e for e in at.expander if "Sintético" in e.label]
        assert len(term_expanders) <= 25
        # Page 2 (items 26-50) should NOT contain term 000 (page 1 only)
        expander_labels = " ".join(e.label for e in at.expander)
        assert "Sintético 000" not in expander_labels
