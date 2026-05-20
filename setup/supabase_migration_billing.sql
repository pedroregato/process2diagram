-- setup/supabase_migration_billing.sql
-- ─────────────────────────────────────────────────────────────────────────────
-- Billing tables: user credits + payment log
-- Execute once in Supabase → SQL Editor
-- ─────────────────────────────────────────────────────────────────────────────

-- ── user_credits ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_credits (
    id                          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                     TEXT        NOT NULL UNIQUE,
    email                       TEXT,
    creditos_restantes          INTEGER     NOT NULL DEFAULT 0,
    degustacao_ativa            BOOLEAN     NOT NULL DEFAULT TRUE,
    data_expiracao_degustacao   TIMESTAMPTZ,
    is_contribuidor             BOOLEAN     NOT NULL DEFAULT FALSE,
    plano                       TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_credits_user_id ON user_credits(user_id);
CREATE INDEX IF NOT EXISTS idx_user_credits_updated ON user_credits(updated_at DESC);

-- Auto-update updated_at on every change
CREATE OR REPLACE FUNCTION _billing_set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS user_credits_updated_at ON user_credits;
CREATE TRIGGER user_credits_updated_at
    BEFORE UPDATE ON user_credits
    FOR EACH ROW EXECUTE FUNCTION _billing_set_updated_at();

ALTER TABLE user_credits DISABLE ROW LEVEL SECURITY;


-- ── pagamentos ────────────────────────────────────────────────────────────────
-- Immutable payment log. Status: pending | paid | failed | simulated | refunded
CREATE TABLE IF NOT EXISTS pagamentos (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     TEXT        NOT NULL,
    email       TEXT,
    valor       NUMERIC     NOT NULL,
    plano       TEXT,
    creditos    INTEGER     NOT NULL DEFAULT 0,
    status      TEXT        NOT NULL DEFAULT 'pending',
    external_id TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pagamentos_user_id    ON pagamentos(user_id);
CREATE INDEX IF NOT EXISTS idx_pagamentos_status     ON pagamentos(status);
CREATE INDEX IF NOT EXISTS idx_pagamentos_created_at ON pagamentos(created_at DESC);

ALTER TABLE pagamentos DISABLE ROW LEVEL SECURITY;
