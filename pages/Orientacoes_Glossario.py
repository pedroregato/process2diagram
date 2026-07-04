# pages/Orientacoes_Glossario.py
# ─────────────────────────────────────────────────────────────────────────────
# Glossário técnico interativo do Process2Diagram.
# Layout inspirado no pedro-lab/metodologia/glossario.html:
#   • Header escuro com contador de verbetes
#   • Barra de busca sticky em tempo real
#   • Filtros por categoria (bpmn | req | ai | dev | neg)
#   • Índice alfabético lateral sticky
#   • Verbetes com coluna esquerda (termo, inglês, tag) + coluna direita (def, exemplo, ver também)
# Renderizado via st.components.v1.html() para suportar JavaScript interativo.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
import streamlit.components.v1 as components

from ui.auth_gate import apply_auth_gate
from modules.glossary_data import GLOSSARY_ENTRIES, TAG_META

apply_auth_gate()


# ─────────────────────────────────────────────────────────────────────────────
# Build HTML
# ─────────────────────────────────────────────────────────────────────────────

def _build_glossary_html() -> str:
    """Generate the full standalone HTML for the interactive glossary."""

    # ── Serialize ENTRIES to JS ───────────────────────────────────────────────
    js_entries: list[dict] = []
    for e in GLOSSARY_ENTRIES:
        js_entries.append({
            "term":    e["term"],
            "en":      e.get("en", ""),
            "tag":     e.get("tag", ""),
            "def":     e.get("def_", ""),
            "example": e.get("example", ""),
            "related": e.get("related", []),
        })
    entries_json = json.dumps(js_entries, ensure_ascii=False, indent=2)

    # ── Filter buttons HTML ───────────────────────────────────────────────────
    filter_buttons = '<button class="filter-btn fb-all active" onclick="filtrar(\'all\', this)">Todos</button>\n'
    for slug, meta in TAG_META.items():
        label = f"{meta['emoji']} {meta['label']}"
        filter_buttons += (
            f'  <button class="filter-btn fb-{slug}" '
            f'onclick="filtrar(\'{slug}\', this)">{label}</button>\n'
        )

    # ── CSS vars for category colors ──────────────────────────────────────────
    css_cat_vars = "\n".join(
        f"  --{slug}: {meta['color']};"
        for slug, meta in TAG_META.items()
    )

    # ── CSS active states for filter buttons ──────────────────────────────────
    css_active_states = "\n".join(
        f".fb-{slug}.active {{ background: var(--{slug}); }}"
        for slug in TAG_META
    )

    # ── CSS tag badge classes ─────────────────────────────────────────────────
    def _hex_to_rgba(hex_color: str, alpha: float) -> str:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    css_tag_classes = ""
    for slug, meta in TAG_META.items():
        bg  = _hex_to_rgba(meta["color"], 0.10)
        brd = _hex_to_rgba(meta["color"], 0.22)
        css_tag_classes += (
            f".tag-{slug} {{ "
            f"background: {bg}; "
            f"color: var(--{slug}); "
            f"border: 1px solid {brd}; }}\n"
        )

    total = len(GLOSSARY_ENTRIES)
    n_cats = len(TAG_META)
    version = "v5.15"

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Glossário · Process2Diagram</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&family=IBM+Plex+Mono:wght@300;400&display=swap');

  :root {{
    --bg:     #f8f5ef;
    --s1:     #ffffff;
    --s2:     #f0ece2;
    --s3:     #e4ded2;
    --border: #d4cec0;
    --ink:    #1e1a12;
    --muted:  #8a8070;
    --dim:    #b8b0a0;

    {css_cat_vars}

    --serif: 'Libre Baskerville', Georgia, serif;
    --mono:  'IBM Plex Mono', monospace;
  }}

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html {{ scroll-behavior: smooth; }}

  body {{
    background: var(--bg);
    color: var(--ink);
    font-family: var(--serif);
    font-size: 14px;
    line-height: 1.85;
  }}

  /* ── HEADER ── */
  header {{
    background: var(--ink);
    color: #f8f5ef;
    padding: 48px 64px 36px;
    position: relative;
    overflow: hidden;
  }}
  header::after {{
    content: 'G';
    position: absolute;
    right: 40px; bottom: -80px;
    font-family: var(--serif);
    font-size: 320px;
    font-weight: 700; font-style: italic;
    color: rgba(255,255,255,.03);
    pointer-events: none;
    line-height: 1;
  }}
  .h-label {{
    font-family: var(--mono);
    font-size: 10px; letter-spacing: .18em;
    text-transform: uppercase; color: rgba(248,245,239,.4);
    margin-bottom: 10px;
  }}
  header h1 {{
    font-size: clamp(32px, 5.5vw, 58px);
    font-weight: 700; font-style: italic;
    line-height: 1.05; letter-spacing: -.02em;
    color: #fff; margin-bottom: 12px;
  }}
  header h1 span {{ color: #c8a44a; font-style: normal; }}
  .h-sub {{
    font-family: var(--mono);
    font-size: 11.5px; color: rgba(248,245,239,.42);
    max-width: 540px; line-height: 1.7;
  }}
  .h-stats {{
    margin-top: 22px;
    display: flex; gap: 24px; flex-wrap: wrap;
    font-family: var(--mono); font-size: 10.5px;
    color: rgba(248,245,239,.28);
  }}

  /* ── PESQUISA ── */
  .search-bar {{
    background: var(--s1); border-bottom: 1px solid var(--border);
    padding: 14px 64px; position: sticky; top: 0; z-index: 100;
    display: flex; gap: 12px; align-items: center;
  }}
  .search-input {{
    flex: 1; background: var(--s2); border: 1px solid var(--border);
    border-radius: 2px; padding: 8px 14px;
    font-family: var(--mono); font-size: 13px; color: var(--ink);
    transition: border-color .12s;
  }}
  .search-input:focus {{ outline: none; border-color: var(--ink); }}
  .search-input::placeholder {{ color: var(--dim); }}
  .search-count {{
    font-family: var(--mono); font-size: 11px; color: var(--muted);
    white-space: nowrap; min-width: 80px; text-align: right;
  }}

  /* ── FILTROS ── */
  .filters {{
    background: var(--s2); border-bottom: 1px solid var(--border);
    padding: 10px 64px; display: flex; gap: 7px; flex-wrap: wrap;
  }}
  .filter-btn {{
    font-family: var(--mono); font-size: 9.5px;
    letter-spacing: .08em; text-transform: uppercase;
    padding: 4px 11px; border-radius: 1px;
    border: 1px solid var(--border); background: transparent;
    color: var(--muted); cursor: pointer; transition: all .12s;
    white-space: nowrap;
  }}
  .filter-btn:hover {{ color: var(--ink); border-color: var(--ink); }}
  .filter-btn.active {{ color: #fff; border-color: transparent; }}
  .fb-all.active {{ background: var(--ink); color: #fff; }}
  {css_active_states}

  /* ── LAYOUT ── */
  .layout {{
    display: grid;
    grid-template-columns: 196px 1fr;
    min-height: calc(100vh - 200px);
  }}

  /* ── ÍNDICE LATERAL ── */
  nav {{
    border-right: 1px solid var(--border);
    padding: 18px 0;
    position: sticky; top: 97px;
    height: calc(100vh - 97px);
    overflow-y: auto;
    background: var(--s1);
  }}
  nav::-webkit-scrollbar {{ width: 3px; }}
  nav::-webkit-scrollbar-thumb {{ background: var(--border); }}
  .nav-label {{
    padding: 4px 18px 2px;
    font-family: var(--mono); font-size: 9px;
    letter-spacing: .14em; text-transform: uppercase; color: var(--dim);
  }}
  .nav-letter {{
    display: block; padding: 4px 18px;
    font-family: var(--serif); font-size: 15px; font-weight: 700;
    color: var(--muted); text-decoration: none;
    transition: color .1s; cursor: pointer;
  }}
  .nav-letter:hover {{ color: var(--ink); }}
  .nav-letter.has-entries {{ color: var(--ink); }}

  /* ── CONTEÚDO ── */
  .content {{ padding: 0 56px 64px; }}

  /* ── LETRA ── */
  .letter-section {{ margin-top: 36px; }}
  .letter-heading {{
    font-size: clamp(44px, 7vw, 74px);
    font-weight: 700; font-style: italic;
    color: var(--s3); line-height: 1;
    margin-bottom: 14px; padding-bottom: 10px;
    border-bottom: 2px solid var(--border);
    letter-spacing: -.02em;
  }}

  /* ── VERBETE ── */
  .entry {{
    padding: 18px 0;
    border-bottom: 1px solid var(--border);
    display: grid;
    grid-template-columns: 210px 1fr;
    gap: 22px;
    transition: background .1s;
  }}
  .entry:last-child {{ border-bottom: none; }}
  .entry:hover {{ background: rgba(0,0,0,.01); }}

  .entry-left {{ padding-top: 2px; }}
  .entry-term {{
    font-size: 16px; font-weight: 700;
    color: var(--ink); line-height: 1.2; margin-bottom: 5px;
  }}
  .entry-en {{
    font-family: var(--mono); font-size: 10px;
    color: var(--dim); font-style: normal;
    margin-bottom: 8px; display: block;
  }}
  .entry-tag {{
    display: inline-block;
    font-family: var(--mono); font-size: 8.5px;
    letter-spacing: .1em; text-transform: uppercase;
    padding: 2px 7px; border-radius: 1px;
  }}
  {css_tag_classes}

  .entry-def {{
    font-size: 13px; color: #4a4438; line-height: 1.88;
    margin-bottom: 9px;
  }}
  .entry-def strong {{ color: var(--ink); font-weight: 700; }}
  .entry-def em {{ font-style: italic; color: var(--muted); }}

  .entry-example {{
    background: var(--s2); border-left: 3px solid var(--border);
    padding: 9px 13px; margin-top: 9px;
    font-size: 12px; color: var(--muted);
    font-style: italic; line-height: 1.75;
  }}
  .entry-example::before {{
    content: 'Exemplo: ';
    font-family: var(--mono); font-size: 9px;
    letter-spacing: .1em; text-transform: uppercase;
    color: var(--dim); font-style: normal; display: block;
    margin-bottom: 3px;
  }}

  .entry-related {{
    margin-top: 9px; display: flex; align-items: center; gap: 7px;
    flex-wrap: wrap;
  }}
  .er-label {{
    font-family: var(--mono); font-size: 9px;
    letter-spacing: .1em; text-transform: uppercase; color: var(--dim);
  }}
  .er-link {{
    font-family: var(--mono); font-size: 10.5px;
    color: var(--bpmn); text-decoration: underline;
    text-underline-offset: 3px; cursor: pointer;
    transition: color .1s;
  }}
  .er-link:hover {{ color: var(--ink); }}

  /* ── SEM RESULTADOS ── */
  .no-results {{
    padding: 48px 0; text-align: center;
    font-family: var(--mono); font-size: 13px; color: var(--dim);
    display: none;
  }}

  /* ── RESPONSIVO ── */
  @media (max-width: 720px) {{
    header {{ padding: 28px 18px; }}
    .search-bar, .filters {{ padding: 10px 16px; }}
    .layout {{ grid-template-columns: 1fr; }}
    nav {{ display: none; }}
    .content {{ padding: 0 16px 48px; }}
    .entry {{ grid-template-columns: 1fr; gap: 8px; }}
  }}
</style>
</head>
<body>

<header>
  <div class="h-label">Process2Diagram · Ajuda</div>
  <h1><span>Glossário</span> de Termos</h1>
  <div class="h-sub">
    Termos técnicos, conceitos, especificações e boas práticas de mercado do Process2Diagram —
    BPMN, requisitos, IA, infraestrutura e metodologias de análise de negócios.
  </div>
  <div class="h-stats">
    <span id="total-count">— verbetes</span>
    <span>{n_cats} categorias</span>
    <span>Process2Diagram · {version}</span>
  </div>
</header>

<div class="search-bar">
  <input class="search-input" id="search" type="text"
    placeholder="Buscar termo, sigla ou conceito..." oninput="buscar()">
  <span class="search-count" id="result-count"></span>
</div>

<div class="filters">
  {filter_buttons}
</div>

<div class="layout">

<nav id="nav-index">
  <div class="nav-label">Índice</div>
</nav>

<div class="content" id="glossary-content">
  <div class="no-results" id="no-results">Nenhum termo encontrado para esta busca.</div>
</div>

</div>

<script>
const ENTRIES = {entries_json};

const TAG_LABEL = {{
  bpmn: "Modelagem & BPMN",
  req:  "Requisitos & Spec",
  ai:   "IA & LLM",
  dev:  "Dev & Infra",
  neg:  "Negócios",
}};

let activeFilter = 'all';

/* ── render(entries) ─────────────────────────────────────────── */
function render(entries) {{
  const content = document.getElementById('glossary-content');
  const noRes   = document.getElementById('no-results');
  const nav     = document.getElementById('nav-index');

  // Keep the no-results sentinel in the DOM
  content.innerHTML = '';
  content.appendChild(noRes);

  if (entries.length === 0) {{
    noRes.style.display = 'block';
    rebuildNav([]);
    document.getElementById('result-count').textContent = '0 resultado';
    return;
  }}
  noRes.style.display = 'none';

  // Group by first letter
  const groups = {{}};
  entries.forEach(e => {{
    const letter = e.term[0].toUpperCase();
    if (!groups[letter]) groups[letter] = [];
    groups[letter].push(e);
  }});

  const letters = Object.keys(groups).sort();
  letters.forEach(letter => {{
    const section = document.createElement('div');
    section.className = 'letter-section';
    section.id = 'letter-' + letter;

    const heading = document.createElement('div');
    heading.className = 'letter-heading';
    heading.textContent = letter;
    section.appendChild(heading);

    groups[letter].forEach(e => {{
      section.appendChild(buildEntry(e));
    }});

    content.appendChild(section);
  }});

  rebuildNav(letters);

  const n = entries.length;
  document.getElementById('result-count').textContent =
    n + (n === 1 ? ' resultado' : ' resultados');
}}

/* ── buildEntry(e) ───────────────────────────────────────────── */
function buildEntry(e) {{
  const div = document.createElement('div');
  div.className = 'entry';

  const enHtml   = e.en ? `<span class="entry-en">${{e.en}}</span>` : '';
  const tagLabel = TAG_LABEL[e.tag] || e.tag;

  const exHtml = e.example
    ? `<div class="entry-example">${{e.example}}</div>`
    : '';

  const relHtml = (e.related && e.related.length)
    ? `<div class="entry-related">
        <span class="er-label">Ver também:</span>
        ${{e.related.map(r =>
          `<span class="er-link" onclick="searchTerm('${{r.replace(/'/g,"\\\\'")}}')">${{r}}</span>`
        ).join('')}}
       </div>`
    : '';

  div.innerHTML = `
    <div class="entry-left">
      <div class="entry-term">${{e.term}}</div>
      ${{enHtml}}
      <span class="entry-tag tag-${{e.tag}}">${{tagLabel}}</span>
    </div>
    <div class="entry-right">
      <div class="entry-def">${{e.def}}</div>
      ${{exHtml}}
      ${{relHtml}}
    </div>
  `;
  return div;
}}

/* ── rebuildNav(letters) ─────────────────────────────────────── */
function rebuildNav(activeLetters) {{
  const nav = document.getElementById('nav-index');
  // Remove all letter links (keep the label)
  Array.from(nav.querySelectorAll('.nav-letter')).forEach(el => el.remove());

  const ALL = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');
  const activeSet = new Set(activeLetters);

  ALL.forEach(letter => {{
    const a = document.createElement('span');
    a.className = 'nav-letter' + (activeSet.has(letter) ? ' has-entries' : '');
    a.textContent = letter;
    if (activeSet.has(letter)) {{
      a.onclick = () => {{
        const el = document.getElementById('letter-' + letter);
        if (el) el.scrollIntoView({{behavior: 'smooth', block: 'start'}});
      }};
    }}
    nav.appendChild(a);
  }});
}}

/* ── buscar() ────────────────────────────────────────────────── */
function buscar() {{
  const q = document.getElementById('search').value.toLowerCase().trim();
  let pool = activeFilter === 'all'
    ? ENTRIES
    : ENTRIES.filter(e => e.tag === activeFilter);

  if (!q) {{
    render(pool);
    return;
  }}

  const results = pool.filter(e => {{
    const hay = [
      e.term,
      e.en,
      e.def.replace(/<[^>]+>/g, ''),
      e.example,
      (e.related || []).join(' '),
    ].join(' ').toLowerCase();
    return hay.includes(q);
  }});
  render(results);
}}

/* ── filtrar(tag, btn) ───────────────────────────────────────── */
function filtrar(tag, btn) {{
  activeFilter = tag;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  buscar();
}}

/* ── searchTerm(term) ────────────────────────────────────────── */
function searchTerm(term) {{
  activeFilter = 'all';
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  document.querySelector('.fb-all').classList.add('active');
  const input = document.getElementById('search');
  input.value = term;
  buscar();
  document.querySelector('.search-bar').scrollIntoView({{behavior: 'smooth'}});
}}

/* ── Init ────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {{
  document.getElementById('total-count').textContent = ENTRIES.length + ' verbetes';
  render(ENTRIES);
}});
</script>
</body>
</html>"""


# ─────────────────────────────────────────────────────────────────────────────
# Render
# ─────────────────────────────────────────────────────────────────────────────

html = _build_glossary_html()
components.html(html, height=860, scrolling=True)
