# tests/test_bpmn_auto_repair.py
"""
Tests for modules/bpmn_auto_repair.py — all four repair passes.
No LLM calls; pure structural logic.
"""

import pytest
from modules.bpmn_auto_repair import repair_bpmn, RepairReport
from tests.conftest import step, edge, model, pool, collab


# ── Pass 1: Dangling edge removal ─────────────────────────────────────────────

class TestDanglingEdges:
    def test_removes_edge_with_missing_source(self):
        m = model(step("a", "A"), step("b", "B"),
                  edges=[edge("ghost", "b"), edge("a", "b")])
        repair_bpmn(m)
        assert len(m.edges) == 1
        assert m.edges[0].source == "a"

    def test_removes_edge_with_missing_target(self):
        m = model(step("a", "A"), step("b", "B"),
                  edges=[edge("a", "nowhere"), edge("a", "b")])
        repair_bpmn(m)
        assert len(m.edges) == 1

    def test_keeps_valid_edges(self):
        m = model(step("a", "A"), step("b", "B"),
                  edges=[edge("a", "b")])
        repair_bpmn(m)
        assert len(m.edges) == 1

    def test_report_counts_removed_edges(self):
        m = model(step("a", "A"),
                  edges=[edge("a", "x"), edge("y", "a")])
        r = repair_bpmn(m)
        assert r.count == 1
        assert "dangling" in r.repairs[0].lower()

    def test_no_repair_report_when_clean(self):
        m = model(step("a", "A"), step("b", "B"), edges=[edge("a", "b")])
        r = repair_bpmn(m)
        assert not any("dangling" in rep.lower() for rep in r.repairs)


# ── Pass 2: Isolated node removal ─────────────────────────────────────────────

class TestIsolatedNodes:
    def test_removes_isolated_node(self):
        m = model(step("a", "A"), step("b", "B"), step("x", "Orphan"),
                  edges=[edge("a", "b")])
        repair_bpmn(m)
        assert len(m.steps) == 2
        assert not any(s.id == "x" for s in m.steps)

    def test_preserves_connected_nodes(self):
        m = model(step("a", "A"), step("b", "B"), step("c", "C"),
                  edges=[edge("a", "b"), edge("b", "c")])
        repair_bpmn(m)
        assert len(m.steps) == 3

    def test_does_not_remove_when_two_steps_remain(self):
        # Safety: ≤2 steps → don't strip further
        m = model(step("a", "A"), step("b", "B"))
        repair_bpmn(m)
        assert len(m.steps) == 2

    def test_iterates_until_stable(self):
        # Two isolated nodes — both should be removed in successive passes
        m = model(step("a", "A"), step("b", "B"),
                  step("x", "X"), step("y", "Y"),
                  edges=[edge("a", "b")])
        repair_bpmn(m)
        assert len(m.steps) == 2

    def test_report_lists_each_isolated_node(self):
        m = model(step("a", "A"), step("b", "B"), step("x", "Orphan"),
                  edges=[edge("a", "b")])
        r = repair_bpmn(m)
        isolated_entries = [rep for rep in r.repairs if "isolated" in rep.lower()]
        assert len(isolated_entries) == 1
        assert "Orphan" in isolated_entries[0]


# ── Pass 3: XOR edge label inference ──────────────────────────────────────────

class TestXORLabels:
    def test_infers_nao_when_other_branch_is_sim(self):
        gw = step("gw", "Check?", is_decision=True)
        m = model(gw, step("y", "Yes"), step("n", "No"),
                  edges=[edge("gw", "y", label="Sim"), edge("gw", "n", label="")])
        repair_bpmn(m)
        unlabeled = next(e for e in m.edges if e.target == "n")
        assert unlabeled.label == "Não"

    def test_infers_sim_when_other_branch_is_nao(self):
        gw = step("gw", "Check?", is_decision=True)
        m = model(gw, step("y", "Yes"), step("n", "No"),
                  edges=[edge("gw", "n", label="Não"), edge("gw", "y", label="")])
        repair_bpmn(m)
        unlabeled = next(e for e in m.edges if e.target == "y")
        assert unlabeled.label == "Sim"

    def test_assigns_sim_nao_when_both_unlabeled(self):
        gw = step("gw", "Check?", is_decision=True)
        m = model(gw, step("y", "Yes"), step("n", "No"),
                  edges=[edge("gw", "y", label=""), edge("gw", "n", label="")])
        repair_bpmn(m)
        labels = {e.label for e in m.edges if e.source == "gw"}
        assert labels == {"Sim", "Não"}

    def test_assigns_generic_labels_for_three_branches(self):
        gw = step("gw", "Route?", is_decision=True)
        m = model(gw, step("a", "A"), step("b", "B"), step("c", "C"),
                  edges=[edge("gw", "a", ""), edge("gw", "b", ""), edge("gw", "c", "")])
        repair_bpmn(m)
        labels = {e.label for e in m.edges if e.source == "gw"}
        assert len(labels) == 3
        assert all(l.startswith("Opção") for l in labels)

    def test_does_not_relabel_already_labeled_xor(self):
        gw = step("gw", "Check?", is_decision=True)
        m = model(gw, step("y", "Yes"), step("n", "No"),
                  edges=[edge("gw", "y", "Aprovado"), edge("gw", "n", "Rejeitado")])
        repair_bpmn(m)
        labels = {e.label for e in m.edges if e.source == "gw"}
        assert labels == {"Aprovado", "Rejeitado"}

    def test_non_decision_node_not_labeled(self):
        # Regular task with two outgoing edges should not be relabeled
        m = model(step("a", "Task"), step("b", "B"), step("c", "C"),
                  edges=[edge("a", "b", ""), edge("a", "c", "")])
        repair_bpmn(m)
        assert all(e.label == "" for e in m.edges if e.source == "a")


# ── Pass 4: Redundant gateway bypass ──────────────────────────────────────────

class TestRedundantGatewayBypass:
    def test_bypasses_single_in_single_out_gateway(self):
        m = model(step("a", "A"), step("gw", "GW", is_decision=True), step("b", "B"),
                  edges=[edge("a", "gw"), edge("gw", "b")])
        repair_bpmn(m)
        assert len(m.steps) == 2
        assert not any(s.id == "gw" for s in m.steps)
        assert m.edges[0].source == "a"
        assert m.edges[0].target == "b"

    def test_does_not_bypass_join_gateway(self):
        # Multi-in gateway (join) with single out → NOT bypassed
        m = model(
            step("a", "A"), step("b", "B"),
            step("join", "Join", task_type="parallelGateway"),
            step("c", "C"),
            edges=[edge("a", "join"), edge("b", "join"), edge("join", "c")],
        )
        repair_bpmn(m)
        assert any(s.id == "join" for s in m.steps)

    def test_does_not_bypass_split_gateway(self):
        # Single-in, multi-out gateway → NOT bypassed (real decision)
        m = model(
            step("a", "A"),
            step("gw", "Decision", is_decision=True),
            step("b", "B"), step("c", "C"),
            edges=[edge("a", "gw"), edge("gw", "b"), edge("gw", "c")],
        )
        repair_bpmn(m)
        assert any(s.id == "gw" for s in m.steps)

    def test_bypasses_chain_of_redundant_gateways(self):
        # A → gw1(redundant) → gw2(redundant) → B
        m = model(
            step("a", "A"),
            step("gw1", "GW1", is_decision=True),
            step("gw2", "GW2", is_decision=True),
            step("b", "B"),
            edges=[edge("a", "gw1"), edge("gw1", "gw2"), edge("gw2", "b")],
        )
        repair_bpmn(m)
        assert len(m.steps) == 2
        assert m.edges[0].source == "a"
        assert m.edges[0].target == "b"

    def test_report_entry_per_bypassed_gateway(self):
        m = model(step("a", "A"), step("gw", "GW", is_decision=True), step("b", "B"),
                  edges=[edge("a", "gw"), edge("gw", "b")])
        r = repair_bpmn(m)
        bypass_entries = [rep for rep in r.repairs if "bypassed" in rep.lower()]
        assert len(bypass_entries) == 1


# ── Collaboration models ───────────────────────────────────────────────────────

class TestCollaborationRepair:
    def test_repairs_each_pool_independently(self):
        p1 = pool("p1", "Pool1",
                  steps=[step("a", "A"), step("b", "B"), step("x", "Orphan")],
                  edges=[edge("a", "b")])
        p2 = pool("p2", "Pool2",
                  steps=[step("c", "C"), step("d", "D")],
                  edges=[edge("c", "d")])
        m = collab(p1, p2)
        r = repair_bpmn(m)
        assert len(p1.steps) == 2
        assert len(p2.steps) == 2
        assert any("Pool1" in rep for rep in r.repairs)

    def test_does_not_cross_pool_boundaries(self):
        # Edge in p1 referencing p2 step ID should only be evaluated within p1
        p1 = pool("p1", "P1",
                  steps=[step("a", "A")],
                  edges=[edge("a", "c")])   # "c" exists in p2 but not p1
        p2 = pool("p2", "P2",
                  steps=[step("c", "C"), step("d", "D")],
                  edges=[edge("c", "d")])
        m = collab(p1, p2)
        repair_bpmn(m)
        # The dangling edge in p1 should be removed; p2 untouched
        assert len(p1.edges) == 0
        assert len(p2.edges) == 1


# ── Never raises ───────────────────────────────────────────────────────────────

class TestSafety:
    def test_empty_model_does_not_raise(self):
        m = model()
        r = repair_bpmn(m)
        assert isinstance(r, RepairReport)

    def test_single_step_model_does_not_raise(self):
        m = model(step("a", "Only"))
        r = repair_bpmn(m)
        assert isinstance(r, RepairReport)

    def test_report_bool_false_when_no_repairs(self):
        m = model(step("a", "A"), step("b", "B"), edges=[edge("a", "b")])
        r = repair_bpmn(m)
        assert not r
