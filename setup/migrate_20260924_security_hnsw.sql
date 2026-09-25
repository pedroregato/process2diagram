-- ─────────────────────────────────────────────────────────────────────────────
-- migrate_20260924_security_hnsw.sql
-- Registro das migrations aplicadas em produção em 2026-09-24
-- (security_hardening_20260924 + vector_indexes_hnsw_20260924).
-- Idempotente: pode ser reexecutado com segurança.
--
-- O app usa a chave service_role (ignora RLS), então nada aqui altera o
-- comportamento da aplicação — apenas fecha o acesso via anon/authenticated.
-- ─────────────────────────────────────────────────────────────────────────────

-- 1. login_logs: RLS ativo, sem acesso para anon/authenticated
ALTER TABLE public.login_logs ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.login_logs FROM anon, authenticated;

-- 2. View passa a respeitar o RLS de quem consulta
ALTER VIEW public.v_knowledge_graph_nodes SET (security_invoker = true);

-- 3. Remove SELECT aberto (USING true) e policies de escrita redundantes
--    (service_role já ignora RLS)
DROP POLICY IF EXISTS arg_maps_select            ON public.argumentation_maps;
DROP POLICY IF EXISTS arg_maps_write             ON public.argumentation_maps;
DROP POLICY IF EXISTS dmn_decisions_select       ON public.dmn_decisions;
DROP POLICY IF EXISTS dmn_decisions_write        ON public.dmn_decisions;
DROP POLICY IF EXISTS dmn_models_select          ON public.dmn_models;
DROP POLICY IF EXISTS dmn_models_write           ON public.dmn_models;
DROP POLICY IF EXISTS ibis_alt_select            ON public.ibis_alternatives;
DROP POLICY IF EXISTS ibis_alt_write             ON public.ibis_alternatives;
DROP POLICY IF EXISTS ibis_q_select              ON public.ibis_questions;
DROP POLICY IF EXISTS ibis_q_write               ON public.ibis_questions;
DROP POLICY IF EXISTS kh_analyses_select         ON public.kh_analyses;
DROP POLICY IF EXISTS kh_analyses_write          ON public.kh_analyses;
DROP POLICY IF EXISTS kh_contradictions_select   ON public.kh_contradictions;
DROP POLICY IF EXISTS kh_contradictions_write    ON public.kh_contradictions;
DROP POLICY IF EXISTS kh_entities_select         ON public.kh_entities;
DROP POLICY IF EXISTS kh_entities_write          ON public.kh_entities;
DROP POLICY IF EXISTS kh_facts_select            ON public.kh_facts;
DROP POLICY IF EXISTS kh_facts_write             ON public.kh_facts;
DROP POLICY IF EXISTS kh_processes_select        ON public.kh_processes;
DROP POLICY IF EXISTS kh_processes_write         ON public.kh_processes;
DROP POLICY IF EXISTS dialogue_acts_select       ON public.meeting_dialogue_acts;
DROP POLICY IF EXISTS dialogue_acts_write        ON public.meeting_dialogue_acts;
DROP POLICY IF EXISTS mp_select_authenticated    ON public.meeting_participants;
DROP POLICY IF EXISTS mp_write_service           ON public.meeting_participants;
DROP POLICY IF EXISTS roster_select_authenticated ON public.project_roster;
DROP POLICY IF EXISTS roster_write_service       ON public.project_roster;

-- 4. search_path fixo (public + extensions, para resolver vector / <=>)
DO $$
DECLARE f regprocedure;
BEGIN
  FOR f IN
    SELECT p.oid::regprocedure FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname = 'public' AND p.proname IN (
      'find_recurring_topics','set_updated_at','delete_expired_llm_cache','_billing_set_updated_at',
      '_docs_set_updated_at','next_req_number','get_meeting_participants_full',
      'delete_old_llm_telemetry','match_transcript_chunks','match_document_chunks')
  LOOP
    EXECUTE format('ALTER FUNCTION %s SET search_path = public, extensions', f);
  END LOOP;
END $$;

-- 5. Índice para toda foreign key sem índice em public (prefixo idx_fk_)
DO $$
DECLARE r record;
BEGIN
  FOR r IN
    SELECT c.conrelid::regclass AS tbl, c.conname,
           string_agg(quote_ident(a.attname), ', ' ORDER BY k.ord) AS cols
    FROM pg_constraint c
    JOIN pg_namespace n ON n.oid = c.connamespace
    CROSS JOIN LATERAL unnest(c.conkey) WITH ORDINALITY k(attnum, ord)
    JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = k.attnum
    WHERE c.contype = 'f' AND n.nspname = 'public'
      AND NOT EXISTS (
        SELECT 1 FROM pg_index i
        WHERE i.indrelid = c.conrelid
          AND (i.indkey::int2[])[0:array_length(c.conkey,1)-1] = c.conkey)
    GROUP BY c.conrelid, c.conname
  LOOP
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %s (%s)',
                   left('idx_fk_' || r.conname, 63), r.tbl, r.cols);
  END LOOP;
END $$;

-- 6. Índices vetoriais: ivfflat → HNSW (recall@8: ~31% → ~97%)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'transcript_chunks_embedding_idx' AND indexdef ILIKE '%hnsw%') THEN
    DROP INDEX IF EXISTS public.transcript_chunks_embedding_idx;
    CREATE INDEX transcript_chunks_embedding_idx ON public.transcript_chunks USING hnsw (embedding vector_cosine_ops);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'document_chunks_embedding_idx' AND indexdef ILIKE '%hnsw%') THEN
    DROP INDEX IF EXISTS public.document_chunks_embedding_idx;
    CREATE INDEX document_chunks_embedding_idx ON public.document_chunks USING hnsw (embedding vector_cosine_ops);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE indexname = 'idx_req_embedding' AND indexdef ILIKE '%hnsw%') THEN
    DROP INDEX IF EXISTS public.idx_req_embedding;
    CREATE INDEX idx_req_embedding ON public.requirements USING hnsw (embedding vector_cosine_ops);
  END IF;
END $$;

ANALYZE;
