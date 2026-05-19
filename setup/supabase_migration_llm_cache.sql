-- setup/supabase_migration_llm_cache.sql
-- Semantic cache for LLM responses — avoids redundant API calls on reprocessing.
--
-- Cache key: SHA256(provider | model | system_prompt | sanitized_user_prompt)
-- Cache value: raw LLM output BEFORE PII desanitization (callers apply desanitize
--              with their own token_map on hit — prevents PII leakage between sessions).
--
-- Run once in the Supabase SQL editor.

CREATE TABLE IF NOT EXISTS llm_cache (
    hash        TEXT PRIMARY KEY,
    agent_name  TEXT        NOT NULL,
    result      TEXT        NOT NULL,
    tokens_used INTEGER     NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    ttl_days    INTEGER     NOT NULL DEFAULT 30,
    hit_count   INTEGER     NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS llm_cache_agent_name_idx ON llm_cache (agent_name);
CREATE INDEX IF NOT EXISTS llm_cache_created_at_idx ON llm_cache (created_at);

-- Garbage collection: call periodically from a Supabase cron job or manually.
CREATE OR REPLACE FUNCTION delete_expired_llm_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted INTEGER;
BEGIN
    DELETE FROM llm_cache
    WHERE created_at < (now() - (ttl_days || ' days')::INTERVAL);
    GET DIAGNOSTICS deleted = ROW_COUNT;
    RETURN deleted;
END;
$$ LANGUAGE plpgsql;
