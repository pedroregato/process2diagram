# modules/meeting_roi_calculator.py
# ─────────────────────────────────────────────────────────────────────────────
# ROI-TR (Retorno sobre Investimento — Tempo de Reunião) calculator  v2
#
# v2 — Type-aware formula with LLM classification (DeepSeek).
#   Each meeting type has a weight profile that defines which artefacts are
#   primary, secondary or irrelevant.  DC is computed using the weights that
#   match the meeting type; a fulfillment score shows delivery against the
#   type's expected minimum output.
#
# Zero hard LLM dependency — classification is optional and falls back to a
# heuristic when no api_key / provider_cfg is supplied.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import re
from dataclasses import dataclass


# ── Cyclical-discussion signal patterns ───────────────────────────────────────

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


# ── Meeting type registry ──────────────────────────────────────────────────────

MEETING_TYPES: list[str] = [
    "Levantamento de Requisitos",
    "Tomada de Decisão",
    "Revisão de Processos",
    "Definição Conceitual",
    "Planejamento",
    "Retrospectiva",
    "Status Report",
    "Kick-off",
    "Validação",
    "Esclarecimento de Dúvidas",
    "Híbrida",
]

# Weight profile per meeting type.
# Keys: req, dec, act (action items complete), sbvr, bpmn
# min_dc: minimum weighted DC expected for full-fulfillment of this type.
TYPE_WEIGHTS: dict[str, dict] = {
    "Levantamento de Requisitos": {
        "req": 3.0, "dec": 1.0, "act": 1.5, "sbvr": 2.0, "bpmn": 1.0,
        "min_dc": 4.5,
    },
    "Tomada de Decisão": {
        "req": 0.5, "dec": 3.0, "act": 2.0, "sbvr": 0.0, "bpmn": 0.0,
        "min_dc": 6.0,
    },
    "Revisão de Processos": {
        "req": 1.0, "dec": 1.5, "act": 1.5, "sbvr": 1.5, "bpmn": 3.0,
        "min_dc": 3.0,
    },
    "Definição Conceitual": {
        "req": 1.5, "dec": 1.0, "act": 1.0, "sbvr": 3.0, "bpmn": 1.5,
        "min_dc": 9.0,
    },
    "Planejamento": {
        "req": 1.5, "dec": 2.0, "act": 2.5, "sbvr": 0.0, "bpmn": 1.0,
        "min_dc": 5.0,
    },
    "Retrospectiva": {
        "req": 0.5, "dec": 1.5, "act": 3.0, "sbvr": 0.0, "bpmn": 0.0,
        "min_dc": 6.0,
    },
    "Status Report": {
        "req": 0.0, "dec": 2.0, "act": 2.5, "sbvr": 0.0, "bpmn": 0.0,
        "min_dc": 2.0,
    },
    "Kick-off": {
        "req": 1.0, "dec": 2.0, "act": 2.5, "sbvr": 1.0, "bpmn": 0.5,
        "min_dc": 4.0,
    },
    "Validação": {
        "req": 1.0, "dec": 2.5, "act": 2.0, "sbvr": 0.5, "bpmn": 1.0,
        "min_dc": 2.5,
    },
    "Esclarecimento de Dúvidas": {
        "req": 0.0, "dec": 2.0, "act": 2.0, "sbvr": 0.5, "bpmn": 0.0,
        "min_dc": 2.0,
    },
    "Híbrida": {
        "req": 1.0, "dec": 1.5, "act": 1.5, "sbvr": 1.0, "bpmn": 0.5,
        "min_dc": 3.0,
    },
}

_FALLBACK_TYPE = "Híbrida"

# ── Meeting type icons ─────────────────────────────────────────────────────────

TYPE_ICONS: dict[str, str] = {
    "Levantamento de Requisitos": "📋",
    "Tomada de Decisão":          "⚖️",
    "Revisão de Processos":       "🔄",
    "Definição Conceitual":       "📖",
    "Planejamento":               "📅",
    "Retrospectiva":              "🔍",
    "Status Report":              "📊",
    "Kick-off":                   "🚀",
    "Validação":                  "✅",
    "Esclarecimento de Dúvidas":  "❓",
    "Híbrida":                    "🔀",
}


# ── Heuristic classifier (no LLM) ─────────────────────────────────────────────

def _classify_heuristic(
    title: str,
    n_req: int,
    n_dec: int,
    n_actions: int,
    n_sbvr: int,
    n_bpmn: int,
) -> tuple[str, float]:
    """Classify meeting type from title keywords and artefact counts."""
    t = title.lower()

    _KW: list[tuple[list[str], str]] = [
        (["kick-off", "kickoff", "abertura", "iniciação", "início do projeto"],  "Kick-off"),
        (["retrospectiva", "retro", "lições aprendidas", "lessons learned"],     "Retrospectiva"),
        (["levantamento", "elicitação", "elicitar", "requisito"],                "Levantamento de Requisitos"),
        (["validação", "validar", "aceite", "homologação", "uat"],               "Validação"),
        (["planejamento", "planning", "sprint plan", "release plan"],            "Planejamento"),
        (["status", "acompanhamento", "progresso", "report", "ponto de controle"], "Status Report"),
        (["processo", "fluxo", "bpmn", "mapeamento", "revisão de processo"],     "Revisão de Processos"),
        (["decisão", "decisões", "aprovação", "comitê", "ccb", "governança"],   "Tomada de Decisão"),
        (["glossário", "vocabulário", "dicionário", "definição", "conceitual"],  "Definição Conceitual"),
        (["dúvida", "esclarecimento", "alinhamento pontual", "impedimento"],     "Esclarecimento de Dúvidas"),
    ]
    for keywords, mtype in _KW:
        if any(kw in t for kw in keywords):
            return mtype, 0.75

    # Artefact-based fallback (lower confidence)
    if n_sbvr >= 3:
        return "Definição Conceitual", 0.45
    if n_req >= 3:
        return "Levantamento de Requisitos", 0.45
    if n_bpmn >= 1:
        return "Revisão de Processos", 0.45
    if n_dec >= 3 and n_req == 0:
        return "Tomada de Decisão", 0.45
    if n_actions >= 3 and n_dec < 2:
        return "Planejamento", 0.35

    return _FALLBACK_TYPE, 0.30


# ── LLM classifier ────────────────────────────────────────────────────────────

_CLASSIFY_SYSTEM = """Você é um classificador de reuniões corporativas.
Dada uma reunião (título, trecho da transcrição e contagem de artefatos gerados),
classifique-a em EXATAMENTE um dos tipos abaixo e atribua uma confiança de 0.0 a 1.0.

Tipos válidos:
""" + "\n".join(f"- {t}" for t in MEETING_TYPES) + """

Responda APENAS com JSON válido, sem texto extra:
{"type": "<tipo>", "confidence": <0.0–1.0>}"""


def classify_meeting_type(
    title: str,
    transcript_sample: str,
    n_req: int,
    n_dec: int,
    n_actions: int,
    n_sbvr: int,
    n_bpmn: int,
    llm_config: dict,
) -> tuple[str, float]:
    """
    Classify meeting type using LLM.

    llm_config must contain: api_key, model, provider_cfg
    Falls back to heuristic on any LLM error.

    Returns (meeting_type: str, confidence: float).
    """
    api_key     = llm_config.get("api_key", "")
    model       = llm_config.get("model", "")
    provider    = llm_config.get("provider_cfg", {})
    client_type = provider.get("client_type", "openai_compatible")
    base_url    = provider.get("base_url")

    if not api_key or not model:
        return _classify_heuristic(title, n_req, n_dec, n_actions, n_sbvr, n_bpmn)

    excerpt = " ".join(transcript_sample.split()[:400]) if transcript_sample else "(sem transcrição)"
    artefacts = (
        f"Requisitos: {n_req}, Decisões: {n_dec}, Itens de ação: {n_actions}, "
        f"Termos/Regras SBVR: {n_sbvr}, Processos BPMN: {n_bpmn}"
    )
    user_prompt = (
        f"Título da reunião: {title}\n\n"
        f"Trecho da transcrição (primeiras ~400 palavras):\n{excerpt}\n\n"
        f"Artefatos gerados: {artefacts}"
    )

    try:
        if client_type == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            resp = client.messages.create(
                model=model,
                max_tokens=64,
                system=_CLASSIFY_SYSTEM,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = resp.content[0].text.strip()
        else:
            from openai import OpenAI
            kwargs: dict = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            client = OpenAI(**kwargs)
            resp = client.chat.completions.create(
                model=model,
                response_format={"type": "json_object"},
                max_tokens=64,
                messages=[
                    {"role": "system", "content": _CLASSIFY_SYSTEM},
                    {"role": "user",   "content": user_prompt},
                ],
            )
            raw = resp.choices[0].message.content or "{}"

        data       = json.loads(raw)
        mtype      = data.get("type", _FALLBACK_TYPE)
        confidence = float(data.get("confidence", 0.5))

        if mtype not in MEETING_TYPES:
            # LLM returned an unexpected type — fuzzy match
            mtype_lower = mtype.lower()
            for t in MEETING_TYPES:
                if any(w in mtype_lower for w in t.lower().split()):
                    mtype = t
                    break
            else:
                mtype = _FALLBACK_TYPE
                confidence = 0.3

        return mtype, min(1.0, max(0.0, confidence))

    except Exception:
        return _classify_heuristic(title, n_req, n_dec, n_actions, n_sbvr, n_bpmn)


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
    n_sbvr: int          # sbvr_terms + sbvr_rules
    n_bpmn_procs: int    # bpmn_processes for this meeting

    word_count: int
    duration_min: float
    duration_hours: float

    cycle_signals: int
    trc: float           # 0–100

    meeting_type: str            # classified type
    meeting_type_confidence: float  # 0–1
    fulfillment_score: float     # 0–1 — how well the meeting delivered vs type expectation

    dc_score: float      # type-weighted composite Concrete Decisions
    cost_estimate: float
    roi_tr: float        # 0–10

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
    def fulfillment_label(self) -> str:
        if self.fulfillment_score >= 0.9:
            return "🟢 Pleno"
        if self.fulfillment_score >= 0.6:
            return "🟡 Parcial"
        if self.fulfillment_score >= 0.3:
            return "🟠 Baixo"
        return "🔴 Crítico"

    @property
    def type_icon(self) -> str:
        return TYPE_ICONS.get(self.meeting_type, "🔀")

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
    sbvr_by_mid: dict[str, int],
    bpmn_by_mid: dict[str, int],
    cost_per_hour: float,
    meeting_type: str,
    meeting_type_confidence: float,
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

    # ── Requirements, SBVR, BPMN ─────────────────────────────────────────────
    n_reqs      = req_by_mid.get(mid, 0)
    n_sbvr      = sbvr_by_mid.get(mid, 0)
    n_bpmn_proc = min(1, bpmn_by_mid.get(mid, 0))  # cap at 1 — existence matters

    # ── Transcript word count and duration ───────────────────────────────────
    words   = len(transcript.split()) if transcript else 0
    dur_min = words / 130.0 if words else 0.0
    dur_h   = dur_min / 60.0

    # ── TRC proxy ────────────────────────────────────────────────────────────
    n_cycle = len(_CYCLE_RE.findall(transcript)) if transcript else 0
    trc     = min(100.0, (n_cycle / max(1, words / 500)) * 20) if words > 0 else 0.0

    # ── Type-weighted DC ─────────────────────────────────────────────────────
    w  = TYPE_WEIGHTS.get(meeting_type, TYPE_WEIGHTS[_FALLBACK_TYPE])
    dc = (
        n_dec       * w["dec"]
        + n_act_done * w["act"]
        + n_reqs     * w["req"]
        + n_sbvr     * w["sbvr"]
        + n_bpmn_proc * w["bpmn"]
    )

    # ── Fulfillment score: actual DC vs expected minimum for this type ────────
    min_dc      = max(1.0, w["min_dc"])
    fulfillment = min(1.0, dc / min_dc)

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
        meeting_number           = n,
        title                    = title,
        date                     = date,
        meeting_id               = mid,
        has_minutes              = bool(minutes_md),
        has_transcript           = bool(transcript),
        n_participants           = n_part,
        n_decisions              = n_dec,
        n_actions_total          = n_act_total,
        n_actions_complete       = n_act_done,
        n_requirements           = n_reqs,
        n_sbvr                   = n_sbvr,
        n_bpmn_procs             = n_bpmn_proc,
        word_count               = words,
        duration_min             = dur_min,
        duration_hours           = dur_h,
        cycle_signals            = n_cycle,
        trc                      = trc,
        meeting_type             = meeting_type,
        meeting_type_confidence  = meeting_type_confidence,
        fulfillment_score        = fulfillment,
        dc_score                 = dc,
        cost_estimate            = cost,
        roi_tr                   = roi,
        cost_per_hour            = cost_per_hour,
    )


# ── Public API ────────────────────────────────────────────────────────────────

def compute_project_roi(
    project_id: str,
    cost_per_hour: float = 150.0,
    llm_config: dict | None = None,
    save_types: bool = True,
) -> list[MeetingROIData]:
    """
    Compute ROI-TR for all meetings in a project.

    When llm_config is provided (api_key, model, provider_cfg), meetings that
    don't yet have a meeting_type are classified via LLM and (when save_types=True)
    the type is persisted back to meetings.meeting_type.

    Returns a list of MeetingROIData ordered by meeting_number.
    Returns [] if Supabase is unavailable or no meetings exist.
    """
    from modules.supabase_client import get_supabase_client

    db = get_supabase_client()
    if not db:
        return []

    # ── Meetings ──────────────────────────────────────────────────────────────
    try:
        meetings = (
            db.table("meetings")
            .select(
                "id, meeting_number, title, meeting_date, meeting_type, "
                "minutes_md, transcript_clean, transcript_raw"
            )
            .eq("project_id", project_id)
            .order("meeting_number")
            .execute().data or []
        )
    except Exception:
        # Column meeting_type may not exist yet — retry without it
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

    if not meetings:
        return []

    # ── Requirements per meeting ──────────────────────────────────────────────
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

    # ── SBVR per meeting (terms + rules) ─────────────────────────────────────
    sbvr_by_mid: dict[str, int] = {}
    for tbl in ("sbvr_terms", "sbvr_rules"):
        try:
            rows = (
                db.table(tbl)
                .select("meeting_id")
                .execute().data or []
            )
            for r in rows:
                mid = r.get("meeting_id")
                if mid:
                    sbvr_by_mid[mid] = sbvr_by_mid.get(mid, 0) + 1
        except Exception:
            pass

    # ── BPMN processes per meeting ────────────────────────────────────────────
    bpmn_by_mid: dict[str, int] = {}
    try:
        bpmn_rows = (
            db.table("bpmn_processes")
            .select("meeting_id")
            .execute().data or []
        )
        for r in bpmn_rows:
            mid = r.get("meeting_id")
            if mid:
                bpmn_by_mid[mid] = bpmn_by_mid.get(mid, 0) + 1
    except Exception:
        pass

    # ── Classify and compute ──────────────────────────────────────────────────
    results: list[MeetingROIData] = []
    for m in meetings:
        mid   = m.get("id") or ""
        title = m.get("title") or f"Reunião {m.get('meeting_number', 0)}"
        n_req = req_by_mid.get(mid, 0)
        n_sbv = sbvr_by_mid.get(mid, 0)
        n_bpm = bpmn_by_mid.get(mid, 0)

        # Rebuild minimal artefact counts for classifier
        minutes_md = m.get("minutes_md") or ""
        transcript = m.get("transcript_clean") or m.get("transcript_raw") or ""
        dec_lines  = [
            l for l in _section(minutes_md, "Decisões", "Decisions").splitlines()
            if l.strip() and l.strip()[0] in "-•*|123456789"
        ]
        act_lines = [
            l for l in _section(minutes_md, "Itens de Ação", "Action Items", "Ações").splitlines()
            if l.strip()
        ]
        n_dec = len(dec_lines)
        n_act = len(act_lines)

        stored_type = m.get("meeting_type") or ""

        if stored_type and stored_type in MEETING_TYPES:
            mtype      = stored_type
            confidence = 1.0  # was persisted → treat as authoritative
        elif llm_config:
            mtype, confidence = classify_meeting_type(
                title        = title,
                transcript_sample = transcript,
                n_req        = n_req,
                n_dec        = n_dec,
                n_actions    = n_act,
                n_sbvr       = n_sbv,
                n_bpmn       = n_bpm,
                llm_config   = llm_config,
            )
            # Persist back to DB so next run reuses the classification
            if save_types and mid:
                try:
                    db.table("meetings").update({"meeting_type": mtype}).eq("id", mid).execute()
                except Exception:
                    pass
        else:
            mtype, confidence = _classify_heuristic(title, n_req, n_dec, n_act, n_sbv, n_bpm)

        results.append(_compute_single(
            meeting                  = m,
            req_by_mid               = req_by_mid,
            sbvr_by_mid              = sbvr_by_mid,
            bpmn_by_mid              = bpmn_by_mid,
            cost_per_hour            = cost_per_hour,
            meeting_type             = mtype,
            meeting_type_confidence  = confidence,
        ))

    return results


def project_summary(data: list[MeetingROIData]) -> dict:
    """Aggregate project-level stats from a list of MeetingROIData."""
    if not data:
        return {}
    roi_values  = [m.roi_tr for m in data]
    trc_values  = [m.trc for m in data if m.has_transcript]
    cost_values = [m.cost_estimate for m in data if m.cost_estimate > 0]
    best        = max(data, key=lambda m: m.roi_tr)
    worst       = min(data, key=lambda m: m.roi_tr)
    return {
        "total_meetings"       : len(data),
        "avg_roi"              : sum(roi_values) / len(roi_values),
        "max_roi"              : max(roi_values),
        "min_roi"              : min(roi_values),
        "best_meeting"         : best,
        "worst_meeting"        : worst,
        "avg_trc"              : sum(trc_values) / len(trc_values) if trc_values else 0.0,
        "total_cost"           : sum(cost_values),
        "total_requirements"   : sum(m.n_requirements for m in data),
        "total_decisions"      : sum(m.n_decisions for m in data),
        "total_actions"        : sum(m.n_actions_total for m in data),
        "total_actions_done"   : sum(m.n_actions_complete for m in data),
        "total_sbvr"           : sum(m.n_sbvr for m in data),
        "total_bpmn"           : sum(m.n_bpmn_procs for m in data),
    }
