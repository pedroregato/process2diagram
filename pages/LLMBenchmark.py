# pages/LLMBenchmark.py
# ─────────────────────────────────────────────────────────────────────────────
# LLM Benchmark & Telemetria — Process2Diagram
#
# Dois modos:
#   1. Benchmark On-Demand — dispara chamadas sintéticas para medir latência
#      e throughput em tempo real, por provider e tipo de agente.
#   2. Telemetria Real — analisa dados históricos coletados passivamente pelo
#      pipeline (base_agent registra cada chamada de forma assíncrona).
#
# Métricas:  latência (ms), throughput (tokens/s), p50/p95, heatmap por agente.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import time
import statistics
from typing import Optional

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

from ui.auth_gate import apply_auth_gate
from ui.components.page_header import render_page_header
from modules.config import AVAILABLE_PROVIDERS
from modules.session_security import get_session_llm_client, _session_key
from modules.supabase_client import supabase_configured
from services.llm_telemetry import (
    BENCHMARK_TASKS,
    TRANSCRIPTS,
    TelemetryRecord,
    _telemetry,
    run_benchmark_call,
)
from core.agent_registry import AGENT_REGISTRY


def _skill_version(agent_key: str) -> str | None:
    """Parse version: from YAML frontmatter of the skill file for agent_key."""
    import re
    skill_path = (AGENT_REGISTRY.get(agent_key) or {}).get("skill_path")
    if not skill_path:
        return None
    try:
        content = open(skill_path, encoding="utf-8").read()
        m = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if m:
            v = re.search(r'^version:\s*(.+)', m.group(1), re.MULTILINE)
            if v:
                return v.group(1).strip()
    except Exception:
        pass
    return None

apply_auth_gate()
render_page_header("⚡", "LLM Benchmark & Telemetria", "Avalie latência e throughput de cada provider por tipo de agente")

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.bm-card {
    background:#0d1b2a; border:1px solid #1e3a5f; border-radius:8px;
    padding:14px 18px; margin-bottom:10px;
}
.bm-metric-label { color:#8ab4d4; font-size:.78rem; margin-bottom:2px; }
.bm-metric-value { color:#f0f4f8; font-size:1.4rem; font-weight:700; }
.bm-badge-ok   { background:#1A7F5A22; color:#4ade80; border:1px solid #1A7F5A;
                  border-radius:4px; padding:1px 8px; font-size:.75rem; }
.bm-badge-err  { background:#B5451B22; color:#f87171; border:1px solid #B5451B;
                  border-radius:4px; padding:1px 8px; font-size:.75rem; }
</style>
""", unsafe_allow_html=True)

_PALETTE = [
    "#C97B1A", "#1A4B8C", "#1A7F5A", "#6B3FA0", "#B5451B",
    "#1A7BB5", "#4A7C59", "#7B3F6E", "#5C4A1E", "#2E6B8C",
]

tab_bench, tab_tele = st.tabs(["🧪 Benchmark On-Demand", "📊 Telemetria Real"])


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  TAB 1 — BENCHMARK ON-DEMAND                                            ║
# ╚══════════════════════════════════════════════════════════════════════════╝
with tab_bench:
    st.markdown(
        "Dispara chamadas LLM reais com transcrições sintéticas e mede latência e throughput "
        "para cada combinação de **provider × agente**. Os resultados são opcionalmente "
        "gravados na telemetria histórica."
    )
    st.markdown("---")

    col_cfg, col_res = st.columns([1, 2], gap="large")

    with col_cfg:
        st.markdown("#### Configuração")

        # Providers disponíveis (com chave configurada)
        all_providers = list(AVAILABLE_PROVIDERS.keys())
        configured = []
        for p in all_providers:
            pcfg  = AVAILABLE_PROVIDERS[p]
            alias = pcfg.get("api_key_alias", p)
            if st.session_state.get(_session_key(alias)):
                configured.append(p)

        if not configured:
            st.warning("Nenhum provider com API key configurada. Configure em **⚙️ Configurações**.")
            st.stop()

        sel_providers = st.multiselect(
            "Providers a testar",
            configured,
            default=configured[:2] if len(configured) >= 2 else configured,
            key="bm_providers",
        )

        sel_agents = st.multiselect(
            "Tipos de agente",
            list(BENCHMARK_TASKS.keys()),
            default=["bpmn", "minutes"],
            format_func=lambda k: BENCHMARK_TASKS[k]["label"],
            key="bm_agents",
        )

        n_runs = st.slider("Repetições por combinação", 1, 5, 2, key="bm_runs",
                           help="Mais repetições = estatísticas mais precisas")

        transcript_choice = st.radio(
            "Transcrição sintética",
            list(TRANSCRIPTS.keys()),
            key="bm_transcript",
        )

        save_to_db = st.checkbox(
            "Gravar resultados na telemetria histórica",
            value=True, key="bm_save",
            help="Grava com flag benchmark_run=True — separado dos dados reais do pipeline",
        )

        st.markdown("---")
        run_btn = st.button(
            "▶ Executar Benchmark",
            disabled=(not sel_providers or not sel_agents),
            type="primary",
            use_container_width=True,
        )

    with col_res:
        st.markdown("#### Resultados")

        if not run_btn:
            st.info("Configure os parâmetros à esquerda e clique em **▶ Executar Benchmark**.")

        else:
            transcript_text = TRANSCRIPTS[transcript_choice]
            total_calls     = len(sel_providers) * len(sel_agents) * n_runs
            progress_bar    = st.progress(0.0, text="Iniciando…")
            results: list[dict] = []
            call_idx = 0

            for provider_name in sel_providers:
                pcfg  = AVAILABLE_PROVIDERS[provider_name]
                alias = pcfg.get("api_key_alias", provider_name)
                ci    = st.session_state.get(_session_key(alias), "")
                if not ci:
                    continue

                for agent_key in sel_agents:
                    task       = BENCHMARK_TASKS[agent_key]
                    run_lats   = []
                    run_toks_s = []

                    for run_i in range(n_runs):
                        call_idx += 1
                        pct  = call_idx / total_calls
                        desc = (f"{provider_name} · {task['label']} · run {run_i+1}/{n_runs}")
                        progress_bar.progress(pct, text=desc)

                        system = task["system"]
                        user   = task["user"].format(transcript=transcript_text)

                        latency_ms, inp, out, err = run_benchmark_call(
                            provider_name, pcfg, ci, system, user
                        )

                        tok_s = round((out / (latency_ms / 1000)), 1) if latency_ms > 0 and out > 0 else 0.0

                        if save_to_db:
                            _telemetry.record(TelemetryRecord(
                                agent_name=agent_key,
                                provider=pcfg.get("api_key_label", provider_name),
                                model=pcfg.get("default_model", ""),
                                latency_ms=latency_ms,
                                input_tokens=inp,
                                output_tokens=out,
                                total_tokens=inp + out,
                                from_cache=False,
                                long_context=False,
                                is_error=bool(err),
                                benchmark_run=True,
                                skill_version=_skill_version(agent_key),
                            ))

                        if not err:
                            run_lats.append(latency_ms)
                            run_toks_s.append(tok_s)

                        results.append({
                            "Provider":      provider_name,
                            "Agente":        task["label"],
                            "Run":           run_i + 1,
                            "Latência (ms)": latency_ms if not err else None,
                            "Tokens/s":      tok_s if not err else None,
                            "Entrada (tok)": inp,
                            "Saída (tok)":   out,
                            "Status":        "❌ Erro" if err else "✅ OK",
                            "Erro":          err or "",
                            "_prov":         provider_name,
                            "_agent":        agent_key,
                        })

            progress_bar.progress(1.0, text="Concluído!")

            if not results:
                st.error("Nenhum resultado obtido. Verifique as API keys.")
            else:
                df = pd.DataFrame(results)

                # ── Summary table ──────────────────────────────────────────
                st.markdown("##### Resultados por run")
                display_cols = ["Provider", "Agente", "Run",
                                "Latência (ms)", "Tokens/s",
                                "Entrada (tok)", "Saída (tok)", "Status"]
                st.dataframe(
                    df[display_cols].style.map(
                        lambda v: "color:#4ade80" if v == "✅ OK" else "color:#f87171",
                        subset=["Status"]
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

                # ── Aggregated bar chart ───────────────────────────────────
                df_ok = df[df["Latência (ms)"].notna()].copy()
                if not df_ok.empty:
                    agg = (
                        df_ok.groupby(["Provider", "Agente"])
                        .agg(
                            med_lat=("Latência (ms)", "median"),
                            med_tps=("Tokens/s",      "median"),
                        )
                        .reset_index()
                    )

                    fig = go.Figure()
                    for i, prov in enumerate(sel_providers):
                        sub = agg[agg["Provider"] == prov]
                        fig.add_trace(go.Bar(
                            name=prov,
                            x=sub["Agente"],
                            y=sub["med_lat"],
                            marker_color=_PALETTE[i % len(_PALETTE)],
                            text=sub["med_lat"].apply(lambda v: f"{v:.0f} ms"),
                            textposition="outside",
                        ))
                    fig.update_layout(
                        title="Latência mediana por agente × provider (ms)",
                        barmode="group",
                        height=360,
                        plot_bgcolor="#0d1b2a",
                        paper_bgcolor="#0d1b2a",
                        font_color="#f0f4f8",
                        yaxis_title="Latência (ms)",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # Throughput chart
                    fig2 = go.Figure()
                    for i, prov in enumerate(sel_providers):
                        sub = agg[agg["Provider"] == prov]
                        fig2.add_trace(go.Bar(
                            name=prov,
                            x=sub["Agente"],
                            y=sub["med_tps"],
                            marker_color=_PALETTE[i % len(_PALETTE)],
                            text=sub["med_tps"].apply(lambda v: f"{v:.0f} tok/s"),
                            textposition="outside",
                        ))
                    fig2.update_layout(
                        title="Throughput mediano por agente × provider (tokens de saída/s)",
                        barmode="group",
                        height=320,
                        plot_bgcolor="#0d1b2a",
                        paper_bgcolor="#0d1b2a",
                        font_color="#f0f4f8",
                        yaxis_title="Tokens/s",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02),
                    )
                    st.plotly_chart(fig2, use_container_width=True)

                if save_to_db:
                    st.success("Resultados gravados na telemetria histórica (tab **📊 Telemetria Real**).")


# ╔══════════════════════════════════════════════════════════════════════════╗
# ║  TAB 2 — TELEMETRIA REAL                                                ║
# ╚══════════════════════════════════════════════════════════════════════════╝
with tab_tele:
    if not supabase_configured():
        st.info("Supabase não configurado — telemetria indisponível.")
        st.stop()

    st.markdown(
        "Dados coletados automaticamente pelo pipeline a cada chamada LLM. "
        "Cada reunião processada adiciona um registro por agente."
    )
    st.markdown("---")

    # ── Filters ───────────────────────────────────────────────────────────
    fc1, fc2, fc3, fc4, fc5 = st.columns([2, 2, 1, 1, 1])
    with fc1:
        f_provider = st.selectbox(
            "Provider",
            ["Todos"] + sorted({p.get("api_key_label", k) for k, p in AVAILABLE_PROVIDERS.items()}),
            key="tele_prov",
        )
    with fc2:
        f_agent = st.selectbox(
            "Agente",
            ["Todos"] + sorted(BENCHMARK_TASKS.keys()),
            format_func=lambda k: k if k == "Todos" else BENCHMARK_TASKS.get(k, {}).get("label", k),
            key="tele_agent",
        )
    with fc3:
        f_days = st.selectbox("Período", [7, 14, 30, 60, 90], index=2, key="tele_days")
    with fc4:
        f_cache = st.checkbox("Incluir cache hits", value=False, key="tele_cache",
                              help="Cache hits têm latência muito baixa (< 50 ms) e distorcem as médias")
    with fc5:
        f_bench = st.checkbox("Incluir benchmarks", value=True, key="tele_bench")

    @st.cache_data(ttl=60, show_spinner=False)
    def _load_telemetry(provider, agent, days, include_cache, include_benchmark):
        return _telemetry.query(
            provider=None if provider == "Todos" else provider,
            agent_name=None if agent == "Todos" else agent,
            days=days,
            include_cache=include_cache,
            include_benchmark=include_benchmark,
        )

    records = _load_telemetry(f_provider, f_agent, f_days, f_cache, f_bench)

    if not records:
        st.info(
            "Nenhum dado de telemetria para os filtros selecionados. "
            "Execute o pipeline em algumas reuniões ou use o **Benchmark On-Demand** para gerar dados."
        )
        st.stop()

    df_all = pd.DataFrame(records)
    df_all["tokens_per_sec"] = df_all.apply(
        lambda r: round(r["output_tokens"] / (r["latency_ms"] / 1000), 1)
        if r["latency_ms"] > 0 and r["output_tokens"] > 0 else 0.0,
        axis=1,
    )

    # ── Filtro skill_version (post-load, populado da df_all) ──────────────
    _sv_col = "skill_version"
    _versions_in_data = sorted(df_all[_sv_col].dropna().unique().tolist())
    if _versions_in_data:
        _ver_opts = ["Todas"] + _versions_in_data
        f_skill_ver = st.selectbox(
            "Versão do skill",
            _ver_opts,
            key="tele_skill_ver",
            help="Filtra registros pela versão do arquivo de skill que gerou a chamada (PC83)",
        )
        if f_skill_ver != "Todas":
            df_all = df_all[df_all[_sv_col] == f_skill_ver]

    # ── KPIs ──────────────────────────────────────────────────────────────
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("Registros",        f"{len(df_all):,}")
    k2.metric("Latência mediana", f"{int(df_all['latency_ms'].median()):,} ms")
    k3.metric("p95 latência",     f"{int(df_all['latency_ms'].quantile(.95)):,} ms")
    k4.metric("Throughput mediano", f"{df_all['tokens_per_sec'].median():.0f} tok/s")
    k5.metric("Providers únicos", df_all["provider"].nunique())
    k6.metric("Versões de skill", df_all[_sv_col].nunique())

    st.markdown("---")

    sub_lat, sub_thr, sub_hist, sub_heat, sub_ver = st.tabs([
        "📊 Latência", "⚡ Throughput", "📈 Histórico", "🔥 Heatmap", "📋 Versões",
    ])

    providers_present = sorted(df_all["provider"].unique())
    prov_colors = {p: _PALETTE[i % len(_PALETTE)] for i, p in enumerate(providers_present)}

    # ── Sub-tab: Latência (box plot) ───────────────────────────────────────
    with sub_lat:
        st.markdown("Distribuição de latência por agente e provider (exclui outliers > p99).")
        agents_present = sorted(df_all["agent_name"].unique())
        fig = go.Figure()
        for prov in providers_present:
            sub = df_all[df_all["provider"] == prov]
            p99 = sub["latency_ms"].quantile(.99)
            sub = sub[sub["latency_ms"] <= p99]
            fig.add_trace(go.Box(
                y=sub["latency_ms"],
                x=sub["agent_name"],
                name=prov,
                marker_color=prov_colors[prov],
                boxmean="sd",
            ))
        fig.update_layout(
            title="Distribuição de latência por agente (ms) — box plot p5/p25/median/p75/p95",
            boxmode="group",
            height=420,
            plot_bgcolor="#0d1b2a",
            paper_bgcolor="#0d1b2a",
            font_color="#f0f4f8",
            yaxis_title="Latência (ms)",
            xaxis_title="Agente",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Summary table
        agg_lat = (
            df_all.groupby(["provider", "agent_name"])["latency_ms"]
            .agg(n="count", p50="median",
                 p95=lambda x: x.quantile(.95),
                 p99=lambda x: x.quantile(.99),
                 mean="mean")
            .reset_index()
            .rename(columns={"provider": "Provider", "agent_name": "Agente",
                              "n": "N", "p50": "p50 (ms)", "p95": "p95 (ms)",
                              "p99": "p99 (ms)", "mean": "Média (ms)"})
        )
        for col in ["p50 (ms)", "p95 (ms)", "p99 (ms)", "Média (ms)"]:
            agg_lat[col] = agg_lat[col].apply(lambda v: f"{v:.0f}")
        st.dataframe(agg_lat, use_container_width=True, hide_index=True)

    # ── Sub-tab: Throughput ────────────────────────────────────────────────
    with sub_thr:
        st.markdown("Throughput mediano de tokens de saída por segundo por provider.")
        agg_thr = (
            df_all[df_all["tokens_per_sec"] > 0]
            .groupby(["provider", "agent_name"])["tokens_per_sec"]
            .median()
            .reset_index()
            .rename(columns={"provider": "Provider", "agent_name": "Agente",
                              "tokens_per_sec": "Throughput mediano (tok/s)"})
        )
        fig2 = go.Figure()
        for prov in providers_present:
            sub = agg_thr[agg_thr["Provider"] == prov]
            fig2.add_trace(go.Bar(
                name=prov,
                x=sub["Agente"],
                y=sub["Throughput mediano (tok/s)"],
                marker_color=prov_colors[prov],
                text=sub["Throughput mediano (tok/s)"].apply(lambda v: f"{v:.0f}"),
                textposition="outside",
            ))
        fig2.update_layout(
            title="Throughput mediano por agente (tokens de saída / segundo)",
            barmode="group",
            height=380,
            plot_bgcolor="#0d1b2a",
            paper_bgcolor="#0d1b2a",
            font_color="#f0f4f8",
            yaxis_title="tok/s",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig2, use_container_width=True)
        st.dataframe(agg_thr, use_container_width=True, hide_index=True)

    # ── Sub-tab: Histórico (time series) ──────────────────────────────────
    with sub_hist:
        st.markdown("Evolução da latência ao longo do tempo (mediana por dia por provider).")
        df_ts = df_all.copy()
        df_ts["date"] = pd.to_datetime(df_ts["created_at"]).dt.date
        agg_ts = (
            df_ts.groupby(["date", "provider"])["latency_ms"]
            .median()
            .reset_index()
            .rename(columns={"latency_ms": "Latência mediana (ms)"})
        )
        fig3 = go.Figure()
        for prov in providers_present:
            sub = agg_ts[agg_ts["provider"] == prov].sort_values("date")
            fig3.add_trace(go.Scatter(
                x=sub["date"],
                y=sub["Latência mediana (ms)"],
                name=prov,
                mode="lines+markers",
                line=dict(color=prov_colors[prov], width=2),
                marker=dict(size=6),
            ))
        fig3.update_layout(
            title="Evolução da latência mediana por dia (ms)",
            height=380,
            plot_bgcolor="#0d1b2a",
            paper_bgcolor="#0d1b2a",
            font_color="#f0f4f8",
            yaxis_title="Latência mediana (ms)",
            xaxis_title="Data",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig3, use_container_width=True)

    # ── Sub-tab: Heatmap ───────────────────────────────────────────────────
    with sub_heat:
        st.markdown("Latência mediana (ms) — agente × provider. Mais escuro = mais lento.")
        pivot = (
            df_all.groupby(["agent_name", "provider"])["latency_ms"]
            .median()
            .unstack(fill_value=0)
        )
        fig4 = go.Figure(go.Heatmap(
            z=pivot.values,
            x=list(pivot.columns),
            y=list(pivot.index),
            colorscale="Blues",
            text=[[f"{v:.0f} ms" for v in row] for row in pivot.values],
            texttemplate="%{text}",
            colorbar=dict(title="ms"),
        ))
        fig4.update_layout(
            title="Heatmap: latência mediana (ms) por agente × provider",
            height=max(300, len(pivot.index) * 60 + 100),
            plot_bgcolor="#0d1b2a",
            paper_bgcolor="#0d1b2a",
            font_color="#f0f4f8",
            xaxis_title="Provider",
            yaxis_title="Agente",
        )
        st.plotly_chart(fig4, use_container_width=True)

    # ── Sub-tab: Versões de Skill ──────────────────────────────────────────
    with sub_ver:
        df_ver = df_all[df_all[_sv_col].notna()].copy()
        if df_ver.empty:
            st.info(
                "Nenhum registro com skill_version nos dados filtrados. "
                "Versões são registradas a partir do PC83 — processe novas reuniões para populá-las."
            )
        else:
            st.markdown(
                "Latência e throughput agrupados por versão do arquivo de skill. "
                "Permite comparar o impacto de mudanças no prompt entre versões."
            )

            # ── Tabela de resumo ──────────────────────────────────────────
            agg_ver = (
                df_ver.groupby([_sv_col, "agent_name"])
                .agg(
                    N=("latency_ms", "count"),
                    p50=("latency_ms", "median"),
                    p95=("latency_ms", lambda x: x.quantile(.95)),
                    throughput=("tokens_per_sec", "median"),
                )
                .reset_index()
                .rename(columns={
                    _sv_col:      "Versão do Skill",
                    "agent_name": "Agente",
                    "p50":        "p50 (ms)",
                    "p95":        "p95 (ms)",
                    "throughput": "Throughput (tok/s)",
                })
            )
            for col in ["p50 (ms)", "p95 (ms)"]:
                agg_ver[col] = agg_ver[col].apply(lambda v: f"{v:.0f}")
            agg_ver["Throughput (tok/s)"] = agg_ver["Throughput (tok/s)"].apply(
                lambda v: f"{v:.1f}"
            )
            st.dataframe(agg_ver, use_container_width=True, hide_index=True)

            # ── Bar chart: latência mediana por versão × agente ───────────
            _ver_list = sorted(df_ver[_sv_col].unique())
            _ver_colors = {v: _PALETTE[i % len(_PALETTE)] for i, v in enumerate(_ver_list)}
            _agg_chart = (
                df_ver.groupby([_sv_col, "agent_name"])["latency_ms"]
                .median()
                .reset_index()
            )
            fig_ver = go.Figure()
            for ver in _ver_list:
                sub = _agg_chart[_agg_chart[_sv_col] == ver]
                fig_ver.add_trace(go.Bar(
                    name=ver,
                    x=sub["agent_name"],
                    y=sub["latency_ms"],
                    marker_color=_ver_colors[ver],
                    text=sub["latency_ms"].apply(lambda v: f"{v:.0f} ms"),
                    textposition="outside",
                ))
            fig_ver.update_layout(
                title="Latência mediana por versão de skill × agente (ms)",
                barmode="group",
                height=400,
                plot_bgcolor="#0d1b2a",
                paper_bgcolor="#0d1b2a",
                font_color="#f0f4f8",
                yaxis_title="Latência mediana (ms)",
                xaxis_title="Agente",
                legend=dict(
                    title="Versão do Skill",
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                ),
            )
            st.plotly_chart(fig_ver, use_container_width=True)

            # ── Evolução temporal por versão ──────────────────────────────
            if "created_at" in df_ver.columns:
                df_ver_ts = df_ver.copy()
                df_ver_ts["date"] = pd.to_datetime(df_ver_ts["created_at"]).dt.date
                agg_vts = (
                    df_ver_ts.groupby(["date", _sv_col])["latency_ms"]
                    .median()
                    .reset_index()
                )
                fig_vts = go.Figure()
                for ver in _ver_list:
                    sub = agg_vts[agg_vts[_sv_col] == ver].sort_values("date")
                    if sub.empty:
                        continue
                    fig_vts.add_trace(go.Scatter(
                        x=sub["date"],
                        y=sub["latency_ms"],
                        name=ver,
                        mode="lines+markers",
                        line=dict(color=_ver_colors[ver], width=2),
                        marker=dict(size=6),
                    ))
                fig_vts.update_layout(
                    title="Evolução da latência mediana por versão de skill (ms/dia)",
                    height=340,
                    plot_bgcolor="#0d1b2a",
                    paper_bgcolor="#0d1b2a",
                    font_color="#f0f4f8",
                    yaxis_title="Latência mediana (ms)",
                    xaxis_title="Data",
                    legend=dict(
                        title="Versão",
                        orientation="h",
                        yanchor="bottom",
                        y=1.02,
                    ),
                )
                st.plotly_chart(fig_vts, use_container_width=True)

    st.markdown("---")
    st.caption(
        f"Últimos {f_days} dias · {len(df_all):,} registros · "
        "Cache hits excluídos por padrão (distorcem a distribuição) · "
        "Atualizado a cada 60 s"
    )
