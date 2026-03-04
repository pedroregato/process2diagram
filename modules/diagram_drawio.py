# modules/diagram_drawio.py

import xml.etree.ElementTree as ET
from modules.schema import Process


_NODE_W = 160
_NODE_H = 60
_DECISION_W = 120
_DECISION_H = 80
_H_GAP = 80
_START_X = 100
_START_Y = 40


def generate_drawio(process: Process) -> str:
    root = ET.Element("mxGraphModel")
    root.set("dx", "1422")
    root.set("dy", "762")
    root.set("grid", "1")
    root.set("gridSize", "10")
    root.set("guides", "1")
    root.set("tooltips", "1")
    root.set("connect", "1")
    root.set("arrows", "1")
    root.set("fold", "1")
    root.set("page", "1")
    root.set("pageScale", "1")
    root.set("pageWidth", "1169")
    root.set("pageHeight", "827")

    parent = ET.SubElement(root, "root")
    ET.SubElement(parent, "mxCell", id="0")
    ET.SubElement(parent, "mxCell", id="1", parent="0")

    positions = {}
    y = _START_Y

    for i, step in enumerate(process.steps):
        w = _DECISION_W if step.is_decision else _NODE_W
        h = _DECISION_H if step.is_decision else _NODE_H
        x = _START_X
        positions[step.id] = (x, y, w, h)

        cell = ET.SubElement(parent, "mxCell")
        cell.set("id", step.id)
        label = step.title
        if step.actor:
            label = f"[{step.actor}]\n{step.title}"
        cell.set("value", label)
        cell.set("vertex", "1")
        cell.set("parent", "1")

        if step.is_decision:
            cell.set("style", "rhombus;whiteSpace=wrap;html=1;fillColor=#fff2cc;strokeColor=#d6b656;")
        else:
            cell.set("style", "rounded=1;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;")

        geo = ET.SubElement(cell, "mxGeometry")
        geo.set("x", str(x))
        geo.set("y", str(y))
        geo.set("width", str(w))
        geo.set("height", str(h))
        geo.set("as", "geometry")

        y += h + _H_GAP

    # Edges
    for i, edge in enumerate(process.edges):
        cell = ET.SubElement(parent, "mxCell")
        cell.set("id", f"E{i:03d}")
        cell.set("value", edge.label)
        cell.set("edge", "1")
        cell.set("source", edge.source)
        cell.set("target", edge.target)
        cell.set("parent", "1")
        cell.set("style", "rounded=1;orthogonalLoop=1;jettySize=auto;exitX=0.5;exitY=1;exitDx=0;exitDy=0;")
        geo = ET.SubElement(cell, "mxGeometry")
        geo.set("relative", "1")
        geo.set("as", "geometry")

    return ET.tostring(root, encoding="unicode", xml_declaration=False)
