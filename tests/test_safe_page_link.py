# tests/test_safe_page_link.py
"""
UX-01 (melhorias/ux-amigabilidade-e-elegancia.md, achado em auditoria de
produção 2026-09-28): pages/Home.py quebrava com StreamlitPageNotFoundError
em reload a frio — o menu (st.navigation() em app.py) é montado com
is_admin() calculado ANTES da sessão persistente (NAV-05) terminar de
restaurar; um usuário Master via cookie via um st.page_link para uma
página admin que ainda não tinha sido registrada nesta execução.

Causa raiz corrigida em ui/auth_gate.py::_maybe_restore_session() (agora
força st.rerun() assim que a sessão é restaurada, antes de qualquer
st.navigation() rodar com o papel desatualizado — ver
tests/test_session_restore.py::TestSuccessfulRestoreForcesRerunBeforeRenderingNav16).

Este arquivo cobre a camada de defesa complementar pedida pelo UX-01:
ui/components/safe_page_link.py nunca deixa esse erro derrubar a página,
mesmo se a mesma janela de corrida se repetir por outro motivo.

Testado via mock direto de st.page_link/st.caption (não via AppTest real)
de propósito: vários outros arquivos deste projeto fazem
`st.page_link = lambda *a, **k: None` em nível de módulo, sem nunca
restaurar — um monkeypatch global que sobrevive entre arquivos na mesma
sessão pytest (mesma armadilha documentada em vários outros testes deste
repositório) e mascararia justamente o comportamento real que este teste
precisa observar (a exceção sendo de fato lançada e capturada).
"""

from unittest.mock import patch

from streamlit.errors import StreamlitPageNotFoundError

from ui.components.safe_page_link import safe_page_link


class TestSafePageLinkNeverCrashes:
    def test_falls_back_to_caption_when_page_not_registered(self):
        with patch("streamlit.page_link",
                   side_effect=StreamlitPageNotFoundError("pages/MasterAdmin.py", ".", True)) as _link, \
             patch("streamlit.caption") as _caption:
            safe_page_link("pages/MasterAdmin.py", label="Abrir Master Admin", icon="🛡️")

        _link.assert_called_once()
        _caption.assert_called_once()
        assert "Abrir Master Admin" in _caption.call_args[0][0]

    def test_behaves_like_plain_page_link_when_page_is_registered(self):
        with patch("streamlit.page_link") as _link, \
             patch("streamlit.caption") as _caption:
            safe_page_link("pages/MasterAdmin.py", label="Abrir Master Admin", icon="🛡️")

        _link.assert_called_once()
        _caption.assert_not_called()

    def test_only_catches_the_specific_page_not_found_error(self):
        """safe_page_link não deve engolir outras exceções — só a que ele
        sabe tratar (página ainda não registrada nesta execução)."""
        with patch("streamlit.page_link", side_effect=RuntimeError("outra coisa")):
            try:
                safe_page_link("pages/MasterAdmin.py", label="x")
            except RuntimeError:
                return
        raise AssertionError("RuntimeError deveria ter propagado, não ser engolida")
