# tests/test_api_security.py
# ─────────────────────────────────────────────────────────────────────────────
# Testes das duas camadas de segurança da API comercial (api.py):
#   1. Validação de API Key  (require_api_key)
#   2. Controle de Concorrência / Rate Limiting  (check_rate_limit)
#
# Isolamento completo: Supabase mockado em todos os testes via unittest.mock.
# Não realiza chamadas de rede nem acessa o banco de dados real.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import hashlib
import time
from collections import deque
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import api as api_module
from api import (
    MAX_CONCURRENT_PIPELINES,
    _RATE_MAX_REQUESTS,
    _RATE_WINDOW_SECS,
    _active_pipeline_lock,
    _hash_key,
    app,
)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_rate_state():
    """Reseta estado volátil de concorrência e rate windows entre cada teste."""
    with _active_pipeline_lock:
        api_module._active_pipeline_count = 0
    api_module._key_windows.clear()
    yield
    with _active_pipeline_lock:
        api_module._active_pipeline_count = 0
    api_module._key_windows.clear()


@pytest.fixture()
def client():
    """TestClient síncrono do FastAPI (não sobe servidor real)."""
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def valid_key() -> str:
    return "p2d-test-key-valid-abc123"


@pytest.fixture()
def valid_key_hash(valid_key) -> str:
    return _hash_key(valid_key)


def _make_mock_db(key_hash: str, name: str = "TestClient", is_active: bool = True) -> MagicMock:
    """
    Cria mock de cliente Supabase que retorna uma api_key válida para o hash dado.
    Encadeia .table().select().eq().maybe_single().execute() → resp.data = row.
    """
    mock_resp = MagicMock()
    mock_resp.data = {"name": name, "is_active": is_active}

    # Monta a cadeia de métodos do Supabase fluent API
    mock_execute = MagicMock(return_value=mock_resp)
    mock_maybe_single = MagicMock()
    mock_maybe_single.execute = mock_execute

    mock_eq = MagicMock()
    mock_eq.maybe_single = MagicMock(return_value=mock_maybe_single)

    mock_select = MagicMock()
    mock_select.eq = MagicMock(return_value=mock_eq)

    mock_table = MagicMock()
    mock_table.select = MagicMock(return_value=mock_select)
    mock_table.update = MagicMock(return_value=MagicMock(eq=MagicMock(return_value=MagicMock(execute=MagicMock()))))

    mock_db = MagicMock()
    mock_db.table = MagicMock(return_value=mock_table)
    return mock_db


def _make_mock_db_not_found() -> MagicMock:
    """Mock de DB que retorna key não encontrada (resp.data = None)."""
    mock_resp = MagicMock()
    mock_resp.data = None

    mock_execute = MagicMock(return_value=mock_resp)
    mock_maybe_single = MagicMock()
    mock_maybe_single.execute = mock_execute

    mock_eq = MagicMock()
    mock_eq.maybe_single = MagicMock(return_value=mock_maybe_single)

    mock_select = MagicMock()
    mock_select.eq = MagicMock(return_value=mock_eq)

    mock_table = MagicMock()
    mock_table.select = MagicMock(return_value=mock_select)

    mock_db = MagicMock()
    mock_db.table = MagicMock(return_value=mock_table)
    return mock_db


# ─────────────────────────────────────────────────────────────────────────────
# CAMADA 1 — Testes de Validação de API Key
# ─────────────────────────────────────────────────────────────────────────────

class TestApiKeyValidation:
    """Testes da dependência require_api_key."""

    def test_missing_header_returns_401(self, client):
        """Ausência total do header X-API-Key deve retornar 401."""
        resp = client.get("/health")
        # /health não usa autenticação — garante que o endpoint existe
        assert resp.status_code == 200

        # Um endpoint protegido sem key deve retornar 401
        resp = client.post(
            "/pipeline/run",
            json={"job_id": "fake-job"},
        )
        assert resp.status_code == 401
        assert "X-API-Key" in resp.json()["detail"]

    def test_empty_header_returns_401(self, client):
        """Header X-API-Key com valor vazio deve retornar 401."""
        resp = client.post(
            "/pipeline/run",
            json={"job_id": "fake-job"},
            headers={"X-API-Key": "   "},
        )
        assert resp.status_code == 401

    def test_valid_key_with_supabase_passes(self, client, valid_key, valid_key_hash):
        """Key válida com Supabase disponível e ativa deve passar a validação."""
        mock_db = _make_mock_db(valid_key_hash)
        # Pré-carrega um job para que /pipeline/run não retorne 404
        api_module._JOBS["test-job-ok"] = api_module.JobRecord(
            job_id="test-job-ok",
            result={"_transcript_raw": "x" * 200},
        )

        with patch.object(api_module, "_get_api_supabase", return_value=mock_db):
            resp = client.post(
                "/pipeline/run",
                json={"job_id": "test-job-ok", "provider": "DeepSeek"},
                headers={"X-API-Key": valid_key},
            )
        # 202 (enfileirado) ou 409 (já em execução) — qualquer um confirma que passou a auth
        assert resp.status_code in (202, 409)

    def test_invalid_key_with_supabase_returns_403(self, client):
        """Key não encontrada no banco deve retornar 403."""
        mock_db = _make_mock_db_not_found()
        with patch.object(api_module, "_get_api_supabase", return_value=mock_db):
            resp = client.post(
                "/pipeline/run",
                json={"job_id": "irrelevant"},
                headers={"X-API-Key": "invalid-key-xyz"},
            )
        assert resp.status_code == 403
        assert "inválida" in resp.json()["detail"]

    def test_inactive_key_returns_403(self, client, valid_key, valid_key_hash):
        """Key existente mas is_active=False deve retornar 403."""
        mock_db = _make_mock_db(valid_key_hash, is_active=False)
        with patch.object(api_module, "_get_api_supabase", return_value=mock_db):
            resp = client.post(
                "/pipeline/run",
                json={"job_id": "irrelevant"},
                headers={"X-API-Key": valid_key},
            )
        assert resp.status_code == 403
        assert "revogada" in resp.json()["detail"] or "inativa" in resp.json()["detail"]

    def test_supabase_unavailable_fails_open(self, client, valid_key):
        """Supabase indisponível (None) deve fail-open — request continua (não 401/403)."""
        api_module._JOBS["job-failopen"] = api_module.JobRecord(
            job_id="job-failopen",
            result={"_transcript_raw": "x" * 200},
        )
        with patch.object(api_module, "_get_api_supabase", return_value=None):
            resp = client.post(
                "/pipeline/run",
                json={"job_id": "job-failopen"},
                headers={"X-API-Key": valid_key},
            )
        # Fail-open: auth passa, chega no pipeline (202 ou erro de pipeline, nunca 401/403)
        assert resp.status_code not in (401, 403)

    def test_supabase_db_exception_fails_open(self, client, valid_key):
        """Exceção de DB em tempo de validação deve fail-open."""
        mock_db = MagicMock()
        mock_db.table.side_effect = RuntimeError("connection refused")

        api_module._JOBS["job-dberr"] = api_module.JobRecord(
            job_id="job-dberr",
            result={"_transcript_raw": "x" * 200},
        )
        with patch.object(api_module, "_get_api_supabase", return_value=mock_db):
            resp = client.post(
                "/pipeline/run",
                json={"job_id": "job-dberr"},
                headers={"X-API-Key": valid_key},
            )
        assert resp.status_code not in (401, 403)

    def test_raw_key_not_in_logs(self, caplog, client, valid_key, valid_key_hash):
        """A raw key NUNCA deve aparecer nos logs — apenas prefixo do hash."""
        import logging

        mock_db = _make_mock_db(valid_key_hash)
        with patch.object(api_module, "_get_api_supabase", return_value=mock_db):
            with caplog.at_level(logging.DEBUG, logger="api"):
                client.post(
                    "/pipeline/run",
                    json={"job_id": "nonexistent-job"},
                    headers={"X-API-Key": valid_key},
                )

        all_logs = " ".join(caplog.messages)
        assert valid_key not in all_logs, "Raw API key encontrada nos logs — violação de segurança!"

    def test_hash_function_deterministic(self):
        """_hash_key deve ser determinístico e produzir SHA-256 hex (64 chars)."""
        key = "minha-chave-secreta"
        h1 = _hash_key(key)
        h2 = _hash_key(key)
        assert h1 == h2
        assert len(h1) == 64
        assert h1 == hashlib.sha256(key.encode()).hexdigest()

    def test_different_keys_produce_different_hashes(self):
        """Chaves diferentes devem produzir hashes diferentes."""
        assert _hash_key("key-a") != _hash_key("key-b")


# ─────────────────────────────────────────────────────────────────────────────
# CAMADA 2 — Testes de Controle de Concorrência / Rate Limiting
# ─────────────────────────────────────────────────────────────────────────────

class TestConcurrencyControl:
    """Testes do cap global de concorrência (_active_pipeline_count)."""

    def _run_with_db(self, client, job_id: str, mock_db: Any, key: str = "test-key-cc"):
        return client.post(
            "/pipeline/run",
            json={"job_id": job_id, "provider": "DeepSeek"},
            headers={"X-API-Key": key},
        )

    def _make_job(self, job_id: str):
        api_module._JOBS[job_id] = api_module.JobRecord(
            job_id=job_id,
            result={"_transcript_raw": "x" * 200},
        )

    def test_first_request_passes_when_below_limit(self, client, valid_key, valid_key_hash):
        """Primeiro request passa quando contador de pipelines está zerado."""
        self._make_job("cc-job-1")
        mock_db = _make_mock_db(valid_key_hash)
        with patch.object(api_module, "_get_api_supabase", return_value=mock_db):
            resp = self._run_with_db(client, "cc-job-1", mock_db, valid_key)
        assert resp.status_code != 429

    def test_request_rejected_when_at_capacity(self, client, valid_key, valid_key_hash):
        """Request deve receber 429 quando _active_pipeline_count >= MAX_CONCURRENT_PIPELINES."""
        # Simula servidor saturado sem usar threads reais
        with _active_pipeline_lock:
            api_module._active_pipeline_count = MAX_CONCURRENT_PIPELINES

        self._make_job("cc-job-saturated")
        mock_db = _make_mock_db(valid_key_hash)
        with patch.object(api_module, "_get_api_supabase", return_value=mock_db):
            resp = self._run_with_db(client, "cc-job-saturated", mock_db, valid_key)

        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    def test_request_passes_after_capacity_freed(self, client, valid_key, valid_key_hash):
        """Após liberar uma slot, próximo request deve passar."""
        with _active_pipeline_lock:
            api_module._active_pipeline_count = MAX_CONCURRENT_PIPELINES - 1

        self._make_job("cc-job-free")
        mock_db = _make_mock_db(valid_key_hash)
        with patch.object(api_module, "_get_api_supabase", return_value=mock_db):
            resp = self._run_with_db(client, "cc-job-free", mock_db, valid_key)

        assert resp.status_code != 429

    def test_counter_decrements_on_pipeline_error(self):
        """_active_pipeline_count deve ser decrementado mesmo se o pipeline falhar."""
        with _active_pipeline_lock:
            api_module._active_pipeline_count = 0

        config = api_module.PipelineConfig(job_id="crash-job", provider="DeepSeek")
        api_module._JOBS["crash-job"] = api_module.JobRecord(job_id="crash-job")

        # Chama diretamente o worker — vai falhar (KnowledgeHub não está disponível
        # sem o ambiente completo), mas o finally deve garantir que o contador volta a 0.
        api_module._run_pipeline_sync("crash-job", "transcript text", config, "hash")

        with _active_pipeline_lock:
            # Independente de erro no pipeline, o contador deve ser 0 após o finally
            assert api_module._active_pipeline_count == 0

    def test_counter_never_goes_below_zero(self):
        """Salvaguarda: o contador não deve ficar negativo por decrementos extras."""
        with _active_pipeline_lock:
            api_module._active_pipeline_count = 0

        config = api_module.PipelineConfig(job_id="z", provider="DeepSeek")
        api_module._JOBS["neg-job"] = api_module.JobRecord(job_id="neg-job")

        api_module._run_pipeline_sync("neg-job", "transcript text", config, "hash")

        with _active_pipeline_lock:
            assert api_module._active_pipeline_count >= 0


class TestRateLimiting:
    """Testes da sliding window por key."""

    def _make_job(self, job_id: str):
        api_module._JOBS[job_id] = api_module.JobRecord(
            job_id=job_id,
            result={"_transcript_raw": "x" * 200},
        )

    def test_first_requests_within_limit_pass(self, client, valid_key, valid_key_hash):
        """Primeiros N requests abaixo do limite devem passar."""
        mock_db = _make_mock_db(valid_key_hash)

        for i in range(3):
            job_id = f"rl-ok-{i}"
            self._make_job(job_id)
            with patch.object(api_module, "_get_api_supabase", return_value=mock_db):
                resp = client.post(
                    "/pipeline/run",
                    json={"job_id": job_id},
                    headers={"X-API-Key": valid_key},
                )
            assert resp.status_code != 429, f"Request {i} não deveria ter sido bloqueado"

    def test_exceeding_window_returns_429(self, client, valid_key, valid_key_hash):
        """Ao exceder _RATE_MAX_REQUESTS na janela, deve retornar 429."""
        key_hash = valid_key_hash
        now = time.monotonic()

        # Preenche a janela com timestamps recentes manualmente
        with api_module._key_windows_lock:
            api_module._key_windows[key_hash] = deque(
                [now - 1.0] * _RATE_MAX_REQUESTS
            )

        self._make_job("rl-exceeded")
        mock_db = _make_mock_db(valid_key_hash)
        with patch.object(api_module, "_get_api_supabase", return_value=mock_db):
            resp = client.post(
                "/pipeline/run",
                json={"job_id": "rl-exceeded"},
                headers={"X-API-Key": valid_key},
            )

        assert resp.status_code == 429
        body = resp.json()
        assert "Retry-After" in resp.headers
        assert str(_RATE_MAX_REQUESTS) in body["detail"]

    def test_expired_timestamps_are_evicted(self, client, valid_key, valid_key_hash):
        """Timestamps fora da janela devem ser ignorados — requests velhos não bloqueiam."""
        key_hash = valid_key_hash
        old_time = time.monotonic() - _RATE_WINDOW_SECS - 5  # já expirado

        with api_module._key_windows_lock:
            # Preenche com timestamps antigos (expirados)
            api_module._key_windows[key_hash] = deque(
                [old_time] * _RATE_MAX_REQUESTS
            )

        self._make_job("rl-expired")
        mock_db = _make_mock_db(valid_key_hash)
        with patch.object(api_module, "_get_api_supabase", return_value=mock_db):
            resp = client.post(
                "/pipeline/run",
                json={"job_id": "rl-expired"},
                headers={"X-API-Key": valid_key},
            )

        # Timestamps expirados → janela limpa → request não bloqueado pelo rate limit
        assert resp.status_code != 429

    def test_different_keys_have_independent_windows(self, client, valid_key_hash):
        """Keys diferentes devem ter janelas de rate limit independentes."""
        key_a = "key-alpha-distinct"
        key_b = "key-beta-distinct"
        hash_a = _hash_key(key_a)
        hash_b = _hash_key(key_b)
        now = time.monotonic()

        # Satura a janela de key_a
        with api_module._key_windows_lock:
            api_module._key_windows[hash_a] = deque([now - 1.0] * _RATE_MAX_REQUESTS)

        # key_b deve ainda passar
        self._make_job("rl-keyb-job")
        mock_db_b = _make_mock_db(hash_b, name="ClientB")
        with patch.object(api_module, "_get_api_supabase", return_value=mock_db_b):
            resp = client.post(
                "/pipeline/run",
                json={"job_id": "rl-keyb-job"},
                headers={"X-API-Key": key_b},
            )

        assert resp.status_code != 429

    def test_retry_after_header_present_on_rate_limit(self, client, valid_key, valid_key_hash):
        """Response 429 deve incluir header Retry-After."""
        key_hash = valid_key_hash
        now = time.monotonic()

        with api_module._key_windows_lock:
            api_module._key_windows[key_hash] = deque([now - 1.0] * _RATE_MAX_REQUESTS)

        self._make_job("rl-retry-after")
        mock_db = _make_mock_db(valid_key_hash)
        with patch.object(api_module, "_get_api_supabase", return_value=mock_db):
            resp = client.post(
                "/pipeline/run",
                json={"job_id": "rl-retry-after"},
                headers={"X-API-Key": valid_key},
            )

        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        assert int(resp.headers["Retry-After"]) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Testes de integração leve (camadas combinadas)
# ─────────────────────────────────────────────────────────────────────────────

class TestSecurityIntegration:
    """Testes que exercitam as duas camadas juntas."""

    def test_health_endpoint_unauthenticated(self, client):
        """/health não requer autenticação e deve responder 200."""
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "active_pipelines" in data
        assert "max_pipelines" in data

    def test_both_layers_block_independently(self, client, valid_key, valid_key_hash):
        """
        Cenário: key válida mas servidor saturado → 429 (layer 2 bloqueia antes do pipeline).
        Demonstra que as camadas são compostas (require_api_key → check_rate_limit).
        """
        mock_db = _make_mock_db(valid_key_hash)
        with _active_pipeline_lock:
            api_module._active_pipeline_count = MAX_CONCURRENT_PIPELINES

        api_module._JOBS["integration-sat"] = api_module.JobRecord(
            job_id="integration-sat",
            result={"_transcript_raw": "x" * 200},
        )

        with patch.object(api_module, "_get_api_supabase", return_value=mock_db):
            resp = client.post(
                "/pipeline/run",
                json={"job_id": "integration-sat"},
                headers={"X-API-Key": valid_key},
            )

        # Key válida mas servidor cheio → 429 (não 401/403)
        assert resp.status_code == 429

    def test_no_key_blocked_before_rate_limit_check(self, client):
        """
        Sem X-API-Key, o bloqueio ocorre na camada 1 (401) sem chegar na camada 2.
        O contador de pipelines não deve ser alterado.
        """
        with _active_pipeline_lock:
            before = api_module._active_pipeline_count

        client.post("/pipeline/run", json={"job_id": "x"})

        with _active_pipeline_lock:
            after = api_module._active_pipeline_count

        assert before == after, "Contador alterado mesmo sem autenticação"

    def test_upload_then_run_flow(self, client, valid_key, valid_key_hash):
        """Fluxo upload → run: /upload cria job, /pipeline/run autentica e enfileira."""
        long_text = "Esta é uma transcrição longa " * 10  # >50 chars

        # Step 1: upload sem autenticação (text enviado como form field via Form())
        resp = client.post("/upload", data={"text": long_text})
        assert resp.status_code == 202
        job_id = resp.json()["job_id"]
        assert len(job_id) == 36  # UUID v4

        # Step 2: run com autenticação
        mock_db = _make_mock_db(valid_key_hash)
        with patch.object(api_module, "_get_api_supabase", return_value=mock_db):
            resp2 = client.post(
                "/pipeline/run",
                json={"job_id": job_id, "provider": "DeepSeek"},
                headers={"X-API-Key": valid_key},
            )

        # 202 = enfileirado com sucesso
        assert resp2.status_code == 202
        assert resp2.json()["job_id"] == job_id

    def test_status_endpoint_reflects_job_state(self, client):
        """/status/{job_id} retorna estado correto para job existente."""
        api_module._JOBS["status-test"] = api_module.JobRecord(
            job_id="status-test",
            status=api_module.JobStatus.RUNNING,
            progress=42,
        )
        resp = client.get("/status/status-test")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["progress"] == 42
        assert data["result"] is None  # só exposto quando DONE

    def test_status_endpoint_nonexistent_job_returns_404(self, client):
        resp = client.get("/status/nonexistent-uuid")
        assert resp.status_code == 404
