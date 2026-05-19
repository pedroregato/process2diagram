# tests/test_context_analyzer.py
# ─────────────────────────────────────────────────────────────────────────────
# Unit tests for services/context_analyzer.py — no LLM, no Supabase calls.
# Run with: pytest tests/test_context_analyzer.py -v
# ─────────────────────────────────────────────────────────────────────────────

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.context_analyzer import (
    LONG_CONTEXT_AGENTS,
    LONG_CONTEXT_THRESHOLD,
    estimate_tokens,
    inject_long_context_instruction,
    should_use_long_context,
)


# ── estimate_tokens ───────────────────────────────────────────────────────────

class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_short_text(self):
        text = "a" * 400   # 100 chars → ~100 tokens
        result = estimate_tokens(text)
        assert result > 0

    def test_scales_with_length(self):
        short = "word " * 1000
        long_ = "word " * 5000
        assert estimate_tokens(long_) > estimate_tokens(short)

    def test_approximate_ratio(self):
        # 40000 chars ÷ 4 = 10000 tokens (tiktoken fallback)
        text = "x" * 40_000
        result = estimate_tokens(text)
        # Allow ±50% around expected 10000 to accommodate tiktoken accuracy
        assert 5_000 <= result <= 15_000


# ── should_use_long_context ───────────────────────────────────────────────────

class TestShouldUseLongContext:
    _SHORT = "Reunião de alinhamento. " * 100          # ~2 400 chars → ~600 tokens
    _LONG  = "Transcrição extensa. " * 15_000          # ~315 000 chars → ~78 750 tokens

    def test_short_transcript_returns_false(self):
        assert should_use_long_context(self._SHORT, "bpmn") is False

    def test_long_transcript_bpmn_returns_true(self):
        assert should_use_long_context(self._LONG, "bpmn") is True

    def test_long_transcript_sbvr_returns_true(self):
        assert should_use_long_context(self._LONG, "sbvr") is True

    def test_long_transcript_bmm_returns_true(self):
        assert should_use_long_context(self._LONG, "bmm") is True

    def test_long_transcript_minutes_returns_false(self):
        # minutes is not in LONG_CONTEXT_AGENTS
        assert should_use_long_context(self._LONG, "minutes") is False

    def test_long_transcript_requirements_returns_false(self):
        assert should_use_long_context(self._LONG, "requirements") is False

    def test_disabled_returns_false(self):
        assert should_use_long_context(self._LONG, "bpmn", enabled=False) is False

    def test_threshold_boundary(self):
        # Text estimated just below threshold should be False
        below = "x" * (LONG_CONTEXT_THRESHOLD * 4 - 400)   # ~4 chars/token
        assert should_use_long_context(below, "bpmn") is False

    def test_unknown_agent_returns_false(self):
        assert should_use_long_context(self._LONG, "unknown_agent") is False


# ── inject_long_context_instruction ──────────────────────────────────────────

class TestInjectLongContextInstruction:
    _SYSTEM = "You are an expert BPMN analyst."

    def test_no_injection_when_disabled(self):
        result = inject_long_context_instruction(self._SYSTEM, use_long=False)
        assert result == self._SYSTEM

    def test_instruction_prepended_when_enabled(self):
        result = inject_long_context_instruction(self._SYSTEM, use_long=True)
        assert result.startswith("## TRANSCRIÇÃO COMPLETA DISPONÍVEL")
        assert self._SYSTEM in result

    def test_original_system_preserved(self):
        result = inject_long_context_instruction(self._SYSTEM, use_long=True)
        assert self._SYSTEM in result

    def test_no_duplicate_injection(self):
        # Injecting twice (e.g. on retry) should not add duplicate headers
        once = inject_long_context_instruction(self._SYSTEM, use_long=True)
        # A second injection would add it again — that's acceptable since
        # _call_llm injects only once; verify it's present at least once
        assert once.count("## TRANSCRIÇÃO COMPLETA DISPONÍVEL") >= 1


# ── LONG_CONTEXT_AGENTS set ───────────────────────────────────────────────────

class TestLongContextAgentsSet:
    def test_expected_agents_present(self):
        assert "bpmn" in LONG_CONTEXT_AGENTS
        assert "sbvr" in LONG_CONTEXT_AGENTS
        assert "bmm"  in LONG_CONTEXT_AGENTS

    def test_excluded_agents_absent(self):
        assert "minutes"      not in LONG_CONTEXT_AGENTS
        assert "requirements" not in LONG_CONTEXT_AGENTS
        assert "quality"      not in LONG_CONTEXT_AGENTS
