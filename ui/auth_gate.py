# ui/auth_gate.py
# ─────────────────────────────────────────────────────────────────────────────
# Authentication UI — login page rendering and session gate.
#
# Pattern mirrors DataJudMonitor/auth.py:
#   • st.button (not st.form) — simpler rerun model
#   • error state stored in st.session_state["_login_erro"]
#   • render_login_page() calls st.stop() at the end
#   • apply_auth_gate() is the single entry point for every page
#
# Business logic (credential loading, password verification, session helpers)
# lives in modules/auth.py.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import streamlit as st

from modules.auth import _load_users, _extract_name, login_valido, is_authenticated, auth_required

# ── Login page styles ─────────────────────────────────────────────────────────

_LOGIN_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans:wght@300;400;600&display=swap');
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewBlockContainer"],
.main .block-container {
    background: #0A1628 !important;
    min-height: 100vh !important;
    padding-top: 0 !important;
    font-family: 'IBM Plex Sans', sans-serif;
}
section[data-testid="stSidebar"],
header[data-testid="stHeader"],
div[data-testid="stToolbar"],
[data-testid="stDecoration"] { display: none !important; }
.l-card {
    max-width: 420px;
    margin: 0 auto;
    padding-top: 8vh;
}
.l-banner {
    background: linear-gradient(135deg, #0B1E3D 0%, #1A3A6B 100%);
    border-bottom: 3px solid #C97B1A;
    border-radius: 10px 10px 0 0;
    padding: 1.8rem 2rem 1.5rem;
    text-align: center;
}
.l-banner .icon  { font-size: 2.8rem; line-height: 1; margin-bottom: .5rem; }
.l-banner .title {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 1.7rem;
    color: #FAFAF8;
    margin: 0 0 .2rem;
    letter-spacing: -.01em;
}
.l-banner .sub {
    font-size: .75rem;
    color: #8899AA;
    letter-spacing: .08em;
    text-transform: uppercase;
}
.l-body {
    background: #0F2040;
    border-radius: 0 0 10px 10px;
    padding: 2rem;
    border: 1px solid #1e3a55;
    border-top: none;
}
.l-label {
    font-size: .75rem;
    font-weight: 600;
    color: #8899AA;
    letter-spacing: .08em;
    text-transform: uppercase;
    margin-bottom: .3rem;
}
.l-err {
    background: rgba(192,57,43,.15);
    border: 1px solid rgba(192,57,43,.4);
    border-radius: 6px;
    color: #E74C3C;
    font-size: .82rem;
    padding: .6rem .9rem;
    margin-bottom: 1rem;
}
.l-cfg-err {
    background: rgba(201,123,26,.12);
    border: 1px solid rgba(201,123,26,.4);
    border-radius: 6px;
    color: #E8941A;
    font-size: .8rem;
    padding: .6rem .9rem;
    margin-bottom: 1rem;
}
.l-foot {
    margin-top: 1.2rem;
    text-align: center;
    font-size: .7rem;
    color: #445566;
}
div[data-testid="stTextInput"] input {
    background: #0D1B2A !important;
    border: 1px solid #1e3a55 !important;
    color: #FAFAF8 !important;
    border-radius: 6px !important;
}
div[data-testid="stTextInput"] input:focus {
    border-color: #C97B1A !important;
    box-shadow: 0 0 0 2px rgba(201,123,26,.2) !important;
}
div[data-testid="stTextInput"] label { color: #8899AA !important; font-size:.75rem !important; }
div[data-testid="stButton"] button {
    background: linear-gradient(135deg, #C97B1A, #E8941A) !important;
    color: #fff !important;
    font-weight: 700 !important;
    border: none !important;
    border-radius: 6px !important;
    width: 100%;
    font-size: .9rem !important;
    letter-spacing: .04em;
    margin-top: .5rem;
}
</style>
"""


# ── Login page ────────────────────────────────────────────────────────────────

def render_login_page() -> None:
    """Render the full-page login form and call st.stop().

    Mirrors the DataJudMonitor pattern: uses st.button (not st.form),
    stores error state in session_state, and always ends with st.stop()
    so the rest of the page never renders.
    """
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    # Check for credential config errors
    cfg_error: str | None = None
    try:
        _load_users()
    except RuntimeError as exc:
        cfg_error = str(exc)

    erro = st.session_state.get("_login_erro", False)

    erro_html = '<div class="l-err">⚠️ Usuário ou senha incorretos.</div>' if erro else ""
    cfg_html  = f'<div class="l-cfg-err">⚙️ Erro de configuração: {cfg_error}</div>' if cfg_error else ""

    st.markdown(f"""
    <div class="l-card">
      <div class="l-banner">
        <div class="icon">⚡</div>
        <div class="title">Process2Diagram</div>
        <div class="sub">Multi-agent process intelligence platform</div>
      </div>
      <div class="l-body">
        {cfg_html}{erro_html}
        <div class="l-label">Usuário</div>
    """, unsafe_allow_html=True)

    usuario = st.text_input("Usuário", label_visibility="collapsed", key="_l_user",
                            placeholder="seu.usuario")
    st.markdown('<div class="l-label" style="margin-top:.8rem">Senha</div>',
                unsafe_allow_html=True)
    senha = st.text_input("Senha", type="password", label_visibility="collapsed",
                          key="_l_pass", placeholder="••••••••")

    if st.button("Entrar →", use_container_width=True, key="_l_btn"):
        uname = usuario.strip()
        if login_valido(uname, senha):
            users = _load_users()
            user_data = users.get(uname) or users.get(uname.upper())
            st.session_state["_autenticado"]   = True
            st.session_state["_usuario_login"] = uname
            st.session_state["_usuario_nome"]  = _extract_name(user_data, uname)
            st.session_state["_login_erro"]    = False
            st.rerun()
        else:
            st.session_state["_login_erro"] = True
            st.rerun()

    st.markdown("""
      <div class="l-foot">Process2Diagram v4.6 · Acesso restrito</div>
      </div></div>
    """, unsafe_allow_html=True)

    st.stop()


# ── Gate ──────────────────────────────────────────────────────────────────────

def apply_auth_gate() -> None:
    """Enforce authentication gate.

    Call once, immediately after st.set_page_config(), on every page.
    If not authenticated, renders the login page and halts execution.
    """
    if not is_authenticated():
        render_login_page()
