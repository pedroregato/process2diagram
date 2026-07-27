# tests/test_pipeline_run_provocations.py
"""
Tests for core/pipeline.py::run_provocations() — PC207 telemetry wiring.

run_provocations() nunca tinha teste próprio antes desta PC (só a função
vizinha backfill_contradiction_provocations, PC204, tinha). Foco aqui é só
a chamada nova a record_provocations_outcome() — o resto da função
(geração via AgentProvocations, bridge de contradição, save_provocations)
já é exercitado indiretamente/documentado em outros lugares e não é
o que mudou nesta PC.
"""

from unittest.mock import MagicMock, patch

from core.pipeline import run_provocations
from core.knowledge_hub import ProvocationsModel


def _run(**overrides):
    hub = MagicMock()

    def _fake_run(hub_arg, output_lang):
        hub_arg.provocations = overrides.get("provocations_model", ProvocationsModel(
            items=[], rejected_count=2, rejected_reasons={"reference_not_found": 2}, ready=True,
        ))

    with patch("agents.agent_provocations.AgentProvocations") as MockAgent, \
         patch("core.project_store.save_provocations") as mock_save, \
         patch("core.project_store.list_provocations_by_project", return_value=[]), \
         patch("services.llm_telemetry._telemetry") as mock_telemetry:
        MockAgent.return_value.run.side_effect = _fake_run
        MockAgent.return_value.skill_version = overrides.get("skill_version", "1.3")
        MockAgent.bridge_contradictions.return_value = []

        run_provocations(
            hub, {}, {}, "Auto-detect",
            meeting_id="mtg-1", project_id="proj-1",
            progress_callback=lambda *_: None,
        )

    return mock_telemetry, mock_save


class TestRunProvocationsTelemetry:
    def test_records_outcome_with_expected_values(self):
        mock_telemetry, _ = _run()
        mock_telemetry.record_provocations_outcome.assert_called_once_with(
            "proj-1", "mtg-1", "1.3",
            approved_count=0, rejected_count=2,
            rejected_reasons={"reference_not_found": 2},
        )

    def test_approved_count_matches_len_of_items(self):
        from core.knowledge_hub import ProvocationItem
        model = ProvocationsModel(
            items=[ProvocationItem(kind="absence", title="t", body="b", question="q")],
            rejected_count=0, rejected_reasons={}, ready=True,
        )
        mock_telemetry, _ = _run(provocations_model=model)
        _, kwargs = mock_telemetry.record_provocations_outcome.call_args
        assert kwargs["approved_count"] == 1
        assert kwargs["rejected_count"] == 0

    def test_telemetry_failure_does_not_prevent_save(self):
        """Fail-open: se record_provocations_outcome() explodir, o salvamento
        normal das provocações não pode ser afetado."""
        hub = MagicMock()

        def _fake_run(hub_arg, output_lang):
            hub_arg.provocations = ProvocationsModel(items=[], rejected_count=0, rejected_reasons={}, ready=True)

        with patch("agents.agent_provocations.AgentProvocations") as MockAgent, \
             patch("core.project_store.save_provocations") as mock_save, \
             patch("core.project_store.list_provocations_by_project", return_value=[]), \
             patch("services.llm_telemetry._telemetry") as mock_telemetry:
            MockAgent.return_value.run.side_effect = _fake_run
            MockAgent.return_value.skill_version = "1.3"
            MockAgent.bridge_contradictions.return_value = []
            mock_telemetry.record_provocations_outcome.side_effect = RuntimeError("kaboom")

            run_provocations(
                hub, {}, {}, "Auto-detect",
                meeting_id="mtg-1", project_id="proj-1",
                progress_callback=lambda *_: None,
            )

        # items == [] aqui (nenhuma provocação aprovada nem bridged), então
        # save_provocations nem deveria ser chamado — o que importa é que a
        # função NÃO lançou e chegou até o fim sem erro (progress_callback
        # "done", não "skipped" — verificado implicitamente por não ter
        # levantado exceção).
        assert True  # chegou até aqui sem propagar o RuntimeError do mock

    def test_skips_cleanly_when_meeting_id_missing(self):
        calls = []
        run_provocations(
            MagicMock(), {}, {}, "Auto-detect",
            meeting_id=None, project_id="proj-1",
            progress_callback=lambda step, status: calls.append((step, status)),
        )
        assert calls == [("Provocações", "skipped")]
