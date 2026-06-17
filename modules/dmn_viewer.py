# modules/dmn_viewer.py
# ─────────────────────────────────────────────────────────────────────────────
# Visual DMN decision table renderer — OMG DMN 1.4 style.
# Dark theme, color-coded input/output columns, hit policy badge, row pinning.
# No CDN — pure CSS + vanilla JS.
#
# Public API:
#   render_dmn_model(model: DMNModel, height=600) → None  (Streamlit component)
#   render_dmn_page(decisions: list[dict]) → str           (Artefatos.py / dict format)
#   estimate_height(decisions: list[dict]) → int
#   dmn_to_xml(model: DMNModel) → str                     (XML export — unchanged)
# ─────────────────────────────────────────────────────────────────────────────
from __future__ import annotations

import html as _html
from core.knowledge_hub import DMNModel, DMNDecision


# ── Hit policy metadata ───────────────────────────────────────────────────────

_HIT_POLICY = {
    "U": ("#1d4ed8", "UNIQUE",      "Apenas uma regra se aplica por vez"),
    "A": ("#7c3aed", "ANY",         "Qualquer regra satisfeita; mesmo resultado"),
    "F": ("#b45309", "FIRST",       "Primeira regra satisfeita vence"),
    "C": ("#065f46", "COLLECT",     "Todas as regras satisfeitas são coletadas"),
    "R": ("#9f1239", "RULE ORDER",  "Regras ordenadas por prioridade"),
    "P": ("#0369a1", "PRIORITY",    "Saída com maior prioridade vence"),
}


def _e(v: object) -> str:
    return _html.escape(str(v or ""))


# ── Shared CSS ────────────────────────────────────────────────────────────────

_CSS = """
<style>
*, *::before, *::after { box-sizing: border-box; }
body {
    background: #0d1b2a;
    color: #e2e8f0;
    font-family: 'Segoe UI', system-ui, sans-serif;
    margin: 0;
    padding: 10px 12px 16px;
}
.dec-block { margin-bottom: 28px; }
.dec-header {
    display: flex; align-items: baseline; gap: 12px;
    margin-bottom: 8px;
    border-bottom: 1px solid #1e3a55; padding-bottom: 6px;
}
.dec-name   { font-size: .95rem; font-weight: 700; color: #f1f5f9; }
.dec-origin { font-size: .78rem; color: #475569; }

/* Context panel */
.ctx-panel {
    padding: 8px 14px; background: #0f2235;
    border-left: 3px solid #2563eb;
    border-radius: 0 6px 6px 0; margin-bottom: 8px;
}
.ctx-q  { font-size: .87rem; font-weight: 600; color: #93c5fd; margin-bottom: 3px; }
.ctx-r  { font-size: .8rem; color: #94a3b8; margin-bottom: 3px; }
.ctx-by { font-size: .8rem; color: #94a3b8; }
.chip {
    display: inline-block; background: #1e3a5f; color: #93c5fd;
    border-radius: 10px; padding: 0 7px; margin: 0 2px; font-size: .76rem;
}

/* Table wrapper */
.dmn-wrap { overflow-x: auto; border: 1px solid #1e3a55; border-radius: 8px; }

/* Table */
.dmn-tbl { width: 100%; border-collapse: collapse; font-size: .84rem; }

/* Hit-policy cell (vertical text) */
.hp-cell {
    width: 44px; min-width: 44px; text-align: center;
    vertical-align: middle; padding: 4px 2px;
    border-right: 2px solid rgba(255,255,255,.18);
}
.hp-txt {
    display: block; font-weight: 800; font-size: .68rem;
    letter-spacing: .06em; color: #fff;
    writing-mode: vertical-rl; transform: rotate(180deg); white-space: nowrap;
}

/* Group header */
.gh-inp {
    background: #1a3561; color: #93c5fd; text-align: center;
    font-size: .76rem; font-weight: 600; padding: 4px 8px;
    border-right: 2px solid #2d5fa8; border-bottom: 1px solid #2d5fa8;
}
.gh-out {
    background: #3b2200; color: #fbbf24; text-align: center;
    font-size: .76rem; font-weight: 600; padding: 4px 8px;
    border-right: 2px solid #92400e; border-bottom: 1px solid #92400e;
}
.gh-ann {
    background: #131e2b; color: #475569; text-align: center;
    font-size: .76rem; font-weight: 600; padding: 4px 8px;
    border-bottom: 1px solid #1e3a55;
}

/* Column label row */
.ch-inp {
    background: #112443; color: #60a5fa; padding: 6px 10px;
    border-right: 1px solid #1e3a55; border-bottom: 2px solid #2d5fa8; white-space: nowrap;
}
.ch-out {
    background: #201000; color: #fbbf24; padding: 6px 10px;
    border-right: 1px solid #1e3a55; border-bottom: 2px solid #92400e; white-space: nowrap;
}
.col-lbl  { font-weight: 600; }
.col-expr { font-size: .73rem; color: #475569; font-style: italic; margin-top: 1px; }

/* Number column */
.num-cell {
    color: #475569; text-align: center; font-size: .76rem;
    padding: 5px 8px; background: #0d1b2a;
    border-right: 1px solid #1e3a55; border-bottom: 1px solid #1e2a35;
    min-width: 32px; user-select: none;
}
/* Data cells */
.inp-cell {
    padding: 6px 10px;
    border-right: 1px solid #1e3a55; border-bottom: 1px solid #1e2a35;
    color: #cbd5e1; font-family: 'Cascadia Code','Fira Mono',monospace; font-size: .82rem;
}
.out-cell {
    padding: 6px 10px;
    border-right: 1px solid #1e3a55; border-bottom: 1px solid #1e2a35;
    color: #fcd34d; font-weight: 600; border-left: 2px solid #92400e;
}
.ann-cell {
    padding: 6px 10px; border-bottom: 1px solid #1e2a35;
    color: #64748b; font-style: italic; font-size: .79rem;
}
.dash { color: #334155; }

/* Row hover / pin */
.rule-row { cursor: pointer; transition: background .1s; }
.rule-row:hover .inp-cell,
.rule-row:hover .out-cell,
.rule-row:hover .ann-cell,
.rule-row:hover .num-cell { background: rgba(37,99,235,.14); }
.rule-row.pinned .inp-cell,
.rule-row.pinned .out-cell,
.rule-row.pinned .ann-cell { background: rgba(37,99,235,.28); }
.rule-row.pinned .num-cell  { color: #60a5fa; font-weight: 700; }

/* Footer */
.dec-footer { display: flex; align-items: center; gap: 10px; margin-top: 6px; padding: 0 2px; }
.dec-id   { font-size: .75rem; color: #334155; font-family: monospace; }
.hp-desc  { font-size: .75rem; color: #475569; }
.conf-hi  { font-size: .75rem; background: #064e3b; color: #34d399; border-radius: 4px; padding: 1px 7px; }
.conf-md  { font-size: .75rem; background: #451a03; color: #fbbf24; border-radius: 4px; padding: 1px 7px; }
.conf-lo  { font-size: .75rem; background: #450a0a; color: #f87171; border-radius: 4px; padding: 1px 7px; }
.empty { color: #475569; text-align: center; padding: 16px; font-style: italic; }
</style>
"""

_JS = "<script>function togglePin(r){r.classList.toggle('pinned');}</script>"


# ── Core table builder (works on plain dict) ──────────────────────────────────

def _build_table_html(d: dict, table_id: str = "t0") -> tuple[str, str, str]:
    """Return (table_html, hp_short, hp_desc)."""
    inputs  = d.get("inputs")  or []
    outputs = d.get("outputs") or []
    rules   = d.get("rules")   or []
    hp      = (d.get("hit_policy") or "U").strip().upper()

    hp_color, hp_short, hp_desc = _HIT_POLICY.get(hp, ("#374151", hp, hp))
    n_inp = max(len(inputs), 1)
    n_out = max(len(outputs), 1)

    # Group header row
    group_row = (
        f'<tr>'
        f'<th class="hp-cell" rowspan="2" style="background:{hp_color}" title="{_e(hp_desc)}">'
        f'<span class="hp-txt">{_e(hp_short)}</span></th>'
        f'<th class="gh-inp" colspan="{n_inp}">Entradas (Inputs)</th>'
        f'<th class="gh-out" colspan="{n_out}">Saídas (Outputs)</th>'
        f'<th class="gh-ann" rowspan="2">Anotação</th>'
        f'</tr>'
    )

    # Column label row
    inp_cols = "".join(
        f'<th class="ch-inp">'
        f'<div class="col-lbl">{_e(i.get("label", f"Input {j+1}"))}</div>'
        + (f'<div class="col-expr">{_e(i["expression"])}</div>' if i.get("expression") else "")
        + f'</th>'
        for j, i in enumerate(inputs or [{"label": "Input", "expression": ""}])
    )
    out_cols = "".join(
        f'<th class="ch-out"><div class="col-lbl">{_e(o.get("label", f"Output {k+1}"))}</div></th>'
        for k, o in enumerate(outputs or [{"label": "Output", "value": ""}])
    )
    col_row = f'<tr>{inp_cols}{out_cols}</tr>'

    # Data rows
    rows_html = ""
    for idx, rule in enumerate(rules, 1):
        r_inp = rule.get("inputs") or []
        r_out = rule.get("output", "")
        r_ann = rule.get("annotation", "")

        inp_cells = "".join(
            f'<td class="inp-cell">'
            + (_any_val(r_inp[j] if j < len(r_inp) else ""))
            + f'</td>'
            for j in range(n_inp)
        )
        out_cells = (
            f'<td class="out-cell">{_e(r_out) or "<span class=dash>—</span>"}</td>'
            + "".join(f'<td class="out-cell"><span class="dash">—</span></td>' for _ in range(n_out - 1))
        )
        ann_cell = f'<td class="ann-cell">{_e(r_ann)}</td>'

        rows_html += (
            f'<tr class="rule-row" onclick="togglePin(this)">'
            f'<td class="num-cell">{idx}</td>'
            f'{inp_cells}{out_cells}{ann_cell}'
            f'</tr>'
        )

    if not rows_html:
        total = 1 + n_inp + n_out + 1
        rows_html = f'<tr><td colspan="{total}" class="empty">Nenhuma regra registrada.</td></tr>'

    tbl = (
        f'<div class="dmn-wrap">'
        f'<table class="dmn-tbl">'
        f'<thead>{group_row}{col_row}</thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table></div>'
    )
    return tbl, hp_short, hp_desc


def _any_val(v: str) -> str:
    """Render a cell value; treat blank and '-' as any-value dash."""
    v = v.strip() if v else ""
    if not v or v == "-":
        return '<span class="dash">—</span>'
    return _e(v)


def _ctx_html(d: dict) -> str:
    parts = []
    if d.get("question"):
        parts.append(f'<div class="ctx-q">❓ {_e(d["question"])}</div>')
    if d.get("rationale"):
        parts.append(f'<div class="ctx-r">📝 {_e(d["rationale"])}</div>')
    if d.get("decided_by"):
        chips = "".join(f'<span class="chip">{_e(p)}</span>' for p in d["decided_by"])
        parts.append(f'<div class="ctx-by">👥 {chips}</div>')
    return f'<div class="ctx-panel">{"".join(parts)}</div>' if parts else ""


def _footer_html(d: dict, hp_short: str, hp_desc: str) -> str:
    dec_id = d.get("id", "")
    conf   = float(d.get("confidence") or 1.0)
    pct    = int(conf * 100)
    cls    = "conf-hi" if conf >= 0.85 else ("conf-md" if conf >= 0.65 else "conf-lo")
    return (
        f'<div class="dec-footer">'
        + (f'<span class="dec-id">{_e(dec_id)}</span>' if dec_id else "")
        + f'<span class="hp-desc">Política: {_e(hp_short)} — {_e(hp_desc)}</span>'
        + f'<span class="{cls}">Confiança {pct}%</span>'
        + f'</div>'
    )


def _decision_block(d: dict, i: int, show_origin: bool = False) -> str:
    name    = d.get("name", f"Decisão {i + 1}")
    m_num   = d.get("_meeting_number")
    m_title = d.get("_meeting_title", "")
    origin  = ""
    if show_origin and m_num:
        origin = f"Reunião {m_num}" + (f" — {m_title}" if m_title else "")

    header = (
        f'<div class="dec-header">'
        f'<span class="dec-name">{_e(name)}</span>'
        + (f'<span class="dec-origin">🗓️ {_e(origin)}</span>' if origin else "")
        + f'</div>'
    )
    ctx           = _ctx_html(d)
    tbl, hp_s, hp_d = _build_table_html(d, table_id=f"t{i}")
    foot          = _footer_html(d, hp_s, hp_d)
    return f'<div class="dec-block">{header}{ctx}{tbl}{foot}</div>'


# ── Public: dict-based (Artefatos.py) ────────────────────────────────────────

def render_dmn_page(decisions: list[dict], show_origin: bool = True) -> str:
    """Return a complete self-contained HTML page with all DMN decision tables.

    Intended for ``streamlit.components.v1.html()``.
    decisions — list of dicts from ``project_store.list_dmn_by_project``.
    """
    if not decisions:
        return (
            f"{_CSS}{_JS}"
            "<div class='empty' style='padding:40px;font-size:.9rem;'>"
            "Nenhuma tabela de decisão DMN disponível.</div>"
        )
    blocks = [_decision_block(d, i, show_origin=show_origin) for i, d in enumerate(decisions)]
    return f"{_CSS}{_JS}" + "\n".join(blocks)


def estimate_height(decisions: list[dict]) -> int:
    """Estimate iframe height in pixels for a list of decisions."""
    if not decisions:
        return 120
    total = 40
    for d in decisions:
        n_rules = len(d.get("rules") or [])
        has_ctx = bool(d.get("question") or d.get("rationale") or d.get("decided_by"))
        total += 60                        # dec-header + footer + margins
        total += 68 if has_ctx else 0      # context panel
        total += 62                        # table header (2 rows)
        total += max(n_rules, 1) * 34      # rule rows
        total += 28                        # bottom margin between decisions
    return min(total + 20, 2000)


# ── Public: DMNModel-based (Pipeline dmn_tab.py) ─────────────────────────────

def _model_to_dicts(model: DMNModel) -> list[dict]:
    """Convert DMNModel dataclass to list of plain dicts for the shared renderer."""
    result = []
    for d in model.decisions:
        result.append({
            "id":         d.id,
            "name":       d.name,
            "question":   d.question,
            "rationale":  d.rationale,
            "decided_by": d.decided_by,
            "hit_policy": d.hit_policy,
            "confidence": d.confidence,
            "inputs":  [{"label": i.label, "expression": i.expression} for i in d.inputs],
            "outputs": [{"label": o.label, "value": o.value} for o in d.outputs],
            "rules":   [{"inputs": r.inputs, "output": r.output, "annotation": r.annotation}
                        for r in d.rules],
        })
    return result


def render_dmn_model(model: DMNModel, height: int = 600) -> None:
    """Render a DMNModel as an interactive visual component in Streamlit.

    Used by ui/tabs/dmn_tab.py for the Pipeline DMN tab.
    """
    import streamlit as st
    from streamlit.components.v1 import html as st_html

    if not model or not model.ready or not model.decisions:
        st.info("Nenhuma tabela DMN disponível para esta reunião.")
        return

    st.caption(
        f"{len(model.decisions)} tabela(s) de decisão DMN extraída(s). "
        "Cada tabela formaliza uma decisão tomada como regras de negócio "
        "consultáveis e reutilizáveis."
    )

    dicts = _model_to_dicts(model)
    page_html = render_dmn_page(dicts, show_origin=False)
    actual_h  = estimate_height(dicts)
    st_html(page_html, height=max(height, actual_h), scrolling=True)


# ── XML export (unchanged) ────────────────────────────────────────────────────

def dmn_to_xml(model: DMNModel, model_name: str = "Meeting Decisions") -> str:
    """Generate DMN 1.4 XML from a DMNModel."""
    import xml.etree.ElementTree as ET

    ns    = "https://www.omg.org/spec/DMN/20191111/MODEL/"
    dmndi = "https://www.omg.org/spec/DMN/20191111/DMNDI/"
    ET.register_namespace("", ns)
    ET.register_namespace("dmndi", dmndi)

    root = ET.Element(f"{{{ns}}}definitions")
    root.set("xmlns", ns)
    root.set("xmlns:dmndi", dmndi)
    root.set("name", model_name)
    root.set("namespace", "http://camunda.org/schema/1.0/dmn")
    root.set("exporter", "Process2Diagram")
    root.set("exporterVersion", "4.29")

    for d in model.decisions:
        dec_el = ET.SubElement(root, f"{{{ns}}}decision")
        dec_el.set("id", d.id)
        dec_el.set("name", d.name)

        if d.question or d.rationale:
            doc = ET.SubElement(dec_el, f"{{{ns}}}description")
            doc.text = f"{d.question}\n\n{d.rationale}".strip()

        dt = ET.SubElement(dec_el, f"{{{ns}}}decisionTable")
        dt.set("id", f"dt_{d.id}")
        dt.set("hitPolicy", d.hit_policy)

        for inp in d.inputs:
            inp_el = ET.SubElement(dt, f"{{{ns}}}input")
            inp_el.set("id", f"i_{d.id}_{(inp.expression or inp.label)[:12]}")
            inp_el.set("label", inp.label)
            ie = ET.SubElement(inp_el, f"{{{ns}}}inputExpression")
            ie.set("typeRef", "string")
            txt = ET.SubElement(ie, f"{{{ns}}}text")
            txt.text = inp.expression or inp.label

        for k, out in enumerate(d.outputs):
            out_el = ET.SubElement(dt, f"{{{ns}}}output")
            out_el.set("id", f"o_{d.id}_{k}")
            out_el.set("label", out.label)
            out_el.set("typeRef", "string")

        for r_idx, rule in enumerate(d.rules):
            rule_el = ET.SubElement(dt, f"{{{ns}}}rule")
            rule_el.set("id", f"r_{d.id}_{r_idx}")
            for j, inp_val in enumerate(rule.inputs):
                ie_el = ET.SubElement(rule_el, f"{{{ns}}}inputEntry")
                ie_el.set("id", f"ie_{d.id}_{r_idx}_{j}")
                t = ET.SubElement(ie_el, f"{{{ns}}}text")
                t.text = inp_val if inp_val not in ("-", "") else ""
            oe_el = ET.SubElement(rule_el, f"{{{ns}}}outputEntry")
            oe_el.set("id", f"oe_{d.id}_{r_idx}")
            ot = ET.SubElement(oe_el, f"{{{ns}}}text")
            ot.text = rule.output
            if rule.annotation:
                ann = ET.SubElement(rule_el, f"{{{ns}}}annotationEntry")
                ann.text = rule.annotation

    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")
