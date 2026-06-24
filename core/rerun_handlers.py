# core/rerun_handlers.py
import streamlit as st
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
from core.knowledge_hub import SynthesizerModel

def handle_rerun(agent_name, hub, client_info, provider_cfg, output_language):
    """Run a single agent and return (hub, messages).

    messages is a list of (level, text) tuples where level is "info"|"warning"|"error".
    No st.* calls are made here — safe to run from a background thread.
    """
    messages = []

    if agent_name == "quality":
        agent = AgentTranscriptQuality(client_info, provider_cfg)
        agent._lg_skip_cache = True
        hub = agent.run(hub, output_language)
    elif agent_name == "bpmn":
        if hub.bpmn.raw_llm_dict:
            # Fast path: regenerate XML/Mermaid from stored extraction data (no LLM call).
            # Avoids calling DeepSeek from a background thread, which returns empty responses.
            agent = AgentBPMN(client_info, provider_cfg)
            hub.bpmn = agent._build_model(hub.bpmn.raw_llm_dict)
            hub.bpmn.raw_llm_dict = hub.bpmn.raw_llm_dict  # preserve
            agent._enforce_rules(hub.bpmn, getattr(hub.nlp, "actors", None))
            try:
                from modules.bpmn_auto_repair import repair_bpmn, reformat_bpmn_labels
                report = repair_bpmn(hub.bpmn)
                hub.bpmn.repair_log = report.repairs
            except Exception:
                hub.bpmn.repair_log = []
            try:
                from agents.agent_mermaid import MermaidGenerator
                hub.bpmn.mermaid = MermaidGenerator.generate(hub.bpmn)
            except Exception:
                hub.bpmn.mermaid = ""
            hub.bpmn.bpmn_xml = agent._generate_bpmn_xml(hub.bpmn)
            try:
                from modules.bpmn_auto_repair import reformat_bpmn_labels
                _xml_fmt, _fmt_changes = reformat_bpmn_labels(hub.bpmn.bpmn_xml)
                if not any(c.startswith("[ERRO]") for c in _fmt_changes):
                    hub.bpmn.bpmn_xml = _xml_fmt
            except Exception:
                pass
            hub.bpmn.ready = True
            hub.mark_agent_run("bpmn")
            hub.bump()
            # Update execution log to reflect fast-path rerun
            from datetime import datetime as _dt, timezone as _tz
            _prev_log = hub.bpmn.execution_log or {}
            try:
                _reformat_log = _fmt_changes  # noqa: F821  defined in try block above
            except NameError:
                _reformat_log = []
            hub.bpmn.execution_log = {
                **_prev_log,
                "generated_at": _dt.now(_tz.utc).isoformat(),
                "source": "fast_path_rerun",
                "repair_passes": hub.bpmn.repair_log,
                "reformat_passes": _reformat_log,
                "metrics": {
                    "steps":      len(hub.bpmn.steps),
                    "edges":      len(hub.bpmn.edges),
                    "lanes":      len(hub.bpmn.lanes),
                    "gateways":   sum(1 for s in hub.bpmn.steps if s.is_decision),
                    "long_titles": [s.title for s in hub.bpmn.steps if len(s.title) > 35],
                },
            }
            messages.append(("info", "ℹ️ Diagrama BPMN regenerado a partir da extração anterior (sem nova chamada LLM)."))
        else:
            agent = AgentBPMN(client_info, provider_cfg)
            agent._lg_skip_cache = True  # rerun sempre ignora cache semântico
            hub = agent.run(hub, output_language)
        # Invalida relatório
        hub.synthesizer = SynthesizerModel()
        hub.synthesizer.ready = False
        messages.append(("info", "ℹ️ Relatório executivo invalidado por mudança no BPMN."))
    elif agent_name == "minutes":
        agent = AgentMinutes(client_info, provider_cfg)
        agent._lg_skip_cache = True
        hub = agent.run(hub, output_language)
    elif agent_name == "requirements":
        agent = AgentRequirements(client_info, provider_cfg)
        agent._lg_skip_cache = True
        hub = agent.run(hub, output_language)
    elif agent_name == "sbvr":
        agent = AgentSBVR(client_info, provider_cfg)
        agent._lg_skip_cache = True
        hub = agent.run(hub, output_language)
        if hub.requirements.ready and hub.requirements.requirements:
            messages.append((
                "info",
                "ℹ️ Regras SBVR atualizadas. Re-execute o agente de Requisitos para "
                "atualizar os campos `business_rule_refs`.",
            ))
    elif agent_name == "bmm":
        agent = AgentBMM(client_info, provider_cfg)
        agent._lg_skip_cache = True
        hub = agent.run(hub, output_language)
    elif agent_name == "synthesizer":
        agent = AgentSynthesizer(client_info, provider_cfg)
        agent._lg_skip_cache = True
        hub = agent.run(hub, output_language)
        # Auto-save report_html to Supabase so it persists without requiring a manual save
        try:
            mid = (
                st.session_state.get("current_meeting_id")
                or st.session_state.get("_loaded_meeting_id")
            )
            if mid and hub.synthesizer.ready and hub.synthesizer.html:
                from core.project_store import save_report_html
                save_report_html(
                    mid,
                    hub.synthesizer.html,
                    provider_cfg.get("provider_name", ""),
                )
        except Exception:
            pass  # fail-open: session state update still happened
    elif agent_name == "dmn":
        agent = AgentDMN(client_info, provider_cfg)
        agent._lg_skip_cache = True
        hub = agent.run(hub, output_language)
    elif agent_name == "argumentation":
        agent = AgentArgumentation(client_info, provider_cfg)
        agent._lg_skip_cache = True
        hub = agent.run(hub, output_language)
    elif agent_name == "query_summarizer":
        agent = AgentQuerySummarizer(client_info, provider_cfg)
        agent._lg_skip_cache = True
        hub = agent.run(hub, output_language)
    elif agent_name == "communication_noise":
        agent = AgentCommunicationNoise(client_info, provider_cfg)
        agent._lg_skip_cache = True
        hub = agent.run(hub, output_language)
    elif agent_name == "mermaid":
        from agents.agent_mermaid import MermaidGenerator
        if hub.bpmn.steps:
            hub.bpmn.mermaid = MermaidGenerator.generate(hub.bpmn)
        else:
            messages.append(("warning", "⚠️ Dados do BPMN não disponíveis. Execute o agente BPMN primeiro."))
    else:
        raise ValueError(f"Unknown agent: {agent_name}")
    return hub, messages
