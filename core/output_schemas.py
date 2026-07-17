# core/output_schemas.py
# ─────────────────────────────────────────────────────────────────────────────
# Pydantic v2 output schemas for LLM agent responses.
#
# Design principles:
#   - Fail-open: never block the pipeline — schemas warn, not raise
#   - Permissive: extra='allow' — LLMs sometimes add undeclared fields
#   - Minimal required fields: only what _build_model() strictly needs
#   - Validated in BaseAgent._call_with_retry() after _parse_json()
#
# Integration:
#   Each agent declares `output_schema = XxxOutputSchema` (class attribute).
#   BaseAgent._call_with_retry() calls schema.model_validate(data) and emits
#   a warnings.warn() on failure — data is returned unchanged regardless.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator


class _PermissiveModel(BaseModel):
    """Base for all output schemas — allows extra fields the LLM may add."""
    model_config = ConfigDict(extra="allow")


# ── BPMN ─────────────────────────────────────────────────────────────────────

class BPMNStepSchema(_PermissiveModel):
    id: str
    title: str
    description: str = ""
    actor: Optional[str] = None
    is_decision: bool = False
    task_type: str = "userTask"
    lane: Optional[str] = None

    @field_validator("id", "title")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("field cannot be blank")
        return v


class BPMNEdgeSchema(_PermissiveModel):
    source: str
    target: str
    label: str = ""
    condition: str = ""

    @field_validator("source", "target")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("field cannot be blank")
        return v


class BPMNPoolProcessSchema(_PermissiveModel):
    steps: list[BPMNStepSchema] = []
    edges: list[BPMNEdgeSchema] = []
    lanes: list[str] = []


class BPMNPoolSchema(_PermissiveModel):
    id: str
    name: str
    process: BPMNPoolProcessSchema = BPMNPoolProcessSchema()


class BPMNMessageFlowSchema(_PermissiveModel):
    id: str
    name: str = ""
    source: dict[str, Any]
    target: dict[str, Any]


class BPMNOutputSchema(_PermissiveModel):
    """Validates the raw LLM JSON from AgentBPMN (flat or collaboration)."""
    name: str
    description: str = ""
    process_trigger: str = ""
    process_outcomes: list[str] = []
    process_type: str = ""
    # Flat format
    steps: Optional[list[BPMNStepSchema]] = None
    edges: Optional[list[BPMNEdgeSchema]] = None
    lanes: Optional[list[str]] = None
    # Collaboration format
    pools: Optional[list[BPMNPoolSchema]] = None
    message_flows: Optional[list[BPMNMessageFlowSchema]] = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name cannot be empty")
        return v


# ── Minutes ───────────────────────────────────────────────────────────────────

class ActionItemSchema(_PermissiveModel):
    task: str
    responsible: str = "A definir"
    deadline: Optional[str] = None
    priority: str = "normal"
    raised_by: Optional[str] = None


class MinutesOutputSchema(_PermissiveModel):
    """Validates the raw LLM JSON from AgentMinutes."""
    title: str = "Reunião"
    date: str = ""
    location: str = ""
    participants: list[str] = []
    agenda: list[str] = []
    summary: list[Any] = []
    decisions: list[str] = []
    action_items: list[ActionItemSchema] = []
    next_meeting: Optional[str] = None
    assumptions: list[str] = []
    open_questions: list[str] = []
    risks_identified: list[str] = []
    dependencies: list[str] = []
    stakeholder_needs: list[str] = []
    meeting_antipatterns: list[Any] = []


# ── Requirements ──────────────────────────────────────────────────────────────

class RequirementItemSchema(_PermissiveModel):
    id: str
    title: str
    description: str = ""
    type: str = "functional"
    actor: Optional[str] = None
    priority: str = "unspecified"
    process_step: Optional[str] = None
    source_quote: str = ""
    speaker: Optional[str] = None
    business_rule_refs: list[str] = []
    sphere: Optional[str] = None

    @field_validator("id", "title")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("field cannot be blank")
        return v


class RequirementsOutputSchema(_PermissiveModel):
    """Validates the raw LLM JSON from AgentRequirements."""
    name: str = "Processo"
    requirements: list[RequirementItemSchema]

    @field_validator("requirements")
    @classmethod
    def requirements_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("requirements list cannot be empty")
        return v


# ── SBVR ──────────────────────────────────────────────────────────────────────

class BusinessTermSchema(_PermissiveModel):
    term: str
    definition: str
    category: str = "concept"

    @field_validator("term", "definition")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("field cannot be blank")
        return v


class BusinessRuleSchema(_PermissiveModel):
    id: str = ""
    statement: str
    short_title: str = ""
    rule_type: str = "constraint"
    source: str = ""
    sphere: str = "geral"
    sphere_owner: str = ""
    bmm_policy_ref: Optional[str] = None
    speaker_quote: str = ""

    @field_validator("statement")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("statement cannot be blank")
        return v


class SBVROutputSchema(_PermissiveModel):
    """Validates the raw LLM JSON from AgentSBVR."""
    domain: str = ""
    vocabulary: list[BusinessTermSchema] = []
    rules: list[BusinessRuleSchema] = []


# ── BMM ───────────────────────────────────────────────────────────────────────

class BMMGoalSchema(_PermissiveModel):
    id: str = ""
    name: str
    description: str = ""
    goal_type: str = "strategic"
    horizon: str = "medium"

    @field_validator("name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name cannot be blank")
        return v


class BMMStrategySchema(_PermissiveModel):
    id: str = ""
    name: str
    description: str = ""
    supports: list[str] = []


class BMMPolicySchema(_PermissiveModel):
    id: str = ""
    statement: str
    category: str = ""

    @field_validator("statement")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("statement cannot be blank")
        return v


class BMMOutputSchema(_PermissiveModel):
    """Validates the raw LLM JSON from AgentBMM."""
    vision: str = ""
    mission: str = ""
    goals: list[BMMGoalSchema] = []
    strategies: list[BMMStrategySchema] = []
    policies: list[BMMPolicySchema] = []


# ── Transcript Quality ────────────────────────────────────────────────────────

_VALID_GRADES = frozenset(["A", "B", "C", "D", "E"])


class CriterionScoreSchema(_PermissiveModel):
    criterion: str
    score: float
    justification: str = ""

    @field_validator("score")
    @classmethod
    def score_in_range(cls, v: float) -> float:
        if not (0 <= v <= 100):
            raise ValueError(f"score must be 0–100, got {v}")
        return v


class TranscriptQualityOutputSchema(_PermissiveModel):
    """Validates the raw LLM JSON from AgentTranscriptQuality."""
    criteria: list[CriterionScoreSchema]
    overall_score: float = 0.0
    grade: str = ""
    overall_summary: str = ""
    recommendation: str = ""
    inconsistencies: list[Any] = []

    @field_validator("criteria")
    @classmethod
    def criteria_not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("criteria list cannot be empty")
        return v

    @field_validator("grade")
    @classmethod
    def grade_valid(cls, v: str) -> str:
        if v and v.upper() not in _VALID_GRADES:
            raise ValueError(f"grade must be one of {_VALID_GRADES}, got {v!r}")
        return v.upper() if v else v


# ── DMN ───────────────────────────────────────────────────────────────────────

class DMNInputItemSchema(_PermissiveModel):
    label: str = ""
    expression: str = ""


class DMNOutputItemSchema(_PermissiveModel):
    label: str = ""
    value: str = ""


class DMNRuleSchema(_PermissiveModel):
    inputs: list[Any] = []
    output: str = ""
    annotation: str = ""


class DMNDecisionSchema(_PermissiveModel):
    id: str = ""
    name: str
    question: str = ""
    rationale: str = ""
    decided_by: list[str] = []
    inputs: list[DMNInputItemSchema] = []
    outputs: list[DMNOutputItemSchema] = []
    rules: list[DMNRuleSchema] = []
    hit_policy: str = "U"
    confidence: float = 1.0

    @field_validator("name")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("name cannot be blank")
        return v

    @field_validator("confidence")
    @classmethod
    def confidence_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence must be 0.0–1.0, got {v}")
        return v


class DMNOutputSchema(_PermissiveModel):
    """Validates the raw LLM JSON from AgentDMN."""
    decisions: list[DMNDecisionSchema] = []


# ── Synthesizer ───────────────────────────────────────────────────────────────

class SynthesizerOutputSchema(_PermissiveModel):
    """Validates the raw LLM JSON from AgentSynthesizer."""
    executive_summary: str
    process_narrative: str = ""
    key_insights: list[str] = []
    recommendations: list[str] = []

    @field_validator("executive_summary")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("executive_summary cannot be empty")
        return v


# ── Argumentation (IBIS) ──────────────────────────────────────────────────────

class IBISResolutionSchema(_PermissiveModel):
    type: str = "unresolved"
    chosen_alternative_id: str = ""
    rationale: str = ""
    with_caveats: list[str] = []


class IBISAlternativeSchema(_PermissiveModel):
    id: str = ""
    description: str = ""
    proposed_by: str = ""
    pros: list[str] = []
    cons: list[str] = []
    supported_by: list[str] = []
    opposed_by: list[str] = []
    was_chosen: bool = False


class IBISQuestionSchema(_PermissiveModel):
    id: str = ""
    statement: str = ""
    raised_by: str = ""
    alternatives: list[IBISAlternativeSchema] = []
    resolution: IBISResolutionSchema = IBISResolutionSchema()
    confidence: float = 1.0

    @field_validator("confidence")
    @classmethod
    def confidence_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence must be 0.0–1.0, got {v}")
        return v


class ArgumentationOutputSchema(_PermissiveModel):
    """Validates the raw LLM JSON from AgentArgumentation."""
    questions: list[IBISQuestionSchema] = []


# ── Communication Noise ───────────────────────────────────────────────────────

class AmbiguityItemSchema(_PermissiveModel):
    text: str = ""
    ambiguity_type: str = "lexical"
    speaker: str = ""
    possible_interpretations: list[str] = []
    suggestion: str = ""
    confidence: float = 0.8

    @field_validator("confidence")
    @classmethod
    def confidence_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence must be 0.0–1.0, got {v}")
        return v


class CommunicationGapSchema(_PermissiveModel):
    gap_type: str = "missing_info"
    description: str = ""
    raised_by: str = "–"
    topic: str = ""
    evidence_quote: str = ""
    impact: str = ""
    recommendation: str = ""


class CommunicationNoiseOutputSchema(_PermissiveModel):
    """Validates the raw LLM JSON from AgentCommunicationNoise."""
    ambiguities: list[AmbiguityItemSchema] = []
    gaps: list[CommunicationGapSchema] = []
    noise_score: float = 0.0
    summary: str = ""

    @field_validator("noise_score")
    @classmethod
    def score_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 10.0):
            raise ValueError(f"noise_score must be 0–10, got {v}")
        return v


# ── Knowledge Extractor ───────────────────────────────────────────────────────

class KHEntitySchema(_PermissiveModel):
    canonical_name: str = ""
    entity_type: str = "other"
    aliases: list[str] = []


class KHProcessSchema(_PermissiveModel):
    process_name: str = ""
    description: str = ""


class KHFactSchema(_PermissiveModel):
    fact_type: str = "insight"
    content: str = ""
    confidence: float = 0.9
    dialogue_act: str = ""
    utterance_speaker: Optional[str] = None

    @field_validator("confidence")
    @classmethod
    def confidence_in_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence must be 0.0–1.0, got {v}")
        return v


class KHContradictionSchema(_PermissiveModel):
    process_name: str = ""
    description: str = ""
    severity: str = "medium"


class KnowledgeExtractorOutputSchema(_PermissiveModel):
    """Validates the raw LLM JSON from AgentKnowledgeExtractor."""
    entities: list[KHEntitySchema] = []
    processes: list[KHProcessSchema] = []
    facts: list[KHFactSchema] = []
    contradictions: list[KHContradictionSchema] = []


# ── Query Summarizer ──────────────────────────────────────────────────────────

class PerspectiveSummarySchema(_PermissiveModel):
    perspective: str = ""
    label: str = ""
    headline: str = ""
    highlights: list[str] = []
    open_items: list[str] = []
    recommended_actions: list[str] = []


class QuerySummaryOutputSchema(_PermissiveModel):
    """Validates the raw LLM JSON from AgentQuerySummarizer."""
    perspectives: list[PerspectiveSummarySchema] = []


# ── Provocations ─────────────────────────────────────────────────────────────
# Schema-level checks only guard against genuinely malformed JSON (blank
# required fields). Taxonomy/confidence/tone/grounding enforcement is NOT done
# here — that's the deterministic validator in agents/agent_provocations.py
# (the "coração da proposta" per melhorias/arquivados/agente-de-provocacoes.md),
# which is the real gate before anything reaches the DB/UI. Keeping this schema
# permissive avoids conflating "expected content the validator will filter"
# (e.g. confidence="baixa") with "malformed JSON" in the PC183 quality signal.
#
# `absence_check` (melhorias/revisao-plano-provocacoes.md, PC190-fix): a
# citação existindo no transcript só prova PRESENÇA. Os dois tipos da fase 1
# alegam AUSÊNCIA ("este termo não ocorre em lugar nenhum" / "ninguém
# retomou o tema entre a objeção e o fechamento") — sem essa checagem
# separada, o validador auditava a decoração (a citação existe) e não a
# alegação em si (o "nunca" também é verdade). Ver agent_provocations.py.

class ProvocationReferenceSchema(_PermissiveModel):
    timestamp: str = ""
    speaker: str = ""
    excerpt: str = ""


class ProvocationAbsenceCheckSchema(_PermissiveModel):
    terms: list[str] = []


class ProvocationGroundingSchema(_PermissiveModel):
    type: str = ""
    references: list[ProvocationReferenceSchema] = []
    business_assets: list[str] = []
    context_artifacts: list[str] = []
    absence_check: ProvocationAbsenceCheckSchema = ProvocationAbsenceCheckSchema()


class ProvocationItemSchema(_PermissiveModel):
    kind: str = ""
    title: str
    body: str
    question: str
    grounding: ProvocationGroundingSchema = ProvocationGroundingSchema()
    confidence: str = "medium"

    @field_validator("title", "body", "question")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("field cannot be blank")
        return v


class ProvocationsOutputSchema(_PermissiveModel):
    """Validates the raw LLM JSON from AgentProvocations."""
    provocations: list[ProvocationItemSchema] = []
