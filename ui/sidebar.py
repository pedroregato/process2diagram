# ui/sidebar.py
import streamlit as st
from datetime import date
from modules.config import AVAILABLE_PROVIDERS
from modules.session_security import render_api_key_gate
from modules.auth import get_current_name, logout

def render_sidebar():
    with st.sidebar:
        st.markdown("⚡ **Process2Diagram**")

        # ── Usuário autenticado ────────────────────────────────────────────────
        name = get_current_name() or "Usuário"
        col_usr, col_out = st.columns([3, 1])
        with col_usr:
            st.caption(f"👤 {name}")
        with col_out:
            if st.button("Sair", key="logout_btn", help="Encerrar sessão"):
                logout()

        st.markdown("---")

        # ══════════════════════════════════════════════════════════════════════
        # CONFIGURAÇÃO RÁPIDA — sempre visível
        # ══════════════════════════════════════════════════════════════════════
        st.markdown("### 🤖 Provedor LLM")
        provider_names = list(AVAILABLE_PROVIDERS.keys())
        sel = st.selectbox(
            "Provider",
            provider_names,
            index=provider_names.index(st.session_state.selected_provider),
            key="provider_select",
        )
        st.session_state.selected_provider = sel
        st.session_state.provider_cfg = AVAILABLE_PROVIDERS[sel]
        st.code(st.session_state.provider_cfg["default_model"])
        render_api_key_gate(sel, st.session_state.provider_cfg)

        out_lang = st.selectbox(
            "Idioma de saída",
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
        with st.expander("⚙️ Configuração Avançada"):

            # ── Nomenclatura de arquivos ───────────────────────────────────────
            st.markdown("**📁 Arquivos exportados**")
            col_pref, col_suf = st.columns(2)
            with col_pref:
                pref = st.text_input(
                    "Prefixo (máx 11)",
                    value=st.session_state.prefix.rstrip("_"),
                    max_chars=11,
                )
            with col_suf:
                suf = st.text_input(
                    "Sufixo (máx 11)",
                    value=st.session_state.suffix,
                    max_chars=11,
                )
            st.session_state.prefix = (pref.strip() + "_") if pref.strip() else "P2D_"
            st.session_state.suffix = suf.strip() if suf.strip() else date.today().isoformat()

            st.markdown("---")

            # ── Agentes ───────────────────────────────────────────────────────
            st.markdown("**🤖 Agentes ativos**")
            st.session_state.run_quality = st.checkbox(
                "Inspetor de Qualidade", value=st.session_state.run_quality
            )
            st.session_state.run_bpmn = st.checkbox(
                "Arquiteto BPMN", value=st.session_state.run_bpmn
            )
            if st.session_state.run_bpmn:
                st.session_state.n_bpmn_runs = st.select_slider(
                    "Passes de Otimização", [1, 3, 5], value=st.session_state.n_bpmn_runs
                )
                if st.session_state.n_bpmn_runs > 1:
                    with st.expander("Pesos de Seleção"):
                        st.session_state.bpmn_weights = {
                            "granularity": st.slider("Granularidade", 0, 10, st.session_state.bpmn_weights.get("granularity", 5)),
                            "task_type":   st.slider("Tipo de Tarefa", 0, 10, st.session_state.bpmn_weights.get("task_type",   5)),
                            "gateways":    st.slider("Gateways",       0, 10, st.session_state.bpmn_weights.get("gateways",    5)),
                            "structural":  st.slider("Estrutural",     0, 10, st.session_state.bpmn_weights.get("structural",  5)),
                        }
                if st.session_state.n_bpmn_runs == 1:
                    st.session_state.use_langgraph = st.checkbox(
                        "🔄 Retry Adaptativo (LangGraph)",
                        value=st.session_state.use_langgraph,
                        help="Reexecuta o BPMN automaticamente se a pontuação ficar abaixo do limiar.",
                    )
                    if st.session_state.use_langgraph:
                        st.session_state.validation_threshold = st.slider(
                            "Limiar de Qualidade", 0.0, 10.0,
                            value=float(st.session_state.validation_threshold),
                            step=0.5,
                        )
                        st.session_state.max_bpmn_retries = st.selectbox(
                            "Máx. Retentativas", [1, 2, 3, 5],
                            index=[1, 2, 3, 5].index(st.session_state.max_bpmn_retries)
                            if st.session_state.max_bpmn_retries in [1, 2, 3, 5] else 2,
                        )
            st.session_state.run_minutes      = st.checkbox("Ata de Reunião",                   value=st.session_state.run_minutes)
            st.session_state.run_requirements = st.checkbox("Requisitos",                       value=st.session_state.run_requirements)
            st.session_state.run_sbvr         = st.checkbox("Vocabulário & Regras (SBVR)",      value=st.session_state.run_sbvr)
            st.session_state.run_bmm          = st.checkbox("Motivação do Negócio (BMM)",       value=st.session_state.run_bmm)
            st.session_state.run_synthesizer  = st.checkbox("Relatório Executivo",              value=st.session_state.run_synthesizer)

            st.markdown("---")

            # ── Modo desenvolvedor ─────────────────────────────────────────────
            st.caption("🔒 Chaves de API armazenadas apenas na sessão.")
            st.session_state.show_dev_tools = st.checkbox(
                "Modo Desenvolvedor", value=st.session_state.show_dev_tools
            )
            if st.session_state.show_dev_tools:
                st.session_state.show_raw_json = st.checkbox(
                    "Exibir JSON bruto", value=st.session_state.show_raw_json
                )

        # ══════════════════════════════════════════════════════════════════════
        # REEXECUÇÃO DE AGENTES — só aparece após o primeiro pipeline
        # ══════════════════════════════════════════════════════════════════════
        if "hub" in st.session_state:
            st.markdown("---")
            st.markdown("### 🔄 Reexecutar Agente")
            st.caption("Reprocessa um agente individualmente.")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔬 Qualidade",  key="rr_q"):
                    st.session_state.rerun_agent = "quality"
                if st.button("📐 BPMN",       key="rr_b"):
                    st.session_state.rerun_agent = "bpmn"
                if st.button("📋 Ata",        key="rr_m"):
                    st.session_state.rerun_agent = "minutes"
            with col2:
                if st.button("📝 Requisitos", key="rr_r"):
                    st.session_state.rerun_agent = "requirements"
                if st.button("📄 Relatório",  key="rr_s"):
                    st.session_state.rerun_agent = "synthesizer"
