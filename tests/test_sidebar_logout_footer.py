# tests/test_sidebar_logout_footer.py
"""
NAV-14, parte "Sair no rodapé" (melhorias/parciais/navegabilidade.md):
"Sair" era só mais um st.Page() dentro da seção "Início" — um item de menu
igual a "Sobre o P2D" ou "Segurança de Dados", fácil de perder de vista
entre os outros, e sem nenhuma indicação de QUEM está logado ou em QUAL
contexto/tenant antes de clicar.

Fix: pages/Logout.py removido do dict de st.navigation() (e do repo — sem
nenhuma outra referência de código a ele, virava página órfã/inalcançável).
Em seu lugar, um rodapé fixo em st.sidebar, escrito diretamente em app.py
depois de pg.run() (aparece abaixo de qualquer sidebar específica de página,
como a de Pipeline.py) com o nome do usuário + contexto ativo + botão
"Sair" que chama modules.auth.logout() diretamente — sem depender de
navegação pra um Page dedicado.

Segue o mesmo padrão de tests/test_report_backfill_admin_gate.py: checagem
estática sobre o texto-fonte de app.py — simular o boot completo (auth +
sidebar renderizado) via AppTest exigiria autenticar uma sessão fake dentro
do teste pra sequer alcançar o bloco `if st.session_state.get("_autenticado")`,
overhead desproporcional pra confirmar posicionamento/chamadas de código.
"""

from pathlib import Path

_APP_SRC = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")

_PAGES_DIR = Path(__file__).resolve().parent.parent / "pages"


class TestLogoutPageRemovedFromNavigation:
    def test_logout_page_not_registered_in_any_navigation_section(self):
        assert "pages/Logout.py" not in _APP_SRC

    def test_logout_file_no_longer_exists(self):
        # Página órfã (nenhum st.Page() apontava mais pra ela) — removida
        # do repo em vez de deixada morta.
        assert not (_PAGES_DIR / "Logout.py").exists()


class TestSidebarFooterAddedAfterNavigationRun:
    def test_footer_block_guarded_by_authenticated_check(self):
        assert 'if st.session_state.get("_autenticado"):' in _APP_SRC

    def test_footer_is_written_after_pg_run_so_it_appears_below_page_sidebar(self):
        run_idx = _APP_SRC.index("pg.run()")
        footer_idx = _APP_SRC.index('if st.session_state.get("_autenticado"):')
        assert run_idx < footer_idx

    def test_footer_calls_logout_directly_without_a_dedicated_page(self):
        footer_idx = _APP_SRC.index('if st.session_state.get("_autenticado"):')
        footer_block = _APP_SRC[footer_idx:]
        assert "from modules.auth import get_current_name, logout" in footer_block
        assert "logout()" in footer_block

    def test_footer_shows_user_name_and_active_context(self):
        footer_idx = _APP_SRC.index('if st.session_state.get("_autenticado"):')
        footer_block = _APP_SRC[footer_idx:]
        assert "get_current_name()" in footer_block
        assert '_tenant_name' in footer_block
