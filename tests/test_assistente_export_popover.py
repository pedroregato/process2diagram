# tests/test_assistente_export_popover.py
"""
UX-03 (melhorias/ux-amigabilidade-e-elegancia.md): a barra de ferramentas
do chat do Assistente tinha 3 botões (Markdown/HTML/Limpar) espremidos em
colunas estreitas (st.columns([1.1, 1.1, 1, 5])) — em ~840px o rótulo
"⬇️ Markdown" quebrava letra a letra.

Fix: Markdown e HTML (mesma ação — exportar) viram opções dentro de um
único st.popover("⬇️ Exportar"); Limpar continua botão próprio (ação
destrutiva, categoria diferente de exportação).
"""

from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

st.page_link = lambda *a, **k: None

_HISTORY = [
    {"role": "user", "content": "Quais são as decisões da última reunião?"},
    {"role": "assistant", "content": "A equipe decidiu adotar SSO."},
]


def _base_app() -> AppTest:
    at = AppTest.from_file("pages/Assistente.py", default_timeout=60)
    at.session_state["_autenticado"] = True
    at.session_state["_usuario_login"] = "teste"
    at.session_state["_usuario_nome"] = "Teste"
    at.session_state["_role"] = "user"
    at.session_state["active_project_id"] = "ux03-asst-export"
    at.session_state["active_project_name"] = "Projeto Teste"
    at.session_state["asst_api_key"] = "fake-key-for-tests"
    at.session_state["assistant_history"] = list(_HISTORY)
    return at


class TestExportButtonsConsolidatedIntoPopover:
    def test_export_popover_exists_with_markdown_and_html_inside(self):
        # AppTest não expõe .popover nem .download_button como accessors
        # dedicados nesta versão do Streamlit (.get("...") devolve
        # UnknownElement, sem .key — só .label sobrevive). Verificação por
        # rótulo aqui; a checagem estática abaixo confirma a estrutura de
        # código (1 bloco popover envolvendo os 2 downloads).
        with patch("modules.supabase_client.supabase_configured", lambda: True):
            at = _base_app()
            at.run()
        assert not at.exception

        # A página tem outros popovers (não relacionados a este fix) — o
        # que importa é existir um com exatamente os 2 downloads dentro.
        popovers = at.get("popover")
        assert any(len(p.children) == 2 for p in popovers), (
            f"nenhum popover com 2 filhos (Markdown + HTML) encontrado entre {len(popovers)} popovers"
        )

        dl_labels = {b.label for b in at.get("download_button")}
        assert "⬇️ Markdown" in dl_labels
        assert "⬇️ HTML" in dl_labels

    def test_clear_button_remains_standalone_not_inside_popover(self):
        with patch("modules.supabase_client.supabase_configured", lambda: True):
            at = _base_app()
            at.run()
        assert not at.exception

        clear_btn = next(b for b in at.button if b.key == "btn_clear_chat")
        assert clear_btn.label == "🗑️ Limpar"

    def test_no_more_than_three_top_level_toolbar_columns(self):
        # Antes: 4 colunas (md, html, limpar, info). Depois: 3 (exportar,
        # limpar, info) — o popover substitui 2 colunas por 1.
        with patch("modules.supabase_client.supabase_configured", lambda: True):
            at = _base_app()
            at.run()
        assert not at.exception

        src = (
            __import__("pathlib").Path(__file__).resolve().parent.parent
            / "pages" / "Assistente.py"
        ).read_text(encoding="utf-8")
        assert "_tb_md, _tb_html, _tb_clear, _tb_info" not in src
        assert "_tb_export, _tb_clear, _tb_info = st.columns(" in src

    def test_both_downloads_are_structurally_nested_inside_the_popover_block(self):
        src = (
            __import__("pathlib").Path(__file__).resolve().parent.parent
            / "pages" / "Assistente.py"
        ).read_text(encoding="utf-8")
        popover_idx = src.index('with st.popover("⬇️ Exportar"')
        clear_idx = src.index('with _tb_clear:')
        block = src[popover_idx:clear_idx]
        assert "btn_export_chat_md" in block
        assert "btn_export_chat_html" in block
