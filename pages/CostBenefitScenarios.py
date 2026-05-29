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

_ALL_AGENTS = list(DEFAULT_TOKEN_PROFILES)
_AGENT_NAMES = [p.agent_name for p in _ALL_AGENTS]
_AGENT_DISPLAY = {p.agent_name: p.display_name for p in _ALL_AGENTS}

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


# ── Helpers de chave ──────────────────────────────────────────────────────────

def _scen_key(scen_idx: int, agent_name: str, field: str) -> str:
    return f"cbs_s{scen_idx}_{agent_name}_{field}"

def _scen_name_key(scen_idx: int) -> str:
    return f"cbs_s{scen_idx}_name"


# ── Inicialização de defaults ─────────────────────────────────────────────────

def _init_scenario_defaults(catalog: list[ModelPricing]) -> None:
    providers = get_providers_in_catalog(catalog)
    default_provider = providers[0] if providers else ""
    default_model = catalog[0].model_id if catalog else ""
    preset_names = ["Custo Mínimo", "Qualidade Máxima", "Balanceado", "Cenário 4", "Cenário 5"]
    for i in range(_MAX_SCENARIOS):
        if _scen_name_key(i) not in st.session_state:
            st.session_state[_scen_name_key(i)] = preset_names[i]
        for agent in _AGENT_NAMES:
            if _scen_key(i, agent, "provider") not in st.session_state:
                st.session_state[_scen_key(i, agent, "provider")] = default_provider
            if _scen_key(i, agent, "model") not in st.session_state:
                st.session_state[_scen_key(i, agent, "model")] = default_model


# ── Presets ───────────────────────────────────────────────────────────────────

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


# ── Build de cenário ──────────────────────────────────────────────────────────

def _build_scenario(scen_idx: int) -> ScenarioConfig:
    name   = st.session_state.get(_scen_name_key(scen_idx), f"Cenário {scen_idx + 1}")
    active = st.session_state["cost_active_agents"]
    assignments = {
        agent: st.session_state.get(_scen_key(scen_idx, agent, "model"), "")
        for agent in active
        if st.session_state.get(_scen_key(scen_idx, agent, "model"), "")
    }
    return ScenarioConfig(
        name=name,
        assignments=assignments,
        n_bpmn_runs=st.session_state["cost_n_bpmn_runs"],
        active_agents=active,
    )


def _build_default_scenario(catalog: list[ModelPricing]) -> ScenarioConfig:
    """Cenário que espelha a configuração global atual do pipeline (sidebar)."""
    provider_name = st.session_state.get("selected_provider", "DeepSeek")
    provider_cfg  = st.session_state.get("provider_cfg", {})
    model_id      = provider_cfg.get("default_model", "")

    catalog_by_id = {m.model_id: m for m in catalog}
    if model_id not in catalog_by_id:
        for m in catalog:
            if m.provider == provider_name:
                model_id = m.model_id
                break
        else:
            model_id = catalog[0].model_id if catalog else ""

    active = st.session_state.get("cost_active_agents", _AGENT_NAMES[:])
    return ScenarioConfig(
        name="Default (configuração atual)",
        assignments={agent: model_id for agent in active},
        n_bpmn_runs=st.session_state.get("n_bpmn_runs", 1),
        active_agents=active,
    )


# ── Aplicar / restaurar cenário ───────────────────────────────────────────────

def _do_apply(scen: ScenarioConfig) -> None:
    """Salva backup do estado anterior e ativa o novo cenário."""
    st.session_state["scenario_assignments_backup"] = dict(
        st.session_state.get("scenario_assignments") or {}
    )
    st.session_state["scenario_name_backup"] = st.session_state.get("scenario_name", "Default (configuração atual)")
    st.session_state["scenario_assignments"] = dict(scen.assignments)
    st.session_state["scenario_name"]        = scen.name
    st.session_state["n_bpmn_runs"]          = scen.n_bpmn_runs

def _do_restore() -> None:
    """Restaura o cenário anterior ao último apply."""
    prev_assignments = st.session_state.pop("scenario_assignments_backup", {})
    prev_name        = st.session_state.pop("scenario_name_backup", "Default (configuração atual)")
    if prev_assignments:
        st.session_state["scenario_assignments"] = prev_assignments
        st.session_state["scenario_name"]        = prev_name
    else:
        st.session_state.pop("scenario_assignments", None)
        st.session_state.pop("scenario_name", None)

def _do_clear() -> None:
    """Remove qualquer cenário ativo — pipeline volta ao modelo global."""
    st.session_state.pop("scenario_assignments", None)
    st.session_state.pop("scenario_name", None)
    st.session_state.pop("scenario_assignments_backup", None)
    st.session_state.pop("scenario_name_backup", None)


# ── Setup inicial ─────────────────────────────────────────────────────────────

catalog = get_effective_catalog(st.session_state["cost_catalog_overrides"])
_init_scenario_defaults(catalog)
providers_in_catalog = get_providers_in_catalog(catalog)
catalog_by_id = {m.model_id: m for m in catalog}
word_count = st.session_state["cost_word_count"]

# ═══════════════════════════════════════════════════════════════════════════════
# STATUS — cenário ativo + opções de restauração
# ═══════════════════════════════════════════════════════════════════════════════

active_assignments = st.session_state.get("scenario_assignments")
active_name        = st.session_state.get("scenario_name", "")
has_backup         = bool(st.session_state.get("scenario_assignments_backup"))

if active_assignments:
    parts = " | ".join(f"{k}: `{v}`" for k, v in list(active_assignments.items())[:4])
    more  = f" + {len(active_assignments) - 4} mais" if len(active_assignments) > 4 else ""
    st.success(
        f"**Cenário ativo: \"{active_name}\"** — {parts}{more}",
        icon="✅",
    )
    bcol1, bcol2, bcol3 = st.columns(3)
    if has_backup:
        prev_name = st.session_state.get("scenario_name_backup", "anterior")
        if bcol1.button(f"Restaurar '{prev_name}'", key="cbs_restore_prev", use_container_width=True):
            _do_restore()
            st.rerun()
    if bcol2.button("Voltar ao Default", key="cbs_clear_to_default", use_container_width=True):
        _do_clear()
        st.rerun()
    bcol3.page_link("pages/Pipeline.py", label="Ir para Pipeline", icon="🚀")
else:
    st.info("Nenhum cenário ativo. Configure e aplique um cenário abaixo.", icon="ℹ️")

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# PARÂMETROS DE TRANSCRIÇÃO
# ═══════════════════════════════════════════════════════════════════════════════

with st.expander("Parâmetros de transcrição", expanded=True):
    pc1, pc2, pc3, pc4 = st.columns(4)
    st.session_state["cost_word_count"] = pc1.number_input(
        "Palavras estimadas",
        min_value=100, max_value=50000,
        value=st.session_state["cost_word_count"],
        step=100,
        help="Escala os tokens de entrada proporcionalmente.",
    )
    st.session_state["cost_n_bpmn_runs"] = pc2.slider(
        "Runs BPMN",
        min_value=1, max_value=5,
        value=st.session_state["cost_n_bpmn_runs"],
        help="Multiplica custo do Agente BPMN.",
    )
    n_scen_input = pc3.number_input(
        "Nº de cenários",
        min_value=1, max_value=_MAX_SCENARIOS,
        value=st.session_state["cost_n_scenarios"],
        step=1,
    )
    st.session_state["cost_n_scenarios"] = int(n_scen_input)

    st.session_state["cost_active_agents"] = st.multiselect(
        "Agentes a incluir",
        options=_AGENT_NAMES,
        default=st.session_state["cost_active_agents"],
        format_func=lambda x: _AGENT_DISPLAY.get(x, x),
    )

word_count = st.session_state["cost_word_count"]

# ═══════════════════════════════════════════════════════════════════════════════
# CENÁRIO DEFAULT (referência — somente leitura)
# ═══════════════════════════════════════════════════════════════════════════════

default_scenario = _build_default_scenario(catalog)
default_result   = project_cost(default_scenario, word_count, catalog)

with st.expander(
    f"Cenário Default — {default_scenario.name}  "
    f"(custo: ${default_result.total_cost_usd:.5f} | Q: {default_result.avg_quality_index:.1f})",
    expanded=False,
):
    _prov_def = st.session_state.get("selected_provider", "—")
    _mod_def  = st.session_state.get("provider_cfg", {}).get("default_model", "—")
    st.caption(
        f"Provedor global: **{_prov_def}** | Modelo: **{_mod_def}** | "
        f"Todos os agentes usam este modelo."
    )
    _def_rows = []
    for ag in st.session_state["cost_active_agents"]:
        mid = default_scenario.assignments.get(ag, "—")
        pr  = catalog_by_id.get(mid)
        _def_rows.append({
            "Agente":  _AGENT_DISPLAY.get(ag, ag),
            "Modelo":  pr.label if pr else mid,
            "Custo":   f"${default_result.per_agent.get(ag, 0):.6f}",
        })
    st.dataframe(_def_rows, use_container_width=True, hide_index=True)

    if st.button("Aplicar Default ao Pipeline", key="cbs_apply_default"):
        _do_apply(default_scenario)
        st.success(f"Cenário Default aplicado.")
        st.rerun()

st.divider()

# ═══════════════════════════════════════════════════════════════════════════════
# EDITOR DE CENÁRIOS — coluna única
# ═══════════════════════════════════════════════════════════════════════════════

st.subheader("Editor de cenários")

n_scen = st.session_state["cost_n_scenarios"]
tab_labels = [
    st.session_state.get(_scen_name_key(i), f"Cenário {i+1}")
    for i in range(n_scen)
]
scen_tabs = st.tabs(tab_labels)

built_scenarios: list[ScenarioConfig] = []
built_results:   list[ScenarioResult]  = []

for scen_idx, tab in enumerate(scen_tabs):
    with tab:
        # Nome
        new_name = st.text_input(
            "Nome do cenário",
            value=st.session_state.get(_scen_name_key(scen_idx), f"Cenário {scen_idx+1}"),
            key=f"cbs_nameInput_{scen_idx}",
        )
        st.session_state[_scen_name_key(scen_idx)] = new_name

        # Presets
        p1, p2, p3 = st.columns(3)
        if p1.button("Custo Mínimo",   key=f"cbs_pmin_{scen_idx}", use_container_width=True):
            _apply_preset_min_cost(scen_idx, catalog)
            st.rerun()
        if p2.button("Qualidade Máx.", key=f"cbs_pmax_{scen_idx}", use_container_width=True):
            _apply_preset_max_quality(scen_idx, catalog)
            st.rerun()
        if p3.button("Balanceado",     key=f"cbs_pbal_{scen_idx}", use_container_width=True):
            _apply_preset_balanced(scen_idx, catalog)
            st.rerun()

        st.caption("Configure o provedor e o modelo para cada agente:")

        active_agents = st.session_state["cost_active_agents"]

        for agent_name in active_agents:
            display  = _AGENT_DISPLAY.get(agent_name, agent_name)
            prov_key = _scen_key(scen_idx, agent_name, "provider")
            mod_key  = _scen_key(scen_idx, agent_name, "model")

            cur_provider = st.session_state.get(prov_key, providers_in_catalog[0])
            if cur_provider not in providers_in_catalog:
                cur_provider = providers_in_catalog[0]

            st.markdown(f"**{display}**")
            col_prov, col_mod, col_cost = st.columns([3, 4, 2])

            new_provider = col_prov.selectbox(
                "Provedor",
                options=providers_in_catalog,
                index=providers_in_catalog.index(cur_provider),
                key=f"cbs_prov_{scen_idx}_{agent_name}",
            )
            st.session_state[prov_key] = new_provider

            models_for_prov = get_models_for_provider(new_provider, catalog)
            model_ids = [m.model_id for m in models_for_prov]
            cur_model = st.session_state.get(mod_key, model_ids[0] if model_ids else "")
            if cur_model not in model_ids:
                cur_model = model_ids[0] if model_ids else ""

            new_model = col_mod.selectbox(
                "Modelo",
                options=model_ids,
                index=model_ids.index(cur_model) if cur_model in model_ids else 0,
                format_func=lambda mid: catalog_by_id[mid].label if mid in catalog_by_id else mid,
                key=f"cbs_mod_{scen_idx}_{agent_name}",
            )
            st.session_state[mod_key] = new_model

            # Custo parcial estimado
            from core.cost_model import estimate_tokens, DEFAULT_TOKEN_PROFILES as _DTP
            _prof = next((p for p in _DTP if p.agent_name == agent_name), None)
            if _prof and new_model in catalog_by_id:
                _pr   = catalog_by_id[new_model]
                _inp, _out = estimate_tokens(_prof, word_count)
                _n = st.session_state["cost_n_bpmn_runs"] if agent_name == "bpmn" else 1
                _c = (_inp * _n * _pr.input_price_per_1m + _out * _n * _pr.output_price_per_1m) / 1_000_000
                col_cost.metric("Custo est.", f"${_c:.5f}")

        # Rodapé com total + Aplicar
        scen_cfg = _build_scenario(scen_idx)
        result   = project_cost(scen_cfg, word_count, catalog)
        built_scenarios.append(scen_cfg)
        built_results.append(result)

        st.markdown("---")
        rf1, rf2 = st.columns([3, 2])
        rf1.markdown(
            f"**Custo total estimado:** `${result.total_cost_usd:.5f}` &nbsp;|&nbsp; "
            f"**Quality Index:** `{result.avg_quality_index:.1f}/10`"
        )

        if result.warnings:
            for w in result.warnings:
                st.warning(w, icon="⚠️")

        # ── Botão Aplicar por cenário ──────────────────────────────────────
        if rf2.button(
            f"Aplicar '{new_name}' ao Pipeline",
            key=f"cbs_apply_{scen_idx}",
            type="primary",
            use_container_width=True,
        ):
            _do_apply(scen_cfg)
            st.success(
                f"Cenário **{new_name}** aplicado a {len(scen_cfg.assignments)} agente(s). "
                f"Vá para o Pipeline para executar."
            )
            st.page_link("pages/Pipeline.py", label="Ir para Pipeline", icon="🚀")
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# COMPARAÇÃO — gráficos + tabela (incluindo Default)
# ═══════════════════════════════════════════════════════════════════════════════

all_scenarios = [default_scenario] + built_scenarios
all_results   = [default_result]   + built_results

import plotly.graph_objects as go
import plotly.express as px

st.divider()
st.subheader("Comparação de cenários")

active_agents = st.session_state["cost_active_agents"]
agent_colors  = px.colors.qualitative.Plotly

# ── Gráfico 1: barras empilhadas ──────────────────────────────────────────────
fig_bar = go.Figure()
for agent_idx, agent_name in enumerate(active_agents):
    display    = _AGENT_DISPLAY.get(agent_name, agent_name)
    scen_names = [r.scenario_name for r in all_results]
    y_vals     = [r.per_agent.get(agent_name, 0.0) for r in all_results]
    hover_texts = []
    for i, r in enumerate(all_results):
        mid     = all_scenarios[i].assignments.get(agent_name, "—")
        pricing = catalog_by_id.get(mid)
        hover_texts.append(
            f"<b>{display}</b><br>"
            f"Provedor: {pricing.provider if pricing else '—'}<br>"
            f"Modelo: {pricing.label if pricing else mid}<br>"
            f"Custo: ${r.per_agent.get(agent_name, 0):.6f}"
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
    height=340,
    margin=dict(t=10, b=10),
)
st.plotly_chart(fig_bar, use_container_width=True)

# ── Gráfico 2: scatter Custo × Qualidade ─────────────────────────────────────
costs_list   = [r.total_cost_usd    for r in all_results]
quality_list = [r.avg_quality_index for r in all_results]
scen_labels  = [r.scenario_name     for r in all_results]
n_agents_list= [len(r.per_agent)    for r in all_results]

fig_scatter = go.Figure()
fig_scatter.add_trace(go.Scatter(
    x=costs_list,
    y=quality_list,
    mode="markers+text",
    text=scen_labels,
    textposition="top center",
    marker=dict(
        size=[max(14, n * 4) for n in n_agents_list],
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
if costs_list and quality_list:
    median_cost = sorted(costs_list)[len(costs_list) // 2]
    median_qual = sorted(quality_list)[len(quality_list) // 2]
    fig_scatter.add_shape(
        type="rect", x0=0, x1=median_cost, y0=median_qual, y1=10.5,
        fillcolor="rgba(0,200,0,0.07)", line=dict(width=0),
    )
    fig_scatter.add_annotation(
        x=median_cost / 2, y=10.3, text="zona ideal",
        showarrow=False, font=dict(color="green", size=11),
    )
fig_scatter.update_layout(
    xaxis_title="Custo Total USD",
    yaxis_title="Quality Index médio",
    xaxis_tickformat="$.5f",
    yaxis_range=[0, 10.5],
    height=320,
    margin=dict(t=10, b=10),
)
st.plotly_chart(fig_scatter, use_container_width=True)

# ── Tabela resumo ─────────────────────────────────────────────────────────────
table_rows = []
for r in all_results:
    is_active = (r.scenario_name == active_name and bool(active_assignments))
    table_rows.append({
        "Cenário":          ("✅ " if is_active else "") + r.scenario_name,
        "Custo Total":      f"${r.total_cost_usd:.5f}",
        "Quality Index":    f"{r.avg_quality_index:.1f}",
        "Custo/Qualidade":  f"${r.cost_per_quality:.5f}" if r.avg_quality_index > 0 else "—",
        "Warnings":         len(r.warnings),
    })
st.dataframe(table_rows, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════════════════════
# CATÁLOGO DE PREÇOS
# ═══════════════════════════════════════════════════════════════════════════════

st.divider()
with st.expander("Catálogo de preços — editar valores"):
    st.caption("Alterações afetam apenas esta sessão.")
    catalog_data = [
        {
            "Provedor":      m.provider,
            "Modelo":        m.model_id,
            "Label":         m.label,
            "Input $/1M":    m.input_price_per_1m,
            "Output $/1M":   m.output_price_per_1m,
            "Quality Index": m.quality_index,
            "Contexto K":    m.context_window_k,
            "Notas":         m.notes,
        }
        for m in catalog
    ]
    edited = st.data_editor(
        catalog_data,
        use_container_width=True,
        num_rows="fixed",
        column_config={
            "Provedor":      st.column_config.TextColumn(disabled=True),
            "Modelo":        st.column_config.TextColumn(disabled=True),
            "Label":         st.column_config.TextColumn(disabled=True),
            "Input $/1M":    st.column_config.NumberColumn(format="%.4f", min_value=0.0),
            "Output $/1M":   st.column_config.NumberColumn(format="%.4f", min_value=0.0),
            "Quality Index": st.column_config.NumberColumn(format="%.1f", min_value=0.0, max_value=10.0),
            "Contexto K":    st.column_config.NumberColumn(disabled=True),
            "Notas":         st.column_config.TextColumn(disabled=True),
        },
        key="cbs_catalog_editor",
    )
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

    if st.button("Restaurar padrões", key="cbs_restore_cat"):
        st.session_state["cost_catalog_overrides"] = {}
        st.rerun()
