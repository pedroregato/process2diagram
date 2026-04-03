# ui/tabs/bpmn_tabs.py
import streamlit as st
import streamlit.components.v1 as components
from modules.bpmn_viewer import preview_from_xml
from modules.mermaid_renderer import render_mermaid_block
from agents.agent_mermaid import generate_mermaid
from services.export_service import make_filename

def render_bpmn(hub, prefix, suffix):
    st.markdown("### 📐 BPMN Process Model")
    if hub.bpmn.bpmn_xml:
        bpmn_html = preview_from_xml(hub.bpmn.bpmn_xml)
        components.html(bpmn_html, height=800, scrolling=False)
        if hub.bpmn.lanes:
            st.markdown("**Lanes:** " + ", ".join(hub.bpmn.lanes))
    else:
        st.warning("BPMN XML not available")

def render_mermaid(hub, prefix, suffix):
    st.markdown("### 📊 Mermaid Flowchart")
    render_mermaid_block(hub.bpmn.mermaid, show_code=True, key_suffix="modular_mermaid")

def render_validation(hub):
    val = hub.validation
    st.markdown(f"### Selection among {val.n_bpmn_runs} passes")
    best = val.bpmn_score
    rows = []
    for c in sorted(val.bpmn_candidates, key=lambda x: x.weighted, reverse=True):
        rows.append({
            "Pass": f"{'⭐' if c.run_index == best.run_index else ''} {c.run_index}",
            "Granularity": f"{c.granularity:.1f}",
            "Task Type": f"{c.task_type:.1f}",
            "Gateways": f"{c.gateways:.1f}",
            "Final Score": f"{c.weighted:.2f}",
            "Activities": c.n_tasks,
            "Gateways #": c.n_gateways,
        })
    st.dataframe(rows, use_container_width=True)
    st.caption(f"Selected pass {best.run_index} (score {best.weighted:.2f}/10)")
