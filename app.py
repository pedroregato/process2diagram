## --- Process2Diagram v4.5 — Re‑runnable Agents + Custom Prefix/Suffix + Curadoria ---
## --- Sem st.rerun() explícito para evitar erro de SessionInfo ---

import sys
from pathlib import Path
import json
import subprocess as _sp
from datetime import date

import streamlit as st
import streamlit.components.v1 as components

# ── Fix import path ───────────────────────────────────────────────────────────
root_dir = Path(__file__).parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# ── Core imports ──────────────────────────────────────────────────────────────
from modules.session_security import render_api_key_gate, get_session_llm_client
from modules.config import AVAILABLE_PROVIDERS
from modules.ingest import load_transcript

# ── v3 Multi-agent imports ────────────────────────────────────────────────────
from core.knowledge_hub import KnowledgeHub, BPMNModel
from agents.orchestrator import Orchestrator
from agents.agent_bpmn import AgentBPMN
from agents.agent_validator import AgentValidator
from agents.agent_minutes import AgentMinutes
from agents.agent_mermaid import generate_mermaid

# ── BPMN viewer ──────────────────────────────────────────────────────────────
from modules.bpmn_viewer import preview_from_xml
from modules.mermaid_renderer import render_mermaid_block
from modules.bpmn_diagnostics import render_bpmn_diagnostics


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Process2Diagram | AI-Powered Process Mining",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Enhanced CSS (mesmo do anterior, omitido por brevidade) ───────────────────
# ... (mantenha o CSS exatamente como estava) ...


# ── Helper functions (mesmas) ─────────────────────────────────────────────────
def _grade_from_score(score: int) -> str:
    if score >= 90: return "A"
    if score >= 75: return "B"
    if score >= 60: return "C"
    if score >= 45: return "D"
    return "E"

def _render_highlighted_transcript(clean_text: str, inconsistencies: list, key: str) -> None:
    # ... (código original, sem mudanças) ...
    pass

def _copy_button(text: str, key: str, label: str = "📋 Copy to Clipboard") -> None:
    # ... (código original) ...
    pass

def _make_filename(base_name: str, ext: str, prefix: str, suffix: str) -> str:
    safe_base = base_name.replace(" ", "_")
    return f"{prefix}{safe_base}{suffix}.{ext.lstrip('.')}"


# ── Sidebar (sem mudanças) ───────────────────────────────────────────────────
# ... (mantenha o código da sidebar exatamente como estava) ...


# ── Main area ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <p class="main-title">Process2Diagram</p>
    <p class="sub-title">Transform meeting transcripts into professional process diagrams with AI agents.</p>
</div>
""", unsafe_allow_html=True)

if not get_session_llm_client(selected_provider):
    st.warning("👈 **Action Required:** Please enter your API key in the sidebar to unlock the agents.")
    st.stop()

# ── Input Section (sem rerun) ────────────────────────────────────────────────
if "transcript_text" not in st.session_state:
    st.session_state.transcript_text = ""

def update_transcript():
    st.session_state.transcript_text = st.session_state.transcript_input_area

with st.container():
    st.markdown("### 📥 Input Transcript")
    transcript_text = st.text_area(
        "Paste your meeting transcript here",
        value=st.session_state.transcript_text,
        placeholder="Speaker 1: Hello, let's discuss...",
        height=250,
        label_visibility="collapsed",
        key="transcript_input_area",
        on_change=update_transcript
    )
    
    col_btn1, col_btn2, _ = st.columns([1, 1, 2])
    with col_btn1:
        uploaded_file = st.file_uploader("Or upload a file", type=["txt", "docx", "pdf"], label_visibility="collapsed")
    
    if uploaded_file:
        file_content = load_transcript(uploaded_file)
        st.session_state.transcript_text = file_content
        # Não chama rerun; o Streamlit rerun automaticamente
    
    # Pré-processamento manual
    if st.button("🧹 Pré‑processar Transcrição (sem LLM)", use_container_width=True):
        if not st.session_state.transcript_text.strip():
            st.warning("Cole ou carregue uma transcrição primeiro.")
        else:
            from modules.transcript_preprocessor import preprocess as _preprocess
            pp_result = _preprocess(st.session_state.transcript_text)
            st.session_state["pp_result"] = pp_result
            st.session_state["curated_clean"] = pp_result.clean_text
            st.success("Pré‑processamento concluído! Revise abaixo.")
    
    # Curadoria
    if "pp_result" in st.session_state:
        pp = st.session_state["pp_result"]
        st.markdown("#### 🧹 Curadoria da Transcrição")
        stats_html = f"""
        <div style='display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:0.6rem'>
            <span style='background:#f1f5f9;padding:3px 10px;border-radius:20px'>
                <b>{pp.fillers_removed}</b> fillers removidos
            </span>
            <span style='background:#fef9c3;padding:3px 10px;border-radius:20px'>
                <b>{pp.artifact_turns}</b> artefatos <code>[?]</code>
            </span>
            <span style='background:#f1f5f9;padding:3px 10px;border-radius:20px'>
                <b>{pp.repetitions_collapsed}</b> repetições colapsadas
            </span>
        </div>
        """
        st.markdown(stats_html, unsafe_allow_html=True)
        for issue in pp.metadata_issues:
            st.warning(f"⚠️ {issue}")
        st.caption("Revise o texto pré‑processado abaixo. Itens com `[?]` são artefatos suspeitos. Edite à vontade.")
        
        col_orig, col_clean = st.columns(2)
        with col_orig:
            st.markdown("**Original (somente leitura)**")
            st.text_area("orig", value=st.session_state.transcript_text, height=300,
                         disabled=True, label_visibility="collapsed", key="ta_orig_pre")
        with col_clean:
            st.markdown("**Pré‑processada — edite aqui**")
            curated = st.text_area("clean", value=st.session_state.get("curated_clean", pp.clean_text),
                                   height=300, label_visibility="collapsed", key="ta_curated")
            st.session_state["curated_clean"] = curated
        
        if st.button("✅ Usar texto curado no pipeline", use_container_width=True):
            st.session_state.transcript_text = st.session_state["curated_clean"]
            st.success("Texto curado definido como transcrição principal. Agora clique em 'Generate Insights'.")
    
    with col_btn2:
        start_process = st.button("🚀 Generate Insights", type="primary", use_container_width=True)


# ── Processing Logic (sem rerun no final) ─────────────────────────────────────
if start_process and st.session_state.transcript_text.strip():
    # ... (todo o código de pipeline, igual ao anterior, mas remova o último st.rerun()) ...
    # Ao final, apenas armazene no session_state:
    st.session_state["hub"] = hub
    st.session_state["output_language"] = output_language
    # NÃO chame st.rerun()


# ── Re-run agent handler (sem rerun) ─────────────────────────────────────────
if "rerun_agent" in st.session_state:
    agent_to_rerun = st.session_state.pop("rerun_agent")
    hub = st.session_state.get("hub")
    # ... (código de re-execução) ...
    # Após atualizar hub:
    st.session_state["hub"] = hub
    # NÃO chame st.rerun()


# ── Results Display (sem mudanças) ───────────────────────────────────────────
if "hub" in st.session_state:
    # ... (todo o código de exibição, igual ao anterior) ...
    pass

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style='text-align:center; color:var(--text-muted); font-size:0.8rem; padding:1rem;'>
    Process2Diagram v4.5 • Powered by Multi-Agent AI Architecture • 2024
</div>
""", unsafe_allow_html=True)
