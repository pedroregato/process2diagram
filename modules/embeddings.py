# modules/embeddings.py
# ─────────────────────────────────────────────────────────────────────────────
# Utilitários de embedding para busca semântica.
#
# Provedores suportados (APIs de nuvem com endpoint de embeddings):
#   - Google Gemini: text-embedding-004 (768 dims nativos) — tier gratuito
#   - OpenAI: text-embedding-3-small com dimensions=768
#
# NOTA: A API pública do DeepSeek (api.deepseek.com) NÃO possui endpoint de
# embeddings — apenas chat/completions. Use Google Gemini (gratuito) ou OpenAI.
#
# Gemini: google-genai SDK com api_version="v1" (estável).
# Diagnóstico: list_gemini_embedding_models(api_key) lista modelos disponíveis.
#
# Funções públicas:
#   chunk_text(text, chunk_size, overlap) → list[str]
#   embed_text(text, api_key, provider)   → list[float]  (768 dims)
#   embed_batch(texts, api_key, provider) → list[list[float]]
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
}


# ── Chunking ──────────────────────────────────────────────────────────────────

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
    Gera embedding de 768 dimensões para um texto usando o provedor especificado.

    Args:
        text:     Texto a embedar.
        api_key:  API key do provedor.
        provider: "Google Gemini" ou "OpenAI".

    Returns:
        Lista de 768 floats.

    Raises:
        ValueError: provedor desconhecido ou resposta inesperada.
        Exception:  erro da API.
    """
    if provider == "Google Gemini":
        return _embed_gemini(text, api_key)
    elif provider == "OpenAI":
        return _embed_openai_compatible(text, api_key, "text-embedding-3-small", None)
    else:
        raise ValueError(f"Provedor de embedding desconhecido: {provider!r}")


def embed_batch(texts: list[str], api_key: str, provider: str) -> list[list[float]]:
    """
    Gera embeddings para uma lista de textos.

    OpenAI: batch nativo (uma chamada para todos os textos).
    Google Gemini: chamadas individuais (SDK Python não suporta batch).

    Returns:
        Lista de listas de 768 floats, na mesma ordem de `texts`.
    """
    if not texts:
        return []

    if provider == "Google Gemini":
        return _embed_batch_gemini(texts, api_key)
    elif provider == "OpenAI":
        cfg = EMBEDDING_PROVIDERS[provider]
        return _embed_batch_openai_compatible(
            texts, api_key,
            model=cfg["model"],
            base_url=cfg.get("base_url"),
        )
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
    Usado tanto para OpenAI quanto para DeepSeek (mesmo formato).
    Para OpenAI usa dimensions=768; para DeepSeek o modelo já gera 768 dims nativamente.
    """
    from openai import OpenAI

    kwargs: dict = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url

    client = OpenAI(**kwargs)

    create_kwargs: dict = {"model": model, "input": text}
    # OpenAI text-embedding-3-small suporta dimensions; DeepSeek ignora o parâmetro
    if not base_url:  # OpenAI nativo
        create_kwargs["dimensions"] = EMBEDDING_DIM

    resp = client.embeddings.create(**create_kwargs)
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
    """Batch embedding via API compatível com OpenAI SDK."""
    from openai import OpenAI

    kwargs: dict = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url

    client = OpenAI(**kwargs)

    create_kwargs: dict = {"model": model, "input": texts}
    if not base_url:  # OpenAI nativo
        create_kwargs["dimensions"] = EMBEDDING_DIM

    resp = client.embeddings.create(**create_kwargs)
    return [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]


_GEMINI_RATE_DELAY = 1.2   # segundos entre chamadas (~50 req/min, metade do limite free de 100)
_GEMINI_MAX_RETRIES = 5    # tentativas em caso de 429


def _embed_gemini(text: str, api_key: str) -> list[float]:
    """Google Gemini embeddings via google-generativeai SDK.

    Modelos (confirmados pelo diagnóstico):
      - models/gemini-embedding-001  (estável, 1536 dims via output_dimensionality)
      - models/gemini-embedding-2-preview  (fallback)

    Retry automático em 429 usando o retry_delay sugerido pelo próprio erro.
    """
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
                    # Extrai retry_delay do corpo do erro (ex: "seconds: 6")
                    m = re.search(r"seconds[\"':\s]+(\d+)", exc_str)
                    wait = int(m.group(1)) + 10 if m else 40
                    time.sleep(wait)
                    continue  # retenta
                if "404" in exc_str and model_name == "models/gemini-embedding-001":
                    break  # tenta modelo fallback
                raise  # outro erro — propaga imediatamente
        else:
            raise RuntimeError(
                f"Rate limit Gemini: {_GEMINI_MAX_RETRIES} tentativas esgotadas para {model_name}."
            )

    raise RuntimeError(
        "Nenhum modelo Gemini disponível. "
        "Use '🔍 Testar chave' para ver os modelos disponíveis para sua chave."
    )


def _embed_batch_gemini(texts: list[str], api_key: str) -> list[list[float]]:
    """Batch: chama _embed_gemini com delay entre chamadas para respeitar rate limit."""
    import time
    results = []
    for t in texts:
        results.append(_embed_gemini(t, api_key))
        time.sleep(_GEMINI_RATE_DELAY)  # ~85 req/min, abaixo do free tier (100/min)
    return results


# ── Diagnóstico ───────────────────────────────────────────────────────────────

def list_gemini_embedding_models(api_key: str) -> list[dict]:
    """
    Lista os modelos Gemini que suportam embedContent para a chave fornecida.

    Usa google-generativeai (v1beta) para máxima compatibilidade com list_models().
    Retorna lista de dicts com 'name' e 'display_name'.
    Lança RuntimeError se a chave for inválida ou a API não estiver habilitada.
    """
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
