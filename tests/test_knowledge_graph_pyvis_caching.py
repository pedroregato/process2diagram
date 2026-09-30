# tests/test_knowledge_graph_pyvis_caching.py
"""
NAV-17 (melhorias/parciais/navegabilidade.md): pages/KnowledgeGraph.py
reconstruía o grafo pyvis (HTML+JS) do zero em TODO rerun da página —
mesmo mudando de aba pra "Fatos"/"Timeline" (st.tabs renderiza todos os
corpos sempre, não só a aba visível). Maior causa isolada dos ~30s medidos
num contexto com 150 entidades/608 arestas.

Fix: _build_pyvis_graph() ganhou @st.cache_data — a função já era pura
(recebe tudo via argumento, sem I/O), memoizar por conteúdo dos argumentos
evita reconstruir quando nada que afeta o grafo mudou.

Mesmo padrão de tests/test_assistente_load_caching.py (NAV-09): 2
instâncias de AppTest com o MESMO project_id e os mesmos filtros padrão do
sidebar — a 2ª deve bater no cache global de processo preenchido pela 1ª.
pyvis.network.Network é mockado pra contar construções reais em vez de
depender de medir tempo de execução.
"""

from unittest.mock import patch, MagicMock

import streamlit as st
from streamlit.testing.v1 import AppTest

st.page_link = lambda *a, **k: None

_pid_counter = iter(range(1, 1000))


class _Resp:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class _FakeQuery:
    def __init__(self, rows: list[dict]):
        self._rows = list(rows)
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
            return _Resp([], count=len(self._rows))
        rows = self._rows[: self._limit] if self._limit is not None else self._rows
        return _Resp(rows)


class _FakeDB:
    """kh_entities tem dado real e estável; demais tabelas vazias,
    fail-open — mesmo padrão de tests/test_knowledge_graph_truncation.py."""

    def __init__(self, entity_rows: list[dict]):
        self._entity_rows = entity_rows

    def table(self, name):
        if name == "kh_entities":
            return _FakeQuery(self._entity_rows)
        return _FakeQuery([])


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


class TestPyvisGraphBuildIsCachedAcrossReruns:
    def test_network_constructed_once_across_two_reruns_with_identical_filters(self):
        st.cache_data.clear()
        pid = f"nav17-kg-{next(_pid_counter)}"
        fake_db = _FakeDB(_fake_entities(20))

        _net_calls = {"n": 0}

        class _FakeNetwork:
            def __init__(self, *a, **k):
                _net_calls["n"] += 1
                self._nodes = []
                self._edges = []

            def add_node(self, *a, **k):
                pass

            def add_edge(self, *a, **k):
                pass

            def set_options(self, *a, **k):
                pass

            def generate_html(self, *a, **k):
                return "<html></html>"

            def show_buttons(self, *a, **k):
                pass

            @property
            def nodes(self):
                return self._nodes

            @property
            def edges(self):
                return self._edges

            def write_html(self, path, *a, **k):
                with open(path, "w", encoding="utf-8") as f:
                    f.write("<html></html>")

        with patch("modules.supabase_client.get_supabase_client", lambda: fake_db), \
             patch("pyvis.network.Network", _FakeNetwork):

            at1 = _base_app(pid)
            at1.run()
            assert not at1.exception, f"1ª execução falhou: {at1.exception}"

            # 2ª instância NOVA de AppTest (não um 2º .run() na mesma
            # instância — limitação conhecida do framework, documentada em
            # tests/test_assistente_load_caching.py). st.cache_data é
            # global de processo: uma instância nova com o mesmo pid e os
            # mesmos filtros padrão do sidebar ainda bate no cache
            # preenchido pela 1ª.
            at2 = _base_app(pid)
            at2.run()
            assert not at2.exception, f"2ª execução falhou: {at2.exception}"

        assert _net_calls["n"] == 1, (
            f"pyvis.Network() construído {_net_calls['n']}x em 2 reruns idênticos "
            "— cache de _build_pyvis_graph pode ter regredido"
        )


class TestRefreshButtonClearsBothCaches:
    def test_refresh_button_clears_pyvis_cache_alongside_graph_data_cache(self):
        src = (
            __import__("pathlib").Path(__file__).resolve().parent.parent
            / "pages" / "KnowledgeGraph.py"
        ).read_text(encoding="utf-8")
        anchor = src.index('st.button("🔄 Recarregar dados"')
        block = src[anchor:anchor + 300]
        assert "_load_graph_data.clear()" in block
        assert "_build_pyvis_graph.clear()" in block
