# ui/tabs/minutes_tab.py
import streamlit as st
from agents.agent_minutes import AgentMinutes
from services.export_service import make_filename

def render(hub, prefix, suffix):
    m = hub.minutes
    st.markdown(f"## {m.title}")
    col1, col2, col3 = st.columns(3)
    col1.markdown(f"**Date:** {m.date or 'N/A'}")
    col2.markdown(f"**Location:** {m.location or 'N/A'}")
    col3.markdown(f"**Participants:** {len(m.participants)}")
    if m.agenda:
        st.markdown("### Agenda")
        for i, item in enumerate(m.agenda, 1):
            st.markdown(f"{i}. {item}")
    if m.summary:
        st.markdown("### Summary")
        for block in m.summary:
            st.markdown(f"**{block.get('topic','')}**")
            st.markdown(block.get("content",""))
    if m.decisions:
        st.markdown("### Decisions")
        for d in m.decisions:
            st.markdown(f"- {d}")
    if m.action_items:
        st.markdown("### Action Items")
        rows = []
        for ai in m.action_items:
            rows.append({
                "Priority": ai.priority,
                "Task": ai.task,
                "Owner": ai.responsible,
                "Deadline": ai.deadline or "—"
            })
        st.dataframe(rows, use_container_width=True)
    st.markdown("---")
    st.markdown("### Export Minutes")
    md_content = AgentMinutes.to_markdown(m)
    
    # Dentro de render(hub, prefix, suffix):
    st.download_button("⬇️ .md", data=md_content, file_name=make_filename("minutes", "md", prefix, suffix), key="minutes_md")
    try:
        from modules.minutes_exporter import to_docx
        st.download_button("⬇️ .docx", data=to_docx(m), file_name=make_filename("minutes", "docx", prefix, suffix), key="minutes_docx")
    except Exception:
        pass
    try:
        from modules.minutes_exporter import to_pdf
        st.download_button("⬇️ .pdf", data=to_pdf(m), file_name=make_filename("minutes", "pdf", prefix, suffix), key="minutes_pdf")
    except Exception:
        pass
