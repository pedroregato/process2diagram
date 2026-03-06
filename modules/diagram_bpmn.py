# modules/diagram_bpmn.py
# Generates valid BPMN 2.0 XML (.bpmn) compatible with bpmn-js, Camunda, Bizagi, draw.io

import xml.etree.ElementTree as ET
from modules.schema import BpmnProcess, BpmnElement, BpmnLane, BpmnPool, SequenceFlow

# ── Namespaces ────────────────────────────────────────────────────────────────
_NS = {
    "bpmn":   "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
    "dc":     "http://www.omg.org/spec/DD/20100524/DC",
    "di":     "http://www.omg.org/spec/DD/20100524/DI",
    "xsi":    "http://www.w3.org/2001/XMLSchema-instance",
}
for _p, _u in _NS.items():
    ET.register_namespace(_p, _u)

B   = "{%s}" % _NS["bpmn"]
DI  = "{%s}" % _NS["bpmndi"]
DC  = "{%s}" % _NS["dc"]
DDI = "{%s}" % _NS["di"]

# ── Layout constants ──────────────────────────────────────────────────────────
TASK_W,  TASK_H   = 120, 60
GW_W,    GW_H     = 50,  50
EV_W,    EV_H     = 36,  36
H_GAP             = 60   # horizontal gap between elements
V_PAD             = 40   # vertical padding inside lane
LANE_HEADER_W     = 30   # width of lane label column
POOL_HEADER_W     = 30   # width of pool label column
FIRST_X           = 80   # x of first element inside lane (relative to lane start)
MIN_LANE_H        = 160


def _sub(parent, tag, attribs=None):
    return ET.SubElement(parent, tag, attribs or {})


def _ev_def(etype):
    return {
        "message": "messageEventDefinition", "timer": "timerEventDefinition",
        "error": "errorEventDefinition",     "signal": "signalEventDefinition",
        "escalation": "escalationEventDefinition",
        "terminate": "terminateEventDefinition",
        "compensation": "compensateEventDefinition",
        "cancel": "cancelEventDefinition",
        "conditional": "conditionalEventDefinition",
        "link": "linkEventDefinition",
    }.get(etype)


def _el_size(el):
    t = el.type
    if t in ("startEvent","endEvent","intermediateThrowEvent",
             "intermediateCatchEvent","boundaryEvent"):
        return EV_W, EV_H
    if "Gateway" in t:
        return GW_W, GW_H
    return TASK_W, TASK_H


# ── Process XML ───────────────────────────────────────────────────────────────

def _build_el(parent, el):
    t = el.type
    if t in ("startEvent","endEvent","intermediateThrowEvent","intermediateCatchEvent"):
        node = _sub(parent, B + t, {"id": el.id, "name": el.name})
        d = _ev_def(el.event_type)
        if d:
            _sub(node, B + d, {"id": el.id + "_def"})

    elif t == "boundaryEvent":
        attrs = {"id": el.id, "name": el.name,
                 "attachedToRef": el.attached_to or "",
                 "cancelActivity": str(el.is_interrupting).lower()}
        node = _sub(parent, B + "boundaryEvent", attrs)
        d = _ev_def(el.event_type)
        if d:
            _sub(node, B + d, {"id": el.id + "_def"})

    elif "Gateway" in t:
        _sub(parent, B + t, {"id": el.id, "name": el.name})

    elif t == "subProcess":
        node = _sub(parent, B + "subProcess",
                    {"id": el.id, "name": el.name, "triggeredByEvent": "false"})
        for child in el.children:
            _build_el(node, child)

    elif t == "callActivity":
        attrs = {"id": el.id, "name": el.name}
        if el.called_element:
            attrs["calledElement"] = el.called_element
        _sub(parent, B + "callActivity", attrs)

    else:
        tag = t if t in ("userTask","serviceTask","scriptTask","sendTask",
                         "receiveTask","manualTask","businessRuleTask") else "task"
        attrs = {"id": el.id, "name": el.name}
        node = _sub(parent, B + tag, attrs)
        if el.is_loop:
            _sub(node, B + "standardLoopCharacteristics", {"id": el.id + "_loop"})
        elif el.is_parallel_multi:
            mi = _sub(node, B + "multiInstanceLoopCharacteristics", {"id": el.id + "_mi"})
            mi.set("isSequential", "false")
        elif el.is_sequential_multi:
            mi = _sub(node, B + "multiInstanceLoopCharacteristics", {"id": el.id + "_mi"})
            mi.set("isSequential", "true")

    if el.documentation:
        # attach documentation to the last added child
        kids = list(parent)
        if kids:
            _sub(kids[-1], B + "documentation", {}).text = el.documentation


def _build_flow(parent, flow):
    attrs = {"id": flow.id, "name": flow.name,
             "sourceRef": flow.source, "targetRef": flow.target}
    node = _sub(parent, B + "sequenceFlow", attrs)
    if flow.condition:
        c = _sub(node, B + "conditionExpression",
                 {"{%s}type" % _NS["xsi"]: "tFormalExpression"})
        c.text = flow.condition


# ── Layout ────────────────────────────────────────────────────────────────────

def _topo_sort(elements, flows):
    """Return element ids in approximate topological order."""
    ids   = [e.id for e in elements]
    indeg = {i: 0 for i in ids}
    succ  = {i: [] for i in ids}
    id_set = set(ids)
    for f in flows:
        if f.source in id_set and f.target in id_set:
            succ[f.source].append(f.target)
            indeg[f.target] += 1
    queue  = [i for i in ids if indeg[i] == 0]
    result = []
    while queue:
        n = queue.pop(0)
        result.append(n)
        for m in succ[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    # append any remaining (cycles)
    for i in ids:
        if i not in result:
            result.append(i)
    return result


def _compute_layout(bpmn):
    """
    Returns:
      shapes      : {element_id: (x, y, w, h)}   — absolute coords
      pool_shapes : {pool/lane_id: (x, y, w, h)}  — absolute coords
    """
    shapes      = {}
    pool_shapes = {}

    order = _topo_sort(
        [e for e in bpmn.elements if e.type != "boundaryEvent"],
        bpmn.flows
    )

    if bpmn.pools:
        pool = bpmn.pools[0]

        # Collect ordered elements per lane
        lane_els = {}
        for lane in pool.lanes:
            s = set(lane.element_ids)
            lane_els[lane.id] = [eid for eid in order if eid in s]

        # Compute lane heights
        lane_h = {}
        for lane in pool.lanes:
            els = lane_els[lane.id]
            max_h = max((_el_size(e)[1] for e in bpmn.elements if e.id in set(els)),
                        default=TASK_H)
            lane_h[lane.id] = max(MIN_LANE_H, max_h + V_PAD * 2)

        total_pool_h = sum(lane_h[l.id] for l in pool.lanes)

        # Pool shape (absolute)
        pool_x = 0
        pool_y = 0
        pool_w = POOL_HEADER_W + LANE_HEADER_W

        # First pass: compute max width needed
        for lane in pool.lanes:
            els = lane_els[lane.id]
            if els:
                total_w = FIRST_X
                for eid in els:
                    el = next((e for e in bpmn.elements if e.id == eid), None)
                    if el:
                        w, _ = _el_size(el)
                        total_w += w + H_GAP
                pool_w = max(pool_w, POOL_HEADER_W + LANE_HEADER_W + total_w + H_GAP)

        pool_shapes[pool.id] = (pool_x, pool_y,
                                max(pool_w, 600), total_pool_h + 0)

        # Lane shapes and element positions
        cur_y = pool_y
        for lane in pool.lanes:
            lh = lane_h[lane.id]
            lx = pool_x + POOL_HEADER_W
            ly = cur_y
            lw = pool_shapes[pool.id][2] - POOL_HEADER_W
            pool_shapes[lane.id] = (lx, ly, lw, lh)

            els = lane_els[lane.id]
            cur_x = lx + LANE_HEADER_W + FIRST_X
            for eid in els:
                el = next((e for e in bpmn.elements if e.id == eid), None)
                if not el:
                    continue
                w, h = _el_size(el)
                x = int(cur_x)
                y = int(ly + (lh - h) / 2)
                shapes[el.id] = (x, y, w, h)
                cur_x += w + H_GAP

            cur_y += lh

    else:
        # No pools — simple vertical layout
        cur_y = V_PAD
        for eid in order:
            el = next((e for e in bpmn.elements
                       if e.id == eid and e.type != "boundaryEvent"), None)
            if not el:
                continue
            w, h = _el_size(el)
            shapes[el.id] = (FIRST_X, int(cur_y), w, h)
            cur_y += h + H_GAP

    # Boundary events: anchored to bottom-right of host
    for el in bpmn.elements:
        if el.type == "boundaryEvent" and el.attached_to:
            host = shapes.get(el.attached_to)
            if host:
                hx, hy, hw, hh = host
                shapes[el.id] = (hx + hw - EV_W // 2,
                                  hy + hh - EV_H // 2,
                                  EV_W, EV_H)
            else:
                # Host not found — place off-canvas so bpmn-js doesn't crash
                shapes[el.id] = (10, 10, EV_W, EV_H)

    return shapes, pool_shapes


# ── DI builder ────────────────────────────────────────────────────────────────

def _wp(edge, x, y):
    wp = _sub(edge, DDI + "waypoint")
    wp.set("x", str(int(x)))
    wp.set("y", str(int(y)))


def _build_di(diagram, plane_bpmn_el, shapes, pool_shapes, bpmn):
    plane = _sub(diagram, DI + "BPMNPlane",
                 {"id": "plane_1", "bpmnElement": plane_bpmn_el})

    # Pool / lane shapes (isHorizontal=true required for lanes)
    for eid, (x, y, w, h) in pool_shapes.items():
        shape = _sub(plane, DI + "BPMNShape",
                     {"id": eid + "_di", "bpmnElement": eid,
                      "isHorizontal": "true"})
        b = _sub(shape, DC + "Bounds")
        b.set("x", str(int(x))); b.set("y", str(int(y)))
        b.set("width", str(int(w))); b.set("height", str(int(h)))

    # Element shapes
    for el in bpmn.elements:
        if el.id not in shapes:
            continue
        x, y, w, h = shapes[el.id]
        # Validate — skip if any coord is invalid
        if any(v != v or abs(v) == float("inf") for v in (x, y, w, h)):
            continue
        attrs = {"id": el.id + "_di", "bpmnElement": el.id}
        shape = _sub(plane, DI + "BPMNShape", attrs)
        b = _sub(shape, DC + "Bounds")
        b.set("x", str(int(x))); b.set("y", str(int(y)))
        b.set("width", str(int(w))); b.set("height", str(int(h)))
        # Label below element
        lbl = _sub(shape, DI + "BPMNLabel")
        lb  = _sub(lbl, DC + "Bounds")
        lb.set("x", str(int(x))); lb.set("y", str(int(y + h + 2)))
        lb.set("width", str(int(w))); lb.set("height", "20")

    # Edges
    for flow in bpmn.flows:
        src = shapes.get(flow.source)
        tgt = shapes.get(flow.target)
        edge = _sub(plane, DI + "BPMNEdge",
                    {"id": flow.id + "_di", "bpmnElement": flow.id})
        if src and tgt:
            sx, sy, sw, sh = src
            tx, ty, tw, th = tgt
            # Source: right-center; Target: left-center
            _wp(edge, sx + sw,       sy + sh / 2)
            _wp(edge, tx,            ty + th / 2)
        else:
            # Fallback waypoints to avoid SVGMatrix crash
            _wp(edge, 100, 100)
            _wp(edge, 200, 100)
        if flow.name:
            lbl = _sub(edge, DI + "BPMNLabel")
            _sub(lbl, DC + "Bounds",
                 {"x": "0", "y": "0", "width": "60", "height": "14"})


# ── Public API ────────────────────────────────────────────────────────────────

def generate_bpmn_xml(bpmn: BpmnProcess) -> str:
    """Generate BPMN 2.0 XML string. Save as .bpmn to open in any BPMN tool."""
    defs = ET.Element(B + "definitions", {
        "xmlns":          _NS["bpmn"],
        "xmlns:bpmndi":   _NS["bpmndi"],
        "xmlns:dc":       _NS["dc"],
        "xmlns:di":       _NS["di"],
        "xmlns:xsi":      _NS["xsi"],
        "targetNamespace":"http://process2diagram.io/bpmn",
        "id":             "definitions_1",
        "exporter":       "Process2Diagram",
        "exporterVersion":"2.0",
    })

    process_id = "process_1"
    proc = _sub(defs, B + "process", {
        "id": process_id, "name": bpmn.name,
        "isExecutable": "false", "processType": "None",
    })
    if bpmn.documentation:
        _sub(proc, B + "documentation", {}).text = bpmn.documentation

    # Lane set
    if bpmn.pools:
        pool = bpmn.pools[0]
        lset = _sub(proc, B + "laneSet", {"id": pool.id + "_lset"})
        for lane in pool.lanes:
            ln = _sub(lset, B + "lane", {"id": lane.id, "name": lane.name})
            for eid in lane.element_ids:
                _sub(ln, B + "flowNodeRef", {}).text = eid

    # Elements
    for el in bpmn.elements:
        _build_el(proc, el)

    # Flows
    for flow in bpmn.flows:
        _build_flow(proc, flow)

    # Collaboration
    collab_id = None
    if bpmn.pools:
        pool      = bpmn.pools[0]
        collab_id = "collab_1"
        collab    = _sub(defs, B + "collaboration", {"id": collab_id})
        _sub(collab, B + "participant", {
            "id": pool.id, "name": pool.name, "processRef": process_id,
        })

    # Diagram interchange
    # CRITICAL: BPMNPlane must reference collaboration when it exists
    shapes, pool_shapes = _compute_layout(bpmn)
    plane_ref = collab_id if collab_id else process_id
    diagram   = _sub(defs, DI + "BPMNDiagram", {"id": "diagram_1"})
    _build_di(diagram, plane_ref, shapes, pool_shapes, bpmn)

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + \
           ET.tostring(defs, encoding="unicode")


def generate_bpmn_preview(bpmn: BpmnProcess) -> str:
    """HTML with bpmn-js viewer + zoom/pan toolbar. Use in components.html()."""
    xml = generate_bpmn_xml(bpmn)
    # Escape backticks and $ for JS template literal
    xml_js = xml.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")

    return f"""<!DOCTYPE html>
<html>
<head>
  <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{background:#f8fafc;overflow:hidden}}
    #canvas{{width:100vw;height:100vh}}
    #toolbar{{
      position:fixed;bottom:16px;left:50%;transform:translateX(-50%);
      display:flex;align-items:center;gap:4px;
      background:rgba(15,23,42,0.92);backdrop-filter:blur(12px);
      border-radius:12px;padding:6px 10px;
      box-shadow:0 4px 24px rgba(0,0,0,0.3);z-index:100;
    }}
    .tb-btn{{
      width:32px;height:32px;border:none;background:transparent;
      color:#94a3b8;border-radius:6px;cursor:pointer;font-size:15px;
      display:flex;align-items:center;justify-content:center;
      transition:background 0.15s,color 0.15s;
    }}
    .tb-btn:hover{{background:rgba(255,255,255,0.1);color:#e2e8f0}}
    .tb-divider{{width:1px;height:20px;background:rgba(255,255,255,0.12);margin:0 2px}}
    #zoom-label{{color:#64748b;font-size:11px;font-family:monospace;min-width:38px;text-align:center}}
    #err{{display:none;position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);
      background:white;border:1px solid #fca5a5;border-radius:8px;padding:24px;
      max-width:500px;font-family:monospace;font-size:12px;color:#dc2626;
      box-shadow:0 4px 24px rgba(0,0,0,0.15)}}
  </style>
  <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17/dist/assets/bpmn-js.css">
  <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17/dist/assets/diagram-js.css">
  <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17/dist/assets/bpmn-font/css/bpmn-embedded.css">
</head>
<body>
<div id="canvas"></div>
<div id="toolbar">
  <button class="tb-btn" id="btn-out"   title="Zoom out">&#8722;</button>
  <span   id="zoom-label">100%</span>
  <button class="tb-btn" id="btn-in"    title="Zoom in">&#43;</button>
  <div class="tb-divider"></div>
  <button class="tb-btn" id="btn-fit"   title="Fit to screen">&#8862;</button>
  <button class="tb-btn" id="btn-reset" title="Reset zoom">&#8634;</button>
</div>
<div id="err"></div>
<script src="https://unpkg.com/bpmn-js@17/dist/bpmn-viewer.development.js"></script>
<script>
const xml = `{xml_js}`;
const viewer  = new BpmnJS({{container:'#canvas'}});
const zoomLbl = document.getElementById('zoom-label');
const errDiv  = document.getElementById('err');

function updateLabel(){{
  try {{ zoomLbl.textContent = Math.round(viewer.get('canvas').zoom()*100)+'%'; }} catch(e){{}}
}}

viewer.importXML(xml).then(()=>{{
  viewer.get('canvas').zoom('fit-viewport','auto');
  updateLabel();
}}).catch(err=>{{
  errDiv.style.display='block';
  errDiv.textContent = 'BPMN render error:\\n' + err.message;
}});

document.getElementById('btn-in').onclick    = ()=>{{ viewer.get('zoomScroll').stepZoom(1);  updateLabel(); }};
document.getElementById('btn-out').onclick   = ()=>{{ viewer.get('zoomScroll').stepZoom(-1); updateLabel(); }};
document.getElementById('btn-fit').onclick   = ()=>{{ viewer.get('canvas').zoom('fit-viewport','auto'); updateLabel(); }};
document.getElementById('btn-reset').onclick = ()=>{{ viewer.get('canvas').zoom(1); updateLabel(); }};
viewer.get('eventBus').on('canvas.viewbox.changed', updateLabel);
</script>
</body>
</html>"""
