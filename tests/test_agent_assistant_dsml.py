# tests/test_agent_assistant_dsml.py
"""
Regression tests for the DeepSeek DSML tool-call-leak parser in
agents/agent_assistant.py.

Bug report: user asked "Mostre os encaminhamentos por responsável em
gráfico" and the model leaked raw tool-call markup as visible chat text
instead of executing the tool calls. Root cause: DeepSeek doubled the
delimiter character on each side of "DSML" ("<｜｜DSML｜｜invoke ...>"
instead of the previously-observed single delimiter "<｜DSML｜invoke
...>"), and the parser's regexes assumed exactly one delimiter char,
so _parse_dsml_tool_calls() silently returned [] and _strip_dsml()
returned the text unmodified.
"""

from agents.agent_assistant import _parse_dsml_tool_calls, _strip_dsml, _DSML_DETECT_RE

_LEAKED_DOUBLE_PIPE = (
    'Vou tentar extrair as decisões de cada reunião, que costumam conter os '
    'encaminhamentos com responsáveis.\n\n'
    '<｜｜DSML｜｜tool_calls>\n'
    '<｜｜DSML｜｜invoke name="get_meeting_decisions">\n'
    '<｜｜DSML｜｜parameter name="meeting_number" string="false">1</｜｜DSML｜｜parameter>\n'
    '</｜｜DSML｜｜invoke>\n'
    '<｜｜DSML｜｜invoke name="get_meeting_decisions">\n'
    '<｜｜DSML｜｜parameter name="meeting_number" string="false">2</｜｜DSML｜｜parameter>\n'
    '</｜｜DSML｜｜invoke>\n'
    '<｜｜DSML｜｜invoke name="get_meeting_decisions">\n'
    '<｜｜DSML｜｜parameter name="meeting_number" string="false">3</｜｜DSML｜｜parameter>\n'
    '</｜｜DSML｜｜invoke>\n'
    '<｜｜DSML｜｜invoke name="get_meeting_decisions">\n'
    '<｜｜DSML｜｜parameter name="meeting_number" string="false">4</｜｜DSML｜｜parameter>\n'
    '</｜｜DSML｜｜invoke>'
)

_LEAKED_SINGLE_PIPE = (
    'Vou verificar.\n\n'
    '<｜DSML｜function_calls>\n'
    '<｜DSML｜invoke name="get_meeting_action_items">\n'
    '<｜DSML｜parameter name="meeting_number">1</｜DSML｜parameter>\n'
    '</｜DSML｜invoke>\n'
    '</｜DSML｜function_calls>'
)

_LEAKED_ASCII_PIPE = (
    'Vou verificar.\n\n'
    '<|DSML|invoke name="get_meeting_summary">\n'
    '<|DSML|parameter name="meeting_number">5</|DSML|parameter>\n'
    '</|DSML|invoke>'
)

_CLEAN_PREFIX = (
    'Vou tentar extrair as decisões de cada reunião, que costumam conter os '
    'encaminhamentos com responsáveis.'
)


class TestDetectDoubledDelimiter:
    def test_detects_doubled_fullwidth_pipe(self):
        assert _DSML_DETECT_RE.search(_LEAKED_DOUBLE_PIPE)

    def test_detects_single_fullwidth_pipe(self):
        assert _DSML_DETECT_RE.search(_LEAKED_SINGLE_PIPE)

    def test_detects_ascii_pipe(self):
        assert _DSML_DETECT_RE.search(_LEAKED_ASCII_PIPE)

    def test_no_false_positive_on_clean_text(self):
        assert not _DSML_DETECT_RE.search("Texto normal sem nenhuma marcação especial.")


class TestParseDoubledDelimiter:
    """The exact payload from the user's bug report — 4 chained invokes,
    doubled fullwidth-pipe delimiters, extra 'string=\"false\"' attribute
    on the parameter tag."""

    def test_parses_all_four_invokes(self):
        calls = _parse_dsml_tool_calls(_LEAKED_DOUBLE_PIPE)
        assert len(calls) == 4
        assert all(c["name"] == "get_meeting_decisions" for c in calls)

    def test_parses_meeting_numbers_as_ints_in_order(self):
        calls = _parse_dsml_tool_calls(_LEAKED_DOUBLE_PIPE)
        assert [c["args"]["meeting_number"] for c in calls] == [1, 2, 3, 4]


class TestParseSingleDelimiterStillWorks:
    """Guard against regressing the previously-working single-delimiter format."""

    def test_parses_single_pipe_invoke(self):
        calls = _parse_dsml_tool_calls(_LEAKED_SINGLE_PIPE)
        assert len(calls) == 1
        assert calls[0]["name"] == "get_meeting_action_items"
        assert calls[0]["args"]["meeting_number"] == 1

    def test_parses_ascii_pipe_invoke(self):
        calls = _parse_dsml_tool_calls(_LEAKED_ASCII_PIPE)
        assert len(calls) == 1
        assert calls[0]["name"] == "get_meeting_summary"
        assert calls[0]["args"]["meeting_number"] == 5


class TestStripDsml:
    def test_strips_doubled_delimiter_leak_leaving_only_human_text(self):
        result = _strip_dsml(_LEAKED_DOUBLE_PIPE)
        assert result == _CLEAN_PREFIX
        assert "DSML" not in result
        assert "invoke" not in result

    def test_strips_single_delimiter_leak(self):
        result = _strip_dsml(_LEAKED_SINGLE_PIPE)
        assert result == "Vou verificar."
        assert "DSML" not in result

    def test_no_op_on_clean_text(self):
        clean = "Esta é uma resposta normal, sem nenhuma marcação."
        assert _strip_dsml(clean) == clean
