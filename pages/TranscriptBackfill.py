# pages/TranscriptBackfill.py
# ─────────────────────────────────────────────────────────────────────────────
# Transcript Backfill — salva transcrições para reuniões que existem no banco
# mas cujo campo transcript_clean é NULL (payload overflow ou versão anterior).
#
# Zero chamadas LLM — apenas extração de texto e gravação no Supabase.
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
from modules.supabase_client import supabase_configured
from modules.ingest import load_transcript
from core.project_store import (
    list_projects,
    list_meetings_without_transcript,
    save_transcript_text,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Transcript Backfill — Process2Diagram",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_auth_gate()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 📝 Transcript Backfill")
st.caption(
    "Salva transcrições para reuniões já registradas no banco que ainda não têm "
    "transcrição armazenada. Não cria novas reuniões nem executa nenhum agente LLM."
)

if not supabase_configured():
    st.error("⚙️ Supabase não configurado.")
    st.stop()

# ── 1. Projeto ────────────────────────────────────────────────────────────────
st.markdown("## 1️⃣ Projeto")
projects = list_projects()
if not projects:
    st.warning("Nenhum projeto disponível.")
    st.stop()

proj_map = {p["name"]: p for p in projects}
sel_proj = st.selectbox("Projeto", list(proj_map.keys()), key="tb_proj")
project_id = proj_map[sel_proj]["id"]

# ── 2. Reuniões sem transcrição ───────────────────────────────────────────────
st.markdown("## 2️⃣ Reuniões sem transcrição")
pending = list_meetings_without_transcript(project_id)

if not pending:
    st.success("✅ Todas as reuniões do projeto já têm transcrição armazenada.")
    st.stop()

st.metric("Reuniões sem transcrição", len(pending))

preview = [
    {
        "Nº":    m.get("meeting_number") or "—",
        "Título": m.get("title") or "(sem título)",
        "Data":  str(m.get("meeting_date") or "—"),
    }
    for m in pending
]
st.dataframe(pd.DataFrame(preview), use_container_width=True, hide_index=True)

# ── 3. Upload ─────────────────────────────────────────────────────────────────
st.markdown("## 3️⃣ Upload das transcrições")
st.caption(
    "Faça o upload do arquivo original de cada reunião (.txt, .docx ou .pdf). "
    "O texto será extraído e salvo sem nenhuma modificação ou chamada LLM."
)

uploads: dict[str, str] = {}   # meeting_id → texto extraído

for m in pending:
    mid   = m["id"]
    num   = m.get("meeting_number") or "?"
    title = m.get("title") or "(sem título)"
    date  = str(m.get("meeting_date") or "—")

    uf = st.file_uploader(
        f"Reunião {num} — {title} ({date})",
        type=["txt", "docx", "pdf"],
        key=f"tb_up_{mid}",
    )
    if uf:
        try:
            text = load_transcript(uf)
            if text and text.strip():
                uploads[mid] = text
                st.caption(f"   ✅ `{uf.name}` — {len(text):,} caracteres")
            else:
                st.warning(f"   ⚠️ `{uf.name}` parece vazio.")
        except Exception as exc:
            st.error(f"   ❌ Erro ao ler `{uf.name}`: {exc}")

# ── 4. Salvar ─────────────────────────────────────────────────────────────────
st.markdown("---")

if not uploads:
    st.info("👆 Faça o upload das transcrições acima para habilitar o salvamento.")
    st.stop()

n_ready = len(uploads)
if st.button(
    f"💾 Salvar {n_ready} transcrição(ões)",
    type="primary",
    key="tb_save",
):
    results = []
    prog = st.progress(0.0)

    for i, (mid, text) in enumerate(uploads.items()):
        # Encontra metadados da reunião pelo ID
        meta = next((m for m in pending if m["id"] == mid), {})
        title = meta.get("title") or f"Reunião {meta.get('meeting_number','?')}"

        ok = save_transcript_text(mid, text)
        results.append({
            "Reunião": title,
            "Chars":   f"{len(text):,}",
            "Status":  "✅ Salvo" if ok else "❌ Erro ao salvar",
        })
        prog.progress((i + 1) / n_ready)

    prog.empty()
    st.session_state["tb_results"] = results

# ── 5. Resultados ─────────────────────────────────────────────────────────────
if st.session_state.get("tb_results"):
    results = st.session_state["tb_results"]
    st.markdown("---")
    st.markdown("## 📊 Resultados")

    ok_count   = sum(1 for r in results if r["Status"].startswith("✅"))
    fail_count = len(results) - ok_count

    c1, c2 = st.columns(2)
    c1.metric("✅ Salvas com sucesso", ok_count)
    c2.metric("❌ Erros", fail_count)

    st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)

    if ok_count:
        st.success(
            "💡 Transcrições salvas. O **Assistente** já pode consultá-las. "
            "Para habilitar busca semântica, gere os embeddings em "
            "**Assistente → ⚡ Gerar Embeddings**."
        )
        # Limpa resultados para não mostrar novamente após rerun
        if st.button("🔄 Verificar novamente", key="tb_refresh"):
            st.session_state.pop("tb_results", None)
            st.rerun()
