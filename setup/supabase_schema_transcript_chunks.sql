-- setup/supabase_schema_transcript_chunks.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Tabela de chunks de transcrição com embeddings para busca semântica (pgvector).
--
-- Modelo: gemini-embedding-001 (3072 dims nativos)
--
-- Pré-requisito: extensão vector já instalada no projeto Supabase.
-- (Supabase habilita pgvector por padrão em todos os projetos)
--
-- Execute este script no SQL Editor do Supabase.
-- ─────────────────────────────────────────────────────────────────────────────

-- Garante que a extensão vector está habilitada
CREATE EXTENSION IF NOT EXISTS vector;

-- ── Remove versão anterior (se existir) ───────────────────────────────────────
DROP FUNCTION IF EXISTS match_transcript_chunks(vector(768), uuid, int);
DROP TABLE  IF EXISTS transcript_chunks CASCADE;

-- ── Tabela principal ──────────────────────────────────────────────────────────
CREATE TABLE transcript_chunks (
    id              uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id      uuid         NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    project_id      uuid         NOT NULL,
    chunk_index     integer      NOT NULL,        -- posição do chunk na transcrição (0-based)
    chunk_text      text         NOT NULL,        -- texto do chunk (~500 chars com overlap)
    embedding       vector(3072) NOT NULL,        -- vetor gemini-embedding-001 (3072 dims nativos)
    created_at      timestamptz  DEFAULT now()
);

-- ── Índices ───────────────────────────────────────────────────────────────────
-- IVFFlat para busca por cosine similarity.
-- lists=100 é adequado para coleções de até ~1M chunks.
-- Nota: para vetores de alta dimensão (3072) o HNSW costuma ser mais eficiente,
-- mas o IVFFlat funciona corretamente e está disponível no Supabase gratuito.
CREATE INDEX transcript_chunks_embedding_idx
    ON transcript_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX transcript_chunks_project_idx  ON transcript_chunks (project_id);
CREATE INDEX transcript_chunks_meeting_idx  ON transcript_chunks (meeting_id);

-- Unique: cada chunk_index deve ser único por reunião
CREATE UNIQUE INDEX transcript_chunks_meeting_chunk_idx
    ON transcript_chunks (meeting_id, chunk_index);

-- ── RLS desabilitado (acesso via service key) ─────────────────────────────────
ALTER TABLE transcript_chunks DISABLE ROW LEVEL SECURITY;

-- ── Função de busca semântica ─────────────────────────────────────────────────
-- Retorna os chunks mais similares a um embedding de consulta, filtrados por projeto.
-- Uso: SELECT * FROM match_transcript_chunks(query_embedding, project_id_val, match_count);
CREATE OR REPLACE FUNCTION match_transcript_chunks(
    query_embedding   vector(3072),
    filter_project_id uuid,
    match_count       int DEFAULT 8
)
RETURNS TABLE (
    id          uuid,
    meeting_id  uuid,
    project_id  uuid,
    chunk_index integer,
    chunk_text  text,
    similarity  float
)
LANGUAGE sql STABLE
AS $$
    SELECT
        tc.id,
        tc.meeting_id,
        tc.project_id,
        tc.chunk_index,
        tc.chunk_text,
        1 - (tc.embedding <=> query_embedding) AS similarity
    FROM transcript_chunks tc
    WHERE tc.project_id = filter_project_id
    ORDER BY tc.embedding <=> query_embedding
    LIMIT match_count;
$$;

-- ── Comentários ───────────────────────────────────────────────────────────────
COMMENT ON TABLE transcript_chunks IS
    'Chunks de transcrição com embeddings vetoriais para busca semântica via pgvector.';
COMMENT ON COLUMN transcript_chunks.embedding IS
    'Vetor de 3072 dimensões — gemini-embedding-001 (dimensão nativa completa).';
COMMENT ON FUNCTION match_transcript_chunks IS
    'Busca semântica por cosine similarity. Retorna top-K chunks mais similares ao embedding da consulta.';
