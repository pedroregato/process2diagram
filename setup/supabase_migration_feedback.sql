-- Feedback — PC191 (melhorias/arquivados/aprimoramento-metacognitivo-3camadas.md, Camada 1)
-- Avaliação leve de usuário sobre respostas do Assistente e artefatos gerados
-- (processo BPMN, ata de reunião). Linhas cruas por evento — agregação
-- (média, taxa de aceitação) é calculada na leitura via
-- core/project_store.py::get_feedback_summary(), nunca mantida em coluna
-- própria (evita read-modify-write concorrente numa tabela de agregado).
--
-- rating é sempre 1-5, mesmo para o widget de thumbs (Assistente): down→1,
-- up→5 — uma única escala pros dois tipos de widget, evita uma segunda
-- coluna só pra thumbs.

-- project_id → contexts(id): nome herdado (mesmo registro de
-- setup/supabase_migration_provocations.sql, PC190). O termo de produto é
-- "contexto", não "projeto" — mantido por consistência com
-- asset_metadata/assistant_artifacts/provocations, que já usam esse nome
-- herdado. Renomear para context_id só no inventário de uma renomeação
-- global futura. Não corrigir isoladamente nesta tabela.

CREATE TABLE IF NOT EXISTS feedback (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
    meeting_id    UUID REFERENCES meetings(id) ON DELETE CASCADE,  -- null: assistant_response nem sempre é sobre 1 reunião
    artifact_type TEXT NOT NULL CHECK (artifact_type IN ('assistant_response', 'bpmn_process', 'meeting_minutes')),
    artifact_id   TEXT NOT NULL,  -- índice da msg no chat | bpmn_processes.id | meetings.id
    rating        INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    is_acceptable BOOLEAN,  -- só usado por artefatos; null em assistant_response
    comment       TEXT,
    created_by    TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_feedback_project_type ON feedback(project_id, artifact_type);

ALTER TABLE feedback ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE feedback IS 'PC191 — Avaliação de usuário sobre respostas do Assistente e artefatos gerados (melhorias/arquivados/aprimoramento-metacognitivo-3camadas.md, Camada 1). Agregação calculada na leitura via get_feedback_summary(), não mantida em coluna própria.';
