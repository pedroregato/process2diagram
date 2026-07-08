# modules/ata_template_engine.py
# ─────────────────────────────────────────────────────────────────────────────
# Extração de modelo (template) de ata a partir de um .docx de referência, e
# aplicação desse modelo na geração de uma ata via modules/minutes_exporter.py.
#
# PC160 (melhorias/templates-ata-por-contexto.md) — Fase 1: modelo declarativo.
# Não é um BaseAgent (sem chamada de LLM) — pura lógica Python determinística,
# mesmo espírito de agent_mermaid.py/agent_validator.py.
#
# Public API:
#   extract_template_from_docx(docx_bytes) -> (template_markdown, style_spec, assets)
#   apply_template_to_docx(minutes, style_spec, assets) -> bytes
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from io import BytesIO
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.knowledge_hub import MinutesModel

# Estilos de heading em Word — nomes variam por idioma/template (EN "Heading N",
# PT-BR "Título N"). Mapeamos ambos para o mesmo nível markdown.
_HEADING_STYLE_LEVELS = {
    "heading 1": 1, "título 1": 1, "titulo 1": 1,
    "heading 2": 2, "título 2": 2, "titulo 2": 2,
    "heading 3": 3, "título 3": 3, "titulo 3": 3,
    "heading 4": 4, "título 4": 4, "titulo 4": 4,
}


def _heading_level(paragraph) -> int | None:
    style_name = (paragraph.style.name or "").strip().lower()
    return _HEADING_STYLE_LEVELS.get(style_name)


def _dominant_heading_color(doc) -> str | None:
    """
    Best-effort accent color: the most common explicit RGB color set on a
    run within a heading paragraph. Returns a '#RRGGBB' string, or None if
    no heading run has an explicit color (falls back to the app default).
    """
    from collections import Counter

    counts: Counter[str] = Counter()
    for p in doc.paragraphs:
        if _heading_level(p) is None:
            continue
        for run in p.runs:
            color = getattr(run.font, "color", None)
            rgb = getattr(color, "rgb", None) if color else None
            if rgb:
                counts[str(rgb)] += 1
    if not counts:
        return None
    return "#" + counts.most_common(1)[0][0]


def _extract_images_from_part(part, origin: str) -> list[dict]:
    """Pull every image relationship out of a document/header/footer part."""
    from docx.opc.constants import RELATIONSHIP_TYPE as RT

    assets: list[dict] = []
    try:
        rels = part.rels
    except Exception:
        return assets

    for rel in rels.values():
        if rel.reltype != RT.IMAGE or rel.is_external:
            continue
        try:
            image_part = rel.target_part
            blob = image_part.blob
            content_type = image_part.content_type or "image/png"
            try:
                width_px, height_px = image_part.image.size
            except Exception:
                width_px = height_px = None
        except Exception:
            continue

        asset_type = "logo" if origin == "header" else (
            "footer_image" if origin == "footer" else "other"
        )
        assets.append({
            "asset_type": asset_type,
            "origin": origin,
            "image_bytes": blob,
            "mime_type": content_type,
            "width_px": width_px,
            "height_px": height_px,
        })
    return assets


def _extract_page_background(doc) -> dict | None:
    """
    Best-effort extraction of a legacy VML page background (w:background in
    document.xml, referencing a v:background picture fill via r:id). This is
    an old Word feature with no high-level python-docx API — if the document
    doesn't use it, or the XML shape doesn't match what we expect, this
    silently returns None rather than failing the whole extraction.
    """
    try:
        ns = {
            "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
            "v": "urn:schemas-microsoft-com:vml",
            "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
        }
        root = doc.element
        bg = root.find(".//w:background", ns)
        if bg is None:
            return None
        fill = bg.find(".//v:fill", ns) if bg is not None else None
        if fill is None:
            return None
        r_id = fill.get(f"{{{ns['r']}}}id")
        if not r_id:
            return None
        part = doc.part.related_parts.get(r_id)
        if part is None:
            return None
        blob = part.blob
        content_type = getattr(part, "content_type", "image/png")
        return {
            "asset_type": "background",
            "origin": "page_background",
            "image_bytes": blob,
            "mime_type": content_type,
            "width_px": None,
            "height_px": None,
        }
    except Exception:
        return None


def extract_template_from_docx(docx_bytes: bytes) -> tuple[str, dict, list[dict]]:
    """
    Parse a reference .docx and derive:
      - template_markdown: a heading skeleton mirroring the document's own
        section names/order ('# Título', '## Subtítulo', ...).
      - style_spec: {"accent_color": "#RRGGBB" | None}.
      - assets: list of {asset_type, origin, image_bytes, mime_type,
        width_px, height_px} — every image found in header/footer/body,
        plus a best-effort page background.

    Never raises for a well-formed .docx; malformed input propagates as a
    python-docx exception for the caller to surface to the user.
    """
    from docx import Document

    doc = Document(BytesIO(docx_bytes))

    # ── Markdown skeleton from heading paragraphs ──────────────────────────
    lines: list[str] = []
    for p in doc.paragraphs:
        level = _heading_level(p)
        if level is None:
            continue
        text = p.text.strip()
        if text:
            lines.append("#" * level + " " + text)
    template_markdown = "\n\n".join(lines)

    # ── Style spec ───────────────────────────────────────────────────────
    style_spec = {"accent_color": _dominant_heading_color(doc)}

    # ── Assets: header/footer (per section) + body + page background ──────
    assets: list[dict] = []
    seen_blobs: set[bytes] = set()

    for section in doc.sections:
        for part, origin in (
            (section.header.part, "header"),
            (section.footer.part, "footer"),
        ):
            for asset in _extract_images_from_part(part, origin):
                if asset["image_bytes"] in seen_blobs:
                    continue
                seen_blobs.add(asset["image_bytes"])
                assets.append(asset)

    for asset in _extract_images_from_part(doc.part, "body"):
        if asset["image_bytes"] in seen_blobs:
            continue
        seen_blobs.add(asset["image_bytes"])
        assets.append(asset)

    bg_asset = _extract_page_background(doc)
    if bg_asset and bg_asset["image_bytes"] not in seen_blobs:
        assets.append(bg_asset)

    return template_markdown, style_spec, assets


def apply_template_to_docx(
    minutes: "MinutesModel",
    style_spec: dict | None = None,
    assets: list[dict] | None = None,
) -> bytes:
    """
    Thin wrapper over modules.minutes_exporter.to_docx() that forwards a
    template spec built from extract_template_from_docx() (or loaded back
    from the ata_templates/ata_template_assets tables). Kept as a separate
    function (rather than requiring every caller to import to_docx directly)
    so the template-resolution/application concern stays in one module.
    """
    from modules.minutes_exporter import to_docx

    template_spec = None
    if style_spec or assets:
        template_spec = {
            "accent_color": (style_spec or {}).get("accent_color"),
            "assets": assets or [],
        }
    return to_docx(minutes, template_spec=template_spec)
