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
    list_meetings, list_requirements, list_requirements_light,
    list_requirement_versions, list_contradictions,
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
# TTLs calibrados pelo ritmo de mudança dos dados:
#   meetings/contradictions: 120s (podem mudar após pipeline)
#   requirements/SBVR/BPMN/docs: 300s (mudam raramente)
#   bpmn_tables_exist: 3600s (estrutura permanente — elimina 2 pings desnecessários)
#   DMN/IBIS: carregados sob demanda via session_state (JSONs pesados, abas raramente visitadas)

@st.cache_data(ttl=120, show_spinner=False)
def _load_meetings(pid):           return list_meetings(pid)

@st.cache_data(ttl=300, show_spinner=False)
def _load_requirements(pid):       return list_requirements_light(pid)

@st.cache_data(ttl=300, show_spinner=False)
def _load_req_versions(req_id):    return list_requirement_versions(req_id)

@st.cache_data(ttl=120, show_spinner=False)
def _load_contradictions(pid):     return list_contradictions(pid)

@st.cache_data(ttl=300, show_spinner=False)
def _load_sbvr_terms(pid):         return list_sbvr_terms(pid)

@st.cache_data(ttl=300, show_spinner=False)
def _load_sbvr_rules(pid):         return list_sbvr_rules(pid)

@st.cache_data(ttl=3600, show_spinner=False)
def _bpmn_tables_exist_cached() -> bool:
    return bpmn_tables_exist()

@st.cache_data(ttl=300, show_spinner=False)
def _load_bpmn_procs(pid):
    return list_bpmn_processes(pid) if _bpmn_tables_exist_cached() else []

@st.cache_data(ttl=300, show_spinner=False)
def _load_bpmn_versions(pid):      return list_bpmn_versions(pid)

@st.cache_data(ttl=300, show_spinner=False)
def _load_dmn(pid):                return list_dmn_by_project(pid)

@st.cache_data(ttl=300, show_spinner=False)
def _load_argumentation(pid):      return list_argumentation_by_project(pid)

@st.cache_data(ttl=300, show_spinner=False)
def _load_documents(pid):          return list_documents(pid)

# ── Carregamento inicial: dados leves apenas ──────────────────────────────────
# DMN e IBIS buscam dmn_json/argumentation_json de TODAS as reuniões (JSONs pesados).
# São carregados sob demanda na primeira visita à respectiva aba, via session_state.
# Isso reduz o carregamento inicial de 10-11 queries para 7-8 queries sequenciais.

meetings         = _load_meetings(project_id)
requirements     = _load_requirements(project_id)
contradictions   = _load_contradictions(project_id)
sbvr_terms       = _load_sbvr_terms(project_id)
sbvr_rules       = _load_sbvr_rules(project_id)
bpmn_procs       = _load_bpmn_procs(project_id)
documents        = _load_documents(project_id)

# DMN e IBIS: lê do session_state se já carregados nesta sessão.
# None = ainda não carregado (primeira visita). [] = carregado, sem dados.
_DMN_SS  = f"_art_dmn_{project_id}"
_IBIS_SS = f"_art_ibis_{project_id}"
dmn_decisions  = st.session_state.get(_DMN_SS,  None)
ibis_questions = st.session_state.get(_IBIS_SS, None)

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
col_m1.metric("Decisões DMN",  len(dmn_decisions)  if dmn_decisions  is not None else "—",
              help="Acesse a aba DMN para carregar" if dmn_decisions is None else None)
col_m2.metric("Questões IBIS", len(ibis_questions) if ibis_questions is not None else "—",
              help="Acesse a aba IBIS para carregar" if ibis_questions is None else None)
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
    f"⚖️ DMN ({len(dmn_decisions) if dmn_decisions is not None else '…'})",
    f"🗺️ IBIS ({len(ibis_questions) if ibis_questions is not None else '…'})",
    "🔗 Rastreabilidade",
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — REQUISITOS
# ════════════════════════════════════════════════════════════════════════════
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
_REQ_PAGE_SIZE = 25

with tab_req:
    st.caption(
        "**Requisitos** são condições ou capacidades que o sistema ou processo deve satisfazer, "
        "extraídos das transcrições pela IA seguindo o padrão IEEE 830. "
        "Cada requisito tem tipo (funcional, não-funcional, regra de negócio…), prioridade e rastreabilidade até a reunião de origem."
    )
    if not requirements:
        st.info("Nenhum requisito registrado para este projeto.")
    else:
        # ── Filtros ──────────────────────────────────────────────────────
        col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)
        with col_f1:
            sel_status = st.selectbox(
                "Status",
                ["Todos", "backlog", "active", "approved", "in_progress",
                 "implemented", "revised", "contradicted", "deprecated", "rejected"],
                key="rt_status",
            )
        with col_f2:
            _types = sorted({r.get("req_type", "") for r in requirements if r.get("req_type")})
            sel_type = st.selectbox("Tipo", ["Todos"] + _types, key="rt_type")
        with col_f3:
            _prios = sorted({r.get("priority", "") for r in requirements if r.get("priority")})
            sel_prio = st.selectbox("Prioridade", ["Todos"] + _prios, key="rt_prio")
        with col_f4:
            sel_origin_req = st.selectbox(
                "Origem", ["Todas", "Transcrição", "Documento"], key="rt_origin"
            )
        with col_f5:
            sel_search = st.text_input(
                "Buscar", placeholder="título ou descrição…", key="rt_search"
            )

        # ── Aplicar filtros ───────────────────────────────────────────────
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
        if sel_search:
            _q = sel_search.lower()
            filtered = [
                r for r in filtered
                if _q in (r.get("title") or "").lower()
                or _q in (r.get("description") or "").lower()
            ]

        n_filtered = len(filtered)

        # ── Paginação — reset ao mudar filtros ou projeto ─────────────────
        _filter_sig = f"{project_id}|{sel_status}|{sel_type}|{sel_prio}|{sel_origin_req}|{sel_search}"
        if st.session_state.get("_rt_last_filter") != _filter_sig:
            st.session_state["rt_page"] = 0
            st.session_state["_rt_last_filter"] = _filter_sig

        _page       = min(st.session_state.get("rt_page", 0),
                          max(0, (n_filtered - 1) // _REQ_PAGE_SIZE))
        _n_pages    = max(1, (n_filtered + _REQ_PAGE_SIZE - 1) // _REQ_PAGE_SIZE)
        _page_start = _page * _REQ_PAGE_SIZE
        _page_end   = min(_page_start + _REQ_PAGE_SIZE, n_filtered)
        page_items  = filtered[_page_start:_page_end]

        # ── Navegação de página (topo) ────────────────────────────────────
        _nav1, _nav2, _nav3, _nav4 = st.columns([1, 1, 4, 1])
        with _nav1:
            if st.button("← Anterior", key="rt_prev", disabled=(_page == 0)):
                st.session_state["rt_page"] = _page - 1
                st.rerun()
        with _nav2:
            if st.button("Próximo →", key="rt_next", disabled=(_page == _n_pages - 1)):
                st.session_state["rt_page"] = _page + 1
                st.rerun()
        with _nav3:
            st.caption(
                f"Itens **{_page_start + 1}–{_page_end}** de **{n_filtered}** "
                f"· Página **{_page + 1}** de **{_n_pages}**"
                + (f"  ·  *(filtro ativo)*" if n_filtered < n_total else "")
            )
        with _nav4:
            _go = st.number_input(
                "Ir para", min_value=1, max_value=_n_pages, value=_page + 1,
                step=1, key="rt_goto", label_visibility="collapsed",
            )
            if _go - 1 != _page:
                st.session_state["rt_page"] = int(_go) - 1
                st.rerun()

        # ── Tabela compacta ───────────────────────────────────────────────
        _rows_html = ""
        for _idx, _r in enumerate(page_items, start=_page_start + 1):
            _num   = _r.get("req_number", 0)
            _title = (_r.get("title") or "—")[:60]
            _rtype = _r.get("req_type") or "—"
            _prio  = _r.get("priority") or "—"
            _st    = _r.get("status", "active")
            _bc, _bt = _STATUS_BADGE.get(_st, ("badge-active", _st))
            _orig_icon = "📄" if _r.get("origin") == "documento" else "🎙️"
            _rows_html += (
                f"<tr>"
                f"<td style='color:#64748b;text-align:right;padding:4px 6px'>{_idx}</td>"
                f"<td style='padding:4px 8px'><code>REQ-{_num:03d}</code></td>"
                f"<td style='padding:4px 8px'>{_title}</td>"
                f"<td style='padding:4px 8px;white-space:nowrap'>{_rtype}</td>"
                f"<td style='padding:4px 8px'><span class='badge {_bc}'>{_bt}</span></td>"
                f"<td style='padding:4px 8px;white-space:nowrap'>{_prio}</td>"
                f"<td style='padding:4px 8px;text-align:center'>{_orig_icon}</td>"
                f"</tr>"
            )
        st.markdown(
            "<table style='width:100%;font-size:0.83em;border-collapse:collapse'>"
            "<thead><tr style='border-bottom:1px solid #334155'>"
            "<th style='padding:4px 6px;color:#64748b;text-align:right'>#</th>"
            "<th align='left' style='padding:4px 8px'>ID</th>"
            "<th align='left' style='padding:4px 8px'>Título</th>"
            "<th align='left' style='padding:4px 8px'>Tipo</th>"
            "<th align='left' style='padding:4px 8px'>Status</th>"
            "<th align='left' style='padding:4px 8px'>Prioridade</th>"
            "<th align='center' style='padding:4px 8px'>Origem</th>"
            "</tr></thead>"
            f"<tbody>{_rows_html}</tbody></table>",
            unsafe_allow_html=True,
        )

        # ── Painel de detalhes (um requisito por vez) ─────────────────────
        st.markdown("---")
        st.markdown("##### Detalhes do requisito")
        st.caption(
            "Selecione um requisito para ver descrição completa e histórico de versões. "
            "O histórico é carregado do banco de dados apenas quando solicitado."
        )

        _detail_opts = {
            f"REQ-{r['req_number']:03d} — {r['title']}": r
            for r in filtered
        }
        if _detail_opts:
            _sel_det_lbl = st.selectbox(
                "Selecionar requisito",
                list(_detail_opts.keys()),
                key="rt_detail_sel",
            )
            _det_req = _detail_opts[_sel_det_lbl]
            _det_status = _det_req.get("status", "active")
            _det_bc, _det_bt = _STATUS_BADGE.get(_det_status, ("badge-active", _det_status))

            _dd1, _dd2 = st.columns([3, 1])
            with _dd1:
                st.markdown(
                    f'<span class="badge {_det_bc}">{_det_bt}</span> '
                    f'{_origin_badge(_det_req.get("origin"))}',
                    unsafe_allow_html=True,
                )
                st.markdown(f"**Descrição:** {_det_req.get('description') or '—'}")
                if _det_req.get("cited_by"):
                    st.caption(f"👤 Proponente: **{_det_req['cited_by']}**")
                if _det_req.get("source_quote"):
                    st.caption(f'💬 *"{_det_req["source_quote"]}"*')
                if _det_req.get("status_note"):
                    st.caption(f"📝 {_det_req['status_note']}")
            with _dd2:
                if _det_req.get("origin") == "documento":
                    st.caption(f"📄 {doc_label(_det_req.get('doc_ref'))}")
                else:
                    st.caption(f"🏁 {meet_label(_det_req.get('first_meeting_id'))}")
                    st.caption(f"🔄 {meet_label(_det_req.get('last_meeting_id'))}")
                if _det_req.get("owner"):
                    st.caption(f"🙋 {_det_req['owner']}")

            # Histórico de versões — carregado sob demanda (1 query por seleção)
            _det_vers = _load_req_versions(_det_req["id"])
            if _det_vers:
                with st.expander(f"📋 Histórico de versões ({len(_det_vers)})", expanded=False):
                    for _v in _det_vers:
                        _ct  = _v.get("change_type", "")
                        _dot = _DOT_COLOR.get(_ct, "#aaa")
                        _flag = " ⚠️" if _v.get("contradiction_flag") else ""
                        st.markdown(
                            f'<span class="version-dot" style="background:{_dot}"></span>'
                            f'**v{_v.get("version","?")}** — {meet_label(_v.get("meeting_id"))} '
                            f'· `{_ct}`{_flag}',
                            unsafe_allow_html=True,
                        )
                        if _v.get("change_summary"):
                            st.caption(f"   ↳ {_v['change_summary']}")
                        if _v.get("cited_by"):
                            st.caption(f"   👤 {_v['cited_by']}")
                        if _v.get("source_quote"):
                            st.caption(f'   💬 *"{_v["source_quote"]}"*')
                        if _v.get("contradiction_detail"):
                            st.error(_v["contradiction_detail"])
        else:
            st.info("Nenhum requisito corresponde aos filtros aplicados.")

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — MIND MAP
# ════════════════════════════════════════════════════════════════════════════
with tab_mindmap:
    st.caption(
        "**Mind Map de Requisitos** — visualização hierárquica interativa que agrupa os requisitos "
        "por tipo (funcional, não-funcional, regra de negócio…). "
        "Permite navegar, colapsar ramos e exportar como imagem para apresentações."
    )
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
    st.caption(
        "**Contradições** são conflitos detectados entre requisitos de reuniões diferentes — "
        "situações em que duas afirmações se opõem ou se excluem mutuamente. "
        "A detecção usa similaridade semântica (embeddings) e análise de antônimos; "
        "cada conflito traz os trechos originais e uma explicação gerada pela IA."
    )
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
    st.caption(
        "**Histórico de Requisitos** — linha do tempo de como cada requisito evoluiu entre reuniões. "
        "Cada versão registra a descrição, prioridade e status vigentes naquele momento, "
        "permitindo auditar mudanças de escopo ao longo do projeto."
    )
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
        versions = _load_req_versions(sel_req["id"])

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
    st.caption(
        "**Reuniões** — índice de todas as reuniões do projeto com seus artefatos consolidados: "
        "participantes, decisões, itens de ação e resumo executivo. "
        "Use esta aba como ponto de entrada para revisar o conteúdo de uma reunião específica "
        "sem precisar reabrir o pipeline."
    )
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
                # Aproximação: requisitos cuja última versão foi nesta reunião
                # (sem join de requirement_versions para manter a query leve)
                reqs_touched = [
                    r for r in requirements
                    if r.get("first_meeting_id") != m["id"]
                    and r.get("last_meeting_id") == m["id"]
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
    st.caption(
        "**SBVR (Semantics of Business Vocabulary and Rules)** é um padrão OMG para formalizar "
        "o vocabulário e as regras de negócio de um domínio em linguagem não-ambígua. "
        "Os **termos** definem os conceitos do negócio; as **regras** expressam obrigações, "
        "proibições e permissões que governam o processo — cada uma rastreável à reunião e ao falante de origem."
    )
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
    st.caption(
        "**BPMN 2.0 (Business Process Model and Notation)** é o padrão ISO/OMG para modelagem "
        "de processos de negócio. Os diagramas gerados mostram o fluxo de tarefas, decisões "
        "(gateways), raias por responsável (lanes) e eventos de início/fim — "
        "exportáveis como XML para ferramentas como Camunda, Bizagi ou Signavio."
    )
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
        # ── Reordena processos por número de reunião (ascendente) ─────────
        def _proc_meet_num(p):
            mid = p.get("first_meeting_id") or p.get("last_meeting_id")
            if mid and mid in meet_map:
                return meet_map[mid].get("meeting_number") or 9999
            return 9999

        bpmn_procs_sorted = sorted(bpmn_procs, key=_proc_meet_num)
        total_vers = sum(p.get("version_count") or 0 for p in bpmn_procs_sorted)

        st.caption(
            f"**{len(bpmn_procs_sorted)} processo(s)** · "
            f"**{total_vers} versão(ões)** no total."
        )

        # ── Tabela-resumo (colapsável) ────────────────────────────────────
        with st.expander("Ver lista de todos os processos", expanded=False):
            _tbl_rows = []
            for _i, _p in enumerate(bpmn_procs_sorted, 1):
                _mid = _p.get("first_meeting_id") or _p.get("last_meeting_id")
                _m   = meet_map.get(_mid or "", {})
                _mnum = _m.get("meeting_number", "—")
                _status_cls, _status_txt = _STATUS_PROC_BADGE.get(
                    _p.get("status", "active"), ("badge-active", "Ativo")
                )
                _tbl_rows.append(
                    f"<tr>"
                    f"<td style='padding:3px 8px;color:#64748b'>{_i}</td>"
                    f"<td style='padding:3px 8px;white-space:nowrap'>Reunião {_mnum}</td>"
                    f"<td style='padding:3px 8px'><b>{_p.get('name') or '—'}</b></td>"
                    f"<td style='padding:3px 8px'>{_p.get('version_count') or 0}</td>"
                    f"<td style='padding:3px 8px'>"
                    f"<span class='badge {_status_cls}'>{_status_txt}</span></td>"
                    f"</tr>"
                )
            st.markdown(
                "<table style='width:100%;font-size:0.83em;border-collapse:collapse'>"
                "<thead><tr style='border-bottom:1px solid #334155'>"
                "<th style='padding:3px 8px;color:#64748b'>#</th>"
                "<th align='left' style='padding:3px 8px'>Reunião</th>"
                "<th align='left' style='padding:3px 8px'>Processo</th>"
                "<th align='left' style='padding:3px 8px'>Versões</th>"
                "<th align='left' style='padding:3px 8px'>Status</th>"
                "</tr></thead><tbody>"
                + "".join(_tbl_rows)
                + "</tbody></table>",
                unsafe_allow_html=True,
            )

        st.markdown("")

        # ── Seletor por reunião (ordem numérica) ──────────────────────────
        _proc_sel_labels = []
        _proc_sel_map    = {}
        for _p in bpmn_procs_sorted:
            _mid  = _p.get("first_meeting_id") or _p.get("last_meeting_id")
            _m    = meet_map.get(_mid or "", {})
            _mnum = _m.get("meeting_number", "?")
            _mtit = _m.get("title", "") or _p.get("name") or ""
            _mdt  = _m.get("meeting_date", "") or ""
            _lbl  = f"Reunião {_mnum} — {_mtit}"
            if _mdt:
                _lbl += f"  ({_mdt})"
            # garante unicidade de label em caso de colisão
            if _lbl in _proc_sel_map:
                _lbl += f"  [{_p['id'][:6]}]"
            _proc_sel_labels.append(_lbl)
            _proc_sel_map[_lbl] = _p

        _sel_proc_lbl = st.selectbox(
            "Selecionar reunião",
            _proc_sel_labels,
            key="bpmn_proc_selector",
            help="Lista ordenada por número de reunião.",
        )
        sel_proc = _proc_sel_map[_sel_proc_lbl]
        pid      = sel_proc["id"]
        slug     = sel_proc.get("slug", "")

        st.markdown("---")

        # ── Versões do processo selecionado (1 query) ────────────────────
        versions = _load_bpmn_versions(pid)
        if not versions:
            st.info("Nenhuma versão registrada ainda para este processo.")
        else:
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

            sel_ver_lbl = st.selectbox(
                "Versão", list(ver_options.keys()), key=f"bpmn_ver_sel_{pid}"
            )
            sel_ver      = ver_options[sel_ver_lbl]
            bpmn_xml     = sel_ver.get("bpmn_xml") or ""
            mermaid_code = sel_ver.get("mermaid_code") or ""

            # ── Diagramas ────────────────────────────────────────────────
            if bpmn_xml or mermaid_code:
                sub_bpmn, sub_mermaid = st.tabs(["📐 BPMN 2.0", "📊 Mermaid"])
                with sub_bpmn:
                    if bpmn_xml:
                        st.download_button(
                            "⬇️ Download BPMN XML",
                            data=bpmn_xml.encode("utf-8"),
                            file_name=f"{slug}_v{sel_ver['version']}.bpmn",
                            mime="application/xml",
                            key=f"dl_bpmn_{pid}_{sel_ver['version']}",
                        )
                        if st.toggle(
                            "Visualizar diagrama interativo",
                            key=f"bpmn_show_{pid}_{sel_ver['version']}",
                        ):
                            try:
                                bpmn_html = preview_from_xml(bpmn_xml)
                                components.html(bpmn_html, height=700, scrolling=False)
                            except Exception as e:
                                st.error(f"Erro ao renderizar BPMN: {e}")
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
            else:
                st.info("Esta versão não possui diagrama armazenado. Use a reconversão abaixo para gerar um novo.")

            # ── Reconversão Method & Style v7.0 ──────────────────────────
            st.markdown("---")
            st.markdown("##### Reconverter com Method & Style v7.0")
            st.caption(
                "Re-executa o AgentBPMN aplicando a metodologia Top-Down de Bruce Silver "
                "(skill v7.0): regra de densidade, callActivity, Verbo+Objeto, boundary events. "
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
    st.caption(
        "**DMN (Decision Model and Notation)** é o padrão OMG para formalizar decisões de negócio "
        "como tabelas de regras (decision tables). Cada tabela define as entradas (condições), "
        "as saídas (ações/resultados) e a política de acerto (UNIQUE, ANY, FIRST…), "
        "tornando as regras auditáveis, testáveis e integráveis a motores de regras como Drools."
    )
    # Carregamento sob demanda: só busca do Supabase se ainda não foi feito nesta sessão
    if _DMN_SS not in st.session_state:
        with st.spinner("Buscando decisões DMN..."):
            st.session_state[_DMN_SS] = _load_dmn(project_id)
        st.rerun()  # re-renderiza para atualizar contador no cabeçalho e métricas
    dmn_decisions = st.session_state[_DMN_SS]  # agora é lista (pode ser [])

    if st.button("🔄 Atualizar DMN", key="art_dmn_refresh"):
        st.session_state.pop(_DMN_SS, None)
        _load_dmn.clear()
        st.rerun()

    if not dmn_decisions:
        st.info("Nenhuma tabela de decisão DMN registrada. Execute o pipeline com o agente DMN habilitado.")
        # ── Diagnóstico temporário ────────────────────────────────────────────
        with st.expander("🔍 Diagnóstico DMN (temporário)", expanded=False):
            try:
                from modules.supabase_client import get_supabase_client as _sc
                _db_diag = _sc()
                if _db_diag:
                    _rows = _db_diag.table("meetings").select(
                        "id, meeting_number, dmn_json"
                    ).eq("project_id", project_id).execute().data or []
                    st.write(f"**Rows retornadas:** {len(_rows)}")
                    for _r in _rows[:3]:
                        _raw = _r.get("dmn_json") or ""
                        st.write(f"Reunião #{_r.get('meeting_number')} — `dmn_json` len={len(_raw)} — preview: `{_raw[:120]}`")
                else:
                    st.warning("Supabase não conectado.")
            except Exception as _exc:
                st.error(f"Erro no diagnóstico: {_exc}")
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
    st.caption(
        "**IBIS (Issue-Based Information System)** é uma metodologia de argumentação estruturada "
        "que organiza as discussões de uma reunião em **questões** (Issues), "
        "**alternativas** (Positions) com prós e contras, e **resoluções**. "
        "Permite entender não apenas o que foi decidido, mas por que — "
        "registrando o raciocínio coletivo da equipe."
    )
    # Carregamento sob demanda: só busca do Supabase se ainda não foi feito nesta sessão
    if _IBIS_SS not in st.session_state:
        with st.spinner("Buscando questões IBIS..."):
            st.session_state[_IBIS_SS] = _load_argumentation(project_id)
        st.rerun()  # re-renderiza para atualizar contador no cabeçalho e métricas
    ibis_questions = st.session_state[_IBIS_SS]  # agora é lista (pode ser [])

    if st.button("🔄 Atualizar IBIS", key="art_ibis_refresh"):
        st.session_state.pop(_IBIS_SS, None)
        _load_argumentation.clear()
        st.rerun()

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

        # ── Fase 1b: Métricas detalhadas do debate ────────────────────────────
        n_total_alts = sum(len(q.get("alternatives", [])) for q in ibis_questions)
        n_total_args = sum(
            len(a.get("pros", [])) + len(a.get("cons", []))
            for q in ibis_questions
            for a in q.get("alternatives", [])
        )
        taxa_res = round(n_decided / len(ibis_questions) * 100) if ibis_questions else 0
        q_mais_debatida = max(
            ibis_questions,
            key=lambda q: len(q.get("alternatives", [])),
            default=None,
        )

        with st.expander("📊 Análise do Debate", expanded=True):
            ma1, ma2, ma3 = st.columns(3)
            ma1.metric("Alternativas avaliadas", n_total_alts)
            ma2.metric("Argumentos registrados", n_total_args)
            ma3.metric("Taxa de resolução", f"{taxa_res}%")

            if q_mais_debatida:
                n_alt_max = len(q_mais_debatida.get("alternatives", []))
                stmt_preview = q_mais_debatida.get("statement", "")[:110]
                if len(q_mais_debatida.get("statement", "")) > 110:
                    stmt_preview += "…"
                st.caption(
                    f"🔥 **Questão mais debatida:** {stmt_preview} "
                    f"({n_alt_max} alternativas · Reunião {q_mais_debatida.get('_meeting_number', '?')})"
                )

            # ── Fase 1c: Participação por ator ────────────────────────────────
            _actor: dict[str, dict] = {}

            def _ensure(name: str) -> None:
                if name and name not in _actor:
                    _actor[name] = {
                        "Questões levantadas": 0,
                        "Alternativas propostas": 0,
                        "Posições vencedoras": 0,
                        "A favor (votos)": 0,
                        "Contra (votos)": 0,
                    }

            for _q in ibis_questions:
                _rb = (_q.get("raised_by") or "").strip()
                if _rb:
                    _ensure(_rb)
                    _actor[_rb]["Questões levantadas"] += 1
                for _alt in _q.get("alternatives", []):
                    _pb = (_alt.get("proposed_by") or "").strip()
                    if _pb:
                        _ensure(_pb)
                        _actor[_pb]["Alternativas propostas"] += 1
                        if _alt.get("was_chosen"):
                            _actor[_pb]["Posições vencedoras"] += 1
                    for _s in (_alt.get("supported_by") or []):
                        _s = (_s or "").strip()
                        if _s:
                            _ensure(_s)
                            _actor[_s]["A favor (votos)"] += 1
                    for _o in (_alt.get("opposed_by") or []):
                        _o = (_o or "").strip()
                        if _o:
                            _ensure(_o)
                            _actor[_o]["Contra (votos)"] += 1

            if _actor:
                import pandas as _pd_ibis
                st.markdown("---")
                st.markdown("**👥 Participação por Ator**")
                _df_actor = (
                    _pd_ibis.DataFrame.from_dict(_actor, orient="index")
                    .fillna(0)
                    .astype(int)
                )
                _df_actor.index.name = "Participante"
                _df_actor = _df_actor.sort_values(
                    ["Questões levantadas", "Alternativas propostas"], ascending=False
                )
                # Adiciona coluna de influência total
                _df_actor["Influência total"] = (
                    _df_actor["Questões levantadas"] * 2
                    + _df_actor["Alternativas propostas"]
                    + _df_actor["Posições vencedoras"] * 3
                    + _df_actor["A favor (votos)"]
                    + _df_actor["Contra (votos)"]
                )
                _df_actor = _df_actor.sort_values("Influência total", ascending=False)
                st.dataframe(_df_actor, use_container_width=True)
                st.caption(
                    "Influência total = 2 × questões levantadas + alternativas propostas "
                    "+ 3 × posições vencedoras + votos a favor + votos contra."
                )

        # ── Fase 3b: Evolução Temporal de Debates ────────────────────────────
        with st.expander("📅 Evolução Temporal de Debates", expanded=False):
            st.caption(
                "Agrupa questões similares de reuniões diferentes em **threads de debate** "
                "e exibe a linha do tempo de cada tema — mostrando como foi tratado ao longo do projeto "
                "(adiado repetidamente, reaberto após decisão, etc.)."
            )

            _evo_thresh = st.slider(
                "Limiar de similaridade",
                min_value=0.10, max_value=0.50, value=0.22, step=0.03,
                key="ibis_evo_thresh",
                help="Jaccard sobre tokens PT-BR. Menor = mais threads detectadas.",
            )

            # ── Stop words e similaridade ──────────────────────────────────
            import re as _re_evo
            _EVO_STOP = {
                "a","o","as","os","de","do","da","dos","das","em","no","na",
                "nos","nas","para","que","um","uma","uns","umas","e","ou","se",
                "com","por","mas","é","ser","ter","ao","à","aos","às","não",
                "como","mais","deve","há","esta","este","seu","sua","seus",
                "suas","foi","sido","sendo","está","estão","são","faz","fazer",
                "pode","deve","devem","podem","será","vai","vão",
                "the","of","to","in","is","it","be","as","at","or","an","and",
            }

            def _evo_tok(text: str) -> set:
                words = _re_evo.sub(r"[^\w\sáéíóúâêôãç]", " ", text.lower()).split()
                return {w for w in words if w not in _EVO_STOP and len(w) > 2}

            def _evo_jac(a: str, b: str) -> float:
                wa, wb = _evo_tok(a), _evo_tok(b)
                if not wa or not wb:
                    return 0.0
                return len(wa & wb) / len(wa | wb)

            # ── Union-Find sobre TODAS as questões do projeto ──────────────
            _n = len(ibis_questions)
            _uf = list(range(_n))

            def _uf_find(p: list, x: int) -> int:
                while p[x] != x:
                    p[x] = p[p[x]]
                    x = p[x]
                return x

            def _uf_union(p: list, x: int, y: int) -> None:
                rx, ry = _uf_find(p, x), _uf_find(p, y)
                if rx != ry:
                    p[ry] = rx

            for _ea in range(_n):
                for _eb in range(_ea + 1, _n):
                    _qa = ibis_questions[_ea]
                    _qb = ibis_questions[_eb]
                    if _qa.get("_meeting_id") == _qb.get("_meeting_id"):
                        continue
                    if _evo_jac(_qa.get("statement", ""), _qb.get("statement", "")) >= _evo_thresh:
                        _uf_union(_uf, _ea, _eb)

            # ── Agrupar em componentes ─────────────────────────────────────
            from collections import defaultdict as _dd_evo
            _comp: dict = _dd_evo(list)
            for _ei, _eq in enumerate(ibis_questions):
                _comp[_uf_find(_uf, _ei)].append(_eq)

            # Manter só componentes com 2+ reuniões distintas
            _threads: list[list] = []
            for _root, _qs in _comp.items():
                _mids_in = {q.get("_meeting_id") for q in _qs}
                if len(_mids_in) >= 2:
                    _threads.append(
                        sorted(_qs, key=lambda q: (q.get("_meeting_number") or 0))
                    )
            _threads.sort(key=lambda t: t[0].get("_meeting_number") or 0)

            if not _threads:
                st.info(
                    "Nenhum debate recorrente detectado com este limiar. "
                    "Tente reduzir o valor do slider."
                )
            else:
                _res_cfg = {
                    "decided":    ("✅", "Decidida",  "#14532d", "#4ade80"),
                    "deferred":   ("⏳", "Adiada",    "#451a03", "#fbbf24"),
                    "unresolved": ("❓", "Em aberto", "#450a0a", "#f87171"),
                }
                st.success(f"**{len(_threads)} debate(s) recorrente(s)** identificado(s) no projeto.")
                st.markdown("")

                for _ti, _thread in enumerate(_threads, 1):
                    _rep = _thread[0].get("statement", "")
                    _preview = _rep[:90] + ("…" if len(_rep) > 90 else "")
                    st.markdown(f"**Debate #{_ti}** — {_preview}")

                    # Cabeçalho de reuniões com seta entre elas
                    _ncols = min(len(_thread), 6)
                    _thread_show = _thread[:6]
                    if len(_thread) > 6:
                        st.caption(f"(Exibindo primeiras 6 de {len(_thread)} ocorrências)")

                    _tcols = st.columns(_ncols)
                    for _tci, (_col, _tq) in enumerate(zip(_tcols, _thread_show)):
                        _t_mnum  = _tq.get("_meeting_number", "?")
                        _t_mdate = str(_tq.get("_meeting_date") or "")[:10]
                        _t_stmt  = _tq.get("statement", "")
                        _t_res   = (_tq.get("resolution") or {}).get("type", "unresolved")
                        _t_rat   = (_tq.get("resolution") or {}).get("rationale", "")
                        _t_cav   = (_tq.get("resolution") or {}).get("with_caveats") or []
                        _emoji, _label, _bg, _border = _res_cfg.get(_t_res, _res_cfg["unresolved"])

                        with _col:
                            st.markdown(
                                f"<div style='background:{_bg};border:1px solid {_border};"
                                "border-radius:8px;padding:8px 10px;font-size:12px;"
                                "color:#f1f5f9;min-height:110px'>"
                                f"<b>Reunião {_t_mnum}</b>"
                                + (f"<br><span style='color:#94a3b8;font-size:10px'>{_t_mdate}</span>" if _t_mdate else "")
                                + f"<br><br>{_emoji} <b>{_label}</b>"
                                + (f"<br><span style='font-size:10px;color:#cbd5e1'>{_t_stmt[:60]}…</span>" if len(_t_stmt) > 60 else f"<br><span style='font-size:10px;color:#cbd5e1'>{_t_stmt}</span>")
                                + "</div>",
                                unsafe_allow_html=True,
                            )
                            if _t_rat or _t_cav:
                                with st.popover("ℹ️"):
                                    st.markdown(f"**Questão:** {_t_stmt}")
                                    if _t_rat:
                                        st.info(f"**Resolução:** {_t_rat}")
                                    for _cav in _t_cav:
                                        st.warning(f"Ressalva: {_cav}")

                    # Linha de progresso visual
                    _statuses = [
                        (_tq.get("resolution") or {}).get("type", "unresolved")
                        for _tq in _thread_show
                    ]
                    _decided_at = next(
                        (i + 1 for i, s in enumerate(_statuses) if s == "decided"), None
                    )
                    if _decided_at:
                        _pct = int(_decided_at / len(_statuses) * 100)
                        _note = (
                            f"Decidido na {_decided_at}ª ocorrência"
                            if _decided_at > 1
                            else "Decidido na primeira ocorrência"
                        )
                        if _decided_at < len(_statuses):
                            _note += " — reaberto depois"
                        st.caption(f"🔁 {_note}")
                    elif all(s == "deferred" for s in _statuses):
                        st.caption("⏳ Adiado em todas as ocorrências — ainda sem decisão")
                    elif all(s == "unresolved" for s in _statuses):
                        st.caption("❓ Permanece sem resolução ao longo do projeto")

                    st.markdown("---")

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

        # ── Toggle de visualização ────────────────────────────────────────────
        ibis_view = st.radio(
            "Visualização",
            ["📋 Lista", "🕸️ Mapa Visual"],
            horizontal=True,
            key="ibis_view_toggle",
            label_visibility="collapsed",
        )

        st.caption(f"Exibindo {len(filtered_ibis)} questão(ões)")

        # ════════════════════════════════════════════════════════════════════
        # MODO LISTA (existente)
        # ════════════════════════════════════════════════════════════════════
        if ibis_view == "📋 Lista":
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

                    if res_type != "unresolved":
                        if resolution.get("rationale"):
                            st.info(f"**Resolução:** {resolution['rationale']}")
                        if resolution.get("with_caveats"):
                            st.warning("**Ressalvas:**\n" + "\n".join(f"- {c}" for c in resolution["with_caveats"]))
                    else:
                        st.error("Questão sem resolução ao final da reunião.")

        # ════════════════════════════════════════════════════════════════════
        # MODO MAPA VISUAL (pyvis)
        # ════════════════════════════════════════════════════════════════════
        else:
            _RES_BORDER = {
                "decided":    "#22c55e",   # verde
                "deferred":   "#fbbf24",   # âmbar
                "unresolved": "#f87171",   # vermelho
            }
            _GRAPH_H = 680

            # Opções do grafo
            with st.expander("⚙️ Opções do grafo", expanded=False):
                _g_col1, _g_col2 = st.columns(2)
                _cross_thresh = _g_col1.slider(
                    "Limiar de similaridade (cross-links entre reuniões)",
                    min_value=0.10, max_value=0.55, value=0.22, step=0.03,
                    key="ibis_cross_thresh",
                    help="Jaccard sobre tokens PT-BR. Menor valor = mais conexões; maior valor = só os debates mais parecidos.",
                )
                _show_args = _g_col2.checkbox(
                    "Mostrar argumentos (prós/contras) no grafo",
                    value=True, key="ibis_show_args",
                )

            if len(filtered_ibis) > 60:
                st.warning(
                    f"O filtro retornou {len(filtered_ibis)} questões. "
                    "Considere filtrar por reunião para um grafo mais legível."
                )

            try:
                import streamlit.components.v1 as _comp_ibis
                from pyvis.network import Network as _IbisNet

                _net = _IbisNet(
                    height=f"{_GRAPH_H}px",
                    width="100%",
                    bgcolor="#0d1b2a",
                    font_color="#f1f5f9",
                )

                for _q in filtered_ibis:
                    _qid     = _q.get("id", "Q?")
                    _stmt    = _q.get("statement", "")
                    _rb      = _q.get("raised_by", "")
                    _mnum    = _q.get("_meeting_number", "?")
                    _rt      = (_q.get("resolution") or {}).get("type", "unresolved")
                    _rationale = (_q.get("resolution") or {}).get("rationale", "")
                    _nid_q   = f"Q_{_mnum}_{_qid}"

                    _q_label = _stmt[:32] + ("…" if len(_stmt) > 32 else "")
                    _q_tip   = (
                        f"<b>{_qid}</b> · Reunião {_mnum}<br>"
                        f"{_stmt}<br><br>"
                        + (f"Levantada por: {_rb}<br>" if _rb else "")
                        + f"Status: {_rt}"
                        + (f"<br><i>{_rationale[:120]}</i>" if _rationale else "")
                    )
                    _net.add_node(
                        _nid_q,
                        label=_q_label,
                        title=_q_tip,
                        shape="ellipse",
                        size=22,
                        color={
                            "background": "#f97316",
                            "border":     _RES_BORDER.get(_rt, "#f87171"),
                            "highlight":  {"background": "#fb923c", "border": "#fff"},
                        },
                        font={"size": 11, "color": "#fff", "bold": True},
                        borderWidth=3,
                    )

                    for _alt in (_q.get("alternatives") or []):
                        _aid    = _alt.get("id", "A?")
                        _adesc  = _alt.get("description", "")
                        _pb     = _alt.get("proposed_by", "")
                        _chosen = _alt.get("was_chosen", False)
                        _nid_a  = f"A_{_mnum}_{_qid}_{_aid}"

                        _a_label = _adesc[:28] + ("…" if len(_adesc) > 28 else "")
                        _a_tip   = (
                            f"<b>{_aid}</b>"
                            + (" ✅ escolhida" if _chosen else "")
                            + f"<br>{_adesc}"
                            + (f"<br>Proposta por: {_pb}" if _pb else "")
                        )
                        _net.add_node(
                            _nid_a,
                            label=_a_label,
                            title=_a_tip,
                            shape="diamond",
                            size=16,
                            color={
                                "background": "#2563eb" if not _chosen else "#1d4ed8",
                                "border":     "#fbbf24" if _chosen else "#60a5fa",
                                "highlight":  {"background": "#3b82f6", "border": "#fff"},
                            },
                            font={"size": 10, "color": "#dbeafe"},
                            borderWidth=2 if not _chosen else 3,
                        )
                        _net.add_edge(
                            _nid_q, _nid_a,
                            color={"color": "#94a3b8", "highlight": "#fff"},
                            width=1.5,
                            arrows="to",
                            title="Alternativa proposta",
                        )

                        if _show_args:
                            for _i, _pro in enumerate(_alt.get("pros") or []):
                                _nid_p = f"P_{_mnum}_{_qid}_{_aid}_{_i}"
                                _p_label = str(_pro)[:26] + ("…" if len(str(_pro)) > 26 else "")
                                _net.add_node(
                                    _nid_p,
                                    label=_p_label,
                                    title=f"<b>A favor:</b> {_pro}",
                                    shape="dot",
                                    size=9,
                                    color={
                                        "background": "#16a34a",
                                        "border":     "#4ade80",
                                        "highlight":  {"background": "#22c55e", "border": "#fff"},
                                    },
                                    font={"size": 9, "color": "#dcfce7"},
                                    borderWidth=1,
                                )
                                _net.add_edge(
                                    _nid_a, _nid_p,
                                    color={"color": "#4ade80", "highlight": "#fff"},
                                    width=1,
                                    arrows="to",
                                    dashes=True,
                                    title="Argumento a favor",
                                )

                            for _j, _con in enumerate(_alt.get("cons") or []):
                                _nid_c = f"C_{_mnum}_{_qid}_{_aid}_{_j}"
                                _c_label = str(_con)[:26] + ("…" if len(str(_con)) > 26 else "")
                                _net.add_node(
                                    _nid_c,
                                    label=_c_label,
                                    title=f"<b>Contra:</b> {_con}",
                                    shape="dot",
                                    size=9,
                                    color={
                                        "background": "#b91c1c",
                                        "border":     "#f87171",
                                        "highlight":  {"background": "#ef4444", "border": "#fff"},
                                    },
                                    font={"size": 9, "color": "#fee2e2"},
                                    borderWidth=1,
                                )
                                _net.add_edge(
                                    _nid_a, _nid_c,
                                    color={"color": "#f87171", "highlight": "#fff"},
                                    width=1,
                                    arrows="to",
                                    dashes=True,
                                    title="Argumento contra",
                                )

                # ── Fase 2b: Cross-links entre reuniões ──────────────────────
                import re as _re_ibis
                import json as _json_ibis

                _IBIS_STOP = {
                    "a","o","as","os","de","do","da","dos","das","em","no","na",
                    "nos","nas","para","que","um","uma","uns","umas","e","ou","se",
                    "com","por","mas","é","ser","ter","ao","à","aos","às","não",
                    "como","mais","deve","há","esta","este","seu","sua","seus",
                    "suas","foi","ser","sido","sendo","está","estão","são","faz",
                    "fazer","pode","deve","devem","podem","será","vai","vão","use",
                    "the","of","to","in","is","it","be","as","at","or","an","and",
                }

                def _ibis_tokens(text: str) -> set:
                    words = _re_ibis.sub(r"[^\w\sáéíóúâêôãç]", " ", text.lower()).split()
                    return {w for w in words if w not in _IBIS_STOP and len(w) > 2}

                def _ibis_jaccard(a: str, b: str) -> float:
                    wa, wb = _ibis_tokens(a), _ibis_tokens(b)
                    if not wa or not wb:
                        return 0.0
                    return len(wa & wb) / len(wa | wb)

                # Índice de nós-questão para cross-link
                _q_idx: list[tuple] = []   # (nid, statement, meeting_id, meeting_num, q_id)
                for _q2 in filtered_ibis:
                    _qid2   = _q2.get("id", "Q?")
                    _mnum2  = _q2.get("_meeting_number", "?")
                    _mid2   = _q2.get("_meeting_id", "")
                    _stmt2  = _q2.get("statement", "")
                    _mtitle2 = _q2.get("_meeting_title", f"Reunião {_mnum2}")
                    _q_idx.append((f"Q_{_mnum2}_{_qid2}", _stmt2, _mid2, _mnum2, _mtitle2))

                _cross_found: list[dict] = []
                _seen_pairs: set = set()
                for _ia in range(len(_q_idx)):
                    for _ib in range(_ia + 1, len(_q_idx)):
                        _na, _sa, _mida, _mnuma, _mtitlea = _q_idx[_ia]
                        _nb, _sb, _midb, _mnumb, _mtitleb = _q_idx[_ib]
                        if _mida == _midb:
                            continue   # mesma reunião
                        _pair_key = tuple(sorted([_na, _nb]))
                        if _pair_key in _seen_pairs:
                            continue
                        _seen_pairs.add(_pair_key)
                        _sim = _ibis_jaccard(_sa, _sb)
                        if _sim >= _cross_thresh:
                            _cross_found.append({
                                "nid_a": _na, "nid_b": _nb,
                                "sim": _sim,
                                "stmt_a": _sa, "stmt_b": _sb,
                                "mnum_a": _mnuma, "mnum_b": _mnumb,
                                "mtitle_a": _mtitlea, "mtitle_b": _mtitleb,
                            })

                for _cl in _cross_found:
                    _w = max(1.5, _cl["sim"] * 6)
                    _net.add_edge(
                        _cl["nid_a"], _cl["nid_b"],
                        color={"color": "#a855f7", "highlight": "#d8b4fe"},
                        width=_w,
                        arrows="",
                        dashes=[6, 4],
                        title=(
                            f"<b>Debate recorrente</b> ({_cl['sim']:.0%} similaridade)<br>"
                            f"Reunião {_cl['mnum_a']}: {_cl['stmt_a'][:80]}<br>"
                            f"Reunião {_cl['mnum_b']}: {_cl['stmt_b'][:80]}"
                        ),
                    )

                # ── Opções de física ─────────────────────────────────────────
                _net.set_options(_json_ibis.dumps({
                    "physics": {
                        "enabled": True,
                        "barnesHut": {
                            "gravitationalConstant": -9000,
                            "centralGravity":        0.25,
                            "springLength":          130,
                            "springConstant":        0.035,
                            "damping":               0.12,
                            "avoidOverlap":          0.4,
                        },
                        "stabilization": {"iterations": 250, "fit": True},
                    },
                    "interaction": {
                        "hover":         True,
                        "tooltipDelay":  150,
                        "navigationButtons": False,
                        "keyboard":      True,
                        "zoomView":      True,
                    },
                    "edges": {"smooth": {"type": "dynamic"}},
                    "nodes": {"scaling": {"min": 8, "max": 28}},
                }))

                _html_ibis = _net.generate_html(local=False)

                # Legenda injetada no HTML
                _has_cross = bool(_cross_found)
                _legend_html = (
                    "<div style='position:absolute;top:10px;left:10px;background:#1e293b;"
                    "border:1px solid #334155;border-radius:8px;padding:10px 14px;"
                    "font-size:11px;color:#cbd5e1;z-index:999;line-height:1.8'>"
                    "<b style='color:#f1f5f9'>Legenda</b><br>"
                    "<span style='color:#f97316'>&#9650;</span> Issue/Questão &nbsp;"
                    "<span style='color:#3b82f6'>&#9670;</span> Alternativa &nbsp;"
                    "<span style='color:#22c55e'>&#9679;</span> A favor &nbsp;"
                    "<span style='color:#ef4444'>&#9679;</span> Contra<br>"
                    "<span style='color:#22c55e'>&#9646;</span> Decidida &nbsp;"
                    "<span style='color:#fbbf24'>&#9646;</span> Adiada &nbsp;"
                    "<span style='color:#f87171'>&#9646;</span> Em aberto"
                    + (
                        "<br><span style='color:#a855f7'>&#9473;&#9473;</span> Debate recorrente (cross-link)"
                        if _has_cross else ""
                    )
                    + "</div>"
                )
                _html_ibis = _html_ibis.replace("<body>", "<body style='margin:0'>" + _legend_html)

                _comp_ibis.html(_html_ibis, height=_GRAPH_H + 40, scrolling=False)

                # ── Tabela de cross-links detectados ─────────────────────────
                if _cross_found:
                    _cross_sorted = sorted(_cross_found, key=lambda x: x["sim"], reverse=True)
                    with st.expander(
                        f"🔗 {len(_cross_found)} debate(s) recorrente(s) detectado(s) entre reuniões",
                        expanded=True,
                    ):
                        st.caption(
                            "Questões com alto grau de similaridade textual em reuniões diferentes — "
                            "indício de um tema não resolvido que reaparece ao longo do projeto."
                        )
                        import pandas as _pd_cl
                        _cl_rows = []
                        for _cl in _cross_sorted:
                            _cl_rows.append({
                                "Reunião A": f"Reunião {_cl['mnum_a']}",
                                "Questão A": _cl["stmt_a"][:90] + ("…" if len(_cl["stmt_a"]) > 90 else ""),
                                "Reunião B": f"Reunião {_cl['mnum_b']}",
                                "Questão B": _cl["stmt_b"][:90] + ("…" if len(_cl["stmt_b"]) > 90 else ""),
                                "Similaridade": f"{_cl['sim']:.0%}",
                            })
                        st.dataframe(
                            _pd_cl.DataFrame(_cl_rows),
                            use_container_width=True,
                            hide_index=True,
                        )
                elif _cross_thresh <= 0.30:
                    st.caption(
                        f"Nenhum debate recorrente detectado com limiar {_cross_thresh:.0%}. "
                        "Tente reduzir o limiar nas opções do grafo."
                    )

            except ImportError:
                st.error(
                    "A biblioteca **pyvis** não está instalada. "
                    "Adicione `pyvis` ao `requirements.txt` e faça redeploy."
                )


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
