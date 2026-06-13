# pages/IbisBackfill.py
# ─────────────────────────────────────────────────────────────────────────────
# IBIS Backfill — extrai e persiste mapas argumentativos IBIS (argumentation_json)
# para reuniões processadas antes do AgentArgumentation existir no pipeline.
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
from core.project_store import list_projects, save_meeting_artifacts

apply_auth_gate()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuração LLM")
    selected_provider = st.selectbox(
        "Provedor",
        list(AVAILABLE_PROVIDERS.keys()),
        key="ibis_bf_provider",
    )
    provider_cfg = AVAILABLE_PROVIDERS[selected_provider]
    api_key = render_api_key_readonly(selected_provider)
    output_language = st.selectbox(
        "Idioma de saída",
        ["Auto-detect", "Portuguese (BR)", "English"],
        key="ibis_bf_lang",
    )

client_info = {"api_key": api_key} if api_key else None

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 🗺️ IBIS Backfill")
st.caption(
    "Extrai e persiste mapas argumentativos IBIS para reuniões processadas "
    "antes do AgentArgumentation existir no pipeline."
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
sel_proj     = st.selectbox("Contexto", list(proj_map.keys()), index=_default_idx, key="ibis_bf_proj")
if not sel_proj:
    st.stop()

project_id = proj_map[sel_proj]["id"]

# ── 2. Reuniões ───────────────────────────────────────────────────────────────
st.markdown("## 2️⃣ Reuniões a processar")

try:
    all_meetings = (
        db.table("meetings")
        .select(
            "id, meeting_number, title, meeting_date, "
            "transcript_clean, transcript_raw, argumentation_json"
        )
        .eq("project_id", project_id)
        .order("meeting_number")
        .execute().data or []
    )
except Exception as e:
    st.error(f"Erro ao carregar reuniões: {e}")
    st.stop()

all_with_transcript = [
    m for m in all_meetings
    if m.get("transcript_clean") or m.get("transcript_raw")
]

show_all = st.checkbox(
    "Mostrar todas as reuniões (inclusive as que já têm IBIS)",
    value=False,
    key="ibis_bf_show_all",
)

def _missing(m: dict) -> bool:
    return not m.get("argumentation_json")

pending = all_with_transcript if show_all else [m for m in all_with_transcript if _missing(m)]

if not pending:
    if show_all:
        st.warning("Nenhuma reunião com transcrição encontrada.")
    else:
        st.success("✅ Todas as reuniões do projeto já possuem IBIS.")
    st.stop()

col_a, col_b = st.columns(2)
col_a.metric("Reuniões com transcrição", len(all_with_transcript))
col_b.metric("Sem IBIS" if not show_all else "Exibindo", len(pending))

def _status(m: dict) -> str:
    return "✅ IBIS" if m.get("argumentation_json") else "❌ sem IBIS"

st.dataframe(
    pd.DataFrame([{
        "Nº":     m.get("meeting_number") or "—",
        "Título": m.get("title") or "(sem título)",
        "Data":   str(m.get("meeting_date") or "—"),
        "Status": _status(m),
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
    default=[lbl for lbl, m in zip(all_labels, pending) if _missing(m)],
    key="ibis_bf_sel",
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
    f"▶️ Extrair IBIS para {len(pending_sel)} reunião(ões)",
    type="primary",
    key="ibis_bf_run",
):
    from core.knowledge_hub import KnowledgeHub
    from agents.agent_argumentation import AgentArgumentation

    agent_ibis = AgentArgumentation(client_info=client_info, provider_cfg=provider_cfg)

    progress_bar = st.progress(0.0)
    status_area  = st.empty()
    total        = len(pending_sel)
    results: list[dict] = []

    for i, meeting in enumerate(pending_sel):
        meeting_id = meeting["id"]
        title      = meeting.get("title") or "(sem título)"
        transcript = meeting.get("transcript_clean") or meeting.get("transcript_raw") or ""

        status_area.info(f"⏳ **{i + 1}/{total}** — `{title}`")

        try:
            hub = KnowledgeHub.new()
            hub.set_transcript(transcript)
            hub.meta.llm_provider = selected_provider

            hub = agent_ibis.run(hub, output_language)
            n_questions = len(getattr(hub.argumentation, "questions", []))

            ok = save_meeting_artifacts(meeting_id, hub)

            results.append({
                "Nº":          meeting.get("meeting_number") or "—",
                "Título":      title,
                "Status":      "✅ Salvo" if ok else "⚠️ Extração ok mas save falhou",
                "Questões IBIS": n_questions,
            })
        except Exception as exc:
            results.append({
                "Nº":            meeting.get("meeting_number") or "—",
                "Título":        title,
                "Status":        f"❌ Erro: {exc}",
                "Questões IBIS": "—",
            })

        progress_bar.progress((i + 1) / total)

    status_area.empty()
    progress_bar.progress(1.0)

    n_ok   = sum(1 for r in results if r["Status"].startswith("✅"))
    n_warn = sum(1 for r in results if r["Status"].startswith("⚠️"))
    n_err  = sum(1 for r in results if r["Status"].startswith("❌"))

    if n_ok:
        st.success(f"✅ {n_ok} reunião(ões) processadas com sucesso.")
    if n_warn:
        st.warning(f"⚠️ {n_warn} reunião(ões) com extração ok mas falha no save.")
    if n_err:
        st.error(f"❌ {n_err} erro(s) durante o processamento.")

    st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
