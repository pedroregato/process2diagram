# services/secret_manager.py
# ─────────────────────────────────────────────────────────────────────────────
# Secret resolution — 4 camadas, Fail-Open.
#
# Ordem de resolução por get_secret(name):
#   1. Google Cloud Secret Manager  (produção GCP — GCP_PROJECT_ID detectado)
#   2. Variáveis de ambiente        (Cloud Run auto-injected / docker --env-file)
#   3. Streamlit secrets            (st.secrets — dev/staging Streamlit Cloud)
#   4. None                         (Fail-Open — caller decide; nunca levanta exceção)
#
# Princípio Fail-Open (ENGINEERING_MANIFESTO §2):
#   Nenhuma camada bloqueia a operação. Falha silenciosa + log warning na Camada 4.
#
# Uso:
#   from services.secret_manager import get_secret, get_secret_required
#   api_key = get_secret("DEEPSEEK_API_KEY")   # None se não encontrado
#   url     = get_secret_required("SUPABASE_URL")  # ValueError se ausente
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)


# ── Detecção do projeto GCP ───────────────────────────────────────────────────

def _gcp_project_id() -> Optional[str]:
    """Resolve GCP project ID a partir de env vars padrão do Cloud Run."""
    return (
        os.environ.get("GCP_PROJECT_ID")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or os.environ.get("GCLOUD_PROJECT")
    )


# ── Camada 1: Google Cloud Secret Manager ─────────────────────────────────────

@lru_cache(maxsize=128)
def _from_secret_manager(name: str, project_id: str) -> Optional[str]:
    """
    Busca secret no GCP Secret Manager.
    Resultado cacheado por (name, project_id) — evita chamadas repetidas por instância.
    Retorna None em qualquer erro (Fail-Open).
    """
    try:
        from google.cloud import secretmanager  # type: ignore
        client   = secretmanager.SecretManagerServiceClient()
        resource = f"projects/{project_id}/secrets/{name}/versions/latest"
        response = client.access_secret_version(request={"name": resource})
        value    = response.payload.data.decode("utf-8").strip()
        if value:
            logger.debug("get_secret(%s): Camada 1 — Secret Manager (project=%s)", name, project_id)
            return value
        return None
    except ImportError:
        # Pacote google-cloud-secret-manager não instalado (dev sem GCP)
        return None
    except Exception as exc:
        logger.debug("get_secret(%s): Camada 1 — Secret Manager indisponível (%s)", name, exc)
        return None


# ── Camada 2: Variáveis de ambiente ───────────────────────────────────────────

def _from_env(name: str) -> Optional[str]:
    """Tenta nome exato e variante uppercase."""
    value = os.environ.get(name) or os.environ.get(name.upper())
    if value and value.strip():
        logger.debug("get_secret(%s): Camada 2 — env var", name)
        return value.strip()
    return None


# ── Camada 3: Streamlit secrets ───────────────────────────────────────────────

def _from_streamlit(name: str) -> Optional[str]:
    """
    Lê de st.secrets se disponível (Streamlit Cloud dev/staging).
    Completamente Fail-Open: se Streamlit não estiver rodando, retorna None silenciosamente.
    Suporta chave plana ("DEEPSEEK_API_KEY") e notação de seção ("supabase.url").
    """
    try:
        import streamlit as st  # type: ignore
        # Chave plana
        if name in st.secrets:
            val = str(st.secrets[name]).strip()
            if val:
                logger.debug("get_secret(%s): Camada 3 — st.secrets (flat)", name)
                return val
        # Notação seção.chave (ex: "supabase.url" → st.secrets["supabase"]["url"])
        parts = name.lower().replace("-", "_").split(".", 1)
        if len(parts) == 2:
            section, key = parts
            try:
                val = str(st.secrets[section][key]).strip()
                if val:
                    logger.debug("get_secret(%s): Camada 3 — st.secrets[%s][%s]", name, section, key)
                    return val
            except (KeyError, TypeError):
                pass
        return None
    except Exception:
        return None


# ── API pública ───────────────────────────────────────────────────────────────

def get_secret(name: str, *, project_id: Optional[str] = None) -> Optional[str]:
    """
    Resolve um secret usando fallback de 4 camadas (Fail-Open).

    Args:
        name:       Nome do secret. Usado como nome no Secret Manager E como nome de env var.
        project_id: Project ID GCP (override). Usa GCP_PROJECT_ID/GOOGLE_CLOUD_PROJECT por padrão.

    Returns:
        Valor do secret como string, ou None se não encontrado em nenhuma camada.
        Nunca levanta exceção (Fail-Open — ENGINEERING_MANIFESTO §2).
    """
    pid = project_id or _gcp_project_id()

    # Camada 1 — Secret Manager (apenas se project_id conhecido)
    if pid:
        value = _from_secret_manager(name, pid)
        if value:
            return value

    # Camada 2 — Env vars
    value = _from_env(name)
    if value:
        return value

    # Camada 3 — Streamlit secrets
    value = _from_streamlit(name)
    if value:
        return value

    # Camada 4 — None (Fail-Open)
    logger.warning(
        "get_secret(%s): não encontrado em nenhuma camada "
        "(Secret Manager / env var / Streamlit secrets) — retornando None (fail-open)",
        name,
    )
    return None


def get_secret_required(name: str, *, project_id: Optional[str] = None) -> str:
    """
    Como get_secret(), mas levanta ValueError se não encontrado.
    Usar apenas na inicialização para configs verdadeiramente obrigatórias.
    """
    value = get_secret(name, project_id=project_id)
    if not value:
        raise ValueError(
            f"Secret obrigatório '{name}' não encontrado em nenhuma camada "
            f"(Secret Manager / env var / st.secrets)."
        )
    return value


def invalidate_cache(name: Optional[str] = None) -> None:
    """
    Invalida o cache do Secret Manager (útil em testes ou após rotação de secrets).
    Se name=None, invalida todo o cache.
    """
    if name is None:
        _from_secret_manager.cache_clear()
    else:
        # lru_cache não suporta invalidação por chave — limpa tudo
        _from_secret_manager.cache_clear()
