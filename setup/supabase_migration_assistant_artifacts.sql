-- Ativos de Negócio — Promoção de conteúdo gerado pelo Assistente (Fase C)
-- Ver melhorias/promocao-ativos-negocio.md §5.3 para o plano técnico completo.
--
-- Hoje, nada do que o Assistente gera sob demanda (relatórios, decks, análises,
-- gráficos) é persistido — só existe como download efêmero no navegador
-- (st.session_state["_pending_file_download"], pages/Assistente.py). Esta
-- tabela guarda um SNAPSHOT do conteúdo no momento da promoção — cada
-- promoção é independente, não há deduplicação (mesmo padrão de "salvar
-- como", já documentado como decisão consciente no plano §7).

CREATE TABLE IF NOT EXISTS assistant_artifacts (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       UUID NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
    title            TEXT NOT NULL,
    content_markdown TEXT NOT NULL,
    source_tool      TEXT,                 -- ex: 'gerar_project_charter', 'generate_requirements_heatmap'
    meeting_id       UUID REFERENCES meetings(id) ON DELETE SET NULL,  -- opcional
    created_by       TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_assistant_artifacts_project ON assistant_artifacts(project_id);

ALTER TABLE assistant_artifacts ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE assistant_artifacts IS 'Snapshot de conteúdo gerado sob demanda pelo Assistente, persistido no momento da promoção a Ativo de Negócio (Fase C, melhorias/promocao-ativos-negocio.md). artifact_type="assistant_artifact" em asset_metadata, artifact_id=assistant_artifacts.id.';
