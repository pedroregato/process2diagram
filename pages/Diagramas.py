# pages/Diagramas.py
# ─────────────────────────────────────────────────────────────────────────────
# Dedicated full-screen diagram viewer — Streamlit multi-page app.
#
# Shares st.session_state["hub"] with app.py.
# Shows BPMN 2.0 (bpmn-js), Mermaid flowchart, and Mind Map dos Requisitos.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

# ── Fix import path ───────────────────────────────────────────────────────────
root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from core.knowledge_hub import KnowledgeHub
from modules.bpmn_viewer import preview_from_xml
from modules.mermaid_renderer import render_mermaid_block

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Diagramas — Process2Diagram",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
  html, body, [class*="css"] { font-family: 'IBM Plex Sans', sans-serif; }
  h1, h2, h3 { font-family: 'IBM Plex Mono', monospace !important; letter-spacing: -0.03em; }
  .block-container { padding-top: 1.5rem; padding-bottom: 0.5rem; }
</style>
""", unsafe_allow_html=True)

# ── Load hub from session_state ───────────────────────────────────────────────
hub: KnowledgeHub | None = st.session_state.get("hub")

if hub is None:
    st.info("Nenhum resultado disponível. Processe uma transcrição na página principal primeiro.")
    st.page_link("app.py", label="← Voltar para Process2Diagram", icon="⚙️")
    st.stop()

hub = KnowledgeHub.migrate(hub)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 📐 Visualizador de Diagramas")
st.caption(
    f"Processo: **{hub.bpmn.name or hub.requirements.name or '—'}**  ·  "
    f"Hub v{hub.version}  ·  Provider: `{hub.meta.llm_provider}`"
)
st.page_link("app.py", label="← Voltar para o pipeline", icon="⚙️")
st.divider()

# ── Build tab list dynamically ────────────────────────────────────────────────
tab_labels: list[str] = []
if hub.bpmn.ready and hub.bpmn.bpmn_xml:
    tab_labels.append("📐 BPMN 2.0")
if hub.bpmn.ready and hub.bpmn.mermaid:
    tab_labels.append("📊 Mermaid")
if hub.requirements.ready and hub.requirements.requirements:
    tab_labels.append("🗺️ Mind Map")

if not tab_labels:
    st.warning("Nenhum diagrama disponível. Execute o pipeline com ao menos o Agente BPMN ativado.")
    st.stop()

tabs = st.tabs(tab_labels)
tab_idx = 0

# ── BPMN 2.0 (bpmn-js) ───────────────────────────────────────────────────────
if "📐 BPMN 2.0" in tab_labels:
    with tabs[tab_idx]:
        st.caption(
            "Renderizado com [bpmn-js](https://bpmn.io) · "
            "Arraste para mover · Scroll para zoom · Tecla **0** para ajustar tela"
        )
        bpmn_html = preview_from_xml(hub.bpmn.bpmn_xml)
        components.html(bpmn_html, height=900, scrolling=False)

        if hub.bpmn.lanes:
            st.markdown(f"**Swimlanes:** {', '.join(f'`{l}`' for l in hub.bpmn.lanes)}")

        st.download_button(
            "⬇️ Baixar .bpmn",
            data=hub.bpmn.bpmn_xml,
            file_name=f"{hub.bpmn.name.replace(' ', '_')}.bpmn",
            mime="application/xml",
        )
    tab_idx += 1

# ── Mermaid flowchart ─────────────────────────────────────────────────────────
if "📊 Mermaid" in tab_labels:
    with tabs[tab_idx]:
        st.caption("Fluxograma Mermaid · ↓/→ alterna direção · Scroll: zoom · Drag: mover")
        render_mermaid_block(hub.bpmn.mermaid, show_code=True, key_suffix="diag_mermaid", height=820)
    tab_idx += 1

# ── Mind Map dos Requisitos ───────────────────────────────────────────────────
if "🗺️ Mind Map" in tab_labels:
    with tabs[tab_idx]:
        from modules.mindmap_interactive import render_mindmap_from_requirements
        req = hub.requirements
        st.caption(
            f"**{len(req.requirements)}** requisitos agrupados por tipo · "
            "Clique nos grupos para expandir/retrair · Scroll: zoom · Drag: mover"
        )
        session_title = getattr(req, 'session_title', '') or req.name
        render_mindmap_from_requirements(req, session_title=session_title, height=840)
        if getattr(req, 'mindmap', ''):
            with st.expander("📝 Código Mermaid (mindmap)", expanded=False):
                st.code(req.mindmap, language="text")
    tab_idx += 1
