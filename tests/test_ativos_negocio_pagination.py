# tests/test_ativos_negocio_pagination.py
"""
NAV-09 (melhorias/parciais/navegabilidade.md, PC219): pages/AtivosDeNegocio.py
renderizava um st.expander() por item, para cada um dos 11 tipos de
artefato, sem nenhum limite — medido em produção: 79 mil caracteres numa
página só, 8,5s de carregamento. Fix: paginação via
ui/components/paginator.py (25 itens/página) por tipo de artefato — cada
tipo pagina independentemente, com sua própria assinatura de filtro
(inclui todos os filtros ativos: busca, contexto, interesse, perspectiva,
classificação, arquivados).
"""

from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

st.page_link = lambda *a, **k: None

_pid_counter = iter(range(1, 1000))


def _fake_requirement_items(n: int) -> list[dict]:
    return [
        {
            "id": f"req-{i}",
            "artifact_id": f"req-{i}",
            "title": f"Requisito Sintético {i:03d}",
            "context_name": "Projeto Teste",
            "context_id": "p1",
            "meeting_ref": "Reunião 1",
            "meeting_date": "2026-01-01",
            "has_metadata_support": True,
            "metadata": {
                "status": "ativo",
                "business_interest": "operacional",
                "business_perspective": [],
                "formal_classification": None,
                "promotion_justification": "",
                "tags": [],
                "owner": "",
                "notes": "",
            },
        }
        for i in range(n)
    ]


def _base_app(pid: str) -> AppTest:
    at = AppTest.from_file("pages/AtivosDeNegocio.py", default_timeout=60)
    at.session_state["_autenticado"] = True
    at.session_state["_usuario_login"] = "teste"
    at.session_state["_usuario_nome"] = "Teste"
    at.session_state["_role"] = "admin"
    at.session_state["active_project_id"] = pid
    at.session_state["active_project_name"] = "Projeto Teste"
    return at


def _run(pid: str, n_items: int = 40) -> AppTest:
    assets = {"requirement": _fake_requirement_items(n_items)}
    with patch("modules.supabase_client.supabase_configured", lambda: True), \
         patch("core.project_store.list_all_business_assets", lambda pid: assets):
        at = _base_app(pid)
        at.run()
    return at


class TestAtivosPaginationCapsRenderedExpanders:
    def test_40_items_render_at_most_25_expanders_on_first_page(self):
        pid = f"nav09-an-{next(_pid_counter)}"
        at = _run(pid)

        assert not at.exception
        item_expanders = [e for e in at.expander if "Requisito Sintético" in e.label]
        assert len(item_expanders) <= 25, (
            f"esperado no máximo 25 expanders por página, encontrados "
            f"{len(item_expanders)} — NAV-09 pode ter regredido"
        )

    def test_next_page_button_advances_without_repeating_first_item(self):
        pid = f"nav09-an-{next(_pid_counter)}"
        at = _run(pid)
        assert not at.exception
        item_expanders = [e for e in at.expander if "Requisito Sintético" in e.label]
        assert len(item_expanders) <= 25

        next_btn = [b for b in at.button if b.key == "an_requirement_next"]
        assert next_btn, "botão 'Próximo →' não encontrado — paginação ausente"
        next_btn[0].click().run()

        assert not at.exception
        item_expanders_p2 = [e for e in at.expander if "Requisito Sintético" in e.label]
        assert len(item_expanders_p2) <= 25
        labels_p2 = " ".join(e.label for e in item_expanders_p2)
        assert "Sintético 000" not in labels_p2
