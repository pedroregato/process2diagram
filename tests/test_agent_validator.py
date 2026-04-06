# tests/test_agent_validator.py
"""
Tests for agents/agent_validator.py — all four scoring dimensions.
No LLM calls; pure heuristic scoring.
"""

import pytest
from agents.agent_validator import AgentValidator
from core.knowledge_hub import BPMNValidationScore
from tests.conftest import step, edge, model


WEIGHTS_EQUAL = {"granularity": 5, "task_type": 5, "gateways": 5, "structural": 5}
WEIGHTS_GRAN_ONLY = {"granularity": 10, "task_type": 0, "gateways": 0, "structural": 0}
WEIGHTS_TYPE_ONLY = {"granularity": 0, "task_type": 10, "gateways": 0, "structural": 0}
WEIGHTS_GW_ONLY   = {"granularity": 0, "task_type": 0,  "gateways": 10, "structural": 0}
WEIGHTS_STR_ONLY  = {"granularity": 0, "task_type": 0,  "gateways": 0,  "structural": 10}


@pytest.fixture
def validator():
    return AgentValidator()


def words(n):
    """Return a transcript string of approximately n words."""
    return " ".join(["word"] * n)


# ── Granularity dimension ──────────────────────────────────────────────────────

class TestGranularity:
    def test_right_density_scores_ten(self, validator):
        # Target: 1 task per 40-100 words → 5 tasks for 250-word transcript
        tasks = [step(f"t{i}", f"Task {i}") for i in range(5)]
        m = model(*tasks, edges=[])
        sc = validator.score(m, words(250), WEIGHTS_GRAN_ONLY)
        assert sc.granularity == 10.0

    def test_too_few_tasks_scores_below_ten(self, validator):
        tasks = [step("t1", "Single Task")]
        m = model(*tasks, edges=[])
        sc = validator.score(m, words(500), WEIGHTS_GRAN_ONLY)
        assert sc.granularity < 10.0

    def test_too_many_tasks_scores_below_ten(self, validator):
        tasks = [step(f"t{i}", f"T{i}") for i in range(50)]
        m = model(*tasks, edges=[])
        sc = validator.score(m, words(100), WEIGHTS_GRAN_ONLY)
        assert sc.granularity < 10.0

    def test_zero_tasks_scores_zero(self, validator):
        # Events and gateways only → no tasks → 0
        events = [step("s", "Start", task_type="noneStartEvent"),
                  step("e", "End",   task_type="noneEndEvent")]
        m = model(*events, edges=[edge("s", "e")])
        sc = validator.score(m, words(100), WEIGHTS_GRAN_ONLY)
        assert sc.granularity == 0.0

    def test_n_tasks_excludes_events_and_gateways(self, validator):
        m = model(
            step("s",  "Start",    task_type="noneStartEvent"),
            step("t1", "Task One", task_type="userTask"),
            step("gw", "Gateway",  task_type="exclusiveGateway"),
            step("e",  "End",      task_type="noneEndEvent"),
            edges=[],
        )
        sc = validator.score(m, words(100), WEIGHTS_GRAN_ONLY)
        assert sc.n_tasks == 1
        assert sc.n_gateways == 1


# ── Task type dimension ────────────────────────────────────────────────────────

class TestTaskType:
    def test_service_task_with_keyword_scores_ten(self, validator):
        t = step("t", "Sistema processa pagamento", task_type="serviceTask")
        m = model(t)
        sc = validator.score(m, "transcript", WEIGHTS_TYPE_ONLY)
        assert sc.task_type == 10.0

    def test_user_task_with_service_keyword_scores_low(self, validator):
        t = step("t", "Sistema processa automaticamente", task_type="userTask")
        m = model(t)
        sc = validator.score(m, "transcript", WEIGHTS_TYPE_ONLY)
        assert sc.task_type <= 4.0   # should be 3.0

    def test_user_task_without_specific_keyword_scores_neutral(self, validator):
        t = step("t", "Revisar proposta", task_type="userTask")
        m = model(t)
        sc = validator.score(m, "transcript", WEIGHTS_TYPE_ONLY)
        assert sc.task_type == 6.0

    def test_specific_type_without_keyword_scores_seven(self, validator):
        t = step("t", "Verificar aprovação", task_type="serviceTask")
        m = model(t)
        sc = validator.score(m, "transcript", WEIGHTS_TYPE_ONLY)
        assert sc.task_type == 7.0

    def test_no_tasks_returns_neutral_five(self, validator):
        m = model(step("s", "Start", task_type="noneStartEvent"))
        sc = validator.score(m, "transcript", WEIGHTS_TYPE_ONLY)
        assert sc.task_type == 5.0


# ── Gateways dimension ────────────────────────────────────────────────────────

class TestGateways:
    def test_fully_labeled_xor_scores_ten(self, validator):
        gw = step("gw", "Check?", task_type="exclusiveGateway")
        m = model(gw, step("a", "A"), step("b", "B"),
                  edges=[edge("gw", "a", "Sim"), edge("gw", "b", "Não")])
        sc = validator.score(m, "transcript", WEIGHTS_GW_ONLY)
        assert sc.gateways == 10.0

    def test_partially_labeled_xor_scores_proportionally(self, validator):
        gw = step("gw", "Check?", task_type="exclusiveGateway")
        m = model(gw, step("a", "A"), step("b", "B"), step("c", "C"),
                  edges=[edge("gw", "a", "Sim"), edge("gw", "b", "Não"),
                         edge("gw", "c", "")])   # 2/3 labeled
        sc = validator.score(m, "transcript", WEIGHTS_GW_ONLY)
        assert sc.gateways == pytest.approx(10 * 2 / 3, rel=0.01)

    def test_and_with_join_scores_ten(self, validator):
        split = step("split", "Fork", task_type="parallelGateway")
        join  = step("join",  "Join", task_type="parallelGateway")
        m = model(step("s", "S"), split, step("a", "A"), step("b", "B"), join,
                  edges=[edge("s", "split"), edge("split", "a"), edge("split", "b"),
                         edge("a", "join"), edge("b", "join")])
        sc = validator.score(m, "transcript", WEIGHTS_GW_ONLY)
        assert sc.gateways == 10.0

    def test_and_without_join_scores_zero(self, validator):
        gw = step("gw", "Fork", task_type="parallelGateway")
        m = model(step("s", "S"), gw, step("a", "A"), step("b", "B"),
                  edges=[edge("s", "gw"), edge("gw", "a"), edge("gw", "b")])
        sc = validator.score(m, "transcript", WEIGHTS_GW_ONLY)
        assert sc.gateways == 0.0

    def test_no_gateways_returns_neutral_five(self, validator):
        m = model(step("a", "A"), step("b", "B"), edges=[edge("a", "b")])
        sc = validator.score(m, "transcript", WEIGHTS_GW_ONLY)
        assert sc.gateways == 5.0


# ── Structural dimension ───────────────────────────────────────────────────────

class TestStructural:
    def test_clean_model_scores_ten(self, validator):
        m = model(step("a", "A"), step("b", "B"), edges=[edge("a", "b")])
        sc = validator.score(m, "transcript", WEIGHTS_STR_ONLY)
        assert sc.structural == 10.0
        assert sc.n_structural_errors == 0
        assert sc.n_structural_warnings == 0

    def test_one_error_costs_2pt5(self, validator):
        # Dangling edge → 1 error
        m = model(step("a", "A"), edges=[edge("a", "ghost")])
        sc = validator.score(m, "transcript", WEIGHTS_STR_ONLY)
        assert sc.structural == pytest.approx(7.5, rel=0.01)
        assert sc.n_structural_errors == 1

    def test_four_errors_score_zero(self, validator):
        # 4+ errors → 0.0
        m = model(step("a", "A"),
                  edges=[edge("a", "x1"), edge("a", "x2"),
                         edge("a", "x3"), edge("a", "x4")])
        sc = validator.score(m, "transcript", WEIGHTS_STR_ONLY)
        assert sc.structural == 0.0

    def test_warning_costs_half_point(self, validator):
        # XOR with 1 unlabeled branch → 1 warning (0.5 penalty)
        gw = step("gw", "Check?", is_decision=True)
        m = model(gw, step("a", "A"), step("b", "B"),
                  edges=[edge("gw", "a", "Sim"), edge("gw", "b", "")])
        sc = validator.score(m, "transcript", WEIGHTS_STR_ONLY)
        assert sc.structural == pytest.approx(9.5, rel=0.01)
        assert sc.n_structural_warnings >= 1


# ── Weighted composite ────────────────────────────────────────────────────────

class TestWeightedScore:
    def test_zero_weight_dimension_excluded(self, validator):
        # 4 dangling edges → structural = 0.0 (maximum penalty)
        # With structural weight=5: the 0 drags weighted below the 3-dim average.
        # With structural weight=0: structural excluded → higher weighted.
        m = model(step("a", "A"),
                  edges=[edge("a", "x1"), edge("a", "x2"),
                         edge("a", "x3"), edge("a", "x4")])
        sc_with    = validator.score(m, "word " * 50, WEIGHTS_EQUAL)
        sc_without = validator.score(m, "word " * 50,
                                     {"granularity": 5, "task_type": 5,
                                      "gateways": 5, "structural": 0})
        assert sc_without.weighted > sc_with.weighted

    def test_score_returns_bpmn_validation_score_instance(self, validator):
        m = model(step("a", "A"))
        sc = validator.score(m, "transcript", WEIGHTS_EQUAL)
        assert isinstance(sc, BPMNValidationScore)

    def test_weighted_within_zero_ten_range(self, validator):
        m = model(step("a", "A"), step("b", "B"),
                  edges=[edge("a", "ghost"), edge("b", "nowhere")])
        sc = validator.score(m, "word " * 10, WEIGHTS_EQUAL)
        assert 0.0 <= sc.weighted <= 10.0
