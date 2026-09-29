# tests/test_settings_db_tab_performance.py
"""
NAV-17 (melhorias/parciais/navegabilidade.md): a aba "Banco de Dados" de
pages/Settings.py rodava a cada rerun da página inteira (st.tabs() executa
todos os corpos, não só a aba visível) — até 9 idas ao Supabase sem cache:
1 fetch de contexts (necessário, dá os ids pro filtro de tenant), 2 fetches
de linha completa só pra fazer len() em Python (meetings/requirements —
count="exact" evita transferir as linhas), e 6 probes de "tabela existe?".

Fix: _db_overview_stats(tid) e _optional_tables_status() com @st.cache_data
— reruns dentro da janela de TTL reusam o resultado em vez de reconsultar.
meetings/requirements passam a usar count="exact" + limit(1) (mesmo padrão
de KnowledgeGraph.py::_true_count(), NAV-15) em vez de trazer a lista
completa de IDs só pra contar.

tests/test_settings_tenant_isolation.py já cobre que a query de contexts
continua filtrada por tenant_id — não duplicado aqui.
"""

from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

st.page_link = lambda *a, **k: None

_pid_counter = iter(range(1, 1000))

_SETTINGS_SRC = (
    __import__("pathlib").Path(__file__).resolve().parent.parent / "pages" / "Settings.py"
).read_text(encoding="utf-8")


class TestStaticCachingAndCountExactWiring:
    def test_db_overview_stats_and_optional_tables_status_are_cached(self):
        for fn_name in ("_db_overview_stats", "_optional_tables_status"):
            anchor = _SETTINGS_SRC.index(f"def {fn_name}(")
            block = _SETTINGS_SRC[max(0, anchor - 150):anchor]
            assert "@st.cache_data(" in block, f"{fn_name} não está decorada com @st.cache_data"

    def test_meetings_and_requirements_counts_use_count_exact_not_full_fetch(self):
        block = _SETTINGS_SRC[
            _SETTINGS_SRC.index("def _db_overview_stats("):
            _SETTINGS_SRC.index("def _optional_tables_status(")
        ]
        assert block.count('count="exact"') == 2, (
            "esperava count=\"exact\" nas consultas de meetings E requirements"
        )
        assert '.select("id").in_("project_id"' not in block, (
            "ainda traz a lista completa de IDs em vez de só contar"
        )


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

    def eq(self, col, val):
        self._rows = [r for r in self._rows if r.get(col) == val]
        return self

    def in_(self, col, vals):
        self._rows = [r for r in self._rows if r.get(col) in vals]
        return self

    def update(self, patch):
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
    def __init__(self, contexts, meetings, requirements):
        self._tables = {"contexts": contexts, "meetings": meetings, "requirements": requirements}

    def table(self, name):
        return _FakeQuery(self._tables.get(name, []))


class TestDbOverviewStatsRendersRealCounts:
    def test_kpis_show_real_counts_via_count_exact(self):
        pid_tenant = f"nav17-settings-{next(_pid_counter)}"
        contexts = [{"id": "ctx-1", "tenant_id": pid_tenant, "name": "Projeto X",
                     "description": "", "sigla": "PX"}]
        meetings = [{"id": f"m{i}", "project_id": "ctx-1"} for i in range(7)]
        requirements = [{"id": f"r{i}", "project_id": "ctx-1"} for i in range(42)]
        fake_db = _FakeDB(contexts, meetings, requirements)

        with patch("modules.supabase_client.supabase_configured", lambda: True), \
             patch("modules.supabase_client.get_supabase_client", lambda: fake_db):
            at = AppTest.from_file("pages/Settings.py", default_timeout=60)
            at.session_state["_autenticado"] = True
            at.session_state["_usuario_login"] = "teste"
            at.session_state["_usuario_nome"] = "Teste"
            at.session_state["_role"] = "user"
            at.session_state["_tenant_id"] = pid_tenant
            at.run()

        assert not at.exception
        metrics = {m.label: m.value for m in at.metric}
        assert metrics.get("Projetos") == "1"
        assert metrics.get("Reuniões") == "7"
        assert metrics.get("Requisitos") == "42"
