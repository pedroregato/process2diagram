# app.py — Process2Diagram Navigation Host
# ─────────────────────────────────────────────────────────────────────────────
# Host de navegação — define as seções e páginas do app.
# Código aqui roda em TODAS as páginas antes de pg.run().
#
# Estrutura de seções:
#   Pipeline     → Processar Transcrição, Diagramas
#   Análise      → Assistente, Req. Tracker, Qualidade ROI-TR, Entidades
#   Sistema      → Configurações, Admin, Banco, Custo, Orientações
#   Manutenção   → Batch Runner, Backfills (ferramentas de manutenção)
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st
from core.session_state import init_session_state
from ui.auth_gate import apply_auth_gate

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

# ── Navegação — deve ser definida ANTES de apply_auth_gate() ──────────────────
# st.navigation() precisa ser chamado em TODAS as execuções (inclusive as
# não-autenticadas), caso contrário o roteamento não é inicializado e
# Streamlit trata cada navegação de página como nova sessão → login repetido.
pages = {
    "Pipeline": [
        st.Page("pages/Pipeline.py",  title="Processar Transcrição", icon="🚀", default=True),
        st.Page("pages/Diagramas.py", title="Diagramas",             icon="📐"),
    ],
    "Análise": [
        st.Page("pages/Assistente.py",        title="Assistente",       icon="💬"),
        st.Page("pages/ReqTracker.py",        title="Req. Tracker",     icon="📋"),
        st.Page("pages/ValidationHub.py",     title="Validação",        icon="✅"),
        st.Page("pages/MeetingROI.py",        title="Qualidade ROI-TR", icon="📊"),
        st.Page("pages/EntityRecognition.py", title="Entidades (NER)",  icon="🔍"),
    ],
    "Sistema": [
        st.Page("pages/Settings.py",                  title="Configurações",       icon="⚙️"),
        st.Page("pages/MasterAdmin.py",               title="Master Admin",        icon="🛡️"),
        st.Page("pages/DatabaseOverview.py",          title="Banco de Dados",      icon="🗄️"),
        st.Page("pages/CostEstimator.py",             title="Estimativa de Custo", icon="💰"),
        st.Page("pages/Orientacoes_ComoIniciar.py",   title="Como Iniciar",        icon="📖"),
        st.Page("pages/Orientacoes_Arquiteturas.py",  title="Arquiteturas",        icon="🏗️"),
    ],
    "Manutenção": [
        st.Page("pages/BatchRunner.py",        title="Batch Runner",        icon="🔄"),
        st.Page("pages/BpmnBackfill.py",       title="BPMN Backfill",       icon="🔧"),
        st.Page("pages/MinutesBackfill.py",    title="Minutes Backfill",    icon="📝"),
        st.Page("pages/TranscriptBackfill.py", title="Transcript Backfill", icon="📑"),
    ],
}
pg = st.navigation(pages)

# ── Autenticação — após st.navigation(), antes de pg.run() ────────────────────
# Se não autenticado: render_login_page() oculta a sidebar via CSS e chama
# st.stop() — pg.run() nunca é alcançado. O CSS do login já esconde a sidebar.
apply_auth_gate()

pg.run()
