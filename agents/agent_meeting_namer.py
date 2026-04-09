# agents/agent_meeting_namer.py
# ─────────────────────────────────────────────────────────────────────────────
# Sugere título e extrai data de uma transcrição via LLM.
# Usado pelo BatchPipeline para nomear reuniões automaticamente.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import re
from pathlib import Path

from agents.base_agent import BaseAgent

_SYSTEM_PROMPT = """\
You are a meeting analyst assistant.
Given the beginning of a meeting transcript and its filename, extract or infer:
1. A short, descriptive title for the meeting (max 60 characters).
   Describe the main topic discussed — never use generic titles like "Meeting" or "Reunião".
2. The meeting date, if mentioned anywhere in the text.

Return ONLY valid JSON, no explanation:
{
  "title": "<descriptive meeting title>",
  "date": "<YYYY-MM-DD or null if not found or ambiguous>"
}

Date search order:
- ISO format: 2024-01-15
- Brazilian format: 15/01/2024 or 15.01.2024
- Written: "15 de janeiro de 2024" or "janeiro de 2024"
If only month/year is found, use the 1st day of that month.
"""


class AgentMeetingNamer(BaseAgent):
    """Extrai título descritivo e data de uma transcrição (chamada única ao LLM)."""

    name = "meeting_namer"
    skill_path = None  # prompt definido inline

    def _load_skill(self) -> str:  # type: ignore[override]
        return _SYSTEM_PROMPT

    def build_prompt(self, hub, output_language: str = "Auto-detect"):  # type: ignore[override]
        return _SYSTEM_PROMPT, ""

    def run(self, hub, output_language: str = "Auto-detect"):  # type: ignore[override]
        return hub  # não usado no pipeline padrão

    def suggest(self, content: str, filename: str, hub) -> dict[str, str | None]:
        """Retorna {"title": "...", "date": "YYYY-MM-DD" | None}.

        Usa os primeiros 1000 caracteres da transcrição + nome do arquivo.
        Em caso de erro, retorna título derivado do nome do arquivo e date=None.
        """
        snippet = content[:1000]
        user_prompt = (
            f"Filename: {filename}\n\n"
            f"Transcript beginning:\n{snippet}"
        )
        try:
            raw = self._call_llm(_SYSTEM_PROMPT, user_prompt, hub)
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                result = json.loads(match.group())
                return {
                    "title": (result.get("title") or "").strip() or None,
                    "date":  result.get("date") or None,
                }
        except Exception:
            pass
        # Fallback: sanitiza o nome do arquivo
        stem = Path(filename).stem.replace("_", " ").replace("-", " ")
        return {"title": stem.title(), "date": None}
