-- setup/supabase_schema_transcript_chunks.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Tabela de chunks de transcrição com embeddings para busca semântica (pgvector).
--
-- Pré-requisito: extensão vector já instalada no projeto Supabase.
-- (Supabase habilita pgvector por padrão em todos os projetos)
--
-- Execute este script no SQL Editor do Supabase.
-- ─────────────────────────────────────────────────────────────────────────────

-- Garante que a extensão vector está habilitada
CREATE EXTENSION IF NOT EXISTS vector;

-- ── Tabela principal ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS transcript_chunks (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id      uuid        NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    project_id      uuid        NOT NULL,
    chunk_index     integer     NOT NULL,        -- posição do chunk na transcrição (0-based)
    chunk_text      text        NOT NULL,        -- texto do chunk (~500 chars com overlap)
    embedding       vector(768) NOT NULL,        -- vetor de embedding (768 dims = Gemini/OpenAI)
    created_at      timestamptz DEFAULT now()
);

-- ── Índices ───────────────────────────────────────────────────────────────────
-- Índice vetorial para busca por cosine similarity (IVFFlat)
-- lists=100 é adequado para coleções de até ~1M chunks
CREATE INDEX IF NOT EXISTS transcript_chunks_embedding_idx
    ON transcript_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS transcript_chunks_project_idx
    ON transcript_chunks (project_id);

CREATE INDEX IF NOT EXISTS transcript_chunks_meeting_idx
    ON transcript_chunks (meeting_id);

-- Unique: cada chunk_index deve ser único por reunião
CREATE UNIQUE INDEX IF NOT EXISTS transcript_chunks_meeting_chunk_idx
    ON transcript_chunks (meeting_id, chunk_index);

-- ── RLS desabilitado (acesso via service key) ─────────────────────────────────
ALTER TABLE transcript_chunks DISABLE ROW LEVEL SECURITY;

-- ── Função de busca semântica ─────────────────────────────────────────────────
-- Retorna os chunks mais similares a um embedding de consulta, filtrados por projeto.
-- Uso: SELECT * FROM match_transcript_chunks(query_embedding, project_id_val, match_count);
CREATE OR REPLACE FUNCTION match_transcript_chunks(
    query_embedding vector(768),
    filter_project_id uuid,
    match_count int DEFAULT 8
)
RETURNS TABLE (
    id              uuid,
    meeting_id      uuid,
    project_id      uuid,
    chunk_index     integer,
    chunk_text      text,
    similarity      float
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
    'Vetor de 768 dimensões — compatível com Google text-embedding-004 e OpenAI text-embedding-3-small (dimensions=768).';
COMMENT ON FUNCTION match_transcript_chunks IS
    'Busca semântica por cosine similarity. Retorna top-K chunks mais similares ao embedding da consulta.';
