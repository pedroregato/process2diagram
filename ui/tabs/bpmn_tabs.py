# ui/tabs/bpmn_tabs.py
import streamlit as st
import streamlit.components.v1 as components
from modules.bpmn_viewer import preview_from_xml
from modules.mermaid_renderer import render_mermaid_block
from agents.agent_mermaid import generate_mermaid
from services.export_service import make_filename

def render_bpmn(hub, prefix, suffix):
    from ui.components.quality_badge import render_quality_badge
    _c1, _c2 = st.columns([8, 2])
    _c1.markdown("### 📐 BPMN Process Model")
    with _c2:
        render_quality_badge(hub, "bpmn")
    if hub.bpmn.bpmn_xml:
        bpmn_html = preview_from_xml(hub.bpmn.bpmn_xml)
        components.html(bpmn_html, height=800, scrolling=False)
        if hub.bpmn.lanes:
            st.markdown("**Lanes:** " + ", ".join(hub.bpmn.lanes))

        # ── Structural validation panel ────────────────────────────────────
        try:
            from modules.bpmn_structural_validator import validate_bpmn_structure
            issues = validate_bpmn_structure(hub.bpmn)
            if issues:
                errors   = [i for i in issues if i.severity == "error"]
                warnings = [i for i in issues if i.severity == "warning"]
                infos    = [i for i in issues if i.severity == "info"]
                label = (
                    f"🔴 {len(errors)} erro(s)" if errors else
                    f"🟡 {len(warnings)} aviso(s)" if warnings else
                    f"🔵 {len(infos)} info(s)"
                )
                with st.expander(f"Diagnóstico estrutural — {label}", expanded=bool(errors)):
                    for i in errors:
                        st.error(f"`{i.element_id or '—'}` {i.message}")
                    for i in warnings:
                        st.warning(f"`{i.element_id or '—'}` {i.message}")
                    for i in infos:
                        st.info(f"`{i.element_id or '—'}` {i.message}")
            else:
                st.caption("✅ Nenhum problema estrutural detectado.")
        except Exception:
            pass

        repair_log = getattr(hub.bpmn, 'repair_log', [])
        if repair_log:
            with st.expander(f"🔧 {len(repair_log)} auto-repair(s) applied", expanded=False):
                for entry in repair_log:
                    st.caption(f"• {entry}")

        lg_attempts = getattr(hub.bpmn, 'lg_attempts', 0)
        if lg_attempts > 0:
            lg_score   = getattr(hub.bpmn, 'lg_final_score', 0.0)
            lg_min_r   = getattr(hub.validation, 'lg_minutes_retries', 0)
            lg_req_r   = getattr(hub.validation, 'lg_req_retries', 0)
            lg_del_log = getattr(hub.validation, 'lg_delegation_log', [])

            parts = [f"BPMN: {lg_attempts} tentativa(s), score {lg_score:.1f}/10"]
            if lg_min_r > 0:
                parts.append(f"Ata: {lg_min_r} tentativa(s)")
            if lg_req_r > 0:
                parts.append(f"Requisitos: {lg_req_r} tentativa(s)")
            if lg_del_log:
                _agent_labels = {"bpmn": "BPMN", "minutes": "Ata", "requirements": "Requisitos"}
                del_names = [_agent_labels.get(d.get("agent", ""), d.get("agent", "")) for d in lg_del_log]
                parts.append(f"🤝 Delegações A2A: {', '.join(del_names)}")

            st.info(f"🔄 **LangGraph expandido** — " + " · ".join(parts))

            coord_notes = getattr(hub.validation, 'lg_coordination_notes', [])
            if coord_notes:
                with st.expander(f"🔗 {len(coord_notes)} nota(s) do coordenador", expanded=False):
                    for note in coord_notes:
                        st.caption(note)
            if lg_del_log:
                with st.expander(f"🤝 {len(lg_del_log)} delegação(ões) A2A realizadas", expanded=False):
                    for d in lg_del_log:
                        agent_label = {"bpmn": "AgentBPMN", "minutes": "AgentMinutes", "requirements": "AgentRequirements"}.get(d.get("agent", ""), d.get("agent", ""))
                        st.caption(f"→ **{agent_label}**: {d.get('summary', '')}")
    else:
        st.warning("BPMN XML not available")

def render_mermaid(hub, prefix, suffix):
    from ui.components.quality_badge import render_quality_badge
    _c1, _c2 = st.columns([8, 2])
    _c1.markdown("### 📊 Mermaid Flowchart")
    with _c2:
        render_quality_badge(hub, "mermaid")
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
            "Structural": f"{getattr(c, 'structural', 0.0):.1f}",
            "Issues": f"{getattr(c, 'n_structural_errors', 0)}E / {getattr(c, 'n_structural_warnings', 0)}W",
            "Final Score": f"{c.weighted:.2f}",
            "Activities": c.n_tasks,
            "Gateways #": c.n_gateways,
        })
    st.dataframe(rows, use_container_width=True)
    st.caption(f"Selected pass {best.run_index} (score {best.weighted:.2f}/10)")
