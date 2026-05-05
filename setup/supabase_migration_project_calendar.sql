-- setup/supabase_migration_project_calendar.sql
-- -----------------------------------------------------------------------------
-- Fase 1: tabela de calendar_id por projeto (sem credenciais adicionais).
-- A service account global permanece em st.secrets[google_calendar].
-- Execute no SQL Editor do Supabase (uma única vez).
-- -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS project_calendar_config (
    project_id  UUID PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    calendar_id TEXT NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE project_calendar_config ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE project_calendar_config IS
    'calendar_id do Google Calendar por projeto. '
    'Usa a service account global configurada em st.secrets[google_calendar]. '
    'Se ausente, o sistema usa o calendar_id padrão dos secrets (fallback).';
COMMENT ON COLUMN project_calendar_config.calendar_id IS
    'ID da agenda Google Calendar associada a este projeto '
    '(ex: xxx@group.calendar.google.com).';
