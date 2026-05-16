# app.py — Process2Diagram Navigation Host
# ─────────────────────────────────────────────────────────────────────────────
# Host de navegação — define as seções e páginas do app.
# Código aqui roda em TODAS as páginas antes de pg.run().
#
# Estrutura de seções:
#   (default)    → Home (Central de Operações)
#   Pipeline     → Processar Transcrição, Diagramas, Editor BPMN
#   Análise      → Assistente, Req. Tracker, Validação, ROI-TR, Entidades
#   Sistema      → Configurações, Custo [+ Admin, Banco apenas para admin]
#   Ajuda        → Como Iniciar, Arquiteturas
#   Manutenção   → Batch Runner, Backfills [apenas admin]
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
from core.session_state import init_session_state
from ui.auth_gate import apply_auth_gate
from modules.auth import is_admin

# ── Configuração global da página ─────────────────────────────────────────────
# set_page_config deve ser chamado AQUI (única vez) — páginas não devem chamá-lo.
st.set_page_config(
    page_title="Process2Diagram",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Inicialização ─────────────────────────────────────────────────────────────
init_session_state()

# ── Navegação dinâmica por perfil ─────────────────────────────────────────────
# st.navigation() deve ser chamado em TODAS as execuções (inclusive antes do
# login) — caso contrário o roteamento não é inicializado e Streamlit trata
# cada navegação como nova sessão. is_admin() lê st.session_state e retorna
# False antes do login, True após — o menu se atualiza automaticamente ao logar.
_admin = is_admin()

_sistema_pages = [
    st.Page("pages/Settings.py",         title="Configurações",       icon="⚙️"),
    st.Page("pages/CostEstimator.py",    title="Estimativa de Custo", icon="💰"),
]
if _admin:
    _sistema_pages += [
        st.Page("pages/MasterAdmin.py",      title="Master Admin",    icon="🛡️"),
        st.Page("pages/DatabaseOverview.py", title="Banco de Dados",  icon="🗄️"),
    ]

pages = {
    "Início": [
        st.Page("pages/Home.py", title="Central de Operações", icon="🏠", default=True),
    ],
    "Pipeline": [
        st.Page("pages/Pipeline.py",    title="Processar Transcrição", icon="🚀"),
        st.Page("pages/Diagramas.py",   title="Diagramas",             icon="📐"),
        st.Page("pages/BpmnEditor.py",  title="Editor BPMN",           icon="✏️"),
    ],
    "Análise": [
        st.Page("pages/ContextHealth.py",     title="Saúde do Contexto",icon="🏥"),
        st.Page("pages/Assistente.py",        title="Assistente",       icon="💬"),
        st.Page("pages/ReqTracker.py",        title="Req. Tracker",     icon="📋"),
        st.Page("pages/ValidationHub.py",     title="Validação",        icon="✅"),
        st.Page("pages/MeetingROI.py",        title="Qualidade ROI-TR", icon="📊"),
        st.Page("pages/EntityRecognition.py", title="Entidades (NER)",  icon="🔍"),
        st.Page("pages/KnowledgeHub.py",      title="Knowledge Hub",    icon="🧠"),
    ],
    "Sistema": _sistema_pages,
    "Ajuda": [
        st.Page("pages/Orientacoes_ComoIniciar.py",  title="Como Iniciar",  icon="📖"),
        st.Page("pages/Orientacoes_Arquiteturas.py", title="Arquiteturas",  icon="🏗️"),
        st.Page("pages/Orientacoes_CKF.py",          title="Guia CKF",      icon="🧠"),
    ],
}
if _admin:
    pages["Manutenção"] = [
        st.Page("pages/BatchRunner.py",        title="Batch Runner",        icon="🔄"),
        st.Page("pages/BpmnBackfill.py",       title="BPMN Backfill",       icon="🔧"),
        st.Page("pages/MinutesBackfill.py",    title="Minutes Backfill",    icon="📝"),
        st.Page("pages/TranscriptBackfill.py", title="Transcript Backfill", icon="📑"),
        st.Page("pages/ReportBackfill.py", title="Relatório Executivo", icon="📄"),
    ]
pg = st.navigation(pages)

# ── Autenticação — após st.navigation(), antes de pg.run() ────────────────────
# Se não autenticado: render_login_page() oculta a sidebar via CSS e chama
# st.stop() — pg.run() nunca é alcançado. O CSS do login já esconde a sidebar.
apply_auth_gate()

pg.run()
