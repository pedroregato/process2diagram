# tests/test_llm_telemetry_pc207.py
"""
PC207 — observabilidade de Provocações por reunião:
  - record_provocations_outcome()
  - query_provocations_diagnostics()

Antes desta PC, o resultado do validador determinístico de AgentProvocations
(aprovadas/rejeitadas + motivo, já calculado em hub.provocations) só existia
em memória e num logging.info() efêmero — sem jeito de perguntar "por que a
reunião X não gerou provocações" sem abrir os logs do processo. Mesmo padrão
de mock de tests/test_llm_telemetry_pc183.py — _mock_db_returning(), sem
chamada de rede real.
"""

from unittest.mock import MagicMock, patch

from services.llm_telemetry import LLMTelemetry, TelemetryRecord


def _mock_db_returning(rows):
    """Builds a MagicMock chain matching supabase-py's fluent query builder,
    where every chained method returns the same mock and .execute() yields rows."""
    db = MagicMock()
    query = db.table.return_value
    for method in ("select", "eq", "gte", "order", "limit"):
        getattr(query, method).return_value = query
    query.execute.return_value = MagicMock(data=rows)
    return db


class TestRecordProvocationsOutcome:
    def test_builds_record_with_expected_fields_and_calls_record(self):
        tele = LLMTelemetry()
        with patch.object(tele, "record") as mock_record:
            tele.record_provocations_outcome(
                project_id="proj-1", meeting_id="mtg-1", skill_version="1.3",
                approved_count=2, rejected_count=3,
                rejected_reasons={"reference_not_found": 2, "premise_marker_missing": 1},
            )

        assert mock_record.called
        rec: TelemetryRecord = mock_record.call_args[0][0]
        assert rec.agent_name == "provocations"
        assert rec.project_id == "proj-1"
        assert rec.meeting_id == "mtg-1"
        assert rec.skill_version == "1.3"
        assert rec.approved_count == 2
        assert rec.rejected_count == 3
        assert rec.rejected_reasons == {"reference_not_found": 2, "premise_marker_missing": 1}
        assert rec.latency_ms == 0  # evento diagnóstico, não uma chamada LLM

    def test_accepts_none_project_and_meeting_id(self):
        """Fail-open na chamada: nunca deve lançar mesmo com ids ausentes."""
        tele = LLMTelemetry()
        with patch.object(tele, "record") as mock_record:
            tele.record_provocations_outcome(
                project_id=None, meeting_id=None, skill_version=None,
                approved_count=0, rejected_count=0, rejected_reasons={},
            )
        rec: TelemetryRecord = mock_record.call_args[0][0]
        assert rec.project_id is None
        assert rec.meeting_id is None


class TestQueryProvocationsDiagnostics:
    def test_returns_rows_filtered_by_project_and_meeting(self):
        rows = [{
            "meeting_id": "mtg-1", "skill_version": "1.3",
            "approved_count": 1, "rejected_count": 2,
            "rejected_reasons": {"reference_not_found": 2},
            "created_at": "2026-07-26T10:00:00Z",
        }]
        tele = LLMTelemetry()
        with patch("modules.supabase_client.get_supabase_client", return_value=_mock_db_returning(rows)):
            result = tele.query_provocations_diagnostics("proj-1", "mtg-1")

        assert result == rows

    def test_meeting_id_is_optional(self):
        rows = [{"meeting_id": "mtg-2", "approved_count": 0, "rejected_count": 0,
                  "rejected_reasons": None, "skill_version": None, "created_at": "x"}]
        tele = LLMTelemetry()
        with patch("modules.supabase_client.get_supabase_client", return_value=_mock_db_returning(rows)):
            result = tele.query_provocations_diagnostics("proj-1")

        assert result == rows

    def test_fail_open_on_error(self):
        tele = LLMTelemetry()
        with patch("modules.supabase_client.get_supabase_client", side_effect=Exception("down")):
            assert tele.query_provocations_diagnostics("proj-1") == []

    def test_fail_open_when_client_unconfigured(self):
        tele = LLMTelemetry()
        with patch("modules.supabase_client.get_supabase_client", return_value=None):
            assert tele.query_provocations_diagnostics("proj-1") == []
