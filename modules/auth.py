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
        "hash": "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9",
        "nome": "Administrador",
    },
    "demo": {
        "hash": "3fb59388d9fcc5f7b965bc0f1747bea74c0f59102e733e1a7279911899e2879b",
        "nome": "Usuário Demo",
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


def logout() -> None:
    for key in ("_autenticado", "_usuario_login", "_usuario_nome", "_login_erro"):
        st.session_state.pop(key, None)
    st.rerun()
