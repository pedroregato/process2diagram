# tests/test_agent_bpmn_analyst.py
"""
Tests for agents/agent_bpmn_analyst.py::AgentBPMNAnalyst (PC135).

No real LLM calls — _call_llm is mocked at the class level. Covers prompt
assembly (process name, cleaned XML, detail context, question) and the
DI-stripping helper.
"""

from unittest.mock import patch

from agents.agent_bpmn_analyst import AgentBPMNAnalyst

_CLIENT_INFO = {"api_key": "fake"}
_PROVIDER_CFG = {"client_type": "openai_compatible", "default_model": "fake-model"}

_XML_WITH_DI = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL" '
    'xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI" '
    'xmlns:dc="http://www.omg.org/spec/DD/20100524/DC">'
    '<process id="p1">'
    '<startEvent id="s1" name="Inicio"/>'
    '<callActivity id="ca1" name="Contratar Consultoria">'
    '<documentation>Fase de contratacao com fornecedor externo.</documentation>'
    '</callActivity>'
    '<endEvent id="e1" name="Fim"/>'
    '</process>'
    '<bpmndi:BPMNDiagram id="d1">'
    '<bpmndi:BPMNPlane id="pl1">'
    '<bpmndi:BPMNShape id="s1_di" bpmnElement="s1"><dc:Bounds x="0" y="0" width="36" height="36"/></bpmndi:BPMNShape>'
    '</bpmndi:BPMNPlane>'
    '</bpmndi:BPMNDiagram>'
    '</definitions>'
)


class TestStripDiagramInterchange:
    def test_removes_bpmndi_section(self):
        cleaned = AgentBPMNAnalyst._strip_diagram_interchange(_XML_WITH_DI)
        assert "BPMNDiagram" not in cleaned
        assert "BPMNShape" not in cleaned

    def test_preserves_semantic_content(self):
        cleaned = AgentBPMNAnalyst._strip_diagram_interchange(_XML_WITH_DI)
        assert "Contratar Consultoria" in cleaned
        assert "Fase de contratacao com fornecedor externo." in cleaned
        assert 'id="s1"' in cleaned
        assert 'id="e1"' in cleaned

    def test_no_mangled_namespace_prefixes(self):
        cleaned = AgentBPMNAnalyst._strip_diagram_interchange(_XML_WITH_DI)
        assert "ns0:" not in cleaned

    def test_malformed_xml_fails_open(self):
        malformed = "<definitions><process><unclosed></process>"
        assert AgentBPMNAnalyst._strip_diagram_interchange(malformed) == malformed

    def test_empty_string(self):
        assert AgentBPMNAnalyst._strip_diagram_interchange("") == ""


class TestBuildPrompt:
    def _agent(self):
        return AgentBPMNAnalyst(_CLIENT_INFO, _PROVIDER_CFG)

    def test_includes_process_name_and_question(self):
        agent = self._agent()
        system, user = agent._build_prompt(
            "Processo de Teste", _XML_WITH_DI, "Descreva a fase Contratar Consultoria", "", "Auto-detect"
        )
        assert "Processo de Teste" in user
        assert "Descreva a fase Contratar Consultoria" in user
        assert "Contratar Consultoria" in user  # from the cleaned XML

    def test_strips_di_from_user_prompt(self):
        agent = self._agent()
        _, user = agent._build_prompt("P", _XML_WITH_DI, "pergunta", "", "Auto-detect")
        assert "BPMNDiagram" not in user

    def test_includes_detail_context_when_provided(self):
        agent = self._agent()
        detail_xml = "### Detalhamento de 'Contratar Consultoria'\n```xml\n<definitions/>\n```"
        _, user = agent._build_prompt("P", _XML_WITH_DI, "pergunta", detail_xml, "Auto-detect")
        assert "Detalhamentos de fase já disponíveis" in user
        assert detail_xml in user

    def test_omits_detail_section_when_absent(self):
        agent = self._agent()
        _, user = agent._build_prompt("P", _XML_WITH_DI, "pergunta", "", "Auto-detect")
        assert "Detalhamentos de fase já disponíveis" not in user

    def test_system_prompt_includes_skill_and_language(self):
        agent = self._agent()
        system, _ = agent._build_prompt("P", _XML_WITH_DI, "pergunta", "", "Portuguese (BR)")
        assert "BPMN" in system
        assert "Brazilian Portuguese" in system


class TestAnswer:
    def test_answer_returns_llm_response(self):
        agent = AgentBPMNAnalyst(_CLIENT_INFO, _PROVIDER_CFG)
        with patch.object(AgentBPMNAnalyst, "_call_llm", return_value="  Resposta do LLM.  ") as mock_call:
            result = agent.answer("Processo X", _XML_WITH_DI, "Descreva a fase Y")
        assert result == "Resposta do LLM."
        mock_call.assert_called_once()

    def test_answer_fails_open_on_llm_exception(self):
        agent = AgentBPMNAnalyst(_CLIENT_INFO, _PROVIDER_CFG)
        with patch.object(AgentBPMNAnalyst, "_call_llm", side_effect=RuntimeError("boom")):
            result = agent.answer("Processo X", _XML_WITH_DI, "Descreva a fase Y")
        assert "Erro ao consultar o diagrama" in result
        assert "boom" in result
