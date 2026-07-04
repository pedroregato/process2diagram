# agents/agent_bpmn_studio.py
# ─────────────────────────────────────────────────────────────────────────────
# BPMN Studio (PC116) — gera BPMN 2.0 + Mermaid a partir de uma descrição de
# processo em texto livre, sem depender de uma reunião/transcrição real.
#
# Não é um agente novo: é um wrapper fino que monta um KnowledgeHub sintético
# (transcript_clean = descrição) e reaproveita AgentBPMN sem alteração — o
# agente não distingue a origem do texto que recebe.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from agents.agent_bpmn import AgentBPMN
from agents.nlp_chunker import NLPChunker
from core.knowledge_hub import KnowledgeHub


def generate_bpmn_from_description(
    description: str,
    client_info: dict,
    provider_cfg: dict,
    run_nlp: bool = True,
    output_language: str = "Auto-detect",
) -> KnowledgeHub:
    """Gera um BPMNModel (XML + Mermaid) a partir de uma descrição de processo em texto livre.

    Monta um KnowledgeHub sintético com ``transcript_clean = description`` e roda
    ``AgentBPMN`` normalmente — o agente, ``_enforce_rules()`` e os geradores de
    XML/Mermaid são reaproveitados sem nenhuma alteração.

    Args:
        description: descrição do processo em texto livre (não precisa ser uma
            transcrição de reunião).
        client_info: credenciais/config do provedor LLM (mesmo formato usado por
            ``get_session_llm_client()``).
        provider_cfg: configuração do provedor (modelo, etc.), mesmo formato do
            pipeline normal.
        run_nlp: quando True (padrão), roda ``NLPChunker`` (sem LLM) antes do
            AgentBPMN para melhorar a detecção de atores/organizações e, com
            isso, a nomeação de lanes.
        output_language: idioma de saída, mesmo parâmetro do pipeline normal.

    Retorna o ``KnowledgeHub`` com ``hub.bpmn`` populado (``hub.bpmn.ready=True``
    em caso de sucesso). Levanta a mesma exceção que ``AgentBPMN.run()`` levantaria
    em caso de falha — o chamador (página Streamlit) decide como exibir o erro.
    """
    hub = KnowledgeHub.new()
    hub.transcript_raw = description
    hub.transcript_clean = description

    if run_nlp:
        try:
            hub = NLPChunker().run(hub)
        except Exception:
            pass  # fail-open: AgentBPMN funciona com hub.nlp vazio (0 atores detectados)

    agent = AgentBPMN(client_info, provider_cfg)
    hub = agent.run(hub, output_language)
    return hub
