# tests/test_assistente_html_export.py
"""
Regression test for a production crash: exporting the Assistente chat to
HTML raised TypeError: Object of type datetime is not JSON serializable
and took down the whole page (uncaught at module top level, not just the
chart), because pages/Assistente.py::_export_chat_to_html() serialized
each chart dict with the plain stdlib json.dumps() instead of Plotly's
own encoder.

Root cause: generate_gantt_chart() (core/tools/tools_admin_charts_entities.py)
stores raw datetime.datetime objects in each bar trace's `base` field —
valid Plotly figure data, but not JSON-serializable by the stdlib encoder.
Any chart tool that stores datetime/numpy/pandas values in its figure dict
would trigger the same crash.

Fix: json.dumps(chart_dict, cls=plotly.utils.PlotlyJSONEncoder), wrapped in
try/except so a single still-unserializable chart is skipped instead of
crashing the whole export.
"""

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import importlib

from core.assistant_tools import AssistantToolExecutor

_LLM_CONFIG = {
    "api_key": "fake-key",
    "model": "fake-model",
    "provider_cfg": {"client_type": "openai_compatible", "default_model": "fake-model"},
}


def _assistente_module():
    return importlib.import_module("pages.Assistente")


def _executor():
    return AssistantToolExecutor("proj-1", llm_config=_LLM_CONFIG)


class TestExportChatToHtmlWithDatetimeChart:
    """Exact production repro: a Gantt chart (raw datetime objects in
    trace data) attached to an assistant message."""

    def test_gantt_chart_export_does_not_raise(self):
        mod = _assistente_module()
        ex = _executor()
        ex.generate_gantt_chart(
            title="Cronograma",
            phases=[{"name": "Fase 1", "start": "2026-01-01", "end": "2026-02-01"}],
        )
        fig_dict = ex._pending_charts[0]

        history = [
            {"role": "user", "content": "mostre o cronograma"},
            {"role": "assistant", "content": "aqui está", "charts": [fig_dict],
             "tools_used": ["generate_gantt_chart"]},
        ]
        html = mod._export_chat_to_html(history, "Projeto Teste", "DeepSeek")
        assert "Plotly.newPlot" in html
        assert "Fase 1" not in html or True  # presence not required; just must not raise

    def test_gantt_chart_json_embedded_is_valid(self):
        import json
        mod = _assistente_module()
        ex = _executor()
        ex.generate_gantt_chart(
            title="Cronograma",
            phases=[{"name": "Fase 1", "start": "2026-01-01", "end": "2026-02-01"}],
        )
        fig_dict = ex._pending_charts[0]
        history = [
            {"role": "assistant", "content": "ok", "charts": [fig_dict], "tools_used": []},
        ]
        html = mod._export_chat_to_html(history, "Projeto Teste", "DeepSeek")
        start = html.index("var spec = ") + len("var spec = ")
        end = html.index(";\n", start)
        embedded = html[start:end]
        parsed = json.loads(embedded)  # must not raise — proves valid JSON was embedded
        assert "data" in parsed


class TestExportChatToHtmlResilience:
    def test_unserializable_chart_is_skipped_not_fatal(self):
        """A chart dict containing a genuinely unserializable object must be
        skipped (no chart script emitted for it) rather than crashing the
        whole export for every other message."""
        mod = _assistente_module()

        class _Unserializable:
            pass

        bad_chart = {"data": [{"x": [_Unserializable()]}], "layout": {}}
        history = [
            {"role": "assistant", "content": "resposta", "charts": [bad_chart], "tools_used": []},
        ]
        html = mod._export_chat_to_html(history, "Projeto Teste", "DeepSeek")
        assert "resposta" in html
        assert "Plotly.newPlot" not in html

    def test_normal_chart_still_exports_fine(self):
        mod = _assistente_module()
        ex = _executor()
        ex.generate_custom_chart(chart_type="bar", title="T", labels=["a", "b"], values=[1, 2])
        fig_dict = ex._pending_charts[0]
        history = [
            {"role": "assistant", "content": "ok", "charts": [fig_dict], "tools_used": []},
        ]
        html = mod._export_chat_to_html(history, "Projeto Teste", "DeepSeek")
        assert "Plotly.newPlot" in html
