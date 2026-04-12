# core/assistant_tools.py
# ─────────────────────────────────────────────────────────────────────────────
# Tool definitions and executor for AgentAssistant tool-use mode.
#
# Each tool maps to an existing project_store / Supabase query.
# The LLM decides which tools to call based on the question context.
#
# Schemas are provided in two formats:
#   get_tool_schemas_openai()    → OpenAI / DeepSeek / Groq function calling
#   get_tool_schemas_anthropic() → Anthropic tool_use
#
# Execution:
#   executor = AssistantToolExecutor(project_id)
#   result   = executor.execute(tool_name, tool_input_dict)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations
import re


# ── Tool schemas ──────────────────────────────────────────────────────────────

def get_tool_schemas_openai() -> list[dict]:
    """Tool definitions in OpenAI function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": "get_meeting_list",
                "description": (
                    "Lista todas as reuniões do projeto com número, título, data, "
                    "e indica se possuem ata e transcrição armazenadas."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_meeting_participants",
                "description": (
                    "Retorna a lista completa de participantes de uma reunião específica, "
                    "extraída da ata gerada pelo pipeline."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_number": {
                            "type": "integer",
                            "description": "Número da reunião (ex: 1, 2, 3...)",
                        }
                    },
                    "required": ["meeting_number"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_meeting_decisions",
                "description": "Retorna as decisões formais tomadas em uma reunião específica.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_number": {
                            "type": "integer",
                            "description": "Número da reunião",
                        }
                    },
                    "required": ["meeting_number"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_meeting_action_items",
                "description": (
                    "Retorna os itens de ação (tarefas) definidos em uma reunião. "
                    "Pode filtrar por responsável."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_number": {
                            "type": "integer",
                            "description": "Número da reunião",
                        },
                        "responsible": {
                            "type": "string",
                            "description": "Filtrar tarefas por nome do responsável (opcional)",
                        },
                    },
                    "required": ["meeting_number"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_meeting_summary",
                "description": (
                    "Retorna a ata completa de uma reunião: participantes, pauta, "
                    "resumo, decisões e itens de ação."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_number": {
                            "type": "integer",
                            "description": "Número da reunião",
                        }
                    },
                    "required": ["meeting_number"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_transcript",
                "description": (
                    "Busca trechos relevantes nas transcrições das reuniões "
                    "usando palavras-chave. Use quando precisar de falas, discussões "
                    "ou contexto detalhado sobre um tema específico."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Palavras-chave ou frase para buscar nas transcrições",
                        },
                        "meeting_number": {
                            "type": "integer",
                            "description": "Limitar a busca a uma reunião específica (opcional)",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_requirements",
                "description": (
                    "Busca e lista requisitos do projeto. Pode filtrar por palavra-chave, "
                    "tipo (funcional, não-funcional, regra de negócio, restrição, interface) "
                    "e status (active, revised, contradicted, confirmed)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "Palavra-chave para buscar no título e descrição",
                        },
                        "req_type": {
                            "type": "string",
                            "description": "Tipo: funcional | não-funcional | regra de negócio | restrição | interface",
                        },
                        "status": {
                            "type": "string",
                            "description": "Status: active | revised | contradicted | confirmed",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_bpmn_processes",
                "description": "Lista os processos BPMN modelados no projeto com nome e número de versões.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_sbvr_terms",
                "description": "Busca termos do vocabulário de negócio (SBVR) do projeto.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "Palavra-chave para filtrar termos (opcional)",
                        }
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_sbvr_rules",
                "description": "Busca regras de negócio formais (SBVR) do projeto.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": "Palavra-chave para filtrar regras (opcional)",
                        }
                    },
                    "required": [],
                },
            },
        },
    ]


def get_tool_schemas_anthropic() -> list[dict]:
    """Tool definitions in Anthropic tool_use format."""
    return [
        {
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "input_schema": t["function"]["parameters"],
        }
        for t in get_tool_schemas_openai()
    ]


# ── Tool executor ─────────────────────────────────────────────────────────────

class AssistantToolExecutor:
    """
    Executes tool calls for AgentAssistant.

    Each method queries Supabase via existing project_store functions and
    returns a plain-text result string ready to be injected back into the LLM.
    """

    def __init__(self, project_id: str):
        self.project_id = project_id
        self._meeting_cache: list[dict] | None = None

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _get_meetings(self) -> list[dict]:
        """Fetch all meetings for the project (cached for the lifetime of the executor)."""
        if self._meeting_cache is None:
            from modules.supabase_client import get_supabase_client
            db = get_supabase_client()
            if not db:
                self._meeting_cache = []
            else:
                try:
                    self._meeting_cache = (
                        db.table("meetings")
                        .select(
                            "id, meeting_number, title, meeting_date, "
                            "minutes_md, transcript_clean, transcript_raw"
                        )
                        .eq("project_id", self.project_id)
                        .order("meeting_number")
                        .execute()
                        .data or []
                    )
                except Exception:
                    self._meeting_cache = []
        return self._meeting_cache

    def _find_meeting(self, meeting_number: int) -> dict | None:
        for m in self._get_meetings():
            if m.get("meeting_number") == meeting_number:
                return m
        return None

    @staticmethod
    def _section(minutes_md: str, *section_names: str) -> str:
        """Extract a named section from minutes markdown. Tries each name in order."""
        for name in section_names:
            m = re.search(
                rf'##\s*{re.escape(name)}\s*\n([\s\S]*?)(?=\n##|\Z)',
                minutes_md,
                re.IGNORECASE,
            )
            if m:
                return m.group(1).strip()
        return ""

    # ── Tool implementations ──────────────────────────────────────────────────

    def get_meeting_list(self) -> str:
        meetings = self._get_meetings()
        if not meetings:
            return "Nenhuma reunião encontrada no projeto."
        lines = [f"Reuniões do projeto ({len(meetings)} no total):"]
        for m in meetings:
            n     = m.get("meeting_number", "?")
            title = m.get("title") or "Sem título"
            date  = m.get("meeting_date") or "—"
            flags = []
            if m.get("minutes_md"):
                flags.append("✓ ata")
            if m.get("transcript_clean") or m.get("transcript_raw"):
                flags.append("✓ transcrição")
            flag_str = ", ".join(flags) if flags else "✗ sem dados"
            lines.append(f"  Reunião {n}: {title} ({date}) [{flag_str}]")
        return "\n".join(lines)

    def get_meeting_participants(self, meeting_number: int) -> str:
        m = self._find_meeting(meeting_number)
        if not m:
            return f"Reunião {meeting_number} não encontrada no projeto."
        title   = m.get("title") or f"Reunião {meeting_number}"
        date    = m.get("meeting_date") or ""
        header  = f"Reunião {meeting_number} — {title}" + (f" ({date})" if date else "")
        content = self._section(m.get("minutes_md") or "", "Participantes")
        if not content:
            return (
                f"{header}\n"
                "Informação de participantes não disponível — "
                "ata não gerada para esta reunião."
            )
        return f"{header}\nParticipantes:\n{content}"

    def get_meeting_decisions(self, meeting_number: int) -> str:
        m = self._find_meeting(meeting_number)
        if not m:
            return f"Reunião {meeting_number} não encontrada."
        title   = m.get("title") or f"Reunião {meeting_number}"
        header  = f"Reunião {meeting_number} — {title}"
        content = self._section(m.get("minutes_md") or "", "Decisões", "Decisions")
        if not content:
            return f"{header}\nNenhuma decisão registrada na ata."
        return f"{header}\nDecisões:\n{content}"

    def get_meeting_action_items(
        self,
        meeting_number: int,
        responsible: str | None = None,
    ) -> str:
        m = self._find_meeting(meeting_number)
        if not m:
            return f"Reunião {meeting_number} não encontrada."
        title   = m.get("title") or f"Reunião {meeting_number}"
        header  = f"Reunião {meeting_number} — {title}"
        content = self._section(
            m.get("minutes_md") or "",
            "Itens de Ação", "Action Items", "Ações",
        )
        if not content:
            return f"{header}\nNenhum item de ação registrado na ata."
        if responsible:
            filtered = [
                line for line in content.splitlines()
                if responsible.lower() in line.lower()
                or not line.strip().startswith(("-", "|", "*", "•"))
            ]
            content = "\n".join(filtered) if filtered else content
        return f"{header}\nItens de Ação:\n{content}"

    def get_meeting_summary(self, meeting_number: int) -> str:
        m = self._find_meeting(meeting_number)
        if not m:
            return f"Reunião {meeting_number} não encontrada."
        title      = m.get("title") or f"Reunião {meeting_number}"
        date       = m.get("meeting_date") or ""
        minutes_md = m.get("minutes_md") or ""
        header     = (
            f"=== Ata: Reunião {meeting_number} — {title}"
            + (f" ({date})" if date else "")
            + " ==="
        )
        if not minutes_md:
            return f"Reunião {meeting_number} — {title}: ata não disponível."
        body = minutes_md[:2500] + ("…" if len(minutes_md) > 2500 else "")
        return f"{header}\n{body}"

    def search_transcript(
        self,
        query: str,
        meeting_number: int | None = None,
    ) -> str:
        from core.project_store import _extract_keywords, _extract_passages
        from modules.supabase_client import get_supabase_client

        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        keywords = _extract_keywords(query)
        if not keywords:
            return "Consulta sem palavras-chave úteis — tente termos mais específicos."

        try:
            q = (
                db.table("meetings")
                .select("meeting_number, title, meeting_date, transcript_clean, transcript_raw")
                .eq("project_id", self.project_id)
            )
            if meeting_number is not None:
                q = q.eq("meeting_number", meeting_number)
            rows = q.order("meeting_number").execute().data or []
        except Exception as exc:
            return f"Erro ao acessar transcrições: {exc}"

        results: list[str] = []
        for m in rows:
            transcript = m.get("transcript_clean") or m.get("transcript_raw") or ""
            if not transcript:
                continue
            passages = _extract_passages(transcript, keywords, max_passages=3)
            if not passages:
                continue
            n    = m.get("meeting_number", "?")
            titl = m.get("title") or ""
            date = m.get("meeting_date") or ""
            date_str = f" ({date})" if date else ""
            results.append(f"[Reunião {n} — {titl}{date_str}]")
            for i, p in enumerate(passages):
                results.append(p)
                if i < len(passages) - 1:
                    results.append("---")
            results.append("")

        if not results:
            scope = f" na Reunião {meeting_number}" if meeting_number else ""
            return f"Nenhum trecho encontrado para '{query}'{scope}."
        return "\n".join(results)

    def get_requirements(
        self,
        keyword: str | None = None,
        req_type: str | None = None,
        status: str | None = None,
    ) -> str:
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."
        try:
            q = (
                db.table("requirements")
                .select("req_number, title, description, req_type, status, priority")
                .eq("project_id", self.project_id)
                .order("req_number")
            )
            if req_type:
                q = q.eq("req_type", req_type)
            if status:
                q = q.eq("status", status)
            rows = q.execute().data or []
        except Exception as exc:
            return f"Erro ao acessar requisitos: {exc}"

        if keyword:
            kw = keyword.lower()
            rows = [
                r for r in rows
                if kw in (r.get("title") or "").lower()
                or kw in (r.get("description") or "").lower()
            ]

        if not rows:
            return "Nenhum requisito encontrado com os filtros fornecidos."

        lines = [f"Requisitos encontrados ({len(rows)}):"]
        for r in rows:
            n        = r.get("req_number")
            req_id   = f"REQ-{n:03d}" if isinstance(n, int) else "REQ-???"
            rtype    = r.get("req_type") or "—"
            rstatus  = r.get("status") or "—"
            rprio    = r.get("priority") or "—"
            title    = r.get("title") or ""
            desc     = (r.get("description") or "")[:150]
            if len(r.get("description") or "") > 150:
                desc += "..."
            lines.append(f"• {req_id} [{rtype} | {rstatus} | prioridade: {rprio}]: {title}")
            if desc:
                lines.append(f"  {desc}")
        return "\n".join(lines)

    def list_bpmn_processes(self) -> str:
        from core.project_store import list_bpmn_processes
        procs = list_bpmn_processes(self.project_id)
        if not procs:
            return "Nenhum processo BPMN registrado no projeto."
        lines = [f"Processos BPMN ({len(procs)}):"]
        for p in procs:
            lines.append(
                f"• {p.get('name')} — {p.get('version_count', 0)} versão(ões) "
                f"[status: {p.get('status', '—')}]"
            )
        return "\n".join(lines)

    def get_sbvr_terms(self, keyword: str | None = None) -> str:
        from core.project_store import list_sbvr_terms
        terms = list_sbvr_terms(self.project_id)
        if keyword:
            kw = keyword.lower()
            terms = [
                t for t in terms
                if kw in (t.get("term") or "").lower()
                or kw in (t.get("definition") or "").lower()
            ]
        if not terms:
            return "Nenhum termo SBVR encontrado."
        lines = [f"Termos SBVR ({len(terms)}):"]
        for t in terms:
            lines.append(f"• {t.get('term')}: {t.get('definition')}")
        return "\n".join(lines)

    def get_sbvr_rules(self, keyword: str | None = None) -> str:
        from core.project_store import list_sbvr_rules
        rules = list_sbvr_rules(self.project_id)
        if keyword:
            kw = keyword.lower()
            rules = [
                r for r in rules
                if kw in (r.get("statement") or "").lower()
                or kw in (r.get("nucleo_nominal") or "").lower()
            ]
        if not rules:
            return "Nenhuma regra de negócio SBVR encontrada."
        lines = [f"Regras de Negócio SBVR ({len(rules)}):"]
        for r in rules:
            rule_id   = r.get("rule_id") or ""
            statement = r.get("statement") or ""
            nucleo    = r.get("nucleo_nominal") or ""
            lines.append(f"• [{rule_id}] {nucleo}: {statement}")
        return "\n".join(lines)

    # ── Dispatcher ────────────────────────────────────────────────────────────

    def execute(self, tool_name: str, tool_input: dict) -> str:
        """Route a tool call by name to the appropriate implementation."""
        try:
            dispatch = {
                "get_meeting_list":         lambda: self.get_meeting_list(),
                "get_meeting_participants":  lambda: self.get_meeting_participants(tool_input["meeting_number"]),
                "get_meeting_decisions":     lambda: self.get_meeting_decisions(tool_input["meeting_number"]),
                "get_meeting_action_items":  lambda: self.get_meeting_action_items(
                    tool_input["meeting_number"],
                    tool_input.get("responsible"),
                ),
                "get_meeting_summary":       lambda: self.get_meeting_summary(tool_input["meeting_number"]),
                "search_transcript":         lambda: self.search_transcript(
                    tool_input["query"],
                    tool_input.get("meeting_number"),
                ),
                "get_requirements":          lambda: self.get_requirements(
                    keyword=tool_input.get("keyword"),
                    req_type=tool_input.get("req_type"),
                    status=tool_input.get("status"),
                ),
                "list_bpmn_processes":       lambda: self.list_bpmn_processes(),
                "get_sbvr_terms":            lambda: self.get_sbvr_terms(tool_input.get("keyword")),
                "get_sbvr_rules":            lambda: self.get_sbvr_rules(tool_input.get("keyword")),
            }
            if tool_name not in dispatch:
                return f"Ferramenta desconhecida: '{tool_name}'"
            return dispatch[tool_name]()
        except Exception as exc:
            return f"Erro ao executar '{tool_name}': {exc}"
