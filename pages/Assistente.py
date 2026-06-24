# pages/Assistente.py
# Assistente conversacional RAG sobre reuniões, requisitos, processos e SBVR.

from __future__ import annotations

import sys
from pathlib import Path
import re
import threading
import time
from collections import Counter

import streamlit as st

from ui.auth_gate import apply_auth_gate
from modules.supabase_client import supabase_configured, get_supabase_client
from modules.config import AVAILABLE_PROVIDERS
from modules.embeddings import EMBEDDING_PROVIDERS
from core.project_store import (
    retrieve_context_for_question,
    retrieve_context_semantic,
    format_context,
    transcript_chunks_table_exists,
    get_embedding_coverage,
)
from ui.project_selector import require_active_project
from agents.agent_assistant import AgentAssistant
from ui.components.copy_button import copy_button
from core.chart_config import CHART_PALETTES, DEFAULT_PALETTE
from modules.excel_exporter import export_table_to_excel


# ── Análise Autônoma UI ───────────────────────────────────────────────────────

def _render_analyst_mode(
    project_id: str,
    project_name: str,
    api_key: str,
    provider_cfg: dict,
    provider_name: str,
) -> None:
    """Render the Autonomous Analysis mode UI."""
    st.caption(
        "Descreva um objetivo analítico complexo. O agente planeja e executa "
        "múltiplas ferramentas autonomamente, produzindo um relatório estruturado."
    )

    # ── Objective input ───────────────────────────────────────────────────────
    objective = st.text_area(
        "Objetivo da análise",
        height=120,
        placeholder=(
            "Ex: Identifique os requisitos funcionais não implementados e compare "
            "com as decisões das últimas 3 reuniões. Liste ações em aberto por responsável."
        ),
        key="analyst_objective",
    )

    col_btn, col_info = st.columns([2, 5])
    run_clicked = col_btn.button("▶️ Iniciar Análise", type="primary", use_container_width=True)
    col_info.caption(
        f"Provedor: **{provider_name}** · modelo: `{provider_cfg.get('default_model', '—')}`"
    )

    # ── Results from previous run ─────────────────────────────────────────────
    if "_analyst_report" in st.session_state:
        _render_analyst_report(st.session_state["_analyst_report"], project_id)

    # ── Run ───────────────────────────────────────────────────────────────────
    if run_clicked:
        if not objective.strip():
            st.warning("Descreva o objetivo da análise antes de iniciar.")
            return

        # Clear previous result
        st.session_state.pop("_analyst_report", None)

        from modules.auth import is_admin
        llm_config = {
            "client_type":      provider_cfg.get("client_type", "openai_compatible"),
            "model":            provider_cfg.get("default_model", "deepseek-v4-flash"),
            "api_key":          api_key,
            "base_url":         provider_cfg.get("base_url"),
            "reasoning_effort": provider_cfg.get("reasoning_effort"),
        }

        with st.status("🔬 Executando análise autônoma...", expanded=True) as status:
            st.write("Inicializando agente ReAct...")
            try:
                from agents.agent_analyst import AgentAnalyst
                analyst = AgentAnalyst(
                    llm_config = llm_config,
                    project_id = project_id,
                    is_admin   = is_admin(),
                )
                st.write("Agente iniciado. Executando passos analíticos...")
                report = analyst.run(objective.strip())
                st.session_state["_analyst_report"] = report
                if report.success:
                    status.update(
                        label=f"✅ Análise concluída — {len(report.steps)} passo(s) · {report.duration_s:.1f}s",
                        state="complete",
                    )
                else:
                    status.update(label=f"❌ Falha: {report.error[:80]}", state="error")
            except Exception as exc:
                status.update(label=f"❌ Erro inesperado: {exc}", state="error")
                st.error(str(exc))
                return

        st.rerun()


def _analyst_report_to_pdf(report) -> bytes:
    """Generate a styled PDF from AnalysisReport using fpdf2. Returns raw bytes."""
    import re
    from fpdf import FPDF

    # ── Helpers ───────────────────────────────────────────────────────────────

    # Only map characters NOT in Latin-1 (> U+00FF) to ASCII equivalents.
    # Portuguese accented chars (ã â á é ê etc.) ARE in Latin-1 — keep them.
    _UNICODE_MAP = str.maketrans({
        "\u2019": "'",  "\u2018": "'",  "\u201c": '"',  "\u201d": '"',
        "\u2013": "-",  "\u2014": "-",  "\u2026": "...", "\u2022": "-",
        "\u00b7": ".",  "\u2605": "*",  "\u25cf": "*",
    })

    def _p(text: str) -> str:
        """Sanitize text for fpdf2 Latin-1 core fonts."""
        if not text:
            return ""
        text = text.translate(_UNICODE_MAP)
        # Drop any remaining non-Latin-1 chars (emojis, symbols, etc.)
        return text.encode("latin-1", errors="ignore").decode("latin-1")

    def _clean_md(text: str) -> str:
        """Strip Markdown syntax to produce clean plain text."""
        text = re.sub(r"^-{3,}$",      "",    text, flags=re.MULTILINE)  # ---
        text = re.sub(r"^={3,}$",      "",    text, flags=re.MULTILINE)  # ===
        text = re.sub(r"^>\s*",        "",    text, flags=re.MULTILINE)  # > quote
        text = re.sub(r"^#{1,6}\s*",   "",    text, flags=re.MULTILINE)  # ## header
        text = re.sub(r"\*{2,3}(.*?)\*{2,3}", r"\1", text)              # **bold**
        text = re.sub(r"\*(.*?)\*",    r"\1", text)                      # *italic*
        text = re.sub(r"`([^`]+)`",    r"\1", text)                      # `code`
        # Markdown table separator rows
        text = re.sub(r"^\|[-:| ]+\|$", "", text, flags=re.MULTILINE)
        # Markdown table rows → pipe-joined plain text
        def _fmt_row(m: re.Match) -> str:
            cells = [c.strip() for c in m.group(1).split("|") if c.strip()]
            return "  |  ".join(cells)
        text = re.sub(r"^\|(.+)\|$", _fmt_row, text, flags=re.MULTILINE)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _section_bar(pdf: "FPDF", label: str, color: tuple, W: int) -> None:
        r, g, b = color
        pdf.set_fill_color(r, g, b)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(W, 7, f"  {_p(label)}", fill=True, new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)
        pdf.ln(1)

    def _render_body(pdf: "FPDF", text: str, W: int) -> None:
        """Render cleaned Markdown body text with basic structure detection."""
        for line in _clean_md(text).split("\n"):
            line = line.strip()
            if not line:
                pdf.ln(2)
                continue
            # Bullet points
            if line.startswith(("- ", "* ", "+ ")):
                pdf.set_font("Helvetica", "", 10)
                pdf.multi_cell(W - 5, 5, _p("  " + line[2:]),
                               new_x="LMARGIN", new_y="NEXT")
                continue
            # Numbered list
            if re.match(r"^\d+\.", line):
                pdf.set_font("Helvetica", "", 10)
                pdf.multi_cell(W - 5, 5, _p("  " + line),
                               new_x="LMARGIN", new_y="NEXT")
                continue
            # Short line without sentence-ending punctuation → treat as sub-header
            if len(line) < 70 and not line[-1] in ".,:;)":
                pdf.set_font("Helvetica", "B", 10)
                pdf.multi_cell(W, 5, _p(line), new_x="LMARGIN", new_y="NEXT")
                continue
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(W, 5, _p(line), new_x="LMARGIN", new_y="NEXT")

    # ── Constants ─────────────────────────────────────────────────────────────
    NAVY  = (13,  42,  74)
    AMBER = (201, 123,  26)
    LGRAY = (245, 245, 245)
    W     = 190

    # ── PDF class ─────────────────────────────────────────────────────────────
    class _PDF(FPDF):
        def header(self):
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(150, 150, 150)
            self.cell(0, 6, "Process2Diagram - Analise Autonoma",
                      align="R", new_x="LMARGIN", new_y="NEXT")
            self.set_text_color(0, 0, 0)

        def footer(self):
            self.set_y(-12)
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(150, 150, 150)
            self.cell(0, 6, f"Pagina {self.page_no()}", align="C")
            self.set_text_color(0, 0, 0)

    pdf = _PDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(10, 14, 10)
    pdf.set_auto_page_break(auto=True, margin=16)
    pdf.add_page()

    # ── Title bar ─────────────────────────────────────────────────────────────
    r, g, b = NAVY
    pdf.set_fill_color(r, g, b)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(W, 11, "Analise Autonoma - Relatorio",
             fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # ── Objetivo ──────────────────────────────────────────────────────────────
    r, g, b = AMBER
    pdf.set_text_color(r, g, b)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(W, 6, "OBJETIVO", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(W, 5, _p(report.objective), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # ── Conclusão ─────────────────────────────────────────────────────────────
    if report.conclusion:
        _section_bar(pdf, "CONCLUSAO", AMBER, W)
        _render_body(pdf, report.conclusion, W)
        pdf.ln(4)

    # ── Tabelas ───────────────────────────────────────────────────────────────
    for tbl in report.tables:
        cols = tbl.get("columns", [])
        rows = tbl.get("rows", [])
        if not cols or not rows:
            continue

        _section_bar(pdf, tbl.get("title", "Tabela").upper(), NAVY, W)

        col_w = W / len(cols)

        # Header row
        r, g, b = AMBER
        pdf.set_fill_color(r, g, b)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Helvetica", "B", 8)
        for col in cols:
            pdf.cell(col_w, 7, _p(str(col)), fill=True, border=0)
        pdf.ln()

        # Data rows
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 9)
        for i, row in enumerate(rows):
            pdf.set_fill_color(*(LGRAY if i % 2 == 0 else (255, 255, 255)))
            for val in row:
                pdf.cell(col_w, 6, _p(str(val)), fill=True, border=0)
            pdf.ln()
        pdf.ln(5)

    # ── Cadeia de raciocínio — compacta ───────────────────────────────────────
    if report.steps:
        _section_bar(pdf, f"CADEIA DE RACIOCINIO  ({len(report.steps)} passos)", NAVY, W)
        pdf.set_font("Helvetica", "", 8)

        for i, step in enumerate(report.steps, 1):
            # Step header: number + tool name
            pdf.set_font("Helvetica", "B", 8)
            label = _p(f"{i}. {step.label}")
            pdf.cell(W, 5, label, new_x="LMARGIN", new_y="NEXT")

            # One-line observation summary (max 120 chars, no Markdown)
            if step.observation:
                obs_clean = _clean_md(step.observation)
                # Take first non-empty line only
                first_line = next(
                    (ln.strip() for ln in obs_clean.split("\n") if ln.strip()), ""
                )
                if first_line:
                    pdf.set_font("Helvetica", "", 7)
                    pdf.set_text_color(80, 80, 80)
                    pdf.multi_cell(W - 6, 4, _p("   " + first_line[:140]),
                                   new_x="LMARGIN", new_y="NEXT")
                    pdf.set_text_color(0, 0, 0)
            pdf.ln(0.5)

    # ── Meta rodapé ───────────────────────────────────────────────────────────
    pdf.ln(5)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(150, 150, 150)
    pdf.multi_cell(
        W, 5,
        _p(f"Gerado em {report.duration_s:.1f}s  |  {len(report.steps)} passos  |  Process2Diagram"),
        new_x="LMARGIN", new_y="NEXT",
    )

    return bytes(pdf.output())


def _analyst_report_to_html(report) -> str:
    """Generate a self-contained HTML report with embedded Plotly charts."""
    import json, re

    # ── Markdown → HTML (basic) ───────────────────────────────────────────────
    def _md_to_html(text: str) -> str:
        text = re.sub(r"^---+$", "<hr>", text, flags=re.MULTILINE)
        text = re.sub(r"^#{3}\s+(.+)$", r"<h3>\1</h3>", text, flags=re.MULTILINE)
        text = re.sub(r"^#{2}\s+(.+)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
        text = re.sub(r"^#{1}\s+(.+)$", r"<h2>\1</h2>", text, flags=re.MULTILINE)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = re.sub(r"\*(.+?)\*",     r"<em>\1</em>", text)
        text = re.sub(r"`(.+?)`",       r"<code>\1</code>", text)
        text = re.sub(r"^>\s*(.+)$",    r'<blockquote>\1</blockquote>', text, flags=re.MULTILINE)
        # Bullet lists
        def _list_block(m):
            items = re.findall(r"^[-*+]\s+(.+)$", m.group(0), re.MULTILINE)
            return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"
        text = re.sub(r"(^[-*+]\s+.+$\n?)+", _list_block, text, flags=re.MULTILINE)
        # Numbered lists
        def _olist_block(m):
            items = re.findall(r"^\d+\.\s+(.+)$", m.group(0), re.MULTILINE)
            return "<ol>" + "".join(f"<li>{i}</li>" for i in items) + "</ol>"
        text = re.sub(r"(^\d+\.\s+.+$\n?)+", _olist_block, text, flags=re.MULTILINE)
        # Paragraphs
        paragraphs = []
        for block in re.split(r"\n{2,}", text):
            block = block.strip()
            if not block:
                continue
            if block.startswith(("<h", "<ul", "<ol", "<hr", "<blockquote")):
                paragraphs.append(block)
            else:
                paragraphs.append(f"<p>{block.replace(chr(10), ' ')}</p>")
        return "\n".join(paragraphs)

    # ── Tables HTML ───────────────────────────────────────────────────────────
    def _table_html(tbl: dict) -> str:
        cols = tbl.get("columns", [])
        rows = tbl.get("rows", [])
        title = tbl.get("title", "Tabela")
        if not cols or not rows:
            return ""
        head = "".join(f"<th>{c}</th>" for c in cols)
        body = ""
        for row in rows:
            body += "<tr>" + "".join(f"<td>{v}</td>" for v in row) + "</tr>"
        return (
            f'<div class="section">'
            f'<h2 class="section-title">{title}</h2>'
            f'<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'
            f'</div>'
        )

    # ── Charts HTML (Plotly) ──────────────────────────────────────────────────
    chart_blocks = ""
    if report.charts:
        for i, chart_dict in enumerate(report.charts):
            chart_id = f"chart-{i}"
            data_json = json.dumps(chart_dict.get("data", []))
            layout_json = json.dumps(chart_dict.get("layout", {}))
            chart_blocks += (
                f'<div class="section">'
                f'<div id="{chart_id}" class="chart-container"></div>'
                f'<script>Plotly.newPlot("{chart_id}", {data_json}, '
                f'Object.assign({{responsive:true}}, {layout_json}));</script>'
                f'</div>\n'
            )

    # ── Steps HTML ────────────────────────────────────────────────────────────
    steps_html = ""
    if report.steps:
        items = ""
        for i, step in enumerate(report.steps, 1):
            obs = f'<div class="obs">{step.observation[:300]}</div>' if step.observation else ""
            items += (
                f'<div class="step">'
                f'<span class="step-num">{i}</span>'
                f'<div class="step-body">'
                f'<strong>{step.label}</strong>{obs}'
                f'</div></div>\n'
            )
        steps_html = (
            f'<div class="section collapsible-section">'
            f'<h2 class="section-title toggle-btn" onclick="toggleSteps()">'
            f'Cadeia de Raciocinio ({len(report.steps)} passos) '
            f'<span id="toggle-icon">&#9660;</span></h2>'
            f'<div id="steps-body">{items}</div>'
            f'</div>'
        )

    # ── Assemble ──────────────────────────────────────────────────────────────
    tables_html = "\n".join(_table_html(t) for t in report.tables)
    conclusion_html = _md_to_html(report.conclusion) if report.conclusion else ""
    plotly_cdn = '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>' if report.charts else ""
    date_str   = __import__("datetime").datetime.now().strftime("%d/%m/%Y %H:%M")

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Analise Autonoma - Process2Diagram</title>
{plotly_cdn}
<style>
  :root {{
    --navy: #0d2a4a; --amber: #c97b1a; --bg: #f5f7fa;
    --card: #ffffff; --text: #1a1a2e; --muted: #6b7280;
    --border: #e5e7eb;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Segoe UI', Arial, sans-serif; background: var(--bg);
          color: var(--text); font-size: 14px; line-height: 1.6; }}
  .header {{ background: var(--navy); color: #fff; padding: 24px 40px; }}
  .header h1 {{ font-size: 22px; font-weight: 700; margin-bottom: 4px; }}
  .header .meta {{ font-size: 12px; color: #a0b4cc; }}
  .objective-bar {{ background: var(--amber); color: #fff;
                    padding: 12px 40px; font-size: 13px; font-style: italic; }}
  .main {{ max-width: 960px; margin: 0 auto; padding: 32px 24px; }}
  .section {{ background: var(--card); border-radius: 8px;
              border: 1px solid var(--border); margin-bottom: 24px;
              overflow: hidden; }}
  .section-title {{ background: var(--navy); color: #fff;
                    padding: 10px 18px; font-size: 13px;
                    font-weight: 700; letter-spacing: .04em; }}
  .section-body {{ padding: 20px 22px; }}
  .section-body h2 {{ font-size: 15px; color: var(--navy);
                      margin: 16px 0 6px; border-bottom: 1px solid var(--border);
                      padding-bottom: 4px; }}
  .section-body h3 {{ font-size: 13px; color: var(--amber); margin: 12px 0 4px; }}
  .section-body p {{ margin-bottom: 10px; }}
  .section-body ul, .section-body ol {{ padding-left: 22px; margin-bottom: 10px; }}
  .section-body li {{ margin-bottom: 4px; }}
  .section-body blockquote {{ border-left: 3px solid var(--amber);
                               padding: 6px 12px; margin: 10px 0;
                               background: #fef9f0; color: #555; font-style: italic; }}
  .section-body code {{ background: #f3f4f6; padding: 1px 5px;
                         border-radius: 3px; font-size: 12px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  thead tr {{ background: var(--amber); color: #fff; }}
  th {{ padding: 9px 12px; text-align: left; font-weight: 600; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid var(--border); }}
  tbody tr:nth-child(even) {{ background: #f9fafb; }}
  tbody tr:hover {{ background: #eef2ff; }}
  .chart-container {{ padding: 16px; min-height: 300px; }}
  .toggle-btn {{ cursor: pointer; user-select: none; }}
  .toggle-btn:hover {{ background: #163d68; }}
  .step {{ display: flex; gap: 12px; padding: 8px 18px;
           border-bottom: 1px solid var(--border); }}
  .step:last-child {{ border-bottom: none; }}
  .step-num {{ background: var(--amber); color: #fff; border-radius: 50%;
               min-width: 22px; height: 22px; font-size: 11px; font-weight: 700;
               display: flex; align-items: center; justify-content: center;
               margin-top: 2px; }}
  .step-body {{ font-size: 12px; flex: 1; }}
  .obs {{ color: var(--muted); font-size: 11px; margin-top: 3px; }}
  hr {{ border: none; border-top: 1px solid var(--border); margin: 12px 0; }}
  .footer {{ text-align: center; color: var(--muted); font-size: 11px;
             padding: 24px; }}
</style>
</head>
<body>
<div class="header">
  <h1>Analise Autonoma — Relatorio</h1>
  <div class="meta">Process2Diagram &nbsp;·&nbsp; {date_str} &nbsp;·&nbsp;
    {len(report.steps)} passos &nbsp;·&nbsp; {report.duration_s:.1f}s</div>
</div>
<div class="objective-bar">{report.objective}</div>
<div class="main">

{"" if not conclusion_html else f'''
<div class="section">
  <div class="section-title">CONCLUSAO</div>
  <div class="section-body">{conclusion_html}</div>
</div>'''}

{tables_html}
{chart_blocks}
{steps_html}

</div>
<div class="footer">Gerado por Process2Diagram &nbsp;·&nbsp; {date_str}</div>
<script>
  function toggleSteps() {{
    var b = document.getElementById('steps-body');
    var i = document.getElementById('toggle-icon');
    if (b.style.display === 'none') {{ b.style.display = ''; i.innerHTML = '&#9660;'; }}
    else {{ b.style.display = 'none'; i.innerHTML = '&#9654;'; }}
  }}
</script>
</body>
</html>"""


def _render_analyst_report(report, project_id: str) -> None:
    """Display a completed AnalysisReport."""
    from agents.agent_analyst import AnalysisReport  # for isinstance check

    st.markdown("---")

    # ── Conclusion ────────────────────────────────────────────────────────────
    if report.conclusion:
        st.markdown("## Conclusão da Análise")
        st.markdown(report.conclusion)

    # ── Tables ────────────────────────────────────────────────────────────────
    if report.tables:
        st.markdown("### Tabelas geradas")
        for tbl in report.tables:
            title   = tbl.get("title", "Tabela")
            columns = tbl.get("columns", [])
            rows    = tbl.get("rows", [])
            if not columns or not rows:
                continue
            import pandas as pd
            df = pd.DataFrame(rows, columns=columns)
            st.markdown(f"**{title}**")
            st.dataframe(df, use_container_width=True)
            try:
                from modules.excel_exporter import export_table_to_excel
                excel_bytes = export_table_to_excel(tbl)
                if excel_bytes:
                    st.download_button(
                        f"⬇️ Exportar {title} (.xlsx)",
                        data        = excel_bytes,
                        file_name   = f"{title.lower().replace(' ', '_')}.xlsx",
                        mime        = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key         = f"analyst_dl_{title}",
                    )
            except Exception:
                pass

    # ── Charts ────────────────────────────────────────────────────────────────
    if report.charts:
        for chart_dict in report.charts:
            try:
                import plotly.graph_objects as go
                fig = go.Figure(chart_dict)
                st.plotly_chart(fig, use_container_width=True)
            except Exception:
                pass

    # ── Chain of thought ──────────────────────────────────────────────────────
    if report.steps:
        with st.expander(f"🧠 Cadeia de raciocínio ({len(report.steps)} passos)", expanded=False):
            for i, step in enumerate(report.steps, 1):
                icon = {"action": "🛠️", "conclusion": "✅", "error": "❌"}.get(step.type, "🔍")
                with st.container():
                    st.markdown(f"**{icon} Passo {i} — {step.label}**")
                    if step.content:
                        st.markdown(step.content)
                    if step.observation:
                        st.caption(f"Observação: {step.observation[:500]}")
                    st.divider()

    # ── Export ────────────────────────────────────────────────────────────────
    _col_save, _col_export, _col_pdf, _col_html, _col_meta = st.columns([2, 2, 2, 2, 2])

    _md_lines: list[str] = [f"# Análise Autônoma\n\n**Objetivo:** {report.objective}\n"]
    if report.conclusion:
        _md_lines.append(f"## Conclusão\n\n{report.conclusion}\n")
    for tbl in report.tables:
        cols = tbl.get("columns", [])
        rows = tbl.get("rows", [])
        if cols and rows:
            _md_lines.append(f"## {tbl.get('title', 'Tabela')}\n")
            _md_lines.append("| " + " | ".join(cols) + " |")
            _md_lines.append("| " + " | ".join(["---"] * len(cols)) + " |")
            for row in rows:
                _md_lines.append("| " + " | ".join(str(v) for v in row) + " |")
            _md_lines.append("")
    if report.charts:
        _md_lines.append(
            f"> **Nota:** esta análise gerou {len(report.charts)} gráfico(s) interativo(s). "
            "Gráficos não são exportáveis para Markdown — visualize-os na plataforma.\n"
        )
    if report.steps:
        _md_lines.append("## Cadeia de Raciocínio\n")
        for i, step in enumerate(report.steps, 1):
            _md_lines.append(f"**Passo {i} — {step.label}**\n")
            if step.tool_input:
                _md_lines.append(f"Input: `{step.tool_input[:200]}`\n")
            if step.observation:
                _md_lines.append(f"Resultado: {step.observation[:400]}\n")
    _md_lines.append(
        f"\n---\n*Gerado em {report.duration_s:.1f}s · {len(report.steps)} passos*"
    )
    _md_export = "\n".join(_md_lines)

    _col_export.download_button(
        "📄 Exportar Markdown",
        data      = _md_export.encode("utf-8"),
        file_name = "analise_autonoma.md",
        mime      = "text/markdown",
        key       = "analyst_dl_md",
        use_container_width=True,
    )

    try:
        _pdf_bytes = _analyst_report_to_pdf(report)
        _col_pdf.download_button(
            "📑 Exportar PDF",
            data      = _pdf_bytes,
            file_name = "analise_autonoma.pdf",
            mime      = "application/pdf",
            key       = "analyst_dl_pdf",
            use_container_width=True,
        )
    except Exception as _pdf_err:
        _col_pdf.caption(f"PDF indisponível: {_pdf_err}")

    try:
        _html_bytes = _analyst_report_to_html(report).encode("utf-8")
        _col_html.download_button(
            "🌐 Exportar HTML",
            data      = _html_bytes,
            file_name = "analise_autonoma.html",
            mime      = "text/html",
            key       = "analyst_dl_html",
            use_container_width=True,
        )
    except Exception as _html_err:
        _col_html.caption(f"HTML indisponível: {_html_err}")

    if _col_save.button("💾 Salvar análise", key="analyst_save"):
        try:
            from core.analyst_store import save_analysis, analyses_table_exists
            if not analyses_table_exists():
                st.error(
                    "Tabela `kh_analyses` não encontrada. "
                    "Execute `setup/supabase_migration_kh_analyses.sql` no Supabase."
                )
            else:
                user = st.session_state.get("_usuario_login", "")
                aid  = save_analysis(project_id, report, created_by=user)
                if aid:
                    st.session_state["_analyst_saved_id"] = aid
                    st.success(f"✅ Análise salva (ID: `{aid[:8]}…`)")
                else:
                    st.error("Falha ao salvar análise.")
        except Exception as exc:
            st.error(f"Erro ao salvar: {exc}")

    _col_meta.caption(
        f"Passos: {len(report.steps)} · "
        f"Tempo: {report.duration_s:.1f}s · "
        f"Tabelas: {len(report.tables)}"
    )


# ── Page config ───────────────────────────────────────────────────────────────
apply_auth_gate()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 💬 Assistente")

    st.markdown("#### 📁 Projeto de Trabalho")
    _ap_name = st.session_state.get("active_project_name", "")
    if _ap_name:
        st.success(f"**{_ap_name}**")
        st.page_link("pages/Home.py", label="↩ Trocar contexto")
    else:
        st.warning("Nenhum contexto ativo.")
        st.page_link("pages/Home.py", label="← Selecionar contexto")

    st.markdown("---")

    st.markdown("#### 🔧 Modo Ferramentas")
    use_tools = st.checkbox("Ativar tool-use", value=True, key="asst_use_tools")
    if use_tools:
        st.caption("🔢 22 ferramentas · catálogo em Configurações")

    st.markdown("---")

    st.markdown("#### 🎨 Gráficos")
    _palette_names = list(CHART_PALETTES.keys())
    _prev_palette = st.session_state.get("asst_chart_palette", DEFAULT_PALETTE)
    _cur_idx = _palette_names.index(_prev_palette) if _prev_palette in _palette_names else 0
    _sel_palette = st.selectbox(
        "Paleta de cores",
        _palette_names,
        index=_cur_idx,
        key="asst_chart_palette_sel",
    )
    st.session_state["asst_chart_palette"] = _sel_palette
    _swatches_html = "".join(
        f'<span style="display:inline-block;width:20px;height:20px;border-radius:4px;'
        f'background:{c};margin:2px;border:1px solid #ffffff30"></span>'
        for c in CHART_PALETTES[_sel_palette]
    )
    st.markdown(f'<div style="margin-top:2px;line-height:1">{_swatches_html}</div>', unsafe_allow_html=True)
    if _sel_palette != _prev_palette:
        st.info("Paleta alterada. Repita o pedido no chat para gerar o grafico com as novas cores.", icon="🎨")
    else:
        st.caption("Selecione uma paleta e repita o pedido no chat para aplicar.")

    st.markdown("---")

    # Contexto adicional
    uploaded_ctx_file = st.file_uploader(
        "Arquivo de contexto", type=["txt", "docx", "pdf", "csv", "xlsx"],
        key="asst_context_file",
    )

    if uploaded_ctx_file:
        try:
            import io
            content = ""
            if uploaded_ctx_file.type == "text/plain":
                content = uploaded_ctx_file.read().decode("utf-8")
            elif uploaded_ctx_file.type == "application/pdf":
                try:
                    import PyPDF2
                    pdf_reader = PyPDF2.PdfReader(io.BytesIO(uploaded_ctx_file.read()))
                    content = " ".join([page.extract_text() for page in pdf_reader.pages])
                except ImportError:
                    content = "PDF import não disponível"
            else:
                content = uploaded_ctx_file.read().decode("utf-8", errors="ignore")[:50000]

            if content:
                st.session_state["_asst_file_ctx"] = content
                st.session_state["_asst_file_name"] = uploaded_ctx_file.name
                st.success(f"✅ {uploaded_ctx_file.name} carregado ({len(content):,} caracteres)")
        except Exception as e:
            st.error(f"Erro ao processar arquivo: {e}")

    if st.button("🗑️ Limpar conversa", key="asst_clear"):
        st.session_state["assistant_history"] = []
        st.session_state.pop("_asst_file_ctx", None)
        st.session_state.pop("_asst_file_name", None)
        st.rerun()

# ── Configurações ─────────────────────────────────────────────────────────────
selected_provider = st.session_state.get("asst_provider", "DeepSeek")
provider_cfg = AVAILABLE_PROVIDERS.get(selected_provider, AVAILABLE_PROVIDERS.get("DeepSeek", {}))
api_key = st.session_state.get("asst_api_key", "")
_chunks_table_ok = supabase_configured() and transcript_chunks_table_exists()

if "asst_use_semantic" not in st.session_state:
    st.session_state["asst_use_semantic"] = bool(
        st.session_state.get("asst_embed_key", "") and _chunks_table_ok
    )

# ── CSS — chat area ───────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Área de chat ── */
[data-testid="stChatMessageContainer"] {
    padding: .75rem 1rem !important;
    border-radius: 10px !important;
    margin-bottom: .5rem !important;
}
/* Mensagem do usuário */
[data-testid="stChatMessageContainer"][data-role="user"] {
    background: #0d2a4a !important;
    border: 1px solid #1e4a7a !important;
    border-left: 3px solid #3b82f6 !important;
}
/* Mensagem do assistente */
[data-testid="stChatMessageContainer"][data-role="assistant"] {
    background: #0f2235 !important;
    border: 1px solid #1a3a55 !important;
    border-left: 3px solid #C97B1A !important;
}
/* Texto das mensagens */
[data-testid="stChatMessageContainer"] .stMarkdown p,
[data-testid="stChatMessageContainer"] .stMarkdown li,
[data-testid="stChatMessageContainer"] .stMarkdown {
    color: #e2eaf4 !important;
    font-size: .93rem !important;
    line-height: 1.6 !important;
}
/* Headings dentro do chat */
[data-testid="stChatMessageContainer"] .stMarkdown h1,
[data-testid="stChatMessageContainer"] .stMarkdown h2,
[data-testid="stChatMessageContainer"] .stMarkdown h3 {
    color: #f0f4fa !important;
}
/* Código inline */
[data-testid="stChatMessageContainer"] .stMarkdown code {
    background: #1a3a5a !important;
    color: #7dd3fc !important;
    padding: 1px 6px !important;
    border-radius: 4px !important;
}
/* Bloco de código */
[data-testid="stChatMessageContainer"] .stMarkdown pre {
    background: #071628 !important;
    border: 1px solid #1e3a55 !important;
    border-radius: 6px !important;
}
/* Avatares */
[data-testid="chatAvatarIcon-user"],
[data-testid="chatAvatarIcon-assistant"] {
    background: transparent !important;
    border: none !important;
}
[data-testid="chatAvatarIcon-user"] svg,
[data-testid="chatAvatarIcon-assistant"] svg {
    fill: #3b82f6 !important;
}
[data-testid="chatAvatarIcon-assistant"] svg {
    fill: #C97B1A !important;
}
/* Fallback: qualquer elemento de avatar (baseweb) */
[data-baseweb="avatar"] {
    background: transparent !important;
}
[data-baseweb="avatar"] svg {
    fill: #3b82f6 !important;
}
/* Campo de entrada — todos os níveis do container */
[data-testid="stChatInput"],
[data-testid="stChatInput"] > div,
[data-testid="stChatInput"] > div > div,
[data-testid="stChatInput"] > div > div > div {
    background: #000000 !important;
    border-radius: 10px !important;
}
[data-testid="stChatInput"] {
    border: 1px solid #3a5a7a !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color: #C97B1A !important;
    box-shadow: 0 0 0 2px rgba(201,123,26,.25) !important;
}
/* Textarea */
[data-testid="stChatInput"] textarea {
    background: #000000 !important;
    color: #ffffff !important;
    caret-color: #ffffff !important;
}
[data-testid="stChatInput"] textarea::placeholder {
    color: #6b8aa8 !important;
}
/* Botão de envio — todos os níveis */
[data-testid="stChatInput"] button,
[data-testid="stChatInput"] button > div,
[data-testid="stChatInput"] [data-baseweb="button"],
[data-testid="stChatInputSubmitButton"] {
    background: #000000 !important;
    border: none !important;
    border-radius: 6px !important;
    color: #ffffff !important;
}
[data-testid="stChatInput"] button svg,
[data-testid="stChatInputSubmitButton"] svg {
    fill: #ffffff !important;
    stroke: #ffffff !important;
}
[data-testid="stChatInput"] button:hover svg,
[data-testid="stChatInputSubmitButton"]:hover svg {
    fill: #C97B1A !important;
    stroke: #C97B1A !important;
}
</style>
""", unsafe_allow_html=True)

# ── Main Area ─────────────────────────────────────────────────────────────────
_col_title, _col_mode, _col_help = st.columns([3, 2, 1])
with _col_title:
    st.markdown("# 💬 Assistente")
with _col_mode:
    st.radio(
        "Modo",
        ["💬 Assistente", "🔬 Análise Autônoma"],
        key="asst_mode",
        horizontal=True,
    )
with _col_help:
    with st.popover("❓ Modos"):
        st.markdown(
            "### 💬 Assistente\n"
            "Conversa interativa com os dados do projeto. "
            "Faça perguntas e receba respostas baseadas nas reuniões, "
            "requisitos e documentos armazenados.\n\n"
            "- Responde perguntas pontuais\n"
            "- Usa até 8 ferramentas por rodada\n"
            "- Mantém histórico da conversa\n"
            "- Ideal para consultas rápidas\n\n"
            "**Exemplos:**\n"
            "> *Quem participou da reunião 3?*\n\n"
            "> *Quais decisões foram tomadas sobre o módulo de pagamento?*\n\n"
            "> *Liste os requisitos funcionais de alta prioridade.*\n\n"
            "> *O que ficou pendente na última reunião?*\n\n"
            "---\n\n"
            "### 🔬 Análise Autônoma\n"
            "Agente que executa um objetivo analítico complexo de forma "
            "autônoma, sem intervenção manual a cada passo.\n\n"
            "- Planeja e encadeia múltiplas ferramentas (até 15 passos)\n"
            "- Produz relatório estruturado com conclusão, tabelas e gráficos\n"
            "- Ideal para análises cruzadas (ex: requisitos × decisões × prazos)\n"
            "- Resultados salvos no histórico do projeto\n\n"
            "**Exemplos:**\n"
            "> *Compare os requisitos funcionais aprovados com as decisões das "
            "últimas 3 reuniões e identifique lacunas de implementação.*\n\n"
            "> *Liste todas as ações em aberto por responsável, calcule o prazo "
            "médio de entrega e aponte os itens atrasados.*\n\n"
            "> *Gere um panorama completo do projeto: reuniões realizadas, "
            "volume de requisitos por tipo, decisões críticas e próximos passos.*\n\n"
            "---\n\n"
            "### Quando usar cada modo?\n\n"
            "| | 💬 Assistente | 🔬 Análise Autônoma |\n"
            "|---|---|---|\n"
            "| Profundidade | Resumo (amostra) | Exaustiva (tudo) |\n"
            "| Formato | Texto de chat | Relatório com tabelas |\n"
            "| Tempo | ~10–20 s | ~60–120 s |\n"
            "| Ideal para | Consultas rápidas e pontuais | Análises cruzadas completas |"
        )

if not supabase_configured():
    st.warning("⚙️ Supabase não configurado.")
    st.stop()

project_id, project_name = require_active_project()

_col_proj, _col_change = st.columns([5, 1])
with _col_proj:
    st.success(f"📁 **Contexto:** {project_name}")
with _col_change:
    st.page_link("pages/Home.py", label="Trocar")

# ── Guard: LLM API key ───────────────────────────────────────────────────────
if not api_key:
    st.warning("⚙️ Configure a chave de API em Configurações → LLM Assistente.")
    st.stop()

# ── Análise Autônoma mode branch ──────────────────────────────────────────────
if st.session_state.get("asst_mode") == "🔬 Análise Autônoma":
    _render_analyst_mode(project_id, project_name, api_key, provider_cfg, selected_provider)
    st.stop()

# ── Status badges ────────────────────────────────────────────────────────────
def _badge(icon: str, label: str, value: str, color: str) -> str:
    return (
        f'<span style="display:inline-flex;align-items:center;gap:5px;'
        f'background:{color};border-radius:20px;padding:4px 12px;'
        f'font-size:0.78rem;font-weight:600;color:#fff;white-space:nowrap;">'
        f'{icon} <span style="opacity:.75">{label}</span> {value}'
        f'</span>'
    )

_use_sem    = st.session_state.get("asst_use_semantic", False) and _chunks_table_ok
_embed_prov = st.session_state.get("asst_embed_provider", "")
_embed_key  = st.session_state.get("asst_embed_key", "")
_model      = provider_cfg.get("default_model", "")

_badges = [
    _badge("📁", "Contexto", project_name, "#1A4B8C"),
    _badge("🤖", "LLM", selected_provider, "#C97B1A"),
    _badge("⚡", "Modelo", _model, "#1e3a5f"),
]

if _use_sem and _embed_key:
    _badges.append(_badge("🔮", "Busca", "Semântica · pgvector", "#6B3FA0"))
    _badges.append(_badge("🧮", "Embedding", _embed_prov, "#4A2870"))
else:
    _badges.append(_badge("🔑", "Busca", "Keyword", "#374151"))

if _chunks_table_ok:
    _cov = get_embedding_coverage(project_id)
    _idx = _cov.get("indexed_meetings", 0)
    _tot = _cov.get("total_meetings", 0)
    _chunks_n = _cov.get("total_chunks", 0)
    if _idx > 0:
        _badges.append(_badge("📊", "Índice", f"{_idx}/{_tot} reuniões · {_chunks_n:,} chunks", "#1A7F5A"))

_ctx_file_name = st.session_state.get("_asst_file_name", "")
if _ctx_file_name:
    _ctx_words = len(st.session_state.get("_asst_file_ctx", "").split())
    _badges.append(_badge("📎", "Arquivo", f"{_ctx_file_name} · {_ctx_words:,} palavras", "#374151"))

st.markdown(
    '<div style="display:flex;flex-wrap:wrap;gap:8px;margin:8px 0 16px 0;">'
    + "".join(_badges)
    + "</div>",
    unsafe_allow_html=True,
)

_DSML_SAFETY_RE = re.compile(r'<[|\uff5c]DSML[|\uff5c][^>]*>.*?<[|\uff5c]DSML[|\uff5c][^>]*>', re.DOTALL)
_DSML_CUT_RE    = re.compile(r'<[|\uff5c]DSML[|\uff5c]')


def _clean_response(text: str) -> str:
    """Safety-net: strip any DSML markup that leaked through the agent layer."""
    m = _DSML_CUT_RE.search(text)
    if m:
        text = text[:m.start()].rstrip()
    text = _DSML_SAFETY_RE.sub('', text)
    return text.strip()


def _render_message_tables(tables: list[dict], msg_idx: int, project_name: str, question: str) -> None:
    """Render tables stored in a message dict as st.dataframe + Excel download button."""
    import pandas as pd
    from datetime import datetime as _dt
    for ti, table_data in enumerate(tables):
        columns = table_data.get("columns", [])
        rows    = table_data.get("rows", [])
        title   = table_data.get("title", "Tabela")
        if not columns or not rows:
            continue

        st.markdown(f"**{title}**")
        df = pd.DataFrame(rows, columns=columns)
        st.dataframe(df, use_container_width=True, hide_index=True)

        cache_key = f"_excel_bytes_{msg_idx}_{ti}"
        if cache_key not in st.session_state:
            st.session_state[cache_key] = export_table_to_excel(
                table_data=table_data,
                question=question,
                project_name=project_name,
            )

        ct = table_data.get("chart_type", "none")
        chart_label = f" + grafico {ct}" if ct and ct != "none" else ""
        filename = f"p2d_tabela_{_dt.now().strftime('%Y%m%d_%H%M')}.xlsx"

        st.download_button(
            label=f"Exportar para Excel{chart_label}",
            data=st.session_state[cache_key],
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"btn_excel_{msg_idx}_{ti}",
        )


def _render_message_widgets(widgets: list[dict], msg_idx: int) -> None:
    """Render A2UI widgets (BPMN, Mermaid, metrics) stored in a message dict."""
    import streamlit.components.v1 as _stc
    for wi, widget in enumerate(widgets):
        w_type = widget.get("type")
        title  = widget.get("title", "")
        if title:
            st.markdown(f"**{title}**")
        if w_type == "bpmn":
            xml = widget.get("xml", "")
            if xml:
                try:
                    from modules.bpmn_viewer import preview_from_xml
                    _stc.html(preview_from_xml(xml), height=500, scrolling=False)
                except Exception as _e:
                    st.warning(f"Não foi possível renderizar o BPMN: {_e}")
        elif w_type == "mermaid":
            code = widget.get("code", "")
            if code:
                try:
                    from modules.mermaid_renderer import render_mermaid_block
                    render_mermaid_block(
                        code,
                        show_code=False,
                        key_suffix=f"asst_{msg_idx}_{wi}",
                        height=400,
                    )
                except Exception as _e:
                    st.warning(f"Não foi possível renderizar o Mermaid: {_e}")
        elif w_type == "transcript":
            content = widget.get("content", "")
            wc = widget.get("word_count", 0)
            cc = widget.get("char_count", 0)
            st.caption(f"{wc:,} palavras · {cc:,} caracteres")
            st.text_area(
                label="transcrição",
                value=content,
                height=420,
                disabled=True,
                key=f"ta_asst_transcript_{msg_idx}_{wi}",
                label_visibility="collapsed",
            )
        elif w_type == "metrics":
            items = widget.get("items") or []
            if items:
                n_cols = min(len(items), 4)
                cols = st.columns(n_cols)
                for ci, item in enumerate(items):
                    with cols[ci % n_cols]:
                        st.metric(
                            label=item.get("label", ""),
                            value=str(item.get("value", "")),
                            delta=item.get("delta") or None,
                        )


def _export_chat_to_markdown(
    messages: list[dict],
    project_name: str,
    provider: str,
) -> str:
    """Format conversation history as a Markdown document for download."""
    from datetime import datetime as _dt
    lines = [
        "# Conversa — Assistente P2D",
        f"**Contexto:** {project_name}",
        f"**Data:** {_dt.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Provedor LLM:** {provider}",
        "",
        "---",
        "",
    ]
    turn = 0
    for msg in messages:
        if msg["role"] == "user":
            turn += 1
            lines += [f"## Turno {turn}", "", f"**Voce:** {msg['content']}", ""]
        elif msg["role"] == "assistant":
            tools = msg.get("tools_used") or []
            meta = provider
            if tools:
                meta += f" · ferramentas: {', '.join(tools)}"
            lines += [f"**Assistente ({meta}):**", "", msg["content"], "", "---", ""]
    return "\n".join(lines)


def _export_chat_to_html(
    messages: list[dict],
    project_name: str,
    provider: str,
) -> str:
    """Build a self-contained HTML export of the conversation, including Plotly charts."""
    import json
    from datetime import datetime as _dt

    ts = _dt.now().strftime("%Y-%m-%d %H:%M")

    # ── Collect all chart dicts to decide whether to include Plotly CDN ──────
    has_charts = any(msg.get("charts") for msg in messages)
    plotly_cdn = (
        '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>\n'
        if has_charts else ""
    )

    # ── Build message blocks ──────────────────────────────────────────────────
    blocks: list[str] = []
    turn = 0
    for msg in messages:
        role = msg["role"]
        content = msg.get("content", "")
        charts = msg.get("charts") or []
        tools = msg.get("tools_used") or []

        if role == "user":
            turn += 1
            blocks.append(f"""
<div class="msg msg-user">
  <div class="msg-label">Você</div>
  <div class="msg-body md-content" data-md="{_html_escape_attr(content)}">{_html_escape(content)}</div>
</div>""")
        elif role == "assistant":
            tool_badge = ""
            if tools:
                tool_badge = "".join(
                    f'<span class="tool-badge">{_html_escape(t)}</span>' for t in tools
                )
            chart_html = ""
            for ci, chart_dict in enumerate(charts):
                div_id = f"chart_{turn}_{ci}"
                chart_json = json.dumps(chart_dict)
                chart_html += f"""
<div class="chart-wrap">
  <div id="{div_id}" class="plotly-chart"></div>
  <script>
    (function() {{
      var spec = {chart_json};
      var fig = spec;
      Plotly.newPlot('{div_id}',
        fig.data || [],
        Object.assign({{paper_bgcolor:'#0B1E3D',plot_bgcolor:'#0B1E3D',
          font:{{color:'#FAFAF8'}},margin:{{t:40,b:40,l:40,r:20}}}}, fig.layout || {{}}),
        {{responsive:true, displayModeBar:true}}
      );
    }})();
  </script>
</div>"""
            blocks.append(f"""
<div class="msg msg-assistant">
  <div class="msg-label">Assistente <span class="provider-label">{_html_escape(provider)}</span>{tool_badge}</div>
  <div class="msg-body md-content" data-md="{_html_escape_attr(content)}">{_html_escape(content)}</div>
  {chart_html}
</div>""")

    body = "\n".join(blocks)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conversa — {_html_escape(project_name)}</title>
{plotly_cdn}<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #071428;
    color: #FAFAF8;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 14px;
    line-height: 1.6;
    padding: 0;
  }}
  .page-header {{
    background: linear-gradient(135deg, #071428 0%, #0B1E3D 55%, #122848 100%);
    border-bottom: 3px solid #C97B1A;
    padding: 1.2rem 2rem;
  }}
  .page-header h1 {{ font-size: 1.2rem; color: #FAFAF8; font-weight: 700; }}
  .page-header .meta {{ font-size: .75rem; color: #7A8EA8; margin-top: .3rem; }}
  .chat-container {{ max-width: 860px; margin: 0 auto; padding: 1.5rem 1rem 4rem; }}
  .msg {{ border-radius: 10px; margin-bottom: 1rem; padding: 1rem 1.2rem; }}
  .msg-user {{
    background: #0d2a4a;
    border-left: 4px solid #2563EB;
  }}
  .msg-assistant {{
    background: #0f2235;
    border-left: 4px solid #C97B1A;
  }}
  .msg-label {{
    font-size: .68rem; font-weight: 800; letter-spacing: .09em;
    text-transform: uppercase; color: #7A8EA8; margin-bottom: .5rem;
    display: flex; align-items: center; gap: .4rem; flex-wrap: wrap;
  }}
  .provider-label {{
    font-weight: 400; text-transform: none; letter-spacing: 0;
    color: #C97B1A; font-size: .68rem;
  }}
  .tool-badge {{
    background: #1A2E48; color: #60A5FA;
    border: 1px solid #1D4A80;
    border-radius: 4px; padding: .1rem .4rem;
    font-size: .60rem; font-weight: 700; letter-spacing: .05em;
    text-transform: none;
  }}
  .msg-body {{ color: #D4E1F5; }}
  .msg-body h1,.msg-body h2,.msg-body h3 {{
    color: #FAFAF8; margin: .8rem 0 .4rem; font-size: 1rem;
  }}
  .msg-body h1 {{ font-size: 1.15rem; }}
  .msg-body p {{ margin: .5rem 0; }}
  .msg-body ul,.msg-body ol {{ margin: .5rem 0 .5rem 1.4rem; }}
  .msg-body li {{ margin: .2rem 0; }}
  .msg-body code {{
    background: #0A1628; color: #93C5FD;
    padding: .1rem .35rem; border-radius: 4px;
    font-family: 'Courier New', monospace; font-size: .85em;
  }}
  .msg-body pre {{
    background: #050D1A; border: 1px solid #1A2E48;
    border-radius: 8px; padding: .8rem 1rem;
    overflow-x: auto; margin: .6rem 0;
  }}
  .msg-body pre code {{ background: none; padding: 0; color: #93C5FD; }}
  .msg-body table {{
    width: 100%; border-collapse: collapse; margin: .6rem 0; font-size: .82rem;
  }}
  .msg-body th {{
    background: #0B1E3D; color: #FAFAF8;
    padding: .4rem .7rem; text-align: left; border: 1px solid #1A3050;
  }}
  .msg-body td {{ padding: .35rem .7rem; border: 1px solid #1A2E48; color: #B0C4DE; }}
  .msg-body tr:nth-child(even) td {{ background: #071428; }}
  .msg-body blockquote {{
    border-left: 3px solid #C97B1A; margin: .5rem 0;
    padding: .3rem .8rem; color: #9AAABB; background: #0A1628;
    border-radius: 0 6px 6px 0;
  }}
  .msg-body a {{ color: #60A5FA; }}
  .msg-body strong {{ color: #FAFAF8; }}
  .msg-body em {{ color: #A3B8CC; }}
  .msg-body hr {{ border: none; border-top: 1px solid #1A2E48; margin: .8rem 0; }}
  .chart-wrap {{ margin-top: .8rem; }}
  .plotly-chart {{ width: 100%; min-height: 380px; }}
  .page-footer {{
    text-align: center; font-size: .70rem; color: #4A6A8A;
    padding: 1.5rem; border-top: 1px solid #1A2E48; margin-top: 2rem;
  }}
</style>
</head>
<body>
<div class="page-header">
  <h1>💬 Conversa — {_html_escape(project_name)}</h1>
  <div class="meta">Exportado em {ts} · Provedor: {_html_escape(provider)}</div>
</div>
<div class="chat-container">
{body}
</div>
<div class="page-footer">
  Gerado por Process2Diagram · {ts}
</div>
<script>
  // Render Markdown in all .md-content elements
  document.querySelectorAll('.md-content').forEach(function(el) {{
    var md = el.getAttribute('data-md') || '';
    if (md) el.innerHTML = marked.parse(md);
  }});
</script>
</body>
</html>"""


def _html_escape(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def _html_escape_attr(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("\n", "&#10;")
            .replace("\r", ""))


# ── Session history ───────────────────────────────────────────────────────────
if "assistant_history" not in st.session_state:
    st.session_state["assistant_history"] = []

history: list[dict] = st.session_state["assistant_history"]

# ── Modo Plantonista — briefing automático na primeira abertura ───────────────
_plantonista_key = f"_plantonista_done_{project_id}"
if (
    not history
    and project_id
    and st.session_state.get("asst_use_tools", True)
    and not st.session_state.get(_plantonista_key)
):
    try:
        from core.assistant_tools import AssistantToolExecutor as _ATE
        _executor = _ATE(project_id=project_id)
        _briefing = _executor.sugestoes_plantonista()
        if _briefing:
            history.append({"role": "assistant", "content": _briefing, "charts": [], "tables": [], "widgets": []})
            st.session_state["assistant_history"] = history
    except Exception:
        pass
    st.session_state[_plantonista_key] = True


# ── Chat toolbar (export + limpar) ───────────────────────────────────────
if st.session_state.get("_confirm_clear"):
    st.warning("Limpar toda a conversa? Esta acao nao pode ser desfeita.")
    _cy, _cn, _ = st.columns([1, 1, 8])
    with _cy:
        if st.button("Confirmar", key="btn_clear_yes", type="primary"):
            for _ck in ["assistant_history", "_edit_idx", "_edit_draft",
                        "_resubmit_question", "_confirm_clear"]:
                st.session_state.pop(_ck, None)
            st.rerun()
    with _cn:
        if st.button("Cancelar", key="btn_clear_no"):
            st.session_state.pop("_confirm_clear", None)
            st.rerun()
    st.markdown("---")

if history:
    _tb_md, _tb_html, _tb_clear, _tb_info = st.columns([1.1, 1.1, 1, 5])
    from datetime import datetime as _dt2
    _ts_str = _dt2.now().strftime("%Y%m%d_%H%M")
    with _tb_md:
        _export_md = _export_chat_to_markdown(history, project_name, selected_provider)
        st.download_button(
            "⬇️ Markdown",
            data=_export_md,
            file_name=f"conversa_{_ts_str}.md",
            mime="text/markdown",
            key="btn_export_chat_md",
            help="Baixar conversa como Markdown",
        )
    with _tb_html:
        _export_html = _export_chat_to_html(history, project_name, selected_provider)
        st.download_button(
            "⬇️ HTML",
            data=_export_html.encode("utf-8"),
            file_name=f"conversa_{_ts_str}.html",
            mime="text/html",
            key="btn_export_chat_html",
            help="Baixar conversa como HTML com gráficos interativos",
        )
    with _tb_clear:
        if st.button("🗑️ Limpar", key="btn_clear_chat", help="Limpar historico"):
            st.session_state["_confirm_clear"] = True
            st.rerun()
    with _tb_info:
        _n_turns = sum(1 for _m in history if _m["role"] == "user")
        st.caption(f"{_n_turns} pergunta(s) · {len(history)} mensagens")

# ── Render existing conversation ──────────────────────────────────────────────
_editing_idx: int | None = st.session_state.get("_edit_idx")

for i, msg in enumerate(history):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        # Render charts attached to this assistant message
        if msg["role"] == "assistant":
            for ci, fig_dict in enumerate(msg.get("charts") or []):
                try:
                    import plotly.graph_objects as go
                    fig = go.Figure(fig_dict)
                    st.plotly_chart(fig, use_container_width=True, key=f"chart_{i}_{ci}")
                except Exception as _chart_err:
                    st.caption(f"⚠️ Não foi possível renderizar o gráfico: {_chart_err}")
            # Render tables attached to this assistant message
            if msg.get("tables"):
                _render_message_tables(
                    tables=msg["tables"],
                    msg_idx=i,
                    project_name=st.session_state.get("active_project_name", ""),
                    question=msg.get("question", ""),
                )
            # Render A2UI widgets (BPMN, Mermaid, metrics)
            if msg.get("widgets"):
                _render_message_widgets(msg["widgets"], i)
            # ── Relatório executivo disponível para download ───────────────────
            if rd := msg.get("report_download"):
                _rk  = rd.get("cache_key", "")
                _fn  = rd.get("filename", "relatorio_executivo.html")
                _num = rd.get("meeting_number", 0)
                if _rk and _rk in st.session_state:
                    st.download_button(
                        label=f"⬇️ Relatório Executivo — Reunião {_num}",
                        data=st.session_state[_rk],
                        file_name=_fn,
                        mime="text/html",
                        key=f"btn_report_dl_{i}_{_num}",
                    )
        if msg["role"] == "user":
            col_edit, col_copy, _ = st.columns([1, 1, 8])
            with col_edit:
                if st.button("✏️", key=f"_edit_btn_{i}", help="Reeditar esta pergunta"):
                    st.session_state["_edit_idx"]   = i
                    st.session_state["_edit_draft"] = msg["content"]
                    st.rerun()
            with col_copy:
                copy_button(msg["content"], key=f"copy_q_{i}", label="📋", compact=True)
        else:
            copy_button(msg["content"], key=f"copy_a_{i}", label="📋 Copiar resposta", compact=True)

# ── Edit panel (shown when a message is being re-edited) ──────────────────────
if _editing_idx is not None:
    st.markdown("---")
    st.markdown(
        f"**✏️ Reeditando pergunta {_editing_idx // 2 + 1}** "
        f"— as respostas seguintes serão descartadas."
    )
    edited_text = st.text_area(
        "Editar pergunta:",
        value=st.session_state.get("_edit_draft", ""),
        height=100,
        key="_edit_ta",
    )
    col_cancel, col_submit = st.columns([1, 3])
    with col_cancel:
        if st.button("✖️ Cancelar", key="_edit_cancel", use_container_width=True):
            st.session_state.pop("_edit_idx", None)
            st.session_state.pop("_edit_draft", None)
            st.rerun()
    with col_submit:
        if st.button("🔄 Reenviar", key="_edit_submit", type="primary", use_container_width=True):
            if edited_text.strip():
                st.session_state["assistant_history"] = history[:_editing_idx]
                st.session_state["_resubmit_question"] = edited_text.strip()
                st.session_state.pop("_edit_idx", None)
                st.session_state.pop("_edit_draft", None)
                st.rerun()

# ── Polling block — tool-use running in background thread ─────────────────────
_asst_running = st.session_state.get("_asst_running", False)

if _asst_running:
    thread: threading.Thread = st.session_state.get("_asst_thread")
    cancel_ev: threading.Event = st.session_state.get("_asst_cancel_event")
    result_box: dict = st.session_state.get("_asst_result_box", {})

    if thread and thread.is_alive():
        status_msg = st.session_state.get("_asst_status", "🔧 Consultando ferramentas…")
        with st.chat_message("assistant"):
            st.markdown(f"_{status_msg}_")

        col_msg, col_stop = st.columns([4, 1])
        with col_msg:
            st.caption(status_msg)
        with col_stop:
            if st.button("⏹ Parar", key="asst_stop_btn", type="secondary", use_container_width=True):
                cancel_ev.set()
                st.session_state["_asst_status"] = "⏹ Interrompendo…"

        time.sleep(0.6)
        st.rerun()

    else:
        if thread:
            thread.join(timeout=2)

        response_text = result_box.get("response") or "❌ Sem resposta."
        tokens_used   = result_box.get("tokens", 0)
        tools_called  = result_box.get("tools_called", [])
        charts        = result_box.get("charts", [])
        error         = result_box.get("error")

        if error and not result_box.get("response"):
            response_text = f"❌ Erro: {error}"

        response_text = _clean_response(response_text) or response_text
        pending_tables  = st.session_state.pop("_pending_tables",  [])
        pending_widgets = st.session_state.pop("_pending_widgets", [])
        history = st.session_state["assistant_history"]
        last_question = history[-1]["content"] if history and history[-1]["role"] == "user" else ""
        history.append({
            "role":    "assistant",
            "content": response_text,
            "charts":  charts,
            "tables":  pending_tables,
            "widgets": pending_widgets,
            "question": last_question,
        })

        # ── Relatório executivo pendente (get_executive_report tool) ──────────
        if _pending_report := st.session_state.pop("_pending_report_html", None):
            _rkey = _pending_report.get("cache_key", f"_report_dl_{_pending_report.get('meeting_number', 0)}")
            if _rkey not in st.session_state and _pending_report.get("html"):
                st.session_state[_rkey] = _pending_report["html"].encode()
            history[-1]["report_download"] = {
                "cache_key": _rkey,
                "filename":  _pending_report.get("filename", "relatorio_executivo.html"),
                "meeting_number": _pending_report.get("meeting_number", 0),
            }

        st.session_state["assistant_history"] = history

        st.session_state["_asst_last_caption"] = {
            "tokens": tokens_used,
            "tools": tools_called,
            "mode": "tools",
            "error": error,
        }

        for _k in ("_asst_running", "_asst_thread", "_asst_cancel_event",
                   "_asst_result_box", "_asst_status"):
            st.session_state.pop(_k, None)

        st.rerun()

# Show caption from the just-completed tool-use turn (survives one rerun)
if "_asst_last_caption" in st.session_state:
    cap = st.session_state.pop("_asst_last_caption")
    tools_called = cap.get("tools", [])
    tokens_used  = cap.get("tokens", 0)
    if tools_called:
        tools_str = " · ".join(f"`{t}`" for t in tools_called)
        st.caption(f"🔢 {tokens_used} tokens · 🔧 ferramentas usadas: {tools_str}")
    else:
        st.caption(f"🔢 {tokens_used} tokens · 🔧 tool-use (sem chamadas externas)")
    if cap.get("error"):
        st.warning(f"⚠️ Erro interno: {cap['error']}")

# ── New message input ─────────────────────────────────────────────────────────
question = st.chat_input(
    "Faça uma pergunta sobre as reuniões, requisitos, processos ou sobre como usar o sistema...",
    disabled=(_editing_idx is not None or _asst_running),
)

# Aceita pergunta nova ou pergunta reeditada
active_question: str | None = (
    st.session_state.pop("_resubmit_question", None)
    or question
)

if active_question and not _asst_running:
    # File context is injected into the LLM question but NOT shown in chat UI
    display_question = active_question
    _file_ctx  = st.session_state.get("_asst_file_ctx", "")
    _file_name = st.session_state.get("_asst_file_name", "")
    if _file_ctx:
        _n_words = len(_file_ctx.split())
        llm_question = (
            f"[ARQUIVO ANEXADO: {_file_name} — {_n_words:,} palavras]\n"
            f"{'─' * 50}\n"
            f"{_file_ctx}\n"
            f"{'─' * 50}\n\n"
            f"{display_question}"
        )
    else:
        llm_question = display_question

    question = display_question
    history = st.session_state["assistant_history"]

    history.append({"role": "user", "content": display_question})
    with st.chat_message("user"):
        st.markdown(display_question)

    use_tools_now = st.session_state.get("asst_use_tools", True)

    # ── Caminho A: Tool-use — background thread com botão Parar ──────────────
    if use_tools_now:
        _cancel_ev  = threading.Event()
        _result_box: dict = {}

        _api_key       = api_key
        _provider_cfg  = provider_cfg
        _history_snap  = list(history[:-1])
        _question      = llm_question
        _project_id    = project_id
        _project_name  = project_name

        def _run_tools_thread() -> None:
            def _status(msg: str) -> None:
                try:
                    st.session_state["_asst_status"] = msg
                except Exception:
                    pass

            try:
                _status("🔧 Iniciando consulta…")
                _chart_palette = st.session_state.get("asst_chart_palette", "P2D Dark")
                _agent = AgentAssistant({"api_key": _api_key, "chart_palette": _chart_palette}, _provider_cfg)
                resp_text, tok, tools, charts = _agent.chat_with_tools(
                    history=_history_snap,
                    question=_question,
                    project_id=_project_id,
                    project_name=_project_name,
                    cancel_event=_cancel_ev,
                    status_fn=_status,
                )
                _result_box["response"]     = resp_text
                _result_box["tokens"]       = tok
                _result_box["tools_called"] = tools
                _result_box["charts"]       = charts
            except Exception as _exc:
                _status("⚠️ Tool-use falhou — usando busca por keyword…")
                try:
                    _ctx  = retrieve_context_for_question(_project_id, _question)
                    _ctxt = format_context(_ctx, _project_name)
                    _agent2 = AgentAssistant({"api_key": _api_key}, _provider_cfg)
                    resp_text, tok = _agent2.chat(
                        history=_history_snap,
                        context_text=_ctxt,
                        question=_question,
                    )
                    _result_box["response"]     = resp_text
                    _result_box["tokens"]       = tok
                    _result_box["tools_called"] = []
                    _result_box["error"]        = f"tool-use falhou: {_exc} (fallback keyword)"
                except Exception as _exc2:
                    _result_box["response"]     = f"❌ Erro ao gerar resposta: {_exc2}"
                    _result_box["tokens"]       = 0
                    _result_box["tools_called"] = []
                    _result_box["error"]        = str(_exc2)

        _thread = threading.Thread(target=_run_tools_thread, daemon=True)
        try:
            from streamlit.runtime.scriptrunner import add_script_run_ctx
            add_script_run_ctx(_thread)
        except Exception:
            pass
        st.session_state["_asst_running"]      = True
        st.session_state["_asst_thread"]       = _thread
        st.session_state["_asst_cancel_event"] = _cancel_ev
        st.session_state["_asst_result_box"]   = _result_box
        st.session_state["_asst_status"]       = "🔧 Iniciando consulta…"
        st.session_state["assistant_history"]  = history
        _thread.start()
        st.rerun()

    # ── Caminho B: RAG clássico (keyword / semântico) ─────────────────────────
    else:
        use_semantic_now = (
            st.session_state.get("asst_use_semantic", False)
            and _chunks_table_ok
        )

        if use_semantic_now:
            embed_key_now = st.session_state.get("asst_embed_key", "")
            embed_provider_now = st.session_state.get(
                "asst_embed_provider", list(EMBEDDING_PROVIDERS.keys())[0]
            )
            if not embed_key_now:
                st.warning("⚠️ Busca semântica ativa mas sem API key de embedding. Usando keyword.")
                use_semantic_now = False

        with st.spinner("🔍 Pesquisando nas fontes de dados..."):
            if use_semantic_now:
                ctx = retrieve_context_semantic(
                    project_id=project_id,
                    question=display_question,
                    api_key=embed_key_now,
                    provider=embed_provider_now,
                )
            else:
                ctx = retrieve_context_for_question(project_id, display_question)

            context_text = format_context(ctx, project_name)

            if _file_ctx:
                _n_words = len(_file_ctx.split())
                context_text = (
                    f"## Arquivo Anexado: {_file_name} ({_n_words:,} palavras)\n\n"
                    f"{_file_ctx}\n\n"
                    f"---\n\n"
                    + context_text
                )

        meetings_passages = ctx.get("meetings_passages") or []
        no_transcript     = ctx.get("meetings_without_transcript") or []
        search_mode       = ctx.get("search_mode", "keyword")

        if search_mode == "keyword_fallback":
            st.info(
                "ℹ️ Embeddings ainda não gerados — usando busca por **keyword**. "
                "Gere os embeddings em Banco de Dados → Embeddings para ativar a busca semântica.",
                icon=None,
            )
        if not meetings_passages and no_transcript:
            st.warning(
                "⚠️ Nenhum trecho relevante encontrado. "
                "Reuniões sem correspondência: " + ", ".join(no_transcript)
            )

        with st.spinner("🤖 Gerando resposta..."):
            client_info = {"api_key": api_key}
            agent = AgentAssistant(client_info, provider_cfg)
            try:
                response_text, tokens_used = agent.chat(
                    history=history[:-1],
                    context_text=context_text,
                    question=question,
                )
            except Exception as exc:
                response_text = f"❌ Erro ao gerar resposta: {exc}"
                tokens_used = 0

        response_text = _clean_response(response_text) or response_text
        history.append({"role": "assistant", "content": response_text})
        st.session_state["assistant_history"] = history

        with st.chat_message("assistant"):
            st.markdown(response_text)

        n_meetings = len(meetings_passages)
        if search_mode == "semantic":
            mode_badge = "🔮 semântica"
        elif search_mode == "keyword_fallback":
            mode_badge = "🔑 keyword (fallback)"
        else:
            mode_badge = "🔑 keyword"
        st.caption(
            f"🔢 {tokens_used} tokens · {n_meetings} reunião(ões) · {mode_badge}"
        )
