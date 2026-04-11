# pages/BpmnBackfill.py
# ─────────────────────────────────────────────────────────────────────────────
# BPMN Backfill — gera diagramas BPMN para reuniões já persistidas no Supabase
# que ainda não possuem versão BPMN registrada.
#
# Fluxo:
#   1. Seleciona o projeto
#   2. Lista reuniões sem BPMN (possuem transcrição no banco)
#   3. Usuário seleciona quais processar
#   4. Executa apenas AgentBPMN (sem recriar a reunião nem duplicar dados)
#   5. Salva bpmn_processes + bpmn_versions vinculados ao meeting_id existente
# ─────────────────────────────────────────────────────────────────────────────

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
    list_meetings_without_bpmn,
    save_bpmn_from_hub,
    bpmn_tables_exist,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BPMN Backfill — Process2Diagram",
    page_icon="📐",
    layout="wide",
    initial_sidebar_state="expanded",
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
    api_key = st.text_input(
        provider_cfg.get("api_key_label", "API Key"),
        type="password",
        key="bf_api_key",
        help=provider_cfg.get("api_key_help", ""),
    )
    output_language = st.selectbox(
        "Idioma de saída",
        ["Auto-detect", "Portuguese (BR)", "English"],
        key="bf_lang",
    )
    st.markdown("---")
    n_runs = st.selectbox("Passes BPMN", [1, 3, 5], key="bf_runs",
                          help="Número de gerações por reunião — melhor qualidade com mais passes.")

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
    st.markdown(
        "Execute o script abaixo no **SQL Editor do Supabase Dashboard** e recarregue a página:"
    )
    st.code("setup/supabase_schema_bpmn_processes.sql", language="sql")
    st.markdown("""
```sql
-- Conteúdo resumido (use o arquivo completo em setup/):
CREATE TABLE IF NOT EXISTS bpmn_processes ( ... );
CREATE TABLE IF NOT EXISTS bpmn_versions  ( ... );
```
""")
    st.info("Após executar o SQL, recarregue esta página (F5).")
    st.stop()

# ── 1. Projeto ────────────────────────────────────────────────────────────────
st.markdown("## 1️⃣ Projeto")
projects  = list_projects()
proj_map  = {p["name"]: p for p in projects}
sel_proj  = st.selectbox("Projeto", list(proj_map.keys()), key="bf_proj")

if not sel_proj:
    st.stop()

project_id = proj_map[sel_proj]["id"]

# ── 2. Reuniões sem BPMN ──────────────────────────────────────────────────────
st.markdown("## 2️⃣ Reuniões sem BPMN")
pending = list_meetings_without_bpmn(project_id)

if not pending:
    st.success("✅ Todas as reuniões do projeto já possuem versão BPMN registrada.")
    st.stop()

st.info(f"**{len(pending)}** reunião(ões) sem BPMN encontrada(s).")

# Tabela de seleção
import pandas as pd

rows = []
for m in pending:
    rows.append({
        "Nº":    m.get("meeting_number") or "—",
        "Título": m.get("title") or "(sem título)",
        "Data":   str(m.get("meeting_date") or "—"),
        "ID":     m["id"],
    })

df = pd.DataFrame(rows)
st.dataframe(df[["Nº", "Título", "Data"]], use_container_width=True, hide_index=True)

# Seleção das reuniões a processar
all_titles = [f"#{r['Nº']} — {r['Título']} ({r['Data']})" for r in rows]
selected   = st.multiselect(
    "Selecione as reuniões a processar",
    options=all_titles,
    default=all_titles,
    key="bf_sel",
)

selected_ids = [rows[all_titles.index(t)]["ID"] for t in selected]
pending_sel  = [m for m in pending if m["id"] in selected_ids]

if not pending_sel:
    st.warning("Nenhuma reunião selecionada.")
    st.stop()

st.markdown("---")

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
    total = len(pending_sel)
    results: list[dict] = []

    for i, meeting in enumerate(pending_sel):
        meeting_id = meeting["id"]
        title      = meeting.get("title") or "(sem título)"
        transcript = meeting.get("transcript_clean") or meeting.get("transcript_raw") or ""

        status_area.info(f"⏳ **{i + 1}/{total}** — `{title}`")

        if not transcript.strip():
            results.append({"Reunião": title, "Status": "⚠️ sem transcrição", "Processo": ""})
            progress_bar.progress((i + 1) / total)
            continue

        try:
            hub = KnowledgeHub.new()
            hub.set_transcript(transcript)
            hub.meta.llm_provider = selected_provider

            hub = run_pipeline(hub, pipeline_config, lambda *_: None)

            if hub.bpmn.ready:
                process_id = save_bpmn_from_hub(
                    meeting_id=meeting_id,
                    project_id=project_id,
                    hub=hub,
                )
                proc_name = hub.bpmn.name or "—"
                status_icon = "✅" if process_id else "⚠️ BPMN gerado, falha ao salvar"
                results.append({
                    "Reunião":  title,
                    "Status":   status_icon,
                    "Processo": proc_name,
                })
            else:
                results.append({"Reunião": title, "Status": "❌ AgentBPMN não gerou resultado", "Processo": ""})

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

    ok    = sum(1 for r in results if r["Status"].startswith("✅"))
    fail  = len(results) - ok

    c1, c2 = st.columns(2)
    c1.metric("✅ Gerados com sucesso", ok)
    c2.metric("❌ Erros / sem transcrição", fail)

    st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)

    if ok:
        st.info(
            "💡 Os processos BPMN estão registrados no banco. "
            "Acesse **ReqTracker** para visualizar os diagramas por processo."
        )
