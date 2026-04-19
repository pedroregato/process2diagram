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
    persist_key: str = "",   # config_key in tenant_config — set to auto-persist on save
) -> None:
    """Renders a reusable API key input: show masked value + clear, or input + save.

    When persist_key is provided and _tenant_id is in session_state, the key is
    also saved/deleted in the tenant_config table so it survives browser refreshes.
    """
    stored: str = st.session_state.get(state_key, "")

    if stored:
        masked = stored[:6] + "••••••••" + stored[-4:] if len(stored) > 10 else "••••••••"
        col_info, col_clear = st.columns([4, 1])
        with col_info:
            st.success(f"🔑 Chave ativa: `{masked}`")
        with col_clear:
            if st.button("🗑 Limpar", key=clear_btn_key, use_container_width=True):
                st.session_state.pop(state_key, None)
                if persist_key:
                    tid = st.session_state.get("_tenant_id")
                    if tid:
                        from modules.tenant_config import delete_config
                        delete_config(tid, persist_key)
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
                    value = entered.strip()
                    st.session_state[state_key] = value
                    if persist_key:
                        tid = st.session_state.get("_tenant_id")
                        if tid:
                            from modules.tenant_config import save_config
                            save_config(tid, persist_key, value)
                    st.rerun()
                else:
                    st.error("Chave muito curta.")


# ══════════════════════════════════════════════════════════════════════════════
# TABS
# ══════════════════════════════════════════════════════════════════════════════
tab_llm, tab_asst, tab_embed, tab_db, tab_pref, tab_domain = st.tabs([
    "🤖 LLM Principal",
    "💬 LLM Assistente",
    "🔮 Embeddings & Busca",
    "🗄️ Banco de Dados",
    "🌐 Preferências",
    "🔑 Domínio",
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

    # ── Tool catalog ──────────────────────────────────────────────────────────
    st.markdown("---")
    try:
        from core.assistant_tools import get_tool_catalog
        _catalog = get_tool_catalog()
        _cat_groups: dict = {}
        for _t in _catalog:
            _cat_groups.setdefault(_t["category"], []).append(_t)

        _cat_labels = {
            "consulta": ("🔍 Consulta", "#1A4B8C", "Somente leitura — busca e exibe dados do projeto"),
            "escrita":  ("✏️ Escrita",  "#7C2D12", "Modifica dados — requer confirmação do usuário"),
            "geração":  ("🤖 Geração",  "#166534", "Chama o LLM para gerar conteúdo e salva no banco"),
            "admin":    ("🔒 Admin",    "#374151", "Requer perfil administrador"),
        }

        with st.expander(f"📖 Catálogo de Ferramentas  ·  {len(_catalog)} disponíveis", expanded=False):
            st.caption(
                "Ferramentas que o Assistente pode chamar automaticamente durante uma conversa. "
                "O LLM decide qual(is) usar com base na pergunta."
            )
            for _cat_key in ("consulta", "escrita", "geração", "admin"):
                _tools_in_cat = _cat_groups.get(_cat_key, [])
                if not _tools_in_cat:
                    continue
                _cat_label, _cat_color, _cat_desc = _cat_labels[_cat_key]
                st.markdown(
                    f'<span style="display:inline-block;background:{_cat_color};color:#fff;'
                    f'border-radius:6px;padding:2px 10px;font-size:0.78rem;font-weight:600;'
                    f'margin-bottom:4px">{_cat_label} · {len(_tools_in_cat)} ferramentas</span>  '
                    f'<span style="color:#64748b;font-size:0.78rem">{_cat_desc}</span>',
                    unsafe_allow_html=True,
                )
                for _t in _tools_in_cat:
                    _params_str = (
                        f"`({'`, `'.join(_t['params'])})`" if _t["params"] else "*(sem parâmetros)*"
                    )
                    _req_str = (
                        f"  · obrigatórios: `{'`, `'.join(_t['required'])}`" if _t["required"] else ""
                    )
                    st.markdown(
                        f"**`{_t['name']}`**{_req_str}  \n"
                        f"{_t['description'][:160]}{'…' if len(_t['description']) > 160 else ''}  \n"
                        f"<span style='color:#94a3b8;font-size:0.75rem'>parâmetros: {_params_str}</span>",
                        unsafe_allow_html=True,
                    )
                st.markdown("")
    except Exception as _cat_err:
        st.caption(f"Catálogo de ferramentas indisponível: {_cat_err}")

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
        persist_key="embedding_key",
    )

    # ── Botão de teste do modelo de embedding ─────────────────────────────────
    st.markdown("---")
    st.markdown("#### 🧪 Testar Modelo de Embedding")

    # Feedback persistido (sobrevive ao rerun)
    if "_emb_test_result" in st.session_state:
        lvl, msg = st.session_state.pop("_emb_test_result")
        if lvl == "ok":
            st.success(msg)
        else:
            st.error(msg)

    emb_key_for_test = st.session_state.get("asst_embed_key", "").strip()
    if not emb_key_for_test:
        st.caption("Configure e salve a API key acima para habilitar o teste.")
    else:
        if st.button("🧪 Testar modelo agora", key="settings_test_emb_model"):
            with st.spinner(f"Testando {sel_emb} — {ecfg.get('model', '?')}…"):
                try:
                    import time as _time
                    t0 = _time.perf_counter()
                    from modules.embeddings import embed_text, EMBEDDING_DIM
                    vec = embed_text(
                        "Teste de embedding Process2Diagram — verificação de modelo.",
                        emb_key_for_test,
                        sel_emb,
                    )
                    elapsed = _time.perf_counter() - t0
                    if len(vec) == EMBEDDING_DIM:
                        st.session_state["_emb_test_result"] = (
                            "ok",
                            f"✅ **{sel_emb}** — modelo `{ecfg.get('model','?')}` funcionando. "
                            f"{len(vec)} dimensões · {elapsed:.2f}s",
                        )
                    else:
                        st.session_state["_emb_test_result"] = (
                            "err",
                            f"❌ Dimensão inesperada: {len(vec)} (esperado {EMBEDDING_DIM}). "
                            f"Verifique o modelo configurado.",
                        )
                except Exception as exc:
                    st.session_state["_emb_test_result"] = (
                        "err",
                        f"❌ **Falha no teste** ({sel_emb}): {str(exc)[:400]}",
                    )
            st.rerun()

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

    # ── Persistência do provedor e do toggle ──────────────────────────────────
    st.markdown("---")
    if "_settings_emb_saved" in st.session_state:
        st.success(st.session_state.pop("_settings_emb_saved"))

    tid = st.session_state.get("_tenant_id")
    if tid:
        if st.button("💾 Salvar configurações de embedding", key="settings_save_emb_prefs", type="primary"):
            from modules.tenant_config import save_config, PREFS_MAP
            ok = 0
            for k in ("asst_embed_provider", "asst_use_semantic"):
                v = st.session_state.get(k)
                if v is not None:
                    cfg_key, _ = PREFS_MAP[k]
                    if save_config(tid, cfg_key, str(v)):
                        ok += 1
            st.session_state["_settings_emb_saved"] = (
                f"✅ Configurações de embedding salvas ({ok}/2 itens)."
            )
            st.rerun()
    else:
        st.caption("ℹ️ Faça login com domínio para persistir estas configurações entre sessões.")

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

    # ── Projetos — gestão de sigla ─────────────────────────────────────────
    if db:
        st.markdown("#### 📁 Projetos")
        st.caption("Visualize e edite a sigla dos projetos cadastrados.")

        try:
            proj_rows = db.table("projects").select("*").order("name").execute().data or []
        except Exception as e:
            proj_rows = []
            st.warning(f"Erro ao carregar projetos: {e}")

        if not proj_rows:
            st.info("Nenhum projeto cadastrado.")
            # Show migration SQL if sigla column is likely missing
            with st.expander("🔧 Adicionar coluna `sigla` ao Supabase", expanded=False):
                st.markdown(
                    "Execute este SQL no **Supabase → SQL Editor** para adicionar a coluna:"
                )
                st.code(
                    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS sigla TEXT DEFAULT '';",
                    language="sql",
                )
        else:
            # Check if sigla column exists in response
            _has_sigla = "sigla" in (proj_rows[0] if proj_rows else {})
            if not _has_sigla:
                st.warning(
                    "⚠️ A coluna `sigla` não existe na tabela `projects`. "
                    "Execute o SQL abaixo no Supabase para criá-la:"
                )
                st.code(
                    "ALTER TABLE projects ADD COLUMN IF NOT EXISTS sigla TEXT DEFAULT '';",
                    language="sql",
                )

            for p in proj_rows:
                pid   = p["id"]
                pname = p.get("name", "—")
                psig  = p.get("sigla", "") or ""
                with st.expander(f"📁 {pname}", expanded=False):
                    col_a, col_b = st.columns([3, 1])
                    new_sigla = col_a.text_input(
                        "Sigla",
                        value=psig,
                        max_chars=20,
                        key=f"sigla_{pid}",
                        help="Abreviação do projeto (ex: SDEA, FGV, P2D)",
                    )
                    new_name = col_a.text_input(
                        "Nome",
                        value=pname,
                        key=f"pname_{pid}",
                    )
                    new_desc = col_a.text_area(
                        "Descrição",
                        value=p.get("description", "") or "",
                        key=f"pdesc_{pid}",
                        height=80,
                    )
                    with col_b:
                        st.write("")
                        st.write("")
                        if st.button("💾 Salvar", key=f"save_proj_{pid}", use_container_width=True):
                            patch: dict = {"name": new_name.strip(), "description": new_desc.strip()}
                            if _has_sigla:
                                patch["sigla"] = new_sigla.strip().upper()
                            try:
                                db.table("projects").update(patch).eq("id", pid).execute()
                                st.success("✅ Projeto atualizado.")
                                st.rerun()
                            except Exception as upd_err:
                                st.error(f"Erro ao salvar: {upd_err}")

    st.markdown("---")

    # ── Migração de schema ─────────────────────────────────────────────────
    if db:
        st.markdown("#### 🔧 Migração de Schema")
        st.caption(
            "Se alguma tabela estiver com colunas ausentes, execute o SQL correspondente "
            "no **Supabase → SQL Editor**."
        )
        _migration_sql = """\
-- Adiciona coluna sigla em projects (caso não exista)
ALTER TABLE projects ADD COLUMN IF NOT EXISTS sigla TEXT DEFAULT '';

-- Torna meeting_id opcional em sbvr_terms e sbvr_rules
-- (permite termos/regras adicionados pelo Assistente sem reunião de origem)
ALTER TABLE sbvr_terms ALTER COLUMN meeting_id DROP NOT NULL;
ALTER TABLE sbvr_rules ALTER COLUMN meeting_id DROP NOT NULL;

-- Adiciona coluna source para identificar a origem do termo/regra
ALTER TABLE sbvr_terms ADD COLUMN IF NOT EXISTS source TEXT DEFAULT NULL;
ALTER TABLE sbvr_rules ADD COLUMN IF NOT EXISTS source TEXT DEFAULT NULL;
"""
        st.code(_migration_sql, language="sql")

        st.markdown("---")
        st.markdown("#### 🏷️ Fase 3b — ROI-TR v2: Tipo de Reunião")
        st.info(
            "**Como aplicar:**\n\n"
            "1. Acesse **supabase.com → seu projeto → SQL Editor**\n"
            "2. Clique em **New query**, cole o SQL abaixo e clique em **Run**\n\n"
            "Adiciona a coluna `meeting_type` na tabela `meetings`. "
            "Necessária para classificação de tipo e fórmula DC ponderada."
        )
        _meeting_type_sql = """\
-- Adiciona coluna de tipo de reunião (classificada por LLM ou heurística)
ALTER TABLE meetings ADD COLUMN IF NOT EXISTS meeting_type TEXT DEFAULT NULL;
"""
        st.code(_meeting_type_sql, language="sql")

        st.markdown("---")
        st.markdown("#### 📊 Fase 3 — ROI-TR: Qualidade de Reuniões")
        st.info(
            "**Como aplicar:**\n\n"
            "1. Copie o SQL abaixo (ou baixe o arquivo)\n"
            "2. Acesse **supabase.com → seu projeto → SQL Editor**\n"
            "3. Clique em **New query**, cole o SQL e clique em **Run**\n\n"
            "Isso cria a tabela `meeting_quality_scores` (histórico ROI-TR) "
            "e a função `find_recurring_topics` (análise cross-meeting via embeddings)."
        )
        # Load from file so it's always in sync with the actual schema
        _roi_sql_path = Path(__file__).parent.parent / "setup" / "supabase_schema_meeting_quality.sql"
        try:
            _roi_sql_content = _roi_sql_path.read_text(encoding="utf-8")
        except Exception:
            _roi_sql_content = "-- Arquivo não encontrado: setup/supabase_schema_meeting_quality.sql"
        st.download_button(
            "⬇️ Baixar supabase_schema_meeting_quality.sql",
            data=_roi_sql_content,
            file_name="supabase_schema_meeting_quality.sql",
            mime="text/plain",
            use_container_width=False,
        )
        st.caption(
            "Execute no Supabase → SQL Editor para habilitar persistência de scores "
            "e análise cross-meeting semântica (tópicos recorrentes via embeddings)."
        )
        _roi_sql = """\
-- Tabela de histórico de indicadores ROI-TR
CREATE TABLE IF NOT EXISTS meeting_quality_scores (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID        NOT NULL REFERENCES projects(id)  ON DELETE CASCADE,
    meeting_id          UUID        NOT NULL REFERENCES meetings(id)  ON DELETE CASCADE,
    meeting_number      INTEGER     NOT NULL,
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cost_per_hour       NUMERIC     DEFAULT 150,
    n_participants      INTEGER,
    duration_min        NUMERIC,
    cost_estimate       NUMERIC,
    n_decisions         INTEGER,
    n_actions_total     INTEGER,
    n_actions_complete  INTEGER,
    n_requirements      INTEGER,
    cycle_signals       INTEGER,
    trc                 NUMERIC,
    dc_score            NUMERIC,
    roi_tr              NUMERIC
);
CREATE INDEX IF NOT EXISTS idx_mqs_project
    ON meeting_quality_scores (project_id, meeting_number, computed_at DESC);
ALTER TABLE meeting_quality_scores DISABLE ROW LEVEL SECURITY;

-- Função para análise cross-meeting (requer pgvector + transcript_chunks)
CREATE OR REPLACE FUNCTION find_recurring_topics(
    p_project_id UUID, p_threshold FLOAT DEFAULT 0.87, p_max_results INT DEFAULT 30
)
RETURNS TABLE (meeting_id_a UUID, meeting_id_b UUID, chunk_text_a TEXT, chunk_text_b TEXT, similarity FLOAT)
LANGUAGE sql STABLE AS $$
    SELECT a.meeting_id, b.meeting_id, a.chunk_text, b.chunk_text,
           (1 - (a.embedding <=> b.embedding))::FLOAT
    FROM transcript_chunks a
    JOIN transcript_chunks b ON a.project_id = b.project_id AND a.meeting_id < b.meeting_id
    WHERE a.project_id = p_project_id
      AND (1 - (a.embedding <=> b.embedding)) > p_threshold
    ORDER BY (1 - (a.embedding <=> b.embedding)) DESC LIMIT p_max_results;
$$;
"""
        st.code(_roi_sql, language="sql")

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

# ╔══════════════════════════════════════════════════════╗
# ║  TAB 6 — API Keys do Domínio (multi-tenant)         ║
# ╚══════════════════════════════════════════════════════╝
with tab_domain:
    tenant_id   = st.session_state.get("_tenant_id")
    role        = st.session_state.get("_role", "user")
    domain_name = st.session_state.get("_tenant_name", st.session_state.get("_domain", ""))
    user_nome   = st.session_state.get("_usuario_nome", "")

    if not tenant_id:
        st.info(
            "Esta seção está disponível apenas para usuários autenticados via **domínio**.\n\n"
            "Faça login informando o campo **Domínio** para acessar as configurações compartilhadas."
        )
    else:
        from modules.tenant_config import (
            load_all_config, save_config, delete_config,
            mask_key, PROVIDER_KEY_MAP, EXTRA_KEY_MAP,
        )
        from modules.session_security import _session_key

        # ── Cabeçalho ─────────────────────────────────────────────────────────
        c_info, c_role = st.columns([4, 1])
        c_info.markdown(f"**Domínio:** {domain_name} &nbsp;&nbsp; **Usuário:** {user_nome}")
        c_role.markdown(
            f"{'🟢 `admin`' if role == 'admin' else '🔵 `user`'}",
            unsafe_allow_html=False,
        )
        st.markdown(
            "Keys salvas aqui são **carregadas automaticamente** para todos os usuários "
            "do domínio ao fazer login — nenhuma configuração manual necessária."
        )
        st.markdown("---")

        # Mensagem de sucesso persistida (sobrevive ao st.rerun())
        if "_domain_save_ok" in st.session_state:
            st.success(f"✅ {st.session_state.pop('_domain_save_ok')}")

        # Carrega config atual do banco (uma vez por renderização)
        current_cfg = load_all_config(tenant_id)

        # ── Perfil user: sem acesso ────────────────────────────────────────────
        if role == "user":
            st.info(
                "🔒 Acesso restrito. "
                "Configurações do domínio são gerenciadas pelo administrador."
            )

        # ── Perfil master: redireciona para MasterAdmin ────────────────────────
        elif role == "master":
            from modules.tenant_config import PREFS_MAP, PREFS_LABELS
            st.info(
                "🛡️ Você tem perfil **master**. "
                "Gerencie domínios, usuários e configurações de todos os tenants na página dedicada."
            )
            st.page_link("pages/MasterAdmin.py", label="Abrir Master Admin →", icon="🛡️")
            st.markdown("---")
            st.markdown("#### Configurações do seu domínio (leitura)")
            all_keys = {**PROVIDER_KEY_MAP, **{"Embedding": "embedding_key", "Assistente": "assistant_key"}}
            for label, key_name in all_keys.items():
                val = current_cfg.get(key_name, "")
                status = f"`{mask_key(val)}`" if val else "❌ Não configurada"
                st.markdown(f"**{label}:** {status}")

        # ── Modo admin ────────────────────────────────────────────────────────
        elif role == "admin":
            from modules.tenant_config import save_all_prefs, PREFS_MAP, PREFS_LABELS
            st.markdown("#### 🤖 Provedores LLM")

            for provider, key_name in PROVIDER_KEY_MAP.items():
                pcfg    = AVAILABLE_PROVIDERS.get(provider, {})
                cur_val = current_cfg.get(key_name, "")
                icon    = "✅" if cur_val else "⬜"

                with st.expander(f"{icon} {provider}", expanded=not bool(cur_val)):
                    if cur_val:
                        st.success(f"Chave ativa: `{mask_key(cur_val)}`")

                    col_inp, col_save, col_del = st.columns([5, 1, 1])
                    new_val = col_inp.text_input(
                        provider,
                        type="password",
                        placeholder=(
                            f"{pcfg.get('api_key_prefix', '')}..."
                            + (" (vazio = manter atual)" if cur_val else "")
                        ),
                        key=f"dom_inp_{key_name}",
                        label_visibility="collapsed",
                    )
                    with col_save:
                        if st.button("💾", key=f"dom_save_{key_name}",
                                     use_container_width=True, type="primary",
                                     help="Salvar no domínio"):
                            v = new_val.strip()
                            if not v:
                                st.warning("Digite a chave antes de salvar.")
                            elif len(v) < 10:
                                st.error("Chave muito curta.")
                            elif save_config(tenant_id, key_name, v):
                                st.session_state[_session_key(provider)] = v
                                st.session_state["_domain_save_ok"] = f"✅ {provider} salva no domínio."
                                st.rerun()
                            else:
                                st.error("Erro ao salvar no banco.")
                    with col_del:
                        if cur_val and st.button("🗑", key=f"dom_del_{key_name}",
                                                  use_container_width=True,
                                                  help="Remover do domínio"):
                            if delete_config(tenant_id, key_name):
                                st.session_state.pop(_session_key(provider), None)
                                st.session_state["_domain_save_ok"] = f"🗑 {provider} removida do domínio."
                                st.rerun()

            st.markdown("---")
            st.markdown("#### 🔮 Embedding & Assistente")

            _extra_labels = {
                "embedding_key": ("Google Gemini / OpenAI Embedding", "asst_embed_key", "AIza..."),
                "assistant_key": ("LLM do Assistente (asst_api_key)", "asst_api_key", "sk-..."),
            }
            for cfg_key, (label, state_key, ph) in _extra_labels.items():
                cur_val = current_cfg.get(cfg_key, "")
                icon    = "✅" if cur_val else "⬜"
                with st.expander(f"{icon} {label}", expanded=not bool(cur_val)):
                    if cur_val:
                        st.success(f"Chave ativa: `{mask_key(cur_val)}`")
                    col_i, col_s, col_d = st.columns([5, 1, 1])
                    nv = col_i.text_input(
                        label, type="password",
                        placeholder=ph + (" (vazio = manter)" if cur_val else ""),
                        key=f"dom_inp_{cfg_key}", label_visibility="collapsed",
                    )
                    with col_s:
                        if st.button("💾", key=f"dom_save_{cfg_key}",
                                     use_container_width=True, type="primary",
                                     help="Salvar no domínio"):
                            v = nv.strip()
                            if not v:
                                st.warning("Digite a chave antes de salvar.")
                            elif len(v) < 10:
                                st.error("Chave muito curta.")
                            elif save_config(tenant_id, cfg_key, v):
                                st.session_state[state_key] = v
                                st.session_state["_domain_save_ok"] = f"✅ {label} salva no domínio."
                                st.rerun()
                            else:
                                st.error("Erro ao salvar no banco.")
                    with col_d:
                        if cur_val and st.button("🗑", key=f"dom_del_{cfg_key}",
                                                  use_container_width=True,
                                                  help="Remover do domínio"):
                            if delete_config(tenant_id, cfg_key):
                                st.session_state.pop(state_key, None)
                                st.session_state["_domain_save_ok"] = f"🗑 {label} removida do domínio."
                                st.rerun()

            # ── Preferências do domínio ───────────────────────────────────────
            st.markdown("---")
            st.markdown("#### ⚙️ Preferências do Domínio")
            st.markdown(
                "Configure as preferências nos outros tabs "
                "(**LLM Principal**, **LLM Assistente**, **Embeddings & Busca**, **Preferências**) "
                "e clique no botão abaixo para persistir o estado atual para todos do domínio."
            )

            # Prévia: o que será salvo
            with st.expander("📋 Prévia — o que será salvo", expanded=False):
                import pandas as pd
                preview_rows = []
                for state_key, (config_key, _) in PREFS_MAP.items():
                    val = st.session_state.get(state_key)
                    saved_val = current_cfg.get(config_key, "")
                    lbl = PREFS_LABELS.get(state_key, state_key)
                    preview_rows.append({
                        "Preferência": lbl,
                        "Valor atual (sessão)": str(val) if val is not None else "—",
                        "Salvo no domínio": str(saved_val) if saved_val else "—",
                    })
                st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

            if st.button(
                "💾 Salvar preferências atuais no domínio",
                key="dom_save_all_prefs",
                type="primary",
                use_container_width=True,
            ):
                saved, failed = save_all_prefs(tenant_id)
                if failed == 0:
                    st.session_state["_domain_save_ok"] = (
                        f"{saved} preferências salvas no domínio {domain_name}. "
                        "Serão carregadas automaticamente no próximo login."
                    )
                else:
                    st.session_state["_domain_save_ok"] = (
                        f"{saved} preferências salvas, {failed} falharam."
                    )
                st.rerun()

            st.markdown("---")
            st.caption(
                "⚠️ Keys salvas no domínio ficam em texto claro no Supabase. "
                "Para produção pública, habilite a criptografia AES-256 "
                "(ver `docs/auth_evolution_roadmap.html` — Segurança 1)."
            )

# ── Rodapé ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "💡 As configurações são mantidas enquanto a aba do navegador estiver aberta. "
    "Ao fechar ou recarregar a página, as chaves de API precisam ser inseridas novamente "
    "(por segurança, nunca são persistidas em disco). "
    "Usuários autenticados via domínio têm as chaves carregadas automaticamente no login."
)
