# modules/cross_meeting_analyzer.py
# ─────────────────────────────────────────────────────────────────────────────
# Fase 3 — Análise cross-meeting: detecta tópicos recorrentes entre reuniões.
#
# Dois modos:
#   1. Semântico (primário)  — usa embeddings em transcript_chunks + SQL function
#                              find_recurring_topics() instalada via
#                              supabase_schema_meeting_quality.sql
#   2. Keyword (fallback)    — extrai termos técnicos/acrônimos que aparecem em
#                              3+ reuniões quando embeddings não estão disponíveis
#
# Zero chamadas LLM — análise totalmente determinística.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class RecurringTopic:
    topic_id: int                       # sequential index
    meetings: list[int]                 # meeting_numbers involved (sorted)
    meeting_titles: dict[int, str]      # meeting_number → title
    keywords: list[str]                 # key terms driving the match
    excerpt_a: str                      # context from first meeting
    excerpt_b: str                      # context from another meeting
    similarity: float                   # cosine similarity (0 = keyword match)
    detection: str                      # "semantic" | "keyword"

    @property
    def meetings_str(self) -> str:
        return ", ".join(f"R{n}" for n in sorted(self.meetings))

    @property
    def intensity_label(self) -> str:
        if self.similarity >= 0.93:
            return "🔴 Muito alto"
        if self.similarity >= 0.88:
            return "🟠 Alto"
        if self.similarity > 0:
            return "🟡 Moderado"
        return "ℹ️ Keyword"

    @property
    def intensity_color(self) -> str:
        if self.similarity >= 0.93:
            return "#ef4444"
        if self.similarity >= 0.88:
            return "#f97316"
        if self.similarity > 0:
            return "#eab308"
        return "#94a3b8"


# ── Internal helpers ──────────────────────────────────────────────────────────

# Portuguese stopwords (minimal set for keyword extraction)
_PT_STOPWORDS = {
    "a", "o", "as", "os", "de", "da", "do", "das", "dos", "em", "no", "na",
    "nos", "nas", "um", "uma", "uns", "umas", "e", "é", "eu", "tu", "ele",
    "ela", "nós", "para", "por", "com", "sem", "que", "se", "não", "mas",
    "ou", "seu", "sua", "seus", "suas", "isso", "este", "esta", "esse",
    "essa", "aqui", "ali", "então", "também", "já", "ainda", "mais", "como",
    "quando", "onde", "tudo", "isso", "foi", "ser", "ter", "fazer", "vai",
    "vou", "tem", "está", "são", "nos", "me", "te", "lhe", "nos", "vos",
    "lhes", "meu", "minha", "nosso", "nossa", "aquele", "aquela", "muito",
    "bem", "sim", "porque", "pelo", "pela", "pelos", "pelas", "qual", "quais",
    "sobre", "entre", "até", "depois", "antes", "durante", "sempre", "nunca",
    "pode", "precisa", "vai", "ser", "assim", "mesmo", "toda", "todo",
    "cada", "outros", "outras", "outro", "outra", "esse", "essa", "esses",
    "essas", "algum", "alguma", "nenhum", "nenhuma", "agora", "aqui", "lá",
    "aqui", "aí", "né", "pra", "pro", "numa", "num", "desse", "dessa",
    "deste", "desta", "nesse", "nessa", "neste", "nesta", "disso", "disto",
    "nisso", "nisto", "isso", "aquilo", "isto", "só", "também", "além",
    "através", "junto", "tendo", "sendo", "então", "talvez", "segundo",
    "tanto", "tão", "tal", "tais", "há", "havia", "haja", "haverá",
}

# Pattern to identify significant technical terms: uppercase acronyms,
# camelCase identifiers, or capitalized words (likely proper nouns / products)
_TECH_TERM_RE = re.compile(
    r'\b(?:'
    r'[A-ZÁÉÍÓÚÂÊÔÃ]{2,}'          # ACRONYMS: SLA, BPMN, SE-SUITE
    r'|[A-Z][a-z]+(?:[A-Z][a-z]+)+'  # CamelCase: SeeSuite
    r'|[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]{2,}){1,2}'  # Proper names: Maria José
    r')\b'
)

# Also capture hyphenated technical terms
_HYPHEN_TERM_RE = re.compile(
    r'\b[A-Za-z]{2,}(?:-[A-Za-z]{2,})+\b'  # SE-SUITE, E-MAIL, sub-módulo
)


def _extract_keywords(text: str) -> list[str]:
    """Extract significant terms from a block of text for keyword matching."""
    terms: set[str] = set()
    for m in _TECH_TERM_RE.finditer(text):
        t = m.group().strip()
        if len(t) >= 2 and t.lower() not in _PT_STOPWORDS:
            terms.add(t.upper() if len(t) <= 5 else t)
    for m in _HYPHEN_TERM_RE.finditer(text):
        t = m.group().strip()
        if len(t) >= 4:
            terms.add(t)
    return sorted(terms)


def _context_around(text: str, term: str, chars: int = 200) -> str:
    """Return a ~chars context window around the first occurrence of term."""
    pos = text.lower().find(term.lower())
    if pos == -1:
        return text[:chars]
    start = max(0, pos - chars // 2)
    end   = min(len(text), pos + len(term) + chars // 2)
    snippet = text[start:end].replace("\n", " ").strip()
    if start > 0:
        snippet = "…" + snippet
    if end < len(text):
        snippet += "…"
    return snippet


# ── Semantic detection (via SQL function) ────────────────────────────────────

def _semantic(
    project_id: str,
    threshold: float,
    max_pairs: int,
    meeting_map: dict[str, dict],
) -> list[RecurringTopic]:
    """
    Call find_recurring_topics() SQL function.
    Returns [] if the function doesn't exist or transcript_chunks is empty.
    """
    from modules.supabase_client import get_supabase_client
    db = get_supabase_client()
    if not db:
        return []

    try:
        rows = db.rpc(
            "find_recurring_topics",
            {
                "p_project_id":   project_id,
                "p_threshold":    threshold,
                "p_max_results":  max_pairs,
            },
        ).execute().data or []
    except Exception:
        return []

    if not rows:
        return []

    topics: list[RecurringTopic] = []
    seen: set[frozenset] = set()    # deduplicate meeting pairs

    for i, row in enumerate(rows):
        mid_a = row.get("meeting_id_a") or ""
        mid_b = row.get("meeting_id_b") or ""
        m_a   = meeting_map.get(mid_a, {})
        m_b   = meeting_map.get(mid_b, {})
        n_a   = m_a.get("meeting_number", 0)
        n_b   = m_b.get("meeting_number", 0)

        pair_key = frozenset({n_a, n_b})
        if pair_key in seen:
            continue
        seen.add(pair_key)

        text_a = row.get("chunk_text_a") or ""
        text_b = row.get("chunk_text_b") or ""
        sim    = float(row.get("similarity") or 0)
        kws    = _extract_keywords(text_a + " " + text_b)[:5]

        topics.append(RecurringTopic(
            topic_id       = i + 1,
            meetings       = sorted([n_a, n_b]),
            meeting_titles = {
                n_a: m_a.get("title") or f"Reunião {n_a}",
                n_b: m_b.get("title") or f"Reunião {n_b}",
            },
            keywords  = kws,
            excerpt_a = text_a[:300],
            excerpt_b = text_b[:300],
            similarity = sim,
            detection  = "semantic",
        ))

    return topics


# ── Keyword fallback ──────────────────────────────────────────────────────────

def _keyword_fallback(
    project_id: str,
    max_topics: int,
    meeting_map: dict[str, dict],
) -> list[RecurringTopic]:
    """
    Extract significant technical terms and find those appearing in 2+ meetings.
    Used when transcript_chunks (embeddings) are not available.
    """
    # Build meeting_number → transcript map
    meetings_by_num: dict[int, dict] = {
        m.get("meeting_number", 0): m
        for m in meeting_map.values()
        if m.get("meeting_number")
    }

    # Extract terms per meeting
    term_to_meetings: dict[str, list[int]] = {}
    for num, m in meetings_by_num.items():
        transcript = m.get("transcript_clean") or m.get("transcript_raw") or ""
        if not transcript:
            continue
        for term in _extract_keywords(transcript):
            if term not in term_to_meetings:
                term_to_meetings[term] = []
            if num not in term_to_meetings[term]:
                term_to_meetings[term].append(num)

    # Keep terms appearing in 2+ meetings, sorted by frequency
    recurring = sorted(
        [(term, sorted(nums)) for term, nums in term_to_meetings.items() if len(nums) >= 2],
        key=lambda x: (-len(x[1]), x[0]),
    )[:max_topics]

    if not recurring:
        return []

    # Cluster: group terms by identical meeting set to avoid repetition
    cluster_map: dict[str, list[str]] = {}
    for term, nums in recurring:
        key = ",".join(str(n) for n in nums)
        cluster_map.setdefault(key, []).append(term)

    topics: list[RecurringTopic] = []
    for i, (key, terms) in enumerate(cluster_map.items()):
        nums = [int(n) for n in key.split(",")]
        # Pick the first two meetings for excerpts
        n_a = nums[0]
        n_b = nums[1] if len(nums) > 1 else nums[0]
        m_a = meetings_by_num.get(n_a, {})
        m_b = meetings_by_num.get(n_b, {})
        t_a = m_a.get("transcript_clean") or m_a.get("transcript_raw") or ""
        t_b = m_b.get("transcript_clean") or m_b.get("transcript_raw") or ""
        best_term = terms[0]

        topics.append(RecurringTopic(
            topic_id       = i + 1,
            meetings       = nums,
            meeting_titles = {
                n: meetings_by_num.get(n, {}).get("title") or f"Reunião {n}"
                for n in nums
            },
            keywords  = terms[:6],
            excerpt_a = _context_around(t_a, best_term) if t_a else "(sem transcrição)",
            excerpt_b = _context_around(t_b, best_term) if t_b else "(sem transcrição)",
            similarity = 0.0,
            detection  = "keyword",
        ))

    return topics[:max_topics]


# ── Public API ────────────────────────────────────────────────────────────────

def find_recurring_topics(
    project_id: str,
    threshold: float = 0.87,
    max_results: int = 25,
) -> tuple[list[RecurringTopic], str]:
    """
    Detect recurring topics across meetings in the project.

    Returns (topics, method) where method is "semantic" or "keyword".

    Strategy:
    1. Try semantic via find_recurring_topics() SQL function + embeddings.
    2. Fall back to keyword overlap if embeddings unavailable.
    """
    from modules.supabase_client import get_supabase_client
    db = get_supabase_client()
    if not db:
        return [], "unavailable"

    # Load meeting metadata for enrichment
    try:
        rows = (
            db.table("meetings")
            .select("id, meeting_number, title, transcript_clean, transcript_raw")
            .eq("project_id", project_id)
            .order("meeting_number")
            .execute().data or []
        )
    except Exception:
        return [], "error"

    meeting_map: dict[str, dict] = {m["id"]: m for m in rows if m.get("id")}

    # ── Try semantic ───────────────────────────────────────────────────────────
    topics = _semantic(project_id, threshold, max_results, meeting_map)
    if topics:
        return topics, "semantic"

    # ── Fallback: keyword ──────────────────────────────────────────────────────
    topics = _keyword_fallback(project_id, max_results, meeting_map)
    return topics, "keyword"


# ── Score persistence ─────────────────────────────────────────────────────────

def save_project_scores(
    project_id: str,
    roi_data: list,      # list[MeetingROIData]
) -> dict:
    """
    Persist ROI-TR scores to meeting_quality_scores table.

    Returns {"saved": N, "errors": [...]}
    """
    from modules.supabase_client import get_supabase_client
    db = get_supabase_client()
    if not db:
        return {"saved": 0, "errors": ["Supabase não configurado."]}

    # Resolve meeting_id → UUID for each meeting_number
    try:
        rows = (
            db.table("meetings")
            .select("id, meeting_number")
            .eq("project_id", project_id)
            .execute().data or []
        )
        num_to_id = {r["meeting_number"]: r["id"] for r in rows if r.get("id")}
    except Exception as exc:
        return {"saved": 0, "errors": [f"Erro ao carregar reuniões: {exc}"]}

    saved  = 0
    errors = []
    for m in roi_data:
        mid = num_to_id.get(m.meeting_number)
        if not mid:
            errors.append(f"Reunião {m.meeting_number}: ID não encontrado.")
            continue
        payload = {
            "project_id":          project_id,
            "meeting_id":          mid,
            "meeting_number":      m.meeting_number,
            "cost_per_hour":       m.cost_per_hour,
            "n_participants":      m.n_participants,
            "duration_min":        round(m.duration_min, 2),
            "cost_estimate":       round(m.cost_estimate, 2),
            "n_decisions":         m.n_decisions,
            "n_actions_total":     m.n_actions_total,
            "n_actions_complete":  m.n_actions_complete,
            "n_requirements":      m.n_requirements,
            "cycle_signals":       m.cycle_signals,
            "trc":                 round(m.trc, 2),
            "dc_score":            round(m.dc_score, 2),
            "roi_tr":              round(m.roi_tr, 2),
        }
        try:
            db.table("meeting_quality_scores").insert(payload).execute()
            saved += 1
        except Exception as exc:
            errors.append(f"Reunião {m.meeting_number}: {exc}")

    return {"saved": saved, "errors": errors}


def load_score_history(
    project_id: str,
    meeting_number: int | None = None,
) -> list[dict]:
    """Load historical ROI-TR scores for trend analysis."""
    from modules.supabase_client import get_supabase_client
    db = get_supabase_client()
    if not db:
        return []
    try:
        q = (
            db.table("meeting_quality_scores")
            .select("meeting_number, computed_at, roi_tr, trc, cost_estimate, dc_score")
            .eq("project_id", project_id)
            .order("computed_at", desc=False)
        )
        if meeting_number is not None:
            q = q.eq("meeting_number", meeting_number)
        return q.execute().data or []
    except Exception:
        return []
