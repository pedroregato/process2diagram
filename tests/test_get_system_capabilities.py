# tests/test_get_system_capabilities.py
# Guards get_system_capabilities() against staleness — it drifted for many PCs (tool list
# hardcoded, missing pages/providers) before the tool section was made dynamic (PC193).
from __future__ import annotations

from core.assistant_tools import AssistantToolExecutor, get_tool_catalog


def _capabilities_text() -> str:
    executor = AssistantToolExecutor("test-project-id")
    return executor.get_system_capabilities()


def test_no_circular_import_and_returns_string():
    text = _capabilities_text()
    assert isinstance(text, str)
    assert "Funcionalidades do Process2Diagram" in text


def test_tool_section_is_generated_from_real_catalog():
    text = _capabilities_text()
    catalog_names = {t["name"] for t in get_tool_catalog()}
    # A handful of tools added well after the original hardcoded list was written —
    # if these are missing, the section reverted to a stale hand-maintained list.
    for recent_tool in (
        "diagnostico_projeto",
        "promover_ativo_negocio",
        "pesquisar_multi_contexto",
        "mapa_rastreabilidade",
    ):
        assert recent_tool in catalog_names, f"{recent_tool} missing from get_tool_catalog()"
        assert recent_tool in text, f"{recent_tool} missing from get_system_capabilities() output"


def test_mentions_azure_openai_provider():
    assert "Azure OpenAI" in _capabilities_text()


def test_mentions_ajuda_and_guias_groups():
    text = _capabilities_text()
    assert "Ajuda" in text
    assert "Guias" in text
    assert "Cache LLM" in text
    assert "Manifesto de Engenharia" in text


def test_mentions_provocations_agent_card():
    # AgentProvocations (PC190) is registered as an Agent Card — should surface
    # automatically without needing a separate hardcoded mention.
    assert "Provoca" in _capabilities_text()
