# ui/tabs/query_summary_tab.py
# Fase F — Multi-perspective post-pipeline summary display.

import streamlit as st
from core.knowledge_hub import KnowledgeHub

_ICONS = {
    "executive":       "🏛️",
    "technical":       "⚙️",
    "project_manager": "📋",
    "compliance":      "⚖️",
}

_ORDER = ["executive", "technical", "project_manager", "compliance"]


def render(hub: KnowledgeHub) -> None:
    qs = getattr(hub, "query_summary", None)
    if not qs or not qs.ready:
        st.info("Sumário por perspectiva não disponível. Habilite o agente na sidebar e reprocesse.")
        return

    # Index by perspective key for ordered rendering
    by_key = {p.perspective: p for p in qs.perspectives}

    for key in _ORDER:
        ps = by_key.get(key)
        if not ps:
            continue
        icon = _ICONS.get(key, "📌")
        st.markdown(f"### {icon} {ps.label}")

        if ps.headline:
            st.markdown(f"> {ps.headline}")

        col_hl, col_oi = st.columns([3, 2])

        with col_hl:
            if ps.highlights:
                st.markdown("**Destaques**")
                for h in ps.highlights:
                    st.markdown(f"- {h}")

        with col_oi:
            if ps.open_items:
                st.markdown("**Pontos em aberto**")
                for o in ps.open_items:
                    st.markdown(f"- {o}")

        if ps.recommended_actions:
            st.markdown("**Ações recomendadas**")
            for a in ps.recommended_actions:
                st.markdown(f"- {a}")

        st.divider()
