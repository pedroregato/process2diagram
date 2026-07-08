-- supabase_migration_ata_templates.sql
-- PC160: Templates de ata por contexto (melhorias/templates-ata-por-contexto.md)
-- Cria as tabelas ata_templates + ata_template_assets.
-- Execute no Supabase → SQL Editor (uma única vez).
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ata_templates (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    context_id        UUID        NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
    name              TEXT        NOT NULL,          -- rótulo pro usuário, ex: "Modelo padrão SDEA"
    docx_filename     TEXT        NOT NULL,
    docx_base64       TEXT        NOT NULL,          -- bytes do .docx original, base64
    template_markdown TEXT,                          -- esqueleto derivado (## Seção na ordem do Word)
    style_spec        JSONB,                          -- {"accent_color": "...", "section_order": [...]}
    is_active         BOOLEAN     NOT NULL DEFAULT true,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by        TEXT                            -- login do usuário que fez o upload
);

-- Um contexto tem no máximo um template ATIVO por vez (desativar, não apagar, ao trocar).
CREATE UNIQUE INDEX IF NOT EXISTS idx_ata_templates_context_active
    ON ata_templates (context_id) WHERE is_active;

CREATE INDEX IF NOT EXISTS idx_ata_templates_context
    ON ata_templates (context_id, created_at DESC);

CREATE TABLE IF NOT EXISTS ata_template_assets (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    template_id   UUID        NOT NULL REFERENCES ata_templates(id) ON DELETE CASCADE,
    asset_type    TEXT        NOT NULL
        CHECK (asset_type IN ('logo', 'background', 'header_image', 'footer_image', 'other')),
    origin        TEXT        NOT NULL
        CHECK (origin IN ('header', 'footer', 'body', 'page_background')),
    image_base64  TEXT        NOT NULL,
    mime_type     TEXT        NOT NULL,               -- 'image/png' | 'image/jpeg' | ...
    width_px      INTEGER,
    height_px     INTEGER,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ata_template_assets_template
    ON ata_template_assets (template_id);

-- RLS habilitado (padrão do projeto — ver supabase_migration_enable_rls.sql):
-- bloqueia acesso via chave anon/authenticated; o app usa service_role, que
-- ignora RLS automaticamente, então isto não afeta o funcionamento do app.
-- Nenhuma policy para anon/authenticated é criada de propósito (acesso público
-- fica bloqueado por padrão).
ALTER TABLE ata_templates        ENABLE ROW LEVEL SECURITY;
ALTER TABLE ata_template_assets  ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE ata_templates IS
    'Modelo de ata em Word por contexto (PC160). Estrutura de seções (template_markdown) '
    'é injetada no prompt do AgentMinutes junto do CKF; style_spec + assets parametrizam '
    'modules/minutes_exporter.py::to_docx() na exportação. Só admin/master configuram.';

COMMENT ON TABLE ata_template_assets IS
    'Imagens de identidade visual extraídas do .docx de referência (logo, cabeçalho/rodapé, '
    'plano de fundo quando detectável) — reinseridas no Word gerado por to_docx().';
