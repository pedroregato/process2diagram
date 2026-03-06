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
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ background: #f8fafc; font-family: 'IBM Plex Sans', sans-serif; overflow: hidden; }}
    #toolbar {{
      position: fixed; bottom: 16px; left: 50%; transform: translateX(-50%);
      display: flex; align-items: center; gap: 4px;
      background: rgba(15,23,42,0.92); backdrop-filter: blur(12px);
      border-radius: 12px; padding: 6px 10px;
      box-shadow: 0 4px 24px rgba(0,0,0,0.3); z-index: 100; user-select: none;
    }}
    .tb-btn {{
      width: 32px; height: 32px; border: none; background: transparent;
      color: #94a3b8; border-radius: 6px; cursor: pointer; font-size: 15px;
      display: flex; align-items: center; justify-content: center;
      transition: background 0.15s, color 0.15s;
    }}
    .tb-btn:hover {{ background: rgba(255,255,255,0.1); color: #e2e8f0; }}
    .tb-divider {{ width: 1px; height: 20px; background: rgba(255,255,255,0.12); margin: 0 2px; }}
    #zoom-label {{ color: #64748b; font-size: 11px; font-family: monospace; min-width: 38px; text-align: center; }}
    #canvas {{ width: 100vw; height: 100vh; overflow: hidden; cursor: grab; position: relative; }}
    #canvas.grabbing {{ cursor: grabbing; }}
    #diagram-wrap {{ position: absolute; top: 0; left: 0; transform-origin: 0 0; padding: 40px; }}
    .mermaid {{ background: white; border-radius: 10px; padding: 32px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08); display: inline-block; }}
    #minimap {{
      position: fixed; bottom: 72px; right: 16px; width: 160px; height: 100px;
      background: rgba(15,23,42,0.85); backdrop-filter: blur(8px);
      border-radius: 8px; border: 1px solid rgba(255,255,255,0.08);
      overflow: hidden; opacity: 0; transition: opacity 0.2s;
    }}
    #minimap.visible {{ opacity: 1; }}
    #minimap-viewport {{
      position: absolute; border: 1.5px solid #38bdf8;
      background: rgba(56,189,248,0.12); border-radius: 2px; pointer-events: none;
    }}
    #toast {{
      position: fixed; top: 16px; left: 50%;
      transform: translateX(-50%) translateY(-60px);
      background: rgba(15,23,42,0.92); color: #e2e8f0; font-size: 12px;
      padding: 6px 14px; border-radius: 20px;
      transition: transform 0.25s cubic-bezier(.34,1.56,.64,1);
      pointer-events: none; font-family: monospace;
    }}
    #toast.show {{ transform: translateX(-50%) translateY(0); }}
  </style>
</head>
<body>
<div id="canvas">
  <div id="diagram-wrap">
    <div class="mermaid">{mermaid_code}</div>
  </div>
</div>
<div id="toolbar">
  <button class="tb-btn" id="btn-zoom-out" title="Zoom out">&#8722;</button>
  <span id="zoom-label">100%</span>
  <button class="tb-btn" id="btn-zoom-in" title="Zoom in">&#43;</button>
  <div class="tb-divider"></div>
  <button class="tb-btn" id="btn-fit" title="Fit to screen">&#8862;</button>
  <button class="tb-btn" id="btn-reset" title="Reset view">&#8634;</button>
  <div class="tb-divider"></div>
  <button class="tb-btn" id="btn-minimap" title="Toggle minimap">&#8862;</button>
</div>
<div id="minimap"><div id="minimap-viewport"></div></div>
<div id="toast"></div>
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
  mermaid.initialize({{ startOnLoad: true, theme: 'neutral', securityLevel: 'loose' }});
  await new Promise(r => setTimeout(r, 700));
  const canvas = document.getElementById('canvas');
  const wrap = document.getElementById('diagram-wrap');
  const zoomLbl = document.getElementById('zoom-label');
  const minimap = document.getElementById('minimap');
  const mmvp = document.getElementById('minimap-viewport');
  const toast = document.getElementById('toast');
  let scale = 1, tx = 40, ty = 40, dragging = false;
  let startX, startY, startTx, startTy, minimapOn = false, lastDist = null;
  let touchTx, touchTy;
  function apply() {{
    wrap.style.transform = `translate(${{tx}}px, ${{ty}}px) scale(${{scale}})`;
    zoomLbl.textContent = Math.round(scale * 100) + '%';
    updateMinimap();
  }}
  function clamp(s) {{ return Math.min(Math.max(s, 0.1), 5); }}
  function zoomTo(ns, cx, cy) {{
    const r = ns / scale; tx = cx - r*(cx-tx); ty = cy - r*(cy-ty);
    scale = ns; apply();
  }}
  function fitToScreen() {{
    const svg = wrap.querySelector('svg');
    if (!svg) return;
    const sw = svg.getBoundingClientRect().width / scale;
    const sh = svg.getBoundingClientRect().height / scale;
    const ns = clamp(Math.min((canvas.clientWidth-80)/sw, (canvas.clientHeight-80)/sh));
    scale = ns;
    tx = (canvas.clientWidth - sw*scale) / 2;
    ty = (canvas.clientHeight - sh*scale) / 2;
    apply();
  }}
  function updateMinimap() {{
    if (!minimapOn) return;
    const svg = wrap.querySelector('svg');
    if (!svg) return;
    const sw = svg.getBoundingClientRect().width / scale;
    const sh = svg.getBoundingClientRect().height / scale;
    const mw = minimap.clientWidth, mh = minimap.clientHeight;
    const r = Math.min(mw/sw, mh/sh) * 0.9;
    mmvp.style.width  = (canvas.clientWidth/scale*r) + 'px';
    mmvp.style.height = (canvas.clientHeight/scale*r) + 'px';
    mmvp.style.left   = (-tx/scale*r + (mw-sw*r)/2) + 'px';
    mmvp.style.top    = (-ty/scale*r + (mh-sh*r)/2) + 'px';
  }}
  function showToast(msg) {{
    toast.textContent = msg; toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 1800);
  }}
  canvas.addEventListener('wheel', e => {{
    e.preventDefault();
    const r = canvas.getBoundingClientRect();
    zoomTo(clamp(scale * (e.deltaY > 0 ? 0.9 : 1.1)), e.clientX-r.left, e.clientY-r.top);
  }}, {{passive: false}});
  canvas.addEventListener('mousedown', e => {{
    if (e.button !== 0) return;
    dragging = true; startX = e.clientX; startY = e.clientY;
    startTx = tx; startTy = ty; canvas.classList.add('grabbing');
  }});
  window.addEventListener('mousemove', e => {{
    if (!dragging) return;
    tx = startTx + e.clientX - startX; ty = startTy + e.clientY - startY; apply();
  }});
  window.addEventListener('mouseup', () => {{ dragging = false; canvas.classList.remove('grabbing'); }});
  canvas.addEventListener('touchstart', e => {{
    if (e.touches.length === 1) {{
      startX = e.touches[0].clientX; startY = e.touches[0].clientY;
      touchTx = tx; touchTy = ty;
    }}
    if (e.touches.length === 2) {{
      lastDist = Math.hypot(e.touches[0].clientX-e.touches[1].clientX, e.touches[0].clientY-e.touches[1].clientY);
    }}
  }}, {{passive: true}});
  canvas.addEventListener('touchmove', e => {{
    if (e.touches.length === 1) {{
      tx = touchTx + e.touches[0].clientX - startX;
      ty = touchTy + e.touches[0].clientY - startY; apply();
    }}
    if (e.touches.length === 2) {{
      const d = Math.hypot(e.touches[0].clientX-e.touches[1].clientX, e.touches[0].clientY-e.touches[1].clientY);
      const mx = (e.touches[0].clientX+e.touches[1].clientX)/2;
      const my = (e.touches[0].clientY+e.touches[1].clientY)/2;
      if (lastDist) zoomTo(clamp(scale*d/lastDist), mx, my);
      lastDist = d;
    }}
    e.preventDefault();
  }}, {{passive: false}});
  canvas.addEventListener('touchend', () => {{ lastDist = null; }});
  window.addEventListener('keydown', e => {{
    const cx = canvas.clientWidth/2, cy = canvas.clientHeight/2;
    if (e.key==='+' || e.key==='=') zoomTo(clamp(scale*1.15), cx, cy);
    if (e.key==='-') zoomTo(clamp(scale*0.87), cx, cy);
    if (e.key==='0') fitToScreen();
    if (e.key==='r' || e.key==='R') {{ scale=1; tx=40; ty=40; apply(); }}
  }});
  document.getElementById('btn-zoom-in').onclick  = () => zoomTo(clamp(scale*1.2), canvas.clientWidth/2, canvas.clientHeight/2);
  document.getElementById('btn-zoom-out').onclick = () => zoomTo(clamp(scale*0.8), canvas.clientWidth/2, canvas.clientHeight/2);
  document.getElementById('btn-fit').onclick = fitToScreen;
  document.getElementById('btn-reset').onclick = () => {{ scale=1; tx=40; ty=40; apply(); }};
  document.getElementById('btn-minimap').onclick = () => {{
    minimapOn = !minimapOn;
    minimap.classList.toggle('visible', minimapOn);
    updateMinimap();
    showToast(minimapOn ? 'Minimap on' : 'Minimap off');
  }};
  setTimeout(fitToScreen, 400);
</script>
</body>
</html>
"""
        components.html(mermaid_html, height=1000, scrolling=False)

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
