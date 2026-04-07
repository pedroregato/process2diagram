# modules/auth.py
# ─────────────────────────────────────────────────────────────────────────────
# Authentication layer for Process2Diagram.
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

import streamlit as st


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
    """Load users dict from st.secrets['auth']['users'].

    Returns an empty dict when no auth section is configured —
    this disables auth (local dev without secrets.toml).
    """
    try:
        auth_section = st.secrets.get("auth", {})
        users = auth_section.get("users", {})
        return dict(users) if users else {}
    except Exception:
        return {}


def auth_required() -> bool:
    """True when credentials are configured and auth should be enforced."""
    return bool(_load_users())


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


# ── Login page ────────────────────────────────────────────────────────────────

_LOGIN_CSS = """
<style>
/* Dark gradient background */
[data-testid="stAppViewContainer"] > .main {
    background: linear-gradient(145deg, #0B1E3D 0%, #1A3A6B 60%, #0F2850 100%);
    min-height: 100vh;
}
[data-testid="stAppViewContainer"] {
    background: linear-gradient(145deg, #0B1E3D 0%, #1A3A6B 60%, #0F2850 100%);
}
/* Hide sidebar on login page */
[data-testid="stSidebar"] { display: none !important; }
/* Hide the top header */
[data-testid="stHeader"] { background: transparent !important; }
/* Card */
.login-card {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 16px;
    padding: 2.5rem 2.5rem 2rem;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
}
.login-logo {
    font-size: 2.6rem;
    text-align: center;
    margin-bottom: 0.2rem;
}
.login-title {
    color: #FFFFFF;
    font-size: 1.7rem;
    font-weight: 700;
    text-align: center;
    letter-spacing: -0.5px;
    margin-bottom: 0.15rem;
}
.login-subtitle {
    color: rgba(255,255,255,0.55);
    font-size: 0.85rem;
    text-align: center;
    margin-bottom: 1.8rem;
}
.login-divider {
    border: none;
    border-top: 1px solid rgba(255,255,255,0.10);
    margin: 1.4rem 0;
}
/* Override Streamlit input labels inside form */
.login-card label { color: rgba(255,255,255,0.80) !important; font-size: 0.82rem !important; }
/* Button override */
.login-card .stButton > button {
    background: linear-gradient(90deg, #C97B1A, #E8941A) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    letter-spacing: 0.3px;
    height: 2.6rem;
    width: 100%;
    transition: opacity .15s;
}
.login-card .stButton > button:hover { opacity: 0.88; }
.login-footer {
    color: rgba(255,255,255,0.30);
    font-size: 0.72rem;
    text-align: center;
    margin-top: 1.4rem;
}
</style>
"""


def render_login_page() -> None:
    """Render the full-page login form.

    Call this when ``is_authenticated()`` returns False.
    The caller is responsible for calling ``st.stop()`` afterwards so
    the rest of the page does not render.
    """
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    # Center the card using columns
    _, col, _ = st.columns([1, 1.4, 1])
    with col:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.markdown('<div class="login-logo">⚡</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-title">Process2Diagram</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="login-subtitle">Multi-agent process intelligence platform</div>',
            unsafe_allow_html=True,
        )
        st.markdown('<hr class="login-divider">', unsafe_allow_html=True)

        with st.form("p2d_login", clear_on_submit=False):
            username = st.text_input("Usuário", placeholder="seu.usuario")
            password = st.text_input("Senha", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Entrar →", use_container_width=True)

        if submitted:
            _attempt_login(username.strip(), password)

        st.markdown(
            '<div class="login-footer">Process2Diagram v4.6 · Acesso restrito</div>',
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)


def _attempt_login(username: str, password: str) -> None:
    """Validate credentials and update session state."""
    if not username or not password:
        st.warning("Preencha usuário e senha.")
        return

    users = _load_users()
    user_data = users.get(username)

    if user_data is None:
        # Deliberate vague message — don't reveal whether user exists
        st.error("Usuário ou senha incorretos.")
        return

    # user_data may be a plain dict or a Streamlit AttrDict
    stored_hash = (
        user_data.get("password_hash", "")
        if hasattr(user_data, "get")
        else getattr(user_data, "password_hash", "")
    )

    if _verify_password(password, stored_hash):
        display_name = (
            user_data.get("name", username)
            if hasattr(user_data, "get")
            else getattr(user_data, "name", username)
        )
        st.session_state.authenticated = True
        st.session_state.auth_user = username
        st.session_state.auth_name = display_name
        st.rerun()
    else:
        st.error("Usuário ou senha incorretos.")
