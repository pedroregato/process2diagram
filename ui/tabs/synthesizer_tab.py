# ui/tabs/synthesizer_tab.py
import streamlit as st
import streamlit.components.v1 as components
from services.export_service import make_filename

def render(hub, prefix, suffix):
    syn = hub.synthesizer
    st.markdown("### 📄 Executive Report")
    st.download_button("⬇️ Download HTML", data=syn.html, file_name=make_filename("executive_report", "html", prefix, suffix))
    components.html(syn.html, height=800, scrolling=True)
