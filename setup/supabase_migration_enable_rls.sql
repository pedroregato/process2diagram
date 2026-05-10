-- ─────────────────────────────────────────────────────────────────────────────
-- Process2Diagram — Migração de Segurança: Habilitar Row Level Security
-- ─────────────────────────────────────────────────────────────────────────────
--
-- PROBLEMA: Todas as tabelas estavam com RLS desabilitado, tornando os dados
-- acessíveis publicamente via chave anon do Supabase.
--
-- SOLUÇÃO: Habilitar RLS em todas as tabelas. O app usa a chave service_role
-- (st.secrets["supabase"]["key"]) que ignora RLS automaticamente — portanto
-- esta migração NÃO quebra o funcionamento do app.
--
-- Nenhuma policy para anon/authenticated é criada: acesso público bloqueado.
-- O backend (service_role) continua com acesso irrestrito.
--
-- Execute este script no SQL Editor do Supabase Dashboard.
-- ─────────────────────────────────────────────────────────────────────────────

-- ── Schema principal ─────────────────────────────────────────────────────────
ALTER TABLE projects             ENABLE ROW LEVEL SECURITY;
ALTER TABLE meetings             ENABLE ROW LEVEL SECURITY;
ALTER TABLE requirements         ENABLE ROW LEVEL SECURITY;
ALTER TABLE requirement_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE sbvr_terms           ENABLE ROW LEVEL SECURITY;
ALTER TABLE sbvr_rules           ENABLE ROW LEVEL SECURITY;

-- ── BPMN ─────────────────────────────────────────────────────────────────────
ALTER TABLE bpmn_processes ENABLE ROW LEVEL SECURITY;
ALTER TABLE bpmn_versions  ENABLE ROW LEVEL SECURITY;

-- ── Chunks de transcrição (embeddings vetoriais) ─────────────────────────────
ALTER TABLE transcript_chunks ENABLE ROW LEVEL SECURITY;

-- ── Entidades NLP ────────────────────────────────────────────────────────────
ALTER TABLE meeting_entities  ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_dictionary ENABLE ROW LEVEL SECURITY;

-- ── Qualidade de reuniões ────────────────────────────────────────────────────
ALTER TABLE meeting_quality_scores ENABLE ROW LEVEL SECURITY;

-- ── Batch ────────────────────────────────────────────────────────────────────
ALTER TABLE batch_log ENABLE ROW LEVEL SECURITY;

-- ── Multi-tenant auth (CRÍTICO — armazena API keys) ──────────────────────────
ALTER TABLE tenants       ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_users  ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenant_config ENABLE ROW LEVEL SECURITY;

-- ─────────────────────────────────────────────────────────────────────────────
-- VERIFICAÇÃO: execute após a migração para confirmar
-- ─────────────────────────────────────────────────────────────────────────────
-- SELECT schemaname, tablename, rowsecurity
-- FROM pg_tables
-- WHERE schemaname = 'public'
-- ORDER BY tablename;
--
-- Todas as linhas devem ter rowsecurity = true.
-- ─────────────────────────────────────────────────────────────────────────────
