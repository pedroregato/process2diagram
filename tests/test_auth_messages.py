# tests/test_auth_messages.py
"""
NAV-02 (melhorias/navegabilidade.md, PC211): a tela de login mostrava, em
qualquer falha de credencial no modo multi-tenant, "Falha no login.
Diagnóstico: Hash não confere. Armazenado=<prefixo> Calculado=<prefixo>" —
vazando parte do hash SHA-256 armazenado e do hash calculado da senha
digitada para qualquer visitante não autenticado (modules/tenant_auth.py,
ui/auth_gate.py).

Fix: modules/tenant_auth.login_tenant_debug() nunca mais devolve hash em
nenhum motivo de falha; ui/auth_gate.py mostra sempre a mesma mensagem
genérica para qualquer falha de credencial multi-tenant, sem distinguir
domínio/usuário/senha, e loga o motivo detalhado só via logging.warning()
(nunca na UI).
"""

from unittest.mock import patch

from modules.tenant_auth import login_tenant_debug

TENANT_ID = "tenant-11111111-1111-1111-1111-111111111111"
STORED_HASH = "a" * 64  # sha256 hexdigest length


class _Resp:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, rows: list[dict]):
        self._rows = list(rows)

    def select(self, *a, **k):
        return self

    def eq(self, col, val):
        self._rows = [r for r in self._rows if r.get(col) == val]
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    def execute(self):
        return _Resp(self._rows)


class _FakeDB:
    def __init__(self, tenants, users):
        self._tenants = tenants
        self._users = users

    def table(self, name):
        if name == "tenants":
            return _FakeQuery(self._tenants)
        if name == "tenant_users":
            return _FakeQuery(self._users)
        raise AssertionError(f"unexpected table: {name}")


def _db_with_user(password_hash: str) -> _FakeDB:
    return _FakeDB(
        tenants=[{"id": TENANT_ID, "display_name": "Acme", "active": True}],
        users=[{
            "id": "u1", "tenant_id": TENANT_ID, "login": "pedro",
            "display_name": "Pedro", "role": "user", "active": True,
            "password_hash": password_hash,
        }],
    )


def _db_no_user() -> _FakeDB:
    return _FakeDB(
        tenants=[{"id": TENANT_ID, "display_name": "Acme", "active": True}],
        users=[],
    )


_FORBIDDEN_SUBSTRINGS = ("Hash", "Armazenado", "Calculado")


def test_wrong_password_message_has_no_hash_leakage():
    with patch("modules.tenant_auth.get_supabase_client", return_value=_db_with_user(STORED_HASH)):
        result, motivo = login_tenant_debug("acme", "pedro", "senha-errada")
    assert result is None
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in motivo


def test_nonexistent_user_message_has_no_hash_leakage():
    with patch("modules.tenant_auth.get_supabase_client", return_value=_db_no_user()):
        result, motivo = login_tenant_debug("acme", "ghost", "qualquer-senha")
    assert result is None
    for forbidden in _FORBIDDEN_SUBSTRINGS:
        assert forbidden not in motivo


def test_ui_never_interpolates_login_failure_reason():
    """Static guard on ui/auth_gate.py: no f-string may embed the tenant
    login failure reason (motivo/motivo_diag) into the HTML shown to an
    unauthenticated visitor — regression would silently reopen NAV-02."""
    from pathlib import Path
    text = (Path(__file__).resolve().parent.parent / "ui" / "auth_gate.py").read_text(encoding="utf-8")
    assert "motivo_diag" not in text
    assert '_login_erro"] = f"tenant:' not in text
