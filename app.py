## --- Process2Diagram v3 — Multi-Agent Architecture
## --- Pedro Gentil

import sys
from pathlib import Path
import json

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
from core.knowledge_hub import KnowledgeHub
from agents.orchestrator import Orchestrator
from agents.agent_minutes import AgentMinutes
from agents.agent_mermaid import generate_mermaid

# ── BPMN viewer (presentation layer — separated from generator) ──────────────
from modules.bpmn_viewer import preview_from_xml

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Process2Diagram",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
  html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
  h1, h2, h3 { font-family: 'IBM Plex Mono', monospace !important; letter-spacing: -0.03em; }
  .main-title { font-family: 'IBM Plex Mono', monospace; font-size: 2.4rem; font-weight: 600;
    letter-spacing: -0.04em; color: #0f172a; margin-bottom: 0; }
  .sub-title { font-family: 'IBM Plex Sans', sans-serif; font-weight: 300; color: #64748b;
    margin-top: 0.2rem; font-size: 1rem; }
  .stTextArea textarea { font-family: 'IBM Plex Mono', monospace !important; font-size: 0.85rem; }
  .block-container { padding-top: 2rem; }
  div[data-testid="stSidebar"] { background: #0f172a; color: #e2e8f0; }
  div[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
  div[data-testid="stSidebar"] .stSelectbox label,
  div[data-testid="stSidebar"] .stTextInput label { color: #94a3b8 !important; }
  .agent-badge { display: inline-block; padding: 2px 8px; border-radius: 12px;
    font-size: 0.75rem; font-weight: 600; margin: 2px; }
</style>
""", unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────
def render_mermaid_block(mermaid_text: str, *, show_code: bool = True, key_suffix: str = "") -> None:
    """
    Renderiza Mermaid interativamente com zoom, pan e fit-to-screen.
    Usa mermaid JS via CDN dentro de um components.html.
    """
    import hashlib

    # Escape the mermaid text for safe embedding in JS template literal
    escaped = (
        mermaid_text
        .replace("\\", "\\\\")
        .replace("`", "\\`")
        .replace("${", "\\${")
    )

    uid = hashlib.md5((mermaid_text + key_suffix).encode()).hexdigest()[:8]

    html_code = f"""
<!DOCTYPE html>
<html>
<head>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ background: #fff; overflow: hidden; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }}

  .toolbar {{
    position: absolute; top: 8px; right: 8px; z-index: 100;
    display: flex; gap: 4px;
  }}
  .toolbar button {{
    width: 32px; height: 32px; border: 1px solid #cbd5e1; border-radius: 6px;
    background: #fff; cursor: pointer; font-size: 16px; display: flex;
    align-items: center; justify-content: center; color: #475569;
    transition: all 0.15s;
  }}
  .toolbar button:hover {{ background: #f1f5f9; border-color: #94a3b8; }}
  .toolbar button:active {{ background: #e2e8f0; }}

  #container {{
    width: 100%; height: 100vh; overflow: hidden;
    cursor: grab; position: relative; background: #fafafa;
    border: 1px solid #e2e8f0; border-radius: 8px;
  }}
  #container:active {{ cursor: grabbing; }}

  #viewport {{
    transform-origin: 0 0;
    position: absolute; top: 0; left: 0;
    will-change: transform;
  }}

  .zoom-hint {{
    position: absolute; bottom: 8px; left: 8px; z-index: 100;
    font-size: 11px; color: #94a3b8;
    pointer-events: none;
  }}

  .loading {{
    display: flex; align-items: center; justify-content: center;
    height: 100vh; color: #64748b; font-size: 14px;
  }}
</style>
</head>
<body>

<div id="loading" class="loading">Renderizando diagrama...</div>

<div id="wrapper" style="display:none; width:100%; height:100vh; position:relative;">
  <div class="toolbar">
    <button onclick="zoomIn()" title="Zoom in">+</button>
    <button onclick="zoomOut()" title="Zoom out">−</button>
    <button onclick="fitToScreen()" title="Fit to screen">⊡</button>
    <button onclick="resetView()" title="Reset">↺</button>
  </div>
  <div class="zoom-hint" id="zoomHint">Scroll: zoom · Drag: mover · ⊡ ajustar</div>
  <div id="container">
    <div id="viewport">
      <div id="diagram_{uid}" class="mermaid">
{escaped}
      </div>
    </div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<script>
(function() {{
  // ── State ──
  let scale = 1, panX = 0, panY = 0;
  let dragging = false, startX = 0, startY = 0;
  const MIN_SCALE = 0.1, MAX_SCALE = 5;

  const container = document.getElementById("container");
  const viewport  = document.getElementById("viewport");

  function applyTransform() {{
    viewport.style.transform =
      "translate(" + panX + "px, " + panY + "px) scale(" + scale + ")";
    document.getElementById("zoomHint").textContent =
      Math.round(scale * 100) + "% · Scroll: zoom · Drag: mover · ⊡ ajustar";
  }}

  // ── Zoom ──
  window.zoomIn  = function() {{ scale = Math.min(scale * 1.25, MAX_SCALE); applyTransform(); }};
  window.zoomOut = function() {{ scale = Math.max(scale / 1.25, MIN_SCALE); applyTransform(); }};

  window.resetView = function() {{
    scale = 1; panX = 0; panY = 0; applyTransform();
  }};

  window.fitToScreen = function() {{
    const svg = viewport.querySelector("svg");
    if (!svg) return;
    const vb = svg.viewBox.baseVal;
    const svgW = vb && vb.width  > 0 ? vb.width  : svg.scrollWidth;
    const svgH = vb && vb.height > 0 ? vb.height : svg.scrollHeight;
    const cW = container.clientWidth;
    const cH = container.clientHeight;
    if (svgW === 0 || svgH === 0) return;
    scale = Math.min(cW / svgW, cH / svgH, 2) * 0.92;
    panX = (cW - svgW * scale) / 2;
    panY = (cH - svgH * scale) / 2;
    applyTransform();
  }};

  // ── Wheel zoom (centered on cursor) ──
  container.addEventListener("wheel", function(e) {{
    e.preventDefault();
    const rect = container.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const oldScale = scale;
    const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
    scale = Math.min(Math.max(scale * factor, MIN_SCALE), MAX_SCALE);
    // Keep point under cursor stable
    panX = mx - (mx - panX) * (scale / oldScale);
    panY = my - (my - panY) * (scale / oldScale);
    applyTransform();
  }}, {{ passive: false }});

  // ── Drag / pan ──
  container.addEventListener("mousedown", function(e) {{
    dragging = true; startX = e.clientX - panX; startY = e.clientY - panY;
  }});
  window.addEventListener("mousemove", function(e) {{
    if (!dragging) return;
    panX = e.clientX - startX; panY = e.clientY - startY;
    applyTransform();
  }});
  window.addEventListener("mouseup", function() {{ dragging = false; }});

  // ── Touch support ──
  let lastTouchDist = 0;
  container.addEventListener("touchstart", function(e) {{
    if (e.touches.length === 1) {{
      dragging = true;
      startX = e.touches[0].clientX - panX;
      startY = e.touches[0].clientY - panY;
    }} else if (e.touches.length === 2) {{
      dragging = false;
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      lastTouchDist = Math.sqrt(dx * dx + dy * dy);
    }}
  }}, {{ passive: true }});
  container.addEventListener("touchmove", function(e) {{
    if (e.touches.length === 1 && dragging) {{
      panX = e.touches[0].clientX - startX;
      panY = e.touches[0].clientY - startY;
      applyTransform();
    }} else if (e.touches.length === 2) {{
      const dx = e.touches[0].clientX - e.touches[1].clientX;
      const dy = e.touches[0].clientY - e.touches[1].clientY;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (lastTouchDist > 0) {{
        const factor = dist / lastTouchDist;
        scale = Math.min(Math.max(scale * factor, MIN_SCALE), MAX_SCALE);
        applyTransform();
      }}
      lastTouchDist = dist;
    }}
  }}, {{ passive: true }});
  container.addEventListener("touchend", function() {{
    dragging = false; lastTouchDist = 0;
  }});

  // ── Mermaid init ──
  mermaid.initialize({{
    startOnLoad: false,
    theme: "default",
    flowchart: {{ curve: "basis", useMaxWidth: false }},
    securityLevel: "loose"
  }});

  mermaid.run({{ querySelector: "#diagram_{uid}" }}).then(function() {{
    document.getElementById("loading").style.display = "none";
    document.getElementById("wrapper").style.display = "block";
    // Auto fit after a small delay for SVG to settle
    setTimeout(fitToScreen, 120);
  }}).catch(function(err) {{
    document.getElementById("loading").innerHTML =
      "<div style='color:#dc2626;padding:24px;'>" +
      "<b>Mermaid render error:</b><br><pre style='white-space:pre-wrap;font-size:12px;'>" +
      err.toString() + "</pre></div>";
  }});
}})();
</script>
</body>
</html>
"""

    components.html(html_code, height=620, scrolling=False)

    if show_code:
        with st.expander("📝 Código Mermaid", expanded=False):
            st.code(mermaid_text, language="text")


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Process2Diagram")
    st.markdown("*v3 — Multi-Agent*")
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
    output_language = st.selectbox("Output language", ["Auto-detect", "Portuguese (BR)", "English"])

    st.markdown("### 🤖 Active Agents")
    run_bpmn = st.checkbox("Agente BPMN", value=True)
    run_minutes = st.checkbox("Agente Ata de Reunião", value=True)

    show_raw_json = st.checkbox("Show raw JSON", value=False)
    st.markdown("---")
    st.caption("Keys live **only in your session**.\nNever stored or logged.")

# ── Main area ─────────────────────────────────────────────────────────────────
st.markdown('<p class="main-title">Process2Diagram</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-title">Turn meeting transcripts into process diagrams — automatically.</p>',
    unsafe_allow_html=True,
)

if not get_session_llm_client(selected_provider):
    st.info(f"👈 Enter your **{selected_provider}** API key in the sidebar to start.")
    st.stop()

# ── Input ─────────────────────────────────────────────────────────────────────
st.markdown("### 📋 Transcript")
col_input, col_help = st.columns([3, 1])

with col_input:
    transcript_text = st.text_area(
        "Paste your meeting transcript here",
        height=220,
        placeholder=(
            "Exemplo:\n"
            "1) A equipe faz upload da foto.\n"
            "2) O sistema detecta rostos.\n"
            "3) O especialista identifica as pessoas.\n"
            "4) O sistema gera a legenda SVG.\n"
            "5) Os arquivos são enviados ao ECM."
        ),
        key="transcript_input",
    )

with col_help:
    st.markdown("**Dicas:**")
    st.markdown("""
- Passos numerados funcionam melhor
- Mencione atores: *"a equipe"*, *"o sistema"*
- Palavras de decisão: *"se"*, *"quando"*, *"caso contrário"*
- Regras: *"deve"*, *"não pode"*, *"obrigatório"*
    """)

uploaded_file = st.file_uploader("Ou envie um arquivo .txt", type=["txt"])
if uploaded_file:
    transcript_text = load_transcript(uploaded_file)
    st.success(f"Carregado: {uploaded_file.name}")

# ── Diagnóstico — sempre visível, fora do bloco generate_btn ─────────────────
with st.expander("🛠️ Diagnóstico — Arquivos de Skill em Runtime", expanded=False):
    st.caption(
        "Mostra o conteúdo **real** dos arquivos lidos pelo servidor. "
        "Use para confirmar que os skills estão corretos no repositório após cada commit."
    )

    import re as _re

    _SKILL_FILES = {
        "skill_bpmn.md": "skills/skill_bpmn.md",
        "skill_minutes.md": "skills/skill_minutes.md",
    }
    _SUSPICIOUS = [
        "cache_resource", "reruns", "KnowledgeHub", "st.cache",
        "Bearer", "base_agent", "ensure_utf8", "NLPChunker",
    ]

    for fname, rel_path in _SKILL_FILES.items():
        p = Path(rel_path)
        st.markdown(f"#### 📄 `{rel_path}`")

        if not p.exists():
            st.error(
                f"❌ **Arquivo não encontrado:** `{rel_path}`  \n"
                "O agente está rodando **sem system prompt**. "
                "Verifique o nome e o caminho no repositório."
            )
            continue

        raw = p.read_text(encoding="utf-8", errors="replace")
        found_suspicious = [t for t in _SUSPICIOUS if t in raw]
        has_placeholder = "{output_language}" in raw
        non_ascii = sum(1 for c in raw if ord(c) > 127)
        json_hits = len(_re.findall(r"json", raw, _re.IGNORECASE))

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Tamanho", f"{len(raw):,} chars")
        c2.metric("Não-ASCII", non_ascii)
        c3.metric("Ocorr. 'json'", json_hits)
        c4.metric("{output_language}", "✅" if has_placeholder else "❌")

        if found_suspicious:
            st.error(
                "⚠️ **Conteúdo suspeito** — tokens encontrados: "
                + ", ".join(f"`{t}`" for t in found_suspicious)
                + "  \nEste arquivo pode estar corrompido com texto de chat. "
                  "Substitua pelo arquivo correto no repositório."
            )
        else:
            st.success("✅ Arquivo íntegro — nenhum conteúdo suspeito detectado.")

        if not has_placeholder:
            st.warning("⚠️ Placeholder `{output_language}` ausente — instrução de idioma não será injetada.")

        st.code(raw, language="markdown")
        st.download_button(
            label=f"⬇️ Baixar {fname}",
            data=raw.encode("utf-8"),
            file_name=fname,
            mime="text/markdown",
            key=f"diag_dl_{fname}",
        )
        st.divider()

# ── Generate ──────────────────────────────────────────────────────────────────
generate_btn = st.button("⚡ Processar Transcrição", type="primary", use_container_width=True)

if generate_btn:
    if not transcript_text or len(transcript_text.strip()) < 20:
        st.warning("Por favor, forneça uma transcrição com pelo menos algumas linhas.")
        st.stop()

    if not run_bpmn and not run_minutes:
        st.warning("Selecione ao menos um agente na barra lateral.")
        st.stop()

    client_info = get_session_llm_client(selected_provider)

    # ── Initialize Knowledge Hub ──────────────────────────────────────────────
    hub = KnowledgeHub.new()
    hub.set_transcript(transcript_text)
    hub.meta.llm_provider = selected_provider

    # ── Progress display ──────────────────────────────────────────────────────
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

    # ── Run Orchestrator ──────────────────────────────────────────────────────
    try:
        orchestrator = Orchestrator(
            client_info=client_info,
            provider_cfg=provider_cfg,
            progress_callback=update_progress,
        )
        hub = orchestrator.run(
            hub,
            output_language=output_language,
            run_bpmn=run_bpmn,
            run_minutes=run_minutes,
        )
    except Exception as e:
        st.error(f"Erro no pipeline: {e}")
        st.stop()

    progress_placeholder.empty()

    # ── Metrics banner ────────────────────────────────────────────────────────
    col_a, col_b, col_c, col_d = st.columns(4)
    if hub.bpmn.ready:
        col_a.metric("Etapas BPMN", len(hub.bpmn.steps))
        col_b.metric("Conexões", len(hub.bpmn.edges))
        actors = list(set(s.actor for s in hub.bpmn.steps if s.actor))
        col_c.metric("Atores", len(actors))
    if hub.minutes.ready:
        col_d.metric("Action Items", len(hub.minutes.action_items))

    # ── Tabs ──────────────────────────────────────────────────────────────────
    tabs_to_show = []
    if hub.bpmn.ready:
        tabs_to_show += ["📐 BPMN 2.0", "📊 Mermaid"]
    if hub.minutes.ready:
        tabs_to_show += ["📋 Ata de Reunião"]
    tabs_to_show += ["🔧 Exportar", "🔍 Knowledge Hub"]

    tabs = st.tabs(tabs_to_show)
    tab_idx = 0

    # ── Tab: BPMN 2.0 (bpmn-js viewer) ───────────────────────────────────────
    if hub.bpmn.ready:
        with tabs[tab_idx]:
            st.caption(
                "Renderizado com [bpmn-js](https://bpmn.io) · Arraste para mover · Scroll para zoom · Tecla 0 para ajustar tela"
            )

            if hub.bpmn.bpmn_xml:
                bpmn_html = preview_from_xml(hub.bpmn.bpmn_xml)
                components.html(bpmn_html, height=1000, scrolling=False)

                if hub.bpmn.lanes:
                    st.markdown(f"**Swimlanes:** {', '.join(f'`{l}`' for l in hub.bpmn.lanes)}")
            else:
                st.info("ℹ️ Viewer bpmn-js indisponível — exibindo Mermaid como fallback.")
                render_mermaid_block(hub.bpmn.mermaid, show_code=False, key_suffix="bpmn_fallback")

        tab_idx += 1

        # ── Tab: Mermaid ──────────────────────────────────────────────────────
        with tabs[tab_idx]:
            st.caption("Fluxograma Mermaid · Cole em [mermaid.live](https://mermaid.live) para editar.")
            render_mermaid_block(hub.bpmn.mermaid, show_code=True, key_suffix="mermaid_tab")

        tab_idx += 1

    # ── Tab: Ata de Reunião ───────────────────────────────────────────────────
    if hub.minutes.ready:
        with tabs[tab_idx]:
            m = hub.minutes
            st.markdown(f"## {m.title}")
            col1, col2 = st.columns(2)
            col1.markdown(f"**Data:** {m.date or '—'}")
            col2.markdown(f"**Local:** {m.location or '—'}")

            if m.participants:
                st.markdown("**Participantes:** " + ", ".join(f"`{p}`" for p in m.participants))

            if m.agenda:
                st.markdown("### 📌 Pauta")
                for i, item in enumerate(m.agenda, 1):
                    st.markdown(f"{i}. {item}")

            if m.summary:
                st.markdown("### 📝 Resumo")
                for block in m.summary:
                    st.markdown(f"**{block.get('topic', '')}**")
                    st.markdown(block.get("content", ""))

            if m.decisions:
                st.markdown("### ✅ Decisões")
                for d in m.decisions:
                    st.markdown(f"- {d}")

            if m.action_items:
                st.markdown("### 🎯 Action Items")
                prio_colors = {"high": "🔴", "normal": "🟡", "low": "🟢"}
                rows = []
                for ai in m.action_items:
                    prio = prio_colors.get(ai.priority, "⚪")
                    rows.append({
                        "Prioridade": prio,
                        "Tarefa": ai.task,
                        "Responsável": ai.responsible,
                        "Prazo": ai.deadline or "—",
                    })
                st.dataframe(rows, use_container_width=True)

            if m.next_meeting:
                st.info(f"📅 Próxima reunião: **{m.next_meeting}**")

        tab_idx += 1

    # ── Tab: Exportar ─────────────────────────────────────────────────────────
    with tabs[tab_idx]:
        st.markdown("### ⬇️ Downloads")

        if hub.bpmn.ready:
            st.markdown("**Diagrama BPMN**")
            col1, col2, col3 = st.columns(3)

            with col1:
                if hub.bpmn.bpmn_xml:
                    st.download_button(
                        "⬇️ Diagrama .bpmn",
                        data=hub.bpmn.bpmn_xml,
                        file_name=f"{hub.bpmn.name.replace(' ', '_')}.bpmn",
                        mime="application/xml",
                        use_container_width=True,
                    )

            with col2:
                st.download_button(
                    "⬇️ Diagrama .drawio",
                    data=hub.bpmn.drawio_xml,
                    file_name=f"{hub.bpmn.name.replace(' ', '_')}.drawio",
                    mime="application/xml",
                    use_container_width=True,
                )

            with col3:
                mermaid_content = generate_mermaid(hub.bpmn)
                st.download_button(
                    "⬇️ Fluxo .mermaid",
                    data=mermaid_content,
                    file_name=f"{hub.bpmn.name.replace(' ', '_')}.mmd",
                    mime="text/plain",
                    use_container_width=True,
                )

            st.markdown("---")

            bpmn_json = json.dumps({
                "name": hub.bpmn.name,
                "steps": [vars(s) for s in hub.bpmn.steps],
                "edges": [vars(e) for e in hub.bpmn.edges],
                "lanes": hub.bpmn.lanes,
            }, ensure_ascii=False, indent=2)

            st.download_button(
                "⬇️ BPMN estruturado .json",
                data=bpmn_json,
                file_name=f"{hub.bpmn.name.replace(' ', '_')}_bpmn.json",
                mime="application/json",
            )

            with st.expander("Como importar o diagrama"):
                st.markdown("""
| Ferramenta | Como importar |
|---|---|
| **Camunda Modeler** | File → Open → selecione o `.bpmn` |
| **Bizagi Modeler** | File → Open → selecione o `.bpmn` |
| **draw.io** | File → Open from Device → selecione o `.drawio` |
| **bpmn.io** | Arraste o `.bpmn` para o canvas |
| **Mermaid Live** | Cole o conteúdo do `.mmd` em [mermaid.live](https://mermaid.live) |
""")

        if hub.minutes.ready:
            st.markdown("**Ata de Reunião**")
            md_content = AgentMinutes.to_markdown(hub.minutes)
            st.download_button(
                "⬇️ Ata .md",
                data=md_content,
                file_name="ata_reuniao.md",
                mime="text/markdown",
            )

    tab_idx += 1

    # ── Tab: Knowledge Hub ────────────────────────────────────────────────────
    with tabs[tab_idx]:
        st.markdown("### 🔍 Knowledge Hub — Estado da Sessão")
        col_meta1, col_meta2, col_meta3 = st.columns(3)
        col_meta1.metric("Versão do Hub", hub.version)
        col_meta2.metric("Tokens usados", hub.meta.total_tokens_used)
        col_meta3.metric("Agentes executados", len(hub.meta.agents_run))
        st.markdown(f"**Provider:** `{hub.meta.llm_provider}` — **Model:** `{hub.meta.llm_model}`")
        st.markdown(
            f"**Segmentos NLP:** {len(hub.nlp.segments)} — "
            f"**Atores:** {', '.join(hub.nlp.actors) or '—'} — "
            f"**Idioma:** `{hub.nlp.language_detected}`"
        )

        if show_raw_json:
            st.json(hub.to_dict())

        st.download_button(
            "⬇️ Knowledge Hub .json",
            data=hub.to_json(),
            file_name="knowledge_hub.json",
            mime="application/json",
        )

    # Store in session
    st.session_state["hub"] = hub
    