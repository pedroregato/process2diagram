# tests/test_artefatos_provocations_tab.py
"""
Boot-smoke + interaction test for the "🎭 Provocações" tab in pages/Artefatos.py
(PC190, melhorias/arquivados/agente-de-provocacoes.md).

Real AppTest run (not a mocked function call) — exercises the actual page
script end to end: tab renders, default filter ("Novas") hides non-new
items, switching to "Todas" shows everything, and accept/discard buttons
only appear for status="new" items.
"""

from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

# Known project workaround (see tests/test_artefatos_sbvr_pagination.py,
# memory/engineering_notes): st.page_link("pages/Home.py", ...) can't resolve
# a sibling page when AppTest treats this file as the sole entrypoint.
st.page_link = lambda *a, **k: None


_FAKE_PROVOCATIONS = [
    {
        "id": "prov-1", "meeting_id": "m1", "project_id": "p1", "tenant_id": None,
        "kind": "asymmetry", "title": "Objeção não respondida",
        "body": "A objeção foi levantada e não recebeu resposta.",
        "question": "Foi considerada?",
        "grounding": {
            "type": "turns",
            "references": [
                {"timestamp": "00:01", "speaker": "João", "excerpt": "algo"},
                {"timestamp": "00:02", "speaker": "Ricardo", "excerpt": "outro"},
            ],
            "absence_check": {"terms": []},
        },
        "confidence": "high", "status": "new", "created_at": "2026-01-01T00:00:00Z",
    },
    {
        "id": "prov-2", "meeting_id": "m1", "project_id": "p1", "tenant_id": None,
        "kind": "absence", "title": "Multa não discutida",
        "body": "Nenhuma menção a penalidade por atraso.",
        "question": "Existe multa prevista?",
        "grounding": {"type": "absence", "references": [], "absence_check": {"terms": ["multa"]}},
        "confidence": "medium", "status": "accepted", "created_at": "2026-01-01T00:00:00Z",
    },
]


# Cada teste usa um project_id distinto e NAMESPACED (prefixo próprio, nunca
# "p1"/"p2" — os IDs curtos que outros arquivos de teste de Artefatos.py já
# usam) — pages/Artefatos.py envolve os loaders em @st.cache_data(ttl=...),
# que é um cache GLOBAL do processo, sobrevivendo entre AppTest.from_file()
# separados e entre ARQUIVOS de teste diferentes rodando na mesma sessão
# pytest. Reusar "p1" aqui colidiria com tests/test_artefatos_sbvr_pagination.py
# (mesmo pid hardcoded) — o teste daqui rodando primeiro (ordem alfabética:
# "provocations" < "sbvr") deixaria _load_sbvr_terms("p1")/_load_sbvr_rules("p1")
# cacheados como [] antes do outro arquivo rodar, mascarando o mock real dele.
# Descoberto ao rodar a suíte completa — passava isolado, falhava em conjunto.
_pid_counter = iter(range(1, 1000))


def _base_app(pid: str):
    at = AppTest.from_file("pages/Artefatos.py", default_timeout=60)
    at.session_state["_autenticado"] = True
    at.session_state["_usuario_login"] = "teste"
    at.session_state["_usuario_nome"] = "Teste"
    at.session_state["_role"] = "admin"
    at.session_state["active_project_id"] = pid
    at.session_state["active_project_name"] = "Projeto Teste"
    return at


def _run_with_mocks(provocations=None):
    pid = f"pc190-test-{next(_pid_counter)}"
    with patch("modules.supabase_client.supabase_configured", lambda: True), \
         patch("core.project_store.list_meetings", lambda pid: [
             {"id": "m1", "meeting_number": 1, "title": "R1", "meeting_date": "2026-01-01",
              "total_tokens": 0, "llm_provider": "x"}
         ]), \
         patch("core.project_store.list_requirements_light", lambda pid: []), \
         patch("core.project_store.list_contradictions", lambda pid: []), \
         patch("core.project_store.list_bpmn_processes", lambda pid: []), \
         patch("core.project_store.bpmn_tables_exist", lambda: False), \
         patch("core.project_store.get_asset_metadata_map", lambda pid: {}), \
         patch("core.project_store.list_sbvr_terms", lambda pid: []), \
         patch("core.project_store.list_sbvr_rules", lambda pid: []), \
         patch("core.project_store.list_provocations_by_project",
               lambda pid, status=None: provocations or []), \
         patch("modules.document_store.list_documents", lambda pid, **_: []):
        at = _base_app(pid)
        at.run()
    return at


class TestProvocationsTabBootSmoke:
    def test_renders_without_exception_when_empty(self):
        at = _run_with_mocks(provocations=[])
        assert not at.exception

    def test_renders_without_exception_with_data(self):
        at = _run_with_mocks(provocations=_FAKE_PROVOCATIONS)
        assert not at.exception

    def test_default_filter_shows_only_new(self):
        at = _run_with_mocks(provocations=_FAKE_PROVOCATIONS)
        labels = [e.label for e in at.expander]
        assert any("Objeção não respondida" in l for l in labels)
        assert not any("Multa não discutida" in l for l in labels)

    def test_switching_to_todas_shows_all(self):
        at = _run_with_mocks(provocations=_FAKE_PROVOCATIONS)
        radios = [r for r in at.radio if r.key == "prov_filter"]
        assert radios, "filtro de provocações não encontrado"
        radios[0].set_value("Todas").run()
        assert not at.exception
        labels = [e.label for e in at.expander]
        assert any("Objeção não respondida" in l for l in labels)
        assert any("Multa não discutida" in l for l in labels)

    def test_accept_discard_buttons_only_for_new_status(self):
        at = _run_with_mocks(provocations=_FAKE_PROVOCATIONS)
        radios = [r for r in at.radio if r.key == "prov_filter"]
        radios[0].set_value("Todas").run()
        accept_buttons = [b for b in at.button if b.key == "prov_acc_prov-1"]
        discard_buttons = [b for b in at.button if b.key == "prov_disc_prov-1"]
        assert accept_buttons and discard_buttons  # prov-1 is status="new"
        no_action_on_accepted = [b for b in at.button if "prov-2" in (b.key or "")]
        assert no_action_on_accepted == []  # prov-2 is status="accepted", no actions
