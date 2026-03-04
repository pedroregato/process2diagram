from __future__ import annotations
from xml.sax.saxutils import escape
from .schema import ProcessModel

def to_drawio_xml(proc: ProcessModel) -> str:
    """
    Gera um diagrama draw.io básico com layout em coluna.
    (draw.io usa mxGraphModel dentro de <diagram>.)
    """
    # Layout simples: caixas empilhadas
    x, y = 120, 80
    w, h = 260, 70
    gap = 40

    # IDs numéricos para mxCells
    base_id = 2
    node_ids = {}

    cells = []
    # root / layer
    cells.append('<mxCell id="0"/>')
    cells.append('<mxCell id="1" parent="0"/>')

    # nodes
    cur_y = y
    for idx, s in enumerate(proc.steps):
        cid = str(base_id + idx)
        node_ids[s.id] = cid
        value = escape(s.title)
        style = "rounded=1;whiteSpace=wrap;html=1;"
        cells.append(
            f'<mxCell id="{cid}" value="{value}" style="{style}" vertex="1" parent="1">'
            f'<mxGeometry x="{x}" y="{cur_y}" width="{w}" height="{h}" as="geometry"/>'
            f"</mxCell>"
        )
        cur_y += h + gap

    # edges
    edge_base = base_id + len(proc.steps)
    for i, e in enumerate(proc.edges):
        eid = str(edge_base + i)
        src = node_ids.get(e.source)
        tgt = node_ids.get(e.target)
        if not src or not tgt:
            continue
        style = "endArrow=block;html=1;rounded=0;"
        label = escape(e.label) if e.label else ""
        cells.append(
            f'<mxCell id="{eid}" value="{label}" style="{style}" edge="1" parent="1" source="{src}" target="{tgt}">'
            f'<mxGeometry relative="1" as="geometry"/>'
            f"</mxCell>"
        )

    mxgraph = (
        '<mxGraphModel dx="1200" dy="800" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" page="1" pageScale="1" pageWidth="1100" pageHeight="850" math="0" shadow="0">'
        "<root>"
        + "".join(cells) +
        "</root>"
        "</mxGraphModel>"
    )

    xml = f'''<mxfile host="app.diagrams.net" modified="1" agent="process2diagram" version="22.1.0" type="device">
  <diagram name="{escape(proc.name)}">{escape(mxgraph)}</diagram>
</mxfile>'''
    return xml
