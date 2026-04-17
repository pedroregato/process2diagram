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
        {
            "type": "function",
            "function": {
                "name": "calculate_meeting_roi",
                "description": (
                    "Calcula o ROI-TR (Retorno sobre Investimento de Tempo de Reunião) para uma "
                    "ou todas as reuniões do projeto. Analisa decisões concretas, itens de ação "
                    "com responsável e prazo, requisitos formalizados, participantes e estima "
                    "custo em horas. Retorna índice ROI-TR (0–10), Taxa de Retrabalho Conceitual "
                    "(TRC) e comparativo entre reuniões. "
                    "USE quando o usuário perguntar sobre qualidade, eficiência, desperdício de "
                    "tempo, produtividade, ROI ou indicadores das reuniões."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_number": {
                            "type": "integer",
                            "description": (
                                "Número de uma reunião específica. "
                                "Omita para calcular todas as reuniões do projeto."
                            ),
                        },
                        "cost_per_hour": {
                            "type": "number",
                            "description": (
                                "Custo médio por participante por hora em R$ (padrão: 150). "
                                "Use valores diferentes se o usuário informar custos específicos."
                            ),
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_recurring_topics",
                "description": (
                    "Detecta tópicos que foram discutidos em múltiplas reuniões sem resolução "
                    "definitiva — o padrão de 'patinação' que gera desperdício de tempo. "
                    "Usa embeddings semânticos quando disponíveis; caso contrário usa análise "
                    "de palavras-chave. "
                    "USE quando o usuário perguntar sobre assuntos repetidos, tópicos sem "
                    "progressão, ciclagem de discussões ou padrões de desperdício entre reuniões."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "threshold": {
                            "type": "number",
                            "description": (
                                "Limiar de similaridade semântica (0.80–0.98). "
                                "Padrão 0.87. Maior = correspondências mais estritas."
                            ),
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_meeting_metadata",
                "description": (
                    "Retorna metadados detalhados de uma reunião: presença de transcrição, ata, "
                    "requisitos, BPMN, termos SBVR e chunks de embedding. "
                    "USE para verificar o status de uma reunião antes de tomar ações sobre ela."
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
                "name": "preview_meeting_deletion",
                "description": (
                    "Exibe o que seria excluído ao deletar uma reunião: ata, transcrição, "
                    "requisitos, embeddings e outros dados associados. "
                    "SEMPRE chame esta ferramenta ANTES de delete_meeting. "
                    "Somente-leitura — não modifica dados."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_number": {
                            "type": "integer",
                            "description": "Número da reunião a ser pré-visualizada para exclusão",
                        }
                    },
                    "required": ["meeting_number"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "delete_meeting",
                "description": (
                    "Exclui permanentemente uma reunião e todos os seus dados associados "
                    "(requisitos, ata, transcrição, embeddings, BPMN, SBVR). "
                    "ATENÇÃO: operação IRREVERSÍVEL. "
                    "NUNCA chame sem antes chamar preview_meeting_deletion E receber "
                    "confirmação explícita do usuário ('sim', 'confirme', 'pode excluir', 'delete')."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_number": {
                            "type": "integer",
                            "description": "Número da reunião a excluir",
                        },
                        "confirmed": {
                            "type": "boolean",
                            "description": (
                                "Deve ser true SOMENTE após o usuário confirmar explicitamente "
                                "a exclusão depois de ver o preview. Padrão: false."
                            ),
                        },
                    },
                    "required": ["meeting_number"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "reprocess_meeting_requirements",
                "description": (
                    "Re-executa o AgentRequirements sobre a transcrição armazenada de uma reunião "
                    "e salva os novos requisitos no banco. Útil para reuniões que não tiveram "
                    "requisitos extraídos ou que precisam de reextração (ex: Reunião 6 com discussão "
                    "sobre legado e patinação). Requer transcrição armazenada no Supabase."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_number": {
                            "type": "integer",
                            "description": "Número da reunião a reprocessar",
                        },
                        "output_language": {
                            "type": "string",
                            "description": "Idioma dos requisitos extraídos. Padrão: 'Auto-detect'.",
                        },
                    },
                    "required": ["meeting_number"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_missing_minutes",
                "description": (
                    "Gera atas de reunião (AgentMinutes) para todas as reuniões do projeto "
                    "que possuem transcrição armazenada mas ainda não têm ata (minutes_md). "
                    "Usa o LLM para extrair participantes, pauta, decisões e encaminhamentos. "
                    "Salva o resultado em minutes_md no Supabase. "
                    "USE quando o usuário pedir para gerar atas faltantes, completar atas pendentes, "
                    "ou criar atas das reuniões sem ata."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_numbers": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": (
                                "Lista de números de reunião específicos a processar. "
                                "Omita para processar todas as reuniões elegíveis."
                            ),
                        },
                        "force_regenerate": {
                            "type": "boolean",
                            "description": (
                                "Se true, regenera a ata mesmo para reuniões que já possuem minutes_md. "
                                "Padrão: false (pula reuniões já com ata)."
                            ),
                        },
                        "output_language": {
                            "type": "string",
                            "description": "Idioma das atas geradas. Padrão: 'Auto-detect'.",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_speaker_contributions",
                "description": (
                    "Busca TODAS as falas e menções de um participante específico nas transcrições, "
                    "varrendo todos os chunks armazenados em ordem cronológica. "
                    "Muito mais completo que search_transcript para perguntas sobre contribuições, "
                    "papel ou posição de uma pessoa específica ao longo do projeto. "
                    "Também retorna requisitos atribuídos ao participante via cited_by. "
                    "USE quando o usuário perguntar: contribuições de alguém, o que X disse/propôs/"
                    "defendeu, papel/posição de uma pessoa, participação de X em reuniões."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "participant_name": {
                            "type": "string",
                            "description": (
                                "Nome do participante a buscar. Pode ser nome completo "
                                "(ex: 'Pedro Gentil') ou apenas o primeiro nome (ex: 'Pedro'). "
                                "Use o nome exatamente como aparece nas transcrições."
                            ),
                        },
                        "meeting_number": {
                            "type": "integer",
                            "description": (
                                "Limitar a busca a uma reunião específica (opcional). "
                                "Omita para buscar em todas as reuniões do projeto."
                            ),
                        },
                    },
                    "required": ["participant_name"],
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


# ── Tool catalog metadata (for UI display) ────────────────────────────────────

_TOOL_CATEGORIES: dict[str, str] = {
    # Consulta (read-only)
    "get_meeting_list":             "consulta",
    "get_meeting_participants":     "consulta",
    "get_meeting_decisions":        "consulta",
    "get_meeting_action_items":     "consulta",
    "get_meeting_summary":          "consulta",
    "search_transcript":            "consulta",
    "get_requirements":             "consulta",
    "list_bpmn_processes":          "consulta",
    "get_sbvr_terms":               "consulta",
    "get_sbvr_rules":               "consulta",
    "calculate_meeting_roi":        "consulta",
    "get_recurring_topics":         "consulta",
    "get_meeting_metadata":         "consulta",
    "preview_meeting_deletion":     "consulta",
    "preview_text_correction":      "consulta",
    # Escrita / Modificação
    "add_sbvr_term":                "escrita",
    "update_sbvr_term":             "escrita",
    "add_sbvr_rule":                "escrita",
    "apply_text_correction":        "escrita",
    "delete_meeting":               "escrita",
    "get_speaker_contributions":    "consulta",
    # Geração (LLM-powered)
    "generate_missing_minutes":     "geração",
    "reprocess_meeting_requirements": "geração",
}


def get_tool_catalog() -> list[dict]:
    """
    Return all tools with display metadata: name, description, parameters, category.
    Used by the Assistente UI to render a dynamic tool catalog — NOT sent to any LLM.
    """
    return [
        {
            "name":        t["function"]["name"],
            "description": t["function"]["description"],
            "params":      list(t["function"]["parameters"].get("properties", {}).keys()),
            "required":    t["function"]["parameters"].get("required", []),
            "category":    _TOOL_CATEGORIES.get(t["function"]["name"], "consulta"),
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

    def __init__(self, project_id: str, llm_config: dict | None = None):
        self.project_id = project_id
        self.llm_config = llm_config or {}   # {"api_key", "model", "provider_cfg"}
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

    # ── Meeting management tools ──────────────────────────────────────────────

    def get_meeting_metadata(self, meeting_number: int) -> str:
        """Detailed metadata for a single meeting: all stored artefacts + counts."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        m = self._find_meeting(meeting_number)
        if not m:
            return f"Reunião {meeting_number} não encontrada no projeto."

        mid   = m.get("id", "")
        title = m.get("title") or f"Reunião {meeting_number}"
        date  = m.get("meeting_date") or "—"

        has_transcript = bool(m.get("transcript_clean") or m.get("transcript_raw"))
        has_minutes    = bool(m.get("minutes_md"))
        transcript_len = len((m.get("transcript_clean") or m.get("transcript_raw") or "").split())

        counts: dict[str, int] = {}
        for table, filter_col in [
            ("requirements",      "project_id"),
            ("transcript_chunks", "meeting_id"),
            ("sbvr_terms",        "meeting_id"),
            ("bpmn_processes",    "project_id"),
        ]:
            try:
                fv = self.project_id if filter_col == "project_id" else mid
                rows = db.table(table).select("id").eq(filter_col, fv).execute().data or []
                counts[table] = len(rows)
            except Exception:
                counts[table] = -1

        # Also count requirements per meeting (first_meeting_id)
        try:
            req_rows = (
                db.table("requirements").select("id")
                .eq("project_id", self.project_id)
                .eq("first_meeting_id", mid)
                .execute().data or []
            )
            counts["requirements_this_meeting"] = len(req_rows)
        except Exception:
            counts["requirements_this_meeting"] = -1

        def _c(v: int) -> str:
            return str(v) if v >= 0 else "erro"

        lines = [
            f"=== Metadados: Reunião {meeting_number} — {title} ({date}) ===",
            f"ID interno: {mid}",
            "",
            "Artefatos armazenados:",
            f"  Transcrição: {'✅' if has_transcript else '❌'}",
        ]
        if has_transcript:
            lines.append(f"  Palavras na transcrição: {transcript_len:,}")
        lines += [
            f"  Ata (minutes_md): {'✅' if has_minutes else '❌'}",
            f"  Requisitos desta reunião: {_c(counts['requirements_this_meeting'])}",
            f"  Chunks de embedding: {_c(counts['transcript_chunks'])}",
            f"  Termos SBVR vinculados: {_c(counts['sbvr_terms'])}",
        ]
        return "\n".join(lines)

    def preview_meeting_deletion(self, meeting_number: int) -> str:
        """Show what would be cascade-deleted if the meeting were removed."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        m = self._find_meeting(meeting_number)
        if not m:
            return f"Reunião {meeting_number} não encontrada no projeto."

        mid   = m.get("id", "")
        title = m.get("title") or f"Reunião {meeting_number}"
        date  = m.get("meeting_date") or "—"

        cascade: list[str] = []
        for table, col in [
            ("requirements",      "first_meeting_id"),
            ("transcript_chunks", "meeting_id"),
            ("sbvr_terms",        "meeting_id"),
            ("sbvr_rules",        "meeting_id"),
            ("bpmn_processes",    "meeting_id"),
        ]:
            try:
                rows = db.table(table).select("id").eq(col, mid).execute().data or []
                if rows:
                    cascade.append(f"  • {len(rows)} registro(s) em `{table}`")
            except Exception:
                cascade.append(f"  • `{table}`: não foi possível verificar")

        has_transcript = bool(m.get("transcript_clean") or m.get("transcript_raw"))
        has_minutes    = bool(m.get("minutes_md"))

        lines = [
            f"⚠️  PRÉVIA DE EXCLUSÃO — Reunião {meeting_number}",
            f"   Título: {title}",
            f"   Data: {date}",
            f"   Transcrição: {'✅ presente' if has_transcript else '❌ ausente'}",
            f"   Ata: {'✅ presente' if has_minutes else '❌ ausente'}",
            "",
            "Dados que serão excluídos em cascata:",
        ]
        if cascade:
            lines += cascade
        else:
            lines.append("  (nenhum dado associado encontrado além do registro principal)")
        lines += [
            "",
            "⚠️  Esta operação é IRREVERSÍVEL.",
            "Para confirmar, responda: 'sim, exclua a Reunião N' ou 'confirme a exclusão'.",
        ]
        return "\n".join(lines)

    def delete_meeting(self, meeting_number: int, confirmed: bool = False) -> str:
        """Permanently delete a meeting and all cascade data."""
        if not confirmed:
            return (
                f"❌ Exclusão não confirmada. "
                f"Para excluir a Reunião {meeting_number}, confirme explicitamente: "
                f"'sim, exclua a Reunião {meeting_number}'."
            )
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        m = self._find_meeting(meeting_number)
        if not m:
            return f"Reunião {meeting_number} não encontrada."

        mid   = m.get("id", "")
        title = m.get("title") or f"Reunião {meeting_number}"

        try:
            # ── Step 1: Null-out non-cascade FK references in requirements ──────
            for fk_col in ("last_meeting_id", "first_meeting_id"):
                try:
                    db.table("requirements").update({fk_col: None}).eq(fk_col, mid).execute()
                except Exception:
                    pass  # column may not exist — safe to ignore

            # ── Step 2: Delete child rows in tables that may lack CASCADE DELETE ─
            # (transcript_chunks, sbvr_terms, sbvr_rules, bpmn_processes)
            for table in ("transcript_chunks", "sbvr_terms", "sbvr_rules", "bpmn_processes"):
                try:
                    db.table(table).delete().eq("meeting_id", mid).execute()
                except Exception:
                    pass  # table/column may not exist — safe to ignore

            # ── Step 3: Delete the meeting row itself ────────────────────────────
            db.table("meetings").delete().eq("id", mid).execute()
            self._meeting_cache = None  # invalidate cache
            return (
                f"✅ Reunião {meeting_number} — '{title}' excluída com sucesso.\n"
                "Todos os dados associados (requisitos, transcrição, ata, BPMN, "
                "SBVR e embeddings) foram removidos."
            )
        except Exception as exc:
            return f"❌ Erro ao excluir Reunião {meeting_number}: {exc}"

    def reprocess_meeting_requirements(
        self,
        meeting_number: int,
        output_language: str = "Auto-detect",
    ) -> str:
        """Re-run AgentRequirements on a stored transcript and save new requirements."""
        if not self.llm_config:
            return (
                "❌ Configuração LLM não disponível no executor. "
                "Certifique-se de que a chave de API está configurada no Assistente."
            )

        m = self._find_meeting(meeting_number)
        if not m:
            return f"Reunião {meeting_number} não encontrada no projeto."

        mid        = m.get("id", "")
        title      = m.get("title") or f"Reunião {meeting_number}"
        transcript = m.get("transcript_clean") or m.get("transcript_raw") or ""

        if not transcript:
            return (
                f"❌ Reunião {meeting_number} — '{title}' não possui transcrição armazenada. "
                "Faça upload da transcrição via TranscriptBackfill antes de reprocessar."
            )

        try:
            from core.knowledge_hub import KnowledgeHub
            from agents.agent_requirements import AgentRequirements
            from core.project_store import save_requirements_from_hub

            hub = KnowledgeHub.new()
            hub.transcript_clean = transcript
            hub.transcript_raw   = transcript

            provider_cfg = self.llm_config.get("provider_cfg", {})
            client_info  = {"api_key": self.llm_config.get("api_key", "")}

            agent = AgentRequirements(client_info, provider_cfg)
            hub   = agent.run(hub, output_language=output_language)

            if not hub.requirements.ready:
                return (
                    f"❌ AgentRequirements não produziu requisitos para Reunião {meeting_number}. "
                    "Verifique a transcrição ou tente outro provedor LLM."
                )

            n_reqs = len(hub.requirements.requirements)
            saved  = save_requirements_from_hub(mid, self.project_id, hub)

            return (
                f"✅ Reprocessamento concluído — Reunião {meeting_number} — '{title}'\n"
                f"• Requisitos extraídos: {n_reqs}\n"
                f"• Requisitos salvos no banco: {saved}\n"
                f"• Acesse o ReqTracker para visualizar os novos requisitos."
            )

        except Exception as exc:
            return f"❌ Erro ao reprocessar Reunião {meeting_number}: {exc}"

    # ── Cross-meeting recurring topics ───────────────────────────────────────

    def get_recurring_topics(self, threshold: float = 0.87) -> str:
        """Detect topics recurring across meetings (semantic or keyword fallback)."""
        from modules.cross_meeting_analyzer import find_recurring_topics as _find

        topics, method = _find(self.project_id, threshold=threshold, max_results=20)

        method_label = {
            "semantic":    "análise semântica de embeddings",
            "keyword":     "correspondência de palavras-chave (embeddings não disponíveis)",
            "unavailable": "Supabase indisponível",
            "error":       "erro ao acessar o banco",
        }.get(method, method)

        if not topics:
            return (
                f"Nenhum tópico recorrente detectado (método: {method_label}). "
                f"Limiar usado: {threshold:.2f}. "
                "Tente reduzir o limiar ou verifique se as transcrições estão disponíveis."
            )

        lines = [
            f"=== Tópicos Recorrentes entre Reuniões (método: {method_label}) ===",
            f"Limiar de similaridade: {threshold:.2f}",
            f"{len(topics)} tópico(s) identificado(s):",
            "",
        ]
        for t in topics:
            meet_str = ", ".join(f"Reunião {n}" for n in t.meetings)
            kw_str   = " · ".join(t.keywords[:5]) if t.keywords else "—"
            sim_str  = f"  (similaridade: {t.similarity:.2f})" if t.similarity > 0 else ""
            lines.append(f"• {t.intensity_label}  [{meet_str}]{sim_str}")
            lines.append(f"  Termos-chave: {kw_str}")
            lines.append(f"  Trecho (R{t.meetings[0]}): {t.excerpt_a[:200]}")
            if len(t.meetings) > 1:
                n_b = t.meetings[1]
                lines.append(f"  Trecho (R{n_b}): {t.excerpt_b[:200]}")
            lines.append("")

        # Meeting recurrence summary
        meeting_counts: dict[int, int] = {}
        for t in topics:
            for n in t.meetings:
                meeting_counts[n] = meeting_counts.get(n, 0) + 1
        if meeting_counts:
            lines.append("Reuniões com mais tópicos recorrentes:")
            for n, cnt in sorted(meeting_counts.items(), key=lambda x: -x[1])[:5]:
                lines.append(f"  Reunião {n}: {cnt} tópico(s)")

        return "\n".join(lines)

    # ── ROI-TR calculator ─────────────────────────────────────────────────────

    def calculate_meeting_roi(
        self,
        meeting_number: int | None = None,
        cost_per_hour: float = 150.0,
    ) -> str:
        """
        Compute ROI-TR (Return on Investment – Meeting Time) and TRC (Taxa de
        Retrabalho Conceitual) for one or all meetings in the project.

        All inputs come from existing Supabase data (minutes_md, transcripts,
        requirements). No LLM call is made.
        """
        import re as _re

        # ── Cyclical-discussion signal patterns ───────────────────────────────
        _CYCLE_SIGNALS = [
            r'\bcomo (?:eu|já) (?:disse|falei|mencionei)\b',
            r'\bcomo já (?:falamos|discutimos|abordamos)\b',
            r'\bjá (?:mencionei|mencionamos|foi dito|abordamos|discutimos)\b',
            r'\bvoltando ao mesmo\b',
            r'\bpatinando\b',
            r'\bde novo\b',
            r'\bnovamente\b',
            r'\bmais uma vez\b',
            r'\brepetindo\b',
            r'\brepete\b',
            r'\bnão avança\b',
            r'\bnão progride\b',
        ]
        _CYCLE_RE     = _re.compile('|'.join(_CYCLE_SIGNALS), _re.IGNORECASE)
        _RESP_RE      = _re.compile(
            r'\b[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÇÜ][a-záéíóúâêîôûãõàçü]+'
            r'(?:\s+[A-ZÁÉÍÓÚÂÊÎÔÛÃÕÀÇÜ][a-záéíóúâêîôûãõàçü]+)*\b'
        )
        _DEADLINE_RE  = _re.compile(
            r'\b(?:\d{1,2}/\d{1,2}(?:/\d{2,4})?'
            r'|\d{4}-\d{2}-\d{2}'
            r'|prazo|deadline'
            r'|até\s+\w+)\b',
            _re.IGNORECASE,
        )

        # ── Load meetings ─────────────────────────────────────────────────────
        meetings = self._get_meetings()
        if not meetings:
            return "Nenhuma reunião encontrada no projeto."

        if meeting_number is not None:
            meetings = [m for m in meetings if m.get("meeting_number") == meeting_number]
            if not meetings:
                return f"Reunião {meeting_number} não encontrada no projeto."

        # ── Load requirements (project-wide) ──────────────────────────────────
        try:
            from modules.supabase_client import get_supabase_client
            db = get_supabase_client()
            req_rows = (
                db.table("requirements")
                .select("req_number, first_meeting_id")
                .eq("project_id", self.project_id)
                .execute().data or []
            ) if db else []
        except Exception:
            req_rows = []

        total_reqs = len(req_rows)
        req_by_mid: dict[str, int] = {}
        for r in req_rows:
            mid = r.get("first_meeting_id")
            if mid:
                req_by_mid[mid] = req_by_mid.get(mid, 0) + 1

        results: list[str] = []
        all_roi: list[float] = []

        for m in meetings:
            n          = m.get("meeting_number", "?")
            title      = m.get("title") or f"Reunião {n}"
            date       = m.get("meeting_date") or ""
            minutes_md = m.get("minutes_md") or ""
            transcript = m.get("transcript_clean") or m.get("transcript_raw") or ""
            mid        = m.get("id") or ""

            # ── Participants ──────────────────────────────────────────────────
            part_text   = self._section(minutes_md, "Participantes")
            part_lines  = [l for l in part_text.splitlines() if l.strip()]
            n_part      = max(1, len(part_lines))

            # ── Decisions ────────────────────────────────────────────────────
            dec_text   = self._section(minutes_md, "Decisões", "Decisions")
            dec_lines  = [
                l for l in dec_text.splitlines()
                if l.strip() and l.strip()[0] in "-•*|123456789"
            ]
            n_decisions = len(dec_lines)

            # ── Action items ─────────────────────────────────────────────────
            act_text   = self._section(minutes_md, "Itens de Ação", "Action Items", "Ações")
            act_lines  = [l for l in act_text.splitlines() if l.strip()]
            n_act_total = len([
                l for l in act_lines
                if l.strip()[0:1] in "-•*|" or l.strip()[0:1].isdigit()
            ])
            n_act_done  = sum(
                1 for l in act_lines
                if bool(_DEADLINE_RE.search(l)) and bool(_RESP_RE.search(l))
            )

            # ── Requirements for this meeting ────────────────────────────────
            n_reqs = req_by_mid.get(mid, 0)

            # ── Transcript metrics ────────────────────────────────────────────
            words          = len(transcript.split()) if transcript else 0
            dur_min        = words / 130.0 if words else 0.0   # ~130 wpm in meetings
            dur_h          = dur_min / 60.0
            n_cycle        = len(_CYCLE_RE.findall(transcript)) if transcript else 0
            # TRC proxy: cycles per 500-word block, scaled 0–100
            trc = min(100.0, (n_cycle / max(1, words / 500)) * 20) if words > 0 else 0.0

            # ── Concrete Decisions composite score (DC) ───────────────────────
            dc = n_decisions + (n_act_done * 2) + (n_reqs * 1.5)

            # ── Cost estimate ────────────────────────────────────────────────
            cost = n_part * dur_h * cost_per_hour if dur_h > 0 else 0.0

            # ── ROI-TR (0–10) ─────────────────────────────────────────────────
            if cost > 0:
                roi = min(10.0, (dc * 1000.0 / cost) * 1.5)
            elif dc > 0:
                roi = 5.0   # decisions exist but duration unknown → neutral
            else:
                roi = 0.0
            all_roi.append(roi)

            # ── Labels ────────────────────────────────────────────────────────
            roi_label = (
                "🟢 Alto" if roi >= 7.5 else
                "🟡 Médio" if roi >= 4.5 else
                "🟠 Baixo" if roi >= 2.0 else
                "🔴 Crítico"
            )
            trc_label = (
                "🔴 Alto" if trc > 40 else
                "🟠 Médio" if trc > 20 else
                "🟢 Baixo"
            )
            no_data = not (minutes_md or transcript)

            block: list[str] = [
                f"┌─ Reunião {n}"
                + (f" — {title}" if title != f"Reunião {n}" else "")
                + (f" ({date})" if date else "")
                + (" ⚠️ sem dados" if no_data else ""),
                f"│  Participantes (est.):      {n_part}",
            ]
            if transcript:
                block.append(f"│  Duração estimada:          {dur_min:.0f} min ({dur_h:.1f}h)")
            if cost > 0:
                block.append(f"│  Custo estimado:            R$ {cost:,.0f}")
            block += [
                f"│  Decisões na ata:           {n_decisions}",
                f"│  Itens de ação total:       {n_act_total}",
                f"│  Itens c/ responsável+prazo:{n_act_done}",
                f"│  Requisitos formalizados:   {n_reqs}",
            ]
            if transcript:
                block.append(f"│  Sinais de ciclagem (TRC):  {n_cycle}x → TRC {trc:.0f}% {trc_label}")
            block.append(f"└─ ROI-TR: {roi:.1f}/10  {roi_label}")
            results.append("\n".join(block))

        # ── Project summary (multi-meeting) ───────────────────────────────────
        summary = ""
        if len(meetings) > 1 and all_roi:
            avg     = sum(all_roi) / len(all_roi)
            best_i  = all_roi.index(max(all_roi))
            worst_i = all_roi.index(min(all_roi))
            avg_lbl = (
                "🟢 Alto" if avg >= 7.5 else
                "🟡 Médio" if avg >= 4.5 else
                "🟠 Baixo" if avg >= 2.0 else
                "🔴 Crítico"
            )
            summary = (
                f"\n{'═' * 52}\n"
                f"RESUMO DO PROJETO ({len(meetings)} reuniões avaliadas)\n"
                f"  ROI-TR médio:        {avg:.1f}/10  {avg_lbl}\n"
                f"  Melhor reunião:      Reunião {meetings[best_i].get('meeting_number')} "
                f"(ROI {max(all_roi):.1f})\n"
                f"  Pior reunião:        Reunião {meetings[worst_i].get('meeting_number')} "
                f"(ROI {min(all_roi):.1f})\n"
                f"  Total de requisitos: {total_reqs}\n"
                f"  Custo/h utilizado:   R$ {cost_per_hour:.0f}/participante\n"
                f"{'═' * 52}"
            )

        footer = (
            "\n\nNota: ROI-TR = DC×peso / (Participantes × Horas × Custo/h). "
            "TRC = proxy linguístico de retrabalho conceitual (sinais de repetição na transcrição). "
            "Reuniões sem ata ou transcrição têm precisão limitada."
        )
        return (
            "=== Análise ROI-TR — Qualidade de Reuniões ===\n"
            + "\n\n".join(results)
            + summary
            + footer
        )

    def generate_missing_minutes(
        self,
        meeting_numbers: list[int] | None = None,
        force_regenerate: bool = False,
        output_language: str = "Auto-detect",
    ) -> str:
        """Generate minutes (AgentMinutes) for meetings that have transcripts but no minutes_md."""
        if not self.llm_config:
            return (
                "❌ Configuração LLM não disponível. "
                "Certifique-se de que a chave de API está configurada no Assistente."
            )

        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "❌ Supabase não disponível."

        # Fetch candidates
        try:
            q = (
                db.table("meetings")
                .select("id, meeting_number, title, transcript_clean, transcript_raw, minutes_md")
                .eq("project_id", self.project_id)
                .order("meeting_number")
            )
            all_meetings = q.execute().data or []
        except Exception as exc:
            return f"❌ Erro ao listar reuniões: {exc}"

        # Filter
        candidates = []
        for m in all_meetings:
            n          = m.get("meeting_number")
            transcript = m.get("transcript_clean") or m.get("transcript_raw") or ""
            has_minutes = bool((m.get("minutes_md") or "").strip())

            if not transcript.strip():
                continue  # no transcript — skip
            if has_minutes and not force_regenerate:
                continue  # already has minutes and not forcing
            if meeting_numbers is not None and n not in meeting_numbers:
                continue  # not in the requested list

            candidates.append(m)

        if not candidates:
            return (
                "Nenhuma reunião elegível encontrada.\n"
                "• Todas as reuniões já possuem ata, ou\n"
                "• Nenhuma reunião possui transcrição armazenada.\n"
                "Use `force_regenerate: true` para regenerar atas existentes."
            )

        from core.knowledge_hub import KnowledgeHub
        from agents.agent_minutes import AgentMinutes

        provider_cfg = self.llm_config.get("provider_cfg", {})
        client_info  = {"api_key": self.llm_config.get("api_key", "")}

        successes: list[str] = []
        failures:  list[str] = []

        for m in candidates:
            mid        = m.get("id", "")
            n          = m.get("meeting_number", "?")
            title      = m.get("title") or f"Reunião {n}"
            transcript = m.get("transcript_clean") or m.get("transcript_raw") or ""

            try:
                hub = KnowledgeHub.new()
                hub.transcript_clean = transcript
                hub.transcript_raw   = transcript

                agent   = AgentMinutes(client_info, provider_cfg)
                hub     = agent.run(hub, output_language=output_language)

                if not hub.minutes.ready:
                    failures.append(f"  • Reunião {n} — '{title}': AgentMinutes não retornou resultado.")
                    continue

                minutes_md = AgentMinutes.to_markdown(hub.minutes)
                db.table("meetings").update({"minutes_md": minutes_md}).eq("id", mid).execute()

                # Invalidate cache so subsequent tool calls see the new minutes
                self._meeting_cache = None

                successes.append(
                    f"  • Reunião {n} — '{title}': {len(minutes_md):,} chars"
                )
            except Exception as exc:
                failures.append(f"  • Reunião {n} — '{title}': {exc}")

        lines = [
            f"Geração de atas concluída — {len(successes)} sucesso(s), {len(failures)} falha(s).",
            "",
        ]
        if successes:
            lines.append(f"✅ Atas geradas ({len(successes)}):")
            lines.extend(successes)
        if failures:
            lines.append(f"\n❌ Falhas ({len(failures)}):")
            lines.extend(failures)
        if successes:
            lines.append(
                "\nAs atas foram salvas em `minutes_md` no Supabase. "
                "Use `get_meeting_summary` para visualizar qualquer ata gerada."
            )
        return "\n".join(lines)

    # ── Speaker contributions ─────────────────────────────────────────────────

    def get_speaker_contributions(
        self,
        participant_name: str,
        meeting_number: int | None = None,
    ) -> str:
        """
        Find ALL transcript chunks and requirements attributed to a specific participant.

        Strategy:
        1. Search transcript_chunks table (most complete — all chunks in order).
        2. For meetings without chunks, fall back to full transcript keyword search.
        3. Also pull requirements where cited_by contains the participant name.
        """
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        if not participant_name or not participant_name.strip():
            return "Nome do participante não fornecido."

        search_term = participant_name.strip()

        # ── Build meeting maps ─────────────────────────────────────────────────
        meetings = self._get_meetings()
        if not meetings:
            return "Nenhuma reunião encontrada no projeto."

        mid_to_num:   dict[str, int]  = {}
        mid_to_title: dict[str, str]  = {}
        num_to_mid:   dict[int, str]  = {}
        num_to_m:     dict[int, dict] = {}

        for m in meetings:
            mid = m.get("id")
            n   = m.get("meeting_number")
            if mid and n is not None:
                mid_to_num[mid]   = n
                mid_to_title[mid] = m.get("title") or f"Reunião {n}"
                num_to_mid[n]     = mid
                num_to_m[n]       = m

        # ── Restrict by meeting_number if given ───────────────────────────────
        if meeting_number is not None:
            if meeting_number not in num_to_mid:
                return f"Reunião {meeting_number} não encontrada no projeto."
            target_mids = {num_to_mid[meeting_number]}
        else:
            target_mids = set(mid_to_num.keys())

        # ── 1. Search transcript_chunks ───────────────────────────────────────
        chunks_by_meeting: dict[int, list[str]] = {}
        mids_with_chunks:  set[str]             = set()

        try:
            q = (
                db.table("transcript_chunks")
                .select("meeting_id, chunk_index, chunk_text")
                .eq("project_id", self.project_id)
                .ilike("chunk_text", f"%{search_term}%")
                .order("meeting_id")
                .order("chunk_index")
            )
            raw_chunks = q.execute().data or []
        except Exception as exc:
            raw_chunks = []

        for c in raw_chunks:
            mid = c.get("meeting_id")
            if mid not in target_mids:
                continue
            mids_with_chunks.add(mid)
            n = mid_to_num.get(mid)
            if n is None:
                continue
            if n not in chunks_by_meeting:
                chunks_by_meeting[n] = []
            chunks_by_meeting[n].append(c.get("chunk_text", ""))

        # ── 2. Fallback: full-transcript search for meetings without chunks ────
        for n, m in num_to_m.items():
            if meeting_number is not None and n != meeting_number:
                continue
            mid = num_to_mid.get(n, "")
            if mid in mids_with_chunks:
                continue  # already covered by chunk search
            transcript = m.get("transcript_clean") or m.get("transcript_raw") or ""
            if not transcript:
                continue
            # Manual passage extraction around participant name occurrences
            passages: list[str] = []
            text = transcript
            idx  = 0
            while len(passages) < 12:
                pos = text.lower().find(search_term.lower(), idx)
                if pos == -1:
                    break
                start    = max(0, pos - 200)
                end      = min(len(text), pos + 400)
                snippet  = text[start:end].strip()
                if start > 0:
                    snippet = "…" + snippet
                if end < len(text):
                    snippet += "…"
                passages.append(snippet)
                idx = pos + len(search_term)
            if passages:
                chunks_by_meeting[n] = passages

        # ── 3. Requirements with cited_by matching the participant ────────────
        reqs_by_meeting: dict[int, list[str]] = {}
        try:
            req_rows = (
                db.table("requirements")
                .select("req_number, title, cited_by, first_meeting_id")
                .eq("project_id", self.project_id)
                .ilike("cited_by", f"%{search_term}%")
                .execute().data or []
            )
            for r in req_rows:
                mid = r.get("first_meeting_id")
                n   = mid_to_num.get(mid) if mid else None
                if meeting_number is not None and n != meeting_number:
                    continue
                key = n or 0
                if key not in reqs_by_meeting:
                    reqs_by_meeting[key] = []
                rn     = r.get("req_number")
                req_id = f"REQ-{rn:03d}" if isinstance(rn, int) else "REQ-???"
                cited  = r.get("cited_by") or ""
                reqs_by_meeting[key].append(
                    f"  {req_id}: {r.get('title', '')}  [citado por: {cited}]"
                )
        except Exception:
            pass

        # ── 4. Format output ──────────────────────────────────────────────────
        all_meeting_nums = sorted(
            set(list(chunks_by_meeting.keys()) + list(reqs_by_meeting.keys()))
        )
        if not all_meeting_nums:
            scope_str = f" na Reunião {meeting_number}" if meeting_number else " no projeto"
            return (
                f"Nenhuma contribuição de '{search_term}' encontrada{scope_str}.\n"
                "Dica: verifique a grafia exata do nome como aparece nas transcrições. "
                "Tente variações como primeiro nome apenas, abreviações ou iniciais."
            )

        lines = [
            f"=== Contribuições de '{search_term}' ===",
            "",
        ]

        total_chunks = 0
        total_reqs   = 0

        for n in all_meeting_nums:
            mid   = num_to_mid.get(n)
            title = mid_to_title.get(mid, f"Reunião {n}") if mid else f"Reunião {n}"
            lines.append(f"── Reunião {n} — {title} ──")

            meeting_chunks = chunks_by_meeting.get(n, [])
            total_chunks  += len(meeting_chunks)
            if meeting_chunks:
                lines.append(f"  Trechos da transcrição ({len(meeting_chunks)} passagem(ns)):")
                for i, txt in enumerate(meeting_chunks[:10]):
                    display = txt[:450] + ("…" if len(txt) > 450 else "")
                    lines.append(f"  [{i + 1}] {display}")
                if len(meeting_chunks) > 10:
                    lines.append(f"  … e mais {len(meeting_chunks) - 10} passagem(ns) omitida(s)")

            meeting_reqs = reqs_by_meeting.get(n, [])
            total_reqs  += len(meeting_reqs)
            if meeting_reqs:
                lines.append(f"  Requisitos atribuídos ({len(meeting_reqs)}):")
                lines.extend(meeting_reqs[:8])
                if len(meeting_reqs) > 8:
                    lines.append(f"  … e mais {len(meeting_reqs) - 8} requisito(s)")

            lines.append("")

        lines.append(
            f"Resumo: {total_chunks} trecho(s) de transcrição + "
            f"{total_reqs} requisito(s) atribuído(s) em "
            f"{len(all_meeting_nums)} reunião(ões)."
        )
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
                "calculate_meeting_roi":     lambda: self.calculate_meeting_roi(
                    tool_input.get("meeting_number"),
                    float(tool_input.get("cost_per_hour", 150.0)),
                ),
                "get_recurring_topics":           lambda: self.get_recurring_topics(
                    float(tool_input.get("threshold", 0.87)),
                ),
                "get_meeting_metadata":           lambda: self.get_meeting_metadata(
                    tool_input["meeting_number"],
                ),
                "preview_meeting_deletion":       lambda: self.preview_meeting_deletion(
                    tool_input["meeting_number"],
                ),
                "delete_meeting":                 lambda: self.delete_meeting(
                    tool_input["meeting_number"],
                    bool(tool_input.get("confirmed", False)),
                ),
                "reprocess_meeting_requirements": lambda: self.reprocess_meeting_requirements(
                    tool_input["meeting_number"],
                    tool_input.get("output_language", "Auto-detect"),
                ),
                "generate_missing_minutes":       lambda: self.generate_missing_minutes(
                    tool_input.get("meeting_numbers"),
                    bool(tool_input.get("force_regenerate", False)),
                    tool_input.get("output_language", "Auto-detect"),
                ),
                "get_speaker_contributions":      lambda: self.get_speaker_contributions(
                    tool_input["participant_name"],
                    tool_input.get("meeting_number"),
                ),
            }
            if tool_name not in dispatch:
                return f"Ferramenta desconhecida: '{tool_name}'"
            return dispatch[tool_name]()
        except Exception as exc:
            return f"Erro ao executar '{tool_name}': {exc}"
