# core/knowledge_hub.py
# ─────────────────────────────────────────────────────────────────────────────
# Central session state shared by all agents.
#
# Design decisions:
#   - Pure Python dataclasses (no ORM, no DB) — lives in st.session_state.
#   - Versioned: each write bumps `version` for traceability.
#   - Serializable: to_dict() / from_dict() for JSON export and persistence.
#   - Agents write only their own section; Orchestrator owns the top level.
#   - Iniciativa de Pedro Gentil
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional


# ── NLP Envelope ─────────────────────────────────────────────────────────────

@dataclass
class NLPSegment:
    """A classified chunk of transcript text."""
    text: str
    segment_type: str           # process | rule | goal | actor | decision | data | other
    confidence: float = 1.0
    actors: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)


@dataclass
class NLPEnvelope:
    """Output of the NLP/Chunker agent."""
    segments: list[NLPSegment] = field(default_factory=list)
    actors: list[str] = field(default_factory=list)
    entities: list[dict] = field(default_factory=list)   # {text, label, start, end}
    language_detected: str = "pt"
    ready: bool = False


# ── BPMN Model ────────────────────────────────────────────────────────────────

@dataclass
class BPMNStep:
    id: str
    title: str
    description: str = ""
    actor: Optional[str] = None
    is_decision: bool = False
    task_type: str = "userTask"   # userTask | serviceTask | businessRuleTask | scriptTask
    lane: Optional[str] = None


@dataclass
class BPMNEdge:
    source: str
    target: str
    label: str = ""
    condition: str = ""           # formal condition expression (optional)


@dataclass
class BPMNModel:
    """Output of the BPMN Agent."""
    name: str = ""
    steps: list[BPMNStep] = field(default_factory=list)
    edges: list[BPMNEdge] = field(default_factory=list)
    lanes: list[str] = field(default_factory=list)
    bpmn_xml: str = ""            # OMG BPMN 2.0 XML
    mermaid: str = ""
    ready: bool = False

    def to_process(self):
        """Bridge to legacy schema.Process for diagram generators."""
        from core.schema import Process, Step, Edge
        steps = [Step(
            id=s.id, title=s.title, description=s.description,
            actor=s.actor, is_decision=s.is_decision
        ) for s in self.steps]
        edges = [Edge(source=e.source, target=e.target, label=e.label)
                 for e in self.edges]
        return Process(name=self.name, steps=steps, edges=edges)


# ── Minutes Model ─────────────────────────────────────────────────────────────

@dataclass
class ActionItem:
    task: str
    responsible: str = "A definir"
    deadline: Optional[str] = None
    priority: str = "normal"      # high | normal | low
    raised_by: Optional[str] = None  # initials of who raised this action (e.g. "MF")


@dataclass
class MinutesModel:
    """Output of the Minutes Agent."""
    title: str = ""
    date: str = ""
    location: str = ""
    participants: list[str] = field(default_factory=list)
    agenda: list[str] = field(default_factory=list)
    summary: list[dict] = field(default_factory=list)   # [{topic, content}]
    decisions: list[str] = field(default_factory=list)
    action_items: list[ActionItem] = field(default_factory=list)
    next_meeting: Optional[str] = None
    ready: bool = False


# ── Requirements Model ────────────────────────────────────────────────────

@dataclass
class RequirementItem:
    id: str
    title: str
    description: str = ""
    type: str = "functional"      # ui_field | validation | business_rule | functional | non_functional
    actor: Optional[str] = None
    priority: str = "unspecified" # high | medium | low | unspecified
    process_step: Optional[str] = None
    source_quote: str = ""
    speaker: Optional[str] = None  # initials of who said source_quote (e.g. "MF")


@dataclass
class RequirementsModel:
    """Output of the Requirements Agent."""
    name: str = ""
    requirements: list[RequirementItem] = field(default_factory=list)
    markdown: str = ""
    ready: bool = False


# ── Validation Report ─────────────────────────────────────────────────────────

@dataclass
class ValidationIssue:
    severity: str       # error | warning | info
    agent: str          # which agent produced the issue
    message: str
    element_id: str = ""


@dataclass
class ValidationReport:
    score: int = 100    # 0–100
    issues: list[ValidationIssue] = field(default_factory=list)
    ready: bool = False

    @property
    def errors(self):
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self):
        return [i for i in self.issues if i.severity == "warning"]


# ── Session Metadata ──────────────────────────────────────────────────────────

@dataclass
class SessionMetadata:
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    llm_provider: str = ""
    llm_model: str = ""
    agents_run: list[str] = field(default_factory=list)
    total_tokens_used: int = 0
    processing_time_ms: int = 0


# ── Knowledge Hub (root) ──────────────────────────────────────────────────────

@dataclass
class KnowledgeHub:
    """
    Central shared state for a single processing session.

    Lifecycle:
        hub = KnowledgeHub.new()
        hub.set_transcript(raw_text)
        # agents populate their sections
        hub.bpmn.steps = [...]
        hub.bpmn.ready = True
        hub.bump()   # increments version
    """
    version: int = 0
    transcript_raw: str = ""
    transcript_clean: str = ""
    nlp: NLPEnvelope = field(default_factory=NLPEnvelope)
    bpmn: BPMNModel = field(default_factory=BPMNModel)
    minutes: MinutesModel = field(default_factory=MinutesModel)
    requirements: RequirementsModel = field(default_factory=RequirementsModel)
    validation: ValidationReport = field(default_factory=ValidationReport)
    meta: SessionMetadata = field(default_factory=SessionMetadata)

    # ── Factory ──────────────────────────────────────────────────────────────

    @classmethod
    def new(cls) -> "KnowledgeHub":
        return cls()

    # ── Session-state migration ───────────────────────────────────────────────

    @classmethod
    def migrate(cls, hub: "KnowledgeHub") -> "KnowledgeHub":
        """
        Migrate a hub loaded from st.session_state that may be missing fields
        added in newer versions.

        Call once after every st.session_state.get("hub") in app.py.
        When adding a new field to any dataclass, add one line here.

        Pattern:
            if not hasattr(obj, 'field'):
                obj.field = <default>
        """
        # ── v3.2: RequirementsModel added to hub ──────────────────────────────
        if not hasattr(hub, 'requirements'):
            hub.requirements = RequirementsModel()

        # ── v3.2: drawio_xml removed from BPMNModel ───────────────────────────
        if hasattr(hub.bpmn, 'drawio_xml'):
            del hub.bpmn.__dict__['drawio_xml']

        # ── v3.3: ActionItem.raised_by ────────────────────────────────────────
        for ai in hub.minutes.action_items:
            if not hasattr(ai, 'raised_by'):
                ai.raised_by = None

        # ── v3.3: RequirementItem.speaker ─────────────────────────────────────
        for req in hub.requirements.requirements:
            if not hasattr(req, 'speaker'):
                req.speaker = None

        return hub

    # ── Lifecycle helpers ─────────────────────────────────────────────────────

    def set_transcript(self, raw: str, clean: str = "") -> None:
        self.transcript_raw = raw
        self.transcript_clean = clean or raw
        self.bump()

    def bump(self) -> None:
        """Increment version — call after any meaningful write."""
        self.version += 1

    def mark_agent_run(self, agent_name: str) -> None:
        if agent_name not in self.meta.agents_run:
            self.meta.agents_run.append(agent_name)

    # ── Status helpers ────────────────────────────────────────────────────────

    @property
    def is_ready(self) -> bool:
        """True when at least BPMN or Minutes is populated."""
        return self.bpmn.ready or self.minutes.ready

    @property
    def status_summary(self) -> dict[str, bool]:
        return {
            "nlp": self.nlp.ready,
            "bpmn": self.bpmn.ready,
            "minutes": self.minutes.ready,
            "requirements": self.requirements.ready,
            "validation": self.validation.ready,
        }

    # ── Serialization ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        """Full serialization for JSON export."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeHub":
        """Reconstruct from a previously exported dict (basic)."""
        hub = cls()
        hub.version = data.get("version", 0)
        hub.transcript_raw = data.get("transcript_raw", "")
        hub.transcript_clean = data.get("transcript_clean", "")
        # Deep reconstruction omitted for PC1 — extend as models grow
        return hub

    def to_json(self, indent: int = 2) -> str:
        import json
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)