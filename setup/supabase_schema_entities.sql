-- setup/supabase_schema_entities.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Tabelas para reconhecimento de entidades (pessoas, áreas, unidades, cargos)
-- nas transcrições de reuniões.
--
-- Execute este script no SQL Editor do Supabase.
-- ─────────────────────────────────────────────────────────────────────────────

-- ── Entidades extraídas automaticamente das transcrições ─────────────────────
CREATE TABLE IF NOT EXISTS meeting_entities (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id       UUID         NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    project_id       UUID         NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    entity_text      TEXT         NOT NULL,
    entity_type      TEXT         NOT NULL,   -- 'PESSOA' | 'AREA' | 'UNIDADE' | 'CARGO'
    normalized_name  TEXT,
    confidence_score FLOAT        DEFAULT 1.0,
    context          TEXT,                    -- trecho onde a entidade aparece
    start_position   INTEGER,
    end_position     INTEGER,
    source           TEXT,                    -- 'spacy' | 'regex' | 'dictionary'
    created_at       TIMESTAMPTZ  DEFAULT now()
);

CREATE INDEX IF NOT EXISTS meeting_entities_project_idx
    ON meeting_entities (project_id);
CREATE INDEX IF NOT EXISTS meeting_entities_meeting_idx
    ON meeting_entities (meeting_id);
CREATE INDEX IF NOT EXISTS meeting_entities_type_idx
    ON meeting_entities (entity_type);
CREATE INDEX IF NOT EXISTS meeting_entities_normalized_idx
    ON meeting_entities (normalized_name);

ALTER TABLE meeting_entities DISABLE ROW LEVEL SECURITY;

-- ── Dicionário de entidades conhecidas (curado por projeto) ──────────────────
CREATE TABLE IF NOT EXISTS entity_dictionary (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID         NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    entity_text     TEXT         NOT NULL,
    normalized_name TEXT         NOT NULL,
    entity_type     TEXT         NOT NULL,   -- 'PESSOA' | 'AREA' | 'UNIDADE' | 'CARGO'
    category        TEXT,                    -- 'INTERNO' | 'EXTERNO' | 'CLIENTE' | 'FORNECEDOR'
    metadata        JSONB        DEFAULT '{}',
    created_at      TIMESTAMPTZ  DEFAULT now(),
    UNIQUE (project_id, entity_text, entity_type)
);

CREATE INDEX IF NOT EXISTS entity_dictionary_project_idx
    ON entity_dictionary (project_id);
CREATE INDEX IF NOT EXISTS entity_dictionary_type_idx
    ON entity_dictionary (entity_type);

ALTER TABLE entity_dictionary DISABLE ROW LEVEL SECURITY;

COMMENT ON TABLE meeting_entities IS
    'Entidades (pessoas, áreas, unidades, cargos) extraídas automaticamente das transcrições via spaCy + regex + dicionário.';
COMMENT ON TABLE entity_dictionary IS
    'Dicionário curado de entidades conhecidas por projeto — alimenta a extração com alta confiança.';
