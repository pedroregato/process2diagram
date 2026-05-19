# services/context_analyzer.py
# ─────────────────────────────────────────────────────────────────────────────
# Context analyzer — decides when to activate "long context mode" for an agent.
#
# What long context mode does (and doesn't do):
#   - Does NOT send a magic API parameter — there is none in the DeepSeek API.
#   - DOES increase max_tokens output limit (prevents truncation on complex BPMN
#     for very long transcripts).
#   - DOES inject an explicit instruction telling the LLM the full transcript is
#     available, discouraging unnecessary summarization.
#   - DOES increase API timeout to 180s (longer inputs → longer processing time).
#
# The current pipeline already sends the full transcript in a single call per
# agent — there is no chunking of agent prompts. The risk this module mitigates
# is *output* truncation: a complex 100k-token transcript may produce a BPMN
# with 40+ steps, which can exceed the default 4096-token output limit.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

# Agents that benefit from long context mode.
# Minutes and Requirements are excluded: they run in parallel and their outputs
# are typically compact enough to fit in the standard max_tokens.
LONG_CONTEXT_AGENTS: frozenset[str] = frozenset({"bpmn", "sbvr", "bmm"})

# Estimated token threshold above which long context mode is activated.
LONG_CONTEXT_THRESHOLD: int = 50_000


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for a given text.

    Tries tiktoken (cl100k_base) for accuracy; falls back to len(text)//4
    (Portuguese averages ~4 chars/token).
    """
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return len(text) // 4


def should_use_long_context(
    text: str,
    agent_name: str,
    enabled: bool = True,
) -> bool:
    """
    Return True when long context mode should be activated for this call.

    Conditions (all must be true):
      1. `enabled` is True (global toggle from session_state)
      2. agent_name is in LONG_CONTEXT_AGENTS
      3. estimated tokens exceed LONG_CONTEXT_THRESHOLD
    """
    if not enabled:
        return False
    if agent_name not in LONG_CONTEXT_AGENTS:
        return False
    return estimate_tokens(text) > LONG_CONTEXT_THRESHOLD


_LONG_CONTEXT_INSTRUCTION = """\
## TRANSCRIÇÃO COMPLETA DISPONÍVEL
Você está recebendo a transcrição COMPLETA desta reunião (sem truncamento ou chunking).
Analise o texto integralmente — não resuma, não omita detalhes de processos, atores,
decisões ou fluxos. Extraia todos os elementos relevantes para sua função específica.\
"""


def inject_long_context_instruction(system: str, use_long: bool) -> str:
    """
    Prepend the long context instruction to the system prompt when active.
    Returns the original system prompt unchanged when use_long is False.
    """
    if not use_long:
        return system
    return _LONG_CONTEXT_INSTRUCTION + "\n\n" + system
