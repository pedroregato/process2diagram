# agents/agent_assistant.py
# ─────────────────────────────────────────────────────────────────────────────
# AgentAssistant — conversational RAG agent for meeting/project Q&A.
#
# Two modes:
#   chat(history, context_text, question)
#       Classic RAG: receives a pre-built context string and answers in one shot.
#
#   chat_with_tools(history, question, project_id, project_name)
#       Tool-use mode: the LLM decides which project_store tools to call.
#       Supports Claude (tool_use) and OpenAI-compatible (function_calling).
#       Max MAX_TOOL_ROUNDS rounds before forcing a final answer.
#
# run() and build_prompt() are stubs that raise NotImplementedError — callers
# must use chat() or chat_with_tools() directly.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations
import json

from core.knowledge_hub import KnowledgeHub
from agents.base_agent import BaseAgent

MAX_TOOL_ROUNDS = 5  # max LLM ↔ tool iterations before forcing final answer


# ── System prompt templates ───────────────────────────────────────────────────

_SYSTEM_TOOLS_TEMPLATE = """\
Você é um assistente especializado em análise de reuniões e projetos.

{p2d_guide}

═══ PROJETO: {project_name} ═══
{data_summary}
═══ FIM DO RESUMO ═══

INSTRUÇÕES DE USO DAS FERRAMENTAS:
- Use as ferramentas disponíveis para obter dados precisos antes de responder.
- Estratégia recomendada por tipo de pergunta:
  • Participantes de uma reunião → get_meeting_participants
  • Decisões ou ações de uma reunião → get_meeting_decisions / get_meeting_action_items
  • Visão geral de uma reunião → get_meeting_summary
  • Falas ou discussões específicas → search_transcript
  • Requisitos do projeto → get_requirements
  • Processos BPMN → list_bpmn_processes
  • Vocabulário ou regras SBVR → get_sbvr_terms / get_sbvr_rules
  • Lista de reuniões existentes → get_meeting_list
- Você pode encadear múltiplas ferramentas quando necessário.
- Após obter os dados, sintetize uma resposta clara e objetiva.

REGRAS DE RESPOSTA:
1. Responda APENAS com base nos dados retornados pelas ferramentas ou no guia acima.
2. Se a informação não for encontrada, diga: "Não encontrei essa informação nos dados disponíveis."
3. Sempre cite a reunião de origem (ex: "Na Reunião 3 — Título...").
4. Use listas quando houver múltiplos itens.
5. Não invente, não extrapole.
6. Responda em Português do Brasil, salvo se o usuário escrever em outro idioma.
7. Para requisitos, sempre inclua o identificador (REQ-001) e o tipo.
"""

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

    # ── Tool-use system prompt builder ───────────────────────────────────────

    def _build_system_prompt_tools(
        self,
        project_name: str,
        project_id: str,
    ) -> str:
        """Build the system prompt for tool-use mode (compact data summary, no raw context)."""
        try:
            p2d_guide = self._load_skill()
        except Exception:
            p2d_guide = "(guia do Process2Diagram não disponível)"

        from core.project_store import retrieve_data_summary
        ds = retrieve_data_summary(project_id)

        summary_lines: list[str] = []
        meetings = ds.get("meetings") or []
        summary_lines.append(f"Total de reuniões: {len(meetings)}")
        for m in meetings:
            flag = "✓ com ata" if m.get("has_transcript") else "✗ sem ata"
            summary_lines.append(
                f"  • Reunião {m.get('number','?')} — {m.get('title')} ({m.get('date')}) [{flag}]"
            )
        req_total = ds.get("req_total", 0)
        summary_lines.append(f"Total de requisitos: {req_total}")
        n_terms = ds.get("n_sbvr_terms", 0)
        n_rules = ds.get("n_sbvr_rules", 0)
        summary_lines.append(f"SBVR: {n_terms} termos, {n_rules} regras")
        bpmn_procs = ds.get("bpmn_processes") or []
        summary_lines.append(f"Processos BPMN: {len(bpmn_procs)}")

        return _SYSTEM_TOOLS_TEMPLATE.format(
            p2d_guide=p2d_guide,
            project_name=project_name,
            data_summary="\n".join(summary_lines),
        )

    # ── Tool-use loop — OpenAI-compatible ─────────────────────────────────────

    def _chat_with_tools_openai(
        self,
        system: str,
        messages: list[dict],
        api_key: str,
        model: str,
        executor,
    ) -> tuple[str, int, list[str]]:
        """
        OpenAI / DeepSeek / Groq function-calling loop.
        Returns (response_text, total_tokens, tools_called).
        """
        from openai import OpenAI
        from core.assistant_tools import get_tool_schemas_openai

        client   = OpenAI(api_key=api_key, base_url=self.provider_cfg.get("base_url"))
        tools    = get_tool_schemas_openai()
        msgs     = [{"role": "system", "content": system}] + list(messages)
        total_tk = 0
        called: list[str] = []

        for _ in range(MAX_TOOL_ROUNDS):
            resp = client.chat.completions.create(
                model=model,
                messages=msgs,
                tools=tools,
                tool_choice="auto",
                max_tokens=self.provider_cfg.get("max_tokens", 2048),
                temperature=0.3,
            )
            total_tk += resp.usage.total_tokens if resp.usage else 0
            choice = resp.choices[0]

            if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
                # Final text answer
                return choice.message.content or "", total_tk, called

            # Execute each tool call and append results
            msgs.append(choice.message)
            for tc in choice.message.tool_calls:
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments or "{}")
                called.append(fn_name)
                result  = executor.execute(fn_name, fn_args)
                msgs.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })

        # Force a final answer after MAX_TOOL_ROUNDS
        resp = client.chat.completions.create(
            model=model,
            messages=msgs,
            max_tokens=self.provider_cfg.get("max_tokens", 2048),
            temperature=0.3,
        )
        total_tk += resp.usage.total_tokens if resp.usage else 0
        return resp.choices[0].message.content or "", total_tk, called

    # ── Tool-use loop — Anthropic ─────────────────────────────────────────────

    def _chat_with_tools_anthropic(
        self,
        system: str,
        messages: list[dict],
        api_key: str,
        model: str,
        executor,
    ) -> tuple[str, int, list[str]]:
        """
        Anthropic tool_use loop.
        Returns (response_text, total_tokens, tools_called).
        """
        import anthropic
        from core.assistant_tools import get_tool_schemas_anthropic

        client   = anthropic.Anthropic(api_key=api_key)
        tools    = get_tool_schemas_anthropic()
        msgs     = list(messages)
        total_tk = 0
        called: list[str] = []

        for _ in range(MAX_TOOL_ROUNDS):
            resp = client.messages.create(
                model=model,
                system=system,
                tools=tools,
                messages=msgs,
                max_tokens=self.provider_cfg.get("max_tokens", 2048),
                temperature=0.3,
            )
            total_tk += (resp.usage.input_tokens + resp.usage.output_tokens) if resp.usage else 0

            if resp.stop_reason != "tool_use":
                # Final text answer — extract first text block
                text = next(
                    (b.text for b in resp.content if hasattr(b, "text")),
                    "",
                )
                return text, total_tk, called

            # Collect tool_use blocks
            tool_use_blocks = [b for b in resp.content if b.type == "tool_use"]
            if not tool_use_blocks:
                text = next(
                    (b.text for b in resp.content if hasattr(b, "text")),
                    "",
                )
                return text, total_tk, called

            # Append assistant turn (full content list)
            msgs.append({"role": "assistant", "content": resp.content})

            # Execute tools and build tool_result turn
            tool_results = []
            for tb in tool_use_blocks:
                called.append(tb.name)
                result = executor.execute(tb.name, tb.input or {})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tb.id,
                    "content": result,
                })
            msgs.append({"role": "user", "content": tool_results})

        # Force final answer
        resp = client.messages.create(
            model=model,
            system=system,
            messages=msgs,
            max_tokens=self.provider_cfg.get("max_tokens", 2048),
            temperature=0.3,
        )
        total_tk += (resp.usage.input_tokens + resp.usage.output_tokens) if resp.usage else 0
        text = next((b.text for b in resp.content if hasattr(b, "text")), "")
        return text, total_tk, called

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

    def chat_with_tools(
        self,
        history: list[dict],
        question: str,
        project_id: str,
        project_name: str = "",
    ) -> tuple[str, int, list[str]]:
        """
        Tool-use conversational turn.

        The LLM receives the project data summary and a set of tools it can call
        to fetch specific data (participants, decisions, requirements, etc.).
        It decides which tools to invoke based on the question, executes them,
        and synthesises a final answer.

        Args:
            history:      Prior turns — [{"role": "user"|"assistant", "content": "..."}]
                          Pass history[:-1] (exclude current question).
            question:     Current user question.
            project_id:   Supabase project UUID.
            project_name: Human-readable project name (for the system prompt).

        Returns:
            (response_text, tokens_used, tools_called)
            tools_called is a list of tool names that were invoked.
        """
        from core.assistant_tools import AssistantToolExecutor

        system   = self._build_system_prompt_tools(project_name, project_id)
        messages = list(history) + [{"role": "user", "content": question}]
        executor = AssistantToolExecutor(project_id)

        client_type = self.provider_cfg["client_type"]
        api_key     = self.client_info["api_key"]
        model       = self.provider_cfg["default_model"]

        if client_type == "openai_compatible":
            return self._chat_with_tools_openai(system, messages, api_key, model, executor)
        elif client_type == "anthropic":
            return self._chat_with_tools_anthropic(system, messages, api_key, model, executor)
        else:
            raise ValueError(f"client_type '{client_type}' não suporta tool-use")
