-- Migration: minutes_ata_html (PC155)
-- Persiste o HTML interativo da ATA Engine (hub.minutes.ata_html), que antes
-- só existia em memória durante a sessão do pipeline e se perdia em qualquer
-- reload de reunião (Modo B / Assistente / DocumentManager).
-- Execução: psycopg2 com conn.autocommit = True

ALTER TABLE meetings
  ADD COLUMN IF NOT EXISTS ata_html text;

COMMENT ON COLUMN meetings.ata_html IS
  'HTML standalone da Ata Interativa (ATA Engine) — chips de participante, tabela de pendências, persistência local via localStorage. Gerado por modules/ata_engine_generator.py::generate_ata_html(). Pode ficar vazio para reuniões processadas antes desta coluna existir.';
