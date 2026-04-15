# agents/agent_assistant.py  (v12 — declared-intent detection + copy button fix)
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
import re
import threading
from typing import Callable

from core.knowledge_hub import KnowledgeHub
from agents.base_agent import BaseAgent

MAX_TOOL_ROUNDS = 5       # max LLM ↔ tool iterations before forcing final answer
_MAX_TOOL_RESULT_CHARS = 5_000   # truncate individual tool results above this (~1250 tokens)
_MAX_HISTORY_TURNS     = 3       # max user+assistant pairs kept from prior history
_MAX_HISTORY_MSG_CHARS = 1_500   # truncate individual history messages above this
# Budget: 131 072 token limit × ~3 chars/tok; reserve 12 k tokens for completion+system
_MAX_INPUT_CHARS       = 240_000


def _truncate_tool_result(result: str, label: str = "") -> str:
    """Cap a tool result to _MAX_TOOL_RESULT_CHARS to avoid context overflow."""
    if len(result) <= _MAX_TOOL_RESULT_CHARS:
        return result
    kept = result[: _MAX_TOOL_RESULT_CHARS]
    omitted = len(result) - _MAX_TOOL_RESULT_CHARS
    suffix = f"\n\n[… resultado truncado — {omitted} caracteres omitidos]"
    return kept.rstrip() + suffix


def _trim_history(history: list[dict]) -> list[dict]:
    """
    Keep only the last _MAX_HISTORY_TURNS user+assistant pairs AND
    truncate each individual message to _MAX_HISTORY_MSG_CHARS.
    """
    if not history:
        return []
    pairs_needed = _MAX_HISTORY_TURNS * 2
    trimmed = history[-pairs_needed:] if len(history) > pairs_needed else list(history)
    result = []
    for msg in trimmed:
        c = msg.get("content", "")
        if isinstance(c, str) and len(c) > _MAX_HISTORY_MSG_CHARS:
            c = c[:_MAX_HISTORY_MSG_CHARS] + " [… truncado]"
            msg = {**msg, "content": c}
        result.append(msg)
    return result


def _msgs_total_chars(msgs: list[dict]) -> int:
    total = 0
    for m in msgs:
        c = m.get("content") or ""
        if isinstance(c, list):
            for block in c:
                if isinstance(block, dict):
                    total += len(str(block.get("content", "")))
        else:
            total += len(str(c))
        for tc in (m.get("tool_calls") or []):
            total += len(str(tc))
    return total


def _enforce_budget(msgs: list[dict]) -> list[dict]:
    """
    Hard guardrail called before every API call.
    If total chars exceed _MAX_INPUT_CHARS:
      1. Replace tool/tool_result content with placeholder (oldest first).
      2. Remove old assistant messages entirely.
      3. As last resort, truncate remaining long messages.
    Always preserves msgs[0] (system) and msgs[-1] (current user question).
    """
    if _msgs_total_chars(msgs) <= _MAX_INPUT_CHARS:
        return msgs

    result = list(msgs)

    # Pass 1 — blank out tool results (least important, oldest first)
    for i in range(1, len(result) - 1):
        if _msgs_total_chars(result) <= _MAX_INPUT_CHARS:
            return result
        role = result[i].get("role", "")
        if role == "tool":
            result[i] = {
                "role": "tool",
                "tool_call_id": result[i].get("tool_call_id", ""),
                "content": "[omitido]",
            }

    # Pass 2 — remove oldest non-system/non-current messages entirely
    while len(result) > 3 and _msgs_total_chars(result) > _MAX_INPUT_CHARS:
        result.pop(1)

    # Pass 3 — truncate any remaining long content
    for i in range(1, len(result)):
        if _msgs_total_chars(result) <= _MAX_INPUT_CHARS:
            break
        c = result[i].get("content", "")
        if isinstance(c, str) and len(c) > 500:
            result[i] = {**result[i], "content": c[:500] + " [… truncado]"}

    return result


def _trim_msgs_if_needed(msgs: list[dict]) -> list[dict]:
    """Alias to _enforce_budget for post-tool-call trimming."""
    return _enforce_budget(msgs)

# ── DeepSeek DSML tool-call format parser ─────────────────────────────────────
# DeepSeek sometimes outputs tool calls using its internal DSML XML format in the
# response *content* instead of the standard OpenAI `tool_calls` field.
# These regexes detect and parse that format so the calls can still be executed.
#
# Observed format:
#   <｜DSML｜function_calls>            (｜ may be U+FF5C or U+007C)
#     <｜DSML｜invoke name="tool_name">
#       <｜DSML｜parameter name="param">value</｜DSML｜parameter>
#     </｜DSML｜invoke>
#   </｜DSML｜function_calls>
#
# We match both ASCII pipe | (U+007C) and fullwidth ｜ (U+FF5C) to be safe.

_P = r'[|\uff5c]'   # matches both pipe variants in a character class

_DSML_DETECT_RE = re.compile(_P + r'DSML' + _P)   # quick presence check
_DSML_INVOKE_RE = re.compile(
    r'<' + _P + r'DSML' + _P + r'invoke\s+name="([^"]+)">(.*?)</' + _P + r'DSML' + _P + r'invoke>',
    re.DOTALL,
)
_DSML_PARAM_RE = re.compile(
    r'<' + _P + r'DSML' + _P + r'parameter\s+name="([^"]+)"[^>]*>(.*?)</' + _P + r'DSML' + _P + r'parameter>',
    re.DOTALL,
)
# Strip any remaining <｜DSML｜...>…</｜DSML｜...> blocks
_DSML_ANY_TAG_RE = re.compile(
    r'<[/]?' + _P + r'DSML' + _P + r'[^>]*>',
    re.DOTALL,
)


def _parse_dsml_tool_calls(content: str) -> list[dict]:
    """
    Extract tool calls from DeepSeek DSML-formatted content.
    Returns a list of {"name": str, "args": dict} dicts.
    """
    calls: list[dict] = []
    for invoke_m in _DSML_INVOKE_RE.finditer(content):
        name = invoke_m.group(1).strip()
        body = invoke_m.group(2)
        args: dict = {}
        for param_m in _DSML_PARAM_RE.finditer(body):
            key = param_m.group(1).strip()
            val = param_m.group(2).strip()
            if val.lstrip("-").isdigit():
                val = int(val)  # type: ignore[assignment]
            args[key] = val
        calls.append({"name": name, "args": args})
    return calls


def _strip_dsml(content: str) -> str:
    """Remove DSML markup from a response string.

    Strategy: DeepSeek always appends DSML *after* the text content, so cutting
    at the first DSML tag position reliably isolates the human-readable part.
    Any residual stray tags are removed in a second pass.
    """
    m = re.search(r'<[|\uff5c]DSML[|\uff5c]', content)
    if m:
        content = content[:m.start()].rstrip()
    # Remove any stray DSML tags that may remain
    content = _DSML_ANY_TAG_RE.sub('', content)
    return content.strip()


# ── Correction-intent interceptor ────────────────────────────────────────────
# Detects substitution requests (substitua X por Y, troque X por Y, etc.) in
# the user message at the Python level so we never rely on LLM judgment to
# choose the right tool for this case.

_CORRECTION_RE = re.compile(
    r'(?:substitua|troque|corrija|altere|mude|renomeie|renomear)\s+'
    r'["\u201c\u201d]?(.+?)["\u201c\u201d]?\s+'
    r'(?:por|para)\s+'
    r'["\u201c\u201d\u201c]?(.+?)["\u201c\u201d\u201d]?'
    r'(?:\s+em\s+(?:todos\s+os\s+)?artefatos?|\s+(?:nos|em\s+nossos)\s+artefatos?|$)',
    re.IGNORECASE,
)

# Also match simpler form: "substitua X por Y" (without "em artefatos")
_CORRECTION_SIMPLE_RE = re.compile(
    r'(?:substitua|troque|corrija|altere|mude)\s+'
    r'["\u201c\u201d]?(.+?)["\u201c\u201d]?\s+'
    r'(?:por|para)\s+'
    r'["\u201c\u201d]?([^\s,\.]+)["\u201c\u201d]?',
    re.IGNORECASE,
)


def _detect_correction_intent(text: str) -> tuple[str, str] | None:
    """
    Return (find_text, replace_text) if the message is a substitution request,
    else None.  Prefers the longer pattern first (with "em artefatos"), falls
    back to the simple two-word form.
    """
    m = _CORRECTION_RE.search(text)
    if m:
        return m.group(1).strip().strip('"').strip('\u201c\u201d'), \
               m.group(2).strip().strip('"').strip('\u201c\u201d')
    m = _CORRECTION_SIMPLE_RE.search(text)
    if m:
        return m.group(1).strip().strip('"').strip('\u201c\u201d'), \
               m.group(2).strip().strip('"').strip('\u201c\u201d')
    return None


# ── SBVR-add interceptor ──────────────────────────────────────────────────────
# Detects "inclua X no SBVR/SVBR como Y", "adicione X ao SBVR", etc.
# Handles common typos (SVBR) and the "TERM - DEFINITION" dash pattern.
# When term+definition are both present, executes add_sbvr_term directly in
# Python and injects the result — LLM only needs to present the success.
# When only term is present, injects a directive for the LLM to call the tool
# immediately with an inferred definition (no user follow-up required).

_SBVR_KEYWORD = r'(?:svbr|sbvr|vocab(?:ulário)?\s+sbvr|vocab(?:ulário)?\s+svbr)'
_Q = r'["\u201c\u201d\u2018\u2019]'  # any quote variant

# Pattern 1: "inclua TERM - DEFINITION no SBVR/SVBR"  (dash separator)
_SBVR_DASH_RE = re.compile(
    r'(?:inclua?|adicione?|cadastre?|insira?|coloque?)\s+'
    r'(?:o\s+termo\s+)?' + _Q + r'?(.+?)' + _Q + r'?'
    + r'\s*[-\u2013\u2014]\s*'
    + r'(.+?)'
    + r'\s+(?:em\s+nosso|em\s+nossos|no|ao|em)\s+' + _SBVR_KEYWORD,
    re.IGNORECASE,
)

# Pattern 2: "inclua TERM no SBVR como DEFINITION"
_SBVR_COMO_RE = re.compile(
    r'(?:inclua?|adicione?|cadastre?|insira?|coloque?)\s+'
    r'(?:o\s+termo\s+)?' + _Q + r'?(.+?)' + _Q + r'?'
    + r'\s+(?:em\s+nosso|em\s+nossos|no|ao|em|ao\s+vocabulário\s+do)?\s*' + _SBVR_KEYWORD
    + r'(?:\s+como\s+' + _Q + r'?(.+?)' + _Q + r'?)?'
    + r'(?:\.|$)',
    re.IGNORECASE,
)

# Pattern 3: bare "TERM como DEFINITION no SBVR" (no verb at start)
_SBVR_BARE_RE = re.compile(
    _Q + r'?(\w[\w\s]{0,30})' + _Q + r'?\s+como\s+(.+?)\s+(?:no|ao|em)\s+' + _SBVR_KEYWORD,
    re.IGNORECASE,
)


def _strip_quotes(s: str) -> str:
    return s.strip().strip('"\'').strip('\u201c\u201d\u2018\u2019').strip()


_DELETE_MEETING_RE = re.compile(
    r'(?:exclua?|delete|remova?|apague?|elimine?)\s+'
    r'(?:a\s+)?'
    r'(?:reunião|reuni[aã]o|meeting)\s*'
    r'(?:n[oº°]?\s*)?(\d+)',
    re.IGNORECASE,
)

# Confirmation starters — when the message begins with these words it's a
# reply to a previous preview, not a fresh delete request; skip the interceptor.
_DELETE_CONFIRM_RE = re.compile(
    r'^\s*(?:sim|s[íi]|confirme?|confirmo|autorizo|autoriza[çc][aã]o|'
    r'pode|ok|yes|prossiga|execute|pode\s+excluir|pode\s+deletar|'
    r'eu\s+autorizo|eu\s+confirmo|dou\s+autoriza)[,.\s!]',
    re.IGNORECASE,
)


def _detect_delete_meeting_intent(text: str) -> int | None:
    """Return meeting_number if this is a fresh delete request (not a confirmation)."""
    # If the message starts with a confirmation word, it's answering a previous
    # preview — let the LLM handle it as a confirmation to call delete_meeting.
    if _DELETE_CONFIRM_RE.match(text.strip()):
        return None
    m = _DELETE_MEETING_RE.search(text)
    return int(m.group(1)) if m else None


def _detect_sbvr_update_origin_intent(text: str) -> str | None:
    """
    Return term name if the message asks to change an SBVR term's origin to 'assistente'.
    Detects: "altere a origem do termo X para Assistente", "mude a origem de X", etc.
    """
    m = re.search(
        r'(?:altere?|mude?|corrija?|atualize?)\s+(?:a\s+)?origem\s+(?:do\s+termo\s+)?'
        + _Q + r'?(\w[\w\s]{0,30})' + _Q + r'?',
        text, re.IGNORECASE,
    )
    if m:
        return _strip_quotes(m.group(1))
    # "origem do DCI para Assistente"
    m = re.search(
        r'origem\s+d[oa]\s+' + _Q + r'?(\w[\w\s]{0,20})' + _Q + r'?\s+para\s+assistente',
        text, re.IGNORECASE,
    )
    if m:
        return _strip_quotes(m.group(1))
    return None


def _detect_sbvr_add_intent(text: str) -> tuple[str, str] | None:
    """
    Return (term, definition_hint) if the message asks to add an SBVR term.
    definition_hint may be empty string when only the term was provided.
    Handles typo SVBR, dash/dash-en/dash-em separators, and quote variants.
    """
    m = _SBVR_DASH_RE.search(text)
    if m:
        return _strip_quotes(m.group(1)), _strip_quotes(m.group(2))
    m = _SBVR_BARE_RE.search(text)
    if m:
        return _strip_quotes(m.group(1)), _strip_quotes(m.group(2))
    m = _SBVR_COMO_RE.search(text)
    if m:
        term    = _strip_quotes(m.group(1))
        defhint = _strip_quotes(m.group(2) or "")
        return term, defhint
    return None


# ── System prompt templates ───────────────────────────────────────────────────

_SYSTEM_TOOLS_TEMPLATE = """\
╔══════════════════════════════════════════════════════════════════╗
║  CAPACIDADES CONFIRMADAS — leia antes de qualquer outra coisa   ║
╚══════════════════════════════════════════════════════════════════╝
Você é um assistente com CAPACIDADE TOTAL DE LEITURA E ESCRITA nos artefatos
do projeto. Suas ferramentas incluem operações que MODIFICAM dados no banco.

PROIBIÇÃO ABSOLUTA:
❌ NUNCA diga "não tenho capacidade de editar", "não posso modificar dados",
   "não consigo alterar" ou qualquer variante. Essa afirmação é FALSA —
   você possui preview_text_correction e apply_text_correction exatamente
   para isso. Dizer que não pode modificar é um erro grave de comportamento.

CAPACIDADES DE ESCRITA DISPONÍVEIS:
✅ preview_text_correction      — localiza e pré-visualiza substituições (somente-leitura)
✅ apply_text_correction        — aplica a substituição nos dados do Supabase (escrita)
✅ preview_meeting_deletion     — mostra o que seria excluído (somente-leitura)
✅ delete_meeting               — exclui reunião permanentemente (confirmed=true)
✅ reprocess_meeting_requirements — reprocessa requisitos de reunião armazenada

════════════════════════════════════════════════════════════════
REGRA PRIORITÁRIA — EXCLUSÃO DE REUNIÃO:
════════════════════════════════════════════════════════════════
Quando o usuário CONFIRMAR explicitamente a exclusão após ver o preview
(dizendo "sim", "confirme", "autorizo", "pode excluir", etc.):

FLUXO OBRIGATÓRIO:
  1. Chame IMEDIATAMENTE delete_meeting(meeting_number=N, confirmed=true)
     → NÃO mostre o preview novamente — ele já foi apresentado.
     → NÃO pergunte mais uma vez — a confirmação já foi dada.
     → NÃO descreva o que vai fazer — apenas execute a ferramenta.
  2. Reporte o resultado da exclusão.

Exemplos de confirmação:
  "sim, exclua a Reunião 5"   → delete_meeting(5, confirmed=true)
  "confirme a exclusão"       → delete_meeting(N, confirmed=true)
  "autorizo"                  → delete_meeting(N, confirmed=true)
  "pode excluir"              → delete_meeting(N, confirmed=true)

════════════════════════════════════════════════════════════════
REGRA PRIORITÁRIA — SUBSTITUIÇÃO / CORREÇÃO DE TEXTO:
════════════════════════════════════════════════════════════════
Quando o usuário pedir para substituir, trocar, corrigir ou alterar qualquer
termo/texto nos artefatos — incluindo:
  "substitua X por Y", "troque X por Y", "corrija X para Y",
  "pode alterar X?", "mude X para Y", "altere X em todos os artefatos"

FLUXO OBRIGATÓRIO (em ordem):
  1. Chame IMEDIATAMENTE preview_text_correction(find_text=X, replace_text=Y, scope="all")
     → NÃO chame search_transcript, get_sbvr_rules ou qualquer outra ferramenta antes.
  2. Apresente o resultado do preview: quantas ocorrências, em quais reuniões/campos.
  3. Pergunte: "Deseja aplicar a substituição?"
  4. Se o usuário confirmar ("sim", "pode", "aplique", "ok", "confirmar", "execute"),
     chame apply_text_correction com os mesmos parâmetros.
  5. Reporte quantos registros foram atualizados.

Exemplos:
  "Substitua ODCI por DCI"   → preview_text_correction("ODCI", "DCI", "all")
  "Troque FDTI por DTI"      → preview_text_correction("FDTI", "DTI", "all")
  "Corrija OSEUITE para SESUITE" → preview_text_correction("OSEUITE", "SESUITE", "all")
════════════════════════════════════════════════════════════════

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
  • Localizar texto / pré-visualizar correção → preview_text_correction
  • Aplicar correção (após confirmação) → apply_text_correction
  • Qualidade de reuniões / ROI / eficiência / desperdício → calculate_meeting_roi
  • Assuntos repetidos / tópicos sem progressão / ciclagem → get_recurring_topics
  • Status detalhado de uma reunião / verificar artefatos → get_meeting_metadata
  • Ver o que seria excluído de uma reunião → preview_meeting_deletion
  • Excluir reunião (após preview + confirmação) → delete_meeting
  • Reprocessar requisitos de reunião já armazenada → reprocess_meeting_requirements
- Você pode encadear múltiplas ferramentas quando necessário.
- Após obter os dados, sintetize uma resposta clara e objetiva.

PROTOCOLO COMPLETO DE CORREÇÃO DE TEXTO:
  1. Usuário solicita correção → chame preview_text_correction imediatamente.
  2. Apresente o resultado: quantas ocorrências, em quais reuniões/campos.
  3. AGUARDE confirmação explícita: "sim", "pode fazer", "confirmar", "aplique", "ok".
  4. SOMENTE após confirmação, chame apply_text_correction.
  5. Reporte: quantos registros foram atualizados.

REGRA ABSOLUTA: NUNCA chame apply_text_correction sem antes:
  (a) ter chamado preview_text_correction e apresentado o resultado, E
  (b) ter recebido confirmação explícita do usuário nesta mesma conversa.

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
        cancel_event: threading.Event | None = None,
        status_fn: Callable[[str], None] | None = None,
    ) -> tuple[str, int, list[str]]:
        """
        OpenAI / DeepSeek / Groq function-calling loop.
        Returns (response_text, total_tokens, tools_called).
        cancel_event: if set between rounds, returns early with an interruption message.
        status_fn: optional callback called with a human-readable status string on each step.
        """
        from openai import OpenAI
        from core.assistant_tools import get_tool_schemas_openai

        client   = OpenAI(api_key=api_key, base_url=self.provider_cfg.get("base_url"))
        tools    = get_tool_schemas_openai()
        msgs     = _enforce_budget([{"role": "system", "content": system}] + list(messages))
        total_tk = 0
        called: list[str] = []

        for round_n in range(MAX_TOOL_ROUNDS):
            if cancel_event and cancel_event.is_set():
                return "⏹ Processamento interrompido pelo usuário.", total_tk, called

            if status_fn:
                status_fn(f"🧠 Analisando pergunta (rodada {round_n + 1}/{MAX_TOOL_ROUNDS})…")

            resp = client.chat.completions.create(
                model=model,
                messages=_enforce_budget(msgs),
                tools=tools,
                tool_choice="auto",
                max_tokens=self.provider_cfg.get("max_tokens", 2048),
                temperature=0.3,
            )
            total_tk += resp.usage.total_tokens if resp.usage else 0
            choice = resp.choices[0]

            content = choice.message.content or ""

            if choice.finish_reason != "tool_calls" or not choice.message.tool_calls:
                # ── Declared-intent detection ──────────────────────────────────
                # Detect responses like "Vou verificar a ata..." that declare intent
                # to act but made no tool call — push the model to actually call it.
                _DECLARED_INTENT_RE = re.compile(
                    r'^(?:vou\s+(?:verificar|buscar|consultar|analisar|checar|obter|acessar|'
                    r'pesquisar|investigar|examinar|procurar|localizar|identificar|'
                    r'carregar|recuperar)|'
                    r'deixa\s+(?:eu|me)\s+(?:verificar|buscar|consultar|checar)|'
                    r'vamos\s+(?:ver|buscar|verificar|checar)|'
                    r'preciso\s+(?:verificar|buscar|consultar|checar)|'
                    r'primeiro\s+(?:vou|preciso|deixa)|'
                    r'para\s+responder.{0,30}preciso)',
                    re.IGNORECASE | re.DOTALL,
                )
                if _DECLARED_INTENT_RE.match(content.strip()) and round_n < MAX_TOOL_ROUNDS - 1:
                    # Model declared what it will do but didn't call a tool.
                    # Push with increasing urgency each round.
                    push_msg = (
                        "EXECUTE AGORA: chame a ferramenta imediatamente. "
                        "Use search_transcript para buscar o conteúdo pedido. "
                        "Não escreva texto — apenas chame a ferramenta."
                    ) if round_n >= 1 else (
                        "Chame a ferramenta agora. Não descreva o que vai fazer."
                    )
                    msgs.append({"role": "assistant", "content": content})
                    msgs.append({"role": "user", "content": push_msg})
                    continue  # next round

                # Check if DeepSeek leaked tool calls in DSML format inside the text
                if _DSML_DETECT_RE.search(content):
                    dsml_calls = _parse_dsml_tool_calls(content)
                    if dsml_calls:
                        # Execute the DSML-encoded tool calls
                        # Use stripped content for history; if nothing remains (pure DSML),
                        # use a neutral placeholder — never store raw DSML in conversation history.
                        msgs.append({"role": "assistant", "content": _strip_dsml(content) or "…"})
                        for dc in dsml_calls:
                            called.append(dc["name"])
                            if status_fn:
                                status_fn(f"🔧 Executando `{dc['name']}`…")
                            if cancel_event and cancel_event.is_set():
                                return "⏹ Processamento interrompido pelo usuário.", total_tk, called
                            result = executor.execute(dc["name"], dc["args"])
                            msgs.append({
                                "role": "user",
                                "content": f"[Resultado de {dc['name']}]:\n{_truncate_tool_result(result, dc['name'])}",
                            })
                            msgs = _trim_msgs_if_needed(msgs)
                        # Force a text-only final answer WITHOUT tools parameter
                        # (avoids another DSML cycle from DeepSeek)
                        if status_fn:
                            status_fn("🧠 Elaborando resposta final…")
                        if cancel_event and cancel_event.is_set():
                            return "⏹ Processamento interrompido pelo usuário.", total_tk, called
                        final_resp = client.chat.completions.create(
                            model=model,
                            messages=_enforce_budget(msgs),
                            max_tokens=self.provider_cfg.get("max_tokens", 2048),
                            temperature=0.3,
                            # No tools= → DeepSeek returns plain text, no DSML
                        )
                        total_tk += final_resp.usage.total_tokens if final_resp.usage else 0
                        final_text = final_resp.choices[0].message.content or ""
                        # If DSML persists in the final answer, strip it; never return raw DSML.
                        return _strip_dsml(final_text) or "✅ Consulta realizada. Verifique os dados.", total_tk, called
                # No DSML — clean any stray tags and return as final answer
                return _strip_dsml(content) or content, total_tk, called

            # Execute each tool call and append results.
            # Convert choice.message to a plain dict — newer OpenAI SDK versions
            # include a `refusal` field (and other extras) in ChatCompletionMessage
            # that DeepSeek's API rejects as "Bad message format".
            _tc_list = choice.message.tool_calls or []
            msgs.append({
                "role": "assistant",
                "content": choice.message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in _tc_list
                ],
            })
            for tc in _tc_list:
                if cancel_event and cancel_event.is_set():
                    return "⏹ Processamento interrompido pelo usuário.", total_tk, called
                fn_name = tc.function.name
                fn_args = json.loads(tc.function.arguments or "{}")
                called.append(fn_name)
                if status_fn:
                    status_fn(f"🔧 Executando `{fn_name}`…")
                result = executor.execute(fn_name, fn_args)
                msgs.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": _truncate_tool_result(result, fn_name),
                })
            msgs = _trim_msgs_if_needed(msgs)

        # Force a final answer after MAX_TOOL_ROUNDS
        if cancel_event and cancel_event.is_set():
            return "⏹ Processamento interrompido pelo usuário.", total_tk, called
        if status_fn:
            status_fn("🧠 Elaborando resposta final…")
        resp = client.chat.completions.create(
            model=model,
            messages=_enforce_budget(msgs),
            max_tokens=self.provider_cfg.get("max_tokens", 2048),
            temperature=0.3,
        )
        total_tk += resp.usage.total_tokens if resp.usage else 0
        raw = resp.choices[0].message.content or ""
        return _strip_dsml(raw) or "✅ Consulta realizada. Verifique os dados.", total_tk, called

    # ── Tool-use loop — Anthropic ─────────────────────────────────────────────

    def _chat_with_tools_anthropic(
        self,
        system: str,
        messages: list[dict],
        api_key: str,
        model: str,
        executor,
        cancel_event: threading.Event | None = None,
        status_fn: Callable[[str], None] | None = None,
    ) -> tuple[str, int, list[str]]:
        """
        Anthropic tool_use loop.
        Returns (response_text, total_tokens, tools_called).
        cancel_event: if set between rounds, returns early with an interruption message.
        status_fn: optional callback called with a human-readable status string on each step.
        """
        import anthropic
        from core.assistant_tools import get_tool_schemas_anthropic

        client   = anthropic.Anthropic(api_key=api_key)
        tools    = get_tool_schemas_anthropic()
        msgs     = _enforce_budget(list(messages))
        total_tk = 0
        called: list[str] = []

        for round_n in range(MAX_TOOL_ROUNDS):
            if cancel_event and cancel_event.is_set():
                return "⏹ Processamento interrompido pelo usuário.", total_tk, called

            if status_fn:
                status_fn(f"🧠 Analisando pergunta (rodada {round_n + 1}/{MAX_TOOL_ROUNDS})…")

            resp = client.messages.create(
                model=model,
                system=system,
                tools=tools,
                messages=_enforce_budget(msgs),
                max_tokens=self.provider_cfg.get("max_tokens", 2048),
                temperature=0.3,
            )
            total_tk += (resp.usage.input_tokens + resp.usage.output_tokens) if resp.usage else 0

            if resp.stop_reason != "tool_use":
                text = next((b.text for b in resp.content if hasattr(b, "text")), "")
                return text, total_tk, called

            tool_use_blocks = [b for b in resp.content if b.type == "tool_use"]
            if not tool_use_blocks:
                text = next((b.text for b in resp.content if hasattr(b, "text")), "")
                return text, total_tk, called

            msgs.append({"role": "assistant", "content": resp.content})

            tool_results = []
            for tb in tool_use_blocks:
                if cancel_event and cancel_event.is_set():
                    return "⏹ Processamento interrompido pelo usuário.", total_tk, called
                called.append(tb.name)
                if status_fn:
                    status_fn(f"🔧 Executando `{tb.name}`…")
                result = executor.execute(tb.name, tb.input or {})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tb.id,
                    "content": _truncate_tool_result(result, tb.name),
                })
            msgs.append({"role": "user", "content": tool_results})
            msgs = _trim_msgs_if_needed(msgs)

        # Force final answer
        if cancel_event and cancel_event.is_set():
            return "⏹ Processamento interrompido pelo usuário.", total_tk, called
        if status_fn:
            status_fn("🧠 Elaborando resposta final…")
        resp = client.messages.create(
            model=model,
            system=system,
            messages=_enforce_budget(msgs),
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
        messages = _trim_history(list(history)) + [{"role": "user", "content": question}]

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
        cancel_event: threading.Event | None = None,
        status_fn: Callable[[str], None] | None = None,
    ) -> tuple[str, int, list[str]]:
        """
        Tool-use conversational turn.

        The LLM receives the project data summary and a set of tools it can call
        to fetch specific data (participants, decisions, requirements, etc.).
        It decides which tools to invoke based on the question, executes them,
        and synthesises a final answer.

        Args:
            history:       Prior turns — [{"role": "user"|"assistant", "content": "..."}]
                           Pass history[:-1] (exclude current question).
            question:      Current user question.
            project_id:    Supabase project UUID.
            project_name:  Human-readable project name (for the system prompt).
            cancel_event:  threading.Event — set it to interrupt the loop between rounds.
            status_fn:     Optional callable(str) invoked with step descriptions
                           (e.g. "🔧 Executando `get_meeting_list`…").

        Returns:
            (response_text, tokens_used, tools_called)
            tools_called is a list of tool names that were invoked.
        """
        from core.assistant_tools import AssistantToolExecutor

        system   = self._build_system_prompt_tools(project_name, project_id)
        messages = _trim_history(list(history)) + [{"role": "user", "content": question}]
        executor = AssistantToolExecutor(
            project_id,
            llm_config={
                "api_key":      self.client_info.get("api_key", ""),
                "model":        self.provider_cfg.get("default_model", ""),
                "provider_cfg": self.provider_cfg,
            },
        )

        # ── Correction-intent pre-flight ─────────────────────────────────────
        # If the user is asking to substitute/replace text, bypass LLM tool
        # selection entirely: run preview_text_correction in Python, inject the
        # result as a synthetic tool turn, then let the LLM compose the
        # confirmation question from real data.
        correction = _detect_correction_intent(question)
        if correction:
            find_text, replace_text = correction
            if status_fn:
                status_fn("🔍 Localizando ocorrências de substituição…")
            preview_result = executor.execute(
                "preview_text_correction",
                {"find_text": find_text, "replace_text": replace_text, "scope": "all"},
            )
            # Inject as a completed tool interaction so the LLM sees the data
            messages.append({
                "role": "assistant",
                "content": (
                    f"[Pré-visualização automática]\n"
                    f"Chamei preview_text_correction(find_text=\"{find_text}\", "
                    f"replace_text=\"{replace_text}\", scope=\"all\") e obtive:\n\n"
                    f"{preview_result}"
                ),
            })
            messages.append({
                "role": "user",
                "content": (
                    "Com base nessa pré-visualização, apresente as ocorrências encontradas "
                    "e pergunte se devo aplicar a substituição."
                ),
            })
        # ── SBVR update-origin pre-flight ────────────────────────────────────
        if not correction:
            origin_term = _detect_sbvr_update_origin_intent(question)
            if origin_term:
                if status_fn:
                    status_fn(f"🔄 Atualizando origem do termo SBVR '{origin_term}'…")
                update_result = executor.execute(
                    "update_sbvr_term",
                    {"term": origin_term, "origin": "assistente"},
                )
                messages.append({
                    "role": "assistant",
                    "content": (
                        f"[Execução automática — update_sbvr_term]\n"
                        f"Chamei update_sbvr_term(term=\"{origin_term}\", origin=\"assistente\") "
                        f"e obtive:\n\n{update_result}"
                    ),
                })
                messages.append({
                    "role": "user",
                    "content": "Apresente o resultado ao usuário.",
                })

        # ── SBVR-add pre-flight ───────────────────────────────────────────────
        # When term+definition are both present in the message: execute
        # add_sbvr_term directly in Python and inject the result so the LLM
        # only needs to present the success — no LLM tool-selection needed.
        # When only the term is present: inject a strong directive telling the
        # LLM to call add_sbvr_term immediately with an inferred definition,
        # without asking the user for more information.
        if not correction:   # only if not already handled as a text correction
            sbvr_add = _detect_sbvr_add_intent(question)
            if sbvr_add:
                term, defhint = sbvr_add
                if status_fn:
                    status_fn(f"📖 Adicionando termo SBVR '{term}'…")

                if defhint:
                    # ── Definition provided → execute immediately in Python ──
                    add_result = executor.execute(
                        "add_sbvr_term",
                        {"term": term, "definition": defhint, "category": "Conceito"},
                    )
                    messages.append({
                        "role": "assistant",
                        "content": (
                            f"[Execução automática — add_sbvr_term]\n"
                            f"Chamei add_sbvr_term(term=\"{term}\", "
                            f"definition=\"{defhint}\", category=\"Conceito\") e obtive:\n\n"
                            f"{add_result}"
                        ),
                    })
                    messages.append({
                        "role": "user",
                        "content": "Apresente o resultado da inclusão ao usuário de forma clara.",
                    })
                else:
                    # ── No definition → strong directive: infer and call NOW ──
                    messages.append({
                        "role": "assistant",
                        "content": (
                            f"[Interceptação automática — adição de termo SBVR]\n"
                            f"O usuário pediu para adicionar o termo \"{term}\" ao SBVR.\n"
                            f"NÃO pergunte por mais informações. NÃO faça buscas nas transcrições.\n"
                            f"AÇÃO OBRIGATÓRIA: chame add_sbvr_term AGORA com:\n"
                            f"  term=\"{term}\"\n"
                            f"  definition=<definição inferida com base no contexto do projeto>\n"
                            f"  category=<categoria mais adequada: Ator, Conceito, Organização, Processo…>"
                        ),
                    })
                    messages.append({
                        "role": "user",
                        "content": "Prossiga: chame add_sbvr_term imediatamente.",
                    })
        # ── Delete-meeting pre-flight ─────────────────────────────────────────
        # When user requests deleting a meeting, bypass LLM tool-selection:
        # always call preview_meeting_deletion first in Python so the LLM
        # has real data to present before asking for confirmation.
        if not correction:
            del_num = _detect_delete_meeting_intent(question)
            if del_num is not None:
                if status_fn:
                    status_fn(f"⚠️ Prévia de exclusão — Reunião {del_num}…")
                preview_result = executor.execute(
                    "preview_meeting_deletion", {"meeting_number": del_num}
                )
                messages.append({
                    "role": "assistant",
                    "content": (
                        f"[Pré-visualização automática de exclusão]\n"
                        f"Chamei preview_meeting_deletion(meeting_number={del_num}) e obtive:\n\n"
                        f"{preview_result}"
                    ),
                })
                messages.append({
                    "role": "user",
                    "content": (
                        "Apresente ao usuário o que será excluído e pergunte se confirma "
                        "a exclusão. Aguarde confirmação explícita antes de chamar delete_meeting."
                    ),
                })
        # ─────────────────────────────────────────────────────────────────────

        client_type = self.provider_cfg["client_type"]
        api_key     = self.client_info["api_key"]
        model       = self.provider_cfg["default_model"]

        if client_type == "openai_compatible":
            return self._chat_with_tools_openai(
                system, messages, api_key, model, executor, cancel_event, status_fn
            )
        elif client_type == "anthropic":
            return self._chat_with_tools_anthropic(
                system, messages, api_key, model, executor, cancel_event, status_fn
            )
        else:
            raise ValueError(f"client_type '{client_type}' não suporta tool-use")
