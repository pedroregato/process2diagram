# ui/components/page_header.py
# ─────────────────────────────────────────────────────────────────────────────
# Componente de cabeçalho de página padronizado.
#
# Uso:
#   from ui.components.page_header import render_page_header
#   render_page_header("🚀", "Processar Transcrição", "Descrição curta da página.")
#
#   from ui.components.page_header import render_context_chip
#   render_context_chip(project_name)   # depois de require_active_project()
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


def render_context_chip(project_name: str, change_page: str = "pages/Home.py") -> None:
    """Chip neutro de contexto ativo (UX-07, melhorias/ux-amigabilidade-e-
    elegancia.md, achado E7: "banners verdes de Contexto repetidos em
    todas as páginas — o verde de sucesso perde significado"). Substitui
    o padrão repetido `st.success(f"📁 **Contexto:** ...")` + coluna
    "Trocar" — um pill compacto no lugar de um alerta de largura total,
    sem reservar a cor verde pra algo que não é "ação concluída com
    sucesso".

    Chamar DEPOIS de require_active_project() — project_name só é
    conhecido depois que o contexto ativo é resolvido."""
    col_chip, col_change = st.columns([5, 1])
    with col_chip:
        st.markdown(
            "<div style='display:inline-flex;align-items:center;gap:6px;"
            "padding:4px 12px;border-radius:14px;margin:2px 0 8px;"
            "background:rgba(148,163,184,.12);border:1px solid rgba(148,163,184,.3);"
            f"font-size:0.85rem;'>📁 <b>Contexto:</b> {project_name}</div>",
            unsafe_allow_html=True,
        )
    with col_change:
        st.page_link(change_page, label="Trocar")
