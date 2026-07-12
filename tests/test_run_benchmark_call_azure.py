# tests/test_run_benchmark_call_azure.py
"""
run_benchmark_call() Azure OpenAI branch — the On-Demand Benchmark tab in
pages/LLMBenchmark.py routes through this function, separate from
BaseAgent._call_llm's routing (no hub/cache/PII in this path). No real
network calls — openai.AzureOpenAI is mocked.
"""

from unittest.mock import patch, MagicMock

from services.llm_telemetry import run_benchmark_call
from modules.config import AVAILABLE_PROVIDERS

_AZURE_CFG = AVAILABLE_PROVIDERS["Azure OpenAI"]


def _fake_response():
    resp = MagicMock()
    resp.usage.prompt_tokens = 80
    resp.usage.completion_tokens = 40
    return resp


class TestRunBenchmarkCallAzure:
    def test_returns_error_when_endpoint_not_configured(self):
        with patch("modules.session_security.get_extra_field", return_value=""):
            latency, inp, out, error = run_benchmark_call(
                "Azure OpenAI", _AZURE_CFG, "fake-key", "system", "user"
            )
        assert error is not None
        assert "endpoint" in error.lower()
        assert (inp, out) == (0, 0)

    def test_success_with_endpoint_configured(self):
        def _fake_get_field(provider, key):
            return {"azure_endpoint": "https://fake.openai.azure.com",
                     "deployment_name": ""}[key]

        with patch("modules.session_security.get_extra_field", side_effect=_fake_get_field), \
             patch("openai.AzureOpenAI") as MockAzure:
            MockAzure.return_value.chat.completions.create.return_value = _fake_response()
            latency, inp, out, error = run_benchmark_call(
                "Azure OpenAI", _AZURE_CFG, "fake-key", "system", "user"
            )

        assert error is None
        assert (inp, out) == (80, 40)
        MockAzure.assert_called_once_with(
            api_key="fake-key",
            azure_endpoint="https://fake.openai.azure.com",
            api_version="2024-10-21",
        )

    def test_deployment_override_used_as_model(self):
        def _fake_get_field(provider, key):
            return {"azure_endpoint": "https://fake.openai.azure.com",
                     "deployment_name": "my-deployment"}[key]

        with patch("modules.session_security.get_extra_field", side_effect=_fake_get_field), \
             patch("openai.AzureOpenAI") as MockAzure:
            MockAzure.return_value.chat.completions.create.return_value = _fake_response()
            run_benchmark_call("Azure OpenAI", _AZURE_CFG, "fake-key", "system", "user")

        call_kwargs = MockAzure.return_value.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "my-deployment"
