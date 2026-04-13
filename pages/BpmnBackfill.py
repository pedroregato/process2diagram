# pages/BpmnBackfill.py
# ─────────────────────────────────────────────────────────────────────────────
# BPMN Backfill — gera diagramas BPMN para reuniões já persistidas no Supabase
# que ainda não possuem versão BPMN registrada.
#
# Fluxo:
#   1. Seleciona o projeto
#   2. Lista todas as reuniões sem BPMN (com ou sem transcrição armazenada)
#   3. Para reuniões COM transcrição no banco: processa direto
#   4. Para reuniões SEM transcrição: permite upload do arquivo original
#   5. Executa apenas AgentBPMN; salva bpmn_processes + bpmn_versions
#      vinculados ao meeting_id existente (sem recriar reuniões)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import io
import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pandas as pd
import streamlit as st

from ui.auth_gate import apply_auth_gate
from modules.supabase_client import supabase_configured
from modules.config import AVAILABLE_PROVIDERS
from modules.session_security import render_api_key_readonly
from modules.ingest import load_transcript
from core.project_store import (
    list_projects,
    list_meetings_without_bpmn,
    save_transcript,
    save_bpmn_from_hub,
    bpmn_tables_exist,
)

apply_auth_gate()

# ── Sidebar: LLM provider + API key ──────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Configuração LLM")
    selected_provider = st.selectbox(
        "Provedor",
        list(AVAILABLE_PROVIDERS.keys()),
        key="bf_provider",
    )
    provider_cfg = AVAILABLE_PROVIDERS[selected_provider]
    api_key = render_api_key_readonly(selected_provider)
    output_language = st.selectbox(
        "Idioma de saída",
        ["Auto-detect", "Portuguese (BR)", "English"],
        key="bf_lang",
    )
    st.markdown("---")
    n_runs = st.selectbox(
        "Passes BPMN", [1, 3, 5], key="bf_runs",
        help="Número de gerações por reunião — melhor qualidade com mais passes.",
    )

client_info = {"api_key": api_key} if api_key else None

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 📐 BPMN Backfill")
st.caption(
    "Gera diagramas BPMN para reuniões já salvas no banco de dados que ainda "
    "não possuem versão BPMN registrada. Não cria novas reuniões nem duplica dados."
)

if not supabase_configured():
    st.error("⚙️ Supabase não configurado.")
    st.stop()

# ── Pré-requisito: tabelas BPMN devem existir ─────────────────────────────────
if not bpmn_tables_exist():
    st.error("⚠️ Tabelas BPMN ainda não foram criadas no banco de dados.")
    st.info("Execute `setup/supabase_schema_bpmn_processes.sql` no SQL Editor do Supabase e recarregue a página (F5).")
    st.stop()

# ── 1. Projeto ────────────────────────────────────────────────────────────────
st.markdown("## 1️⃣ Projeto")
projects = list_projects()
proj_map = {p["name"]: p for p in projects}
sel_proj = st.selectbox("Projeto", list(proj_map.keys()), key="bf_proj")

if not sel_proj:
    st.stop()

project_id = proj_map[sel_proj]["id"]

# ── 2. Reuniões sem BPMN ──────────────────────────────────────────────────────
st.markdown("## 2️⃣ Reuniões sem BPMN")
pending = list_meetings_without_bpmn(project_id)

if not pending:
    st.success("✅ Todas as reuniões do projeto já possuem versão BPMN registrada.")
    st.stop()

n_with    = sum(1 for m in pending if m.get("has_transcript"))
n_without = len(pending) - n_with

col_a, col_b = st.columns(2)
col_a.metric("📄 Com transcrição no banco", n_with, help="Processamento automático")
col_b.metric("⚠️ Sem transcrição no banco", n_without,
             help="Necessário fazer upload do arquivo original")

if n_without:
    st.warning(
        f"**{n_without} reunião(ões)** não têm transcrição armazenada — "
        "provavelmente o `save_meeting_artifacts` falhou por payload muito grande. "
        "Faça o upload do arquivo original de cada uma na seção abaixo."
    )

# Tabela de preview
preview_rows = []
for m in pending:
    preview_rows.append({
        "Nº":          m.get("meeting_number") or "—",
        "Título":      m.get("title") or "(sem título)",
        "Data":        str(m.get("meeting_date") or "—"),
        "Transcrição": "✅ no banco" if m.get("has_transcript") else "⚠️ ausente — upload necessário",
        "ID":          m["id"],
    })

st.dataframe(
    pd.DataFrame(preview_rows)[["Nº", "Título", "Data", "Transcrição"]],
    use_container_width=True,
    hide_index=True,
)

# ── Upload para reuniões sem transcrição ──────────────────────────────────────
# Mapeia meeting_id → conteúdo de texto (via upload)
uploaded_transcripts: dict[str, str] = {}

if n_without:
    st.markdown("### 📤 Upload de transcrições ausentes")
    st.caption("Faça o upload de cada arquivo — o sistema vincula ao meeting_id correspondente.")

    for m in pending:
        if m.get("has_transcript"):
            continue
        num   = m.get("meeting_number") or "?"
        title = m.get("title") or "(sem título)"
        uf = st.file_uploader(
            f"Reunião {num} — {title}",
            type=["txt", "docx", "pdf"],
            key=f"bf_upload_{m['id']}",
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
    if m.get("has_transcript") or m["id"] in uploaded_transcripts
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
    key="bf_sel",
)
selected_ids = {processable[all_labels.index(lbl)]["id"] for lbl in selected_labels}
pending_sel  = [m for m in processable if m["id"] in selected_ids]

if not pending_sel:
    st.warning("Nenhuma reunião selecionada.")
    st.stop()

# ── 3. Execução ───────────────────────────────────────────────────────────────
st.markdown("## 3️⃣ Execução")

if not client_info:
    st.warning("👈 Insira a API key na sidebar antes de executar.")
    st.stop()

if st.button(
    f"▶️ Gerar BPMN para {len(pending_sel)} reunião(ões)",
    type="primary",
    key="bf_run",
):
    from core.knowledge_hub import KnowledgeHub
    from core.pipeline import run_pipeline

    pipeline_config = {
        "client_info":          client_info,
        "provider_cfg":         provider_cfg,
        "output_language":      output_language,
        "run_quality":          False,
        "run_bpmn":             True,
        "run_minutes":          False,
        "run_requirements":     False,
        "run_sbvr":             False,
        "run_bmm":              False,
        "run_synthesizer":      False,
        "n_bpmn_runs":          n_runs,
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

        # Fonte da transcrição: banco ou upload
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

            if hub.bpmn.ready:
                # Salva transcrição na reunião (backfill para meetings com transcript nulo)
                save_transcript(meeting_id, hub)

                process_id = save_bpmn_from_hub(
                    meeting_id=meeting_id,
                    project_id=project_id,
                    hub=hub,
                )
                proc_name   = hub.bpmn.name or "—"
                status_icon = "✅" if process_id else "⚠️ BPMN gerado, falha ao salvar"
                results.append({"Reunião": title, "Status": status_icon, "Processo": proc_name})
            else:
                results.append({"Reunião": title, "Status": "❌ AgentBPMN sem resultado", "Processo": ""})

        except Exception as exc:
            results.append({"Reunião": title, "Status": f"❌ {str(exc)[:80]}", "Processo": ""})

        progress_bar.progress((i + 1) / total)

    status_area.empty()
    progress_bar.progress(1.0)
    st.session_state["bf_results"] = results

# ── 4. Resultados ─────────────────────────────────────────────────────────────
if st.session_state.get("bf_results"):
    results = st.session_state["bf_results"]
    st.markdown("---")
    st.markdown("## 📊 Resultados")

    ok   = sum(1 for r in results if r["Status"].startswith("✅"))
    fail = len(results) - ok

    c1, c2 = st.columns(2)
    c1.metric("✅ Gerados com sucesso", ok)
    c2.metric("❌ Erros", fail)

    st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)

    if ok:
        st.success(
            "💡 Processos BPMN registrados. "
            "Acesse **ReqTracker → aba 📐 Processos BPMN** para visualizar os diagramas."
        )
