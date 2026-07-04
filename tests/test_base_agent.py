# tests/test_base_agent.py
"""
Tests for agents/base_agent.py — the finish_reason='length' retry escalation
(PC118-D). No real LLM calls: _call_openai is mocked to simulate a truncated
completion on the first attempt and a valid one on the second.
"""

from unittest.mock import patch, MagicMock

from agents.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub

_CLIENT_INFO = {"api_key": "fake", "enable_long_context": True}
_PROVIDER_CFG = {
    "client_type": "openai_compatible",
    "default_model": "fake-model",
    "max_tokens": 8192,
    "long_context_max_tokens": 32768,
}


class _DummyAgent(BaseAgent):
    name = "dummy"
    skill_path = ""

    def run(self, hub):
        return hub

    def build_prompt(self, hub):
        return "system", "user"


class TestLengthTruncationEscalation:
    def test_retry_after_length_truncation_escalates_to_long_context(self):
        agent = _DummyAgent(_CLIENT_INFO, _PROVIDER_CFG)
        hub = KnowledgeHub.new()

        calls = []

        def _fake_call_openai(self, system, user, api_key, model, timeout=60, long_context=False):
            calls.append(long_context)
            if len(calls) == 1:
                # Mirrors the real _call_openai's own raise on empty content
                raise ValueError(
                    "[dummy] LLM retornou conteúdo vazio "
                    "(finish_reason='length', model='fake-model')."
                )
            return '{"ok": true}', 100, 200

        with patch.object(BaseAgent, "_call_openai", _fake_call_openai):
            data = agent._call_with_retry("system", "user", hub)

        assert data == {"ok": True}
        assert calls == [False, True]  # 2nd attempt escalated to long_context

    def test_force_long_context_not_set_for_other_parse_errors(self):
        agent = _DummyAgent(_CLIENT_INFO, _PROVIDER_CFG)
        hub = KnowledgeHub.new()

        calls = []

        def _fake_call_openai(self, system, user, api_key, model, timeout=60, long_context=False):
            calls.append(long_context)
            if len(calls) == 1:
                return "not json at all, no braces", 100, 50
            return '{"ok": true}', 100, 200

        with patch.object(BaseAgent, "_call_openai", _fake_call_openai):
            agent._call_with_retry("system", "user", hub)

        # A malformed (non-truncated) response must NOT force long-context —
        # only a finish_reason='length' failure should trigger the escalation.
        assert calls == [False, False]

    def test_nonempty_truncated_content_still_escalates(self):
        # PC118-E: telemetry showed calls repeatedly maxing out output_tokens
        # with NON-empty content (silently "fixed" by json_repair, missing
        # whole sections) — the old empty-content-only check never saw this
        # as a failure, so escalation never triggered. Confirm the retry loop
        # still escalates when the raised message uses the new non-empty
        # truncation wording (mirrors what _call_openai now raises).
        agent = _DummyAgent(_CLIENT_INFO, _PROVIDER_CFG)
        hub = KnowledgeHub.new()

        calls = []

        def _fake_call_openai(self, system, user, api_key, model, timeout=60, long_context=False):
            calls.append(long_context)
            if len(calls) == 1:
                raise ValueError(
                    "[dummy] LLM truncou a resposta antes de completar "
                    "(finish_reason='length', model='fake-model', output_tokens=8192)."
                )
            return '{"ok": true}', 100, 200

        with patch.object(BaseAgent, "_call_openai", _fake_call_openai):
            data = agent._call_with_retry("system", "user", hub)

        assert data == {"ok": True}
        assert calls == [False, True]

    def test_all_attempts_truncated_raises_after_max_retries(self):
        agent = _DummyAgent(_CLIENT_INFO, _PROVIDER_CFG)
        hub = KnowledgeHub.new()

        def _always_truncated(self, system, user, api_key, model, timeout=60, long_context=False):
            raise ValueError(
                "[dummy] LLM retornou conteúdo vazio "
                "(finish_reason='length', model='fake-model')."
            )

        with patch.object(BaseAgent, "_call_openai", _always_truncated):
            try:
                agent._call_with_retry("system", "user", hub)
                assert False, "expected RuntimeError"
            except RuntimeError as exc:
                assert "Failed after" in str(exc)


def _make_fake_openai_response(finish_reason, content):
    resp = MagicMock()
    choice = MagicMock()
    choice.finish_reason = finish_reason
    choice.message.content = content
    resp.choices = [choice]
    resp.usage.prompt_tokens = 100
    resp.usage.completion_tokens = 8192
    return resp


class TestCallOpenAINonEmptyTruncation:
    """Unit tests for the real _call_openai() — PC118-E: a finish_reason=
    'length' response must raise even when content is non-empty."""

    def test_raises_on_length_with_nonempty_content(self):
        agent = _DummyAgent(_CLIENT_INFO, _PROVIDER_CFG)
        fake_resp = _make_fake_openai_response("length", '{"steps": [')  # truncated mid-array

        with patch("openai.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.return_value = fake_resp
            try:
                agent._call_openai("system", "user", "fake-key", "fake-model")
                assert False, "expected ValueError"
            except ValueError as exc:
                assert "finish_reason='length'" in str(exc)

    def test_does_not_raise_on_normal_stop(self):
        agent = _DummyAgent(_CLIENT_INFO, _PROVIDER_CFG)
        fake_resp = _make_fake_openai_response("stop", '{"ok": true}')

        with patch("openai.OpenAI") as MockOpenAI:
            MockOpenAI.return_value.chat.completions.create.return_value = fake_resp
            content, tin, tout = agent._call_openai("system", "user", "fake-key", "fake-model")

        assert content == '{"ok": true}'


class TestCallAnthropicNonEmptyTruncation:
    """Same check for the Anthropic path — stop_reason='max_tokens' is the
    Claude equivalent of OpenAI's finish_reason='length'."""

    def test_raises_on_max_tokens_stop_reason(self):
        agent = _DummyAgent(_CLIENT_INFO, _PROVIDER_CFG)
        fake_msg = MagicMock()
        fake_msg.stop_reason = "max_tokens"
        fake_msg.content = [MagicMock(text='{"steps": [')]
        fake_msg.usage.input_tokens = 100
        fake_msg.usage.output_tokens = 8192

        with patch("anthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value.messages.create.return_value = fake_msg
            try:
                agent._call_anthropic("system", "user", "fake-key", "fake-model")
                assert False, "expected ValueError"
            except ValueError as exc:
                assert "finish_reason='length'" in str(exc)

    def test_does_not_raise_on_normal_end_turn(self):
        agent = _DummyAgent(_CLIENT_INFO, _PROVIDER_CFG)
        fake_msg = MagicMock()
        fake_msg.stop_reason = "end_turn"
        fake_msg.content = [MagicMock(text='{"ok": true}')]
        fake_msg.usage.input_tokens = 100
        fake_msg.usage.output_tokens = 200

        with patch("anthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value.messages.create.return_value = fake_msg
            content, tin, tout = agent._call_anthropic("system", "user", "fake-key", "fake-model")

        assert content == '{"ok": true}'
