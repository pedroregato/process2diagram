# tests/test_paginator_component.py
"""
NAV-09 (melhorias/parciais/navegabilidade.md, PC219): ui/components/paginator.py
extraído da lógica que existia duplicada em pages/ArtefatosModelagem.py
(PC178) e pages/ValidationHub.py::_paginate (PC212/NAV-03) — ambos
refatorados pra usar este componente (ver tests/test_artefatos_sbvr_pagination.py
e tests/test_validation_hub_pagination.py, que continuam cobrindo o
comportamento nos dois call sites reais).

Este arquivo testa o componente isoladamente via uma página mínima
(AppTest.from_string()), sem precisar mockar nada específico de negócio.
"""

from streamlit.testing.v1 import AppTest

_PAGE_SRC = """
import streamlit as st
from ui.components.paginator import paginate

items = [f"item-{i:03d}" for i in range(60)]
page = paginate(items, key_prefix="t", filter_sig="sig-a")
for it in page:
    st.markdown(it)
"""

_PAGE_SRC_NO_SELECTOR = """
import streamlit as st
from ui.components.paginator import paginate

items = [f"item-{i:03d}" for i in range(60)]
page = paginate(items, key_prefix="t", filter_sig="sig-a",
                 page_sizes=(25,), show_size_selector=False)
for it in page:
    st.markdown(it)
"""


class TestPaginatorSlicing:
    def test_first_page_has_25_items_by_default(self):
        at = AppTest.from_string(_PAGE_SRC, default_timeout=30)
        at.run()
        assert not at.exception
        rendered = [m.value for m in at.markdown if m.value.startswith("item-")]
        assert len(rendered) == 25
        assert rendered[0] == "item-000"
        assert rendered[-1] == "item-024"

    def test_next_button_advances_without_repeating(self):
        at = AppTest.from_string(_PAGE_SRC, default_timeout=30)
        at.run()
        next_btn = [b for b in at.button if b.key == "t_next"]
        assert next_btn, "botão 'Próximo →' não encontrado"
        next_btn[0].click().run()

        assert not at.exception
        rendered = [m.value for m in at.markdown if m.value.startswith("item-")]
        assert len(rendered) == 25
        assert rendered[0] == "item-025"
        assert "item-000" not in rendered

    def test_prev_button_disabled_on_first_page(self):
        at = AppTest.from_string(_PAGE_SRC, default_timeout=30)
        at.run()
        prev_btn = [b for b in at.button if b.key == "t_prev"]
        assert prev_btn and prev_btn[0].disabled

    def test_page_size_selector_changes_slice_size(self):
        at = AppTest.from_string(_PAGE_SRC, default_timeout=30)
        at.run()
        sel = [sb for sb in at.selectbox if sb.key == "pg_size_t"]
        assert sel, "seletor de itens por página não encontrado"
        sel[0].select(50).run()

        assert not at.exception
        rendered = [m.value for m in at.markdown if m.value.startswith("item-")]
        assert len(rendered) == 50


class TestPaginatorWithoutSizeSelector:
    def test_fixed_page_size_no_selector_widget(self):
        at = AppTest.from_string(_PAGE_SRC_NO_SELECTOR, default_timeout=30)
        at.run()
        assert not at.exception
        assert not [sb for sb in at.selectbox if sb.key == "pg_size_t"]
        rendered = [m.value for m in at.markdown if m.value.startswith("item-")]
        assert len(rendered) == 25


class TestPaginatorFilterSignatureReset:
    def test_changing_filter_sig_resets_to_first_page(self):
        at = AppTest.from_string(_PAGE_SRC, default_timeout=30)
        at.run()
        next_btn = [b for b in at.button if b.key == "t_next"]
        next_btn[0].click().run()
        rendered = [m.value for m in at.markdown if m.value.startswith("item-")]
        assert rendered[0] == "item-025"  # confirma que avançou

        # Nova execução com filter_sig DIFERENTE — simula o usuário mudando
        # um filtro (reunião/status/categoria) na página real.
        page_src_new_sig = _PAGE_SRC.replace('filter_sig="sig-a"', 'filter_sig="sig-b"')
        at2 = AppTest.from_string(page_src_new_sig, default_timeout=30)
        at2.session_state["pg_page_t"] = at.session_state["pg_page_t"]
        at2.session_state["_pg_last_filter_t"] = "sig-a"
        at2.run()

        assert not at2.exception
        rendered2 = [m.value for m in at2.markdown if m.value.startswith("item-")]
        assert rendered2[0] == "item-000", "filter_sig mudou mas a página não resetou pra 0"
