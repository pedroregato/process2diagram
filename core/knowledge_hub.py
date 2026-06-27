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
    raw_llm_dict: Optional[dict] = None  # last successful LLM extraction — rerun bypasses LLM
    execution_log: Optional[dict] = None  # structured log of the last agent run
    process_trigger: str = ""             # Start Event title (LLM-supplied; default: "Início")
    process_outcomes: list[str] = field(default_factory=list)  # End Event titles per outcome
    process_type: str = ""               # "flat" | "hierarchical" | "collaboration" (optional, LLM-supplied)
    process_description_md: str = ""     # Natural language description of the process (AgentBPMN or reviewer)

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
    # BABOK Guide v3 — Elicitation fields (Fase E)
    assumptions: list[str] = field(default_factory=list)       # explicit premises stated
    open_questions: list[str] = field(default_factory=list)    # unanswered questions at end
    risks_identified: list[str] = field(default_factory=list)  # risks (not formal requirements)
    dependencies: list[str] = field(default_factory=list)      # inter-team/system dependencies
    stakeholder_needs: list[str] = field(default_factory=list) # informal stakeholder needs
    # Meeting conduct antipatterns detected by AgentMinutes (v4.28)
    # Each entry: {"type": str, "description": str, "examples": list[str]}
    meeting_antipatterns: list[dict] = field(default_factory=list)
    # Raw markdown — populated when loading from DB (structured fields may be empty)
    minutes_md: str = ""
    # ATA Engine interactive HTML — generated after pipeline, empty if not available
    ata_html: str = ""
    ata_html_error: str = ""


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
    # Multi-sphere traceability (Fase G — v4.24)
    business_rule_refs: list = field(default_factory=list)  # List[str] — e.g. ["BR001", "BR003"]
    sphere: Optional[str] = None   # inherited from the most relevant SBVR rule
    # Origin traceability (v4.23)
    origin: str = "transcricao"    # 'transcricao' | 'documento'
    doc_ref: Optional[str] = None  # UUID of source meeting_document when origin='documento'


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
    semantic:    float = 0.0   # 0–10 (10 = no naming violations)
    weighted:    float = 0.0   # weighted composite 0–10
    n_tasks:     int   = 0
    n_gateways:  int   = 0
    n_structural_errors:   int = 0
    n_structural_warnings: int = 0
    n_semantic_violations: int = 0
    transcript_words: int = 0
    run_index:   int   = 0     # 1-based index of the run that produced this score


@dataclass
class AgentOutcomeScore:
    """
    Resultado da validação de outcome para um agente específico.
    Produzido por AgentValidator.validate_all() — pure Python, sem LLM.
    """
    agent_name: str
    passed: bool                    # True se todos os critérios obrigatórios passaram
    score: float                    # 0.0–10.0 derivado do % de checks passing
    checks: dict = field(default_factory=dict)   # {"label": True/False}
    warnings: list = field(default_factory=list) # critérios opcionais falhos / observações


@dataclass
class ValidationReport:
    score: int = 100    # 0–100 (legacy)
    issues: list[ValidationIssue] = field(default_factory=list)
    bpmn_score: BPMNValidationScore = field(default_factory=BPMNValidationScore)
    bpmn_candidates: list[BPMNValidationScore] = field(default_factory=list)
    n_bpmn_runs: int = 1
    ready: bool = False
    # v4.26: per-agent outcome scores (populated by AgentValidator.validate_all)
    agent_scores: dict = field(default_factory=dict)  # agent_name → AgentOutcomeScore
    # v4.28: LangGraph full-pipeline retry tracking
    lg_minutes_retries: int = 0       # number of minutes retries performed
    lg_req_retries: int = 0           # number of requirements retries performed
    lg_coordination_notes: list[str] = field(default_factory=list)  # cross-agent insights
    # v4.29: A2A delegation log — [{agent, summary}] for each delegation round
    lg_delegation_log: list = field(default_factory=list)

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
    # Origin traceability (v4.23)
    origin: str = "transcricao"
    doc_ref: Optional[str] = None


_VALID_SPHERES = frozenset(
    ["marketing", "financeiro", "rh", "operacoes", "juridico", "tecnologia", "geral"]
)


@dataclass
class BusinessRule:
    """A business rule extracted by AgentSBVR."""
    id: str
    statement: str
    short_title: str = ""           # 2–5 word inferred title; stored as nucleo_nominal in DB
    rule_type: str = "constraint"   # constraint | operational | behavioral | structural
    source: str = ""                # participant initials who stated it
    # Multi-sphere fields (Fase G — v4.24)
    sphere: str = "geral"           # marketing | financeiro | rh | operacoes | juridico | tecnologia | geral
    sphere_owner: str = ""          # typical owner: CMO, CFO, CHRO, COO, CLO, CTO, CEO
    bmm_policy_ref: Optional[str] = None   # "POL-001" reference to hub.bmm.policies
    speaker_quote: str = ""         # verbatim quote from transcript
    # Origin traceability (v4.23)
    origin: str = "transcricao"
    doc_ref: Optional[str] = None


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
    # Origin traceability (v4.23)
    origin: str = "transcricao"
    doc_ref: Optional[str] = None


@dataclass
class BMMStrategy:
    """A business strategy extracted by AgentBMM."""
    id: str
    name: str
    description: str = ""
    supports: list[str] = field(default_factory=list)   # goal ids
    # Origin traceability (v4.23)
    origin: str = "transcricao"
    doc_ref: Optional[str] = None


@dataclass
class BMMPolicy:
    """A business policy extracted by AgentBMM."""
    id: str
    statement: str
    category: str = ""   # governance | compliance | operational | financial
    # Origin traceability (v4.23)
    origin: str = "transcricao"
    doc_ref: Optional[str] = None


@dataclass
class BMMModel:
    """Output of AgentBMM — business motivation model."""
    vision: str = ""
    mission: str = ""
    goals: list[BMMGoal] = field(default_factory=list)
    strategies: list[BMMStrategy] = field(default_factory=list)
    policies: list[BMMPolicy] = field(default_factory=list)
    ready: bool = False



# ── DMN Model (Fase A — OMG DMN 1.4) ─────────────────────────────────────────

@dataclass
class DMNInput:
    label: str
    expression: str = ""    # condition expression (e.g. "value >= 5000")


@dataclass
class DMNOutput:
    label: str
    value: str = ""          # outcome value


@dataclass
class DMNRule:
    inputs: list[str] = field(default_factory=list)   # one per DMNInput
    output: str = ""
    annotation: str = ""     # optional note on this rule row


@dataclass
class DMNDecision:
    id: str
    name: str
    question: str = ""       # business question this decision answers
    rationale: str = ""      # context and justification
    decided_by: list[str] = field(default_factory=list)
    inputs: list[DMNInput] = field(default_factory=list)
    outputs: list[DMNOutput] = field(default_factory=list)
    rules: list[DMNRule] = field(default_factory=list)
    hit_policy: str = "U"    # U=Unique, A=Any, F=First, C=Collect
    confidence: float = 1.0
    # Origin traceability (v4.23)
    origin: str = "transcricao"
    doc_ref: Optional[str] = None


@dataclass
class DMNModel:
    """Output of AgentDMN — formalized decision tables (OMG DMN 1.4)."""
    decisions: list[DMNDecision] = field(default_factory=list)
    ready: bool = False


# ── Argumentation Map (Fase C — IBIS) ─────────────────────────────────────────

@dataclass
class IBISAlternative:
    id: str
    description: str
    proposed_by: str = ""
    pros: list[str] = field(default_factory=list)
    cons: list[str] = field(default_factory=list)
    supported_by: list[str] = field(default_factory=list)
    opposed_by: list[str] = field(default_factory=list)
    was_chosen: bool = False


@dataclass
class IBISResolution:
    type: str = "unresolved"          # decided | deferred | unresolved
    chosen_alternative_id: str = ""
    rationale: str = ""
    with_caveats: list[str] = field(default_factory=list)


@dataclass
class IBISQuestion:
    id: str
    statement: str
    raised_by: str = ""
    alternatives: list[IBISAlternative] = field(default_factory=list)
    resolution: IBISResolution = field(default_factory=IBISResolution)


@dataclass
class ArgumentationMap:
    """Output of AgentArgumentation — IBIS argumentation structure."""
    questions: list[IBISQuestion] = field(default_factory=list)
    ready: bool = False

    @property
    def resolved_count(self) -> int:
        return sum(1 for q in self.questions if q.resolution.type == "decided")

    @property
    def unresolved_count(self) -> int:
        return sum(1 for q in self.questions if q.resolution.type == "unresolved")


# ── Communication Noise Model ────────────────────────────────────────────────

@dataclass
class AmbiguityItem:
    """A term, phrase or commitment with multiple possible interpretations."""
    text: str                               # verbatim or near-verbatim quote
    ambiguity_type: str                     # lexical | referential | vague_commitment | syntactic
    speaker: str                            # participant initials or name
    possible_interpretations: list[str] = field(default_factory=list)  # 2–3 alternatives
    suggestion: str = ""                    # recommended clarification action
    confidence: float = 0.8                 # 0.0–1.0


@dataclass
class CommunicationGap:
    """A missing, unanswered or abandoned communication thread."""
    gap_type: str                           # unanswered_question | abandoned_topic | implicit_disagreement | missing_info
    description: str                        # what the gap is
    raised_by: str = ""                     # who raised the topic (initials or "–")
    topic: str = ""                         # thematic category
    evidence_quote: str = ""               # supporting text from transcript
    impact: str = ""                        # potential impact if unresolved
    recommendation: str = ""               # suggested follow-up action


@dataclass
class CommunicationNoiseModel:
    """Output of AgentCommunicationNoise — ambiguities + gaps detected in transcript."""
    ambiguities: list[AmbiguityItem] = field(default_factory=list)
    gaps: list[CommunicationGap] = field(default_factory=list)
    noise_score: float = 0.0    # 0–10, lower = cleaner communication
    summary: str = ""
    ready: bool = False


# ── Query Summary Model (Fase F — multi-perspective summarization) ────────────

@dataclass
class PerspectiveSummary:
    """Summary of the meeting from one stakeholder perspective."""
    perspective: str          # executive | technical | project_manager | compliance
    label: str                # display label (PT or EN)
    headline: str = ""        # one-sentence takeaway
    highlights: list[str] = field(default_factory=list)   # 3–5 bullet points
    open_items: list[str] = field(default_factory=list)   # open questions / risks for this perspective
    recommended_actions: list[str] = field(default_factory=list)


@dataclass
class QuerySummaryModel:
    """Output of AgentQuerySummarizer — 4-perspective post-pipeline summary."""
    perspectives: list[PerspectiveSummary] = field(default_factory=list)
    ready: bool = False

    def get(self, perspective: str) -> Optional["PerspectiveSummary"]:
        """Return the PerspectiveSummary for the given perspective key, or None."""
        for p in self.perspectives:
            if p.perspective == perspective:
                return p
        return None


# ── Meeting Time Model ────────────────────────────────────────────────────────

@dataclass
class MeetingTimeModel:
    """
    Meeting duration and per-speaker talk time extracted from transcript timestamps.
    Populated by transcript_time_parser (pure Python, no LLM).
    When has_timestamps=False the values are word-count estimates.
    """
    has_timestamps: bool = False
    format_detected: str = ""          # e.g. "bracket_ts_speaker" or "word_count_estimate"
    duration_seconds: Optional[int] = None
    speaker_times: dict = field(default_factory=dict)   # name → seconds
    speaker_turns: dict = field(default_factory=dict)   # name → turn count
    ready: bool = False

    @property
    def duration_minutes(self) -> Optional[int]:
        if self.duration_seconds is None:
            return None
        return max(1, round(self.duration_seconds / 60))


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
    cache_hits: int = 0
    tokens_saved: int = 0
    long_context_calls: int = 0
    # Tier-2 PII pseudonymization (PC82) — built once via detect_names(transcript)
    # Format: { "[PESSOA:PG]": "Pedro Gentil" }  token → original name
    # Passed to sanitize() on every _call_llm() so all agents share a consistent
    # pseudonymization scheme for the duration of the session.
    name_map: dict = field(default_factory=dict)


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
    # Context fields (v4.21 — formerly "project")
    context_id:    str = ""   # UUID of the active context
    context_type:  str = ""   # project | product | feasibility | strategic | meeting_series | discussion | other
    context_skill: str = ""        # CKF manual (skill_md) — injected into agent prompts
    context_files_text: str = ""   # Extracted text from uploaded context files (HTML, PPTX, PDF, TXT)
    transcript_quality: TranscriptQualityModel = field(default_factory=TranscriptQualityModel)
    preprocessing: PreprocessingModel = field(default_factory=PreprocessingModel)
    nlp: NLPEnvelope = field(default_factory=NLPEnvelope)
    bpmn: BPMNModel = field(default_factory=BPMNModel)
    minutes: MinutesModel = field(default_factory=MinutesModel)
    requirements: RequirementsModel = field(default_factory=RequirementsModel)
    sbvr: SBVRModel = field(default_factory=SBVRModel)
    bmm: BMMModel = field(default_factory=BMMModel)
    dmn: DMNModel = field(default_factory=DMNModel)                      # Fase A: DMN decisions
    argumentation: ArgumentationMap = field(default_factory=ArgumentationMap)  # Fase C: IBIS map
    query_summary: QuerySummaryModel = field(default_factory=QuerySummaryModel)  # Fase F: multi-perspective
    communication_noise: CommunicationNoiseModel = field(default_factory=CommunicationNoiseModel)
    validation: ValidationReport = field(default_factory=ValidationReport)
    synthesizer: SynthesizerModel = field(default_factory=SynthesizerModel)
    meeting_time: MeetingTimeModel = field(default_factory=MeetingTimeModel)
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

        # ── v4.34: raw_llm_dict for rerun-without-LLM ────────────────────────────
        if not hasattr(hub.bpmn, 'raw_llm_dict'):
            hub.bpmn.raw_llm_dict = None

        # ── v4.35: execution_log for BPMN agent diagnostics ──────────────────────
        if not hasattr(hub.bpmn, 'execution_log'):
            hub.bpmn.execution_log = None

        # ── v4.37: process_trigger / process_outcomes for meaningful Start/End Event names
        if not hasattr(hub.bpmn, 'process_trigger'):
            hub.bpmn.process_trigger = ""
        if not hasattr(hub.bpmn, 'process_outcomes'):
            hub.bpmn.process_outcomes = []

        # ── v4.55: process_type + process_description_md
        if not hasattr(hub.bpmn, 'process_type'):
            hub.bpmn.process_type = ""
        if not hasattr(hub.bpmn, 'process_description_md'):
            hub.bpmn.process_description_md = ""

        # ── v4.7: structural score fields added to BPMNValidationScore ──────────
        for score_obj in [hub.validation.bpmn_score] + list(hub.validation.bpmn_candidates):
            if not hasattr(score_obj, 'structural'):
                score_obj.structural = 0.0
            if not hasattr(score_obj, 'n_structural_errors'):
                score_obj.n_structural_errors = 0
            if not hasattr(score_obj, 'n_structural_warnings'):
                score_obj.n_structural_warnings = 0

        # ── v4.59: semantic score fields added to BPMNValidationScore ────────────
        for score_obj in [hub.validation.bpmn_score] + list(hub.validation.bpmn_candidates):
            if not hasattr(score_obj, 'semantic'):
                score_obj.semantic = 0.0
            if not hasattr(score_obj, 'n_semantic_violations'):
                score_obj.n_semantic_violations = 0

        # ── v3.2: drawio_xml removed from BPMNModel ───────────────────────────
        if hasattr(hub.bpmn, 'drawio_xml'):
            del hub.bpmn.__dict__['drawio_xml']

        # ── v4.13: minutes_md raw fallback field ─────────────────────────────────
        if not hasattr(hub.minutes, 'minutes_md'):
            hub.minutes.minutes_md = ""

        # ── v4.19: ATA Engine HTML output fields ─────────────────────────────────
        if not hasattr(hub.minutes, 'ata_html'):
            hub.minutes.ata_html = ""
        if not hasattr(hub.minutes, 'ata_html_error'):
            hub.minutes.ata_html_error = ""

        # ── v4.28: Meeting conduct antipatterns ───────────────────────────────────
        if not hasattr(hub.minutes, 'meeting_antipatterns'):
            hub.minutes.meeting_antipatterns = []

        # ── v4.21: Context fields (project → context rename) ──────────────────
        if not hasattr(hub, 'context_id'):
            hub.context_id = ""
        if not hasattr(hub, 'context_type'):
            hub.context_type = ""
        if not hasattr(hub, 'context_skill'):
            hub.context_skill = ""
        if not hasattr(hub, 'context_files_text'):
            hub.context_files_text = ""

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

        # ── v4.23 BMIF: DMN (Fase A) ─────────────────────────────────────────────
        if not hasattr(hub, 'dmn'):
            hub.dmn = DMNModel()

        # ── v4.23 BMIF: Argumentation / IBIS (Fase C) ────────────────────────
        if not hasattr(hub, 'argumentation'):
            hub.argumentation = ArgumentationMap()

        # ── v4.23 BMIF: BABOK fields in MinutesModel (Fase E) ────────────────
        for _field in ('assumptions', 'open_questions', 'risks_identified',
                       'dependencies', 'stakeholder_needs'):
            if not hasattr(hub.minutes, _field):
                setattr(hub.minutes, _field, [])

        # ── v4.24 BMIF: QuerySummaryModel (Fase F) ───────────────────────────
        if not hasattr(hub, 'query_summary'):
            hub.query_summary = QuerySummaryModel()

        # ── v4.25: cache_hits + tokens_saved in SessionMetadata ─────────────
        if not hasattr(hub.meta, 'cache_hits'):
            hub.meta.cache_hits = 0
        if not hasattr(hub.meta, 'tokens_saved'):
            hub.meta.tokens_saved = 0
        if not hasattr(hub.meta, 'long_context_calls'):
            hub.meta.long_context_calls = 0

        # ── v4.24 Multi-sphere SBVR (Fase G) ─────────────────────────────────
        for _rule in hub.sbvr.rules:
            if not hasattr(_rule, 'sphere'):
                _rule.sphere = "geral"
            if not hasattr(_rule, 'sphere_owner'):
                _rule.sphere_owner = ""
            if not hasattr(_rule, 'bmm_policy_ref'):
                _rule.bmm_policy_ref = None
            if not hasattr(_rule, 'speaker_quote'):
                _rule.speaker_quote = ""
        for _req in hub.requirements.requirements:
            if not hasattr(_req, 'business_rule_refs'):
                _req.business_rule_refs = []
            if not hasattr(_req, 'sphere'):
                _req.sphere = None

        # ── v4.23: origin + doc_ref para artefatos de documentos ─────────────
        for _req in hub.requirements.requirements:
            if not hasattr(_req, 'origin'):
                _req.origin = "transcricao"
            if not hasattr(_req, 'doc_ref'):
                _req.doc_ref = None
        for _term in hub.sbvr.vocabulary:
            if not hasattr(_term, 'origin'):
                _term.origin = "transcricao"
            if not hasattr(_term, 'doc_ref'):
                _term.doc_ref = None
        for _rule in hub.sbvr.rules:
            if not hasattr(_rule, 'origin'):
                _rule.origin = "transcricao"
            if not hasattr(_rule, 'doc_ref'):
                _rule.doc_ref = None
        for _goal in hub.bmm.goals:
            if not hasattr(_goal, 'origin'):
                _goal.origin = "transcricao"
            if not hasattr(_goal, 'doc_ref'):
                _goal.doc_ref = None
        for _strat in hub.bmm.strategies:
            if not hasattr(_strat, 'origin'):
                _strat.origin = "transcricao"
            if not hasattr(_strat, 'doc_ref'):
                _strat.doc_ref = None
        for _pol in hub.bmm.policies:
            if not hasattr(_pol, 'origin'):
                _pol.origin = "transcricao"
            if not hasattr(_pol, 'doc_ref'):
                _pol.doc_ref = None
        for _dec in hub.dmn.decisions:
            if not hasattr(_dec, 'origin'):
                _dec.origin = "transcricao"
            if not hasattr(_dec, 'doc_ref'):
                _dec.doc_ref = None

        # ── v4.25: MeetingTimeModel ───────────────────────────────────────────
        if not hasattr(hub, 'meeting_time'):
            hub.meeting_time = MeetingTimeModel()

        # ── v4.26: ValidationReport.agent_scores ─────────────────────────────
        if not hasattr(hub.validation, 'agent_scores'):
            hub.validation.agent_scores = {}

        # ── v4.26: CommunicationNoiseModel ────────────────────────────────────
        if not hasattr(hub, 'communication_noise'):
            hub.communication_noise = CommunicationNoiseModel()

        # ── v4.28: LangGraph full-pipeline retry fields ───────────────────────
        if not hasattr(hub.validation, 'lg_minutes_retries'):
            hub.validation.lg_minutes_retries = 0
        if not hasattr(hub.validation, 'lg_req_retries'):
            hub.validation.lg_req_retries = 0
        if not hasattr(hub.validation, 'lg_coordination_notes'):
            hub.validation.lg_coordination_notes = []

        # ── v4.29: A2A delegation log ─────────────────────────────────────────
        if not hasattr(hub.validation, 'lg_delegation_log'):
            hub.validation.lg_delegation_log = []

        # ── PC82: Tier-2 PII name_map in SessionMetadata ─────────────────────
        if not hasattr(hub.meta, 'name_map'):
            hub.meta.name_map = {}

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