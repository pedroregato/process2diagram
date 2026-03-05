## --- Pedro Gentil

import streamlit as st
import streamlit.components.v1 as components
from modules.session_security import render_api_key_gate, get_session_llm_client
from modules.config import AVAILABLE_PROVIDERS
from modules.ingest import load_transcript
from modules.preprocess import preprocess_text
from modules.extract_llm import extract_process_llm
try:
    from modules.extract_llm import extract_process_bpmn
    _BPMN_AVAILABLE = True
except ImportError:
    _BPMN_AVAILABLE = False
from modules.schema import Process
from modules.diagram_mermaid import generate_mermaid
from modules.diagram_drawio import generate_drawio
try:
    from modules.diagram_bpmn import generate_bpmn_xml, generate_bpmn_preview
except ImportError:
    generate_bpmn_xml = generate_bpmn_preview = None
from modules.utils import process_to_json

# -- Page config ----------------------------------------------------------------
st.set_page_config(
    page_title="Process2Diagram",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -- Custom CSS -----------------------------------------------------------------
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');

  html, body, [class*="css"] {
    font-family: 'IBM Plex Sans', sans-serif;
  }
  h1, h2, h3 {
    font-family: 'IBM Plex Mono', monospace !important;
    letter-spacing: -0.03em;
  }
  .main-title {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 2.4rem;
    font-weight: 600;
    letter-spacing: -0.04em;
    color: #0f172a;
    margin-bottom: 0;
  }
  .sub-title {
    font-family: 'IBM Plex Sans', sans-serif;
    font-weight: 300;
    color: #64748b;
    margin-top: 0.2rem;
    font-size: 1rem;
  }
  .provider-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 4px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.75rem;
    font-weight: 600;
    background: #0f172a;
    color: #38bdf8;
    margin-left: 8px;
    vertical-align: middle;
  }
  .stTextArea textarea {
    font-family: 'IBM Plex Mono', monospace !important;
    font-size: 0.85rem;
  }
  .block-container { padding-top: 2rem; }
  div[data-testid="stSidebar"] {
    background: #0f172a;
    color: #e2e8f0;
  }
  div[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
  div[data-testid="stSidebar"] .stSelectbox label,
  div[data-testid="stSidebar"] .stTextInput label { color: #94a3b8 !important; }
</style>
""", unsafe_allow_html=True)

# -- Sidebar: LLM Provider + API Key gate --------------------------------------
with st.sidebar:
    st.markdown("## ⚙️ Process2Diagram")
    st.markdown("---")

    st.markdown("### 🤖 LLM Provider")
    provider_names = list(AVAILABLE_PROVIDERS.keys())
    selected_provider = st.selectbox(
        "Choose provider",
        provider_names,
        index=provider_names.index("DeepSeek") if "DeepSeek" in provider_names else 0,
        key="selected_provider",
    )

    provider_cfg = AVAILABLE_PROVIDERS[selected_provider]

    st.markdown(f"**Model:** `{provider_cfg['default_model']}`")
    st.markdown(f"**Cost:** {provider_cfg['cost_hint']}")
    st.markdown("---")

    render_api_key_gate(selected_provider, provider_cfg)

    st.markdown("---")
    st.markdown("### ⚙️ Options")
    output_language = st.selectbox("Output language", ["Auto-detect", "English", "Portuguese (BR)"])
    show_raw_json = st.checkbox("Show raw JSON", value=False)
    if _BPMN_AVAILABLE:
        generate_bpmn = st.checkbox("Also generate BPMN diagram", value=False,
                                    help="Runs a second LLM call with the BPMN 2.0 extraction prompt.")
    else:
        generate_bpmn = False
        st.caption("⚠️ BPMN module not available — update extract_llm.py")
    st.markdown("---")
    st.caption("Keys live **only in your session**.\nNever stored or logged.")

# -- Main area -----------------------------------------------------------------
st.markdown('<p class="main-title">Process2Diagram</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">Turn meeting transcripts into process diagrams — automatically.</p>', unsafe_allow_html=True)

if not get_session_llm_client(selected_provider):
    st.info(f"👈 Enter your **{selected_provider}** API key in the sidebar to start.")
    st.stop()

# -- Input ---------------------------------------------------------------------
st.markdown("### 📋 Transcript")
col_input, col_help = st.columns([3, 1])

with col_input:
    transcript_text = st.text_area(
        "Paste your meeting transcript here",
        height=220,
        placeholder="Example:\n1) The team uploads the photo.\n2) The system detects faces.\n3) The specialist identifies people.\n4) The system generates the SVG.\n5) Files are uploaded to ECM.",
        key="transcript_input",
    )

with col_help:
    st.markdown("**Tips for best results:**")
    st.markdown("""
- Numbered steps work best
- Bullet points also supported
- Mention actors: *"the team"*, *"the system"*
- Decision words: *"if"*, *"when"*, *"otherwise"*
- Multiple actors → swimlanes auto-generated
- Enable **BPMN** in sidebar for full BPMN 2.0
    """)

uploaded_file = st.file_uploader("Or upload a .txt file", type=["txt"])
if uploaded_file:
    transcript_text = load_transcript(uploaded_file)
    st.success(f"Loaded: {uploaded_file.name}")

# -- Generate ------------------------------------------------------------------
generate_btn = st.button("⚡ Generate Diagram", type="primary", use_container_width=True)

if generate_btn:
    if not transcript_text or len(transcript_text.strip()) < 20:
        st.warning("Please provide a transcript with at least a few lines.")
        st.stop()

    client_info = get_session_llm_client(selected_provider)

    # ── Mermaid / Draw.io extraction (original) ───────────────────────────────
    with st.spinner(f"Extracting process with {selected_provider}..."):
        clean_text = preprocess_text(transcript_text)
        try:
            process: Process = extract_process_llm(
                text=clean_text,
                client_info=client_info,
                provider=selected_provider,
                provider_cfg=provider_cfg,
                output_language=output_language,
            )
        except Exception as e:
            st.error(f"Extraction failed: {e}")
            st.stop()

    st.success(f"✅ Extracted **{len(process.steps)} steps** and **{len(process.edges)} connections**")

    # ── BPMN extraction (optional second call) ────────────────────────────────
    bpmn_process = None
    if generate_bpmn:
        with st.spinner(f"Extracting BPMN model with {selected_provider}..."):
            try:
                bpmn_process = extract_process_bpmn(
                    text=clean_text,
                    client_info=client_info,
                    provider=selected_provider,
                    provider_cfg=provider_cfg,
                    output_language=output_language,
                )
                n_elements = len(bpmn_process.elements)
                n_flows    = len(bpmn_process.flows)
                n_lanes    = len(bpmn_process.lanes_flat())
                st.success(
                    f"✅ BPMN extracted — **{n_elements} elements**, "
                    f"**{n_flows} flows**, **{n_lanes} lanes**"
                )
            except Exception as e:
                st.warning(f"BPMN extraction failed: {e}")

    # -- Outputs ---------------------------------------------------------------
    tab_labels = ["📊 Diagram", "📄 Mermaid Code", "🔧 Export"]
    if bpmn_process:
        tab_labels.append("📐 BPMN")

    tabs = st.tabs(tab_labels)
    tab1, tab2, tab3 = tabs[0], tabs[1], tabs[2]
    tab_bpmn = tabs[3] if bpmn_process else None

    # ── Tab 1: Mermaid diagram ────────────────────────────────────────────────
    with tab1:
        mermaid_code = generate_mermaid(process)
        st.markdown("#### Process Flow")

        mermaid_html = f"""
<!DOCTYPE html>
<html>
<head>
  <style>
    body {{ margin: 0; padding: 16px; background: #f8fafc; font-family: sans-serif; }}
    .mermaid {{ background: white; padding: 24px; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
  </style>
</head>
<body>
  <div class="mermaid">
{mermaid_code}
  </div>
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
    mermaid.initialize({{ startOnLoad: true, theme: 'neutral', securityLevel: 'loose' }});
  </script>
</body>
</html>
"""
        components.html(mermaid_html, height=1200, scrolling=True)

        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Steps", len(process.steps))
        m2.metric("Connections", len(process.edges))
        actors = list(dict.fromkeys(s.actor for s in process.steps if s.actor))  # ordered, deduped
        m3.metric("Actors / Lanes", len(actors))
        decisions = [s for s in process.steps if s.is_decision]
        m4.metric("Decisions", len(decisions))
        m5.metric("Swimlanes", "✅" if actors else "—")

        if actors:
            st.markdown(f"**Lanes detected:** {', '.join(f'`{a}`' for a in actors)}")

    # ── Tab 2: Mermaid code ───────────────────────────────────────────────────
    with tab2:
        mermaid_code = generate_mermaid(process)
        st.code(mermaid_code, language="text")
        st.caption("Paste this into [mermaid.live](https://mermaid.live) to preview and edit.")

    # ── Tab 3: Export ─────────────────────────────────────────────────────────
    with tab3:
        col_dl1, col_dl2 = st.columns(2)

        drawio_xml = generate_drawio(process)
        with col_dl1:
            st.download_button(
                label="⬇️ Download .drawio",
                data=drawio_xml,
                file_name=f"{process.name.replace(' ', '_')}.drawio",
                mime="application/xml",
                use_container_width=True,
            )

        json_data = process_to_json(process)
        with col_dl2:
            st.download_button(
                label="⬇️ Download .json",
                data=json_data,
                file_name=f"{process.name.replace(' ', '_')}.json",
                mime="application/json",
                use_container_width=True,
            )

        if show_raw_json:
            st.markdown("#### Structured JSON")
            st.json(json_data)

        st.markdown("#### Open .drawio file")
        st.markdown("1. Go to [diagrams.net](https://app.diagrams.net)\n2. File → Open from → Device\n3. Select the downloaded `.drawio` file")

    # ── Tab 4: BPMN ───────────────────────────────────────────────────────────
    if tab_bpmn and bpmn_process:
        with tab_bpmn:
            st.markdown("#### BPMN 2.0 Process Diagram")

            try:
                bpmn_xml = generate_bpmn_xml(bpmn_process)

                # Interactive preview via bpmn-js
                bpmn_html = generate_bpmn_preview(bpmn_xml)
                components.html(bpmn_html, height=620, scrolling=False)

            except Exception as e:
                st.error(f"BPMN diagram generation failed: {e}")
                bpmn_xml = None

            # Metrics
            st.markdown("---")
            b1, b2, b3, b4, b5 = st.columns(5)
            b1.metric("Elements",  len(bpmn_process.elements))
            b2.metric("Flows",     len(bpmn_process.flows))
            b3.metric("Lanes",     len(bpmn_process.lanes_flat()))
            b4.metric("Gateways",  len(bpmn_process.gateways()))
            b5.metric("Tasks",     len(bpmn_process.tasks()))

            if bpmn_process.lanes_flat():
                lane_names = [l.name for l in bpmn_process.lanes_flat() if l.name]
                st.markdown(f"**Lanes / Actors:** {', '.join(f'`{n}`' for n in lane_names)}")

            # Boundary events summary
            boundaries = bpmn_process.boundary_events()
            if boundaries:
                st.markdown("**Boundary events:**")
                for be in boundaries:
                    host = bpmn_process.get_element(be.attached_to) if be.attached_to else None
                    host_name = host.name if host else be.attached_to
                    interrupt = "interrupting" if be.is_interrupting else "non-interrupting"
                    st.markdown(f"- `{be.name}` ({be.event_type}, {interrupt}) → attached to **{host_name}**")

            # Sub-processes summary
            subprocs = bpmn_process.sub_processes()
            if subprocs:
                st.markdown("**Sub-processes:**")
                for sp in subprocs:
                    st.markdown(f"- `{sp.name}` — {len(sp.children)} inner element(s)")

            # Downloads
            st.markdown("---")
            if bpmn_xml:
                col_b1, col_b2 = st.columns(2)
                with col_b1:
                    st.download_button(
                        label="⬇️ Download .bpmn",
                        data=bpmn_xml,
                        file_name=f"{bpmn_process.name.replace(' ', '_')}.bpmn",
                        mime="application/xml",
                        use_container_width=True,
                    )
                with col_b2:
                    st.download_button(
                        label="⬇️ Download BPMN as .xml",
                        data=bpmn_xml,
                        file_name=f"{bpmn_process.name.replace(' ', '_')}_bpmn.xml",
                        mime="application/xml",
                        use_container_width=True,
                    )

                st.markdown("#### Open in Camunda Modeler or diagrams.net")
                st.markdown(
                    "1. Download the `.bpmn` file above\n"
                    "2. Open [Camunda Modeler](https://camunda.com/download/modeler/) "
                    "or [diagrams.net](https://app.diagrams.net)\n"
                    "3. File → Open → select the `.bpmn` file\n"
                    "4. Edit, annotate and export as needed"
                )

                if show_raw_json:
                    st.markdown("#### Raw BPMN XML")
                    st.code(bpmn_xml, language="xml")

    # Store last results in session
    st.session_state["last_process"]      = process
    st.session_state["last_bpmn_process"] = bpmn_process
