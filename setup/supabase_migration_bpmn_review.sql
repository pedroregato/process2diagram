-- supabase_migration_bpmn_review.sql
-- PC75: tabelas para AgentBPMNReviewer
-- Executar uma vez no Supabase SQL Editor (ou via psycopg2 local)

-- ──────────────────────────────────────────────────────────────────────────────
-- Tabela 1: bpmn_process_descriptions
--   Armazena a descrição textual (Markdown) gerada para cada versão de processo.
--   É o "elo perdido" entre transcrição bruta e o diagrama BPMN.
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS bpmn_process_descriptions (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    process_id      uuid        NOT NULL REFERENCES bpmn_processes(id) ON DELETE CASCADE,
    version_id      uuid        REFERENCES bpmn_versions(id) ON DELETE SET NULL,
    description_md  text        NOT NULL DEFAULT '',
    generated_by    text        NOT NULL DEFAULT 'unknown',  -- 'agent_bpmn', 'bpmn_reviewer', 'manual'
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bpmn_proc_desc_process_id
    ON bpmn_process_descriptions(process_id);

COMMENT ON TABLE bpmn_process_descriptions IS
    'Descrições textuais estruturadas de processos BPMN (geradas pelo AgentBPMN ou AgentBPMNReviewer).';

-- ──────────────────────────────────────────────────────────────────────────────
-- Tabela 2: bpmn_review_log
--   Log de auditoria das operações de revisão e correção de diagramas BPMN.
-- ──────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS bpmn_review_log (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id        uuid,
    process_name      text,
    version_before    integer,
    version_after     integer,
    issues_found      integer     NOT NULL DEFAULT 0,
    issues_corrected  integer     NOT NULL DEFAULT 0,
    review_report     jsonb,
    user_approved     boolean     NOT NULL DEFAULT false,
    created_at        timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bpmn_review_log_project_id
    ON bpmn_review_log(project_id);

CREATE INDEX IF NOT EXISTS idx_bpmn_review_log_created_at
    ON bpmn_review_log(created_at DESC);

COMMENT ON TABLE bpmn_review_log IS
    'Log de auditoria das correções aplicadas via AgentBPMNReviewer.';
