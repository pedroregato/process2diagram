# pages/Settings.py
# ─────────────────────────────────────────────────────────────────────────────
# Configurações da Sessão — Process2Diagram
#
# Central de configuração: provedores LLM, chaves de API, embeddings, busca e
# preferências gerais. Tudo persiste em st.session_state durante a sessão.
#
# As páginas individuais (Pipeline, Assistente, BatchRunner…) leem automaticamente
# os valores aqui definidos — configure uma vez, use em todas as páginas.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st

from ui.auth_gate import apply_auth_gate
from modules.config import AVAILABLE_PROVIDERS
from modules.embeddings import EMBEDDING_PROVIDERS
from modules.supabase_client import supabase_configured, get_supabase_client

apply_auth_gate()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# ⚙️ Configurações da Sessão")
st.caption(
    "Configure provedores, chaves de API, modo de busca e preferências. "
    "Tudo persiste durante a sessão — configure uma vez e todas as páginas usarão."
)

# ── Helper: API key section with mask/clear pattern ───────────────────────────
def _render_api_key_section(
    *,
    section_title: str,
    state_key: str,
    label: str,
    placeholder: str,
    help_text: str,
    save_btn_key: str,
    clear_btn_key: str,
    input_key: str,
) -> None:
    """Renders a reusable API key input: show masked value + clear, or input + save."""
    stored: str = st.session_state.get(state_key, "")

    if stored:
        masked = stored[:6] + "••••••••" + stored[-4:] if len(stored) > 10 else "••••••••"
        col_info, col_clear = st.columns([4, 1])
        with col_info:
            st.success(f"🔑 Chave ativa: `{masked}`")
        with col_clear:
            if st.button("🗑 Limpar", key=clear_btn_key, use_container_width=True):
                st.session_state.pop(state_key, None)
                st.rerun()
    else:
        col_inp, col_save = st.columns([4, 1])
        with col_inp:
            entered = st.text_input(
                label,
                type="password",
                placeholder=placeholder,
                help=help_text,
                key=input_key,
                label_visibility="collapsed",
            )
        with col_save:
            if st.button("💾 Salvar", key=save_btn_key, type="primary", use_container_width=True):
                if entered and len(entered.strip()) > 10:
                    st.session_state[state_key] = entered.strip()
                    st.rerun()
                else:
                    st.error("Chave muito curta.")


# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_llm, tab_asst, tab_embed, tab_db, tab_pref = st.tabs([
    "🤖 LLM Principal",
    "💬 LLM Assistente",
    "🔮 Embeddings & Busca",
    "🗄️ Banco de Dados",
    "🌐 Preferências",
])

# ╔══════════════════════════════════════════════════════╗
# ║  TAB 1 — LLM Principal (Pipeline / Batch / Backfill)║
# ╚══════════════════════════════════════════════════════╝
with tab_llm:
    st.markdown(
        "Configuração do LLM utilizado pelo **Pipeline** (Processar Transcrição), "
        "**Batch Runner** e **BPMN Backfill**."
    )
    st.markdown("---")

    # Provider
    st.markdown("#### Provedor e Modelo")
    provider_names = list(AVAILABLE_PROVIDERS.keys())
    current_provider = st.session_state.get("selected_provider", "DeepSeek")
    selected = st.selectbox(
        "Provedor LLM",
        provider_names,
        index=provider_names.index(current_provider) if current_provider in provider_names else 0,
        key="settings_llm_provider",
    )
    st.session_state["selected_provider"] = selected
    st.session_state["provider_cfg"]       = AVAILABLE_PROVIDERS[selected]

    pcfg = AVAILABLE_PROVIDERS[selected]
    c1, c2, c3 = st.columns(3)
    c1.metric("Modelo padrão",       pcfg["default_model"])
    c2.metric("Modo JSON",           "✅ Sim" if pcfg.get("supports_json_mode") else "❌ Não")
    c3.metric("Prompt de sistema",   "✅ Sim" if pcfg.get("supports_system_prompt") else "❌ Não")
    if pcfg.get("cost_hint"):
        st.caption(f"💰 {pcfg['cost_hint']}")

    st.markdown("---")
    st.markdown(f"#### 🔑 API Key — {selected}")
    st.caption(pcfg.get("api_key_help", ""))

    # Reuse session_security key format so Pipeline sidebar reads the same value
    from modules.session_security import _session_key
    sk = _session_key(selected)
    _render_api_key_section(
        section_title=selected,
        state_key=sk,
        label=pcfg.get("api_key_label", "API Key"),
        placeholder=f"{pcfg.get('api_key_prefix', '')}...",
        help_text=pcfg.get("api_key_help", ""),
        save_btn_key=f"settings_save_llm_{selected}",
        clear_btn_key=f"settings_clear_llm_{selected}",
        input_key=f"settings_input_llm_{selected}",
    )

    # Show status for all providers
    st.markdown("---")
    st.markdown("#### Status de todas as chaves")
    rows = []
    for name in provider_names:
        stored = st.session_state.get(_session_key(name), "")
        rows.append({
            "Provedor": name,
            "Modelo":   AVAILABLE_PROVIDERS[name]["default_model"],
            "Chave":    "✅ Configurada" if stored else "❌ Não configurada",
        })
    import pandas as pd
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

# ╔══════════════════════════════════════════════════════╗
# ║  TAB 2 — LLM Assistente                             ║
# ╚══════════════════════════════════════════════════════╝
with tab_asst:
    st.markdown(
        "Configuração do LLM utilizado pelo **Assistente de Reuniões**. "
        "Pode ser o mesmo provedor do Pipeline ou um diferente."
    )
    st.markdown("---")

    st.markdown("#### Provedor e Modelo")
    asst_prov_names = list(AVAILABLE_PROVIDERS.keys())
    current_asst = st.session_state.get("asst_provider", "DeepSeek")
    sel_asst = st.selectbox(
        "Provedor LLM",
        asst_prov_names,
        index=asst_prov_names.index(current_asst) if current_asst in asst_prov_names else 0,
        key="settings_asst_provider",
    )
    st.session_state["asst_provider"] = sel_asst

    acfg = AVAILABLE_PROVIDERS[sel_asst]
    ca1, ca2 = st.columns(2)
    ca1.metric("Modelo padrão", acfg["default_model"])
    ca2.metric("Function Calling", "✅ Sim" if acfg.get("supports_json_mode") else "⚠️ Limitado")
    if acfg.get("cost_hint"):
        st.caption(f"💰 {acfg['cost_hint']}")

    st.markdown("---")
    st.markdown(f"#### 🔑 API Key — {sel_asst}")
    st.caption(acfg.get("api_key_help", ""))

    # asst_api_key is the key Assistente.py reads from its text_input widget
    _render_api_key_section(
        section_title=sel_asst,
        state_key="asst_api_key",
        label=acfg.get("api_key_label", "API Key"),
        placeholder=f"{acfg.get('api_key_prefix', '')}...",
        help_text=acfg.get("api_key_help", ""),
        save_btn_key="settings_save_asst_key",
        clear_btn_key="settings_clear_asst_key",
        input_key="settings_input_asst_key",
    )

    st.markdown("---")
    st.markdown("#### ⚙️ Comportamento do Assistente")

    use_tools = st.toggle(
        "🔧 Modo Tool-Use (recomendado)",
        value=st.session_state.get("asst_use_tools", True),
        key="settings_asst_tools",
        help=(
            "O LLM decide dinamicamente quais ferramentas chamar "
            "(participantes, decisões, requisitos, correção de texto…). "
            "Mais preciso. Requer suporte a function calling do provedor."
        ),
    )
    st.session_state["asst_use_tools"] = use_tools

    if use_tools:
        st.info(
            "✅ **12 ferramentas disponíveis:** participantes, decisões, ações, "
            "transcrições, requisitos, BPMN, SBVR e correção de texto (preview + aplicar).",
            icon=None,
        )
    else:
        st.info(
            "🔑 **Modo RAG Clássico:** busca por keyword ou semântica nas transcrições. "
            "Mais simples, não suporta correção de texto.",
            icon=None,
        )

# ╔══════════════════════════════════════════════════════╗
# ║  TAB 3 — Embeddings & Busca                         ║
# ╚══════════════════════════════════════════════════════╝
with tab_embed:
    st.markdown(
        "Configuração do provedor de embeddings para **busca semântica** no Assistente. "
        "A API do DeepSeek **não** possui endpoint de embeddings — use Google Gemini (gratuito) ou OpenAI."
    )
    st.markdown("---")

    st.markdown("#### Provedor de Embedding")
    emb_prov_names = list(EMBEDDING_PROVIDERS.keys())
    current_emb = st.session_state.get("asst_embed_provider", "Google Gemini")
    sel_emb = st.selectbox(
        "Provedor de Embedding",
        emb_prov_names,
        index=emb_prov_names.index(current_emb) if current_emb in emb_prov_names else 0,
        key="settings_emb_provider",
    )
    st.session_state["asst_embed_provider"] = sel_emb

    ecfg = EMBEDDING_PROVIDERS[sel_emb]
    st.metric("Modelo", ecfg.get("model", "—"))
    st.caption(ecfg.get("api_key_help", ""))

    st.markdown("---")
    st.markdown(f"#### 🔑 API Key — {sel_emb}")

    _render_api_key_section(
        section_title=sel_emb,
        state_key="asst_embed_key",
        label=ecfg.get("api_key_label", "API Key"),
        placeholder=f"{ecfg.get('api_key_prefix', '')}...",
        help_text=ecfg.get("api_key_help", ""),
        save_btn_key="settings_save_emb_key",
        clear_btn_key="settings_clear_emb_key",
        input_key="settings_input_emb_key",
    )

    st.markdown("---")
    st.markdown("#### 🔍 Modo de Busca Padrão")

    use_sem = st.toggle(
        "Usar busca semântica (pgvector)",
        value=st.session_state.get("asst_use_semantic", False),
        key="settings_use_semantic",
        help=(
            "Substitui a busca por palavras-chave por busca vetorial. "
            "Requer que os embeddings das transcrições tenham sido gerados "
            "e que a tabela transcript_chunks exista no Supabase."
        ),
    )
    st.session_state["asst_use_semantic"] = use_sem

    if use_sem:
        emb_key_set = bool(st.session_state.get("asst_embed_key", "").strip())
        if emb_key_set:
            st.success("✅ Busca semântica ativada e API key configurada.")
        else:
            st.warning("⚠️ Busca semântica ativada mas API key de embedding não configurada acima.")

        from modules.supabase_client import supabase_configured
        from core.project_store import transcript_chunks_table_exists
        if supabase_configured():
            chunks_ok = transcript_chunks_table_exists()
            if chunks_ok:
                st.success("✅ Tabela `transcript_chunks` encontrada no banco.")
            else:
                st.warning(
                    "⚠️ Tabela `transcript_chunks` não encontrada. "
                    "Execute `setup/supabase_schema_transcript_chunks.sql` para criá-la."
                )
    else:
        st.info("🔑 Modo Keyword ativo — sem necessidade de API key de embedding.")

# ╔══════════════════════════════════════════════════════╗
# ║  TAB 4 — Banco de Dados                             ║
# ╚══════════════════════════════════════════════════════╝
with tab_db:
    st.markdown(
        "Credenciais do Supabase são lidas de `st.secrets` (definidas no Streamlit Cloud ou "
        "em `.streamlit/secrets.toml` localmente). Não podem ser alteradas aqui."
    )
    st.markdown("---")

    if not supabase_configured():
        st.error(
            "❌ Supabase não configurado. "
            "Adicione `[supabase]` com `url` e `key` em Settings → Secrets no Streamlit Cloud."
        )
        st.code(
            "[supabase]\nurl = \"https://xxxx.supabase.co\"\nkey = \"eyJ...\"",
            language="toml",
        )
    else:
        db = get_supabase_client()
        if db:
            st.success("✅ Conexão com Supabase estabelecida.")

            # Quick stats
            try:
                n_proj = len(db.table("projects").select("id").execute().data or [])
                n_meet = len(db.table("meetings").select("id").execute().data or [])
                n_req  = len(db.table("requirements").select("id").execute().data or [])
                c1, c2, c3 = st.columns(3)
                c1.metric("Projetos",   n_proj)
                c2.metric("Reuniões",   n_meet)
                c3.metric("Requisitos", n_req)
            except Exception as e:
                st.warning(f"Erro ao consultar tabelas: {e}")

            # Tabelas opcionais
            st.markdown("#### Tabelas opcionais")
            optional_tables = {
                "bpmn_processes":    "Processos BPMN",
                "bpmn_versions":     "Versões BPMN",
                "sbvr_terms":        "Termos SBVR",
                "sbvr_rules":        "Regras SBVR",
                "transcript_chunks": "Chunks de Embedding (busca semântica)",
                "batch_log":         "Log do Batch Runner",
            }
            tbl_rows = []
            for tbl, desc in optional_tables.items():
                try:
                    db.table(tbl).select("id").limit(1).execute()
                    status = "✅ Existe"
                except Exception:
                    status = "❌ Não encontrada"
                tbl_rows.append({"Tabela": tbl, "Descrição": desc, "Status": status})
            import pandas as pd
            st.dataframe(pd.DataFrame(tbl_rows), use_container_width=True, hide_index=True)
        else:
            st.error("❌ Falha ao conectar ao Supabase.")

    st.markdown("---")
    st.markdown("#### 📊 Painel completo do banco")
    st.markdown(
        "Para ver totais de registros, integridade de dados, distribuição de requisitos "
        "e cobertura de embeddings, acesse a página **🗄️ Visão do Banco** no menu "
        "**Operações** na barra lateral esquerda."
    )
    st.page_link("pages/DatabaseOverview.py", label="Abrir Visão do Banco →", icon="🗄️")

# ╔══════════════════════════════════════════════════════╗
# ║  TAB 5 — Preferências Gerais                        ║
# ╚══════════════════════════════════════════════════════╝
with tab_pref:
    st.markdown("#### 🌐 Idioma de Saída")
    lang_options = ["Auto-detect", "Portuguese (BR)", "English"]
    current_lang = st.session_state.get("output_language", "Auto-detect")
    sel_lang = st.selectbox(
        "Idioma dos artefatos gerados",
        lang_options,
        index=lang_options.index(current_lang) if current_lang in lang_options else 0,
        key="settings_output_lang",
        help="Idioma das atas, requisitos, relatórios e diagramas gerados pelo pipeline.",
    )
    st.session_state["output_language"] = sel_lang

    st.markdown("---")
    st.markdown("#### 📄 Prefixo e Sufixo de Arquivos")
    st.caption("Usados nos nomes dos arquivos baixados (ex: `P2D_ata_2025-06-01.docx`).")
    from datetime import date as _date
    col_pref, col_suf = st.columns(2)
    with col_pref:
        pref_val = st.session_state.get("prefix", "P2D_").rstrip("_")
        pref = st.text_input("Prefixo (máx 11 chars)", value=pref_val, max_chars=11, key="settings_prefix")
        st.session_state["prefix"] = (pref.strip() + "_") if pref.strip() else "P2D_"
    with col_suf:
        suf_val = st.session_state.get("suffix", _date.today().isoformat())
        suf = st.text_input("Sufixo (máx 11 chars)", value=suf_val, max_chars=11, key="settings_suffix")
        st.session_state["suffix"] = suf.strip() if suf.strip() else _date.today().isoformat()
    st.caption(f"Exemplo: `{st.session_state['prefix']}ata_{st.session_state['suffix']}.docx`")

    st.markdown("---")
    st.markdown("#### 🤖 Agentes Padrão do Pipeline")
    st.caption("Define quais agentes são ativados por padrão ao abrir o Pipeline.")

    col_a, col_b = st.columns(2)
    with col_a:
        st.session_state["run_quality"]      = st.checkbox("Quality Inspector",  value=st.session_state.get("run_quality", True),      key="settings_rq")
        st.session_state["run_bpmn"]         = st.checkbox("BPMN Architect",     value=st.session_state.get("run_bpmn", True),          key="settings_rb")
        st.session_state["run_minutes"]      = st.checkbox("Meeting Minutes",    value=st.session_state.get("run_minutes", True),       key="settings_rm")
        st.session_state["run_requirements"] = st.checkbox("Requirements",       value=st.session_state.get("run_requirements", True),  key="settings_rr")
    with col_b:
        st.session_state["run_sbvr"]         = st.checkbox("SBVR (vocabulário)", value=st.session_state.get("run_sbvr", False),         key="settings_rs")
        st.session_state["run_bmm"]          = st.checkbox("BMM (motivação)",    value=st.session_state.get("run_bmm", False),          key="settings_rbm")
        st.session_state["run_synthesizer"]  = st.checkbox("Executive Report",   value=st.session_state.get("run_synthesizer", False),  key="settings_rsy")

    st.markdown("---")
    st.markdown("#### 🔄 Pipeline BPMN")
    n_runs = st.select_slider(
        "Optimization Passes",
        options=[1, 3, 5],
        value=st.session_state.get("n_bpmn_runs", 1),
        key="settings_n_bpmn",
        help="Número de rodadas do agente BPMN. Mais rodadas = melhor resultado, mais custo.",
    )
    st.session_state["n_bpmn_runs"] = n_runs

# ── Rodapé ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "💡 As configurações são mantidas enquanto a aba do navegador estiver aberta. "
    "Ao fechar ou recarregar a página, as chaves de API precisam ser inseridas novamente "
    "(por segurança, nunca são persistidas em disco)."
)
