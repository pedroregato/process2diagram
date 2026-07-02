# core/tools/tools_documents_ibis_diagrams.py
# Auto-extracted from core/assistant_tools.py (split PC115) — mixin for AssistantToolExecutor.
# Methods here assume `self` is an AssistantToolExecutor instance (project_id, llm_config,
# _meeting_cache, _pending_charts, _palette — set in AssistantToolExecutor.__init__).

from __future__ import annotations
import re
from core.chart_config import CHART_PALETTES, DEFAULT_PALETTE
from core.tools._shared import _compute_initials


DOCUMENTS_IBIS_DIAGRAMS_SCHEMAS: list[dict] = [
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
                    "name": "render_requirements_table",
                    "description": (
                        "Renderiza uma tabela interativa de requisitos diretamente no chat (HTML com cards expansíveis). "
                        "USE quando o usuário pedir para LISTAR, EXIBIR ou VER os requisitos de uma reunião ou do projeto. "
                        "Cada card mostra: REQ-ID, tipo, prioridade, status e título — clicável para ver descrição completa, "
                        "fala de origem e autor. Evita paginação e truncamento. "
                        "PREFIRA esta ferramenta a get_requirements quando o usuário quiser ver os requisitos na íntegra."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_number": {
                                "type": "integer",
                                "description": "Número da reunião para filtrar requisitos. Omita para mostrar todos do projeto.",
                            },
                            "req_type": {
                                "type": "string",
                                "description": "Filtro por tipo: 'funcional', 'não-funcional', 'negócio', 'regra de negócio', etc. Opcional.",
                            },
                            "status": {
                                "type": "string",
                                "description": "Filtro por status: 'em aberto', 'aprovado', 'implementado', 'cancelado'. Opcional.",
                            },
                            "title": {
                                "type": "string",
                                "description": "Título para exibir acima da tabela. Opcional.",
                            },
                        },
                        "required": [],
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
]

class _DocumentsIbisDiagramsToolsMixin:
    """Mixin: tools_documents_ibis_diagrams tools."""

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

    def render_requirements_table(
        self,
        meeting_number: int | None = None,
        req_type: str | None = None,
        status: str | None = None,
        title: str = "",
    ) -> str:
        """Fetch all requirements and queue an interactive HTML card table for inline rendering."""
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        # Resolve meeting_number → UUID
        meeting_id_filter: str | None = None
        meeting_label = ""
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
                if not m_rows.data:
                    return f"Reunião {meeting_number} não encontrada no projeto."
                meeting_id_filter = m_rows.data[0]["id"]
                meeting_label = m_rows.data[0].get("title") or f"Reunião {meeting_number}"
            except Exception as exc:
                return f"Erro ao buscar reunião {meeting_number}: {exc}"

        # Fetch all requirements (no pagination)
        try:
            q = (
                db.table("requirements")
                .select(
                    "req_number, title, description, req_type, status, priority, "
                    "source_quote, cited_by, first_meeting_id, "
                    "resolution_notes, implemented_at"
                )
                .eq("project_id", self.project_id)
                .order("req_number")
                .limit(500)
            )
            if req_type:
                q = q.eq("req_type", req_type)
            if status:
                q = q.eq("status", status)
            if meeting_id_filter:
                q = q.eq("first_meeting_id", meeting_id_filter)
            rows = q.execute().data or []
        except Exception as exc:
            return f"Erro ao acessar requisitos: {exc}"

        if not rows:
            hint = f" da Reunião {meeting_number}" if meeting_number else ""
            return f"Nenhum requisito encontrado{hint} com os filtros fornecidos."

        # Build self-contained HTML
        def _esc(s: str) -> str:
            return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

        def _prio_cls(p: str) -> str:
            p = (p or "").lower()
            if p in ("alta", "crítica", "critica", "high"):
                return "prio-alta"
            if p in ("baixa", "low"):
                return "prio-baixa"
            return "prio-media"

        # meeting lookup — show per-card only when not filtered to a single meeting
        mlookup = self._meeting_lookup() if not meeting_id_filter else {}

        cards = []
        for r in rows:
            n      = r.get("req_number")
            req_id = f"REQ-{n:03d}" if isinstance(n, int) else "REQ-???"
            rtype  = _esc(r.get("req_type") or "—")
            rprio  = _esc(r.get("priority") or "—")
            rst    = _esc(r.get("status") or "—")
            rtitle = _esc(r.get("title") or "(sem título)")
            rdesc  = _esc(r.get("description") or "—")
            rquote = _esc(r.get("source_quote") or "")
            rauthor = _esc(r.get("cited_by") or "")
            rres   = _esc(r.get("resolution_notes") or "")
            rimpl  = (r.get("implemented_at") or "")[:10]
            prio_cls = _prio_cls(r.get("priority") or "")
            minfo = mlookup.get(r.get("first_meeting_id") or "")
            mtag  = _esc(self._fmt_meeting_tag(minfo)) if minfo else ""
            meeting_badge = f'<span class="badge badge-meeting">{mtag}</span>' if mtag else ""
            quote_html = (
                f'<div class="field-label">Fala de origem</div>'
                f'<div class="source-quote">{rquote}</div>'
                if rquote else ""
            )
            author_html = (
                f'<div class="field-label">Autor</div>'
                f'<div class="field-value">{rauthor}</div>'
                if rauthor else ""
            )
            impl_label = f"Solução implementada" + (f" ({rimpl})" if rimpl else "")
            resolution_html = (
                f'<div class="field-label">{impl_label}</div>'
                f'<div class="resolution-box">{rres}</div>'
                if rres else ""
            )
            cards.append(
                f'<div class="req-card">'
                f'<div class="req-header" onclick="toggle(this)">'
                f'<span class="req-id">{req_id}</span>'
                f'<span class="badge badge-type">{rtype}</span>'
                f'<span class="badge badge-{prio_cls}">{rprio}</span>'
                f'<span class="badge badge-status">{rst}</span>'
                f'{meeting_badge}'
                f'<span class="req-title">{rtitle}</span>'
                f'<span class="toggle-icon">▶</span>'
                f'</div>'
                f'<div class="req-body">'
                f'<div class="field-label">Descrição</div>'
                f'<div class="field-value">{rdesc}</div>'
                f'{resolution_html}'
                f'{quote_html}'
                f'{author_html}'
                f'</div>'
                f'</div>'
            )

        ctx = f" — {meeting_label}" if meeting_label else ""
        if not title:
            title = f"📋 Requisitos{ctx} ({len(rows)} itens)"

        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f1117;color:#e0e0e0;margin:0;padding:8px;}}
.summary{{color:#9ca3af;font-size:12px;margin-bottom:8px;}}
.req-card{{border:1px solid #2a2d38;border-radius:6px;margin:5px 0;overflow:hidden;}}
.req-header{{display:flex;align-items:center;gap:6px;padding:9px 12px;cursor:pointer;user-select:none;background:#1a1d24;flex-wrap:wrap;}}
.req-header:hover{{background:#22262f;}}
.req-id{{font-weight:700;font-size:11px;padding:2px 6px;border-radius:4px;background:#2563eb;color:#fff;flex-shrink:0;}}
.req-title{{flex:1;font-size:13px;font-weight:500;min-width:120px;}}
.badge{{font-size:11px;padding:2px 6px;border-radius:3px;flex-shrink:0;}}
.badge-type{{background:#374151;color:#d1d5db;}}
.badge-prio-alta{{background:#7f1d1d;color:#fca5a5;}}
.badge-prio-media{{background:#78350f;color:#fcd34d;}}
.badge-prio-baixa{{background:#1e3a5f;color:#93c5fd;}}
.badge-status{{background:#064e3b;color:#6ee7b7;}}
.badge-meeting{{background:#1e1b4b;color:#a5b4fc;}}
.resolution-box{{background:#052e16;border-left:3px solid #16a34a;padding:6px 10px;border-radius:3px;font-size:12px;line-height:1.5;color:#bbf7d0;}}
.req-body{{padding:12px 14px;display:none;background:#131620;border-top:1px solid #2a2d38;}}
.req-body.open{{display:block;}}
.field-label{{font-size:11px;color:#9ca3af;margin-top:8px;margin-bottom:3px;text-transform:uppercase;letter-spacing:.04em;}}
.field-value{{font-size:13px;line-height:1.6;}}
.source-quote{{font-style:italic;color:#cbd5e1;background:#1e2030;border-left:3px solid #4b5563;padding:6px 10px;border-radius:3px;font-size:12px;line-height:1.5;}}
.toggle-icon{{font-size:10px;color:#6b7280;margin-left:auto;flex-shrink:0;}}
</style></head><body>
<p class="summary">{_esc(title)}</p>
{''.join(cards)}
<script>
function toggle(el){{
  var body=el.nextElementSibling;
  var icon=el.querySelector('.toggle-icon');
  if(body.classList.contains('open')){{body.classList.remove('open');icon.textContent='▶';}}
  else{{body.classList.add('open');icon.textContent='▼';}}
}}
</script>
</body></html>"""

        import streamlit as st
        st.session_state.setdefault("_pending_widgets", []).append({
            "type":   "requirements_html",
            "html":   html,
            "title":  title,
            "count":  len(rows),
        })
        return f"📋 Tabela com {len(rows)} requisito(s){ctx} renderizada no chat. Clique em cada card para ver a descrição completa."

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
