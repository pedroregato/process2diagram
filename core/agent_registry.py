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


# ── Governance registry (Read / Draft / Act ladder) ───────────────────────────
#
# authority_level:
#   read   — generates reports only; no persistent side effects
#   draft  — persists artefacts to Supabase; reviewed by humans before
#             any external action
#   act    — performs external actions (calendar, email, webhooks);
#             admin-gated, requires Red-Teaming before production use
#
AGENT_REGISTRY: dict[str, dict] = {
    # ── Read-only ─────────────────────────────────────────────────────────
    "transcript_quality": {
        "authority_level": "read",
        "skill_path": "skills/skill_transcript_quality.md",
        "pipeline_step": 1,
        "default_enabled": True,
        "tags": ["quality", "gate"],
    },
    "communication_noise": {
        "authority_level": "read",
        "skill_path": "skills/skill_communication_noise.md",
        "pipeline_step": 2,
        "default_enabled": True,
        "tags": ["quality"],
    },
    "synthesizer": {
        "authority_level": "read",
        "skill_path": "skills/SKILL_SYNTHESIZER.md",
        "pipeline_step": 8,
        "default_enabled": True,
        "tags": ["report", "html"],
    },
    "query_summarizer": {
        "authority_level": "read",
        "skill_path": "skills/skill_query_summarizer.md",
        "pipeline_step": None,
        "default_enabled": True,
        "tags": ["assistant", "rag"],
    },
    "contradiction_detector": {
        "authority_level": "read",
        "skill_path": "skills/skill_contradiction_detector.md",
        "pipeline_step": None,
        "default_enabled": False,
        "tags": ["analysis", "on-demand"],
    },
    # ── Draft — persists artefacts to Supabase ────────────────────────────
    "bpmn": {
        "authority_level": "draft",
        "skill_path": "skills/skill_bpmn.md",
        "pipeline_step": 3,
        "default_enabled": True,
        "tags": ["diagram", "bpmn"],
    },
    "bpmn_studio": {
        "authority_level": "draft",
        "skill_path": "skills/skill_bpmn.md",
        "pipeline_step": None,
        "default_enabled": True,
        "tags": ["diagram", "bpmn", "on-demand"],
    },
    "minutes": {
        "authority_level": "draft",
        "skill_path": "skills/skill_minutes.md",
        "pipeline_step": 4,
        "default_enabled": True,
        "tags": ["minutes"],
    },
    "requirements": {
        "authority_level": "draft",
        "skill_path": "skills/SKILL_REQUIREMENTS.md",
        "pipeline_step": 4,
        "default_enabled": True,
        "tags": ["requirements", "ieee830"],
    },
    "sbvr": {
        "authority_level": "draft",
        "skill_path": "skills/skill_sbvr.md",
        "pipeline_step": 5,
        "default_enabled": True,
        "tags": ["sbvr", "omg"],
    },
    "bmm": {
        "authority_level": "draft",
        "skill_path": "skills/skill_bmm.md",
        "pipeline_step": 6,
        "default_enabled": True,
        "tags": ["bmm", "omg"],
    },
    "dmn": {
        "authority_level": "draft",
        "skill_path": "skills/skill_dmn.md",
        "pipeline_step": 7,
        "default_enabled": True,
        "tags": ["dmn", "diagram"],
    },
    "argumentation": {
        "authority_level": "draft",
        "skill_path": "skills/skill_argumentation.md",
        "pipeline_step": 7,
        "default_enabled": True,
        "tags": ["ibis", "argumentation"],
    },
    "ckf_updater": {
        "authority_level": "draft",
        "skill_path": "skills/skill_ckf_updater.md",
        "pipeline_step": 9,
        "default_enabled": True,
        "tags": ["ckf"],
    },
    "knowledge_extractor": {
        "authority_level": "draft",
        "skill_path": "skills/skill_knowledge_extractor.md",
        "pipeline_step": None,
        "default_enabled": False,
        "tags": ["knowledge-graph", "on-demand"],
    },
    # ── Act — external side effects (admin-gated) ─────────────────────────
    # Calendar scheduling is currently performed via assistant tools (admin-only),
    # not a dedicated pipeline agent.
}

READ_AGENTS: set[str] = {
    k for k, v in AGENT_REGISTRY.items() if v["authority_level"] == "read"
}
DRAFT_AGENTS: set[str] = {
    k for k, v in AGENT_REGISTRY.items() if v["authority_level"] == "draft"
}
ACTION_AGENTS: set[str] = {
    k for k, v in AGENT_REGISTRY.items() if v["authority_level"] == "act"
}
