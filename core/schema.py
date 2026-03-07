# core/schema.py
# ─────────────────────────────────────────────────────────────────────────────
# Internal process model — backward-compatible with modules/schema.py (v2).
# Diagram generators (Mermaid, Draw.io) consume this schema.
# Knowledge Hub's BPMNModel.to_process() bridges to this when needed.
# ─────────────────────────────────────────────────────────────────────────────

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Step:
    id: str                                           # e.g. "S01"
    title: str                                        # Short label for diagram nodes
    description: str = ""                             # Full description from transcript
    actor: Optional[str] = None                       # Who performs this step
    is_decision: bool = False                         # True → diamond shape
    task_type: str = "userTask"                       # BPMN task type hint
    lane: Optional[str] = None                        # Swimlane (actor pool)
    decision_yes_target: Optional[str] = None
    decision_no_target: Optional[str] = None


@dataclass
class Edge:
    source: str
    target: str
    label: str = ""
    condition: str = ""


@dataclass
class Process:
    name: str
    steps: list[Step] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def get_step(self, step_id: str) -> Optional[Step]:
        return next((s for s in self.steps if s.id == step_id), None)

    @property
    def actors(self) -> list[str]:
        return list(dict.fromkeys(s.actor for s in self.steps if s.actor))

    @property
    def decisions(self) -> list[Step]:
        return [s for s in self.steps if s.is_decision]