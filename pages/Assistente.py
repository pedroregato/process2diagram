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
from modules.embeddings import EMBEDDING_PROVIDERS
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
            if st.button("⚡ Gerar Embeddings", key="asst_gen_embeddings", type="secondary"):
                if not embed_api_key:
                    st.warning("Insira a API key do provedor de embedding.")
                else:
                    st.session_state["_trigger_embed"] = {
                        "provider": embed_provider,
                        "api_key":  embed_api_key,
                        "project_id": project_id,
                    }

    if use_semantic:
        embed_provider_sel = st.session_state.get("asst_embed_provider", list(EMBEDDING_PROVIDERS.keys())[0])
        embed_key_sel = st.session_state.get("asst_embed_key", "")
        st.caption(f"Provedor ativo: **{embed_provider_sel}**")
        if not embed_key_sel:
            st.warning("Insira a API key de embedding acima para a busca semântica funcionar.")

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

            for i, m in enumerate(meeting_rows_raw):
                transcript = m.get("transcript_clean") or m.get("transcript_raw") or ""
                title = m.get("title") or f"Reunião {m.get('meeting_number','?')}"
                if transcript.strip():
                    n_saved = save_transcript_embeddings(
                        meeting_id=m["id"],
                        project_id=project_id,
                        transcript=transcript,
                        api_key=trigger["api_key"],
                        provider=trigger["provider"],
                    )
                    if n_saved > 0:
                        total_gen += n_saved
                    else:
                        errors.append(title)
                prog.progress((i + 1) / n_total if n_total else 1.0)

            prog.empty()
            if errors:
                st.warning(f"⚠️ Falha ao gerar embeddings para: {', '.join(errors)}")
            else:
                st.success(f"✅ {total_gen} chunks indexados em {n_total} reuniões.")
            st.rerun()

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
for msg in history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── New message input ─────────────────────────────────────────────────────────
question = st.chat_input("Faça uma pergunta sobre as reuniões, requisitos, processos ou sobre como usar o sistema...")

if question:
    # 1. Append and render user message
    history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # 2. Retrieve context
    use_semantic_now = (
        st.session_state.get("asst_use_semantic", False)
        and _chunks_table_ok
    )

    if use_semantic_now:
        embed_key_now = st.session_state.get("asst_embed_key", "")
        embed_provider_now = st.session_state.get("asst_embed_provider", list(EMBEDDING_PROVIDERS.keys())[0])

        if not embed_key_now:
            st.warning("⚠️ Busca semântica ativa mas sem API key de embedding. Usando busca por keyword.")
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

    # Warn if no transcript data is available at all
    meetings_passages = ctx.get("meetings_passages") or []
    no_transcript = ctx.get("meetings_without_transcript") or []
    search_mode = ctx.get("search_mode", "keyword")

    if not meetings_passages and no_transcript:
        st.warning(
            "⚠️ Nenhuma transcrição encontrada para este projeto. "
            "As reuniões a seguir não têm transcrição "
            + ("indexada (gere os embeddings acima)" if search_mode == "semantic" else "armazenada")
            + ": "
            + ", ".join(no_transcript)
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

    # 4. Append and render assistant response
    history.append({"role": "assistant", "content": response_text})
    st.session_state["assistant_history"] = history

    with st.chat_message("assistant"):
        st.markdown(response_text)

    # 5. Token / source info caption
    n_meetings = len(meetings_passages)
    mode_badge = "🔮 semântica" if use_semantic_now else "🔑 keyword"
    st.caption(
        f"🔢 {tokens_used} tokens · {n_meetings} reunião(ões) consultada(s) · {mode_badge}"
    )
