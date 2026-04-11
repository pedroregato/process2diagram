# agents/agent_assistant.py
# ─────────────────────────────────────────────────────────────────────────────
# AgentAssistant — conversational RAG agent for meeting/project Q&A.
#
# Unlike other agents, this one does NOT use the KnowledgeHub pipeline.
# Its main entry point is chat(), which accepts multi-turn conversation history
# plus a pre-built context string (from core/project_store.retrieve_context_for_question).
#
# run() and build_prompt() are stubs that raise NotImplementedError — callers
# must use chat() directly.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from core.knowledge_hub import KnowledgeHub
from agents.base_agent import BaseAgent


# ── System prompt template ────────────────────────────────────────────────────

_SYSTEM_TEMPLATE = """\
Você é um assistente especializado em dois domínios:

1. **Análise de reuniões e projetos**: responde perguntas com base nas informações do
   contexto fornecido (transcrições, requisitos, processos BPMN e vocabulário SBVR).
2. **Orientação ao usuário**: explica como utilizar o Process2Diagram usando o guia abaixo.

{p2d_guide}

═══ CONTEXTO DO PROJETO ═══
{context}
═══ FIM DO CONTEXTO ═══

REGRAS DE RESPOSTA:
1. Se a pergunta for sobre o conteúdo das reuniões, responda APENAS com base no contexto acima.
2. Se a pergunta for sobre como usar o Process2Diagram, use o guia acima.
3. Se a informação não estiver disponível em nenhuma das fontes, diga claramente:
   "Não encontrei informação sobre isso nos dados disponíveis."
4. Ao mencionar algo de uma transcrição, sempre cite a reunião (ex: "Na Reunião 3 — Título (data)...").
5. Se o participante for identificável no formato "Nome: texto" ou "NOME: texto", cite-o diretamente
   (ex: 'Pedro disse: "..."').
6. Seja organizado: use listas quando houver múltiplos itens.
7. Não invente, não extrapole além do que está escrito no contexto ou no guia.
8. Responda em Português do Brasil, a menos que o usuário escreva em outro idioma.
9. Para requisitos, sempre inclua o identificador (ex: REQ-001) e o tipo quando relevante.
10. Para regras SBVR, mencione o núcleo nominal e a declaração completa quando pertinente.
"""


# ── Agent ─────────────────────────────────────────────────────────────────────

class AgentAssistant(BaseAgent):
    """
    Conversational RAG agent for project/meeting Q&A + P2D usage orientation.

    Usage:
        agent = AgentAssistant(client_info, provider_cfg)
        response, tokens = agent.chat(history, context_text, question)
    """

    name = "assistant"
    skill_path = "skills/skill_assistant.md"

    # ── Stubs (this agent uses chat(), not the hub pipeline) ──────────────────

    def run(self, hub: KnowledgeHub) -> KnowledgeHub:
        raise NotImplementedError(
            "AgentAssistant does not use the hub pipeline. Use chat() instead."
        )

    def build_prompt(self, hub: KnowledgeHub) -> tuple[str, str]:
        raise NotImplementedError(
            "AgentAssistant does not use build_prompt(). Use chat() instead."
        )

    # ── System prompt builder ─────────────────────────────────────────────────

    def _build_system_prompt(self, context_text: str) -> str:
        """Build system prompt combining the P2D guide and the retrieved context."""
        try:
            p2d_guide = self._load_skill()
        except Exception:
            p2d_guide = "(guia do Process2Diagram não disponível)"

        return _SYSTEM_TEMPLATE.format(
            p2d_guide=p2d_guide,
            context=context_text,
        )

    # ── LLM call methods (multi-turn, plain text) ─────────────────────────────

    def _call_chat_openai(
        self,
        system: str,
        messages: list[dict],
        api_key: str,
        model: str,
    ) -> tuple[str, int]:
        """
        Call an OpenAI-compatible endpoint with full message history.
        Returns (response_text, tokens_used).
        """
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=self.provider_cfg.get("base_url"))
        full_messages = [{"role": "system", "content": system}] + messages
        resp = client.chat.completions.create(
            model=model,
            messages=full_messages,
            max_tokens=self.provider_cfg.get("max_tokens", 2048),
            temperature=0.3,
        )
        tokens = resp.usage.total_tokens if resp.usage else 0
        return resp.choices[0].message.content, tokens

    def _call_chat_anthropic(
        self,
        system: str,
        messages: list[dict],
        api_key: str,
        model: str,
    ) -> tuple[str, int]:
        """
        Call the Anthropic Messages API with full message history.
        Returns (response_text, tokens_used).
        """
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model,
            max_tokens=self.provider_cfg.get("max_tokens", 2048),
            temperature=0.3,
            system=system,
            messages=messages,
        )
        tokens = (msg.usage.input_tokens + msg.usage.output_tokens) if msg.usage else 0
        return msg.content[0].text, tokens

    # ── Public chat entry point ───────────────────────────────────────────────

    def chat(
        self,
        history: list[dict],
        context_text: str,
        question: str,
    ) -> tuple[str, int]:
        """
        Run a conversational turn against the RAG context + P2D guide.

        Args:
            history:      Prior turns — [{"role": "user"|"assistant", "content": "..."}]
                          Pass history[:-1] (exclude current question from history).
            context_text: Retrieved and formatted context from project_store.format_context().
            question:     Current user question (will be appended as the final user turn).

        Returns:
            (response_text, tokens_used)
        """
        system = self._build_system_prompt(context_text)
        messages = list(history) + [{"role": "user", "content": question}]

        client_type = self.provider_cfg["client_type"]
        api_key = self.client_info["api_key"]
        model = self.provider_cfg["default_model"]

        if client_type == "openai_compatible":
            return self._call_chat_openai(system, messages, api_key, model)
        elif client_type == "anthropic":
            return self._call_chat_anthropic(system, messages, api_key, model)
        else:
            raise ValueError(f"Unknown client_type: {client_type}")
