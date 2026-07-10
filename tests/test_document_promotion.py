# tests/test_document_promotion.py
"""
Tests for core/project_store.py :: suggest_formal_classification_for_document()
(Ativos de Negócio — Fase B, melhorias/promocao-ativos-negocio.md §3.3): only
`document` has an automatic suggestion for Classificação Formal, derived from
its `document_types.category` — every other artifact_type is manual from the
start. The suggestion is only a pre-selection; the promotion form always lets
the user override it.
"""

from unittest.mock import patch

from core.project_store import (
    suggest_formal_classification_for_document,
    DOCUMENT_CATEGORY_TO_FORMAL_CLASSIFICATION,
)

_DOC_TYPES = [
    {"code": "CONTRATO", "category": "Contratos e Acordos"},
    {"code": "POLITICA", "category": "Normas e Políticas"},
    {"code": "ASIS", "category": "Processos"},
    {"code": "SWOT", "category": "Análise de Negócio"},
]


class TestSuggestFormalClassificationForDocument:
    def test_maps_known_category(self):
        with patch("core.project_store._get_document_types", return_value=_DOC_TYPES):
            result = suggest_formal_classification_for_document("CONTRATO")
        assert result == "AN-08"

    def test_maps_a_second_known_category(self):
        with patch("core.project_store._get_document_types", return_value=_DOC_TYPES):
            result = suggest_formal_classification_for_document("ASIS")
        assert result == "AN-03"

    def test_unknown_doc_type_returns_none(self):
        with patch("core.project_store._get_document_types", return_value=_DOC_TYPES):
            result = suggest_formal_classification_for_document("NAO_EXISTE")
        assert result is None

    def test_empty_document_types_returns_none_never_raises(self):
        with patch("core.project_store._get_document_types", return_value=[]):
            result = suggest_formal_classification_for_document("CONTRATO")
        assert result is None

    def test_category_mapping_covers_the_9_taxonomy_categories(self):
        assert set(DOCUMENT_CATEGORY_TO_FORMAL_CLASSIFICATION.keys()) == {
            "Contratos e Acordos", "Normas e Políticas", "Governança", "Técnico",
            "Processos", "Requisitos", "Análise de Negócio", "Qualidade",
            "Iniciação e Planejamento",
        }
