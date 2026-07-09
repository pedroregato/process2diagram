# tests/test_find_similar_existing_requirements.py
"""
Tests for core/project_store.py::find_similar_existing_requirements() (Onda
3 — Importador de Planilha de Requisitos): plain-text similarity screening
(difflib, no LLM/embedding cost) against titles of existing requirements,
used to warn (not block) about likely duplicates before importing a
spreadsheet row.

No real DB calls.
"""

from unittest.mock import patch, MagicMock

from core.project_store import find_similar_existing_requirements


class _FakeQuery:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def neq(self, field, value):
        self._rows = [r for r in self._rows if r.get(field) != value]
        return self

    def execute(self):
        resp = MagicMock()
        resp.data = self._rows
        return resp


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows

    def table(self, name):
        return _FakeQuery(list(self._rows))


class TestFindSimilarExistingRequirements:
    def test_identical_title_matches_with_high_score(self):
        db = _FakeDB([{"req_number": 1, "title": "Login com SSO corporativo", "status": "active"}])
        with patch("core.project_store._db", return_value=db):
            result = find_similar_existing_requirements("proj-1", "Login com SSO corporativo")
        assert len(result) == 1
        assert result[0]["req_number"] == 1
        assert result[0]["score"] >= 0.99

    def test_completely_different_title_does_not_match(self):
        db = _FakeDB([{"req_number": 1, "title": "Login com SSO corporativo", "status": "active"}])
        with patch("core.project_store._db", return_value=db):
            result = find_similar_existing_requirements("proj-1", "Exportar relatório financeiro em PDF")
        assert result == []

    def test_similar_but_below_threshold_does_not_match(self):
        db = _FakeDB([{"req_number": 1, "title": "Login", "status": "active"}])
        with patch("core.project_store._db", return_value=db):
            result = find_similar_existing_requirements(
                "proj-1", "Sistema completo de autenticação multifator com auditoria", threshold=0.75,
            )
        assert result == []

    def test_deprecated_requirements_excluded(self):
        db = _FakeDB([{"req_number": 1, "title": "Login com SSO corporativo", "status": "deprecated"}])
        with patch("core.project_store._db", return_value=db):
            result = find_similar_existing_requirements("proj-1", "Login com SSO corporativo")
        assert result == []

    def test_empty_project_returns_empty_list_without_error(self):
        db = _FakeDB([])
        with patch("core.project_store._db", return_value=db):
            result = find_similar_existing_requirements("proj-1", "Qualquer título")
        assert result == []

    def test_empty_title_returns_empty_list(self):
        db = _FakeDB([{"req_number": 1, "title": "Algo", "status": "active"}])
        with patch("core.project_store._db", return_value=db):
            result = find_similar_existing_requirements("proj-1", "   ")
        assert result == []

    def test_results_sorted_by_score_descending(self):
        db = _FakeDB([
            {"req_number": 1, "title": "Login básico", "status": "active"},
            {"req_number": 2, "title": "Login com SSO corporativo completo", "status": "active"},
        ])
        with patch("core.project_store._db", return_value=db):
            result = find_similar_existing_requirements("proj-1", "Login com SSO corporativo", threshold=0.3)
        assert len(result) == 2
        assert result[0]["score"] >= result[1]["score"]
