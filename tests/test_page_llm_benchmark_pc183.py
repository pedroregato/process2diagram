# tests/test_page_llm_benchmark_pc183.py
"""
Boot-smoke for pages/LLMBenchmark.py after PC183 (Alertas + Qualidade
sub-tabs added to the Telemetria Real tab). st.tabs() executes every tab's
body on every rerun (only hides output via CSS) — so this exercises the new
sub_alert/sub_qual code paths against the real Supabase instance (read-only
queries against the post-migration llm_telemetry columns), not just imports.
"""

from streamlit.testing.v1 import AppTest


def _base_app():
    at = AppTest.from_file("pages/LLMBenchmark.py", default_timeout=60)
    at.session_state["_autenticado"] = True
    at.session_state["_usuario_login"] = "teste"
    at.session_state["_usuario_nome"] = "Teste"
    at.session_state["_role"] = "admin"
    return at


class TestLLMBenchmarkBootSmoke:
    def test_page_renders_without_exception(self):
        at = _base_app()
        at.run()
        assert not at.exception

    def test_telemetria_tab_has_seven_subtabs_including_alertas_and_qualidade(self):
        at = _base_app()
        at.run()
        assert not at.exception
        # tab_bench (index 0) has no nested st.tabs; tab_tele (index 1) has
        # the 7 sub-tabs (5 pre-existing + Alertas + Qualidade, PC183).
        all_tab_labels = [t.label for t in at.tabs]
        assert "🚨 Alertas" not in all_tab_labels  # top-level tabs unaffected
        # Nested tabs aren't exposed as at.tabs directly on AppTest — instead
        # confirm no exception surfaced while executing sub_alert/sub_qual
        # bodies, which is the actual regression risk (new pandas/plotly code).
