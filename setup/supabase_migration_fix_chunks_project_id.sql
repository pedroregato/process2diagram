-- setup/supabase_migration_fix_chunks_project_id.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Corrige o project_id de chunks cujo project_id está NULL ou diverge
-- do project_id da reunião correspondente.
--
-- Por que isso acontece:
--   Chunks gerados em versões anteriores ou por caminhos de código com bug
--   podem ter project_id = NULL ou herdado incorretamente.
--   O campo meetings.project_id é sempre a fonte de verdade.
--
-- Execute no SQL Editor do Supabase.
-- É idempotente: re-executar não causa efeitos colaterais.
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. Diagnóstico: mostra quantos chunks têm project_id divergente
SELECT
    tc.project_id        AS chunk_project_id,
    m.project_id         AS meeting_project_id,
    COUNT(*)             AS n_chunks,
    COUNT(DISTINCT tc.meeting_id) AS n_meetings
FROM transcript_chunks tc
JOIN meetings m ON m.id = tc.meeting_id
WHERE tc.project_id IS NULL
   OR tc.project_id != m.project_id
GROUP BY tc.project_id, m.project_id;

-- 2. Correção: atualiza project_id dos chunks para o da reunião
UPDATE transcript_chunks tc
SET project_id = m.project_id
FROM meetings m
WHERE tc.meeting_id = m.id
  AND (
      tc.project_id IS NULL
      OR tc.project_id != m.project_id
  );

-- 3. Confirmação: mostra o resultado
SELECT
    p.name               AS projeto,
    COUNT(DISTINCT tc.meeting_id) AS reunioes_indexadas,
    COUNT(tc.id)         AS total_chunks
FROM transcript_chunks tc
JOIN meetings m ON m.id = tc.meeting_id
JOIN projects p ON p.id = m.project_id
GROUP BY p.name
ORDER BY p.name;
