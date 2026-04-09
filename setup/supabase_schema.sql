-- ─────────────────────────────────────────────────────────────────────────────
-- Process2Diagram — Supabase Schema
-- Execute este script no SQL Editor do Supabase Dashboard
-- ─────────────────────────────────────────────────────────────────────────────

-- Habilita extensão pgvector para busca semântica (F3)
CREATE EXTENSION IF NOT EXISTS vector;

-- ─────────────────────────────────────────────────────────────────────────────
-- PROJETOS / INICIATIVAS
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS projects (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- REUNIÕES
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS meetings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    meeting_date    DATE,
    meeting_number  INTEGER,          -- sequencial dentro do projeto
    transcript_raw  TEXT,
    transcript_clean TEXT,
    bpmn_xml        TEXT,
    mermaid_code    TEXT,
    minutes_md      TEXT,
    report_html     TEXT,
    llm_provider    TEXT,
    total_tokens    INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- REQUISITOS — registro mestre (um por REQ-XXX por projeto)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS requirements (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    req_number       INTEGER NOT NULL,   -- 1, 2, 3... (exibido como REQ-001)
    title            TEXT NOT NULL,
    description      TEXT,
    req_type         TEXT,               -- functional | non-functional | business | etc.
    priority         TEXT,               -- high | medium | low
    status           TEXT DEFAULT 'active',  -- active | revised | contradicted | deprecated
    embedding        vector(768),        -- Google Gemini text-embedding-004 (F3)
    first_meeting_id UUID REFERENCES meetings(id),
    last_meeting_id  UUID REFERENCES meetings(id),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (project_id, req_number)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- VERSÕES DE REQUISITOS — histórico completo
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS requirement_versions (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    requirement_id       UUID NOT NULL REFERENCES requirements(id) ON DELETE CASCADE,
    meeting_id           UUID NOT NULL REFERENCES meetings(id),
    version              INTEGER NOT NULL,  -- 1, 2, 3...
    title                TEXT NOT NULL,
    description          TEXT,
    req_type             TEXT,
    priority             TEXT,
    change_type          TEXT NOT NULL,     -- new | confirmed | revised | contradicted
    change_summary       TEXT,              -- "campo login: 20 → 120 caracteres"
    contradiction_flag   BOOLEAN DEFAULT FALSE,
    contradiction_detail TEXT,              -- análise LLM quando contradicted
    created_at           TIMESTAMPTZ DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────────────
-- ÍNDICES
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_meetings_project      ON meetings(project_id);
CREATE INDEX IF NOT EXISTS idx_requirements_project  ON requirements(project_id);
CREATE INDEX IF NOT EXISTS idx_req_versions_req      ON requirement_versions(requirement_id);
CREATE INDEX IF NOT EXISTS idx_req_versions_meeting  ON requirement_versions(meeting_id);
CREATE INDEX IF NOT EXISTS idx_req_status            ON requirements(status);
CREATE INDEX IF NOT EXISTS idx_req_contradiction     ON requirement_versions(contradiction_flag)
    WHERE contradiction_flag = TRUE;

-- Índice vetorial para busca semântica (F3)
CREATE INDEX IF NOT EXISTS idx_req_embedding ON requirements
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ─────────────────────────────────────────────────────────────────────────────
-- FUNÇÃO: próximo número de requisito por projeto
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION next_req_number(p_project_id UUID)
RETURNS INTEGER AS $$
    SELECT COALESCE(MAX(req_number), 0) + 1
    FROM requirements
    WHERE project_id = p_project_id;
$$ LANGUAGE SQL STABLE;

-- ─────────────────────────────────────────────────────────────────────────────
-- RLS — desabilitado para uso via service_role (Streamlit backend)
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE projects              DISABLE ROW LEVEL SECURITY;
ALTER TABLE meetings              DISABLE ROW LEVEL SECURITY;
ALTER TABLE requirements          DISABLE ROW LEVEL SECURITY;
ALTER TABLE requirement_versions  DISABLE ROW LEVEL SECURITY;
