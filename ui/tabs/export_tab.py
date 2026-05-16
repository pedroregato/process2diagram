# ui/tabs/export_tab.py
import json
import streamlit as st
from agents.agent_minutes import AgentMinutes
from agents.agent_mermaid import generate_mermaid
from services.export_service import make_filename

def render(hub, prefix, suffix):
    st.markdown("### 📦 Export Assets")
    if hub.bpmn.ready:
        st.markdown("**Process Models**")
        if hub.bpmn.bpmn_xml:
            st.download_button(
                "⬇️ .bpmn",
                data=hub.bpmn.bpmn_xml,
                file_name=make_filename("process", "bpmn", prefix, suffix),
                key="export_bpmn"
            )
        st.download_button(
            "⬇️ .mermaid",
            data=generate_mermaid(hub.bpmn),
            file_name=make_filename("process", "mmd", prefix, suffix),
            key="export_mermaid"
        )
        st.markdown("---")
    if hub.minutes.ready:
        st.markdown("**Meeting Minutes**")
        md = AgentMinutes.to_markdown(hub.minutes)
        st.download_button(
            "⬇️ .md",
            data=md,
            file_name=make_filename("minutes", "md", prefix, suffix),
            key="export_minutes_md"
        )
        try:
            from modules.minutes_exporter import to_docx, to_pdf
            st.download_button(
                "⬇️ .docx",
                data=to_docx(hub.minutes),
                file_name=make_filename("minutes", "docx", prefix, suffix),
                key="export_minutes_docx"
            )
            st.download_button(
                "⬇️ .pdf",
                data=to_pdf(hub.minutes),
                file_name=make_filename("minutes", "pdf", prefix, suffix),
                key="export_minutes_pdf"
            )
        except Exception:
            pass
        st.markdown("---")
    if hub.requirements.ready:
        st.markdown("**Requirements**")
        st.download_button(
            "⬇️ .md",
            data=hub.requirements.markdown,
            file_name=make_filename("requirements", "md", prefix, suffix),
            key="export_req_md"
        )
        req_json = json.dumps(
            {"name": hub.requirements.name, "requirements": [r.__dict__ for r in hub.requirements.requirements]},
            ensure_ascii=False, indent=2
        )
        st.download_button(
            "⬇️ .json",
            data=req_json,
            file_name=make_filename("requirements", "json", prefix, suffix),
            key="export_req_json"
        )
        st.markdown("---")

    if getattr(hub, 'dmn', None) and hub.dmn.ready:
        st.markdown("**Decision Tables (DMN)**")
        try:
            from modules.dmn_viewer import dmn_to_xml
            import json as _json
            st.download_button(
                "⬇️ DMN 1.4 (.xml)",
                data=dmn_to_xml(hub.dmn).encode("utf-8"),
                file_name=make_filename("decisions", "dmn", prefix, suffix),
                mime="application/xml",
                key="export_tab_dmn_xml",
            )
            decisions_list = [
                {"id": d.id, "name": d.name, "question": d.question,
                 "rationale": d.rationale, "decided_by": d.decided_by,
                 "rules": [{"inputs": r.inputs, "output": r.output} for r in d.rules]}
                for d in hub.dmn.decisions
            ]
            st.download_button(
                "⬇️ DMN JSON",
                data=_json.dumps({"decisions": decisions_list}, ensure_ascii=False, indent=2),
                file_name=make_filename("decisions", "json", prefix, suffix),
                key="export_tab_dmn_json",
            )
        except Exception:
            pass
        st.markdown("---")

    if getattr(hub, 'argumentation', None) and hub.argumentation.ready:
        import json as _json2, dataclasses
        st.markdown("**Argumentation Map (IBIS)**")
        ibis_data = {"questions": [dataclasses.asdict(q) for q in hub.argumentation.questions]}
        st.download_button(
            "⬇️ IBIS JSON",
            data=_json2.dumps(ibis_data, ensure_ascii=False, indent=2),
            file_name=make_filename("argumentation", "json", prefix, suffix),
            key="export_tab_ibis_json",
        )
        st.markdown("---")
    if hub.synthesizer.ready:
        st.markdown("**Executive Report**")
        st.download_button(
            "⬇️ .html",
            data=hub.synthesizer.html,
            file_name=make_filename("executive_report", "html", prefix, suffix),
            key="export_report_html"
        )
