# modules/auth.py
# ─────────────────────────────────────────────────────────────────────────────
# Authentication business logic for Process2Diagram.
#
# Responsibilities: credential loading, password hashing/verification,
# session state helpers (is_authenticated, logout, etc.).
#
# UI (login page rendering, CSS, form handling) lives in ui/auth_gate.py.
#
# Credentials are stored in .streamlit/secrets.toml under [auth.users].
# If no [auth] section is present, authentication is skipped entirely
# (convenient for local dev without secrets.toml).
#
# Password format: "sha256$<salt>$<hex_digest>"
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
    """Return a 'sha256$<salt>$<hex>' string suitable for secrets.toml."""
    if salt is None:
        salt = os.urandom(16).hex()
    digest = hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()
    return f"sha256${salt}${digest}"


def _verify_password(password: str, stored: str) -> bool:
    """Constant-time verification against a stored hash string."""
    try:
        scheme, salt, expected = stored.split("$", 2)
        if scheme != "sha256":
            return False
        digest = hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()
        # Use compare_digest to prevent timing attacks
        return hmac.compare_digest(digest, expected)
    except (ValueError, AttributeError):
        return False


# ── Credential loading ────────────────────────────────────────────────────────

def _load_users() -> dict:
    """Load users from credentials configuration.

    Resolution order:
    1. st.secrets["auth"]["users"]  — Streamlit Cloud / runtime injection
    2. .streamlit/secrets.toml read directly by absolute path — local dev

    Returns {} only when no [auth] section exists anywhere (auth disabled).
    Raises RuntimeError when a secrets file exists but cannot be parsed,
    so the caller can display a clear error instead of silently opening access.
    """
    # ── 1. st.secrets (Streamlit Cloud or local Streamlit runtime) ────────────
    try:
        auth_section = st.secrets.get("auth", {})
        if auth_section:
            users = auth_section.get("users", {})
            return dict(users) if users else {}
    except Exception:
        pass  # Fall through to file-based loading

    # ── 2. Direct file read by absolute path (CWD-independent) ───────────────
    if _SECRETS_PATH.exists():
        try:
            data = toml.loads(_SECRETS_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(
                f"secrets.toml encontrado mas não pôde ser lido: {exc}"
            ) from exc
        users = data.get("auth", {}).get("users", {})
        return users  # may be {} if [auth] section absent

    # No secrets file anywhere → auth disabled (open local dev)
    return {}


def auth_required() -> bool:
    """True when credentials are configured and auth should be enforced."""
    try:
        return bool(_load_users())
    except RuntimeError:
        return True  # Fail-closed: broken config still enforces auth


# ── Session helpers ───────────────────────────────────────────────────────────

def is_authenticated() -> bool:
    """True when the current session has passed the login gate."""
    if not auth_required():
        return True   # No credentials configured → open access
    return st.session_state.get("authenticated", False)


def get_current_user() -> str | None:
    return st.session_state.get("auth_user")


def get_current_name() -> str | None:
    return st.session_state.get("auth_name")


def logout() -> None:
    """Clear auth state and force a rerun (returns to login page)."""
    for key in ("authenticated", "auth_user", "auth_name"):
        st.session_state.pop(key, None)
    st.rerun()
