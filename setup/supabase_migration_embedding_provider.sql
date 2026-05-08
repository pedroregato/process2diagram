-- setup/supabase_migration_embedding_provider.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Adiciona colunas de rastreamento do provedor e modelo de embedding
-- à tabela transcript_chunks.
--
-- Importante: embeddings gerados por provedores ou modelos diferentes NÃO são
-- compatíveis entre si (espaços vetoriais distintos). Estas colunas permitem
-- identificar e isolar chunks de origens incompatíveis.
--
-- Execute no SQL Editor do Supabase (seguro — usa IF NOT EXISTS).
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE transcript_chunks
    ADD COLUMN IF NOT EXISTS embedding_provider TEXT DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS embedding_model     TEXT DEFAULT NULL;

COMMENT ON COLUMN transcript_chunks.embedding_provider IS
    'Provedor que gerou o embedding: ex. "Google Gemini", "OpenAI", "Grok (xAI)".';
COMMENT ON COLUMN transcript_chunks.embedding_model IS
    'Modelo exato usado: ex. "models/gemini-embedding-001", "text-embedding-3-small".';
