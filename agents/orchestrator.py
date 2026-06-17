# agents/orchestrator.py
# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator — pipeline sequencial com execução paralela de Minutes e
# Requirements (ThreadPoolExecutor — compatível com Streamlit).
#
# Pipeline:
#   0. AgentTranscriptQuality → hub.transcript_quality  (quality gate)
#   0.5 TranscriptPreprocessor → hub.transcript_clean   (no LLM)
#   1. NLPChunker             → hub.nlp                 (no LLM)
#   2. AgentBPMN              → hub.bpmn
#   3. AgentMinutes  ┐  paralelo  → hub.minutes
#   4. AgentRequirements ┘         → hub.requirements
#   5. AgentSynthesizer → hub.synthesizer               (opcional)
#
# Paralelismo:
#   Minutes e Requirements são independentes entre si — ambos leem apenas
#   hub.transcript_clean e hub.nlp (somente leitura após o NLP).
#   Cada agente recebe uma cópia rasa do hub com meta isolado.
#   Os resultados são mergeados de volta no hub principal após ambos concluírem.
#   Fallback automático para execução sequencial se o executor falhar.
#
# Progress reporting:
#   O progress_callback é protegido por threading.Lock para evitar writes
#   simultâneos no placeholder Streamlit.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import copy
import threading
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Optional

from agents.nlp_chunker import NLPChunker
from agents.agent_bpmn import AgentBPMN
from agents.agent_minutes import AgentMinutes
from agents.agent_requirements import AgentRequirements
from agents.agent_sbvr import AgentSBVR
from agents.agent_bmm import AgentBMM
from agents.agent_dmn import AgentDMN
from agents.agent_argumentation import AgentArgumentation
from agents.agent_synthesizer import AgentSynthesizer
from agents.agent_query_summarizer import AgentQuerySummarizer
from agents.agent_communication_noise import AgentCommunicationNoise
from agents.agent_transcript_quality import AgentTranscriptQuality
from core.knowledge_hub import KnowledgeHub, MeetingTimeModel, PreprocessingModel, SessionMetadata
from modules.transcript_preprocessor import preprocess
from modules.transcript_time_parser import (
    parse_transcript_timings,
    estimate_timings_from_wordcount,
)


# Type alias for progress callbacks
ProgressCallback = Callable[[str, str], None]   # (step_name, status) → None


class Orchestrator:
    """
    Orchestrator: TranscriptQuality → NLP → BPMN → [Minutes ‖ Requirements] → Synthesizer.

    Minutes e Requirements são executados em paralelo via ThreadPoolExecutor
    quando ambos estão habilitados, reduzindo a latência total em ~40 %.

    Usage:
        hub = KnowledgeHub.new()
        hub.set_transcript(raw_text)

        orc = Orchestrator(client_info, provider_cfg)
        hub = orc.run(hub, output_language="Portuguese (BR)")
    """

    _PLAN = ["transcript_quality", "preprocessing", "nlp", "bpmn",
             "minutes", "requirements", "sbvr", "bmm", "dmn", "argumentation", "synthesizer",
             "query_summarizer", "knowledge_extractor", "contradiction_detector",
             "communication_noise"]

    def __init__(
        self,
        client_info: dict,
        provider_cfg: dict,
        progress_callback: Optional[ProgressCallback] = None,
    ):
        self.client_info = client_info
        self.provider_cfg = provider_cfg
        self._progress_lock = threading.Lock()
        self._progress_raw = progress_callback or (lambda name, status: None)

        # Instantiate agents
        self._agent_quality      = AgentTranscriptQuality(client_info, provider_cfg)
        self._chunker            = NLPChunker()
        self._agent_bpmn         = AgentBPMN(client_info, provider_cfg)
        self._agent_minutes      = AgentMinutes(client_info, provider_cfg)
        self._agent_requirements = AgentRequirements(client_info, provider_cfg)
        self._agent_sbvr         = AgentSBVR(client_info, provider_cfg)
        self._agent_bmm          = AgentBMM(client_info, provider_cfg)
        self._agent_synthesizer  = AgentSynthesizer(client_info, provider_cfg)
        self._agent_dmn          = AgentDMN(client_info, provider_cfg)
        self._agent_argumentation = AgentArgumentation(client_info, provider_cfg)
        self._agent_query_summarizer = AgentQuerySummarizer(client_info, provider_cfg)
        self._agent_communication_noise = AgentCommunicationNoise(client_info, provider_cfg)

    # ── Thread-safe progress callback ─────────────────────────────────────────

    def _progress(self, name: str, status: str) -> None:
        """Call the progress callback under a lock (safe from worker threads)."""
        with self._progress_lock:
            self._progress_raw(name, status)

    # ── Main entry point ──────────────────────────────────────────────────────

    def run(
        self,
        hub: KnowledgeHub,
        output_language: str = "Auto-detect",
        run_quality: bool = True,
        run_bpmn: bool = True,
        run_minutes: bool = True,
        run_requirements: bool = True,
        run_sbvr: bool = False,
        run_bmm: bool = False,
        run_dmn: bool = False,
        run_argumentation: bool = False,
        run_synthesizer: bool = False,
        run_query_summarizer: bool = False,
        run_communication_noise: bool = False,
        run_prereqs: bool = True,
    ) -> KnowledgeHub:
        """
        Execute the pipeline.

        Minutes and Requirements run in parallel when both are enabled.
        Synthesizer always runs after both complete.
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
                hub.bump()

        # ── Step 0.5: Transcript Preprocessor (no LLM) ───────────────────────
        if run_prereqs:
            already_curated = (
                hub.transcript_clean
                and hub.transcript_clean.strip() != hub.transcript_raw.strip()
            )
            if already_curated:
                self._progress("Pré-processamento", "skipped (texto curado pelo usuário)")
            else:
                self._progress("Pré-processamento", "running")
            try:
                if not already_curated:
                    result = preprocess(hub.transcript_raw)
                    hub.transcript_clean = result.clean_text
                    hub.preprocessing = PreprocessingModel(
                        fillers_removed=result.fillers_removed,
                        artifact_turns=result.artifact_turns,
                        repetitions_collapsed=result.repetitions_collapsed,
                        metadata_issues=result.metadata_issues,
                        ready=True,
                    )
                hub.bump()
                self._progress("Pré-processamento", "done")
            except Exception as exc:
                self._progress("Pré-processamento", f"error: {exc}")
                hub.bump()
        else:
            self._progress("Pré-processamento", "skipped")

        # ── Step 1: NLP Chunker (no LLM) ─────────────────────────────────────
        if run_prereqs:
            self._progress("NLP / Chunker", "running")
            try:
                hub = self._chunker.run(hub)
                self._progress("NLP / Chunker", "done")
            except Exception as exc:
                self._progress("NLP / Chunker", f"error: {exc}")
                hub.transcript_clean = hub.transcript_raw
                hub.bump()
        else:
            self._progress("NLP / Chunker", "skipped")

        # ── Step 1.5: Transcript Time Parser (no LLM) ────────────────────────
        try:
            _timings = parse_transcript_timings(hub.transcript_raw)
            if not _timings.has_timestamps:
                _timings = estimate_timings_from_wordcount(hub.transcript_raw)
            hub.meeting_time = MeetingTimeModel(
                has_timestamps=_timings.has_timestamps,
                format_detected=_timings.format_detected,
                duration_seconds=_timings.duration_seconds,
                speaker_times=_timings.speaker_times,
                speaker_turns=_timings.speaker_turns,
                ready=True,
            )
            hub.bump()
        except Exception:
            pass   # non-fatal — leave meeting_time in default state

        # ── Step 2: BPMN Agent ────────────────────────────────────────────────
        if run_bpmn:
            self._progress("Agente BPMN", "running")
            try:
                hub = self._agent_bpmn.run(hub, output_language)
                self._progress("Agente BPMN", "done")
            except Exception as exc:
                self._progress("Agente BPMN", f"error: {exc}")
                raise RuntimeError(f"BPMN Agent failed: {exc}") from exc

        # ── Step 2.5: SBVR Agent (before Minutes+Requirements for traceability) ─
        # When SBVR is enabled it runs here so Requirements can reference BR-IDs.
        # When SBVR is disabled, Requirements runs without BR context (legacy path).
        if run_sbvr:
            self._progress("Agente SBVR", "running")
            try:
                hub = self._agent_sbvr.run(hub, output_language)
                self._progress("Agente SBVR", "done")
            except Exception as exc:
                self._progress("Agente SBVR", f"error: {exc}")
                hub.bump()

        # ── Steps 3 & 4: Minutes + Requirements (parallel when both enabled) ──
        both_enabled = run_minutes and run_requirements
        if both_enabled:
            hub = self._run_minutes_requirements_parallel(hub, output_language)
        else:
            if run_minutes:
                self._progress("Agente Ata", "running")
                try:
                    hub = self._agent_minutes.run(hub, output_language)
                    self._progress("Agente Ata", "done")
                except Exception as exc:
                    self._progress("Agente Ata", f"error: {exc}")
                    raise RuntimeError(f"Minutes Agent failed: {exc}") from exc

        # ── Post-minutes: ATA Engine HTML generation ──────────────────────────
        if run_minutes and hub.minutes.ready:
            try:
                from modules.ata_engine_generator import generate_ata_html
                from datetime import date as _date
                _cfg     = getattr(self, "_pipeline_config", {})
                _slug    = _cfg.get("project_slug") or "p2d"
                _proj_id = _cfg.get("project_id", "")
                _mtg_id  = _cfg.get("meeting_id", "")
                _local   = _cfg.get("meeting_location", "Videoconferência")
                hub.minutes.ata_html = generate_ata_html(
                    minutes      = hub.minutes,
                    project_id   = _proj_id,
                    meeting_id   = _mtg_id,
                    project_slug = _slug,
                    meeting_date = _date.today(),
                    local        = _local,
                )
                hub.bump()
            except Exception as _ata_err:
                hub.minutes.ata_html_error = str(_ata_err)

        # ── Step 4: Requirements Agent ────────────────────────────────────────
        # Runs independently of run_minutes — Requirements Backfill uses
        # run_minutes=False + run_requirements=True.
        # The parallel path (both_enabled) already handled the combined case above.
        if run_requirements and not both_enabled:
            self._progress("Agente Requisitos", "running")
            try:
                hub = self._agent_requirements.run(hub, output_language)
                self._progress("Agente Requisitos", "done")
            except Exception as exc:
                self._progress("Agente Requisitos", f"error: {exc}")
                raise RuntimeError(f"Requirements Agent failed: {exc}") from exc

        # ── Step 5: SBVR Agent (legacy position — only if not already run above) ─
        # This block is now a no-op (run_sbvr is handled at step 2.5), kept for
        # clarity and in case the order is changed back in future.

        # ── Step 6: BMM Agent ─────────────────────────────────────────────────
        if run_bmm:
            self._progress("Agente BMM", "running")
            try:
                hub = self._agent_bmm.run(hub, output_language)
                self._progress("Agente BMM", "done")
            except Exception as exc:
                self._progress("Agente BMM", f"error: {exc}")
                hub.bump()

        # ── Step 6b: DMN Agent ───────────────────────────────────────────────────
        if run_dmn:
            self._progress("Agente DMN", "running")
            try:
                hub = self._agent_dmn.run(hub, output_language)
                self._progress("Agente DMN", "done")
            except Exception as exc:
                self._progress("Agente DMN", f"error: {exc}")
                hub.bump()

        # ── Step 6c: Argumentation Agent ─────────────────────────────────────
        if run_argumentation:
            self._progress("Agente Argumentacao (IBIS)", "running")
            try:
                hub = self._agent_argumentation.run(hub, output_language)
                self._progress("Agente Argumentacao (IBIS)", "done")
            except Exception as exc:
                self._progress("Agente Argumentacao (IBIS)", f"error: {exc}")
                hub.bump()

        # ── Step 6d: Query Summarizer Agent (Fase F) ──────────────────────────
        if run_query_summarizer:
            self._progress("Agente Sumário por Perspectiva", "running")
            try:
                hub = self._agent_query_summarizer.run(hub, output_language)
                self._progress("Agente Sumário por Perspectiva", "done")
            except Exception as exc:
                self._progress("Agente Sumário por Perspectiva", f"error: {exc}")
                hub.bump()

        # ── Step 6e: Communication Noise Agent ───────────────────────────────
        if run_communication_noise:
            self._progress("Agente Ruídos de Comunicação", "running")
            try:
                hub = self._agent_communication_noise.run(hub, output_language)
                self._progress("Agente Ruídos de Comunicação", "done")
            except Exception as exc:
                self._progress("Agente Ruídos de Comunicação", f"error: {exc}")
                hub.bump()

        # ── Step 7: Synthesizer Agent ─────────────────────────────────────────
        if run_synthesizer:
            self._progress("Agente Sintetizador", "running")
            try:
                hub = self._agent_synthesizer.run(hub, output_language)
                self._progress("Agente Sintetizador", "done")
            except Exception as exc:
                self._progress("Agente Sintetizador", f"error: {exc}")
                hub.bump()

        # ── Step 8: Outcome validation (pure Python, fail-open) ───────────────
        # Populates hub.validation.agent_scores for every pipeline run.
        try:
            from agents.agent_validator import AgentValidator as _AV
            _bpmn_weights = getattr(self, "_pipeline_config", {}).get("bpmn_weights", {})
            hub.validation.agent_scores = _AV().validate_all(hub, _bpmn_weights)
            hub.bump()
        except Exception:
            pass  # never break the pipeline

        return hub

    # ── Parallel execution helper ─────────────────────────────────────────────

    def _run_minutes_requirements_parallel(
        self, hub: KnowledgeHub, output_language: str
    ) -> KnowledgeHub:
        """
        Run AgentMinutes and AgentRequirements concurrently using a
        ThreadPoolExecutor with 2 workers.

        Each agent receives a shallow copy of hub with an isolated meta object
        so that concurrent writes to meta (token counts, agents_run) do not
        race.  After both futures resolve, results are merged back into the
        original hub.

        Falls back to sequential execution if the executor raises.
        """
        tokens_base = hub.meta.total_tokens_used

        def _make_hub_copy(source: KnowledgeHub) -> KnowledgeHub:
            """Shallow copy with an independent meta — safe for parallel agents."""
            h = copy.copy(source)
            h.meta = copy.copy(source.meta)
            h.meta.agents_run = list(source.meta.agents_run)
            return h

        def _run_minutes(h: KnowledgeHub):
            self._progress("Agente Ata", "running")
            result = self._agent_minutes.run(h, output_language)
            self._progress("Agente Ata", "done")
            return result

        def _run_requirements(h: KnowledgeHub):
            self._progress("Agente Requisitos", "running")
            result = self._agent_requirements.run(h, output_language)
            self._progress("Agente Requisitos", "done")
            return result

        try:
            hub_m = _make_hub_copy(hub)
            hub_r = _make_hub_copy(hub)

            with ThreadPoolExecutor(max_workers=2) as executor:
                future_m: Future = executor.submit(_run_minutes, hub_m)
                future_r: Future = executor.submit(_run_requirements, hub_r)
                # Retrieve results (raises if the callable raised)
                hub_m_result = future_m.result()
                hub_r_result = future_r.result()

            # ── Merge results into main hub ───────────────────────────────────
            hub.minutes      = hub_m_result.minutes
            hub.requirements = hub_r_result.requirements

            # Token deltas: each copy started from tokens_base
            delta_m = hub_m_result.meta.total_tokens_used - tokens_base
            delta_r = hub_r_result.meta.total_tokens_used - tokens_base
            hub.meta.total_tokens_used += max(0, delta_m) + max(0, delta_r)

            # Merge agents_run (preserve order, avoid duplicates)
            for agent_name in hub_m_result.meta.agents_run:
                if agent_name not in hub.meta.agents_run:
                    hub.meta.agents_run.append(agent_name)
            for agent_name in hub_r_result.meta.agents_run:
                if agent_name not in hub.meta.agents_run:
                    hub.meta.agents_run.append(agent_name)

            hub.bump()

        except Exception as exc:
            # Parallel execution failed — fall back to sequential
            self._progress("Agente Ata", "running (sequencial)")
            try:
                hub = self._agent_minutes.run(hub, output_language)
                self._progress("Agente Ata", "done")
            except Exception as exc2:
                raise RuntimeError(f"Minutes Agent failed: {exc2}") from exc2

            self._progress("Agente Requisitos", "running (sequencial)")
            try:
                hub = self._agent_requirements.run(hub, output_language)
                self._progress("Agente Requisitos", "done")
            except Exception as exc3:
                raise RuntimeError(f"Requirements Agent failed: {exc3}") from exc3

        return hub

    # ── Status helpers ────────────────────────────────────────────────────────

    @property
    def plan(self) -> list[str]:
        return list(self._PLAN)
