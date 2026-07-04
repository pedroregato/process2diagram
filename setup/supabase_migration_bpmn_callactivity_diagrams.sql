-- setup/supabase_migration_bpmn_callactivity_diagrams.sql
-- PC120: diagramas de detalhe sob demanda para elementos callActivity.
--
-- Um diagrama BPMN (bpmn_versions) pode ter N callActivity — cada uma pode
-- ganhar um diagrama detalhado independente, gerado sob demanda a partir da
-- <documentation> da callActivity (reaproveitando AgentBPMN, mesmo padrão do
-- BPMN Studio). Tabela separada, não coluna em bpmn_versions, porque é uma
-- relação 1-para-N (um diagrama pai, várias callActivity detalhadas).
--
-- is_current + índice único parcial seguem o mesmo padrão de bpmn_versions:
-- permite regenerar um detalhamento insatisfatório sem perder o histórico.
-- ON DELETE CASCADE em bpmn_version_id: apagar a versão pai limpa seus
-- detalhamentos automaticamente.
--
-- Seguro para re-execução (CREATE TABLE/INDEX IF NOT EXISTS).

CREATE TABLE IF NOT EXISTS bpmn_callactivity_diagrams (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bpmn_version_id     UUID NOT NULL REFERENCES bpmn_versions(id) ON DELETE CASCADE,
    element_id          TEXT NOT NULL,   -- id do callActivity no XML pai (ex: "p1_S01")
    element_name        TEXT NOT NULL,   -- nome exibido no diagrama pai (cache p/ listar sem reparse)
    pool_name           TEXT,            -- participant/pool a que a callActivity pertence
    source_description  TEXT,            -- documentation da callActivity usada como entrada do agente
    bpmn_xml            TEXT NOT NULL,
    mermaid_code        TEXT,
    bpmn_score          JSONB,           -- score do AgentValidator, se o torneio rodou
    is_current          BOOLEAN DEFAULT TRUE,
    created_by          TEXT,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bpmn_callact_version
    ON bpmn_callactivity_diagrams(bpmn_version_id);

CREATE UNIQUE INDEX IF NOT EXISTS uq_bpmn_callact_current
    ON bpmn_callactivity_diagrams(bpmn_version_id, element_id)
    WHERE is_current = TRUE;

ALTER TABLE bpmn_callactivity_diagrams ENABLE ROW LEVEL SECURITY;
