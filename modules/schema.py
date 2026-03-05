# modules/schema.py
# ─────────────────────────────────────────────────────────────────────────────
# Internal process model.
#
# Two layers:
#   1. Process / Step / Edge  →  original model (Mermaid + Draw.io, unchanged)
#   2. BpmnProcess / BpmnElement / SequenceFlow  →  BPMN-advanced model
#
# All diagram generators continue to work independently.
# ─────────────────────────────────────────────────────────────────────────────

from dataclasses import dataclass, field
from typing import Optional, Literal


# ── Original model (unchanged) ────────────────────────────────────────────────

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


# ── BPMN model ────────────────────────────────────────────────────────────────

# Element types supported in BPMN 2.0 (advanced)
BpmnElementType = Literal[
    # Events
    "startEvent",
    "endEvent",
    "intermediateThrowEvent",
    "intermediateCatchEvent",
    "boundaryEvent",
    # Tasks
    "task",
    "userTask",
    "serviceTask",
    "scriptTask",
    "sendTask",
    "receiveTask",
    "manualTask",
    "businessRuleTask",
    "callActivity",
    # Gateways
    "exclusiveGateway",
    "parallelGateway",
    "inclusiveGateway",
    "eventBasedGateway",
    "complexGateway",
    # Sub-processes
    "subProcess",
    "adHocSubProcess",
    # Artifacts
    "dataObject",
    "dataStore",
    "annotation",
]

# Event subtypes (used in startEvent, endEvent, intermediate*, boundaryEvent)
BpmnEventType = Literal[
    "none",          # plain event — no marker
    "message",
    "timer",
    "error",
    "escalation",
    "cancel",
    "compensation",
    "signal",
    "terminate",
    "conditional",
    "link",
]


@dataclass
class BpmnElement:
    """
    Represents any BPMN flow element: event, task, gateway or sub-process.

    For sub-processes, `children` holds the nested BpmnElements.
    For boundaryEvents, `attached_to` points to the host task ID.
    """
    id: str
    type: BpmnElementType
    name: str = ""

    # Task / event specifics
    actor: Optional[str] = None          # Maps to lane name
    lane: Optional[str] = None           # Explicit lane override
    event_type: BpmnEventType = "none"   # Marker inside event circle/envelope

    # Boundary event
    attached_to: Optional[str] = None    # Host task ID
    is_interrupting: bool = True         # Boundary: interrupting vs non-interrupting

    # Sub-process
    is_expanded: bool = True
    children: list["BpmnElement"] = field(default_factory=list)

    # Loop / multi-instance markers
    is_loop: bool = False
    is_parallel_multi: bool = False
    is_sequential_multi: bool = False

    # Compensation marker
    is_compensation: bool = False

    # Call activity
    called_element: Optional[str] = None

    # Data associations (IDs of data objects linked)
    data_inputs: list[str] = field(default_factory=list)
    data_outputs: list[str] = field(default_factory=list)

    # Free-form documentation / tooltip
    documentation: str = ""


@dataclass
class SequenceFlow:
    """Directed connection between two BpmnElements."""
    id: str
    source: str            # BpmnElement ID
    target: str            # BpmnElement ID
    name: str = ""         # Label shown on diagram (e.g. "Yes", "No", "Error")
    condition: str = ""    # FormalExpression text (for conditional flows)
    is_default: bool = False


@dataclass
class BpmnLane:
    """A swimlane inside a pool, mapping to an actor / role."""
    id: str
    name: str
    element_ids: list[str] = field(default_factory=list)   # IDs of contained elements


@dataclass
class BpmnPool:
    """
    A collaboration pool. In most single-process diagrams there is one pool.
    Multiple pools model inter-organizational message exchanges.
    """
    id: str
    name: str
    lanes: list[BpmnLane] = field(default_factory=list)
    is_black_box: bool = False    # True → opaque pool, no internal elements shown


@dataclass
class BpmnProcess:
    """
    Full BPMN process model. Consumed by diagram_bpmn.py.

    Elements are flat (boundary events reference their host via attached_to).
    Sub-process children are nested inside their parent BpmnElement.
    """
    name: str
    process_id: str = "process_1"

    elements: list[BpmnElement] = field(default_factory=list)
    flows: list[SequenceFlow] = field(default_factory=list)
    pools: list[BpmnPool] = field(default_factory=list)

    # Metadata
    is_executable: bool = False
    documentation: str = ""

    # ── Helpers ───────────────────────────────────────────────────────────────

    def get_element(self, element_id: str) -> Optional[BpmnElement]:
        return next((e for e in self.elements if e.id == element_id), None)

    def get_lane_for(self, element_id: str) -> Optional[BpmnLane]:
        for pool in self.pools:
            for lane in pool.lanes:
                if element_id in lane.element_ids:
                    return lane
        return None

    def lanes_flat(self) -> list[BpmnLane]:
        return [lane for pool in self.pools for lane in pool.lanes]

    def start_events(self) -> list[BpmnElement]:
        return [e for e in self.elements if e.type == "startEvent"]

    def end_events(self) -> list[BpmnElement]:
        return [e for e in self.elements if e.type == "endEvent"]

    def gateways(self) -> list[BpmnElement]:
        return [e for e in self.elements if "Gateway" in e.type]

    def tasks(self) -> list[BpmnElement]:
        task_types = {
            "task", "userTask", "serviceTask", "scriptTask",
            "sendTask", "receiveTask", "manualTask",
            "businessRuleTask", "callActivity",
        }
        return [e for e in self.elements if e.type in task_types]

    def boundary_events(self) -> list[BpmnElement]:
        return [e for e in self.elements if e.type == "boundaryEvent"]

    def sub_processes(self) -> list[BpmnElement]:
        return [e for e in self.elements if e.type in ("subProcess", "adHocSubProcess")]
