# tests/test_bpmn_structural_validator.py
"""
Tests for modules/bpmn_structural_validator.py — all six structural checks.
No LLM calls; pure graph-theory logic.
"""

import pytest
from modules.bpmn_structural_validator import validate_bpmn_structure, BPMNIssue
from tests.conftest import step, edge, model, pool, collab


def severities(issues):
    return [i.severity for i in issues]


def errors(issues):
    return [i for i in issues if i.severity == "error"]


def warnings(issues):
    return [i for i in issues if i.severity == "warning"]


def infos(issues):
    return [i for i in issues if i.severity == "info"]


# ── Clean model produces no issues ────────────────────────────────────────────

class TestCleanModel:
    def test_simple_linear_flow_has_no_issues(self):
        m = model(step("a", "A"), step("b", "B"), step("c", "C"),
                  edges=[edge("a", "b"), edge("b", "c")])
        assert validate_bpmn_structure(m) == []

    def test_empty_model_has_no_issues(self):
        m = model()
        assert validate_bpmn_structure(m) == []

    def test_single_step_has_no_issues(self):
        m = model(step("a", "Solo"))
        assert validate_bpmn_structure(m) == []


# ── Check 1: Dangling edge references ─────────────────────────────────────────

class TestDanglingEdges:
    def test_missing_source_raises_error(self):
        m = model(step("b", "B"), edges=[edge("ghost", "b")])
        issues = validate_bpmn_structure(m)
        assert any(i.severity == "error" and "ghost" in i.message for i in issues)

    def test_missing_target_raises_error(self):
        m = model(step("a", "A"), edges=[edge("a", "nowhere")])
        issues = validate_bpmn_structure(m)
        assert any(i.severity == "error" and "nowhere" in i.message for i in issues)

    def test_valid_edges_no_error(self):
        m = model(step("a", "A"), step("b", "B"), edges=[edge("a", "b")])
        assert not errors(validate_bpmn_structure(m))


# ── Check 2: Isolated nodes ───────────────────────────────────────────────────

class TestIsolatedNodes:
    def test_isolated_node_is_error(self):
        m = model(step("a", "A"), step("b", "B"), step("x", "Orphan"),
                  edges=[edge("a", "b")])
        issues = validate_bpmn_structure(m)
        assert any(i.severity == "error" and "x" in (i.element_id or "") for i in issues)

    def test_no_error_when_single_node(self):
        m = model(step("a", "Only"))
        assert not errors(validate_bpmn_structure(m))

    def test_all_connected_no_isolated_error(self):
        m = model(step("a", "A"), step("b", "B"), step("c", "C"),
                  edges=[edge("a", "b"), edge("b", "c")])
        assert not any("isolated" in i.message.lower() for i in validate_bpmn_structure(m))


# ── Check 3: Unreachable nodes ────────────────────────────────────────────────

class TestUnreachableNodes:
    def test_disconnected_subgraph_is_error(self):
        # Main flow: A → B
        # Isolated cycle: D → E → D  (D and E have incoming edges so are not roots;
        #                              they are unreachable from A via BFS)
        m = model(step("a", "A"), step("b", "B"), step("d", "D"), step("e", "E"),
                  edges=[edge("a", "b"), edge("d", "e"), edge("e", "d")])
        issues = validate_bpmn_structure(m)
        unreachable = [i for i in issues if "unreachable" in i.message.lower()]
        assert unreachable

    def test_fully_connected_dag_no_unreachable(self):
        m = model(step("a", "A"), step("b", "B"), step("c", "C"),
                  edges=[edge("a", "b"), edge("a", "c")])
        assert not any("unreachable" in i.message.lower()
                       for i in validate_bpmn_structure(m))


# ── Check 4: XOR gateway missing labels ───────────────────────────────────────

class TestXORMissingLabels:
    def test_unlabeled_xor_branch_is_warning(self):
        gw = step("gw", "Approve?", is_decision=True)
        m = model(gw, step("y", "Yes"), step("n", "No"),
                  edges=[edge("gw", "y", "Sim"), edge("gw", "n", "")])
        issues = validate_bpmn_structure(m)
        assert any(i.severity == "warning" and "gw" in (i.element_id or "")
                   for i in issues)

    def test_fully_labeled_xor_no_warning(self):
        gw = step("gw", "Approve?", is_decision=True)
        m = model(gw, step("y", "Yes"), step("n", "No"),
                  edges=[edge("gw", "y", "Sim"), edge("gw", "n", "Não")])
        assert not any(i.severity == "warning" and "label" in i.message.lower()
                       for i in validate_bpmn_structure(m))

    def test_xor_with_single_outgoing_not_checked_for_labels(self):
        # Single outgoing → it's a trivial gateway, not a split — no label warning
        gw = step("gw", "GW", is_decision=True)
        m = model(step("a", "A"), gw, step("b", "B"),
                  edges=[edge("a", "gw"), edge("gw", "b")])
        label_warnings = [i for i in validate_bpmn_structure(m)
                          if "label" in i.message.lower()]
        assert not label_warnings


# ── Check 5: AND / OR split without join ──────────────────────────────────────

class TestAndOrMissingJoin:
    def test_parallel_split_without_join_is_warning(self):
        gw = step("gw", "Fork", task_type="parallelGateway")
        m = model(step("start", "Start"), gw, step("a", "A"), step("b", "B"),
                  edges=[edge("start", "gw"), edge("gw", "a"), edge("gw", "b")])
        issues = validate_bpmn_structure(m)
        assert any(i.severity == "warning" and "join" in i.message.lower() for i in issues)

    def test_parallel_split_with_join_no_warning(self):
        split = step("split", "Fork", task_type="parallelGateway")
        join  = step("join",  "Join", task_type="parallelGateway")
        m = model(step("s", "Start"), split, step("a", "A"), step("b", "B"), join,
                  edges=[
                      edge("s", "split"),
                      edge("split", "a"), edge("split", "b"),
                      edge("a", "join"), edge("b", "join"),
                  ])
        assert not any("join" in i.message.lower() for i in validate_bpmn_structure(m))

    def test_inclusive_split_without_join_is_warning(self):
        gw = step("gw", "OR-Fork", task_type="inclusiveGateway")
        m = model(step("s", "S"), gw, step("a", "A"), step("b", "B"),
                  edges=[edge("s", "gw"), edge("gw", "a"), edge("gw", "b")])
        issues = validate_bpmn_structure(m)
        assert any("OR" in i.message and i.severity == "warning" for i in issues)


# ── Check 6: Redundant decision (single outgoing) ─────────────────────────────

class TestRedundantGateway:
    def test_single_outgoing_gateway_is_info(self):
        gw = step("gw", "Unnecessary GW", is_decision=True)
        m = model(step("a", "A"), gw, step("b", "B"),
                  edges=[edge("a", "gw"), edge("gw", "b")])
        issues = validate_bpmn_structure(m)
        assert any(i.severity == "info" and "gw" in (i.element_id or "")
                   for i in issues)

    def test_multi_outgoing_gateway_no_redundancy_info(self):
        gw = step("gw", "Real Decision", is_decision=True)
        m = model(step("a", "A"), gw, step("b", "B"), step("c", "C"),
                  edges=[edge("a", "gw"), edge("gw", "b"), edge("gw", "c")])
        redundancy = [i for i in validate_bpmn_structure(m)
                      if i.severity == "info" and "redundant" in i.message.lower()]
        assert not redundancy


# ── Collaboration models ───────────────────────────────────────────────────────

class TestCollaborationValidation:
    def test_issues_prefixed_with_pool_name(self):
        # Isolated node in pool "Banco"
        p1 = pool("p1", "Cliente",
                  steps=[step("a", "A"), step("b", "B")],
                  edges=[edge("a", "b")])
        p2 = pool("p2", "Banco",
                  steps=[step("c", "C"), step("d", "D"), step("x", "Orphan")],
                  edges=[edge("c", "d")])
        m = collab(p1, p2)
        issues = validate_bpmn_structure(m)
        assert any("Banco" in i.message for i in issues)
        assert not any("Cliente" in i.message for i in issues)

    def test_clean_collaboration_has_no_issues(self):
        p1 = pool("p1", "P1",
                  steps=[step("a", "A"), step("b", "B")], edges=[edge("a", "b")])
        p2 = pool("p2", "P2",
                  steps=[step("c", "C"), step("d", "D")], edges=[edge("c", "d")])
        m = collab(p1, p2)
        assert validate_bpmn_structure(m) == []


# ── Never raises ───────────────────────────────────────────────────────────────

class TestSafety:
    def test_returns_list_always(self):
        assert isinstance(validate_bpmn_structure(model()), list)

    def test_returns_bpmn_issue_objects(self):
        m = model(step("a", "A"), edges=[edge("a", "ghost")])
        issues = validate_bpmn_structure(m)
        assert all(isinstance(i, BPMNIssue) for i in issues)
