# pages/CostEstimator.py
# ─────────────────────────────────────────────────────────────────────────────
# Estimativa de Custos LLM — Process2Diagram
#
# Três seções:
#   1. Histórico real — tokens consumidos por reunião (do Supabase)
#   2. Calculadora de cenários — quanto custaria processar N reuniões
#   3. Comparação de provedores — tabela lado a lado para o cenário configurado
#
# Zero chamadas LLM — cálculo puramente Python.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pandas as pd
import streamlit as st

from ui.auth_gate import apply_auth_gate
from modules.supabase_client import supabase_configured
from modules.cost_estimator import (
    PROVIDER_PRICING,
    EMBEDDING_PRICING,
    AGENT_TOKEN_PROFILE,
    estimate_scenario,
    estimate_embedding_cost,
    compare_providers,
    cost_for_tokens,
)
from core.project_store import list_projects, _db, _ok

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Custos LLM — Process2Diagram",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_auth_gate()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 💰 Estimativa de Custos LLM")
st.caption(
    "Análise de custo real (histórico de tokens do banco) e estimativas para cenários futuros. "
    "Preços aproximados — consulte a página oficial de cada provedor para valores atualizados."
)

# ── Aviso de preços ───────────────────────────────────────────────────────────
with st.expander("ℹ️ Fontes e premissas dos preços", expanded=False):
    rows = []
    for name, p in PROVIDER_PRICING.items():
        rows.append({
            "Provedor":    name,
            "Modelo":      p["model"],
            "Entrada ($/1M tok)": f"${p['input_usd']:.3f}",
            "Saída ($/1M tok)":   f"${p['output_usd']:.3f}",
            "Tier gratuito": "✅" if p["free_tier"] else "—",
            "Fonte": p["source"],
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.caption(
        "⚠️ Preços válidos em jun/2025. A relação entrada/saída assume ~70% entrada · 30% saída, "
        "típica para transcrições de 2 000–5 000 palavras com o pipeline completo."
    )

st.markdown("---")

# ╔══════════════════════════════════════════════════════════════════╗
# ║  SEÇÃO 1 — Histórico real do projeto                            ║
# ╚══════════════════════════════════════════════════════════════════╝
st.markdown("## 📊 1. Histórico Real de Consumo")

if not supabase_configured():
    st.info("Supabase não configurado — histórico indisponível. Veja as seções 2 e 3 para estimativas.")
else:
    projects = list_projects()
    if projects:
        proj_map  = {p["name"]: p for p in projects}
        sel_proj  = st.selectbox("Projeto", list(proj_map.keys()), key="ce_proj")
        project_id = proj_map[sel_proj]["id"]

        db = _db()
        hist_rows = []
        total_tok  = 0
        total_cost = 0.0

        if db:
            try:
                meetings = _ok(
                    db.table("meetings")
                    .select("meeting_number, title, meeting_date, tokens_used, llm_provider")
                    .eq("project_id", project_id)
                    .order("meeting_number")
                    .execute()
                )
            except Exception:
                meetings = []

            for m in meetings:
                tokens   = m.get("tokens_used") or 0
                provider = m.get("llm_provider") or "—"
                # Estimativa de custo: assume split 70/30 input/output
                inp = int(tokens * 0.70)
                out = int(tokens * 0.30)
                cost = cost_for_tokens(inp, out, provider)
                total_tok  += tokens
                total_cost += cost
                hist_rows.append({
                    "Nº":        m.get("meeting_number") or "—",
                    "Reunião":   m.get("title") or "(sem título)",
                    "Data":      str(m.get("meeting_date") or "—"),
                    "Provedor":  provider,
                    "Tokens":    f"{tokens:,}",
                    "Custo (USD)": f"${cost:.4f}" if cost else "—",
                })

        if hist_rows:
            c1, c2, c3 = st.columns(3)
            c1.metric("Reuniões processadas",  len(hist_rows))
            c2.metric("Tokens totais",          f"{total_tok:,}")
            c3.metric("Custo estimado total",   f"${total_cost:.4f}")

            st.dataframe(
                pd.DataFrame(hist_rows),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                "💡 Custo estimado com base no split 70% entrada / 30% saída aplicado "
                "ao total de tokens registrado por reunião. Pode variar ±20% do custo real."
            )
        else:
            st.info("Nenhuma reunião com tokens registrados neste projeto.")
    else:
        st.info("Nenhum projeto disponível.")

st.markdown("---")

# ╔══════════════════════════════════════════════════════════════════╗
# ║  SEÇÃO 2 — Calculadora de cenários                              ║
# ╚══════════════════════════════════════════════════════════════════╝
st.markdown("## 🧮 2. Calculadora de Cenários")

col_cfg, col_res = st.columns([1, 1], gap="large")

with col_cfg:
    st.markdown("#### ⚙️ Configuração")

    calc_provider = st.selectbox(
        "Provedor LLM",
        list(PROVIDER_PRICING.keys()),
        key="ce_prov",
    )
    calc_n = st.slider(
        "Número de reuniões",
        min_value=1, max_value=200, value=10, step=1,
        key="ce_n",
    )
    calc_passes = st.select_slider(
        "Passes BPMN",
        options=[1, 3, 5],
        value=1,
        key="ce_passes",
        help="Mais passes = melhor BPMN, mais custo",
    )

    st.markdown("**Agentes ativos:**")
    all_agents = list(AGENT_TOKEN_PROFILE.keys())
    # Defaults que correspondem ao pipeline padrão
    default_on  = {"quality", "bpmn", "minutes", "requirements"}
    agent_checks: dict[str, bool] = {}
    for key, profile in AGENT_TOKEN_PROFILE.items():
        agent_checks[key] = st.checkbox(
            profile["label"],
            value=(key in default_on),
            key=f"ce_ag_{key}",
        )

    enabled_agents = [k for k, v in agent_checks.items() if v]

    # Embedding
    st.markdown("**Embeddings (operação única):**")
    calc_embed      = st.checkbox("Incluir custo de embedding", value=False, key="ce_emb")
    if calc_embed:
        embed_prov  = st.selectbox(
            "Provedor de embedding",
            list(EMBEDDING_PRICING.keys()),
            key="ce_emb_prov",
        )
        avg_chars   = st.slider(
            "Tamanho médio da transcrição (chars)",
            min_value=1_000, max_value=100_000, value=15_000, step=1_000,
            key="ce_chars",
            help="Transcrição típica de 1h ≈ 8 000–20 000 chars",
        )
    else:
        embed_prov = "Google Gemini"
        avg_chars  = 15_000

with col_res:
    st.markdown("#### 📋 Estimativa")

    if not enabled_agents:
        st.warning("Selecione ao menos um agente.")
    else:
        est = estimate_scenario(calc_provider, calc_n, enabled_agents, calc_passes)

        # Métricas principais
        m1, m2 = st.columns(2)
        m1.metric("Por reunião",   f"${est.cost_per_meeting:.4f}")
        m2.metric(f"Total ({calc_n} reuniões)", f"${est.total_cost_usd:.4f}")

        m3, m4 = st.columns(2)
        m3.metric("Tokens / reunião", f"{est.total_tokens // calc_n:,}")
        m4.metric("Tokens totais",    f"{est.total_tokens:,}")

        if calc_embed:
            emb_cost = estimate_embedding_cost(calc_n, avg_chars, embed_prov)
            st.metric(
                f"Embedding — {embed_prov}",
                f"${emb_cost:.4f}" if emb_cost > 0 else "Gratuito",
                help="Custo único para indexar todos os chunks (gera uma vez, usa sempre)",
            )
            grand_total = est.total_cost_usd + emb_cost
            st.metric("**Total geral (LLM + Embedding)**", f"${grand_total:.4f}")

        # Breakdown por agente
        st.markdown("**Breakdown por agente (por reunião):**")
        bd_rows = [
            {
                "Agente":       b.label,
                "Tokens entrada": f"{b.input_tokens:,}",
                "Tokens saída":   f"{b.output_tokens:,}",
                "Custo (USD)":    f"${b.cost_usd:.5f}",
            }
            for b in est.breakdown
        ]
        if calc_passes > 1:
            st.caption(f"⚡ BPMN com {calc_passes} passes (passes extras incluídos)")
        st.dataframe(pd.DataFrame(bd_rows), use_container_width=True, hide_index=True)

        # Projeção em BRL
        brl_rate = st.number_input(
            "Taxa USD → BRL",
            min_value=1.0, max_value=20.0, value=5.80, step=0.10,
            key="ce_brl",
            format="%.2f",
        )
        total_brl = est.total_cost_usd * brl_rate
        st.caption(f"💵 Equivalente em BRL: **R$ {total_brl:.2f}** (taxa 1 USD = R$ {brl_rate:.2f})")

st.markdown("---")

# ╔══════════════════════════════════════════════════════════════════╗
# ║  SEÇÃO 3 — Comparação de provedores                             ║
# ╚══════════════════════════════════════════════════════════════════╝
st.markdown("## ⚖️ 3. Comparação de Provedores")
st.caption(f"Cenário: **{calc_n} reuniões**, agentes: **{', '.join(enabled_agents) or '—'}**, passes BPMN: **{calc_passes}**")

if enabled_agents:
    comparison = compare_providers(calc_n, enabled_agents, calc_passes)
    df_comp = pd.DataFrame(comparison)

    # Formata colunas numéricas
    df_comp["Custo total (USD)"] = df_comp["Custo total (USD)"].apply(lambda x: f"${x:.4f}")
    df_comp["Por reunião (USD)"] = df_comp["Por reunião (USD)"].apply(lambda x: f"${x:.5f}")

    st.dataframe(df_comp, use_container_width=True, hide_index=True)

    st.markdown("---")

    # Gráfico de barras de custo total
    try:
        import altair as alt

        chart_data = pd.DataFrame([
            {"Provedor": r["Provedor"], "Custo (USD)": compare_providers(calc_n, enabled_agents, calc_passes)[i]["Custo total (USD)"]}
            for i, r in enumerate(compare_providers(calc_n, enabled_agents, calc_passes))
        ])
        chart = (
            alt.Chart(chart_data)
            .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4)
            .encode(
                x=alt.X("Provedor:N", sort="-y", title=None),
                y=alt.Y("Custo (USD):Q", title="Custo total (USD)"),
                color=alt.Color(
                    "Provedor:N",
                    scale=alt.Scale(
                        domain=list(PROVIDER_PRICING.keys()),
                        range=["#C97B1A", "#1A4B8C", "#1e3a5f", "#1A7F5A", "#6B3FA0"],
                    ),
                    legend=None,
                ),
                tooltip=["Provedor:N", "Custo (USD):Q"],
            )
            .properties(height=280, title=f"Custo total para {calc_n} reuniões por provedor")
        )
        st.altair_chart(chart, use_container_width=True)
    except ImportError:
        pass  # altair não disponível — tabela já exibida acima
else:
    st.warning("Configure os agentes na calculadora acima para ver a comparação.")

st.markdown("---")
st.caption(
    "💡 **Dica**: DeepSeek com cache de prompt ativo pode reduzir o custo de entrada em ~80% "
    "quando múltiplas reuniões compartilham o mesmo sistema de prompt. "
    "Groq e Google Gemini oferecem tiers gratuitos adequados para projetos de pequeno porte."
)
