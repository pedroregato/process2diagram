-- Ativos de Negócio — Etapa 2 (Metadados)
-- Tabela genérica polimórfica ("Rota B") para governança de ativos:
-- status de ciclo de vida (rascunho/ativo/arquivado), tags, owner, notas.
-- Cobre apenas os tipos de artefato com linha própria (UUID real) no banco:
-- requirement, bpmn_process, sbvr_term, sbvr_rule, meeting_minutes.
-- BMM/DMN/IBIS/Relatórios (JSON dentro de meetings.*_json, sem linha própria)
-- ficam fora desta tabela por ora — ver melhorias/cognicao-de-negocio.md.

CREATE TABLE IF NOT EXISTS asset_metadata (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    UUID NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
    artifact_type TEXT NOT NULL,   -- 'requirement' | 'bpmn_process' | 'sbvr_term' | 'sbvr_rule' | 'meeting_minutes'
    artifact_id   UUID NOT NULL,
    status        TEXT NOT NULL DEFAULT 'rascunho',  -- rascunho | ativo | arquivado
    tags          TEXT[] NOT NULL DEFAULT '{}',
    owner         TEXT,
    notes         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by    TEXT,
    UNIQUE (project_id, artifact_type, artifact_id)
);

CREATE INDEX IF NOT EXISTS idx_asset_metadata_project ON asset_metadata(project_id);
CREATE INDEX IF NOT EXISTS idx_asset_metadata_type    ON asset_metadata(project_id, artifact_type);
CREATE INDEX IF NOT EXISTS idx_asset_metadata_status  ON asset_metadata(project_id, status);

ALTER TABLE asset_metadata ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE asset_metadata IS 'Governança polimórfica de ativos de negócio (Etapa 2, melhorias/cognicao-de-negocio.md) — rascunho/ativo/arquivado, tags, owner, notas. Dimensão separada do status de negócio já existente em requirements/bpmn_processes.';
