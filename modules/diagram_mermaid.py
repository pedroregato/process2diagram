# modules/diagram_mermaid.py
# ─────────────────────────────────────────────────────────────────────────────
# Generates Mermaid flowchart code from a Process object.
#
# Two modes:
#   - With actors  → swimlane layout using Mermaid subgraphs (one per actor)
#   - Without actors → plain top-down flowchart (original behavior)
#
# Swimlane strategy:
#   Mermaid doesn't have native swimlanes, but subgraphs styled with
#   direction LR inside a TD flowchart produce a readable lane effect.
#   Each actor gets a subgraph; unassigned steps go to a "General" lane.
# ─────────────────────────────────────────────────────────────────────────────

from modules.schema import Process, Step


def _sanitize(text: str) -> str:
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


def _node(step: Step) -> str:
    """Returns the Mermaid node definition line for a step."""
    label = _sanitize(step.title)
    if step.is_decision:
        return f'    {step.id}{{{{ "{label}" }}}}'
    else:
        return f'    {step.id}["{label}"]'


def _has_actors(process: Process) -> bool:
    return any(s.actor for s in process.steps)


def generate_mermaid(process: Process) -> str:
    """
    Generates Mermaid flowchart code.
    Uses swimlanes (subgraphs) when actor information is present.
    """
    if _has_actors(process):
        return _generate_with_swimlanes(process)
    else:
        return _generate_plain(process)


# ── Plain flowchart (no actors) ───────────────────────────────────────────────

def _generate_plain(process: Process) -> str:
    lines = ["flowchart TD"]

    for step in process.steps:
        lines.append(_node(step))

    lines.append("")

    for edge in process.edges:
        if edge.label:
            lines.append(f"    {edge.source} -->|{_sanitize(edge.label)}| {edge.target}")
        else:
            lines.append(f"    {edge.source} --> {edge.target}")

    return "\n".join(lines)


# ── Swimlane flowchart (with actors) ─────────────────────────────────────────

def _generate_with_swimlanes(process: Process) -> str:
    """
    Groups steps by actor into Mermaid subgraphs.
    Edges are declared at the top level (outside subgraphs) so cross-lane
    connections render correctly.

    Actor names are normalized to safe subgraph IDs.
    """
    # Collect ordered unique actors (preserve appearance order)
    actors_seen: list[str] = []
    for step in process.steps:
        actor = step.actor or "_unassigned"
        if actor not in actors_seen:
            actors_seen.append(actor)

    # Group step IDs by actor
    lanes: dict[str, list[Step]] = {a: [] for a in actors_seen}
    for step in process.steps:
        actor = step.actor or "_unassigned"
        lanes[actor].append(step)

    lines = ["flowchart TD"]
    lines.append("")

    # ── Subgraph per actor ────────────────────────────────────────────────────
    for actor in actors_seen:
        steps_in_lane = lanes[actor]

        # Safe subgraph ID: no spaces or special chars
        safe_id = "lane_" + actor.replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "")
        # Display label: use original actor name, or "Unassigned" for fallback
        display = actor if actor != "_unassigned" else "Unassigned"

        lines.append(f'    subgraph {safe_id}["{_sanitize(display)}"]')
        lines.append(f'    direction TB')
        for step in steps_in_lane:
            lines.append("  " + _node(step))
        lines.append("    end")
        lines.append("")

    # ── Edges (declared outside subgraphs for cross-lane connections) ─────────
    for edge in process.edges:
        if edge.label:
            lines.append(f"    {edge.source} -->|{_sanitize(edge.label)}| {edge.target}")
        else:
            lines.append(f"    {edge.source} --> {edge.target}")

    # ── Styling: alternate lane background colors ─────────────────────────────
    lane_colors = [
        "#EFF6FF",  # blue-50
        "#F0FDF4",  # green-50
        "#FFF7ED",  # orange-50
        "#FAF5FF",  # purple-50
        "#FFF1F2",  # rose-50
        "#F0F9FF",  # sky-50
        "#FEFCE8",  # yellow-50
        "#F7F7F7",  # neutral
    ]
    lines.append("")
    for i, actor in enumerate(actors_seen):
        safe_id = "lane_" + actor.replace(" ", "_").replace("-", "_").replace("/", "_").replace(".", "")
        color = lane_colors[i % len(lane_colors)]
        lines.append(f"    style {safe_id} fill:{color},stroke:#CBD5E1,stroke-width:1px,color:#1e293b")

    return "\n".join(lines)
