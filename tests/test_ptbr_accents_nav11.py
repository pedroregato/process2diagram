# tests/test_ptbr_accents_nav11.py
"""
NAV-11 parcial (melhorias/parciais/navegabilidade.md, PC217): 2 fixes
concretos citados no plano de navegabilidade — ui/input_area.py tinha texto
em inglês ("Input Transcript", "Generate Insights") sobrevivendo desde uma
versão anterior do app; pages/KnowledgeGraph.py tinha uma seção inteira de
texto de ajuda sem acentuação ("O que e", "Relacoes", "Contradicoes" etc.)
e vazava os valores brutos de entity_type (ACTOR/SYSTEM/DEPARTMENT/PERSON…)
sem tradução no multiselect de filtro e na coluna "Tipo" da tabela.

A varredura ampla de acentuação (20 arquivos com match de
`[a-z]cao\\b|[a-z]coes\\b`, a maioria ruído — nomes de variável, comentários
internos) fica no backlog — este teste cobre só os 2 itens concretos que
foram de fato corrigidos nesta rodada.
"""

from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


class TestInputAreaIsPortuguese:
    def test_no_leftover_english_ui_strings(self):
        src = (_ROOT / "ui" / "input_area.py").read_text(encoding="utf-8")
        for leftover in ("Input Transcript", "Generate Insights",
                          "Paste your meeting transcript here", "Or upload a file"):
            assert leftover not in src, f'string em inglês ainda presente: "{leftover}"'


class TestKnowledgeGraphAccentsAndLegend:
    def _src(self) -> str:
        return (_ROOT / "pages" / "KnowledgeGraph.py").read_text(encoding="utf-8")

    def test_help_expander_title_is_accented(self):
        assert "O que é um Grafo de Conhecimento" in self._src()
        assert "O que e um Grafo de Conhecimento" not in self._src()

    def test_kpi_labels_are_accented(self):
        src = self._src()
        assert 'k3.metric("Fatos / Relações"' in src
        assert 'k4.metric("Contradições"' in src

    def test_entity_type_legend_is_translated_for_display(self):
        src = self._src()
        assert "_TYPE_LABEL_PT" in src
        # multiselect de filtro usa format_func — não traduz o valor
        # armazenado (usado pra filtrar), só o rótulo mostrado ao usuário.
        assert "format_func=lambda t: _TYPE_LABEL_PT.get(t, t)" in src
        # coluna "Tipo" da tabela de entidades também traduz pra exibição.
        assert '_TYPE_LABEL_PT.get(e.get("entity_type", ""), e.get("entity_type", "—"))' in src

    def test_no_leftover_unaccented_markers_in_help_block(self):
        src = self._src()
        for leftover in (
            "relacoes semanticas", "Deteccao de conflitos", "Contradicoes entre fatos",
            "Ocorrencias minimas", "Simulacao fisica", "Arestas de contradicao",
            "Fatos / Decisoes", "nao esta instalada",
        ):
            assert leftover not in src, f'texto sem acentuação ainda presente: "{leftover}"'
