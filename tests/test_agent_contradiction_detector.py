# tests/test_agent_contradiction_detector.py
"""
Tests for agents/agent_contradiction_detector.py::_call_and_store() (PC206-fix).

Bug real encontrado testando o projeto AURORA na prática: contradições
detectadas via "Full Scan" (_run_fullscan_mode, botão admin/Assistente)
gravavam meeting_a_id=None PERMANENTEMENTE — o código atribuía
`"meeting_a_id": meeting_id` direto do parâmetro, sem nunca resolver por
fato (diferente de meeting_b_id, que já era resolvido via fact_b_id).
_run_fullscan_mode chama _call_and_store(meeting_id=None, ...) de propósito
(não há "reunião atual" numa varredura completa) — então TODA contradição de
full-scan nascia sem meeting_a_id, e nunca conseguia passar em
AgentProvocations.bridge_contradictions() (PC200), que exige
meeting_a_id == a reunião sendo iterada. Confirmado com dado real do
projeto AURORA: 8 contradições genuínas (relation_type/severity corretos),
zero bridged, porque as 8 tinham sido detectadas via full-scan.

Nenhum teste existia pra este arquivo antes deste PC.
"""

from unittest.mock import patch

from agents.agent_contradiction_detector import AgentContradictionDetector


FACT_A = {"id": "fact-a", "fact_type": "deadline", "content": "Prazo X", "source_meeting_ids": ["mtg-1"]}
FACT_B = {"id": "fact-b", "fact_type": "deadline", "content": "Prazo Y", "source_meeting_ids": ["mtg-2"]}


def _agent() -> AgentContradictionDetector:
    return AgentContradictionDetector({}, {})


def _llm_contradiction(**overrides) -> dict:
    base = {
        "description": "Fato A contradiz fato B",
        "confidence": 0.9,
        "relation_type": "contradiction_direct",
        "fact_a_id": "fact-a",
        "fact_b_id": "fact-b",
        "severity": "high",
    }
    base.update(overrides)
    return base


class TestCallAndStoreMeetingResolution:
    def test_compare_mode_uses_passed_meeting_id_for_meeting_a(self):
        """Modo compare (pipeline): meeting_id é sempre a reunião real sendo
        processada — deve continuar sendo usado tal qual, sem regressão."""
        agent = _agent()
        with patch.object(agent, "_call_with_retry", return_value={"contradictions": [_llm_contradiction()]}), \
             patch("core.knowledge_store.insert_contradiction", return_value={"id": "kh-1"}) as mock_insert:
            n = agent._call_and_store(
                project_id="proj-1", meeting_id="mtg-2",
                new_facts=[FACT_A], existing_facts=[FACT_B],
            )

        assert n == 1
        payload = mock_insert.call_args[0][1]
        assert payload["meeting_a_id"] == "mtg-2"   # meeting_id passado, não fact_a_id resolvido (fact-a -> mtg-1)
        assert payload["meeting_b_id"] == "mtg-2"    # resolvido via fact_b_id (fact-b -> mtg-2)

    def test_fullscan_mode_resolves_meeting_a_id_from_fact_a_id(self):
        """Regressão do bug real: modo full-scan (meeting_id=None) precisa
        resolver meeting_a_id a partir de fact_a_id, não gravar None."""
        agent = _agent()
        with patch.object(agent, "_call_with_retry", return_value={"contradictions": [_llm_contradiction()]}), \
             patch("core.knowledge_store.insert_contradiction", return_value={"id": "kh-1"}) as mock_insert:
            n = agent._call_and_store(
                project_id="proj-1", meeting_id=None,
                new_facts=[FACT_A, FACT_B], existing_facts=[],
            )

        assert n == 1
        payload = mock_insert.call_args[0][1]
        assert payload["meeting_a_id"] == "mtg-1"  # resolvido via fact_a_id -> FACT_A -> mtg-1
        assert payload["meeting_b_id"] == "mtg-2"  # resolvido via fact_b_id -> FACT_B -> mtg-2

    def test_fullscan_mode_meeting_a_id_none_when_fact_a_id_missing(self):
        """Sem fact_a_id no output do LLM, meeting_a_id continua None —
        fail-open, sem lançar exceção (mesmo comportamento de antes do fix
        pra esse caso específico)."""
        agent = _agent()
        contradiction = _llm_contradiction()
        del contradiction["fact_a_id"]
        with patch.object(agent, "_call_with_retry", return_value={"contradictions": [contradiction]}), \
             patch("core.knowledge_store.insert_contradiction", return_value={"id": "kh-1"}) as mock_insert:
            agent._call_and_store(
                project_id="proj-1", meeting_id=None,
                new_facts=[FACT_A, FACT_B], existing_facts=[],
            )

        payload = mock_insert.call_args[0][1]
        assert payload["meeting_a_id"] is None
        assert payload["meeting_b_id"] == "mtg-2"  # lado B continua resolvido normalmente

    def test_fullscan_mode_unknown_fact_a_id_yields_none(self):
        """fact_a_id que não corresponde a nenhum fato conhecido -> None,
        não lança KeyError."""
        agent = _agent()
        with patch.object(agent, "_call_with_retry",
                           return_value={"contradictions": [_llm_contradiction(fact_a_id="fact-inexistente")]}), \
             patch("core.knowledge_store.insert_contradiction", return_value={"id": "kh-1"}) as mock_insert:
            agent._call_and_store(
                project_id="proj-1", meeting_id=None,
                new_facts=[FACT_A, FACT_B], existing_facts=[],
            )

        payload = mock_insert.call_args[0][1]
        assert payload["meeting_a_id"] is None
