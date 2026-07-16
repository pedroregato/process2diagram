"""
Tests for PC189 — evaluation of melhorias/proposta-assistente-20261607.md.

Covers the 2 implemented items:
  #1 — tools_used_digest (cross-turn "already called" hint, name-only)
  #4 — automatic embedding on save (Pipeline.py) is not unit-tested here
       directly (inline script logic, fail-open try/except) — covered by
       manual review + boot-smoke instead.
"""
from __future__ import annotations

from unittest.mock import patch

from pages.Assistente import _build_tools_used_digest, _TOOLS_USED_DIGEST_MAX
from agents.agent_assistant import AgentAssistant


class TestBuildToolsUsedDigest:
    def test_empty_history_returns_empty_string(self):
        assert _build_tools_used_digest([]) == ""

    def test_messages_without_tools_used_returns_empty_string(self):
        history = [{"role": "user", "content": "oi"}, {"role": "assistant", "content": "olá"}]
        assert _build_tools_used_digest(history) == ""

    def test_deduplicates_across_messages_preserving_first_seen_order(self):
        history = [
            {"role": "assistant", "content": "a1", "tools_used": ["get_meeting_list", "count_artifacts"]},
            {"role": "assistant", "content": "a2", "tools_used": ["count_artifacts", "get_meeting_decisions"]},
        ]
        assert _build_tools_used_digest(history) == "get_meeting_list, count_artifacts, get_meeting_decisions"

    def test_caps_to_max_length_keeping_most_recent(self):
        history = [
            {"role": "assistant", "content": f"a{i}", "tools_used": [f"tool_{i}"]}
            for i in range(_TOOLS_USED_DIGEST_MAX + 10)
        ]
        digest = _build_tools_used_digest(history)
        names = digest.split(", ")
        assert len(names) == _TOOLS_USED_DIGEST_MAX
        # keeps the LAST N distinct names seen, not the first N
        assert names[-1] == f"tool_{_TOOLS_USED_DIGEST_MAX + 9}"


class TestSystemPromptToolsDigestInjection:
    def _build(self, digest: str = "") -> str:
        agent = AgentAssistant(
            {"api_key": "fake"},
            {"client_type": "openai_compatible", "default_model": "x", "base_url": "y"},
        )
        with patch.object(agent, "_load_skill", return_value="(guia)"), patch(
            "core.project_store.retrieve_data_summary",
            return_value={
                "meetings": [], "req_total": 0,
                "n_sbvr_terms": 0, "n_sbvr_rules": 0, "bpmn_processes": [],
            },
        ):
            return agent._build_system_prompt_tools("Projeto X", "pid-1", digest)

    def test_no_digest_omits_marker_block(self):
        prompt = self._build("")
        assert "FERRAMENTAS JÁ CHAMADAS" not in prompt

    def test_digest_present_appends_marker_and_names(self):
        prompt = self._build("get_meeting_list, count_artifacts")
        assert "FERRAMENTAS JÁ CHAMADAS" in prompt
        assert "get_meeting_list, count_artifacts" in prompt

    def test_digest_does_not_break_existing_template_substitutions(self):
        # Guards against reintroducing the .format()-vs-dict-literal bug this
        # file already works around (see comment near _SYSTEM_TOOLS_TEMPLATE).
        prompt = self._build("some_tool")
        assert "{p2d_guide}" not in prompt
        assert "{project_name}" not in prompt
        assert "{data_summary}" not in prompt
        assert "Projeto X" in prompt
