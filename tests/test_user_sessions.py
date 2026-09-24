# tests/test_user_sessions.py
"""
NAV-05 (melhorias/parciais/navegabilidade.md, PC214): sessão persistente
multi-tenant — F5, link direto ou fechar/reabrir o navegador mantêm o
usuário logado (12h de expiração deslizante), com o mesmo contexto de
trabalho ativo, sem is_authenticated() depender só de st.session_state.

Testes unitários (mock de banco) para o ciclo de vida do token opaco em
core/project_store.py: criar, validar, deslizar expiração, atualizar
contexto e revogar. Nenhum destes testes bate no Supabase real — um fake
client em memória substitui core.project_store._db().
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from core.project_store import (
    create_user_session,
    validate_user_session,
    update_user_session_context,
    revoke_user_session,
    _hash_session_token,
)


class _Resp:
    def __init__(self, data):
        self.data = data


class _FakeTable:
    def __init__(self, store: dict, name: str):
        self.store = store
        self.name = name
        self._filters: dict = {}
        self._op = None
        self._payload = None
        self._limit = None

    def insert(self, payload):
        self._op = "insert"
        self._payload = payload
        return self

    def select(self, *_a, **_k):
        self._op = "select"
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def delete(self):
        self._op = "delete"
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def limit(self, n):
        self._limit = n
        return self

    def _matched(self, rows):
        return [r for r in rows if all(r.get(k) == v for k, v in self._filters.items())]

    def execute(self):
        rows = self.store.setdefault(self.name, [])
        if self._op == "insert":
            row = dict(self._payload)
            row.setdefault("id", f"id-{len(rows)}")
            rows.append(row)
            return _Resp([row])
        matched = self._matched(rows)
        if self._op == "select":
            if self._limit is not None:
                matched = matched[: self._limit]
            return _Resp(matched)
        if self._op == "update":
            for r in matched:
                r.update(self._payload)
            return _Resp(matched)
        if self._op == "delete":
            self.store[self.name] = [r for r in rows if r not in matched]
            return _Resp(matched)
        return _Resp([])


class _FakeDB:
    def __init__(self):
        self.store: dict = {}

    def table(self, name):
        return _FakeTable(self.store, name)


_PS = "core.project_store"


class TestCreateUserSession:
    def test_returns_token_and_persists_only_the_hash(self):
        db = _FakeDB()
        with patch(f"{_PS}._db", lambda: db):
            token = create_user_session("tenant-1", "pedro")

        assert token and isinstance(token, str)
        rows = db.store["user_sessions"]
        assert len(rows) == 1
        assert rows[0]["token_hash"] == _hash_session_token(token)
        assert rows[0]["token_hash"] != token
        assert rows[0]["tenant_id"] == "tenant-1"
        assert rows[0]["username"] == "pedro"

    def test_fail_open_when_db_unavailable(self):
        with patch(f"{_PS}._db", lambda: None):
            assert create_user_session("tenant-1", "pedro") is None


class TestValidateUserSession:
    def test_valid_token_returns_session_data(self):
        db = _FakeDB()
        with patch(f"{_PS}._db", lambda: db):
            token = create_user_session("tenant-1", "pedro")
            session = validate_user_session(token)

        assert session == {
            "tenant_id": "tenant-1",
            "username": "pedro",
            "last_context_id": None,
        }

    def test_unknown_token_returns_none(self):
        db = _FakeDB()
        with patch(f"{_PS}._db", lambda: db):
            assert validate_user_session("nao-existe-nenhum-token") is None

    def test_empty_token_returns_none_without_hitting_db(self):
        assert validate_user_session("") is None
        assert validate_user_session(None) is None

    def test_expired_token_returns_none(self):
        db = _FakeDB()
        with patch(f"{_PS}._db", lambda: db):
            token = create_user_session("tenant-1", "pedro")
            # Volta a expiração pro passado — simula sessão vencida.
            db.store["user_sessions"][0]["expires_at"] = (
                datetime.now(timezone.utc) - timedelta(hours=1)
            ).isoformat()
            assert validate_user_session(token) is None

    def test_valid_token_slides_expiration_forward(self):
        db = _FakeDB()
        with patch(f"{_PS}._db", lambda: db):
            token = create_user_session("tenant-1", "pedro")
            original_expiry = datetime.fromisoformat(db.store["user_sessions"][0]["expires_at"])
            # Simula tempo passando — expiração original ainda no futuro,
            # mas visivelmente mais próxima.
            db.store["user_sessions"][0]["expires_at"] = (
                datetime.now(timezone.utc) + timedelta(hours=1)
            ).isoformat()
            validate_user_session(token)
            new_expiry = datetime.fromisoformat(db.store["user_sessions"][0]["expires_at"])

        assert new_expiry > datetime.now(timezone.utc) + timedelta(hours=11)
        assert new_expiry < original_expiry + timedelta(hours=12, minutes=1)


class TestUpdateUserSessionContext:
    def test_updates_last_context_id(self):
        db = _FakeDB()
        with patch(f"{_PS}._db", lambda: db):
            token = create_user_session("tenant-1", "pedro")
            update_user_session_context(token, "ctx-42")
            session = validate_user_session(token)

        assert session["last_context_id"] == "ctx-42"

    def test_noop_with_empty_token(self):
        db = _FakeDB()
        with patch(f"{_PS}._db", lambda: db):
            update_user_session_context("", "ctx-42")  # não deve lançar
        assert db.store == {}


class TestRevokeUserSession:
    def test_revoked_token_no_longer_validates(self):
        db = _FakeDB()
        with patch(f"{_PS}._db", lambda: db):
            token = create_user_session("tenant-1", "pedro")
            assert validate_user_session(token) is not None
            revoke_user_session(token)
            assert validate_user_session(token) is None

    def test_noop_with_empty_token(self):
        db = _FakeDB()
        with patch(f"{_PS}._db", lambda: db):
            revoke_user_session("")  # não deve lançar
        assert db.store == {}
