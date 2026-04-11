# modules/embeddings.py
# ─────────────────────────────────────────────────────────────────────────────
# Utilitários de embedding para busca semântica.
#
# Provedores suportados:
#   - Google Gemini: text-embedding-004 (768 dims nativos)
#   - OpenAI: text-embedding-3-small com dimensions=768
#
# Funções públicas:
#   chunk_text(text, chunk_size, overlap) → list[str]
#   embed_text(text, api_key, provider)   → list[float]  (768 dims)
#   embed_batch(texts, api_key, provider) → list[list[float]]
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from typing import List

# ── Dimensão alvo ─────────────────────────────────────────────────────────────
EMBEDDING_DIM = 768

# ── Provedores de embedding suportados ───────────────────────────────────────
EMBEDDING_PROVIDERS = {
    "Google Gemini": {
        "model": "models/text-embedding-004",
        "api_key_label": "Google API Key",
        "api_key_help": "Crie em console.cloud.google.com → APIs → Generative Language API",
        "api_key_prefix": "AI",
    },
    "OpenAI": {
        "model": "text-embedding-3-small",
        "api_key_label": "OpenAI API Key",
        "api_key_help": "Crie em platform.openai.com/api-keys",
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
        return _embed_openai(text, api_key)
    else:
        raise ValueError(f"Provedor de embedding desconhecido: {provider!r}")


def embed_batch(texts: list[str], api_key: str, provider: str) -> list[list[float]]:
    """
    Gera embeddings para uma lista de textos.
    Google Gemini: chamadas individuais (API não suporta batch nativo pelo SDK Python).
    OpenAI: batch nativo.

    Returns:
        Lista de listas de 768 floats, na mesma ordem de `texts`.
    """
    if not texts:
        return []

    if provider == "OpenAI":
        return _embed_batch_openai(texts, api_key)
    else:
        # Fallback: chamadas individuais
        return [embed_text(t, api_key, provider) for t in texts]


# ── Implementações por provedor ───────────────────────────────────────────────

def _embed_gemini(text: str, api_key: str) -> list[float]:
    """Google Generative AI — text-embedding-004 (768 dims)."""
    try:
        import google.generativeai as genai
    except ImportError as exc:
        raise ImportError(
            "Pacote google-generativeai não instalado. "
            "Execute: pip install google-generativeai"
        ) from exc

    genai.configure(api_key=api_key)
    result = genai.embed_content(
        model="models/text-embedding-004",
        content=text,
        task_type="retrieval_document",
    )
    embedding = result["embedding"]
    if len(embedding) != EMBEDDING_DIM:
        raise ValueError(
            f"Embedding Gemini retornou {len(embedding)} dims, esperado {EMBEDDING_DIM}"
        )
    return embedding


def _embed_openai(text: str, api_key: str) -> list[float]:
    """OpenAI — text-embedding-3-small com dimensions=768."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
        dimensions=EMBEDDING_DIM,
    )
    return resp.data[0].embedding


def _embed_batch_openai(texts: list[str], api_key: str) -> list[list[float]]:
    """OpenAI batch embedding — mais eficiente que chamadas individuais."""
    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    resp = client.embeddings.create(
        model="text-embedding-3-small",
        input=texts,
        dimensions=EMBEDDING_DIM,
    )
    # A API retorna embeddings na mesma ordem do input
    return [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]
