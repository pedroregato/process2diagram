# modules/session_cookie.py
# ─────────────────────────────────────────────────────────────────────────────
# Cookie de sessão persistente (NAV-05, PC214) — via streamlit_javascript,
# já pinado em requirements.txt (nenhuma dependência nova).
#
# Não é HttpOnly — nenhuma opção é, num app Streamlit puro sem proxy
# reverso: qualquer cookie definido a partir do código Python passa por JS
# injetado no navegador (inclusive via extra-streamlit-components, que o
# plano original cogitava — mesmo mecanismo por baixo). Mesmo perfil de
# exposição de qualquer SPA que persiste sessão client-side.
#
# streamlit_javascript entrega o valor de forma ASSÍNCRONA: a 1ª chamada
# num rerun novo tipicamente devolve 0 (o "default" do componente, não
# None) mesmo com cookie presente — o valor real só chega no rerun
# seguinte, disparado automaticamente pelo componente quando o JS retorna.
# Ver ui/auth_gate.py::_maybe_restore_session() para o tratamento dessa
# corrida (2 tentativas, sem "flash" de tela de login pra quem tem sessão
# válida).
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

_COOKIE_NAME = "p2d_session"
_COOKIE_MAX_AGE_SECONDS = 12 * 60 * 60  # 12h — mesma janela de core/project_store.py::_SESSION_TTL_HOURS


def read_session_cookie() -> str | None:
    """Lê o cookie de sessão do navegador. None se ausente, componente
    ainda não entregou o valor, ou streamlit_javascript indisponível."""
    try:
        from streamlit_javascript import st_javascript
    except Exception:
        return None
    js = (
        "(() => { "
        f"const m = document.cookie.match('(^|;)\\\\s*{_COOKIE_NAME}\\\\s*=\\\\s*([^;]+)'); "
        "return m ? m.pop() : null; "
        "})()"
    )
    try:
        value = st_javascript(js)
    except Exception:
        return None
    if not value or not isinstance(value, str):
        return None
    return value


def write_session_cookie(token: str) -> None:
    """Grava o cookie de sessão no navegador (12h, path=/, SameSite=Lax)."""
    try:
        from streamlit_javascript import st_javascript
    except Exception:
        return
    js = (
        f"document.cookie = '{_COOKIE_NAME}={token}; "
        f"max-age={_COOKIE_MAX_AGE_SECONDS}; path=/; SameSite=Lax'; true"
    )
    try:
        st_javascript(js)
    except Exception:
        pass


def clear_session_cookie() -> None:
    """Remove o cookie de sessão (Logout)."""
    try:
        from streamlit_javascript import st_javascript
    except Exception:
        return
    js = f"document.cookie = '{_COOKIE_NAME}=; max-age=0; path=/'; true"
    try:
        st_javascript(js)
    except Exception:
        pass
