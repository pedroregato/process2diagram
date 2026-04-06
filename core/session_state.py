# core/session_state.py
import streamlit as st
from datetime import date
from modules.config import AVAILABLE_PROVIDERS

def init_session_state():
    """Inicializa todas as chaves do session_state com valores padrão.
    Deve ser chamado imediatamente após st.set_page_config().
    """
    if "selected_provider" not in st.session_state:
        st.session_state.selected_provider = "DeepSeek"
    if "provider_cfg" not in st.session_state:
        st.session_state.provider_cfg = AVAILABLE_PROVIDERS.get(st.session_state.selected_provider, {})
    if "output_language" not in st.session_state:
        st.session_state.output_language = "Auto-detect"
    if "prefix" not in st.session_state:
        st.session_state.prefix = "P2D_"
    if "suffix" not in st.session_state:
        st.session_state.suffix = date.today().isoformat()
    if "run_quality" not in st.session_state:
        st.session_state.run_quality = True
    if "run_bpmn" not in st.session_state:
        st.session_state.run_bpmn = True
    if "run_minutes" not in st.session_state:
        st.session_state.run_minutes = True
    if "run_requirements" not in st.session_state:
        st.session_state.run_requirements = True
    if "run_sbvr" not in st.session_state:
        st.session_state.run_sbvr = False
    if "run_bmm" not in st.session_state:
        st.session_state.run_bmm = False
    if "run_synthesizer" not in st.session_state:
        st.session_state.run_synthesizer = False
    if "n_bpmn_runs" not in st.session_state:
        st.session_state.n_bpmn_runs = 1
    if "bpmn_weights" not in st.session_state:
        st.session_state.bpmn_weights = {"granularity": 5, "task_type": 5, "gateways": 5, "structural": 5}
    if "show_dev_tools" not in st.session_state:
        st.session_state.show_dev_tools = False
    if "show_raw_json" not in st.session_state:
        st.session_state.show_raw_json = False
    if "transcript_text" not in st.session_state:
        st.session_state.transcript_text = ""
