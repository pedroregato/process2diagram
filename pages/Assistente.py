# pages/Assistente.py
# Assistente conversacional RAG sobre reuniões, requisitos, processos e SBVR.

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st

from ui.auth_gate import apply_auth_gate
from modules.supabase_client import supabase_configured
from modules.config import AVAILABLE_PROVIDERS
from core.project_store import (
    list_projects,
    retrieve_context_for_question,
    format_context,
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

    # ── Clear conversation ────────────────────────────────────────────────────
    if st.button("🗑️ Limpar conversa", key="asst_clear"):
        st.session_state["assistant_history"] = []
        st.rerun()

# ── Main area ─────────────────────────────────────────────────────────────────
st.markdown("# 💬 Assistente de Reuniões")
st.caption(
    "Faça perguntas sobre transcrições, requisitos, processos BPMN e vocabulário SBVR "
    "armazenados no projeto selecionado. O assistente cita as reuniões de origem das informações."
)

# ── Guard: Supabase + project + API key ───────────────────────────────────────
if not supabase_configured():
    st.warning(
        "⚙️ Supabase não configurado. Adicione as credenciais em Settings → Secrets."
    )
    st.stop()

if not project_id:
    st.warning("👈 Selecione um projeto na sidebar para começar.")
    st.stop()

if not api_key:
    st.warning("👈 Insira a API key na sidebar antes de fazer perguntas.")
    st.stop()

# ── Session history ───────────────────────────────────────────────────────────
if "assistant_history" not in st.session_state:
    st.session_state["assistant_history"] = []

history: list[dict] = st.session_state["assistant_history"]

# ── Render existing conversation ──────────────────────────────────────────────
for msg in history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── New message input ─────────────────────────────────────────────────────────
question = st.chat_input("Faça uma pergunta sobre as reuniões, requisitos ou processos...")

if question:
    # 1. Append and render user message
    history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # 2. Retrieve context
    with st.spinner("🔍 Pesquisando nas fontes de dados..."):
        ctx = retrieve_context_for_question(project_id, question)
        context_text = format_context(ctx, project_name)

    # Warn if no transcript data is available at all
    meetings_passages = ctx.get("meetings_passages") or []
    no_transcript = ctx.get("meetings_without_transcript") or []
    if not meetings_passages and no_transcript:
        st.warning(
            "⚠️ Nenhuma transcrição encontrada para este projeto. "
            "As reuniões a seguir não têm transcrição armazenada e não podem ser pesquisadas: "
            + ", ".join(no_transcript)
        )

    # 3. Generate response
    with st.spinner("🤖 Gerando resposta..."):
        client_info = {"api_key": api_key}
        agent = AgentAssistant(client_info, provider_cfg)
        # Pass all history except the current question (history[:-1]) + question separately
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
    st.caption(
        f"🔢 {tokens_used} tokens · {n_meetings} reunião(ões) consultada(s)"
    )
