-- PC83 — Add skill_version column to llm_telemetry
-- Tracks which skill file version produced each LLM call.
-- Safe to run multiple times (IF NOT EXISTS).

ALTER TABLE llm_telemetry
    ADD COLUMN IF NOT EXISTS skill_version TEXT;

-- Optional index for filtering by skill version in LLMBenchmark analytics
CREATE INDEX IF NOT EXISTS llm_telemetry_skill_version_idx
    ON llm_telemetry (skill_version)
    WHERE skill_version IS NOT NULL;
