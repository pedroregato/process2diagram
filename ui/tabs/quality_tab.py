# ui/tabs/quality_tab.py
import streamlit as st
from ui.components.copy_button import copy_button
from ui.components.download_button import download_button
from ui.components.transcript_highlighter import render_highlighted_transcript
from services.export_service import make_filename

def render(hub, prefix, suffix):
    tq = hub.transcript_quality
    pp = getattr(hub, 'preprocessing', None)
    grade_colors = {"A":"#16a34a","B":"#65a30d","C":"#ca8a04","D":"#ea580c","E":"#dc2626"}
    color = grade_colors.get(tq.grade, "#64748b")
    col1, col2 = st.columns([1,3])
    with col1:
        st.markdown(f"<div style='text-align:center;padding:2rem;border:2px solid {color}'><h1>{tq.grade}</h1><h3>{tq.overall_score:.1f}/100</h3></div>", unsafe_allow_html=True)
    with col2:
        for c in tq.criteria:
            with st.expander(f"{c.criterion} — {c.score}/100"):
                st.progress(c.score/100)
                st.markdown(c.justification)
    if tq.inconsistencies:
        with st.expander(f"🔍 Inconsistências ({len(tq.inconsistencies)})"):
            for inc in tq.inconsistencies:
                st.markdown(f"**{inc.speaker}** {inc.timestamp}: {inc.text} → {inc.reason}")
    if pp and pp.ready:
        st.markdown("### Texto Original vs. Pré‑processado")
        col_raw, col_clean = st.columns(2)
        with col_raw:
            st.text_area("Original", hub.transcript_raw, height=300, disabled=True)
            download_button(hub.transcript_raw, make_filename("transcricao_original", "txt", prefix, suffix), "⬇️ Original")
        with col_clean:
            render_highlighted_transcript(hub.transcript_clean, tq.inconsistencies)
            download_button(hub.transcript_clean, make_filename("transcricao_preprocessada", "txt", prefix, suffix), "⬇️ Limpa")
