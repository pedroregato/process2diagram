# modules/pii_sanitizer.py
# ─────────────────────────────────────────────────────────────────────────────
# PII sanitization before LLM calls — two tiers:
#
#  Tier 1 — Structured PII (per-call, stateless):
#    CPF, CNPJ, email, phone, monetary values → @LABEL_NNN tokens.
#    sanitize(text) / desanitize(text, token_map)  ← unchanged API
#
#  Tier 2 — Personal names (session-wide, stateful):
#    Detected ONCE via spaCy on the full transcript; stored in hub.meta.name_map.
#    detect_names(text) → { "[PESSOA:PG]": "Pedro Gentil" }
#    sanitize(text, name_map=...) applies substitutions per LLM call.
#    desanitize() handles both tiers via the merged token_map.
#
# Design decisions:
#   - Only multi-word names (≥ 2 parts) are pseudonymized — single words
#     ("João", "Maria") are too ambiguous in Brazilian meeting transcripts.
#   - Title+surname variants handled in sanitize() ("Sr. Gentil" → [PESSOA:PG]).
#   - Initials are unique within a session; collisions resolved automatically.
#   - Fail-open throughout: any spaCy error returns empty map, pipeline continues.
#   - Token format [PESSOA:XX] chosen for LLM robustness — brackets are
#     preserved >95% of the time vs ~70% for {curly brace} variants.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ── Shared dataclass ──────────────────────────────────────────────────────────

@dataclass
class SanitizationResult:
    text: str
    token_map: dict[str, str] = field(default_factory=dict)  # token → original


# ── Tier 1: Structured PII patterns ──────────────────────────────────────────
#
# Ordered most-specific → least-specific to avoid partial matches.

_PATTERNS: list[tuple[str, re.Pattern]] = [
    # CNPJ — before CPF (longer digit sequence)
    ("CNPJ",  re.compile(r'\b\d{2}\.?\d{3}\.?\d{3}/?\.?\d{4}[-.]?\d{2}\b')),
    # CPF
    ("CPF",   re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}[-.]?\d{2}\b')),
    # Email
    ("EMAIL", re.compile(r'\b[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+\b', re.IGNORECASE)),
    # Brazilian phone (+55 optional, DDD optional, 8 or 9 digits)
    ("TEL",   re.compile(
        r'(?:(?:\+55\s?)?(?:\(?\d{2}\)?\s?))?(?:9\s?)?\d{4}[-\s]?\d{4}\b'
    )),
    # Monetary value in BRL — "R$ 1.200,00" / "R$ 5M" / "R$ 2 milhões"
    ("VALOR", re.compile(
        r'R\$\s?[\d.,]+(?:\s?(?:mil(?:h[oõ]es?)?|bi(?:lh[oõ]es?)?|M|k))?',
        re.IGNORECASE,
    )),
]


def sanitize(text: str, name_map: dict[str, str] | None = None) -> SanitizationResult:
    """
    Replace PII in *text* with stable tokens.

    Tier 1 (always applied): CPF, CNPJ, email, phone, monetary values.
    Tier 2 (when name_map provided): person names pre-detected via detect_names().

    name_map format: { "[PESSOA:PG]": "Pedro Gentil" }  (token → original)

    Names are substituted BEFORE structured patterns to prevent any accidental
    overlap with digit sequences inside names.

    Returns SanitizationResult with:
        .text       — sanitized text (safe to send to LLM)
        .token_map  — merged map for desanitize() (both tiers)
    """
    merged: dict[str, str] = {}

    # ── Tier 2: personal names ────────────────────────────────────────────────
    if name_map:
        # Sort by name length desc so longer/more-specific names replace first.
        name_pairs = sorted(
            ((name, token) for token, name in name_map.items()),
            key=lambda x: len(x[0]),
            reverse=True,
        )

        # Full name substitution
        for name, token in name_pairs:
            text = re.sub(
                rf'\b{re.escape(name)}\b',
                token,
                text,
                flags=re.IGNORECASE,
            )

        # Title + surname variants: "Sr. Gentil" → [PESSOA:PG]
        _TITLES_RE = ("Sr.", "Sra.", "Dr.", "Dra.", "Prof.", "Profa.", "Eng.")
        for name, token in name_pairs:
            parts = name.split()
            if len(parts) >= 2:
                surname = re.escape(parts[-1])
                for title in _TITLES_RE:
                    text = re.sub(
                        rf'\b{re.escape(title)}\s+{surname}\b',
                        token,
                        text,
                        flags=re.IGNORECASE,
                    )

        merged.update(name_map)

    # ── Tier 1: structured PII ────────────────────────────────────────────────
    counters: dict[str, int] = {}
    _orig_to_token: dict[str, str] = {}

    def _replace(label: str, match: re.Match) -> str:
        original = match.group(0)
        if original in _orig_to_token:
            return _orig_to_token[original]
        counters[label] = counters.get(label, 0) + 1
        token = f"@{label}_{counters[label]:03d}"
        merged[token] = original
        _orig_to_token[original] = token
        return token

    for label, pattern in _PATTERNS:
        text = pattern.sub(lambda m, lbl=label: _replace(lbl, m), text)

    return SanitizationResult(text=text, token_map=merged)


def desanitize(text: str, token_map: dict[str, str]) -> str:
    """
    Replace tokens in *text* with their original values using *token_map*.

    Handles both Tier 1 tokens (@CPF_001) and Tier 2 tokens ([PESSOA:PG]).
    Safe to call with an empty map — returns text unchanged.
    """
    if not token_map:
        return text
    for token, original in token_map.items():
        text = text.replace(token, original)
    return text


# ── Tier 2: Name detection ────────────────────────────────────────────────────

_SPACY_MAX_CHARS = 50_000
_HONORIFICS = frozenset({
    "dr", "dra", "sr", "sra", "prof", "profa", "eng", "adv", "rev", "pe", "me"
})


def _get_nlp():
    """Lazy-load spaCy pt_core_news_lg once per process (mirrors nlp_chunker pattern)."""
    if not hasattr(_get_nlp, "_cache"):
        import spacy
        _get_nlp._cache = spacy.load("pt_core_news_lg")
    return _get_nlp._cache


def _clean_name(raw: str) -> str:
    """Strip leading/trailing honorific titles and normalize whitespace."""
    parts = raw.strip().split()
    cleaned = [p for p in parts if p.lower().rstrip(".") not in _HONORIFICS]
    return " ".join(cleaned).strip()


def _unique_initials(name: str, used: set[str]) -> str:
    """
    Generate unique uppercase initials for *name*, disambiguating collisions.

    Resolution order:
      1. First letter of each word:         "Pedro Gentil"  → "PG"
      2. First letter + full last name:     "Paulo Gomes"   → "PGOMES"
      3. Numbered suffix on base initials:  still "PG"      → "PG2", "PG3" …
    """
    parts = name.split()
    initials = "".join(p[0].upper() for p in parts if p)

    if initials not in used:
        return initials

    if len(parts) >= 2:
        candidate = (parts[0][0] + parts[-1]).upper()
        if candidate not in used:
            return candidate

    base = initials
    counter = 2
    while f"{base}{counter}" in used:
        counter += 1
    return f"{base}{counter}"


def detect_names(text: str) -> dict[str, str]:
    """
    Detect full person names in *text* using spaCy NER (pt_core_news_lg).

    Returns a name_map ready for use as the *name_map* arg in sanitize():
        { "[PESSOA:PG]": "Pedro Gentil", "[PESSOA:AS]": "Ana Souza" }

    Call this ONCE on hub.transcript_clean and store the result in
    hub.meta.name_map.  Every subsequent _call_llm() passes it to sanitize()
    so all agents share a consistent pseudonymization scheme.

    Notes:
    - Only multi-word names (≥ 2 parts after title stripping) are mapped.
      Single words are too ambiguous ("João" may not refer to João da Silva).
    - Input is capped at _SPACY_MAX_CHARS to bound processing time on long
      transcripts.  Names beyond that limit are not detected (acceptable for MVP).
    - Fail-open: any error (spaCy not installed, model missing, OOM) returns {}
      so the pipeline is never blocked.
    """
    try:
        nlp = _get_nlp()
    except Exception:
        return {}

    try:
        doc = nlp(text[:_SPACY_MAX_CHARS])
    except Exception:
        return {}

    seen: dict[str, str] = {}        # cleaned_name_lower → token
    token_map: dict[str, str] = {}   # token → original_name
    used_initials: set[str] = set()

    for ent in doc.ents:
        if ent.label_ != "PER":
            continue

        cleaned = _clean_name(ent.text)
        if len(cleaned.split()) < 2:
            continue  # single-word names skipped (too ambiguous)

        key = cleaned.lower()
        if key in seen:
            continue  # already registered

        initials = _unique_initials(cleaned, used_initials)
        used_initials.add(initials)
        token = f"[PESSOA:{initials}]"

        seen[key] = token
        token_map[token] = cleaned

    return token_map
