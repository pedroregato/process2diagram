# tests/test_knowledge_graph_truncation.py
"""
NAV-15 (melhorias/parciais/navegabilidade.md): pages/KnowledgeGraph.py
carrega entidades/processos/fatos/contradições com .limit(150/50/300/50)
direto na query, sem nenhum indicador de corte — um contexto com mais
dados do que o teto mostrava "150 entidades" como se fosse o total real
do contexto (achado original: Saúde do Contexto contava 67 contradições
no mesmo contexto onde o Grafo mostrava só até 50).

Fix: _true_count() faz uma 2ª consulta count="exact" (sem transferir
linha nenhuma) por tabela; quando o total real é maior que o que foi
carregado, o st.metric mostra "N de M" com help explicando o corte, em
vez do número cru.
"""

from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

st.page_link = lambda *a, **k: None

_pid_counter = iter(range(1, 1000))


class _Resp:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class _FakeQuery:
    def __init__(self, rows: list[dict], true_count: int):
        self._rows = list(rows)
        self._true_count = true_count
        self._is_count = False
        self._limit = None

    def select(self, *cols, count=None):
        if count == "exact":
            self._is_count = True
        return self

    def eq(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        if self._is_count:
            return _Resp([], count=self._true_count)
        rows = self._rows[: self._limit] if self._limit is not None else self._rows
        return _Resp(rows)


class _FakeDB:
    """kh_entities tem mais linhas reais (true_count) do que a query com
    .limit() devolve — simula o corte. As demais tabelas usadas pela
    página (kh_processes/kh_facts/kh_contradictions/project_roster/
    meetings) devolvem vazio, fail-open, sem derrubar a página."""

    def __init__(self, entity_rows: list[dict], entity_true_count: int):
        self._entity_rows = entity_rows
        self._entity_true_count = entity_true_count

    def table(self, name):
        if name == "kh_entities":
            return _FakeQuery(self._entity_rows, self._entity_true_count)
        return _FakeQuery([], 0)


def _fake_entities(n: int) -> list[dict]:
    return [
        {
            "id": f"e{i}", "entity_type": "ACTOR", "canonical_name": f"Entidade {i}",
            "aliases": [], "occurrence_count": 1, "meeting_ids": [],
            "first_seen_meeting_id": None, "last_seen_meeting_id": None, "metadata": {},
        }
        for i in range(n)
    ]


def _base_app(pid: str) -> AppTest:
    at = AppTest.from_file("pages/KnowledgeGraph.py", default_timeout=60)
    at.session_state["_autenticado"] = True
    at.session_state["_usuario_login"] = "teste"
    at.session_state["_usuario_nome"] = "Teste"
    at.session_state["_role"] = "user"
    at.session_state["active_project_id"] = pid
    at.session_state["active_project_name"] = "Projeto Teste"
    return at


class TestTruncationIndicatorShownWhenCapped:
    def test_shows_n_of_total_when_real_count_exceeds_the_cap(self):
        # >10 entidades — o slider "Max entidades no grafo" tem min_value=10
        # fixo mais abaixo na página; menos que isso quebraria o slider por
        # um motivo sem relação nenhuma com o que este teste verifica.
        pid = f"nav15-kg-{next(_pid_counter)}"
        fake_db = _FakeDB(entity_rows=_fake_entities(20), entity_true_count=623)
        with patch("modules.supabase_client.get_supabase_client", lambda: fake_db):
            at = _base_app(pid)
            at.run()

        assert not at.exception
        metrics = {m.label: m for m in at.metric}
        assert "Entidades" in metrics
        assert metrics["Entidades"].value == "20 de 623"
        assert metrics["Entidades"].help and "corte" in metrics["Entidades"].help.lower()

    def test_shows_plain_count_when_not_truncated(self):
        pid = f"nav15-kg-{next(_pid_counter)}"
        # true_count == quantidade carregada — sem corte, sem indicador.
        fake_db = _FakeDB(entity_rows=_fake_entities(20), entity_true_count=20)
        with patch("modules.supabase_client.get_supabase_client", lambda: fake_db):
            at = _base_app(pid)
            at.run()

        assert not at.exception
        metrics = {m.label: m for m in at.metric}
        assert metrics["Entidades"].value == "20"
        assert not metrics["Entidades"].help
