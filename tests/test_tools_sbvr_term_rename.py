# tests/test_tools_sbvr_term_rename.py
"""
Tests for PC156: closing the gap where a misspelled term propagated across
transcript/ata/requirements could be fixed via apply_text_correction, but
the SBVR vocabulary term name itself had no rename path.

Covers:
- update_sbvr_term / update_sbvr_term_by_id gain a `new_term` parameter
  (with duplicate-name guard).
- preview_text_correction / apply_text_correction gain scope="sbvr"
  (and scope="all" now includes SBVR), touching sbvr_terms.term,
  sbvr_terms.definition, and sbvr_rules.statement.

No real DB/LLM calls — Supabase mocked via a small fake chainable client.
"""

from unittest.mock import patch, MagicMock

from core.assistant_tools import AssistantToolExecutor

_LLM_CONFIG = {
    "api_key": "fake-key",
    "model": "fake-model",
    "provider_cfg": {"client_type": "openai_compatible", "default_model": "fake-model"},
}


def _executor():
    return AssistantToolExecutor("proj-1", llm_config=_LLM_CONFIG)


class _FakeQuery:
    """Mimics db.table(x).select(...).eq(...).ilike(...).update(...).execute()."""

    def __init__(self, rows, table_name, updates_log):
        self._rows = rows
        self._table_name = table_name
        self._updates_log = updates_log
        self._pending_update = None

    def select(self, *a, **k):
        return self

    def eq(self, field, value):
        self._rows = [r for r in self._rows if r.get(field) == value]
        return self

    def ilike(self, field, value):
        v = value.lower()
        self._rows = [r for r in self._rows if (r.get(field) or "").lower() == v]
        return self

    def order(self, *a, **k):
        return self

    def update(self, patch_dict):
        self._pending_update = patch_dict
        return self

    def execute(self):
        if self._pending_update is not None:
            for r in self._rows:
                r.update(self._pending_update)
                self._updates_log.append((self._table_name, r.get("id"), dict(self._pending_update)))
        resp = MagicMock()
        resp.data = self._rows
        return resp


class _FakeDB:
    def __init__(self, tables: dict):
        # tables: {table_name: [row_dict, ...]} — rows mutated in place on update
        self._tables = tables
        self.updates_log: list[tuple] = []

    def table(self, name):
        return _FakeQuery(list(self._tables.get(name, [])), name, self.updates_log)


def _sbvr_terms():
    return [
        {"id": "t1", "project_id": "proj-1", "term": "SASEP", "definition": "Sistema de acompanhamento.", "category": "sigla"},
        {"id": "t2", "project_id": "proj-1", "term": "DTI", "definition": "Diretoria de TI.", "category": "sigla"},
    ]


def _sbvr_rules():
    return [
        {"id": "r1", "project_id": "proj-1", "rule_id": "BR001", "statement": "O SASEP deve ser consultado antes da aprovação."},
    ]


class TestUpdateSbvrTermRename:
    def test_renames_term_successfully(self):
        ex = _executor()
        db = _FakeDB({"sbvr_terms": _sbvr_terms()})
        with patch("modules.supabase_client.get_supabase_client", return_value=db):
            result = ex.update_sbvr_term(term="SASEP", new_term="SACEP")
        assert "✅" in result
        assert "SACEP" in result
        assert db._tables["sbvr_terms"][0]["term"] == "SACEP"

    def test_rejects_duplicate_name(self):
        ex = _executor()
        db = _FakeDB({"sbvr_terms": _sbvr_terms()})
        with patch("modules.supabase_client.get_supabase_client", return_value=db):
            result = ex.update_sbvr_term(term="SASEP", new_term="DTI")
        assert "❌" in result and "duplicad" in result.lower()
        # original term must remain untouched
        assert db._tables["sbvr_terms"][0]["term"] == "SASEP"

    def test_term_not_found(self):
        ex = _executor()
        db = _FakeDB({"sbvr_terms": _sbvr_terms()})
        with patch("modules.supabase_client.get_supabase_client", return_value=db):
            result = ex.update_sbvr_term(term="INEXISTENTE", new_term="X")
        assert "não encontrado" in result

    def test_rename_plus_definition_together(self):
        ex = _executor()
        db = _FakeDB({"sbvr_terms": _sbvr_terms()})
        with patch("modules.supabase_client.get_supabase_client", return_value=db):
            result = ex.update_sbvr_term(term="SASEP", new_term="SACEP", definition="Novo texto.")
        assert "✅" in result
        assert db._tables["sbvr_terms"][0]["term"] == "SACEP"
        assert db._tables["sbvr_terms"][0]["definition"] == "Novo texto."


class TestUpdateSbvrTermByIdRename:
    def test_renames_by_id_successfully(self):
        ex = _executor()
        db = _FakeDB({"sbvr_terms": _sbvr_terms()})
        with patch("modules.supabase_client.get_supabase_client", return_value=db):
            result = ex.update_sbvr_term_by_id(term_id="t1", new_term="SACEP")
        assert "✅" in result
        assert db._tables["sbvr_terms"][0]["term"] == "SACEP"

    def test_rejects_duplicate_name(self):
        ex = _executor()
        db = _FakeDB({"sbvr_terms": _sbvr_terms()})
        with patch("modules.supabase_client.get_supabase_client", return_value=db):
            result = ex.update_sbvr_term_by_id(term_id="t1", new_term="DTI")
        assert "❌" in result and "duplicad" in result.lower()
        assert db._tables["sbvr_terms"][0]["term"] == "SASEP"

    def test_no_op_rename_to_same_name_is_allowed(self):
        ex = _executor()
        db = _FakeDB({"sbvr_terms": _sbvr_terms()})
        with patch("modules.supabase_client.get_supabase_client", return_value=db):
            result = ex.update_sbvr_term_by_id(term_id="t1", new_term="SASEP", new_category="novo")
        assert "✅" in result
        assert db._tables["sbvr_terms"][0]["term"] == "SASEP"
        assert db._tables["sbvr_terms"][0]["category"] == "novo"


class TestTextCorrectionSbvrScope:
    def test_preview_finds_occurrences_in_term_definition_and_rule(self):
        ex = _executor()
        db = _FakeDB({"sbvr_terms": _sbvr_terms(), "sbvr_rules": _sbvr_rules()})
        with patch("modules.supabase_client.get_supabase_client", return_value=db):
            result = ex.preview_text_correction("SASEP", "SACEP", "sbvr")
        assert "Termo SBVR 'SASEP'" in result
        assert "BR001" in result
        assert "3 ocorrência" in result or "ocorrência(s)" in result  # term + rule (definition has no match here)

    def test_preview_sbvr_scope_ignores_other_tables(self):
        ex = _executor()
        db = _FakeDB({"sbvr_terms": [], "sbvr_rules": []})
        with patch("modules.supabase_client.get_supabase_client", return_value=db):
            result = ex.preview_text_correction("SASEP", "SACEP", "sbvr")
        assert "Nenhuma ocorrência" in result
        assert "vocabulário SBVR" in result

    def test_apply_renames_term_and_rule_statement(self):
        ex = _executor()
        db = _FakeDB({"sbvr_terms": _sbvr_terms(), "sbvr_rules": _sbvr_rules()})
        with patch("modules.supabase_client.get_supabase_client", return_value=db):
            result = ex.apply_text_correction("SASEP", "SACEP", "sbvr")
        assert "Termo SBVR 'SACEP'" in result
        assert "Regra SBVR BR001" in result
        assert db._tables["sbvr_terms"][0]["term"] == "SACEP"
        assert db._tables["sbvr_rules"][0]["statement"] == "O SACEP deve ser consultado antes da aprovação."

    def test_apply_scope_all_still_covers_sbvr(self):
        ex = _executor()
        db = _FakeDB({
            "meetings": [],
            "requirements": [],
            "sbvr_terms": _sbvr_terms(),
            "sbvr_rules": _sbvr_rules(),
        })
        with patch("modules.supabase_client.get_supabase_client", return_value=db):
            result = ex.apply_text_correction("SASEP", "SACEP", "all")
        assert db._tables["sbvr_terms"][0]["term"] == "SACEP"
        assert db._tables["sbvr_rules"][0]["statement"] == "O SACEP deve ser consultado antes da aprovação."
        assert "Termo SBVR" in result

    def test_apply_sbvr_scope_does_not_touch_meetings_or_requirements(self):
        ex = _executor()
        meetings = [{"id": "m1", "meeting_number": 1, "title": "R1",
                     "transcript_clean": "fala sobre SASEP", "transcript_raw": "", "minutes_md": ""}]
        reqs = [{"id": "req1", "req_number": 1, "title": "SASEP obrigatório", "description": ""}]
        db = _FakeDB({"meetings": meetings, "requirements": reqs,
                       "sbvr_terms": _sbvr_terms(), "sbvr_rules": _sbvr_rules()})
        with patch("modules.supabase_client.get_supabase_client", return_value=db):
            ex.apply_text_correction("SASEP", "SACEP", "sbvr")
        assert db._tables["meetings"][0]["transcript_clean"] == "fala sobre SASEP"
        assert db._tables["requirements"][0]["title"] == "SASEP obrigatório"
