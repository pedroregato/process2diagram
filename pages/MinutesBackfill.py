# pages/MinutesBackfill.py
# ─────────────────────────────────────────────────────────────────────────────
# Minutes Backfill — gera atas de reunião para meetings já persistidas no
# Supabase que ainda não possuem minutes_md registrado.
#
# Fluxo:
#   1. Seleciona o projeto
#   2. Lista todas as reuniões sem ata (com ou sem transcrição armazenada)
#   3. Para reuniões COM transcrição no banco: processa direto
#   4. Para reuniões SEM transcrição: permite upload do arquivo original
#   5. Executa apenas AgentMinutes; salva minutes_md no registro existente
#      (sem recriar reuniões)
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
from modules.ingest import load_transcript
from core.project_store import list_projects

apply_auth_gate()

# ── Sidebar: LLM provider + API key ──────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuração LLM")
    selected_provider = st.selectbox(
        "Provedor",
        list(AVAILABLE_PROVIDERS.keys()),
        key="mb_provider",
    )
    provider_cfg = AVAILABLE_PROVIDERS[selected_provider]
    api_key = st.text_input(
        provider_cfg.get("api_key_label", "API Key"),
        type="password",
        key="mb_api_key",
        help=provider_cfg.get("api_key_help", ""),
    )
    output_language = st.selectbox(
        "Idioma de saída",
        ["Auto-detect", "Portuguese (BR)", "English"],
        key="mb_lang",
    )

client_info = {"api_key": api_key} if api_key else None

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 📝 Minutes Backfill")
st.caption(
    "Gera atas de reunião (AgentMinutes) para reuniões já salvas no banco de dados "
    "que ainda não possuem ata registrada. Não cria novas reuniões nem duplica dados."
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

proj_map = {p["name"]: p for p in projects}
sel_proj = st.selectbox("Projeto", list(proj_map.keys()), key="mb_proj")
if not sel_proj:
    st.stop()

project_id = proj_map[sel_proj]["id"]

# ── 2. Reuniões sem ata ───────────────────────────────────────────────────────
st.markdown("## 2️⃣ Reuniões sem ata")

try:
    all_meetings = db.table("meetings") \
        .select("id, meeting_number, title, meeting_date, transcript_clean, transcript_raw, minutes_md") \
        .eq("project_id", project_id) \
        .order("meeting_number") \
        .execute().data or []
except Exception as e:
    st.error(f"Erro ao carregar reuniões: {e}")
    st.stop()

pending = [
    {**m, "has_transcript": bool(m.get("transcript_clean") or m.get("transcript_raw"))}
    for m in all_meetings
    if not (m.get("minutes_md") or "").strip()
]

if not pending:
    st.success("✅ Todas as reuniões do projeto já possuem ata registrada.")
    st.stop()

n_with    = sum(1 for m in pending if m["has_transcript"])
n_without = len(pending) - n_with

col_a, col_b, col_c = st.columns(3)
col_a.metric("📋 Total sem ata",          len(pending))
col_b.metric("📄 Com transcrição no banco", n_with,    help="Processamento automático")
col_c.metric("⚠️ Sem transcrição",          n_without, help="Upload necessário")

if n_without:
    st.warning(
        f"**{n_without} reunião(ões)** não têm transcrição armazenada. "
        "Faça o upload do arquivo original na seção abaixo."
    )

# Preview table
st.dataframe(
    pd.DataFrame([{
        "Nº":          m.get("meeting_number") or "—",
        "Título":      m.get("title") or "(sem título)",
        "Data":        str(m.get("meeting_date") or "—"),
        "Transcrição": "✅ no banco" if m["has_transcript"] else "⚠️ ausente — upload necessário",
    } for m in pending]),
    use_container_width=True,
    hide_index=True,
)

# ── Upload para reuniões sem transcrição ──────────────────────────────────────
uploaded_transcripts: dict[str, str] = {}

if n_without:
    st.markdown("### 📤 Upload de transcrições ausentes")
    st.caption("Faça o upload de cada arquivo — o sistema vincula ao meeting_id correspondente.")

    for m in pending:
        if m["has_transcript"]:
            continue
        num   = m.get("meeting_number") or "?"
        title = m.get("title") or "(sem título)"
        uf = st.file_uploader(
            f"Reunião {num} — {title}",
            type=["txt", "docx", "pdf"],
            key=f"mb_upload_{m['id']}",
        )
        if uf:
            try:
                content = load_transcript(uf)
                uploaded_transcripts[m["id"]] = content
                st.caption(f"   ✅ `{uf.name}` carregado ({len(content):,} chars)")
            except Exception as exc:
                st.error(f"   ❌ Erro ao ler {uf.name}: {exc}")

# ── Seleção das reuniões a processar ─────────────────────────────────────────
st.markdown("---")
processable = [
    m for m in pending
    if m["has_transcript"] or m["id"] in uploaded_transcripts
]

if not processable:
    if n_without and not uploaded_transcripts:
        st.info("👆 Faça o upload das transcrições acima para habilitar o processamento.")
    st.stop()

all_labels = [
    f"#{m.get('meeting_number','?')} — {m.get('title','(sem título)')} ({m.get('meeting_date','—')})"
    for m in processable
]
selected_labels = st.multiselect(
    "Selecione as reuniões a processar",
    options=all_labels,
    default=all_labels,
    key="mb_sel",
)
selected_ids  = {processable[all_labels.index(lbl)]["id"] for lbl in selected_labels}
pending_sel   = [m for m in processable if m["id"] in selected_ids]

if not pending_sel:
    st.warning("Nenhuma reunião selecionada.")
    st.stop()

# ── 3. Execução ───────────────────────────────────────────────────────────────
st.markdown("## 3️⃣ Execução")

if not client_info:
    st.warning("👈 Insira a API key na sidebar antes de executar.")
    st.stop()

if st.button(
    f"▶️ Gerar ata para {len(pending_sel)} reunião(ões)",
    type="primary",
    key="mb_run",
):
    from core.knowledge_hub import KnowledgeHub
    from core.pipeline import run_pipeline

    pipeline_config = {
        "client_info":          client_info,
        "provider_cfg":         provider_cfg,
        "output_language":      output_language,
        "run_quality":          False,
        "run_bpmn":             False,
        "run_minutes":          True,
        "run_requirements":     False,
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
            uploaded_transcripts.get(meeting_id)
            or meeting.get("transcript_clean")
            or meeting.get("transcript_raw")
            or ""
        )

        status_area.info(f"⏳ **{i + 1}/{total}** — `{title}`")

        try:
            hub = KnowledgeHub.new()
            hub.set_transcript(transcript)
            hub.meta.llm_provider = selected_provider

            hub = run_pipeline(hub, pipeline_config, lambda *_: None)

            if hub.minutes.ready:
                minutes_md = hub.minutes.full_text or ""
                db.table("meetings") \
                    .update({"minutes_md": minutes_md}) \
                    .eq("id", meeting_id) \
                    .execute()
                results.append({
                    "Nº":      meeting.get("meeting_number") or "—",
                    "Título":  title,
                    "Status":  "✅ Ata gerada e salva",
                    "Chars":   f"{len(minutes_md):,}",
                })
            else:
                results.append({
                    "Nº":      meeting.get("meeting_number") or "—",
                    "Título":  title,
                    "Status":  "⚠️ AgentMinutes não retornou resultado",
                    "Chars":   "0",
                })

        except Exception as exc:
            results.append({
                "Nº":      meeting.get("meeting_number") or "—",
                "Título":  title,
                "Status":  f"❌ Erro: {exc}",
                "Chars":   "—",
            })

        progress_bar.progress((i + 1) / total)

    status_area.empty()
    st.markdown("### Resultado")
    st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)

    n_ok  = sum(1 for r in results if r["Status"].startswith("✅"))
    n_err = len(results) - n_ok
    if n_ok:
        st.success(f"✅ {n_ok} ata(s) gerada(s) e salva(s) no banco.")
    if n_err:
        st.warning(f"⚠️ {n_err} reunião(ões) com erro — verifique a API key e tente novamente.")
