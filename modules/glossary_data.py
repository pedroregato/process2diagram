# modules/glossary_data.py
# ─────────────────────────────────────────────────────────────────────────────
# Dados do Glossário técnico do Process2Diagram.
#
# Cada entrada é um dict com os campos:
#   term     — nome do termo em português (usado para agrupamento alfabético)
#   en       — nome em inglês / sigla original (pode ser "")
#   tag      — categoria: bpmn | req | ai | dev | neg
#   def_     — definição HTML (<strong> e <em> permitidos, max 2 <strong>)
#   example  — exemplo concreto do projeto (texto puro, sem HTML)
#   related  — lista de termos do mesmo glossário para links cruzados
#
# Categorias:
#   bpmn → Modelagem & BPMN       (#1a5080 azul processo)
#   req  → Requisitos & Spec      (#1a6040 verde)
#   ai   → IA & LLM               (#7a4a10 âmbar)
#   dev  → Dev & Infraestrutura   (#4a1a7a violeta)
#   neg  → Negócios & Metodologia (#6a2a10 terracota)
#   seg  → Segurança & Privacidade (#0a6050 verde-azulado)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations
import re

GLOSSARY_ENTRIES: list[dict] = [

    # ── A ─────────────────────────────────────────────────────────────────────

    {
        "term": "Agente LLM",
        "en": "LLM Agent",
        "tag": "ai",
        "def_": (
            "Componente autônomo que usa um LLM para realizar uma tarefa específica. "
            "Recebe um <strong>prompt de sistema</strong> (skill), lê e escreve no KnowledgeHub, "
            "e retorna saída estruturada (JSON) com até 3 retentativas automáticas em caso de falha de parse."
        ),
        "example": (
            "AgentBPMN lê a transcrição preprocessada, chama o DeepSeek com skill_bpmn.md "
            "e retorna um BPMNModel com steps, lanes, edges e gateways."
        ),
        "related": ["BaseAgent", "KnowledgeHub", "Orchestrator", "Skill"],
    },
    {
        "term": "AgentBMM",
        "en": "BMM Agent",
        "tag": "neg",
        "def_": (
            "Agente que extrai o modelo de motivação de negócio da transcrição no formato OMG BMM: "
            "<strong>Vision</strong> (onde queremos chegar), Mission, Goals (objetivos SMART), "
            "Strategies (como alcançar) e Policies (restrições que governam as estratégias)."
        ),
        "example": (
            "Da pauta 'reduzir tempo de onboarding de 30 para 15 dias', extrai "
            "Goal: 'Reduzir onboarding para 15 dias em Q3'."
        ),
        "related": ["BMM 1.3", "SBVR 1.5", "AgentSBVR"],
    },
    {
        "term": "AgentBPMN",
        "en": "BPMN Agent",
        "tag": "bpmn",
        "def_": (
            "Agente principal do pipeline. Extrai o processo de negócio da transcrição e gera o BPMNModel. "
            "Aplica <strong>_enforce_rules()</strong> (5 regras determinísticas) após a extração LLM "
            "e aciona bpmn_generator.py para gerar o XML."
        ),
        "example": (
            "Dado 'O analista envia o formulário para o gestor aprovar', extrai: "
            "lane=Analista → Task(Enviar Formulário), lane=Gestor → Task(Aprovar) com Gateway XOR."
        ),
        "related": ["BPMN 2.0", "Enforce Rules", "Torneio BPMN", "AgentValidator", "LangGraph"],
    },
    {
        "term": "AgentMinutes",
        "en": "Minutes Agent",
        "tag": "neg",
        "def_": (
            "Extrai a <strong>ata de reunião estruturada</strong> da transcrição: título, data, participantes, "
            "pauta, resumo por tópico, decisões, itens de ação e campos BABOK "
            "(suposições, riscos, dependências, stakeholder_needs)."
        ),
        "example": (
            "Da frase 'Pedro ficou responsável por entregar o relatório até sexta', extrai: "
            "action_item = {assignee: 'Pedro', task: 'Entregar relatório', deadline: 'sexta-feira'}."
        ),
        "related": ["BABOK v3", "MinutesModel", "Stakeholder"],
    },
    {
        "term": "AgentRequirements",
        "en": "Requirements Agent",
        "tag": "req",
        "def_": (
            "Extrai <strong>requisitos formais</strong> da transcrição seguindo IEEE 830. "
            "Cada requisito tem: REQ-ID, título, descrição, tipo (functional / non_functional / "
            "business_rule / constraint), prioridade, ator, source_quote e cited_by."
        ),
        "example": (
            "'O sistema deve processar em até 2 segundos' → REQ-002, tipo: non_functional, prioridade: Alta."
        ),
        "related": ["IEEE 830 / ISO 29148", "Rastreabilidade", "Reconciliação de Requisitos"],
    },
    {
        "term": "AgentSBVR",
        "en": "SBVR Agent",
        "tag": "neg",
        "def_": (
            "Extrai o vocabulário de negócio (BusinessTerms) e as <strong>regras de negócio</strong> "
            "(BusinessRules) da transcrição no formato OMG SBVR 1.5. "
            "Cada regra carrega esfera de negócio (sphere) e dono executivo (sphere_owner)."
        ),
        "example": (
            "'É obrigatório emitir fatura em até 3 dias úteis' → BusinessRule, "
            "tipo: Behavioral Rule, sphere: Financeiro, owner: CFO."
        ),
        "related": ["SBVR 1.5", "Regra de Negócio", "Esfera de Negócio"],
    },
    {
        "term": "AgentSynthesizer",
        "en": "Synthesizer Agent",
        "tag": "neg",
        "def_": (
            "Gera o <strong>Relatório Executivo</strong> HTML autocontido sintetizando todos os artefatos "
            "da reunião: sumário narrativo, análise do processo, insights, recomendações e tabelas. "
            "É invalidado automaticamente se o AgentBPMN for re-executado."
        ),
        "example": (
            "O relatório integra ata + requisitos + SBVR + BMM em um documento HTML de ~15 páginas, "
            "exportável como arquivo .html."
        ),
        "related": ["Relatório Executivo", "KnowledgeHub", "Sumário por Perspectiva"],
    },
    {
        "term": "AgentValidator",
        "en": "BPMN Validator",
        "tag": "bpmn",
        "def_": (
            "Avaliador <strong>Pure Python sem LLM</strong> que pontua candidatos BPMN em 4 dimensões: "
            "granularidade (0–10), diversidade de task_type (0–10), uso de gateways (0–10) "
            "e ausência de erros estruturais. Usado no Torneio BPMN para selecionar o melhor candidato."
        ),
        "example": (
            "Um diagrama com apenas User Tasks recebe nota baixa em task_type. "
            "Sem nenhum gateway, nota zero em gateways."
        ),
        "related": ["Torneio BPMN", "AgentBPMN", "Validação Estrutural BPMN"],
    },
    {
        "term": "ASR",
        "en": "Automatic Speech Recognition",
        "tag": "dev",
        "def_": (
            "Tecnologia de <strong>transcrição automática de fala para texto</strong>. "
            "Produz artefatos como repetições, hesitações ('ahn', 'é'), palavras cortadas "
            "e erros de homófonos que reduzem a qualidade da transcrição bruta."
        ),
        "example": (
            "'O o o sistema deve deve processar...' — o TranscriptPreprocessor remove "
            "duplicações e fillers antes do pipeline LLM."
        ),
        "related": ["Qualidade de Transcrição"],
    },
    {
        "term": "Assistente RAG",
        "en": "RAG Assistant",
        "tag": "ai",
        "def_": (
            "Página de QA conversacional com dois modos: <strong>Modo A (Tool-use)</strong> — LLM acessa "
            "dados via ferramentas estruturadas (até 8 rounds) — e Modo B (RAG Clássico) — "
            "busca semântica + keyword em Supabase. Modo Análise Autônoma executa até 15 rounds."
        ),
        "example": (
            "'Quais decisões foram tomadas na Reunião 3?' → Modo A: chama get_meeting_decisions(3) "
            "→ lista de decisões formatada."
        ),
        "related": ["RAG", "Tool-use", "Embedding"],
    },

    # ── B ─────────────────────────────────────────────────────────────────────

    {
        "term": "BABOK v3",
        "en": "Business Analysis Body of Knowledge",
        "tag": "neg",
        "def_": (
            "Guia publicado pelo IIBA com as melhores práticas de <strong>análise de negócios</strong>. "
            "Define técnicas de elicitação, documentação e validação de requisitos. "
            "Campos BABOK na ata: assumptions, open_questions, risks_identified, dependencies, stakeholder_needs."
        ),
        "example": (
            "O campo open_questions da ata captura perguntas sem resposta da reunião "
            "— rastreável para o próximo encontro via ReconciliaÇão de Requisitos."
        ),
        "related": ["Elicitação", "Stakeholder", "AgentMinutes"],
    },
    {
        "term": "BaseAgent",
        "en": "Base Agent",
        "tag": "ai",
        "def_": (
            "Classe abstrata base de todos os agentes do sistema. Fornece: "
            "<strong>_call_llm()</strong> com roteamento de provedor, sanitização PII, "
            "cache semântico, telemetria assíncrona, até 3 retentativas JSON e rastreamento de tokens."
        ),
        "example": (
            "AgentBPMN(BaseAgent) herda _call_with_retry() e _load_skill() — "
            "apenas implementa build_prompt() e run()."
        ),
        "related": ["Agente LLM", "Skill", "Semantic Cache", "LLM Telemetria"],
    },
    {
        "term": "BMM 1.3",
        "en": "Business Motivation Model",
        "tag": "neg",
        "def_": (
            "Padrão OMG que estrutura os elementos de motivação de negócio: "
            "<strong>Vision</strong> (onde queremos chegar), Mission (o que fazemos), "
            "Goals (objetivos SMART), Strategies (como alcançar) e Policies (restrições)."
        ),
        "example": (
            "Vision: 'Ser líder em automação de processos' → Mission: 'Digitalizamos reuniões' "
            "→ Goal: '100% das atas geradas em até 24h após a reunião'."
        ),
        "related": ["AgentBMM", "SBVR 1.5", "Regra de Negócio", "OMG"],
    },
    {
        "term": "BPMN 2.0",
        "en": "Business Process Model and Notation",
        "tag": "bpmn",
        "def_": (
            "Notação gráfica padronizada pela OMG (ISO/IEC 19510) para modelar processos de negócio. "
            "Usa elementos como <strong>Events, Tasks, Gateways e Pools/Lanes</strong>. "
            "O XML gerado é compatível com Camunda, Signavio, bpmn-js e qualquer ferramenta BPMN 2.0."
        ),
        "example": (
            "Pool 'Financeiro' com Lane 'Analista' → Task 'Lançar NF' → "
            "Gateway XOR 'Aprovado?' → Task 'Pagar' ou Task 'Devolver'."
        ),
        "related": ["Pool", "Lane", "Gateway", "Evento BPMN", "Tarefa BPMN", "bpmn-js", "AgentBPMN"],
    },
    {
        "term": "bpmn-js",
        "en": "bpmn-js",
        "tag": "dev",
        "def_": (
            "Biblioteca JavaScript da bpmn.io (Camunda) para <strong>renderização e edição de BPMN 2.0</strong> "
            "no browser. Versão 17 é injetada inline (server-side fetch + lru_cache) — "
            "sem dependência de CDN bloqueado pelo sandbox do Streamlit Cloud."
        ),
        "example": (
            "canvas.zoom('fit-viewport') é deferido via setTimeout(fn, 150) para evitar "
            "erros de SVGMatrix non-finite em container de dimensão zero."
        ),
        "related": ["BPMN 2.0", "Validação Estrutural BPMN"],
    },

    # ── C ─────────────────────────────────────────────────────────────────────

    {
        "term": "Cache Hit / Cache Miss",
        "en": "Cache Hit / Cache Miss",
        "tag": "ai",
        "def_": (
            "<strong>Hit</strong>: o hash calculado para a chamada já existe no cache LLM — a resposta "
            "salva é reaproveitada, <strong>nenhuma chamada de API acontece</strong> (custo real ≈ $0, "
            "só uma leitura no Supabase). <strong>Miss</strong>: hash não encontrado — a chamada segue "
            "normalmente ao provider, e a resposta é gravada no cache ao final para a próxima vez."
        ),
        "example": (
            "Reprocessar a mesma reunião sem mudar nada → todo agente bate em hit. "
            "Mudar uma frase da transcrição → hash muda → miss só naquele agente, os demais podem "
            "continuar batendo em hit se o texto que eles usam não mudou."
        ),
        "related": ["Semantic Cache", "Hash (SHA-256)", "LLM Telemetria"],
    },
    {
        "term": "CKF",
        "en": "Context Knowledge File",
        "tag": "neg",
        "def_": (
            "Arquivo de <strong>conhecimento acumulado</strong> sobre um projeto. "
            "Contém participantes recorrentes, termos do domínio, regras estabelecidas e objetivos. "
            "Injetado no system prompt dos agentes para contextualizar o processamento de cada nova reunião."
        ),
        "example": (
            "O CKF registra 'Pedro = Gerente de TI do TRF2' — assim o AgentBPMN usa "
            "'TI / TRF2' como lane name em vez do genérico 'Sistema'."
        ),
        "related": ["Prompt de Sistema", "KnowledgeHub"],
    },
    {
        "term": "Collaboration BPMN",
        "en": "BPMN Collaboration / Message Flow",
        "tag": "bpmn",
        "def_": (
            "Diagrama BPMN com <strong>múltiplos Pools</strong> (participantes distintos) conectados "
            "por Message Flows (setas tracejadas que representam troca de mensagens entre organizações). "
            "Diferente de um processo simples (único Pool com Lanes)."
        ),
        "example": (
            "Pool 'Empresa A' envia mensagem ao Pool 'Banco' via Message Flow — "
            "representa comunicação B2B entre organizações distintas."
        ),
        "related": ["Pool", "BPMN 2.0"],
    },
    {
        "term": "Context Analyzer",
        "en": "Context Analyzer",
        "tag": "ai",
        "def_": (
            "Serviço (services/context_analyzer.py) que detecta transcrições longas (>50k tokens) "
            "e <strong>ajusta automaticamente</strong> o comportamento dos agentes LONG_CONTEXT_AGENTS "
            "(bpmn, sbvr, bmm): aumenta max_tokens para 8192, timeout para 180s e injeta instrução no system prompt."
        ),
        "example": (
            "Uma transcrição de 6h de reunião dispara o modo long context, "
            "evitando truncamento silencioso no AgentBPMN."
        ),
        "related": ["BaseAgent", "Token", "LLM"],
    },
    {
        "term": "Camada de Conformidade LGPD",
        "en": "LGPD Compliance Layer",
        "tag": "seg",
        "def_": (
            "Módulo <strong>modules/compliance/</strong> introduzido no PC81 com três componentes: "
            "<strong>detector.py</strong> (classifica PII via regex + spaCy NER, sem anonimizar), "
            "<strong>consent.py</strong> (painel pós-pipeline para registro da base legal LGPD), "
            "<strong>audit.py</strong> (grava eventos na trilha compliance_audit de forma assíncrona). "
            "Integrada ao Pipeline: executa automaticamente após salvar cada reunião."
        ),
        "example": (
            "Ao processar reunião com CPF e e-mails, detector.py retorna risco=Alto. "
            "O painel 🔒 abre automaticamente e exige seleção de base legal (ex.: Legítimo Interesse Art. 7°, IX) "
            "antes de liberar as abas de resultados."
        ),
        "related": ["LGPD", "PII", "Sanitização de PII", "Trilha de Auditoria", "Consentimento de Dados"],
    },
    {
        "term": "Consentimento de Dados",
        "en": "Data Consent (LGPD)",
        "tag": "seg",
        "def_": (
            "Registro formal da <strong>base legal LGPD (Art. 7°)</strong> para tratamento dos dados "
            "pessoais de cada reunião. Salvo na tabela <code>compliance_consent</code> com: "
            "base legal (Legítimo Interesse / Consentimento / Contrato / Obrigação Legal), "
            "perfil dos participantes (interno / externo / misto), prazo de retenção (30–365 dias) "
            "e resumo do PII detectado. Exibido como painel 🔒 no Pipeline após salvar a reunião."
        ),
        "example": (
            "Reunião com parceiros externos → sistema alerta para uso de 'Consentimento Explícito (Art. 7°, I)' "
            "em vez de Legítimo Interesse. Operador registra base legal → evento 'consent_granted' gravado na auditoria."
        ),
        "related": ["LGPD", "Camada de Conformidade LGPD", "Trilha de Auditoria"],
    },

    # ── D ─────────────────────────────────────────────────────────────────────

    {
        "term": "DeepSeek V4 Flash",
        "en": "DeepSeek V4 Flash",
        "tag": "ai",
        "def_": (
            "Modelo LLM <strong>padrão</strong> do Process2Diagram. Contexto de 1M tokens, custo muito baixo. "
            "Identificador: deepseek-v4-flash. Provedor: openai_compatible. "
            "Variantes: V4 Pro (premium), V4 Flash Thinking (raciocínio estendido)."
        ),
        "example": (
            "Por padrão, todos os agentes usam DeepSeek V4 Flash. "
            "Para tarefas críticas, DeepSeek V4 Pro ou Claude (Anthropic) podem ser configurados."
        ),
        "related": ["LLM", "BaseAgent", "Thinking Mode"],
    },
    {
        "term": "DMN 1.4",
        "en": "Decision Model and Notation",
        "tag": "bpmn",
        "def_": (
            "Padrão OMG para modelar <strong>tabelas de decisão formais</strong>. "
            "Define Inputs (condições), Outputs (resultados), Rules (linhas) "
            "e Hit Policy (como múltiplas regras se aplicam: U=Unique, A=Any, F=First, C=Collect)."
        ),
        "example": (
            "Tabela 'Aprovação de Crédito': Input=Score, Input=Renda → Output=Decisão "
            "(Aprovado / Negado / Análise Manual)."
        ),
        "related": ["BPMN 2.0", "Regra de Negócio", "OMG"],
    },
    {
        "term": "Document Manager",
        "en": "Document Manager",
        "tag": "dev",
        "def_": (
            "Módulo de gestão de documentos com 5 abas: Enviar (upload .txt/.pdf/.docx), "
            "<strong>Biblioteca</strong> (busca semântica/keyword), Extrair Artefatos, "
            "Análise Cruzada (alinhamento doc × reunião) e Taxonomia (53 tipos / 9 categorias)."
        ),
        "example": (
            "Upload do 'Contrato de TI' → auto-embed (chunks 500/80 chars) → "
            "busca 'prazo de entrega' → 3 chunks semanticamente relevantes retornados."
        ),
        "related": ["Supabase", "Embedding", "RAG"],
    },

    # ── E ─────────────────────────────────────────────────────────────────────

    {
        "term": "Elicitação",
        "en": "Elicitation",
        "tag": "neg",
        "def_": (
            "Processo de descoberta e coleta de necessidades e requisitos de stakeholders. "
            "Técnicas clássicas: entrevistas, workshops, observação, análise de documentos. "
            "No Process2Diagram, a elicitação é <strong>automatizada via análise de transcrição</strong> pelo LLM."
        ),
        "example": (
            "O AgentRequirements 'elicita' requisitos ouvindo as falas da reunião — "
            "source_quote registra a frase motivadora exata."
        ),
        "related": ["BABOK v3", "Stakeholder", "AgentRequirements", "Rastreabilidade"],
    },
    {
        "term": "Embedding",
        "en": "Semantic Embedding",
        "tag": "ai",
        "def_": (
            "Representação numérica de texto em um espaço vetorial de <strong>alta dimensão (1536 dims)</strong>. "
            "Textos semanticamente similares têm vetores próximos (cosine similarity). "
            "Gerados pelo Google Gemini gemini-embedding-001 com output_dimensionality=1536."
        ),
        "example": (
            "'Prazo de entrega' e 'deadline' têm vetores similares → a busca semântica "
            "os conecta mesmo sem coincidência de palavras-chave."
        ),
        "related": ["pgvector", "RAG", "Supabase", "Gemini", "Fuzzy Matching", "Semantic Cache"],
    },
    {
        "term": "Enforce Rules",
        "en": "_enforce_rules()",
        "tag": "bpmn",
        "def_": (
            "Função do AgentBPMN aplicada após a extração LLM, <strong>antes dos geradores</strong>. "
            "Rule 0: remove Start/End declarados pelo LLM. Rule 1: serviceTask sem ator → lane=None. "
            "Rule 1b: inferência de nomes reais de lane. Rule 2: correction loop → gateway upstream."
        ),
        "example": (
            "LLM declara lane='Sistema' → Rule 1b detecta o nome real 'ERP SAP' "
            "a partir dos atores NLP e renomeia a lane automaticamente."
        ),
        "related": ["AgentBPMN", "BPMN 2.0", "Lane", "NLPChunker"],
    },
    {
        "term": "Esfera de Negócio",
        "en": "Business Sphere",
        "tag": "neg",
        "def_": (
            "Domínio organizacional ao qual uma regra de negócio pertence. "
            "Esferas suportadas: <strong>Marketing (CMO), Financeiro (CFO), RH (CHRO), "
            "Operações (COO), Jurídico (CLO), Tecnologia (CTO), Geral (CEO)</strong>."
        ),
        "example": (
            "Regra 'Fatura emitida em até 3 dias' → sphere: Financeiro, owner: CFO. "
            "Permite agrupar regras por área e identificar o responsável executivo."
        ),
        "related": ["SBVR 1.5", "Regra de Negócio", "AgentSBVR"],
    },
    {
        "term": "Evento BPMN",
        "en": "BPMN Event",
        "tag": "bpmn",
        "def_": (
            "Ocorrência que afeta o fluxo do processo. Tipos: <strong>Start Event</strong> (inicia), "
            "<strong>End Event</strong> (encerra), Intermediate Event (ocorre durante — timer, mensagem, erro). "
            "O gerador BPMN adiciona Start/End automaticamente — a LLM não deve declará-los (Rule 0)."
        ),
        "example": (
            "Link Intermediate Event: conecta fluxos que cruzam 2+ fronteiras de Lane "
            "sem criar setas longas e diagonais. Throw lança; Catch recebe."
        ),
        "related": ["BPMN 2.0", "Link Intermediate Event", "AgentBPMN", "Enforce Rules"],
    },

    # ── F ─────────────────────────────────────────────────────────────────────

    {
        "term": "Fuzzy Matching",
        "en": "Fuzzy / Similarity Matching",
        "tag": "ai",
        "def_": (
            "Correspondência <strong>aproximada</strong> entre dois textos, baseada em distância vetorial "
            "de embedding (ex.: similaridade de cosseno ≥ threshold) em vez de igualdade exata. "
            "É a técnica por trás de um cache semântico \"de verdade\" — mas o P2D "
            "<strong>avaliou e optou por não usá-la</strong> no cache LLM (PC185): exigiria uma chamada de "
            "embedding extra em toda consulta (hit ou miss) e, para artefatos de negócio (BPMN, ata), "
            "um falso positivo entregaria o resultado de uma transcrição diferente ao usuário."
        ),
        "example": (
            "Cache exato: 'Aprovar o pedido' e 'Aprovar  o  pedido' (espaço extra) → mesmo hash após "
            "normalização, hit. Fuzzy matching: 'Aprovar o pedido' e 'Autorizar a solicitação' → embeddings "
            "próximos, hit por similaridade — é justamente esse tipo de hit que o P2D evita."
        ),
        "related": ["Semantic Cache", "Embedding", "Cache Hit / Cache Miss"],
    },

    # ── G ─────────────────────────────────────────────────────────────────────

    {
        "term": "Gateway",
        "en": "Gateway",
        "tag": "bpmn",
        "def_": (
            "Elemento BPMN que controla divergência e convergência de fluxos. "
            "Tipos: <strong>XOR</strong> (exclusivo — uma saída), "
            "<strong>AND/Paralelo</strong> (todos os caminhos simultâneos), OR (inclusivo — um ou mais)."
        ),
        "example": (
            "'Se aprovado, segue para pagamento; se não, volta para revisão' "
            "→ Gateway XOR com 2 saídas condicionais."
        ),
        "related": ["BPMN 2.0", "AgentBPMN", "AgentValidator"],
    },
    {
        "term": "Gemini",
        "en": "Google Gemini",
        "tag": "ai",
        "def_": (
            "Família de LLMs da Google. No Process2Diagram: provedor de <strong>embeddings</strong> "
            "(gemini-embedding-001, 1536 dims, saída configurável via output_dimensionality) "
            "e provedor LLM opcional (gemini-2.0-flash). Tier gratuito: rate limit de 100 req/min."
        ),
        "example": (
            "embed_text('Aprovação de fatura') → vetor de 1536 floats via API Gemini Embedding. "
            "Rate limit: 1.2s delay entre chamadas + 5 retries em 429."
        ),
        "related": ["Embedding", "LLM", "pgvector"],
    },
    {
        "term": "Google Calendar API",
        "en": "Google Calendar API v3",
        "tag": "dev",
        "def_": (
            "API REST do Google para criar, listar, atualizar e excluir eventos em agendas. "
            "Autenticação via <strong>Service Account</strong> (JSON de credenciais). "
            "O calendar_client.py expõe 8 funções. Credenciais em st.secrets['google_calendar']."
        ),
        "example": (
            "O Assistente pode agendar itens de ação da reunião via tool-use: "
            "calendar_create_event('Revisão de Requisitos', '2026-06-01T10:00:00', ...)."
        ),
        "related": ["Assistente RAG", "Tool-use"],
    },

    # ── H ─────────────────────────────────────────────────────────────────────

    {
        "term": "Hash (SHA-256)",
        "en": "Hash (SHA-256)",
        "tag": "dev",
        "def_": (
            "Função que transforma um texto de tamanho qualquer numa <strong>impressão digital</strong> "
            "de tamanho fixo (64 caracteres hexadecimais) — o mesmo texto sempre produz o mesmo hash, "
            "e qualquer mudança de conteúdo produz um hash completamente diferente (sem meio-termo). "
            "É a chave do cache LLM: <code>SHA256(provedor | modelo | system_prompt | user_prompt)</code>."
        ),
        "example": (
            "compute_hash('DeepSeek', 'deepseek-v4-flash', system, prompt) → "
            "'a3f9...'(64 chars). Mudar um único caractere do prompt produz um hash totalmente diferente."
        ),
        "related": ["Semantic Cache", "Cache Hit / Cache Miss", "Fuzzy Matching"],
    },

    # ── I ─────────────────────────────────────────────────────────────────────

    {
        "term": "IBIS",
        "en": "Issue-Based Information System",
        "tag": "neg",
        "def_": (
            "Framework para captura de raciocínio deliberativo (Rittel & Webber, 1973). "
            "Estrutura: <strong>Issues</strong> (questões), Positions (alternativas) "
            "e Arguments (Pros/Cons). Cada questão tem uma resolução: decidida / adiada / pendente."
        ),
        "example": (
            "Issue: 'Qual banco de dados usar?' → Position A: 'PostgreSQL' "
            "(Pro: open-source, Con: setup), Position B: 'MongoDB'. Resolução: decidida → PostgreSQL."
        ),
        "related": ["Regra de Negócio", "DMN 1.4"],
    },
    {
        "term": "IEEE 830 / ISO 29148",
        "en": "IEEE 830 / ISO/IEC/IEEE 29148:2018",
        "tag": "req",
        "def_": (
            "IEEE 830-1998 (substituído pela ISO/IEC/IEEE 29148:2018). "
            "Padrão para <strong>Especificação de Requisitos de Software</strong>. "
            "Define: completude, consistência, verificabilidade, rastreabilidade e não-ambiguidade."
        ),
        "example": (
            "Cada requisito do AgentRequirements tem ID único, título, descrição, "
            "tipo, prioridade, ator e source_quote — estrutura compatível com IEEE 830."
        ),
        "related": ["Requisito Funcional", "Requisito Não-Funcional", "Rastreabilidade", "AgentRequirements"],
    },

    # ── J ─────────────────────────────────────────────────────────────────────

    {
        "term": "JSON Retry",
        "en": "JSON Retry",
        "tag": "ai",
        "def_": (
            "Mecanismo do BaseAgent que tenta até <strong>3 vezes</strong> obter um JSON válido do LLM. "
            "Na primeira falha, adiciona instrução de correção ao prompt e reenviar. "
            "Essencial para modelos que retornam texto explicativo em vez de JSON puro."
        ),
        "example": (
            "Se o LLM retorna 'Aqui está o JSON: {...}', o retry extrai o bloco JSON do texto "
            "e tenta parse. Se falhar 3x, o agente lança exceção e o pipeline falha com mensagem clara."
        ),
        "related": ["BaseAgent", "LLM", "Agente LLM"],
    },

    # ── K ─────────────────────────────────────────────────────────────────────

    {
        "term": "KnowledgeGraph",
        "en": "Knowledge Graph",
        "tag": "dev",
        "def_": (
            "Grafo de entidades e fatos extraídos das reuniões de um projeto. "
            "Nós = entidades (pessoas, processos, sistemas, conceitos). "
            "Arestas = relações/fatos. Nós ⚠ = <strong>contradições</strong> detectadas entre reuniões. "
            "Visualizado via pyvis/vis-network (Obsidian-like)."
        ),
        "example": (
            "Entidade 'Pedro' conectada a fato 'é responsável por' → 'Módulo de Pagamento' (Reunião 3). "
            "Tabelas Supabase: kh_entities, kh_facts, kh_contradictions."
        ),
        "related": ["KnowledgeHub", "Supabase", "Reconciliação de Requisitos"],
    },
    {
        "term": "KnowledgeHub",
        "en": "Knowledge Hub",
        "tag": "dev",
        "def_": (
            "Dataclass central que representa o <strong>estado completo de uma sessão</strong>. "
            "Contém todos os artefatos: BPMN, ata, requisitos, SBVR, BMM, DMN, IBIS, qualidade, metadados. "
            "Persistido em st.session_state['hub']. Versionado via hub.bump()."
        ),
        "example": (
            "hub.bpmn.steps → passos extraídos; hub.meta.total_tokens_used → consumo total; "
            "hub.to_json() → serialização para persistência no Supabase."
        ),
        "related": ["Agente LLM", "Orchestrator", "st.session_state"],
    },
    {
        "term": "KPI",
        "en": "Key Performance Indicator",
        "tag": "neg",
        "def_": (
            "Métrica quantitativa para avaliar progresso em relação a objetivos estratégicos. "
            "Deve ser <strong>SMART</strong>: Específico, Mensurável, Atingível, Relevante, Temporal. "
            "No Process2Diagram, os KPIs do ROI-TR medem qualidade por tipo de reunião."
        ),
        "example": (
            "KPI: '80% das reuniões com ata gerada em até 5 minutos após encerramento'. "
            "Monitorado no dashboard Qualidade ROI-TR."
        ),
        "related": ["ROI-TR", "BMM 1.3"],
    },

    # ── L ─────────────────────────────────────────────────────────────────────

    {
        "term": "Lane",
        "en": "Swimlane",
        "tag": "bpmn",
        "def_": (
            "Subdivisão horizontal ou vertical dentro de um Pool BPMN. "
            "Representa um papel, departamento ou sistema responsável pelas tarefas contidas nela. "
            "<strong>Nomes devem ser unidades organizacionais reais</strong>, nunca genéricos."
        ),
        "example": (
            "Correto: 'Financeiro / TRF2', 'Analista de Contratos'. "
            "Errado: 'Usuário', 'Sistema', 'Validador' — corrigidos pela Rule 1b do Enforce Rules."
        ),
        "related": ["Pool", "BPMN 2.0", "Enforce Rules", "AgentBPMN"],
    },
    {
        "term": "LangGraph",
        "en": "LangGraph",
        "tag": "ai",
        "def_": (
            "Biblioteca para orquestrar agentes LLM como <strong>grafos de estado cíclicos</strong>. "
            "Permite ciclos condicionais (retry se qualidade baixa). "
            "No Process2Diagram: LGBPMNRunner usa LangGraph para retry adaptativo do BPMN até score ≥ 6.0."
        ),
        "example": (
            "AgentBPMN gera diagrama → AgentValidator pontua → "
            "se score < 6.0 e tentativas < 3 → retry com feedback dos erros específicos."
        ),
        "related": ["AgentBPMN", "AgentValidator", "Torneio BPMN"],
    },
    {
        "term": "LGPD",
        "en": "Lei Geral de Proteção de Dados (Lei 13.709/2018)",
        "tag": "seg",
        "def_": (
            "Lei brasileira de proteção de dados pessoais. O P2D implementa conformidade em <strong>6 camadas</strong>: "
            "C1 sanitização PII (pii_sanitizer.py), C2 conformidade LGPD (modules/compliance/), "
            "C3 autenticação SHA-256, C4 API keys em sessão, C5 dados em trânsito TLS, C6 Supabase RLS. "
            "Bases legais suportadas (Art. 7°): Legítimo Interesse (IX), Consentimento (I), Contrato (V), Obrigação Legal (II)."
        ),
        "example": (
            "Pipeline salva reunião → detector.py classifica PII → painel 🔒 exige base legal "
            "→ consentimento gravado em compliance_consent → evento auditado em compliance_audit."
        ),
        "related": ["PII", "Sanitização de PII", "Camada de Conformidade LGPD", "Consentimento de Dados", "Trilha de Auditoria", "Segurança"],
    },
    {
        "term": "Link Intermediate Event",
        "en": "Link Intermediate Event",
        "tag": "bpmn",
        "def_": (
            "Evento BPMN para conectar fluxos que cruzam fronteiras de Lane "
            "sem setas longas e diagonais. Um <strong>Throw</strong> lança o link; um <strong>Catch</strong> recebe. "
            "Injetado automaticamente pelo bpmn_generator.py — a LLM nunca deve declará-los."
        ),
        "example": (
            "Fluxo cruza 3 lanes → bpmn_generator detecta ≥ 2 fronteiras → "
            "insere Throw Link na Lane de origem e Catch Link na Lane de destino."
        ),
        "related": ["BPMN 2.0", "Evento BPMN", "AgentBPMN"],
    },
    {
        "term": "LLM",
        "en": "Large Language Model",
        "tag": "ai",
        "def_": (
            "Modelo de linguagem de grande escala treinado em vastos corpus textuais. "
            "O Process2Diagram é <strong>agnóstico de provedor</strong>: qualquer LLM configurado "
            "em AVAILABLE_PROVIDERS pode ser usado. Roteamento em BaseAgent._call_llm()."
        ),
        "example": (
            "Provedores disponíveis: DeepSeek (padrão), Claude (Anthropic), OpenAI, "
            "Groq/Llama, Gemini, Grok/xAI. Todos mapeados via client_type."
        ),
        "related": ["BaseAgent", "DeepSeek V4 Flash", "Prompt de Sistema", "Token"],
    },
    {
        "term": "LLM Telemetria",
        "en": "LLM Telemetry",
        "tag": "ai",
        "def_": (
            "Sistema de rastreamento passivo de todas as chamadas LLM reais (exceto cache hits). "
            "Registra: agente, provedor, modelo, <strong>latência_ms, tokens</strong>, long_context, erros. "
            "Escritas assíncronas via daemon thread — nunca bloqueiam o pipeline."
        ),
        "example": (
            "Página LLM Benchmark analisa telemetria real: latência P5/P25/P75/P95 por agente, "
            "throughput (tokens/s), heatmap agente × provedor."
        ),
        "related": ["BaseAgent", "Semantic Cache", "LLM"],
    },

    # ── M ─────────────────────────────────────────────────────────────────────

    {
        "term": "Mermaid",
        "en": "Mermaid",
        "tag": "bpmn",
        "def_": (
            "Linguagem de marcação textual para diagramas (flowcharts, sequência, Gantt). "
            "Sintaxe: <strong>flowchart LR</strong>, nós [] tarefas e {} decisões, "
            "arestas -->|label|. Versão 10. Renderização via mermaid.ink (server-side SVG)."
        ),
        "example": (
            "'A[Receber Pedido] --> B{Estoque?}' → renderiza nó retangular A "
            "conectado a losango de decisão B. Nós reservados (END, START) devem ser evitados."
        ),
        "related": ["mermaid.ink", "BPMN 2.0"],
    },
    {
        "term": "mermaid.ink",
        "en": "mermaid.ink",
        "tag": "dev",
        "def_": (
            "Serviço web que converte código Mermaid em SVG via endpoint REST. "
            "O Process2Diagram faz <strong>fetch server-side</strong> (Python, não no browser) "
            "para contornar o sandbox do Streamlit Cloud que bloqueia scripts externos em components.html."
        ),
        "example": (
            "GET mermaid.ink/svg/<base64> → SVG inline injetado no HTML. "
            "Suporta orientação TD/LR com toggle client-side via JavaScript."
        ),
        "related": ["Mermaid", "Streamlit"],
    },
    {
        "term": "MinutesModel",
        "en": "Minutes Model",
        "tag": "neg",
        "def_": (
            "Dataclass que representa a <strong>ata de reunião estruturada</strong>. "
            "Campos: title, date, participants, agenda_items, summary_by_topic, decisions, "
            "action_items, assumptions, open_questions, risks_identified, dependencies, stakeholder_needs."
        ),
        "example": (
            "hub.minutes.decisions[0] → {description: 'Adotar Supabase como banco de dados', "
            "owner: 'Pedro'}. Exportável como Word (.docx) e PDF."
        ),
        "related": ["AgentMinutes", "BABOK v3", "KnowledgeHub"],
    },

    # ── N ─────────────────────────────────────────────────────────────────────

    {
        "term": "NER",
        "en": "Named Entity Recognition",
        "tag": "ai",
        "def_": (
            "Tarefa de NLP que <strong>identifica e classifica entidades nomeadas</strong> em texto: "
            "pessoas (PER), organizações (ORG), locais (LOC), datas (DATE), etc. "
            "O NLPChunker usa NER para extrair os atores da reunião, usados nas lanes do BPMN."
        ),
        "example": (
            "'Pedro (TRF2) vai até Brasília na quinta' → PER=Pedro, ORG=TRF2, "
            "LOC=Brasília, DATE=quinta. Resultado alimenta Enforce Rules Rule 1b."
        ),
        "related": ["NLPChunker", "spaCy", "Lane", "AgentBPMN"],
    },
    {
        "term": "NLPChunker",
        "en": "NLP Chunker",
        "tag": "ai",
        "def_": (
            "Componente <strong>Pure Python sem LLM</strong> que usa spaCy pt_core_news_lg para: "
            "NER (extração de atores), segmentação da transcrição em blocos temáticos "
            "e detecção de mudanças de assunto. Roda antes de todos os agentes LLM."
        ),
        "example": (
            "Transcrição de 3.000 palavras → NLPChunker segmenta em 8 chunks por tema, "
            "identifica 5 atores (Pedro, Maria, TRF2, STJ, Governa)."
        ),
        "related": ["spaCy", "NER", "AgentBPMN", "KnowledgeHub"],
    },

    # ── O ─────────────────────────────────────────────────────────────────────

    {
        "term": "OMG",
        "en": "Object Management Group",
        "tag": "neg",
        "def_": (
            "Consórcio internacional de padronização de tecnologias orientadas a objetos e modelagem. "
            "Responsável pelos padrões <strong>BPMN 2.0, DMN 1.4, SBVR 1.5, BMM 1.3</strong>, "
            "UML 2.5, MOF e outros usados no Process2Diagram."
        ),
        "example": (
            "O XML BPMN gerado pelo Process2Diagram é válido contra o schema XSD "
            "da especificação OMG formal/2013-12-09 (ISO/IEC 19510:2013)."
        ),
        "related": ["BPMN 2.0", "DMN 1.4", "SBVR 1.5", "BMM 1.3"],
    },
    {
        "term": "Orchestrator",
        "en": "Orchestrator",
        "tag": "ai",
        "def_": (
            "Componente (agents/orchestrator.py) que sequencia todos os agentes do pipeline. "
            "AgentMinutes e AgentRequirements rodam em <strong>paralelo via ThreadPoolExecutor</strong> "
            "(max_workers=2). Tokens dos workers são mesclados no hub principal após o join."
        ),
        "example": (
            "Paralelismo: enquanto AgentMinutes extrai a ata, AgentRequirements extrai requisitos "
            "— economizando ~40% do tempo total do pipeline."
        ),
        "related": ["Agente LLM", "KnowledgeHub", "Pipeline de Agentes", "BaseAgent"],
    },

    # ── P ─────────────────────────────────────────────────────────────────────

    {
        "term": "pgvector",
        "en": "pgvector",
        "tag": "dev",
        "def_": (
            "Extensão PostgreSQL para armazenamento e busca de vetores de alta dimensão. "
            "Suporta índices <strong>ivfflat</strong> (limite: 2.000 dims) e HNSW. "
            "Operações: cosine, L2, inner product. Dimensão configurada: 1536 (compatível com ivfflat)."
        ),
        "example": (
            "match_transcript_chunks(query_embedding, 0.7, 5) → retorna os 5 chunks "
            "semanticamente mais similares à query via cosine similarity."
        ),
        "related": ["Supabase", "Embedding", "RAG"],
    },
    {
        "term": "PII",
        "en": "Personally Identifiable Information",
        "tag": "dev",
        "def_": (
            "Informação que pode identificar um indivíduo: CPF, CNPJ, e-mail, telefone, valores monetários. "
            "O <strong>pii_sanitizer.py</strong> substitui PIIs por tokens antes de enviar ao LLM "
            "e restaura os tokens originais na resposta (sanitize → API → desanitize)."
        ),
        "example": (
            "'e-mail pedro@empresa.com' → [PII_EMAIL_1] enviado ao LLM → restaurado na resposta final. "
            "Exigência da LGPD (Lei 13.709/2018)."
        ),
        "related": ["LGPD", "BaseAgent", "Segurança"],
    },
    {
        "term": "Pipeline de Agentes",
        "en": "Agent Pipeline",
        "tag": "ai",
        "def_": (
            "Sequência orquestrada de agentes LLM que transforma uma transcrição bruta em artefatos. "
            "Etapas: Qualidade → Preprocessamento → NLP → <strong>BPMN → SBVR → "
            "Minutes ‖ Requirements → BMM → DMN → IBIS → Sintetizador → Sumário</strong>."
        ),
        "example": (
            "run_pipeline(hub, config, callback) → executa o pipeline completo. "
            "3 modos: Torneio BPMN (N runs), LangGraph Adaptive Retry, Standard."
        ),
        "related": ["Orchestrator", "KnowledgeHub", "BaseAgent", "Torneio BPMN"],
    },
    {
        "term": "Pool",
        "en": "Pool",
        "tag": "bpmn",
        "def_": (
            "Contêiner BPMN que representa um <strong>participante ou organização</strong> em um processo. "
            "Cada Pool pode conter Lanes que subdividem os responsáveis internos. "
            "Em diagramas Collaboration, múltiplos Pools se comunicam via Message Flows."
        ),
        "example": (
            "Pool 'TRF2' com Lanes 'Financeiro' e 'Operações'; Pool 'Banco' separado com Lane 'Compensação'."
        ),
        "related": ["Lane", "BPMN 2.0", "Collaboration BPMN"],
    },
    {
        "term": "Prompt de Sistema",
        "en": "System Prompt / Skill",
        "tag": "ai",
        "def_": (
            "Instrução de comportamento passada ao LLM antes da mensagem do usuário. "
            "Define papel, formato de saída (JSON schema) e restrições. "
            "Carregado de <strong>skills/*.md</strong> via _load_skill() — "
            "path absoluto, case-sensitive no Linux/Streamlit Cloud."
        ),
        "example": (
            "skills/skill_bpmn.md define o papel do AgentBPMN, o JSON schema esperado "
            "e as 5 regras que a LLM deve seguir para produzir diagramas válidos."
        ),
        "related": ["BaseAgent", "Agente LLM", "Skill"],
    },

    # ── Q ─────────────────────────────────────────────────────────────────────

    {
        "term": "Qualidade de Transcrição",
        "en": "Transcript Quality",
        "tag": "neg",
        "def_": (
            "Avaliação da qualidade da transcrição em graus <strong>A–E</strong> "
            "pelo AgentTranscriptQuality. Critérios: cobertura de decisões, clareza de responsáveis, "
            "identificabilidade dos processos, completude da pauta. Não-fatal se o agente falhar."
        ),
        "example": (
            "Grau A: transcrição clara com nomes, decisões e ações identificadas. "
            "Grau E: fala confusa, muitas hesitações, sem contexto organizacional discernível."
        ),
        "related": ["ASR"],
    },

    # ── R ─────────────────────────────────────────────────────────────────────

    {
        "term": "RAG",
        "en": "Retrieval-Augmented Generation",
        "tag": "ai",
        "def_": (
            "Técnica que combina busca de documentos relevantes (retrieval) com geração de resposta "
            "pelo LLM, <strong>reduzindo alucinações</strong>. O Assistente opera em Modo B "
            "(RAG Clássico) via busca semântica + keyword em Supabase."
        ),
        "example": (
            "'Qual foi a decisão sobre o banco de dados?' → busca semântica encontra chunk da Reunião 3 "
            "→ LLM formula resposta baseada no trecho recuperado."
        ),
        "related": ["Embedding", "pgvector", "Supabase", "Assistente RAG"],
    },
    {
        "term": "Rastreabilidade",
        "en": "Traceability",
        "tag": "req",
        "def_": (
            "Capacidade de rastrear um requisito desde sua <strong>origem</strong> (fala na reunião) "
            "até sua implementação. source_quote registra a frase motivadora; cited_by o autor; "
            "business_rule_refs liga o requisito à regra SBVR que o originou."
        ),
        "example": (
            "REQ-005.source_quote = 'O sistema deve avisar o gestor em até 1 hora' "
            "(Pedro, Reunião 4). REQ-005.cited_by = 'Pedro Regato'."
        ),
        "related": ["IEEE 830 / ISO 29148", "AgentRequirements", "Requisito Funcional"],
    },
    {
        "term": "Reconciliação de Requisitos",
        "en": "Requirements Reconciliation",
        "tag": "req",
        "def_": (
            "Processo de comparar requisitos de uma nova reunião com os já armazenados no projeto, "
            "identificando: <strong>novidades, revisões, confirmações e contradições</strong>. "
            "Executado pelo AgentReqReconciler ao final do pipeline quando Supabase está configurado."
        ),
        "example": (
            "REQ-003 da Reunião 1 (prazo 30 dias) vs REQ-003 da Reunião 4 (prazo 15 dias) "
            "→ Status: revised + contradiction flag no KnowledgeGraph."
        ),
        "related": ["AgentRequirements", "Rastreabilidade", "KnowledgeGraph"],
    },
    {
        "term": "Regra de Negócio",
        "en": "Business Rule",
        "tag": "neg",
        "def_": (
            "Diretiva declarativa que governa o comportamento de um processo. "
            "Em SBVR: <strong>fato estrutural</strong> ('A fatura tem prazo de pagamento') "
            "ou <strong>restrição operacional</strong> ('É obrigatório emitir fatura em até 3 dias'). "
            "Rastreável via business_rule_refs nos requisitos."
        ),
        "example": (
            "'É necessário que todo contrato seja assinado por dois aprovadores' "
            "→ BusinessRule, tipo: Necessity, sphere: Jurídico, owner: CLO."
        ),
        "related": ["SBVR 1.5", "Esfera de Negócio", "AgentSBVR", "Rastreabilidade"],
    },
    {
        "term": "Relatório Executivo",
        "en": "Executive Report",
        "tag": "neg",
        "def_": (
            "HTML autocontido gerado pelo AgentSynthesizer que <strong>sintetiza todos os artefatos</strong> "
            "da reunião: sumário narrativo, análise do processo, insights, recomendações "
            "e tabelas de requisitos e decisões. Exportável como arquivo .html."
        ),
        "example": (
            "Um relatório de ~15 páginas integrando ata + requisitos + SBVR + BMM "
            "para apresentação ao board — com gráficos e tabelas inline."
        ),
        "related": ["AgentSynthesizer", "KnowledgeHub", "Sumário por Perspectiva"],
    },
    {
        "term": "Requisito Funcional",
        "en": "Functional Requirement",
        "tag": "req",
        "def_": (
            "Descreve uma <strong>função, comportamento ou serviço</strong> que o sistema deve fornecer. "
            "Responde à pergunta: 'O que o sistema deve fazer?' "
            "Tipo functional no AgentRequirements. Abreviação: RF."
        ),
        "example": (
            "'O sistema deve autenticar o usuário via SSO corporativo' "
            "→ RF-001, prioridade: Alta, ator: Usuário Final."
        ),
        "related": ["IEEE 830 / ISO 29148", "Requisito Não-Funcional", "AgentRequirements", "Rastreabilidade"],
    },
    {
        "term": "Requisito Não-Funcional",
        "en": "Non-Functional Requirement",
        "tag": "req",
        "def_": (
            "Restrição ou <strong>atributo de qualidade</strong> que o sistema deve satisfazer: "
            "desempenho, segurança, usabilidade, disponibilidade, escalabilidade. "
            "Tipo non_functional no AgentRequirements. Abreviação: RNF."
        ),
        "example": (
            "'O sistema deve responder em até 2 segundos para 95% das requisições' "
            "→ RNF-003, prioridade: Alta, ator: Equipe de TI."
        ),
        "related": ["IEEE 830 / ISO 29148", "Requisito Funcional", "KPI"],
    },
    {
        "term": "RLS",
        "en": "Row Level Security",
        "tag": "dev",
        "def_": (
            "Mecanismo do PostgreSQL que restringe acesso a linhas de uma tabela com base em políticas. "
            "Habilitado em <strong>todas as tabelas do Supabase</strong> — "
            "dados de um projeto não vazam para outro, mesmo via SQL direto."
        ),
        "example": (
            "POLICY 'users see own project' ON meetings "
            "USING (project_id = current_project_id())."
        ),
        "related": ["Supabase", "pgvector", "Segurança"],
    },
    {
        "term": "ROI-TR",
        "en": "Return on Investment from Transcription",
        "tag": "neg",
        "def_": (
            "Métrica proprietária que avalia o <strong>valor gerado</strong> pelo processamento de uma reunião. "
            "Considera 11 tipos de reunião com matrizes de pesos distintas para 5 dimensões "
            "(req, dec, act, sbvr, bpmn). Calculado em modules/meeting_roi_calculator.py."
        ),
        "example": (
            "Reunião de 'Planejamento' tem peso alto em requisitos; "
            "'Sprint Review' tem peso alto em decisões e itens de ação."
        ),
        "related": ["KPI", "Qualidade de Transcrição", "KnowledgeHub"],
    },

    # ── S ─────────────────────────────────────────────────────────────────────

    {
        "term": "SBVR 1.5",
        "en": "Semantics of Business Vocabulary and Rules",
        "tag": "neg",
        "def_": (
            "Padrão OMG para formalizar <strong>vocabulário e regras de negócio</strong> "
            "em linguagem natural estruturada. Separa BusinessTerms (vocabulário) "
            "de BusinessRules (restrições operacionais). Esfera e dono executivo por regra."
        ),
        "example": (
            "BusinessTerm: 'Nota Fiscal' — BusinessRule: 'É necessário que toda "
            "Nota Fiscal tenha CFOP antes de ser emitida'."
        ),
        "related": ["AgentSBVR", "Regra de Negócio", "Esfera de Negócio", "BMM 1.3"],
    },
    {
        "term": "Sanitização de PII",
        "en": "PII Sanitization",
        "tag": "seg",
        "def_": (
            "Substituição reversível de dados pessoais estruturados por tokens opacos antes de cada chamada LLM. "
            "Implementada em <strong>modules/pii_sanitizer.py</strong>. "
            "Dados substituídos: CPF (@CPF_001), CNPJ (@CNPJ_001), e-mail (@EMAIL_001), "
            "telefone (@TEL_001), valores monetários R$ (@VALOR_001). "
            "Nomes de pessoas <em>não são substituídos</em> — necessários para lanes BPMN, atas e IBIS. "
            "A restauração ocorre localmente após o retorno do LLM (desanitize)."
        ),
        "example": (
            "'Contato: joao@empresa.com · CPF 123.456.789-00' → "
            "'Contato: @EMAIL_001 · CPF @CPF_001' enviado ao LLM → "
            "resposta recebida com tokens → restaurada antes de exibir ao usuário."
        ),
        "related": ["PII", "LGPD", "Camada de Conformidade LGPD", "BaseAgent"],
    },
    {
        "term": "Segurança",
        "en": "Security Model",
        "tag": "seg",
        "def_": (
            "Arquitetura de segurança multicamada do P2D — <strong>6 camadas</strong>: "
            "C1 Sanitização PII (pii_sanitizer.py), "
            "C2 Conformidade LGPD (modules/compliance/), "
            "C3 Autenticação SHA-256 com perfis master/admin/user, "
            "C4 API Keys exclusivamente em st.session_state (nunca em disco), "
            "C5 Dados em trânsito TLS para provedores LLM, "
            "C6 Supabase RLS + criptografia AES-256 em repouso. "
            "Documentada em <strong>páginas/Segurança de Dados</strong> (menu Início)."
        ),
        "example": (
            "USUARIOS = {'pedro': {'hash': sha256('senha'), 'role': 'master'}} — "
            "roles: master > admin > user. is_admin() retorna True para admin e master."
        ),
        "related": ["PII", "Sanitização de PII", "LGPD", "Camada de Conformidade LGPD", "RLS", "Supabase"],
    },
    {
        "term": "Semantic Cache",
        "en": "Semantic Cache (Cache LLM)",
        "tag": "ai",
        "def_": (
            "Cache de respostas LLM do Process2Diagram. Apesar do nome (herdado do módulo, "
            "<code>services/semantic_cache.py</code>), a implementação é <strong>hash exato SHA-256</strong> "
            "(provedor + modelo + prompt) — não similaridade de embedding (ver Fuzzy Matching). "
            "Desde o PC185, o texto é normalizado (espaços/quebras de linha colapsados) antes do hash, "
            "então só diferenças de formatação reaproveitam a mesma entrada — qualquer mudança real de "
            "conteúdo gera um hash novo. Em hit, aplica o token_map da sessão atual (PII-safe). "
            "hub.meta.cache_hits rastreia acertos por sessão; estatísticas reais em Qualidade ROI-TR → 💾 Cache LLM."
        ),
        "example": (
            "Segunda execução da mesma transcrição no mesmo agente → "
            "resposta do cache em <100ms (leitura Supabase) vs ~5s da API real — custo dessa chamada ≈ $0."
        ),
        "related": ["BaseAgent", "LLM", "Supabase", "Cache Hit / Cache Miss", "Fuzzy Matching", "Hash (SHA-256)"],
    },
    {
        "term": "Skill",
        "en": "Agent Skill",
        "tag": "ai",
        "def_": (
            "Arquivo Markdown (skills/*.md) que define o <strong>system prompt</strong> de um agente. "
            "Carregado via _load_skill() com path absoluto — case-sensitive no Linux/Streamlit Cloud. "
            "Nome do arquivo deve ser verificado com 'git ls-files skills/' antes de commitar."
        ),
        "example": (
            "skills/skill_bpmn.md (lowercase) é o prompt do AgentBPMN. "
            "SKILL_REQUIREMENTS.md (uppercase) é outro — git ls-files revela o nome exato."
        ),
        "related": ["Prompt de Sistema", "BaseAgent", "Agente LLM"],
    },
    {
        "term": "spaCy",
        "en": "spaCy",
        "tag": "ai",
        "def_": (
            "Biblioteca Python de NLP de alta performance. Suporta NER, POS tagging, "
            "dependency parsing, segmentação. Modelo: <strong>pt_core_news_lg</strong> "
            "(corpus jornalístico PT). Roda antes de qualquer chamada LLM — custo zero de API."
        ),
        "example": (
            "nlp('Pedro vai ao TRF2 amanhã') → {PER: Pedro, ORG: TRF2, DATE: amanhã}. "
            "Instalar com: python -m spacy download pt_core_news_lg."
        ),
        "related": ["NER", "NLPChunker", "AgentBPMN"],
    },
    {
        "term": "Stakeholder",
        "en": "Stakeholder",
        "tag": "neg",
        "def_": (
            "Qualquer indivíduo, grupo ou organização com <strong>interesse nos resultados</strong> "
            "de um sistema ou projeto. Pode ser interno (equipe, gestão) ou externo "
            "(cliente, regulador, fornecedor). Associado a requisitos via campo actor."
        ),
        "example": (
            "Stakeholders do sistema de faturamento: Financeiro (interno), "
            "Receita Federal (externo regulador), Clientes (externos afetados)."
        ),
        "related": ["BABOK v3", "Elicitação", "AgentRequirements", "AgentMinutes"],
    },
    {
        "term": "st.session_state",
        "en": "Streamlit Session State",
        "tag": "dev",
        "def_": (
            "Dicionário persistente por sessão do Streamlit. Mantém estado entre reruns. "
            "O KnowledgeHub fica em st.session_state['hub']. "
            "<strong>API keys ficam APENAS aqui</strong> — nunca em disco, logs ou variáveis de ambiente."
        ),
        "example": (
            "st.session_state['hub'] = hub → salvo antes de qualquer widget. "
            "st.download_button() dispara rerun — sem este padrão, hub é perdido."
        ),
        "related": ["Streamlit", "KnowledgeHub", "Segurança"],
    },
    {
        "term": "Streamlit",
        "en": "Streamlit",
        "tag": "dev",
        "def_": (
            "Framework Python para aplicações web interativas sem HTML/CSS/JS manual. "
            "<strong>Re-executa o script completo</strong> a cada interação do usuário. "
            "Deploy automático no Streamlit Cloud via push no branch main do GitHub."
        ),
        "example": (
            "st.navigation() define 5 grupos de páginas. st.set_page_config() é chamado "
            "apenas em app.py (única vez). Cada página é um arquivo .py independente."
        ),
        "related": ["st.session_state", "KnowledgeHub", "mermaid.ink"],
    },
    {
        "term": "Supabase",
        "en": "Supabase",
        "tag": "dev",
        "def_": (
            "Plataforma BaaS open-source baseada em <strong>PostgreSQL</strong>. "
            "Oferece banco de dados relacional, autenticação, storage, RLS e APIs REST automáticas. "
            "Fail-open quando não configurado — retorna [] ou None, nunca exceção descontrolada."
        ),
        "example": (
            "get_supabase_client() retorna o singleton; se supabase.url não configurado "
            "em st.secrets, retorna None (fail-open) — o pipeline continua sem persistência."
        ),
        "related": ["pgvector", "RLS", "Embedding", "Streamlit"],
    },
    {
        "term": "Sumário por Perspectiva",
        "en": "Perspective Summary",
        "tag": "neg",
        "def_": (
            "Artefato gerado com <strong>4 ângulos distintos</strong>: "
            "Executivo (impacto estratégico), Técnico (integrações e fluxo), "
            "Gestor de Projeto (ações e prazos), Conformidade & Auditoria (regras e rastreabilidade)."
        ),
        "example": (
            "Ângulo Executivo: 'A reunião definiu a adoção de ERP SAP com ROI estimado em 18 meses.' "
            "Ângulo Conformidade: 'REQ-007 exige LGPD — DPO deve ser notificado em 5 dias.'"
        ),
        "related": ["KnowledgeHub", "Relatório Executivo", "AgentSynthesizer"],
    },

    # ── T ─────────────────────────────────────────────────────────────────────

    {
        "term": "Tarefa BPMN",
        "en": "BPMN Task",
        "tag": "bpmn",
        "def_": (
            "Unidade de trabalho atômica dentro de um processo BPMN. "
            "Tipos: <strong>User Task</strong> (humano), Service Task (sistema/API), "
            "Business Rule Task (regra de negócio), Script Task (automação). "
            "O AgentValidator pontua a diversidade de tipos usados."
        ),
        "example": (
            "'Analista preenche formulário' → User Task. "
            "'Sistema envia e-mail automático' → Service Task."
        ),
        "related": ["BPMN 2.0", "Gateway", "AgentValidator", "AgentBPMN"],
    },
    {
        "term": "Tax (Overhead por Chamada)",
        "en": "Tax / Overhead per Call",
        "tag": "ai",
        "def_": (
            "Custo (latência e/ou dinheiro) adicionado a <strong>toda</strong> chamada de um mecanismo, "
            "independentemente do resultado — diferente de um custo pago só quando algo dá certo. "
            "É o principal argumento contra o fuzzy matching por embedding no cache LLM (PC185): checar o "
            "cache por similaridade exigiria 1 chamada de embedding em toda consulta, <strong>hit ou miss</strong> "
            "— uma tax paga 100% das vezes, não só nas que teriam hit."
        ),
        "example": (
            "Cache exato (hash): tax ≈ 0 — cálculo de hash é local e instantâneo. "
            "Cache fuzzy (embedding): tax = 1 chamada de rede extra por consulta, mesmo em miss."
        ),
        "related": ["Fuzzy Matching", "Semantic Cache", "Embedding"],
    },
    {
        "term": "Temperatura",
        "en": "Temperature (LLM)",
        "tag": "ai",
        "def_": (
            "Parâmetro que controla a <strong>aleatoriedade</strong> das respostas do LLM. "
            "0.0 = determinístico; 1.0 = criativo/aleatório. "
            "Para extração estruturada (JSON), valores baixos (0.1–0.3) são preferidos. "
            "Omitido automaticamente no Thinking Mode."
        ),
        "example": (
            "Agentes de extração usam temperature=0.1. "
            "DeepSeek V4 Flash Thinking não aceita temperature — BaseAgent omite o parâmetro automaticamente."
        ),
        "related": ["LLM", "BaseAgent", "Thinking Mode", "DeepSeek V4 Flash"],
    },
    {
        "term": "Thinking Mode",
        "en": "Thinking Mode",
        "tag": "ai",
        "def_": (
            "Modo de raciocínio estendido ativado pelo parâmetro <strong>reasoning_effort: 'high'</strong> "
            "no provider. O modelo gasta mais tokens raciocínando internamente antes de responder. "
            "Incompatível com json_mode e temperature."
        ),
        "example": (
            "DeepSeek V4 Flash Thinking: extra_body={'thinking': {'type': 'enabled'}} — "
            "BaseAgent detecta o modo e omite temperature/json_mode automaticamente."
        ),
        "related": ["DeepSeek V4 Flash", "BaseAgent", "LLM"],
    },
    {
        "term": "Token",
        "en": "Token (LLM)",
        "tag": "ai",
        "def_": (
            "Unidade básica de texto processada por LLMs. "
            "~0.75 palavras em inglês ou <strong>~0.6 palavras em português</strong>. "
            "O custo de API é cobrado por token de entrada + saída. "
            "hub.meta.total_tokens_used acumula tokens de todos os agentes da sessão."
        ),
        "example": (
            "'O sistema deve processar pedidos' ≈ 7 tokens. "
            "Uma transcrição de 1h de reunião ≈ 8.000–15.000 tokens de entrada."
        ),
        "related": ["LLM", "BaseAgent", "Context Analyzer", "Semantic Cache", "Sanitização de PII"],
    },
    {
        "term": "TTL",
        "en": "Time To Live",
        "tag": "dev",
        "def_": (
            "Prazo de validade de uma entrada de cache — depois dele, a entrada é tratada como expirada "
            "e descartada, mesmo que o hash ainda bata. No cache LLM do P2D, o TTL é fixo em "
            "<strong>30 dias</strong> (checado no cliente a cada leitura; sem UI de configuração). "
            "Evita que uma resposta antiga demais (ex.: de uma versão anterior de um skill) seja "
            "reaproveitada indefinidamente."
        ),
        "example": (
            "Entrada gravada há 31 dias → próxima consulta com o mesmo hash não conta como hit, "
            "a entrada expirada é apagada e uma nova chamada real ao provider acontece."
        ),
        "related": ["Semantic Cache", "Cache Hit / Cache Miss"],
    },
    {
        "term": "Trilha de Auditoria",
        "en": "Audit Trail (LGPD)",
        "tag": "seg",
        "def_": (
            "Registro imutável e assíncrono de eventos de tratamento de dados, salvo na tabela "
            "<strong>compliance_audit</strong> via <code>modules/compliance/audit.py</code>. "
            "Eventos registrados: <code>pipeline_run</code> (nova reunião processada), "
            "<code>consent_granted</code> (base legal registrada), <code>data_accessed</code>, "
            "<code>data_deleted</code>, <code>pii_detected</code>. "
            "Retida por <strong>365 dias</strong> — mais tempo que os próprios dados da reunião. "
            "Gravação em thread daemon (fail-open: nunca bloqueia o pipeline)."
        ),
        "example": (
            "Após processar reunião: compliance_audit recebe {event_type: 'pipeline_run', "
            "meeting_id: '...', user_login: 'pedro', details: {pii_risk_level: 'high', categories: ['CPF', 'EMAIL']}}."
        ),
        "related": ["LGPD", "Camada de Conformidade LGPD", "Consentimento de Dados", "Segurança"],
    },
    {
        "term": "Tool-use",
        "en": "Tool-use / Function Calling",
        "tag": "ai",
        "def_": (
            "Capacidade de LLMs de <strong>invocar funções externas</strong> durante a geração de resposta. "
            "O LLM recebe um catálogo de ferramentas, decide quais chamar e interpreta os resultados. "
            "O Assistente Modo A usa tool-use: até 8 rounds de chamadas por turno."
        ),
        "example": (
            "'Quais decisões foram tomadas na Reunião 3?' → LLM chama get_meeting_decisions(3) "
            "→ recebe resultado → formula resposta baseada nos dados reais."
        ),
        "related": ["Assistente RAG", "BaseAgent", "RAG"],
    },
    {
        "term": "Torneio BPMN",
        "en": "BPMN Tournament",
        "tag": "bpmn",
        "def_": (
            "Modo de otimização que executa <strong>N passes do AgentBPMN</strong> (1, 3 ou 5) "
            "e seleciona o candidato com maior pontuação composta (granularidade, task_type, "
            "gateways, erros estruturais — 0–10 cada). Alternativa ao LangGraph Adaptive Retry."
        ),
        "example": (
            "N=3: AgentBPMN gera 3 versões do mesmo diagrama em paralelo → "
            "AgentValidator pontua cada uma → melhor candidato vai para hub.bpmn."
        ),
        "related": ["AgentBPMN", "AgentValidator", "LangGraph"],
    },

    # ── V ─────────────────────────────────────────────────────────────────────

    {
        "term": "Validação Estrutural BPMN",
        "en": "BPMN Structural Validation",
        "tag": "bpmn",
        "def_": (
            "Checagem determinística de <strong>6 critérios estruturais</strong> do XML BPMN: "
            "gates desconectados, lanes vazias, tasks sem lane, fluxos para nenhum lugar, "
            "IDs duplicados, ausência de Start/End Events. Classifica por severidade (error/warning/info)."
        ),
        "example": (
            "repair_bpmn() executa 4 passes de reparo determinístico antes de exibir o diagrama. "
            "Diagnóstico exibido no painel BPMN da página Pipeline."
        ),
        "related": ["AgentValidator", "bpmn-js", "AgentBPMN"],
    },

]


# ─────────────────────────────────────────────────────────────────────────────
# Search function — used by the Assistant tool
# ─────────────────────────────────────────────────────────────────────────────

_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    return _HTML_TAG_RE.sub("", text)


def search_glossary(
    query: str,
    tag: str | None = None,
    max_results: int = 8,
) -> list[dict]:
    """
    Search GLOSSARY_ENTRIES by query string and optional category tag.

    Returns a list of plain-dict results (HTML stripped from def_) suitable
    for LLM consumption via the search_glossary assistant tool.
    """
    q = query.lower().strip()
    if not q:
        return []

    results = []
    for entry in GLOSSARY_ENTRIES:
        if tag and entry.get("tag") != tag:
            continue

        searchable = " ".join([
            entry.get("term", ""),
            entry.get("en", ""),
            _strip_html(entry.get("def_", "")),
            entry.get("example", ""),
            " ".join(entry.get("related", [])),
        ]).lower()

        if q in searchable:
            results.append({
                "term":    entry["term"],
                "en":      entry.get("en", ""),
                "tag":     entry.get("tag", ""),
                "def_":    _strip_html(entry.get("def_", "")),
                "example": entry.get("example", ""),
                "related": entry.get("related", []),
            })

    return results[:max_results]


# ─────────────────────────────────────────────────────────────────────────────
# Tag metadata (used by the page to build filters)
# ─────────────────────────────────────────────────────────────────────────────

TAG_META: dict[str, dict] = {
    "bpmn": {"label": "Modelagem & BPMN",       "emoji": "🔷", "color": "#1a5080"},
    "req":  {"label": "Requisitos & Spec",       "emoji": "📋", "color": "#1a6040"},
    "ai":   {"label": "IA & LLM",               "emoji": "🤖", "color": "#7a4a10"},
    "dev":  {"label": "Dev & Infraestrutura",    "emoji": "⚙️",  "color": "#4a1a7a"},
    "neg":  {"label": "Negócios & Metodologia",  "emoji": "🎯", "color": "#6a2a10"},
    "seg":  {"label": "Segurança & Privacidade", "emoji": "🔒", "color": "#0a6050"},
}
