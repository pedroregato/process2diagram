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
