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
# ── LGFullPipelineRunner (v4.29) ──────────────────────────────────────────
# Topology:
#   [bpmn] → [validate_bpmn] ──retry──→ [bpmn]
#                              └─proceed──→ [commit_bpmn]
#                                               │
#                                          [minutes] → [validate_minutes] ──retry──→ [minutes]
#                                                                           └─proceed──→ [requirements]
#                                                        [requirements] → [validate_req] ──retry──→ [requirements]
#                                                                                        └─proceed──→ [coordinator]
#                                                                                                         │
#                                                           ┌──────────────────────────────────────────── coordinator
#                                                           │  (A2A delegation — round 0 only)
#                                                    [delegate_bpmn]  ─┐
#                                                    [delegate_minutes] ┼──→ coordinator (round 1) → END
#                                                    [delegate_req]    ─┘
#
# A2A Delegation (v4.29): after coordinator analysis, if cross-agent issues are
# detected, the coordinator delegates to the affected agent with a context hint
# injected into the system prompt via BaseAgent._lg_delegation_hint.
# Only 1 delegation round per session (max_delegation_rounds=1 default).
#
# Delegation triggers (priority order):
#   1. bpmn      — ≥2 BPMN lanes have no matching minutes participant
#   2. requirements — BPMN gateways > n_req / 2 (insufficient business rules)
#   3. minutes   — BPMN gateways > minutes.decisions count
#
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
        hub      = state["hub"]
        attempts = state["bpmn_attempts"] + 1
        max_r    = state["max_bpmn_retries"]
        self._progress("Agente BPMN (LG)", f"running (tentativa {attempts}/{max_r})")

        hub_copy      = copy.copy(hub)
        hub_copy.bpmn = BPMNModel()
        # Skip cache on retries so each attempt produces a fresh LLM response
        self.agent_bpmn._lg_skip_cache = (attempts > 1)
        hub_copy = self.agent_bpmn.run(hub_copy, state["output_language"])
        self.agent_bpmn._lg_skip_cache = False
        self._progress("Agente BPMN (LG)", "done")

        return {"hub": hub_copy, "bpmn_attempts": attempts}

    def _validate_node(self, state: BPMNLoopState) -> dict:
        """Score the latest BPMN; keep track of the best candidate."""
        hub     = state["hub"]
        weights = state["bpmn_weights"]

        score = self.validator.score(hub.bpmn, hub.transcript_clean, weights)
        self._progress("Validação BPMN (LG)", f"done (score {score.weighted:.1f})")

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
    # A2A delegation (v4.29)
    delegation_hints: dict        # {agent_name: hint_text} set by coordinator
    delegation_rounds: int        # incremented after each delegation node runs
    max_delegation_rounds: int    # cap (default 1 — single delegation pass)
    delegation_log: list          # [{agent, summary}] for UI display


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
        self._progress("Agente BPMN (LG)", f"running (tentativa {attempts}/{max_r})")

        hub_copy      = copy.copy(hub)
        hub_copy.bpmn = BPMNModel()
        # Skip cache on retries — guarantees a fresh LLM call each attempt
        self.agent_bpmn._lg_skip_cache = (attempts > 1)
        hub_copy = self.agent_bpmn.run(hub_copy, state["output_language"])
        self.agent_bpmn._lg_skip_cache = False
        self._progress("Agente BPMN (LG)", "done")

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

        self._progress("Validação BPMN (LG)", f"done (score {score.weighted:.1f})")
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

        hub = state["hub"]
        hub.bpmn = best_hub.bpmn
        if hasattr(hub.bpmn, "lg_attempts"):
            hub.bpmn.lg_attempts    = attempts
        if hasattr(hub.bpmn, "lg_final_score"):
            hub.bpmn.lg_final_score = round(best_score, 2)
        hub.bump()

        met = best_score >= threshold
        verdict = "threshold atingido" if met else "melhor candidato selecionado"
        self._progress("Agente BPMN (LG)", f"done ({verdict}: score {best_score:.1f})")
        return {"hub": hub}

    # ── Minutes nodes ──────────────────────────────────────────────────────────

    def _minutes_node(self, state: LGFullPipelineState) -> dict:
        if not state["run_minutes"]:
            return {}
        hub      = state["hub"]
        attempts = state["minutes_attempts"] + 1
        self._progress("Agente Ata (LG)", f"running (tentativa {attempts})")
        agent = self._get_minutes_agent()
        agent._lg_skip_cache = (attempts > 1)
        hub = agent.run(hub, state["output_language"])
        agent._lg_skip_cache = False
        self._progress("Agente Ata (LG)", "done")
        return {"hub": hub, "minutes_attempts": attempts}

    def _validate_minutes_node(self, state: LGFullPipelineState) -> dict:
        if not state["run_minutes"]:
            return {}
        hub = state["hub"]
        n_p  = len(hub.minutes.participants or [])
        n_da = len(hub.minutes.decisions or []) + len(hub.minutes.action_items or [])
        ok   = n_p >= self._MIN_PARTICIPANTS and n_da >= self._MIN_DECISIONS_AI
        verdict = "ok" if ok else "reprocessar"
        self._progress(
            "Validação Ata (LG)",
            f"done (participantes={n_p} decisões+ações={n_da} → {verdict})",
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
        self._progress("Agente Requisitos (LG)", f"running (tentativa {attempts})")
        agent = self._get_req_agent()
        agent._lg_skip_cache = (attempts > 1)
        hub = agent.run(hub, state["output_language"])
        agent._lg_skip_cache = False
        self._progress("Agente Requisitos (LG)", "done")
        return {"hub": hub, "req_attempts": attempts}

    def _validate_req_node(self, state: LGFullPipelineState) -> dict:
        if not state["run_requirements"]:
            return {}
        hub   = state["hub"]
        n_req = len(hub.requirements.requirements or [])
        self._progress("Validação Requisitos (LG)", f"done ({n_req} requisito(s))")
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

    @staticmethod
    def _bpmn_gateways(hub: KnowledgeHub) -> list:
        """Return all gateway steps from the BPMN model (flat or collaboration)."""
        _GW = {"exclusiveGateway", "parallelGateway", "inclusiveGateway",
               "eventBasedGateway", "complexGateway", "gateway"}
        if hub.bpmn.is_collaboration and hub.bpmn.pool_models:
            steps = [s for pool in hub.bpmn.pool_models for s in pool.steps]
        else:
            steps = list(hub.bpmn.steps or [])
        return [s for s in steps if s.task_type in _GW]

    def _coordinator_node(self, state: LGFullPipelineState) -> dict:
        """
        Cross-agent consistency check + A2A delegation decision.

        Analysis:
        1. BPMN lanes ↔ minutes participants mismatch
        2. Requirements adequacy vs transcript length
        3. Gateway count vs requirements / decisions (triggers delegation)

        Delegation (round 0 only — capped by max_delegation_rounds):
        - Priority 1 bpmn:          ≥2 lanes without a matching participant
        - Priority 2 requirements:  gateways × 2 > n_req (missing business rules)
        - Priority 3 minutes:       gateways > n_decisions (missing decisions)

        Non-fatal — any exception is swallowed.
        """
        hub              = state["hub"]
        notes: list[str] = []
        delegation_hints: dict = {}
        rounds   = state.get("delegation_rounds", 0)
        max_del  = state.get("max_delegation_rounds", 1)

        # Word normaliser for fuzzy lane ↔ participant matching
        def _words(s: str) -> set:
            return set(re.sub(r"[^a-záàâãéèêíïóôõúüç\s]", "", s.lower()).split())

        unmatched_lanes: list[str] = []
        unmatched_parts: list[str] = []
        lanes_set: set  = set()
        parts_set: set  = set()

        try:
            # ── 1. BPMN lanes ↔ minutes participants ──────────────────────────
            if hub.bpmn.ready and hub.minutes.ready:
                lanes_set = {
                    (l.get("name") or "").strip().lower()
                    for l in (hub.bpmn.lanes or [])
                }
                parts_set = {
                    (p.get("name") or "").strip().lower()
                    for p in (hub.minutes.participants or [])
                }

                if lanes_set and parts_set:
                    for lane in lanes_set:
                        matched = any(_words(lane) & _words(p) for p in parts_set)
                        if not matched:
                            unmatched_lanes.append(lane)
                            notes.append(
                                f"⚠️ Raia BPMN '{lane.title()}' não encontrada nos participantes da ata."
                            )
                    for part in parts_set:
                        matched = any(_words(part) & _words(l) for l in lanes_set)
                        if not matched:
                            unmatched_parts.append(part)
                            notes.append(
                                f"ℹ️ Participante '{part.title()}' não aparece como raia BPMN."
                            )

            # ── 2. Requirements adequacy ──────────────────────────────────────
            n_req = 0
            if state["run_requirements"]:
                n_req  = len(hub.requirements.requirements or [])
                words  = len(hub.transcript_clean.split())
                expected = max(self._MIN_REQUIREMENTS, (words // 500) * self._REQ_PER_500_WORDS)
                if n_req < expected:
                    notes.append(
                        f"ℹ️ Apenas {n_req} requisito(s); esperado ≥{expected} "
                        f"para transcrição de {words} palavras."
                    )
                else:
                    notes.append(f"✅ {n_req} requisito(s) — cobertura adequada.")

            # ── 3. Retry summary ──────────────────────────────────────────────
            if state["run_minutes"] and state["minutes_attempts"] > 1:
                notes.append(
                    f"ℹ️ Ata reprocessada {state['minutes_attempts']} vez(es) pelo LangGraph."
                )
            if state["run_requirements"] and state["req_attempts"] > 1:
                notes.append(
                    f"ℹ️ Requisitos reprocessados {state['req_attempts']} vez(es) pelo LangGraph."
                )

            # ── 4. A2A Delegation decision ────────────────────────────────────
            if rounds < max_del and hub.bpmn.ready:
                gateways = self._bpmn_gateways(hub)

                # Priority 1 — BPMN ← Coordinator: lanes without participants
                if len(unmatched_lanes) >= 2:
                    parts_str = ", ".join(p.title() for p in sorted(parts_set)[:8])
                    missing_str = ", ".join(l.title() for l in unmatched_lanes[:5])
                    delegation_hints["bpmn"] = (
                        "[DELEGAÇÃO: Coordenador→AgentBPMN]\n"
                        "A Ata de Reunião identificou participantes não representados como lanes.\n\n"
                        f"Participantes na ata: {parts_str or 'N/D'}\n"
                        f"Lanes sem correspondência: {missing_str}\n\n"
                        "Revise a transcrição e certifique-se de que TODOS os participantes da ata "
                        "sejam representados como lanes. Preserve o fluxo já identificado; apenas "
                        "adicione lanes ausentes e reposicione atividades conforme necessário."
                    )
                    notes.append(
                        f"→ Delegando ao AgentBPMN: {len(unmatched_lanes)} raia(s) sem "
                        "participante correspondente na ata."
                    )

                # Priority 2 — Requirements ← Coordinator: gateways suggest more business rules
                elif gateways and state["run_requirements"] and n_req < len(gateways) * 2:
                    gw_list = "\n".join(
                        f"  • {s.title} ({s.task_type})" for s in gateways[:8]
                    )
                    expected_from_gw = len(gateways) * 2
                    delegation_hints["requirements"] = (
                        "[DELEGAÇÃO: Coordenador→AgentRequirements]\n"
                        f"O BPMN contém {len(gateways)} gateway(s) de decisão, mas apenas "
                        f"{n_req} requisito(s) foram extraídos (esperado ≥{expected_from_gw}).\n\n"
                        "Gateways representam critérios de decisão que devem originar requisitos "
                        "do tipo business_rule ou constraint.\n\n"
                        f"Pontos de decisão identificados:\n{gw_list}\n\n"
                        "Para cada gateway, extraia: o critério que governa a decisão, "
                        "as condições de cada caminho (ex: 'Valor < R$500k', 'Aprovado') "
                        "e quaisquer restrições implícitas na transcrição."
                    )
                    notes.append(
                        f"→ Delegando ao AgentRequirements: {len(gateways)} gateway(s) "
                        f"sugere(m) ≥{expected_from_gw} requisitos, encontrados {n_req}."
                    )

                # Priority 3 — Minutes ← Coordinator: gateways suggest missing decisions
                elif gateways and state["run_minutes"] and hub.minutes.ready:
                    n_dec = len(hub.minutes.decisions or [])
                    if n_dec < len(gateways):
                        gw_list = "\n".join(f"  • {s.title}" for s in gateways[:8])
                        delegation_hints["minutes"] = (
                            "[DELEGAÇÃO: Coordenador→AgentMinutes]\n"
                            f"O BPMN contém {len(gateways)} ponto(s) de decisão (gateway), "
                            f"mas a ata registrou apenas {n_dec} decisão(ões) formal(is).\n\n"
                            f"Pontos de decisão no BPMN:\n{gw_list}\n\n"
                            "Revise a transcrição focando nesses pontos e extraia as decisões "
                            "e encaminhamentos associados a cada gateway."
                        )
                        notes.append(
                            f"→ Delegando ao AgentMinutes: {len(gateways)} gateway(s) "
                            f"mas apenas {n_dec} decisão(ões) na ata."
                        )

        except Exception:
            notes.append("⚠️ Coordenação entre agentes falhou silenciosamente.")

        hub.validation.lg_coordination_notes = notes
        hub.validation.lg_minutes_retries    = state["minutes_attempts"]
        hub.validation.lg_req_retries        = state["req_attempts"]
        hub.bump()

        n_del = len(delegation_hints)
        suffix = f", {n_del} delegação(ões)" if n_del else ""
        self._progress("Coordenador LG", f"done ({len(notes)} nota(s){suffix})")
        return {"hub": hub, "delegation_hints": delegation_hints}

    # ── A2A delegation nodes ────────────────────────────────────────────────────

    def _node_delegate_bpmn(self, state: LGFullPipelineState) -> dict:
        """Re-run AgentBPMN with coordinator context injected into system prompt."""
        hub   = state["hub"]
        hint  = state.get("delegation_hints", {}).get("bpmn", "")
        rounds = state.get("delegation_rounds", 0)

        self._progress("Agente BPMN (Delegação A2A)", "running")
        hub_copy      = copy.copy(hub)
        hub_copy.bpmn = BPMNModel()
        self.agent_bpmn._lg_delegation_hint = hint
        self.agent_bpmn._lg_skip_cache      = True
        try:
            hub_copy = self.agent_bpmn.run(hub_copy, state["output_language"])
        finally:
            self.agent_bpmn._lg_delegation_hint = ""
            self.agent_bpmn._lg_skip_cache      = False

        hub.bpmn = hub_copy.bpmn
        hub.meta.total_tokens_used = hub_copy.meta.total_tokens_used
        hub.bump()
        self._progress("Agente BPMN (Delegação A2A)", "done")

        log = list(state.get("delegation_log", []))
        log.append({"agent": "bpmn", "summary": "lanes ↔ participantes da ata"})
        hub.validation.lg_delegation_log = log
        return {
            "hub": hub,
            "delegation_rounds": rounds + 1,
            "delegation_hints":  {},
            "delegation_log":    log,
        }

    def _node_delegate_minutes(self, state: LGFullPipelineState) -> dict:
        """Re-run AgentMinutes with coordinator context injected into system prompt."""
        hub   = state["hub"]
        hint  = state.get("delegation_hints", {}).get("minutes", "")
        rounds = state.get("delegation_rounds", 0)

        self._progress("Agente Ata (Delegação A2A)", "running")
        agent = self._get_minutes_agent()
        agent._lg_delegation_hint = hint
        agent._lg_skip_cache      = True
        try:
            hub = agent.run(hub, state["output_language"])
        finally:
            agent._lg_delegation_hint = ""
            agent._lg_skip_cache      = False

        self._progress("Agente Ata (Delegação A2A)", "done")

        log = list(state.get("delegation_log", []))
        log.append({"agent": "minutes", "summary": "gateways BPMN ↔ decisões da ata"})
        hub.validation.lg_delegation_log = log
        return {
            "hub": hub,
            "delegation_rounds": rounds + 1,
            "delegation_hints":  {},
            "delegation_log":    log,
        }

    def _node_delegate_req(self, state: LGFullPipelineState) -> dict:
        """Re-run AgentRequirements with coordinator context injected into system prompt."""
        hub   = state["hub"]
        hint  = state.get("delegation_hints", {}).get("requirements", "")
        rounds = state.get("delegation_rounds", 0)

        self._progress("Agente Requisitos (Delegação A2A)", "running")
        agent = self._get_req_agent()
        agent._lg_delegation_hint = hint
        agent._lg_skip_cache      = True
        try:
            hub = agent.run(hub, state["output_language"])
        finally:
            agent._lg_delegation_hint = ""
            agent._lg_skip_cache      = False

        self._progress("Agente Requisitos (Delegação A2A)", "done")

        log = list(state.get("delegation_log", []))
        log.append({"agent": "requirements", "summary": "gateways BPMN → regras de negócio"})
        hub.validation.lg_delegation_log = log
        return {
            "hub": hub,
            "delegation_rounds": rounds + 1,
            "delegation_hints":  {},
            "delegation_log":    log,
        }

    def _route_coordinator(self, state: LGFullPipelineState) -> str:
        """Route coordinator output: to a delegation node or END."""
        hints  = state.get("delegation_hints", {})
        rounds = state.get("delegation_rounds", 0)
        max_d  = state.get("max_delegation_rounds", 1)

        if rounds >= max_d or not hints:
            return "end"
        if "bpmn" in hints:
            return "delegate_bpmn"
        if "requirements" in hints:
            return "delegate_req"
        if "minutes" in hints:
            return "delegate_minutes"
        return "end"

    # ── Graph construction ─────────────────────────────────────────────────────

    def _build_graph(self):
        graph = StateGraph(LGFullPipelineState)

        # ── Core pipeline nodes ───────────────────────────────────────────────
        graph.add_node("bpmn",             self._bpmn_node)
        graph.add_node("validate_bpmn",    self._validate_bpmn_node)
        graph.add_node("commit_bpmn",      self._commit_bpmn_node)
        graph.add_node("minutes",          self._minutes_node)
        graph.add_node("validate_minutes", self._validate_minutes_node)
        graph.add_node("requirements",     self._requirements_node)
        graph.add_node("validate_req",     self._validate_req_node)
        graph.add_node("coordinator",      self._coordinator_node)

        # ── A2A delegation nodes ──────────────────────────────────────────────
        graph.add_node("delegate_bpmn",    self._node_delegate_bpmn)
        graph.add_node("delegate_minutes", self._node_delegate_minutes)
        graph.add_node("delegate_req",     self._node_delegate_req)

        # ── Pipeline edges ────────────────────────────────────────────────────
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

        # ── Coordinator → delegation or END ───────────────────────────────────
        graph.add_conditional_edges(
            "coordinator",
            self._route_coordinator,
            {
                "delegate_bpmn":    "delegate_bpmn",
                "delegate_minutes": "delegate_minutes",
                "delegate_req":     "delegate_req",
                "end":              END,
            },
        )

        # ── Delegation → coordinator (round+1 will route to END) ──────────────
        graph.add_edge("delegate_bpmn",    "coordinator")
        graph.add_edge("delegate_minutes", "coordinator")
        graph.add_edge("delegate_req",     "coordinator")

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

        max_delegation = self.config.get("max_delegation_rounds", 1)

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
            # A2A delegation
            "delegation_hints":        {},
            "delegation_rounds":       0,
            "max_delegation_rounds":   max_delegation,
            "delegation_log":          [],
        }

        final_state = compiled.invoke(initial_state)
        return final_state["hub"]
