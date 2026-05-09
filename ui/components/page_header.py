# ui/components/page_header.py
# ─────────────────────────────────────────────────────────────────────────────
# Componente de cabeçalho de página padronizado.
#
# Uso:
#   from ui.components.page_header import render_page_header
#   render_page_header("🚀", "Processar Transcrição", "Descrição curta da página.")
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st

_ACCENT = "#C97B1A"   # âmbar — cor de destaque da identidade visual


def render_page_header(icon: str, title: str, caption: str = "") -> None:
    """Renderiza um cabeçalho de página consistente com a identidade visual.

    Parâmetros
    ----------
    icon    : emoji ou string usada como ícone (ex: "🚀")
    title   : título principal da página
    caption : subtítulo/descrição curta (opcional)
    """
    st.markdown(
        f"<h1 style='margin-bottom:0.1rem'>{icon} {title}</h1>",
        unsafe_allow_html=True,
    )
    if caption:
        st.caption(caption)
    st.markdown(
        f"<hr style='margin-top:0.4rem;margin-bottom:1rem;border:none;"
        f"border-top:2px solid {_ACCENT};opacity:0.45'>",
        unsafe_allow_html=True,
    )
