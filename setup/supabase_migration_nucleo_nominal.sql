-- ─────────────────────────────────────────────────────────────────────────────
-- Process2Diagram — Migração: nucleo_nominal em sbvr_rules
-- Execute no SQL Editor do Supabase Dashboard
-- Seguro para re-execução (IF NOT EXISTS / IF NOT EXISTS implícito via ADD COLUMN).
-- ─────────────────────────────────────────────────────────────────────────────

-- Adiciona a coluna nucleo_nominal à tabela sbvr_rules.
-- Regras já existentes ficam com string vazia; o app calcula on-the-fly
-- via fallback (modules/text_utils.rule_keyword_pt) para esses registros
-- e gravará o valor nas próximas inserções.
ALTER TABLE sbvr_rules
    ADD COLUMN IF NOT EXISTS nucleo_nominal TEXT NOT NULL DEFAULT '';
