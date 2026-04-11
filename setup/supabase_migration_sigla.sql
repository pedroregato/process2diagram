-- ─────────────────────────────────────────────────────────────────────────────
-- Process2Diagram — Migração: sigla em projects
-- Execute no SQL Editor do Supabase Dashboard
-- Seguro para re-execução (ADD COLUMN IF NOT EXISTS).
-- ─────────────────────────────────────────────────────────────────────────────

-- Adiciona a coluna sigla à tabela projects.
-- Projetos existentes ficam com string vazia; editar manualmente no Supabase
-- ou pelo app ao criar novos projetos.
ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS sigla TEXT NOT NULL DEFAULT '';
