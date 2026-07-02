# tests/test_secret_manager.py
# ─────────────────────────────────────────────────────────────────────────────
# Suite de testes para services/secret_manager.py
# 13 testes — zero dependências de rede (GCP Secret Manager mockado via patch).
# ─────────────────────────────────────────────────────────────────────────────

import os
import importlib
from unittest.mock import MagicMock, patch

import pytest


# ── Fixture: importação isolada do módulo ─────────────────────────────────────

@pytest.fixture(autouse=True)
def _clear_lru_cache():
    """Limpa o cache do Secret Manager entre testes."""
    from services.secret_manager import _from_secret_manager, invalidate_cache
    invalidate_cache()
    yield
    invalidate_cache()


# ── Camada 1: GCP Secret Manager ──────────────────────────────────────────────

def test_gcp_layer_returns_value():
    """Camada 1 retorna valor quando Secret Manager disponível (mockado via sys.modules)."""
    from services import secret_manager as sm
    sm._from_secret_manager.cache_clear()

    mock_resp   = MagicMock()
    mock_resp.payload.data.decode.return_value = "gcp_secret_value"
    mock_client = MagicMock()
    mock_client.access_secret_version.return_value = mock_resp

    mock_sm_module  = MagicMock()
    mock_sm_module.SecretManagerServiceClient.return_value = mock_client

    mock_google      = MagicMock()
    mock_google_cloud = MagicMock()
    mock_google_cloud.secretmanager = mock_sm_module

    with patch.dict("sys.modules", {
        "google":                      mock_google,
        "google.cloud":                mock_google_cloud,
        "google.cloud.secretmanager":  mock_sm_module,
    }):
        sm._from_secret_manager.cache_clear()
        result = sm._from_secret_manager("MY_SECRET", "my-project")

    assert result == "gcp_secret_value"


def test_gcp_layer_returns_none_on_import_error():
    """Camada 1 retorna None quando google-cloud-secret-manager não instalado (ImportError)."""
    from services import secret_manager as sm
    sm._from_secret_manager.cache_clear()
    # O pacote não está instalado no dev env — _from_secret_manager captura ImportError
    result = sm._from_secret_manager("MY_SECRET_NOPKG", "my-project")
    assert result is None


def test_gcp_layer_fail_open_on_exception():
    """Camada 1 retorna None em qualquer exceção de rede (Fail-Open)."""
    from services import secret_manager as sm
    sm._from_secret_manager.cache_clear()

    mock_client = MagicMock()
    mock_client.access_secret_version.side_effect = Exception("connection timeout")

    mock_sm_module = MagicMock()
    mock_sm_module.SecretManagerServiceClient.return_value = mock_client

    with patch.dict("sys.modules", {
        "google.cloud.secretmanager": mock_sm_module,
    }):
        sm._from_secret_manager.cache_clear()
        result = sm._from_secret_manager("MY_SECRET", "my-project")

    assert result is None


# ── Camada 2: Variáveis de ambiente ───────────────────────────────────────────

def test_env_layer_exact_name(monkeypatch):
    """Camada 2 resolve nome exato da env var."""
    monkeypatch.setenv("MY_API_KEY", "env_value_exact")
    from services import secret_manager as sm
    assert sm._from_env("MY_API_KEY") == "env_value_exact"


def test_env_layer_uppercase_fallback(monkeypatch):
    """Camada 2 tenta variante uppercase automaticamente."""
    monkeypatch.setenv("MY_API_KEY", "env_value_upper")
    from services import secret_manager as sm
    assert sm._from_env("my_api_key") == "env_value_upper"


def test_env_layer_returns_none_when_absent(monkeypatch):
    """Camada 2 retorna None quando variável não existe."""
    monkeypatch.delenv("ABSENT_KEY", raising=False)
    from services import secret_manager as sm
    assert sm._from_env("ABSENT_KEY") is None


def test_env_layer_strips_whitespace(monkeypatch):
    """Camada 2 faz strip() no valor antes de retornar."""
    monkeypatch.setenv("PADDED_KEY", "  value_with_spaces  ")
    from services import secret_manager as sm
    result = sm._from_env("PADDED_KEY")
    assert result == "value_with_spaces"


# ── Camada 3: Streamlit secrets ───────────────────────────────────────────────

def test_streamlit_layer_returns_none_outside_streamlit():
    """Camada 3 é Fail-Open: retorna None quando Streamlit não está rodando."""
    from services import secret_manager as sm
    # Fora do contexto Streamlit, qualquer import/acesso levanta; deve retornar None
    result = sm._from_streamlit("SOME_KEY")
    assert result is None


# ── API pública: get_secret ───────────────────────────────────────────────────

def test_get_secret_env_fallback(monkeypatch):
    """get_secret() resolve via Camada 2 quando GCP não disponível."""
    monkeypatch.setenv("MY_SECRET", "from_env")
    from services import secret_manager as sm
    sm._from_secret_manager.cache_clear()

    # Força GCP como indisponível — project_id ausente
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GCLOUD_PROJECT", raising=False)

    result = sm.get_secret("MY_SECRET")
    assert result == "from_env"


def test_get_secret_returns_none_when_all_layers_fail(monkeypatch):
    """get_secret() retorna None (Fail-Open) quando nenhuma camada encontra o valor."""
    monkeypatch.delenv("TOTALLY_ABSENT", raising=False)
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GCLOUD_PROJECT", raising=False)

    from services import secret_manager as sm
    sm._from_secret_manager.cache_clear()
    result = sm.get_secret("TOTALLY_ABSENT")
    assert result is None


def test_get_secret_never_raises():
    """get_secret() nunca propaga exceção (contrato Fail-Open)."""
    from services import secret_manager as sm
    try:
        sm.get_secret("__IMPOSSIBLE_KEY__9999")
    except Exception as exc:
        pytest.fail(f"get_secret() levantou exceção inesperada: {exc}")


# ── API pública: get_secret_required ─────────────────────────────────────────

def test_get_secret_required_raises_when_absent(monkeypatch):
    """get_secret_required() levanta ValueError quando secret ausente."""
    monkeypatch.delenv("REQUIRED_KEY_ABSENT", raising=False)
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GCLOUD_PROJECT", raising=False)

    from services import secret_manager as sm
    sm._from_secret_manager.cache_clear()
    with pytest.raises(ValueError, match="REQUIRED_KEY_ABSENT"):
        sm.get_secret_required("REQUIRED_KEY_ABSENT")


def test_get_secret_required_returns_value(monkeypatch):
    """get_secret_required() retorna valor quando secret presente."""
    monkeypatch.setenv("REQ_KEY_PRESENT", "required_value")
    monkeypatch.delenv("GCP_PROJECT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GCLOUD_PROJECT", raising=False)

    from services import secret_manager as sm
    sm._from_secret_manager.cache_clear()
    assert sm.get_secret_required("REQ_KEY_PRESENT") == "required_value"
