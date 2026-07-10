# tests/test_promote_to_business_asset.py
"""
Tests for core/project_store.py :: promote_to_business_asset() / demote_business_asset()
(melhorias/promocao-ativos-negocio.md Fase A): explicit promotion gate — a row
in asset_metadata now IS the definition of "being a business asset".

No real DB calls — reuses the _FakeDB/_FakeAssetTable pattern from
tests/test_asset_metadata.py.
"""

from unittest.mock import MagicMock, patch

from core.project_store import promote_to_business_asset, demote_business_asset


class _FakeAssetTable:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self._filters = {}
        self._mode = None
        self._upsert_payload = None

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


class TestPromoteToBusinessAsset:
    def test_promotes_with_all_required_fields(self):
        db = _FakeDB([])
        with patch("core.project_store._db", return_value=db):
            result = promote_to_business_asset(
                "p1", "requirement", "r1",
                business_interest="estrategico",
                business_perspective=["financeiro", "juridico"],
                promotion_justification="Impacta o orçamento e requer aprovação jurídica.",
                created_by="pedro",
            )
        assert result is not None
        assert result["status"] == "rascunho"
        assert result["business_interest"] == "estrategico"
        assert result["business_perspective"] == ["financeiro", "juridico"]
        assert result["promotion_justification"] == "Impacta o orçamento e requer aprovação jurídica."
        assert result["created_by"] == "pedro"
        assert result["promoted_by"] == "pedro"
        assert len(db._table.rows) == 1

    def test_formal_classification_is_optional(self):
        db = _FakeDB([])
        with patch("core.project_store._db", return_value=db):
            result = promote_to_business_asset(
                "p1", "bpmn_process", "b1",
                business_interest="tatico",
                business_perspective=["operacoes"],
                promotion_justification="Processo reutilizável entre contextos.",
            )
        assert result is not None
        assert result["formal_classification"] is None

    def test_formal_classification_when_provided(self):
        db = _FakeDB([])
        with patch("core.project_store._db", return_value=db):
            result = promote_to_business_asset(
                "p1", "bpmn_process", "b1",
                business_interest="tatico",
                business_perspective=["operacoes"],
                promotion_justification="Processo reutilizável entre contextos.",
                formal_classification="AN-03",
            )
        assert result["formal_classification"] == "AN-03"

    def test_missing_business_interest_refused(self):
        db = _FakeDB([])
        with patch("core.project_store._db", return_value=db):
            result = promote_to_business_asset(
                "p1", "requirement", "r1",
                business_interest="",
                business_perspective=["financeiro"],
                promotion_justification="Motivo.",
            )
        assert result is None
        assert db._table.rows == []

    def test_missing_business_perspective_refused(self):
        db = _FakeDB([])
        with patch("core.project_store._db", return_value=db):
            result = promote_to_business_asset(
                "p1", "requirement", "r1",
                business_interest="estrategico",
                business_perspective=[],
                promotion_justification="Motivo.",
            )
        assert result is None
        assert db._table.rows == []

    def test_blank_justification_refused(self):
        db = _FakeDB([])
        with patch("core.project_store._db", return_value=db):
            result = promote_to_business_asset(
                "p1", "requirement", "r1",
                business_interest="estrategico",
                business_perspective=["financeiro"],
                promotion_justification="   ",
            )
        assert result is None
        assert db._table.rows == []

    def test_justification_is_stripped(self):
        db = _FakeDB([])
        with patch("core.project_store._db", return_value=db):
            result = promote_to_business_asset(
                "p1", "requirement", "r1",
                business_interest="estrategico",
                business_perspective=["financeiro"],
                promotion_justification="  motivo com espaços  ",
            )
        assert result["promotion_justification"] == "motivo com espaços"


class TestDemoteBusinessAsset:
    def test_moves_status_to_arquivado_keeping_classification(self):
        rows = [{
            "id": "m1", "project_id": "p1", "artifact_type": "requirement", "artifact_id": "r1",
            "status": "ativo", "tags": [], "owner": None, "notes": None,
            "business_interest": "estrategico", "business_perspective": ["financeiro"],
            "formal_classification": "AN-03", "promotion_justification": "Motivo original.",
        }]
        db = _FakeDB(rows)
        with patch("core.project_store._db", return_value=db):
            ok = demote_business_asset("p1", "requirement", "r1")
        assert ok is True
        assert db._table.rows[0]["status"] == "arquivado"
        assert db._table.rows[0]["business_interest"] == "estrategico"
        assert db._table.rows[0]["promotion_justification"] == "Motivo original."

    def test_nonexistent_asset_is_not_silently_created(self):
        """Demoting something never promoted must not create a row without
        the mandatory classifications — it should simply fail."""
        db = _FakeDB([])
        with patch("core.project_store._db", return_value=db):
            ok = demote_business_asset("p1", "requirement", "r1")
        assert ok is False
        assert db._table.rows == []
