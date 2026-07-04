-- setup/supabase_migration_bpmn_studio.sql
-- PC116/BPMN Studio: permite salvar uma versão de BPMN sem reunião vinculada.
--
-- bpmn_processes.first_meeting_id / last_meeting_id já eram nullable (REFERENCES
-- meetings(id) ON DELETE SET NULL). O bloqueio real estava em bpmn_versions.meeting_id
-- (NOT NULL) — tornando literalmente impossível salvar uma versão sem reunião,
-- condição que o BPMN Studio precisa violar por definição (processo criado antes de
-- qualquer reunião existir).
--
-- Sem efeitos colaterais: ON DELETE CASCADE continua válido para linhas onde
-- meeting_id está preenchido; linhas com meeting_id IS NULL simplesmente não são
-- afetadas por delete de reunião.

ALTER TABLE bpmn_versions ALTER COLUMN meeting_id DROP NOT NULL;
