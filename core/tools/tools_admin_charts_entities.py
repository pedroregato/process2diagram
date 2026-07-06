# core/tools/tools_admin_charts_entities.py
# Auto-extracted from core/assistant_tools.py (split PC115) — mixin for AssistantToolExecutor.
# Methods here assume `self` is an AssistantToolExecutor instance (project_id, llm_config,
# _meeting_cache, _pending_charts, _palette — set in AssistantToolExecutor.__init__).

from __future__ import annotations
import re
from core.chart_config import CHART_PALETTES, DEFAULT_PALETTE
from core.tools._shared import _compute_initials


ADMIN_CHARTS_ENTITIES_SCHEMAS: list[dict] = [
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
                            "z_matrix": {
                                "type": "array",
                                "items": {"type": "array", "items": {"type": "number"}},
                                "description": (
                                    "Obrigatório quando chart_type='heatmap' — matriz 2D de valores "
                                    "(uma lista por linha). 'labels' vira os rótulos das colunas (eixo X) "
                                    "e 'y_axis_labels' os rótulos das linhas (eixo Y)."
                                ),
                            },
                            "y_axis_labels": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Rótulos do eixo Y — usado apenas com chart_type='heatmap'.",
                            },
                        },
                        "required": ["chart_type", "title", "labels", "values"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_requirements_flow_chart",
                    "description": (
                        "Visualiza a hierarquia Tipo → Prioridade → Status dos requisitos como Sankey "
                        "(fluxo), Treemap (blocos) ou Sunburst (anéis concêntricos) — mostra em um único "
                        "gráfico como os requisitos se distribuem e onde estão os gargalos, sem precisar "
                        "de 3 gráficos de barra separados. Use quando o usuário pedir para 'visualizar o "
                        "fluxo dos requisitos', 'ver a distribuição hierárquica' ou pedir Sankey/Treemap/Sunburst."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "view": {
                                "type": "string",
                                "enum": ["sankey", "treemap", "sunburst"],
                                "description": "Tipo de visualização. Padrão: sankey.",
                            },
                            "meeting_number": {
                                "type": "integer",
                                "description": "Restringe aos requisitos de uma única reunião (opcional — padrão: todo o projeto)",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_requirements_heatmap",
                    "description": (
                        "Gera um mapa de calor cruzado Reunião × Tipo/Prioridade/Status de requisitos — "
                        "a matriz é montada automaticamente a partir do banco, sem necessidade de informar "
                        "cada valor manualmente (diferente de generate_custom_chart). Use para responder "
                        "'qual reunião teve mais requisitos de tipo X' ou revelar concentração por reunião."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "dimension": {
                                "type": "string",
                                "enum": ["req_type", "priority", "status"],
                                "description": "Dimensão cruzada com reunião no eixo Y. Padrão: req_type.",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_requirements_bubble_chart",
                    "description": (
                        "Gráfico de bolhas: eixo X = reunião, eixo Y = prioridade média (1=baixa, 2=média, "
                        "3=alta), tamanho da bolha = quantidade de requisitos. Mostra 3 dimensões num único "
                        "gráfico compacto — ideal para status reports com pouco espaço."
                    ),
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_requirements_waterfall",
                    "description": (
                        "Gráfico de cascata (waterfall) mostrando a evolução cumulativa de requisitos "
                        "ativos ao longo das reuniões do projeto — quantos foram adicionados em cada "
                        "reunião e quantos saíram de 'active' (contradicted/deprecated), até o saldo final. "
                        "Use para responder 'como o total de requisitos evoluiu ao longo do projeto'."
                    ),
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_meeting_radar_chart",
                    "description": (
                        "Gráfico radar (teia) comparando reuniões em 4 dimensões (contagens brutas): "
                        "Decisões, Ações, Requisitos e Participantes — substitui 4 gráficos de barra "
                        "separados. Use para comparar a 'densidade' de várias reuniões de uma só vez."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_numbers": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": "Números das reuniões a comparar (2 a 6). Se omitido, usa todas as reuniões do projeto (até 6).",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_gantt_chart",
                    "description": (
                        "Gera um cronograma (Gantt) a partir de fases/marcos fornecidos explicitamente — "
                        "o sistema não tem um modelo nativo de planejamento com datas, então o usuário (ou "
                        "o LLM em nome dele) deve informar cada fase com início e fim. Use quando o usuário "
                        "pedir um cronograma, roadmap ou timeline de fases do projeto."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "Título do cronograma (ex: 'Cronograma do Projeto AURORA')",
                            },
                            "phases": {
                                "type": "array",
                                "description": "Lista de fases/marcos do cronograma",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string", "description": "Nome da fase/marco"},
                                        "start": {"type": "string", "description": "Data de início (YYYY-MM-DD)"},
                                        "end": {"type": "string", "description": "Data de fim (YYYY-MM-DD)"},
                                        "status": {
                                            "type": "string",
                                            "enum": ["planejado", "em_andamento", "concluído", "atrasado"],
                                            "description": "Status da fase (opcional, padrão 'planejado')",
                                        },
                                    },
                                    "required": ["name", "start", "end"],
                                },
                            },
                        },
                        "required": ["title", "phases"],
                    },
                },
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
]

class _AdminChartsEntitiesToolsMixin:
    """Mixin: tools_admin_charts_entities tools."""

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
        """Bar chart of requirements grouped by type and/or priority.

        PC142: previously filtered with .eq("meeting_number", meeting_number)
        directly on the requirements table — that column doesn't exist there
        (only first_meeting_id, a meetings.id UUID), so every call with
        meeting_number set silently failed with "Erro ao buscar requisitos".
        """
        import plotly.graph_objects as go
        from collections import Counter

        rows, err = self._requirements_with_meeting_numbers(meeting_number)
        if err:
            return err

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

        # PC142: requirements has no meeting_number column (only first_meeting_id,
        # a meetings.id UUID) — this previously always returned zero requirements
        # per meeting. Resolve meeting_number via the shared helper instead.
        req_rows, _req_err = self._requirements_with_meeting_numbers()
        if _req_err:
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
            # PC142: '|' has lower precedence than the rest of the pattern, so the
            # un-grouped "Ações|Action Items.*?\n(.*?)..." matched bare "Ações" with
            # no group(1) whenever minutes used the Portuguese header, raising
            # AttributeError on .splitlines(). Wrap the alternation explicitly.
            act_section = re.search(r"(?:Ações|Action Items).*?\n(.*?)(?:\n##|\Z)", minutes_md, re.DOTALL | re.IGNORECASE)
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
        z_matrix: list[list[float]] | None = None,
        y_axis_labels: list[str] | None = None,
    ) -> str:
        """Render a custom chart from LLM-provided data.

        PC142: chart_type='heatmap' was listed in the schema/description but
        had no implementation — it silently fell through to the 'bar'
        default (labels/values are 1-D and can never represent a matrix
        anyway). z_matrix/y_axis_labels make the promised capability real.
        """
        import plotly.graph_objects as go

        colors = [self._palette[i % len(self._palette)] for i in range(len(labels))]

        ct = chart_type.lower()
        try:
            if ct == "heatmap":
                if not z_matrix:
                    return (
                        "Erro: chart_type='heatmap' requer o parâmetro z_matrix (matriz 2D de "
                        "valores) — 'labels'/'values' sozinhos não representam uma matriz. Para a "
                        "matriz Reunião × Tipo/Prioridade/Status de requisitos já pronta, use "
                        "generate_requirements_heatmap em vez desta ferramenta."
                    )
                fig = go.Figure(go.Heatmap(
                    z=z_matrix, x=labels, y=y_axis_labels or None,
                    colorscale="YlOrRd",
                    text=z_matrix, texttemplate="%{text}",
                ))
                self._dark_layout(fig, title)
                if x_label:
                    fig.update_xaxes(title_text=x_label)
                if y_label:
                    fig.update_yaxes(title_text=y_label)
                self._pending_charts.append(fig.to_dict())
                n_rows = len(z_matrix)
                n_cols = len(z_matrix[0]) if z_matrix else 0
                return f"📊 Heatmap '{title}' gerado ({n_rows}×{n_cols})."
            elif ct == "pie":
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

    # ── New chart tools (PC142) ────────────────────────────────────────────────
    # Proposed by the assistant after investigating the requirements
    # duplication incident (PC140/141) with a limited visual repertoire.

    def _requirements_with_meeting_numbers(self, meeting_number: int | None = None) -> tuple[list[dict], str]:
        """Fetch project requirements (req_type/priority/status) enriched with
        meeting_number resolved from first_meeting_id.

        requirements has NO meeting_number column (only first_meeting_id, a
        meetings.id UUID) — a prior chart (generate_requirements_chart) filtered
        directly on '.eq("meeting_number", ...)', which always raised (caught
        silently) since that column doesn't exist. Fixed here and reused by
        every new chart that needs a per-meeting breakdown.
        """
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if db is None:
            return [], "Supabase não configurado."

        meeting_id_filter = None
        if meeting_number is not None:
            mtg = self._find_meeting(meeting_number)
            if not mtg:
                return [], f"Reunião {meeting_number} não encontrada."
            meeting_id_filter = mtg["id"]

        try:
            q = (
                db.table("requirements")
                .select("req_type, priority, status, first_meeting_id")
                .eq("project_id", self.project_id)
            )
            if meeting_id_filter:
                q = q.eq("first_meeting_id", meeting_id_filter)
            rows = q.execute().data or []
        except Exception as exc:
            return [], f"Erro ao buscar requisitos: {exc}"

        if not rows:
            return [], "Nenhum requisito encontrado."

        mlookup = {m["id"]: m.get("meeting_number") for m in self._get_meetings()}
        for r in rows:
            r["meeting_number"] = mlookup.get(r.get("first_meeting_id"))
        return rows, ""

    def generate_requirements_flow_chart(
        self,
        view: str = "sankey",
        meeting_number: int | None = None,
    ) -> str:
        """Sankey / Treemap / Sunburst of the Type -> Priority -> Status hierarchy."""
        import plotly.graph_objects as go
        from collections import Counter

        rows, err = self._requirements_with_meeting_numbers(meeting_number)
        if err:
            return err

        def _label(v, fallback):
            return (v or fallback).strip() or fallback

        types = [_label(r.get("req_type"), "Outro") for r in rows]
        prios = [_label(r.get("priority"), "Não definida") for r in rows]
        stats = [_label(r.get("status"), "active") for r in rows]

        suffix = f" — Reunião {meeting_number}" if meeting_number else ""
        view = (view or "sankey").lower()

        if view == "sankey":
            type_prio = Counter(zip(types, prios))
            prio_status = Counter(zip(prios, stats))
            all_types = sorted(set(types))
            all_prios = sorted(set(prios))
            all_status = sorted(set(stats))
            nodes = all_types + all_prios + all_status
            idx = {n: i for i, n in enumerate(nodes)}
            node_colors = [self._palette[i % len(self._palette)] for i in range(len(nodes))]

            src, tgt, val = [], [], []
            for (t, p), n in type_prio.items():
                src.append(idx[t]); tgt.append(idx[p]); val.append(n)
            for (p, s), n in prio_status.items():
                src.append(idx[p]); tgt.append(idx[s]); val.append(n)

            fig = go.Figure(go.Sankey(
                node=dict(label=nodes, color=node_colors, pad=15, thickness=18,
                          line=dict(color="#0A1A32", width=0.5)),
                link=dict(source=src, target=tgt, value=val),
            ))
            self._dark_layout(fig, f"Fluxo de Requisitos — Tipo → Prioridade → Status{suffix}")
        elif view in ("treemap", "sunburst"):
            labels_all, parents_all, values_all = ["Requisitos"], [""], [len(rows)]
            for t in sorted(set(types)):
                labels_all.append(t); parents_all.append("Requisitos")
                values_all.append(types.count(t))
            for (t, p), n in Counter(zip(types, prios)).items():
                key = f"{t}·{p}"
                labels_all.append(key); parents_all.append(t); values_all.append(n)
            for (t, p, s), n in Counter(zip(types, prios, stats)).items():
                labels_all.append(f"{t}·{p}·{s}")
                parents_all.append(f"{t}·{p}")
                values_all.append(n)

            trace_cls = go.Treemap if view == "treemap" else go.Sunburst
            fig = go.Figure(trace_cls(
                labels=labels_all, parents=parents_all, values=values_all,
                branchvalues="total",
                marker=dict(colors=[self._palette[i % len(self._palette)] for i in range(len(labels_all))]),
            ))
            title_kind = "Treemap" if view == "treemap" else "Sunburst"
            self._dark_layout(fig, f"{title_kind} de Requisitos — Tipo → Prioridade → Status{suffix}")
        else:
            return f"view inválida: '{view}' — use 'sankey', 'treemap' ou 'sunburst'."

        self._pending_charts.append(fig.to_dict())
        return f"📊 {view.capitalize()} gerado: {len(rows)} requisito(s){suffix}."

    def generate_requirements_heatmap(self, dimension: str = "req_type") -> str:
        """Cross heatmap: Meeting x (req_type | priority | status)."""
        import plotly.graph_objects as go
        from collections import Counter

        dimension = dimension if dimension in ("req_type", "priority", "status") else "req_type"
        rows, err = self._requirements_with_meeting_numbers()
        if err:
            return err

        meetings = sorted({r["meeting_number"] for r in rows if r.get("meeting_number") is not None})
        if not meetings:
            return "Nenhum requisito vinculado a uma reunião identificável."
        cats = sorted({(r.get(dimension) or "—") for r in rows})

        counts = Counter((r["meeting_number"], r.get(dimension) or "—") for r in rows if r.get("meeting_number") is not None)
        z = [[counts.get((m, c), 0) for c in cats] for m in meetings]

        fig = go.Figure(go.Heatmap(
            z=z, x=cats, y=[f"Reunião {m}" for m in meetings],
            colorscale="YlOrRd", text=z, texttemplate="%{text}",
        ))
        dim_label = {"req_type": "Tipo", "priority": "Prioridade", "status": "Status"}[dimension]
        self._dark_layout(fig, f"Requisitos por Reunião × {dim_label}")
        self._pending_charts.append(fig.to_dict())
        return f"📊 Heatmap gerado: {len(meetings)} reunião(ões) × {len(cats)} categoria(s) de {dim_label.lower()}."

    def generate_requirements_bubble_chart(self) -> str:
        """Bubble chart: X=meeting, Y=avg priority (1-3), size=requirement count."""
        import plotly.graph_objects as go
        from collections import defaultdict

        rows, err = self._requirements_with_meeting_numbers()
        if err:
            return err

        _PRIO_SCORE = {"baixa": 1, "média": 2, "media": 2, "alta": 3, "low": 1, "medium": 2, "high": 3}
        by_meeting: dict[int, list] = defaultdict(list)
        for r in rows:
            n = r.get("meeting_number")
            if n is not None:
                by_meeting[n].append(_PRIO_SCORE.get((r.get("priority") or "").strip().lower(), 2))

        if not by_meeting:
            return "Nenhum requisito vinculado a uma reunião identificável."

        meetings = sorted(by_meeting.keys())
        avg_prio = [sum(by_meeting[m]) / len(by_meeting[m]) for m in meetings]
        counts = [len(by_meeting[m]) for m in meetings]
        max_count = max(counts) or 1
        sizes = [12 + 40 * (c / max_count) for c in counts]

        fig = go.Figure(go.Scatter(
            x=[f"Reunião {m}" for m in meetings], y=avg_prio, mode="markers+text",
            text=[str(c) for c in counts], textposition="middle center",
            marker=dict(size=sizes, color=self._palette[0], opacity=0.75,
                        line=dict(color="#0A1A32", width=1)),
        ))
        fig.update_yaxes(title_text="Prioridade média (1=baixa, 3=alta)", range=[0.5, 3.5])
        self._dark_layout(fig, "Requisitos por Reunião — Prioridade Média × Volume")
        self._pending_charts.append(fig.to_dict())
        return f"📊 Bubble chart gerado: {len(meetings)} reunião(ões)."

    def generate_requirements_waterfall(self) -> str:
        """Cumulative net active-requirement evolution across meetings."""
        import plotly.graph_objects as go
        from collections import defaultdict

        rows, err = self._requirements_with_meeting_numbers()
        if err:
            return err

        _INACTIVE = {"contradicted", "deprecated"}
        added: dict[int, int] = defaultdict(int)
        removed: dict[int, int] = defaultdict(int)
        for r in rows:
            n = r.get("meeting_number")
            if n is None:
                continue
            added[n] += 1
            if (r.get("status") or "").strip().lower() in _INACTIVE:
                removed[n] += 1

        meetings = sorted(added.keys())
        if not meetings:
            return "Nenhum requisito vinculado a uma reunião identificável."

        x, y, measure, text = [], [], [], []
        for m in meetings:
            net = added[m] - removed[m]
            x.append(f"Reunião {m}")
            y.append(net)
            measure.append("relative")
            text.append(f"+{added[m]}" + (f" -{removed[m]}" if removed[m] else ""))
        x.append("Total")
        y.append(0)
        measure.append("total")
        text.append("")

        fig = go.Figure(go.Waterfall(
            x=x, y=y, measure=measure, text=text, textposition="outside",
            increasing=dict(marker=dict(color="#10b981")),
            decreasing=dict(marker=dict(color="#ef4444")),
            totals=dict(marker=dict(color=self._palette[0])),
        ))
        self._dark_layout(fig, "Evolução Cumulativa de Requisitos Ativos")
        self._pending_charts.append(fig.to_dict())
        return f"📊 Waterfall gerado: {len(meetings)} reunião(ões)."

    def generate_meeting_radar_chart(self, meeting_numbers: list[int] | None = None) -> str:
        """Radar comparing meetings across Decisions / Actions / Requirements / Participants."""
        import re
        import plotly.graph_objects as go

        meetings = self._get_meetings()
        if not meetings:
            return "Nenhuma reunião encontrada."
        if meeting_numbers:
            wanted = set(meeting_numbers)
            meetings = [m for m in meetings if m.get("meeting_number") in wanted]
        else:
            meetings = meetings[:6]
        if not meetings:
            return "Nenhuma reunião encontrada com os números informados."
        if len(meetings) < 2:
            return "É necessário pelo menos 2 reuniões para comparar no radar."
        if len(meetings) > 6:
            meetings = meetings[:6]

        def _count_section(md: str, header_pattern: str) -> int:
            # header_pattern may itself contain capturing groups (e.g. "Decis(ões|oes)"),
            # which would shift the content group's index — always take the LAST
            # group (the trailing content capture) rather than assuming group(1).
            if not md:
                return 0
            section = re.search(header_pattern + r".*?\n(.*?)(?:\n##|\Z)", md, re.DOTALL | re.IGNORECASE)
            if not section:
                return 0
            content = section.group(section.re.groups)
            return len([ln for ln in content.splitlines() if ln.strip().startswith("-")])

        def _count_participants(md: str) -> int:
            return _count_section(md, r"Participantes")

        reqs_rows, _ = self._requirements_with_meeting_numbers()
        from collections import Counter
        req_counts = Counter(r["meeting_number"] for r in reqs_rows if r.get("meeting_number") is not None)

        axes = ["Decisões", "Ações", "Requisitos", "Participantes"]
        traces = []
        for i, m in enumerate(meetings):
            md = m.get("minutes_md") or ""
            decisions = _count_section(md, r"Decis(ões|oes)")
            actions = _count_section(md, r"(Ações|Acoes|Action Items)")
            n_reqs = req_counts.get(m.get("meeting_number"), 0)
            participants = _count_participants(md)
            values = [decisions, actions, n_reqs, participants]
            traces.append(go.Scatterpolar(
                r=values + [values[0]], theta=axes + [axes[0]],
                fill="toself", name=f"Reunião {m.get('meeting_number')}",
                line=dict(color=self._palette[i % len(self._palette)]),
            ))

        fig = go.Figure(data=traces)
        fig.update_layout(polar=dict(radialaxis=dict(visible=True, gridcolor="#1A3050")))
        self._dark_layout(fig, "Comparativo de Reuniões — Radar")
        self._pending_charts.append(fig.to_dict())
        return f"📊 Radar gerado comparando {len(meetings)} reunião(ões)."

    def generate_gantt_chart(self, title: str, phases: list[dict]) -> str:
        """Gantt chart from explicitly supplied phases (no native scheduling data model exists)."""
        import plotly.graph_objects as go
        from datetime import datetime as _dt

        if not phases:
            return "Nenhuma fase informada — forneça ao menos uma fase com name/start/end."

        _STATUS_COLORS = {
            "planejado": "#64748b", "em_andamento": "#3b82f6",
            "concluído": "#10b981", "concluido": "#10b981", "atrasado": "#ef4444",
        }

        parsed = []
        for p in phases:
            try:
                start = _dt.fromisoformat(str(p["start"])[:10])
                end = _dt.fromisoformat(str(p["end"])[:10])
            except (KeyError, ValueError) as exc:
                return f"Data inválida na fase '{p.get('name', '?')}': {exc}"
            parsed.append({
                "name": p.get("name", "Fase"),
                "start": start, "end": end,
                "status": (p.get("status") or "planejado").strip().lower(),
            })
        parsed.sort(key=lambda p: p["start"])

        fig = go.Figure()
        for p in parsed:
            duration_days = max((p["end"] - p["start"]).days, 1)
            fig.add_trace(go.Bar(
                x=[duration_days], y=[p["name"]], base=[p["start"]],
                orientation="h",
                marker_color=_STATUS_COLORS.get(p["status"], self._palette[0]),
                name=p["status"], showlegend=False,
                text=f"{p['start'].date()} → {p['end'].date()}",
                textposition="inside",
            ))
        fig.update_layout(barmode="overlay", xaxis=dict(type="date"))
        self._dark_layout(fig, title)
        self._pending_charts.append(fig.to_dict())
        return f"📊 Gantt '{title}' gerado com {len(parsed)} fase(s)."

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
