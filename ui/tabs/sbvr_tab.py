# ui/tabs/sbvr_tab.py
import streamlit as st


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


def render(hub, prefix, suffix):
    sbvr = hub.sbvr
    st.markdown("### 📖 Business Vocabulary & Rules (SBVR)")

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
    if sbvr.rules:
        st.markdown(f"#### 📋 Regras de Negócio ({len(sbvr.rules)})")
        for rule in sbvr.rules:
            badge = _RULE_TYPE_BADGE.get(rule.rule_type, rule.rule_type)
            source_note = f"  *(declarado por {rule.source})*" if rule.source else ""
            st.markdown(
                f"**{rule.id}** &nbsp; {badge}{source_note}  \n"
                f"{rule.statement}"
            )
            st.markdown("---")
    else:
        st.info("Nenhuma regra de negócio extraída.")

    # ── Export ────────────────────────────────────────────────────────────────
    import json
    from services.export_service import make_filename

    sbvr_dict = {
        "domain": sbvr.domain,
        "vocabulary": [
            {"term": t.term, "definition": t.definition, "category": t.category}
            for t in sbvr.vocabulary
        ],
        "rules": [
            {"id": r.id, "statement": r.statement,
             "rule_type": r.rule_type, "source": r.source}
            for r in sbvr.rules
        ],
    }
    st.download_button(
        "⬇️ Exportar SBVR (.json)",
        data=json.dumps(sbvr_dict, ensure_ascii=False, indent=2),
        file_name=make_filename("sbvr", "json", prefix, suffix),
        key="export_sbvr_json",
    )
