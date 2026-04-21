# ui/tabs/requirements_tab.py
import streamlit as st
from services.export_service import make_filename

_TYPE_LABELS = {
    "ui_field":       "UI Field",
    "validation":     "Validation",
    "business_rule":  "Business Rule",
    "functional":     "Functional",
    "non_functional": "Non-functional",
}
_TYPE_REVERSE = {v: k for k, v in _TYPE_LABELS.items()}

_PRIORITY_ICON = {"high": "🔴", "medium": "🟡", "low": "🟢", "unspecified": "⚪"}

_TYPE_BADGE_COLOR = {
    "functional":     "#1e3a6e",
    "non_functional": "#2d1e6e",
    "business_rule":  "#0d4f2e",
    "validation":     "#4a3000",
    "ui_field":       "#134e4a",
}

_STATUS_BADGE = {
    "active":       ("#0d4f2e", "#4ade80",  "Ativo"),
    "backlog":      ("#1e293b", "#94a3b8",  "Backlog"),
    "approved":     ("#064e3b", "#6ee7b7",  "Aprovado"),
    "in_progress":  ("#1e3a6e", "#93c5fd",  "Em Desenvolvimento"),
    "implemented":  ("#134e4a", "#5eead4",  "Implementado"),
    "revised":      ("#4a3000", "#fbbf24",  "Revisado"),
    "contradicted": ("#4a0d0d", "#f87171",  "Contradição"),
    "deprecated":   ("#2a2a2a", "#9ca3af",  "Depreciado"),
    "rejected":     ("#3b0f1f", "#fda4af",  "Rejeitado"),
}


def render(hub, prefix, suffix):
    req = hub.requirements
    if not req.requirements:
        st.warning("Nenhum requisito extraído.")
        return

    # ── Métricas ─────────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    col1.metric("Total", len(req.requirements))
    col2.metric("Alta Prioridade", sum(1 for r in req.requirements if r.priority == "high"))
    col3.metric("Tipos", len(set(r.type for r in req.requirements)))

    # ── Filtros ───────────────────────────────────────────────────────────────
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        selected_type = st.selectbox(
            "Filtrar por tipo",
            ["Todos"] + list(_TYPE_LABELS.values()),
            key="req_tab_type_filter",
        )
    with col_f2:
        prio_opts = ["Todos", "high", "medium", "low", "unspecified"]
        selected_prio = st.selectbox(
            "Filtrar por prioridade",
            prio_opts,
            key="req_tab_prio_filter",
        )

    filtered = req.requirements
    if selected_type != "Todos":
        filtered = [r for r in filtered if r.type == _TYPE_REVERSE.get(selected_type)]
    if selected_prio != "Todos":
        filtered = [r for r in filtered if r.priority == selected_prio]

    st.caption(f"Exibindo {len(filtered)} de {len(req.requirements)} requisito(s)")

    # ── Grid resumo ───────────────────────────────────────────────────────────
    rows = []
    for r in filtered:
        status = getattr(r, "status", "active")
        _, _, status_label = _STATUS_BADGE.get(status, ("#1e293b", "#94a3b8", status.capitalize()))
        rows.append({
            "ID":          r.id,
            "Tipo":        _TYPE_LABELS.get(r.type, r.type),
            "Prioridade":  _PRIORITY_ICON.get(r.priority, "⚪"),
            "Status":      status_label,
            "Título":      r.title,
            "Proponente":  r.speaker or (r.actor or "—"),
        })
    if rows:
        st.dataframe(rows, use_container_width=True)

    # ── Detalhes por cartão ───────────────────────────────────────────────────
    st.markdown("### Detalhes")
    for r in filtered:
        type_label = _TYPE_LABELS.get(r.type, r.type)
        type_color = _TYPE_BADGE_COLOR.get(r.type, "#1e293b")
        status = getattr(r, "status", "active")
        st_bg, st_fg, st_label = _STATUS_BADGE.get(status, ("#1e293b", "#94a3b8", status.capitalize()))
        badges_html = (
            f'<span style="display:inline-block;padding:2px 10px;border-radius:20px;'
            f'font-size:.72rem;font-weight:600;background:{type_color};color:#e2e8f0;'
            f'margin-right:6px">{type_label}</span>'
            f'<span style="display:inline-block;padding:2px 10px;border-radius:20px;'
            f'font-size:.72rem;font-weight:600;background:{st_bg};color:{st_fg}">{st_label}</span>'
        )
        prio_icon = _PRIORITY_ICON.get(r.priority, "⚪")

        with st.expander(f"{r.id} — {r.title}  ·  {prio_icon} {r.priority.capitalize()}"):
            st.markdown(badges_html, unsafe_allow_html=True)
            st.markdown(f"**Descrição:** {r.description}")

            meta_parts = []
            if r.speaker:
                meta_parts.append(f"👤 Proponente: **{r.speaker}**")
            elif r.actor:
                meta_parts.append(f"👤 Ator: **{r.actor}**")
            if r.process_step:
                meta_parts.append(f"🔷 Etapa: {r.process_step}")
            for part in meta_parts:
                st.caption(part)

            if r.source_quote:
                st.caption(f'💬 *"{r.source_quote}"*')

    # ── Mind Map ─────────────────────────────────────────────────────────────
    st.markdown("### 🗺️ Mind Map")
    try:
        from modules.mindmap_interactive import render_mindmap_from_requirements
        render_mindmap_from_requirements(req, session_title=req.name, height=540)
    except Exception as e:
        st.warning(f"Mind map interativo falhou: {e}. Exibindo código Mermaid.")
        from modules.requirements_mindmap import generate_requirements_mindmap
        code = generate_requirements_mindmap(req)
        if code:
            st.code(code, language="mermaid")
