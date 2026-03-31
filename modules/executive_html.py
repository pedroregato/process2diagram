# modules/executive_html.py
# ─────────────────────────────────────────────────────────────────────────────
# Professional executive HTML report generator.
#
# generate_executive_html(hub, narrative) → str
#   Returns a fully self-contained HTML document (no external CDN).
#   System fonts only. Print-friendly (@media print).
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import html as _html
from datetime import datetime


# ── Palette ───────────────────────────────────────────────────────────────────

_TYPE_COLOR = {
    "ui_field":       "#2563eb",
    "validation":     "#0891b2",
    "business_rule":  "#7c3aed",
    "functional":     "#0d9488",
    "non_functional": "#9333ea",
}
_TYPE_LABEL = {
    "ui_field":       "Campo de Tela",
    "validation":     "Validação",
    "business_rule":  "Regra de Negócio",
    "functional":     "Funcional",
    "non_functional": "Não Funcional",
}
_PRIO_COLOR = {
    "high":        "#dc2626",
    "medium":      "#d97706",
    "low":         "#16a34a",
    "unspecified": "#94a3b8",
}
_PRIO_LABEL = {
    "high": "Alta", "medium": "Média",
    "low": "Baixa", "unspecified": "N/D",
}
_GRADE_COLOR = {
    "A": "#16a34a", "B": "#65a30d",
    "C": "#ca8a04", "D": "#ea580c", "E": "#dc2626",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _e(s: object) -> str:
    """HTML-escape a value."""
    return _html.escape(str(s or ""))


def _nl2p(text: str) -> str:
    """Convert double-newline-separated paragraphs to <p> tags."""
    paras = [p.strip() for p in str(text or "").split("\n\n") if p.strip()]
    if not paras:
        return "<p><em>—</em></p>"
    return "".join(f"<p>{_e(p)}</p>" for p in paras)


def _badge(label: str, color: str, text_color: str = "#fff") -> str:
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:20px;'
        f'background:{color};color:{text_color};font-size:11px;font-weight:600;'
        f'letter-spacing:.03em">{_e(label)}</span>'
    )


def _section(icon: str, title: str, accent: str, body: str) -> str:
    return f"""
<div class="card">
  <div class="card-header" style="border-left:4px solid {accent}">
    <span class="card-icon" style="background:{accent}20;color:{accent}">{icon}</span>
    <span class="card-title">{_e(title)}</span>
  </div>
  <div class="card-body">{body}</div>
</div>"""


# ── CSS ───────────────────────────────────────────────────────────────────────

_CSS = """
:root{
  --navy:#0f172a;--slate:#334155;--muted:#64748b;--border:#e2e8f0;
  --bg:#f1f5f9;--white:#ffffff;--accent:#2563eb;
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Arial,sans-serif;
  background:var(--bg);color:var(--slate);line-height:1.65;font-size:14px}
a{color:var(--accent)}

/* ── Hero ── */
.hero{background:var(--navy);color:#fff;padding:44px 48px 32px;position:relative;overflow:hidden}
.hero::after{content:'';position:absolute;top:0;right:0;width:360px;height:100%;
  background:linear-gradient(135deg,transparent 30%,rgba(37,99,235,.18) 100%);pointer-events:none}
.hero-badge{display:inline-flex;align-items:center;gap:6px;
  background:rgba(37,99,235,.22);border:1px solid rgba(37,99,235,.4);
  color:#93c5fd;padding:4px 14px;border-radius:20px;font-size:11px;font-weight:700;
  text-transform:uppercase;letter-spacing:.09em;margin-bottom:18px}
.hero h1{font-size:26px;font-weight:700;letter-spacing:-.02em;line-height:1.2;margin-bottom:6px}
.hero-meta{color:#94a3b8;font-size:13px;margin-bottom:28px}
.stats{display:flex;gap:0;margin-top:28px;padding-top:24px;border-top:1px solid rgba(255,255,255,.1)}
.stat{flex:1;text-align:center;padding:0 16px;border-right:1px solid rgba(255,255,255,.1)}
.stat:last-child{border-right:none}
.stat-val{font-size:26px;font-weight:700;color:#fff;line-height:1}
.stat-lbl{font-size:10px;color:#94a3b8;text-transform:uppercase;letter-spacing:.07em;margin-top:4px}

/* ── Cards ── */
.page{max-width:960px;margin:0 auto;padding:0 0 60px}
.card{background:var(--white);margin:20px 24px 0;border-radius:12px;
  box-shadow:0 1px 3px rgba(0,0,0,.07),0 1px 2px rgba(0,0,0,.05);overflow:hidden}
.card-header{padding:18px 28px;display:flex;align-items:center;gap:12px;
  border-bottom:1px solid var(--border)}
.card-icon{width:34px;height:34px;border-radius:8px;display:flex;align-items:center;
  justify-content:center;font-size:16px;flex-shrink:0}
.card-title{font-size:15px;font-weight:700;color:var(--navy)}
.card-body{padding:24px 28px}
.card-body p{margin-bottom:12px;color:var(--slate)}
.card-body p:last-child{margin-bottom:0}

/* ── Two-column layout ── */
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.col-label{font-size:12px;font-weight:700;text-transform:uppercase;
  letter-spacing:.07em;color:var(--muted);margin-bottom:10px}

/* ── Tables ── */
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:var(--navy);color:#fff;padding:10px 14px;text-align:left;font-weight:600;font-size:12px}
td{padding:9px 14px;border-bottom:1px solid var(--border);vertical-align:top}
tr:last-child td{border-bottom:none}
tr:nth-child(even) td{background:#f8fafc}
tr:hover td{background:#f0f9ff}

/* ── Lists ── */
ol.insights{padding-left:0;list-style:none}
ol.insights li{position:relative;padding:10px 14px 10px 44px;
  border-bottom:1px solid var(--border);font-size:13px;color:var(--slate)}
ol.insights li:last-child{border-bottom:none}
ol.insights li::before{content:counter(item);counter-increment:item;
  position:absolute;left:12px;top:50%;transform:translateY(-50%);
  width:22px;height:22px;border-radius:50%;background:var(--accent);color:#fff;
  display:flex;align-items:center;justify-content:center;
  font-size:11px;font-weight:700;line-height:1}
ol.insights{counter-reset:item}

/* ── Participants ── */
.chips{display:flex;flex-wrap:wrap;gap:8px;padding:4px 0}
.chip{background:#f1f5f9;border:1px solid var(--border);border-radius:20px;
  padding:4px 12px;font-size:12px;font-weight:600;color:var(--slate)}

/* ── Progress bars ── */
.bar-wrap{display:flex;align-items:center;gap:10px;margin:6px 0}
.bar-label{width:130px;font-size:12px;color:var(--slate);flex-shrink:0}
.bar-track{flex:1;height:8px;background:var(--border);border-radius:4px;overflow:hidden}
.bar-fill{height:100%;border-radius:4px}
.bar-count{font-size:12px;color:var(--muted);min-width:28px;text-align:right}

/* ── Quality block ── */
.quality-grid{display:flex;gap:16px;align-items:flex-start}
.grade-badge{font-size:48px;font-weight:800;line-height:1;padding:8px 20px;
  border-radius:12px;color:#fff;flex-shrink:0}
.quality-detail{flex:1}
.quality-score{font-size:22px;font-weight:700;margin-bottom:4px}
.quality-rec{font-size:13px;color:var(--slate);margin-top:8px}
.crit-bar{margin:6px 0}
.crit-name{font-size:12px;color:var(--muted);margin-bottom:2px}
.crit-track{height:6px;background:var(--border);border-radius:3px;overflow:hidden}
.crit-fill{height:100%;background:var(--accent);border-radius:3px}

/* ── Footer ── */
.footer{margin:36px 24px 0;padding:20px 28px;background:#f8fafc;
  border-top:2px solid var(--border);border-radius:12px;
  display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
.footer-brand{font-size:13px;font-weight:700;color:var(--navy)}
.footer-meta{font-size:12px;color:var(--muted)}

/* ── Print ── */
@media print{
  body{background:#fff;font-size:11pt}
  .hero{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .card{break-inside:avoid;box-shadow:none;border:1px solid var(--border)}
  .footer .no-print{display:none}
}
"""


# ── Section builders ──────────────────────────────────────────────────────────

def _hero(hub, narrative) -> str:
    title = (getattr(hub.minutes, "title", "") or hub.bpmn.name or "Relatório Executivo")
    date_str = getattr(hub.minutes, "date", "") or datetime.now().strftime("%d/%m/%Y")
    provider = getattr(hub.meta, "llm_provider", "")
    generated = datetime.now().strftime("%d/%m/%Y às %H:%M")

    n_steps    = len(hub.bpmn.steps) if hub.bpmn.ready else "—"
    n_parts    = len(hub.minutes.participants) if hub.minutes.ready else "—"
    n_reqs     = len(hub.requirements.requirements) if hub.requirements.ready else "—"
    n_actions  = len(hub.minutes.action_items) if hub.minutes.ready else "—"

    grade = getattr(hub.transcript_quality, "grade", "")
    score = getattr(hub.transcript_quality, "overall_score", 0)
    g_color = _GRADE_COLOR.get(grade, "#94a3b8")
    grade_pill = (
        f'<span style="margin-left:12px;background:{g_color};color:#fff;'
        f'padding:3px 12px;border-radius:20px;font-size:12px;font-weight:700">'
        f'Qualidade {_e(grade)} &nbsp;{score:.0f}/100</span>'
        if grade else ""
    )

    return f"""
<div class="hero">
  <div class="hero-badge">&#9881; Relatório Executivo</div>
  <h1>{_e(title)}</h1>
  <div class="hero-meta">
    {_e(date_str)}{grade_pill}
    &ensp;·&ensp; Gerado em {_e(generated)}
    {f'&ensp;·&ensp; {_e(provider)}' if provider else ''}
  </div>
  <div class="stats">
    <div class="stat"><div class="stat-val">{n_steps}</div><div class="stat-lbl">Etapas&nbsp;BPMN</div></div>
    <div class="stat"><div class="stat-val">{n_parts}</div><div class="stat-lbl">Participantes</div></div>
    <div class="stat"><div class="stat-val">{n_reqs}</div><div class="stat-lbl">Requisitos</div></div>
    <div class="stat"><div class="stat-val">{n_actions}</div><div class="stat-lbl">Action&nbsp;Items</div></div>
  </div>
</div>"""


def _section_summary(narrative) -> str:
    body = _nl2p(narrative.executive_summary)
    return _section("📋", "Sumário Executivo", "#2563eb", body)


def _section_process(hub, narrative) -> str:
    if not hub.bpmn.ready:
        return ""
    rows = []
    for s in hub.bpmn.steps:
        task_label = {
            "userTask": "Usuário", "serviceTask": "Sistema",
            "businessRuleTask": "Regra", "scriptTask": "Script",
        }.get(getattr(s, "task_type", "userTask"), "Usuário")
        dec_icon = "⟡" if s.is_decision else ""
        rows.append(
            f"<tr><td><strong>{_e(s.id)}</strong></td>"
            f"<td>{_e(s.title)} {dec_icon}</td>"
            f"<td>{_e(s.lane or '—')}</td>"
            f"<td><span style='font-size:11px;color:#64748b'>{_e(task_label)}</span></td></tr>"
        )
    lanes_html = ""
    if hub.bpmn.lanes:
        chips = "".join(
            f'<span class="chip">{_e(l)}</span>' for l in hub.bpmn.lanes
        )
        lanes_html = f'<div class="col-label">Swimlanes</div><div class="chips" style="margin-bottom:18px">{chips}</div>'

    n_dec = sum(1 for s in hub.bpmn.steps if s.is_decision)
    narrative_html = f'<div style="margin-bottom:18px">{_nl2p(narrative.process_narrative)}</div>'

    body = f"""
{narrative_html}
{lanes_html}
<div class="col-label" style="margin-bottom:8px">
  {len(hub.bpmn.steps)} etapas &nbsp;·&nbsp; {n_dec} decisões (⟡)
</div>
<table>
  <thead><tr><th>ID</th><th>Etapa</th><th>Lane</th><th>Tipo</th></tr></thead>
  <tbody>{"".join(rows)}</tbody>
</table>"""
    return _section("⚙️", "Visão do Processo", "#7c3aed", body)


def _section_minutes(hub) -> str:
    if not hub.minutes.ready:
        return ""
    m = hub.minutes

    # Participants
    chips = "".join(f'<span class="chip">{_e(p)}</span>' for p in m.participants)
    parts_html = f'<div class="col-label">Participantes</div><div class="chips" style="margin-bottom:18px">{chips}</div>' if chips else ""

    # Decisions
    dec_items = "".join(f"<li style='margin:5px 0'>{_e(d)}</li>" for d in m.decisions)
    dec_html = (
        f'<div class="col-label" style="margin-bottom:6px">Decisões</div>'
        f'<ul style="padding-left:20px;margin-bottom:18px">{dec_items}</ul>'
    ) if dec_items else ""

    # Action items table
    ai_rows = []
    prio_icons = {"high": "🔴", "normal": "🟡", "low": "🟢"}
    for ai in m.action_items:
        icon = prio_icons.get(ai.priority, "⚪")
        raised = _e(ai.raised_by or "—")
        ai_rows.append(
            f"<tr><td style='text-align:center'>{icon}</td>"
            f"<td>{raised}</td>"
            f"<td>{_e(ai.task)}</td>"
            f"<td><strong>{_e(ai.responsible)}</strong></td>"
            f"<td>{_e(ai.deadline or '—')}</td></tr>"
        )
    ai_table = ""
    if ai_rows:
        ai_table = (
            f'<div class="col-label" style="margin-bottom:8px">Action Items ({len(m.action_items)})</div>'
            f'<table><thead><tr><th>P</th><th>Por</th><th>Tarefa</th><th>Responsável</th><th>Prazo</th></tr></thead>'
            f'<tbody>{"".join(ai_rows)}</tbody></table>'
        )

    body = parts_html + dec_html + ai_table
    return _section("📝", "Ata de Reunião", "#0891b2", body)


def _section_requirements(hub) -> str:
    if not hub.requirements.ready or not hub.requirements.requirements:
        return ""
    reqs = hub.requirements.requirements

    from collections import Counter
    type_counts = Counter(r.type for r in reqs)
    total = len(reqs)

    # Distribution bars
    bars = []
    for t_key in _TYPE_LABEL:
        cnt = type_counts.get(t_key, 0)
        if cnt == 0:
            continue
        pct = int(cnt / total * 100)
        color = _TYPE_COLOR.get(t_key, "#64748b")
        bars.append(
            f'<div class="bar-wrap">'
            f'<div class="bar-label">{_e(_TYPE_LABEL[t_key])}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{color}"></div></div>'
            f'<div class="bar-count">{cnt}</div></div>'
        )

    # Requirements table
    req_rows = []
    for r in sorted(reqs, key=lambda x: (x.type, {"high": 0, "medium": 1, "low": 2}.get(x.priority, 3))):
        t_color = _TYPE_COLOR.get(r.type, "#64748b")
        t_label = _TYPE_LABEL.get(r.type, r.type)
        p_color = _PRIO_COLOR.get(r.priority, "#94a3b8")
        p_label = _PRIO_LABEL.get(r.priority, "N/D")
        req_rows.append(
            f"<tr>"
            f"<td><strong style='font-family:monospace'>{_e(r.id)}</strong></td>"
            f"<td>{_badge(t_label, t_color)}</td>"
            f"<td><span style='color:{p_color};font-weight:700'>{_e(p_label)}</span></td>"
            f"<td>{_e(r.title)}</td>"
            f"<td>{_e(r.actor or '—')}</td>"
            f"</tr>"
        )

    high_count = type_counts.get("high", sum(1 for r in reqs if r.priority == "high"))
    body = f"""
<div style="margin-bottom:18px">
  <span style="font-size:24px;font-weight:700;color:var(--navy)">{total}</span>
  <span style="color:var(--muted);margin-left:6px">requisitos &nbsp;·&nbsp;</span>
  <span style="font-weight:700;color:#dc2626">{sum(1 for r in reqs if r.priority=='high')} alta prioridade</span>
</div>
<div style="margin-bottom:20px">{"".join(bars)}</div>
<table>
  <thead><tr><th>ID</th><th>Tipo</th><th>Prioridade</th><th>Título</th><th>Ator</th></tr></thead>
  <tbody>{"".join(req_rows)}</tbody>
</table>"""
    return _section("📊", "Especificação de Requisitos", "#0d9488", body)


def _section_quality(hub) -> str:
    if not hub.transcript_quality.ready:
        return ""
    tq = hub.transcript_quality
    g_color = _GRADE_COLOR.get(tq.grade, "#94a3b8")

    crit_html = ""
    for c in tq.criteria[:6]:
        crit_html += (
            f'<div class="crit-bar"><div class="crit-name">{_e(c.criterion)} — {c.score}/100</div>'
            f'<div class="crit-track"><div class="crit-fill" style="width:{c.score}%"></div></div></div>'
        )

    body = f"""
<div class="quality-grid">
  <div class="grade-badge" style="background:{g_color}">{_e(tq.grade)}</div>
  <div class="quality-detail">
    <div class="quality-score" style="color:{g_color}">{tq.overall_score:.1f} / 100</div>
    <div style="color:var(--muted);font-size:12px;margin-bottom:10px">Nota ponderada da transcrição ASR</div>
    {crit_html}
    <div class="quality-rec" style="margin-top:12px">{_e(tq.recommendation)}</div>
  </div>
</div>"""
    return _section("🔬", "Qualidade da Transcrição", "#64748b", body)


def _section_insights(narrative) -> str:
    insights = narrative.key_insights or []
    recs = narrative.recommendations or []

    def _ol(items):
        if not items:
            return "<p><em>—</em></p>"
        lis = "".join(f"<li>{_e(item)}</li>" for item in items)
        return f'<ol class="insights">{lis}</ol>'

    body = f"""
<div class="two-col">
  <div>
    <div class="col-label" style="margin-bottom:10px">Insights Identificados</div>
    {_ol(insights)}
  </div>
  <div>
    <div class="col-label" style="margin-bottom:10px">Recomendações</div>
    {_ol(recs)}
  </div>
</div>"""
    return _section("💡", "Insights e Recomendações", "#d97706", body)


def _footer(hub) -> str:
    session_id = getattr(hub.meta, "session_id", "")[:8]
    generated = datetime.now().strftime("%d/%m/%Y às %H:%M")
    return f"""
<div class="footer">
  <div>
    <div class="footer-brand">&#9881; Process2Diagram</div>
    <div class="footer-meta">Relatório gerado automaticamente por agentes LLM</div>
  </div>
  <div style="text-align:right">
    <div class="footer-meta">Sessão <code>{_e(session_id)}</code></div>
    <div class="footer-meta">{_e(generated)}</div>
  </div>
</div>"""


# ── Public entry point ────────────────────────────────────────────────────────

def generate_executive_html(hub, narrative) -> str:
    """
    Generate a self-contained professional executive HTML report.

    Args:
        hub:       Fully (or partially) populated KnowledgeHub.
        narrative: SynthesizerModel with executive_summary, process_narrative,
                   key_insights, recommendations filled by the LLM.

    Returns:
        A complete HTML string — ready for download or components.html().
    """
    process_name = (
        getattr(hub.minutes, "title", "")
        or hub.bpmn.name
        or "Relatório Executivo"
    )

    sections = "\n".join(filter(None, [
        _section_summary(narrative),
        _section_process(hub, narrative),
        _section_minutes(hub),
        _section_requirements(hub),
        _section_quality(hub),
        _section_insights(narrative),
    ]))

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Relatório Executivo — {_e(process_name)}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="page">
{_hero(hub, narrative)}
{sections}
{_footer(hub)}
</div>
</body>
</html>"""
