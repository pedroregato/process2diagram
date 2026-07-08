# tests/test_tools_executive_advanced.py
"""
Tests for core/tools/tools_executive_advanced.py::export_project_charter_docx()
— queues a .docx download in st.session_state["_pending_file_download"] from
the same Markdown gerar_project_charter() already produces.

No real DB/LLM calls: gerar_project_charter() is stubbed per test, except in
TestGerarProjectCharterRealSectionCall, which deliberately runs the REAL
gerar_project_charter() to catch a real bug found while building this tool:
core/tools/tools_meetings_requirements.py::_section() was missing `self` in
its signature, so every self._section(...) call site (13 call sites across
5 files, including gerar_project_charter itself) crashed with TypeError.
"""

import streamlit as st

from core.assistant_tools import AssistantToolExecutor
from core.tools.tools_executive_advanced import _ExecutiveAdvancedToolsMixin


class _FakeExecutor(_ExecutiveAdvancedToolsMixin):
    def __init__(self, charter_markdown: str):
        self.project_id = "proj-1"
        self._charter_markdown = charter_markdown

    def gerar_project_charter(self, **kwargs):
        return self._charter_markdown


class TestGerarProjectCharterRealSectionCall:
    """Regression test for the _section() missing-self bug — uses the real
    AssistantToolExecutor (all mixins), stubbing only the DB/LLM-touching
    helpers gerar_project_charter() calls, so self._section() itself runs
    for real against real minutes_md text."""

    def setup_method(self):
        st.session_state.clear()

    def test_gerar_project_charter_does_not_crash_on_section_extraction(self):
        ex = AssistantToolExecutor(project_id="proj-1")
        ex._get_meetings = lambda: [
            {
                "id": "m1", "meeting_number": 1, "title": "Kickoff",
                "meeting_date": "2026-07-01",
                "minutes_md": (
                    "# Ata\n\n## Participantes\n\nFulano, Beltrano\n\n"
                    "## Itens de Ação\n\n- Enviar proposta\n"
                ),
            },
        ]
        ex.get_bmm = lambda: "não encontrado"
        ex.get_ckf = lambda: "não encontrado"
        ex.list_bpmn_processes = lambda: "(nenhum)"
        ex._llm_call = lambda system, user, max_tokens=3000: "Charter gerado com sucesso."

        result = ex.gerar_project_charter()  # must not raise TypeError
        assert "Charter gerado com sucesso." in result
        assert result.lstrip().startswith("#")


class TestExportProjectCharterDocx:
    def setup_method(self):
        st.session_state.clear()

    def test_success_path_queues_docx_download(self):
        ex = _FakeExecutor("# Project Charter\n\n## Escopo\n\nTexto de exemplo.")
        result = ex.export_project_charter_docx()
        assert "download" in result.lower() or "docx" in result.lower()

        pending = st.session_state.get("_pending_file_download")
        assert pending is not None
        assert pending["mime"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert pending["filename"].endswith(".docx")

        docx_bytes = st.session_state[pending["cache_key"]]
        assert isinstance(docx_bytes, bytes) and len(docx_bytes) > 0

    def test_error_string_from_gerar_project_charter_passes_through_without_export(self):
        ex = _FakeExecutor("Nenhuma reunião encontrada no projeto para gerar o Project Charter.")
        result = ex.export_project_charter_docx()
        assert result == "Nenhuma reunião encontrada no projeto para gerar o Project Charter."
        assert "_pending_file_download" not in st.session_state
