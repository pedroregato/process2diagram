# tests/test_page_casos_de_uso.py
"""
Tests for pages/Orientacoes_CasosDeUso.py — new business-value use-case
guide (2026-07-11) for the Assistente. Single source of scenario data feeds
both the in-app Streamlit rendering and the standalone HTML export button;
this test exercises both paths.
"""

from streamlit.testing.v1 import AppTest


def _base_app():
    at = AppTest.from_file("pages/Orientacoes_CasosDeUso.py", default_timeout=30)
    at.session_state["_autenticado"] = True
    at.session_state["_usuario_login"] = "teste"
    at.session_state["_usuario_nome"] = "Teste"
    at.session_state["_role"] = "admin"
    at.session_state["active_project_id"] = "p1"
    at.session_state["active_project_name"] = "Projeto Teste"
    return at


class TestCasosDeUsoBootSmoke:
    def test_page_renders_without_exception(self):
        at = _base_app()
        at.run()
        assert not at.exception

    def test_renders_a_tab_per_scenario_category_and_one_download_button(self):
        at = _base_app()
        at.run()
        assert len(at.tabs) == 5  # one per _SCENARIOS category
        assert len(at.get("download_button")) == 1


class TestStandaloneHtmlExport:
    def _build_html(self) -> str:
        import runpy
        import ui.auth_gate as ag
        original = ag.apply_auth_gate
        ag.apply_auth_gate = lambda: None
        try:
            ns = runpy.run_path("pages/Orientacoes_CasosDeUso.py", run_name="__not_main__")
        finally:
            ag.apply_auth_gate = original
        return ns["_build_standalone_html"]()

    def test_html_is_well_formed_and_self_contained(self):
        html = self._build_html()
        assert html.strip().startswith("<!doctype html>")
        assert "<title>" in html
        assert "http://" not in html and "https://" not in html  # no CDN/external refs

    def test_html_includes_every_scenario_category_and_tool_name(self):
        import runpy
        import ui.auth_gate as ag
        original = ag.apply_auth_gate
        ag.apply_auth_gate = lambda: None
        try:
            ns = runpy.run_path("pages/Orientacoes_CasosDeUso.py", run_name="__not_main__")
        finally:
            ag.apply_auth_gate = original

        html = ns["_build_standalone_html"]()
        scenarios = ns["_SCENARIOS"]
        assert len(scenarios) >= 3  # meaningfully more than a stub

        for category, items in scenarios.items():
            assert category in html
            for s in items:
                assert s["pergunta"] in html
                if s.get("tool"):
                    assert s["tool"] in html

    def test_new_pc179_tools_are_represented_as_scenarios(self):
        html = self._build_html()
        for tool in ("exportar_pacote_completo", "sugerir_encaminhamentos_pendentes",
                     "pesquisar_multi_contexto"):
            assert tool in html, f"{tool} (PC179) missing from the use-case guide"
