# ui/sidebar.py
import streamlit as st
from datetime import date
from modules.config import AVAILABLE_PROVIDERS
from modules.session_security import render_api_key_gate

def render_sidebar():
    with st.sidebar:
        st.markdown("⚡ Process2Diagram", unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("### 🤖 LLM Engine")
        provider_names = list(AVAILABLE_PROVIDERS.keys())
        sel = st.selectbox("Provider", provider_names,
                           index=provider_names.index(st.session_state.selected_provider),
                           key="provider_select")
        st.session_state.selected_provider = sel
        st.session_state.provider_cfg = AVAILABLE_PROVIDERS[sel]
        st.code(st.session_state.provider_cfg['default_model'])
        render_api_key_gate(sel, st.session_state.provider_cfg)

        st.markdown("### ⚙️ Configuration")
        out_lang = st.selectbox("Output Language",
                                ["Auto-detect", "Portuguese (BR)", "English"],
                                index=["Auto-detect","Portuguese (BR)","English"].index(st.session_state.output_language),
                                key="out_lang")
        st.session_state.output_language = {"Auto-detect":"Auto-detect","Portuguese (BR)":"Portuguese (BR)","English":"English"}[out_lang]

        col_pref, col_suf = st.columns(2)
        with col_pref:
            pref = st.text_input("Prefix (max 11 chars)", value=st.session_state.prefix.rstrip("_"), max_chars=11)
        with col_suf:
            suf = st.text_input("Suffix (max 11 chars)", value=st.session_state.suffix, max_chars=11)
        st.session_state.prefix = (pref.strip() + "_") if pref.strip() else "P2D_"
        st.session_state.suffix = suf.strip() if suf.strip() else date.today().isoformat()

        st.markdown("### 🤖 Active Agents")
        st.session_state.run_quality = st.checkbox("Quality Inspector", value=st.session_state.run_quality)
        st.session_state.run_bpmn = st.checkbox("BPMN Architect", value=st.session_state.run_bpmn)
        if st.session_state.run_bpmn:
            st.session_state.n_bpmn_runs = st.select_slider("Optimization Passes", [1,3,5], value=st.session_state.n_bpmn_runs)
            if st.session_state.n_bpmn_runs > 1:
                with st.expander("Selection Weights"):
                    st.session_state.bpmn_weights = {
                        "granularity": st.slider("Granularity", 0, 10, st.session_state.bpmn_weights.get("granularity", 5)),
                        "task_type":   st.slider("Task Type",   0, 10, st.session_state.bpmn_weights.get("task_type",   5)),
                        "gateways":    st.slider("Gateways",    0, 10, st.session_state.bpmn_weights.get("gateways",    5)),
                        "structural":  st.slider("Structural",  0, 10, st.session_state.bpmn_weights.get("structural",  5)),
                    }
        st.session_state.run_minutes = st.checkbox("Meeting Minutes", value=st.session_state.run_minutes)
        st.session_state.run_requirements = st.checkbox("Requirements", value=st.session_state.run_requirements)
        st.session_state.run_sbvr = st.checkbox("Business Vocabulary & Rules (SBVR)", value=st.session_state.run_sbvr)
        st.session_state.run_bmm = st.checkbox("Business Motivation Model (BMM)", value=st.session_state.run_bmm)
        st.session_state.run_synthesizer = st.checkbox("Executive Report", value=st.session_state.run_synthesizer)

        st.markdown("---")
        st.caption("🔒 API keys are session-only.")
        st.session_state.show_dev_tools = st.checkbox("Developer Mode", value=st.session_state.show_dev_tools)
        if st.session_state.show_dev_tools:
            st.session_state.show_raw_json = st.checkbox("Show Raw JSON", value=st.session_state.show_raw_json)

        # ── SEÇÃO DE REEXECUÇÃO (diagnóstico incluído) ──
        if "hub" in st.session_state:
            st.markdown("---")
            st.markdown("### 🔄 Re‑run Agents")
            st.caption("Run any agent again on the current transcript.")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔬 Quality", key="rr_q"):
                    st.session_state.rerun_agent = "quality"
                if st.button("📐 BPMN", key="rr_b"):
                    st.session_state.rerun_agent = "bpmn"
                if st.button("📋 Minutes", key="rr_m"):
                    st.session_state.rerun_agent = "minutes"
            with col2:
                if st.button("📝 Requirements", key="rr_r"):
                    st.session_state.rerun_agent = "requirements"
                if st.button("📄 Report", key="rr_s"):
                    st.session_state.rerun_agent = "synthesizer"
        else:
            # Mensagem de diagnóstico (opcional)
            st.caption("(Execute o pipeline primeiro para ver os botões de reexecução)")
