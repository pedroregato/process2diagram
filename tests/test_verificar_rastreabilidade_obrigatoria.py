# tests/test_verificar_rastreabilidade_obrigatoria.py
"""
Tests for core/tools/tools_knowledge_requirements2.py::
verificar_rastreabilidade_obrigatoria() (melhorias/avaliacao-proposta-
assistente-20260708.md, proposta #17): project-wide gap analysis —
requirements missing source_quote, IBIS questions with no alternative/
resolution, BPMN processes with no description. No LLM.

No real DB calls — Supabase client mocked via a small fake keyed by table name.
"""

from unittest.mock import patch, MagicMock

from core.assistant_tools import AssistantToolExecutor

_LLM_CONFIG = {
    "api_key": "fake-key",
    "model": "fake-model",
    "provider_cfg": {"client_type": "openai_compatible", "default_model": "fake-model"},
}


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def execute(self):
        resp = MagicMock()
        resp.data = self._rows
        return resp


class _FakeDB:
    def __init__(self, tables: dict):
        self._tables = tables

    def table(self, name):
        return _FakeQuery(self._tables.get(name, []))


def _executor(meetings, tables):
    ex = AssistantToolExecutor(project_id="proj-1", llm_config=_LLM_CONFIG)
    ex._get_meetings = lambda: meetings
    db = _FakeDB(tables)
    patcher = patch("modules.supabase_client.get_supabase_client", return_value=db)
    patcher.start()
    return ex, patcher


class TestVerificarRastreabilidadeObrigatoria:
    def test_no_meetings_short_circuits(self):
        ex, patcher = _executor([], {})
        try:
            result = ex.verificar_rastreabilidade_obrigatoria()
        finally:
            patcher.stop()
        assert "nenhuma reunião" in result.lower()

    def test_reports_gaps_across_all_three_categories(self):
        tables = {
            "requirements": [
                {"req_number": 1, "title": "Com origem", "source_quote": "trecho real"},
                {"req_number": 2, "title": "Sem origem", "source_quote": ""},
                {"req_number": 3, "title": "Também sem origem", "source_quote": None},
            ],
            "argumentation_questions": [
                {"id": "q1", "statement": "Pergunta resolvida", "alternatives": [{"description": "A"}],
                 "resolution": {"type": "decided"}},
                {"id": "q2", "statement": "Pergunta incompleta", "alternatives": [], "resolution": {}},
            ],
            "bpmn_processes": [
                {"name": "Processo Documentado", "description": "Descrição completa."},
                {"name": "Processo Sem Descrição", "description": ""},
            ],
        }
        ex, patcher = _executor([{"id": "m1", "meeting_number": 1}], tables)
        try:
            result = ex.verificar_rastreabilidade_obrigatoria()
        finally:
            patcher.stop()

        assert "REQ-002" in result and "Sem origem" in result
        assert "REQ-003" in result and "Também sem origem" in result
        assert "REQ-001" not in result  # has source_quote, not a gap

        assert "Pergunta incompleta" in result
        assert "Pergunta resolvida" not in result  # has resolution, not a gap

        assert "Processo Sem Descrição" in result
        assert "Processo Documentado" not in result  # has description, not a gap

        assert "4 gap(s)" in result  # 2 reqs + 1 ibis + 1 bpmn

    def test_no_gaps_reports_all_clear(self):
        tables = {
            "requirements": [{"req_number": 1, "title": "OK", "source_quote": "trecho"}],
            "argumentation_questions": [
                {"id": "q1", "statement": "OK", "alternatives": [{"description": "A"}], "resolution": {}},
            ],
            "bpmn_processes": [{"name": "OK", "description": "desc"}],
        }
        ex, patcher = _executor([{"id": "m1", "meeting_number": 1}], tables)
        try:
            result = ex.verificar_rastreabilidade_obrigatoria()
        finally:
            patcher.stop()
        assert "0 gap(s)" in result
        assert result.count("✅") == 3
