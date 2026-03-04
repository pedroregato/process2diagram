# modules/diagram_mermaid.py

from modules.schema import Process


def _sanitize(text: str) -> str:
    """Escape characters that break Mermaid labels."""
    return text.replace('"', "'").replace("\n", " ").replace("[", "(").replace("]", ")")


def generate_mermaid(process: Process) -> str:
    lines = ["flowchart TD"]

    for step in process.steps:
        label = _sanitize(step.title)
        actor_prefix = f"{step.actor}: " if step.actor else ""
        full_label = f"{actor_prefix}{label}"

        if step.is_decision:
            lines.append(f'    {step.id}{{{{"  {full_label}  "}}}}')
        else:
            lines.append(f'    {step.id}["{full_label}"]')

    lines.append("")

    for edge in process.edges:
        label_part = f'|"{_sanitize(edge.label)}"|' if edge.label else "-->"
        if edge.label:
            lines.append(f"    {edge.source} -->|{_sanitize(edge.label)}| {edge.target}")
        else:
            lines.append(f"    {edge.source} --> {edge.target}")

    return "\n".join(lines)
