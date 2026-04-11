-- ─────────────────────────────────────────────────────────────────────────────
-- Process2Diagram — Schema: bpmn_processes + bpmn_versions
-- Execute no SQL Editor do Supabase Dashboard
-- Seguro para re-execução (CREATE TABLE IF NOT EXISTS).
-- ─────────────────────────────────────────────────────────────────────────────

-- ─────────────────────────────────────────────────────────────────────────────
-- PROCESSOS BPMN — identidade única de um fluxo de processo (N reuniões
-- podem gerar versões do mesmo processo; slug normalizado permite
-- correspondência automática pelo nome).
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bpmn_processes (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name             TEXT NOT NULL,          -- nome de exibição (ex: "Gestão de Contratos")
    slug             TEXT NOT NULL,          -- normalizado p/ matching auto (ex: "gestao_contratos")
    description      TEXT,
    status           TEXT DEFAULT 'active',  -- active | archived
    first_meeting_id UUID REFERENCES meetings(id) ON DELETE SET NULL,
    last_meeting_id  UUID REFERENCES meetings(id) ON DELETE SET NULL,
    version_count    INTEGER DEFAULT 0,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (project_id, slug)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- VERSÕES BPMN — um registro por (processo × pipeline run)
-- Cada vez que um pipeline gera um BPMN para um processo, uma versão é
-- criada. is_current = TRUE marca a versão mais recente.
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bpmn_versions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    process_id   UUID NOT NULL REFERENCES bpmn_processes(id) ON DELETE CASCADE,
    meeting_id   UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    project_id   UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    version      INTEGER NOT NULL,    -- 1, 2, 3... (sequencial por processo)
    bpmn_xml     TEXT,
    mermaid_code TEXT,
    change_notes TEXT,                -- notas automáticas ou do usuário
    is_current   BOOLEAN DEFAULT TRUE,
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (process_id, version)
);

-- ─────────────────────────────────────────────────────────────────────────────
-- ÍNDICES
-- ─────────────────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_bpmn_proc_project ON bpmn_processes(project_id);
CREATE INDEX IF NOT EXISTS idx_bpmn_proc_slug    ON bpmn_processes(project_id, slug);
CREATE INDEX IF NOT EXISTS idx_bpmn_ver_process  ON bpmn_versions(process_id);
CREATE INDEX IF NOT EXISTS idx_bpmn_ver_meeting  ON bpmn_versions(meeting_id);
CREATE INDEX IF NOT EXISTS idx_bpmn_ver_current  ON bpmn_versions(process_id, is_current)
    WHERE is_current = TRUE;

-- ─────────────────────────────────────────────────────────────────────────────
-- RLS — desabilitado para uso via service_role (Streamlit backend)
-- ─────────────────────────────────────────────────────────────────────────────
ALTER TABLE bpmn_processes DISABLE ROW LEVEL SECURITY;
ALTER TABLE bpmn_versions  DISABLE ROW LEVEL SECURITY;
