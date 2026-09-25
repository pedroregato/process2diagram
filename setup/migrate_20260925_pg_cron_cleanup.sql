-- ─────────────────────────────────────────────────────────────────────────────
-- migrate_20260925_pg_cron_cleanup.sql
-- Registro da migration aplicada em produção em 2026-09-25
-- (pg_cron_cleanup_jobs_20260925). Horários em UTC (03:xx UTC = 00:xx BRT).
--
-- llm_telemetry NÃO é limpa automaticamente (decisão de 2026-09-25): guarda só
-- metadados operacionais (modelo, tokens, latência, erros, skill_version), sem
-- conteúdo das reuniões; ocupa ~664 kB e o histórico tem valor para comparar
-- versões de skills/provedores ao longo do tempo. delete_old_llm_telemetry()
-- continua disponível para execução manual. Transcrições e artefatos (meetings,
-- transcript_chunks etc.) também não têm limpeza automática — são ativos brutos.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE EXTENSION IF NOT EXISTS pg_cron;

-- Remove agendamentos anteriores com o mesmo nome (idempotente)
SELECT cron.unschedule(jobname) FROM cron.job
WHERE jobname IN ('cleanup-llm-cache','cleanup-user-sessions','retention-compliance-audit');

-- Cache LLM: entradas além do ttl_days de cada linha (diário)
SELECT cron.schedule('cleanup-llm-cache', '15 3 * * *',
  $$SELECT public.delete_expired_llm_cache()$$);

-- Sessões persistentes (PC214): expiradas há mais de 1 dia (diário)
SELECT cron.schedule('cleanup-user-sessions', '25 3 * * *',
  $$DELETE FROM public.user_sessions WHERE expires_at < now() - interval '1 day'$$);

-- LGPD: retenção de 365 dias da trilha de auditoria (semanal, domingo)
SELECT cron.schedule('retention-compliance-audit', '35 3 * * 0',
  $$DELETE FROM public.compliance_audit WHERE created_at < now() - interval '365 days'$$);
