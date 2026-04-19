-- ─────────────────────────────────────────────────────────────────────────────
-- Migration: ciclo de vida completo dos requisitos
--
-- owner       — responsável pelo requisito (pessoa ou equipe)
-- status_note — nota explicativa sobre o status atual (ex: "aprovado em sprint 3")
--
-- Os novos valores de status suportados pela aplicação são:
--   backlog | active | approved | in_progress | implemented |
--   revised | contradicted | deprecated | rejected
--
-- Execute no SQL Editor do Supabase Dashboard.
-- Operação segura: IF NOT EXISTS — pode ser executada múltiplas vezes.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE requirements
    ADD COLUMN IF NOT EXISTS owner       TEXT,
    ADD COLUMN IF NOT EXISTS status_note TEXT;
