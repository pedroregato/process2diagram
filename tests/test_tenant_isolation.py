# tests/test_tenant_isolation.py
"""
NAV-01 (melhorias/navegabilidade.md, PC211): list_projects was a bare alias
for list_contexts() called with no tenant_id in 14 call sites across pages/
(Diagramas, CostEstimator, Pipeline, Settings, Capacitacao + 9 admin-only
Manutenção pages) — every one of them silently listed contexts from every
tenant, not just the logged-in one. The alias is now removed; every caller
must pass tenant_id=st.session_state.get("_tenant_id") explicitly, mirroring
the pattern already used in pages/Home.py and ui/project_selector.py.

This suite proves two things with real evidence, not assumption:
  1. list_contexts(tenant_id=...) actually filters (same fake-DB pattern as
     tests/test_context_isolation.py).
  2. No file under pages/ still calls list_contexts() bare (no args) or
     imports/calls the removed list_projects — a regression here would
     silently reopen the cross-tenant leak.
"""

import re
from pathlib import Path
from unittest.mock import patch

from core.project_store import list_contexts

TENANT_A = "tenant-a-11111111-1111-1111-1111-111111111111"
TENANT_B = "tenant-b-22222222-2222-2222-2222-222222222222"

_PAGES_DIR = Path(__file__).resolve().parent.parent / "pages"


class _Resp:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, rows: list[dict]):
        self._rows = list(rows)

    def select(self, *a, **k):
        return self

    def eq(self, col, val):
        self._rows = [r for r in self._rows if r.get(col) == val]
        return self

    def order(self, *a, **k):
        return self

    def execute(self):
        return _Resp(self._rows)


class _FakeDB:
    def __init__(self, rows):
        self._rows = rows

    def table(self, name):
        assert name == "contexts"
        return _FakeQuery(self._rows)


def _seeded_db() -> _FakeDB:
    return _FakeDB([
        {"id": "ctx-a1", "tenant_id": TENANT_A, "name": "SECRET-A contexto"},
        {"id": "ctx-b1", "tenant_id": TENANT_B, "name": "SECRET-B contexto"},
    ])


def test_list_contexts_filters_by_tenant_id():
    with patch("core.project_store.get_supabase_client", return_value=_seeded_db()):
        rows_a = list_contexts(tenant_id=TENANT_A)
        rows_b = list_contexts(tenant_id=TENANT_B)
    names_a = {r["name"] for r in rows_a}
    names_b = {r["name"] for r in rows_b}
    assert "SECRET-A contexto" in names_a
    assert "SECRET-B contexto" not in names_a
    assert "SECRET-B contexto" in names_b
    assert "SECRET-A contexto" not in names_b


def test_list_contexts_without_tenant_id_returns_everyone():
    """Documents the leak that made NAV-01 necessary: tenant_id=None (or
    omitted) is a deliberate fallback for local/dev login, not a safe
    default — every caller inside pages/ must supply it explicitly."""
    with patch("core.project_store.get_supabase_client", return_value=_seeded_db()):
        rows = list_contexts()
    names = {r["name"] for r in rows}
    assert {"SECRET-A contexto", "SECRET-B contexto"} <= names


def test_no_page_calls_list_contexts_without_tenant_id():
    offenders = []
    for path in sorted(_PAGES_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if re.search(r"\blist_contexts\(\s*\)", text):
            offenders.append(path.name)
    assert offenders == [], f"pages/ calling list_contexts() bare (no tenant_id): {offenders}"


def test_no_page_imports_or_calls_list_projects():
    offenders = []
    for path in sorted(_PAGES_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        if re.search(r"\blist_projects\b", text):
            offenders.append(path.name)
    assert offenders == [], f"pages/ still referencing removed list_projects alias: {offenders}"


def test_list_projects_alias_removed_from_project_store():
    import core.project_store as ps
    assert not hasattr(ps, "list_projects")
