# tests/test_list_all_business_assets.py
"""
Tests for core/project_store.py :: list_all_business_assets() (Ativos de
Negócio — Fase A/B da promoção explícita, melhorias/promocao-ativos-negocio.md
§4): a partir desta versão, só aparecem os artefatos PROMOVIDOS (com linha em
asset_metadata) para os 6 tipos com suporte a governança (requirement/
bpmn_process/sbvr_term/sbvr_rule/meeting_minutes/document) — deixou de listar
automaticamente tudo que existe nas tabelas de origem (comportamento antigo,
PC164). Os 4 tipos somente-leitura (bmm/dmn/ibis/report) continuam listados
automaticamente, sem promoção.

Mocks the underlying listing/lookup functions directly — this test exercises
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
        "_list_documents": [],
        "list_assistant_artifacts_by_project": [],
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
            "meeting_minutes", "document", "assistant_artifact",
            "bmm", "dmn", "ibis", "report",
        }
        assert all(v == [] for v in result.values())

    def test_promoted_assistant_artifact_included_with_metadata(self):
        overrides = _patches(
            list_assistant_artifacts_by_project=[
                {"id": "a1", "title": "Análise de Tendências", "created_at": "2026-07-01T10:00:00",
                 "content_markdown": "## Achados\n...", "source_tool": "analisar_tendencias"},
            ],
            get_asset_metadata_map={
                ("assistant_artifact", "a1"): {"status": "ativo", "business_interest": "tatico"},
            },
        )
        with patch.multiple("core.project_store", **overrides):
            result = list_all_business_assets("p1")
        assert len(result["assistant_artifact"]) == 1
        item = result["assistant_artifact"][0]
        assert item["title"] == "Análise de Tendências"
        assert item["metadata"]["business_interest"] == "tatico"
        assert item["content_markdown"] == "## Achados\n..."
        assert item["source_tool"] == "analisar_tendencias"

    def test_unpromoted_assistant_artifact_excluded(self):
        overrides = _patches(
            list_assistant_artifacts_by_project=[{"id": "a1", "title": "Rascunho", "created_at": ""}],
        )
        with patch.multiple("core.project_store", **overrides):
            result = list_all_business_assets("p1")
        assert result["assistant_artifact"] == []

    def test_document_not_promoted_is_excluded(self):
        overrides = _patches(
            _list_documents=[{"id": "d1", "title": "Contrato de Fornecimento", "created_at": "2026-07-01T10:00:00"}],
        )
        with patch.multiple("core.project_store", **overrides):
            result = list_all_business_assets("p1")
        assert result["document"] == []

    def test_promoted_document_included_with_metadata(self):
        overrides = _patches(
            _list_documents=[{"id": "d1", "title": "Contrato de Fornecimento", "created_at": "2026-07-01T10:00:00"}],
            get_asset_metadata_map={
                ("document", "d1"): {
                    "status": "ativo", "formal_classification": "AN-08",
                },
            },
        )
        with patch.multiple("core.project_store", **overrides):
            result = list_all_business_assets("p1")
        assert len(result["document"]) == 1
        item = result["document"][0]
        assert item["title"] == "Contrato de Fornecimento"
        assert item["meeting_date"] == "2026-07-01"
        assert item["has_metadata_support"] is True
        assert item["metadata"]["formal_classification"] == "AN-08"

    def test_requirement_not_promoted_is_excluded(self):
        """Existing in the source table is no longer enough — only a row in
        asset_metadata (i.e. an explicit promotion) makes it appear."""
        overrides = _patches(
            list_requirements_light=[{"id": "r1", "req_number": 1, "title": "Login SSO"}],
        )
        with patch.multiple("core.project_store", **overrides):
            result = list_all_business_assets("p1")
        assert result["requirement"] == []

    def test_promoted_requirement_is_included_with_merged_metadata(self):
        overrides = _patches(
            list_requirements_light=[{"id": "r1", "req_number": 1, "title": "Login SSO"}],
            get_asset_metadata_map={
                ("requirement", "r1"): {
                    "status": "ativo", "owner": "Ana",
                    "business_interest": "estrategico", "business_perspective": ["ti"],
                },
            },
        )
        with patch.multiple("core.project_store", **overrides):
            result = list_all_business_assets("p1")
        assert len(result["requirement"]) == 1
        item = result["requirement"][0]
        assert item["artifact_id"] == "r1"
        assert item["has_metadata_support"] is True
        assert item["metadata"]["status"] == "ativo"
        assert item["metadata"]["owner"] == "Ana"
        assert item["metadata"]["business_interest"] == "estrategico"

    def test_promoted_requirement_missing_from_source_gets_fallback_title(self):
        """Promotion is never silently undone by the source row disappearing —
        the asset still shows up, with a fallback title instead of crashing."""
        overrides = _patches(
            list_requirements_light=[],  # r1 not found in the source table anymore
            get_asset_metadata_map={("requirement", "r1"): {"status": "ativo"}},
        )
        with patch.multiple("core.project_store", **overrides):
            result = list_all_business_assets("p1")
        assert len(result["requirement"]) == 1
        assert result["requirement"][0]["title"] == "(artefato de origem não encontrado)"

    def test_bmm_dmn_ibis_report_are_read_only_and_still_auto_listed(self):
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

    def test_bpmn_and_sbvr_types_only_listed_when_promoted(self):
        overrides = _patches(
            list_bpmn_processes=[{"id": "b1", "name": "Compras"}],
            list_sbvr_terms=[{"id": "t1", "term": "Cliente"}],
            list_sbvr_rules=[{"id": "ru1", "rule_id": "R001", "statement": "Todo cliente deve..."}],
            list_meetings=[{"id": "m1", "title": "Ata 1", "meeting_date": "2026-06-01", "minutes_md": "conteúdo"}],
            get_asset_metadata_map={
                ("bpmn_process", "b1"): {"status": "rascunho"},
                ("sbvr_term", "t1"): {"status": "rascunho"},
                ("sbvr_rule", "ru1"): {"status": "rascunho"},
                ("meeting_minutes", "m1"): {"status": "rascunho"},
            },
        )
        with patch.multiple("core.project_store", **overrides):
            result = list_all_business_assets("p1")
        assert result["bpmn_process"][0]["has_metadata_support"] is True
        assert result["bpmn_process"][0]["title"] == "Compras"
        assert result["sbvr_term"][0]["title"] == "Cliente"
        assert result["sbvr_rule"][0]["title"].startswith("R001")
        assert result["meeting_minutes"][0]["title"] == "Ata 1"

    def test_unpromoted_bpmn_and_sbvr_excluded_even_though_they_exist(self):
        overrides = _patches(
            list_bpmn_processes=[{"id": "b1", "name": "Compras"}],
            list_sbvr_terms=[{"id": "t1", "term": "Cliente"}],
            list_sbvr_rules=[{"id": "ru1", "rule_id": "R001", "statement": "..."}],
            list_meetings=[{"id": "m1", "title": "Ata 1", "meeting_date": "2026-06-01", "minutes_md": "conteúdo"}],
        )
        with patch.multiple("core.project_store", **overrides):
            result = list_all_business_assets("p1")
        assert result["bpmn_process"] == []
        assert result["sbvr_term"] == []
        assert result["sbvr_rule"] == []
        assert result["meeting_minutes"] == []

    def test_promoted_meeting_minutes_included_regardless_of_minutes_md(self):
        """Promotion state drives inclusion now, not the presence of
        minutes_md — a promoted meeting stays visible even if minutes_md
        was later cleared (edge case, not actively encouraged by the UI)."""
        overrides = _patches(
            list_meetings=[{"id": "m1", "title": "Sem ata", "meeting_date": "2026-06-01", "minutes_md": ""}],
            get_asset_metadata_map={("meeting_minutes", "m1"): {"status": "rascunho"}},
        )
        with patch.multiple("core.project_store", **overrides):
            result = list_all_business_assets("p1")
        assert len(result["meeting_minutes"]) == 1
