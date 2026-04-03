## --- Process2Diagram v4.6 — Final (sem SessionInfo error) ---

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

# ── Multi-agent imports ───────────────────────────────────────────────────────
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


# ═══════════════════════════════════════════════════════════════════════════════
# INICIALIZAÇÃO OBRIGATÓRIA DO SESSION_STATE (APÓS set_page_config)
# ═══════════════════════════════════════════════════════════════════════════════
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
if "transcript_text" not in st.session_state:
    st.session_state.transcript_text = ""


# ── Enhanced CSS (moderno, legível) ──────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');
    :root {
        --primary: #2563eb;
        --secondary: #64748b;
        --background: #f8fafc;
        --card-bg: #ffffff;
        --text-main: #1e293b;
        --text-muted: #64748b;
        --border: #e2e8f0;
        --sidebar-bg: #0f172a;
        --sidebar-text: #f8fafc;
    }
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: var(--text-main); }
    section[data-testid="stSidebar"] { background-color: var(--sidebar-bg); border-right: 1px solid #1e293b; }
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] .stMarkdown p, section[data-testid="stSidebar"] .stText p {
        color: var(--sidebar-text) !important;
    }
    section[data-testid="stSidebar"] .stMarkdown strong { color: #ffffff !important; }
    section[data-testid="stSidebar"] label p { color: #cbd5e1 !important; font-weight: 600 !important; }
    .main-header { padding: 1.5rem 0 2rem 0; border-bottom: 1px solid var(--border); margin-bottom: 2rem; }
    .main-title { font-size: 2.5rem; font-weight: 800; background: linear-gradient(90deg, #2563eb 0%, #7c3aed 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
    .sub-title { font-size: 1.1rem; color: var(--text-muted); }
    .stTabs [data-baseweb="tab"] { background-color: #f1f5f9; border-radius: 8px 8px 0 0; padding: 10px 20px; font-weight: 500; }
    .stTabs [aria-selected="true"] { background-color: var(--card-bg) !important; color: var(--primary) !important; border-bottom: 2px solid var(--primary) !important; }
    .stTextArea textarea { font-family: 'JetBrains Mono', monospace !important; border-radius: 8px !important; }
    .stButton button { border-radius: 8px !important; font-weight: 500 !important; transition: all 0.2s ease; }
    .stButton button:hover { border-color: var(--primary) !important; color: var(--primary) !important; transform: translateY(-1px); }
    .badge { display: inline-block; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; }
    .badge-blue { background: #dbeafe; color: #1e40af; }
    .badge-green { background: #dcfce7; color: #166534; }
</style>
""", unsafe_allow_html=True)


# ── Helper functions ──────────────────────────────────────────────────────────
def _grade_from_score(score: int) -> str:
    if score >= 90: return "A"
    if score >= 75: return "B"
    if score >= 60: return "C"
    if score >= 45: return "D"
    return "E"

def _render_highlighted_transcript(clean_text: str, inconsistencies: list, key: str) -> None:
    import html as _html
    if not inconsistencies:
        components.html(
            f"<div style='height:400px;overflow-y:scroll;font-family:\"JetBrains Mono\",monospace;"
            f"font-size:0.85rem;line-height:1.6;padding:1.5rem;border:1px solid #e2e8f0;border-radius:12px;background:#f8fafc'>"
            f"{_html.escape(clean_text).replace(chr(10), '<br>')}</div>",
            height=420,
        )
        return
    spans = []
    for inc in inconsistencies:
        candidates = [f"[? {inc.text.rstrip('.')}]", f"[? {inc.text}]", inc.text]
        for cand in candidates:
            idx = clean_text.find(cand)
            if idx >= 0:
                spans.append((idx, idx + len(cand), inc.reason))
                break
    spans.sort(key=lambda s: s[0])
    merged = []
    for s in spans:
        if merged and s[0] < merged[-1][1]:
            continue
        merged.append(s)
    parts = []
    prev = 0
    for start, end, reason in merged:
        parts.append(_html.escape(clean_text[prev:start]))
        tooltip = _html.escape(reason[:120])
        highlighted = _html.escape(clean_text[start:end])
        parts.append(f'<mark title="{tooltip}" style="background:#fef08a;border-radius:4px;cursor:help;padding:2px 4px;border-bottom:2px solid #eab308">{highlighted}</mark>')
        prev = end
    parts.append(_html.escape(clean_text[prev:]))
    body = "".join(parts).replace("\n", "<br>")
    components.html(
        f"<div style='height:400px;overflow-y:scroll;font-family:\"JetBrains Mono\",monospace;"
        f"font-size:0.85rem;line-height:1.6;padding:1.5rem;border:1px solid #e2e8f0;border-radius:12px;background:#f8fafc'>"
        f"{body}</div>",
        height=420,
    )

def _copy_button(text: str, key: str, label: str = "📋 Copy to Clipboard") -> None:
    import json as _json
    safe = _json.dumps(text)
    components.html(
        f"""
        <button id="cbtn_{key}"
          onclick="(function(){{
            var el = document.createElement('textarea');
            el.value = {safe};
            el.style.position='fixed'; el.style.opacity='0';
            document.body.appendChild(el);
            el.focus(); el.select();
            try {{ document.execCommand('copy'); }} catch(e) {{}}
            document.body.removeChild(el);
            var b = document.getElementById('cbtn_{key}');
            b.innerHTML = '✅ Copied!';
            b.style.borderColor = '#22c55e';
            b.style.color = '#22c55e';
            setTimeout(function(){{ 
                b.innerHTML = '{label}'; 
                b.style.borderColor = '#cbd5e1';
                b.style.color = '#475569';
            }}, 2000);
          }})()"
          style="padding:8px 16px;border:1px solid #cbd5e1;border-radius:8px;
                 background:#ffffff;cursor:pointer;font-size:0.85rem;
                 font-family:'Inter',sans-serif;font-weight:500;color:#475569;">
          {label}
        </button>
        """,
        height=45,
    )

def _make_filename(base_name: str, ext: str, prefix: str, suffix: str) -> str:
    safe_base = base_name.replace(" ", "_")
    return f"{prefix}{safe_base}{suffix}.{ext.lstrip('.')}"


# ── SIDEBAR (atualiza session_state) ──────────────────────────────────────────
with st.sidebar:
    _commit = _sp.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip() or "v4.6"
    st.markdown(f"<h2 style='margin:0; color:#fff;'>⚡ Process2Diagram</h2><p style='color:#cbd5e1;'>Build {_commit} — Multi-Agent</p>", unsafe_allow_html=True)
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
    st.caption("🔒 API keys are session-only and never stored.")
    st.session_state.show_dev_tools = st.checkbox("🛠️ Developer Mode", value=st.session_state.show_dev_tools)
    if st.session_state.show_dev_tools:
        st.session_state.show_raw_json = st.checkbox("Show Raw JSON", value=st.session_state.show_raw_json)

    # ── SEÇÃO DE REEXECUÇÃO (aparece somente após o pipeline) ────────────────
    if "hub" in st.session_state:
        st.markdown("---")
        st.markdown("### 🔄 Re‑run Agents")
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            if st.button("🔬 Quality", use_container_width=True, key="rerun_quality"):
                st.session_state["rerun_agent"] = "quality"
            if st.button("📐 BPMN", use_container_width=True, key="rerun_bpmn"):
                st.session_state["rerun_agent"] = "bpmn"
            if st.button("📋 Minutes", use_container_width=True, key="rerun_minutes"):
                st.session_state["rerun_agent"] = "minutes"
        with col_r2:
            if st.button("📝 Requirements", use_container_width=True, key="rerun_requirements"):
                st.session_state["rerun_agent"] = "requirements"
            if st.button("📄 Report", use_container_width=True, key="rerun_synthesizer"):
                st.session_state["rerun_agent"] = "synthesizer"
        st.caption("⚠️ Re-running overwrites previous output for that agent.")


# ── MAIN AREA ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <p class="main-title">Process2Diagram</p>
    <p class="sub-title">Transform meeting transcripts into professional process diagrams with AI agents.</p>
</div>
""", unsafe_allow_html=True)

# Verifica API key
if not get_session_llm_client(st.session_state.selected_provider):
    st.warning("👈 **Action Required:** Please enter your API key in the sidebar to unlock the agents.")
    st.stop()

# ── INPUT SECTION (com curadoria e reset no upload) ───────────────────────────
def update_transcript():
    st.session_state.transcript_text = st.session_state.transcript_input

with st.container():
    st.markdown("### 📥 Input Transcript")
    st.text_area(
        "Paste your meeting transcript here",
        value=st.session_state.transcript_text,
        height=250,
        key="transcript_input",
        on_change=update_transcript,
        label_visibility="collapsed"
    )
    col_up, col_btn = st.columns([1, 1])
    with col_up:
        uploaded_file = st.file_uploader("Or upload a file", type=["txt","docx","pdf"], label_visibility="collapsed")
        if uploaded_file:
            # Carrega conteúdo do novo arquivo
            file_content = load_transcript(uploaded_file)
            # Substitui a transcrição
            st.session_state.transcript_text = file_content
            # Remove dados antigos de pré-processamento e curadoria
            st.session_state.pop("pp_result", None)
            st.session_state.pop("curated_clean", None)
            # Remove hub antigo para evitar exibição de resultados desatualizados
            st.session_state.pop("hub", None)
    with col_btn:
        preproc = st.button("🧹 Pré‑processar Transcrição (sem LLM)", use_container_width=True)
        if preproc and st.session_state.transcript_text.strip():
            from modules.transcript_preprocessor import preprocess as _prep
            pp = _prep(st.session_state.transcript_text)
            st.session_state["pp_result"] = pp
            st.session_state["curated_clean"] = pp.clean_text
            st.success("Pré‑processamento concluído! Revise abaixo.")
    
    if "pp_result" in st.session_state:
        pp = st.session_state["pp_result"]
        st.markdown("#### 🧹 Curadoria da Transcrição")
        st.markdown(
            f"<div style='display:flex;gap:1rem;margin-bottom:0.6rem'>"
            f"<span style='background:#f1f5f9;padding:3px 10px;border-radius:20px'><b>{pp.fillers_removed}</b> fillers</span>"
            f"<span style='background:#fef9c3;padding:3px 10px;border-radius:20px'><b>{pp.artifact_turns}</b> artefatos</span>"
            f"<span style='background:#f1f5f9;padding:3px 10px;border-radius:20px'><b>{pp.repetitions_collapsed}</b> repetições</span>"
            f"</div>", unsafe_allow_html=True)
        for issue in pp.metadata_issues:
            st.warning(f"⚠️ {issue}")
        st.caption("Revise o texto pré‑processado. Itens `[?]` são artefatos suspeitos.")
        col_orig, col_clean = st.columns(2)
        with col_orig:
            st.markdown("**Original (somente leitura)**")
            st.text_area("orig", value=st.session_state.transcript_text, height=300, disabled=True, key="orig_ro")
        with col_clean:
            st.markdown("**Pré‑processada — edite aqui**")
            curated = st.text_area("clean", value=st.session_state.get("curated_clean", pp.clean_text), height=300, key="curated_edit")
            st.session_state["curated_clean"] = curated
        if st.button("✅ Usar texto curado no pipeline", use_container_width=True):
            st.session_state.transcript_text = st.session_state["curated_clean"]
            st.success("Texto curado definido como transcrição principal. Clique em 'Generate Insights'.")

    start_process = st.button("🚀 Generate Insights", type="primary", use_container_width=True)


# ── PLACEHOLDER PARA PROGRESSO (fora do if) ───────────────────────────────────
progress_placeholder = st.empty()

# ── PIPELINE PRINCIPAL ────────────────────────────────────────────────────────
if start_process and st.session_state.transcript_text.strip():
    if not (st.session_state.run_quality or st.session_state.run_bpmn or st.session_state.run_minutes or st.session_state.run_requirements or st.session_state.run_synthesizer):
        st.warning("Please select at least one agent in the sidebar.")
        st.stop()

    client_info = get_session_llm_client(st.session_state.selected_provider)
    if client_info is None:
        st.error("API key not found or invalid. Please re-enter your key in the sidebar.")
        st.stop()

    hub = KnowledgeHub.new()
    hub.set_transcript(st.session_state.transcript_text)
    if st.session_state.get("curated_clean") and st.session_state["curated_clean"] != st.session_state.transcript_text:
        hub.transcript_clean = st.session_state["curated_clean"]
    hub.meta.llm_provider = st.session_state.selected_provider

    agent_status = {}
    def update_progress(step_name: str, status: str):
        agent_status[step_name] = status
        icons = {"running": "⏳", "done": "✅", "error": "❌"}
        lines = []
        for name, st_val in agent_status.items():
            icon = next((v for k, v in icons.items() if k in st_val), "🔵")
            lines.append(f"{icon} **{name}** — {st_val}")
        progress_placeholder.markdown("  \n".join(lines))

    try:
        orchestrator = Orchestrator(
            client_info=client_info,
            provider_cfg=st.session_state.provider_cfg,
            progress_callback=update_progress,
        )

        if st.session_state.run_bpmn and st.session_state.n_bpmn_runs > 1:
            import copy as _copy
            _validator = AgentValidator()
            _agent_bpmn = AgentBPMN(client_info, st.session_state.provider_cfg)

            # Roda qualidade + NLP primeiro
            hub = orchestrator.run(
                hub,
                output_language=st.session_state.output_language,
                run_quality=st.session_state.run_quality,
                run_bpmn=False,
                run_minutes=False,
                run_requirements=False,
                run_synthesizer=False,
            )

            candidates = []
            for i in range(st.session_state.n_bpmn_runs):
                update_progress("BPMN Agent", f"pass {i+1}/{st.session_state.n_bpmn_runs}…")
                hub_c = _copy.copy(hub)
                hub_c.bpmn = BPMNModel()
                hub_c = _agent_bpmn.run(hub_c, st.session_state.output_language)
                score = _validator.score(hub_c.bpmn, hub_c.transcript_clean, st.session_state.bpmn_weights)
                score.run_index = i + 1
                candidates.append((score, hub_c.bpmn))

            best_score, best_bpmn = max(candidates, key=lambda x: x[0].weighted)
            hub.bpmn = best_bpmn
            hub.validation.bpmn_score = best_score
            hub.validation.bpmn_candidates = [c[0] for c in candidates]
            hub.validation.n_bpmn_runs = st.session_state.n_bpmn_runs
            hub.validation.ready = True
            hub.bump()
            update_progress(
                "BPMN Agent",
                f"done — pass {best_score.run_index}/{st.session_state.n_bpmn_runs} selected (score {best_score.weighted:.1f}/10)",
            )

            # Roda os demais agentes
            hub = orchestrator.run(
                hub,
                output_language=st.session_state.output_language,
                run_quality=False,
                run_bpmn=False,
                run_minutes=st.session_state.run_minutes,
                run_requirements=st.session_state.run_requirements,
                run_synthesizer=st.session_state.run_synthesizer,
            )
        else:
            hub = orchestrator.run(
                hub,
                output_language=st.session_state.output_language,
                run_quality=st.session_state.run_quality,
                run_bpmn=st.session_state.run_bpmn,
                run_minutes=st.session_state.run_minutes,
                run_requirements=st.session_state.run_requirements,
                run_synthesizer=st.session_state.run_synthesizer,
            )

        # Resumo final
        done = [n for n, s in agent_status.items() if "done" in s]
        errors = [n for n, s in agent_status.items() if "error" in s]
        summary = f"✅ {len(done)} agent(s) completed"
        if errors:
            summary += f" · ⚠️ {len(errors)} errors: {', '.join(errors)}"
        summary += f" · 🔢 {hub.meta.total_tokens_used:,} tokens · ⏱️ {hub.meta.processing_time_ms // 1000}s"
        progress_placeholder.success(summary)

        st.session_state["hub"] = hub
        st.session_state["output_language"] = st.session_state.output_language

    except Exception as e:
        progress_placeholder.error(f"Pipeline error: {e}")
        st.exception(e)
        st.stop()


# ── RE‑RUN AGENT HANDLER (invalida relatório quando BPMN muda) ────────────────
if "rerun_agent" in st.session_state:
    agent_to_rerun = st.session_state.pop("rerun_agent")
    hub = st.session_state.get("hub")
    if hub is None:
        st.error("No existing session found. Please run the full pipeline first.")
        st.stop()
    client_info = get_session_llm_client(st.session_state.selected_provider)
    if client_info is None:
        st.error("API key not found. Please re-enter your key.")
        st.stop()
    output_language = st.session_state.get("output_language", "Auto-detect")
    with st.spinner(f"Re‑running {agent_to_rerun} agent..."):
        try:
            if agent_to_rerun == "quality":
                from agents.agent_transcript_quality import AgentTranscriptQuality
                agent = AgentTranscriptQuality(client_info, st.session_state.provider_cfg)
                hub = agent.run(hub, output_language)
            elif agent_to_rerun == "bpmn":
                agent = AgentBPMN(client_info, st.session_state.provider_cfg)
                hub = agent.run(hub, output_language)
                # Invalida o relatório existente porque o BPMN mudou
                try:
                    from core.knowledge_hub import SynthesizerModel
                    hub.synthesizer = SynthesizerModel()
                except ImportError:
                    from dataclasses import dataclass, field
                    @dataclass
                    class _SM:
                        executive_summary: str = ""
                        process_narrative: str = ""
                        key_insights: list = field(default_factory=list)
                        recommendations: list = field(default_factory=list)
                        html: str = ""
                        ready: bool = False
                    hub.synthesizer = _SM()
                hub.synthesizer.ready = False
                st.info("ℹ️ Executive report invalidated due to BPMN change. Re-run Report to generate a new one.")
            elif agent_to_rerun == "minutes":
                agent = AgentMinutes(client_info, st.session_state.provider_cfg)
                hub = agent.run(hub, output_language)
            elif agent_to_rerun == "requirements":
                from agents.agent_requirements import AgentRequirements
                agent = AgentRequirements(client_info, st.session_state.provider_cfg)
                hub = agent.run(hub, output_language)
            elif agent_to_rerun == "synthesizer":
                from agents.agent_synthesizer import AgentSynthesizer
                agent = AgentSynthesizer(client_info, st.session_state.provider_cfg)
                hub = agent.run(hub, output_language)
            st.session_state["hub"] = hub
            st.success(f"✅ {agent_to_rerun.capitalize()} agent re-run complete.")
        except Exception as e:
            st.error(f"Error re‑running {agent_to_rerun}: {e}")


# ── RESULTS DISPLAY (fora do bloco de processamento) ──────────────────────────
if "hub" in st.session_state:
    hub = st.session_state["hub"]
    hub = KnowledgeHub.migrate(hub)
    # Garante campos obrigatórios
    if not hasattr(hub, 'transcript_quality'):
        from core.knowledge_hub import TranscriptQualityModel
        hub.transcript_quality = TranscriptQualityModel()
    if not hasattr(hub, 'synthesizer'):
        try:
            from core.knowledge_hub import SynthesizerModel
            hub.synthesizer = SynthesizerModel()
        except ImportError:
            from dataclasses import dataclass, field
            @dataclass
            class _SM:
                executive_summary: str = ""
                process_narrative: str = ""
                key_insights: list = field(default_factory=list)
                recommendations: list = field(default_factory=list)
                html: str = ""
                ready: bool = False
            hub.synthesizer = _SM()

    # Verifica se pelo menos um agente gerou saída
    any_ready = any([
        hub.transcript_quality.ready if hasattr(hub, 'transcript_quality') else False,
        hub.bpmn.ready if hasattr(hub, 'bpmn') else False,
        hub.minutes.ready if hasattr(hub, 'minutes') else False,
        hub.requirements.ready if hasattr(hub, 'requirements') else False,
        hub.synthesizer.ready if hasattr(hub, 'synthesizer') else False,
    ])
    if not any_ready:
        st.error("No agent produced output. Check API key and logs.")
        st.json({"agents_run": hub.meta.agents_run, "tokens": hub.meta.total_tokens_used})
        st.stop()

    # Métricas rápidas
    col_a, col_b, col_c, col_d = st.columns(4)
    if hub.bpmn.ready:
        col_a.metric("BPMN Steps", len(hub.bpmn.steps))
        col_b.metric("Connections", len(hub.bpmn.edges))
        actors = list(set(s.actor for s in hub.bpmn.steps if s.actor))
        col_c.metric("Actors", len(actors))
    if hub.minutes.ready:
        col_d.metric("Action Items", len(hub.minutes.action_items))

    # Monta abas
    tabs_to_show = []
    if hub.transcript_quality.ready:
        tabs_to_show.append("🔬 Quality")
    if hub.bpmn.ready:
        tabs_to_show.append("📐 BPMN 2.0")
        tabs_to_show.append("📊 Mermaid")
        if hub.validation.ready and hub.validation.n_bpmn_runs > 1:
            tabs_to_show.append("🏆 BPMN Validation")
    if hub.minutes.ready:
        tabs_to_show.append("📋 Minutes")
    if hub.requirements.ready:
        tabs_to_show.append("📝 Requirements")
    if hub.synthesizer.ready:
        tabs_to_show.append("📄 Executive Report")
    tabs_to_show.append("📦 Export")
    if st.session_state.show_dev_tools:
        tabs_to_show.append("🔍 Knowledge Hub")

    tabs = st.tabs(tabs_to_show)
    tab_idx = 0

    # ── Tab: Quality (igual ao anterior, omitido por brevidade) ───────────────
    if hub.transcript_quality.ready:
        with tabs[tab_idx]:
            tq = hub.transcript_quality
            pp = getattr(hub, 'preprocessing', None)
            grade_colors = {"A":"#16a34a","B":"#65a30d","C":"#ca8a04","D":"#ea580c","E":"#dc2626"}
            grade_color = grade_colors.get(tq.grade, "#64748b")
            col_q1, col_q2 = st.columns([1,3])
            with col_q1:
                st.markdown(f"<div style='text-align:center;padding:2rem;background:{grade_color}10;border-radius:16px;border:2px solid {grade_color}'>"
                            f"<div style='font-size:4rem;font-weight:800;color:{grade_color}'>{tq.grade}</div>"
                            f"<div style='font-size:1.2rem;font-weight:600;color:{grade_color}'>{tq.overall_score:.1f}/100</div></div>", unsafe_allow_html=True)
            with col_q2:
                st.markdown("### Evaluation Criteria")
                for c in tq.criteria:
                    with st.expander(f"**{c.criterion}** — {c.score}/100"):
                        st.progress(c.score/100)
                        st.markdown(c.justification)
            st.markdown("---")
            col_sum, col_rec = st.columns(2)
            col_sum.info(tq.overall_summary)
            if tq.grade in ["A","B"]:
                col_rec.success(tq.recommendation)
            elif tq.grade in ["C","D"]:
                col_rec.warning(tq.recommendation)
            else:
                col_rec.error(tq.recommendation)
            if tq.inconsistencies:
                st.markdown(f"### 🔍 AI‑Detected Inconsistencies  `{len(tq.inconsistencies)}`")
                for inc in tq.inconsistencies:
                    with st.expander(f"**{inc.speaker}** `{inc.timestamp}` — *{inc.text}*"):
                        st.markdown(f"**Reason:** {inc.reason}")
            if pp and pp.ready:
                st.markdown("### 🧹 Automated Pre-processing")
                c1,c2,c3 = st.columns(3)
                c1.metric("Fillers Removed", pp.fillers_removed)
                c2.metric("Artifacts Flagged", pp.artifact_turns)
                c3.metric("Repetitions Collapsed", pp.repetitions_collapsed)
                col_raw, col_clean = st.columns(2)
                with col_raw:
                    st.markdown("**Original Transcript**")
                    st.text_area("raw", hub.transcript_raw, height=400, disabled=True, key="ta_raw")
                    _copy_button(hub.transcript_raw, key="tab_orig")
                    st.download_button("⬇️ Original (.txt)", data=hub.transcript_raw,
                                       file_name=_make_filename("transcricao_original", "txt", st.session_state.prefix, st.session_state.suffix),
                                       key="dl_raw")
                with col_clean:
                    st.markdown("**Cleaned Transcript** (hover for issues)")
                    _render_highlighted_transcript(hub.transcript_clean, tq.inconsistencies, key="hl_quality")
                    _copy_button(hub.transcript_clean, key="tab_clean")
                    st.download_button("⬇️ Cleaned (.txt)", data=hub.transcript_clean,
                                       file_name=_make_filename("transcricao_preprocessada", "txt", st.session_state.prefix, st.session_state.suffix),
                                       key="dl_clean")
        tab_idx += 1

    # ── Tab: BPMN 2.0 (igual ao anterior) ─────────────────────────────────────
    if hub.bpmn.ready:
        with tabs[tab_idx]:
            st.markdown("<h3>📐 BPMN Process Model</h3><span class='badge badge-blue'>Interactive Viewer</span>", unsafe_allow_html=True)
            if hub.bpmn.bpmn_xml:
                bpmn_html = preview_from_xml(hub.bpmn.bpmn_xml)
                components.html(bpmn_html, height=800, scrolling=False)
                if hub.bpmn.lanes:
                    st.markdown("**Identified Roles:** " + " ".join([f"<span class='badge badge-green'>{l}</span>" for l in hub.bpmn.lanes]), unsafe_allow_html=True)
            else:
                st.warning("BPMN XML not available. Showing Mermaid fallback.")
                render_mermaid_block(hub.bpmn.mermaid, show_code=False, key_suffix="bpmn_fallback")
        tab_idx += 1
        with tabs[tab_idx]:
            st.markdown("### 📊 Mermaid Flowchart")
            render_mermaid_block(hub.bpmn.mermaid, show_code=True, key_suffix="mermaid_tab")
        tab_idx += 1
        if hub.validation.ready and hub.validation.n_bpmn_runs > 1:
            with tabs[tab_idx]:
                val = hub.validation
                st.markdown(f"### Selection among {val.n_bpmn_runs} passes")
                best = val.bpmn_score
                rows = []
                for c in sorted(val.bpmn_candidates, key=lambda x: x.weighted, reverse=True):
                    rows.append({
                        "Pass": f"{'⭐ ' if c.run_index == best.run_index else ''}{c.run_index}",
                        "Granularity": f"{c.granularity:.1f}",
                        "Task Type": f"{c.task_type:.1f}",
                        "Gateways": f"{c.gateways:.1f}",
                        "Final Score": f"{c.weighted:.2f}",
                        "Activities": c.n_tasks,
                        "Gateways #": c.n_gateways,
                    })
                st.dataframe(rows, use_container_width=True)
                st.caption(f"Pass **{best.run_index}** selected · Score {best.weighted:.2f}/10")
            tab_idx += 1

    # ── Tab: Minutes (igual ao anterior) ──────────────────────────────────────
    if hub.minutes.ready:
        with tabs[tab_idx]:
            m = hub.minutes
            st.markdown(f"## {m.title}")
            col_m1, col_m2, col_m3 = st.columns(3)
            col_m1.markdown(f"**📅 Date:** {m.date or 'N/A'}")
            col_m2.markdown(f"**📍 Location:** {m.location or 'N/A'}")
            col_m3.markdown(f"**👥 Participants:** {len(m.participants)}")
            st.markdown("### 📌 Agenda")
            for i, item in enumerate(m.agenda, 1):
                st.markdown(f"{i}. {item}")
            st.markdown("### 📝 Summary")
            for block in m.summary:
                st.markdown(f"**{block.get('topic', '')}**")
                st.markdown(block.get("content", ""))
            if m.decisions:
                st.markdown("### ✅ Key Decisions")
                for d in m.decisions:
                    st.markdown(f"- {d}")
            if m.action_items:
                st.markdown("### 🎯 Action Items")
                prio_map = {"high":"🔴 High","normal":"🟡 Normal","low":"🟢 Low"}
                rows = []
                for ai in m.action_items:
                    rows.append({
                        "Priority": prio_map.get(ai.priority, "⚪"),
                        "Task": ai.task,
                        "Owner": ai.responsible,
                        "Deadline": ai.deadline or "—"
                    })
                st.dataframe(rows, use_container_width=True)
            st.markdown("---")
            st.markdown("### 📎 Export Minutes")
            md_content = AgentMinutes.to_markdown(m)
            col_exp1, col_exp2, col_exp3 = st.columns(3)
            with col_exp1:
                st.download_button("⬇️ .md", data=md_content,
                                   file_name=_make_filename("minutes", "md", st.session_state.prefix, st.session_state.suffix),
                                   use_container_width=True, key="dl_minutes_md")
            with col_exp2:
                try:
                    from modules.minutes_exporter import to_docx
                    st.download_button("⬇️ .docx", data=to_docx(m),
                                       file_name=_make_filename("minutes", "docx", st.session_state.prefix, st.session_state.suffix),
                                       use_container_width=True, key="dl_minutes_docx")
                except Exception as e:
                    st.caption(f"DOCX unavailable: {e}")
            with col_exp3:
                try:
                    from modules.minutes_exporter import to_pdf
                    st.download_button("⬇️ .pdf", data=to_pdf(m),
                                       file_name=_make_filename("minutes", "pdf", st.session_state.prefix, st.session_state.suffix),
                                       use_container_width=True, key="dl_minutes_pdf")
                except Exception as e:
                    st.caption(f"PDF unavailable: {e}")
        tab_idx += 1

    # ── Tab: Requirements (com Mind Map interativo e fallback) ─────────────────
    if hub.requirements.ready:
        with tabs[tab_idx]:
            req = hub.requirements
            if not req.requirements:
                st.warning("Nenhum requisito foi extraído da transcrição.")
            else:
                type_labels = {"ui_field":"🖥️ UI Field","validation":"✅ Validation","business_rule":"📋 Business Rule",
                               "functional":"⚙️ Functional","non_functional":"📊 Non-functional"}
                priority_colors = {"high":"🔴","medium":"🟡","low":"🟢","unspecified":"⚪"}
                c1,c2,c3 = st.columns(3)
                c1.metric("Total Requirements", len(req.requirements))
                c2.metric("High Priority", sum(1 for r in req.requirements if r.priority=="high"))
                c3.metric("Distinct Types", len(set(r.type for r in req.requirements)))

                selected_type = st.selectbox("Filter by type", ["All"]+list(type_labels.values()), key="req_type_filter")
                type_reverse = {v:k for k,v in type_labels.items()}
                rows = []
                for r in req.requirements:
                    if selected_type!="All" and r.type!=type_reverse.get(selected_type):
                        continue
                    rows.append({
                        "ID": r.id,
                        "Type": type_labels.get(r.type, r.type),
                        "Priority": priority_colors.get(r.priority,"⚪"),
                        "Title": r.title,
                        "Process Step": r.process_step or "—",
                        "Actor": r.actor or "—",
                    })
                if rows:
                    st.dataframe(rows, use_container_width=True)

                st.markdown("---")
                st.markdown("### Detailed View")
                for r in req.requirements:
                    if selected_type!="All" and r.type!=type_reverse.get(selected_type):
                        continue
                    with st.expander(f"{r.id} — {r.title}  {priority_colors.get(r.priority,'')}"):
                        st.markdown(f"**Type:** {type_labels.get(r.type, r.type)}")
                        st.markdown(f"**Priority:** {priority_colors.get(r.priority,'⚪')} {r.priority}")
                        if r.actor:
                            st.markdown(f"**Actor:** {r.actor}")
                        if r.process_step:
                            st.markdown(f"**Process step:** {r.process_step}")
                        st.markdown(f"**Description:** {r.description}")
                        if r.source_quote:
                            speaker_tag = f"**[{r.speaker}]** " if r.speaker else ""
                            st.markdown(f"> {speaker_tag}*\"{r.source_quote}\"*")

                # Mind Map
                st.markdown("---")
                st.markdown("### 🗺️ Mind Map dos Requisitos")
                try:
                    from modules.mindmap_interactive import render_mindmap_from_requirements
                    session_title = getattr(req, 'session_title', '') or req.name
                    render_mindmap_from_requirements(req, session_title=session_title, height=540)
                except Exception as e:
                    st.warning(f"Mindmap interativo indisponível: {e}. Exibindo código Mermaid.")
                    from modules.requirements_mindmap import generate_requirements_mindmap
                    mindmap_code = generate_requirements_mindmap(req)
                    if mindmap_code:
                        st.code(mindmap_code, language="mermaid")
                    else:
                        st.info("Mind map não disponível (sem dados suficientes).")
        tab_idx += 1

    # ── Tab: Executive Report ─────────────────────────────────────────────────
    if hub.synthesizer.ready:
        with tabs[tab_idx]:
            syn = hub.synthesizer
            st.markdown("### 📄 Executive Report")
            st.caption("AI-generated executive summary of all artifacts.")
            st.download_button("⬇️ Download Report (.html)", data=syn.html,
                               file_name=_make_filename("executive_report", "html", st.session_state.prefix, st.session_state.suffix),
                               use_container_width=True, key="dl_report_tab")
            st.divider()
            components.html(syn.html, height=800, scrolling=True)
        tab_idx += 1

    # ── Tab: Export ───────────────────────────────────────────────────────────
    with tabs[tab_idx]:
        st.markdown("### 📦 Export Assets")
        if hub.bpmn.ready:
            st.markdown("**Process Models**")
            col1, col2 = st.columns(2)
            with col1:
                if hub.bpmn.bpmn_xml:
                    st.download_button("⬇️ .bpmn", data=hub.bpmn.bpmn_xml,
                                       file_name=_make_filename("process", "bpmn", st.session_state.prefix, st.session_state.suffix),
                                       use_container_width=True, key="dl_bpmn")
            with col2:
                mermaid_content = generate_mermaid(hub.bpmn)
                st.download_button("⬇️ .mermaid", data=mermaid_content,
                                   file_name=_make_filename("process", "mmd", st.session_state.prefix, st.session_state.suffix),
                                   use_container_width=True, key="dl_mermaid")
            st.markdown("---")
        if hub.minutes.ready:
            st.markdown("**Meeting Minutes**")
            md_content = AgentMinutes.to_markdown(hub.minutes)
            col_md, col_docx, col_pdf = st.columns(3)
            with col_md:
                st.download_button("⬇️ .md", data=md_content,
                                   file_name=_make_filename("minutes", "md", st.session_state.prefix, st.session_state.suffix),
                                   use_container_width=True, key="dl_minutes_md_export")
            with col_docx:
                try:
                    from modules.minutes_exporter import to_docx
                    st.download_button("⬇️ .docx", data=to_docx(hub.minutes),
                                       file_name=_make_filename("minutes", "docx", st.session_state.prefix, st.session_state.suffix),
                                       use_container_width=True, key="dl_minutes_docx_export")
                except Exception as e:
                    st.caption(f"DOCX unavailable: {e}")
            with col_pdf:
                try:
                    from modules.minutes_exporter import to_pdf
                    st.download_button("⬇️ .pdf", data=to_pdf(hub.minutes),
                                       file_name=_make_filename("minutes", "pdf", st.session_state.prefix, st.session_state.suffix),
                                       use_container_width=True, key="dl_minutes_pdf_export")
                except Exception as e:
                    st.caption(f"PDF unavailable: {e}")
            st.markdown("---")
        if hub.requirements.ready:
            st.markdown("**Requirements**")
            st.download_button("⬇️ Requirements (.md)", data=hub.requirements.markdown,
                               file_name=_make_filename("requirements", "md", st.session_state.prefix, st.session_state.suffix),
                               use_container_width=True, key="dl_req_md")
            req_json = json.dumps({"name": hub.requirements.name,
                                   "requirements": [r.__dict__ for r in hub.requirements.requirements]},
                                  ensure_ascii=False, indent=2)
            st.download_button("⬇️ Requirements (.json)", data=req_json,
                               file_name=_make_filename("requirements", "json", st.session_state.prefix, st.session_state.suffix),
                               use_container_width=True, key="dl_req_json")
            st.markdown("---")
        if hub.synthesizer.ready:
            st.markdown("**Executive Report**")
            st.download_button("⬇️ Report (.html)", data=hub.synthesizer.html,
                               file_name=_make_filename("executive_report", "html", st.session_state.prefix, st.session_state.suffix),
                               use_container_width=True, key="dl_report_export")
    tab_idx += 1

    # ── Tab: Knowledge Hub (dev mode) ─────────────────────────────────────────
    if st.session_state.show_dev_tools:
        with tabs[tab_idx]:
            st.markdown("### 🔍 Knowledge Hub — Session State")
            col_meta1, col_meta2, col_meta3 = st.columns(3)
            col_meta1.metric("Hub Version", hub.version)
            col_meta2.metric("Tokens Used", hub.meta.total_tokens_used)
            col_meta3.metric("Agents Executed", len(hub.meta.agents_run))
            st.markdown(f"**Provider:** `{hub.meta.llm_provider}` — **Model:** `{hub.meta.llm_model}`")
            st.markdown(f"**NLP Segments:** {len(hub.nlp.segments)} — **Actors:** {', '.join(hub.nlp.actors) or '—'} — **Language:** `{hub.nlp.language_detected}`")
            if st.session_state.show_raw_json:
                st.json(hub.to_dict())
            st.download_button("⬇️ Knowledge Hub (.json)", data=hub.to_json(),
                               file_name=_make_filename("knowledge_hub", "json", st.session_state.prefix, st.session_state.suffix),
                               key="dl_hub_json")
        tab_idx += 1


# ── FOOTER ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("<div style='text-align:center; color:var(--text-muted); font-size:0.8rem;'>Process2Diagram v4.6 • Powered by Multi-Agent AI Architecture • 2024</div>", unsafe_allow_html=True)
