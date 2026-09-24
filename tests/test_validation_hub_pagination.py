# tests/test_validation_hub_pagination.py
"""
NAV-03 (melhorias/parciais/navegabilidade.md, PC212): pages/ValidationHub.py
renderizava todos os artefatos pendentes/concluídos de uma vez, com 3 botões
de ação por item. Em produção, um contexto com 2.252 artefatos gerou cerca de
2.490 botões — a página levou 42s e derrubou a sessão (mesma classe de
incidente do PC178, já corrigido para a paginação SBVR de
pages/ArtefatosModelagem.py).

Fix: filtro de status padrão passa a ser "Pendentes" (era "Todos"); as 4 abas
de artefato (Requisitos/Termos/Regras/BPMN) paginam a 25 itens por página
(seletor 25/50/100, navegação Anterior/Próximo, estado em
session_state["vh_page_<aba>"]); os 3 botões por item (Validar/Em Revisão/
Rejeitar) foram substituídos por um st.data_editor com coluna Status editável
por página + um botão "Salvar alterações" que grava só as linhas alteradas
(delta via `edited_rows`); os KPIs do topo passam a vir de
core.project_store.count_validation_status() (count="exact" agregado no
Supabase), não mais de len() sobre as listas completas carregadas para
renderizar a página.

Este teste semeia 60 requisitos sintéticos e confere: (1) o filtro de status
abre em "Pendentes"; (2) no máximo 25 cards de requisito são renderizados por
página; (3) o botão "Próximo" avança a página sem estourar o limite e sem
repetir o item da primeira página.
"""

from contextlib import contextmanager
from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

# Mesmo workaround usado em test_artefatos_sbvr_pagination.py: AppTest.from_file()
# roda a página fora da navegação multi-página de app.py — st.page_link() para
# uma página irmã não resolve nesse contexto e levanta StreamlitPageNotFoundError.
st.page_link = lambda *a, **k: None

_PS = "core.project_store"

# pages/ValidationHub.py envolve os loaders em @st.cache_data(ttl=60) — cache
# GLOBAL do processo, sobrevivendo entre AppTest.from_file() separados e entre
# arquivos de teste diferentes rodando na mesma sessão pytest (mesma armadilha
# documentada em tests/test_artefatos_provocations_tab.py). Reusar "p1" aqui
# colidiria com outros arquivos que já usam esse pid — cada teste precisa de
# um project_id próprio, nunca hardcoded.
_pid_counter = iter(range(1, 1000))


def _fake_reqs(n: int) -> list[dict]:
    return [
        {
            "id": f"req-{i}",
            "req_number": i,
            "title": f"Requisito Sintético {i:03d}",
            "description": f"Descrição do requisito {i}",
            "req_type": "functional",
            "priority": "medium",
            "validation_status": "proposto",
            "validation_notes": None,
            "cited_by": None,
            "source_quote": None,
            "first_meeting_id": None,
        }
        for i in range(n)
    ]


def _base_app(pid: str):
    at = AppTest.from_file("pages/ValidationHub.py", default_timeout=30)
    at.session_state["_autenticado"] = True
    at.session_state["_usuario_login"] = "teste"
    at.session_state["_usuario_nome"] = "Teste"
    at.session_state["_role"] = "admin"
    at.session_state["active_project_id"] = pid
    at.session_state["active_project_name"] = "Projeto Teste"
    return at


_PATCH_EMPTY = dict(
    list_meetings=lambda pid: [],
    list_meetings_quality=lambda pid: [],
    list_dmn_by_project=lambda pid: [],
    list_sbvr_terms=lambda pid: [],
    list_sbvr_rules=lambda pid: [],
    list_bpmn_processes=lambda pid: [],
    count_validation_status=lambda pid: {
        "proposto": 60, "em_revisão": 0, "validado": 0, "ajustado": 0, "rejeitado": 0,
    },
)


@contextmanager
def _patched_reqs_env():
    """Mocks ativos durante todo o teste — necessário para reruns disparados
    por cliques (ex.: paginação), que também re-executam a página inteira e
    portanto os imports/consultas do NAV-03."""
    with patch("modules.supabase_client.supabase_configured", lambda: True), \
         patch(f"{_PS}.list_requirements_light", lambda p: _fake_reqs(60)), \
         patch(f"{_PS}.list_meetings", _PATCH_EMPTY["list_meetings"]), \
         patch(f"{_PS}.list_meetings_quality", _PATCH_EMPTY["list_meetings_quality"]), \
         patch(f"{_PS}.list_dmn_by_project", _PATCH_EMPTY["list_dmn_by_project"]), \
         patch(f"{_PS}.list_sbvr_terms", _PATCH_EMPTY["list_sbvr_terms"]), \
         patch(f"{_PS}.list_sbvr_rules", _PATCH_EMPTY["list_sbvr_rules"]), \
         patch(f"{_PS}.list_bpmn_processes", _PATCH_EMPTY["list_bpmn_processes"]), \
         patch(f"{_PS}.count_validation_status", _PATCH_EMPTY["count_validation_status"]):
        yield


def _run_with_60_reqs() -> AppTest:
    pid = f"nav03-test-{next(_pid_counter)}"
    with _patched_reqs_env():
        at = _base_app(pid)
        at.run()
    return at


class TestValidationHubDefaultFilterIsPendentes:
    def test_status_filter_selectbox_defaults_to_pendentes(self):
        at = _run_with_60_reqs()
        assert not at.exception
        filtro = [sb for sb in at.selectbox if sb.key == "vhub_filter"]
        assert filtro, "seletor de filtro de status não encontrado"
        assert filtro[0].value == "Pendentes"


class TestValidationHubPaginationCapsRenderedCards:
    def test_60_requirements_render_at_most_25_cards_on_first_page(self):
        at = _run_with_60_reqs()
        assert not at.exception
        req_cards = [m for m in at.markdown if "Requisito Sintético" in m.value]
        assert len(req_cards) <= 25, (
            f"esperado no máximo 25 cards de requisito por página, "
            f"encontrados {len(req_cards)} — NAV-03 pode ter regredido"
        )

    def test_next_page_button_advances_without_repeating_first_item(self):
        pid = f"nav03-test-{next(_pid_counter)}"
        with _patched_reqs_env():
            at = _base_app(pid)
            at.run()
            assert not at.exception
            req_cards = [m for m in at.markdown if "Requisito Sintético" in m.value]
            assert len(req_cards) <= 25

            next_btn = [b for b in at.button if b.key == "req_next"]
            assert next_btn, "botão 'Próximo →' não encontrado — controles de paginação ausentes"
            next_btn[0].click().run()

        assert not at.exception
        req_cards_p2 = [m for m in at.markdown if "Requisito Sintético" in m.value]
        assert len(req_cards_p2) <= 25
        labels_p2 = " ".join(m.value for m in req_cards_p2)
        assert "Sintético 000" not in labels_p2
