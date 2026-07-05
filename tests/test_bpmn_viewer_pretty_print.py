# tests/test_bpmn_viewer_pretty_print.py
"""
Tests for modules/bpmn_viewer.py::pretty_print_xml() (PC133).

User feedback 2026-07-05: BPMN XML shown in st.code() boxes across
BpmnStudio.py / BpmnEditor.py was a single continuous line — the generator
(xml.etree.ElementTree.write()) emits no whitespace between tags, which is
fine for storage/bpmn-js/DB but unreadable as displayed text. This is a
display-only formatter: it must never be written back into hub.bpmn.bpmn_xml
or persisted.
"""

from modules.bpmn_viewer import pretty_print_xml

_ONE_LINE_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<definitions xmlns="http://www.omg.org/spec/BPMN/20100524/MODEL">'
    '<process id="p1"><startEvent id="s1" name="Inicio"/>'
    '<userTask id="t1" name="Fazer Algo"><documentation>Detalhe da tarefa.</documentation></userTask>'
    '<endEvent id="e1" name="Fim"/>'
    '<sequenceFlow id="f1" sourceRef="s1" targetRef="t1"/>'
    '<sequenceFlow id="f2" sourceRef="t1" targetRef="e1"/>'
    '</process></definitions>'
)


class TestPrettyPrintXml:
    def test_adds_line_breaks(self):
        result = pretty_print_xml(_ONE_LINE_XML)
        assert result.count("\n") > 5
        assert "\n" in result

    def test_preserves_all_element_ids(self):
        result = pretty_print_xml(_ONE_LINE_XML)
        for eid in ("s1", "t1", "e1", "f1", "f2"):
            assert f'"{eid}"' in result

    def test_preserves_documentation_text(self):
        result = pretty_print_xml(_ONE_LINE_XML)
        assert "Detalhe da tarefa." in result

    def test_no_blank_lines(self):
        """minidom scatters whitespace-only lines between every tag by
        default — these must be stripped for a compact, readable result."""
        result = pretty_print_xml(_ONE_LINE_XML)
        lines = result.split("\n")
        assert all(ln.strip() for ln in lines), "blank lines should be stripped"

    def test_indentation_present(self):
        result = pretty_print_xml(_ONE_LINE_XML)
        lines = result.split("\n")
        assert any(ln.startswith("  ") for ln in lines), "nested elements should be indented"

    def test_empty_string_returns_unchanged(self):
        assert pretty_print_xml("") == ""

    def test_malformed_xml_fails_open(self):
        malformed = "<definitions><process><unclosed></process>"
        assert pretty_print_xml(malformed) == malformed

    def test_preserves_original_xml_declaration_with_encoding(self):
        """minidom's own toprettyxml() drops encoding="UTF-8" from the
        declaration line -- the original one must be re-attached verbatim."""
        result = pretty_print_xml(_ONE_LINE_XML)
        assert result.startswith('<?xml version="1.0" encoding="UTF-8"?>')

    def test_result_is_still_valid_xml(self):
        import xml.etree.ElementTree as ET
        result = pretty_print_xml(_ONE_LINE_XML)
        root = ET.fromstring(result)  # must not raise
        assert root is not None
