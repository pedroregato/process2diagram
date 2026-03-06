# modules/diagram_mermaid.py

import re
import unicodedata
from modules.schema import Process, Step


def _sanitize(text):
    """Escape characters that break Mermaid labels."""
    return (
        text
        .replace('"', "'")
        .replace("\n", " ")
        .replace("[", "(")
        .replace("]", ")")
        .replace("{", "(")
        .replace("}", ")")
        .strip()
    )


def _safe_id(actor):
    """
    Convert actor name to a valid Mermaid subgraph ID (ASCII only).
    Mermaid 10.x rejects non-ASCII characters in subgraph IDs.
    """
    normalized = unicodedata.normalize("NFD", actor)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^\w]", "_", ascii_only)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return "lane_" + slug if slug else "lane_misc"


def _node(step):
    label = _sanitize(step.title)
    if step.is_decision:
        return '    ' + step.id + '{{ "' + label + '" }}'
    else:
        return '    ' + step.id + '["' + label + '"]'


def _has_actors(process):
    return any(s.actor for s in process.steps)


def generate_mermaid(process):
    if _has_actors(process):
        return _generate_with_swimlanes(process)
    return _generate_plain(process)


def _generate_plain(process):
    lines = ["flowchart TD"]
    for step in process.steps:
        lines.append(_node(step))
    lines.append("")
    for edge in process.edges:
        if edge.label:
            lines.append("    " + edge.source + " -->|" + _sanitize(edge.label) + "| " + edge.target)
        else:
            lines.append("    " + edge.source + " --> " + edge.target)
    return "\n".join(lines)


def _generate_with_swimlanes(process):
    actors_seen = []
    for step in process.steps:
        actor = step.actor or "Unassigned"
        if actor not in actors_seen:
            actors_seen.append(actor)

    lanes = {a: [] for a in actors_seen}
    for step in process.steps:
        actor = step.actor or "Unassigned"
        lanes[actor].append(step)

    lines = ["flowchart TD", ""]

    for actor in actors_seen:
        safe_id = _safe_id(actor)
        display = _sanitize(actor)
        lines.append('    subgraph ' + safe_id + '["' + display + '"]')
        lines.append("    direction TB")
        for step in lanes[actor]:
            lines.append("  " + _node(step))
        lines.append("    end")
        lines.append("")

    for edge in process.edges:
        if edge.label:
            lines.append("    " + edge.source + " -->|" + _sanitize(edge.label) + "| " + edge.target)
        else:
            lines.append("    " + edge.source + " --> " + edge.target)

    lane_colors = [
        "#EFF6FF", "#F0FDF4", "#FFF7ED", "#FAF5FF",
        "#FFF1F2", "#F0F9FF", "#FEFCE8", "#F7F7F7",
    ]
    lines.append("")
    for i, actor in enumerate(actors_seen):
        safe_id = _safe_id(actor)
        color = lane_colors[i % len(lane_colors)]
        lines.append(
            "    style " + safe_id +
            " fill:" + color + ",stroke:#CBD5E1,stroke-width:1px,color:#1e293b"
        )

    return "\n".join(lines)
