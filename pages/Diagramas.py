# pages/Diagramas.py
# ─────────────────────────────────────────────────────────────────────────────
# Dedicated full-screen diagram viewer — Streamlit multi-page app.
#
# Two modes:
#   A) hub present in session_state  → show pipeline results (BPMN, Mermaid, Mind Map)
#   B) no hub                        → Supabase fallback: project/process/version picker
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
from ui.auth_gate import apply_auth_gate
from modules.bpmn_viewer import preview_from_xml
from modules.mermaid_renderer import render_mermaid_block
from modules.supabase_client import supabase_configured

# ── Autenticação ───────────────────────────────────────────────────────────────
apply_auth_gate()

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


# ── Fallback: load from Supabase ──────────────────────────────────────────────
def _render_from_supabase() -> None:
    from core.project_store import list_projects, list_bpmn_processes, list_bpmn_versions

    st.markdown("## 📐 Visualizador de Diagramas")
    st.caption("Nenhuma transcrição processada nesta sessão — carregando diagramas salvos no Supabase.")
    st.page_link("pages/Pipeline.py", label="← Processar nova transcrição", icon="🚀")
    st.divider()

    if not supabase_configured():
        st.info("Supabase não configurado. Processe uma transcrição primeiro.")
        return

    projects = list_projects()
    if not projects:
        st.info("Nenhum projeto encontrado no Supabase.")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        proj_names = [p["name"] for p in projects]
        proj_map   = {p["name"]: p for p in projects}
        sel_proj   = st.selectbox("Projeto", proj_names, key="diag_sb_proj")
        project_id = proj_map[sel_proj]["id"]

    processes = list_bpmn_processes(project_id)
    if not processes:
        st.info("Nenhum processo BPMN encontrado neste projeto.")
        return

    with col2:
        def _proc_label(p: dict) -> str:
            mtg = p.get("meetings") or {}
            num = mtg.get("meeting_number")
            return f"#{num} · {p['name']}" if num else p["name"]

        proc_labels = [_proc_label(p) for p in processes]
        proc_map    = {lbl: p for lbl, p in zip(proc_labels, processes)}
        sel_proc    = st.selectbox("Processo", proc_labels, key="diag_sb_proc")
        process_id  = proc_map[sel_proc]["id"]

    versions = list_bpmn_versions(process_id)
    if not versions:
        st.info("Nenhuma versão encontrada para este processo.")
        return

    with col3:
        def _ver_label(v: dict) -> str:
            mtg = v.get("meetings") or {}
            title = mtg.get("title") or "—"
            return f"v{v['version']} · {title}"

        ver_labels = [_ver_label(v) for v in versions]
        ver_map    = {lbl: v for lbl, v in zip(ver_labels, versions)}
        sel_ver    = st.selectbox("Versão", ver_labels, key="diag_sb_ver")
        version    = ver_map[sel_ver]

    bpmn_xml = version.get("bpmn_xml") or ""
    mermaid  = version.get("mermaid_code") or ""

    # Build tab list
    tab_labels = []
    if bpmn_xml:
        tab_labels.append("📐 BPMN 2.0")
    if mermaid:
        tab_labels.append("📊 Mermaid")

    if not tab_labels:
        st.warning("Esta versão não tem BPMN XML armazenado.")
        return

    tabs = st.tabs(tab_labels)
    tab_idx = 0

    if "📐 BPMN 2.0" in tab_labels:
        with tabs[tab_idx]:
            st.caption(
                "Renderizado com bpmn-js · "
                "Arraste para mover · Scroll para zoom · Tecla **0** para ajustar tela"
            )
            components.html(preview_from_xml(bpmn_xml), height=900, scrolling=False)
            st.download_button(
                "⬇️ Baixar .bpmn",
                data=bpmn_xml,
                file_name=f"{proc_map[sel_proc]['name'].replace(' ', '_')}_v{version['version']}.bpmn",
                mime="application/xml",
            )
        tab_idx += 1

    if "📊 Mermaid" in tab_labels:
        with tabs[tab_idx]:
            st.caption("Fluxograma Mermaid · ↓/→ alterna direção · Scroll: zoom · Drag: mover")
            render_mermaid_block(mermaid, show_code=True, key_suffix="diag_sb_mermaid", height=820)


if hub is None:
    _render_from_supabase()
    st.stop()

hub = KnowledgeHub.migrate(hub)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("## 📐 Visualizador de Diagramas")
st.caption(
    f"Processo: **{hub.bpmn.name or hub.requirements.name or '—'}**  ·  "
    f"Hub v{hub.version}  ·  Provider: `{hub.meta.llm_provider}`"
)
st.page_link("pages/Pipeline.py", label="← Voltar para o pipeline", icon="⚙️")
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
