# modules/bpmn_generator.py
# ─────────────────────────────────────────────────────────────────────────────
# BPMN 2.0 XML generator — business logic only, zero UI.
#
# Extracted from diagram_bpmn.py (original by Pedro Gentil).
# Separation rationale: this module can be used from CLI, API, tests,
# or any frontend without pulling in HTML/JS dependencies.
#
# Public API:
#   generate_bpmn_xml(bpmn: BpmnProcess) -> str
#
# Compatible with: Camunda Modeler, Bizagi, draw.io, bpmn.io, Signavio
# ─────────────────────────────────────────────────────────────────────────────

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


# ── XML helpers ───────────────────────────────────────────────────────────────

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
    Returns dict {element_id: lane_id} for every non-boundary element.
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
        if el.type == "boundaryEvent" or el.id in assignment:
            continue
        actor = el.actor or el.lane
        if actor and actor in lane_by_name:
            assignment[el.id] = lane_by_name[actor]

    # Collect still-unassigned non-boundary element ids
    all_ids   = {e.id for e in bpmn.elements if e.type != "boundaryEvent"}
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
        fallback = pool.lanes[0].id
        for eid in unassigned:
            assignment[eid] = fallback

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
    """Topological sort — preserves process flow order."""
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


def _assign_columns(order, flows):
    """
    Assign a global column index (0-based) to every element.

    Rules
    -----
    1. Process elements in topological order.
    2. Each element's column = max(predecessor columns) + 1.
       (Start nodes with no predecessors get column 0.)
    3. This guarantees:
       - Diverging gateway branches all start at gateway_col + 1,
         so they occupy the same column slot in their respective lanes.
       - Converging gateways are placed *after* all their branches,
         eliminating the most common source of edge crossings.

    Returns
    -------
    dict {element_id: column_index}
    """
    # Build predecessor map (only within the order set)
    id_set = set(order)
    pred_col = {eid: -1 for eid in order}   # max predecessor column seen so far

    # Index flows by target for fast lookup
    preds_of = {eid: [] for eid in order}
    for f in flows:
        if f.source in id_set and f.target in id_set:
            preds_of[f.target].append(f.source)

    col = {}
    for eid in order:
        preds = preds_of[eid]
        if not preds:
            col[eid] = 0
        else:
            # Column must be at least 1 past every predecessor's column.
            # Use the maximum so converging nodes land after all branches.
            max_pred = max(col[p] for p in preds if p in col)
            col[eid] = max_pred + 1

    return col


def _col_x(col_index, col_widths, base_x):
    """
    Return the left-edge X for the given column index.
    col_widths[c] = width of the widest element in column c.
    base_x        = x offset where column 0 starts.
    """
    x = base_x
    for c in range(col_index):
        x += col_widths.get(c, TASK_W) + H_GAP
    return x


def _compute_layout(bpmn, lane_assignment):
    shapes      = {}
    pool_shapes = {}

    non_boundary = [e for e in bpmn.elements if e.type != "boundaryEvent"]
    order  = _topo_sort([e.id for e in non_boundary], bpmn.flows)
    el_map = {e.id: e for e in bpmn.elements}

    if bpmn.pools:
        pool = bpmn.pools[0]

        # ── Step 1: assign global columns ─────────────────────────────────────
        col_of = _assign_columns(order, bpmn.flows)

        # ── Step 2: compute the width of each column (widest element in it) ───
        col_widths = {}
        for eid in order:
            c = col_of.get(eid, 0)
            w, _ = _el_size(el_map[eid]) if eid in el_map else (TASK_W, TASK_H)
            col_widths[c] = max(col_widths.get(c, 0), w)

        # ── Step 3: bucket elements per lane, preserving column order ─────────
        lane_order = {lane.id: [] for lane in pool.lanes}
        for eid in order:
            lid = lane_assignment.get(eid)
            if lid and lid in lane_order:
                lane_order[lid].append(eid)
            elif pool.lanes:
                lane_order[pool.lanes[0].id].append(eid)

        # ── Step 4: lane heights ───────────────────────────────────────────────
        lane_h = {}
        for lane in pool.lanes:
            els_in_lane = [el_map[eid] for eid in lane_order[lane.id] if eid in el_map]
            max_h = max((_el_size(e)[1] for e in els_in_lane), default=TASK_H)
            lane_h[lane.id] = max(MIN_LANE_H, max_h + V_PAD * 2)

        total_h = sum(lane_h[l.id] for l in pool.lanes)

        # ── Step 5: pool width from column grid ───────────────────────────────
        base_x = POOL_HEADER_W + LANE_HEADER_W + FIRST_X
        max_col = max(col_of.values(), default=0)
        pool_w = base_x + sum(col_widths.get(c, TASK_W) + H_GAP
                              for c in range(max_col + 1)) + FIRST_X
        pool_w = max(pool_w, 700)

        pool_shapes[pool.id] = (0, 0, pool_w, total_h)

        # ── Step 6: position each element using its column's X ─────────────────
        cur_y = 0
        for lane in pool.lanes:
            lh  = lane_h[lane.id]
            lx  = POOL_HEADER_W
            lw  = pool_w - POOL_HEADER_W
            pool_shapes[lane.id] = (lx, cur_y, lw, lh)

            for eid in lane_order[lane.id]:
                if eid not in el_map:
                    continue
                el   = el_map[eid]
                w, h = _el_size(el)
                c    = col_of.get(eid, 0)
                # Centre the element horizontally within its column slot
                col_slot_w = col_widths.get(c, TASK_W)
                x = _col_x(c, col_widths, base_x) + (col_slot_w - w) // 2
                y = cur_y + (lh - h) // 2          # vertically centred in lane
                shapes[el.id] = (int(x), int(y), w, h)

            cur_y += lh

    else:
        # ── No-pool fallback: single vertical column per element ───────────────
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

    # ── Boundary events: anchored on host element ──────────────────────────────
    for el in bpmn.elements:
        if el.type == "boundaryEvent" and el.attached_to:
            host = shapes.get(el.attached_to)
            if host:
                hx, hy, hw, hh = host
                shapes[el.id] = (hx + hw - EV_W // 2, hy + hh - EV_H // 2, EV_W, EV_H)

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

    lane_ids = {lane.id for pool in bpmn.pools for lane in pool.lanes}

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

    for flow in bpmn.flows:
        src = shapes.get(flow.source)
        tgt = shapes.get(flow.target)
        if not src or not tgt or not _valid(src) or not _valid(tgt):
            continue
        edge = _sub(plane, DI + "BPMNEdge",
                    {"id": flow.id + "_di", "bpmnElement": flow.id})
        sx, sy, sw, sh = src
        tx, ty, tw, th = tgt
        _wp(edge, sx + sw, sy + sh / 2)   # source right-centre
        _wp(edge, tx,      ty + th / 2)   # target left-centre
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
    """
    Generate BPMN 2.0 XML string.
    Save with .bpmn extension to open in Camunda, Bizagi, draw.io, bpmn.io.
    """
    defs = ET.Element(B + "definitions", {
        "xmlns":           _NS["bpmn"],
        "xmlns:bpmndi":    _NS["bpmndi"],
        "xmlns:dc":        _NS["dc"],
        "xmlns:di":        _NS["di"],
        "xmlns:xsi":       _NS["xsi"],
        "targetNamespace": "http://process2diagram.io/bpmn",
        "id":              "definitions_1",
        "exporter":        "Process2Diagram",
        "exporterVersion": "3.0",
    })

    process_id = "process_1"
    proc = _sub(defs, B + "process", {
        "id": process_id, "name": bpmn.name,
        "isExecutable": "false", "processType": "None",
    })
    if bpmn.documentation:
        _sub(proc, B + "documentation", {}).text = bpmn.documentation

    lane_assignment = _assign_lanes(bpmn)

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

    for el in bpmn.elements:
        _build_el(proc, el)
    for flow in bpmn.flows:
        _build_flow(proc, flow)

    collab_id = None
    if bpmn.pools:
        pool      = bpmn.pools[0]
        collab_id = "collab_1"
        collab    = _sub(defs, B + "collaboration", {"id": collab_id})
        _sub(collab, B + "participant",
             {"id": pool.id, "name": pool.name, "processRef": process_id})

    shapes, pool_shapes = _compute_layout(bpmn, lane_assignment)
    plane_ref = collab_id if collab_id else process_id
    diagram   = _sub(defs, DI + "BPMNDiagram", {"id": "diagram_1"})
    _build_di(diagram, plane_ref, shapes, pool_shapes, bpmn)

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + \
           ET.tostring(defs, encoding="unicode")
