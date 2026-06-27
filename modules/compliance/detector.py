# modules/compliance/detector.py
# ─────────────────────────────────────────────────────────────────────────────
# PII classification for LGPD compliance (PC81).
#
# CLASSIFICATION ONLY — no anonymization, no text replacement.
# Names detected via spaCy NER are listed for disclosure purposes only.
# The pii_sanitizer.py handles replacement for LLM calls; this module
# is solely for compliance awareness and audit purposes.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re
from dataclasses import dataclass, field


# ── Structured PII patterns (mirrors pii_sanitizer._PATTERNS) ────────────────

_STRUCTURED: list[tuple[str, re.Pattern]] = [
    ("CNPJ",  re.compile(r'\b\d{2}\.?\d{3}\.?\d{3}/?\.?\d{4}[-.]?\d{2}\b')),
    ("CPF",   re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}[-.]?\d{2}\b')),
    ("EMAIL", re.compile(r'\b[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+\b', re.IGNORECASE)),
    ("TEL",   re.compile(
        r'(?:(?:\+55\s?)?(?:\(?\d{2}\)?\s?))?(?:9\s?)?\d{4}[-\s]?\d{4}\b'
    )),
    ("VALOR", re.compile(
        r'R\$\s?[\d.,]+(?:\s?(?:mil(?:h[oõ]es?)?|bi(?:lh[oõ]es?)?|M|k))?',
        re.IGNORECASE,
    )),
]

# Cap text sent to spaCy to avoid OOM on very long transcripts
_SPACY_MAX_CHARS = 50_000


# ── spaCy lazy loader (function-level cache, same pattern as nlp_chunker) ────

def _get_nlp():
    if not hasattr(_get_nlp, "_cache"):
        try:
            import spacy
            try:
                _get_nlp._cache = spacy.load("pt_core_news_lg")
            except OSError:
                try:
                    _get_nlp._cache = spacy.load("pt_core_news_sm")
                except OSError:
                    _get_nlp._cache = None
        except ImportError:
            _get_nlp._cache = None
    return _get_nlp._cache


# ── Result dataclass ─────────────────────────────────────────────────────────

@dataclass
class PIIDetectionResult:
    has_pii: bool = False
    categories: dict[str, int] = field(default_factory=dict)  # category → count
    persons_detected: list[str] = field(default_factory=list)  # spaCy PER entities (max 20)
    risk_level: str = "low"   # low | medium | high

    @property
    def summary(self) -> dict:
        """Serializable summary for JSONB storage."""
        return {
            "has_pii": self.has_pii,
            "categories": self.categories,
            "persons_count": len(self.persons_detected),
            "risk_level": self.risk_level,
        }


# ── Public API ────────────────────────────────────────────────────────────────

def detect_pii(text: str) -> PIIDetectionResult:
    """
    Classify PII present in *text*. No text modification occurs.

    Detects:
    - Structured PII via regex: CPF, CNPJ, EMAIL, TEL, VALOR
    - Named persons via spaCy NER (PER label) — listed for disclosure only

    Returns PIIDetectionResult with categories, persons list, and risk_level.
    """
    if not text:
        return PIIDetectionResult()

    categories: dict[str, int] = {}

    # Structured PII
    for label, pattern in _STRUCTURED:
        found = pattern.findall(text)
        if found:
            categories[label] = len(found)

    # Named persons via spaCy
    persons: list[str] = []
    nlp = _get_nlp()
    if nlp is not None:
        doc = nlp(text[:_SPACY_MAX_CHARS])
        seen: set[str] = set()
        for ent in doc.ents:
            if ent.label_ == "PER":
                name = ent.text.strip()
                if name and name not in seen:
                    persons.append(name)
                    seen.add(name)
        if persons:
            categories["NOME_PESSOA"] = len(persons)

    has_pii = bool(categories)

    # Risk: high if any identifier (CPF, CNPJ, EMAIL); medium for names/phone/money; low if none
    _high_risk = {"CPF", "CNPJ", "EMAIL"}
    if any(k in _high_risk for k in categories):
        risk_level = "high"
    elif has_pii:
        risk_level = "medium"
    else:
        risk_level = "low"

    return PIIDetectionResult(
        has_pii=has_pii,
        categories=categories,
        persons_detected=persons[:20],
        risk_level=risk_level,
    )
