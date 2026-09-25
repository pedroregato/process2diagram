# tests/test_knowledge_hub_pagination.py
"""
NAV-09 (melhorias/parciais/navegabilidade.md, PC219): pages/KnowledgeHub.py
usava st.tabs() pras 5 seções (Entidades/Processos/Fatos/Contradições/
Análises), cada uma com um loop de itens sem paginação — medido em
produção: 310 botões, 80 expanders, 6,7s de carregamento (soma das 5 abas
sempre renderizando juntas, cada uma sem limite de itens).

Fix: st.radio(horizontal=True) no lugar de st.tabs() (só a seção ativa
executa) + paginação via ui/components/paginator.py em cada um dos 5
loops.
"""

from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

st.page_link = lambda *a, **k: None

_pid_counter = iter(range(1, 1000))


def _fake_entities(n: int) -> list[dict]:
    return [
        {
            "entity_type": "person",
            "canonical_name": f"Entidade Sintética {i:03d}",
            "aliases": [],
            "occurrence_count": 1,
        }
        for i in range(n)
    ]


def _fake_contradictions(n: int) -> list[dict]:
    return [
        {
            "id": f"c{i}",
            "severity": "medium",
            "status": "open",
            "relation_type": "contradiction_direct",
            "confidence": 0.9,
            "process_name": None,
            "description": f"Contradição sintética número {i}",
            "clarifying_question": None,
            "suggested_rewrite": None,
        }
        for i in range(n)
    ]


def _base_app(pid: str) -> AppTest:
    at = AppTest.from_file("pages/KnowledgeHub.py", default_timeout=60)
    at.session_state["_autenticado"] = True
    at.session_state["_usuario_login"] = "teste"
    at.session_state["_usuario_nome"] = "Teste"
    at.session_state["_role"] = "user"  # não-admin: sem os botões extras de Full Scan/consolidação
    at.session_state["active_project_id"] = pid
    at.session_state["active_project_name"] = "Projeto Teste"
    return at


class TestEntitiesSectionPagination:
    def test_60_entities_render_at_most_25_on_first_page(self):
        pid = f"nav09-kh-{next(_pid_counter)}"
        with patch("modules.supabase_client.supabase_configured", lambda: True), \
             patch("core.knowledge_store.kh_tables_exist", lambda: True), \
             patch("core.knowledge_store.get_entities", lambda pid, entity_type=None, limit=200: _fake_entities(60)):
            at = _base_app(pid)
            at.run()

        assert not at.exception
        radio = [r for r in at.radio if r.key == "kh_view"]
        assert radio and radio[0].value == "👥 Entidades"
        names = [m.value for m in at.markdown if "Entidade Sintética" in m.value]
        assert len(names) <= 25, (
            f"esperado no máximo 25 entidades por página, encontradas {len(names)}"
        )

    def test_other_sections_do_not_render_with_entities_selected(self):
        pid = f"nav09-kh-{next(_pid_counter)}"
        with patch("modules.supabase_client.supabase_configured", lambda: True), \
             patch("core.knowledge_store.kh_tables_exist", lambda: True), \
             patch("core.knowledge_store.get_entities", lambda pid, entity_type=None, limit=200: []), \
             patch("core.knowledge_store.get_contradictions", lambda *a, **k: _fake_contradictions(60)):
            at = _base_app(pid)
            at.run()

        assert not at.exception
        # Descrição da seção Contradições não deve aparecer com Entidades ativa
        # — st.tabs() voltaria a renderizar tudo junto.
        text = " ".join(m.value for m in at.markdown)
        assert "Contradições detectadas automaticamente" not in text


class TestContradictionsSectionPagination:
    def _run(self, pid: str):
        with patch("modules.supabase_client.supabase_configured", lambda: True), \
             patch("core.knowledge_store.kh_tables_exist", lambda: True), \
             patch("core.knowledge_store.get_entities", lambda pid, entity_type=None, limit=200: []), \
             patch("core.knowledge_store.get_contradictions", lambda *a, **k: _fake_contradictions(60)):
            at = _base_app(pid)
            at.run()
            radio = [r for r in at.radio if r.key == "kh_view"]
            radio[0].set_value("⚠️ Contradições").run()
        return at

    def test_60_contradictions_render_at_most_25_descriptions_on_first_page(self):
        pid = f"nav09-kh-{next(_pid_counter)}"
        at = self._run(pid)

        assert not at.exception
        descs = [m.value for m in at.markdown if "Contradição sintética número" in m.value]
        assert len(descs) <= 25, (
            f"esperado no máximo 25 contradições por página, encontradas {len(descs)} "
            "— cada uma com 2 botões (✅/🚫), o principal contribuinte pros "
            "310 botões medidos em produção"
        )

    def test_next_page_button_advances_without_repeating_first_item(self):
        pid = f"nav09-kh-{next(_pid_counter)}"
        at = self._run(pid)
        assert not at.exception

        next_btn = [b for b in at.button if b.key == "kh_contra_next"]
        assert next_btn, "botão 'Próximo →' não encontrado — paginação ausente"
        next_btn[0].click().run()

        assert not at.exception
        descs_p2 = [m.value for m in at.markdown if "Contradição sintética número" in m.value]
        assert len(descs_p2) <= 25
        assert not any("número 0\n" in d or d.endswith("número 0") for d in descs_p2)
