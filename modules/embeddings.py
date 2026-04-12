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
# Gemini embeddings usam o endpoint OpenAI-compatível do Google (v1beta/openai/).
# Nenhum SDK extra necessário — mesmo pacote openai já instalado.
#
# Funções públicas:
#   chunk_text(text, chunk_size, overlap) → list[str]
#   embed_text(text, api_key, provider)   → list[float]  (768 dims)
#   embed_batch(texts, api_key, provider) → list[list[float]]
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

# ── Dimensão alvo ─────────────────────────────────────────────────────────────
EMBEDDING_DIM = 768

# ── Provedores de embedding suportados ───────────────────────────────────────
EMBEDDING_PROVIDERS = {
    "Google Gemini": {
        "model":         "models/text-embedding-004",
        "base_url":      None,
        "api_key_label": "Google API Key",
        "api_key_help":  "Crie em console.cloud.google.com → APIs → Generative Language API. Tier gratuito disponível.",
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


def _embed_gemini(text: str, api_key: str) -> list[float]:
    """Google Gemini embeddings via google-genai SDK forçando endpoint v1 (estável).

    O SDK usa v1beta por padrão, mas os modelos de embedding requerem v1.
    http_options={"api_version": "v1"} replica o que LangChain faz com version="v1".

    Tenta text-embedding-004 primeiro (mais recente, 768 dims) e faz fallback
    para embedding-001 (estável, 768 dims) se o modelo não estiver disponível.
    """
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError as exc:
        raise ImportError(
            "Pacote google-genai não instalado. "
            "Execute: pip install google-genai"
        ) from exc

    client = genai.Client(
        api_key=api_key,
        http_options={"api_version": "v1"},  # força endpoint estável (não v1beta)
    )

    for model_name in ("text-embedding-004", "embedding-001"):
        try:
            result = client.models.embed_content(
                model=model_name,
                contents=text,
                config=genai_types.EmbedContentConfig(task_type="RETRIEVAL_DOCUMENT"),
            )
            embedding = list(result.embeddings[0].values)
            if len(embedding) != EMBEDDING_DIM:
                raise ValueError(
                    f"Embedding {model_name} retornou {len(embedding)} dims, "
                    f"esperado {EMBEDDING_DIM}"
                )
            return embedding
        except Exception as exc:
            if "404" in str(exc) and model_name == "text-embedding-004":
                continue  # tenta fallback
            raise

    raise RuntimeError(
        "Nenhum modelo Gemini disponível (text-embedding-004 e embedding-001 falharam). "
        "Verifique se a chave foi criada em aistudio.google.com e se a "
        "'Generative Language API' está habilitada."
    )


def _embed_batch_gemini(texts: list[str], api_key: str) -> list[list[float]]:
    """Batch: chama _embed_gemini individualmente."""
    return [_embed_gemini(t, api_key) for t in texts]
