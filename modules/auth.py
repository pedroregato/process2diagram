# modules/auth.py
# ─────────────────────────────────────────────────────────────────────────────
# Authentication business logic for Process2Diagram.
#
# Responsibilities: credential loading, password verification,
# session state helpers (is_authenticated, logout, etc.).
#
# UI (login page rendering, CSS, form handling) lives in ui/auth_gate.py.
#
# Credentials are stored in .streamlit/secrets.toml under [auth.users].
# Supported formats in secrets.toml:
#
#   Format A — plain sha256 (recommended, same as DataJudMonitor):
#     [auth.users]
#     admin = "d4dc7bcc..."   # hashlib.sha256(b"password").hexdigest()
#
#   Format B — salted hash:
#     [auth.users]
#     admin = "sha256$salt$hexdigest"
#
#   Format C — nested (with display name):
#     [auth.users.admin]
#     hash = "d4dc7bcc..."
#     name = "Administrador"
#
# If no [auth] section is present, authentication is skipped (local dev).
# Use setup/generate_password_hash.py to generate hashes.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import hashlib
import hmac
import os
from pathlib import Path

import toml
import streamlit as st

# Absolute path to the secrets file — works regardless of CWD
_SECRETS_PATH = Path(__file__).parent.parent / ".streamlit" / "secrets.toml"


# ── Password utilities ────────────────────────────────────────────────────────

def hash_password(password: str, salt: str | None = None) -> str:
    """Return a salted hash string 'sha256$<salt>$<hex>' for secrets.toml."""
    if salt is None:
        salt = os.urandom(16).hex()
    digest = hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()
    return f"sha256${salt}${digest}"


def hash_password_plain(password: str) -> str:
    """Return a plain sha256 hex digest (no salt). Same as DataJudMonitor."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def _verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored hash.

    Supports three stored formats:
      - "sha256$<salt>$<hex>"  — salted (Process2Diagram native)
      - "<64-char hex>"        — plain sha256 (DataJudMonitor compatible)
    """
    if not stored:
        return False
    try:
        if stored.startswith("sha256$"):
            # Salted format: sha256$salt$hexdigest
            _, salt, expected = stored.split("$", 2)
            digest = hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()
            return hmac.compare_digest(digest, expected)
        else:
            # Plain sha256 (no salt)
            digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
            return hmac.compare_digest(digest, stored)
    except Exception:
        return False


# ── Credential loading ────────────────────────────────────────────────────────

def _load_users() -> dict:
    """Load users dict from st.secrets or secrets.toml file.

    Returns a dict mapping username → hash_string (or nested dict with 'hash'/'password_hash').
    Returns {} only when no [auth] section exists (auth disabled for local dev).
    """
    # ── 1. st.secrets (Streamlit runtime — Cloud and local streamlit run) ─────
    try:
        users = st.secrets["auth"]["users"]
        result = dict(users)
        if result:
            return result
    except Exception:
        pass  # fall through to direct file read

    # ── 2. Direct file read — CWD-independent absolute path ──────────────────
    if not _SECRETS_PATH.exists():
        return {}  # no secrets file → auth disabled

    try:
        data = toml.loads(_SECRETS_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"secrets.toml não pôde ser lido: {exc}") from exc

    users = data.get("auth", {}).get("users", {})
    return users  # {} if [auth.users] absent → auth disabled


def _extract_hash(user_data) -> str:
    """Extract the hash string from a user record (any supported format)."""
    if isinstance(user_data, str):
        return user_data
    if hasattr(user_data, "get"):
        return user_data.get("hash", "") or user_data.get("password_hash", "")
    return getattr(user_data, "hash", "") or getattr(user_data, "password_hash", "")


def _extract_name(user_data, fallback: str) -> str:
    """Extract the display name from a user record."""
    if isinstance(user_data, str):
        return fallback
    if hasattr(user_data, "get"):
        return user_data.get("name", fallback)
    return getattr(user_data, "name", fallback)


def login_valido(usuario: str, senha: str) -> bool:
    """Return True if the username/password combination is valid."""
    users = _load_users()
    # Try both as-is and uppercased (DataJudMonitor stores keys in uppercase)
    user_data = users.get(usuario.strip()) or users.get(usuario.upper().strip())
    if user_data is None:
        return False
    return _verify_password(senha, _extract_hash(user_data))


# ── Session helpers ───────────────────────────────────────────────────────────

def auth_required() -> bool:
    """True when credentials are configured and auth should be enforced."""
    try:
        return bool(_load_users())
    except RuntimeError:
        return True  # Fail-closed: broken config still enforces auth


def is_authenticated() -> bool:
    """True when the current session has passed the login gate."""
    if not auth_required():
        return True  # No credentials configured → open access
    return bool(st.session_state.get("_autenticado"))


def get_current_user() -> str | None:
    return st.session_state.get("_usuario_login")


def get_current_name() -> str | None:
    return st.session_state.get("_usuario_nome")


def logout() -> None:
    """Clear auth state and force a rerun (returns to login page)."""
    for key in ("_autenticado", "_usuario_login", "_usuario_nome", "_login_erro"):
        st.session_state.pop(key, None)
    st.rerun()
