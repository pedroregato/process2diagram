# pages/Orientacoes_Manifesto.py
# ─────────────────────────────────────────────────────────────────────────────
# Página de orientação: Manifesto de Engenharia do P2D.
# Renderiza ENGINEERING_MANIFESTO.md via st.markdown().
# ─────────────────────────────────────────────────────────────────────────────

import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
from core.session_state import init_session_state
from ui.auth_gate import apply_auth_gate
from ui.components.page_header import render_page_header

apply_auth_gate()
init_session_state()

render_page_header("🛸", "Manifesto de Engenharia", "Blueprint Arquitetural e Governança do P2D")

_manifesto_path = _ROOT / "manifestos" / "ENGINEERING_MANIFESTO.md"
if _manifesto_path.exists():
    st.markdown(_manifesto_path.read_text(encoding="utf-8"))
else:
    st.error("Arquivo manifestos/ENGINEERING_MANIFESTO.md não encontrado.")
