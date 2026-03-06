# modules/diagram_bpmn.py
# BPMN 2.0 XML generator + bpmn-js preview with enhanced layout
# Compatible with: Camunda Modeler, Bizagi, draw.io, bpmn.io, Signavio

import xml.etree.ElementTree as ET
from modules.schema import BpmnProcess, BpmnElement, BpmnLane, BpmnPool, SequenceFlow
import math
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

# ── Layout constants (optimized) ─────────────────────────────────────────────
TASK_W,  TASK_H   = 120, 72        # Slightly taller for better label fit
GW_W,    GW_H     = 50,  50        # Diamond shape
EV_W,    EV_H     = 36,  36        # Circle
H_GAP             = 80             # Horizontal gap between elements
V_GAP             = 40             # Vertical gap in flat layouts
LANE_HEADER_W     = 120            # Wider for better lane name visibility
POOL_HEADER_W     = 100            # Pool header width
FIRST_X           = 100            # Left margin inside lane
MIN_LANE_H        = 200            # Minimum lane height
LANE_PADDING_Y    = 30             # Vertical padding inside lane
LANE_PADDING_X    = 40             # Horizontal padding at lane ends

# Element type categories for better positioning
EVENT_TYPES = {"startEvent", "endEvent", "intermediateThrowEvent", 
               "intermediateCatchEvent", "boundaryEvent"}
GATEWAY_TYPES = {"exclusiveGateway", "inclusiveGateway", "parallelGateway", 
                 "eventBasedGateway", "complexGateway"}
TASK_TYPES = {"task", "userTask", "serviceTask", "sendTask", "receiveTask",
              "manualTask", "businessRuleTask", "scriptTask", "callActivity"}

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


def _is_start_event(el):
    return el.type == "startEvent"


def _is_end_event(el):
    return el.type == "endEvent"


def _is_gateway(el):
    return el.type in GATEWAY_TYPES


# ── Enhanced lane assignment with better inference ───────────────────────────

def _assign_lanes(bpmn):
    """
    Enhanced lane assignment with better inference and error handling.
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

    # Step 3 — build flow graph for inference
    flow_graph = defaultdict(list)
    reverse_graph = defaultdict(list)
    for flow in bpmn.flows:
        flow_graph[flow.source].append(flow.target)
        reverse_graph[flow.target].append(flow.source)

    # Step 4 — propagate assignments through flows
    unassigned = {e.id for e in bpmn.elements 
                  if e.type != "boundaryEvent" and e.id not in assignment}
    
    # Propagate from assigned to unassigned
    queue = deque(assignment.keys())
    
    while queue:
        current = queue.popleft()
        current_lane = assignment[current]
        
        # Forward propagation
        for target in flow_graph[current]:
            if target not in assignment and target in unassigned:
                assignment[target] = current_lane
                unassigned.discard(target)
                queue.append(target)
        
        # Backward propagation
        for source in reverse_graph[current]:
            if source not in assignment and source in unassigned:
                assignment[source] = current_lane
                unassigned.discard(source)
                queue.append(source)

    # Step 5 — intelligent fallback for remaining elements
    if unassigned:
        # Find most connected lane for each unassigned element
        for eid in list(unassigned):
            # Check all neighbors
            neighbors = set(flow_graph[eid] + reverse_graph[eid])
            assigned_neighbors = [n for n in neighbors if n in assignment]
            
            if assigned_neighbors:
                # Use most common lane among neighbors
                from collections import Counter
                lane_counts = Counter(assignment[n] for n in assigned_neighbors)
                assignment[eid] = lane_counts.most_common(1)[0][0]
                unassigned.discard(eid)

    # Step 6 — final fallback to first lane
    if unassigned and pool.lanes:
        fallback_lane = pool.lanes[0].id
        for eid in unassigned:
            assignment[eid] = fallback_lane

    return assignment


# ── Enhanced layout engine with grid-based positioning ───────────────────────

def _build_element_graph(bpmn):
    """Build enhanced graph representation with level calculation."""
    graph = {}
    reverse_graph = {}
    
    # Initialize
    for el in bpmn.elements:
        if el.type != "boundaryEvent":
            graph[el.id] = []
            reverse_graph[el.id] = []
    
    # Add flows
    for flow in bpmn.flows:
        if flow.source in graph and flow.target in graph:
            graph[flow.source].append(flow.target)
            reverse_graph[flow.target].append(flow.source)
    
    return graph, reverse_graph


def _calculate_element_levels(graph, start_nodes):
    """
    Calculate optimal levels for each element using longest path.
    Returns dict {element_id: level_index}
    """
    levels = {}
    
    # Initialize with start nodes
    queue = deque()
    for node in start_nodes:
        levels[node] = 0
        queue.append(node)
    
    # BFS with level assignment
    while queue:
        current = queue.popleft()
        current_level = levels[current]
        
        for neighbor in graph.get(current, []):
            new_level = current_level + 1
            if neighbor not in levels or new_level > levels[neighbor]:
                levels[neighbor] = new_level
                queue.append(neighbor)
    
    return levels


def _optimize_lane_element_positions(lane_elements, el_map, graph, reverse_graph):
    """
    Optimize element positions within a lane using level-based layout.
    Returns list of (element_id, level, row_index) tuples.
    """
    if not lane_elements:
        return []
    
    # Identify start and end nodes
    start_nodes = [eid for eid in lane_elements 
                   if _is_start_event(el_map[eid]) or not reverse_graph.get(eid)]
    
    # Calculate levels
    levels = _calculate_element_levels(graph, start_nodes)
    
    # Group elements by level
    level_groups = defaultdict(list)
    for eid in lane_elements:
        if eid in levels:
            level = levels[eid]
            level_groups[level].append(eid)
        else:
            # Put unleveled elements at the end
            level_groups[999].append(eid)
    
    # Sort levels
    max_level = max([l for l in level_groups.keys() if l != 999], default=0)
    
    # Distribute elements vertically within lanes if needed (parallel paths)
    # For now, simple single row per level
    positioned = []
    for level in range(max_level + 1):
        elements = level_groups.get(level, [])
        # Sort elements within level for consistent order
        elements.sort(key=lambda eid: (el_map[eid].type, eid))
        for eid in elements:
            positioned.append((eid, level, 0))  # row 0 for now
    
    # Add any remaining elements
    if 999 in level_groups:
        for eid in level_groups[999]:
            positioned.append((eid, max_level + 1, 0))
    
    return positioned


def _compute_layout(bpmn, lane_assignment):
    """Enhanced layout computation with better spacing and positioning."""
    shapes = {}
    pool_shapes = {}
    
    # Filter out boundary events for main layout
    non_boundary = [e for e in bpmn.elements if e.type != "boundaryEvent"]
    el_map = {e.id: e for e in bpmn.elements}
    
    # Build graph
    graph, reverse_graph = _build_element_graph(bpmn)
    
    if bpmn.pools and bpmn.pools[0].lanes:
        pool = bpmn.pools[0]
        
        # Group elements by lane
        lane_elements = defaultdict(list)
        for eid, lid in lane_assignment.items():
            if eid in el_map:
                lane_elements[lid].append(eid)
        
        # Calculate optimal positions for each lane
        lane_positions = {}
        for lane in pool.lanes:
            if lane.id in lane_elements and lane_elements[lane.id]:
                lane_positions[lane.id] = _optimize_lane_element_positions(
                    lane_elements[lane.id], el_map, graph, reverse_graph
                )
            else:
                lane_positions[lane.id] = []
        
        # Calculate lane heights based on content
        lane_heights = {}
        for lane in pool.lanes:
            positions = lane_positions.get(lane.id, [])
            if positions:
                # Group by row (for future multi-row support)
                rows = defaultdict(list)
                for eid, level, row in positions:
                    rows[row].append(eid)
                
                # Calculate height needed
                num_rows = len(rows)
                max_row_height = max((_el_size(el_map[eid])[1] for eid in lane_elements.get(lane.id, [])), default=TASK_H)
                lane_heights[lane.id] = max(
                    MIN_LANE_H,
                    num_rows * (max_row_height + LANE_PADDING_Y * 2)
                )
            else:
                lane_heights[lane.id] = MIN_LANE_H
        
        # Calculate total height
        total_h = sum(lane_heights[l.id] for l in pool.lanes)
        
        # Calculate required width based on maximum level across lanes
        max_levels = {}
        for lid, positions in lane_positions.items():
            if positions:
                max_levels[lid] = max([level for _, level, _ in positions], default=0)
            else:
                max_levels[lid] = 0
        
        # Calculate width needed for each lane
        lane_widths = {}
        for lane in pool.lanes:
            if lane.id in lane_positions and lane_positions[lane.id]:
                max_level = max_levels[lane.id]
                elements_at_level = defaultdict(list)
                for eid, level, _ in lane_positions[lane.id]:
                    elements_at_level[level].append(eid)
                
                # Calculate width needed for each level
                level_widths = []
                for level in range(max_level + 1):
                    elements = elements_at_level.get(level, [])
                    if elements:
                        total_width = (len(elements) - 1) * H_GAP
                        for eid in elements:
                            w, _ = _el_size(el_map[eid])
                            total_width += w
                        total_width += LANE_PADDING_X * 2
                        level_widths.append(total_width)
                
                lane_widths[lane.id] = max(level_widths) if level_widths else 700
            else:
                lane_widths[lane.id] = 700
        
        # Overall pool width (maximum across lanes)
        pool_w = max(lane_widths.values()) + POOL_HEADER_W + LANE_HEADER_W
        
        # Create pool shape
        pool_shapes[pool.id] = (0, 0, pool_w, total_h)
        
        # Position lanes and elements
        cur_y = 0
        for lane in pool.lanes:
            lh = lane_heights[lane.id]
            lw = pool_w - POOL_HEADER_W
            pool_shapes[lane.id] = (POOL_HEADER_W, cur_y, lw, lh)
            
            # Position elements in this lane
            positions = lane_positions.get(lane.id, [])
            if positions:
                # Group by level for x-position calculation
                level_groups = defaultdict(list)
                for eid, level, row in positions:
                    level_groups[level].append(eid)
                
                # Calculate x positions for each level
                for level, elements in level_groups.items():
                    total_width = sum(_el_size(el_map[eid])[0] for eid in elements)
                    total_width += (len(elements) - 1) * H_GAP
                    
                    start_x = POOL_HEADER_W + LANE_HEADER_W + LANE_PADDING_X
                    
                    # Distribute elements evenly at this level
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
        # Flat layout with grid-based positioning
        start_nodes = [e.id for e in non_boundary if _is_start_event(e)]
        if not start_nodes and non_boundary:
            start_nodes = [non_boundary[0].id]
        
        levels = _calculate_element_levels(graph, start_nodes)
        
        # Group by level
        level_groups = defaultdict(list)
        for e in non_boundary:
            if e.id in levels:
                level_groups[levels[e.id]].append(e.id)
        
        # Calculate positions
        max_level = max(level_groups.keys()) if level_groups else 0
        
        cur_y = V_GAP
        for level in range(max_level + 1):
            elements = level_groups.get(level, [])
            if elements:
                # Sort elements for consistent layout
                elements.sort(key=lambda eid: (el_map[eid].type, eid))
                
                # Calculate total width needed for this level
                total_width = sum(_el_size(el_map[eid])[0] for eid in elements)
                total_width += (len(elements) - 1) * H_GAP
                
                # Center the level horizontally
                start_x = max(FIRST_X, (1200 - total_width) / 2)
                
                cur_x = start_x
                max_h = 0
                
                for eid in elements:
                    el = el_map[eid]
                    w, h = _el_size(el)
                    shapes[el.id] = (int(cur_x), int(cur_y), w, h)
                    max_h = max(max_h, h)
                    cur_x += w + H_GAP
                
                cur_y += max_h + V_GAP
    
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


# ── Enhanced edge routing ────────────────────────────────────────────────────

def _calculate_edge_points(src_coords, tgt_coords, src_type, tgt_type):
    """
    Calculate optimal edge routing with better connection points.
    Returns list of waypoints.
    """
    sx, sy, sw, sh = src_coords
    tx, ty, tw, th = tgt_coords
    
    points = []
    
    # Determine connection sides based on relative positions
    dx = (tx + tw/2) - (sx + sw/2)
    dy = (ty + th/2) - (sy + sh/2)
    
    # Source connection point
    if abs(dx) > abs(dy):
        # Horizontal movement dominant
        if dx > 0:
            # Source to right
            points.append((sx + sw, sy + sh/2))
        else:
            # Source to left
            points.append((sx, sy + sh/2))
    else:
        # Vertical movement dominant
        if dy > 0:
            # Source down
            points.append((sx + sw/2, sy + sh))
        else:
            # Source up
            points.append((sx + sw/2, sy))
    
    # Add intermediate points for orthogonal routing if needed
    if abs(dx) > 100 and abs(dy) > 50:
        # Need a bend
        mid_x = (sx + sw/2 + tx + tw/2) / 2
        mid_y = (sy + sh/2 + ty + th/2) / 2
        
        if abs(dx) > abs(dy):
            # First horizontal, then vertical
            points.append((mid_x, sy + sh/2))
            points.append((mid_x, ty + th/2))
        else:
            # First vertical, then horizontal
            points.append((sx + sw/2, mid_y))
            points.append((tx + tw/2, mid_y))
    
    # Target connection point
    if abs(dx) > abs(dy):
        if dx > 0:
            # Target from left
            points.append((tx, ty + th/2))
        else:
            # Target from right
            points.append((tx + tw, ty + th/2))
    else:
        if dy > 0:
            # Target from top
            points.append((tx + tw/2, ty))
        else:
            # Target from bottom
            points.append((tx + tw/2, ty + th))
    
    return points


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


# ── Enhanced DI builder ──────────────────────────────────────────────────────

def _build_di(diagram, plane_ref, shapes, pool_shapes, bpmn):
    """Enhanced DI builder with better edge routing."""
    plane = _sub(diagram, DI + "BPMNPlane",
                 {"id": "plane_1", "bpmnElement": plane_ref})
    
    # Build element type map for routing decisions
    el_map = {el.id: el for el in bpmn.elements}
    
    # Collect lane ids
    lane_ids = set()
    pool_ids = set()
    for pool in bpmn.pools:
        pool_ids.add(pool.id)
        for lane in pool.lanes:
            lane_ids.add(lane.id)
    
    # Pool / lane shapes with enhanced label positioning
    for eid, (x, y, w, h) in pool_shapes.items():
        is_lane = eid in lane_ids
        shape = _sub(plane, DI + "BPMNShape",
                     {"id": eid + "_di", "bpmnElement": eid, "isHorizontal": "true"})
        b = _sub(shape, DC + "Bounds")
        b.set("x", str(int(x))); b.set("y", str(int(y)))
        b.set("width", str(int(w))); b.set("height", str(int(h)))
        
        if is_lane:
            # Enhanced lane label positioning - vertical text
            lbl = _sub(shape, DI + "BPMNLabel")
            lb = _sub(lbl, DC + "Bounds")
            # Position label in the lane header with proper dimensions for vertical text
            lb.set("x", str(int(x + 10)))
            lb.set("y", str(int(y + 10)))
            lb.set("width", str(LANE_HEADER_W - 20))
            lb.set("height", str(int(h - 20)))
    
    # Element shapes with enhanced label positioning
    for el in bpmn.elements:
        if el.id not in shapes:
            continue
        coords = shapes.get(el.id)
        if not _valid(coords):
            continue
        x, y, w, h = coords
        
        shape = _sub(plane, DI + "BPMNShape", {"id": el.id + "_di", "bpmnElement": el.id})
        b = _sub(shape, DC + "Bounds")
        b.set("x", str(int(x))); b.set("y", str(int(y)))
        b.set("width", str(int(w))); b.set("height", str(int(h)))
        
        # Enhanced label positioning based on element type
        lbl = _sub(shape, DI + "BPMNLabel")
        lb = _sub(lbl, DC + "Bounds")
        
        if el.type in EVENT_TYPES:
            # Events: label below
            lb.set("x", str(int(x - 10)))
            lb.set("y", str(int(y + h + 5)))
            lb.set("width", str(int(w + 20)))
        elif el.type in GATEWAY_TYPES:
            # Gateways: label below with extra space for diamond
            lb.set("x", str(int(x - 15)))
            lb.set("y", str(int(y + h + 5)))
            lb.set("width", str(int(w + 30)))
        else:
            # Tasks: label inside if possible, otherwise below
            lb.set("x", str(int(x)))
            lb.set("y", str(int(y + h + 2)))
            lb.set("width", str(int(w)))
        lb.set("height", "20")
    
    # Edges with enhanced routing
    for flow in bpmn.flows:
        src_coords = shapes.get(flow.source)
        tgt_coords = shapes.get(flow.target)
        
        if not src_coords or not tgt_coords:
            continue
        if not _valid(src_coords) or not _valid(tgt_coords):
            continue
        
        edge = _sub(plane, DI + "BPMNEdge",
                    {"id": flow.id + "_di", "bpmnElement": flow.id})
        
        # Calculate optimal edge points
        src_type = el_map[flow.source].type if flow.source in el_map else ""
        tgt_type = el_map[flow.target].type if flow.target in el_map else ""
        
        points = _calculate_edge_points(src_coords, tgt_coords, src_type, tgt_type)
        
        # Add waypoints
        for px, py in points:
            _wp(edge, px, py)
        
        # Enhanced label positioning for edges
        if flow.name:
            # Find midpoint of the edge for label placement
            if len(points) >= 2:
                mid_idx = len(points) // 2
                p1 = points[mid_idx - 1]
                p2 = points[mid_idx]
                mid_x = (p1[0] + p2[0]) / 2
                mid_y = (p1[1] + p2[1]) / 2
            else:
                # Fallback to simple midpoint
                sx, sy, sw, sh = src_coords
                tx, ty, tw, th = tgt_coords
                mid_x = (sx + sw/2 + tx + tw/2) / 2
                mid_y = (sy + sh/2 + ty + th/2) / 2
            
            lbl = _sub(edge, DI + "BPMNLabel")
            _sub(lbl, DC + "Bounds", {
                "x": str(int(mid_x - 30)),
                "y": str(int(mid_y - 15)),
                "width": "60",
                "height": "20",
            })


# ── Public API ────────────────────────────────────────────────────────────────

def generate_bpmn_xml(bpmn: BpmnProcess) -> str:
    """Generate enhanced BPMN 2.0 XML with better layout."""
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
    
    # Lane set with improved member collection
    if bpmn.pools and bpmn.pools[0].lanes:
        pool = bpmn.pools[0]
        lset = _sub(proc, B + "laneSet", {"id": pool.id + "_lset"})
        
        # Group elements by lane based on assignment
        lane_members = defaultdict(list)
        for eid, lid in lane_assignment.items():
            lane_members[lid].append(eid)
        
        for lane in pool.lanes:
            ln = _sub(lset, B + "lane", {"id": lane.id, "name": lane.name})
            # Sort members for consistent XML
            for eid in sorted(lane_members.get(lane.id, [])):
                _sub(ln, B + "flowNodeRef", {}).text = eid
    
    # Build elements and flows
    for el in bpmn.elements:
        _build_el(proc, el)
    for flow in bpmn.flows:
        _build_flow(proc, flow)
    
    # Collaboration (for pools)
    collab_id = None
    if bpmn.pools:
        pool = bpmn.pools[0]
        collab_id = "collab_1"
        collab = _sub(defs, B + "collaboration", {"id": collab_id})
        _sub(collab, B + "participant",
             {"id": pool.id, "name": pool.name, "processRef": process_id})
    
    # Enhanced diagram interchange
    shapes, pool_shapes = _compute_layout(bpmn, lane_assignment)
    plane_ref = collab_id if collab_id else process_id
    diagram = _sub(defs, DI + "BPMNDiagram", {"id": "diagram_1"})
    _build_di(diagram, plane_ref, shapes, pool_shapes, bpmn)
    
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + \
           ET.tostring(defs, encoding="unicode")


def generate_bpmn_preview(bpmn: BpmnProcess) -> str:
    """HTML with enhanced bpmn-js viewer and better rendering."""
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
    
    body {{
      background: #f8fafc;
      overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    }}
    
    /* Main viewport with transform */
    #viewport {{
      position: absolute;
      top: 0;
      left: 0;
      transform-origin: 0 0;
      cursor: grab;
      transition: transform 0.05s ease;
      will-change: transform;
    }}
    
    #viewport.grabbing {{
      cursor: grabbing;
      transition: none;
    }}
    
    /* bpmn-js container */
    #bpmn-container {{
      position: relative;
      width: 4000px;
      height: 3000px;
    }}
    
    /* Enhanced bpmn-js styling */
    .djs-container {{
      background: transparent !important;
    }}
    
    .djs-container > svg {{
      display: block;
      filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.05));
    }}
    
    /* Improved element styling */
    .djs-shape .djs-visual > :nth-child(1) {{
      fill: white !important;
      stroke: #2563eb !important;
      stroke-width: 2px !important;
      transition: all 0.2s ease;
    }}
    
    .djs-shape:hover .djs-visual > :nth-child(1) {{
      stroke: #3b82f6 !important;
      stroke-width: 3px !important;
      filter: drop-shadow(0 4px 6px rgba(37, 99, 235, 0.2));
    }}
    
    /* Event styling */
    .djs-shape[data-element-type$="Event"] .djs-visual > :nth-child(1) {{
      fill: #f0f9ff !important;
      stroke: #0891b2 !important;
    }}
    
    /* Gateway styling */
    .djs-shape[data-element-type$="Gateway"] .djs-visual > :nth-child(1) {{
      fill: #f5f3ff !important;
      stroke: #7c3aed !important;
    }}
    
    /* Task styling */
    .djs-shape[data-element-type$="Task"] .djs-visual > :nth-child(1),
    .djs-shape[data-element-type="callActivity"] .djs-visual > :nth-child(1) {{
      fill: #ffffff !important;
      stroke: #2563eb !important;
    }}
    
    /* Label styling */
    .djs-label {{
      font-family: inherit !important;
      font-size: 12px !important;
      fill: #1e293b !important;
      font-weight: 500 !important;
      text-anchor: middle !important;
      dominant-baseline: middle !important;
      pointer-events: none !important;
    }}
    
    .djs-shape:hover .djs-label {{
      fill: #0f172a !important;
      font-weight: 600 !important;
    }}
    
    /* Edge styling */
    .djs-connection .djs-visual > path {{
      stroke: #94a3b8 !important;
      stroke-width: 2px !important;
      marker-end: url('#sequenceflow-arrow') !important;
      transition: all 0.2s ease;
    }}
    
    .djs-connection:hover .djs-visual > path {{
      stroke: #2563eb !important;
      stroke-width: 3px !important;
    }}
    
    /* Edge label styling */
    .djs-connection .djs-label {{
      fill: #64748b !important;
      font-size: 11px !important;
      background: rgba(255, 255, 255, 0.9);
      padding: 2px 6px;
      border-radius: 4px;
    }}
    
    /* Lane styling */
    .djs-shape[data-element-type="lane"] .djs-visual > rect {{
      fill: #f8fafc !important;
      stroke: #cbd5e1 !important;
      stroke-dasharray: 4 2 !important;
    }}
    
    .djs-shape[data-element-type="participant"] .djs-visual > rect {{
      fill: #f1f5f9 !important;
      stroke: #94a3b8 !important;
      stroke-width: 2px !important;
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
      display: flex;
      align-items: center;
      justify-content: center;
      transition: all 0.2s ease;
    }}
    
    .tb-btn:hover {{
      background: rgba(255, 255, 255, 0.1);
      color: #f1f5f9;
      transform: scale(1.05);
    }}
    
    .tb-btn:active {{
      transform: scale(0.95);
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
      font-weight: 500;
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
      padding: 20px 28px;
      max-width: 600px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 13px;
      color: #dc2626;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
      z-index: 2000;
      backdrop-filter: blur(8px);
      background: rgba(255, 255, 255, 0.98);
    }}
  </style>
  
  <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17/dist/assets/bpmn-js.css">
  <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17/dist/assets/diagram-js.css">
  <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17/dist/assets/bpmn-font/css/bpmn-embedded.css">
</head>
<body>
<div id="viewport">
  <div id="bpmn-container"></div>
</div>

<div id="toolbar">
  <button class="tb-btn" id="btn-out" title="Zoom out (Ctrl -)">−</button>
  <span id="zoom-label">100%</span>
  <button class="tb-btn" id="btn-in" title="Zoom in (Ctrl +)">+</button>
  <div class="tb-divider"></div>
  <button class="tb-btn" id="btn-fit" title="Fit to screen (0)">⤢</button>
  <button class="tb-btn" id="btn-reset" title="Reset view (R)">↺</button>
  <div class="tb-divider"></div>
  <button class="tb-btn" id="btn-center" title="Center view">◎</button>
</div>

<div id="err"></div>

<script src="https://unpkg.com/bpmn-js@17/dist/bpmn-viewer.development.js"></script>
<script>
(function() {{
  const xml = `{xml_js}`;
  const errDiv = document.getElementById('err');
  const vp = document.getElementById('viewport');
  const zoomLbl = document.getElementById('zoom-label');
  
  // ── State management ─────────────────────────────────────────────────
  let scale = 1, tx = 0, ty = 0;
  let dragging = false, startX, startY, startTx, startTy;
  let lastDist = null;
  
  // Animation frame for smooth updates
  let rafId = null;
  
  function apply() {{
    if (rafId) cancelAnimationFrame(rafId);
    rafId = requestAnimationFrame(() => {{
      vp.style.transform = `translate(${{tx}}px, ${{ty}}px) scale(${{scale}})`;
      zoomLbl.textContent = Math.round(scale * 100) + '%';
      rafId = null;
    }});
  }}
  
  function clamp(s) {{
    return Math.min(Math.max(s, 0.1), 5);
  }}
  
  function zoomTo(ns, cx, cy) {{
    const r = ns / scale;
    tx = cx - r * (cx - tx);
    ty = cy - r * (cy - ty);
    scale = ns;
    apply();
  }}
  
  // ── Fit to screen with padding ───────────────────────────────────────
  function fitToScreen() {{
    const svg = document.querySelector('#bpmn-container svg');
    if (!svg) return;
    
    let sw, sh;
    const vb = svg.viewBox && svg.viewBox.baseVal;
    
    if (vb && vb.width > 10 && vb.height > 10) {{
      sw = vb.width;
      sh = vb.height;
    }} else {{
      const bbox = svg.getBBox();
      if (bbox && bbox.width > 10) {{
        sw = bbox.width;
        sh = bbox.height;
      }} else {{
        sw = parseFloat(svg.getAttribute('width')) || 1200;
        sh = parseFloat(svg.getAttribute('height')) || 800;
      }}
    }}
    
    if (!sw || !sh || sw < 10) return;
    
    const padding = 60;
    const W = window.innerWidth - padding * 2;
    const H = window.innerHeight - padding * 2 - 80;
    
    const ns = clamp(Math.min(W / sw, H / sh) * 0.95);
    
    if (!isFinite(ns) || ns <= 0) return;
    
    scale = ns;
    tx = (window.innerWidth - sw * scale) / 2;
    ty = Math.max(40, (window.innerHeight - sh * scale) / 2);
    
    apply();
  }}
  
  function centerView() {{
    const svg = document.querySelector('#bpmn-container svg');
    if (!svg) return;
    
    const vb = svg.viewBox && svg.viewBox.baseVal;
    if (vb && vb.width > 10) {{
      tx = (window.innerWidth - vb.width * scale) / 2;
      ty = (window.innerHeight - vb.height * scale) / 2;
      apply();
    }}
  }}
  
  // ── Mouse pan ────────────────────────────────────────────────────────
  vp.addEventListener('mousedown', e => {{
    if (e.button !== 0) return;
    e.preventDefault();
    dragging = true;
    startX = e.clientX;
    startY = e.clientY;
    startTx = tx;
    startTy = ty;
    vp.classList.add('grabbing');
  }});
  
  window.addEventListener('mousemove', e => {{
    if (!dragging) return;
    e.preventDefault();
    tx = startTx + e.clientX - startX;
    ty = startTy + e.clientY - startY;
    apply();
  }});
  
  window.addEventListener('mouseup', () => {{
    dragging = false;
    vp.classList.remove('grabbing');
  }});
  
  // ── Wheel zoom with smooth behavior ──────────────────────────────────
  window.addEventListener('wheel', e => {{
    e.preventDefault();
    
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    const ns = clamp(scale * delta);
    
    // Zoom toward mouse position
    const mouseX = e.clientX;
    const mouseY = e.clientY;
    
    zoomTo(ns, mouseX, mouseY);
  }}, {{ passive: false }});
  
  // ── Touch support ────────────────────────────────────────────────────
  vp.addEventListener('touchstart', e => {{
    if (e.touches.length === 1) {{
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
      startTx = tx;
      startTy = ty;
    }}
    if (e.touches.length === 2) {{
      lastDist = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
    }}
  }}, {{ passive: true }});
  
  vp.addEventListener('touchmove', e => {{
    e.preventDefault();
    
    if (e.touches.length === 1 && !lastDist) {{
      tx = startTx + e.touches[0].clientX - startX;
      ty = startTy + e.touches[0].clientY - startY;
      apply();
    }}
    
    if (e.touches.length === 2) {{
      const d = Math.hypot(
        e.touches[0].clientX - e.touches[1].clientX,
        e.touches[0].clientY - e.touches[1].clientY
      );
      const mx = (e.touches[0].clientX + e.touches[1].clientX) / 2;
      const my = (e.touches[0].clientY + e.touches[1].clientY) / 2;
      
      if (lastDist) {{
        const ns = clamp(scale * d / lastDist);
        zoomTo(ns, mx, my);
      }}
      lastDist = d;
    }}
  }}, {{ passive: false }});
  
  vp.addEventListener('touchend', () => {{
    lastDist = null;
  }});
  
  // ── Keyboard shortcuts ───────────────────────────────────────────────
  window.addEventListener('keydown', e => {{
    const cx = window.innerWidth / 2;
    const cy = window.innerHeight / 2;
    
    if (e.key === '+' || e.key === '=') {{
      e.preventDefault();
      zoomTo(clamp(scale * 1.2), cx, cy);
    }}
    if (e.key === '-' || e.key === '_') {{
      e.preventDefault();
      zoomTo(clamp(scale * 0.8), cx, cy);
    }}
    if (e.key === '0') {{
      e.preventDefault();
      fitToScreen();
    }}
    if (e.key === 'r' || e.key === 'R') {{
      e.preventDefault();
      scale = 1;
      tx = 0;
      ty = 0;
      apply();
    }}
    // Arrow key panning
    const panStep = 50 / scale;
    if (e.key === 'ArrowLeft') {{
      e.preventDefault();
      tx += panStep;
      apply();
    }}
    if (e.key === 'ArrowRight') {{
      e.preventDefault();
      tx -= panStep;
      apply();
    }}
    if (e.key === 'ArrowUp') {{
      e.preventDefault();
      ty += panStep;
      apply();
    }}
    if (e.key === 'ArrowDown') {{
      e.preventDefault();
      ty -= panStep;
      apply();
    }}
  }});
  
  // ── Toolbar buttons ──────────────────────────────────────────────────
  const cx = () => window.innerWidth / 2;
  const cy = () => window.innerHeight / 2;
  
  document.getElementById('btn-in').onclick = () => 
    zoomTo(clamp(scale * 1.2), cx(), cy());
  
  document.getElementById('btn-out').onclick = () => 
    zoomTo(clamp(scale * 0.8), cx(), cy());
  
  document.getElementById('btn-fit').onclick = fitToScreen;
  
  document.getElementById('btn-reset').onclick = () => {{
    scale = 1;
    tx = 0;
    ty = 0;
    apply();
  }};
  
  document.getElementById('btn-center').onclick = centerView;
  
  // ── Initialize bpmn-js ───────────────────────────────────────────────
  const viewer = new BpmnJS({{
    container: '#bpmn-container',
    keyboard: {{ bindTo: null }}, // Disable built-in keyboard
    modules: [] // Use minimal modules for better performance
  }});
  
  // Add custom arrow marker
  const svgNamespace = "http://www.w3.org/2000/svg";
  const defs = document.createElementNS(svgNamespace, "defs");
  const marker = document.createElementNS(svgNamespace, "marker");
  marker.setAttribute("id", "sequenceflow-arrow");
  marker.setAttribute("viewBox", "0 0 10 10");
  marker.setAttribute("refX", "9");
  marker.setAttribute("refY", "5");
  marker.setAttribute("markerWidth", "6");
  marker.setAttribute("markerHeight", "6");
  marker.setAttribute("orient", "auto");
  
  const path = document.createElementNS(svgNamespace, "path");
  path.setAttribute("d", "M 0 0 L 10 5 L 0 10 z");
  path.setAttribute("fill", "#94a3b8");
  marker.appendChild(path);
  defs.appendChild(marker);
  
  viewer.importXML(xml)
    .then(() => {{
      // Disable built-in zoom/scroll
      try {{
        const zs = viewer.get('zoomScroll');
        zs._enabled = false;
      }} catch(_) {{}}
      
      // Add arrow marker to SVG
      const svg = document.querySelector('#bpmn-container svg');
      if (svg && !svg.querySelector('#sequenceflow-arrow')) {{
        svg.insertBefore(defs, svg.firstChild);
      }}
      
      // Fit to screen after rendering
      setTimeout(() => fitToScreen(), 300);
    }})
    .catch(err => {{
      errDiv.style.display = 'block';
      errDiv.innerHTML = '<b>⚠️ BPMN rendering error:</b><br>' + 
        err.message.replace(/</g, '&lt;').replace(/>/g, '&gt;');
      console.error('BPMN import error:', err);
    }});
}})();
</script>
</body>
</html>"""
