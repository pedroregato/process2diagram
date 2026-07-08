# tests/test_section_action_items_heading.py
"""
Regression test for a second bug found while building the Onda 1 quick wins
(melhorias/avaliacao-proposta-assistente-20260708.md): every self._section(...)
call site extracting "encaminhamentos"/action items passed the wrong
alternate heading names ("Itens de Ação", "Action Items", "Ações") — none of
which match the REAL heading AgentMinutes.to_markdown() actually writes,
"Encaminhamentos / Action Items". _section()'s regex requires the heading
line to match up to \\s*\\n, so "Action Items" as a bare name never matched
a line that continues with " / Action Items" after it — extraction silently
returned "" for years, with no test ever catching it.

Fixed in 7 call sites across 5 files by adding the real heading name
("Encaminhamentos / Action Items", "Encaminhamentos") to each _section()
call's tried-names list. This test covers the real heading text directly
plus one representative end-to-end tool (get_meeting_action_items).

No real DB/LLM calls.
"""

from core.assistant_tools import AssistantToolExecutor
from core.tools.tools_meetings_requirements import _MeetingsRequirementsToolsMixin

_LLM_CONFIG = {
    "api_key": "fake-key",
    "model": "fake-model",
    "provider_cfg": {"client_type": "openai_compatible", "default_model": "fake-model"},
}

_REAL_MINUTES_MD = (
    "# Ata\n\n"
    "## Participantes\n\n- Fulano\n\n"
    "## Decisões Tomadas\n\n- Decisão A\n\n"
    "## Encaminhamentos / Action Items\n\n"
    "| # | Tarefa | Levantado por | Responsável | Prazo | Prioridade |\n"
    "|---|--------|---------------|-------------|-------|------------|\n"
    "| 1 | Enviar relatório | **F** | Fulano | 10/07 | 🔴 Alta |\n\n"
    "---\n*Ata gerada automaticamente pelo Process2Diagram — 08/07/2026*"
)


class TestSectionMatchesRealActionItemsHeading:
    def test_section_extracts_action_items_from_real_heading_text(self):
        class Fake(_MeetingsRequirementsToolsMixin):
            pass

        section = Fake()._section(
            _REAL_MINUTES_MD,
            "Encaminhamentos / Action Items", "Encaminhamentos",
            "Itens de Ação", "Action Items", "Ações",
        )
        assert "Enviar relatório" in section

    def test_old_alternate_names_alone_never_matched(self):
        """Documents WHY the bug existed: the pre-fix alternate names alone
        never matched the real heading — confirms the fix was necessary,
        not just cosmetic."""
        class Fake(_MeetingsRequirementsToolsMixin):
            pass

        section = Fake()._section(_REAL_MINUTES_MD, "Itens de Ação", "Action Items", "Ações")
        assert section == ""

    def test_get_meeting_action_items_returns_real_content_end_to_end(self):
        ex = AssistantToolExecutor(project_id="proj-1", llm_config=_LLM_CONFIG)
        ex._get_meetings = lambda: [
            {"id": "m1", "meeting_number": 1, "title": "Kickoff", "minutes_md": _REAL_MINUTES_MD},
        ]
        result = ex.get_meeting_action_items(meeting_number=1)
        assert "Enviar relatório" in result
