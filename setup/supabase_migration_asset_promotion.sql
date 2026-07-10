-- Ativos de Negócio — Promoção Explícita + Classificação em 3 Dimensões
-- Ver melhorias/promocao-ativos-negocio.md para o plano técnico completo.
--
-- A partir desta migration, existir uma linha em asset_metadata passa a SER
-- a definição de "é um ativo de negócio" — deixa de ser um enriquecimento
-- opcional de artefatos que já apareciam automaticamente na Central de Ativos.
--
-- Linhas já existentes (criadas desde PC164/165) recebem os defaults abaixo
-- e ficam "promovidas" com classificação mínima — fail-open, sem perda de dado.

ALTER TABLE asset_metadata
    ADD COLUMN IF NOT EXISTS business_interest      TEXT NOT NULL DEFAULT 'operacional',
    ADD COLUMN IF NOT EXISTS business_perspective    TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS formal_classification    TEXT,
    ADD COLUMN IF NOT EXISTS promotion_justification  TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS promoted_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS promoted_by              TEXT;

CREATE INDEX IF NOT EXISTS idx_asset_metadata_interest ON asset_metadata(project_id, business_interest);

COMMENT ON COLUMN asset_metadata.business_interest IS
    'estrategico | tatico | operacional — validado na aplicação, não via CHECK (mesmo padrão de status)';
COMMENT ON COLUMN asset_metadata.business_perspective IS
    'multi-valor: comercial, compliance, compras_suprimentos, contabilidade, financeiro, governanca, juridico, logistica, marketing, operacoes, rh, ti — validado na aplicação';
COMMENT ON COLUMN asset_metadata.formal_classification IS
    'AN-01..AN-12 (taxonomia de Ativos de Negócio — ISO 55000/APQC PCF/BIZBOK/TOGAF, ver melhorias/promocao-ativos-negocio.md §3.3) — nullable, algumas classes ainda sem artefato P2D correspondente';
COMMENT ON COLUMN asset_metadata.promotion_justification IS
    'texto livre obrigatório em toda promoção nova — por que este ativo interessa ao negócio; DEFAULT vazio só para não quebrar linhas já existentes';
COMMENT ON COLUMN asset_metadata.promoted_at IS
    'quando o ativo foi promovido (linhas antigas recebem o momento da migration, não a data real de criação)';
COMMENT ON COLUMN asset_metadata.promoted_by IS
    'quem promoveu — nullable para linhas antigas sem esse dado';
