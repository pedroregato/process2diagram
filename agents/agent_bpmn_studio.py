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

import copy

from agents.agent_bpmn import AgentBPMN
from agents.nlp_chunker import NLPChunker
from core.knowledge_hub import KnowledgeHub


def generate_bpmn_from_description(
    description: str,
    client_info: dict,
    provider_cfg: dict,
    run_nlp: bool = True,
    output_language: str = "Auto-detect",
    max_attempts: int = 2,
) -> KnowledgeHub:
    """Gera um BPMNModel (XML + Mermaid) a partir de uma descrição de processo em texto livre.

    Monta um KnowledgeHub sintético com ``transcript_clean = description`` e roda
    ``AgentBPMN`` normalmente — o agente, ``_enforce_rules()`` e os geradores de
    XML/Mermaid são reaproveitados sem nenhuma alteração.

    Resiliência (PC116 follow-up): o pipeline normal tem duas redes de segurança
    que o BPMN Studio não expõe (torneio ``n_bpmn_runs`` + LangGraph adaptativo) —
    aqui, cada chamada de ``AgentBPMN.run()`` já tenta até 3x internamente
    (``BaseAgent.max_retries``), mas todas as tentativas reforçam a MESMA correção
    sobre a MESMA extração; se o modelo ficar "preso" num padrão de falha (ex.:
    pool sem sequence flows), as 3 tentativas internas falham identicamente.
    ``max_attempts`` reinicia a chamada inteira do zero — um novo pedido "limpo"
    à LLM, sem o histórico da correção que não funcionou — antes de desistir.
    Cada tentativa opera sobre uma cópia rasa do hub (``copy.copy``), isolando
    qualquer estado parcial de uma tentativa malsucedida.

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
        max_attempts: número de tentativas completas (chamada inteira ao
            AgentBPMN, não as tentativas internas dele). Padrão 2 — dobra a
            resiliência efetiva sem aproximar o custo do torneio completo.

    Retorna o ``KnowledgeHub`` com ``hub.bpmn`` populado (``hub.bpmn.ready=True``
    em caso de sucesso). Se todas as tentativas falharem, levanta a exceção da
    última tentativa — o chamador (página Streamlit) decide como exibir o erro.
    """
    hub = KnowledgeHub.new()
    hub.transcript_raw = description
    hub.transcript_clean = description

    if run_nlp:
        try:
            hub = NLPChunker().run(hub)
        except Exception:
            pass  # fail-open: AgentBPMN funciona com hub.nlp vazio (0 atores detectados)

    last_error: Exception | None = None
    for _attempt in range(max(1, max_attempts)):
        try:
            hub_attempt = copy.copy(hub)
            agent = AgentBPMN(client_info, provider_cfg)
            return agent.run(hub_attempt, output_language)
        except Exception as exc:
            last_error = exc

    raise last_error
