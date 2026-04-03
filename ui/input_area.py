# ui/input_area.py
import streamlit as st
from services.file_ingest import load_transcript
from services.preprocessor_service import preprocess_transcript

def update_transcript():
    st.session_state.transcript_text = st.session_state.transcript_input

def render_input_area():
    with st.container():
        st.markdown("### 📥 Input Transcript")
        st.text_area(
            "Paste your meeting transcript here",
            value=st.session_state.transcript_text,
            height=250,
            key="transcript_input",
            on_change=update_transcript,
            label_visibility="collapsed"
        )
        col_up, col_btn = st.columns([1,1])
        with col_up:
            uploaded = st.file_uploader("Or upload a file", type=["txt","docx","pdf"], label_visibility="collapsed")
            if uploaded:
                st.session_state.transcript_text = load_transcript(uploaded)
                # limpa estados antigos
                st.session_state.pop("pp_result", None)
                st.session_state.pop("curated_clean", None)
                st.session_state.pop("hub", None)
        with col_btn:
            if st.button("🧹 Pré‑processar Transcrição (sem LLM)"):
                if st.session_state.transcript_text.strip():
                    pp = preprocess_transcript(st.session_state.transcript_text)
                    st.session_state.pp_result = pp
                    st.session_state.curated_clean = pp.clean_text
                    st.success("Pré‑processamento concluído!")
        if "pp_result" in st.session_state:
            pp = st.session_state.pp_result
            st.markdown("#### 🧹 Curadoria da Transcrição")
            st.markdown(f"Fillers removidos: {pp.fillers_removed} | Artefatos: {pp.artifact_turns} | Repetições: {pp.repetitions_collapsed}")
            for issue in pp.metadata_issues:
                st.warning(issue)
            col_orig, col_clean = st.columns(2)
            with col_orig:
                st.markdown("**Original**")
                st.text_area("orig", st.session_state.transcript_text, height=200, disabled=True)
            with col_clean:
                st.markdown("**Pré‑processada (editável)**")
                curated = st.text_area("clean", st.session_state.curated_clean, height=200, key="curated_edit")
                st.session_state.curated_clean = curated
            if st.button("✅ Usar texto curado no pipeline"):
                st.session_state.transcript_text = st.session_state.curated_clean
                st.success("Texto curado definido como transcrição principal.")
        return st.button("🚀 Generate Insights", type="primary", use_container_width=True)
