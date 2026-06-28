-- supabase_migration_api_keys.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Tabela de API keys para a API comercial (api.py).
-- Armazena apenas o SHA-256 da chave — nunca a chave em texto claro.
--
-- Executar via psycopg2 (local) ou Supabase SQL Editor.
-- ─────────────────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS api_keys (
    id           uuid        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    key_hash     text        NOT NULL UNIQUE,   -- SHA-256(raw_key), hex 64 chars
    name         text        NOT NULL,           -- rótulo descritivo (cliente/tenant)
    is_active    boolean     NOT NULL DEFAULT true,
    created_at   timestamptz NOT NULL DEFAULT now(),
    last_used_at timestamptz                     -- atualizado a cada request autenticado
);

-- Índice de busca por hash (lookup crítico em todo request autenticado)
CREATE INDEX IF NOT EXISTS api_keys_hash_idx ON api_keys (key_hash);

-- Comentários de documentação
COMMENT ON TABLE  api_keys             IS 'API keys para autenticação da API comercial Process2Diagram. Armazena apenas SHA-256 — nunca o texto claro.';
COMMENT ON COLUMN api_keys.key_hash    IS 'SHA-256 hex da raw key. Gerado em Python: hashlib.sha256(raw_key.encode()).hexdigest()';
COMMENT ON COLUMN api_keys.name        IS 'Rótulo identificador do cliente ou integração (ex: "Cliente XPTO - Produção").';
COMMENT ON COLUMN api_keys.is_active   IS 'False = key revogada. Retorna 403 em qualquer request.';
COMMENT ON COLUMN api_keys.last_used_at IS 'Timestamp do último request autenticado com esta key. Atualizado de forma fire-and-forget (fail-open).';

-- ─────────────────────────────────────────────────────────────────────────────
-- Inserir uma key de exemplo (para desenvolvimento/teste local)
-- Gerar o hash: python -c "import hashlib; print(hashlib.sha256(b'minha-api-key-dev').hexdigest())"
-- ─────────────────────────────────────────────────────────────────────────────
-- INSERT INTO api_keys (key_hash, name) VALUES
--     ('<hash_sha256_aqui>', 'Dev Local - Teste');
