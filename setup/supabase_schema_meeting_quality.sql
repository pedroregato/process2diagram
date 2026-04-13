-- setup/supabase_schema_meeting_quality.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Fase 3 — ROI-TR: persistência de scores e análise cross-meeting
--
-- 1. Tabela meeting_quality_scores — histórico de indicadores ROI-TR
-- 2. Função find_recurring_topics   — detecção semântica de tópicos recorrentes
--
-- Execute no Supabase → SQL Editor (requer extensão pgvector já instalada).
-- ─────────────────────────────────────────────────────────────────────────────

-- ── 1. Tabela de scores ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS meeting_quality_scores (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id          UUID        NOT NULL REFERENCES projects(id)  ON DELETE CASCADE,
    meeting_id          UUID        NOT NULL REFERENCES meetings(id)  ON DELETE CASCADE,
    meeting_number      INTEGER     NOT NULL,
    computed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cost_per_hour       NUMERIC     DEFAULT 150,

    -- raw metrics
    n_participants      INTEGER,
    duration_min        NUMERIC,
    cost_estimate       NUMERIC,
    n_decisions         INTEGER,
    n_actions_total     INTEGER,
    n_actions_complete  INTEGER,
    n_requirements      INTEGER,
    cycle_signals       INTEGER,

    -- composite indicators
    trc                 NUMERIC,    -- 0–100 Taxa de Retrabalho Conceitual
    dc_score            NUMERIC,    -- Decisões Concretas (composite)
    roi_tr              NUMERIC     -- 0–10 ROI-TR index
);

CREATE INDEX IF NOT EXISTS idx_mqs_project
    ON meeting_quality_scores (project_id, meeting_number, computed_at DESC);

CREATE INDEX IF NOT EXISTS idx_mqs_meeting
    ON meeting_quality_scores (meeting_id, computed_at DESC);

ALTER TABLE meeting_quality_scores DISABLE ROW LEVEL SECURITY;

COMMENT ON TABLE meeting_quality_scores IS
    'Histórico de indicadores ROI-TR por reunião — permite análise de tendência ao longo do tempo.';

-- ── 2. Função de análise cross-meeting via embeddings ─────────────────────────
-- Retorna pares de chunks semanticamente similares de reuniões DIFERENTES.
-- Indica tópicos discutidos em múltiplas reuniões (padrão de ciclagem).
--
-- Requer: tabela transcript_chunks com embeddings (ver supabase_schema_transcript_chunks.sql)

CREATE OR REPLACE FUNCTION find_recurring_topics(
    p_project_id    UUID,
    p_threshold     FLOAT  DEFAULT 0.87,
    p_max_results   INT    DEFAULT 30
)
RETURNS TABLE (
    meeting_id_a    UUID,
    meeting_id_b    UUID,
    chunk_text_a    TEXT,
    chunk_text_b    TEXT,
    similarity      FLOAT
)
LANGUAGE sql STABLE AS $$
    SELECT
        a.meeting_id,
        b.meeting_id,
        a.chunk_text,
        b.chunk_text,
        (1 - (a.embedding <=> b.embedding))::FLOAT AS similarity
    FROM transcript_chunks a
    JOIN transcript_chunks b
        ON  a.project_id = b.project_id
        AND a.meeting_id < b.meeting_id   -- avoid duplicate pairs
    WHERE a.project_id = p_project_id
        AND (1 - (a.embedding <=> b.embedding)) > p_threshold
    ORDER BY similarity DESC
    LIMIT p_max_results;
$$;

COMMENT ON FUNCTION find_recurring_topics IS
    'Detecta tópicos discutidos em múltiplas reuniões via similaridade coseno entre chunks. '
    'Threshold recomendado: 0.87–0.92 (mais alto = mais estrito).';
