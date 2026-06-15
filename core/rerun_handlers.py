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
    if agent_name == "quality":
        agent = AgentTranscriptQuality(client_info, provider_cfg)
        hub = agent.run(hub, output_language)
    elif agent_name == "bpmn":
        agent = AgentBPMN(client_info, provider_cfg)
        hub = agent.run(hub, output_language)
        # Invalida relatório
        hub.synthesizer = SynthesizerModel()
        hub.synthesizer.ready = False
        st.info("ℹ️ Executive report invalidated due to BPMN change.")
    elif agent_name == "minutes":
        agent = AgentMinutes(client_info, provider_cfg)
        hub = agent.run(hub, output_language)
    elif agent_name == "requirements":
        agent = AgentRequirements(client_info, provider_cfg)
        hub = agent.run(hub, output_language)
    elif agent_name == "sbvr":
        agent = AgentSBVR(client_info, provider_cfg)
        hub = agent.run(hub, output_language)
        # Warn that Requirements traceability is now stale
        if hub.requirements.ready and hub.requirements.requirements:
            st.info(
                "ℹ️ Regras SBVR atualizadas. Re-execute o agente de Requisitos para "
                "atualizar os campos `business_rule_refs`."
            )
    elif agent_name == "bmm":
        agent = AgentBMM(client_info, provider_cfg)
        hub = agent.run(hub, output_language)
    elif agent_name == "synthesizer":
        agent = AgentSynthesizer(client_info, provider_cfg)
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
        hub = agent.run(hub, output_language)
    elif agent_name == "argumentation":
        agent = AgentArgumentation(client_info, provider_cfg)
        hub = agent.run(hub, output_language)
    elif agent_name == "query_summarizer":
        agent = AgentQuerySummarizer(client_info, provider_cfg)
        hub = agent.run(hub, output_language)
    elif agent_name == "communication_noise":
        agent = AgentCommunicationNoise(client_info, provider_cfg)
        hub = agent.run(hub, output_language)
    elif agent_name == "mermaid":
        from agents.agent_mermaid import MermaidGenerator
        if hub.bpmn.steps:
            hub.bpmn.mermaid = MermaidGenerator.generate(hub.bpmn)
        else:
            st.warning("⚠️ Dados do BPMN não disponíveis nesta sessão. Execute o agente BPMN primeiro.")
    else:
        raise ValueError(f"Unknown agent: {agent_name}")
    return hub
