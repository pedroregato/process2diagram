# agents/base_agent.py
# ─────────────────────────────────────────────────────────────────────────────
# Abstract base class for all specialist agents.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import re
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Optional

from core.knowledge_hub import KnowledgeHub


class BaseAgent(ABC):

    name: str = "base"
    skill_path: str = ""

    def __init__(self, client_info: dict, provider_cfg: dict):
        self.client_info = client_info
        self.provider_cfg = provider_cfg
        self.max_retries: int = 2
        self._skill: str = self._load_skill()

    @abstractmethod
    def run(self, hub: KnowledgeHub) -> KnowledgeHub: ...

    @abstractmethod
    def build_prompt(self, hub: KnowledgeHub) -> tuple[str, str]: ...

    # ── LLM call ─────────────────────────────────────────────────────────────

    def _call_llm(self, system: str, user: str, hub: KnowledgeHub) -> str:
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

        hub.meta.total_tokens_used += tokens
        hub.meta.processing_time_ms += int((time.time() - t0) * 1000)
        hub.meta.llm_provider = self.provider_cfg.get("api_key_label", "")
        hub.meta.llm_model = model
        return raw

    @staticmethod
    def _ensure_utf8(s: str) -> str:
        """Round-trip through UTF-8 to strip surrogates/corrupt code points."""
        return s.encode("utf-8", errors="replace").decode("utf-8")

    def _call_openai(self, system: str, user: str, api_key: str, model: str) -> tuple[str, int]:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=self.provider_cfg.get("base_url"))

        system = self._ensure_utf8(system)
        user   = self._ensure_utf8(user)

        kwargs: dict[str, Any] = dict(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
            max_tokens=3000,
            temperature=0.1,
        )
        if self.provider_cfg.get("supports_json_mode"):
            kwargs["response_format"] = {"type": "json_object"}
            user_msg = kwargs["messages"][-1]["content"]
            if "json" not in user_msg.lower():
                kwargs["messages"][-1]["content"] = user_msg + "\n\nRespond with valid json only."

        resp = client.chat.completions.create(**kwargs)
        tokens = resp.usage.total_tokens if resp.usage else 0
        return resp.choices[0].message.content, tokens

    def _call_anthropic(self, system: str, user: str, api_key: str, model: str) -> tuple[str, int]:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model=model, max_tokens=3000, temperature=0.1,
            system=system, messages=[{"role": "user", "content": user}],
        )
        tokens = (msg.usage.input_tokens + msg.usage.output_tokens) if msg.usage else 0
        return msg.content[0].text, tokens

    # ── JSON parsing ──────────────────────────────────────────────────────────

    def _parse_json(self, raw: str) -> dict:
        clean = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).strip().rstrip("`").strip()
        start = clean.find("{")
        end   = clean.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError(f"[{self.name}] No JSON object found.\nPreview: {raw[:400]}")
        try:
            return json.loads(clean[start:end])
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"[{self.name}] JSON decode error: {exc}\nSnippet: {clean[start:start+300]}"
            ) from exc

    def _call_with_retry(self, system: str, user: str, hub: KnowledgeHub, parse_fn=None) -> dict:
        parse = parse_fn or self._parse_json
        last_error: Optional[Exception] = None

        for attempt in range(1 + self.max_retries):
            try:
                raw = self._call_llm(system, user, hub)
                return parse(raw)
            except (ValueError, KeyError, UnicodeEncodeError) as exc:
                last_error = exc
                if attempt < self.max_retries:
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

    # ── Skill loading ─────────────────────────────────────────────────────────

    def _load_skill(self) -> str:
        if not self.skill_path:
            return ""
        path = Path(self.skill_path)
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    @staticmethod
    def _language_instruction(output_language: str) -> str:
        return {
            "Auto-detect": "same language as the input transcript",
            "English": "English",
            "Portuguese (BR)": "Brazilian Portuguese",
        }.get(output_language, "same language as the input transcript")