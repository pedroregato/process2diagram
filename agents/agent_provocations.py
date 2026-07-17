# agents/agent_provocations.py
# ─────────────────────────────────────────────────────────────────────────────
# AgentProvocations — gera "Provocações": observações lastreadas sobre o que
# ficou fechado numa reunião sem ter sido examinado.
#
# Fase 1 (melhorias/arquivados/agente-de-provocacoes.md): apenas os tipos
# `absence` e `asymmetry`, com evidência (`grounding`) verificada exclusivamente
# contra a transcrição da própria reunião — sem leitura de memória do contexto
# ou de Ativos de Negócio (isso fica para uma fase futura, ver o arquivo acima).
#
# A restrição central da proposta não é de prompt, é de arquitetura: nenhuma
# provocação sai sem lastro verificado em código. O validador determinístico
# abaixo (_validate_and_rank) é o "coração da proposta" — roda sempre, mesmo
# que o LLM produza uma saída "perfeita", e descarta silenciosamente qualquer
# item cuja evidência não resista à conferência literal contra o transcript.
#
# PC190-fix (melhorias/revisao-plano-provocacoes.md §1, bloqueante): a
# primeira versão só conferia PRESENÇA — que as citações existem no
# transcript. Mas os dois tipos da fase 1 alegam AUSÊNCIA: "este termo não
# ocorre em lugar nenhum" (absence) e "ninguém retomou o tema entre a
# objeção e o fechamento" (asymmetry) — a citação existir não prova o
# "nunca". Ambos se reduzem a uma primitiva única: "estes termos não
# ocorrem neste span" — span = transcrição inteira (absence) ou a janela
# de turnos entre as duas referências (asymmetry). Ver _span_text().
#
# Reads:  hub.transcript_clean
# Writes: hub.provocations (ProvocationsModel)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import logging
import re
from collections import Counter

from agents.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub, ProvocationsModel, ProvocationItem
from core.output_schemas import ProvocationsOutputSchema
from modules.transcript_preprocessor import _SPEAKER_LINE_PAT
from modules.transcript_time_parser import _ts_to_seconds
from modules.transcript_time_parser import _PATTERNS as _OTHER_PATTERNS, _TS_FIRST_PATTERNS as _OTHER_TS_FIRST

_logger = logging.getLogger(__name__)

_ENABLED_KINDS = {"absence", "asymmetry"}
_ALLOWED_CONFIDENCE = {"high", "medium"}
_MAX_PROVOCATIONS = 5

# Regras de tom — melhorias/arquivados/agente-de-provocacoes.md §4:
# "proibido 'vocês ignoraram', 'a equipe falhou', 'deveriam ter'... isto entra
# no skill como regra explícita E como checagem de lista negra no validador."
_TONE_BLACKLIST = (
    "vocês ignoraram", "voces ignoraram",
    "a equipe falhou",
    "deveriam ter",
)

_CONFIDENCE_RANK = {"high": 0, "medium": 1}
_TIMESTAMP_RE = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")


def _normalize(text: str) -> str:
    """Lowercase + colapsa espaços — para correspondência literal tolerante a formatação."""
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def _contains_blacklisted_tone(*texts: str) -> bool:
    haystack = _normalize(" ".join(texts))
    return any(term in haystack for term in _TONE_BLACKLIST)


# `_SPEAKER_LINE_PAT` (modules/transcript_preprocessor.py) casa o formato REAL
# de hub.transcript_clean pós-preprocessamento Teams: "Nome   0:03" numa linha
# própria, SEM dois-pontos (confirmado empiricamente contra
# test-scenarios/cenario-teste-002/transcricao.txt — os 6 padrões de
# modules/transcript_time_parser.py, todos com ':' obrigatório no fim, NÃO
# casam nada nesse formato: parse_transcript_timings() nele retorna
# has_timestamps=False). Reusa o pattern original (mesma fonte da verdade),
# só recompilado com re.MULTILINE para varrer o texto inteiro de uma vez em
# vez de linha a linha.
_TEAMS_SPEAKER_LINE = re.compile(_SPEAKER_LINE_PAT.pattern, re.MULTILINE)


def _turn_positions(transcript: str) -> list[tuple[int, int]]:
    """
    Detecta turnos com timestamp no transcript. Tenta o formato Teams (o real
    formato de hub.transcript_clean neste projeto) e os formatos alternativos
    de transcript_time_parser.py, ficando com o que casar mais vezes — mesma
    heurística de parse_transcript_timings(). Retorna
    [(segundos, posição_no_texto), ...] ordenado por posição (ordem real do
    transcript, não por segundo — a posição é o que importa para fatiar texto).
    """
    best_turns: list[tuple[int, int]] = []

    teams_turns = [
        (_ts_to_seconds(m.group(2)), m.start())
        for m in _TEAMS_SPEAKER_LINE.finditer(transcript)
    ]
    if len(teams_turns) > len(best_turns):
        best_turns = teams_turns

    for fmt_name, pattern in _OTHER_PATTERNS:
        turns: list[tuple[int, int]] = []
        for m in pattern.finditer(transcript):
            groups = m.groups()
            ts_str = groups[0] if fmt_name in _OTHER_TS_FIRST else groups[1]
            turns.append((_ts_to_seconds(ts_str), m.start()))
        if len(turns) > len(best_turns):
            best_turns = turns

    best_turns.sort(key=lambda t: t[1])
    return best_turns


def _looks_like_timestamp(ts: str) -> bool:
    return bool(_TIMESTAMP_RE.match((ts or "").strip()))


def _span_text(transcript: str, ts_from: str, ts_to: str) -> str | None:
    """
    Texto de todos os turnos ESTRITAMENTE ENTRE ts_from e ts_to (exclusivo nas
    duas pontas) — do início do primeiro turno depois de ts_from até o início
    do turno em ts_to (ou fim do transcript).

    Exclusivo de propósito: os dois turnos de fronteira são a própria objeção
    e a própria decisão (já conferidos separadamente via `references` —
    citação literal). Incluí-los aqui produziria falso positivo sistemático
    — a objeção NECESSARIAMENTE menciona o termo do próprio tema que ela
    levanta, então checar o termo dentro do turno da objeção sempre "acharia"
    o termo, mesmo quando ninguém jamais retomou o assunto depois dela.

    Retorna None (span não resolvível — a alegação não pode ser verificada,
    então é reprovada, nunca aprovada por omissão) quando:
      - ts_from/ts_to não parecem timestamps válidos
      - ts_from >= ts_to (invertidos ou iguais)
      - o transcript não tem timestamps detectáveis
      - ts_from ou ts_to não correspondem a um turno real detectado
        (timestamp fabricado/inexistente no transcript)

    Retorna "" (span vazio, um resultado VÁLIDO — nenhum turno entre os dois
    marcos, o caso mais forte possível de "ninguém retomou o tema") quando os
    dois timestamps são turnos reais mas adjacentes.
    """
    if not (_looks_like_timestamp(ts_from) and _looks_like_timestamp(ts_to)):
        return None
    sec_from, sec_to = _ts_to_seconds(ts_from), _ts_to_seconds(ts_to)
    if sec_from >= sec_to:
        return None

    turns = _turn_positions(transcript)
    if not turns:
        return None

    known_seconds = {sec for sec, _ in turns}
    if sec_from not in known_seconds or sec_to not in known_seconds:
        return None

    in_range = [pos for (sec, pos) in turns if sec_from < sec < sec_to]
    if not in_range:
        return ""

    start = min(in_range)
    end_candidates = [pos for (sec, pos) in turns if pos > max(in_range)]
    end = min(end_candidates) if end_candidates else len(transcript)
    return transcript[start:end]


class AgentProvocations(BaseAgent):

    name                = "provocations"
    skill_path          = "skills/skill_provocations.md"
    required_hub_fields = ["transcript_clean"]
    output_schema       = ProvocationsOutputSchema

    # ── Prompt ────────────────────────────────────────────────────────────────

    def build_prompt(
        self, hub: KnowledgeHub, output_language: str = "Auto-detect"
    ) -> tuple[str, str]:
        lang   = self._language_instruction(output_language)
        system = self._skill.replace("{output_language}", lang)

        user = (
            "Examine esta transcrição de reunião e produza provocações lastreadas, "
            "seguindo a taxonomia e o formato de saída definidos no seu prompt de sistema.\n\n"
            f"## Transcrição\n\n{hub.transcript_clean}"
        )
        return system, user

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(
        self, hub: KnowledgeHub, output_language: str = "Auto-detect"
    ) -> KnowledgeHub:
        system, user = self.build_prompt(hub, output_language)
        data = self._call_with_retry(system, user, hub)

        raw_items = (data or {}).get("provocations") or []
        approved, rejected_count, rejected_reasons = self._validate_and_rank(
            raw_items, hub.transcript_clean or ""
        )
        # PC190-fix §4 (melhorias/revisao-plano-provocacoes.md): a taxa de
        # reprovação é o sinal de alucinação e precisa ser observável antes do
        # usuário notar. Persistência estruturada (tabela/telemetria própria)
        # fica para uma rodada futura — este log é o mínimo viável agora,
        # já mais visível que nada: aparece nos logs do Streamlit Cloud com
        # o breakdown por motivo, não só uma contagem.
        if raw_items:
            _logger.info(
                "AgentProvocations: %d gerada(s), %d aprovada(s), %d reprovada(s) %s",
                len(raw_items), len(approved), rejected_count, rejected_reasons or "",
            )

        hub.provocations = ProvocationsModel(
            items=approved,
            rejected_count=rejected_count,
            rejected_reasons=rejected_reasons,
            ready=True,
        )
        hub.mark_agent_run(self.name)
        hub.bump()
        return hub

    # ── Validador determinístico (sem LLM) ──────────────────────────────────────
    # "A passagem [2] é o coração da proposta. Ela é determinística e barata.
    # Não a substitua por um 'agente validador' — validar existência de string
    # não é tarefa para LLM. Um LLM validando outro LLM só multiplica o custo
    # e a superfície de alucinação." (melhorias/arquivados/agente-de-provocacoes.md)

    @staticmethod
    def _validate_and_rank(
        raw_items: list[dict], transcript: str
    ) -> tuple[list[ProvocationItem], int, dict]:
        transcript_norm = _normalize(transcript)
        approved: list[ProvocationItem] = []
        reasons: Counter = Counter()

        def reject(reason: str) -> None:
            reasons[reason] += 1

        for item in raw_items:
            if not isinstance(item, dict):
                reject("not_a_dict")
                continue

            kind       = str(item.get("kind") or "").strip()
            title      = str(item.get("title") or "").strip()
            body       = str(item.get("body") or "").strip()
            question   = str(item.get("question") or "").strip()
            confidence = str(item.get("confidence") or "").strip().lower()
            grounding  = item.get("grounding") or {}
            if not isinstance(grounding, dict):
                grounding = {}

            if not (title and body and question):
                reject("blank_required_field")
                continue
            # PC190-fix §2: allowlist em código, não só no prompt — mesmo que
            # o modelo emita um kind fora da fase 1 (a taxonomia inteira NÃO
            # está mais descrita no skill, mas um LLM pode divagar), nunca
            # passa. Ver melhorias/revisao-plano-provocacoes.md §2.
            if kind not in _ENABLED_KINDS:
                reject("kind_not_enabled")
                continue
            if confidence not in _ALLOWED_CONFIDENCE:
                reject("invalid_confidence")
                continue
            if _contains_blacklisted_tone(body, question):
                reject("blacklisted_tone")
                continue

            absence_check = grounding.get("absence_check") or {}
            if not isinstance(absence_check, dict):
                absence_check = {}
            terms = [str(t).strip() for t in (absence_check.get("terms") or []) if str(t).strip()]
            if not terms:
                reject("absence_check_missing")
                continue

            references: list[dict] = []

            if kind == "absence":
                # Span = transcrição inteira. Lastro é falso se QUALQUER termo
                # supostamente ausente na verdade ocorre em algum lugar.
                if any(_normalize(t) in transcript_norm for t in terms):
                    reject("term_present_in_span")
                    continue

            else:  # kind == "asymmetry"
                refs = grounding.get("references") or []
                if not isinstance(refs, list) or len(refs) < 2:
                    reject("insufficient_references")
                    continue
                refs = [r for r in refs if isinstance(r, dict)]
                excerpts = [str(r.get("excerpt") or "").strip() for r in refs[:2]]
                if len(excerpts) < 2 or not all(excerpts):
                    reject("insufficient_references")
                    continue
                # Cada excerto precisa ser citação literal (normalizada) da
                # transcrição — uma paráfrase é lastro inventado, não real.
                if not all(_normalize(ex) in transcript_norm for ex in excerpts):
                    reject("reference_not_found")
                    continue

                # A alegação real de asymmetry é "ninguém retomou o tema
                # ENTRE a objeção e o fechamento" — span derivado das duas
                # referências (não confiado a um span separado do LLM, que
                # poderia não corresponder às citações de fato fornecidas).
                span = _span_text(transcript, refs[0].get("timestamp", ""), refs[1].get("timestamp", ""))
                if span is None:
                    reject("span_unresolved")
                    continue
                if any(_normalize(t) in _normalize(span) for t in terms):
                    reject("term_present_in_span")
                    continue
                references = refs

            approved.append(ProvocationItem(
                kind=kind,
                title=title,
                body=body,
                question=question,
                grounding_type=str(grounding.get("type") or kind),
                references=references,
                absence_terms=terms,
                confidence=confidence,
            ))

        approved.sort(key=lambda p: _CONFIDENCE_RANK.get(p.confidence, 9))
        rejected_count = sum(reasons.values())
        return approved[:_MAX_PROVOCATIONS], rejected_count, dict(reasons)
