# core/tools/tools_meeting_ops_calendar.py
# Auto-extracted from core/assistant_tools.py (split PC115) — mixin for AssistantToolExecutor.
# Methods here assume `self` is an AssistantToolExecutor instance (project_id, llm_config,
# _meeting_cache, _pending_charts, _palette — set in AssistantToolExecutor.__init__).

from __future__ import annotations
import re
from core.chart_config import CHART_PALETTES, DEFAULT_PALETTE
from core.tools._shared import _compute_initials


MEETING_OPS_CALENDAR_SCHEMAS: list[dict] = [
            {
                "type": "function",
                "function": {
                    "name": "show_meeting_transcript",
                    "description": (
                        "Exibe a transcrição de uma reunião no chat. "
                        "USE quando o usuário pedir para ver, ler ou exibir a transcrição de uma reunião específica. "
                        "Mostra a transcrição processada (pré-processada) e, se diferente, a original como opção secundária."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_number": {
                                "type": "integer",
                                "description": "Número da reunião cuja transcrição será exibida",
                            },
                        },
                        "required": ["meeting_number"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "compare_meeting_transcripts",
                    "description": (
                        "Compara as transcrições de 2 a 5 reuniões para detectar duplicatas ou conteúdos muito similares. "
                        "Retorna score de similaridade combinado (textual + Jaccard + razão de tamanho), veredicto "
                        "(DUPLICATA / MUITO SIMILAR / PARCIALMENTE SIMILAR / DISTINTOS) e trechos comuns como evidência. "
                        "USE quando o usuário perguntar se há duplicatas, reuniões repetidas ou conteúdo idêntico."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_numbers": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "minItems": 2,
                                "maxItems": 5,
                                "description": "Lista de 2 a 5 números de reunião a comparar. Ex: [1, 2] ou [3, 4, 5].",
                            },
                        },
                        "required": ["meeting_numbers"],
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
                    "name": "delete_project_artifacts",
                    "description": (
                        "Exclui TODOS os artefatos do projeto atual: reuniões, requisitos, BPMN, "
                        "Knowledge Graph, SBVR e documentos. O projeto (contexto) em si é mantido. "
                        "ATENÇÃO: operação IRREVERSÍVEL. "
                        "NUNCA chame sem confirmação explícita do usuário ('sim, limpe o projeto', etc.)."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "confirmed": {
                                "type": "boolean",
                                "description": (
                                    "Deve ser true SOMENTE após o usuário confirmar explicitamente. "
                                    "Padrão: false."
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
                    "name": "reprocess_meeting_requirements",
                    "description": (
                        "Re-executa o AgentRequirements sobre a transcrição armazenada de uma reunião "
                        "e salva os novos requisitos com source_quote (frase motivadora) e cited_by "
                        "(autor). Por padrão exclui os requisitos existentes antes de reinserir "
                        "(force_replace=true) para evitar duplicatas e recuperar a rastreabilidade. "
                        "Requer transcrição armazenada no Supabase."
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
                            "force_replace": {
                                "type": "boolean",
                                "description": (
                                    "Se true (padrão), exclui os requisitos existentes desta reunião "
                                    "antes de inserir os novos. Use false para adicionar sem remover."
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
                    "name": "batch_reprocess_requirements",
                    "description": (
                        "Reprocessa os requisitos de múltiplas reuniões em lote, extraindo "
                        "novamente com AgentRequirements e salvando source_quote (frase que motivou "
                        "o requisito) e cited_by (autor/iniciais). "
                        "Por padrão substitui os requisitos existentes (force_replace=true). "
                        "USE quando o usuário pedir para reprocessar requisitos de todas as reuniões, "
                        "recuperar autores/frases motivadoras, ou atualizar a rastreabilidade dos requisitos."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_numbers": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": (
                                    "Lista de números de reunião a processar. "
                                    "Omita para processar todas as reuniões com transcrição."
                                ),
                            },
                            "force_replace": {
                                "type": "boolean",
                                "description": (
                                    "Se true (padrão), exclui os requisitos existentes de cada "
                                    "reunião antes de reinserir. Use false para adicionar sem remover."
                                ),
                            },
                            "output_language": {
                                "type": "string",
                                "description": "Idioma dos requisitos extraídos. Padrão: 'Auto-detect'.",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calendar_diagnose",
                    "description": (
                        "Executa diagnóstico passo a passo da integração Google Calendar: "
                        "verifica carregamento de credenciais, formato da chave privada, "
                        "calendar ID, conectividade com a API e acesso à agenda. "
                        "USE quando houver erros de autenticação (invalid_grant, 403) ou "
                        "quando o usuário perguntar por que o calendário não está funcionando. "
                        "🔒 Requer perfil administrador."
                    ),
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calendar_list_events",
                    "description": (
                        "Lista os próximos eventos do Google Calendar do projeto. "
                        "Pode filtrar por período (time_min/time_max em ISO 8601) e por texto (query). "
                        "USE quando o usuário perguntar sobre reuniões agendadas, agenda, "
                        "próximos eventos ou compromissos do projeto."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "max_results": {
                                "type": "integer",
                                "description": "Número máximo de eventos a retornar (padrão 10, max 50)",
                            },
                            "time_min": {
                                "type": "string",
                                "description": "Início do período (ISO 8601, ex: '2026-05-01T00:00:00'). Padrão: agora.",
                            },
                            "time_max": {
                                "type": "string",
                                "description": "Fim do período (ISO 8601). Opcional.",
                            },
                            "query": {
                                "type": "string",
                                "description": "Filtro por texto livre no título ou descrição do evento. Opcional.",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calendar_get_event",
                    "description": (
                        "Retorna os detalhes completos de um evento do Google Calendar pelo seu ID. "
                        "USE quando o usuário quiser ver os detalhes de um evento específico. "
                        "O ID é obtido via calendar_list_events."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "event_id": {
                                "type": "string",
                                "description": "ID do evento (obtido via calendar_list_events)",
                            },
                        },
                        "required": ["event_id"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calendar_suggest_time",
                    "description": (
                        "Sugere horários livres para uma reunião consultando a API freebusy do Google Calendar. "
                        "USE quando o usuário quiser encontrar um horário disponível, verificar disponibilidade "
                        "ou planejar uma reunião de acompanhamento."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "duration_minutes": {
                                "type": "integer",
                                "description": "Duração necessária em minutos (padrão 60)",
                            },
                            "attendees": {
                                "type": "string",
                                "description": "E-mails dos participantes separados por vírgula (opcional)",
                            },
                            "time_min": {
                                "type": "string",
                                "description": "Início da janela de busca (ISO 8601). Padrão: agora.",
                            },
                            "time_max": {
                                "type": "string",
                                "description": "Fim da janela de busca (ISO 8601). Padrão: +7 dias.",
                            },
                            "max_suggestions": {
                                "type": "integer",
                                "description": "Número de sugestões a retornar (padrão 3)",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "calendar_create_event",
                    "description": (
                        "Cria um novo evento no Google Calendar do projeto. "
                        "USE quando o usuário pedir para agendar uma reunião, criar um evento ou "
                        "marcar um follow-up após análise de uma reunião do P2D. "
                        "Horários sem fuso horário são tratados como America/Sao_Paulo. "
                        "🔒 Requer perfil administrador."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "summary": {
                                "type": "string",
                                "description": "Título do evento",
                            },
                            "start_datetime": {
                                "type": "string",
                                "description": "Início — ISO 8601 (ex: '2026-05-20T14:00:00')",
                            },
                            "end_datetime": {
                                "type": "string",
                                "description": "Fim — ISO 8601 (ex: '2026-05-20T15:00:00')",
                            },
                            "description": {
                                "type": "string",
                                "description": "Descrição ou pauta do evento (opcional)",
                            },
                            "location": {
                                "type": "string",
                                "description": "Local ou link de videoconferência (opcional)",
                            },
                            "attendees": {
                                "type": "string",
                                "description": "E-mails dos participantes separados por vírgula (opcional)",
                            },
                        },
                        "required": ["summary", "start_datetime", "end_datetime"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_speaker_contributions",
                    "description": (
                        "Busca TODAS as contribuições de um participante: trechos de transcrição, "
                        "requisitos propostos (cited_by) e regras de negócio SBVR (source). "
                        "Aceita nome completo, primeiro nome ou iniciais — resolve automaticamente "
                        "o nome para iniciais (ex: 'Maria de Fátima' → 'MF'). "
                        "USE para: contribuições/papel/falas de alguém, o que X disse/propôs/defendeu, "
                        "requisitos ou regras propostos por X, participação de X em reuniões."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "participant_name": {
                                "type": "string",
                                "description": (
                                    "Nome do participante. Pode ser nome completo "
                                    "(ex: 'Maria de Fátima Duarte Miranda'), primeiro nome "
                                    "(ex: 'Maria') ou iniciais (ex: 'MFDM'). "
                                    "A ferramenta resolve automaticamente para iniciais."
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
            {
                "type": "function",
                "function": {
                    "name": "get_users_by_domain",
                    "description": "Lista todos os usuários cadastrados em um domínio específico (ex: 'fgv', 'gmail.com'). Responde perguntas como 'Quais são os usuários do domínio fgv?'",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "domain": {
                                "type": "string",
                                "description": "Nome do domínio (ex: 'fgv', 'fgv.br', 'gmail.com')"
                            }
                        },
                        "required": ["domain"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_all_domains",
                    "description": "Lista todos os domínios ou projetos cadastrados na solução, com contagem de usuários por domínio. Responde perguntas como 'Quais domínios estão cadastrados?' ou 'Quais são todos os projetos/domínios?'",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_users_by_project",
                    "description": "Lista todos os usuários agrupados por projeto cadastrado na solução. Responde perguntas como 'Liste todos os usuários por projeto'. Opcionalmente filtra por um projeto específico.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_id": {
                                "type": "string",
                                "description": "ID do projeto para filtrar (opcional). Se omitido, retorna todos os projetos."
                            }
                        },
                        "required": []
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "set_active_project",
                    "description": (
                        "Define o contexto de trabalho ativo para toda a aplicação. "
                        "Após a mudança, todas as páginas (Assistente, Artefatos, Editor BPMN, ROI-TR, ValidationHub) "
                        "passarão a usar o novo contexto automaticamente. "
                        "Use quando o usuário pedir para mudar, selecionar ou trocar o contexto de trabalho."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "project_name": {
                                "type": "string",
                                "description": "Nome do contexto (busca parcial sem distinção de maiúsculas/minúsculas). Ex: 'SDEA', 'saúde', 'proj'."
                            }
                        },
                        "required": ["project_name"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "rename_meeting",
                    "description": (
                        "Renomeia uma reunião — altera o título exibido em toda a aplicação. "
                        "USE quando o usuário pedir para renomear, alterar o nome ou corrigir o título de uma reunião. "
                        "O novo título é persistido imediatamente no banco de dados."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_number": {
                                "type": "integer",
                                "description": "Número da reunião a renomear (ex: 1, 2, 3...).",
                            },
                            "new_title": {
                                "type": "string",
                                "description": "Novo título da reunião. Máximo 200 caracteres.",
                            },
                        },
                        "required": ["meeting_number", "new_title"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "batch_rename_meetings",
                    "description": (
                        "Renomeia múltiplas reuniões de uma vez em lote. "
                        "USE quando detectar que vários títulos estão incorretos ou repetidos — "
                        "por exemplo, após comparar o campo 'title' com o conteúdo real das atas. "
                        "Chame get_meeting_list antes para obter os números e títulos atuais."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "renames": {
                                "type": "array",
                                "description": "Lista de renomeações a aplicar",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "meeting_number": {
                                            "type": "integer",
                                            "description": "Número da reunião",
                                        },
                                        "new_title": {
                                            "type": "string",
                                            "description": "Novo título (máximo 200 caracteres)",
                                        },
                                    },
                                    "required": ["meeting_number", "new_title"],
                                },
                                "minItems": 1,
                                "maxItems": 20,
                            },
                        },
                        "required": ["renames"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "save_context_skill",
                    "description": (
                        "Salva ou atualiza o Context Knowledge File (CKF) do contexto de trabalho ativo. "
                        "O CKF é injetado no prompt de todos os agentes (BPMN, Ata, SBVR, BMM) em cada execução do pipeline, "
                        "fornecendo conhecimento permanente sobre participantes, glossário, processos e regras de negócio. "
                        "Use quando o usuário pedir para salvar, atualizar ou documentar informações permanentes do contexto."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "skill_md": {
                                "type": "string",
                                "description": "Conteúdo Markdown do CKF. Pode incluir participantes, glossário, processos conhecidos, regras permanentes e objetivos estratégicos."
                            }
                        },
                        "required": ["skill_md"]
                    }
                }
            },
]

class _MeetingOpsCalendarToolsMixin:
    """Mixin: tools_meeting_ops_calendar tools."""

    def delete_project_artifacts(self, confirmed: bool = False) -> str:
        """Delete ALL artifacts from the current project, keeping the project (context) itself."""
        if not confirmed:
            return (
                "❌ Operação não confirmada. Esta ação exclui TODOS os artefatos do projeto "
                "(reuniões, requisitos, BPMN, Knowledge Graph, SBVR, documentos). "
                "O projeto em si é mantido. "
                "Para confirmar, diga: 'sim, limpe o projeto' ou 'confirme a limpeza'."
            )
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        pid = self.project_id
        deleted: list[str] = []
        errors:  list[str] = []

        def _del(table: str, col: str = "project_id") -> None:
            try:
                result = db.table(table).delete().eq(col, pid).execute()
                n = len(result.data or [])
                deleted.append(f"  • {n} registro(s) em `{table}`")
            except Exception as exc:
                errors.append(f"  • `{table}`: {exc}")

        # ── requirement_versions (FK para requirements AND meetings) ──────────
        try:
            req_ids = [
                r["id"] for r in
                (db.table("requirements").select("id").eq("project_id", pid).execute().data or [])
            ]
            if req_ids:
                for i in range(0, len(req_ids), 200):
                    db.table("requirement_versions").delete().in_("requirement_id", req_ids[i:i+200]).execute()
                deleted.append(f"  • versões de {len(req_ids)} requisito(s) em `requirement_versions`")
        except Exception as exc:
            errors.append(f"  • `requirement_versions`: {exc}")

        # ── bpmn_versions (FK para bpmn_processes — deve vir antes) ──────────
        _del("bpmn_versions")

        # ── bpmn_processes ────────────────────────────────────────────────────
        _del("bpmn_processes")

        # ── requirements ──────────────────────────────────────────────────────
        _del("requirements")

        # ── sbvr_rules, sbvr_terms ────────────────────────────────────────────
        _del("sbvr_rules")
        _del("sbvr_terms")

        # ── Knowledge Graph ───────────────────────────────────────────────────
        _del("kh_facts")
        _del("kh_entities")

        # ── Documents (project_id é TEXT nesta tabela) ────────────────────────
        try:
            result = db.table("meeting_documents").delete().eq("project_id", pid).execute()
            n = len(result.data or [])
            deleted.append(f"  • {n} registro(s) em `meeting_documents`")
        except Exception as exc:
            errors.append(f"  • `meeting_documents`: {exc}")

        # ── Meetings (CASCADE deletes: transcript_chunks, dmn_models, etc.) ───
        _del("meetings")

        self._meeting_cache = None

        lines = ["✅ Limpeza do projeto concluída. O projeto em si foi mantido.\n", "Artefatos excluídos:"]
        lines += deleted if deleted else ["  (nenhum artefato encontrado)"]
        if errors:
            lines += ["", "⚠️  Erros parciais (verifique):"] + errors
        return "\n".join(lines)

    def reprocess_meeting_requirements(
        self,
        meeting_number: int,
        output_language: str = "Auto-detect",
        force_replace: bool = True,
    ) -> str:
        """Re-run AgentRequirements on a stored transcript and save new requirements.

        force_replace=True (padrão): exclui os requisitos existentes desta reunião
        antes de inserir os novos — garante que source_quote e cited_by sejam
        salvos sem gerar duplicatas.
        """
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
            from modules.supabase_client import get_supabase_client
            from core.knowledge_hub import KnowledgeHub
            from agents.agent_requirements import AgentRequirements
            from core.project_store import save_requirements_from_hub

            db = get_supabase_client()

            # ── Step 1: delete existing requirements ─────────────────────────
            deleted   = 0
            del_error = ""
            if force_replace and db and mid:
                try:
                    existing = (
                        db.table("requirements").select("id")
                        .eq("project_id", self.project_id)
                        .eq("first_meeting_id", mid)
                        .execute().data or []
                    )
                    deleted = len(existing)
                    if deleted:
                        db.table("requirements").delete() \
                            .eq("project_id", self.project_id) \
                            .eq("first_meeting_id", mid).execute()
                except Exception as exc:
                    del_error = str(exc)[:200]

            # ── Step 2: re-extract ────────────────────────────────────────────
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

            # ── Step 3: save ──────────────────────────────────────────────────
            n_reqs = len(hub.requirements.requirements)
            saved  = save_requirements_from_hub(mid, self.project_id, hub)

            lines = [
                "══════════════════════════════════════════════",
                f"  Reunião {meeting_number} — '{title}'",
                "══════════════════════════════════════════════",
            ]
            if del_error:
                lines.append(f"  ⚠️ Erro ao excluir anteriores: {del_error}")
            elif deleted:
                lines.append(f"  Requisitos excluídos    : {deleted}")
            lines += [
                f"  Requisitos extraídos    : {n_reqs}",
                f"  Requisitos salvos       : {saved}",
            ]
            if saved == 0 and n_reqs > 0:
                lines += [
                    "  ❌ Nenhum salvo — execute a migration SQL:",
                    "     ALTER TABLE requirements",
                    "       ADD COLUMN IF NOT EXISTS source_quote TEXT,",
                    "       ADD COLUMN IF NOT EXISTS cited_by TEXT;",
                ]
            else:
                lines.append(
                    "  ✅ source_quote e cited_by incluídos."
                )
            return "\n".join(lines)

        except Exception as exc:
            return f"❌ Erro ao reprocessar Reunião {meeting_number}: {exc}"

    def batch_reprocess_requirements(
        self,
        meeting_numbers: list[int] | None = None,
        force_replace: bool = True,
        output_language: str = "Auto-detect",
    ) -> str:
        """Reprocess AgentRequirements for multiple meetings (batch version).

        Mirrors generate_missing_minutes but for requirements.
        force_replace=True (padrão): exclui os requisitos existentes de cada
        reunião antes de reinserir — necessário para recuperar source_quote/cited_by.
        """
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
            all_meetings = (
                db.table("meetings")
                .select("id, meeting_number, title, transcript_clean, transcript_raw")
                .eq("project_id", self.project_id)
                .order("meeting_number")
                .execute().data or []
            )
        except Exception as exc:
            return f"❌ Erro ao listar reuniões: {exc}"

        candidates = []
        for m in all_meetings:
            n          = m.get("meeting_number")
            transcript = m.get("transcript_clean") or m.get("transcript_raw") or ""
            if not transcript.strip():
                continue
            if meeting_numbers is not None and n not in meeting_numbers:
                continue
            candidates.append(m)

        if not candidates:
            return (
                "Nenhuma reunião elegível encontrada.\n"
                "Verifique se as reuniões possuem transcrição armazenada."
            )

        from core.knowledge_hub import KnowledgeHub
        from agents.agent_requirements import AgentRequirements
        from core.project_store import save_requirements_from_hub

        provider_cfg = self.llm_config.get("provider_cfg", {})
        client_info  = {"api_key": self.llm_config.get("api_key", "")}

        successes: list[str] = []
        failures:  list[str] = []

        total_extracted = 0
        total_saved     = 0
        total_deleted   = 0

        for m in candidates:
            mid        = m.get("id", "")
            n          = m.get("meeting_number", "?")
            title      = m.get("title") or f"Reunião {n}"
            transcript = m.get("transcript_clean") or m.get("transcript_raw") or ""

            try:
                # ── Step 1: delete existing requirements for this meeting ──────
                deleted   = 0
                del_error = ""
                if force_replace and mid:
                    try:
                        existing = (
                            db.table("requirements").select("id")
                            .eq("project_id", self.project_id)
                            .eq("first_meeting_id", mid)
                            .execute().data or []
                        )
                        deleted = len(existing)
                        if deleted:
                            db.table("requirements").delete() \
                                .eq("project_id", self.project_id) \
                                .eq("first_meeting_id", mid).execute()
                    except Exception as exc:
                        del_error = str(exc)[:120]

                # ── Step 2: run AgentRequirements ─────────────────────────────
                hub = KnowledgeHub.new()
                hub.transcript_clean = transcript
                hub.transcript_raw   = transcript

                agent = AgentRequirements(client_info, provider_cfg)
                hub   = agent.run(hub, output_language=output_language)

                if not hub.requirements.ready:
                    failures.append(
                        f"  • Reunião {n} — '{title}': "
                        "AgentRequirements não retornou resultado."
                    )
                    continue

                n_extracted  = len(hub.requirements.requirements)
                total_extracted += n_extracted

                # ── Step 3: save new requirements ─────────────────────────────
                saved = save_requirements_from_hub(mid, self.project_id, hub)
                total_saved   += saved
                total_deleted += deleted

                status_parts = [f"{saved}/{n_extracted} salvo(s)"]
                if deleted:
                    status_parts.append(f"{deleted} anterior(es) excluído(s)")
                if del_error:
                    status_parts.append(f"⚠️ erro ao excluir: {del_error}")
                if saved == 0 and n_extracted > 0:
                    status_parts.append("❌ nenhum salvo — verifique a migration SQL")

                successes.append(
                    f"  • Reunião {n} — '{title}': {', '.join(status_parts)}"
                )

            except Exception as exc:
                failures.append(f"  • Reunião {n} — '{title}': {exc}")

        lines = [
            "══════════════════════════════════════════════",
            "  Reprocessamento de Requisitos — Resultado",
            "══════════════════════════════════════════════",
            f"  Reuniões processadas : {len(successes)}",
            f"  Reuniões com falha   : {len(failures)}",
            f"  Requisitos extraídos : {total_extracted}",
            f"  Requisitos salvos    : {total_saved}",
            f"  Requisitos excluídos : {total_deleted}",
            "══════════════════════════════════════════════",
            "",
        ]
        if successes:
            lines.append("Detalhes por reunião:")
            lines.extend(successes)
        if failures:
            lines.append(f"\n❌ Falhas ({len(failures)}):")
            lines.extend(failures)
        if total_saved > 0:
            lines.append(
                "\n✅ Requisitos salvos com source_quote (frase motivadora) "
                "e cited_by (autor)."
            )
        elif total_extracted > 0 and total_saved == 0:
            lines.append(
                "\n⚠️ Requisitos foram extraídos mas não salvos.\n"
                "Execute a migration SQL em Configurações → Banco de Dados:\n"
                "  ALTER TABLE requirements "
                "ADD COLUMN IF NOT EXISTS source_quote TEXT, "
                "ADD COLUMN IF NOT EXISTS cited_by TEXT;\n"
                "  ALTER TABLE requirement_versions "
                "ADD COLUMN IF NOT EXISTS source_quote TEXT, "
                "ADD COLUMN IF NOT EXISTS cited_by TEXT;"
            )
        return "\n".join(lines)

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

        # Build list of search terms: full name + computed initials + first name
        search_terms = self._resolve_search_terms(db, participant_name)

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

        # ── 1. Search transcript_chunks (all search terms) ────────────────────
        chunks_by_meeting: dict[int, list[str]] = {}
        mids_with_chunks:  set[str]             = set()

        raw_chunks: list[dict] = []
        seen_chunk_keys: set[tuple] = set()
        for term in search_terms:
            try:
                rows = (
                    db.table("transcript_chunks")
                    .select("meeting_id, chunk_index, chunk_text")
                    .eq("project_id", self.project_id)
                    .ilike("chunk_text", f"%{term}%")
                    .order("meeting_id")
                    .order("chunk_index")
                    .execute().data or []
                )
                for row in rows:
                    key = (row.get("meeting_id"), row.get("chunk_index"))
                    if key not in seen_chunk_keys:
                        seen_chunk_keys.add(key)
                        raw_chunks.append(row)
            except Exception:
                pass


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
            passages: list[str] = []
            seen_positions: set[int] = set()
            for term in search_terms:
                text = transcript
                idx  = 0
                while len(passages) < 12:
                    pos = text.lower().find(term.lower(), idx)
                    if pos == -1:
                        break
                    # Avoid overlapping passages from different terms
                    if not any(abs(pos - p) < 300 for p in seen_positions):
                        start   = max(0, pos - 200)
                        end     = min(len(text), pos + 400)
                        snippet = text[start:end].strip()
                        if start > 0:
                            snippet = "…" + snippet
                        if end < len(text):
                            snippet += "…"
                        passages.append(snippet)
                        seen_positions.add(pos)
                    idx = pos + len(term)
            if passages:
                chunks_by_meeting[n] = passages

        # ── 3. Requirements with cited_by matching any search term ───────────
        reqs_by_meeting: dict[int, list[str]] = {}
        seen_req_ids: set = set()
        for term in search_terms:
            try:
                req_rows = (
                    db.table("requirements")
                    .select("req_number, title, cited_by, first_meeting_id")
                    .eq("project_id", self.project_id)
                    .ilike("cited_by", f"%{term}%")
                    .execute().data or []
                )
                for r in req_rows:
                    rn = r.get("req_number")
                    if rn in seen_req_ids:
                        continue
                    seen_req_ids.add(rn)
                    mid = r.get("first_meeting_id")
                    n   = mid_to_num.get(mid) if mid else None
                    if meeting_number is not None and n != meeting_number:
                        continue
                    key = n or 0
                    if key not in reqs_by_meeting:
                        reqs_by_meeting[key] = []
                    req_id = f"REQ-{rn:03d}" if isinstance(rn, int) else "REQ-???"
                    cited  = r.get("cited_by") or ""
                    reqs_by_meeting[key].append(
                        f"  {req_id}: {r.get('title', '')}  [citado por: {cited}]"
                    )
            except Exception:
                pass

        # ── 4. SBVR rules with source matching any search term ────────────────
        sbvr_by_meeting: dict[int, list[str]] = {}
        seen_rule_ids: set = set()
        for term in search_terms:
            try:
                rule_rows = (
                    db.table("sbvr_rules")
                    .select("rule_id, statement, source, meeting_id")
                    .eq("project_id", self.project_id)
                    .ilike("source", f"%{term}%")
                    .execute().data or []
                )
                for r in rule_rows:
                    rid = r.get("rule_id")
                    if rid in seen_rule_ids:
                        continue
                    seen_rule_ids.add(rid)
                    mid = r.get("meeting_id")
                    n   = mid_to_num.get(mid) if mid else None
                    if meeting_number is not None and n != meeting_number:
                        continue
                    key = n or 0
                    if key not in sbvr_by_meeting:
                        sbvr_by_meeting[key] = []
                    statement = r.get("statement") or ""
                    source    = r.get("source") or ""
                    display   = statement[:120] + ("…" if len(statement) > 120 else "")
                    sbvr_by_meeting[key].append(
                        f"  {rid}: {display}  [fonte: {source}]"
                    )
            except Exception:
                pass

        # ── 5. Format output ──────────────────────────────────────────────────
        all_meeting_nums = sorted(
            set(list(chunks_by_meeting.keys())
                + list(reqs_by_meeting.keys())
                + list(sbvr_by_meeting.keys()))
        )
        if not all_meeting_nums:
            scope_str = f" na Reunião {meeting_number}" if meeting_number else " no projeto"
            terms_str = " / ".join(search_terms)
            return (
                f"Nenhuma contribuição encontrada para '{terms_str}'{scope_str}.\n"
                "Dica: verifique a grafia do nome como aparece nas transcrições ou atas."
            )

        terms_display = search_terms[0]
        if len(search_terms) > 1:
            terms_display += f" (iniciais: {', '.join(search_terms[1:])})"

        lines = [
            f"=== Contribuições de '{terms_display}' ===",
            "",
        ]

        total_chunks = 0
        total_reqs   = 0
        total_sbvr   = 0

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
                lines.append(f"  Requisitos propostos ({len(meeting_reqs)}):")
                lines.extend(meeting_reqs[:8])
                if len(meeting_reqs) > 8:
                    lines.append(f"  … e mais {len(meeting_reqs) - 8} requisito(s)")

            meeting_sbvr = sbvr_by_meeting.get(n, [])
            total_sbvr  += len(meeting_sbvr)
            if meeting_sbvr:
                lines.append(f"  Regras de negócio propostas ({len(meeting_sbvr)}):")
                lines.extend(meeting_sbvr[:8])
                if len(meeting_sbvr) > 8:
                    lines.append(f"  … e mais {len(meeting_sbvr) - 8} regra(s)")

            lines.append("")

        lines.append(
            f"Resumo: {total_chunks} trecho(s) de transcrição + "
            f"{total_reqs} requisito(s) + {total_sbvr} regra(s) SBVR em "
            f"{len(all_meeting_nums)} reunião(ões)."
        )
        return "\n".join(lines)

    def get_users_by_domain(self, domain: str) -> str:
        """Lista usuários cujo login contém o domínio informado."""
        domain = domain.strip().lstrip("@")
        from core import project_store
        users = project_store.list_users_by_domain(domain)
        if not users:
            return f"Nenhum usuário encontrado para o domínio '{domain}'."
        lines = [f"**Usuários do domínio `{domain}`** ({len(users)} encontrados):\n"]
        for u in users:
            role_badge = f" `{u.get('role', 'user')}`"
            nome = u.get("display_name") or u.get("login", "?")
            lines.append(f"- **{nome}** ({u.get('login', '')}){role_badge}")
        return "\n".join(lines)

    def list_all_domains_tool(self) -> str:
        """Lista todos os domínios distintos extraídos dos logins cadastrados."""
        from core import project_store
        domains = project_store.list_all_domains()
        if not domains:
            return "Nenhum domínio encontrado."
        lines = ["**Domínios cadastrados na solução:**\n"]
        for d in domains:
            lines.append(f"- `{d['domain']}` — {d['user_count']} usuário(s)")
        return "\n".join(lines)

    def list_users_by_project_tool(self, project_id: str | None = None) -> str:
        """Lista usuários agrupados por projeto."""
        from core import project_store
        data = project_store.list_users_by_project(project_id)
        if not data:
            return "Nenhum dado encontrado."
        lines = ["**Usuários por projeto:**\n"]
        for proj in data:
            count = proj["user_count"]
            lines.append(f"\n### 📁 {proj['project_name']} ({count} usuário(s))")
            for u in proj.get("users", []):
                lines.append(
                    f"- {u.get('nome', u.get('login', '?'))} "
                    f"({u.get('login', '')}) `{u.get('role', 'user')}`"
                )
        return "\n".join(lines)

    def show_meeting_transcript(self, meeting_number: int) -> str:
        """Exibe a transcrição de uma reunião no chat via _pending_widgets."""
        import streamlit as st
        m = self._find_meeting(meeting_number)
        if not m:
            return f"❌ Reunião {meeting_number} não encontrada no projeto."
        clean = (m.get("transcript_clean") or "").strip()
        raw   = (m.get("transcript_raw")   or "").strip()
        text  = clean or raw
        if not text:
            return (
                f"❌ Reunião {meeting_number} — transcrição não disponível no banco. "
                "A transcrição pode não ter sido salva para esta reunião."
            )
        title = m.get("title") or f"Reunião {meeting_number}"
        date  = (m.get("meeting_date") or "")[:10]
        label = f"Reunião {meeting_number} — {title}" + (f" ({date})" if date else "")
        wc = len(text.split())
        cc = len(text)
        version = "processada" if clean else "original"
        widget_title = f"📜 Transcrição {version} — {label}"
        st.session_state.setdefault("_pending_widgets", []).append({
            "type":       "transcript",
            "title":      widget_title,
            "content":    text,
            "word_count": wc,
            "char_count": cc,
        })
        return f"📜 Transcrição da {label} exibida abaixo ({wc:,} palavras · {cc:,} caracteres)."

    def compare_meeting_transcripts(self, meeting_numbers: list) -> str:
        """Compare transcripts from multiple meetings to detect duplicates."""
        import difflib

        meeting_numbers = list(dict.fromkeys(int(n) for n in meeting_numbers))  # dedupe, preserve order
        if len(meeting_numbers) < 2:
            return "Forneça pelo menos 2 números de reunião distintos para comparar."
        if len(meeting_numbers) > 5:
            return "Máximo de 5 reuniões por comparação."

        # Load data
        _PT_STOP = {
            "a","o","e","de","da","do","que","em","um","uma","para","com","não",
            "se","por","mais","como","mas","ao","dos","das","foi","ser","são",
            "essa","esse","isso","ele","ela","eles","elas","eu","você","nós",
            "na","no","nos","nas","pelo","pela","pelos","pelas","já","também",
        }
        meetings_data = []
        for num in meeting_numbers:
            m = self._find_meeting(num)
            if not m:
                return f"❌ Reunião {num} não encontrada no contexto atual."
            transcript = (m.get("transcript_clean") or m.get("transcript_raw") or "").strip()
            meetings_data.append({
                "number": num,
                "title":  m.get("title") or f"Reunião {num}",
                "date":   (m.get("meeting_date") or "")[:10],
                "transcript": transcript,
                "length": len(transcript),
            })

        lines = [f"## 🔍 Comparação de Transcrições — {len(meetings_data)} reuniões\n"]

        pair_sections = []
        for i in range(len(meetings_data)):
            for j in range(i + 1, len(meetings_data)):
                a, b = meetings_data[i], meetings_data[j]
                t_a, t_b = a["transcript"], b["transcript"]

                if not t_a or not t_b:
                    missing = a["number"] if not t_a else b["number"]
                    pair_sections.append(
                        f"### R{a['number']} ↔ R{b['number']}\n"
                        f"⚠️ Reunião {missing} não possui transcrição salva no banco."
                    )
                    continue

                # ── Métricas ─────────────────────────────────────────────────
                # 1. Similaridade textual (amostra de até 12k chars para performance)
                sample_a = t_a[:12_000]
                sample_b = t_b[:12_000]
                char_sim = difflib.SequenceMatcher(None, sample_a, sample_b).ratio()

                # 2. Jaccard sobre palavras significativas (len>3, fora de stop words)
                words_a = {w for w in t_a.lower().split() if len(w) > 3 and w not in _PT_STOP}
                words_b = {w for w in t_b.lower().split() if len(w) > 3 and w not in _PT_STOP}
                union   = words_a | words_b
                jaccard = len(words_a & words_b) / len(union) if union else 0.0

                # 3. Razão de comprimento
                len_ratio = (
                    min(a["length"], b["length"]) / max(a["length"], b["length"])
                    if max(a["length"], b["length"]) > 0 else 0.0
                )

                # Score combinado
                score = (char_sim * 0.50 + jaccard * 0.35 + len_ratio * 0.15) * 100

                # ── Veredicto ────────────────────────────────────────────────
                if score >= 80:
                    verdict = "🔴 **DUPLICATA PROVÁVEL**"
                    rec = "Considere excluir a duplicata ou mesclar com `mesclar_reunioes`."
                elif score >= 60:
                    verdict = "🟠 **MUITO SIMILAR** (possível duplicata parcial)"
                    rec = "Investigue manualmente — podem ser partes da mesma sessão ou reprocessamento."
                elif score >= 35:
                    verdict = "🟡 **PARCIALMENTE SIMILAR**"
                    rec = "Tópicos em comum mas conteúdos distintos — provavelmente reuniões diferentes."
                else:
                    verdict = "🟢 **CONTEÚDOS DISTINTOS**"
                    rec = "Não são duplicatas."

                # ── Evidência: maiores blocos em comum ───────────────────────
                matcher = difflib.SequenceMatcher(None, t_a, t_b, autojunk=False)
                evidence = []
                for blk in sorted(matcher.get_matching_blocks(), key=lambda x: x.size, reverse=True)[:4]:
                    if blk.size < 80:
                        break
                    snippet = " ".join(t_a[blk.a : blk.a + blk.size].split())[:130]
                    if len(snippet) >= 40:
                        evidence.append(f'  > *"…{snippet}…"*')

                sec = [
                    f"### R{a['number']} «{a['title']}» ({a['date']}) ↔ "
                    f"R{b['number']} «{b['title']}» ({b['date']})",
                    f"**Veredicto:** {verdict}",
                    "",
                    "| Métrica | Valor |",
                    "|---|---|",
                    f"| **Score combinado** | **{score:.1f}%** |",
                    f"| Similaridade textual (char) | {char_sim*100:.1f}% |",
                    f"| Jaccard palavras-chave | {jaccard*100:.1f}% |",
                    f"| Razão de comprimento | {len_ratio*100:.0f}% "
                    f"({a['length']:,} vs {b['length']:,} chars) |",
                    "",
                ]
                if evidence:
                    sec.append("**Trechos idênticos encontrados:**")
                    sec.extend(evidence)
                    sec.append("")
                sec.append(f"💡 *{rec}*")
                pair_sections.append("\n".join(sec))

        lines.extend(pair_sections)
        return "\n\n---\n\n".join(lines)

    def rename_meeting(self, meeting_number: int, new_title: str) -> str:
        """Renomeia uma reunião no banco de dados."""
        m = self._find_meeting(meeting_number)
        if not m:
            return f"Reunião {meeting_number} não encontrada no contexto atual."
        new_title = new_title.strip()[:200]
        if not new_title:
            return "O novo título não pode ser vazio."
        old_title = m.get("title") or ""
        if new_title == old_title:
            return f"O título da Reunião {meeting_number} já é «{old_title}» — nenhuma alteração necessária."
        from core.project_store import update_meeting_title
        ok = update_meeting_title(m["id"], new_title)
        if not ok:
            return f"❌ Falha ao renomear a Reunião {meeting_number} no banco de dados."
        # Invalidate meeting cache so the next call reflects the new title
        self._meeting_cache = None
        return (
            f"✅ Reunião {meeting_number} renomeada com sucesso.\n"
            f"- **Título anterior:** {old_title}\n"
            f"- **Novo título:** {new_title}"
        )

    def batch_rename_meetings(self, renames: list) -> str:
        """Renomeia múltiplas reuniões em lote."""
        if not renames:
            return "❌ Lista de renomeações vazia."
        from core.project_store import update_meeting_title
        results = []
        for item in renames:
            num = int(item.get("meeting_number", 0))
            new_title = str(item.get("new_title", "")).strip()[:200]
            if not new_title:
                results.append(f"- Reunião {num}: ❌ título vazio — ignorado")
                continue
            m = self._find_meeting(num)
            if not m:
                results.append(f"- Reunião {num}: ❌ não encontrada")
                continue
            old_title = m.get("title") or f"Reunião {num}"
            if new_title == old_title:
                results.append(f"- Reunião {num}: ℹ️ título já correto — «{old_title}»")
                continue
            ok = update_meeting_title(m["id"], new_title)
            if ok:
                results.append(f"- Reunião {num}: ✅ «{old_title}» → «{new_title}»")
            else:
                results.append(f"- Reunião {num}: ❌ falha ao atualizar no banco")
        self._meeting_cache = None
        ok_count = sum(1 for r in results if "✅" in r)
        return f"**Renomeação em lote — {ok_count}/{len(renames)} sucesso(s):**\n" + "\n".join(results)

    def set_active_project(self, project_name: str) -> str:
        """Define o contexto de trabalho ativo para toda a aplicação."""
        import streamlit as st
        from core.project_store import list_contexts
        projects = list_contexts()
        if not projects:
            return "Nenhum contexto disponível no banco de dados."
        name_lower = project_name.lower().strip()
        project = next((p for p in projects if p["name"].lower() == name_lower), None)
        if not project:
            project = next((p for p in projects if name_lower in p["name"].lower()), None)
        if not project:
            names = ", ".join(p["name"] for p in projects)
            return (
                f"Contexto não encontrado: '{project_name}'. "
                f"Contextos disponíveis: {names}"
            )
        st.session_state["active_project_id"]   = project["id"]
        st.session_state["active_project_name"] = project["name"]
        if project.get("sigla"):
            st.session_state["prefix"] = project["sigla"].strip() + "_"
        return (
            f"Contexto de trabalho alterado para **{project['name']}**. "
            "Todas as páginas agora usarão este contexto."
        )

    def save_context_skill(self, skill_md: str) -> str:
        """Salva o Context Knowledge File (CKF) do contexto de trabalho ativo."""
        import streamlit as st
        ctx_id = st.session_state.get("active_project_id")
        if not ctx_id:
            return "Nenhum contexto ativo. Selecione um contexto na Home primeiro."
        ctx_name = st.session_state.get("active_project_name", ctx_id)
        try:
            from core.project_store import save_context_skill as _save
            ok = _save(ctx_id, skill_md.strip())
            if ok:
                return (
                    f"✅ Context Knowledge File salvo para **{ctx_name}**. "
                    "Será injetado automaticamente no próximo pipeline."
                )
            return "❌ Erro ao salvar o CKF no Supabase. Verifique a coluna `skill_md` na tabela `contexts`."
        except Exception as exc:
            return f"❌ Erro: {exc}"

    def calendar_diagnose(self) -> str:
        from modules.calendar_client import diagnose_calendar
        return diagnose_calendar()

    def calendar_list_events(
        self,
        max_results: int = 10,
        time_min: str | None = None,
        time_max: str | None = None,
        query: str | None = None,
        project_id: str | None = None,
    ) -> str:
        from modules.calendar_client import list_events, calendar_configured
        if not calendar_configured():
            return (
                "⚙️ Google Calendar não configurado neste ambiente. "
                "Configure st.secrets[google_calendar] para habilitar esta funcionalidade."
            )
        return list_events(
            max_results=max_results,
            time_min=time_min,
            time_max=time_max,
            query=query,
            project_id=project_id,
        )

    def calendar_get_event(self, event_id: str, project_id: str | None = None) -> str:
        from modules.calendar_client import get_event, calendar_configured
        if not calendar_configured():
            return "⚙️ Google Calendar não configurado neste ambiente."
        return get_event(event_id, project_id=project_id)

    def calendar_suggest_time(
        self,
        duration_minutes: int = 60,
        attendees: str | None = None,
        time_min: str | None = None,
        time_max: str | None = None,
        max_suggestions: int = 3,
        project_id: str | None = None,
    ) -> str:
        from modules.calendar_client import suggest_time, calendar_configured
        if not calendar_configured():
            return "⚙️ Google Calendar não configurado neste ambiente."
        return suggest_time(
            duration_minutes=duration_minutes,
            attendees=attendees,
            time_min=time_min,
            time_max=time_max,
            max_suggestions=max_suggestions,
            project_id=project_id,
        )

    def calendar_create_event(
        self,
        summary: str,
        start_datetime: str,
        end_datetime: str,
        description: str | None = None,
        location: str | None = None,
        attendees: str | None = None,
        project_id: str | None = None,
    ) -> str:
        from modules.calendar_client import create_event, calendar_configured
        if not calendar_configured():
            return "⚙️ Google Calendar não configurado neste ambiente."
        return create_event(
            summary=summary,
            start_datetime=start_datetime,
            end_datetime=end_datetime,
            description=description,
            location=location,
            attendees=attendees,
            project_id=project_id,
        )
