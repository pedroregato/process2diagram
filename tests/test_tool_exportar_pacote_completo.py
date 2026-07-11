# tests/test_tool_exportar_pacote_completo.py
"""
Tests for AssistantToolExecutor.exportar_pacote_completo() — melhoria
"assistente-20260711.md" item #2: one consolidated .docx (ata + requisitos +
SBVR + BMM + BPMN + IBIS) instead of exporting each artifact separately.

No real DB/LLM calls: _get_meetings()/get_bmm() are stubbed on the instance;
core.project_store list_* functions are patched at the source (project_store
imports are done locally inside the method, so patching the source module
attribute is picked up).
"""

from unittest.mock import patch

import streamlit as st

from core.assistant_tools import AssistantToolExecutor


def _executor():
    ex = AssistantToolExecutor("proj-1", {})
    ex._get_meetings = lambda: [
        {"meeting_number": 1, "title": "Kickoff", "meeting_date": "2026-01-01",
         "minutes_md": "## Decisões\nAprovado o escopo inicial.\n"},
        {"meeting_number": 2, "title": "Revisão", "meeting_date": "2026-01-08",
         "minutes_md": ""},
    ]
    ex.get_bmm = lambda meeting_number=None: "## Visão\nSer referência no setor."
    return ex


class TestExportarPacoteCompleto:
    def setup_method(self):
        st.session_state.clear()

    def test_no_meetings_returns_error_without_crashing(self):
        ex = AssistantToolExecutor("proj-1", {})
        ex._get_meetings = lambda: []
        result = ex.exportar_pacote_completo()
        assert "nenhuma reunião" in result.lower()
        assert "_pending_file_download" not in st.session_state

    def test_success_queues_docx_download_with_all_sections(self):
        with patch("core.project_store.list_requirements_light", return_value=[
                {"req_number": 1, "title": "Login via SSO", "req_type": "Funcional",
                 "priority": "Alto", "status": "active"},
            ]), \
             patch("core.project_store.list_sbvr_terms", return_value=[
                {"term": "Cliente", "definition": "Pessoa que contrata o serviço"},
             ]), \
             patch("core.project_store.list_sbvr_rules", return_value=[
                {"rule_id": "RN-001", "statement": "Todo cliente deve ter CPF válido."},
             ]), \
             patch("core.project_store.list_bpmn_processes", return_value=[
                {"name": "Processo de Onboarding", "version_count": 2},
             ]), \
             patch("core.project_store.list_argumentation_by_project", return_value=[
                {"id": "Q-001", "statement": "Qual fluxo de aprovação usar?"},
             ]):
            ex = _executor()
            result = ex.exportar_pacote_completo()

        assert "✅" in result
        assert "Atas das Reuniões" in result
        assert "Requisitos" in result
        assert "SBVR" in result
        assert "BMM" in result
        assert "Processos BPMN" in result
        assert "IBIS" in result

        pending = st.session_state.get("_pending_file_download")
        assert pending is not None
        assert pending["mime"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        assert pending["filename"].endswith(".docx")
        docx_bytes = st.session_state[pending["cache_key"]]
        assert isinstance(docx_bytes, bytes) and len(docx_bytes) > 0

    def test_incluir_secoes_filters_to_requested_sections_only(self):
        with patch("core.project_store.list_requirements_light", return_value=[]), \
             patch("core.project_store.list_sbvr_terms", return_value=[]), \
             patch("core.project_store.list_sbvr_rules", return_value=[]), \
             patch("core.project_store.list_bpmn_processes", return_value=[]), \
             patch("core.project_store.list_argumentation_by_project", return_value=[]):
            ex = _executor()
            result = ex.exportar_pacote_completo(incluir_secoes=["atas", "requisitos"])

        assert "Atas das Reuniões" in result
        assert "Requisitos" in result
        assert "SBVR" not in result
        assert "BMM" not in result
        assert "Processos BPMN" not in result
        assert "IBIS" not in result

    def test_meeting_numbers_filters_atas_section(self):
        with patch("core.project_store.list_requirements_light", return_value=[]), \
             patch("core.project_store.list_sbvr_terms", return_value=[]), \
             patch("core.project_store.list_sbvr_rules", return_value=[]), \
             patch("core.project_store.list_bpmn_processes", return_value=[]), \
             patch("core.project_store.list_argumentation_by_project", return_value=[]):
            ex = _executor()
            result = ex.exportar_pacote_completo(meeting_numbers=[1], incluir_secoes=["atas"])

        assert "✅" in result
        pending = st.session_state.get("_pending_file_download")
        assert pending is not None

    def test_docx_generation_failure_reported_without_raising(self):
        with patch("core.project_store.list_requirements_light", return_value=[]), \
             patch("core.project_store.list_sbvr_terms", return_value=[]), \
             patch("core.project_store.list_sbvr_rules", return_value=[]), \
             patch("core.project_store.list_bpmn_processes", return_value=[]), \
             patch("core.project_store.list_argumentation_by_project", return_value=[]), \
             patch("modules.minutes_exporter.markdown_to_docx", side_effect=RuntimeError("boom")):
            ex = _executor()
            result = ex.exportar_pacote_completo()
        assert "❌" in result
        assert "_pending_file_download" not in st.session_state

    def test_registered_in_dispatch_and_schema(self):
        from core.assistant_tools import get_tool_schemas_openai
        names = [s["function"]["name"] for s in get_tool_schemas_openai()]
        assert "exportar_pacote_completo" in names

    def test_not_admin_only(self):
        from core.assistant_tools import _ADMIN_TOOLS
        assert "exportar_pacote_completo" not in _ADMIN_TOOLS
