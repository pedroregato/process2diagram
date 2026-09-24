# tests/test_session_restore.py
"""
NAV-05 (melhorias/parciais/navegabilidade.md, PC214): F5 ou link direto
reiniciava st.session_state — is_authenticated() só olhava
st.session_state["_autenticado"] (modules/auth.py), então uma sessão válida
sempre voltava pra tela de login, sem contexto de trabalho ativo.

Fix: ui/auth_gate.py::_maybe_restore_session()/_try_restore_session() —
antes de mostrar o login, tenta restaurar via cookie persistente (token
opaco, validado contra a tabela user_sessions em
core/project_store.py::validate_user_session()). Sessão válida repovoa
_autenticado/_usuario_login/_tenant_id/etc. e active_project_id a partir de
last_context_id.

Este teste usa uma página mínima via AppTest.from_string() — só
apply_auth_gate() + um marcador — em vez de uma página real do app, pra
isolar o mecanismo de restauração sem precisar mockar dados de negócio sem
relação com o que está sendo testado aqui.
"""

from unittest.mock import patch

from streamlit.testing.v1 import AppTest

_PAGE_SRC = """
import streamlit as st
from ui.auth_gate import apply_auth_gate
apply_auth_gate()
st.markdown("PAGE_CONTENT_RENDERED")
"""

_USER = {
    "tenant_id":    "tenant-1",
    "domain":       "fgv",
    "tenant_name":  "FGV",
    "user_id":      "u1",
    "user_name":    "pedro",
    "display_name": "Pedro",
    "role":         "user",
}

_CTX = {"id": "ctx-a", "name": "Contexto A", "sigla": "CTXA"}


def _patched(read_cookie_value, session_value, user_value=_USER, ctx_value=None):
    return (
        patch("modules.session_cookie.read_session_cookie", lambda: read_cookie_value),
        patch("core.project_store.validate_user_session", lambda token: session_value),
        patch("modules.tenant_auth.get_tenant_user", lambda tid, login: user_value),
        patch("modules.tenant_config.load_all_config", lambda tid: {}),
        patch("modules.tenant_config.apply_config_to_session", lambda cfg: None),
        patch("ui.project_selector.get_active_context", lambda: ctx_value),
    )


class TestSessionRestoreWithValidToken:
    def test_valid_token_skips_login_and_restores_context(self):
        patches = _patched(
            read_cookie_value="tok-valido",
            session_value={"tenant_id": "tenant-1", "username": "pedro", "last_context_id": "ctx-a"},
            ctx_value=_CTX,
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            at = AppTest.from_string(_PAGE_SRC, default_timeout=30)
            at.run()

        assert not at.exception
        # Nunca mostrou a tela de login — os campos de usuário/senha não existem.
        assert not [ti for ti in at.text_input if ti.key == "_l_user"]
        assert not [ti for ti in at.text_input if ti.key == "_l_pass"]
        # Conteúdo real da página renderizou.
        assert [m for m in at.markdown if "PAGE_CONTENT_RENDERED" in m.value]
        # Sessão e contexto restaurados.
        assert at.session_state["_autenticado"] is True
        assert at.session_state["_usuario_login"] == "pedro"
        assert at.session_state["_tenant_id"] == "tenant-1"
        assert at.session_state["active_project_id"] == "ctx-a"
        assert at.session_state["active_project_name"] == "Contexto A"

    def test_token_updates_session_state_key_for_later_revocation(self):
        """_session_token precisa ficar em session_state pra logout() /
        activate_context() conseguirem revogar/atualizar a sessão depois."""
        patches = _patched(
            read_cookie_value="tok-valido-2",
            session_value={"tenant_id": "tenant-1", "username": "pedro", "last_context_id": None},
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            at = AppTest.from_string(_PAGE_SRC, default_timeout=30)
            at.run()

        assert not at.exception
        assert at.session_state["_session_token"] == "tok-valido-2"


def _run_twice(at: AppTest) -> None:
    """_maybe_restore_session() nunca trata a 1ª tentativa sem sessão como
    definitiva — mostra um placeholder neutro (nunca a tela de login) e
    para, contando com o rerun automático que o componente JS real dispara
    quando entrega o valor do cookie. Um 2º .run() nesta mesma sessão de
    AppTest simula esse rerun; só nele a ausência de sessão vira a tela de
    login de fato."""
    at.run()
    assert not at.exception
    assert not [ti for ti in at.text_input if ti.key == "_l_user"], (
        "1ª tentativa deveria mostrar o placeholder neutro, não o login"
    )
    at.run()


class TestSessionRestoreWithoutValidToken:
    def test_no_cookie_shows_login_page_on_second_attempt(self):
        patches = _patched(read_cookie_value=None, session_value=None)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            at = AppTest.from_string(_PAGE_SRC, default_timeout=30)
            _run_twice(at)

        assert not at.exception
        assert [ti for ti in at.text_input if ti.key == "_l_user"]
        assert "_autenticado" not in at.session_state

    def test_expired_or_unknown_token_shows_login_page_on_second_attempt(self):
        patches = _patched(read_cookie_value="tok-expirado", session_value=None)
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            at = AppTest.from_string(_PAGE_SRC, default_timeout=30)
            _run_twice(at)

        assert not at.exception
        assert [ti for ti in at.text_input if ti.key == "_l_user"]
        assert "_autenticado" not in at.session_state

    def test_deactivated_user_after_login_shows_login_page_on_second_attempt(self):
        """Sessão válida na tabela, mas tenant/usuário foi desativado por um
        admin depois do login — get_tenant_user() rechecagem em tempo real
        deve barrar a restauração mesmo com token e sessão íntegros."""
        patches = _patched(
            read_cookie_value="tok-valido-mas-usuario-desativado",
            session_value={"tenant_id": "tenant-1", "username": "pedro", "last_context_id": None},
            user_value=None,
        )
        with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5]:
            at = AppTest.from_string(_PAGE_SRC, default_timeout=30)
            _run_twice(at)

        assert not at.exception
        assert [ti for ti in at.text_input if ti.key == "_l_user"]
        assert "_autenticado" not in at.session_state
