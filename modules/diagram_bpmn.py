# modules/diagram_bpmn.py
# BPMN 2.0 XML generator + bpmn-js preview
# Compatible with: Camunda Modeler, Bizagi, draw.io, bpmn.io, Signavio

import xml.etree.ElementTree as ET
from modules.schema import BpmnProcess, BpmnElement, BpmnLane, BpmnPool, SequenceFlow
from collections import defaultdict, deque

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
TASK_W,  TASK_H   = 120, 72
GW_W,    GW_H     = 50,  50
EV_W,    EV_H     = 36,  36
H_GAP             = 80
LANE_HEADER_W     = 120
POOL_HEADER_W     = 100
FIRST_X           = 100
MIN_LANE_H        = 200
LANE_PADDING_X    = 40

# Element type categories
EVENT_TYPES = {"startEvent", "endEvent", "intermediateThrowEvent", 
               "intermediateCatchEvent", "boundaryEvent"}
GATEWAY_TYPES = {"exclusiveGateway", "inclusiveGateway", "parallelGateway", 
                 "eventBasedGateway", "complexGateway"}


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
    if t in EVENT_TYPES:
        return EV_W, EV_H
    if t in GATEWAY_TYPES:
        return GW_W, GW_H
    return TASK_W, TASK_H


def _build_el(parent, el):
    """Build BPMN element XML."""
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
    """Build sequence flow XML."""
    node = _sub(parent, B + "sequenceFlow", {
        "id": flow.id, "name": flow.name,
        "sourceRef": flow.source, "targetRef": flow.target,
    })
    if flow.condition:
        c = _sub(node, B + "conditionExpression",
                 {"{%s}type" % _NS["xsi"]: "tFormalExpression"})
        c.text = flow.condition


def _assign_lanes(bpmn):
    """
    Returns a dict {element_id: lane_id} for every non-boundary element.
    """
    if not bpmn.pools or not bpmn.pools[0].lanes:
        return {}

    pool = bpmn.pools[0]
    if not pool.lanes:
        return {}

    assignment = {}
    lane_by_name = {lane.name: lane.id for lane in pool.lanes}

    # Step 1 — explicit element_ids in lane definition
    for lane in pool.lanes:
        for eid in lane.element_ids:
            assignment[eid] = lane.id

    # Step 2 — match by actor/lane name
    for el in bpmn.elements:
        if el.type == "boundaryEvent" or el.id in assignment:
            continue
        actor = el.actor or el.lane
        if actor and actor in lane_by_name:
            assignment[el.id] = lane_by_name[actor]

    # Build flow graph
    flow_graph = defaultdict(list)
    reverse_graph = defaultdict(list)
    for flow in bpmn.flows:
        flow_graph[flow.source].append(flow.target)
        reverse_graph[flow.target].append(flow.source)

    # Propagate assignments
    unassigned = {e.id for e in bpmn.elements 
                  if e.type != "boundaryEvent" and e.id not in assignment}
    
    queue = deque(assignment.keys())
    while queue:
        current = queue.popleft()
        current_lane = assignment[current]
        
        for target in flow_graph[current]:
            if target not in assignment and target in unassigned:
                assignment[target] = current_lane
                unassigned.discard(target)
                queue.append(target)
        
        for source in reverse_graph[current]:
            if source not in assignment and source in unassigned:
                assignment[source] = current_lane
                unassigned.discard(source)
                queue.append(source)

    # Fallback to first lane
    if unassigned and pool.lanes:
        fallback_lane = pool.lanes[0].id
        for eid in unassigned:
            assignment[eid] = fallback_lane

    return assignment


def _compute_layout(bpmn, lane_assignment):
    """Compute positions for all elements."""
    shapes = {}
    pool_shapes = {}
    
    non_boundary = [e for e in bpmn.elements if e.type != "boundaryEvent"]
    el_map = {e.id: e for e in bpmn.elements}
    
    if bpmn.pools and bpmn.pools[0].lanes:
        pool = bpmn.pools[0]
        
        # Group elements by lane
        lane_elements = defaultdict(list)
        for eid, lid in lane_assignment.items():
            if eid in el_map:
                lane_elements[lid].append(eid)
        
        # Calculate lane heights
        lane_heights = {}
        for lane in pool.lanes:
            elements = lane_elements.get(lane.id, [])
            if elements:
                max_h = max((_el_size(el_map[eid])[1] for eid in elements), default=TASK_H)
                lane_heights[lane.id] = max(MIN_LANE_H, max_h + 40)
            else:
                lane_heights[lane.id] = MIN_LANE_H
        
        total_h = sum(lane_heights[l.id] for l in pool.lanes)
        
        # Calculate pool width
        pool_w = 800
        for lane in pool.lanes:
            elements = lane_elements.get(lane.id, [])
            if elements:
                total_width = LANE_PADDING_X * 2
                for eid in elements:
                    w, _ = _el_size(el_map[eid])
                    total_width += w + H_GAP
                total_width += POOL_HEADER_W + LANE_HEADER_W
                pool_w = max(pool_w, total_width)
        
        pool_shapes[pool.id] = (0, 0, pool_w, total_h)
        
        # Position lanes and elements
        cur_y = 0
        for lane in pool.lanes:
            lh = lane_heights[lane.id]
            lw = pool_w - POOL_HEADER_W
            pool_shapes[lane.id] = (POOL_HEADER_W, cur_y, lw, lh)
            
            # Position elements in this lane
            elements = lane_elements.get(lane.id, [])
            if elements:
                start_x = POOL_HEADER_W + LANE_HEADER_W + LANE_PADDING_X
                cur_x = start_x
                
                for eid in elements:
                    el = el_map[eid]
                    w, h = _el_size(el)
                    y_pos = cur_y + (lh - h) / 2
                    shapes[el.id] = (int(cur_x), int(y_pos), w, h)
                    cur_x += w + H_GAP
            
            cur_y += lh
    
    else:
        # Flat layout
        cur_y = 40
        for e in non_boundary:
            w, h = _el_size(e)
            shapes[e.id] = (FIRST_X, int(cur_y), w, h)
            cur_y += h + 40
    
    # Position boundary events
    for el in bpmn.elements:
        if el.type == "boundaryEvent" and el.attached_to:
            host = shapes.get(el.attached_to)
            if host:
                hx, hy, hw, hh = host
                shapes[el.id] = (
                    hx + (hw - EV_W) // 2,
                    hy + hh - EV_H // 2,
                    EV_W, EV_H
                )
    
    return shapes, pool_shapes


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
    """Build diagram interchange."""
    plane = _sub(diagram, DI + "BPMNPlane",
                 {"id": "plane_1", "bpmnElement": plane_ref})
    
    # Collect lane ids
    lane_ids = set()
    for pool in bpmn.pools:
        for lane in pool.lanes:
            lane_ids.add(lane.id)
    
    # Pool/lane shapes
    for eid, (x, y, w, h) in pool_shapes.items():
        is_lane = eid in lane_ids
        shape = _sub(plane, DI + "BPMNShape",
                     {"id": eid + "_di", "bpmnElement": eid, "isHorizontal": "true"})
        b = _sub(shape, DC + "Bounds")
        b.set("x", str(int(x)))
        b.set("y", str(int(y)))
        b.set("width", str(int(w)))
        b.set("height", str(int(h)))
        
        if is_lane:
            lbl = _sub(shape, DI + "BPMNLabel")
            lb = _sub(lbl, DC + "Bounds")
            lb.set("x", str(int(x + 10)))
            lb.set("y", str(int(y + 10)))
            lb.set("width", str(LANE_HEADER_W - 20))
            lb.set("height", str(int(h - 20)))
    
    # Element shapes
    for el in bpmn.elements:
        if el.id not in shapes:
            continue
        coords = shapes.get(el.id)
        if not _valid(coords):
            continue
        x, y, w, h = coords
        
        shape = _sub(plane, DI + "BPMNShape", {"id": el.id + "_di", "bpmnElement": el.id})
        b = _sub(shape, DC + "Bounds")
        b.set("x", str(int(x)))
        b.set("y", str(int(y)))
        b.set("width", str(int(w)))
        b.set("height", str(int(h)))
        
        lbl = _sub(shape, DI + "BPMNLabel")
        lb = _sub(lbl, DC + "Bounds")
        lb.set("x", str(int(x)))
        lb.set("y", str(int(y + h + 2)))
        lb.set("width", str(int(w)))
        lb.set("height", "20")
    
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
        
        _wp(edge, sx + sw, sy + sh/2)
        _wp(edge, tx, ty + th/2)
        
        if flow.name:
            mid_x = int((sx + sw + tx) / 2)
            mid_y = int((sy + sh/2 + ty + th/2) / 2) - 10
            lbl = _sub(edge, DI + "BPMNLabel")
            _sub(lbl, DC + "Bounds", {
                "x": str(mid_x - 30),
                "y": str(mid_y),
                "width": "60",
                "height": "20",
            })


def generate_bpmn_xml(bpmn: BpmnProcess) -> str:
    """Generate BPMN 2.0 XML."""
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
    
    # Lane set
    if bpmn.pools and bpmn.pools[0].lanes:
        pool = bpmn.pools[0]
        lset = _sub(proc, B + "laneSet", {"id": pool.id + "_lset"})
        
        lane_members = defaultdict(list)
        for eid, lid in lane_assignment.items():
            lane_members[lid].append(eid)
        
        for lane in pool.lanes:
            ln = _sub(lset, B + "lane", {"id": lane.id, "name": lane.name})
            for eid in sorted(lane_members.get(lane.id, [])):
                _sub(ln, B + "flowNodeRef", {}).text = eid
    
    # Elements and flows
    for el in bpmn.elements:
        _build_el(proc, el)
    for flow in bpmn.flows:
        _build_flow(proc, flow)
    
    # Collaboration
    collab_id = None
    if bpmn.pools:
        pool = bpmn.pools[0]
        collab_id = "collab_1"
        collab = _sub(defs, B + "collaboration", {"id": collab_id})
        _sub(collab, B + "participant",
             {"id": pool.id, "name": pool.name, "processRef": process_id})
    
    # Diagram interchange
    shapes, pool_shapes = _compute_layout(bpmn, lane_assignment)
    plane_ref = collab_id if collab_id else process_id
    diagram = _sub(defs, DI + "BPMNDiagram", {"id": "diagram_1"})
    _build_di(diagram, plane_ref, shapes, pool_shapes, bpmn)
    
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + \
           ET.tostring(defs, encoding="unicode")


def generate_bpmn_preview(bpmn: BpmnProcess) -> str:
    """HTML with bpmn-js viewer."""
    xml = generate_bpmn_xml(bpmn)
    xml_js = xml.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    * {{
      margin: 0;
      padding: 0;
      box-sizing: border-box;
    }}
    
    body, html {{
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: #f8fafc;
    }}
    
    #bpmn-container {{
      width: 100%;
      height: 100%;
      position: relative;
    }}
    
    #toolbar {{
      position: fixed;
      bottom: 24px;
      left: 50%;
      transform: translateX(-50%);
      display: flex;
      align-items: center;
      gap: 4px;
      background: rgba(15, 23, 42, 0.95);
      backdrop-filter: blur(12px);
      border-radius: 14px;
      padding: 8px 12px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
      z-index: 1000;
    }}
    
    .tb-btn {{
      width: 36px;
      height: 36px;
      border: none;
      background: transparent;
      color: #94a3b8;
      border-radius: 8px;
      cursor: pointer;
      font-size: 18px;
    }}
    
    .tb-btn:hover {{
      background: rgba(255, 255, 255, 0.1);
      color: #f1f5f9;
    }}
    
    .tb-divider {{
      width: 1px;
      height: 24px;
      background: rgba(255, 255, 255, 0.15);
      margin: 0 4px;
    }}
    
    #zoom-label {{
      color: #cbd5e1;
      font-size: 12px;
      font-family: monospace;
      min-width: 48px;
      text-align: center;
    }}
    
    #err {{
      display: none;
      position: fixed;
      top: 24px;
      left: 50%;
      transform: translateX(-50%);
      background: white;
      border: 1px solid #fecaca;
      border-radius: 12px;
      padding: 16px 24px;
      color: #dc2626;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
      z-index: 2000;
    }}
  </style>
  
  <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17.9.1/dist/assets/bpmn-js.css">
  <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17.9.1/dist/assets/diagram-js.css">
  <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17.9.1/dist/assets/bpmn-font/css/bpmn.css">
</head>
<body>
  <div id="bpmn-container"></div>
  
  <div id="toolbar">
    <button class="tb-btn" id="btn-out" title="Zoom out">−</button>
    <span id="zoom-label">100%</span>
    <button class="tb-btn" id="btn-in" title="Zoom in">+</button>
    <div class="tb-divider"></div>
    <button class="tb-btn" id="btn-fit" title="Fit to screen">⤢</button>
    <button class="tb-btn" id="btn-reset" title="Reset">↺</button>
  </div>
  
  <div id="err"></div>

  <script src="https://unpkg.com/bpmn-js@17.9.1/dist/bpmn-viewer.development.js"></script>
  <script>
    (function() {{
      const viewer = new BpmnJS({{
        container: '#bpmn-container'
      }});
      
      const xml = `{xml_js}`;
      const errDiv = document.getElementById('err');
      const zoomLbl = document.getElementById('zoom-label');
      
      viewer.importXML(xml)
        .then(() => {{
          const canvas = viewer.get('canvas');
          
          function updateZoom() {{
            zoomLbl.textContent = Math.round(canvas.zoom() * 100) + '%';
          }}
          
          document.getElementById('btn-in').onclick = () => {{
            canvas.zoom(1.2);
            updateZoom();
          }};
          
          document.getElementById('btn-out').onclick = () => {{
            canvas.zoom(0.8);
            updateZoom();
          }};
          
          document.getElementById('btn-fit').onclick = () => {{
            canvas.zoom('fit-viewport');
            updateZoom();
          }};
          
          document.getElementById('btn-reset').onclick = () => {{
            canvas.zoom(1);
            canvas.scroll({{ dx: 0, dy: 0 }});
            updateZoom();
          }};
          
          canvas.on('viewbox.changed', updateZoom);
          setTimeout(() => canvas.zoom('fit-viewport'), 200);
        }})
        .catch(err => {{
          errDiv.style.display = 'block';
          errDiv.innerHTML = '<b>Erro:</b> ' + err.message;
        }});
    }})();
  </script>
</body>
</html>"""
