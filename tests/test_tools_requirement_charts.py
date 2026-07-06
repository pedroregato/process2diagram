# tests/test_tools_requirement_charts.py
"""
Tests for the 6 PC142 chart tools added to
core/tools/tools_admin_charts_entities.py, proposed by the assistant after
PC140/141 as a richer visual repertoire for committee-style presentations:
generate_requirements_flow_chart (sankey/treemap/sunburst),
generate_requirements_heatmap, generate_requirements_bubble_chart,
generate_requirements_waterfall, generate_meeting_radar_chart,
generate_gantt_chart.

Also covers two bugfixes discovered while implementing them:
- generate_custom_chart's promised but unimplemented chart_type="heatmap".
- generate_requirements_chart / generate_meetings_timeline filtering
  directly on a nonexistent requirements.meeting_number column.

No real DB/LLM calls — Supabase mocked via a small fake client keyed by
table name.
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


class _FakeChain:
    """Mimics db.table(x).select(...).eq(...).order(...).limit(...).execute()."""

    def __init__(self, rows):
        self._rows = rows

    def select(self, *a, **k):
        return self

    def eq(self, col, val):
        self._rows = [r for r in self._rows if r.get(col) == val]
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def execute(self):
        resp = MagicMock()
        resp.data = self._rows
        return resp


class _FakeDB:
    """Routes db.table(name) to a per-table row list."""

    def __init__(self, tables: dict):
        self._tables = tables

    def table(self, name):
        return _FakeChain(self._tables.get(name, []))


_MEETINGS = [
    {"id": "m1", "meeting_number": 1, "title": "Kickoff", "project_id": "proj-1",
     "minutes_md": "## Decisões\n- Decisão A\n- Decisão B\n\n## Participantes\n- Ana\n- Bruno\n\n## Ações\n- Ação 1"},
    {"id": "m2", "meeting_number": 2, "title": "Sprint Review", "project_id": "proj-1",
     "minutes_md": "## Decisões\n- Decisão C\n\n## Participantes\n- Ana\n\n## Ações\n- Ação 2\n- Ação 3"},
]

_REQS = [
    {"req_type": "functional", "priority": "alta", "status": "active", "first_meeting_id": "m1", "project_id": "proj-1"},
    {"req_type": "functional", "priority": "alta", "status": "active", "first_meeting_id": "m1", "project_id": "proj-1"},
    {"req_type": "non_functional", "priority": "média", "status": "contradicted", "first_meeting_id": "m2", "project_id": "proj-1"},
    {"req_type": "functional", "priority": "baixa", "status": "active", "first_meeting_id": "m2", "project_id": "proj-1"},
]


def _patched_db(project_id="proj-1", meetings=None, reqs=None):
    return _FakeDB({"meetings": meetings if meetings is not None else _MEETINGS,
                     "requirements": reqs if reqs is not None else _REQS})


class TestRequirementsWithMeetingNumbers:
    def test_no_supabase_configured(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=None):
            rows, err = ex._requirements_with_meeting_numbers()
        assert rows == []
        assert "Supabase" in err

    def test_resolves_meeting_number_via_first_meeting_id(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db()):
            rows, err = ex._requirements_with_meeting_numbers()
        assert err == ""
        assert [r["meeting_number"] for r in rows] == [1, 1, 2, 2]

    def test_meeting_number_filter_not_found(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db()):
            rows, err = ex._requirements_with_meeting_numbers(meeting_number=99)
        assert rows == []
        assert "não encontrada" in err

    def test_empty_requirements(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db(reqs=[])):
            rows, err = ex._requirements_with_meeting_numbers()
        assert rows == []
        assert "Nenhum requisito" in err


class TestGenerateRequirementsChartBugfix:
    """PC142: generate_requirements_chart used to filter directly with
    .eq('meeting_number', ...) on the requirements table, a column that
    doesn't exist there — every call with meeting_number set failed."""

    def test_meeting_number_filter_now_resolves_correctly(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db()):
            result = ex.generate_requirements_chart(group_by="type", meeting_number=1)
        assert "Gráfico gerado" in result
        assert len(ex._pending_charts) == 1

    def test_no_meeting_number_still_works(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db()):
            result = ex.generate_requirements_chart(group_by="type")
        assert "Gráfico gerado" in result


class TestGenerateMeetingsTimelineBugfix:
    """PC142: requirements-per-meeting bars were always zero because the
    query filtered on the nonexistent meeting_number column."""

    def test_requirement_counts_now_populated(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db()):
            result = ex.generate_meetings_timeline(metric="requirements")
        assert "Gráfico gerado" in result
        fig = ex._pending_charts[0]
        req_trace = next(t for t in fig["data"] if t.get("name") == "Requisitos")
        assert list(req_trace["y"]) == [2, 2]


class TestDarkLayoutLegendContrast:
    """PC145: legend text had no explicit font color set, only the top-level
    layout font — reported by the user as low-contrast/unreadable legend
    labels against the dark background. _dark_layout() must set an explicit
    legend.font.color so it can never fail to inherit."""

    def test_legend_font_color_is_explicit(self):
        ex = _executor()
        ex.generate_custom_chart(chart_type="bar", title="T", labels=["a"], values=[1], series_name="S")
        legend = ex._pending_charts[0]["layout"]["legend"]
        assert legend["font"]["color"] == "#FAFAF8"

    def test_legend_font_color_survives_downstream_legend_overrides(self):
        """generate_requirements_heatmap etc. call _dark_layout() then set
        additional legend keys — those must merge, not wipe out font."""
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db()):
            ex.generate_requirements_flow_chart()
        legend = ex._pending_charts[0]["layout"].get("legend", {})
        if legend:
            assert legend.get("font", {}).get("color") == "#FAFAF8"


class TestGenerateCustomChartHeatmap:
    def test_heatmap_without_z_matrix_errors(self):
        ex = _executor()
        result = ex.generate_custom_chart(
            chart_type="heatmap", title="T", labels=["a", "b"], values=[1, 2],
        )
        assert "z_matrix" in result
        assert ex._pending_charts == []

    def test_heatmap_with_z_matrix_renders(self):
        ex = _executor()
        result = ex.generate_custom_chart(
            chart_type="heatmap", title="T", labels=["a", "b"], values=[],
            z_matrix=[[1, 2], [3, 4]], y_axis_labels=["r1", "r2"],
        )
        assert "Heatmap" in result
        assert len(ex._pending_charts) == 1
        assert ex._pending_charts[0]["data"][0]["type"] == "heatmap"


class TestGenerateRequirementsFlowChart:
    def test_sankey_default(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db()):
            result = ex.generate_requirements_flow_chart()
        assert "Sankey" in result
        assert ex._pending_charts[0]["data"][0]["type"] == "sankey"

    def test_treemap(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db()):
            result = ex.generate_requirements_flow_chart(view="treemap")
        assert "Treemap" in result
        assert ex._pending_charts[0]["data"][0]["type"] == "treemap"

    def test_sunburst(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db()):
            result = ex.generate_requirements_flow_chart(view="sunburst")
        assert ex._pending_charts[0]["data"][0]["type"] == "sunburst"

    def test_invalid_view(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db()):
            result = ex.generate_requirements_flow_chart(view="bogus")
        assert "inválida" in result
        assert ex._pending_charts == []

    def test_meeting_number_filter(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db()):
            result = ex.generate_requirements_flow_chart(meeting_number=1)
        assert "2 requisito" in result


class TestGenerateRequirementsHeatmap:
    def test_default_dimension(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db()):
            result = ex.generate_requirements_heatmap()
        assert "Heatmap gerado" in result
        z = ex._pending_charts[0]["data"][0]["z"]
        assert len(z) == 2  # 2 meetings

    def test_priority_dimension(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db()):
            result = ex.generate_requirements_heatmap(dimension="priority")
        assert "prioridade" in result

    def test_no_requirements(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db(reqs=[])):
            result = ex.generate_requirements_heatmap()
        assert "Nenhum requisito" in result


class TestGenerateRequirementsBubbleChart:
    def test_bubble_chart(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db()):
            result = ex.generate_requirements_bubble_chart()
        assert "Bubble chart gerado" in result
        trace = ex._pending_charts[0]["data"][0]
        assert trace["type"] == "scatter"
        assert len(trace["x"]) == 2

    def test_no_requirements(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db(reqs=[])):
            result = ex.generate_requirements_bubble_chart()
        assert "Nenhum requisito" in result


class TestGenerateRequirementsWaterfall:
    def test_waterfall_counts(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db()):
            result = ex.generate_requirements_waterfall()
        assert "Waterfall gerado" in result
        trace = ex._pending_charts[0]["data"][0]
        assert trace["type"] == "waterfall"
        # meeting 1: +2 added, 0 removed -> net 2; meeting 2: +2 added, 1 removed (contradicted) -> net 1
        assert list(trace["y"]) == [2, 1, 0]
        assert list(trace["measure"]) == ["relative", "relative", "total"]

    def test_no_requirements(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db(reqs=[])):
            result = ex.generate_requirements_waterfall()
        assert "Nenhum requisito" in result


class TestGenerateMeetingRadarChart:
    def test_requires_at_least_two_meetings(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db()):
            result = ex.generate_meeting_radar_chart(meeting_numbers=[1])
        assert "pelo menos 2" in result

    def test_default_all_meetings(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db()):
            result = ex.generate_meeting_radar_chart()
        assert "Radar gerado" in result
        assert len(ex._pending_charts[0]["data"]) == 2

    def test_no_meetings_found_for_filter(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db()):
            result = ex.generate_meeting_radar_chart(meeting_numbers=[999, 998])
        assert "não encontrada" in result.lower() or "Nenhuma reunião" in result

    def test_axes_reflect_minutes_counts(self):
        ex = _executor()
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db()):
            ex.generate_meeting_radar_chart(meeting_numbers=[1, 2])
        trace1 = ex._pending_charts[0]["data"][0]
        # meeting 1: 2 decisions, 1 action, 2 reqs, 2 participants (closed loop repeats first value)
        assert list(trace1["r"])[:4] == [2, 1, 2, 2]


class TestGenerateGanttChart:
    def test_basic_gantt(self):
        ex = _executor()
        phases = [
            {"name": "Fase 1", "start": "2026-01-01", "end": "2026-02-01", "status": "concluído"},
            {"name": "Fase 2", "start": "2026-02-01", "end": "2026-03-15"},
        ]
        result = ex.generate_gantt_chart(title="Cronograma", phases=phases)
        assert "Gantt" in result
        assert len(ex._pending_charts[0]["data"]) == 2

    def test_no_phases(self):
        ex = _executor()
        result = ex.generate_gantt_chart(title="Cronograma", phases=[])
        assert "Nenhuma fase" in result
        assert ex._pending_charts == []

    def test_invalid_date(self):
        ex = _executor()
        result = ex.generate_gantt_chart(title="X", phases=[{"name": "F1", "start": "not-a-date", "end": "2026-01-01"}])
        assert "Data inválida" in result

    def test_sorted_by_start_date(self):
        ex = _executor()
        phases = [
            {"name": "Segunda", "start": "2026-03-01", "end": "2026-04-01"},
            {"name": "Primeira", "start": "2026-01-01", "end": "2026-02-01"},
        ]
        ex.generate_gantt_chart(title="X", phases=phases)
        names = [t["y"][0] for t in ex._pending_charts[0]["data"]]
        assert names == ["Primeira", "Segunda"]


class TestDispatchWiring:
    """Every new tool must be reachable through execute()'s dispatch dict."""

    def test_all_new_tools_dispatch(self):
        ex = _executor()
        calls = {
            "generate_requirements_flow_chart": {},
            "generate_requirements_heatmap": {},
            "generate_requirements_bubble_chart": {},
            "generate_requirements_waterfall": {},
            "generate_meeting_radar_chart": {},
            "generate_gantt_chart": {"title": "T", "phases": [{"name": "F1", "start": "2026-01-01", "end": "2026-01-02"}]},
        }
        with patch("modules.supabase_client.get_supabase_client", return_value=_patched_db()):
            for name, args in calls.items():
                result = ex.execute(name, args)
                assert isinstance(result, str)
                assert "Erro" not in result or name == "generate_meeting_radar_chart"

    def test_generate_custom_chart_passes_heatmap_kwargs(self):
        ex = _executor()
        result = ex.execute("generate_custom_chart", {
            "chart_type": "heatmap", "title": "T", "labels": ["a"], "values": [],
            "z_matrix": [[1]], "y_axis_labels": ["r1"],
        })
        assert "Heatmap" in result


class TestAdminGateAbsence:
    def test_new_tools_not_admin_gated(self):
        from core.assistant_tools import _ADMIN_TOOLS
        new_tools = {
            "generate_requirements_flow_chart", "generate_requirements_heatmap",
            "generate_requirements_bubble_chart", "generate_requirements_waterfall",
            "generate_meeting_radar_chart", "generate_gantt_chart",
        }
        assert new_tools.isdisjoint(_ADMIN_TOOLS)

    def test_new_tools_categorized_as_grafico(self):
        from core.assistant_tools import _TOOL_CATEGORIES
        for name in (
            "generate_requirements_flow_chart", "generate_requirements_heatmap",
            "generate_requirements_bubble_chart", "generate_requirements_waterfall",
            "generate_meeting_radar_chart", "generate_gantt_chart",
        ):
            assert _TOOL_CATEGORIES.get(name) == "grafico"
