-- user_sessions — PC214 (NAV-05, melhorias/parciais/navegabilidade.md)
--
-- Sessão persistente multi-tenant: F5, link direto ou fechar/reabrir o
-- navegador mantêm o usuário logado (até 12h de inatividade), com o mesmo
-- contexto de trabalho ativo. Escopo: só o modo de login multi-tenant
-- (ui/auth_gate.py::_handle_tenant_login) — o modo local (USUARIOS
-- hardcoded em modules/auth.py) é fallback de desenvolvimento/emergência e
-- permanece efêmero.
--
-- Token opaco (secrets.token_urlsafe(32)) gerado no login e devolvido só
-- para o navegador do usuário via cookie — no banco fica SÓ o hash
-- SHA-256 (token_hash), nunca o valor em si, mesmo padrão de
-- tenant_users.password_hash.
--
-- last_context_id espelha active_project_id (NAV-04) — atualizado a cada
-- troca de contexto via ui/project_selector.py::activate_context(), e
-- restaurado em active_project_id quando a sessão é validada
-- (ui/auth_gate.py::_try_restore_session()).

CREATE TABLE IF NOT EXISTS user_sessions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash       TEXT NOT NULL UNIQUE,
    tenant_id        UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    username         TEXT NOT NULL,
    last_context_id  UUID REFERENCES contexts(id) ON DELETE SET NULL,
    expires_at       TIMESTAMPTZ NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_token_hash ON user_sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);

ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE user_sessions IS 'PC214 (NAV-05) — sessão persistente multi-tenant via token opaco (hash SHA-256, nunca o valor em si) + contexto ativo (last_context_id), restaurados no reload via cookie (streamlit_javascript). Expiração deslizante de 12h — renovada a cada validação bem-sucedida em core/project_store.py::validate_user_session(). Linhas expiradas não têm limpeza automática ainda (não implementada nesta rodada — ver nota no roadmap PC214).';
