# pages/PiiBackfill.py
# ─────────────────────────────────────────────────────────────────────────────
# PII Backfill — classifica PII (categoria + contagem + risk_level, via
# modules/compliance/detector.py::detect_pii()) para reuniões já processadas
# ANTES da feature existir, ou carregadas por qualquer caminho que não passe
# por pages/Pipeline.py (ver melhorias/parciais/classificador-pii-transcricoes.md).
# Não roda nenhum agente LLM, não reprocessa a reunião — só lê a transcrição
# já armazenada e persiste em `meetings.pii_risk_level`/`pii_categories`.
#
# Fluxo:
#   1. Seleciona o projeto
#   2. Lista reuniões ainda sem classificação (pii_risk_level IS NULL)
#   3. Executa o backfill em lote via core.pipeline.backfill_meeting_pii()
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
from core.project_store import list_projects, list_meetings_pii_summary
from core.pipeline import backfill_meeting_pii

apply_auth_gate()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 🔐 PII — Backfill de Classificação")
st.caption(
    "Classifica dados sensíveis (CPF, CNPJ, e-mail, telefone, valor monetário, nome de pessoa) "
    "em reuniões **já processadas** que ainda não têm essa classificação — sem rodar nenhum "
    "agente LLM, sem reprocessar a reunião. Útil para reuniões processadas antes desta feature "
    "existir. Depois de rodar, os resultados aparecem no badge (🟢🟡🔴) e no card de detalhe da "
    "aba **Artefatos → Reuniões**."
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
sel_proj     = st.selectbox("Contexto", list(proj_map.keys()), index=_default_idx, key="piib_proj")
if not sel_proj:
    st.stop()

project_id = proj_map[sel_proj]["id"]

# ── 2. Reuniões ainda sem classificação ────────────────────────────────────────
st.markdown("## 2️⃣ Reuniões ainda não classificadas")

with st.spinner("Verificando reuniões pendentes..."):
    all_pii = list_meetings_pii_summary(project_id)
    eligible = [p for p in all_pii if p.get("pii_risk_level") is None]

if not eligible:
    st.success(
        "✅ Todas as reuniões deste projeto já têm classificação de PII "
        "(ou não há reuniões no projeto)."
    )
    st.stop()

st.metric("📋 Reuniões pendentes de classificação", len(eligible))

st.dataframe(
    pd.DataFrame([{
        "Nº":     m.get("meeting_number") or "—",
        "Título": m.get("title") or "(sem título)",
        "Data":   m.get("meeting_date") or "—",
    } for m in eligible]),
    use_container_width=True,
    hide_index=True,
)

# ── Seleção das reuniões a processar ─────────────────────────────────────────
st.markdown("---")
all_labels = [
    f"#{m.get('meeting_number','?')} — {m.get('title','(sem título)')}"
    for m in eligible
]
selected_labels = st.multiselect(
    "Selecione as reuniões a processar",
    options=all_labels,
    default=all_labels,
    key="piib_sel",
)
selected_ids = {eligible[all_labels.index(lbl)]["id"] for lbl in selected_labels}
meeting_sel  = [m for m in eligible if m["id"] in selected_ids]

if not meeting_sel:
    st.warning("Nenhuma reunião selecionada.")
    st.stop()

# ── 3. Execução ───────────────────────────────────────────────────────────────
st.markdown("## 3️⃣ Execução")

if st.button(f"▶️ Classificar {len(meeting_sel)} reunião(ões)", type="primary", key="piib_run"):
    progress_bar = st.progress(0.0)
    status_area  = st.empty()

    def _on_progress(i: int, total: int, row: dict) -> None:
        title = row.get("title") or "(sem título)"
        status_area.info(f"⏳ **{i + 1}/{total}** — `{title}`")
        progress_bar.progress((i + 1) / total)

    results = backfill_meeting_pii(
        project_id,
        meeting_ids=[m["id"] for m in meeting_sel],
        progress_callback=_on_progress,
    )

    status_area.empty()
    st.markdown("### Resultado")

    _BADGE = {"low": "🟢", "medium": "🟡", "high": "🔴"}

    st.dataframe(
        pd.DataFrame([{
            "Nº":     r.get("meeting_number") or "—",
            "Título": r.get("title") or "(sem título)",
            "Status": (
                f"❌ Erro: {r['error']}" if "error" in r
                else f"⏭️ {r['skipped']}" if "skipped" in r
                else f"{_BADGE.get(r.get('risk_level'), '⚪')} {r.get('total', 0)} sensível(is)"
            ),
        } for r in results]),
        use_container_width=True,
        hide_index=True,
    )

    n_ok      = sum(1 for r in results if r.get("saved"))
    n_err     = sum(1 for r in results if "error" in r)
    n_skipped = sum(1 for r in results if "skipped" in r)
    if n_ok:
        st.success(f"✅ {n_ok} reunião(ões) classificada(s).")
    if n_skipped:
        st.info(f"⏭️ {n_skipped} reunião(ões) sem transcrição salva, puladas.")
    if n_err:
        st.error(f"❌ {n_err} reunião(ões) com erro — ver detalhe na tabela acima.")
