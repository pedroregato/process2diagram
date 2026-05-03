-- setup/supabase_migration_user_accounts.sql
-- -----------------------------------------------------------------------------
-- Adiciona campos de conta Google e Microsoft Teams à tabela tenant_users.
-- Execute este script no SQL Editor do Supabase (uma única vez).
-- -----------------------------------------------------------------------------

ALTER TABLE tenant_users
    ADD COLUMN IF NOT EXISTS google_account   TEXT DEFAULT NULL,
    ADD COLUMN IF NOT EXISTS ms_teams_account TEXT DEFAULT NULL;

COMMENT ON COLUMN tenant_users.google_account IS
    'Conta Google do usuário (ex: pedro.regato@gmail.com). Usada para compartilhamento de agenda.';
COMMENT ON COLUMN tenant_users.ms_teams_account IS
    'Conta Microsoft 365 / Teams do usuário (ex: pedro@empresa.com). Usada para agendamento e envio de ata.';
