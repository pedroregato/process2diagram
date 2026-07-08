# tests/test_analisar_tendencias.py
"""
Tests for core/tools/tools_knowledge_requirements2.py::analisar_tendencias()
(melhorias/avaliacao-proposta-assistente-20260708.md, proposta #1): project-
wide longitudinal trends — most-revised requirements, most-debated IBIS
topics (by alternative count), contradictions by severity. No LLM.

Deliberately does NOT rank participants by contested contributions — see
docstring in the tool itself for why (no table links contradictions/
revisions to a specific author).

No real DB calls.
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

    def in_(self, *a, **k):
        return self

    def execute(self):
        resp = MagicMock()
        resp.data = self._rows
        return resp


_REAL_TABLES = {"requirement_versions", "requirements", "kh_contradictions"}


class _FakeDB:
    def __init__(self, tables: dict):
        self._tables = tables

    def table(self, name):
        if name not in _REAL_TABLES:
            raise Exception(f"relation \"{name}\" does not exist")
        return _FakeQuery(self._tables.get(name, []))


def _executor(meetings, tables, ibis_questions):
    ex = AssistantToolExecutor(project_id="proj-1", llm_config=_LLM_CONFIG)
    ex._get_meetings = lambda: meetings
    ex._load_ibis_questions = lambda **kw: ibis_questions
    db = _FakeDB(tables)
    patcher = patch("modules.supabase_client.get_supabase_client", return_value=db)
    patcher.start()
    return ex, patcher


class TestAnalisarTendencias:
    def test_no_meetings_short_circuits(self):
        ex, patcher = _executor([], {}, [])
        try:
            result = ex.analisar_tendencias()
        finally:
            patcher.stop()
        assert "nenhuma reunião" in result.lower()

    def test_ranks_most_revised_requirements(self):
        tables = {
            "requirement_versions": [
                {"requirement_id": "r1"}, {"requirement_id": "r1"}, {"requirement_id": "r1"},
                {"requirement_id": "r2"},
            ],
            "requirements": [
                {"id": "r1", "req_number": 10, "title": "Requisito Instável"},
                {"id": "r2", "req_number": 20, "title": "Requisito Estável"},
            ],
            "kh_contradictions": [],
        }
        ex, patcher = _executor([{"id": "m1", "meeting_number": 1}], tables, [])
        try:
            result = ex.analisar_tendencias(top_n=5)
        finally:
            patcher.stop()
        assert "REQ-010" in result
        assert "3 versão" in result
        # REQ-010 (3 versions) must be listed before REQ-020 (1 version).
        assert result.index("REQ-010") < result.index("REQ-020")

    def test_ranks_most_debated_ibis_topics_by_alternative_count(self):
        ibis_questions = [
            {"statement": "Pouco debatido", "alternatives": [{"description": "A"}]},
            {"statement": "Muito debatido", "alternatives": [{"description": "A"}, {"description": "B"}, {"description": "C"}]},
            {"statement": "Sem alternativas", "alternatives": []},
        ]
        ex, patcher = _executor([{"id": "m1", "meeting_number": 1}], {}, ibis_questions)
        try:
            result = ex.analisar_tendencias()
        finally:
            patcher.stop()
        assert "Muito debatido" in result
        assert "3 alternativa" in result
        assert "Sem alternativas" not in result  # zero alternatives excluded
        assert result.index("Muito debatido") < result.index("Pouco debatido")

    def test_groups_contradictions_by_severity(self):
        tables = {
            "requirement_versions": [],
            "kh_contradictions": [
                {"severity": "high", "status": "open"},
                {"severity": "high", "status": "open"},
                {"severity": "low", "status": "resolved"},
            ],
        }
        ex, patcher = _executor([{"id": "m1", "meeting_number": 1}], tables, [])
        try:
            result = ex.analisar_tendencias()
        finally:
            patcher.stop()
        assert "high: 2" in result
        assert "low: 1" in result
        assert "1 aberta" in result or "1 resolvida" in result

    def test_never_ranks_participants(self):
        """Documents the explicit scope decision — no participant-level
        metric anywhere in the output."""
        ex, patcher = _executor([{"id": "m1", "meeting_number": 1}], {}, [])
        try:
            result = ex.analisar_tendencias()
        finally:
            patcher.stop()
        assert "participante" not in result.lower()
