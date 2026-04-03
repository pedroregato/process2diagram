# app.py
import streamlit as st
from core.session_state import init_session_state
from ui.sidebar import render_sidebar
from ui.input_area import render_input_area
from core.pipeline import run_pipeline
from core.rerun_handlers import handle_rerun
from ui.tabs import (
    quality_tab, bpmn_tabs, minutes_tab, requirements_tab,
    synthesizer_tab, export_tab, dev_tools_tab
)
from services.export_service import make_filename
from modules.session_security import get_session_llm_client

# Configuração da página (sempre primeiro)
st.set_page_config(page_title="Process2Diagram", layout="wide")

# Inicialização segura do session_state
init_session_state()

# Sidebar
render_sidebar()

# Área de entrada e curadoria
start_process = render_input_area()

# Verificação de API key
if not get_session_llm_client(st.session_state.selected_provider):
    st.warning("👈 Enter your API key in the sidebar.")
    st.stop()

# Progresso (placeholder global)
progress_placeholder = st.empty()

# Pipeline principal
if start_process and st.session_state.transcript_text.strip():
    if not any([st.session_state.run_quality, st.session_state.run_bpmn,
                st.session_state.run_minutes, st.session_state.run_requirements,
                st.session_state.run_synthesizer]):
        st.warning("Select at least one agent.")
        st.stop()

    client_info = get_session_llm_client(st.session_state.selected_provider)
    if not client_info:
        st.error("API key missing.")
        st.stop()

    from core.knowledge_hub import KnowledgeHub
    hub = KnowledgeHub.new()
    hub.set_transcript(st.session_state.transcript_text)
    if st.session_state.get("curated_clean") and st.session_state.curated_clean != st.session_state.transcript_text:
        hub.transcript_clean = st.session_state.curated_clean
    hub.meta.llm_provider = st.session_state.selected_provider

    config = {
        "client_info": client_info,
        "provider_cfg": st.session_state.provider_cfg,
        "output_language": st.session_state.output_language,
        "run_quality": st.session_state.run_quality,
        "run_bpmn": st.session_state.run_bpmn,
        "run_minutes": st.session_state.run_minutes,
        "run_requirements": st.session_state.run_requirements,
        "run_synthesizer": st.session_state.run_synthesizer,
        "n_bpmn_runs": st.session_state.n_bpmn_runs,
        "bpmn_weights": st.session_state.bpmn_weights,
    }

    agent_status = {}
    def update_progress(step, status):
        agent_status[step] = status
        lines = [f"{'✅' if 'done' in s else '⏳' if 'running' in s else '❌'} **{n}** — {s}" for n,s in agent_status.items()]
        progress_placeholder.markdown("\n".join(lines))

    try:
        hub = run_pipeline(hub, config, update_progress)
        st.session_state.hub = hub
        progress_placeholder.success(f"✅ Pipeline concluído. Tokens: {hub.meta.total_tokens_used}")
    except Exception as e:
        progress_placeholder.error(f"Erro: {e}")
        st.stop()

# Reexecução de agente (se acionado)
if "rerun_agent" in st.session_state:
    agent = st.session_state.pop("rerun_agent")
    hub = st.session_state.get("hub")
    if hub:
        client_info = get_session_llm_client(st.session_state.selected_provider)
        if client_info:
            try:
                hub = handle_rerun(agent, hub, client_info, st.session_state.provider_cfg,
                                   st.session_state.output_language)
                st.session_state.hub = hub
                st.success(f"✅ {agent.capitalize()} re‑executado.")
            except Exception as e:
                st.error(f"Erro: {e}")
        else:
            st.error("API key não encontrada.")
    else:
        st.error("Nenhuma sessão ativa. Execute o pipeline primeiro.")

# Exibição dos resultados (apenas se hub existir)
if "hub" in st.session_state:
    hub = st.session_state.hub
    prefix = st.session_state.prefix
    suffix = st.session_state.suffix

    tabs_to_show = []
    if hub.transcript_quality.ready: tabs_to_show.append("quality")
    if hub.bpmn.ready: tabs_to_show.extend(["bpmn", "mermaid"])
    if hub.validation.ready and hub.validation.n_bpmn_runs > 1: tabs_to_show.append("validation")
    if hub.minutes.ready: tabs_to_show.append("minutes")
    if hub.requirements.ready: tabs_to_show.append("requirements")
    if hub.synthesizer.ready: tabs_to_show.append("synthesizer")
    tabs_to_show.append("export")
    if st.session_state.show_dev_tools: tabs_to_show.append("devtools")

    tab_labels = {
        "quality": "🔬 Quality", "bpmn": "📐 BPMN 2.0", "mermaid": "📊 Mermaid",
        "validation": "🏆 Validação", "minutes": "📋 Minutes", "requirements": "📝 Requirements",
        "synthesizer": "📄 Report", "export": "📦 Export", "devtools": "🔍 Dev"
    }
    tabs = st.tabs([tab_labels[t] for t in tabs_to_show])
    for idx, tab_id in enumerate(tabs_to_show):
        with tabs[idx]:
            if tab_id == "quality":
                quality_tab.render(hub, prefix, suffix)
            elif tab_id == "bpmn":
                bpmn_tabs.render_bpmn(hub, prefix, suffix)
            elif tab_id == "mermaid":
                bpmn_tabs.render_mermaid(hub, prefix, suffix)
            elif tab_id == "validation":
                bpmn_tabs.render_validation(hub)
            elif tab_id == "minutes":
                minutes_tab.render(hub, prefix, suffix)
            elif tab_id == "requirements":
                requirements_tab.render(hub, prefix, suffix)
            elif tab_id == "synthesizer":
                synthesizer_tab.render(hub, prefix, suffix)
            elif tab_id == "export":
                export_tab.render(hub, prefix, suffix)
            elif tab_id == "devtools":
                dev_tools_tab.render(hub, st.session_state.show_raw_json)

st.markdown("---")
st.markdown("Process2Diagram v4.6 — Multi‑Agent Architecture")
