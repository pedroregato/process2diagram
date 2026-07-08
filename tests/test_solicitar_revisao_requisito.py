# tests/test_solicitar_revisao_requisito.py
"""
Tests for core/tools/tools_meetings_requirements.py::solicitar_revisao_requisito()
(melhorias/avaliacao-proposta-assistente-20260708.md, proposta #4, escopo
reduzido — Onda 3): structured "request revision" workflow, no e-mail/Slack
notification (that infra doesn't exist in the project). Written directly
(not delegated to update_requirement_status) specifically so a SECOND
revision request on an already-'revised' requirement is still recorded —
update_requirement_status early-returns "sem alteração" when old_status ==
new_status, which would silently drop it.

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
    def __init__(self, rows, log):
        self._rows = rows
        self._log = log
        self._pending_update = None
        self._pending_insert = None

    def select(self, *a, **k):
        return self

    def eq(self, *a, **k):
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def update(self, patch_dict):
        self._pending_update = patch_dict
        return self

    def insert(self, payload):
        self._pending_insert = payload
        return self

    def execute(self):
        resp = MagicMock()
        if self._pending_update is not None:
            for r in self._rows:
                r.update(self._pending_update)
            self._log.append(("update", dict(self._pending_update)))
            resp.data = self._rows
        elif self._pending_insert is not None:
            self._log.append(("insert", dict(self._pending_insert)))
            resp.data = [self._pending_insert]
        else:
            resp.data = self._rows
        return resp


class _FakeDB:
    def __init__(self, tables: dict):
        self._tables = tables
        self.log: list[tuple] = []

    def table(self, name):
        return _FakeQuery(self._tables.setdefault(name, []), self.log)


def _executor(tables):
    ex = AssistantToolExecutor(project_id="proj-1", llm_config=_LLM_CONFIG)
    db = _FakeDB(tables)
    patcher = patch("modules.supabase_client.get_supabase_client", return_value=db)
    patcher.start()
    return ex, db, patcher


class TestSolicitarRevisaoRequisito:
    def test_requisito_nao_encontrado(self):
        ex, db, patcher = _executor({"requirements": []})
        try:
            result = ex.solicitar_revisao_requisito(req_number=99, motivo="teste")
        finally:
            patcher.stop()
        assert "99" in result and "não encontrado" in result.lower()

    def test_marca_status_revised_com_nota_estruturada(self):
        tables = {"requirements": [
            {"id": "r1", "req_number": 5, "title": "Login SSO", "status": "active",
             "req_type": "functional", "first_meeting_id": "m1"},
        ]}
        ex, db, patcher = _executor(tables)
        try:
            result = ex.solicitar_revisao_requisito(
                req_number=5, motivo="Escopo mudou após reunião com cliente",
                revisor_sugerido="Maria (PO)",
            )
        finally:
            patcher.stop()

        assert "REQ-005" in result
        assert "Escopo mudou após reunião com cliente" in result
        assert "Maria (PO)" in result
        assert "sem notificação" in result.lower()

        update_calls = [entry for kind, entry in db.log if kind == "update"]
        assert update_calls
        assert update_calls[0]["status"] == "revised"
        assert "🔍 Revisão solicitada:" in update_calls[0]["status_note"]
        assert "Maria (PO)" in update_calls[0]["status_note"]

    def test_second_request_on_already_revised_requirement_still_recorded(self):
        """Regression guard: unlike update_requirement_status (which
        early-returns when old_status == new_status), a second revision
        request on an already-'revised' requirement must still update the
        note and register a new version — never silently dropped."""
        tables = {"requirements": [
            {"id": "r1", "req_number": 5, "title": "Login SSO", "status": "revised",
             "req_type": "functional", "first_meeting_id": "m1"},
        ]}
        ex, db, patcher = _executor(tables)
        try:
            result = ex.solicitar_revisao_requisito(req_number=5, motivo="Segunda rodada de dúvidas")
        finally:
            patcher.stop()

        assert "❌" not in result
        assert "Segunda rodada de dúvidas" in result
        update_calls = [entry for kind, entry in db.log if kind == "update"]
        assert update_calls
        assert "Segunda rodada de dúvidas" in update_calls[0]["status_note"]

    def test_no_reviewer_omits_that_line(self):
        tables = {"requirements": [
            {"id": "r1", "req_number": 5, "title": "Login SSO", "status": "active",
             "req_type": "functional", "first_meeting_id": "m1"},
        ]}
        ex, db, patcher = _executor(tables)
        try:
            result = ex.solicitar_revisao_requisito(req_number=5, motivo="Ajuste de escopo")
        finally:
            patcher.stop()
        assert "Revisor sugerido" not in result
