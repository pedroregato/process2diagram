-- PC183 — Error-path telemetry + schema-validation quality metric
--
-- Two additions to llm_telemetry, both fail-open / additive:
--   1) error_message — captures the exception text for failed LLM calls.
--      Previously is_error was hardcoded FALSE on every write (the only
--      telemetry write happened AFTER a successful call), so failures
--      (e.g. the intermittent DeepSeek "conteúdo vazio" issue) left zero
--      trace. base_agent.py now wraps the provider call and records
--      is_error=TRUE before re-raising.
--   2) is_validation_event / schema_valid — persists the outcome of
--      output_schema.model_validate() (PC84), previously only an ephemeral
--      warnings.warn(). These rows share the table but represent a distinct
--      event type (no latency/token data) — query() filters them out of the
--      existing latency/throughput views via is_validation_event = FALSE.
--
-- Safe to run multiple times (IF NOT EXISTS).

ALTER TABLE llm_telemetry
    ADD COLUMN IF NOT EXISTS error_message        TEXT,
    ADD COLUMN IF NOT EXISTS is_validation_event   BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS schema_valid          BOOLEAN;

CREATE INDEX IF NOT EXISTS idx_llm_telemetry_is_error
    ON llm_telemetry(is_error)
    WHERE is_error = TRUE;

CREATE INDEX IF NOT EXISTS idx_llm_telemetry_validation_event
    ON llm_telemetry(is_validation_event)
    WHERE is_validation_event = TRUE;
