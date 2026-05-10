# pages/Orientacoes_Arquiteturas.py
# ─────────────────────────────────────────────────────────────────────────────
# Mapas de arquitetura do sistema — Process2Diagram
# Centraliza os dois diagramas arquiteturais que antes ficavam nas páginas
# operacionais (Pipeline Principal e Assistente).
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from ui.auth_gate import apply_auth_gate
from ui.architecture_diagram import render_architecture_diagram
from ui.assistant_diagram import render_assistant_diagram
from ui.comms_diagram import render_comms_diagram

apply_auth_gate()


def _fullscreen_btn(diagram_key: str) -> None:
    """Button that opens the diagram in the dedicated full-screen viewer."""
    if st.button("⛶ Tela cheia", key=f"fs_{diagram_key}", help="Abrir em tela dedicada"):
        st.session_state["arch_viewer_diagram"] = diagram_key
        st.switch_page("pages/ArquiteturaViewer.py")


# ── Cabeçalho ─────────────────────────────────────────────────────────────────
st.markdown("# 🏗️ Arquiteturas do Sistema")
st.caption(
    "Mapas visuais dos fluxos do Process2Diagram. "
    "Use scroll + drag para explorar. Botão ⊞ para ajustar à tela. "
    "Clique em ⛶ Tela cheia para abrir o diagrama em tela dedicada."
)

st.markdown("---")

# ── Diagrama 1: Pipeline Principal ────────────────────────────────────────────
col1, col2 = st.columns([9, 1])
with col1:
    st.markdown("## 🚀 Pipeline de Processamento")
with col2:
    _fullscreen_btn("pipeline")

st.markdown(
    """
Fluxo completo desde a transcrição bruta até os artefatos finais.
Cada nó representa um agente ou módulo independente; as setas indicam
dependências de dados via **KnowledgeHub**.
"""
)

render_architecture_diagram(height=720)

st.markdown("---")

# ── Diagrama 2: Assistente RAG ────────────────────────────────────────────────
col1, col2 = st.columns([9, 1])
with col1:
    st.markdown("## 💬 Assistente — Pipeline RAG")
with col2:
    _fullscreen_btn("assistente")

st.markdown(
    """
Dois modos de operação para responder perguntas sobre as reuniões armazenadas:

- **Modo A — Tool-use (padrão):** o LLM decide dinamicamente quais das 22
  ferramentas chamar — dados de reuniões, requisitos, BPMN, SBVR, Google
  Calendar e ferramentas admin. Até 5 rounds de chamadas antes da resposta final.

- **Modo B — RAG Clássico (fallback):** busca por keyword + similaridade
  semântica via pgvector; o contexto recuperado é passado diretamente ao LLM.
"""
)

render_assistant_diagram(height=680)

st.markdown("---")

# ── Diagrama 3: Comunicação & Integrações ─────────────────────────────────────
col1, col2 = st.columns([9, 1])
with col1:
    st.markdown("## 🔌 Comunicação & Integrações")
with col2:
    _fullscreen_btn("comms")

st.markdown(
    """
Topologia completa de comunicação — quem chama quem, por qual protocolo
e com qual autenticação. Destaque para os **dois caminhos independentes**
ao Google Calendar:

- **Streamlit App** → `calendar_client.py` → Google Calendar API
  (service account JWT; `calendar_id` resolvido via Supabase → secrets → arquivo → `"primary"`)
- **Claude Code CLI** → `google_calendar_server.py` (MCP / stdio) → Google Calendar API
  (mesmo service account, caminho totalmente separado do Streamlit; uso exclusivo em desenvolvimento)

Ferramentas marcadas com **★** requerem perfil `admin` ou `master` — verificado
pelo `is_admin()` gate no `AssistantToolExecutor`.
"""
)

render_comms_diagram(height=760)

st.markdown("---")
st.caption("Process2Diagram · Arquiteturas do Sistema")
