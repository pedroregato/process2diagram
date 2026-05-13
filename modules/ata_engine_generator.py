# modules/ata_engine_generator.py
# =============================================================================
# ATA Engine HTML Generator — Process2Diagram Integration
# FGV/DTI · Equipe SOLCORP
#
# Converts MinutesModel + roster data into a standalone interactive HTML file
# that mirrors the ATA Engine design system:
#   - Participant chips with colour badges (sidebar + hero strip)
#   - Topic cards with decisions per topic
#   - Action items table with localStorage persistence
#   - Base64 self-embedding for encapsulated export (works via file://)
#
# Public API:
#   generate_ata_html(minutes, project_id, meeting_id, project_slug,
#                     meeting_date, local, next_meeting, next_meeting_detail) -> str
# =============================================================================

from __future__ import annotations

import base64
import html as _html
from datetime import date, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.knowledge_hub import MinutesModel


# ── helpers ───────────────────────────────────────────────────────────────────

def _e(text: str) -> str:
    """HTML-escape a string."""
    return _html.escape(str(text or ""), quote=True)


def _slug_keys(slug: str, d: date) -> tuple[str, str, str]:
    """Return the three localStorage key bases for a given slug + date."""
    base = f"{slug}_{d.year}_{d.month:02d}_{d.day:02d}_v1"
    return base, base + "_meta", base + "_comments"


def _b64(html_str: str) -> str:
    return base64.b64encode(html_str.encode("utf-8")).decode("ascii")


# ── public entry point ────────────────────────────────────────────────────────

def generate_ata_html(
    minutes: "MinutesModel",
    project_id: str = "",
    meeting_id: str = "",
    project_slug: str = "p2d",
    meeting_date: date | None = None,
    local: str = "Videoconferência",
    next_meeting: str = "",
    next_meeting_detail: str = "",
) -> str:
    """
    Generate a standalone interactive ATA Engine HTML from a MinutesModel.

    The HTML:
    - Embeds all CSS + JS inline (no external dependencies)
    - Uses localStorage for action item status + comments persistence
    - Supports export: generates a new self-contained HTML with state baked in
    - Works via file:// protocol
    """
    if meeting_date is None:
        meeting_date = date.today()

    slug = (project_slug or "p2d").lower()
    key_main, key_meta, key_comments = _slug_keys(slug, meeting_date)

    # ── Resolve participants ───────────────────────────────────────────────────
    participants = _resolve_participants(minutes, project_id, meeting_id)

    # ── Build action items JS array ───────────────────────────────────────────
    action_items_js = _build_action_items_js(minutes)

    # ── Build sections HTML ───────────────────────────────────────────────────
    sidebar_chips_html  = _render_sidebar_chips(participants)
    hero_chips_html     = _render_hero_chips(participants)
    topics_html         = _render_topics(minutes)
    next_meeting_html   = _render_next_meeting(next_meeting, next_meeting_detail)

    # ── Metadata ──────────────────────────────────────────────────────────────
    date_str  = meeting_date.strftime("%d/%m/%Y")
    title     = _e(minutes.title or "Ata de Reunião")
    location  = _e(local or minutes.location or "Videoconferência")
    n_actions = len(minutes.action_items) if minutes.action_items else 0
    n_decided = len(minutes.decisions) if minutes.decisions else 0

    # ── Assemble HTML (plain string substitution — avoids .format() brace conflicts) ──
    html_body = _TEMPLATE
    for placeholder, value in [
        ("{{TITLE}}",          title),
        ("{{DATE_STR}}",       date_str),
        ("{{LOCATION}}",       location),
        ("{{N_ACTIONS}}",      str(n_actions)),
        ("{{N_DECIDED}}",      str(n_decided)),
        ("{{SLUG}}",           slug),
        ("{{KEY_MAIN}}",       key_main),
        ("{{KEY_META}}",       key_meta),
        ("{{KEY_COMMENTS}}",   key_comments),
        ("{{SIDEBAR_CHIPS}}",  sidebar_chips_html),
        ("{{HERO_CHIPS}}",     hero_chips_html),
        ("{{TOPICS}}",         topics_html),
        ("{{NEXT_MEETING}}",   next_meeting_html),
        ("{{ACTION_ITEMS_JS}}", action_items_js),
        ("{{EXPORT_JS}}",      _EXPORT_JS),
    ]:
        html_body = html_body.replace(placeholder, value)

    # ── Embed Base64 snapshot for encapsulated export ─────────────────────────
    return _embed_b64_source(html_body)


# ── participant resolution ────────────────────────────────────────────────────

def _resolve_participants(minutes: "MinutesModel", project_id: str, meeting_id: str) -> list[dict]:
    """
    Resolve participant list: try roster first, fall back to minutes.participants strings.
    Returns list of dicts with: initials, full_name, area, color_hex.
    """
    if project_id and meeting_id:
        try:
            from core.project_store import get_meeting_participants_roster, infer_and_save_participants
            roster_participants = get_meeting_participants_roster(meeting_id)
            if roster_participants:
                return roster_participants
            # No confirmed participants yet — infer from transcript names
            names = getattr(minutes, "participants", []) or []
            if names:
                return infer_and_save_participants(names, project_id, meeting_id)
        except Exception:
            pass

    # Fallback: build temporary participants from minutes.participants strings
    _ATA_COLORS = ["0B1E3D", "1A4B8C", "1A7F5A", "C97B1A", "6B3FA0", "2E7FD9"]
    result = []
    for i, name in enumerate(getattr(minutes, "participants", []) or []):
        parts = str(name).strip().split()
        if len(parts) >= 2:
            ini = (parts[0][0] + parts[1][0]).upper()
        elif parts:
            ini = parts[0][:2].upper()
        else:
            continue
        result.append({
            "initials":  ini,
            "full_name": str(name).strip(),
            "area":      None,
            "color_hex": _ATA_COLORS[i % len(_ATA_COLORS)],
        })
    return result


# ── component renderers ───────────────────────────────────────────────────────

def _render_sidebar_chips(participants: list[dict]) -> str:
    if not participants:
        return '<p class="no-participants">Nenhum participante registrado.</p>'
    chips = []
    for p in participants:
        ini   = _e(p.get("initials", "?"))
        name  = _e((p.get("full_name") or "").split()[0] if p.get("full_name") else ini)
        color = p.get("color_hex", "8496B0")
        area  = _e(p.get("area") or "")
        chips.append(
            f'<button class="part-chip" data-initials="{ini}" data-color="{color}" '
            f'title="{_e(p.get("full_name",""))}{ " · " + area if area else ""}">'
            f'<span class="part-initials" style="background:#{color}">{ini}</span>'
            f'<span class="part-name">{name}</span>'
            f'<span class="part-count" id="pcount-{ini}">0</span>'
            f'</button>'
        )
    return "\n".join(chips)


def _render_hero_chips(participants: list[dict]) -> str:
    chips = []
    for p in participants:
        ini   = _e(p.get("initials", "?"))
        name  = _e(p.get("full_name") or ini)
        color = p.get("color_hex", "8496B0")
        area  = _e(p.get("area") or "")
        chips.append(
            f'<span class="participant-chip" style="border-color:#{color}" '
            f'title="{name}{ " · " + area if area else ""}">'
            f'<span class="pchip-ini" style="background:#{color}">{ini}</span>'
            f'<span class="pchip-name">{name}</span>'
            f'</span>'
        )
    return "\n".join(chips)


def _render_topics(minutes: "MinutesModel") -> str:
    """Build topic cards from summary blocks + decisions grouped by topic."""
    blocks = getattr(minutes, "summary", []) or []
    decisions_all = list(getattr(minutes, "decisions", []) or [])

    if not blocks and not decisions_all:
        return '<p class="no-topics">Sem tópicos registrados.</p>'

    html_parts = []

    if blocks:
        for idx, block in enumerate(blocks, start=1):
            topic   = _e(block.get("topic") or f"Tópico {idx}")
            content = _e(block.get("content") or "")
            html_parts.append(
                f'<div class="topic-card" data-topic="{idx}">'
                f'<div class="topic-header"><span class="topic-num">{idx}</span>'
                f'<span class="topic-title">{topic}</span></div>'
                f'<div class="topic-body"><p>{content}</p></div>'
                f'</div>'
            )
    elif decisions_all:
        # No summary blocks — show all decisions in a single card
        items = "".join(f"<li>{_e(d)}</li>" for d in decisions_all)
        html_parts.append(
            f'<div class="topic-card" data-topic="1">'
            f'<div class="topic-header"><span class="topic-num">1</span>'
            f'<span class="topic-title">Decisões e Pontos Discutidos</span></div>'
            f'<div class="topic-body"><ul class="decision-list">{items}</ul></div>'
            f'</div>'
        )

    return "\n".join(html_parts)


def _render_next_meeting(next_meeting: str, detail: str) -> str:
    if not next_meeting:
        return ""
    return (
        f'<div class="next-meeting-card">'
        f'<span class="next-label">Próxima reunião</span>'
        f'<span class="next-date">{_e(next_meeting)}</span>'
        f'{"<span class=next-detail>" + _e(detail) + "</span>" if detail else ""}'
        f'</div>'
    )


def _build_action_items_js(minutes: "MinutesModel") -> str:
    """Serialize action_items to a JS array literal."""
    items = getattr(minutes, "action_items", []) or []
    if not items:
        return "[]"
    rows = []
    for i, ai in enumerate(items, start=1):
        task  = str(getattr(ai, "task", "") or "").replace("\\", "\\\\").replace('"', '\\"')
        resp  = str(getattr(ai, "responsible", "") or "—").replace('"', '\\"')
        prazo = str(getattr(ai, "deadline", "") or "A definir").replace('"', '\\"')
        rows.append(
            f'  {{"id":{i},"desc":"{task}","resp":"{resp}","prazo":"{prazo}","status":"open"}}'
        )
    return "[\n" + ",\n".join(rows) + "\n]"


# ── Base64 self-embedding ─────────────────────────────────────────────────────

_SNAPSHOT_RESTORE_JS = """<script id="__snapshot_restore__">
(function(){
  try {
    var src = document.getElementById('__src__');
    if (!src) return;
    var b64 = src.textContent.trim();
    if (!b64) return;
    // Snapshot source is available — export button will use it as base template
    window.__ATA_SRC_B64__ = b64;
  } catch(e) {}
})();
'<' + '/script>'
</script>""".replace("'<' + '/script>'\n</script>", "</script>")

_EXPORT_JS = """
function exportAta() {
  try {
    var b64src = window.__ATA_SRC_B64__;
    if (!b64src) { alert('Fonte não disponível para exportação.'); return; }
    var baseHtml = decodeURIComponent(escape(atob(b64src)));

    // Inject current localStorage state as inline script
    var stateScript = '<script id="__inject_state__">\\n';
    stateScript += 'try {\\n';
    for (var k in localStorage) {
      if (localStorage.hasOwnProperty(k)) {
        var val = localStorage.getItem(k).replace(/\\\\/g,'\\\\\\\\').replace(/'/g,"\\\\'");
        stateScript += "  localStorage.setItem('" + k.replace(/'/g, "\\\\'") + "','" + val + "');\\n";
      }
    }
    stateScript += '} catch(e) {}\\n';
    stateScript += '<' + '/script>';

    var now = new Date();
    var stamp = now.getFullYear() + '-' +
      String(now.getMonth()+1).padStart(2,'0') + '-' +
      String(now.getDate()).padStart(2,'0');

    // Embed state right before </body>
    var exported = baseHtml.replace('</body>', stateScript + '\\n</body>');
    var newB64 = btoa(unescape(encodeURIComponent(exported)));
    exported = exported.replace(
      /<script id="__src__"[^>]*>[\\s\\S]*?<\\/script>/,
      '<script id="__src__" type="text/plain">' + newB64 + '<' + '/script>'
    );

    var blob = new Blob([exported], {type: 'text/html;charset=utf-8'});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = document.title.replace(/\\s+/g,'_') + '_compartilhado_' + stamp + '.html';
    a.click();
  } catch(e) {
    alert('Erro ao exportar: ' + e.message);
  }
}
"""


def _embed_b64_source(html_str: str) -> str:
    """Embed the HTML as Base64 inside a <script id='__src__'> block for export chaining."""
    b64 = _b64(html_str)
    src_block = f'<script id="__src__" type="text/plain">{b64}<' + "/script>"
    return html_str.replace("</head>", f"{_SNAPSHOT_RESTORE_JS}\n{src_block}\n</head>", 1)


# ── HTML template ─────────────────────────────────────────────────────────────
# Placeholders use {{NAME}} syntax — replaced via str.replace(), not str.format().
# This avoids conflicts with CSS/JS curly braces.

_TEMPLATE = """\
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{TITLE}}</title>
<style>
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
:root {
  --navy:    #0F172A;
  --amber:   #C97B1A;
  --bg:      #0B1120;
  --surface: #111827;
  --surface2:#1E2A3B;
  --border:  #1E3A55;
  --text:    #E2EAF4;
  --muted:   #8496B0;
  --radius:  8px;
  --sidebar: 220px;
}
body { font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--text);
       display: flex; min-height: 100vh; }
a { color: var(--amber); text-decoration: none; }

.sidebar {
  width: var(--sidebar); min-height: 100vh; background: var(--surface);
  border-right: 1px solid var(--border); display: flex; flex-direction: column;
  position: fixed; top: 0; left: 0; bottom: 0; overflow-y: auto; z-index: 100;
}
.sidebar-header { padding: 20px 16px 12px; border-bottom: 1px solid var(--border); }
.sidebar-title { font-size: 11px; font-weight: 700; color: var(--muted);
                 text-transform: uppercase; letter-spacing: .08em; }
.sidebar-subtitle { font-size: 13px; font-weight: 600; color: var(--text); margin-top: 4px; }
.sidebar-date { font-size: 11px; color: var(--muted); margin-top: 2px; }
.part-section { padding: 12px 16px; border-bottom: 1px solid var(--border); }
.part-section-label { font-size: 10px; font-weight: 700; color: var(--muted);
                      text-transform: uppercase; letter-spacing: .08em; margin-bottom: 8px; }
.part-chip {
  display: flex; align-items: center; gap: 8px; width: 100%;
  padding: 6px 8px; border: none; background: transparent; cursor: pointer;
  border-radius: var(--radius); color: var(--text); text-align: left;
  transition: background .15s; margin-bottom: 2px;
}
.part-chip:hover, .part-chip.active { background: var(--surface2); }
.part-initials {
  display: inline-flex; align-items: center; justify-content: center;
  width: 28px; height: 28px; border-radius: 6px; font-size: 11px;
  font-weight: 700; color: #fff; flex-shrink: 0;
}
.part-name { font-size: 12px; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.part-count {
  font-size: 10px; font-weight: 700; background: var(--surface2);
  color: var(--amber); padding: 1px 5px; border-radius: 10px; min-width: 18px; text-align: center;
}
.sidebar-nav { padding: 12px 8px; flex: 1; }
.nav-item {
  display: flex; align-items: center; gap: 8px; padding: 7px 8px;
  border-radius: var(--radius); font-size: 12px; color: var(--muted);
  cursor: pointer; transition: all .15s; text-decoration: none;
}
.nav-item:hover { color: var(--text); background: var(--surface2); }
.nav-item.active { color: var(--amber); background: rgba(201,123,26,.1); }
.sidebar-footer { padding: 12px 16px; border-top: 1px solid var(--border); }
.export-btn {
  width: 100%; padding: 8px; background: var(--amber); color: #fff;
  border: none; border-radius: var(--radius); font-size: 12px; font-weight: 700;
  cursor: pointer; transition: opacity .15s;
}
.export-btn:hover { opacity: .85; }

.main { margin-left: var(--sidebar); flex: 1; display: flex; flex-direction: column; }
.hero {
  background: linear-gradient(135deg, #0B1E3D 0%, #0F172A 100%);
  border-bottom: 2px solid var(--amber); padding: 28px 36px 20px;
}
.hero-badge {
  display: inline-block; font-size: 10px; font-weight: 700; letter-spacing: .1em;
  text-transform: uppercase; color: var(--amber); border: 1px solid var(--amber);
  padding: 2px 8px; border-radius: 4px; margin-bottom: 10px;
}
.hero h1 { font-size: 22px; font-weight: 700; color: #fff; margin-bottom: 6px; line-height: 1.3; }
.hero-meta { display: flex; gap: 24px; flex-wrap: wrap; margin-bottom: 14px; }
.hero-meta-item { font-size: 12px; color: var(--muted); }
.hero-meta-item strong { color: var(--text); }
.hero-chips { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
.participant-chip {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 3px 10px 3px 4px; border-radius: 20px;
  border: 1px solid #333; background: rgba(255,255,255,.04); font-size: 11px; color: var(--text);
}
.pchip-ini {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 50%; font-size: 9px; font-weight: 700; color: #fff;
}
.pchip-name { max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

.content { padding: 28px 36px; display: flex; flex-direction: column; gap: 28px; }
.section-title {
  font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .1em;
  color: var(--muted); margin-bottom: 14px; padding-bottom: 6px;
  border-bottom: 1px solid var(--border);
}
.topic-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); overflow: hidden;
}
.topic-header {
  display: flex; align-items: center; gap: 10px;
  padding: 10px 16px; background: var(--surface2); cursor: pointer;
  border-bottom: 1px solid var(--border);
}
.topic-num {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 50%; background: var(--amber);
  color: #fff; font-size: 11px; font-weight: 700; flex-shrink: 0;
}
.topic-title { font-size: 13px; font-weight: 600; flex: 1; }
.topic-body { padding: 14px 16px; font-size: 13px; line-height: 1.6; }
.topic-body.hidden { display: none; }
.topic-card.collapsed .topic-body { display: none; }
.decision-list { padding-left: 18px; display: flex; flex-direction: column; gap: 6px; }
.decision-list li { color: var(--text); }
.no-topics, .no-participants { color: var(--muted); font-size: 12px; font-style: italic; padding: 8px; }

.actions-table-wrap { overflow-x: auto; }
table.ai-table { width: 100%; border-collapse: collapse; font-size: 12px; }
table.ai-table th {
  padding: 8px 12px; background: var(--surface2); color: var(--muted);
  font-weight: 700; text-transform: uppercase; font-size: 10px; letter-spacing: .06em;
  border-bottom: 1px solid var(--border); text-align: left;
}
table.ai-table td { padding: 9px 12px; border-bottom: 1px solid var(--border); vertical-align: top; }
table.ai-table tr:last-child td { border-bottom: none; }
table.ai-table tr:hover td { background: rgba(255,255,255,.02); }
.status-badge {
  display: inline-block; padding: 2px 8px; border-radius: 10px;
  font-size: 10px; font-weight: 700; cursor: pointer; user-select: none;
}
.status-badge.open     { background: rgba(201,123,26,.2); color: #E8A338; border: 1px solid rgba(201,123,26,.3); }
.status-badge.done     { background: rgba(26,127,90,.2);  color: #3ABA86; border: 1px solid rgba(26,127,90,.3); }
.status-badge.canceled { background: rgba(100,116,139,.2);color: var(--muted); border: 1px solid rgba(100,116,139,.3); }
.ai-desc { color: var(--text); }
.ai-resp { color: var(--muted); font-weight: 500; }
.ai-prazo { color: var(--muted); white-space: nowrap; }
.no-actions { color: var(--muted); font-size: 12px; font-style: italic; padding: 12px 0; }
.next-meeting-card {
  background: rgba(201,123,26,.08); border: 1px solid rgba(201,123,26,.3);
  border-radius: var(--radius); padding: 14px 18px; display: flex; align-items: center; gap: 14px;
}
.next-label { font-size: 10px; font-weight: 700; text-transform: uppercase;
              letter-spacing: .08em; color: var(--amber); }
.next-date { font-size: 14px; font-weight: 600; color: var(--text); }
.next-detail { font-size: 12px; color: var(--muted); }
.filter-bar { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px; }
.filter-chip {
  padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600;
  cursor: pointer; border: 1px solid var(--border); color: var(--muted);
  background: transparent; transition: all .15s;
}
.filter-chip:hover { color: var(--text); border-color: var(--text); }
.filter-chip.active { background: var(--amber); color: #fff; border-color: var(--amber); }
.stats-bar {
  display: flex; gap: 20px; flex-wrap: wrap; background: var(--surface2);
  padding: 10px 36px; border-bottom: 1px solid var(--border); font-size: 12px;
}
.stat-item { color: var(--muted); }
.stat-item strong { color: var(--text); margin-right: 4px; }
</style>
</head>
<body>

<aside class="sidebar">
  <div class="sidebar-header">
    <div class="sidebar-title">Ata de Reuniao</div>
    <div class="sidebar-subtitle">{{TITLE}}</div>
    <div class="sidebar-date">{{DATE_STR}}</div>
  </div>
  <div class="part-section">
    <div class="part-section-label">Participantes</div>
    {{SIDEBAR_CHIPS}}
  </div>
  <nav class="sidebar-nav">
    <a class="nav-item active" href="#topics">Topicos</a>
    <a class="nav-item" href="#actions">Pendencias</a>
    <a class="nav-item" href="#next">Proxima</a>
  </nav>
  <div class="sidebar-footer">
    <button class="export-btn" onclick="exportAta()">Exportar copia</button>
  </div>
</aside>

<main class="main">
  <div class="hero">
    <div class="hero-badge">Ata Oficial</div>
    <h1>{{TITLE}}</h1>
    <div class="hero-meta">
      <div class="hero-meta-item">Data: <strong>{{DATE_STR}}</strong></div>
      <div class="hero-meta-item">Local: <strong>{{LOCATION}}</strong></div>
      <div class="hero-meta-item">Pendencias: <strong>{{N_ACTIONS}}</strong></div>
      <div class="hero-meta-item">Decisoes: <strong>{{N_DECIDED}}</strong></div>
    </div>
    <div class="hero-chips">{{HERO_CHIPS}}</div>
  </div>

  <div class="stats-bar">
    <span class="stat-item"><strong id="stat-open">-</strong> em aberto</span>
    <span class="stat-item"><strong id="stat-done">-</strong> concluidas</span>
    <span class="stat-item"><strong id="stat-total">{{N_ACTIONS}}</strong> total</span>
  </div>

  <div class="content">
    <section id="topics">
      <div class="section-title">Topicos da Reuniao</div>
      {{TOPICS}}
    </section>

    <section id="actions">
      <div class="section-title">Pendencias e Action Items</div>
      <div class="filter-bar">
        <button class="filter-chip active" onclick="applyFilter(this,'all')">Todas</button>
        <button class="filter-chip" onclick="applyFilter(this,'open')">Em aberto</button>
        <button class="filter-chip" onclick="applyFilter(this,'done')">Concluidas</button>
        <button class="filter-chip" onclick="applyFilter(this,'canceled')">Canceladas</button>
      </div>
      <div class="actions-table-wrap">
        <table class="ai-table" id="ai-table">
          <thead><tr><th>#</th><th>Pendencia</th><th>Responsavel</th><th>Prazo</th><th>Status</th></tr></thead>
          <tbody id="ai-tbody"></tbody>
        </table>
        <p class="no-actions" id="no-actions-msg" style="display:none">Nenhuma pendencia registrada.</p>
      </div>
    </section>

    <section id="next">
      <div class="section-title">Proxima Reuniao</div>
      {{NEXT_MEETING}}
    </section>
  </div>
</main>

<script>
const ORIGINAL = {{ACTION_ITEMS_JS}};
const STORAGE_KEY = '{{KEY_MAIN}}';
let items = JSON.parse(JSON.stringify(ORIGINAL));
let activeFilter = 'all';

function loadState() {
  try {
    var saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      var parsed = JSON.parse(saved);
      items = items.map(function(item) {
        var s = parsed.find(function(p) { return p.id === item.id; });
        return s ? Object.assign({}, item, {status: s.status}) : item;
      });
    }
  } catch(e) {}
}

function saveState() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items.map(function(i) {
      return {id: i.id, status: i.status};
    })));
  } catch(e) {}
}

function renderTable() {
  var tbody = document.getElementById('ai-tbody');
  var noMsg = document.getElementById('no-actions-msg');
  if (!ORIGINAL.length) {
    document.getElementById('ai-table').style.display = 'none';
    noMsg.style.display = 'block';
    return;
  }
  var filtered = activeFilter === 'all' ? items : items.filter(function(i) { return i.status === activeFilter; });
  tbody.innerHTML = '';
  var labels = {open: 'Em aberto', done: 'Concluido', canceled: 'Cancelado'};
  filtered.forEach(function(item) {
    var tr = document.createElement('tr');
    tr.setAttribute('data-id', item.id);
    tr.innerHTML =
      '<td style="color:var(--muted);width:30px">' + item.id + '</td>' +
      '<td class="ai-desc">' + item.desc + '</td>' +
      '<td class="ai-resp">' + item.resp + '</td>' +
      '<td class="ai-prazo">' + item.prazo + '</td>' +
      '<td><span class="status-badge ' + item.status + '" onclick="cycleStatus(' + item.id + ')">' +
        (labels[item.status] || item.status) + '</span></td>';
    tbody.appendChild(tr);
  });
  updateStats();
}

function cycleStatus(id) {
  var cycle = {open:'done', done:'canceled', canceled:'open'};
  var item = items.find(function(i) { return i.id === id; });
  if (item) { item.status = cycle[item.status] || 'open'; saveState(); renderTable(); updateCounts(); }
}

function applyFilter(btn, filter) {
  activeFilter = filter;
  document.querySelectorAll('.filter-chip').forEach(function(c) { c.classList.remove('active'); });
  btn.classList.add('active');
  renderTable();
}

function updateStats() {
  var open = items.filter(function(i) { return i.status === 'open'; }).length;
  var done = items.filter(function(i) { return i.status === 'done'; }).length;
  var el_open = document.getElementById('stat-open');
  var el_done = document.getElementById('stat-done');
  if (el_open) el_open.textContent = open;
  if (el_done) el_done.textContent = done;
}

function updateCounts() {
  document.querySelectorAll('.part-chip').forEach(function(chip) {
    var ini = chip.dataset.initials;
    var countEl = document.getElementById('pcount-' + ini);
    if (!countEl) return;
    var count = items.filter(function(i) { return i.resp && i.resp.toUpperCase().indexOf(ini) >= 0; }).length;
    countEl.textContent = count;
  });
}

document.querySelectorAll('.topic-header').forEach(function(header) {
  header.addEventListener('click', function() {
    var card = header.closest('.topic-card');
    card.classList.toggle('collapsed');
  });
});

loadState();
renderTable();
updateCounts();

{{EXPORT_JS}}
</script>
</body>
</html>
"""
