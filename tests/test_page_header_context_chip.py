# tests/test_page_header_context_chip.py
"""
UX-07 (melhorias/ux-amigabilidade-e-elegancia.md, Onda B): o padrao
repetido st.success(f"[icon] **Contexto:** {name}") + coluna "Trocar" (9
paginas confirmadas: Artefatos.py e as 5 subsecoes, EntityRecognition.py,
ValidationHub.py, BpmnEditor.py) usava um alerta verde de largura total
pra mostrar o contexto ativo -- achado E7: "o verde de sucesso perde
significado" quando reaproveitado pra algo que nao e confirmacao de acao.

Fix: ui/components/page_header.py::render_context_chip() -- um pill
compacto (nao um st.success) com o mesmo conteudo (contexto + link
Trocar). Testado isoladamente via AppTest.from_string(), sem depender de
nenhuma pagina real (mesmo padrao de tests/test_kpi_row_component.py e
tests/test_paginator_component.py).

AppTest.from_string() grava o script temporario usando a codificacao
padrao do SO (cp1252 neste Windows), nao UTF-8 -- emoji/acentos dentro da
string INLINE do script quebram com UnicodeEncodeError (documentado em
outros arquivos deste projeto, ex. tests/test_paginator_component.py).
Por isso as strings _PAGE_SRC* abaixo sao ASCII-puro; os caracteres reais
(emoji/acentos) vivem em ui/components/page_header.py (arquivo real,
UTF-8) e sao conferidos por leitura direta do arquivo, nao via AppTest.

st.page_link("pages/Home.py", ...) dentro de render_context_chip levanta
StreamlitPageNotFoundError quando a pagina nao esta registrada no
contexto isolado do AppTest.from_string() -- st.page_link e
monkeypatchado pra no-op neste arquivo, mesmo workaround usado em outros
testes deste projeto (ex. tests/test_safe_page_link.py).
"""

import streamlit as st
from streamlit.testing.v1 import AppTest

st.page_link = lambda *a, **k: None

_PAGE_SRC = """
import streamlit as st
from ui.components.page_header import render_context_chip

render_context_chip("Projeto X")
"""

_PAGE_SRC_CUSTOM_LINK = """
import streamlit as st
from ui.components.page_header import render_context_chip

render_context_chip("Projeto Y", change_page="pages/Outra.py")
"""

_PAGE_SRC_HEADER = """
import streamlit as st
from ui.components.page_header import render_page_header

render_page_header("X", "Titulo Teste", "legenda curta")
"""


class TestRenderContextChipDoesNotUseSuccessAlert:
    def test_no_success_alert_rendered(self):
        at = AppTest.from_string(_PAGE_SRC, default_timeout=30)
        at.run()
        assert not at.exception
        assert len(at.success) == 0, "render_context_chip nao deve usar st.success (E7)"

    def test_project_name_appears_in_rendered_markdown(self):
        at = AppTest.from_string(_PAGE_SRC, default_timeout=30)
        at.run()
        assert not at.exception
        html_blocks = [m.value for m in at.markdown if "Projeto X" in m.value]
        assert html_blocks, "nome do projeto nao apareceu em nenhum bloco markdown"
        assert "Contexto" in html_blocks[0]


class TestRenderContextChipKeepsTheChangeLink:
    def test_default_change_link_points_to_home(self):
        # st.page_link nao e um accessor dedicado nesta versao do AppTest
        # (vira UnknownElement sem .key) -- confirma via leitura do
        # arquivo real que o parametro tem o default esperado, em vez de
        # hardcoded "pages/Home.py" espalhado pela função.
        src = (
            __import__("pathlib").Path(__file__).resolve().parent.parent
            / "ui" / "components" / "page_header.py"
        ).read_text(encoding="utf-8")
        assert 'def render_context_chip(project_name: str, change_page: str = "pages/Home.py")' in src

    def test_custom_change_page_is_accepted_without_raising(self):
        at = AppTest.from_string(_PAGE_SRC_CUSTOM_LINK, default_timeout=30)
        at.run()
        assert not at.exception


class TestRenderPageHeaderUnchanged:
    """Garante que a extensao do modulo (novo render_context_chip) nao
    alterou o comportamento ja existente de render_page_header()."""

    def test_render_page_header_still_renders_title_and_caption(self):
        at = AppTest.from_string(_PAGE_SRC_HEADER, default_timeout=30)
        at.run()
        assert not at.exception
        titles = [m.value for m in at.markdown if "Titulo Teste" in m.value]
        assert titles
        captions = [c.value for c in at.caption if c.value == "legenda curta"]
        assert captions
