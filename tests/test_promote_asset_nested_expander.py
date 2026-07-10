# tests/test_promote_asset_nested_expander.py
"""
Regression test for a production crash: render_promote_button() /
render_promote_assistant_content_button() used to open their form inside an
st.expander(). Several callers (Reuniões/SBVR tabs in Artefatos.py,
Biblioteca tab in DocumentManager.py) already render each item inside their
own st.expander() — Streamlit raises StreamlitAPIException on nested
expanders regardless of expanded state, so every visit to those tabs with
at least one item crashed the whole page.

Fix: both functions now use a st.button() toggle + st.session_state flag
instead of st.expander(). This test reproduces the exact nested-expander
shape (outer expander wrapping the promote widget) and asserts it no longer
raises — both on initial render and after clicking the toggle button (which
renders the form itself).

Note: do NOT call st.session_state.clear() here — each AppTest.from_string()
already runs its own isolated session, and touching st.session_state from
the outer (non-AppTest) process breaks the next AppTest run's widget tree.

Note: script strings use plain ASCII only — AppTest.from_string() on this
Windows environment silently drops widgets when the script text contains
accented characters (button count comes back 0, no exception raised). Pure
test-tooling quirk, unrelated to the production code under test.
"""

from streamlit.testing.v1 import AppTest


_SCRIPT_PROMOTE_BUTTON = """
import streamlit as st
from ui.components.promote_asset import render_promote_button

with st.expander("Reuniao 1 - Ata de teste"):
    render_promote_button(
        "proj-1", "meeting_minutes", "art-1",
        title="Ata de teste", key_suffix="art-1", already_promoted=False,
    )
"""

_SCRIPT_PROMOTE_ASSISTANT_BUTTON = """
import streamlit as st
from ui.components.promote_asset import render_promote_assistant_content_button

with st.expander("Alguma secao com expander"):
    render_promote_assistant_content_button(
        "proj-1", "Resposta do Assistente", "conteudo de teste", key_suffix="1",
    )
"""

_SCRIPT_ALREADY_PROMOTED_NO_CRASH = """
import streamlit as st
from ui.components.promote_asset import render_promote_button

with st.expander("Reuniao 1 - Ata ja promovida"):
    render_promote_button(
        "proj-1", "meeting_minutes", "art-1",
        title="Ata de teste", key_suffix="art-1", already_promoted=True,
    )
"""


class TestRenderPromoteButtonInsideExpander:
    def test_initial_render_does_not_raise_nested_expander_error(self):
        at = AppTest.from_string(_SCRIPT_PROMOTE_BUTTON)
        at.run()
        assert not at.exception

    def test_clicking_toggle_renders_form_without_raising(self):
        at = AppTest.from_string(_SCRIPT_PROMOTE_BUTTON)
        at.run()
        at.button[0].click().run()
        assert not at.exception
        assert len(at.text_input) > 0  # form fields rendered (owner/tags)

    def test_already_promoted_shows_caption_without_raising(self):
        at = AppTest.from_string(_SCRIPT_ALREADY_PROMOTED_NO_CRASH)
        at.run()
        assert not at.exception
        assert len(at.button) == 0  # no toggle button — already promoted


class TestRenderPromoteAssistantContentButtonInsideExpander:
    def test_initial_render_does_not_raise_nested_expander_error(self):
        at = AppTest.from_string(_SCRIPT_PROMOTE_ASSISTANT_BUTTON)
        at.run()
        assert not at.exception

    def test_clicking_toggle_renders_form_without_raising(self):
        at = AppTest.from_string(_SCRIPT_PROMOTE_ASSISTANT_BUTTON)
        at.run()
        at.button[0].click().run()
        assert not at.exception
        assert len(at.text_input) > 0
