# tests/test_pipeline_knowledge_extraction.py
"""
Tests for core/pipeline.py::run_knowledge_extraction() and the meeting_id
guard around its internal use inside run_pipeline() (PC137).

Regression guard for a real bug found 2026-07-06: pages/Pipeline.py's "Nova
Transcricao" flow (and core/batch_pipeline.py's new-file path) call
run_pipeline() BEFORE create_meeting() exists, so config["meeting_id"] was
never set. run_pipeline() unconditionally ran AgentKnowledgeExtractor with
meeting_id=None whenever run_knowledge_extractor was True (the default),
silently writing kh_entities/kh_processes rows with empty meeting_ids —
making Knowledge Graph correlations (entity<->process, entity<->entity)
permanently impossible for those rows, since pages/KnowledgeGraph.py computes
edges strictly from meeting_ids intersection. Confirmed on a real project
(100% of entities/processes had meeting_ids=[]).

Fix: run_pipeline() only fires the internal knowledge-extraction step when
config["meeting_id"] is already present (batch/backfill/reprocess flows that
operate on an existing meeting). Callers that create the meeting AFTER the
pipeline runs must call the new standalone run_knowledge_extraction()
themselves once the real meeting_id exists.
"""

from unittest.mock import patch, MagicMock

from core.pipeline import run_knowledge_extraction


class TestRunKnowledgeExtractionStandalone:
    def test_skips_cleanly_when_meeting_id_missing(self):
        calls = []
        run_knowledge_extraction(
            hub=MagicMock(), client_info={}, provider_cfg={}, output_lang="Auto-detect",
            meeting_id=None, project_id="proj-1",
            progress_callback=lambda step, status: calls.append((step, status)),
        )
        assert calls == [("Knowledge Hub", "skipped")]

    def test_calls_extractor_and_contradiction_detector_with_meeting_id(self):
        hub = MagicMock()
        with patch("agents.agent_knowledge_extractor.AgentKnowledgeExtractor") as MockExtractor, \
             patch("agents.agent_contradiction_detector.AgentContradictionDetector") as MockDetector:
            run_knowledge_extraction(
                hub, {"api_key": "k"}, {"client_type": "openai_compatible"}, "Auto-detect",
                meeting_id="mtg-1", project_id="proj-1",
                progress_callback=lambda *_: None,
            )
        MockExtractor.assert_called_once_with({"api_key": "k"}, {"client_type": "openai_compatible"})
        MockExtractor.return_value.run.assert_called_once_with(
            hub, "Auto-detect", meeting_id="mtg-1", project_id="proj-1",
        )
        MockDetector.return_value.run_for_meeting.assert_called_once_with("proj-1", "mtg-1")

    def test_skips_contradiction_detector_when_project_id_missing(self):
        hub = MagicMock()
        with patch("agents.agent_knowledge_extractor.AgentKnowledgeExtractor"), \
             patch("agents.agent_contradiction_detector.AgentContradictionDetector") as MockDetector:
            run_knowledge_extraction(
                hub, {}, {}, "Auto-detect",
                meeting_id="mtg-1", project_id=None,
                progress_callback=lambda *_: None,
            )
        MockDetector.return_value.run_for_meeting.assert_not_called()

    def test_extractor_exception_is_swallowed(self):
        calls = []
        with patch("agents.agent_knowledge_extractor.AgentKnowledgeExtractor",
                   side_effect=RuntimeError("boom")):
            run_knowledge_extraction(
                MagicMock(), {}, {}, "Auto-detect",
                meeting_id="mtg-1", project_id="proj-1",
                progress_callback=lambda step, status: calls.append((step, status)),
            )
        assert ("Knowledge Hub", "skipped") in calls

    def test_contradiction_detector_exception_is_swallowed(self):
        calls = []
        with patch("agents.agent_knowledge_extractor.AgentKnowledgeExtractor"), \
             patch("agents.agent_contradiction_detector.AgentContradictionDetector",
                   side_effect=RuntimeError("boom")):
            run_knowledge_extraction(
                MagicMock(), {}, {}, "Auto-detect",
                meeting_id="mtg-1", project_id="proj-1",
                progress_callback=lambda step, status: calls.append((step, status)),
            )
        assert ("Detecção de Contradições", "skipped") in calls


class TestRunPipelineMeetingIdGuard:
    """Exercises run_pipeline()'s "standard" branch with Orchestrator mocked
    out, to isolate the tail-end knowledge-extraction guard logic."""

    def _base_config(self, **overrides):
        config = {
            "client_info": {"api_key": "k"},
            "provider_cfg": {"client_type": "openai_compatible"},
            "output_language": "Auto-detect",
            "run_quality": False,
            "run_bpmn": False,
            "run_minutes": False,
            "run_requirements": False,
            "run_synthesizer": False,
            "n_bpmn_runs": 1,
            "bpmn_weights": {},
        }
        config.update(overrides)
        return config

    def test_internal_kh_extraction_skipped_without_meeting_id(self):
        """The exact PC137 scenario: run_knowledge_extractor=True (default)
        but no meeting_id yet (meeting not created at call time) — must NOT
        fire the internal call."""
        from core.pipeline import run_pipeline
        config = self._base_config(run_knowledge_extractor=True, project_id="proj-1")
        with patch("agents.orchestrator.Orchestrator") as MockOrch, \
             patch("core.pipeline.run_knowledge_extraction") as mock_kh:
            MockOrch.return_value.run.return_value = MagicMock()
            run_pipeline(MagicMock(), config, lambda *_: None)
        mock_kh.assert_not_called()

    def test_internal_kh_extraction_fires_when_meeting_id_present(self):
        """Backward-compat: batch/backfill/reprocess flows that already know
        meeting_id at call time must keep working exactly as before."""
        from core.pipeline import run_pipeline
        config = self._base_config(
            run_knowledge_extractor=True, meeting_id="mtg-1", project_id="proj-1",
        )
        with patch("agents.orchestrator.Orchestrator") as MockOrch, \
             patch("core.pipeline.run_knowledge_extraction") as mock_kh:
            MockOrch.return_value.run.return_value = MagicMock()
            run_pipeline(MagicMock(), config, lambda *_: None)
        mock_kh.assert_called_once()
        _, kwargs = mock_kh.call_args
        assert kwargs["meeting_id"] == "mtg-1"
        assert kwargs["project_id"] == "proj-1"

    def test_internal_kh_extraction_respects_disabled_flag(self):
        from core.pipeline import run_pipeline
        config = self._base_config(
            run_knowledge_extractor=False, meeting_id="mtg-1", project_id="proj-1",
        )
        with patch("agents.orchestrator.Orchestrator") as MockOrch, \
             patch("core.pipeline.run_knowledge_extraction") as mock_kh:
            MockOrch.return_value.run.return_value = MagicMock()
            run_pipeline(MagicMock(), config, lambda *_: None)
        mock_kh.assert_not_called()
