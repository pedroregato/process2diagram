# tests/test_base_agent_azure_openai.py
"""
Azure OpenAI Service as a new LLM provider (client_type="azure_openai").
Architecture is provider-agnostic (modules/config.py::AVAILABLE_PROVIDERS +
routing in BaseAgent._call_llm); this adds Azure's own SDK client (endpoint +
api_version instead of base_url) while reusing the shared chat-completions
logic (_run_openai_chat) that _call_openai already relies on.

No real network calls — openai.AzureOpenAI is mocked throughout.
"""

from unittest.mock import patch, MagicMock

import pytest

from agents.base_agent import BaseAgent
from core.knowledge_hub import KnowledgeHub
from modules.config import AVAILABLE_PROVIDERS

_AZURE_PROVIDER_CFG = AVAILABLE_PROVIDERS["Azure OpenAI"]


class _DummyAgent(BaseAgent):
    name = "dummy"
    skill_path = ""

    def run(self, hub):
        return hub

    def build_prompt(self, hub):
        return "system", "user"


def _make_fake_openai_response(finish_reason, content):
    resp = MagicMock()
    choice = MagicMock()
    choice.finish_reason = finish_reason
    choice.message.content = content
    resp.choices = [choice]
    resp.usage.prompt_tokens = 100
    resp.usage.completion_tokens = 50
    return resp


class TestProviderRegistration:
    def test_azure_openai_is_registered(self):
        assert "Azure OpenAI" in AVAILABLE_PROVIDERS

    def test_client_type_is_azure_openai(self):
        assert _AZURE_PROVIDER_CFG["client_type"] == "azure_openai"

    def test_has_endpoint_extra_field(self):
        keys = [f["key"] for f in _AZURE_PROVIDER_CFG["extra_fields"]]
        assert "azure_endpoint" in keys
        assert "deployment_name" in keys


class TestCallAzureOpenAI:
    _CLIENT_INFO = {"api_key": "fake", "azure_endpoint": "https://fake.openai.azure.com"}

    def test_raises_without_endpoint_configured(self):
        agent = _DummyAgent({"api_key": "fake"}, _AZURE_PROVIDER_CFG)
        with pytest.raises(ValueError, match="endpoint"):
            agent._call_azure_openai("system", "user", "fake-key", "gpt-4o-mini")

    def test_builds_azure_client_with_endpoint_and_api_version(self):
        agent = _DummyAgent(self._CLIENT_INFO, _AZURE_PROVIDER_CFG)
        fake_resp = _make_fake_openai_response("stop", '{"ok": true}')

        with patch("openai.AzureOpenAI") as MockAzure:
            MockAzure.return_value.chat.completions.create.return_value = fake_resp
            content, tin, tout = agent._call_azure_openai(
                "system", "user", "fake-key", "gpt-4o-mini"
            )

        MockAzure.assert_called_once_with(
            api_key="fake-key",
            azure_endpoint="https://fake.openai.azure.com",
            api_version="2024-10-21",
        )
        assert content == '{"ok": true}'
        assert (tin, tout) == (100, 50)

    def test_deployment_override_replaces_model_in_the_call(self):
        client_info = dict(self._CLIENT_INFO, azure_deployment="my-prod-deployment")
        agent = _DummyAgent(client_info, _AZURE_PROVIDER_CFG)
        fake_resp = _make_fake_openai_response("stop", '{"ok": true}')

        with patch("openai.AzureOpenAI") as MockAzure:
            MockAzure.return_value.chat.completions.create.return_value = fake_resp
            agent._call_azure_openai("system", "user", "fake-key", "gpt-4o-mini")

        call_kwargs = MockAzure.return_value.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "my-prod-deployment"

    def test_raises_on_length_finish_reason_same_as_openai(self):
        # Reuses _run_openai_chat — same truncation-safety contract as the
        # plain OpenAI path (finish_reason='length' must raise, not silently
        # return truncated JSON).
        agent = _DummyAgent(self._CLIENT_INFO, _AZURE_PROVIDER_CFG)
        fake_resp = _make_fake_openai_response("length", '{"steps": [')

        with patch("openai.AzureOpenAI") as MockAzure:
            MockAzure.return_value.chat.completions.create.return_value = fake_resp
            with pytest.raises(ValueError, match="finish_reason='length'"):
                agent._call_azure_openai("system", "user", "fake-key", "gpt-4o-mini")

    def test_falls_back_to_session_security_extra_field_when_client_info_empty(self):
        agent = _DummyAgent({"api_key": "fake"}, _AZURE_PROVIDER_CFG)
        fake_resp = _make_fake_openai_response("stop", '{"ok": true}')

        with patch("modules.session_security.get_extra_field") as mock_get_field, \
             patch("openai.AzureOpenAI") as MockAzure:
            mock_get_field.side_effect = lambda provider, key: {
                "azure_endpoint": "https://from-settings.openai.azure.com",
                "deployment_name": "",
            }[key]
            MockAzure.return_value.chat.completions.create.return_value = fake_resp
            agent._call_azure_openai("system", "user", "fake-key", "gpt-4o-mini")

        MockAzure.assert_called_once_with(
            api_key="fake-key",
            azure_endpoint="https://from-settings.openai.azure.com",
            api_version="2024-10-21",
        )


class TestCallLlmRoutesToAzure:
    def test_call_llm_dispatches_azure_client_type(self):
        client_info = {
            "api_key": "fake",
            "azure_endpoint": "https://fake.openai.azure.com",
            "enable_long_context": False,
        }
        agent = _DummyAgent(client_info, _AZURE_PROVIDER_CFG)
        hub = KnowledgeHub.new()

        with patch.object(
            BaseAgent, "_call_azure_openai",
            return_value=('{"ok": true}', 100, 50),
        ) as mock_azure_call, \
             patch("services.llm_telemetry._telemetry"):
            raw = agent._call_llm("system", "user", hub, skip_cache=True)

        assert raw == '{"ok": true}'
        assert mock_azure_call.called

    def test_unknown_client_type_still_raises(self):
        bogus_cfg = dict(_AZURE_PROVIDER_CFG, client_type="something_else")
        agent = _DummyAgent({"api_key": "fake"}, bogus_cfg)
        hub = KnowledgeHub.new()

        with patch("services.llm_telemetry._telemetry"), \
             pytest.raises(ValueError, match="Unknown client_type"):
            agent._call_llm("system", "user", hub, skip_cache=True)
