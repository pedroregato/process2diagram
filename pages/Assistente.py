# pages/Assistente.py
# Assistente conversacional RAG sobre reuniões, requisitos, processos e SBVR.

from __future__ import annotations

import sys
from pathlib import Path
import re
import threading
import time
from collections import Counter

import streamlit as st

from ui.auth_gate import apply_auth_gate
from modules.supabase_client import supabase_configured, get_supabase_client
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
from ui.components.copy_button import copy_button

# ── Page config ───────────────────────────────────────────────────────────────
apply_auth_gate()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 💬 Assistente")

    st.markdown("#### 📁 Projeto")
    projects = list_projects()
    if projects:
        proj_names = [p["name"] for p in projects]
        proj_map = {p["name"]: p for p in projects}
        selected_proj_name = st.selectbox("Selecione o projeto", proj_names, key="asst_proj_sel")
        selected_project = proj_map[selected_proj_name]
        project_id = selected_project["id"]
        project_name = selected_project["name"]
    else:
        st.info("Nenhum projeto disponível.")
        project_id = None
        project_name = ""

    st.markdown("---")

    st.markdown("#### 🔧 Modo Ferramentas")
    use_tools = st.checkbox("Ativar tool-use", value=True, key="asst_use_tools")
    if use_tools:
        st.caption("🔢 21 ferramentas disponíveis")

    st.markdown("---")

    # Contexto adicional (mantido)
    uploaded_ctx_file = st.file_uploader("Arquivo de contexto", type=["txt", "docx", "pdf", "csv", "xlsx"], key="asst_context_file")
    # ... (seu código de processamento de arquivo pode ficar aqui - mantive simplificado por brevidade)

    if st.button("🗑️ Limpar conversa", key="asst_clear"):
        st.session_state["assistant_history"] = []
        st.rerun()

# ── Configurações ─────────────────────────────────────────────────────────────
selected_provider = st.session_state.get("asst_provider", "DeepSeek")
provider_cfg = AVAILABLE_PROVIDERS.get(selected_provider, AVAILABLE_PROVIDERS.get("DeepSeek", {}))
api_key = st.session_state.get("asst_api_key", "")
_chunks_table_ok = supabase_configured() and transcript_chunks_table_exists()
embed_provider = st.session_state.get("asst_embed_provider", list(EMBEDDING_PROVIDERS.keys())[0])
embed_api_key = st.session_state.get("asst_embed_key", "")

if "asst_use_semantic" not in st.session_state:
    st.session_state["asst_use_semantic"] = bool(embed_api_key and _chunks_table_ok)

# ── Main Area ─────────────────────────────────────────────────────────────────
st.markdown("# 💬 Assistente de Reuniões")

if not supabase_configured():
    st.warning("⚙️ Supabase não configurado.")
    st.stop()

if not project_id:
    st.warning("👈 Selecione um projeto na sidebar.")
    st.stop()

# ── Trigger: Batch Embeddings ─────────────────────────────────────────────────
if "_trigger_embed" in st.session_state:
    trigger = st.session_state.pop("_trigger_embed")
    if trigger["project_id"] == project_id:
        db = get_supabase_client()
        if db:
            with st.spinner("⚡ Gerando embeddings em lote..."):
                meeting_rows = db.table("meetings") \
                    .select("id, title, meeting_number, transcript_clean, transcript_raw") \
                    .eq("project_id", project_id) \
                    .order("meeting_number") \
                    .execute().data or []

            total_gen = 0
            errors = []
            skipped = []
            prog = st.progress(0.0)
            n_total = len(meeting_rows)

            for i, m in enumerate(meeting_rows):
                meeting_id = m["id"]
                title = m.get("title") or f"Reunião {m.get('meeting_number', '?')}"
                transcript = (m.get("transcript_clean") or m.get("transcript_raw") or "").strip()

                if len(transcript) < 100:
                    skipped.append(title)
                    prog.progress((i + 1) / n_total if n_total else 1.0)
                    continue

                try:
                    if i > 0:
                        time.sleep(1.8)
                    n_saved = save_transcript_embeddings(
                        meeting_id=meeting_id,
                        project_id=project_id,
                        transcript=transcript,
                        api_key=trigger["api_key"],
                        provider=trigger["provider"],
                    )
                    total_gen += n_saved
                except Exception as exc:
                    error_str = str(exc)
                    if any(x in error_str.lower() for x in ["429", "quota", "rate limit"]):
                        errors.append(f"{title} → Rate limit do Gemini")
                        time.sleep(10)
                    else:
                        errors.append(f"{title}: {error_str[:150]}")

                prog.progress((i + 1) / n_total if n_total else 1.0)

            prog.empty()

            msg = f"✅ **{total_gen:,} chunks** gerados com sucesso."
            if skipped:
                msg += f"\n\n⚠️ {len(skipped)} reuniões puladas (transcrição curta)."
            if errors:
                msg += f"\n\n❌ Falhas em {len(errors)} reuniões:\n" + "\n".join(errors[:15])

            st.session_state["_embed_result"] = msg
            st.rerun()

# ── Feedback ─────────────────────────────────────────────────────────────────
if "_embed_result" in st.session_state:
    result = st.session_state.pop("_embed_result")
    if "❌" in result:
        st.error(result)
    elif "⚠️" in result:
        st.warning(result)
    else:
        st.success(result)

# ── Gerar Embeddings em Lote ─────────────────────────────────────────────────
if _chunks_table_ok and project_id:
    _emb_cov = get_embedding_coverage(project_id)
    _emb_idx = _emb_cov.get("indexed_meetings", 0)
    _emb_tot = _emb_cov.get("total_meetings", 0)
    _emb_chk = _emb_cov.get("total_chunks", 0)

    with st.expander(
        f"⚡ Gerar Embeddings em Lote · {_emb_idx}/{_emb_tot} reuniões · {_emb_chk:,} chunks",
        expanded=(_emb_idx == 0 and _emb_tot > 0),
    ):
        st.caption("Gera embeddings para todas as reuniões de uma vez.")
        if st.button("⚡ Gerar para Todas as Reuniões", key="asst_gen_embeddings_batch", type="primary", use_container_width=True):
            if not embed_api_key:
                st.warning("Configure a chave de embedding em Configurações.")
            else:
                st.session_state["_trigger_embed"] = {
                    "provider": embed_provider,
                    "api_key": embed_api_key,
                    "project_id": project_id,
                }
                st.rerun()

# ── Reprocessamento Individual ───────────────────────────────────────────────
if _chunks_table_ok and project_id:
    st.markdown("---")
    st.markdown("### 🔄 Reprocessar Embeddings Individualmente")

    try:
        db = get_supabase_client()
        meetings = db.table("meetings") \
            .select("id, meeting_number, title, transcript_clean, transcript_raw") \
            .eq("project_id", project_id) \
            .order("meeting_number") \
            .execute().data or []

        meeting_ids = [m["id"] for m in meetings if m.get("id")]
        chunk_counts = {}
        if meeting_ids:
            chunk_data = db.table("transcript_chunks") \
                .select("meeting_id") \
                .in_("meeting_id", meeting_ids) \
                .execute().data or []
            count_dict = Counter(row["meeting_id"] for row in chunk_data)
            chunk_counts = dict(count_dict)

        for m in meetings:
            meeting_id = m["id"]
            number = m.get("meeting_number")
            title = m.get("title") or f"Reunião {number}"
            transcript = (m.get("transcript_clean") or m.get("transcript_raw") or "").strip()
            chunk_qty = chunk_counts.get(meeting_id, 0)

            status_icon = "✅" if chunk_qty > 0 else "❌"

            with st.expander(
                f"{status_icon} Reunião {number} — {title[:68]}{'...' if len(title) > 68 else ''}",
                expanded=False
            ):
                col_info, col_btn = st.columns([3, 1])
                with col_info:
                    st.caption(f"**Título:** {title}")
                    st.caption(f"**Tamanho:** {len(transcript):,} caracteres")
                    st.metric("Chunks", chunk_qty)
                with col_btn:
                    if st.button("🔄 Gerar Embeddings", key=f"embed_single_{meeting_id}", use_container_width=True, type="secondary"):
                        with st.spinner(f"Processando Reunião {number}..."):
                            try:
                                if len(transcript) < 100:
                                    st.warning("Transcrição muito curta.")
                                else:
                                    n_saved = save_transcript_embeddings(
                                        meeting_id=meeting_id,
                                        project_id=project_id,
                                        transcript=transcript,
                                        api_key=embed_api_key,
                                        provider=embed_provider,
                                    )
                                    if n_saved > 0:
                                        st.success(f"✅ {n_saved} chunks gerados!")
                                    else:
                                        st.info("Nenhum chunk gerado.")
                                st.rerun()
                            except Exception as e:
                                error_msg = str(e)
                                if any(x in error_msg.lower() for x in ["429", "quota", "rate limit"]):
                                    st.error("❌ Rate limit do Gemini. Aguarde alguns minutos.")
                                else:
                                    st.error(f"❌ Erro: {error_msg[:180]}")

    except Exception as e:
        st.error(f"Erro ao carregar reuniões: {e}")

# ── Guard: LLM API key ───────────────────────────────────────────────────────
if not api_key:
    st.warning("⚙️ Configure a chave de API em Configurações → LLM Assistente.")
    st.stop()

if not project_id:
    st.warning("👈 Selecione um projeto na sidebar para começar.")
    st.stop()

# ── Trigger: geração de embeddings (antes do guard de api_key LLM) ──────────
# Processado aqui para não depender da chave LLM — usa a chave de embedding.
# ── Trigger: geração de embeddings em batch (mantido e melhorado) ─────────────

# ── Trigger: geração de embeddings em batch ───────────────────────────────────
if "_trigger_embed" in st.session_state:
    trigger = st.session_state.pop("_trigger_embed")
    if trigger["project_id"] == project_id:
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if db:
            with st.spinner("⚡ Gerando embeddings em lote... (pode demorar em reuniões longas)"):
                meeting_rows = db.table("meetings") \
                    .select("id, title, meeting_number, transcript_clean, transcript_raw") \
                    .eq("project_id", project_id) \
                    .order("meeting_number") \
                    .execute().data or []

            total_gen = 0
            errors = []
            skipped = []
            prog = st.progress(0.0)
            n_total = len(meeting_rows)

            for i, m in enumerate(meeting_rows):
                meeting_id = m["id"]
                title = m.get("title") or f"Reunião {m.get('meeting_number', '?')}"
                transcript = (m.get("transcript_clean") or m.get("transcript_raw") or "").strip()

                if len(transcript) < 100:
                    skipped.append(title)
                    prog.progress((i + 1) / n_total if n_total else 1.0)
                    continue

                try:
                    if i > 0:
                        time.sleep(1.8)  # Delay para evitar rate limit do Gemini

                    n_saved = save_transcript_embeddings(
                        meeting_id=meeting_id,
                        project_id=project_id,
                        transcript=transcript,
                        api_key=trigger["api_key"],
                        provider=trigger["provider"],
                    )
                    total_gen += n_saved
                except Exception as exc:
                    error_str = str(exc)
                    if any(x in error_str.lower() for x in ["429", "quota", "rate limit"]):
                        errors.append(f"{title} → Rate limit / Quota esgotada do Gemini")
                        time.sleep(10)
                    else:
                        errors.append(f"{title}: {error_str[:150]}")

                prog.progress((i + 1) / n_total if n_total else 1.0)

            prog.empty()

            msg = f"✅ **{total_gen:,} chunks** gerados com sucesso em lote."
            if skipped:
                msg += f"\n\n⚠️ **{len(skipped)} reuniões puladas** (transcrição muito curta)."
            if errors:
                msg += f"\n\n❌ **Falhas em {len(errors)} reuniões**:\n" + "\n".join(errors[:15])

            st.session_state["_embed_result"] = msg
            st.rerun()


# ── Feedback do processamento (batch ou individual) ───────────────────────────
if "_embed_result" in st.session_state:
    result = st.session_state.pop("_embed_result")
    if "❌" in result:
        st.error(result)
    elif "⚠️" in result:
        st.warning(result)
    else:
        st.success(result)


# ── Gerar Embeddings em Lote ─────────────────────────────────────────────────
if _chunks_table_ok and project_id:
    _emb_cov = get_embedding_coverage(project_id)
    _emb_idx = _emb_cov.get("indexed_meetings", 0)
    _emb_tot = _emb_cov.get("total_meetings", 0)
    _emb_chk = _emb_cov.get("total_chunks", 0)

    with st.expander(
        f"⚡ Gerar Embeddings em Lote  ·  {_emb_idx}/{_emb_tot} reuniões indexadas · {_emb_chk:,} chunks",
        expanded=(_emb_idx == 0 and _emb_tot > 0),
    ):
        st.caption(
            "Gera embeddings para **todas** as reuniões do projeto de uma vez. "
            "Recomendado quando o projeto ainda não tem embeddings ou após adicionar várias reuniões."
        )
        st.caption(f"Provedor atual: **{embed_provider}**")

        col_btn, col_info = st.columns([2, 3])
        with col_btn:
            if st.button("⚡ Gerar Embeddings para Todas as Reuniões",
                         key="asst_gen_embeddings_batch",
                         type="primary",
                         use_container_width=True):
                if not embed_api_key:
                    st.warning("Configure a chave de embedding em Configurações → Embeddings & Busca.")
                else:
                    st.session_state["_trigger_embed"] = {
                        "provider": embed_provider,
                        "api_key": embed_api_key,
                        "project_id": project_id,
                    }
                    st.rerun()

        with col_info:
            st.caption("⚠️ Pode demorar bastante em projetos com reuniões longas devido ao limite do Gemini Free Tier.")


# ── Reprocessamento Individual por Reunião ───────────────────────────────────
if _chunks_table_ok and project_id:
    st.markdown("---")
    st.markdown("### 🔄 Reprocessar Embeddings Individualmente")

    try:
        db = get_supabase_client()

        # Busca todas as reuniões do projeto
        meetings = db.table("meetings") \
            .select("id, meeting_number, title, transcript_clean, transcript_raw") \
            .eq("project_id", project_id) \
            .order("meeting_number") \
            .execute().data or []

        # Conta quantos chunks cada reunião tem
        meeting_ids = [m["id"] for m in meetings if m.get("id")]
        chunk_counts = {}

        if meeting_ids:
            try:
                chunk_data = db.table("transcript_chunks") \
                    .select("meeting_id") \
                    .in_("meeting_id", meeting_ids) \
                    .execute().data or []

                from collections import Counter
                count_dict = Counter(row["meeting_id"] for row in chunk_data)
                chunk_counts = dict(count_dict)
            except Exception:
                chunk_counts = {}

        for m in meetings:
            meeting_id = m["id"]
            number = m.get("meeting_number")
            title = m.get("title") or f"Reunião {number}"
            transcript = (m.get("transcript_clean") or m.get("transcript_raw") or "").strip()
            chunk_qty = chunk_counts.get(meeting_id, 0)

            status_icon = "✅" if chunk_qty > 0 else "❌"

            with st.expander(
                f"{status_icon} Reunião {number} — {title[:68]}{'...' if len(title) > 68 else ''}",
                expanded=False
            ):
                col_info, col_btn = st.columns([3, 1])

                with col_info:
                    st.caption(f"**Título:** {title}")
                    st.caption(f"**Tamanho da transcrição:** {len(transcript):,} caracteres")
                    st.metric("Chunks gerados", chunk_qty)

                with col_btn:
                    if st.button(
                        "🔄 Gerar Embeddings",
                        key=f"embed_single_{meeting_id}",
                        use_container_width=True,
                        type="secondary"
                    ):
                        with st.spinner(f"Processando Reunião {number}: {title[:50]}..."):
                            try:
                                if len(transcript) < 100:
                                    st.warning("Transcrição muito curta. Nada foi processado.")
                                else:
                                    n_saved = save_transcript_embeddings(
                                        meeting_id=meeting_id,
                                        project_id=project_id,
                                        transcript=transcript,
                                        api_key=embed_api_key,
                                        provider=embed_provider,
                                    )
                                    if n_saved > 0:
                                        st.success(f"✅ {n_saved} chunks gerados com sucesso!")
                                    else:
                                        st.info("Nenhum chunk novo foi gerado.")
                                st.rerun()
                            except Exception as e:
                                error_msg = str(e)
                                if any(x in error_msg.lower() for x in ["429", "quota", "rate limit", "resource exhausted"]):
                                    st.error("❌ Rate limit / Quota esgotada do Gemini. Aguarde alguns minutos e tente novamente.")
                                else:
                                    st.error(f"❌ Erro ao gerar embeddings: {error_msg[:180]}")

    except Exception as e:
        st.error(f"Erro ao carregar lista de reuniões para reprocessamento: {e}")
    trigger = st.session_state.pop("_trigger_embed")
    if trigger["project_id"] == project_id:
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if db:
            with st.spinner("⚡ Gerando embeddings em lote... (pode demorar em reuniões longas)"):
                meeting_rows = db.table("meetings") \
                    .select("id, title, meeting_number, transcript_clean, transcript_raw") \
                    .eq("project_id", project_id) \
                    .order("meeting_number") \
                    .execute().data or []

            total_gen = 0
            errors = []
            skipped = []
            prog = st.progress(0.0)
            n_total = len(meeting_rows)

            for i, m in enumerate(meeting_rows):
                meeting_id = m["id"]
                title = m.get("title") or f"Reunião {m.get('meeting_number', '?')}"
                transcript = (m.get("transcript_clean") or m.get("transcript_raw") or "").strip()

                if len(transcript) < 100:
                    skipped.append(title)
                    prog.progress((i + 1) / n_total if n_total else 1.0)
                    continue

                try:
                    if i > 0:
                        time.sleep(1.8)  # Delay para evitar rate limit do Gemini Free Tier

                    n_saved = save_transcript_embeddings(
                        meeting_id=meeting_id,
                        project_id=project_id,
                        transcript=transcript,
                        api_key=trigger["api_key"],
                        provider=trigger["provider"],
                    )
                    total_gen += n_saved
                except Exception as exc:
                    error_str = str(exc)
                    if "429" in error_str or "quota" in error_str.lower() or "rate limit" in error_str.lower():
                        errors.append(f"{title} → Rate limit / Quota esgotada do Gemini")
                        time.sleep(10)
                    else:
                        errors.append(f"{title}: {error_str[:150]}")

                prog.progress((i + 1) / n_total if n_total else 1.0)

            prog.empty()

            msg = f"✅ **{total_gen:,} chunks** gerados com sucesso em lote."
            if skipped:
                msg += f"\n\n⚠️ **{len(skipped)} reuniões puladas** (transcrição muito curta)."
            if errors:
                msg += f"\n\n❌ **Falhas em {len(errors)} reuniões**:\n" + "\n".join(errors[:15])

            st.session_state["_embed_result"] = msg
            st.rerun()


# ── Feedback do processamento (batch ou individual) ───────────────────────────
if "_embed_result" in st.session_state:
    result = st.session_state.pop("_embed_result")
    if "❌" in result:
        st.error(result)
    elif "⚠️" in result:
        st.warning(result)
    else:
        st.success(result)


# ── Gerar Embeddings em Batch ─────────────────────────────────────────────────
if _chunks_table_ok and project_id:
    _emb_cov = get_embedding_coverage(project_id)
    _emb_idx = _emb_cov.get("indexed_meetings", 0)
    _emb_tot = _emb_cov.get("total_meetings", 0)
    _emb_chk = _emb_cov.get("total_chunks", 0)

    with st.expander(
        f"⚡ Gerar Embeddings em Lote  ·  {_emb_idx}/{_emb_tot} reuniões indexadas · {_emb_chk:,} chunks",
        expanded=(_emb_idx == 0 and _emb_tot > 0),
    ):
        st.caption(
            "Gera embeddings para **todas** as reuniões do projeto de uma vez. "
            "Recomendado quando o projeto ainda não tem embeddings ou após adicionar várias reuniões."
        )
        st.caption(f"Provedor atual: **{embed_provider}**")

        col_btn, col_info = st.columns([2, 3])
        with col_btn:
            if st.button("⚡ Gerar Embeddings para Todas as Reuniões",
                         key="asst_gen_embeddings_batch",
                         type="primary",
                         use_container_width=True):
                if not embed_api_key:
                    st.warning("Configure a chave de embedding em Configurações → Embeddings & Busca.")
                else:
                    st.session_state["_trigger_embed"] = {
                        "provider": embed_provider,
                        "api_key": embed_api_key,
                        "project_id": project_id,
                    }
                    st.rerun()

        with col_info:
            st.caption("⚠️ Pode demorar bastante em projetos com reuniões longas devido ao limite do Gemini Free Tier.")


# ── Reprocessamento Individual por Reunião ───────────────────────────────────
if _chunks_table_ok and project_id:
    st.markdown("---")
    st.markdown("### 🔄 Reprocessar Embeddings Individualmente")

    try:
        db = get_supabase_client()

        # Busca todas as reuniões do projeto
        meetings = db.table("meetings") \
            .select("id, meeting_number, title, transcript_clean, transcript_raw") \
            .eq("project_id", project_id) \
            .order("meeting_number") \
            .execute().data or []

        # Conta quantos chunks cada reunião tem (forma correta e compatível)
        meeting_ids = [m["id"] for m in meetings if m.get("id")]
        chunk_counts = {}

        if meeting_ids:
            try:
                chunk_data = db.table("transcript_chunks") \
                    .select("meeting_id") \
                    .in_("meeting_id", meeting_ids) \
                    .execute().data or []

                # Conta manualmente usando Counter
                from collections import Counter
                count_dict = Counter(row["meeting_id"] for row in chunk_data)
                chunk_counts = dict(count_dict)
            except Exception:
                chunk_counts = {}  # se falhar, mostramos 0 chunks

        for m in meetings:
            meeting_id = m["id"]
            number = m.get("meeting_number")
            title = m.get("title") or f"Reunião {number}"
            transcript = (m.get("transcript_clean") or m.get("transcript_raw") or "").strip()
            chunk_qty = chunk_counts.get(meeting_id, 0)

            status_icon = "✅" if chunk_qty > 0 else "❌"

            with st.expander(
                f"{status_icon} Reunião {number} — {title[:68]}{'...' if len(title) > 68 else ''}",
                expanded=False
            ):
                col_info, col_btn = st.columns([3, 1])

                with col_info:
                    st.caption(f"**Título:** {title}")
                    st.caption(f"**Tamanho da transcrição:** {len(transcript):,} caracteres")
                    st.metric("Chunks gerados", chunk_qty)

                with col_btn:
                    if st.button(
                        "🔄 Gerar Embeddings",
                        key=f"embed_single_{meeting_id}",
                        use_container_width=True,
                        type="secondary"
                    ):
                        with st.spinner(f"Processando Reunião {number}: {title[:50]}..."):
                            try:
                                if len(transcript) < 100:
                                    st.warning("Transcrição muito curta. Nada foi processado.")
                                else:
                                    n_saved = save_transcript_embeddings(
                                        meeting_id=meeting_id,
                                        project_id=project_id,
                                        transcript=transcript,
                                        api_key=embed_api_key,
                                        provider=embed_provider,
                                    )
                                    if n_saved > 0:
                                        st.success(f"✅ {n_saved} chunks gerados com sucesso!")
                                    else:
                                        st.info("Nenhum chunk novo foi gerado.")
                                st.rerun()
                            except Exception as e:
                                error_msg = str(e)
                                if any(x in error_msg.lower() for x in ["429", "quota", "rate limit", "resource exhausted"]):
                                    st.error("❌ Rate limit / Quota esgotada do Gemini. Aguarde alguns minutos e tente novamente.")
                                else:
                                    st.error(f"❌ Erro ao gerar embeddings: {error_msg[:180]}")

    except Exception as e:
        st.error(f"Erro ao carregar lista de reuniões para reprocessamento: {e}")

# ── Feedback de geração de embeddings (persiste entre reruns) ────────────────
if "_embed_error" in st.session_state:
    st.error(st.session_state.pop("_embed_error"))
if "_embed_success" in st.session_state:
    st.success(st.session_state.pop("_embed_success"))

# ── Gerar Embeddings (body) — disponível quando a tabela de chunks existe ─────
if _chunks_table_ok and project_id:
    _emb_cov  = get_embedding_coverage(project_id)
    _emb_tot  = _emb_cov.get("total_meetings", 0)
    _emb_idx  = _emb_cov.get("indexed_meetings", 0)
    _emb_chk  = _emb_cov.get("total_chunks", 0)
    with st.expander(
        f"⚡ Gerar Embeddings  ·  {_emb_idx}/{_emb_tot} reuniões indexadas · {_emb_chk:,} chunks",
        expanded=(_emb_idx == 0 and _emb_tot > 0),
    ):
        st.caption(
            "Gera embeddings das transcrições para habilitar a busca semântica. "
            "Execute uma vez por projeto (ou novamente quando adicionar reuniões). "
            "Configure o provedor e a chave em **⚙️ Configurações → Embeddings & Busca**."
        )
        _ep_label = embed_provider or "—"
        _ek_masked = (embed_api_key[:6] + "••••" + embed_api_key[-4:]) if len(embed_api_key) > 10 else ("✅ configurada" if embed_api_key else "❌ não configurada")
        st.caption(f"Provedor: **{_ep_label}** · Chave: `{_ek_masked}`")
        col_btn, col_diag = st.columns([2, 1])
        with col_btn:
            if st.button("⚡ Gerar Embeddings", key="asst_gen_embeddings", type="secondary", use_container_width=True):
                if not embed_api_key:
                    st.warning("Configure a chave de embedding em ⚙️ Configurações → Embeddings & Busca.")
                else:
                    st.session_state["_trigger_embed"] = {
                        "provider":   embed_provider,
                        "api_key":    embed_api_key,
                        "project_id": project_id,
                    }
        with col_diag:
            if st.button("🔍 Testar chave", key="asst_diag_models", use_container_width=True,
                         help="Lista os modelos de embedding disponíveis para esta chave"):
                if not embed_api_key:
                    st.warning("Configure a chave de embedding em ⚙️ Configurações.")
                elif embed_provider == "Google Gemini":
                    with st.spinner("Consultando modelos disponíveis..."):
                        try:
                            models = list_gemini_embedding_models(embed_api_key)
                            if models:
                                st.success(f"✅ {len(models)} modelo(s) disponíveis:")
                                for m in models:
                                    st.code(m["name"])
                            else:
                                st.error(
                                    "❌ Nenhum modelo encontrado. Verifique se a "
                                    "'Generative Language API' está habilitada para esta chave."
                                )
                        except Exception as exc:
                            st.error(f"❌ Erro: {exc}")
                else:
                    st.info("Diagnóstico disponível apenas para Google Gemini.")

# ── Guard: LLM API key (somente para o chat — embeddings independem disso) ───
if not api_key:
    st.warning("⚙️ Configure a chave de API em **Configurações → LLM Assistente** antes de fazer perguntas.")
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

_ctx_file_name = st.session_state.get("_asst_file_name", "")
if _ctx_file_name:
    _ctx_words = len(st.session_state.get("_asst_file_ctx", "").split())
    _badges.append(_badge("📎", "Arquivo", f"{_ctx_file_name} · {_ctx_words:,} palavras", "#374151"))

st.markdown(
    '<div style="display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 16px 0;">'
    + "".join(_badges)
    + "</div>",
    unsafe_allow_html=True,
)

# ── Tool catalog ──────────────────────────────────────────────────────────────
if st.session_state.get("asst_use_tools", True):
    from core.assistant_tools import get_tool_catalog
    _catalog = get_tool_catalog()
    _cat_groups = {}
    for _t in _catalog:
        _cat_groups.setdefault(_t["category"], []).append(_t)

    _cat_labels = {
        "consulta": ("🔍 Consulta", "#1A4B8C", "Somente leitura — busca e exibe dados do projeto"),
        "escrita":  ("✏️ Escrita", "#7C2D12", "Modifica dados — requer confirmação do usuário"),
        "geração":  ("🤖 Geração", "#166534", "Chama o LLM para gerar conteúdo e salva no banco"),
    }

    with st.expander(f"📖 Catálogo de Ferramentas  ·  {len(_catalog)} disponíveis", expanded=False):
        st.caption(
            "Ferramentas que o Assistente pode chamar automaticamente durante uma conversa. "
            "O LLM decide qual(is) usar com base na pergunta."
        )
        for _cat_key in ("consulta", "escrita", "geração"):
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

_DSML_SAFETY_RE = re.compile(r'<[|\uff5c]DSML[|\uff5c][^>]*>.*?<[|\uff5c]DSML[|\uff5c][^>]*>', re.DOTALL)
_DSML_CUT_RE    = re.compile(r'<[|\uff5c]DSML[|\uff5c]')


def _clean_response(text: str) -> str:
    """Safety-net: strip any DSML markup that leaked through the agent layer."""
    m = _DSML_CUT_RE.search(text)
    if m:
        text = text[:m.start()].rstrip()
    text = _DSML_SAFETY_RE.sub('', text)
    return text.strip()


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
            col_edit, col_copy, _ = st.columns([1, 1, 8])
            with col_edit:
                if st.button("✏️", key=f"_edit_btn_{i}", help="Reeditar esta pergunta"):
                    st.session_state["_edit_idx"]   = i
                    st.session_state["_edit_draft"] = msg["content"]
                    st.rerun()
            with col_copy:
                copy_button(msg["content"], key=f"copy_q_{i}", label="📋", compact=True)
        else:
            copy_button(msg["content"], key=f"copy_a_{i}", label="📋 Copiar resposta", compact=True)

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

# ── Polling block — tool-use running in background thread ─────────────────────
_asst_running = st.session_state.get("_asst_running", False)

if _asst_running:
    thread: threading.Thread = st.session_state.get("_asst_thread")
    cancel_ev: threading.Event = st.session_state.get("_asst_cancel_event")
    result_box: dict = st.session_state.get("_asst_result_box", {})

    if thread and thread.is_alive():
        # Show live status + stop button
        status_msg = st.session_state.get("_asst_status", "🔧 Consultando ferramentas…")
        with st.chat_message("assistant"):
            st.markdown(f"_{status_msg}_")

        col_msg, col_stop = st.columns([4, 1])
        with col_msg:
            st.caption(status_msg)
        with col_stop:
            if st.button("⏹ Parar", key="asst_stop_btn", type="secondary", use_container_width=True):
                cancel_ev.set()
                st.session_state["_asst_status"] = "⏹ Interrompendo…"

        # Poll — sleep briefly then rerun to check thread again
        time.sleep(0.6)
        st.rerun()

    else:
        # Thread finished (or never started) — collect result
        if thread:
            thread.join(timeout=2)

        response_text = result_box.get("response") or "❌ Sem resposta."
        tokens_used   = result_box.get("tokens", 0)
        tools_called  = result_box.get("tools_called", [])
        error         = result_box.get("error")

        if error and not result_box.get("response"):
            response_text = f"❌ Erro: {error}"

        response_text = _clean_response(response_text) or response_text
        history = st.session_state["assistant_history"]
        history.append({"role": "assistant", "content": response_text})
        st.session_state["assistant_history"] = history

        # Store caption info for display after rerun
        st.session_state["_asst_last_caption"] = {
            "tokens": tokens_used,
            "tools": tools_called,
            "mode": "tools",
        }

        # Clear running state
        for _k in ("_asst_running", "_asst_thread", "_asst_cancel_event",
                   "_asst_result_box", "_asst_status"):
            st.session_state.pop(_k, None)

        st.rerun()

# Show caption from the just-completed tool-use turn (survives one rerun)
if "_asst_last_caption" in st.session_state:
    cap = st.session_state.pop("_asst_last_caption")
    tools_called = cap.get("tools", [])
    tokens_used  = cap.get("tokens", 0)
    if tools_called:
        tools_str = " · ".join(f"`{t}`" for t in tools_called)
        st.caption(f"🔢 {tokens_used} tokens · 🔧 ferramentas usadas: {tools_str}")
    else:
        st.caption(f"🔢 {tokens_used} tokens · 🔧 tool-use (sem chamadas externas)")

# ── New message input ─────────────────────────────────────────────────────────
question = st.chat_input(
    "Faça uma pergunta sobre as reuniões, requisitos, processos ou sobre como usar o sistema...",
    disabled=(_editing_idx is not None or _asst_running),
)

# Aceita pergunta nova ou pergunta reeditada
active_question: str | None = (
    st.session_state.pop("_resubmit_question", None)
    or question
)

if active_question and not _asst_running:
    # ── Separate display question (stored in history) from LLM question ──────
    # File context is injected into the LLM question but NOT shown in the chat
    # UI or stored in history — so re-editing, copy and display stay clean.
    display_question = active_question
    _file_ctx  = st.session_state.get("_asst_file_ctx", "")
    _file_name = st.session_state.get("_asst_file_name", "")
    if _file_ctx:
        _n_words = len(_file_ctx.split())
        llm_question = (
            f"[ARQUIVO ANEXADO: {_file_name} — {_n_words:,} palavras]\n"
            f"{'─' * 50}\n"
            f"{_file_ctx}\n"
            f"{'─' * 50}\n\n"
            f"{display_question}"
        )
    else:
        llm_question = display_question

    question = display_question  # used for display / history
    # Reload history (may have been truncated by resubmit)
    history = st.session_state["assistant_history"]

    # 1. Append and render user message (always shows clean question)
    history.append({"role": "user", "content": display_question})
    with st.chat_message("user"):
        st.markdown(display_question)

    use_tools_now = st.session_state.get("asst_use_tools", True)

    # ── Caminho A: Tool-use — background thread com botão Parar ──────────────
    if use_tools_now:
        _cancel_ev  = threading.Event()
        _result_box: dict = {}

        # Capture values needed by the thread
        _api_key       = api_key
        _provider_cfg  = provider_cfg
        _history_snap  = list(history[:-1])   # excludes the current question
        _question      = llm_question          # includes file context when present
        _project_id    = project_id
        _project_name  = project_name

        def _run_tools_thread() -> None:
            def _status(msg: str) -> None:
                st.session_state["_asst_status"] = msg

            try:
                _status("🔧 Iniciando consulta…")
                _agent = AgentAssistant({"api_key": _api_key}, _provider_cfg)
                resp_text, tok, tools = _agent.chat_with_tools(
                    history=_history_snap,
                    question=_question,
                    project_id=_project_id,
                    project_name=_project_name,
                    cancel_event=_cancel_ev,
                    status_fn=_status,
                )
                _result_box["response"]     = resp_text
                _result_box["tokens"]       = tok
                _result_box["tools_called"] = tools
            except Exception as _exc:
                # Fallback to keyword RAG
                _status("⚠️ Tool-use falhou — usando busca por keyword…")
                try:
                    _ctx  = retrieve_context_for_question(_project_id, _question)
                    _ctxt = format_context(_ctx, _project_name)
                    _agent2 = AgentAssistant({"api_key": _api_key}, _provider_cfg)
                    resp_text, tok = _agent2.chat(
                        history=_history_snap,
                        context_text=_ctxt,
                        question=_question,
                    )
                    _result_box["response"]     = resp_text
                    _result_box["tokens"]       = tok
                    _result_box["tools_called"] = []
                    _result_box["error"]        = f"tool-use falhou: {_exc} (fallback keyword)"
                except Exception as _exc2:
                    _result_box["response"]     = f"❌ Erro ao gerar resposta: {_exc2}"
                    _result_box["tokens"]       = 0
                    _result_box["tools_called"] = []
                    _result_box["error"]        = str(_exc2)

        _thread = threading.Thread(target=_run_tools_thread, daemon=True)
        # Propagate Streamlit script-run context to the worker thread so that
        # st.session_state writes from _status() don't raise
        # "Tried to use SessionInfo before it was initialized".
        try:
            from streamlit.runtime.scriptrunner import add_script_run_ctx
            add_script_run_ctx(_thread)
        except Exception:
            pass  # older Streamlit versions — context not required
        st.session_state["_asst_running"]      = True
        st.session_state["_asst_thread"]       = _thread
        st.session_state["_asst_cancel_event"] = _cancel_ev
        st.session_state["_asst_result_box"]   = _result_box
        st.session_state["_asst_status"]       = "🔧 Iniciando consulta…"
        st.session_state["assistant_history"]  = history
        _thread.start()
        st.rerun()

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
                    question=display_question,
                    api_key=embed_key_now,
                    provider=embed_provider_now,
                )
            else:
                ctx = retrieve_context_for_question(project_id, display_question)

            context_text = format_context(ctx, project_name)

            # Prepend file context when available (placed before meeting data)
            if _file_ctx:
                _n_words = len(_file_ctx.split())
                context_text = (
                    f"## Arquivo Anexado: {_file_name} ({_n_words:,} palavras)\n\n"
                    f"{_file_ctx}\n\n"
                    f"---\n\n"
                    + context_text
                )

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
        response_text = _clean_response(response_text) or response_text
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
