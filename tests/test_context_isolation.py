# tests/test_context_isolation.py
"""
PRODUCT_MANIFESTO Sec 4 promises a hard boundary: an artifact never leaks from
one context to another unless explicitly promoted (Ativo de Negocio). PC195's
reconciliation report (achado #7) found that boundary has no structural
enforcement today - it depends entirely on every caller remembering to filter
by project_id. This suite is the evidence requested in the Agente 0 arbitration
(Fase A2): create two contexts, seed a non-promoted artifact in each, and prove
(not assume) whether a read scoped to context A can ever return context B's data.

No real DB calls - a small in-memory fake Supabase client with real filtering
semantics (same pattern as tests/test_meeting_processing_log.py's _FakeSelectQuery).

Two kinds of test here, both real evidence:
  - test_protected_* : functions that DO filter by project_id -> proven safe.
  - test_ambiguous_*  : functions that filter by a child id only (no project_id
    re-check) -> proven to return foreign-context data when called with an id
    the caller didn't validate. This is not a bug fix target this round - it's
    the empirical proof behind proposta-isolamento-de-contexto.md.
"""

from unittest.mock import patch

from core.project_store import (
    list_requirements_light,
    list_bpmn_processes,
    list_sbvr_terms,
    get_bpmn_process,
    list_requirement_versions,
)

CONTEXT_A = "context-a-11111111-1111-1111-1111-111111111111"
CONTEXT_B = "context-b-22222222-2222-2222-2222-222222222222"


class _Resp:
    def __init__(self, data):
        self.data = data
        self.count = len(data) if isinstance(data, list) else None


class _FakeQuery:
    """Chainable fake with real filtering — rows only survive matching .eq()/.in_() calls."""

    def __init__(self, rows: list[dict]):
        self._rows = list(rows)
        self._single = False

    def select(self, *a, **k):
        return self

    def eq(self, col, val):
        self._rows = [r for r in self._rows if r.get(col) == val]
        return self

    def in_(self, col, vals):
        vals = set(vals)
        self._rows = [r for r in self._rows if r.get(col) in vals]
        return self

    def order(self, *a, **k):
        return self

    def limit(self, n):
        self._rows = self._rows[:n]
        return self

    def single(self):
        self._single = True
        return self

    def execute(self):
        if self._single:
            return _Resp(self._rows[0] if self._rows else None)
        return _Resp(self._rows)


class _FakeDB:
    """Routes .table(name) to that table's seeded rows. Read-only fake — no
    insert/update needed since every test seeds rows directly into `tables`."""

    def __init__(self, tables: dict[str, list[dict]]):
        self._tables = tables

    def table(self, name):
        return _FakeQuery(self._tables.get(name, []))


def _seeded_db() -> _FakeDB:
    """Two contexts (A, B) in the same domain, one non-promoted artifact of
    each type per context. Titles/ids are unique so a leak is unmistakable."""
    return _FakeDB({
        "requirements": [
            {"id": "req-a1", "project_id": CONTEXT_A, "req_number": 1,
             "title": "SECRET-A — requisito do contexto A"},
            {"id": "req-b1", "project_id": CONTEXT_B, "req_number": 1,
             "title": "SECRET-B — requisito do contexto B"},
        ],
        "requirement_versions": [
            {"id": "v-a1", "requirement_id": "req-a1", "version": 1,
             "title": "SECRET-A v1"},
            {"id": "v-b1", "requirement_id": "req-b1", "version": 1,
             "title": "SECRET-B v1"},
        ],
        "bpmn_processes": [
            {"id": "proc-a1", "project_id": CONTEXT_A, "name": "SECRET-A processo"},
            {"id": "proc-b1", "project_id": CONTEXT_B, "name": "SECRET-B processo"},
        ],
        "sbvr_terms": [
            {"id": "term-a1", "project_id": CONTEXT_A, "term": "SECRET-A termo"},
            {"id": "term-b1", "project_id": CONTEXT_B, "term": "SECRET-B termo"},
        ],
    })


def _patched(fake_db):
    return patch("core.project_store.get_supabase_client", return_value=fake_db)


# ── Caminhos protegidos (.eq("project_id", ...)) — devem isolar corretamente ──

def test_protected_requirements_never_leak_across_context():
    with _patched(_seeded_db()):
        rows_a = list_requirements_light(CONTEXT_A)
        rows_b = list_requirements_light(CONTEXT_B)
    titles_a = {r["title"] for r in rows_a}
    titles_b = {r["title"] for r in rows_b}
    assert "SECRET-A — requisito do contexto A" in titles_a
    assert "SECRET-B — requisito do contexto B" not in titles_a
    assert "SECRET-B — requisito do contexto B" in titles_b
    assert "SECRET-A — requisito do contexto A" not in titles_b


def test_protected_bpmn_processes_never_leak_across_context():
    with _patched(_seeded_db()):
        rows_a = list_bpmn_processes(CONTEXT_A)
    names_a = {r["name"] for r in rows_a}
    assert "SECRET-A processo" in names_a
    assert "SECRET-B processo" not in names_a


def test_protected_sbvr_terms_never_leak_across_context():
    with _patched(_seeded_db()):
        rows_a = list_sbvr_terms(CONTEXT_A)
    terms_a = {r["term"] for r in rows_a}
    assert "SECRET-A termo" in terms_a
    assert "SECRET-B termo" not in terms_a


# ── Caminhos ambíguos (filtram só por id-filho, sem project_id) — a evidência
# empírica de achado #7: a função por si só NÃO garante isolamento; o
# isolamento hoje é 100% responsabilidade de quem chama já ter validado o id.

def test_ambiguous_get_bpmn_process_returns_foreign_context_data_by_id():
    """get_bpmn_process(process_id) has no project_id check — proven here by
    fetching context B's process while nothing in the call declares "context A".
    Safe in production ONLY because every current caller resolves process_id
    through a project_id-scoped lookup first (see proposta-isolamento-de-contexto.md
    Sec 1) — a guarantee this function itself does not enforce."""
    with _patched(_seeded_db()):
        leaked = get_bpmn_process("proc-b1")
    assert leaked is not None
    assert leaked["project_id"] == CONTEXT_B
    assert leaked["name"] == "SECRET-B processo"


def test_ambiguous_list_requirement_versions_returns_foreign_context_data_by_id():
    """Same pattern as above for requirement_versions — filters only by
    requirement_id, never by project_id."""
    with _patched(_seeded_db()):
        leaked = list_requirement_versions("req-b1")
    assert len(leaked) == 1
    assert leaked[0]["title"] == "SECRET-B v1"
