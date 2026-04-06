# ui/tabs/bmm_tab.py
import streamlit as st


_GOAL_TYPE_ICON = {"strategic": "🎯", "tactical": "📌", "operational": "⚡"}
_HORIZON_LABEL  = {"short": "Curto prazo", "medium": "Médio prazo", "long": "Longo prazo"}
_POLICY_ICON    = {
    "governance": "🏛️", "compliance": "⚖️",
    "operational": "⚙️", "financial": "💰",
}


def render(hub, prefix, suffix):
    bmm = hub.bmm
    st.markdown("### 🎯 Business Motivation Model (BMM)")

    # ── Vision / Mission ──────────────────────────────────────────────────────
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**🔭 Visão**")
        st.info(bmm.vision or "*Não identificada no transcript*")
    with col2:
        st.markdown("**🚀 Missão**")
        st.info(bmm.mission or "*Não identificada no transcript*")

    st.markdown("---")

    # ── Goals ─────────────────────────────────────────────────────────────────
    if bmm.goals:
        st.markdown(f"#### 🎯 Objetivos ({len(bmm.goals)})")
        for g in bmm.goals:
            icon    = _GOAL_TYPE_ICON.get(g.goal_type, "🎯")
            horizon = _HORIZON_LABEL.get(g.horizon, g.horizon)
            with st.expander(f"{icon} **{g.id}** — {g.name}  ·  *{horizon}*"):
                st.markdown(g.description or "*Sem descrição adicional.*")
                st.caption(f"Tipo: {g.goal_type.capitalize()}")
    else:
        st.info("Nenhum objetivo extraído.")

    # ── Strategies ────────────────────────────────────────────────────────────
    if bmm.strategies:
        st.markdown(f"#### 🗺️ Estratégias ({len(bmm.strategies)})")

        # Build goal name map for readable "supports" labels
        goal_names = {g.id: g.name for g in bmm.goals}

        for s in bmm.strategies:
            supports_txt = ", ".join(
                f"{gid} ({goal_names.get(gid, '?')})" for gid in s.supports
            ) if s.supports else "—"
            with st.expander(f"🗺️ **{s.id}** — {s.name}"):
                st.markdown(s.description or "*Sem descrição adicional.*")
                st.caption(f"Suporta: {supports_txt}")

    # ── Policies ─────────────────────────────────────────────────────────────
    if bmm.policies:
        st.markdown(f"#### 📜 Políticas ({len(bmm.policies)})")
        for p in bmm.policies:
            icon = _POLICY_ICON.get(p.category, "📜")
            cat  = p.category.capitalize() if p.category else "Geral"
            st.markdown(
                f"**{p.id}** &nbsp; {icon} *{cat}*  \n{p.statement}"
            )
            st.markdown("---")

    # ── Export ────────────────────────────────────────────────────────────────
    import json
    from services.export_service import make_filename

    bmm_dict = {
        "vision":     bmm.vision,
        "mission":    bmm.mission,
        "goals":      [{"id": g.id, "name": g.name, "description": g.description,
                        "goal_type": g.goal_type, "horizon": g.horizon}
                       for g in bmm.goals],
        "strategies": [{"id": s.id, "name": s.name, "description": s.description,
                        "supports": s.supports}
                       for s in bmm.strategies],
        "policies":   [{"id": p.id, "statement": p.statement, "category": p.category}
                       for p in bmm.policies],
    }
    st.download_button(
        "⬇️ Exportar BMM (.json)",
        data=json.dumps(bmm_dict, ensure_ascii=False, indent=2),
        file_name=make_filename("bmm", "json", prefix, suffix),
        key="export_bmm_json",
    )
