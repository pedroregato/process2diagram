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
class BPMNPoolData:
    """One participant's process in a multi-pool (collaboration) diagram."""
    pool_id: str
    name: str
    steps: list[BPMNStep] = field(default_factory=list)
    edges: list[BPMNEdge] = field(default_factory=list)
    lanes: list[str] = field(default_factory=list)


@dataclass
class BPMNMessageFlow:
    """A cross-pool message connection in a collaboration diagram."""
    id: str
    source_pool: str    # pool_id of source pool
    source_step: str    # step id within source pool
    target_pool: str    # pool_id of target pool
    target_step: str    # step id within target pool ("start" → startEvent)
    name: str = ""


@dataclass
class BPMNModel:
    """Output of the BPMN Agent."""
    name: str = ""
    steps: list[BPMNStep] = field(default_factory=list)
    edges: list[BPMNEdge] = field(default_factory=list)
    lanes: list[str] = field(default_factory=list)
    description: str = ""        # process description → <documentation> in XML
    bpmn_xml: str = ""            # OMG BPMN 2.0 XML
    mermaid: str = ""
    ready: bool = False
    repair_log: list[str] = field(default_factory=list)  # repairs from bpmn_auto_repair
    lg_attempts: int = 0          # LangGraph adaptive-retry: number of BPMN passes run
    lg_final_score: float = 0.0   # LangGraph adaptive-retry: best validation score achieved
    # Multi-pool (collaboration) — populated when LLM returns pools format
    is_collaboration: bool = False
    pool_models: list[BPMNPoolData] = field(default_factory=list)
    message_flows_data: list[BPMNMessageFlow] = field(default_factory=list)

    def to_process(self):
        """Bridge to legacy schema.Process for diagram generators."""
        from core.schema import Process, Step, Edge  # type: ignore
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
    # Raw markdown — populated when loading from DB (structured fields may be empty)
    minutes_md: str = ""


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
    status: str = "active"         # active | backlog | approved | in_progress | implemented | revised | contradicted | deprecated | rejected


@dataclass
class RequirementsModel:
    """Output of the Requirements Agent."""
    name: str = ""
    session_title: str = ""   # Meeting title for mindmap root (LLM or from MinutesModel)
    requirements: list[RequirementItem] = field(default_factory=list)
    markdown: str = ""
    mindmap: str = ""      # Mermaid mindmap source
    ready: bool = False


# ── Preprocessing Model ───────────────────────────────────────────────────────

@dataclass
class PreprocessingModel:
    """Output of the TranscriptPreprocessor (rule-based, no LLM)."""
    fillers_removed: int = 0
    artifact_turns: int = 0
    repetitions_collapsed: int = 0
    metadata_issues: list[str] = field(default_factory=list)
    ready: bool = False


# ── Transcript Quality Model ──────────────────────────────────────────────────

@dataclass
class CriterionScore:
    criterion: str
    score: int           # 0–100
    weight: float        # 0.0–1.0 (informational; weighted average computed in agent)
    justification: str = ""


@dataclass
class InconsistencyItem:
    speaker: str
    timestamp: str
    text: str
    reason: str = ""   # LLM explanation: why this is likely background noise / artifact


@dataclass
class TranscriptQualityModel:
    """Output of the TranscriptQuality Agent."""
    criteria: list[CriterionScore] = field(default_factory=list)
    overall_score: float = 0.0   # weighted average 0–100
    grade: str = ""              # A / B / C / D / E
    overall_summary: str = ""
    recommendation: str = ""
    inconsistencies: list[InconsistencyItem] = field(default_factory=list)
    ready: bool = False


# ── Synthesizer Model ─────────────────────────────────────────────────────────

@dataclass
class SynthesizerModel:
    """Output of the AgentSynthesizer — executive narrative + HTML report."""
    executive_summary: str = ""
    process_narrative: str = ""
    key_insights: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)
    html: str = ""
    ready: bool = False


# ── Validation Report ─────────────────────────────────────────────────────────

@dataclass
class ValidationIssue:
    severity: str       # error | warning | info
    agent: str          # which agent produced the issue
    message: str
    element_id: str = ""


@dataclass
class BPMNValidationScore:
    """Score for a single BPMN candidate produced by AgentValidator."""
    granularity: float = 0.0   # 0–10
    task_type:   float = 0.0   # 0–10
    gateways:    float = 0.0   # 0–10
    structural:  float = 0.0   # 0–10 (10 = no structural issues)
    weighted:    float = 0.0   # weighted composite 0–10
    n_tasks:     int   = 0
    n_gateways:  int   = 0
    n_structural_errors:   int = 0
    n_structural_warnings: int = 0
    transcript_words: int = 0
    run_index:   int   = 0     # 1-based index of the run that produced this score


@dataclass
class ValidationReport:
    score: int = 100    # 0–100 (legacy)
    issues: list[ValidationIssue] = field(default_factory=list)
    bpmn_score: BPMNValidationScore = field(default_factory=BPMNValidationScore)
    bpmn_candidates: list[BPMNValidationScore] = field(default_factory=list)
    n_bpmn_runs: int = 1
    ready: bool = False

    @property
    def errors(self):
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self):
        return [i for i in self.issues if i.severity == "warning"]


# ── SBVR Model ───────────────────────────────────────────────────────────────

@dataclass
class BusinessTerm:
    """A business vocabulary term extracted by AgentSBVR."""
    term: str
    definition: str
    category: str = "concept"   # concept | fact_type | role | process


@dataclass
class BusinessRule:
    """A business rule extracted by AgentSBVR."""
    id: str
    statement: str
    short_title: str = ""           # 2–5 word inferred title; stored as nucleo_nominal in DB
    rule_type: str = "constraint"   # constraint | operational | behavioral | structural
    source: str = ""                # participant initials who stated it


@dataclass
class SBVRModel:
    """Output of AgentSBVR — business vocabulary + rules."""
    domain: str = ""
    vocabulary: list[BusinessTerm] = field(default_factory=list)
    rules: list[BusinessRule] = field(default_factory=list)
    ready: bool = False


# ── BMM Model ─────────────────────────────────────────────────────────────────

@dataclass
class BMMGoal:
    """A business goal extracted by AgentBMM."""
    id: str
    name: str
    description: str = ""
    goal_type: str = "strategic"   # strategic | tactical | operational
    horizon: str = "medium"        # short | medium | long


@dataclass
class BMMStrategy:
    """A business strategy extracted by AgentBMM."""
    id: str
    name: str
    description: str = ""
    supports: list[str] = field(default_factory=list)   # goal ids


@dataclass
class BMMPolicy:
    """A business policy extracted by AgentBMM."""
    id: str
    statement: str
    category: str = ""   # governance | compliance | operational | financial


@dataclass
class BMMModel:
    """Output of AgentBMM — business motivation model."""
    vision: str = ""
    mission: str = ""
    goals: list[BMMGoal] = field(default_factory=list)
    strategies: list[BMMStrategy] = field(default_factory=list)
    policies: list[BMMPolicy] = field(default_factory=list)
    ready: bool = False


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
    # Set to True when hub was reconstructed from DB (not from a live pipeline run)
    loaded_from_db: bool = False
    transcript_quality: TranscriptQualityModel = field(default_factory=TranscriptQualityModel)
    preprocessing: PreprocessingModel = field(default_factory=PreprocessingModel)
    nlp: NLPEnvelope = field(default_factory=NLPEnvelope)
    bpmn: BPMNModel = field(default_factory=BPMNModel)
    minutes: MinutesModel = field(default_factory=MinutesModel)
    requirements: RequirementsModel = field(default_factory=RequirementsModel)
    sbvr: SBVRModel = field(default_factory=SBVRModel)
    bmm: BMMModel = field(default_factory=BMMModel)
    validation: ValidationReport = field(default_factory=ValidationReport)
    synthesizer: SynthesizerModel = field(default_factory=SynthesizerModel)
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
        # ── v3.4: TranscriptQualityModel added to hub ─────────────────────────
        if not hasattr(hub, 'transcript_quality'):
            hub.transcript_quality = TranscriptQualityModel()

        # ── v3.5: PreprocessingModel added to hub ─────────────────────────────
        if not hasattr(hub, 'preprocessing'):
            hub.preprocessing = PreprocessingModel()

        # ── v3.6: InconsistencyItem list added to TranscriptQualityModel ─────────
        if not hasattr(hub.transcript_quality, 'inconsistencies'):
            hub.transcript_quality.inconsistencies = []

        # ── v3.2: RequirementsModel added to hub ──────────────────────────────
        if not hasattr(hub, 'requirements'):
            hub.requirements = RequirementsModel()

        # ── v3.7: multi-pool collaboration fields added to BPMNModel ─────────
        if not hasattr(hub.bpmn, 'is_collaboration'):
            hub.bpmn.is_collaboration = False
        if not hasattr(hub.bpmn, 'pool_models'):
            hub.bpmn.pool_models = []
        if not hasattr(hub.bpmn, 'message_flows_data'):
            hub.bpmn.message_flows_data = []

        # ── v3.8: mindmap added to RequirementsModel ─────────────────────────────
        if not hasattr(hub.requirements, 'mindmap'):
            hub.requirements.mindmap = ""

        # ── v3.9: session_title added to RequirementsModel ───────────────────────
        if not hasattr(hub.requirements, 'session_title'):
            hub.requirements.session_title = ""

        # ── v3.8: BPMNValidationScore fields added to ValidationReport ──────────
        if not hasattr(hub.validation, 'bpmn_score'):
            hub.validation.bpmn_score = BPMNValidationScore()
        if not hasattr(hub.validation, 'bpmn_candidates'):
            hub.validation.bpmn_candidates = []
        if not hasattr(hub.validation, 'n_bpmn_runs'):
            hub.validation.n_bpmn_runs = 1

        # ── v4.9: SBVRModel and BMMModel added to KnowledgeHub ───────────────────
        if not hasattr(hub, 'sbvr'):
            hub.sbvr = SBVRModel()
        if not hasattr(hub, 'bmm'):
            hub.bmm = BMMModel()

        # ── v4.8: repair_log added to BPMNModel ──────────────────────────────────
        if not hasattr(hub.bpmn, 'repair_log'):
            hub.bpmn.repair_log = []

        # ── v4.10: LangGraph retry fields added to BPMNModel ─────────────────────
        if not hasattr(hub.bpmn, 'lg_attempts'):
            hub.bpmn.lg_attempts = 0
        if not hasattr(hub.bpmn, 'lg_final_score'):
            hub.bpmn.lg_final_score = 0.0

        # ── v4.7: structural score fields added to BPMNValidationScore ──────────
        for score_obj in [hub.validation.bpmn_score] + list(hub.validation.bpmn_candidates):
            if not hasattr(score_obj, 'structural'):
                score_obj.structural = 0.0
            if not hasattr(score_obj, 'n_structural_errors'):
                score_obj.n_structural_errors = 0
            if not hasattr(score_obj, 'n_structural_warnings'):
                score_obj.n_structural_warnings = 0

        # ── v3.2: drawio_xml removed from BPMNModel ───────────────────────────
        if hasattr(hub.bpmn, 'drawio_xml'):
            del hub.bpmn.__dict__['drawio_xml']

        # ── v4.13: minutes_md raw fallback field ─────────────────────────────────
        if not hasattr(hub.minutes, 'minutes_md'):
            hub.minutes.minutes_md = ""

        # ── v4.13: loaded_from_db flag ────────────────────────────────────────
        if not hasattr(hub, 'loaded_from_db'):
            hub.loaded_from_db = False

        # ── v3.3: ActionItem.raised_by ────────────────────────────────────────
        for ai in hub.minutes.action_items:
            if not hasattr(ai, 'raised_by'):
                ai.raised_by = None

        # ── v3.10: SynthesizerModel added to hub ─────────────────────────────────
        if not hasattr(hub, 'synthesizer'):
            hub.synthesizer = SynthesizerModel()

        # ── v3.3: RequirementItem.speaker ─────────────────────────────────────
        for req in hub.requirements.requirements:
            if not hasattr(req, 'speaker'):
                req.speaker = None

        # ── v4.13: RequirementItem.status ─────────────────────────────────────
        for req in hub.requirements.requirements:
            if not hasattr(req, 'status'):
                req.status = "active"

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
            "transcript_quality": self.transcript_quality.ready,
            "preprocessing": self.preprocessing.ready,
            "nlp": self.nlp.ready,
            "bpmn": self.bpmn.ready,
            "minutes": self.minutes.ready,
            "requirements": self.requirements.ready,
            "validation": self.validation.ready,
            "synthesizer": self.synthesizer.ready,
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