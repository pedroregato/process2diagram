# modules/minutes_exporter.py
# ─────────────────────────────────────────────────────────────────────────────
# Export MinutesModel to Word (.docx) and PDF.
#
# to_docx(minutes) → bytes   — python-docx
# to_pdf(minutes)  → bytes   — fpdf2 (pure Python, Latin-1 covers Portuguese)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.knowledge_hub import MinutesModel


# ── Shared helpers ────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now().strftime("%d/%m/%Y")


def _prio_label(p: str) -> str:
    return {"high": "Alta", "normal": "Normal", "low": "Baixa"}.get(p, p.capitalize())


# ── Word (.docx) ──────────────────────────────────────────────────────────────

def to_docx(minutes: "MinutesModel") -> bytes:
    """Generate a Word document from MinutesModel. Returns raw bytes."""
    from docx import Document
    from docx.shared import Pt, RGBColor, Inches, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    NAVY   = RGBColor(0x0B, 0x1E, 0x3D)
    ACCENT = RGBColor(0x2E, 0x7F, 0xD9)
    MUTED  = RGBColor(0x64, 0x74, 0x8B)

    doc = Document()

    # ── Page margins ─────────────────────────────────────────────────────────
    for section in doc.sections:
        section.top_margin    = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin   = Cm(2.5)
        section.right_margin  = Cm(2.5)

    # ── Default paragraph style ───────────────────────────────────────────────
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    # ── Title ─────────────────────────────────────────────────────────────────
    title_para = doc.add_paragraph()
    title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = title_para.add_run(minutes.title or "Ata de Reunião")
    run.bold = True
    run.font.size = Pt(20)
    run.font.color.rgb = NAVY

    # ── Metadata line ─────────────────────────────────────────────────────────
    meta = doc.add_paragraph()
    meta.alignment = WD_ALIGN_PARAGRAPH.CENTER
    parts = []
    if minutes.date:
        parts.append(f"Data: {minutes.date}")
    if minutes.location:
        parts.append(f"Local/Modalidade: {minutes.location}")
    parts.append(f"Gerado em: {_now()}")
    for i, part in enumerate(parts):
        if i:
            r = meta.add_run("   ·   ")
            r.font.color.rgb = MUTED
        r = meta.add_run(part)
        r.font.color.rgb = MUTED
        r.font.size = Pt(10)

    doc.add_paragraph()  # spacer

    def _heading(text: str) -> None:
        h = doc.add_paragraph()
        run = h.add_run(text.upper())
        run.bold = True
        run.font.size = Pt(9)
        run.font.color.rgb = ACCENT
        run.font.name = "Calibri"
        # Bottom border
        pPr = h._p.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "4")
        bottom.set(qn("w:space"), "4")
        bottom.set(qn("w:color"), "2E7FD9")
        pBdr.append(bottom)
        pPr.append(pBdr)
        h.paragraph_format.space_after = Pt(4)

    def _bullet(text: str) -> None:
        p = doc.add_paragraph(style="List Bullet")
        p.add_run(text).font.size = Pt(11)
        p.paragraph_format.space_after = Pt(2)

    def _body(text: str) -> None:
        p = doc.add_paragraph(text)
        p.paragraph_format.space_after = Pt(4)

    # ── Participants ──────────────────────────────────────────────────────────
    if minutes.participants:
        _heading("Participantes")
        for p in minutes.participants:
            _bullet(p)
        doc.add_paragraph()

    # ── Agenda ────────────────────────────────────────────────────────────────
    if minutes.agenda:
        _heading("Pauta")
        for i, item in enumerate(minutes.agenda, 1):
            p = doc.add_paragraph(style="List Number")
            p.add_run(item).font.size = Pt(11)
            p.paragraph_format.space_after = Pt(2)
        doc.add_paragraph()

    # ── Summary ───────────────────────────────────────────────────────────────
    if minutes.summary:
        _heading("Resumo da Reunião")
        for block in minutes.summary:
            topic   = block.get("topic", "")
            content = block.get("content", "")
            if topic:
                sub = doc.add_paragraph()
                run = sub.add_run(topic)
                run.bold = True
                run.font.size = Pt(11)
                run.font.color.rgb = NAVY
                sub.paragraph_format.space_before = Pt(6)
                sub.paragraph_format.space_after  = Pt(2)
            if content:
                _body(content)
        doc.add_paragraph()

    # ── Decisions ─────────────────────────────────────────────────────────────
    if minutes.decisions:
        _heading("Decisões Tomadas")
        for d in minutes.decisions:
            _bullet(d)
        doc.add_paragraph()

    # ── Action Items table ────────────────────────────────────────────────────
    if minutes.action_items:
        _heading(f"Encaminhamentos / Action Items ({len(minutes.action_items)})")
        doc.add_paragraph()

        headers = ["Prioridade", "Tarefa", "Responsável", "Prazo", "Levantado por"]
        table = doc.add_table(rows=1, cols=len(headers))
        table.style = "Table Grid"

        # Header row
        hdr_cells = table.rows[0].cells
        for i, h in enumerate(headers):
            hdr_cells[i].text = h
            run = hdr_cells[i].paragraphs[0].runs[0]
            run.bold = True
            run.font.size = Pt(10)
            run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
            # Navy background
            tc = hdr_cells[i]._tc
            tcPr = tc.get_or_add_tcPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), "0B1E3D")
            tcPr.append(shd)

        # Data rows
        for ai in minutes.action_items:
            row_cells = table.add_row().cells
            row_cells[0].text = _prio_label(ai.priority)
            row_cells[1].text = ai.task
            row_cells[2].text = ai.responsible
            row_cells[3].text = ai.deadline or "—"
            row_cells[4].text = ai.raised_by or "—"
            for cell in row_cells:
                for para in cell.paragraphs:
                    for run in para.runs:
                        run.font.size = Pt(10)

        doc.add_paragraph()

    # ── Next meeting ──────────────────────────────────────────────────────────
    if minutes.next_meeting:
        _heading("Próxima Reunião")
        p = doc.add_paragraph()
        run = p.add_run(minutes.next_meeting)
        run.font.size = Pt(11)
        run.font.color.rgb = NAVY
        doc.add_paragraph()

    # ── Footer note ───────────────────────────────────────────────────────────
    footer_para = doc.add_paragraph()
    footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = footer_para.add_run(f"Documento gerado automaticamente por Process2Diagram — {_now()}")
    run.font.size = Pt(9)
    run.font.color.rgb = MUTED
    run.italic = True

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ── PDF ───────────────────────────────────────────────────────────────────────

# fpdf2 core fonts (Helvetica) are limited to Latin-1 (ISO 8859-1).
# This helper replaces common non-Latin-1 characters with safe equivalents
# before passing text to fpdf cells/multi_cell calls.
_PDF_CHAR_MAP = {
    "\u2014": "-",    # em dash
    "\u2013": "-",    # en dash
    "\u2012": "-",    # figure dash
    "\u2010": "-",    # hyphen
    "\u2022": "*",    # bullet
    "\u2023": ">",    # triangular bullet
    "\u2192": "->",   # right arrow
    "\u2190": "<-",   # left arrow
    "\u2026": "...",  # horizontal ellipsis
    "\u201c": '"',    # left double quotation mark
    "\u201d": '"',    # right double quotation mark
    "\u2018": "'",    # left single quotation mark
    "\u2019": "'",    # right single quotation mark
    "\u00b7": "*",    # middle dot
}


def _p(text: str) -> str:
    """Sanitize text for fpdf2 Latin-1 core fonts."""
    for src, dst in _PDF_CHAR_MAP.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def to_pdf(minutes: "MinutesModel") -> bytes:
    """Generate a PDF from MinutesModel using fpdf2. Returns raw bytes."""
    from fpdf import FPDF

    class _PDF(FPDF):
        def header(self):
            pass  # custom header handled manually

        def footer(self):
            self.set_y(-14)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(100, 116, 139)
            self.cell(0, 8,
                _p(f"Process2Diagram  {_now()}  |  Pagina {self.page_no()}"),
                align="C")

    pdf = _PDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(left=20, top=20, right=20)
    pdf.add_page()

    W = pdf.w - 40  # usable width (margins 20 each side)

    def set_navy():   pdf.set_text_color(11, 30, 61)
    def set_accent(): pdf.set_text_color(46, 127, 217)
    def set_muted():  pdf.set_text_color(100, 116, 139)
    def set_white():  pdf.set_text_color(255, 255, 255)
    def set_body():   pdf.set_text_color(28, 42, 58)

    # ── Title block ───────────────────────────────────────────────────────────
    pdf.set_fill_color(11, 30, 61)
    pdf.rect(20, 20, W, 24, style="F")
    pdf.set_xy(20, 22)
    pdf.set_font("Helvetica", "B", 16)
    set_white()
    title_text = _p(minutes.title or "Ata de Reuniao")
    pdf.multi_cell(W, 8, title_text, align="C")

    # Metadata strip
    pdf.set_fill_color(238, 244, 252)
    meta_y = pdf.get_y()
    pdf.rect(20, meta_y, W, 8, style="F")
    pdf.set_xy(20, meta_y + 1)
    pdf.set_font("Helvetica", "", 9)
    set_muted()
    meta_parts = []
    if minutes.date:
        meta_parts.append(f"Data: {_p(minutes.date)}")
    if minutes.location:
        meta_parts.append(f"Local: {_p(minutes.location)}")
    meta_parts.append(f"Gerado em: {_now()}")
    pdf.cell(W, 6, "   |   ".join(meta_parts), align="C")
    pdf.ln(12)

    def section_header(title: str) -> None:
        pdf.set_fill_color(46, 127, 217)
        pdf.set_font("Helvetica", "B", 9)
        set_white()
        pdf.cell(W, 7, _p(f"  {title.upper()}"), fill=True, ln=True)
        pdf.ln(2)
        set_body()
        pdf.set_font("Helvetica", "", 10)

    def bullet(text: str) -> None:
        pdf.set_font("Helvetica", "", 10)
        set_body()
        pdf.set_x(24)
        pdf.cell(4, 5, "-")
        pdf.set_x(28)
        pdf.multi_cell(W - 8, 5, _p(text))

    def body_text(text: str) -> None:
        pdf.set_font("Helvetica", "", 10)
        set_body()
        pdf.multi_cell(W, 5, _p(text))
        pdf.ln(1)

    # ── Participants ──────────────────────────────────────────────────────────
    if minutes.participants:
        section_header(f"Participantes ({len(minutes.participants)})")
        # Two-column layout
        col_w = W / 2 - 4
        for i, p in enumerate(minutes.participants):
            if i % 2 == 0:
                x_start = 20
            else:
                x_start = 20 + col_w + 8
            pdf.set_x(x_start)
            pdf.set_font("Helvetica", "", 10)
            set_body()
            pdf.cell(col_w, 5, _p(f"*  {p[:55]}"))
            if i % 2 == 1 or i == len(minutes.participants) - 1:
                pdf.ln(5)
        pdf.ln(4)

    # ── Agenda ────────────────────────────────────────────────────────────────
    if minutes.agenda:
        section_header(f"Pauta ({len(minutes.agenda)} itens)")
        for i, item in enumerate(minutes.agenda, 1):
            pdf.set_font("Helvetica", "", 10)
            set_body()
            pdf.set_x(24)
            pdf.cell(6, 5, f"{i}.")
            pdf.set_x(30)
            pdf.multi_cell(W - 10, 5, _p(item))
        pdf.ln(4)

    # ── Summary ───────────────────────────────────────────────────────────────
    if minutes.summary:
        section_header("Resumo da Reuniao")
        for block in minutes.summary:
            topic   = block.get("topic", "")
            content = block.get("content", "")
            if topic:
                pdf.set_font("Helvetica", "B", 10)
                set_navy()
                pdf.multi_cell(W, 5, _p(topic))
                pdf.ln(1)
            if content:
                body_text(content)
        pdf.ln(2)

    # ── Decisions ─────────────────────────────────────────────────────────────
    if minutes.decisions:
        section_header(f"Decisoes Tomadas ({len(minutes.decisions)})")
        for d in minutes.decisions:
            bullet(d)
        pdf.ln(4)

    # ── Action Items table ────────────────────────────────────────────────────
    if minutes.action_items:
        section_header(f"Encaminhamentos / Action Items ({len(minutes.action_items)})")
        col_widths = [22, W - 22 - 38 - 24 - 22, 38, 24, 22]
        headers    = ["Prior.", "Tarefa", "Responsavel", "Prazo", "Por"]

        # Table header
        pdf.set_fill_color(11, 30, 61)
        pdf.set_font("Helvetica", "B", 9)
        set_white()
        for h, w in zip(headers, col_widths):
            pdf.cell(w, 7, f" {h}", fill=True, border=0)
        pdf.ln()

        prio_colors = {
            "high":        (201, 123, 26),
            "normal":      (46,  127, 217),
            "low":         (26,  127, 90),
            "unspecified": (100, 116, 139),
        }

        for i, ai in enumerate(minutes.action_items):
            fill = i % 2 == 0
            pdf.set_fill_color(248, 250, 252) if fill else pdf.set_fill_color(255, 255, 255)
            pdf.set_font("Helvetica", "", 9)
            r, g, b = prio_colors.get(ai.priority, (100, 116, 139))
            pdf.set_text_color(r, g, b)
            pdf.cell(col_widths[0], 6, _p(f" {_prio_label(ai.priority)}"), fill=fill, border=0)
            set_body()
            # Task may be long — truncate for table
            task = ai.task if len(ai.task) <= 60 else ai.task[:57] + "..."
            pdf.cell(col_widths[1], 6, _p(f" {task}"), fill=fill, border=0)
            pdf.cell(col_widths[2], 6, _p(f" {ai.responsible[:20]}"), fill=fill, border=0)
            pdf.cell(col_widths[3], 6, _p(f" {ai.deadline or '-'}"), fill=fill, border=0)
            pdf.cell(col_widths[4], 6, _p(f" {ai.raised_by or '-'}"), fill=fill, border=0)
            pdf.ln()

        # Bottom border
        pdf.set_draw_color(213, 227, 245)
        pdf.line(20, pdf.get_y(), 20 + W, pdf.get_y())
        pdf.ln(5)

    # ── Next meeting ──────────────────────────────────────────────────────────
    if minutes.next_meeting:
        section_header("Proxima Reuniao")
        pdf.set_font("Helvetica", "B", 11)
        set_navy()
        pdf.cell(W, 7, _p(minutes.next_meeting), ln=True)
        pdf.ln(3)

    return bytes(pdf.output())
