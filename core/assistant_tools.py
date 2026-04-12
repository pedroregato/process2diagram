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
        {
            "type": "function",
            "function": {
                "name": "add_sbvr_term",
                "description": (
                    "Adiciona um novo termo ao vocabulário SBVR do projeto diretamente no banco de dados. "
                    "Use quando o usuário pedir para incluir, cadastrar ou adicionar um termo SBVR. "
                    "Não reprocessa reuniões — insere o termo manualmente."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "term": {
                            "type": "string",
                            "description": "Nome do termo (ex: 'DCI')",
                        },
                        "definition": {
                            "type": "string",
                            "description": "Definição do termo no domínio do negócio",
                        },
                        "category": {
                            "type": "string",
                            "description": (
                                "Categoria SBVR do termo. Valores típicos: "
                                "'Conceito', 'Ator', 'Processo', 'Documento', 'Sistema', 'Regra'. "
                                "Infira a categoria com base no termo e definição se não informada."
                            ),
                        },
                    },
                    "required": ["term", "definition"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update_sbvr_term",
                "description": (
                    "Atualiza um termo SBVR existente: definição, categoria e/ou origem. "
                    "USE quando o usuário pedir para alterar a origem de um termo para 'Assistente', "
                    "ou para corrigir a definição/categoria de um termo já cadastrado."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "term": {
                            "type": "string",
                            "description": "Nome do termo a atualizar (ex: 'DCI')",
                        },
                        "definition": {
                            "type": "string",
                            "description": "Nova definição (opcional — omita para não alterar)",
                        },
                        "category": {
                            "type": "string",
                            "description": "Nova categoria (opcional — omita para não alterar)",
                        },
                        "origin": {
                            "type": "string",
                            "description": (
                                "Rótulo de origem. Use 'assistente' para marcar como adicionado pelo assistente. "
                                "Padrão: 'assistente'."
                            ),
                        },
                    },
                    "required": ["term"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "add_sbvr_rule",
                "description": (
                    "Adiciona uma nova regra de negócio SBVR ao projeto diretamente no banco de dados. "
                    "Use quando o usuário pedir para incluir, cadastrar ou adicionar uma regra SBVR."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "statement": {
                            "type": "string",
                            "description": "Enunciado formal da regra no padrão SBVR",
                        },
                        "rule_type": {
                            "type": "string",
                            "description": (
                                "Tipo da regra SBVR. Valores: "
                                "'Definitional Rule', 'Behavioral Rule', 'Structural Rule'. "
                                "Infira com base no enunciado se não informado."
                            ),
                        },
                        "source": {
                            "type": "string",
                            "description": "Origem da regra (ex: nome da reunião, documento, ou 'manual'). Opcional.",
                        },
                    },
                    "required": ["statement"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "preview_text_correction",
                "description": (
                    "Localiza e pré-visualiza onde um texto ocorre nos dados do projeto (transcrições, atas, requisitos). "
                    "USE SEMPRE esta ferramenta primeiro quando o usuário pedir para substituir/trocar/corrigir um termo. "
                    "Retorna contagem de ocorrências e trechos de contexto. Somente-leitura — não modifica dados."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "find_text": {
                            "type": "string",
                            "description": "Texto a ser localizado (diferencia maiúsculas/minúsculas)",
                        },
                        "replace_text": {
                            "type": "string",
                            "description": "Texto pelo qual será substituído (apenas para exibição no preview)",
                        },
                        "scope": {
                            "type": "string",
                            "enum": ["transcripts", "minutes", "requirements", "all"],
                            "description": (
                                "Onde buscar: 'transcripts' (transcrições), 'minutes' (atas), "
                                "'requirements' (requisitos), 'all' (tudo)"
                            ),
                        },
                        "meeting_number": {
                            "type": "integer",
                            "description": "Limitar a busca a uma reunião específica (opcional; não aplicável a 'requirements')",
                        },
                    },
                    "required": ["find_text", "replace_text", "scope"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "apply_text_correction",
                "description": (
                    "Aplica substituição de texto nos dados armazenados no Supabase. "
                    "ATENÇÃO: esta operação modifica dados permanentemente. "
                    "NUNCA chame esta ferramenta sem antes apresentar o preview ao usuário e "
                    "receber confirmação explícita ('sim', 'confirmar', 'pode alterar', 'aplique', 'execute')."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "find_text": {
                            "type": "string",
                            "description": "Texto a ser substituído (diferencia maiúsculas/minúsculas)",
                        },
                        "replace_text": {
                            "type": "string",
                            "description": "Texto substituto",
                        },
                        "scope": {
                            "type": "string",
                            "enum": ["transcripts", "minutes", "requirements", "all"],
                            "description": (
                                "Onde aplicar: 'transcripts' (transcrições), 'minutes' (atas), "
                                "'requirements' (requisitos), 'all' (tudo)"
                            ),
                        },
                        "meeting_number": {
                            "type": "integer",
                            "description": "Limitar a uma reunião específica (opcional; não aplicável a 'requirements')",
                        },
                    },
                    "required": ["find_text", "replace_text", "scope"],
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

    def _get_fallback_meeting_id(self, db) -> str | None:
        """Return any meeting_id from this project — used when meeting_id NOT NULL constraint exists."""
        try:
            rows = db.table("meetings").select("id") \
                .eq("project_id", self.project_id).limit(1).execute().data or []
            return rows[0]["id"] if rows else None
        except Exception:
            return None

    def add_sbvr_term(
        self,
        term: str,
        definition: str,
        category: str = "Conceito",
    ) -> str:
        """Insert a new SBVR vocabulary term directly into the Supabase sbvr_terms table."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "❌ Supabase não configurado — não é possível inserir o termo."

        base_payload = {
            "project_id": self.project_id,
            "term":       term.strip(),
            "definition": definition.strip(),
            "category":   category.strip() or "Conceito",
        }
        fallback_mid = self._get_fallback_meeting_id(db)

        # Try 4 combinations: (source col present/absent) × (meeting_id null/fallback)
        attempts = []
        for include_source in (True, False):
            for mid in (None, fallback_mid):
                p = {**base_payload}
                if include_source:
                    p["source"] = "assistente"
                p["meeting_id"] = mid
                attempts.append(p)

        last_err = ""
        for p in attempts:
            if p.get("meeting_id") is None and fallback_mid is None:
                # skip null-mid variant if we have no fallback (same as next attempt)
                pass
            try:
                db.table("sbvr_terms").insert(p).execute()
                return (
                    f"✅ Termo SBVR adicionado com sucesso!\n"
                    f"• Termo: {term}\n"
                    f"• Definição: {definition}\n"
                    f"• Categoria: {category or 'Conceito'}"
                )
            except Exception as exc:
                last_err = str(exc)

        return (
            f"❌ Falha ao inserir termo SBVR após todas as tentativas.\n"
            f"Último erro: {last_err}\n"
            f"Execute o SQL de migração em Configurações → Banco de Dados para corrigir o schema."
        )

    def update_sbvr_term(
        self,
        term: str,
        definition: str | None = None,
        category: str | None = None,
        origin: str = "assistente",
    ) -> str:
        """Update an existing SBVR term's definition, category, and/or origin label."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "❌ Supabase não configurado."

        # Find the term
        try:
            rows = db.table("sbvr_terms").select("id, term, definition, category") \
                .eq("project_id", self.project_id) \
                .ilike("term", term.strip()) \
                .execute().data or []
        except Exception as exc:
            return f"❌ Erro ao buscar termo: {exc}"

        if not rows:
            return f"❌ Termo '{term}' não encontrado no vocabulário SBVR do projeto."

        patch: dict = {}
        if definition:
            patch["definition"] = definition.strip()
        if category:
            patch["category"] = category.strip()

        # Try to set source and clear meeting_id
        for include_source, clear_mid in ((True, True), (True, False), (False, False)):
            p = dict(patch)
            if include_source:
                p["source"] = origin
            if clear_mid:
                p["meeting_id"] = None
            if not p:
                continue
            try:
                db.table("sbvr_terms").update(p).eq("id", rows[0]["id"]).execute()
                updated_fields = []
                if "definition" in p:
                    updated_fields.append("definição")
                if "category" in p:
                    updated_fields.append("categoria")
                if "source" in p:
                    updated_fields.append(f"origem → '{origin}'")
                if "meeting_id" in p:
                    updated_fields.append("reunião de origem removida")
                return (
                    f"✅ Termo '{term}' atualizado com sucesso!\n"
                    f"• Campos alterados: {', '.join(updated_fields) or 'nenhum'}"
                )
            except Exception:
                continue

        return f"❌ Não foi possível atualizar o termo '{term}'. Execute o SQL de migração em Configurações → Banco de Dados."

    def add_sbvr_rule(
        self,
        statement: str,
        rule_type: str = "Behavioral Rule",
        source: str = "manual",
    ) -> str:
        """Insert a new SBVR business rule directly into the Supabase sbvr_rules table."""
        from modules.supabase_client import get_supabase_client
        from modules.text_utils import rule_keyword_pt
        db = get_supabase_client()
        if not db:
            return "❌ Supabase não configurado — não é possível inserir a regra."

        try:
            nucleo = rule_keyword_pt(statement)
            existing = db.table("sbvr_rules").select("rule_id") \
                .eq("project_id", self.project_id).execute()
            count = len(existing.data or []) + 1
            rule_id = f"RBN-{count:03d}"
        except Exception:
            rule_id = "RBN-001"
            nucleo  = statement.split()[0] if statement else "regra"

        payload = {
            "project_id":     self.project_id,
            "rule_id":        rule_id,
            "statement":      statement.strip(),
            "nucleo_nominal": nucleo,
            "rule_type":      rule_type.strip() or "Behavioral Rule",
            "source":         source.strip() or "manual",
        }

        def _success_msg():
            return (
                f"✅ Regra SBVR adicionada com sucesso!\n"
                f"• ID: {rule_id}\n"
                f"• Enunciado: {statement}\n"
                f"• Tipo: {rule_type or 'Behavioral Rule'}\n"
                f"• Origem: {source or 'manual'}"
            )

        try:
            db.table("sbvr_rules").insert({**payload, "meeting_id": None}).execute()
            return _success_msg()
        except Exception as exc1:
            err1 = str(exc1)

        fallback_mid = self._get_fallback_meeting_id(db)
        if fallback_mid:
            try:
                db.table("sbvr_rules").insert({**payload, "meeting_id": fallback_mid}).execute()
                return _success_msg()
            except Exception as exc2:
                return (
                    f"❌ Falha ao inserir regra SBVR.\n"
                    f"• Erro sem meeting_id: {err1}\n"
                    f"• Erro com meeting_id: {exc2}"
                )
        return f"❌ Falha ao inserir regra SBVR: {err1}"

    # ── Write tools ───────────────────────────────────────────────────────────

    def preview_text_correction(
        self,
        find_text: str,
        replace_text: str,
        scope: str,
        meeting_number: int | None = None,
    ) -> str:
        """
        Read-only preview: shows all occurrences of find_text within the
        requested scope without modifying any data.
        """
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        results: list[str] = []
        total_occurrences = 0

        # ── Meetings table (transcripts and/or minutes) ────────────────────
        if scope in ("transcripts", "minutes", "all"):
            try:
                q = (
                    db.table("meetings")
                    .select("meeting_number, title, transcript_clean, transcript_raw, minutes_md")
                    .eq("project_id", self.project_id)
                )
                if meeting_number is not None:
                    q = q.eq("meeting_number", meeting_number)
                rows = q.order("meeting_number").execute().data or []
            except Exception as exc:
                return f"Erro ao acessar reuniões: {exc}"

            for m in rows:
                n     = m.get("meeting_number", "?")
                title = m.get("title") or f"Reunião {n}"
                fields_to_check = []
                if scope in ("transcripts", "all"):
                    for fld in ("transcript_clean", "transcript_raw"):
                        val = m.get(fld) or ""
                        if val:
                            fields_to_check.append((fld, val))
                if scope in ("minutes", "all"):
                    val = m.get("minutes_md") or ""
                    if val:
                        fields_to_check.append(("minutes_md", val))

                for fld, text in fields_to_check:
                    count = text.count(find_text)
                    if count == 0:
                        continue
                    total_occurrences += count
                    # Extract up to 3 context snippets
                    snippets: list[str] = []
                    idx = 0
                    while len(snippets) < 3:
                        pos = text.find(find_text, idx)
                        if pos == -1:
                            break
                        start = max(0, pos - 60)
                        end   = min(len(text), pos + len(find_text) + 60)
                        snippet = text[start:end].replace("\n", " ")
                        if start > 0:
                            snippet = "…" + snippet
                        if end < len(text):
                            snippet = snippet + "…"
                        snippets.append(f'  "{snippet}"')
                        idx = pos + len(find_text)
                    extra = count - len(snippets)
                    field_label = {
                        "transcript_clean": "transcrição",
                        "transcript_raw":   "transcrição (raw)",
                        "minutes_md":       "ata",
                    }.get(fld, fld)
                    results.append(
                        f"• Reunião {n} — {title} [{field_label}]: {count} ocorrência(s)"
                    )
                    results.extend(snippets)
                    if extra > 0:
                        results.append(f"  … e mais {extra} ocorrência(s)")

        # ── Requirements table ─────────────────────────────────────────────
        if scope in ("requirements", "all"):
            try:
                req_rows = (
                    db.table("requirements")
                    .select("req_number, title, description")
                    .eq("project_id", self.project_id)
                    .execute().data or []
                )
            except Exception as exc:
                return f"Erro ao acessar requisitos: {exc}"

            for r in req_rows:
                n = r.get("req_number")
                req_id = f"REQ-{n:03d}" if isinstance(n, int) else "REQ-???"
                for fld in ("title", "description"):
                    text = r.get(fld) or ""
                    count = text.count(find_text)
                    if count == 0:
                        continue
                    total_occurrences += count
                    pos     = text.find(find_text)
                    start   = max(0, pos - 60)
                    end     = min(len(text), pos + len(find_text) + 60)
                    snippet = text[start:end].replace("\n", " ")
                    if start > 0:
                        snippet = "…" + snippet
                    if end < len(text):
                        snippet += "…"
                    results.append(
                        f"• {req_id} [{fld}]: {count} ocorrência(s)\n"
                        f'  "{snippet}"'
                    )

        if total_occurrences == 0:
            scope_label = {"transcripts": "transcrições", "minutes": "atas",
                           "requirements": "requisitos", "all": "todos os dados"}.get(scope, scope)
            return (
                f'Nenhuma ocorrência de "{find_text}" encontrada em {scope_label}.'
            )

        header = (
            f'Preview de correção: "{find_text}" → "{replace_text}"\n'
            f"Total: {total_occurrences} ocorrência(s) encontrada(s)\n"
            "──────────────────────────────────────────\n"
        )
        footer = (
            "\n──────────────────────────────────────────\n"
            "⚠️ Para aplicar a correção, confirme explicitamente (ex: 'sim, aplique')."
        )
        return header + "\n".join(results) + footer

    def apply_text_correction(
        self,
        find_text: str,
        replace_text: str,
        scope: str,
        meeting_number: int | None = None,
    ) -> str:
        """
        Applies find→replace across the specified scope in Supabase.
        Returns a summary of records updated.
        """
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        updated_records: list[str] = []
        errors: list[str] = []

        # ── Meetings table ─────────────────────────────────────────────────
        if scope in ("transcripts", "minutes", "all"):
            try:
                q = (
                    db.table("meetings")
                    .select("id, meeting_number, title, transcript_clean, transcript_raw, minutes_md")
                    .eq("project_id", self.project_id)
                )
                if meeting_number is not None:
                    q = q.eq("meeting_number", meeting_number)
                rows = q.order("meeting_number").execute().data or []
            except Exception as exc:
                return f"Erro ao acessar reuniões: {exc}"

            for m in rows:
                mid   = m["id"]
                n     = m.get("meeting_number", "?")
                title = m.get("title") or f"Reunião {n}"
                patch: dict = {}

                if scope in ("transcripts", "all"):
                    for fld in ("transcript_clean", "transcript_raw"):
                        val = m.get(fld) or ""
                        if find_text in val:
                            patch[fld] = val.replace(find_text, replace_text)

                if scope in ("minutes", "all"):
                    val = m.get("minutes_md") or ""
                    if find_text in val:
                        patch["minutes_md"] = val.replace(find_text, replace_text)

                if not patch:
                    continue

                try:
                    db.table("meetings").update(patch).eq("id", mid).execute()
                    fields_str = ", ".join(patch.keys())
                    updated_records.append(
                        f"✅ Reunião {n} — {title} (campos: {fields_str})"
                    )
                    # Invalidate the meeting cache so subsequent reads reflect the change
                    self._meeting_cache = None
                except Exception as exc:
                    errors.append(f"❌ Reunião {n} — {title}: {exc}")

        # ── Requirements table ─────────────────────────────────────────────
        if scope in ("requirements", "all"):
            try:
                req_rows = (
                    db.table("requirements")
                    .select("id, req_number, title, description")
                    .eq("project_id", self.project_id)
                    .execute().data or []
                )
            except Exception as exc:
                return f"Erro ao acessar requisitos: {exc}"

            for r in req_rows:
                rid    = r["id"]
                n      = r.get("req_number")
                req_id = f"REQ-{n:03d}" if isinstance(n, int) else "REQ-???"
                patch: dict = {}
                for fld in ("title", "description"):
                    val = r.get(fld) or ""
                    if find_text in val:
                        patch[fld] = val.replace(find_text, replace_text)
                if not patch:
                    continue
                try:
                    db.table("requirements").update(patch).eq("id", rid).execute()
                    updated_records.append(f"✅ {req_id} (campos: {', '.join(patch.keys())})")
                except Exception as exc:
                    errors.append(f"❌ {req_id}: {exc}")

        if not updated_records and not errors:
            return (
                f'Nenhuma ocorrência de "{find_text}" encontrada — nenhum dado alterado.'
            )

        lines = [
            f'Correção aplicada: "{find_text}" → "{replace_text}"',
            f"{len(updated_records)} registro(s) atualizado(s):",
        ]
        lines.extend(updated_records)
        if errors:
            lines.append(f"\n{len(errors)} erro(s):")
            lines.extend(errors)
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
                "add_sbvr_term":             lambda: self.add_sbvr_term(
                    tool_input["term"],
                    tool_input["definition"],
                    tool_input.get("category", "Conceito"),
                ),
                "update_sbvr_term":          lambda: self.update_sbvr_term(
                    tool_input["term"],
                    tool_input.get("definition"),
                    tool_input.get("category"),
                    tool_input.get("origin", "assistente"),
                ),
                "add_sbvr_rule":             lambda: self.add_sbvr_rule(
                    tool_input["statement"],
                    tool_input.get("rule_type", "Behavioral Rule"),
                    tool_input.get("source", "manual"),
                ),
                "preview_text_correction":   lambda: self.preview_text_correction(
                    tool_input["find_text"],
                    tool_input["replace_text"],
                    tool_input["scope"],
                    tool_input.get("meeting_number"),
                ),
                "apply_text_correction":     lambda: self.apply_text_correction(
                    tool_input["find_text"],
                    tool_input["replace_text"],
                    tool_input["scope"],
                    tool_input.get("meeting_number"),
                ),
            }
            if tool_name not in dispatch:
                return f"Ferramenta desconhecida: '{tool_name}'"
            return dispatch[tool_name]()
        except Exception as exc:
            return f"Erro ao executar '{tool_name}': {exc}"
