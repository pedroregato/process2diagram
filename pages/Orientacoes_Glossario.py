# pages/Orientacoes_Glossario.py
# ─────────────────────────────────────────────────────────────────────────────
# Glossário de termos, conceitos e referências — Process2Diagram
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from ui.auth_gate import apply_auth_gate

apply_auth_gate()

# ── CSS (mesmo visual das demais Orientações) ─────────────────────────────────
st.markdown("""
<style>
.guide-header {
    background: linear-gradient(135deg, #071428 0%, #0B1E3D 55%, #122848 100%);
    border-bottom: 3px solid #C97B1A;
    border-radius: 12px;
    padding: 1.4rem 2rem;
    margin-bottom: 1.6rem;
    box-shadow: 0 4px 24px rgba(0,0,0,.35);
}
.guide-header .gh-title { font-size: 1.5rem; font-weight: 700; color: #FAFAF8; }
.guide-header .gh-sub   { font-size: .80rem; color: #7A8EA8; margin-top: .3rem; }

.g-section-hdr {
    display: flex; align-items: center; gap: .6rem;
    font-size: .72rem; font-weight: 700; color: #6A7E98;
    letter-spacing: .12em; text-transform: uppercase;
    margin: 1.8rem 0 .8rem;
}
.g-section-hdr::after {
    content: ""; flex: 1; height: 1px;
    background: linear-gradient(90deg, #1e3a55 0%, transparent 100%);
}

/* ── Glossary card ── */
.gl-card {
    background: #0A1A32;
    border: 1px solid #1A3050;
    border-radius: 10px;
    padding: .85rem 1.1rem;
    margin-bottom: .6rem;
    box-shadow: 0 2px 8px rgba(0,0,0,.18);
}
.gl-card .gl-term {
    font-size: .95rem; font-weight: 700; color: #FAFAF8;
    display: flex; align-items: center; gap: .5rem;
    margin-bottom: .3rem;
}
.gl-card .gl-acro {
    font-size: .68rem; font-weight: 700;
    background: rgba(201,123,26,.15); color: #C97B1A;
    border: 1px solid rgba(201,123,26,.3);
    border-radius: 8px; padding: 1px 7px; letter-spacing: .04em;
}
.gl-card .gl-def {
    font-size: .80rem; color: #9AAABB; line-height: 1.58;
    margin-bottom: .3rem;
}
.gl-card .gl-note {
    font-size: .73rem; color: #C9A060;
    background: rgba(201,123,26,.07);
    border-left: 2px solid #C97B1A;
    border-radius: 3px; padding: .3rem .6rem;
    margin-top: .35rem;
}
.gl-card .gl-spec {
    font-size: .70rem; color: #4A7EA8;
    margin-top: .3rem;
}

/* ── Reference card ── */
.ref-card {
    background: #0A1A32;
    border: 1px solid #1A3050;
    border-left: 4px solid #3b82f6;
    border-radius: 10px;
    padding: .8rem 1.1rem;
    margin-bottom: .55rem;
}
.ref-card .ref-title { font-size: .88rem; font-weight: 700; color: #FAFAF8; }
.ref-card .ref-body  { font-size: .77rem; color: #7A8EA8; line-height: 1.5; margin-top: .25rem; }
.ref-card .ref-link  { font-size: .72rem; color: #3b82f6; margin-top: .2rem; }

/* ── Category badge ── */
.cat-badge {
    display: inline-block; padding: 2px 9px; border-radius: 10px;
    font-size: .64rem; font-weight: 700; letter-spacing: .05em;
    margin-bottom: .6rem;
}

/* ── Two-col grid for cards ── */
.gl-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    gap: .6rem;
}
</style>
""", unsafe_allow_html=True)

# ── Cabeçalho ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="guide-header">
  <div class="gh-title">📚 Glossário</div>
  <div class="gh-sub">
    Termos, conceitos e referências do Process2Diagram —
    organizado por domínio para facilitar a consulta.
  </div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# DADOS DO GLOSSÁRIO
# ─────────────────────────────────────────────────────────────────────────────

# Estrutura: (termo, sigla_ou_None, definição, nota_de_contexto, spec_ref)
_SECTIONS: list[tuple[str, str, list[tuple]]] = [

    # ── 1. Processo & Modelagem BPMN ──────────────────────────────────────────
    ("Processo & Modelagem", "📐", [
        ("BPMN 2.0", "BPMN",
         "Business Process Model and Notation versão 2.0. Notação gráfica padronizada pela OMG para "
         "modelar processos de negócio. Usa elementos como Events, Tasks, Gateways e Pools para "
         "representar o fluxo de trabalho de uma organização.",
         "Padrão utilizado para gerar o diagrama principal da solução. O XML gerado é compatível "
         "com qualquer ferramenta BPMN 2.0 (Camunda, Signavio, bpmn-js).",
         "OMG BPMN 2.0 / ISO 19510"),

        ("Pool", None,
         "Contêiner que representa um participante ou organização em um processo BPMN. "
         "Cada Pool pode conter Lanes (raias) que subdivide os responsáveis internos.",
         "No Process2Diagram, a LLM extrai os atores da transcrição e os mapeia em Pools/Lanes automaticamente.",
         "OMG BPMN 2.0 §9"),

        ("Lane", None,
         "Subdivisão horizontal ou vertical dentro de um Pool. Representa um papel, departamento "
         "ou sistema responsável pelas tarefas contidas nela.",
         "A Regra 1b do AgentBPMN evita nomes genéricos ('Usuário', 'Sistema') — infere o nome "
         "real da organização a partir das falas da transcrição.",
         "OMG BPMN 2.0 §9.2"),

        ("Gateway", None,
         "Elemento BPMN que controla a divergência e convergência de fluxos. Tipos principais: "
         "XOR (exclusivo — uma saída), AND/Paralelo (todos os caminhos), OR (inclusivo — um ou mais).",
         "O AgentBPMN classifica gateways. O AgentValidator pontua a qualidade do uso de gateways "
         "no diagrama gerado.",
         "OMG BPMN 2.0 §10"),

        ("Evento (Event)", None,
         "Ocorrência que afeta o fluxo do processo. Tipos: Start Event (inicia), End Event (encerra), "
         "Intermediate Event (ocorre durante). Pode ser de mensagem, timer, sinal, erro, entre outros.",
         "O gerador BPMN adiciona Start e End Events automaticamente — a LLM não deve declará-los "
         "(Rule 0 de _enforce_rules).",
         "OMG BPMN 2.0 §10.4"),

        ("Tarefa (Task)", None,
         "Unidade de trabalho atômica dentro de um processo. Tipos relevantes: User Task (humano), "
         "Service Task (sistema/API), Business Rule Task (regra de negócio), Script Task (automação).",
         "O AgentValidator pontua a diversidade de tipos de tarefa: processos com apenas User Tasks "
         "perdem pontos em 'task_type'.",
         "OMG BPMN 2.0 §10.2"),

        ("Link Intermediate Event", None,
         "Evento intermediário usado para conectar fluxos que atravessam fronteiras de Lane sem "
         "criar setas longas e diagonais. Um 'Throw' lança o link; um 'Catch' o recebe.",
         "O bpmn_generator.py injeta Links automaticamente quando um fluxo cruza 2 ou mais "
         "fronteiras de Lane — a LLM não deve declará-los.",
         "OMG BPMN 2.0 §10.4.4"),

        ("Collaboration / Message Flow", None,
         "Diagrama BPMN com múltiplos Pools (participantes distintos) conectados por Message Flows "
         "(setas tracejadas que representam troca de mensagens entre organizações).",
         "O Process2Diagram suporta o modo collaboration quando o LLM retorna um campo 'pools' "
         "no JSON. Pools distintos são desenhados lado a lado.",
         "OMG BPMN 2.0 §9.4"),

        ("Mermaid", None,
         "Linguagem de marcação textual para diagramas (flowcharts, sequência, Gantt). "
         "Sintaxe simples: nós, arestas e labels em texto plano, renderizados como SVG.",
         "O AgentMermaid gera o fluxograma Mermaid a partir do BPMNModel (pure Python, sem LLM). "
         "Renderização via mermaid.ink.",
         "mermaid.js v10"),

        ("DMN 1.4", "DMN",
         "Decision Model and Notation versão 1.4. Padrão OMG para modelar tabelas de decisão. "
         "Define: Inputs (condições), Outputs (resultados), Rules (linhas) e Hit Policy (como "
         "múltiplas regras se aplicam).",
         "O AgentDMN extrai decisões formais da transcrição e as converte em tabelas DMN. "
         "Hit policies suportadas: U (Unique), A (Any), F (First), C (Collect).",
         "OMG DMN 1.4"),

        ("IBIS / Argumentação", "IBIS",
         "Issue-Based Information System. Framework para captura de raciocínio deliberativo: "
         "Questões (Issues), Alternativas (Positions) e Argumentos (Pros/Cons). "
         "Desenvolvido por Rittel & Webber (1973).",
         "O AgentArgumentation extrai o mapa IBIS da transcrição. Cada questão tem alternativas "
         "com pros/cons e resolução (decidida / adiada / pendente).",
         "Rittel & Webber (1973) — Rittel & Kunz (1970) IBIS"),
    ]),

    # ── 2. Análise de Negócios ─────────────────────────────────────────────────
    ("Análise de Negócios", "🎯", [
        ("SBVR 1.5", "SBVR",
         "Semantics of Business Vocabulary and Rules. Padrão OMG para formalizar o vocabulário "
         "e as regras de negócio de uma organização em linguagem natural estruturada. "
         "Separa fatos estruturais de restrições operacionais.",
         "O AgentSBVR extrai BusinessTerms (vocabulário) e BusinessRules (regras). "
         "Cada regra agora carrega esfera de negócio (sphere) e dono (sphere_owner).",
         "OMG SBVR 1.5"),

        ("Esfera de Negócio (Sphere)", None,
         "Domínio organizacional ao qual uma regra de negócio pertence. Esferas suportadas: "
         "Marketing, Financeiro, RH, Operações, Jurídico, Tecnologia, Geral. "
         "Cada esfera tem um dono típico (CMO, CFO, CHRO, COO, CLO, CTO, CEO).",
         "Classificação multi-esfera implementada na Fase G do Process2Diagram. "
         "Permite agrupar regras por área e identificar o responsável executivo.",
         "Process2Diagram — Proposta Multi-Esfera SBVR"),

        ("BMM 1.3", "BMM",
         "Business Motivation Model. Padrão OMG que estrutura os elementos de motivação de negócio: "
         "Vision (onde queremos chegar), Mission (o que fazemos), Goals (objetivos), "
         "Strategies (como alcançamos) e Policies (restrições que governam as estratégias).",
         "O AgentBMM extrai o modelo BMM da transcrição. Políticas BMM podem ser vinculadas "
         "a regras SBVR via bmm_policy_ref.",
         "OMG BMM 1.3"),

        ("Regra de Negócio (Business Rule)", None,
         "Diretiva declarativa que governa o comportamento de um processo ou sistema de negócio. "
         "Em SBVR: separada em fato estrutural ('A fatura tem prazo de pagamento') e "
         "restrição operacional ('É obrigatório emitir fatura em até 3 dias úteis').",
         "Rastreabilidade: requirements.business_rule_refs conecta cada requisito às regras SBVR "
         "que ele realiza.",
         "OMG SBVR 1.5 §8"),

        ("BABOK v3", "BABOK",
         "Business Analysis Body of Knowledge. Guia publicado pelo IIBA com as melhores práticas "
         "de análise de negócios. Define técnicas de elicitação, documentação e validação de "
         "requisitos e necessidades de stakeholders.",
         "Os campos BABOK adicionados na Fase E: assumptions, open_questions, risks_identified, "
         "dependencies e stakeholder_needs extraídos pela ata de reunião.",
         "IIBA BABOK Guide v3"),

        ("Elicitação", None,
         "Processo de descoberta e coleta de necessidades e requisitos de stakeholders. "
         "Técnicas incluem entrevistas, workshops, observação, análise de documentos e prototipagem.",
         "No Process2Diagram, a elicitação ocorre de forma automatizada via transcrição de reunião — "
         "o LLM atua como analista de requisitos.",
         "IIBA BABOK v3 — Capítulo 4"),

        ("Stakeholder", None,
         "Qualquer indivíduo, grupo ou organização que tem interesse direto ou indireto nos "
         "resultados de um sistema ou projeto. Pode ser interno (equipe) ou externo (cliente, regulador).",
         "O AgentMinutes identifica participantes; o AgentRequirements associa stakeholders "
         "a requisitos via campo 'actor'.",
         "ISO/IEC/IEEE 29148:2018"),

        ("KPI", "KPI",
         "Key Performance Indicator. Métrica quantitativa usada para avaliar o progresso em relação "
         "a objetivos estratégicos ou operacionais. Deve ser específico, mensurável, atingível, "
         "relevante e temporal (SMART).",
         "O dashboard ROI-TR calcula KPIs de qualidade por tipo de reunião.",
         "—"),
    ]),

    # ── 3. Requisitos ─────────────────────────────────────────────────────────
    ("Requisitos de Software", "📝", [
        ("IEEE 830 / ISO 29148", None,
         "IEEE 830-1998 (substituído pela ISO/IEC/IEEE 29148:2018). Padrão que define "
         "a estrutura e as características de uma boa Especificação de Requisitos de Software (SRS). "
         "Define: completude, consistência, verificabilidade, rastreabilidade e não-ambiguidade.",
         "O AgentRequirements produz saída compatível com IEEE 830: ID único, título, "
         "descrição, tipo, prioridade, ator e citação-fonte.",
         "ISO/IEC/IEEE 29148:2018 / IEEE 830-1998"),

        ("Requisito Funcional", "RF",
         "Descreve uma função, comportamento ou serviço que o sistema deve fornecer. "
         "Responde à pergunta: 'O que o sistema deve fazer?'",
         "Tipo 'functional' no Process2Diagram. Exemplos: autenticação, geração de relatório, "
         "integração com API.",
         "ISO/IEC/IEEE 29148:2018 §5.2.5"),

        ("Requisito Não-Funcional", "RNF",
         "Restrição ou atributo de qualidade que o sistema deve satisfazer: desempenho, "
         "segurança, usabilidade, disponibilidade, escalabilidade.",
         "Tipo 'non_functional' no AgentRequirements. Frequentemente derivado de falas sobre "
         "SLA, tempo de resposta ou compliance.",
         "ISO/IEC/IEEE 29148:2018 §5.2.5"),

        ("Rastreabilidade (Traceability)", None,
         "Capacidade de rastrear um requisito desde sua origem (fala na reunião) até sua "
         "implementação e testes. Permite identificar o impacto de mudanças.",
         "O campo source_quote + speaker registra a evidência do requisito. "
         "business_rule_refs conecta requisito à regra SBVR que o originou.",
         "ISO/IEC/IEEE 29148:2018 §6.3"),

        ("Prioridade", None,
         "Classificação da importância relativa de um requisito: Alta, Média, Baixa, Não-especificada. "
         "Orienta o planejamento de sprints e gestão de escopo.",
         "O Req. Tracker exibe requisitos filtráveis por prioridade. "
         "A aba Mind Map agrupa por tipo e destaca prioridade com ícones de cor.",
         "—"),

        ("Status do Requisito", None,
         "Ciclo de vida de um requisito: active, backlog, approved, in_progress, implemented, "
         "revised, contradicted, deprecated, rejected.",
         "O AgentReqReconciler compara novos requisitos com o histórico do projeto e atribui "
         "status (novo, revisado, confirmado, contradição).",
         "—"),

        ("Reconciliação de Requisitos", None,
         "Processo de comparar requisitos de uma nova reunião com os já armazenados no projeto, "
         "identificando novidades, revisões, confirmações e contradições.",
         "Executado pelo AgentReqReconciler ao final do pipeline quando Supabase está configurado.",
         "—"),
    ]),

    # ── 4. Inteligência Artificial & LLM ──────────────────────────────────────
    ("Inteligência Artificial & LLM", "🤖", [
        ("LLM", "LLM",
         "Large Language Model. Modelo de linguagem de grande escala treinado em vastos corpus textuais "
         "para compreender e gerar texto. Exemplos: GPT-4, Claude, Llama, Gemini, DeepSeek.",
         "O Process2Diagram é agnóstico de provedor: qualquer LLM configurado em AVAILABLE_PROVIDERS "
         "pode ser usado. O roteamento ocorre em BaseAgent._call_llm().",
         "—"),

        ("Agente LLM (Agent)", None,
         "Componente autônomo que usa um LLM para realizar uma tarefa específica, seguindo um "
         "prompt de sistema (skill) e retornando saída estruturada (JSON). "
         "Cada agente lê e escreve no KnowledgeHub.",
         "Padrão: herda BaseAgent → define skill_path e build_prompt() → chama _call_with_retry() "
         "→ constrói o modelo de dados → registra em hub.",
         "—"),

        ("Prompt de Sistema (System Prompt)", None,
         "Instrução de comportamento passada ao LLM antes da mensagem do usuário. "
         "Define papel, formato de saída esperado e restrições.",
         "No Process2Diagram, o system prompt de cada agente é carregado de um arquivo .md "
         "em skills/ via _load_skill(). A variável {output_language} é substituída em runtime.",
         "—"),

        ("RAG", "RAG",
         "Retrieval-Augmented Generation. Técnica que combina busca de documentos relevantes "
         "(retrieval) com geração de resposta pelo LLM, reduzindo alucinações e permitindo "
         "que o modelo responda sobre dados que não estavam em seu treino.",
         "O Assistente opera em Modo B (RAG Clássico) via busca semântica + keyword em Supabase. "
         "No Modo A (tool-use), o LLM acessa os dados via ferramentas estruturadas.",
         "Lewis et al., 2020 — RAG Paper (arXiv:2005.11401)"),

        ("Embedding / Vetor Semântico", None,
         "Representação numérica de texto em um espaço vetorial de alta dimensão. "
         "Textos semanticamente similares têm vetores próximos (cosine similarity). "
         "Dimensão usada: 1536 (compatível com pgvector ivfflat).",
         "Provedor: Google Gemini 'gemini-embedding-001' com output_dimensionality=1536. "
         "Gerados via Banco de Dados → aba Embeddings.",
         "—"),

        ("Token", None,
         "Unidade básica de texto processada por LLMs. Aproximadamente 0,75 palavras em inglês "
         "ou 0,6 palavras em português. O custo de API é cobrado por token de entrada + saída.",
         "O hub.meta.total_tokens_used acumula tokens de todos os agentes. "
         "A página Estimativa de Custo calcula o custo antes do processamento.",
         "—"),

        ("Temperatura (Temperature)", None,
         "Parâmetro que controla a aleatoriedade das respostas do LLM. "
         "0.0 = determinístico; 1.0 = criativo/aleatório. "
         "Para extração estruturada (JSON), valores baixos (0.1–0.3) são preferidos.",
         "Os agentes do Process2Diagram usam temperature baixa para maximizar a consistência "
         "do JSON gerado.",
         "—"),

        ("Tool-use / Function Calling", None,
         "Capacidade de LLMs de invocar funções externas (ferramentas) durante a geração de resposta. "
         "O LLM recebe um catálogo de tools, decide quais chamar e interpreta os resultados.",
         "O Assistente em Modo A usa tool-use: até 8 rounds de chamadas. "
         "As ferramentas acessam Supabase, Google Calendar e o KnowledgeHub.",
         "OpenAI Function Calling / Anthropic Tool-use"),

        ("LangGraph", None,
         "Biblioteca da LangChain para orquestrar agentes LLM como grafos de estado. "
         "Permite ciclos condicionais (ex: tentar novamente se a qualidade for baixa).",
         "Usado no LGBPMNRunner: retry adaptativo do BPMN até atingir o limiar de qualidade "
         "configurado (padrão: score >= 6.0).",
         "LangGraph — github.com/langchain-ai/langgraph"),

        ("spaCy", None,
         "Biblioteca Python de NLP de alta performance. Suporta NER (Named Entity Recognition), "
         "POS tagging, dependency parsing, e segmentação de sentenças.",
         "O NLPChunker usa spaCy (pt_core_news_lg) para extrair atores, entidades e segmentar "
         "a transcrição sem LLM, antes dos agentes.",
         "spaCy.io — Honnibal & Montani, 2017"),

        ("NER", "NER",
         "Named Entity Recognition. Tarefa de NLP que identifica e classifica entidades nomeadas "
         "em texto: pessoas (PER), organizações (ORG), locais (LOC), datas (DATE), etc.",
         "O NLPChunker usa NER para extrair os atores da reunião, usados nas lanes do BPMN. "
         "A página Entidades (NER) exibe as entidades identificadas no texto.",
         "—"),

        ("PII", "PII",
         "Personally Identifiable Information. Informação que pode identificar um indivíduo: "
         "CPF, CNPJ, e-mail, telefone, valores monetários, etc.",
         "O módulo pii_sanitizer.py substitui PIIs por tokens antes de enviar ao LLM "
         "e restaura os tokens originais na resposta (sanitize/desanitize).",
         "LGPD — Lei 13.709/2018"),
    ]),

    # ── 5. Dados & Infraestrutura ─────────────────────────────────────────────
    ("Dados & Infraestrutura", "🗄️", [
        ("Supabase", None,
         "Plataforma BaaS (Backend as a Service) open-source baseada em PostgreSQL. "
         "Oferece banco de dados relacional, autenticação, storage e APIs REST automáticas.",
         "Usado para persistir reuniões, artefatos, requisitos, embeddings, regras SBVR, "
         "configurações de projeto e controle de acesso (RLS).",
         "supabase.com"),

        ("pgvector", None,
         "Extensão PostgreSQL para armazenamento e busca de vetores de alta dimensão. "
         "Suporta índices ivfflat (limite: 2000 dimensões) e HNSW. "
         "Operações: similaridade por cosine, L2, produto interno.",
         "Usado para busca semântica no Assistente Modo B. "
         "Dimensão configurada: 1536 (compatível com ivfflat). "
         "Função SQL: match_transcript_chunks().",
         "github.com/pgvector/pgvector"),

        ("Row Level Security", "RLS",
         "Mecanismo do PostgreSQL que restringe acesso a linhas de uma tabela com base em políticas. "
         "Cada policy define QUAL usuário ou role pode SELECT, INSERT, UPDATE ou DELETE.",
         "Habilitado em todas as tabelas do Supabase — dados de um projeto não vazam para outro.",
         "PostgreSQL RLS Docs"),

        ("Streamlit", None,
         "Framework Python para criação de aplicações web interativas sem escrever HTML/CSS/JS. "
         "Baseado em re-execução do script completo a cada interação do usuário.",
         "O Process2Diagram é inteiramente construído em Streamlit. "
         "A navegação usa st.navigation() com 5 grupos de páginas.",
         "streamlit.io"),

        ("st.session_state", None,
         "Dicionário persistente por sessão do Streamlit. Mantém estado entre reruns "
         "(dados que não devem ser reiniciados a cada interação do usuário).",
         "O KnowledgeHub é armazenado em st.session_state['hub']. "
         "API keys ficam APENAS no session_state — nunca em disco.",
         "Streamlit Docs — Session State"),

        ("bpmn-js v17", None,
         "Biblioteca JavaScript para renderização e edição de BPMN 2.0 no browser. "
         "Oferece um Viewer (somente leitura) e um Modeler (edição completa).",
         "O bpmn_viewer.py injeta bpmn-js inline (server-side fetch + lru_cache), "
         "eliminando dependência de CDN bloqueado pelo sandbox do Streamlit Cloud.",
         "github.com/bpmn-io/bpmn-js"),

        ("Google Calendar API v3", None,
         "API REST do Google para criar, listar, atualizar e excluir eventos em agendas Google. "
         "Autenticação via Service Account (JSON de credenciais) ou OAuth 2.0.",
         "O calendar_client.py expõe 8 funções. O Assistente pode agendar ações "
         "via tool-use. Credenciais ficam em st.secrets['google_calendar'].",
         "developers.google.com/calendar"),

        ("ASR", "ASR",
         "Automatic Speech Recognition. Tecnologia de transcrição automática de fala para texto. "
         "Produz artefatos como repetições, hesitações ('ahn', 'é'), palavras cortadas e erros de "
         "homófonos que reduzem a qualidade da transcrição.",
         "O TranscriptPreprocessor (modules/transcript_preprocessor.py) remove esses artefatos "
         "via regras determinísticas antes de alimentar os agentes LLM.",
         "—"),
    ]),

    # ── 6. Artefatos & Módulos da Solução ─────────────────────────────────────
    ("Artefatos & Módulos da Solução", "🧩", [
        ("KnowledgeHub", None,
         "Dataclass central que representa o estado completo de uma sessão de processamento. "
         "Contém todos os artefatos produzidos pelos agentes: BPMN, ata, requisitos, SBVR, BMM, "
         "DMN, IBIS, qualidade, metadados e o sumário por perspectiva.",
         "Versionado (hub.bump()). Persistido em st.session_state['hub']. "
         "Serializado para JSON via hub.to_json(). Migrado via KnowledgeHub.migrate().",
         "core/knowledge_hub.py"),

        ("KnowledgeGraph", None,
         "Grafo de entidades e fatos extraídos das reuniões de um projeto ao longo do tempo. "
         "Nós = entidades (pessoas, processos, sistemas, conceitos). "
         "Arestas = fatos e relações entre entidades. "
         "Nós ⚠ = contradições detectadas entre reuniões.",
         "Visualizado na página Grafo de Conhecimento (pyvis/vis-network). "
         "Tabelas Supabase: kh_entities, kh_facts, kh_contradictions.",
         "pages/KnowledgeGraph.py"),

        ("Context Knowledge File", "CKF",
         "Arquivo de conhecimento acumulado sobre um contexto/projeto. "
         "Contém participantes recorrentes, termos do domínio, regras estabelecidas e objetivos. "
         "Injetado no system prompt dos agentes para contextualizar o processamento.",
         "Gerado e atualizado automaticamente pelo AgentCKFUpdater ao final de cada pipeline. "
         "Editável manualmente em Configurações → CKF do contexto.",
         "pages/Orientacoes_CKF.py"),

        ("Pipeline de Agentes", None,
         "Sequência orquestrada de agentes LLM que transformam uma transcrição bruta em artefatos "
         "estruturados. Etapas: Qualidade → Preprocessamento → NLP → BPMN → SBVR → "
         "Minutes ‖ Requirements → BMM → DMN → IBIS → Sintetizador → Sumário.",
         "Orchestrator.run() coordena a execução. Minutes e Requirements rodam em paralelo "
         "(ThreadPoolExecutor). SBVR roda ANTES de Requirements desde a Fase G.",
         "agents/orchestrator.py"),

        ("Ata de Reunião (Minutes)", None,
         "Documento estruturado gerado pelo AgentMinutes com: título, data, participantes, "
         "pauta, resumo por tópico, decisões, itens de ação e campos BABOK "
         "(suposições, questões abertas, riscos, dependências, necessidades dos stakeholders).",
         "Exportável como Markdown, Word (.docx) e PDF. "
         "A ATA Engine gera HTML interativo com assinaturas digitais.",
         "agents/agent_minutes.py"),

        ("ROI-TR", "ROI-TR",
         "Return on Investment from Transcription. Métrica proprietária que avalia o valor "
         "gerado pelo processamento de uma reunião com base nos artefatos produzidos "
         "e no tipo de reunião (11 tipos com matrizes de pesos distintas).",
         "Calculado em modules/meeting_roi_calculator.py. "
         "Dashboard na página Qualidade ROI-TR.",
         "pages/MeetingROI.py"),

        ("Sumário por Perspectiva", None,
         "Artefato da Fase F: sumário automático gerado após o pipeline com 4 ângulos distintos: "
         "Executivo (impacto estratégico), Técnico (integrações e fluxo), "
         "Gestor de Projeto (ações e prazos), Conformidade & Auditoria (regras e rastreabilidade).",
         "Gerado pelo AgentQuerySummarizer. "
         "Ativado pelo checkbox 'Sumário por Perspectiva' na sidebar.",
         "agents/agent_query_summarizer.py"),

        ("Relatório Executivo (Synthesizer)", None,
         "HTML auto-contido que sintetiza todos os artefatos da reunião em uma narrativa executiva. "
         "Inclui: sumário, narrativa do processo, insights, recomendações e tabelas de requisitos.",
         "Gerado pelo AgentSynthesizer. "
         "Exportável como .html. Invalidado automaticamente se o BPMN for re-executado.",
         "agents/agent_synthesizer.py"),

        ("Validação BPMN (Torneio)", None,
         "Mecanismo de otimização: executa N passes do AgentBPMN (1, 3 ou 5) e seleciona "
         "o candidato com maior pontuação composta por: granularidade, tipo de tarefa, "
         "uso de gateways e ausência de erros estruturais (0–10 cada).",
         "Pontuação calculada pelo AgentValidator (pure Python, sem LLM). "
         "LangGraph Adaptive Retry é uma alternativa para 1 passe com retentativa.",
         "agents/agent_validator.py"),
    ]),
]


# ─────────────────────────────────────────────────────────────────────────────
# REFERÊNCIAS
# ─────────────────────────────────────────────────────────────────────────────

_REFS: list[tuple[str, str, str, str]] = [
    # (título, tipo, descrição, url_ou_local)
    ("OMG BPMN 2.0 — formal/2013-12-09", "Especificação",
     "Especificação oficial da OMG (Object Management Group) para Business Process Model and Notation. "
     "Padrão ISO/IEC 19510:2013.",
     "omg.org/spec/BPMN/2.0"),

    ("OMG SBVR 1.5", "Especificação",
     "Semantics of Business Vocabulary and Rules — especificação da OMG para formalização de vocabulário "
     "e regras de negócio em linguagem natural estruturada.",
     "omg.org/spec/SBVR/1.5"),

    ("OMG BMM 1.3", "Especificação",
     "Business Motivation Model — especificação da OMG para estruturar Vision, Mission, Goals, "
     "Strategies e Policies de uma organização.",
     "omg.org/spec/BMM/1.3"),

    ("OMG DMN 1.4", "Especificação",
     "Decision Model and Notation — padrão OMG para tabelas de decisão formais com Hit Policies "
     "e rastreabilidade de regras.",
     "omg.org/spec/DMN/1.4"),

    ("ISO/IEC/IEEE 29148:2018", "Norma",
     "Systems and software engineering — Life cycle processes — Requirements engineering. "
     "Substitui IEEE 830-1998. Define boas práticas para especificação de requisitos de sistema e software.",
     "iso.org/standard/72089.html"),

    ("IIBA BABOK Guide v3", "Guia de Boas Práticas",
     "A Guide to the Business Analysis Body of Knowledge. Publicado pelo IIBA (International Institute "
     "of Business Analysis). Define técnicas, perspectivas e áreas de conhecimento da Análise de Negócios.",
     "iiba.org/babok-guide"),

    ("Rittel & Webber (1973) — IBIS", "Artigo Científico",
     "Dilemmas in a General Theory of Planning (Policy Sciences, 1973). "
     "Introdução ao IBIS (Issue-Based Information System) como método para estruturar problemas mal definidos.",
     "doi.org/10.1007/BF01405730"),

    ("RAG — Lewis et al. (2020)", "Artigo Científico",
     "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks. "
     "Artigo seminal que define a arquitetura RAG combinando busca densa com geração por LLM.",
     "arxiv.org/abs/2005.11401"),

    ("pgvector", "Biblioteca Open Source",
     "Extensão PostgreSQL para vetores de alta dimensão. Suporta índices ivfflat e HNSW, "
     "operações de similaridade cosine, L2 e inner product. Limite ivfflat: 2000 dimensões.",
     "github.com/pgvector/pgvector"),

    ("bpmn-js v17", "Biblioteca Open Source",
     "Toolkit JavaScript para renderização e edição de BPMN 2.0 no browser. "
     "Desenvolvido pela bpmn.io (Camunda). Oferece Viewer, Modeler e Navigated Viewer.",
     "github.com/bpmn-io/bpmn-js"),

    ("LangGraph", "Framework",
     "Biblioteca para construção de agentes LLM como grafos de estado cíclicos. "
     "Permite workflows com ciclos condicionais, múltiplos agentes e estado persistente.",
     "github.com/langchain-ai/langgraph"),

    ("spaCy v3 — pt_core_news_lg", "Biblioteca NLP",
     "Modelo de língua portuguesa para spaCy com suporte a NER, POS tagging e dependency parsing. "
     "Treinado em corpus jornalístico (CoNLL 2003 / Universal Dependencies).",
     "spacy.io/models/pt"),

    ("Google Gemini Embedding — gemini-embedding-001", "API",
     "Modelo de embedding da Google com output_dimensionality configurável (padrão: 1536). "
     "Tier gratuito sujeito a rate limit de 100 req/min (1,2s de delay entre chamadas).",
     "ai.google.dev/gemini-api/docs/embeddings"),

    ("LGPD — Lei 13.709/2018", "Legislação",
     "Lei Geral de Proteção de Dados Pessoais do Brasil. Regula o tratamento de dados pessoais "
     "e exige mecanismos de consentimento, anonimização e segurança.",
     "planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm"),

    ("Streamlit 1.45", "Framework",
     "Framework Python para aplicações web de dados. Reexecuta o script completo a cada interação. "
     "Usado como frontend do Process2Diagram com st.navigation() multi-página.",
     "streamlit.io"),

    ("Supabase", "Plataforma",
     "Alternativa open-source ao Firebase baseada em PostgreSQL. "
     "Oferece banco de dados, autenticação, storage, RLS e APIs REST automáticas.",
     "supabase.com"),
]


# ─────────────────────────────────────────────────────────────────────────────
# RENDERIZAÇÃO
# ─────────────────────────────────────────────────────────────────────────────

def _card(term: str, acro: str | None, defn: str, note: str, spec: str) -> str:
    acro_html = (
        f'<span class="gl-acro">{acro}</span>' if acro else ""
    )
    note_html = (
        f'<div class="gl-note">💡 {note}</div>' if note else ""
    )
    spec_html = (
        f'<div class="gl-spec">📎 {spec}</div>' if spec and spec != "—" else ""
    )
    return (
        f'<div class="gl-card">'
        f'<div class="gl-term">{term} {acro_html}</div>'
        f'<div class="gl-def">{defn}</div>'
        f'{note_html}'
        f'{spec_html}'
        f'</div>'
    )


def _ref_card(title: str, tipo: str, desc: str, url: str) -> str:
    return (
        f'<div class="ref-card">'
        f'<div class="ref-title">{title}'
        f'  <span style="font-size:.65rem;font-weight:700;color:#6A7E98;'
        f'margin-left:.5rem;letter-spacing:.05em">{tipo.upper()}</span>'
        f'</div>'
        f'<div class="ref-body">{desc}</div>'
        f'<div class="ref-link">🔗 {url}</div>'
        f'</div>'
    )


# Tab-based navigation (uma aba por categoria + Referências)
tab_labels = [f"{icon} {name}" for name, icon, _ in _SECTIONS] + ["📎 Referências"]
tabs = st.tabs(tab_labels)

for i, (name, icon, terms) in enumerate(_SECTIONS):
    with tabs[i]:
        st.markdown(
            f'<div class="g-section-hdr">{name}</div>',
            unsafe_allow_html=True,
        )
        html = '<div class="gl-grid">'
        for row in terms:
            term, acro, defn, note, spec = row
            html += _card(term, acro, defn, note, spec)
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

# Aba de Referências
with tabs[-1]:
    st.markdown(
        '<div class="g-section-hdr">Especificações, Normas e Referências</div>',
        unsafe_allow_html=True,
    )
    for title, tipo, desc, url in _REFS:
        st.markdown(_ref_card(title, tipo, desc, url), unsafe_allow_html=True)

# ── Rodapé ─────────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='margin-top:2rem;padding-top:.8rem;border-top:1px solid #1A3050;"
    "text-align:center;font-size:.68rem;color:#3A5070;letter-spacing:.04em'>"
    "Process2Diagram &nbsp;·&nbsp; Glossário de Termos e Referências"
    "</div>",
    unsafe_allow_html=True,
)
