# tests/test_artefatos_debates_pagination.py
"""
NAV-09 (melhorias/parciais/navegabilidade.md, PC219): pages/ArtefatosDebates.py
(Debates/IBIS) renderizava um st.expander() por questão na visualização
"📋 Lista" sem limite — medido em produção: 177 expanders, 52 mil
caracteres, 16,6s de carregamento. Mesma classe de incidente já corrigida
2x (PC178 SBVR, PC212/NAV-03 Validação).

Fix: paginação via ui/components/paginator.py (25 itens/página) na lista de
questões filtradas — o mapa visual pyvis (outro modo de visualização,
alternável por st.radio) continua mostrando o conjunto filtrado inteiro,
sem paginação (é uma renderização única, não um loop de widgets por item).

Este teste pré-popula st.session_state com o cache lazy-load da página
(ibis_session_key) — evita ter que simular o rerun interno de carregamento
sob demanda (linha "if _IBIS_SS not in st.session_state: ... st.rerun()").
"""

from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

st.page_link = lambda *a, **k: None

_PS = "ui.artefatos_shared"
_pid_counter = iter(range(1, 1000))


def _fake_questions(n: int) -> list[dict]:
    return [
        {
            "id": f"Q{i:03d}",
            "statement": f"Questão sintética número {i}",
            "raised_by": "Ana",
            "alternatives": [],
            "resolution": {"type": "unresolved"},
            "_meeting_number": 1,
            "_meeting_id": "m1",
        }
        for i in range(n)
    ]


def _base_app(pid: str) -> AppTest:
    at = AppTest.from_file("pages/ArtefatosDebates.py", default_timeout=60)
    at.session_state["_autenticado"] = True
    at.session_state["_usuario_login"] = "teste"
    at.session_state["_usuario_nome"] = "Teste"
    at.session_state["_role"] = "admin"
    at.session_state["active_project_id"] = pid
    at.session_state["active_project_name"] = "Projeto Teste"
    at.session_state[f"_art_ibis_{pid}"] = _fake_questions(60)
    return at


class TestDebatesListPaginationCapsRenderedExpanders:
    def test_60_questions_render_at_most_25_expanders_on_first_page(self):
        pid = f"nav09-ibis-{next(_pid_counter)}"
        with patch("modules.supabase_client.supabase_configured", lambda: True), \
             patch(f"{_PS}.list_meetings", lambda pid: []):
            at = _base_app(pid)
            at.run()

        assert not at.exception
        q_expanders = [e for e in at.expander if "Questão sintética" in e.label]
        assert len(q_expanders) <= 25, (
            f"esperado no máximo 25 expanders de questão por página, "
            f"encontrados {len(q_expanders)} — NAV-09 pode ter regredido"
        )

    def test_next_page_button_advances_without_repeating_first_item(self):
        pid = f"nav09-ibis-{next(_pid_counter)}"
        with patch("modules.supabase_client.supabase_configured", lambda: True), \
             patch(f"{_PS}.list_meetings", lambda pid: []):
            at = _base_app(pid)
            at.run()
            assert not at.exception
            q_expanders = [e for e in at.expander if "Questão sintética" in e.label]
            assert len(q_expanders) <= 25

            next_btn = [b for b in at.button if b.key == "ibis_list_next"]
            assert next_btn, "botão 'Próximo →' não encontrado — paginação ausente"
            next_btn[0].click().run()

        assert not at.exception
        q_expanders_p2 = [e for e in at.expander if "Questão sintética" in e.label]
        assert len(q_expanders_p2) <= 25
        labels_p2 = " ".join(e.label for e in q_expanders_p2)
        assert "número 0 " not in labels_p2 and "Q000" not in labels_p2
