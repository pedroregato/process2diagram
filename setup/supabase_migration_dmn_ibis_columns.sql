-- setup/supabase_migration_dmn_ibis_columns.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Adiciona colunas dmn_json e argumentation_json à tabela meetings.
--
-- Por que: a migration v4_23_bmif.sql criou tabelas dedicadas (dmn_models,
-- argumentation_maps) mas o código Python lê/escreve essas colunas JSON em
-- meetings, seguindo o mesmo padrão de bmm_json.
--
-- Seguro re-executar: usa ADD COLUMN IF NOT EXISTS.
-- Execute no Supabase → SQL Editor.
-- ─────────────────────────────────────────────────────────────────────────────

ALTER TABLE meetings
    ADD COLUMN IF NOT EXISTS dmn_json            TEXT,   -- DMNModel serializado (AgentDMN)
    ADD COLUMN IF NOT EXISTS argumentation_json  TEXT;   -- ArgumentationMap serializado (AgentArgumentation/IBIS)

COMMENT ON COLUMN meetings.dmn_json           IS 'JSON do DMNModel gerado pelo AgentDMN — decisões formalizadas (OMG DMN 1.4)';
COMMENT ON COLUMN meetings.argumentation_json IS 'JSON do ArgumentationMap gerado pelo AgentArgumentation — mapa IBIS da reunião';

-- Verificação pós-execução:
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'meetings'
  AND column_name IN ('bmm_json', 'dmn_json', 'argumentation_json')
ORDER BY column_name;
