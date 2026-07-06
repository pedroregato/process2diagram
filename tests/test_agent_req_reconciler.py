# tests/test_agent_req_reconciler.py
"""
Tests for agents/agent_req_reconciler.py::AgentReqReconciler (PC140).

Regression guard for a real bug found 2026-07-06: run() built `existing` by
filtering OUT any requirement whose last_meeting_id equalled the meeting
being processed:

    existing = [r for r in list_requirements(project_id)
                if r.get("last_meeting_id") != meeting_id]

`existing` is fetched ONCE, before this run's own new requirements are ever
saved -- so it could never contain a genuine "self-match" from the CURRENT
pass. The only rows this filter could ever exclude were requirements
created by a PREVIOUS run of this exact same meeting (reprocessing). That
meant every reprocess of a meeting saw its own prior output excluded from
the candidate pool, so every item was always classified "new" and
duplicated wholesale -- confirmed on a real project (2466 rows for 47
distinct requirements, reprocessed repeatedly over 8 days).
"""

from unittest.mock import patch, MagicMock

from agents.agent_req_reconciler import AgentReqReconciler

_CLIENT_INFO = {"api_key": "fake"}
_PROVIDER_CFG = {"client_type": "openai_compatible", "default_model": "fake-model"}


def _fake_hub_with_requirements(items):
    hub = MagicMock()
    hub.requirements.ready = True
    hub.requirements.requirements = items
    return hub


def _new_item(title, description, type_="functional", priority="medium"):
    item = MagicMock()
    item.title = title
    item.description = description
    item.type = type_
    item.priority = priority
    item.source_quote = ""
    item.speaker = ""
    return item


class TestExistingCandidatePool:
    """PC140: existing requirements from a PRIOR pass of the SAME meeting
    must remain valid match candidates -- reprocessing must not duplicate."""

    def test_reprocessing_same_meeting_matches_instead_of_duplicating(self):
        meeting_id = "meeting-1"
        prior_requirement = {
            "id": "req-uuid-1",
            "req_number": 2,
            "title": "Validação cadastral automática",
            "description": "Consultar Serasa, Quod e Receita Federal em <30s.",
            "req_type": "functional",
            "priority": "high",
            "status": "active",
            "last_meeting_id": meeting_id,  # created/last touched by THIS meeting
            "requirement_versions": [{"version": 1}],
        }

        new_item = _new_item(
            "Validação cadastral automática",
            "Consultar Serasa, Quod e Receita Federal em <30s.",
        )
        hub = _fake_hub_with_requirements([new_item])

        with patch("agents.agent_req_reconciler.list_requirements", return_value=[prior_requirement]), \
             patch("agents.agent_req_reconciler.next_req_number", return_value=3), \
             patch("agents.agent_req_reconciler.save_new_requirement") as mock_save_new, \
             patch("agents.agent_req_reconciler.add_requirement_version") as mock_add_version, \
             patch("agents.agent_req_reconciler.update_requirement") as mock_update, \
             patch.object(AgentReqReconciler, "_call_llm",
                          return_value='{"change_type": "confirmed", "change_summary": "", "contradiction_detail": ""}'):
            reconciler = AgentReqReconciler(_CLIENT_INFO, _PROVIDER_CFG)
            counts = reconciler.run(hub, project_id="proj-1", meeting_id=meeting_id)

        mock_save_new.assert_not_called()
        mock_add_version.assert_called_once()
        mock_update.assert_called_once()
        assert counts == {"new": 0, "confirmed": 1, "revised": 0, "contradicted": 0}

    def test_existing_includes_rows_from_other_meetings_too(self):
        """Sanity check: requirements last touched by a DIFFERENT meeting
        were never excluded even before the fix -- must still work."""
        prior_requirement = {
            "id": "req-uuid-2",
            "req_number": 5,
            "title": "Criptografia de dados pessoais",
            "description": "AES-256 em repouso.",
            "req_type": "non_functional",
            "priority": "high",
            "status": "active",
            "last_meeting_id": "meeting-OTHER",
            "requirement_versions": [{"version": 1}],
        }
        new_item = _new_item("Criptografia de dados pessoais", "AES-256 em repouso.")
        hub = _fake_hub_with_requirements([new_item])

        with patch("agents.agent_req_reconciler.list_requirements", return_value=[prior_requirement]), \
             patch("agents.agent_req_reconciler.next_req_number", return_value=6), \
             patch("agents.agent_req_reconciler.save_new_requirement") as mock_save_new, \
             patch("agents.agent_req_reconciler.add_requirement_version") as mock_add_version, \
             patch("agents.agent_req_reconciler.update_requirement"), \
             patch.object(AgentReqReconciler, "_call_llm",
                          return_value='{"change_type": "confirmed", "change_summary": "", "contradiction_detail": ""}'):
            reconciler = AgentReqReconciler(_CLIENT_INFO, _PROVIDER_CFG)
            reconciler.run(hub, project_id="proj-1", meeting_id="meeting-2")

        mock_save_new.assert_not_called()
        mock_add_version.assert_called_once()

    def test_genuinely_new_requirement_still_creates_new_row(self):
        prior_requirement = {
            "id": "req-uuid-3",
            "req_number": 1,
            "title": "Submissão digital de proposta",
            "description": "Upload via portal web.",
            "req_type": "functional",
            "priority": "high",
            "status": "active",
            "last_meeting_id": "meeting-1",
            "requirement_versions": [{"version": 1}],
        }
        new_item = _new_item(
            "Relatório mensal de Credit Quality Review",
            "Gerar relatório PDF consolidado mensalmente para o comitê.",
        )
        hub = _fake_hub_with_requirements([new_item])

        with patch("agents.agent_req_reconciler.list_requirements", return_value=[prior_requirement]), \
             patch("agents.agent_req_reconciler.next_req_number", return_value=2), \
             patch("agents.agent_req_reconciler.save_new_requirement") as mock_save_new, \
             patch("agents.agent_req_reconciler.add_requirement_version") as mock_add_version, \
             patch.object(AgentReqReconciler, "_call_llm") as mock_llm:
            reconciler = AgentReqReconciler(_CLIENT_INFO, _PROVIDER_CFG)
            counts = reconciler.run(hub, project_id="proj-1", meeting_id="meeting-1")

        # Jaccard pre-filter should reject this pair outright (unrelated
        # topics) -- the LLM should not even need to be called.
        mock_save_new.assert_called_once()
        mock_add_version.assert_not_called()
        assert counts == {"new": 1, "confirmed": 0, "revised": 0, "contradicted": 0}

    def test_no_existing_requirements_always_creates_new(self):
        new_item = _new_item("Qualquer título", "Qualquer descrição.")
        hub = _fake_hub_with_requirements([new_item])

        with patch("agents.agent_req_reconciler.list_requirements", return_value=[]), \
             patch("agents.agent_req_reconciler.next_req_number", return_value=1), \
             patch("agents.agent_req_reconciler.save_new_requirement") as mock_save_new:
            reconciler = AgentReqReconciler(_CLIENT_INFO, _PROVIDER_CFG)
            counts = reconciler.run(hub, project_id="proj-1", meeting_id="meeting-1")

        mock_save_new.assert_called_once()
        assert counts["new"] == 1

    def test_no_requirements_ready_returns_empty(self):
        hub = MagicMock()
        hub.requirements.ready = False
        reconciler = AgentReqReconciler(_CLIENT_INFO, _PROVIDER_CFG)
        assert reconciler.run(hub, project_id="proj-1", meeting_id="meeting-1") == {}
