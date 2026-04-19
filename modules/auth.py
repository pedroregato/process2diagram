# modules/auth.py
# ─────────────────────────────────────────────────────────────────────────────
# Autenticação do Process2Diagram — padrão DataJudMonitor.
#
# Credenciais hardcoded — sem dependência de secrets.toml, caminhos,
# parsing de TOML ou lógica condicional que possa desativar o login.
#
# Para gerar um novo hash:
#   python -c "import hashlib; print(hashlib.sha256(b'SENHA').hexdigest())"
# ─────────────────────────────────────────────────────────────────────────────

import hashlib
import streamlit as st

# ── Credenciais ───────────────────────────────────────────────────────────────

USUARIOS = {
    "admin": {
        "hash": "b5cda95e2e42318a9d2ab8d0f77d77d8f2319d4cf09f73219efe9d716b30caf6",
        "nome": "Administrador",
        "role": "admin",
    },
    "demo": {
        "hash": "2c3749eab531cf5fd3f8fca77f80b1b2a4c2efab51c3a66badff46fca754f8fa",
        "nome": "Usuário Demo",
        "role": "user",
    },
}


# ── Lógica de autenticação ────────────────────────────────────────────────────

def _hash(senha: str) -> str:
    return hashlib.sha256(senha.encode()).hexdigest()


def login_valido(usuario: str, senha: str) -> bool:
    u = USUARIOS.get(usuario.lower().strip())
    return u is not None and u["hash"] == _hash(senha)


def is_authenticated() -> bool:
    return bool(st.session_state.get("_autenticado"))


def get_current_user() -> str | None:
    return st.session_state.get("_usuario_login")


def get_current_name() -> str | None:
    return st.session_state.get("_usuario_nome")


def is_admin() -> bool:
    """Returns True if the current session user has admin role.

    Checks _role from session_state first (set by both tenant and local login).
    Falls back to USUARIOS dict lookup for sessions that predate role storage.
    """
    role = st.session_state.get("_role")
    if role:
        return role == "admin"
    # Fallback: derive from USUARIOS for existing sessions
    user = get_current_user()
    if not user:
        return False
    u = USUARIOS.get(user.lower().strip())
    return u is not None and u.get("role") == "admin"


def logout() -> None:
    for key in (
        "_autenticado", "_usuario_login", "_usuario_nome", "_login_erro",
        "_tenant_id", "_domain", "_tenant_name", "_role",
    ):
        st.session_state.pop(key, None)
    st.rerun()
