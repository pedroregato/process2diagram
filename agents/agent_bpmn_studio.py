# agents/agent_bpmn_studio.py
# ─────────────────────────────────────────────────────────────────────────────
# BPMN Studio (PC116) — gera BPMN 2.0 + Mermaid a partir de uma descrição de
# processo em texto livre, sem depender de uma reunião/transcrição real.
#
# Não é um agente novo: é um wrapper fino que monta um KnowledgeHub sintético
# (transcript_clean = descrição) e reaproveita AgentBPMN sem alteração — o
# agente não distingue a origem do texto que recebe.
#
# PC116-D: substitui o retry simples ("tenta de novo do zero se falhar") pelo
# MESMO torneio multi-run + AgentValidator que core/pipeline.py usa por padrão
# quando n_bpmn_runs > 1 — mesmo rigor, mesmas ferramentas, não um mecanismo
# paralelo. Motivado por evidência real: sem torneio, uma única extração podia
# "passar" na validação estrutural mínima (steps + edges presentes) mas ainda
# assim ser estruturalmente pobre (ex.: colapsar uma organização externa citada
# nominalmente num sendTask/receiveTask dentro do mesmo pool, em vez de um
# segundo pool; ou colapsar um sub-ciclo descrito em detalhe — validação,
# correção, pagamento — num único callActivity opaco). O torneio roda N
# extrações independentes e usa o mesmo AgentValidator (scorer puro Python,
# sem LLM) do pipeline principal para escolher a melhor.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import copy

from agents.agent_bpmn import AgentBPMN
from agents.agent_validator import AgentValidator
from agents.nlp_chunker import NLPChunker
from core.knowledge_hub import BPMNModel, KnowledgeHub

_DEFAULT_BPMN_WEIGHTS = {
    "granularity": 5, "task_type": 5, "gateways": 5, "structural": 5, "semantic": 5,
}


def generate_bpmn_from_description(
    description: str,
    client_info: dict,
    provider_cfg: dict,
    run_nlp: bool = True,
    output_language: str = "Auto-detect",
    n_runs: int = 3,
    bpmn_weights: dict | None = None,
) -> KnowledgeHub:
    """Gera um BPMNModel (XML + Mermaid) a partir de uma descrição de processo em texto livre.

    Monta um KnowledgeHub sintético com ``transcript_clean = description`` e roda
    ``AgentBPMN`` normalmente — o agente, ``_enforce_rules()`` e os geradores de
    XML/Mermaid são reaproveitados sem nenhuma alteração.

    Torneio multi-run (PC116-D): roda ``AgentBPMN`` até ``n_runs`` vezes de forma
    independente e usa ``AgentValidator`` (o mesmo scorer puro Python do pipeline
    principal — granularidade, tipo de tarefa, gateways, integridade estrutural,
    semântica de nomes) para escolher a melhor extração — exatamente o mecanismo
    de ``core/pipeline.py`` quando ``n_bpmn_runs > 1`` (o caminho padrão do
    pipeline normal, já que ``n_bpmn_runs`` é 3 por padrão). Uma execução que
    falhe (exceção do retry interno do próprio AgentBPMN) é descartada do
    torneio sem interromper as demais; só levanta exceção se TODAS falharem.
    Cada execução opera sobre uma cópia rasa do hub (``copy.copy``), isolando
    estado entre tentativas.

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
        n_runs: número de execuções independentes do torneio. Padrão 3 — mesmo
            valor padrão de ``st.session_state.n_bpmn_runs`` no pipeline normal;
            o chamador (página Streamlit) deve passar esse valor de sessão
            diretamente para manter os dois caminhos sempre em paridade.
        bpmn_weights: pesos por dimensão para o ``AgentValidator``, mesmo
            formato/default de ``st.session_state.bpmn_weights``. ``None`` usa
            pesos iguais (5) em todas as dimensões.

    Retorna o ``KnowledgeHub`` vencedor do torneio, com ``hub.bpmn`` populado e
    ``hub.validation.bpmn_score``/``bpmn_candidates`` preenchidos (mesma
    estrutura que o pipeline normal grava). Levanta a exceção da última
    execução malsucedida se todas as ``n_runs`` falharem.
    """
    weights = bpmn_weights or _DEFAULT_BPMN_WEIGHTS

    hub = KnowledgeHub.new()
    hub.transcript_raw = description
    hub.transcript_clean = description

    if run_nlp:
        try:
            hub = NLPChunker().run(hub)
        except Exception:
            pass  # fail-open: AgentBPMN funciona com hub.nlp vazio (0 atores detectados)

    validator = AgentValidator()
    agent = AgentBPMN(client_info, provider_cfg)

    candidates: list[tuple] = []
    last_error: Exception | None = None
    for i in range(max(1, n_runs)):
        try:
            hub_c = copy.copy(hub)
            hub_c.bpmn = BPMNModel()
            hub_c = agent.run(hub_c, output_language)
            score = validator.score(hub_c.bpmn, hub_c.transcript_clean, weights)
            score.run_index = i + 1
            candidates.append((score, hub_c))
        except Exception as exc:
            last_error = exc

    if not candidates:
        raise last_error

    best_score, best_hub = max(candidates, key=lambda c: c[0].weighted)
    best_hub.validation.bpmn_score = best_score
    best_hub.validation.bpmn_candidates = [c[0] for c in candidates]
    best_hub.validation.n_bpmn_runs = len(candidates)
    best_hub.validation.ready = True
    return best_hub
