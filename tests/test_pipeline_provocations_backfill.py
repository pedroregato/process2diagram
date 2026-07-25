# tests/test_pipeline_provocations_backfill.py
"""
Tests for core/pipeline.py::backfill_contradiction_provocations() (PC204).

Motivação: AgentProvocations.bridge_contradictions() (PC200) só era chamado
de dentro de run_provocations(), que só roda no momento do processamento de
UMA reunião. Reuniões processadas com "Gerar Provocações" desligado (padrão)
nunca tiveram a ponte executada, mesmo com kh_contradictions já populada por
AgentContradictionDetector. Este backfill roda a ponte em lote, sem LLM, sem
reprocessar nada — cobrindo o gap achado testando o projeto AURORA na prática.

Reusa exatamente a mesma lógica de dedup já testada implicitamente em
run_provocations() (PC200) — aqui construída uma vez para o lote inteiro, não
por reunião.
"""

from unittest.mock import patch, MagicMock

from core.pipeline import backfill_contradiction_provocations
from core.knowledge_hub import ProvocationItem


def _item(source_id: str) -> ProvocationItem:
    return ProvocationItem(
        kind="contradiction", title="t", body="b", question="q",
        contradiction_ref={"source_contradiction_id": source_id, "meeting_a_id": "m1", "meeting_b_id": "m2"},
    )


MEETINGS = [
    {"id": "m1", "meeting_number": 1, "title": "Reunião 1"},
    {"id": "m2", "meeting_number": 2, "title": "Reunião 2"},
    {"id": "m3", "meeting_number": 3, "title": "Reunião 3"},
]


class TestBackfillContradictionProvocations:
    def test_processes_all_meetings_and_saves_new_items(self):
        with patch("core.project_store.list_meetings", return_value=MEETINGS), \
             patch("core.project_store.list_provocations_by_project", return_value=[]), \
             patch("core.project_store.save_provocations", return_value=1) as mock_save, \
             patch("agents.agent_provocations.AgentProvocations.bridge_contradictions",
                   side_effect=lambda pid, mid: [_item(f"kh-{mid}")]):
            results = backfill_contradiction_provocations("proj-1")

        assert len(results) == 3
        assert all(r["saved"] == 1 and r["candidates"] == 1 and r["skipped_dup"] == 0 for r in results)
        assert mock_save.call_count == 3

    def test_dedup_built_once_not_per_meeting(self):
        """list_provocations_by_project deve ser chamada 1 vez pro lote inteiro,
        não 1 vez por reunião — otimização central desta função sobre a versão
        single-meeting já existente em run_provocations()."""
        with patch("core.project_store.list_meetings", return_value=MEETINGS), \
             patch("core.project_store.list_provocations_by_project", return_value=[]) as mock_list_prov, \
             patch("core.project_store.save_provocations", return_value=0), \
             patch("agents.agent_provocations.AgentProvocations.bridge_contradictions", return_value=[]):
            backfill_contradiction_provocations("proj-1")

        assert mock_list_prov.call_count == 1

    def test_dedup_skips_already_bridged_per_meeting(self):
        existing = [{
            "meeting_id": "m1", "kind": "contradiction",
            "grounding": {"source_contradiction_id": "kh-m1"},
        }]
        with patch("core.project_store.list_meetings", return_value=MEETINGS[:1]), \
             patch("core.project_store.list_provocations_by_project", return_value=existing), \
             patch("core.project_store.save_provocations") as mock_save, \
             patch("agents.agent_provocations.AgentProvocations.bridge_contradictions",
                   return_value=[_item("kh-m1")]):
            results = backfill_contradiction_provocations("proj-1")

        assert results[0]["candidates"] == 1
        assert results[0]["saved"] == 0
        assert results[0]["skipped_dup"] == 1
        mock_save.assert_not_called()  # nada novo -> nunca chama save_provocations

    def test_filters_by_meeting_ids(self):
        with patch("core.project_store.list_meetings", return_value=MEETINGS), \
             patch("core.project_store.list_provocations_by_project", return_value=[]), \
             patch("core.project_store.save_provocations", return_value=0), \
             patch("agents.agent_provocations.AgentProvocations.bridge_contradictions", return_value=[]) as mock_bridge:
            results = backfill_contradiction_provocations("proj-1", meeting_ids=["m2"])

        assert len(results) == 1
        assert results[0]["meeting_id"] == "m2"
        mock_bridge.assert_called_once_with("proj-1", "m2")

    def test_empty_meeting_ids_filter_yields_no_results(self):
        with patch("core.project_store.list_meetings", return_value=MEETINGS), \
             patch("core.project_store.list_provocations_by_project", return_value=[]), \
             patch("core.project_store.save_provocations"), \
             patch("agents.agent_provocations.AgentProvocations.bridge_contradictions", return_value=[]):
            results = backfill_contradiction_provocations("proj-1", meeting_ids=["nonexistent"])

        assert results == []

    def test_isolated_error_does_not_abort_other_meetings(self):
        def _bridge(pid, mid):
            if mid == "m2":
                raise RuntimeError("kaboom")
            return []

        with patch("core.project_store.list_meetings", return_value=MEETINGS), \
             patch("core.project_store.list_provocations_by_project", return_value=[]), \
             patch("core.project_store.save_provocations", return_value=0), \
             patch("agents.agent_provocations.AgentProvocations.bridge_contradictions", side_effect=_bridge):
            results = backfill_contradiction_provocations("proj-1")

        assert len(results) == 3  # todas as 3 reuniões aparecem no resultado
        by_id = {r["meeting_id"]: r for r in results}
        assert "error" in by_id["m2"] and "kaboom" in by_id["m2"]["error"]
        assert "error" not in by_id["m1"] and "error" not in by_id["m3"]

    def test_progress_callback_invoked_per_meeting(self):
        calls = []
        with patch("core.project_store.list_meetings", return_value=MEETINGS), \
             patch("core.project_store.list_provocations_by_project", return_value=[]), \
             patch("core.project_store.save_provocations", return_value=0), \
             patch("agents.agent_provocations.AgentProvocations.bridge_contradictions", return_value=[]):
            backfill_contradiction_provocations(
                "proj-1", progress_callback=lambda i, total, row: calls.append((i, total, row["meeting_id"]))
            )

        assert calls == [(0, 3, "m1"), (1, 3, "m2"), (2, 3, "m3")]

    def test_no_progress_callback_is_optional(self):
        with patch("core.project_store.list_meetings", return_value=MEETINGS), \
             patch("core.project_store.list_provocations_by_project", return_value=[]), \
             patch("core.project_store.save_provocations", return_value=0), \
             patch("agents.agent_provocations.AgentProvocations.bridge_contradictions", return_value=[]):
            results = backfill_contradiction_provocations("proj-1")  # sem progress_callback, não deve lançar

        assert len(results) == 3

    def test_no_meetings_in_project_returns_empty_list(self):
        with patch("core.project_store.list_meetings", return_value=[]), \
             patch("core.project_store.list_provocations_by_project", return_value=[]):
            results = backfill_contradiction_provocations("proj-1")

        assert results == []
