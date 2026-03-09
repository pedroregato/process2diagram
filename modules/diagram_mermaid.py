# modules/diagram_mermaid.py

import re
import unicodedata
from modules.schema import Process, Step

# Mermaid reserved words that cannot be used as node IDs
_RESERVED = {"END", "end", "START", "start", "STOP", "stop",
             "graph", "flowchart", "subgraph", "direction",
             "style", "classDef", "class", "click", "linkStyle"}


def _sanitize_label(text):
    """Sanitize text for use inside [ ] rectangle labels (quotes allowed)."""
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


def _sanitize_decision(text):
    """Sanitize text for use inside {{ }} decision labels (NO quotes allowed)."""
    return (
        text
        .replace('"', "")
        .replace("'", "")
        .replace("\n", " ")
        .replace("[", "(")
        .replace("]", ")")
        .replace("{", "(")
        .replace("}", ")")
        .strip()
    )


def _safe_id(actor):
    """Convert actor name to ASCII-only Mermaid subgraph ID."""
    normalized = unicodedata.normalize("NFD", actor)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^\w]", "_", ascii_only)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return "lane_" + slug if slug else "lane_misc"


def _safe_node_id(step_id):
    """Prefix reserved words so Mermaid doesn't choke on them."""
    if step_id in _RESERVED or step_id.upper() in _RESERVED:
        return "N_" + step_id
    return step_id


def _node(step):
    """Return Mermaid node definition line for a step."""
    nid = _safe_node_id(step.id)
    if step.is_decision:
        # {{ }} = hexagon/decision. NO quotes inside.
        label = _sanitize_decision(step.title)
        return '    ' + nid + '{{' + label + '}}'
    else:
        # [ ] = rectangle. Quotes allowed.
        label = _sanitize_label(step.title)
        return '    ' + nid + '["' + label + '"]'


def _collect_defined_ids(process):
    """Return set of all step IDs defined in the process."""
    return {_safe_node_id(s.id) for s in process.steps}


def _has_actors(process):
    return any(s.actor for s in process.steps)


def generate_mermaid(process):
    if _has_actors(process):
        return _generate_with_swimlanes(process)
    return _generate_plain(process)


# ── Plain flowchart ───────────────────────────────────────────────────────────

def _generate_plain(process):
    defined = _collect_defined_ids(process)
    lines = ["flowchart TD"]
    for step in process.steps:
        lines.append(_node(step))

    # Add any missing terminal nodes referenced in edges
    for edge in process.edges:
        tgt = _safe_node_id(edge.target)
        if tgt not in defined:
            lines.append('    ' + tgt + '([' + tgt + '])')
            defined.add(tgt)

    lines.append("")
    for edge in process.edges:
        src = _safe_node_id(edge.source)
        tgt = _safe_node_id(edge.target)
        if edge.label:
            lines.append("    " + src + " -->|" + _sanitize_label(edge.label) + "| " + tgt)
        else:
            lines.append("    " + src + " --> " + tgt)
    return "\n".join(lines)


# ── Swimlane flowchart ────────────────────────────────────────────────────────

def _generate_with_swimlanes(process):
    defined = _collect_defined_ids(process)

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
        display = _sanitize_label(actor)
        lines.append('    subgraph ' + safe_id + '["' + display + '"]')
        lines.append("    direction TB")
        for step in lanes[actor]:
            lines.append("  " + _node(step))
        lines.append("    end")
        lines.append("")

    # Add missing terminal nodes OUTSIDE subgraphs
    for edge in process.edges:
        tgt = _safe_node_id(edge.target)
        if tgt not in defined:
            lines.append('    ' + tgt + '([' + tgt + '])')
            defined.add(tgt)

    lines.append("")

    for edge in process.edges:
        src = _safe_node_id(edge.source)
        tgt = _safe_node_id(edge.target)
        if edge.label:
            lines.append("    " + src + " -->|" + _sanitize_label(edge.label) + "| " + tgt)
        else:
            lines.append("    " + src + " --> " + tgt)

    colors = ["#EFF6FF", "#F0FDF4", "#FFF7ED", "#FAF5FF",
              "#FFF1F2", "#F0F9FF", "#FEFCE8", "#F7F7F7"]
    lines.append("")
    for i, actor in enumerate(actors_seen):
        safe_id = _safe_id(actor)
        lines.append(
            "    style " + safe_id +
            " fill:" + colors[i % len(colors)] +
            ",stroke:#CBD5E1,stroke-width:1px,color:#1e293b"
        )

    return "\n".join(lines)
    
