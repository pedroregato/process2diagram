-- Provocações — PC190 (melhorias/arquivados/agente-de-provocacoes.md)
-- Observações lastreadas geradas por AgentProvocations: o que ficou fechado
-- numa reunião sem ter sido examinado (tema ausente, objeção sem resposta,
-- contradição no tempo, premissa não questionada, analogia estrutural).
-- Fase 1 do agente só emite kind IN ('absence', 'asymmetry') — o CHECK abaixo
-- já aceita os 5 valores da taxonomia completa para não exigir migração nova
-- quando as fases futuras (contradiction/premise/analogy) forem implementadas.
--
-- Nenhuma linha chega aqui sem passar pelo validador determinístico do agente
-- (grounding conferido literalmente contra a transcrição antes de persistir).

-- project_id → contexts(id): nome herdado (registro, melhorias/revisao-plano-provocacoes.md §3).
-- O termo de produto é "contexto", não "projeto" — mantido por consistência com
-- asset_metadata/assistant_artifacts, que já usam esse mesmo nome herdado.
-- Renomear para context_id só no inventário de uma renomeação global futura
-- (p2d → Vichara, projeto → contexto). Não corrigir isoladamente nesta tabela.

CREATE TABLE IF NOT EXISTS provocations (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id    UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    project_id    UUID NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
    tenant_id     UUID,  -- denormalizado, sem FK — mesmo padrão de contexts.tenant_id (schema drift conhecido, sem migration própria)
    kind          TEXT NOT NULL CHECK (kind IN ('absence', 'contradiction', 'premise', 'asymmetry', 'analogy')),
    title         TEXT NOT NULL,
    body          TEXT NOT NULL,
    question      TEXT NOT NULL,
    grounding     JSONB NOT NULL,
    confidence    TEXT NOT NULL CHECK (confidence IN ('high', 'medium')),
    status        TEXT NOT NULL DEFAULT 'new'
                  CHECK (status IN ('new', 'accepted', 'discarded', 'became_divergence')),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_provocations_project_status ON provocations(project_id, status);
CREATE INDEX IF NOT EXISTS idx_provocations_meeting        ON provocations(meeting_id);

ALTER TABLE provocations ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE provocations IS 'PC190 — Provocações lastreadas geradas por AgentProvocations (melhorias/arquivados/agente-de-provocacoes.md). Toda linha já passou pelo validador determinístico do agente antes de ser persistida.';
