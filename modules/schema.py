# modules/schema.py
# ─────────────────────────────────────────────────────────────────────────────
# Internal process model. All diagram generators consume this schema.
# Keeping schema separate from extraction means any generator works with
# any extractor (heuristic or any LLM provider).
# ─────────────────────────────────────────────────────────────────────────────

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Step:
    id: str                          # e.g. "S01"
    title: str                       # Short label for the diagram node
    description: str = ""            # Full description from transcript
    actor: Optional[str] = None      # Who performs this step
    is_decision: bool = False        # True → diamond shape in diagram
    decision_yes_target: Optional[str] = None   # Step ID for "yes" branch
    decision_no_target: Optional[str] = None    # Step ID for "no" branch


@dataclass
class Edge:
    source: str                      # Step ID
    target: str                      # Step ID
    label: str = ""                  # Optional edge label (e.g. "yes", "no")


@dataclass
class Process:
    name: str
    steps: list[Step] = field(default_factory=list)
    edges: list[Edge] = field(default_factory=list)

    def get_step(self, step_id: str) -> Optional[Step]:
        return next((s for s in self.steps if s.id == step_id), None)
