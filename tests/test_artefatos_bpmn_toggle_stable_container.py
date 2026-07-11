# tests/test_artefatos_bpmn_toggle_stable_container.py
"""
Regression test for pages/Artefatos.py's BPMN tab: the "Visualizar diagrama
interativo" st.toggle() conditionally rendered a components.html() block
(the whole bpmn-js library + diagram XML — a large payload) directly inline,
without a stable st.container() wrapper — same "variable child count" defect
class already fixed for the promote-button toggle (PC172/174) and the "Ver
Ata Completa" toggle (PC175), both of which caused a production
"Bad 'setIn' index" crash in the Streamlit frontend.

This test reproduces the exact shape (toggle inside nested st.tabs(), same
as the real BPMN sub-tab structure) with a stubbed heavy payload standing in
for components.html(bpmn_html, ...), and asserts the toggle can be clicked
without raising — both before and after the fix, this Python-level check
can't observe the JS crash itself (that's the acknowledged limitation
documented in CLAUDE.md pitfalls / PC174 roadmap entry), but it does prove
the container-wrapping structure is in place and that toggling doesn't blow
up on the Python side.
"""

from streamlit.testing.v1 import AppTest


_SCRIPT_TOGGLE_WITH_STABLE_CONTAINER = """
import streamlit as st

sub_bpmn, sub_mermaid = st.tabs(["BPMN", "Mermaid"])
with sub_bpmn:
    show = st.toggle("Visualizar diagrama interativo", key="bpmn_show_p1_v1")
    with st.container():
        if show:
            st.markdown("<div>heavy embedded diagram payload</div>", unsafe_allow_html=True)
with sub_mermaid:
    st.caption("mermaid tab")
"""


class TestBpmnToggleStableContainer:
    def test_initial_render_does_not_raise(self):
        at = AppTest.from_string(_SCRIPT_TOGGLE_WITH_STABLE_CONTAINER)
        at.run()
        assert not at.exception

    def test_toggling_on_then_off_does_not_raise(self):
        at = AppTest.from_string(_SCRIPT_TOGGLE_WITH_STABLE_CONTAINER)
        at.run()
        toggle = at.toggle[0]
        toggle.set_value(True).run()
        assert not at.exception
        toggle.set_value(False).run()
        assert not at.exception


class TestArtefatosBpmnTabSourceUsesStableContainer:
    def test_bpmn_toggle_is_wrapped_in_st_container(self):
        """Static check on the real source: the toggle's result must be
        captured into a variable BEFORE a st.container() block, and the
        heavy components.html() call must live inside that container —
        not directly gated by `if st.toggle(...):`."""
        src = open("pages/Artefatos.py", encoding="utf-8").read()
        idx = src.index('key=f"bpmn_show_{pid}_{sel_ver[\'version\']}",')
        window = src[idx: idx + 800]
        assert "with st.container():" in window
        assert "components.html(bpmn_html" in window
