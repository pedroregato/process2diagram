# tests/test_tool_gerar_variacao_apresentacao.py
"""
Tests for AssistantToolExecutor.gerar_variacao_apresentacao() — lets the user
ask the Assistant, in natural language, for a variation of one of the two
commercial material pages (Apresentação Geral / Sobre o P2D), reusing the
real static HTML as a design/content reference. No real LLM call: _llm_call
is stubbed per test.
"""

from unittest.mock import patch

import streamlit as st

from core.assistant_tools import AssistantToolExecutor


def _executor():
    return AssistantToolExecutor("p1", {})


class TestGerarVariacaoApresentacao:
    def setup_method(self):
        st.session_state.clear()

    def test_invalid_base_rejected(self):
        result = _executor().gerar_variacao_apresentacao(
            base="marketing", variacao_pedida="foco em saúde",
        )
        assert "inválido" in result.lower()

    def test_blank_variacao_rejected(self):
        result = _executor().gerar_variacao_apresentacao(base="sobre", variacao_pedida="   ")
        assert "descreva" in result.lower()

    def test_success_queues_html_download(self):
        fake_html = "<!doctype html><html><head></head><body>Variação</body></html>"
        with patch.object(AssistantToolExecutor, "_llm_call", return_value=fake_html):
            result = _executor().gerar_variacao_apresentacao(
                base="apresentacao", variacao_pedida="foco em clientes de saúde",
            )
        assert "✅" in result
        pending = st.session_state.get("_pending_file_download")
        assert pending is not None
        assert pending["mime"] == "text/html"
        assert pending["filename"].endswith(".html")
        assert "apresentacao" in pending["filename"]

        html_bytes = st.session_state[pending["cache_key"]]
        assert isinstance(html_bytes, bytes)
        assert b"<html" in html_bytes.lower()

    def test_sobre_base_strips_huge_base64_photo_before_prompting_llm(self):
        """static/sobre-p2d.html embeds the author photo as base64 (~2.7MB) —
        sending that raw to the LLM would blow up tokens/cost for zero value.
        Must be replaced with a short placeholder before the prompt is built."""
        fake_html = "<!doctype html><html><body>ok</body></html>"
        with patch.object(AssistantToolExecutor, "_llm_call", return_value=fake_html) as mocked:
            _executor().gerar_variacao_apresentacao(base="sobre", variacao_pedida="tom mais técnico")
        _, kwargs = mocked.call_args
        args = mocked.call_args.args
        user_prompt = kwargs.get("user") if "user" in kwargs else args[1]
        assert "base64,__FOTO_OMITIDA__" in user_prompt
        assert len(user_prompt) < 60000

    def test_markdown_fence_is_stripped_from_response(self):
        fenced = "```html\n<!doctype html><html><body>x</body></html>\n```"
        with patch.object(AssistantToolExecutor, "_llm_call", return_value=fenced):
            result = _executor().gerar_variacao_apresentacao(base="sobre", variacao_pedida="resumida")
        assert "✅" in result
        html_bytes = st.session_state[st.session_state["_pending_file_download"]["cache_key"]]
        assert not html_bytes.strip().startswith(b"```")

    def test_response_without_html_tag_returns_error(self):
        with patch.object(AssistantToolExecutor, "_llm_call", return_value="Desculpe, não consigo."):
            result = _executor().gerar_variacao_apresentacao(base="sobre", variacao_pedida="resumida")
        assert "❌" in result
        assert "_pending_file_download" not in st.session_state

    def test_llm_error_returns_error_message_without_raising(self):
        with patch.object(AssistantToolExecutor, "_llm_call", side_effect=RuntimeError("boom")):
            result = _executor().gerar_variacao_apresentacao(base="sobre", variacao_pedida="resumida")
        assert "❌" in result
        assert "_pending_file_download" not in st.session_state

    def test_registered_in_dispatch_and_schema(self):
        from core.assistant_tools import get_tool_schemas_openai
        names = [s["function"]["name"] for s in get_tool_schemas_openai()]
        assert "gerar_variacao_apresentacao" in names

    def test_not_admin_only(self):
        from core.assistant_tools import _ADMIN_TOOLS
        assert "gerar_variacao_apresentacao" not in _ADMIN_TOOLS
