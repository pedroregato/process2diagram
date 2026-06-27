# tests/test_output_schemas.py
"""
Tests for core/output_schemas.py — Pydantic v2 fail-open output schemas.

Coverage goals:
  - Valid data passes model_validate without error
  - Required-field violations raise ValidationError
  - Extra fields are silently accepted (extra='allow')
  - field_validator constraints fire correctly
  - Optional fields default correctly
"""

import pytest
from pydantic import ValidationError

from core.output_schemas import (
    BPMNOutputSchema,
    BPMNStepSchema,
    BPMNEdgeSchema,
    BPMNPoolSchema,
    BPMNPoolProcessSchema,
    BPMNMessageFlowSchema,
    MinutesOutputSchema,
    ActionItemSchema,
    RequirementsOutputSchema,
    RequirementItemSchema,
    SBVROutputSchema,
    BusinessTermSchema,
    BusinessRuleSchema,
    BMMOutputSchema,
    BMMGoalSchema,
    BMMStrategySchema,
    BMMPolicySchema,
    TranscriptQualityOutputSchema,
    CriterionScoreSchema,
    SynthesizerOutputSchema,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _step(**kw):
    return {"id": "s1", "title": "Passo 1", **kw}

def _edge(**kw):
    return {"source": "s1", "target": "s2", **kw}

def _criterion(**kw):
    return {"criterion": "Clareza", "score": 80.0, **kw}

def _requirement(**kw):
    return {"id": "R1", "title": "Requisito", **kw}

def _term(**kw):
    return {"term": "Processo", "definition": "Sequência de atividades", **kw}

def _rule(**kw):
    return {"statement": "O sistema deve validar o usuário", **kw}

def _goal(**kw):
    return {"name": "Expandir mercado", **kw}

def _policy(**kw):
    return {"statement": "Toda transação deve ser auditada", **kw}


# ═══════════════════════════════════════════════════════════════════════════════
# BPMNStepSchema
# ═══════════════════════════════════════════════════════════════════════════════

class TestBPMNStepSchema:
    def test_valid_minimal(self):
        s = BPMNStepSchema.model_validate(_step())
        assert s.id == "s1"
        assert s.title == "Passo 1"
        assert s.is_decision is False
        assert s.task_type == "userTask"

    def test_valid_full(self):
        s = BPMNStepSchema.model_validate(_step(
            description="desc", actor="Analista",
            is_decision=True, task_type="serviceTask", lane="TI",
        ))
        assert s.is_decision is True
        assert s.lane == "TI"

    def test_blank_id_raises(self):
        with pytest.raises(ValidationError):
            BPMNStepSchema.model_validate(_step(id="  "))

    def test_blank_title_raises(self):
        with pytest.raises(ValidationError):
            BPMNStepSchema.model_validate(_step(title=""))

    def test_extra_fields_allowed(self):
        s = BPMNStepSchema.model_validate(_step(unknown_field="x"))
        assert s.id == "s1"


# ═══════════════════════════════════════════════════════════════════════════════
# BPMNEdgeSchema
# ═══════════════════════════════════════════════════════════════════════════════

class TestBPMNEdgeSchema:
    def test_valid(self):
        e = BPMNEdgeSchema.model_validate(_edge())
        assert e.source == "s1"
        assert e.label == ""

    def test_blank_source_raises(self):
        with pytest.raises(ValidationError):
            BPMNEdgeSchema.model_validate(_edge(source=""))

    def test_blank_target_raises(self):
        with pytest.raises(ValidationError):
            BPMNEdgeSchema.model_validate(_edge(target="  "))

    def test_extra_allowed(self):
        e = BPMNEdgeSchema.model_validate(_edge(color="red"))
        assert e.source == "s1"


# ═══════════════════════════════════════════════════════════════════════════════
# BPMNOutputSchema
# ═══════════════════════════════════════════════════════════════════════════════

class TestBPMNOutputSchema:
    def test_flat_minimal(self):
        data = {"name": "Processo de Compra", "steps": [_step()], "edges": []}
        b = BPMNOutputSchema.model_validate(data)
        assert b.name == "Processo de Compra"
        assert len(b.steps) == 1

    def test_flat_with_lanes(self):
        data = {
            "name": "Proc",
            "steps": [_step(lane="Financeiro")],
            "edges": [_edge()],
            "lanes": ["Financeiro", "TI"],
        }
        b = BPMNOutputSchema.model_validate(data)
        assert b.lanes == ["Financeiro", "TI"]

    def test_collaboration(self):
        data = {
            "name": "Collab",
            "pools": [{"id": "p1", "name": "Empresa A"}],
            "message_flows": [],
        }
        b = BPMNOutputSchema.model_validate(data)
        assert len(b.pools) == 1

    def test_blank_name_raises(self):
        with pytest.raises(ValidationError):
            BPMNOutputSchema.model_validate({"name": ""})

    def test_extra_fields_allowed(self):
        data = {"name": "Proc", "llm_notes": "some note"}
        b = BPMNOutputSchema.model_validate(data)
        assert b.name == "Proc"

    def test_optional_fields_default_to_none(self):
        b = BPMNOutputSchema.model_validate({"name": "Proc"})
        assert b.steps is None
        assert b.pools is None
        assert b.process_trigger == ""

    def test_process_metadata(self):
        data = {
            "name": "Proc",
            "process_trigger": "Solicitação do cliente",
            "process_outcomes": ["Pedido aprovado"],
            "process_type": "approval",
        }
        b = BPMNOutputSchema.model_validate(data)
        assert b.process_trigger == "Solicitação do cliente"
        assert b.process_outcomes == ["Pedido aprovado"]


# ═══════════════════════════════════════════════════════════════════════════════
# MinutesOutputSchema
# ═══════════════════════════════════════════════════════════════════════════════

class TestMinutesOutputSchema:
    def test_all_optional(self):
        m = MinutesOutputSchema.model_validate({})
        assert m.title == "Reunião"
        assert m.participants == []
        assert m.action_items == []

    def test_full(self):
        data = {
            "title": "Sprint Planning",
            "date": "2026-06-27",
            "participants": ["Ana", "Bob"],
            "decisions": ["Priorizar feature X"],
            "action_items": [{"task": "Criar issue", "responsible": "Ana"}],
        }
        m = MinutesOutputSchema.model_validate(data)
        assert m.title == "Sprint Planning"
        assert len(m.action_items) == 1
        assert m.action_items[0].task == "Criar issue"

    def test_action_item_defaults(self):
        ai = ActionItemSchema.model_validate({"task": "Revisar doc"})
        assert ai.responsible == "A definir"
        assert ai.priority == "normal"

    def test_extra_allowed(self):
        m = MinutesOutputSchema.model_validate({"extra_key": 42})
        assert m.title == "Reunião"


# ═══════════════════════════════════════════════════════════════════════════════
# RequirementsOutputSchema
# ═══════════════════════════════════════════════════════════════════════════════

class TestRequirementsOutputSchema:
    def test_valid(self):
        data = {"requirements": [_requirement()]}
        r = RequirementsOutputSchema.model_validate(data)
        assert len(r.requirements) == 1

    def test_empty_list_raises(self):
        with pytest.raises(ValidationError):
            RequirementsOutputSchema.model_validate({"requirements": []})

    def test_missing_requirements_raises(self):
        with pytest.raises(ValidationError):
            RequirementsOutputSchema.model_validate({})

    def test_requirement_defaults(self):
        r = RequirementItemSchema.model_validate(_requirement())
        assert r.type == "functional"
        assert r.priority == "unspecified"
        assert r.business_rule_refs == []

    def test_requirement_blank_id_raises(self):
        with pytest.raises(ValidationError):
            RequirementItemSchema.model_validate(_requirement(id=""))

    def test_requirement_blank_title_raises(self):
        with pytest.raises(ValidationError):
            RequirementItemSchema.model_validate(_requirement(title="  "))

    def test_extra_allowed(self):
        data = {"requirements": [_requirement()], "meta": "extra"}
        r = RequirementsOutputSchema.model_validate(data)
        assert r.name == "Processo"


# ═══════════════════════════════════════════════════════════════════════════════
# SBVROutputSchema
# ═══════════════════════════════════════════════════════════════════════════════

class TestSBVROutputSchema:
    def test_empty_lists_ok(self):
        s = SBVROutputSchema.model_validate({})
        assert s.vocabulary == []
        assert s.rules == []

    def test_with_terms_and_rules(self):
        data = {
            "domain": "Financeiro",
            "vocabulary": [_term()],
            "rules": [_rule()],
        }
        s = SBVROutputSchema.model_validate(data)
        assert s.domain == "Financeiro"
        assert len(s.vocabulary) == 1
        assert s.vocabulary[0].category == "concept"

    def test_blank_term_raises(self):
        with pytest.raises(ValidationError):
            BusinessTermSchema.model_validate(_term(term=""))

    def test_blank_definition_raises(self):
        with pytest.raises(ValidationError):
            BusinessTermSchema.model_validate(_term(definition="  "))

    def test_blank_rule_statement_raises(self):
        with pytest.raises(ValidationError):
            BusinessRuleSchema.model_validate({"statement": ""})

    def test_rule_defaults(self):
        r = BusinessRuleSchema.model_validate(_rule())
        assert r.rule_type == "constraint"
        assert r.sphere == "geral"
        assert r.id == ""

    def test_extra_allowed(self):
        s = SBVROutputSchema.model_validate({"extra": True})
        assert s.rules == []


# ═══════════════════════════════════════════════════════════════════════════════
# BMMOutputSchema
# ═══════════════════════════════════════════════════════════════════════════════

class TestBMMOutputSchema:
    def test_all_optional(self):
        b = BMMOutputSchema.model_validate({})
        assert b.vision == ""
        assert b.goals == []

    def test_full(self):
        data = {
            "vision": "Ser líder de mercado",
            "mission": "Entregar valor",
            "goals": [_goal()],
            "strategies": [{"name": "Expansão regional"}],
            "policies": [_policy()],
        }
        b = BMMOutputSchema.model_validate(data)
        assert b.vision == "Ser líder de mercado"
        assert len(b.goals) == 1
        assert b.goals[0].goal_type == "strategic"

    def test_blank_goal_name_raises(self):
        with pytest.raises(ValidationError):
            BMMGoalSchema.model_validate({"name": ""})

    def test_blank_policy_statement_raises(self):
        with pytest.raises(ValidationError):
            BMMPolicySchema.model_validate({"statement": "  "})

    def test_strategy_supports_default(self):
        s = BMMStrategySchema.model_validate({"name": "S1"})
        assert s.supports == []

    def test_extra_allowed(self):
        b = BMMOutputSchema.model_validate({"unknown": 99})
        assert b.mission == ""


# ═══════════════════════════════════════════════════════════════════════════════
# TranscriptQualityOutputSchema
# ═══════════════════════════════════════════════════════════════════════════════

class TestTranscriptQualityOutputSchema:
    def test_valid(self):
        data = {
            "criteria": [_criterion()],
            "overall_score": 75.0,
            "grade": "B",
        }
        t = TranscriptQualityOutputSchema.model_validate(data)
        assert t.grade == "B"
        assert t.overall_score == 75.0

    def test_empty_criteria_raises(self):
        with pytest.raises(ValidationError):
            TranscriptQualityOutputSchema.model_validate({"criteria": []})

    def test_missing_criteria_raises(self):
        with pytest.raises(ValidationError):
            TranscriptQualityOutputSchema.model_validate({"overall_score": 80})

    def test_grade_normalized_to_upper(self):
        data = {"criteria": [_criterion()], "grade": "a"}
        t = TranscriptQualityOutputSchema.model_validate(data)
        assert t.grade == "A"

    def test_invalid_grade_raises(self):
        with pytest.raises(ValidationError):
            TranscriptQualityOutputSchema.model_validate({
                "criteria": [_criterion()],
                "grade": "F",
            })

    def test_score_out_of_range_raises(self):
        with pytest.raises(ValidationError):
            CriterionScoreSchema.model_validate({"criterion": "X", "score": 101.0})

    def test_score_negative_raises(self):
        with pytest.raises(ValidationError):
            CriterionScoreSchema.model_validate({"criterion": "X", "score": -1.0})

    def test_score_boundary_valid(self):
        c0  = CriterionScoreSchema.model_validate({"criterion": "X", "score": 0.0})
        c100 = CriterionScoreSchema.model_validate({"criterion": "X", "score": 100.0})
        assert c0.score == 0.0
        assert c100.score == 100.0

    def test_empty_grade_allowed(self):
        data = {"criteria": [_criterion()], "grade": ""}
        t = TranscriptQualityOutputSchema.model_validate(data)
        assert t.grade == ""

    def test_extra_allowed(self):
        data = {"criteria": [_criterion()], "raw_llm_notes": "ok"}
        t = TranscriptQualityOutputSchema.model_validate(data)
        assert t.overall_score == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# SynthesizerOutputSchema
# ═══════════════════════════════════════════════════════════════════════════════

class TestSynthesizerOutputSchema:
    def test_valid_minimal(self):
        s = SynthesizerOutputSchema.model_validate({
            "executive_summary": "Resumo executivo do processo."
        })
        assert s.executive_summary == "Resumo executivo do processo."
        assert s.key_insights == []
        assert s.recommendations == []

    def test_full(self):
        data = {
            "executive_summary": "Resumo.",
            "process_narrative": "Narrativa do processo.",
            "key_insights": ["Insight 1", "Insight 2"],
            "recommendations": ["Ação A"],
        }
        s = SynthesizerOutputSchema.model_validate(data)
        assert len(s.key_insights) == 2

    def test_blank_summary_raises(self):
        with pytest.raises(ValidationError):
            SynthesizerOutputSchema.model_validate({"executive_summary": ""})

    def test_whitespace_summary_raises(self):
        with pytest.raises(ValidationError):
            SynthesizerOutputSchema.model_validate({"executive_summary": "   "})

    def test_missing_summary_raises(self):
        with pytest.raises(ValidationError):
            SynthesizerOutputSchema.model_validate({})

    def test_extra_allowed(self):
        s = SynthesizerOutputSchema.model_validate({
            "executive_summary": "Ok",
            "llm_model_used": "deepseek-v4",
        })
        assert s.executive_summary == "Ok"
