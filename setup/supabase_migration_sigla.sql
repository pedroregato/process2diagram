-- ─────────────────────────────────────────────────────────────────────────────
-- Process2Diagram — Migração: sigla em contexts
-- Execute no SQL Editor do Supabase Dashboard
-- Seguro para re-execução (ADD COLUMN IF NOT EXISTS).
-- ─────────────────────────────────────────────────────────────────────────────

-- Adiciona a coluna sigla à tabela contexts.
-- Projetos existentes ficam com string vazia; editar manualmente no Supabase
-- ou pelo app ao criar novos projetos.
ALTER TABLE contexts
    ADD COLUMN IF NOT EXISTS sigla TEXT NOT NULL DEFAULT '';
