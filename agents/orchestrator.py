# agents/orchestrator.py
# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator — PC1 implementation.
#
# PC1 pipeline (sequential for Streamlit compatibility):
#   0. AgentTranscriptQuality → hub.transcript_quality  (quality gate)
#   1. NLPChunker             → hub.nlp
#   2. AgentBPMN              → hub.bpmn
#   3. AgentMinutes           → hub.minutes
#   4. AgentRequirements      → hub.requirements
#
# PC2 upgrade path:
#   - Replace sequential calls with asyncio.gather() for parallel execution
#   - Add AgentSBVR, AgentBMM, AgentDecisionLog, AgentSLA
#   - Add AgentValidator after all specialists complete
#   - Integrate LangGraph for conditional re-routing on validation failures
#
# Progress reporting:
#   - Accepts optional callback(step_name, status) for Streamlit progress bar
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from typing import Callable, Optional

from agents.nlp_chunker import NLPChunker
from agents.agent_bpmn import AgentBPMN
from agents.agent_minutes import AgentMinutes
from agents.agent_requirements import AgentRequirements
from agents.agent_transcript_quality import AgentTranscriptQuality
from core.knowledge_hub import KnowledgeHub


# Type alias for progress callbacks
ProgressCallback = Callable[[str, str], None]   # (step_name, status) → None


class Orchestrator:
    """
    PC1 Orchestrator: TranscriptQuality → NLP → BPMN → Minutes → Requirements.

    Usage:
        hub = KnowledgeHub.new()
        hub.set_transcript(raw_text)

        orc = Orchestrator(client_info, provider_cfg)
        hub = orc.run(hub, output_language="Portuguese (BR)")
    """

    # Agent execution plan for PC1
    _PLAN = ["transcript_quality", "nlp", "bpmn", "minutes", "requirements"]

    def __init__(
        self,
        client_info: dict,
        provider_cfg: dict,
        progress_callback: Optional[ProgressCallback] = None,
    ):
        self.client_info = client_info
        self.provider_cfg = provider_cfg
        self._progress = progress_callback or (lambda name, status: None)

        # Instantiate agents
        self._agent_quality = AgentTranscriptQuality(client_info, provider_cfg)
        self._chunker = NLPChunker()
        self._agent_bpmn = AgentBPMN(client_info, provider_cfg)
        self._agent_minutes = AgentMinutes(client_info, provider_cfg)
        self._agent_requirements = AgentRequirements(client_info, provider_cfg)

    # ── Main entry point ──────────────────────────────────────────────────────

    def run(
        self,
        hub: KnowledgeHub,
        output_language: str = "Auto-detect",
        run_quality: bool = True,
        run_bpmn: bool = True,
        run_minutes: bool = True,
        run_requirements: bool = True,
    ) -> KnowledgeHub:
        """
        Execute PC1 pipeline.

        Args:
            hub:               Initialized KnowledgeHub with transcript set.
            output_language:   Language preference for agent outputs.
            run_quality:       Whether to run the Transcript Quality agent.
            run_bpmn:          Whether to run the BPMN agent.
            run_minutes:       Whether to run the Minutes agent.
            run_requirements:  Whether to run the Requirements agent.

        Returns:
            Populated KnowledgeHub.
        """
        if not hub.transcript_raw:
            raise ValueError("KnowledgeHub has no transcript. Call hub.set_transcript() first.")

        # ── Step 0: Transcript Quality Agent ─────────────────────────────────
        if run_quality:
            self._progress("Agente Qualidade", "running")
            try:
                hub = self._agent_quality.run(hub, output_language)
                self._progress("Agente Qualidade", "done")
            except Exception as exc:
                self._progress("Agente Qualidade", f"error: {exc}")
                # Quality failure is non-fatal — pipeline continues
                hub.bump()

        # ── Step 1: NLP Chunker (no LLM) ─────────────────────────────────────
        self._progress("NLP / Chunker", "running")
        try:
            hub = self._chunker.run(hub)
            self._progress("NLP / Chunker", "done")
        except Exception as exc:
            self._progress("NLP / Chunker", f"error: {exc}")
            # NLP failure is non-fatal — set clean transcript and continue
            hub.transcript_clean = hub.transcript_raw
            hub.bump()

        # ── Step 2: BPMN Agent ────────────────────────────────────────────────
        if run_bpmn:
            self._progress("Agente BPMN", "running")
            try:
                hub = self._agent_bpmn.run(hub, output_language)
                self._progress("Agente BPMN", "done")
            except Exception as exc:
                self._progress("Agente BPMN", f"error: {exc}")
                raise RuntimeError(f"BPMN Agent failed: {exc}") from exc

        # ── Step 3: Minutes Agent ─────────────────────────────────────────────
        if run_minutes:
            self._progress("Agente Ata", "running")
            try:
                hub = self._agent_minutes.run(hub, output_language)
                self._progress("Agente Ata", "done")
            except Exception as exc:
                self._progress("Agente Ata", f"error: {exc}")
                raise RuntimeError(f"Minutes Agent failed: {exc}") from exc

        # ── Step 4: Requirements Agent ────────────────────────────────────────
        if run_requirements:
            self._progress("Agente Requisitos", "running")
            try:
                hub = self._agent_requirements.run(hub, output_language)
                self._progress("Agente Requisitos", "done")
            except Exception as exc:
                self._progress("Agente Requisitos", f"error: {exc}")
                raise RuntimeError(f"Requirements Agent failed: {exc}") from exc

        return hub

    # ── Status helpers ────────────────────────────────────────────────────────

    @property
    def plan(self) -> list[str]:
        return list(self._PLAN)
