# modules/preprocess.py
import re


_FILLERS = r"\b(uh|um|hmm|like|you know|I mean|sort of|kind of)\b"


def preprocess_text(text: str) -> str:
    """Normalize transcript text before sending to LLM."""
    text = re.sub(_FILLERS, "", text, flags=re.IGNORECASE)
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
