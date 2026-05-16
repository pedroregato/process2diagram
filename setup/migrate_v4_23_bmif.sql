-- =============================================================================
-- migrate_v4_23_bmif.sql
-- Business Meeting Intelligence Framework (BMIF) — Schema completo
-- Fases A, B, C, D, E do plano estratégico (melhorias/BMIF-Strategic-Plan.md)
--
-- Seguro para re-execução: usa CREATE TABLE IF NOT EXISTS e ADD COLUMN IF NOT EXISTS.
-- Ordem de execução: Fase A → Fase B → Fase C → Fase D → Fase E
-- Fase F não requer DDL (usa infraestrutura existente do Assistente).
-- =============================================================================


-- =============================================================================
-- FASE A — DMN: Formalização de Decisões
-- Referência: OMG Decision Model and Notation 1.4
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- dmn_models — um registro por extração de reunião (análogo a bpmn_processes,
-- mas DMN é gerado por reunião, não por processo de negócio recorrente).
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dmn_models (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID        NOT NULL REFERENCES contexts(id)  ON DELETE CASCADE,
    meeting_id      UUID        NOT NULL REFERENCES meetings(id)  ON DELETE CASCADE,
    model_name      TEXT        NOT NULL DEFAULT '',      -- ex: "Decisões — Reunião 12"
    dmn_xml         TEXT,                                 -- DMN 1.4 XML gerado
    decisions_json  JSONB       NOT NULL DEFAULT '[]',    -- estrutura para viewer/export
    decisions_count INT         NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  dmn_models                IS 'Modelos DMN gerados por reunião — um registro por pipeline run com DMN ativo';
COMMENT ON COLUMN dmn_models.dmn_xml        IS 'XML DMN 1.4 completo, pronto para download e importação em ferramentas DMN';
COMMENT ON COLUMN dmn_models.decisions_json IS 'Array de decisões estruturadas para renderização no viewer interno';

-- ─────────────────────────────────────────────────────────────────────────────
-- dmn_decisions — decisões individuais de um modelo (para consultas cross-meeting
-- no Assistente e métricas no ContextHealth).
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS dmn_decisions (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id        UUID        NOT NULL REFERENCES dmn_models(id) ON DELETE CASCADE,
    project_id      UUID        NOT NULL REFERENCES contexts(id)   ON DELETE CASCADE,
    meeting_id      UUID        NOT NULL REFERENCES meetings(id)   ON DELETE CASCADE,
    decision_id     TEXT        NOT NULL DEFAULT '',   -- ID interno DMN (ex: "D1", "D2")
    name            TEXT        NOT NULL,              -- nome da decisão
    question        TEXT,                              -- pergunta que a decisão responde
    rationale       TEXT,                              -- justificativa e contexto
    decided_by      TEXT[]      NOT NULL DEFAULT '{}', -- participantes que decidiram
    confidence      FLOAT       NOT NULL DEFAULT 1.0
                                CHECK (confidence BETWEEN 0.0 AND 1.0),
    linked_fact_id  UUID        REFERENCES kh_facts(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  dmn_decisions              IS 'Decisões individuais extraídas e formalizadas como tabelas DMN';
COMMENT ON COLUMN dmn_decisions.question     IS 'Pergunta de negócio que esta decisão responde (ex: "Quando aprovar sem assinatura adicional?")';
COMMENT ON COLUMN dmn_decisions.decided_by   IS 'Participantes da reunião que tomaram ou confirmaram a decisão';
COMMENT ON COLUMN dmn_decisions.linked_fact_id IS 'FK para kh_facts.type=decision correspondente (rastreabilidade)';

-- Índices Fase A
CREATE INDEX IF NOT EXISTS idx_dmn_models_project    ON dmn_models   (project_id);
CREATE INDEX IF NOT EXISTS idx_dmn_models_meeting    ON dmn_models   (meeting_id);
CREATE INDEX IF NOT EXISTS idx_dmn_decisions_model   ON dmn_decisions (model_id);
CREATE INDEX IF NOT EXISTS idx_dmn_decisions_project ON dmn_decisions (project_id);
CREATE INDEX IF NOT EXISTS idx_dmn_decisions_meeting ON dmn_decisions (meeting_id);

-- Triggers updated_at
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END; $$;

DROP TRIGGER IF EXISTS trg_dmn_models_updated_at ON dmn_models;
CREATE TRIGGER trg_dmn_models_updated_at
    BEFORE UPDATE ON dmn_models FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- RLS Fase A
ALTER TABLE dmn_models    ENABLE ROW LEVEL SECURITY;
ALTER TABLE dmn_decisions ENABLE ROW LEVEL SECURITY;

CREATE POLICY dmn_models_select    ON dmn_models    FOR SELECT USING (true);
CREATE POLICY dmn_decisions_select ON dmn_decisions FOR SELECT USING (true);
CREATE POLICY dmn_models_write     ON dmn_models    FOR ALL    USING (auth.role() = 'service_role');
CREATE POLICY dmn_decisions_write  ON dmn_decisions FOR ALL    USING (auth.role() = 'service_role');


-- =============================================================================
-- FASE B — Atos de Diálogo (ISO 24617-2 simplificado)
-- Enriquece kh_facts com o ato pragmático do trecho + tabela dedicada
-- para atos que não geraram um fato estruturado (perguntas em aberto, etc.)
-- =============================================================================

-- Coluna dialogue_act em kh_facts — classifica o ato comunicativo do fato
ALTER TABLE kh_facts
    ADD COLUMN IF NOT EXISTS dialogue_act TEXT
    CHECK (dialogue_act IN (
        'decision','commitment','objection','risk',
        'open_question','agreement','exception','revision'
    ));

ALTER TABLE kh_facts
    ADD COLUMN IF NOT EXISTS utterance_speaker TEXT;   -- falante que gerou o fato

COMMENT ON COLUMN kh_facts.dialogue_act       IS 'Ato de diálogo ISO 24617-2 simplificado: decision|commitment|objection|risk|open_question|agreement|exception|revision';
COMMENT ON COLUMN kh_facts.utterance_speaker  IS 'Participante cujo trecho de fala originou este fato';

-- ─────────────────────────────────────────────────────────────────────────────
-- meeting_dialogue_acts — atos de diálogo relevantes que NÃO geraram um
-- kh_fact estruturado (ex: pergunta em aberto sem resposta, objeção isolada).
-- Permite medir resolução da reunião independentemente dos fatos consolidados.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS meeting_dialogue_acts (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID        NOT NULL REFERENCES contexts(id)  ON DELETE CASCADE,
    meeting_id      UUID        NOT NULL REFERENCES meetings(id)  ON DELETE CASCADE,
    dialogue_act    TEXT        NOT NULL
                                CHECK (dialogue_act IN (
                                    'decision','commitment','objection','risk',
                                    'open_question','agreement','exception','revision'
                                )),
    content         TEXT        NOT NULL,     -- trecho ou resumo do ato
    speaker         TEXT,                     -- participante (quando identificável)
    resolved        BOOLEAN     NOT NULL DEFAULT FALSE,
    resolution_note TEXT,                     -- como foi resolvido (ex: virou requisito)
    linked_fact_id  UUID        REFERENCES kh_facts(id)        ON DELETE SET NULL,
    linked_req_id   UUID        REFERENCES requirements(id)    ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  meeting_dialogue_acts             IS 'Atos de diálogo classificados por reunião (ISO 24617-2 simplificado)';
COMMENT ON COLUMN meeting_dialogue_acts.dialogue_act IS 'Tipo do ato: decision|commitment|objection|risk|open_question|agreement|exception|revision';
COMMENT ON COLUMN meeting_dialogue_acts.resolved     IS 'TRUE quando o ato foi endereçado (pergunta respondida, objeção considerada, etc.)';
COMMENT ON COLUMN meeting_dialogue_acts.linked_fact_id IS 'FK para kh_facts se o ato gerou um fato consolidado';
COMMENT ON COLUMN meeting_dialogue_acts.linked_req_id  IS 'FK para requirements se o ato gerou um requisito formal';

-- Índices Fase B
CREATE INDEX IF NOT EXISTS idx_dialogue_acts_project    ON meeting_dialogue_acts (project_id);
CREATE INDEX IF NOT EXISTS idx_dialogue_acts_meeting    ON meeting_dialogue_acts (meeting_id);
CREATE INDEX IF NOT EXISTS idx_dialogue_acts_type       ON meeting_dialogue_acts (project_id, dialogue_act);
CREATE INDEX IF NOT EXISTS idx_dialogue_acts_unresolved ON meeting_dialogue_acts (project_id)
    WHERE resolved = FALSE;
CREATE INDEX IF NOT EXISTS idx_kh_facts_dialogue_act    ON kh_facts (project_id, dialogue_act)
    WHERE dialogue_act IS NOT NULL;

-- RLS Fase B
ALTER TABLE meeting_dialogue_acts ENABLE ROW LEVEL SECURITY;

CREATE POLICY dialogue_acts_select ON meeting_dialogue_acts FOR SELECT USING (true);
CREATE POLICY dialogue_acts_write  ON meeting_dialogue_acts FOR ALL    USING (auth.role() = 'service_role');


-- =============================================================================
-- FASE C — Mapa de Argumentação IBIS
-- Referência: Issue-Based Information System (IBIS) + Dialogue Mapping
-- =============================================================================

-- ─────────────────────────────────────────────────────────────────────────────
-- argumentation_maps — um mapa por reunião; armazena o JSON completo IBIS
-- e estatísticas pré-calculadas para ContextHealth.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS argumentation_maps (
    id               UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       UUID        NOT NULL REFERENCES contexts(id)  ON DELETE CASCADE,
    meeting_id       UUID        NOT NULL REFERENCES meetings(id)  ON DELETE CASCADE,
    map_json         JSONB       NOT NULL DEFAULT '{}',   -- estrutura IBIS completa
    questions_count  INT         NOT NULL DEFAULT 0,
    resolved_count   INT         NOT NULL DEFAULT 0,      -- resolution_type = 'decided'
    deferred_count   INT         NOT NULL DEFAULT 0,      -- resolution_type = 'deferred'
    unresolved_count INT         NOT NULL DEFAULT 0,      -- resolution_type = 'unresolved'
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  argumentation_maps                  IS 'Mapas de argumentação IBIS por reunião — captura o raciocínio por trás das decisões';
COMMENT ON COLUMN argumentation_maps.map_json         IS 'Estrutura IBIS completa com questões, alternativas, pros/cons e resoluções';
COMMENT ON COLUMN argumentation_maps.resolved_count   IS 'Questões com decisão tomada na reunião';
COMMENT ON COLUMN argumentation_maps.unresolved_count IS 'Questões em aberto ao final da reunião — indicador de resolução';

-- ─────────────────────────────────────────────────────────────────────────────
-- ibis_questions — questões individuais para consulta cross-meeting.
-- Permite rastrear questões recorrentes entre reuniões diferentes.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ibis_questions (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    map_id              UUID        NOT NULL REFERENCES argumentation_maps(id) ON DELETE CASCADE,
    project_id          UUID        NOT NULL REFERENCES contexts(id)  ON DELETE CASCADE,
    meeting_id          UUID        NOT NULL REFERENCES meetings(id)  ON DELETE CASCADE,
    statement           TEXT        NOT NULL,    -- "Como deve ser feita a triagem?"
    raised_by           TEXT,                    -- participante que trouxe a questão
    resolution_type     TEXT        NOT NULL DEFAULT 'unresolved'
                                    CHECK (resolution_type IN ('decided','deferred','unresolved')),
    chosen_alternative  TEXT,                    -- descrição da alternativa escolhida
    rationale           TEXT,                    -- justificativa da decisão tomada
    with_caveats        TEXT[]      NOT NULL DEFAULT '{}',  -- ressalvas registradas
    linked_dmn_id       UUID        REFERENCES dmn_decisions(id) ON DELETE SET NULL,
    linked_fact_id      UUID        REFERENCES kh_facts(id)      ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  ibis_questions                   IS 'Questões IBIS individuais — permite rastrear temas recorrentes entre reuniões';
COMMENT ON COLUMN ibis_questions.resolution_type   IS 'decided | deferred | unresolved';
COMMENT ON COLUMN ibis_questions.with_caveats      IS 'Ressalvas ou condições registradas junto com a decisão';
COMMENT ON COLUMN ibis_questions.linked_dmn_id     IS 'FK para dmn_decisions quando a questão gerou uma tabela DMN formal';
COMMENT ON COLUMN ibis_questions.linked_fact_id    IS 'FK para kh_facts.type=decision correspondente';

-- ─────────────────────────────────────────────────────────────────────────────
-- ibis_alternatives — alternativas avaliadas por questão.
-- Captura o "o que mais foi considerado" além da decisão tomada.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ibis_alternatives (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id  UUID        NOT NULL REFERENCES ibis_questions(id) ON DELETE CASCADE,
    description  TEXT        NOT NULL,            -- alternativa proposta
    proposed_by  TEXT,                            -- participante que sugeriu
    pros         TEXT[]      NOT NULL DEFAULT '{}',
    cons         TEXT[]      NOT NULL DEFAULT '{}',
    supported_by TEXT[]      NOT NULL DEFAULT '{}',  -- participantes a favor
    opposed_by   TEXT[]      NOT NULL DEFAULT '{}',  -- participantes contra
    was_chosen   BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE  ibis_alternatives            IS 'Alternativas avaliadas para cada questão IBIS — preserva o raciocínio de escolha';
COMMENT ON COLUMN ibis_alternatives.was_chosen IS 'TRUE para a alternativa que se tornou a decisão';
COMMENT ON COLUMN ibis_alternatives.pros       IS 'Argumentos a favor levantados na reunião';
COMMENT ON COLUMN ibis_alternatives.cons       IS 'Argumentos contra levantados na reunião';

-- Índices Fase C
CREATE INDEX IF NOT EXISTS idx_arg_maps_project       ON argumentation_maps (project_id);
CREATE INDEX IF NOT EXISTS idx_arg_maps_meeting       ON argumentation_maps (meeting_id);
CREATE INDEX IF NOT EXISTS idx_ibis_q_project         ON ibis_questions     (project_id);
CREATE INDEX IF NOT EXISTS idx_ibis_q_meeting         ON ibis_questions     (meeting_id);
CREATE INDEX IF NOT EXISTS idx_ibis_q_unresolved      ON ibis_questions     (project_id)
    WHERE resolution_type = 'unresolved';
CREATE INDEX IF NOT EXISTS idx_ibis_alt_question      ON ibis_alternatives  (question_id);

-- Trigger updated_at Fase C
DROP TRIGGER IF EXISTS trg_arg_maps_updated_at ON argumentation_maps;
CREATE TRIGGER trg_arg_maps_updated_at
    BEFORE UPDATE ON argumentation_maps FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- RLS Fase C
ALTER TABLE argumentation_maps ENABLE ROW LEVEL SECURITY;
ALTER TABLE ibis_questions     ENABLE ROW LEVEL SECURITY;
ALTER TABLE ibis_alternatives  ENABLE ROW LEVEL SECURITY;

CREATE POLICY arg_maps_select  ON argumentation_maps FOR SELECT USING (true);
CREATE POLICY ibis_q_select    ON ibis_questions     FOR SELECT USING (true);
CREATE POLICY ibis_alt_select  ON ibis_alternatives  FOR SELECT USING (true);
CREATE POLICY arg_maps_write   ON argumentation_maps FOR ALL    USING (auth.role() = 'service_role');
CREATE POLICY ibis_q_write     ON ibis_questions     FOR ALL    USING (auth.role() = 'service_role');
CREATE POLICY ibis_alt_write   ON ibis_alternatives  FOR ALL    USING (auth.role() = 'service_role');


-- =============================================================================
-- FASE D — Knowledge Graph (View para visualização)
-- Nenhuma tabela nova: o grafo é construído sobre dados existentes.
-- Esta view facilita a consulta unificada de nós e arestas.
-- =============================================================================

CREATE OR REPLACE VIEW v_knowledge_graph_nodes AS
    SELECT 'entity'       AS node_type,
           id::TEXT       AS node_id,
           canonical_name AS label,
           entity_type    AS subtype,
           project_id,
           NULL::UUID     AS meeting_id
    FROM kh_entities
UNION ALL
    SELECT 'fact',
           id::TEXT,
           LEFT(content, 100),
           fact_type,
           project_id,
           (source_meeting_ids)[1]
    FROM kh_facts
    WHERE is_active = TRUE
UNION ALL
    SELECT 'requirement',
           id::TEXT,
           CONCAT('REQ-', req_number, ': ', LEFT(title, 80)),
           req_type,
           project_id,
           NULL::UUID
    FROM requirements
UNION ALL
    SELECT 'dmn_decision',
           id::TEXT,
           LEFT(name, 100),
           'dmn_decision',
           project_id,
           meeting_id
    FROM dmn_decisions
UNION ALL
    SELECT 'ibis_question',
           id::TEXT,
           LEFT(statement, 100),
           resolution_type,
           project_id,
           meeting_id
    FROM ibis_questions;

COMMENT ON VIEW v_knowledge_graph_nodes IS
    'Nós unificados do grafo de conhecimento: entities, facts, requirements, DMN decisions, IBIS questions';


-- =============================================================================
-- FASE E — Enriquecimento BABOK da Ata
-- Referência: BABOK Guide v3 — Elicitation and Collaboration
-- Adiciona colunas JSONB em meetings para os campos de elicitação BABOK
-- que AgentMinutes passará a extrair.
-- =============================================================================

-- Premissas explícitas declaradas na reunião
ALTER TABLE meetings
    ADD COLUMN IF NOT EXISTS assumptions       JSONB NOT NULL DEFAULT '[]';

-- Perguntas sem resposta ao final da reunião (distintas de action items)
ALTER TABLE meetings
    ADD COLUMN IF NOT EXISTS open_questions    JSONB NOT NULL DEFAULT '[]';

-- Riscos mencionados (distintos de requisitos não-funcionais)
ALTER TABLE meetings
    ADD COLUMN IF NOT EXISTS risks_identified  JSONB NOT NULL DEFAULT '[]';

-- Dependências entre times, sistemas ou entregas identificadas
ALTER TABLE meetings
    ADD COLUMN IF NOT EXISTS dependencies      JSONB NOT NULL DEFAULT '[]';

-- Necessidades de stakeholder expressas informalmente (pré-requisito)
ALTER TABLE meetings
    ADD COLUMN IF NOT EXISTS stakeholder_needs JSONB NOT NULL DEFAULT '[]';

COMMENT ON COLUMN meetings.assumptions       IS 'BABOK: premissas explícitas declaradas na reunião (array de strings)';
COMMENT ON COLUMN meetings.open_questions    IS 'BABOK: perguntas sem resposta registradas ao final da reunião';
COMMENT ON COLUMN meetings.risks_identified  IS 'BABOK: riscos mencionados (sem formalização como requisito)';
COMMENT ON COLUMN meetings.dependencies      IS 'BABOK: dependências entre times, sistemas ou entregas identificadas';
COMMENT ON COLUMN meetings.stakeholder_needs IS 'BABOK: necessidades de stakeholders expressas informalmente';


-- =============================================================================
-- VERIFICAÇÃO PÓS-MIGRAÇÃO
-- Execute para confirmar que tudo foi criado corretamente:
-- =============================================================================
/*
SELECT table_name, COUNT(*) AS colunas
FROM information_schema.columns
WHERE table_name IN (
    'dmn_models', 'dmn_decisions',
    'meeting_dialogue_acts',
    'argumentation_maps', 'ibis_questions', 'ibis_alternatives'
)
GROUP BY table_name
ORDER BY table_name;

SELECT indexname, tablename
FROM pg_indexes
WHERE tablename IN (
    'dmn_models', 'dmn_decisions',
    'meeting_dialogue_acts',
    'argumentation_maps', 'ibis_questions', 'ibis_alternatives',
    'kh_facts'
)
ORDER BY tablename, indexname;

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'meetings'
  AND column_name IN ('assumptions','open_questions','risks_identified','dependencies','stakeholder_needs')
ORDER BY column_name;

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'kh_facts'
  AND column_name IN ('dialogue_act','utterance_speaker')
ORDER BY column_name;
*/
