# core/rerun_handlers.py
import streamlit as st
from agents.agent_bpmn import AgentBPMN
from agents.agent_minutes import AgentMinutes
from agents.agent_requirements import AgentRequirements
from agents.agent_sbvr import AgentSBVR
from agents.agent_bmm import AgentBMM
from agents.agent_synthesizer import AgentSynthesizer
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
    elif agent_name == "bmm":
        agent = AgentBMM(client_info, provider_cfg)
        hub = agent.run(hub, output_language)
    elif agent_name == "synthesizer":
        agent = AgentSynthesizer(client_info, provider_cfg)
        hub = agent.run(hub, output_language)
    else:
        raise ValueError(f"Unknown agent: {agent_name}")
    return hub
