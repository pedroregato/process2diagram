# tests/test_verificar_rastreabilidade_obrigatoria.py
"""
Tests for core/tools/tools_knowledge_requirements2.py::
verificar_rastreabilidade_obrigatoria() (melhorias/avaliacao-proposta-
assistente-20260708.md, proposta #17): project-wide gap analysis —
requirements missing source_quote, IBIS questions with no alternative/
resolution, BPMN processes with no description. No LLM.

Regression note: the first version of this tool queried a table named
"argumentation_questions" for the IBIS gap check — confirmed against the
live Supabase schema that table DOES NOT EXIST (IBIS data lives as JSON
in meetings.argumentation_json, read via the existing
_load_ibis_questions() helper in _DocumentsIbisDiagramsToolsMixin, shared
with search_ibis_debates/get_ibis_timeline). Every call failed with a
PostgREST "table not found" error, caught silently (n_ibis = 0, no gaps
reported) — the mocked tests here originally passed because the fake DB
never validated the table name existed, giving false confidence. Fixed
to call self._load_ibis_questions() instead of querying a table directly.

No real DB calls for requirements/bpmn_processes (still real tables,
mocked via a small fake keyed by table name); _load_ibis_questions is
mocked directly since it already has its own dedicated test coverage
elsewhere in the IBIS tool suite.
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


# Real tables this tool is allowed to query directly — anything else
# raises, so a regression back to a non-existent table name fails loudly.
_REAL_TABLES = {"requirements", "bpmn_processes"}


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


class TestVerificarRastreabilidadeObrigatoria:
    def test_no_meetings_short_circuits(self):
        ex, patcher = _executor([], {}, [])
        try:
            result = ex.verificar_rastreabilidade_obrigatoria()
        finally:
            patcher.stop()
        assert "nenhuma reunião" in result.lower()

    def test_does_not_query_a_nonexistent_ibis_table(self):
        """Regression guard: IBIS gaps must come from _load_ibis_questions(),
        never a direct db.table("argumentation_questions") call — the fake
        DB raises on any table name outside {requirements, bpmn_processes}."""
        ex, patcher = _executor(
            [{"id": "m1", "meeting_number": 1}],
            {"requirements": [], "bpmn_processes": []},
            ibis_questions=[{"statement": "Sem alternativa", "alternatives": [], "resolution": {}}],
        )
        try:
            result = ex.verificar_rastreabilidade_obrigatoria()
        finally:
            patcher.stop()
        assert "Sem alternativa" in result

    def test_reports_gaps_across_all_three_categories(self):
        tables = {
            "requirements": [
                {"req_number": 1, "title": "Com origem", "source_quote": "trecho real"},
                {"req_number": 2, "title": "Sem origem", "source_quote": ""},
                {"req_number": 3, "title": "Também sem origem", "source_quote": None},
            ],
            "bpmn_processes": [
                {"name": "Processo Documentado", "description": "Descrição completa."},
                {"name": "Processo Sem Descrição", "description": ""},
            ],
        }
        ibis_questions = [
            {"statement": "Pergunta resolvida", "alternatives": [{"description": "A"}],
             "resolution": {"type": "decided"}},
            {"statement": "Pergunta incompleta", "alternatives": [], "resolution": {}},
        ]
        ex, patcher = _executor([{"id": "m1", "meeting_number": 1}], tables, ibis_questions)
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
            "bpmn_processes": [{"name": "OK", "description": "desc"}],
        }
        ibis_questions = [
            {"statement": "OK", "alternatives": [{"description": "A"}], "resolution": {}},
        ]
        ex, patcher = _executor([{"id": "m1", "meeting_number": 1}], tables, ibis_questions)
        try:
            result = ex.verificar_rastreabilidade_obrigatoria()
        finally:
            patcher.stop()
        assert "0 gap(s)" in result
        assert result.count("✅") == 3
