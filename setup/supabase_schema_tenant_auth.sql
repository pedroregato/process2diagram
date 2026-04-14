-- setup/supabase_schema_tenant_auth.sql
-- -----------------------------------------------------------------------------
-- Multi-tenant authentication tables
-- Empresas (dominios), usuarios por tenant e configuracoes (API keys).
--
-- Execute este script no SQL Editor do Supabase.
-- -----------------------------------------------------------------------------


-- 1. Tenants (empresas / dominios)
CREATE TABLE IF NOT EXISTS tenants (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    domain_slug  TEXT        NOT NULL UNIQUE,
    display_name TEXT        NOT NULL,
    active       BOOLEAN     NOT NULL DEFAULT true,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS tenants_domain_idx ON tenants (domain_slug);

ALTER TABLE tenants DISABLE ROW LEVEL SECURITY;

COMMENT ON TABLE tenants IS
    'Empresas ou dominios que acessam o Process2Diagram (ex: FGV, ACME).';
COMMENT ON COLUMN tenants.domain_slug IS
    'Identificador curto usado na tela de login (ex: fgv, acme). Case-insensitive na aplicacao.';


-- 2. Usuarios por tenant
CREATE TABLE IF NOT EXISTS tenant_users (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    login         TEXT        NOT NULL,
    password_hash TEXT        NOT NULL,
    display_name  TEXT        NOT NULL,
    role          TEXT        NOT NULL DEFAULT 'user',
    active        BOOLEAN     NOT NULL DEFAULT true,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, login)
);

CREATE INDEX IF NOT EXISTS tenant_users_tenant_idx ON tenant_users (tenant_id);
CREATE INDEX IF NOT EXISTS tenant_users_login_idx  ON tenant_users (tenant_id, login);

ALTER TABLE tenant_users DISABLE ROW LEVEL SECURITY;

COMMENT ON TABLE tenant_users IS
    'Usuarios cadastrados por tenant. Login unico dentro de cada dominio.';
COMMENT ON COLUMN tenant_users.password_hash IS
    'SHA-256 hex da senha (mesmo padrao do modulo auth.py atual).';
COMMENT ON COLUMN tenant_users.role IS
    'Perfil do usuario: ''admin'' pode salvar API keys do dominio; ''user'' so le.';


-- 3. Configuracoes do tenant (API keys e preferencias)
CREATE TABLE IF NOT EXISTS tenant_config (
    id           UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id    UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    config_key   TEXT        NOT NULL,
    config_value TEXT        NOT NULL,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, config_key)
);

CREATE INDEX IF NOT EXISTS tenant_config_tenant_idx ON tenant_config (tenant_id);

ALTER TABLE tenant_config DISABLE ROW LEVEL SECURITY;

COMMENT ON TABLE tenant_config IS
    'Configuracoes por tenant: API keys dos provedores de IA, preferencias, etc.';
COMMENT ON COLUMN tenant_config.config_key IS
    'Nome da configuracao: deepseek_key, openai_key, gemini_key, groq_key, anthropic_key.';
COMMENT ON COLUMN tenant_config.config_value IS
    'Valor da configuracao. Para POC armazenado em texto claro; migrar para AES-256 em producao.';
