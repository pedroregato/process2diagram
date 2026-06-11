# pages/RequirementsBackfill.py
# ─────────────────────────────────────────────────────────────────────────────
# Requirements Backfill — re-extrai e persiste requisitos na tabela requirements
# para reuniões que foram processadas antes do save_requirements_from_hub ser
# chamado no pipeline (bug corrigido em PC37).
#
# Fluxo:
#   1. Seleciona o projeto
#   2. Lista reuniões SEM requisitos na tabela requirements (ou todas)
#   3. Para cada reunião selecionada, roda AgentRequirements sobre a transcrição
#   4. Persiste via save_requirements_from_hub (cria REQ-NNN no projeto)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pandas as pd
import streamlit as st

from ui.auth_gate import apply_auth_gate
from modules.supabase_client import supabase_configured, get_supabase_client
from modules.config import AVAILABLE_PROVIDERS
from modules.session_security import render_api_key_readonly
from core.project_store import list_projects, save_requirements_from_hub

apply_auth_gate()

# ── Sidebar: LLM provider + API key ──────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuração LLM")
    selected_provider = st.selectbox(
        "Provedor",
        list(AVAILABLE_PROVIDERS.keys()),
        key="rb_provider",
    )
    provider_cfg = AVAILABLE_PROVIDERS[selected_provider]
    api_key = render_api_key_readonly(selected_provider)
    output_language = st.selectbox(
        "Idioma de saída",
        ["Auto-detect", "Portuguese (BR)", "English"],
        key="rb_lang",
    )

client_info = {"api_key": api_key} if api_key else None

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 📝 Requirements Backfill")
st.caption(
    "Re-extrai e persiste requisitos (AgentRequirements) para reuniões que foram "
    "processadas antes do pipeline salvar na tabela `requirements`. "
    "Não recria reuniões nem duplica dados."
)

if not supabase_configured():
    st.error("⚙️ Supabase não configurado.")
    st.stop()

db = get_supabase_client()
if not db:
    st.error("Não foi possível conectar ao Supabase.")
    st.stop()

# ── 1. Projeto ────────────────────────────────────────────────────────────────
st.markdown("## 1️⃣ Projeto")
projects = list_projects()
if not projects:
    st.warning("Nenhum projeto encontrado no banco de dados.")
    st.stop()

proj_map     = {p["name"]: p for p in projects}
_active_pid  = st.session_state.get("active_project_id")
_default_idx = next((i for i, p in enumerate(projects) if p["id"] == _active_pid), 0)
sel_proj     = st.selectbox("Contexto", list(proj_map.keys()), index=_default_idx, key="rb_proj")
if not sel_proj:
    st.stop()

project_id = proj_map[sel_proj]["id"]

# ── 2. Reuniões sem requisitos ────────────────────────────────────────────────
st.markdown("## 2️⃣ Reuniões a processar")

try:
    all_meetings = db.table("meetings") \
        .select("id, meeting_number, title, meeting_date, transcript_clean, transcript_raw") \
        .eq("project_id", project_id) \
        .order("meeting_number") \
        .execute().data or []
except Exception as e:
    st.error(f"Erro ao carregar reuniões: {e}")
    st.stop()

# IDs que já têm requisitos na tabela requirements
try:
    existing_req_mids = {
        r["first_meeting_id"]
        for r in (
            db.table("requirements")
              .select("first_meeting_id")
              .eq("project_id", project_id)
              .execute().data or []
        )
        if r.get("first_meeting_id")
    }
except Exception:
    existing_req_mids = set()

all_with_transcript = [
    {**m, "has_transcript": bool(m.get("transcript_clean") or m.get("transcript_raw"))}
    for m in all_meetings
    if bool(m.get("transcript_clean") or m.get("transcript_raw"))
]

show_all = st.checkbox(
    "Mostrar todas as reuniões (inclusive as que já têm requisitos)",
    value=False,
    key="rb_show_all",
)
pending = all_with_transcript if show_all else [
    m for m in all_with_transcript
    if m["id"] not in existing_req_mids
]

if not pending:
    if show_all:
        st.warning("Nenhuma reunião com transcrição encontrada.")
    else:
        st.success("✅ Todas as reuniões do projeto já possuem requisitos na tabela.")
    st.stop()

col_a, col_b = st.columns(2)
col_a.metric("Total de reuniões com transcrição", len(all_with_transcript))
col_b.metric(
    "Sem requisitos na tabela" if not show_all else "Exibindo",
    len(pending),
)

st.dataframe(
    pd.DataFrame([{
        "Nº":     m.get("meeting_number") or "—",
        "Título": m.get("title") or "(sem título)",
        "Data":   str(m.get("meeting_date") or "—"),
        "Status": "⚠️ sem requisitos" if m["id"] not in existing_req_mids else "✅ já tem requisitos",
    } for m in pending]),
    use_container_width=True,
    hide_index=True,
)

# ── Seleção ───────────────────────────────────────────────────────────────────
all_labels = [
    f"#{m.get('meeting_number','?')} — {m.get('title','(sem título)')} ({m.get('meeting_date','—')})"
    for m in pending
]
selected_labels = st.multiselect(
    "Selecione as reuniões a processar",
    options=all_labels,
    default=[lbl for lbl, m in zip(all_labels, pending) if m["id"] not in existing_req_mids],
    key="rb_sel",
)
selected_ids = {pending[all_labels.index(lbl)]["id"] for lbl in selected_labels}
pending_sel  = [m for m in pending if m["id"] in selected_ids]

if not pending_sel:
    st.warning("Nenhuma reunião selecionada.")
    st.stop()

# ── 3. Execução ───────────────────────────────────────────────────────────────
st.markdown("## 3️⃣ Execução")

if not client_info:
    st.warning("👈 Insira a API key na sidebar antes de executar.")
    st.stop()

if st.button(
    f"▶️ Extrair requisitos para {len(pending_sel)} reunião(ões)",
    type="primary",
    key="rb_run",
):
    from core.knowledge_hub import KnowledgeHub
    from core.pipeline import run_pipeline

    pipeline_config = {
        "client_info":          client_info,
        "provider_cfg":         provider_cfg,
        "output_language":      output_language,
        "run_quality":          False,
        "run_bpmn":             False,
        "run_minutes":          False,
        "run_requirements":     True,
        "run_sbvr":             False,
        "run_bmm":              False,
        "run_synthesizer":      False,
        "n_bpmn_runs":          1,
        "bpmn_weights":         {"granularity": 5, "task_type": 5,
                                  "gateways": 5, "structural": 5},
        "use_langgraph":        False,
        "validation_threshold": 6.0,
        "max_bpmn_retries":     3,
    }

    progress_bar = st.progress(0.0)
    status_area  = st.empty()
    total        = len(pending_sel)
    results: list[dict] = []

    for i, meeting in enumerate(pending_sel):
        meeting_id = meeting["id"]
        title      = meeting.get("title") or "(sem título)"

        transcript = (
            meeting.get("transcript_clean")
            or meeting.get("transcript_raw")
            or ""
        )

        status_area.info(f"⏳ **{i + 1}/{total}** — `{title}`")

        try:
            hub = KnowledgeHub.new()
            hub.set_transcript(transcript)
            hub.meta.llm_provider = selected_provider

            hub = run_pipeline(hub, pipeline_config, lambda *_: None)

            if hub.requirements.ready and hub.requirements.requirements:
                n_saved = save_requirements_from_hub(meeting_id, project_id, hub)
                results.append({
                    "Nº":          meeting.get("meeting_number") or "—",
                    "Título":      title,
                    "Status":      "✅ Requisitos salvos",
                    "Requisitos":  str(n_saved),
                })
            else:
                results.append({
                    "Nº":          meeting.get("meeting_number") or "—",
                    "Título":      title,
                    "Status":      "⚠️ Nenhum requisito extraído",
                    "Requisitos":  "0",
                })
        except Exception as exc:
            results.append({
                "Nº":          meeting.get("meeting_number") or "—",
                "Título":      title,
                "Status":      f"❌ Erro: {exc}",
                "Requisitos":  "—",
            })

        progress_bar.progress((i + 1) / total)

    status_area.empty()
    progress_bar.progress(1.0)

    n_ok  = sum(1 for r in results if r["Status"].startswith("✅"))
    n_err = sum(1 for r in results if r["Status"].startswith("❌"))
    n_empty = sum(1 for r in results if r["Status"].startswith("⚠️"))

    if n_ok:
        st.success(f"✅ {n_ok} reunião(ões) processadas com sucesso.")
    if n_empty:
        st.warning(f"⚠️ {n_empty} reunião(ões) sem requisitos extraídos.")
    if n_err:
        st.error(f"❌ {n_err} erro(s) durante o processamento.")

    st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
