-- ─────────────────────────────────────────────────────────────────────────────
-- Migration: adiciona rastreabilidade de origem aos requisitos
--
-- source_quote  — frase verbatim da transcrição que motivou o requisito
-- cited_by      — iniciais do participante que originou a afirmação (ex: "PG")
--
-- Execute no SQL Editor do Supabase Dashboard.
-- Operação segura: IF NOT EXISTS — pode ser executada múltiplas vezes.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE requirements
    ADD COLUMN IF NOT EXISTS source_quote TEXT,
    ADD COLUMN IF NOT EXISTS cited_by     TEXT;

ALTER TABLE requirement_versions
    ADD COLUMN IF NOT EXISTS source_quote TEXT,
    ADD COLUMN IF NOT EXISTS cited_by     TEXT;
