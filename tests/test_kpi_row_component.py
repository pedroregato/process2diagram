# tests/test_kpi_row_component.py
"""
UX-02 (melhorias/ux-amigabilidade-e-elegancia.md): ui/components/kpi_row.py
— substitui linhas de st.metric com 5-7 colunas (truncavam rótulos/valores
em ~840px) por linhas de no máximo max_per_row colunas, quebrando em
múltiplas linhas em vez de espremer tudo numa só.

Testado isoladamente via AppTest.from_string() (mesmo padrão de
tests/test_paginator_component.py) — sem depender de nenhuma página real
nem do Supabase.
"""

from streamlit.testing.v1 import AppTest

_PAGE_SRC = """
import streamlit as st
from ui.components.kpi_row import kpi_row

kpi_row([
    {"label": "A", "value": 1},
    {"label": "B", "value": 2, "help": "ajuda B"},
    {"label": "C", "value": 3, "delta": "+1", "delta_color": "inverse"},
    {"label": "D", "value": 4},
    {"label": "E", "value": 5},
    {"label": "F", "value": 6},
    {"label": "G", "value": 7},
], max_per_row=4)
"""

_PAGE_SRC_EMPTY = """
import streamlit as st
from ui.components.kpi_row import kpi_row

kpi_row([], max_per_row=4)
st.markdown("depois-do-kpi-row")
"""


class TestKpiRowWrapsIntoMultipleRows:
    def test_seven_items_at_max_four_per_row_renders_all_seven_metrics(self):
        at = AppTest.from_string(_PAGE_SRC, default_timeout=30)
        at.run()
        assert not at.exception
        labels = [m.label for m in at.metric]
        assert labels == ["A", "B", "C", "D", "E", "F", "G"]

    def test_no_single_row_exceeds_max_per_row_columns(self):
        # 7 itens com max_per_row=4 devem virar 2 chamadas a st.columns():
        # uma de 4 e uma de 3 — nunca uma linha só de 7. AppTest expõe uma
        # lista achatada de Column, cada um com weight=1/N do grupo em que
        # foi criado — colunas consecutivas com o mesmo weight pertencem à
        # mesma chamada a st.columns(N), então agrupar por weight recupera
        # o tamanho de cada linha original.
        at = AppTest.from_string(_PAGE_SRC, default_timeout=30)
        at.run()
        assert not at.exception

        row_sizes = []
        last_weight = None
        for col in at.columns:
            if row_sizes and last_weight is not None and abs(col.weight - last_weight) < 1e-9:
                row_sizes[-1] += 1
            else:
                row_sizes.append(1)
            last_weight = col.weight

        assert row_sizes == [4, 3], f"esperava linhas de [4, 3] colunas, achou {row_sizes}"

    def test_help_and_delta_are_passed_through(self):
        at = AppTest.from_string(_PAGE_SRC, default_timeout=30)
        at.run()
        assert not at.exception
        b_metric = next(m for m in at.metric if m.label == "B")
        assert b_metric.help == "ajuda B"
        c_metric = next(m for m in at.metric if m.label == "C")
        assert c_metric.delta == "+1"


class TestKpiRowEmptyList:
    def test_empty_items_renders_nothing_and_does_not_crash(self):
        at = AppTest.from_string(_PAGE_SRC_EMPTY, default_timeout=30)
        at.run()
        assert not at.exception
        assert len(at.metric) == 0
        assert any(m.value == "depois-do-kpi-row" for m in at.markdown)
