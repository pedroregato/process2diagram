# tests/test_estimar_risco_requisito.py
"""
Tests for core/tools/tools_meetings_requirements.py::estimar_risco_requisito()
(melhorias/avaliacao-proposta-assistente-20260708.md, proposta #3): weighted
heuristic risk score per requirement (revisions, contradiction flag, missing
source_quote, vague/short description, high priority without advanced
status). No LLM, no semantic analysis — factors always shown alongside the
score, never a bare number.

No real DB calls.
"""

from unittest.mock import patch, MagicMock

from core.assistant_tools import AssistantToolExecutor

_LLM_CONFIG = {
    "api_key": "fake-key",
    "model": "fake-model",
    "provider_cfg": {"client_type": "openai_compatible", "default_model": "fake-model"},
}


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def in_(self, *a, **k):
        return self

    def execute(self):
        resp = MagicMock()
        resp.data = self._rows
        return resp


class _FakeDB:
    def __init__(self, tables: dict):
        self._tables = tables

    def table(self, name):
        return _FakeQuery(list(self._tables.get(name, [])))


def _executor(tables):
    ex = AssistantToolExecutor(project_id="proj-1", llm_config=_LLM_CONFIG)
    db = _FakeDB(tables)
    patcher = patch("modules.supabase_client.get_supabase_client", return_value=db)
    patcher.start()
    return ex, patcher


_LOW_RISK_REQ = {
    "id": "r1", "req_number": 1, "title": "Login simples",
    "description": "O sistema deve permitir login com e-mail e senha cadastrados previamente.",
    "priority": "low", "status": "implemented", "source_quote": "trecho real da transcrição",
}

_HIGH_RISK_REQ = {
    "id": "r2", "req_number": 2, "title": "Requisito arriscado",
    "description": "Deve ser adequado", "priority": "high", "status": "active", "source_quote": "",
}


class TestEstimarRiscoRequisito:
    def test_requisito_nao_encontrado(self):
        ex, patcher = _executor({"requirements": []})
        try:
            result = ex.estimar_risco_requisito(req_number=99)
        finally:
            patcher.stop()
        assert "99" in result and "não encontrado" in result.lower()

    def test_projeto_sem_requisitos(self):
        ex, patcher = _executor({"requirements": []})
        try:
            result = ex.estimar_risco_requisito()
        finally:
            patcher.stop()
        assert "nenhum requisito" in result.lower()

    def test_low_risk_requirement_scores_low(self):
        tables = {"requirements": [_LOW_RISK_REQ], "requirement_versions": []}
        ex, patcher = _executor(tables)
        try:
            result = ex.estimar_risco_requisito(req_number=1)
        finally:
            patcher.stop()
        assert "🟢 Baixo" in result
        assert "Nenhum fator de risco identificado" in result

    def test_high_risk_requirement_shows_all_contributing_factors(self):
        tables = {
            "requirements": [_HIGH_RISK_REQ],
            "requirement_versions": [
                {"requirement_id": "r2", "contradiction_flag": True},
                {"requirement_id": "r2", "contradiction_flag": False},
            ],
        }
        ex, patcher = _executor(tables)
        try:
            result = ex.estimar_risco_requisito(req_number=2)
        finally:
            patcher.stop()
        assert "score" in result.lower() or "Score" in result
        assert "contradição sinalizada" in result
        assert "sem source_quote" in result
        assert "descrição curta ou vaga" in result
        assert "prioridade alta" in result
        assert "🔴 Crítico" in result or "🟠 Alto" in result

    def test_ranking_sorted_by_score_descending(self):
        tables = {
            "requirements": [_LOW_RISK_REQ, _HIGH_RISK_REQ],
            "requirement_versions": [
                {"requirement_id": "r2", "contradiction_flag": True},
            ],
        }
        ex, patcher = _executor(tables)
        try:
            result = ex.estimar_risco_requisito(top_n=10)
        finally:
            patcher.stop()
        assert result.index("REQ-002") < result.index("REQ-001")

    def test_top_n_limits_ranking_size(self):
        reqs = [
            {**_LOW_RISK_REQ, "id": f"r{i}", "req_number": i}
            for i in range(1, 6)
        ]
        tables = {"requirements": reqs, "requirement_versions": []}
        ex, patcher = _executor(tables)
        try:
            result = ex.estimar_risco_requisito(top_n=2)
        finally:
            patcher.stop()
        assert result.count("REQ-") == 2
