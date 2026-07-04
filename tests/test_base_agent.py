# tests/test_base_agent.py
"""
Tests for agents/base_agent.py — the finish_reason='length' retry escalation
(PC118-D). No real LLM calls: _call_openai is mocked to simulate a truncated
completion on the first attempt and a valid one on the second.
"""

from unittest.mock import patch

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
