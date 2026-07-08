# core/tools/tools_meetings_requirements.py
# Auto-extracted from core/assistant_tools.py (split PC115) — mixin for AssistantToolExecutor.
# Methods here assume `self` is an AssistantToolExecutor instance (project_id, llm_config,
# _meeting_cache, _pending_charts, _palette — set in AssistantToolExecutor.__init__).

from __future__ import annotations
import re
from core.chart_config import CHART_PALETTES, DEFAULT_PALETTE
from core.tools._shared import _compute_initials


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Pure-Python cosine similarity — avoids adding numpy just for this."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


MEETINGS_REQUIREMENTS_SCHEMAS: list[dict] = [
            {
                "type": "function",
                "function": {
                    "name": "get_meeting_list",
                    "description": (
                        "Lista todas as reuniões do projeto com número, título, data, "
                        "e indica se possuem ata e transcrição armazenadas. "
                        "Use order_by='date' para listar por data cronológica da reunião "
                        "(útil quando reuniões foram inseridas fora de ordem no sistema). "
                        "Use order_by='number' (padrão) para listar por número de entrada."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "order_by": {
                                "type": "string",
                                "enum": ["number", "date"],
                                "description": (
                                    "'number' (padrão) — ordena pelo número de entrada no sistema. "
                                    "'date' — ordena pela data real da reunião (campo meeting_date). "
                                    "Use 'date' quando o usuário pedir por ordem cronológica ou mencionar "
                                    "que reuniões foram inseridas fora de ordem."
                                ),
                            }
                        },
                        "required": [],
                    },
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
                    "description": (
                        "Retorna as decisões formais (deliberações) tomadas em uma reunião "
                        "específica. NÃO use para 'encaminhamentos', 'itens de ação' ou "
                        "'tarefas com responsável' — isso é get_meeting_action_items."
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
                    "name": "get_meeting_processing_history",
                    "description": (
                        "Retorna o histórico de processamento de uma reunião: quando ela foi "
                        "processada pela primeira vez e cada reprocessamento posterior (completo "
                        "ou de um agente específico), com data efetiva, tokens e sucesso/erro. "
                        "Use para 'quantas vezes essa reunião foi processada/reprocessada', "
                        "'quando essa reunião foi processada de verdade' (útil quando a data "
                        "registrada da reunião parece não bater com o processamento real)."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_number": {
                                "type": "integer",
                                "description": "Número da reunião",
                            },
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
                        "Retorna os itens de ação — também chamados de 'encaminhamentos' ou "
                        "'tarefas' — definidos em uma reunião. Pode filtrar por responsável. "
                        "Use para 'encaminhamentos', 'itens de ação', 'tarefas atribuídas' "
                        "(diferente de get_meeting_decisions, que é para deliberações formais)."
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
            {
                "type": "function",
                "function": {
                    "name": "sample_requirements",
                    "description": (
                        "Retorna uma amostra ALEATÓRIA de requisitos de uma reunião — mais rápido e barato "
                        "que paginar com get_requirements quando o objetivo é avaliar qualidade/granularidade "
                        "geral, não ler todos os itens. Use quando o usuário pedir para 'dar uma olhada', "
                        "'ver um exemplo', 'avaliar o padrão' dos requisitos de uma reunião."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_number": {
                                "type": "integer",
                                "description": "Número da reunião cujos requisitos serão amostrados",
                            },
                            "sample_size": {
                                "type": "integer",
                                "description": "Quantos requisitos incluir na amostra (padrão 20, máximo 100)",
                            },
                            "seed": {
                                "type": "integer",
                                "description": "Semente aleatória opcional, para amostra reprodutível",
                            },
                        },
                        "required": ["meeting_number"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "analyze_requirement_quality",
                    "description": (
                        "Gera um relatório estatístico sobre a granularidade dos requisitos de uma reunião: "
                        "tamanho médio de título/descrição, palavras mais frequentes nos títulos, e proporção "
                        "requisitos-por-100-palavras da transcrição (sinaliza super-granularidade quando alta). "
                        "Use para diagnosticar rapidamente se uma reunião produziu requisitos "
                        "excessivamente fragmentados, sem precisar ler item por item."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_number": {
                                "type": "integer",
                                "description": "Número da reunião a analisar",
                            },
                        },
                        "required": ["meeting_number"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "estimar_risco_requisito",
                    "description": (
                        "Calcula um score de risco (0-100) por requisito cruzando: nº de "
                        "revisões (instabilidade), contradição sinalizada em alguma versão, "
                        "ausência de source_quote (rastreabilidade fraca), descrição "
                        "curta/vaga (ambiguidade) e prioridade alta sem status avançado. "
                        "Sem análise semântica profunda — heurística ponderada e transparente, "
                        "não um julgamento definitivo. Informe req_number para o detalhamento "
                        "de 1 requisito, ou omita para o ranking dos mais arriscados do "
                        "projeto. Use quando o usuário pedir 'quais requisitos são mais "
                        "arriscados', 'risco do REQ-X' ou 'onde focar a revisão'."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "req_number": {
                                "type": "integer",
                                "description": "Número do requisito específico (opcional — padrão: ranking do projeto todo).",
                            },
                            "top_n": {
                                "type": "integer",
                                "description": "Quantos requisitos mostrar no ranking (ignorado se req_number for informado). Padrão: 10.",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "map_transcript_to_requirements",
                    "description": (
                        "Divide a transcrição de uma reunião em trechos/parágrafos e conta quantos requisitos "
                        "cada trecho gerou (via source_quote de cada requisito) — revela ONDE exatamente um "
                        "possível oversplitting está ocorrendo (trechos técnicos específicos vs. distribuição "
                        "uniforme). Use para localizar a origem de uma super-granularidade já detectada."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_number": {
                                "type": "integer",
                                "description": "Número da reunião a mapear",
                            },
                        },
                        "required": ["meeting_number"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "cluster_similar_requirements",
                    "description": (
                        "Agrupa requisitos de uma reunião por similaridade semântica (embeddings) — revela "
                        "'famílias' de requisitos que dizem essencialmente a mesma coisa com palavras "
                        "diferentes (ex: 'validar CPF' / 'CPF deve ser validado' → mesmo cluster). "
                        "Use para detectar duplicação semântica ou consolidar requisitos redundantes. "
                        "Custa uma chamada de API de embedding por requisito — limitado a 200 por chamada "
                        "por padrão; para reuniões maiores, combine com sample_requirements primeiro."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_number": {
                                "type": "integer",
                                "description": "Número da reunião cujos requisitos serão clusterizados",
                            },
                            "threshold": {
                                "type": "number",
                                "description": "Similaridade de cosseno mínima para agrupar no mesmo cluster (0.5–0.99, padrão 0.85)",
                            },
                            "max_requirements": {
                                "type": "integer",
                                "description": "Limite de requisitos processados nesta chamada (padrão 200, protege contra custo excessivo)",
                            },
                        },
                        "required": ["meeting_number"],
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
                    "name": "update_requirement_status",
                    "description": (
                        "Atualiza o status de um ou mais requisitos do projeto. "
                        "Pode filtrar por número(s) de requisito, tipo, status atual ou reunião de origem. "
                        "USE quando o usuário pedir para mudar, atualizar ou corrigir o status de requisitos. "
                        "Para marcar como IMPLEMENTADO e registrar a solução, prefira update_requirement_implementation. "
                        "Registra uma nova versão em requirement_versions com change_type='status_change'."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "new_status": {
                                "type": "string",
                                "enum": [
                                    "active", "backlog", "approved", "in_progress",
                                    "implemented", "revised", "contradicted",
                                    "deprecated", "rejected", "confirmed",
                                ],
                                "description": (
                                    "Novo status a aplicar. "
                                    "active=ativo/em vigor, backlog=pendente análise, approved=aprovado, "
                                    "in_progress=em desenvolvimento, implemented=implementado, "
                                    "revised=revisado, contradicted=contradição, "
                                    "deprecated=depreciado, rejected=rejeitado."
                                ),
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
                    "name": "update_requirement_implementation",
                    "description": (
                        "Marca um requisito como implementado e registra a solução adotada. "
                        "USE quando o usuário disser que um requisito foi atendido, desenvolvido, "
                        "entregue ou resolvido, e quiser documentar como foi implementado. "
                        "Exemplos: 'O REQ-050 foi implementado — criamos tela de aprovação automática', "
                        "'Marque o REQ-120 como concluído com a nota: integração via API REST'. "
                        "Define status='implemented', registra resolution_notes e implemented_at. "
                        "Cria versão em requirement_versions com change_type='implementation'."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "req_number": {
                                "type": "integer",
                                "description": "Número do requisito (ex: 50 para REQ-050).",
                            },
                            "resolution_notes": {
                                "type": "string",
                                "description": (
                                    "Descrição da solução adotada: o que foi desenvolvido, "
                                    "como foi implementado, qual componente/módulo atende ao requisito. "
                                    "Obrigatório — sem esta informação a implementação não fica rastreável."
                                ),
                            },
                            "new_status": {
                                "type": "string",
                                "enum": ["implemented", "in_progress", "approved", "deprecated", "rejected"],
                                "description": (
                                    "Status a aplicar. Padrão: 'implemented'. "
                                    "Use 'in_progress' se ainda estiver em desenvolvimento mas quiser registrar nota parcial."
                                ),
                            },
                        },
                        "required": ["req_number", "resolution_notes"],
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
]

class _MeetingsRequirementsToolsMixin:
    """Mixin: tools_meetings_requirements tools."""

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

    def _meeting_lookup(self) -> dict[str, dict]:
        """Return {meeting_id_uuid: {number, date, title}} from cached meetings."""
        return {
            m["id"]: {
                "number": m.get("meeting_number"),
                "date":   (m.get("meeting_date") or "")[:10] or "sem data",
                "title":  m.get("title") or "",
            }
            for m in self._get_meetings()
            if m.get("id")
        }

    def _fmt_meeting_tag(info: dict | None) -> str:
        """Format 'Reunião N (YYYY-MM-DD)' from a lookup entry, or '' if None."""
        if not info:
            return ""
        n    = info.get("number", "?")
        date = info.get("date") or "sem data"
        return f"Reunião {n} ({date})"

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

        valid_statuses = {
            "active", "backlog", "approved", "in_progress",
            "implemented", "revised", "contradicted",
            "deprecated", "rejected", "confirmed",
        }
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

    def update_requirement_implementation(
        self,
        req_number: int,
        resolution_notes: str,
        new_status: str = "implemented",
    ) -> str:
        """Marca requisito como implementado e registra a solução adotada."""
        from modules.supabase_client import get_supabase_client
        from datetime import datetime, timezone
        db = get_supabase_client()
        if not db:
            return "❌ Supabase não configurado."
        if not resolution_notes or not resolution_notes.strip():
            return "❌ resolution_notes é obrigatório para documentar a solução implementada."

        valid = {"implemented", "in_progress", "approved", "deprecated", "rejected"}
        if new_status not in valid:
            new_status = "implemented"

        try:
            rows = (
                db.table("requirements")
                .select("id, req_number, title, description, status, priority, req_type, first_meeting_id")
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
        now = datetime.now(timezone.utc).isoformat()

        patch = {
            "status":           new_status,
            "resolution_notes": resolution_notes.strip(),
            "implemented_at":   now,
        }
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
            db.table("requirement_versions").insert({
                "requirement_id": rid,
                "meeting_id":     row.get("first_meeting_id"),
                "version":        next_ver,
                "title":          row.get("title", ""),
                "description":    row.get("description"),
                "status":         new_status,
                "priority":       row.get("priority"),
                "req_type":       row.get("req_type"),
                "change_type":    "implementation",
                "changed_at":     now,
                "change_note":    f"Implementação registrada: {resolution_notes.strip()[:200]}",
            }).execute()
        except Exception:
            pass  # versionamento é best-effort

        status_label = {
            "implemented": "Implementado",
            "in_progress": "Em Desenvolvimento",
            "approved":    "Aprovado",
            "deprecated":  "Depreciado",
            "rejected":    "Rejeitado",
        }.get(new_status, new_status)

        return (
            f"✅ REQ-{req_number:03d} — **{row.get('title', '')}**\n"
            f"• Status: → **{status_label}**\n"
            f"• Solução registrada: {resolution_notes.strip()[:300]}\n"
            f"• Registrado em: {now[:10]}"
        )

    def _section(self, minutes_md: str, *section_names: str) -> str:
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
    show_bpmn_diagram, show_mermaid_diagram, show_metrics, render_requirements_table

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

    def get_meeting_list(self, order_by: str = "number") -> str:
        meetings = list(self._get_meetings())  # copy — don't mutate cache
        if not meetings:
            return "Nenhuma reunião encontrada no projeto."

        order_label = "por número de entrada"
        if order_by == "date":
            # Sort by meeting_date (ISO string "YYYY-MM-DD"); nulls go to the end
            meetings.sort(key=lambda m: (m.get("meeting_date") or "9999-99-99"))
            order_label = "por data da reunião"

        lines = [f"Reuniões do projeto ({len(meetings)} no total) — {order_label}:"]
        for m in meetings:
            n     = m.get("meeting_number", "?")
            title = m.get("title") or "Sem título"
            date  = m.get("meeting_date") or "sem data"
            flags = []
            if m.get("minutes_md"):
                flags.append("✓ ata")
            if m.get("transcript_clean") or m.get("transcript_raw"):
                flags.append("✓ transcrição")
            flag_str = ", ".join(flags) if flags else "✗ sem dados"
            lines.append(f"  Reunião {n}: {title} ({date}) [{flag_str}]")

        if order_by == "date":
            lines.append(
                "\nNota: 'Reunião N' é o número de entrada no sistema (ordem de processamento), "
                "não necessariamente a ordem cronológica."
            )
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
            "Encaminhamentos / Action Items", "Encaminhamentos",
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

    def get_meeting_processing_history(self, meeting_number: int) -> str:
        """History of every processing/reprocessing event for a meeting (PC152)."""
        m = self._find_meeting(meeting_number)
        if not m:
            return f"Reunião {meeting_number} não encontrada."
        title = m.get("title") or f"Reunião {meeting_number}"
        header = f"Reunião {meeting_number} — {title}"

        from core.project_store import get_meeting_processing_history
        rows = get_meeting_processing_history(m["id"])
        if not rows:
            return (
                f"{header}\nNenhum registro de processamento encontrado — a tabela de "
                "histórico foi introduzida depois desta reunião ter sido processada, ou "
                "o processamento ainda não foi registrado."
            )

        _type_label = {
            "new": "Processamento inicial",
            "reprocess_full": "Reprocessamento completo",
            "reprocess_agent": "Reprocessamento de agente",
        }
        lines = [f"{header}\nHistórico de processamento ({len(rows)} evento(s)):"]
        for r in rows:
            ts = (r.get("processed_at") or "")[:19].replace("T", " ")
            label = _type_label.get(r.get("processing_type"), r.get("processing_type") or "?")
            if r.get("processing_type") == "reprocess_agent" and r.get("agent_name"):
                label += f" ({r['agent_name']})"
            status = "✅" if r.get("success", True) else f"❌ {r.get('error_message') or 'erro'}"
            tokens = r.get("total_tokens") or 0
            lines.append(f"  - {ts} — {label} — {status}" + (f" — {tokens:,} tokens" if tokens else ""))
        return "\n".join(lines)

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
                        "source_quote, cited_by, first_meeting_id, "
                        "resolution_notes, implemented_at",
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
                        "source_quote, cited_by, first_meeting_id, "
                        "resolution_notes, implemented_at",
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

        # Build meeting lookup only when listing across meetings (no filter)
        mlookup = self._meeting_lookup() if not meeting_id_filter else {}

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
            res     = r.get("resolution_notes") or ""
            impl_at = (r.get("implemented_at") or "")[:10]
            mtag    = self._fmt_meeting_tag(mlookup.get(r.get("first_meeting_id") or ""))
            meeting_suffix = f" | {mtag}" if mtag else ""
            lines.append(f"• {req_id} [{rtype} | {rstatus} | prioridade: {rprio}{meeting_suffix}]: {title}")
            if desc:
                lines.append(f"  {desc}")
            if cited or quote:
                attr = f"[{cited}] " if cited else ""
                if quote:
                    lines.append(f'  > {attr}"{quote}"')
                elif cited:
                    lines.append(f"  Autor: {cited}")
            if res:
                impl_date = f" ({impl_at})" if impl_at else ""
                lines.append(f"  ✅ Solução{impl_date}: {res[:200]}")

        if page < total_pages:
            lines.append(
                f"\n[Há mais requisitos. Chame get_requirements(page={page + 1}) para continuar.]"
            )

        return "\n".join(lines)

    # ── Investigative tools (PC141) ───────────────────────────────────────────
    # 4 tools proposed by the assistant itself after investigating a real
    # duplication incident (PC140) with only paginated get_requirements calls.
    # All operate on ONE meeting's requirements (via first_meeting_id) and
    # avoid full-table pagination for diagnostic/quality questions.

    def _requirements_for_meeting(self, meeting_number: int, fields: str) -> tuple[dict | None, list[dict], str]:
        """Shared resolution: meeting_number -> (meeting_dict, requirement_rows, error_message).
        error_message is non-empty (and the other two are None/[]) on failure."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return None, [], "Banco de dados não disponível."
        mtg = self._find_meeting(meeting_number)
        if not mtg:
            return None, [], f"Reunião {meeting_number} não encontrada."
        try:
            rows = (
                db.table("requirements")
                .select(fields)
                .eq("project_id", self.project_id)
                .eq("first_meeting_id", mtg["id"])
                .order("req_number")
                .execute()
                .data or []
            )
        except Exception as exc:
            return None, [], f"Erro ao acessar requisitos: {exc}"
        if not rows:
            return None, [], f"Nenhum requisito encontrado para a Reunião {meeting_number}."
        return mtg, rows, ""

    def sample_requirements(
        self,
        meeting_number: int,
        sample_size: int = 20,
        seed: int | None = None,
    ) -> str:
        """Amostra aleatória (não paginada) de requisitos de uma reunião."""
        import random

        mtg, rows, err = self._requirements_for_meeting(
            meeting_number, "req_number, title, description, req_type, priority, status"
        )
        if err:
            return err

        sample_size = max(1, min(int(sample_size or 20), len(rows), 100))
        rng = random.Random(seed) if seed is not None else random.Random()
        sample = sorted(rng.sample(rows, sample_size), key=lambda r: r.get("req_number") or 0)

        lines = [f"Amostra aleatória de {sample_size} de {len(rows)} requisito(s) — Reunião {meeting_number}:"]
        for r in sample:
            n = r.get("req_number")
            req_id = f"REQ-{n:03d}" if isinstance(n, int) else "REQ-???"
            desc = (r.get("description") or "")[:120]
            lines.append(
                f"• {req_id} [{r.get('req_type') or '—'} | {r.get('priority') or '—'} | {r.get('status') or '—'}] "
                f"{r.get('title') or ''} — {desc}"
            )
        return "\n".join(lines)

    def analyze_requirement_quality(self, meeting_number: int) -> str:
        """Relatório estatístico de granularidade dos requisitos de uma reunião."""
        import re
        from collections import Counter

        mtg, rows, err = self._requirements_for_meeting(meeting_number, "title, description")
        if err:
            return err

        transcript = (mtg.get("transcript_clean") or mtg.get("transcript_raw") or "")
        n_words_transcript = len(transcript.split())

        titles = [r.get("title") or "" for r in rows]
        descs = [r.get("description") or "" for r in rows]
        avg_title_len = sum(len(t) for t in titles) / len(titles)
        avg_desc_len = sum(len(d) for d in descs) / len(descs) if descs else 0.0

        _STOPWORDS = {
            "o", "a", "os", "as", "de", "do", "da", "dos", "das", "que", "e",
            "para", "com", "em", "um", "uma", "deve", "sistema", "ser", "no",
            "na", "ao", "aos", "às", "se", "por", "the", "of", "to", "and",
        }
        words = re.findall(r"\w+", " ".join(titles).lower())
        words = [w for w in words if w not in _STOPWORDS and len(w) > 2]
        common = Counter(words).most_common(10)

        ratio_per_100 = (len(rows) / n_words_transcript * 100) if n_words_transcript else 0.0
        # ~1 req per 40 words (2.5/100) is already dense for a well-scoped
        # extraction; above that is a red flag for over-fragmentation.
        alert = ratio_per_100 > 2.5

        lines = [
            f"# Qualidade dos Requisitos — Reunião {meeting_number}",
            f"Total de requisitos: {len(rows)}",
            f"Palavras na transcrição: {n_words_transcript}",
            f"Proporção: {ratio_per_100:.2f} requisitos por 100 palavras"
            + (" ⚠️ possível super-granularidade" if alert else ""),
            f"Tamanho médio do título: {avg_title_len:.0f} caracteres",
            f"Tamanho médio da descrição: {avg_desc_len:.0f} caracteres",
            "",
            "Palavras mais frequentes nos títulos: "
            + (", ".join(f"{w} ({n})" for w, n in common) if common else "—"),
        ]
        return "\n".join(lines)

    _VAGUE_WORDS = {
        "adequado", "adequada", "apropriado", "apropriada", "conforme necessário",
        "quando aplicável", "de forma eficiente", "etc", "diversos", "diversas",
        "algum", "alguma", "alguns", "algumas", "flexível", "robusto", "amigável",
    }

    @classmethod
    def _is_vague_description(cls, description: str) -> bool:
        """Best-effort heuristic, not NLP: a description is flagged as vague
        when it's short (<8 words) or contains a hedge/filler word commonly
        associated with unmeasurable requirements. Transparent and coarse
        on purpose — never presented as a semantic judgment."""
        text = (description or "").strip()
        if not text:
            return True
        words = text.split()
        if len(words) < 8:
            return True
        lowered = text.lower()
        return any(w in lowered for w in cls._VAGUE_WORDS)

    def _score_requirement_risk(self, req: dict, n_revisions: int, has_contradiction: bool) -> dict:
        """Weighted heuristic, 0-100: instabilidade (revisões) + contradição +
        rastreabilidade fraca (sem source_quote) + ambiguidade (descrição
        curta/vaga) + prioridade alta sem status avançado."""
        score = 0
        factors: list[str] = []

        revision_points = min(max(n_revisions - 1, 0) * 15, 30)
        if revision_points:
            score += revision_points
            factors.append(f"{n_revisions} versão(ões) registrada(s) (+{revision_points})")

        if has_contradiction:
            score += 30
            factors.append("contradição sinalizada em alguma versão (+30)")

        if not (req.get("source_quote") or "").strip():
            score += 15
            factors.append("sem source_quote — rastreabilidade fraca (+15)")

        if self._is_vague_description(req.get("description", "")):
            score += 15
            factors.append("descrição curta ou vaga (+15)")

        priority = (req.get("priority") or "").lower()
        status = (req.get("status") or "").lower()
        if priority == "high" and status in ("backlog", "active", "revised"):
            score += 10
            factors.append(f"prioridade alta, status ainda '{status}' (+10)")

        score = min(score, 100)
        if score >= 75:
            label = "🔴 Crítico"
        elif score >= 50:
            label = "🟠 Alto"
        elif score >= 25:
            label = "🟡 Médio"
        else:
            label = "🟢 Baixo"

        return {"score": score, "label": label, "factors": factors}

    def estimar_risco_requisito(self, req_number: int | None = None, top_n: int = 10) -> str:
        """Weighted heuristic risk score per requirement — no LLM. See
        _score_requirement_risk for the formula; always shows the factors
        that contributed to a score, never a bare number."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        try:
            query = (
                db.table("requirements")
                .select("id, req_number, title, description, priority, status, source_quote")
                .eq("project_id", self.project_id)
            )
            if req_number is not None:
                query = query.eq("req_number", req_number)
            reqs = query.execute().data or []
        except Exception as exc:
            return f"❌ Erro ao buscar requisitos: {exc}"

        if not reqs:
            if req_number is not None:
                return f"REQ-{req_number:03d} não encontrado no projeto."
            return "Nenhum requisito encontrado no projeto."

        try:
            req_ids = [r["id"] for r in reqs]
            versions = (
                db.table("requirement_versions")
                .select("requirement_id, contradiction_flag")
                .in_("requirement_id", req_ids)
                .execute().data or []
            )
        except Exception:
            versions = []

        from collections import Counter
        rev_counts = Counter(v["requirement_id"] for v in versions)
        contradicted_ids = {v["requirement_id"] for v in versions if v.get("contradiction_flag")}

        scored = []
        for r in reqs:
            n_rev = rev_counts.get(r["id"], 0) + 1  # +1 for the baseline (current) version
            has_contra = r["id"] in contradicted_ids or (r.get("status") or "").lower() == "contradicted"
            result = self._score_requirement_risk(r, n_rev, has_contra)
            scored.append((r, result))

        if req_number is not None:
            r, result = scored[0]
            lines = [
                f"## ⚠️ Risco — REQ-{r.get('req_number', 0):03d} — {r.get('title', '')}",
                f"\n**Score: {result['score']}/100 — {result['label']}**\n",
                "**Fatores considerados:**" if result["factors"] else "Nenhum fator de risco identificado.",
            ]
            lines.extend(f"- {f}" for f in result["factors"])
            return "\n".join(lines)

        scored.sort(key=lambda pair: pair[1]["score"], reverse=True)
        lines = [f"## ⚠️ Requisitos Mais Arriscados — Top {min(top_n, len(scored))}\n"]
        for r, result in scored[:top_n]:
            lines.append(
                f"- **REQ-{r.get('req_number', 0):03d}** — {r.get('title', '')}: "
                f"{result['score']}/100 {result['label']}"
            )
        return "\n".join(lines)

    def map_transcript_to_requirements(self, meeting_number: int) -> str:
        """Mapeia trechos da transcrição para a contagem de requisitos gerados por trecho."""
        import re

        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."
        mtg = self._find_meeting(meeting_number)
        if not mtg:
            return f"Reunião {meeting_number} não encontrada."
        transcript = (mtg.get("transcript_clean") or mtg.get("transcript_raw") or "").strip()
        if not transcript:
            return f"Reunião {meeting_number} não possui transcrição armazenada."

        _, rows, err = self._requirements_for_meeting(meeting_number, "req_number, title, source_quote")
        if err:
            return err

        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", transcript) if p.strip()]
        if len(paragraphs) < 2:
            # Transcript has no blank-line paragraph breaks — fall back to sentences.
            paragraphs = [p.strip() for p in re.split(r"(?<=[.!?])\s+", transcript) if p.strip()]
        if not paragraphs:
            return f"Não foi possível dividir a transcrição da Reunião {meeting_number} em trechos."

        counts = [0] * len(paragraphs)
        unmatched = 0
        for r in rows:
            quote = (r.get("source_quote") or "").strip()
            if not quote:
                unmatched += 1
                continue
            quote_lower = quote.lower()
            quote_words = set(re.findall(r"\w+", quote_lower))
            best_idx, best_score = None, 0.0
            for i, p in enumerate(paragraphs):
                p_lower = p.lower()
                if quote_lower in p_lower:
                    best_idx, best_score = i, 1.0
                    break
                p_words = set(re.findall(r"\w+", p_lower))
                if quote_words and p_words:
                    overlap = len(quote_words & p_words) / len(quote_words)
                    if overlap > best_score:
                        best_score, best_idx = overlap, i
            if best_idx is not None and best_score >= 0.5:
                counts[best_idx] += 1
            else:
                unmatched += 1

        ranked = sorted(range(len(paragraphs)), key=lambda i: counts[i], reverse=True)
        avg = sum(counts) / len(counts) if counts else 0.0

        lines = [
            f"# Mapa Transcrição → Requisitos — Reunião {meeting_number}",
            f"{len(paragraphs)} trecho(s) identificado(s), {len(rows)} requisito(s), "
            f"média {avg:.1f} requisito(s)/trecho.",
        ]
        if unmatched:
            lines.append(f"{unmatched} requisito(s) sem correspondência clara de trecho.")
        lines.append("")
        shown = 0
        for i in ranked:
            if counts[i] == 0 or shown >= 10:
                break
            flag = " ⚠️ possível oversplitting" if counts[i] > max(3, avg * 2) else ""
            excerpt = paragraphs[i][:150] + ("..." if len(paragraphs[i]) > 150 else "")
            lines.append(f'📄 "{excerpt}"\n   → {counts[i]} requisito(s){flag}')
            shown += 1
        return "\n".join(lines)

    def cluster_similar_requirements(
        self,
        meeting_number: int,
        threshold: float = 0.85,
        max_requirements: int = 200,
    ) -> str:
        """Agrupa requisitos de uma reunião por similaridade semântica (embeddings)."""
        from modules.embeddings import embed_batch, get_active_embedding_params

        mtg, rows, err = self._requirements_for_meeting(meeting_number, "req_number, title, description")
        if err:
            return err

        max_requirements = max(1, int(max_requirements or 200))
        if len(rows) > max_requirements:
            return (
                f"Reunião {meeting_number} tem {len(rows)} requisitos — acima do limite de "
                f"{max_requirements} por chamada (protege contra custo excessivo de embeddings). "
                f"Use sample_requirements para uma amostra, ou aumente max_requirements explicitamente."
            )

        try:
            provider, api_key = get_active_embedding_params()
        except RuntimeError as exc:
            return f"❌ {exc}"

        texts = [f"{r.get('title') or ''} {r.get('description') or ''}".strip() for r in rows]
        try:
            vectors = embed_batch(texts, api_key, provider)
        except Exception as exc:
            return f"❌ Erro ao gerar embeddings: {exc}"

        threshold = max(0.5, min(float(threshold or 0.85), 0.99))
        clusters: list[dict] = []
        for row, vec in zip(rows, vectors):
            best_idx, best_sim = None, -1.0
            for i, c in enumerate(clusters):
                sim = _cosine_similarity(vec, c["centroid"])
                if sim > best_sim:
                    best_sim, best_idx = sim, i
            if best_idx is not None and best_sim >= threshold:
                clusters[best_idx]["members"].append(row)
            else:
                clusters.append({"centroid": vec, "members": [row]})

        clusters.sort(key=lambda c: len(c["members"]), reverse=True)
        multi = [c for c in clusters if len(c["members"]) > 1]

        lines = [
            f"# Clusterização de Requisitos — Reunião {meeting_number}",
            f"{len(rows)} requisito(s) → {len(clusters)} cluster(s) (threshold={threshold:.2f}).",
            f"{len(multi)} cluster(s) com mais de 1 requisito (possíveis duplicatas/redundâncias).",
            "",
        ]
        shown = 0
        for c in clusters:
            if len(c["members"]) <= 1 or shown >= 15:
                continue
            members = c["members"]
            titles = "; ".join(f"REQ-{m['req_number']:03d} {m['title']}" for m in members[:5])
            extra = f" (+{len(members) - 5})" if len(members) > 5 else ""
            lines.append(f"🧬 Cluster de {len(members)}: {titles}{extra}")
            shown += 1
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
