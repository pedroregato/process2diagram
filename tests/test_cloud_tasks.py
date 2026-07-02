# tests/test_cloud_tasks.py
# ─────────────────────────────────────────────────────────────────────────────
# Suite de testes para services/cloud_tasks.py
# 10 testes — zero dependências de rede (Cloud Tasks client mockado via patch).
# ─────────────────────────────────────────────────────────────────────────────

import os
import threading
import time
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_state():
    """Reseta _active_count entre testes."""
    import services.cloud_tasks as ct
    with ct._active_lock:
        ct._active_count = 0
    yield
    with ct._active_lock:
        ct._active_count = 0


# ── Detecção de modo ──────────────────────────────────────────────────────────

def test_detect_mode_sync_fallback_when_no_env(monkeypatch):
    """Sem CLOUD_TASKS_QUEUE → SYNC_FALLBACK."""
    monkeypatch.delenv("CLOUD_TASKS_QUEUE", raising=False)
    from services.cloud_tasks import _detect_mode, CloudTasksMode
    assert _detect_mode() == CloudTasksMode.SYNC_FALLBACK


def test_detect_mode_cloud_tasks_when_env_set(monkeypatch):
    """Com CLOUD_TASKS_QUEUE definido → CLOUD_TASKS."""
    monkeypatch.setenv("CLOUD_TASKS_QUEUE", "my-queue")
    from services.cloud_tasks import _detect_mode, CloudTasksMode
    assert _detect_mode() == CloudTasksMode.CLOUD_TASKS


# ── Controle de concorrência ──────────────────────────────────────────────────

def test_active_pipeline_count_starts_at_zero():
    """active_pipeline_count() deve iniciar em 0."""
    from services.cloud_tasks import active_pipeline_count
    assert active_pipeline_count() == 0


def test_wrap_sync_increments_and_decrements():
    """_wrap_sync incrementa durante execução e decrementa no finally."""
    import services.cloud_tasks as ct
    counts_during = []

    def _spy_fn():
        counts_during.append(ct._active_count)

    ct._wrap_sync(_spy_fn)
    assert counts_during == [1]        # 1 durante execução
    assert ct._active_count == 0      # 0 após término


def test_wrap_sync_decrements_on_exception():
    """_wrap_sync sempre decrementa mesmo quando fn lança exceção."""
    import services.cloud_tasks as ct

    def _boom():
        raise RuntimeError("deliberate error")

    try:
        ct._wrap_sync(_boom)
    except Exception:
        pass  # a exceção é propagada — comportamento esperado

    assert ct._active_count == 0


def test_can_accept_true_below_limit(monkeypatch):
    """_can_accept() retorna True quando abaixo do limite."""
    monkeypatch.setenv("MAX_CONCURRENT_PIPELINES", "4")
    import services.cloud_tasks as ct
    with ct._active_lock:
        ct._active_count = 3
    assert ct._can_accept() is True


def test_can_accept_false_at_limit(monkeypatch):
    """_can_accept() retorna False ao atingir MAX_CONCURRENT_PIPELINES."""
    import services.cloud_tasks as ct
    with ct._active_lock:
        ct._active_count = ct.MAX_CONCURRENT_PIPELINES
    assert ct._can_accept() is False


# ── enqueue_pipeline ──────────────────────────────────────────────────────────

def test_enqueue_pipeline_sync_fallback(monkeypatch):
    """enqueue_pipeline usa SYNC_FALLBACK quando CLOUD_TASKS_QUEUE ausente."""
    monkeypatch.delenv("CLOUD_TASKS_QUEUE", raising=False)
    from services.cloud_tasks import enqueue_pipeline, CloudTasksMode

    executed = []

    def _fn(x):
        executed.append(x)

    result = enqueue_pipeline("job-1", _fn, (42,))
    # Aguarda thread terminar
    time.sleep(0.2)

    assert result == CloudTasksMode.SYNC_FALLBACK
    assert executed == [42]


def test_enqueue_pipeline_raises_429_at_capacity(monkeypatch):
    """enqueue_pipeline levanta HTTP 429 quando no limite de concorrência."""
    monkeypatch.delenv("CLOUD_TASKS_QUEUE", raising=False)
    import services.cloud_tasks as ct
    from fastapi import HTTPException

    with ct._active_lock:
        ct._active_count = ct.MAX_CONCURRENT_PIPELINES

    with pytest.raises(HTTPException) as exc_info:
        ct.enqueue_pipeline("job-overflow", lambda: None)

    assert exc_info.value.status_code == 429


def test_enqueue_pipeline_cloud_tasks_fallback_on_error(monkeypatch):
    """enqueue_pipeline faz fallback para SYNC_FALLBACK quando Cloud Tasks falha."""
    monkeypatch.setenv("CLOUD_TASKS_QUEUE", "my-queue")
    monkeypatch.setenv("GCP_PROJECT_ID", "my-project")
    monkeypatch.setenv("WORKER_URL", "https://worker.example.com")

    executed = []

    def _fn():
        executed.append(True)

    # Simula falha no Cloud Tasks client
    with patch("services.cloud_tasks._enqueue_cloud_tasks", side_effect=Exception("GCP error")):
        from services.cloud_tasks import enqueue_pipeline, CloudTasksMode
        result = enqueue_pipeline(
            "job-ct-fail",
            _fn,
            cloud_tasks_payload={"key": "value"},
            worker_url="https://worker.example.com",
        )

    time.sleep(0.2)
    assert result == CloudTasksMode.SYNC_FALLBACK
    assert executed == [True]
