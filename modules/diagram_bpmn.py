# modules/diagram_bpmn.py
# Generates valid BPMN 2.0 XML (.bpmn) from a BpmnProcess model.
# Compatible with: Camunda Modeler, Signavio, Bizagi, draw.io, bpmn.io

import xml.etree.ElementTree as ET
from modules.schema import BpmnProcess, BpmnElement, BpmnLane, BpmnPool, SequenceFlow

# ── Namespaces ────────────────────────────────────────────────────────────────
NS = {
    "bpmn":  "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmndi":"http://www.omg.org/spec/BPMN/20100524/DI",
    "dc":    "http://www.omg.org/spec/DD/20100524/DC",
    "di":    "http://www.omg.org/spec/DD/20100524/DI",
    "xsi":   "http://www.w3.org/2001/XMLSchema-instance",
}
for prefix, uri in NS.items():
    ET.register_namespace(prefix, uri)

B  = "{%s}" % NS["bpmn"]
DI = "{%s}" % NS["bpmndi"]
DC = "{%s}" % NS["dc"]
DID= "{%s}" % NS["di"]

# ── Layout constants ──────────────────────────────────────────────────────────
TASK_W, TASK_H       = 120, 60
GW_W,   GW_H         = 50,  50
EVENT_W, EVENT_H     = 36,  36
LANE_W               = 800
LANE_HEADER          = 30
ROW_H                = 100   # vertical spacing between elements
COL_X                = 180   # x of first element column
START_Y              = 40    # y of first row
POOL_HEADER          = 30

# ── BPMN tag helpers ──────────────────────────────────────────────────────────

def _tag(parent, local, attribs=None, text=None):
    el = ET.SubElement(parent, B + local, attribs or {})
    if text:
        el.text = text
    return el


def _event_def_tag(etype):
    mapping = {
        "message":      "messageEventDefinition",
        "timer":        "timerEventDefinition",
        "error":        "errorEventDefinition",
        "signal":       "signalEventDefinition",
        "escalation":   "escalationEventDefinition",
        "terminate":    "terminateEventDefinition",
        "compensation": "compensateEventDefinition",
        "cancel":       "cancelEventDefinition",
        "conditional":  "conditionalEventDefinition",
        "link":         "linkEventDefinition",
    }
    return mapping.get(etype)


# ── Element XML builders ──────────────────────────────────────────────────────

def _build_element(parent, el: BpmnElement, process_id: str):
    t = el.type

    if t == "startEvent":
        node = _tag(parent, "startEvent", {"id": el.id, "name": el.name})
        defn = _event_def_tag(el.event_type)
        if defn:
            _tag(node, defn, {"id": el.id + "_def"})

    elif t == "endEvent":
        node = _tag(parent, "endEvent", {"id": el.id, "name": el.name})
        defn = _event_def_tag(el.event_type)
        if defn:
            _tag(node, defn, {"id": el.id + "_def"})

    elif t == "intermediateThrowEvent":
        node = _tag(parent, "intermediateThrowEvent", {"id": el.id, "name": el.name})
        defn = _event_def_tag(el.event_type)
        if defn:
            _tag(node, defn, {"id": el.id + "_def"})

    elif t == "intermediateCatchEvent":
        node = _tag(parent, "intermediateCatchEvent", {"id": el.id, "name": el.name})
        defn = _event_def_tag(el.event_type)
        if defn:
            _tag(node, defn, {"id": el.id + "_def"})

    elif t == "boundaryEvent":
        attrs = {
            "id": el.id, "name": el.name,
            "attachedToRef": el.attached_to or "",
            "cancelActivity": str(el.is_interrupting).lower(),
        }
        node = _tag(parent, "boundaryEvent", attrs)
        defn = _event_def_tag(el.event_type)
        if defn:
            _tag(node, defn, {"id": el.id + "_def"})

    elif t in ("exclusiveGateway", "parallelGateway",
               "inclusiveGateway", "eventBasedGateway", "complexGateway"):
        _tag(parent, t, {"id": el.id, "name": el.name})

    elif t == "subProcess":
        attrs = {"id": el.id, "name": el.name,
                 "triggeredByEvent": "false"}
        node = _tag(parent, "subProcess", attrs)
        for child in el.children:
            _build_element(node, child, process_id)

    elif t == "callActivity":
        attrs = {"id": el.id, "name": el.name}
        if el.called_element:
            attrs["calledElement"] = el.called_element
        _tag(parent, "callActivity", attrs)

    else:
        # userTask, serviceTask, scriptTask, sendTask, receiveTask,
        # manualTask, businessRuleTask, task  → all map to their BPMN tag
        tag_name = t if t in (
            "userTask","serviceTask","scriptTask","sendTask",
            "receiveTask","manualTask","businessRuleTask",
        ) else "task"
        attrs = {"id": el.id, "name": el.name}
        if el.is_loop:
            node = _tag(parent, tag_name, attrs)
            _tag(node, "standardLoopCharacteristics", {"id": el.id + "_loop"})
        elif el.is_parallel_multi:
            node = _tag(parent, tag_name, attrs)
            mi = _tag(node, "multiInstanceLoopCharacteristics", {"id": el.id + "_mi"})
            mi.set("isSequential", "false")
        elif el.is_sequential_multi:
            node = _tag(parent, tag_name, attrs)
            mi = _tag(node, "multiInstanceLoopCharacteristics", {"id": el.id + "_mi"})
            mi.set("isSequential", "true")
        else:
            _tag(parent, tag_name, attrs)

    if el.documentation:
        doc_parent = parent.find(B + t) or parent[-1]
        _tag(doc_parent, "documentation", {}, el.documentation)


def _build_flow(parent, flow: SequenceFlow):
    attrs = {
        "id":        flow.id,
        "name":      flow.name,
        "sourceRef": flow.source,
        "targetRef": flow.target,
    }
    if flow.is_default:
        attrs["default"] = flow.id
    node = _tag(parent, "sequenceFlow", attrs)
    if flow.condition:
        cond = _tag(node, "conditionExpression",
                    {"xsi:type": "tFormalExpression"})
        cond.text = flow.condition
    return node


# ── Layout engine ─────────────────────────────────────────────────────────────

def _layout(bpmn: BpmnProcess):
    """
    Assigns (x, y, w, h) to every element and returns two dicts:
      shapes: {element_id: (x, y, w, h)}
      pool_shapes: {pool_or_lane_id: (x, y, w, h)}
    """
    shapes = {}
    pool_shapes = {}

    if bpmn.pools:
        pool = bpmn.pools[0]
        n_lanes = len(pool.lanes)
        lane_h = max(ROW_H * 4, ROW_H * 2 + START_Y * 2)

        # Collect order of elements per lane
        lane_elements = {}
        for lane in pool.lanes:
            ids = lane.element_ids
            lane_elements[lane.id] = [e for e in bpmn.elements if e.id in ids]

        # Auto-size lane height based on element count
        for lane in pool.lanes:
            count = max(len(lane_elements.get(lane.id, [])), 1)
            lane_h = max(lane_h, ROW_H * count + START_Y)

        pool_y = 0
        pool_h = lane_h * n_lanes + POOL_HEADER

        pool_shapes[pool.id] = (0, pool_y, LANE_W + LANE_HEADER + POOL_HEADER, pool_h)

        for li, lane in enumerate(pool.lanes):
            lx = POOL_HEADER
            ly = pool_y + POOL_HEADER + li * lane_h
            pool_shapes[lane.id] = (lx, ly, LANE_W + LANE_HEADER, lane_h)

            els = lane_elements.get(lane.id, [])
            for ei, el in enumerate(els):
                w, h = _element_size(el)
                x = lx + LANE_HEADER + COL_X + ei * (TASK_W + 80)
                y = ly + (lane_h - h) / 2
                shapes[el.id] = (int(x), int(y), w, h)

    else:
        # No pools — simple vertical layout
        for i, el in enumerate(bpmn.elements):
            w, h = _element_size(el)
            x = COL_X
            y = START_Y + i * ROW_H
            shapes[el.id] = (x, y, w, h)

    # Boundary events: overlay on host element
    for el in bpmn.elements:
        if el.type == "boundaryEvent" and el.attached_to:
            host = shapes.get(el.attached_to)
            if host:
                hx, hy, hw, hh = host
                shapes[el.id] = (hx + hw - EVENT_W // 2, hy + hh - EVENT_H // 2,
                                  EVENT_W, EVENT_H)

    return shapes, pool_shapes


def _element_size(el: BpmnElement):
    if el.type in ("startEvent","endEvent","intermediateThrowEvent",
                   "intermediateCatchEvent","boundaryEvent"):
        return EVENT_W, EVENT_H
    if "Gateway" in el.type:
        return GW_W, GW_H
    return TASK_W, TASK_H


# ── DI (diagram interchange) builder ─────────────────────────────────────────

def _build_di(diagram, plane_id, shapes, pool_shapes, bpmn, flows_idx):
    plane = ET.SubElement(diagram, DI + "BPMNPlane",
                          {"id": plane_id + "_plane",
                           "bpmnElement": plane_id})

    # Pool & lane shapes
    for eid, (x, y, w, h) in pool_shapes.items():
        shape = ET.SubElement(plane, DI + "BPMNShape",
                              {"id": eid + "_di", "bpmnElement": eid,
                               "isHorizontal": "true"})
        bounds = ET.SubElement(shape, DC + "Bounds")
        bounds.set("x", str(x)); bounds.set("y", str(y))
        bounds.set("width", str(w)); bounds.set("height", str(h))

    # Element shapes
    for el in bpmn.elements:
        if el.id not in shapes:
            continue
        x, y, w, h = shapes[el.id]
        is_marker = el.type in ("startEvent","endEvent","intermediateCatchEvent",
                                 "intermediateThrowEvent","boundaryEvent")
        attrs = {"id": el.id + "_di", "bpmnElement": el.id}
        if not is_marker:
            attrs["isExpanded"] = str(el.is_expanded).lower() if el.type == "subProcess" else "false"
        shape = ET.SubElement(plane, DI + "BPMNShape", attrs)
        bounds = ET.SubElement(shape, DC + "Bounds")
        bounds.set("x", str(x)); bounds.set("y", str(y))
        bounds.set("width", str(w)); bounds.set("height", str(h))
        lbl = ET.SubElement(shape, DI + "BPMNLabel")
        lbl_bounds = ET.SubElement(lbl, DC + "Bounds")
        lbl_bounds.set("x", str(x)); lbl_bounds.set("y", str(y + h + 2))
        lbl_bounds.set("width", str(w)); lbl_bounds.set("height", "14")

    # Edges
    for flow in bpmn.flows:
        src = shapes.get(flow.source)
        tgt = shapes.get(flow.target)
        edge = ET.SubElement(plane, DI + "BPMNEdge",
                             {"id": flow.id + "_di", "bpmnElement": flow.id})
        if src and tgt:
            sx, sy, sw, sh = src
            tx2, ty2, tw, th = tgt
            wp1 = ET.SubElement(edge, DID + "waypoint")
            wp1.set("x", str(sx + sw // 2)); wp1.set("y", str(sy + sh // 2))
            wp2 = ET.SubElement(edge, DID + "waypoint")
            wp2.set("x", str(tx2 + tw // 2)); wp2.set("y", str(ty2 + th // 2))
        if flow.name:
            lbl = ET.SubElement(edge, DI + "BPMNLabel")
            ET.SubElement(lbl, DC + "Bounds",
                          {"x": "0","y": "0","width": "50","height": "14"})


# ── Public entry point ────────────────────────────────────────────────────────

def generate_bpmn_xml(bpmn: BpmnProcess) -> str:
    """
    Generates a valid BPMN 2.0 XML string from a BpmnProcess.
    The output can be saved as .bpmn and opened in any BPMN tool.
    """
    # Root
    defs = ET.Element(B + "definitions", {
        "xmlns":      NS["bpmn"],
        "xmlns:bpmndi": NS["bpmndi"],
        "xmlns:dc":   NS["dc"],
        "xmlns:di":   NS["di"],
        "xmlns:xsi":  NS["xsi"],
        "targetNamespace": "http://process2diagram.io/bpmn",
        "id":         "definitions_1",
        "exporter":   "Process2Diagram",
        "exporterVersion": "2.0",
    })

    process_id = "process_1"
    proc = ET.SubElement(defs, B + "process", {
        "id":          process_id,
        "name":        bpmn.name,
        "isExecutable":"false",
        "processType": "None",
    })

    if bpmn.documentation:
        _tag(proc, "documentation", {}, bpmn.documentation)

    # Lanes
    if bpmn.pools:
        pool = bpmn.pools[0]
        lset = _tag(proc, "laneSet", {"id": pool.id + "_lset", "name": ""})
        for lane in pool.lanes:
            ln = _tag(lset, "lane", {"id": lane.id, "name": lane.name})
            for eid in lane.element_ids:
                _tag(ln, "flowNodeRef", {}, eid)

    # Elements
    for el in bpmn.elements:
        _build_element(proc, el, process_id)

    # Flows
    flows_idx = {}
    for flow in bpmn.flows:
        _build_flow(proc, flow)
        flows_idx[flow.id] = flow

    # Collaboration (pool box)
    if bpmn.pools:
        pool = bpmn.pools[0]
        collab = ET.SubElement(defs, B + "collaboration", {"id": "collab_1"})
        ET.SubElement(collab, B + "participant", {
            "id":          pool.id,
            "name":        pool.name,
            "processRef":  process_id,
        })

    # Diagram interchange
    diagram = ET.SubElement(defs, DI + "BPMNDiagram", {"id": "diagram_1"})
    shapes, pool_shapes = _layout(bpmn)
    _build_di(diagram, process_id, shapes, pool_shapes, bpmn, flows_idx)

    return ET.tostring(defs, encoding="unicode", xml_declaration=False)


def generate_bpmn_preview(bpmn: BpmnProcess) -> str:
    """
    Returns an HTML string that renders the BPMN using bpmn-js (Camunda viewer).
    Embed in a Streamlit components.html() call.
    """
    xml = generate_bpmn_xml(bpmn)
    xml_escaped = xml.replace("`", "\\`").replace("$", "\\$")

    return f"""<!DOCTYPE html>
<html>
<head>
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body {{ background:#f8fafc; overflow:hidden; }}
    #canvas {{ width:100vw; height:100vh; }}
    #toolbar {{
      position:fixed; bottom:16px; left:50%; transform:translateX(-50%);
      display:flex; align-items:center; gap:4px;
      background:rgba(15,23,42,0.92); backdrop-filter:blur(12px);
      border-radius:12px; padding:6px 10px;
      box-shadow:0 4px 24px rgba(0,0,0,0.3); z-index:100;
    }}
    .tb-btn {{
      width:32px; height:32px; border:none; background:transparent;
      color:#94a3b8; border-radius:6px; cursor:pointer; font-size:15px;
      display:flex; align-items:center; justify-content:center;
      transition:background 0.15s, color 0.15s;
    }}
    .tb-btn:hover {{ background:rgba(255,255,255,0.1); color:#e2e8f0; }}
    .tb-divider {{ width:1px; height:20px; background:rgba(255,255,255,0.12); margin:0 2px; }}
    #zoom-label {{ color:#64748b; font-size:11px; font-family:monospace; min-width:38px; text-align:center; }}
    #toast {{
      position:fixed; top:16px; left:50%;
      transform:translateX(-50%) translateY(-60px);
      background:rgba(15,23,42,0.92); color:#e2e8f0; font-size:12px;
      padding:6px 14px; border-radius:20px;
      transition:transform 0.25s cubic-bezier(.34,1.56,.64,1);
      pointer-events:none; font-family:monospace;
    }}
    #toast.show {{ transform:translateX(-50%) translateY(0); }}
  </style>
  <link rel="stylesheet"
    href="https://unpkg.com/bpmn-js@17/dist/assets/bpmn-js.css">
  <link rel="stylesheet"
    href="https://unpkg.com/bpmn-js@17/dist/assets/diagram-js.css">
  <link rel="stylesheet"
    href="https://unpkg.com/bpmn-js@17/dist/assets/bpmn-font/css/bpmn-embedded.css">
</head>
<body>
<div id="canvas"></div>
<div id="toolbar">
  <button class="tb-btn" id="btn-zoom-out" title="Zoom out">&#8722;</button>
  <span id="zoom-label">100%</span>
  <button class="tb-btn" id="btn-zoom-in"  title="Zoom in">&#43;</button>
  <div class="tb-divider"></div>
  <button class="tb-btn" id="btn-fit"   title="Fit to screen">&#8862;</button>
  <button class="tb-btn" id="btn-reset" title="Reset view">&#8634;</button>
</div>
<div id="toast"></div>

<script src="https://unpkg.com/bpmn-js@17/dist/bpmn-viewer.development.js"></script>
<script>
  const bpmnXml = `{xml_escaped}`;
  const viewer = new BpmnJS({{ container: '#canvas' }});
  const zoomLbl = document.getElementById('zoom-label');
  const toast   = document.getElementById('toast');

  function showToast(msg) {{
    toast.textContent = msg; toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 1800);
  }}
  function updateZoomLabel() {{
    const z = viewer.get('canvas').zoom();
    zoomLbl.textContent = Math.round(z * 100) + '%';
  }}

  viewer.importXML(bpmnXml).then(() => {{
    viewer.get('canvas').zoom('fit-viewport', 'auto');
    updateZoomLabel();
  }}).catch(err => {{
    document.body.innerHTML = '<pre style="color:red;padding:16px">' +
      'BPMN render error:\\n' + err.message + '</pre>';
  }});

  document.getElementById('btn-zoom-in').onclick = () => {{
    viewer.get('zoomScroll').stepZoom(1); updateZoomLabel();
  }};
  document.getElementById('btn-zoom-out').onclick = () => {{
    viewer.get('zoomScroll').stepZoom(-1); updateZoomLabel();
  }};
  document.getElementById('btn-fit').onclick = () => {{
    viewer.get('canvas').zoom('fit-viewport', 'auto'); updateZoomLabel();
  }};
  document.getElementById('btn-reset').onclick = () => {{
    viewer.get('canvas').zoom(1); updateZoomLabel();
  }};
</script>
</body>
</html>"""
