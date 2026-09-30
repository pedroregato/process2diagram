# tests/test_cost_benefit_scenarios_tabs_to_radio.py
"""
NAV-17 (melhorias/parciais/navegabilidade.md): pages/CostBenefitScenarios.py
era a página mais lenta medida em produção (~30s) — não por falta de cache
(a página é Python puro, sem Supabase/LLM), mas porque st.tabs() renderiza
TODOS os corpos a cada rerun. Com até 5 cenários x 9 agentes x ~3 widgets
cada, isso é ~150 widgets construídos sempre, mesmo olhando só 1 cenário.

Fix: st.tabs() virou st.radio() — só o cenário selecionado desenha seus
widgets de edição. Isso só foi seguro porque _build_scenario(scen_idx) já
lia exclusivamente de st.session_state (sem depender de nenhum widget ter
sido renderizado nesta execução) e _init_scenario_defaults() já populava
os 5 slots de cenário desde o carregamento inicial da página — a seção de
"Comparação de cenários" continua vendo TODOS os cenários (não só o
selecionado no radio), calculados via _build_scenario()+project_cost()
direto, sem nenhum widget envolvido.

Página sem dependência de Supabase/LLM (Python puro, core/cost_model.py) —
dá pra testar via AppTest.from_file() direto, sem mock nenhum.
"""

from unittest.mock import patch

import streamlit as st
from streamlit.testing.v1 import AppTest

st.page_link = lambda *a, **k: None

# Depois de aplicar um cenário, a página mostra um banner com um
# `coluna.page_link("pages/Pipeline.py", ...)` (código pré-existente, não
# tocado por este fix) — chamado no objeto de coluna, não em `st` direto,
# então o monkeypatch de `st.page_link` acima não alcança. AppTest.from_file()
# só registra a página-alvo do teste, então qualquer page_link pra OUTRA
# página lançaria StreamlitPageNotFoundError; patch na classe intercepta as
# duas formas de chamada.
_PAGE_LINK_PATCH = patch(
    "streamlit.elements.widgets.button.ButtonMixin.page_link",
    lambda self, *a, **k: None,
)


def _base_app() -> AppTest:
    at = AppTest.from_file("pages/CostBenefitScenarios.py", default_timeout=60)
    at.session_state["_autenticado"] = True
    at.session_state["_usuario_login"] = "teste"
    at.session_state["_usuario_nome"] = "Teste"
    at.session_state["_role"] = "user"
    return at


class TestOnlySelectedScenarioRendersWidgets:
    def test_default_two_scenarios_renders_only_one_scenarios_worth_of_selectboxes(self):
        at = _base_app()
        at.run()
        assert not at.exception

        n_agents = len(at.session_state["cost_active_agents"])
        # 2 selectboxes por agente (provedor + modelo) — só do cenário
        # selecionado no radio, não dos 2 cenários (cost_n_scenarios=2
        # por padrão) que existiam antes do fix.
        assert len(at.selectbox) == n_agents * 2

    def test_only_one_scenario_editor_footer_is_shown(self):
        at = _base_app()
        at.run()
        assert not at.exception

        footers = [m.value for m in at.markdown if "Custo total estimado" in m.value]
        assert len(footers) == 1


class TestComparisonIncludesAllScenariosRegardlessOfSelection:
    def test_comparison_table_has_one_row_per_scenario_plus_default(self):
        at = _base_app()
        at.run()
        assert not at.exception

        n_scen = at.session_state["cost_n_scenarios"]
        # Procura a tabela de comparação pelo formato (N linhas = default +
        # cada cenário, colunas de custo/qualidade) — a única com n_scen+1
        # linhas entre os dataframes da página.
        comparison_tables = [
            df.value for df in at.dataframe
            if len(df.value) == n_scen + 1
        ]
        assert comparison_tables, (
            f"nenhuma tabela com {n_scen + 1} linhas (default + {n_scen} cenários) encontrada"
        )

    def test_three_scenarios_still_all_appear_in_comparison_without_visiting_their_tabs(self):
        at = _base_app()
        at.session_state["cost_n_scenarios"] = 3
        at.run()
        assert not at.exception

        # Só o cenário 0 (padrão do radio) tem widgets renderizados nesta
        # execução — mas a comparação deve, mesmo assim, contar 4 linhas
        # (default + 3 cenários), provando que built_scenarios/built_results
        # não dependem de nenhum widget ter sido desenhado.
        comparison_tables = [df.value for df in at.dataframe if len(df.value) == 4]
        assert comparison_tables


class TestSwitchingScenarioPreservesOtherScenariosConfig:
    def test_editing_scenario_0_then_switching_to_scenario_1_keeps_scenario_0_provider(self):
        at = _base_app()
        at.run()
        assert not at.exception

        # Muda o provedor do 1º agente no cenário 0 (selecionado por
        # padrão) — sem format_func, ao contrário do selectbox de modelo,
        # então .options/.value são os valores crus, sem ambiguidade.
        first_provider_select = at.selectbox[0]  # [0]=provedor do 1º agente
        original_options = list(first_provider_select.options)
        new_value = next(o for o in original_options if o != first_provider_select.value)
        first_provider_select.set_value(new_value).run()
        assert not at.exception

        agent0 = at.session_state["cost_active_agents"][0]
        assert at.session_state[f"cbs_s0_{agent0}_provider"] == new_value

        # Troca pro cenário 1 via radio.
        at.radio[0].set_value(1).run()
        assert not at.exception

        # A config do cenário 0 continua intacta em session_state mesmo
        # sem seus widgets estarem mais renderizados.
        assert at.session_state[f"cbs_s0_{agent0}_provider"] == new_value


class TestApplyButtonStillWorksForSelectedScenario:
    def test_apply_button_writes_scenario_assignments(self):
        with _PAGE_LINK_PATCH:
            at = _base_app()
            at.run()
            assert not at.exception

            apply_btn = next(b for b in at.button if b.key == "cbs_apply_0")
            apply_btn.click().run()
            assert not at.exception

        assert at.session_state["scenario_name"] == at.session_state["cbs_s0_name"]
        assert at.session_state["scenario_assignments"]


class TestScenarioCountShrinkDoesNotBreakRadio:
    def test_reducing_scenario_count_below_selected_index_resets_selection(self):
        at = _base_app()
        at.session_state["cost_n_scenarios"] = 3
        at.run()
        at.radio[0].set_value(2).run()
        assert not at.exception
        assert at.session_state["cbs_active_scenario_idx"] == 2

        # Reduz de 3 pra 1 cenário — índice 2 não existe mais.
        at.session_state["cost_n_scenarios"] = 1
        at.run()
        assert not at.exception
        assert at.session_state["cbs_active_scenario_idx"] == 0
