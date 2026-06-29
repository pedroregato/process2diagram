# ui/tabs/synthesizer_tab.py
import streamlit as st
import streamlit.components.v1 as components
from services.export_service import make_filename

def render(hub, prefix, suffix):
    syn = hub.synthesizer
    st.markdown("### 📄 Executive Report")
    st.download_button(
            "⬇️ Download HTML",
            data=syn.html,
            file_name=make_filename("executive_report", "html", prefix, suffix),
            key="synth_html"
        )
    # Lightweight placeholder during polling — same 1-widget structure keeps tree stable.
    if st.session_state.get("_diagram_is_loading", False):
        components.html(
            "<!DOCTYPE html><html><body style='display:flex;align-items:center;"
            "justify-content:center;height:100vh;background:#fff;"
            "font-family:sans-serif;color:#64748b'>"
            "<p>⏳ Aguardando conclusão do agente...</p></body></html>",
            height=800,
            scrolling=True,
        )
    else:
        components.html(syn.html, height=800, scrolling=True)
