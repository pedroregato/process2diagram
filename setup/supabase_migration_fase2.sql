-- =============================================================================
-- Migration Fase 2 — Editor Estrutural + Sincronizador Calendário
-- Process2Diagram v4.33
-- Apply via: SQL Editor do Supabase Dashboard
-- =============================================================================
--
-- SEGURANÇA: O app usa a chave service_role (st.secrets["supabase"]["key"]),
-- que ignora RLS automaticamente. RLS é habilitado nas novas tabelas para
-- bloquear acesso público via chave anon/authenticated — sem criar policies.
-- Nenhuma quebra de funcionamento para o backend.
-- =============================================================================

-- 1. sort_order on requirements (for reordenar_requisitos)
ALTER TABLE requirements ADD COLUMN IF NOT EXISTS sort_order integer;

-- 2. SBVR ↔ IBIS links table (for vincular_regra_debate)
CREATE TABLE IF NOT EXISTS sbvr_ibis_links (
    id               uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id       uuid        NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
    rule_id          text        NOT NULL,
    ibis_question_id text        NOT NULL,
    relacao          text        NOT NULL DEFAULT 'justifica',  -- justifica | contradiz | limita
    created_at       timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE sbvr_ibis_links ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS sbvr_ibis_links_project_id_idx
    ON sbvr_ibis_links(project_id);

CREATE INDEX IF NOT EXISTS sbvr_ibis_links_rule_id_idx
    ON sbvr_ibis_links(project_id, rule_id);

-- 3. Calendar sync items table (for sincronizar_calendario)
CREATE TABLE IF NOT EXISTS calendar_sync_items (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      uuid        NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
    meeting_id      uuid        REFERENCES meetings(id) ON DELETE SET NULL,
    action_text     text        NOT NULL,
    responsible     text,
    google_event_id text,
    sync_direction  text        NOT NULL DEFAULT 'to_calendar',  -- to_calendar | from_calendar
    status          text        NOT NULL DEFAULT 'pending',       -- pending | synced | completed | error
    last_sync_at    timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE calendar_sync_items ENABLE ROW LEVEL SECURITY;

CREATE INDEX IF NOT EXISTS calendar_sync_items_project_id_idx
    ON calendar_sync_items(project_id);

CREATE INDEX IF NOT EXISTS calendar_sync_items_meeting_id_idx
    ON calendar_sync_items(meeting_id);
