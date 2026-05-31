# pages/Artefatos.py
# ─────────────────────────────────────────────────────────────────────────────
# Central de Artefatos — painel consolidado de todos os artefatos do projeto.
# Cobre: Requisitos, Mind Map, Contradições, Histórico, Reuniões, SBVR,
#        Processos BPMN, DMN, IBIS e Rastreabilidade de Origem (PC24).
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

# Fix import path para Streamlit Cloud
root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from datetime import date

from ui.auth_gate import apply_auth_gate
from modules.supabase_client import supabase_configured
from modules.text_utils import rule_keyword_pt
from modules.reqtracker_exporter import to_html as export_html, to_pdf as export_pdf
from core.project_store import (
    list_meetings, list_requirements, list_contradictions,
    list_sbvr_terms, list_sbvr_rules,
    list_bpmn_processes, list_bpmn_versions, bpmn_tables_exist,
    list_dmn_by_project, list_argumentation_by_project,
    load_meeting_as_hub, save_bpmn_from_hub,
)
from ui.project_selector import require_active_project

try:
    from modules.document_store import list_documents
    _has_doc_store = True
except ImportError:
    _has_doc_store = False
    def list_documents(project_id, **_):  # type: ignore
        return []

apply_auth_gate()

# ── Estilos ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.req-card {
    border: 1px solid #1e3a55; border-radius: 8px;
    padding: 1rem 1.2rem; margin-bottom: .6rem;
    background: #0F2040;
}
.req-number { font-family: monospace; font-weight: 700; font-size: 1rem; }
.badge {
    display: inline-block; padding: 2px 10px; border-radius: 20px;
    font-size: .72rem; font-weight: 600; letter-spacing: .04em;
}
.badge-backlog      { background:#1e293b; color:#94a3b8; }
.badge-active       { background:#0d4f2e; color:#4ade80; }
.badge-approved     { background:#064e3b; color:#6ee7b7; }
.badge-in-progress  { background:#1e3a6e; color:#93c5fd; }
.badge-implemented  { background:#134e4a; color:#5eead4; }
.badge-revised      { background:#4a3000; color:#fbbf24; }
.badge-contradicted { background:#4a0d0d; color:#f87171; }
.badge-deprecated   { background:#2a2a2a; color:#9ca3af; }
.badge-rejected     { background:#3b0f1f; color:#fda4af; }
.badge-new          { background:#0d2f4f; color:#60a5fa; }
.badge-confirmed    { background:#0d3f1f; color:#34d399; }
.contradiction-box {
    border-left: 4px solid #f87171; padding: .8rem 1rem;
    background: rgba(248,113,113,.06); border-radius: 0 8px 8px 0;
    margin-bottom: .5rem;
}
.version-dot {
    display: inline-block; width: 10px; height: 10px;
    border-radius: 50%; margin-right: 6px;
}
.dmn-table { width: 100%; border-collapse: collapse; font-size: .85rem; }
.dmn-table th {
    background: #1e3a55; color: #93c5fd; padding: 6px 10px;
    text-align: left; border-bottom: 2px solid #2d5a8e;
}
.dmn-table td {
    padding: 5px 10px; border-bottom: 1px solid #1e293b; color: #e2e8f0;
}
.dmn-table tr:hover td { background: rgba(30,58,85,.4); }
.ibis-badge-decided    { background:#0d4f2e; color:#4ade80; }
.ibis-badge-deferred   { background:#4a3000; color:#fbbf24; }
.ibis-badge-unresolved { background:#4a0d0d; color:#f87171; }
.badge-transcricao { background:#1e3a6e; color:#93c5fd; }
.badge-documento   { background:#0d3f2e; color:#6ee7b7; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 🗂️ Central de Artefatos")

if not supabase_configured():
    st.error("⚙️ Supabase não configurado. Adicione as credenciais em Settings → Secrets.")
    st.stop()

# ── Contexto de trabalho ativo ───────────────────────────────────────────────
project_id, project_name = require_active_project()
_col_proj, _col_change = st.columns([5, 1])
with _col_proj:
    st.success(f"📁 **Contexto:** {project_name}")
with _col_change:
    st.page_link("pages/Home.py", label="Trocar")

# ── Carrega dados (com cache para evitar queries a cada rerun) ─────────────────
@st.cache_data(ttl=60, show_spinner=False)
def _load_meetings(pid):           return list_meetings(pid)

@st.cache_data(ttl=60, show_spinner=False)
def _load_requirements(pid):       return list_requirements(pid)

@st.cache_data(ttl=60, show_spinner=False)
def _load_contradictions(pid):     return list_contradictions(pid)

@st.cache_data(ttl=60, show_spinner=False)
def _load_sbvr_terms(pid):         return list_sbvr_terms(pid)

@st.cache_data(ttl=60, show_spinner=False)
def _load_sbvr_rules(pid):         return list_sbvr_rules(pid)

@st.cache_data(ttl=60, show_spinner=False)
def _load_bpmn_procs(pid):
    return list_bpmn_processes(pid) if bpmn_tables_exist() else []

@st.cache_data(ttl=60, show_spinner=False)
def _load_bpmn_versions(pid):      return list_bpmn_versions(pid)

@st.cache_data(ttl=60, show_spinner=False)
def _load_dmn(pid):                return list_dmn_by_project(pid)

@st.cache_data(ttl=60, show_spinner=False)
def _load_argumentation(pid):      return list_argumentation_by_project(pid)

@st.cache_data(ttl=60, show_spinner=False)
def _load_documents(pid):          return list_documents(pid)

meetings         = _load_meetings(project_id)
requirements     = _load_requirements(project_id)
contradictions   = _load_contradictions(project_id)
sbvr_terms       = _load_sbvr_terms(project_id)
sbvr_rules       = _load_sbvr_rules(project_id)
bpmn_procs       = _load_bpmn_procs(project_id)
dmn_decisions    = _load_dmn(project_id)
ibis_questions   = _load_argumentation(project_id)
documents        = _load_documents(project_id)

meet_map = {m["id"]: m for m in meetings}
doc_map  = {d["id"]: d for d in documents}

def meet_label(mid: str | None) -> str:
    if not mid or mid not in meet_map:
        return "—"
    m = meet_map[mid]
    dt = m.get("meeting_date") or ""
    return f"Reunião {m.get('meeting_number', '?')} — {m.get('title', '')} ({dt})"

def doc_label(doc_id: str | None) -> str:
    if not doc_id or doc_id not in doc_map:
        return "—"
    return doc_map[doc_id].get("title", "Documento")

def _origin_badge(origin: str | None) -> str:
    """Retorna HTML de badge para a origem do artefato."""
    if origin == "documento":
        return '<span class="badge badge-documento">📄 Documento</span>'
    return '<span class="badge badge-transcricao">🎙️ Transcrição</span>'

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
col_m1.metric("Decisões DMN", len(dmn_decisions))
col_m2.metric("Questões IBIS", len(ibis_questions))
col_m3.metric("Processos BPMN", len(bpmn_procs))
col_m4.metric("Documentos", len(documents))

st.markdown("---")

# ── Export ────────────────────────────────────────────────────────────────────
with st.expander("📦 Exportar Relatório", expanded=False):
    st.caption("Gera um relatório completo com requisitos, contradições, SBVR e reuniões.")
    col_html, col_pdf, _ = st.columns([1, 1, 4])

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

# ── Abas principais ───────────────────────────────────────────────────────────
tab_req, tab_mindmap, tab_contra, tab_hist, tab_meet, tab_sbvr, tab_bpmn, tab_dmn, tab_ibis, tab_trace = st.tabs([
    "📝 Requisitos",
    "🗺️ Mind Map",
    f"⚠️ Contradições ({len(contradictions)})",
    "📅 Histórico",
    "🗓️ Reuniões",
    f"📖 SBVR ({len(sbvr_terms)}T · {len(sbvr_rules)}R)",
    f"📐 Processos BPMN ({len(bpmn_procs)})",
    f"⚖️ DMN ({len(dmn_decisions)})",
    f"🗺️ IBIS ({len(ibis_questions)})",
    "🔗 Rastreabilidade",
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — REQUISITOS
# ════════════════════════════════════════════════════════════════════════════
with tab_req:
    if not requirements:
        st.info("Nenhum requisito registrado para este projeto.")
    else:
        col_f1, col_f2, col_f3, col_f4 = st.columns(4)
        with col_f1:
            status_opts = [
                "Todos", "backlog", "active", "approved", "in_progress",
                "implemented", "revised", "contradicted", "deprecated", "rejected",
            ]
            sel_status = st.selectbox("Status", status_opts, key="rt_status")
        with col_f2:
            types = sorted({r.get("req_type", "") for r in requirements if r.get("req_type")})
            sel_type = st.selectbox("Tipo", ["Todos"] + types, key="rt_type")
        with col_f3:
            prios = sorted({r.get("priority", "") for r in requirements if r.get("priority")})
            sel_prio = st.selectbox("Prioridade", ["Todos"] + prios, key="rt_prio")
        with col_f4:
            sel_origin_req = st.selectbox(
                "Origem", ["Todas", "Transcrição", "Documento"], key="rt_origin"
            )

        filtered = requirements
        if sel_status != "Todos":
            filtered = [r for r in filtered if r.get("status") == sel_status]
        if sel_type != "Todos":
            filtered = [r for r in filtered if r.get("req_type") == sel_type]
        if sel_prio != "Todos":
            filtered = [r for r in filtered if r.get("priority") == sel_prio]
        if sel_origin_req == "Transcrição":
            filtered = [r for r in filtered if r.get("origin", "transcricao") != "documento"]
        elif sel_origin_req == "Documento":
            filtered = [r for r in filtered if r.get("origin") == "documento"]

        st.caption(f"Exibindo {len(filtered)} de {n_total} requisito(s)")
        st.markdown("")

        _STATUS_BADGE = {
            "backlog":      ("badge-backlog",      "Backlog"),
            "active":       ("badge-active",       "Ativo"),
            "approved":     ("badge-approved",     "Aprovado"),
            "in_progress":  ("badge-in-progress",  "Em Desenvolvimento"),
            "implemented":  ("badge-implemented",  "Implementado"),
            "revised":      ("badge-revised",      "Revisado"),
            "contradicted": ("badge-contradicted", "Contradição"),
            "deprecated":   ("badge-deprecated",   "Depreciado"),
            "rejected":     ("badge-rejected",     "Rejeitado"),
        }
        _DOT_COLOR = {
            "new":          "#60a5fa",
            "confirmed":    "#34d399",
            "revised":      "#fbbf24",
            "contradicted": "#f87171",
        }

        for req in filtered:
            num     = req.get("req_number", 0)
            label   = f"REQ-{num:03d}"
            status  = req.get("status", "active")
            badge_cls, badge_txt = _STATUS_BADGE.get(status, ("badge-active", status))
            versions = req.get("requirement_versions") or []
            n_ver    = len(versions)

            with st.expander(
                f"**{label}** — {req.get('title', '')}  "
                f"·  {req.get('req_type', '')}  ·  {req.get('priority', '')}",
                expanded=(status == "contradicted"),
            ):
                col_d, col_m = st.columns([3, 1])
                with col_d:
                    st.markdown(
                        f'<span class="badge {badge_cls}">{badge_txt}</span> '
                        f'{_origin_badge(req.get("origin"))}',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**Descrição:** {req.get('description', '—')}")
                    if req.get("cited_by"):
                        st.caption(f"👤 Proponente: **{req['cited_by']}**")
                    if req.get("source_quote"):
                        st.caption(f'💬 *"{req["source_quote"]}"*')
                with col_m:
                    if req.get("origin") == "documento":
                        st.caption(f"📄 {doc_label(req.get('doc_ref'))}")
                    else:
                        st.caption(f"🏁 {meet_label(req.get('first_meeting_id'))}")
                        st.caption(f"🔄 {meet_label(req.get('last_meeting_id'))}")
                    st.caption(f"📌 {n_ver} versão(ões)")
                    if req.get("owner"):
                        st.caption(f"🙋 {req['owner']}")
                    if req.get("status_note"):
                        st.caption(f"📝 {req['status_note']}")

                if versions:
                    st.markdown("**Versões:**")
                    for v in sorted(versions, key=lambda x: x.get("version", 0)):
                        ct  = v.get("change_type", "")
                        dot = _DOT_COLOR.get(ct, "#aaa")
                        flag = " ⚠️" if v.get("contradiction_flag") else ""
                        st.markdown(
                            f'<span class="version-dot" style="background:{dot}"></span>'
                            f'**v{v.get("version","?")}** — {meet_label(v.get("meeting_id"))} '
                            f'· `{ct}`{flag}',
                            unsafe_allow_html=True,
                        )
                        if v.get("change_summary"):
                            st.caption(f"   ↳ {v['change_summary']}")
                        if v.get("cited_by"):
                            st.caption(f"   👤 {v['cited_by']}")
                        if v.get("source_quote"):
                            st.caption(f'   💬 *"{v["source_quote"]}"*')
                        if v.get("contradiction_detail"):
                            st.error(v["contradiction_detail"])

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — MIND MAP
# ════════════════════════════════════════════════════════════════════════════
with tab_mindmap:
    if not requirements:
        st.info("Nenhum requisito registrado para este projeto.")
    else:
        try:
            from modules.requirements_mindmap import build_mindmap_tree_from_dicts
            from modules.mindmap_interactive import render_interactive_mindmap
            _mindmap_ok = True
        except Exception as _mm_err:
            st.error(f"Erro ao carregar módulo de mind map: {_mm_err}")
            _mindmap_ok = False

        col_mm1, col_mm2, col_mm3 = st.columns([2, 2, 2])
        with col_mm1:
            mm_status = st.selectbox(
                "Filtrar por status",
                ["Todos", "backlog", "active", "approved", "in_progress",
                 "implemented", "revised", "contradicted", "deprecated", "rejected"],
                key="mm_status",
            )
        with col_mm2:
            mm_types = sorted({r.get("req_type", "") for r in requirements if r.get("req_type")})
            mm_type = st.selectbox("Filtrar por tipo", ["Todos"] + mm_types, key="mm_type")
        with col_mm3:
            mm_height = st.slider("Altura (px)", 500, 1200, 700, 50, key="mm_height")

        mm_reqs = requirements
        if mm_status != "Todos":
            mm_reqs = [r for r in mm_reqs if r.get("status") == mm_status]
        if mm_type != "Todos":
            mm_reqs = [r for r in mm_reqs if r.get("req_type") == mm_type]

        if not mm_reqs:
            st.info("Nenhum requisito corresponde aos filtros selecionados.")
        elif _mindmap_ok:
            st.caption(f"Exibindo {len(mm_reqs)} requisito(s) no mind map.")
            tree = build_mindmap_tree_from_dicts(mm_reqs, project_name)
            if tree.get("children"):
                render_interactive_mindmap(tree, height=mm_height)
            else:
                st.info("Não foi possível gerar o mind map para os requisitos selecionados.")

# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — CONTRADIÇÕES
# ════════════════════════════════════════════════════════════════════════════
with tab_contra:
    if not contradictions:
        st.success("✅ Nenhuma contradição detectada neste projeto.")
    else:
        st.warning(f"**{len(contradictions)} contradição(ões) ativa(s)** requerem atenção.")
        st.markdown("")

        for c in contradictions:
            req_info = c.get("requirements") or {}
            num      = req_info.get("req_number", "?")
            title    = req_info.get("title", "")
            meet     = meet_label(c.get("meeting_id"))

            with st.expander(f"⚠️ REQ-{num:03d} — {title}", expanded=True):
                st.markdown(
                    f'<div class="contradiction-box">'
                    f'<strong>Reunião que gerou a contradição:</strong> {meet}<br>'
                    f'<strong>Nova definição:</strong> {c.get("description", "—")}<br><br>'
                    f'<strong>Análise:</strong> {c.get("contradiction_detail", "—")}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if c.get("change_summary"):
                    st.info(f"📝 Resumo da mudança: {c['change_summary']}")

# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — HISTÓRICO POR REQUISITO
# ════════════════════════════════════════════════════════════════════════════
with tab_hist:
    if not requirements:
        st.info("Nenhum requisito registrado.")
    else:
        req_options = {
            f"REQ-{r['req_number']:03d} — {r['title']}": r
            for r in requirements
        }
        sel_req_label = st.selectbox("Selecione o requisito", list(req_options.keys()),
                                     key="rt_hist_sel")
        sel_req = req_options[sel_req_label]
        versions = sorted(
            sel_req.get("requirement_versions") or [],
            key=lambda x: x.get("version", 0),
        )

        if not versions:
            st.info("Nenhuma versão registrada.")
        else:
            st.markdown(f"### Linha do tempo — REQ-{sel_req['req_number']:03d}")
            _DOT_COLOR = {
                "new":          "#60a5fa",
                "confirmed":    "#34d399",
                "revised":      "#fbbf24",
                "contradicted": "#f87171",
            }
            for v in versions:
                ct    = v.get("change_type", "new")
                color = _DOT_COLOR.get(ct, "#aaa")
                flag  = " ⚠️ **CONTRADIÇÃO**" if v.get("contradiction_flag") else ""
                m_lbl = meet_label(v.get("meeting_id"))

                st.markdown(
                    f'<div style="border-left:3px solid {color};padding:.6rem 1rem;'
                    f'margin-bottom:.5rem;border-radius:0 6px 6px 0;'
                    f'background:rgba(15,32,64,.6)">'
                    f'<strong>v{v.get("version","?")} · {m_lbl}</strong>'
                    f'<span style="color:{color};margin-left:8px">[{ct}]</span>{flag}<br>'
                    f'<strong>Título:</strong> {v.get("title","—")}<br>'
                    f'<strong>Descrição:</strong> {v.get("description","—")}',
                    unsafe_allow_html=True,
                )
                if v.get("change_summary"):
                    st.markdown(
                        f'<span style="color:#fbbf24">↳ {v["change_summary"]}</span>',
                        unsafe_allow_html=True,
                    )
                if v.get("cited_by"):
                    st.markdown(
                        f'<span style="color:#93c5fd">👤 Proponente: <strong>{v["cited_by"]}</strong></span>',
                        unsafe_allow_html=True,
                    )
                if v.get("source_quote"):
                    st.markdown(
                        f'<span style="color:#d1d5db">💬 <em>"{v["source_quote"]}"</em></span>',
                        unsafe_allow_html=True,
                    )
                if v.get("contradiction_detail"):
                    st.markdown(
                        f'<span style="color:#f87171">⚠️ {v["contradiction_detail"]}</span>',
                        unsafe_allow_html=True,
                    )
                st.markdown("</div>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — REUNIÕES
# ════════════════════════════════════════════════════════════════════════════
with tab_meet:
    if not meetings:
        st.info("Nenhuma reunião registrada para este projeto.")
    else:
        for m in meetings:
            num   = m.get("meeting_number", "?")
            title = m.get("title", "")
            dt    = m.get("meeting_date") or "—"
            tok   = m.get("total_tokens") or 0
            prov  = m.get("llm_provider") or "—"

            with st.expander(f"**Reunião {num}** — {title} · {dt}"):
                c1, c2, c3 = st.columns(3)
                c1.metric("Tokens usados", f"{tok:,}")
                c2.metric("Provedor LLM", prov)
                c3.metric("Data", str(dt))

                reqs_originated = [
                    r for r in requirements
                    if r.get("first_meeting_id") == m["id"]
                ]
                reqs_touched = [
                    r for r in requirements
                    if r.get("first_meeting_id") != m["id"]
                    and any(
                        v.get("meeting_id") == m["id"]
                        for v in (r.get("requirement_versions") or [])
                    )
                ]
                if reqs_originated:
                    st.markdown(f"**{len(reqs_originated)} requisito(s) originado(s) nesta reunião:**")
                    for r in reqs_originated:
                        st.markdown(f"- `REQ-{r['req_number']:03d}` {r.get('title','')}")
                if reqs_touched:
                    st.markdown(f"**{len(reqs_touched)} requisito(s) revisado(s)/confirmado(s) nesta reunião:**")
                    for r in reqs_touched:
                        status = r.get("status", "active")
                        icon = "🔄" if status == "revised" else "⚠️" if status == "contradicted" else "✅"
                        st.markdown(f"- {icon} `REQ-{r['req_number']:03d}` {r.get('title','')}")

                terms_here = [t for t in sbvr_terms if t.get("meeting_id") == m["id"]]
                rules_here = [r for r in sbvr_rules if r.get("meeting_id") == m["id"]]
                if terms_here or rules_here:
                    st.markdown(f"**SBVR:** {len(terms_here)} termo(s) · {len(rules_here)} regra(s)")

                minutes_md = m.get("minutes_md") or ""
                if minutes_md:
                    st.markdown("---")
                    toggle_key = f"_show_minutes_{m['id']}"
                    col_btn, col_dl = st.columns([2, 1])
                    with col_btn:
                        label = "🙈 Ocultar Ata" if st.session_state.get(toggle_key) else "📄 Ver Ata Completa"
                        if st.button(label, key=f"btn_minutes_{m['id']}", use_container_width=True):
                            st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)
                            st.rerun()
                    with col_dl:
                        st.download_button(
                            "⬇️ Download Ata (.md)",
                            data=minutes_md.encode("utf-8"),
                            file_name=f"ata_reuniao_{num}.md",
                            mime="text/markdown",
                            key=f"dl_minutes_{m['id']}",
                            use_container_width=True,
                        )
                    if st.session_state.get(toggle_key):
                        st.markdown(minutes_md)
                else:
                    st.caption("_Ata não disponível para esta reunião._")

# ════════════════════════════════════════════════════════════════════════════
# TAB 6 — SBVR
# ════════════════════════════════════════════════════════════════════════════
_CATEGORY_BADGE = {
    "concept":   ("badge-new",       "Conceito"),
    "fact_type": ("badge-confirmed",  "Tipo de Fato"),
    "role":      ("badge-revised",    "Papel"),
    "process":   ("badge-active",     "Processo"),
}
_RULE_BADGE = {
    "constraint":   ("badge-contradicted", "Restrição"),
    "operational":  ("badge-active",       "Operacional"),
    "behavioral":   ("badge-revised",      "Comportamental"),
    "structural":   ("badge-new",          "Estrutural"),
}

with tab_sbvr:
    if not sbvr_terms and not sbvr_rules:
        st.info("Nenhum dado SBVR registrado. Execute o pipeline com o agente SBVR habilitado.")
    else:
        col_t, col_r = st.columns(2)

        with col_t:
            st.markdown(f"### 📚 Vocabulário ({len(sbvr_terms)} termos)")
            meet_ids = sorted({t.get("meeting_id") for t in sbvr_terms if t.get("meeting_id")})
            meet_labels_sbvr = {"Todas": None}
            for mid in meet_ids:
                meet_labels_sbvr[meet_label(mid)] = mid
            sel_meet_t = st.selectbox("Reunião", list(meet_labels_sbvr.keys()), key="sbvr_meet_t")
            filtered_terms = sbvr_terms if not meet_labels_sbvr[sel_meet_t] else [
                t for t in sbvr_terms if t.get("meeting_id") == meet_labels_sbvr[sel_meet_t]
            ]
            cats = sorted({t.get("category", "") for t in filtered_terms if t.get("category")})
            sel_cat = st.selectbox("Categoria", ["Todas"] + cats, key="sbvr_cat")
            if sel_cat != "Todas":
                filtered_terms = [t for t in filtered_terms if t.get("category") == sel_cat]
            st.caption(f"{len(filtered_terms)} termo(s)")
            st.markdown("")

            for t in filtered_terms:
                cat = t.get("category", "concept")
                badge_cls, badge_txt = _CATEGORY_BADGE.get(cat, ("badge-active", cat))
                meet_info = t.get("meetings") or {}
                m_num = meet_info.get("meeting_number")
                t_origin = t.get("origin", "transcricao")
                if t_origin == "documento":
                    source_label = f"📄 {doc_label(t.get('doc_ref'))}"
                elif t.get("source") == "assistente" or not m_num:
                    source_label = "🤖 Assistente"
                else:
                    source_label = f"🗓️ Reunião {m_num}"
                with st.expander(f"**{t.get('term', '—')}**", expanded=False):
                    st.markdown(
                        f'<span class="badge {badge_cls}">{badge_txt}</span> '
                        f'{_origin_badge(t_origin)}',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**Definição:** {t.get('definition', '—')}")
                    st.caption(source_label)

        with col_r:
            st.markdown(f"### 📋 Regras de Negócio ({len(sbvr_rules)} regras)")
            meet_ids_r = sorted({r.get("meeting_id") for r in sbvr_rules if r.get("meeting_id")})
            meet_labels_sbvr_r = {"Todas": None}
            for mid in meet_ids_r:
                meet_labels_sbvr_r[meet_label(mid)] = mid
            sel_meet_r = st.selectbox("Reunião", list(meet_labels_sbvr_r.keys()), key="sbvr_meet_r")
            filtered_rules = sbvr_rules if not meet_labels_sbvr_r[sel_meet_r] else [
                r for r in sbvr_rules if r.get("meeting_id") == meet_labels_sbvr_r[sel_meet_r]
            ]
            types = sorted({r.get("rule_type", "") for r in filtered_rules if r.get("rule_type")})
            sel_rtype = st.selectbox("Tipo", ["Todos"] + types, key="sbvr_rtype")
            if sel_rtype != "Todos":
                filtered_rules = [r for r in filtered_rules if r.get("rule_type") == sel_rtype]
            st.caption(f"{len(filtered_rules)} regra(s)")
            st.markdown("")

            for idx, r in enumerate(filtered_rules, 1):
                rtype = r.get("rule_type", "constraint")
                badge_cls, badge_txt = _RULE_BADGE.get(rtype, ("badge-active", rtype))
                rule_id = r.get("rule_id") or f"BR-{idx:03d}"
                meet_info = r.get("meetings") or {}
                m_num = meet_info.get("meeting_number")
                r_origin = r.get("origin", "transcricao")
                kw = r.get("nucleo_nominal") or rule_keyword_pt(r.get("statement", ""))
                label = f"**{rule_id}**  —  {kw}" if kw else f"**{rule_id}**"
                with st.expander(label, expanded=False):
                    st.markdown(
                        f'<span class="badge {badge_cls}">{badge_txt}</span> '
                        f'{_origin_badge(r_origin)}',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"{r.get('statement', '—')}")
                    if r_origin == "documento":
                        footer = f"📄 {doc_label(r.get('doc_ref'))}"
                    elif m_num:
                        footer = f"🗓️ Reunião {m_num}"
                    else:
                        footer = "🤖 Assistente"
                    if r.get("source") and r["source"] not in ("manual", "assistente"):
                        footer += f" · 👤 {r['source']}"
                    st.caption(footer)

# ════════════════════════════════════════════════════════════════════════════
# TAB 7 — PROCESSOS BPMN
# ════════════════════════════════════════════════════════════════════════════
import streamlit.components.v1 as components


def _do_bpmn_reconvert(process_id: str, meeting_id: str, project_id: str) -> None:
    """Re-run AgentBPMN (skill v7.0) sobre uma reunião e salva como nova versão."""
    from modules.session_security import get_session_llm_client

    client_info  = get_session_llm_client(st.session_state.get("selected_provider", ""))
    provider_cfg = st.session_state.get("provider_cfg") or {}

    if not client_info:
        st.error("Configure um provedor LLM em **Sistema → Configurações** antes de reconverter.")
        return

    with st.spinner("Carregando transcrição da reunião..."):
        hub = load_meeting_as_hub(meeting_id, project_id)

    if not hub:
        st.error("Reunião não encontrada no banco de dados.")
        return

    transcript = (hub.transcript_clean or hub.transcript_raw or "").strip()
    if len(transcript) < 50:
        st.error(
            "Transcrição não disponível ou muito curta para esta reunião. "
            "Reprocesse a transcrição pelo Pipeline antes de reconverter."
        )
        return

    with st.spinner("Reconvertendo com AgentBPMN (Method & Style v7.0)..."):
        try:
            from agents.agent_bpmn import AgentBPMN
            agent = AgentBPMN(client_info, provider_cfg)
            hub   = agent.run(hub)
        except Exception as exc:
            st.error(f"Erro na reconversão: {exc}")
            return

    if not getattr(hub.bpmn, "ready", False):
        st.error("O agente não produziu um modelo BPMN válido.")
        return

    n_steps    = len(hub.bpmn.steps)
    n_call_act = sum(1 for s in hub.bpmn.steps if s.task_type == "callActivity")
    n_loops    = sum(1 for s in hub.bpmn.steps if s.task_type in ("loopTask", "multiInstanceTask"))

    with st.spinner("Salvando nova versão..."):
        saved = save_bpmn_from_hub(meeting_id, project_id, hub, bpmn_process_id=process_id)

    if saved:
        st.success("Diagrama reconvertido e salvo como nova versão!")
        c1, c2, c3 = st.columns(3)
        c1.metric("Nós no nível 1", n_steps,
                  help="Steps + gateways no nível principal do diagrama")
        c2.metric("callActivities", n_call_act,
                  help="Fases agrupadas pela regra de densidade Silver Level 1 (>10 atividades)")
        c3.metric("Loop / Multi-instance", n_loops,
                  help="Tarefas loopTask ou multiInstanceTask identificadas")
        if hub.bpmn.repair_log:
            st.caption(f"Reparos automáticos aplicados: {len(hub.bpmn.repair_log)}")
        _load_bpmn_versions.clear()
        _load_bpmn_procs.clear()
        st.rerun()
    else:
        st.error("Erro ao salvar a nova versão. Verifique a conexão com o banco de dados.")
from modules.bpmn_viewer import preview_from_xml
from modules.mermaid_renderer import render_mermaid_block

_STATUS_PROC_BADGE = {
    "active":   ("badge-active",    "Ativo"),
    "archived": ("badge-deprecated","Arquivado"),
}

with tab_bpmn:
    if not bpmn_procs:
        if not bpmn_tables_exist():
            st.warning(
                "⚠️ Tabelas BPMN ainda não criadas. "
                "Execute `setup/supabase_schema_bpmn_processes.sql` no Supabase."
            )
        else:
            st.info(
                "Nenhum processo BPMN registrado para este projeto. "
                "Execute o pipeline com BPMN habilitado ou use o **📐 BPMN Backfill**."
            )
    else:
        st.caption(
            f"**{len(bpmn_procs)} processo(s)** registrado(s). "
            "Expanda um processo para ver o histórico de versões e visualizar o diagrama."
        )
        st.markdown("")

        for proc in bpmn_procs:
            pid        = proc["id"]
            proc_name  = proc.get("name") or "Processo"
            n_ver      = proc.get("version_count") or 0
            status     = proc.get("status", "active")
            slug       = proc.get("slug", "")
            last_mid   = proc.get("last_meeting_id")
            badge_cls, badge_txt = _STATUS_PROC_BADGE.get(status, ("badge-active", status))

            header = (
                f"**{proc_name}**  ·  "
                f'{n_ver} versão(ões)  ·  '
                f'última: {meet_label(last_mid)}'
            )
            with st.expander(header, expanded=(n_ver > 0)):
                col_m1, col_m2, col_m3 = st.columns(3)
                with col_m1:
                    st.markdown(f'<span class="badge {badge_cls}">{badge_txt}</span>', unsafe_allow_html=True)
                with col_m2:
                    st.caption(f"🔑 slug: `{slug}`")
                with col_m3:
                    st.caption(f"🏁 Primeira: {meet_label(proc.get('first_meeting_id'))}")
                st.markdown("---")

                versions = _load_bpmn_versions(pid)
                if not versions:
                    st.info("Nenhuma versão registrada ainda.")
                    continue

                ver_options = {}
                for v in versions:
                    m_info = v.get("meetings") or {}
                    m_num  = m_info.get("meeting_number", "?")
                    m_tit  = m_info.get("title", "")
                    m_dt   = m_info.get("meeting_date", "")
                    lbl    = f"v{v['version']}  ·  Reunião {m_num} — {m_tit} ({m_dt})"
                    if v.get("is_current"):
                        lbl = "⭐ " + lbl + "  (atual)"
                    ver_options[lbl] = v

                sel_ver_lbl = st.selectbox("Versão", list(ver_options.keys()), key=f"bpmn_ver_sel_{pid}")
                sel_ver = ver_options[sel_ver_lbl]

                bpmn_xml     = sel_ver.get("bpmn_xml") or ""
                mermaid_code = sel_ver.get("mermaid_code") or ""

                if not bpmn_xml and not mermaid_code:
                    st.warning("Esta versão não possui diagrama armazenado.")
                    continue

                sub_bpmn, sub_mermaid = st.tabs(["📐 BPMN 2.0", "📊 Mermaid"])
                with sub_bpmn:
                    if bpmn_xml:
                        try:
                            bpmn_html = preview_from_xml(bpmn_xml)
                            components.html(bpmn_html, height=700, scrolling=False)
                        except Exception as e:
                            st.error(f"Erro ao renderizar BPMN: {e}")
                        st.download_button(
                            "⬇️ Download BPMN XML",
                            data=bpmn_xml.encode("utf-8"),
                            file_name=f"{slug}_v{sel_ver['version']}.bpmn",
                            mime="application/xml",
                            key=f"dl_bpmn_{pid}_{sel_ver['version']}",
                        )
                    else:
                        st.info("XML BPMN não disponível para esta versão.")
                with sub_mermaid:
                    if mermaid_code:
                        render_mermaid_block(
                            mermaid_code,
                            show_code=False,
                            key_suffix=f"rt_mmd_{pid}_{sel_ver['version']}",
                            height=500,
                        )
                    else:
                        st.info("Código Mermaid não disponível para esta versão.")

                # ── Reconversão Method & Style v7.0 ──────────────────────
                st.markdown("---")
                st.markdown("##### Reconverter com Method & Style v7.0")
                st.caption(
                    "Re-executa o AgentBPMN aplicando a metodologia Top-Down de Bruce Silver "
                    "(skill v7.0): regra de densidade, callActivity, Verbo+Objeto, boundary events). "
                    "Salva como nova versão — a versão atual é preservada no histórico."
                )
                _reconv_mid = sel_ver.get("meeting_id")
                if _reconv_mid:
                    st.caption(
                        f"Origem: {meet_label(_reconv_mid)}  "
                        f"·  versão selecionada: v{sel_ver['version']}"
                    )
                    if st.button(
                        "Reconverter este diagrama",
                        key=f"reconvert_{pid}_{sel_ver['version']}",
                        type="primary",
                        use_container_width=True,
                    ):
                        _do_bpmn_reconvert(pid, _reconv_mid, project_id)
                else:
                    st.warning("Reunião origem não identificada nesta versão.")

# ════════════════════════════════════════════════════════════════════════════
# TAB 8 — DMN
# ════════════════════════════════════════════════════════════════════════════
_HIT_POLICY_LABEL = {
    "U": "Unique — apenas uma regra pode ser satisfeita",
    "A": "Any — qualquer regra satisfeita produz o mesmo resultado",
    "F": "First — primeira regra satisfeita vence",
    "C": "Collect — todas as regras satisfeitas são coletadas",
}

with tab_dmn:
    if not dmn_decisions:
        st.info("Nenhuma tabela de decisão DMN registrada. Execute o pipeline com o agente DMN habilitado.")
    else:
        st.caption(
            f"**{len(dmn_decisions)} decisão(ões)** extraídas de {len({d['_meeting_id'] for d in dmn_decisions})} reunião(ões). "
            "Cada decisão representa uma tabela de regras DMN 1.4."
        )

        # Filtro por reunião
        meet_ids_dmn = sorted({d["_meeting_id"] for d in dmn_decisions})
        meet_labels_dmn = {"Todas as reuniões": None}
        for mid in meet_ids_dmn:
            meet_labels_dmn[meet_label(mid)] = mid
        sel_meet_dmn = st.selectbox("Filtrar por reunião", list(meet_labels_dmn.keys()), key="dmn_meet_filter")
        filtered_dmn = dmn_decisions if not meet_labels_dmn[sel_meet_dmn] else [
            d for d in dmn_decisions if d["_meeting_id"] == meet_labels_dmn[sel_meet_dmn]
        ]

        st.markdown("")
        for d in filtered_dmn:
            dec_id   = d.get("id", "—")
            dec_name = d.get("name", "—")
            hp       = d.get("hit_policy", "U")
            inputs   = d.get("inputs", [])
            outputs  = d.get("outputs", [])
            rules    = d.get("rules", [])
            m_num    = d.get("_meeting_number")
            origin   = f"🗓️ Reunião {m_num}" if m_num else "—"

            with st.expander(f"**{dec_id}** — {dec_name}  ·  {origin}", expanded=False):
                # Cabeçalho da decisão
                col_q, col_hp = st.columns([3, 1])
                with col_q:
                    if d.get("question"):
                        st.markdown(f"**Questão:** {d['question']}")
                    if d.get("rationale"):
                        st.caption(f"📝 {d['rationale']}")
                    if d.get("decided_by"):
                        st.caption(f"👥 Decidido por: {', '.join(d['decided_by'])}")
                with col_hp:
                    st.markdown(
                        f'<span class="badge badge-new">Hit Policy: {hp}</span>',
                        unsafe_allow_html=True,
                    )
                    st.caption(_HIT_POLICY_LABEL.get(hp, hp))

                if not inputs or not outputs or not rules:
                    st.info("Tabela de decisão sem regras registradas.")
                    continue

                # Monta a tabela HTML
                input_labels  = [i.get("label", f"Input {j+1}") for j, i in enumerate(inputs)]
                output_labels = [o.get("label", f"Output {k+1}") for k, o in enumerate(outputs)]

                header_cells = "".join(f"<th>{h}</th>" for h in input_labels + output_labels + ["Anotação"])
                rows_html = ""
                for idx, rule in enumerate(rules, 1):
                    rule_inputs  = rule.get("inputs", [])
                    rule_output  = rule.get("output", "")
                    annotation   = rule.get("annotation", "")
                    input_cells  = "".join(
                        f"<td>{rule_inputs[j] if j < len(rule_inputs) else '—'}</td>"
                        for j in range(len(input_labels))
                    )
                    output_cell  = f"<td><strong>{rule_output}</strong></td>"
                    annot_cell   = f"<td><em>{annotation}</em></td>" if annotation else "<td>—</td>"
                    rows_html   += f"<tr>{input_cells}{output_cell}{annot_cell}</tr>"

                st.markdown(
                    f'<table class="dmn-table"><thead><tr>{header_cells}</tr></thead>'
                    f'<tbody>{rows_html}</tbody></table>',
                    unsafe_allow_html=True,
                )

# ════════════════════════════════════════════════════════════════════════════
# TAB 9 — IBIS / ARGUMENTAÇÃO
# ════════════════════════════════════════════════════════════════════════════
_RESOLUTION_BADGE = {
    "decided":    ("ibis-badge-decided",    "✅ Decidida"),
    "deferred":   ("ibis-badge-deferred",   "⏳ Adiada"),
    "unresolved": ("ibis-badge-unresolved", "❓ Em aberto"),
}

with tab_ibis:
    if not ibis_questions:
        st.info("Nenhum mapa argumentativo IBIS registrado. Execute o pipeline com o agente Argumentação habilitado.")
    else:
        n_decided    = sum(1 for q in ibis_questions if q.get("resolution", {}).get("type") == "decided")
        n_deferred   = sum(1 for q in ibis_questions if q.get("resolution", {}).get("type") == "deferred")
        n_unresolved = sum(1 for q in ibis_questions if q.get("resolution", {}).get("type") == "unresolved")

        ki1, ki2, ki3, ki4 = st.columns(4)
        ki1.metric("Total de Questões", len(ibis_questions))
        ki2.metric("✅ Decididas", n_decided)
        ki3.metric("⏳ Adiadas", n_deferred)
        ki4.metric("❓ Em aberto", n_unresolved)

        st.markdown("---")

        # Filtro por reunião
        meet_ids_ibis = sorted({q["_meeting_id"] for q in ibis_questions})
        meet_labels_ibis = {"Todas as reuniões": None}
        for mid in meet_ids_ibis:
            meet_labels_ibis[meet_label(mid)] = mid
        sel_meet_ibis = st.selectbox("Filtrar por reunião", list(meet_labels_ibis.keys()), key="ibis_meet_filter")

        # Filtro por resolução
        sel_res = st.selectbox(
            "Filtrar por resolução",
            ["Todas", "decided", "deferred", "unresolved"],
            format_func=lambda x: {"Todas": "Todas", "decided": "✅ Decididas",
                                    "deferred": "⏳ Adiadas", "unresolved": "❓ Em aberto"}.get(x, x),
            key="ibis_res_filter",
        )

        filtered_ibis = ibis_questions
        if meet_labels_ibis[sel_meet_ibis]:
            filtered_ibis = [q for q in filtered_ibis if q["_meeting_id"] == meet_labels_ibis[sel_meet_ibis]]
        if sel_res != "Todas":
            filtered_ibis = [q for q in filtered_ibis if q.get("resolution", {}).get("type") == sel_res]

        st.caption(f"Exibindo {len(filtered_ibis)} questão(ões)")
        st.markdown("")

        for q in filtered_ibis:
            q_id        = q.get("id", "—")
            statement   = q.get("statement", "—")
            raised_by   = q.get("raised_by", "")
            alternatives = q.get("alternatives", [])
            resolution  = q.get("resolution", {})
            res_type    = resolution.get("type", "unresolved")
            badge_cls, badge_txt = _RESOLUTION_BADGE.get(res_type, ("ibis-badge-unresolved", "❓"))
            m_num = q.get("_meeting_number")
            origin = f"🗓️ Reunião {m_num}" if m_num else "—"

            with st.expander(
                f"**{q_id}** — {statement[:80]}{'…' if len(statement) > 80 else ''}  ·  {origin}",
                expanded=(res_type == "unresolved"),
            ):
                col_s, col_b = st.columns([4, 1])
                with col_s:
                    st.markdown(f"**{statement}**")
                    if raised_by:
                        st.caption(f"👤 Levantada por: **{raised_by}**")
                with col_b:
                    st.markdown(
                        f'<span class="badge {badge_cls}">{badge_txt}</span>',
                        unsafe_allow_html=True,
                    )

                # Alternativas
                if alternatives:
                    st.markdown("**Alternativas avaliadas:**")
                    for alt in alternatives:
                        chosen_mark = " ✅ **(escolhida)**" if alt.get("was_chosen") else ""
                        st.markdown(f"**{alt.get('id', '—')}** — {alt.get('description', '—')}{chosen_mark}")
                        if alt.get("proposed_by"):
                            st.caption(f"Proposta por: {alt['proposed_by']}")
                        cols_arg = st.columns(2)
                        if alt.get("pros"):
                            cols_arg[0].success("**A favor:**\n" + "\n".join(f"- {p}" for p in alt["pros"]))
                        if alt.get("cons"):
                            cols_arg[1].error("**Contra:**\n" + "\n".join(f"- {c}" for c in alt["cons"]))
                        supporters = ", ".join(alt.get("supported_by", []))
                        opposers   = ", ".join(alt.get("opposed_by", []))
                        parts = []
                        if supporters:
                            parts.append(f"A favor: {supporters}")
                        if opposers:
                            parts.append(f"Contra: {opposers}")
                        if parts:
                            st.caption(" | ".join(parts))
                        st.markdown("---")

                # Resolução
                if res_type != "unresolved":
                    if resolution.get("rationale"):
                        st.info(f"**Resolução:** {resolution['rationale']}")
                    if resolution.get("with_caveats"):
                        st.warning("**Ressalvas:**\n" + "\n".join(f"- {c}" for c in resolution["with_caveats"]))
                else:
                    st.error("Questão sem resolução ao final da reunião.")


# ════════════════════════════════════════════════════════════════════════════
# TAB 10 — RASTREABILIDADE DE ORIGEM
# ════════════════════════════════════════════════════════════════════════════

with tab_trace:
    st.subheader("Matriz de Rastreabilidade de Origem")
    st.caption(
        "Visão consolidada de todos os artefatos com sua fonte de origem: "
        "reunião (transcrição) ou documento. "
        "Use os filtros para localizar artefatos por tipo ou origem."
    )

    # ── Filtros ────────────────────────────────────────────────────────────────
    tf1, tf2 = st.columns(2)
    with tf1:
        sel_trace_tipo = st.selectbox(
            "Tipo de artefato",
            ["Todos", "Requisito", "Termo SBVR", "Regra SBVR"],
            key="trace_tipo",
        )
    with tf2:
        sel_trace_origin = st.selectbox(
            "Origem",
            ["Todas", "Transcrição", "Documento"],
            key="trace_origin",
        )

    # ── Montar linhas da matriz ────────────────────────────────────────────────
    import pandas as pd

    rows = []

    if sel_trace_tipo in ("Todos", "Requisito"):
        for r in requirements:
            orig = r.get("origin", "transcricao")
            if sel_trace_origin == "Transcrição" and orig == "documento":
                continue
            if sel_trace_origin == "Documento" and orig != "documento":
                continue
            num = r.get("req_number", 0)
            if orig == "documento":
                fonte = doc_label(r.get("doc_ref"))
                origem_txt = "📄 Documento"
            else:
                mid = r.get("first_meeting_id")
                fonte = meet_label(mid) if mid else "—"
                origem_txt = "🎙️ Transcrição"
            rows.append({
                "Tipo":    "Requisito",
                "ID":      f"REQ-{num:03d}",
                "Título":  r.get("title", "—"),
                "Origem":  origem_txt,
                "Fonte":   fonte,
                "Status":  r.get("status", "—"),
                "Prio.":   r.get("priority", "—"),
            })

    if sel_trace_tipo in ("Todos", "Termo SBVR"):
        for t in sbvr_terms:
            orig = t.get("origin", "transcricao")
            if sel_trace_origin == "Transcrição" and orig == "documento":
                continue
            if sel_trace_origin == "Documento" and orig != "documento":
                continue
            if orig == "documento":
                fonte = doc_label(t.get("doc_ref"))
                origem_txt = "📄 Documento"
            else:
                meet_info = t.get("meetings") or {}
                m_num = meet_info.get("meeting_number")
                fonte = f"Reunião {m_num}" if m_num else "Assistente"
                origem_txt = "🎙️ Transcrição"
            rows.append({
                "Tipo":    "Termo SBVR",
                "ID":      "—",
                "Título":  t.get("term", "—"),
                "Origem":  origem_txt,
                "Fonte":   fonte,
                "Status":  t.get("category", "—"),
                "Prio.":   "—",
            })

    if sel_trace_tipo in ("Todos", "Regra SBVR"):
        for idx, r in enumerate(sbvr_rules, 1):
            orig = r.get("origin", "transcricao")
            if sel_trace_origin == "Transcrição" and orig == "documento":
                continue
            if sel_trace_origin == "Documento" and orig != "documento":
                continue
            if orig == "documento":
                fonte = doc_label(r.get("doc_ref"))
                origem_txt = "📄 Documento"
            else:
                meet_info = r.get("meetings") or {}
                m_num = meet_info.get("meeting_number")
                fonte = f"Reunião {m_num}" if m_num else "Assistente"
                origem_txt = "🎙️ Transcrição"
            rows.append({
                "Tipo":    "Regra SBVR",
                "ID":      r.get("rule_id") or f"BR-{idx:03d}",
                "Título":  r.get("nucleo_nominal") or r.get("statement", "—")[:80],
                "Origem":  origem_txt,
                "Fonte":   fonte,
                "Status":  r.get("rule_type", "—"),
                "Prio.":   "—",
            })

    if not rows:
        st.info("Nenhum artefato encontrado para os filtros selecionados.")
    else:
        # KPIs de rastreabilidade
        n_doc_rows = sum(1 for row in rows if row["Origem"].startswith("📄"))
        n_tra_rows = len(rows) - n_doc_rows
        tk1, tk2, tk3 = st.columns(3)
        tk1.metric("Total de artefatos", len(rows))
        tk2.metric("🎙️ De transcrições", n_tra_rows)
        tk3.metric("📄 De documentos", n_doc_rows)
        st.markdown("")

        df_trace = pd.DataFrame(rows)
        st.dataframe(
            df_trace,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Tipo":   st.column_config.TextColumn(width="small"),
                "ID":     st.column_config.TextColumn(width="small"),
                "Título": st.column_config.TextColumn(width="large"),
                "Origem": st.column_config.TextColumn(width="medium"),
                "Fonte":  st.column_config.TextColumn(width="large"),
                "Status": st.column_config.TextColumn(width="small"),
                "Prio.":  st.column_config.TextColumn(width="small"),
            },
        )

        # Download CSV
        st.download_button(
            label="⬇️ Exportar CSV",
            data=df_trace.to_csv(index=False).encode("utf-8"),
            file_name=f"rastreabilidade_{project_name.replace(' ', '_')}.csv",
            mime="text/csv",
            key="trace_csv",
        )
