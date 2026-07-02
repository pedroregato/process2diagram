# services/cloud_tasks.py
# ─────────────────────────────────────────────────────────────────────────────
# Cloud Tasks — fila distribuída de pipelines com fallback síncrono.
#
# Detecção de modo (automática via env var):
#   CLOUD_TASKS_QUEUE definido → CloudTasksMode.CLOUD_TASKS  (distribuído, durável)
#   Não definido              → CloudTasksMode.SYNC_FALLBACK (ThreadPoolExecutor local)
#
# Ambos os modos respeitam MAX_CONCURRENT_PIPELINES (padrão: 4).
#
# Fail-Open (ENGINEERING_MANIFESTO §2):
#   Qualquer erro no Cloud Tasks → fallback automático para SYNC_FALLBACK.
#   Nunca bloqueia o caller por falha de infraestrutura GCP.
#
# Isolamento de estado (ENGINEERING_MANIFESTO §3):
#   SYNC_FALLBACK: _active_count rastreado por instância (threading.Lock)
#   CLOUD_TASKS:   Cloud Tasks gerencia concurrency limit globalmente
#                  → containerConcurrency=4 no service.yaml garante isolamento
#
# Fase 2 (migração futura):
#   - _JOBS dict em memória → Firestore/Supabase (durable, cross-instance)
#   - _active_count local → Cloud Tasks queue concurrency config
#   - threading.Lock → eliminado completamente
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import logging
import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Máximo de pipelines simultâneos — lido de env para permitir override no Cloud Run
MAX_CONCURRENT_PIPELINES: int = int(os.environ.get("MAX_CONCURRENT_PIPELINES", "4"))


# ── Modo de execução ──────────────────────────────────────────────────────────

class CloudTasksMode(str, Enum):
    CLOUD_TASKS   = "cloud_tasks"
    SYNC_FALLBACK = "sync_fallback"


def _detect_mode() -> CloudTasksMode:
    """
    Auto-detecta modo baseado na presença de CLOUD_TASKS_QUEUE.
    Chamada a cada enqueue (permite mudança de config sem reiniciar).
    """
    return (
        CloudTasksMode.CLOUD_TASKS
        if os.environ.get("CLOUD_TASKS_QUEUE", "").strip()
        else CloudTasksMode.SYNC_FALLBACK
    )


# ── Sync fallback — ThreadPoolExecutor local ──────────────────────────────────

_EXECUTOR = ThreadPoolExecutor(
    max_workers=MAX_CONCURRENT_PIPELINES,
    thread_name_prefix="p2d_ct_fallback",
)
_active_count: int = 0
_active_lock  = threading.Lock()


def _wrap_sync(fn: Callable, *args: Any) -> None:
    """
    Executa fn(*args) rastreando _active_count.
    Garante decremento no finally (mesmo em erro).
    """
    global _active_count
    with _active_lock:
        _active_count += 1
    try:
        fn(*args)
    finally:
        with _active_lock:
            _active_count = max(0, _active_count - 1)


def _can_accept() -> bool:
    """True se ainda há capacidade para mais pipelines no fallback síncrono."""
    with _active_lock:
        return _active_count < MAX_CONCURRENT_PIPELINES


def active_pipeline_count() -> int:
    """Número atual de pipelines ativos no modo fallback síncrono."""
    with _active_lock:
        return _active_count


# ── Cloud Tasks enqueue ────────────────────────────────────────────────────────

def _enqueue_cloud_tasks(
    worker_url:      str,
    job_id:          str,
    payload:         dict,
    service_account: Optional[str],
) -> str:
    """
    Cria uma task HTTP no Cloud Tasks apontando para o worker_url.
    Retorna o nome da task em sucesso.
    Levanta Exception em qualquer falha (caller faz fallback).

    Configuração da fila (gcloud CLI — executar uma vez):
        gcloud tasks queues create p2d-pipeline-queue \\
          --location=us-central1 \\
          --max-dispatches-per-second=4 \\
          --max-concurrent-dispatches=4 \\
          --max-attempts=3 \\
          --min-backoff=10s \\
          --max-backoff=300s
    """
    from google.cloud import tasks_v2  # type: ignore

    queue    = os.environ["CLOUD_TASKS_QUEUE"]
    location = os.environ.get("CLOUD_TASKS_LOCATION", "us-central1")
    project  = (
        os.environ.get("GCP_PROJECT_ID")
        or os.environ.get("GOOGLE_CLOUD_PROJECT")
        or ""
    )
    if not project:
        raise ValueError("GCP_PROJECT_ID não definido — não é possível criar task no Cloud Tasks")
    if not worker_url:
        raise ValueError("WORKER_URL não definido — não é possível criar task HTTP no Cloud Tasks")

    client     = tasks_v2.CloudTasksClient()
    queue_path = client.queue_path(project, location, queue)

    body_bytes = json.dumps({"job_id": job_id, **payload}).encode("utf-8")

    # Limite de payload do Cloud Tasks: 100 KB
    if len(body_bytes) > 98_000:
        raise ValueError(
            f"Payload da task ({len(body_bytes)} bytes) excede 100 KB — "
            "use sync_fallback ou pré-persista a transcrição no Supabase"
        )

    task: dict[str, Any] = {
        "http_request": {
            "http_method": tasks_v2.HttpMethod.POST,
            "url": f"{worker_url.rstrip('/')}/internal/run",
            "headers": {"Content-Type": "application/json"},
            "body": body_bytes,
        }
    }
    if service_account:
        task["http_request"]["oidc_token"] = {
            "service_account_email": service_account,
        }

    response = client.create_task(parent=queue_path, task=task)
    logger.info(
        "cloud_tasks: task criada — job_id=%s task=%s", job_id, response.name
    )
    return response.name


# ── API pública ───────────────────────────────────────────────────────────────

def enqueue_pipeline(
    job_id:              str,
    sync_fn:             Callable,
    sync_args:           tuple = (),
    *,
    cloud_tasks_payload: Optional[dict] = None,
    worker_url:          Optional[str]  = None,
    service_account:     Optional[str]  = None,
) -> CloudTasksMode:
    """
    Enfileira um job de pipeline.

    Lógica de decisão:
    1. Se CLOUD_TASKS_QUEUE definido e payload/worker_url fornecidos
       → tenta Cloud Tasks; Fail-Open: qualquer erro → SYNC_FALLBACK
    2. SYNC_FALLBACK: submete sync_fn(*sync_args) ao ThreadPoolExecutor local
       → levanta HTTP 429 se _active_count >= MAX_CONCURRENT_PIPELINES

    Args:
        job_id:              Identificador do job (para logging e task name).
        sync_fn:             Callable a executar no fallback síncrono.
        sync_args:           Args para sync_fn (passados como *args).
        cloud_tasks_payload: Payload JSON para o worker via Cloud Tasks.
        worker_url:          URL do endpoint /internal/run do Cloud Run worker.
        service_account:     E-mail da service account para OIDC (Cloud Tasks → Cloud Run).

    Returns:
        CloudTasksMode indicando qual modo foi efetivamente usado.

    Raises:
        HTTPException(429): somente no fallback síncrono ao atingir MAX_CONCURRENT_PIPELINES.
    """
    # Evita import circular — FastAPI/HTTPException importado late
    from fastapi import HTTPException, status as http_status  # noqa: F401

    mode = _detect_mode()

    # ── Tenta Cloud Tasks ─────────────────────────────────────────────────────
    if (
        mode == CloudTasksMode.CLOUD_TASKS
        and cloud_tasks_payload is not None
        and worker_url
    ):
        try:
            _enqueue_cloud_tasks(
                worker_url,
                job_id,
                cloud_tasks_payload,
                service_account,
            )
            return CloudTasksMode.CLOUD_TASKS
        except ImportError:
            logger.warning(
                "enqueue_pipeline: google-cloud-tasks não instalado — sync_fallback (job=%s)",
                job_id,
            )
        except Exception as exc:
            logger.warning(
                "enqueue_pipeline: Cloud Tasks falhou (%s) — sync_fallback (job=%s)",
                exc, job_id,
            )
        # Continua para SYNC_FALLBACK

    # ── Fallback síncrono (ThreadPoolExecutor) ────────────────────────────────
    if not _can_accept():
        raise HTTPException(
            status_code=http_status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Servidor no limite de {MAX_CONCURRENT_PIPELINES} pipelines simultâneos. "
                "Tente novamente em instantes."
            ),
            headers={"Retry-After": "10"},
        )

    _EXECUTOR.submit(_wrap_sync, sync_fn, *sync_args)
    logger.info("enqueue_pipeline: sync_fallback — job_id=%s", job_id)
    return CloudTasksMode.SYNC_FALLBACK
