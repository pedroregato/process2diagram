-- setup/supabase_migration_meeting_processing_log.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- PC152 — Tabela auxiliar que registra a data efetiva de cada processamento
-- de uma reunião (pipeline novo, reprocessamento completo, ou reprocessamento
-- de um único agente), permitindo saber quantas vezes uma transcrição foi
-- processada e quando cada processamento ocorreu.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS meeting_processing_log (
    id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    meeting_id      UUID        NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    project_id      UUID        NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
    processing_type TEXT        NOT NULL DEFAULT 'new'
                        CHECK (processing_type IN ('new', 'reprocess_full', 'reprocess_agent')),
    agent_name      TEXT,       -- preenchido apenas quando processing_type = 'reprocess_agent'
    llm_provider    TEXT,
    total_tokens    INTEGER     NOT NULL DEFAULT 0,
    success         BOOLEAN     NOT NULL DEFAULT TRUE,
    error_message   TEXT,
    processed_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS meeting_processing_log_meeting_idx      ON meeting_processing_log(meeting_id);
CREATE INDEX IF NOT EXISTS meeting_processing_log_project_idx      ON meeting_processing_log(project_id);
CREATE INDEX IF NOT EXISTS meeting_processing_log_processed_at_idx ON meeting_processing_log(processed_at DESC);

COMMENT ON TABLE meeting_processing_log IS
    'PC152 — registra cada processamento (novo ou reprocessamento) de uma reunião: '
    'data efetiva, tipo, agente (quando reprocessamento pontual), tokens e sucesso/erro. '
    'Permite contar quantas vezes uma transcrição foi processada e quando.';
COMMENT ON COLUMN meeting_processing_log.processing_type IS
    'new = pipeline completo na criação da reunião; '
    'reprocess_full = reprocessamento completo (todos os agentes, reunião já existente); '
    'reprocess_agent = reexecução de um único agente (bpmn, minutes, requirements, sbvr, bmm, '
    'synthesizer, quality, dmn, argumentation, query_summarizer, communication_noise, mermaid)';
COMMENT ON COLUMN meeting_processing_log.agent_name IS
    'Nome do agente reexecutado quando processing_type = reprocess_agent; NULL para new/reprocess_full';
