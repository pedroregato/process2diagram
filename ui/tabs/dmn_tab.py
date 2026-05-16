# ui/tabs/dmn_tab.py
import json
import streamlit as st
from services.export_service import make_filename


def render(hub, prefix, suffix):
    dmn = hub.dmn
    if not dmn or not dmn.ready:
        st.info("Nenhuma tabela DMN disponivel para esta reuniao.")
        return

    st.markdown("### Tabelas de Decisao DMN")
    st.caption(
        "Formalizacao das decisoes tomadas como **OMG Decision Model and Notation 1.4**. "
        "Cada tabela mapeia condicoes de entrada para resultados de negocio — "
        "tornando o raciocinio decisorio explicito, consultavel e reutilizavel."
    )

    from modules.dmn_viewer import render_dmn_model
    render_dmn_model(dmn, height=max(400, len(dmn.decisions) * 250))

    st.markdown("---")
    st.markdown("#### Export DMN")
    c1, c2 = st.columns(2)

    # XML export
    try:
        from modules.dmn_viewer import dmn_to_xml
        xml_bytes = dmn_to_xml(dmn).encode("utf-8")
        c1.download_button(
            "⬇️ DMN 1.4 (.xml)",
            data=xml_bytes,
            file_name=make_filename("decisions", "dmn", prefix, suffix),
            mime="application/xml",
            key="export_dmn_xml",
        )
    except Exception as e:
        c1.warning(f"XML nao disponivel: {e}")

    # JSON export
    decisions_list = []
    for d in dmn.decisions:
        decisions_list.append({
            "id": d.id, "name": d.name, "question": d.question,
            "rationale": d.rationale, "decided_by": d.decided_by,
            "hit_policy": d.hit_policy, "confidence": d.confidence,
            "inputs":  [{"label": i.label, "expression": i.expression} for i in d.inputs],
            "outputs": [{"label": o.label, "value": o.value} for o in d.outputs],
            "rules":   [{"inputs": r.inputs, "output": r.output, "annotation": r.annotation} for r in d.rules],
        })
    json_str = json.dumps({"decisions": decisions_list}, ensure_ascii=False, indent=2)
    c2.download_button(
        "⬇️ JSON",
        data=json_str,
        file_name=make_filename("decisions", "json", prefix, suffix),
        mime="application/json",
        key="export_dmn_json",
    )
