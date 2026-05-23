-- setup/supabase_migration_artifact_origin.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Adiciona rastreabilidade de origem (transcrição vs documento) aos artefatos.
--
-- Artefatos afetados: requirements, requirement_versions, sbvr_terms, sbvr_rules
-- Novos campos:
--   origin  TEXT  DEFAULT 'transcricao'  → 'transcricao' | 'documento'
--   doc_ref UUID  REFERENCES meeting_documents(id)  → UUID do documento de origem
--
-- Permite meeting_id = NULL quando origin = 'documento'.
-- Execute uma vez no Supabase → SQL Editor.
-- ─────────────────────────────────────────────────────────────────────────────

-- ── requirements ──────────────────────────────────────────────────────────────
ALTER TABLE requirements
    ADD COLUMN IF NOT EXISTS origin  TEXT DEFAULT 'transcricao',
    ADD COLUMN IF NOT EXISTS doc_ref UUID REFERENCES meeting_documents(id) ON DELETE SET NULL;

-- Permite salvar requisitos sem vínculo de reunião (origem = documento)
ALTER TABLE requirements ALTER COLUMN first_meeting_id DROP NOT NULL;
ALTER TABLE requirements ALTER COLUMN last_meeting_id  DROP NOT NULL;

-- Índices para filtrar por origem
CREATE INDEX IF NOT EXISTS idx_requirements_origin  ON requirements(project_id, origin);
CREATE INDEX IF NOT EXISTS idx_requirements_doc_ref ON requirements(doc_ref) WHERE doc_ref IS NOT NULL;


-- ── requirement_versions ──────────────────────────────────────────────────────
ALTER TABLE requirement_versions
    ADD COLUMN IF NOT EXISTS origin  TEXT DEFAULT 'transcricao',
    ADD COLUMN IF NOT EXISTS doc_ref UUID;

-- Permite versões sem reunião vinculada
ALTER TABLE requirement_versions ALTER COLUMN meeting_id DROP NOT NULL;


-- ── sbvr_terms ────────────────────────────────────────────────────────────────
ALTER TABLE sbvr_terms
    ADD COLUMN IF NOT EXISTS origin  TEXT DEFAULT 'transcricao',
    ADD COLUMN IF NOT EXISTS doc_ref UUID REFERENCES meeting_documents(id) ON DELETE SET NULL;

-- Permite termos extraídos de documentos sem reunião vinculada
ALTER TABLE sbvr_terms ALTER COLUMN meeting_id DROP NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sbvr_terms_origin  ON sbvr_terms(project_id, origin);
CREATE INDEX IF NOT EXISTS idx_sbvr_terms_doc_ref ON sbvr_terms(doc_ref) WHERE doc_ref IS NOT NULL;


-- ── sbvr_rules ────────────────────────────────────────────────────────────────
ALTER TABLE sbvr_rules
    ADD COLUMN IF NOT EXISTS origin  TEXT DEFAULT 'transcricao',
    ADD COLUMN IF NOT EXISTS doc_ref UUID REFERENCES meeting_documents(id) ON DELETE SET NULL;

ALTER TABLE sbvr_rules ALTER COLUMN meeting_id DROP NOT NULL;

CREATE INDEX IF NOT EXISTS idx_sbvr_rules_origin  ON sbvr_rules(project_id, origin);
CREATE INDEX IF NOT EXISTS idx_sbvr_rules_doc_ref ON sbvr_rules(doc_ref) WHERE doc_ref IS NOT NULL;
