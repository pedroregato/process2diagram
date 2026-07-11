# core/tools/tools_knowledge_requirements2.py
# Auto-extracted from core/assistant_tools.py (split PC115) — mixin for AssistantToolExecutor.
# Methods here assume `self` is an AssistantToolExecutor instance (project_id, llm_config,
# _meeting_cache, _pending_charts, _palette — set in AssistantToolExecutor.__init__).

from __future__ import annotations
import re
from core.chart_config import CHART_PALETTES, DEFAULT_PALETTE
from core.tools._shared import _compute_initials


KNOWLEDGE_REQUIREMENTS2_SCHEMAS: list[dict] = [
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
            {
                "type": "function",
                "function": {
                    "name": "merge_requirements",
                    "description": (
                        "Mescla dois ou mais requisitos duplicados em um único requisito, "
                        "transfere o histórico de versões e marca os absorvidos como deprecated. "
                        "USE quando o usuário identificar duplicatas e quiser consolidá-las. "
                        "Exemplos: 'mescle REQ-010 e REQ-025 mantendo o REQ-010', "
                        "'una os requisitos 10, 25 e 37 no REQ-010'. "
                        "Ferramenta ADMIN — exige perfil administrador."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "req_numbers": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": "Lista de números de TODOS os requisitos a mesclar (incluindo o que será mantido).",
                            },
                            "keep_number": {
                                "type": "integer",
                                "description": "Número do requisito que será MANTIDO (os demais serão absorvidos por ele).",
                            },
                            "merge_strategy": {
                                "type": "string",
                                "enum": ["combine", "longest", "keep_main"],
                                "description": (
                                    "Como combinar as descrições: "
                                    "'combine' (padrão) = concatena todas; "
                                    "'longest' = mantém a descrição mais longa; "
                                    "'keep_main' = mantém apenas a descrição do requisito principal."
                                ),
                            },
                            "merge_note": {
                                "type": "string",
                                "description": "Justificativa para a mesclagem (registrada no histórico). Recomendado.",
                            },
                        },
                        "required": ["req_numbers", "keep_number"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "diff_requirement",
                    "description": (
                        "Renderiza um diff visual (colorido) entre duas versões de um requisito no chat. "
                        "USE quando o usuário quiser ver 'o que mudou', 'evolução', 'diferença entre versões'. "
                        "Mostra texto removido em vermelho e texto adicionado em verde."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "req_number": {
                                "type": "integer",
                                "description": "Número do requisito (ex: 42 para REQ-042).",
                            },
                            "from_version": {
                                "type": "integer",
                                "description": "Versão de origem. Omita para usar a primeira versão disponível.",
                            },
                            "to_version": {
                                "type": "integer",
                                "description": "Versão de destino. Omita para usar a versão mais recente.",
                            },
                        },
                        "required": ["req_number"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_universal",
                    "description": (
                        "Busca uma query em TODOS os tipos de artefatos de uma vez: "
                        "transcrições, requisitos, termos SBVR, regras SBVR, debates IBIS e documentos. "
                        "USE quando o usuário pedir 'busque X em tudo', 'onde aparece X no projeto', "
                        "'mostre tudo sobre X'. Retorna resultados agrupados por tipo com scores de relevância. "
                        "Substitui chamar search_transcript + get_requirements + get_sbvr_terms + etc. separadamente."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Tema, termo ou expressão a buscar em todos os artefatos.",
                            },
                            "scopes": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "Tipos a buscar. Padrão: todos. "
                                    "Opções: 'transcripts', 'requirements', 'sbvr', 'ibis', 'documents'."
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
                    "name": "batch_text_correction",
                    "description": (
                        "Aplica múltiplas correções de texto (find→replace) em uma única chamada. "
                        "USE quando o usuário pedir para corrigir várias siglas, nomes ou termos de uma vez. "
                        "Exemplo: 'troque ODCI por DCI, FDTI por DTI e OSEUITE por SESUITE em todas as transcrições'. "
                        "Muito mais eficiente que aplicar apply_text_correction uma a uma. "
                        "Ferramenta ADMIN — exige perfil administrador."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "corrections": {
                                "type": "array",
                                "description": "Lista de correções a aplicar em sequência.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "find":    {"type": "string", "description": "Texto a localizar."},
                                        "replace": {"type": "string", "description": "Texto substituto."},
                                        "scope":   {
                                            "type": "string",
                                            "enum": ["transcripts", "minutes", "requirements", "sbvr", "all"],
                                            "description": "Escopo da substituição ('sbvr' = termos e regras do vocabulário SBVR).",
                                        },
                                    },
                                    "required": ["find", "replace", "scope"],
                                },
                            },
                            "meeting_number": {
                                "type": "integer",
                                "description": "Restringir a uma reunião específica (opcional).",
                            },
                        },
                        "required": ["corrections"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "detect_requirement_contradictions",
                    "description": (
                        "Analisa os requisitos do projeto com IA e identifica pares em possível contradição, "
                        "explicando a motivação para cada suspeita. "
                        "USE quando o usuário pedir: 'há requisitos contraditórios?', 'identifique conflitos', "
                        "'mostre inconsistências nos requisitos', 'quais requisitos se contradizem?'. "
                        "Renderiza cards HTML expansíveis com: par REQ-A ↔ REQ-B, motivação do conflito, "
                        "severidade e sugestão de resolução."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_number": {
                                "type": "integer",
                                "description": "Analisar apenas requisitos de uma reunião específica. Omita para analisar todo o projeto.",
                            },
                            "req_type": {
                                "type": "string",
                                "description": "Filtrar por tipo: 'funcional', 'não-funcional', 'regra de negócio', etc. Opcional.",
                            },
                            "max_reqs": {
                                "type": "integer",
                                "description": "Máximo de requisitos a analisar (padrão: 80, máx: 120). Reduza se houver timeout.",
                            },
                        },
                        "required": [],
                    },
                },
            },
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
                    "name": "sugerir_encaminhamentos_pendentes",
                    "description": (
                        "Analisa Decisões x Encaminhamentos de uma ata (ou das 5 reuniões mais "
                        "recentes) e aponta: (1) decisões que parecem não ter um encaminhamento/"
                        "ação correspondente registrada, (2) encaminhamentos com prazo já vencido. "
                        "Use quando o usuário pedir 'essa reunião teve decisão sem encaminhamento?', "
                        "'tem algo vencido nos encaminhamentos?' ou 'verifique os encaminhamentos "
                        "pendentes'."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_number": {
                                "type": "integer",
                                "description": (
                                    "Reunião específica a analisar. Omitido: analisa as 5 reuniões "
                                    "mais recentes do projeto."
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
                            "include_revision_requests": {
                                "type": "boolean",
                                "description": "Incluir requisitos com revisão solicitada pendente (via solicitar_revisao_requisito). Padrão: true.",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "verificar_rastreabilidade_obrigatoria",
                    "description": (
                        "Varre TODO o projeto (não uma reunião ou requisito específico) e aponta "
                        "gaps de completude/rastreabilidade: requisitos sem source_quote (sem "
                        "trecho de origem na transcrição), questões IBIS sem alternativa "
                        "registrada nem resolução, e processos BPMN sem descrição textual. "
                        "Sem LLM — varredura direta no banco. Diferente de diagnostico_projeto "
                        "(saúde geral do pipeline) — aqui o foco é completude de conteúdo. "
                        "Use quando o usuário pedir 'auditoria de rastreabilidade', 'o que está "
                        "incompleto no projeto', 'gaps de documentação' ou 'requisitos sem "
                        "origem'."
                    ),
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "analisar_tendencias",
                    "description": (
                        "Detecta padrões longitudinais no projeto, sem LLM: requisitos que mais "
                        "mudam de versão (instabilidade), temas IBIS mais debatidos (mais "
                        "alternativas discutidas) e distribuição de contradições por "
                        "severidade/status. Não inclui ranking de participante — dado não "
                        "estruturado o suficiente pra isso sem risco de fabricação. Use quando "
                        "o usuário pedir 'tendências do projeto', 'requisitos mais instáveis', "
                        "'temas mais discutidos' ou 'padrões ao longo do tempo'."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "top_n": {
                                "type": "integer",
                                "description": "Quantos itens mostrar por ranking. Padrão: 5.",
                            },
                        },
                        "required": [],
                    },
                },
            },
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
]

class _KnowledgeRequirements2ToolsMixin:
    """Mixin: tools_knowledge_requirements2 tools."""

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

    def merge_requirements(
        self,
        req_numbers: list[int],
        keep_number: int,
        merge_strategy: str = "combine",
        merge_note: str = "",
    ) -> str:
        """Mescla requisitos duplicados: absorve os secundários no principal."""
        from modules.supabase_client import get_supabase_client
        from datetime import datetime, timezone
        db = get_supabase_client()
        if not db:
            return "❌ Supabase não configurado."
        if keep_number not in req_numbers:
            return f"❌ keep_number ({keep_number}) deve estar em req_numbers."
        if len(req_numbers) < 2:
            return "❌ Informe ao menos 2 requisitos para mesclar."

        absorbed = [n for n in req_numbers if n != keep_number]

        # Busca todos os requisitos
        try:
            rows = (
                db.table("requirements")
                .select("id, req_number, title, description, status, priority, "
                        "req_type, first_meeting_id, last_meeting_id")
                .eq("project_id", self.project_id)
                .in_("req_number", req_numbers)
                .execute().data or []
            )
        except Exception as exc:
            return f"❌ Erro ao buscar requisitos: {exc}"

        by_num = {r["req_number"]: r for r in rows}
        missing = [n for n in req_numbers if n not in by_num]
        if missing:
            return f"❌ Requisitos não encontrados: {[f'REQ-{n:03d}' for n in missing]}"

        keep_row = by_num[keep_number]
        keep_id  = keep_row["id"]
        now      = datetime.now(timezone.utc).isoformat()

        # Mescla descrições
        if merge_strategy == "keep_main":
            new_desc = keep_row.get("description") or ""
        elif merge_strategy == "longest":
            all_descs = [by_num[n].get("description") or "" for n in req_numbers]
            new_desc  = max(all_descs, key=len)
        else:  # combine
            parts = [keep_row.get("description") or ""]
            for n in absorbed:
                d = by_num[n].get("description") or ""
                if d and d not in parts[0]:
                    parts.append(f"[Absorvido de REQ-{n:03d}] {d}")
            new_desc = "\n\n".join(p for p in parts if p)

        # Transfere versões dos absorvidos para o requisito mantido
        try:
            ver_q = (
                db.table("requirement_versions")
                .select("version")
                .eq("requirement_id", keep_id)
                .order("version", desc=True)
                .limit(1)
                .execute().data or []
            )
            next_ver = (ver_q[0]["version"] + 1) if ver_q else 1
        except Exception:
            next_ver = 1

        for n in absorbed:
            abs_id = by_num[n]["id"]
            try:
                abs_vers = (
                    db.table("requirement_versions")
                    .select("*")
                    .eq("requirement_id", abs_id)
                    .order("version")
                    .execute().data or []
                )
                for v in abs_vers:
                    payload = {k: v[k] for k in v if k not in ("id", "requirement_id")}
                    payload["requirement_id"] = keep_id
                    payload["version"]        = next_ver
                    payload["change_note"]    = (
                        f"[Transferido de REQ-{n:03d}] {payload.get('change_note') or ''}"
                    ).strip()
                    db.table("requirement_versions").insert(payload).execute()
                    next_ver += 1
            except Exception:
                pass  # best-effort

        # Atualiza descrição do requisito mantido e insere versão de mesclagem
        try:
            db.table("requirements").update({
                "description": new_desc,
                "updated_at":  now,
            }).eq("id", keep_id).execute()
            db.table("requirement_versions").insert({
                "requirement_id": keep_id,
                "version":        next_ver,
                "title":          keep_row.get("title", ""),
                "description":    new_desc,
                "status":         keep_row.get("status", "active"),
                "priority":       keep_row.get("priority"),
                "req_type":       keep_row.get("req_type"),
                "change_type":    "merge",
                "changed_at":     now,
                "change_note":    merge_note or (
                    f"Mesclagem de {[f'REQ-{n:03d}' for n in absorbed]}"
                ),
            }).execute()
        except Exception as exc:
            return f"❌ Erro ao atualizar REQ-{keep_number:03d}: {exc}"

        # Marca absorvidos como deprecated
        absorbed_labels = []
        for n in absorbed:
            abs_id = by_num[n]["id"]
            try:
                db.table("requirements").update({
                    "status":      "deprecated",
                    "status_note": f"Mesclado em REQ-{keep_number:03d}",
                    "updated_at":  now,
                }).eq("id", abs_id).execute()
                absorbed_labels.append(f"REQ-{n:03d}")
            except Exception:
                pass

        return (
            f"✅ Mesclagem concluída!\n"
            f"• Mantido: **REQ-{keep_number:03d}** — {keep_row.get('title', '')}\n"
            f"• Absorvidos (deprecated): {', '.join(absorbed_labels)}\n"
            f"• Estratégia: {merge_strategy}\n"
            f"• Histórico de versões transferido\n"
            + (f"• Nota: {merge_note}" if merge_note else "")
        )

    def diff_requirement(
        self,
        req_number: int,
        from_version: int | None = None,
        to_version:   int | None = None,
    ) -> str:
        """Renderiza diff visual entre duas versões de um requisito."""
        import difflib
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "❌ Supabase não configurado."

        # Busca ID do requisito
        try:
            rows = (
                db.table("requirements")
                .select("id, req_number, title")
                .eq("project_id", self.project_id)
                .eq("req_number", req_number)
                .limit(1)
                .execute().data or []
            )
        except Exception as exc:
            return f"❌ Erro ao buscar REQ-{req_number:03d}: {exc}"
        if not rows:
            return f"❌ REQ-{req_number:03d} não encontrado."

        req_id = rows[0]["id"]
        title  = rows[0].get("title") or f"REQ-{req_number:03d}"

        # Busca versões
        try:
            versions = (
                db.table("requirement_versions")
                .select("version, title, description, change_type, change_summary, created_at")
                .eq("requirement_id", req_id)
                .order("version")
                .execute().data or []
            )
        except Exception as exc:
            return f"❌ Erro ao buscar versões: {exc}"

        if len(versions) < 2:
            return f"REQ-{req_number:03d} tem apenas {len(versions)} versão — diff requer ao menos 2."

        ver_map = {v["version"]: v for v in versions}
        ver_nums = sorted(ver_map.keys())

        from_v = from_version or ver_nums[0]
        to_v   = to_version   or ver_nums[-1]

        if from_v not in ver_map:
            return f"❌ Versão {from_v} não encontrada. Versões disponíveis: {ver_nums}"
        if to_v not in ver_map:
            return f"❌ Versão {to_v} não encontrada. Versões disponíveis: {ver_nums}"
        if from_v >= to_v:
            return f"❌ from_version ({from_v}) deve ser menor que to_version ({to_v})."

        va = ver_map[from_v]
        vb = ver_map[to_v]

        def _words(text: str) -> list[str]:
            """Split into words preserving whitespace as separate tokens."""
            import re
            return re.split(r"(\s+)", text or "")

        def _build_diff_html(old_text: str, new_text: str) -> str:
            old_words = _words(old_text)
            new_words = _words(new_text)
            sm     = difflib.SequenceMatcher(None, old_words, new_words, autojunk=False)
            parts  = []
            for tag, i1, i2, j1, j2 in sm.get_opcodes():
                if tag == "equal":
                    parts.append("".join(old_words[i1:i2]).replace("&", "&amp;").replace("<", "&lt;"))
                elif tag == "replace":
                    old_chunk = "".join(old_words[i1:i2]).replace("&", "&amp;").replace("<", "&lt;")
                    new_chunk = "".join(new_words[j1:j2]).replace("&", "&amp;").replace("<", "&lt;")
                    parts.append(f'<del class="del">{old_chunk}</del><ins class="ins">{new_chunk}</ins>')
                elif tag == "delete":
                    chunk = "".join(old_words[i1:i2]).replace("&", "&amp;").replace("<", "&lt;")
                    parts.append(f'<del class="del">{chunk}</del>')
                elif tag == "insert":
                    chunk = "".join(new_words[j1:j2]).replace("&", "&amp;").replace("<", "&lt;")
                    parts.append(f'<ins class="ins">{chunk}</ins>')
            return "".join(parts)

        def _esc(s):
            return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        title_diff    = _build_diff_html(va.get("title") or "", vb.get("title") or "")
        desc_diff     = _build_diff_html(va.get("description") or "", vb.get("description") or "")
        date_a        = (va.get("created_at") or "")[:10]
        date_b        = (vb.get("created_at") or "")[:10]
        note_b        = _esc(vb.get("change_summary") or vb.get("change_type") or "")

        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f1117;color:#e0e0e0;margin:0;padding:10px;}}
h3{{font-size:14px;margin:0 0 4px;color:#94a3b8;}}
.meta{{font-size:11px;color:#64748b;margin-bottom:12px;}}
.field-label{{font-size:11px;color:#9ca3af;text-transform:uppercase;letter-spacing:.04em;margin:12px 0 4px;}}
.diff-box{{font-size:13px;line-height:1.7;background:#131620;padding:10px 12px;border-radius:6px;border:1px solid #2a2d38;white-space:pre-wrap;word-break:break-word;}}
del.del{{background:#7f1d1d;color:#fca5a5;text-decoration:line-through;border-radius:2px;padding:0 1px;}}
ins.ins{{background:#14532d;color:#86efac;text-decoration:none;border-radius:2px;padding:0 1px;}}
.legend{{font-size:11px;color:#6b7280;margin-top:10px;}}
</style></head><body>
<h3>REQ-{req_number:03d} — {_esc(title)}</h3>
<p class="meta">
  Diff: <strong>v{from_v}</strong> ({date_a or '—'}) → <strong>v{to_v}</strong> ({date_b or '—'})
  {(' · ' + note_b) if note_b else ''}
</p>
<div class="field-label">Título</div>
<div class="diff-box">{title_diff or '(sem alteração)'}</div>
<div class="field-label">Descrição</div>
<div class="diff-box">{desc_diff or '(sem alteração)'}</div>
<p class="legend">
  <del class="del">Removido</del> &nbsp; <ins class="ins">Adicionado</ins>
</p>
</body></html>"""

        import streamlit as st
        st.session_state.setdefault("_pending_widgets", []).append({
            "type": "req_diff_html",
            "html": html,
        })
        return (
            f"📋 Diff REQ-{req_number:03d} — v{from_v} ({date_a or '?'}) → v{to_v} ({date_b or '?'}) "
            "renderizado no chat. Vermelho = removido, verde = adicionado."
        )

    def search_universal(
        self,
        query: str,
        scopes: list[str] | None = None,
    ) -> str:
        """Busca uma query em todos os tipos de artefatos e retorna resultados agrupados."""
        all_scopes = {"transcripts", "requirements", "sbvr", "ibis", "documents"}
        active = set(scopes) & all_scopes if scopes else all_scopes

        sections: list[str] = [f"## 🔍 Busca Universal: '{query}'\n"]
        found_any = False

        if "transcripts" in active:
            result = self.search_transcript(query)
            if "Nenhum" not in result and "sem palavras-chave" not in result:
                sections.append(f"### 🎙️ Transcrições\n{result}")
                found_any = True

        if "requirements" in active:
            result = self.get_requirements(keyword=query, page_size=10)
            if "Nenhum" not in result:
                sections.append(f"### 📋 Requisitos\n{result}")
                found_any = True

        if "sbvr" in active:
            terms = self.get_sbvr_terms(keyword=query)
            rules = self.get_sbvr_rules(keyword=query)
            sbvr_found = False
            if "Nenhum" not in terms:
                sections.append(f"### 📖 Termos SBVR\n{terms}")
                sbvr_found = True
            if "Nenhum" not in rules:
                sections.append(f"### 📖 Regras SBVR\n{rules}")
                sbvr_found = True
            if sbvr_found:
                found_any = True

        if "ibis" in active:
            result = self.search_ibis_debates(query)
            if "Nenhum" not in result:
                sections.append(f"### 🗺️ Debates IBIS\n{result}")
                found_any = True

        if "documents" in active:
            result = self.search_documents(query, mode="keyword")
            if "Nenhum" not in result:
                sections.append(f"### 📄 Documentos\n{result}")
                found_any = True

        if not found_any:
            return f"🔍 Nenhum resultado encontrado para '{query}' em nenhum artefato do projeto."

        return "\n\n---\n\n".join(sections)

    def batch_text_correction(
        self,
        corrections: list[dict],
        meeting_number: int | None = None,
    ) -> str:
        """Aplica múltiplas correções find→replace em uma única chamada."""
        if not corrections:
            return "❌ Lista de correções vazia."

        summary_lines: list[str] = [
            f"## Correção em Lote — {len(corrections)} substituição(ões)\n"
        ]
        total_changes = 0
        errors: list[str] = []

        for i, corr in enumerate(corrections, start=1):
            find    = corr.get("find") or ""
            replace = corr.get("replace") or ""
            scope   = corr.get("scope") or "all"

            if not find:
                errors.append(f"#{i}: 'find' vazio — ignorado.")
                continue

            result = self.apply_text_correction(find, replace, scope, meeting_number)

            # Count how many ✅ lines are in the result
            ok_count = result.count("✅")
            total_changes += ok_count

            summary_lines.append(
                f"**#{i}** `{find}` → `{replace}` (escopo: {scope})\n"
                + (f"{result}\n" if result else "  Nenhuma ocorrência encontrada.\n")
            )

        if errors:
            summary_lines.append("**Avisos:**\n" + "\n".join(f"- {e}" for e in errors))

        summary_lines.append(f"\n**Total de registros modificados: {total_changes}**")
        return "\n\n".join(summary_lines)

    def detect_requirement_contradictions(
        self,
        meeting_number: int | None = None,
        req_type: str | None = None,
        max_reqs: int = 80,
    ) -> str:
        """Usa LLM para identificar pares de requisitos com possível contradição."""
        import json
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        max_reqs = max(10, min(int(max_reqs or 80), 120))

        # Resolve meeting_number → UUID para filtro opcional
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

        # Busca requisitos
        try:
            q = (
                db.table("requirements")
                .select("req_number, title, description, req_type, status")
                .eq("project_id", self.project_id)
                .not_.in_("status", ["deprecated", "rejected", "cancelled"])
                .order("req_number")
                .limit(max_reqs)
            )
            if req_type:
                q = q.eq("req_type", req_type)
            if meeting_id_filter:
                q = q.eq("first_meeting_id", meeting_id_filter)
            rows = q.execute().data or []
        except Exception as exc:
            return f"Erro ao acessar requisitos: {exc}"

        if len(rows) < 2:
            return "Não há requisitos suficientes para análise de contradições (mínimo: 2)."

        ctx = f" da Reunião {meeting_number} — {meeting_label}" if meeting_number else " do projeto"
        if len(rows) == max_reqs:
            cap_note = f" (primeiros {max_reqs} requisitos)"
        else:
            cap_note = ""

        # Prepara lista compacta para o LLM
        req_list = [
            {
                "id":    f"REQ-{r['req_number']:03d}",
                "tipo":  r.get("req_type") or "—",
                "title": r.get("title") or "",
                "desc":  (r.get("description") or "")[:400],
            }
            for r in rows
        ]

        system_prompt = (
            "Você é um analista sênior de requisitos. "
            "Sua tarefa é identificar PARES de requisitos que apresentem possível contradição ou conflito lógico.\n\n"
            "Tipos de contradição a detectar:\n"
            "- Negação direta: um exige X e outro proíbe X\n"
            "- Conflito de regra de negócio: dois requisitos impõem regras incompatíveis para o mesmo cenário\n"
            "- Inconsistência de prioridade/comportamento: o mesmo sistema age de modos opostos\n"
            "- Ambiguidade conflitante: termos iguais com semânticas opostas entre requisitos\n\n"
            "Para CADA par contraditório retorne:\n"
            "  req_a: ID do primeiro requisito (ex: 'REQ-012')\n"
            "  req_b: ID do segundo requisito\n"
            "  motivacao: explicação clara e objetiva do conflito (2-4 frases, sem jargão)\n"
            "  severidade: 'alta' | 'media' | 'baixa'\n"
            "  sugestao: como harmonizar os dois requisitos (1-2 frases)\n\n"
            "Retorne SOMENTE JSON válido no formato:\n"
            "{\"pares\": [{\"req_a\":\"...\",\"req_b\":\"...\",\"motivacao\":\"...\","
            "\"severidade\":\"...\",\"sugestao\":\"...\"}]}\n\n"
            "Se não houver contradições reais, retorne {\"pares\": []}.\n"
            "Não invente contradições. Só inclua pares com suspeita fundamentada."
        )
        user_prompt = (
            f"Analise os {len(req_list)} requisitos abaixo{ctx}{cap_note} "
            "e identifique pares em possível contradição:\n\n"
            + json.dumps(req_list, ensure_ascii=False, indent=2)
        )

        try:
            raw = self._llm_call(system_prompt, user_prompt, max_tokens=4000)
        except Exception as exc:
            return f"❌ Erro na chamada LLM: {exc}"

        # Parse JSON
        try:
            # Strip markdown fences if present
            raw_clean = raw.strip()
            if raw_clean.startswith("```"):
                raw_clean = raw_clean.split("```")[1]
                if raw_clean.startswith("json"):
                    raw_clean = raw_clean[4:]
            data = json.loads(raw_clean)
            pairs = data.get("pares") or []
        except Exception:
            # Fallback: return raw text
            return f"Análise de contradições{ctx}:\n\n{raw}"

        if not pairs:
            return (
                f"✅ Nenhuma contradição detectada entre os {len(rows)} requisitos{ctx}{cap_note}.\n"
                "Os requisitos analisados parecem consistentes entre si."
            )

        # Build HTML widget
        def _esc(s: str) -> str:
            return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        def _sev_cls(s: str) -> str:
            s = (s or "").lower()
            if s == "alta":
                return "sev-alta"
            if s == "media":
                return "sev-media"
            return "sev-baixa"

        def _sev_label(s: str) -> str:
            return {"alta": "Alta", "media": "Média", "baixa": "Baixa"}.get((s or "").lower(), s)

        cards_html = ""
        for i, p in enumerate(pairs):
            ra      = _esc(p.get("req_a", ""))
            rb      = _esc(p.get("req_b", ""))
            motiv   = _esc(p.get("motivacao", "—"))
            sev     = (p.get("severidade") or "baixa").lower()
            sug     = _esc(p.get("sugestao", ""))
            sev_cls = _sev_cls(sev)
            sev_lbl = _sev_label(sev)
            cards_html += (
                f'<div class="pair-card">'
                f'<div class="pair-header" onclick="toggle(this)">'
                f'<span class="pair-ids">{ra} ↔ {rb}</span>'
                f'<span class="sev-badge {sev_cls}">⚠ {sev_lbl}</span>'
                f'<span class="toggle-icon">▶</span>'
                f'</div>'
                f'<div class="pair-body">'
                f'<div class="field-label">Motivação do conflito</div>'
                f'<div class="motiv-box">{motiv}</div>'
                + (
                    f'<div class="field-label">Sugestão de resolução</div>'
                    f'<div class="field-value sug-text">{sug}</div>'
                    if sug else ""
                )
                + f'</div>'
                f'</div>'
            )

        summary_line = _esc(
            f"{len(pairs)} par(es) com possível contradição entre {len(rows)} requisitos{ctx}{cap_note}"
        )

        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0f1117;color:#e0e0e0;margin:0;padding:8px;}}
.summary{{color:#9ca3af;font-size:12px;margin-bottom:10px;}}
.pair-card{{border:1px solid #2a2d38;border-radius:6px;margin:6px 0;overflow:hidden;}}
.pair-header{{display:flex;align-items:center;gap:8px;padding:10px 12px;cursor:pointer;user-select:none;background:#1a1d24;}}
.pair-header:hover{{background:#22262f;}}
.pair-ids{{font-weight:700;font-size:13px;font-family:monospace;flex:1;}}
.sev-badge{{font-size:11px;padding:2px 8px;border-radius:3px;font-weight:600;flex-shrink:0;}}
.sev-alta{{background:#7f1d1d;color:#fca5a5;}}
.sev-media{{background:#78350f;color:#fcd34d;}}
.sev-baixa{{background:#1e3a5f;color:#93c5fd;}}
.toggle-icon{{font-size:10px;color:#6b7280;flex-shrink:0;}}
.pair-body{{padding:12px 14px;display:none;background:#131620;border-top:1px solid #2a2d38;}}
.pair-body.open{{display:block;}}
.field-label{{font-size:11px;color:#9ca3af;margin-top:10px;margin-bottom:3px;text-transform:uppercase;letter-spacing:.04em;}}
.field-label:first-child{{margin-top:0;}}
.field-value{{font-size:13px;line-height:1.6;}}
.motiv-box{{font-size:13px;line-height:1.6;background:#1a1218;border-left:3px solid #f87171;padding:8px 10px;border-radius:3px;color:#fecaca;}}
.sug-text{{color:#a7f3d0;background:#052e16;border-left:3px solid #16a34a;padding:6px 10px;border-radius:3px;font-size:12px;}}
</style></head><body>
<p class="summary">{summary_line}</p>
{cards_html}
<script>
function toggle(el){{
  var b=el.nextElementSibling,i=el.querySelector('.toggle-icon');
  if(b.classList.contains('open')){{b.classList.remove('open');i.textContent='▶';}}
  else{{b.classList.add('open');i.textContent='▼';}}
}}
</script>
</body></html>"""

        import streamlit as st
        height = min(len(pairs) * 60 + 80, 700)
        st.session_state.setdefault("_pending_widgets", []).append({
            "type":  "req_contradictions_html",
            "html":  html,
            "count": len(pairs),
        })
        return (
            f"⚠️ Foram identificados **{len(pairs)} par(es)** com possível contradição "
            f"entre os {len(rows)} requisitos analisados{ctx}{cap_note}. "
            "Clique em cada par para ver a motivação e sugestão de resolução."
        )

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

    def sugerir_encaminhamentos_pendentes(self, meeting_number: int | None = None) -> str:
        """Compara Decisões x Encaminhamentos da ata (texto livre em
        minutes_md, sem tabela estruturada de action items no banco) via LLM,
        pra achar decisões sem item de ação correspondente e encaminhamentos
        com prazo aparentemente vencido. meeting_number=None analisa as 5
        reuniões mais recentes; passar um número foca numa reunião só."""
        meetings = self._get_meetings()
        if not meetings:
            return "Nenhuma reunião encontrada neste projeto."

        if meeting_number is not None:
            target = [m for m in meetings if m.get("meeting_number") == meeting_number]
            if not target:
                return f"Reunião {meeting_number} não encontrada."
        else:
            target = meetings[-5:]

        from datetime import date as _date
        today_str = _date.today().isoformat()

        lines: list[str] = ["# 📋 Encaminhamentos Pendentes\n"]
        analisadas = 0
        for m in target:
            md = m.get("minutes_md") or ""
            if not md:
                continue
            decisions = self._section(md, "Decisões", "Decisões Tomadas", "Decisions")
            actions = self._section(
                md, "Encaminhamentos / Action Items", "Encaminhamentos",
                "Itens de Ação", "Action Items", "Ações",
            )
            if not decisions and not actions:
                continue
            analisadas += 1
            num   = m.get("meeting_number")
            title = m.get("title") or f"Reunião {num}"

            system = (
                "Você analisa atas de reunião pra achar (1) decisões sem encaminhamento/ação "
                "correspondente registrada e (2) encaminhamentos cujo prazo já passou. "
                "Responda em Português do Brasil, só com o que encontrar de fato — se uma "
                "categoria não tiver nenhuma pendência, diga isso claramente em vez de forçar "
                "um achado. Máximo 5 itens por categoria, objetivo, sem repetir o texto da ata."
            )
            user = (
                f"Data de hoje: {today_str}\n\n"
                f"**Decisões da reunião:**\n{decisions or '(nenhuma seção de decisões na ata)'}\n\n"
                f"**Encaminhamentos da reunião:**\n{actions or '(nenhuma seção de encaminhamentos na ata)'}\n\n"
                "1. Decisões que parecem não ter um encaminhamento/ação correspondente registrada.\n"
                "2. Encaminhamentos com prazo mencionado que já passou da data de hoje."
            )
            try:
                result = self._llm_call(system, user, max_tokens=700)
            except Exception as exc:
                result = f"⚠️ Erro ao analisar: {exc}"

            lines.append(f"## Reunião {num} — {title}")
            lines.append(result)
            lines.append("")

        if not analisadas:
            escopo = f"a reunião {meeting_number}" if meeting_number is not None else "as reuniões recentes"
            return f"Nenhuma decisão ou encaminhamento registrado em {escopo} para analisar."
        return "\n".join(lines)

    def verificar_rastreabilidade_obrigatoria(self) -> str:
        """Project-wide gap analysis, no LLM: requirements missing source_quote,
        IBIS questions with no alternative/resolution, BPMN processes with no
        description. Distinct from diagnostico_projeto (pipeline health)."""
        from modules.supabase_client import get_supabase_client

        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        meetings = self._get_meetings()
        if not meetings:
            return "Nenhuma reunião encontrada. Processe transcrições no Pipeline."

        # ── 1. Requisitos sem source_quote ──────────────────────────────────
        reqs_sem_origem: list[str] = []
        try:
            reqs = (
                db.table("requirements")
                .select("req_number, title, source_quote")
                .eq("project_id", self.project_id)
                .execute().data or []
            )
            reqs_sem_origem = [
                f"REQ-{r.get('req_number', 0):03d} — {r.get('title', '')}"
                for r in reqs if not (r.get("source_quote") or "").strip()
            ]
            n_reqs = len(reqs)
        except Exception:
            n_reqs = 0

        # ── 2. Questões IBIS sem alternativa nem resolução ──────────────────
        # IBIS não é uma tabela própria — vive como JSON em meetings.argumentation_json
        # (ver _load_ibis_questions, compartilhado com search_ibis_debates/get_ibis_timeline).
        ibis_incompletas: list[str] = []
        try:
            qs = self._load_ibis_questions()
            for q in qs:
                has_alt = bool(q.get("alternatives"))
                has_res = bool((q.get("resolution") or {}).get("type"))
                if not has_alt and not has_res:
                    stmt = (q.get("statement") or "")[:80]
                    ibis_incompletas.append(f"«{stmt}»")
            n_ibis = len(qs)
        except Exception:
            n_ibis = 0

        # ── 3. Processos BPMN sem descrição ─────────────────────────────────
        bpmn_sem_desc: list[str] = []
        try:
            procs = (
                db.table("bpmn_processes")
                .select("name, description")
                .eq("project_id", self.project_id)
                .execute().data or []
            )
            bpmn_sem_desc = [
                p.get("name", "") for p in procs if not (p.get("description") or "").strip()
            ]
            n_bpmn = len(procs)
        except Exception:
            n_bpmn = 0

        lines = ["## 🔍 Rastreabilidade Obrigatória — Gap Analysis\n"]

        lines.append(f"### 📋 Requisitos ({n_reqs} total)")
        if reqs_sem_origem:
            lines.append(f"**{len(reqs_sem_origem)} sem fonte na transcrição (`source_quote` vazio):**")
            lines.extend(f"- {r}" for r in reqs_sem_origem[:20])
            if len(reqs_sem_origem) > 20:
                lines.append(f"- ... e mais {len(reqs_sem_origem) - 20}")
        else:
            lines.append("✅ Todos os requisitos têm fonte rastreável na transcrição.")
        lines.append("")

        lines.append(f"### 💬 Questões IBIS ({n_ibis} total)")
        if ibis_incompletas:
            lines.append(f"**{len(ibis_incompletas)} sem alternativa registrada nem resolução:**")
            lines.extend(f"- {q}" for q in ibis_incompletas[:20])
            if len(ibis_incompletas) > 20:
                lines.append(f"- ... e mais {len(ibis_incompletas) - 20}")
        else:
            lines.append("✅ Todas as questões IBIS têm alternativa ou resolução registrada.")
        lines.append("")

        lines.append(f"### ⚙️ Processos BPMN ({n_bpmn} total)")
        if bpmn_sem_desc:
            lines.append(f"**{len(bpmn_sem_desc)} sem descrição textual:**")
            lines.extend(f"- {p}" for p in bpmn_sem_desc[:20])
        else:
            lines.append("✅ Todos os processos BPMN têm descrição.")

        total_gaps = len(reqs_sem_origem) + len(ibis_incompletas) + len(bpmn_sem_desc)
        lines.insert(1, f"**{total_gaps} gap(s) de rastreabilidade encontrado(s)** no projeto.\n")

        return "\n".join(lines)

    def analisar_tendencias(self, top_n: int = 5) -> str:
        """Project-wide longitudinal trends, no LLM: requirements with the most
        revisions, most-debated IBIS topics, contradictions by severity/status.
        Deliberately does NOT rank participants by contested contributions —
        no table links a contradiction/revision to a specific author, and
        approximating that from free-text minutes would risk misattribution."""
        from modules.supabase_client import get_supabase_client

        meetings = self._get_meetings()
        if not meetings:
            return "Nenhuma reunião encontrada. Processe transcrições no Pipeline."

        db = get_supabase_client()
        if not db:
            return "Banco de dados não disponível."

        # ── 1. Requisitos que mais mudam de versão ──────────────────────────
        top_unstable: list[tuple[str, str, int]] = []
        try:
            meeting_ids = [m["id"] for m in meetings]
            versions = (
                db.table("requirement_versions")
                .select("requirement_id")
                .in_("meeting_id", meeting_ids)
                .execute().data or []
            ) if meeting_ids else []
            from collections import Counter
            counts = Counter(v["requirement_id"] for v in versions if v.get("requirement_id"))
            top_ids = [rid for rid, _ in counts.most_common(top_n)]
            if top_ids:
                reqs = (
                    db.table("requirements")
                    .select("id, req_number, title")
                    .in_("id", top_ids)
                    .execute().data or []
                )
                req_lookup = {r["id"]: r for r in reqs}
                top_unstable = [
                    (
                        f"REQ-{req_lookup.get(rid, {}).get('req_number', 0):03d}",
                        req_lookup.get(rid, {}).get("title", "—"),
                        n,
                    )
                    for rid, n in counts.most_common(top_n)
                    if rid in req_lookup
                ]
        except Exception:
            pass

        # ── 2. Temas IBIS mais debatidos (mais alternativas discutidas) ─────
        top_debated: list[tuple[str, int]] = []
        try:
            qs = self._load_ibis_questions()
            ranked = sorted(qs, key=lambda q: len(q.get("alternatives") or []), reverse=True)
            top_debated = [
                (q.get("statement", "")[:100], len(q.get("alternatives") or []))
                for q in ranked[:top_n] if q.get("alternatives")
            ]
        except Exception:
            pass

        # ── 3. Contradições por severidade/status ───────────────────────────
        contra_by_severity: dict = {}
        n_open = n_resolved = 0
        try:
            contras = (
                db.table("kh_contradictions")
                .select("severity, status")
                .eq("project_id", self.project_id)
                .execute().data or []
            )
            from collections import Counter as _Counter
            contra_by_severity = _Counter(c.get("severity") or "—" for c in contras)
            n_open = sum(1 for c in contras if c.get("status") == "open")
            n_resolved = sum(1 for c in contras if c.get("status") != "open")
        except Exception:
            pass

        lines = ["## 📈 Análise de Tendências\n"]

        lines.append("### 🔄 Requisitos mais instáveis (mais revisões)")
        if top_unstable:
            for label, title, n in top_unstable:
                lines.append(f"- {label} — {title}: **{n} versão(ões)**")
        else:
            lines.append("Nenhum requisito com múltiplas versões registradas.")
        lines.append("")

        lines.append("### 💬 Temas IBIS mais debatidos (por nº de alternativas)")
        if top_debated:
            for stmt, n_alt in top_debated:
                lines.append(f"- «{stmt}» — **{n_alt} alternativa(s)**")
        else:
            lines.append("Nenhuma questão IBIS com alternativas registradas.")
        lines.append("")

        lines.append("### ⚠️ Contradições por severidade")
        if contra_by_severity:
            for sev, n in contra_by_severity.most_common():
                lines.append(f"- {sev}: {n}")
            lines.append(f"\n{n_open} aberta(s) · {n_resolved} resolvida(s)/outro status")
        else:
            lines.append("Nenhuma contradição registrada no Knowledge Hub.")

        return "\n".join(lines)

    def diagnostico_projeto(
        self,
        include_integrity: bool = True,
        include_contradictions: bool = True,
        include_roi: bool = True,
        include_recurring: bool = True,
        include_pendencies: bool = True,
        include_revision_requests: bool = True,
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

        # 7. Revisões solicitadas pendentes (solicitar_revisao_requisito) —
        # única forma de visibilidade dessas solicitações hoje: não há
        # notificação por e-mail/Slack, então precisam aparecer aqui.
        if include_revision_requests:
            try:
                pending = (
                    get_supabase_client()
                    .table("requirements")
                    .select("req_number, title, status_note")
                    .eq("project_id", self.project_id)
                    .eq("status", "revised")
                    .execute().data or []
                )
                from core.tools.tools_meetings_requirements import _MeetingsRequirementsToolsMixin as _MRM
                marker = _MRM._REVISION_REQUEST_MARKER
                pending = [r for r in pending if (r.get("status_note") or "").startswith(marker)]
                if pending:
                    itens = ", ".join(f"REQ-{r['req_number']:03d}" for r in pending[:8])
                    alertas.append(f"**{len(pending)} requisito(s)** com revisão solicitada pendente: {itens}")
                    acoes.append((2, "Revisar pendências: `estimar_risco_requisito()` ou consulte cada REQ"))
                else:
                    oks.append("Nenhuma revisão solicitada pendente ✓")
            except Exception:
                pass

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
