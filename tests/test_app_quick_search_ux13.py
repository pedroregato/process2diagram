# tests/test_app_quick_search_ux13.py
"""
UX-13 (melhorias/ux-amigabilidade-e-elegancia.md, Onda C): com 39+ itens
visiveis no menu pro usuario comum (54 no total), rolar a sidebar
procurando uma pagina especifica e incomodo. app.py ganha um campo
"Ir para..." (st.selectbox, com filtro nativo por digitacao) no topo da
sidebar, renderizado ANTES de pg.run() -- aparece acima de qualquer
conteudo de sidebar especifico da pagina atual.

Implementacao introspecta os proprios objetos st.Page() ja construidos no
dict `pages` (.title/.icon sao propriedades publicas da API do
Streamlit) -- sem lista duplicada que pudesse ficar fora de sincronia ao
adicionar/remover uma pagina.

AppTest.from_file("app.py") funciona (confirmado manualmente) apesar de
app.py chamar st.navigation()+pg.run() em vez de ser uma "pagina" simples
-- mas a pagina PARA ONDE o usuario navega via st.switch_page() nao
renderiza conteudo observavel em at.markdown/at.title nesta versao do
AppTest (limitacao conhecida de framework com navegacao disparada por
widget, nao um bug do app real) -- por isso o teste confirma a troca de
pagina mockando streamlit.switch_page() e verificando o argumento
recebido, em vez de tentar observar o conteudo da pagina-destino.
"""

from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

st.page_link = lambda *a, **k: None


def _base_app() -> AppTest:
    at = AppTest.from_file("app.py", default_timeout=60)
    at.session_state["_autenticado"] = True
    at.session_state["_usuario_login"] = "teste"
    at.session_state["_usuario_nome"] = "Teste"
    at.session_state["_role"] = "user"
    return at


class TestGotoSelectboxRendersAllVisiblePages:
    def test_selectbox_exists_with_placeholder_plus_all_pages(self):
        at = _base_app()
        at.run()
        assert not at.exception

        goto = next((sb for sb in at.selectbox if sb.key == "_ux13_goto"), None)
        assert goto is not None, "selectbox 'Ir para...' nao encontrado"
        # 39 paginas visiveis pro usuario comum (nao-admin) + 1 placeholder "-"
        assert len(goto.options) == 40

    def test_admin_sees_more_options_than_regular_user(self):
        at_user = _base_app()
        at_user.run()
        goto_user = next(sb for sb in at_user.selectbox if sb.key == "_ux13_goto")

        at_admin = _base_app()
        at_admin.session_state["_role"] = "admin"
        at_admin.run()
        goto_admin = next(sb for sb in at_admin.selectbox if sb.key == "_ux13_goto")

        assert len(goto_admin.options) > len(goto_user.options)

    def test_no_duplicate_options(self):
        at = _base_app()
        at.run()
        goto = next(sb for sb in at.selectbox if sb.key == "_ux13_goto")
        assert len(goto.options) == len(set(goto.options))


class TestGotoSelectionTriggersSwitchPage:
    def test_selecting_a_page_calls_switch_page_with_the_right_target(self):
        calls = []

        def _record_switch(page):
            calls.append(page)
            raise st.runtime.scriptrunner.StopException()

        with patch("streamlit.switch_page", side_effect=_record_switch):
            at = _base_app()
            at.run()
            goto = next(sb for sb in at.selectbox if sb.key == "_ux13_goto")
            target_option = next(o for o in goto.options if "Diagramas" in o)
            goto.select(target_option).run()

        assert not at.exception
        assert len(calls) == 1
        assert calls[0].title == "Diagramas"

    def test_placeholder_selection_does_not_trigger_switch_page(self):
        calls = []

        def _record_switch(page):
            calls.append(page)

        with patch("streamlit.switch_page", side_effect=_record_switch):
            at = _base_app()
            at.run()

        assert not at.exception
        assert calls == []


class TestGotoRendersBeforePgRun:
    """Confere via leitura do codigo-fonte que o widget de busca fica ANTES
    de pg.run() -- garante que aparece no topo da sidebar, nao misturado
    com conteudo especifico da pagina atual (renderizado depois)."""

    def test_goto_selectbox_code_precedes_pg_run_call(self):
        src = (
            __import__("pathlib").Path(__file__).resolve().parent.parent / "app.py"
        ).read_text(encoding="utf-8")
        goto_idx = src.index('key="_ux13_goto"')
        # Busca a CHAMADA real "pg.run()" (linha propria), nao a mencao em
        # comentario no cabecalho do arquivo ("...antes de pg.run().").
        pg_run_idx = src.index("\npg.run()\n")
        assert goto_idx < pg_run_idx
