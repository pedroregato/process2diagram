# tests/test_tools_bpmn_generation_analysis.py
"""
Tests for the three PC135 assistant tools added to
core/tools/tools_bpmn_sbvr.py: ask_bpmn_diagram, generate_bpmn_diagram,
save_generated_bpmn. No real LLM/Supabase calls — all dependencies mocked
at their import source.
"""

from unittest.mock import patch, MagicMock

from core.assistant_tools import AssistantToolExecutor, _ADMIN_TOOLS
from core.knowledge_hub import KnowledgeHub, BPMNValidationScore, BPMNModel

_LLM_CONFIG = {
    "api_key": "fake-key",
    "model": "fake-model",
    "provider_cfg": {"client_type": "openai_compatible", "default_model": "fake-model"},
}

_PROCESSES = [{"id": "proc-1", "name": "Processo de Contratação", "version_count": 1}]
_VERSIONS = [{"id": "ver-1", "process_id": "proc-1", "version": 1, "is_current": True,
              "bpmn_xml": "<definitions><process id='p1'/></definitions>"}]


def _executor():
    return AssistantToolExecutor("proj-1", llm_config=_LLM_CONFIG)


class TestAskBpmnDiagram:
    def test_process_not_found(self):
        ex = _executor()
        with patch("core.project_store.list_bpmn_processes", return_value=[]):
            result = ex.ask_bpmn_diagram("Inexistente", "Descreva a fase X")
        assert "não encontrado" in result

    def test_ambiguous_match_lists_options(self):
        ex = _executor()
        procs = [{"id": "1", "name": "Processo A"}, {"id": "2", "name": "Processo AB"}]
        with patch("core.project_store.list_bpmn_processes", return_value=procs):
            result = ex.ask_bpmn_diagram("Processo A", "pergunta")
        assert "Múltiplos processos" in result

    def test_no_xml_stored(self):
        ex = _executor()
        with patch("core.project_store.list_bpmn_processes", return_value=_PROCESSES), \
             patch("core.project_store.list_bpmn_versions", return_value=[{"id": "v1", "is_current": True, "bpmn_xml": ""}]):
            result = ex.ask_bpmn_diagram("Contratação", "pergunta")
        assert "não possui XML" in result

    def test_calls_analyst_with_resolved_xml_and_question(self):
        ex = _executor()
        with patch("core.project_store.list_bpmn_processes", return_value=_PROCESSES), \
             patch("core.project_store.list_bpmn_versions", return_value=_VERSIONS), \
             patch("core.project_store.get_current_bpmn_version_id", return_value="ver-1"), \
             patch("core.project_store.list_bpmn_callactivity_diagrams", return_value=[]), \
             patch("agents.agent_bpmn_analyst.AgentBPMNAnalyst.answer", return_value="Resposta gerada.") as mock_answer:
            result = ex.ask_bpmn_diagram("Contratação", "Descreva o subprocesso X")
        assert result == "Resposta gerada."
        _, kwargs = mock_answer.call_args
        assert kwargs["process_name"] == "Processo de Contratação"
        assert kwargs["question"] == "Descreva o subprocesso X"
        assert "<definitions>" in kwargs["bpmn_xml"]

    def test_includes_matching_detail_diagram_in_context(self):
        ex = _executor()
        details = [{"element_name": "Contratar Consultoria", "bpmn_xml": "<definitions>detalhe</definitions>"}]
        with patch("core.project_store.list_bpmn_processes", return_value=_PROCESSES), \
             patch("core.project_store.list_bpmn_versions", return_value=_VERSIONS), \
             patch("core.project_store.get_current_bpmn_version_id", return_value="ver-1"), \
             patch("core.project_store.list_bpmn_callactivity_diagrams", return_value=details), \
             patch("agents.agent_bpmn_analyst.AgentBPMNAnalyst.answer", return_value="ok") as mock_answer:
            ex.ask_bpmn_diagram("Contratação", "Descreva a fase Contratar Consultoria")
        _, kwargs = mock_answer.call_args
        assert "Contratar Consultoria" in kwargs["detail_context"]
        assert "detalhe" in kwargs["detail_context"]

    def test_missing_llm_config_returns_error(self):
        ex = AssistantToolExecutor("proj-1", llm_config={})
        with patch("core.project_store.list_bpmn_processes", return_value=_PROCESSES), \
             patch("core.project_store.list_bpmn_versions", return_value=_VERSIONS):
            result = ex.ask_bpmn_diagram("Contratação", "pergunta")
        assert "Configuração de LLM não disponível" in result


class TestGenerateBpmnDiagram:
    def _fake_hub(self, name="Processo Teste"):
        h = KnowledgeHub.new()
        h.bpmn = BPMNModel(
            name=name,
            bpmn_xml='<?xml version="1.0"?><definitions><process id="p1"/></definitions>',
            mermaid="flowchart LR\n a-->b",
            ready=True,
        )
        h.validation.bpmn_score = BPMNValidationScore(weighted=7.5)
        return h

    def test_requires_meeting_or_description(self):
        ex = _executor()
        result = ex.generate_bpmn_diagram()
        assert "Informe meeting_number" in result

    def test_meeting_not_found(self):
        ex = _executor()
        with patch.object(AssistantToolExecutor, "_find_meeting", return_value=None):
            result = ex.generate_bpmn_diagram(meeting_number=99)
        assert "não encontrada" in result

    def test_meeting_without_transcript(self):
        ex = _executor()
        with patch.object(AssistantToolExecutor, "_find_meeting",
                           return_value={"id": "m1", "title": "Reuniao", "transcript_clean": "", "transcript_raw": ""}):
            result = ex.generate_bpmn_diagram(meeting_number=1)
        assert "não possui transcrição" in result

    def test_description_too_short(self):
        ex = _executor()
        result = ex.generate_bpmn_diagram(description="processo curto")
        assert "muito curto" in result

    def test_successful_generation_from_description(self):
        ex = _executor()
        description = " ".join(["palavra"] * 20)
        with patch("agents.agent_bpmn_studio.generate_bpmn_from_description",
                   return_value=self._fake_hub()) as mock_gen:
            result = ex.generate_bpmn_diagram(description=description, n_runs=2)
        assert "Diagrama gerado a partir de: descrição fornecida" in result
        assert "Processo Teste" in result
        assert "Score do torneio" in result
        assert "<definitions>" in result
        assert "save_generated_bpmn" in result
        _, kwargs = mock_gen.call_args
        assert kwargs["n_runs"] == 2

    def test_n_runs_capped_at_three(self):
        ex = _executor()
        description = " ".join(["palavra"] * 20)
        with patch("agents.agent_bpmn_studio.generate_bpmn_from_description",
                   return_value=self._fake_hub()) as mock_gen:
            ex.generate_bpmn_diagram(description=description, n_runs=99)
        _, kwargs = mock_gen.call_args
        assert kwargs["n_runs"] == 3

    def test_generation_from_meeting_transcript(self):
        ex = _executor()
        transcript = " ".join(["palavra"] * 20)
        with patch.object(AssistantToolExecutor, "_find_meeting",
                           return_value={"id": "m1", "title": "Reuniao de Kickoff", "transcript_clean": transcript}), \
             patch("agents.agent_bpmn_studio.generate_bpmn_from_description",
                   return_value=self._fake_hub()):
            result = ex.generate_bpmn_diagram(meeting_number=5)
        assert "Reunião 5" in result

    def test_generation_failure_returns_error(self):
        ex = _executor()
        description = " ".join(["palavra"] * 20)
        with patch("agents.agent_bpmn_studio.generate_bpmn_from_description",
                   side_effect=RuntimeError("todas as execuções falharam")):
            result = ex.generate_bpmn_diagram(description=description)
        assert "Erro ao gerar o diagrama" in result

    def test_missing_llm_config_returns_error(self):
        ex = AssistantToolExecutor("proj-1", llm_config={})
        description = " ".join(["palavra"] * 20)
        result = ex.generate_bpmn_diagram(description=description)
        assert "Configuração de LLM não disponível" in result


class TestSaveGeneratedBpmn:
    def test_empty_xml_rejected(self):
        ex = _executor()
        result = ex.save_generated_bpmn("Processo X", "")
        assert "XML BPMN vazio" in result

    def test_empty_name_rejected(self):
        ex = _executor()
        result = ex.save_generated_bpmn("", "<definitions/>")
        assert "Informe um nome" in result

    def test_successful_save(self):
        ex = _executor()
        with patch("core.project_store.save_bpmn_from_hub", return_value="new-process-id") as mock_save:
            result = ex.save_generated_bpmn("Processo Novo", "<definitions><process/></definitions>")
        assert "salvo com sucesso" in result
        assert "sem reunião vinculada" in result
        _, kwargs = mock_save.call_args
        assert kwargs["project_id"] == "proj-1"
        assert kwargs["hub"].bpmn.name == "Processo Novo"
        assert kwargs["hub"].bpmn.ready is True

    def test_save_with_meeting_link(self):
        ex = _executor()
        with patch.object(AssistantToolExecutor, "_find_meeting", return_value={"id": "m1"}), \
             patch("core.project_store.save_bpmn_from_hub", return_value="pid") as mock_save:
            result = ex.save_generated_bpmn("Processo Novo", "<definitions/>", meeting_number=3)
        assert "vinculado à Reunião 3" in result
        _, kwargs = mock_save.call_args
        assert kwargs["meeting_id"] == "m1"

    def test_save_failure_returns_error(self):
        ex = _executor()
        with patch("core.project_store.save_bpmn_from_hub", return_value=None):
            result = ex.save_generated_bpmn("Processo Novo", "<definitions/>")
        assert "Erro ao salvar" in result

    def test_is_registered_as_admin_only(self):
        assert "save_generated_bpmn" in _ADMIN_TOOLS
        assert "generate_bpmn_diagram" not in _ADMIN_TOOLS
        assert "ask_bpmn_diagram" not in _ADMIN_TOOLS


class TestToolDispatchWiring:
    def test_execute_routes_ask_bpmn_diagram(self):
        ex = _executor()
        with patch.object(AssistantToolExecutor, "ask_bpmn_diagram", return_value="ok") as mock_method:
            result = ex.execute("ask_bpmn_diagram", {"process_name": "P", "question": "Q"})
        assert result == "ok"
        mock_method.assert_called_once_with(process_name="P", question="Q")

    def test_execute_routes_generate_bpmn_diagram(self):
        ex = _executor()
        with patch.object(AssistantToolExecutor, "generate_bpmn_diagram", return_value="ok") as mock_method:
            ex.execute("generate_bpmn_diagram", {"description": "texto", "n_runs": 2})
        mock_method.assert_called_once_with(meeting_number=None, description="texto", n_runs=2)

    def test_execute_blocks_save_generated_bpmn_for_non_admin(self):
        ex = _executor()
        with patch("modules.auth.is_admin", return_value=False):
            result = ex.execute("save_generated_bpmn", {"process_name": "P", "bpmn_xml": "<x/>"})
        assert "administrador" in result

    def test_execute_allows_save_generated_bpmn_for_admin(self):
        ex = _executor()
        with patch("modules.auth.is_admin", return_value=True), \
             patch.object(AssistantToolExecutor, "save_generated_bpmn", return_value="ok") as mock_method:
            result = ex.execute("save_generated_bpmn", {"process_name": "P", "bpmn_xml": "<x/>"})
        assert result == "ok"
        mock_method.assert_called_once()
