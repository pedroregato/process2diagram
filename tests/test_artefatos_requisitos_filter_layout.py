# tests/test_artefatos_requisitos_filter_layout.py
"""
UX-03 (melhorias/ux-amigabilidade-e-elegancia.md): a aba "Requisitos" de
pages/ArtefatosRequisitos.py tinha 5 filtros (Status/Tipo/Prioridade/
Origem/Buscar) numa linha só (st.columns(5)) — em ~840px (sidebar aberta)
cada selectbox ficava espremido demais.

Fix: quebrado em 2 linhas — st.columns(3) (Status/Tipo/Prioridade) +
st.columns(2) (Origem/Buscar). Mesmas keys/comportamento de filtro, só a
disposição visual muda.

O smoke test existente (tests/test_artefatos_pages_boot_smoke.py) semeia
requirements=[] — cai no branch "Nenhum requisito registrado", nunca
alcança o bloco de filtros. Este arquivo semeia dados reais pra exercitar
o código de fato alterado.
"""

from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

st.page_link = lambda *a, **k: None

_PS = "ui.artefatos_shared"

_REQS = [
    {"id": "r1", "req_number": 1, "title": "Login com SSO", "req_type": "funcional",
     "priority": "high", "status": "active", "origin": "transcricao",
     "first_meeting_id": "m1"},
    {"id": "r2", "req_number": 2, "title": "Auditoria de acesso", "req_type": "regra_negocio",
     "priority": "medium", "status": "backlog", "origin": "documento",
     "first_meeting_id": "m1"},
]


def _base_app() -> AppTest:
    at = AppTest.from_file("pages/ArtefatosRequisitos.py", default_timeout=60)
    at.session_state["_autenticado"] = True
    at.session_state["_usuario_login"] = "teste"
    at.session_state["_usuario_nome"] = "Teste"
    at.session_state["_role"] = "admin"
    at.session_state["active_project_id"] = "ux03-req-filters"
    at.session_state["active_project_name"] = "Projeto Teste"
    return at


def _patched(**overrides):
    base = dict(
        supabase_configured=lambda: True,
        list_meetings=lambda pid: [],
        list_requirements_light=lambda pid: _REQS,
        list_contradictions=lambda pid: [],
        list_documents=lambda pid, **_: [],
        get_asset_metadata_map=lambda pid: {},
    )
    base.update(overrides)
    return [
        patch("modules.supabase_client.supabase_configured", base["supabase_configured"]),
        patch(f"{_PS}.list_meetings", base["list_meetings"]),
        patch(f"{_PS}.list_requirements_light", base["list_requirements_light"]),
        patch(f"{_PS}.list_contradictions", base["list_contradictions"]),
        patch(f"{_PS}.list_documents", base["list_documents"]),
        patch(f"{_PS}.get_asset_metadata_map", base["get_asset_metadata_map"]),
    ]


class TestFilterRowSplitIntoTwoLines:
    def test_five_filters_render_across_two_rows_not_one(self):
        patches = _patched()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            at = _base_app()
            at.run()
        assert not at.exception

        selectboxes_by_key = {sb.key: sb for sb in at.selectbox}
        for key in ("rt_status", "rt_type", "rt_prio", "rt_origin"):
            assert key in selectboxes_by_key, f"filtro {key} não encontrado"
        assert any(ti.key == "rt_search" for ti in at.text_input)

        # Confirma via weight de coluna (1/3 pros 3 primeiros, 1/2 pros 2
        # últimos) que são DUAS chamadas a st.columns(), não uma de 5.
        weights = [round(c.weight, 4) for c in at.columns if c.weight]
        n_third = sum(1 for w in weights if abs(w - 1 / 3) < 1e-3)
        n_half = sum(1 for w in weights if abs(w - 1 / 2) < 1e-3)
        assert n_third >= 3, f"esperava >=3 colunas de peso 1/3 (linha de 3), achou {n_third}"
        assert n_half >= 2, f"esperava >=2 colunas de peso 1/2 (linha de 2), achou {n_half}"


class TestFiltersStillFilterCorrectly:
    def test_status_filter_narrows_results(self):
        patches = _patched()
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            at = _base_app()
            at.run()
            status_sb = next(sb for sb in at.selectbox if sb.key == "rt_status")
            status_sb.select("active").run()
        assert not at.exception

        titles = " ".join(m.value for m in at.markdown)
        assert "Login com SSO" in titles
        assert "Auditoria de acesso" not in titles
