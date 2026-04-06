# agents/agent_mermaid.py
# ─────────────────────────────────────────────────────────────────────────────
# MermaidGenerator — pure-Python Mermaid flowchart generator, no LLM.
#
# Handles both single-pool and multi-pool (collaboration) BPMNModels.
# Used by:
#   - agent_bpmn.py   → stores hub.bpmn.mermaid during extraction
#   - export_tab.py   → generate_mermaid(hub.bpmn) for .mmd download
#   - bpmn_tabs.py    → render_mermaid_block(hub.bpmn.mermaid)
# ─────────────────────────────────────────────────────────────────────────────

import re
from typing import Optional
from core.knowledge_hub import BPMNModel, BPMNStep, BPMNEdge


# Event task_type values → rendered as stadium shape (("label"))
_EVENT_TASK_TYPES = {
    "noneStartEvent", "startMessageEvent", "startTimerEvent",
    "noneEndEvent", "endMessageEvent", "errorEndEvent",
    "intermediateTimerCatchEvent", "intermediateMessageCatchEvent",
    "intermediateMessageThrowEvent",
    # Legacy / generic aliases the LLM sometimes emits
    "startEvent", "endEvent", "start", "end",
}


class MermaidGenerator:
    """Generates Mermaid flowchart syntax from a BPMNModel."""

    # ── Character maps ────────────────────────────────────────────────────────

    ACENTOS_MAP = {
        'á': 'a', 'à': 'a', 'ã': 'a', 'â': 'a', 'ä': 'a',
        'é': 'e', 'è': 'e', 'ê': 'e', 'ë': 'e',
        'í': 'i', 'ì': 'i', 'î': 'i', 'ï': 'i',
        'ó': 'o', 'ò': 'o', 'õ': 'o', 'ô': 'o', 'ö': 'o',
        'ú': 'u', 'ù': 'u', 'û': 'u', 'ü': 'u',
        'ç': 'c', 'ñ': 'n',
        'Á': 'A', 'À': 'A', 'Ã': 'A', 'Â': 'A', 'Ä': 'A',
        'É': 'E', 'È': 'E', 'Ê': 'E', 'Ë': 'E',
        'Í': 'I', 'Ì': 'I', 'Î': 'I', 'Ï': 'I',
        'Ó': 'O', 'Ò': 'O', 'Õ': 'O', 'Ô': 'O', 'Ö': 'O',
        'Ú': 'U', 'Ù': 'U', 'Û': 'U', 'Ü': 'U',
        'Ç': 'C', 'Ñ': 'N',
    }
    PROIBIDOS_PATTERN = r'[()\[\]{}/\\:;|<>]'

    # ── Public API ────────────────────────────────────────────────────────────

    @classmethod
    def generate(cls, model: BPMNModel, direction: str = "TD") -> str:
        """
        Generate a complete Mermaid flowchart string from *model*.

        Args:
            model:     BPMNModel (single-pool or collaboration).
            direction: Mermaid direction — "TD" (top-down) or "LR" (left-right).
                       mermaid_renderer.py fetches both anyway, so this only
                       affects the initial/default orientation.
        """
        if model.is_collaboration and model.pool_models:
            return cls._generate_multi(model, direction)
        return cls._generate_single(model, direction)

    # ── Formatters (usable standalone) ───────────────────────────────────────

    @classmethod
    def sanitize_text(cls, text: Optional[str]) -> str:
        """Remove/replace characters that break Mermaid syntax."""
        if not text:
            return "Step"
        for acento, sem in cls.ACENTOS_MAP.items():
            text = text.replace(acento, sem)
        text = text.replace('"', "'")
        text = re.sub(cls.PROIBIDOS_PATTERN, " ", text)
        text = re.sub(r' {2,}', " ", text)
        return text.strip() or "Step"

    @classmethod
    def format_node(cls, step: BPMNStep, id_prefix: str = "",
                    indent: str = "    ") -> str:
        """Format a single BPMN step as a Mermaid node line."""
        node_id = id_prefix + step.id
        label   = cls.sanitize_text(step.title)
        if step.is_decision:
            return f'{indent}{node_id}{{"{label}"}}'
        if step.task_type in _EVENT_TASK_TYPES:
            return f'{indent}{node_id}(("{label}"))'
        return f'{indent}{node_id}["{label}"]'

    @classmethod
    def format_edge(cls, edge: BPMNEdge, src_prefix: str = "",
                    tgt_prefix: str = "", indent: str = "    ") -> str:
        """Format a single BPMN edge as a Mermaid arrow line."""
        source = src_prefix + edge.source
        target = tgt_prefix + edge.target
        if edge.label:
            safe = cls.sanitize_text(edge.label)
            if safe and safe != "Step":
                return f'{indent}{source} -->|{safe}| {target}'
        return f'{indent}{source} --> {target}'

    # ── Internal generators ───────────────────────────────────────────────────

    @classmethod
    def _generate_single(cls, model: BPMNModel, direction: str) -> str:
        lines = [f"flowchart {direction}"]
        for step in model.steps:
            lines.append(cls.format_node(step))
        for edge in model.edges:
            lines.append(cls.format_edge(edge))
        for step in model.steps:
            if step.is_decision:
                lines.append(f"    style {step.id} fill:#fff3cd,stroke:#f59e0b")
        return "\n".join(lines)

    @classmethod
    def _generate_multi(cls, model: BPMNModel, direction: str) -> str:
        lines = [f"flowchart {direction}"]

        pool_prefix: dict[str, str] = {}
        for i, pm in enumerate(model.pool_models):
            prefix = f"p{i + 1}_"
            pool_prefix[pm.pool_id] = prefix
            pool_name = cls.sanitize_text(pm.name)
            lines.append(f'    subgraph {prefix}pool["{pool_name}"]')
            for step in pm.steps:
                lines.append(cls.format_node(step, id_prefix=prefix, indent="        "))
            for edge in pm.edges:
                lines.append(cls.format_edge(
                    edge, src_prefix=prefix, tgt_prefix=prefix, indent="        "))
            lines.append("    end")

        # Cross-pool message flows as dashed arrows
        for mf in model.message_flows_data:
            src_pfx = pool_prefix.get(mf.source_pool, "p1_")
            tgt_pfx = pool_prefix.get(mf.target_pool, "p2_")
            src_id  = cls._resolve_mf_step(mf.source_step, src_pfx)
            tgt_id  = cls._resolve_mf_step(mf.target_step, tgt_pfx)
            label   = mf.name or "msg"
            lines.append(f"    {src_id} -. {label} .-> {tgt_id}")

        return "\n".join(lines)

    @staticmethod
    def _resolve_mf_step(step_ref: str, prefix: str) -> str:
        """Resolve a message-flow step reference to a prefixed element ID."""
        if step_ref in ("start", "ev_start"):
            return prefix + "ev_start"
        if step_ref in ("end", "ev_end"):
            return prefix + "ev_end"
        return prefix + step_ref


# ── Module-level convenience function (kept for backward compatibility) ───────

def generate_mermaid(model: BPMNModel) -> str:
    """Generate a Mermaid flowchart string from a BPMNModel."""
    return MermaidGenerator.generate(model)
