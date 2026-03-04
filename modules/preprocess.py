from __future__ import annotations
import re

def normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()

def remove_filler(text: str) -> str:
    # heurística simples; ajuste ao seu gosto
    fillers = [
        r"\b(é|né|tipo|assim|então|tá|tá bom|beleza|ok)\b",
        r"\b(hum|hã|ahn|uh)\b",
    ]
    out = text
    for pat in fillers:
        out = re.sub(pat, "", out, flags=re.IGNORECASE)
    out = re.sub(r"\s{2,}", " ", out)
    return out.strip()

def preprocess_transcript(text: str) -> str:
    text = normalize_whitespace(text)
    text = remove_filler(text)
    return text
