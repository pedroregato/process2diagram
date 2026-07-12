# tests/test_base_agent_telemetry.py
"""
PC183 — two additions to base_agent.py's telemetry instrumentation:
  1) A failed LLM call now records a TelemetryRecord(is_error=True) before
     re-raising (previously: zero telemetry trace for failures at all).
  2) The output_schema.model_validate() outcome (PC84) is now persisted via
     LLMTelemetry.record_validation() instead of only warnings.warn().
Both are verified here without any real network/Supabase call — the
telemetry singleton's record()/record_validation() methods are mocked.
"""

from unittest.mock import patch, MagicMock

import pydantic
import pytest

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


class _StrictSchema(pydantic.BaseModel):
    required_field: str


class TestErrorPathTelemetry:
    def test_failed_call_records_is_error_true_then_reraises(self):
        agent = _DummyAgent(_CLIENT_INFO, _PROVIDER_CFG)
        hub = KnowledgeHub.new()

        def _always_fails(self, system, user, api_key, model, timeout=60, long_context=False):
            raise ValueError("[dummy] LLM retornou conteúdo vazio (finish_reason=None, model='fake-model').")

        with patch.object(BaseAgent, "_call_openai", _always_fails), \
             patch("services.llm_telemetry._telemetry") as mock_telemetry:
            with pytest.raises(ValueError):
                agent._call_llm("system", "user", hub)

        assert mock_telemetry.record.called
        recorded = mock_telemetry.record.call_args[0][0]
        assert recorded.is_error is True
        assert recorded.agent_name == "dummy"
        assert "conteúdo vazio" in recorded.error_message

    def test_successful_call_records_is_error_false(self):
        agent = _DummyAgent(_CLIENT_INFO, _PROVIDER_CFG)
        hub = KnowledgeHub.new()

        def _ok(self, system, user, api_key, model, timeout=60, long_context=False):
            return '{"ok": true}', 100, 50

        with patch.object(BaseAgent, "_call_openai", _ok), \
             patch("services.llm_telemetry._telemetry") as mock_telemetry:
            agent._call_llm("system", "user", hub)

        assert mock_telemetry.record.called
        recorded = mock_telemetry.record.call_args[0][0]
        assert recorded.is_error is False

    def test_telemetry_failure_never_blocks_the_exception_propagation(self):
        # Fail-open: even if the telemetry write itself blows up, the original
        # LLM error must still propagate unchanged (never swallowed).
        agent = _DummyAgent(_CLIENT_INFO, _PROVIDER_CFG)
        hub = KnowledgeHub.new()

        def _always_fails(self, system, user, api_key, model, timeout=60, long_context=False):
            raise ValueError("boom")

        with patch.object(BaseAgent, "_call_openai", _always_fails), \
             patch("services.llm_telemetry._telemetry") as mock_telemetry:
            mock_telemetry.record.side_effect = Exception("supabase down")
            with pytest.raises(ValueError, match="boom"):
                agent._call_llm("system", "user", hub)

    def test_retry_loop_still_escalates_after_error_telemetry_added(self):
        # Regression guard: the new try/except around the provider call must
        # not change _call_with_retry's existing retry/escalation behavior.
        agent = _DummyAgent(_CLIENT_INFO, _PROVIDER_CFG)
        hub = KnowledgeHub.new()

        calls = []

        def _fake_call_openai(self, system, user, api_key, model, timeout=60, long_context=False):
            calls.append(long_context)
            if len(calls) == 1:
                raise ValueError(
                    "[dummy] LLM retornou conteúdo vazio "
                    "(finish_reason='length', model='fake-model')."
                )
            return '{"ok": true}', 100, 200

        with patch.object(BaseAgent, "_call_openai", _fake_call_openai), \
             patch("agents.base_agent.time.sleep"):
            data = agent._call_with_retry("system", "user", hub)

        assert data == {"ok": True}
        assert calls == [False, True]


class TestSchemaValidationTelemetry:
    def test_valid_output_records_schema_valid_true(self):
        agent = _DummyAgent(_CLIENT_INFO, _PROVIDER_CFG)
        agent.output_schema = _StrictSchema
        hub = KnowledgeHub.new()

        def _ok(self, system, user, api_key, model, timeout=60, long_context=False):
            return '{"required_field": "present"}', 100, 50

        with patch.object(BaseAgent, "_call_openai", _ok), \
             patch("services.llm_telemetry._telemetry") as mock_telemetry:
            agent._call_with_retry("system", "user", hub)

        assert mock_telemetry.record_validation.called
        args = mock_telemetry.record_validation.call_args[0]
        assert args[0] == "dummy"
        assert args[2] is True

    def test_invalid_output_records_schema_valid_false_but_does_not_raise(self):
        agent = _DummyAgent(_CLIENT_INFO, _PROVIDER_CFG)
        agent.output_schema = _StrictSchema
        hub = KnowledgeHub.new()

        def _missing_field(self, system, user, api_key, model, timeout=60, long_context=False):
            return '{"unrelated": "value"}', 100, 50

        with patch.object(BaseAgent, "_call_openai", _missing_field), \
             patch("services.llm_telemetry._telemetry") as mock_telemetry, \
             pytest.warns(UserWarning):
            data = agent._call_with_retry("system", "user", hub)

        # Fail-open (PC84): pipeline is never blocked by a schema mismatch.
        assert data == {"unrelated": "value"}
        assert mock_telemetry.record_validation.called
        args = mock_telemetry.record_validation.call_args[0]
        assert args[2] is False

    def test_no_output_schema_never_calls_record_validation(self):
        agent = _DummyAgent(_CLIENT_INFO, _PROVIDER_CFG)
        assert getattr(agent, "output_schema", None) is None
        hub = KnowledgeHub.new()

        def _ok(self, system, user, api_key, model, timeout=60, long_context=False):
            return '{"anything": true}', 100, 50

        with patch.object(BaseAgent, "_call_openai", _ok), \
             patch("services.llm_telemetry._telemetry") as mock_telemetry:
            agent._call_with_retry("system", "user", hub)

        mock_telemetry.record_validation.assert_not_called()
