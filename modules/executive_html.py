# modules/executive_html.py
# ─────────────────────────────────────────────────────────────────────────────
# Professional executive HTML report generator.
#
# generate_executive_html(hub, narrative) → str
#   Returns a fully self-contained HTML document.
#   Google Fonts (DM Serif Display / DM Sans / JetBrains Mono) via CDN.
#   Print-friendly (@media print). Sidebar nav. Scroll animations.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import base64
import html as _html
import re as _re
import urllib.request
from datetime import datetime


# ── Palette ───────────────────────────────────────────────────────────────────

_TYPE_COLOR = {
    "ui_field":       "#2E7FD9",
    "validation":     "#0891b2",
    "business_rule":  "#6B3FA0",
    "functional":     "#1A7F5A",
    "non_functional": "#C97B1A",
}
_TYPE_LABEL = {
    "ui_field":       "Campo de Tela",
    "validation":     "Validação",
    "business_rule":  "Regra de Negócio",
    "functional":     "Funcional",
    "non_functional": "Não Funcional",
}
_TYPE_BG = {
    "ui_field":       "#EEF4FC",
    "validation":     "#E0F5FA",
    "business_rule":  "#F0E8FA",
    "functional":     "#E3F5ED",
    "non_functional": "#FEF3E2",
}
_PRIO_COLOR  = {"high": "#C97B1A", "medium": "#2E7FD9", "low": "#1A7F5A", "unspecified": "#8496B0"}
_PRIO_BG     = {"high": "#FEF3E2", "medium": "#EEF4FC", "low": "#E3F5ED", "unspecified": "#F4F7FB"}
_PRIO_BORDER = {"high": "#F5D9A0", "medium": "#C8DBEE", "low": "#9FD9BC", "unspecified": "#D5E3F5"}
_PRIO_LABEL  = {"high": "Alta",    "medium": "Média",   "low": "Baixa",   "unspecified": "N/D"}
_GRADE_COLOR = {"A": "#1A7F5A", "B": "#65a30d", "C": "#C97B1A", "D": "#C05621", "E": "#C0392B"}
_GRADE_BG    = {"A": "#E3F5ED", "B": "#f0fdf4", "C": "#FEF3E2", "D": "#FDE8D8", "E": "#FDE8E4"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _e(s: object) -> str:
    return _html.escape(str(s or ""))


def _nl2p(text: str) -> str:
    paras = [p.strip() for p in str(text or "").split("\n\n") if p.strip()]
    if not paras:
        return "<p><em>—</em></p>"
    return "".join(f"<p>{_e(p)}</p>" for p in paras)


def _initials(name: str) -> str:
    """Extract up to 2 uppercase initials from a name."""
    parts = name.strip().split()
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def _status_pill(priority: str) -> str:
    color  = _PRIO_COLOR.get(priority, "#8496B0")
    bg     = _PRIO_BG.get(priority, "#F4F7FB")
    border = _PRIO_BORDER.get(priority, "#D5E3F5")
    label  = _PRIO_LABEL.get(priority, "N/D")
    return (
        f'<span style="display:inline-flex;align-items:center;gap:5px;'
        f'font-size:11px;font-weight:500;padding:3px 9px;border-radius:100px;'
        f'background:{bg};color:{color};border:1px solid {border};white-space:nowrap">'
        f'<span style="width:5px;height:5px;border-radius:50%;'
        f'background:{color};flex-shrink:0;display:inline-block"></span>'
        f'{_e(label)}</span>'
    )


def _type_badge(t_key: str) -> str:
    color  = _TYPE_COLOR.get(t_key, "#8496B0")
    bg     = _TYPE_BG.get(t_key, "#F4F7FB")
    label  = _TYPE_LABEL.get(t_key, t_key)
    return (
        f'<span style="display:inline-block;font-size:11px;font-weight:500;'
        f'padding:3px 9px;border-radius:100px;background:{bg};color:{color};'
        f'border:1px solid {color}33">{_e(label)}</span>'
    )


def _section_card(icon: str, title: str, body: str, sec_id: str = "") -> str:
    id_attr = f' id="{sec_id}"' if sec_id else ""
    return f"""
<section class="section card"{id_attr}>
  <div class="card-header">
    <div class="section-icon">{icon}</div>
    <h2 class="section-title">{_e(title)}</h2>
  </div>
  <div class="card-body">{body}</div>
</section>"""


# ── CSS ───────────────────────────────────────────────────────────────────────

_CSS = """
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&family=JetBrains+Mono:wght@400;500&display=swap');

:root{
  --navy:#0B1E3D; --blue:#1A4B8C; --accent:#2E7FD9; --gold:#C9A84C;
  --light:#F4F7FB; --muted:#8496B0; --border:#D5E3F5; --white:#FFFFFF;
  --text:#1C2A3A; --green:#1A7F5A; --amber:#C97B1A; --purple:#6B3FA0;
  --sidebar-w:220px;
}

*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth}
body{font-family:'DM Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  background:var(--light);color:var(--text);line-height:1.6;font-size:14px}

/* ── Sidebar ── */
#sidebar{
  position:fixed;top:0;left:0;bottom:0;width:var(--sidebar-w);
  background:var(--navy);overflow-y:auto;z-index:200;padding:28px 0 28px;
}
.sb-brand{
  display:flex;align-items:center;gap:8px;
  padding:0 20px 24px;border-bottom:1px solid rgba(255,255,255,.08);
  margin-bottom:20px;
}
.sb-brand-icon{
  width:30px;height:30px;border-radius:8px;background:var(--accent);
  display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0
}
.sb-brand-text{font-size:12px;font-weight:600;color:rgba(255,255,255,.9);line-height:1.3}
.sb-brand-sub{font-size:10px;color:rgba(255,255,255,.4);font-weight:400}

.sb-section{padding:0 12px;margin-bottom:4px}
.sb-label{
  font-size:9px;letter-spacing:.12em;text-transform:uppercase;
  color:rgba(255,255,255,.3);padding:0 8px;margin-bottom:6px;display:block
}
.sb-link{
  display:flex;align-items:center;gap:9px;padding:8px 10px;border-radius:8px;
  text-decoration:none;color:rgba(255,255,255,.6);font-size:12.5px;
  transition:all .15s;margin-bottom:2px
}
.sb-link:hover{background:rgba(255,255,255,.07);color:rgba(255,255,255,.95)}
.sb-link .sb-ic{font-size:14px;flex-shrink:0}
.sb-link.active{background:rgba(46,127,217,.2);color:#93c5fd}

/* ── Main ── */
#main{margin-left:var(--sidebar-w)}

/* ── Hero ── */
.hero{
  background:linear-gradient(135deg,var(--navy) 0%,var(--blue) 100%);
  position:relative;overflow:hidden;padding:52px 56px 44px;
}
.hero::before{
  content:'';position:absolute;top:-80px;right:-80px;
  width:360px;height:360px;border-radius:50%;
  background:radial-gradient(circle,rgba(46,127,217,.28) 0%,transparent 70%)
}
.hero::after{
  content:'';position:absolute;bottom:-60px;left:-60px;
  width:240px;height:240px;border-radius:50%;
  background:radial-gradient(circle,rgba(201,168,76,.13) 0%,transparent 70%)
}
.hero-badges{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:20px;position:relative;z-index:1}
.hero-badge{
  font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:.08em;
  padding:4px 12px;border-radius:5px;
  background:rgba(255,255,255,.1);color:rgba(255,255,255,.75);
  border:1px solid rgba(255,255,255,.15)
}
.hero-badge.gold{
  background:rgba(201,168,76,.18);color:var(--gold);border-color:rgba(201,168,76,.35)
}
.hero h1{
  font-family:'DM Serif Display',Georgia,serif;
  font-size:clamp(24px,3.2vw,38px);font-weight:400;letter-spacing:-.01em;
  color:#fff;line-height:1.2;margin-bottom:10px;position:relative;z-index:1
}
.hero-sub{
  font-size:14px;color:rgba(255,255,255,.55);margin-bottom:32px;
  position:relative;z-index:1
}
.hero-cards{
  display:flex;flex-wrap:wrap;gap:12px;position:relative;z-index:1
}
.hero-card{
  background:rgba(255,255,255,.07);backdrop-filter:blur(6px);
  border:1px solid rgba(255,255,255,.12);border-radius:10px;
  padding:12px 18px;min-width:140px
}
.hero-card-label{
  font-size:9px;letter-spacing:.12em;text-transform:uppercase;
  color:rgba(255,255,255,.4);margin-bottom:4px
}
.hero-card-value{font-size:13px;font-weight:500;color:rgba(255,255,255,.9)}

/* ── Participants strip ── */
.participants-strip{
  background:var(--white);padding:16px 56px;display:flex;
  align-items:center;flex-wrap:wrap;gap:8px;
  border-bottom:2px solid var(--border);
}
.strip-label{
  font-size:10px;letter-spacing:.1em;text-transform:uppercase;
  color:var(--muted);font-weight:600;margin-right:4px;white-space:nowrap
}
.p-chip{
  display:inline-flex;align-items:center;gap:7px;
  background:var(--light);border:1px solid var(--border);
  border-radius:100px;padding:4px 12px 4px 5px;
  font-size:12.5px;color:var(--text)
}
.p-avatar{
  width:24px;height:24px;border-radius:50%;background:var(--navy);
  display:flex;align-items:center;justify-content:center;
  font-family:'JetBrains Mono',monospace;
  font-size:9px;font-weight:500;color:#fff;flex-shrink:0
}

/* ── Stats bar ── */
.stats-bar{
  display:flex;gap:0;background:var(--white);
  border-bottom:1px solid var(--border);
}
.stat{
  flex:1;text-align:center;padding:18px 12px;
  border-right:1px solid var(--border)
}
.stat:last-child{border-right:none}
.stat-val{
  font-family:'DM Serif Display',serif;font-size:28px;color:var(--navy);line-height:1
}
.stat-lbl{
  font-size:10px;text-transform:uppercase;letter-spacing:.08em;
  color:var(--muted);margin-top:4px
}

/* ── Content ── */
.content{max-width:960px;margin:0 auto;padding:0 0 60px}

/* ── Section cards ── */
.card{
  background:var(--white);margin:24px 24px 0;border-radius:14px;
  border:1px solid var(--border);
  box-shadow:0 1px 3px rgba(11,30,61,.05);
  opacity:0;transform:translateY(16px);
  transition:opacity .5s ease,transform .5s ease,box-shadow .2s
}
.card.visible{opacity:1;transform:translateY(0)}
.card:hover{box-shadow:0 4px 24px rgba(11,30,61,.08)}
.card-header{
  padding:20px 28px;display:flex;align-items:center;gap:14px;
  border-bottom:2px solid var(--border)
}
.section-icon{
  width:38px;height:38px;border-radius:10px;background:var(--navy);
  display:flex;align-items:center;justify-content:center;
  font-size:18px;flex-shrink:0
}
.section-title{
  font-family:'DM Serif Display',serif;
  font-size:20px;font-weight:400;color:var(--navy)
}
.card-body{padding:24px 28px}
.card-body p{margin-bottom:12px;color:var(--text);font-size:13.5px;line-height:1.65}
.card-body p:last-child{margin-bottom:0}

/* ── Tables ── */
table{width:100%;border-collapse:collapse;font-size:13px}
thead{background:var(--light)}
th{
  padding:10px 16px;text-align:left;font-size:11px;font-weight:600;
  letter-spacing:.08em;text-transform:uppercase;color:var(--muted);white-space:nowrap
}
td{
  padding:11px 16px;border-top:1px solid var(--border);
  vertical-align:middle;color:var(--text);line-height:1.55
}
tbody tr{transition:background .15s}
tbody tr:hover td{background:#f8fafd}

/* ── Chips / badges ── */
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{
  background:var(--light);border:1px solid var(--border);
  border-radius:6px;padding:4px 10px;font-size:12px;color:var(--text)
}

/* ── Two-column ── */
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:24px}
.col-label{
  font-size:10px;font-weight:600;text-transform:uppercase;
  letter-spacing:.1em;color:var(--muted);margin-bottom:10px
}

/* ── Numbered list ── */
ol.items{counter-reset:item;padding:0;list-style:none}
ol.items li{
  position:relative;padding:10px 14px 10px 46px;
  border-top:1px solid var(--border);
  font-size:13.5px;color:var(--text);line-height:1.6;counter-increment:item
}
ol.items li:first-child{border-top:none}
ol.items li::before{
  content:counter(item,'0'counter(item));
  position:absolute;left:14px;top:50%;transform:translateY(-50%);
  font-family:'JetBrains Mono',monospace;font-size:10px;font-weight:500;
  background:var(--accent);color:#fff;
  padding:2px 6px;border-radius:5px;line-height:1.4
}

/* ── Progress bars ── */
.bar-wrap{display:flex;align-items:center;gap:10px;margin:6px 0}
.bar-label{width:140px;font-size:12px;color:var(--text);flex-shrink:0}
.bar-track{flex:1;height:7px;background:var(--border);border-radius:4px;overflow:hidden}
.bar-fill{height:100%;border-radius:4px;transition:width .6s ease}
.bar-count{
  font-family:'JetBrains Mono',monospace;font-size:11px;
  color:var(--muted);min-width:26px;text-align:right
}

/* ── Quality block ── */
.quality-grid{display:flex;gap:20px;align-items:flex-start}
.grade-badge{
  font-family:'DM Serif Display',serif;font-size:52px;font-weight:400;
  line-height:1;padding:10px 22px;border-radius:14px;flex-shrink:0
}
.crit-bar{margin:7px 0}
.crit-name{font-size:12px;color:var(--muted);margin-bottom:3px}
.crit-track{height:6px;background:var(--border);border-radius:3px;overflow:hidden}
.crit-fill{height:100%;background:var(--accent);border-radius:3px}

/* ── Next meeting card ── */
.next-meeting{
  background:linear-gradient(135deg,var(--navy) 0%,var(--blue) 100%);
  border-radius:14px;padding:28px 32px;
  display:flex;align-items:center;gap:24px;
  position:relative;overflow:hidden;margin:24px 24px 0
}
.next-meeting::before{
  content:'';position:absolute;right:-40px;top:-40px;
  width:180px;height:180px;border-radius:50%;
  background:rgba(255,255,255,.04);pointer-events:none
}
.nm-icon{font-size:38px;flex-shrink:0}
.nm-label{
  font-size:10px;letter-spacing:.15em;text-transform:uppercase;
  color:var(--gold);margin-bottom:6px
}
.nm-date{
  font-family:'DM Serif Display',serif;font-size:22px;color:#fff;margin-bottom:4px
}
.nm-detail{font-size:13px;color:rgba(255,255,255,.55)}

/* ── Scroll to top ── */
#scrollTop{
  position:fixed;bottom:28px;right:28px;
  width:40px;height:40px;border-radius:10px;
  background:var(--navy);border:none;cursor:pointer;
  display:flex;align-items:center;justify-content:center;
  font-size:18px;color:#fff;
  opacity:0;pointer-events:none;transition:opacity .25s;z-index:300
}
#scrollTop.show{opacity:1;pointer-events:all}
#scrollTop:hover{background:var(--blue)}

/* ── Footer ── */
.page-footer{
  margin:36px 24px 0;padding:20px 28px;background:var(--white);
  border-top:2px solid var(--border);border-radius:14px;
  display:flex;justify-content:space-between;align-items:center;
  flex-wrap:wrap;gap:8px
}
.footer-brand{
  font-family:'DM Serif Display',serif;font-size:16px;color:var(--navy)
}
.footer-meta{font-size:12px;color:var(--muted)}

/* ── Diagram containers ── */
.diagram-wrap{
  border:1px solid var(--border);border-radius:10px;overflow:hidden
}
.diagram-caption{
  font-size:11px;color:var(--muted);margin-top:8px;font-style:italic
}

/* ── Print ── */
@media print{
  #sidebar,#scrollTop{display:none!important}
  #main{margin-left:0!important}
  body{background:#fff;font-size:11pt}
  .card{break-inside:avoid;box-shadow:none;opacity:1!important;transform:none!important}
  .hero{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  .next-meeting{-webkit-print-color-adjust:exact;print-color-adjust:exact}
}

/* ── Responsive ── */
@media(max-width:820px){
  #sidebar{display:none}
  #main{margin-left:0}
  .hero{padding:36px 24px 32px}
  .participants-strip{padding:14px 24px}
  .stats-bar .stat-val{font-size:22px}
  .two-col{grid-template-columns:1fr}
  .content{padding:0 0 40px}
  .card,.next-meeting,.page-footer{margin-left:12px;margin-right:12px}
}
"""


# ── JavaScript ────────────────────────────────────────────────────────────────

_JS = """
// ── Intersection Observer — fade-in sections ──────────────────────────────
const io = new IntersectionObserver(
  entries => entries.forEach(e => { if(e.isIntersecting) e.target.classList.add('visible'); }),
  { threshold: 0.06 }
);
document.querySelectorAll('.card').forEach(el => io.observe(el));

// ── Scroll to top ─────────────────────────────────────────────────────────
const scrollBtn = document.getElementById('scrollTop');
window.addEventListener('scroll', () => {
  scrollBtn.classList.toggle('show', window.scrollY > 400);
}, { passive: true });
scrollBtn.addEventListener('click', () => window.scrollTo({ top: 0, behavior: 'smooth' }));

// ── Sidebar active link on scroll ─────────────────────────────────────────
const sections = document.querySelectorAll('section.card[id]');
const sbLinks  = document.querySelectorAll('.sb-link[href^="#"]');
const ioSb = new IntersectionObserver(entries => {
  entries.forEach(e => {
    if (e.isIntersecting) {
      sbLinks.forEach(l => l.classList.remove('active'));
      const match = document.querySelector(`.sb-link[href="#${e.target.id}"]`);
      if (match) match.classList.add('active');
    }
  });
}, { rootMargin: '-30% 0px -60% 0px' });
sections.forEach(s => ioSb.observe(s));
"""


# ── Section builders ──────────────────────────────────────────────────────────

def _sidebar(hub, narrative) -> str:
    links = []
    links.append(('📋', 'Sumário Executivo', 'sec-summary'))
    if hub.bpmn.ready:
        links.append(('⚙️', 'Visão do Processo', 'sec-process'))
        if hub.bpmn.bpmn_xml:
            links.append(('📐', 'Diagrama BPMN', 'sec-bpmn'))
        if hub.bpmn.mermaid:
            links.append(('📊', 'Fluxograma', 'sec-mermaid'))
    if hub.minutes.ready:
        links.append(('📝', 'Ata de Reunião', 'sec-minutes'))
    if hub.requirements.ready and hub.requirements.requirements:
        links.append(('📋', 'Requisitos', 'sec-reqs'))
    if hub.transcript_quality.ready:
        links.append(('🔬', 'Qualidade', 'sec-quality'))
    links.append(('💡', 'Insights', 'sec-insights'))

    items = "\n".join(
        f'<a class="sb-link" href="#{sid}"><span class="sb-ic">{ic}</span>{_e(label)}</a>'
        for ic, label, sid in links
    )
    process_name = (getattr(hub.minutes, "title", "") or hub.bpmn.name or "Relatório")
    short_name = process_name[:28] + "…" if len(process_name) > 28 else process_name

    return f"""
<nav id="sidebar">
  <div class="sb-brand">
    <div class="sb-brand-icon">⚙</div>
    <div>
      <div class="sb-brand-text">Process2Diagram</div>
      <div class="sb-brand-sub">Relatório Executivo</div>
    </div>
  </div>
  <div class="sb-section">
    <span class="sb-label">Navegação</span>
    {items}
  </div>
</nav>"""


def _hero(hub, narrative) -> str:
    title    = (getattr(hub.minutes, "title", "") or hub.bpmn.name or "Relatório Executivo")
    date_str = getattr(hub.minutes, "date", "")  or datetime.now().strftime("%d/%m/%Y")
    location = getattr(hub.minutes, "location", "") or ""
    provider = getattr(hub.meta, "llm_provider", "")
    generated = datetime.now().strftime("%d/%m/%Y às %H:%M")

    grade = getattr(hub.transcript_quality, "grade", "")
    score = getattr(hub.transcript_quality, "overall_score", 0)

    badges = [f'<span class="hero-badge gold">Relatório Executivo</span>']
    if date_str:
        badges.append(f'<span class="hero-badge">{_e(date_str)}</span>')
    if location:
        badges.append(f'<span class="hero-badge">{_e(location)}</span>')
    if grade:
        g_color = _GRADE_COLOR.get(grade, "#8496B0")
        g_bg    = _GRADE_BG.get(grade, "#F4F7FB")
        badges.append(
            f'<span class="hero-badge" style="background:{g_bg}22;color:{g_color};'
            f'border-color:{g_color}44">Qualidade {_e(grade)} · {score:.0f}/100</span>'
        )

    cards = []
    if hub.bpmn.ready:
        cards.append(("Processo", hub.bpmn.name or "—"))
    if hub.minutes.ready and hub.minutes.participants:
        cards.append(("Participantes", str(len(hub.minutes.participants))))
    if hub.requirements.ready:
        cards.append(("Requisitos", str(len(hub.requirements.requirements))))
    if provider:
        cards.append(("Gerado por", provider))
    cards.append(("Data", generated))

    cards_html = "".join(
        f'<div class="hero-card"><div class="hero-card-label">{_e(k)}</div>'
        f'<div class="hero-card-value">{_e(v)}</div></div>'
        for k, v in cards
    )

    return f"""
<header class="hero">
  <div class="hero-badges">{''.join(badges)}</div>
  <h1>{_e(title)}</h1>
  <p class="hero-sub">Process2Diagram &mdash; Análise automatizada por agentes LLM</p>
  <div class="hero-cards">{cards_html}</div>
</header>"""


def _participants_strip(hub) -> str:
    if not hub.minutes.ready or not hub.minutes.participants:
        return ""
    chips = ""
    for p in hub.minutes.participants:
        ini = _initials(p)
        chips += (
            f'<div class="p-chip"><div class="p-avatar">{_e(ini)}</div>'
            f'<span>{_e(p)}</span></div>'
        )
    return f"""
<div class="participants-strip">
  <span class="strip-label">Participantes</span>
  {chips}
</div>"""


def _stats_bar(hub) -> str:
    stats = []
    if hub.bpmn.ready:
        stats.append((str(len(hub.bpmn.steps)), "Etapas BPMN"))
        n_gw = sum(1 for s in hub.bpmn.steps if s.is_decision)
        if n_gw:
            stats.append((str(n_gw), "Decisões"))
    if hub.minutes.ready:
        stats.append((str(len(hub.minutes.action_items)), "Action Items"))
    if hub.requirements.ready:
        stats.append((str(len(hub.requirements.requirements)), "Requisitos"))
        high = sum(1 for r in hub.requirements.requirements if r.priority == "high")
        if high:
            stats.append((str(high), "Alta Prioridade"))
    if not stats:
        return ""
    cells = "".join(
        f'<div class="stat"><div class="stat-val">{v}</div><div class="stat-lbl">{_e(l)}</div></div>'
        for v, l in stats
    )
    return f'<div class="stats-bar">{cells}</div>'


def _section_summary(narrative) -> str:
    body = _nl2p(narrative.executive_summary)
    return _section_card("📋", "Sumário Executivo", body, "sec-summary")


def _section_process(hub, narrative) -> str:
    if not hub.bpmn.ready:
        return ""

    narrative_html = f'<div style="margin-bottom:20px">{_nl2p(narrative.process_narrative)}</div>'

    lanes_html = ""
    if hub.bpmn.lanes:
        chips = "".join(f'<span class="chip">{_e(l)}</span>' for l in hub.bpmn.lanes)
        lanes_html = (
            f'<div class="col-label" style="margin-bottom:8px">Swimlanes</div>'
            f'<div class="chips" style="margin-bottom:20px">{chips}</div>'
        )

    rows = []
    for s in hub.bpmn.steps:
        task_label = {
            "userTask": "Usuário", "serviceTask": "Sistema",
            "businessRuleTask": "Regra", "scriptTask": "Script",
            "manualTask": "Manual", "sendTask": "Envio", "receiveTask": "Recebimento",
        }.get(getattr(s, "task_type", "userTask"), "Usuário")
        dec_icon = (
            ' <span style="font-family:JetBrains Mono,monospace;font-size:10px;'
            'background:#6B3FA022;color:#6B3FA0;padding:1px 6px;border-radius:4px">GW</span>'
            if s.is_decision else ""
        )
        rows.append(
            f"<tr>"
            f"<td><span style='font-family:JetBrains Mono,monospace;font-size:11px;"
            f"background:var(--light);padding:2px 7px;border-radius:4px'>{_e(s.id)}</span></td>"
            f"<td>{_e(s.title)}{dec_icon}</td>"
            f"<td>{_e(s.lane or '—')}</td>"
            f"<td><span style='font-size:11px;color:var(--muted)'>{_e(task_label)}</span></td>"
            f"</tr>"
        )

    n_dec = sum(1 for s in hub.bpmn.steps if s.is_decision)
    body = f"""
{narrative_html}
{lanes_html}
<div class="col-label" style="margin-bottom:8px">
  {len(hub.bpmn.steps)} etapas &nbsp;&middot;&nbsp; {n_dec} gateways de decisão
</div>
<table>
  <thead><tr><th>ID</th><th>Etapa</th><th>Lane</th><th>Tipo</th></tr></thead>
  <tbody>{"".join(rows)}</tbody>
</table>"""
    return _section_card("⚙️", "Visão do Processo", body, "sec-process")


def _section_bpmn_diagram(hub) -> str:
    if not hub.bpmn.ready or not hub.bpmn.bpmn_xml:
        return ""
    try:
        from modules.bpmn_viewer import preview_from_xml
        viewer_html = preview_from_xml(hub.bpmn.bpmn_xml)
        srcdoc_val  = _html.escape(viewer_html, quote=True)
        body = (
            f'<div class="diagram-wrap">'
            f'<iframe srcdoc="{srcdoc_val}" '
            f'style="width:100%;height:540px;border:none;display:block" '
            f'title="Diagrama BPMN 2.0" loading="lazy"></iframe></div>'
            f'<p class="diagram-caption">'
            f'Arraste para mover &nbsp;&middot;&nbsp; Scroll para zoom &nbsp;&middot;&nbsp; '
            f'Tecla <kbd>0</kbd> para ajustar &nbsp;&middot;&nbsp; '
            f'<em>Requer internet para carregar bpmn-js via CDN.</em></p>'
        )
        return _section_card("📐", "Diagrama BPMN 2.0", body, "sec-bpmn")
    except Exception:
        return ""


def _fetch_mermaid_svg(mermaid_code: str) -> str | None:
    try:
        p   = base64.urlsafe_b64encode(mermaid_code.encode("utf-8")).decode("ascii")
        url = f"https://mermaid.ink/svg/{p}"
        req = urllib.request.Request(url, headers={"User-Agent": "Process2Diagram/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            svg = resp.read().decode("utf-8")
        if not svg or "<svg" not in svg.lower():
            return None
        tag_m = _re.search(r"<svg[^>]*>", svg)
        if tag_m:
            tag = tag_m.group(0)
            w_m = _re.search(r'width="([\d.]+)"', tag)
            h_m = _re.search(r'height="([\d.]+)"', tag)
            has_vb = "viewBox" in tag or "viewbox" in tag
            new_tag = tag
            if w_m and h_m and not has_vb:
                new_tag = new_tag.replace(
                    "<svg", f'<svg viewBox="0 0 {w_m.group(1)} {h_m.group(1)}"', 1
                )
            new_tag = _re.sub(r'\s*width="[^"]*"',  "", new_tag)
            new_tag = _re.sub(r'\s*height="[^"]*"', "", new_tag)
            new_tag = new_tag.replace("<svg", '<svg width="100%" height="auto"', 1)
            svg = svg.replace(tag_m.group(0), new_tag, 1)
        return svg
    except Exception:
        return None


def _section_mermaid_diagram(hub) -> str:
    if not hub.bpmn.ready or not hub.bpmn.mermaid:
        return ""
    svg = _fetch_mermaid_svg(hub.bpmn.mermaid)
    if not svg:
        return ""
    body = (
        f'<div class="diagram-wrap" style="padding:16px;background:#fafbfc;overflow:auto;max-height:560px">'
        f'{svg}</div>'
        f'<p class="diagram-caption">Fluxograma gerado via mermaid.ink &nbsp;&middot;&nbsp; SVG embutido &mdash; funciona sem internet.</p>'
    )
    return _section_card("📊", "Fluxograma do Processo", body, "sec-mermaid")


def _section_minutes(hub) -> str:
    if not hub.minutes.ready:
        return ""
    m = hub.minutes

    dec_items = "".join(f"<li>{_e(d)}</li>" for d in m.decisions)
    dec_html = ""
    if dec_items:
        dec_html = (
            f'<div class="col-label" style="margin-bottom:8px">Decisões ({len(m.decisions)})</div>'
            f'<ol class="items" style="margin-bottom:24px">{dec_items}</ol>'
        )

    ai_rows = []
    for ai in m.action_items:
        pill  = _status_pill(ai.priority)
        raised = _e(ai.raised_by or "—")
        ai_rows.append(
            f"<tr>"
            f"<td>{pill}</td>"
            f"<td style='font-family:JetBrains Mono,monospace;font-size:11px'>{raised}</td>"
            f"<td>{_e(ai.task)}</td>"
            f"<td><strong>{_e(ai.responsible)}</strong></td>"
            f"<td style='color:var(--muted);font-size:12px'>{_e(ai.deadline or '—')}</td>"
            f"</tr>"
        )
    ai_table = ""
    if ai_rows:
        ai_table = (
            f'<div class="col-label" style="margin-bottom:8px">Action Items ({len(m.action_items)})</div>'
            f'<table><thead><tr>'
            f'<th>Prioridade</th><th>Por</th><th>Tarefa</th><th>Responsável</th><th>Prazo</th>'
            f'</tr></thead><tbody>{"".join(ai_rows)}</tbody></table>'
        )

    body = dec_html + ai_table
    if not body:
        body = "<p><em>Sem decisões ou action items registrados.</em></p>"
    return _section_card("📝", "Ata de Reunião", body, "sec-minutes")


def _section_requirements(hub) -> str:
    if not hub.requirements.ready or not hub.requirements.requirements:
        return ""
    reqs  = hub.requirements.requirements
    total = len(reqs)

    from collections import Counter
    type_counts = Counter(r.type for r in reqs)

    bars = []
    for t_key in _TYPE_LABEL:
        cnt = type_counts.get(t_key, 0)
        if cnt == 0:
            continue
        pct   = int(cnt / total * 100)
        color = _TYPE_COLOR.get(t_key, "#8496B0")
        bars.append(
            f'<div class="bar-wrap">'
            f'<div class="bar-label">{_e(_TYPE_LABEL[t_key])}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{pct}%;background:{color}"></div></div>'
            f'<div class="bar-count">{cnt}</div></div>'
        )

    req_rows = []
    for r in sorted(reqs, key=lambda x: (x.type, {"high": 0, "medium": 1, "low": 2}.get(x.priority, 3))):
        req_rows.append(
            f"<tr>"
            f"<td><span style='font-family:JetBrains Mono,monospace;font-size:11px;"
            f"background:var(--light);padding:2px 7px;border-radius:4px'>{_e(r.id)}</span></td>"
            f"<td>{_type_badge(r.type)}</td>"
            f"<td>{_status_pill(r.priority)}</td>"
            f"<td>{_e(r.title)}</td>"
            f"<td style='font-size:12px;color:var(--muted)'>{_e(r.actor or '—')}</td>"
            f"</tr>"
        )

    high_count = sum(1 for r in reqs if r.priority == "high")
    body = f"""
<div style="margin-bottom:16px">
  <span style="font-family:'DM Serif Display',serif;font-size:32px;color:var(--navy)">{total}</span>
  <span style="color:var(--muted);margin-left:6px;font-size:13px">requisitos &nbsp;&middot;&nbsp;</span>
  <span style="font-weight:600;color:var(--amber)">{high_count} alta prioridade</span>
</div>
<div style="margin-bottom:22px">{"".join(bars)}</div>
<table>
  <thead><tr><th>ID</th><th>Tipo</th><th>Prioridade</th><th>Título</th><th>Ator</th></tr></thead>
  <tbody>{"".join(req_rows)}</tbody>
</table>"""
    return _section_card("📋", "Especificação de Requisitos", body, "sec-reqs")


def _section_quality(hub) -> str:
    if not hub.transcript_quality.ready:
        return ""
    tq      = hub.transcript_quality
    g_color = _GRADE_COLOR.get(tq.grade, "#8496B0")
    g_bg    = _GRADE_BG.get(tq.grade, "#F4F7FB")

    crit_html = ""
    for c in tq.criteria[:6]:
        crit_html += (
            f'<div class="crit-bar">'
            f'<div class="crit-name">{_e(c.criterion)} &mdash; '
            f'<span style="font-family:JetBrains Mono,monospace;font-size:11px">{c.score}/100</span></div>'
            f'<div class="crit-track"><div class="crit-fill" style="width:{c.score}%"></div></div></div>'
        )

    body = f"""
<div class="quality-grid">
  <div class="grade-badge" style="background:{g_bg};color:{g_color}">{_e(tq.grade)}</div>
  <div style="flex:1">
    <div style="font-size:24px;font-weight:600;color:{g_color};margin-bottom:2px">
      {tq.overall_score:.1f} <span style="font-size:14px;color:var(--muted)">/ 100</span>
    </div>
    <div style="font-size:12px;color:var(--muted);margin-bottom:14px">
      Nota ponderada da transcrição ASR
    </div>
    {crit_html}
    <div style="margin-top:12px;font-size:13px;color:var(--text)">{_e(tq.recommendation)}</div>
  </div>
</div>"""
    return _section_card("🔬", "Qualidade da Transcrição", body, "sec-quality")


def _section_insights(narrative) -> str:
    insights = narrative.key_insights or []
    recs     = narrative.recommendations or []

    def _ol(items):
        if not items:
            return "<p><em>—</em></p>"
        lis = "".join(f"<li>{_e(item)}</li>" for item in items)
        return f'<ol class="items">{lis}</ol>'

    body = f"""
<div class="two-col">
  <div>
    <div class="col-label" style="margin-bottom:10px">Insights Identificados</div>
    {_ol(insights)}
  </div>
  <div>
    <div class="col-label" style="margin-bottom:10px">Recomendações Prioritárias</div>
    {_ol(recs)}
  </div>
</div>"""
    return _section_card("💡", "Insights e Recomendações", body, "sec-insights")


def _next_meeting(hub) -> str:
    nm = getattr(hub.minutes, "next_meeting", None) if hub.minutes.ready else None
    if not nm:
        return ""
    return f"""
<div class="next-meeting">
  <div class="nm-icon">📅</div>
  <div>
    <div class="nm-label">Próxima Reunião</div>
    <div class="nm-date">{_e(nm)}</div>
    <div class="nm-detail">Confirme a pauta com os participantes com antecedência.</div>
  </div>
</div>"""


def _footer(hub) -> str:
    session_id = getattr(hub.meta, "session_id", "")[:8]
    generated  = datetime.now().strftime("%d/%m/%Y às %H:%M")
    return f"""
<div class="page-footer">
  <div>
    <div class="footer-brand">⚙ Process2Diagram</div>
    <div class="footer-meta">Relatório gerado automaticamente por agentes LLM</div>
  </div>
  <div style="text-align:right">
    <div class="footer-meta">Sessão <code style="font-family:JetBrains Mono,monospace">{_e(session_id)}</code></div>
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
        _section_bpmn_diagram(hub),
        _section_mermaid_diagram(hub),
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
{_sidebar(hub, narrative)}
<div id="main">
{_hero(hub, narrative)}
{_participants_strip(hub)}
{_stats_bar(hub)}
<div class="content">
{sections}
{_next_meeting(hub)}
{_footer(hub)}
</div>
</div>
<button id="scrollTop" title="Voltar ao topo">↑</button>
<script>{_JS}</script>
</body>
</html>"""
