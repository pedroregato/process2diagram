# core/agent_registry.py
# ─────────────────────────────────────────────────────────────────────────────
# Agent Registry — loads Agent Cards from skills/agent_cards/*.yaml and
# provides a typed interface for the rest of the system.
#
# Usage:
#   from core.agent_registry import get_agent_cards, get_agent_card
#
#   cards = get_agent_cards()          # all cards as list[dict]
#   card  = get_agent_card("bpmn")     # single card or None
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

# yaml is part of PyYAML — already in requirements.txt via streamlit
try:
    import yaml as _yaml
except ImportError:  # pragma: no cover
    _yaml = None  # type: ignore[assignment]

_CARDS_DIR = Path(__file__).parent.parent / "skills" / "agent_cards"


@lru_cache(maxsize=1)
def get_agent_cards() -> list[dict]:
    """Return all agent cards sorted by pipeline_phase then name."""
    if _yaml is None:
        return []
    cards: list[dict] = []
    if not _CARDS_DIR.exists():
        return cards
    for path in sorted(_CARDS_DIR.glob("*.yaml")):
        try:
            with open(path, encoding="utf-8") as fh:
                card = _yaml.safe_load(fh)
            if isinstance(card, dict):
                cards.append(card)
        except Exception:
            pass
    # Sort by phase order then name
    _phase_order = {
        "pre": 0, "core": 1, "enrichment": 2,
        "output": 3, "post": 4, "on_demand": 5,
    }
    cards.sort(key=lambda c: (_phase_order.get(c.get("pipeline_phase", ""), 9), c.get("name", "")))
    return cards


def get_agent_card(name: str) -> Optional[dict]:
    """Return a single agent card by name, or None if not found."""
    for card in get_agent_cards():
        if card.get("name") == name:
            return card
    return None


def get_pipeline_agents() -> list[dict]:
    """Return only agents that run automatically in the pipeline (exclude on_demand)."""
    return [c for c in get_agent_cards() if c.get("pipeline_phase") != "on_demand"]


def get_on_demand_agents() -> list[dict]:
    """Return only on-demand agents (not part of the automatic pipeline)."""
    return [c for c in get_agent_cards() if c.get("pipeline_phase") == "on_demand"]


def format_card_summary(card: dict) -> str:
    """Return a concise single-line summary of an agent card."""
    mode = card.get("mode", "llm")
    phase = card.get("pipeline_phase", "")
    fatal = card.get("fatal", True)
    fatal_tag = "" if fatal else " (não-fatal)"
    artifacts = card.get("artifacts") or []
    art_str = "; ".join(artifacts[:2])
    if len(artifacts) > 2:
        art_str += f" (+{len(artifacts)-2})"
    return (
        f"**{card.get('display_name', card.get('name', ''))}** "
        f"[{mode} · {phase}{fatal_tag}] — {card.get('description', '')}. "
        f"Artefatos: {art_str}."
    )
