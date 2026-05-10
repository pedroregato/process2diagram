# pages/ArquiteturaViewer.py
# ─────────────────────────────────────────────────────────────────────────────
# Visualizador de diagramas de arquitetura em tela cheia.
# Aberto via st.switch_page() com st.session_state["arch_viewer_diagram"]
# definido pelo chamador ("pipeline" | "assistente" | "comms").
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from ui.auth_gate import apply_auth_gate
from ui.architecture_diagram import render_architecture_diagram
from ui.assistant_diagram import render_assistant_diagram
from ui.comms_diagram import render_comms_diagram

apply_auth_gate()

# ── Seleção do diagrama ───────────────────────────────────────────────────────

DIAGRAMS = {
    "pipeline":   ("🚀 Pipeline de Processamento",     render_architecture_diagram, 900),
    "assistente": ("💬 Assistente — Pipeline RAG",      render_assistant_diagram,    900),
    "comms":      ("🔌 Comunicação & Integrações",      render_comms_diagram,        900),
}

current = st.session_state.get("arch_viewer_diagram", "pipeline")
if current not in DIAGRAMS:
    current = "pipeline"

# ── Barra de controle ─────────────────────────────────────────────────────────

col_back, col_sel, _ = st.columns([1, 3, 6])

with col_back:
    st.page_link(
        "pages/Orientacoes_Arquiteturas.py",
        label="← Arquiteturas",
        icon="🏗️",
    )

with col_sel:
    selected = st.selectbox(
        "Diagrama",
        options=list(DIAGRAMS.keys()),
        index=list(DIAGRAMS.keys()).index(current),
        format_func=lambda k: DIAGRAMS[k][0],
        label_visibility="collapsed",
        key="arch_viewer_sel",
    )
    st.session_state["arch_viewer_diagram"] = selected

# ── Renderização ──────────────────────────────────────────────────────────────

title, render_fn, height = DIAGRAMS[selected]
st.markdown(f"### {title}")
render_fn(height=height)
