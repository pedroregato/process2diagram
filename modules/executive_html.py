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


_CHEVRON_SVG = '<svg viewBox="0 0 24 24"><polyline points="6 9 12 15 18 9"/></svg>'

def _section_card(icon: str, title: str, body: str, sec_id: str = "") -> str:
    id_attr = f' id="{sec_id}"' if sec_id else ""
    return f"""
<section class="section card"{id_attr}>
  <div class="card-header">
    <div class="section-icon">{icon}</div>
    <h2 class="section-title">{_e(title)}</h2>
    <div class="chevron">{_CHEVRON_SVG}</div>
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

/* ── Interactive: Collapsible sections ── */
.card-header{cursor:pointer;user-select:none}
.card-header:hover .section-title{color:var(--accent)}
.chevron{
  margin-left:auto;width:28px;height:28px;border-radius:50%;
  background:var(--light);border:1px solid var(--border);
  display:flex;align-items:center;justify-content:center;
  flex-shrink:0;transition:transform .3s cubic-bezier(.4,0,.2,1),background .2s
}
.chevron svg{width:14px;height:14px;stroke:var(--muted);fill:none;stroke-width:2;
  transition:stroke .2s}
.card.collapsed .chevron{transform:rotate(-90deg)}
.card.collapsed .chevron svg{stroke:var(--accent)}
.card.collapsed .card-body{display:none}
.expand-all-btn{
  font-size:12px;padding:6px 14px;border-radius:7px;
  border:1px solid var(--border);background:var(--white);
  color:var(--blue);cursor:pointer;font-weight:500;
  transition:all .15s;display:flex;align-items:center;gap:6px;
  font-family:inherit;margin:20px 24px 0;
}
.expand-all-btn:hover{background:var(--navy);color:#fff;border-color:var(--navy)}

/* ── Interactive: Requirements ── */
.req-toolbar{
  background:var(--light);border:1px solid var(--border);
  border-radius:10px;padding:14px 16px;margin-bottom:4px;
  display:flex;flex-direction:column;gap:10px
}
.req-toolbar-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.req-filter-btn{
  font-size:11px;padding:4px 11px;border-radius:100px;
  border:1px solid var(--border);background:var(--white);
  color:var(--muted);cursor:pointer;font-weight:500;
  transition:all .15s;font-family:inherit
}
.req-filter-btn:hover{border-color:var(--req-color,var(--accent));color:var(--req-color,var(--accent))}
.req-filter-btn.active{
  background:var(--req-color,var(--navy));
  color:#fff;border-color:var(--req-color,var(--navy))
}

/* ── Interactive: Comments ── */
.cmt-toggle{
  display:inline-flex;align-items:center;gap:5px;
  margin-top:10px;font-size:12px;color:var(--muted);
  background:none;border:none;cursor:pointer;padding:3px 0;
  transition:color .15s;font-family:inherit
}
.cmt-toggle:hover{color:var(--accent)}
.cmt-count-badge{
  background:var(--accent);color:#fff;
  font-family:'JetBrains Mono',monospace;font-size:10px;
  padding:1px 6px;border-radius:100px
}
.cmt-panel{
  display:none;margin-top:10px;padding:12px 14px;
  background:var(--light);border:1px solid var(--border);
  border-radius:10px
}
.cmt-panel.open{display:block}
.cmt-bubble{
  background:var(--white);border:1px solid var(--border);
  border-radius:10px;padding:9px 12px;
  font-size:13px;color:var(--text);line-height:1.55;margin-bottom:8px
}
.cmt-meta{
  font-size:10px;color:var(--muted);margin-bottom:4px;
  font-family:'JetBrains Mono',monospace
}
.cmt-row{display:flex;gap:8px;margin-top:10px;align-items:flex-end}
.cmt-input{
  flex:1;padding:8px 12px;border:1px solid var(--border);border-radius:8px;
  font-size:13px;font-family:inherit;color:var(--text);
  outline:none;resize:none;transition:border-color .15s;min-height:38px;line-height:1.5
}
.cmt-input:focus{border-color:var(--accent)}
.cmt-submit{
  padding:8px 14px;background:var(--navy);color:#fff;
  border:none;border-radius:8px;font-size:12px;font-weight:500;
  cursor:pointer;transition:background .15s;font-family:inherit;white-space:nowrap
}
.cmt-submit:hover{background:var(--blue)}

/* ── Interactive: Action Items ── */
.ai-toolbar{
  display:flex;align-items:center;justify-content:space-between;
  margin-bottom:14px;flex-wrap:wrap;gap:8px
}
.ai-count{
  font-family:'JetBrains Mono',monospace;font-size:12px;color:var(--muted)
}
.filter-group{display:flex;gap:4px;flex-wrap:wrap}
.filter-btn{
  font-size:12px;padding:5px 13px;border-radius:7px;
  border:1px solid var(--border);background:var(--white);
  color:var(--muted);cursor:pointer;font-weight:500;
  transition:all .15s;font-family:inherit
}
.filter-btn:hover{background:var(--light);color:var(--text)}
.filter-btn.active{background:var(--navy);color:#fff;border-color:var(--navy)}
.ai-pill{
  display:inline-flex;align-items:center;gap:5px;
  font-size:11px;font-weight:500;padding:4px 10px;border-radius:100px;
  border:1px solid;cursor:pointer;white-space:nowrap;
  transition:opacity .15s,transform .1s;user-select:none
}
.ai-pill:hover{opacity:.82;transform:scale(.97)}
/* Status popup */
#ai-popup{
  display:none;position:fixed;z-index:600;
  background:var(--white);border:1px solid var(--border);border-radius:12px;
  box-shadow:0 8px 32px rgba(11,30,61,.16);padding:8px;min-width:170px
}
#ai-popup-title{
  font-size:9px;letter-spacing:.12em;text-transform:uppercase;
  color:var(--muted);padding:4px 8px 8px;
  border-bottom:1px solid var(--border);margin-bottom:6px
}
.pop-opt{
  display:flex;align-items:center;gap:9px;padding:7px 10px;
  border-radius:8px;cursor:pointer;font-size:13px;color:var(--text);
  transition:background .12s
}
.pop-opt:hover{background:var(--light)}
.pop-dot{width:8px;height:8px;border-radius:50%;flex-shrink:0}
/* Toast */
#ai-toast{
  position:fixed;bottom:80px;right:28px;z-index:9999;
  background:var(--navy);color:#fff;font-size:13px;
  padding:10px 18px;border-radius:10px;
  box-shadow:0 4px 16px rgba(0,0,0,.2);
  opacity:0;transform:translateY(10px);
  transition:opacity .25s,transform .25s;pointer-events:none
}
#ai-toast.show{opacity:1;transform:translateY(0)}

/* ── Print ── */
@media print{
  #sidebar,#scrollTop,#ai-popup,#ai-toast{display:none!important}
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

// ── Action Items — Status Management ──────────────────────────────────────
(function() {
  const SESSION = window.P2D_SESSION || 'default';
  const LS_KEY  = 'p2d_ai_' + SESSION;

  const STATUS = {
    open:    { label: 'Aberto',    color: '#C97B1A', bg: '#FEF3E2', border: '#F5D9A0' },
    done:    { label: 'Concluído', color: '#1A7F5A', bg: '#E3F5ED', border: '#9FD9BC' },
    delayed: { label: 'Adiado',    color: '#6B3FA0', bg: '#F0E8FA', border: '#C9A8E8' },
  };

  // Load persisted statuses
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(LS_KEY) || '{}'); } catch(_) {}

  function applyStatus(row, status) {
    const pill = row.querySelector('.ai-pill');
    if (!pill) return;
    const cfg = STATUS[status] || STATUS.open;
    pill.innerHTML =
      `<span style="width:5px;height:5px;border-radius:50%;background:${cfg.color};`+
      `display:inline-block;flex-shrink:0"></span>${cfg.label}`;
    pill.style.cssText += `;background:${cfg.bg};color:${cfg.color};border-color:${cfg.border}`;
    row.dataset.aiStatus = status;
  }

  // Apply saved on load
  document.querySelectorAll('tr[data-ai-idx]').forEach(row => {
    const s = saved[row.dataset.aiIdx];
    if (s) applyStatus(row, s);
  });

  // Popup & toast
  const popup = document.getElementById('ai-popup');
  const toast = document.getElementById('ai-toast');
  let activeRow = null, toastTimer;

  function showToast(msg) {
    toast.textContent = msg;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), 2600);
  }

  function updateCount() {
    const rows   = document.querySelectorAll('tr[data-ai-idx]');
    const active = document.querySelector('.filter-btn.active');
    const filter = active ? active.dataset.filter : 'all';
    let vis = 0;
    rows.forEach(r => {
      const show = filter === 'all' || r.dataset.aiStatus === filter;
      r.style.display = show ? '' : 'none';
      if (show) vis++;
    });
    const el = document.getElementById('ai-visible');
    if (el) el.textContent = vis;
  }

  // Open popup on pill click
  document.addEventListener('click', e => {
    const pill = e.target.closest('.ai-pill');
    if (pill) {
      e.stopPropagation();
      activeRow = pill.closest('tr[data-ai-idx]');
      const r = pill.getBoundingClientRect();
      popup.style.top  = (r.bottom + 6 + window.scrollY) + 'px';
      popup.style.left = Math.min(r.left, window.innerWidth - 190) + 'px';
      popup.style.display = 'block';
      return;
    }
    if (!popup.contains(e.target)) popup.style.display = 'none';
  });

  // Select option
  popup.querySelectorAll('.pop-opt').forEach(opt => {
    opt.addEventListener('click', () => {
      if (!activeRow) return;
      const status = opt.dataset.status;
      const idx    = activeRow.dataset.aiIdx;
      applyStatus(activeRow, status);
      saved[idx] = status;
      try { localStorage.setItem(LS_KEY, JSON.stringify(saved)); } catch(_) {}
      popup.style.display = 'none';
      updateCount();
      showToast('✓ Status: ' + STATUS[status].label);
    });
  });

  // Filter buttons
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      updateCount();
    });
  });

  updateCount();
})();

// ── Collapsible section cards ─────────────────────────────────────────────
(function() {
  const cards = document.querySelectorAll('.card');

  cards.forEach(card => {
    card.querySelector('.card-header').addEventListener('click', () => {
      card.classList.toggle('collapsed');
    });
  });

  const expandBtn = document.getElementById('expandAllBtn');
  let allExpanded = true;
  if (expandBtn) {
    expandBtn.addEventListener('click', () => {
      allExpanded = !allExpanded;
      cards.forEach(c => c.classList.toggle('collapsed', !allExpanded));
      expandBtn.innerHTML = allExpanded
        ? `<svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" fill="none" stroke-width="2"><polyline points="7 13 12 18 17 13"/><polyline points="7 6 12 11 17 6"/></svg> Expandir todas as seções`
        : `<svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" fill="none" stroke-width="2"><polyline points="7 11 12 6 17 11"/><polyline points="7 18 12 13 17 18"/></svg> Retrair todas as seções`;
    });
  }
})();

// ── Requirements — Type & Priority Filters ────────────────────────────────
(function() {
  let activeType = 'all', activePrio = 'all';

  function updateReqs() {
    const rows = document.querySelectorAll('#req-tbody tr[data-req-type]');
    let vis = 0;
    rows.forEach(r => {
      const show =
        (activeType === 'all' || r.dataset.reqType === activeType) &&
        (activePrio === 'all' || r.dataset.reqPrio === activePrio);
      r.style.display = show ? '' : 'none';
      if (show) vis++;
    });
    const el = document.getElementById('req-visible');
    if (el) el.textContent = vis;
  }

  document.querySelectorAll('.req-filter-btn[data-req-filter-type]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.req-filter-btn[data-req-filter-type]')
        .forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeType = btn.dataset.reqFilterType;
      updateReqs();
    });
  });

  document.querySelectorAll('.req-filter-btn[data-req-filter-prio]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.req-filter-btn[data-req-filter-prio]')
        .forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activePrio = btn.dataset.reqFilterPrio;
      updateReqs();
    });
  });
})();

// ── Action Items — Comments ───────────────────────────────────────────────
(function() {
  const SESSION  = window.P2D_SESSION || 'default';
  const LS_KEY   = 'p2d_cmt_' + SESSION;

  let allComments = {};
  try { allComments = JSON.parse(localStorage.getItem(LS_KEY) || '{}'); } catch(_) {}

  function saveComments() {
    try { localStorage.setItem(LS_KEY, JSON.stringify(allComments)); } catch(_) {}
  }

  function renderComments(idx) {
    const list  = document.getElementById('cmt-list-' + idx);
    const badge = document.getElementById('cmt-badge-' + idx);
    if (!list) return;
    const cmts = allComments[idx] || [];
    list.innerHTML = cmts.map(c =>
      `<div class="cmt-bubble">
        <div class="cmt-meta">${c.ts}</div>
        ${c.text.replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\n/g,'<br>')}
      </div>`
    ).join('');
    if (badge) {
      badge.textContent = cmts.length;
      badge.style.display = cmts.length ? 'inline' : 'none';
    }
  }

  // Render persisted comments on load
  document.querySelectorAll('[id^="cmt-panel-"]').forEach(panel => {
    const idx = panel.id.replace('cmt-panel-', '');
    renderComments(idx);
  });

  // Toggle panel
  document.addEventListener('click', e => {
    const btn = e.target.closest('.cmt-toggle');
    if (btn) {
      const idx   = btn.dataset.cmtIdx;
      const panel = document.getElementById('cmt-panel-' + idx);
      if (panel) panel.classList.toggle('open');
      return;
    }

    // Submit comment
    const sub = e.target.closest('[data-cmt-submit]');
    if (sub) {
      const idx   = sub.dataset.cmtSubmit;
      const input = document.getElementById('cmt-input-' + idx);
      const text  = input ? input.value.trim() : '';
      if (!text) return;
      if (!allComments[idx]) allComments[idx] = [];
      const now = new Date().toLocaleString('pt-BR', { dateStyle:'short', timeStyle:'short' });
      allComments[idx].push({ ts: now, text });
      saveComments();
      renderComments(idx);
      if (input) input.value = '';
    }
  });
})();
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

    ai_table = ""
    if m.action_items:
        n = len(m.action_items)
        toolbar = (
            f'<div class="ai-toolbar">'
            f'<span class="ai-count"><span id="ai-visible">{n}</span> de {n} itens</span>'
            f'<div class="filter-group">'
            f'<button class="filter-btn active" data-filter="all">Todos</button>'
            f'<button class="filter-btn" data-filter="open">Abertos</button>'
            f'<button class="filter-btn" data-filter="done">Concluídos</button>'
            f'<button class="filter-btn" data-filter="delayed">Adiados</button>'
            f'</div></div>'
        )
        ai_rows = []
        for idx, ai in enumerate(m.action_items):
            # Default visual: open (amber)
            pill = (
                f'<span class="ai-pill" title="Clique para alterar status" '
                f'style="background:#FEF3E2;color:#C97B1A;border-color:#F5D9A0">'
                f'<span style="width:5px;height:5px;border-radius:50%;background:#C97B1A;'
                f'display:inline-block;flex-shrink:0"></span>Aberto</span>'
            )
            prio_badge = _status_pill(ai.priority)
            cmt_cell = (
                f'<td style="white-space:nowrap">'
                f'<button class="cmt-toggle" data-cmt-idx="{idx}">'
                f'💬 <span class="cmt-count-badge" id="cmt-badge-{idx}" '
                f'style="display:none">0</span>'
                f'</button>'
                f'<div class="cmt-panel" id="cmt-panel-{idx}">'
                f'<div id="cmt-list-{idx}"></div>'
                f'<div class="cmt-row">'
                f'<textarea class="cmt-input" id="cmt-input-{idx}" '
                f'placeholder="Adicionar comentário…" rows="1"></textarea>'
                f'<button class="cmt-submit" data-cmt-submit="{idx}">Enviar</button>'
                f'</div></div></td>'
            )
            ai_rows.append(
                f'<tr data-ai-idx="{idx}" data-ai-status="open">'
                f"<td>{pill}</td>"
                f"<td>{prio_badge}</td>"
                f"<td style='font-family:JetBrains Mono,monospace;font-size:11px'>"
                f"{_e(ai.raised_by or '—')}</td>"
                f"<td>{_e(ai.task)}</td>"
                f"<td><strong>{_e(ai.responsible)}</strong></td>"
                f"<td style='color:var(--muted);font-size:12px'>{_e(ai.deadline or '—')}</td>"
                f"{cmt_cell}"
                f"</tr>"
            )
        ai_table = (
            f'<div class="col-label" style="margin-bottom:10px">Action Items ({n})</div>'
            f'{toolbar}'
            f'<div style="overflow-x:auto"><table>'
            f'<thead><tr>'
            f'<th>Status</th><th>Prioridade</th><th>Por</th>'
            f'<th>Tarefa</th><th>Responsável</th><th>Prazo</th><th>💬</th>'
            f'</tr></thead>'
            f'<tbody>{"".join(ai_rows)}</tbody>'
            f'</table></div>'
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
    prio_counts = Counter(r.priority for r in reqs)

    # Distribution bars
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

    # Type filter buttons (only types that exist)
    type_filters = '<button class="req-filter-btn active" data-req-filter-type="all">Todos os tipos</button>'
    for t_key in _TYPE_LABEL:
        if type_counts.get(t_key, 0) == 0:
            continue
        color = _TYPE_COLOR.get(t_key, "#8496B0")
        type_filters += (
            f'<button class="req-filter-btn" data-req-filter-type="{_e(t_key)}" '
            f'style="--req-color:{color}">{_e(_TYPE_LABEL[t_key])}</button>'
        )

    # Priority filter buttons
    prio_filters = '<button class="req-filter-btn active" data-req-filter-prio="all">Todas</button>'
    for p_key, p_label in [("high","Alta"),("medium","Média"),("low","Baixa"),("unspecified","N/D")]:
        if prio_counts.get(p_key, 0) == 0:
            continue
        color = _PRIO_COLOR.get(p_key, "#8496B0")
        prio_filters += (
            f'<button class="req-filter-btn" data-req-filter-prio="{_e(p_key)}" '
            f'style="--req-color:{color}">{_e(p_label)}</button>'
        )

    toolbar = f"""
<div class="req-toolbar">
  <div class="req-toolbar-row">
    <span class="col-label" style="margin:0;white-space:nowrap">Tipo:</span>
    <div class="filter-group">{type_filters}</div>
  </div>
  <div class="req-toolbar-row">
    <span class="col-label" style="margin:0;white-space:nowrap">Prioridade:</span>
    <div class="filter-group">{prio_filters}</div>
  </div>
  <div class="ai-count" style="margin-top:4px">
    <span id="req-visible">{total}</span> de {total} requisitos
  </div>
</div>"""

    # Rows with data attributes
    req_rows = []
    for r in sorted(reqs, key=lambda x: (x.type, {"high": 0, "medium": 1, "low": 2}.get(x.priority, 3))):
        req_rows.append(
            f'<tr data-req-type="{_e(r.type)}" data-req-prio="{_e(r.priority)}">'
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
{toolbar}
<div style="overflow-x:auto;margin-top:14px">
<table>
  <thead><tr><th>ID</th><th>Tipo</th><th>Prioridade</th><th>Título</th><th>Ator</th></tr></thead>
  <tbody id="req-tbody">{"".join(req_rows)}</tbody>
</table></div>"""
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
    session_id = _e(getattr(hub.meta, "session_id", "default")[:16])

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
<button class="expand-all-btn" id="expandAllBtn">
  <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" fill="none" stroke-width="2">
    <polyline points="7 13 12 18 17 13"/><polyline points="7 6 12 11 17 6"/>
  </svg>
  Expandir todas as seções
</button>
<div class="content">
{sections}
{_next_meeting(hub)}
{_footer(hub)}
</div>
</div>
<button id="scrollTop" title="Voltar ao topo">↑</button>

<!-- Status popup (action items) -->
<div id="ai-popup">
  <div id="ai-popup-title">Alterar status</div>
  <div class="pop-opt" data-status="open">
    <span class="pop-dot" style="background:#C97B1A"></span>Aberto
  </div>
  <div class="pop-opt" data-status="done">
    <span class="pop-dot" style="background:#1A7F5A"></span>Concluído
  </div>
  <div class="pop-opt" data-status="delayed">
    <span class="pop-dot" style="background:#6B3FA0"></span>Adiado
  </div>
</div>
<div id="ai-toast"></div>

<script>window.P2D_SESSION = '{session_id}';</script>
<script>{_JS}</script>
</body>
</html>"""
