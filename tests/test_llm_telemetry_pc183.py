# tests/test_llm_telemetry_pc183.py
"""
PC183 — new query/aggregation helpers on LLMTelemetry:
  - query_error_rate_by_provider() / detect_error_anomalies()
  - query_recent_errors()
  - query_schema_validation_rate()
  - record_validation()
All fail-open (return {}/[] on any Supabase error) — verified with a mocked
Supabase client, no real network call.
"""

from unittest.mock import MagicMock, patch

from services.llm_telemetry import LLMTelemetry, TelemetryRecord


def _mock_db_returning(rows):
    """Builds a MagicMock chain matching supabase-py's fluent query builder,
    where every chained method returns the same mock and .execute() yields rows."""
    db = MagicMock()
    query = db.table.return_value
    # every filter/order/limit call must return the same chainable mock
    for method in ("select", "eq", "gte", "order", "limit"):
        getattr(query, method).return_value = query
    query.execute.return_value = MagicMock(data=rows)
    return db


class TestQueryErrorRateByProvider:
    def test_computes_rate_per_provider(self):
        rows = [
            {"provider": "deepseek", "is_error": True},
            {"provider": "deepseek", "is_error": False},
            {"provider": "deepseek", "is_error": False},
            {"provider": "openai", "is_error": False},
        ]
        tele = LLMTelemetry()
        with patch("modules.supabase_client.get_supabase_client", return_value=_mock_db_returning(rows)):
            stats = tele.query_error_rate_by_provider(hours=24)

        assert stats["deepseek"]["total"] == 3
        assert stats["deepseek"]["errors"] == 1
        assert abs(stats["deepseek"]["error_rate"] - 1 / 3) < 1e-9
        assert stats["openai"]["error_rate"] == 0.0

    def test_returns_empty_dict_on_supabase_error(self):
        tele = LLMTelemetry()
        with patch("modules.supabase_client.get_supabase_client", side_effect=Exception("down")):
            assert tele.query_error_rate_by_provider() == {}

    def test_returns_empty_dict_when_client_unconfigured(self):
        tele = LLMTelemetry()
        with patch("modules.supabase_client.get_supabase_client", return_value=None):
            assert tele.query_error_rate_by_provider() == {}


class TestDetectErrorAnomalies:
    def test_flags_provider_above_threshold_with_enough_calls(self):
        rows = [{"provider": "deepseek", "is_error": True}] * 3 + \
               [{"provider": "deepseek", "is_error": False}] * 7  # 30% error, 10 calls
        tele = LLMTelemetry()
        with patch("modules.supabase_client.get_supabase_client", return_value=_mock_db_returning(rows)):
            anomalies = tele.detect_error_anomalies(hours=24, min_calls=5, error_rate_threshold=0.15)

        assert len(anomalies) == 1
        assert anomalies[0]["provider"] == "deepseek"

    def test_ignores_low_volume_noise_below_min_calls(self):
        # 1 error out of 1 call = 100% but must not be flagged (min_calls=5)
        rows = [{"provider": "flaky", "is_error": True}]
        tele = LLMTelemetry()
        with patch("modules.supabase_client.get_supabase_client", return_value=_mock_db_returning(rows)):
            anomalies = tele.detect_error_anomalies(hours=24, min_calls=5, error_rate_threshold=0.15)

        assert anomalies == []

    def test_no_anomalies_when_all_below_threshold(self):
        rows = [{"provider": "deepseek", "is_error": False}] * 10
        tele = LLMTelemetry()
        with patch("modules.supabase_client.get_supabase_client", return_value=_mock_db_returning(rows)):
            anomalies = tele.detect_error_anomalies(hours=24, min_calls=5, error_rate_threshold=0.15)

        assert anomalies == []


class TestQueryRecentErrors:
    def test_returns_rows_on_success(self):
        rows = [{"agent_name": "bpmn", "provider": "deepseek", "model": "deepseek-v4-flash",
                  "error_message": "conteúdo vazio", "created_at": "2026-07-12T10:00:00Z"}]
        tele = LLMTelemetry()
        with patch("modules.supabase_client.get_supabase_client", return_value=_mock_db_returning(rows)):
            result = tele.query_recent_errors(hours=24, limit=20)

        assert result == rows

    def test_fail_open_on_error(self):
        tele = LLMTelemetry()
        with patch("modules.supabase_client.get_supabase_client", side_effect=Exception("down")):
            assert tele.query_recent_errors() == []


class TestQuerySchemaValidationRate:
    def test_returns_rows(self):
        rows = [
            {"agent_name": "bpmn", "skill_version": "1.2", "schema_valid": True, "created_at": "2026-07-12T10:00:00Z"},
            {"agent_name": "bpmn", "skill_version": "1.2", "schema_valid": False, "created_at": "2026-07-12T11:00:00Z"},
        ]
        tele = LLMTelemetry()
        with patch("modules.supabase_client.get_supabase_client", return_value=_mock_db_returning(rows)):
            result = tele.query_schema_validation_rate(days=30)

        assert result == rows

    def test_fail_open_on_error(self):
        tele = LLMTelemetry()
        with patch("modules.supabase_client.get_supabase_client", side_effect=Exception("down")):
            assert tele.query_schema_validation_rate() == []


class TestRecordValidation:
    def test_builds_record_with_expected_fields_and_calls_record(self):
        tele = LLMTelemetry()
        with patch.object(tele, "record") as mock_record:
            tele.record_validation("bpmn", "1.2", True)

        assert mock_record.called
        rec: TelemetryRecord = mock_record.call_args[0][0]
        assert rec.agent_name == "bpmn"
        assert rec.skill_version == "1.2"
        assert rec.is_validation_event is True
        assert rec.schema_valid is True
        assert rec.latency_ms == 0
