# modules/embeddings.py
# ─────────────────────────────────────────────────────────────────────────────
# Utilitários de embedding para busca semântica.
#
# Provedores suportados (APIs de nuvem com endpoint de embeddings):
#   - Google Gemini: text-embedding-004 (768 dims nativos) — tier gratuito
#   - OpenAI: text-embedding-3-small com dimensions=768
#   - Grok (xAI): grok-embedding-small — mesma chave da API xAI (console.x.ai)
#
# NOTA: A API pública do DeepSeek NÃO possui endpoint de embeddings.
# Grok (xAI) suporta /v1/embeddings via OpenAI-compatible endpoint.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

# ── Dimensão alvo ─────────────────────────────────────────────────────────────
EMBEDDING_DIM = 1536  # gemini-embedding-001 truncado (máx ivfflat = 2000 dims)

# ── Provedores de embedding suportados ───────────────────────────────────────
EMBEDDING_PROVIDERS = {
    "Google Gemini": {
        "model":         "models/gemini-embedding-001",
        "base_url":      None,
        "api_key_label": "Google API Key",
        "api_key_help":  "Crie em aistudio.google.com → Get API Key. Tier gratuito disponível.",
        "api_key_prefix": "AI",
    },
    "OpenAI": {
        "model":         "text-embedding-3-small",
        "base_url":      None,
        "api_key_label": "OpenAI API Key",
        "api_key_help":  "Crie em platform.openai.com/api-keys",
        "api_key_prefix": "sk-",
    },
    # ── Novo: Grok (xAI) ─────────────────────────────────────────────────────
    "Grok (xAI)": {
        "model":         "grok-embedding-small",
        "base_url":      "https://api.x.ai/v1",
        "api_key_label": "xAI Grok API Key",
        "api_key_help":  "Mesma chave usada no LLM Principal (console.x.ai). Suporta endpoint /v1/embeddings.",
        "api_key_prefix": "xai-",
    },
}


# ── Normalização para embedding ───────────────────────────────────────────────

def normalize_for_embedding(text: str) -> str:
    """
    Limpa lixo de ASR / SRT antes de chunking.

    Remove:
      • Timestamps SRT/VTT  (00:00:15,000 --> 00:00:18,000, [00:15:30], etc.)
      • Números de sequência SRT (linhas só com dígitos)
      • Marcadores de ruído  ([inaudível], (risos), [noise], etc.)
      • Tags HTML e entidades comuns
      • Separadores decorativos (-----, =====, .....)
      • Linhas com menos de 4 caracteres não-espaço (puro ruído)

    Preserva:
      • Nomes de falantes  ("PEDRO:", "Maria:")
      • Conteúdo das falas
      • Parágrafos/quebras de linha (importantes para chunk_text)
    """
    import re

    if not text:
        return ""

    # Tags HTML
    text = re.sub(r'<[^>]+>', ' ', text)

    # Entidades HTML comuns
    for ent, ch in (('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'), ('&nbsp;', ' '), ('&quot;', '"')):
        text = text.replace(ent, ch)

    # Timestamps SRT/VTT completos: "00:00:15,000 --> 00:00:18,000"
    text = re.sub(
        r'\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3}\s*-->\s*\d{1,2}:\d{2}:\d{2}[,\.]\d{1,3}',
        ' ', text,
    )
    # Timestamps isolados: [00:15:30] ou 0:15:30
    text = re.sub(r'\[?\d{1,2}:\d{2}:\d{2}\]?', ' ', text)
    # Timestamps mm:ss isolados (só antes de espaço para não capturar "às 9:30 a reunião")
    text = re.sub(r'\[?\d{1,2}:\d{2}\]?(?=\s|$)', ' ', text)

    # Números de sequência SRT (linhas contendo apenas dígitos)
    text = re.sub(r'^\s*\d+\s*$', '', text, flags=re.MULTILINE)

    # Marcadores de ruído / inaudível (PT e EN)
    text = re.sub(
        r'[\[\(]'
        r'(?:inaudível|inaudible|inaud\.?|ruído|noise|risos?|laughter|'
        r'aplausos?|applause|música|music|silêncio|silence|corte|cut|'
        r'trecho\s+inaudível|unintelligible)'
        r'[\]\)]',
        ' ', text, flags=re.IGNORECASE,
    )

    # Separadores decorativos: ----, ====, ....
    text = re.sub(r'[-=_\.~]{4,}', ' ', text)

    # Colapsa espaços múltiplos dentro de cada linha
    lines_out: list[str] = []
    for line in text.splitlines():
        line = re.sub(r'[ \t]+', ' ', line).strip()
        # Descarta linhas com menos de 4 caracteres não-espaço (ruído puro)
        if len(line.replace(' ', '')) >= 4:
            lines_out.append(line)

    return '\n'.join(lines_out)


# ── Chunking ───────────────────────────────────────────────────────────────────
def chunk_text(
    text: str,
    chunk_size: int = 500,
    overlap: int = 80,
) -> list[str]:
    """
    Divide o texto em chunks de tamanho aproximado `chunk_size` chars com `overlap`.

    Tenta dividir em parágrafos/linhas primeiro; se um parágrafo for muito longo,
    divide por palavras. Garante que nenhum chunk fique vazio.

    Returns:
        Lista de strings (chunks).
    """
    if not text or not text.strip():
        return []

    # Divide por linhas em branco (parágrafos) para preservar contexto semântico
    paragraphs: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.strip():
            current.append(line)
        else:
            if current:
                paragraphs.append(" ".join(current))
                current = []
    if current:
        paragraphs.append(" ".join(current))

    # Agrupa parágrafos em chunks respeitando chunk_size
    chunks: list[str] = []
    buffer = ""

    for para in paragraphs:
        # Parágrafo cabe no buffer?
        if len(buffer) + len(para) + 1 <= chunk_size:
            buffer = (buffer + " " + para).strip()
        else:
            # Salva buffer atual (se não vazio)
            if buffer:
                chunks.append(buffer)
            # Parágrafo maior que chunk_size? Divide por palavras
            if len(para) > chunk_size:
                words = para.split()
                buf2 = ""
                for word in words:
                    if len(buf2) + len(word) + 1 <= chunk_size:
                        buf2 = (buf2 + " " + word).strip()
                    else:
                        if buf2:
                            chunks.append(buf2)
                        buf2 = word
                buffer = buf2
            else:
                buffer = para

    if buffer:
        chunks.append(buffer)

    # Aplica overlap: cada chunk (exceto o primeiro) prefixado com final do anterior
    if overlap > 0 and len(chunks) > 1:
        overlapped: list[str] = [chunks[0]]
        for i in range(1, len(chunks)):
            tail = chunks[i - 1][-overlap:]
            overlapped.append((tail + " " + chunks[i]).strip())
        return [c for c in overlapped if c.strip()]

    return [c for c in chunks if c.strip()]


# ── Embedding de texto único ──────────────────────────────────────────────────

def embed_text(text: str, api_key: str, provider: str) -> list[float]:
    """
    Gera embedding de 1536 dimensões para um texto usando o provedor especificado.

    Args:
        text:     Texto a embedar.
        api_key:  API key do provedor.
        provider: "Google Gemini", "OpenAI" ou "Grok (xAI)".

    Returns:
        Lista de 1536 floats.

    Raises:
        ValueError: provedor desconhecido ou resposta inesperada.
        Exception:  erro da API.
    """
    if provider == "Google Gemini":
        return _embed_gemini(text, api_key)
    elif provider == "OpenAI":
        return _embed_openai_compatible(text, api_key, "text-embedding-3-small", None)
    elif provider == "Grok (xAI)":
        return _embed_openai_compatible(
            text, api_key, "grok-embedding-small", "https://api.x.ai/v1"
        )
    else:
        raise ValueError(f"Provedor de embedding desconhecido: {provider!r}")


def embed_batch(texts: list[str], api_key: str, provider: str) -> list[list[float]]:
    """
    Gera embeddings para uma lista de textos.

    OpenAI e Grok (xAI): batch nativo (uma chamada para todos os textos).
    Google Gemini: chamadas individuais (SDK Python não suporta batch).

    Returns:
        Lista de listas de 1536 floats, na mesma ordem de `texts`.
    """
    if not texts:
        return []

    if provider == "Google Gemini":
        return _embed_batch_gemini(texts, api_key)
    elif provider in ("OpenAI", "Grok (xAI)"):
        cfg = EMBEDDING_PROVIDERS[provider]
        base_url = cfg.get("base_url")
        model = cfg["model"]
        return _embed_batch_openai_compatible(texts, api_key, model=model, base_url=base_url)
    else:
        return [embed_text(t, api_key, provider) for t in texts]


# ── Implementações por provedor ───────────────────────────────────────────────

def _embed_openai_compatible(
    text: str,
    api_key: str,
    model: str,
    base_url: str | None,
) -> list[float]:
    """
    Embedding via API compatível com OpenAI SDK.
    Usado para OpenAI e Grok (xAI).
    """
    from openai import OpenAI

    kwargs: dict = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url

    client = OpenAI(**kwargs)

    resp = client.embeddings.create(model=model, input=text)
    embedding = resp.data[0].embedding

    if len(embedding) != EMBEDDING_DIM:
        raise ValueError(
            f"Embedding {model} retornou {len(embedding)} dims, esperado {EMBEDDING_DIM}"
        )
    return embedding


def _embed_batch_openai_compatible(
    texts: list[str],
    api_key: str,
    model: str,
    base_url: str | None,
) -> list[list[float]]:
    """Batch embedding via API compatível com OpenAI SDK (OpenAI + Grok)."""
    from openai import OpenAI

    kwargs: dict = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url

    client = OpenAI(**kwargs)

    resp = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]


# (Todo o código de _embed_gemini, _embed_batch_gemini e list_gemini_embedding_models
# permanece exatamente igual — não mexi em nada)

_GEMINI_RATE_DELAY = 1.2
_GEMINI_MAX_RETRIES = 5


def _embed_gemini(text: str, api_key: str) -> list[float]:
    """Google Gemini embeddings via google-generativeai SDK. (mantido inalterado)"""
    import re
    import time
    import warnings
    warnings.filterwarnings("ignore", category=FutureWarning, module="google")
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise ImportError(
            "Pacote google-generativeai não instalado. "
            "Execute: pip install google-generativeai"
        ) from exc

    genai.configure(api_key=api_key)

    for model_name in ("models/gemini-embedding-001", "models/gemini-embedding-2-preview"):
        for attempt in range(_GEMINI_MAX_RETRIES):
            try:
                result = genai.embed_content(
                    model=model_name,
                    content=text,
                    task_type="retrieval_document",
                    output_dimensionality=EMBEDDING_DIM,
                )
                embedding = result["embedding"]
                if len(embedding) != EMBEDDING_DIM:
                    raise ValueError(
                        f"Embedding {model_name} retornou {len(embedding)} dims, "
                        f"esperado {EMBEDDING_DIM}"
                    )
                return embedding

            except Exception as exc:
                exc_str = str(exc)
                is_rate_limit = (
                    "429" in exc_str
                    or "quota" in exc_str.lower()
                    or "rate limit" in exc_str.lower()
                    or "resource exhausted" in exc_str.lower()
                )
                if is_rate_limit:
                    m = re.search(r"seconds[\"':\s]+(\d+)", exc_str)
                    wait = int(m.group(1)) + 10 if m else 40
                    time.sleep(wait)
                    continue
                if "404" in exc_str and model_name == "models/gemini-embedding-001":
                    break
                raise
        else:
            raise RuntimeError(
                f"Rate limit Gemini: {_GEMINI_MAX_RETRIES} tentativas esgotadas para {model_name}."
            )

    raise RuntimeError(
        "Nenhum modelo Gemini disponível. "
        "Use '🔍 Testar chave' para ver os modelos disponíveis para sua chave."
    )


def _embed_batch_gemini(texts: list[str], api_key: str) -> list[list[float]]:
    """Batch: chama _embed_gemini com delay entre chamadas (mantido inalterado)."""
    import time
    results = []
    for t in texts:
        results.append(_embed_gemini(t, api_key))
        time.sleep(_GEMINI_RATE_DELAY)
    return results


# ── Diagnóstico ───────────────────────────────────────────────────────────────

def list_gemini_embedding_models(api_key: str) -> list[dict]:
    """Lista os modelos Gemini que suportam embedContent (mantido inalterado)."""
    import warnings
    warnings.filterwarnings("ignore", category=FutureWarning, module="google")

    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise ImportError(
            "Pacote google-generativeai não instalado. "
            "Execute: pip install google-generativeai"
        ) from exc

    genai.configure(api_key=api_key)
    try:
        models = [
            {"name": m.name, "display_name": getattr(m, "display_name", m.name)}
            for m in genai.list_models()
            if "embedContent" in (m.supported_generation_methods or [])
        ]
    except Exception as exc:
        raise RuntimeError(f"Erro ao listar modelos Gemini: {exc}") from exc

    return models