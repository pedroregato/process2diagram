-- =============================================================================
-- migrate_kh_entities_meeting_ids.sql
-- Adiciona meeting_ids[] a kh_entities para rastrear todas as reunioes
-- onde cada entidade foi mencionada (nao apenas first/last seen).
-- Seguro re-executar: usa ADD COLUMN IF NOT EXISTS + UPDATE condicional.
-- =============================================================================

ALTER TABLE kh_entities
    ADD COLUMN IF NOT EXISTS meeting_ids UUID[] NOT NULL DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_kh_entities_meeting_ids_gin
    ON kh_entities USING GIN (meeting_ids);

-- Backfill: popula meeting_ids com first_seen e last_seen para registros existentes
UPDATE kh_entities
SET meeting_ids = ARRAY(
    SELECT DISTINCT unnest
    FROM unnest(ARRAY[first_seen_meeting_id, last_seen_meeting_id])
    WHERE unnest IS NOT NULL
)
WHERE meeting_ids = '{}';

COMMENT ON COLUMN kh_entities.meeting_ids IS
    'Todas as reunioes onde esta entidade foi mencionada (superset de first/last seen)';

-- Verificacao pos-migracao
/*
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'kh_entities'
ORDER BY ordinal_position;

SELECT canonical_name, entity_type, occurrence_count, array_length(meeting_ids,1) AS n_meetings
FROM kh_entities
ORDER BY occurrence_count DESC
LIMIT 20;
*/
