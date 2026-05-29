# pages/CostBenefitScenarios.py
# ─────────────────────────────────────────────────────────────────────────────
# Cenários de Custo-Benefício — projeta e compara combinações de LLMs por agente.
# Todos os cálculos são síncronos, sem LLM ou rede (NF-1, NF-3).
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from ui.auth_gate import apply_auth_gate
from ui.components.page_header import render_page_header
from core.cost_model import (
    PRICING_CATALOG,
    DEFAULT_TOKEN_PROFILES,
    ModelPricing,
    ScenarioConfig,
    ScenarioResult,
    get_effective_catalog,
    get_models_for_provider,
    get_providers_in_catalog,
    cheapest_model,
    best_quality_model,
    project_cost,
)

apply_auth_gate()

render_page_header(
    "💰",
    "Cenários de Custo-Benefício",
    "Projete e compare o custo estimado de diferentes combinações de LLMs por agente.",
)

# ── Constantes ────────────────────────────────────────────────────────────────

_ALL_AGENTS = [p for p in DEFAULT_TOKEN_PROFILES]
_AGENT_NAMES = [p.agent_name for p in _ALL_AGENTS]
_AGENT_DISPLAY = {p.agent_name: p.display_name for p in _ALL_AGENTS}

# Preset "Balanceado": Groq para Quality/NLP, DeepSeek para BPMN/Minutes/Req,
# Claude Haiku para Synthesizer
_PRESET_BALANCED = {
    "transcript_quality": "llama-3.3-70b-versatile",
    "bpmn":               "deepseek-v4-flash",
    "minutes":            "deepseek-v4-flash",
    "requirements":       "deepseek-v4-flash",
    "sbvr":               "llama-3.3-70b-versatile",
    "bmm":                "llama-3.3-70b-versatile",
    "synthesizer":        "claude-haiku-4-5-20251001",
    "dmn":                "deepseek-v4-flash",
    "argumentation":      "deepseek-v4-flash",
}

_MAX_SCENARIOS = 5

# ── Session state defaults ────────────────────────────────────────────────────

if "cost_catalog_overrides" not in st.session_state:
    st.session_state["cost_catalog_overrides"] = {}

if "cost_n_scenarios" not in st.session_state:
    st.session_state["cost_n_scenarios"] = 2

if "cost_active_agents" not in st.session_state:
    st.session_state["cost_active_agents"] = _AGENT_NAMES[:]

if "cost_word_count" not in st.session_state:
    st.session_state["cost_word_count"] = 1500

if "cost_n_bpmn_runs" not in st.session_state:
    st.session_state["cost_n_bpmn_runs"] = 1


def _scen_key(scen_idx: int, agent_name: str, field: str) -> str:
    return f"cbs_s{scen_idx}_{agent_name}_{field}"


def _scen_name_key(scen_idx: int) -> str:
    return f"cbs_s{scen_idx}_name"


def _init_scenario_defaults(catalog: list[ModelPricing]) -> None:
    """Inicializa chaves de session_state para todos os cenários se ausentes."""
    n = st.session_state["cost_n_scenarios"]
    providers = get_providers_in_catalog(catalog)
    default_provider = providers[0] if providers else ""
    default_model = catalog[0].model_id if catalog else ""

    preset_names = ["Custo Mínimo", "Qualidade Máxima", "Balanceado", "Cenário 4", "Cenário 5"]
    for i in range(_MAX_SCENARIOS):
        if _scen_name_key(i) not in st.session_state:
            st.session_state[_scen_name_key(i)] = preset_names[i]
        for agent in _AGENT_NAMES:
            prov_key = _scen_key(i, agent, "provider")
            mod_key  = _scen_key(i, agent, "model")
            if prov_key not in st.session_state:
                st.session_state[prov_key] = default_provider
            if mod_key not in st.session_state:
                st.session_state[mod_key] = default_model


def _apply_preset_min_cost(scen_idx: int, catalog: list[ModelPricing]) -> None:
    cheapest = cheapest_model(catalog)
    for agent in _AGENT_NAMES:
        st.session_state[_scen_key(scen_idx, agent, "provider")] = cheapest.provider
        st.session_state[_scen_key(scen_idx, agent, "model")]    = cheapest.model_id


def _apply_preset_max_quality(scen_idx: int, catalog: list[ModelPricing]) -> None:
    best = best_quality_model(catalog)
    for agent in _AGENT_NAMES:
        st.session_state[_scen_key(scen_idx, agent, "provider")] = best.provider
        st.session_state[_scen_key(scen_idx, agent, "model")]    = best.model_id


def _apply_preset_balanced(scen_idx: int, catalog: list[ModelPricing]) -> None:
    catalog_by_id = {m.model_id: m for m in catalog}
    for agent, model_id in _PRESET_BALANCED.items():
        pricing = catalog_by_id.get(model_id)
        if pricing:
            st.session_state[_scen_key(scen_idx, agent, "provider")] = pricing.provider
            st.session_state[_scen_key(scen_idx, agent, "model")]    = model_id


def _build_scenario(scen_idx: int) -> ScenarioConfig:
    name = st.session_state.get(_scen_name_key(scen_idx), f"Cenário {scen_idx + 1}")
    active = st.session_state["cost_active_agents"]
    assignments = {}
    for agent in active:
        model_id = st.session_state.get(_scen_key(scen_idx, agent, "model"), "")
        if model_id:
            assignments[agent] = model_id
    return ScenarioConfig(
        name=name,
        assignments=assignments,
        n_bpmn_runs=st.session_state["cost_n_bpmn_runs"],
        active_agents=active,
    )


# ── Catálogo efetivo ──────────────────────────────────────────────────────────

catalog = get_effective_catalog(st.session_state["cost_catalog_overrides"])
_init_scenario_defaults(catalog)
providers_in_catalog = get_providers_in_catalog(catalog)

# ── Layout principal ──────────────────────────────────────────────────────────

col_left, col_right = st.columns([4, 6])

# ═══════════════════════════════════════════════════════════════════════════════
# PAINEL ESQUERDO
# ═══════════════════════════════════════════════════════════════════════════════
with col_left:

    # ── Parâmetros de transcrição ─────────────────────────────────────────────
    st.subheader("Parâmetros de transcrição")

    st.session_state["cost_word_count"] = st.number_input(
        "Palavras estimadas na transcrição",
        min_value=100, max_value=50000,
        value=st.session_state["cost_word_count"],
        step=100,
        help="Afeta proporcionalmente a estimativa de tokens de entrada por agente.",
    )

    st.session_state["cost_active_agents"] = st.multiselect(
        "Agentes a executar",
        options=_AGENT_NAMES,
        default=st.session_state["cost_active_agents"],
        format_func=lambda x: _AGENT_DISPLAY.get(x, x),
    )

    st.session_state["cost_n_bpmn_runs"] = st.slider(
        "Número de runs BPMN (torneio)",
        min_value=1, max_value=5,
        value=st.session_state["cost_n_bpmn_runs"],
        help="Multiplica o custo do Agente BPMN pelo número de runs.",
    )

    n_scen_input = st.number_input(
        "Número de cenários a comparar",
        min_value=1, max_value=_MAX_SCENARIOS,
        value=st.session_state["cost_n_scenarios"],
        step=1,
    )
    st.session_state["cost_n_scenarios"] = int(n_scen_input)

    st.divider()

    # ── Editor de cenários ────────────────────────────────────────────────────
    st.subheader("Editor de cenários")

    n_scen = st.session_state["cost_n_scenarios"]
    tab_labels = [
        st.session_state.get(_scen_name_key(i), f"Cenário {i+1}")
        for i in range(n_scen)
    ]
    scen_tabs = st.tabs(tab_labels)

    for scen_idx, tab in enumerate(scen_tabs):
        with tab:
            # Nome do cenário
            new_name = st.text_input(
                "Nome do cenário",
                value=st.session_state.get(_scen_name_key(scen_idx), f"Cenário {scen_idx+1}"),
                key=f"cbs_nameInput_{scen_idx}",
            )
            st.session_state[_scen_name_key(scen_idx)] = new_name

            # Botões de preset
            p1, p2, p3 = st.columns(3)
            if p1.button("Custo Mínimo", key=f"cbs_preset_min_{scen_idx}", use_container_width=True):
                _apply_preset_min_cost(scen_idx, catalog)
                st.rerun()
            if p2.button("Qualidade Máx.", key=f"cbs_preset_max_{scen_idx}", use_container_width=True):
                _apply_preset_max_quality(scen_idx, catalog)
                st.rerun()
            if p3.button("Balanceado", key=f"cbs_preset_bal_{scen_idx}", use_container_width=True):
                _apply_preset_balanced(scen_idx, catalog)
                st.rerun()

            st.caption("Agente → Provedor → Modelo")

            # Tabela de seleção por agente
            active_agents = st.session_state["cost_active_agents"]
            word_count = st.session_state["cost_word_count"]
            catalog_by_id = {m.model_id: m for m in catalog}

            for agent_name in active_agents:
                display = _AGENT_DISPLAY.get(agent_name, agent_name)
                prov_key = _scen_key(scen_idx, agent_name, "provider")
                mod_key  = _scen_key(scen_idx, agent_name, "model")

                cur_provider = st.session_state.get(prov_key, providers_in_catalog[0])
                if cur_provider not in providers_in_catalog:
                    cur_provider = providers_in_catalog[0]

                ca1, ca2, ca3 = st.columns([2, 2, 1])
                ca1.markdown(f"**{display}**")

                new_provider = ca2.selectbox(
                    "Provedor",
                    options=providers_in_catalog,
                    index=providers_in_catalog.index(cur_provider),
                    key=f"cbs_prov_{scen_idx}_{agent_name}",
                    label_visibility="collapsed",
                )
                st.session_state[prov_key] = new_provider

                models_for_prov = get_models_for_provider(new_provider, catalog)
                model_ids = [m.model_id for m in models_for_prov]
                cur_model = st.session_state.get(mod_key, model_ids[0] if model_ids else "")
                if cur_model not in model_ids:
                    cur_model = model_ids[0] if model_ids else ""

                new_model = ca3.selectbox(
                    "Modelo",
                    options=model_ids,
                    index=model_ids.index(cur_model) if cur_model in model_ids else 0,
                    format_func=lambda mid: catalog_by_id[mid].label if mid in catalog_by_id else mid,
                    key=f"cbs_mod_{scen_idx}_{agent_name}",
                    label_visibility="collapsed",
                )
                st.session_state[mod_key] = new_model

            # Rodapé do cenário: custo total + quality index
            scen_cfg = _build_scenario(scen_idx)
            result = project_cost(scen_cfg, word_count, catalog)
            st.markdown(
                f"**Custo estimado:** `${result.total_cost_usd:.5f}` &nbsp;|&nbsp; "
                f"**Quality Index médio:** `{result.avg_quality_index:.1f}/10`"
            )
            if result.warnings:
                for w in result.warnings:
                    st.warning(w, icon="⚠️")

    st.divider()

    # ── Catálogo de preços (expandable) ───────────────────────────────────────
    with st.expander("Catálogo de preços — editar valores"):
        st.caption("Alterações afetam apenas esta sessão.")
        catalog_data = [
            {
                "Provedor": m.provider,
                "Modelo": m.model_id,
                "Label": m.label,
                "Input $/1M": m.input_price_per_1m,
                "Output $/1M": m.output_price_per_1m,
                "Quality Index": m.quality_index,
                "Contexto K": m.context_window_k,
                "Notas": m.notes,
            }
            for m in catalog
        ]
        edited = st.data_editor(
            catalog_data,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "Provedor":       st.column_config.TextColumn(disabled=True),
                "Modelo":         st.column_config.TextColumn(disabled=True),
                "Label":          st.column_config.TextColumn(disabled=True),
                "Input $/1M":     st.column_config.NumberColumn(format="%.4f", min_value=0.0),
                "Output $/1M":    st.column_config.NumberColumn(format="%.4f", min_value=0.0),
                "Quality Index":  st.column_config.NumberColumn(format="%.1f", min_value=0.0, max_value=10.0),
                "Contexto K":     st.column_config.NumberColumn(disabled=True),
                "Notas":          st.column_config.TextColumn(disabled=True),
            },
            key="cbs_catalog_editor",
        )

        # Salvar overrides em session_state
        overrides: dict = {}
        for row, base in zip(edited, PRICING_CATALOG):
            if (row["Input $/1M"] != base.input_price_per_1m
                    or row["Output $/1M"] != base.output_price_per_1m
                    or row["Quality Index"] != base.quality_index):
                overrides[base.model_id] = {
                    "input_price_per_1m":  row["Input $/1M"],
                    "output_price_per_1m": row["Output $/1M"],
                    "quality_index":       row["Quality Index"],
                }
        st.session_state["cost_catalog_overrides"] = overrides

        if st.button("Restaurar padrões", key="cbs_restore"):
            st.session_state["cost_catalog_overrides"] = {}
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PAINEL DIREITO
# ═══════════════════════════════════════════════════════════════════════════════
with col_right:

    # Calcular resultados de todos os cenários
    n_scen = st.session_state["cost_n_scenarios"]
    word_count = st.session_state["cost_word_count"]
    results: list[ScenarioResult] = []
    scenarios: list[ScenarioConfig] = []
    for i in range(n_scen):
        scen_cfg = _build_scenario(i)
        scenarios.append(scen_cfg)
        results.append(project_cost(scen_cfg, word_count, catalog))

    import plotly.graph_objects as go
    import plotly.express as px

    # ── Gráfico 1: Custo por agente (barras empilhadas) ───────────────────────
    st.subheader("Custo por agente por cenário")

    active_agents = st.session_state["cost_active_agents"]
    agent_colors = px.colors.qualitative.Plotly

    fig_bar = go.Figure()
    for agent_idx, agent_name in enumerate(active_agents):
        display = _AGENT_DISPLAY.get(agent_name, agent_name)
        y_vals = [r.per_agent.get(agent_name, 0.0) for r in results]
        scen_names = [r.scenario_name for r in results]

        # Build tooltip per scenario
        catalog_by_id = {m.model_id: m for m in catalog}
        hover_texts = []
        for i, r in enumerate(results):
            model_id = scenarios[i].assignments.get(agent_name, "—")
            pricing = catalog_by_id.get(model_id)
            prov = pricing.provider if pricing else "—"
            lbl  = pricing.label    if pricing else model_id
            cost_val = r.per_agent.get(agent_name, 0.0)
            hover_texts.append(
                f"<b>{display}</b><br>"
                f"Provedor: {prov}<br>"
                f"Modelo: {lbl}<br>"
                f"Custo: ${cost_val:.6f}"
            )

        fig_bar.add_trace(go.Bar(
            name=display,
            x=scen_names,
            y=y_vals,
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_texts,
            marker_color=agent_colors[agent_idx % len(agent_colors)],
        ))

    fig_bar.update_layout(
        barmode="stack",
        xaxis_title="Cenário",
        yaxis_title="Custo USD",
        yaxis_tickformat="$.5f",
        legend_title="Agente",
        height=320,
        margin=dict(t=20, b=20),
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # ── Gráfico 2: Custo × Qualidade (scatter) ────────────────────────────────
    st.subheader("Custo vs. Qualidade")

    scen_names_list  = [r.scenario_name for r in results]
    costs_list       = [r.total_cost_usd for r in results]
    quality_list     = [r.avg_quality_index for r in results]
    n_agents_list    = [len(r.per_agent) for r in results]

    fig_scatter = go.Figure()
    fig_scatter.add_trace(go.Scatter(
        x=costs_list,
        y=quality_list,
        mode="markers+text",
        text=scen_names_list,
        textposition="top center",
        marker=dict(
            size=[max(12, n * 4) for n in n_agents_list],
            color=costs_list,
            colorscale="RdYlGn_r",
            showscale=True,
            colorbar=dict(title="USD"),
        ),
        hovertemplate=(
            "<b>%{text}</b><br>"
            "Custo: $%{x:.5f}<br>"
            "Quality: %{y:.1f}/10<extra></extra>"
        ),
    ))
    # Quadrante ideal (baixo custo, alta qualidade)
    if costs_list and quality_list:
        median_cost = sorted(costs_list)[len(costs_list) // 2]
        median_qual = sorted(quality_list)[len(quality_list) // 2]
        fig_scatter.add_shape(
            type="rect",
            x0=0, x1=median_cost,
            y0=median_qual, y1=10.5,
            fillcolor="rgba(0,200,0,0.07)",
            line=dict(width=0),
        )
        fig_scatter.add_annotation(
            x=median_cost / 2, y=10.3,
            text="zona ideal",
            showarrow=False,
            font=dict(color="green", size=11),
        )

    fig_scatter.update_layout(
        xaxis_title="Custo Total USD",
        yaxis_title="Quality Index médio",
        xaxis_tickformat="$.5f",
        yaxis_range=[0, 10.5],
        height=300,
        margin=dict(t=20, b=20),
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

    # ── Tabela resumo ─────────────────────────────────────────────────────────
    st.subheader("Resumo")

    table_rows = []
    for r in results:
        table_rows.append({
            "Cenário":        r.scenario_name,
            "Custo Total":    f"${r.total_cost_usd:.5f}",
            "Quality Index":  f"{r.avg_quality_index:.1f}",
            "Custo/Qualidade": f"${r.cost_per_quality:.5f}" if r.avg_quality_index > 0 else "—",
            "Warnings":       len(r.warnings),
        })
    st.dataframe(table_rows, use_container_width=True, hide_index=True)

    # ── Botão "Aplicar Cenário" ────────────────────────────────────────────────
    st.subheader("Aplicar cenário ao pipeline")

    scen_labels = [r.scenario_name for r in results]
    selected_scen_label = st.selectbox(
        "Selecionar cenário para aplicar",
        options=scen_labels,
        key="cbs_apply_select",
    )
    selected_scen_idx = scen_labels.index(selected_scen_label) if selected_scen_label in scen_labels else 0
    selected_scen = scenarios[selected_scen_idx]

    if st.button(
        f"Aplicar '{selected_scen_label}' ao Pipeline",
        type="primary",
        key="cbs_apply_btn",
        use_container_width=True,
    ):
        st.session_state["scenario_assignments"] = dict(selected_scen.assignments)
        st.session_state["scenario_name"] = selected_scen_label
        st.session_state["n_bpmn_runs"] = selected_scen.n_bpmn_runs
        st.success(
            f"Cenário **{selected_scen_label}** aplicado. "
            f"{len(selected_scen.assignments)} agente(s) configurado(s)."
        )
        st.page_link("pages/Pipeline.py", label="Ir para Pipeline", icon="🚀")

    # Botão para limpar cenário ativo
    if st.session_state.get("scenario_assignments"):
        if st.button("Limpar cenário ativo", key="cbs_clear_btn"):
            st.session_state.pop("scenario_assignments", None)
            st.session_state.pop("scenario_name", None)
            st.success("Cenário removido. Pipeline voltará ao modelo padrão.")
            st.rerun()
