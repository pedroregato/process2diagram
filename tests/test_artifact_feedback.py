# tests/test_artifact_feedback.py
"""
Tests for PC191 (melhorias/arquivados/aprimoramento-metacognitivo-3camadas.md,
Camada 1 — feedback leve em respostas do Assistente e artefatos gerados).

Covers:
  - core/project_store.py::save_feedback() / get_feedback_summary() (fail-open,
    agregação correta a partir de linhas cruas)
  - diagnostico_projeto()'s include_feedback check (isolado, sem DB real)

No real DB calls.
"""

from unittest.mock import patch, MagicMock

from core import project_store
from core.assistant_tools import AssistantToolExecutor

_LLM_CONFIG = {
    "api_key": "fake-key",
    "model": "fake-model",
    "provider_cfg": {"client_type": "openai_compatible", "default_model": "fake-model"},
}


# ── save_feedback / get_feedback_summary ──────────────────────────────────────

class TestSaveFeedback:
    def test_fail_open_when_db_unavailable(self):
        with patch.object(project_store, "_db", return_value=None):
            assert project_store.save_feedback("p1", "bpmn_process", "a1", 5) is False

    def test_success_path_inserts_expected_payload(self):
        db = MagicMock()
        with patch.object(project_store, "_db", return_value=db):
            ok = project_store.save_feedback(
                "p1", "meeting_minutes", "m1", 4,
                is_acceptable=True, comment="  bom trabalho  ",
                meeting_id="m1", created_by="pedro",
            )
        assert ok is True
        payload = db.table.return_value.insert.call_args[0][0]
        assert payload["project_id"] == "p1"
        assert payload["artifact_type"] == "meeting_minutes"
        assert payload["artifact_id"] == "m1"
        assert payload["rating"] == 4
        assert payload["is_acceptable"] is True
        assert payload["comment"] == "bom trabalho"  # trimmed

    def test_fail_open_on_exception(self):
        db = MagicMock()
        db.table.side_effect = Exception("boom")
        with patch.object(project_store, "_db", return_value=db):
            assert project_store.save_feedback("p1", "bpmn_process", "a1", 3) is False


class TestGetFeedbackSummary:
    def test_fail_open_when_db_unavailable(self):
        with patch.object(project_store, "_db", return_value=None):
            assert project_store.get_feedback_summary("p1") == {}

    def test_empty_rows_returns_empty_dict(self):
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []
        with patch.object(project_store, "_db", return_value=db):
            assert project_store.get_feedback_summary("p1") == {}

    def test_aggregates_avg_rating_and_acceptance_rate_per_type(self):
        rows = [
            {"artifact_type": "bpmn_process", "rating": 5, "is_acceptable": True},
            {"artifact_type": "bpmn_process", "rating": 1, "is_acceptable": False},
            {"artifact_type": "bpmn_process", "rating": 3, "is_acceptable": True},
            {"artifact_type": "assistant_response", "rating": 5, "is_acceptable": None},
            {"artifact_type": "assistant_response", "rating": 1, "is_acceptable": None},
        ]
        db = MagicMock()
        db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = rows
        with patch.object(project_store, "_db", return_value=db):
            summary = project_store.get_feedback_summary("p1")

        assert summary["bpmn_process"]["count"] == 3
        assert summary["bpmn_process"]["avg_rating"] == 3.0
        assert summary["bpmn_process"]["acceptance_rate"] == round(2 / 3, 2)

        # assistant_response never sets is_acceptable → no acceptance_rate key at all
        assert summary["assistant_response"]["count"] == 2
        assert summary["assistant_response"]["avg_rating"] == 3.0
        assert "acceptance_rate" not in summary["assistant_response"]

    def test_fail_open_on_exception(self):
        db = MagicMock()
        db.table.side_effect = Exception("boom")
        with patch.object(project_store, "_db", return_value=db):
            assert project_store.get_feedback_summary("p1") == {}


# ── diagnostico_projeto() include_feedback ────────────────────────────────────

def _executor():
    ex = AssistantToolExecutor(project_id="proj-1", llm_config=_LLM_CONFIG)
    # minutes_md preenchido: o check "3. Reuniões sem ata" não tem flag
    # include_* (roda sempre) — sem isso, todo teste daqui ganharia um
    # 🟡 Atenção espúrio não relacionado a feedback.
    ex._get_meetings = lambda: [{"id": "m1", "meeting_number": 1, "minutes_md": "ata"}]
    return ex


def _run_isolated(ex, feedback_summary, **kwargs):
    with patch(
        "core.project_store.get_feedback_summary", return_value=feedback_summary
    ):
        return ex.diagnostico_projeto(
            include_integrity=False, include_contradictions=False, include_roi=False,
            include_recurring=False, include_pendencies=False,
            include_revision_requests=False, **kwargs,
        )


class TestDiagnosticoProjetoFeedback:
    def test_low_acceptance_rate_is_critico(self):
        result = _run_isolated(_executor(), {
            "bpmn_process": {"count": 5, "avg_rating": 2.1, "acceptance_rate": 0.4},
        })
        assert "Processos BPMN" in result
        assert "40%" in result
        assert "🔴 Crítico" in result

    def test_medium_low_acceptance_rate_is_alerta_not_critico(self):
        result = _run_isolated(_executor(), {
            "meeting_minutes": {"count": 5, "avg_rating": 3.2, "acceptance_rate": 0.6},
        })
        assert "Atas" in result
        assert "60%" in result
        assert "🟡 Atenção" in result
        assert "🔴 Crítico" not in result

    def test_high_acceptance_rate_is_ok(self):
        result = _run_isolated(_executor(), {
            "bpmn_process": {"count": 5, "avg_rating": 4.5, "acceptance_rate": 0.9},
        })
        assert "🟢 OK" in result
        assert "🔴 Crítico" not in result
        assert "🟡 Atenção" not in result

    def test_assistant_response_uses_avg_rating_not_acceptance(self):
        result = _run_isolated(_executor(), {
            "assistant_response": {"count": 4, "avg_rating": 2.2},
        })
        assert "Respostas do Assistente" in result
        assert "2.2/5" in result
        assert "🟡 Atenção" in result

    def test_below_minimum_count_is_ignored(self):
        """_MIN_FEEDBACK_COUNT=3 — 2 avaliações não bastam pra virar sinal,
        evita falso positivo de baixo volume (mesmo princípio de
        detect_error_anomalies, services/llm_telemetry.py)."""
        result = _run_isolated(_executor(), {
            "bpmn_process": {"count": 2, "avg_rating": 1.0, "acceptance_rate": 0.0},
        })
        assert "Processos BPMN" not in result
        assert "volume insuficiente" in result

    def test_empty_summary_reports_insufficient_volume(self):
        result = _run_isolated(_executor(), {})
        assert "volume insuficiente" in result

    def test_disabled_by_flag(self):
        result = _run_isolated(
            _executor(),
            {"bpmn_process": {"count": 5, "avg_rating": 1.0, "acceptance_rate": 0.1}},
            include_feedback=False,
        )
        assert "Processos BPMN" not in result
        assert "volume insuficiente" not in result
