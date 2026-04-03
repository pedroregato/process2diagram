# ui/tabs/dev_tools_tab.py
import streamlit as st
from services.export_service import make_filename

def render(hub, show_raw_json):
    st.markdown("### 🔍 Knowledge Hub")
    col1, col2, col3 = st.columns(3)
    col1.metric("Version", hub.version)
    col2.metric("Tokens", hub.meta.total_tokens_used)
    col3.metric("Agents", len(hub.meta.agents_run))
    st.markdown(f"**Provider:** {hub.meta.llm_provider} — **Model:** {hub.meta.llm_model}")
    st.markdown(f"**NLP segments:** {len(hub.nlp.segments)} — **Actors:** {', '.join(hub.nlp.actors)}")
    if show_raw_json:
        st.json(hub.to_dict())
    st.download_button(
            "⬇️ Knowledge Hub JSON",
            data=hub.to_json(),
            file_name=make_filename("knowledge_hub", "json", "", ""),
            key="dev_hub_json"
        )
