-- ============================================================
-- Process2Diagram — Migration v4.21
-- Rename: projects → contexts
-- Add: contexts.skill_md, contexts.context_type
-- ============================================================
-- Execute via Supabase SQL Editor before deploying v4.21 code.
-- Verify: Table Editor should show table "contexts" after execution.
-- ============================================================

-- 1. Renomear tabela principal
ALTER TABLE projects RENAME TO contexts;

-- 2. Adicionar coluna de tipo de contexto
ALTER TABLE contexts
    ADD COLUMN IF NOT EXISTS context_type TEXT DEFAULT 'project';
-- Valores válidos: 'project' | 'product' | 'feasibility' | 'strategic' | 'meeting_series' | 'discussion' | 'other'

-- 3. Adicionar coluna para o Context Knowledge File (CKF)
ALTER TABLE contexts
    ADD COLUMN IF NOT EXISTS skill_md TEXT;

-- 4. Comentários de documentação
COMMENT ON TABLE contexts IS 'Process2Diagram contexts (formerly: projects). A context groups meetings sharing the same organizational universe.';
COMMENT ON COLUMN contexts.context_type IS 'Nature of the context: project | product | feasibility | strategic | meeting_series | discussion | other';
COMMENT ON COLUMN contexts.skill_md IS 'Context Knowledge File (CKF): markdown with participants, glossary, decisions, goals. Injected into agent prompts.';
