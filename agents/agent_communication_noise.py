# agents/agent_communication_noise.py
# ─────────────────────────────────────────────────────────────────────────────
# AgentCommunicationNoise — detects ambiguities and communication gaps in
# meeting transcripts.
#
# Reads:  hub.transcript_clean, hub.nlp.actors, hub.minutes (participants,
#         decisions, open_questions for context)
# Writes: hub.communication_noise  (CommunicationNoiseModel)
#
# Optional — default OFF. Non-fatal: pipeline continues on failure.
#
# PC209 — turn-taking dynamics: dominância de fala, turno interrompido/
# retomado, tema repetido e sempre rejeitado, desqualificação de falante, e
# risco de atribuição de falante (dispositivo compartilhado). Dominância e
# risco de atribuição são 100% determinísticos (sem LLM, ver
# _compute_dominance/_compute_attribution_risks) — reaproveitam
# parse_turn_spans() de modules/transcript_time_parser.py. Os 3 gap_types
# novos (interrupted_resumed/repeated_unresolved_topic/speaker_disqualification)
# vêm do LLM mas passam por um validador determinístico antes de aprovação —
# mesmo "coração da proposta" de agent_provocations.py: citação verbatim
# contra a transcrição real, nunca aceita por omissão.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import logging
import re
from collections import Counter

from agents.base_agent import BaseAgent
from core.knowledge_hub import (
    KnowledgeHub,
    CommunicationNoiseModel,
    AmbiguityItem,
    CommunicationGap,
    SpeakerDominance,
    SpeakerAttributionRisk,
)
from core.output_schemas import CommunicationNoiseOutputSchema
from modules.transcript_time_parser import parse_turn_spans, _ts_to_seconds

_logger = logging.getLogger(__name__)

_STRICT_GAP_KINDS = {"interrupted_resumed", "repeated_unresolved_topic", "speaker_disqualification"}
_ALLOWED_CONFIDENCE = {"high", "medium"}

_DOMINANCE_THRESHOLD_PCT = 65.0
_MIN_SPEAKERS_FOR_DOMINANCE = 2
_MIN_TURNS_FOR_DOMINANCE = 4

_TIMESTAMP_RE = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")

# Strips the ASR-cleanup bracket syntax (`[? ...]`, `[rep: ...]`) added by
# modules/transcript_preprocessor.py, keeping the words inside for word-count
# purposes — those markers flag confidence, they don't delete real speech.
_ASR_MARKER_RE = re.compile(r"\[\?\s*|\[rep:\s*|\]")

# Vocative address near a first name — "obrigado, Deise", "tchau Fátima" — used
# as the required evidence for a SpeakerAttributionRisk flag (never flag on
# name-in-participant-list alone, that would be an unfounded claim).
_VOCATIVE_RE_TEMPLATE = (
    r"[^.\n]{{0,40}}\b(?:obrigad[oa]s?|valeu|tchau|at[ée] logo|bom trabalho|"
    r"bom (?:final de semana|descanso))\b[^.\n]{{0,12}}\b{name}\b[^.\n]{{0,20}}"
)


def _normalize(text: str) -> str:
    """Lowercase + colapsa espaços — correspondência literal tolerante a formatação."""
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def _looks_like_timestamp(ts: str) -> bool:
    return bool(_TIMESTAMP_RE.match((ts or "").strip()))


def _strip_asr_markers(text: str) -> str:
    return _ASR_MARKER_RE.sub("", text or "")


# ── Dominância de fala (determinístico, sem LLM) ────────────────────────────

def _compute_dominance(transcript: str) -> list[SpeakerDominance]:
    """% de palavras/turnos por falante — puro código, via parse_turn_spans()."""
    spans = parse_turn_spans(transcript)
    if len(spans) < _MIN_TURNS_FOR_DOMINANCE:
        return []

    word_counts: Counter = Counter()
    turn_counts: Counter = Counter()
    for sp in spans:
        word_counts[sp.speaker] += len(_strip_asr_markers(sp.text).split())
        turn_counts[sp.speaker] += 1

    speakers = set(turn_counts)
    if len(speakers) < _MIN_SPEAKERS_FOR_DOMINANCE:
        return []

    total_words = sum(word_counts.values()) or 1
    total_turns = sum(turn_counts.values()) or 1

    result = []
    for spk in speakers:
        word_pct = 100.0 * word_counts.get(spk, 0) / total_words
        turn_pct = 100.0 * turn_counts[spk] / total_turns
        result.append(SpeakerDominance(
            speaker=spk,
            turns=turn_counts[spk],
            word_share_pct=round(word_pct, 1),
            turn_share_pct=round(turn_pct, 1),
            dominant=word_pct >= _DOMINANCE_THRESHOLD_PCT,
        ))
    result.sort(key=lambda d: -d.word_share_pct)
    return result


# ── Risco de atribuição de falante (determinístico, sem LLM) ────────────────

def _find_vocative_quote(transcript: str, first_name: str) -> str:
    if not first_name:
        return ""
    pattern = re.compile(_VOCATIVE_RE_TEMPLATE.format(name=re.escape(first_name)), re.IGNORECASE)
    m = pattern.search(transcript)
    return m.group(0).strip() if m else ""


def _compute_attribution_risks(
    transcript: str, participants: list[str]
) -> list[SpeakerAttributionRisk]:
    """
    Flags a named participant who never appears as the speaker of their own
    turn — possible sign of merged speech (shared device/microphone). Never
    flags without a verbatim vocative quote as evidence (e.g. "obrigado,
    Deise") — a name simply being in the participant list is not evidence.
    """
    spans = parse_turn_spans(transcript)
    if not spans or not participants:
        return []

    speaker_labels_norm = {_normalize(sp.speaker) for sp in spans}
    turn_counts = Counter(sp.speaker for sp in spans)
    top_speaker = turn_counts.most_common(1)[0][0] if turn_counts else ""

    risks: list[SpeakerAttributionRisk] = []
    seen: set[str] = set()
    for name in participants:
        norm = _normalize(name)
        if not norm or norm in seen:
            continue
        seen.add(norm)

        # Already has their own turns — no attribution risk.
        if any(norm in label or label in norm for label in speaker_labels_norm):
            continue

        first_name = name.strip().split()[0] if name.strip() else ""
        quote = _find_vocative_quote(transcript, first_name)
        if not quote:
            continue

        risks.append(SpeakerAttributionRisk(
            mentioned_name=name,
            mentioned_context=quote,
            possibly_merged_into=top_speaker,
        ))
    return risks


# ── Validador determinístico dos 3 gap_types evidence-backed ────────────────
# Mesmo padrão de agent_provocations.py::_validate_and_rank — citação verbatim
# contra a transcrição real, timestamp correspondente a um turno de fato
# existente do falante alegado. Nunca aprova por omissão.

def _validate_and_rank_strict_gaps(
    raw_gaps: list[dict], transcript: str
) -> tuple[list[CommunicationGap], int, dict]:
    transcript_norm = _normalize(transcript)
    spans = parse_turn_spans(transcript)

    seconds_by_speaker: dict[str, set[int]] = {}
    all_speakers_norm: set[str] = set()
    for sp in spans:
        seconds_by_speaker.setdefault(sp.speaker, set()).add(sp.seconds)
        all_speakers_norm.add(_normalize(sp.speaker))

    def _speaker_has_turn_at(speaker: str, ts: str) -> bool:
        if not _looks_like_timestamp(ts):
            return False
        sec = _ts_to_seconds(ts)
        secs = seconds_by_speaker.get(speaker)
        if secs is None:
            secs = next(
                (s for label, s in seconds_by_speaker.items() if _normalize(label) == _normalize(speaker)),
                None,
            )
        return secs is not None and sec in secs

    approved: list[CommunicationGap] = []
    reasons: Counter = Counter()

    def reject(reason: str) -> None:
        reasons[reason] += 1

    for item in raw_gaps:
        if not isinstance(item, dict):
            reject("not_a_dict")
            continue

        kind = str(item.get("gap_type") or "").strip()
        if kind not in _STRICT_GAP_KINDS:
            reject("kind_not_enabled")
            continue

        description = str(item.get("description") or "").strip()
        confidence  = str(item.get("confidence") or "").strip().lower()
        refs_raw    = item.get("references") or []

        if not description:
            reject("blank_description")
            continue
        if confidence not in _ALLOWED_CONFIDENCE:
            reject("invalid_confidence")
            continue
        if not isinstance(refs_raw, list) or len(refs_raw) < 2:
            reject("insufficient_references")
            continue

        refs = [r for r in refs_raw if isinstance(r, dict)][:3]
        excerpts   = [str(r.get("excerpt") or "").strip() for r in refs]
        timestamps = [str(r.get("timestamp") or "").strip() for r in refs]
        speakers   = [str(r.get("speaker") or "").strip() for r in refs]

        if len(refs) < 2 or not all(excerpts[:2]):
            reject("insufficient_references")
            continue
        if not all(_normalize(ex) in transcript_norm for ex in excerpts if ex):
            reject("reference_not_found")
            continue
        if not all(_speaker_has_turn_at(spk, ts) for spk, ts in zip(speakers, timestamps)):
            reject("reference_not_found")
            continue

        target_speaker = ""

        if kind == "interrupted_resumed":
            if _normalize(speakers[0]) != _normalize(speakers[1]):
                reject("interrupted_resumed_speaker_mismatch")
                continue
            if _ts_to_seconds(timestamps[1]) <= _ts_to_seconds(timestamps[0]):
                reject("interrupted_resumed_out_of_order")
                continue
            target_speaker = speakers[0]

        elif kind == "repeated_unresolved_topic":
            secs = [_ts_to_seconds(t) for t in timestamps]
            if secs != sorted(secs) or len(set(secs)) < len(secs):
                reject("repeated_topic_out_of_order")
                continue

        else:  # speaker_disqualification
            target_speaker = str(item.get("target_speaker") or "").strip()
            if not target_speaker:
                reject("target_speaker_missing")
                continue
            if _normalize(target_speaker) == _normalize(speakers[0]):
                reject("disqualification_self_target")
                continue
            target_norm = _normalize(target_speaker)
            if not any(target_norm in lbl or lbl in target_norm for lbl in all_speakers_norm):
                reject("disqualification_target_unknown")
                continue

        approved.append(CommunicationGap(
            gap_type=kind,
            description=description,
            raised_by=str(item.get("raised_by") or speakers[0] or "").strip(),
            topic=str(item.get("topic") or "").strip(),
            evidence_quote=excerpts[0],
            impact=str(item.get("impact") or "").strip(),
            recommendation=str(item.get("recommendation") or "").strip(),
            target_speaker=target_speaker,
            references=refs,
            confidence=confidence,
        ))

    approved.sort(key=lambda g: 0 if g.confidence == "high" else 1)
    return approved, sum(reasons.values()), dict(reasons)


class AgentCommunicationNoise(BaseAgent):

    name                 = "communication_noise"
    skill_path           = "skills/skill_communication_noise.md"
    required_hub_fields  = ["transcript_clean"]
    output_schema        = CommunicationNoiseOutputSchema

    # ── Prompt ────────────────────────────────────────────────────────────────

    def build_prompt(
        self, hub: KnowledgeHub, output_language: str = "Auto-detect"
    ) -> tuple[str, str]:
        lang = self._language_instruction(output_language)
        system = self._skill.replace("{output_language}", lang)

        if getattr(hub, "context_skill", "").strip():
            system += f"\n\n## Conhecimento do Contexto\n\n{hub.context_skill.strip()}"

        # Build context block from prior agents
        context_lines: list[str] = []

        actors = getattr(hub.nlp, "actors", [])
        if actors:
            context_lines.append(f"Participants identified: {', '.join(actors)}")

        if hub.minutes.ready:
            if hub.minutes.participants:
                context_lines.append(
                    f"Participants from minutes: {', '.join(hub.minutes.participants)}"
                )
            if hub.minutes.decisions:
                decisions_txt = "; ".join(hub.minutes.decisions[:10])
                context_lines.append(f"Decisions recorded: {decisions_txt}")
            if hub.minutes.open_questions:
                oq_txt = "; ".join(hub.minutes.open_questions[:5])
                context_lines.append(
                    f"Open questions already flagged in minutes: {oq_txt}"
                )

        context_block = ""
        if context_lines:
            context_block = "\n\n## Meeting Context\n\n" + "\n".join(
                f"- {line}" for line in context_lines
            )

        user = (
            f"Analyse the transcript below for communication noise "
            f"(ambiguities, gaps, and turn-taking dynamics).{context_block}\n\n"
            f"## Transcript\n\n{hub.transcript_clean}"
        )
        return system, user

    # ── Run ───────────────────────────────────────────────────────────────────

    def run(
        self, hub: KnowledgeHub, output_language: str = "Auto-detect"
    ) -> KnowledgeHub:
        system, user = self.build_prompt(hub, output_language)
        data = self._call_with_retry(system, user, hub)

        transcript = hub.transcript_clean or ""
        raw_gaps = (data or {}).get("gaps") or []
        legacy_raw = [
            g for g in raw_gaps
            if isinstance(g, dict) and str(g.get("gap_type") or "") not in _STRICT_GAP_KINDS
        ]
        strict_raw = [
            g for g in raw_gaps
            if isinstance(g, dict) and str(g.get("gap_type") or "") in _STRICT_GAP_KINDS
        ]

        model = self._build_model({**(data or {}), "gaps": legacy_raw})

        strict_gaps, rejected_count, rejected_reasons = _validate_and_rank_strict_gaps(
            strict_raw, transcript
        )
        model.gaps = model.gaps + strict_gaps
        model.rejected_count = rejected_count
        model.rejected_reasons = rejected_reasons
        if strict_raw:
            _logger.info(
                "AgentCommunicationNoise: %d gap(s) evidence-backed gerado(s), %d aprovado(s), "
                "%d reprovado(s) %s",
                len(strict_raw), len(strict_gaps), rejected_count, rejected_reasons or "",
            )

        model.dominance = _compute_dominance(transcript)
        model.attribution_risks = _compute_attribution_risks(
            transcript, list(getattr(hub.minutes, "participants", []) or [])
        )

        model.ready = True
        hub.communication_noise = model
        hub.mark_agent_run(self.name)
        hub.bump()
        return hub

    # ── Model building ────────────────────────────────────────────────────────

    @staticmethod
    def _build_model(data: dict) -> CommunicationNoiseModel:
        ambiguities = [
            AmbiguityItem(
                text=a.get("text", ""),
                ambiguity_type=a.get("ambiguity_type", "lexical"),
                speaker=a.get("speaker", ""),
                possible_interpretations=a.get("possible_interpretations", []),
                suggestion=a.get("suggestion", ""),
                confidence=float(a.get("confidence", 0.8)),
            )
            for a in data.get("ambiguities", [])
            if a.get("text")
        ]

        gaps = [
            CommunicationGap(
                gap_type=g.get("gap_type", "missing_info"),
                description=g.get("description", ""),
                raised_by=g.get("raised_by", "–"),
                topic=g.get("topic", ""),
                evidence_quote=g.get("evidence_quote", ""),
                impact=g.get("impact", ""),
                recommendation=g.get("recommendation", ""),
            )
            for g in data.get("gaps", [])
            if g.get("description")
        ]

        raw_score = data.get("noise_score", 0.0)
        try:
            noise_score = float(raw_score)
        except (TypeError, ValueError):
            noise_score = 0.0
        noise_score = max(0.0, min(10.0, noise_score))

        return CommunicationNoiseModel(
            ambiguities=ambiguities,
            gaps=gaps,
            noise_score=noise_score,
            summary=data.get("summary", ""),
        )
