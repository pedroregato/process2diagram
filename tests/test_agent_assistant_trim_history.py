# tests/test_agent_assistant_trim_history.py
"""
Regression test for a production crash: asking the Assistente a plain
question ("O que precisa ser feito para que tenhamos um cronograma do
projeto?") with no chart request at all failed with:
"Erro ao gerar resposta: Object of type datetime is not JSON serializable"
— on BOTH the tool-use path and its keyword-search fallback.

Root cause: pages/Assistente.py stores full message dicts in
st.session_state["assistant_history"], including UI-only keys ("charts",
"tools_used", "tables", "widgets") attached to prior assistant turns —
e.g. a Plotly Gantt chart figure (which embeds raw datetime.datetime
objects in its trace data, see PC146) generated earlier in the SAME
conversation. agents/agent_assistant.py::_trim_history() forwarded these
dicts unchanged (aside from re-spreading them when truncating content),
so the "charts" key rode along into the `messages` list passed straight
to `client.chat.completions.create(messages=...)` in both chat() and
chat_with_tools() (see _call_chat_openai / the tool-use round loop). The
OpenAI/Anthropic SDKs don't strip unknown keys before serializing the
request body, so the previously-generated Gantt chart's raw datetime
values crashed the encoder on the *next*, unrelated question.

Fix: _trim_history() now always rebuilds a clean {"role", "content"}
dict, discarding any extra keys regardless of whether truncation kicks in.
"""

import json
from datetime import datetime

from agents.agent_assistant import _trim_history
from core.assistant_tools import AssistantToolExecutor

_LLM_CONFIG = {
    "api_key": "fake-key",
    "model": "fake-model",
    "provider_cfg": {"client_type": "openai_compatible", "default_model": "fake-model"},
}


def _gantt_chart_dict() -> dict:
    ex = AssistantToolExecutor("proj-1", llm_config=_LLM_CONFIG)
    ex.generate_gantt_chart(
        title="Cronograma",
        phases=[{"name": "Fase 1", "start": "2026-01-01", "end": "2026-02-01"}],
    )
    return ex._pending_charts[0]


class TestTrimHistoryStripsUiOnlyKeys:
    def test_charts_key_is_dropped(self):
        history = [
            {"role": "user", "content": "mostre o cronograma"},
            {"role": "assistant", "content": "aqui está", "charts": [_gantt_chart_dict()],
             "tools_used": ["generate_gantt_chart"]},
        ]
        trimmed = _trim_history(history)
        assert all(set(m.keys()) == {"role", "content"} for m in trimmed)

    def test_tables_and_widgets_keys_are_dropped(self):
        history = [
            {"role": "assistant", "content": "ok", "tables": [{"title": "t"}],
             "widgets": [{"type": "bpmn"}]},
        ]
        trimmed = _trim_history(history)
        assert trimmed == [{"role": "assistant", "content": "ok"}]

    def test_content_and_role_preserved(self):
        history = [{"role": "user", "content": "olá"}, {"role": "assistant", "content": "oi"}]
        assert _trim_history(history) == history

    def test_truncation_still_works_and_still_strips_extra_keys(self):
        long_content = "x" * 5000
        history = [{"role": "assistant", "content": long_content, "charts": [{"data": [datetime.now()]}]}]
        trimmed = _trim_history(history)
        assert len(trimmed) == 1
        assert "charts" not in trimmed[0]
        assert trimmed[0]["content"].endswith("[… truncado]")
        assert len(trimmed[0]["content"]) < len(long_content)


class TestTrimHistoryOutputIsJsonSerializable:
    """The exact production repro: a Gantt chart (raw datetime in trace
    data) attached to a PRIOR assistant turn must never break the JSON
    encoding of the NEXT LLM request — regardless of what that next
    question is about."""

    def test_history_with_prior_gantt_chart_is_json_serializable(self):
        history = [
            {"role": "user", "content": "mostre o cronograma"},
            {"role": "assistant", "content": "aqui está o cronograma", "charts": [_gantt_chart_dict()]},
        ]
        trimmed = _trim_history(history)
        messages = trimmed + [{"role": "user", "content": "O que precisa ser feito para termos um cronograma?"}]
        full_messages = [{"role": "system", "content": "system prompt"}] + messages
        json.dumps(full_messages)  # must not raise — this is what the OpenAI SDK does internally
