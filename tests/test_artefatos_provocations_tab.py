# tests/test_artefatos_provocations_tab.py
"""
Boot-smoke + interaction test for the "🎭 Provocações" tab in
pages/ArtefatosQualidade.py
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

# PC208: os loaders/cached-loaders foram movidos de pages/Artefatos.py para
# ui/artefatos_shared.py (import compartilhado por todas as 6 páginas da
# seção). unittest.mock.patch precisa mirar o namespace onde o NOME é
# procurado em tempo de chamada — que agora é ui.artefatos_shared, não mais
# core.project_store (from-import não repassa patches feitos na origem depois
# que o módulo compartilhado já foi importado uma vez no processo).
_PS = "ui.artefatos_shared"


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
    {
        # kind="contradiction" — bridge determinístico a partir de
        # kh_contradictions (AgentProvocations.bridge_contradictions), sem
        # citação transcript-literal; grounding tem forma diferente das
        # outras 2 kinds (meeting_a_id/meeting_b_id/relation_type).
        "id": "prov-3", "meeting_id": "m1", "project_id": "p1", "tenant_id": None,
        "kind": "contradiction", "title": "Catálogo Mestre",
        "body": "Reunião 1 decidiu X; Reunião 2 decidiu o oposto.",
        "question": "Qual decisão vale?",
        "grounding": {
            "type": "contradiction_bridge",
            "source_contradiction_id": "kh-1",
            "meeting_a_id": "m1", "meeting_b_id": "m2",
            "relation_type": "contradiction_direct",
            "suggested_rewrite": "Consolidar a decisão da Reunião 2.",
        },
        "confidence": "high", "status": "new", "created_at": "2026-01-01T00:00:00Z",
    },
    {
        # kind="premise" (PC201) — citações literais como asymmetry, mas sem
        # absence_check; ganha premise_markers em vez de termos ausentes.
        "id": "prov-4", "meeting_id": "m1", "project_id": "p1", "tenant_id": None,
        "kind": "premise", "title": "Localização assumida sem debate",
        "body": "Afirmação categórica seguida de mudança de assunto, sem questionamento.",
        "question": "Isso já estava decidido antes?",
        "grounding": {
            "type": "premise",
            "references": [
                {"timestamp": "00:14", "speaker": "Pedro", "excerpt": "é claro que fica assim"},
                {"timestamp": "00:15", "speaker": "Ana", "excerpt": "próximo item"},
            ],
            "premise_markers": ["é claro que"],
        },
        "confidence": "high", "status": "new", "created_at": "2026-01-01T00:00:00Z",
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
    at = AppTest.from_file("pages/ArtefatosQualidade.py", default_timeout=60)
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
         patch(f"{_PS}.list_meetings", lambda pid: [
             {"id": "m1", "meeting_number": 1, "title": "R1", "meeting_date": "2026-01-01",
              "total_tokens": 0, "llm_provider": "x"},
             {"id": "m2", "meeting_number": 2, "title": "R2", "meeting_date": "2026-01-02",
              "total_tokens": 0, "llm_provider": "x"},
         ]), \
         patch(f"{_PS}.list_provocations_by_project",
               lambda pid, status=None: provocations or []), \
         patch(f"{_PS}.list_communication_noise_by_project", lambda pid: []):
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


class TestContradictionKindRendering:
    """kind='contradiction' (bridge) tem um formato de grounding diferente
    das outras 2 kinds — sem citação transcript-literal, referencia
    meeting_a_id/meeting_b_id/relation_type. Confere que a aba não quebra e
    que o branch de renderização novo aparece."""

    def test_renders_without_exception(self):
        at = _run_with_mocks(provocations=_FAKE_PROVOCATIONS)
        assert not at.exception

    def test_kind_label_and_meeting_reference_shown(self):
        at = _run_with_mocks(provocations=_FAKE_PROVOCATIONS)
        radios = [r for r in at.radio if r.key == "prov_filter"]
        radios[0].set_value("Todas").run()
        assert not at.exception
        labels = [e.label for e in at.expander]
        assert any("Catálogo Mestre" in l for l in labels)

        captions = " ".join(c.value for c in at.caption)
        assert "Reunião 1" in captions and "Reunião 2" in captions
        assert "contradiction_direct" in captions

        markdowns = " ".join(m.value for m in at.markdown)
        assert "Consolidar a decisão da Reunião 2." in markdowns


class TestPremiseKindRendering:
    """kind='premise' (PC201) reusa o bloco de citações de absence/asymmetry
    (references já renderiza igual), mas troca 'termos ausentes' por
    premise_markers — confere que aparece sem quebrar."""

    def test_renders_without_exception(self):
        at = _run_with_mocks(provocations=_FAKE_PROVOCATIONS)
        assert not at.exception

    def test_markers_and_references_shown(self):
        at = _run_with_mocks(provocations=_FAKE_PROVOCATIONS)
        radios = [r for r in at.radio if r.key == "prov_filter"]
        radios[0].set_value("Todas").run()
        assert not at.exception
        labels = [e.label for e in at.expander]
        assert any("Localização assumida sem debate" in l for l in labels)

        captions = " ".join(c.value for c in at.caption)
        assert "é claro que" in captions

        markdowns = " ".join(m.value for m in at.markdown)
        assert "é claro que fica assim" in markdowns
