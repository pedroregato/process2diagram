# tests/test_agent_provocations.py
"""
Tests for agents/agent_provocations.py — PC190 (melhorias/arquivados/agente-de-provocacoes.md)
+ PC190-fix (melhorias/revisao-plano-provocacoes.md).

The deterministic validator (AgentProvocations._validate_and_rank) is the
"coração da proposta" — the anti-hallucination gate. Every rejection rule
gets its own explicit test: this is the part that must never regress
silently, since a bug here means an ungrounded provocation could reach a
real user.

PC190-fix §1 (bloqueante): the original validator only checked PRESENCE
(quoted excerpts exist in the transcript) — but both enabled kinds actually
claim ABSENCE ("this term occurs nowhere" / "nobody revisited the topic
between the objection and the decision"). A quote existing doesn't prove
the "never" part of the claim. The fix unifies both under one primitive:
"these terms do not occur in this span" (span = whole transcript for
absence, or the turn window between the two references for asymmetry).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from agents.agent_provocations import (
    AgentProvocations, _normalize, _contains_blacklisted_tone, _span_text, _turn_positions,
)
from core.knowledge_hub import ProvocationItem
from core.output_schemas import ProvocationsOutputSchema, ProvocationItemSchema


# Formato real de hub.transcript_clean pós-preprocessamento Teams:
# "Nome   M:SS" numa linha própria, seguido do conteúdo — ver
# modules/transcript_preprocessor.py::_SPEAKER_LINE_PAT. A objeção ("João",
# 0:22) nunca é retomada antes do fechamento ("Ricardo", 0:41); "Maria" e
# "Pedro" falam de outro assunto no meio.
TRANSCRIPT = """João   0:22
Se a nota já foi emitida a gente não consegue processar o estorno rápido.
Maria   0:28
Precisamos revisar o cronograma da próxima sprint antes de tudo.
Pedro   0:35
Concordo, vamos priorizar isso na reunião de amanhã.
Ricardo   0:41
Fechado então? Todo mundo de acordo.
"""

VALID_ASYMMETRY = {
    "kind": "asymmetry",
    "title": "Objeção não respondida",
    "body": "A objeção sobre a nota foi levantada e não recebeu resposta.",
    "question": "A emissão da nota foi considerada?",
    "confidence": "high",
    "grounding": {
        "type": "turns",
        "references": [
            {"timestamp": "0:22", "speaker": "João", "excerpt": "se a nota já foi emitida a gente não consegue processar o estorno rápido"},
            {"timestamp": "0:41", "speaker": "Ricardo", "excerpt": "Fechado então? Todo mundo de acordo."},
        ],
        "absence_check": {"terms": ["nota fiscal", "estorno", "emissão"]},
    },
}

VALID_ABSENCE = {
    "kind": "absence",
    "title": "Multa não discutida",
    "body": "A reunião fechou o contrato sem mencionar penalidade por atraso.",
    "question": "Existe multa prevista?",
    "confidence": "medium",
    "grounding": {"type": "absence", "references": [], "absence_check": {"terms": ["multa por atraso", "penalidade contratual"]}},
}

# Transcript próprio pra premise — TRANSCRIPT acima não tem nenhum marcador de
# assertiva categórica (_PREMISE_MARKERS) em nenhuma linha.
PREMISE_TRANSCRIPT = """João   0:22
É claro que o Catálogo Mestre fica no SE Suíte, não precisa nem discutir.
Maria   0:28
Ok, próximo item da pauta.
Pedro   0:35
Concordo, vamos priorizar isso na reunião de amanhã.
Ricardo   0:41
Fechado então? Todo mundo de acordo.
"""

VALID_PREMISE = {
    "kind": "premise",
    "title": "Localização do Catálogo Mestre assumida sem debate",
    "body": "João afirmou a localização como óbvia; a pauta seguiu sem questionar.",
    "question": "Isso já estava decidido antes, ou fechou sem debate?",
    "confidence": "high",
    "grounding": {
        "type": "premise",
        "references": [
            {"timestamp": "0:22", "speaker": "João", "excerpt": "É claro que o Catálogo Mestre fica no SE Suíte, não precisa nem discutir."},
            {"timestamp": "0:28", "speaker": "Maria", "excerpt": "Ok, próximo item da pauta."},
        ],
    },
}


class TestNormalizeAndBlacklist:
    def test_normalize_collapses_whitespace_and_lowercases(self):
        assert _normalize("  Fechado   então?  \n") == "fechado então?"

    def test_blacklist_detects_forbidden_tone(self):
        assert _contains_blacklisted_tone("a equipe falhou em entregar", "")
        assert _contains_blacklisted_tone("", "vocês ignoraram isso")
        assert _contains_blacklisted_tone("Isso deveriam ter avisado antes", "")

    def test_blacklist_allows_descriptive_tone(self):
        assert not _contains_blacklisted_tone("A objeção não foi respondida.", "Foi considerado?")


class TestTurnPositionsAndSpan:
    """A primitiva que fundamenta toda a checagem de ausência — ver PC190-fix §1."""

    def test_turn_positions_detects_teams_format(self):
        turns = _turn_positions(TRANSCRIPT)
        seconds = [s for s, _ in turns]
        assert seconds == [22, 28, 35, 41]

    def test_turn_positions_detects_single_space_format(self):
        """hub.transcript_clean REAL (pós modules/transcript_preprocessor.py)
        tem só 1 espaço entre nome e timestamp — a limpeza final do
        preprocessador (`re.sub(r"\\s{2,}", " ", text)`) colapsa qualquer
        sequência de 2+ espaços em 1, inclusive a que separa nome de
        timestamp. Achado real da POC AURORA (2026-08-02, domínio p2d /
        contexto Projeto AURORA): a regex original exigia 2+ espaços (mesma
        de _SPEAKER_LINE_PAT, desenhada pro texto BRUTO, pré-limpeza) e nunca
        batia contra transcript_clean de verdade — 0 turnos detectados em
        produção, todo `asymmetry` rejeitado com "span_unresolved",
        silenciosamente, desde o PC190."""
        single_space = TRANSCRIPT.replace("   ", " ")
        turns = _turn_positions(single_space)
        seconds = [s for s, _ in turns]
        assert seconds == [22, 28, 35, 41]

    def test_span_resolves_with_single_space_format(self):
        single_space = TRANSCRIPT.replace("   ", " ")
        span = _span_text(single_space, "0:22", "0:41")
        assert "cronograma" in span.lower()

    def test_span_excludes_both_boundary_turns(self):
        """Exclusivo nas duas pontas de propósito — a objeção sempre menciona
        o próprio tema que levanta; incluí-la no span produziria falso
        positivo sistemático (ver docstring de _span_text)."""
        span = _span_text(TRANSCRIPT, "0:22", "0:41")
        assert "estorno" not in span.lower()   # turno da própria objeção (0:22), fora
        assert "cronograma" in span.lower()    # turno do meio, dentro
        assert "acordo" not in span.lower()    # turno da própria decisão (0:41), fora

    def test_span_excludes_content_after_upper_boundary(self):
        span = _span_text(TRANSCRIPT, "0:22", "0:35")
        assert "acordo" not in span.lower()   # turno de 0:41 fica de fora
        assert "concordo" not in span.lower()  # turno de fronteira 0:35 tb fica de fora (exclusivo)

    def test_span_empty_string_when_boundaries_are_adjacent_turns(self):
        """Dois turnos reais mas sem nada entre eles — resultado válido (o
        caso mais forte de 'ninguém retomou o tema'), não None/reprovado."""
        span = _span_text(TRANSCRIPT, "0:28", "0:35")
        assert span == ""

    def test_span_none_when_timestamps_inverted(self):
        assert _span_text(TRANSCRIPT, "0:41", "0:22") is None

    def test_span_none_when_timestamps_not_found_in_transcript(self):
        assert _span_text(TRANSCRIPT, "5:00", "6:00") is None

    def test_span_none_when_only_one_boundary_is_a_real_turn(self):
        assert _span_text(TRANSCRIPT, "0:22", "5:00") is None

    def test_span_none_when_not_timestamp_like(self):
        assert _span_text(TRANSCRIPT, "abc", "def") is None

    def test_span_none_on_transcript_without_timestamps(self):
        assert _span_text("Texto corrido sem nenhum timestamp.", "0:01", "0:02") is None


class TestValidateAndRankApproves:
    def test_valid_asymmetry_is_approved(self):
        approved, rejected, reasons = AgentProvocations._validate_and_rank([VALID_ASYMMETRY], TRANSCRIPT)
        assert len(approved) == 1
        assert rejected == 0
        assert reasons == {}
        assert approved[0].kind == "asymmetry"
        assert len(approved[0].references) == 2

    def test_valid_absence_is_approved(self):
        approved, rejected, reasons = AgentProvocations._validate_and_rank([VALID_ABSENCE], TRANSCRIPT)
        assert len(approved) == 1
        assert rejected == 0
        assert approved[0].kind == "absence"
        assert approved[0].absence_terms == ["multa por atraso", "penalidade contratual"]

    def test_asymmetry_excerpt_matching_is_whitespace_tolerant(self):
        item = dict(VALID_ASYMMETRY)
        item["grounding"] = {
            "references": [
                {"timestamp": "0:22", "excerpt": "se a nota   já foi emitida\na gente não consegue processar o estorno rápido"},
                {"timestamp": "0:41", "excerpt": "Fechado então?   Todo mundo de acordo."},
            ],
            "absence_check": {"terms": ["nota fiscal"]},
        }
        approved, rejected, _ = AgentProvocations._validate_and_rank([item], TRANSCRIPT)
        assert len(approved) == 1
        assert rejected == 0

    def test_term_present_outside_span_but_not_inside_is_approved(self):
        """O caso que prova que a primitiva de span funciona de verdade
        (PC190-fix §1) — 'cronograma' não ocorre no meio da conversa desses
        dois falantes específicos, mas testamos um termo que só aparece
        FORA do intervalo [0:22, 0:41] inteiro (antes do início)."""
        transcript_with_prefix = "Ana   0:05\nVamos falar sobre o orçamento anual primeiro.\n" + TRANSCRIPT
        item = dict(VALID_ASYMMETRY)
        item["grounding"] = {
            "references": [
                {"timestamp": "0:22", "excerpt": "se a nota já foi emitida a gente não consegue processar o estorno rápido"},
                {"timestamp": "0:41", "excerpt": "Fechado então? Todo mundo de acordo."},
            ],
            "absence_check": {"terms": ["orçamento anual"]},  # só ocorre ANTES do span
        }
        approved, rejected, _ = AgentProvocations._validate_and_rank([item], transcript_with_prefix)
        assert len(approved) == 1
        assert rejected == 0


class TestValidateAndRankRejects:
    def test_rejects_blank_required_fields(self):
        item = dict(VALID_ASYMMETRY, title="")
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], TRANSCRIPT)
        assert approved == []
        assert rejected == 1
        assert reasons == {"blank_required_field": 1}

    def test_rejects_kind_outside_enabled_taxonomy(self):
        # "premise" saiu desta lista no PC201 — virou um kind válido (ver
        # TestValidateAndRankPremise). "contradiction" nunca passa por aqui —
        # só o bridge determinístico pode produzi-lo (ver PC200).
        for kind in ("contradiction", "analogy", "insight", "sugestao"):
            item = dict(VALID_ASYMMETRY, kind=kind)
            approved, rejected, reasons = AgentProvocations._validate_and_rank([item], TRANSCRIPT)
            assert approved == [], f"kind={kind} should never be approved"
            assert reasons == {"kind_not_enabled": 1}

    def test_rejects_invalid_confidence(self):
        for conf in ("baixa", "low", "", "alta"):
            item = dict(VALID_ASYMMETRY, confidence=conf)
            approved, rejected, reasons = AgentProvocations._validate_and_rank([item], TRANSCRIPT)
            assert approved == [], f"confidence={conf!r} should never be approved"
            assert reasons == {"invalid_confidence": 1}

    def test_rejects_blacklisted_tone_in_body(self):
        item = dict(VALID_ASYMMETRY, body="A equipe falhou em considerar a objeção.")
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], TRANSCRIPT)
        assert approved == []
        assert reasons == {"blacklisted_tone": 1}

    def test_rejects_blacklisted_tone_in_question(self):
        item = dict(VALID_ASYMMETRY, question="Por que vocês ignoraram isso?")
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], TRANSCRIPT)
        assert approved == []
        assert reasons == {"blacklisted_tone": 1}

    # ── absence_check (PC190-fix §1) ────────────────────────────────────────

    def test_rejects_absence_without_absence_check(self):
        item = dict(VALID_ABSENCE, grounding={"references": []})  # sem absence_check
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], TRANSCRIPT)
        assert approved == []
        assert reasons == {"absence_check_missing": 1}

    def test_rejects_absence_check_with_empty_terms(self):
        item = dict(VALID_ABSENCE, grounding={"absence_check": {"terms": []}})
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], TRANSCRIPT)
        assert approved == []
        assert reasons == {"absence_check_missing": 1}

    def test_rejects_absence_when_term_actually_occurs_in_full_transcript(self):
        """A alegação de absence é 'não ocorre em lugar nenhum' — span = transcrição inteira."""
        item = dict(VALID_ABSENCE, grounding={"absence_check": {"terms": ["estorno"]}})  # "estorno" está no transcript
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], TRANSCRIPT)
        assert approved == []
        assert reasons == {"term_present_in_span": 1}

    def test_rejects_asymmetry_without_absence_check(self):
        item = dict(VALID_ASYMMETRY)
        item["grounding"] = {
            "references": [
                {"timestamp": "0:22", "excerpt": "se a nota já foi emitida a gente não consegue processar o estorno rápido"},
                {"timestamp": "0:41", "excerpt": "Fechado então? Todo mundo de acordo."},
            ],
            # sem absence_check — prova só que a objeção/decisão existem,
            # nunca que ninguém retomou o tema entre elas
        }
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], TRANSCRIPT)
        assert approved == []
        assert reasons == {"absence_check_missing": 1}

    def test_rejects_asymmetry_when_term_occurs_inside_span(self):
        """O caso central do bug bloqueante: a objeção FOI retomada entre os
        dois timestamps (alguém falou de 'estorno' de novo no meio) — antes
        do fix, isso passava porque só as 2 citações eram conferidas."""
        item = dict(VALID_ASYMMETRY)
        item["grounding"] = {
            "references": [
                {"timestamp": "0:22", "excerpt": "se a nota já foi emitida a gente não consegue processar o estorno rápido"},
                {"timestamp": "0:41", "excerpt": "Fechado então? Todo mundo de acordo."},
            ],
            "absence_check": {"terms": ["cronograma"]},  # "cronograma" ocorre no turno de Maria, 0:28, dentro do span
        }
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], TRANSCRIPT)
        assert approved == []
        assert reasons == {"term_present_in_span": 1}

    def test_rejects_asymmetry_with_inverted_timestamps(self):
        item = dict(VALID_ASYMMETRY)
        item["grounding"] = {
            "references": [
                {"timestamp": "0:41", "excerpt": "Fechado então? Todo mundo de acordo."},
                {"timestamp": "0:22", "excerpt": "se a nota já foi emitida a gente não consegue processar o estorno rápido"},
            ],
            "absence_check": {"terms": ["nota fiscal"]},
        }
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], TRANSCRIPT)
        assert approved == []
        assert reasons == {"span_unresolved": 1}

    def test_rejects_asymmetry_with_nonexistent_timestamps(self):
        item = dict(VALID_ASYMMETRY)
        item["grounding"] = {
            "references": [
                {"timestamp": "9:00", "excerpt": "se a nota já foi emitida a gente não consegue processar o estorno rápido"},
                {"timestamp": "9:30", "excerpt": "Fechado então? Todo mundo de acordo."},
            ],
            "absence_check": {"terms": ["nota fiscal"]},
        }
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], TRANSCRIPT)
        assert approved == []
        assert reasons == {"span_unresolved": 1}

    def test_rejects_absence_with_no_terms(self):
        item = dict(VALID_ABSENCE, grounding={"absence_check": {"terms": []}})
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], TRANSCRIPT)
        assert approved == []
        assert reasons == {"absence_check_missing": 1}

    def test_rejects_asymmetry_with_fewer_than_two_references(self):
        item = dict(VALID_ASYMMETRY)
        item["grounding"] = {
            "references": [{"timestamp": "0:22", "excerpt": "algo"}],
            "absence_check": {"terms": ["x"]},
        }
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], TRANSCRIPT)
        assert approved == []
        assert reasons == {"insufficient_references": 1}

    def test_rejects_asymmetry_with_paraphrased_excerpt(self):
        """Excerto que não é citação literal (paráfrase) é lastro inventado."""
        item = dict(VALID_ASYMMETRY)
        item["grounding"] = {
            "references": [
                {"timestamp": "0:22", "excerpt": "João mencionou um problema com a nota fiscal"},
                {"timestamp": "0:41", "excerpt": "Fechado então? Todo mundo de acordo."},
            ],
            "absence_check": {"terms": ["nota fiscal"]},
        }
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], TRANSCRIPT)
        assert approved == []
        assert reasons == {"reference_not_found": 1}

    def test_rejects_non_dict_items_without_crashing(self):
        approved, rejected, reasons = AgentProvocations._validate_and_rank(["not a dict", None, 42], TRANSCRIPT)
        assert approved == []
        assert rejected == 3
        assert reasons == {"not_a_dict": 3}


class TestValidateAndRankPremise:
    """kind='premise' (PC201) — não reduz à primitiva ausência-de-termo-em-span
    das outras kinds ('ninguém contestou' é julgamento semântico, só o LLM
    julga). O piso objetivo aqui é diferente: citação literal + marcador de
    assertiva categórica de lista fixa + turno seguinte real e posterior."""

    def test_valid_premise_is_approved(self):
        approved, rejected, reasons = AgentProvocations._validate_and_rank([VALID_PREMISE], PREMISE_TRANSCRIPT)
        assert len(approved) == 1
        assert rejected == 0
        assert reasons == {}
        item = approved[0]
        assert item.kind == "premise"
        assert len(item.references) == 2
        assert item.premise_markers == ["é claro que"]
        assert item.absence_terms == []  # não se aplica a premise

    def test_rejects_premise_without_marker(self):
        """Afirmação sem nenhum marcador de certeza/dispensa de debate —
        pode ser uma opinião comum, não uma premissa não examinada."""
        item = dict(VALID_PREMISE)
        item["grounding"] = {
            "references": [
                {"timestamp": "0:35", "speaker": "Pedro", "excerpt": "Concordo, vamos priorizar isso na reunião de amanhã."},
                {"timestamp": "0:41", "speaker": "Ricardo", "excerpt": "Fechado então? Todo mundo de acordo."},
            ],
        }
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], PREMISE_TRANSCRIPT)
        assert approved == []
        assert reasons == {"premise_marker_missing": 1}

    def test_rejects_premise_with_paraphrased_excerpt(self):
        item = dict(VALID_PREMISE)
        item["grounding"] = {
            "references": [
                {"timestamp": "0:22", "speaker": "João", "excerpt": "João disse que era óbvio onde ficava o Catálogo Mestre"},
                {"timestamp": "0:28", "speaker": "Maria", "excerpt": "Ok, próximo item da pauta."},
            ],
        }
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], PREMISE_TRANSCRIPT)
        assert approved == []
        assert reasons == {"reference_not_found": 1}

    def test_rejects_premise_with_fewer_than_two_references(self):
        item = dict(VALID_PREMISE)
        item["grounding"] = {
            "references": [
                {"timestamp": "0:22", "speaker": "João", "excerpt": "É claro que o Catálogo Mestre fica no SE Suíte, não precisa nem discutir."},
            ],
        }
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], PREMISE_TRANSCRIPT)
        assert approved == []
        assert reasons == {"insufficient_references": 1}

    def test_rejects_premise_with_inverted_turn_order(self):
        """Referência 1 (suposto 'turno seguinte') vem ANTES da premissa —
        não prova que a reunião seguiu adiante sem contestação."""
        item = dict(VALID_PREMISE)
        item["grounding"] = {
            "references": [
                {"timestamp": "0:28", "speaker": "Maria", "excerpt": "Ok, próximo item da pauta."},
                {"timestamp": "0:22", "speaker": "João", "excerpt": "É claro que o Catálogo Mestre fica no SE Suíte, não precisa nem discutir."},
            ],
        }
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], PREMISE_TRANSCRIPT)
        assert approved == []
        assert reasons == {"premise_marker_missing": 1}  # marcador só está no excerto[0], que aqui é "Ok, próximo item..."

    def test_rejects_premise_when_next_turn_timestamp_does_not_exist(self):
        """Excerto é uma citação literal real (existe em outro ponto do
        transcript), mas o timestamp anexado a ele é fabricado — não
        corresponde a nenhum turno real, então não prova que a citação
        ocorreu ONDE o LLM diz que ocorreu."""
        item = dict(VALID_PREMISE)
        item["grounding"] = {
            "references": [
                {"timestamp": "0:22", "speaker": "João", "excerpt": "É claro que o Catálogo Mestre fica no SE Suíte, não precisa nem discutir."},
                {"timestamp": "9:00", "speaker": "Alguém", "excerpt": "Ok, próximo item da pauta."},
            ],
        }
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], PREMISE_TRANSCRIPT)
        assert approved == []
        assert reasons == {"next_turn_not_after": 1}

    def test_rejects_premise_when_next_turn_same_timestamp_as_premise(self):
        item = dict(VALID_PREMISE)
        item["grounding"] = {
            "references": [
                {"timestamp": "0:22", "speaker": "João", "excerpt": "É claro que o Catálogo Mestre fica no SE Suíte, não precisa nem discutir."},
                {"timestamp": "0:22", "speaker": "João", "excerpt": "É claro que o Catálogo Mestre fica no SE Suíte, não precisa nem discutir."},
            ],
        }
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], PREMISE_TRANSCRIPT)
        assert approved == []
        assert reasons == {"next_turn_not_after": 1}

    def test_rejects_premise_blacklisted_tone(self):
        item = dict(VALID_PREMISE, body="A equipe falhou em questionar isso.")
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], PREMISE_TRANSCRIPT)
        assert approved == []
        assert reasons == {"blacklisted_tone": 1}

    def test_rejects_premise_invalid_confidence(self):
        item = dict(VALID_PREMISE, confidence="baixa")
        approved, rejected, reasons = AgentProvocations._validate_and_rank([item], PREMISE_TRANSCRIPT)
        assert approved == []
        assert reasons == {"invalid_confidence": 1}


class TestValidateAndRankCapAndRank:
    def test_caps_at_five_and_ranks_high_confidence_first(self):
        items = []
        for i in range(8):
            item = dict(VALID_ABSENCE)
            item["title"] = f"Provocação {i}"
            item["confidence"] = "high" if i % 2 == 0 else "medium"
            item["grounding"] = {"absence_check": {"terms": [f"termo inexistente {i}"]}}
            items.append(item)

        approved, rejected, reasons = AgentProvocations._validate_and_rank(items, TRANSCRIPT)
        assert len(approved) == 5
        assert rejected == 0
        # high-confidence items (even indices) ranked before medium
        confidences = [p.confidence for p in approved]
        assert confidences.count("high") == 4
        assert confidences[:4] == ["high"] * 4

    def test_zero_approved_is_a_valid_result_not_an_error(self):
        approved, rejected, reasons = AgentProvocations._validate_and_rank([], TRANSCRIPT)
        assert approved == []
        assert rejected == 0
        assert reasons == {}


class TestProvocationsOutputSchema:
    def test_valid_payload_parses(self):
        data = {"provocations": [VALID_ASYMMETRY, VALID_ABSENCE]}
        model = ProvocationsOutputSchema.model_validate(data)
        assert len(model.provocations) == 2
        assert model.provocations[0].kind == "asymmetry"
        assert model.provocations[0].grounding.absence_check.terms == ["nota fiscal", "estorno", "emissão"]

    def test_empty_provocations_is_valid(self):
        model = ProvocationsOutputSchema.model_validate({"provocations": []})
        assert model.provocations == []

    def test_extra_fields_allowed(self):
        data = {"provocations": [], "some_unexpected_field": "ok"}
        model = ProvocationsOutputSchema.model_validate(data)
        assert model.provocations == []

    def test_blank_title_raises(self):
        item = dict(VALID_ASYMMETRY, title="")
        with pytest.raises(ValidationError):
            ProvocationItemSchema.model_validate(item)

    def test_confidence_baixa_does_not_raise_at_schema_level(self):
        """Schema is permissive by design — 'baixa' is expected content the
        deterministic validator filters, not malformed JSON (see comment in
        core/output_schemas.py)."""
        item = dict(VALID_ASYMMETRY, confidence="baixa")
        model = ProvocationItemSchema.model_validate(item)
        assert model.confidence == "baixa"


class TestProvocationItemDataclass:
    def test_defaults(self):
        item = ProvocationItem(kind="absence", title="t", body="b", question="q")
        assert item.confidence == "medium"
        assert item.status == "new"
        assert item.references == []
        assert item.absence_terms == []
        assert item.db_id is None
        assert item.contradiction_ref is None


# ── bridge_contradictions — kind="contradiction" (bridge determinístico,
# sem LLM, ver comentário no topo de agent_provocations.py) ─────────────────

MEETING_ID = "meeting-current"
OTHER_MEETING_ID = "meeting-prior"
PROJECT_ID = "project-1"


def _kh_row(**overrides) -> dict:
    row = {
        "id": "kh-contra-1",
        "process_name": "Catálogo Mestre",
        "description": "Reunião 12 decidiu X; Reunião 18 decidiu o oposto.",
        "meeting_a_id": MEETING_ID,
        "meeting_b_id": OTHER_MEETING_ID,
        "severity": "high",
        "status": "open",
        "relation_type": "contradiction_direct",
        "confidence": 0.9,
        "clarifying_question": "Qual decisão vale?",
        "suggested_rewrite": "Consolidar a decisão da Reunião 18.",
    }
    row.update(overrides)
    return row


class TestBridgeContradictions:
    def test_builds_provocation_from_qualifying_row(self, monkeypatch):
        monkeypatch.setattr(
            "core.knowledge_store.get_contradictions",
            lambda project_id, status="open", limit=200: [_kh_row()],
        )
        items = AgentProvocations.bridge_contradictions(PROJECT_ID, MEETING_ID)
        assert len(items) == 1
        item = items[0]
        assert item.kind == "contradiction"
        assert item.title == "Catálogo Mestre"
        assert item.confidence == "high"  # confidence 0.9 >= 0.7
        assert item.contradiction_ref == {
            "source_contradiction_id": "kh-contra-1",
            "meeting_a_id": MEETING_ID,
            "meeting_b_id": OTHER_MEETING_ID,
            "relation_type": "contradiction_direct",
            "suggested_rewrite": "Consolidar a decisão da Reunião 18.",
        }

    def test_excludes_rows_not_detected_in_this_meeting(self, monkeypatch):
        """Só provoca na reunião onde a contradição foi detectada — evita
        reintroduzir a mesma contradição toda vez que outra reunião roda."""
        monkeypatch.setattr(
            "core.knowledge_store.get_contradictions",
            lambda project_id, status="open", limit=200: [_kh_row(meeting_a_id="meeting-other")],
        )
        assert AgentProvocations.bridge_contradictions(PROJECT_ID, MEETING_ID) == []

    def test_excludes_rows_without_meeting_b(self, monkeypatch):
        """Contradição intra-reunião (AgentKnowledgeExtractor, sem meeting_b_id)
        não é 'no tempo' — fica de fora do bridge."""
        monkeypatch.setattr(
            "core.knowledge_store.get_contradictions",
            lambda project_id, status="open", limit=200: [_kh_row(meeting_b_id=None)],
        )
        assert AgentProvocations.bridge_contradictions(PROJECT_ID, MEETING_ID) == []

    def test_excludes_rows_where_meeting_b_equals_meeting_a(self, monkeypatch):
        monkeypatch.setattr(
            "core.knowledge_store.get_contradictions",
            lambda project_id, status="open", limit=200: [_kh_row(meeting_b_id=MEETING_ID)],
        )
        assert AgentProvocations.bridge_contradictions(PROJECT_ID, MEETING_ID) == []

    def test_excludes_relation_type_outside_allowlist(self, monkeypatch):
        for relation_type in ("exception", "ambiguous", "something_unknown", ""):
            monkeypatch.setattr(
                "core.knowledge_store.get_contradictions",
                lambda project_id, status="open", limit=200, rt=relation_type: [_kh_row(relation_type=rt)],
            )
            assert AgentProvocations.bridge_contradictions(PROJECT_ID, MEETING_ID) == [], \
                f"relation_type={relation_type!r} should never bridge"

    def test_includes_superseded_relation_type(self, monkeypatch):
        """superseded = 'uma reunião reverteu a outra' — o mais próximo do
        que a proposta original chama de 'contradição no tempo' (decisão
        pendente documentada no código, não um esquecimento)."""
        monkeypatch.setattr(
            "core.knowledge_store.get_contradictions",
            lambda project_id, status="open", limit=200: [_kh_row(relation_type="superseded")],
        )
        items = AgentProvocations.bridge_contradictions(PROJECT_ID, MEETING_ID)
        assert len(items) == 1
        assert items[0].contradiction_ref["relation_type"] == "superseded"

    def test_excludes_low_severity(self, monkeypatch):
        monkeypatch.setattr(
            "core.knowledge_store.get_contradictions",
            lambda project_id, status="open", limit=200: [_kh_row(severity="low")],
        )
        assert AgentProvocations.bridge_contradictions(PROJECT_ID, MEETING_ID) == []

    def test_maps_confidence_below_threshold_to_medium(self, monkeypatch):
        monkeypatch.setattr(
            "core.knowledge_store.get_contradictions",
            lambda project_id, status="open", limit=200: [_kh_row(confidence=0.5)],
        )
        items = AgentProvocations.bridge_contradictions(PROJECT_ID, MEETING_ID)
        assert items[0].confidence == "medium"

    def test_maps_missing_or_invalid_confidence_to_medium(self, monkeypatch):
        for bad_confidence in (None, "not-a-number"):
            monkeypatch.setattr(
                "core.knowledge_store.get_contradictions",
                lambda project_id, status="open", limit=200, c=bad_confidence: [_kh_row(confidence=c)],
            )
            items = AgentProvocations.bridge_contradictions(PROJECT_ID, MEETING_ID)
            assert items[0].confidence == "medium"

    def test_falls_back_to_default_question_when_missing(self, monkeypatch):
        monkeypatch.setattr(
            "core.knowledge_store.get_contradictions",
            lambda project_id, status="open", limit=200: [_kh_row(clarifying_question="")],
        )
        items = AgentProvocations.bridge_contradictions(PROJECT_ID, MEETING_ID)
        assert "reflete a decisão atual" in items[0].question

    def test_caps_at_max_provocations(self, monkeypatch):
        rows = [_kh_row(id=f"kh-{i}") for i in range(8)]
        monkeypatch.setattr(
            "core.knowledge_store.get_contradictions",
            lambda project_id, status="open", limit=200: rows,
        )
        items = AgentProvocations.bridge_contradictions(PROJECT_ID, MEETING_ID)
        assert len(items) == 5

    def test_empty_when_no_contradictions(self, monkeypatch):
        monkeypatch.setattr(
            "core.knowledge_store.get_contradictions",
            lambda project_id, status="open", limit=200: [],
        )
        assert AgentProvocations.bridge_contradictions(PROJECT_ID, MEETING_ID) == []
