# modules/dmn_viewer.py
# ─────────────────────────────────────────────────────────────────────────────
# DMN Viewer — renderiza tabelas DMN 1.4 como HTML interativo no Streamlit.
# Sem dependências externas além de streamlit.components.v1.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import html
from core.knowledge_hub import DMNModel, DMNDecision


_COLORS = {
    "header_bg": "#0d2a4a",
    "header_fg": "#ffffff",
    "input_bg":  "#e8f0fe",
    "output_bg": "#fff3e0",
    "rule_even": "#f8f9fa",
    "rule_odd":  "#ffffff",
    "border":    "#dee2e6",
    "accent":    "#f5a623",
}

_HIT_POLICY_LABELS = {
    "U": "U — Unique (uma regra por vez)",
    "F": "F — First (primeira regra que se aplica)",
    "A": "A — Any (qualquer regra; mesmo output)",
    "C": "C — Collect (agrega todos os resultados)",
}


def _esc(s: str) -> str:
    return html.escape(str(s or "—"))


def _render_decision_html(d: DMNDecision, idx: int) -> str:
    hit = _HIT_POLICY_LABELS.get(d.hit_policy, d.hit_policy)
    decided = ", ".join(d.decided_by) if d.decided_by else "—"
    conf_pct = int(d.confidence * 100)
    conf_color = "#28a745" if d.confidence >= 0.8 else ("#ffc107" if d.confidence >= 0.6 else "#dc3545")

    # Table header: inputs + output + annotation
    input_headers = "".join(
        f'<th style="background:{_COLORS["input_bg"]};border:1px solid {_COLORS["border"]};padding:8px 12px;text-align:center;font-size:0.82rem;">'
        f'<div style="font-weight:600;color:#1a3a5c;">{_esc(inp.label)}</div>'
        f'<div style="font-size:0.72rem;color:#666;font-style:italic;">{_esc(inp.expression) if inp.expression else ""}</div>'
        f'</th>'
        for inp in d.inputs
    )
    output_headers = "".join(
        f'<th style="background:{_COLORS["output_bg"]};border:1px solid {_COLORS["border"]};padding:8px 12px;text-align:center;font-size:0.82rem;">'
        f'<div style="font-weight:600;color:#7a4f00;">{_esc(out.label)}</div>'
        f'</th>'
        for out in d.outputs
    )

    # Rule rows
    rows = ""
    for r_idx, rule in enumerate(d.rules):
        bg = _COLORS["rule_even"] if r_idx % 2 == 0 else _COLORS["rule_odd"]
        input_cells = "".join(
            f'<td style="background:{bg};border:1px solid {_COLORS["border"]};padding:7px 12px;text-align:center;font-size:0.85rem;">'
            f'{_esc(v)}</td>'
            for v in (rule.inputs or ["—"] * len(d.inputs))
        )
        output_cell = (
            f'<td style="background:{_COLORS["output_bg"]};border:1px solid {_COLORS["border"]};'
            f'padding:7px 12px;text-align:center;font-weight:600;font-size:0.85rem;">'
            f'{_esc(rule.output)}</td>'
        )
        annot = (
            f'<td style="background:{bg};border:1px solid {_COLORS["border"]};padding:7px 12px;'
            f'color:#666;font-size:0.78rem;font-style:italic;">{_esc(rule.annotation)}</td>'
            if rule.annotation else ""
        )
        rows += f"<tr>{input_cells}{output_cell}{annot}</tr>"

    annot_header = (
        f'<th style="background:{_COLORS["rule_odd"]};border:1px solid {_COLORS["border"]};'
        f'padding:8px 12px;font-size:0.82rem;color:#888;">Anotação</th>'
        if any(r.annotation for r in d.rules) else ""
    )

    return f"""
<div style="margin-bottom:28px;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.10);">
  <!-- Decision Header -->
  <div style="background:{_COLORS['header_bg']};color:{_COLORS['header_fg']};padding:12px 16px;display:flex;align-items:center;justify-content:space-between;">
    <div>
      <span style="font-size:0.75rem;opacity:0.7;letter-spacing:1px;">D{idx} · {_esc(hit)}</span><br>
      <strong style="font-size:1.05rem;">{_esc(d.name)}</strong>
    </div>
    <div style="text-align:right;">
      <div style="font-size:0.75rem;color:{conf_color};font-weight:700;">{conf_pct}% confiança</div>
      <div style="font-size:0.72rem;opacity:0.75;">Por: {_esc(decided)}</div>
    </div>
  </div>

  <!-- Question + Rationale -->
  {"" if not d.question else f'<div style="background:#f0f4ff;padding:10px 16px;font-size:0.88rem;color:#1a3a5c;border-bottom:1px solid {_COLORS[chr(98)+chr(111)+chr(114)+chr(100)+chr(101)+chr(114)]}"><strong>Pergunta:</strong> {_esc(d.question)}</div>'}
  {"" if not d.rationale else f'<div style="background:#fffdf0;padding:8px 16px;font-size:0.83rem;color:#555;border-bottom:1px solid {_COLORS["border"]}"><em>{_esc(d.rationale)}</em></div>'}

  <!-- Decision Table -->
  <div style="overflow-x:auto;">
    <table style="width:100%;border-collapse:collapse;font-family:sans-serif;">
      <thead>
        <tr>
          <th colspan="{len(d.inputs)}" style="background:{_COLORS['input_bg']};border:1px solid {_COLORS['border']};padding:6px;text-align:center;font-size:0.78rem;color:#1a3a5c;letter-spacing:1px;">CONDIÇÕES DE ENTRADA</th>
          <th colspan="{max(1, len(d.outputs))}" style="background:{_COLORS['output_bg']};border:1px solid {_COLORS['border']};padding:6px;text-align:center;font-size:0.78rem;color:#7a4f00;letter-spacing:1px;">RESULTADO</th>
          {"" if not any(r.annotation for r in d.rules) else f'<th style="background:{_COLORS["rule_odd"]};border:1px solid {_COLORS["border"]};padding:6px;font-size:0.78rem;color:#888;letter-spacing:1px;">ANOTAÇÃO</th>'}
        </tr>
        <tr>{input_headers}{output_headers}{annot_header}</tr>
      </thead>
      <tbody>{rows if rows else f'<tr><td colspan="99" style="text-align:center;padding:12px;color:#888;font-style:italic;">Sem regras definidas</td></tr>'}</tbody>
    </table>
  </div>
</div>
"""


def render_dmn_model(model: DMNModel, height: int = 600) -> None:
    """Render the full DMN model as an HTML component in Streamlit."""
    import streamlit as st
    from streamlit.components.v1 import html as st_html

    if not model or not model.ready or not model.decisions:
        st.info("Nenhuma decisao DMN extraida desta reuniao.")
        return

    st.caption(
        f"{len(model.decisions)} tabela(s) de decisao DMN extraida(s). "
        "Cada tabela formaliza uma decisao tomada como regras de negocio consultaveis."
    )

    decisions_html = "".join(
        _render_decision_html(d, i + 1)
        for i, d in enumerate(model.decisions)
    )

    page_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: transparent; margin: 0; padding: 12px; }}
  * {{ box-sizing: border-box; }}
</style>
</head>
<body>{decisions_html}</body>
</html>"""

    st_html(page_html, height=height, scrolling=True)


def dmn_to_xml(model: DMNModel, model_name: str = "Meeting Decisions") -> str:
    """Generate DMN 1.4 XML from a DMNModel."""
    import xml.etree.ElementTree as ET

    ns = "https://www.omg.org/spec/DMN/20191111/MODEL/"
    dmndi = "https://www.omg.org/spec/DMN/20191111/DMNDI/"
    ET.register_namespace("", ns)
    ET.register_namespace("dmndi", dmndi)

    root = ET.Element(f"{{{ns}}}definitions")
    root.set("xmlns", ns)
    root.set("xmlns:dmndi", dmndi)
    root.set("name", model_name)
    root.set("namespace", "http://camunda.org/schema/1.0/dmn")
    root.set("exporter", "Process2Diagram")
    root.set("exporterVersion", "4.23")

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
            inp_el.set("id", f"i_{d.id}_{inp.expression or inp.label[:8]}")
            inp_el.set("label", inp.label)
            ie = ET.SubElement(inp_el, f"{{{ns}}}inputExpression")
            ie.set("typeRef", "string")
            txt = ET.SubElement(ie, f"{{{ns}}}text")
            txt.text = inp.expression or inp.label

        for out in d.outputs:
            out_el = ET.SubElement(dt, f"{{{ns}}}output")
            out_el.set("id", f"o_{d.id}_{out.label[:8]}")
            out_el.set("label", out.label)
            out_el.set("typeRef", "string")

        for r_idx, rule in enumerate(d.rules):
            rule_el = ET.SubElement(dt, f"{{{ns}}}rule")
            rule_el.set("id", f"r_{d.id}_{r_idx}")
            for inp_val in rule.inputs:
                ie_el = ET.SubElement(rule_el, f"{{{ns}}}inputEntry")
                ie_el.set("id", f"ie_{d.id}_{r_idx}_{rule.inputs.index(inp_val)}")
                t = ET.SubElement(ie_el, f"{{{ns}}}text")
                t.text = inp_val if inp_val != "-" else ""
            oe_el = ET.SubElement(rule_el, f"{{{ns}}}outputEntry")
            oe_el.set("id", f"oe_{d.id}_{r_idx}")
            ot = ET.SubElement(oe_el, f"{{{ns}}}text")
            ot.text = rule.output
            if rule.annotation:
                ann = ET.SubElement(rule_el, f"{{{ns}}}annotationEntry")
                ann.text = rule.annotation

    ET.indent(root, space="  ")
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="unicode")
