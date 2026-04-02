## --- Process2Diagram v4.2 — High Contrast Multi-Agent UI
## --- Improved by Manus

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

# ── BPMN viewer (presentation layer — separated from generator) ──────────────
from modules.bpmn_viewer import preview_from_xml
from modules.mermaid_renderer import render_mermaid_block

#  ── Outras funcionalidades ──────────────
from modules.bpmn_diagnostics import render_bpmn_diagnostics


# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Process2Diagram | AI-Powered Process Mining",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Enhanced CSS (Modern SaaS Look with High Contrast) ────────────────────────
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

    /* Sidebar Styling - High Contrast Refinement */
    section[data-testid="stSidebar"] {
        background-color: var(--sidebar-bg);
        border-right: 1px solid #1e293b;
    }
    
    /* Sidebar Headings & Labels */
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3 {
        color: var(--sidebar-text) !important;
    }
    
    section[data-testid="stSidebar"] label p {
        color: var(--sidebar-label) !important;
        font-weight: 500 !important;
    }

    /* Sidebar Selectbox Contrast Fix */
    section[data-testid="stSidebar"] div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        color: #1e293b !important; /* Dark text on white background */
        border-radius: 8px;
    }
    
    /* Ensure selected value is dark */
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] div[role="button"] {
        color: #1e293b !important;
    }

    /* Sidebar Checkbox Label Contrast Fix */
    section[data-testid="stSidebar"] .stCheckbox label span {
        color: var(--sidebar-text) !important;
        font-weight: 400 !important;
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


# ── Helpers ───────────────────────────────────────────────────────────────────

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
                      capture_output=True, text=True).stdout.strip() or "v4.2"
    
    st.markdown(f"""
    <div style='padding: 1rem 0;'>
        <h2 style='margin:0; font-size:1.5rem; color: #f8fafc;'>⚡ Process2Diagram</h2>
        <p style='color:#94a3b8; font-size:0.8rem; margin-top:0.2rem;'>Build {_commit} — Multi-Agent</p>
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

    st.markdown("### 🤖 Active Agents")
    run_quality = st.checkbox("Quality Inspector", value=True)
    run_bpmn = st.checkbox("BPMN Architect", value=True)

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
        else:
            bpmn_weights = {"granularity": 5, "task_type": 5, "gateways": 5}

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

# ── Processing Logic ──────────────────────────────────────────────────────────
if start_process and transcript_text:
    hub = KnowledgeHub(transcript_text)
    orchestrator = Orchestrator(hub, selected_provider)
    
    with st.status("🤖 Agents are working...", expanded=True) as status:
        if run_quality:
            status.write("🔍 Quality Inspector: Analyzing transcript...")
            orchestrator.run_quality_inspector()
        
        if run_bpmn:
            status.write(f"📐 BPMN Architect: Generating process model ({n_bpmn_runs} passes)...")
            orchestrator.run_bpmn_architect(n_runs=n_bpmn_runs, weights=bpmn_weights)
            
        if run_minutes:
            status.write("📋 Minutes Agent: Drafting meeting summary...")
            orchestrator.run_minutes_agent()
            
        if run_requirements:
            status.write("📝 Requirements Agent: Extracting specifications...")
            orchestrator.run_requirements_agent()
            
        if run_synthesizer:
            status.write("📄 Synthesizer: Creating executive report...")
            orchestrator.run_synthesizer()
            
        status.update(label="✅ Analysis Complete!", state="complete", expanded=False)
    
    st.session_state.hub = hub

# ── Results Display ───────────────────────────────────────────────────────────
if "hub" in st.session_state:
    hub = st.session_state.hub
    
    tabs_to_show = []
    if hub.transcript_quality.ready: tabs_to_show.append("🔬 Quality")
    if hub.bpmn.ready: 
        tabs_to_show.append("📐 BPMN 2.0")
        tabs_to_show.append("📊 Mermaid")
    if hub.minutes.ready: tabs_to_show.append("📋 Minutes")
    if hub.requirements.ready: tabs_to_show.append("📝 Requirements")
    if hub.synthesizer.ready: tabs_to_show.append("📄 Executive Report")
    tabs_to_show.append("📦 Export")
    
    tabs = st.tabs(tabs_to_show)
    tab_map = {name: i for i, name in enumerate(tabs_to_show)}

    # ── Tab: Quality ──────────────────────────────────────────────────────────
    if "🔬 Quality" in tab_map:
        with tabs[tab_map["🔬 Quality"]]:
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
                if tq.grade in ["A", "B"]: st.success(tq.recommendation)
                elif tq.grade in ["C", "D"]: st.warning(tq.recommendation)
                else: st.error(tq.recommendation)

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

    # ── Tab: BPMN 2.0 ─────────────────────────────────────────────────────────
    if "📐 BPMN 2.0" in tab_map:
        with tabs[tab_map["📐 BPMN 2.0"]]:
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

    # ── Tab: Mermaid ──────────────────────────────────────────────────────
    if "📊 Mermaid" in tab_map:
        with tabs[tab_map["📊 Mermaid"]]:
            st.markdown("### 📊 Mermaid Flowchart")
            render_mermaid_block(hub.bpmn.mermaid, show_code=True, key_suffix="mermaid_tab")

    # ── Tab: Minutes ──────────────────────────────────────────────────────────
    if "📋 Minutes" in tab_map:
        with tabs[tab_map["📋 Minutes"]]:
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
                st.table(rows)

    # ── Tab: Requirements ─────────────────────────────────────────────────────
    if "📝 Requirements" in tab_map:
        with tabs[tab_map["📝 Requirements"]]:
            req = hub.requirements
            st.markdown("### 📝 System Requirements")
            
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Requirements", len(req.requirements))
            c2.metric("High Priority", sum(1 for r in req.requirements if r.priority == "high"))
            c3.metric("Distinct Types", len(set(r.type for r in req.requirements)))

            for r in req.requirements:
                with st.expander(f"**{r.id}** — {r.title}"):
                    st.markdown(f"**Type:** `{r.type}` | **Priority:** `{r.priority}`")
                    st.markdown(f"**Description:** {r.description}")
                    if r.source_quote:
                        st.markdown(f"> *\"{r.source_quote}\"* — **{r.speaker or 'Unknown'}**")

    # ── Tab: Executive Report ─────────────────────────────────────────────────
    if "📄 Executive Report" in tab_map:
        with tabs[tab_map["📄 Executive Report"]]:
            syn = hub.synthesizer
            st.markdown("### 📄 Executive Report")
            st.caption("AI-generated executive summary of all artifacts.")
            st.divider()
            components.html(syn.html, height=800, scrolling=True)

    # ── Tab: Export ───────────────────────────────────────────────────────────
    if "📦 Export" in tab_map:
        with tabs[tab_map["📦 Export"]]:
            st.markdown("### 📦 Export Assets")
            
            col_ex1, col_ex2 = st.columns(2)
            
            with col_ex1:
                st.markdown("#### 📐 Process Models")
                if hub.bpmn.ready:
                    st.download_button("⬇️ Download .bpmn", hub.bpmn.bpmn_xml, file_name="process.bpmn", use_container_width=True, key="dl_bpmn")
                    st.download_button("⬇️ Download .mermaid", hub.bpmn.mermaid, file_name="process.mmd", use_container_width=True, key="dl_mermaid")
            
            with col_ex2:
                st.markdown("#### 📋 Documentation")
                if hub.minutes.ready:
                    from agents.agent_minutes import AgentMinutes
                    md_minutes = AgentMinutes.to_markdown(hub.minutes)
                    st.download_button("⬇️ Download Minutes (.md)", md_minutes, file_name="minutes.md", use_container_width=True, key="dl_minutes")
                
                if hub.synthesizer.ready:
                    st.download_button("⬇️ Download Executive Report (.html)", hub.synthesizer.html, file_name="report.html", use_container_width=True, key="dl_report")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown("""
<div style='text-align:center; color:var(--text-muted); font-size:0.8rem; padding:1rem;'>
    Process2Diagram v4.2 • Powered by Multi-Agent AI Architecture • 2024
</div>
""", unsafe_allow_html=True)
