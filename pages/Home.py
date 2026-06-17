# pages/Home.py
# ─────────────────────────────────────────────────────────────────────────────
# Central de Operações — tela inicial exibida após o login.
#
# Seções:
#   1. Header de boas-vindas (nome, perfil, data)
#   2. KPIs globais do banco (contextos, reuniões, requisitos, processos BPMN)
#   3. Fluxo de trabalho visual (4 etapas com links)
#   4. Acesso rápido por área (esquerda) + Reuniões recentes (direita)
#   5. Agenda do Contexto (Google Calendar embed)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st

from ui.auth_gate import apply_auth_gate
from modules.auth import is_admin
from modules.i18n import t
from core.project_store import get_global_stats, list_recent_meetings, list_contexts, list_meetings_quality

apply_auth_gate()

# ── Identidade do usuário ─────────────────────────────────────────────────────
user_name   = st.session_state.get("_usuario_nome")  or st.session_state.get("_usuario_login", "Usuário")
user_role   = st.session_state.get("_role", "user")
tenant_name = st.session_state.get("_tenant_name", "")
domain_slug = st.session_state.get("_domain", "")
today_str   = datetime.today().strftime("%d/%m/%Y")

_ROLE_LABEL = {"master": "Master", "admin": "Admin", "user": "Usuário"}
_ROLE_COLOR = {"master": "#c97b1a", "admin": "#3b82f6", "user": "#64748b"}
role_label = _ROLE_LABEL.get(user_role, user_role.capitalize())
role_color = _ROLE_COLOR.get(user_role, "#64748b")

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Header ── */
.home-header {
    background: linear-gradient(135deg, #071428 0%, #0B1E3D 55%, #122848 100%);
    border-bottom: 3px solid #C97B1A;
    border-radius: 12px;
    padding: 1.6rem 2rem;
    margin-bottom: 1.4rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 4px 24px rgba(0,0,0,.35);
    position: relative;
    overflow: hidden;
}
.home-header::before {
    content: "";
    position: absolute;
    top: -40px; right: -40px;
    width: 180px; height: 180px;
    background: radial-gradient(circle, rgba(201,123,26,.12) 0%, transparent 70%);
    pointer-events: none;
}
.home-header .greeting {
    font-size: 1.55rem; font-weight: 700; color: #FAFAF8;
    letter-spacing: -.01em;
}
.home-header .sub { font-size: .82rem; color: #7A8EA8; margin-top: .3rem; }
.home-header .brand-badge {
    text-align: right; opacity: .7;
    font-size: .65rem; letter-spacing: .14em;
    text-transform: uppercase; color: #C97B1A;
    line-height: 1.6;
}
.home-header .brand-badge span {
    display: block; font-size: 1.6rem; opacity: .5; letter-spacing: 0;
}
.role-badge {
    display: inline-block; padding: 3px 10px; border-radius: 20px;
    font-size: .70rem; font-weight: 700; letter-spacing: .07em;
    margin-left: .6rem; vertical-align: middle;
}

/* ── KPI Cards ── */
.kpi-card {
    background: #0A1A32;
    border: 1px solid #1A3050;
    border-top: 3px solid var(--kpi-accent, #C97B1A);
    border-radius: 10px;
    padding: 1.1rem 1.2rem .9rem;
    text-align: center;
    transition: transform .15s, box-shadow .15s;
    box-shadow: 0 2px 10px rgba(0,0,0,.25);
}
.kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0,0,0,.35);
}
.kpi-card .kpi-icon { font-size: 1.3rem; margin-bottom: .2rem; }
.kpi-card .kpi-num  {
    font-size: 2.1rem; font-weight: 800; color: #FAFAF8;
    line-height: 1; letter-spacing: -.02em;
}
.kpi-card .kpi-lbl  {
    font-size: .68rem; color: #6A7E98; letter-spacing: .08em;
    text-transform: uppercase; margin-top: .35rem;
}

/* ── Section header ── */
.section-hdr {
    display: flex; align-items: center; gap: .6rem;
    font-size: .72rem; font-weight: 700; color: #6A7E98;
    letter-spacing: .12em; text-transform: uppercase;
    margin: 1.4rem 0 .6rem;
}
.section-hdr::after {
    content: ""; flex: 1;
    height: 1px;
    background: linear-gradient(90deg, #1e3a55 0%, transparent 100%);
}

/* ── Flow steps ── */
.flow-step {
    background: #0A1A32;
    border: 1px solid #1A3050;
    border-left: 3px solid var(--step-color, #C97B1A);
    border-radius: 10px;
    padding: 1rem 1rem .9rem;
    text-align: center;
    height: 100%;
    box-shadow: 0 2px 10px rgba(0,0,0,.2);
    transition: transform .15s, box-shadow .15s;
    position: relative;
}
.flow-step:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0,0,0,.3);
}
.flow-step .step-num {
    display: inline-flex; align-items: center; justify-content: center;
    width: 26px; height: 26px;
    border-radius: 50%;
    background: var(--step-color, #C97B1A);
    color: #fff; font-size: .72rem; font-weight: 800;
    margin-bottom: .5rem;
    box-shadow: 0 2px 6px rgba(0,0,0,.3);
}
.flow-step .step-icon  { font-size: 1.25rem; display: block; margin-bottom: .3rem; }
.flow-step .step-title { font-size: .88rem; font-weight: 700; color: #FAFAF8; }
.flow-step .step-desc  { font-size: .70rem; color: #7A8EA8; margin-top: .3rem; line-height: 1.45; }

/* ── Flow arrow ── */
.flow-arrow {
    text-align: center; padding-top: 2.1rem;
    color: #C97B1A; font-size: 1.3rem; opacity: .7;
}

/* ── Area cards ── */
.area-card {
    background: #0A1A32;
    border: 1px solid #1A3050;
    border-radius: 10px;
    padding: 1rem 1.2rem 1rem;
    margin-bottom: .8rem;
    box-shadow: 0 2px 10px rgba(0,0,0,.2);
}
.area-card .area-title {
    font-size: .70rem; font-weight: 700; color: #C97B1A;
    letter-spacing: .1em; text-transform: uppercase;
    margin-bottom: .7rem; display: flex; align-items: center; gap: .4rem;
}
.area-card .area-title::after {
    content: ""; flex: 1; height: 1px; background: #1A3050;
}

/* ── Meeting cards ── */
.mtg-card {
    background: #0A1A32;
    border: 1px solid #1A3050;
    border-left: 3px solid #2A5080;
    border-radius: 10px;
    padding: .8rem 1rem;
    margin-bottom: .5rem;
    box-shadow: 0 2px 8px rgba(0,0,0,.18);
    transition: border-left-color .15s;
}
.mtg-card:hover { border-left-color: #C97B1A; }
.mtg-card .mtg-num   { font-size: .65rem; color: #C97B1A; font-weight: 700; letter-spacing: .08em; }
.mtg-card .mtg-title { font-size: .88rem; font-weight: 600; color: #FAFAF8; margin-top: .1rem; }
.mtg-card .mtg-meta  { font-size: .68rem; color: #6A7E98; margin-top: .25rem; }

/* ── Footer ── */
.home-footer {
    margin-top: 2.5rem;
    padding-top: .8rem;
    border-top: 1px solid #1A3050;
    text-align: center;
    font-size: .68rem;
    color: #3A5070;
    letter-spacing: .04em;
}
</style>
""", unsafe_allow_html=True)

# ── 1. Header ─────────────────────────────────────────────────────────────────
tenant_str   = f" · {tenant_name}" if tenant_name else ""
domain_badge = (
    f'''<span style="display:inline-block;margin-left:.8rem;padding:3px 10px;
    border-radius:20px;font-size:.68rem;font-weight:700;letter-spacing:.1em;
    background:#C97B1A22;color:#C97B1A;border:1px solid #C97B1A55;
    text-transform:uppercase;vertical-align:middle;">{domain_slug}</span>'''
    if domain_slug else ""
)
st.markdown(f"""
<div class="home-header">
  <div>
    <div class="greeting">
      {t("welcome", name=user_name)}
      <span class="role-badge"
            style="background:{role_color}22;color:{role_color};border:1px solid {role_color}55">
        {role_label}
      </span>
      {domain_badge}
    </div>
    <div class="sub">Process2Diagram{tenant_str} &nbsp;·&nbsp; {today_str}</div>
  </div>
  <div class="brand-badge">
    <span>⚙</span>
    Process2Diagram<br>{t("ops_center")}
  </div>
</div>
""", unsafe_allow_html=True)

# ── Contexto de Trabalho ─────────────────────────────────────────────────────
@st.cache_data(ttl=120, show_spinner=False)
def _load_projects(tenant_id: str | None = None):
    return list_contexts(tenant_id=tenant_id)

_all_projects = _load_projects(tenant_id=st.session_state.get("_tenant_id"))
_ap_id   = st.session_state.get("active_project_id")
_ap_name = st.session_state.get("active_project_name", "")

# Auto-selecionar quando houver apenas 1 contexto e nenhum ativo
if _all_projects and not _ap_id and len(_all_projects) == 1:
    _p = _all_projects[0]
    st.session_state["active_project_id"]   = _p["id"]
    st.session_state["active_project_name"] = _p["name"]
    if _p.get("sigla"):
        st.session_state["prefix"] = _p["sigla"].strip() + "_"
    _ap_id   = _p["id"]
    _ap_name = _p["name"]

if _ap_id:
    _col_badge, _col_change = st.columns([5, 1])
    with _col_badge:
        st.success(f"📁 **{t('working_context')}:** {_ap_name}")
    with _col_change:
        if st.button(t("change"), key="home_change_proj", use_container_width=True):
            st.session_state["active_project_id"]   = None
            st.session_state["active_project_name"] = ""
            st.rerun()
elif _all_projects:
    with st.container(border=True):
        st.markdown(f"#### {t('select_context')}")
        st.caption(t("select_context_caption"))
        _proj_map = {p["name"]: p for p in _all_projects}
        _proj_sel = st.selectbox(
            t("context_label"), list(_proj_map.keys()),
            key="home_proj_sel", label_visibility="collapsed",
        )
        if st.button(t("activate"), key="home_activate_proj",
                     type="primary", use_container_width=True):
            _p = _proj_map[_proj_sel]
            st.session_state["active_project_id"]   = _p["id"]
            st.session_state["active_project_name"] = _p["name"]
            if _p.get("sigla"):
                st.session_state["prefix"] = _p["sigla"].strip() + "_"
            _load_projects.clear()  # invalida cache do tenant atual
            st.rerun()
else:
    st.info(t("no_context_found"))

# ── 2. KPIs ───────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def _load_stats():
    return get_global_stats()

@st.cache_data(ttl=60, show_spinner=False)
def _load_recent(project_id: str | None = None):
    return list_recent_meetings(limit=6, project_id=project_id)

stats  = _load_stats()
recent = _load_recent(_ap_id)

def _fmt(n: int, available: bool) -> str:
    return str(n) if available else "—"

_KPI_ACCENTS = ["#C97B1A", "#3b82f6", "#10b981", "#8b5cf6", "#ec4899"]
_KPI_ICONS   = ["📁", "🗓️", "📝", "📐", "📄"]
_KPI_DATA    = [
    ("n_projects",   t("kpi_contexts")),
    ("n_meetings",   t("kpi_meetings")),
    ("n_reqs",       t("kpi_requirements")),
    ("n_bpmn_procs", t("kpi_bpmn")),
    ("n_documents",  t("kpi_documents")),
]

cols = st.columns(5)
for col, (key, label), accent, icon in zip(cols, _KPI_DATA, _KPI_ACCENTS, _KPI_ICONS):
    val = _fmt(stats.get(key, 0), stats.get("available", False))
    with col:
        st.markdown(
            f'<div class="kpi-card" style="--kpi-accent:{accent}">'
            f'<div class="kpi-icon">{icon}</div>'
            f'<div class="kpi-num">{val}</div>'
            f'<div class="kpi-lbl">{label}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

if not stats["available"]:
    st.caption(t("kpi_unavailable"))

# ── 3. Fluxo de trabalho ──────────────────────────────────────────────────────
st.markdown(f'<div class="section-hdr">{t("workflow_title")}</div>', unsafe_allow_html=True)

_STEPS = [
    ("#C97B1A", "1", "📥", t("step1_title"), t("step1_desc")),
    ("#3b82f6", "2", "✅", t("step2_title"), t("step2_desc")),
    ("#10b981", "3", "🔍", t("step3_title"), t("step3_desc")),
    ("#8b5cf6", "4", "📤", t("step4_title"), t("step4_desc")),
]

f1, arr1, f2, arr2, f3, arr3, f4 = st.columns([4, 1, 4, 1, 4, 1, 4])

for col, arrow_col, (color, num, icon, title, desc) in zip(
    [f1, f2, f3, f4],
    [None, arr1, arr2, arr3],
    _STEPS,
):
    if arrow_col is not None:
        with arrow_col:
            st.markdown(
                f'<div class="flow-arrow">›</div>',
                unsafe_allow_html=True,
            )
    with col:
        st.markdown(
            f'<div class="flow-step" style="--step-color:{color}">'
            f'<div class="step-num">{num}</div>'
            f'<div class="step-icon">{icon}</div>'
            f'<div class="step-title">{title}</div>'
            f'<div class="step-desc">{desc}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

# ── 4. Acesso rápido + Reuniões recentes ──────────────────────────────────────
st.markdown(f'<div class="section-hdr">{t("quick_access")}</div>', unsafe_allow_html=True)

col_nav, col_recent = st.columns([3, 2], gap="large")

# ── Acesso rápido ──────────────────────────────────────────────────────────────
with col_nav:

    # Pipeline
    st.markdown(f'<div class="area-card"><div class="area-title">{t("area_pipeline")}</div>', unsafe_allow_html=True)
    b1, b2, b3 = st.columns(3)
    with b1:
        st.page_link("pages/Pipeline.py",   label=t("btn_new_transcript"), use_container_width=True)
    with b2:
        st.page_link("pages/Diagramas.py",  label=t("btn_diagrams"),       use_container_width=True)
    with b3:
        st.page_link("pages/BpmnEditor.py", label=t("btn_bpmn_editor"),    use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Análise
    st.markdown(f'<div class="area-card"><div class="area-title">{t("area_analysis")}</div>', unsafe_allow_html=True)
    b4, b5, b6, b7 = st.columns(4)
    with b4:
        st.page_link("pages/Assistente.py",    label=t("btn_assistant"),  use_container_width=True)
    with b5:
        st.page_link("pages/ValidationHub.py", label=t("btn_validation"), use_container_width=True)
    with b6:
        st.page_link("pages/Artefatos.py",     label=t("btn_artifacts"),  use_container_width=True)
    with b7:
        st.page_link("pages/MeetingROI.py",    label=t("btn_roi"),        use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Sistema
    st.markdown(f'<div class="area-card"><div class="area-title">{t("area_system")}</div>', unsafe_allow_html=True)
    if is_admin():
        s1, s2, s3, s4 = st.columns(4)
        with s1:
            st.page_link("pages/Settings.py",         label=t("btn_settings"),      use_container_width=True)
        with s2:
            st.page_link("pages/DatabaseOverview.py", label=t("btn_database"),      use_container_width=True)
        with s3:
            st.page_link("pages/MasterAdmin.py",      label=t("btn_master_admin"),  use_container_width=True)
        with s4:
            st.page_link("pages/CostEstimator.py",    label=t("btn_costs"),         use_container_width=True)
    else:
        s1, s2 = st.columns(2)
        with s1:
            st.page_link("pages/Settings.py",      label=t("btn_settings"),      use_container_width=True)
        with s2:
            st.page_link("pages/CostEstimator.py", label=t("btn_cost_estimate"), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Orientações / Guides
    st.markdown(f'<div class="area-card"><div class="area-title">{t("area_guides")}</div>', unsafe_allow_html=True)
    g1, g2 = st.columns(2)
    with g1:
        st.page_link("pages/Orientacoes_ComoIniciar.py",  label=t("btn_how_to_start"),  use_container_width=True)
    with g2:
        st.page_link("pages/Orientacoes_Arquiteturas.py", label=t("btn_architectures"), use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ── Reuniões recentes ─────────────────────────────────────────────────────────
with col_recent:
    st.markdown(f'<div class="section-hdr" style="margin-top:0">{t("recent_meetings")}</div>', unsafe_allow_html=True)

    if not recent:
        st.caption(t("no_meetings"))
        st.page_link("pages/Pipeline.py", label=t("btn_process_first"))
    else:
        for mtg in recent:
            num   = mtg.get("meeting_number", "?")
            title = mtg.get("title", "(sem título)")
            date  = mtg.get("meeting_date", "—")
            proj  = _ap_name or "—"

            label_short = title if len(title) <= 38 else title[:35] + "…"
            _mtg_label = t("meeting_label", num=num)

            st.markdown(f"""
<div class="mtg-card">
  <div class="mtg-num">{_mtg_label}</div>
  <div class="mtg-title">{label_short}</div>
  <div class="mtg-meta">📁 {proj} &nbsp;·&nbsp; 📅 {date}</div>
</div>""", unsafe_allow_html=True)

            lc1, lc2, lc3 = st.columns(3)
            with lc1:
                st.page_link(
                    "pages/Assistente.py",
                    label=t("mtg_link_assistant"),
                    help=t("mtg_help_assistant"),
                    use_container_width=True,
                )
            with lc2:
                st.page_link(
                    "pages/ValidationHub.py",
                    label=t("mtg_link_validation"),
                    help=t("mtg_help_validation"),
                    use_container_width=True,
                )
            with lc3:
                st.page_link(
                    "pages/BpmnEditor.py",
                    label=t("mtg_link_editor"),
                    help=t("mtg_help_editor"),
                    use_container_width=True,
                )

        st.markdown(
            "<div style='text-align:right;margin-top:.4rem'>",
            unsafe_allow_html=True,
        )
        st.page_link("pages/Assistente.py", label=t("mtg_link_all"))
        st.markdown("</div>", unsafe_allow_html=True)

# ── 5. Radar de Qualidade + Export ZIP ───────────────────────────────────────
if _ap_id:
    @st.cache_data(ttl=120, show_spinner=False)
    def _load_quality(project_id: str):
        return list_meetings_quality(project_id)

    _quality_data = _load_quality(_ap_id)

    if _quality_data:
        _col_radar, _col_export = st.columns([3, 2], gap="large")

        with _col_radar:
            st.markdown(f'<div class="section-hdr">📡 Radar de Qualidade do Projeto</div>', unsafe_allow_html=True)
            try:
                import plotly.graph_objects as _go
                _n   = len(_quality_data)
                _pct = lambda key: round(100 * sum(1 for m in _quality_data if m.get(key)) / max(1, _n))

                _dims  = ["BPMN", "Ata", "DMN", "IBIS", "Relatório"]
                _vals  = [_pct("has_bpmn"), _pct("has_minutes"), _pct("has_dmn"),
                          _pct("has_ibis"), _pct("has_synthesizer")]
                _avg   = round(sum(_vals) / len(_vals))

                _fig = _go.Figure()
                _fig.add_trace(_go.Scatterpolar(
                    r=_vals + [_vals[0]], theta=_dims + [_dims[0]],
                    fill="toself", name=f"Cobertura (n={_n})",
                    line=dict(color="#C97B1A", width=2.5),
                    fillcolor="rgba(201,123,26,0.13)",
                ))
                _fig.update_layout(
                    polar=dict(
                        bgcolor="#0A1A32",
                        angularaxis=dict(color="#94a3b8", linecolor="#1e3a55",
                                         tickfont=dict(size=11, color="#94a3b8")),
                        radialaxis=dict(visible=True, range=[0, 100], color="#475569",
                                        gridcolor="#1e3a55", ticksuffix="%",
                                        tickfont=dict(size=9, color="#475569")),
                    ),
                    paper_bgcolor="#0d1b2a", plot_bgcolor="#0d1b2a",
                    font=dict(color="#94a3b8", size=11),
                    legend=dict(bgcolor="#0A1A32", bordercolor="#1e3a55"),
                    margin=dict(t=20, b=10, l=30, r=30),
                    height=300,
                )
                st.plotly_chart(_fig, use_container_width=True, key="home_radar")
                st.caption(f"Cobertura média de artefatos: **{_avg}%** em {_n} reunião(ões).")
            except Exception:
                # Fallback: simple metrics
                _cols_r = st.columns(5)
                for _ci, (_lbl, _key) in enumerate(zip(
                    ["BPMN", "Ata", "DMN", "IBIS", "Relatório"],
                    ["has_bpmn", "has_minutes", "has_dmn", "has_ibis", "has_synthesizer"],
                )):
                    _n = len(_quality_data)
                    _v = sum(1 for m in _quality_data if m.get(_key))
                    _cols_r[_ci].metric(_lbl, f"{_v}/{_n}")

        with _col_export:
            st.markdown(f'<div class="section-hdr">📦 Exportar Projeto</div>', unsafe_allow_html=True)
            st.caption("Gera um arquivo ZIP com todos os artefatos do projeto ativo.")

            if st.button("⬇️ Gerar ZIP do Projeto", key="home_gen_zip", use_container_width=True):
                import io as _io
                import zipfile as _zf
                from core.project_store import (
                    list_bpmn_processes, list_bpmn_versions,
                    list_requirements_light, list_meetings as _list_mtgs_full,
                )

                with st.spinner("Compilando artefatos…"):
                    try:
                        _buf = _io.BytesIO()
                        _fname_proj = (_ap_name or "projeto").replace(" ", "_")
                        _procs         = list_bpmn_processes(_ap_id)
                        _reqs          = list_requirements_light(_ap_id)
                        _meetings_full = _list_mtgs_full(_ap_id)

                        with _zf.ZipFile(_buf, "w", _zf.ZIP_DEFLATED) as _zzip:
                            # ── BPMN XMLs ──
                            for _proc in _procs:
                                _proc_name  = (_proc.get("name") or "processo").replace(" ", "_")
                                _proc_vers  = list_bpmn_versions(_ap_id)
                                _proc_v     = [v for v in _proc_vers if v.get("process_id") == _proc.get("id") and v.get("is_current")]
                                if _proc_v and _proc_v[0].get("bpmn_xml"):
                                    _zzip.writestr(
                                        f"bpmn/{_proc_name}.xml",
                                        _proc_v[0]["bpmn_xml"],
                                    )

                            # ── Atas (minutes_md) ──
                            for _m in _meetings_full:
                                _mnum  = _m.get("meeting_number", "?")
                                _mtit  = (_m.get("title") or f"reuniao_{_mnum}").replace(" ", "_")
                                _mmins = _m.get("minutes_md") or ""
                                if _mmins:
                                    _zzip.writestr(f"atas/reuniao_{_mnum}_{_mtit[:30]}.md", _mmins)

                            # ── Requisitos JSON ──
                            import json as _json_zip
                            if _reqs:
                                _zzip.writestr(
                                    "requisitos/requisitos.json",
                                    _json_zip.dumps(_reqs, ensure_ascii=False, indent=2),
                                )

                            # ── README ──
                            _zzip.writestr(
                                "README.md",
                                f"# {_ap_name} — Exportação Process2Diagram\n\n"
                                f"Projeto: {_ap_name}\n"
                                f"Reuniões: {len(_meetings_full)}\n"
                                f"Requisitos: {len(_reqs)}\n"
                                f"Processos BPMN: {len(_procs)}\n",
                            )

                        _buf.seek(0)
                        st.session_state["home_zip_bytes"] = _buf.read()
                        st.session_state["home_zip_fname"] = f"{_fname_proj}_export.zip"
                    except Exception as _ze:
                        st.error(f"Erro ao gerar ZIP: {_ze}")

            if st.session_state.get("home_zip_bytes"):
                st.download_button(
                    label="📥 Download ZIP",
                    data=st.session_state["home_zip_bytes"],
                    file_name=st.session_state.get("home_zip_fname", "export.zip"),
                    mime="application/zip",
                    key="home_dl_zip",
                    use_container_width=True,
                )
                st.caption(
                    "Contém: BPMNs (.xml), atas (.md), requisitos (.json) e README."
                )

# ── 7. Agenda do Contexto ────────────────────────────────────────────────────
st.markdown('<div class="section-hdr">📅 Agenda do Contexto</div>', unsafe_allow_html=True)

try:
    from urllib.parse import quote
    from modules.calendar_client import _load_calendar_id, calendar_configured
    if calendar_configured():
        cal_id  = _load_calendar_id()
        cal_url = (
            "https://calendar.google.com/calendar/embed"
            f"?src={quote(cal_id)}&ctz=America%2FSao_Paulo"
            "&showTitle=0&showNav=1&showPrint=0&showTabs=1&showCalendars=0"
        )
        import streamlit.components.v1 as _components
        _components.html(
            f'<iframe src="{cal_url}" '
            f'style="border:0;width:100%;height:600px;border-radius:10px" '
            f'frameborder="0" scrolling="no"></iframe>',
            height=620,
        )
    else:
        st.caption("📅 Agenda não configurada. Configure Google Calendar em **Sistema → Configurações**.")
except Exception as _cal_exc:
    st.caption(f"📅 Agenda indisponível: {_cal_exc}")

# ── Rodapé ────────────────────────────────────────────────────────────────────
_APP_VERSION = "v4.31"
st.markdown(
    f'<div class="home-footer">'
    f'Process2Diagram {_APP_VERSION} &nbsp;·&nbsp; Multi-agent process intelligence platform'
    f'</div>',
    unsafe_allow_html=True,
)
