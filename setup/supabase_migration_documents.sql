-- setup/supabase_migration_documents.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Document Management: taxonomy + storage + semantic search
-- Execute once in Supabase → SQL Editor
-- ─────────────────────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS vector;

-- ── document_types (taxonomy) ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS document_types (
    code        TEXT        PRIMARY KEY,
    label       TEXT        NOT NULL,
    category    TEXT        NOT NULL,
    description TEXT,
    sort_order  INTEGER     NOT NULL DEFAULT 0
);

ALTER TABLE document_types DISABLE ROW LEVEL SECURITY;

-- ── Taxonomy pre-population ───────────────────────────────────────────────────
INSERT INTO document_types (code, label, category, description, sort_order) VALUES

-- Iniciação e Planejamento
('TAP',        'Termo de Abertura do Projeto (TAP)',            'Iniciação e Planejamento', 'Autoriza formalmente o projeto; define objetivo, escopo inicial, stakeholders e patrocinador (PMBOK)', 10),
('PGP',        'Plano de Gerenciamento do Projeto (PGP)',       'Iniciação e Planejamento', 'Plano mestre que integra escopo, cronograma, custo, qualidade, comunicação e riscos (PMBOK)', 20),
('CRONOGRAMA', 'Cronograma / Timeline',                         'Iniciação e Planejamento', 'Sequência de atividades, dependências, durações e marcos do projeto', 30),
('EAP',        'Estrutura Analítica do Projeto (EAP / WBS)',    'Iniciação e Planejamento', 'Decomposição hierárquica do escopo total do trabalho (PMBOK)', 40),
('ORCAMENTO',  'Orçamento / Budget',                            'Iniciação e Planejamento', 'Estimativas de custo, baseline de custo e fundo de contingência', 50),
('RACI',       'Matriz RACI',                                   'Iniciação e Planejamento', 'Responsável, Aprovador, Consultado, Informado — mapa de responsabilidades', 60),
('STAKEHOLDERS','Análise de Stakeholders',                      'Iniciação e Planejamento', 'Identificação, avaliação e estratégia de engajamento dos stakeholders', 70),
('PREMISSAS',  'Registro de Premissas e Restrições',            'Iniciação e Planejamento', 'Premissas assumidas, restrições impostas e dependências externas', 80),

-- Requisitos
('BRD',        'Documento de Requisitos de Negócio (BRD)',      'Requisitos', 'Requisitos do ponto de vista do negócio; o que a solução deve fazer para atingir objetivos estratégicos', 110),
('SRS',        'Especificação de Requisitos de Software (SRS)', 'Requisitos', 'Requisitos funcionais e não-funcionais detalhados para desenvolvimento de software (IEEE 830)', 120),
('BACKLOG',    'Backlog de Produto',                            'Requisitos', 'Lista priorizada de épicos, features e user stories — artefato central do Scrum / SAFe', 130),
('USER_STORY', 'User Stories / Histórias de Usuário',           'Requisitos', 'Como [persona] quero [ação] para [benefício] — padrão Connextra', 140),
('CASO_USO',   'Casos de Uso',                                  'Requisitos', 'Interações ator-sistema; fluxo principal, alternativo e de exceção (UML)', 150),
('CRITERIOS',  'Critérios de Aceite',                           'Requisitos', 'Condições que devem ser satisfeitas para aceitar um requisito, história ou entrega', 160),

-- Processos
('ASIS',       'Mapeamento de Processo AS-IS',                  'Processos', 'Documentação do processo atual — estado presente, com problemas e gargalos identificados', 210),
('TOBE',       'Mapeamento de Processo TO-BE',                  'Processos', 'Documentação do processo futuro — estado desejado após melhoria ou transformação', 220),
('POP',        'Procedimento Operacional Padrão (POP)',          'Processos', 'Instruções passo a passo para execução padronizada de uma atividade operacional', 230),
('SIPOC',      'SIPOC',                                         'Processos', 'Suppliers, Inputs, Process, Outputs, Customers — visão macro do processo (Six Sigma)', 240),
('VSM',        'Value Stream Map (VSM)',                        'Processos', 'Mapeamento do fluxo de valor — identifica desperdícios e oportunidades Lean', 250),
('FLUXOGRAMA', 'Fluxograma de Processo',                        'Processos', 'Representação gráfica do fluxo de atividades, decisões e responsabilidades', 260),
('BPMN_DOC',   'Diagrama BPMN',                                 'Processos', 'Modelo de processo em notação BPMN 2.0 — padrão OMG para modelagem de negócio', 270),

-- Governança
('ATA',        'Ata de Reunião',                                'Governança', 'Registro formal de decisões, participantes, encaminhamentos e próximos passos', 310),
('STATUS',     'Relatório de Status',                           'Governança', 'Relatório periódico de progresso, indicadores, riscos e próximos passos do projeto', 320),
('RISCOS',     'Registro de Riscos',                            'Governança', 'Identificação, avaliação (probabilidade × impacto), resposta e monitoramento de riscos (PMBOK)', 330),
('ISSUES',     'Registro de Issues',                            'Governança', 'Log de problemas identificados, responsável, prazo e status de resolução', 340),
('CHANGE',     'Solicitação de Mudança (Change Request)',        'Governança', 'Proposta, avaliação e aprovação formal de mudanças no escopo, cronograma ou custo', 350),
('PLANO_COM',  'Plano de Comunicação',                          'Governança', 'Define o quê, para quem, como, quando e quem comunica no projeto', 360),
('LICOES',     'Registro de Lições Aprendidas',                 'Governança', 'Aprendizados do projeto para reaproveitamento em projetos futuros (PMBOK)', 370),

-- Análise de Negócio
('SWOT',       'Análise SWOT',                                  'Análise de Negócio', 'Forças, Fraquezas, Oportunidades e Ameaças — análise estratégica do ambiente', 410),
('BMC',        'Business Model Canvas',                         'Análise de Negócio', '9 blocos: proposta de valor, segmentos, canais, relacionamento, receitas, recursos, atividades, parceiros, custos (Osterwalder)', 420),
('VPC',        'Mapa de Proposta de Valor',                     'Análise de Negócio', 'Value Proposition Canvas — alinha proposta de valor com perfil do cliente (jobs, pains, gains)', 430),
('BIA',        'Análise de Impacto de Negócio (BIA)',           'Análise de Negócio', 'Avalia o impacto de interrupções nos processos críticos de negócio', 440),
('VIABILIDADE','Estudo de Viabilidade',                         'Análise de Negócio', 'Análise técnica, econômica e operacional da viabilidade de uma iniciativa', 450),
('ROI_DOC',    'Análise ROI / Business Case',                   'Análise de Negócio', 'Retorno sobre investimento esperado, custos, benefícios e payback period', 460),

-- Técnico
('ESPEC_TEC',  'Especificação Técnica',                         'Técnico', 'Detalhamento técnico de uma solução: componentes, integrações, protocolos, restrições', 510),
('ARQ',        'Documento de Arquitetura',                      'Técnico', 'Visão arquitetural: componentes, camadas, padrões, decisões de design (ADR / C4)', 520),
('API_SPEC',   'Especificação de API',                          'Técnico', 'Contrato de API: endpoints, payloads, autenticação, códigos de resposta (OpenAPI / Swagger)', 530),
('DIAGRAMA_TEC','Diagrama Técnico (UML / C4)',                  'Técnico', 'Diagramas de componentes, sequência, implantação ou contexto (UML 2 / C4 Model)', 540),
('MANUAL',     'Manual Técnico / Runbook',                      'Técnico', 'Guia operacional para administração, troubleshooting e manutenção do sistema', 550),
('DER',        'Diagrama Entidade-Relacionamento (DER)',         'Técnico', 'Modelo de dados: entidades, atributos, relacionamentos e cardinalidades', 560),

-- Qualidade
('PLANO_TESTE','Plano de Testes',                               'Qualidade', 'Estratégia, escopo, recursos, cronograma e critérios de saída dos testes', 610),
('REL_TESTE',  'Relatório de Testes',                           'Qualidade', 'Resultados de execução: casos, defeitos encontrados, cobertura e métricas de qualidade', 620),
('CHECKLIST',  'Checklist de QA',                               'Qualidade', 'Lista de verificação de itens de qualidade a validar antes de uma entrega', 630),
('DEF_DONE',   'Definition of Done (DoD)',                      'Qualidade', 'Critérios que definem quando um item do backlog está completo (Scrum)', 640),

-- Contratos e Acordos
('CONTRATO',   'Contrato',                                      'Contratos e Acordos', 'Instrumento legal que formaliza direitos, obrigações, escopo e condições entre as partes', 710),
('SLA',        'SLA (Service Level Agreement)',                  'Contratos e Acordos', 'Acordo de nível de serviço: métricas de desempenho, disponibilidade e penalidades', 720),
('MOU',        'MOU (Memorando de Entendimento)',                'Contratos e Acordos', 'Documento não vinculante que expressa intenção de cooperação entre as partes', 730),
('PROPOSTA',   'Proposta Comercial',                            'Contratos e Acordos', 'Oferta formal de solução, escopo, prazo, equipe e precificação para o cliente', 740),
('NDA',        'NDA (Acordo de Confidencialidade)',              'Contratos e Acordos', 'Protege informações confidenciais trocadas entre as partes', 750),

-- Normas e Políticas
('POLITICA',   'Política Interna',                              'Normas e Políticas', 'Diretriz organizacional que define regras e princípios para um tema específico', 810),
('NORMA',      'Norma / Regulamento',                           'Normas e Políticas', 'Regra obrigatória, interna ou externa (ABNT, ISO, regulamentação setorial)', 820),
('PROC_CORP',  'Procedimento Corporativo',                      'Normas e Políticas', 'Passos padronizados para execução de processos corporativos transversais', 830),
('CODIGO',     'Código de Conduta / Ética',                     'Normas e Políticas', 'Princípios e regras de comportamento esperado de colaboradores e parceiros', 840)

ON CONFLICT (code) DO NOTHING;


-- ── meeting_documents ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS meeting_documents (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   TEXT        NOT NULL,
    meeting_id   UUID,                          -- optional link to meetings.id
    title        TEXT        NOT NULL,
    doc_type     TEXT        REFERENCES document_types(code),
    file_name    TEXT        NOT NULL DEFAULT '',
    content_text TEXT        NOT NULL DEFAULT '',
    metadata     JSONB       NOT NULL DEFAULT '{}',
    created_by   TEXT        NOT NULL DEFAULT '',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_meeting_docs_project   ON meeting_documents(project_id);
CREATE INDEX IF NOT EXISTS idx_meeting_docs_meeting   ON meeting_documents(meeting_id);
CREATE INDEX IF NOT EXISTS idx_meeting_docs_doc_type  ON meeting_documents(doc_type);
CREATE INDEX IF NOT EXISTS idx_meeting_docs_created   ON meeting_documents(created_at DESC);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION _docs_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS meeting_documents_updated_at ON meeting_documents;
CREATE TRIGGER meeting_documents_updated_at
    BEFORE UPDATE ON meeting_documents
    FOR EACH ROW EXECUTE FUNCTION _docs_set_updated_at();

ALTER TABLE meeting_documents DISABLE ROW LEVEL SECURITY;


-- ── document_chunks (embeddings) ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS document_chunks (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id  UUID        NOT NULL REFERENCES meeting_documents(id) ON DELETE CASCADE,
    chunk_index  INTEGER     NOT NULL,
    content      TEXT        NOT NULL,
    embedding    vector(1536),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_doc_chunks_document_id  ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_chunks_chunk_index  ON document_chunks(document_id, chunk_index);

-- IVFFlat index for fast ANN search (create after data is loaded)
-- CREATE INDEX IF NOT EXISTS idx_doc_chunks_embedding
--     ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 50);

ALTER TABLE document_chunks DISABLE ROW LEVEL SECURITY;


-- ── pgvector similarity search function ───────────────────────────────────────
CREATE OR REPLACE FUNCTION match_document_chunks(
    query_embedding  vector(1536),
    match_project_id TEXT,
    match_count      INT   DEFAULT 5,
    match_threshold  FLOAT DEFAULT 0.4
)
RETURNS TABLE (
    id            UUID,
    document_id   UUID,
    chunk_index   INT,
    content       TEXT,
    similarity    FLOAT,
    doc_title     TEXT,
    doc_type      TEXT,
    doc_file_name TEXT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id,
        dc.document_id,
        dc.chunk_index,
        dc.content,
        (1 - (dc.embedding <=> query_embedding))::FLOAT AS similarity,
        md.title     AS doc_title,
        md.doc_type,
        md.file_name AS doc_file_name
    FROM document_chunks dc
    JOIN meeting_documents md ON md.id = dc.document_id
    WHERE md.project_id = match_project_id
      AND dc.embedding  IS NOT NULL
      AND (1 - (dc.embedding <=> query_embedding)) > match_threshold
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;
