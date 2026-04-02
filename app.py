## --- Process2Diagram v4.4 — Robust Multi-Agent UI (Fixed) ---
## --- Original UI improvements by Manus, processing logic corrected ---

import sys
from pathlib import Path
import json
import subprocess as _sp

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

# ── Enhanced CSS (Modern SaaS Look with Maximum Contrast) ─────────────────────
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
        --sidebar-label: #94a3b8;
    }

    html, body, [class*="css"] { 
        font-family: 'Inter', sans-serif; 
        color: var(--text-main);
    }

    /* Sidebar Styling - Maximum Contrast Refinement */
    section[data-testid="stSidebar"] {
        background-color: var(--sidebar-bg);
        border-right: 1px solid #1e293b;
    }
    
    /* Force Sidebar Headings & Labels to be visible */
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stText p {
        color: var(--sidebar-text) !important;
    }
    
    section[data-testid="stSidebar"] .stMarkdown strong,
    section[data-testid="stSidebar"] .stMarkdown em {
        color: #ffffff !important;
    }

    section[data-testid="stSidebar"] label p {
        color: #cbd5e1 !important;
        font-weight: 600 !important;
        font-size: 0.9rem !important;
    }

    section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        border-radius: 8px;
    }
    
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] div[role="button"],
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] span {
        color: #0f172a !important;
        font-weight: 500 !important;
    }

    section[data-testid="stSidebar"] .stCheckbox label span {
        color: #f8fafc !important;
        font-weight: 500 !important;
    }

    section[data-testid="stSidebar"] .stCaption,
    section[data-testid="stSidebar"] caption,
    section[data-testid="stSidebar"] .stMarkdown small {
        color: #94a3b8 !important;
        font-size: 0.8rem !important;
        display: block;
        margin-top: 0.5rem;
    }
    
    section[data-testid="stSidebar"] div[data-testid="stCaptionContainer"] {
        color: #cbd5e1 !important;
    }

    /* Main Title & Header */
    .main-header {
        padding: 1.5rem 0 2rem 0;
        border-bottom: 1px solid var(--border);
        margin-bottom: 2rem;
    }
    .main-title {
        font-size: 2.5rem;
        font-weight: 800;
        letter-spacing: -0.025em;
        background: linear-gradient(90deg, #2563eb 0%, #7c3aed 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.5rem;
    }
    .sub-title {
        font-size: 1.1rem;
        color: var(--text-muted);
        font-weight: 400;
    }

    /* Cards & Containers */
    .stMetric {
        background: var(--card-bg);
        padding: 1.25rem;
        border-radius: 12px;
        border: 1px solid var(--border);
        box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1);
    }
    
    .custom-card {
        background: var(--card-bg);
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid var(--border);
        margin-bottom: 1rem;
    }

    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
    }
    .stTabs [data-baseweb="tab"] {
        height: 45px;
        white-space: pre-wrap;
        background-color: #f1f5f9;
        border-radius: 8px 8px 0 0;
        gap: 1px;
        padding: 10px 20px;
        font-weight: 500;
        color: var(--text-muted);
        border: 1px solid transparent;
    }
    .stTabs [aria-selected="true"] {
        background-color: var(--card-bg) !important;
        color: var(--primary) !important;
        border: 1px solid var(--border) !important;
        border-bottom: 2px solid var(--primary) !important;
    }

    /* Code & Text Areas */
    .stTextArea textarea {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.9rem !important;
        border-radius: 8px !important;
        border: 1px solid var(--border) !important;
    }
    
    /* Buttons */
    .stButton button {
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease;
    }
    .stButton button:hover {
        border-color: var(--primary) !important;
        color: var(--primary) !important;
        transform: translateY(-1px);
    }

    /* Badges */
    .badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.025em;
    }
    .badge-blue { background: #dbeafe; color: #1e40af; }
    .badge-green { background: #dcfce7; color: #166534; }
    .badge-yellow { background: #fef9c3; color: #854d0e; }
</style>
""", unsafe_allow_html=True)


# ── Helpers (copied from original, adapted) ───────────────────────────────────
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
            f"font-size:0.85rem;line-height:1.6;padding:1.5rem;"
            f"border:1px solid #e2e8f0;border-radius:12px;background:#f8fafc;color:#334155'>"
            f"{_html.escape(clean_text).replace(chr(10), '<br>')}</div>",
            height=420,
        )
        return

    spans: list[tuple[int, int, str]] = []
    for inc in inconsistencies:
        candidates = [f"[? {inc.text.rstrip('.')}]", f"[? {inc.text}]", inc.text]
        for candidate in candidates:
            idx = clean_text.find(candidate)
            if idx >= 0:
                spans.append((idx, idx + len(candidate), inc.reason))
                break

    spans.sort(key=lambda s: s[0])
    merged: list[tuple[int, int, str]] = []
    for s in spans:
        if merged and s[0] < merged[-1][1]: continue
        merged.append(s)

    parts: list[str] = []
    prev = 0
    for start, end, reason in merged:
        parts.append(_html.escape(clean_text[prev:start]))
        tooltip = _html.escape(reason[:120])
        highlighted = _html.escape(clean_text[start:end])
        parts.append(
            f'<mark title="{tooltip}" style="background:#fef08a;border-radius:4px;'
            f'cursor:help;padding:2px 4px;border-bottom:2px solid #eab308">{highlighted}</mark>'
        )
        prev = end
    parts.append(_html.escape(clean_text[prev:]))

    body = "".join(parts).replace("\n", "<br>")
    components.html(
        f"<div style='height:400px;overflow-y:scroll;font-family:\"JetBrains Mono\",monospace;"
        f"font-size:0.85rem;line-height:1.6;padding:1.5rem;"
        f"border:1px solid #e2e8f0;border-radius:12px;background:#f8fafc;color:#334155'>"
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
                 font-family:'Inter',sans-serif;font-weight:500;color:#475569;
                 transition:all 0.2s ease;display:flex;align-items:center;gap:8px">
          {label}
        </button>
        """,
        height=45,
    )


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    _commit = _sp.run(["git", "rev-parse", "--short", "HEAD"],
                      capture_output=True, text=True).stdout.strip() or "v4.4"
    
    st.markdown(f"""
    <div style='padding: 1rem 0;'>
        <h2 style='margin:0; font-size:1.5rem; color: #ffffff;'>⚡ Process2Diagram</h2>
        <p style='color:#cbd5e1; font-size:0.85rem; margin-top:0.2rem;'>Build {_commit} — Multi-Agent</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")

    st.markdown("### 🤖 LLM Engine")
    provider_names = list(AVAILABLE_PROVIDERS.keys())
    selected_provider = st.selectbox(
        "Provider",
        provider_names,
        index=provider_names.index("DeepSeek") if "DeepSeek" in provider_names else 0,
        key="selected_provider",
    )

    provider_cfg = AVAILABLE_PROVIDERS[selected_provider]
    
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        st.caption("Model")
        st.code(provider_cfg['default_model'], language="text")
    with col_s2:
        st.caption("Cost")
        st.code(provider_cfg['cost_hint'], language="text")

    render_api_key_gate(selected_provider, provider_cfg)

    st.markdown("---")
    st.markdown("### ⚙️ Configuration")
    output_language = st.selectbox(
        "Output Language",
        ["Auto-detect", "Portuguese (BR)", "English"],
        key="output_language_select",
    )
    # Map to expected values by agents
    _lang_map = {"Auto-detect": "Auto-detect", "Portuguese (BR)": "Portuguese (BR)", "English": "English"}
    output_language = _lang_map.get(output_language, output_language)

    st.markdown("### 🤖 Active Agents")
    run_quality = st.checkbox("Quality Inspector", value=True)
    run_bpmn = st.checkbox("BPMN Architect", value=True)

    # Multi-run BPMN settings (same as original)
    n_bpmn_runs = 1
    bpmn_weights = {"granularity": 5, "task_type": 5, "gateways": 5}
    if run_bpmn:
        n_bpmn_runs = st.select_slider(
            "Optimization Passes", options=[1, 3, 5], value=1,
            help="Runs the BPMN Agent N times and selects the best result.",
        )
        if n_bpmn_runs > 1:
            with st.expander("Selection Weights"):
                bpmn_weights = {
                    "granularity": st.slider("Granularity", 0, 10, 5, key="w_gran"),
                    "task_type":   st.slider("Task Type", 0, 10, 5, key="w_type"),
                    "gateways":    st.slider("Gateways", 0, 10, 8, key="w_gw"),
                }

    run_minutes = st.checkbox("Meeting Minutes", value=True)
    run_requirements = st.checkbox("Requirements", value=True)
    run_synthesizer = st.checkbox("Executive Report", value=False)

    st.markdown("---")
    st.caption("🔒 API keys are session-only and never stored.")
    
    show_dev_tools = st.checkbox("🛠️ Developer Mode", value=False)
    show_raw_json = False
    if show_dev_tools:
        show_raw_json = st.checkbox("Show Raw JSON", value=False)


# ── Main area ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <p class="main-title">Process2Diagram</p>
    <p class="sub-title">Transform meeting transcripts into professional process diagrams with AI agents.</p>
</div>
""", unsafe_allow_html=True)

# Check API key
if not get_session_llm_client(selected_provider):
    st.warning("👈 **Action Required:** Please enter your API key in the sidebar to unlock the agents.")
    st.stop()

# ── Input Section ─────────────────────────────────────────────────────────────
with st.container():
    st.markdown("### 📥 Input Transcript")
    transcript_text = st.text_area(
        "Paste your meeting transcript here",
        placeholder="Speaker 1: Hello, let's discuss the onboarding process...\nSpeaker 2: Sure, first we need to...",
        height=250,
        label_visibility="collapsed"
    )

    col_btn1, col_btn2, _ = st.columns([1, 1, 2])
    with col_btn1:
        uploaded_file = st.file_uploader("Or upload a file", type=["txt", "docx", "pdf"], label_visibility="collapsed")
    
    if uploaded_file:
        transcript_text = load_transcript(uploaded_file)

    with col_btn2:
        start_process = st.button("🚀 Generate Insights", type="primary", use_container_width=True)


# ── Processing Logic (CORRECTED using original Orchestrator.run) ──────────────
if start_process and transcript_text:
    if not run_quality and not run_bpmn and not run_minutes and not run_requirements and not run_synthesizer:
        st.warning("Please select at least one agent in the sidebar.")
        st.stop()

    client_info = get_session_llm_client(selected_provider)

    # Initialize KnowledgeHub (original pattern)
    hub = KnowledgeHub.new()
    hub.set_transcript(transcript_text)
    hub.meta.llm_provider = selected_provider

    # Progress display (simple, but keeps the original style)
    progress_placeholder = st.empty()
    agent_status: dict[str, str] = {}

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
            provider_cfg=provider_cfg,
            progress_callback=update_progress,
        )

        # ── Multi-run BPMN logic (copied from original) ─────────────────
        if run_bpmn and n_bpmn_runs > 1:
            import copy as _copy
            _validator = AgentValidator()
            _agent_bpmn = AgentBPMN(client_info, provider_cfg)

            # Run orchestrator for quality + NLP only, skip BPMN for now
            hub = orchestrator.run(
                hub,
                output_language=output_language,
                run_quality=run_quality,
                run_bpmn=False,
                run_minutes=False,
                run_requirements=False,
                run_synthesizer=False,
            )

            candidates = []
            for i in range(n_bpmn_runs):
                update_progress("BPMN Agent", f"pass {i+1}/{n_bpmn_runs}…")
                hub_c = _copy.copy(hub)
                hub_c.bpmn = BPMNModel()
                hub_c = _agent_bpmn.run(hub_c, output_language)
                score = _validator.score(hub_c.bpmn, hub_c.transcript_clean, bpmn_weights)
                score.run_index = i + 1
                candidates.append((score, hub_c.bpmn))

            best_score, best_bpmn = max(candidates, key=lambda x: x[0].weighted)
            hub.bpmn = best_bpmn
            hub.validation.bpmn_score = best_score
            hub.validation.bpmn_candidates = [c[0] for c in candidates]
            hub.validation.n_bpmn_runs = n_bpmn_runs
            hub.validation.ready = True
            hub.bump()
            update_progress(
                "BPMN Agent",
                f"done — pass {best_score.run_index}/{n_bpmn_runs} selected "
                f"(score {best_score.weighted:.1f}/10)",
            )

            # Run remaining agents (minutes, requirements, synthesizer)
            hub = orchestrator.run(
                hub,
                output_language=output_language,
                run_quality=False,
                run_bpmn=False,
                run_minutes=run_minutes,
                run_requirements=run_requirements,
                run_synthesizer=run_synthesizer,
            )

        else:
            # Single-run (original flow)
            hub = orchestrator.run(
                hub,
                output_language=output_language,
                run_quality=run_quality,
                run_bpmn=run_bpmn,
                run_minutes=run_minutes,
                run_requirements=run_requirements,
                run_synthesizer=run_synthesizer,
            )

    except Exception as e:
        st.error(f"Pipeline error: {e}")
        st.stop()

    # Summary of completion
    _done = [n for n, s in agent_status.items() if "done" in s]
    _errors = [n for n, s in agent_status.items() if "error" in s]
    _summary_parts = [f"✅ {len(_done)} agent(s) completed"]
    if _errors:
        _summary_parts.append(f"⚠️ {len(_errors)} with errors: {', '.join(_errors)}")
    _summary_parts.append(f"🔢 {hub.meta.total_tokens_used:,} tokens")
    _summary_parts.append(f"⏱️ {hub.meta.processing_time_ms // 1000}s")
    progress_placeholder.success("  ·  ".join(_summary_parts))

    # Store hub in session state for later rendering
    st.session_state["hub"] = hub


# ── Results Display (preserves all UI improvements) ───────────────────────────
if "hub" in st.session_state:
    hub = st.session_state.hub
    # Ensure migration and missing fields (as in original)
    hub = KnowledgeHub.migrate(hub)
    if not hasattr(hub, 'transcript_quality'):
        from core.knowledge_hub import TranscriptQualityModel
        hub.transcript_quality = TranscriptQualityModel()
    if not hasattr(hub, 'synthesizer'):
        try:
            from core.knowledge_hub import SynthesizerModel
            hub.synthesizer = SynthesizerModel()
        except ImportError:
            from dataclasses import dataclass, field as _field
            @dataclass
            class _SM:
                executive_summary: str = ""
                process_narrative: str = ""
                key_insights: list = _field(default_factory=list)
                recommendations: list = _field(default_factory=list)
                html: str = ""
                ready: bool = False
            hub.synthesizer = _SM()

    # Metrics banner (original style)
    col_a, col_b, col_c, col_d = st.columns(4)
    if hub.bpmn.ready:
        col_a.metric("BPMN Steps", len(hub.bpmn.steps))
        col_b.metric("Connections", len(hub.bpmn.edges))
        actors = list(set(s.actor for s in hub.bpmn.steps if s.actor))
        col_c.metric("Actors", len(actors))
    if hub.minutes.ready:
        col_d.metric("Action Items", len(hub.minutes.action_items))

    # Build tabs list
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
    if show_dev_tools:
        tabs_to_show.append("🔍 Knowledge Hub")

    tabs = st.tabs(tabs_to_show)
    tab_idx = 0

    # ── Tab: Quality ──────────────────────────────────────────────────────────
    if hub.transcript_quality.ready:
        with tabs[tab_idx]:
            tq = hub.transcript_quality
            pp = getattr(hub, 'preprocessing', None)
            
            grade_colors = {"A": "#16a34a", "B": "#65a30d", "C": "#ca8a04", "D": "#ea580c", "E": "#dc2626"}
            grade_color = grade_colors.get(tq.grade, "#64748b")

            col_q1, col_q2 = st.columns([1, 3])
            with col_q1:
                st.markdown(f"""
                <div style='text-align:center; padding:2rem; background:{grade_color}10; border-radius:16px; border:2px solid {grade_color}'>
                    <div style='font-size:4rem; font-weight:800; color:{grade_color}; line-height:1;'>{tq.grade}</div>
                    <div style='font-size:1.2rem; font-weight:600; color:{grade_color}; margin-top:0.5rem;'>{tq.overall_score:.1f}/100</div>
                    <div style='color:var(--text-muted); font-size:0.8rem; margin-top:0.5rem;'>Weighted Score</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col_q2:
                st.markdown("### Evaluation Criteria")
                for c in tq.criteria:
                    with st.expander(f"**{c.criterion}** — {c.score}/100"):
                        st.progress(c.score / 100)
                        st.markdown(c.justification)

            st.markdown("---")
            
            col_sum, col_rec = st.columns(2)
            with col_sum:
                st.markdown("### 📝 General Analysis")
                st.info(tq.overall_summary)
            with col_rec:
                st.markdown("### 💡 Recommendation")
                if tq.grade in ["A", "B"]:
                    st.success(tq.recommendation)
                elif tq.grade in ["C", "D"]:
                    st.warning(tq.recommendation)
                else:
                    st.error(tq.recommendation)

            if tq.inconsistencies:
                st.markdown(f"### 🔍 AI‑Detected Inconsistencies  `{len(tq.inconsistencies)}`")
                for inc in tq.inconsistencies:
                    label = f"**{inc.speaker}** `{inc.timestamp}` — *{inc.text}*"
                    with st.expander(label, expanded=False):
                        st.markdown(f"**Reason:** {inc.reason}")

            if pp and pp.ready:
                st.markdown("### 🧹 Automated Pre-processing")
                c1, c2, c3 = st.columns(3)
                c1.metric("Fillers Removed", pp.fillers_removed)
                c2.metric("Artifacts Flagged", pp.artifact_turns)
                c3.metric("Repetitions Collapsed", pp.repetitions_collapsed)

                col_raw, col_clean = st.columns(2)
                with col_raw:
                    st.markdown("**Original Transcript**")
                    st.text_area("raw", hub.transcript_raw, height=400, disabled=True, label_visibility="collapsed", key="ta_raw")
                    _copy_button(hub.transcript_raw, key="tab_orig")
                with col_clean:
                    st.markdown("**Cleaned Transcript** (Hover for issues)")
                    _render_highlighted_transcript(hub.transcript_clean, tq.inconsistencies, key="hl_quality")
                    _copy_button(hub.transcript_clean, key="tab_clean")
        tab_idx += 1

    # ── Tab: BPMN 2.0 ─────────────────────────────────────────────────────────
    if hub.bpmn.ready:
        with tabs[tab_idx]:
            st.markdown("""
            <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem;'>
                <h3 style='margin:0;'>📐 BPMN Process Model</h3>
                <span class='badge badge-blue'>Interactive Viewer</span>
            </div>
            """, unsafe_allow_html=True)
            
            if hub.bpmn.bpmn_xml:
                bpmn_html = preview_from_xml(hub.bpmn.bpmn_xml)
                components.html(bpmn_html, height=800, scrolling=False)
                
                if hub.bpmn.lanes:
                    st.markdown("**Identified Roles:** " + " ".join([f"<span class='badge badge-green'>{l}</span>" for l in hub.bpmn.lanes]), unsafe_allow_html=True)
            else:
                st.warning("BPMN XML not available. Showing Mermaid fallback.")
                render_mermaid_block(hub.bpmn.mermaid, show_code=False, key_suffix="bpmn_fallback")
        tab_idx += 1

        # ── Tab: Mermaid ──────────────────────────────────────────────────────
        with tabs[tab_idx]:
            st.markdown("### 📊 Mermaid Flowchart")
            render_mermaid_block(hub.bpmn.mermaid, show_code=True, key_suffix="mermaid_tab")
        tab_idx += 1

        # ── Tab: BPMN Validation (multi-run) ───────────────────────────────────
        if hub.validation.ready and hub.validation.n_bpmn_runs > 1:
            with tabs[tab_idx]:
                val = hub.validation
                st.markdown(f"### Selection among {val.n_bpmn_runs} passes")
                best = val.bpmn_score
                rows = []
                for c in sorted(val.bpmn_candidates, key=lambda x: x.weighted, reverse=True):
                    rows.append({
                        "Pass":        f"{'⭐ ' if c.run_index == best.run_index else ''}{c.run_index}",
                        "Granularity": f"{c.granularity:.1f}",
                        "Task Type":   f"{c.task_type:.1f}",
                        "Gateways":    f"{c.gateways:.1f}",
                        "Final Score": f"{c.weighted:.2f}",
                        "Activities":  c.n_tasks,
                        "Gateways #":  c.n_gateways,
                    })
                st.dataframe(rows, use_container_width=True)
                st.caption(f"Pass **{best.run_index}** selected · Score {best.weighted:.2f}/10")
            tab_idx += 1

    # ── Tab: Minutes ──────────────────────────────────────────────────────────
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
                with st.container():
                    st.markdown(f"**{block.get('topic', '')}**")
                    st.markdown(block.get("content", ""))

            if m.decisions:
                st.markdown("### ✅ Key Decisions")
                for d in m.decisions:
                    st.markdown(f"- {d}")

            if m.action_items:
                st.markdown("### 🎯 Action Items")
                prio_map = {"high": "🔴 High", "normal": "🟡 Normal", "low": "🟢 Low"}
                rows = []
                for ai in m.action_items:
                    rows.append({
                        "Priority": prio_map.get(ai.priority, "⚪"),
                        "Task": ai.task,
                        "Owner": ai.responsible,
                        "Deadline": ai.deadline or "—"
                    })
                st.dataframe(rows, use_container_width=True)
        tab_idx += 1

    # ── Tab: Requirements ─────────────────────────────────────────────────────
    if hub.requirements.ready:
        with tabs[tab_idx]:
            req = hub.requirements
            type_labels = {
                "ui_field":       "🖥️ UI Field",
                "validation":     "✅ Validation",
                "business_rule":  "📋 Business Rule",
                "functional":     "⚙️ Functional",
                "non_functional": "📊 Non-functional",
            }
            priority_colors = {"high": "🔴", "medium": "🟡", "low": "🟢", "unspecified": "⚪"}
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Requirements", len(req.requirements))
            c2.metric("High Priority", sum(1 for r in req.requirements if r.priority == "high"))
            c3.metric("Distinct Types", len(set(r.type for r in req.requirements)))

            # Filter by type
            selected_type = st.selectbox(
                "Filter by type",
                ["All"] + list(type_labels.values()),
                key="req_type_filter",
            )
            type_reverse = {v: k for k, v in type_labels.items()}
            
            rows = []
            for r in req.requirements:
                if selected_type != "All" and r.type != type_reverse.get(selected_type):
                    continue
                rows.append({
                    "ID": r.id,
                    "Type": type_labels.get(r.type, r.type),
                    "Priority": priority_colors.get(r.priority, "⚪"),
                    "Title": r.title,
                    "Process Step": r.process_step or "—",
                    "Actor": r.actor or "—",
                })
            if rows:
                st.dataframe(rows, use_container_width=True)

            st.markdown("---")
            st.markdown("### Detailed View")
            for r in req.requirements:
                if selected_type != "All" and r.type != type_reverse.get(selected_type):
                    continue
                with st.expander(f"{r.id} — {r.title}  {priority_colors.get(r.priority, '')}"):
                    st.markdown(f"**Type:** {type_labels.get(r.type, r.type)}")
                    st.markdown(f"**Priority:** {priority_colors.get(r.priority, '⚪')} {r.priority}")
                    if r.actor:
                        st.markdown(f"**Actor:** {r.actor}")
                    if r.process_step:
                        st.markdown(f"**Process step:** {r.process_step}")
                    st.markdown(f"**Description:** {r.description}")
                    if r.source_quote:
                        speaker_tag = f"**[{r.speaker}]** " if r.speaker else ""
                        st.markdown(f"> {speaker_tag}*\"{r.source_quote}\"*")
        tab_idx += 1

    # ── Tab: Executive Report ─────────────────────────────────────────────────
    if hub.synthesizer.ready:
        with tabs[tab_idx]:
            syn = hub.synthesizer
            st.markdown("### 📄 Executive Report")
            st.caption("AI-generated executive summary of all artifacts.")
            st.download_button(
                "⬇️ Download Executive Report (.html)",
                data=syn.html,
                file_name="executive_report.html",
                mime="text/html",
                use_container_width=True,
            )
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
                    st.download_button("⬇️ Download .bpmn", hub.bpmn.bpmn_xml, file_name="process.bpmn", use_container_width=True, key="dl_bpmn")
            with col2:
                mermaid_content = generate_mermaid(hub.bpmn)
                st.download_button("⬇️ Download .mermaid", mermaid_content, file_name="process.mmd", use_container_width=True, key="dl_mermaid")
            st.markdown("---")
        
        if hub.minutes.ready:
            st.markdown("**Meeting Minutes**")
            md_content = AgentMinutes.to_markdown(hub.minutes)
            st.download_button("⬇️ Download Minutes (.md)", md_content, file_name="minutes.md", use_container_width=True, key="dl_minutes")
            st.markdown("---")
        
        if hub.requirements.ready:
            st.markdown("**Requirements**")
            st.download_button("⬇️ Download Requirements (.md)", hub.requirements.markdown, file_name="requirements.md", use_container_width=True, key="dl_req_md")
            req_json = json.dumps(
                {"name": hub.requirements.name,
                 "requirements": [r.__dict__ for r in hub.requirements.requirements]},
                ensure_ascii=False, indent=2
            )
            st.download_button("⬇️ Download Requirements (.json)", req_json, file_name="requirements.json", use_container_width=True, key="dl_req_json")
            st.markdown("---")
        
        if hub.synthesizer.ready:
            st.markdown("**Executive Report**")
            st.download_button("⬇️ Download Report (.html)", hub.synthesizer.html, file_name="executive_report.html", use_container_width=True, key="dl_report")
    
    tab_idx += 1

    # ── Tab: Knowledge Hub (developer mode) ───────────────────────────────────
    if show_dev_tools:
        with tabs[tab_idx]:
            st.markdown("### 🔍 Knowledge Hub — Session State")
            col_meta1, col_meta2, col_meta3 = st.columns(3)
            col_meta1.metric("Hub Version", hub.version)
            col_meta2.metric("Tokens Used", hub.meta.total_tokens_used)
            col_meta3.metric("Agents Executed", len(hub.meta.agents_run))
            st.markdown(f"**Provider:** `{hub.meta.llm_provider}` — **Model:** `{hub.meta.llm_model}`")
            st.markdown(f"**NLP Segments:** {len(hub.nlp.segments)} — **Actors:** {', '.join(hub.nlp.actors) or '—'} — **Language:** `{hub.nlp.language_detected}`")
            if show_raw_json:
                st.json(hub.to_dict())
            st.download_button("⬇️ Download Knowledge Hub (.json)", hub.to_json(), file_name="knowledge_hub.json", mime="application/json")
        tab_idx += 1


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style='text-align:center; color:var(--text-muted); font-size:0.8rem; padding:1rem;'>
    Process2Diagram v4.4 • Powered by Multi-Agent AI Architecture • 2024
</div>
""", unsafe_allow_html=True)
