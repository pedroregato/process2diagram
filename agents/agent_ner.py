# agents/agent_ner.py
# ─────────────────────────────────────────────────────────────────────────────
# AgentNER — LLM-based Named Entity Recognition for meeting transcripts.
#
# Extracts PESSOA, AREA, UNIDADE, CARGO entities by sending transcript chunks
# to the configured LLM and parsing the structured JSON response.
#
# Used standalone (not in Orchestrator) — instantiated directly by
# pages/EntityRecognition.py and core/assistant_tools.py.
# Token tracking uses a transient KnowledgeHub per extraction run.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import re
import unicodedata

from agents.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub

_CHUNK_SIZE    = 5_000   # characters per chunk sent to LLM
_CHUNK_OVERLAP = 300     # overlap between consecutive chunks

_VALID_TYPES = {"PESSOA", "AREA", "UNIDADE", "CARGO"}


class AgentNER(BaseAgent):
    """
    LLM-based NER agent.

    Primary interface: extract_entities(text) -> (entities, tokens_used)

    Each entity dict contains:
      text, type, normalized, confidence, context, source, start, end
    """

    name       = "ner"
    skill_path = "skills/skill_ner.md"

    # ── BaseAgent abstract interface (not used in main pipeline) ──────────────

    def build_prompt(self, hub: KnowledgeHub, output_language: str = "Auto-detect"):
        return self._skill, ""

    def run(self, hub: KnowledgeHub, output_language: str = "Auto-detect") -> KnowledgeHub:
        return hub

    # ── Main extraction interface ─────────────────────────────────────────────

    def extract_entities(self, text: str) -> tuple[list[dict], int]:
        """
        Extract entities from text, chunking as needed.

        Returns:
            (entities, total_tokens_used)
            Each entity: {text, type, normalized, confidence, context, source, start, end}
        """
        chunks     = _make_chunks(text)
        raw_items: list[dict] = []
        hub        = KnowledgeHub.new()   # single hub for token tracking

        for chunk in chunks:
            user_prompt = f"Transcrição de reunião (trecho):\n\n{chunk}"
            try:
                raw = self._call_llm(self._skill, user_prompt, hub)
                raw_items.extend(_parse_entity_json(raw))
            except Exception:
                continue

        entities = _normalize_and_dedup(raw_items)
        return entities, hub.meta.total_tokens_used


# ── Module-level helpers ──────────────────────────────────────────────────────

def _make_chunks(text: str) -> list[str]:
    """Split text into overlapping fixed-size chunks."""
    if len(text) <= _CHUNK_SIZE:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        chunks.append(text[start: start + _CHUNK_SIZE])
        start += _CHUNK_SIZE - _CHUNK_OVERLAP
    return chunks


def _parse_entity_json(raw: str) -> list[dict]:
    """Extract and validate the JSON array from an LLM response."""
    clean = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).strip().rstrip("`").strip()
    start = clean.find("[")
    end   = clean.rfind("]") + 1
    if start == -1 or end == 0:
        return []
    try:
        items = json.loads(clean[start:end])
    except Exception:
        return []
    return [
        item for item in items
        if isinstance(item, dict)
        and (item.get("text") or "").strip()
        and item.get("type") in _VALID_TYPES
    ]


def _normalize_text(text: str) -> str:
    """Remove accents and convert to uppercase."""
    nfd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfd if not unicodedata.combining(c)).upper().strip()


def _normalize_and_dedup(items: list[dict]) -> list[dict]:
    """
    Normalize entity text and deduplicate by (normalized_name, type).
    When duplicates exist, keep the entry with the longest context.
    """
    seen: dict[tuple, dict] = {}
    for item in items:
        text = (item.get("text") or "").strip()
        if len(text) < 3:
            continue
        entity_type = item.get("type", "")
        normalized  = _normalize_text(text)
        key         = (normalized, entity_type)
        context     = (item.get("context") or "")[:150]

        if key not in seen or len(context) > len(seen[key]["context"]):
            seen[key] = {
                "text":        text,
                "type":        entity_type,
                "normalized":  normalized,
                "confidence":  0.9,
                "context":     context,
                "source":      "llm",
                "start":       0,
                "end":         0,
            }
    return list(seen.values())
