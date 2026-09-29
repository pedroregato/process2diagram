# tests/test_ux02_kpi_row_wiring.py
"""
UX-02 (melhorias/ux-amigabilidade-e-elegancia.md): confirma que os 5 blocos
de KPI com 5-7 colunas citados na auditoria (ROI-TR, Saúde do Contexto,
Validação x2, Central de Artefatos) migraram para ui/components/kpi_row.py
— o comportamento do componente em si já tem cobertura funcional via
AppTest em tests/test_kpi_row_component.py.

pages/Settings.py NÃO está nesta lista: a auditoria citou "Configurações"
como truncando, mas checando o código as métricas de Settings.py estão
todas em linhas de no máx. 3 colunas (st.columns(3)) — não reproduz o
sintoma descrito. Corrigir aqui seria mudar um layout que já cabe, então
foi deixado de fora (mesmo raciocínio de "verificar antes de aplicar" já
usado nesta rodada pro UX-05).

Checagem estática, mesmo padrão dos demais testes desta rodada.
"""

from pathlib import Path

_PAGES_DIR = Path(__file__).resolve().parent.parent / "pages"

_MIGRATED_PAGES = [
    "MeetingROI.py",
    "ContextHealth.py",
    "ValidationHub.py",
    "Artefatos.py",
]


class TestPagesImportKpiRow:
    def test_all_four_pages_import_kpi_row(self):
        for fname in _MIGRATED_PAGES:
            src = (_PAGES_DIR / fname).read_text(encoding="utf-8")
            assert "from ui.components.kpi_row import kpi_row" in src, (
                f"{fname}: não importa kpi_row"
            )


class TestNoWideColumnsAssignedToMetricVars:
    def test_no_5_to_7_column_metric_row_remains(self):
        # Os st.columns(N>=5) originalmente citados na auditoria não devem
        # mais existir com esse padrão (var1, var2, ..., varN = st.columns(N)).
        patterns = [
            "c1, c2, c3, c4, c5, c6 = st.columns(6)",   # Artefatos.py (KPI resumo)
            "c1, c2, c3, c4, c5, c6 = st.columns(6)",   # MeetingROI.py
            "c1,c2,c3,c4,c5,c6,c7 = st.columns(7)",     # ContextHealth.py
            "m1, m2, m3, m4, m5 = st.columns(5)",       # ValidationHub.py (topo)
            "_kc1, _kc2, _kc3, _kc4, _kc5, _kc6 = st.columns(6)",  # ValidationHub.py (coverage)
        ]
        for fname in _MIGRATED_PAGES:
            src = (_PAGES_DIR / fname).read_text(encoding="utf-8")
            for pattern in patterns:
                assert pattern not in src, f"{fname}: ainda contém '{pattern}'"


class TestEachMigratedBlockCallsKpiRow:
    def test_meeting_roi_kpi_block_uses_kpi_row(self):
        src = (_PAGES_DIR / "MeetingROI.py").read_text(encoding="utf-8")
        anchor = src.index('"label": "ROI-TR Médio"')
        assert "kpi_row([" in src[max(0, anchor - 200):anchor]

    def test_context_health_kpi_block_uses_kpi_row(self):
        src = (_PAGES_DIR / "ContextHealth.py").read_text(encoding="utf-8")
        anchor = src.index('"label": "Saúde Geral"')
        assert "kpi_row([" in src[max(0, anchor - 200):anchor]

    def test_validation_hub_top_kpi_block_uses_kpi_row(self):
        src = (_PAGES_DIR / "ValidationHub.py").read_text(encoding="utf-8")
        anchor = src.index('"label": "Total de artefatos"')
        assert "kpi_row([" in src[max(0, anchor - 200):anchor]

    def test_validation_hub_coverage_kpi_block_uses_kpi_row(self):
        src = (_PAGES_DIR / "ValidationHub.py").read_text(encoding="utf-8")
        anchor = src.index('"label": "Reuniões", "value": _n')
        assert "kpi_row([" in src[max(0, anchor - 200):anchor]

    def test_artefatos_overview_kpi_block_uses_kpi_row(self):
        src = (_PAGES_DIR / "Artefatos.py").read_text(encoding="utf-8")
        anchor = src.index('"label": "Requisitos"')
        assert "kpi_row([" in src[max(0, anchor - 200):anchor]


class TestSettingsDeliberatelyUnchanged:
    def test_settings_metrics_still_in_3_column_rows_not_5_plus(self):
        src = (_PAGES_DIR / "Settings.py").read_text(encoding="utf-8")
        assert "kpi_row" not in src
        import re
        wide_rows = re.findall(r"st\.columns\((\d+)\)", src)
        assert all(int(n) <= 4 for n in wide_rows), (
            "Settings.py ganhou uma linha de 5+ colunas — reconsiderar migrar pra kpi_row"
        )
