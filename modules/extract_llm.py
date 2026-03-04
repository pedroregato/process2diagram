from __future__ import annotations
from .schema import ProcessModel

def extract_process_llm(text: str, name: str = "Process") -> ProcessModel:
    """
    Placeholder: aqui você pluga OpenAI/Azure/local.
    A ideia é: LLM recebe a transcrição e devolve JSON no formato ProcessModel.
    """
    raise NotImplementedError("LLM extractor not wired yet. Use heuristic extractor or implement provider.")
