# tests/test_list_all_business_assets.py
"""
Tests for core/project_store.py :: list_all_business_assets() (Ativos de
Negócio — Etapa 1, melhorias/cognicao-de-negocio.md): aggregates all 8
artifact types (5 with metadata support + BMM/DMN/IBIS/Relatórios read-only)
into a single unified structure for the "Ativos de Negócio" page.

Mocks the 9 underlying listing/lookup functions directly — this test exercises
only the merge/normalization logic in list_all_business_assets(), not the
individual listing functions (covered elsewhere).
"""

from unittest.mock import patch

from core.project_store import list_all_business_assets


def _patches(**overrides):
    meta_map = overrides.pop("get_asset_metadata_map", {})
    values = {
        "list_requirements_light": [],
        "list_bpmn_processes": [],
        "list_sbvr_terms": [],
        "list_sbvr_rules": [],
        "list_meetings": [],
        "list_bmm_by_project": [],
        "list_dmn_by_project": [],
        "list_argumentation_by_project": [],
        "list_reports_by_project": [],
    }
    values.update(overrides)
    patches = {name: (lambda project_id, _v=v: _v) for name, v in values.items()}
    patches["get_asset_metadata_map"] = lambda project_id, _m=meta_map: _m
    return patches


class TestListAllBusinessAssets:
    def test_empty_project_returns_all_type_keys_with_empty_lists(self):
        with patch.multiple("core.project_store", **_patches()):
            result = list_all_business_assets("p1")
        assert set(result.keys()) == {
            "requirement", "bpmn_process", "sbvr_term", "sbvr_rule",
            "meeting_minutes", "bmm", "dmn", "ibis", "report",
        }
        assert all(v == [] for v in result.values())

    def test_requirement_has_metadata_support_and_merges_existing_metadata(self):
        overrides = _patches(
            list_requirements_light=[{"id": "r1", "req_number": 1, "title": "Login SSO"}],
            get_asset_metadata_map={("requirement", "r1"): {"status": "ativo", "owner": "Ana"}},
        )
        with patch.multiple("core.project_store", **overrides):
            result = list_all_business_assets("p1")
        item = result["requirement"][0]
        assert item["artifact_id"] == "r1"
        assert item["has_metadata_support"] is True
        assert item["metadata"]["status"] == "ativo"
        assert item["metadata"]["owner"] == "Ana"

    def test_requirement_without_metadata_row_has_none_metadata(self):
        overrides = _patches(
            list_requirements_light=[{"id": "r1", "req_number": 1, "title": "Login SSO"}],
        )
        with patch.multiple("core.project_store", **overrides):
            result = list_all_business_assets("p1")
        assert result["requirement"][0]["metadata"] is None

    def test_bmm_dmn_ibis_report_are_read_only(self):
        overrides = _patches(
            list_bmm_by_project=[{"vision": "Ser líder", "_meeting_number": 1,
                                    "_meeting_title": "Kickoff", "_meeting_date": "2026-06-01"}],
            list_dmn_by_project=[{"name": "Elegibilidade", "_meeting_title": "R2", "_meeting_date": "2026-06-15"}],
            list_argumentation_by_project=[{"statement": "Devemos migrar?", "_meeting_title": "R3", "_meeting_date": "2026-07-01"}],
            list_reports_by_project=[{"title": "Relatório Q2", "meeting_number": 4, "meeting_date": "2026-07-05"}],
        )
        with patch.multiple("core.project_store", **overrides):
            result = list_all_business_assets("p1")
        for artifact_type in ("bmm", "dmn", "ibis", "report"):
            assert len(result[artifact_type]) == 1
            item = result[artifact_type][0]
            assert item["has_metadata_support"] is False
            assert item["metadata"] is None
            assert item["artifact_id"] is None

    def test_bpmn_and_sbvr_types_have_metadata_support(self):
        overrides = _patches(
            list_bpmn_processes=[{"id": "b1", "name": "Compras"}],
            list_sbvr_terms=[{"id": "t1", "term": "Cliente"}],
            list_sbvr_rules=[{"id": "ru1", "rule_id": "R001", "statement": "Todo cliente deve..."}],
            list_meetings=[{"id": "m1", "title": "Ata 1", "meeting_date": "2026-06-01", "minutes_md": "conteúdo"}],
        )
        with patch.multiple("core.project_store", **overrides):
            result = list_all_business_assets("p1")
        assert result["bpmn_process"][0]["has_metadata_support"] is True
        assert result["sbvr_term"][0]["has_metadata_support"] is True
        assert result["sbvr_rule"][0]["has_metadata_support"] is True
        assert result["meeting_minutes"][0]["has_metadata_support"] is True

    def test_meeting_without_minutes_excluded(self):
        overrides = _patches(
            list_meetings=[{"id": "m1", "title": "Sem ata", "meeting_date": "2026-06-01", "minutes_md": ""}],
        )
        with patch.multiple("core.project_store", **overrides):
            result = list_all_business_assets("p1")
        assert result["meeting_minutes"] == []
