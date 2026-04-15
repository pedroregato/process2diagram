# modules/reqtracker_exporter.py
# ─────────────────────────────────────────────────────────────────────────────
# Exportador profissional do ReqTracker.
#
# to_html(project, meetings, requirements, contradictions, sbvr_terms, sbvr_rules)
#   → str  (HTML auto-contido com navegação lateral, filtros e print CSS)
#
# to_pdf(project, meetings, requirements, contradictions, sbvr_terms, sbvr_rules)
#   → bytes  (PDF A4 via fpdf2: capa, requisitos, contradições, SBVR, reuniões)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import html as _html_lib
from datetime import datetime
from io import BytesIO


# ── Helpers compartilhados ────────────────────────────────────────────────────

def _esc(s: object) -> str:
    return _html_lib.escape(str(s or ""))


def _now() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")


def _now_short() -> str:
    return datetime.now().strftime("%d/%m/%Y")


def _meet_label(mid: str | None, meet_map: dict) -> str:
    if not mid or mid not in meet_map:
        return "—"
    m = meet_map[mid]
    dt = m.get("meeting_date") or ""
    return f"Reunião {m.get('meeting_number', '?')} — {m.get('title', '')} ({dt})"


_STATUS_LABEL = {
    "active":       ("✅", "Ativo",       "#0d4f2e", "#4ade80"),
    "revised":      ("🔄", "Revisado",    "#4a3000", "#fbbf24"),
    "contradicted": ("⚠️",  "Contradição", "#4a0d0d", "#f87171"),
    "deprecated":   ("🗃️", "Depreciado",  "#2a2a2a", "#9ca3af"),
}

_CHANGE_COLOR = {
    "new":          "#60a5fa",
    "confirmed":    "#34d399",
    "revised":      "#fbbf24",
    "contradicted": "#f87171",
}

_RULE_LABEL = {
    "constraint":   ("Restrição",    "#4a0d0d", "#f87171"),
    "operational":  ("Operacional",  "#0d4f2e", "#4ade80"),
    "behavioral":   ("Comportamental","#4a3000", "#fbbf24"),
    "structural":   ("Estrutural",   "#0d2f4f", "#60a5fa"),
}

_CAT_LABEL = {
    "concept":   ("Conceito",     "#0d2f4f", "#60a5fa"),
    "fact_type": ("Tipo de Fato", "#0d3f1f", "#34d399"),
    "role":      ("Papel",        "#4a3000", "#fbbf24"),
    "process":   ("Processo",     "#0d4f2e", "#4ade80"),
}

# ── PDF text sanitizer (fpdf2 Latin-1 core fonts) ─────────────────────────────

_PDF_MAP = {
    "\u2014": "-", "\u2013": "-", "\u2022": "*", "\u2192": "->",
    "\u2026": "...", "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
    "\u00b7": "*",
}


def _md_to_html(md: str) -> str:
    """Minimal Markdown → HTML converter for meeting minutes."""
    import re
    lines = md.splitlines()
    out = []
    in_ul = False
    in_table = False

    def close_ul():
        nonlocal in_ul
        if in_ul:
            out.append("</ul>")
            in_ul = False

    def close_table():
        nonlocal in_table
        if in_table:
            out.append("</tbody></table>")
            in_table = False

    def inline(text: str) -> str:
        text = _html_lib.escape(text)
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*',     r'<em>\1</em>',          text)
        return text

    for line in lines:
        stripped = line.rstrip()

        # Table row
        if stripped.startswith("|"):
            close_ul()
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if all(re.match(r'^[-:]+$', c) for c in cells if c):
                # separator row — skip, but mark as header done
                continue
            if not in_table:
                out.append('<table class="minutes-table"><tbody>')
                in_table = True
            tds = "".join(f"<td>{inline(c)}</td>" for c in cells)
            out.append(f"<tr>{tds}</tr>")
            continue

        close_table()

        # Headers
        if stripped.startswith("### "):
            close_ul()
            out.append(f'<h5 class="min-h5">{inline(stripped[4:])}</h5>')
        elif stripped.startswith("## "):
            close_ul()
            out.append(f'<h4 class="min-h4">{inline(stripped[3:])}</h4>')
        elif stripped.startswith("# "):
            close_ul()
            out.append(f'<h3 class="min-h3">{inline(stripped[2:])}</h3>')
        # List items
        elif re.match(r'^[-*] ', stripped):
            if not in_ul:
                out.append("<ul>")
                in_ul = True
            out.append(f"<li>{inline(stripped[2:])}</li>")
        elif re.match(r'^\d+\. ', stripped):
            close_ul()
            out.append(f"<li>{inline(re.sub(r'^\d+\. ', '', stripped))}</li>")
        # Blank line
        elif not stripped:
            close_ul()
            out.append("<br>")
        else:
            close_ul()
            out.append(f"<p>{inline(stripped)}</p>")

    close_ul()
    close_table()
    return "\n".join(out)


def _p(text: object) -> str:
    t = str(text or "")
    for src, dst in _PDF_MAP.items():
        t = t.replace(src, dst)
    return t.encode("latin-1", errors="replace").decode("latin-1")


# ══════════════════════════════════════════════════════════════════════════════
# HTML EXPORT
# ══════════════════════════════════════════════════════════════════════════════

def to_html(
    project: dict,
    meetings: list[dict],
    requirements: list[dict],
    contradictions: list[dict],
    sbvr_terms: list[dict],
    sbvr_rules: list[dict],
) -> str:
    meet_map = {m["id"]: m for m in meetings}
    proj_name = _esc(project.get("name", "Projeto"))
    now = _now()

    n_req   = len(requirements)
    n_meet  = len(meetings)
    n_contr = sum(1 for r in requirements if r.get("status") == "contradicted")
    n_rev   = sum(1 for r in requirements if r.get("status") == "revised")
    n_terms = len(sbvr_terms)
    n_rules = len(sbvr_rules)

    # ── Requirements rows ─────────────────────────────────────────────────────
    req_rows = ""
    for req in requirements:
        num    = req.get("req_number", 0)
        status = req.get("status", "active")
        icon, label, bg, fg = _STATUS_LABEL.get(status, ("", status, "#222", "#ccc"))
        vers   = req.get("requirement_versions") or []

        req_rows += f"""
        <tr data-status="{_esc(status)}"
            data-type="{_esc(req.get('req_type',''))}"
            data-prio="{_esc(req.get('priority',''))}">
          <td><span class="mono">REQ-{num:03d}</span></td>
          <td>{_esc(req.get('title',''))}</td>
          <td>{_esc(req.get('req_type',''))}</td>
          <td>{_esc(req.get('priority',''))}</td>
          <td><span class="badge" style="background:{bg};color:{fg}">{icon} {label}</span></td>
          <td style="text-align:center">{len(vers)}</td>
          <td class="desc">{_esc(req.get('description',''))}</td>
        </tr>"""

    # ── Contradiction cards ───────────────────────────────────────────────────
    contra_cards = ""
    for c in contradictions:
        req_info = c.get("requirements") or {}
        num      = req_info.get("req_number", "?")
        title    = _esc(req_info.get("title", ""))
        meet     = _esc(_meet_label(c.get("meeting_id"), meet_map))
        new_def  = _esc(c.get("description", "—"))
        analysis = _esc(c.get("contradiction_detail", "—"))
        summary  = _esc(c.get("change_summary", ""))

        contra_cards += f"""
        <div class="contra-card">
          <div class="contra-header">⚠️ REQ-{num:03d if isinstance(num, int) else num} — {title}</div>
          <div class="contra-body">
            <div class="contra-field"><span class="field-label">Reunião que gerou a contradição:</span> {meet}</div>
            <div class="contra-field"><span class="field-label">Nova definição:</span> {new_def}</div>
            <div class="contra-field contra-analysis"><span class="field-label">Análise:</span> {analysis}</div>
            {"<div class='contra-field'><span class='field-label'>Resumo da mudança:</span> " + summary + "</div>" if summary else ""}
          </div>
        </div>"""

    if not contra_cards:
        contra_cards = '<div class="empty-msg">✅ Nenhuma contradição detectada neste projeto.</div>'

    # ── SBVR terms table ──────────────────────────────────────────────────────
    terms_rows = ""
    for t in sbvr_terms:
        cat = t.get("category", "concept")
        lbl, bg, fg = _CAT_LABEL.get(cat, (cat, "#222", "#ccc"))
        meet_info = t.get("meetings") or {}
        m_num = meet_info.get("meeting_number", "?")
        terms_rows += f"""
        <tr>
          <td><strong>{_esc(t.get('term',''))}</strong></td>
          <td><span class="badge" style="background:{bg};color:{fg}">{lbl}</span></td>
          <td>{_esc(t.get('definition',''))}</td>
          <td style="text-align:center">#{m_num}</td>
        </tr>"""

    if not terms_rows:
        terms_rows = '<tr><td colspan="4" class="empty-td">Nenhum termo registrado.</td></tr>'

    # ── SBVR rules table ──────────────────────────────────────────────────────
    rules_rows = ""
    for i, r in enumerate(sbvr_rules, 1):
        rtype = r.get("rule_type", "constraint")
        lbl, bg, fg = _RULE_LABEL.get(rtype, (rtype, "#222", "#ccc"))
        rule_id = r.get("rule_id") or f"BR-{i:03d}"
        meet_info = r.get("meetings") or {}
        m_num = meet_info.get("meeting_number", "?")
        src = _esc(r.get("source", "") or "")
        rules_rows += f"""
        <tr>
          <td><span class="mono">{_esc(rule_id)}</span></td>
          <td><span class="badge" style="background:{bg};color:{fg}">{lbl}</span></td>
          <td>{_esc(r.get('statement',''))}</td>
          <td style="text-align:center">{src or "—"}</td>
          <td style="text-align:center">#{m_num}</td>
        </tr>"""

    if not rules_rows:
        rules_rows = '<tr><td colspan="5" class="empty-td">Nenhuma regra registrada.</td></tr>'

    # ── Minutes cards (one collapsible card per meeting) ─────────────────────
    n_minutes = sum(1 for m in meetings if m.get("minutes_md"))
    minutes_cards = ""
    for m in meetings:
        num      = m.get("meeting_number", "?")
        dt       = m.get("meeting_date") or "—"
        md_text  = m.get("minutes_md") or ""
        body_id  = f"min-body-{num}"
        if md_text:
            body_html = _md_to_html(md_text)
            minutes_cards += f"""
        <div class="minutes-card">
          <div class="minutes-card-header" onclick="toggleMinutes('{body_id}',this)">
            <div class="minutes-card-num">{num}</div>
            <div class="minutes-card-title">{_esc(m.get('title',''))}</div>
            <div class="minutes-card-meta">{_esc(str(dt))}</div>
            <span class="minutes-toggle">▼</span>
          </div>
          <div id="{body_id}" class="minutes-body">{body_html}</div>
        </div>"""
        else:
            minutes_cards += f"""
        <div class="minutes-card">
          <div class="minutes-card-header">
            <div class="minutes-card-num">{num}</div>
            <div class="minutes-card-title">{_esc(m.get('title',''))}</div>
            <div class="minutes-card-meta">{_esc(str(dt))}</div>
          </div>
          <div class="minutes-body open">
            <p class="minutes-no-data">Ata não disponível para esta reunião.</p>
          </div>
        </div>"""

    if not minutes_cards:
        minutes_cards = '<div class="empty-msg">Nenhuma ata disponível.</div>'

    # ── Meetings cards ────────────────────────────────────────────────────────
    meet_cards = ""
    for m in meetings:
        num  = m.get("meeting_number", "?")
        dt   = m.get("meeting_date") or "—"
        tok  = m.get("total_tokens") or 0
        prov = _esc(m.get("llm_provider") or "—")
        reqs_here = [r for r in requirements if r.get("first_meeting_id") == m["id"]]
        terms_here = [t for t in sbvr_terms if t.get("meeting_id") == m["id"]]
        rules_here = [r for r in sbvr_rules if r.get("meeting_id") == m["id"]]

        req_list = "".join(
            f'<li><span class="mono">REQ-{r["req_number"]:03d}</span> {_esc(r.get("title",""))}</li>'
            for r in reqs_here
        )

        meet_cards += f"""
        <div class="meet-card">
          <div class="meet-num">{num}</div>
          <div class="meet-body">
            <div class="meet-title">{_esc(m.get('title',''))}</div>
            <div class="meet-meta">{dt} &nbsp;·&nbsp; {tok:,} tokens &nbsp;·&nbsp; {prov}</div>
            <div class="meet-stats">
              <span>{len(reqs_here)} requisito(s) originado(s)</span>
              <span>{len(terms_here)} termo(s) SBVR</span>
              <span>{len(rules_here)} regra(s) SBVR</span>
            </div>
            {"<ul class='req-list'>" + req_list + "</ul>" if req_list else ""}
          </div>
        </div>"""

    # ── Filter options ────────────────────────────────────────────────────────
    all_types = sorted({r.get("req_type", "") for r in requirements if r.get("req_type")})
    all_prios = sorted({r.get("priority", "") for r in requirements if r.get("priority")})

    type_opts = "".join(f'<option value="{_esc(t)}">{_esc(t)}</option>' for t in all_types)
    prio_opts = "".join(f'<option value="{_esc(p)}">{_esc(p)}</option>' for p in all_prios)

    # ── Assemble HTML ─────────────────────────────────────────────────────────
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ReqTracker — {proj_name}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<style>
:root{{
  --navy:#0B1E3D;--navy2:#0F2040;--navy3:#0a1628;
  --accent:#2E7FD9;--accent2:#60a5fa;
  --border:#1e3a55;--border2:#243b55;
  --text:#e2e8f0;--muted:#94a3b8;--white:#f8fafc;
  --success:#4ade80;--warning:#fbbf24;--danger:#f87171;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--navy3);color:var(--text);font-family:'Inter',sans-serif;font-size:14px;line-height:1.6}}
a{{color:var(--accent2);text-decoration:none}}

/* ── Sidebar ── */
.sidebar{{position:fixed;left:0;top:0;width:230px;height:100vh;background:var(--navy);
  border-right:1px solid var(--border);overflow-y:auto;padding:1.5rem 0;z-index:100}}
.sidebar-logo{{padding:0 1.5rem 1.5rem;border-bottom:1px solid var(--border);margin-bottom:1rem}}
.sidebar-logo .app-name{{font-size:.7rem;color:var(--muted);letter-spacing:.1em;text-transform:uppercase}}
.sidebar-logo .proj-name{{font-size:1rem;font-weight:700;color:var(--white);margin-top:.2rem;word-break:break-word}}
.nav-section{{padding:.3rem 1.5rem .1rem;font-size:.65rem;font-weight:600;
  letter-spacing:.1em;text-transform:uppercase;color:var(--muted);margin-top:.8rem}}
.nav-link{{display:block;padding:.45rem 1.5rem;color:var(--muted);cursor:pointer;
  transition:all .15s;font-size:.87rem;border-left:3px solid transparent}}
.nav-link:hover{{color:var(--white);background:rgba(255,255,255,.05);border-left-color:var(--accent)}}
.sidebar-footer{{position:absolute;bottom:0;left:0;right:0;padding:1rem 1.5rem;
  border-top:1px solid var(--border);font-size:.72rem;color:var(--muted)}}

/* ── Main ── */
.main{{margin-left:230px;padding:2rem 2.5rem;max-width:1100px}}
.section{{margin-bottom:3rem}}
.section-title{{font-size:1.25rem;font-weight:700;color:var(--white);
  padding:.7rem 1rem;border-bottom:2px solid var(--accent);margin-bottom:0;
  display:flex;align-items:center;gap:.5rem;cursor:pointer;
  background:var(--navy2);border-radius:8px 8px 0 0;user-select:none;
  transition:background .15s}}
.section-title:hover{{background:#162d52}}
.section-title .chev{{margin-left:auto;font-size:.8rem;color:var(--muted);
  transition:transform .25s;display:inline-block}}
.section-title.collapsed .chev{{transform:rotate(-90deg)}}
.section-body{{overflow:hidden;transition:max-height .3s ease,opacity .25s ease;
  max-height:9999px;opacity:1;padding-top:1rem}}
.section-body.collapsed{{max-height:0;opacity:0;padding-top:0}}

/* ── Header banner ── */
.header-banner{{background:linear-gradient(135deg,var(--navy) 0%,#1a3a6e 100%);
  border:1px solid var(--border2);border-radius:12px;padding:1.8rem 2rem;
  margin-bottom:2rem;display:flex;justify-content:space-between;align-items:flex-start}}
.banner-title{{font-size:1.6rem;font-weight:700;color:var(--white)}}
.banner-subtitle{{color:var(--muted);font-size:.875rem;margin-top:.2rem}}
.banner-date{{color:var(--muted);font-size:.8rem;text-align:right}}
.banner-badge{{background:var(--accent);color:#fff;font-size:.7rem;font-weight:700;
  padding:2px 10px;border-radius:20px;letter-spacing:.05em}}

/* ── Metric cards ── */
.metrics{{display:grid;grid-template-columns:repeat(6,1fr);gap:1rem;margin-bottom:2rem}}
.metric-card{{background:var(--navy2);border:1px solid var(--border);border-radius:10px;
  padding:1rem 1.2rem;text-align:center}}
.metric-value{{font-size:1.8rem;font-weight:700;color:var(--accent2)}}
.metric-label{{font-size:.72rem;color:var(--muted);margin-top:.2rem;text-transform:uppercase;letter-spacing:.05em}}
.metric-card.danger .metric-value{{color:var(--danger)}}
.metric-card.warning .metric-value{{color:var(--warning)}}
.metric-card.success .metric-value{{color:var(--success)}}

/* ── Filter bar ── */
.filter-bar{{display:flex;gap:.8rem;flex-wrap:wrap;margin-bottom:1rem;align-items:center}}
.filter-bar select,.filter-bar input{{background:var(--navy2);border:1px solid var(--border2);
  color:var(--text);padding:.4rem .8rem;border-radius:6px;font-size:.85rem;outline:none}}
.filter-bar select:focus,.filter-bar input:focus{{border-color:var(--accent)}}
.filter-count{{color:var(--muted);font-size:.8rem;margin-left:auto}}

/* ── Requirements table ── */
.req-table{{width:100%;border-collapse:collapse;font-size:.85rem}}
.req-table th{{background:var(--navy);color:var(--muted);font-weight:600;font-size:.75rem;
  text-transform:uppercase;letter-spacing:.05em;padding:.6rem 1rem;text-align:left;
  border-bottom:2px solid var(--border2);position:sticky;top:0;z-index:10}}
.req-table td{{padding:.6rem 1rem;border-bottom:1px solid var(--border);vertical-align:top}}
.req-table tr:hover td{{background:rgba(46,127,217,.06)}}
.req-table tr[data-status="contradicted"] td:first-child{{border-left:3px solid var(--danger)}}
.req-table tr[data-status="revised"] td:first-child{{border-left:3px solid var(--warning)}}
.desc{{max-width:300px;color:var(--muted);font-size:.8rem}}
.mono{{font-family:'JetBrains Mono',monospace;font-size:.82rem;color:var(--accent2);font-weight:600}}
.hidden{{display:none!important}}

/* ── Badges ── */
.badge{{display:inline-block;padding:2px 10px;border-radius:20px;font-size:.7rem;font-weight:600;letter-spacing:.04em}}

/* ── Contradiction cards ── */
.contra-card{{border-left:4px solid var(--danger);background:rgba(248,113,113,.06);
  border-radius:0 10px 10px 0;padding:1.2rem 1.5rem;margin-bottom:1rem}}
.contra-header{{font-weight:700;font-size:1rem;color:var(--danger);margin-bottom:.8rem}}
.contra-body{{display:flex;flex-direction:column;gap:.5rem}}
.contra-field{{font-size:.875rem}}
.field-label{{font-weight:600;color:var(--muted)}}
.contra-analysis{{background:rgba(248,113,113,.08);padding:.5rem .8rem;border-radius:6px;margin-top:.2rem}}
.empty-msg{{color:var(--success);padding:1rem;background:rgba(74,222,128,.06);
  border:1px solid rgba(74,222,128,.2);border-radius:8px;text-align:center}}

/* ── SBVR tables ── */
.sbvr-grid{{display:grid;grid-template-columns:1fr 1fr;gap:2rem}}
.sbvr-table{{width:100%;border-collapse:collapse;font-size:.85rem}}
.sbvr-table th{{background:var(--navy);color:var(--muted);font-weight:600;font-size:.75rem;
  text-transform:uppercase;letter-spacing:.05em;padding:.6rem .8rem;text-align:left;
  border-bottom:2px solid var(--border2)}}
.sbvr-table td{{padding:.55rem .8rem;border-bottom:1px solid var(--border);vertical-align:top}}
.sbvr-table tr:hover td{{background:rgba(46,127,217,.06)}}
.empty-td{{text-align:center;color:var(--muted);padding:1.5rem}}
.subsection-title{{font-size:1rem;font-weight:600;color:var(--accent2);margin-bottom:.8rem}}

/* ── Meeting cards ── */
.meet-card{{display:flex;gap:1.2rem;padding:1rem 1.2rem;background:var(--navy2);
  border:1px solid var(--border);border-radius:10px;margin-bottom:.8rem}}
.meet-num{{width:36px;height:36px;border-radius:50%;background:var(--accent);color:#fff;
  display:flex;align-items:center;justify-content:center;font-weight:700;font-size:1rem;flex-shrink:0}}
.meet-body{{flex:1}}
.meet-title{{font-weight:600;color:var(--white);font-size:.95rem}}
.meet-meta{{color:var(--muted);font-size:.8rem;margin-top:.2rem}}
.meet-stats{{display:flex;gap:1rem;margin-top:.5rem;flex-wrap:wrap}}
.meet-stats span{{background:var(--navy);padding:2px 10px;border-radius:20px;font-size:.75rem;
  color:var(--accent2);border:1px solid var(--border2)}}
.req-list{{list-style:none;margin-top:.5rem;display:flex;flex-direction:column;gap:.2rem}}
.req-list li{{font-size:.82rem;color:var(--muted)}}

/* ── Minutes cards ── */
.minutes-card{{background:var(--navy2);border:1px solid var(--border);border-radius:10px;
  margin-bottom:1.2rem;overflow:hidden}}
.minutes-card-header{{display:flex;align-items:center;gap:1rem;padding:.8rem 1.2rem;
  background:var(--navy);border-bottom:1px solid var(--border);cursor:pointer;user-select:none}}
.minutes-card-num{{width:30px;height:30px;border-radius:50%;background:var(--accent);color:#fff;
  display:flex;align-items:center;justify-content:center;font-weight:700;font-size:.9rem;flex-shrink:0}}
.minutes-card-title{{font-weight:600;color:var(--white);font-size:.9rem;flex:1}}
.minutes-card-meta{{color:var(--muted);font-size:.78rem}}
.minutes-toggle{{color:var(--muted);font-size:.8rem;transition:transform .25s}}
.minutes-body{{padding:1.2rem 1.4rem;display:none}}
.minutes-body.open{{display:block}}
.minutes-body h3.min-h3,.minutes-body h3{{font-size:1rem;color:var(--accent2);margin:.8rem 0 .3rem;border-bottom:1px solid var(--border);padding-bottom:.2rem}}
.minutes-body h4.min-h4,.minutes-body h4{{font-size:.9rem;color:var(--accent2);margin:.6rem 0 .2rem}}
.minutes-body h5.min-h5,.minutes-body h5{{font-size:.85rem;color:var(--muted);margin:.4rem 0 .1rem}}
.minutes-body p{{font-size:.85rem;margin:.2rem 0;color:var(--text)}}
.minutes-body ul{{padding-left:1.2rem;margin:.2rem 0}}
.minutes-body li{{font-size:.85rem;color:var(--text);margin:.1rem 0}}
.minutes-body table.minutes-table{{width:100%;border-collapse:collapse;font-size:.8rem;margin:.4rem 0}}
.minutes-body table.minutes-table td{{padding:.35rem .6rem;border:1px solid var(--border);vertical-align:top}}
.minutes-body table.minutes-table tr:first-child td{{background:var(--navy);color:var(--muted);font-weight:600}}
.minutes-no-data{{color:var(--muted);font-style:italic;font-size:.85rem;padding:1rem}}
@media print{{
  .minutes-body{{display:block!important}}
  .minutes-card-header .minutes-toggle{{display:none}}
}}

/* ── Print CSS ── */
@media print{{
  body{{background:#fff;color:#1a2a3a;font-size:11pt}}
  .sidebar{{display:none}}
  .main{{margin-left:0;padding:1cm}}
  .header-banner{{background:#0B1E3D!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  .metric-card{{border:1px solid #cbd5e1;background:#f8fafc!important}}
  .metric-value{{color:#2E7FD9!important}}
  .req-table th{{background:#e2e8f0!important;color:#475569!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
  .req-table td{{border-bottom:1px solid #e2e8f0;color:#1a2a3a}}
  .contra-card{{background:#fff0f0!important;border-left-color:#dc2626!important}}
  .meet-card{{background:#f8fafc!important;border:1px solid #e2e8f0}}
  .section{{page-break-inside:avoid}}
  .filter-bar{{display:none}}
}}
</style>
</head>
<body>

<!-- ── Sidebar ── -->
<nav class="sidebar">
  <div class="sidebar-logo">
    <div class="app-name">Process2Diagram</div>
    <div class="proj-name">{proj_name}</div>
  </div>
  <div class="nav-section">Navegação</div>
  <a class="nav-link" data-target="sec-metrics">📊 Resumo Executivo</a>
  <a class="nav-link" data-target="sec-req">📝 Requisitos ({n_req})</a>
  <a class="nav-link" data-target="sec-contra">⚠️ Contradições ({n_contr})</a>
  <a class="nav-link" data-target="sec-sbvr">📖 SBVR ({n_terms}T · {n_rules}R)</a>
  <a class="nav-link" data-target="sec-meetings">🗓️ Reuniões ({n_meet})</a>
  <a class="nav-link" data-target="sec-minutes">📄 Atas ({n_minutes})</a>
  <div class="sidebar-footer">
    Gerado em {now}<br>
    Process2Diagram ReqTracker
  </div>
</nav>

<!-- ── Main ── -->
<main class="main">

  <!-- Header -->
  <div class="header-banner">
    <div>
      <div class="banner-title">📋 Rastreador de Requisitos</div>
      <div class="banner-subtitle">{proj_name}</div>
      <div style="margin-top:.5rem">
        <span class="banner-badge">ReqTracker Export</span>
      </div>
    </div>
    <div class="banner-date">
      Gerado em<br><strong>{now}</strong>
    </div>
  </div>

  <!-- Metrics -->
  <div id="sec-metrics" class="metrics">
    <div class="metric-card">
      <div class="metric-value">{n_req}</div>
      <div class="metric-label">Requisitos</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">{n_meet}</div>
      <div class="metric-label">Reuniões</div>
    </div>
    <div class="metric-card warning">
      <div class="metric-value">{n_rev}</div>
      <div class="metric-label">Revisados</div>
    </div>
    <div class="metric-card danger">
      <div class="metric-value">{n_contr}</div>
      <div class="metric-label">Contradições</div>
    </div>
    <div class="metric-card success">
      <div class="metric-value">{n_terms}</div>
      <div class="metric-label">Termos SBVR</div>
    </div>
    <div class="metric-card">
      <div class="metric-value">{n_rules}</div>
      <div class="metric-label">Regras SBVR</div>
    </div>
  </div>

  <!-- Requirements -->
  <div id="sec-req" class="section">
    <div class="section-title" onclick="toggleSection('body-req')">
      📝 Especificação de Requisitos
      <span class="chev">▼</span>
    </div>
    <div id="body-req" class="section-body">
    <div class="filter-bar">
      <select id="f-status" onchange="filterReqs()">
        <option value="">Todos os status</option>
        <option value="active">Ativo</option>
        <option value="revised">Revisado</option>
        <option value="contradicted">Contradição</option>
        <option value="deprecated">Depreciado</option>
      </select>
      <select id="f-type" onchange="filterReqs()">
        <option value="">Todos os tipos</option>
        {type_opts}
      </select>
      <select id="f-prio" onchange="filterReqs()">
        <option value="">Todas as prioridades</option>
        {prio_opts}
      </select>
      <input id="f-search" type="text" placeholder="🔍 Buscar..." oninput="filterReqs()" style="min-width:180px">
      <span class="filter-count" id="req-count">{n_req} requisito(s)</span>
    </div>
    <div style="overflow-x:auto">
      <table class="req-table" id="req-table">
        <thead>
          <tr>
            <th>ID</th><th>Título</th><th>Tipo</th><th>Prioridade</th>
            <th>Status</th><th>Versões</th><th>Descrição</th>
          </tr>
        </thead>
        <tbody id="req-body">
          {req_rows}
        </tbody>
      </table>
    </div>
    </div><!-- /body-req -->
  </div>

  <!-- Contradictions -->
  <div id="sec-contra" class="section">
    <div class="section-title" onclick="toggleSection('body-contra')">
      ⚠️ Contradições Detectadas
      <span class="chev">▼</span>
    </div>
    <div id="body-contra" class="section-body">
      {contra_cards}
    </div>
  </div>

  <!-- SBVR -->
  <div id="sec-sbvr" class="section">
    <div class="section-title" onclick="toggleSection('body-sbvr')">
      📖 Vocabulário e Regras SBVR
      <span class="chev">▼</span>
    </div>
    <div id="body-sbvr" class="section-body">
      <div class="sbvr-grid">
        <div>
          <div class="subsection-title">📚 Vocabulário de Negócio ({n_terms} termos)</div>
          <table class="sbvr-table">
            <thead><tr><th>Termo</th><th>Categoria</th><th>Definição</th><th>Reunião</th></tr></thead>
            <tbody>{terms_rows}</tbody>
          </table>
        </div>
        <div>
          <div class="subsection-title">📋 Regras de Negócio ({n_rules} regras)</div>
          <table class="sbvr-table">
            <thead><tr><th>ID</th><th>Tipo</th><th>Enunciado</th><th>Fonte</th><th>Reunião</th></tr></thead>
            <tbody>{rules_rows}</tbody>
          </table>
        </div>
      </div>
    </div>
  </div>

  <!-- Meetings -->
  <div id="sec-meetings" class="section">
    <div class="section-title" onclick="toggleSection('body-meetings')">
      🗓️ Linha do Tempo de Reuniões
      <span class="chev">▼</span>
    </div>
    <div id="body-meetings" class="section-body">
      {meet_cards}
    </div>
  </div>

  <!-- Minutes -->
  <div id="sec-minutes" class="section">
    <div class="section-title" onclick="toggleSection('body-minutes')">
      📄 Atas das Reuniões
      <span class="chev">▼</span>
    </div>
    <div id="body-minutes" class="section-body">
      {minutes_cards}
    </div>
  </div>

</main>

<script>
function toggleMinutes(bodyId, header) {{
  const body   = document.getElementById(bodyId);
  const toggle = header.querySelector('.minutes-toggle');
  const isOpen = body.classList.contains('open');
  body.classList.toggle('open', !isOpen);
  if (toggle) toggle.style.transform = isOpen ? '' : 'rotate(180deg)';
}}

function toggleSection(bodyId) {{
  const body  = document.getElementById(bodyId);
  const title = body.previousElementSibling;
  const isCollapsed = body.classList.contains('collapsed');
  body.classList.toggle('collapsed', !isCollapsed);
  title.classList.toggle('collapsed', !isCollapsed);
}}

// Sidebar navigation — expands section if collapsed before scrolling
document.querySelectorAll('.nav-link[data-target]').forEach(link => {{
  link.addEventListener('click', e => {{
    e.preventDefault();
    const section = document.getElementById(link.dataset.target);
    if (!section) return;
    const body = section.querySelector('.section-body');
    if (body && body.classList.contains('collapsed')) {{
      toggleSection(body.id);
    }}
    section.scrollIntoView({{behavior: 'smooth', block: 'start'}});
  }});
}});

// Requirements filter
function filterReqs() {{
  const status = document.getElementById('f-status').value;
  const type   = document.getElementById('f-type').value;
  const prio   = document.getElementById('f-prio').value;
  const search = document.getElementById('f-search').value.toLowerCase();
  const rows   = document.querySelectorAll('#req-body tr');
  let visible  = 0;
  rows.forEach(row => {{
    const ms = !status || row.dataset.status === status;
    const mt = !type   || row.dataset.type   === type;
    const mp = !prio   || row.dataset.prio   === prio;
    const ms2 = !search || row.textContent.toLowerCase().includes(search);
    const show = ms && mt && mp && ms2;
    row.classList.toggle('hidden', !show);
    if (show) visible++;
  }});
  document.getElementById('req-count').textContent = visible + ' requisito(s)';
}}
</script>
</body>
</html>"""


# ══════════════════════════════════════════════════════════════════════════════
# PDF EXPORT
# ══════════════════════════════════════════════════════════════════════════════

def to_pdf(
    project: dict,
    meetings: list[dict],
    requirements: list[dict],
    contradictions: list[dict],
    sbvr_terms: list[dict],
    sbvr_rules: list[dict],
) -> bytes:
    from fpdf import FPDF

    meet_map = {m["id"]: m for m in meetings}

    n_req   = len(requirements)
    n_meet  = len(meetings)
    n_contr = sum(1 for r in requirements if r.get("status") == "contradicted")
    n_rev   = sum(1 for r in requirements if r.get("status") == "revised")
    n_terms = len(sbvr_terms)
    n_rules = len(sbvr_rules)
    proj_name = _p(project.get("name", "Projeto"))

    _PDF_STATUS = {
        "active":       ("Ativo",       (13, 79, 46),  (74, 222, 128)),
        "revised":      ("Revisado",    (74, 48,  0),  (251,191, 36)),
        "contradicted": ("Contradicao", (74, 13, 13),  (248,113,113)),
        "deprecated":   ("Depreciado",  (42, 42, 42),  (156,163,175)),
    }

    class _PDF(FPDF):
        def header(self):
            if self.page_no() == 1:
                return
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(148, 163, 184)
            self.set_y(10)
            self.cell(0, 5, _p(f"ReqTracker — {project.get('name','')}"), align="L")
            self.set_y(10)
            self.cell(0, 5, _p(f"Gerado em {_now_short()}"), align="R")
            self.set_draw_color(30, 58, 85)
            self.line(20, 16, self.w - 20, 16)
            self.ln(4)

        def footer(self):
            self.set_y(-14)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(148, 163, 184)
            self.cell(0, 8, _p(f"Process2Diagram  |  Pagina {self.page_no()}"), align="C")

    pdf = _PDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(left=20, top=24, right=20)

    W = pdf.w - 40

    def set_white():  pdf.set_text_color(248, 250, 252)
    def set_navy():   pdf.set_text_color(11, 30, 61)
    def set_accent(): pdf.set_text_color(46, 127, 217)
    def set_muted():  pdf.set_text_color(100, 116, 139)
    def set_body():   pdf.set_text_color(30, 42, 58)
    def set_danger(): pdf.set_text_color(220, 38, 38)

    def section_header(title: str) -> None:
        pdf.set_fill_color(46, 127, 217)
        pdf.set_font("Helvetica", "B", 9)
        set_white()
        pdf.cell(W, 7, _p(f"  {title.upper()}"), fill=True, ln=True)
        pdf.ln(3)
        set_body()
        pdf.set_font("Helvetica", "", 10)

    # ── Capa ──────────────────────────────────────────────────────────────────
    pdf.add_page()
    pdf.set_margins(left=0, top=0, right=0)

    # Navy background full page
    pdf.set_fill_color(11, 30, 61)
    pdf.rect(0, 0, pdf.w, pdf.h, style="F")

    # Gradient accent strip
    pdf.set_fill_color(46, 127, 217)
    pdf.rect(0, 0, 8, pdf.h, style="F")

    # Logo text top
    pdf.set_xy(20, 30)
    pdf.set_font("Helvetica", "", 9)
    set_muted()
    pdf.cell(0, 6, "PROCESS2DIAGRAM", ln=True)

    # Main title
    pdf.set_xy(20, 50)
    pdf.set_font("Helvetica", "B", 28)
    set_white()
    pdf.cell(0, 14, "ReqTracker", ln=True)
    pdf.set_x(20)
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(96, 165, 250)
    pdf.cell(0, 8, "Relatorio de Rastreamento de Requisitos", ln=True)

    # Project name
    pdf.set_xy(20, 90)
    pdf.set_font("Helvetica", "B", 16)
    set_white()
    pdf.multi_cell(pdf.w - 40, 9, proj_name)

    # Divider
    pdf.set_draw_color(30, 58, 85)
    y_div = pdf.get_y() + 6
    pdf.line(20, y_div, pdf.w - 20, y_div)
    pdf.ln(14)

    # Metrics grid on cover
    metrics = [
        (str(n_req),   "Requisitos"),
        (str(n_meet),  "Reunioes"),
        (str(n_rev),   "Revisados"),
        (str(n_contr), "Contradicoes"),
        (str(n_terms), "Termos SBVR"),
        (str(n_rules), "Regras SBVR"),
    ]
    card_w = (pdf.w - 40 - 10) / 3
    card_h = 22
    for i, (val, lbl) in enumerate(metrics):
        col = i % 3
        row = i // 3
        x = 20 + col * (card_w + 5)
        y = y_div + 16 + row * (card_h + 4)
        pdf.set_fill_color(15, 32, 64)
        pdf.set_draw_color(30, 58, 85)
        pdf.rect(x, y, card_w, card_h, style="FD")
        pdf.set_xy(x, y + 2)
        pdf.set_font("Helvetica", "B", 16)
        pdf.set_text_color(96, 165, 250)
        pdf.cell(card_w, 10, val, align="C")
        pdf.set_xy(x, y + 12)
        pdf.set_font("Helvetica", "", 7)
        set_muted()
        pdf.cell(card_w, 6, lbl.upper(), align="C")

    # Generation date
    pdf.set_xy(20, pdf.h - 30)
    pdf.set_font("Helvetica", "", 9)
    set_muted()
    pdf.cell(0, 6, _p(f"Gerado em {_now()}"), align="R")

    pdf.set_margins(left=20, top=24, right=20)

    # ── Requisitos ────────────────────────────────────────────────────────────
    pdf.add_page()
    section_header(f"Especificacao de Requisitos ({n_req})")

    # Table header
    col_w = [18, 60, 28, 22, 28, 12, W - 18 - 60 - 28 - 22 - 28 - 12]
    headers = ["ID", "Titulo", "Tipo", "Prioridade", "Status", "Vers.", "Descricao"]
    pdf.set_fill_color(11, 30, 61)
    pdf.set_font("Helvetica", "B", 8)
    set_white()
    for h, w in zip(headers, col_w):
        pdf.cell(w, 6, f" {h}", fill=True, border=0)
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    for i, req in enumerate(requirements):
        num    = req.get("req_number", 0)
        status = req.get("status", "active")
        lbl, (r1,g1,b1), (r2,g2,b2) = _PDF_STATUS.get(
            status, ("Ativo", (13,79,46), (74,222,128))
        )
        vers = req.get("requirement_versions") or []

        fill_even = i % 2 == 0
        pdf.set_fill_color(15, 32, 64) if fill_even else pdf.set_fill_color(10, 22, 46)
        set_body()

        row_y = pdf.get_y()
        # ID
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(96, 165, 250)
        pdf.cell(col_w[0], 5.5, f"REQ-{num:03d}", fill=fill_even, border=0)
        # Title
        pdf.set_font("Helvetica", "", 8)
        set_body()
        title_txt = _p(req.get("title", ""))[:55]
        pdf.cell(col_w[1], 5.5, f" {title_txt}", fill=fill_even, border=0)
        # Type
        pdf.cell(col_w[2], 5.5, _p(req.get("req_type", ""))[:18], fill=fill_even, border=0)
        # Priority
        pdf.cell(col_w[3], 5.5, _p(req.get("priority", ""))[:12], fill=fill_even, border=0)
        # Status badge
        pdf.set_text_color(r2, g2, b2)
        pdf.cell(col_w[4], 5.5, _p(lbl), fill=fill_even, border=0)
        # Versions
        set_muted()
        pdf.cell(col_w[5], 5.5, str(len(vers)), fill=fill_even, border=0, align="C")
        # Description
        set_body()
        desc_txt = _p(req.get("description", ""))[:60]
        pdf.cell(col_w[6], 5.5, f" {desc_txt}", fill=fill_even, border=0, ln=True)

    pdf.ln(4)

    # ── Contradições ─────────────────────────────────────────────────────────
    if contradictions:
        pdf.add_page()
        section_header(f"Contradicoes Detectadas ({len(contradictions)})")

        for c in contradictions:
            req_info = c.get("requirements") or {}
            num   = req_info.get("req_number", "?")
            title = _p(req_info.get("title", ""))
            meet  = _p(_meet_label(c.get("meeting_id"), meet_map))

            pdf.set_fill_color(74, 13, 13)
            pdf.set_font("Helvetica", "B", 9)
            set_danger()
            num_str = f"{num:03d}" if isinstance(num, int) else str(num)
            pdf.cell(W, 6, _p(f"  REQ-{num_str} - {title[:70]}"), fill=True, ln=True)
            pdf.ln(1)

            pdf.set_font("Helvetica", "B", 8)
            set_muted()
            pdf.cell(30, 5, "Reuniao:")
            pdf.set_font("Helvetica", "", 8)
            set_body()
            pdf.multi_cell(W - 30, 5, meet[:100])

            pdf.set_font("Helvetica", "B", 8)
            set_muted()
            pdf.cell(30, 5, "Nova definicao:")
            pdf.set_font("Helvetica", "", 8)
            set_body()
            pdf.multi_cell(W - 30, 5, _p(c.get("description", "—"))[:200])

            pdf.set_font("Helvetica", "B", 8)
            set_muted()
            pdf.cell(30, 5, "Analise:")
            pdf.set_font("Helvetica", "", 8)
            set_body()
            pdf.multi_cell(W - 30, 5, _p(c.get("contradiction_detail", "—"))[:300])
            pdf.ln(4)

    # ── SBVR Termos ───────────────────────────────────────────────────────────
    if sbvr_terms:
        pdf.add_page()
        section_header(f"Vocabulario de Negocios SBVR ({n_terms} termos)")

        col_t = [38, 28, W - 38 - 28 - 14, 14]
        hdrs_t = ["Termo", "Categoria", "Definicao", "Reun."]
        pdf.set_fill_color(11, 30, 61)
        pdf.set_font("Helvetica", "B", 8)
        set_white()
        for h, w in zip(hdrs_t, col_t):
            pdf.cell(w, 6, f" {h}", fill=True, border=0)
        pdf.ln()

        pdf.set_font("Helvetica", "", 8)
        for i, t in enumerate(sbvr_terms):
            fill_even = i % 2 == 0
            pdf.set_fill_color(15, 32, 64) if fill_even else pdf.set_fill_color(10, 22, 46)
            meet_info = t.get("meetings") or {}
            m_num = meet_info.get("meeting_number", "?")

            pdf.set_font("Helvetica", "B", 8)
            set_accent()
            pdf.cell(col_t[0], 5.5, _p(t.get("term", ""))[:22], fill=fill_even, border=0)
            pdf.set_font("Helvetica", "", 8)
            set_muted()
            pdf.cell(col_t[1], 5.5, _p(t.get("category", ""))[:15], fill=fill_even, border=0)
            set_body()
            defn = _p(t.get("definition", ""))[:80]
            pdf.cell(col_t[2], 5.5, f" {defn}", fill=fill_even, border=0)
            set_muted()
            pdf.cell(col_t[3], 5.5, f"#{m_num}", fill=fill_even, border=0, align="C", ln=True)

        pdf.ln(5)

    # ── SBVR Regras ───────────────────────────────────────────────────────────
    if sbvr_rules:
        section_header(f"Regras de Negocios SBVR ({n_rules} regras)")

        col_r = [20, 28, W - 20 - 28 - 18 - 14, 18, 14]
        hdrs_r = ["ID", "Tipo", "Enunciado", "Fonte", "Reun."]
        pdf.set_fill_color(11, 30, 61)
        pdf.set_font("Helvetica", "B", 8)
        set_white()
        for h, w in zip(hdrs_r, col_r):
            pdf.cell(w, 6, f" {h}", fill=True, border=0)
        pdf.ln()

        pdf.set_font("Helvetica", "", 8)
        for i, r in enumerate(sbvr_rules, 1):
            fill_even = i % 2 == 0
            pdf.set_fill_color(15, 32, 64) if fill_even else pdf.set_fill_color(10, 22, 46)
            rule_id   = _p(r.get("rule_id") or f"BR-{i:03d}")
            meet_info = r.get("meetings") or {}
            m_num     = meet_info.get("meeting_number", "?")

            pdf.set_font("Helvetica", "B", 8)
            set_accent()
            pdf.cell(col_r[0], 5.5, rule_id[:10], fill=fill_even, border=0)
            pdf.set_font("Helvetica", "", 8)
            set_muted()
            pdf.cell(col_r[1], 5.5, _p(r.get("rule_type", ""))[:15], fill=fill_even, border=0)
            set_body()
            stmt = _p(r.get("statement", ""))[:90]
            pdf.cell(col_r[2], 5.5, f" {stmt}", fill=fill_even, border=0)
            set_muted()
            pdf.cell(col_r[3], 5.5, _p(r.get("source", "") or "—")[:10], fill=fill_even, border=0, align="C")
            pdf.cell(col_r[4], 5.5, f"#{m_num}", fill=fill_even, border=0, align="C", ln=True)

        pdf.ln(5)

    # ── Reuniões ──────────────────────────────────────────────────────────────
    pdf.add_page()
    section_header(f"Reunioes do Projeto ({n_meet})")

    for m in meetings:
        num   = m.get("meeting_number", "?")
        title = _p(m.get("title", ""))
        dt    = _p(m.get("meeting_date") or "—")
        tok   = m.get("total_tokens") or 0
        prov  = _p(m.get("llm_provider") or "—")

        reqs_here  = [r for r in requirements if r.get("first_meeting_id") == m["id"]]
        terms_here = [t for t in sbvr_terms if t.get("meeting_id") == m["id"]]
        rules_here = [r for r in sbvr_rules if r.get("meeting_id") == m["id"]]

        pdf.set_fill_color(15, 32, 64)
        pdf.set_draw_color(30, 58, 85)
        pdf.set_font("Helvetica", "B", 10)
        set_accent()
        pdf.cell(10, 7, str(num), fill=True, border=0)
        pdf.set_font("Helvetica", "B", 10)
        set_white()
        pdf.cell(W - 10, 7, f"  {title[:80]}", fill=True, border=0, ln=True)

        pdf.set_font("Helvetica", "", 8)
        set_muted()
        pdf.set_x(20)
        pdf.cell(W, 5,
            _p(f"   Data: {dt}   |   Tokens: {tok:,}   |   Provedor: {prov}   |   "
               f"Requisitos originados: {len(reqs_here)}   |   "
               f"Termos SBVR: {len(terms_here)}   |   Regras SBVR: {len(rules_here)}"),
            ln=True)

        if reqs_here:
            for r in reqs_here[:6]:
                pdf.set_x(24)
                pdf.set_font("Helvetica", "", 8)
                set_body()
                pdf.cell(W - 4, 4.5,
                    _p(f"REQ-{r['req_number']:03d}  {r.get('title','')[:60]}"), ln=True)
            if len(reqs_here) > 6:
                pdf.set_x(24)
                set_muted()
                pdf.cell(W, 4.5, _p(f"... e mais {len(reqs_here)-6} requisito(s)"), ln=True)

        pdf.ln(4)

    # ── Atas das Reuniões ─────────────────────────────────────────────────────
    meetings_with_minutes = [m for m in meetings if m.get("minutes_md")]
    if meetings_with_minutes:
        import re as _re
        pdf.add_page()
        section_header(f"Atas das Reunioes ({len(meetings_with_minutes)})")

        def _strip_md(text: str) -> str:
            """Remove markdown markers for plain-text PDF rendering."""
            t = _re.sub(r'^#{1,6}\s+', '', text, flags=_re.MULTILINE)
            t = _re.sub(r'\*\*(.+?)\*\*', r'\1', t)
            t = _re.sub(r'\*(.+?)\*',     r'\1', t)
            t = _re.sub(r'^\|.+\|$', '', t, flags=_re.MULTILINE)   # table rows
            t = _re.sub(r'^[-|:]+$', '', t, flags=_re.MULTILINE)    # table separators
            t = _re.sub(r'\n{3,}', '\n\n', t)
            return t.strip()

        for m in meetings_with_minutes:
            num   = m.get("meeting_number", "?")
            title = _p(m.get("title", ""))
            dt    = _p(m.get("meeting_date") or "—")

            # Meeting header
            pdf.set_fill_color(15, 32, 64)
            pdf.set_font("Helvetica", "B", 10)
            set_accent()
            pdf.cell(10, 7, str(num), fill=True, border=0)
            set_white()
            pdf.cell(W - 10, 7, f"  {title[:80]}", fill=True, border=0, ln=True)
            pdf.set_font("Helvetica", "", 8)
            set_muted()
            pdf.set_x(20)
            pdf.cell(W, 5, _p(f"   Data: {dt}"), ln=True)
            pdf.ln(1)

            # Minutes content — iterate lines
            clean_text = _strip_md(m["minutes_md"])
            for line in clean_text.splitlines():
                line = line.rstrip()
                if not line:
                    pdf.ln(2)
                    continue
                pdf.set_font("Helvetica", "", 8)
                set_body()
                pdf.set_x(20)
                pdf.multi_cell(W, 4.5, _p(line))

            pdf.ln(6)

    return bytes(pdf.output())
