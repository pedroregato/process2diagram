# core/tools/tools_bpmn_sbvr.py
# Auto-extracted from core/assistant_tools.py (split PC115) — mixin for AssistantToolExecutor.
# Methods here assume `self` is an AssistantToolExecutor instance (project_id, llm_config,
# _meeting_cache, _pending_charts, _palette — set in AssistantToolExecutor.__init__).

from __future__ import annotations
import re
from core.chart_config import CHART_PALETTES, DEFAULT_PALETTE
from core.tools._shared import _compute_initials


BPMN_SBVR_SCHEMAS: list[dict] = [
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
                    "name": "ask_bpmn_diagram",
                    "description": (
                        "Responde a uma pergunta livre sobre um diagrama BPMN já armazenado, via análise LLM "
                        "(AgentBPMNAnalyst) — não apenas a descrição estruturada fixa de describe_bpmn_process. "
                        "Use para perguntas específicas como: 'Descreva o subprocesso X', 'Quem aprova o contrato?', "
                        "'O que acontece se a proposta for reprovada?', 'Essa fase tem alguma decisão automatizada?'. "
                        "Quando a pergunta for sobre uma fase (callActivity) que já tem detalhamento salvo "
                        "(ver BpmnEditor), a resposta usa os passos internos reais dessa fase, não apenas o resumo. "
                        "Use list_bpmn_processes para descobrir os nomes disponíveis."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "process_name": {
                                "type": "string",
                                "description": "Nome (ou parte do nome) do processo BPMN sobre o qual perguntar",
                            },
                            "question": {
                                "type": "string",
                                "description": "Pergunta em linguagem natural sobre o processo",
                            },
                        },
                        "required": ["process_name", "question"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "generate_bpmn_diagram",
                    "description": (
                        "Gera um novo diagrama BPMN 2.0 a partir da transcrição de uma reunião existente OU de "
                        "uma descrição de processo em texto livre — mesmo mecanismo de geração do BPMN Studio "
                        "(torneio de execuções + AgentValidator). NÃO salva automaticamente — retorna o XML "
                        "gerado, uma descrição estruturada e o score de qualidade para revisão. "
                        "Use quando o usuário pedir: 'Gere um BPMN para a Reunião N', 'Crie um diagrama a partir "
                        "desta descrição: ...', 'Monte o fluxo BPMN deste processo'. "
                        "Após o usuário confirmar que o resultado está bom, use save_generated_bpmn para persistir."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "meeting_number": {
                                "type": "integer",
                                "description": "Número da reunião cuja transcrição será usada como base (opcional se description for informado)",
                            },
                            "description": {
                                "type": "string",
                                "description": "Descrição do processo em texto livre — usada quando não há reunião de referência (opcional se meeting_number for informado)",
                            },
                            "n_runs": {
                                "type": "integer",
                                "description": "Número de execuções independentes do torneio de qualidade (1-3). Padrão 1 — mais execuções melhoram a qualidade mas custam mais tempo/tokens.",
                            },
                        },
                        "required": [],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "save_generated_bpmn",
                    "description": (
                        "Salva um diagrama BPMN gerado por generate_bpmn_diagram no projeto — cria um processo "
                        "novo, ou uma nova versão se já existir um processo com o mesmo nome. "
                        "Use APENAS depois que o usuário confirmar explicitamente que quer salvar o diagrama "
                        "apresentado por generate_bpmn_diagram. "
                        "Admin only."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "process_name": {
                                "type": "string",
                                "description": "Nome do processo a salvar",
                            },
                            "bpmn_xml": {
                                "type": "string",
                                "description": "XML BPMN 2.0 completo retornado por generate_bpmn_diagram",
                            },
                            "mermaid_code": {
                                "type": "string",
                                "description": "Código Mermaid correspondente (opcional)",
                            },
                            "meeting_number": {
                                "type": "integer",
                                "description": "Número da reunião de referência para vincular esta versão (opcional)",
                            },
                        },
                        "required": ["process_name", "bpmn_xml"],
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
]

class _BpmnSbvrToolsMixin:
    """Mixin: tools_bpmn_sbvr tools."""

    def describe_bpmn_process(self, process_name: str) -> str:
        """Gera descrição textual estruturada de um processo BPMN a partir do XML."""
        from core.project_store import list_bpmn_processes, list_bpmn_versions
        from modules.bpmn_describer import describe_bpmn_from_xml

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

        return describe_bpmn_from_xml(
            current["bpmn_xml"],
            process_name=proc["name"],
            version=current.get("version", "?"),
        )

    def _resolve_llm_agent_config(self) -> tuple[dict, dict] | None:
        """Build (client_info, provider_cfg) for instantiating a BaseAgent
        subclass from self.llm_config. Returns None when incomplete —
        callers should surface a clear error instead of instantiating an
        agent that will fail on its first _call_llm()."""
        api_key = self.llm_config.get("api_key", "")
        provider_cfg = self.llm_config.get("provider_cfg") or {}
        if not api_key or not provider_cfg.get("client_type"):
            return None
        return {"api_key": api_key}, provider_cfg

    def ask_bpmn_diagram(self, process_name: str, question: str) -> str:
        """Responde a uma pergunta livre sobre um diagrama BPMN via AgentBPMNAnalyst (LLM)."""
        from core.project_store import (
            list_bpmn_processes, list_bpmn_versions,
            get_current_bpmn_version_id, list_bpmn_callactivity_diagrams,
        )
        from agents.agent_bpmn_analyst import AgentBPMNAnalyst

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

        # Detalhamentos de fase salvos (PC120/PC129) cujo nome apareça na
        # pergunta — dá ao analista os passos internos reais da fase, em vez
        # de apenas a documentation resumida do diagrama principal.
        detail_context = ""
        try:
            version_id = current.get("id") or get_current_bpmn_version_id(proc["id"])
            details = list_bpmn_callactivity_diagrams(version_id) if version_id else []
            q_lower = question.lower()
            relevant = [
                d for d in details
                if (d.get("element_name") or "").strip()
                and d["element_name"].lower() in q_lower
            ]
            detail_context = "\n\n".join(
                f"### Detalhamento de '{d.get('element_name')}'\n```xml\n{d.get('bpmn_xml', '')}\n```"
                for d in relevant
            )
        except Exception:
            detail_context = ""

        agent_cfg = self._resolve_llm_agent_config()
        if not agent_cfg:
            return "❌ Configuração de LLM não disponível para consultar o diagrama."
        client_info, provider_cfg = agent_cfg

        agent = AgentBPMNAnalyst(client_info, provider_cfg)
        return agent.answer(
            process_name=proc["name"],
            bpmn_xml=current["bpmn_xml"],
            question=question,
            detail_context=detail_context,
        )

    def generate_bpmn_diagram(
        self,
        meeting_number: int | None = None,
        description: str | None = None,
        n_runs: int = 1,
    ) -> str:
        """Gera um novo diagrama BPMN a partir de uma transcrição existente ou
        de uma descrição livre — mesmo torneio do BPMN Studio. Não salva."""
        from agents.agent_bpmn_studio import generate_bpmn_from_description
        from modules.bpmn_describer import describe_bpmn_from_xml

        if meeting_number is not None:
            mtg = self._find_meeting(meeting_number)
            if not mtg:
                return f"Reunião {meeting_number} não encontrada."
            text = (mtg.get("transcript_clean") or mtg.get("transcript_raw") or "").strip()
            if not text:
                return f"Reunião {meeting_number} não possui transcrição armazenada."
            source_label = f"Reunião {meeting_number} — {mtg.get('title', '') or 'sem título'}"
        elif description and description.strip():
            text = description.strip()
            source_label = "descrição fornecida"
        else:
            return "Informe meeting_number (reunião existente) ou description (texto livre) para gerar o diagrama."

        if len(text.split()) < 15:
            return "Texto de origem muito curto para gerar um diagrama confiável (mínimo ~15 palavras)."

        agent_cfg = self._resolve_llm_agent_config()
        if not agent_cfg:
            return "❌ Configuração de LLM não disponível para gerar o diagrama."
        client_info, provider_cfg = agent_cfg

        n_runs = max(1, min(int(n_runs or 1), 3))  # cap de custo — sem permitir abuso via chat
        try:
            hub = generate_bpmn_from_description(
                text, client_info, provider_cfg,
                run_nlp=True, n_runs=n_runs,
            )
        except Exception as exc:
            return f"❌ Erro ao gerar o diagrama: {exc}"

        if not hub.bpmn.ready or not hub.bpmn.bpmn_xml:
            return "Não foi possível gerar um diagrama a partir deste texto."

        score = hub.validation.bpmn_score
        score_line = (
            f"**Score do torneio:** {score.weighted:.1f}/10 "
            f"(granularidade {score.granularity:.1f} · tipo de tarefa {score.task_type:.1f} · "
            f"gateways {score.gateways:.1f} · estrutural {score.structural:.1f} · "
            f"semântica {score.semantic:.1f})\n\n"
            if score else ""
        )
        description_md = describe_bpmn_from_xml(hub.bpmn.bpmn_xml, process_name=hub.bpmn.name)

        return (
            f"# Diagrama gerado a partir de: {source_label}\n\n"
            f"**Nome sugerido:** {hub.bpmn.name}\n\n"
            f"{score_line}"
            f"{description_md}\n\n"
            "---\n"
            "Para salvar este diagrama no projeto, confirme com o usuário e chame "
            "`save_generated_bpmn` com `process_name` e o `bpmn_xml` abaixo.\n\n"
            f"```xml\n{hub.bpmn.bpmn_xml}\n```"
        )

    def save_generated_bpmn(
        self,
        process_name: str,
        bpmn_xml: str,
        mermaid_code: str = "",
        meeting_number: int | None = None,
    ) -> str:
        """Salva um diagrama gerado por generate_bpmn_diagram — cria um novo
        processo, ou uma nova versão se já existir um com o mesmo nome."""
        from core.project_store import save_bpmn_from_hub
        from core.knowledge_hub import KnowledgeHub

        if not bpmn_xml or not bpmn_xml.strip():
            return "❌ XML BPMN vazio — gere o diagrama com generate_bpmn_diagram primeiro."
        if not process_name or not process_name.strip():
            return "❌ Informe um nome para o processo."

        meeting_id = None
        if meeting_number is not None:
            mtg = self._find_meeting(meeting_number)
            if mtg:
                meeting_id = mtg["id"]

        hub = KnowledgeHub.new()
        hub.bpmn.name = process_name.strip()
        hub.bpmn.bpmn_xml = bpmn_xml.strip()
        hub.bpmn.mermaid = mermaid_code or ""
        hub.bpmn.ready = True

        pid = save_bpmn_from_hub(meeting_id=meeting_id, project_id=self.project_id, hub=hub)
        if not pid:
            return f"❌ Erro ao salvar o diagrama '{process_name}'."

        return (
            f"✅ Diagrama '{process_name}' salvo com sucesso"
            + (f" — vinculado à Reunião {meeting_number}." if meeting_id else " — sem reunião vinculada.")
        )

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
            m = t.get("meetings") or {}
            n    = m.get("meeting_number")
            date = (m.get("meeting_date") or "")[:10]
            mtag = f" [Reunião {n} ({date or 'sem data'})]" if n else ""
            lines.append(f"• {t.get('term')}{mtag}: {t.get('definition')}")
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
            m = r.get("meetings") or {}
            n    = m.get("meeting_number")
            date = (m.get("meeting_date") or "")[:10]
            mtag = f" [Reunião {n} ({date or 'sem data'})]" if n else ""
            lines.append(f"• [{rule_id}]{mtag} {nucleo}: {statement}")
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
