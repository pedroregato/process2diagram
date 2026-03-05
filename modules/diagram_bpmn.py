# modules/diagram_bpmn.py
# ─────────────────────────────────────────────────────────────────────────────
# Generates:
#   1. generate_bpmn_xml(process)  → valid BPMN 2.0 XML string (.bpmn file)
#   2. generate_bpmn_preview(xml)  → self-contained HTML with bpmn-js viewer
#
# The XML is consumable by Camunda Modeler, bpmn-js, Bizagi and any
# BPMN 2.0 compliant tool.
#
# Layout strategy: vertical top-down, lanes stacked horizontally.
# Each lane gets its own column; elements are distributed evenly in Y.
# ─────────────────────────────────────────────────────────────────────────────

import xml.etree.ElementTree as ET
from typing import Optional
from modules.schema import BpmnProcess, BpmnElement, BpmnLane, BpmnPool, SequenceFlow


# ── Layout constants ──────────────────────────────────────────────────────────

_TASK_W = 120
_TASK_H = 60
_EVENT_R = 36          # diameter
_GW_SIZE = 50          # diamond width = height
_SUB_W = 160
_SUB_H = 100

_COL_W = 200           # horizontal space per lane column
_ROW_H = 100           # vertical gap between rows
_MARGIN_X = 80         # left margin inside lane
_MARGIN_Y = 60         # top margin
_POOL_HEADER_W = 30    # width of pool label bar
_LANE_HEADER_H = 30    # height of lane label bar (horizontal layout)


# ── BPMN XML namespaces ───────────────────────────────────────────────────────

_NS = {
    "bpmn":  "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmndi":"http://www.omg.org/spec/BPMN/20100524/DI",
    "dc":    "http://www.omg.org/spec/DD/20100524/DC",
    "di":    "http://www.omg.org/spec/DD/20100524/DI",
    "xsi":   "http://www.w3.org/2001/XMLSchema-instance",
}

for prefix, uri in _NS.items():
    ET.register_namespace(prefix, uri)

_BPMN  = _NS["bpmn"]
_DI    = _NS["bpmndi"]
_DC    = _NS["dc"]
_DIDC  = _NS["di"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tag(ns: str, local: str) -> str:
    return f"{{{ns}}}{local}"


def _sub(parent, ns: str, local: str, **attrs) -> ET.Element:
    el = ET.SubElement(parent, _tag(ns, local))
    for k, v in attrs.items():
        el.set(k.replace("_", ":").replace("__", ":"), str(v))
    return el


def _bounds(parent, x: float, y: float, w: float, h: float) -> ET.Element:
    b = ET.SubElement(parent, _tag(_DC, "Bounds"))
    b.set("x", str(round(x)))
    b.set("y", str(round(y)))
    b.set("width", str(round(w)))
    b.set("height", str(round(h)))
    return b


def _waypoint(parent, x: float, y: float) -> ET.Element:
    wp = ET.SubElement(parent, _tag(_DIDC, "waypoint"))
    wp.set("x", str(round(x)))
    wp.set("y", str(round(y)))
    return wp


# ── Event definition tag mapping ─────────────────────────────────────────────

_EVENT_DEF_TAG: dict[str, str] = {
    "message":      "messageEventDefinition",
    "timer":        "timerEventDefinition",
    "error":        "errorEventDefinition",
    "escalation":   "escalationEventDefinition",
    "cancel":       "cancelEventDefinition",
    "compensation": "compensateEventDefinition",
    "signal":       "signalEventDefinition",
    "terminate":    "terminateEventDefinition",
    "conditional":  "conditionalEventDefinition",
    "link":         "linkEventDefinition",
}

# bpmn-js shape style overrides for event types
_EVENT_SHAPE_STYLE: dict[str, str] = {
    "startEvent":              "shape=mxgraph.bpmn.shape;perimeter=mxgraph.bpmn.perimeter.event_perimeter;symbol=general;isLooping=0;isSequential=0;isCompensation=0;",
    "endEvent":                "shape=mxgraph.bpmn.shape;perimeter=mxgraph.bpmn.perimeter.event_perimeter;symbol=terminate;strokeWidth=3;",
    "intermediateThrowEvent":  "shape=mxgraph.bpmn.shape;perimeter=mxgraph.bpmn.perimeter.event_perimeter;symbol=general;strokeWidth=1.5;",
    "intermediateCatchEvent":  "shape=mxgraph.bpmn.shape;perimeter=mxgraph.bpmn.perimeter.event_perimeter;symbol=general;strokeWidth=1.5;",
    "boundaryEvent":           "shape=mxgraph.bpmn.shape;perimeter=mxgraph.bpmn.perimeter.event_perimeter;symbol=general;strokeWidth=1.5;",
    "exclusiveGateway":        "rhombus;",
    "parallelGateway":         "rhombus;",
    "inclusiveGateway":        "rhombus;",
    "eventBasedGateway":       "rhombus;",
    "complexGateway":          "rhombus;",
    "subProcess":              "rounded=1;arcSize=10;",
    "adHocSubProcess":         "rounded=1;arcSize=10;",
    "callActivity":            "rounded=1;arcSize=10;strokeWidth=4;",
    "dataObject":              "shape=mxgraph.bpmn.shape;symbol=dataObject;",
    "dataStore":               "shape=mxgraph.bpmn.shape;symbol=dataStore;",
}


# ── Layout engine ─────────────────────────────────────────────────────────────

def _compute_layout(process: BpmnProcess) -> dict[str, tuple[float, float, float, float]]:
    """
    Returns {element_id: (x, y, w, h)} for every element.

    Strategy:
      - If pools/lanes exist: each lane is a horizontal band.
        Elements in each lane are distributed left-to-right in order.
      - If no lanes: single-column vertical layout.
    """
    positions: dict[str, tuple[float, float, float, float]] = {}
    lanes_flat = process.lanes_flat()

    def _size(el: BpmnElement) -> tuple[float, float]:
        if el.type in ("startEvent", "endEvent",
                       "intermediateThrowEvent", "intermediateCatchEvent",
                       "boundaryEvent"):
            return _EVENT_R, _EVENT_R
        if "Gateway" in el.type:
            return _GW_SIZE, _GW_SIZE
        if el.type in ("subProcess", "adHocSubProcess"):
            return _SUB_W, _SUB_H
        return _TASK_W, _TASK_H

    if lanes_flat:
        # Horizontal-band layout: lanes stacked top-to-bottom
        lane_h = 140
        x_start = _POOL_HEADER_W + _MARGIN_X

        # Assign elements to lanes
        lane_elements: dict[str, list[BpmnElement]] = {}
        for lane in lanes_flat:
            lane_elements[lane.id] = [
                process.get_element(eid)
                for eid in lane.element_ids
                if process.get_element(eid) is not None
            ]

        # Elements not in any lane → append to a virtual "unassigned" lane
        assigned = {eid for lane in lanes_flat for eid in lane.element_ids}
        unassigned = [e for e in process.elements
                      if e.id not in assigned and e.type != "boundaryEvent"]
        if unassigned:
            # Create virtual last lane
            virtual = BpmnLane(id="_unassigned", name="")
            lane_elements["_unassigned"] = unassigned
            lanes_flat.append(virtual)

        y_offset = _LANE_HEADER_H
        for lane in lanes_flat:
            els = lane_elements.get(lane.id, [])
            x = x_start
            for el in els:
                w, h = _size(el)
                cy = y_offset + (lane_h - h) / 2
                positions[el.id] = (x, cy, w, h)
                x += w + 60
            y_offset += lane_h

        # Boundary events: snap to bottom-right of host
        for el in process.boundary_events():
            if el.attached_to and el.attached_to in positions:
                hx, hy, hw, hh = positions[el.attached_to]
                w, h = _size(el)
                positions[el.id] = (hx + hw - w / 2, hy + hh - h / 2, w, h)

    else:
        # Single-column vertical layout
        x = _MARGIN_X + 60
        y = _MARGIN_Y
        for el in process.elements:
            if el.type == "boundaryEvent":
                continue  # placed after their host
            w, h = _size(el)
            positions[el.id] = (x, y, w, h)
            y += h + _ROW_H

        for el in process.boundary_events():
            if el.attached_to and el.attached_to in positions:
                hx, hy, hw, hh = positions[el.attached_to]
                w, h = _size(el)
                positions[el.id] = (hx + hw - w / 2, hy + hh - h / 2, w, h)

    return positions


def _compute_pool_bounds(
    process: BpmnProcess,
    positions: dict[str, tuple[float, float, float, float]],
) -> tuple[float, float, float, float]:
    """Returns (x, y, total_w, total_h) for the enclosing pool rectangle."""
    if not positions:
        return (0, 0, 600, 400)
    xs = [v[0] for v in positions.values()]
    ys = [v[1] for v in positions.values()]
    x2s = [v[0] + v[2] for v in positions.values()]
    y2s = [v[1] + v[3] for v in positions.values()]
    pad = 40
    x = min(xs) - pad
    y = min(ys) - pad
    w = max(x2s) - x + pad
    h = max(y2s) - y + pad
    return (x, y, w, h)


# ── XML builder ───────────────────────────────────────────────────────────────

def _build_element_xml(
    parent: ET.Element,
    el: BpmnElement,
    process_id: str,
) -> None:
    """Appends the semantic BPMN XML for one element."""
    tag = _tag(_BPMN, el.type)
    node = ET.SubElement(parent, tag)
    node.set("id", el.id)
    node.set("name", el.name)

    if el.type == "boundaryEvent" and el.attached_to:
        node.set("attachedToRef", el.attached_to)
        node.set("cancelActivity", "true" if el.is_interrupting else "false")

    if el.is_loop:
        li = ET.SubElement(node, _tag(_BPMN, "standardLoopCharacteristics"))
        li.set("id", f"{el.id}_loop")

    if el.is_parallel_multi:
        mi = ET.SubElement(node, _tag(_BPMN, "multiInstanceLoopCharacteristics"))
        mi.set("id", f"{el.id}_mi")
        mi.set("isSequential", "false")

    if el.is_sequential_multi:
        mi = ET.SubElement(node, _tag(_BPMN, "multiInstanceLoopCharacteristics"))
        mi.set("id", f"{el.id}_mi")
        mi.set("isSequential", "true")

    if el.documentation:
        doc = ET.SubElement(node, _tag(_BPMN, "documentation"))
        doc.text = el.documentation

    # Event definition
    if el.event_type != "none":
        def_tag = _EVENT_DEF_TAG.get(el.event_type)
        if def_tag:
            edef = ET.SubElement(node, _tag(_BPMN, def_tag))
            edef.set("id", f"{el.id}_def")

    # Sub-process children (recursive)
    if el.type in ("subProcess", "adHocSubProcess"):
        for child in el.children:
            _build_element_xml(node, child, process_id)

    if el.called_element:
        node.set("calledElement", el.called_element)


def generate_bpmn_xml(process: BpmnProcess) -> str:
    """
    Generates a complete, valid BPMN 2.0 XML document.
    Returns a UTF-8 string.
    """
    positions = _compute_layout(process)

    # ── Root: definitions ─────────────────────────────────────────────────────
    definitions = ET.Element(_tag(_BPMN, "definitions"))
    definitions.set("xmlns:bpmn",   _BPMN)
    definitions.set("xmlns:bpmndi", _DI)
    definitions.set("xmlns:dc",     _DC)
    definitions.set("xmlns:di",     _DIDC)
    definitions.set("xmlns:xsi",    _NS["xsi"])
    definitions.set("id", "Definitions_1")
    definitions.set("targetNamespace", "http://bpmn.io/schema/bpmn")
    definitions.set("exporter", "Process2Diagram")
    definitions.set("exporterVersion", "2.0")

    # ── Collaboration (pools) ─────────────────────────────────────────────────
    collab_el = None
    if process.pools:
        collab_el = ET.SubElement(definitions, _tag(_BPMN, "collaboration"))
        collab_el.set("id", "collaboration_1")
        for pool in process.pools:
            p_node = ET.SubElement(collab_el, _tag(_BPMN, "participant"))
            p_node.set("id", pool.id)
            p_node.set("name", pool.name)
            p_node.set("processRef", process.process_id)

    # ── Process ───────────────────────────────────────────────────────────────
    proc_el = ET.SubElement(definitions, _tag(_BPMN, "process"))
    proc_el.set("id", process.process_id)
    proc_el.set("name", process.name)
    proc_el.set("isExecutable", "true" if process.is_executable else "false")

    if process.documentation:
        doc = ET.SubElement(proc_el, _tag(_BPMN, "documentation"))
        doc.text = process.documentation

    # Lanes inside process
    if process.pools:
        for pool in process.pools:
            if pool.lanes:
                lset = ET.SubElement(proc_el, _tag(_BPMN, "laneSet"))
                lset.set("id", f"{pool.id}_laneSet")
                for lane in pool.lanes:
                    lane_el = ET.SubElement(lset, _tag(_BPMN, "lane"))
                    lane_el.set("id", lane.id)
                    lane_el.set("name", lane.name)
                    for eid in lane.element_ids:
                        ref = ET.SubElement(lane_el, _tag(_BPMN, "flowNodeRef"))
                        ref.text = eid

    # Elements (top-level, non-boundary first, then boundary)
    non_boundary = [e for e in process.elements if e.type != "boundaryEvent"]
    boundary     = [e for e in process.elements if e.type == "boundaryEvent"]
    for el in non_boundary + boundary:
        _build_element_xml(proc_el, el, process.process_id)

    # Sequence flows
    for flow in process.flows:
        sf = ET.SubElement(proc_el, _tag(_BPMN, "sequenceFlow"))
        sf.set("id", flow.id)
        sf.set("name", flow.name)
        sf.set("sourceRef", flow.source)
        sf.set("targetRef", flow.target)
        if flow.condition:
            cond = ET.SubElement(sf, _tag(_BPMN, "conditionExpression"))
            cond.set("{http://www.w3.org/2001/XMLSchema-instance}type", "bpmn:tFormalExpression")
            cond.text = flow.condition
        if flow.is_default:
            # Mark source gateway's default attribute
            src_el = process.get_element(flow.source)
            if src_el:
                # Find the element node already written and set default attr
                for node in proc_el:
                    if node.get("id") == flow.source:
                        node.set("default", flow.id)

    # ── BPMN Diagram (DI) ─────────────────────────────────────────────────────
    diagram = ET.SubElement(definitions, _tag(_DI, "BPMNDiagram"))
    diagram.set("id", "BPMNDiagram_1")
    plane = ET.SubElement(diagram, _tag(_DI, "BPMNPlane"))
    plane.set("id", "BPMNPlane_1")
    plane.set("bpmnElement", "collaboration_1" if process.pools else process.process_id)

    # Pool shape
    if process.pools:
        pool_x, pool_y, pool_w, pool_h = _compute_pool_bounds(process, positions)
        for pool in process.pools:
            ps = ET.SubElement(plane, _tag(_DI, "BPMNShape"))
            ps.set("id", f"{pool.id}_di")
            ps.set("bpmnElement", pool.id)
            ps.set("isHorizontal", "true")
            _bounds(ps, pool_x - _POOL_HEADER_W, pool_y, pool_w + _POOL_HEADER_W, pool_h)

            # Lane shapes
            lane_h_total = pool_h / max(len(pool.lanes), 1)
            for i, lane in enumerate(pool.lanes):
                ls = ET.SubElement(plane, _tag(_DI, "BPMNShape"))
                ls.set("id", f"{lane.id}_di")
                ls.set("bpmnElement", lane.id)
                ls.set("isHorizontal", "true")
                _bounds(ls, pool_x, pool_y + i * lane_h_total, pool_w, lane_h_total)

    # Element shapes
    for el in process.elements:
        if el.id not in positions:
            continue
        x, y, w, h = positions[el.id]
        shape = ET.SubElement(plane, _tag(_DI, "BPMNShape"))
        shape.set("id", f"{el.id}_di")
        shape.set("bpmnElement", el.id)

        # Gateways need isMarkerVisible
        if "Gateway" in el.type:
            shape.set("isMarkerVisible", "true")

        # Sub-processes: expanded flag
        if el.type in ("subProcess", "adHocSubProcess"):
            shape.set("isExpanded", "true" if el.is_expanded else "false")

        _bounds(shape, x, y, w, h)

        # Sub-process children DI
        if el.type in ("subProcess", "adHocSubProcess") and el.is_expanded:
            child_y = y + 40
            child_x = x + 20
            for child in el.children:
                cshape = ET.SubElement(plane, _tag(_DI, "BPMNShape"))
                cshape.set("id", f"{child.id}_di")
                cshape.set("bpmnElement", child.id)
                _bounds(cshape, child_x, child_y, _TASK_W, _TASK_H)
                child_x += _TASK_W + 30

    # Sequence flow edges
    for flow in process.flows:
        src_pos = positions.get(flow.source)
        tgt_pos = positions.get(flow.target)
        if not src_pos or not tgt_pos:
            continue

        edge = ET.SubElement(plane, _tag(_DI, "BPMNEdge"))
        edge.set("id", f"{flow.id}_di")
        edge.set("bpmnElement", flow.id)

        sx, sy, sw, sh = src_pos
        tx, ty, tw, th = tgt_pos

        # Simple 2-waypoint path: center-bottom → center-top
        _waypoint(edge, sx + sw / 2, sy + sh)
        _waypoint(edge, tx + tw / 2, ty)

        if flow.name:
            label = ET.SubElement(edge, _tag(_DI, "BPMNLabel"))
            mx = (sx + sw / 2 + tx + tw / 2) / 2
            my = (sy + sh + ty) / 2
            _bounds(label, mx - 30, my - 10, 60, 20)

    return ET.tostring(definitions, encoding="unicode", xml_declaration=False)


# ── bpmn-js HTML preview ──────────────────────────────────────────────────────

def generate_bpmn_preview(bpmn_xml: str) -> str:
    """
    Returns a self-contained HTML page that renders the BPMN XML
    using bpmn-js NavigatedViewer (zoom + pan built-in).
    Safe to embed in st.components.html().
    """
    # Escape backticks so the XML can be safely embedded in a JS template literal
    escaped_xml = bpmn_xml.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8" />
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html, body {{ width: 100%; height: 100%; background: #f8fafc; }}
    #canvas {{
      width: 100%;
      height: calc(100vh - 48px);
      background: white;
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0,0,0,.1);
    }}
    #toolbar {{
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      background: #0f172a;
      height: 48px;
    }}
    #toolbar button {{
      background: #1e293b;
      color: #e2e8f0;
      border: 1px solid #334155;
      border-radius: 4px;
      padding: 4px 10px;
      cursor: pointer;
      font-size: 12px;
      font-family: monospace;
    }}
    #toolbar button:hover {{ background: #334155; }}
    #toolbar span {{
      color: #94a3b8;
      font-size: 12px;
      font-family: monospace;
      margin-left: auto;
    }}
    #error-box {{
      display: none;
      padding: 12px 16px;
      background: #fef2f2;
      color: #b91c1c;
      font-family: monospace;
      font-size: 12px;
      border-left: 4px solid #dc2626;
      margin: 12px;
      border-radius: 4px;
    }}
  </style>
</head>
<body>
  <div id="toolbar">
    <button onclick="viewer.get('zoomScroll').reset()">⟳ Fit</button>
    <button onclick="viewer.get('zoomScroll').zoom(0.2)">＋ Zoom In</button>
    <button onclick="viewer.get('zoomScroll').zoom(-0.2)">－ Zoom Out</button>
    <span id="info">Loading…</span>
  </div>
  <div id="error-box"></div>
  <div id="canvas"></div>

  <script src="https://unpkg.com/bpmn-js@17/dist/bpmn-navigated-viewer.production.min.js"></script>
  <script>
    const XML = `{escaped_xml}`;

    const viewer = new BpmnJS({{ container: '#canvas' }});

    viewer.importXML(XML).then(function(result) {{
      const warnings = result.warnings;
      viewer.get('canvas').zoom('fit-viewport');
      const info = document.getElementById('info');
      const elCount = XML.match(/bpmnElement=/g);
      info.textContent = 'Rendered · ' + (elCount ? elCount.length : '?') + ' elements' +
                         (warnings.length ? ' · ⚠ ' + warnings.length + ' warning(s)' : '');
    }}).catch(function(err) {{
      const box = document.getElementById('error-box');
      box.style.display = 'block';
      box.textContent = 'BPMN render error: ' + err.message;
      document.getElementById('info').textContent = 'Render failed';
    }});
  </script>
</body>
</html>"""
