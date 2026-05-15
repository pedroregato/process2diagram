# adapters/langchain_tools.py
# ─────────────────────────────────────────────────────────────────────────────
# LangChain Tool wrappers over existing AssistantToolExecutor.
#
# Builds a list of LangChain Tool objects from the same Supabase queries
# already used by the AgentAssistant, with no logic duplication.
#
# Public API:
#   build_langchain_tools(project_id, is_admin, llm_config)
#       -> (AssistantToolExecutor, list[Tool])
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import logging

_log = logging.getLogger(__name__)


# ── Helper: parse tool input ──────────────────────────────────────────────────

def _parse_json_arg(arg: str) -> dict:
    """Parse JSON string arg; return {} on failure or empty input."""
    if not arg or str(arg).strip() in ("", "all", "none"):
        return {}
    s = str(arg).strip()
    try:
        parsed = json.loads(s)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass
    return {"input": s}


def _int_arg(arg) -> int:
    """Coerce arg to int (for meeting_number params)."""
    try:
        return int(str(arg).strip())
    except (ValueError, TypeError):
        return 1


# ── Knowledge Hub search (standalone, no executor needed) ────────────────────

def _search_kh(query: str, project_id: str) -> str:
    """Search the persistent Knowledge Hub (facts, entities, processes)."""
    try:
        from core.knowledge_store import get_facts, get_entities, get_processes

        parts: list[str] = []

        facts = get_facts(project_id, limit=10)
        if facts:
            parts.append("**Fatos consolidados:**")
            for f in facts[:5]:
                conf = f.get("confidence", 1.0)
                parts.append(
                    f"- [{f['fact_type']}] {f['content']}"
                    + (f" (conf: {conf:.0%})" if conf < 0.95 else "")
                )

        entities = get_entities(project_id, limit=20)
        if entities:
            parts.append("**Entidades organizacionais:**")
            for e in entities[:6]:
                parts.append(
                    f"- [{e['entity_type']}] {e['canonical_name']}"
                    f" — {e.get('occurrence_count', 1)} ocorrência(s)"
                )

        processes = get_processes(project_id)
        if processes:
            parts.append("**Processos documentados:**")
            for p in processes[:5]:
                parts.append(
                    f"- {p['process_name']}"
                    f" ({p.get('version_count', 1)} versão/ões)"
                )

        return "\n".join(parts) if parts else "Nenhum conhecimento acumulado encontrado para esta query."
    except Exception as exc:
        _log.warning("_search_kh(%s): %s", query, exc)
        return f"Knowledge Hub indisponível: {exc}"


# ── Main builder ──────────────────────────────────────────────────────────────

def build_langchain_tools(
    project_id: str,
    is_admin: bool = False,
    llm_config: dict | None = None,
) -> tuple:
    """
    Build LangChain Tool list wrapping AssistantToolExecutor.

    Returns: (executor, tools)
      executor — AssistantToolExecutor instance (caller may inspect _pending_charts)
      tools    — list[Tool] ready for create_react_agent
    """
    from langchain_core.tools import Tool
    from core.assistant_tools import AssistantToolExecutor

    executor = AssistantToolExecutor(project_id=project_id, llm_config=llm_config or {})

    tools = [
        Tool(
            name="get_meeting_list",
            description=(
                "Lista todas as reuniões do projeto com número, título, data e "
                "disponibilidade de ata/transcrição. Não requer input."
            ),
            func=lambda _: executor.execute("get_meeting_list", {}),
        ),
        Tool(
            name="count_artifacts",
            description=(
                "Conta artefatos do banco de dados. artifact_type: 'all' (dashboard completo), "
                "'requirements', 'meetings', 'bpmn_processes', 'sbvr_terms', 'sbvr_rules', "
                "'kh_facts', 'kh_entities'. "
                "Input JSON: {\"artifact_type\": \"all\"} ou {\"artifact_type\": \"requirements\", \"req_type\": \"Funcional\"}."
            ),
            func=lambda args: executor.execute("count_artifacts", _parse_json_arg(args)),
        ),
        Tool(
            name="get_meeting_participants",
            description=(
                "Retorna participantes de uma reunião. "
                "Input: número da reunião (inteiro)."
            ),
            func=lambda n: executor.execute(
                "get_meeting_participants", {"meeting_number": _int_arg(n)}
            ),
        ),
        Tool(
            name="get_meeting_decisions",
            description=(
                "Retorna decisões tomadas em uma reunião. "
                "Input: número da reunião (inteiro)."
            ),
            func=lambda n: executor.execute(
                "get_meeting_decisions", {"meeting_number": _int_arg(n)}
            ),
        ),
        Tool(
            name="get_meeting_action_items",
            description=(
                "Retorna action items / tarefas de uma reunião com responsável e prazo. "
                "Input: número da reunião (inteiro)."
            ),
            func=lambda n: executor.execute(
                "get_meeting_action_items", {"meeting_number": _int_arg(n)}
            ),
        ),
        Tool(
            name="get_meeting_summary",
            description=(
                "Retorna o resumo executivo de uma reunião. "
                "Input: número da reunião (inteiro)."
            ),
            func=lambda n: executor.execute(
                "get_meeting_summary", {"meeting_number": _int_arg(n)}
            ),
        ),
        Tool(
            name="get_requirements",
            description=(
                "Lista/busca requisitos do projeto. Use para LISTAR ou DETALHAR requisitos; "
                "use count_artifacts para CONTAR. "
                "Input JSON: {\"keyword\": \"...\", \"req_type\": \"Funcional\", "
                "\"priority\": \"Alta\", \"page\": 1, \"page_size\": 20}. "
                "Todos os campos são opcionais."
            ),
            func=lambda args: executor.execute("get_requirements", _parse_json_arg(args)),
        ),
        Tool(
            name="search_transcript",
            description=(
                "Busca semântica e por palavra-chave nas transcrições das reuniões. "
                "Input JSON: {\"query\": \"texto a buscar\", \"meeting_number\": 3} "
                "ou simplesmente o texto da query como string."
            ),
            func=lambda args: executor.execute(
                "search_transcript",
                _parse_json_arg(args) if str(args).strip().startswith("{") else {"query": str(args)},
            ),
        ),
        Tool(
            name="list_bpmn_processes",
            description=(
                "Lista processos BPMN documentados no projeto com versões disponíveis. "
                "Não requer input."
            ),
            func=lambda _: executor.execute("list_bpmn_processes", {}),
        ),
        Tool(
            name="get_sbvr_terms",
            description=(
                "Retorna termos do vocabulário SBVR (regras de negócio). "
                "Input: keyword para filtrar (string) ou vazio para todos."
            ),
            func=lambda kw: executor.execute(
                "get_sbvr_terms",
                {"keyword": str(kw)} if str(kw).strip() not in ("", "all", "none") else {},
            ),
        ),
        Tool(
            name="get_sbvr_rules",
            description=(
                "Retorna regras SBVR do projeto. "
                "Input: keyword para filtrar (string) ou vazio para todos."
            ),
            func=lambda kw: executor.execute(
                "get_sbvr_rules",
                {"keyword": str(kw)} if str(kw).strip() not in ("", "all", "none") else {},
            ),
        ),
        Tool(
            name="search_knowledge_hub",
            description=(
                "Busca conhecimento acumulado cross-sessão: processos recorrentes, "
                "fatos/regras consolidados, entidades organizacionais. "
                "Input: texto descrevendo o que buscar (string simples)."
            ),
            func=lambda query: _search_kh(str(query), project_id),
        ),
        Tool(
            name="render_table",
            description=(
                "Registra dados tabulares estruturados para exibição e exportação Excel. "
                "Use sempre que tiver dados em forma de tabela. "
                "Input JSON: {\"title\": \"...\", \"columns\": [\"Col1\", \"Col2\"], "
                "\"rows\": [[\"v1\", \"v2\"], [\"v3\", \"v4\"]]}."
            ),
            func=lambda args: executor.execute("render_table", _parse_json_arg(args)),
        ),
    ]

    if is_admin:
        tools.append(
            Tool(
                name="get_database_integrity",
                description="Relatório completo de integridade do banco de dados (admin). Não requer input.",
                func=lambda _: executor.execute("get_database_integrity", {}),
            )
        )

    return executor, tools
