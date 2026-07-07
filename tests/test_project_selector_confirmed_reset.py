# tests/test_project_selector_confirmed_reset.py
"""
Regression test for PC151 — a production data-loss bug found by the user:
two full transcript pipeline runs (confirmed via llm_telemetry — every
agent ran, real LLM cost incurred) produced ZERO new rows in `meetings`,
with no error shown anywhere.

Root cause: ui/project_selector.py::_init() runs on EVERY rerun of
pages/Pipeline.py (via render_project_selector(), called before the
"Processar Transcrição" button logic on the very same script pass). Its
sync block compared `active_project_id` (set elsewhere, e.g. Home.py's
Central de Operações) against Pipeline's own `project_id` on every single
rerun — not just when active_project_id itself changed. Whenever a user
deliberately confirmed a DIFFERENT project inside Pipeline's own selector
than whatever happened to be "active" elsewhere, this mismatch persisted
across every subsequent rerun and re-triggered the reset each time,
silently reverting project_id back to the stale active project and
project_confirmed back to False — including on the exact rerun that
processes the transcript. Since pages/Pipeline.py's persistence block is
gated by `if supabase_configured() and project_confirmed:` with no
`else`, the LLM pipeline still ran (agents don't depend on this flag) but
create_meeting()/save_* were silently skipped, with zero user-facing
feedback.

Fix: track the last-seen active_project_id and only reset on a genuine
CHANGE of that value, not merely because it differs from Pipeline's
already-confirmed project_id.
"""

import streamlit as st
from ui.project_selector import _init


class _FakeSessionState(dict):
    """Mimics Streamlit's SessionStateProxy: supports both dict and
    attribute access against the same underlying storage."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value


def _fresh_session():
    st.session_state = _FakeSessionState()
    return st.session_state


class TestConfirmedProjectSurvivesReruns:
    """The core regression: confirming a project different from whatever
    happens to be 'active' elsewhere must NOT self-destruct on the next
    rerun — this is exactly what happens on the same script pass as the
    'Processar Transcrição' button click."""

    def test_manual_confirmation_of_different_project_survives_next_init(self):
        ss = _fresh_session()
        ss["active_project_id"] = "aurora-id"
        ss["active_project_name"] = "AURORA"
        _init()  # first render — syncs project_id to the active project

        # User picks a DIFFERENT project inside Pipeline's own selector and confirms it
        ss["project_id"] = "sdea-id"
        ss["project_name"] = "SDEA"
        ss["project_confirmed"] = True

        # Next rerun (e.g. the same one that processes "Processar Transcrição")
        _init()

        assert ss["project_id"] == "sdea-id"
        assert ss["project_confirmed"] is True

    def test_confirmation_survives_multiple_subsequent_reruns(self):
        ss = _fresh_session()
        ss["active_project_id"] = "aurora-id"
        _init()
        ss["project_id"] = "sdea-id"
        ss["project_confirmed"] = True

        for _ in range(5):
            _init()
            assert ss["project_id"] == "sdea-id"
            assert ss["project_confirmed"] is True

    def test_confirmation_survives_when_active_project_id_is_none(self):
        ss = _fresh_session()
        ss["active_project_id"] = None
        _init()
        ss["project_id"] = "sdea-id"
        ss["project_confirmed"] = True
        _init()
        assert ss["project_id"] == "sdea-id"
        assert ss["project_confirmed"] is True


class TestGenuineActiveProjectChangeStillResets:
    """The reset must still fire when the user genuinely switches the
    active project elsewhere (e.g. Home.py's Central de Operações) —
    this is the behavior the sync block is actually meant to provide."""

    def test_real_change_of_active_project_resets_confirmation(self):
        ss = _fresh_session()
        ss["active_project_id"] = "aurora-id"
        _init()
        ss["project_id"] = "sdea-id"
        ss["project_confirmed"] = True
        _init()
        assert ss["project_confirmed"] is True  # sanity: still confirmed before the switch

        # User genuinely switches active project in Home.py
        ss["active_project_id"] = "other-project-id"
        ss["active_project_name"] = "OTHER"
        _init()

        assert ss["project_id"] == "other-project-id"
        assert ss["project_confirmed"] is False

    def test_first_ever_active_project_id_syncs_on_first_init(self):
        ss = _fresh_session()
        ss["active_project_id"] = "aurora-id"
        ss["active_project_name"] = "AURORA"
        _init()
        assert ss["project_id"] == "aurora-id"
        assert ss["project_confirmed"] is False

    def test_switching_back_to_a_previously_active_project_resets_again(self):
        """Switching A -> B -> A must reset each time (each is a genuine
        change event), not just the first transition away from A."""
        ss = _fresh_session()
        ss["active_project_id"] = "proj-a"
        _init()
        ss["project_id"] = "proj-a"
        ss["project_confirmed"] = True

        ss["active_project_id"] = "proj-b"
        _init()
        assert ss["project_confirmed"] is False
        ss["project_id"] = "proj-b"
        ss["project_confirmed"] = True

        ss["active_project_id"] = "proj-a"
        _init()
        assert ss["project_confirmed"] is False
        assert ss["project_id"] == "proj-a"
