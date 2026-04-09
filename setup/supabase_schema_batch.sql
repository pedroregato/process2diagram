-- ─────────────────────────────────────────────────────────────────────────────
-- Process2Diagram — Batch Runner Schema
-- Execute este script no SQL Editor do Supabase Dashboard
-- Pré-requisito: supabase_schema.sql já executado (tabelas projects e meetings existem)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS batch_log (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    meeting_id       UUID REFERENCES meetings(id) ON DELETE SET NULL,
    filename         TEXT NOT NULL,
    file_hash        TEXT NOT NULL,     -- SHA-256 parcial do conteúdo (deduplicação)
    status           TEXT NOT NULL DEFAULT 'done',  -- done | failed | duplicate
    req_new          INTEGER DEFAULT 0,
    req_revised      INTEGER DEFAULT 0,
    req_contradicted INTEGER DEFAULT 0,
    req_confirmed    INTEGER DEFAULT 0,
    n_terms          INTEGER DEFAULT 0,
    n_rules          INTEGER DEFAULT 0,
    error_detail     TEXT,
    processed_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_batch_log_project ON batch_log(project_id);
CREATE INDEX IF NOT EXISTS idx_batch_log_hash    ON batch_log(file_hash);

ALTER TABLE batch_log DISABLE ROW LEVEL SECURITY;
