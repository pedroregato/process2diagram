# modules/sbvr_lexicon.py
from __future__ import annotations
import html
import re
import unicodedata


def _slug(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text.lower())
    ascii_str = nfkd.encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_str).strip("-")


_CAT_LABEL = {
    "concept":   "Conceito",
    "fact_type": "Tipo de Fato",
    "role":      "Papel",
    "process":   "Processo",
}

_CAT_COLOR = {
    "concept":   "#1a3a5c",
    "fact_type": "#b45309",
    "role":      "#065f46",
    "process":   "#5b21b6",
}

_RULE_TYPE_LABEL = {
    "constraint":  "Restrição",
    "operational": "Operacional",
    "behavioral":  "Comportamental",
    "structural":  "Estrutural",
}

_RULE_TYPE_COLOR = {
    "constraint":  "#991b1b",
    "operational": "#1e40af",
    "behavioral":  "#065f46",
    "structural":  "#5b21b6",
}


def _cross_ref(definition: str, term_slugs: dict[str, str]) -> str:
    result = definition
    for term_lower, slug in sorted(term_slugs.items(), key=lambda x: -len(x[0])):
        pattern = re.compile(re.escape(term_lower), re.IGNORECASE)
        def replacer(m, _slug=slug):
            return (
                f'<a class="xref" href="#{_slug}" '
                f'onclick="highlightTerm(\'{_slug}\')">'
                f'{html.escape(m.group(0))}</a>'
            )
        result = pattern.sub(replacer, result)
    return result


def generate_sbvr_lexicon(sbvr_model, project_name: str = "") -> str:
    domain        = getattr(sbvr_model, "domain", "") or ""
    vocab         = list(getattr(sbvr_model, "vocabulary", []) or [])
    rules         = list(getattr(sbvr_model, "rules", []) or [])
    vocab_sorted  = sorted(vocab, key=lambda t: t.term.strip().upper())

    term_slugs: dict[str, str] = {
        t.term.strip().lower(): "term-" + _slug(t.term)
        for t in vocab_sorted if t.term.strip()
    }

    rules_by_term: dict[str, list] = {t.term.strip(): [] for t in vocab_sorted}
    for r in rules:
        nucleo = getattr(r, "short_title", "") or getattr(r, "nucleo_nominal", "") or ""
        stmt   = r.statement or ""
        for t in vocab_sorted:
            tname = t.term.strip()
            if tname.lower() in nucleo.lower() or tname.lower() in stmt.lower():
                rules_by_term[tname].append(r)

    letters_present: set[str] = set()
    for t in vocab_sorted:
        first = t.term.strip()[0].upper() if t.term.strip() else ""
        if first.isalpha():
            letters_present.add(first)

    cards_html     = ""
    current_letter = ""

    for t in vocab_sorted:
        tname        = t.term.strip()
        slug_id      = "term-" + _slug(tname)
        cat          = t.category or "concept"
        cat_label    = _CAT_LABEL.get(cat, cat)
        cat_color    = _CAT_COLOR.get(cat, "#374151")
        first_letter = tname[0].upper() if tname else ""

        if first_letter != current_letter and first_letter.isalpha():
            current_letter = first_letter
            cards_html += f'<div class="letter-divider" id="letter-{current_letter}">{current_letter}</div>\n'

        defn_safe     = html.escape(t.definition or "")
        slugs_no_self = {k: v for k, v in term_slugs.items() if k != tname.lower()}
        defn_linked   = _cross_ref(defn_safe, slugs_no_self)

        related       = rules_by_term.get(tname, [])
        rules_section = ""
        if related:
            rule_items = ""
            for r in related[:6]:
                rt_color = _RULE_TYPE_COLOR.get(r.rule_type, "#374151")
                rt_label = _RULE_TYPE_LABEL.get(r.rule_type, r.rule_type or "")
                src_note = f" <span class='rule-source'>↳ {html.escape(r.source)}</span>" if r.source else ""
                rule_items += (
                    f'<li class="rule-item">'
                    f'<span class="rule-badge" style="background:{rt_color}">{html.escape(rt_label)}</span>'
                    f' <span class="rule-id">{html.escape(r.id)}</span>'
                    f' {html.escape(r.statement or "")}{src_note}'
                    f'</li>\n'
                )
            rules_section = (
                f'<div class="related-rules">'
                f'<h4>Regras relacionadas</h4><ul>{rule_items}</ul></div>'
            )

        cards_html += (
            f'<article class="term-card" id="{slug_id}" '
            f'data-letter="{first_letter}" '
            f'data-category="{html.escape(cat)}" '
            f'data-searchtext="{html.escape(tname.lower())} {html.escape((t.definition or "").lower())}">\n'
            f'  <div class="term-header">\n'
            f'    <h2 class="term-name">{html.escape(tname)}</h2>\n'
            f'    <span class="cat-badge" style="background:{cat_color}">{html.escape(cat_label)}</span>\n'
            f'  </div>\n'
            f'  <p class="term-def">{defn_linked}</p>\n'
            f'  {rules_section}\n'
            f'</article>\n'
        )

    rules_html = ""
    for r in rules:
        rt_color = _RULE_TYPE_COLOR.get(r.rule_type, "#374151")
        rt_label = _RULE_TYPE_LABEL.get(r.rule_type, r.rule_type or "")
        src_note = f'<span class="rule-source">Proposto por: {html.escape(r.source)}</span>' if r.source else ""
        rules_html += (
            f'<div class="rule-card" '
            f'data-searchtext="{html.escape((r.id or "").lower())} {html.escape((r.statement or "").lower())}">\n'
            f'  <div class="rule-card-header">\n'
            f'    <span class="rule-id-large">{html.escape(r.id or "")}</span>\n'
            f'    <span class="rule-badge-large" style="background:{rt_color}">{html.escape(rt_label)}</span>\n'
            f'    {src_note}\n'
            f'  </div>\n'
            f'  <p class="rule-statement">{html.escape(r.statement or "")}</p>\n'
            f'</div>\n'
        )

    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    az_nav   = ""
    for letter in alphabet:
        active = "az-active" if letter in letters_present else "az-inactive"
        click  = f'filterByLetter("{letter}")' if letter in letters_present else ""
        az_nav += (
            f'<button class="az-btn {active}" onclick="{click}" title="{letter}">{letter}</button>'
        )

    n_terms    = len(vocab_sorted)
    n_rules    = len(rules)
    subtitle   = f"{domain} — " if domain else ""
    subtitle  += f"{n_terms} termo{'s' if n_terms != 1 else ''} · {n_rules} regra{'s' if n_rules != 1 else ''}"
    page_title = f"Léxico SBVR · {project_name}" if project_name else "Léxico SBVR"

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(page_title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@600;700&family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{
  --navy:   #1a2e4a;
  --amber:  #d97706;
  --bg:     #f7f5f0;
  --card:   #ffffff;
  --border: #e2ddd6;
  --text:   #1f2937;
  --muted:  #6b7280;
  --shadow: 0 1px 4px rgba(0,0,0,.08);
}}
body {{ font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }}
header {{ background: var(--navy); color: #fff; padding: 2.5rem 2rem 2rem; text-align: center; }}
header h1 {{ font-family: 'Playfair Display', serif; font-size: clamp(1.6rem, 4vw, 2.6rem); letter-spacing: .02em; margin-bottom: .4rem; }}
header .subtitle {{ font-size: .9rem; opacity: .75; font-weight: 300; letter-spacing: .04em; text-transform: uppercase; }}
header .stats-bar {{ display: flex; justify-content: center; gap: 2rem; margin-top: 1.2rem; font-size: .82rem; opacity: .85; }}
header .stats-bar span {{ display: flex; align-items: center; gap: .4rem; }}
.sticky-nav {{ position: sticky; top: 0; z-index: 100; background: #fff; border-bottom: 1px solid var(--border); box-shadow: 0 2px 8px rgba(0,0,0,.06); }}
.nav-inner {{ max-width: 1100px; margin: 0 auto; padding: .75rem 1.5rem; display: flex; flex-direction: column; gap: .6rem; }}
.search-row {{ display: flex; gap: .75rem; align-items: center; }}
.search-box {{ flex: 1; padding: .55rem 1rem; border: 1.5px solid var(--border); border-radius: 8px; font-family: inherit; font-size: .92rem; outline: none; transition: border-color .2s; }}
.search-box:focus {{ border-color: var(--navy); }}
.tab-row {{ display: flex; gap: .4rem; flex-wrap: wrap; }}
.tab-btn {{ padding: .3rem .85rem; border: 1.5px solid var(--border); border-radius: 20px; background: transparent; font-family: inherit; font-size: .8rem; cursor: pointer; color: var(--muted); transition: all .18s; }}
.tab-btn:hover {{ border-color: var(--navy); color: var(--navy); }}
.tab-btn.active {{ background: var(--navy); color: #fff; border-color: var(--navy); }}
.section-toggle {{ padding: .3rem .85rem; border: 1.5px solid var(--border); border-radius: 20px; background: transparent; font-family: inherit; font-size: .8rem; cursor: pointer; color: var(--muted); margin-left: auto; transition: all .18s; }}
.section-toggle.active {{ background: var(--amber); color: #fff; border-color: var(--amber); }}
.az-strip {{ background: #f0ede8; border-bottom: 1px solid var(--border); padding: .4rem 1.5rem; display: flex; justify-content: center; flex-wrap: wrap; gap: 2px; }}
.az-btn {{ width: 28px; height: 28px; border: none; border-radius: 5px; font-family: 'Playfair Display', serif; font-size: .85rem; font-weight: 600; cursor: default; background: transparent; }}
.az-active {{ color: var(--navy); cursor: pointer; }}
.az-active:hover {{ background: var(--navy); color: #fff; }}
.az-inactive {{ color: #c4bdb4; }}
main {{ max-width: 1100px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }}
.section-title {{ font-family: 'Playfair Display', serif; font-size: 1.4rem; color: var(--navy); border-bottom: 2px solid var(--amber); padding-bottom: .4rem; margin: 2rem 0 1.2rem; }}
.letter-divider {{ font-family: 'Playfair Display', serif; font-size: 2rem; font-weight: 700; color: var(--navy); border-bottom: 1px solid var(--border); padding: 1.2rem 0 .3rem; margin: 1.5rem 0 .8rem; scroll-margin-top: 130px; opacity: .35; }}
.term-card {{ background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 1.4rem 1.6rem; margin-bottom: 1rem; box-shadow: var(--shadow); scroll-margin-top: 130px; transition: box-shadow .2s, border-color .2s; }}
.term-card:target, .term-card.highlight {{ border-color: var(--amber); box-shadow: 0 0 0 3px rgba(217,119,6,.15); }}
.term-header {{ display: flex; align-items: baseline; gap: .8rem; flex-wrap: wrap; margin-bottom: .7rem; }}
.term-name {{ font-family: 'Playfair Display', serif; font-size: 1.25rem; color: var(--navy); }}
.cat-badge {{ font-size: .72rem; font-weight: 600; color: #fff; padding: .18rem .6rem; border-radius: 12px; letter-spacing: .04em; text-transform: uppercase; }}
.term-def {{ font-size: .95rem; color: #374151; line-height: 1.7; margin-bottom: .6rem; }}
.xref {{ color: var(--navy); text-decoration: underline; text-decoration-style: dotted; text-underline-offset: 3px; cursor: pointer; font-weight: 500; }}
.xref:hover {{ color: var(--amber); text-decoration-style: solid; }}
.related-rules {{ margin-top: .9rem; padding-top: .8rem; border-top: 1px dashed var(--border); }}
.related-rules h4 {{ font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; color: var(--muted); margin-bottom: .5rem; }}
.related-rules ul {{ list-style: none; display: flex; flex-direction: column; gap: .45rem; }}
.rule-item {{ font-size: .85rem; color: #374151; display: flex; gap: .5rem; align-items: flex-start; flex-wrap: wrap; }}
.rule-badge {{ font-size: .68rem; font-weight: 600; color: #fff; padding: .15rem .5rem; border-radius: 10px; white-space: nowrap; flex-shrink: 0; margin-top: .1rem; }}
.rule-id {{ font-family: monospace; font-size: .8rem; color: var(--muted); flex-shrink: 0; }}
.rule-source {{ color: var(--amber); font-size: .8rem; font-style: italic; }}
.rule-card {{ background: var(--card); border: 1px solid var(--border); border-left: 4px solid var(--navy); border-radius: 8px; padding: 1.2rem 1.4rem; margin-bottom: .9rem; box-shadow: var(--shadow); }}
.rule-card-header {{ display: flex; align-items: center; gap: .75rem; flex-wrap: wrap; margin-bottom: .6rem; }}
.rule-id-large {{ font-family: monospace; font-size: .95rem; font-weight: 600; color: var(--navy); }}
.rule-badge-large {{ font-size: .72rem; font-weight: 600; color: #fff; padding: .18rem .6rem; border-radius: 12px; letter-spacing: .04em; text-transform: uppercase; }}
.rule-statement {{ font-size: .93rem; color: #374151; line-height: 1.65; }}
.empty-state {{ text-align: center; padding: 3rem 1rem; color: var(--muted); font-size: .95rem; }}
#no-match-vocab, #no-match-rules {{ display: none; }}
#no-match-vocab.visible, #no-match-rules.visible {{ display: block; text-align: center; padding: 2.5rem; color: var(--muted); font-size: .93rem; }}
footer {{ text-align: center; padding: 1.5rem; font-size: .78rem; color: #9ca3af; border-top: 1px solid var(--border); margin-top: 2rem; }}
</style>
</head>
<body>
<header>
  <h1>📖 {html.escape(page_title)}</h1>
  <p class="subtitle">{html.escape(subtitle)}</p>
  <div class="stats-bar">
    <span>🏷️ {n_terms} Termos</span>
    <span>📋 {n_rules} Regras</span>
  </div>
</header>
<nav class="sticky-nav">
  <div class="nav-inner">
    <div class="search-row">
      <input class="search-box" id="searchBox" type="search"
             placeholder="🔍  Buscar termo ou definição…"
             oninput="onSearch()" autocomplete="off">
      <button class="section-toggle" id="toggleRules" onclick="toggleRulesSection()">
        📋 Ver Regras
      </button>
    </div>
    <div class="tab-row">
      <button class="tab-btn active" onclick="filterByCategory('all')">Todos</button>
      <button class="tab-btn" onclick="filterByCategory('concept')"   style="color:#1a3a5c;border-color:#1a3a5c">Conceito</button>
      <button class="tab-btn" onclick="filterByCategory('fact_type')" style="color:#b45309;border-color:#b45309">Tipo de Fato</button>
      <button class="tab-btn" onclick="filterByCategory('role')"      style="color:#065f46;border-color:#065f46">Papel</button>
      <button class="tab-btn" onclick="filterByCategory('process')"   style="color:#5b21b6;border-color:#5b21b6">Processo</button>
    </div>
  </div>
</nav>
<div class="az-strip">{az_nav}</div>
<main>
  <section id="vocab-section">
    <h2 class="section-title">Vocabulário de Negócio</h2>
    <div id="vocab-list">
      {cards_html if cards_html else '<div class="empty-state">Nenhum termo disponível.</div>'}
    </div>
    <p id="no-match-vocab" class="empty-state">Nenhum termo encontrado para esta busca.</p>
  </section>
  <section id="rules-section" style="display:none">
    <h2 class="section-title">Regras de Negócio</h2>
    <input class="search-box" id="rulesSearchBox" type="search"
           placeholder="🔍  Buscar regra…"
           oninput="onRulesSearch()" autocomplete="off"
           style="margin-bottom:1.2rem;width:100%;max-width:500px;">
    <div id="rules-list">
      {rules_html if rules_html else '<div class="empty-state">Nenhuma regra disponível.</div>'}
    </div>
    <p id="no-match-rules" class="empty-state">Nenhuma regra encontrada para esta busca.</p>
  </section>
</main>
<footer>Gerado por Process2Diagram · SBVR Léxico Interativo</footer>
<script>
let currentCategory = 'all';
let currentLetter   = '';
let currentQuery    = '';
let rulesVisible    = false;

function applyVocabFilter() {{
  const cards   = document.querySelectorAll('#vocab-list .term-card');
  const divs    = document.querySelectorAll('#vocab-list .letter-divider');
  const query   = currentQuery.trim().toLowerCase();
  let   visible = 0;
  cards.forEach(card => {{
    const catOk    = currentCategory === 'all' || card.dataset.category === currentCategory;
    const letterOk = !currentLetter || card.dataset.letter === currentLetter;
    const queryOk  = !query || (card.dataset.searchtext || '').includes(query);
    const show = catOk && letterOk && queryOk;
    card.style.display = show ? '' : 'none';
    if (show) visible++;
  }});
  divs.forEach(div => {{
    const letter = div.id.replace('letter-', '');
    const hasVisible = [...cards].some(c => c.dataset.letter === letter && c.style.display !== 'none');
    div.style.display = hasVisible ? '' : 'none';
  }});
  const noMatch = document.getElementById('no-match-vocab');
  if (noMatch) noMatch.classList.toggle('visible', visible === 0 && cards.length > 0);
}}

function onSearch() {{
  currentQuery  = document.getElementById('searchBox').value;
  currentLetter = '';
  applyVocabFilter();
}}

function filterByCategory(cat) {{
  currentCategory = cat;
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  applyVocabFilter();
}}

function filterByLetter(letter) {{
  if (currentLetter === letter) {{ currentLetter = ''; }}
  else {{
    currentLetter = letter;
    document.getElementById('searchBox').value = '';
    currentQuery = '';
  }}
  applyVocabFilter();
  if (currentLetter) {{
    const target = document.getElementById('letter-' + letter);
    if (target) target.scrollIntoView({{behavior: 'smooth', block: 'start'}});
  }}
}}

function onRulesSearch() {{
  const query = document.getElementById('rulesSearchBox').value.trim().toLowerCase();
  const cards = document.querySelectorAll('#rules-list .rule-card');
  let visible = 0;
  cards.forEach(card => {{
    const show = !query || (card.dataset.searchtext || '').includes(query);
    card.style.display = show ? '' : 'none';
    if (show) visible++;
  }});
  const noMatch = document.getElementById('no-match-rules');
  if (noMatch) noMatch.classList.toggle('visible', visible === 0 && cards.length > 0);
}}

function toggleRulesSection() {{
  rulesVisible = !rulesVisible;
  document.getElementById('vocab-section').style.display = rulesVisible ? 'none' : '';
  document.getElementById('rules-section').style.display = rulesVisible ? '' : 'none';
  const btn = document.getElementById('toggleRules');
  btn.textContent = rulesVisible ? '📚 Ver Vocabulário' : '📋 Ver Regras';
  btn.classList.toggle('active', rulesVisible);
}}

function highlightTerm(slugId) {{
  document.querySelectorAll('.term-card.highlight').forEach(c => c.classList.remove('highlight'));
  const target = document.getElementById(slugId);
  if (!target) return;
  if (rulesVisible) toggleRulesSection();
  currentCategory = 'all'; currentLetter = ''; currentQuery = '';
  document.getElementById('searchBox').value = '';
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelector('.tab-btn').classList.add('active');
  applyVocabFilter();
  setTimeout(() => {{
    target.scrollIntoView({{behavior: 'smooth', block: 'center'}});
    target.classList.add('highlight');
    setTimeout(() => target.classList.remove('highlight'), 2500);
  }}, 80);
}}
</script>
</body>
</html>"""
