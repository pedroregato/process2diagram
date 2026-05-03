# pages/Home.py
# ─────────────────────────────────────────────────────────────────────────────
# Central de Operações — tela inicial exibida após o login.
#
# Seções:
#   1. Header de boas-vindas (nome, perfil, data)
#   2. KPIs globais do banco (projetos, reuniões, requisitos, processos BPMN)
#   3. Fluxo de trabalho visual (4 etapas com links)
#   4. Acesso rápido por área (esquerda) + Reuniões recentes (direita)
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
.home-header {
    background: linear-gradient(135deg, #0B1E3D 0%, #1A3A6B 100%);
    border-bottom: 3px solid #C97B1A;
    border-radius: 10px;
    padding: 1.4rem 2rem;
    margin-bottom: 1.2rem;
    display: flex; align-items: center; justify-content: space-between;
}
.home-header .greeting { font-size: 1.5rem; font-weight: 700; color: #FAFAF8; }
.home-header .sub      { font-size: .82rem; color: #8899AA; margin-top: .2rem; }
.role-badge {
    display:inline-block; padding:3px 10px; border-radius:20px;
    font-size:.72rem; font-weight:700; letter-spacing:.06em;
    margin-left:.6rem; vertical-align:middle;
}
.kpi-card {
    background: #0F2040; border: 1px solid #1e3a55; border-radius: 8px;
    padding: 1rem 1.2rem; text-align: center;
}
.kpi-card .kpi-num  { font-size: 2rem; font-weight: 700; color: #FAFAF8; line-height:1; }
.kpi-card .kpi-lbl  { font-size: .72rem; color: #8899AA; letter-spacing:.06em;
                       text-transform: uppercase; margin-top: .3rem; }
.flow-step {
    background: #0F2040; border: 1px solid #1e3a55; border-radius: 8px;
    padding: .9rem 1rem; text-align: center; position: relative;
}
.flow-step .step-num {
    display:inline-block; width:22px; height:22px; line-height:22px;
    border-radius:50%; background:#C97B1A; color:#fff;
    font-size:.72rem; font-weight:700; margin-bottom:.4rem;
}
.flow-step .step-title { font-size: .88rem; font-weight: 700; color: #FAFAF8; }
.flow-step .step-desc  { font-size: .72rem; color: #8899AA; margin-top:.25rem; }
.area-card {
    background: #0F2040; border: 1px solid #1e3a55; border-radius: 8px;
    padding: 1rem 1.2rem; margin-bottom: .8rem;
}
.area-card .area-title {
    font-size: .78rem; font-weight: 700; color: #C97B1A;
    letter-spacing: .08em; text-transform: uppercase; margin-bottom: .6rem;
}
.mtg-card {
    background: #0F2040; border: 1px solid #1e3a55; border-radius: 8px;
    padding: .8rem 1rem; margin-bottom: .6rem;
}
.mtg-card .mtg-title { font-size: .88rem; font-weight: 600; color: #FAFAF8; }
.mtg-card .mtg-meta  { font-size: .72rem; color: #8899AA; margin-top: .2rem; }
.section-hdr {
    font-size: .78rem; font-weight: 700; color: #8899AA;
    letter-spacing: .1em; text-transform: uppercase;
    margin: 1.2rem 0 .5rem;
    border-bottom: 1px solid #1e3a55; padding-bottom: .3rem;
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
  <span class="role-badge" style="background:{role_color}22;color:{role_color};border:1px solid {role_color}44">{role_label}</span>
</div>
<div class="sub">Process2Diagram{tenant_str} · {today_str}</div>
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

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(f'<div class="kpi-card"><div class="kpi-num">{_fmt(stats["n_projects"], stats["available"])}</div><div class="kpi-lbl">Projetos</div></div>', unsafe_allow_html=True)
with c2:
    st.markdown(f'<div class="kpi-card"><div class="kpi-num">{_fmt(stats["n_meetings"], stats["available"])}</div><div class="kpi-lbl">Reuniões</div></div>', unsafe_allow_html=True)
with c3:
    st.markdown(f'<div class="kpi-card"><div class="kpi-num">{_fmt(stats["n_reqs"], stats["available"])}</div><div class="kpi-lbl">Requisitos</div></div>', unsafe_allow_html=True)
with c4:
    st.markdown(f'<div class="kpi-card"><div class="kpi-num">{_fmt(stats["n_bpmn_procs"], stats["available"])}</div><div class="kpi-lbl">Processos BPMN</div></div>', unsafe_allow_html=True)

if not stats["available"]:
    st.caption("⚠️ Banco de dados não configurado — KPIs indisponíveis. Configure em **Sistema → Configurações**.")

# ── 3. Fluxo de trabalho ──────────────────────────────────────────────────────
st.markdown('<div class="section-hdr">Fluxo de trabalho</div>', unsafe_allow_html=True)

f1, arr1, f2, arr2, f3, arr3, f4 = st.columns([4, 1, 4, 1, 4, 1, 4])

with f1:
    st.markdown("""
<div class="flow-step">
<div class="step-num">1</div>
<div class="step-title">📥 Processar</div>
<div class="step-desc">Cole ou faça upload de uma transcrição e execute o pipeline de agentes</div>
</div>""", unsafe_allow_html=True)

with arr1:
    st.markdown("<div style='text-align:center;padding-top:1.8rem;color:#C97B1A;font-size:1.4rem'>→</div>", unsafe_allow_html=True)

with f2:
    st.markdown("""
<div class="flow-step">
<div class="step-num">2</div>
<div class="step-title">✅ Validar</div>
<div class="step-desc">Revise e aprove requisitos, termos SBVR, regras e diagramas BPMN</div>
</div>""", unsafe_allow_html=True)

with arr2:
    st.markdown("<div style='text-align:center;padding-top:1.8rem;color:#C97B1A;font-size:1.4rem'>→</div>", unsafe_allow_html=True)

with f3:
    st.markdown("""
<div class="flow-step">
<div class="step-num">3</div>
<div class="step-title">🔍 Analisar</div>
<div class="step-desc">Converse com o Assistente, acompanhe requisitos e indicadores de ROI</div>
</div>""", unsafe_allow_html=True)

with arr3:
    st.markdown("<div style='text-align:center;padding-top:1.8rem;color:#C97B1A;font-size:1.4rem'>→</div>", unsafe_allow_html=True)

with f4:
    st.markdown("""
<div class="flow-step">
<div class="step-num">4</div>
<div class="step-title">📤 Exportar</div>
<div class="step-desc">Edite diagramas BPMN, visualize fluxos e exporte atas, relatórios e XML</div>
</div>""", unsafe_allow_html=True)

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

    # Sistema (sempre visível, mas conteúdo restringe-se ao papel)
    st.markdown('<div class="area-card"><div class="area-title">⚙️ Sistema</div>', unsafe_allow_html=True)
    if is_admin():
        s1, s2, s3, s4 = st.columns(4)
        with s1:
            st.page_link("pages/Settings.py",          label="⚙️ Configurações",    use_container_width=True)
        with s2:
            st.page_link("pages/DatabaseOverview.py",  label="🗄️ Banco de Dados",   use_container_width=True)
        with s3:
            st.page_link("pages/MasterAdmin.py",       label="🛡️ Master Admin",     use_container_width=True)
        with s4:
            st.page_link("pages/CostEstimator.py",     label="💰 Custos",           use_container_width=True)
    else:
        s1, s2 = st.columns(2)
        with s1:
            st.page_link("pages/Settings.py",          label="⚙️ Configurações",    use_container_width=True)
        with s2:
            st.page_link("pages/CostEstimator.py",     label="💰 Estimativa de Custo", use_container_width=True)
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
    else:
        for mtg in recent:
            num   = mtg.get("meeting_number", "?")
            title = mtg.get("title", "(sem título)")
            date  = mtg.get("meeting_date", "—")
            proj  = mtg.get("project_name", "—")
            mid   = mtg.get("id")
            pid   = mtg.get("project_id")

            # Label truncado para caber no card
            label_short = title if len(title) <= 38 else title[:35] + "…"

            st.markdown(f"""
<div class="mtg-card">
<div class="mtg-title">#{num} — {label_short}</div>
<div class="mtg-meta">📁 {proj} · 📅 {date}</div>
</div>""", unsafe_allow_html=True)

            # Links contextuais inline
            lc1, lc2, lc3 = st.columns(3)
            with lc1:
                st.page_link(
                    "pages/Assistente.py",
                    label="💬",
                    help=f"Assistente — {title}",
                    use_container_width=True,
                )
            with lc2:
                st.page_link(
                    "pages/ValidationHub.py",
                    label="✅",
                    help=f"Validação — {title}",
                    use_container_width=True,
                )
            with lc3:
                st.page_link(
                    "pages/BpmnEditor.py",
                    label="✏️",
                    help=f"Editor BPMN — {title}",
                    use_container_width=True,
                )

# ── 5. Agenda do Projeto ──────────────────────────────────────────────────────
st.markdown('<div class="section-hdr">📅 Agenda do Projeto</div>', unsafe_allow_html=True)

try:
    from urllib.parse import quote
    from modules.calendar_client import _load_calendar_id, calendar_configured
    if calendar_configured():
        cal_id   = _load_calendar_id()
        cal_url  = (
            "https://calendar.google.com/calendar/embed"
            f"?src={quote(cal_id)}&ctz=America%2FSao_Paulo"
            "&showTitle=0&showNav=1&showPrint=0&showTabs=1&showCalendars=0"
        )
        import streamlit.components.v1 as _components
        _components.html(
            f'<iframe src="{cal_url}" style="border:0;width:100%;height:600px" '
            f'frameborder="0" scrolling="no"></iframe>',
            height=620,
        )
    else:
        st.caption("📅 Agenda não configurada. Configure Google Calendar em **Sistema → Configurações**.")
except Exception as _cal_exc:
    st.caption(f"📅 Agenda indisponível: {_cal_exc}")

# ── Rodapé ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-top:2rem;padding-top:.8rem;border-top:1px solid #1e3a55;
text-align:center;font-size:.7rem;color:#445566">
Process2Diagram v4.15 · Multi-agent process intelligence platform
</div>
""", unsafe_allow_html=True)
