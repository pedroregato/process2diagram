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
            st.download_button("⬇️ .bpmn", data=hub.bpmn.bpmn_xml, 
                               file_name=make_filename("process", "bpmn", prefix, suffix),
                               key="export_bpmn")
        st.download_button("⬇️ .mermaid", data=generate_mermaid(hub.bpmn), 
                           file_name=make_filename("process", "mmd", prefix, suffix),
                           key="export_mermaid")
        st.markdown("---")
    if hub.minutes.ready:
        st.markdown("**Meeting Minutes**")
        md = AgentMinutes.to_markdown(hub.minutes)
        st.download_button("⬇️ .md", data=md, 
                           file_name=make_filename("minutes", "md", prefix, suffix),
                           key="export_minutes_md")
        try:
            from modules.minutes_exporter import to_docx, to_pdf
            st.download_button("⬇️ .docx", data=to_docx(hub.minutes), 
                               file_name=make_filename("minutes", "docx", prefix, suffix),
                               key="export_minutes_docx")
            st.download_button("⬇️ .pdf", data=to_pdf(hub.minutes), 
                               file_name=make_filename("minutes", "pdf", prefix, suffix),
                               key="export_minutes_pdf")
        except Exception:
            pass
        st.markdown("---")
    if hub.requirements.ready:
        st.markdown("**Requirements**")
        st.download_button("⬇️ .md", data=hub.requirements.markdown, 
                           file_name=make_filename("requirements", "md", prefix, suffix),
                           key="export_requirements_md")
        req_json = json.dumps({"name": hub.requirements.name, 
                               "requirements": [r.__dict__ for r in hub.requirements.requirements]}, 
                              ensure_ascii=False, indent=2)
        st.download_button("⬇️ .json", data=req_json, 
                           file_name=make_filename("requirements", "json", prefix, suffix),
                           key="export_requirements_json")
        st.markdown("---")
    if hub.synthesizer.ready:
        st.markdown("**Executive Report**")
        st.download_button("⬇️ .html", data=hub.synthesizer.html, 
                           file_name=make_filename("executive_report", "html", prefix, suffix),
                           key="export_report_html")
