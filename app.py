## --- Process2Diagram v4.5 — Corrigido (sem NameError) ---
import sys
from pathlib import Path
import json
import subprocess as _sp
from datetime import date

import streamlit as st
import streamlit.components.v1 as components

root_dir = Path(__file__).parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from modules.session_security import render_api_key_gate, get_session_llm_client
from modules.config import AVAILABLE_PROVIDERS
from modules.ingest import load_transcript
from core.knowledge_hub import KnowledgeHub, BPMNModel
from agents.orchestrator import Orchestrator
from agents.agent_bpmn import AgentBPMN
from agents.agent_validator import AgentValidator
from agents.agent_minutes import AgentMinutes
from agents.agent_mermaid import generate_mermaid
from modules.bpmn_viewer import preview_from_xml
from modules.mermaid_renderer import render_mermaid_block
from modules.bpmn_diagnostics import render_bpmn_diagnostics

st.set_page_config(page_title="Process2Diagram", page_icon="⚡", layout="wide")

# ── Inicializa session_state com valores padrão ─────────────────────────────
if "selected_provider" not in st.session_state:
    st.session_state.selected_provider = "DeepSeek"
if "provider_cfg" not in st.session_state:
    st.session_state.provider_cfg = AVAILABLE_PROVIDERS.get(st.session_state.selected_provider, {})
if "output_language" not in st.session_state:
    st.session_state.output_language = "Auto-detect"
if "prefix" not in st.session_state:
    st.session_state.prefix = "P2D_"
if "suffix" not in st.session_state:
    st.session_state.suffix = date.today().isoformat()
if "run_quality" not in st.session_state:
    st.session_state.run_quality = True
if "run_bpmn" not in st.session_state:
    st.session_state.run_bpmn = True
if "run_minutes" not in st.session_state:
    st.session_state.run_minutes = True
if "run_requirements" not in st.session_state:
    st.session_state.run_requirements = True
if "run_synthesizer" not in st.session_state:
    st.session_state.run_synthesizer = False
if "n_bpmn_runs" not in st.session_state:
    st.session_state.n_bpmn_runs = 1
if "bpmn_weights" not in st.session_state:
    st.session_state.bpmn_weights = {"granularity": 5, "task_type": 5, "gateways": 5}
if "show_dev_tools" not in st.session_state:
    st.session_state.show_dev_tools = False
if "show_raw_json" not in st.session_state:
    st.session_state.show_raw_json = False

# ── Sidebar (atualiza session_state) ───────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚡ Process2Diagram")
    st.markdown("---")
    st.markdown("### 🤖 LLM Engine")
    provider_names = list(AVAILABLE_PROVIDERS.keys())
    sel = st.selectbox("Provider", provider_names,
                       index=provider_names.index(st.session_state.selected_provider) if st.session_state.selected_provider in provider_names else 0,
                       key="provider_select")
    st.session_state.selected_provider = sel
    st.session_state.provider_cfg = AVAILABLE_PROVIDERS[sel]
    st.code(st.session_state.provider_cfg['default_model'], language="text")
    st.caption(st.session_state.provider_cfg['cost_hint'])
    render_api_key_gate(sel, st.session_state.provider_cfg)

    st.markdown("---")
    st.markdown("### ⚙️ Configuration")
    out_lang = st.selectbox("Output Language", ["Auto-detect", "Portuguese (BR)", "English"],
                            index=["Auto-detect", "Portuguese (BR)", "English"].index(st.session_state.output_language),
                            key="out_lang")
    st.session_state.output_language = {"Auto-detect":"Auto-detect","Portuguese (BR)":"Portuguese (BR)","English":"English"}[out_lang]

    col_pref, col_suf = st.columns(2)
    with col_pref:
        pref = st.text_input("Prefix (max 11 chars)", value=st.session_state.prefix.rstrip("_"), max_chars=11)
    with col_suf:
        suf = st.text_input("Suffix (max 11 chars)", value=st.session_state.suffix, max_chars=11)
    st.session_state.prefix = (pref.strip() + "_") if pref.strip() else "P2D_"
    st.session_state.suffix = suf.strip() if suf.strip() else date.today().isoformat()

    st.markdown("### 🤖 Active Agents")
    st.session_state.run_quality = st.checkbox("Quality Inspector", value=st.session_state.run_quality)
    st.session_state.run_bpmn = st.checkbox("BPMN Architect", value=st.session_state.run_bpmn)
    if st.session_state.run_bpmn:
        st.session_state.n_bpmn_runs = st.select_slider("Optimization Passes", options=[1,3,5], value=st.session_state.n_bpmn_runs)
        if st.session_state.n_bpmn_runs > 1:
            with st.expander("Selection Weights"):
                st.session_state.bpmn_weights = {
                    "granularity": st.slider("Granularity", 0,10, st.session_state.bpmn_weights["granularity"], key="w_gran"),
                    "task_type":   st.slider("Task Type",   0,10, st.session_state.bpmn_weights["task_type"],   key="w_type"),
                    "gateways":    st.slider("Gateways",    0,10, st.session_state.bpmn_weights["gateways"],    key="w_gw"),
                }
    st.session_state.run_minutes = st.checkbox("Meeting Minutes", value=st.session_state.run_minutes)
    st.session_state.run_requirements = st.checkbox("Requirements", value=st.session_state.run_requirements)
    st.session_state.run_synthesizer = st.checkbox("Executive Report", value=st.session_state.run_synthesizer)

    st.markdown("---")
    st.caption("🔒 API keys are session-only.")
    st.session_state.show_dev_tools = st.checkbox("🛠️ Developer Mode", value=st.session_state.show_dev_tools)
    if st.session_state.show_dev_tools:
        st.session_state.show_raw_json = st.checkbox("Show Raw JSON", value=st.session_state.show_raw_json)

# ── Main area ──────────────────────────────────────────────────────────────
st.markdown("<h1 style='font-size:2.5rem'>Process2Diagram</h1>", unsafe_allow_html=True)
st.markdown("Turn meeting transcripts into process diagrams — automatically.")

if not get_session_llm_client(st.session_state.selected_provider):
    st.warning("👈 Enter your API key in the sidebar.")
    st.stop()

# ── Input Section (com session state para o texto) ─────────────────────────
if "transcript_text" not in st.session_state:
    st.session_state.transcript_text = ""

def update_transcript():
    st.session_state.transcript_text = st.session_state.transcript_input

with st.container():
    st.text_area("Paste your meeting transcript here", value=st.session_state.transcript_text,
                 height=250, key="transcript_input", on_change=update_transcript)
    uploaded = st.file_uploader("Or upload a file", type=["txt","docx","pdf"])
    if uploaded:
        st.session_state.transcript_text = load_transcript(uploaded)
        # Força atualização do text_area na próxima execução
    if st.button("🧹 Pré‑processar (sem LLM)"):
        if st.session_state.transcript_text.strip():
            from modules.transcript_preprocessor import preprocess as _prep
            pp = _prep(st.session_state.transcript_text)
            st.session_state["pp_result"] = pp
            st.session_state["curated_clean"] = pp.clean_text
            st.success("Pré‑processamento concluído.")
    if "pp_result" in st.session_state:
        pp = st.session_state["pp_result"]
        st.markdown(f"**Fillers removidos:** {pp.fillers_removed} | **Artefatos:** {pp.artifact_turns} | **Repetições:** {pp.repetitions_collapsed}")
        st.text_area("Texto pré‑processado (editável)", value=st.session_state.get("curated_clean", pp.clean_text),
                     height=200, key="curated_edit")
        st.session_state["curated_clean"] = st.session_state.curated_edit
        if st.button("✅ Usar texto curado"):
            st.session_state.transcript_text = st.session_state["curated_clean"]
            st.success("Texto curado ativado.")

    start = st.button("🚀 Generate Insights", type="primary")

# ── Pipeline ────────────────────────────────────────────────────────────────
if start and st.session_state.transcript_text.strip():
    # ... (aqui vai o código do pipeline, usando st.session_state para todas as configurações)
    # Exemplo:
    client_info = get_session_llm_client(st.session_state.selected_provider)
    hub = KnowledgeHub.new()
    hub.set_transcript(st.session_state.transcript_text)
    hub.meta.llm_provider = st.session_state.selected_provider
    if st.session_state.get("curated_clean") and st.session_state["curated_clean"] != st.session_state.transcript_text:
        hub.transcript_clean = st.session_state["curated_clean"]

    orchestrator = Orchestrator(client_info, st.session_state.provider_cfg)
    hub = orchestrator.run(hub,
                           output_language=st.session_state.output_language,
                           run_quality=st.session_state.run_quality,
                           run_bpmn=st.session_state.run_bpmn,
                           run_minutes=st.session_state.run_minutes,
                           run_requirements=st.session_state.run_requirements,
                           run_synthesizer=st.session_state.run_synthesizer)
    st.session_state["hub"] = hub

# ── Exibição dos resultados (usando st.session_state["hub"]) ────────────────
if "hub" in st.session_state:
    hub = st.session_state["hub"]
    # ... (todo o código de abas, exportação, etc., usando st.session_state.prefix, st.session_state.suffix) ...

# Footer
st.markdown("---")
st.markdown("Process2Diagram v4.5 • Multi-Agent", unsafe_allow_html=True)
