# tests/test_tool_sugerir_encaminhamentos_pendentes.py
"""
Tests for AssistantToolExecutor.sugerir_encaminhamentos_pendentes() —
melhoria "assistente-20260711.md" item #5: compares Decisões x
Encaminhamentos in minutes_md (unstructured text — no action_items table
exists) via 1 LLM call per meeting, flagging decisions with no matching
action item and overdue action items.
"""

from unittest.mock import patch

from core.assistant_tools import AssistantToolExecutor


def _executor(meetings):
    ex = AssistantToolExecutor("proj-1", {})
    ex._get_meetings = lambda: meetings
    return ex


_MD_WITH_BOTH = (
    "## Decisões\nAprovado o novo fluxo de aprovação.\n\n"
    "## Encaminhamentos / Action Items\nMaria vai atualizar o BPMN até 10/01.\n"
)
_MD_DECISIONS_ONLY = "## Decisões\nDecidido migrar para o novo provedor de nuvem.\n"
_MD_EMPTY = ""


class TestSugerirEncaminhamentosPendentes:
    def test_no_meetings_returns_clear_message(self):
        ex = _executor([])
        result = ex.sugerir_encaminhamentos_pendentes()
        assert "nenhuma reunião" in result.lower()

    def test_unknown_meeting_number_returns_not_found(self):
        ex = _executor([{"meeting_number": 1, "minutes_md": _MD_WITH_BOTH}])
        result = ex.sugerir_encaminhamentos_pendentes(meeting_number=99)
        assert "não encontrada" in result.lower()

    def test_meeting_without_decisions_or_actions_reports_nothing_to_analyze(self):
        ex = _executor([{"meeting_number": 1, "title": "Sem pauta", "minutes_md": _MD_EMPTY}])
        result = ex.sugerir_encaminhamentos_pendentes(meeting_number=1)
        assert "nenhuma decisão ou encaminhamento" in result.lower()

    def test_single_meeting_calls_llm_once_and_includes_result(self):
        ex = _executor([{"meeting_number": 3, "title": "Sprint Review", "minutes_md": _MD_WITH_BOTH}])
        with patch.object(AssistantToolExecutor, "_llm_call",
                           return_value="1. Nenhuma decisão sem encaminhamento.\n2. Nenhum prazo vencido.") as mocked:
            result = ex.sugerir_encaminhamentos_pendentes(meeting_number=3)
        mocked.assert_called_once()
        assert "Reunião 3" in result
        assert "Sprint Review" in result
        assert "Nenhuma decisão sem encaminhamento" in result

    def test_default_scope_analyzes_last_5_meetings_only(self):
        meetings = [
            {"meeting_number": n, "title": f"R{n}", "minutes_md": _MD_DECISIONS_ONLY}
            for n in range(1, 8)  # 7 meetings — only last 5 should be analyzed
        ]
        ex = _executor(meetings)
        with patch.object(AssistantToolExecutor, "_llm_call", return_value="ok") as mocked:
            result = ex.sugerir_encaminhamentos_pendentes()
        assert mocked.call_count == 5
        assert "Reunião 1 —" not in result
        assert "Reunião 2 —" not in result
        assert "Reunião 7 —" in result

    def test_meeting_with_no_minutes_md_is_skipped(self):
        ex = _executor([
            {"meeting_number": 1, "title": "Sem ata", "minutes_md": None},
            {"meeting_number": 2, "title": "Com ata", "minutes_md": _MD_DECISIONS_ONLY},
        ])
        with patch.object(AssistantToolExecutor, "_llm_call", return_value="ok") as mocked:
            result = ex.sugerir_encaminhamentos_pendentes()
        mocked.assert_called_once()
        assert "Reunião 1" not in result
        assert "Reunião 2" in result

    def test_llm_error_reported_inline_without_raising(self):
        ex = _executor([{"meeting_number": 5, "title": "R5", "minutes_md": _MD_WITH_BOTH}])
        with patch.object(AssistantToolExecutor, "_llm_call", side_effect=RuntimeError("boom")):
            result = ex.sugerir_encaminhamentos_pendentes(meeting_number=5)
        assert "⚠️" in result
        assert "boom" in result

    def test_registered_in_dispatch_and_schema(self):
        from core.assistant_tools import get_tool_schemas_openai
        names = [s["function"]["name"] for s in get_tool_schemas_openai()]
        assert "sugerir_encaminhamentos_pendentes" in names

    def test_not_admin_only(self):
        from core.assistant_tools import _ADMIN_TOOLS
        assert "sugerir_encaminhamentos_pendentes" not in _ADMIN_TOOLS
