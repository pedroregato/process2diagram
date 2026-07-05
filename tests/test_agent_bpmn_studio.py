# tests/test_agent_bpmn_studio.py
"""
Tests for agents/agent_bpmn_studio.py::generate_bpmn_from_description().

No LLM calls, no Streamlit — AgentBPMN.run() and AgentValidator.score() are
mocked at the class level.
"""

from unittest.mock import patch

from agents.agent_bpmn import AgentBPMN
from agents.agent_bpmn_studio import generate_bpmn_from_description
from core.knowledge_hub import BPMNModel, BPMNValidationScore

_CLIENT_INFO = {"api_key": "fake"}
_PROVIDER_CFG = {"client_type": "openai_compatible", "default_model": "fake-model"}


def _make_fake_run(skip_cache_log, name_by_call):
    """Builds a fake AgentBPMN.run() that records `_lg_skip_cache` at call
    time and tags hub.bpmn with a distinct name per call."""
    call_count = {"n": 0}

    def _fake_run(self, hub, output_language="Auto-detect"):
        skip_cache_log.append(getattr(self, "_lg_skip_cache", False))
        i = call_count["n"]
        call_count["n"] += 1
        hub.bpmn = BPMNModel(name=name_by_call[i], steps=[], edges=[])
        return hub

    return _fake_run


class TestTournamentCacheBypass:
    def test_skip_cache_is_set_on_every_tournament_pass(self):
        """
        PC118 regression: reusing one AgentBPMN across N tournament passes
        without bypassing the semantic cache means passes 2..N would replay
        pass 1's cached completion (identical prompt → identical cache hash).
        `_lg_skip_cache` must be True for every pass, not just conceptually
        set once and forgotten.
        """
        skip_cache_log: list = []
        fake_run = _make_fake_run(skip_cache_log, ["A", "B", "C"])

        with patch.object(AgentBPMN, "run", fake_run), \
             patch("agents.agent_bpmn_studio.AgentValidator.score") as mock_score:
            mock_score.return_value = BPMNValidationScore(weighted=5.0)
            generate_bpmn_from_description(
                "descrição de processo de teste",
                _CLIENT_INFO, _PROVIDER_CFG,
                run_nlp=False, n_runs=3,
            )

        assert skip_cache_log == [True, True, True]

    def test_best_scoring_candidate_wins(self):
        fake_run = _make_fake_run([], ["worst", "best", "middle"])
        scores = iter([
            BPMNValidationScore(weighted=3.0),
            BPMNValidationScore(weighted=9.0),
            BPMNValidationScore(weighted=6.0),
        ])

        with patch.object(AgentBPMN, "run", fake_run), \
             patch("agents.agent_bpmn_studio.AgentValidator.score",
                   side_effect=lambda *a, **k: next(scores)):
            hub = generate_bpmn_from_description(
                "descrição de processo de teste",
                _CLIENT_INFO, _PROVIDER_CFG,
                run_nlp=False, n_runs=3,
            )

        assert hub.bpmn.name == "best"
        assert hub.validation.bpmn_score.weighted == 9.0
        assert hub.validation.n_bpmn_runs == 3

    def test_partial_failure_does_not_abort_tournament(self):
        call_count = {"n": 0}

        def _fake_run(self, hub, output_language="Auto-detect"):
            i = call_count["n"]
            call_count["n"] += 1
            if i == 1:
                raise ValueError("simulated extraction failure")
            hub.bpmn = BPMNModel(name=f"run{i}", steps=[], edges=[])
            return hub

        with patch.object(AgentBPMN, "run", _fake_run), \
             patch("agents.agent_bpmn_studio.AgentValidator.score") as mock_score:
            mock_score.return_value = BPMNValidationScore(weighted=5.0)
            hub = generate_bpmn_from_description(
                "descrição de processo de teste",
                _CLIENT_INFO, _PROVIDER_CFG,
                run_nlp=False, n_runs=3,
            )

        assert hub.validation.n_bpmn_runs == 2

    def test_all_failures_raise_last_error(self):
        def _fake_run(self, hub, output_language="Auto-detect"):
            raise RuntimeError("boom")

        with patch.object(AgentBPMN, "run", _fake_run):
            try:
                generate_bpmn_from_description(
                    "descrição de processo de teste",
                    _CLIENT_INFO, _PROVIDER_CFG,
                    run_nlp=False, n_runs=2,
                )
                assert False, "expected RuntimeError"
            except RuntimeError as exc:
                assert "boom" in str(exc)


class TestPhaseDetailFlag:
    """
    PC127 regression: "Detalhar uma fase" passes a single callActivity's
    documentation (not a full process description) into the exact same
    generate_bpmn_from_description() used for the main generation. That short
    text often contains collaboration vocabulary ("fornecedor", "concorrência")
    that legitimately describes what the phase deals with — but the process-
    level canonical-pattern/collaboration heuristics can't tell that apart from
    a real multi-org process description, and hallucinate a brand new 2-pool
    process around the one phase instead of detailing its internal steps.
    is_phase_detail=True must flip the two flags AgentBPMN.run()/build_prompt()
    check to suppress both mechanisms.
    """

    def test_is_phase_detail_sets_flags_on_agent_instance(self):
        captured_flags = {}

        def _fake_run(self, hub, output_language="Auto-detect"):
            captured_flags["skip_canonical_pattern"] = getattr(self, "_skip_canonical_pattern", False)
            captured_flags["force_single_pool"] = getattr(self, "_force_single_pool", False)
            hub.bpmn = BPMNModel(name="detail", steps=[], edges=[])
            return hub

        with patch.object(AgentBPMN, "run", _fake_run), \
             patch("agents.agent_bpmn_studio.AgentValidator.score") as mock_score:
            mock_score.return_value = BPMNValidationScore(weighted=5.0)
            generate_bpmn_from_description(
                "Receber relatórios do fornecedor, validar e aprovar pagamento.",
                _CLIENT_INFO, _PROVIDER_CFG,
                run_nlp=False, n_runs=1, is_phase_detail=True,
            )

        assert captured_flags == {"skip_canonical_pattern": True, "force_single_pool": True}

    def test_default_call_leaves_flags_unset(self):
        captured_flags = {}

        def _fake_run(self, hub, output_language="Auto-detect"):
            captured_flags["skip_canonical_pattern"] = getattr(self, "_skip_canonical_pattern", False)
            captured_flags["force_single_pool"] = getattr(self, "_force_single_pool", False)
            hub.bpmn = BPMNModel(name="main", steps=[], edges=[])
            return hub

        with patch.object(AgentBPMN, "run", _fake_run), \
             patch("agents.agent_bpmn_studio.AgentValidator.score") as mock_score:
            mock_score.return_value = BPMNValidationScore(weighted=5.0)
            generate_bpmn_from_description(
                "Processo completo de contratação de fornecedor.",
                _CLIENT_INFO, _PROVIDER_CFG,
                run_nlp=False, n_runs=1,
            )

        assert captured_flags == {"skip_canonical_pattern": False, "force_single_pool": False}
