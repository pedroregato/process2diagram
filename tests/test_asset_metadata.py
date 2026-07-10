# tests/test_asset_metadata.py
"""
Tests for core/project_store.py :: get_asset_metadata_map / upsert_asset_metadata
(Ativos de Negócio — Etapa 2, melhorias/cognicao-de-negocio.md): polymorphic
governance table (status/tags/owner/notes) for the 5 artifact types that have
a real row id (requirement, bpmn_process, sbvr_term, sbvr_rule, meeting_minutes).

No real DB calls.
"""

from unittest.mock import MagicMock, patch

from core.project_store import (
    get_asset_metadata_map,
    upsert_asset_metadata,
    ASSET_TYPES_WITH_METADATA,
)


class _FakeAssetTable:
    """In-memory stand-in for the asset_metadata table.

    Mimics enough of the Supabase query builder (select/eq/limit/upsert/execute)
    to exercise the real read-merge-write logic in upsert_asset_metadata().
    """

    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self._filters = {}
        self._mode = None
        self._upsert_payload = None

    # ── query builder chain ──────────────────────────────────────────────
    def select(self, *a, **k):
        self._mode = "select"
        return self

    def eq(self, field, value):
        self._filters[field] = value
        return self

    def limit(self, *a, **k):
        return self

    def upsert(self, payload, on_conflict=None):
        self._mode = "upsert"
        self._upsert_payload = dict(payload)
        return self

    def execute(self):
        resp = MagicMock()
        if self._mode == "upsert":
            payload = self._upsert_payload
            key = (payload["project_id"], payload["artifact_type"], payload["artifact_id"])
            existing_idx = next(
                (i for i, r in enumerate(self.rows)
                 if (r["project_id"], r["artifact_type"], r["artifact_id"]) == key),
                None,
            )
            if existing_idx is not None:
                self.rows[existing_idx] = {**self.rows[existing_idx], **payload}
                resp.data = [self.rows[existing_idx]]
            else:
                new_row = {"id": f"generated-{len(self.rows)}", **payload}
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
    def __init__(self, rows=None):
        self._table = _FakeAssetTable(rows)

    def table(self, name):
        assert name == "asset_metadata"
        return self._table


class TestGetAssetMetadataMap:
    def test_indexes_by_type_and_id(self):
        rows = [
            {"id": "m1", "project_id": "p1", "artifact_type": "requirement", "artifact_id": "r1",
             "status": "ativo", "tags": ["prioritario"], "owner": "Ana", "notes": ""},
            {"id": "m2", "project_id": "p1", "artifact_type": "bpmn_process", "artifact_id": "b1",
             "status": "rascunho", "tags": [], "owner": None, "notes": None},
        ]
        with patch("core.project_store._db", return_value=_FakeDB(rows)):
            result = get_asset_metadata_map("p1")
        assert result[("requirement", "r1")]["owner"] == "Ana"
        assert result[("bpmn_process", "b1")]["status"] == "rascunho"

    def test_empty_project_returns_empty_dict(self):
        with patch("core.project_store._db", return_value=_FakeDB([])):
            result = get_asset_metadata_map("p1")
        assert result == {}

    def test_no_db_returns_empty_dict(self):
        with patch("core.project_store._db", return_value=None):
            result = get_asset_metadata_map("p1")
        assert result == {}


class TestUpsertAssetMetadata:
    def test_creates_new_row_when_none_exists(self):
        db = _FakeDB([])
        with patch("core.project_store._db", return_value=db):
            result = upsert_asset_metadata(
                "p1", "requirement", "r1",
                status="ativo", tags=["urgente"], owner="Ana", notes="nota",
                business_interest="estrategico", business_perspective=["financeiro"],
                promotion_justification="Impacta o orçamento anual.",
            )
        assert result["status"] == "ativo"
        assert result["tags"] == ["urgente"]
        assert result["owner"] == "Ana"
        assert result["business_interest"] == "estrategico"
        assert result["business_perspective"] == ["financeiro"]
        assert len(db._table.rows) == 1

    def test_new_row_without_promotion_fields_is_refused(self):
        """A row's mere existence now means 'promoted' (melhorias/promocao-ativos-negocio.md
        §4) — creating one without the 3 mandatory classifications must be refused,
        not silently defaulted, so editing code can't accidentally promote something."""
        db = _FakeDB([])
        with patch("core.project_store._db", return_value=db):
            result = upsert_asset_metadata(
                "p1", "requirement", "r1", status="ativo", tags=["urgente"], owner="Ana",
            )
        assert result is None
        assert db._table.rows == []

    def test_new_row_with_empty_justification_is_refused(self):
        db = _FakeDB([])
        with patch("core.project_store._db", return_value=db):
            result = upsert_asset_metadata(
                "p1", "requirement", "r1",
                business_interest="estrategico", business_perspective=["financeiro"],
                promotion_justification="   ",
            )
        assert result is None
        assert db._table.rows == []

    def test_updates_existing_row(self):
        rows = [{"id": "m1", "project_id": "p1", "artifact_type": "requirement", "artifact_id": "r1",
                  "status": "rascunho", "tags": [], "owner": None, "notes": None}]
        db = _FakeDB(rows)
        with patch("core.project_store._db", return_value=db):
            result = upsert_asset_metadata("p1", "requirement", "r1", status="ativo")
        assert result["status"] == "ativo"
        assert len(db._table.rows) == 1  # updated in place, not duplicated

    def test_omitted_fields_preserve_existing_values(self):
        rows = [{"id": "m1", "project_id": "p1", "artifact_type": "requirement", "artifact_id": "r1",
                  "status": "ativo", "tags": ["existente"], "owner": "Ana", "notes": "nota antiga"}]
        db = _FakeDB(rows)
        with patch("core.project_store._db", return_value=db):
            # Only touching status — tags/owner/notes must survive untouched.
            result = upsert_asset_metadata("p1", "requirement", "r1", status="arquivado")
        assert result["status"] == "arquivado"
        assert result["tags"] == ["existente"]
        assert result["owner"] == "Ana"
        assert result["notes"] == "nota antiga"

    def test_unsupported_artifact_type_returns_none(self):
        db = _FakeDB([])
        with patch("core.project_store._db", return_value=db):
            result = upsert_asset_metadata("p1", "dmn", "synthetic-id", status="ativo")
        assert result is None
        assert db._table.rows == []

    def test_no_db_returns_none(self):
        with patch("core.project_store._db", return_value=None):
            result = upsert_asset_metadata("p1", "requirement", "r1", status="ativo")
        assert result is None

    def test_supported_types(self):
        assert ASSET_TYPES_WITH_METADATA == {
            "requirement", "bpmn_process", "sbvr_term", "sbvr_rule", "meeting_minutes",
            "document",
        }
