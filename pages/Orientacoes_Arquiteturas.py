# pages/Orientacoes_Arquiteturas.py
# ─────────────────────────────────────────────────────────────────────────────
# Mapas de arquitetura do sistema — Process2Diagram
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

# ── Cabeçalho ─────────────────────────────────────────────────────────────────
st.markdown("# 🏗️ Arquiteturas do Sistema")
st.caption(
    "Mapas visuais dos fluxos do Process2Diagram. "
    "Use scroll + drag para explorar · ⊞ ajusta à tela · "
    "⧉ abre o diagrama em nova janela do browser."
)

st.markdown("---")

# ── Diagrama 1: Pipeline Principal ────────────────────────────────────────────
st.markdown("## 🚀 Pipeline de Processamento")
st.markdown(
    """
Fluxo completo desde a transcrição bruta até os artefatos finais.
Cada nó representa um agente ou módulo independente; as setas indicam
dependências de dados via **KnowledgeHub**.

O diagrama inclui a **camada de segurança transversal (🔒 C1–C6)**:
sanitização de PII antes de cada chamada LLM, conformidade LGPD pós-pipeline
(detecção · consentimento · auditoria) e autenticação/RLS na persistência.
Para detalhes completos, consulte **Início → 🔒 Segurança de Dados**.

Toda chamada de agente passa primeiro pela **⚡ Cache LLM** (hash exato
SHA-256 de provedor+modelo+prompt, PII-safe) antes de ir ao provider real —
um hit evita a chamada de API por completo. Detalhes em
**Ajuda → 🗄️ Cache LLM**.
"""
)

render_architecture_diagram(height=720)

st.markdown("---")

# ── Diagrama 2: Assistente RAG ────────────────────────────────────────────────
st.markdown("## 💬 Assistente — Pipeline RAG")
st.markdown(
    """
Dois modos de operação para responder perguntas sobre as reuniões armazenadas:

- **Modo A — Tool-use (padrão):** o LLM decide dinamicamente quais das 35
  ferramentas chamar — dados de reuniões, requisitos, BPMN, SBVR, Google
  Calendar e ferramentas admin. Até 5 rounds de chamadas antes da resposta final.

- **Modo B — RAG Clássico (fallback):** busca por keyword + similaridade
  semântica via pgvector; o contexto recuperado é passado diretamente ao LLM.
"""
)

render_assistant_diagram(height=680)

st.markdown("---")

# ── Diagrama 3: Comunicação & Integrações ─────────────────────────────────────
st.markdown("## 🔌 Comunicação & Integrações")
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
