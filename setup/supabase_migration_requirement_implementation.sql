-- Migration: requirement_implementation (PC115)
-- Adiciona campos de implementação à tabela requirements
-- Execução: psycopg2 com conn.autocommit = True

-- Novos campos de implementação
ALTER TABLE requirements
  ADD COLUMN IF NOT EXISTS resolution_notes   text,
  ADD COLUMN IF NOT EXISTS implemented_at     timestamptz;

-- Índice para filtragem rápida por status de implementação
CREATE INDEX IF NOT EXISTS idx_requirements_status
  ON requirements (project_id, status);

-- Comentários descritivos
COMMENT ON COLUMN requirements.resolution_notes IS
  'Descrição da solução adotada para atender o requisito. Preenchido quando o requisito é marcado como implementado.';
COMMENT ON COLUMN requirements.implemented_at IS
  'Timestamp de quando o requisito foi marcado como implementado.';
