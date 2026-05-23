# modules/transcript_time_parser.py
# ─────────────────────────────────────────────────────────────────────────────
# Pure-Python parser for timestamped transcripts.
# Extracts meeting duration and per-speaker talk time from common ASR formats.
#
# Supported formats (auto-detected):
#   [00:01:23] João Silva: text
#   [00:01:23.456] João: text
#   00:01:23 - João: text
#   00:01:23  João: text
#   João (00:01:23): text
#   João [00:01:23]: text
#   João Silva - 00:01:23: text
#   00:01 João: text            (MM:SS only)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ── Timestamp helpers ─────────────────────────────────────────────────────────

def _ts_to_seconds(ts: str) -> int:
    """Convert HH:MM:SS or MM:SS (with optional fractional seconds) to integer seconds."""
    ts = ts.strip().split(".")[0]   # drop milliseconds
    parts = ts.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
    except ValueError:
        pass
    return 0


def _fmt_duration(seconds: int) -> str:
    """Format seconds as Xh Ym or Ym Zs for display."""
    if seconds <= 0:
        return "—"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}h {m:02d}min"
    if m > 0:
        return f"{m}min {s:02d}s"
    return f"{s}s"


def _fmt_speaker_time(seconds: int) -> str:
    """Format seconds as Xm Ys for speaker time display."""
    if seconds <= 0:
        return "0s"
    m = seconds // 60
    s = seconds % 60
    if m > 0:
        return f"{m}min {s:02d}s"
    return f"{s}s"


# ── Regex patterns (ordered by specificity) ───────────────────────────────────

# Group 1 = timestamp, Group 2 = speaker name
_PATTERNS: list[tuple[str, re.Pattern]] = [
    # [00:01:23] Speaker:   or   [00:01:23.456] Speaker:
    ("bracket_ts_speaker",
     re.compile(r"^\[(\d{1,2}:\d{2}:\d{2}(?:\.\d+)?)\]\s*([^:\[\]\n]{2,40}?)\s*:", re.MULTILINE)),

    # 00:01:23 - Speaker:  or  00:01:23 – Speaker:
    ("ts_dash_speaker",
     re.compile(r"^(\d{1,2}:\d{2}:\d{2})\s*[-–]\s*([^:\n]{2,40}?)\s*:", re.MULTILINE)),

    # Speaker (00:01:23):  or  Speaker (00:01):
    ("speaker_paren_ts",
     re.compile(r"^([^:\(\)\[\]\n]{2,40}?)\s*\((\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?)\)\s*:", re.MULTILINE)),

    # Speaker [00:01:23]:  or  Speaker [00:01]:
    ("speaker_bracket_ts",
     re.compile(r"^([^:\(\)\[\]\n]{2,40}?)\s*\[(\d{1,2}:\d{2}(?::\d{2})?)\]\s*:", re.MULTILINE)),

    # 00:01:23  Speaker:   (timestamp then space then speaker)
    ("ts_space_speaker",
     re.compile(r"^(\d{1,2}:\d{2}:\d{2})\s{1,5}([^:\n]{2,40}?)\s*:", re.MULTILINE)),

    # 00:01 Speaker:  (MM:SS only)
    ("mmss_space_speaker",
     re.compile(r"^(\d{1,2}:\d{2})\s{1,5}([^:\n]{2,40}?)\s*:", re.MULTILINE)),
]

_TS_FIRST_PATTERNS = {"bracket_ts_speaker", "ts_dash_speaker", "ts_space_speaker", "mmss_space_speaker"}


# ── Main parser ───────────────────────────────────────────────────────────────

@dataclass
class MeetingTimings:
    """Result of parsing a transcript for time information."""
    has_timestamps: bool = False
    format_detected: str = ""
    duration_seconds: Optional[int] = None     # total meeting length
    speaker_times: dict = field(default_factory=dict)   # name → seconds of talk time
    speaker_turns: dict = field(default_factory=dict)   # name → number of turns


def parse_transcript_timings(transcript: str) -> MeetingTimings:
    """
    Parse a transcript and extract meeting duration + per-speaker talk time.

    Returns a MeetingTimings with has_timestamps=False when no timestamps
    are detected (caller should use word-count estimation instead).
    """
    result = MeetingTimings()
    if not transcript or len(transcript) < 20:
        return result

    # Try each pattern, pick the one with the most matches
    best_fmt: str = ""
    best_turns: list[tuple[int, str]] = []   # (seconds, speaker_name)

    for fmt_name, pattern in _PATTERNS:
        matches = pattern.findall(transcript)
        if len(matches) < 2:
            continue

        turns: list[tuple[int, str]] = []
        for m in matches:
            if fmt_name in _TS_FIRST_PATTERNS:
                ts_str, speaker = m[0], m[1]
            else:
                speaker, ts_str = m[0], m[1]
            speaker = _normalize_speaker(speaker)
            if not speaker:
                continue
            turns.append((_ts_to_seconds(ts_str), speaker))

        if len(turns) > len(best_turns):
            best_turns = turns
            best_fmt = fmt_name

    if len(best_turns) < 2:
        return result

    # Sort by timestamp (some transcripts may be out of order)
    best_turns.sort(key=lambda t: t[0])

    result.has_timestamps = True
    result.format_detected = best_fmt

    # Duration = last turn start − first turn start
    first_ts = best_turns[0][0]
    last_ts  = best_turns[-1][0]
    result.duration_seconds = max(0, last_ts - first_ts)

    # Per-speaker talk time: each turn's duration = next_turn_start − this_turn_start
    # The last turn's duration is estimated as the median turn length
    speaker_times: dict[str, int] = {}
    speaker_turns: dict[str, int] = {}

    for i, (ts, spk) in enumerate(best_turns):
        speaker_turns[spk] = speaker_turns.get(spk, 0) + 1
        if i < len(best_turns) - 1:
            turn_dur = best_turns[i + 1][0] - ts
            speaker_times[spk] = speaker_times.get(spk, 0) + max(0, turn_dur)

    # Estimate last turn duration as median of all computed durations
    if len(best_turns) > 1:
        all_durs = [
            best_turns[i + 1][0] - best_turns[i][0]
            for i in range(len(best_turns) - 1)
            if best_turns[i + 1][0] > best_turns[i][0]
        ]
        if all_durs:
            all_durs.sort()
            median_dur = all_durs[len(all_durs) // 2]
            last_spk = best_turns[-1][1]
            speaker_times[last_spk] = speaker_times.get(last_spk, 0) + median_dur
            result.duration_seconds = (result.duration_seconds or 0) + median_dur

    result.speaker_times = speaker_times
    result.speaker_turns = speaker_turns
    return result


def estimate_timings_from_wordcount(transcript: str) -> MeetingTimings:
    """
    Estimate per-speaker talk time from word count when no timestamps exist.
    Uses 130 words/minute (average Portuguese speech rate).
    Detects `Speaker: text` lines to count words per speaker.
    """
    result = MeetingTimings()
    WORDS_PER_MIN = 130
    SECONDS_PER_WORD = 60.0 / WORDS_PER_MIN

    speaker_words: dict[str, int] = {}
    speaker_turns: dict[str, int] = {}
    current_speaker: Optional[str] = None
    current_words = 0

    for line in transcript.splitlines():
        m = re.match(r"^([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .'-]{1,39}?)\s*:\s*(.+)$", line.strip())
        if m:
            if current_speaker:
                speaker_words[current_speaker] = speaker_words.get(current_speaker, 0) + current_words
            current_speaker = _normalize_speaker(m.group(1))
            text = m.group(2)
            current_words = len(text.split())
            if current_speaker:
                speaker_turns[current_speaker] = speaker_turns.get(current_speaker, 0) + 1
        elif current_speaker and line.strip():
            current_words += len(line.split())

    if current_speaker:
        speaker_words[current_speaker] = speaker_words.get(current_speaker, 0) + current_words

    if not speaker_words:
        return result

    result.has_timestamps = False
    result.format_detected = "word_count_estimate"
    result.speaker_times = {
        spk: int(words * SECONDS_PER_WORD)
        for spk, words in speaker_words.items()
    }
    result.speaker_turns = speaker_turns
    total_seconds = sum(result.speaker_times.values())
    result.duration_seconds = total_seconds if total_seconds > 0 else None
    return result


# ── Display helpers ───────────────────────────────────────────────────────────

def format_duration(timings: MeetingTimings) -> str:
    """Return human-readable duration string."""
    if timings.duration_seconds is None:
        return "—"
    return _fmt_duration(timings.duration_seconds)


def format_speaker_table(timings: MeetingTimings) -> list[dict]:
    """
    Return list of dicts suitable for st.dataframe():
      [{"Participante": ..., "Tempo de fala": ..., "Turnos": ..., "%": ...}, ...]
    Sorted by talk time descending.
    """
    total = sum(timings.speaker_times.values()) or 1
    rows = []
    for spk, secs in sorted(timings.speaker_times.items(), key=lambda x: -x[1]):
        rows.append({
            "Participante": spk,
            "Tempo de fala": _fmt_speaker_time(secs),
            "Turnos": timings.speaker_turns.get(spk, 0),
            "%": f"{secs / total * 100:.0f}%",
        })
    return rows


# ── Internal helpers ──────────────────────────────────────────────────────────

_NOISE_NAMES = frozenset([
    "ok", "sim", "não", "yes", "no", "eh", "ah", "uh", "mm",
    "obrigado", "obrigada", "certo", "então", "mas", "e", "a", "o",
])


def _normalize_speaker(name: str) -> str:
    """Strip punctuation/whitespace and filter out obvious non-name matches."""
    name = name.strip(" \t\r\n-–—:().[]")
    name = re.sub(r"\s{2,}", " ", name)
    if not name or len(name) < 2 or name.lower() in _NOISE_NAMES:
        return ""
    # Reject strings that look like timestamps or pure numbers
    if re.fullmatch(r"[\d:.\-\s]+", name):
        return ""
    return name
