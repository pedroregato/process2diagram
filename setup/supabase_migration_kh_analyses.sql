-- =============================================================================
-- supabase_migration_kh_analyses.sql
-- Tabela de Análises Autônomas — AgentAnalyst (Feature B)
-- Process2Diagram · FGV/DTI · Maio 2026
-- =============================================================================
-- Aplique via Supabase Dashboard → SQL Editor.
-- Idempotente: usa CREATE TABLE IF NOT EXISTS e IF NOT EXISTS nos índices/políticas.
-- =============================================================================

CREATE TABLE IF NOT EXISTS kh_analyses (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id   UUID         NOT NULL
                               REFERENCES projects(id)
                               ON DELETE CASCADE
                               ON UPDATE CASCADE,

    -- Objetivo analítico submetido pelo usuário
    objective    TEXT         NOT NULL,

    -- Conclusão final produzida pelo agente
    conclusion   TEXT,

    -- Passos ReAct serializados como JSONB (list[ReActStep])
    steps_json   JSONB        DEFAULT '[]',

    -- Tabelas geradas via render_table (para re-renderizar Excel)
    tables_json  JSONB        DEFAULT '[]',

    -- Métricas de execução
    tokens_used  INT          DEFAULT 0,
    duration_s   FLOAT,
    step_count   INT          DEFAULT 0,

    -- Autoria
    created_by   TEXT,        -- username da sessão

    -- Status
    success      BOOLEAN      NOT NULL DEFAULT TRUE,
    error_msg    TEXT,        -- preenchido quando success = FALSE

    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

COMMENT ON TABLE  kh_analyses               IS 'Análises autônomas geradas pelo AgentAnalyst (LangChain ReAct)';
COMMENT ON COLUMN kh_analyses.steps_json    IS 'Cadeia de raciocínio ReAct serializada: [{type, label, content, tool_name, observation}]';
COMMENT ON COLUMN kh_analyses.tables_json   IS 'Tabelas geradas via render_table durante a análise';
COMMENT ON COLUMN kh_analyses.duration_s    IS 'Tempo total de execução em segundos';


-- ─────────────────────────────────────────────────────────────────────────────
-- ÍNDICES
-- ─────────────────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_kh_analyses_project_created
    ON kh_analyses (project_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_kh_analyses_success
    ON kh_analyses (project_id, success)
    WHERE success = TRUE;


-- ─────────────────────────────────────────────────────────────────────────────
-- ROW LEVEL SECURITY
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE kh_analyses ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS kh_analyses_select ON kh_analyses;
CREATE POLICY kh_analyses_select
    ON kh_analyses FOR SELECT
    USING (true);

DROP POLICY IF EXISTS kh_analyses_write ON kh_analyses;
CREATE POLICY kh_analyses_write
    ON kh_analyses FOR ALL
    USING (auth.role() = 'service_role');


-- ─────────────────────────────────────────────────────────────────────────────
-- VERIFICAÇÃO PÓS-MIGRAÇÃO
-- ─────────────────────────────────────────────────────────────────────────────
/*
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_name = 'kh_analyses'
ORDER BY ordinal_position;

SELECT COUNT(*) FROM kh_analyses;
*/
