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

apply_auth_gate()

# ── Cabeçalho ─────────────────────────────────────────────────────────────────
st.markdown("# 🏗️ Arquiteturas do Sistema")
st.caption(
    "Mapas visuais dos dois fluxos principais do Process2Diagram. "
    "Use scroll + drag para explorar. Botão ⊞ para ajustar à tela."
)

st.markdown("---")

# ── Diagrama 1: Pipeline Principal ────────────────────────────────────────────
st.markdown("## 🚀 Pipeline de Processamento")
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
st.markdown("## 💬 Assistente — Pipeline RAG")
st.markdown(
    """
Dois modos de operação para responder perguntas sobre as reuniões armazenadas:

- **Modo A — Tool-use (padrão):** o LLM decide dinamicamente quais ferramentas
  chamar (participantes, decisões, requisitos, BPMN, SBVR…). Até 5 rounds de
  chamadas a ferramentas antes de gerar a resposta final.

- **Modo B — RAG Clássico (fallback):** busca por keyword + similaridade
  semântica via pgvector; o contexto recuperado é passado diretamente ao LLM.
"""
)

render_assistant_diagram(height=680)

st.markdown("---")
st.caption("Process2Diagram · Arquiteturas do Sistema")
