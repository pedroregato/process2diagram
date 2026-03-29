# modules/transcript_preprocessor.py
# ─────────────────────────────────────────────────────────────────────────────
# Rule-based preprocessor for Microsoft Teams transcript format.
# No LLM required — pure Python/stdlib.
#
# Input format:
#   Transcrição
#   6 de março de 2026, 05:05PM
#
#   Speaker Full Name   0:03
#   Content of what they said.
#
# Public API:
#   result = preprocess(raw_text: str) -> PreprocessingResult
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class PreprocessingResult:
    clean_text: str
    fillers_removed: int = 0
    artifact_turns: int = 0
    repetitions_collapsed: int = 0
    metadata_issues: list[str] = field(default_factory=list)


# ── Internal dataclass for parsed turns ──────────────────────────────────────

@dataclass
class _Turn:
    speaker: str
    timestamp: str
    lines: list[str]


# ── Filler patterns ───────────────────────────────────────────────────────────

# Vocal sounds and PT-BR fillers as standalone tokens
_FILLER_STANDALONE = re.compile(
    r"(?<!\w)"
    r"(Hhh|[Mm]hm|[Aa]ham|[Hh]mm+|[Hh]m+|[Aa]h+|[Oo]h+|H)"
    r"(?!\w)",
    re.IGNORECASE,
)

# PT-BR spoken fillers (word-boundary aware)
_FILLER_PTBR = re.compile(
    r"\b(ééé+|ãã+|éh|ahm|hum|né|assim|tipo|tá|tô|aí)\b",
    re.IGNORECASE,
)

# Standalone hesitation markers: "é..." or "é," at the start or after whitespace
_FILLER_HESITATION = re.compile(
    r"(?:^|\s)(é\.\.\.+|é,)\s*",
    re.IGNORECASE,
)

# English fillers
_FILLER_EN = re.compile(
    r"\b(uh+|um+|you know|like|so|well)\b",
    re.IGNORECASE,
)

# Single-letter tokens that are clearly noise (isolated H)
_SINGLE_LETTER_NOISE = re.compile(r"(?<!\w)[Hh](?!\w)")


# ── Repetition collapse ───────────────────────────────────────────────────────

def _collapse_repetitions(text: str) -> tuple[str, int]:
    """
    Collapse 3+ consecutive repetitions of the same word or short phrase.
    Returns (modified_text, count_of_collapses).
    """
    count = 0

    # Multi-word sequence repetition (2–4 words, repeated 3+ times)
    # e.g. "Santos de Amaral Amaral Amaral Amaral" — collapse the repeated part
    def _replace_multi(m: re.Match) -> str:
        nonlocal count
        count += 1
        return f"[rep: {m.group(1)}]"

    # Single-word repetition: word repeated 3+ times consecutively
    # Captures the word and all its repetitions
    single_pat = re.compile(
        r"\b([A-Za-zÀ-ÿ]+)\b(?:\s+\1\b){2,}",
        re.IGNORECASE,
    )

    def _replace_single(m: re.Match) -> str:
        nonlocal count
        count += 1
        return f"[rep: {m.group(1)}]"

    text = single_pat.sub(_replace_single, text)

    # Two-word phrase repeated 3+ times: "word1 word2" repeated
    two_word_pat = re.compile(
        r"\b([A-Za-zÀ-ÿ]+\s+[A-Za-zÀ-ÿ]+)\b(?:\s+\1\b){2,}",
        re.IGNORECASE,
    )
    text = two_word_pat.sub(_replace_multi, text)

    return text, count


# ── Business vocabulary (turns containing these are NOT artifacts) ────────────

_BUSINESS_VOCAB = {
    "processo", "sistema", "cadastro", "validação", "validar", "usuário",
    "escola", "organograma", "estrutura", "unidade", "departamento",
    "aprovação", "aprovar", "rejeitar", "enviar", "receber", "criar",
    "dados", "formulário", "campo", "registro", "relatório", "documento",
    "fluxo", "etapa", "passo", "atividade", "tarefa", "responsável",
    "prazo", "objetivo", "meta", "requisito", "funcional", "regra",
    "ok", "sim", "não", "isso", "certo", "entendido", "correto",
    "então", "depois", "sequência", "primeiro", "segundo", "terceiro",
}


# ── Surname / artifact detection ──────────────────────────────────────────────

def _is_artifact_turn(cleaned_content: str, known_speakers: list[str]) -> bool:
    """
    Detect turns that are likely ASR noise after cleaning.
    Returns True if the turn is likely an artifact.
    """
    # Strip trailing punctuation for analysis
    content = cleaned_content.strip().rstrip(".,!?;:")
    words = content.split()

    if not words:
        return True  # empty after cleaning

    if len(words) > 3:
        return False  # multi-word non-trivial content is kept as-is

    # Check if all words are in business vocabulary
    lower_words = [w.lower() for w in words]
    if any(w in _BUSINESS_VOCAB for w in lower_words):
        return False

    # Check if any word is a substring of a known speaker name
    for word in words:
        word_lower = word.lower()
        for speaker in known_speakers:
            if word_lower in speaker.lower() and len(word_lower) > 2:
                return True  # looks like a surname artifact

    # Single-word turns that are capitalized (typical ASR surname fragments)
    if len(words) == 1:
        w = words[0].rstrip(".,!?")
        # Capitalized word not in business vocab → likely artifact
        if w and w[0].isupper() and w.lower() not in _BUSINESS_VOCAB:
            return True

    # Two-word turns: both capitalized proper nouns not in vocab
    if len(words) == 2:
        both_cap = all(w and w[0].isupper() for w in words)
        both_unknown = all(w.lower().rstrip(".,!?") not in _BUSINESS_VOCAB for w in words)
        if both_cap and both_unknown:
            return True

    return False


# ── Metadata cleaning ─────────────────────────────────────────────────────────

_INVALID_DATE_PAT = re.compile(
    r"Invalid\s+Date[\s,]*InvalidDate|Invalid\s+Date",
    re.IGNORECASE,
)

_MONTHS_PT = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8,
    "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}

_VALID_DATE_PAT = re.compile(
    r"\d{1,2}\s+de\s+(?:" + "|".join(_MONTHS_PT.keys()) + r")\s+de\s+\d{4}",
    re.IGNORECASE,
)


def _clean_metadata_line(line: str) -> tuple[str, Optional[str]]:
    """
    Clean a metadata/header line. Returns (cleaned_line, issue_or_None).
    """
    if _INVALID_DATE_PAT.search(line):
        return "[Data não registrada]", "Data inválida no cabeçalho"
    return line, None


# ── Punctuation normalization ─────────────────────────────────────────────────

def _normalize_punctuation(text: str) -> str:
    """
    - Remove duplicate/orphaned punctuation left by filler removal
    - Collapse ". ." → ".", ".. " → ". ", etc.
    """
    # Orphaned period after filler removal: ". ." or ".  ."
    text = re.sub(r"\.\s+\.", ".", text)
    # Consecutive periods (not ellipsis)
    text = re.sub(r"\.{2,}", ".", text)
    # Orphaned leading/trailing punctuation inside a sentence fragment
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)
    # Duplicate commas, exclamation marks, question marks
    text = re.sub(r",{2,}", ",", text)
    text = re.sub(r"!{2,}", "!", text)
    text = re.sub(r"\?{2,}", "?", text)
    return text


# ── Teams transcript parser ───────────────────────────────────────────────────

# Speaker line pattern: "Name Name   0:03" or "Name   00:03"
_SPEAKER_LINE_PAT = re.compile(
    r"^(.+?)\s{2,}(\d{1,2}:\d{2}(?::\d{2})?)\s*$"
)

# Header line: title line (e.g. "Transcrição") and date line
_HEADER_DATE_PAT = re.compile(
    r"^\d{1,2}\s+de\s+\w+\s+de\s+\d{4}",
    re.IGNORECASE,
)


def _parse_teams_transcript(raw: str) -> tuple[list[str], list[_Turn], list[str]]:
    """
    Parse a Teams transcript into (header_lines, turns, metadata_issues).
    Falls back gracefully for non-Teams formats.
    """
    lines = raw.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    header_lines: list[str] = []
    turns: list[_Turn] = []
    metadata_issues: list[str] = []

    i = 0
    n = len(lines)

    # Collect header (lines before first speaker turn)
    # Header = title line + date line (first 1-3 non-empty lines)
    header_collected = False
    while i < n and not header_collected:
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        # Check if this line matches a speaker pattern
        if _SPEAKER_LINE_PAT.match(line):
            header_collected = True
            break
        # Otherwise it's a header line
        cleaned_hdr, issue = _clean_metadata_line(line)
        header_lines.append(cleaned_hdr)
        if issue:
            metadata_issues.append(issue)
        i += 1

    # Parse speaker turns
    current_speaker: Optional[str] = None
    current_timestamp: str = ""
    current_lines: list[str] = []

    while i < n:
        line = lines[i]
        stripped = line.strip()
        i += 1

        if not stripped:
            continue

        m = _SPEAKER_LINE_PAT.match(stripped)
        if m:
            # Save previous turn
            if current_speaker is not None and current_lines:
                turns.append(_Turn(
                    speaker=current_speaker,
                    timestamp=current_timestamp,
                    lines=current_lines,
                ))
            current_speaker = m.group(1).strip()
            current_timestamp = m.group(2).strip()
            current_lines = []
        else:
            if current_speaker is not None:
                current_lines.append(stripped)
            else:
                # Content before any speaker line — treat as header overflow
                cleaned_hdr, issue = _clean_metadata_line(stripped)
                header_lines.append(cleaned_hdr)
                if issue:
                    metadata_issues.append(issue)

    # Flush last turn
    if current_speaker is not None and current_lines:
        turns.append(_Turn(
            speaker=current_speaker,
            timestamp=current_timestamp,
            lines=current_lines,
        ))

    return header_lines, turns, metadata_issues


# ── Filler removal ────────────────────────────────────────────────────────────

def _remove_fillers(text: str) -> tuple[str, int]:
    """Remove filler words/sounds from text. Returns (cleaned, count_removed)."""
    count = 0

    def _count_sub(pat: re.Pattern, repl: str, t: str) -> tuple[str, int]:
        matches = pat.findall(t)
        c = len(matches)
        return pat.sub(repl, t), c

    text, c = _count_sub(_FILLER_HESITATION, " ", text)
    count += c

    text, c = _count_sub(_FILLER_STANDALONE, "", text)
    count += c

    text, c = _count_sub(_FILLER_PTBR, "", text)
    count += c

    text, c = _count_sub(_FILLER_EN, "", text)
    count += c

    # Clean up extra whitespace left by removals
    text = re.sub(r"\s{2,}", " ", text).strip()

    return text, count


# ── Clean a single turn's content ─────────────────────────────────────────────

def _clean_turn_content(lines: list[str]) -> tuple[str, int, int]:
    """
    Clean the lines of a single turn.
    Returns (cleaned_text, fillers_removed, repetitions_collapsed).
    """
    joined = " ".join(lines)

    # Remove fillers
    cleaned, fillers = _remove_fillers(joined)

    # Collapse repetitions
    cleaned, reps = _collapse_repetitions(cleaned)

    # Normalize punctuation
    cleaned = _normalize_punctuation(cleaned)

    # Final whitespace cleanup
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

    return cleaned, fillers, reps


# ── Main public function ──────────────────────────────────────────────────────

def preprocess(raw_text: str) -> PreprocessingResult:
    """
    Preprocess a Microsoft Teams transcript (or any speaker-labelled transcript).

    Steps:
      1. Parse structure into header + turns
      2. Clean fillers from each turn
      3. Collapse repetitions in each turn
      4. Detect artifact turns and mark with [? ...]
      5. Rebuild clean transcript with speaker labels preserved

    Returns:
        PreprocessingResult with clean_text and statistics.
    """
    total_fillers = 0
    total_artifacts = 0
    total_reps = 0
    metadata_issues: list[str] = []

    # Parse Teams format
    header_lines, turns, parse_issues = _parse_teams_transcript(raw_text)
    metadata_issues.extend(parse_issues)

    # If no turns parsed, treat the whole text as unstructured and return lightly cleaned
    if not turns:
        cleaned_raw, fillers = _remove_fillers(raw_text)
        cleaned_raw, reps = _collapse_repetitions(cleaned_raw)
        cleaned_raw = _normalize_punctuation(cleaned_raw)
        cleaned_raw = re.sub(r"\s{2,}", " ", cleaned_raw)
        cleaned_raw = re.sub(r"\n{3,}", "\n\n", cleaned_raw).strip()
        return PreprocessingResult(
            clean_text=cleaned_raw,
            fillers_removed=fillers,
            artifact_turns=0,
            repetitions_collapsed=reps,
            metadata_issues=metadata_issues,
        )

    # Collect speaker names for artifact detection
    known_speakers = list({t.speaker for t in turns})

    # Process each turn
    output_parts: list[str] = []

    # Add header
    if header_lines:
        output_parts.append("\n".join(header_lines))
        output_parts.append("")

    rep_turns_count = 0

    for turn in turns:
        # Skip single-letter turns entirely
        raw_content = " ".join(turn.lines).strip()
        if len(raw_content) <= 1:
            total_artifacts += 1
            continue

        # Clean the content
        cleaned_content, fillers, reps = _clean_turn_content(turn.lines)
        total_fillers += fillers
        total_reps += reps

        if reps > 0:
            rep_turns_count += 1

        # Skip if completely empty after cleaning
        if not cleaned_content:
            total_artifacts += 1
            continue

        # Detect artifact turns
        if _is_artifact_turn(cleaned_content, known_speakers):
            # Mark with [? ...] but keep in output
            cleaned_content = f"[? {cleaned_content.rstrip('.')}]"
            total_artifacts += 1

        # Format: "Speaker Name   timestamp\nContent"
        speaker_label = f"{turn.speaker}   {turn.timestamp}"
        output_parts.append(speaker_label)
        output_parts.append(cleaned_content)
        output_parts.append("")

    # Report repetition collapses in metadata_issues if any
    if rep_turns_count > 0:
        metadata_issues.append(
            f"{rep_turns_count} turn(s) com repetição detectada e colapsada"
        )

    if total_artifacts > 0:
        metadata_issues.append(
            f"{total_artifacts} turno(s) marcado(s) como artefato ASR [?]"
        )

    clean_text = "\n".join(output_parts).strip()

    return PreprocessingResult(
        clean_text=clean_text,
        fillers_removed=total_fillers,
        artifact_turns=total_artifacts,
        repetitions_collapsed=total_reps,
        metadata_issues=metadata_issues,
    )
