# tests/test_mermaid_generator.py
"""
Tests for agents/agent_mermaid.py — MermaidGenerator (pure Python, no LLM).
Covers sanitization, node/edge formatting, single-pool and multi-pool generation.
"""

import pytest
from agents.agent_mermaid import MermaidGenerator, generate_mermaid
from core.knowledge_hub import BPMNMessageFlow
from tests.conftest import step, edge, model, pool, collab


# ── sanitize_text ─────────────────────────────────────────────────────────────

class TestSanitizeText:
    def test_removes_accents(self):
        assert MermaidGenerator.sanitize_text("Aprovação") == "Aprovacao"

    def test_replaces_double_quotes(self):
        assert '"' not in MermaidGenerator.sanitize_text('say "hello"')

    def test_removes_forbidden_chars(self):
        result = MermaidGenerator.sanitize_text("step (A) [B]")
        assert "(" not in result
        assert "[" not in result

    def test_collapses_multiple_spaces(self):
        result = MermaidGenerator.sanitize_text("a   b")
        assert "  " not in result

    def test_empty_string_returns_step(self):
        assert MermaidGenerator.sanitize_text("") == "Step"

    def test_none_returns_step(self):
        assert MermaidGenerator.sanitize_text(None) == "Step"

    def test_whitespace_only_returns_step(self):
        assert MermaidGenerator.sanitize_text("   ") == "Step"


# ── format_node ───────────────────────────────────────────────────────────────

class TestFormatNode:
    def test_decision_node_uses_braces(self):
        s = step("gw", "Is approved?", is_decision=True)
        result = MermaidGenerator.format_node(s)
        assert 'gw{' in result

    def test_task_node_uses_brackets(self):
        s = step("t", "Review Document")
        result = MermaidGenerator.format_node(s)
        assert 't[' in result

    def test_start_event_uses_stadium_shape(self):
        s = step("s", "Inicio", task_type="noneStartEvent")
        result = MermaidGenerator.format_node(s)
        assert 's((' in result

    def test_end_event_uses_stadium_shape(self):
        s = step("e", "Fim", task_type="noneEndEvent")
        result = MermaidGenerator.format_node(s)
        assert 'e((' in result

    def test_generic_start_alias_uses_stadium_shape(self):
        s = step("s", "Start", task_type="start")
        result = MermaidGenerator.format_node(s)
        assert 's((' in result

    def test_id_prefix_prepended(self):
        s = step("t1", "Task")
        result = MermaidGenerator.format_node(s, id_prefix="p1_")
        assert result.startswith("    p1_t1")

    def test_custom_indent(self):
        s = step("t1", "Task")
        result = MermaidGenerator.format_node(s, indent="        ")
        assert result.startswith("        t1")

    def test_label_is_sanitized(self):
        s = step("t", "Aprovar (solicitação)")
        result = MermaidGenerator.format_node(s)
        assert "(" not in result.split('"')[1]  # no parens inside the quoted label


# ── format_edge ───────────────────────────────────────────────────────────────

class TestFormatEdge:
    def test_labeled_edge_uses_pipe_syntax(self):
        e = edge("a", "b", label="Sim")
        result = MermaidGenerator.format_edge(e)
        assert "-->|Sim|" in result

    def test_unlabeled_edge_uses_plain_arrow(self):
        e = edge("a", "b")
        result = MermaidGenerator.format_edge(e)
        assert "-->" in result
        assert "|" not in result

    def test_label_is_sanitized_in_edge(self):
        e = edge("a", "b", label="Não aprovado")
        result = MermaidGenerator.format_edge(e)
        assert "-->|Nao aprovado|" in result

    def test_src_and_tgt_prefix_applied(self):
        e = edge("t1", "t2")
        result = MermaidGenerator.format_edge(e, src_prefix="p1_", tgt_prefix="p1_")
        assert "p1_t1 --> p1_t2" in result


# ── generate — single-pool ────────────────────────────────────────────────────

class TestGenerateSingle:
    def test_starts_with_flowchart_directive(self):
        m = model(step("a", "A"), step("b", "B"), edges=[edge("a", "b")])
        result = MermaidGenerator.generate(m)
        assert result.startswith("flowchart")

    def test_default_direction_is_td(self):
        m = model(step("a", "A"))
        assert MermaidGenerator.generate(m).startswith("flowchart TD")

    def test_custom_direction_lr(self):
        m = model(step("a", "A"))
        assert MermaidGenerator.generate(m, direction="LR").startswith("flowchart LR")

    def test_includes_all_steps(self):
        m = model(step("a", "Alpha"), step("b", "Beta"))
        result = MermaidGenerator.generate(m)
        assert "a[" in result
        assert "b[" in result

    def test_includes_all_edges(self):
        m = model(step("a", "A"), step("b", "B"), step("c", "C"),
                  edges=[edge("a", "b"), edge("b", "c")])
        result = MermaidGenerator.generate(m)
        assert "a --> b" in result
        assert "b --> c" in result

    def test_decision_nodes_styled_yellow(self):
        gw = step("gw", "Check", is_decision=True)
        m = model(gw, step("a", "A"), step("b", "B"),
                  edges=[edge("gw", "a"), edge("gw", "b")])
        result = MermaidGenerator.generate(m)
        assert "style gw fill:#fff3cd" in result

    def test_event_nodes_rendered_as_stadium(self):
        m = model(
            step("s", "Start", task_type="noneStartEvent"),
            step("t", "Task"),
            step("e", "End", task_type="noneEndEvent"),
            edges=[edge("s", "t"), edge("t", "e")],
        )
        result = MermaidGenerator.generate(m)
        assert "s((" in result
        assert "e((" in result
        assert "t[" in result

    def test_labeled_edges_use_pipe_syntax(self):
        gw = step("gw", "Decision", is_decision=True)
        m = model(gw, step("a", "A"), step("b", "B"),
                  edges=[edge("gw", "a", "Sim"), edge("gw", "b", "Não")])
        result = MermaidGenerator.generate(m)
        assert "-->|Sim|" in result
        assert "-->|Nao|" in result   # accent stripped


# ── generate — multi-pool (collaboration) ─────────────────────────────────────

class TestGenerateMulti:
    def test_generates_subgraph_per_pool(self):
        p1 = pool("p1", "Cliente", [step("a", "Solicitar")], [])
        p2 = pool("p2", "Banco",   [step("b", "Aprovar")],   [])
        m = collab(p1, p2)
        result = MermaidGenerator.generate(m)
        assert "subgraph p1_pool" in result
        assert "subgraph p2_pool" in result

    def test_step_ids_prefixed_by_pool_index(self):
        p1 = pool("p1", "P1", [step("t", "Task")], [])
        m = collab(p1)
        result = MermaidGenerator.generate(m)
        assert "p1_t" in result

    def test_edges_within_pool_prefixed(self):
        p1 = pool("p1", "P1",
                  [step("a", "A"), step("b", "B")],
                  [edge("a", "b")])
        m = collab(p1)
        result = MermaidGenerator.generate(m)
        assert "p1_a --> p1_b" in result

    def test_message_flows_rendered_as_dashed(self):
        p1 = pool("p1", "Sender",   [step("s", "Send")],    [])
        p2 = pool("p2", "Receiver", [step("r", "Receive")], [])
        mf = BPMNMessageFlow("mf1", "p1", "s", "p2", "r", name="pedido")
        m = collab(p1, p2, message_flows=[mf])
        result = MermaidGenerator.generate(m)
        assert "p1_s -. pedido .-> p2_r" in result

    def test_message_flow_start_resolves_to_ev_start(self):
        p1 = pool("p1", "P1", [step("a", "A")], [])
        p2 = pool("p2", "P2", [step("b", "B")], [])
        mf = BPMNMessageFlow("mf1", "p1", "a", "p2", "start", name="msg")
        m = collab(p1, p2, message_flows=[mf])
        result = MermaidGenerator.generate(m)
        assert "p2_ev_start" in result

    def test_pool_name_sanitized(self):
        p1 = pool("p1", "Cliente (Pessoa Física)",
                  [step("a", "A")], [])
        m = collab(p1)
        result = MermaidGenerator.generate(m)
        assert "(" not in result.split('"')[1]  # parens stripped from pool name


# ── Module-level convenience function ─────────────────────────────────────────

class TestGenerateMermaidFunction:
    def test_returns_string(self):
        m = model(step("a", "A"))
        assert isinstance(generate_mermaid(m), str)

    def test_delegates_to_generator(self):
        m = model(step("a", "Alpha"))
        result = generate_mermaid(m)
        assert "Alpha" in result or "Alpha" in MermaidGenerator.sanitize_text("Alpha")
