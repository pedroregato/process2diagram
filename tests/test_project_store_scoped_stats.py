# tests/test_project_store_scoped_stats.py
"""
Tests for core/project_store.py::get_domain_stats() / get_context_stats() /
_exact_count() (PC138 + PC139).

Regression guard for two real bugs found 2026-07-06:
  1. (PC138) pages/Home.py showed get_global_stats() (every tenant, every
     project, no filter at all) as if it were the active domain's numbers.
     A domain with 4 real contexts displayed "8 contexts" because the count
     silently included another tenant's contexts too.
  2. (PC139) even after scoping the query correctly, a project with 2466
     real requirements displayed exactly "1000" — len(_ok(query.execute()))
     only counts rows actually TRANSFERRED, capped at Supabase/PostgREST's
     default 1000-row response limit. Fixed with count="exact" + .limit(1),
     which asks PostgREST to compute the real aggregate server-side.

The fake Supabase client below mimics this exact behavior: .data is capped
at 1000 rows (like the real API), but .count (when count="exact" is
requested) always reflects the TRUE filtered total.
"""

from unittest.mock import patch

from core.project_store import get_domain_stats, get_context_stats, _exact_count

_POSTGREST_DEFAULT_ROW_CAP = 1000


class _FakeResponse:
    def __init__(self, data, count=None):
        self.data = data
        self.count = count


class _FakeQuery:
    def __init__(self, table_name, data_by_table, calls):
        self._table_name = table_name
        self._data_by_table = data_by_table
        self._calls = calls
        self._filters: list[tuple] = []
        self._count_exact = False
        self._limit: int | None = None

    def select(self, *args, count=None, **kwargs):
        if count == "exact":
            self._count_exact = True
        return self

    def eq(self, col, val):
        self._filters.append(("eq", col, val))
        return self

    def in_(self, col, vals):
        self._filters.append(("in", col, list(vals)))
        return self

    def limit(self, n):
        self._limit = n
        return self

    def execute(self):
        self._calls.append((self._table_name, list(self._filters)))
        rows = self._data_by_table.get(self._table_name, [])
        for ftype, col, val in self._filters:
            if ftype == "eq":
                rows = [r for r in rows if r.get(col) == val]
            elif ftype == "in":
                rows = [r for r in rows if r.get(col) in val]
        true_count = len(rows)
        # Mirrors the real PostgREST default: data payload capped at 1000
        # rows regardless of the true match count; an explicit .limit()
        # caps it further still.
        data_cap = self._limit if self._limit is not None else _POSTGREST_DEFAULT_ROW_CAP
        capped_rows = rows[:data_cap]
        return _FakeResponse(capped_rows, count=true_count if self._count_exact else None)


class _FakeDB:
    def __init__(self, data_by_table):
        self._data_by_table = data_by_table
        self.calls: list[tuple] = []

    def table(self, name):
        return _FakeQuery(name, self._data_by_table, self.calls)


# Two tenants ("p2d" and "outro"), 4 contexts each — mirrors the real bug
# report: domain p2d has 4 contexts but the page showed 8 (4 + 4 from the
# other tenant, summed with zero filtering).
_TENANT_P2D = "tenant-p2d"
_TENANT_OUTRO = "tenant-outro"

_CONTEXTS = (
    [{"id": f"p2d-ctx-{i}", "tenant_id": _TENANT_P2D} for i in range(4)]
    + [{"id": f"outro-ctx-{i}", "tenant_id": _TENANT_OUTRO} for i in range(4)]
)
_MEETINGS = (
    [{"id": f"m{i}", "project_id": "p2d-ctx-0"} for i in range(3)]
    + [{"id": f"m{i+10}", "project_id": "p2d-ctx-1"} for i in range(2)]
    + [{"id": f"m{i+20}", "project_id": "outro-ctx-0"} for i in range(30)]
)
_REQUIREMENTS = (
    [{"id": f"r{i}", "project_id": "p2d-ctx-0"} for i in range(5)]
    + [{"id": f"r{i+50}", "project_id": "outro-ctx-0"} for i in range(40)]
)
_BPMN_PROCESSES = (
    [{"id": f"b{i}", "project_id": "p2d-ctx-0"} for i in range(2)]
    + [{"id": f"b{i+20}", "project_id": "outro-ctx-0"} for i in range(49)]
)
_DOCUMENTS = (
    [{"id": f"d{i}", "project_id": "p2d-ctx-0"} for i in range(1)]
    + [{"id": f"d{i+10}", "project_id": "outro-ctx-0"} for i in range(1)]
)

_DATA_BY_TABLE = {
    "contexts": _CONTEXTS,
    "meetings": _MEETINGS,
    "requirements": _REQUIREMENTS,
    "bpmn_processes": _BPMN_PROCESSES,
    "meeting_documents": _DOCUMENTS,
}


def _fake_db():
    return _FakeDB(_DATA_BY_TABLE)


class TestGetDomainStats:
    def test_counts_only_this_tenants_contexts(self):
        with patch("core.project_store._db", side_effect=_fake_db):
            stats = get_domain_stats(_TENANT_P2D)
        assert stats["n_projects"] == 4, "must NOT count the other tenant's 4 contexts too"
        assert stats["available"] is True

    def test_meetings_scoped_to_tenants_own_projects(self):
        with patch("core.project_store._db", side_effect=_fake_db):
            stats = get_domain_stats(_TENANT_P2D)
        assert stats["n_meetings"] == 5  # 3 + 2, not the other tenant's 30

    def test_requirements_bpmn_documents_scoped(self):
        with patch("core.project_store._db", side_effect=_fake_db):
            stats = get_domain_stats(_TENANT_P2D)
        assert stats["n_reqs"] == 5
        assert stats["n_bpmn_procs"] == 2
        assert stats["n_documents"] == 1

    def test_different_tenant_sees_its_own_numbers(self):
        with patch("core.project_store._db", side_effect=_fake_db):
            stats = get_domain_stats(_TENANT_OUTRO)
        assert stats["n_projects"] == 4
        assert stats["n_meetings"] == 30
        assert stats["n_reqs"] == 40
        assert stats["n_bpmn_procs"] == 49

    def test_none_tenant_id_returns_zeros_fail_closed(self):
        with patch("core.project_store._db", side_effect=_fake_db):
            stats = get_domain_stats(None)
        assert stats == {
            "n_projects": 0, "n_meetings": 0, "n_reqs": 0,
            "n_bpmn_procs": 0, "n_documents": 0, "available": False,
        }

    def test_no_db_returns_zeros(self):
        with patch("core.project_store._db", return_value=None):
            stats = get_domain_stats(_TENANT_P2D)
        assert stats["available"] is False

    def test_tenant_with_zero_contexts_returns_zeros_not_exception(self):
        with patch("core.project_store._db", side_effect=_fake_db):
            stats = get_domain_stats("tenant-with-nothing")
        assert stats["n_projects"] == 0
        assert stats["n_meetings"] == 0


class TestGetContextStats:
    def test_scoped_to_single_project(self):
        with patch("core.project_store._db", side_effect=_fake_db):
            stats = get_context_stats("p2d-ctx-0")
        assert stats["n_meetings"] == 3
        assert stats["n_reqs"] == 5
        assert stats["n_bpmn_procs"] == 2
        assert stats["n_documents"] == 1
        assert stats["available"] is True

    def test_different_project_in_same_tenant_is_isolated(self):
        with patch("core.project_store._db", side_effect=_fake_db):
            stats = get_context_stats("p2d-ctx-1")
        assert stats["n_meetings"] == 2
        assert stats["n_reqs"] == 0  # no requirements seeded for this project

    def test_none_project_id_returns_zeros_fail_closed(self):
        with patch("core.project_store._db", side_effect=_fake_db):
            stats = get_context_stats(None)
        assert stats == {
            "n_meetings": 0, "n_reqs": 0, "n_bpmn_procs": 0,
            "n_documents": 0, "available": False,
        }

    def test_no_db_returns_zeros(self):
        with patch("core.project_store._db", return_value=None):
            stats = get_context_stats("p2d-ctx-0")
        assert stats["available"] is False


class TestExactCountBeyondPostgrestDefaultCap:
    """PC139: a project with more matching rows than PostgREST's default
    1000-row response limit must still report the TRUE count, not 1000."""

    def _db_with_many_requirements(self, n_requirements: int):
        data = {
            "contexts": [{"id": "aurora", "tenant_id": "tenant-p2d"}],
            "meetings": [{"id": f"m{i}", "project_id": "aurora"} for i in range(4)],
            "requirements": [{"id": f"r{i}", "project_id": "aurora"} for i in range(n_requirements)],
            "bpmn_processes": [],
            "meeting_documents": [],
        }
        return _FakeDB(data)

    def test_exact_count_exceeds_1000_row_cap(self):
        db = self._db_with_many_requirements(2466)
        assert _exact_count(db, "requirements", {"project_id": "aurora"}) == 2466

    def test_get_context_stats_reports_true_count_above_cap(self):
        with patch("core.project_store._db", side_effect=lambda: self._db_with_many_requirements(2466)):
            stats = get_context_stats("aurora")
        assert stats["n_reqs"] == 2466, "must report the real total, not the 1000-row PostgREST default cap"

    def test_get_domain_stats_reports_true_count_above_cap(self):
        with patch("core.project_store._db", side_effect=lambda: self._db_with_many_requirements(2466)):
            stats = get_domain_stats("tenant-p2d")
        assert stats["n_reqs"] == 2466

    def test_old_len_of_data_pattern_would_have_undercounted(self):
        """Sanity check that the fake DB genuinely reproduces the bug shape
        (data capped at 1000) so the regression above is meaningful."""
        db = self._db_with_many_requirements(2466)
        resp = db.table("requirements").select("id").eq("project_id", "aurora").execute()
        assert len(resp.data) == 1000
