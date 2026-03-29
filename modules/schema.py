# modules/schema.py

from dataclasses import dataclass, field
from typing import Optional


# ── Mermaid / Draw.io model ───────────────────────────────────────────────────

@dataclass
class Step:
    id: str
    title: str
    description: str = ""
    actor: Optional[str] = None
    is_decision: bool = False
    decision_yes_target: Optional[str] = None
    decision_no_target: Optional[str] = None


@dataclass
class Edge:
    source: str
    target: str
    label: str = ""


@dataclass
class Process:
    name: str
    steps: list = field(default_factory=list)
    edges: list = field(default_factory=list)

    def get_step(self, step_id: str):
        return next((s for s in self.steps if s.id == step_id), None)


# ── BPMN 2.0 model ───────────────────────────────────────────────────────────

@dataclass
class BpmnElement:
    id: str
    type: str                          # startEvent, userTask, exclusiveGateway, endEvent, etc.
    name: str
    actor: Optional[str] = None        # lane name
    lane: Optional[str] = None
    event_type: str = "none"           # none | message | timer | error | signal | terminate
    attached_to: Optional[str] = None  # boundaryEvent host
    is_interrupting: bool = True
    is_expanded: bool = True
    children: list = field(default_factory=list)
    is_loop: bool = False
    is_parallel_multi: bool = False
    is_sequential_multi: bool = False
    is_compensation: bool = False
    called_element: Optional[str] = None
    documentation: str = ""


@dataclass
class SequenceFlow:
    id: str
    source: str
    target: str
    name: str = ""
    condition: str = ""
    is_default: bool = False


@dataclass
class BpmnLane:
    id: str
    name: str
    element_ids: list = field(default_factory=list)


@dataclass
class MessageFlow:
    """Cross-pool message flow for BPMN collaboration diagrams."""
    id: str
    source: str    # element id in the flat XML namespace
    target: str
    name: str = ""


@dataclass
class BpmnPool:
    id: str
    name: str
    lanes: list = field(default_factory=list)
    # Per-pool elements/flows for multi-pool collaboration diagrams.
    # When populated, this pool owns its own sub-process (multi-pool mode).
    elements: list = field(default_factory=list)
    flows: list = field(default_factory=list)


@dataclass
class BpmnProcess:
    name: str
    documentation: str = ""
    elements: list = field(default_factory=list)
    flows: list = field(default_factory=list)
    pools: list = field(default_factory=list)
    message_flows: list = field(default_factory=list)   # cross-pool MessageFlow list

    def get_element(self, eid: str):
        return next((e for e in self.elements if e.id == eid), None)
