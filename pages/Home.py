# pages/Home.py
# ─────────────────────────────────────────────────────────────────────────────
# Central de Operações — tela inicial exibida após o login.
#
# Seções:
#   1. Header de boas-vindas (nome, perfil, data)
#   2. KPIs globais do banco (projetos, reuniões, requisitos, processos BPMN)
#   3. Fluxo de trabalho visual (4 etapas com links)
#   4. Acesso rápido por área (esquerda) + Reuniões recentes (direita)
#   5. Agenda do Projeto (Google Calendar embed)
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
from core.project_store import get_global_stats, list_recent_meetings

apply_auth_gate()

# ── Identidade do usuário ─────────────────────────────────────────────────────
user_name   = st.session_state.get("_usuario_nome")  or st.session_state.get("_usuario_login", "Usuário")
user_role   = st.session_state.get("_role", "user")
tenant_name = st.session_state.get("_tenant_name", "")
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
tenant_str = f" · {tenant_name}" if tenant_name else ""
st.markdown(f"""
<div class="home-header">
  <div>
    <div class="greeting">
      Bem-vindo(a), {user_name}
      <span class="role-badge"
            style="background:{role_color}22;color:{role_color};border:1px solid {role_color}55">
        {role_label}
      </span>
    </div>
    <div class="sub">Process2Diagram{tenant_str} &nbsp;·&nbsp; {today_str}</div>
  </div>
  <div class="brand-badge">
    <span>⚙</span>
    Process2Diagram<br>Central de Operações
  </div>
</div>
""", unsafe_allow_html=True)

# ── 2. KPIs ───────────────────────────────────────────────────────────────────
@st.cache_data(ttl=60, show_spinner=False)
def _load_stats():
    return get_global_stats()

@st.cache_data(ttl=60, show_spinner=False)
def _load_recent():
    return list_recent_meetings(limit=6)

stats  = _load_stats()
recent = _load_recent()

def _fmt(n: int, available: bool) -> str:
    return str(n) if available else "—"

_KPI_ACCENTS = ["#C97B1A", "#3b82f6", "#10b981", "#8b5cf6"]
_KPI_ICONS   = ["📁", "🗓️", "📝", "📐"]
_KPI_DATA    = [
    ("n_projects",   "Projetos"),
    ("n_meetings",   "Reuniões"),
    ("n_reqs",       "Requisitos"),
    ("n_bpmn_procs", "Processos BPMN"),
]

cols = st.columns(4)
for col, (key, label), accent, icon in zip(cols, _KPI_DATA, _KPI_ACCENTS, _KPI_ICONS):
    val = _fmt(stats[key], stats["available"])
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
    st.caption("⚠️ Banco de dados não configurado — KPIs indisponíveis. Configure em **Sistema → Configurações**.")

# ── 3. Fluxo de trabalho ──────────────────────────────────────────────────────
st.markdown('<div class="section-hdr">Fluxo de trabalho</div>', unsafe_allow_html=True)

_STEPS = [
    ("#C97B1A", "1", "📥", "Processar",
     "Cole ou faça upload de uma transcrição e execute o pipeline de agentes"),
    ("#3b82f6", "2", "✅", "Validar",
     "Revise e aprove requisitos, termos SBVR, regras e diagramas BPMN"),
    ("#10b981", "3", "🔍", "Analisar",
     "Converse com o Assistente, acompanhe requisitos e indicadores de ROI"),
    ("#8b5cf6", "4", "📤", "Exportar",
     "Edite diagramas BPMN, visualize fluxos e exporte atas, relatórios e XML"),
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
st.markdown('<div class="section-hdr">Acesso rápido</div>', unsafe_allow_html=True)

col_nav, col_recent = st.columns([3, 2], gap="large")

# ── Acesso rápido ──────────────────────────────────────────────────────────────
with col_nav:

    # Pipeline
    st.markdown('<div class="area-card"><div class="area-title">⚡ Pipeline</div>', unsafe_allow_html=True)
    b1, b2, b3 = st.columns(3)
    with b1:
        st.page_link("pages/Pipeline.py",   label="🚀 Nova Transcrição",    use_container_width=True)
    with b2:
        st.page_link("pages/Diagramas.py",  label="📐 Diagramas",          use_container_width=True)
    with b3:
        st.page_link("pages/BpmnEditor.py", label="✏️ Editor BPMN",        use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Análise
    st.markdown('<div class="area-card"><div class="area-title">🔍 Análise</div>', unsafe_allow_html=True)
    b4, b5, b6, b7 = st.columns(4)
    with b4:
        st.page_link("pages/Assistente.py",     label="💬 Assistente",    use_container_width=True)
    with b5:
        st.page_link("pages/ValidationHub.py",  label="✅ Validação",     use_container_width=True)
    with b6:
        st.page_link("pages/ReqTracker.py",     label="📋 Req. Tracker",  use_container_width=True)
    with b7:
        st.page_link("pages/MeetingROI.py",     label="📊 ROI-TR",        use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Sistema
    st.markdown('<div class="area-card"><div class="area-title">⚙️ Sistema</div>', unsafe_allow_html=True)
    if is_admin():
        s1, s2, s3, s4 = st.columns(4)
        with s1:
            st.page_link("pages/Settings.py",         label="⚙️ Configurações",  use_container_width=True)
        with s2:
            st.page_link("pages/DatabaseOverview.py", label="🗄️ Banco de Dados", use_container_width=True)
        with s3:
            st.page_link("pages/MasterAdmin.py",      label="🛡️ Master Admin",   use_container_width=True)
        with s4:
            st.page_link("pages/CostEstimator.py",    label="💰 Custos",         use_container_width=True)
    else:
        s1, s2 = st.columns(2)
        with s1:
            st.page_link("pages/Settings.py",      label="⚙️ Configurações",       use_container_width=True)
        with s2:
            st.page_link("pages/CostEstimator.py", label="💰 Estimativa de Custo", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Orientações
    st.markdown('<div class="area-card"><div class="area-title">📖 Orientações</div>', unsafe_allow_html=True)
    g1, g2 = st.columns(2)
    with g1:
        st.page_link("pages/Orientacoes_ComoIniciar.py",  label="📖 Como Iniciar",  use_container_width=True)
    with g2:
        st.page_link("pages/Orientacoes_Arquiteturas.py", label="🏗️ Arquiteturas", use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ── Reuniões recentes ─────────────────────────────────────────────────────────
with col_recent:
    st.markdown('<div class="section-hdr" style="margin-top:0">Reuniões recentes</div>', unsafe_allow_html=True)

    if not recent:
        st.caption("Nenhuma reunião encontrada. Processe a primeira transcrição para começar.")
        st.page_link("pages/Pipeline.py", label="🚀 Processar primeira transcrição")
    else:
        for mtg in recent:
            num   = mtg.get("meeting_number", "?")
            title = mtg.get("title", "(sem título)")
            date  = mtg.get("meeting_date", "—")
            proj  = mtg.get("project_name", "—")

            label_short = title if len(title) <= 38 else title[:35] + "…"

            st.markdown(f"""
<div class="mtg-card">
  <div class="mtg-num">REUNIÃO #{num}</div>
  <div class="mtg-title">{label_short}</div>
  <div class="mtg-meta">📁 {proj} &nbsp;·&nbsp; 📅 {date}</div>
</div>""", unsafe_allow_html=True)

            lc1, lc2, lc3 = st.columns(3)
            with lc1:
                st.page_link(
                    "pages/Assistente.py",
                    label="💬 Assistente",
                    help="Consultar dados desta reunião no Assistente",
                    use_container_width=True,
                )
            with lc2:
                st.page_link(
                    "pages/ValidationHub.py",
                    label="✅ Validação",
                    help="Revisar requisitos e artefatos desta reunião",
                    use_container_width=True,
                )
            with lc3:
                st.page_link(
                    "pages/BpmnEditor.py",
                    label="✏️ Editor",
                    help="Editar diagrama BPMN desta reunião",
                    use_container_width=True,
                )

        st.markdown(
            "<div style='text-align:right;margin-top:.4rem'>",
            unsafe_allow_html=True,
        )
        st.page_link("pages/Assistente.py", label="Ver todas as reuniões →")
        st.markdown("</div>", unsafe_allow_html=True)

# ── 5. Agenda do Projeto ──────────────────────────────────────────────────────
st.markdown('<div class="section-hdr">📅 Agenda do Projeto</div>', unsafe_allow_html=True)

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
_APP_VERSION = "v4.16"
st.markdown(
    f'<div class="home-footer">'
    f'Process2Diagram {_APP_VERSION} &nbsp;·&nbsp; Multi-agent process intelligence platform'
    f'</div>',
    unsafe_allow_html=True,
)
