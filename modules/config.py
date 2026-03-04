from __future__ import annotations
from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    use_llm: bool = os.getenv("USE_LLM", "0") == "1"
    # placeholders para quando você plugar LLM:
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")  # openai|azure|local
    llm_model: str = os.getenv("LLM_MODEL", "gpt-4.1-mini")  # exemplo
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
  
