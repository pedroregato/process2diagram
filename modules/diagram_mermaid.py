from __future__ import annotations
from .schema import ProcessModel

def to_mermaid_flowchart(proc: ProcessModel) -> str:
    # Flowchart TB (top-bottom)
    lines = ["flowchart TB"]
    for s in proc.steps:
        label = s.title.replace('"', "'")
        lines.append(f'  {s.id}["{label}"]')

    for e in proc.edges:
        if e.label:
            lines.append(f"  {e.source} -->|{e.label}| {e.target}")
        else:
            lines.append(f"  {e.source} --> {e.target}")

    return "\n".join(lines)
