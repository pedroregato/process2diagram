# core/pipeline.py
import streamlit as st
import copy
from core.knowledge_hub import KnowledgeHub, BPMNModel
from agents.orchestrator import Orchestrator
from agents.agent_bpmn import AgentBPMN
from agents.agent_validator import AgentValidator

def run_pipeline(hub, config, progress_callback):
    """
    Executa o pipeline com base nas flags de config.
    Retorna hub atualizado ou levanta exceção.
    """
    client_info = config["client_info"]
    provider_cfg = config["provider_cfg"]
    output_lang = config["output_language"]
    run_quality = config["run_quality"]
    run_bpmn = config["run_bpmn"]
    run_minutes = config["run_minutes"]
    run_requirements = config["run_requirements"]
    run_sbvr = config.get("run_sbvr", False)
    run_bmm = config.get("run_bmm", False)
    run_dmn = config.get("run_dmn", False)
    run_argumentation = config.get("run_argumentation", False)
    run_synthesizer = config["run_synthesizer"]
    run_query_summarizer = config.get("run_query_summarizer", False)
    run_communication_noise = config.get("run_communication_noise", False)
    n_bpmn_runs = config["n_bpmn_runs"]
    bpmn_weights = config["bpmn_weights"]

    orchestrator = Orchestrator(client_info, provider_cfg, progress_callback)
    orchestrator._pipeline_config = config  # gives ATA Engine access to project_id/slug/location

    if run_bpmn and n_bpmn_runs > 1:
        # ── Multi‑run tournament: run N passes, pick best by AgentValidator ──────
        hub = orchestrator.run(hub, output_lang,
                               run_quality=run_quality,
                               run_bpmn=False,
                               run_minutes=False,
                               run_requirements=False,
                               run_synthesizer=False)

        validator = AgentValidator()
        agent_bpmn = AgentBPMN(client_info, provider_cfg)
        candidates = []
        for i in range(n_bpmn_runs):
            progress_callback("BPMN Agent", f"pass {i+1}/{n_bpmn_runs}…")
            hub_c = copy.copy(hub)
            hub_c.bpmn = BPMNModel()
            hub_c = agent_bpmn.run(hub_c, output_lang)
            score = validator.score(hub_c.bpmn, hub_c.transcript_clean, bpmn_weights)
            score.run_index = i + 1
            candidates.append((score, hub_c.bpmn))

        best_score, best_bpmn = max(candidates, key=lambda x: x[0].weighted)
        hub.bpmn = best_bpmn
        hub.validation.bpmn_score = best_score
        hub.validation.bpmn_candidates = [c[0] for c in candidates]
        hub.validation.n_bpmn_runs = n_bpmn_runs
        hub.validation.ready = True
        hub.bump()

        hub = orchestrator.run(hub, output_lang,
                               run_quality=False,
                               run_bpmn=False,
                               run_minutes=run_minutes,
                               run_requirements=run_requirements,
                               run_sbvr=run_sbvr,
                               run_bmm=run_bmm,
                               run_dmn=run_dmn,
                               run_argumentation=run_argumentation,
                               run_synthesizer=run_synthesizer,
                               run_query_summarizer=run_query_summarizer,
                               run_communication_noise=run_communication_noise)

    elif run_bpmn and config.get("use_langgraph", False):
        # ── LangGraph expandido: BPMN + Minutes + Requirements retry loops ─────
        from core.lg_pipeline import LGFullPipelineRunner

        # Step 1: prerequisites (Quality + Preprocessing + NLP only)
        hub = orchestrator.run(hub, output_lang,
                               run_quality=run_quality,
                               run_bpmn=False,
                               run_minutes=False,
                               run_requirements=False,
                               run_sbvr=False,
                               run_bmm=False,
                               run_synthesizer=False)

        # Step 2: BPMN → Minutes → Requirements adaptive retry via LangGraph
        lg_runner = LGFullPipelineRunner(client_info, provider_cfg, config, progress_callback)
        hub = lg_runner.run(
            hub, output_lang,
            run_minutes=run_minutes,
            run_requirements=run_requirements,
        )

        # Step 3: downstream agents (SBVR, BMM, DMN, Argumentation, Synthesizer)
        hub = orchestrator.run(hub, output_lang,
                               run_quality=False,
                               run_bpmn=False,
                               run_minutes=False,       # already done by LG runner
                               run_requirements=False,  # already done by LG runner
                               run_sbvr=run_sbvr,
                               run_bmm=run_bmm,
                               run_dmn=run_dmn,
                               run_argumentation=run_argumentation,
                               run_synthesizer=run_synthesizer,
                               run_query_summarizer=run_query_summarizer,
                               run_communication_noise=run_communication_noise)

    else:
        # ── Standard single‑run (no validation) ──────────────────────────────────
        hub = orchestrator.run(hub, output_lang,
                               run_quality=run_quality,
                               run_bpmn=run_bpmn,
                               run_minutes=run_minutes,
                               run_requirements=run_requirements,
                               run_sbvr=run_sbvr,
                               run_bmm=run_bmm,
                               run_dmn=run_dmn,
                               run_argumentation=run_argumentation,
                               run_synthesizer=run_synthesizer,
                               run_query_summarizer=run_query_summarizer,
                               run_communication_noise=run_communication_noise)

    # ── CKF Updater (non-fatal, post-pipeline) ────────────────────────────────
    if config.get("run_ckf_updater", False):
        _ckf_ctx_id = (
            config.get("active_project_id")
            or config.get("project_id")
            or getattr(hub, "context_id", "")
        )
        if _ckf_ctx_id:
            try:
                progress_callback("Atualizador CKF", "running")
                from agents.agent_ckf_updater import AgentCKFUpdater
                _ckf_agent = AgentCKFUpdater(client_info, provider_cfg)
                hub = _ckf_agent.run(hub, output_lang, context_id=_ckf_ctx_id)
                progress_callback("Atualizador CKF", "done")
            except Exception:
                progress_callback("Atualizador CKF", "skipped")

    # ── Knowledge extraction (non-fatal, post-pipeline) ───────────────────────
    _kh_meeting_id = config.get("meeting_id")
    _kh_project_id = config.get("project_id")
    _run_kh = config.get("run_knowledge_extractor", True)

    if _run_kh:
        try:
            progress_callback("Knowledge Hub", "running")
            from agents.agent_knowledge_extractor import AgentKnowledgeExtractor
            _kh_agent = AgentKnowledgeExtractor(client_info, provider_cfg)
            _kh_agent.run(
                hub, output_lang,
                meeting_id=_kh_meeting_id,
                project_id=_kh_project_id,
            )
            progress_callback("Knowledge Hub", "done")
        except Exception:
            progress_callback("Knowledge Hub", "skipped")

        # ── Cross-meeting contradiction detection (non-fatal) ─────────────────
        if _kh_project_id and _kh_meeting_id:
            try:
                progress_callback("Detecção de Contradições", "running")
                from agents.agent_contradiction_detector import AgentContradictionDetector
                _cd_agent = AgentContradictionDetector(client_info, provider_cfg)
                _cd_agent.run_for_meeting(_kh_project_id, _kh_meeting_id)
                progress_callback("Detecção de Contradições", "done")
            except Exception:
                progress_callback("Detecção de Contradições", "skipped")

    return hub
