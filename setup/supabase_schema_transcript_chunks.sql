-- setup/supabase_schema_transcript_chunks.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Tabela de chunks de transcrição com embeddings para busca semântica (pgvector).
--
-- Modelo: gemini-embedding-001 truncado para 1536 dims
--         (pgvector ivfflat suporta até 2000 dims; 1536 é o melhor valor prático)
--
-- Execute este script no SQL Editor do Supabase.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS vector;

-- ── Remove versão anterior ────────────────────────────────────────────────────
DROP FUNCTION IF EXISTS match_transcript_chunks(vector(768),  uuid, int);
DROP FUNCTION IF EXISTS match_transcript_chunks(vector(3072), uuid, int);
DROP TABLE  IF EXISTS transcript_chunks CASCADE;

-- ── Tabela principal ──────────────────────────────────────────────────────────
CREATE TABLE transcript_chunks (
    id          uuid         PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id  uuid         NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    project_id  uuid         NOT NULL,
    chunk_index integer      NOT NULL,
    chunk_text  text         NOT NULL,
    embedding   vector(1536) NOT NULL,
    created_at  timestamptz  DEFAULT now()
);

-- ── Índices ───────────────────────────────────────────────────────────────────
CREATE INDEX transcript_chunks_embedding_idx
    ON transcript_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX transcript_chunks_project_idx  ON transcript_chunks (project_id);
CREATE INDEX transcript_chunks_meeting_idx  ON transcript_chunks (meeting_id);

CREATE UNIQUE INDEX transcript_chunks_meeting_chunk_idx
    ON transcript_chunks (meeting_id, chunk_index);

ALTER TABLE transcript_chunks DISABLE ROW LEVEL SECURITY;

-- ── Função de busca semântica ─────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION match_transcript_chunks(
    query_embedding   vector(1536),
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
LANGUAGE sql STABLE AS $$
    SELECT
        tc.id, tc.meeting_id, tc.project_id, tc.chunk_index, tc.chunk_text,
        1 - (tc.embedding <=> query_embedding) AS similarity
    FROM transcript_chunks tc
    WHERE tc.project_id = filter_project_id
    ORDER BY tc.embedding <=> query_embedding
    LIMIT match_count;
$$;

COMMENT ON TABLE transcript_chunks IS
    'Chunks de transcrição com embeddings vetoriais para busca semântica via pgvector.';
COMMENT ON COLUMN transcript_chunks.embedding IS
    'Vetor de 1536 dims — gemini-embedding-001 com output_dimensionality=1536.';
COMMENT ON FUNCTION match_transcript_chunks IS
    'Busca semântica por cosine similarity. Retorna top-K chunks mais similares ao embedding da consulta.';
