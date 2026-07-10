# tests/test_promote_assistant_output.py
"""
Tests for core/project_store.py :: promote_assistant_output_to_asset() /
list_assistant_artifacts_by_project() (Ativos de Negócio — Fase C,
melhorias/promocao-ativos-negocio.md §6): the only artifact_type whose
promotion CREATES its own source row (assistant_artifacts) instead of
promoting something that already existed — today nothing the Assistant
generates on demand is persisted anywhere else.

No real DB calls — a small fake Supabase client covering both
`assistant_artifacts` and `asset_metadata` tables.
"""

from unittest.mock import MagicMock, patch

from core.project_store import (
    promote_assistant_output_to_asset,
    list_assistant_artifacts_by_project,
    ASSET_TYPES_WITH_METADATA,
)


class _FakeTable:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self._filters = {}
        self._mode = None
        self._payload = None

    def select(self, *a, **k):
        self._mode = "select"
        return self

    def insert(self, payload):
        self._mode = "insert"
        self._payload = dict(payload)
        return self

    def upsert(self, payload, on_conflict=None):
        self._mode = "upsert"
        self._payload = dict(payload)
        return self

    def eq(self, field, value):
        self._filters[field] = value
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        resp = MagicMock()
        if self._mode == "insert":
            new_row = {"id": f"generated-{len(self.rows)}", **self._payload}
            self.rows.append(new_row)
            resp.data = [new_row]
        elif self._mode == "upsert":
            key_fields = ("project_id", "artifact_type", "artifact_id")
            key = tuple(self._payload.get(f) for f in key_fields)
            existing_idx = next(
                (i for i, r in enumerate(self.rows)
                 if tuple(r.get(f) for f in key_fields) == key),
                None,
            )
            if existing_idx is not None:
                self.rows[existing_idx] = {**self.rows[existing_idx], **self._payload}
                resp.data = [self.rows[existing_idx]]
            else:
                new_row = {"id": f"generated-{len(self.rows)}", **self._payload}
                self.rows.append(new_row)
                resp.data = [new_row]
        else:
            matched = [
                r for r in self.rows
                if all(r.get(k) == v for k, v in self._filters.items())
            ]
            resp.data = matched
        return resp


class _FakeDB:
    def __init__(self):
        self.tables = {"assistant_artifacts": _FakeTable(), "asset_metadata": _FakeTable()}

    def table(self, name):
        return self.tables[name]


class TestPromoteAssistantOutputToAsset:
    def test_creates_snapshot_and_promotes_in_one_call(self):
        db = _FakeDB()
        with patch("core.project_store._db", return_value=db):
            result = promote_assistant_output_to_asset(
                "p1", "Análise de Tendências — Q3",
                "## Requisitos mais instáveis\n...",
                business_interest="tatico",
                business_perspective=["governanca"],
                promotion_justification="Diretoria pediu para acompanhar isso mensalmente.",
                source_tool="analisar_tendencias",
                created_by="pedro",
            )
        assert result is not None
        assert len(db.tables["assistant_artifacts"].rows) == 1
        assert len(db.tables["asset_metadata"].rows) == 1
        snapshot = db.tables["assistant_artifacts"].rows[0]
        assert snapshot["title"] == "Análise de Tendências — Q3"
        assert snapshot["source_tool"] == "analisar_tendencias"
        asset_row = db.tables["asset_metadata"].rows[0]
        assert asset_row["artifact_type"] == "assistant_artifact"
        assert asset_row["artifact_id"] == snapshot["id"]
        assert asset_row["business_interest"] == "tatico"

    def test_blank_title_refused_before_any_write(self):
        db = _FakeDB()
        with patch("core.project_store._db", return_value=db):
            result = promote_assistant_output_to_asset(
                "p1", "   ", "conteúdo",
                business_interest="estrategico", business_perspective=["ti"],
                promotion_justification="motivo",
            )
        assert result is None
        assert db.tables["assistant_artifacts"].rows == []
        assert db.tables["asset_metadata"].rows == []

    def test_blank_content_refused_before_any_write(self):
        db = _FakeDB()
        with patch("core.project_store._db", return_value=db):
            result = promote_assistant_output_to_asset(
                "p1", "Título", "   ",
                business_interest="estrategico", business_perspective=["ti"],
                promotion_justification="motivo",
            )
        assert result is None
        assert db.tables["assistant_artifacts"].rows == []

    def test_missing_classification_refused_before_any_write(self):
        db = _FakeDB()
        with patch("core.project_store._db", return_value=db):
            result = promote_assistant_output_to_asset(
                "p1", "Título", "conteúdo",
                business_interest="", business_perspective=["ti"],
                promotion_justification="motivo",
            )
        assert result is None
        assert db.tables["assistant_artifacts"].rows == []

    def test_assistant_artifact_is_a_supported_type(self):
        assert "assistant_artifact" in ASSET_TYPES_WITH_METADATA


class TestListAssistantArtifactsByProject:
    def test_returns_rows_for_project(self):
        db = _FakeDB()
        db.tables["assistant_artifacts"].rows = [
            {"id": "a1", "project_id": "p1", "title": "Relatório X", "content_markdown": "..."},
            {"id": "a2", "project_id": "p2", "title": "Outro projeto", "content_markdown": "..."},
        ]
        with patch("core.project_store._db", return_value=db):
            result = list_assistant_artifacts_by_project("p1")
        assert len(result) == 1
        assert result[0]["title"] == "Relatório X"

    def test_no_db_returns_empty_list(self):
        with patch("core.project_store._db", return_value=None):
            result = list_assistant_artifacts_by_project("p1")
        assert result == []
