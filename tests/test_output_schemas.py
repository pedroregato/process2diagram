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
    # PC88
    ArgumentationOutputSchema,
    IBISQuestionSchema,
    IBISAlternativeSchema,
    IBISResolutionSchema,
    CommunicationNoiseOutputSchema,
    AmbiguityItemSchema,
    CommunicationGapSchema,
    KnowledgeExtractorOutputSchema,
    KHEntitySchema,
    KHProcessSchema,
    KHFactSchema,
    KHContradictionSchema,
    QuerySummaryOutputSchema,
    PerspectiveSummarySchema,
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


# ═══════════════════════════════════════════════════════════════════════════════
# ArgumentationOutputSchema  (PC88)
# ═══════════════════════════════════════════════════════════════════════════════

def _alternative(**kw):
    return {"id": "Q1-A1", "description": "Adotar solução interna", **kw}

def _resolution(**kw):
    return {"type": "decided", "chosen_alternative_id": "Q1-A1", **kw}

def _question(**kw):
    return {
        "id": "Q1",
        "statement": "Devemos migrar para a nuvem?",
        "alternatives": [_alternative()],
        "resolution": _resolution(),
        **kw,
    }


class TestIBISAlternativeSchema:
    def test_valid_minimal(self):
        a = IBISAlternativeSchema.model_validate({"description": "Opção A"})
        assert a.description == "Opção A"
        assert a.was_chosen is False
        assert a.pros == []
        assert a.cons == []

    def test_valid_full(self):
        a = IBISAlternativeSchema.model_validate(_alternative(
            proposed_by="Ana",
            pros=["Mais barato"],
            cons=["Menos escalável"],
            supported_by=["Ana", "Bob"],
            opposed_by=["Carlos"],
            was_chosen=True,
        ))
        assert a.was_chosen is True
        assert len(a.pros) == 1

    def test_defaults(self):
        a = IBISAlternativeSchema.model_validate({})
        assert a.id == ""
        assert a.proposed_by == ""
        assert a.supported_by == []
        assert a.opposed_by == []

    def test_extra_allowed(self):
        a = IBISAlternativeSchema.model_validate({"description": "Opção B", "llm_note": "x"})
        assert a.description == "Opção B"


class TestIBISQuestionSchema:
    def test_valid_minimal(self):
        q = IBISQuestionSchema.model_validate({"statement": "Devemos migrar?"})
        assert q.statement == "Devemos migrar?"
        assert q.alternatives == []
        assert q.confidence == 1.0

    def test_valid_full(self):
        q = IBISQuestionSchema.model_validate(_question(
            raised_by="Gerente",
            confidence=0.85,
        ))
        assert q.raised_by == "Gerente"
        assert q.confidence == 0.85
        assert q.resolution.type == "decided"

    def test_confidence_above_range_raises(self):
        with pytest.raises(ValidationError):
            IBISQuestionSchema.model_validate({"statement": "Q?", "confidence": 1.1})

    def test_confidence_below_range_raises(self):
        with pytest.raises(ValidationError):
            IBISQuestionSchema.model_validate({"statement": "Q?", "confidence": -0.1})

    def test_confidence_boundary_valid(self):
        q0 = IBISQuestionSchema.model_validate({"statement": "Q?", "confidence": 0.0})
        q1 = IBISQuestionSchema.model_validate({"statement": "Q?", "confidence": 1.0})
        assert q0.confidence == 0.0
        assert q1.confidence == 1.0

    def test_resolution_defaults(self):
        q = IBISQuestionSchema.model_validate({"statement": "Q?"})
        assert q.resolution.type == "unresolved"
        assert q.resolution.with_caveats == []

    def test_extra_allowed(self):
        q = IBISQuestionSchema.model_validate({"statement": "Q?", "extra": True})
        assert q.statement == "Q?"


class TestArgumentationOutputSchema:
    def test_empty_questions_ok(self):
        a = ArgumentationOutputSchema.model_validate({})
        assert a.questions == []

    def test_empty_list_ok(self):
        a = ArgumentationOutputSchema.model_validate({"questions": []})
        assert a.questions == []

    def test_valid_with_questions(self):
        data = {"questions": [_question(), _question(id="Q2", statement="Outro debate?")]}
        a = ArgumentationOutputSchema.model_validate(data)
        assert len(a.questions) == 2
        assert a.questions[0].resolution.chosen_alternative_id == "Q1-A1"

    def test_nested_alternative_in_question(self):
        data = {"questions": [_question(alternatives=[
            _alternative(was_chosen=True, pros=["Vantagem"]),
            _alternative(id="Q1-A2", description="Opção B", was_chosen=False),
        ])]}
        a = ArgumentationOutputSchema.model_validate(data)
        assert a.questions[0].alternatives[0].was_chosen is True
        assert a.questions[0].alternatives[1].description == "Opção B"

    def test_with_caveats_preserved(self):
        res = {**_resolution(), "with_caveats": ["Sujeito a aprovação jurídica"]}
        data = {"questions": [_question(resolution=res)]}
        a = ArgumentationOutputSchema.model_validate(data)
        assert "Sujeito a aprovação jurídica" in a.questions[0].resolution.with_caveats

    def test_extra_allowed(self):
        a = ArgumentationOutputSchema.model_validate({"meta": "ok"})
        assert a.questions == []


# ═══════════════════════════════════════════════════════════════════════════════
# CommunicationNoiseOutputSchema  (PC88)
# ═══════════════════════════════════════════════════════════════════════════════

def _ambiguity(**kw):
    return {
        "text": "ele vai fazer isso",
        "ambiguity_type": "referential",
        "possible_interpretations": ["Pedro fará", "Carlos fará"],
        **kw,
    }

def _gap(**kw):
    return {
        "gap_type": "unanswered_question",
        "description": "Quem valida o cronograma?",
        "evidence_quote": "alguém deve validar isso",
        **kw,
    }


class TestAmbiguityItemSchema:
    def test_valid_minimal(self):
        a = AmbiguityItemSchema.model_validate({"text": "ele"})
        assert a.text == "ele"
        assert a.ambiguity_type == "lexical"
        assert a.confidence == 0.8

    def test_valid_full(self):
        a = AmbiguityItemSchema.model_validate(_ambiguity(
            speaker="AS",
            suggestion="Esclarecer o referente antes de prosseguir",
            confidence=0.9,
        ))
        assert a.speaker == "AS"
        assert a.confidence == 0.9
        assert len(a.possible_interpretations) == 2

    def test_confidence_above_range_raises(self):
        with pytest.raises(ValidationError):
            AmbiguityItemSchema.model_validate({"text": "x", "confidence": 1.5})

    def test_confidence_below_range_raises(self):
        with pytest.raises(ValidationError):
            AmbiguityItemSchema.model_validate({"text": "x", "confidence": -0.1})

    def test_confidence_boundary_valid(self):
        a0 = AmbiguityItemSchema.model_validate({"text": "x", "confidence": 0.0})
        a1 = AmbiguityItemSchema.model_validate({"text": "x", "confidence": 1.0})
        assert a0.confidence == 0.0
        assert a1.confidence == 1.0

    def test_defaults(self):
        a = AmbiguityItemSchema.model_validate({})
        assert a.text == ""
        assert a.speaker == ""
        assert a.possible_interpretations == []
        assert a.suggestion == ""

    def test_extra_allowed(self):
        a = AmbiguityItemSchema.model_validate({"text": "algo", "llm_note": "ok"})
        assert a.text == "algo"


class TestCommunicationGapSchema:
    def test_valid_minimal(self):
        g = CommunicationGapSchema.model_validate({"description": "Pergunta sem resposta"})
        assert g.gap_type == "missing_info"
        assert g.raised_by == "–"

    def test_valid_full(self):
        g = CommunicationGapSchema.model_validate(_gap(
            raised_by="PM",
            topic="Cronograma",
            impact="Bloqueia planejamento",
            recommendation="Definir responsável na próxima reunião",
        ))
        assert g.raised_by == "PM"
        assert g.topic == "Cronograma"

    def test_defaults(self):
        g = CommunicationGapSchema.model_validate({})
        assert g.description == ""
        assert g.evidence_quote == ""
        assert g.impact == ""
        assert g.recommendation == ""

    def test_extra_allowed(self):
        g = CommunicationGapSchema.model_validate({"description": "gap", "x": 1})
        assert g.description == "gap"


class TestCommunicationNoiseOutputSchema:
    def test_all_empty_ok(self):
        c = CommunicationNoiseOutputSchema.model_validate({})
        assert c.ambiguities == []
        assert c.gaps == []
        assert c.noise_score == 0.0
        assert c.summary == ""

    def test_full_data(self):
        data = {
            "ambiguities": [_ambiguity()],
            "gaps": [_gap()],
            "noise_score": 4.5,
            "summary": "Comunicação com ruído moderado.",
        }
        c = CommunicationNoiseOutputSchema.model_validate(data)
        assert len(c.ambiguities) == 1
        assert len(c.gaps) == 1
        assert c.noise_score == 4.5
        assert c.summary == "Comunicação com ruído moderado."

    def test_noise_score_above_range_raises(self):
        with pytest.raises(ValidationError):
            CommunicationNoiseOutputSchema.model_validate({"noise_score": 10.1})

    def test_noise_score_below_range_raises(self):
        with pytest.raises(ValidationError):
            CommunicationNoiseOutputSchema.model_validate({"noise_score": -0.5})

    def test_noise_score_boundary_valid(self):
        c0  = CommunicationNoiseOutputSchema.model_validate({"noise_score": 0.0})
        c10 = CommunicationNoiseOutputSchema.model_validate({"noise_score": 10.0})
        assert c0.noise_score == 0.0
        assert c10.noise_score == 10.0

    def test_extra_allowed(self):
        c = CommunicationNoiseOutputSchema.model_validate({"meta": "ok"})
        assert c.noise_score == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# KnowledgeExtractorOutputSchema  (PC88)
# ═══════════════════════════════════════════════════════════════════════════════

def _kh_entity(**kw):
    return {"canonical_name": "Maria de Fátima", "entity_type": "person", **kw}

def _kh_fact(**kw):
    return {
        "fact_type": "decision",
        "content": "Ficou decidido migrar para a nuvem em julho.",
        "confidence": 0.95,
        "dialogue_act": "decision",
        **kw,
    }


class TestKHFactSchema:
    def test_valid_minimal(self):
        f = KHFactSchema.model_validate({"content": "Um fato importante."})
        assert f.fact_type == "insight"
        assert f.confidence == 0.9
        assert f.utterance_speaker is None

    def test_valid_full(self):
        f = KHFactSchema.model_validate(_kh_fact(
            utterance_speaker="MF",
        ))
        assert f.fact_type == "decision"
        assert f.utterance_speaker == "MF"

    def test_confidence_above_range_raises(self):
        with pytest.raises(ValidationError):
            KHFactSchema.model_validate({"content": "x", "confidence": 1.01})

    def test_confidence_below_range_raises(self):
        with pytest.raises(ValidationError):
            KHFactSchema.model_validate({"content": "x", "confidence": -0.01})

    def test_confidence_boundary_valid(self):
        f0 = KHFactSchema.model_validate({"content": "x", "confidence": 0.0})
        f1 = KHFactSchema.model_validate({"content": "x", "confidence": 1.0})
        assert f0.confidence == 0.0
        assert f1.confidence == 1.0

    def test_defaults(self):
        f = KHFactSchema.model_validate({})
        assert f.content == ""
        assert f.dialogue_act == ""
        assert f.utterance_speaker is None

    def test_extra_allowed(self):
        f = KHFactSchema.model_validate({"content": "fato", "extra": True})
        assert f.content == "fato"


class TestKnowledgeExtractorOutputSchema:
    def test_all_empty_ok(self):
        k = KnowledgeExtractorOutputSchema.model_validate({})
        assert k.entities == []
        assert k.processes == []
        assert k.facts == []
        assert k.contradictions == []

    def test_full_data(self):
        data = {
            "entities": [_kh_entity(), _kh_entity(canonical_name="SAP", entity_type="system")],
            "processes": [{"process_name": "Processo de Aprovação", "description": "Fluxo de aprovação"}],
            "facts": [_kh_fact()],
            "contradictions": [{"description": "Antes era 5 dias, agora é 3.", "severity": "medium"}],
        }
        k = KnowledgeExtractorOutputSchema.model_validate(data)
        assert len(k.entities) == 2
        assert k.entities[1].entity_type == "system"
        assert len(k.processes) == 1
        assert k.processes[0].process_name == "Processo de Aprovação"
        assert len(k.facts) == 1
        assert k.facts[0].confidence == 0.95
        assert k.contradictions[0].severity == "medium"

    def test_entity_defaults(self):
        e = KHEntitySchema.model_validate({})
        assert e.canonical_name == ""
        assert e.entity_type == "other"
        assert e.aliases == []

    def test_process_defaults(self):
        p = KHProcessSchema.model_validate({"process_name": "Onboarding"})
        assert p.description == ""

    def test_contradiction_defaults(self):
        c = KHContradictionSchema.model_validate({"description": "Conflito"})
        assert c.process_name == ""
        assert c.severity == "medium"

    def test_extra_allowed(self):
        k = KnowledgeExtractorOutputSchema.model_validate({"meta": "ok"})
        assert k.facts == []


# ═══════════════════════════════════════════════════════════════════════════════
# QuerySummaryOutputSchema  (PC88)
# ═══════════════════════════════════════════════════════════════════════════════

def _perspective(**kw):
    return {
        "perspective": "executive",
        "label": "Executivo",
        "headline": "Projeto aprovado com risco de prazo.",
        "highlights": ["Orçamento aprovado", "Escopo definido"],
        "open_items": ["Fornecedor ainda não selecionado"],
        "recommended_actions": ["Convocar reunião de seleção de fornecedor"],
        **kw,
    }


class TestPerspectiveSummarySchema:
    def test_valid_minimal(self):
        p = PerspectiveSummarySchema.model_validate({"perspective": "technical"})
        assert p.perspective == "technical"
        assert p.label == ""
        assert p.headline == ""
        assert p.highlights == []

    def test_valid_full(self):
        p = PerspectiveSummarySchema.model_validate(_perspective())
        assert p.perspective == "executive"
        assert len(p.highlights) == 2
        assert len(p.open_items) == 1
        assert len(p.recommended_actions) == 1

    def test_defaults(self):
        p = PerspectiveSummarySchema.model_validate({})
        assert p.perspective == ""
        assert p.open_items == []
        assert p.recommended_actions == []

    def test_extra_allowed(self):
        p = PerspectiveSummarySchema.model_validate({"perspective": "compliance", "extra": 1})
        assert p.perspective == "compliance"


class TestQuerySummaryOutputSchema:
    def test_empty_ok(self):
        q = QuerySummaryOutputSchema.model_validate({})
        assert q.perspectives == []

    def test_four_perspectives(self):
        data = {"perspectives": [
            _perspective(perspective="executive", label="Executivo"),
            _perspective(perspective="technical", label="Técnico"),
            _perspective(perspective="project_manager", label="Gestor de Projeto"),
            _perspective(perspective="compliance", label="Conformidade & Auditoria"),
        ]}
        q = QuerySummaryOutputSchema.model_validate(data)
        assert len(q.perspectives) == 4
        assert q.perspectives[0].perspective == "executive"
        assert q.perspectives[3].label == "Conformidade & Auditoria"

    def test_perspective_content_preserved(self):
        data = {"perspectives": [_perspective()]}
        q = QuerySummaryOutputSchema.model_validate(data)
        assert q.perspectives[0].headline == "Projeto aprovado com risco de prazo."
        assert "Orçamento aprovado" in q.perspectives[0].highlights

    def test_extra_allowed(self):
        q = QuerySummaryOutputSchema.model_validate({"generated_at": "2026-06-28"})
        assert q.perspectives == []
