-- =============================================================================
-- supabase_migration_kh_contradictions_v2.sql
-- Estende kh_contradictions com campos do Consistency Guardian Agent
-- RawToInsights AI · Maio 2026
-- =============================================================================
-- Aplicar via Supabase Dashboard → SQL Editor
-- Seguro re-executar: usa ADD COLUMN IF NOT EXISTS
-- =============================================================================

-- Tipo da relação (taxonomia expandida do Consistency Guardian)
ALTER TABLE kh_contradictions
    ADD COLUMN IF NOT EXISTS relation_type TEXT
        CHECK (relation_type IN (
            'contradiction_direct',
            'contradiction_conditional',
            'contradiction_temporal',
            'contradiction_responsibility',
            'exception',
            'superseded',
            'ambiguous'
        ));

-- Confiança da detecção (0.0 – 1.0)
ALTER TABLE kh_contradictions
    ADD COLUMN IF NOT EXISTS confidence FLOAT
        CHECK (confidence BETWEEN 0.0 AND 1.0);

-- Pergunta sugerida para esclarecimento com o cliente/analista
ALTER TABLE kh_contradictions
    ADD COLUMN IF NOT EXISTS clarifying_question TEXT;

-- Sugestão de reescrita que harmoniza as duas afirmações
ALTER TABLE kh_contradictions
    ADD COLUMN IF NOT EXISTS suggested_rewrite TEXT;

-- Índice auxiliar por relation_type
CREATE INDEX IF NOT EXISTS idx_kh_contradictions_relation
    ON kh_contradictions (project_id, relation_type);

-- Comentários
COMMENT ON COLUMN kh_contradictions.relation_type IS
    'contradiction_direct | contradiction_conditional | contradiction_temporal | contradiction_responsibility | exception | superseded | ambiguous';
COMMENT ON COLUMN kh_contradictions.confidence IS
    '0.0-1.0 — confiança do agente na detecção; abaixo de 0.50 não é inserida';
COMMENT ON COLUMN kh_contradictions.clarifying_question IS
    'Pergunta objetiva que um analista deve fazer para resolver a ambiguidade';
COMMENT ON COLUMN kh_contradictions.suggested_rewrite IS
    'Sugestão de como formalizar a regra incorporando ambas as afirmações';

-- Verificação pós-migração
/*
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'kh_contradictions'
ORDER BY ordinal_position;
*/
