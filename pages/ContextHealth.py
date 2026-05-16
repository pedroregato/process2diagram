# pages/ContextHealth.py
# ─────────────────────────────────────────────────────────────────────────────
# Saúde do Contexto — Dashboard integrado de qualidade e conhecimento
#
# Combina indicadores ROI-TR, fulfillment, TRC, riqueza de artefatos,
# contradições e saúde do conhecimento em uma visão unificada do contexto.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from ui.auth_gate import apply_auth_gate
from ui.project_selector import require_active_project
from modules.supabase_client import get_supabase_client, supabase_configured

apply_auth_gate()

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

_NAVY  = "#0d2a4a"
_AMBER = "#f59e0b"
_BLUE  = "#3b82f6"
_GREEN = "#22c55e"
_RED   = "#ef4444"
_ORANGE= "#f97316"

_PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e0e7f0", family="Segoe UI, system-ui"),
    margin=dict(l=20, r=20, t=40, b=20),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
)


def _roi_color(v: float) -> str:
    if v >= 7.5: return _GREEN
    if v >= 4.5: return "#eab308"
    if v >= 2.0: return _ORANGE
    return _RED


def _health_color(v: float) -> str:
    if v >= 7.5: return _GREEN
    if v >= 5.5: return "#eab308"
    if v >= 3.5: return _ORANGE
    return _RED


def _trc_color(v: float) -> str:
    if v > 40: return _RED
    if v > 20: return _ORANGE
    return _GREEN


# ─────────────────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def _load_roi(project_id: str) -> list:
    from modules.meeting_roi_calculator import compute_project_roi
    return compute_project_roi(project_id, cost_per_hour=150.0)


@st.cache_data(ttl=60, show_spinner=False)
def _load_requirements(project_id: str) -> list[dict]:
    db = get_supabase_client()
    if not db:
        return []
    try:
        return (db.table("requirements")
                  .select("req_type, priority, status, meeting_id")
                  .eq("project_id", project_id)
                  .execute().data or [])
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def _load_context_info(project_id: str) -> dict:
    db = get_supabase_client()
    if not db:
        return {}
    try:
        row = (db.table("contexts")
                 .select("name, context_type, skill_md, description")
                 .eq("id", project_id)
                 .single().execute().data or {})
        return row
    except Exception:
        return {}


@st.cache_data(ttl=60, show_spinner=False)
def _load_context_files_count(project_id: str) -> int:
    db = get_supabase_client()
    if not db:
        return 0
    try:
        rows = (db.table("context_files")
                  .select("id")
                  .eq("context_id", project_id)
                  .execute().data or [])
        return len(rows)
    except Exception:
        return 0


@st.cache_data(ttl=60, show_spinner=False)
def _load_sbvr_counts(project_id: str) -> dict:
    db = get_supabase_client()
    if not db:
        return {"terms": 0, "rules": 0}
    try:
        t = len(db.table("sbvr_terms").select("id").eq("project_id", project_id).execute().data or [])
        r = len(db.table("sbvr_rules").select("id").eq("project_id", project_id).execute().data or [])
        return {"terms": t, "rules": r}
    except Exception:
        return {"terms": 0, "rules": 0}


@st.cache_data(ttl=60, show_spinner=False)
def _load_contradictions(project_id: str) -> list[dict]:
    from core.project_store import list_contradictions
    return list_contradictions(project_id)


# ─────────────────────────────────────────────────────────────────────────────
# Health score
# ─────────────────────────────────────────────────────────────────────────────

def _compute_health(roi_data, ctx_info: dict, n_files: int, sbvr: dict,
                    reqs: list[dict], contradictions: list[dict]) -> dict:
    if not roi_data:
        return {"score": 0.0, "dimensions": {}}

    avg_roi         = sum(m.roi_tr         for m in roi_data) / len(roi_data)
    avg_fulfillment = sum(m.fulfillment_score for m in roi_data) / len(roi_data)
    avg_trc         = sum(m.trc            for m in roi_data) / len(roi_data)
    total_actions   = sum(m.n_actions_total   for m in roi_data)
    done_actions    = sum(m.n_actions_complete for m in roi_data)
    action_rate     = done_actions / total_actions if total_actions > 0 else 0.5

    ckf_filled      = bool((ctx_info.get("skill_md") or "").strip())
    knowledge_score = (
        (0.4 if ckf_filled else 0.0)
        + (0.35 if n_files > 0 else 0.0)
        + (0.25 if (sbvr["terms"] + sbvr["rules"]) > 0 else 0.0)
    )

    trc_score        = max(0.0, 1.0 - avg_trc / 100.0)
    contradiction_penalty = min(0.3, len(contradictions) * 0.05)

    dimensions = {
        "ROI-TR Médio":        (avg_roi / 10.0,     0.35),
        "Fulfillment":         (avg_fulfillment,     0.25),
        "Ações Concluídas":    (action_rate,         0.15),
        "Base de Conhecimento":(knowledge_score,     0.15),
        "Baixo Retrabalho":    (trc_score,           0.10),
    }

    raw_score = sum(v * w for v, w in dimensions.values())
    score     = max(0.0, min(10.0, raw_score * 10.0 - contradiction_penalty * 10.0))

    return {
        "score":       score,
        "dimensions":  {k: v for k, (v, _) in dimensions.items()},
        "weights":     {k: w for k, (_, w) in dimensions.items()},
        "avg_roi":     avg_roi,
        "avg_fulfill": avg_fulfillment,
        "avg_trc":     avg_trc,
        "action_rate": action_rate,
        "ckf_filled":  ckf_filled,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Auto-insights
# ─────────────────────────────────────────────────────────────────────────────

def _generate_insights(roi_data, health: dict, reqs: list[dict],
                       contradictions: list[dict], sbvr: dict, n_files: int) -> list[dict]:
    insights = []

    if not roi_data:
        return [{"icon": "ℹ️", "color": "#94a3b8", "text":
                 "Nenhuma reunião encontrada. Execute o pipeline para gerar indicadores."}]

    score    = health["score"]
    avg_roi  = health["avg_roi"]
    avg_trc  = health["avg_trc"]
    avg_fill = health["avg_fulfill"]

    # Overall health
    if score >= 7.5:
        insights.append({"icon": "🟢", "color": _GREEN,
            "text": f"Contexto saudável — score geral de {score:.1f}/10. A qualidade das reuniões e a base de conhecimento estão bem consolidadas."})
    elif score >= 5.0:
        insights.append({"icon": "🟡", "color": "#eab308",
            "text": f"Contexto em desenvolvimento — score {score:.1f}/10. Há oportunidades de melhoria na consistência das reuniões e no conhecimento documentado."})
    else:
        insights.append({"icon": "🔴", "color": _RED,
            "text": f"Contexto requer atenção — score {score:.1f}/10. Revise a qualidade das reuniões e fortaleça a base de conhecimento do contexto."})

    # ROI-TR
    if avg_roi < 3.0:
        insights.append({"icon": "📉", "color": _ORANGE,
            "text": f"ROI-TR médio baixo ({avg_roi:.1f}). As reuniões estão gerando poucos artefatos concretos em relação ao custo de tempo investido."})
    elif avg_roi >= 7.0:
        insights.append({"icon": "📈", "color": _GREEN,
            "text": f"ROI-TR médio excelente ({avg_roi:.1f}/10). As reuniões estão produzindo artefatos ricos e bem documentados."})

    # TRC
    if avg_trc > 35:
        insights.append({"icon": "🔁", "color": _RED,
            "text": f"Taxa de retrabalho conceitual alta ({avg_trc:.0f}%). Há indícios de que os mesmos temas estão sendo rediscutidos sem resolução. Considere pautas mais objetivas."})
    elif avg_trc < 15:
        insights.append({"icon": "✅", "color": _GREEN,
            "text": f"Baixo retrabalho conceitual ({avg_trc:.0f}%). As reuniões avançam de forma objetiva, sem repetição excessiva de pontos."})

    # Fulfillment
    if avg_fill < 0.4:
        insights.append({"icon": "📋", "color": _ORANGE,
            "text": f"Fulfillment médio baixo ({avg_fill*100:.0f}%). As reuniões não estão entregando o esperado para seu tipo. Revise a pauta e os objetivos de cada encontro."})

    # Contradictions
    if contradictions:
        insights.append({"icon": "⚡", "color": _RED,
            "text": f"{len(contradictions)} contradição(ões) detectada(s) em requisitos. Revise as versões conflitantes no Req. Tracker antes de prosseguir."})

    # Knowledge
    if not health["ckf_filled"]:
        insights.append({"icon": "📖", "color": "#94a3b8",
            "text": "O CKF deste contexto está vazio. Preencher o Context Knowledge File melhora significativamente a qualidade dos agentes LLM."})

    if n_files == 0:
        insights.append({"icon": "📎", "color": "#94a3b8",
            "text": "Nenhum arquivo de referência carregado. Adicione manuais, políticas ou apresentações em Configurações → Arquivos de Referência."})
    elif n_files >= 3:
        insights.append({"icon": "📚", "color": _GREEN,
            "text": f"{n_files} arquivo(s) de referência disponíveis. A base de conhecimento do contexto está bem documentada."})

    # Best / worst
    if len(roi_data) >= 3:
        best  = max(roi_data, key=lambda m: m.roi_tr)
        worst = min(roi_data, key=lambda m: m.roi_tr)
        if best.roi_tr - worst.roi_tr > 4:
            insights.append({"icon": "📊", "color": "#94a3b8",
                "text": f"Grande variância de qualidade: Reunião {best.meeting_number} (ROI {best.roi_tr:.1f}) vs Reunião {worst.meeting_number} (ROI {worst.roi_tr:.1f}). Investigue o que diferencia as melhores reuniões."})

    return insights[:7]  # cap at 7


# ─────────────────────────────────────────────────────────────────────────────
# Chart builders
# ─────────────────────────────────────────────────────────────────────────────

def _chart_roi_evolution(roi_data) -> go.Figure:
    labels = [f"R{m.meeting_number}" for m in roi_data]
    roi_vals = [m.roi_tr for m in roi_data]
    fill_vals = [m.fulfillment_score * 10 for m in roi_data]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=labels, y=roi_vals, name="ROI-TR",
        mode="lines+markers",
        line=dict(color=_AMBER, width=2.5),
        marker=dict(size=8, color=[_roi_color(v) for v in roi_vals],
                    line=dict(color="#fff", width=1.5)),
        hovertemplate="<b>%{x}</b><br>ROI-TR: %{y:.1f}<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=labels, y=fill_vals, name="Fulfillment ×10",
        mode="lines+markers",
        line=dict(color=_BLUE, width=2, dash="dot"),
        marker=dict(size=6, color=_BLUE),
        hovertemplate="<b>%{x}</b><br>Fulfillment: %{customdata:.0f}%<extra></extra>",
        customdata=[m.fulfillment_score * 100 for m in roi_data],
    ))
    fig.add_hline(y=7.5, line=dict(color=_GREEN, width=1, dash="dash"), annotation_text="Meta", annotation_font_color=_GREEN)
    fig.add_hline(y=4.5, line=dict(color=_ORANGE, width=1, dash="dash"))

    fig.update_layout(**_PLOTLY_LAYOUT,
        title=dict(text="Evolução ROI-TR e Fulfillment", font=dict(size=14, color=_AMBER)),
        yaxis=dict(range=[0, 10.5], tickfont=dict(color="#94a3b8"), gridcolor="#1e3a5f"),
        xaxis=dict(tickfont=dict(color="#94a3b8"), gridcolor="#1e3a5f"),
        height=300,
    )
    return fig


def _chart_trc(roi_data) -> go.Figure:
    labels   = [f"R{m.meeting_number}" for m in roi_data]
    trc_vals = [m.trc for m in roi_data]
    colors   = [_trc_color(v) for v in trc_vals]

    fig = go.Figure(go.Bar(
        x=labels, y=trc_vals, name="TRC (%)",
        marker=dict(color=colors, line=dict(color="#0a1929", width=1)),
        hovertemplate="<b>%{x}</b><br>TRC: %{y:.1f}%<extra></extra>",
    ))
    fig.add_hline(y=40, line=dict(color=_RED, width=1.5, dash="dash"), annotation_text="Alto", annotation_font_color=_RED)
    fig.add_hline(y=20, line=dict(color=_ORANGE, width=1, dash="dot"))

    fig.update_layout(**_PLOTLY_LAYOUT,
        title=dict(text="TRC — Taxa de Retrabalho Conceitual (%)", font=dict(size=14, color=_AMBER)),
        yaxis=dict(range=[0, max(max(trc_vals, default=0) * 1.2, 50)],
                   ticksuffix="%", tickfont=dict(color="#94a3b8"), gridcolor="#1e3a5f"),
        xaxis=dict(tickfont=dict(color="#94a3b8")),
        height=280,
    )
    return fig


def _chart_artefacts(roi_data) -> go.Figure:
    labels = [f"R{m.meeting_number}" for m in roi_data]

    fig = go.Figure()
    specs = [
        ("Requisitos", [m.n_requirements  for m in roi_data], "#3b82f6"),
        ("Decisões",   [m.n_decisions      for m in roi_data], _AMBER),
        ("Ações",      [m.n_actions_total  for m in roi_data], "#a78bfa"),
        ("SBVR",       [m.n_sbvr           for m in roi_data], "#34d399"),
    ]
    for name, vals, color in specs:
        fig.add_trace(go.Bar(
            name=name, x=labels, y=vals,
            marker_color=color,
            hovertemplate=f"<b>%{{x}}</b><br>{name}: %{{y}}<extra></extra>",
        ))

    fig.update_layout(**_PLOTLY_LAYOUT,
        barmode="group",
        title=dict(text="Artefatos por Reunião", font=dict(size=14, color=_AMBER)),
        yaxis=dict(tickfont=dict(color="#94a3b8"), gridcolor="#1e3a5f"),
        xaxis=dict(tickfont=dict(color="#94a3b8")),
        height=300,
    )
    return fig


def _chart_cumulative(roi_data) -> go.Figure:
    labels = [f"R{m.meeting_number}" for m in roi_data]
    cum_req  = []
    cum_dec  = []
    cum_sbvr = []
    r = d = s = 0
    for m in roi_data:
        r += m.n_requirements
        d += m.n_decisions
        s += m.n_sbvr
        cum_req.append(r)
        cum_dec.append(d)
        cum_sbvr.append(s)

    fig = go.Figure()
    for name, vals, color in [
        ("Requisitos", cum_req,  "#3b82f6"),
        ("Decisões",   cum_dec,  _AMBER),
        ("SBVR",       cum_sbvr, "#34d399"),
    ]:
        fig.add_trace(go.Scatter(
            x=labels, y=vals, name=name, mode="lines",
            stackgroup="one", line=dict(color=color, width=1.5),
            hovertemplate=f"<b>%{{x}}</b><br>{name} acum.: %{{y}}<extra></extra>",
        ))

    fig.update_layout(**_PLOTLY_LAYOUT,
        title=dict(text="Acúmulo de Artefatos ao Longo do Projeto", font=dict(size=14, color=_AMBER)),
        yaxis=dict(tickfont=dict(color="#94a3b8"), gridcolor="#1e3a5f"),
        xaxis=dict(tickfont=dict(color="#94a3b8")),
        height=260,
    )
    return fig


def _chart_meeting_types(roi_data) -> go.Figure:
    from collections import Counter
    counts = Counter(m.meeting_type for m in roi_data)
    labels = list(counts.keys())
    values = list(counts.values())

    palette = [_AMBER, _BLUE, "#a78bfa", "#34d399", _ORANGE, "#f472b6",
               "#60a5fa", "#fb923c", "#4ade80", "#818cf8", "#94a3b8"]

    fig = go.Figure(go.Pie(
        labels=labels, values=values,
        hole=0.55,
        marker=dict(colors=palette[:len(labels)],
                    line=dict(color="#0a1929", width=2)),
        textinfo="percent",
        hovertemplate="<b>%{label}</b><br>%{value} reunião(ões) (%{percent})<extra></extra>",
        textfont=dict(size=11),
    ))
    fig.update_layout(**_PLOTLY_LAYOUT,
        title=dict(text="Tipos de Reunião", font=dict(size=14, color=_AMBER)),
        height=300,
        showlegend=True,
        legend=dict(orientation="v", x=1.02, y=0.5, font=dict(size=10)),
    )
    return fig


def _chart_actions_donut(roi_data) -> go.Figure:
    total = sum(m.n_actions_total    for m in roi_data)
    done  = sum(m.n_actions_complete for m in roi_data)
    pend  = max(0, total - done)

    fig = go.Figure(go.Pie(
        labels=["Concluídas", "Pendentes"],
        values=[done, pend],
        hole=0.60,
        marker=dict(colors=[_GREEN, "#334155"],
                    line=dict(color="#0a1929", width=2)),
        hovertemplate="<b>%{label}</b>: %{value}<extra></extra>",
        textinfo="percent+value",
        textfont=dict(size=11),
    ))
    pct = (done / total * 100) if total > 0 else 0
    fig.add_annotation(text=f"{pct:.0f}%", x=0.5, y=0.5, showarrow=False,
                       font=dict(size=22, color="#fff", family="Segoe UI"))
    fig.update_layout(**_PLOTLY_LAYOUT,
        title=dict(text=f"Ações — {done}/{total} concluídas", font=dict(size=14, color=_AMBER)),
        height=280, showlegend=True,
    )
    return fig


def _chart_reqs_by_type(reqs: list[dict]) -> go.Figure:
    from collections import Counter
    counts = Counter(r.get("req_type", "Outro") for r in reqs)
    sorted_items = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    labels = [k for k, _ in sorted_items]
    values = [v for _, v in sorted_items]
    colors = [_BLUE, _AMBER, "#a78bfa", "#34d399", _ORANGE, "#f472b6"]

    fig = go.Figure(go.Bar(
        y=labels, x=values, orientation="h",
        marker=dict(color=colors[:len(labels)], line=dict(color="#0a1929", width=1)),
        hovertemplate="<b>%{y}</b>: %{x} requisito(s)<extra></extra>",
    ))
    fig.update_layout(**_PLOTLY_LAYOUT,
        title=dict(text="Requisitos por Tipo", font=dict(size=14, color=_AMBER)),
        xaxis=dict(tickfont=dict(color="#94a3b8"), gridcolor="#1e3a5f"),
        yaxis=dict(tickfont=dict(color="#94a3b8"), autorange="reversed"),
        height=280,
    )
    return fig


def _chart_reqs_by_priority(reqs: list[dict]) -> go.Figure:
    from collections import Counter
    counts = Counter(r.get("priority", "Média") for r in reqs)
    order  = ["Alta", "Média", "Baixa"]
    labels = [p for p in order if p in counts] + [p for p in counts if p not in order]
    values = [counts[p] for p in labels]
    colors_map = {"Alta": _RED, "Média": _AMBER, "Baixa": _GREEN}
    colors = [colors_map.get(p, _BLUE) for p in labels]

    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker=dict(color=colors, line=dict(color="#0a1929", width=1)),
        hovertemplate="<b>%{x}</b>: %{y}<extra></extra>",
    ))
    fig.update_layout(**_PLOTLY_LAYOUT,
        title=dict(text="Requisitos por Prioridade", font=dict(size=14, color=_AMBER)),
        yaxis=dict(tickfont=dict(color="#94a3b8"), gridcolor="#1e3a5f"),
        xaxis=dict(tickfont=dict(color="#94a3b8")),
        height=260,
    )
    return fig


def _chart_health_radar(health: dict) -> go.Figure:
    dims   = list(health["dimensions"].keys())
    values = [v * 10 for v in health["dimensions"].values()]
    values_closed = values + [values[0]]
    dims_closed   = dims   + [dims[0]]

    fig = go.Figure(go.Scatterpolar(
        r=values_closed, theta=dims_closed,
        fill="toself",
        fillcolor="rgba(245,158,11,0.15)",
        line=dict(color=_AMBER, width=2),
        marker=dict(size=6, color=_AMBER),
        hovertemplate="<b>%{theta}</b>: %{r:.1f}<extra></extra>",
    ))
    fig.update_layout(**_PLOTLY_LAYOUT,
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(range=[0, 10], tickfont=dict(color="#94a3b8", size=9),
                            gridcolor="#1e3a5f", linecolor="#1e3a5f"),
            angularaxis=dict(tickfont=dict(color="#e0e7f0", size=10),
                             gridcolor="#1e3a5f", linecolor="#1e3a5f"),
        ),
        title=dict(text="Dimensões de Saúde (0–10)", font=dict(size=14, color=_AMBER)),
        height=340,
    )
    return fig


def _chart_fulfillment_bar(roi_data) -> go.Figure:
    labels  = [f"R{m.meeting_number}" for m in roi_data]
    fills   = [m.fulfillment_score * 100 for m in roi_data]
    types   = [m.meeting_type for m in roi_data]
    colors  = [_GREEN if v >= 90 else (_AMBER if v >= 60 else (_ORANGE if v >= 30 else _RED)) for v in fills]

    fig = go.Figure(go.Bar(
        x=labels, y=fills,
        marker=dict(color=colors, line=dict(color="#0a1929", width=1)),
        customdata=types,
        hovertemplate="<b>%{x}</b><br>Fulfillment: %{y:.0f}%<br>Tipo: %{customdata}<extra></extra>",
    ))
    fig.add_hline(y=90, line=dict(color=_GREEN, width=1, dash="dash"), annotation_text="Pleno", annotation_font_color=_GREEN)
    fig.add_hline(y=60, line=dict(color=_AMBER, width=1, dash="dot"))

    fig.update_layout(**_PLOTLY_LAYOUT,
        title=dict(text="Fulfillment por Reunião (%)", font=dict(size=14, color=_AMBER)),
        yaxis=dict(range=[0, 110], ticksuffix="%", tickfont=dict(color="#94a3b8"), gridcolor="#1e3a5f"),
        xaxis=dict(tickfont=dict(color="#94a3b8")),
        height=260,
    )
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Header HTML
# ─────────────────────────────────────────────────────────────────────────────

def _render_header(ctx_name: str, ctx_type: str, score: float,
                   n_meetings: int, n_reqs: int, n_files: int, ckf_filled: bool):
    color    = _health_color(score)
    label    = ("Excelente" if score >= 7.5 else
                "Saudável"  if score >= 5.5 else
                "Em risco"  if score >= 3.5 else "Crítico")

    type_label = ctx_type.replace("_", " ").title() if ctx_type else "Projeto"
    ckf_badge  = ('<span style="background:#14532d;color:#86efac;padding:2px 8px;border-radius:10px;font-size:0.72rem;font-weight:700;">CKF Ativo</span>'
                  if ckf_filled else
                  '<span style="background:#3d1c02;color:#fca5a5;padding:2px 8px;border-radius:10px;font-size:0.72rem;font-weight:700;">Sem CKF</span>')

    html = f"""
<div style="background:linear-gradient(135deg,#0d2a4a 0%,#112240 100%);
            border-bottom:3px solid {color};border-radius:8px;
            padding:28px 36px 24px;display:flex;
            justify-content:space-between;align-items:center;gap:20px;margin-bottom:4px;">
  <div style="flex:1;">
    <div style="font-size:0.75rem;color:#94a3b8;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;">
      {type_label} &nbsp;·&nbsp; {n_meetings} reunião(ões) &nbsp;·&nbsp; {n_reqs} requisitos &nbsp;·&nbsp; {n_files} arquivo(s) &nbsp;&nbsp;{ckf_badge}
    </div>
    <div style="font-size:1.9rem;font-weight:800;color:#fff;line-height:1.2;">{ctx_name}</div>
    <div style="font-size:0.92rem;color:#94a3b8;margin-top:6px;">Visão consolidada de saúde, qualidade e conhecimento do contexto</div>
  </div>
  <div style="text-align:center;min-width:130px;">
    <div style="font-size:3.2rem;font-weight:900;color:{color};line-height:1;">{score:.1f}</div>
    <div style="font-size:0.7rem;color:#94a3b8;margin-top:2px;">/ 10 &nbsp;·&nbsp; SAÚDE</div>
    <div style="background:{color}22;color:{color};padding:4px 14px;border-radius:12px;
                font-size:0.8rem;font-weight:700;margin-top:8px;display:inline-block;">{label}</div>
  </div>
</div>"""
    st.components.v1.html(html, height=140)


def _render_insights(insights: list[dict]):
    items_html = ""
    for ins in insights:
        items_html += f"""
<div style="display:flex;gap:12px;padding:10px 0;border-bottom:1px solid #1a3050;">
  <div style="font-size:1.2rem;flex-shrink:0;margin-top:1px;">{ins['icon']}</div>
  <div style="color:#cbd5e1;font-size:0.88rem;line-height:1.55;">{ins['text']}</div>
</div>"""

    html = f"""
<div style="background:#0f2235;border:1px solid #1e3a5f;border-left:4px solid #f59e0b;
            border-radius:8px;padding:18px 22px;">
  <div style="font-size:0.75rem;color:#f59e0b;letter-spacing:1px;text-transform:uppercase;
              margin-bottom:12px;font-weight:700;">Insights Automáticos</div>
  {items_html}
</div>"""
    st.components.v1.html(html, height=min(80 + len(insights) * 62, 520))


# ─────────────────────────────────────────────────────────────────────────────
# Page
# ─────────────────────────────────────────────────────────────────────────────

if not supabase_configured():
    st.error("⚙️ Supabase não configurado.")
    st.stop()

project_id, project_name = require_active_project()

# ── Load data ─────────────────────────────────────────────────────────────────
with st.spinner("Carregando dados do contexto..."):
    roi_data        = _load_roi(project_id)
    reqs            = _load_requirements(project_id)
    ctx_info        = _load_context_info(project_id)
    n_files         = _load_context_files_count(project_id)
    sbvr            = _load_sbvr_counts(project_id)
    contradictions  = _load_contradictions(project_id)

health   = _compute_health(roi_data, ctx_info, n_files, sbvr, reqs, contradictions)
insights = _generate_insights(roi_data, health, reqs, contradictions, sbvr, n_files)
score    = health["score"]
ctx_type = ctx_info.get("context_type") or "project"
n_reqs   = len(reqs)
n_meetings = len(roi_data)

# ── Header ────────────────────────────────────────────────────────────────────
_render_header(
    project_name, ctx_type, score,
    n_meetings, n_reqs, n_files,
    health.get("ckf_filled", False),
)

# ── KPI strip ─────────────────────────────────────────────────────────────────
if roi_data:
    avg_roi   = health["avg_roi"]
    avg_trc   = health["avg_trc"]
    avg_fill  = health["avg_fulfill"]
    act_rate  = health["action_rate"]
    n_dec     = sum(m.n_decisions     for m in roi_data)
    n_act     = sum(m.n_actions_total for m in roi_data)
    n_sbvr_t  = sbvr["terms"]
    n_sbvr_r  = sbvr["rules"]

    c1,c2,c3,c4,c5,c6,c7 = st.columns(7)
    c1.metric("Saúde",       f"{score:.1f} / 10")
    c2.metric("ROI-TR Médio",f"{avg_roi:.1f}",
              delta="Alto" if avg_roi >= 7.5 else ("Médio" if avg_roi >= 4.5 else "Baixo"),
              delta_color="normal" if avg_roi >= 4.5 else "inverse")
    c3.metric("Fulfillment", f"{avg_fill*100:.0f}%")
    c4.metric("TRC Médio",   f"{avg_trc:.0f}%",
              delta="Alto" if avg_trc > 40 else ("Médio" if avg_trc > 20 else "Baixo"),
              delta_color="inverse" if avg_trc > 20 else "normal")
    c5.metric("Ações",       f"{sum(m.n_actions_complete for m in roi_data)}/{n_act}",
              delta=f"{act_rate*100:.0f}% conc.")
    c6.metric("SBVR",        f"{n_sbvr_t} termos · {n_sbvr_r} regras")
    c7.metric("Contradições",f"{len(contradictions)}",
              delta="Atenção" if contradictions else "Nenhuma",
              delta_color="inverse" if contradictions else "normal")

    st.markdown("---")
else:
    st.info("Nenhuma reunião encontrada para este contexto. Execute o pipeline para gerar indicadores.")
    st.stop()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_qual, tab_art, tab_dist, tab_know, tab_alerts = st.tabs([
    "📈 Qualidade & Evolução",
    "📦 Artefatos",
    "🎯 Distribuição",
    "🧠 Conhecimento",
    "⚡ Alertas & Insights",
])

# ── Tab 1: Qualidade & Evolução ───────────────────────────────────────────────
with tab_qual:
    col_radar, col_roi = st.columns([1, 2])
    with col_radar:
        st.plotly_chart(_chart_health_radar(health), use_container_width=True, config={"displayModeBar": False})
    with col_roi:
        st.plotly_chart(_chart_roi_evolution(roi_data), use_container_width=True, config={"displayModeBar": False})

    col_trc, col_fill = st.columns(2)
    with col_trc:
        st.plotly_chart(_chart_trc(roi_data), use_container_width=True, config={"displayModeBar": False})
    with col_fill:
        st.plotly_chart(_chart_fulfillment_bar(roi_data), use_container_width=True, config={"displayModeBar": False})

    # ── Meeting timeline table ─────────────────────────────────────────────
    with st.expander("📋 Detalhes por Reunião", expanded=False):
        import pandas as pd
        rows = []
        for m in roi_data:
            rows.append({
                "Reunião":      f"R{m.meeting_number}",
                "Título":       m.title[:40] + ("…" if len(m.title) > 40 else ""),
                "Tipo":         m.type_icon + " " + m.meeting_type,
                "ROI-TR":       f"{m.roi_tr:.1f}",
                "Fulfillment":  f"{m.fulfillment_score*100:.0f}%",
                "TRC":          f"{m.trc:.0f}%",
                "Requisitos":   m.n_requirements,
                "Decisões":     m.n_decisions,
                "Ações":        f"{m.n_actions_complete}/{m.n_actions_total}",
                "SBVR":         m.n_sbvr,
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)

# ── Tab 2: Artefatos ──────────────────────────────────────────────────────────
with tab_art:
    st.plotly_chart(_chart_artefacts(roi_data), use_container_width=True, config={"displayModeBar": False})
    st.plotly_chart(_chart_cumulative(roi_data), use_container_width=True, config={"displayModeBar": False})

# ── Tab 3: Distribuição ───────────────────────────────────────────────────────
with tab_dist:
    col_type, col_act = st.columns(2)
    with col_type:
        st.plotly_chart(_chart_meeting_types(roi_data), use_container_width=True, config={"displayModeBar": False})
    with col_act:
        st.plotly_chart(_chart_actions_donut(roi_data), use_container_width=True, config={"displayModeBar": False})

    if reqs:
        col_rtype, col_rpri = st.columns(2)
        with col_rtype:
            st.plotly_chart(_chart_reqs_by_type(reqs), use_container_width=True, config={"displayModeBar": False})
        with col_rpri:
            st.plotly_chart(_chart_reqs_by_priority(reqs), use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("Nenhum requisito encontrado para este contexto.")

# ── Tab 4: Conhecimento ───────────────────────────────────────────────────────
with tab_know:
    ckf_text   = (ctx_info.get("skill_md") or "").strip()
    ckf_words  = len(ckf_text.split()) if ckf_text else 0
    ckf_status = f"Preenchido ({ckf_words} palavras)" if ckf_text else "Vazio"

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("CKF",              ckf_status)
    k2.metric("Arquivos Ref.",    f"{n_files} arquivo(s)")
    k3.metric("Termos SBVR",      sbvr["terms"])
    k4.metric("Regras SBVR",      sbvr["rules"])

    st.markdown("")

    # CKF preview
    col_ckf, col_files = st.columns(2)
    with col_ckf:
        st.markdown("**Context Knowledge File**")
        if ckf_text:
            with st.expander("Visualizar CKF", expanded=False):
                st.markdown(ckf_text)
        else:
            st.warning("CKF vazio. Preencha em Configurações → Context Knowledge File.")
            st.page_link("pages/Settings.py", label="Ir para Configurações")

    with col_files:
        st.markdown("**Arquivos de Referência**")
        from core.project_store import list_context_files as _list_files
        _files = _list_files(project_id)
        if _files:
            for f in _files:
                size_kb = (f.get("file_size") or 0) / 1024
                date    = (f.get("uploaded_at") or "")[:10]
                st.caption(f"📄 **{f['filename']}** ({f['file_type'].upper()}, {size_kb:.0f} KB) — {date}")
        else:
            st.warning("Nenhum arquivo de referência. Adicione em Configurações.")
            st.page_link("pages/Settings.py", label="Ir para Configurações")

    st.markdown("---")
    st.markdown("**Saúde do Conhecimento**")
    km_cols = st.columns(3)
    dims = health.get("dimensions", {})
    for i, (k, v) in enumerate(dims.items()):
        pct = v * 100
        color = _health_color(v * 10)
        km_cols[i % 3].markdown(
            f"**{k}**  \n"
            f"<div style='background:#1e3a5f;border-radius:4px;height:8px;margin:4px 0 2px;'>"
            f"<div style='background:{color};width:{pct:.0f}%;height:8px;border-radius:4px;'></div></div>"
            f"<span style='font-size:0.78rem;color:{color};'>{v*10:.1f}/10</span>",
            unsafe_allow_html=True,
        )

# ── Tab 5: Alertas & Insights ─────────────────────────────────────────────────
with tab_alerts:
    _render_insights(insights)

    if contradictions:
        st.markdown("")
        st.markdown("#### ⚡ Contradições Detectadas em Requisitos")
        for c in contradictions[:10]:
            req_data = c.get("requirements") or {}
            req_num  = req_data.get("req_number", "?")
            title    = req_data.get("title",   "—")
            note     = c.get("notes") or c.get("change_summary") or "Sem detalhes"
            st.error(f"**REQ-{req_num}** — {title}  \n{note}")
        if len(contradictions) > 10:
            st.caption(f"+ {len(contradictions)-10} contradições adicionais no Req. Tracker.")
        st.page_link("pages/ReqTracker.py", label="Ver Req. Tracker")
    else:
        st.success("Nenhuma contradição de requisito detectada neste contexto.")

    st.markdown("")
    st.markdown("#### 🔄 Tópicos Recorrentes")
    try:
        from modules.cross_meeting_analyzer import find_recurring_topics
        with st.spinner("Analisando tópicos recorrentes..."):
            topics = find_recurring_topics(project_id, min_meetings=2, max_results=6)
        if topics:
            for t in topics:
                with st.expander(
                    f"{t.intensity_label} — Reuniões {t.meetings_str} — {', '.join(t.keywords[:3])}",
                    expanded=False,
                ):
                    c1, c2 = st.columns(2)
                    c1.caption(f"**R{t.meetings[0]}:** {t.excerpt_a[:200]}…" if len(t.excerpt_a) > 200 else t.excerpt_a)
                    c2.caption(f"**R{t.meetings[-1]}:** {t.excerpt_b[:200]}…" if len(t.excerpt_b) > 200 else t.excerpt_b)
        else:
            st.info("Nenhum tópico recorrente detectado (requer embeddings nas transcrições).")
    except Exception as _topics_err:
        st.info(f"Análise de tópicos indisponível: {_topics_err}")

    st.markdown("")
    if st.button("🔄 Atualizar dados", help="Limpa o cache e recarrega todos os indicadores"):
        st.cache_data.clear()
        st.rerun()
