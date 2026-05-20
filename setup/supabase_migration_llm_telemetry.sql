-- setup/supabase_migration_llm_telemetry.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- LLM telemetry table — records per-call latency, token counts and metadata
-- for every LLM call made by the pipeline (passive) and on-demand benchmarks.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS llm_telemetry (
    id             BIGSERIAL    PRIMARY KEY,
    agent_name     TEXT         NOT NULL,
    provider       TEXT         NOT NULL,
    model          TEXT         NOT NULL,
    latency_ms     INTEGER      NOT NULL,
    input_tokens   INTEGER      NOT NULL DEFAULT 0,
    output_tokens  INTEGER      NOT NULL DEFAULT 0,
    total_tokens   INTEGER      NOT NULL DEFAULT 0,
    from_cache     BOOLEAN      NOT NULL DEFAULT FALSE,
    long_context   BOOLEAN      NOT NULL DEFAULT FALSE,
    is_error       BOOLEAN      NOT NULL DEFAULT FALSE,
    benchmark_run  BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_llm_telemetry_agent      ON llm_telemetry(agent_name);
CREATE INDEX IF NOT EXISTS idx_llm_telemetry_provider   ON llm_telemetry(provider);
CREATE INDEX IF NOT EXISTS idx_llm_telemetry_created_at ON llm_telemetry(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_llm_telemetry_benchmark  ON llm_telemetry(benchmark_run);

-- Automatic cleanup: keep only last 90 days
CREATE OR REPLACE FUNCTION delete_old_llm_telemetry() RETURNS INTEGER
LANGUAGE plpgsql AS $$
DECLARE deleted INTEGER;
BEGIN
    DELETE FROM llm_telemetry WHERE created_at < now() - INTERVAL '90 days';
    GET DIAGNOSTICS deleted = ROW_COUNT;
    RETURN deleted;
END;
$$;
