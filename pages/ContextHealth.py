# pages/ContextHealth.py
# ─────────────────────────────────────────────────────────────────────────────
# Saúde do Contexto — Dashboard integrado de qualidade e conhecimento
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import json
import streamlit as st
import plotly.graph_objects as go

from ui.auth_gate import apply_auth_gate
from ui.project_selector import require_active_project
from modules.supabase_client import get_supabase_client, supabase_configured

apply_auth_gate()

# ─────────────────────────────────────────────────────────────────────────────
# Palette & layout defaults
# ─────────────────────────────────────────────────────────────────────────────

_AMBER  = "#f59e0b"
_BLUE   = "#3b82f6"
_GREEN  = "#22c55e"
_RED    = "#ef4444"
_ORANGE = "#f97316"
_SUB    = "#94a3b8"

_BASE_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#e0e7f0", family="Segoe UI, system-ui"),
    margin=dict(l=20, r=20, t=44, b=20),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=11)),
)


def _L(**overrides) -> dict:
    """Merge _BASE_LAYOUT with per-chart overrides (avoids duplicate-kwarg error)."""
    return {**_BASE_LAYOUT, **overrides}


def _roi_color(v):
    return _GREEN if v >= 7.5 else ("#eab308" if v >= 4.5 else (_ORANGE if v >= 2.0 else _RED))

def _health_color(v):
    return _GREEN if v >= 7.5 else ("#eab308" if v >= 5.5 else (_ORANGE if v >= 3.5 else _RED))

def _trc_color(v):
    return _RED if v > 40 else (_ORANGE if v > 20 else _GREEN)


# ─────────────────────────────────────────────────────────────────────────────
# Data loaders
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=60, show_spinner=False)
def _load_roi(project_id):
    from modules.meeting_roi_calculator import compute_project_roi
    return compute_project_roi(project_id, cost_per_hour=150.0)


@st.cache_data(ttl=60, show_spinner=False)
def _load_requirements(project_id):
    db = get_supabase_client()
    if not db:
        return []
    try:
        return db.table("requirements").select("req_type,priority,status,meeting_id") \
                 .eq("project_id", project_id).execute().data or []
    except Exception:
        return []


@st.cache_data(ttl=60, show_spinner=False)
def _load_context_info(project_id):
    db = get_supabase_client()
    if not db:
        return {}
    try:
        return db.table("contexts").select("name,context_type,skill_md,description") \
                 .eq("id", project_id).single().execute().data or {}
    except Exception:
        return {}


@st.cache_data(ttl=60, show_spinner=False)
def _load_context_files_count(project_id):
    db = get_supabase_client()
    if not db:
        return 0
    try:
        return len(db.table("context_files").select("id").eq("context_id", project_id).execute().data or [])
    except Exception:
        return 0


@st.cache_data(ttl=60, show_spinner=False)
def _load_sbvr_counts(project_id):
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
def _load_req_contradictions(project_id):
    """Contradições em versões de requisitos (requirement_versions.contradiction_flag)."""
    from core.project_store import list_contradictions
    return list_contradictions(project_id)


@st.cache_data(ttl=60, show_spinner=False)
def _load_kh_contradictions(project_id):
    """Contradições em fatos do Knowledge Hub (kh_contradictions)."""
    try:
        from core.knowledge_store import get_contradictions
        return get_contradictions(project_id, status="open", limit=50)
    except Exception:
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Health score computation
# ─────────────────────────────────────────────────────────────────────────────

def _compute_health(roi_data, ctx_info, n_files, sbvr, req_contradictions, kh_contradictions):
    if not roi_data:
        return {"score": 0.0, "dimensions": {}}

    avg_roi         = sum(m.roi_tr            for m in roi_data) / len(roi_data)
    avg_fulfillment = sum(m.fulfillment_score  for m in roi_data) / len(roi_data)
    avg_trc         = sum(m.trc               for m in roi_data) / len(roi_data)

    # Ações bem-estruturadas: itens que têm responsável E prazo identificados
    # na transcrição — proxy de qualidade, não de status real de conclusão.
    total_actions    = sum(m.n_actions_total    for m in roi_data)
    struct_actions   = sum(m.n_actions_complete for m in roi_data)  # heurístico
    structured_rate  = struct_actions / total_actions if total_actions > 0 else 0.5

    ckf_filled      = bool((ctx_info.get("skill_md") or "").strip())
    knowledge_score = (
        (0.40 if ckf_filled else 0.0)
        + (0.35 if n_files > 0 else 0.0)
        + (0.25 if (sbvr["terms"] + sbvr["rules"]) > 0 else 0.0)
    )

    trc_score = max(0.0, 1.0 - avg_trc / 100.0)

    # Penalidade por contradições abertas (ambos os tipos)
    total_contradictions = len(req_contradictions) + len(kh_contradictions)
    contradiction_penalty = min(0.3, total_contradictions * 0.04)

    dimensions = {
        "ROI-TR Médio":         (avg_roi / 10.0,    0.35),
        "Fulfillment":          (avg_fulfillment,    0.25),
        "Ações Estruturadas":   (structured_rate,    0.15),
        "Base de Conhecimento": (knowledge_score,    0.15),
        "Objetividade (TRC)":   (trc_score,          0.10),
    }

    raw   = sum(v * w for v, w in dimensions.values())
    score = max(0.0, min(10.0, raw * 10.0 - contradiction_penalty * 10.0))

    return {
        "score":            score,
        "dimensions":       {k: v for k, (v, _) in dimensions.items()},
        "weights":          {k: w for k, (_, w) in dimensions.items()},
        "avg_roi":          avg_roi,
        "avg_fulfill":      avg_fulfillment,
        "avg_trc":          avg_trc,
        "structured_rate":  structured_rate,
        "total_actions":    total_actions,
        "struct_actions":   struct_actions,
        "ckf_filled":       ckf_filled,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Auto-insights (racional revisado)
# ─────────────────────────────────────────────────────────────────────────────

def _generate_insights(roi_data, health, reqs, req_contra, kh_contra, sbvr, n_files):
    if not roi_data:
        return [{"icon": "ℹ️", "color": _SUB,
                 "text": "Nenhuma reunião encontrada. Execute o pipeline para gerar indicadores."}]

    insights = []
    score    = health["score"]
    avg_roi  = health["avg_roi"]
    avg_trc  = health["avg_trc"]
    avg_fill = health["avg_fulfill"]
    total_c  = len(req_contra) + len(kh_contra)

    # ── Score geral ───────────────────────────────────────────────────────────
    if score >= 7.5:
        insights.append({"icon": "🟢", "color": _GREEN,
            "text": f"Contexto saudável — score {score:.1f}/10. Reuniões produtivas e base de conhecimento consolidada."})
    elif score >= 5.0:
        insights.append({"icon": "🟡", "color": "#eab308",
            "text": f"Contexto em desenvolvimento — score {score:.1f}/10. Há espaço para melhorar consistência das reuniões e enriquecer o CKF."})
    else:
        insights.append({"icon": "🔴", "color": _RED,
            "text": f"Contexto requer atenção — score {score:.1f}/10. Revise a qualidade das reuniões e fortaleça o conhecimento documentado."})

    # ── ROI-TR ────────────────────────────────────────────────────────────────
    if avg_roi < 3.0:
        insights.append({"icon": "📉", "color": _ORANGE,
            "text": f"ROI-TR médio baixo ({avg_roi:.1f}/10): as reuniões geram poucos artefatos concretos — requisitos, decisões, SBVR e BPMN — em relação ao tempo investido."})
    elif avg_roi >= 7.0:
        insights.append({"icon": "📈", "color": _GREEN,
            "text": f"ROI-TR excelente ({avg_roi:.1f}/10): as reuniões produzem artefatos ricos e bem estruturados."})

    # ── TRC — proxy linguístico (revisado) ────────────────────────────────────
    if avg_trc > 40:
        insights.append({"icon": "🔁", "color": _RED,
            "text": (
                f"Indicador de linguagem cíclica elevado ({avg_trc:.0f}%). "
                "O TRC conta frases como 'de novo', 'como já disse', 'voltando ao mesmo ponto' — "
                "um proxy que sugere discussões circulares, não um rastreador direto de retrabalho. "
                "Verifique se as pautas estão sendo cumpridas e as decisões, registradas."
            )})
    elif avg_trc < 12:
        insights.append({"icon": "✅", "color": _GREEN,
            "text": f"Linguagem objetiva nas transcrições (TRC {avg_trc:.0f}%): poucos marcadores de repetição detectados."})

    # ── Fulfillment ───────────────────────────────────────────────────────────
    if avg_fill < 0.4:
        insights.append({"icon": "📋", "color": _ORANGE,
            "text": f"Fulfillment médio baixo ({avg_fill*100:.0f}%): as reuniões não entregam o conjunto mínimo de artefatos esperado para seu tipo. Verifique se o tipo classificado condiz com o objetivo real da reunião."})

    # ── Contradições ─────────────────────────────────────────────────────────
    if total_c > 0:
        parts = []
        if req_contra:
            parts.append(f"{len(req_contra)} em versões de requisitos")
        if kh_contra:
            parts.append(f"{len(kh_contra)} em fatos do Knowledge Hub")
        insights.append({"icon": "⚡", "color": _RED,
            "text": f"{total_c} contradição(ões) abertas: {' e '.join(parts)}. Revise no Req. Tracker e no Knowledge Hub antes de prosseguir."})

    # ── Ações estruturadas ────────────────────────────────────────────────────
    sa = health["struct_actions"]
    ta = health["total_actions"]
    if ta > 0:
        pct = sa / ta * 100
        if pct < 40:
            insights.append({"icon": "📌", "color": _ORANGE,
                "text": (
                    f"Somente {pct:.0f}% dos itens de ação têm responsável e prazo identificados "
                    f"({sa}/{ta}). Este indicador é uma heurística textual — não reflete "
                    "conclusão real das ações. Para rastreamento real, use o Req. Tracker."
                )})

    # ── Conhecimento ──────────────────────────────────────────────────────────
    if not health["ckf_filled"]:
        insights.append({"icon": "📖", "color": _SUB,
            "text": "CKF vazio. Preencher o Context Knowledge File melhora a qualidade dos agentes LLM em todas as reuniões futuras."})
    if n_files == 0:
        insights.append({"icon": "📎", "color": _SUB,
            "text": "Nenhum arquivo de referência carregado. Manuais, políticas e apresentações enriquecem o contexto dos agentes."})
    elif n_files >= 3:
        insights.append({"icon": "📚", "color": _GREEN,
            "text": f"{n_files} arquivo(s) de referência disponíveis — boa cobertura documental do contexto."})

    # ── Variância ────────────────────────────────────────────────────────────
    if len(roi_data) >= 3:
        best  = max(roi_data, key=lambda m: m.roi_tr)
        worst = min(roi_data, key=lambda m: m.roi_tr)
        if best.roi_tr - worst.roi_tr > 4:
            insights.append({"icon": "📊", "color": _SUB,
                "text": f"Grande variância de qualidade: Reunião {best.meeting_number} (ROI {best.roi_tr:.1f}) vs Reunião {worst.meeting_number} (ROI {worst.roi_tr:.1f}). Identifique o que diferencia as melhores reuniões e replique."})

    return insights[:8]


# ─────────────────────────────────────────────────────────────────────────────
# Chart builders
# ─────────────────────────────────────────────────────────────────────────────

def _chart_roi_evolution(roi_data):
    labels   = [f"R{m.meeting_number}" for m in roi_data]
    roi_vals = [m.roi_tr for m in roi_data]
    fill_vals= [m.fulfillment_score * 10 for m in roi_data]

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
        customdata=[m.fulfillment_score * 100 for m in roi_data],
        hovertemplate="<b>%{x}</b><br>Fulfillment: %{customdata:.0f}%<extra></extra>",
    ))
    fig.add_hline(y=7.5, line=dict(color=_GREEN, width=1, dash="dash"),
                  annotation_text="Meta ROI", annotation_font_color=_GREEN)
    fig.add_hline(y=4.5, line=dict(color=_ORANGE, width=1, dash="dash"))
    fig.update_layout(**_L(
        title=dict(text="Evolução ROI-TR e Fulfillment por Reunião", font=dict(size=14, color=_AMBER)),
        yaxis=dict(range=[0, 10.5], tickfont=dict(color=_SUB), gridcolor="#1e3a5f"),
        xaxis=dict(tickfont=dict(color=_SUB), gridcolor="#1e3a5f"),
        height=300,
    ))
    return fig


def _chart_trc(roi_data):
    labels   = [f"R{m.meeting_number}" for m in roi_data]
    trc_vals = [m.trc for m in roi_data]

    fig = go.Figure(go.Bar(
        x=labels, y=trc_vals,
        marker=dict(color=[_trc_color(v) for v in trc_vals],
                    line=dict(color="#0a1929", width=1)),
        hovertemplate="<b>%{x}</b><br>TRC: %{y:.1f}%<extra></extra>",
    ))
    fig.add_hline(y=40, line=dict(color=_RED, width=1.5, dash="dash"),
                  annotation_text="Alto", annotation_font_color=_RED)
    fig.add_hline(y=20, line=dict(color=_ORANGE, width=1, dash="dot"))
    fig.update_layout(**_L(
        title=dict(text="TRC — Linguagem Cíclica por Reunião (%)", font=dict(size=14, color=_AMBER)),
        yaxis=dict(range=[0, max(max(trc_vals, default=0) * 1.2, 50)],
                   ticksuffix="%", tickfont=dict(color=_SUB), gridcolor="#1e3a5f"),
        xaxis=dict(tickfont=dict(color=_SUB)),
        height=280,
    ))
    return fig


def _chart_fulfillment_bar(roi_data):
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
    fig.add_hline(y=90, line=dict(color=_GREEN, width=1, dash="dash"),
                  annotation_text="Pleno", annotation_font_color=_GREEN)
    fig.add_hline(y=60, line=dict(color=_AMBER, width=1, dash="dot"))
    fig.update_layout(**_L(
        title=dict(text="Fulfillment por Reunião (%)", font=dict(size=14, color=_AMBER)),
        yaxis=dict(range=[0, 110], ticksuffix="%", tickfont=dict(color=_SUB), gridcolor="#1e3a5f"),
        xaxis=dict(tickfont=dict(color=_SUB)),
        height=260,
    ))
    return fig


def _chart_health_radar(health):
    dims   = list(health["dimensions"].keys())
    values = [v * 10 for v in health["dimensions"].values()]
    fig = go.Figure(go.Scatterpolar(
        r=values + [values[0]], theta=dims + [dims[0]],
        fill="toself", fillcolor="rgba(245,158,11,0.15)",
        line=dict(color=_AMBER, width=2),
        marker=dict(size=6, color=_AMBER),
        hovertemplate="<b>%{theta}</b>: %{r:.1f}<extra></extra>",
    ))
    fig.update_layout(**_L(
        polar=dict(
            bgcolor="rgba(0,0,0,0)",
            radialaxis=dict(range=[0, 10], tickfont=dict(color=_SUB, size=9),
                            gridcolor="#1e3a5f", linecolor="#1e3a5f"),
            angularaxis=dict(tickfont=dict(color="#e0e7f0", size=10),
                             gridcolor="#1e3a5f", linecolor="#1e3a5f"),
        ),
        title=dict(text="Radar de Saúde (0–10)", font=dict(size=14, color=_AMBER)),
        height=340,
    ))
    return fig


def _chart_artefacts(roi_data):
    labels = [f"R{m.meeting_number}" for m in roi_data]
    fig = go.Figure()
    for name, vals, color in [
        ("Requisitos", [m.n_requirements for m in roi_data], _BLUE),
        ("Decisões",   [m.n_decisions     for m in roi_data], _AMBER),
        ("Ações",      [m.n_actions_total  for m in roi_data], "#a78bfa"),
        ("SBVR",       [m.n_sbvr           for m in roi_data], "#34d399"),
    ]:
        fig.add_trace(go.Bar(name=name, x=labels, y=vals, marker_color=color,
                             hovertemplate=f"<b>%{{x}}</b><br>{name}: %{{y}}<extra></extra>"))
    fig.update_layout(**_L(
        barmode="group",
        title=dict(text="Artefatos por Reunião", font=dict(size=14, color=_AMBER)),
        yaxis=dict(tickfont=dict(color=_SUB), gridcolor="#1e3a5f"),
        xaxis=dict(tickfont=dict(color=_SUB)),
        height=300,
    ))
    return fig


def _chart_cumulative(roi_data):
    labels = [f"R{m.meeting_number}" for m in roi_data]
    r = d = s = 0
    cum_req, cum_dec, cum_sbvr = [], [], []
    for m in roi_data:
        r += m.n_requirements; d += m.n_decisions; s += m.n_sbvr
        cum_req.append(r); cum_dec.append(d); cum_sbvr.append(s)

    fig = go.Figure()
    for name, vals, color in [
        ("Requisitos", cum_req,  _BLUE),
        ("Decisões",   cum_dec,  _AMBER),
        ("SBVR",       cum_sbvr, "#34d399"),
    ]:
        fig.add_trace(go.Scatter(x=labels, y=vals, name=name, mode="lines",
                                 stackgroup="one", line=dict(color=color, width=1.5),
                                 hovertemplate=f"<b>%{{x}}</b><br>{name} acum.: %{{y}}<extra></extra>"))
    fig.update_layout(**_L(
        title=dict(text="Acúmulo de Artefatos ao Longo do Projeto", font=dict(size=14, color=_AMBER)),
        yaxis=dict(tickfont=dict(color=_SUB), gridcolor="#1e3a5f"),
        xaxis=dict(tickfont=dict(color=_SUB)),
        height=260,
    ))
    return fig


def _chart_meeting_types(roi_data):
    from collections import Counter
    counts  = Counter(m.meeting_type for m in roi_data)
    labels  = list(counts.keys())
    values  = list(counts.values())
    palette = [_AMBER, _BLUE, "#a78bfa", "#34d399", _ORANGE, "#f472b6",
               "#60a5fa", "#fb923c", "#4ade80", "#818cf8", _SUB]
    fig = go.Figure(go.Pie(
        labels=labels, values=values, hole=0.55,
        marker=dict(colors=palette[:len(labels)], line=dict(color="#0a1929", width=2)),
        textinfo="percent", textfont=dict(size=11),
        hovertemplate="<b>%{label}</b>: %{value} reunião(ões) (%{percent})<extra></extra>",
    ))
    fig.update_layout(**{**_L(
        title=dict(text="Tipos de Reunião", font=dict(size=14, color=_AMBER)),
        height=300, showlegend=True,
    ), "legend": dict(orientation="v", x=1.02, y=0.5, font=dict(size=10), bgcolor="rgba(0,0,0,0)")})
    return fig


def _chart_actions_donut(roi_data):
    total = sum(m.n_actions_total    for m in roi_data)
    done  = sum(m.n_actions_complete for m in roi_data)
    pend  = max(0, total - done)
    pct   = (done / total * 100) if total > 0 else 0

    fig = go.Figure(go.Pie(
        labels=["Com responsável+prazo", "Sem responsável/prazo"],
        values=[done, pend], hole=0.60,
        marker=dict(colors=[_GREEN, "#334155"], line=dict(color="#0a1929", width=2)),
        textinfo="percent+value", textfont=dict(size=11),
        hovertemplate="<b>%{label}</b>: %{value}<extra></extra>",
    ))
    fig.add_annotation(text=f"{pct:.0f}%", x=0.5, y=0.5, showarrow=False,
                       font=dict(size=22, color="#fff", family="Segoe UI"))
    fig.update_layout(**_L(
        title=dict(text=f"Ações estruturadas ({done}/{total})", font=dict(size=14, color=_AMBER)),
        height=280, showlegend=True,
    ))
    return fig


def _chart_reqs_by_type(reqs):
    from collections import Counter
    counts = Counter(r.get("req_type", "Outro") for r in reqs)
    items  = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    palette= [_BLUE, _AMBER, "#a78bfa", "#34d399", _ORANGE, "#f472b6"]
    fig = go.Figure(go.Bar(
        y=[k for k,_ in items], x=[v for _,v in items], orientation="h",
        marker=dict(color=palette[:len(items)], line=dict(color="#0a1929", width=1)),
        hovertemplate="<b>%{y}</b>: %{x}<extra></extra>",
    ))
    fig.update_layout(**_L(
        title=dict(text="Requisitos por Tipo", font=dict(size=14, color=_AMBER)),
        xaxis=dict(tickfont=dict(color=_SUB), gridcolor="#1e3a5f"),
        yaxis=dict(tickfont=dict(color=_SUB), autorange="reversed"),
        height=280,
    ))
    return fig


def _chart_reqs_by_priority(reqs):
    from collections import Counter
    counts = Counter(r.get("priority", "Média") for r in reqs)
    order  = ["Alta", "Média", "Baixa"]
    labels = [p for p in order if p in counts] + [p for p in counts if p not in order]
    values = [counts[p] for p in labels]
    cmap   = {"Alta": _RED, "Média": _AMBER, "Baixa": _GREEN}
    fig = go.Figure(go.Bar(
        x=labels, y=values,
        marker=dict(color=[cmap.get(p, _BLUE) for p in labels],
                    line=dict(color="#0a1929", width=1)),
        hovertemplate="<b>%{x}</b>: %{y}<extra></extra>",
    ))
    fig.update_layout(**_L(
        title=dict(text="Requisitos por Prioridade", font=dict(size=14, color=_AMBER)),
        yaxis=dict(tickfont=dict(color=_SUB), gridcolor="#1e3a5f"),
        xaxis=dict(tickfont=dict(color=_SUB)),
        height=260,
    ))
    return fig


# ─────────────────────────────────────────────────────────────────────────────
# Export builders
# ─────────────────────────────────────────────────────────────────────────────

def _build_html_report(project_name, health, roi_data, reqs, sbvr, n_files,
                       req_contra, kh_contra, insights, ctx_info) -> str:
    """Build a self-contained HTML report with embedded Plotly charts."""
    import plotly.io as pio

    def _fig_html(fig) -> str:
        return pio.to_html(fig, full_html=False, include_plotlyjs=False,
                           config={"displayModeBar": False})

    score = health["score"]
    color = _health_color(score)
    label = ("Excelente" if score >= 7.5 else "Saudável" if score >= 5.5
             else "Em risco" if score >= 3.5 else "Crítico")

    avg_roi  = health["avg_roi"]
    avg_trc  = health["avg_trc"]
    avg_fill = health["avg_fulfill"]

    insight_html = "".join(
        f'<div class="insight"><span class="ins-icon">{i["icon"]}</span>'
        f'<span>{i["text"]}</span></div>'
        for i in insights
    )

    req_contra_html = ""
    if req_contra:
        for c in req_contra[:10]:
            rd  = c.get("requirements") or {}
            req_contra_html += (
                f'<div class="contra-item">'
                f'<strong>REQ-{rd.get("req_number","?")} — {rd.get("title","—")}</strong><br>'
                f'<span class="sub">{c.get("contradiction_detail") or c.get("change_summary") or c.get("description") or "Sem detalhes"}</span></div>'
            )

    kh_contra_html = ""
    if kh_contra:
        for c in kh_contra[:10]:
            kh_contra_html += (
                f'<div class="contra-item">'
                f'<strong>{c.get("description","?")[:100]}</strong><br>'
                f'<span class="sub">Processo: {c.get("process_name","—")} · Severidade: {c.get("severity","—")}</span>'
                f'<br><span class="sub">{c.get("clarifying_question","")[:120]}</span></div>'
            )

    charts_html = ""
    for fig_fn in [
        lambda: _chart_roi_evolution(roi_data),
        lambda: _chart_trc(roi_data),
        lambda: _chart_fulfillment_bar(roi_data),
        lambda: _chart_artefacts(roi_data),
        lambda: _chart_cumulative(roi_data),
        lambda: _chart_meeting_types(roi_data),
        lambda: _chart_actions_donut(roi_data),
    ]:
        try:
            charts_html += f'<div class="chart">{_fig_html(fig_fn())}</div>'
        except Exception:
            pass

    if reqs:
        for fig_fn in [lambda: _chart_reqs_by_type(reqs),
                       lambda: _chart_reqs_by_priority(reqs)]:
            try:
                charts_html += f'<div class="chart">{_fig_html(fig_fn())}</div>'
            except Exception:
                pass

    from datetime import date
    today = date.today().strftime("%d/%m/%Y")

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Saúde do Contexto — {project_name}</title>
<script src="https://cdn.plot.ly/plotly-2.30.0.min.js"></script>
<style>
  :root {{ --navy:#0d2a4a; --amber:#f59e0b; --bg:#0a1929; --card:#0f2235;
           --text:#e0e7f0; --sub:#94a3b8; --border:#1e3a5f; }}
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{ background:var(--bg); color:var(--text);
          font-family:'Segoe UI',system-ui,sans-serif; font-size:14px;
          line-height:1.6; padding:0 0 60px; }}
  .hero {{ background:linear-gradient(135deg,var(--navy) 0%,#112240 100%);
           border-bottom:3px solid {color}; padding:32px 48px; }}
  .hero h1 {{ font-size:1.8rem; font-weight:800; color:#fff; margin-bottom:4px; }}
  .hero .score {{ font-size:3rem; font-weight:900; color:{color}; }}
  .hero .meta {{ font-size:0.82rem; color:var(--sub); margin-top:6px; }}
  .badge {{ background:{color}22; color:{color}; padding:3px 12px;
            border-radius:12px; font-size:0.8rem; font-weight:700; display:inline-block; margin-top:8px; }}
  .kpis {{ display:flex; gap:16px; padding:24px 48px; flex-wrap:wrap; }}
  .kpi {{ background:var(--card); border:1px solid var(--border); border-radius:8px;
          padding:16px 20px; min-width:120px; flex:1; }}
  .kpi .val {{ font-size:1.5rem; font-weight:700; color:#fff; }}
  .kpi .lbl {{ font-size:0.72rem; color:var(--sub); text-transform:uppercase; letter-spacing:1px; margin-top:4px; }}
  section {{ padding:0 48px 28px; }}
  h2 {{ font-size:1.1rem; color:var(--amber); border-bottom:1px solid var(--border);
        padding-bottom:8px; margin:28px 0 16px; }}
  .chart {{ background:var(--card); border:1px solid var(--border); border-radius:8px;
            padding:12px; margin-bottom:16px; }}
  .insight {{ display:flex; gap:10px; padding:10px 0;
              border-bottom:1px solid var(--border); font-size:0.88rem; color:#cbd5e1; }}
  .ins-icon {{ font-size:1.1rem; flex-shrink:0; }}
  .contra-item {{ background:#1a0a0a; border-left:3px solid {_RED};
                  border-radius:4px; padding:10px 14px; margin-bottom:8px; font-size:0.85rem; }}
  .contra-item strong {{ color:#fca5a5; }}
  .sub {{ color:var(--sub); font-size:0.8rem; }}
  .footer {{ text-align:center; color:var(--sub); font-size:0.75rem; padding-top:32px; }}
</style>
</head>
<body>

<div class="hero" style="display:flex;justify-content:space-between;align-items:center;">
  <div>
    <div style="font-size:0.72rem;color:var(--sub);letter-spacing:1px;text-transform:uppercase;">
      Relatório de Saúde do Contexto · {today}
    </div>
    <h1>{project_name}</h1>
    <div class="meta">
      {len(roi_data)} reunião(ões) &nbsp;·&nbsp; {len(reqs)} requisitos &nbsp;·&nbsp;
      {n_files} arquivo(s) de referência &nbsp;·&nbsp;
      {sbvr["terms"]} termos SBVR &nbsp;·&nbsp;
      {'CKF ativo' if ctx_info.get("skill_md") else 'Sem CKF'}
    </div>
    <div class="badge">{label}</div>
  </div>
  <div style="text-align:center;">
    <div class="score">{score:.1f}</div>
    <div class="sub">/ 10 &nbsp;·&nbsp; SAÚDE</div>
  </div>
</div>

<div class="kpis">
  <div class="kpi"><div class="val">{avg_roi:.1f}</div><div class="lbl">ROI-TR Médio</div></div>
  <div class="kpi"><div class="val">{avg_fill*100:.0f}%</div><div class="lbl">Fulfillment Médio</div></div>
  <div class="kpi"><div class="val">{avg_trc:.0f}%</div><div class="lbl">TRC Médio</div></div>
  <div class="kpi"><div class="val">{health["struct_actions"]}/{health["total_actions"]}</div><div class="lbl">Ações estruturadas</div></div>
  <div class="kpi"><div class="val">{len(req_contra)+len(kh_contra)}</div><div class="lbl">Contradições</div></div>
  <div class="kpi"><div class="val">{sbvr["terms"]+sbvr["rules"]}</div><div class="lbl">Artefatos SBVR</div></div>
</div>

<section>
  <h2>Insights Automáticos</h2>
  {insight_html if insight_html else "<p style='color:var(--sub)'>Sem insights gerados.</p>"}
</section>

<section>
  <h2>Evolução de Qualidade</h2>
  {charts_html}
</section>

{"<section><h2>Contradições em Requisitos</h2>" + req_contra_html + "</section>" if req_contra else ""}
{"<section><h2>Contradições no Knowledge Hub</h2>" + kh_contra_html + "</section>" if kh_contra else ""}

<div class="footer">Gerado por Process2Diagram · {today} · Este relatório é autocontido.</div>
</body>
</html>"""


def _build_json_report(project_name, health, roi_data, reqs, sbvr, n_files,
                       req_contra, kh_contra) -> str:
    meetings_data = [
        {
            "meeting_number": m.meeting_number,
            "title":          m.title,
            "type":           m.meeting_type,
            "roi_tr":         round(m.roi_tr, 2),
            "fulfillment":    round(m.fulfillment_score, 3),
            "trc":            round(m.trc, 1),
            "n_requirements": m.n_requirements,
            "n_decisions":    m.n_decisions,
            "n_actions":      m.n_actions_total,
            "n_sbvr":         m.n_sbvr,
        }
        for m in roi_data
    ]
    return json.dumps({
        "context": project_name,
        "generated_at": __import__("datetime").date.today().isoformat(),
        "health_score": round(health["score"], 2),
        "dimensions": {k: round(v * 10, 2) for k, v in health["dimensions"].items()},
        "summary": {
            "avg_roi":            round(health["avg_roi"], 2),
            "avg_fulfillment_pct":round(health["avg_fulfill"] * 100, 1),
            "avg_trc_pct":        round(health["avg_trc"], 1),
            "total_requirements": len(reqs),
            "sbvr_terms":         sbvr["terms"],
            "sbvr_rules":         sbvr["rules"],
            "context_files":      n_files,
            "req_contradictions": len(req_contra),
            "kh_contradictions":  len(kh_contra),
            "structured_actions": f"{health['struct_actions']}/{health['total_actions']}",
        },
        "meetings": meetings_data,
    }, ensure_ascii=False, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# Header & Insights HTML components
# ─────────────────────────────────────────────────────────────────────────────

def _render_header(project_name, ctx_type, score, n_meetings, n_reqs, n_files, ckf_filled):
    color     = _health_color(score)
    label     = ("Excelente" if score >= 7.5 else "Saudável" if score >= 5.5
                 else "Em risco" if score >= 3.5 else "Crítico")
    type_lbl  = (ctx_type or "project").replace("_", " ").title()
    ckf_badge = (
        '<span style="background:#14532d;color:#86efac;padding:2px 8px;'
        'border-radius:10px;font-size:0.72rem;font-weight:700;">CKF Ativo</span>'
        if ckf_filled else
        '<span style="background:#3d1c02;color:#fca5a5;padding:2px 8px;'
        'border-radius:10px;font-size:0.72rem;font-weight:700;">Sem CKF</span>'
    )
    st.components.v1.html(f"""
<div style="background:linear-gradient(135deg,#0d2a4a 0%,#112240 100%);
            border-bottom:3px solid {color};border-radius:8px;
            padding:26px 34px 22px;display:flex;
            justify-content:space-between;align-items:center;gap:20px;">
  <div>
    <div style="font-size:0.72rem;color:#94a3b8;letter-spacing:1px;text-transform:uppercase;margin-bottom:6px;">
      {type_lbl} &nbsp;·&nbsp; {n_meetings} reunião(ões) &nbsp;·&nbsp;
      {n_reqs} requisitos &nbsp;·&nbsp; {n_files} arquivo(s) &nbsp;&nbsp;{ckf_badge}
    </div>
    <div style="font-size:1.8rem;font-weight:800;color:#fff;line-height:1.2;">{project_name}</div>
    <div style="font-size:0.88rem;color:#94a3b8;margin-top:6px;">
      Dashboard de saúde, qualidade e conhecimento do contexto
    </div>
  </div>
  <div style="text-align:center;min-width:120px;">
    <div style="font-size:3rem;font-weight:900;color:{color};line-height:1;">{score:.1f}</div>
    <div style="font-size:0.68rem;color:#94a3b8;margin-top:2px;">/ 10 · SAÚDE</div>
    <div style="background:{color}22;color:{color};padding:4px 14px;border-radius:12px;
                font-size:0.78rem;font-weight:700;margin-top:8px;display:inline-block;">{label}</div>
  </div>
</div>""", height=132)


def _render_insights(insights):
    items = "".join(f"""
<div style="display:flex;gap:12px;padding:10px 0;border-bottom:1px solid #1a3050;">
  <div style="font-size:1.1rem;flex-shrink:0;margin-top:2px;">{i['icon']}</div>
  <div style="color:#cbd5e1;font-size:0.87rem;line-height:1.55;">{i['text']}</div>
</div>""" for i in insights)

    st.components.v1.html(f"""
<div style="background:#0f2235;border:1px solid #1e3a5f;border-left:4px solid #f59e0b;
            border-radius:8px;padding:16px 20px;">
  <div style="font-size:0.72rem;color:#f59e0b;letter-spacing:1px;text-transform:uppercase;
              margin-bottom:10px;font-weight:700;">Insights Automáticos</div>
  {items}
</div>""", height=min(72 + len(insights) * 62, 540))


# ─────────────────────────────────────────────────────────────────────────────
# Caption helper
# ─────────────────────────────────────────────────────────────────────────────

def _cap(text: str):
    st.caption(f"ℹ️ {text}")


# ─────────────────────────────────────────────────────────────────────────────
# Page
# ─────────────────────────────────────────────────────────────────────────────

if not supabase_configured():
    st.error("⚙️ Supabase não configurado.")
    st.stop()

project_id, project_name = require_active_project()

with st.spinner("Carregando dados do contexto..."):
    roi_data       = _load_roi(project_id)
    reqs           = _load_requirements(project_id)
    ctx_info       = _load_context_info(project_id)
    n_files        = _load_context_files_count(project_id)
    sbvr           = _load_sbvr_counts(project_id)
    req_contra     = _load_req_contradictions(project_id)
    kh_contra      = _load_kh_contradictions(project_id)

health   = _compute_health(roi_data, ctx_info, n_files, sbvr, req_contra, kh_contra)
insights = _generate_insights(roi_data, health, reqs, req_contra, kh_contra, sbvr, n_files)
score    = health["score"]
ctx_type = ctx_info.get("context_type") or "project"
n_reqs   = len(reqs)
n_meetings = len(roi_data)
total_contra = len(req_contra) + len(kh_contra)

# ── Header ───────────────────────────────────────────────────────────────────
_render_header(project_name, ctx_type, score,
               n_meetings, n_reqs, n_files, health.get("ckf_filled", False))

# ── Export buttons (topo) ────────────────────────────────────────────────────
with st.expander("📥 Exportar Relatório de Saúde", expanded=False):
    ex1, ex2 = st.columns(2)
    with ex1:
        if st.button("📄 Gerar HTML", use_container_width=True):
            with st.spinner("Gerando relatório HTML..."):
                html_bytes = _build_html_report(
                    project_name, health, roi_data, reqs, sbvr, n_files,
                    req_contra, kh_contra, insights, ctx_info
                ).encode("utf-8")
            st.download_button(
                "⬇️ Baixar HTML",
                data=html_bytes,
                file_name=f"saude_{project_name.replace(' ','_')}.html",
                mime="text/html",
                use_container_width=True,
            )
    with ex2:
        if st.button("📊 Gerar JSON", use_container_width=True):
            json_bytes = _build_json_report(
                project_name, health, roi_data, reqs, sbvr, n_files,
                req_contra, kh_contra
            ).encode("utf-8")
            st.download_button(
                "⬇️ Baixar JSON",
                data=json_bytes,
                file_name=f"saude_{project_name.replace(' ','_')}.json",
                mime="application/json",
                use_container_width=True,
            )
    st.caption(
        "O HTML é autocontido (gráficos Plotly embutidos) e pode ser enviado por e-mail ou arquivado. "
        "O JSON é adequado para integrações, Power BI ou análise com Excel/Python."
    )

# ── KPI strip ────────────────────────────────────────────────────────────────
if not roi_data:
    st.info("Nenhuma reunião encontrada. Execute o pipeline para gerar indicadores.")
    st.stop()

avg_roi  = health["avg_roi"]
avg_trc  = health["avg_trc"]
avg_fill = health["avg_fulfill"]
n_act    = health["total_actions"]
n_done   = health["struct_actions"]

c1,c2,c3,c4,c5,c6,c7 = st.columns(7)
c1.metric("Saúde Geral",    f"{score:.1f}/10")
c2.metric("ROI-TR Médio",   f"{avg_roi:.1f}",
          delta="Alto" if avg_roi >= 7.5 else ("Médio" if avg_roi >= 4.5 else "Baixo"),
          delta_color="normal" if avg_roi >= 4.5 else "inverse")
c3.metric("Fulfillment",    f"{avg_fill*100:.0f}%")
c4.metric("TRC (linguagem)",f"{avg_trc:.0f}%",
          delta="Alto" if avg_trc > 40 else ("Médio" if avg_trc > 20 else "Baixo"),
          delta_color="inverse" if avg_trc > 20 else "normal")
c5.metric("Ações estr.",    f"{n_done}/{n_act}",
          help="Itens de ação com responsável E prazo identificados na transcrição — heurística textual.")
c6.metric("SBVR",           f"{sbvr['terms']}T · {sbvr['rules']}R")
c7.metric("Contradições",   str(total_contra),
          delta=f"Req:{len(req_contra)} KH:{len(kh_contra)}" if total_contra else "Nenhuma",
          delta_color="inverse" if total_contra else "normal")

st.markdown("---")

# ── Tabs ─────────────────────────────────────────────────────────────────────
tab_qual, tab_art, tab_dist, tab_know, tab_alerts = st.tabs([
    "📈 Qualidade & Evolução",
    "📦 Artefatos",
    "🎯 Distribuição",
    "🧠 Conhecimento",
    "⚡ Alertas & Insights",
])

# ═══════════════════════════════════════════════════════════════
# Tab 1 — Qualidade & Evolução
# ═══════════════════════════════════════════════════════════════
with tab_qual:
    col_radar, col_roi = st.columns([1, 2])

    with col_radar:
        st.plotly_chart(_chart_health_radar(health), use_container_width=True,
                        config={"displayModeBar": False})
        _cap(
            "**Radar de Saúde:** cada eixo representa uma dimensão ponderada do score geral (0–10). "
            "**ROI-TR Médio** (35%) mede produtividade dos artefatos; "
            "**Fulfillment** (25%) indica entrega vs. expectativa do tipo de reunião; "
            "**Ações Estruturadas** (15%) conta itens com responsável e prazo no texto — *heurística*; "
            "**Base de Conhecimento** (15%) avalia CKF, arquivos e SBVR; "
            "**Objetividade/TRC** (10%) penaliza linguagem cíclica. "
            "O score final é a soma ponderada menos penalidade por contradições abertas."
        )

    with col_roi:
        st.plotly_chart(_chart_roi_evolution(roi_data), use_container_width=True,
                        config={"displayModeBar": False})
        _cap(
            "**Evolução ROI-TR:** mede a relação entre artefatos produzidos (requisitos, decisões, "
            "SBVR, BPMN — ponderados pelo tipo da reunião) e o custo estimado em tempo humano. "
            "Escala 0–10. **Verde** ≥ 7,5 · **Amarelo** ≥ 4,5 · **Laranja** ≥ 2,0 · **Vermelho** < 2,0. "
            "**Fulfillment ×10** (linha pontilhada): proporção entre o DC gerado e o mínimo esperado "
            "para o tipo — multiplicado por 10 para compartilhar o mesmo eixo."
        )

    col_trc, col_fill = st.columns(2)

    with col_trc:
        st.plotly_chart(_chart_trc(roi_data), use_container_width=True,
                        config={"displayModeBar": False})
        _cap(
            "**TRC — Taxa de Retrabalho Conceitual:** *proxy linguístico*, não rastreamento direto. "
            "Conta frases de repetição na transcrição ('de novo', 'como já disse', 'voltando ao mesmo ponto', "
            "'novamente', 'patinando' etc.) normalizadas pelo tamanho do texto. "
            "Fórmula: `(contagem / (palavras/500)) × 20`. "
            "**Interpretação:** valores altos sugerem discussões circulares ou dificuldade de fechar decisões — "
            "verifique se o calendário e a pauta estão sendo respeitados. "
            "Valores baixos indicam objetividade, mas podem refletir transcrições curtas."
        )

    with col_fill:
        st.plotly_chart(_chart_fulfillment_bar(roi_data), use_container_width=True,
                        config={"displayModeBar": False})
        _cap(
            "**Fulfillment por Reunião:** mede quanto do conjunto mínimo de artefatos esperado "
            "para o tipo de reunião foi efetivamente gerado. "
            "Ex.: uma reunião de *Levantamento de Requisitos* tem min_DC = 4,5 pontos — "
            "se produziu requisitos e termos SBVR equivalentes a 3,6 pontos, "
            "seu fulfillment é 80%. "
            "**100%** = entregou o esperado · **< 60%** = reunião subaproveitada para seu tipo. "
            "Se o tipo classificado não condiz com o objetivo real, o fulfillment será distorcido — "
            "reclassifique via página ROI-TR."
        )

    with st.expander("📋 Detalhes por Reunião", expanded=False):
        import pandas as pd
        rows = [{
            "Reunião":     f"R{m.meeting_number}",
            "Título":      m.title[:40] + ("…" if len(m.title) > 40 else ""),
            "Tipo":        m.type_icon + " " + m.meeting_type,
            "ROI-TR":      f"{m.roi_tr:.1f}",
            "Fulfillment": f"{m.fulfillment_score*100:.0f}%",
            "TRC":         f"{m.trc:.0f}%",
            "Requisitos":  m.n_requirements,
            "Decisões":    m.n_decisions,
            "Ações (estr.)": f"{m.n_actions_complete}/{m.n_actions_total}",
            "SBVR":        m.n_sbvr,
        } for m in roi_data]
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        _cap("Ações (estr.) = itens com responsável E prazo no texto — *heurística*, não status real.")

# ═══════════════════════════════════════════════════════════════
# Tab 2 — Artefatos
# ═══════════════════════════════════════════════════════════════
with tab_art:
    st.plotly_chart(_chart_artefacts(roi_data), use_container_width=True,
                    config={"displayModeBar": False})
    _cap(
        "**Artefatos por Reunião:** comparativo lado a lado de cada tipo de artefato produzido. "
        "Requisitos (azul) e SBVR (verde) são os mais densos em conhecimento estruturado. "
        "Ações (roxo) indicam comprometimento operacional. Decisões (âmbar) refletem governança. "
        "Reuniões com poucos artefatos em todas as dimensões têm ROI-TR naturalmente baixo."
    )

    st.plotly_chart(_chart_cumulative(roi_data), use_container_width=True,
                    config={"displayModeBar": False})
    _cap(
        "**Acúmulo de Artefatos:** evolução cumulativa ao longo do projeto. "
        "O crescimento constante indica cadência saudável. "
        "Plateaus prolongados podem indicar reuniões sem artefatos gerados ou "
        "pipeline não executado para todas as reuniões."
    )

# ═══════════════════════════════════════════════════════════════
# Tab 3 — Distribuição
# ═══════════════════════════════════════════════════════════════
with tab_dist:
    col_type, col_act = st.columns(2)

    with col_type:
        st.plotly_chart(_chart_meeting_types(roi_data), use_container_width=True,
                        config={"displayModeBar": False})
        _cap(
            "**Tipos de Reunião:** distribuição dos 11 tipos reconhecidos pelo sistema. "
            "O tipo influencia quais artefatos pesam mais no cálculo de ROI-TR e Fulfillment. "
            "Uma distribuição equilibrada indica projeto maduro. "
            "Excesso de *Híbrida* sugere que as reuniões ainda não foram classificadas — "
            "use a página **Qualidade ROI-TR** para classificar com IA."
        )

    with col_act:
        st.plotly_chart(_chart_actions_donut(roi_data), use_container_width=True,
                        config={"displayModeBar": False})
        _cap(
            "**Ações estruturadas:** *este indicador é uma heurística textual*, não rastreamento real. "
            "Conta itens de ação que contêm simultaneamente um responsável (nome próprio) "
            "e um prazo (data ou palavra-chave) na transcrição. "
            "Não reflete se as ações foram concluídas — para acompanhamento real de status, "
            "use o **Req. Tracker**."
        )

    if reqs:
        col_rtype, col_rpri = st.columns(2)
        with col_rtype:
            st.plotly_chart(_chart_reqs_by_type(reqs), use_container_width=True,
                            config={"displayModeBar": False})
            _cap(
                "**Requisitos por Tipo (IEEE 830):** distribuição das categorias de requisito. "
                "Funcionais descrevem comportamentos do sistema. Não-funcionais definem qualidade "
                "(desempenho, segurança, usabilidade). Negócio expressam objetivos organizacionais. "
                "Uma proporção saudável varia por tipo de projeto."
            )
        with col_rpri:
            st.plotly_chart(_chart_reqs_by_priority(reqs), use_container_width=True,
                            config={"displayModeBar": False})
            _cap(
                "**Requisitos por Prioridade:** excesso de Alta pode indicar falta de critério na "
                "priorização. Ausência de Alta pode indicar escopo ainda indefinido. "
                "Uma distribuição piramidal (Alta < Média < Baixa) é saudável na maioria dos projetos."
            )
    else:
        st.info("Nenhum requisito encontrado para este contexto.")

# ═══════════════════════════════════════════════════════════════
# Tab 4 — Conhecimento
# ═══════════════════════════════════════════════════════════════
with tab_know:
    ckf_text  = (ctx_info.get("skill_md") or "").strip()
    ckf_words = len(ckf_text.split()) if ckf_text else 0

    k1,k2,k3,k4 = st.columns(4)
    k1.metric("CKF",          f"{ckf_words} palavras" if ckf_text else "Vazio")
    k2.metric("Arquivos Ref.",f"{n_files}")
    k3.metric("Termos SBVR",  sbvr["terms"])
    k4.metric("Regras SBVR",  sbvr["rules"])

    st.markdown("")
    col_ckf, col_files = st.columns(2)

    with col_ckf:
        st.markdown("**Context Knowledge File**")
        if ckf_text:
            with st.expander("Visualizar CKF", expanded=False):
                st.markdown(ckf_text)
        else:
            st.warning("CKF vazio.")
            st.page_link("pages/Settings.py", label="Preencher em Configurações")

    with col_files:
        st.markdown("**Arquivos de Referência**")
        from core.project_store import list_context_files as _lf
        for f in _lf(project_id):
            sk  = (f.get("file_size") or 0) / 1024
            dt  = (f.get("uploaded_at") or "")[:10]
            st.caption(f"📄 **{f['filename']}** ({f['file_type'].upper()}, {sk:.0f} KB) — {dt}")
        if not _lf(project_id):
            st.warning("Nenhum arquivo.")
            st.page_link("pages/Settings.py", label="Adicionar em Configurações")

    st.markdown("---")
    st.markdown("**Dimensões da Saúde do Conhecimento**")
    km_cols = st.columns(3)
    for i, (k, v) in enumerate(health.get("dimensions", {}).items()):
        color = _health_color(v * 10)
        km_cols[i % 3].markdown(
            f"**{k}**  \n"
            f"<div style='background:#1e3a5f;border-radius:4px;height:8px;margin:4px 0 2px;'>"
            f"<div style='background:{color};width:{v*100:.0f}%;height:8px;border-radius:4px;'></div></div>"
            f"<span style='font-size:0.78rem;color:{color};'>{v*10:.1f}/10</span>",
            unsafe_allow_html=True,
        )

# ═══════════════════════════════════════════════════════════════
# Tab 5 — Alertas & Insights
# ═══════════════════════════════════════════════════════════════
with tab_alerts:
    _render_insights(insights)

    # ── Contradições em Requisitos ────────────────────────────────────────────
    st.markdown("")
    st.markdown("#### 📋 Contradições em Versões de Requisitos")
    st.caption(
        "Registradas quando um requisito é atualizado de forma conflitante com uma versão anterior "
        "(`requirement_versions.contradiction_flag`). São os mesmos dados exibidos no **Req. Tracker**."
    )
    if req_contra:
        for c in req_contra[:10]:
            rd  = c.get("requirements") or {}
            st.error(
                f"**REQ-{rd.get('req_number','?')} — {rd.get('title','—')}**  \n"
                f"{c.get('contradiction_detail') or c.get('change_summary') or c.get('description') or 'Sem detalhes'}"
            )
        if len(req_contra) > 10:
            st.caption(f"+ {len(req_contra)-10} adicionais — ver Req. Tracker.")
        st.page_link("pages/ValidationHub.py", label="Abrir Validação")
    else:
        st.success("Nenhuma contradição em versões de requisitos.")

    # ── Contradições no Knowledge Hub ────────────────────────────────────────
    st.markdown("")
    st.markdown("#### 🧠 Contradições no Knowledge Hub")
    st.caption(
        "Detectadas pelo `AgentContradictionDetector`: compara fatos semânticos "
        "(regras, decisões, restrições) registrados em reuniões diferentes pelo `AgentKnowledgeExtractor`. "
        "São os mesmos dados da aba *Contradições* no **Knowledge Hub**. "
        "**Estes são conceitos distintos** das contradições de requisitos acima."
    )
    if kh_contra:
        for c in kh_contra[:10]:
            with st.expander(
                f"⚡ {(c.get('description') or c.get('process_name') or 'Contradição')[:70]}…",
                expanded=False,
            ):
                if c.get('process_name'):
                    st.caption(f"**Processo:** {c['process_name']}")
                st.write(c.get('description') or '—')
                cols = st.columns(3)
                cols[0].caption(f"**Severidade:** {c.get('severity','—')}")
                cols[1].caption(f"**Tipo:** {c.get('relation_type','—')}")
                cols[2].caption(f"**Confiança:** {c.get('confidence') or '—'}")
                if c.get('clarifying_question'):
                    st.info(f"❓ {c['clarifying_question']}")
                if c.get('suggested_rewrite'):
                    st.success(f"💡 Sugestão: {c['suggested_rewrite']}")
        if len(kh_contra) > 10:
            st.caption(f"+ {len(kh_contra)-10} adicionais — ver Knowledge Hub.")
        st.page_link("pages/KnowledgeHub.py", label="Abrir Knowledge Hub")
    else:
        st.success("Nenhuma contradição semântica no Knowledge Hub.")

    # ── Tópicos Recorrentes ───────────────────────────────────────────────────
    st.markdown("")
    st.markdown("#### 🔄 Tópicos Recorrentes")
    st.caption("Temas que aparecem em múltiplas reuniões (requer embeddings nas transcrições).")
    try:
        from modules.cross_meeting_analyzer import find_recurring_topics
        with st.spinner("Analisando tópicos..."):
            topics, _method = find_recurring_topics(project_id, max_results=6)
        if topics:
            for t in topics:
                with st.expander(
                    f"{t.intensity_label} — Reuniões {t.meetings_str} — {', '.join(t.keywords[:3])}",
                    expanded=False,
                ):
                    c1, c2 = st.columns(2)
                    c1.caption(t.excerpt_a[:220])
                    c2.caption(t.excerpt_b[:220])
        else:
            st.info("Nenhum tópico recorrente detectado.")
    except Exception as _e:
        st.info(f"Análise de tópicos indisponível: {_e}")

    st.markdown("")
    if st.button("🔄 Atualizar dados", help="Limpa o cache e recarrega todos os indicadores"):
        st.cache_data.clear()
        st.rerun()
