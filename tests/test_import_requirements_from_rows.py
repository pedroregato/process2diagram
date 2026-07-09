# tests/test_import_requirements_from_rows.py
"""
Tests for core/project_store.py::import_requirements_from_rows() (Onda 3,
melhorias/avaliacao-proposta-assistente-20260708.md, proposta #9 —
Importador de Planilha de Requisitos): creates requirements from already
column-mapped/normalized spreadsheet rows, mirroring the exact traceability
convention save_artifacts_from_document() already uses for document-
extracted requirements (meeting_id=None, origin="documento", doc_ref=doc_id).

No real DB calls — Supabase mocked via a small fake client (same pattern as
tests/test_meeting_processing_log.py / tests/test_ata_template_engine.py).
"""

from unittest.mock import patch, MagicMock

from core.project_store import import_requirements_from_rows


class _FakeQuery:
    def __init__(self, rows, table_name, log):
        self._rows = rows
        self._table_name = table_name
        self._log = log
        self._pending_insert = None

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def neq(self, *a, **k):
        return self

    def insert(self, payload):
        self._pending_insert = payload
        return self

    def execute(self):
        resp = MagicMock()
        if self._pending_insert is not None:
            import uuid
            new_row = dict(self._pending_insert)
            new_row.setdefault("id", str(uuid.uuid4()))
            self._log.append((self._table_name, new_row))
            resp.data = [new_row]
        else:
            resp.data = self._rows
        return resp


class _FakeRpc:
    def __init__(self, value):
        self._value = value

    def execute(self):
        resp = MagicMock()
        resp.data = self._value
        return resp


class _FakeDB:
    def __init__(self, next_req_number: int = 1):
        self.log: list[tuple] = []
        self._next_req_number = next_req_number

    def table(self, name):
        return _FakeQuery([], name, self.log)

    def rpc(self, name, params):
        assert name == "next_req_number"
        return _FakeRpc(self._next_req_number)


class TestImportRequirementsFromRows:
    def test_creates_requirements_with_sequential_numbers_and_traceability(self):
        db = _FakeDB(next_req_number=10)
        rows = [
            {"title": "Login SSO", "description": "Permitir login via SSO", "req_type": "functional", "priority": "high"},
            {"title": "Exportar CSV", "description": "", "req_type": "", "priority": ""},
        ]
        with patch("core.project_store._db", return_value=db):
            result = import_requirements_from_rows("proj-1", rows, doc_id="doc-123")

        assert [c["req_number"] for c in result["created"]] == [10, 11]
        assert result["failed"] == []

        req_inserts = [row for table, row in db.log if table == "requirements"]
        assert len(req_inserts) == 2
        assert req_inserts[0]["origin"] == "documento"
        assert req_inserts[0]["doc_ref"] == "doc-123"
        assert req_inserts[0]["title"] == "Login SSO"
        assert req_inserts[1]["req_number"] == 11

    def test_empty_title_row_fails_without_stopping_the_rest(self):
        db = _FakeDB(next_req_number=1)
        rows = [
            {"title": "", "description": "sem título"},
            {"title": "Requisito válido", "description": "ok"},
        ]
        with patch("core.project_store._db", return_value=db):
            result = import_requirements_from_rows("proj-1", rows, doc_id=None)

        assert len(result["failed"]) == 1
        assert result["failed"][0]["reason"] == "Título vazio"
        assert len(result["created"]) == 1
        assert result["created"][0]["title"] == "Requisito válido"
        # The failed row must NOT have consumed a req_number slot.
        assert result["created"][0]["req_number"] == 1

    def test_no_doc_id_still_imports(self):
        db = _FakeDB(next_req_number=1)
        rows = [{"title": "Sem documento de origem"}]
        with patch("core.project_store._db", return_value=db):
            result = import_requirements_from_rows("proj-1", rows, doc_id=None)
        assert len(result["created"]) == 1
        req_inserts = [row for table, row in db.log if table == "requirements"]
        assert "doc_ref" not in req_inserts[0] or req_inserts[0].get("doc_ref") is None

    def test_empty_rows_returns_empty_result(self):
        db = _FakeDB()
        with patch("core.project_store._db", return_value=db):
            result = import_requirements_from_rows("proj-1", [], doc_id="doc-1")
        assert result == {"created": [], "failed": []}
