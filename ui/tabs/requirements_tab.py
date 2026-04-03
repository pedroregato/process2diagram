# ui/tabs/requirements_tab.py
import streamlit as st
from services.export_service import make_filename

def render(hub, prefix, suffix):
    req = hub.requirements
    if not req.requirements:
        st.warning("No requirements extracted.")
        return
    type_labels = {"ui_field":"UI Field","validation":"Validation","business_rule":"Business Rule",
                   "functional":"Functional","non_functional":"Non-functional"}
    priority_colors = {"high":"🔴","medium":"🟡","low":"🟢","unspecified":"⚪"}
    col1, col2, col3 = st.columns(3)
    col1.metric("Total", len(req.requirements))
    col2.metric("High Priority", sum(1 for r in req.requirements if r.priority=="high"))
    col3.metric("Types", len(set(r.type for r in req.requirements)))
    selected_type = st.selectbox("Filter by type", ["All"]+list(type_labels.values()))
    type_reverse = {v:k for k,v in type_labels.items()}
    rows = []
    for r in req.requirements:
        if selected_type!="All" and r.type!=type_reverse.get(selected_type):
            continue
        rows.append({
            "ID": r.id,
            "Type": type_labels.get(r.type, r.type),
            "Priority": priority_colors.get(r.priority,"⚪"),
            "Title": r.title,
            "Process Step": r.process_step or "—",
            "Actor": r.actor or "—",
        })
    if rows:
        st.dataframe(rows, use_container_width=True)
    st.markdown("### Details")
    for r in req.requirements:
        if selected_type!="All" and r.type!=type_reverse.get(selected_type):
            continue
        with st.expander(f"{r.id} — {r.title}"):
            st.markdown(f"**Type:** {type_labels.get(r.type, r.type)}")
            st.markdown(f"**Priority:** {r.priority}")
            if r.actor: st.markdown(f"**Actor:** {r.actor}")
            if r.process_step: st.markdown(f"**Process step:** {r.process_step}")
            st.markdown(f"**Description:** {r.description}")
            if r.source_quote:
                st.markdown(f"> *\"{r.source_quote}\"* — {r.speaker or 'unknown'}")
    # Mind map
    st.markdown("### 🗺️ Mind Map")
    try:
        from modules.mindmap_interactive import render_mindmap_from_requirements
        render_mindmap_from_requirements(req, session_title=req.name, height=540)
    except Exception as e:
        st.warning(f"Mindmap interactive failed: {e}. Showing Mermaid code.")
        from modules.requirements_mindmap import generate_requirements_mindmap
        code = generate_requirements_mindmap(req)
        if code:
            st.code(code, language="mermaid")
