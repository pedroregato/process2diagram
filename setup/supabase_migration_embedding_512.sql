-- setup/supabase_migration_embedding_512.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Migração: redução de embeddings de 1536 → 512 dimensões (Matryoshka)
--
-- Motivação: reduz o consumo de armazenamento pgvector em ~66%, viabilizando
--            o Free Tier do Supabase para comercialização.
--
-- ATENÇÃO: Esta migração TRUNCA os dados de embeddings existentes.
--          Os chunks precisarão ser re-gerados via backfill após a migração.
--          Execute os scripts de backfill (TranscriptBackfill.py / BpmnBackfill.py)
--          após concluir esta migração.
--
-- Execute no SQL Editor do Supabase (como service_role).
-- ─────────────────────────────────────────────────────────────────────────────

-- ── 1. Purgar dados com dimensão incompatível ─────────────────────────────────
-- pgvector não permite ALTER COLUMN para mudar dimensão em coluna com dados.
-- Os embeddings 1536-dim são incompatíveis com vector(512) e devem ser purgados.
TRUNCATE TABLE transcript_chunks;
TRUNCATE TABLE document_chunks;

-- ── 2. Remover índices ivfflat existentes ────────────────────────────────────
DROP INDEX IF EXISTS transcript_chunks_embedding_idx;
DROP INDEX IF EXISTS document_chunks_embedding_idx;

-- ── 3. Remover funções de busca com assinatura antiga ────────────────────────
DROP FUNCTION IF EXISTS match_transcript_chunks(vector(1536), uuid, int);
DROP FUNCTION IF EXISTS match_document_chunks(vector(1536), text, int, float);

-- ── 4. Alterar colunas para vector(512) ──────────────────────────────────────
ALTER TABLE transcript_chunks ALTER COLUMN embedding TYPE vector(512);
ALTER TABLE document_chunks   ALTER COLUMN embedding TYPE vector(512);

-- ── 5. Recriar índices ivfflat ───────────────────────────────────────────────
CREATE INDEX transcript_chunks_embedding_idx
    ON transcript_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX document_chunks_embedding_idx
    ON document_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- ── 6. Recriar função match_transcript_chunks com vector(512) ────────────────
CREATE OR REPLACE FUNCTION match_transcript_chunks(
    query_embedding   vector(512),
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

-- ── 7. Recriar função match_document_chunks com vector(512) ──────────────────
-- Esquema original: document_chunks não tem project_id — filtro via JOIN meeting_documents.
-- match_project_id é TEXT (project_id armazenado como text em meeting_documents).
CREATE OR REPLACE FUNCTION match_document_chunks(
    query_embedding  vector(512),
    match_project_id TEXT,
    match_count      INT   DEFAULT 5,
    match_threshold  FLOAT DEFAULT 0.4
)
RETURNS TABLE (
    id            UUID,
    document_id   UUID,
    chunk_index   INT,
    content       TEXT,
    similarity    FLOAT,
    doc_title     TEXT,
    doc_type      TEXT,
    doc_file_name TEXT
)
LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        dc.id,
        dc.document_id,
        dc.chunk_index,
        dc.content,
        (1 - (dc.embedding <=> query_embedding))::FLOAT AS similarity,
        md.title     AS doc_title,
        md.doc_type,
        md.file_name AS doc_file_name
    FROM document_chunks dc
    JOIN meeting_documents md ON md.id = dc.document_id
    WHERE md.project_id = match_project_id
      AND dc.embedding  IS NOT NULL
      AND (1 - (dc.embedding <=> query_embedding)) > match_threshold
    ORDER BY dc.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- ── 8. Atualizar comentários ──────────────────────────────────────────────────
COMMENT ON COLUMN transcript_chunks.embedding IS
    'Vetor de 512 dims — Matryoshka embedding (text-embedding-3-small dimensions=512 / gemini output_dimensionality=512).';
COMMENT ON COLUMN document_chunks.embedding IS
    'Vetor de 512 dims — Matryoshka embedding (text-embedding-3-small dimensions=512 / gemini output_dimensionality=512).';
COMMENT ON FUNCTION match_transcript_chunks IS
    'Busca semântica por cosine similarity (vector 512-dim). Retorna top-K chunks mais similares ao embedding da consulta.';
COMMENT ON FUNCTION match_document_chunks IS
    'Busca semântica por cosine similarity em documentos (vector 512-dim). Filtra por projeto via JOIN meeting_documents.';
