# tests/test_list_bmm_by_project.py
"""
Tests for core/project_store.py :: list_bmm_by_project / list_reports_by_project
(Ativos de Negócio — Etapa 1, melhorias/cognicao-de-negocio.md): read-only
listing for the artifact types that have no dedicated table (BMM lives only
in meetings.bmm_json; reports only in meetings.report_html — no project-wide
listing function existed for reports before this).

No real DB calls.
"""

import json
from unittest.mock import MagicMock, patch

from core.project_store import list_bmm_by_project, list_reports_by_project


class _NotChain:
    def __init__(self, query):
        self._query = query

    def is_(self, *a, **k):
        return self._query


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    @property
    def not_(self):
        return _NotChain(self)

    def execute(self):
        resp = MagicMock()
        resp.data = self._rows
        return resp


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows

    def table(self, name):
        return _FakeQuery(list(self._rows))


class TestListBmmByProject:
    def test_returns_bmm_enriched_with_meeting_info(self):
        rows = [{
            "id": "m1", "meeting_number": 1, "title": "Kickoff", "meeting_date": "2026-06-01",
            "bmm_json": json.dumps({"vision": "Ser referência", "mission": "Entregar valor",
                                     "goals": [], "strategies": [], "policies": []}),
        }]
        with patch("core.project_store._db", return_value=_FakeDB(rows)):
            result = list_bmm_by_project("p1")
        assert len(result) == 1
        assert result[0]["vision"] == "Ser referência"
        assert result[0]["_meeting_id"] == "m1"
        assert result[0]["_meeting_title"] == "Kickoff"

    def test_malformed_json_skipped_without_error(self):
        rows = [
            {"id": "m1", "meeting_number": 1, "title": "Boa", "meeting_date": "2026-06-01",
             "bmm_json": "{not valid json"},
            {"id": "m2", "meeting_number": 2, "title": "Válida", "meeting_date": "2026-06-15",
             "bmm_json": json.dumps({"vision": "OK"})},
        ]
        with patch("core.project_store._db", return_value=_FakeDB(rows)):
            result = list_bmm_by_project("p1")
        assert len(result) == 1
        assert result[0]["vision"] == "OK"

    def test_empty_project_returns_empty_list(self):
        with patch("core.project_store._db", return_value=_FakeDB([])):
            result = list_bmm_by_project("p1")
        assert result == []

    def test_no_db_returns_empty_list(self):
        with patch("core.project_store._db", return_value=None):
            result = list_bmm_by_project("p1")
        assert result == []


class TestListReportsByProject:
    def test_returns_meetings_with_report_html(self):
        rows = [{
            "id": "m1", "meeting_number": 1, "title": "Sprint Review", "meeting_date": "2026-06-01",
            "report_html": "<html>relatório</html>",
        }]
        with patch("core.project_store._db", return_value=_FakeDB(rows)):
            result = list_reports_by_project("p1")
        assert len(result) == 1
        assert result[0]["title"] == "Sprint Review"

    def test_blank_report_html_excluded(self):
        rows = [{
            "id": "m1", "meeting_number": 1, "title": "Sem relatório", "meeting_date": "2026-06-01",
            "report_html": "   ",
        }]
        with patch("core.project_store._db", return_value=_FakeDB(rows)):
            result = list_reports_by_project("p1")
        assert result == []

    def test_empty_project_returns_empty_list(self):
        with patch("core.project_store._db", return_value=_FakeDB([])):
            result = list_reports_by_project("p1")
        assert result == []
