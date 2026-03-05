# modules/diagram_mermaid.py
from modules.schema import Process


def _sanitize(text: str) -> str:
    """Escape characters that break Mermaid labels."""
    return text.replace('"', "'").replace("\n", " ").replace("[", "(").replace("]", ")")


def generate_mermaid(process: Process) -> str:
    lines = ["flowchart TD"]

    for step in process.steps:
        label = _sanitize(step.title)  # actor prefix removed — title only
        if step.is_decision:
            lines.append(f'    {step.id}{{{{  "{label}"  }}}}')
        else:
            lines.append(f'    {step.id}["{label}"]')

    lines.append("")

    for edge in process.edges:
        if edge.label:
            lines.append(f"    {edge.source} -->|{_sanitize(edge.label)}| {edge.target}")
        else:
            lines.append(f"    {edge.source} --> {edge.target}")

    return "\n".join(lines)
