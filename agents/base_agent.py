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


# ── Base Agent ────────────────────────────────────────────────────────────────

class BaseAgent(ABC):
    """
    All specialist agents extend this class.

    Minimal subclass example:
        class AgentBPMN(BaseAgent):
            name = "bpmn"
            skill_path = "skills/SKILL_BPMN.md"

            def build_prompt(self, hub):
                return self._skill, f"Extract BPMN from:\\n{hub.transcript_clean}"

            def run(self, hub):
                system, user = self.build_prompt(hub)
                raw = self._call_llm(system, user, hub)
                data = self._parse_json(raw)
                # populate hub.bpmn ...
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

    # ── LLM call ─────────────────────────────────────────────────────────────

    def _call_llm(self, system: str, user: str, hub: KnowledgeHub) -> str:
        """
        Provider-agnostic LLM call. Routes by client_type in provider_cfg.
        Updates hub.meta.total_tokens_used on success.
        """
        client_type = self.provider_cfg["client_type"]
        api_key = self.client_info["api_key"]
        model = self.provider_cfg["default_model"]

        t0 = time.time()

        if client_type == "openai_compatible":
            raw, tokens = self._call_openai(system, user, api_key, model)
        elif client_type == "anthropic":
            raw, tokens = self._call_anthropic(system, user, api_key, model)
        else:
            raise ValueError(f"Unknown client_type: {client_type}")

        elapsed_ms = int((time.time() - t0) * 1000)
        hub.meta.total_tokens_used += tokens
        hub.meta.processing_time_ms += elapsed_ms
        hub.meta.llm_provider = self.provider_cfg.get("api_key_label", "")
        hub.meta.llm_model = model

        return raw

    def _call_openai(self, system: str, user: str, api_key: str, model: str) -> tuple[str, int]:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=self.provider_cfg.get("base_url"))
        kwargs: dict[str, Any] = dict(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=3000,
            temperature=0.1,
        )
        if self.provider_cfg.get("supports_json_mode"):
            kwargs["response_format"] = {"type": "json_object"}
            # DeepSeek requires the literal word "json" in the prompt.
            user_msg = kwargs["messages"][-1]["content"]
            if "json" not in user_msg.lower():
                kwargs["messages"][-1]["content"] = user_msg + "\n\nRespond with valid json only."

        try:
            resp = client.chat.completions.create(**kwargs)
        except UnicodeEncodeError:
            # Fallback: strip non-BMP chars and retry once
            for msg in kwargs["messages"]:
                msg["content"] = msg["content"].encode("utf-16", "surrogatepass").decode("utf-16")
            resp = client.chat.completions.create(**kwargs)
        tokens = resp.usage.total_tokens if resp.usage else 0
        return resp.choices[0].message.content, tokens

    def _call_anthropic(self, system: str, user: str, api_key: str, model: str) -> tuple[str, int]:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model,
            max_tokens=3000,
            temperature=0.1,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        tokens = (msg.usage.input_tokens + msg.usage.output_tokens) if msg.usage else 0
        return msg.content[0].text, tokens

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
        try:
            return json.loads(clean[start:end])
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
                    # Use str(exc) directly — no ASCII encoding, API accepts UTF-8.
                    user = (
                        f"{user}\n\n"
                        f"IMPORTANT: Your previous response caused a parse error:\n{str(exc)}\n"
                        f"Return ONLY valid JSON. No markdown. No explanation."
                    )

        raise RuntimeError(
            f"[{self.name}] Failed after {1 + self.max_retries} attempts. "
            f"Last error: {repr(last_error)}"
        )

    # ── Skill loading ─────────────────────────────────────────────────────────

    def _load_skill(self) -> str:
        """Load SKILL.md content. Returns empty string if not found."""
        if not self.skill_path:
            return ""
        path = Path(self.skill_path)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    # ── Language helper ───────────────────────────────────────────────────────

    @staticmethod
    def _language_instruction(output_language: str) -> str:
        return {
            "Auto-detect": "same language as the input transcript",
            "English": "English",
            "Portuguese (BR)": "Brazilian Portuguese",
        }.get(output_language, "same language as the input transcript")
