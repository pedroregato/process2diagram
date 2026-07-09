# tests/test_list_all_business_assets_for_domain.py
"""
Tests for core/project_store.py :: list_all_business_assets_for_domain()
(Catálogo do Domínio — reuso cross-contexto de melhorias/cognicao-de-negocio.md):
aggregates list_all_business_assets() across every context of a tenant,
tagging each item with context_id/context_name.

Mocks list_contexts() and list_all_business_assets() directly — this test
exercises only the cross-context merge/tagging logic, not the per-context
aggregation itself (covered by tests/test_list_all_business_assets.py).
"""

from unittest.mock import patch

from core.project_store import list_all_business_assets_for_domain, _ALL_ASSET_TYPES


class TestListAllBusinessAssetsForDomain:
    def test_no_contexts_returns_all_type_keys_with_empty_lists(self):
        with patch("core.project_store.list_contexts", return_value=[]):
            result = list_all_business_assets_for_domain("t1")
        assert set(result.keys()) == set(_ALL_ASSET_TYPES)
        assert all(v == [] for v in result.values())

    def test_passes_tenant_id_through_to_list_contexts(self):
        with patch("core.project_store.list_contexts", return_value=[]) as mocked:
            list_all_business_assets_for_domain("t42")
        mocked.assert_called_once_with(tenant_id="t42")

    def test_merges_items_from_multiple_contexts_and_tags_context(self):
        contexts = [
            {"id": "ctx-a", "name": "Projeto A"},
            {"id": "ctx-b", "name": "Projeto B"},
        ]

        def _fake_assets(project_id):
            if project_id == "ctx-a":
                return {"requirement": [{"artifact_id": "r1", "title": "Req A", "has_metadata_support": True, "metadata": None}]}
            return {"requirement": [{"artifact_id": "r2", "title": "Req B", "has_metadata_support": True, "metadata": None}]}

        with patch("core.project_store.list_contexts", return_value=contexts), \
             patch("core.project_store.list_all_business_assets", side_effect=_fake_assets):
            result = list_all_business_assets_for_domain("t1")

        reqs = result["requirement"]
        assert len(reqs) == 2
        by_id = {r["artifact_id"]: r for r in reqs}
        assert by_id["r1"]["context_id"] == "ctx-a"
        assert by_id["r1"]["context_name"] == "Projeto A"
        assert by_id["r2"]["context_id"] == "ctx-b"
        assert by_id["r2"]["context_name"] == "Projeto B"

    def test_context_without_id_is_skipped(self):
        contexts = [{"name": "Sem ID"}, {"id": "ctx-a", "name": "Projeto A"}]

        with patch("core.project_store.list_contexts", return_value=contexts), \
             patch("core.project_store.list_all_business_assets", return_value={"requirement": []}) as mocked:
            list_all_business_assets_for_domain("t1")

        mocked.assert_called_once_with("ctx-a")

    def test_tenant_id_none_still_calls_list_contexts(self):
        with patch("core.project_store.list_contexts", return_value=[]) as mocked:
            list_all_business_assets_for_domain(None)
        mocked.assert_called_once_with(tenant_id=None)

    def test_original_items_not_mutated(self):
        contexts = [{"id": "ctx-a", "name": "Projeto A"}]
        original_item = {"artifact_id": "r1", "title": "Req A", "has_metadata_support": True, "metadata": None}

        with patch("core.project_store.list_contexts", return_value=contexts), \
             patch("core.project_store.list_all_business_assets", return_value={"requirement": [original_item]}):
            list_all_business_assets_for_domain("t1")

        assert "context_id" not in original_item
