-- ─────────────────────────────────────────────────────────────────────────────
-- Process2Diagram — SBVR Schema (F5)
-- Execute este script no SQL Editor do Supabase Dashboard
-- Pré-requisito: supabase_schema.sql já executado (tabelas projects e meetings existem)
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS sbvr_terms (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id  UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    project_id  UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    term        TEXT NOT NULL,
    definition  TEXT,
    category    TEXT DEFAULT 'concept',  -- concept | fact_type | role | process
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sbvr_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id      UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    rule_id         TEXT,           -- ex: "BR-001" (id gerado pelo LLM)
    statement       TEXT NOT NULL,
    nucleo_nominal  TEXT NOT NULL DEFAULT '',  -- núcleo nominal extraído do statement (calculado 1× na gravação)
    rule_type       TEXT DEFAULT 'constraint',  -- constraint | operational | behavioral | structural
    source          TEXT,           -- iniciais do participante que enunciou a regra
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sbvr_terms_project  ON sbvr_terms(project_id);
CREATE INDEX IF NOT EXISTS idx_sbvr_terms_meeting  ON sbvr_terms(meeting_id);
CREATE INDEX IF NOT EXISTS idx_sbvr_rules_project  ON sbvr_rules(project_id);
CREATE INDEX IF NOT EXISTS idx_sbvr_rules_meeting  ON sbvr_rules(meeting_id);

ALTER TABLE sbvr_terms DISABLE ROW LEVEL SECURITY;
ALTER TABLE sbvr_rules DISABLE ROW LEVEL SECURITY;
