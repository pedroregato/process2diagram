# core/lg_pipeline.py
# ─────────────────────────────────────────────────────────────────────────────
# LangGraph-based adaptive BPMN retry loop.
#
# Topology (graph):
#
#   [bpmn_node] → [validate_node] ──┐ score < threshold AND attempts < max
#        ↑_____________________________┘
#                                   └─ score >= threshold OR attempts >= max → END
#
# The graph handles only the BPMN extraction + validation cycle.
# Prerequisites (Quality, Preprocessing, NLP) and downstream agents
# (Minutes, Requirements, SBVR, BMM, Synthesizer) are handled by the existing
# Orchestrator so that all logic stays DRY.
#
# Usage (via core/pipeline.py):
#   runner = LGBPMNRunner(client_info, provider_cfg, config, callback)
#   hub = runner.run(hub, output_language)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import copy
from typing import Optional, Any

from langgraph.graph import StateGraph, END

from core.knowledge_hub import KnowledgeHub, BPMNModel
from agents.agent_bpmn import AgentBPMN
from agents.agent_validator import AgentValidator

try:
    from typing import TypedDict
except ImportError:                      # Python < 3.8 fallback (shouldn't happen on 3.13)
    from typing_extensions import TypedDict  # type: ignore


# ── State definition ──────────────────────────────────────────────────────────

class BPMNLoopState(TypedDict):
    """State passed between LangGraph nodes for the BPMN retry loop."""
    hub: KnowledgeHub
    bpmn_attempts: int
    max_bpmn_retries: int
    validation_threshold: float
    best_hub: Optional[Any]   # KnowledgeHub | None  (Any avoids runtime TypedDict issues)
    best_score: float
    bpmn_weights: dict
    output_language: str


# ── Runner (encapsulates agents + graph via method-bound nodes) ───────────────

class LGBPMNRunner:
    """
    Encapsulates the LangGraph BPMN adaptive-retry loop.

    The graph runs AgentBPMN, scores the result with AgentValidator, and
    retries when the score is below the configured threshold — up to
    max_bpmn_retries total attempts.  After exhausting retries, or when the
    threshold is met, the best-scoring BPMN is committed to hub.bpmn.

    Args:
        client_info:       LLM client dict (from session_security)
        provider_cfg:      Provider configuration dict
        config:            Pipeline config dict (must include bpmn_weights,
                           validation_threshold, max_bpmn_retries)
        progress_callback: Optional (name, status) → None callable
    """

    def __init__(
        self,
        client_info: dict,
        provider_cfg: dict,
        config: dict,
        progress_callback=None,
    ):
        self.agent_bpmn  = AgentBPMN(client_info, provider_cfg)
        self.validator   = AgentValidator()
        self.config      = config
        self._callback   = progress_callback or (lambda n, s: None)

    # ── Progress helper ───────────────────────────────────────────────────────

    def _progress(self, name: str, status: str) -> None:
        self._callback(name, status)

    # ── Graph nodes (bound methods capture self — no extra state key needed) ──

    def _bpmn_node(self, state: BPMNLoopState) -> dict:
        """Run one AgentBPMN pass.  Each attempt resets hub.bpmn."""
        hub = state["hub"]
        attempts = state["bpmn_attempts"] + 1
        max_r    = state["max_bpmn_retries"]
        self._progress("Agente BPMN (LG)", f"attempt {attempts}/{max_r}…")

        hub_copy       = copy.copy(hub)
        hub_copy.bpmn  = BPMNModel()
        hub_copy       = self.agent_bpmn.run(hub_copy, state["output_language"])
        self._progress("Agente BPMN (LG)", "done")

        return {"hub": hub_copy, "bpmn_attempts": attempts}

    def _validate_node(self, state: BPMNLoopState) -> dict:
        """Score the latest BPMN; keep track of the best candidate."""
        hub     = state["hub"]
        weights = state["bpmn_weights"]

        score = self.validator.score(hub.bpmn, hub.transcript_clean, weights)
        self._progress("Validação BPMN (LG)", f"score = {score.weighted:.1f}")

        best_hub   = state.get("best_hub")
        best_score = state.get("best_score", -1.0)

        if best_hub is None or score.weighted > best_score:
            best_hub   = hub
            best_score = score.weighted

        return {"best_hub": best_hub, "best_score": best_score}

    def _should_retry(self, state: BPMNLoopState) -> str:
        """Conditional edge function.  Returns 'retry' or 'proceed'."""
        score     = state.get("best_score", 0.0)
        attempts  = state["bpmn_attempts"]
        threshold = state["validation_threshold"]
        max_r     = state["max_bpmn_retries"]

        if score >= threshold or attempts >= max_r:
            return "proceed"
        return "retry"

    # ── Graph construction ────────────────────────────────────────────────────

    def _build_graph(self):
        """Compile the LangGraph for this runner instance."""
        graph = StateGraph(BPMNLoopState)

        graph.add_node("bpmn",     self._bpmn_node)
        graph.add_node("validate", self._validate_node)

        graph.set_entry_point("bpmn")
        graph.add_edge("bpmn", "validate")
        graph.add_conditional_edges(
            "validate",
            self._should_retry,
            {"retry": "bpmn", "proceed": END},
        )

        return graph.compile()

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self, hub: KnowledgeHub, output_language: str = "Auto-detect") -> KnowledgeHub:
        """
        Execute the adaptive BPMN retry loop.

        Returns the hub with hub.bpmn set to the best-scoring candidate.
        Also writes hub.bpmn.lg_attempts and hub.bpmn.lg_final_score for UI display.
        """
        threshold   = self.config.get("validation_threshold", 6.0)
        max_retries = self.config.get("max_bpmn_retries", 3)
        weights     = self.config.get(
            "bpmn_weights",
            {"granularity": 5, "task_type": 5, "gateways": 5, "structural": 5},
        )

        compiled = self._build_graph()

        initial_state: BPMNLoopState = {
            "hub":                hub,
            "bpmn_attempts":      0,
            "max_bpmn_retries":   max_retries,
            "validation_threshold": threshold,
            "best_hub":           None,
            "best_score":         -1.0,
            "bpmn_weights":       weights,
            "output_language":    output_language,
        }

        final_state = compiled.invoke(initial_state)

        # Commit the best candidate's BPMN to the original hub
        best      = final_state.get("best_hub") or final_state["hub"]
        attempts  = final_state["bpmn_attempts"]
        best_score = final_state.get("best_score", 0.0)

        hub.bpmn = best.bpmn

        # Annotate for UI display
        if hasattr(hub.bpmn, "lg_attempts"):
            hub.bpmn.lg_attempts   = attempts
        if hasattr(hub.bpmn, "lg_final_score"):
            hub.bpmn.lg_final_score = round(best_score, 2)

        hub.bump()

        threshold_met = best_score >= threshold
        status = (
            f"✅ threshold met ({best_score:.1f} ≥ {threshold}) in {attempts} attempt(s)"
            if threshold_met
            else f"⚠️ best score {best_score:.1f} after {attempts} attempt(s)"
        )
        self._progress("Agente BPMN (LG)", status)

        return hub
