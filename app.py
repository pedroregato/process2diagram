## --- Pedro Gentil

import streamlit as st
import streamlit.components.v1 as components
from modules.session_security import render_api_key_gate, get_session_llm_client
from modules.config import AVAILABLE_PROVIDERS
from modules.ingest import load_transcript
from modules.preprocess import preprocess_text
from modules.extract_llm import extract_process_llm
from modules.schema import Process
from modules.diagram_mermaid import generate_mermaid
from modules.diagram_drawio import generate_drawio
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

    # -- Outputs ---------------------------------------------------------------
    tab1, tab2, tab3 = st.tabs(["📊 Diagram", "📄 Mermaid Code", "🔧 Export"])

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
        components.html(mermaid_html, height=700, scrolling=True)

        # Metrics row
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Steps", len(process.steps))
        m2.metric("Connections", len(process.edges))
        actors = list(set(s.actor for s in process.steps if s.actor))
        m3.metric("Actors", len(actors))
        decisions = [s for s in process.steps if s.is_decision]
        m4.metric("Decisions", len(decisions))

        if actors:
            st.markdown(f"**Actors detected:** {', '.join(f'`{a}`' for a in actors)}")

    with tab2:
        mermaid_code = generate_mermaid(process)
        st.code(mermaid_code, language="text")
        st.caption("Paste this into [mermaid.live](https://mermaid.live) to preview and edit.")

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

    # Store last result in session for reference
    st.session_state["last_process"] = process
