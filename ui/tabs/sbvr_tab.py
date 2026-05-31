# ui/tabs/sbvr_tab.py
import json
import streamlit as st
from services.export_service import make_filename

_CATEGORY_LABEL = {
    "concept":   "Conceito",
    "fact_type": "Tipo de Fato",
    "role":      "Papel",
    "process":   "Processo",
}

_RULE_TYPE_BADGE = {
    "constraint":   "🔒 Restrição",
    "operational":  "⚙️ Operacional",
    "behavioral":   "👤 Comportamental",
    "structural":   "🏗️ Estrutural",
}

_SPHERE_COLORS = {
    "marketing":   "#FF6B6B",
    "financeiro":  "#4ECDC4",
    "rh":          "#45B7D1",
    "operacoes":   "#96CEB4",
    "juridico":    "#FFEAA7",
    "tecnologia":  "#DDA0DD",
    "geral":       "#95A5A6",
}

_SPHERE_LABELS = {
    "marketing":   "Marketing",
    "financeiro":  "Financeiro",
    "rh":          "RH",
    "operacoes":   "Operações",
    "juridico":    "Jurídico",
    "tecnologia":  "Tecnologia",
    "geral":       "Geral",
}


def _sphere_badge(sphere: str) -> str:
    color = _SPHERE_COLORS.get(sphere, "#95A5A6")
    label = _SPHERE_LABELS.get(sphere, sphere.title())
    return f'<span style="background:{color};color:#fff;padding:2px 8px;border-radius:10px;font-size:11px">{label}</span>'


def render(hub, prefix, suffix):
    from ui.components.quality_badge import render_quality_badge
    _c1, _c2 = st.columns([8, 2])
    _c1.markdown("### 📖 Business Vocabulary & Rules (SBVR)")
    with _c2:
        render_quality_badge(hub, "sbvr")
    sbvr = hub.sbvr

    if sbvr.domain:
        st.caption(f"**Domínio:** {sbvr.domain}")

    # ── Vocabulary ────────────────────────────────────────────────────────────
    if sbvr.vocabulary:
        st.markdown("#### 📚 Vocabulário de Negócio")
        rows = [
            {
                "Termo": t.term,
                "Definição": t.definition,
                "Categoria": _CATEGORY_LABEL.get(t.category, t.category),
            }
            for t in sbvr.vocabulary
        ]
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum termo de vocabulário extraído.")

    st.markdown("---")

    # ── Business Rules ────────────────────────────────────────────────────────
    if not sbvr.rules:
        st.info("Nenhuma regra de negócio extraída.")
    else:
        rules = sbvr.rules
        has_spheres = any(getattr(r, "sphere", "geral") != "geral" for r in rules)

        # Metrics row
        spheres_found = list(dict.fromkeys(
            getattr(r, "sphere", "geral") for r in rules
        ))
        realized_count = 0
        if getattr(hub, "requirements", None) and hub.requirements.ready:
            all_br_refs = set(
                ref
                for req in hub.requirements.requirements
                for ref in getattr(req, "business_rule_refs", [])
            )
            realized_count = sum(1 for r in rules if r.id in all_br_refs)

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total de Regras", len(rules))
        col2.metric("Esferas", len(spheres_found))
        col3.metric("Com Dono Identificado", sum(1 for r in rules if getattr(r, "sphere_owner", "")))
        col4.metric(
            "Realizadas por Requisitos",
            f"{realized_count}/{len(rules)}" if realized_count > 0 else f"0/{len(rules)}",
        )

        st.markdown(f"#### 📋 Regras de Negócio ({len(rules)})")

        if has_spheres:
            # Filter by sphere
            sphere_options = ["Todas"] + [_SPHERE_LABELS.get(s, s.title()) for s in spheres_found]
            selected_label = st.selectbox("Filtrar por Esfera", sphere_options, key="sbvr_sphere_filter")
            selected_sphere = None
            if selected_label != "Todas":
                # Find back the key
                for k, v in _SPHERE_LABELS.items():
                    if v == selected_label:
                        selected_sphere = k
                        break

            # Group by sphere
            from collections import defaultdict
            by_sphere: dict[str, list] = defaultdict(list)
            for r in rules:
                by_sphere[getattr(r, "sphere", "geral")].append(r)

            for sphere in spheres_found:
                if selected_sphere and sphere != selected_sphere:
                    continue
                sphere_rules = by_sphere[sphere]
                color = _SPHERE_COLORS.get(sphere, "#95A5A6")
                label = _SPHERE_LABELS.get(sphere, sphere.title())
                with st.expander(f"**{label}** ({len(sphere_rules)} regras)", expanded=(selected_sphere == sphere)):
                    for rule in sphere_rules:
                        _render_rule(rule, hub)
        else:
            # Legacy flat list (no sphere info)
            for rule in rules:
                _render_rule(rule, hub)

    # ── Export ────────────────────────────────────────────────────────────────
    sbvr_dict = {
        "domain": sbvr.domain,
        "vocabulary": [
            {"term": t.term, "definition": t.definition, "category": t.category}
            for t in sbvr.vocabulary
        ],
        "rules": [
            {
                "id": r.id,
                "statement": r.statement,
                "rule_type": r.rule_type,
                "source": r.source,
                "sphere": getattr(r, "sphere", "geral"),
                "sphere_owner": getattr(r, "sphere_owner", ""),
                "bmm_policy_ref": getattr(r, "bmm_policy_ref", None),
                "speaker_quote": getattr(r, "speaker_quote", ""),
            }
            for r in sbvr.rules
        ],
    }

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(
            "⬇️ Exportar SBVR (.json)",
            data=json.dumps(sbvr_dict, ensure_ascii=False, indent=2),
            file_name=make_filename("sbvr", "json", prefix, suffix),
            key="export_sbvr_json",
        )
    with col2:
        try:
            from modules.sbvr_lexicon import generate_sbvr_lexicon
            project_name = getattr(hub, "_project_name", "") or ""
            lexicon_html = generate_sbvr_lexicon(sbvr, project_name)
            st.download_button(
                "📖 Exportar Léxico HTML",
                data=lexicon_html.encode("utf-8"),
                file_name=make_filename("sbvr_lexico", "html", prefix, suffix),
                mime="text/html",
                key="export_sbvr_lexicon",
            )
        except Exception:
            pass


def _render_rule(rule, hub) -> None:
    """Render a single SBVR rule card with traceability info."""
    badge = _RULE_TYPE_BADGE.get(rule.rule_type, rule.rule_type)
    source_note = f"  *(declarado por {rule.source})*" if rule.source else ""
    sphere_owner = getattr(rule, "sphere_owner", "")
    speaker_quote = getattr(rule, "speaker_quote", "")
    bmm_ref = getattr(rule, "bmm_policy_ref", None)

    st.markdown(
        f"**{rule.id}** &nbsp; {badge}{source_note}"
        + (f" &nbsp; · &nbsp; Dono: **{sphere_owner}**" if sphere_owner else "")
        + f"  \n{rule.statement}"
    )
    if speaker_quote:
        st.caption(f"💬 \"{speaker_quote}\"")
    if bmm_ref:
        st.caption(f"🎯 Política BMM: `{bmm_ref}`")

    # Show linked requirements
    if getattr(hub, "requirements", None) and hub.requirements.ready:
        linked = [
            req.id for req in hub.requirements.requirements
            if rule.id in getattr(req, "business_rule_refs", [])
        ]
        if linked:
            st.caption(f"🔗 Realizado por requisitos: {', '.join(linked)}")

    st.markdown("---")
