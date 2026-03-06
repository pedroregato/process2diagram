# modules/diagram_bpmn.py
# BPMN 2.0 XML generator + bpmn-js preview
# Compatible with: Camunda Modeler, Bizagi, draw.io, bpmn.io, Signavio

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
H_GAP             = 60
V_PAD             = 50
LANE_HEADER_W     = 30
POOL_HEADER_W     = 30
FIRST_X           = 80
MIN_LANE_H        = 160


def _sub(parent, tag, attribs=None):
    return ET.SubElement(parent, tag, attribs or {})


def _ev_def(etype):
    return {
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
    }.get(etype)


def _el_size(el):
    t = el.type
    if t in ("startEvent", "endEvent", "intermediateThrowEvent",
             "intermediateCatchEvent", "boundaryEvent"):
        return EV_W, EV_H
    if "Gateway" in t:
        return GW_W, GW_H
    return TASK_W, TASK_H


# ── Lane assignment ───────────────────────────────────────────────────────────

def _assign_lanes(bpmn):
    """
    Returns a dict {element_id: lane_id} for every non-boundary element.

    Priority:
      1. Explicit assignment via lane.element_ids
      2. Element actor/lane field matches a lane name
      3. Flow-context inference (inherit from assigned neighbor)
      4. Fallback: first lane (startEvent/endEvent land here naturally)
    """
    if not bpmn.pools:
        return {}

    pool = bpmn.pools[0]
    if not pool.lanes:
        return {}

    assignment = {}

    # Step 1 — explicit element_ids in lane definition
    for lane in pool.lanes:
        for eid in lane.element_ids:
            assignment[eid] = lane.id

    # Step 2 — match by actor/lane name on the element itself
    lane_by_name = {lane.name: lane.id for lane in pool.lanes}
    for el in bpmn.elements:
        if el.type == "boundaryEvent":
            continue
        if el.id in assignment:
            continue
        actor = el.actor or el.lane
        if actor and actor in lane_by_name:
            assignment[el.id] = lane_by_name[actor]

    # Collect still-unassigned non-boundary element ids
    all_ids = {e.id for e in bpmn.elements if e.type != "boundaryEvent"}
    unassigned = all_ids - set(assignment.keys())

    if not unassigned:
        return assignment

    # Step 3 — flow-context inference
    predecessors = {e.id: [] for e in bpmn.elements}
    successors   = {e.id: [] for e in bpmn.elements}
    for f in bpmn.flows:
        if f.source in predecessors:
            successors[f.source].append(f.target)
        if f.target in predecessors:
            predecessors[f.target].append(f.source)

    changed = True
    while changed and unassigned:
        changed = False
        for eid in list(unassigned):
            neighbors = predecessors.get(eid, []) + successors.get(eid, [])
            for nid in neighbors:
                if nid in assignment:
                    assignment[eid] = assignment[nid]
                    unassigned.discard(eid)
                    changed = True
                    break

    # Step 4 — true fallback: first lane (catches startEvent/endEvent with actor=null)
    fallback_lane = pool.lanes[0].id
    for eid in unassigned:
        assignment[eid] = fallback_lane

    return assignment


# ── Process XML builders ──────────────────────────────────────────────────────

def _build_el(parent, el):
    t = el.type
    if t in ("startEvent", "endEvent", "intermediateThrowEvent", "intermediateCatchEvent"):
        node = _sub(parent, B + t, {"id": el.id, "name": el.name})
        d = _ev_def(el.event_type)
        if d:
            _sub(node, B + d, {"id": el.id + "_def"})

    elif t == "boundaryEvent":
        attrs = {
            "id": el.id, "name": el.name,
            "attachedToRef": el.attached_to or "",
            "cancelActivity": str(el.is_interrupting).lower(),
        }
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
        tag = t if t in ("userTask", "serviceTask", "scriptTask", "sendTask",
                         "receiveTask", "manualTask", "businessRuleTask") else "task"
        node = _sub(parent, B + tag, {"id": el.id, "name": el.name})
        if el.is_loop:
            _sub(node, B + "standardLoopCharacteristics", {"id": el.id + "_loop"})
        elif el.is_parallel_multi:
            mi = _sub(node, B + "multiInstanceLoopCharacteristics", {"id": el.id + "_mi"})
            mi.set("isSequential", "false")
        elif el.is_sequential_multi:
            mi = _sub(node, B + "multiInstanceLoopCharacteristics", {"id": el.id + "_mi"})
            mi.set("isSequential", "true")

    if el.documentation:
        kids = list(parent)
        if kids:
            _sub(kids[-1], B + "documentation", {}).text = el.documentation


def _build_flow(parent, flow):
    node = _sub(parent, B + "sequenceFlow", {
        "id": flow.id, "name": flow.name,
        "sourceRef": flow.source, "targetRef": flow.target,
    })
    if flow.condition:
        c = _sub(node, B + "conditionExpression",
                 {"{%s}type" % _NS["xsi"]: "tFormalExpression"})
        c.text = flow.condition


# ── Layout ────────────────────────────────────────────────────────────────────

def _topo_sort(ids, flows):
    id_set = set(ids)
    indeg  = {i: 0 for i in ids}
    succ   = {i: [] for i in ids}
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
    for i in ids:
        if i not in result:
            result.append(i)
    return result


def _compute_layout(bpmn, lane_assignment):
    shapes      = {}
    pool_shapes = {}

    non_boundary = [e for e in bpmn.elements if e.type != "boundaryEvent"]
    order  = _topo_sort([e.id for e in non_boundary], bpmn.flows)
    el_map = {e.id: e for e in bpmn.elements}

    if bpmn.pools:
        pool = bpmn.pools[0]

        # Group ordered elements by lane (using fully-resolved assignment)
        lane_order = {lane.id: [] for lane in pool.lanes}
        for eid in order:
            lid = lane_assignment.get(eid)
            if lid and lid in lane_order:
                lane_order[lid].append(eid)
            # Elements not in any lane (should not happen after _assign_lanes fix,
            # but guard anyway) → put in first lane
            elif pool.lanes:
                lane_order[pool.lanes[0].id].append(eid)

        # Lane heights
        lane_h = {}
        for lane in pool.lanes:
            els_in_lane = [el_map[eid] for eid in lane_order[lane.id] if eid in el_map]
            max_h = max((_el_size(e)[1] for e in els_in_lane), default=TASK_H)
            lane_h[lane.id] = max(MIN_LANE_H, max_h + V_PAD * 2)

        total_h = sum(lane_h[l.id] for l in pool.lanes)

        # Compute pool width
        pool_w = 600
        for lane in pool.lanes:
            els = lane_order[lane.id]
            if els:
                w = POOL_HEADER_W + LANE_HEADER_W + FIRST_X
                for eid in els:
                    if eid in el_map:
                        ew, _ = _el_size(el_map[eid])
                        w += ew + H_GAP
                pool_w = max(pool_w, w)

        pool_shapes[pool.id] = (0, 0, pool_w, total_h)

        cur_y = 0
        for lane in pool.lanes:
            lh = lane_h[lane.id]
            lx = POOL_HEADER_W
            lw = pool_w - POOL_HEADER_W
            pool_shapes[lane.id] = (lx, cur_y, lw, lh)

            cur_x = lx + LANE_HEADER_W + FIRST_X
            for eid in lane_order[lane.id]:
                if eid not in el_map:
                    continue
                el = el_map[eid]
                w, h = _el_size(el)
                shapes[el.id] = (int(cur_x), int(cur_y + (lh - h) / 2), w, h)
                cur_x += w + H_GAP

            cur_y += lh

    else:
        # No pools — flat vertical layout
        cur_y = V_PAD
        for eid in order:
            if eid not in el_map:
                continue
            el = el_map[eid]
            if el.type == "boundaryEvent":
                continue
            w, h = _el_size(el)
            shapes[el.id] = (FIRST_X, int(cur_y), w, h)
            cur_y += h + H_GAP

    # Boundary events: anchored on host element
    for el in bpmn.elements:
        if el.type == "boundaryEvent" and el.attached_to:
            host = shapes.get(el.attached_to)
            if host:
                hx, hy, hw, hh = host
                shapes[el.id] = (hx + hw - EV_W // 2,
                                  hy + hh - EV_H // 2,
                                  EV_W, EV_H)
            # No host shape → boundary event gets no DI (bpmn-js skips it gracefully)

    return shapes, pool_shapes


# ── DI builder ────────────────────────────────────────────────────────────────

def _wp(edge, x, y):
    wp = _sub(edge, DDI + "waypoint")
    wp.set("x", str(int(x)))
    wp.set("y", str(int(y)))


def _valid(coords):
    """Return True only if all coords are real finite numbers > 0."""
    try:
        return all(
            isinstance(v, (int, float)) and v == v and abs(v) != float("inf") and v >= 0
            for v in coords
        )
    except Exception:
        return False


def _build_di(diagram, plane_ref, shapes, pool_shapes, bpmn):
    plane = _sub(diagram, DI + "BPMNPlane",
                 {"id": "plane_1", "bpmnElement": plane_ref})

    # Pool / lane shapes
    for eid, (x, y, w, h) in pool_shapes.items():
        shape = _sub(plane, DI + "BPMNShape",
                     {"id": eid + "_di", "bpmnElement": eid, "isHorizontal": "true"})
        b = _sub(shape, DC + "Bounds")
        b.set("x", str(int(x))); b.set("y", str(int(y)))
        b.set("width", str(int(w))); b.set("height", str(int(h)))

    # Element shapes — only emit if coords are valid finite numbers
    for el in bpmn.elements:
        if el.id not in shapes:
            continue
        coords = shapes[el.id]
        if not _valid(coords):
            continue
        x, y, w, h = coords
        shape = _sub(plane, DI + "BPMNShape", {"id": el.id + "_di", "bpmnElement": el.id})
        b = _sub(shape, DC + "Bounds")
        b.set("x", str(int(x))); b.set("y", str(int(y)))
        b.set("width", str(int(w))); b.set("height", str(int(h)))
        lbl = _sub(shape, DI + "BPMNLabel")
        lb  = _sub(lbl, DC + "Bounds")
        lb.set("x", str(int(x))); lb.set("y", str(int(y + h + 2)))
        lb.set("width", str(int(w))); lb.set("height", "20")

    # Edges — only emit if BOTH endpoints have valid shapes
    for flow in bpmn.flows:
        src_coords = shapes.get(flow.source)
        tgt_coords = shapes.get(flow.target)

        # Skip edge entirely if either endpoint has no valid shape
        # (avoids the SVGMatrix non-finite crash in bpmn-js)
        if not src_coords or not tgt_coords:
            continue
        if not _valid(src_coords) or not _valid(tgt_coords):
            continue

        edge = _sub(plane, DI + "BPMNEdge",
                    {"id": flow.id + "_di", "bpmnElement": flow.id})
        sx, sy, sw, sh = src_coords
        tx, ty, tw, th = tgt_coords
        _wp(edge, sx + sw,     sy + sh / 2)   # source right-centre
        _wp(edge, tx,          ty + th / 2)   # target left-centre

        if flow.name:
            lbl = _sub(edge, DI + "BPMNLabel")
            _sub(lbl, DC + "Bounds",
                 {"x": "0", "y": "0", "width": "60", "height": "14"})


# ── Public API ────────────────────────────────────────────────────────────────

def generate_bpmn_xml(bpmn: BpmnProcess) -> str:
    """Generate BPMN 2.0 XML. Save as .bpmn to open in Camunda, Bizagi, draw.io, etc."""
    defs = ET.Element(B + "definitions", {
        "xmlns":           _NS["bpmn"],
        "xmlns:bpmndi":    _NS["bpmndi"],
        "xmlns:dc":        _NS["dc"],
        "xmlns:di":        _NS["di"],
        "xmlns:xsi":       _NS["xsi"],
        "targetNamespace": "http://process2diagram.io/bpmn",
        "id":              "definitions_1",
        "exporter":        "Process2Diagram",
        "exporterVersion": "2.0",
    })

    process_id = "process_1"
    proc = _sub(defs, B + "process", {
        "id": process_id, "name": bpmn.name,
        "isExecutable": "false", "processType": "None",
    })
    if bpmn.documentation:
        _sub(proc, B + "documentation", {}).text = bpmn.documentation

    lane_assignment = _assign_lanes(bpmn)

    # Lane set — rebuilt from the fully-resolved assignment so every element is covered
    if bpmn.pools:
        pool = bpmn.pools[0]
        lset = _sub(proc, B + "laneSet", {"id": pool.id + "_lset"})
        lane_members = {lane.id: [] for lane in pool.lanes}
        for eid, lid in lane_assignment.items():
            if lid in lane_members:
                lane_members[lid].append(eid)
        for lane in pool.lanes:
            ln = _sub(lset, B + "lane", {"id": lane.id, "name": lane.name})
            for eid in lane_members[lane.id]:
                _sub(ln, B + "flowNodeRef", {}).text = eid

    # Elements & flows
    for el in bpmn.elements:
        _build_el(proc, el)
    for flow in bpmn.flows:
        _build_flow(proc, flow)

    # Collaboration (required when pools exist — BPMNPlane must ref collab, not process)
    collab_id = None
    if bpmn.pools:
        pool      = bpmn.pools[0]
        collab_id = "collab_1"
        collab    = _sub(defs, B + "collaboration", {"id": collab_id})
        _sub(collab, B + "participant",
             {"id": pool.id, "name": pool.name, "processRef": process_id})

    # Diagram interchange
    shapes, pool_shapes = _compute_layout(bpmn, lane_assignment)
    plane_ref = collab_id if collab_id else process_id
    diagram   = _sub(defs, DI + "BPMNDiagram", {"id": "diagram_1"})
    _build_di(diagram, plane_ref, shapes, pool_shapes, bpmn)

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + \
           ET.tostring(defs, encoding="unicode")


def generate_bpmn_preview(bpmn: BpmnProcess) -> str:
    """HTML with bpmn-js viewer. Use inside Streamlit components.html()."""
    xml    = generate_bpmn_xml(bpmn)
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
    #zoom-label{{color:#64748b;font-size:11px;font-family:monospace;
      min-width:38px;text-align:center}}
    #err{{display:none;position:fixed;top:16px;left:50%;
      transform:translateX(-50%);
      background:white;border:1px solid #fca5a5;border-radius:8px;
      padding:16px 24px;max-width:600px;font-family:monospace;font-size:12px;
      color:#dc2626;box-shadow:0 4px 24px rgba(0,0,0,0.15);z-index:200}}
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
const xml     = `{xml_js}`;
const viewer  = new BpmnJS({{container:'#canvas'}});
const zoomLbl = document.getElementById('zoom-label');
const errDiv  = document.getElementById('err');

function updateLabel() {{
  try {{ zoomLbl.textContent = Math.round(viewer.get('canvas').zoom()*100)+'%'; }} catch(e){{}}
}}

viewer.importXML(xml)
  .then(() => {{
    setTimeout(() => {{
      try {{
        viewer.get('canvas').zoom('fit-viewport', 'auto');
      }} catch(e) {{
        try {{ viewer.get('canvas').zoom(0.75); }} catch(_) {{}}
      }}
      updateLabel();
    }}, 150);
  }})
  .catch(err => {{
    errDiv.style.display = 'block';
    errDiv.innerHTML = '<b>BPMN render error:</b><br>' + err.message;
  }});

document.getElementById('btn-in').onclick    = () => {{ viewer.get('zoomScroll').stepZoom(1);  updateLabel(); }};
document.getElementById('btn-out').onclick   = () => {{ viewer.get('zoomScroll').stepZoom(-1); updateLabel(); }};
document.getElementById('btn-fit').onclick   = () => {{
  try {{ viewer.get('canvas').zoom('fit-viewport','auto'); }} catch(e) {{ viewer.get('canvas').zoom(0.75); }}
  updateLabel();
}};
document.getElementById('btn-reset').onclick = () => {{ viewer.get('canvas').zoom(1); updateLabel(); }};
viewer.get('eventBus').on('canvas.viewbox.changed', updateLabel);
</script>
</body>
</html>"""
