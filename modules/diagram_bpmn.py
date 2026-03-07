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
H_GAP             = 70
V_PAD             = 55
LANE_HEADER_W     = 100
POOL_HEADER_W     = 100
FIRST_X           = 80
MIN_LANE_H        = 180


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
      4. Fallback: first lane
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
            if eid:
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

    # Step 4 — fallback: first lane
    if unassigned and pool.lanes:
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
    """Topological sort."""
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


def _sort_lane_elements(lane_ids, el_map, flows):
    """Sort elements within a lane: startEvents first, endEvents last, rest topo-sorted."""
    starts = [i for i in lane_ids if el_map.get(i) and el_map[i].type == "startEvent"]
    ends   = [i for i in lane_ids if el_map.get(i) and el_map[i].type == "endEvent"]
    middle = [i for i in lane_ids if i not in starts and i not in ends]
    return starts + _topo_sort(middle, flows) + ends


def _compute_layout(bpmn, lane_assignment):
    shapes      = {}
    pool_shapes = {}

    non_boundary = [e for e in bpmn.elements if e.type != "boundaryEvent"]
    order  = _topo_sort([e.id for e in non_boundary], bpmn.flows)
    el_map = {e.id: e for e in bpmn.elements}

    if bpmn.pools:
        pool = bpmn.pools[0]

        # Group ordered elements by lane
        lane_order = {lane.id: [] for lane in pool.lanes}
        for eid in order:
            lid = lane_assignment.get(eid)
            if lid and lid in lane_order:
                lane_order[lid].append(eid)
            elif pool.lanes:
                lane_order[pool.lanes[0].id].append(eid)

        # Re-sort each lane: startEvents first, endEvents last
        for lane in pool.lanes:
            lane_order[lane.id] = _sort_lane_elements(
                lane_order[lane.id], el_map, bpmn.flows
            )

        # Lane heights
        lane_h = {}
        for lane in pool.lanes:
            els_in_lane = [el_map[eid] for eid in lane_order[lane.id] if eid in el_map]
            max_h = max((_el_size(e)[1] for e in els_in_lane), default=TASK_H)
            lane_h[lane.id] = max(MIN_LANE_H, max_h + V_PAD * 2)

        total_h = sum(lane_h[l.id] for l in pool.lanes)

        # Compute pool width
        pool_w = 700
        for lane in pool.lanes:
            els = lane_order[lane.id]
            if els:
                w = POOL_HEADER_W + LANE_HEADER_W + FIRST_X
                for eid in els:
                    if eid in el_map:
                        ew, _ = _el_size(el_map[eid])
                        w += ew + H_GAP
                w += FIRST_X  # trailing margin
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

    return shapes, pool_shapes


# ── DI builder ────────────────────────────────────────────────────────────────

def _wp(edge, x, y):
    wp = _sub(edge, DDI + "waypoint")
    wp.set("x", str(int(x)))
    wp.set("y", str(int(y)))


def _valid(coords):
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

    lane_ids = set()
    for pool in bpmn.pools:
        for lane in pool.lanes:
            lane_ids.add(lane.id)

    # Pool / lane shapes
    for eid, (x, y, w, h) in pool_shapes.items():
        is_lane = eid in lane_ids
        shape = _sub(plane, DI + "BPMNShape",
                     {"id": eid + "_di", "bpmnElement": eid, "isHorizontal": "true"})
        b = _sub(shape, DC + "Bounds")
        b.set("x", str(int(x))); b.set("y", str(int(y)))
        b.set("width", str(int(w))); b.set("height", str(int(h)))

        if is_lane:
            lbl = _sub(shape, DI + "BPMNLabel")
            lb  = _sub(lbl, DC + "Bounds")
            lb.set("x",      str(int(x + 10)))
            lb.set("y",      str(int(y + 10)))
            lb.set("width",  str(LANE_HEADER_W - 20))
            lb.set("height", str(int(h - 20)))

    # Element shapes
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

    # Edges
    for flow in bpmn.flows:
        src_coords = shapes.get(flow.source)
        tgt_coords = shapes.get(flow.target)

        if not src_coords or not tgt_coords:
            continue
        if not _valid(src_coords) or not _valid(tgt_coords):
            continue

        edge = _sub(plane, DI + "BPMNEdge",
                    {"id": flow.id + "_di", "bpmnElement": flow.id})
        sx, sy, sw, sh = src_coords
        tx, ty, tw, th = tgt_coords
        _wp(edge, sx + sw,  sy + sh / 2)  # source right-centre
        _wp(edge, tx,       ty + th / 2)  # target left-centre

        if flow.name:
            mid_x = int((sx + sw + tx) / 2) - 30
            mid_y = int((sy + sh / 2 + ty + th / 2) / 2) - 16
            lbl = _sub(edge, DI + "BPMNLabel")
            _sub(lbl, DC + "Bounds", {
                "x": str(mid_x), "y": str(mid_y),
                "width": "60", "height": "20",
            })


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

    # Lane set — rebuilt from resolved assignment
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

    # Collaboration
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
    """HTML with bpmn-js viewer. Pan/zoom via manual CSS transform (Streamlit iframe safe)."""
    xml    = generate_bpmn_xml(bpmn)
    xml_js = xml.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")

    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body, html {{ width:100%; height:100%; overflow:hidden; background:#f8fafc; user-select:none; }}

    /* Manual pan/zoom wrapper — bpmn-js renders inside, we transform the wrapper */
    #viewport {{
      position: absolute; top:0; left:0;
      transform-origin: 0 0;
      cursor: grab;
    }}
    #viewport.grabbing {{ cursor: grabbing; }}

    /* bpmn-js container — large canvas, content is clipped by body overflow:hidden */
    #bpmn-container {{
      position: relative;
      width: 4000px;
      height: 3000px;
    }}

    /* Suppress bpmn-js built-in overlays that interfere with our pan */
    .djs-overlay-container {{ pointer-events: none !important; }}

    #toolbar {{
      position: fixed; bottom: 16px; left: 50%; transform: translateX(-50%);
      display: flex; align-items: center; gap: 4px;
      background: rgba(15,23,42,0.92); backdrop-filter: blur(12px);
      border-radius: 12px; padding: 6px 10px;
      box-shadow: 0 4px 24px rgba(0,0,0,0.3); z-index: 100;
    }}
    .tb-btn {{
      width:32px; height:32px; border:none; background:transparent;
      color:#94a3b8; border-radius:6px; cursor:pointer; font-size:16px;
      display:flex; align-items:center; justify-content:center;
      transition: background 0.15s, color 0.15s;
    }}
    .tb-btn:hover {{ background: rgba(255,255,255,0.1); color:#e2e8f0; }}
    .tb-divider {{ width:1px; height:20px; background:rgba(255,255,255,0.12); margin:0 2px; }}
    #zoom-label {{ color:#64748b; font-size:11px; font-family:monospace; min-width:40px; text-align:center; }}

    #loading {{
      position:fixed; top:50%; left:50%; transform:translate(-50%,-50%);
      background:white; padding:12px 24px; border-radius:8px;
      box-shadow:0 2px 8px rgba(0,0,0,0.1); color:#64748b; z-index:200;
    }}
    #err {{
      display:none; position:fixed; top:16px; left:50%; transform:translateX(-50%);
      background:white; border:1px solid #fca5a5; border-radius:8px;
      padding:16px 24px; max-width:600px; font-family:monospace; font-size:12px;
      color:#dc2626; box-shadow:0 4px 24px rgba(0,0,0,0.15); z-index:300;
    }}
  </style>
  <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17/dist/assets/bpmn-js.css">
  <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17/dist/assets/diagram-js.css">
  <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17/dist/assets/bpmn-font/css/bpmn-embedded.css">
</head>
<body>
<div id="loading">Carregando diagrama...</div>
<div id="viewport">
  <div id="bpmn-container"></div>
</div>
<div id="toolbar">
  <button class="tb-btn" id="btn-out"   title="Zoom out">&#8722;</button>
  <span   id="zoom-label">100%</span>
  <button class="tb-btn" id="btn-in"    title="Zoom in">&#43;</button>
  <div class="tb-divider"></div>
  <button class="tb-btn" id="btn-fit"   title="Fit to screen">&#8862;</button>
  <button class="tb-btn" id="btn-reset" title="Reset view">&#8634;</button>
</div>
<div id="err"></div>

<script src="https://unpkg.com/bpmn-js@17/dist/bpmn-viewer.development.js"></script>
<script>
(function() {{
  const xml     = `{xml_js}`;
  const errDiv  = document.getElementById('err');
  const loading = document.getElementById('loading');
  const vp      = document.getElementById('viewport');
  const zoomLbl = document.getElementById('zoom-label');

  // ── Pan/zoom state ──────────────────────────────────────────────────────
  let scale = 1, tx = 0, ty = 0;
  let dragging = false, startX, startY, startTx, startTy;
  let lastDist = null, touchTx, touchTy;

  function apply() {{
    vp.style.transform = `translate(${{tx}}px,${{ty}}px) scale(${{scale}})`;
    zoomLbl.textContent = Math.round(scale * 100) + '%';
  }}

  function clamp(s) {{ return Math.min(Math.max(s, 0.05), 8); }}

  function zoomTo(ns, cx, cy) {{
    const r = ns / scale;
    tx = cx - r * (cx - tx);
    ty = cy - r * (cy - ty);
    scale = clamp(ns);
    apply();
  }}

  function fitToScreen() {{
    const svg = document.querySelector('#bpmn-container svg');
    if (!svg) return;
    // Prefer viewBox (actual BPMN content bounds) over getBoundingClientRect
    const vb = svg.viewBox && svg.viewBox.baseVal;
    let sw, sh;
    if (vb && vb.width > 10 && vb.height > 10) {{
      sw = vb.width; sh = vb.height;
    }} else {{
      sw = parseFloat(svg.getAttribute('width'))  || 800;
      sh = parseFloat(svg.getAttribute('height')) || 600;
    }}
    if (!sw || !sh || sw < 10) return;
    const W = window.innerWidth, H = window.innerHeight - 60;
    const ns = clamp(Math.min((W - 40) / sw, (H - 40) / sh));
    if (!isFinite(ns) || ns <= 0) return;
    scale = ns;
    tx = (W - sw * scale) / 2;
    ty = Math.max(10, (H - sh * scale) / 2);
    apply();
  }}

  function fitWhenReady(n) {{
    const svg = document.querySelector('#bpmn-container svg');
    const vb  = svg && svg.viewBox && svg.viewBox.baseVal;
    if (vb && vb.width > 10) {{ fitToScreen(); }}
    else if (n > 0) {{ setTimeout(() => fitWhenReady(n - 1), 300); }}
  }}

  // ── Mouse pan ───────────────────────────────────────────────────────────
  vp.addEventListener('mousedown', e => {{
    if (e.button !== 0) return;
    dragging = true; startX = e.clientX; startY = e.clientY;
    startTx = tx; startTy = ty;
    vp.classList.add('grabbing');
    e.preventDefault();
  }});
  window.addEventListener('mousemove', e => {{
    if (!dragging) return;
    tx = startTx + e.clientX - startX;
    ty = startTy + e.clientY - startY;
    apply();
  }});
  window.addEventListener('mouseup', () => {{
    dragging = false; vp.classList.remove('grabbing');
  }});

  // ── Wheel zoom ──────────────────────────────────────────────────────────
  window.addEventListener('wheel', e => {{
    e.preventDefault();
    zoomTo(scale * (e.deltaY > 0 ? 0.9 : 1.1), e.clientX, e.clientY);
  }}, {{ passive: false }});

  // ── Touch ───────────────────────────────────────────────────────────────
  vp.addEventListener('touchstart', e => {{
    if (e.touches.length === 1) {{
      startX = e.touches[0].clientX; startY = e.touches[0].clientY;
      touchTx = tx; touchTy = ty;
    }}
    if (e.touches.length === 2) {{
      lastDist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
    }}
  }}, {{ passive: true }});

  vp.addEventListener('touchmove', e => {{
    if (e.touches.length === 1) {{
      tx = touchTx + e.touches[0].clientX - startX;
      ty = touchTy + e.touches[0].clientY - startY;
      apply();
    }}
    if (e.touches.length === 2) {{
      const d  = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      const mx = (e.touches[0].clientX + e.touches[1].clientX) / 2;
      const my = (e.touches[0].clientY + e.touches[1].clientY) / 2;
      if (lastDist) zoomTo(scale * d / lastDist, mx, my);
      lastDist = d;
    }}
    e.preventDefault();
  }}, {{ passive: false }});

  vp.addEventListener('touchend', () => {{ lastDist = null; }});

  // ── Keyboard shortcuts ──────────────────────────────────────────────────
  window.addEventListener('keydown', e => {{
    const cx = window.innerWidth / 2, cy = window.innerHeight / 2;
    if (e.key === '+' || e.key === '=') zoomTo(scale * 1.15, cx, cy);
    if (e.key === '-')                  zoomTo(scale * 0.87, cx, cy);
    if (e.key === '0')                  fitToScreen();
    if (e.key === 'r' || e.key === 'R') {{ scale=1; tx=0; ty=0; apply(); }}
  }});

  // ── Toolbar buttons ─────────────────────────────────────────────────────
  const cx = () => window.innerWidth / 2, cy = () => window.innerHeight / 2;
  document.getElementById('btn-in').onclick    = () => zoomTo(scale * 1.2, cx(), cy());
  document.getElementById('btn-out').onclick   = () => zoomTo(scale * 0.8, cx(), cy());
  document.getElementById('btn-fit').onclick   = fitToScreen;
  document.getElementById('btn-reset').onclick = () => {{ scale=1; tx=0; ty=0; apply(); }};

  // ── Mount bpmn-js — disable its own scroll/keyboard (we own those) ──────
  const viewer = new BpmnJS({{
    container: '#bpmn-container',
    keyboard: {{ bindTo: null }},
  }});

  viewer.importXML(xml)
    .then(() => {{
      loading.style.display = 'none';
      // Disable bpmn-js built-in zoom scroll — our wheel handler takes over
      try {{ viewer.get('zoomScroll')._enabled = false; }} catch(_) {{}}
      // Fit after viewBox is populated
      setTimeout(() => fitWhenReady(10), 400);
    }})
    .catch(err => {{
      loading.style.display = 'none';
      errDiv.style.display  = 'block';
      errDiv.innerHTML = '<b>BPMN render error:</b><br>' + err.message;
    }});
}})();
</script>
</body>
</html>"""
