# pages/ReqTracker.py
# ─────────────────────────────────────────────────────────────────────────────
# Rastreador de Requisitos — painel consolidado por projeto.
# Mostra requisitos, histórico de versões e contradições detectadas.
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
from core.project_store import (
    list_projects, list_meetings, list_requirements, list_contradictions,
    list_sbvr_terms, list_sbvr_rules,
)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Req Tracker — Process2Diagram",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
.badge-active       { background:#0d4f2e; color:#4ade80; }
.badge-revised      { background:#4a3000; color:#fbbf24; }
.badge-contradicted { background:#4a0d0d; color:#f87171; }
.badge-deprecated   { background:#2a2a2a; color:#9ca3af; }
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
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 📋 Rastreador de Requisitos")

if not supabase_configured():
    st.error("⚙️ Supabase não configurado. Adicione as credenciais em Settings → Secrets.")
    st.stop()

# ── Seleção de projeto ────────────────────────────────────────────────────────
projects = list_projects()
if not projects:
    st.info("Nenhum projeto encontrado. Execute pelo menos uma reunião no app principal.")
    st.stop()

proj_map = {p["name"]: p for p in projects}
selected_name = st.selectbox(
    "Selecione o projeto",
    list(proj_map.keys()),
    key="rt_project_sel",
)
project = proj_map[selected_name]
project_id = project["id"]

# ── Carrega dados ─────────────────────────────────────────────────────────────
meetings       = list_meetings(project_id)
requirements   = list_requirements(project_id)
contradictions = list_contradictions(project_id)
sbvr_terms     = list_sbvr_terms(project_id)
sbvr_rules     = list_sbvr_rules(project_id)

meet_map = {m["id"]: m for m in meetings}

def meet_label(mid: str | None) -> str:
    if not mid or mid not in meet_map:
        return "—"
    m = meet_map[mid]
    dt = m.get("meeting_date") or ""
    return f"Reunião {m.get('meeting_number', '?')} — {m.get('title', '')} ({dt})"

# ── Métricas resumo ───────────────────────────────────────────────────────────
n_total        = len(requirements)
n_contradicted = sum(1 for r in requirements if r.get("status") == "contradicted")
n_revised      = sum(1 for r in requirements if r.get("status") == "revised")
n_meetings     = len(meetings)

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Total de Requisitos", n_total)
c2.metric("Reuniões", n_meetings)
c3.metric("Revisados", n_revised)
c4.metric("⚠️ Contradições", n_contradicted, delta=None,
          delta_color="off" if n_contradicted == 0 else "inverse")
c5.metric("Termos SBVR", len(sbvr_terms))
c6.metric("Regras SBVR", len(sbvr_rules))

st.markdown("---")

# ── Abas principais ───────────────────────────────────────────────────────────
tab_req, tab_contra, tab_hist, tab_meet, tab_sbvr = st.tabs([
    "📝 Requisitos",
    f"⚠️ Contradições ({len(contradictions)})",
    "📅 Histórico",
    "🗓️ Reuniões",
    f"📖 SBVR ({len(sbvr_terms)}T · {len(sbvr_rules)}R)",
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — REQUISITOS
# ════════════════════════════════════════════════════════════════════════════
with tab_req:
    if not requirements:
        st.info("Nenhum requisito registrado para este projeto.")
    else:
        # Filtros
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            status_opts = ["Todos", "active", "revised", "contradicted", "deprecated"]
            sel_status = st.selectbox("Status", status_opts, key="rt_status")
        with col_f2:
            types = sorted({r.get("req_type", "") for r in requirements if r.get("req_type")})
            sel_type = st.selectbox("Tipo", ["Todos"] + types, key="rt_type")
        with col_f3:
            prios = sorted({r.get("priority", "") for r in requirements if r.get("priority")})
            sel_prio = st.selectbox("Prioridade", ["Todos"] + prios, key="rt_prio")

        # Filtra
        filtered = requirements
        if sel_status != "Todos":
            filtered = [r for r in filtered if r.get("status") == sel_status]
        if sel_type != "Todos":
            filtered = [r for r in filtered if r.get("req_type") == sel_type]
        if sel_prio != "Todos":
            filtered = [r for r in filtered if r.get("priority") == sel_prio]

        st.caption(f"Exibindo {len(filtered)} de {n_total} requisito(s)")
        st.markdown("")

        _STATUS_BADGE = {
            "active":       ("badge-active",       "Ativo"),
            "revised":      ("badge-revised",       "Revisado"),
            "contradicted": ("badge-contradicted",  "Contradição"),
            "deprecated":   ("badge-deprecated",    "Depreciado"),
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
                    st.markdown(f'<span class="badge {badge_cls}">{badge_txt}</span>',
                                unsafe_allow_html=True)
                    st.markdown(f"**Descrição:** {req.get('description', '—')}")
                with col_m:
                    st.caption(f"🏁 {meet_label(req.get('first_meeting_id'))}")
                    st.caption(f"🔄 {meet_label(req.get('last_meeting_id'))}")
                    st.caption(f"📌 {n_ver} versão(ões)")

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
                        if v.get("contradiction_detail"):
                            st.error(v["contradiction_detail"])

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — CONTRADIÇÕES
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
# TAB 3 — HISTÓRICO POR REQUISITO
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
                if v.get("contradiction_detail"):
                    st.markdown(
                        f'<span style="color:#f87171">⚠️ {v["contradiction_detail"]}</span>',
                        unsafe_allow_html=True,
                    )
                st.markdown("</div>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — REUNIÕES
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

                # Requisitos originados nesta reunião
                reqs_here = [
                    r for r in requirements
                    if r.get("first_meeting_id") == m["id"]
                ]
                if reqs_here:
                    st.markdown(f"**{len(reqs_here)} requisito(s) originado(s) nesta reunião:**")
                    for r in reqs_here:
                        st.markdown(
                            f"- `REQ-{r['req_number']:03d}` {r.get('title','')}"
                        )

                # Termos/regras SBVR desta reunião
                terms_here = [t for t in sbvr_terms if t.get("meeting_id") == m["id"]]
                rules_here = [r for r in sbvr_rules if r.get("meeting_id") == m["id"]]
                if terms_here or rules_here:
                    st.markdown(f"**SBVR:** {len(terms_here)} termo(s) · {len(rules_here)} regra(s)")

# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — SBVR
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

        # ── Vocabulário ──────────────────────────────────────────────────────
        with col_t:
            st.markdown(f"### 📚 Vocabulário ({len(sbvr_terms)} termos)")

            # Filtro por reunião
            meet_ids = sorted({t.get("meeting_id") for t in sbvr_terms if t.get("meeting_id")})
            meet_labels_sbvr = {"Todas": None}
            for mid in meet_ids:
                meet_labels_sbvr[meet_label(mid)] = mid
            sel_meet_t = st.selectbox("Reunião", list(meet_labels_sbvr.keys()), key="sbvr_meet_t")
            filtered_terms = sbvr_terms if not meet_labels_sbvr[sel_meet_t] else [
                t for t in sbvr_terms if t.get("meeting_id") == meet_labels_sbvr[sel_meet_t]
            ]

            # Filtro por categoria
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
                m_num = meet_info.get("meeting_number", "?")
                with st.expander(f"**{t.get('term', '—')}**", expanded=False):
                    st.markdown(
                        f'<span class="badge {badge_cls}">{badge_txt}</span>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**Definição:** {t.get('definition', '—')}")
                    st.caption(f"🗓️ Reunião {m_num}")

        # ── Regras ───────────────────────────────────────────────────────────
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
                m_num = meet_info.get("meeting_number", "?")
                with st.expander(f"**{rule_id}**", expanded=False):
                    st.markdown(
                        f'<span class="badge {badge_cls}">{badge_txt}</span>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"{r.get('statement', '—')}")
                    footer = f"🗓️ Reunião {m_num}"
                    if r.get("source"):
                        footer += f" · 👤 {r['source']}"
                    st.caption(footer)
