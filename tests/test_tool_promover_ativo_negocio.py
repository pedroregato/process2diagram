# tests/test_tool_promover_ativo_negocio.py
"""
Tests for AssistantToolExecutor.promover_ativo_negocio() (Ativos de Negócio —
Fase C, melhorias/promocao-ativos-negocio.md §6): lets the user ask the
Assistant, in natural language, to promote content it just produced to a
business asset. Thin validating wrapper over
core.project_store.promote_assistant_output_to_asset() — same 3 mandatory
classifications, plus tool-specific validation of enum values before ever
touching the DB.
"""

from unittest.mock import patch

from core.assistant_tools import AssistantToolExecutor


def _executor():
    return AssistantToolExecutor("p1", {})


class TestPromoverAtivoNegocio:
    def test_promotes_with_valid_input(self):
        with patch("core.project_store.promote_assistant_output_to_asset", return_value={"id": "a1"}) as mocked:
            result = _executor().promover_ativo_negocio(
                titulo="Análise de Tendências — Q3",
                conteudo="## Requisitos mais instáveis\n...",
                interesse="tatico",
                perspectiva=["governanca", "ti"],
                justificativa="Diretoria pediu acompanhamento mensal.",
            )
        assert "✅" in result
        assert "Análise de Tendências" in result
        mocked.assert_called_once()
        _, kwargs = mocked.call_args
        assert kwargs["business_interest"] == "tatico"
        assert kwargs["business_perspective"] == ["governanca", "ti"]
        assert kwargs["source_tool"] == "promover_ativo_negocio"

    def test_invalid_interest_rejected_before_db_call(self):
        with patch("core.project_store.promote_assistant_output_to_asset") as mocked:
            result = _executor().promover_ativo_negocio(
                titulo="X", conteudo="Y", interesse="urgente",
                perspectiva=["ti"], justificativa="motivo",
            )
        assert "inválido" in result.lower()
        mocked.assert_not_called()

    def test_invalid_perspective_filtered_and_rejected_if_empty(self):
        with patch("core.project_store.promote_assistant_output_to_asset") as mocked:
            result = _executor().promover_ativo_negocio(
                titulo="X", conteudo="Y", interesse="estrategico",
                perspectiva=["departamento_inexistente"], justificativa="motivo",
            )
        assert "perspectiva" in result.lower()
        mocked.assert_not_called()

    def test_unknown_formal_classification_silently_ignored_not_rejected(self):
        """A classificação formal é opcional — um valor inválido não deve
        bloquear a promoção, só ser descartado (mesmo espírito de
        'nunca força, só sugere' do resto da Fase C)."""
        with patch("core.project_store.promote_assistant_output_to_asset", return_value={"id": "a1"}) as mocked:
            result = _executor().promover_ativo_negocio(
                titulo="X", conteudo="Y", interesse="estrategico",
                perspectiva=["ti"], justificativa="motivo",
                classificacao_formal="AN-99",
            )
        assert "✅" in result
        _, kwargs = mocked.call_args
        assert kwargs["formal_classification"] is None

    def test_blank_justification_rejected_before_db_call(self):
        with patch("core.project_store.promote_assistant_output_to_asset") as mocked:
            result = _executor().promover_ativo_negocio(
                titulo="X", conteudo="Y", interesse="estrategico",
                perspectiva=["ti"], justificativa="   ",
            )
        assert "justificativa" in result.lower()
        mocked.assert_not_called()

    def test_db_failure_reported_without_raising(self):
        with patch("core.project_store.promote_assistant_output_to_asset", return_value=None):
            result = _executor().promover_ativo_negocio(
                titulo="X", conteudo="Y", interesse="estrategico",
                perspectiva=["ti"], justificativa="motivo",
            )
        assert "não foi possível" in result.lower()

    def test_registered_in_dispatch_and_schema(self):
        from core.assistant_tools import get_tool_schemas_openai
        names = [s["function"]["name"] for s in get_tool_schemas_openai()]
        assert "promover_ativo_negocio" in names

    def test_not_admin_only(self):
        from core.assistant_tools import _ADMIN_TOOLS
        assert "promover_ativo_negocio" not in _ADMIN_TOOLS
