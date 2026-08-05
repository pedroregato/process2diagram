# pages/Artefatos.py
# ─────────────────────────────────────────────────────────────────────────────
# Central de Artefatos — Visão Geral (PC208).
# Landing page da seção "Artefatos": KPIs consolidados, exportação de
# relatório e navegação para as 5 subseções por assunto (Requisitos,
# Modelagem Formal, Reuniões, Debates/IBIS, Qualidade & Sinais).
# Até o PC208 esta página tinha as 13 abas hoje divididas entre as subseções —
# ver claude_guideline/roadmap.md.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from concurrent.futures import ThreadPoolExecutor as _TPE

from ui.auth_gate import apply_auth_gate
from modules.supabase_client import supabase_configured
from modules.reqtracker_exporter import to_html as export_html, to_pdf as export_pdf
from ui.project_selector import require_active_project
from ui.artefatos_shared import (
    inject_artefatos_css, render_artefatos_nav,
    dmn_session_key, ibis_session_key, noise_session_key,
    _load_meetings, _load_requirements, _load_contradictions,
    _load_sbvr_terms, _load_sbvr_rules, _load_bpmn_procs,
    _load_documents, _load_asset_meta_map, _load_provocations,
)

apply_auth_gate()
inject_artefatos_css()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 🗂️ Central de Artefatos")

if not supabase_configured():
    st.error("⚙️ Supabase não configurado. Adicione as credenciais em Settings → Secrets.")
    st.stop()

# ── Contexto de trabalho ativo ───────────────────────────────────────────────
project_id, project_name = require_active_project()
render_artefatos_nav("pages/Artefatos.py")

_col_proj, _col_change = st.columns([5, 1])
with _col_proj:
    st.success(f"📁 **Contexto:** {project_name}")
with _col_change:
    st.page_link("pages/Home.py", label="Trocar")

# ── Carrega dados (com cache compartilhado com as demais páginas da seção) ───
with _TPE(max_workers=9) as _artefatos_pool:
    _f_meetings       = _artefatos_pool.submit(_load_meetings, project_id)
    _f_requirements   = _artefatos_pool.submit(_load_requirements, project_id)
    _f_contradictions = _artefatos_pool.submit(_load_contradictions, project_id)
    _f_sbvr_terms     = _artefatos_pool.submit(_load_sbvr_terms, project_id)
    _f_sbvr_rules     = _artefatos_pool.submit(_load_sbvr_rules, project_id)
    _f_bpmn_procs     = _artefatos_pool.submit(_load_bpmn_procs, project_id)
    _f_documents      = _artefatos_pool.submit(_load_documents, project_id)
    _f_asset_meta     = _artefatos_pool.submit(_load_asset_meta_map, project_id)
    _f_provocations   = _artefatos_pool.submit(_load_provocations, project_id)

    meetings         = _f_meetings.result()
    requirements     = _f_requirements.result()
    contradictions   = _f_contradictions.result()
    sbvr_terms       = _f_sbvr_terms.result()
    sbvr_rules       = _f_sbvr_rules.result()
    bpmn_procs       = _f_bpmn_procs.result()
    documents        = _f_documents.result()
    asset_meta_map   = _f_asset_meta.result()  # {(artifact_type, artifact_id): row} — só PROMOVIDOS
    provocations     = _f_provocations.result()

# DMN/IBIS/Ruídos: lê do session_state — só ficam populados nesta sessão se o
# usuário já visitou a subseção correspondente (Modelagem Formal / Debates /
# Qualidade & Sinais). Mesmo comportamento lazy de antes do PC208, agora
# entre páginas em vez de entre abas.
dmn_decisions  = st.session_state.get(dmn_session_key(project_id),   None)
ibis_questions = st.session_state.get(ibis_session_key(project_id),  None)
noise_items    = st.session_state.get(noise_session_key(project_id), None)

# ── Métricas resumo ───────────────────────────────────────────────────────────
n_total        = len(requirements)
n_contradicted = sum(1 for r in requirements if r.get("status") == "contradicted")
n_revised      = sum(1 for r in requirements if r.get("status") == "revised")
n_meetings     = len(meetings)
n_req_doc      = sum(1 for r in requirements if r.get("origin") == "documento")
n_terms_doc    = sum(1 for t in sbvr_terms if t.get("origin") == "documento")
n_rules_doc    = sum(1 for r in sbvr_rules if r.get("origin") == "documento")

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Requisitos", n_total, help=f"{n_req_doc} de documentos · {n_total - n_req_doc} de transcrições")
c2.metric("Reuniões", n_meetings)
c3.metric("Revisados", n_revised)
c4.metric("⚠️ Contradições", n_contradicted, delta=None,
          delta_color="off" if n_contradicted == 0 else "inverse")
c5.metric("Termos SBVR", len(sbvr_terms), help=f"{n_terms_doc} de documentos")
c6.metric("Regras SBVR", len(sbvr_rules), help=f"{n_rules_doc} de documentos")

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
col_m1.metric("Decisões DMN",  len(dmn_decisions)  if dmn_decisions  is not None else "—",
              help="Acesse Modelagem Formal para carregar" if dmn_decisions is None else None)
col_m2.metric("Questões IBIS", len(ibis_questions) if ibis_questions is not None else "—",
              help="Acesse Debates (IBIS) para carregar" if ibis_questions is None else None)
col_m3.metric("Processos BPMN", len(bpmn_procs))
col_m4.metric("Documentos", len(documents))

st.markdown("---")

# ── Export ────────────────────────────────────────────────────────────────────
with st.expander("📦 Exportar Relatório", expanded=False):
    st.caption("Gera um relatório completo com requisitos, contradições, SBVR e reuniões.")
    col_html, col_pdf, _ = st.columns([1, 1, 4])
    project = {"name": project_name}

    with col_html:
        if st.button("🌐 Gerar HTML", key="rt_export_html"):
            with st.spinner("Gerando relatório HTML..."):
                try:
                    html_bytes = export_html(
                        project, meetings, requirements,
                        contradictions, sbvr_terms, sbvr_rules,
                    ).encode("utf-8")
                    st.session_state["rt_html"] = html_bytes
                except Exception as e:
                    st.error(f"Erro ao gerar HTML: {e}")

    with col_pdf:
        if st.button("📄 Gerar PDF", key="rt_export_pdf"):
            with st.spinner("Gerando relatório PDF..."):
                try:
                    pdf_bytes = export_pdf(
                        project, meetings, requirements,
                        contradictions, sbvr_terms, sbvr_rules,
                    )
                    st.session_state["rt_pdf"] = pdf_bytes
                except Exception as e:
                    st.error(f"Erro ao gerar PDF: {e}")

    fname = project_name.replace(" ", "_")

    if st.session_state.get("rt_html"):
        st.download_button(
            label="⬇️ Download HTML",
            data=st.session_state["rt_html"],
            file_name=f"Artefatos_{fname}.html",
            mime="text/html",
            key="rt_dl_html",
        )

    if st.session_state.get("rt_pdf"):
        st.download_button(
            label="⬇️ Download PDF",
            data=st.session_state["rt_pdf"],
            file_name=f"Artefatos_{fname}.pdf",
            mime="application/pdf",
            key="rt_dl_pdf",
        )

st.markdown("---")

# ── Navegação por assunto ──────────────────────────────────────────────────────
st.markdown("### Explorar por assunto")

_CARDS = [
    ("pages/ArtefatosRequisitos.py", "📝 Requisitos",
     f"{n_total} requisitos · {n_contradicted} contradições · Mind Map · Governança"),
    ("pages/ArtefatosModelagem.py", "📐 Modelagem Formal",
     f"{len(sbvr_terms)} termos · {len(sbvr_rules)} regras SBVR · {len(bpmn_procs)} processos BPMN · DMN"),
    ("pages/ArtefatosReunioes.py", "🗓️ Reuniões",
     f"{n_meetings} reuniões · Rastreabilidade de origem · Comparação"),
    ("pages/ArtefatosDebates.py", "🗺️ Debates (IBIS)",
     f"{len(ibis_questions) if ibis_questions is not None else '…'} questões · Evolução temporal · Mapa visual"),
    ("pages/ArtefatosQualidade.py", "🔎 Qualidade & Sinais",
     f"{len(noise_items) if noise_items is not None else '…'} ruídos · {len(provocations)} provocações"),
]

_cc1, _cc2 = st.columns(2)
for _idx, (_path, _title, _desc) in enumerate(_CARDS):
    with (_cc1 if _idx % 2 == 0 else _cc2):
        with st.container(border=True):
            st.markdown(f"#### {_title}")
            st.caption(_desc)
            st.page_link(_path, label="Abrir →", use_container_width=True)
