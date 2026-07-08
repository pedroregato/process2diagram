# tests/test_compare_meetings.py
"""
Tests for core/tools/tools_meeting_ops_calendar.py::compare_meetings()
(melhorias/avaliacao-proposta-assistente-20260708.md, proposta #11 —
"Comparador de Atas"): diffs participants/decisions/action items between
two specific meetings' minutes_md — distinct from compare_meeting_transcripts
(text-similarity duplicate detection).

No real DB/LLM calls.
"""

import streamlit as st

from core.assistant_tools import AssistantToolExecutor

_MD_A = """# Ata R1

## Participantes

- Fulano
- Beltrano

## Decisões Tomadas

- Aprovar orçamento
- Adiar contratação

## Encaminhamentos / Action Items

| # | Tarefa | Levantado por | Responsável | Prazo | Prioridade |
|---|--------|---------------|-------------|-------|------------|
| 1 | Enviar proposta | **F** | Fulano | 10/07 | Alta |
| 2 | Revisar contrato | **B** | Beltrano | 12/07 | Normal |
"""

_MD_B = """# Ata R2

## Participantes

- Fulano
- Ciclana

## Decisões Tomadas

- Aprovar orçamento
- Contratar fornecedor X

## Encaminhamentos / Action Items

| # | Tarefa | Levantado por | Responsável | Prazo | Prioridade |
|---|--------|---------------|-------------|-------|------------|
| 1 | Enviar proposta | **F** | Fulano | 10/07 | Alta |
| 2 | Assinar contrato | **F** | Fulano | 15/07 | Alta |
"""


def _executor(meetings):
    ex = AssistantToolExecutor(project_id="proj-1")
    ex._get_meetings = lambda: meetings
    return ex


class TestCompareMeetings:
    def setup_method(self):
        st.session_state.clear()

    def test_diff_identifies_added_removed_and_unchanged_per_category(self):
        ex = _executor([
            {"id": "m1", "meeting_number": 1, "title": "R1", "meeting_date": "2026-07-01", "minutes_md": _MD_A},
            {"id": "m2", "meeting_number": 2, "title": "R2", "meeting_date": "2026-07-08", "minutes_md": _MD_B},
        ])
        result = ex.compare_meetings(1, 2)
        assert "renderizada" in result.lower()

        widgets = st.session_state.get("_pending_widgets", [])
        assert len(widgets) == 1
        html = widgets[0]["html"]

        # Participants: Beltrano left, Ciclana joined, Fulano unchanged.
        assert "− Beltrano" in html
        assert "+ Ciclana" in html
        assert "− Fulano" not in html and "+ Fulano" not in html  # unchanged participant not printed
        assert "(1 sem alteração)" in html

        # Decisions.
        assert "− Adiar contratação" in html
        assert "+ Contratar fornecedor X" in html
        assert "Aprovar orçamento" not in html  # unchanged decision not printed verbatim

        # Action items — diffed by task text, not by full row.
        assert "− Revisar contrato" in html
        assert "+ Assinar contrato" in html
        assert "Enviar proposta" not in html  # unchanged task not printed verbatim

    def test_same_meeting_number_rejected(self):
        ex = _executor([{"id": "m1", "meeting_number": 1, "title": "R1", "minutes_md": _MD_A}])
        result = ex.compare_meetings(1, 1)
        assert "diferentes" in result.lower()
        assert "_pending_widgets" not in st.session_state

    def test_meeting_not_found(self):
        ex = _executor([{"id": "m1", "meeting_number": 1, "title": "R1", "minutes_md": _MD_A}])
        result = ex.compare_meetings(1, 99)
        assert "99" in result and "não encontrada" in result.lower()

    def test_meeting_without_minutes_md(self):
        ex = _executor([
            {"id": "m1", "meeting_number": 1, "title": "R1", "minutes_md": _MD_A},
            {"id": "m2", "meeting_number": 2, "title": "R2", "minutes_md": ""},
        ])
        result = ex.compare_meetings(1, 2)
        assert "não tem ata" in result.lower()
        assert "_pending_widgets" not in st.session_state

    def test_no_differences_reports_no_changes(self):
        ex = _executor([
            {"id": "m1", "meeting_number": 1, "title": "R1", "minutes_md": _MD_A},
            {"id": "m2", "meeting_number": 2, "title": "R2", "minutes_md": _MD_A},
        ])
        ex.compare_meetings(1, 2)
        html = st.session_state["_pending_widgets"][0]["html"]
        assert html.count("sem mudanças") == 3  # participants + decisions + action items
