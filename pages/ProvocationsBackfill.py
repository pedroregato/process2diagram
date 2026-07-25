# pages/ProvocationsBackfill.py
# ─────────────────────────────────────────────────────────────────────────────
# Provocações Backfill (PC204) — re-deriva provocações kind="contradiction" a
# partir de contradições já detectadas em kh_contradictions/AgentContradictionDetector,
# para reuniões já processadas SEM o toggle "🎭 Gerar Provocações" ligado
# (desligado por padrão). Não roda nenhum agente LLM, não reprocessa a reunião —
# só chama AgentProvocations.bridge_contradictions() (PC200, determinístico) e
# persiste o que ainda não tinha sido salvo.
#
# Fluxo:
#   1. Seleciona o projeto
#   2. Lista reuniões com contradições ainda não bridged (chamando o próprio
#      bridge_contradictions() por reunião — mesma função usada na execução,
#      a prévia nunca diverge do resultado real)
#   3. Executa o backfill em lote via core.pipeline.backfill_contradiction_provocations()
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
from core.project_store import list_projects, list_meetings, list_provocations_by_project
from agents.agent_provocations import AgentProvocations
from core.pipeline import backfill_contradiction_provocations

apply_auth_gate()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 🎭 Provocações — Backfill de Contradições")
st.caption(
    "Re-deriva provocações **kind=\"contradiction\"** a partir de contradições já detectadas "
    "(`kh_contradictions`/`AgentContradictionDetector`) para reuniões já processadas — sem rodar "
    "nenhum agente LLM, sem reprocessar a reunião. Útil para reuniões processadas antes de "
    "\"🎭 Gerar Provocações\" estar ligado (desligado por padrão). Não cobre `absence`/`asymmetry`/"
    "`premise` — essas exigem uma chamada real ao LLM sobre a transcrição, não têm backfill barato."
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
sel_proj     = st.selectbox("Contexto", list(proj_map.keys()), index=_default_idx, key="pb_proj")
if not sel_proj:
    st.stop()

project_id = proj_map[sel_proj]["id"]

# ── 2. Reuniões com contradições pendentes de ponte ───────────────────────────
st.markdown("## 2️⃣ Reuniões com contradições pendentes")

meetings = list_meetings(project_id)
if not meetings:
    st.warning("Nenhuma reunião encontrada nesse projeto.")
    st.stop()

with st.spinner("Verificando contradições pendentes..."):
    already_bridged_by_meeting: dict = {}
    for p in list_provocations_by_project(project_id):
        if p.get("kind") == "contradiction":
            already_bridged_by_meeting.setdefault(p.get("meeting_id"), set()).add(
                (p.get("grounding") or {}).get("source_contradiction_id")
            )

    eligible = []
    for m in meetings:
        try:
            bridged = AgentProvocations.bridge_contradictions(project_id, m["id"])
        except Exception:
            bridged = []
        already = already_bridged_by_meeting.get(m["id"], set())
        n_pending = sum(
            1 for b in bridged
            if (b.contradiction_ref or {}).get("source_contradiction_id") not in already
        )
        if n_pending:
            eligible.append({**m, "_pending": n_pending})

if not eligible:
    st.success(
        "✅ Nenhuma contradição pendente de ponte — ou já foram todas processadas, ou não há "
        "contradições cross-reunião detectadas neste projeto (confira em Knowledge Hub → "
        "⚠️ Contradições)."
    )
    st.stop()

st.metric("📋 Reuniões com contradição pendente", len(eligible))

st.dataframe(
    pd.DataFrame([{
        "Nº":                      m.get("meeting_number") or "—",
        "Título":                  m.get("title") or "(sem título)",
        "Data":                    str(m.get("meeting_date") or "—"),
        "Contradições pendentes":  m["_pending"],
    } for m in eligible]),
    use_container_width=True,
    hide_index=True,
)

# ── Seleção das reuniões a processar ─────────────────────────────────────────
st.markdown("---")
all_labels = [
    f"#{m.get('meeting_number','?')} — {m.get('title','(sem título)')} — {m['_pending']} pendente(s)"
    for m in eligible
]
selected_labels = st.multiselect(
    "Selecione as reuniões a processar",
    options=all_labels,
    default=all_labels,
    key="pb_sel",
)
selected_ids = {eligible[all_labels.index(lbl)]["id"] for lbl in selected_labels}
meeting_sel  = [m for m in eligible if m["id"] in selected_ids]

if not meeting_sel:
    st.warning("Nenhuma reunião selecionada.")
    st.stop()

# ── 3. Execução ───────────────────────────────────────────────────────────────
st.markdown("## 3️⃣ Execução")

if st.button(f"▶️ Rodar backfill em {len(meeting_sel)} reunião(ões)", type="primary", key="pb_run"):
    progress_bar = st.progress(0.0)
    status_area  = st.empty()

    def _on_progress(i: int, total: int, row: dict) -> None:
        title = row.get("title") or "(sem título)"
        status_area.info(f"⏳ **{i + 1}/{total}** — `{title}`")
        progress_bar.progress((i + 1) / total)

    results = backfill_contradiction_provocations(
        project_id,
        meeting_ids=[m["id"] for m in meeting_sel],
        progress_callback=_on_progress,
    )

    status_area.empty()
    st.markdown("### Resultado")
    st.dataframe(
        pd.DataFrame([{
            "Nº":                    r.get("meeting_number") or "—",
            "Título":                r.get("title") or "(sem título)",
            "Status": (
                f"❌ Erro: {r['error']}" if "error" in r
                else f"✅ {r.get('saved', 0)} nova(s)" if r.get("saved")
                else "— nada novo (já em dia)"
            ),
            "Candidatas":            r.get("candidates", "—"),
            "Puladas (duplicata)":   r.get("skipped_dup", "—"),
        } for r in results]),
        use_container_width=True,
        hide_index=True,
    )

    n_ok      = sum(1 for r in results if r.get("saved"))
    n_err     = sum(1 for r in results if "error" in r)
    n_nothing = len(results) - n_ok - n_err
    if n_ok:
        st.success(f"✅ {n_ok} reunião(ões) ganharam provocação(ões) nova(s).")
    if n_nothing:
        st.info(f"ℹ️ {n_nothing} reunião(ões) sem novidade (já estavam com a ponte em dia).")
    if n_err:
        st.warning(f"⚠️ {n_err} reunião(ões) com erro — verifique os logs.")
