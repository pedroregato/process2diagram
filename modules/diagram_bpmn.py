# modules/diagram_bpmn.py
# BPMN 2.0 XML generator + bpmn-js preview
# Compatible with: Camunda Modeler, Bizagi, draw.io, bpmn.io, Signavio

import xml.etree.ElementTree as ET
from modules.schema import BpmnProcess, BpmnElement, BpmnLane, BpmnPool, SequenceFlow
from collections import defaultdict, deque
import math

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
V_GAP             = 40
LANE_HEADER_W     = 120
POOL_HEADER_W     = 100
FIRST_X           = 100
MIN_LANE_H        = 200
LANE_PADDING_X    = 40
LANE_PADDING_Y    = 30

# Element type categories
EVENT_TYPES = {"startEvent", "endEvent", "intermediateThrowEvent", 
               "intermediateCatchEvent", "boundaryEvent"}
GATEWAY_TYPES = {"exclusiveGateway", "inclusiveGateway", "parallelGateway", 
                 "eventBasedGateway", "complexGateway"}


def _sub(parent, tag, attribs=None):
    """Create subelement with optional attributes."""
    return ET.SubElement(parent, tag, attribs or {})


def _ev_def(etype):
    """Map event type to BPMN definition element."""
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
    """Get element dimensions based on type."""
    t = el.type
    if t in EVENT_TYPES:
        return EV_W, EV_H
    if t in GATEWAY_TYPES:
        return GW_W, GW_H
    return TASK_W, TASK_H


def _is_start_event(el):
    """Check if element is a start event."""
    return el.type == "startEvent"


def _is_end_event(el):
    """Check if element is an end event."""
    return el.type == "endEvent"


def _build_el(parent, el):
    """Build BPMN element XML."""
    t = el.type
    
    # Eventos
    if t in ("startEvent", "endEvent", "intermediateThrowEvent", "intermediateCatchEvent"):
        node = _sub(parent, B + t, {"id": el.id, "name": el.name})
        d = _ev_def(el.event_type)
        if d:
            _sub(node, B + d, {"id": el.id + "_def"})

    # Boundary events
    elif t == "boundaryEvent":
        attrs = {
            "id": el.id, 
            "name": el.name,
            "attachedToRef": el.attached_to or "",
            "cancelActivity": str(el.is_interrupting).lower(),
        }
        node = _sub(parent, B + "boundaryEvent", attrs)
        d = _ev_def(el.event_type)
        if d:
            _sub(node, B + d, {"id": el.id + "_def"})

    # Gateways
    elif "Gateway" in t:
        _sub(parent, B + t, {"id": el.id, "name": el.name})

    # Subprocesses
    elif t == "subProcess":
        node = _sub(parent, B + "subProcess",
                    {"id": el.id, "name": el.name, "triggeredByEvent": "false"})
        for child in el.children:
            _build_el(node, child)

    # Call activities
    elif t == "callActivity":
        attrs = {"id": el.id, "name": el.name}
        if el.called_element:
            attrs["calledElement"] = el.called_element
        _sub(parent, B + "callActivity", attrs)

    # Tasks
    else:
        tag = t if t in ("userTask", "serviceTask", "scriptTask", "sendTask",
                         "receiveTask", "manualTask", "businessRuleTask") else "task"
        node = _sub(parent, B + tag, {"id": el.id, "name": el.name})
        
        # Loop characteristics
        if el.is_loop:
            _sub(node, B + "standardLoopCharacteristics", {"id": el.id + "_loop"})
        elif el.is_parallel_multi:
            mi = _sub(node, B + "multiInstanceLoopCharacteristics", {"id": el.id + "_mi"})
            mi.set("isSequential", "false")
        elif el.is_sequential_multi:
            mi = _sub(node, B + "multiInstanceLoopCharacteristics", {"id": el.id + "_mi"})
            mi.set("isSequential", "true")

    # Documentation
    if el.documentation:
        kids = list(parent)
        if kids:
            _sub(kids[-1], B + "documentation", {}).text = el.documentation


def _build_flow(parent, flow):
    """Build sequence flow XML."""
    node = _sub(parent, B + "sequenceFlow", {
        "id": flow.id, 
        "name": flow.name,
        "sourceRef": flow.source, 
        "targetRef": flow.target,
    })
    if flow.condition:
        c = _sub(node, B + "conditionExpression",
                 {"{%s}type" % _NS["xsi"]: "tFormalExpression"})
        c.text = flow.condition


def _assign_lanes(bpmn):
    """
    Assign elements to lanes based on various rules.
    Returns dict {element_id: lane_id}
    """
    if not bpmn.pools or not bpmn.pools[0].lanes:
        return {}

    pool = bpmn.pools[0]
    if not pool.lanes:
        return {}

    assignment = {}
    lane_by_name = {lane.name: lane.id for lane in pool.lanes}
    lane_by_id = {lane.id: lane for lane in pool.lanes}

    # Step 1: Explicit assignment from lane.element_ids
    for lane in pool.lanes:
        for eid in lane.element_ids:
            if eid:  # Ensure not empty
                assignment[eid] = lane.id

    # Step 2: Match by actor/lane name on element
    for el in bpmn.elements:
        if el.type == "boundaryEvent" or el.id in assignment:
            continue
        actor = el.actor or el.lane
        if actor and actor in lane_by_name:
            assignment[el.id] = lane_by_name[actor]

    # Build flow graph for propagation
    flow_graph = defaultdict(list)
    reverse_graph = defaultdict(list)
    for flow in bpmn.flows:
        flow_graph[flow.source].append(flow.target)
        reverse_graph[flow.target].append(flow.source)

    # Step 3: Propagate assignments through flows
    unassigned = {e.id for e in bpmn.elements 
                  if e.type != "boundaryEvent" and e.id not in assignment}
    
    # BFS propagation
    queue = deque(assignment.keys())
    while queue:
        current = queue.popleft()
        current_lane = assignment.get(current)
        if not current_lane:
            continue
            
        # Forward propagation
        for target in flow_graph.get(current, []):
            if target not in assignment and target in unassigned:
                assignment[target] = current_lane
                unassigned.discard(target)
                queue.append(target)
        
        # Backward propagation
        for source in reverse_graph.get(current, []):
            if source not in assignment and source in unassigned:
                assignment[source] = current_lane
                unassigned.discard(source)
                queue.append(source)

    # Step 4: Fallback to first lane for any remaining elements
    if unassigned and pool.lanes:
        fallback_lane = pool.lanes[0].id
        for eid in unassigned:
            assignment[eid] = fallback_lane
            print(f"DEBUG: Assigned {eid} to fallback lane {fallback_lane}")

    # Debug output
    print(f"DEBUG: Total assignments: {len(assignment)}")
    for lane in pool.lanes:
        lane_elements = [eid for eid, lid in assignment.items() if lid == lane.id]
        print(f"DEBUG: Lane '{lane.name}' has {len(lane_elements)} elements: {lane_elements}")

    return assignment


def _compute_layout(bpmn, lane_assignment):
    """Compute positions for all elements."""
    shapes = {}
    pool_shapes = {}
    
    # Filter out boundary events for main layout
    non_boundary = [e for e in bpmn.elements if e.type != "boundaryEvent"]
    el_map = {e.id: e for e in bpmn.elements}
    
    if bpmn.pools and bpmn.pools[0].lanes:
        pool = bpmn.pools[0]
        
        # Group elements by lane
        lane_elements = defaultdict(list)
        for eid, lid in lane_assignment.items():
            if eid in el_map:
                lane_elements[lid].append(eid)
        
        # Calculate lane heights based on content
        lane_heights = {}
        for lane in pool.lanes:
            elements = lane_elements.get(lane.id, [])
            if elements:
                # Find tallest element in this lane
                max_h = max((_el_size(el_map[eid])[1] for eid in elements), default=TASK_H)
                # Add padding
                lane_heights[lane.id] = max(MIN_LANE_H, max_h + LANE_PADDING_Y * 2)
            else:
                lane_heights[lane.id] = MIN_LANE_H
        
        total_h = sum(lane_heights[l.id] for l in pool.lanes)
        
        # Calculate pool width based on maximum row width
        pool_w = 800  # minimum width
        for lane in pool.lanes:
            elements = lane_elements.get(lane.id, [])
            if elements:
                # Calculate total width needed for this lane
                total_width = LANE_PADDING_X * 2
                for eid in elements:
                    w, _ = _el_size(el_map[eid])
                    total_width += w + H_GAP
                total_width += POOL_HEADER_W + LANE_HEADER_W
                pool_w = max(pool_w, total_width)
        
        # Create pool shape
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
                    # Center vertically in lane
                    y_pos = cur_y + (lh - h) / 2
                    shapes[el.id] = (int(cur_x), int(y_pos), w, h)
                    cur_x += w + H_GAP
            
            cur_y += lh
    
    else:
        # Flat layout (no pools/lanes)
        # Simple vertical stacking
        cur_y = V_GAP
        for e in non_boundary:
            w, h = _el_size(e)
            shapes[e.id] = (FIRST_X, int(cur_y), w, h)
            cur_y += h + V_GAP
    
    # Position boundary events (attached to their host)
    for el in bpmn.elements:
        if el.type == "boundaryEvent" and el.attached_to:
            host = shapes.get(el.attached_to)
            if host:
                hx, hy, hw, hh = host
                # Position at bottom center of host
                shapes[el.id] = (
                    hx + (hw - EV_W) // 2,
                    hy + hh - EV_H // 2,
                    EV_W, EV_H
                )
    
    return shapes, pool_shapes


def _wp(edge, x, y):
    """Add waypoint to edge."""
    wp = _sub(edge, DDI + "waypoint")
    wp.set("x", str(int(x)))
    wp.set("y", str(int(y)))


def _valid(coords):
    """Check if coordinates are valid numbers."""
    try:
        return all(
            isinstance(v, (int, float)) and 
            math.isfinite(v) and 
            v >= 0
            for v in coords
        )
    except Exception:
        return False


def _build_di(diagram, plane_ref, shapes, pool_shapes, bpmn):
    """Build diagram interchange (layout)."""
    plane = _sub(diagram, DI + "BPMNPlane",
                 {"id": "plane_1", "bpmnElement": plane_ref})
    
    # Collect lane IDs for identification
    lane_ids = set()
    for pool in bpmn.pools:
        for lane in pool.lanes:
            lane_ids.add(lane.id)
    
    # Draw pools and lanes
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
            # Lane label - positioned vertically in the header
            lbl = _sub(shape, DI + "BPMNLabel")
            lb = _sub(lbl, DC + "Bounds")
            # Position in the lane header, centered vertically
            lb.set("x", str(int(x + 10)))
            lb.set("y", str(int(y + 10)))
            lb.set("width", str(LANE_HEADER_W - 20))
            lb.set("height", str(int(h - 20)))
    
    # Draw flow elements (tasks, events, gateways)
    for el in bpmn.elements:
        if el.id not in shapes:
            continue
        coords = shapes.get(el.id)
        if not _valid(coords):
            continue
        x, y, w, h = coords
        
        shape = _sub(plane, DI + "BPMNShape", 
                    {"id": el.id + "_di", "bpmnElement": el.id})
        b = _sub(shape, DC + "Bounds")
        b.set("x", str(int(x)))
        b.set("y", str(int(y)))
        b.set("width", str(int(w)))
        b.set("height", str(int(h)))
        
        # Element label
        lbl = _sub(shape, DI + "BPMNLabel")
        lb = _sub(lbl, DC + "Bounds")
        lb.set("x", str(int(x)))
        lb.set("y", str(int(y + h + 2)))
        lb.set("width", str(int(w)))
        lb.set("height", "20")
    
    # Draw sequence flows
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
        
        # Simple straight line from source right side to target left side
        _wp(edge, sx + sw, sy + sh/2)  # Source right-center
        _wp(edge, tx, ty + th/2)        # Target left-center
        
        # Flow label
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
    """Generate complete BPMN 2.0 XML."""
    # Create root definitions element
    defs = ET.Element(B + "definitions", {
        "xmlns": _NS["bpmn"],
        "xmlns:bpmndi": _NS["bpmndi"],
        "xmlns:dc": _NS["dc"],
        "xmlns:di": _NS["di"],
        "xmlns:xsi": _NS["xsi"],
        "targetNamespace": "http://process2diagram.io/bpmn",
        "id": "definitions_1",
        "exporter": "Process2Diagram",
        "exporterVersion": "2.0",
    })
    
    # Create process
    process_id = "process_1"
    proc = _sub(defs, B + "process", {
        "id": process_id, 
        "name": bpmn.name,
        "isExecutable": "false", 
        "processType": "None",
    })
    
    # Process documentation
    if bpmn.documentation:
        _sub(proc, B + "documentation", {}).text = bpmn.documentation
    
    # Assign elements to lanes
    lane_assignment = _assign_lanes(bpmn)
    
    # Create lane set if pools exist
    if bpmn.pools and bpmn.pools[0].lanes:
        pool = bpmn.pools[0]
        lset = _sub(proc, B + "laneSet", {"id": pool.id + "_lset"})
        
        # Group elements by lane
        lane_members = defaultdict(list)
        for eid, lid in lane_assignment.items():
            lane_members[lid].append(eid)
        
        # Create lane elements
        for lane in pool.lanes:
            ln = _sub(lset, B + "lane", {"id": lane.id, "name": lane.name})
            # Add flow node references
            for eid in sorted(lane_members.get(lane.id, [])):
                _sub(ln, B + "flowNodeRef", {}).text = eid
    
    # Add all flow elements
    for el in bpmn.elements:
        _build_el(proc, el)
    
    # Add all sequence flows
    for flow in bpmn.flows:
        _build_flow(proc, flow)
    
    # Create collaboration if pools exist
    collab_id = None
    if bpmn.pools:
        pool = bpmn.pools[0]
        collab_id = "collab_1"
        collab = _sub(defs, B + "collaboration", {"id": collab_id})
        _sub(collab, B + "participant",
             {"id": pool.id, "name": pool.name, "processRef": process_id})
    
    # Calculate layout
    shapes, pool_shapes = _compute_layout(bpmn, lane_assignment)
    
    # Create diagram
    plane_ref = collab_id if collab_id else process_id
    diagram = _sub(defs, DI + "BPMNDiagram", {"id": "diagram_1"})
    _build_di(diagram, plane_ref, shapes, pool_shapes, bpmn)
    
    # Return formatted XML
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + \
           ET.tostring(defs, encoding="unicode")


def generate_bpmn_preview(bpmn: BpmnProcess) -> str:
    """Generate HTML with embedded bpmn-js viewer."""
    xml = generate_bpmn_xml(bpmn)
    # Escape for JavaScript string
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
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    }}
    
    #bpmn-container {{
      width: 100%;
      height: 100%;
      position: relative;
    }}
    
    /* Toolbar styling */
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
      border: 1px solid rgba(255, 255, 255, 0.1);
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
      transition: all 0.2s ease;
      display: flex;
      align-items: center;
      justify-content: center;
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
      font-family: 'JetBrains Mono', monospace;
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
    
    #loading {{
      position: fixed;
      top: 50%;
      left: 50%;
      transform: translate(-50%, -50%);
      background: white;
      padding: 12px 24px;
      border-radius: 8px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      color: #64748b;
      z-index: 1500;
    }}
  </style>
  
  <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17.9.1/dist/assets/bpmn-js.css">
  <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17.9.1/dist/assets/diagram-js.css">
  <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17.9.1/dist/assets/bpmn-font/css/bpmn.css">
</head>
<body>
  <div id="loading">Carregando diagrama...</div>
  <div id="bpmn-container"></div>
  
  <div id="toolbar">
    <button class="tb-btn" id="btn-out" title="Zoom out">−</button>
    <span id="zoom-label">100%</span>
    <button class="tb-btn" id="btn-in" title="Zoom in">+</button>
    <div class="tb-divider"></div>
    <button class="tb-btn" id="btn-fit" title="Fit to screen">⤢</button>
    <button class="tb-btn" id="btn-reset" title="Reset view">↺</button>
  </div>
  
  <div id="err"></div>

  <script src="https://unpkg.com/bpmn-js@17.9.1/dist/bpmn-viewer.development.js"></script>
  <script>
    (function() {{
      const loadingEl = document.getElementById('loading');
      const errDiv = document.getElementById('err');
      const zoomLbl = document.getElementById('zoom-label');
      
      // Create viewer
      const viewer = new BpmnJS({{
        container: '#bpmn-container'
      }});
      
      const xml = `{xml_js}`;
      
      // Update zoom label
      function updateZoomLabel() {{
        try {{
          const canvas = viewer.get('canvas');
          const zoom = canvas.zoom();
          zoomLbl.textContent = Math.round(zoom * 100) + '%';
        }} catch (e) {{
          console.warn('Error updating zoom:', e);
        }}
      }}
      
      // Import XML
      viewer.importXML(xml)
        .then(() => {{
          loadingEl.style.display = 'none';
          
          const canvas = viewer.get('canvas');
          const eventBus = viewer.get('eventBus');
          
          // Listen for viewbox changes
          eventBus.on('canvas.viewbox.changed', function() {{
            updateZoomLabel();
          }});
          
          // Button handlers
          document.getElementById('btn-in').addEventListener('click', () => {{
            canvas.zoom(1.2);
            updateZoomLabel();
          }});
          
          document.getElementById('btn-out').addEventListener('click', () => {{
            canvas.zoom(0.8);
            updateZoomLabel();
          }});
          
          document.getElementById('btn-fit').addEventListener('click', () => {{
            canvas.zoom('fit-viewport');
            updateZoomLabel();
          }});
          
          document.getElementById('btn-reset').addEventListener('click', () => {{
            canvas.zoom(1);
            canvas.scroll({{ dx: 0, dy: 0 }});
            updateZoomLabel();
          }});
          
          // Initial fit to viewport
          setTimeout(() => {{
            canvas.zoom('fit-viewport');
            updateZoomLabel();
          }}, 300);
        }})
        .catch(err => {{
          loadingEl.style.display = 'none';
          errDiv.style.display = 'block';
          errDiv.innerHTML = '<b>Error:</b> ' + err.message;
          console.error('BPMN import error:', err);
        }});
    }})();
  </script>
</body>
</html>"""
