# tests/test_diagnostico_projeto_revision_requests.py
"""
Tests for the include_revision_requests check added to
core/tools/tools_knowledge_requirements2.py::diagnostico_projeto()
(Onda 3, melhorias/avaliacao-proposta-assistente-20260708.md, proposta
#4): surfaces requirements marked via solicitar_revisao_requisito() —
the only visibility mechanism for that workflow, since no e-mail/Slack
notification exists in the project.

Other diagnostico_projeto checks are disabled (include_*=False) so this
test exercises only the new check in isolation, without needing to mock
get_database_integrity/calculate_meeting_roi/find_recurring_topics.

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

    def execute(self):
        resp = MagicMock()
        resp.data = self._rows
        return resp


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows

    def table(self, name):
        return _FakeQuery(self._rows)


def _executor(meetings, requirements_rows):
    ex = AssistantToolExecutor(project_id="proj-1", llm_config=_LLM_CONFIG)
    ex._get_meetings = lambda: meetings
    db = _FakeDB(requirements_rows)
    patcher = patch("modules.supabase_client.get_supabase_client", return_value=db)
    patcher.start()
    return ex, patcher


def _run_isolated(ex, **kwargs):
    return ex.diagnostico_projeto(
        include_integrity=False, include_contradictions=False, include_roi=False,
        include_recurring=False, include_pendencies=False, **kwargs,
    )


class TestDiagnosticoProjetoRevisionRequests:
    def test_reports_pending_revision_requests(self):
        rows = [
            {"req_number": 5, "title": "REQ com revisão", "status_note": "🔍 Revisão solicitada: escopo mudou"},
            {"req_number": 8, "title": "Outro REQ", "status_note": "🔍 Revisão solicitada: dúvida do PO"},
        ]
        ex, patcher = _executor([{"id": "m1", "meeting_number": 1}], rows)
        try:
            result = _run_isolated(ex)
        finally:
            patcher.stop()
        assert "2 requisito(s)" in result
        assert "REQ-005" in result and "REQ-008" in result

    def test_ignores_revised_requirements_without_the_marker(self):
        """A requirement can be 'revised' for reasons unrelated to
        solicitar_revisao_requisito() (e.g. a manual status update) —
        only status_notes carrying the exact marker count as pending."""
        rows = [
            {"req_number": 3, "title": "Revisado manualmente", "status_note": "Ajustado no sprint 2"},
        ]
        ex, patcher = _executor([{"id": "m1", "meeting_number": 1}], rows)
        try:
            result = _run_isolated(ex)
        finally:
            patcher.stop()
        assert "Nenhuma revisão solicitada pendente" in result

    def test_disabled_by_flag(self):
        rows = [
            {"req_number": 5, "title": "REQ com revisão", "status_note": "🔍 Revisão solicitada: escopo mudou"},
        ]
        ex, patcher = _executor([{"id": "m1", "meeting_number": 1}], rows)
        try:
            result = _run_isolated(ex, include_revision_requests=False)
        finally:
            patcher.stop()
        assert "REQ-005" not in result
