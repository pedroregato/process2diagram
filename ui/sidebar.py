# ui/sidebar.py
import streamlit as st
from datetime import date
from modules.config import AVAILABLE_PROVIDERS
from modules.session_security import render_api_key_gate, render_extra_fields
from modules.auth import get_current_name, logout
from modules.i18n import t

def render_sidebar():
    with st.sidebar:
        st.markdown("⚡ **Process2Diagram**")

        # ── Language toggle ────────────────────────────────────────────────────
        _lang_options = ["pt-BR", "en-US"]
        _lang_labels  = ["🇧🇷 pt-BR", "🇺🇸 en-US"]
        _lang_idx = _lang_options.index(st.session_state.get("ui_language", "pt-BR"))
        _lang_sel = st.radio(
            t("lang_toggle_label"),
            _lang_labels,
            index=_lang_idx,
            horizontal=True,
            key="ui_lang_radio",
            label_visibility="collapsed",
        )
        st.session_state.ui_language = _lang_options[_lang_labels.index(_lang_sel)]

        # ── Usuário autenticado ────────────────────────────────────────────────
        name = get_current_name() or "User"
        col_usr, col_out = st.columns([3, 1])
        with col_usr:
            st.caption(f"👤 {name}")
        with col_out:
            if st.button(t("sign_out"), key="logout_btn"):
                logout()

        st.markdown("---")

        # ══════════════════════════════════════════════════════════════════════
        # CONFIGURAÇÃO RÁPIDA — sempre visível
        # ══════════════════════════════════════════════════════════════════════
        st.markdown(f"### {t('llm_provider')}")
        provider_names = list(AVAILABLE_PROVIDERS.keys())
        sel = st.selectbox(
            "Provider",
            provider_names,
            index=provider_names.index(st.session_state.selected_provider),
            key="provider_select",
        )
        st.session_state.selected_provider = sel
        st.session_state.provider_cfg = AVAILABLE_PROVIDERS[sel]
        st.caption(f"{t('model_label')} `{st.session_state.provider_cfg['default_model']}`")
        render_api_key_gate(sel, st.session_state.provider_cfg)
        render_extra_fields(sel, st.session_state.provider_cfg)

        out_lang = st.selectbox(
            t("output_language"),
            ["Auto-detect", "Portuguese (BR)", "English"],
            index=["Auto-detect", "Portuguese (BR)", "English"].index(
                st.session_state.output_language
            ),
            key="out_lang",
        )
        st.session_state.output_language = out_lang

        # ══════════════════════════════════════════════════════════════════════
        # CONFIGURAÇÃO AVANÇADA — expander fechado por padrão
        # ══════════════════════════════════════════════════════════════════════
        with st.expander(t("advanced_settings")):

            # ── Nomenclatura de arquivos ───────────────────────────────────────
            st.markdown(f"**{t('exported_files')}**")
            col_pref, col_suf = st.columns(2)
            with col_pref:
                pref = st.text_input(
                    t("prefix"),
                    value=st.session_state.prefix.rstrip("_"),
                    max_chars=11,
                )
            with col_suf:
                suf = st.text_input(
                    t("suffix"),
                    value=st.session_state.suffix,
                    max_chars=11,
                )
            st.session_state.prefix = (pref.strip() + "_") if pref.strip() else "P2D_"
            st.session_state.suffix = suf.strip() if suf.strip() else date.today().isoformat()

            st.markdown("---")

            # ── Agentes: Análise de Reunião ────────────────────────────────────
            st.markdown(f"**{t('meeting_analysis')}**")
            st.session_state.run_minutes      = st.checkbox(t("meeting_minutes"), value=st.session_state.run_minutes)
            st.session_state.run_requirements = st.checkbox(t("requirements"),    value=st.session_state.run_requirements)
            st.session_state.run_quality      = st.checkbox(t("quality"),         value=st.session_state.run_quality)

            st.markdown(f"**{t('diagrams')}**")
            st.session_state.run_bpmn = st.checkbox(
                t("bpmn_architect"), value=st.session_state.run_bpmn
            )
            if st.session_state.run_bpmn:
                st.session_state.n_bpmn_runs = st.select_slider(
                    t("optimization_passes"), [1, 3, 5], value=st.session_state.n_bpmn_runs
                )
                if st.session_state.n_bpmn_runs > 1:
                    st.caption(f"**{t('selection_weights')}**")
                    st.session_state.bpmn_weights = {
                        "granularity": st.slider(t("granularity"), 0, 10, st.session_state.bpmn_weights.get("granularity", 5)),
                        "task_type":   st.slider(t("task_type"),   0, 10, st.session_state.bpmn_weights.get("task_type",   5)),
                        "gateways":    st.slider(t("gateways"),    0, 10, st.session_state.bpmn_weights.get("gateways",    5)),
                        "structural":  st.slider(t("structural"),  0, 10, st.session_state.bpmn_weights.get("structural",  5)),
                        "semantic":    st.slider(t("semantic"),    0, 10, st.session_state.bpmn_weights.get("semantic",    5)),
                    }
                if st.session_state.n_bpmn_runs == 1:
                    st.session_state.use_langgraph = st.checkbox(
                        t("adaptive_retry"),
                        value=st.session_state.use_langgraph,
                        help=t("adaptive_retry_help"),
                    )
                    if st.session_state.use_langgraph:
                        st.session_state.validation_threshold = st.slider(
                            t("quality_threshold"), 0.0, 10.0,
                            value=float(st.session_state.validation_threshold),
                            step=0.5,
                        )
                        st.session_state.max_bpmn_retries = st.selectbox(
                            t("max_retries"), [1, 2, 3, 5],
                            index=[1, 2, 3, 5].index(st.session_state.max_bpmn_retries)
                            if st.session_state.max_bpmn_retries in [1, 2, 3, 5] else 2,
                        )
                        _lg_r_col1, _lg_r_col2 = st.columns(2)
                        st.session_state.max_minutes_retries = _lg_r_col1.selectbox(
                            "Retentativas Ata", [1, 2, 3],
                            index=[1, 2, 3].index(st.session_state.get("max_minutes_retries", 2)),
                            help="Máx. retentativas LangGraph para Ata de Reunião",
                        )
                        st.session_state.max_req_retries = _lg_r_col2.selectbox(
                            "Retentativas Req.", [1, 2, 3],
                            index=[1, 2, 3].index(st.session_state.get("max_req_retries", 2)),
                            help="Máx. retentativas LangGraph para Requisitos",
                        )

                st.session_state.enable_long_context = st.checkbox(
                    t("long_context"),
                    value=st.session_state.get("enable_long_context", True),
                    help=t("long_context_help"),
                )

            st.markdown(f"**{t('business_analysis')}**")
            st.session_state.run_sbvr        = st.checkbox(t("sbvr"),               value=st.session_state.run_sbvr)
            st.session_state.run_bmm         = st.checkbox(t("bmm"),                value=st.session_state.run_bmm)
            st.session_state.run_dmn         = st.checkbox(t("dmn"),                value=st.session_state.get("run_dmn", False))
            st.session_state.run_argumentation = st.checkbox(t("ibis"),             value=st.session_state.get("run_argumentation", False))
            st.session_state.run_synthesizer = st.checkbox(t("exec_report"),        value=st.session_state.run_synthesizer)
            st.session_state.run_query_summarizer = st.checkbox(
                t("perspective_summary"),
                value=st.session_state.get("run_query_summarizer", False),
                help=t("perspective_summary_help"),
            )
            st.session_state.run_communication_noise = st.checkbox(
                t("comm_noise"),
                value=st.session_state.get("run_communication_noise", False),
                help=t("comm_noise_help"),
            )
            st.session_state.run_knowledge_extractor = st.checkbox(
                t("knowledge_graph"),
                value=st.session_state.get("run_knowledge_extractor", True),
                help=t("knowledge_graph_help"),
            )
            st.session_state.run_ckf_updater = st.checkbox(
                t("update_ckf"),
                value=st.session_state.run_ckf_updater,
                help=t("update_ckf_help"),
            )
            st.session_state.run_provocations = st.checkbox(
                t("gen_provocations"),
                value=st.session_state.get("run_provocations", False),
                help=t("gen_provocations_help"),
            )

            st.markdown("---")

            # ── Modo desenvolvedor ─────────────────────────────────────────────
            st.caption(t("api_keys_session"))
            st.session_state.show_dev_tools = st.checkbox(
                t("developer_mode"), value=st.session_state.show_dev_tools
            )
            if st.session_state.show_dev_tools:
                st.session_state.show_raw_json = st.checkbox(
                    t("show_raw_json"), value=st.session_state.show_raw_json
                )

        # ══════════════════════════════════════════════════════════════════════
        # REEXECUÇÃO DE AGENTES — só aparece após o primeiro pipeline
        # ══════════════════════════════════════════════════════════════════════
        if "hub" in st.session_state:
            st.markdown("---")
            st.markdown(t("rerun_agent"))
            st.caption(t("rerun_caption"))
            col1, col2 = st.columns(2)
            with col1:
                if st.button(t("btn_quality"),      key="rr_q",   use_container_width=True):
                    st.session_state.rerun_agent = "quality"
                if st.button(t("btn_bpmn"),         key="rr_b",   use_container_width=True):
                    st.session_state.rerun_agent = "bpmn"
                if st.button(t("btn_mermaid"),      key="rr_mmd", use_container_width=True):
                    st.session_state.rerun_agent = "mermaid"
                if st.button(t("btn_minutes"),      key="rr_m",   use_container_width=True):
                    st.session_state.rerun_agent = "minutes"
                if st.button(t("btn_sbvr"),         key="rr_sv",  use_container_width=True):
                    st.session_state.rerun_agent = "sbvr"
                if st.button(t("btn_provocations"), key="rr_prov", use_container_width=True):
                    st.session_state.rerun_agent = "provocations"
            with col2:
                if st.button(t("btn_requirements"), key="rr_r",   use_container_width=True):
                    st.session_state.rerun_agent = "requirements"
                if st.button(t("btn_synthesizer"),  key="rr_s",   use_container_width=True):
                    st.session_state.rerun_agent = "synthesizer"
                if st.button(t("btn_bmm"),          key="rr_bm",  use_container_width=True):
                    st.session_state.rerun_agent = "bmm"
                if st.button(t("btn_dmn"),          key="rr_dmn", use_container_width=True):
                    st.session_state.rerun_agent = "dmn"
                if st.button(t("btn_ibis"),         key="rr_arg", use_container_width=True):
                    st.session_state.rerun_agent = "argumentation"
                if st.button(t("btn_summary"),      key="rr_qs",  use_container_width=True):
                    st.session_state.rerun_agent = "query_summarizer"
                if st.button(t("btn_noise"),        key="rr_cn",  use_container_width=True):
                    st.session_state.rerun_agent = "communication_noise"
