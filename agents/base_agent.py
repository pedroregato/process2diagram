# agents/base_agent.py
# ─────────────────────────────────────────────────────────────────────────────
# Abstract base class for all specialist agents.
#
# Contract every agent must fulfill:
#   - skill_path:  path to its SKILL.md file (loaded once at init)
#   - run(hub):    receives KnowledgeHub, writes its section, returns hub
#
# Infrastructure provided here (agents never duplicate this):
#   - _call_llm()      → provider-agnostic LLM call (OpenAI-compat + Anthropic)
#   - _parse_json()    → robust JSON extraction from raw LLM output
#   - _load_skill()    → reads SKILL.md and exposes it for system prompt injection
#   - retry logic      → up to max_retries on JSON parse failure
#   - token tracking   → updates hub.meta.total_tokens_used
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from core.knowledge_hub import KnowledgeHub
from modules.pii_sanitizer import sanitize, desanitize


# ── Base Agent ────────────────────────────────────────────────────────────────

class BaseAgent(ABC):
    """
    All specialist agents extend this class.

    Minimal subclass example:
        class AgentBPMN(BaseAgent):
            name = "bpmn"
            skill_path = "skills/skill_bpmn.md"

            def build_prompt(self, hub):
                return self._skill, f"Extract BPMN from:\\n{hub.transcript_clean}"

            def run(self, hub):
                system, user = self.build_prompt(hub)
                data = self._call_with_retry(system, user, hub)
                hub.bpmn.ready = True
                hub.mark_agent_run(self.name)
                hub.bump()
                return hub
    """

    # Subclasses must declare these
    name: str = "base"
    skill_path: str = ""

    def __init__(self, client_info: dict, provider_cfg: dict):
        """
        Args:
            client_info:  {"api_key": "...", ...}  from session_security
            provider_cfg: AVAILABLE_PROVIDERS[selected]
        """
        self.client_info = client_info
        self.provider_cfg = provider_cfg
        self.max_retries: int = 2
        self._skill: str = self._load_skill()

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    def run(self, hub: KnowledgeHub) -> KnowledgeHub:
        """Execute agent logic. Reads from hub, writes to hub, returns hub."""
        ...

    @abstractmethod
    def build_prompt(self, hub: KnowledgeHub) -> tuple[str, str]:
        """Return (system_prompt, user_prompt) for this agent."""
        ...

    # ── UTF-8 sanitizer ───────────────────────────────────────────────────────

    @staticmethod
    def _ensure_utf8(s: str) -> str:
        """
        Round-trip through UTF-8 to strip surrogate or corrupt code points.

        The httpx layer (used by the OpenAI SDK) serialises the request body as
        UTF-8.  If a string contains characters that were accidentally encoded as
        Latin-1, or lone surrogates from a bad decode, httpx raises
        UnicodeEncodeError before the request leaves the process.

        This helper is applied to every string that enters _call_openai and to
        the error hint that is re-injected on retries.
        """
        return s.encode("utf-8", errors="replace").decode("utf-8")

    # ── LLM call ─────────────────────────────────────────────────────────────

    def _is_long_context_enabled(self) -> bool:
        """Read the enable_long_context toggle from Streamlit session state."""
        try:
            import streamlit as st
            return bool(st.session_state.get("enable_long_context", True))
        except Exception:
            return True  # default on when outside Streamlit (batch mode)

    def _call_llm(
        self, system: str, user: str, hub: KnowledgeHub, skip_cache: bool = False
    ) -> str:
        """
        Provider-agnostic LLM call. Routes by client_type in provider_cfg.
        Updates hub.meta.total_tokens_used on success.

        PII sanitization (Fase A): structured PII in the user prompt
        (CPF, CNPJ, email, phone, monetary values) is replaced with stable
        tokens before the text leaves the process. Tokens are restored in the
        raw LLM response before returning, so callers never see the tokens.
        Personal names are intentionally preserved (required for BPMN lanes,
        meeting minutes, and IBIS attribution).

        Long context mode (Fase 2): for agents in LONG_CONTEXT_AGENTS and
        transcripts estimated above 50k tokens, injects an explicit instruction
        into the system prompt, increases max_tokens output and API timeout.
        This prevents truncated outputs (e.g. incomplete BPMN for long meetings).
        No non-standard API parameters are sent.

        Semantic cache: checks Supabase llm_cache before calling the API.
        Cache stores the raw output (pre-desanitize); on hit, desanitize is
        applied with the current session's token_map — PII-safe across sessions.
        Cache key includes the (possibly modified) system prompt, so long-context
        and standard calls are cached separately. Pass skip_cache=True to bypass.
        """
        client_type = self.provider_cfg["client_type"]
        api_key = self.client_info["api_key"]
        model = self.provider_cfg["default_model"]

        # ── Scenario model override (NF-5: safe — scenario_assignments may be absent) ─
        try:
            import streamlit as st
            _assignments = st.session_state.get("scenario_assignments", {})
            if self.name in _assignments:
                model = _assignments[self.name]
        except Exception:
            pass
        # ─────────────────────────────────────────────────────────────────────

        # ── A2A delegation hint (LangGraph cross-agent coordination) ─────────
        # Injected by LGFullPipelineRunner delegation nodes via _lg_delegation_hint.
        # Appended to system prompt so it influences the LLM without altering the
        # user prompt or the PII sanitization pipeline.
        _delegation_hint = getattr(self, "_lg_delegation_hint", "")
        if _delegation_hint:
            system = system + "\n\n## CONTEXTO DE COORDENAÇÃO\n" + _delegation_hint
        # ─────────────────────────────────────────────────────────────────

        # ── PII sanitization ──────────────────────────────────────────────
        sanitized = sanitize(user)
        safe_user = sanitized.text
        token_map = sanitized.token_map
        # ─────────────────────────────────────────────────────────────────

        # ── Long context detection (before cache hash) ────────────────────
        try:
            from services.context_analyzer import (
                should_use_long_context,
                inject_long_context_instruction,
            )
            use_long_ctx = should_use_long_context(
                safe_user, self.name, enabled=self._is_long_context_enabled()
            )
        except Exception:
            use_long_ctx = False

        if use_long_ctx:
            system = inject_long_context_instruction(system, True)
            hub.meta.long_context_calls = getattr(hub.meta, "long_context_calls", 0) + 1

        _timeout = 180 if use_long_ctx else 60
        # ─────────────────────────────────────────────────────────────────

        # ── Semantic cache lookup ─────────────────────────────────────────
        # _lg_skip_cache is set by LangGraph runners on retry attempts (attempt > 1)
        # to guarantee a fresh LLM call and avoid identical results every retry.
        if not (skip_cache or getattr(self, "_lg_skip_cache", False)):
            try:
                from services.semantic_cache import _cache
                provider_label = self.provider_cfg.get("api_key_label", client_type)
                cache_hash = _cache.compute_hash(provider_label, model, system, safe_user)
                self._last_computed_cache_hash = cache_hash  # exposed for retry backfill
                hit = _cache.get(cache_hash)
                if hit is not None:
                    cached_raw, cached_tokens = hit
                    if cached_raw:  # defense-in-depth: never use empty cached entries
                        hub.meta.cache_hits = getattr(hub.meta, "cache_hits", 0) + 1
                        hub.meta.tokens_saved = (
                            getattr(hub.meta, "tokens_saved", 0) + cached_tokens
                        )
                        return desanitize(cached_raw, token_map)
            except Exception:
                cache_hash = None  # cache unavailable — proceed to API call
        else:
            cache_hash = None
        # ─────────────────────────────────────────────────────────────────

        t0 = time.time()

        if client_type == "openai_compatible":
            raw, tokens_in, tokens_out = self._call_openai(
                system, safe_user, api_key, model,
                timeout=_timeout, long_context=use_long_ctx,
            )
        elif client_type == "anthropic":
            raw, tokens_in, tokens_out = self._call_anthropic(
                system, safe_user, api_key, model,
                timeout=_timeout, long_context=use_long_ctx,
            )
        else:
            raise ValueError(f"Unknown client_type: {client_type}")

        tokens = tokens_in + tokens_out
        elapsed_ms = int((time.time() - t0) * 1000)
        hub.meta.total_tokens_used += tokens
        hub.meta.processing_time_ms += elapsed_ms
        hub.meta.llm_provider = self.provider_cfg.get("api_key_label", "")
        hub.meta.llm_model = model

        # ── Telemetry record (async, fail-open) ───────────────────────────
        try:
            from services.llm_telemetry import _telemetry, TelemetryRecord
            _telemetry.record(TelemetryRecord(
                agent_name=self.name,
                provider=self.provider_cfg.get("api_key_label", client_type),
                model=model,
                latency_ms=elapsed_ms,
                input_tokens=tokens_in,
                output_tokens=tokens_out,
                total_tokens=tokens,
                from_cache=False,
                long_context=use_long_ctx,
                is_error=False,
                benchmark_run=False,
            ))
        except Exception:
            pass
        # ─────────────────────────────────────────────────────────────────

        # ── Store in cache (raw, pre-desanitize) ──────────────────────────
        # Never cache empty/None responses — a transient API failure would
        # permanently poison the cache for the same prompt hash.
        if cache_hash is not None and raw:
            try:
                from services.semantic_cache import _cache
                _cache.set(cache_hash, self.name, raw, tokens)
            except Exception:
                pass
        # ─────────────────────────────────────────────────────────────────

        # ── Restore originals in response ─────────────────────────────────
        return desanitize(raw, token_map)

    def _call_openai(
        self,
        system: str,
        user: str,
        api_key: str,
        model: str,
        timeout: int = 60,
        long_context: bool = False,
    ) -> tuple[str, int]:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=self.provider_cfg.get("base_url"))

        # Sanitize before sending — httpx encodes body as UTF-8; corrupt or
        # surrogate code points raise UnicodeEncodeError inside the SDK.
        system = self._ensure_utf8(system)
        user   = self._ensure_utf8(user)

        # Long context mode: use a higher output token limit to prevent
        # truncation on complex/long transcripts.
        if long_context:
            max_out = self.provider_cfg.get(
                "long_context_max_tokens",
                max(self.provider_cfg.get("max_tokens", 4096), 8192),
            )
        else:
            max_out = self.provider_cfg.get("max_tokens", 4096)
        # Agent subclasses may declare _min_output_tokens to guarantee a
        # minimum output budget regardless of long-context mode.
        # Example: AgentBPMN sets 8192 because collaboration JSON is large.
        max_out = max(max_out, getattr(self, "_min_output_tokens", 0))

        kwargs: dict[str, Any] = dict(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            max_tokens=max_out,
            temperature=0.1,
        )
        if self.provider_cfg.get("supports_json_mode"):
            kwargs["response_format"] = {"type": "json_object"}
            # DeepSeek (and some providers) require the literal word "json"
            # somewhere in the prompt when json_object mode is active.
            user_msg = kwargs["messages"][-1]["content"]
            if "json" not in user_msg.lower():
                kwargs["messages"][-1]["content"] = (
                    user_msg + "\n\nRespond with valid json only."
                )

        # Thinking mode — DeepSeek V4 Flash/Pro with reasoning_effort
        # Temperature is unsupported in thinking mode; extra_body activates it.
        reasoning_effort = self.provider_cfg.get("reasoning_effort")
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
            kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
            kwargs.pop("temperature", None)

        resp = client.chat.completions.create(**kwargs, timeout=timeout)
        tokens_in  = resp.usage.prompt_tokens     if resp.usage else 0
        tokens_out = resp.usage.completion_tokens if resp.usage else 0
        content = resp.choices[0].message.content if resp.choices else None
        if not content or not content.strip():
            finish_reason = (resp.choices[0].finish_reason if resp.choices else "no_choices")
            raise ValueError(
                f"[{self.name}] LLM retornou conteúdo vazio "
                f"(finish_reason={finish_reason!r}, model={model!r}). "
                f"Possíveis causas: filtro de conteúdo, contexto muito longo, "
                f"ou instabilidade do provider."
            )
        return content, tokens_in, tokens_out

    def _call_anthropic(
        self,
        system: str,
        user: str,
        api_key: str,
        model: str,
        timeout: int = 60,
        long_context: bool = False,
    ) -> tuple[str, int]:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        if long_context:
            max_out = self.provider_cfg.get(
                "long_context_max_tokens",
                max(self.provider_cfg.get("max_tokens", 4096), 8192),
            )
        else:
            max_out = self.provider_cfg.get("max_tokens", 4096)
        max_out = max(max_out, getattr(self, "_min_output_tokens", 0))
        msg = client.messages.create(
            model=model,
            max_tokens=max_out,
            temperature=0.1,
            system=system,
            messages=[{"role": "user", "content": user}],
            timeout=timeout,
        )
        tokens_in  = msg.usage.input_tokens  if msg.usage else 0
        tokens_out = msg.usage.output_tokens if msg.usage else 0
        return msg.content[0].text, tokens_in, tokens_out

    # ── JSON parsing ──────────────────────────────────────────────────────────

    def _parse_json(self, raw: str) -> dict:
        """
        Robust JSON extraction:
          1. Strip markdown fences
          2. Find first { ... last }
          3. Parse
        Raises ValueError with context on failure.
        """
        clean = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).strip()
        clean = clean.rstrip("`").strip()
        start = clean.find("{")
        end = clean.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError(
                f"[{self.name}] No JSON object found in LLM response.\n"
                f"Response preview: {raw[:400]}"
            )
        # Fast path
        try:
            return json.loads(clean[start:end])
        except json.JSONDecodeError:
            pass
        # Fallback: json_repair handles truncated/malformed LLM output
        try:
            from json_repair import repair_json
            repaired = repair_json(clean[start:end], return_objects=True)
            if isinstance(repaired, dict) and repaired:
                return repaired
        except Exception:
            pass
        # All attempts failed — raise with diagnostic info
        try:
            json.loads(clean[start:end])
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"[{self.name}] JSON decode error: {exc}\n"
                f"Raw snippet: {clean[start:start+300]}"
            ) from exc

    def _call_with_retry(
        self,
        system: str,
        user: str,
        hub: KnowledgeHub,
        parse_fn=None,
    ) -> dict:
        """
        Call LLM and parse JSON. Retries up to self.max_retries on parse failure.
        parse_fn: optional callable(raw_str) → dict. Defaults to self._parse_json.
        """
        parse = parse_fn or self._parse_json
        last_error: Optional[Exception] = None

        for attempt in range(1 + self.max_retries):
            try:
                raw = self._call_llm(system, user, hub)
                return parse(raw)
            except (ValueError, KeyError, UnicodeEncodeError) as exc:
                last_error = exc
                if attempt < self.max_retries:
                    # repr() gives an ASCII-safe representation of the error,
                    # avoiding re-injection of non-ASCII chars into the next prompt.
                    hint = repr(str(exc))[:300]
                    user = self._ensure_utf8(
                        f"{user}\n\n"
                        f"IMPORTANT: Your previous response caused a parse error:\n{hint}\n"
                        f"Return ONLY valid JSON. No markdown. No explanation."
                    )

        raise RuntimeError(
            f"[{self.name}] Failed after {1 + self.max_retries} attempts. "
            f"Last error: {repr(last_error)}"
        )

    # ── Cache backfill ────────────────────────────────────────────────────────

    def _backfill_cache(self, cache_hash: str, raw: str) -> None:
        """Store raw LLM output under an alternate hash (used to backfill H0 after retry)."""
        if not cache_hash or not raw:
            return
        try:
            from services.semantic_cache import _cache
            _cache.set(cache_hash, self.name, raw, 0)
        except Exception:
            pass

    # ── Skill loading ─────────────────────────────────────────────────────────

    def _load_skill(self) -> str:
        """Load SKILL.md content, stripping YAML frontmatter before returning."""
        if not self.skill_path:
            return ""
        # Use absolute path so this works regardless of CWD (local or Streamlit Cloud)
        project_root = Path(__file__).parent.parent
        path = project_root / self.skill_path
        if not path.exists():
            return ""
        content = path.read_text(encoding="utf-8")
        # Strip YAML frontmatter (--- ... ---) — metadata noise, not LLM instructions
        content = re.sub(r'^---\s*\n.*?\n---\s*\n', '', content, flags=re.DOTALL)
        return content.lstrip('\n')

    # ── Language helper ───────────────────────────────────────────────────────

    @staticmethod
    def _language_instruction(output_language: str) -> str:
        return {
            "Auto-detect": "same language as the input transcript",
            "English": "English",
            "Portuguese (BR)": "Brazilian Portuguese",
        }.get(output_language, "same language as the input transcript")
