# modules/meeting_roi_calculator.py
# ─────────────────────────────────────────────────────────────────────────────
# ROI-TR (Retorno sobre Investimento — Tempo de Reunião) calculator.
#
# Computes meeting quality indicators from existing Supabase data:
#   - ROI-TR index (0–10)
#   - TRC — Taxa de Retrabalho Conceitual (0–100 %)
#   - Decision count, action item completeness, requirements
#   - Estimated duration (word count ÷ 130 wpm) and cost
#
# Zero LLM calls — all computation is deterministic.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re
from dataclasses import dataclass


# ── Cyclical-discussion signal patterns ───────────────────────────────────────
# Detect Portuguese phrases that indicate a topic is being revisited without
# progress — proxy for the "spinning wheels" pattern.

_CYCLE_SIGNALS = [
    r'\bcomo (?:eu|já) (?:disse|falei|mencionei)\b',
    r'\bcomo já (?:falamos|discutimos|abordamos)\b',
    r'\bjá (?:mencionei|mencionamos|foi dito|abordamos|discutimos)\b',
    r'\bvoltando ao mesmo\b',
    r'\bpatinando\b',
    r'\bde novo\b',
    r'\bnovamente\b',
    r'\bmais uma vez\b',
    r'\brepetindo\b',
    r'\brepete\b',
    r'\bnão avança\b',
    r'\bnão progride\b',
]

_CYCLE_RE    = re.compile('|'.join(_CYCLE_SIGNALS), re.IGNORECASE)
_RESP_RE     = re.compile(
    r'\b[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÇÜ][a-záéíóúâêîôûãõàçü]+'
    r'(?:\s+[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÇÜ][a-záéíóúâêîôûãõàçü]+)*\b'
)
_DEADLINE_RE = re.compile(
    r'\b(?:\d{1,2}/\d{1,2}(?:/\d{2,4})?'
    r'|\d{4}-\d{2}-\d{2}'
    r'|prazo|deadline'
    r'|até\s+\w+)\b',
    re.IGNORECASE,
)


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class MeetingROIData:
    meeting_number: int
    title: str
    date: str
    meeting_id: str

    has_minutes: bool
    has_transcript: bool

    n_participants: int
    n_decisions: int
    n_actions_total: int
    n_actions_complete: int
    n_requirements: int

    word_count: int
    duration_min: float
    duration_hours: float

    cycle_signals: int
    trc: float          # 0–100

    dc_score: float     # composite Concrete Decisions
    cost_estimate: float
    roi_tr: float       # 0–10

    cost_per_hour: float

    # ── Derived labels ────────────────────────────────────────────────────────

    @property
    def roi_label(self) -> str:
        if self.roi_tr >= 7.5:
            return "🟢 Alto"
        if self.roi_tr >= 4.5:
            return "🟡 Médio"
        if self.roi_tr >= 2.0:
            return "🟠 Baixo"
        return "🔴 Crítico"

    @property
    def roi_color(self) -> str:
        if self.roi_tr >= 7.5:
            return "#22c55e"
        if self.roi_tr >= 4.5:
            return "#eab308"
        if self.roi_tr >= 2.0:
            return "#f97316"
        return "#ef4444"

    @property
    def trc_label(self) -> str:
        if self.trc > 40:
            return "🔴 Alto"
        if self.trc > 20:
            return "🟠 Médio"
        return "🟢 Baixo"

    @property
    def trc_color(self) -> str:
        if self.trc > 40:
            return "#ef4444"
        if self.trc > 20:
            return "#f97316"
        return "#22c55e"

    @property
    def short_title(self) -> str:
        return f"R{self.meeting_number}"

    @property
    def full_label(self) -> str:
        label = f"Reunião {self.meeting_number}"
        if self.title and self.title != label:
            label += f" — {self.title}"
        if self.date:
            label += f" ({self.date})"
        return label


# ── Internal helpers ──────────────────────────────────────────────────────────

def _section(minutes_md: str, *names: str) -> str:
    """Extract a named section from minutes markdown."""
    for name in names:
        m = re.search(
            rf'##\s*{re.escape(name)}\s*\n([\s\S]*?)(?=\n##|\Z)',
            minutes_md,
            re.IGNORECASE,
        )
        if m:
            return m.group(1).strip()
    return ""


def _compute_single(
    meeting: dict,
    req_by_mid: dict[str, int],
    cost_per_hour: float,
) -> MeetingROIData:
    """Compute ROI-TR metrics for a single meeting row from Supabase."""
    n          = meeting.get("meeting_number") or 0
    title      = meeting.get("title") or f"Reunião {n}"
    date       = meeting.get("meeting_date") or ""
    mid        = meeting.get("id") or ""
    minutes_md = meeting.get("minutes_md") or ""
    transcript = meeting.get("transcript_clean") or meeting.get("transcript_raw") or ""

    # ── Participants ──────────────────────────────────────────────────────────
    part_text  = _section(minutes_md, "Participantes")
    part_lines = [l for l in part_text.splitlines() if l.strip()]
    n_part     = max(1, len(part_lines))

    # ── Decisions ────────────────────────────────────────────────────────────
    dec_text  = _section(minutes_md, "Decisões", "Decisions")
    dec_lines = [
        l for l in dec_text.splitlines()
        if l.strip() and l.strip()[0] in "-•*|123456789"
    ]
    n_dec = len(dec_lines)

    # ── Action items ─────────────────────────────────────────────────────────
    act_text    = _section(minutes_md, "Itens de Ação", "Action Items", "Ações")
    act_lines   = [l for l in act_text.splitlines() if l.strip()]
    n_act_total = len([
        l for l in act_lines
        if l.strip()[0:1] in "-•*|" or l.strip()[0:1].isdigit()
    ])
    n_act_done  = sum(
        1 for l in act_lines
        if bool(_DEADLINE_RE.search(l)) and bool(_RESP_RE.search(l))
    )

    # ── Requirements ─────────────────────────────────────────────────────────
    n_reqs = req_by_mid.get(mid, 0)

    # ── Transcript word count and duration ───────────────────────────────────
    words     = len(transcript.split()) if transcript else 0
    dur_min   = words / 130.0 if words else 0.0
    dur_h     = dur_min / 60.0

    # ── TRC proxy ────────────────────────────────────────────────────────────
    n_cycle = len(_CYCLE_RE.findall(transcript)) if transcript else 0
    trc     = min(100.0, (n_cycle / max(1, words / 500)) * 20) if words > 0 else 0.0

    # ── Composite Concrete Decisions (DC) ────────────────────────────────────
    dc = n_dec + (n_act_done * 2) + (n_reqs * 1.5)

    # ── Cost estimate ─────────────────────────────────────────────────────────
    cost = n_part * dur_h * cost_per_hour if dur_h > 0 else 0.0

    # ── ROI-TR (0–10) ─────────────────────────────────────────────────────────
    if cost > 0:
        roi = min(10.0, (dc * 1000.0 / cost) * 1.5)
    elif dc > 0:
        roi = 5.0
    else:
        roi = 0.0

    return MeetingROIData(
        meeting_number    = n,
        title             = title,
        date              = date,
        meeting_id        = mid,
        has_minutes       = bool(minutes_md),
        has_transcript    = bool(transcript),
        n_participants    = n_part,
        n_decisions       = n_dec,
        n_actions_total   = n_act_total,
        n_actions_complete= n_act_done,
        n_requirements    = n_reqs,
        word_count        = words,
        duration_min      = dur_min,
        duration_hours    = dur_h,
        cycle_signals     = n_cycle,
        trc               = trc,
        dc_score          = dc,
        cost_estimate     = cost,
        roi_tr            = roi,
        cost_per_hour     = cost_per_hour,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def compute_project_roi(
    project_id: str,
    cost_per_hour: float = 150.0,
) -> list[MeetingROIData]:
    """
    Compute ROI-TR for all meetings in a project.

    Returns a list of MeetingROIData ordered by meeting_number.
    Returns [] if Supabase is unavailable or no meetings exist.
    """
    from modules.supabase_client import get_supabase_client

    db = get_supabase_client()
    if not db:
        return []

    try:
        meetings = (
            db.table("meetings")
            .select(
                "id, meeting_number, title, meeting_date, "
                "minutes_md, transcript_clean, transcript_raw"
            )
            .eq("project_id", project_id)
            .order("meeting_number")
            .execute().data or []
        )
    except Exception:
        return []

    # Build meeting_id → requirement count map
    req_by_mid: dict[str, int] = {}
    try:
        req_rows = (
            db.table("requirements")
            .select("first_meeting_id")
            .eq("project_id", project_id)
            .execute().data or []
        )
        for r in req_rows:
            mid = r.get("first_meeting_id")
            if mid:
                req_by_mid[mid] = req_by_mid.get(mid, 0) + 1
    except Exception:
        pass

    return [_compute_single(m, req_by_mid, cost_per_hour) for m in meetings]


def project_summary(data: list[MeetingROIData]) -> dict:
    """Aggregate project-level stats from a list of MeetingROIData."""
    if not data:
        return {}
    roi_values   = [m.roi_tr for m in data]
    trc_values   = [m.trc for m in data if m.has_transcript]
    cost_values  = [m.cost_estimate for m in data if m.cost_estimate > 0]
    best         = max(data, key=lambda m: m.roi_tr)
    worst        = min(data, key=lambda m: m.roi_tr)
    return {
        "total_meetings"      : len(data),
        "avg_roi"             : sum(roi_values) / len(roi_values),
        "max_roi"             : max(roi_values),
        "min_roi"             : min(roi_values),
        "best_meeting"        : best,
        "worst_meeting"       : worst,
        "avg_trc"             : sum(trc_values) / len(trc_values) if trc_values else 0.0,
        "total_cost"          : sum(cost_values),
        "total_requirements"  : sum(m.n_requirements for m in data),
        "total_decisions"     : sum(m.n_decisions for m in data),
        "total_actions"       : sum(m.n_actions_total for m in data),
        "total_actions_done"  : sum(m.n_actions_complete for m in data),
    }
