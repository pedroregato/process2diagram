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
    run_synthesizer = config["run_synthesizer"]
    n_bpmn_runs = config["n_bpmn_runs"]
    bpmn_weights = config["bpmn_weights"]

    orchestrator = Orchestrator(client_info, provider_cfg, progress_callback)

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
                               run_synthesizer=run_synthesizer)

    elif run_bpmn and config.get("use_langgraph", False):
        # ── LangGraph adaptive retry: run until score ≥ threshold or max retries ─
        from core.lg_pipeline import LGBPMNRunner

        # Step 1: prerequisites (Quality + Preprocessing + NLP only)
        hub = orchestrator.run(hub, output_lang,
                               run_quality=run_quality,
                               run_bpmn=False,
                               run_minutes=False,
                               run_requirements=False,
                               run_sbvr=False,
                               run_bmm=False,
                               run_synthesizer=False)

        # Step 2: BPMN adaptive retry via LangGraph
        lg_runner = LGBPMNRunner(client_info, provider_cfg, config, progress_callback)
        hub = lg_runner.run(hub, output_lang)

        # Step 3: downstream agents
        hub = orchestrator.run(hub, output_lang,
                               run_quality=False,
                               run_bpmn=False,
                               run_minutes=run_minutes,
                               run_requirements=run_requirements,
                               run_sbvr=run_sbvr,
                               run_bmm=run_bmm,
                               run_synthesizer=run_synthesizer)

    else:
        # ── Standard single‑run (no validation) ──────────────────────────────────
        hub = orchestrator.run(hub, output_lang,
                               run_quality=run_quality,
                               run_bpmn=run_bpmn,
                               run_minutes=run_minutes,
                               run_requirements=run_requirements,
                               run_sbvr=run_sbvr,
                               run_bmm=run_bmm,
                               run_synthesizer=run_synthesizer)
    return hub
