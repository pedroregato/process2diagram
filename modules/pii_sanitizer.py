# modules/pii_sanitizer.py
# ─────────────────────────────────────────────────────────────────────────────
# Fase A — PII sanitization before LLM calls.
#
# Replaces structured PII (CPF, CNPJ, email, phone, monetary values) with
# reversible tokens before the text is sent to any external LLM provider.
# The token map is used to restore originals in the LLM response before
# the caller parses the JSON output.
#
# What is sanitized:   CPF, CNPJ, email, phone, monetary values (R$)
# What is NOT touched: personal names (required for BPMN lanes, minutes, IBIS)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class SanitizationResult:
    text: str
    token_map: dict[str, str] = field(default_factory=dict)  # @TOKEN_001 → original


# Patterns ordered from most specific to least specific to avoid partial matches.
# Each entry: (label, compiled_pattern)
_PATTERNS: list[tuple[str, re.Pattern]] = [
    # CNPJ  — must come before CPF (longer number sequence)
    ("CNPJ",  re.compile(r'\b\d{2}\.?\d{3}\.?\d{3}/?\.?\d{4}[-.]?\d{2}\b')),
    # CPF
    ("CPF",   re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}[-.]?\d{2}\b')),
    # Email
    ("EMAIL", re.compile(r'\b[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+\b', re.IGNORECASE)),
    # Brazilian phone  (+55 optional, DDD optional, 8 or 9 digits)
    ("TEL",   re.compile(
        r'(?:(?:\+55\s?)?(?:\(?\d{2}\)?\s?))?(?:9\s?)?\d{4}[-\s]?\d{4}\b'
    )),
    # Monetary value in BRL  — "R$ 1.200,00" / "R$ 5M" / "R$ 2 milhões"
    ("VALOR", re.compile(
        r'R\$\s?[\d.,]+(?:\s?(?:mil(?:h[oõ]es?)?|bi(?:lh[oõ]es?)?|M|k))?',
        re.IGNORECASE,
    )),
]


def sanitize(text: str) -> SanitizationResult:
    """
    Replace PII patterns in *text* with stable tokens.

    Returns a SanitizationResult with:
        .text       — sanitized text (safe to send to LLM)
        .token_map  — dict mapping each token back to the original value
    """
    token_map: dict[str, str] = {}
    counters: dict[str, int] = {}
    # reverse lookup: original → token (to reuse tokens for repeated values)
    _orig_to_token: dict[str, str] = {}

    def _replace(label: str, match: re.Match) -> str:
        original = match.group(0)
        if original in _orig_to_token:
            return _orig_to_token[original]
        counters[label] = counters.get(label, 0) + 1
        token = f"@{label}_{counters[label]:03d}"
        token_map[token] = original
        _orig_to_token[original] = token
        return token

    for label, pattern in _PATTERNS:
        text = pattern.sub(lambda m, lbl=label: _replace(lbl, m), text)

    return SanitizationResult(text=text, token_map=token_map)


def desanitize(text: str, token_map: dict[str, str]) -> str:
    """
    Replace tokens in *text* with their original values using *token_map*.

    Safe to call with an empty map (returns text unchanged).
    """
    if not token_map:
        return text
    for token, original in token_map.items():
        text = text.replace(token, original)
    return text
