# app.py — Process2Diagram Navigation Host
# ─────────────────────────────────────────────────────────────────────────────
# Host de navegação — define as seções e páginas do app.
# Código aqui roda em TODAS as páginas antes de pg.run().
#
# Estrutura de seções:
#   Orientações  → Como Iniciar, Arquiteturas
#   Pipeline     → Processar Transcrição, Diagramas
#   Análise & Dados → Assistente, Req. Tracker
#   Operações    → Batch Runner, BPMN Backfill, Transcript Backfill, Custo
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

# ── Inicialização e autenticação (rodam em todas as páginas) ──────────────────
init_session_state()
apply_auth_gate()

# ── Definição da navegação com seções ─────────────────────────────────────────
pages = {
    "Orientações": [
        st.Page("pages/Orientacoes_ComoIniciar.py",   title="Como Iniciar",   icon="📖"),
        st.Page("pages/Orientacoes_Arquiteturas.py",  title="Arquiteturas",   icon="🏗️"),
    ],
    "Pipeline": [
        st.Page("pages/Pipeline.py",   title="Processar Transcrição", icon="🚀", default=True),
        st.Page("pages/Diagramas.py",  title="Diagramas",             icon="📐"),
    ],
    "Análise & Dados": [
        st.Page("pages/Assistente.py",  title="Assistente",    icon="💬"),
        st.Page("pages/ReqTracker.py",  title="Req. Tracker",  icon="📋"),
    ],
    "Operações": [
        st.Page("pages/BatchRunner.py",         title="Batch Runner",        icon="🔄"),
        st.Page("pages/BpmnBackfill.py",        title="BPMN Backfill",       icon="🔧"),
        st.Page("pages/TranscriptBackfill.py",  title="Transcript Backfill", icon="📝"),
        st.Page("pages/CostEstimator.py",       title="Estimativa de Custo", icon="💰"),
    ],
}

pg = st.navigation(pages)
pg.run()
