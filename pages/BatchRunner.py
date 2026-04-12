# pages/BatchRunner.py
# ─────────────────────────────────────────────────────────────────────────────
# Batch Runner — processa uma pasta de transcrições em lote.
#
# Fluxo:
#   1. Seleciona ou cria um projeto Supabase
#   2. Carrega arquivos (upload múltiplo OU caminho de pasta local)
#   3. Configura quais agentes rodar
#   4. Pré-visualiza arquivos com datas detectadas e status de deduplicação
#   5. Executa o batch com progresso em tempo real
#   6. Exibe resumo e log de auditoria
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import io
import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st

from ui.auth_gate import apply_auth_gate
from modules.supabase_client import supabase_configured
from modules.session_security import get_session_llm_client
from modules.ingest import load_transcript
from core.project_store import (
    list_projects, create_project,
    is_file_processed, list_batch_log,
)
from core.batch_pipeline import (
    BatchPipeline, FileResult,
    extract_date_from_filename, extract_date_from_text, file_hash,
)

apply_auth_gate()

# ── Estilos ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.status-done  { color: #4ade80; font-weight: 700; }
.status-fail  { color: #f87171; font-weight: 700; }
.status-dup   { color: #fbbf24; font-weight: 700; }
.file-row { padding: .3rem 0; border-bottom: 1px solid #1e3a55; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 🗂️ Batch Runner")
st.caption(
    "Processa uma pasta de transcrições em lote — extrai Ata, Requisitos, SBVR e BMM "
    "de cada arquivo e persiste tudo no projeto selecionado."
)

if not supabase_configured():
    st.error("⚙️ Supabase não configurado. Adicione as credenciais em Settings → Secrets.")
    st.stop()

# ── Sidebar: provider / API key ───────────────────────────────────────────────
from modules.config import AVAILABLE_PROVIDERS
with st.sidebar:
    st.markdown("### ⚙️ Configuração")
    selected_provider = st.selectbox(
        "Provedor LLM",
        list(AVAILABLE_PROVIDERS.keys()),
        key="br_provider",
    )
    provider_cfg = AVAILABLE_PROVIDERS[selected_provider]
    api_key = st.text_input(
        provider_cfg.get("api_key_label", "API Key"),
        type="password",
        key="br_api_key",
        help=provider_cfg.get("api_key_help", ""),
    )
    output_language = st.selectbox(
        "Idioma de saída",
        ["Auto-detect", "Portuguese (BR)", "English"],
        key="br_lang",
    )

client_info = {"api_key": api_key} if api_key else None

# ── Helpers ───────────────────────────────────────────────────────────────────

class _LocalFile:
    """Wrapper para arquivos locais compatível com modules/ingest.load_transcript."""
    def __init__(self, path: Path):
        self.name = path.name
        self._buf = io.BytesIO(path.read_bytes())
    def read(self, *a):   return self._buf.read(*a)
    def seek(self, *a):   return self._buf.seek(*a)


def _load_files_from_upload(uploaded) -> list[tuple[str, str]]:
    results = []
    for uf in uploaded:
        try:
            content = load_transcript(uf)
            results.append((uf.name, content))
        except Exception as exc:
            st.warning(f"⚠️ {uf.name}: {exc}")
    return results


def _load_files_from_folder(folder_path: str) -> list[tuple[str, str]]:
    results = []
    p = Path(folder_path)
    if not p.is_dir():
        st.error(f"Pasta não encontrada: {folder_path}")
        return results
    for ext in ("*.txt", "*.docx", "*.pdf"):
        for fpath in sorted(p.glob(ext)):
            try:
                content = load_transcript(_LocalFile(fpath))
                results.append((fpath.name, content))
            except Exception as exc:
                st.warning(f"⚠️ {fpath.name}: {exc}")
    return results


# ── 1. Seleção de Projeto ─────────────────────────────────────────────────────
st.markdown("## 1️⃣ Projeto")

projects = list_projects()
proj_names = [p["name"] for p in projects] + ["➕ Criar novo projeto"]
proj_map   = {p["name"]: p for p in projects}

sel_proj = st.selectbox("Selecione o projeto destino", proj_names, key="br_proj_sel")

project_id: str | None = None

if sel_proj == "➕ Criar novo projeto":
    col_n, col_s, col_b = st.columns([3, 1, 1])
    with col_n:
        new_proj_name = st.text_input("Nome do novo projeto", key="br_new_proj_name")
    with col_s:
        new_proj_sigla = st.text_input("Sigla", key="br_new_proj_sigla",
                                       max_chars=10,
                                       placeholder="Ex: SDEA",
                                       help="Usada como prefixo nos artefatos exportados")
    with col_b:
        st.markdown("<div style='padding-top:28px'>", unsafe_allow_html=True)
        if st.button("Criar", key="br_create_proj"):
            if not new_proj_name.strip():
                st.error("Informe o nome do projeto.")
            elif not new_proj_sigla.strip():
                st.error("Informe a sigla.")
            else:
                created = create_project(new_proj_name.strip(), sigla=new_proj_sigla.strip())
                if created:
                    st.success(f"Projeto **{new_proj_name}** ({new_proj_sigla.upper()}) criado!")
                    st.rerun()
                else:
                    st.error("Erro ao criar projeto.")
        st.markdown("</div>", unsafe_allow_html=True)
else:
    project_id = proj_map[sel_proj]["id"]

if not project_id:
    st.stop()

st.markdown("---")

# ── 2. Arquivos ───────────────────────────────────────────────────────────────
st.markdown("## 2️⃣ Arquivos de Transcrição")

tab_upload, tab_folder = st.tabs(["📤 Upload de Arquivos", "📁 Pasta Local (apenas local)"])

raw_files: list[tuple[str, str]] = []

with tab_upload:
    uploaded = st.file_uploader(
        "Selecione um ou mais arquivos (.txt, .docx, .pdf)",
        type=["txt", "docx", "pdf"],
        accept_multiple_files=True,
        key="br_uploader",
    )
    if uploaded:
        raw_files = _load_files_from_upload(uploaded)

with tab_folder:
    st.info(
        "💡 Esta opção funciona apenas quando o app roda localmente (PyCharm / terminal). "
        "No Streamlit Cloud, use a aba Upload."
    )
    folder_path = st.text_input(
        "Caminho da pasta",
        placeholder="C:/Users/Dell/Documents/reunioes",
        key="br_folder_path",
    )
    if folder_path and st.button("📂 Carregar pasta", key="br_load_folder"):
        raw_files = _load_files_from_folder(folder_path)
        st.session_state["br_folder_files"] = raw_files

    if not raw_files and st.session_state.get("br_folder_files"):
        raw_files = st.session_state["br_folder_files"]

if not raw_files:
    st.info("Nenhum arquivo carregado ainda.")
    st.stop()

st.success(f"**{len(raw_files)} arquivo(s)** carregado(s).")
st.markdown("---")

# ── 3. Configuração dos Agentes ───────────────────────────────────────────────
st.markdown("## 3️⃣ Agentes")

with st.expander("Configurar agentes a executar", expanded=True):
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    run_minutes      = col1.checkbox("📋 Ata",          value=True,  key="br_minutes")
    run_requirements = col2.checkbox("📝 Requisitos",   value=True,  key="br_req")
    run_sbvr         = col3.checkbox("📖 SBVR",         value=True,  key="br_sbvr")
    run_bmm          = col4.checkbox("🎯 BMM",          value=True,  key="br_bmm")
    run_quality      = col5.checkbox("🔬 Qualidade",    value=False, key="br_quality")
    run_bpmn         = col6.checkbox("📐 BPMN (lento)", value=False, key="br_bpmn")

agents_config = {
    "run_minutes":      run_minutes,
    "run_requirements": run_requirements,
    "run_sbvr":         run_sbvr,
    "run_bmm":          run_bmm,
    "run_quality":      run_quality,
    "run_bpmn":         run_bpmn,
    "run_synthesizer":  False,
}

st.markdown("---")

# ── 4. Pré-visualização ───────────────────────────────────────────────────────
st.markdown("## 4️⃣ Pré-visualização")

preview_rows = []
for fname, content in raw_files:
    fh       = file_hash(content)
    det_date = extract_date_from_filename(fname) or extract_date_from_text(content)
    already  = is_file_processed(project_id, fh)
    preview_rows.append({
        "Arquivo":       fname,
        "Data detectada": str(det_date) if det_date else "⚠️ não encontrada — LLM irá inferir",
        "Hash":          fh,
        "Status":        "⏭️ já processado" if already else "🆕 novo",
    })

import pandas as pd
st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)

new_count  = sum(1 for r in preview_rows if r["Status"] == "🆕 novo")
skip_count = len(preview_rows) - new_count
st.caption(f"**{new_count}** arquivo(s) serão processados · **{skip_count}** já processado(s) serão ignorados.")

st.markdown("---")

# ── 5. Execução ───────────────────────────────────────────────────────────────
st.markdown("## 5️⃣ Execução")

if not client_info:
    st.warning("👈 Insira a API key na sidebar antes de executar.")
    st.stop()

if new_count == 0:
    st.info("Todos os arquivos já foram processados. Nada a fazer.")
    st.stop()

if st.button(f"▶️ Executar Batch ({new_count} arquivo(s))", type="primary", key="br_run"):

    pipeline = BatchPipeline(
        client_info=client_info,
        provider_cfg=AVAILABLE_PROVIDERS[selected_provider],
        output_language=output_language,
    )

    progress_bar   = st.progress(0.0)
    status_area    = st.empty()
    results_so_far: list[FileResult] = []
    total          = len(raw_files)

    def _on_progress(fname: str, status: str):
        done = len(results_so_far)
        pct  = done / total
        progress_bar.progress(pct)
        if status == "processing":
            status_area.info(f"⏳ **{done + 1}/{total}** — processando: `{fname}`")

    for i, (fname, content) in enumerate(raw_files):
        _on_progress(fname, "processing")
        result = pipeline._run_one(fname, content, project_id, agents_config)
        results_so_far.append(result)
        progress_bar.progress((i + 1) / total)

    status_area.empty()
    progress_bar.progress(1.0)
    st.session_state["br_results"] = results_so_far

# ── 6. Resultados ─────────────────────────────────────────────────────────────
if st.session_state.get("br_results"):
    results: list[FileResult] = st.session_state["br_results"]

    done_r  = [r for r in results if r.status == "done"]
    fail_r  = [r for r in results if r.status == "failed"]
    dup_r   = [r for r in results if r.status == "duplicate"]

    st.markdown("---")
    st.markdown("## 📊 Resultados")

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("✅ Processados",    len(done_r))
    c2.metric("❌ Erros",          len(fail_r))
    c3.metric("⏭️ Duplicados",     len(dup_r))
    c4.metric("📝 Requisitos novos", sum(r.req_new for r in done_r))
    c5.metric("📚 Termos SBVR",     sum(r.n_terms for r in done_r))
    c6.metric("📋 Regras SBVR",     sum(r.n_rules for r in done_r))

    # Tabela detalhada
    table_rows = []
    for r in results:
        status_icon = {"done": "✅", "failed": "❌", "duplicate": "⏭️"}.get(r.status, r.status)
        table_rows.append({
            "Status":      status_icon,
            "Arquivo":     r.filename,
            "Título sugerido": r.meeting_title or "—",
            "Data":        str(r.meeting_date) if r.meeting_date else f"— ({r.date_source})",
            "REQ novos":   r.req_new,
            "REQ revisados": r.req_revised,
            "Contradições": r.req_contradicted,
            "Termos":      r.n_terms,
            "Regras":      r.n_rules,
            "Erro":        r.error[:80] if r.error else "",
        })

    st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)

    if fail_r:
        st.markdown("### ❌ Detalhes dos erros")
        for r in fail_r:
            st.error(f"**{r.filename}**: {r.error}")

    # ── Log histórico ─────────────────────────────────────────────────────────
    with st.expander("📜 Log de auditoria (todos os batches deste projeto)"):
        logs = list_batch_log(project_id)
        if logs:
            log_df = pd.DataFrame([{
                "Data":       str(lg.get("processed_at", ""))[:16],
                "Arquivo":    lg.get("filename", ""),
                "Status":     lg.get("status", ""),
                "REQ novos":  lg.get("req_new", 0),
                "REQ rev.":   lg.get("req_revised", 0),
                "Contrad.":   lg.get("req_contradicted", 0),
                "Termos":     lg.get("n_terms", 0),
                "Regras":     lg.get("n_rules", 0),
                "Erro":       (lg.get("error_detail") or "")[:60],
            } for lg in logs])
            st.dataframe(log_df, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhum registro de batch para este projeto.")
