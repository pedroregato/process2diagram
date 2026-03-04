## (fallback sem LLM)

from __future__ import annotations
import re
from typing import List, Tuple
from .schema import ProcessModel, Step, Edge

_VERB_HINT = r"(criar|abrir|enviar|validar|aprovar|rejeitar|registrar|gerar|assinar|publicar|extrair|classificar|notificar|arquivar|salvar|baixar|subir|atualizar)"
_SPLIT_PATTERNS = [
    r"^\s*\d+[\)\.\-]\s+",          # "1) ...", "1. ..."
    r"^\s*[-•]\s+",                 # bullet
    r"^\s*(passo|etapa)\s*\d*[:\-]\s+",  # "Passo 1: ..."
]

def _split_candidates(text: str) -> List[str]:
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    chunks: List[str] = []
    cur: List[str] = []

    for ln in lines:
        is_new = any(re.match(p, ln, flags=re.IGNORECASE) for p in _SPLIT_PATTERNS)
        if is_new and cur:
            chunks.append(" ".join(cur).strip())
            cur = [re.sub(r"^\s*(\d+[\)\.\-]|[-•]|passo|etapa)\s*\d*[:\-]?\s*", "", ln, flags=re.IGNORECASE).strip()]
        else:
            cur.append(ln)
    if cur:
        chunks.append(" ".join(cur).strip())

    # Se não achou nada, tenta por frases com “então / depois / em seguida”
    if len(chunks) <= 1:
        rough = re.split(r"\b(então|depois|em seguida|na sequência)\b[:,]?\s*", text, flags=re.IGNORECASE)
        chunks = [c.strip(" ,.;:-") for c in rough if c.strip()]

    return chunks[:25]  # limite de segurança

def _title_from_chunk(chunk: str) -> str:
    # pega até 8 palavras, privilegia verbo
    words = re.findall(r"[A-Za-zÀ-ÿ0-9_]+", chunk)
    if not words:
        return "Step"
    title = " ".join(words[:8])
    return title

def _guess_actor(chunk: str) -> str | None:
    # heurística simples: "Fulano:" ou "Equipe X"
    m = re.match(r"^([A-Za-zÀ-ÿ ]{2,30})\s*:\s*", chunk)
    if m:
        return m.group(1).strip()
    m2 = re.search(r"\b(equipe|time|sra|ndoc|jurídico|compras)\b", chunk, flags=re.IGNORECASE)
    if m2:
        return m2.group(0)
    return None

def extract_process_heuristic(text: str, name: str = "Process") -> ProcessModel:
    chunks = _split_candidates(text)

    steps: List[Step] = []
    for i, ch in enumerate(chunks, start=1):
        step_id = f"S{i:02d}"
        title = _title_from_chunk(ch)
        actor = _guess_actor(ch)
        steps.append(Step(id=step_id, title=title, description=ch, actor=actor))

    edges: List[Edge] = []
    for i in range(len(steps) - 1):
        edges.append(Edge(source=steps[i].id, target=steps[i+1].id))

    # Se tiver pistas de decisão, cria arestas com labels
    # Ex: "se aprovado" / "se não"
    for s in steps:
        if re.search(r"\bse\s+(aprovad|aceit)\w*\b", (s.description or ""), flags=re.IGNORECASE):
            # nada sofisticado; fica como annotation no passo
            pass

    return ProcessModel(name=name, steps=steps, edges=edges)
