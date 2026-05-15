-- migrate_v4_22_context_files.sql
-- Cria a tabela context_files para armazenar arquivos de referência do contexto.
-- Execute no Supabase → SQL Editor (uma única vez).
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS context_files (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    context_id    UUID        NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
    filename      TEXT        NOT NULL,
    file_type     TEXT        NOT NULL,   -- 'html' | 'pptx' | 'pdf' | 'txt' | 'md'
    content_text  TEXT,                   -- texto extraído (sem formatação binária)
    file_size     INTEGER,                -- tamanho em bytes do arquivo original
    uploaded_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    uploaded_by   TEXT                    -- login do usuário que fez o upload
);

CREATE INDEX IF NOT EXISTS idx_ctx_files_context
    ON context_files (context_id, uploaded_at DESC);

ALTER TABLE context_files DISABLE ROW LEVEL SECURITY;

COMMENT ON TABLE context_files IS
    'Arquivos de referência do contexto (HTML, PPTX, PDF, TXT). '
    'O texto extraído é injetado nos prompts dos agentes junto com o CKF manual.';
