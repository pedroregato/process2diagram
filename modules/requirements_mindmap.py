# modules/requirements_mindmap.py
# ─────────────────────────────────────────────────────────────────────────────
# Pure-Python generator for a Mermaid mindmap from a RequirementsModel.
#
# Hierarchy:
#   root((Process Name))
#     Type group (Campo de Tela, Validação, …)
#       [priority icon] REQ-ID — Title (truncated)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re
from collections import defaultdict

_TYPE_LABELS = {
    "ui_field":       "Campo de Tela",
    "validation":     "Validacao",
    "business_rule":  "Regra de Negocio",
    "functional":     "Funcional",
    "non_functional": "Nao Funcional",
}

_PRIORITY_ICON = {
    "high":        "Alta",
    "medium":      "Media",
    "low":         "Baixa",
    "unspecified": "",
}


def _safe(text: str, max_len: int = 45) -> str:
    """Remove characters that break Mermaid mindmap node parsing."""
    # Strip problematic chars: parens, brackets, braces, quotes, colon
    text = re.sub(r'[(){}[\]"\'`:#]', "", text)
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def generate_requirements_mindmap(model) -> str:
    """
    Generate a Mermaid mindmap string from a RequirementsModel.

    Returns an empty string if there are no requirements.
    """
    if not model.requirements:
        return ""

    root_name = _safe(model.name or "Requisitos", 50)

    lines = ["mindmap"]
    lines.append(f"  root(({root_name}))")

    grouped: dict[str, list] = defaultdict(list)
    for r in model.requirements:
        grouped[r.type].append(r)

    for t_key, t_label in _TYPE_LABELS.items():
        items = grouped.get(t_key, [])
        if not items:
            continue

        safe_label = _safe(t_label)
        lines.append(f"    {safe_label}")

        for r in items:
            prio = _PRIORITY_ICON.get(r.priority, "")
            title = _safe(r.title, 40)
            prio_prefix = f"[{prio}] " if prio else ""
            node_text = _safe(f"{prio_prefix}{r.id} - {title}", 55)
            lines.append(f"      {node_text}")

    return "\n".join(lines)
