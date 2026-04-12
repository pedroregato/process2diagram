# pages/Assistente.py
# Assistente conversacional RAG sobre reuniões, requisitos, processos e SBVR.
# Suporta busca por keyword (padrão) e busca semântica via pgvector (opcional).

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st

from ui.auth_gate import apply_auth_gate
from ui.assistant_diagram import render_assistant_diagram
from modules.supabase_client import supabase_configured
from modules.config import AVAILABLE_PROVIDERS
from modules.embeddings import EMBEDDING_PROVIDERS, list_gemini_embedding_models
from core.project_store import (
    list_projects,
    retrieve_context_for_question,
    retrieve_context_semantic,
    format_context,
    transcript_chunks_table_exists,
    save_transcript_embeddings,
    get_embedding_coverage,
)
from agents.agent_assistant import AgentAssistant

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Assistente — Process2Diagram",
    page_icon="💬",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_auth_gate()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 💬 Assistente")

    # ── Project selector ──────────────────────────────────────────────────────
    st.markdown("#### 📁 Projeto")
    projects = list_projects()
    if projects:
        proj_names = [p["name"] for p in projects]
        proj_map = {p["name"]: p for p in projects}
        selected_proj_name = st.selectbox(
            "Selecione o projeto",
            proj_names,
            key="asst_proj_sel",
        )
        selected_project = proj_map[selected_proj_name]
        project_id: str | None = selected_project["id"]
        project_name: str = selected_project["name"]
    else:
        st.info("Nenhum projeto disponível.")
        project_id = None
        project_name = ""

    st.markdown("---")

    # ── LLM provider + API key ────────────────────────────────────────────────
    st.markdown("#### ⚙️ Configuração LLM")
    selected_provider = st.selectbox(
        "Provedor LLM",
        list(AVAILABLE_PROVIDERS.keys()),
        key="asst_provider",
    )
    provider_cfg = AVAILABLE_PROVIDERS[selected_provider]
    api_key = st.text_input(
        provider_cfg.get("api_key_label", "API Key"),
        type="password",
        key="asst_api_key",
        help=provider_cfg.get("api_key_help", ""),
    )

    st.markdown("---")

    # ── Busca semântica ───────────────────────────────────────────────────────
    st.markdown("#### 🔍 Busca Semântica (pgvector)")

    # Detecta se a tabela existe
    _chunks_table_ok = supabase_configured() and transcript_chunks_table_exists()

    if not _chunks_table_ok and supabase_configured():
        st.caption(
            "⚠️ Tabela `transcript_chunks` não encontrada. "
            "Execute `setup/supabase_schema_transcript_chunks.sql` para habilitar a busca semântica."
        )

    use_semantic = st.checkbox(
        "Usar busca semântica",
        value=False,
        key="asst_use_semantic",
        disabled=not _chunks_table_ok,
        help="Substitui a busca por palavras-chave por busca vetorial (pgvector). "
             "Requer que os embeddings das transcrições tenham sido gerados.",
    )

    if _chunks_table_ok and project_id:
        # Cobertura de embeddings
        coverage = get_embedding_coverage(project_id)
        total = coverage.get("total_meetings", 0)
        indexed = coverage.get("indexed_meetings", 0)
        n_chunks = coverage.get("total_chunks", 0)
        if total > 0:
            pct = int(100 * indexed / total)
            st.caption(
                f"📊 Cobertura: **{indexed}/{total}** reuniões indexadas "
                f"({pct}%) · {n_chunks:,} chunks"
            )
        else:
            st.caption("📊 Nenhuma reunião indexada ainda.")

        # Seção de geração de embeddings
        with st.expander("⚡ Gerar Embeddings", expanded=(indexed == 0)):
            st.caption(
                "Gera embeddings das transcrições para habilitar a busca semântica. "
                "Execute uma vez por projeto (ou novamente quando adicionar reuniões)."
            )
            st.info(
                "💡 A API pública do DeepSeek não possui endpoint de embeddings. "
                "Use **Google Gemini** (tier gratuito) ou **OpenAI**.",
                icon=None,
            )
            embed_provider = st.selectbox(
                "Provedor de Embedding",
                list(EMBEDDING_PROVIDERS.keys()),
                key="asst_embed_provider",
                help="Google Gemini text-embedding-004 (gratuito) ou OpenAI text-embedding-3-small (768 dims)",
            )
            embed_cfg = EMBEDDING_PROVIDERS[embed_provider]
            embed_api_key = st.text_input(
                embed_cfg["api_key_label"],
                type="password",
                key="asst_embed_key",
                help=embed_cfg["api_key_help"],
            )
            col_btn, col_diag = st.columns([2, 1])
            with col_btn:
                if st.button("⚡ Gerar Embeddings", key="asst_gen_embeddings", type="secondary", use_container_width=True):
                    if not embed_api_key:
                        st.warning("Insira a API key do provedor de embedding.")
                    else:
                        st.session_state["_trigger_embed"] = {
                            "provider": embed_provider,
                            "api_key":  embed_api_key,
                            "project_id": project_id,
                        }
            with col_diag:
                if st.button("🔍 Testar chave", key="asst_diag_models", use_container_width=True,
                             help="Lista os modelos de embedding disponíveis para esta chave"):
                    if not embed_api_key:
                        st.warning("Insira a API key antes de testar.")
                    elif embed_provider == "Google Gemini":
                        with st.spinner("Consultando modelos disponíveis..."):
                            try:
                                models = list_gemini_embedding_models(embed_api_key)
                                if models:
                                    st.success(f"✅ {len(models)} modelo(s) de embedding disponíveis:")
                                    for m in models:
                                        st.code(m["name"])
                                else:
                                    st.error(
                                        "❌ Nenhum modelo de embedding encontrado para esta chave. "
                                        "Verifique se a 'Generative Language API' está habilitada em "
                                        "console.cloud.google.com para o projeto desta chave."
                                    )
                            except Exception as exc:
                                st.error(f"❌ Erro ao consultar modelos: {exc}")
                    else:
                        st.info("Diagnóstico disponível apenas para Google Gemini.")

    if use_semantic:
        embed_provider_sel = st.session_state.get("asst_embed_provider", list(EMBEDDING_PROVIDERS.keys())[0])
        embed_key_sel = st.session_state.get("asst_embed_key", "")
        st.caption(f"Provedor ativo: **{embed_provider_sel}**")
        if not embed_key_sel:
            st.warning("Insira a API key de embedding acima para a busca semântica funcionar.")

    st.markdown("---")

    # ── Modo ferramentas (tool-use) ───────────────────────────────────────────
    st.markdown("#### 🔧 Modo Ferramentas")
    use_tools = st.checkbox(
        "Ativar tool-use",
        value=True,
        key="asst_use_tools",
        help=(
            "O LLM decide dinamicamente quais ferramentas chamar para responder "
            "(participantes, decisões, requisitos, transcrições...). "
            "Mais preciso para perguntas estruturadas. "
            "Requer suporte a function calling do provedor selecionado."
        ),
    )
    if use_tools:
        st.caption(
            "🔟 ferramentas disponíveis: participantes, decisões, ações, "
            "busca em transcrições, requisitos, BPMN, SBVR…"
        )

    st.markdown("---")

    # ── Clear conversation ────────────────────────────────────────────────────
    if st.button("🗑️ Limpar conversa", key="asst_clear"):
        st.session_state["assistant_history"] = []
        st.rerun()

# ── Main area ─────────────────────────────────────────────────────────────────
st.markdown("# 💬 Assistente de Reuniões")
st.caption(
    "Faça perguntas sobre transcrições, requisitos, processos BPMN e vocabulário SBVR "
    "armazenados no projeto selecionado. Também responde dúvidas sobre como usar o Process2Diagram."
)

with st.expander("🏗️ Arquitetura do Assistente — Como o RAG funciona", expanded=False):
    render_assistant_diagram(height=660)

# ── Guard: Supabase + project + API key ───────────────────────────────────────
if not supabase_configured():
    st.warning(
        "⚙️ Supabase não configurado. Adicione as credenciais em Settings → Secrets."
    )
    st.stop()

if not project_id:
    st.warning("👈 Selecione um projeto na sidebar para começar.")
    st.stop()

# ── Trigger: geração de embeddings (antes do guard de api_key LLM) ──────────
# Processado aqui para não depender da chave LLM — usa a chave de embedding.
if "_trigger_embed" in st.session_state:
    trigger = st.session_state.pop("_trigger_embed")
    if trigger["project_id"] == project_id:
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if db:
            with st.spinner("⚡ Gerando embeddings das transcrições..."):
                try:
                    meeting_rows_raw = db.table("meetings") \
                        .select("id, title, meeting_number, transcript_clean, transcript_raw") \
                        .eq("project_id", project_id) \
                        .execute().data or []
                except Exception:
                    meeting_rows_raw = []

            total_gen = 0
            errors = []
            prog = st.progress(0.0)
            n_total = len(meeting_rows_raw)

            first_error_msg: str | None = None
            for i, m in enumerate(meeting_rows_raw):
                transcript = m.get("transcript_clean") or m.get("transcript_raw") or ""
                title = m.get("title") or f"Reunião {m.get('meeting_number','?')}"
                if transcript.strip():
                    try:
                        n_saved = save_transcript_embeddings(
                            meeting_id=m["id"],
                            project_id=project_id,
                            transcript=transcript,
                            api_key=trigger["api_key"],
                            provider=trigger["provider"],
                        )
                        total_gen += n_saved
                    except Exception as exc:
                        errors.append(title)
                        if first_error_msg is None:
                            first_error_msg = str(exc)
                prog.progress((i + 1) / n_total if n_total else 1.0)

            prog.empty()
            if errors:
                detail = f"\n\n**Erro:** `{first_error_msg}`" if first_error_msg else ""
                # Persiste o erro no session_state — rerun apagaria o st.error imediatamente
                st.session_state["_embed_error"] = (
                    f"❌ Falha ao gerar embeddings para: {', '.join(errors)}.{detail}"
                )
            else:
                st.session_state["_embed_success"] = (
                    f"✅ {total_gen} chunks indexados em {n_total} reuniões."
                )
            st.rerun()

# ── Feedback de geração de embeddings (persiste entre reruns) ────────────────
if "_embed_error" in st.session_state:
    st.error(st.session_state.pop("_embed_error"))
if "_embed_success" in st.session_state:
    st.success(st.session_state.pop("_embed_success"))

# ── Guard: LLM API key (somente para o chat — embeddings independem disso) ───
if not api_key:
    st.warning("👈 Insira a API key na sidebar antes de fazer perguntas.")
    st.stop()

# ── Status badges ────────────────────────────────────────────────────────────
def _badge(icon: str, label: str, value: str, color: str) -> str:
    return (
        f'<span style="display:inline-flex;align-items:center;gap:5px;'
        f'background:{color};border-radius:20px;padding:4px 12px;'
        f'font-size:0.78rem;font-weight:600;color:#fff;white-space:nowrap;">'
        f'{icon} <span style="opacity:.75">{label}</span> {value}'
        f'</span>'
    )

_use_sem   = st.session_state.get("asst_use_semantic", False) and _chunks_table_ok
_embed_prov = st.session_state.get("asst_embed_provider", "")
_embed_key  = st.session_state.get("asst_embed_key", "")
_model      = provider_cfg.get("default_model", "")

_badges = [
    _badge("📁", "Projeto", project_name, "#1A4B8C"),
    _badge("🤖", "LLM", selected_provider, "#C97B1A"),
    _badge("⚡", "Modelo", _model, "#1e3a5f"),
]

if _use_sem and _embed_key:
    _badges.append(_badge("🔮", "Busca", "Semântica · pgvector", "#6B3FA0"))
    _badges.append(_badge("🧮", "Embedding", _embed_prov, "#4A2870"))
else:
    _badges.append(_badge("🔑", "Busca", "Keyword", "#374151"))

if _chunks_table_ok:
    _cov = get_embedding_coverage(project_id)
    _idx = _cov.get("indexed_meetings", 0)
    _tot = _cov.get("total_meetings", 0)
    _chunks_n = _cov.get("total_chunks", 0)
    if _idx > 0:
        _badges.append(_badge("📊", "Índice", f"{_idx}/{_tot} reuniões · {_chunks_n:,} chunks", "#1A7F5A"))

st.markdown(
    '<div style="display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 16px 0;">'
    + "".join(_badges)
    + "</div>",
    unsafe_allow_html=True,
)

# ── Session history ───────────────────────────────────────────────────────────
if "assistant_history" not in st.session_state:
    st.session_state["assistant_history"] = []

history: list[dict] = st.session_state["assistant_history"]

# ── Render existing conversation ──────────────────────────────────────────────
_editing_idx: int | None = st.session_state.get("_edit_idx")

for i, msg in enumerate(history):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "user":
            if st.button("✏️", key=f"_edit_btn_{i}", help="Reeditar esta pergunta"):
                st.session_state["_edit_idx"]   = i
                st.session_state["_edit_draft"] = msg["content"]
                st.rerun()

# ── Edit panel (shown when a message is being re-edited) ──────────────────────
if _editing_idx is not None:
    st.markdown("---")
    st.markdown(
        f"**✏️ Reeditando pergunta {_editing_idx // 2 + 1}** "
        f"— as respostas seguintes serão descartadas."
    )
    edited_text = st.text_area(
        "Editar pergunta:",
        value=st.session_state.get("_edit_draft", ""),
        height=100,
        key="_edit_ta",
    )
    col_cancel, col_submit = st.columns([1, 3])
    with col_cancel:
        if st.button("✖️ Cancelar", key="_edit_cancel", use_container_width=True):
            st.session_state.pop("_edit_idx", None)
            st.session_state.pop("_edit_draft", None)
            st.rerun()
    with col_submit:
        if st.button("🔄 Reenviar", key="_edit_submit", type="primary", use_container_width=True):
            if edited_text.strip():
                st.session_state["assistant_history"] = history[:_editing_idx]
                st.session_state["_resubmit_question"] = edited_text.strip()
                st.session_state.pop("_edit_idx", None)
                st.session_state.pop("_edit_draft", None)
                st.rerun()

# ── New message input ─────────────────────────────────────────────────────────
question = st.chat_input(
    "Faça uma pergunta sobre as reuniões, requisitos, processos ou sobre como usar o sistema...",
    disabled=(_editing_idx is not None),
)

# Aceita pergunta nova ou pergunta reeditada
active_question: str | None = (
    st.session_state.pop("_resubmit_question", None)
    or question
)

if active_question:
    question = active_question
    # Reload history (may have been truncated by resubmit)
    history = st.session_state["assistant_history"]

    # 1. Append and render user message
    history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    use_tools_now = st.session_state.get("asst_use_tools", True)

    # ── Caminho A: Tool-use (LLM decide quais ferramentas usar) ──────────────
    if use_tools_now:
        with st.spinner("🔧 Consultando ferramentas..."):
            client_info = {"api_key": api_key}
            agent = AgentAssistant(client_info, provider_cfg)
            try:
                response_text, tokens_used, tools_called = agent.chat_with_tools(
                    history=history[:-1],
                    question=question,
                    project_id=project_id,
                    project_name=project_name,
                )
            except Exception as exc:
                # Fallback to classic RAG on tool-use failure
                st.warning(
                    f"⚠️ Tool-use falhou ({exc}). Usando busca por keyword como fallback."
                )
                ctx = retrieve_context_for_question(project_id, question)
                context_text = format_context(ctx, project_name)
                try:
                    response_text, tokens_used = agent.chat(
                        history=history[:-1],
                        context_text=context_text,
                        question=question,
                    )
                except Exception as exc2:
                    response_text = f"❌ Erro ao gerar resposta: {exc2}"
                    tokens_used = 0
                tools_called = []

        # 4. Append and render
        history.append({"role": "assistant", "content": response_text})
        st.session_state["assistant_history"] = history

        with st.chat_message("assistant"):
            st.markdown(response_text)

        # 5. Info caption
        if tools_called:
            tools_str = " · ".join(f"`{t}`" for t in tools_called)
            st.caption(f"🔢 {tokens_used} tokens · 🔧 ferramentas usadas: {tools_str}")
        else:
            st.caption(f"🔢 {tokens_used} tokens · 🔧 tool-use (sem chamadas externas)")

    # ── Caminho B: RAG clássico (keyword / semântico) ─────────────────────────
    else:
        # 2. Retrieve context
        use_semantic_now = (
            st.session_state.get("asst_use_semantic", False)
            and _chunks_table_ok
        )

        if use_semantic_now:
            embed_key_now = st.session_state.get("asst_embed_key", "")
            embed_provider_now = st.session_state.get("asst_embed_provider", list(EMBEDDING_PROVIDERS.keys())[0])
            if not embed_key_now:
                st.warning("⚠️ Busca semântica ativa mas sem API key de embedding. Usando keyword.")
                use_semantic_now = False

        with st.spinner("🔍 Pesquisando nas fontes de dados..."):
            if use_semantic_now:
                ctx = retrieve_context_semantic(
                    project_id=project_id,
                    question=question,
                    api_key=embed_key_now,
                    provider=embed_provider_now,
                )
            else:
                ctx = retrieve_context_for_question(project_id, question)

            context_text = format_context(ctx, project_name)

        meetings_passages = ctx.get("meetings_passages") or []
        no_transcript     = ctx.get("meetings_without_transcript") or []
        search_mode       = ctx.get("search_mode", "keyword")

        if search_mode == "keyword_fallback":
            st.info(
                "ℹ️ Embeddings ainda não gerados — usando busca por **keyword**. "
                "Gere os embeddings na sidebar (⚡) para ativar a busca semântica.",
                icon=None,
            )
        if not meetings_passages and no_transcript:
            st.warning(
                "⚠️ Nenhum trecho relevante encontrado. "
                "Reuniões sem correspondência: " + ", ".join(no_transcript)
            )

        # 3. Generate response
        with st.spinner("🤖 Gerando resposta..."):
            client_info = {"api_key": api_key}
            agent = AgentAssistant(client_info, provider_cfg)
            try:
                response_text, tokens_used = agent.chat(
                    history=history[:-1],
                    context_text=context_text,
                    question=question,
                )
            except Exception as exc:
                response_text = f"❌ Erro ao gerar resposta: {exc}"
                tokens_used = 0

        # 4. Append and render
        history.append({"role": "assistant", "content": response_text})
        st.session_state["assistant_history"] = history

        with st.chat_message("assistant"):
            st.markdown(response_text)

        # 5. Info caption
        n_meetings = len(meetings_passages)
        if search_mode == "semantic":
            mode_badge = "🔮 semântica"
        elif search_mode == "keyword_fallback":
            mode_badge = "🔑 keyword (fallback)"
        else:
            mode_badge = "🔑 keyword"
        st.caption(
            f"🔢 {tokens_used} tokens · {n_meetings} reunião(ões) · {mode_badge}"
        )
