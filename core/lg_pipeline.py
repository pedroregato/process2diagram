# core/lg_pipeline.py
# ─────────────────────────────────────────────────────────────────────────────
# LangGraph-based adaptive retry runners.
#
# ── LGBPMNRunner (v4.10) ──────────────────────────────────────────────────
# Topology:
#   [bpmn_node] → [validate_node] ──retry──→ [bpmn_node]
#                                 └─proceed──→ END
#
# Handles only the BPMN extraction + validation cycle.
# Prerequisites and downstream agents handled by Orchestrator.
#
# ── LGFullPipelineRunner (v4.28) ──────────────────────────────────────────
# Topology:
#   [bpmn] → [validate_bpmn] ──retry──→ [bpmn]
#                              └─proceed──→ [commit_bpmn]
#                                               │
#                                          [minutes] → [validate_minutes] ──retry──→ [minutes]
#                                                                           └─proceed──→ [requirements]
#                                                        [requirements] → [validate_req] ──retry──→ [requirements]
#                                                                                        └─proceed──→ [coordinator]
#                                                                                             │
#                                                                                            END
#
# Handles BPMN + Minutes + Requirements retry loops plus a cross-agent
# coordinator that detects lane/participant mismatches and coverage gaps.
# Downstream agents (SBVR, BMM, DMN, Argumentation, Synthesizer) are still
# run by Orchestrator after this runner completes.
#
# Usage (via core/pipeline.py):
#   runner = LGBPMNRunner(client_info, provider_cfg, config, callback)
#   hub = runner.run(hub, output_language)
#
#   runner = LGFullPipelineRunner(client_info, provider_cfg, config, callback)
#   hub = runner.run(hub, output_language)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import copy
import re
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


# ══════════════════════════════════════════════════════════════════════════════
# LGFullPipelineRunner — adaptive retry for BPMN + Minutes + Requirements
# ══════════════════════════════════════════════════════════════════════════════

class LGFullPipelineState(TypedDict):
    """State passed between nodes in the full-pipeline LangGraph."""
    hub: KnowledgeHub
    # BPMN retry
    bpmn_attempts: int
    max_bpmn_retries: int
    bpmn_best_hub: Optional[Any]
    bpmn_best_score: float
    # Minutes retry
    minutes_attempts: int
    max_minutes_retries: int
    # Requirements retry
    req_attempts: int
    max_req_retries: int
    # Shared config
    validation_threshold: float
    bpmn_weights: dict
    output_language: str
    # Feature flags
    run_minutes: bool
    run_requirements: bool


class LGFullPipelineRunner:
    """
    Full-pipeline LangGraph runner: BPMN adaptive retry → Minutes retry →
    Requirements retry → cross-agent coordinator.

    Extends LGBPMNRunner by adding:
    - AgentMinutes retry loop (re-runs if participants/decisions are absent)
    - AgentRequirements retry loop (re-runs if requirement count is too low)
    - Coordinator node: detects BPMN lane ↔ participant mismatches and
      coverage gaps; writes notes to hub.validation.lg_coordination_notes

    The runner does NOT execute SBVR, BMM, DMN, Argumentation or Synthesizer —
    those remain in the Orchestrator, called after runner.run() returns.

    Args:
        client_info:       LLM client dict (from session_security)
        provider_cfg:      Provider configuration dict
        config:            Pipeline config dict
        progress_callback: Optional (name, status) → None callable
    """

    # ── Thresholds (can be overridden via config) ──────────────────────────────
    _MIN_PARTICIPANTS  = 1   # minutes ok if ≥ this many participants extracted
    _MIN_DECISIONS_AI  = 1   # minutes ok if decisions + action_items ≥ this
    _MIN_REQUIREMENTS  = 2   # requirements ok if ≥ this many items extracted
    _REQ_PER_500_WORDS = 2   # expected minimum requirements per 500 transcript words

    def __init__(
        self,
        client_info: dict,
        provider_cfg: dict,
        config: dict,
        progress_callback=None,
    ):
        self.agent_bpmn         = AgentBPMN(client_info, provider_cfg)
        self.validator          = AgentValidator()
        self.client_info        = client_info
        self.provider_cfg       = provider_cfg
        self.config             = config
        self._callback          = progress_callback or (lambda n, s: None)

        # Lazy-import agents (only instantiate if enabled)
        self._agent_minutes     = None
        self._agent_req         = None

    def _progress(self, name: str, status: str) -> None:
        self._callback(name, status)

    def _get_minutes_agent(self):
        if self._agent_minutes is None:
            from agents.agent_minutes import AgentMinutes
            self._agent_minutes = AgentMinutes(self.client_info, self.provider_cfg)
        return self._agent_minutes

    def _get_req_agent(self):
        if self._agent_req is None:
            from agents.agent_requirements import AgentRequirements
            self._agent_req = AgentRequirements(self.client_info, self.provider_cfg)
        return self._agent_req

    # ── BPMN nodes (same logic as LGBPMNRunner) ────────────────────────────────

    def _bpmn_node(self, state: LGFullPipelineState) -> dict:
        hub      = state["hub"]
        attempts = state["bpmn_attempts"] + 1
        max_r    = state["max_bpmn_retries"]
        self._progress("Agente BPMN (LG)", f"tentativa {attempts}/{max_r}…")

        hub_copy      = copy.copy(hub)
        hub_copy.bpmn = BPMNModel()
        hub_copy      = self.agent_bpmn.run(hub_copy, state["output_language"])
        self._progress("Agente BPMN (LG)", "concluído")

        return {"hub": hub_copy, "bpmn_attempts": attempts}

    def _validate_bpmn_node(self, state: LGFullPipelineState) -> dict:
        hub     = state["hub"]
        weights = state["bpmn_weights"]

        score      = self.validator.score(hub.bpmn, hub.transcript_clean, weights)
        best_hub   = state.get("bpmn_best_hub")
        best_score = state.get("bpmn_best_score", -1.0)

        if best_hub is None or score.weighted > best_score:
            best_hub   = hub
            best_score = score.weighted

        self._progress("Validação BPMN (LG)", f"score = {score.weighted:.1f}")
        return {"bpmn_best_hub": best_hub, "bpmn_best_score": best_score}

    def _should_retry_bpmn(self, state: LGFullPipelineState) -> str:
        score     = state.get("bpmn_best_score", 0.0)
        attempts  = state["bpmn_attempts"]
        threshold = state["validation_threshold"]
        max_r     = state["max_bpmn_retries"]
        return "proceed" if (score >= threshold or attempts >= max_r) else "retry"

    def _commit_bpmn_node(self, state: LGFullPipelineState) -> dict:
        """Commit best BPMN candidate to hub; annotate with LG metadata."""
        best_hub   = state.get("bpmn_best_hub") or state["hub"]
        attempts   = state["bpmn_attempts"]
        best_score = state.get("bpmn_best_score", 0.0)
        threshold  = state["validation_threshold"]

        # Merge best BPMN into the canonical hub (keep minutes/req work already done)
        hub = state["hub"]
        hub.bpmn = best_hub.bpmn
        if hasattr(hub.bpmn, "lg_attempts"):
            hub.bpmn.lg_attempts    = attempts
        if hasattr(hub.bpmn, "lg_final_score"):
            hub.bpmn.lg_final_score = round(best_score, 2)
        hub.bump()

        met = best_score >= threshold
        self._progress(
            "Agente BPMN (LG)",
            f"{'✅' if met else '⚠️'} score {best_score:.1f} em {attempts} tentativa(s)"
        )
        return {"hub": hub}

    # ── Minutes nodes ──────────────────────────────────────────────────────────

    def _minutes_node(self, state: LGFullPipelineState) -> dict:
        if not state["run_minutes"]:
            return {}
        hub      = state["hub"]
        attempts = state["minutes_attempts"] + 1
        self._progress("Agente Ata (LG)", f"tentativa {attempts}…")
        hub = self._get_minutes_agent().run(hub, state["output_language"])
        self._progress("Agente Ata (LG)", "concluído")
        return {"hub": hub, "minutes_attempts": attempts}

    def _validate_minutes_node(self, state: LGFullPipelineState) -> dict:
        if not state["run_minutes"]:
            return {}
        hub = state["hub"]
        n_p  = len(hub.minutes.participants or [])
        n_da = len(hub.minutes.decisions or []) + len(hub.minutes.action_items or [])
        ok   = n_p >= self._MIN_PARTICIPANTS and n_da >= self._MIN_DECISIONS_AI
        self._progress(
            "Validação Ata (LG)",
            f"participantes={n_p} decisões+ações={n_da} → {'ok' if ok else 'reprocessar'}",
        )
        return {}

    def _should_retry_minutes(self, state: LGFullPipelineState) -> str:
        if not state["run_minutes"]:
            return "proceed"
        hub      = state["hub"]
        attempts = state["minutes_attempts"]
        max_r    = state["max_minutes_retries"]
        n_p      = len(hub.minutes.participants or [])
        n_da     = len(hub.minutes.decisions or []) + len(hub.minutes.action_items or [])
        ok       = n_p >= self._MIN_PARTICIPANTS and n_da >= self._MIN_DECISIONS_AI
        return "proceed" if (ok or attempts >= max_r) else "retry"

    # ── Requirements nodes ─────────────────────────────────────────────────────

    def _requirements_node(self, state: LGFullPipelineState) -> dict:
        if not state["run_requirements"]:
            return {}
        hub      = state["hub"]
        attempts = state["req_attempts"] + 1
        self._progress("Agente Requisitos (LG)", f"tentativa {attempts}…")
        hub = self._get_req_agent().run(hub, state["output_language"])
        self._progress("Agente Requisitos (LG)", "concluído")
        return {"hub": hub, "req_attempts": attempts}

    def _validate_req_node(self, state: LGFullPipelineState) -> dict:
        if not state["run_requirements"]:
            return {}
        hub   = state["hub"]
        n_req = len(hub.requirements.requirements or [])
        self._progress("Validação Requisitos (LG)", f"requisitos extraídos = {n_req}")
        return {}

    def _should_retry_req(self, state: LGFullPipelineState) -> str:
        if not state["run_requirements"]:
            return "proceed"
        hub      = state["hub"]
        attempts = state["req_attempts"]
        max_r    = state["max_req_retries"]
        n_req    = len(hub.requirements.requirements or [])
        # Dynamic minimum: 2 per 500 words, floor at _MIN_REQUIREMENTS
        words    = len(hub.transcript_clean.split())
        expected = max(self._MIN_REQUIREMENTS, (words // 500) * self._REQ_PER_500_WORDS)
        ok       = n_req >= expected
        return "proceed" if (ok or attempts >= max_r) else "retry"

    # ── Coordinator node ───────────────────────────────────────────────────────

    def _coordinator_node(self, state: LGFullPipelineState) -> dict:
        """
        Cross-agent consistency check.  Detects:
        1. BPMN lanes not represented in minutes participants (and vice-versa)
        2. Requirements count vs transcript size adequacy
        3. Minutes participants count vs transcript speaker density

        Writes notes to hub.validation.lg_coordination_notes.
        Non-fatal — any exception is swallowed.
        """
        hub   = state["hub"]
        notes = []

        try:
            # ── 1. BPMN lanes ↔ minutes participants ──────────────────────────
            if hub.bpmn.ready and hub.minutes.ready:
                lanes        = {(l.get("name") or "").strip().lower() for l in (hub.bpmn.lanes or [])}
                participants = {(p.get("name") or "").strip().lower() for p in (hub.minutes.participants or [])}

                if lanes and participants:
                    # Build normalized word sets for fuzzy matching
                    def _words(s: str) -> set:
                        return set(re.sub(r"[^a-záàâãéèêíïóôõúüç\s]", "", s).split())

                    for lane in lanes:
                        lane_words = _words(lane)
                        matched = any(
                            lane_words & _words(p) for p in participants
                        )
                        if not matched:
                            notes.append(
                                f"⚠️ Raia BPMN '{lane.title()}' não encontrada nos participantes da ata."
                            )

                    for participant in participants:
                        part_words = _words(participant)
                        matched = any(
                            part_words & _words(l) for l in lanes
                        )
                        if not matched:
                            notes.append(
                                f"ℹ️ Participante '{participant.title()}' não aparece como raia BPMN."
                            )

            # ── 2. Requirements adequacy ──────────────────────────────────────
            if state["run_requirements"]:
                n_req  = len(hub.requirements.requirements or [])
                words  = len(hub.transcript_clean.split())
                expected = max(self._MIN_REQUIREMENTS, (words // 500) * self._REQ_PER_500_WORDS)
                if n_req < expected:
                    notes.append(
                        f"ℹ️ Apenas {n_req} requisito(s) extraído(s); "
                        f"esperado ≥{expected} para transcrição de {words} palavras."
                    )
                else:
                    notes.append(f"✅ {n_req} requisito(s) extraído(s) — cobertura adequada.")

            # ── 3. Minutes retries summary ────────────────────────────────────
            if state["run_minutes"] and state["minutes_attempts"] > 1:
                notes.append(
                    f"ℹ️ Ata reprocessada {state['minutes_attempts']} vez(es) pelo LangGraph."
                )
            if state["run_requirements"] and state["req_attempts"] > 1:
                notes.append(
                    f"ℹ️ Requisitos reprocessados {state['req_attempts']} vez(es) pelo LangGraph."
                )

        except Exception:
            notes.append("⚠️ Coordenação entre agentes falhou silenciosamente.")

        # Write to hub
        hub.validation.lg_coordination_notes = notes
        hub.validation.lg_minutes_retries    = state["minutes_attempts"]
        hub.validation.lg_req_retries        = state["req_attempts"]
        hub.bump()

        if notes:
            self._progress("Coordenador LG", f"{len(notes)} nota(s) gerada(s)")

        return {"hub": hub}

    # ── Graph construction ─────────────────────────────────────────────────────

    def _build_graph(self):
        graph = StateGraph(LGFullPipelineState)

        graph.add_node("bpmn",             self._bpmn_node)
        graph.add_node("validate_bpmn",    self._validate_bpmn_node)
        graph.add_node("commit_bpmn",      self._commit_bpmn_node)
        graph.add_node("minutes",          self._minutes_node)
        graph.add_node("validate_minutes", self._validate_minutes_node)
        graph.add_node("requirements",     self._requirements_node)
        graph.add_node("validate_req",     self._validate_req_node)
        graph.add_node("coordinator",      self._coordinator_node)

        graph.set_entry_point("bpmn")
        graph.add_edge("bpmn", "validate_bpmn")
        graph.add_conditional_edges(
            "validate_bpmn",
            self._should_retry_bpmn,
            {"retry": "bpmn", "proceed": "commit_bpmn"},
        )
        graph.add_edge("commit_bpmn",      "minutes")
        graph.add_edge("minutes",          "validate_minutes")
        graph.add_conditional_edges(
            "validate_minutes",
            self._should_retry_minutes,
            {"retry": "minutes", "proceed": "requirements"},
        )
        graph.add_edge("requirements",     "validate_req")
        graph.add_conditional_edges(
            "validate_req",
            self._should_retry_req,
            {"retry": "requirements", "proceed": "coordinator"},
        )
        graph.add_edge("coordinator", END)

        return graph.compile()

    # ── Public API ─────────────────────────────────────────────────────────────

    def run(
        self,
        hub: KnowledgeHub,
        output_language: str = "Auto-detect",
        run_minutes: bool = True,
        run_requirements: bool = True,
    ) -> KnowledgeHub:
        """
        Execute BPMN retry → Minutes retry → Requirements retry → Coordinator.

        Returns hub with hub.bpmn, hub.minutes, hub.requirements populated
        (subject to feature flags) and hub.validation.lg_coordination_notes set.
        """
        threshold        = self.config.get("validation_threshold", 6.0)
        max_bpmn_retries = self.config.get("max_bpmn_retries", 3)
        max_minutes_r    = self.config.get("max_minutes_retries", 2)
        max_req_r        = self.config.get("max_req_retries", 2)
        weights          = self.config.get(
            "bpmn_weights",
            {"granularity": 5, "task_type": 5, "gateways": 5, "structural": 5},
        )

        compiled = self._build_graph()

        initial_state: LGFullPipelineState = {
            "hub":                hub,
            "bpmn_attempts":      0,
            "max_bpmn_retries":   max_bpmn_retries,
            "bpmn_best_hub":      None,
            "bpmn_best_score":    -1.0,
            "minutes_attempts":   0,
            "max_minutes_retries": max_minutes_r,
            "req_attempts":       0,
            "max_req_retries":    max_req_r,
            "validation_threshold": threshold,
            "bpmn_weights":       weights,
            "output_language":    output_language,
            "run_minutes":        run_minutes,
            "run_requirements":   run_requirements,
        }

        final_state = compiled.invoke(initial_state)
        return final_state["hub"]
