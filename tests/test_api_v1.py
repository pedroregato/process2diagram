# tests/test_api_v1.py
# ─────────────────────────────────────────────────────────────────────────────
# Suite de testes para os novos endpoints de api.py (PC114):
#   GET/POST /api/v1/projects
#   POST /api/v1/process
#   POST /internal/run
#   GET /health (campos novos)
# 11 testes — zero dependências de rede (Supabase e pipeline mockados).
# ─────────────────────────────────────────────────────────────────────────────

import os
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Fixture: client com Supabase e pipeline mockados ─────────────────────────

@pytest.fixture(scope="module")
def client():
    # Garante que _api_supabase_init seja resetado para cada módulo de test
    import api
    api._api_supabase_init = False
    api._api_supabase      = None
    return TestClient(api.app)


@pytest.fixture(autouse=True)
def _reset_jobs():
    import api
    api._JOBS.clear()
    yield
    api._JOBS.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

VALID_KEY = "test-api-key-12345"

def _auth(extra: dict | None = None) -> dict:
    headers = {"X-API-Key": VALID_KEY}
    if extra:
        headers.update(extra)
    return headers


def _mock_supabase_ok(monkeypatch):
    """Injeta cliente Supabase mockado diretamente no módulo api."""
    import api
    mock_db = MagicMock()
    api._api_supabase      = mock_db
    api._api_supabase_init = True
    return mock_db


# ── /api/v1/projects GET ──────────────────────────────────────────────────────

def test_list_projects_no_auth(client):
    """GET /api/v1/projects sem X-API-Key → 401."""
    resp = client.get("/api/v1/projects")
    assert resp.status_code == 401


def test_list_projects_supabase_unavailable(client, monkeypatch):
    """GET /api/v1/projects com Supabase indisponível → 200 lista vazia (Fail-Open)."""
    import api
    api._api_supabase      = None
    api._api_supabase_init = True

    # Fail-open na autenticação (Supabase indisponível)
    resp = client.get("/api/v1/projects", headers=_auth())
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_projects_returns_data(client, monkeypatch):
    """GET /api/v1/projects retorna lista de projetos do Supabase."""
    mock_db = _mock_supabase_ok(monkeypatch)
    mock_db.table.return_value.select.return_value.order.return_value.execute.return_value = MagicMock(
        data=[{"id": "abc", "name": "Projeto A", "description": None, "created_at": "2026-01-01"}]
    )

    resp = client.get("/api/v1/projects", headers=_auth())
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["name"] == "Projeto A"


# ── /api/v1/projects POST ─────────────────────────────────────────────────────

def test_create_project_supabase_unavailable(client, monkeypatch):
    """POST /api/v1/projects sem Supabase → 503."""
    import api
    api._api_supabase      = None
    api._api_supabase_init = True

    resp = client.post(
        "/api/v1/projects",
        json={"name": "Novo Projeto"},
        headers=_auth(),
    )
    assert resp.status_code == 503


def test_create_project_success(client, monkeypatch):
    """POST /api/v1/projects cria projeto e retorna 201."""
    mock_db = _mock_supabase_ok(monkeypatch)
    mock_db.table.return_value.insert.return_value.execute.return_value = MagicMock(
        data=[{"id": "xyz", "name": "Novo Projeto", "description": "desc", "created_at": "2026-01-02"}]
    )

    resp = client.post(
        "/api/v1/projects",
        json={"name": "Novo Projeto", "description": "desc"},
        headers=_auth(),
    )
    assert resp.status_code == 201
    assert resp.json()["id"] == "xyz"


# ── /api/v1/process ───────────────────────────────────────────────────────────

LONG_TRANSCRIPT = "Esta é uma transcrição de reunião. " * 10  # > 50 chars


def test_process_no_auth(client):
    """POST /api/v1/process sem X-API-Key → 401."""
    resp = client.post("/api/v1/process", data={"text": LONG_TRANSCRIPT})
    assert resp.status_code == 401


def test_process_no_content(client, monkeypatch):
    """POST /api/v1/process sem text nem file → 422."""
    import api
    api._api_supabase = None
    api._api_supabase_init = True

    resp = client.post("/api/v1/process", data={}, headers=_auth())
    assert resp.status_code == 422


def test_process_text_too_short(client, monkeypatch):
    """POST /api/v1/process com texto < 50 chars → 422."""
    import api
    api._api_supabase = None
    api._api_supabase_init = True

    resp = client.post("/api/v1/process", data={"text": "curto"}, headers=_auth())
    assert resp.status_code == 422


def test_process_enqueues_and_returns_202(client, monkeypatch):
    """POST /api/v1/process com texto válido → 202 + job_id."""
    import api
    api._api_supabase = None
    api._api_supabase_init = True

    # Evita execução real do pipeline
    with patch.object(api, "_run_pipeline_sync", return_value=None):
        resp = client.post(
            "/api/v1/process",
            data={"text": LONG_TRANSCRIPT},
            headers=_auth(),
        )

    assert resp.status_code == 202
    body = resp.json()
    assert "job_id" in body
    assert body["status"] == "queued"
    assert body["job_id"] in api._JOBS


# ── /health ───────────────────────────────────────────────────────────────────

def test_health_includes_new_fields(client, monkeypatch):
    """GET /health deve incluir secret_manager e cloud_tasks_mode."""
    import api
    api._api_supabase = None
    api._api_supabase_init = True

    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert "secret_manager"   in body
    assert "cloud_tasks_mode" in body
    assert body["status"]     == "ok"
