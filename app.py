# app.py
import streamlit as st
from core.session_state import init_session_state
from ui.sidebar import render_sidebar
from ui.input_area import render_input_area
from core.pipeline import run_pipeline
from core.rerun_handlers import handle_rerun
from ui.tabs import (
    render_quality, render_bpmn, render_mermaid, render_validation,
    render_minutes, render_requirements, render_sbvr, render_bmm,
    render_synthesizer, render_export, render_dev_tools
)
from services.export_service import make_filename
from modules.session_security import get_session_llm_client

# Configuração da página (sempre primeiro)
st.set_page_config(page_title="Process2Diagram", layout="wide")

# Inicialização segura do session_state
init_session_state()

# Sidebar (sempre visível)
render_sidebar()

# Área de entrada e curadoria
start_process = render_input_area()

# Verificação de API key
if not get_session_llm_client(st.session_state.selected_provider):
    st.warning("👈 Enter your API key in the sidebar.")
    st.stop()

# Placeholder para progresso
progress_placeholder = st.empty()

# ──────────────────────────────────────────────────────────────────────────────
# PIPELINE PRINCIPAL
# ──────────────────────────────────────────────────────────────────────────────
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
        "run_sbvr": st.session_state.run_sbvr,
        "run_bmm": st.session_state.run_bmm,
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
        progress_placeholder.error(f"Erro no pipeline: {e}")
        st.stop()

# ──────────────────────────────────────────────────────────────────────────────
# REEXECUÇÃO DE AGENTES (botões no corpo principal)
# ──────────────────────────────────────────────────────────────────────────────
if "hub" in st.session_state:
    st.markdown("---")
    st.markdown("### 🔄 Re‑executar Agentes")
    st.caption("Execute novamente um agente individualmente (sobrescreve o resultado anterior).")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        if st.button("🔬 Qualidade", key="rr_quality_body"):
            st.session_state.rerun_agent = "quality"
    with col2:
        if st.button("📐 BPMN", key="rr_bpmn_body"):
            st.session_state.rerun_agent = "bpmn"
    with col3:
        if st.button("📋 Ata", key="rr_minutes_body"):
            st.session_state.rerun_agent = "minutes"
    with col4:
        if st.button("📝 Requisitos", key="rr_req_body"):
            st.session_state.rerun_agent = "requirements"
    with col5:
        if st.button("📄 Relatório", key="rr_synth_body"):
            st.session_state.rerun_agent = "synthesizer"
    col6, col7, _ = st.columns([1, 1, 3])
    with col6:
        if st.button("📖 SBVR", key="rr_sbvr_body"):
            st.session_state.rerun_agent = "sbvr"
    with col7:
        if st.button("🎯 BMM", key="rr_bmm_body"):
            st.session_state.rerun_agent = "bmm"
    st.markdown("---")

# ──────────────────────────────────────────────────────────────────────────────
# HANDLER DE REEXECUÇÃO (deve vir após os botões)
# ──────────────────────────────────────────────────────────────────────────────
if "rerun_agent" in st.session_state:
    agent = st.session_state.pop("rerun_agent")
    hub = st.session_state.get("hub")
    if hub:
        client_info = get_session_llm_client(st.session_state.selected_provider)
        if client_info:
            try:
                hub = handle_rerun(agent, hub, client_info,
                                   st.session_state.provider_cfg,
                                   st.session_state.output_language)
                st.session_state.hub = hub
                st.success(f"✅ {agent.capitalize()} re‑executado com sucesso.")
            except Exception as e:
                st.error(f"Erro na reexecução: {e}")
        else:
            st.error("Chave de API não encontrada.")
    else:
        st.error("Nenhuma sessão ativa. Execute o pipeline primeiro.")

# ──────────────────────────────────────────────────────────────────────────────
# EXIBIÇÃO DOS RESULTADOS (abas)
# ──────────────────────────────────────────────────────────────────────────────
if "hub" in st.session_state:
    hub = st.session_state.hub
    prefix = st.session_state.prefix
    suffix = st.session_state.suffix

    # Define quais abas mostrar
    tabs_to_show = []
    if hub.transcript_quality.ready:
        tabs_to_show.append("quality")
    if hub.bpmn.ready:
        tabs_to_show.append("bpmn")
        tabs_to_show.append("mermaid")
        if hub.validation.ready and hub.validation.n_bpmn_runs > 1:
            tabs_to_show.append("validation")
    if hub.minutes.ready:
        tabs_to_show.append("minutes")
    if hub.requirements.ready:
        tabs_to_show.append("requirements")
    if hub.sbvr.ready:
        tabs_to_show.append("sbvr")
    if hub.bmm.ready:
        tabs_to_show.append("bmm")
    if hub.synthesizer.ready:
        tabs_to_show.append("synthesizer")
    tabs_to_show.append("export")
    if st.session_state.show_dev_tools:
        tabs_to_show.append("devtools")

    # Rótulos das abas
    tab_labels = {
        "quality": "🔬 Qualidade",
        "bpmn": "📐 BPMN 2.0",
        "mermaid": "📊 Mermaid",
        "validation": "🏆 Validação BPMN",
        "minutes": "📋 Ata de Reunião",
        "requirements": "📝 Requisitos",
        "sbvr": "📖 SBVR",
        "bmm": "🎯 BMM",
        "synthesizer": "📄 Relatório Executivo",
        "export": "📦 Exportar",
        "devtools": "🔍 Dev Tools"
    }

    tabs = st.tabs([tab_labels[t] for t in tabs_to_show])
    for idx, tab_id in enumerate(tabs_to_show):
        with tabs[idx]:
            if tab_id == "quality":
                render_quality(hub, prefix, suffix)
            elif tab_id == "bpmn":
                render_bpmn(hub, prefix, suffix)
            elif tab_id == "mermaid":
                render_mermaid(hub, prefix, suffix)
            elif tab_id == "validation":
                render_validation(hub)
            elif tab_id == "minutes":
                render_minutes(hub, prefix, suffix)
            elif tab_id == "requirements":
                render_requirements(hub, prefix, suffix)
            elif tab_id == "sbvr":
                render_sbvr(hub, prefix, suffix)
            elif tab_id == "bmm":
                render_bmm(hub, prefix, suffix)
            elif tab_id == "synthesizer":
                render_synthesizer(hub, prefix, suffix)
            elif tab_id == "export":
                render_export(hub, prefix, suffix)
            elif tab_id == "devtools":
                render_dev_tools(hub, st.session_state.show_raw_json)

# Rodapé
st.markdown("---")
st.markdown("Process2Diagram v4.6 — Arquitetura Multi‑Agente Modular", unsafe_allow_html=True)
