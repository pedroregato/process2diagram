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
from core.chart_config import CHART_PALETTES, DEFAULT_PALETTE

# Preposições PT ignoradas ao calcular iniciais de nomes próprios
_PT_NAME_PREPS = {"de", "da", "do", "dos", "das", "e", "a", "o", "em"}


def _compute_initials(name: str) -> str:
    """'Maria de Fátima Duarte Miranda' → 'MFDM' (ignora preposições PT)."""
    return "".join(
        p[0].upper()
        for p in name.strip().split()
        if p.lower() not in _PT_NAME_PREPS and p
    )

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
                "name": "count_artifacts",
                "description": (
                    "OBRIGATÓRIO para qualquer pergunta de contagem — faz SELECT COUNT(*) no banco. "
                    "Use esta ferramenta (e não get_requirements) quando o usuário perguntar: "
                    "'quantos requisitos?', 'quantas regras?', 'quantos processos BPMN?', "
                    "'quantas reuniões?', 'quantos termos SBVR?', 'quantos fatos no Knowledge Hub?'. "
                    "Resposta exata e instantânea. artifact_type='all' retorna painel completo."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "artifact_type": {
                            "type": "string",
                            "description": (
                                "Tipo de artefato: all | requirements | sbvr_terms | sbvr_rules | "
                                "bpmn_processes | bpmn_versions | meetings | kh_facts | "
                                "kh_entities | kh_contradictions. "
                                "Padrão 'all' retorna todos de uma vez."
                            ),
                        },
                        "req_type": {
                            "type": "string",
                            "description": (
                                "Filtra requisitos por tipo (só usado quando artifact_type='requirements'): "
                                "funcional | não-funcional | regra de negócio | restrição | interface"
                            ),
                        },
                        "status": {
                            "type": "string",
                            "description": (
                                "Filtra por status — para requisitos: active|revised|contradicted|confirmed; "
                                "para contradições: open|resolved|false_positive."
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
                "name": "get_requirements",
                "description": (
                    "Lista o CONTEÚDO dos requisitos (título, descrição, status, prioridade) com paginação. "
                    "NÃO use para contar — use count_artifacts para qualquer pergunta de quantidade. "
                    "Use esta ferramenta apenas quando o usuário pedir para VER ou DETALHAR requisitos."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "keyword": {
                            "type": "string",
                            "description": (
                                "Palavra-chave para buscar no título, descrição ou número do requisito "
                                "(ex: 'REQ-229', '229', 'autenticação')."
                            ),
                        },
                        "req_type": {
                            "type": "string",
                            "description": "Tipo: funcional | não-funcional | regra de negócio | restrição | interface",
                        },
                        "status": {
                            "type": "string",
                            "description": "Status: active | revised | contradicted | confirmed",
                        },
                        "page": {
                            "type": "integer",
                            "description": (
                                "Página a retornar (começa em 1). "
                                "Se o total superar page_size, chame novamente com page=2, 3… "
                                "para obter todos os registros."
                            ),
                        },
                        "page_size": {
                            "type": "integer",
                            "description": "Itens por página (padrão 50, máximo 100).",
                        },
                        "meeting_number": {
                            "type": "integer",
                            "description": (
                                "Filtra requisitos pela reunião de origem (first_meeting_id). "
                                "Use quando o usuário pedir 'requisitos da Reunião N' ou "
                                "'o que foi levantado na Reunião N'."
                            ),
                        },
                        "count_only": {
                            "type": "boolean",
                            "description": (
                                "Legado — prefira count_artifacts. "
                                "Se true, retorna apenas o total sem buscar dados."
                            ),
                        },
                    },
                    "required": [],
                },
            },
        },
        # ── Histórico de requisitos ───────────────────────────────────────────
        {
            "type": "function",
            "function": {
                "name": "get_requirement_history",
                "description": (
                    "Retorna o histórico completo de versões de um requisito específico, "
                    "mostrando como ele evoluiu entre reuniões: mudanças de título, descrição, "
                    "prioridade, tipo, e flags de contradição. "
                    "Use quando o usuário perguntar: 'O que mudou no REQ-042?', "
                    "'Como evoluiu o requisito X entre reuniões?', "
                    "'Algum requisito teve prioridade alterada?', "
                    "'Mostre o histórico de versões do requisito Y'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "req_number": {
                            "type": "string",
                            "description": (
                                "Número do requisito no formato REQ-NNN "
                                "(ex: 'REQ-042', 'REQ-001')"
                            ),
                        },
                    },
                    "required": ["req_number"],
                },
            },
        },
        # ── BMM / CKF ─────────────────────────────────────────────────────────
        {
            "type": "function",
            "function": {
                "name": "get_bmm",
                "description": (
                    "Retorna o Modelo de Motivação do Negócio (BMM) extraído das reuniões: "
                    "visão, missão, objetivos, estratégias e políticas. "
                    "Use quando o usuário perguntar: 'Qual é a visão do projeto?', "
                    "'Quais objetivos estratégicos foram identificados?', "
                    "'Mostre a missão e as políticas de negócio', "
                    "'O que o BMM extraiu da reunião X?'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_number": {
                            "type": "integer",
                            "description": "Filtrar por reunião específica (opcional — omitir retorna o BMM mais recente)",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_ckf",
                "description": (
                    "Retorna o Context Knowledge File (CKF) do projeto — um documento "
                    "Markdown que acumula os insights essenciais de todas as reuniões: "
                    "terminologia do domínio, decisões-chave, participantes, regras de negócio. "
                    "Use quando o usuário perguntar: 'Quais são os fatores críticos de conhecimento?', "
                    "'Qual é o contexto acumulado do projeto?', "
                    "'Mostre o resumo de tudo que já foi aprendido nas reuniões', "
                    "'O que o sistema sabe sobre o projeto até agora?'."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        # ── Knowledge Graph ───────────────────────────────────────────────────
        {
            "type": "function",
            "function": {
                "name": "list_kh_entities",
                "description": (
                    "Lista entidades do Grafo de Conhecimento do projeto: "
                    "pessoas, sistemas, organizações, processos, conceitos. "
                    "Use quando o usuário perguntar: 'Quais entidades estão no grafo?', "
                    "'Liste os sistemas mencionados nas reuniões', "
                    "'Quais organizações aparecem no projeto?', "
                    "'Quais entidades foram mencionadas mais vezes?'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_type": {
                            "type": "string",
                            "enum": ["person", "system", "organization", "process", "concept", "other"],
                            "description": "Filtrar por tipo de entidade (opcional)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Máximo de entidades a retornar (padrão 50, máximo 100)",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_kh_contradictions",
                "description": (
                    "Lista as contradições detectadas pelo Grafo de Conhecimento entre reuniões: "
                    "fatos conflitantes, responsabilidades disputadas, decisões revertidas. "
                    "Use quando o usuário perguntar: 'Quais contradições foram detectadas?', "
                    "'Há conflitos entre reuniões?', "
                    "'Mostre inconsistências no projeto', "
                    "'Quais pontos precisam ser esclarecidos?'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["open", "resolved", "all"],
                            "description": "Filtrar por status (padrão: open)",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "resolve_contradiction",
                "description": (
                    "Marca uma contradição do Grafo de Conhecimento como resolvida, registrando "
                    "a solução adotada. Use quando o usuário disser: "
                    "'A contradição X está resolvida desta forma: Y', "
                    "'Resolva a contradição X com a solução Y', "
                    "'Marque a contradição X como resolvida — a decisão foi Y'. "
                    "A contradição é identificada por trecho da descrição."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description_query": {
                            "type": "string",
                            "description": "Trecho do texto da contradição para identificá-la (busca parcial, case-insensitive)",
                        },
                        "resolution_note": {
                            "type": "string",
                            "description": "Descrição da solução adotada para a contradição",
                        },
                        "resolved_by": {
                            "type": "string",
                            "description": "Nome ou papel de quem resolveu (opcional, padrão: 'assistente')",
                        },
                        "new_status": {
                            "type": "string",
                            "enum": ["resolved", "clarified", "dismissed"],
                            "description": "Novo status da contradição (padrão: resolved)",
                        },
                    },
                    "required": ["description_query", "resolution_note"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "delete_contradiction",
                "description": (
                    "Remove permanentemente uma contradição do Grafo de Conhecimento. "
                    "Use quando o usuário disser: 'Exclua a contradição X', "
                    "'Remova a contradição X', 'Delete a contradição X'. "
                    "Requer confirmação explícita antes de excluir. "
                    "A contradição é identificada por trecho da descrição."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description_query": {
                            "type": "string",
                            "description": "Trecho do texto da contradição para identificá-la (busca parcial, case-insensitive)",
                        },
                        "confirm": {
                            "type": "boolean",
                            "description": "Deve ser true para confirmar a exclusão permanente",
                        },
                    },
                    "required": ["description_query", "confirm"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_kh_facts",
                "description": (
                    "Lista os fatos consolidados do Grafo de Conhecimento: "
                    "decisões, responsabilidades, regras e contexto extraídos e validados entre reuniões. "
                    "Use quando o usuário perguntar: 'Quais fatos o sistema consolidou?', "
                    "'Mostre as decisões registradas no grafo', "
                    "'Quais responsabilidades foram documentadas?', "
                    "'Liste os fatos ativos do projeto'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fact_type": {
                            "type": "string",
                            "description": "Filtrar por tipo: decision | responsibility | rule | context | other (opcional)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Máximo de fatos a retornar (padrão 50)",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_bpmn_execution_log",
                "description": (
                    "Retorna o log de execução detalhado do último run do agente BPMN nesta sessão. "
                    "Inclui: fonte (chamada LLM ou fast-path), provider/modelo, tokens, cache hit/miss, "
                    "latência, alterações feitas por _enforce_rules, repair_bpmn e reformat_bpmn_labels, "
                    "métricas do diagrama (steps/edges/lanes/gateways/tipos de tasks) e alertas de títulos "
                    "com mais de 35 chars. Use quando o usuário perguntar sobre diagnóstico do BPMN, "
                    "por que o diagrama ficou diferente do esperado, ou quais correções automáticas foram aplicadas."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []},
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
                "name": "review_bpmn_diagram",
                "description": (
                    "Audita semanticamente um diagrama BPMN armazenado e retorna um relatório "
                    "com violações detectadas (gateway com verbo, task nomeada como decisão, "
                    "fluxos sem rótulo, lanes genéricas, elementos órfãos, etc.). "
                    "Use quando o usuário disser: 'Revise o diagrama X', 'Audite o BPMN Y', "
                    "'Esse gateway deveria ser uma atividade?', 'Analise os problemas do processo Z'. "
                    "Use list_bpmn_processes primeiro para descobrir os nomes disponíveis."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "process_name": {
                            "type": "string",
                            "description": "Nome (ou parte do nome) do processo BPMN a auditar",
                        },
                    },
                    "required": ["process_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "describe_bpmn_process",
                "description": (
                    "Gera uma descrição textual estruturada de um processo BPMN a partir do XML armazenado. "
                    "Produz: participantes (pools/lanes), fluxo numerado passo-a-passo com tipos e condições, "
                    "e resultados possíveis. Útil como 'elo perdido' entre transcrição e diagrama. "
                    "Use quando o usuário pedir: 'Descreva o processo X', 'Como funciona o fluxo Y?', "
                    "'Documente o processo Z em texto'. "
                    "Use list_bpmn_processes para descobrir os nomes disponíveis."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "process_name": {
                            "type": "string",
                            "description": "Nome (ou parte do nome) do processo BPMN a descrever",
                        },
                    },
                    "required": ["process_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "suggest_bpmn_corrections",
                "description": (
                    "A partir das violações detectadas por review_bpmn_diagram, gera um plano de correção "
                    "estruturado para o processo BPMN — lista o que mudar em cada elemento sem aplicar. "
                    "Use quando o usuário pedir: 'Que correções devo fazer no processo X?', "
                    "'Proponha as correções para o diagrama Y', "
                    "'O que precisa mudar no processo Z?'. "
                    "Execute ANTES de save_bpmn_revision."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "process_name": {
                            "type": "string",
                            "description": "Nome (ou parte do nome) do processo BPMN a corrigir",
                        },
                    },
                    "required": ["process_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "save_bpmn_revision",
                "description": (
                    "Salva uma revisão corrigida de um diagrama BPMN como nova versão no banco. "
                    "Use APENAS quando o usuário confirmar explicitamente que quer aplicar correções. "
                    "Requer o XML BPMN corrigido e o nome do processo. "
                    "Admin only."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "process_name": {
                            "type": "string",
                            "description": "Nome (ou parte do nome) do processo BPMN a atualizar",
                        },
                        "bpmn_xml": {
                            "type": "string",
                            "description": "XML BPMN 2.0 corrigido completo",
                        },
                        "process_description": {
                            "type": "string",
                            "description": "Descrição textual do processo corrigido (Markdown, gerada na Fase 3 da revisão)",
                        },
                        "meeting_number": {
                            "type": "integer",
                            "description": "Número da reunião de referência para esta versão (opcional)",
                        },
                        "revision_notes": {
                            "type": "string",
                            "description": "Notas sobre o que foi corrigido nesta revisão",
                        },
                    },
                    "required": ["process_name", "bpmn_xml"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "apply_bpmn_corrections",
                "description": (
                    "Aplica correções cirúrgicas ao diagrama BPMN via LLM (AgentBPMNReviewer) "
                    "e salva o resultado como nova versão no banco. "
                    "Use APÓS suggest_bpmn_corrections identificar os problemas e o usuário confirmar. "
                    "O agente aplica as correções, regenera o XML e incrementa a versão. "
                    "Exemplos de ações: convert_to_task (gateway→userTask), "
                    "convert_to_gateway (task→exclusiveGateway), rename, add_edge_labels. "
                    "Admin only."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "process_name": {
                            "type": "string",
                            "description": "Nome (ou parte do nome) do processo BPMN a corrigir",
                        },
                        "corrections": {
                            "type": "array",
                            "description": "Lista de correções a aplicar ao diagrama",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "element_id": {
                                        "type": "string",
                                        "description": "ID do elemento no XML (ex: S05, G01)",
                                    },
                                    "element_name": {
                                        "type": "string",
                                        "description": "Nome atual do elemento",
                                    },
                                    "action": {
                                        "type": "string",
                                        "enum": [
                                            "convert_to_task",
                                            "convert_to_gateway",
                                            "rename",
                                            "add_edge_labels",
                                            "add_missing_gateway",
                                        ],
                                        "description": "Ação a executar",
                                    },
                                    "new_type": {
                                        "type": "string",
                                        "description": "Novo tipo BPMN (ex: userTask, exclusiveGateway)",
                                    },
                                    "new_name": {
                                        "type": "string",
                                        "description": "Novo nome do elemento",
                                    },
                                    "reason": {
                                        "type": "string",
                                        "description": "Motivo da correção (para o log)",
                                    },
                                },
                                "required": ["element_id", "action"],
                            },
                        },
                        "version_notes": {
                            "type": "string",
                            "description": "Nota de versão (opcional)",
                        },
                    },
                    "required": ["process_name", "corrections"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_bpmn_versions",
                "description": (
                    "Lista todas as versões de um processo BPMN, mostrando ID, número de versão, "
                    "status (atual/histórico), reunião de origem e notas de alteração. "
                    "Use antes de delete_bpmn_version para obter o version_id correto."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "process_name": {
                            "type": "string",
                            "description": "Nome (ou parte do nome) do processo BPMN a consultar.",
                        },
                    },
                    "required": ["process_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "delete_bpmn_version",
                "description": (
                    "Exclui permanentemente uma versão específica de um diagrama BPMN. "
                    "Seguro: recusa excluir a única versão de um processo; se a versão "
                    "excluída for a atual, promove automaticamente a versão anterior. "
                    "Use list_bpmn_versions para obter o version_id antes de chamar esta tool. "
                    "Admin only."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "version_id": {
                            "type": "string",
                            "description": "UUID da versão BPMN a excluir (obtido via list_bpmn_versions).",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Motivo da exclusão (ex: 'versão duplicada', 'gerada com erro').",
                        },
                    },
                    "required": ["version_id"],
                },
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
                "name": "list_context_files",
                "description": (
                    "Lista os arquivos de referência (HTML, PPTX, PDF, TXT, MD) carregados no contexto ativo. "
                    "Use quando o usuário perguntar sobre documentos de referência, manuais, políticas ou "
                    "apresentações disponíveis no contexto."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []},
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
                "name": "update_requirement_status",
                "description": (
                    "Atualiza o status de um ou mais requisitos do projeto. "
                    "Pode filtrar por número(s) de requisito, tipo, status atual ou reunião de origem. "
                    "USE quando o usuário pedir para mudar, atualizar ou corrigir o status de requisitos. "
                    "Valores válidos para status: 'active', 'revised', 'contradicted', 'confirmed'. "
                    "Registra uma nova versão em requirement_versions com change_type='status_change'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "new_status": {
                            "type": "string",
                            "enum": ["active", "revised", "contradicted", "confirmed"],
                            "description": "Novo status a aplicar nos requisitos selecionados.",
                        },
                        "req_numbers": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": (
                                "Lista de números de requisito a atualizar (ex: [1, 3, 5]). "
                                "Omita para usar os outros filtros."
                            ),
                        },
                        "filter_req_type": {
                            "type": "string",
                            "description": "Filtrar por tipo: 'funcional', 'não-funcional', 'regra de negócio', etc. (opcional)",
                        },
                        "filter_current_status": {
                            "type": "string",
                            "description": "Filtrar apenas requisitos com este status atual (opcional).",
                        },
                        "filter_meeting_number": {
                            "type": "integer",
                            "description": "Filtrar apenas requisitos originados de uma reunião específica (opcional).",
                        },
                        "status_note": {
                            "type": "string",
                            "description": "Nota explicando o motivo da mudança de status (opcional mas recomendado).",
                        },
                    },
                    "required": ["new_status"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update_requirement_text",
                "description": (
                    "Atualiza o título e/ou a descrição completa de um requisito específico pelo número. "
                    "USE quando o usuário pedir para corrigir, trocar ou reescrever o texto de um requisito "
                    "e a correção envolver aspas, caracteres especiais ou mudança substancial de conteúdo — "
                    "casos em que apply_text_correction não seria adequada. "
                    "Exemplos de trigger: 'Corrija a descrição do REQ-710', "
                    "'Substitua o texto do requisito 710 por ...', "
                    "'Altere o título do REQ-005 para ...'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "req_number": {
                            "type": "integer",
                            "description": "Número do requisito a atualizar (ex: 710 para REQ-710)",
                        },
                        "new_description": {
                            "type": "string",
                            "description": "Novo texto completo da descrição do requisito (opcional se apenas title for alterado)",
                        },
                        "new_title": {
                            "type": "string",
                            "description": "Novo título do requisito (opcional se apenas description for alterada)",
                        },
                        "change_note": {
                            "type": "string",
                            "description": "Nota explicando o motivo da alteração (opcional, mas recomendada para rastreabilidade)",
                        },
                    },
                    "required": ["req_number"],
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
                "name": "update_sbvr_rule",
                "description": (
                    "Atualiza o enunciado e/ou tipo de uma regra SBVR existente pelo seu ID (ex: BR002, BR006). "
                    "USE quando o usuário pedir para corrigir, atualizar ou substituir o texto de uma regra SBVR. "
                    "Exemplos de trigger: 'Corrija a regra BR002', 'Atualize o enunciado de BR006 para ...', "
                    "'Troque o texto da regra BR007'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "rule_id": {
                            "type": "string",
                            "description": "ID da regra SBVR a atualizar (ex: 'BR002', 'RBN-003')",
                        },
                        "new_statement": {
                            "type": "string",
                            "description": "Novo enunciado formal da regra no padrão SBVR",
                        },
                        "new_rule_type": {
                            "type": "string",
                            "description": "Novo tipo da regra: 'Definitional Rule', 'Behavioral Rule', 'Structural Rule' (opcional)",
                        },
                    },
                    "required": ["rule_id", "new_statement"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "update_sbvr_term_by_id",
                "description": (
                    "Atualiza um termo SBVR pelo seu UUID — necessário quando há múltiplos termos "
                    "com o mesmo nome (ex: 3 entradas de 'Identificador do Documento'). "
                    "USE quando o usuário quiser atualizar um termo específico identificado pelo ID, "
                    "ou quando update_sbvr_term falhou por haver mais de um termo com o mesmo nome. "
                    "Para obter o ID de um termo, use get_sbvr_terms primeiro."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "term_id": {
                            "type": "string",
                            "description": "UUID do termo SBVR a atualizar",
                        },
                        "new_definition": {
                            "type": "string",
                            "description": "Nova definição do termo (opcional se apenas category for alterada)",
                        },
                        "new_category": {
                            "type": "string",
                            "description": "Nova categoria do termo (opcional)",
                        },
                    },
                    "required": ["term_id"],
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
                "name": "reprocess_meeting_full",
                "description": (
                    "Reprocessa completamente uma reunião existente re-executando o pipeline "
                    "completo (Ata+BABOK, Requisitos, SBVR, BMM, DMN, Argumentação IBIS, "
                    "Relatório Executivo, Sumário por Perspectiva, Grafo de Conhecimento e CKF) "
                    "sobre a transcrição armazenada. "
                    "Atualiza todos os artefatos no Supabase sem criar uma nova reunião. "
                    "USE quando o usuário pedir para reprocessar, atualizar ou corrigir todos "
                    "os artefatos de uma reunião de uma só vez, ou quando quiser garantir que "
                    "a reunião tenha todos os artefatos completos e atualizados. "
                    "Para reprocessar apenas requisitos, prefira reprocess_meeting_requirements. "
                    "Para regenerar apenas o Relatório Executivo, prefira regenerate_executive_report. "
                    "🔒 Requer perfil administrador."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_number": {
                            "type": "integer",
                            "description": "Número da reunião a reprocessar",
                        },
                        "run_bpmn": {
                            "type": "boolean",
                            "description": "Se true, gera também o BPMN (mais lento). Padrão: false.",
                        },
                        "run_quality": {
                            "type": "boolean",
                            "description": "Se true, avalia qualidade da transcrição. Padrão: false.",
                        },
                        "output_language": {
                            "type": "string",
                            "description": "Idioma dos artefatos gerados. Padrão: 'Auto-detect'.",
                        },
                    },
                    "required": ["meeting_number"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "reprocess_communication_noise",
                "description": (
                    "Re-executa o AgentCommunicationNoise sobre a transcrição armazenada de uma reunião "
                    "e salva os resultados (ambiguidades, lacunas, índice de ruído de comunicação). "
                    "Use meeting_number=0 para reprocessar todas as reuniões do projeto. "
                    "🔒 Requer perfil administrador."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_number": {
                            "type": "integer",
                            "description": "Número da reunião. Use 0 para reprocessar todas as reuniões do projeto.",
                        },
                        "output_language": {
                            "type": "string",
                            "description": "Idioma de saída: 'Português', 'English' ou 'Auto-detect'.",
                        },
                    },
                    "required": ["meeting_number"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "regenerate_executive_report",
                "description": (
                    "Regenera apenas o Relatório Executivo HTML de uma reunião usando os "
                    "artefatos já armazenados no banco (BPMN, requisitos, SBVR, BMM) mais "
                    "uma re-execução leve do AgentMinutes sobre a transcrição. "
                    "Muito mais rápido que reprocess_meeting_full (~2 chamadas LLM vs ~10+). "
                    "USE quando o usuário pedir para regenerar, atualizar ou corrigir apenas "
                    "o relatório executivo de uma ou mais reuniões. "
                    "🔒 Requer perfil administrador."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_number": {
                            "type": "integer",
                            "description": "Número da reunião cujo relatório deve ser regenerado.",
                        },
                        "output_language": {
                            "type": "string",
                            "description": "Idioma do relatório. Padrão: 'Auto-detect'.",
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
                "name": "get_database_integrity",
                "description": (
                    "Retorna um relatório completo de integridade do banco de dados do projeto: "
                    "saúde geral (%), reuniões completas vs. com problemas, e lista de campos "
                    "ausentes por reunião (transcrição, ata, embeddings, BPMN, tokens, provedor LLM). "
                    "Inclui ações recomendadas para cada tipo de problema. "
                    "USE quando o usuário perguntar sobre integridade, saúde, completude ou "
                    "problemas nos dados do banco. "
                    "🔒 Requer perfil administrador."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fix_missing_llm_provider",
                "description": (
                    "Atribui um provedor LLM a todas as reuniões do projeto que não têm "
                    "llm_provider registrado (processadas antes deste campo existir). "
                    "Necessário para que o Estimador de Custos calcule corretamente. "
                    "USE quando o usuário pedir para corrigir o provedor ausente, definir o "
                    "provedor das reuniões antigas, ou corrigir integridade de provedor LLM. "
                    "🔒 Requer perfil administrador."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "provider": {
                            "type": "string",
                            "description": (
                                "Nome do provedor LLM a atribuir. "
                                "Exemplos: 'DeepSeek', 'Claude (Anthropic)', 'OpenAI', 'Groq', 'Google Gemini'. "
                                "Infira com base no contexto do projeto se não informado."
                            ),
                        }
                    },
                    "required": ["provider"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_meeting_embeddings",
                "description": (
                    "Gera embeddings de transcrição para reuniões que ainda não foram indexadas "
                    "(sem chunks em transcript_chunks). "
                    "Usa automaticamente o provedor e a API key configurados em Configurações → "
                    "Embeddings & Busca — NÃO peça provider, modelo ou API key ao usuário. "
                    "USE quando o usuário pedir para gerar embeddings, indexar transcrições, "
                    "ou corrigir reuniões sem embeddings para busca semântica. "
                    "Para uma única reunião, prefira embed_meeting. "
                    "🔒 Requer perfil administrador."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_numbers": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": (
                                "Lista de números de reunião a indexar. "
                                "Omita para indexar todas as elegíveis (com transcrição, sem embedding)."
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
                "name": "embed_meeting",
                "description": (
                    "Gera (ou regenera) os embeddings de transcrição de UMA reunião específica. "
                    "Usa automaticamente o provedor e a API key configurados em Configurações → "
                    "Embeddings & Busca — NÃO peça provider, modelo ou API key ao usuário. "
                    "USE quando o usuário mencionar um número de reunião específico: "
                    "'gere o embedding da reunião 11', 'indexe a reunião 3', etc. "
                    "O parâmetro force=true regenera mesmo que a reunião já tenha embeddings. "
                    "🔒 Requer perfil administrador."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_number": {
                            "type": "integer",
                            "description": "Número da reunião cujo embedding deve ser gerado",
                        },
                        "force": {
                            "type": "boolean",
                            "description": (
                                "Se true, apaga os embeddings existentes e gera novos. "
                                "Padrão: false (pula se já tiver embeddings)."
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
                "name": "get_system_capabilities",
                "description": (
                    "Retorna a lista completa de funcionalidades, integrações e operações "
                    "disponíveis no Process2Diagram (P2D). "
                    "USE SEMPRE que o usuário perguntar sobre: o que o sistema faz, "
                    "quais integrações existem, quais operações estão disponíveis, "
                    "funcionalidades do Google Calendar, MCP, ferramentas do assistente, "
                    "ou qualquer variação de 'o que você pode fazer'."
                ),
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
        },
        # ── Google Calendar tools ──────────────────────────────────────────────
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
                "name": "calendar_schedule_action_items",
                "description": (
                    "Cria eventos no Google Calendar para os itens de ação de uma reunião do P2D. "
                    "Lê automaticamente os itens de ação da ata da reunião e cria um evento por item. "
                    "USE quando o usuário pedir para agendar os encaminhamentos, criar lembretes "
                    "para os itens de ação, ou transferir as tarefas da ata para o calendário. "
                    "🔒 Requer perfil administrador."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_number": {
                            "type": "integer",
                            "description": "Número da reunião cujos itens de ação serão agendados",
                        },
                        "default_date": {
                            "type": "string",
                            "description": (
                                "Data/hora base para os eventos (ISO 8601, ex: '2026-05-20T10:00:00'). "
                                "Usada para itens sem prazo explícito na ata."
                            ),
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "Duração de cada evento em minutos (padrão 30)",
                        },
                    },
                    "required": ["meeting_number", "default_date"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calendar_share_with_user",
                "description": (
                    "Compartilha a agenda do Google Calendar do projeto com um e-mail Google. "
                    "USE quando o usuário pedir para dar acesso ao calendário, compartilhar a agenda "
                    "com alguém, adicionar permissão de visualização ou edição no Google Calendar. "
                    "🔒 Requer perfil administrador."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "email": {
                            "type": "string",
                            "description": "E-mail Google da pessoa que receberá acesso (ex: pedro.regato@gmail.com)",
                        },
                        "role": {
                            "type": "string",
                            "enum": ["reader", "writer", "owner"],
                            "description": (
                                "Nível de acesso: "
                                "'reader' = apenas visualizar, "
                                "'writer' = criar e editar eventos (padrão), "
                                "'owner' = gerenciar agenda e compartilhamento"
                            ),
                        },
                    },
                    "required": ["email"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calendar_revoke_access",
                "description": (
                    "Remove o acesso de um e-mail Google à agenda do projeto. "
                    "USE quando o usuário pedir para revogar acesso, remover permissão "
                    "ou descompartilhar a agenda com alguém. "
                    "🔒 Requer perfil administrador."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "email": {
                            "type": "string",
                            "description": "E-mail Google cujo acesso será removido",
                        },
                    },
                    "required": ["email"],
                },
            },
        },
        # ---------------------------- moedas
        {
            "type": "function",
            "function": {
                "name": "convert_usd_to_brl",
                "description": (
                    "Obtém a cotação atual do dólar americano (USD) em reais brasileiros (BRL) "
                    "e converte um valor se fornecido. "
                    "USE para qualquer pergunta sobre: cotação do dólar hoje, valor atual do USD, "
                    "quanto vale um dólar em reais, conversão de USD para BRL, "
                    "custo em reais de valores em dólar. "
                    "Quando o usuário não informar um valor, use usd_amount=1.0 para retornar "
                    "apenas a cotação atual."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "usd_amount": {
                            "type": "number",
                            "description": (
                                "Valor em dólares a converter. "
                                "Use 1.0 quando o usuário perguntar apenas pela cotação atual."
                            ),
                        }
                    },
                    "required": ["usd_amount"],
                },
            },
        },        
        # ---------------------------- Report
        {
         "type": "function",
         "function": {
                "name": "get_executive_report",
                "description": (
                    "Retorna o relatório executivo HTML de uma reunião já gerado e armazenado. "
                    "Use quando o usuário pede para ver, acessar ou baixar o relatório executivo. "
                    "NÃO usa esta ferramenta para gerar um relatório novo — apenas recupera o existente."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_number": {
                            "type": "integer",
                            "description": "Número da reunião cujo relatório deve ser recuperado."
                        }
                    },
                    "required": ["meeting_number"]
                }
            }
        },
        # ---------------------------- speaker
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
        # ── Chart tools ──────────────────────────────────────────────────────
        {
            "type": "function",
            "function": {
                "name": "generate_requirements_chart",
                "description": (
                    "Gera um gráfico de barras interativo com a distribuição de requisitos por tipo "
                    "(Funcional, Não-Funcional, Regra de Negócio, etc.) e/ou por prioridade. "
                    "USE para: 'mostre um gráfico de requisitos', 'quantos requisitos por tipo', "
                    "'distribuição de prioridades', 'gráfico de RF vs RNF'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "group_by": {
                            "type": "string",
                            "enum": ["type", "priority", "both"],
                            "description": "Agrupar por tipo (type), prioridade (priority) ou ambos (both). Padrão: type.",
                        },
                        "meeting_number": {
                            "type": "integer",
                            "description": "Filtrar por reunião específica. Omita para todo o projeto.",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_meetings_timeline",
                "description": (
                    "Gera um gráfico de linha do tempo das reuniões do projeto, mostrando "
                    "volume de artefatos (requisitos, decisões, ações) por reunião. "
                    "USE para: 'mostre a evolução das reuniões', 'linha do tempo', "
                    "'como foi o projeto ao longo do tempo', 'gráfico de reuniões'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "metric": {
                            "type": "string",
                            "enum": ["requirements", "decisions", "action_items", "all"],
                            "description": "Métrica a exibir. Padrão: all.",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_action_items_chart",
                "description": (
                    "Gera um gráfico com o status dos itens de ação (pendentes, em andamento, concluídos) "
                    "e/ou distribuição por responsável. "
                    "USE para: 'gráfico de ações', 'status das tarefas', 'quem tem mais ações pendentes', "
                    "'itens de ação por responsável'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "group_by": {
                            "type": "string",
                            "enum": ["status", "responsible", "meeting"],
                            "description": "Agrupar por status, responsável ou reunião. Padrão: status.",
                        },
                        "meeting_number": {
                            "type": "integer",
                            "description": "Filtrar por reunião específica. Omita para todo o projeto.",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_roi_chart",
                "description": (
                    "Gera um gráfico de barras com o indicador ROI-TR de cada reunião do projeto. "
                    "USE para: 'gráfico de ROI', 'qual reunião teve mais valor', 'evolução do ROI', "
                    "'comparar qualidade das reuniões'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cost_per_hour": {
                            "type": "number",
                            "description": "Custo médio por hora/participante em R$. Padrão: 150.",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_custom_chart",
                "description": (
                    "Gera um gráfico completamente personalizado a partir de dados fornecidos. "
                    "USE quando o usuário pedir um gráfico específico que não se encaixa nos "
                    "gráficos pré-definidos (scatter, pizza, heatmap, etc.). "
                    "O LLM fornece labels e valores e o sistema renderiza interativamente."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chart_type": {
                            "type": "string",
                            "description": "Tipo: bar, line, pie, scatter, heatmap, funnel.",
                        },
                        "title": {
                            "type": "string",
                            "description": "Título do gráfico.",
                        },
                        "labels": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Rótulos do eixo X ou categorias (para pizza).",
                        },
                        "values": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "Valores numéricos correspondentes aos rótulos.",
                        },
                        "x_label": {
                            "type": "string",
                            "description": "Título do eixo X (opcional).",
                        },
                        "y_label": {
                            "type": "string",
                            "description": "Título do eixo Y (opcional).",
                        },
                        "series_name": {
                            "type": "string",
                            "description": "Nome da série de dados (opcional).",
                        },
                    },
                    "required": ["chart_type", "title", "labels", "values"],
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
        {
            "type": "function",
            "function": {
                "name": "render_table",
                "description": (
                    "Use this tool INSTEAD of writing a Markdown table whenever the response "
                    "contains structured tabular data. This captures the data for Excel export. "
                    "Call this once per table. Do NOT call it for purely narrative responses."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Descriptive title for the table and chart (e.g. 'Custo de Embeddings por Reuniao — SDEA')."
                        },
                        "columns": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Column header names, in display order."
                        },
                        "rows": {
                            "type": "array",
                            "items": {"type": "array", "items": {}},
                            "description": "Data rows. Each row is an array of values matching the columns order. Values may be strings, numbers, or null."
                        },
                        "chart_type": {
                            "type": "string",
                            "enum": ["bar", "pie", "line", "none"],
                            "description": "Chart type to generate in Excel. Use 'none' if the data is not suitable for charting."
                        },
                        "chart_x_col": {
                            "type": "string",
                            "description": "Column name to use as X axis (bar/line) or slice labels (pie). Required when chart_type != 'none'."
                        },
                        "chart_y_cols": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Column names to use as Y axis series. One series = one column. Required when chart_type != 'none'."
                        }
                    },
                    "required": ["title", "columns", "rows", "chart_type"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "populate_roster",
                "description": (
                    "Pre-populate the project roster by extracting participant names from existing "
                    "meeting minutes (minutes_md). Generates initials, aliases, and assigns colors "
                    "automatically. Skips participants already in the roster. "
                    "Use dry_run=true first to preview candidates before writing to the database. "
                    "Admin only. Should be used when the user asks to create or seed the roster "
                    "automatically from existing meetings."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dry_run": {
                            "type": "boolean",
                            "description": (
                                "If true, returns the candidate list without writing to the database. "
                                "Recommended as a first call so the user can review before confirming. "
                                "Default: false."
                            )
                        },
                        "meeting_numbers": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": (
                                "Optional list of meeting numbers to scan. "
                                "If omitted, all meetings in the active project are scanned."
                            )
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "populate_knowledge_hub",
                "description": (
                    "Extract and persist structured knowledge into the Knowledge Hub tables "
                    "(kh_entities, kh_processes, kh_facts, kh_contradictions). "
                    "This tool is EXCLUSIVELY for populating these 4 specific kh_* tables — "
                    "it has nothing to do with embeddings, database health, or reprocessing. "
                    "Use this tool whenever the user asks to populate, backfill or rewrite the "
                    "Knowledge Hub. Each meeting transcript is sent to the LLM which extracts "
                    "entities (people, teams, systems), processes, facts (rules, decisions, "
                    "constraints) and contradictions, then persists them in the kh_* tables. "
                    "Admin only."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_numbers": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": (
                                "List of meeting numbers to process. "
                                "If omitted, all meetings in the active project are processed."
                            )
                        },
                        "overwrite": {
                            "type": "boolean",
                            "description": (
                                "If true, existing facts and contradictions linked to each "
                                "meeting will be deleted before re-extraction, allowing a "
                                "clean rewrite. Entities and processes are always upserted "
                                "(merged). Default: false."
                            )
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "detect_contradictions",
                "description": (
                    "Run a full cross-meeting contradiction scan on the project's Knowledge Hub facts. "
                    "Compares all stored kh_facts entries (grouped by fact_type) using a specialised "
                    "LLM agent and inserts detected contradictions into kh_contradictions. "
                    "Use this after populate_knowledge_hub to find inconsistencies across meetings, "
                    "or whenever the user asks to find, scan or analyse contradictions in the project. "
                    "Admin only."
                ),
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
                "name": "lookup_entity",
                "description": (
                    "Look up details of a specific entity in the Knowledge Hub by name. "
                    "Returns entity type, aliases, occurrence count, metadata description, "
                    "and the list of meetings where it appeared. "
                    "Use this to investigate unknown or suspicious entities (e.g. ASR artifacts) "
                    "before deciding to delete or merge them."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_name": {
                            "type": "string",
                            "description": "Name (or partial name) of the entity to look up.",
                        },
                    },
                    "required": ["entity_name"],
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delete_entity",
                "description": (
                    "Permanently delete a spurious, bogus or unrecognised entity from the "
                    "Knowledge Hub. Use when the entity is confirmed to be an ASR artifact, "
                    "noise or a mistake — and NOT a duplicate of another entity (use "
                    "resolve_entity_ambiguity for duplicates). Admin only."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "entity_name": {
                            "type": "string",
                            "description": "Name (or partial name) of the entity to delete.",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Why this entity should be deleted (e.g. 'ASR artifact', 'does not exist').",
                        },
                    },
                    "required": ["entity_name"],
                },
            }
        },
        {
            "type": "function",
            "function": {
                "name": "resolve_entity_ambiguity",
                "description": (
                    "Merges two or more entities that represent the same real-world object "
                    "(person, system, document, concept, etc.) into one canonical entity in the "
                    "Knowledge Hub. Use when the user identifies duplicates, e.g. 'Pedro Gentil' "
                    "and 'Pedro Gentil Regato de Oliveira Soares' are the same person. "
                    "Searches entities by name (case-insensitive, substring match, aliases included). "
                    "The canonical entity absorbs the occurrence counts, aliases and meeting history "
                    "of all duplicates, which are then deleted. Admin only."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "canonical_name": {
                            "type": "string",
                            "description": (
                                "Name of the entity to KEEP as the canonical version. "
                                "Must (partially) match an existing entity in the Knowledge Hub."
                            ),
                        },
                        "duplicate_names": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Names of the entities to merge INTO the canonical entity. "
                                "Each name is searched by substring match and aliases. "
                                "These entities will be absorbed and deleted after the merge."
                            ),
                        },
                        "reason": {
                            "type": "string",
                            "description": "Brief explanation of why these represent the same entity.",
                        },
                    },
                    "required": ["canonical_name", "duplicate_names"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_cache_stats",
                "description": (
                    "Retorna estatísticas do cache semântico de LLM: total de entradas, "
                    "hits acumulados, tokens economizados e custo estimado em USD. "
                    "Inclui breakdown por agente (bpmn, minutes, requirements, sbvr, bmm, etc.). "
                    "Use quando o usuário perguntar sobre economia de API, hits de cache, "
                    "desempenho do pipeline ou custo do sistema."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_name": {
                            "type": "string",
                            "description": (
                                "Opcional. Filtrar estatísticas para um agente específico "
                                "(ex: 'bpmn', 'minutes', 'sbvr', 'bmm', 'requirements'). "
                                "Se omitido, retorna estatísticas globais."
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
                "name": "clear_llm_cache",
                "description": (
                    "Invalida entradas do cache semântico de LLM. Admin only. "
                    "Use quando o prompt de um agente foi alterado e as respostas "
                    "cacheadas estão desatualizadas, ou para forçar reprocessamento limpo."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent_name": {
                            "type": "string",
                            "description": (
                                "Opcional. Nome do agente cujo cache deve ser limpo "
                                "(ex: 'bpmn', 'sbvr'). Se omitido, limpa TODO o cache."
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
                "name": "list_meeting_documents",
                "description": (
                    "Lista os documentos do contexto/projeto (contratos, especificações, "
                    "requisitos, fluxogramas, BRDs, atas externas, critérios de aceite, etc.). "
                    "Use quando o usuário perguntar sobre documentos disponíveis, quais documentos "
                    "existem em uma categoria, ou quiser filtrar por tipo específico. "
                    "Documentos não precisam estar vinculados a uma reunião. "
                    "Pode filtrar por categoria (ex: 'Requisitos'), tipo exato ou reunião."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_number": {
                            "type": "integer",
                            "description": "Filtrar documentos vinculados a uma reunião específica (opcional)",
                        },
                        "doc_type": {
                            "type": "string",
                            "description": (
                                "Código do tipo de documento para filtrar (opcional). "
                                "Ex: SRS, BRD, TAP, ASIS, TOBE, CONTRATO, SLA, ACCEPTANCE_CRITERIA. "
                                "Use get_document_types para ver todos os códigos disponíveis."
                            ),
                        },
                        "category": {
                            "type": "string",
                            "description": (
                                "Nome da categoria para filtrar todos os tipos dessa categoria (opcional). "
                                "Ex: 'Requisitos', 'Planejamento', 'Processos', 'Contratual', 'Qualidade'. "
                                "Use get_document_types para ver todas as categorias disponíveis."
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
                "name": "get_document_content",
                "description": (
                    "Retorna o conteúdo completo de um documento específico pelo ID. "
                    "Use quando o usuário pedir para ler, resumir ou analisar o conteúdo de um documento. "
                    "Obtenha o doc_id chamando list_meeting_documents primeiro."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "doc_id": {
                            "type": "string",
                            "description": "UUID do documento (obtido via list_meeting_documents)",
                        },
                    },
                    "required": ["doc_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_documents",
                "description": (
                    "Pesquisa documentos do projeto por similaridade semântica (embeddings) "
                    "ou por palavra-chave. Use quando o usuário quiser encontrar documentos "
                    "sobre um tema específico, cláusula contratual, requisito ou processo. "
                    "Retorna trechos relevantes com o documento de origem."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Texto da busca — frase ou palavras-chave",
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["semantic", "keyword"],
                            "description": (
                                "Modo de busca: 'semantic' usa embeddings pgvector (melhor para conceitos), "
                                "'keyword' usa ILIKE (melhor para termos exatos). Padrão: semantic."
                            ),
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_document_types",
                "description": (
                    "Retorna a taxonomia completa de tipos de documentos suportados, "
                    "agrupados por categoria (Planejamento, Requisitos, Processos, etc.). "
                    "Use quando o usuário perguntar que tipos de documentos podem ser cadastrados "
                    "ou quiser entender a classificação de documentos."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "suggest_document_title",
                "description": (
                    "Analisa o conteúdo de um documento da biblioteca e sugere um título mais "
                    "adequado usando IA. Também atualiza o título no banco de dados se confirmado. "
                    "Use quando o usuário pedir para renomear, melhorar o nome ou sugerir título "
                    "para um documento da biblioteca."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "doc_id": {
                            "type": "string",
                            "description": "UUID do documento (obtido via list_meeting_documents ou search_documents).",
                        },
                        "apply": {
                            "type": "boolean",
                            "description": (
                                "Se true, salva o título sugerido no banco imediatamente. "
                                "Se false (padrão), apenas exibe a sugestão sem salvar."
                            ),
                        },
                    },
                    "required": ["doc_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_p2d_help",
                "description": (
                    "Ferramenta especializada para responder perguntas sobre o "
                    "Process2Diagram: conceitos, termos técnicos, siglas, agentes, "
                    "páginas e funcionalidades da plataforma. "
                    "Use SEMPRE que o usuário perguntar 'O que é X?', 'Explique X', "
                    "'Como funciona X?', 'Para que serve X?' onde X é qualquer "
                    "componente, sigla ou conceito do P2D (BPMN, SBVR, BMM, DMN, "
                    "IBIS, RAG, NER, gateway, lane, pool, embedding, KnowledgeHub, "
                    "pipeline, Mermaid, pgvector, spaCy, Supabase, CKF, ROI-TR, "
                    "agente, assistente, diagrama, ata, artefato, etc.)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": (
                                "Conceito, termo, sigla ou funcionalidade a explicar "
                                "(ex: 'IBIS', 'SBVR', 'gateway exclusivo', 'RAG', "
                                "'KnowledgeHub', 'embedding', 'pipeline')"
                            ),
                        },
                    },
                    "required": ["topic"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_glossary",
                "description": (
                    "Busca termos no Glossário técnico do Process2Diagram e retorna "
                    "definições, exemplos e termos relacionados. "
                    "Use quando o usuário perguntar o significado de um termo técnico, "
                    "quiser entender um conceito do sistema, ou pedir explicação de siglas "
                    "como BPMN, SBVR, BMM, DMN, RAG, NER, RLS, ASR, KPI, ROI-TR, CKF etc."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "Termo ou conceito a buscar "
                                "(ex: 'BPMN', 'embedding', 'gateway', 'rastreabilidade')"
                            ),
                        },
                        "tag": {
                            "type": "string",
                            "enum": ["bpmn", "req", "ai", "dev", "neg"],
                            "description": (
                                "Filtro opcional por categoria: "
                                "bpmn=Modelagem & BPMN, req=Requisitos & Spec, "
                                "ai=IA & LLM, dev=Dev & Infra, neg=Negócios & Metodologia"
                            ),
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_skill_reference",
                "description": (
                    "Lê as instruções internas de um agente do sistema Process2Diagram. "
                    "Use quando o usuário perguntar COMO um agente funciona, quais regras ele segue, "
                    "qual é o método de modelagem do AgentBPMN, como o AgentMinutes estrutura a ata, "
                    "quais critérios o AgentRequirements usa para classificar requisitos etc. "
                    "Agentes válidos: bpmn, minutes, requirements, sbvr, bmm, dmn, argumentation, "
                    "synthesizer, transcript_quality, communication_noise, ckf_updater, "
                    "knowledge_extractor, query_summarizer. "
                    "Parâmetro section opcional: filtra por cabeçalho específico dentro do arquivo "
                    "(ex: 'Objetivo', 'Formato de Saída', 'Checklist de Qualidade')."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "agent": {
                            "type": "string",
                            "description": (
                                "Nome do agente (ex: 'bpmn', 'minutes', 'requirements', "
                                "'sbvr', 'bmm', 'dmn', 'argumentation', 'synthesizer', "
                                "'transcript_quality', 'communication_noise')"
                            ),
                        },
                        "section": {
                            "type": "string",
                            "description": (
                                "Cabeçalho de seção a extrair (opcional). "
                                "Se omitido, retorna todo o conteúdo da skill. "
                                "Exemplos: 'Objetivo', 'Método de Modelagem', "
                                "'Formato de Saída', 'Checklist de Qualidade'"
                            ),
                        },
                    },
                    "required": ["agent"],
                },
            },
        },
        # ── IBIS / Argumentação ───────────────────────────────────────────────
        {
            "type": "function",
            "function": {
                "name": "search_ibis_debates",
                "description": (
                    "Busca questões IBIS (debates argumentativos) das reuniões do projeto "
                    "por tema ou palavra-chave. Retorna questões com alternativas, prós/contras, "
                    "resolução e reunião de origem. "
                    "Use para: 'O que foi debatido sobre X?', 'Quais decisões sobre Y?', "
                    "'Quais alternativas foram consideradas para Z?', "
                    "'Liste os debates relacionados ao tema T por reunião.'"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "Tema ou palavra-chave a buscar nas questões IBIS "
                                "(ex: 'Catálogo Mestre', 'integração', 'prazo', 'aprovação')"
                            ),
                        },
                        "meeting_number": {
                            "type": "integer",
                            "description": "Filtrar por reunião específica (opcional)",
                        },
                        "resolution_filter": {
                            "type": "string",
                            "enum": ["all", "decided", "deferred", "unresolved"],
                            "description": "Filtrar pelo status de resolução (padrão: all)",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_ibis_timeline",
                "description": (
                    "Retorna a evolução cronológica dos debates IBIS agrupados por reunião, "
                    "com contagens de questões decididas, adiadas e em aberto. "
                    "Gera um gráfico de barras empilhado por status de resolução. "
                    "Use para: 'Como o debate sobre X evoluiu ao longo das reuniões?', "
                    "'Qual reunião teve mais debates não resolvidos?'"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Tema a filtrar (opcional — omita para ver todos os debates do projeto)",
                        },
                    },
                    "required": [],
                },
            },
        },
        # ── Cross-meeting / agenda ────────────────────────────────────────────────
        {
            "type": "function",
            "function": {
                "name": "generate_next_agenda",
                "description": (
                    "Gera uma sugestão de pauta para a próxima reunião com base nos "
                    "itens pendentes do projeto: decisões IBIS adiadas, encaminhamentos "
                    "não concluídos das atas e tópicos sem resolução. "
                    "Use quando o usuário pedir para preparar a próxima reunião, "
                    "montar pauta ou revisar pendências."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": (
                                "Filtro temático opcional — limita a pauta a um tema "
                                "específico (ex: 'autenticação', 'catálogo'). "
                                "Omita para incluir todos os itens pendentes do projeto."
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
                "name": "cluster_topic_decisions",
                "description": (
                    "Agrupa decisões, regras DMN e debates IBIS sobre um tema específico "
                    "em TODAS as reuniões do projeto. Use quando o usuário quiser ver "
                    "como um tópico evoluiu ao longo das reuniões — ex: 'mostre tudo que "
                    "foi decidido sobre autenticação', 'como o tema X foi tratado nas reuniões'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Palavra-chave ou tema a pesquisar (ex: 'autenticação', 'catálogo')",
                        },
                        "artifact_type": {
                            "type": "string",
                            "enum": ["all", "dmn", "ibis", "minutes"],
                            "description": (
                                "Tipo de artefato a incluir: 'all' (padrão) busca em DMN + "
                                "IBIS + atas; 'dmn' apenas decisões DMN; 'ibis' apenas "
                                "debates IBIS; 'minutes' apenas decisões de atas."
                            ),
                        },
                    },
                    "required": ["topic"],
                },
            },
        },
        # ── A2UI — renderização inline no chat ────────────────────────────────────
        {
            "type": "function",
            "function": {
                "name": "show_bpmn_diagram",
                "description": (
                    "Exibe um diagrama BPMN interativo diretamente no chat, com pan/zoom. "
                    "USE quando o usuário pedir para VER, MOSTRAR ou VISUALIZAR um fluxo ou processo BPMN. "
                    "Use list_bpmn_processes primeiro para descobrir os nomes disponíveis."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "process_name": {
                            "type": "string",
                            "description": "Nome ou parte do nome do processo BPMN a exibir.",
                        },
                        "meeting_number": {
                            "type": "integer",
                            "description": "Número da reunião para filtrar a versão do diagrama (opcional).",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "show_mermaid_diagram",
                "description": (
                    "Exibe o fluxograma Mermaid de uma reunião diretamente no chat. "
                    "USE quando o usuário pedir para ver o fluxograma, diagrama de fluxo ou Mermaid. "
                    "O diagrama é renderizado inline com pan/zoom e alternância TD/LR."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_number": {
                            "type": "integer",
                            "description": "Número da reunião cujo fluxograma deve ser exibido.",
                        },
                    },
                    "required": ["meeting_number"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "render_mermaid_code",
                "description": (
                    "Renderiza um diagrama Mermaid gerado pelo assistente diretamente no chat. "
                    "USE quando o usuário pedir para criar, gerar ou desenhar um fluxograma, "
                    "diagrama de sequência, diagrama de classes, diagrama de estado ou qualquer "
                    "outro diagrama Mermaid a partir de uma descrição. "
                    "Gere o código Mermaid completo e válido no parâmetro 'mermaid_code'. "
                    "O diagrama é renderizado inline com pan/zoom."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "mermaid_code": {
                            "type": "string",
                            "description": (
                                "Código Mermaid completo e válido. Deve começar com o tipo do diagrama "
                                "(ex: 'flowchart LR', 'sequenceDiagram', 'classDiagram', 'stateDiagram-v2'). "
                                "Evite IDs com espaços ou caracteres especiais. "
                                "Para flowchart, use LR (esquerda→direita) por padrão."
                            ),
                        },
                        "title": {
                            "type": "string",
                            "description": "Título descritivo para exibir acima do diagrama (opcional).",
                        },
                    },
                    "required": ["mermaid_code"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "show_metrics",
                "description": (
                    "Exibe um painel visual de métricas/KPIs destacados no chat. "
                    "USE para apresentar números importantes de forma visual (totais, médias, contagens). "
                    "Máximo 4 métricas por chamada para boa legibilidade."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Título opcional do painel.",
                        },
                        "items": {
                            "type": "array",
                            "description": "Lista de métricas (máx 4).",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "label": {"type": "string", "description": "Nome da métrica."},
                                    "value": {"type": "string", "description": "Valor principal (ex: '144', '87%')."},
                                    "delta": {"type": "string", "description": "Variação opcional (ex: '+12 este mês'). Omita se não aplicável."},
                                },
                                "required": ["label", "value"],
                            },
                        },
                    },
                    "required": ["items"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "generate_ibis_map",
                "description": (
                    "Gera um Mapa Visual IBIS interativo (grafo Plotly) mostrando questões e alternativas "
                    "agrupados cronologicamente por reunião. "
                    "Nós laranjas = Issues/Questões; azuis = Alternativas; verde = Alternativa eleita. "
                    "Borda: verde=Decidida, âmbar=Adiada, vermelho=Em aberto. "
                    "SEMPRE use quando o usuário pedir 'mapa visual', 'mapa IBIS', 'grafo dos debates' "
                    "ou 'mostre visualmente' as questões debatidas."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {
                            "type": "string",
                            "description": "Tema ou palavra-chave para filtrar questões (opcional)",
                        },
                    },
                    "required": [],
                },
            },
        },
        # ── Plantonista / Diagnóstico ─────────────────────────────────────────
        {
            "type": "function",
            "function": {
                "name": "sugestoes_plantonista",
                "description": (
                    "Gera um briefing proativo do estado atual do projeto: reuniões sem ata, "
                    "contradições abertas, tópicos recorrentes sem resolução e encaminhamentos "
                    "pendentes — com sugestões de ação priorizadas. "
                    "Use quando o usuário pedir um resumo do projeto, 'o que está pendente', "
                    "'raio-x do projeto' ou quando não houver conversa ativa."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "diagnostico_projeto",
                "description": (
                    "Executa um checkup completo do projeto: integridade do banco (admin), "
                    "contradições abertas, reuniões sem ata, ROI-TR abaixo do limiar, "
                    "tópicos recorrentes e encaminhamentos pendentes. "
                    "Retorna relatório estruturado com itens críticos, alertas, situações OK "
                    "e ações recomendadas priorizadas. "
                    "Use quando o usuário pedir 'diagnóstico', 'checkup', 'saúde do projeto' "
                    "ou quiser um relatório completo de problemas e pendências."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "include_integrity": {
                            "type": "boolean",
                            "description": "Incluir verificação de integridade do banco (requer admin). Padrão: true.",
                        },
                        "include_contradictions": {
                            "type": "boolean",
                            "description": "Incluir contagem de contradições abertas no Knowledge Hub. Padrão: true.",
                        },
                        "include_roi": {
                            "type": "boolean",
                            "description": "Incluir análise de ROI-TR das reuniões. Padrão: true.",
                        },
                        "include_recurring": {
                            "type": "boolean",
                            "description": "Incluir detecção de tópicos recorrentes sem resolução. Padrão: true.",
                        },
                        "include_pendencies": {
                            "type": "boolean",
                            "description": "Incluir contagem de reuniões com encaminhamentos listados. Padrão: true.",
                        },
                    },
                    "required": [],
                },
            },
        },
        # ── Editor Estrutural (Fase 2) ─────────────────────────────────────────
        {
            "type": "function",
            "function": {
                "name": "reordenar_requisitos",
                "description": (
                    "Reordena os requisitos do projeto atualizando o campo sort_order. "
                    "Pode receber uma nova ordem explícita (lista de IDs como ['REQ-003','REQ-001']) "
                    "ou um critério de agrupamento ('tipo' ou 'prioridade'). "
                    "Use quando o usuário pedir para reorganizar, priorizar ou agrupar requisitos."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "nova_ordem": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Lista explícita de identificadores de requisitos na nova ordem "
                                "(ex: ['REQ-003','REQ-001','REQ-002']). "
                                "Mutuamente exclusivo com agrupar_por."
                            ),
                        },
                        "agrupar_por": {
                            "type": "string",
                            "enum": ["tipo", "prioridade"],
                            "description": (
                                "Reagrupa automaticamente todos os requisitos por tipo (Funcional → "
                                "Não Funcional → Regra de Negócio) ou por prioridade (Crítico → Alto → "
                                "Médio → Baixo). Mutuamente exclusivo com nova_ordem."
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
                "name": "inserir_secao_ata",
                "description": (
                    "Insere uma nova seção (## Título) na ata de uma reunião. "
                    "Posição pode ser 'inicio', 'fim', 'antes_decisoes', 'apos_participantes' "
                    "ou qualquer nome de seção existente prefixado com 'antes_' ou 'apos_'. "
                    "Use quando o usuário pedir para adicionar seção, acrescentar riscos, "
                    "inserir observações ou enriquecer uma ata existente."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "meeting_number": {
                            "type": "integer",
                            "description": "Número da reunião cuja ata será editada.",
                        },
                        "titulo": {
                            "type": "string",
                            "description": "Título da nova seção (sem ##, ex: 'Riscos Identificados').",
                        },
                        "conteudo": {
                            "type": "string",
                            "description": "Conteúdo Markdown da nova seção.",
                        },
                        "posicao": {
                            "type": "string",
                            "description": (
                                "Onde inserir: 'inicio', 'fim' (padrão), 'antes_decisoes', "
                                "'apos_participantes' ou qualquer 'antes_<nome>' / 'apos_<nome>'."
                            ),
                        },
                    },
                    "required": ["meeting_number", "titulo", "conteudo"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "vincular_regra_debate",
                "description": (
                    "Cria um vínculo entre uma regra SBVR e uma questão IBIS, registrando "
                    "a relação semântica entre elas (justifica, contradiz ou limita). "
                    "Use quando o usuário pedir para ligar uma regra a um debate, "
                    "vincular SBVR a IBIS ou documentar a justificativa de uma regra."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "rule_id": {
                            "type": "string",
                            "description": "Identificador da regra SBVR (ex: 'RN-012').",
                        },
                        "ibis_question_id": {
                            "type": "string",
                            "description": "Identificador da questão IBIS (ex: 'Q-042').",
                        },
                        "relacao": {
                            "type": "string",
                            "enum": ["justifica", "contradiz", "limita"],
                            "description": "Tipo de relação: justifica (padrão), contradiz ou limita.",
                        },
                    },
                    "required": ["rule_id", "ibis_question_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "mesclar_reunioes",
                "description": (
                    "Mescla duas reuniões: transfere todos os artefatos (requisitos, SBVR, BPMN, "
                    "transcrição, ata) da reunião absorvida para a reunião mantida, concatena as atas "
                    "e exclui a reunião absorvida. "
                    "Use preview=true para ver o impacto antes de confirmar. "
                    "Use quando o usuário pedir para unir, combinar ou mesclar duas reuniões."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "manter_meeting": {
                            "type": "integer",
                            "description": "Número da reunião que será mantida (destinatária dos artefatos).",
                        },
                        "absorver_meeting": {
                            "type": "integer",
                            "description": "Número da reunião que será absorvida e excluída.",
                        },
                        "razao": {
                            "type": "string",
                            "description": "Motivo da mesclagem (registrado na ata combinada).",
                        },
                        "preview": {
                            "type": "boolean",
                            "description": "Se true, retorna preview sem executar. Padrão: true (segurança).",
                        },
                    },
                    "required": ["manter_meeting", "absorver_meeting"],
                },
            },
        },
        # ── Fase 3: Rastreabilidade, What-If, Conformidade ────────────────────
        {
            "type": "function",
            "function": {
                "name": "mapa_rastreabilidade",
                "description": (
                    "Gera um mapa de rastreabilidade para um requisito ou tema, mostrando "
                    "as conexões com falas na transcrição, passos do BPMN, regras SBVR e "
                    "debates IBIS. Use quando o usuário pedir 'de onde veio esse requisito', "
                    "'qual parte da transcrição originou a regra X', 'rastreabilidade de REQ-042' "
                    "ou 'onde esse tema é discutido'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "req_number": {
                            "type": "integer",
                            "description": "Número do requisito (ex: 42 para REQ-042). Mutuamente exclusivo com topic.",
                        },
                        "topic": {
                            "type": "string",
                            "description": "Tema para busca por palavra-chave (ex: 'autenticação biométrica'). Mutuamente exclusivo com req_number.",
                        },
                        "include_transcript": {
                            "type": "boolean",
                            "description": "Incluir falas da transcrição. Padrão: true.",
                        },
                        "include_bpmn": {
                            "type": "boolean",
                            "description": "Incluir processos BPMN relacionados. Padrão: true.",
                        },
                        "include_sbvr": {
                            "type": "boolean",
                            "description": "Incluir regras SBVR relacionadas. Padrão: true.",
                        },
                        "include_ibis": {
                            "type": "boolean",
                            "description": "Incluir debates IBIS relacionados. Padrão: true.",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "simular_cenario",
                "description": (
                    "Simula o impacto de uma mudança de decisão ou escopo no projeto. "
                    "Analisa os requisitos afetados, dependências implícitas, regras SBVR a "
                    "revisar, riscos e retorna uma recomendação. "
                    "Use quando o usuário perguntar 'e se movermos X para Fase 2?', "
                    "'o que acontece se removermos REQ-042?', 'impacto de mudar Y', "
                    "'simule o cenário onde...' ou qualquer análise de mudança hipotética."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "descricao": {
                            "type": "string",
                            "description": "Descrição do cenário ou mudança proposta em linguagem natural.",
                        },
                        "requisitos_afetados": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Lista de IDs de requisitos afetados (ex: ['REQ-042','REQ-043']). Opcional — se omitido, o sistema infere pelos keywords.",
                        },
                        "restricoes": {
                            "type": "object",
                            "description": "Restrições do projeto como objeto JSON (ex: {\"prazo\": \"6 meses\", \"equipe\": \"4 devs\"}).",
                        },
                    },
                    "required": ["descricao"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "verificar_conformidade",
                "description": (
                    "Verifica se os requisitos do projeto estão cobertos pelos documentos da "
                    "biblioteca (BRDs, contratos, especificações). Retorna um relatório de "
                    "cobertura com gaps e ações recomendadas. "
                    "Use quando o usuário pedir 'nossos requisitos cobrem o BRD?', "
                    "'há gaps no contrato?', 'conformidade com documento X', "
                    "'quais cláusulas não estão mapeadas' ou análise de aderência."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "doc_id": {
                            "type": "string",
                            "description": "ID de um documento específico para analisar. Se omitido, analisa todos os documentos do projeto.",
                        },
                        "req_type_filter": {
                            "type": "string",
                            "description": "Filtrar por tipo de requisito: 'Funcional', 'Não Funcional' ou 'Regra de Negócio'.",
                        },
                        "threshold": {
                            "type": "number",
                            "description": "Limiar de similaridade para considerar coberto (0–1). Padrão: 0.75.",
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["keyword", "llm"],
                            "description": "Modo de análise: 'keyword' (rápido, padrão) ou 'llm' (LLM para cobertura semântica profunda).",
                        },
                    },
                    "required": [],
                },
            },
        },
        # ── Fase 4: Sugestor de Processos, Deck Executivo, Project Charter ──────
        {
            "type": "function",
            "function": {
                "name": "sugerir_processos",
                "description": (
                    "Analisa os debates IBIS e decisões das reuniões para identificar "
                    "temas recorrentes que podem originar novos processos BPMN. "
                    "Verifica se cada tema já está modelado, infere steps das decisões "
                    "e aponta regras SBVR associadas. "
                    "Use quando o usuário pedir 'que processos novos podemos mapear?', "
                    "'há processos não modelados?', 'quais temas se repetem nas reuniões?'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "min_reunioes": {
                            "type": "integer",
                            "description": "Mínimo de reuniões distintas em que o tema deve aparecer para ser sugerido. Padrão: 2.",
                        },
                        "confidence": {
                            "type": "number",
                            "description": "Limiar de sobreposição de keywords para agrupar questões no mesmo tema (0–1). Padrão: 0.7.",
                        },
                        "include_evidence": {
                            "type": "boolean",
                            "description": "Incluir citações das reuniões como evidência. Padrão: true.",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "gerar_deck_executivo",
                "description": (
                    "Gera um deck executivo completo (Markdown) consolidando todos os "
                    "artefatos do projeto: visão/missão (BMM), métricas, requisitos, "
                    "processos BPMN, ROI-TR, pendências e recomendações. "
                    "Use quando o usuário pedir 'gere uma apresentação', 'preciso de um "
                    "deck para o comitê', 'resumo executivo do projeto', 'prepare slides'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "incluir_secoes": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Seções a incluir. Padrão: todas. Opções: 'resumo_executivo', "
                                "'metricas_principais', 'evolucao_requisitos', 'processos_bpmn', "
                                "'indicadores_roi', 'pendencias', 'recomendacoes'."
                            ),
                        },
                        "meeting_numbers": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "description": "Reuniões a incluir. Padrão: todas.",
                        },
                        "tema_cores": {
                            "type": "string",
                            "enum": ["corporativo", "moderno", "clean"],
                            "description": "Estilo visual. Padrão: 'corporativo'.",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "gerar_project_charter",
                "description": (
                    "Gera um Project Charter formal em Markdown consolidando todos os "
                    "artefatos: visão, missão, stakeholders, escopo (requisitos), "
                    "processos BPMN, regras SBVR, riscos (contradições), cronograma "
                    "(datas das reuniões + encaminhamentos). "
                    "Use quando o usuário pedir 'gere o Project Charter', 'crie o documento "
                    "de abertura do projeto', 'preciso de um term of reference', 'PDD do projeto'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "incluir_riscos": {
                            "type": "boolean",
                            "description": "Incluir seção de riscos baseada em contradições abertas. Padrão: true.",
                        },
                        "incluir_cronograma": {
                            "type": "boolean",
                            "description": "Incluir cronograma inferido das datas de reunião e encaminhamentos. Padrão: true.",
                        },
                        "incluir_stakeholders": {
                            "type": "boolean",
                            "description": "Incluir seção de stakeholders extraídos das atas. Padrão: true.",
                        },
                        "incluir_escopo": {
                            "type": "boolean",
                            "description": "Incluir breakdown do escopo por tipo de requisito. Padrão: true.",
                        },
                    },
                    "required": [],
                },
            },
        },
        # ── Sincronizador Calendário (Fase 2) ─────────────────────────────────
        {
            "type": "function",
            "function": {
                "name": "sincronizar_calendario",
                "description": (
                    "Sincroniza os encaminhamentos (itens de ação) das atas com o Google Calendar. "
                    "Direção 'to_calendar': cria eventos para cada encaminhamento sem evento. "
                    "Direção 'from_calendar': atualiza status dos itens já sincronizados. "
                    "Direção 'bidirectional': ambas. "
                    "Use quando o usuário pedir para agendar tarefas, sincronizar calendário "
                    "ou criar eventos a partir dos encaminhamentos das reuniões."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "direction": {
                            "type": "string",
                            "enum": ["to_calendar", "from_calendar", "bidirectional"],
                            "description": "Direção da sincronização. Padrão: 'to_calendar'.",
                        },
                        "meeting_number": {
                            "type": "integer",
                            "description": "Reunião específica (opcional — padrão: todas as reuniões).",
                        },
                        "default_duration": {
                            "type": "integer",
                            "description": "Duração em minutos para cada evento criado. Padrão: 30.",
                        },
                        "default_work_start": {
                            "type": "string",
                            "description": "Horário de início da janela de trabalho no formato HH:MM. Padrão: '09:00'.",
                        },
                        "default_work_end": {
                            "type": "string",
                            "description": "Horário de fim da janela de trabalho no formato HH:MM. Padrão: '18:00'.",
                        },
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


# ── Tool catalog metadata (for UI display) ────────────────────────────────────

_TOOL_CATEGORIES: dict[str, str] = {
    # Consulta (read-only)
    "get_meeting_list":             "consulta",
    "get_meeting_participants":     "consulta",
    "get_meeting_decisions":        "consulta",
    "get_meeting_action_items":     "consulta",
    "get_meeting_summary":          "consulta",
    "compare_meeting_transcripts":  "consulta",
    "show_meeting_transcript":      "consulta",
    "search_transcript":            "consulta",
    "count_artifacts":              "consulta",
    "get_requirements":             "consulta",
    "get_bpmn_execution_log":       "consulta",
    "list_bpmn_processes":          "consulta",
    "review_bpmn_diagram":          "consulta",
    "describe_bpmn_process":        "consulta",
    "suggest_bpmn_corrections":     "consulta",
    "save_bpmn_revision":           "admin",
    "apply_bpmn_corrections":       "admin",
    "list_bpmn_versions":           "consulta",
    "delete_bpmn_version":          "admin",
    "get_sbvr_terms":               "consulta",
    "get_sbvr_rules":               "consulta",
    "list_context_files":           "consulta",
    "calculate_meeting_roi":        "consulta",
    "get_recurring_topics":         "consulta",
    "get_meeting_metadata":         "consulta",
    "preview_meeting_deletion":     "consulta",
    "preview_text_correction":      "consulta",
    "get_speaker_contributions":    "consulta",
    "get_system_capabilities":          "consulta",
    "get_executive_report":         "consulta",    
    "get_users_by_domain":   "consulta",
    "list_all_domains":      "consulta",
    "list_users_by_project": "consulta",
    "set_active_project":    "escrita",
    "rename_meeting":        "escrita",
    "save_context_skill":    "escrita",

    "convert_usd_to_brl": "consulta",
    
    "calendar_diagnose":                "admin",
    # Google Calendar
    "calendar_list_events":             "consulta",
    "calendar_get_event":               "consulta",
    "calendar_suggest_time":            "consulta",
    "calendar_create_event":            "admin",
    "calendar_schedule_action_items":   "admin",
    "calendar_share_with_user":         "admin",
    "calendar_revoke_access":           "admin",
    # Escrita / Modificação
    "add_sbvr_term":                "escrita",
    "update_sbvr_term":             "escrita",
    "update_sbvr_term_by_id":       "escrita",
    "add_sbvr_rule":                "escrita",
    "update_sbvr_rule":             "escrita",
    "update_requirement_status":    "escrita",
    "update_requirement_text":      "escrita",
    # Admin — escrita privilegiada
    "apply_text_correction":        "admin",
    "rename_meeting":               "admin",
    "batch_rename_meetings":        "admin",
    "delete_meeting":               "admin",
    "delete_project_artifacts":     "admin",
    "fix_missing_llm_provider":     "admin",
    "generate_meeting_embeddings":  "admin",
    "embed_meeting":                "admin",
    "get_database_integrity":       "admin",
    # Geração (LLM-powered) — admin
    "generate_missing_minutes":           "admin",
    "reprocess_meeting_requirements":     "admin",
    "reprocess_communication_noise":      "admin",
    "reprocess_meeting_full":         "admin",
    "reprocess_communication_noise":  "admin",
    "regenerate_executive_report":    "admin",
    "batch_reprocess_requirements":   "admin",
    # Gráficos
    "generate_requirements_chart":    "grafico",
    "generate_meetings_timeline":     "grafico",
    "generate_action_items_chart":    "grafico",
    "generate_roi_chart":             "grafico",
    "generate_custom_chart":          "grafico",
    "render_table":                   "consulta",
    "populate_roster":                 "admin",
    "populate_knowledge_hub":          "admin",
    "detect_contradictions":           "admin",
    "resolve_entity_ambiguity":        "admin",
    "lookup_entity":                   "consulta",
    "delete_entity":                   "admin",
    "get_cache_stats":                 "consulta",
    "clear_llm_cache":                 "admin",
    # Documentos
    "list_meeting_documents":          "consulta",
    "get_document_content":            "consulta",
    "search_documents":                "consulta",
    "get_document_types":              "consulta",
    "suggest_document_title":          "escrita",
    # Ajuda P2D
    "get_p2d_help":                    "consulta",
    # Histórico de requisitos
    "get_requirement_history":         "consulta",
    # BMM / CKF
    "get_bmm":                         "consulta",
    "get_ckf":                         "consulta",
    # Knowledge Graph
    "list_kh_entities":                "consulta",
    "list_kh_contradictions":          "consulta",
    "resolve_contradiction":           "escrita",
    "delete_contradiction":            "escrita",
    "list_kh_facts":                   "consulta",
    # Glossário / Skills
    "search_glossary":                 "consulta",
    "read_skill_reference":            "consulta",
    # IBIS / Argumentação
    "search_ibis_debates":             "consulta",
    "get_ibis_timeline":               "grafico",
    "generate_ibis_map":               "grafico",
    # Cross-meeting / agenda
    "generate_next_agenda":            "consulta",
    "cluster_topic_decisions":         "consulta",
    # Plantonista / Diagnóstico
    "sugestoes_plantonista":           "consulta",
    "diagnostico_projeto":             "consulta",
    # Rastreabilidade / Simulação / Conformidade (Fase 3)
    "mapa_rastreabilidade":            "consulta",
    "simular_cenario":                 "consulta",
    "verificar_conformidade":          "consulta",
    # Sugestor / Deck / Charter (Fase 4)
    "sugerir_processos":               "consulta",
    "gerar_deck_executivo":            "consulta",
    "gerar_project_charter":           "consulta",
    # Editor Estrutural (Fase 2)
    "reordenar_requisitos":            "escrita",
    "inserir_secao_ata":               "admin",
    "vincular_regra_debate":           "escrita",
    "mesclar_reunioes":                "admin",
    # Sincronizador Calendário (Fase 2)
    "sincronizar_calendario":          "admin",
    # A2UI
    "show_bpmn_diagram":               "consulta",
    "show_mermaid_diagram":            "consulta",
    "render_mermaid_code":             "consulta",
    "show_metrics":                    "consulta",
}

# Ferramentas que exigem perfil administrador
_ADMIN_TOOLS: frozenset[str] = frozenset({
    "get_database_integrity",
    "fix_missing_llm_provider",
    "generate_meeting_embeddings",
    "embed_meeting",
    "delete_meeting",
    "delete_project_artifacts",
    "rename_meeting",
    "batch_rename_meetings",
    "apply_text_correction",
    "reprocess_meeting_requirements",
    "reprocess_meeting_full",
    "reprocess_communication_noise",
    "regenerate_executive_report",
    "batch_reprocess_requirements",
    "generate_missing_minutes",
    "calendar_create_event",
    "calendar_schedule_action_items",
    "calendar_share_with_user",
    "calendar_revoke_access",
    "calendar_diagnose",
    "populate_roster",
    "populate_knowledge_hub",
    "detect_contradictions",
    "resolve_entity_ambiguity",
    "delete_entity",
    "delete_bpmn_version",
    "save_bpmn_revision",
    "apply_bpmn_corrections",
    "clear_llm_cache",
    "inserir_secao_ata",
    "mesclar_reunioes",
    "sincronizar_calendario",
})


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
        self.llm_config = llm_config or {}   # {"api_key", "model", "provider_cfg", "chart_palette"}
        self._meeting_cache: list[dict] | None = None
        self._pending_charts: list[dict] = []  # Plotly figure dicts accumulated during a turn
        palette_name = self.llm_config.get("chart_palette", DEFAULT_PALETTE)
        self._palette: list[str] = CHART_PALETTES.get(palette_name, CHART_PALETTES[DEFAULT_PALETTE])

    def get_pending_charts(self) -> list[dict]:
        """Return Plotly figure dicts accumulated by chart tools during this turn."""
        return list(self._pending_charts)
        
    def convert_usd_to_brl(self, usd_amount: float) -> str:
        """Converte USD para BRL usando cotação em tempo real da AwesomeAPI."""
        try:
            from modules.cost_estimator import get_usd_brl_rate
            rate, from_cache = get_usd_brl_rate()
            brl_amount = usd_amount * rate
            cache_label = "cache" if from_cache else "atualizada agora"
            return (
                f"💱 **Conversão USD → BRL**\n\n"
                f"- Valor em USD: **$ {usd_amount:,.4f}**\n"
                f"- Cotação atual: **R$ {rate:.4f}** ({cache_label})\n"
                f"- Valor em BRL: **R$ {brl_amount:,.2f}**\n\n"
                f"_Fonte: AwesomeAPI (economia.awesomeapi.com.br)_"
            )
        except Exception as exc:
            return f"Erro ao obter cotação: {exc}"        

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
        
    def update_requirement_status(
        self,
        new_status: str,
        req_numbers: list[int] | None = None,
        filter_req_type: str | None = None,
        filter_current_status: str | None = None,
        filter_meeting_number: int | None = None,
        status_note: str | None = None,
    ) -> str:
        """Atualiza status de requisitos com filtros opcionais e registra versão."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        valid_statuses = {"active", "revised", "contradicted", "confirmed"}
        if new_status not in valid_statuses:
            return f"❌ Status inválido: '{new_status}'. Use: {', '.join(sorted(valid_statuses))}."

        # ── Buscar requisitos candidatos ──────────────────────────────────────────
        try:
            q = (
                db.table("requirements")
                .select("id, req_number, title, req_type, status, first_meeting_id")
                .eq("project_id", self.project_id)
            )
            if filter_req_type:
                q = q.eq("req_type", filter_req_type)
            if filter_current_status:
                q = q.eq("status", filter_current_status)
            rows = q.order("req_number").execute().data or []
        except Exception as exc:
            return f"❌ Erro ao buscar requisitos: {exc}"

        # Filtro por números de requisito
        if req_numbers:
            rows = [r for r in rows if r.get("req_number") in req_numbers]

        # Filtro por reunião de origem
        if filter_meeting_number is not None:
            # Resolve meeting_number → meeting_id
            meeting = self._find_meeting(filter_meeting_number)
            if not meeting:
                return f"❌ Reunião {filter_meeting_number} não encontrada."
            target_mid = meeting["id"]
            rows = [r for r in rows if r.get("first_meeting_id") == target_mid]

        if not rows:
            return "Nenhum requisito encontrado com os filtros fornecidos."

        # ── Preview antes de aplicar ──────────────────────────────────────────────
        # Se muitos requisitos seriam afetados, lista para confirmação
        if len(rows) > 10:
            preview = "\n".join(
                f"  REQ-{r['req_number']:03d}: {r['title'][:60]} [{r['status']} → {new_status}]"
                for r in rows[:5]
            )
            return (
                f"⚠️ {len(rows)} requisitos seriam atualizados para '{new_status}'.\n"
                f"Primeiros 5:\n{preview}\n  ... e mais {len(rows) - 5}\n\n"
                f"Confirme explicitamente: 'sim, atualize todos' ou refine os filtros."
            )

        # ── Aplicar atualização ───────────────────────────────────────────────────
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()

        updated: list[str] = []
        errors:  list[str] = []

        for r in rows:
            rid        = r["id"]
            req_number = r.get("req_number")
            req_id     = f"REQ-{req_number:03d}" if isinstance(req_number, int) else "REQ-???"
            old_status = r.get("status") or "active"

            if old_status == new_status:
                updated.append(f"  {req_id}: já estava '{new_status}' — sem alteração")
                continue

            # Atualiza requirements
            patch: dict = {
                "status":     new_status,
                "updated_at": now_iso,
            }
            if status_note:
                patch["status_note"] = status_note

            try:
                db.table("requirements").update(patch).eq("id", rid).execute()
            except Exception as exc:
                errors.append(f"  {req_id}: ❌ {exc}")
                continue

            # Registra versão em requirement_versions
            try:
                # Pega a última versão para incrementar
                ver_rows = (
                    db.table("requirement_versions")
                    .select("version")
                    .eq("requirement_id", rid)
                    .order("version", desc=True)
                    .limit(1)
                    .execute().data or []
                )
                next_ver = (ver_rows[0]["version"] + 1) if ver_rows else 1

                # Usa o first_meeting_id como meeting_id de referência
                ver_payload = {
                    "requirement_id": rid,
                    "meeting_id":     r.get("first_meeting_id"),
                    "version":        next_ver,
                    "title":          r.get("title", ""),
                    "description":    None,
                    "req_type":       r.get("req_type"),
                    "priority":       None,
                    "change_type":    "status_change",
                    "change_summary": (
                        f"Status: {old_status} → {new_status}"
                        + (f". {status_note}" if status_note else "")
                    ),
                }
                db.table("requirement_versions").insert(ver_payload).execute()
            except Exception:
                pass  # versão falhou mas o status foi atualizado — não bloqueia

            updated.append(f"  {req_id}: {old_status} → **{new_status}**")

        # ── Resultado ─────────────────────────────────────────────────────────────
        lines = [
            f"**Atualização de Status → `{new_status}`**",
            f"{len([u for u in updated if '→' in u])} requisito(s) atualizado(s):",
            "",
        ]
        lines.extend(updated)
        if errors:
            lines.append(f"\n❌ {len(errors)} erro(s):")
            lines.extend(errors)
        if status_note:
            lines.append(f"\n📝 Nota registrada: *{status_note}*")
        return "\n".join(lines)

    def update_requirement_text(
        self,
        req_number: int,
        new_description: str | None = None,
        new_title: str | None = None,
        change_note: str | None = None,
    ) -> str:
        """Atualiza título e/ou descrição de um requisito específico, com versionamento."""
        from modules.supabase_client import get_supabase_client
        from datetime import datetime, timezone
        db = get_supabase_client()
        if not db:
            return "❌ Supabase não configurado."
        if not new_description and not new_title:
            return "❌ Informe new_description e/ou new_title para atualizar."

        try:
            rows = (
                db.table("requirements")
                .select("id, req_number, title, description, status, first_meeting_id")
                .eq("project_id", self.project_id)
                .eq("req_number", req_number)
                .execute().data or []
            )
        except Exception as exc:
            return f"❌ Erro ao buscar REQ-{req_number:03d}: {exc}"

        if not rows:
            return f"❌ REQ-{req_number:03d} não encontrado no projeto."

        row = rows[0]
        rid = row["id"]
        patch: dict = {}
        if new_title:
            patch["title"] = new_title.strip()
        if new_description:
            patch["description"] = new_description.strip()

        try:
            db.table("requirements").update(patch).eq("id", rid).execute()
        except Exception as exc:
            return f"❌ Erro ao atualizar REQ-{req_number:03d}: {exc}"

        # Registrar versão
        try:
            ver_rows = (
                db.table("requirement_versions")
                .select("version")
                .eq("requirement_id", rid)
                .order("version", desc=True)
                .limit(1)
                .execute().data or []
            )
            next_ver = (ver_rows[0]["version"] + 1) if ver_rows else 1
            ver_payload = {
                "requirement_id": rid,
                "meeting_id":     row.get("first_meeting_id"),
                "version":        next_ver,
                "title":          patch.get("title", row.get("title", "")),
                "description":    patch.get("description", row.get("description")),
                "status":         row.get("status", "active"),
                "change_type":    "text_edit",
                "changed_at":     datetime.now(timezone.utc).isoformat(),
                "change_note":    change_note or "Texto atualizado via Assistente",
            }
            db.table("requirement_versions").insert(ver_payload).execute()
        except Exception:
            pass  # versionamento é best-effort

        fields = (["título"] if new_title else []) + (["descrição"] if new_description else [])
        return (
            f"✅ REQ-{req_number:03d} atualizado com sucesso!\n"
            f"• Campos alterados: {', '.join(fields)}"
            + (f"\n• Novo título: {new_title}" if new_title else "")
            + (f"\n• Nova descrição: {(new_description or '')[:200]}" if new_description else "")
            + (f"\n• Nota: {change_note}" if change_note else "")
        )

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

    def get_cache_stats(self, agent_name: str | None = None) -> str:
        """Return LLM semantic cache statistics as a formatted Markdown string."""
        try:
            from services.semantic_cache import _cache
            stats = _cache.get_stats(agent_name=agent_name or None)
        except Exception as exc:
            return f"⚠️ Não foi possível consultar o cache: {exc}"

        if stats["total_entries"] == 0:
            scope = f" (agente `{agent_name}`)" if agent_name else ""
            return (
                f"O cache LLM{scope} ainda está vazio. "
                "Ele será preenchido automaticamente após a primeira execução do pipeline."
            )

        cost = stats["total_tokens_saved"] / 1_000_000 * 0.27
        hit_ratio = (
            stats["total_hits"] / (stats["total_hits"] + stats["total_entries"])
            if stats["total_entries"] > 0 else 0.0
        )

        lines = [
            "## 💾 Cache Semântico de LLM\n",
            f"| Métrica | Valor |",
            f"|:---|:---|",
            f"| Entradas em cache | {stats['total_entries']} |",
            f"| Cache hits totais | {stats['total_hits']} |",
            f"| Tokens economizados | {stats['total_tokens_saved']:,} |",
            f"| Economia estimada | ~${cost:.4f} USD |",
            f"| Hit ratio | {hit_ratio:.1%} |",
            "",
        ]

        if stats["by_agent"]:
            lines += ["### Por agente\n", "| Agente | Entradas | Hits | Tokens economizados | Economia USD |",
                      "|:---|---:|---:|---:|---:|"]
            for row in stats["by_agent"]:
                agent_cost = row["tokens_saved"] / 1_000_000 * 0.27
                lines.append(
                    f"| `{row['agent']}` | {row['entries']} | {row['hits']} "
                    f"| {row['tokens_saved']:,} | ${agent_cost:.4f} |"
                )
            lines.append("")

        lines.append(
            "_Cache armazena respostas LLM pré-desanitize (PII-safe). "
            "TTL padrão: 30 dias. Veja detalhes em Qualidade ROI-TR → 💾 Cache LLM._"
        )
        return "\n".join(lines)

    def clear_llm_cache(self, agent_name: str | None = None) -> str:
        """Invalidate LLM cache entries (admin only). Returns confirmation."""
        try:
            from services.semantic_cache import _cache
            _cache.invalidate(agent_name=agent_name or None)
            scope = f"do agente `{agent_name}`" if agent_name else "completo"
            return f"✅ Cache LLM {scope} invalidado com sucesso."
        except Exception as exc:
            return f"❌ Erro ao invalidar cache: {exc}"

    def get_system_capabilities(self) -> str:
        """Return a description of all P2D capabilities, built dynamically from Agent Cards."""
        from modules.calendar_client import calendar_configured
        from core.agent_registry import get_agent_cards
        cal_status = "✅ configurado" if calendar_configured() else "⚙️ não configurado neste ambiente"

        # Build agent section from Agent Cards
        cards = get_agent_cards()
        _phase_labels = {
            "pre": "Pré-pipeline",
            "core": "Core (pipeline principal)",
            "enrichment": "Enriquecimento",
            "output": "Saída",
            "post": "Pós-pipeline",
            "on_demand": "Sob demanda",
        }
        agents_by_phase: dict[str, list[dict]] = {}
        for card in cards:
            phase = card.get("pipeline_phase", "core")
            agents_by_phase.setdefault(phase, []).append(card)

        agent_lines = ["## Agentes especializados (Agent Cards)\n"]
        for phase_key, label in _phase_labels.items():
            phase_cards = agents_by_phase.get(phase_key, [])
            if not phase_cards:
                continue
            agent_lines.append(f"### {label}")
            for card in phase_cards:
                name = card.get("display_name", card.get("name", ""))
                desc = card.get("description", "")
                mode = card.get("mode", "llm")
                fatal = card.get("fatal", True)
                fatal_tag = "" if fatal else " · não-fatal"
                arts = card.get("artifacts") or []
                art_str = "; ".join(arts[:2])
                if len(arts) > 2:
                    art_str += f" (+{len(arts)-2})"
                agent_lines.append(f"  • **{name}** [{mode}{fatal_tag}] — {desc}")
                if art_str:
                    agent_lines.append(f"    Artefatos: {art_str}")
            agent_lines.append("")

        agents_section = "\n".join(agent_lines)

        return f"""\
=== Funcionalidades do Process2Diagram (P2D) ===

{agents_section}
## Persistência (Supabase)
  • Projetos, reuniões, requisitos, BPMN, SBVR, embeddings vetoriais
  • Busca semântica nas transcrições via pgvector (512 dims — Matryoshka `vector(512)`)
  • Grafo de Conhecimento (kh_entities, kh_facts, kh_contradictions)

## Ferramentas do Assistente (este chat)
  Consulta (todos os perfis):
    get_meeting_list, get_meeting_participants, get_meeting_decisions,
    get_meeting_action_items, get_meeting_summary, search_transcript,
    get_requirements, get_bpmn_execution_log, list_bpmn_processes, list_bpmn_versions, get_sbvr_terms, get_sbvr_rules,
    list_context_files, calculate_meeting_roi, get_recurring_topics, get_meeting_metadata,
    preview_meeting_deletion, preview_text_correction, get_speaker_contributions,
    get_requirement_history, get_bmm, get_ckf,
    list_kh_entities, list_kh_contradictions, resolve_contradiction, delete_contradiction, list_kh_facts,
    search_ibis_debates, get_ibis_timeline, generate_ibis_map, search_glossary,
    generate_next_agenda, cluster_topic_decisions, read_skill_reference,
    show_bpmn_diagram, show_mermaid_diagram, show_metrics

  Escrita (todos os perfis):
    add_sbvr_term, update_sbvr_term, update_sbvr_term_by_id, add_sbvr_rule, update_sbvr_rule,
    update_requirement_text

  Admin (perfil admin/master):
    apply_text_correction, rename_meeting, delete_meeting, delete_project_artifacts,
    reprocess_meeting_requirements, reprocess_meeting_full, batch_reprocess_requirements,
    generate_missing_minutes, get_database_integrity, fix_missing_llm_provider,
    embed_meeting (reunião única), generate_meeting_embeddings (em lote),
    delete_bpmn_version (exclui versão específica de diagrama BPMN),
    reprocess_communication_noise

## Integração Google Calendar ({cal_status})
  Consulta (todos os perfis):
    calendar_list_events          — lista próximos eventos da agenda do projeto
    calendar_get_event            — detalhes de um evento pelo ID
    calendar_suggest_time         — horários livres via API freebusy

  Admin (perfil admin/master):
    calendar_create_event         — cria evento (título, horário, local, participantes)
    calendar_schedule_action_items — cria eventos para cada item de ação de uma reunião

  Configuração: credenciais via st.secrets[google_calendar][credentials_json] + [calendar_id].

## Outras páginas
  • BpmnEditor       — editor visual BPMN com histórico de versões
  • Artefatos        — central de artefatos: requisitos, SBVR, BMM, DMN, IBIS, Ruídos, rastreabilidade
  • KnowledgeGraph   — grafo de conhecimento interativo (entidades, fatos, contradições)
  • MeetingROI       — dashboard ROI-TR por tipo de reunião
  • DocumentManager  — gestão de documentos com extração de artefatos e análise cruzada
  • DatabaseOverview — saúde do banco + gestão de embeddings
  • BatchRunner      — processamento em lote de múltiplas transcrições

## Provedores LLM suportados
  DeepSeek V4 Flash (padrão), DeepSeek V4 Pro, Claude (Anthropic), OpenAI,
  Groq (Llama), Google Gemini, Grok (xAI)
"""

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
        meeting_number: int | None = None,
        page: int = 1,
        page_size: int = 50,
        count_only: bool = False,
    ) -> str:
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        # ── count_only legado: redireciona para count_artifacts ──────────────
        if count_only and not keyword:
            return self._count_artifacts(artifact_type="requirements",
                                         req_type=req_type, status=status)

        # Clamp page_size
        page_size = max(1, min(int(page_size or 50), 100))
        page      = max(1, int(page or 1))

        # ── Resolve meeting_number → meeting_id (UUID) ────────────────────────
        meeting_id_filter: str | None = None
        meeting_title_hint: str = ""
        if meeting_number:
            try:
                m_rows = (
                    db.table("meetings")
                    .select("id, title")
                    .eq("project_id", self.project_id)
                    .eq("meeting_number", int(meeting_number))
                    .limit(1)
                    .execute()
                )
                if m_rows.data:
                    meeting_id_filter = m_rows.data[0]["id"]
                    meeting_title_hint = m_rows.data[0].get("title") or ""
                else:
                    return f"Reunião {meeting_number} não encontrada no projeto."
            except Exception as exc:
                return f"Erro ao buscar reunião {meeting_number}: {exc}"

        if keyword:
            # Keyword filtering must be client-side — fetch all matching rows
            # (keyword searches are typically narrow, so volume is manageable)
            try:
                q = (
                    db.table("requirements")
                    .select(
                        "req_number, title, description, req_type, status, priority, "
                        "source_quote, cited_by",
                        count="exact",
                    )
                    .eq("project_id", self.project_id)
                    .order("req_number")
                )
                if req_type:
                    q = q.eq("req_type", req_type)
                if status:
                    q = q.eq("status", status)
                if meeting_id_filter:
                    q = q.eq("first_meeting_id", meeting_id_filter)
                result = q.execute()
                all_rows = result.data or []
            except Exception as exc:
                return f"Erro ao acessar requisitos: {exc}"

            kw      = keyword.lower().strip()
            _kw_num = kw.replace("req-", "").replace("req ", "").strip()
            _kw_is_num = _kw_num.isdigit()
            rows = [
                r for r in all_rows
                if kw in (r.get("title") or "").lower()
                or kw in (r.get("description") or "").lower()
                or kw in (r.get("cited_by") or "").lower()
                or (_kw_is_num and (
                    int(_kw_num) == r.get("req_number")
                    or _kw_num == str(r.get("req_number"))
                ))
            ]
            total = len(rows)
            # Still paginate the filtered result
            start = (page - 1) * page_size
            rows  = rows[start: start + page_size]
        else:
            # Server-side pagination via .range()
            start = (page - 1) * page_size
            end   = start + page_size - 1
            try:
                q = (
                    db.table("requirements")
                    .select(
                        "req_number, title, description, req_type, status, priority, "
                        "source_quote, cited_by",
                        count="exact",
                    )
                    .eq("project_id", self.project_id)
                    .order("req_number")
                    .range(start, end)
                )
                if req_type:
                    q = q.eq("req_type", req_type)
                if status:
                    q = q.eq("status", status)
                if meeting_id_filter:
                    q = q.eq("first_meeting_id", meeting_id_filter)
                result = q.execute()
                rows  = result.data or []
                total = result.count if result.count is not None else len(rows)
            except Exception as exc:
                return f"Erro ao acessar requisitos: {exc}"

        if not rows:
            hint = f" da Reunião {meeting_number}" if meeting_number else ""
            return f"Nenhum requisito encontrado{hint} com os filtros fornecidos."

        total_pages = max(1, -(-total // page_size))  # ceiling division
        meeting_ctx = f" — Reunião {meeting_number}" + (f" ({meeting_title_hint})" if meeting_title_hint else "") if meeting_number else ""
        header = f"Requisitos{meeting_ctx} (página {page}/{total_pages} · {len(rows)} de {total} no total):"
        lines  = [header]

        for r in rows:
            n       = r.get("req_number")
            req_id  = f"REQ-{n:03d}" if isinstance(n, int) else "REQ-???"
            rtype   = r.get("req_type") or "—"
            rstatus = r.get("status") or "—"
            rprio   = r.get("priority") or "—"
            title   = r.get("title") or ""
            desc    = (r.get("description") or "")[:200]
            if len(r.get("description") or "") > 200:
                desc += "..."
            cited   = r.get("cited_by") or ""
            quote   = r.get("source_quote") or ""
            lines.append(f"• {req_id} [{rtype} | {rstatus} | prioridade: {rprio}]: {title}")
            if desc:
                lines.append(f"  {desc}")
            if cited or quote:
                attr = f"[{cited}] " if cited else ""
                if quote:
                    lines.append(f'  > {attr}"{quote}"')
                elif cited:
                    lines.append(f"  Autor: {cited}")

        if page < total_pages:
            lines.append(
                f"\n[Há mais requisitos. Chame get_requirements(page={page + 1}) para continuar.]"
            )

        return "\n".join(lines)

    def _count_artifacts(
        self,
        artifact_type: str = "all",
        req_type: str | None = None,
        status: str | None = None,
    ) -> str:
        """
        SELECT COUNT(*) para cada tipo de artefato — resposta exata, sem truncamento.
        """
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        def _count(table: str, filters: list[tuple[str, str]]) -> int:
            """Return COUNT(*) for a table with optional eq filters."""
            try:
                q = db.table(table).select("*", count="exact").limit(0)
                for col, val in filters:
                    q = q.eq(col, val)
                r = q.execute()
                return r.count if r.count is not None else 0
            except Exception:
                return -1  # table may not exist (e.g. KH tables not migrated yet)

        pid = self.project_id
        art = (artifact_type or "all").strip().lower()

        # ── Single-type queries ────────────────────────────────────────────────
        if art == "requirements":
            f = [("project_id", pid)]
            if req_type:
                f.append(("req_type", req_type))
            if status:
                f.append(("status", status))
            n = _count("requirements", f)
            parts = []
            if req_type:
                parts.append(f"tipo: {req_type}")
            if status:
                parts.append(f"status: {status}")
            desc = f" ({', '.join(parts)})" if parts else ""
            return f"Requisitos{desc}: **{n}**"

        if art == "sbvr_terms":
            n = _count("sbvr_terms", [("project_id", pid)])
            return f"Termos SBVR: **{n}**"

        if art == "sbvr_rules":
            n = _count("sbvr_rules", [("project_id", pid)])
            return f"Regras SBVR: **{n}**"

        if art == "bpmn_processes":
            n = _count("bpmn_processes", [("project_id", pid)])
            return f"Processos BPMN: **{n}**"

        if art == "bpmn_versions":
            # versions join through processes — count via processes first then versions
            try:
                proc_ids_result = (
                    db.table("bpmn_processes")
                    .select("id")
                    .eq("project_id", pid)
                    .execute()
                )
                proc_ids = [r["id"] for r in (proc_ids_result.data or [])]
                if not proc_ids:
                    return "Versões BPMN: **0**"
                r = (
                    db.table("bpmn_versions")
                    .select("*", count="exact")
                    .in_("process_id", proc_ids)
                    .limit(0)
                    .execute()
                )
                n = r.count if r.count is not None else 0
                return f"Versões BPMN: **{n}**"
            except Exception as exc:
                return f"Erro ao contar versões BPMN: {exc}"

        if art == "meetings":
            n = _count("meetings", [("project_id", pid)])
            return f"Reuniões: **{n}**"

        if art == "kh_facts":
            n = _count("kh_facts", [("project_id", pid)])
            n_active = _count("kh_facts", [("project_id", pid), ("is_active", True)])
            if n < 0:
                return "Fatos KH: tabelas do Knowledge Hub ainda não criadas."
            return f"Fatos (Knowledge Hub): **{n}** total · **{n_active}** ativos"

        if art == "kh_entities":
            n = _count("kh_entities", [("project_id", pid)])
            if n < 0:
                return "Entidades KH: tabelas do Knowledge Hub ainda não criadas."
            return f"Entidades (Knowledge Hub): **{n}**"

        if art == "kh_contradictions":
            f = [("project_id", pid)]
            if status:
                f.append(("status", status))
            n = _count("kh_contradictions", f)
            if n < 0:
                return "Contradições KH: tabelas do Knowledge Hub ainda não criadas."
            desc = f" (status: {status})" if status else ""
            return f"Contradições (Knowledge Hub){desc}: **{n}**"

        # ── artifact_type == "all": painel completo ────────────────────────────
        lines = [f"## Painel de Artefatos — Projeto"]

        # Meetings
        n_mtg = _count("meetings", [("project_id", pid)])
        lines.append(f"📅 **Reuniões:** {n_mtg}")

        # Requirements breakdown by type
        req_types = ["funcional", "não-funcional", "regra de negócio", "restrição", "interface"]
        n_req_total = _count("requirements", [("project_id", pid)])
        if n_req_total > 0:
            by_type_parts = []
            for rt in req_types:
                c = _count("requirements", [("project_id", pid), ("req_type", rt)])
                if c > 0:
                    by_type_parts.append(f"{rt}: {c}")
            by_type_str = " · ".join(by_type_parts) if by_type_parts else ""
            lines.append(f"📋 **Requisitos:** {n_req_total}" +
                         (f" ({by_type_str})" if by_type_str else ""))
        else:
            lines.append(f"📋 **Requisitos:** {n_req_total}")

        # BPMN
        n_proc = _count("bpmn_processes", [("project_id", pid)])
        lines.append(f"📐 **Processos BPMN:** {n_proc}")

        # SBVR
        n_terms = _count("sbvr_terms", [("project_id", pid)])
        n_rules = _count("sbvr_rules", [("project_id", pid)])
        lines.append(f"📖 **Vocabulário SBVR:** {n_terms} termos · {n_rules} regras")

        # Knowledge Hub (may not exist)
        n_facts    = _count("kh_facts",         [("project_id", pid)])
        n_entities = _count("kh_entities",       [("project_id", pid)])
        n_contras  = _count("kh_contradictions", [("project_id", pid)])
        if n_facts >= 0:
            n_active = _count("kh_facts", [("project_id", pid), ("is_active", True)])
            n_open   = _count("kh_contradictions", [("project_id", pid), ("status", "open")])
            lines.append(
                f"🧠 **Knowledge Hub:** {n_entities} entidades · "
                f"{n_active}/{n_facts} fatos ativos · "
                f"{n_open} contradições abertas"
            )

        return "\n".join(lines)

    def get_bpmn_execution_log(self) -> str:
        """Return the execution log from the most recent BPMN agent run in the current session."""
        try:
            import streamlit as st
            hub = st.session_state.get("hub")
        except Exception:
            hub = None
        if hub is None or not getattr(hub, "bpmn", None):
            return "Hub não disponível. Execute o pipeline primeiro."
        if not hub.bpmn.ready:
            return "Agente BPMN ainda não foi executado nesta sessão."
        log = getattr(hub.bpmn, "execution_log", None)
        if not log:
            return (
                "Log de execução não disponível. "
                "Reexecute o agente BPMN para gerar o log (disponível a partir do próximo run)."
            )
        import json as _json
        source_label = {"llm_call": "Chamada LLM", "fast_path_rerun": "Fast-path (sem LLM)"}.get(
            log.get("source", ""), log.get("source", "—")
        )
        lines = [
            f"## Log de Execução BPMN",
            f"**Gerado em:** {log.get('generated_at', '—')}",
            f"**Fonte:** {source_label}",
        ]
        llm = log.get("llm")
        if llm:
            cache_str = f"Cache {'HIT' if llm.get('from_cache') else 'MISS'} ({llm.get('cache_hits',0)} hits)"
            lines += [
                "",
                "### Chamada LLM",
                f"- Provider: {llm.get('provider')} / {llm.get('model')}",
                f"- Tokens in: {llm.get('tokens_in', '—')}",
                f"- Latência: {llm.get('latency_s', '—')}s",
                f"- Cache: {cache_str}",
            ]
        er = log.get("enforce_rules")
        if er:
            lines += [
                "",
                "### _enforce_rules",
                f"- Steps antes: {er.get('steps_before')} → depois: {er.get('steps_after')} "
                f"(removidos: {er.get('removed', 0)})",
            ]
        repairs = log.get("repair_passes", [])
        lines += ["", "### repair_bpmn"]
        if repairs:
            for r in repairs:
                lines.append(f"- {r}")
        else:
            lines.append("- Nenhum reparo necessário.")
        reformats = log.get("reformat_passes", [])
        lines += ["", "### reformat_bpmn_labels"]
        if reformats:
            for r in reformats:
                lines.append(f"- {r}")
        else:
            lines.append("- Nenhuma alteração.")
        m = log.get("metrics", {})
        if m:
            long_titles = m.get("long_titles", [])
            lines += [
                "",
                "### Métricas do Diagrama",
                f"- Steps: {m.get('steps')} | Edges: {m.get('edges')} | Lanes: {m.get('lanes')} | Gateways: {m.get('gateways')}",
                f"- Tipos de tasks: {_json.dumps(m.get('task_types', {}), ensure_ascii=False)}",
            ]
            if long_titles:
                lines.append(f"- ⚠️ Títulos com >35 chars ({len(long_titles)}): {', '.join(long_titles)}")
            else:
                lines.append("- ✅ Todos os títulos dentro do limite de 35 chars.")
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

    def _list_bpmn_versions(self, args: dict) -> str:
        from core.project_store import list_bpmn_processes, list_bpmn_versions

        process_name = (args.get("process_name") or "").strip().lower()
        if not process_name:
            return "Informe o nome (ou parte do nome) do processo BPMN."

        procs = list_bpmn_processes(self.project_id)
        matches = [p for p in procs if process_name in (p.get("name") or "").lower()]
        if not matches:
            return f"Nenhum processo BPMN encontrado com nome contendo '{process_name}'."
        if len(matches) > 1:
            names = "\n".join(f"  • {p['name']}" for p in matches)
            return f"Múltiplos processos encontrados — seja mais específico:\n{names}"

        proc = matches[0]
        versions = list_bpmn_versions(proc["id"])
        if not versions:
            return f"Processo '{proc['name']}' não possui versões registradas."

        lines = [f"Versões de '{proc['name']}' ({len(versions)} total):"]
        for v in versions:
            mtg   = v.get("meetings") or {}
            atual = " ✅ atual" if v.get("is_current") else ""
            notes = v.get("change_notes") or "—"
            mtg_info = (
                f"Reunião #{mtg.get('meeting_number', '?')} — {mtg.get('title', '')}"
                if mtg else "sem reunião"
            )
            lines.append(
                f"  v{v.get('version', '?')}{atual}  |  {mtg_info}  |  "
                f"notas: {notes}  |  ID: {v['id']}"
            )
        return "\n".join(lines)

    def _delete_bpmn_version(self, args: dict) -> str:
        from core.project_store import delete_bpmn_version

        if not self.is_admin:
            return "Permissão negada — apenas administradores podem excluir versões BPMN."

        version_id = (args.get("version_id") or "").strip()
        reason     = (args.get("reason") or "Não especificado").strip()
        if not version_id:
            return "Informe o version_id da versão a excluir (use list_bpmn_versions)."

        result = delete_bpmn_version(version_id)
        if result["ok"]:
            return f"✅ {result['message']} (motivo: {reason})"
        return f"❌ {result['message']}"

    def review_bpmn_diagram(self, process_name: str) -> str:
        """Audita semanticamente um diagrama BPMN usando análise de XML pura."""
        import xml.etree.ElementTree as ET
        from core.project_store import list_bpmn_processes, list_bpmn_versions

        # ── Localizar processo ─────────────────────────────────────────────────
        procs = list_bpmn_processes(self.project_id)
        name_lower = process_name.lower().strip()
        matches = [p for p in procs if name_lower in (p.get("name") or "").lower()]
        if not matches:
            return f"Processo '{process_name}' não encontrado. Use list_bpmn_processes para ver os disponíveis."
        if len(matches) > 1:
            return "Múltiplos processos encontrados:\n" + "\n".join(f"  • {p['name']}" for p in matches)

        proc = matches[0]
        versions = list_bpmn_versions(proc["id"])
        current = next((v for v in versions if v.get("is_current")), versions[0] if versions else None)
        if not current or not current.get("bpmn_xml"):
            return f"Processo '{proc['name']}' não possui XML BPMN armazenado."

        xml_str = current["bpmn_xml"]

        # ── Parsear XML ────────────────────────────────────────────────────────
        ns = {
            "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
            "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
        }
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as exc:
            return f"ERRO DE SINTAXE no XML: {exc}\nVerifique o XML antes de auditar."

        # Coletar todos os elementos por tipo
        tasks, gateways, events, flows = [], [], [], []
        lanes_found = []
        BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
        task_tags = {f"{{{BPMN_NS}}}{t}" for t in (
            "task", "userTask", "serviceTask", "manualTask", "businessRuleTask",
            "scriptTask", "sendTask", "receiveTask", "callActivity",
        )}
        gw_tags = {f"{{{BPMN_NS}}}{t}" for t in (
            "exclusiveGateway", "parallelGateway", "inclusiveGateway",
            "eventBasedGateway", "complexGateway",
        )}
        event_tags = {f"{{{BPMN_NS}}}{t}" for t in (
            "startEvent", "endEvent", "intermediateCatchEvent", "intermediateThrowEvent",
            "boundaryEvent",
        )}

        for elem in root.iter():
            tag = elem.tag
            eid = elem.get("id", "?")
            name = elem.get("name", "").strip()
            if tag in task_tags:
                tasks.append((eid, name, tag.split("}")[-1]))
            elif tag in gw_tags:
                gateways.append((eid, name, tag.split("}")[-1]))
            elif tag in event_tags:
                events.append((eid, name, tag.split("}")[-1]))
            elif tag == f"{{{BPMN_NS}}}sequenceFlow":
                flows.append((eid, elem.get("sourceRef", "?"), elem.get("targetRef", "?"), name))
            elif tag == f"{{{BPMN_NS}}}lane":
                lanes_found.append((eid, name))

        # ── Aplicar regras ─────────────────────────────────────────────────────
        VERB_TRIGGERS = ("validar", "analisar", "verificar", "revisar", "conferir",
                         "aprovar", "checar", "inspecionar", "auditar", "processar")
        violations, warnings, ok_items = [], [], []

        # R1 — Gateways com verbo de atividade
        for eid, name, gtype in gateways:
            n_lower = name.lower()
            if any(v in n_lower for v in VERB_TRIGGERS):
                violations.append((eid, name, gtype,
                    f"Gateway com verbo de atividade '{name}' — deveria ser userTask/serviceTask + novo gateway de decisão",
                    "R1: Gateways representam pontos de decisão, não trabalho executado"))
            elif name.strip():
                ok_items.append(f"Gateway '{name}' — nomenclatura OK")

        # R2 — Tasks nomeadas como estado/decisão (terminam em '?')
        for eid, name, ttype in tasks:
            if name.endswith("?"):
                violations.append((eid, name, ttype,
                    f"Task '{name}' tem nome de gateway (termina com '?') — deveria ser exclusiveGateway",
                    "R2: Atividades não decidem fluxo — use gateway para ramificação"))
            elif not name:
                warnings.append(f"Task {eid} sem nome — preencha o título")

        # R3 — Start/End Events genéricos
        GENERIC_START = {"inicio", "start", "comecar", "iniciar", "começo"}
        GENERIC_END   = {"fim", "end", "encerrar", "terminar", "final"}
        for eid, name, etype in events:
            nl = name.lower().strip()
            if "start" in etype.lower() and nl in GENERIC_START:
                violations.append((eid, name, etype,
                    f"Start Event com nome genérico '{name}' — descreva o gatilho real",
                    "R3: Start Event deve nomear o evento de negócio que inicia o processo"))
            elif "end" in etype.lower() and nl in GENERIC_END:
                violations.append((eid, name, etype,
                    f"End Event com nome genérico '{name}' — descreva o resultado de negócio",
                    "R4: End Event deve nomear o estado de negócio alcançado"))

        # R4 — Lanes com nomes genéricos
        GENERIC_LANES = {"usuario", "user", "sistema", "system", "ator", "actor",
                         "pessoa", "participante", "validador", "aprovador"}
        for eid, name in lanes_found:
            if name.lower().strip() in GENERIC_LANES:
                violations.append((eid, name, "lane",
                    f"Lane com nome genérico '{name}' — use o nome real do departamento/unidade",
                    "R6: Lanes devem identificar a unidade organizacional responsável"))

        # R5 — Saídas de gateway sem rótulo (sequenceFlow sem name saindo de gateway)
        gw_ids = {g[0] for g in gateways}
        for fid, src, tgt, label in flows:
            if src in gw_ids and not label.strip():
                src_name = next((g[1] for g in gateways if g[0] == src), src)
                warnings.append(
                    f"Fluxo de '{src_name}' (gateway) para '{tgt}' sem rótulo/condição — "
                    "toda saída de gateway deve ter conditionExpression"
                )

        # R6 — Elementos órfãos (sem incoming e sem outgoing)
        all_srcs = {f[1] for f in flows}
        all_tgts = {f[2] for f in flows}
        start_ids = {e[0] for e in events if "start" in e[2].lower()}
        end_ids   = {e[0] for e in events if "end" in e[2].lower()}

        for eid, name, ttype in tasks + gateways:
            has_in  = eid in all_tgts
            has_out = eid in all_srcs
            if not has_in and eid not in start_ids:
                warnings.append(f"Elemento '{name or eid}' ({ttype}) sem fluxo de entrada — possível nó órfão")
            if not has_out and eid not in end_ids:
                warnings.append(f"Elemento '{name or eid}' ({ttype}) sem fluxo de saída — dead end")

        # ── Montar relatório ───────────────────────────────────────────────────
        total = len(tasks) + len(gateways) + len(events)
        score = max(0, round(10 - len(violations) * 1.5 - len(warnings) * 0.5, 1))

        lines = [
            f"# Relatorio de Revisao BPMN",
            f"## Processo: {proc['name']} (v{current.get('version', '?')})",
            "",
            f"## Fase 1 — Estrutura",
            f"- {len(tasks)} tarefas · {len(gateways)} gateways · {len(events)} eventos · {len(flows)} sequenceFlows · {len(lanes_found)} lanes",
            f"- Score de qualidade: **{score}/10**",
            "",
            f"## Fase 2 — Violacoes Detectadas",
        ]

        if violations:
            lines.append(f"\n**{len(violations)} violacao(oes) critica(s):**\n")
            lines.append("| Tipo | Elemento | Problema | Justificativa |")
            lines.append("|---|---|---|---|")
            for eid, name, etype, problem, rule in violations:
                lines.append(f"| VIOLACAO | `{eid}` {name} ({etype}) | {problem} | {rule} |")
        else:
            lines.append("\nNenhuma violacao critica detectada.")

        if warnings:
            lines.append(f"\n**{len(warnings)} aviso(s):**\n")
            for w in warnings:
                lines.append(f"- ATENCAO: {w}")

        if ok_items:
            lines.append(f"\n**Pontos positivos ({len(ok_items)}):**")
            for o in ok_items[:5]:
                lines.append(f"- OK: {o}")

        lines += [
            "",
            "---",
            "",
            "## Proximos passos",
            "1. Para cada VIOLACAO, solicite ao Assistente que reelabore o elemento corrigido.",
            "2. Quando satisfeito com o JSON corrigido, use `save_bpmn_revision` para salvar.",
        ]

        return "\n".join(lines)

    def describe_bpmn_process(self, process_name: str) -> str:
        """Gera descrição textual estruturada de um processo BPMN a partir do XML."""
        import xml.etree.ElementTree as ET
        from core.project_store import list_bpmn_processes, list_bpmn_versions

        procs = list_bpmn_processes(self.project_id)
        name_lower = process_name.lower().strip()
        matches = [p for p in procs if name_lower in (p.get("name") or "").lower()]
        if not matches:
            return f"Processo '{process_name}' não encontrado. Use list_bpmn_processes para ver os disponíveis."
        if len(matches) > 1:
            return "Múltiplos processos:\n" + "\n".join(f"  • {p['name']}" for p in matches)

        proc = matches[0]
        versions = list_bpmn_versions(proc["id"])
        current = next((v for v in versions if v.get("is_current")), versions[0] if versions else None)
        if not current or not current.get("bpmn_xml"):
            return f"Processo '{proc['name']}' não possui XML BPMN armazenado."

        xml_str = current["bpmn_xml"]
        BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"

        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as exc:
            return f"Erro de parsing no XML: {exc}"

        # Coletar elementos com nomes e tipos
        elem_map: dict[str, dict] = {}
        lane_elements: dict[str, list[str]] = {}  # lane_name → [elem_ids]
        pool_names: list[str] = []
        flows: list[tuple] = []  # (src_id, tgt_id, label)

        for elem in root.iter():
            tag = elem.tag
            eid = elem.get("id", "")
            name = (elem.get("name") or "").strip()
            local = tag.replace(f"{{{BPMN_NS}}}", "")

            KNOWN_TYPES = {
                "task", "userTask", "serviceTask", "manualTask", "businessRuleTask",
                "scriptTask", "sendTask", "receiveTask", "callActivity",
                "startEvent", "endEvent", "intermediateCatchEvent", "intermediateThrowEvent",
                "boundaryEvent", "exclusiveGateway", "parallelGateway", "inclusiveGateway",
                "eventBasedGateway", "complexGateway",
            }
            if local in KNOWN_TYPES and eid:
                elem_map[eid] = {"name": name, "type": local}
            elif local == "sequenceFlow" and eid:
                flows.append((elem.get("sourceRef", ""), elem.get("targetRef", ""), name))
            elif local == "lane" and eid:
                lane_name = name
                # collect flowNodeRef children
                refs = [c.text.strip() for c in elem if c.tag == f"{{{BPMN_NS}}}flowNodeRef" and c.text]
                lane_elements[lane_name] = refs
            elif local == "participant" and name:
                pool_names.append(name)

        # Mapear saídas por elemento
        outgoing_map: dict[str, list] = {}
        for src, tgt, lbl in flows:
            outgoing_map.setdefault(src, []).append((tgt, lbl))

        # Determinar ordem topológica simples (BFS a partir de startEvents)
        start_ids = [eid for eid, e in elem_map.items() if "start" in e["type"].lower()]
        visited: list[str] = []
        queue = list(start_ids)
        seen: set[str] = set(start_ids)
        while queue:
            cur = queue.pop(0)
            visited.append(cur)
            for tgt, _ in outgoing_map.get(cur, []):
                if tgt not in seen and tgt in elem_map:
                    seen.add(tgt)
                    queue.append(tgt)
        # Append any remaining (cycles / unreachable)
        for eid in elem_map:
            if eid not in seen:
                visited.append(eid)

        # Mapear cada elemento à sua lane
        elem_to_lane: dict[str, str] = {}
        for lane_name, refs in lane_elements.items():
            for ref in refs:
                elem_to_lane[ref] = lane_name

        # Construir descrição
        TYPE_LABELS = {
            "exclusiveGateway": "Decisão exclusiva (XOR)",
            "parallelGateway":  "Fork/join paralelo (AND)",
            "inclusiveGateway": "Gateway inclusivo (OR)",
            "eventBasedGateway": "Gateway baseado em evento",
            "startEvent": "Evento de início",
            "endEvent":   "Evento de fim",
            "userTask":    "Tarefa humana",
            "serviceTask": "Tarefa de sistema",
            "manualTask":  "Tarefa manual",
            "businessRuleTask": "Regra de negócio",
            "sendTask":    "Envio de mensagem",
            "receiveTask": "Recebimento de mensagem",
            "callActivity": "Subprocesso chamado",
            "intermediateCatchEvent": "Evento intermediário (captura)",
            "intermediateThrowEvent": "Evento intermediário (lançamento)",
            "boundaryEvent": "Evento de fronteira",
        }

        lines = [
            f"## Processo: {proc['name']} (v{current.get('version', '?')})",
            "",
        ]

        if pool_names:
            lines += ["### Participantes (Pools)", ""]
            for p in pool_names:
                lines.append(f"- **{p}**")
            lines.append("")

        if lane_elements:
            lines += ["### Participantes (Lanes)", ""]
            for lane_name in lane_elements:
                lines.append(f"- **{lane_name}**")
            lines.append("")

        lines += ["### Fluxo do Processo", ""]
        step_num = 0
        for eid in visited:
            e = elem_map.get(eid)
            if not e:
                continue
            step_num += 1
            ename = e["name"] or f"[sem nome — {eid}]"
            etype = e["type"]
            type_label = TYPE_LABELS.get(etype, etype)
            lane = elem_to_lane.get(eid, "")
            lane_str = f" ({lane})" if lane else ""

            outs = outgoing_map.get(eid, [])
            if "gateway" in etype.lower():
                if outs:
                    out_desc = "; ".join(
                        f'"{lbl}" → {elem_map.get(tgt, {}).get("name", tgt)}'
                        for tgt, lbl in outs if lbl
                    ) or "; ".join(
                        elem_map.get(tgt, {}).get("name", tgt) for tgt, _ in outs
                    )
                    lines.append(f"{step_num}. **{ename}**{lane_str} — {type_label}: {out_desc}.")
                else:
                    lines.append(f"{step_num}. **{ename}**{lane_str} — {type_label}.")
            elif "end" in etype.lower():
                lines.append(f"{step_num}. **{ename}**{lane_str} — {type_label}. *(resultado final)*")
            else:
                lines.append(f"{step_num}. **{ename}**{lane_str} — {type_label}.")

        end_names = [elem_map[e]["name"] for e in visited
                     if elem_map.get(e, {}).get("type", "").startswith("end") and elem_map[e]["name"]]
        if end_names:
            lines += ["", "### Resultados Possíveis", ""]
            for n in end_names:
                lines.append(f"- {n}")

        return "\n".join(lines)

    def suggest_bpmn_corrections(self, process_name: str) -> str:
        """Gera plano de correção estruturado a partir da auditoria do diagrama BPMN."""
        import xml.etree.ElementTree as ET
        from core.project_store import list_bpmn_processes, list_bpmn_versions

        procs = list_bpmn_processes(self.project_id)
        name_lower = process_name.lower().strip()
        matches = [p for p in procs if name_lower in (p.get("name") or "").lower()]
        if not matches:
            return f"Processo '{process_name}' não encontrado. Use list_bpmn_processes para ver os disponíveis."
        if len(matches) > 1:
            return "Múltiplos processos:\n" + "\n".join(f"  • {p['name']}" for p in matches)

        proc = matches[0]
        versions = list_bpmn_versions(proc["id"])
        current = next((v for v in versions if v.get("is_current")), versions[0] if versions else None)
        if not current or not current.get("bpmn_xml"):
            return f"Processo '{proc['name']}' sem XML armazenado."

        xml_str = current["bpmn_xml"]
        BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
        VERB_TRIGGERS = ("validar", "analisar", "verificar", "revisar", "conferir",
                         "aprovar", "checar", "inspecionar", "auditar", "processar")

        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as exc:
            return f"Erro de parsing no XML: {exc}"

        tasks, gateways, events, flows = [], [], [], []
        for elem in root.iter():
            tag = elem.tag; eid = elem.get("id", "?"); name = (elem.get("name") or "").strip()
            local = tag.replace(f"{{{BPMN_NS}}}", "")
            if local in {"exclusiveGateway", "parallelGateway", "inclusiveGateway",
                         "eventBasedGateway", "complexGateway"}:
                gateways.append((eid, name, local))
            elif local in {"task", "userTask", "serviceTask", "manualTask",
                           "businessRuleTask", "scriptTask", "sendTask", "receiveTask", "callActivity"}:
                tasks.append((eid, name, local))
            elif local in {"startEvent", "endEvent"}:
                events.append((eid, name, local))
            elif local == "sequenceFlow":
                flows.append((eid, elem.get("sourceRef", "?"), elem.get("targetRef", "?"), name))

        gw_ids = {g[0] for g in gateways}
        outgoing: dict[str, list] = {}
        for fid, src, tgt, lbl in flows:
            outgoing.setdefault(src, []).append((tgt, lbl))

        corrections: list[dict] = []

        # Gateways com verbos de atividade
        for eid, name, gtype in gateways:
            if any(v in name.lower() for v in VERB_TRIGGERS):
                outs = outgoing.get(eid, [])
                gw_label = f"{'Conteúdo Validado?' if 'valid' in name.lower() else name + '?'}"
                corrections.append({
                    "element_id": eid,
                    "element_name": name,
                    "current_type": gtype,
                    "action": "convert_to_task",
                    "new_type": "userTask",
                    "new_name": name,
                    "reason": f"'{name}' é verbo de atividade — gateways não executam trabalho",
                    "additional_steps": [
                        f"Criar gateway exclusivo '{gw_label}' após o novo userTask '{name}'",
                        f"Mover as {len(outs)} saídas atuais para o novo gateway",
                    ],
                })

        # Tasks nomeadas como decisão
        for eid, name, ttype in tasks:
            if name.endswith("?"):
                corrections.append({
                    "element_id": eid,
                    "element_name": name,
                    "current_type": ttype,
                    "action": "convert_to_gateway",
                    "new_type": "exclusiveGateway",
                    "new_name": name,
                    "reason": f"'{name}' termina com '?' — é um ponto de decisão, não uma tarefa",
                })

        # Gateways com saídas sem rótulo
        for eid, name, gtype in gateways:
            unlabeled = [(tgt, lbl) for tgt, lbl in outgoing.get(eid, []) if not lbl.strip()]
            if unlabeled and gtype == "exclusiveGateway":
                n_out = len(outgoing.get(eid, []))
                suggested = ["Sim", "Não"] if n_out == 2 else [f"Caminho {i+1}" for i in range(n_out)]
                corrections.append({
                    "element_id": eid,
                    "element_name": name,
                    "current_type": gtype,
                    "action": "add_edge_labels",
                    "reason": f"Gateway exclusivo com {len(unlabeled)} saída(s) sem rótulo",
                    "suggested_labels": suggested,
                })

        # Start/End eventos genéricos
        GENERIC_START = {"inicio", "start", "comecar", "iniciar", "começo"}
        GENERIC_END   = {"fim", "end", "encerrar", "terminar", "final"}
        for eid, name, etype in events:
            nl = name.lower().strip()
            if "start" in etype.lower() and nl in GENERIC_START:
                corrections.append({
                    "element_id": eid, "element_name": name, "current_type": etype,
                    "action": "rename",
                    "reason": "Start Event com nome genérico — descreva o gatilho real do processo",
                    "suggestion": "Ex: 'Solicitação Recebida', 'Demanda Registrada'",
                })
            elif "end" in etype.lower() and nl in GENERIC_END:
                corrections.append({
                    "element_id": eid, "element_name": name, "current_type": etype,
                    "action": "rename",
                    "reason": "End Event com nome genérico — descreva o resultado de negócio",
                    "suggestion": "Ex: 'Processo Concluído com Sucesso', 'Solicitação Recusada'",
                })

        if not corrections:
            return (
                f"Nenhuma correção automática identificada para '{proc['name']}'.\n"
                f"O diagrama passou nos principais critérios de auditoria estrutural.\n"
                f"Para auditoria detalhada, use review_bpmn_diagram."
            )

        lines = [
            f"# Plano de Correcao — {proc['name']}",
            f"**{len(corrections)} correcao(oes) identificada(s)**",
            "",
            "## Correcoes em ordem de prioridade",
            "",
        ]
        for i, c in enumerate(corrections, 1):
            lines += [
                f"### {i}. {c['element_name']} (`{c['element_id']}`)",
                f"- **Tipo atual:** {c['current_type']}",
                f"- **Acao:** {c['action']}",
                f"- **Motivo:** {c['reason']}",
            ]
            if "new_type" in c:
                lines.append(f"- **Novo tipo:** {c['new_type']}")
            if "new_name" in c:
                lines.append(f"- **Novo nome:** {c['new_name']}")
            if "additional_steps" in c:
                lines.append("- **Passos adicionais:**")
                for s in c["additional_steps"]:
                    lines.append(f"  - {s}")
            if "suggested_labels" in c:
                lines.append(f"- **Labels sugeridos:** {', '.join(repr(l) for l in c['suggested_labels'])}")
            if "suggestion" in c:
                lines.append(f"- **Sugestao:** {c['suggestion']}")
            lines.append("")

        lines += [
            "---",
            "## Proximo passo",
            "Revise as correcoes acima, ajuste o JSON BPMN conforme necessario e use `save_bpmn_revision` para salvar.",
        ]
        return "\n".join(lines)

    def save_bpmn_revision(
        self,
        process_name: str,
        bpmn_xml: str,
        process_description: str = "",
        meeting_number: int | None = None,
        revision_notes: str = "",
    ) -> str:
        """Salva XML BPMN corrigido como nova versão no banco."""
        from core.project_store import (
            list_bpmn_processes, save_bpmn_new_version, get_bpmn_process,
        )
        from modules.supabase_client import get_supabase_client

        if not bpmn_xml or not bpmn_xml.strip():
            return "❌ XML BPMN vazio — informe o XML corrigido."

        procs = list_bpmn_processes(self.project_id)
        name_lower = process_name.lower().strip()
        matches = [p for p in procs if name_lower in (p.get("name") or "").lower()]
        if not matches:
            return f"❌ Processo '{process_name}' não encontrado."
        if len(matches) > 1:
            return "Múltiplos processos encontrados:\n" + "\n".join(f"  • {p['name']}" for p in matches)

        proc = matches[0]
        process_id = proc["id"]

        # Resolver meeting_id
        meeting_id = None
        if meeting_number is not None:
            mtg = self._find_meeting(meeting_number)
            if mtg:
                meeting_id = mtg["id"]

        notes = revision_notes or "Revisão via Assistente"
        ok = save_bpmn_new_version(
            process_id=process_id,
            meeting_id=meeting_id,
            project_id=self.project_id,
            bpmn_xml=bpmn_xml,
            version_notes=notes,
            created_by="assistente",
        )

        if not ok:
            return f"❌ Erro ao salvar revisão do processo '{proc['name']}'."

        # Salvar descrição textual se fornecida (campo process_description em bpmn_processes)
        if process_description:
            try:
                db = get_supabase_client()
                if db:
                    db.table("bpmn_processes").update(
                        {"process_description": process_description}
                    ).eq("id", process_id).execute()
            except Exception:
                pass  # campo pode não existir — best-effort

        version_count = (proc.get("version_count") or 0) + 1
        return (
            f"Revisao salva com sucesso!\n"
            f"Processo: {proc['name']}\n"
            f"Nova versao: v{version_count}\n"
            f"Notas: {notes}"
        )

    def apply_bpmn_corrections(
        self,
        process_name: str,
        corrections: list[dict],
        version_notes: str = "",
    ) -> str:
        """Aplica correções cirúrgicas via AgentBPMNReviewer e salva nova versão."""
        from core.project_store import (
            list_bpmn_processes, list_bpmn_versions, save_bpmn_new_version,
            save_bpmn_review_log,
        )
        from agents.agent_bpmn_reviewer import AgentBPMNReviewer
        from agents.agent_bpmn import AgentBPMN

        # 1. Localizar processo e versão atual
        procs = list_bpmn_processes(self.project_id)
        name_lower = process_name.lower().strip()
        matches = [p for p in procs if name_lower in (p.get("name") or "").lower()]
        if not matches:
            return f"Processo '{process_name}' não encontrado. Use list_bpmn_processes."
        if len(matches) > 1:
            return "Múltiplos processos:\n" + "\n".join(f"  • {p['name']}" for p in matches)

        proc = matches[0]
        versions = list_bpmn_versions(proc["id"])
        current = next((v for v in versions if v.get("is_current")), versions[0] if versions else None)
        if not current or not current.get("bpmn_xml"):
            return f"Processo '{proc['name']}' sem XML BPMN armazenado."

        if not corrections:
            return "Lista de correções vazia — nada a aplicar."

        # 2. Chamar AgentBPMNReviewer para aplicar as correções e gerar JSON corrigido
        reviewer = AgentBPMNReviewer()
        corrected_json = reviewer.apply_corrections(
            bpmn_xml=current["bpmn_xml"],
            process_name=proc["name"],
            corrections=corrections,
        )
        if not corrected_json or not isinstance(corrected_json, dict):
            return (
                "Falha ao gerar modelo corrigido via LLM.\n"
                "Alternativas: use suggest_bpmn_corrections para ver o plano de correção "
                "e depois save_bpmn_revision com o XML completo corrigido manualmente."
            )

        # 3. Construir BPMNModel a partir do JSON e gerar novo XML
        try:
            model = AgentBPMN._build_model(corrected_json)
            AgentBPMN._enforce_rules(model, nlp_actors=[])
            bpmn_xml_new = AgentBPMN._generate_bpmn_xml(model)
        except Exception as exc:
            return f"Erro ao gerar XML a partir do modelo corrigido: {exc}"

        if not bpmn_xml_new:
            return (
                "Geração de XML retornou vazio.\n"
                "Use save_bpmn_revision com o XML completo corrigido."
            )

        # 4. Salvar como nova versão
        notes = version_notes.strip() or (
            f"Correções aplicadas via AgentBPMNReviewer "
            f"({len(corrections)} item(s)): "
            + "; ".join(
                f"{c.get('action', '?')} {c.get('element_name') or c.get('element_id', '?')}"
                for c in corrections[:3]
            )
            + ("..." if len(corrections) > 3 else "")
        )

        version_before = current.get("version", 0) or 0
        meeting_id_ref = current.get("meeting_id") or ""

        ok = save_bpmn_new_version(
            process_id=proc["id"],
            meeting_id=meeting_id_ref,
            project_id=self.project_id,
            bpmn_xml=bpmn_xml_new,
            mermaid_code="",
            version_notes=notes,
            created_by="bpmn_reviewer",
        )

        if not ok:
            return f"Correções geradas, mas falha ao salvar no banco. Tente save_bpmn_revision."

        version_after = version_before + 1

        # 5. Registrar no log de auditoria (fail-open)
        try:
            save_bpmn_review_log(
                project_id=self.project_id,
                process_name=proc["name"],
                version_before=version_before,
                version_after=version_after,
                issues_found=len(corrections),
                issues_corrected=len(corrections),
                review_report={"corrections": corrections},
                user_approved=True,
            )
        except Exception:
            pass

        return (
            f"Correções aplicadas com sucesso em '{proc['name']}'.\n"
            f"  Versao: v{version_before} -> v{version_after}\n"
            f"  {len(corrections)} correcao(oes) processada(s)\n"
            f"  Nova versao salva como atual (is_current=True)\n\n"
            f"Use review_bpmn_diagram para confirmar a qualidade do diagrama corrigido."
        )

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

    def list_context_files(self) -> str:
        from core.project_store import list_context_files as _list_files
        files = _list_files(self.project_id)
        if not files:
            return "Nenhum arquivo de referência encontrado para este contexto."
        lines = [f"Arquivos de referência do contexto ({len(files)}):"]
        for f in files:
            size_kb = (f.get("file_size") or 0) / 1024
            date    = (f.get("uploaded_at") or "")[:10]
            by      = f.get("uploaded_by") or ""
            by_str  = f" por {by}" if by else ""
            lines.append(f"• {f['filename']} ({f['file_type'].upper()}, {size_kb:.0f} KB) — adicionado em {date}{by_str}")
        return "\n".join(lines)

    def _resolve_search_terms(self, db, name: str) -> list[str]:
        """Build a deduplicated list of search terms for a participant name.

        Returns: [original_name, computed_initials, first_name_only]
        Only includes terms that actually differ and are non-empty.

        Example: 'Maria de Fátima Duarte Miranda' → ['Maria de Fátima Duarte Miranda', 'MFDM', 'Maria']
        """
        name = name.strip()
        seen: list[str] = []

        def _add(t: str) -> None:
            t = t.strip()
            if t and t not in seen:
                seen.append(t)

        _add(name)
        _add(_compute_initials(name))

        parts = name.split()
        if len(parts) > 1:
            _add(parts[0])  # first name only

        return seen

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

    def update_sbvr_rule(
        self,
        rule_id: str,
        new_statement: str,
        new_rule_type: str | None = None,
    ) -> str:
        """Atualiza o enunciado e/ou tipo de uma regra SBVR existente pelo ID."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "❌ Supabase não configurado."

        try:
            rows = (
                db.table("sbvr_rules")
                .select("id, rule_id, statement, rule_type")
                .eq("project_id", self.project_id)
                .ilike("rule_id", rule_id.strip())
                .execute().data or []
            )
        except Exception as exc:
            return f"❌ Erro ao buscar regra: {exc}"

        if not rows:
            return f"❌ Regra '{rule_id}' não encontrada no projeto."

        patch: dict = {"statement": new_statement.strip()}
        if new_rule_type:
            patch["rule_type"] = new_rule_type.strip()

        try:
            db.table("sbvr_rules").update(patch).eq("id", rows[0]["id"]).execute()
            fields = ["enunciado"] + (["tipo"] if new_rule_type else [])
            return (
                f"✅ Regra {rule_id} atualizada com sucesso!\n"
                f"• Campos alterados: {', '.join(fields)}\n"
                f"• Novo enunciado: {new_statement}"
            )
        except Exception as exc:
            return f"❌ Erro ao atualizar regra '{rule_id}': {exc}"

    def update_sbvr_term_by_id(
        self,
        term_id: str,
        new_definition: str | None = None,
        new_category: str | None = None,
    ) -> str:
        """Atualiza um termo SBVR pelo UUID — para termos homônimos com IDs distintos."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "❌ Supabase não configurado."

        patch: dict = {}
        if new_definition:
            patch["definition"] = new_definition.strip()
        if new_category:
            patch["category"] = new_category.strip()

        if not patch:
            return "❌ Nenhum campo para atualizar. Informe new_definition e/ou new_category."

        try:
            rows = (
                db.table("sbvr_terms")
                .select("id, term, definition")
                .eq("id", term_id.strip())
                .execute().data or []
            )
        except Exception as exc:
            return f"❌ Erro ao verificar termo: {exc}"

        if not rows:
            return f"❌ Termo com ID '{term_id}' não encontrado."

        term_name = rows[0].get("term", "—")
        try:
            db.table("sbvr_terms").update(patch).eq("id", term_id.strip()).execute()
            fields = (["definição"] if new_definition else []) + (["categoria"] if new_category else [])
            return (
                f"✅ Termo '{term_name}' (ID: {term_id[:8]}…) atualizado!\n"
                f"• Campos alterados: {', '.join(fields)}"
                + (f"\n• Nova definição: {new_definition}" if new_definition else "")
            )
        except Exception as exc:
            return f"❌ Erro ao atualizar termo '{term_id}': {exc}"

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
            ("requirement_versions", "meeting_id"),
            ("requirements",         "first_meeting_id"),
            ("transcript_chunks",    "meeting_id"),
            ("sbvr_terms",           "meeting_id"),
            ("sbvr_rules",           "meeting_id"),
            ("bpmn_versions",        "meeting_id"),
        ]:
            try:
                rows = db.table(table).select("id").eq(col, mid).execute().data or []
                if rows:
                    cascade.append(f"  • {len(rows)} registro(s) em `{table}`")
            except Exception:
                cascade.append(f"  • `{table}`: não foi possível verificar")
        # bpmn_processes orphaned after version deletion
        try:
            all_procs = (
                db.table("bpmn_processes").select("id, name").eq("project_id", self.project_id).execute().data or []
            )
            bpmn_ver_rows = db.table("bpmn_versions").select("id, process_id").eq("meeting_id", mid).execute().data or []
            affected_proc_ids = {v["process_id"] for v in bpmn_ver_rows}
            orphaned = []
            for proc in all_procs:
                if proc["id"] not in affected_proc_ids:
                    continue
                remaining = db.table("bpmn_versions").select("id").eq("process_id", proc["id"]).execute().data or []
                # Would have len(remaining) - (versions from this meeting) == 0 → orphaned
                versions_this_meeting = sum(1 for v in bpmn_ver_rows if v["process_id"] == proc["id"])
                if len(remaining) == versions_this_meeting:
                    orphaned.append(proc.get("name", proc["id"]))
            if orphaned:
                cascade.append(f"  • {len(orphaned)} processo(s) BPMN sem versões restantes: {', '.join(orphaned)}")
        except Exception:
            pass

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
            # ── Step 1: Collect requirement IDs that originated from this meeting ─
            try:
                orig_req_ids = [
                    r["id"] for r in
                    (db.table("requirements").select("id").eq("first_meeting_id", mid).execute().data or [])
                ]
            except Exception:
                orig_req_ids = []

            # ── Step 2: Delete requirement_versions for this meeting ──────────────
            # Must come before deleting requirements (FK: requirement_versions.requirement_id)
            try:
                db.table("requirement_versions").delete().eq("meeting_id", mid).execute()
            except Exception:
                pass

            # ── Step 3: Delete requirements that originated from this meeting ──────
            for rid in orig_req_ids:
                try:
                    db.table("requirements").delete().eq("id", rid).execute()
                except Exception:
                    pass

            # ── Step 4: Null-out remaining FK references in requirements ──────────
            for fk_col in ("last_meeting_id", "first_meeting_id"):
                try:
                    db.table("requirements").update({fk_col: None}).eq(fk_col, mid).execute()
                except Exception:
                    pass

            # ── Step 5: Delete tables with meeting_id FK (may lack CASCADE) ───────
            for table in ("transcript_chunks", "sbvr_terms", "sbvr_rules"):
                try:
                    db.table(table).delete().eq("meeting_id", mid).execute()
                except Exception:
                    pass

            # ── Step 6: Delete bpmn_versions for this meeting ─────────────────────
            try:
                db.table("bpmn_versions").delete().eq("meeting_id", mid).execute()
            except Exception:
                pass

            # ── Step 7: Delete bpmn_processes that have no remaining versions ──────
            try:
                all_procs = (
                    db.table("bpmn_processes").select("id").eq("project_id", self.project_id).execute().data or []
                )
                for proc in all_procs:
                    rem = (
                        db.table("bpmn_versions").select("id").eq("process_id", proc["id"]).execute().data or []
                    )
                    if not rem:
                        db.table("bpmn_processes").delete().eq("id", proc["id"]).execute()
            except Exception:
                pass

            # ── Step 8: Delete the meeting row itself ──────────────────────────────
            db.table("meetings").delete().eq("id", mid).execute()
            self._meeting_cache = None  # invalidate cache
            return (
                f"✅ Reunião {meeting_number} — '{title}' excluída com sucesso.\n"
                "Todos os dados associados (requisitos, transcrição, ata, BPMN, "
                "SBVR e embeddings) foram removidos."
            )
        except Exception as exc:
            return f"❌ Erro ao excluir Reunião {meeting_number}: {exc}"

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

    def rename_meeting(self, meeting_number: int, new_title: str) -> str:
        """Rename a meeting — updates title in the meetings table."""
        if not new_title or not new_title.strip():
            return "❌ Novo título não pode ser vazio."

        m = self._find_meeting(meeting_number)
        if not m:
            return f"Reunião {meeting_number} não encontrada no projeto."

        old_title = m.get("title") or f"Reunião {meeting_number}"
        meeting_id = m.get("id", "")

        from core.project_store import update_meeting_title
        success = update_meeting_title(meeting_id, new_title.strip())
        if success:
            return (
                f"✅ Título da Reunião {meeting_number} atualizado com sucesso.\n"
                f"   Antes: {old_title}\n"
                f"   Depois: {new_title.strip()}"
            )
        return f"❌ Falha ao atualizar o título da Reunião {meeting_number}. Verifique a conexão com o banco."

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
        
    # ── User / Domain query methods ────────────────────────────────────────

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

    # ── Google Calendar tools ─────────────────────────────────────────────────

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

    def calendar_schedule_action_items(
        self,
        meeting_number: int,
        default_date: str,
        duration_minutes: int = 30,
        project_id: str | None = None,
    ) -> str:
        from modules.calendar_client import schedule_action_items, calendar_configured
        if not calendar_configured():
            return "⚙️ Google Calendar não configurado neste ambiente."

        m = self._find_meeting(meeting_number)
        if not m:
            return f"Reunião {meeting_number} não encontrada no projeto."

        minutes_md = m.get("minutes_md") or ""
        if not minutes_md:
            return (
                f"Reunião {meeting_number} não possui ata armazenada. "
                "Gere a ata primeiro via pipeline ou pela ferramenta generate_missing_minutes."
            )

        action_items_text = self._section(
            minutes_md, "Itens de Ação", "Action Items", "Ações"
        )
        if not action_items_text.strip():
            return f"Reunião {meeting_number}: nenhum item de ação encontrado na ata."

        meeting_title = m.get("title") or f"Reunião {meeting_number}"
        return schedule_action_items(
            action_items_text=action_items_text,
            meeting_title=meeting_title,
            default_date=default_date,
            duration_minutes=duration_minutes,
            project_id=project_id,
        )

    def calendar_share_with_user(self, email: str, role: str = "writer", project_id: str | None = None) -> str:
        from modules.calendar_client import share_calendar, calendar_configured
        if not calendar_configured():
            return "⚙️ Google Calendar não configurado neste ambiente."
        return share_calendar(email=email, role=role, project_id=project_id)

    def calendar_revoke_access(self, email: str, project_id: str | None = None) -> str:
        from modules.calendar_client import revoke_calendar_access, calendar_configured
        if not calendar_configured():
            return "⚙️ Google Calendar não configurado neste ambiente."
        return revoke_calendar_access(email=email, project_id=project_id)

    # ── Admin: integrity & fix tools ─────────────────────────────────────────

    def get_database_integrity(self) -> str:
        """Full integrity report for the project: health %, missing fields per meeting."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        try:
            meetings = (
                db.table("meetings")
                .select(
                    "id, meeting_number, title, meeting_date, "
                    "transcript_clean, transcript_raw, minutes_md, "
                    "llm_provider, total_tokens"
                )
                .eq("project_id", self.project_id)
                .order("meeting_number")
                .execute().data or []
            )
        except Exception as exc:
            return f"❌ Erro ao carregar reuniões: {exc}"

        # Embeddings — paginação para contornar o limite server-side de 1000 linhas do Supabase
        try:
            from core.project_store import _fetch_all_chunks_paginated
            chunks = _fetch_all_chunks_paginated(db, self.project_id, "meeting_id")
            mids_with_chunks = {c["meeting_id"] for c in chunks}
            chunks_ok = True
        except Exception:
            mids_with_chunks = set()
            chunks_ok = False

        # BPMN
        try:
            bversions = db.table("bpmn_versions").select("meeting_id").execute().data or []
            mids_with_bpmn = {v["meeting_id"] for v in bversions if v.get("meeting_id")}
            bpmn_ok = True
        except Exception:
            mids_with_bpmn = set()
            bpmn_ok = False

        _ACTIONS = {
            "transcrição": "→ use Manutenção > Transcript Backfill",
            "ata":         "→ use generate_missing_minutes()",
            "embeddings":  "→ use embed_meeting(N) para uma reunião ou generate_meeting_embeddings() para todas",
            "BPMN":        "→ use Manutenção > BPMN Backfill",
            "tokens":      "→ use reprocess_meeting_full(N) para regenerar todos os artefatos",
            "provedor LLM": "→ use fix_missing_llm_provider(provider)",
        }

        issues: list[tuple] = []
        field_counts: dict[str, int] = {}
        for m in meetings:
            mid = m["id"]
            missing: list[str] = []
            if not (m.get("transcript_clean") or m.get("transcript_raw")):
                missing.append("transcrição")
            if not m.get("minutes_md"):
                missing.append("ata")
            if chunks_ok and mid not in mids_with_chunks:
                missing.append("embeddings")
            if bpmn_ok and mid not in mids_with_bpmn:
                missing.append("BPMN")
            if not (m.get("total_tokens") or 0):
                missing.append("tokens")
            if not (m.get("llm_provider") or "").strip():
                missing.append("provedor LLM")
            if missing:
                issues.append((m.get("meeting_number"), m.get("title"), missing))
                for f in missing:
                    field_counts[f] = field_counts.get(f, 0) + 1

        n_total    = len(meetings)
        n_slots    = n_total * 6
        n_missing  = sum(len(i[2]) for i in issues)
        health_pct = round(100 * (1 - n_missing / n_slots)) if n_slots else 100

        lines = [
            "=== Integridade do Banco — Projeto ===",
            f"Saúde geral       : {health_pct}%",
            f"Reuniões total    : {n_total}",
            f"Reuniões completas: {n_total - len(issues)}",
            f"Com problemas     : {len(issues)}",
            f"Campos ausentes   : {n_missing}",
            "",
        ]
        if not issues:
            lines.append("✅ Todas as reuniões possuem todos os campos preenchidos.")
        else:
            lines.append("Campos ausentes (por frequência):")
            for f, c in sorted(field_counts.items(), key=lambda x: -x[1]):
                lines.append(f"  • {f}: {c} reunião(ões)  {_ACTIONS.get(f, '')}")
            lines += ["", "Detalhes por reunião:"]
            for n, title, missing in issues:
                lines.append(
                    f"  Reunião {n} — {title or '(sem título)'}: "
                    f"falta {', '.join(missing)}"
                )
        return "\n".join(lines)

    def fix_missing_llm_provider(self, provider: str) -> str:
        """Update llm_provider for all project meetings that have it null/empty."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        try:
            rows = (
                db.table("meetings")
                .select("id, meeting_number, title, llm_provider")
                .eq("project_id", self.project_id)
                .execute().data or []
            )
        except Exception as exc:
            return f"❌ Erro ao buscar reuniões: {exc}"

        affected = [m for m in rows if not (m.get("llm_provider") or "").strip()]
        if not affected:
            return "✅ Todas as reuniões já possuem provedor LLM registrado. Nada a corrigir."

        ok = 0
        errors: list[str] = []
        for m in affected:
            try:
                db.table("meetings").update({"llm_provider": provider}).eq("id", m["id"]).execute()
                ok += 1
            except Exception as exc:
                errors.append(
                    f"  • Reunião {m.get('meeting_number')} — "
                    f"{m.get('title') or '(sem título)'}: {exc}"
                )

        lines = [
            f"fix_missing_llm_provider — provider: '{provider}'",
            f"✅ {ok} reunião(ões) atualizadas.",
        ]
        if errors:
            lines.append(f"❌ {len(errors)} erro(s):")
            lines.extend(errors)
        return "\n".join(lines)

    def _get_embed_credentials(self) -> tuple[str, str]:
        """Read embedding api_key and provider from Streamlit session state."""
        import streamlit as st
        api_key  = st.session_state.get("asst_embed_key", "").strip()
        provider = st.session_state.get("asst_embed_provider", "Google Gemini")
        return api_key, provider

    def _embed_one_meeting(
        self,
        meeting: dict,
        api_key: str,
        provider: str,
        force: bool = False,
    ) -> str:
        """
        Generate and save embeddings for a single meeting dict.
        Returns a status string (success or error message).
        Skips if already has chunks and force=False.
        """
        from modules.supabase_client import get_supabase_client
        from core.project_store import save_transcript_embeddings

        n     = meeting.get("meeting_number", "?")
        title = meeting.get("title") or f"Reunião {n}"
        mid   = meeting["id"]
        text  = meeting.get("transcript_clean") or meeting.get("transcript_raw") or ""

        if not text.strip():
            return f"  • Reunião {n} — '{title}': sem transcrição disponível."

        db = get_supabase_client()
        if db:
            try:
                existing = (
                    db.table("transcript_chunks")
                    .select("chunk_index", count="exact")
                    .eq("meeting_id", mid)
                    .limit(1)
                    .execute()
                )
                has_chunks = (existing.count or 0) > 0
            except Exception:
                has_chunks = False

            if has_chunks and not force:
                return f"  • Reunião {n} — '{title}': já possui embeddings (use force=true para regenerar)."

            if has_chunks and force:
                try:
                    db.table("transcript_chunks").delete().eq("meeting_id", mid).execute()
                except Exception as exc:
                    return f"  • Reunião {n} — '{title}': erro ao apagar embeddings antigos: {exc}"

        try:
            n_chunks = save_transcript_embeddings(
                mid, self.project_id, text, api_key, provider
            )
            from modules.embeddings import EMBEDDING_PROVIDERS
            model = EMBEDDING_PROVIDERS.get(provider, {}).get("model", provider)
            return (
                f"  • Reunião {n} — '{title}': ✅ {n_chunks} chunks indexados "
                f"[{provider} / {model}]."
            )
        except Exception as exc:
            return f"  • Reunião {n} — '{title}': ❌ {exc}"

    def generate_meeting_embeddings(
        self,
        meeting_numbers: list[int] | None = None,
    ) -> str:
        """Generate embeddings for all eligible meetings (no chunks yet)."""
        api_key, provider = self._get_embed_credentials()
        if not api_key:
            return (
                "❌ API key de embedding não configurada. "
                "Acesse **Configurações → Embeddings & Busca** e salve a chave antes de continuar."
            )

        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        try:
            all_meetings = (
                db.table("meetings")
                .select("id, meeting_number, title, transcript_clean, transcript_raw")
                .eq("project_id", self.project_id)
                .order("meeting_number")
                .execute().data or []
            )
        except Exception as exc:
            return f"❌ Erro ao buscar reuniões: {exc}"

        try:
            from core.project_store import _fetch_all_chunks_paginated
            chunks_rows = _fetch_all_chunks_paginated(db, self.project_id, "meeting_id")
            mids_with_chunks = {c["meeting_id"] for c in chunks_rows}
        except Exception:
            mids_with_chunks = set()

        candidates = [
            m for m in all_meetings
            if (m.get("transcript_clean") or m.get("transcript_raw") or "").strip()
            and m["id"] not in mids_with_chunks
            and (meeting_numbers is None or m.get("meeting_number") in meeting_numbers)
        ]

        if not candidates:
            already = "já possuem embeddings" if not meeting_numbers else "já possuem embeddings ou não têm transcrição"
            return f"✅ Todas as reuniões elegíveis {already}. Nada a gerar."

        from modules.embeddings import EMBEDDING_PROVIDERS
        model = EMBEDDING_PROVIDERS.get(provider, {}).get("model", provider)
        results = [self._embed_one_meeting(m, api_key, provider) for m in candidates]

        ok  = [r for r in results if "✅" in r]
        err = [r for r in results if "✅" not in r]

        lines = [
            f"Provedor: **{provider}** · Modelo: `{model}`",
            f"✅ {len(ok)} indexadas · ❌ {len(err)} falha(s) / puladas",
            "",
        ]
        lines.extend(results)
        if ok:
            lines.append("\nTranscrições disponíveis para busca semântica no Assistente.")
        return "\n".join(lines)

    def embed_meeting(self, meeting_number: int, force: bool = False) -> str:
        """Generate (or regenerate) embeddings for a single specific meeting."""
        api_key, provider = self._get_embed_credentials()
        if not api_key:
            return (
                "❌ API key de embedding não configurada. "
                "Acesse **Configurações → Embeddings & Busca** e salve a chave antes de continuar."
            )

        m = self._find_meeting(meeting_number)
        if not m:
            return f"Reunião {meeting_number} não encontrada no projeto."

        result = self._embed_one_meeting(m, api_key, provider, force=force)
        return result.strip("  • ")

    def reprocess_meeting_full(
        self,
        meeting_number: int,
        run_bpmn: bool = False,
        run_quality: bool = False,
        output_language: str = "Auto-detect",
    ) -> str:
        """Re-run the full pipeline on an existing meeting and update all artifacts."""
        if not self.llm_config:
            return (
                "❌ Configuração LLM não disponível no executor. "
                "Certifique-se de que a chave de API está configurada no Assistente."
            )

        m = self._find_meeting(meeting_number)
        if not m:
            return f"Reunião {meeting_number} não encontrada no projeto."

        title      = m.get("title") or f"Reunião {meeting_number}"
        transcript = (m.get("transcript_clean") or m.get("transcript_raw") or "").strip()

        if not transcript:
            return (
                f"❌ Reunião {meeting_number} — '{title}' não possui transcrição armazenada. "
                "Use Manutenção → Transcript Backfill para carregar a transcrição antes de reprocessar."
            )

        try:
            from core.batch_pipeline import BatchPipeline, FileResult

            provider_cfg = self.llm_config.get("provider_cfg", {})
            client_info  = {"api_key": self.llm_config.get("api_key", "")}

            pipeline = BatchPipeline(
                client_info=client_info,
                provider_cfg=provider_cfg,
                output_language=output_language,
            )

            agents_config = {
                "run_minutes":             True,
                "run_requirements":        True,
                "run_sbvr":                True,
                "run_bmm":                 True,
                "run_dmn":                 True,
                "run_argumentation":       True,
                "run_synthesizer":         True,
                "run_ckf_updater":         True,
                "run_query_summarizer":    True,
                "run_knowledge_extractor": True,
                "run_quality":             run_quality,
                "run_bpmn":                run_bpmn,
            }

            result: FileResult = pipeline._reprocess_one(m, self.project_id, agents_config)

            if result.status == "failed":
                return f"❌ Falha ao reprocessar Reunião {meeting_number} — '{title}': {result.error}"

            lines = [
                "══════════════════════════════════════════════",
                f"  Reunião {meeting_number} — '{title}'",
                "══════════════════════════════════════════════",
                f"  Status                  : ✅ Reprocessada com sucesso",
                f"  Requisitos novos        : {result.req_new}",
                f"  Termos SBVR             : {result.n_terms}",
                f"  Regras SBVR             : {result.n_rules}",
                f"  Ata+BABOK               : regenerada",
                f"  DMN                     : regenerado",
                f"  Argumentação IBIS       : regenerada",
                f"  Relatório Executivo     : regenerado",
                f"  Sumário por Perspectiva : regenerado",
                f"  Knowledge Graph         : extraído",
                f"  CKF Contexto            : atualizado",
            ]
            if run_bpmn:
                lines.append("  BPMN                    : regenerado")
            if run_quality:
                lines.append("  Qualidade               : avaliada")
            return "\n".join(lines)

        except Exception as exc:
            return f"❌ Erro ao reprocessar Reunião {meeting_number}: {exc}"

    def reprocess_communication_noise(
        self,
        meeting_number: int,
        output_language: str = "Auto-detect",
    ) -> str:
        """Re-run AgentCommunicationNoise on stored transcript(s) and persist results."""
        if not self.llm_config:
            return "❌ Configuração LLM não disponível. Configure a chave de API no Assistente."

        if meeting_number == 0:
            meetings = self._get_meetings()
            if not meetings:
                return "Nenhuma reunião encontrada no projeto."
            results = [self._reprocess_noise_one(m, output_language) for m in meetings]
            return "\n".join(results)

        m = self._find_meeting(meeting_number)
        if not m:
            return f"Reunião {meeting_number} não encontrada."
        return self._reprocess_noise_one(m, output_language)

    def _reprocess_noise_one(self, m: dict, output_language: str) -> str:
        """Run AgentCommunicationNoise on one meeting and save to DB."""
        from core.project_store import load_meeting_as_hub, save_meeting_artifacts
        from agents.agent_communication_noise import AgentCommunicationNoise

        num       = m.get("meeting_number", "?")
        title     = m.get("title") or f"Reunião {num}"
        mid       = m.get("id", "")
        transcript = (m.get("transcript_clean") or m.get("transcript_raw") or "").strip()

        if not transcript:
            return f"  ⚠️ Reunião {num} — sem transcrição. Use Manutenção → Transcript Backfill."

        try:
            provider_cfg = self.llm_config.get("provider_cfg", {})
            client_info  = {"api_key": self.llm_config.get("api_key", "")}

            hub = load_meeting_as_hub(mid, self.project_id)
            if hub is None:
                from core.knowledge_hub import KnowledgeHub
                hub = KnowledgeHub.new()
                hub.transcript_clean = transcript
                hub.transcript_raw   = transcript

            agent = AgentCommunicationNoise(client_info, provider_cfg)
            hub   = agent.run(hub, output_language)
            save_meeting_artifacts(mid, hub)

            cn = hub.communication_noise
            return (
                f"  ✅ Reunião {num} — '{title}': "
                f"{len(cn.ambiguities)} ambiguidades, {len(cn.gaps)} lacunas, "
                f"índice de ruído {cn.noise_score:.1f}/10."
            )
        except Exception as exc:
            return f"  ❌ Reunião {num} — '{title}': {exc}"

    def regenerate_executive_report(
        self,
        meeting_number: int,
        output_language: str = "Auto-detect",
    ) -> str:
        """Regenerate only the executive HTML report for a meeting.

        Strategy (2 LLM calls vs ~10+ for full reprocess):
          1. Load stored artifacts from Supabase via load_meeting_as_hub
             (BPMN XML/Mermaid, requirements, SBVR)
          2. Parse BPMN XML to reconstruct steps/lanes for the process table
          3. Re-run AgentMinutes on the stored transcript to get structured
             minutes data (participants, decisions, action_items)
          4. Run AgentSynthesizer to produce narrative + HTML
          5. Persist the HTML via save_report_html
        """
        if not self.llm_config:
            return (
                "❌ Configuração LLM não disponível. "
                "Certifique-se de que a chave de API está configurada no Assistente."
            )

        m = self._find_meeting(meeting_number)
        if not m:
            return f"Reunião {meeting_number} não encontrada no projeto."

        title      = m.get("title") or f"Reunião {meeting_number}"
        meeting_id = m["id"]
        transcript = (m.get("transcript_clean") or m.get("transcript_raw") or "").strip()

        if not transcript:
            return (
                f"❌ Reunião {meeting_number} — '{title}' não possui transcrição armazenada. "
                "Use Manutenção → Transcript Backfill antes de regenerar o relatório."
            )

        try:
            from core.project_store import load_meeting_as_hub, save_report_html
            from core.batch_pipeline import _preload_bpmn_from_db
            from agents.agent_minutes import AgentMinutes
            from agents.agent_synthesizer import AgentSynthesizer

            provider_cfg = self.llm_config.get("provider_cfg", {})
            client_info  = {"api_key": self.llm_config.get("api_key", "")}

            # 1. Load stored hub (BPMN XML/Mermaid, requirements, SBVR)
            hub = load_meeting_as_hub(meeting_id, self.project_id)
            if hub is None:
                from core.knowledge_hub import KnowledgeHub
                hub = KnowledgeHub.new()
                hub.set_transcript(transcript)

            # 2. Parse BPMN XML into steps/lanes (if not done by load_meeting_as_hub)
            if hub.bpmn.ready and hub.bpmn.bpmn_xml and not hub.bpmn.steps:
                _preload_bpmn_from_db(hub, meeting_id)
            elif not hub.bpmn.ready:
                _preload_bpmn_from_db(hub, meeting_id)

            # 3. Re-run AgentMinutes to get structured minutes data
            hub.set_transcript(transcript)
            minutes_agent = AgentMinutes(client_info, provider_cfg)
            hub = minutes_agent.run(hub, output_language)

            # 4. Run AgentSynthesizer
            synth_agent = AgentSynthesizer(client_info, provider_cfg)
            hub = synth_agent.run(hub, output_language)

            if not hub.synthesizer.ready or not hub.synthesizer.html:
                return f"❌ AgentSynthesizer não produziu relatório para Reunião {meeting_number}."

            # 5. Persist HTML
            save_report_html(
                meeting_id,
                hub.synthesizer.html,
                provider_cfg.get("provider_name", ""),
            )

            return (
                f"✅ Relatório Executivo da Reunião {meeting_number} — '{title}' "
                f"regenerado e salvo com sucesso."
            )

        except Exception as exc:
            return f"❌ Erro ao regenerar relatório da Reunião {meeting_number}: {exc}"

    # ── Chart tools ───────────────────────────────────────────────────────────

    def _dark_layout(self, fig, title: str = "") -> None:
        """Apply the app's dark theme to a Plotly figure in-place."""
        fig.update_layout(
            title=dict(text=title, font=dict(size=15, color="#FAFAF8")),
            paper_bgcolor="#0A1A32",
            plot_bgcolor="#0A1A32",
            font=dict(color="#FAFAF8", size=12),
            xaxis=dict(gridcolor="#1A3050", zerolinecolor="#1A3050"),
            yaxis=dict(gridcolor="#1A3050", zerolinecolor="#1A3050"),
            legend=dict(bgcolor="#0F2040", bordercolor="#1A3050", borderwidth=1),
            margin=dict(t=60, b=50, l=50, r=20),
        )

    def generate_requirements_chart(
        self,
        group_by: str = "type",
        meeting_number: int | None = None,
    ) -> str:
        """Bar chart of requirements grouped by type and/or priority."""
        from modules.supabase_client import get_supabase_client
        import plotly.graph_objects as go
        from collections import Counter

        client = get_supabase_client()
        if client is None:
            return "Supabase não configurado."
        try:
            q = (
                client.table("requirements")
                .select("req_type, priority")
                .eq("project_id", self.project_id)
            )
            if meeting_number:
                q = q.eq("meeting_number", meeting_number)
            rows = q.execute().data or []
        except Exception as e:
            return f"Erro ao buscar requisitos: {e}"

        if not rows:
            return "Nenhum requisito encontrado para gerar o gráfico."

        _req_types = ["Funcional", "Não-Funcional", "Regra de Negócio", "Restrição", "Interface", "Desempenho"]
        _TYPE_COLORS = {t: self._palette[i % len(self._palette)] for i, t in enumerate(_req_types)}
        _PRIO_COLORS = {"Alta": "#ef4444", "Média": "#C97B1A", "Baixa": "#10b981"}  # semantic, kept fixed

        suffix = f" — Reunião {meeting_number}" if meeting_number else ""
        n_total = len(rows)

        if group_by == "priority":
            counts = Counter(r.get("priority") or "Não definida" for r in rows)
            labels = list(counts.keys())
            values = list(counts.values())
            colors = [_PRIO_COLORS.get(lb, "#64748b") for lb in labels]
            fig = go.Figure(go.Bar(
                x=labels, y=values, marker_color=colors,
                text=values, textposition="outside",
            ))
            self._dark_layout(fig, f"Requisitos por Prioridade{suffix}")

        elif group_by == "both":
            # Stacked bar: type on x, stacked by priority
            type_prio: dict[str, Counter] = {}
            for r in rows:
                t = r.get("req_type") or "Outro"
                p = r.get("priority") or "Não definida"
                type_prio.setdefault(t, Counter())[p] += 1
            all_types = list(type_prio.keys())
            all_prios = list({r.get("priority") or "Não definida" for r in rows})
            traces = []
            for prio in all_prios:
                traces.append(go.Bar(
                    name=prio,
                    x=all_types,
                    y=[type_prio.get(t, Counter()).get(prio, 0) for t in all_types],
                    marker_color=_PRIO_COLORS.get(prio, "#64748b"),
                ))
            fig = go.Figure(data=traces)
            fig.update_layout(barmode="stack")
            self._dark_layout(fig, f"Requisitos por Tipo e Prioridade{suffix}")

        else:  # type (default)
            counts = Counter(r.get("req_type") or "Outro" for r in rows)
            labels = list(counts.keys())
            values = list(counts.values())
            colors = [_TYPE_COLORS.get(lb, "#64748b") for lb in labels]
            fig = go.Figure(go.Bar(
                x=labels, y=values, marker_color=colors,
                text=values, textposition="outside",
            ))
            self._dark_layout(fig, f"Requisitos por Tipo{suffix}")

        self._pending_charts.append(fig.to_dict())
        breakdown = ", ".join(
            f"{k}: {v}"
            for k, v in Counter(r.get("req_type") or "Outro" for r in rows).most_common()
        )
        return f"📊 Gráfico gerado: {n_total} requisitos{suffix} — {breakdown}"

    def generate_meetings_timeline(self, metric: str = "all") -> str:
        """Bar chart of meeting artefact volumes over time."""
        from modules.supabase_client import get_supabase_client
        import plotly.graph_objects as go

        client = get_supabase_client()
        if client is None:
            return "Supabase não configurado."

        meetings = self._get_meetings()
        if not meetings:
            return "Nenhuma reunião encontrada."

        try:
            reqs_resp = (
                client.table("requirements")
                .select("meeting_number")
                .eq("project_id", self.project_id)
                .execute()
            )
            req_rows = reqs_resp.data or []
        except Exception:
            req_rows = []

        from collections import Counter, defaultdict
        req_counts = Counter(r.get("meeting_number") for r in req_rows)

        mtg_nums   = [m.get("meeting_number") for m in meetings]
        mtg_labels = [
            f"#{m.get('meeting_number')} {(m.get('title') or '')[:20]}"
            for m in meetings
        ]

        def _extract_decisions(minutes_md: str) -> int:
            if not minutes_md:
                return 0
            import re
            dec_section = re.search(r"Decisões.*?\n(.*?)(?:\n##|\Z)", minutes_md, re.DOTALL | re.IGNORECASE)
            if dec_section:
                return len([ln for ln in dec_section.group(1).splitlines() if ln.strip().startswith("-")])
            return 0

        def _extract_actions(minutes_md: str) -> int:
            if not minutes_md:
                return 0
            import re
            act_section = re.search(r"Ações|Action Items.*?\n(.*?)(?:\n##|\Z)", minutes_md, re.DOTALL | re.IGNORECASE)
            if act_section:
                return len([ln for ln in act_section.group(1).splitlines() if ln.strip().startswith("-")])
            return 0

        decisions = [_extract_decisions(m.get("minutes_md", "")) for m in meetings]
        actions   = [_extract_actions(m.get("minutes_md", "")) for m in meetings]
        reqs      = [req_counts.get(n, 0) for n in mtg_nums]

        traces = []
        if metric in ("requirements", "all"):
            traces.append(go.Bar(name="Requisitos", x=mtg_labels, y=reqs, marker_color=self._palette[0]))
        if metric in ("decisions", "all"):
            traces.append(go.Bar(name="Decisões", x=mtg_labels, y=decisions, marker_color=self._palette[1]))
        if metric in ("action_items", "all"):
            traces.append(go.Bar(name="Ações", x=mtg_labels, y=actions, marker_color=self._palette[2]))

        fig = go.Figure(data=traces)
        fig.update_layout(barmode="group")
        self._dark_layout(fig, "Linha do Tempo das Reuniões — Artefatos por Reunião")
        self._pending_charts.append(fig.to_dict())
        return f"📊 Gráfico gerado: {len(meetings)} reuniões — requisitos, decisões e ações"

    def generate_action_items_chart(
        self,
        group_by: str = "status",
        meeting_number: int | None = None,
    ) -> str:
        """Bar or pie chart of action items."""
        import plotly.graph_objects as go
        from collections import Counter
        import re

        meetings = self._get_meetings()
        if meeting_number:
            meetings = [m for m in meetings if m.get("meeting_number") == meeting_number]

        # Parse action items from minutes_md
        items = []
        for m in meetings:
            md = m.get("minutes_md") or ""
            # look for lines like "- [ ] Task | Resp | Date" or "- [x] Task"
            for line in md.splitlines():
                line = line.strip()
                if not line.startswith("- ["):
                    continue
                done = line.startswith("- [x]") or line.startswith("- [X]")
                rest = re.sub(r"^- \[.\]\s*", "", line)
                parts = [p.strip() for p in rest.split("|")]
                task = parts[0] if parts else rest
                resp = parts[1] if len(parts) > 1 else "Não definido"
                items.append({
                    "task": task,
                    "responsible": resp,
                    "status": "Concluído" if done else "Pendente",
                    "meeting_number": m.get("meeting_number"),
                })

        if not items:
            return "Nenhum item de ação encontrado (verifique se as atas foram geradas)."

        suffix = f" — Reunião {meeting_number}" if meeting_number else ""

        if group_by == "responsible":
            counts = Counter(it["responsible"] for it in items)
            labels = list(counts.keys())
            values = list(counts.values())
            bar_colors = [self._palette[i % len(self._palette)] for i in range(len(labels))]
            fig = go.Figure(go.Bar(
                x=labels, y=values, marker_color=bar_colors,
                text=values, textposition="outside",
            ))
            self._dark_layout(fig, f"Itens de Ação por Responsável{suffix}")

        elif group_by == "meeting":
            counts = Counter(f"Reunião #{it['meeting_number']}" for it in items)
            labels = list(counts.keys())
            values = list(counts.values())
            bar_colors = [self._palette[i % len(self._palette)] for i in range(len(labels))]
            fig = go.Figure(go.Bar(
                x=labels, y=values, marker_color=bar_colors,
                text=values, textposition="outside",
            ))
            self._dark_layout(fig, "Itens de Ação por Reunião")

        else:  # status — keep semantic green/red (Concluído/Pendente carry meaning)
            counts = Counter(it["status"] for it in items)
            labels = list(counts.keys())
            values = list(counts.values())
            fig = go.Figure(go.Pie(
                labels=labels, values=values,
                marker=dict(colors=["#10b981" if lb == "Concluído" else "#ef4444" for lb in labels]),
                textinfo="label+percent+value",
                hole=0.35,
            ))
            self._dark_layout(fig, f"Status dos Itens de Ação{suffix}")

        self._pending_charts.append(fig.to_dict())
        total = len(items)
        done = sum(1 for it in items if it["status"] == "Concluído")
        return f"📊 Gráfico gerado: {total} itens de ação{suffix} — {done} concluídos, {total - done} pendentes"

    def generate_roi_chart(self, cost_per_hour: float = 150.0) -> str:
        """Bar chart of ROI-TR per meeting."""
        import plotly.graph_objects as go
        import re

        meetings = self._get_meetings()
        if not meetings:
            return "Nenhuma reunião encontrada."

        from modules.supabase_client import get_supabase_client
        client = get_supabase_client()

        labels, roi_values, colors = [], [], []
        for m in meetings:
            num   = m.get("meeting_number")
            title = (m.get("title") or "")[:20]
            md    = m.get("minutes_md") or ""

            # Count participants
            n_part = 1
            part_match = re.search(r"Participantes.*?\n(.*?)(?:\n##|\Z)", md, re.DOTALL | re.IGNORECASE)
            if part_match:
                n_part = max(1, len([ln for ln in part_match.group(1).splitlines() if ln.strip().startswith("-")]))

            # Count decisions
            dec_match = re.search(r"Decisões.*?\n(.*?)(?:\n##|\Z)", md, re.DOTALL | re.IGNORECASE)
            n_dec = len([ln for ln in (dec_match.group(1).splitlines() if dec_match else []) if ln.strip().startswith("-")])

            # Count actions
            n_act = len([ln for ln in md.splitlines() if ln.strip().startswith("- [")])

            # Count requirements
            n_req = 0
            if client:
                try:
                    n_req = len(client.table("requirements").select("id").eq("project_id", self.project_id).eq("meeting_number", num).execute().data or [])
                except Exception:
                    pass

            # Simple ROI formula (approximate)
            dc = n_dec * 1.5 + n_act * 1.0 + n_req * 1.0
            dur_h = 1.0  # assume 1h
            roi = min(10.0, dc * 1000 / (n_part * dur_h * cost_per_hour) * 1.5) if cost_per_hour > 0 else 0.0
            roi = round(roi, 2)

            labels.append(f"#{num} {title}")
            roi_values.append(roi)

        bar_colors = [self._palette[i % len(self._palette)] for i in range(len(labels))]

        fig = go.Figure(go.Bar(
            x=labels, y=roi_values,
            marker_color=bar_colors,
            text=[f"{v:.1f}" for v in roi_values],
            textposition="outside",
        ))
        fig.add_hline(y=7.0, line_dash="dash", line_color="#10b981",
                      annotation_text="Bom (7)", annotation_position="right")
        fig.add_hline(y=4.0, line_dash="dash", line_color="#C97B1A",
                      annotation_text="Regular (4)", annotation_position="right")
        self._dark_layout(fig, "ROI-TR por Reunião (0–10)")
        fig.update_yaxes(range=[0, 11])
        self._pending_charts.append(fig.to_dict())
        avg = sum(roi_values) / len(roi_values) if roi_values else 0
        return f"📊 Gráfico ROI-TR gerado: {len(meetings)} reuniões — média {avg:.1f}/10"

    def generate_custom_chart(
        self,
        chart_type: str,
        title: str,
        labels: list[str],
        values: list[float],
        x_label: str = "",
        y_label: str = "",
        series_name: str = "",
    ) -> str:
        """Render a custom chart from LLM-provided data."""
        import plotly.graph_objects as go

        colors = [self._palette[i % len(self._palette)] for i in range(len(labels))]

        ct = chart_type.lower()
        try:
            if ct == "pie":
                trace = go.Pie(
                    labels=labels, values=values,
                    marker=dict(colors=colors),
                    textinfo="label+percent+value",
                    hole=0.3,
                )
                fig = go.Figure(trace)
            elif ct == "line":
                fig = go.Figure(go.Scatter(
                    x=labels, y=values, mode="lines+markers",
                    name=series_name or title,
                    line=dict(color=self._palette[0], width=2),
                    marker=dict(size=8),
                ))
            elif ct == "scatter":
                fig = go.Figure(go.Scatter(
                    x=labels, y=values, mode="markers",
                    name=series_name or title,
                    marker=dict(color=colors, size=12),
                ))
            elif ct == "funnel":
                fig = go.Figure(go.Funnel(
                    y=labels, x=values,
                    marker=dict(color=colors),
                ))
            else:  # bar (default)
                fig = go.Figure(go.Bar(
                    x=labels, y=values,
                    marker_color=colors,
                    text=values, textposition="outside",
                    name=series_name or title,
                ))

            self._dark_layout(fig, title)
            if x_label:
                fig.update_xaxes(title_text=x_label)
            if y_label:
                fig.update_yaxes(title_text=y_label)
            self._pending_charts.append(fig.to_dict())
            return f"📊 Gráfico '{title}' ({chart_type}) gerado com {len(labels)} categorias."
        except Exception as e:
            return f"Erro ao gerar gráfico personalizado: {e}"

    # ── populate_roster ─────────────────────────────────────────

    def _populate_roster(self, args: dict) -> str:
        """Extract participant names from minutes_md and pre-populate the project roster."""
        from core.project_store import (
            extract_participants_from_project,
            upsert_roster_member,
            get_project_roster,
        )
        dry_run = bool(args.get("dry_run", False))
        meeting_numbers = args.get("meeting_numbers") or None
        project_id = self.project_id

        if not project_id:
            return (
                "Nenhum contexto ativo. Selecione um contexto na Home primeiro "
                "ou use set_active_project."
            )

        result = extract_participants_from_project(project_id, meeting_numbers)
        candidates = result["candidates"]
        existing_initials = result["existing_initials"]
        scanned = result["meetings_scanned"]
        with_parts = result["meetings_with_participants"]

        header = (
            f"Pre-cadastro de participantes — {scanned} reuniao(oes) analisadas, "
            f"{with_parts} com lista de participantes. "
            f"Roster atual: {len(existing_initials)} membro(s)."
        )

        if not candidates:
            return (
                header + "\n\nNenhum participante novo identificado. "
                "Todos os nomes encontrados ja estao no roster, "
                "ou as reunioes nao possuem ata com secao de Participantes."
            )

        if dry_run:
            parts = [header, f"\nPreview — {len(candidates)} candidato(s) novo(s):\n"]
            for c in candidates:
                label = "reuniao" if c["meetings_count"] == 1 else "reunioes"
                parts.append(
                    f"- **{c['initials']}** — {c['full_name']}  "
                    f"cor #{c['color_hex']} | {c['meetings_count']} {label} | "
                    f"aliases: {', '.join(c['name_aliases'])}"
                )
            parts.append(
                "\nPara confirmar o cadastro chame populate_roster sem dry_run."
            )
            return "\n".join(parts)

        # Write to database
        existing_roster = get_project_roster(project_id)
        base_sort = len(existing_roster)
        added, failed = [], []
        for idx, c in enumerate(candidates):
            try:
                row = upsert_roster_member(project_id, {
                    "initials":     c["initials"],
                    "full_name":    c["full_name"],
                    "area":         None,
                    "color_hex":    c["color_hex"],
                    "name_aliases": c["name_aliases"],
                    "sort_order":   base_sort + idx,
                    "is_active":    True,
                })
                if row:
                    added.append(c)
                else:
                    failed.append(c["full_name"])
            except Exception as exc:
                failed.append(f"{c['full_name']} ({exc})")

        parts = [header, f"\n{len(added)} participante(s) adicionado(s):\n"]
        for c in added:
            parts.append(f"- **{c['initials']}** — {c['full_name']}  cor #{c['color_hex']}")
        if failed:
            parts.append(f"\nFalhas ({len(failed)}): {', '.join(failed)}")
        parts.append(
            "\nAcesse Configuracoes > Participantes para ajustar cores, area e aliases."
        )
        return "\n".join(parts)

    def _render_table(self, args: dict) -> str:
        """Persist table data so Assistente.py can render it + offer Excel export."""
        import streamlit as st
        pending = st.session_state.get("_pending_tables", [])
        pending.append({
            "title":       args.get("title", "Tabela"),
            "columns":     args.get("columns", []),
            "rows":        args.get("rows", []),
            "chart_type":  args.get("chart_type", "none"),
            "chart_x_col": args.get("chart_x_col"),
            "chart_y_cols": args.get("chart_y_cols", []),
        })
        st.session_state["_pending_tables"] = pending
        col_count = len(args.get("columns", []))
        row_count = len(args.get("rows", []))
        return f"Tabela '{args.get('title', '')}' registrada ({row_count} linhas x {col_count} colunas)."
        
    def get_executive_report(self, meeting_number: int) -> str:
        """Retrieve persisted executive HTML report and queue for download."""
        import streamlit as st
        from modules.supabase_client import get_supabase_client

        m = self._find_meeting(meeting_number)
        if not m:
            return f"Reunião {meeting_number} não encontrada no projeto."

        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        try:
            row = (
                db.table("meetings")
                .select("report_html, report_generated_at, report_provider")
                .eq("id", m["id"])
                .single()
                .execute()
            ).data
        except Exception as exc:
            return f"Erro ao buscar relatório: {exc}"

        html = row.get("report_html") if row else None
        if not html:
            return (
                f"A reunião {meeting_number} ainda não tem relatório executivo. "
                f"Acesse **Manutenção → Relatório Executivo** para gerar."
            )

        key = f"_report_dl_{meeting_number}"
        st.session_state["_pending_report_html"] = {
            "html":           html,
            "meeting_number": meeting_number,
            "filename":       f"relatorio_executivo_reuniao_{meeting_number}.html",
            "cache_key":      key,
        }
        st.session_state[key] = html.encode()

        gen_at  = (row.get("report_generated_at") or "")[:16].replace("T", " ")
        prov    = row.get("report_provider") or "—"
        size_kb = round(len(html) / 1024, 1)
        return (
            f"✅ Relatório executivo da Reunião {meeting_number} disponível para download.\n"
            f"Gerado em: {gen_at} · Provedor: {prov} · Tamanho: {size_kb} KB"
        )

    # ── detect_contradictions ─────────────────────────────────────────────────

    def _detect_contradictions(self) -> str:
        """Full-scan cross-meeting contradiction detection via AgentContradictionDetector."""
        if not self.llm_config:
            return (
                "❌ Configuração LLM não disponível. "
                "Certifique-se de que a chave de API está configurada no Assistente."
            )
        if not self.project_id:
            return (
                "Nenhum contexto ativo. Selecione um contexto na Home primeiro "
                "ou use set_active_project."
            )

        from core.knowledge_store import kh_tables_exist, get_facts
        if not kh_tables_exist():
            return (
                "❌ As tabelas do Knowledge Hub não existem no Supabase. "
                "Execute setup/supabase_schema_knowledge_hub.sql primeiro."
            )

        all_facts = get_facts(self.project_id, active_only=True, limit=500)
        if len(all_facts) < 2:
            return (
                "O Knowledge Hub do projeto ainda tem poucos fatos armazenados. "
                "Execute populate_knowledge_hub primeiro para popular as tabelas kh_*."
            )

        provider_cfg = self.llm_config.get("provider_cfg", {})
        client_info  = {"api_key": self.llm_config.get("api_key", "")}

        from agents.agent_contradiction_detector import AgentContradictionDetector
        agent = AgentContradictionDetector(client_info, provider_cfg)
        n = agent.run_full_scan(self.project_id)

        by_type: dict[str, int] = {}
        for f in all_facts:
            by_type[f.get("fact_type", "other")] = by_type.get(f.get("fact_type", "other"), 0) + 1

        type_summary = " · ".join(f"{t}: {c}" for t, c in sorted(by_type.items()))
        return (
            f"Varredura de contradições concluída.\n\n"
            f"Fatos analisados: {len(all_facts)} ({type_summary})\n"
            f"Contradições detectadas e inseridas: {n}\n\n"
            f"Consulte a aba ⚠️ Contradições na página 🧠 Knowledge Hub para revisar e resolver."
        )

    # ── lookup_entity ─────────────────────────────────────────────────────────

    def _lookup_entity(self, args: dict) -> str:
        """Return full details of a KH entity to help identify unknown entries."""
        if not self.project_id:
            return "Nenhum contexto ativo."

        from core.knowledge_store import get_entities
        from core.project_store import get_meetings

        entity_name = (args.get("entity_name") or "").strip()
        if not entity_name:
            return "❌ Forneça entity_name."

        all_entities = get_entities(self.project_id, limit=500)
        s = entity_name.lower()
        candidates = [
            e for e in all_entities
            if s in (e.get("canonical_name") or "").lower()
            or any(s in (a or "").lower() for a in (e.get("aliases") or []))
        ]
        if not candidates:
            return (
                f"Nenhuma entidade encontrada com o nome '{entity_name}'.\n"
                f"Use o Grafo de Conhecimento para ver os nomes exatos."
            )

        # Build meeting number map for context
        meetings = get_meetings(self.project_id)
        mid_to_num = {m["id"]: m.get("meeting_number", "?") for m in meetings}

        lines = [f"**{len(candidates)} entidade(s) encontrada(s) para '{entity_name}':**\n"]
        for e in candidates[:5]:
            name     = e.get("canonical_name", "—")
            etype    = e.get("entity_type", "—")
            count    = e.get("occurrence_count", 1)
            aliases  = ", ".join((e.get("aliases") or [])[:6]) or "—"
            meta     = e.get("metadata") or {}
            desc     = (meta.get("description") or "")[:120]
            mids     = e.get("meeting_ids") or []
            mtg_nums = sorted(set(
                str(mid_to_num.get(m, "?")) for m in mids
            ))
            lines.append(
                f"• **{name}**\n"
                f"  Tipo: {etype} | Ocorrências: {count}\n"
                f"  Aliases: {aliases}\n"
                + (f"  Descrição: {desc}\n" if desc else "")
                + f"  Reuniões: {', '.join(mtg_nums) if mtg_nums else '—'}\n"
            )
        lines.append(
            "\nDica: use `search_transcript` com o nome da entidade para ver o contexto "
            "nas transcrições, ou `delete_entity` para removê-la se for um artefato."
        )
        return "\n".join(lines)

    # ── delete_entity ─────────────────────────────────────────────────────────

    def _delete_entity(self, args: dict) -> str:
        """Delete a spurious/bogus entity from kh_entities."""
        if not self.project_id:
            return "Nenhum contexto ativo."

        from core.knowledge_store import get_entities, delete_entity

        entity_name = (args.get("entity_name") or "").strip()
        reason      = (args.get("reason") or "Não especificado").strip()
        if not entity_name:
            return "❌ Forneça entity_name."

        all_entities = get_entities(self.project_id, limit=500)
        s = entity_name.lower()

        # 1. Match exato no canonical_name (prioridade máxima)
        exact = [e for e in all_entities
                 if (e.get("canonical_name") or "").lower() == s]
        if exact:
            entity = exact[0]
        else:
            # 2. Substring no canonical_name
            name_sub = [e for e in all_entities
                        if s in (e.get("canonical_name") or "").lower()]
            if len(name_sub) == 1:
                entity = name_sub[0]
            elif len(name_sub) > 1:
                names = "; ".join(
                    f"'{e.get('canonical_name','?')}'" for e in name_sub[:5]
                )
                return (
                    f"⚠️ '{entity_name}' corresponde a {len(name_sub)} entidades "
                    f"pelo nome: {names}.\n"
                    f"Use o nome exato (cópia do Grafo de Conhecimento) para evitar "
                    f"deleções acidentais."
                )
            else:
                # 3. Substring nos aliases (último recurso)
                alias_sub = [e for e in all_entities
                             if any(s in (a or "").lower()
                                    for a in (e.get("aliases") or []))]
                if not alias_sub:
                    return (
                        f"Nenhuma entidade encontrada com o nome '{entity_name}'.\n"
                        f"Verifique o Grafo de Conhecimento para o nome exato."
                    )
                if len(alias_sub) > 1:
                    details = "; ".join(
                        f"'{e.get('canonical_name','?')}' (aliases: "
                        f"{', '.join((e.get('aliases') or [])[:3])})"
                        for e in alias_sub[:3]
                    )
                    return (
                        f"⚠️ '{entity_name}' foi encontrado como alias em "
                        f"{len(alias_sub)} entidades:\n{details}\n\n"
                        f"Use o canonical_name exato de uma delas para deletar."
                    )
                entity = alias_sub[0]

        eid   = entity["id"]
        ename = entity.get("canonical_name", entity_name)
        ok    = delete_entity(self.project_id, eid)

        if ok:
            return (
                f"✅ Entidade **'{ename}'** removida do Knowledge Hub.\n"
                f"Tipo: {entity.get('entity_type', '—')} | "
                f"Ocorrências: {entity.get('occurrence_count', 1)}\n"
                f"Motivo: {reason}\n\n"
                f"Recarregue a página do Grafo de Conhecimento para ver a alteração "
                f"(o cache expira em 2 min ou recarregue agora com F5)."
            )
        return f"❌ Falha ao remover '{ename}'. Verifique os logs do servidor."

    # ── resolve_entity_ambiguity ──────────────────────────────────────────────

    def _resolve_entity_ambiguity(self, args: dict) -> str:
        """
        Merge duplicate entities in kh_entities.
        Searches by canonical_name and aliases (case-insensitive substring match).
        """
        if not self.project_id:
            return "Nenhum contexto ativo. Selecione um contexto na Home primeiro."

        from core.knowledge_store import get_entities, merge_entities

        canonical_name  = (args.get("canonical_name") or "").strip()
        duplicate_names = [n.strip() for n in (args.get("duplicate_names") or []) if n.strip()]
        reason          = (args.get("reason") or "Mesma entidade com nomes diferentes").strip()

        if not canonical_name or not duplicate_names:
            return "❌ Forneça canonical_name e pelo menos um nome em duplicate_names."

        all_entities = get_entities(self.project_id, limit=500)
        if not all_entities:
            return (
                "Nenhuma entidade encontrada no Knowledge Hub para este projeto. "
                "Execute populate_knowledge_hub primeiro."
            )

        def _match(entity: dict, search: str) -> bool:
            s = search.lower()
            if s in (entity.get("canonical_name") or "").lower():
                return True
            return any(s in (a or "").lower() for a in (entity.get("aliases") or []))

        # Find keep entity
        keep_candidates = [e for e in all_entities if _match(e, canonical_name)]
        if not keep_candidates:
            return (
                f"❌ Nenhuma entidade encontrada com o nome '{canonical_name}'.\n"
                f"Sugestão: use parte do nome (ex: 'Pedro Gentil') ou verifique "
                f"o Grafo de Conhecimento para ver os nomes exatos."
            )
        # Prefer exact match; fallback to highest occurrence_count
        keep_entity = next(
            (e for e in keep_candidates
             if (e.get("canonical_name") or "").lower() == canonical_name.lower()),
            max(keep_candidates, key=lambda e: e.get("occurrence_count") or 1),
        )
        keep_id   = keep_entity["id"]
        keep_name = keep_entity.get("canonical_name", canonical_name)

        # Find discard entities
        discard_ids:   list[str] = []
        not_found:     list[str] = []
        found_names:   list[str] = []

        for dup_name in duplicate_names:
            candidates = [
                e for e in all_entities
                if e["id"] != keep_id and _match(e, dup_name)
            ]
            if not candidates:
                not_found.append(dup_name)
                continue
            # Pick best candidate (prefer exact match, else highest occurrence)
            best = next(
                (e for e in candidates
                 if (e.get("canonical_name") or "").lower() == dup_name.lower()),
                max(candidates, key=lambda e: e.get("occurrence_count") or 1),
            )
            if best["id"] not in discard_ids:
                discard_ids.append(best["id"])
                found_names.append(best.get("canonical_name", dup_name))

        if not discard_ids:
            msg = "❌ Nenhum dos nomes duplicados foi encontrado no Knowledge Hub.\n"
            if not_found:
                msg += f"Não encontrados: {', '.join(not_found)}\n"
            msg += f"Use o Grafo de Conhecimento para verificar os nomes exatos das entidades."
            return msg

        # Execute merge
        ok = merge_entities(self.project_id, keep_id, discard_ids)

        lines = [
            f"{'✅' if ok else '❌'} Fusão de entidades {'concluída' if ok else 'falhou'}.\n",
            f"Entidade mantida: **{keep_name}**",
            f"Absorvidas e removidas: {', '.join(found_names)}",
            f"Motivo: {reason}",
        ]
        if not_found:
            lines.append(f"\n⚠️ Não encontrados (verifique os nomes): {', '.join(not_found)}")
        if ok:
            lines.append(
                "\nO Grafo de Conhecimento será atualizado na próxima visualização. "
                "Os aliases e histórico de reuniões foram transferidos para a entidade canônica."
            )
        return "\n".join(lines)

    # ── populate_knowledge_hub ────────────────────────────────────────────────

    def _populate_knowledge_hub(self, args: dict) -> str:
        """Run AgentKnowledgeExtractor on one or more meetings to populate kh_* tables."""
        if not self.llm_config:
            return (
                "❌ Configuração LLM não disponível. "
                "Certifique-se de que a chave de API está configurada no Assistente."
            )
        if not self.project_id:
            return (
                "Nenhum contexto ativo. Selecione um contexto na Home primeiro "
                "ou use set_active_project."
            )

        from core.knowledge_store import kh_tables_exist
        if not kh_tables_exist():
            return (
                "❌ As tabelas do Knowledge Hub não existem no Supabase. "
                "Execute setup/supabase_schema_knowledge_hub.sql no SQL Editor do Supabase primeiro."
            )

        meeting_numbers = args.get("meeting_numbers") or None
        overwrite       = bool(args.get("overwrite", False))

        provider_cfg = self.llm_config.get("provider_cfg", {})
        client_info  = {"api_key": self.llm_config.get("api_key", "")}

        # Fetch meetings
        meetings = self._get_meetings()
        if meeting_numbers:
            num_set  = set(meeting_numbers)
            meetings = [m for m in meetings if m.get("meeting_number") in num_set]

        if not meetings:
            return "Nenhuma reunião encontrada com os critérios fornecidos."

        from agents.agent_knowledge_extractor import AgentKnowledgeExtractor
        agent = AgentKnowledgeExtractor(client_info, provider_cfg)

        ok_list, skip_list, fail_list = [], [], []

        for m in meetings:
            num       = m.get("meeting_number", "?")
            title     = m.get("title") or f"Reunião {num}"
            mid       = m.get("id")
            transcript = (m.get("transcript_clean") or m.get("transcript_raw") or "").strip()

            if not transcript or len(transcript) < 100:
                skip_list.append(f"Reunião {num} — '{title}' (sem transcrição)")
                continue

            try:
                if overwrite and mid:
                    # Clear existing facts/contradictions for this meeting before re-extraction
                    from modules.supabase_client import get_supabase_client
                    db = get_supabase_client()
                    if db:
                        db.table("kh_facts").delete().contains(
                            "source_meeting_ids", [mid]
                        ).eq("project_id", self.project_id).execute()
                        db.table("kh_contradictions").delete().eq(
                            "meeting_a_id", mid
                        ).eq("project_id", self.project_id).execute()

                from core.knowledge_hub import KnowledgeHub
                mini_hub = KnowledgeHub()
                mini_hub.transcript_raw   = transcript
                mini_hub.transcript_clean = transcript

                agent.run(
                    mini_hub,
                    output_language="Auto-detect",
                    meeting_id=mid,
                    project_id=self.project_id,
                )
                ok_list.append(f"Reunião {num} — '{title}'")
            except Exception as exc:
                fail_list.append(f"Reunião {num} — '{title}': {exc}")

        lines = [
            f"Knowledge Hub — extração concluída",
            f"Projeto: {self.project_id}",
            f"Modo: {'reescrita (overwrite)' if overwrite else 'acumulativo'}",
            "",
            f"✅ Processadas ({len(ok_list)}):",
        ]
        for item in ok_list:
            lines.append(f"  • {item}")
        if skip_list:
            lines.append(f"\n⏭️ Ignoradas — sem transcrição ({len(skip_list)}):")
            for item in skip_list:
                lines.append(f"  • {item}")
        if fail_list:
            lines.append(f"\n❌ Falhas ({len(fail_list)}):")
            for item in fail_list:
                lines.append(f"  • {item}")

        lines.append(
            "\nConsulte a página 🧠 Knowledge Hub para visualizar o conhecimento extraído."
        )
        return "\n".join(lines)

    # ── Document tools ────────────────────────────────────────────────────────

    def list_meeting_documents(
        self,
        meeting_number: int | None = None,
        doc_type: str | None = None,
        category: str | None = None,
    ) -> str:
        """List documents stored for this project, optionally filtered by category or type."""
        from modules.document_store import list_documents, get_document_types, get_types_by_category
        meeting_id: str | None = None
        if meeting_number is not None:
            meetings = self._get_meetings()
            if meeting_number < 1 or meeting_number > len(meetings):
                return f"Reunião #{meeting_number} não encontrada."
            meeting_id = meetings[meeting_number - 1]["id"]

        # Resolve category → list of doc_type codes
        category_codes: list[str] | None = None
        if category:
            grouped = get_types_by_category()
            # Case-insensitive match on category name
            cat_lower = category.strip().lower()
            matched_cat = next(
                (k for k in grouped if k.lower() == cat_lower or cat_lower in k.lower()),
                None,
            )
            if matched_cat:
                category_codes = [t["code"] for t in grouped[matched_cat]]
            else:
                return (
                    f"Categoria '{category}' não encontrada. "
                    "Use get_document_types para ver as categorias disponíveis."
                )

        # Fetch — if category filter, fetch all and filter client-side
        # (Supabase doesn't support IN filter easily in list_documents)
        if category_codes:
            all_docs: list[dict] = []
            for code in category_codes:
                all_docs.extend(list_documents(
                    project_id=self.project_id,
                    meeting_id=meeting_id,
                    doc_type=code,
                    limit=200,
                ))
            # Deduplicate by id
            seen: set[str] = set()
            docs = [d for d in all_docs if not (d["id"] in seen or seen.add(d["id"]))]  # type: ignore[func-returns-value]
        else:
            docs = list_documents(
                project_id=self.project_id,
                meeting_id=meeting_id,
                doc_type=doc_type,
                limit=100,
            )

        if not docs:
            filtro = f" na categoria '{category}'" if category else (f" do tipo '{doc_type}'" if doc_type else "")
            return f"Nenhum documento encontrado{filtro} para este projeto."

        type_labels = {t["code"]: t["label"] for t in get_document_types()}

        filter_desc = ""
        if category:
            filter_desc = f" — categoria **{category}**"
        elif doc_type:
            filter_desc = f" — tipo **{type_labels.get(doc_type, doc_type)}**"

        lines = [
            f"**{len(docs)} documento(s) encontrado(s){filter_desc}:**\n",
            f"> Para visualizar o conteúdo completo acesse **📄 Documentos do Contexto** no menu lateral.\n",
        ]
        for i, d in enumerate(docs, 1):
            tipo = type_labels.get(d.get("doc_type", ""), d.get("doc_type", "—"))
            # Prefer doc_date, then doc_date_estimated, then created_at
            ref_date = (
                d.get("doc_date")
                or d.get("doc_date_estimated")
                or (d.get("created_at") or "")[:10]
            )
            date_label = "Data ref." if d.get("doc_date") or d.get("doc_date_estimated") else "Cadastrado"
            meeting_note = f" · vinculado à reunião" if d.get("meeting_id") else ""
            lines.append(
                f"{i}. **{d['title']}**\n"
                f"   - Tipo: {tipo}{meeting_note}\n"
                f"   - {date_label}: {ref_date or '—'}\n"
                f"   - Arquivo: {d.get('file_name') or '—'}\n"
                f"   - ID: `{d['id']}`\n"
            )
        return "\n".join(lines)

    def get_document_content(self, doc_id: str) -> str:
        """Return the full content of a document by ID."""
        from modules.document_store import get_document
        doc = get_document(doc_id)
        if not doc:
            return f"Documento com ID `{doc_id}` não encontrado."
        content = doc.get("content_text", "")
        if not content:
            return f"O documento **{doc['title']}** não tem conteúdo armazenado."
        header = (
            f"**{doc['title']}**\n"
            f"Tipo: {doc.get('doc_type', '—')} | "
            f"Arquivo: {doc.get('file_name') or '—'} | "
            f"Cadastrado: {(doc.get('created_at') or '')[:10]}\n\n"
        )
        # Cap at 8 000 chars for assistant context
        if len(content) > 8000:
            body = content[:6000] + "\n\n[... conteúdo truncado ...]\n\n" + content[-1000:]
        else:
            body = content
        return header + body

    def search_documents(self, query: str, mode: str = "semantic") -> str:
        """Search documents semantically or by keyword."""
        from modules.document_store import search_documents_semantic, search_documents_keyword, get_document_types
        type_labels = {t["code"]: t["label"] for t in get_document_types()}
        nav_hint = "> Para ver o documento completo acesse **📄 Documentos do Contexto** no menu lateral.\n"

        if mode == "keyword":
            results = search_documents_keyword(query, self.project_id, limit=10)
            if not results:
                return f"Nenhum documento encontrado com a palavra-chave: '{query}'."
            lines = [f"**{len(results)} documento(s) encontrado(s) para '{query}':**\n", nav_hint]
            for d in results:
                tipo = type_labels.get(d.get("doc_type", ""), d.get("doc_type", "—"))
                ref_date = d.get("doc_date") or d.get("doc_date_estimated") or (d.get("created_at") or "")[:10]
                lines.append(
                    f"- **{d['title']}** · {tipo} · {ref_date or '—'} — ID: `{d['id']}`"
                )
            return "\n".join(lines)
        else:
            results = search_documents_semantic(query, self.project_id, limit=5, threshold=0.35)
            if not results:
                return (
                    f"Nenhum trecho encontrado semanticamente para: '{query}'. "
                    "Verifique se os documentos foram indexados (📄 Documentos do Contexto → aba Biblioteca → Re-indexar)."
                )
            lines = [f"**Trechos relevantes encontrados para '{query}':**\n", nav_hint]
            for r in results:
                sim = r.get("similarity", 0)
                tipo = type_labels.get(r.get("doc_type", ""), r.get("doc_type", "—"))
                lines.append(
                    f"---\n"
                    f"**{r['doc_title']}** · {tipo} · Similaridade: {sim:.2f}\n\n"
                    f"{r['content']}\n"
                )
            return "\n".join(lines)

    def get_document_types_tool(self) -> str:
        """Return the full document taxonomy grouped by category."""
        from modules.document_store import get_types_by_category
        grouped = get_types_by_category()
        if not grouped:
            return "Taxonomia não disponível. Execute a migration SQL de documentos."
        lines = ["**Taxonomia de tipos de documentos:**\n"]
        for category, types in grouped.items():
            lines.append(f"\n**{category}**")
            for t in types:
                lines.append(f"- `{t['code']}` — {t['label']}")
        return "\n".join(lines)

    def suggest_document_title(self, doc_id: str, apply: bool = False) -> str:
        """Suggest (and optionally apply) an AI-generated title for a document."""
        from modules.document_store import get_document, update_document_meta
        doc = get_document(doc_id)
        if not doc:
            return f"Documento com ID `{doc_id}` não encontrado."
        content = doc.get("content_text", "")
        if not content:
            return f"O documento **{doc['title']}** não tem conteúdo armazenado — não é possível sugerir título."

        # LLM call using current provider
        try:
            provider_cfg = self.llm_config.get("provider_cfg", {})
            api_key      = self.llm_config.get("api_key", "")
            model        = self.llm_config.get("model", "deepseek-v4-flash")
            client_type  = provider_cfg.get("client_type", "openai_compatible")
            system = "Você é um assistente especialista em gestão documental."
            user   = (
                "Analise o início do documento abaixo e proponha um título conciso e descritivo "
                "(máximo 80 caracteres). Responda APENAS com o título sugerido, sem aspas, sem explicação.\n\n"
                + content[:3000]
            )
            if client_type == "anthropic":
                import anthropic
                ac  = anthropic.Anthropic(api_key=api_key)
                msg = ac.messages.create(model=model, max_tokens=100, system=system,
                                         messages=[{"role": "user", "content": user}])
                suggestion = (msg.content[0].text or "").strip()
            else:
                from openai import OpenAI
                client = OpenAI(api_key=api_key, base_url=provider_cfg.get("base_url"))
                kwargs: dict = dict(
                    model=model,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                    max_tokens=512,  # deepseek-v4 uses thinking tokens before content — 100 is not enough
                )
                if not provider_cfg.get("reasoning_effort") and "deepseek-v4" not in model.lower():
                    kwargs["temperature"] = 0.3
                resp   = client.chat.completions.create(**kwargs)
                suggestion = (resp.choices[0].message.content or "").strip()
        except Exception as e:
            return f"Erro ao chamar o LLM para sugestão de título: {e}"

        if not suggestion:
            return "O modelo não retornou uma sugestão de título."

        old_title = doc.get("title", "")
        if apply:
            ok = update_document_meta(doc_id, title=suggestion)
            if ok:
                return (
                    f"Título atualizado com sucesso!\n"
                    f"- **Anterior:** {old_title}\n"
                    f"- **Novo:** {suggestion}"
                )
            return f"Sugestão gerada (**{suggestion}**) mas falhou ao salvar no banco."
        else:
            return (
                f"Sugestão de título para o documento:\n"
                f"- **Atual:** {old_title}\n"
                f"- **Sugerido:** {suggestion}\n\n"
                f"Para aplicar, use `suggest_document_title(doc_id='{doc_id}', apply=true)`."
            )

    # ── Ajuda P2D — conceitos, funcionalidades, componentes ───────────────────

    def get_p2d_help(self, topic: str) -> str:
        """Responde perguntas sobre o P2D buscando no glossário e no skill guide."""
        import re
        topic_lower = topic.lower().strip()

        # 1. Busca no glossário
        try:
            from modules.glossary_data import search_glossary as _search, TAG_META
            gloss_results = _search(topic, max_results=4)
        except Exception:
            gloss_results = []

        # 2. Busca por seções relevantes em skill_assistant.md
        skill_sections: list[str] = []
        try:
            import os
            skill_path = os.path.join(os.path.dirname(__file__), "..", "skills", "skill_assistant.md")
            skill_path = os.path.abspath(skill_path)
            with open(skill_path, encoding="utf-8") as f:
                skill_text = f.read()
            # Split on ## headers (keep header with content)
            raw_sections = re.split(r"\n(?=## )", skill_text)
            for sec in raw_sections:
                if topic_lower in sec.lower():
                    # Trim to 800 chars to avoid huge blocks
                    skill_sections.append(sec[:800].strip())
        except Exception:
            pass

        if not gloss_results and not skill_sections:
            return (
                f"Não encontrei informações sobre **'{topic}'** no glossário ou "
                f"no guia do Process2Diagram.\n\n"
                f"Tente termos mais específicos como: BPMN, gateway, lane, pool, "
                f"embedding, RAG, SBVR, BMM, DMN, IBIS, KnowledgeHub, pipeline, "
                f"spaCy, Supabase, pgvector, CKF, ROI-TR, token, Mermaid."
            )

        parts: list[str] = [f"## Informações sobre '{topic}' no Process2Diagram\n"]

        if gloss_results:
            parts.append("### Glossário\n")
            for e in gloss_results:
                en_part = f" *(en: {e['en']})*" if e.get("en") else ""
                tag_label = TAG_META.get(e.get("tag", ""), {}).get("label", "") if gloss_results else ""
                parts.append(f"**{e['term']}**{en_part}  `{tag_label}`")
                parts.append(e.get("def_", ""))
                if e.get("example"):
                    parts.append(f"> Exemplo: {e['example']}")
                if e.get("related"):
                    parts.append(f"*Ver também: {', '.join(e['related'])}*")
                parts.append("")

        if skill_sections:
            parts.append("### Guia do Process2Diagram\n")
            for sec in skill_sections[:3]:
                parts.append(sec)
                parts.append("")

        return "\n".join(parts)

    # ── IBIS / Argumentação ───────────────────────────────────────────────────

    def _load_ibis_questions(self, topic_filter: str | None = None,
                             meeting_number: int | None = None) -> list[dict]:
        """Load and optionally filter IBIS questions from all meetings in the project."""
        import json
        import re

        from modules.supabase_client import get_supabase_client
        client = get_supabase_client()
        if not client:
            return []
        try:
            q = (
                client.table("meetings")
                .select("id, meeting_number, title, meeting_date, argumentation_json")
                .eq("project_id", self.project_id)
                .not_.is_("argumentation_json", "null")
                .order("meeting_number")
            )
            if meeting_number:
                q = q.eq("meeting_number", meeting_number)
            rows = q.execute().data or []
        except Exception:
            return []

        _STOP = {
            "a","o","as","os","de","do","da","dos","das","em","no","na","nos","nas",
            "para","que","um","uma","uns","umas","e","ou","se","com","por","mas","é",
            "ser","ter","ao","à","aos","às","não","como","mais","deve","há","esta",
            "este","seu","sua","seus","suas","foi","sido","sendo","está","são",
        }

        def _tok(text: str) -> set:
            return {
                w for w in re.sub(r"[^\w\sáéíóúâêôãç]", " ", text.lower()).split()
                if w not in _STOP and len(w) > 2
            }

        kw_toks = _tok(topic_filter) if topic_filter else set()

        all_qs: list[dict] = []
        for row in rows:
            raw = row.get("argumentation_json") or ""
            if not raw:
                continue
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
                qs = data.get("questions", [])
            except Exception:
                continue
            for q2 in qs:
                q2["_mid"]    = row["id"]
                q2["_mnum"]   = row.get("meeting_number")
                q2["_mtitle"] = row.get("title") or f"Reunião {row.get('meeting_number')}"
                q2["_mdate"]  = str(row.get("meeting_date") or "")
                all_qs.append(q2)

        if not kw_toks:
            return all_qs

        def _matches(q3: dict) -> bool:
            text = " ".join([
                q3.get("statement", ""),
                " ".join(a.get("description", "") for a in q3.get("alternatives", [])),
                " ".join(p for a in q3.get("alternatives", []) for p in (a.get("pros") or [])),
                " ".join(c for a in q3.get("alternatives", []) for c in (a.get("cons") or [])),
            ])
            ttoks = _tok(text)
            return bool(kw_toks & ttoks)

        return [q for q in all_qs if _matches(q)]

    def search_ibis_debates(
        self,
        query: str,
        meeting_number: int | None = None,
        resolution_filter: str = "all",
    ) -> str:
        """Keyword search over IBIS questions and return structured text."""
        qs = self._load_ibis_questions(topic_filter=query, meeting_number=meeting_number)
        if not qs:
            return f"Nenhuma questão IBIS encontrada para o tema '{query}'."

        if resolution_filter != "all":
            qs = [q for q in qs if (q.get("resolution") or {}).get("type") == resolution_filter]
        if not qs:
            return f"Nenhuma questão IBIS com status '{resolution_filter}' encontrada para '{query}'."

        _res_lbl = {
            "decided":    "✅ Decidida",
            "deferred":   "⏳ Adiada",
            "unresolved": "❓ Em aberto",
        }

        lines = [
            f"## Debates IBIS sobre '{query}' — {len(qs)} questão(ões) encontrada(s)\n"
        ]

        # Group by meeting
        from collections import defaultdict
        by_mtg: dict = defaultdict(list)
        for q in qs:
            by_mtg[q["_mnum"]].append(q)

        for mnum in sorted(by_mtg.keys()):
            mtg_qs = by_mtg[mnum]
            mtitle = mtg_qs[0]["_mtitle"]
            mdate  = mtg_qs[0]["_mdate"]
            lines.append(f"\n### Reunião {mnum} — {mtitle}" + (f" ({mdate})" if mdate else ""))

            for q in mtg_qs:
                res     = q.get("resolution") or {}
                rt      = res.get("type", "unresolved")
                rb      = q.get("raised_by", "")
                status  = _res_lbl.get(rt, rt)
                lines.append(f"\n**{q.get('id','?')}** {status} — {q.get('statement','')}")
                if rb:
                    lines.append(f"  *Levantada por: {rb}*")

                alts = q.get("alternatives", [])
                if alts:
                    lines.append("  **Alternativas:**")
                    for alt in alts:
                        chosen = " ✅ **(eleita)**" if alt.get("was_chosen") else ""
                        lines.append(f"  - **{alt.get('id','?')}**{chosen}: {alt.get('description','')}")
                        if alt.get("proposed_by"):
                            lines.append(f"    - Proposta por: {alt['proposed_by']}")
                        pros = alt.get("pros") or []
                        cons = alt.get("cons") or []
                        if pros:
                            lines.append("    - A favor: " + "; ".join(pros))
                        if cons:
                            lines.append("    - Contra: " + "; ".join(cons))
                        sup = alt.get("supported_by") or []
                        opp = alt.get("opposed_by") or []
                        if sup or opp:
                            parts = []
                            if sup:
                                parts.append("A favor: " + ", ".join(sup))
                            if opp:
                                parts.append("Contra: " + ", ".join(opp))
                            lines.append("    - " + " | ".join(parts))

                if res.get("rationale"):
                    lines.append(f"  → **Resolução:** {res['rationale']}")
                if res.get("with_caveats"):
                    lines.append("  → **Ressalvas:** " + "; ".join(res["with_caveats"]))

        return "\n".join(lines)

    def get_ibis_timeline(self, topic: str | None = None) -> str:
        """Stacked bar chart of IBIS resolution status per meeting, with text summary."""
        import plotly.graph_objects as go
        from collections import defaultdict, Counter

        qs = self._load_ibis_questions(topic_filter=topic)
        if not qs:
            msg = f"Nenhum debate IBIS encontrado" + (f" sobre '{topic}'" if topic else "") + "."
            return msg

        by_mtg: dict = defaultdict(list)
        for q in qs:
            by_mtg[q["_mnum"]].append(q)

        sorted_mnums = sorted(by_mtg.keys())
        labels = [f"R.{m}" for m in sorted_mnums]

        decided_cnts    = [sum(1 for q in by_mtg[m] if (q.get("resolution") or {}).get("type") == "decided")    for m in sorted_mnums]
        deferred_cnts   = [sum(1 for q in by_mtg[m] if (q.get("resolution") or {}).get("type") == "deferred")   for m in sorted_mnums]
        unresolved_cnts = [sum(1 for q in by_mtg[m] if (q.get("resolution") or {}).get("type") == "unresolved") for m in sorted_mnums]

        fig = go.Figure(data=[
            go.Bar(name="✅ Decididas",  x=labels, y=decided_cnts,    marker_color="#22c55e"),
            go.Bar(name="⏳ Adiadas",    x=labels, y=deferred_cnts,   marker_color="#fbbf24"),
            go.Bar(name="❓ Em aberto",  x=labels, y=unresolved_cnts, marker_color="#f87171"),
        ])
        fig.update_layout(barmode="stack")
        title = f"Evolução dos Debates IBIS por Reunião"
        if topic:
            title += f" — '{topic}'"
        self._dark_layout(fig, title)
        fig.update_layout(
            xaxis_title="Reunião",
            yaxis_title="Nº de questões",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        self._pending_charts.append(fig.to_dict())

        # Text summary
        total     = len(qs)
        n_decided = sum(decided_cnts)
        n_def     = sum(deferred_cnts)
        n_unres   = sum(unresolved_cnts)
        pct       = round(n_decided / total * 100) if total else 0
        summary   = (
            f"📊 Gráfico gerado: {total} debate(s) em {len(sorted_mnums)} reunião(ões)"
            + (f" sobre '{topic}'" if topic else "")
            + f" — {n_decided} decidido(s) ({pct}%), {n_def} adiado(s), {n_unres} em aberto."
        )
        return summary

    def generate_ibis_map(self, topic: str | None = None) -> str:
        """Plotly network graph of IBIS questions and alternatives, grouped by meeting."""
        import plotly.graph_objects as go

        qs = self._load_ibis_questions(topic_filter=topic)
        if not qs:
            return f"Nenhum debate IBIS encontrado" + (f" sobre '{topic}'" if topic else "") + "."

        _RES_BORDER = {
            "decided":    "#22c55e",
            "deferred":   "#fbbf24",
            "unresolved": "#f87171",
        }

        # Group by meeting
        from collections import defaultdict
        by_mtg: dict = defaultdict(list)
        for q in qs:
            by_mtg[q["_mnum"]].append(q)
        sorted_mnums = sorted(by_mtg.keys())

        # Layout constants
        X_GAP  = 6.0   # horizontal gap between meetings
        Y_GAP  = 3.5   # vertical gap between questions within a meeting
        A_Y    = 2.2   # depth of alternatives below question
        A_XGAP = 1.4   # horizontal spread of alternatives

        node_x, node_y, node_color, node_size, node_symbol = [], [], [], [], []
        node_hover, node_label = [], []
        edge_x, edge_y = [], []

        # Annotation positions for meeting headers
        mtg_annotations = []

        for mx, mnum in enumerate(sorted_mnums):
            mtg_qs  = by_mtg[mnum]
            mtitle  = mtg_qs[0]["_mtitle"]
            x_base  = mx * X_GAP
            mtg_annotations.append(dict(
                x=x_base, xref="x",
                y=1.0, yref="paper",
                text=f"<b>R{mnum}</b>",
                showarrow=False,
                font=dict(size=11, color="#e2e8f0", family="monospace"),
                xanchor="center",
                yanchor="bottom",
                bgcolor="#1e3a5f",
                bordercolor="#2563eb",
                borderwidth=1,
                borderpad=3,
            ))

            for qi, q in enumerate(mtg_qs):
                q_x   = x_base
                q_y   = -(qi * Y_GAP)
                qid   = q.get("id", "Q?")
                rt    = (q.get("resolution") or {}).get("type", "unresolved")
                rat   = (q.get("resolution") or {}).get("rationale", "")
                rb    = q.get("raised_by", "")
                stmt  = q.get("statement", "")
                alts  = q.get("alternatives", [])
                n_a   = len(alts)

                # Question node — globally unique label: "Q1<br>R9"
                node_x.append(q_x);  node_y.append(q_y)
                node_color.append(_RES_BORDER.get(rt, "#f87171"))
                node_size.append(18)
                node_symbol.append("circle")
                node_label.append(f"{qid}<br>R{mnum}")
                tip = (
                    f"<b>{qid}</b> — Reunião {mnum}<br>"
                    f"{stmt}<br><br>"
                    + (f"Levantada por: {rb}<br>" if rb else "")
                    + f"Status: {rt}"
                    + (f"<br><i>Resolução: {rat[:100]}</i>" if rat else "")
                    + f"<br>{n_a} alternativa(s)"
                )
                node_hover.append(tip)

                # Alternative nodes
                for ai, alt in enumerate(alts):
                    a_x = q_x + (ai - (n_a - 1) / 2) * A_XGAP
                    a_y = q_y - A_Y

                    # Edge Q → A
                    edge_x.extend([q_x, a_x, None])
                    edge_y.extend([q_y, a_y, None])

                    chosen  = alt.get("was_chosen", False)
                    a_color = "#16a34a" if chosen else "#2563eb"
                    pros    = alt.get("pros") or []
                    cons    = alt.get("cons") or []
                    pb      = alt.get("proposed_by", "")
                    a_tip   = (
                        f"<b>{alt.get('id','?')}</b> — R{mnum}"
                        + (" ✅ eleita" if chosen else "")
                        + f"<br>{alt.get('description','')}"
                        + (f"<br>Proposta por: {pb}" if pb else "")
                        + f"<br>+{len(pros)} prós / -{len(cons)} contras"
                    )
                    if pros:
                        a_tip += "<br>Prós: " + "; ".join(pros[:2]) + ("…" if len(pros) > 2 else "")
                    if cons:
                        a_tip += "<br>Contras: " + "; ".join(cons[:2]) + ("…" if len(cons) > 2 else "")

                    node_x.append(a_x);  node_y.append(a_y)
                    node_color.append(a_color)
                    node_size.append(12)
                    node_symbol.append("diamond")
                    node_label.append(alt.get("id", "A?"))
                    node_hover.append(a_tip)

        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            mode="lines",
            line=dict(width=1.2, color="#334155"),
            hoverinfo="none",
            showlegend=False,
        )

        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode="markers+text",
            marker=dict(
                size=node_size,
                color=node_color,
                symbol=node_symbol,
                line=dict(width=1.5, color="#0d1b2a"),
            ),
            text=node_label,
            textposition="top center",
            textfont=dict(size=9, color="#f1f5f9"),
            hovertext=node_hover,
            hoverinfo="text",
            showlegend=False,
        )

        fig = go.Figure(data=[edge_trace, node_trace])

        # Legend as extra traces
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
            marker=dict(size=10, color="#f97316", symbol="circle"),
            name="Questão (Issue)", showlegend=True))
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
            marker=dict(size=9, color="#2563eb", symbol="diamond"),
            name="Alternativa", showlegend=True))
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
            marker=dict(size=9, color="#16a34a", symbol="diamond"),
            name="Alternativa eleita", showlegend=True))
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
            marker=dict(size=10, color="#22c55e", symbol="circle"),
            name="Decidida", showlegend=True))
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
            marker=dict(size=10, color="#fbbf24", symbol="circle"),
            name="Adiada", showlegend=True))
        fig.add_trace(go.Scatter(x=[None], y=[None], mode="markers",
            marker=dict(size=10, color="#f87171", symbol="circle"),
            name="Em aberto", showlegend=True))

        title_txt = "Mapa Visual IBIS" + (f" — '{topic}'" if topic else f" — {len(qs)} questão(ões)")
        max_y = max((len(v) * Y_GAP for v in by_mtg.values()), default=1)
        fig.update_layout(
            paper_bgcolor="#0d1b2a",
            plot_bgcolor="#0d1b2a",
            font_color="#f1f5f9",
            title=dict(text=title_txt, font=dict(size=14, color="#f1f5f9")),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            margin=dict(l=20, r=20, t=100, b=20),
            annotations=mtg_annotations,
            legend=dict(
                bgcolor="#1e293b", bordercolor="#334155", borderwidth=1,
                font=dict(size=11, color="#f1f5f9"),
                orientation="h", yanchor="bottom", y=1.04, xanchor="left", x=0,
            ),
            height=max(420, int(max_y * 60) + 180),
        )

        self._pending_charts.append(fig.to_dict())
        n_alts = sum(len(q.get("alternatives", [])) for q in qs)
        return (
            f"🗺️ Mapa IBIS gerado: {len(qs)} questão(ões) e {n_alts} alternativa(s)"
            + (f" sobre '{topic}'" if topic else "")
            + f" em {len(sorted_mnums)} reunião(ões)."
        )

    # ── Cross-meeting / agenda ────────────────────────────────────────────────

    def generate_next_agenda(self, topic: str | None = None) -> str:
        """Suggest an agenda for the next meeting based on deferred IBIS items and pending action items."""
        from core.project_store import list_argumentation_by_project

        kw = topic.lower() if topic else None

        # ── 1. Deferred IBIS questions ────────────────────────────────────────
        all_ibis = list_argumentation_by_project(self.project_id)
        deferred = [
            q for q in all_ibis
            if (q.get("resolution") or {}).get("type") == "deferred"
            and (kw is None or kw in q.get("statement", "").lower())
        ]

        # ── 2. Action items from minutes_md ───────────────────────────────────
        pending_actions: list[tuple[int, str]] = []
        for m in self._get_meetings():
            section = self._section(
                m.get("minutes_md") or "",
                "Itens de Ação", "Action Items", "Ações",
            )
            if not section:
                continue
            mnum = m.get("meeting_number") or 0
            for line in section.splitlines():
                line = line.strip()
                if line and (kw is None or kw in line.lower()):
                    pending_actions.append((mnum, line))

        # ── 3. Build agenda ───────────────────────────────────────────────────
        topic_str = f" sobre '{topic}'" if topic else ""
        lines: list[str] = [
            f"## Sugestão de Pauta — Próxima Reunião{topic_str}\n",
            "_Gerado automaticamente com base em pendências do projeto_\n",
        ]

        # Opening
        lines.append("\n### 1. Abertura e Alinhamento (5 min)")
        lines.append("- Confirmação de quórum e registro de participantes")
        lines.append("- Aprovação da pauta")

        # Pending action items
        lines.append(f"\n### 2. Acompanhamento de Encaminhamentos ({min(15, len(pending_actions) * 2 + 5)} min)")
        if pending_actions:
            shown = pending_actions[:6]
            for mnum, item in shown:
                lines.append(f"- **R{mnum}:** {item[:110]}")
            if len(pending_actions) > 6:
                lines.append(f"- _(+{len(pending_actions) - 6} encaminhamento(s) — verificar atas anteriores)_")
        else:
            lines.append("- Nenhum encaminhamento pendente identificado nas atas.")

        # Deferred IBIS decisions
        lines.append(f"\n### 3. Retomada de Decisões Adiadas ({10 + min(30, len(deferred) * 5)} min)")
        if deferred:
            for q in deferred[:6]:
                mnum = q.get("_meeting_number", "?")
                stmt  = q.get("statement", "")
                res   = q.get("resolution") or {}
                n_alt = len(q.get("alternatives") or [])
                lines.append(f"- **{q.get('id','?')}** [R{mnum}]: {stmt}")
                if n_alt:
                    lines.append(f"  _{n_alt} alternativa(s) já mapeada(s) para análise_")
                if res.get("rationale"):
                    lines.append(f"  _Motivo do adiamento: {res['rationale'][:90]}_")
            if len(deferred) > 6:
                lines.append(f"- _(+{len(deferred) - 6} outros debates adiados)_")
        else:
            lines.append("- Nenhuma decisão IBIS adiada identificada.")

        # New topics
        lines.append("\n### 4. Novos Tópicos e Deliberações (20 min)")
        lines.append("- [Inserir conforme agenda do projeto]")

        # Closure
        lines.append("\n### 5. Encaminhamentos e Encerramento (10 min)")
        lines.append("- Registro das decisões tomadas e responsáveis")
        lines.append("- Definição de prazos e próxima reunião")

        total_items = len(deferred) + len(pending_actions)
        lines.append(
            f"\n---\n*Fontes: {len(deferred)} debate(s) IBIS adiado(s) e "
            f"{len(pending_actions)} encaminhamento(s) nas atas.*"
            + (f" Filtro: '{topic}'." if topic else "")
        )
        if total_items == 0:
            lines.append("\n> Nenhum item pendente encontrado. O projeto pode estar em dia!")

        return "\n".join(lines)

    # ── Cross-meeting clustering ──────────────────────────────────────────────

    def cluster_topic_decisions(
        self,
        topic: str,
        artifact_type: str = "all",
    ) -> str:
        """Groups DMN decisions, IBIS debates, and minutes decisions about a topic across all meetings."""
        from core.project_store import list_dmn_by_project, list_argumentation_by_project
        from collections import defaultdict

        kw = topic.lower()

        def _match(text: str) -> bool:
            return kw in (text or "").lower()

        results: dict[int, dict] = defaultdict(lambda: {"title": "", "date": "", "dmn": [], "ibis": [], "minutes": []})

        # ── DMN decisions ──
        if artifact_type in ("all", "dmn"):
            for d in list_dmn_by_project(self.project_id):
                label = d.get("label", "") or d.get("name", "")
                desc  = d.get("description", "")
                if _match(label) or _match(desc):
                    mnum = d.get("_meeting_number") or 0
                    results[mnum]["title"] = d.get("_meeting_title", "")
                    results[mnum]["date"]  = d.get("_meeting_date", "")
                    hp = d.get("hit_policy", "U")
                    inputs  = [i.get("label", "") for i in (d.get("inputs") or [])]
                    outputs = [o.get("label", "") for o in (d.get("outputs") or [])]
                    n_rules = len(d.get("rules") or [])
                    results[mnum]["dmn"].append(
                        f"**{label}** (hit_policy={hp}, {n_rules} regra(s))"
                        + (f" | inputs: {', '.join(inputs)}" if inputs else "")
                        + (f" | outputs: {', '.join(outputs)}" if outputs else "")
                        + (f"\n    _{desc}_" if desc else "")
                    )

        # ── IBIS questions ──
        if artifact_type in ("all", "ibis"):
            for q in list_argumentation_by_project(self.project_id):
                stmt = q.get("statement", "")
                if _match(stmt) or any(_match(a.get("description", "")) for a in (q.get("alternatives") or [])):
                    mnum = q.get("_meeting_number") or 0
                    results[mnum]["title"] = results[mnum]["title"] or q.get("_meeting_title", "")
                    results[mnum]["date"]  = results[mnum]["date"] or q.get("_meeting_date", "")
                    res   = q.get("resolution") or {}
                    rtype = res.get("type", "unresolved")
                    rlbl  = {"decided": "✅ Decidida", "deferred": "⏳ Adiada"}.get(rtype, "❓ Em aberto")
                    entry = f"**{q.get('id','?')}** {rlbl}: {stmt}"
                    if res.get("rationale"):
                        entry += f"\n    → {res['rationale']}"
                    results[mnum]["ibis"].append(entry)

        # ── Minutes decisions ──
        if artifact_type in ("all", "minutes"):
            for m in self._get_meetings():
                minutes_md = m.get("minutes_md") or ""
                section    = self._section(minutes_md, "Decisões", "Decisions")
                if not section:
                    continue
                matched = [
                    line.strip() for line in section.splitlines()
                    if _match(line)
                ]
                if matched:
                    mnum = m.get("meeting_number") or 0
                    results[mnum]["title"] = results[mnum]["title"] or m.get("title", "")
                    results[mnum]["date"]  = results[mnum]["date"] or str(m.get("meeting_date") or "")
                    results[mnum]["minutes"].extend(matched)

        if not results:
            return f"Nenhum artefato encontrado com o tema '{topic}'."

        lines = [f"## Decisões sobre '{topic}' em {len(results)} reunião(ões)\n"]
        for mnum in sorted(results.keys()):
            r    = results[mnum]
            mtit = r["title"] or f"Reunião {mnum}"
            mdt  = r["date"]
            lines.append(f"\n### Reunião {mnum} — {mtit}" + (f" ({mdt})" if mdt else ""))

            if r["dmn"]:
                lines.append(f"\n**Decisões DMN ({len(r['dmn'])}):**")
                for item in r["dmn"]:
                    lines.append(f"- {item}")

            if r["ibis"]:
                lines.append(f"\n**Debates IBIS ({len(r['ibis'])}):**")
                for item in r["ibis"]:
                    lines.append(f"- {item}")

            if r["minutes"]:
                lines.append(f"\n**Ata — Decisões ({len(r['minutes'])}):**")
                for item in r["minutes"]:
                    lines.append(f"- {item}")

        total = sum(len(r["dmn"]) + len(r["ibis"]) + len(r["minutes"]) for r in results.values())
        lines.append(f"\n---\n*Total: {total} referência(s) ao tema '{topic}' em {len(results)} reunião(ões).*")
        return "\n".join(lines)

    # ── A2UI — renderização inline no chat ────────────────────────────────────

    def show_bpmn_diagram(
        self,
        process_name: str | None = None,
        meeting_number: int | None = None,
    ) -> str:
        """Fetch current BPMN XML and queue for inline rendering in the chat."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."
        pid = self.project_id
        try:
            q = db.table("bpmn_processes").select("id, name").eq("project_id", pid)
            procs = (
                (q.ilike("name", f"%{process_name}%").execute().data or [])
                if process_name
                else (q.execute().data or [])
            )
            if not procs:
                hint = f" para '{process_name}'" if process_name else ""
                return (
                    f"Nenhum processo BPMN encontrado{hint}. "
                    "Use list_bpmn_processes para ver os disponíveis."
                )
            proc      = procs[0]
            proc_id   = proc["id"]
            proc_name = proc["name"]

            ver_q = (
                db.table("bpmn_versions")
                .select("bpmn_xml, version")
                .eq("process_id", proc_id)
            )
            if meeting_number is not None:
                m = self._find_meeting(meeting_number)
                if m:
                    ver_q = ver_q.eq("meeting_id", m["id"])

            versions = (ver_q.eq("is_current", True).limit(1).execute().data or [])
            if not versions:
                versions = (ver_q.order("version", desc=True).limit(1).execute().data or [])
            if not versions or not versions[0].get("bpmn_xml"):
                return f"Nenhum XML BPMN encontrado para '{proc_name}'."

            xml = versions[0]["bpmn_xml"]
            ver = versions[0].get("version", "?")

            import streamlit as st
            st.session_state.setdefault("_pending_widgets", []).append({
                "type":  "bpmn",
                "xml":   xml,
                "title": f"📐 {proc_name} (v{ver})",
            })
            return f"📐 Diagrama BPMN '{proc_name}' (versão {ver}) renderizado no chat."
        except Exception as exc:
            return f"❌ Erro ao buscar diagrama BPMN: {exc}"

    def show_mermaid_diagram(self, meeting_number: int) -> str:
        """Fetch Mermaid flowchart for a meeting and queue for inline rendering."""
        m = self._find_meeting(meeting_number)
        if not m:
            return f"Reunião {meeting_number} não encontrada."
        mid   = m["id"]
        title = m.get("title") or f"Reunião {meeting_number}"

        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        mermaid_code = ""
        try:
            rows = (
                db.table("bpmn_versions")
                .select("mermaid_code")
                .eq("meeting_id", mid)
                .eq("is_current", True)
                .limit(1)
                .execute()
                .data or []
            )
            if not rows:
                rows = (
                    db.table("bpmn_versions")
                    .select("mermaid_code")
                    .eq("meeting_id", mid)
                    .order("version", desc=True)
                    .limit(1)
                    .execute()
                    .data or []
                )
            if rows:
                mermaid_code = (rows[0].get("mermaid_code") or "").strip()
        except Exception:
            pass

        if not mermaid_code:
            try:
                row = (
                    db.table("meetings")
                    .select("mermaid_code")
                    .eq("id", mid)
                    .single()
                    .execute()
                    .data or {}
                )
                mermaid_code = (row.get("mermaid_code") or "").strip()
            except Exception:
                pass

        if not mermaid_code:
            return (
                f"Nenhum fluxograma Mermaid encontrado para Reunião {meeting_number} — '{title}'. "
                "Execute o pipeline com o agente BPMN para gerar o fluxograma."
            )

        import streamlit as st
        st.session_state.setdefault("_pending_widgets", []).append({
            "type":  "mermaid",
            "code":  mermaid_code,
            "title": f"🔀 Fluxograma — {title}",
        })
        return f"🔀 Fluxograma Mermaid da Reunião {meeting_number} — '{title}' renderizado no chat."

    def render_mermaid_code(self, mermaid_code: str, title: str = "") -> str:
        """Render LLM-generated Mermaid code inline in the chat."""
        if not mermaid_code or not mermaid_code.strip():
            return "❌ Código Mermaid vazio — nada a renderizar."
        import streamlit as st
        widget_title = title.strip() if title else "🔀 Diagrama Mermaid"
        st.session_state.setdefault("_pending_widgets", []).append({
            "type":  "mermaid",
            "code":  mermaid_code.strip(),
            "title": widget_title,
        })
        return f"🔀 Diagrama Mermaid '{widget_title}' renderizado no chat."

    def show_metrics(self, items: list[dict], title: str = "") -> str:
        """Display a grid of KPI metrics inline in the chat."""
        if not items:
            return "Nenhum item fornecido para exibir."
        import streamlit as st
        st.session_state.setdefault("_pending_widgets", []).append({
            "type":  "metrics",
            "title": title,
            "items": items[:4],
        })
        labels = ", ".join(
            f"{it.get('label','?')}: {it.get('value','?')}" for it in items[:4]
        )
        return f"📊 Métricas exibidas — {labels}"

    # ── Glossário ─────────────────────────────────────────────────────────────

    def search_glossary(self, query: str, tag: str | None = None) -> str:
        """Busca termos no Glossário técnico do Process2Diagram."""
        try:
            from modules.glossary_data import search_glossary as _search, TAG_META
            results = _search(query, tag=tag, max_results=6)
        except Exception as exc:
            return f"Erro ao acessar o glossário: {exc}"

        if not results:
            tag_hint = f" na categoria '{TAG_META.get(tag, {}).get('label', tag)}'" if tag else ""
            return (
                f"Nenhum termo encontrado no glossário para **'{query}'**{tag_hint}. "
                f"Tente termos como: BPMN, gateway, embedding, RAG, SBVR, BMM, DMN, "
                f"KnowledgeHub, pipeline, token, spaCy, Supabase, pgvector."
            )

        from modules.glossary_data import TAG_META
        lines = [f"**Glossário Process2Diagram — '{query}'**\n"]
        for e in results:
            en_part = f" *(en: {e['en']})*" if e.get("en") else ""
            tag_label = TAG_META.get(e.get("tag", ""), {}).get("label", e.get("tag", ""))
            lines.append(f"### {e['term']}{en_part}  `{tag_label}`")
            lines.append(e.get("def_", ""))
            if e.get("example"):
                lines.append(f"> **Exemplo:** {e['example']}")
            if e.get("related"):
                lines.append(f"*Ver também: {', '.join(e['related'])}*")
            lines.append("")
        return "\n".join(lines)

    # ── Histórico de requisitos ───────────────────────────────────────────────

    def get_requirement_history(self, req_number: str) -> str:
        """Retorna histórico de versões de um requisito pelo seu número (REQ-NNN)."""
        from core.project_store import _db, _ok, list_requirement_versions
        db = _db()
        if not db:
            return "Banco de dados não configurado."
        try:
            rows = _ok(
                db.table("requirements")
                .select("id, req_number, title")
                .eq("project_id", self.project_id)
                .ilike("req_number", req_number.strip())
                .limit(1)
                .execute()
            )
        except Exception as exc:
            return f"Erro ao buscar requisito: {exc}"
        if not rows:
            return f"Requisito '{req_number}' não encontrado no projeto."

        req = rows[0]
        versions = list_requirement_versions(req["id"])
        if not versions:
            return f"**{req['req_number']} — {req['title']}**\n\nNenhuma versão registrada além da atual."

        lines = [f"**Histórico de versões: {req['req_number']} — {req['title']}**\n"]
        for v in versions:
            meeting_ref = f"Reunião {v.get('meeting_number', '?')}" if v.get("meeting_number") else "Documento externo"
            change = v.get("change_type", "—")
            summary = v.get("change_summary", "")
            priority = v.get("priority", "—")
            req_type = v.get("req_type", "—")
            contradiction = " ⚠️ Contradição detectada" if v.get("contradiction_flag") else ""
            lines.append(
                f"**v{v.get('version', '?')}** ({meeting_ref}) · {change}{contradiction}\n"
                f"  Tipo: {req_type} · Prioridade: {priority}\n"
                f"  Título: {v.get('title', '—')}\n"
                + (f"  Resumo da mudança: {summary}\n" if summary else "")
                + (f"  Contradição: {v.get('contradiction_detail','')}\n" if v.get("contradiction_flag") else "")
            )
        return "\n".join(lines)

    # ── BMM ──────────────────────────────────────────────────────────────────

    def get_bmm(self, meeting_number: int | None = None) -> str:
        """Retorna o BMM (Business Motivation Model) de uma ou mais reuniões."""
        import json
        from core.project_store import _db, _ok
        db = _db()
        if not db:
            return "Banco de dados não configurado."
        try:
            q = (
                db.table("meetings")
                .select("meeting_number, title, bmm_json")
                .eq("project_id", self.project_id)
                .order("meeting_number", desc=True)
            )
            if meeting_number:
                q = q.eq("meeting_number", meeting_number)
            else:
                q = q.limit(1)  # most recent with BMM data
            rows = _ok(q.execute())
        except Exception as exc:
            return f"Erro ao buscar BMM: {exc}"

        results = [(r["meeting_number"], r["title"], r.get("bmm_json")) for r in rows if r.get("bmm_json")]
        if not results:
            return "Nenhum dado BMM encontrado. Execute o pipeline com AgentBMM habilitado."

        lines = []
        for mnum, title, bmm_raw in results:
            try:
                bmm = json.loads(bmm_raw)
            except Exception:
                continue
            lines.append(f"## BMM — Reunião {mnum}: {title}\n")
            for field, label in [
                ("vision", "Visão"), ("mission", "Missão"),
                ("goals", "Objetivos"), ("strategies", "Estratégias"), ("policies", "Políticas"),
            ]:
                val = bmm.get(field)
                if not val:
                    continue
                if isinstance(val, list):
                    lines.append(f"### {label}")
                    lines.extend(f"- {item}" for item in val if item)
                else:
                    lines.append(f"### {label}\n{val}")
                lines.append("")
        return "\n".join(lines) if lines else "Dados BMM encontrados mas vazios."

    # ── CKF ──────────────────────────────────────────────────────────────────

    def get_ckf(self) -> str:
        """Retorna o Context Knowledge File (CKF) acumulado do projeto."""
        from core.project_store import get_context_skill
        ckf = get_context_skill(self.project_id)
        if not ckf or not ckf.strip():
            return (
                "Nenhum CKF encontrado para este projeto. "
                "O CKF é gerado automaticamente pelo AgentCKFUpdater após cada reunião processada. "
                "Verifique se o agente CKF está habilitado nas configurações do pipeline."
            )
        return f"**Context Knowledge File (CKF) do projeto**\n\n{ckf}"

    # ── Knowledge Graph ───────────────────────────────────────────────────────

    def list_kh_entities(self, entity_type: str | None = None, limit: int = 50) -> str:
        """Lista entidades do Grafo de Conhecimento."""
        from core.knowledge_store import get_entities
        limit = min(max(1, limit), 100)
        entities = get_entities(self.project_id, entity_type=entity_type, limit=limit)
        if not entities:
            hint = f" do tipo '{entity_type}'" if entity_type else ""
            return (
                f"Nenhuma entidade{hint} encontrada no Grafo de Conhecimento. "
                "O grafo é populado pelo AgentKnowledgeExtractor — verifique se foi executado."
            )
        type_filter = f" (tipo: {entity_type})" if entity_type else ""
        lines = [f"**Entidades do Grafo de Conhecimento{type_filter}** — {len(entities)} encontradas\n"]
        for e in entities:
            aliases = ", ".join(e.get("aliases") or [])
            alias_str = f" · aliases: {aliases}" if aliases else ""
            lines.append(
                f"**{e['canonical_name']}** `{e['entity_type']}`{alias_str} "
                f"· mencionada {e.get('occurrence_count', 1)}×"
            )
        return "\n".join(lines)

    def list_kh_contradictions(self, status: str = "open") -> str:
        """Lista contradições detectadas pelo Grafo de Conhecimento."""
        from core.knowledge_store import get_contradictions
        actual_status = None if status == "all" else status
        contradictions = get_contradictions(self.project_id, status=actual_status, limit=50)
        if not contradictions:
            label = {"open": "abertas", "resolved": "resolvidas", "all": ""}.get(status, status)
            return f"Nenhuma contradição{' ' + label if label else ''} encontrada no Grafo de Conhecimento."

        label = {"open": "abertas", "resolved": "resolvidas", "all": "todas"}.get(status, status)
        lines = [f"**Contradições {label} no Grafo de Conhecimento** — {len(contradictions)} encontradas\n"]
        for c in contradictions:
            severity = c.get("severity", "—")
            sev_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")
            lines.append(
                f"{sev_icon} **{c.get('process_name', 'Processo desconhecido')}** "
                f"[{c.get('relation_type', '—')}] · status: {c.get('status', '—')}\n"
                f"  {c.get('description', '')}"
            )
            if c.get("clarifying_question"):
                lines.append(f"  ❓ {c['clarifying_question']}")
            if c.get("resolution_note"):
                lines.append(f"  ✅ Resolução: {c['resolution_note']}")
            lines.append("")
        return "\n".join(lines)

    def resolve_contradiction(
        self,
        description_query: str,
        resolution_note: str,
        resolved_by: str = "assistente",
        new_status: str = "resolved",
    ) -> str:
        """Marca uma contradição como resolvida."""
        from core.knowledge_store import get_contradictions, resolve_contradiction as _resolve

        contradictions = get_contradictions(self.project_id, status=None, limit=100)
        if not contradictions:
            return "Nenhuma contradição encontrada no projeto."

        query_lower = description_query.lower()
        matches = [c for c in contradictions if query_lower in (c.get("description") or "").lower()]
        if not matches:
            matches = [c for c in contradictions if any(
                query_lower in (c.get(f) or "").lower()
                for f in ("process_name", "clarifying_question")
            )]
        if not matches:
            return (
                f"Nenhuma contradição encontrada com a descrição '{description_query}'. "
                "Use list_kh_contradictions para ver as contradições disponíveis."
            )
        if len(matches) > 1:
            summaries = "\n".join(
                f"  • [{c['id']}] {c.get('process_name', '—')}: {(c.get('description') or '')[:80]}…"
                for c in matches[:5]
            )
            return (
                f"{len(matches)} contradições corresponderam a '{description_query}'. "
                f"Refine a busca:\n{summaries}"
            )

        c = matches[0]
        success = _resolve(
            contradiction_id=c["id"],
            resolved_by=resolved_by,
            resolution_note=resolution_note,
            status=new_status,
        )
        if not success:
            return f"Erro ao atualizar contradição [{c['id']}]. Tente novamente."

        status_label = {"resolved": "resolvida", "clarified": "esclarecida", "dismissed": "descartada"}.get(
            new_status, new_status
        )
        return (
            f"Contradição {status_label} com sucesso.\n\n"
            f"**Contradição:** {c.get('process_name', '—')} — {(c.get('description') or '')[:120]}\n"
            f"**Resolução:** {resolution_note}\n"
            f"**Registrado por:** {resolved_by}"
        )

    def delete_contradiction(self, description_query: str, confirm: bool) -> str:
        """Remove permanentemente uma contradição."""
        if not confirm:
            return (
                "Exclusão cancelada. Para excluir, confirme com confirm=true. "
                "Esta ação é irreversível."
            )

        from core.knowledge_store import get_contradictions
        from modules.supabase_client import get_supabase_client

        contradictions = get_contradictions(self.project_id, status=None, limit=100)
        if not contradictions:
            return "Nenhuma contradição encontrada no projeto."

        query_lower = description_query.lower()
        matches = [c for c in contradictions if query_lower in (c.get("description") or "").lower()]
        if not matches:
            matches = [c for c in contradictions if any(
                query_lower in (c.get(f) or "").lower()
                for f in ("process_name", "clarifying_question")
            )]
        if not matches:
            return (
                f"Nenhuma contradição encontrada com a descrição '{description_query}'. "
                "Use list_kh_contradictions para ver as contradições disponíveis."
            )
        if len(matches) > 1:
            summaries = "\n".join(
                f"  • [{c['id']}] {c.get('process_name', '—')}: {(c.get('description') or '')[:80]}…"
                for c in matches[:5]
            )
            return (
                f"{len(matches)} contradições corresponderam a '{description_query}'. "
                f"Refine a busca:\n{summaries}"
            )

        c = matches[0]
        try:
            sb = get_supabase_client()
            sb.table("kh_contradictions").delete().eq("id", c["id"]).execute()
        except Exception as exc:
            return f"Erro ao excluir contradição [{c['id']}]: {exc}"

        return (
            f"Contradição excluída permanentemente.\n\n"
            f"**Processo:** {c.get('process_name', '—')}\n"
            f"**Descrição:** {(c.get('description') or '')[:200]}"
        )

    def list_kh_facts(self, fact_type: str | None = None, limit: int = 50) -> str:
        """Lista fatos consolidados do Grafo de Conhecimento."""
        from core.knowledge_store import get_facts
        limit = min(max(1, limit), 100)
        facts = get_facts(self.project_id, fact_type=fact_type, active_only=True, limit=limit)
        if not facts:
            hint = f" do tipo '{fact_type}'" if fact_type else ""
            return f"Nenhum fato{hint} encontrado no Grafo de Conhecimento."

        type_filter = f" (tipo: {fact_type})" if fact_type else ""
        lines = [f"**Fatos consolidados do Grafo de Conhecimento{type_filter}** — {len(facts)} encontrados\n"]
        for f in facts:
            conf = f.get("confidence", 1.0)
            conf_str = f" · confiança: {conf:.0%}" if conf < 1.0 else ""
            n_meetings = len(f.get("source_meeting_ids") or [])
            mtg_str = f" · {n_meetings} reunião(ões)" if n_meetings else ""
            lines.append(
                f"**[{f.get('fact_type', '—')}]**{conf_str}{mtg_str}\n"
                f"  {f.get('content', '')}"
            )
        return "\n".join(lines)

    def read_skill_reference(self, agent: str, section: str | None = None) -> str:
        """Lê o conteúdo da skill file de um agente, com extração opcional de seção."""
        from core.agent_registry import AGENT_REGISTRY
        from pathlib import Path

        entry = AGENT_REGISTRY.get(agent.lower().strip())
        if entry is None:
            valid = ", ".join(sorted(AGENT_REGISTRY.keys()))
            return (
                f"Agente '{agent}' não encontrado no registry. "
                f"Agentes disponíveis: {valid}."
            )

        skill_path = entry.get("skill_path")
        if not skill_path:
            return f"O agente '{agent}' não possui skill file associado."

        project_root = Path(__file__).parent.parent
        path = project_root / skill_path
        if not path.exists():
            return f"Arquivo de skill não encontrado em disco: '{skill_path}'."

        import re
        content = path.read_text(encoding="utf-8")
        # Strip YAML frontmatter
        content = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, flags=re.DOTALL).lstrip('\n')

        if not section:
            # Cap at ~6000 chars to avoid flooding the context window
            cap = 6000
            if len(content) > cap:
                content = content[:cap] + (
                    f"\n\n*[conteúdo truncado — {len(content)} chars no total. "
                    "Use o parâmetro `section` para ler uma seção específica.]*"
                )
            return f"**Skill: {agent}** (`{skill_path}`)\n\n{content}"

        # Split content at heading boundaries, then find the matching section.
        # Prepend \n so every heading becomes a split point including the first one.
        parts = re.split(r'\n(?=#{1,4}\s)', '\n' + content)
        for part in parts:
            first_line = part.lstrip('\n').split('\n', 1)[0]
            heading_text = re.sub(r'^#{1,4}\s+', '', first_line).strip()
            if heading_text.lower() == section.lower():
                return f"**Skill: {agent}** — seção `{section}`\n\n{part.strip()}"

        # Section not found — list available headings to help the caller
        headers = re.findall(r'^#{1,4}\s+(.+)', content, flags=re.MULTILINE)
        available = "\n".join(f"- {h.strip()}" for h in headers[:30])
        return (
            f"Seção '{section}' não encontrada na skill '{agent}'.\n\n"
            f"Seções disponíveis:\n{available}"
        )

    # ── Plantonista / Diagnóstico ─────────────────────────────────────────────

    def sugestoes_plantonista(self) -> str:
        """Briefing proativo do estado atual do projeto sem chamada LLM."""
        from modules.supabase_client import get_supabase_client
        from modules.cross_meeting_analyzer import find_recurring_topics as _find

        meetings = self._get_meetings()
        if not meetings:
            return (
                "👋 **Olá!** Nenhuma reunião encontrada neste projeto.\n"
                "Processe a primeira transcrição na aba **Pipeline** para começar."
            )

        n = len(meetings)
        last = meetings[-1]
        last_n = last.get("meeting_number", "?")
        last_title = last.get("title") or f"Reunião {last_n}"

        # Reuniões sem ata
        sem_ata = [m for m in meetings if not m.get("minutes_md")]

        # Contradições abertas
        n_contradictions = 0
        try:
            db = get_supabase_client()
            if db:
                r = (
                    db.table("kh_contradictions")
                    .select("id", count="exact")
                    .eq("project_id", self.project_id)
                    .eq("status", "open")
                    .execute()
                )
                n_contradictions = r.count or 0
        except Exception:
            pass

        # Tópicos recorrentes
        recurring = []
        try:
            recurring, _ = _find(self.project_id, threshold=0.85, max_results=5)
        except Exception:
            pass

        # Reuniões com encaminhamentos listados (qualquer ata que tenha seção "Ações")
        n_with_actions = sum(
            1 for m in meetings
            if m.get("minutes_md") and (
                "Itens de Ação" in (m.get("minutes_md") or "")
                or "Action Items" in (m.get("minutes_md") or "")
            )
        )

        lines: list[str] = []
        sugestoes: list[str] = []

        lines.append(f"👋 **Raio-X do Projeto** — {n} reunião(ões) processada(s)")
        lines.append(f"📅 Última reunião: **{last_title}**")
        lines.append("")

        if sem_ata:
            ns_str = ", ".join(str(m.get("meeting_number", "?")) for m in sem_ata)
            lines.append(f"⚠️ **{len(sem_ata)} reunião(ões) sem ata** — Reuniões {ns_str}")
            sugestoes.append("Gerar atas ausentes: use `generate_missing_minutes()`")
        else:
            lines.append("✅ Todas as reuniões têm ata")

        if n_contradictions > 0:
            lines.append(f"⚠️ **{n_contradictions} contradição(ões) aberta(s)** no Knowledge Hub")
            sugestoes.append("Revisar contradições: pergunte *'mostre as contradições abertas'*")
        else:
            lines.append("✅ Nenhuma contradição aberta no Knowledge Hub")

        if recurring:
            kws = [" · ".join(t.keywords[:3]) for t in recurring[:2] if t.keywords]
            lines.append(
                f"🔄 **{len(recurring)} tópico(s) recorrente(s)** sem resolução: "
                f"*{', '.join(kws)}*"
            )
            sugestoes.append(
                "Gerar pauta focada no tópico recorrente: use `generate_next_agenda()`"
            )
        else:
            lines.append("✅ Nenhum tópico recorrente detectado")

        if n_with_actions > 0:
            lines.append(
                f"📋 **{n_with_actions} reunião(ões)** com encaminhamentos listados"
            )
            sugestoes.append(
                "Ver encaminhamentos: pergunte *'quais são os encaminhamentos em aberto?'*"
            )

        if sugestoes:
            lines.append("")
            lines.append("**Sugestões de ação:**")
            for i, s in enumerate(sugestoes, 1):
                lines.append(f"{i}. {s}")

        lines.append("")
        lines.append(
            "*Para um diagnóstico completo, use `diagnostico_projeto()`. "
            "Ou faça qualquer pergunta sobre o projeto.*"
        )

        return "\n".join(lines)

    def diagnostico_projeto(
        self,
        include_integrity: bool = True,
        include_contradictions: bool = True,
        include_roi: bool = True,
        include_recurring: bool = True,
        include_pendencies: bool = True,
    ) -> str:
        """Checkup completo do projeto: orquestra ferramentas existentes sem LLM."""
        import re as _re
        from modules.supabase_client import get_supabase_client
        from modules.auth import is_admin as _is_admin
        from modules.cross_meeting_analyzer import find_recurring_topics as _find

        meetings = self._get_meetings()
        if not meetings:
            return "Nenhuma reunião encontrada. Processe transcrições no Pipeline."

        n_reunioes = len(meetings)
        criticos: list[str] = []
        alertas: list[str] = []
        oks: list[str] = []
        acoes: list[tuple[int, str]] = []  # (prioridade, texto)

        # 1. Integridade — admin only
        if include_integrity and _is_admin():
            try:
                report = self.get_database_integrity()
                m = _re.search(r'Saúde geral\s*:\s*(\d+)%', report)
                if m:
                    hp = int(m.group(1))
                    if hp < 70:
                        criticos.append(f"Integridade do banco: **{hp}%** — abaixo do mínimo")
                        acoes.append((1, "Verificar campos ausentes: `get_database_integrity()`"))
                    elif hp < 90:
                        alertas.append(f"Integridade do banco: **{hp}%** — campos ausentes detectados")
                        acoes.append((3, "Verificar campos ausentes: `get_database_integrity()`"))
                    else:
                        oks.append(f"Integridade do banco: **{hp}%** ✓")
            except Exception:
                pass

        # 2. Contradições abertas
        if include_contradictions:
            n_contra = 0
            try:
                db = get_supabase_client()
                if db:
                    r = (
                        db.table("kh_contradictions")
                        .select("id", count="exact")
                        .eq("project_id", self.project_id)
                        .eq("status", "open")
                        .execute()
                    )
                    n_contra = r.count or 0
            except Exception:
                pass
            if n_contra > 0:
                alertas.append(f"**{n_contra} contradição(ões)** aberta(s) no Knowledge Hub")
                acoes.append((2, "Revisar contradições: pergunte *'mostre as contradições abertas'*"))
            else:
                oks.append("Nenhuma contradição aberta no Knowledge Hub ✓")

        # 3. Reuniões sem ata
        sem_ata = [m for m in meetings if not m.get("minutes_md")]
        if sem_ata:
            ns = ", ".join(str(m.get("meeting_number", "?")) for m in sem_ata)
            alertas.append(f"**{len(sem_ata)} reunião(ões) sem ata** — Reuniões {ns}")
            acoes.append((2, "Gerar atas ausentes: `generate_missing_minutes()`"))
        else:
            oks.append("Todas as reuniões têm ata ✓")

        # 4. ROI baixo
        if include_roi:
            try:
                roi_text = self.calculate_meeting_roi()
                low = _re.findall(r'Reunião (\d+)[^\n]*ROI-TR[^\n]*?(\d+\.\d+)', roi_text)
                low_meetings = [(n, float(v)) for n, v in low if float(v) < 5.0]
                if low_meetings:
                    itens = ", ".join(f"R{n} (ROI={v:.1f})" for n, v in low_meetings)
                    alertas.append(f"**ROI-TR baixo** em: {itens}")
                    acoes.append((4, "Analisar reunião(ões) com baixo aproveitamento"))
                else:
                    oks.append("ROI-TR adequado em todas as reuniões ✓")
            except Exception:
                pass

        # 5. Tópicos recorrentes
        if include_recurring:
            try:
                topics, _ = _find(self.project_id, threshold=0.85, max_results=10)
                if topics:
                    kws = "; ".join(
                        " · ".join(t.keywords[:3])
                        for t in topics[:3] if t.keywords
                    )
                    alertas.append(
                        f"**{len(topics)} tópico(s) recorrente(s)** sem resolução: *{kws}*"
                    )
                    acoes.append((3, "Gerar pauta focada: `generate_next_agenda()`"))
                else:
                    oks.append("Nenhum tópico recorrente detectado ✓")
            except Exception:
                pass

        # 6. Encaminhamentos em atas
        if include_pendencies:
            n_with_actions = sum(
                1 for m in meetings
                if m.get("minutes_md") and (
                    "Itens de Ação" in (m.get("minutes_md") or "")
                    or "Action Items" in (m.get("minutes_md") or "")
                )
            )
            if n_with_actions > 0:
                alertas.append(
                    f"**{n_with_actions} reunião(ões)** com seção de encaminhamentos"
                )
                acoes.append(
                    (5, "Ver pendências: pergunte *'quais encaminhamentos estão em aberto?'*")
                )
            else:
                oks.append("Nenhum encaminhamento registrado ✓")

        # Score estimado
        total = len(criticos) + len(alertas) + len(oks)
        score = round(100 * (len(oks) + 0.5 * len(alertas)) / total) if total else 100

        lines = [
            "## 🏥 Diagnóstico do Projeto",
            "",
            (
                f"**{n_reunioes} reunião(ões)** · "
                f"Saúde estimada: **{score}%** · "
                f"{'🔴 ' + str(len(criticos)) + ' crítico(s) · ' if criticos else ''}"
                f"🟡 {len(alertas)} alerta(s) · "
                f"🟢 {len(oks)} ok"
            ),
            "",
        ]

        if criticos:
            lines.append("### 🔴 Crítico")
            lines.extend(f"- {s}" for s in criticos)
            lines.append("")

        if alertas:
            lines.append("### 🟡 Atenção")
            lines.extend(f"- {s}" for s in alertas)
            lines.append("")

        if oks:
            lines.append("### 🟢 OK")
            lines.extend(f"- {s}" for s in oks)
            lines.append("")

        if acoes:
            lines.append("### 📋 Ações recomendadas")
            for i, (_, texto) in enumerate(sorted(acoes), 1):
                lines.append(f"{i}. {texto}")

        return "\n".join(lines)

    # ── Sugestor de Processos / Deck Executivo / Project Charter (Fase 4) ──────

    def sugerir_processos(
        self,
        min_reunioes: int = 2,
        confidence: float = 0.7,
        include_evidence: bool = True,
    ) -> str:
        """Identify potential new BPMN processes from IBIS debates and decisions."""
        import re as _re

        qs = self._load_ibis_questions()
        if not qs:
            return (
                "Nenhuma questão IBIS encontrada no projeto. "
                "Execute o pipeline com AgentArgumentation habilitado para gerar questões IBIS."
            )

        _STOP = {
            "a","o","as","os","de","do","da","dos","das","em","no","na","nos","nas",
            "para","que","um","uma","e","ou","se","com","por","mas","é","ser","ter",
            "ao","à","não","como","mais","deve","há","este","esta","seu","sua","foi",
            "sendo","está","são","pelo","pela","isso","cada","todos","todas","qual",
            "quem","quando","onde","seria","será","pode","precisa","sobre","ainda",
        }

        def _kw(text: str) -> set:
            return {
                w for w in _re.sub(r"[^\w\sáéíóúâêôãçÁÉÍÓÚÂÊÔÃÇ]", " ", text.lower()).split()
                if w not in _STOP and len(w) > 3
            }

        # Keyword set per question (statement + alternatives)
        q_words = [
            _kw(q.get("statement", "") + " " + " ".join(
                a.get("description", "") for a in q.get("alternatives", [])
            ))
            for q in qs
        ]

        # Single-linkage clustering by Jaccard overlap >= confidence
        assigned = [False] * len(qs)
        clusters: list[dict] = []

        for i, qi in enumerate(qs):
            if assigned[i]:
                continue
            cl_qs    = [qi]
            cl_words = set(q_words[i])
            cl_mtgs  = {qi["_mnum"]}
            assigned[i] = True

            for j in range(len(qs)):
                if assigned[j]:
                    continue
                union = cl_words | q_words[j]
                if not union:
                    continue
                if len(cl_words & q_words[j]) / len(union) >= confidence:
                    cl_qs.append(qs[j])
                    cl_words |= q_words[j]
                    cl_mtgs.add(qs[j]["_mnum"])
                    assigned[j] = True

            if len(cl_mtgs) >= min_reunioes:
                clusters.append({"questions": cl_qs, "meetings": sorted(cl_mtgs), "words": cl_words})

        if not clusters:
            return (
                f"Nenhum tema emergente encontrado em ≥{min_reunioes} reunião(ões) "
                f"com confiança ≥{confidence:.0%}. "
                "Tente reduzir `min_reunioes` ou `confidence`."
            )

        try:
            from core.project_store import list_bpmn_processes, list_sbvr_rules
            existing_procs = list_bpmn_processes(self.project_id)
            existing_names = [(p.get("name") or "").lower() for p in existing_procs]
            all_rules      = list_sbvr_rules(self.project_id)
        except Exception:
            existing_procs, existing_names, all_rules = [], [], []

        lines = [
            "# 💡 Sugestão de Novos Processos BPMN",
            f"*{len(clusters)} tema(s) emergente(s) detectado(s) em ≥{min_reunioes} reunião(ões)*\n",
        ]

        for idx, cl in enumerate(clusters, 1):
            # Topic name from most frequent keywords
            freq: dict[str, int] = {}
            for q in cl["questions"]:
                for w in _kw(q.get("statement", "")):
                    freq[w] = freq.get(w, 0) + 1
            top_words  = sorted(freq, key=lambda w: -freq[w])[:4]
            topic_name = " ".join(top_words).title() or f"Tema {idx}"
            mtg_list   = ", ".join(f"Reunião {m}" for m in cl["meetings"])

            already = any(
                any(w in name for w in top_words[:2]) for name in existing_names
            )
            badge = "✅ Processo existente" if already else "🆕 Novo processo sugerido"

            lines += [
                f"---\n## {idx}. {topic_name}",
                f"**{badge}** | Reuniões: {mtg_list} ({len(cl['meetings'])})",
                "",
            ]

            if already:
                match = next(
                    (p.get("name") for p in existing_procs
                     if any(w in (p.get("name") or "").lower() for w in top_words[:2])),
                    "processo existente",
                )
                lines.append(f"*Processo relacionado já modelado: **{match}***")
                lines.append("Verifique se cobre todos os cenários discutidos.\n")
            else:
                # Infer steps from IBIS alternatives
                steps: list[str] = []
                for q in cl["questions"]:
                    for alt in q.get("alternatives", []):
                        desc = (alt.get("description") or "").strip()
                        if not desc:
                            continue
                        prefix = "✅ " if alt.get("was_chosen") else "• "
                        steps.insert(0, prefix + desc) if alt.get("was_chosen") else steps.append(prefix + desc)
                if not steps:
                    steps = [
                        f"Definir/Resolver: {q.get('statement','').rstrip('?')}"
                        for q in cl["questions"][:4]
                    ]

                lines.append("### Steps inferidos das decisões IBIS")
                for i_s, step in enumerate(steps[:6], 1):
                    lines.append(f"{i_s}. {step}")
                lines.append("")

                rel_rules = [
                    r for r in all_rules
                    if any(w in (r.get("statement") or "").lower() for w in top_words[:3])
                ][:3]
                if rel_rules:
                    lines.append("### Regras SBVR associadas")
                    for r in rel_rules:
                        lines.append(f"- [{r.get('rule_id','')}] {r.get('statement','')}")
                    lines.append("")

            if include_evidence:
                lines.append("### Evidências")
                for q in cl["questions"][:4]:
                    lines.append(f"- Reunião {q.get('_mnum','?')}: *\"{q.get('statement','')}\"*")
                lines.append("")

        n_new      = sum(1 for cl in clusters if not any(
            any(w in name for w in sorted(
                {w for q in cl["questions"] for w in _kw(q.get("statement",""))},
                key=lambda w: -sum(1 for q in cl["questions"] if w in q.get("statement","").lower()),
            )[:2]) for name in existing_names
        ))
        lines.append(
            f"\n---\n*Resumo: {len(clusters)} tema(s) encontrado(s) — "
            f"{n_new} novo(s) processo(s) sugerido(s), "
            f"{len(clusters) - n_new} já modelado(s).*"
        )
        return "\n".join(lines)

    def _llm_call(self, system: str, user: str, max_tokens: int = 3000) -> str:
        """Shared LLM call helper used by gerar_deck_executivo and gerar_project_charter."""
        provider_cfg = self.llm_config.get("provider_cfg", {})
        api_key      = self.llm_config.get("api_key", "")
        model        = self.llm_config.get("model", "deepseek-v4-flash")
        client_type  = provider_cfg.get("client_type", "openai_compatible")

        if client_type == "anthropic":
            import anthropic as _ant
            ac  = _ant.Anthropic(api_key=api_key)
            msg = ac.messages.create(
                model=model, max_tokens=max_tokens, system=system,
                messages=[{"role": "user", "content": user}],
            )
            return (msg.content[0].text or "").strip()
        else:
            from openai import OpenAI as _OAI
            client = _OAI(api_key=api_key, base_url=provider_cfg.get("base_url"))
            kwargs: dict = dict(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user},
                ],
                max_tokens=max_tokens,
            )
            if not provider_cfg.get("reasoning_effort") and "deepseek-v4" not in model.lower():
                kwargs["temperature"] = 0.35
            return (client.chat.completions.create(**kwargs).choices[0].message.content or "").strip()

    def gerar_deck_executivo(
        self,
        incluir_secoes: list | None = None,
        meeting_numbers: list | None = None,
        tema_cores: str = "corporativo",
    ) -> str:
        """Generate a Markdown executive deck from all project artifacts."""
        meetings = self._get_meetings()
        if meeting_numbers:
            meetings = [m for m in meetings if m.get("meeting_number") in meeting_numbers]
        if not meetings:
            return "Nenhuma reunião encontrada para gerar o deck executivo."

        bmm  = self.get_bmm()
        ckf  = self.get_ckf()
        bpmn = self.list_bpmn_processes()
        roi  = self.calculate_meeting_roi()

        try:
            from modules.supabase_client import get_supabase_client
            db = get_supabase_client()
            reqs = (
                db.table("requirements")
                .select("req_type, priority, status")
                .eq("project_id", self.project_id)
                .execute().data or []
            ) if db else []
        except Exception:
            reqs = []

        n_reqs   = len(reqs)
        n_func   = sum(1 for r in reqs if r.get("req_type") == "Funcional")
        n_nf     = sum(1 for r in reqs if r.get("req_type") == "Não Funcional")
        n_rn     = sum(1 for r in reqs if r.get("req_type") == "Regra de Negócio")
        n_crit   = sum(1 for r in reqs if r.get("priority") == "Crítico")
        n_active = sum(1 for r in reqs if (r.get("status") or "").lower() == "active")

        actions: list[str] = []
        for m in meetings:
            ai = self._section(m.get("minutes_md") or "", "Itens de Ação", "Action Items", "Ações")
            if ai:
                actions.append(f"Reunião {m.get('meeting_number')}: {ai[:150]}")

        bmm_ctx  = bmm[:1500]  if "não encontrad" not in bmm.lower()  else "(não disponível)"
        ckf_ctx  = ckf[:600]   if "não encontrad" not in ckf.lower()  else "(não disponível)"
        bpmn_ctx = bpmn[:600]
        roi_ctx  = roi[:600]
        ai_ctx   = "\n".join(actions[:4]) or "(nenhum)"

        sections = incluir_secoes or [
            "resumo_executivo", "metricas_principais", "evolucao_requisitos",
            "processos_bpmn", "indicadores_roi", "pendencias", "recomendacoes",
        ]

        system = (
            "Você é especialista em apresentações executivas. "
            "Gere um deck executivo em Markdown estruturado. "
            "Cada slide começa com ## (H2). Bullet points concisos, máx 5 por slide. "
            "Tom formal e objetivo. Responda em Português do Brasil."
        )
        user = (
            f"Gere um deck executivo de {len(sections)} slides para um projeto de software.\n\n"
            f"**Dados:**\n"
            f"- Reuniões: {len(meetings)} | Requisitos: {n_reqs} "
            f"({n_func} Func / {n_nf} NF / {n_rn} RN) | Críticos: {n_crit} | Ativos: {n_active}\n\n"
            f"**BMM (Visão/Missão/Objetivos):**\n{bmm_ctx}\n\n"
            f"**Processos BPMN:**\n{bpmn_ctx}\n\n"
            f"**ROI-TR das reuniões:**\n{roi_ctx}\n\n"
            f"**CKF (Contexto estratégico):**\n{ckf_ctx}\n\n"
            f"**Encaminhamentos pendentes:**\n{ai_ctx}\n\n"
            f"**Seções solicitadas:** {', '.join(sections)}\n\n"
            "**Slides obrigatórios:**\n"
            "1. ## 🎯 Visão Geral — visão, missão, objetivo central\n"
            "2. ## 📊 Métricas Principais — KPIs quantitativos\n"
            "3. ## 📋 Análise de Requisitos — breakdown e cobertura\n"
            "4. ## ⚙️ Processos de Negócio — processos BPMN modelados\n"
            "5. ## 📈 Qualidade das Reuniões — ROI-TR resumido\n"
            "6. ## ⚠️ Pendências — encaminhamentos em aberto\n"
            "7. ## 🚀 Próximos Passos — 3-5 ações priorizadas\n\n"
            "Máx 5 bullets por slide. Total aprox. 400 palavras."
        )

        try:
            deck = self._llm_call(system, user, max_tokens=3000)
        except Exception as exc:
            return f"❌ Erro ao gerar deck executivo: {exc}"

        return f"# 📊 Deck Executivo — Process2Diagram\n\n{deck}"

    def gerar_project_charter(
        self,
        incluir_riscos: bool = True,
        incluir_cronograma: bool = True,
        incluir_stakeholders: bool = True,
        incluir_escopo: bool = True,
    ) -> str:
        """Generate a formal project charter in Markdown from all project artifacts."""
        meetings = self._get_meetings()
        if not meetings:
            return "Nenhuma reunião encontrada no projeto para gerar o Project Charter."

        bmm  = self.get_bmm()
        ckf  = self.get_ckf()
        bpmn = self.list_bpmn_processes()

        try:
            from modules.supabase_client import get_supabase_client
            db = get_supabase_client()
            reqs = (
                db.table("requirements")
                .select("req_number, title, description, req_type, priority, status")
                .eq("project_id", self.project_id)
                .order("req_number")
                .execute().data or []
            ) if db else []
        except Exception:
            reqs = []

        try:
            from core.project_store import list_sbvr_rules
            rules = list_sbvr_rules(self.project_id)[:8]
        except Exception:
            rules = []

        try:
            from core.knowledge_store import get_contradictions
            contras = get_contradictions(self.project_id, status="open", limit=8)
        except Exception:
            contras = []

        participants: list[str] = []
        action_items: list[str] = []
        dates: list[str] = []
        for m in meetings:
            md = m.get("minutes_md") or ""
            p  = self._section(md, "Participantes")
            if p:
                participants.append(f"Reunião {m.get('meeting_number')}: {p[:200]}")
            ai = self._section(md, "Itens de Ação", "Action Items", "Ações")
            if ai:
                action_items.append(f"Reunião {m.get('meeting_number')}: {ai[:200]}")
            dt = m.get("meeting_date")
            if dt:
                dates.append(str(dt)[:10])

        n_reqs = len(reqs)
        n_func = sum(1 for r in reqs if r.get("req_type") == "Funcional")
        n_nf   = sum(1 for r in reqs if r.get("req_type") == "Não Funcional")
        n_rn   = sum(1 for r in reqs if r.get("req_type") == "Regra de Negócio")

        top_reqs_txt = "\n".join(
            f"  REQ-{r.get('req_number',0):03d} [{r.get('req_type','—')}/{r.get('priority','—')}]: "
            f"{r.get('title','')} — {(r.get('description') or '')[:80]}"
            for r in reqs[:15]
        ) or "(nenhum)"

        rules_txt  = "\n".join(f"  [{r.get('rule_id','')}] {r.get('statement','')}" for r in rules) or "(nenhuma)"
        contra_txt = "\n".join(f"  [{c.get('severity','—')}] {c.get('description','')[:100]}" for c in contras) or "(nenhuma)"
        parts_txt  = "\n".join(participants[:5]) or "(não disponível)"
        ai_txt     = "\n".join(action_items[:5]) or "(nenhum)"
        period     = f"{min(dates)} a {max(dates)}" if dates else "não disponível"
        bmm_ctx    = bmm[:2000] if "não encontrad" not in bmm.lower() else "(não disponível)"
        ckf_ctx    = ckf[:800]  if "não encontrad" not in ckf.lower() else "(não disponível)"

        optional = []
        if incluir_stakeholders:
            optional.append("5. ## 👥 Stakeholders")
        if incluir_escopo:
            optional.append("6. ## 📋 Escopo e Requisitos")
        if incluir_riscos:
            optional.append("8. ## ⚠️ Riscos e Restrições")
        if incluir_cronograma:
            optional.append("9. ## 📅 Cronograma e Próximos Passos")

        system = (
            "Você é especialista em gestão de projetos (PMO). "
            "Gere um Project Charter formal e completo em Markdown. "
            "Linguagem formal e profissional. Responda em Português do Brasil."
        )
        user = (
            f"Gere um Project Charter formal para um projeto de software.\n\n"
            f"**BMM (Visão/Missão/Objetivos/Estratégias/Políticas):**\n{bmm_ctx}\n\n"
            f"**CKF:**\n{ckf_ctx}\n\n"
            f"**Reuniões:** {len(meetings)} | **Período:** {period}\n\n"
            f"**Participantes:**\n{parts_txt}\n\n"
            f"**Requisitos:** {n_reqs} total ({n_func} Func / {n_nf} NF / {n_rn} RN)\n{top_reqs_txt}\n\n"
            f"**Processos BPMN:**\n{bpmn[:500]}\n\n"
            f"**Regras SBVR:**\n{rules_txt}\n\n"
            f"**Contradições em Aberto (Riscos):**\n{contra_txt}\n\n"
            f"**Encaminhamentos Pendentes:**\n{ai_txt}\n\n"
            "**Seções obrigatórias do charter:**\n"
            "1. ## 🎯 Identificação do Projeto\n"
            "2. ## 📌 Visão e Missão\n"
            "3. ## 🎯 Objetivos Estratégicos\n"
            "4. ## 🔭 Escopo (dentro / fora)\n"
            + ("\n".join(optional)) + "\n"
            "7. ## ⚙️ Processos de Negócio Mapeados\n"
            "10. ## 📜 Premissas e Restrições\n\n"
            "Linguagem formal de PMO. Máx 900 palavras."
        )

        try:
            charter = self._llm_call(system, user, max_tokens=3500)
        except Exception as exc:
            return f"❌ Erro ao gerar Project Charter: {exc}"

        return (
            f"# 📄 Project Charter\n\n"
            f"*Gerado pelo Process2Diagram — {len(meetings)} reunião(ões) | {n_reqs} requisitos*\n\n"
            "---\n\n"
            + charter
        )

    # ── Rastreabilidade / Simulação / Conformidade (Fase 3) ──────────────────

    def mapa_rastreabilidade(
        self,
        req_number: int | None = None,
        topic: str | None = None,
        include_transcript: bool = True,
        include_bpmn: bool = True,
        include_sbvr: bool = True,
        include_ibis: bool = True,
    ) -> str:
        """Build a traceability map for a requirement or topic."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        if not req_number and not topic:
            return (
                "Informe `req_number` (número do requisito, ex: 42) "
                "ou `topic` (tema para busca, ex: 'autenticação biométrica')."
            )

        try:
            q = (
                db.table("requirements")
                .select("id, req_number, title, description, req_type, status, priority")
                .eq("project_id", self.project_id)
            )
            if req_number:
                q = q.eq("req_number", req_number)
            all_rows = q.order("req_number").execute().data or []
        except Exception as exc:
            return f"Erro ao buscar requisitos: {exc}"

        if topic and not req_number:
            kw = topic.lower()
            all_rows = [
                r for r in all_rows
                if kw in (r.get("title") or "").lower()
                or kw in (r.get("description") or "").lower()
            ][:5]

        if not all_rows:
            hint = f"REQ-{req_number:03d}" if isinstance(req_number, int) else f"'{topic}'"
            return f"Nenhum requisito encontrado para {hint}."

        lines = [
            "# 🔗 Mapa de Rastreabilidade",
            f"*{len(all_rows)} requisito(s) analisado(s)*\n",
        ]

        for r in all_rows[:5]:
            n      = r.get("req_number", "?")
            title  = r.get("title", "")
            desc   = r.get("description", "")
            rtype  = r.get("req_type", "—")
            prio   = r.get("priority", "—")
            req_id = f"REQ-{n:03d}" if isinstance(n, int) else f"REQ-{n}"

            lines += [
                f"---\n## 🔷 {req_id} — {title}",
                f"**Tipo:** {rtype} | **Prioridade:** {prio}",
            ]
            if desc:
                lines.append(f"**Descrição:** {desc[:200]}{'…' if len(desc) > 200 else ''}")
            lines.append("")

            # ── Transcript
            if include_transcript:
                try:
                    tr = self.search_transcript(query=title)
                    if not any(x in tr.lower() for x in ("não encontrad", "sem palavras", "consulta sem")):
                        tr_lines = tr.splitlines()
                        lines.append("### 📝 Falas na Transcrição")
                        lines += tr_lines[:10]
                        if len(tr_lines) > 10:
                            lines.append(f"*… {len(tr_lines) - 10} linha(s) adicionais*")
                    else:
                        lines.append("### 📝 Falas na Transcrição\n_Nenhuma fala encontrada_")
                except Exception:
                    lines.append("### 📝 Falas na Transcrição\n_Erro ao buscar_")
                lines.append("")

            # ── BPMN
            if include_bpmn:
                try:
                    from core.project_store import list_bpmn_processes
                    procs = list_bpmn_processes(self.project_id)
                    words = [w for w in title.lower().split() if len(w) > 3]
                    matched = [
                        p for p in procs
                        if any(w in (p.get("name") or "").lower() for w in words)
                    ]
                    if matched:
                        lines.append("### ⚙️ Processos BPMN Relacionados")
                        for p in matched[:3]:
                            lines.append(
                                f"- **{p.get('name')}** — {p.get('version_count', 0)} versão(ões) "
                                f"[{p.get('status', '—')}]"
                            )
                    else:
                        lines.append(
                            "### ⚙️ Processos BPMN Relacionados\n"
                            "_Nenhum processo com nome diretamente relacionado_"
                        )
                except Exception:
                    pass
                lines.append("")

            # ── SBVR
            if include_sbvr:
                try:
                    sbvr = self.get_sbvr_rules(keyword=title)
                    if "nenhuma" not in sbvr.lower():
                        lines.append("### 📐 Regras SBVR Relacionadas")
                        lines.append(sbvr[:800])
                    else:
                        lines.append("### 📐 Regras SBVR Relacionadas\n_Nenhuma regra encontrada_")
                except Exception:
                    pass
                lines.append("")

            # ── IBIS
            if include_ibis:
                try:
                    ibis_qs = self._load_ibis_questions(topic_filter=title)
                    _icon = {"decided": "✅", "deferred": "⏳", "unresolved": "❓"}
                    if ibis_qs:
                        lines.append("### 🗺️ Debates IBIS Relacionados")
                        for q2 in ibis_qs[:4]:
                            rt   = (q2.get("resolution") or {}).get("type", "unresolved")
                            lines.append(
                                f"- {_icon.get(rt, '❓')} **{q2.get('id','?')}** "
                                f"(Reunião {q2.get('_mnum','?')}): {q2.get('statement','')}"
                            )
                        if len(ibis_qs) > 4:
                            lines.append(f"*… e mais {len(ibis_qs) - 4} debate(s)*")
                    else:
                        lines.append("### 🗺️ Debates IBIS Relacionados\n_Nenhum debate encontrado_")
                except Exception:
                    pass
                lines.append("")

        return "\n".join(lines)

    def simular_cenario(
        self,
        descricao: str,
        requisitos_afetados: list | None = None,
        restricoes: dict | None = None,
    ) -> str:
        """Simulate the impact of a scenario change using LLM + project data."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        # 1. Load all requirements
        try:
            all_reqs = (
                db.table("requirements")
                .select("req_number, title, description, req_type, priority, status")
                .eq("project_id", self.project_id)
                .order("req_number")
                .execute().data or []
            )
        except Exception as exc:
            return f"Erro ao buscar requisitos: {exc}"

        if not all_reqs:
            return "Nenhum requisito encontrado no projeto para simular impacto."

        # 2. Identify affected requirements
        affected_rows: list[dict] = []
        if requisitos_afetados:
            for raw_id in requisitos_afetados:
                key = raw_id.strip().upper().replace("REQ-", "").lstrip("0") or "0"
                try:
                    n = int(key)
                    match = next((r for r in all_reqs if r.get("req_number") == n), None)
                    if match and match not in affected_rows:
                        affected_rows.append(match)
                except ValueError:
                    kw = raw_id.lower()
                    affected_rows += [
                        r for r in all_reqs
                        if kw in (r.get("title") or "").lower() and r not in affected_rows
                    ][:2]
        else:
            words = [w for w in descricao.lower().split() if len(w) > 4]
            affected_rows = [
                r for r in all_reqs
                if any(
                    w in (r.get("title") or "").lower()
                    or w in (r.get("description") or "").lower()
                    for w in words
                )
            ][:5]

        # 3. Build compact context
        def _fmt_reqs(reqs: list, label: str) -> str:
            if not reqs:
                return f"{label}: (nenhum identificado)"
            lines = [label + ":"]
            for r in reqs[:12]:
                n = r.get("req_number", "?")
                lines.append(
                    f"  REQ-{n:03d} [{r.get('req_type','—')}/{r.get('priority','—')}]: "
                    f"{r.get('title','')} — {(r.get('description') or '')[:80]}"
                )
            return "\n".join(lines)

        try:
            from core.project_store import list_sbvr_rules
            rules = list_sbvr_rules(self.project_id)
            words = [w for w in descricao.lower().split() if len(w) > 4]
            rel_rules = [
                r for r in rules
                if any(w in (r.get("statement") or "").lower() for w in words)
            ][:5]
            rules_ctx = "\n".join(
                f"  [{r.get('rule_id','')}] {r.get('statement','')}" for r in rel_rules
            ) or "(nenhuma regra diretamente relacionada)"
        except Exception:
            rules_ctx = "(não disponível)"

        try:
            from core.knowledge_store import get_contradictions
            contras = get_contradictions(self.project_id, status="open", limit=10)
            words = [w for w in descricao.lower().split() if len(w) > 4]
            rel_contras = [
                c for c in contras
                if any(w in (c.get("description") or "").lower() for w in words)
            ][:3]
            contra_ctx = "\n".join(
                f"  [{c.get('severity','—')}] {c.get('description','')}" for c in rel_contras
            ) or "(nenhuma contradição relacionada)"
        except Exception:
            contra_ctx = "(não disponível)"

        restricoes_str = (
            "\n".join(f"  - {k}: {v}" for k, v in restricoes.items())
            if restricoes else "  (não informadas)"
        )

        system_prompt = (
            "Você é especialista em análise de impacto de mudanças em projetos de software. "
            "Analise o cenário proposto e retorne análise de impacto clara em Markdown. "
            "Seja conciso e prático. Responda em Português do Brasil."
        )
        user_prompt = (
            f"## Cenário proposto\n{descricao}\n\n"
            f"## Restrições\n{restricoes_str}\n\n"
            f"## Requisitos diretamente afetados\n{_fmt_reqs(affected_rows, 'Afetados')}\n\n"
            f"## Todos os requisitos do projeto\n{_fmt_reqs(all_reqs, 'Todos')}\n\n"
            f"## Regras SBVR relacionadas\n{rules_ctx}\n\n"
            f"## Contradições abertas relacionadas\n{contra_ctx}\n\n"
            "## Responda com:\n"
            "1. **Sumário do Impacto** (🔴 Alto / 🟡 Médio / 🟢 Baixo) com justificativa\n"
            "2. **Requisitos bloqueados ou afetados indiretamente**\n"
            "3. **Regras SBVR a revisar**\n"
            "4. **Riscos e efeitos colaterais**\n"
            "5. **Recomendação final** (prosseguir / revisar / não prosseguir)\n\n"
            "Máximo 600 palavras."
        )

        # 4. LLM call
        try:
            provider_cfg = self.llm_config.get("provider_cfg", {})
            api_key      = self.llm_config.get("api_key", "")
            model        = self.llm_config.get("model", "deepseek-v4-flash")
            client_type  = provider_cfg.get("client_type", "openai_compatible")

            if client_type == "anthropic":
                import anthropic as _ant
                ac  = _ant.Anthropic(api_key=api_key)
                msg = ac.messages.create(
                    model=model, max_tokens=2048, system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                analysis = (msg.content[0].text or "").strip()
            else:
                from openai import OpenAI as _OAI
                client = _OAI(api_key=api_key, base_url=provider_cfg.get("base_url"))
                kwargs: dict = dict(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user",   "content": user_prompt},
                    ],
                    max_tokens=2048,
                )
                if not provider_cfg.get("reasoning_effort") and "deepseek-v4" not in model.lower():
                    kwargs["temperature"] = 0.3
                analysis = (client.chat.completions.create(**kwargs).choices[0].message.content or "").strip()

        except Exception as exc:
            # Heuristic fallback
            n_aff   = len(affected_rows)
            impact  = "🔴 Alto" if n_aff >= 3 else ("🟡 Médio" if n_aff >= 1 else "🟢 Baixo")
            analysis = (
                f"**Análise heurística** *(LLM indisponível: {exc})*\n\n"
                f"- **Impacto estimado:** {impact}\n"
                f"- **{n_aff}** requisito(s) diretamente identificado(s) como afetado(s).\n"
                f"- Verifique dependências com os demais {len(all_reqs)} requisitos manualmente.\n"
                f"- Regras SBVR relacionadas:\n{rules_ctx[:300]}\n"
            )

        return (
            f"# 🔮 Simulação de Cenário\n\n"
            f"**Cenário:** {descricao}\n\n"
            "---\n\n"
            + analysis
        )

    def verificar_conformidade(
        self,
        doc_id: str | None = None,
        req_type_filter: str | None = None,
        threshold: float = 0.75,
        mode: str = "keyword",
    ) -> str:
        """Check coverage of project requirements against library documents."""
        from modules.supabase_client import get_supabase_client
        from modules.document_store import list_documents, get_document
        import re as _re

        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        # 1. Get documents
        if doc_id:
            doc = get_document(doc_id)
            if not doc:
                return f"Documento com ID `{doc_id}` não encontrado."
            docs = [doc]
        else:
            docs = [d for d in list_documents(project_id=self.project_id, limit=30) if d.get("content_text")]

        if not docs:
            return (
                "Nenhum documento com conteúdo encontrado. "
                "Faça upload e indexe documentos via **📄 Documentos**."
            )

        # 2. Get requirements
        try:
            q = (
                db.table("requirements")
                .select("req_number, title, description, req_type, priority")
                .eq("project_id", self.project_id)
                .order("req_number")
            )
            if req_type_filter:
                q = q.eq("req_type", req_type_filter)
            reqs = q.execute().data or []
        except Exception as exc:
            return f"Erro ao buscar requisitos: {exc}"

        if not reqs:
            hint = f" do tipo '{req_type_filter}'" if req_type_filter else ""
            return f"Nenhum requisito{hint} encontrado no projeto."

        # 3. Keyword helper
        _STOP = {
            "a","o","as","os","de","do","da","dos","das","em","no","na","nos","nas",
            "para","que","um","uma","e","ou","se","com","por","mas","é","ser","ter",
            "ao","à","não","como","mais","deve","há","este","esta","seu","sua","foi",
            "sendo","está","são","pelo","pela","isso","cada","todos","todas",
        }

        def _words(text: str) -> set:
            return {
                w for w in _re.sub(r"[^\w\sáéíóúâêôãçÁÉÍÓÚÂÊÔÃÇ]", " ", text.lower()).split()
                if w not in _STOP and len(w) > 2
            }

        def _score(req_w: set, doc_w: set) -> float:
            return len(req_w & doc_w) / len(req_w) if req_w else 0.0

        # Pre-compute doc word sets (cap content at 50k chars for performance)
        doc_word_sets = [
            (d, _words((d.get("content_text") or "")[:50_000]))
            for d in docs
        ]

        # 4. Analyse each requirement
        covered, partial, uncovered = 0, 0, 0
        gap_rows: list[tuple] = []  # (req_id, title, score, doc_title, doc_id)

        for r in reqs:
            n      = r.get("req_number", "?")
            title  = r.get("title", "")
            desc   = r.get("description", "")
            req_id = f"REQ-{n:03d}" if isinstance(n, int) else f"REQ-{n}"
            rw     = _words(f"{title} {desc}")

            best_score, best_doc = 0.0, None
            for d, dw in doc_word_sets:
                s = _score(rw, dw)
                if s > best_score:
                    best_score, best_doc = s, d

            if best_score >= threshold:
                covered += 1
            elif best_score >= threshold * 0.55:
                partial += 1
                gap_rows.append((req_id, title, best_score, best_doc))
            else:
                uncovered += 1
                gap_rows.append((req_id, title, best_score, best_doc))

        total = len(reqs)
        pct   = 100 * covered / total if total else 0
        icon  = "✅" if pct >= 80 else ("🟡" if pct >= 50 else "🔴")

        lines = [
            "# 🔍 Relatório de Conformidade",
            f"**Documentos analisados:** {len(docs)}  |  **Requisitos:** {total}\n",
            f"## {icon} Cobertura Geral: **{pct:.0f}%** ({covered}/{total})\n",
            f"| Cobertos ✅ | Parciais 🟡 | Não mapeados ❌ |",
            f"|---|---|---|",
            f"| {covered} | {partial} | {uncovered} |\n",
        ]

        if gap_rows:
            lines.append("## ⚠️ Gaps e Cobertura Parcial\n")
            # Sort: uncovered first, then partial
            gap_rows.sort(key=lambda x: x[2])
            for req_id, title, score, d in gap_rows[:20]:
                status     = "❌" if score < threshold * 0.55 else "🟡"
                doc_label  = d.get("title", "—") if d else "nenhum documento"
                lines.append(
                    f"- {status} **{req_id}** — {title}\n"
                    f"  Cobertura: {score:.0%} | Melhor match: *{doc_label}*"
                )
            if len(gap_rows) > 20:
                lines.append(f"*… e mais {len(gap_rows) - 20} requisito(s) com gap*")

        if mode == "llm" and gap_rows:
            lines.append(
                "\n> **Modo LLM:** análise semântica profunda ainda não disponível nesta versão. "
                "Os gaps acima foram identificados por correspondência de palavras-chave (keyword). "
                "Para análise semântica completa, use a aba **⚗️ Extrair Artefatos** em Documentos."
            )

        if uncovered > 0 or partial > 0:
            lines += [
                "\n## 📋 Ações Recomendadas",
                f"- **{uncovered}** requisito(s) sem cobertura — considere criar documentos de especificação.",
                f"- **{partial}** requisito(s) com cobertura parcial — revise a completude dos documentos existentes.",
                "- Use **📄 Documentos** para adicionar BRDs, contratos ou specs e re-execute esta análise.",
            ]

        return "\n".join(lines)

    # ── Editor Estrutural (Fase 2) ────────────────────────────────────────────

    def reordenar_requisitos(
        self,
        nova_ordem: list | None = None,
        agrupar_por: str | None = None,
    ) -> str:
        """Reorder requirements by updating sort_order."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        try:
            rows = (
                db.table("requirements")
                .select("id, req_number, req_type, priority")
                .eq("project_id", self.project_id)
                .execute().data or []
            )
        except Exception as exc:
            return f"Erro ao acessar requisitos: {exc}"

        if not rows:
            return "Nenhum requisito encontrado no projeto."

        # Build id-keyed index: "REQ-001" -> row
        req_by_key: dict = {}
        for r in rows:
            n = r.get("req_number")
            if isinstance(n, int):
                req_by_key[f"REQ-{n:03d}"] = r

        if nova_ordem:
            order_map: dict = {}
            for i, raw_id in enumerate(nova_ordem):
                key = raw_id.strip().upper()
                if not key.startswith("REQ-"):
                    key = f"REQ-{key}"
                if key not in req_by_key:
                    return (
                        f"Requisito '{raw_id}' não encontrado. "
                        "Use identificadores como 'REQ-001'."
                    )
                order_map[req_by_key[key]["id"]] = i + 1

            updated, errors = 0, []
            for rid, order in order_map.items():
                try:
                    db.table("requirements").update({"sort_order": order}).eq("id", rid).execute()
                    updated += 1
                except Exception as exc:
                    errors.append(str(exc))

            msg = f"✅ {updated} requisito(s) reordenado(s) com sucesso."
            if errors:
                msg += f"\n⚠️ {len(errors)} erro(s): " + "; ".join(errors[:3])
            return msg

        elif agrupar_por in ("tipo", "prioridade"):
            priority_rank = {"Crítico": 0, "Alto": 1, "Médio": 2, "Baixo": 3}
            type_rank     = {"Funcional": 0, "Não Funcional": 1, "Regra de Negócio": 2}

            def _key(r: dict):
                if agrupar_por == "prioridade":
                    return (priority_rank.get(r.get("priority") or "", 99), r.get("req_number", 0))
                return (type_rank.get(r.get("req_type") or "", 99), r.get("req_number", 0))

            sorted_rows = sorted(rows, key=_key)
            updated, errors = 0, []
            for i, r in enumerate(sorted_rows):
                try:
                    db.table("requirements").update({"sort_order": i + 1}).eq("id", r["id"]).execute()
                    updated += 1
                except Exception as exc:
                    errors.append(str(exc))

            msg = f"✅ {updated} requisito(s) agrupados por **{agrupar_por}** e reordenados."
            if errors:
                msg += f"\n⚠️ {len(errors)} erro(s): " + "; ".join(errors[:3])
            return msg

        else:
            return (
                "Informe `nova_ordem` (lista de IDs como ['REQ-003','REQ-001']) "
                "ou `agrupar_por` ('tipo' ou 'prioridade')."
            )

    def inserir_secao_ata(
        self,
        meeting_number: int,
        titulo: str,
        conteudo: str,
        posicao: str = "fim",
    ) -> str:
        """Insert a new ## section into a meeting's minutes_md."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        m = self._find_meeting(meeting_number)
        if not m:
            return f"Reunião {meeting_number} não encontrada."

        mid        = m["id"]
        minutes_md = m.get("minutes_md") or ""
        new_section = f"\n## {titulo}\n\n{conteudo}\n"

        if not minutes_md:
            minutes_md = f"# Ata — Reunião {meeting_number}\n{new_section}"
        elif re.search(rf'##\s*{re.escape(titulo)}', minutes_md, re.IGNORECASE):
            return (
                f"⚠️ A seção **{titulo}** já existe na ata da Reunião {meeting_number}. "
                "Para atualizar o conteúdo existente, use apply_text_correction."
            )
        else:
            pl = posicao.lower().strip()
            if pl == "inicio":
                h1 = re.search(r'^#\s+.+\n', minutes_md, re.MULTILINE)
                pos = h1.end() if h1 else 0
                minutes_md = minutes_md[:pos] + new_section + minutes_md[pos:]
            elif pl.startswith("antes_"):
                ref = pl[len("antes_"):].replace("_", " ")
                pat = re.search(rf'(##\s*{re.escape(ref)}\b)', minutes_md, re.IGNORECASE)
                if pat:
                    minutes_md = minutes_md[:pat.start()] + new_section + "\n" + minutes_md[pat.start():]
                else:
                    minutes_md = minutes_md.rstrip() + "\n" + new_section
            elif pl.startswith("apos_") or pl.startswith("após_"):
                prefix = "apos_" if pl.startswith("apos_") else "após_"
                ref = pl[len(prefix):].replace("_", " ")
                sec = re.search(
                    rf'(##\s*{re.escape(ref)}[^\n]*\n[\s\S]*?)(?=\n##|\Z)',
                    minutes_md, re.IGNORECASE,
                )
                if sec:
                    minutes_md = minutes_md[:sec.end()] + "\n" + new_section + minutes_md[sec.end():]
                else:
                    minutes_md = minutes_md.rstrip() + "\n" + new_section
            else:
                # "fim" or unknown
                minutes_md = minutes_md.rstrip() + "\n" + new_section

        try:
            db.table("meetings").update({"minutes_md": minutes_md}).eq("id", mid).execute()
            self._meeting_cache = None
            return f"✅ Seção **{titulo}** inserida na ata da Reunião {meeting_number} (posição: {posicao})."
        except Exception as exc:
            return f"❌ Erro ao salvar ata: {exc}"

    def vincular_regra_debate(
        self,
        rule_id: str,
        ibis_question_id: str,
        relacao: str = "justifica",
    ) -> str:
        """Create or update a SBVR rule ↔ IBIS debate link."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        valid = {"justifica", "contradiz", "limita"}
        if relacao not in valid:
            return f"Relação inválida: '{relacao}'. Use: {', '.join(sorted(valid))}."

        try:
            existing = (
                db.table("sbvr_ibis_links")
                .select("id")
                .eq("project_id", self.project_id)
                .eq("rule_id", rule_id)
                .eq("ibis_question_id", ibis_question_id)
                .execute().data or []
            )
            if existing:
                db.table("sbvr_ibis_links").update({"relacao": relacao}).eq("id", existing[0]["id"]).execute()
                return (
                    f"✅ Vínculo atualizado: **{rule_id}** → **{ibis_question_id}** "
                    f"(relação: {relacao})."
                )
            db.table("sbvr_ibis_links").insert({
                "project_id":      self.project_id,
                "rule_id":         rule_id,
                "ibis_question_id": ibis_question_id,
                "relacao":         relacao,
            }).execute()
            return (
                f"✅ Vínculo criado: regra **{rule_id}** *{relacao}* questão **{ibis_question_id}**."
            )
        except Exception as exc:
            return (
                f"❌ Erro ao vincular: {exc}\n"
                "Certifique-se de que a migration Fase 2 foi executada "
                "(setup/supabase_migration_fase2.sql)."
            )

    def mesclar_reunioes(
        self,
        manter_meeting: int,
        absorver_meeting: int,
        razao: str = "",
        preview: bool = True,
    ) -> str:
        """Merge two meetings: transfer all artifacts and delete the absorbed one."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        m_manter   = self._find_meeting(manter_meeting)
        m_absorver = self._find_meeting(absorver_meeting)
        if not m_manter:
            return f"Reunião {manter_meeting} não encontrada."
        if not m_absorver:
            return f"Reunião {absorver_meeting} não encontrada."
        if manter_meeting == absorver_meeting:
            return "As duas reuniões não podem ser a mesma."

        mid_manter   = m_manter["id"]
        mid_absorver = m_absorver["id"]

        # Collect artifacts from absorbed meeting
        try:
            reqs = (
                db.table("requirements").select("req_number, title")
                .eq("first_meeting_id", mid_absorver)
                .execute().data or []
            )
        except Exception:
            reqs = []

        has_minutes = bool(m_absorver.get("minutes_md"))

        if preview:
            lines = [
                f"**Preview da mesclagem** — Reunião {absorver_meeting} → Reunião {manter_meeting}",
                f"- Razão: {razao or '(não informada)'}",
                f"- {len(reqs)} requisito(s) serão reatribuídos para a Reunião {manter_meeting}:",
            ]
            for r in reqs[:5]:
                n = r.get("req_number", "?")
                lines.append(f"  - REQ-{n:03d}: {r.get('title', '')}" if isinstance(n, int) else f"  - {r.get('title', '')}")
            if len(reqs) > 5:
                lines.append(f"  - ... e mais {len(reqs) - 5}")
            lines.append(
                f"- Ata da Reunião {absorver_meeting}: "
                f"{'será concatenada à ata da Reunião ' + str(manter_meeting) if has_minutes else 'vazia — nenhuma alteração'}"
            )
            lines.append(f"- Reunião {absorver_meeting} será **excluída** após a mesclagem.")
            lines.append("\nPara confirmar, chame novamente com `preview=false`.")
            return "\n".join(lines)

        try:
            # Reatribuir requirements
            for col in ("first_meeting_id", "last_meeting_id"):
                try:
                    db.table("requirements").update({col: mid_manter}).eq(col, mid_absorver).execute()
                except Exception:
                    pass

            # Reatribuir outros artefatos
            for tbl, col in [
                ("sbvr_terms",        "meeting_id"),
                ("sbvr_rules",        "meeting_id"),
                ("bpmn_versions",     "meeting_id"),
                ("transcript_chunks", "meeting_id"),
            ]:
                try:
                    db.table(tbl).update({col: mid_manter}).eq(col, mid_absorver).execute()
                except Exception:
                    pass

            # Concatenar atas
            if has_minutes:
                minutes_manter   = m_manter.get("minutes_md") or ""
                minutes_absorver = m_absorver.get("minutes_md") or ""
                razao_note       = f" — {razao}" if razao else ""
                separator = (
                    f"\n\n---\n"
                    f"*Conteúdo mesclado da Reunião {absorver_meeting}{razao_note}*\n\n"
                )
                merged = minutes_manter.rstrip() + separator + minutes_absorver
                try:
                    db.table("meetings").update({"minutes_md": merged}).eq("id", mid_manter).execute()
                except Exception:
                    pass

            # Excluir reunião absorvida
            db.table("meetings").delete().eq("id", mid_absorver).execute()
            self._meeting_cache = None

            return (
                f"✅ Mesclagem concluída.\n"
                f"- Reunião {absorver_meeting} absorvida pela Reunião {manter_meeting}.\n"
                f"- {len(reqs)} requisito(s) reatribuídos.\n"
                f"- Atas {'concatenadas' if has_minutes else 'sem alteração (absorvida era vazia)'}.\n"
                f"- Reunião {absorver_meeting} excluída."
                + (f"\n- Razão registrada: {razao}" if razao else "")
            )
        except Exception as exc:
            return f"❌ Erro durante a mesclagem: {exc}"

    # ── Sincronizador Calendário (Fase 2) ─────────────────────────────────────

    def sincronizar_calendario(
        self,
        direction: str = "to_calendar",
        meeting_number: int | None = None,
        default_duration: int = 30,
        default_work_start: str = "09:00",
        default_work_end: str = "18:00",
    ) -> str:
        """Sync meeting action items with Google Calendar."""
        from modules.calendar_client import calendar_configured, create_event
        if not calendar_configured():
            return "⚙️ Google Calendar não configurado neste ambiente."
        from modules.supabase_client import get_supabase_client
        import datetime as _dt
        import re as _re
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        meetings = self._load_meetings()
        if meeting_number is not None:
            meetings = [m for m in meetings if m.get("meeting_number") == meeting_number]
            if not meetings:
                return f"Reunião {meeting_number} não encontrada."

        synced, errors, notes = 0, 0, []

        if direction in ("to_calendar", "bidirectional"):
            today = _dt.date.today()
            try:
                h_start, m_start = map(int, default_work_start.split(":"))
            except ValueError:
                h_start, m_start = 9, 0
            start_base = _dt.datetime(today.year, today.month, today.day, h_start, m_start)
            end_base   = start_base + _dt.timedelta(minutes=max(default_duration, 15))
            start_str  = start_base.strftime("%Y-%m-%dT%H:%M:00")
            end_str    = end_base.strftime("%Y-%m-%dT%H:%M:00")

            for m in meetings:
                m_num      = m.get("meeting_number", "?")
                minutes_md = m.get("minutes_md") or ""
                action_txt = self._section(minutes_md, "Itens de Ação", "Action Items", "Ações")
                if not action_txt.strip():
                    continue

                items = [
                    line.strip().lstrip("-•*1234567890.)").strip()
                    for line in action_txt.splitlines()
                    if line.strip() and line.strip()[0] in "-•*0123456789"
                ]

                for item in items[:10]:
                    if not item:
                        continue
                    # Skip if already synced
                    try:
                        already = (
                            db.table("calendar_sync_items")
                            .select("id")
                            .eq("project_id", self.project_id)
                            .eq("meeting_id", m["id"])
                            .eq("action_text", item[:500])
                            .execute().data or []
                        )
                        if already:
                            continue
                    except Exception:
                        pass  # table may not exist yet; proceed anyway

                    try:
                        result_txt = create_event(
                            summary=f"[P2D] {item[:80]}",
                            start_datetime=start_str,
                            end_datetime=end_str,
                            description=f"Encaminhamento — Reunião {m_num} (Process2Diagram)",
                            project_id=self.project_id,
                        )
                        id_match  = _re.search(r'ID:\s+(\S+)', result_txt or "")
                        event_id  = id_match.group(1) if id_match else None
                        try:
                            db.table("calendar_sync_items").insert({
                                "project_id":     self.project_id,
                                "meeting_id":     m["id"],
                                "action_text":    item[:500],
                                "google_event_id": event_id,
                                "sync_direction": "to_calendar",
                                "status":         "synced",
                                "last_sync_at":   _dt.datetime.utcnow().isoformat() + "Z",
                            }).execute()
                        except Exception:
                            pass  # log but don't abort
                        synced += 1
                    except Exception as exc:
                        errors += 1
                        notes.append(f"⚠️ Reunião {m_num}: {str(exc)[:80]}")

        if direction in ("from_calendar", "bidirectional"):
            try:
                tracked = (
                    db.table("calendar_sync_items")
                    .select("id, google_event_id, action_text")
                    .eq("project_id", self.project_id)
                    .eq("status", "synced")
                    .execute().data or []
                )
                notes.append(
                    f"📅 Sync reverso: {len(tracked)} item(s) rastreados no Google Calendar "
                    "(atualização de status requer webhook — não disponível nesta versão)."
                )
            except Exception as exc:
                notes.append(f"⚠️ Erro no sync reverso: {exc}")

        lines = [f"**Sincronização de Calendário** — direção: `{direction}`"]
        if direction in ("to_calendar", "bidirectional"):
            lines.append(f"✅ {synced} encaminhamento(s) criados no Google Calendar.")
            if errors:
                lines.append(f"⚠️ {errors} erro(s).")
            if synced == 0 and errors == 0:
                lines.append(
                    "ℹ️ Todos os encaminhamentos já estavam sincronizados "
                    "ou nenhuma ata contém itens de ação."
                )
        lines.extend(notes[:5])
        return "\n".join(lines)

    # ── Dispatcher ────────────────────────────────────────────────────────────

    def execute(self, tool_name: str, tool_input: dict) -> str:
        """Route a tool call by name to the appropriate implementation."""
        # ── Permission gate: admin-only tools ─────────────────────────────────
        if tool_name in _ADMIN_TOOLS:
            try:
                from modules.auth import is_admin
                if not is_admin():
                    return (
                        f"⛔ A ferramenta '{tool_name}' requer perfil **administrador**. "
                        "Faça login com uma conta admin para usar esta funcionalidade."
                    )
            except Exception:
                pass  # if auth module unavailable, allow (fail-open for safety)

        try:
            dispatch = {
                "get_system_capabilities":   lambda: self.get_system_capabilities(),
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
                "count_artifacts":           lambda: self._count_artifacts(
                    artifact_type=tool_input.get("artifact_type", "all"),
                    req_type=tool_input.get("req_type"),
                    status=tool_input.get("status"),
                ),
                "get_requirements":          lambda: (
                    # Guard: bare call with no keyword = almost certainly a count question.
                    # Redirect to count_artifacts to avoid token waste and wrong routing.
                    self._count_artifacts(
                        artifact_type="requirements",
                        req_type=tool_input.get("req_type"),
                        status=tool_input.get("status"),
                    ) + "\n\n[Dica: para LISTAR o conteúdo dos requisitos, chame "
                      "get_requirements com keyword, req_type ou page.]"
                    if (not tool_input.get("keyword")
                        and not tool_input.get("page")
                        and not tool_input.get("meeting_number")
                        and not tool_input.get("count_only"))
                    else self.get_requirements(
                        keyword=tool_input.get("keyword"),
                        req_type=tool_input.get("req_type"),
                        status=tool_input.get("status"),
                        meeting_number=tool_input.get("meeting_number"),
                        page=int(tool_input.get("page") or 1),
                        page_size=int(tool_input.get("page_size") or 50),
                        count_only=bool(tool_input.get("count_only", False)),
                    )
                ),
                "get_bpmn_execution_log":    lambda: self.get_bpmn_execution_log(),
                "list_bpmn_processes":       lambda: self.list_bpmn_processes(),
                "review_bpmn_diagram":       lambda: self.review_bpmn_diagram(
                    process_name=tool_input["process_name"],
                ),
                "describe_bpmn_process":     lambda: self.describe_bpmn_process(
                    process_name=tool_input["process_name"],
                ),
                "suggest_bpmn_corrections":  lambda: self.suggest_bpmn_corrections(
                    process_name=tool_input["process_name"],
                ),
                "save_bpmn_revision":        lambda: self.save_bpmn_revision(
                    process_name=tool_input["process_name"],
                    bpmn_xml=tool_input["bpmn_xml"],
                    process_description=tool_input.get("process_description", ""),
                    meeting_number=tool_input.get("meeting_number"),
                    revision_notes=tool_input.get("revision_notes", ""),
                ),
                "apply_bpmn_corrections":    lambda: self.apply_bpmn_corrections(
                    process_name=tool_input["process_name"],
                    corrections=tool_input.get("corrections", []),
                    version_notes=tool_input.get("version_notes", ""),
                ),
                "list_bpmn_versions":        lambda: self._list_bpmn_versions(tool_input),
                "delete_bpmn_version":       lambda: self._delete_bpmn_version(tool_input),
                "get_sbvr_terms":            lambda: self.get_sbvr_terms(tool_input.get("keyword")),
                "get_sbvr_rules":            lambda: self.get_sbvr_rules(tool_input.get("keyword")),
                "list_context_files":        lambda: self.list_context_files(),
                "add_sbvr_term":             lambda: self.add_sbvr_term(
                    tool_input["term"],
                    tool_input["definition"],
                    tool_input.get("category", "Conceito"),
                ),
                "update_requirement_status": lambda: self.update_requirement_status(
                    new_status=tool_input["new_status"],
                    req_numbers=tool_input.get("req_numbers"),
                    filter_req_type=tool_input.get("filter_req_type"),
                    filter_current_status=tool_input.get("filter_current_status"),
                    filter_meeting_number=tool_input.get("filter_meeting_number"),
                    status_note=tool_input.get("status_note"),
                ),
                "update_requirement_text":   lambda: self.update_requirement_text(
                    req_number=int(tool_input["req_number"]),
                    new_description=tool_input.get("new_description"),
                    new_title=tool_input.get("new_title"),
                    change_note=tool_input.get("change_note"),
                ),
                "update_sbvr_term":          lambda: self.update_sbvr_term(
                    tool_input["term"],
                    tool_input.get("definition"),
                    tool_input.get("category"),
                    tool_input.get("origin", "assistente"),
                ),
                "update_sbvr_term_by_id":    lambda: self.update_sbvr_term_by_id(
                    term_id=tool_input["term_id"],
                    new_definition=tool_input.get("new_definition"),
                    new_category=tool_input.get("new_category"),
                ),
                "add_sbvr_rule":             lambda: self.add_sbvr_rule(
                    tool_input["statement"],
                    tool_input.get("rule_type", "Behavioral Rule"),
                    tool_input.get("source", "manual"),
                ),
                "update_sbvr_rule":          lambda: self.update_sbvr_rule(
                    rule_id=tool_input["rule_id"],
                    new_statement=tool_input["new_statement"],
                    new_rule_type=tool_input.get("new_rule_type"),
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
                "delete_project_artifacts":       lambda: self.delete_project_artifacts(
                    bool(tool_input.get("confirmed", False)),
                ),
                "rename_meeting":                 lambda: self.rename_meeting(
                    tool_input["meeting_number"],
                    tool_input["new_title"],
                ),
                "batch_rename_meetings":          lambda: self.batch_rename_meetings(
                    renames=tool_input["renames"],
                ),
                "show_meeting_transcript":        lambda: self.show_meeting_transcript(
                    meeting_number=tool_input["meeting_number"],
                ),
                "compare_meeting_transcripts":    lambda: self.compare_meeting_transcripts(
                    meeting_numbers=tool_input["meeting_numbers"],
                ),
                "reprocess_meeting_requirements": lambda: self.reprocess_meeting_requirements(
                    tool_input["meeting_number"],
                    tool_input.get("output_language", "Auto-detect"),
                    bool(tool_input.get("force_replace", True)),
                ),
                "batch_reprocess_requirements":   lambda: self.batch_reprocess_requirements(
                    tool_input.get("meeting_numbers"),
                    bool(tool_input.get("force_replace", True)),
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
                "calendar_diagnose":               lambda: self.calendar_diagnose(),
                "calendar_list_events":            lambda: self.calendar_list_events(
                    max_results=int(tool_input.get("max_results", 10)),
                    time_min=tool_input.get("time_min"),
                    time_max=tool_input.get("time_max"),
                    query=tool_input.get("query"),
                    project_id=self.project_id,
                ),
                "calendar_get_event":              lambda: self.calendar_get_event(
                    tool_input["event_id"],
                    project_id=self.project_id,
                ),
                "calendar_suggest_time":           lambda: self.calendar_suggest_time(
                    duration_minutes=int(tool_input.get("duration_minutes", 60)),
                    attendees=tool_input.get("attendees"),
                    time_min=tool_input.get("time_min"),
                    time_max=tool_input.get("time_max"),
                    max_suggestions=int(tool_input.get("max_suggestions", 3)),
                    project_id=self.project_id,
                ),
                "calendar_create_event":           lambda: self.calendar_create_event(
                    tool_input["summary"],
                    tool_input["start_datetime"],
                    tool_input["end_datetime"],
                    tool_input.get("description"),
                    tool_input.get("location"),
                    tool_input.get("attendees"),
                    project_id=self.project_id,
                ),
                "calendar_schedule_action_items":  lambda: self.calendar_schedule_action_items(
                    tool_input["meeting_number"],
                    tool_input["default_date"],
                    int(tool_input.get("duration_minutes", 30)),
                    project_id=self.project_id,
                ),
                "calendar_share_with_user":        lambda: self.calendar_share_with_user(
                    tool_input["email"],
                    tool_input.get("role", "writer"),
                    project_id=self.project_id,
                ),
                "calendar_revoke_access":          lambda: self.calendar_revoke_access(
                    tool_input["email"],
                    project_id=self.project_id,
                ),
                "get_database_integrity":         lambda: self.get_database_integrity(),
                "fix_missing_llm_provider":       lambda: self.fix_missing_llm_provider(
                    tool_input["provider"],
                ),
                "generate_meeting_embeddings":    lambda: self.generate_meeting_embeddings(
                    tool_input.get("meeting_numbers"),
                ),
                "embed_meeting":                  lambda: self.embed_meeting(
                    tool_input["meeting_number"],
                    bool(tool_input.get("force", False)),
                ),
                "reprocess_meeting_full":         lambda: self.reprocess_meeting_full(
                    tool_input["meeting_number"],
                    bool(tool_input.get("run_bpmn", False)),
                    bool(tool_input.get("run_quality", False)),
                    tool_input.get("output_language", "Auto-detect"),
                ),
                "reprocess_communication_noise":  lambda: self.reprocess_communication_noise(
                    tool_input["meeting_number"],
                    tool_input.get("output_language", "Auto-detect"),
                ),
                "regenerate_executive_report":    lambda: self.regenerate_executive_report(
                    tool_input["meeting_number"],
                    tool_input.get("output_language", "Auto-detect"),
                ),
                # ── Moedas ───────────────────────────────────────────────
                "convert_usd_to_brl": lambda: self.convert_usd_to_brl(
                    float(tool_input["usd_amount"]),
                ),
                # ── Chart tools ───────────────────────────────────────────────
                "generate_requirements_chart":    lambda: self.generate_requirements_chart(
                    group_by=tool_input.get("group_by", "type"),
                    meeting_number=tool_input.get("meeting_number"),
                ),
                "generate_meetings_timeline":     lambda: self.generate_meetings_timeline(
                    metric=tool_input.get("metric", "all"),
                ),
                "generate_action_items_chart":    lambda: self.generate_action_items_chart(
                    group_by=tool_input.get("group_by", "status"),
                    meeting_number=tool_input.get("meeting_number"),
                ),
                "generate_roi_chart":             lambda: self.generate_roi_chart(
                    cost_per_hour=float(tool_input.get("cost_per_hour", 150.0)),
                ),
                # ── User / Domain query tools ─────────────────────────────────
                "get_users_by_domain":            lambda: self.get_users_by_domain(
                    tool_input["domain"],
                ),
                "list_all_domains":               lambda: self.list_all_domains_tool(),
                "list_users_by_project":          lambda: self.list_users_by_project_tool(
                    tool_input.get("project_id"),
                ),
                "rename_meeting":                 lambda: self.rename_meeting(
                    meeting_number=tool_input["meeting_number"],
                    new_title=tool_input["new_title"],
                ),
                "batch_rename_meetings":          lambda: self.batch_rename_meetings(
                    renames=tool_input["renames"],
                ),
                "show_meeting_transcript":        lambda: self.show_meeting_transcript(
                    meeting_number=tool_input["meeting_number"],
                ),
                "compare_meeting_transcripts":    lambda: self.compare_meeting_transcripts(
                    meeting_numbers=tool_input["meeting_numbers"],
                ),
                "set_active_project":             lambda: self.set_active_project(
                    tool_input["project_name"],
                ),
                "save_context_skill":             lambda: self.save_context_skill(
                    tool_input["skill_md"],
                ),
                "generate_custom_chart":          lambda: self.generate_custom_chart(
                    chart_type=tool_input["chart_type"],
                    title=tool_input["title"],
                    labels=tool_input["labels"],
                    values=[float(v) for v in tool_input["values"]],
                    x_label=tool_input.get("x_label", ""),
                    y_label=tool_input.get("y_label", ""),
                    series_name=tool_input.get("series_name", ""),
                ),
                "populate_roster":          lambda: self._populate_roster(tool_input),
                "populate_knowledge_hub":    lambda: self._populate_knowledge_hub(tool_input),
                "detect_contradictions":     lambda: self._detect_contradictions(),
                "resolve_entity_ambiguity":  lambda: self._resolve_entity_ambiguity(tool_input),
                "lookup_entity":             lambda: self._lookup_entity(tool_input),
                "delete_entity":             lambda: self._delete_entity(tool_input),
                "get_cache_stats":           lambda: self.get_cache_stats(tool_input.get("agent_name")),
                "clear_llm_cache":           lambda: self.clear_llm_cache(tool_input.get("agent_name")),
                "render_table": lambda: self._render_table(tool_input),
                "get_executive_report": lambda: self.get_executive_report(
                    tool_input["meeting_number"],
                ),
                # Document tools
                "list_meeting_documents": lambda: self.list_meeting_documents(
                    meeting_number=tool_input.get("meeting_number"),
                    doc_type=tool_input.get("doc_type"),
                    category=tool_input.get("category"),
                ),
                "get_document_content":   lambda: self.get_document_content(tool_input["doc_id"]),
                "search_documents":       lambda: self.search_documents(
                    query=tool_input["query"],
                    mode=tool_input.get("mode", "semantic"),
                ),
                "get_document_types":     lambda: self.get_document_types_tool(),
                "suggest_document_title": lambda: self.suggest_document_title(
                    doc_id=tool_input["doc_id"],
                    apply=tool_input.get("apply", False),
                ),
                # Histórico de requisitos / BMM / CKF / Knowledge Graph
                "get_requirement_history": lambda: self.get_requirement_history(
                    req_number=tool_input["req_number"],
                ),
                "get_bmm":                lambda: self.get_bmm(
                    meeting_number=tool_input.get("meeting_number"),
                ),
                "get_ckf":                lambda: self.get_ckf(),
                "list_kh_entities":       lambda: self.list_kh_entities(
                    entity_type=tool_input.get("entity_type"),
                    limit=int(tool_input.get("limit", 50)),
                ),
                "list_kh_contradictions": lambda: self.list_kh_contradictions(
                    status=tool_input.get("status", "open"),
                ),
                "resolve_contradiction":  lambda: self.resolve_contradiction(
                    description_query=tool_input["description_query"],
                    resolution_note=tool_input["resolution_note"],
                    resolved_by=tool_input.get("resolved_by", "assistente"),
                    new_status=tool_input.get("new_status", "resolved"),
                ),
                "delete_contradiction":   lambda: self.delete_contradiction(
                    description_query=tool_input["description_query"],
                    confirm=bool(tool_input.get("confirm", False)),
                ),
                "list_kh_facts":          lambda: self.list_kh_facts(
                    fact_type=tool_input.get("fact_type"),
                    limit=int(tool_input.get("limit", 50)),
                ),
                # Ajuda P2D
                "get_p2d_help":           lambda: self.get_p2d_help(tool_input["topic"]),
                # Glossário / Skills
                "search_glossary":        lambda: self.search_glossary(
                    query=tool_input["query"],
                    tag=tool_input.get("tag"),
                ),
                "read_skill_reference":   lambda: self.read_skill_reference(
                    agent=tool_input["agent"],
                    section=tool_input.get("section"),
                ),
                # IBIS
                "search_ibis_debates":    lambda: self.search_ibis_debates(
                    query=tool_input["query"],
                    meeting_number=tool_input.get("meeting_number"),
                    resolution_filter=tool_input.get("resolution_filter", "all"),
                ),
                "get_ibis_timeline":      lambda: self.get_ibis_timeline(
                    topic=tool_input.get("topic"),
                ),
                "generate_ibis_map":      lambda: self.generate_ibis_map(
                    topic=tool_input.get("topic"),
                ),
                # ── Cross-meeting / agenda
                "generate_next_agenda":   lambda: self.generate_next_agenda(
                    topic=tool_input.get("topic"),
                ),
                "cluster_topic_decisions": lambda: self.cluster_topic_decisions(
                    topic=tool_input["topic"],
                    artifact_type=tool_input.get("artifact_type", "all"),
                ),
                # ── A2UI
                "show_bpmn_diagram":      lambda: self.show_bpmn_diagram(
                    process_name=tool_input.get("process_name"),
                    meeting_number=tool_input.get("meeting_number"),
                ),
                "show_mermaid_diagram":   lambda: self.show_mermaid_diagram(
                    meeting_number=tool_input["meeting_number"],
                ),
                "render_mermaid_code":    lambda: self.render_mermaid_code(
                    mermaid_code=tool_input["mermaid_code"],
                    title=tool_input.get("title", ""),
                ),
                "show_metrics":           lambda: self.show_metrics(
                    items=tool_input["items"],
                    title=tool_input.get("title", ""),
                ),
                # ── Plantonista / Diagnóstico
                "sugestoes_plantonista":  lambda: self.sugestoes_plantonista(),
                "diagnostico_projeto":    lambda: self.diagnostico_projeto(
                    include_integrity=bool(tool_input.get("include_integrity", True)),
                    include_contradictions=bool(tool_input.get("include_contradictions", True)),
                    include_roi=bool(tool_input.get("include_roi", True)),
                    include_recurring=bool(tool_input.get("include_recurring", True)),
                    include_pendencies=bool(tool_input.get("include_pendencies", True)),
                ),
                # ── Sugestor / Deck / Charter (Fase 4)
                "sugerir_processos":      lambda: self.sugerir_processos(
                    min_reunioes=int(tool_input.get("min_reunioes", 2)),
                    confidence=float(tool_input.get("confidence", 0.7)),
                    include_evidence=bool(tool_input.get("include_evidence", True)),
                ),
                "gerar_deck_executivo":   lambda: self.gerar_deck_executivo(
                    incluir_secoes=tool_input.get("incluir_secoes"),
                    meeting_numbers=tool_input.get("meeting_numbers"),
                    tema_cores=tool_input.get("tema_cores", "corporativo"),
                ),
                "gerar_project_charter":  lambda: self.gerar_project_charter(
                    incluir_riscos=bool(tool_input.get("incluir_riscos", True)),
                    incluir_cronograma=bool(tool_input.get("incluir_cronograma", True)),
                    incluir_stakeholders=bool(tool_input.get("incluir_stakeholders", True)),
                    incluir_escopo=bool(tool_input.get("incluir_escopo", True)),
                ),
                # ── Rastreabilidade / Simulação / Conformidade (Fase 3)
                "mapa_rastreabilidade":   lambda: self.mapa_rastreabilidade(
                    req_number=tool_input.get("req_number"),
                    topic=tool_input.get("topic"),
                    include_transcript=bool(tool_input.get("include_transcript", True)),
                    include_bpmn=bool(tool_input.get("include_bpmn", True)),
                    include_sbvr=bool(tool_input.get("include_sbvr", True)),
                    include_ibis=bool(tool_input.get("include_ibis", True)),
                ),
                "simular_cenario":        lambda: self.simular_cenario(
                    descricao=tool_input["descricao"],
                    requisitos_afetados=tool_input.get("requisitos_afetados"),
                    restricoes=tool_input.get("restricoes"),
                ),
                "verificar_conformidade": lambda: self.verificar_conformidade(
                    doc_id=tool_input.get("doc_id"),
                    req_type_filter=tool_input.get("req_type_filter"),
                    threshold=float(tool_input.get("threshold", 0.75)),
                    mode=tool_input.get("mode", "keyword"),
                ),
                # ── Editor Estrutural (Fase 2)
                "reordenar_requisitos":   lambda: self.reordenar_requisitos(
                    nova_ordem=tool_input.get("nova_ordem"),
                    agrupar_por=tool_input.get("agrupar_por"),
                ),
                "inserir_secao_ata":      lambda: self.inserir_secao_ata(
                    meeting_number=int(tool_input["meeting_number"]),
                    titulo=tool_input["titulo"],
                    conteudo=tool_input["conteudo"],
                    posicao=tool_input.get("posicao", "fim"),
                ),
                "vincular_regra_debate":  lambda: self.vincular_regra_debate(
                    rule_id=tool_input["rule_id"],
                    ibis_question_id=tool_input["ibis_question_id"],
                    relacao=tool_input.get("relacao", "justifica"),
                ),
                "mesclar_reunioes":       lambda: self.mesclar_reunioes(
                    manter_meeting=int(tool_input["manter_meeting"]),
                    absorver_meeting=int(tool_input["absorver_meeting"]),
                    razao=tool_input.get("razao", ""),
                    preview=bool(tool_input.get("preview", True)),
                ),
                # ── Sincronizador Calendário (Fase 2)
                "sincronizar_calendario": lambda: self.sincronizar_calendario(
                    direction=tool_input.get("direction", "to_calendar"),
                    meeting_number=tool_input.get("meeting_number"),
                    default_duration=int(tool_input.get("default_duration", 30)),
                    default_work_start=tool_input.get("default_work_start", "09:00"),
                    default_work_end=tool_input.get("default_work_end", "18:00"),
                ),
            }
            if tool_name not in dispatch:
                return f"Ferramenta desconhecida: '{tool_name}'"
            return dispatch[tool_name]()
        except Exception as exc:
            return f"Erro ao executar '{tool_name}': {exc}"
