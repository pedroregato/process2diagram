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
from modules.schema import BpmnProcess, BpmnElement, BpmnLane, BpmnPool, SequenceFlow, MessageFlow

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
POOL_GAP          = 50    # vertical gap between pools in a collaboration


# ── Link-event crossing elimination ──────────────────────────────────────────
#
# After the column-based layout is computed we have concrete (x,y,w,h) for
# every element and two waypoints per edge (right-centre → left-centre).
# This pass:
#   1. Detects edges whose straight line intersects any other edge's straight
#      line (geometric segment-intersection test).
#   2. For each crossing edge, replaces it with a
#      intermediateThrowEvent(link) + intermediateThrowEvent(link) pair placed
#      in the source / target lanes respectively.
#   3. Rewires the BpmnProcess model (elements + flows) in-place so that the
#      standard XML generation path picks up the new elements naturally.
#
# The BPMN 2.0 spec (§13.2.9) explicitly defines Link Events as a mechanism
# to connect distant parts of a diagram without visible crossing connectors.
# ─────────────────────────────────────────────────────────────────────────────

def _edge_segment(flow, shapes):
    """
    Return the (x1,y1, x2,y2) straight-line segment for a flow,
    using the same right-centre / left-centre waypoints as _build_di.
    Returns None if either endpoint is missing.
    """
    src = shapes.get(flow.source)
    tgt = shapes.get(flow.target)
    if not src or not tgt:
        return None
    sx, sy, sw, sh = src
    tx, ty, tw, th = tgt
    return (sx + sw, sy + sh / 2, tx, ty + th / 2)


def _segments_intersect(s1, s2):
    """
    Test whether two line segments (x1,y1,x2,y2) properly intersect.
    'Properly' means the intersection point is strictly interior to both
    segments — shared endpoints (touching) are not counted.
    Uses the standard cross-product / parametric approach.
    """
    ax, ay, bx, by = s1
    cx, cy, dx, dy = s2

    def cross2d(ux, uy, vx, vy):
        return ux * vy - uy * vx

    # Direction vectors
    abx, aby = bx - ax, by - ay
    cdx, cdy = dx - cx, dy - cy

    denom = cross2d(abx, aby, cdx, cdy)
    if abs(denom) < 1e-9:          # parallel / collinear
        return False

    acx, acy = cx - ax, cy - ay
    t = cross2d(acx, acy, cdx, cdy) / denom
    u = cross2d(acx, acy, abx, aby) / denom

    # Strictly interior (exclude endpoints with small epsilon)
    eps = 1e-6
    return eps < t < 1 - eps and eps < u < 1 - eps


def _is_link_flow(flow):
    """True if either endpoint of this flow is a generated link event."""
    return (flow.source.startswith("lnk_") or flow.target.startswith("lnk_"))


def _detect_crossings(flows, shapes, lane_assignment=None, pool=None):
    """
    Return a set of flow IDs that should be replaced with Link Event pairs.

    IMPORTANT: flows that already involve link events (lnk_throw_N or
    lnk_catch_N) are excluded from detection. This prevents the iterative
    injection loop from re-detecting short flows created in a previous pass.

    Only one heuristic is applied:

    LANE-SPANNING  (requires lane_assignment + pool)
      A cross-lane flow that *skips* one or more intermediate lanes
      will visually overlap with flows in those lanes.  Any flow whose
      source and target are separated by ≥2 lane boundaries is flagged.

    Adjacent-lane flows (span = 1) are intentionally left as-is.
    bpmn-js routes their crossing arrows natively; using Link Events for
    them causes layout distortion (the catch event ends up at column 0).
    """
    candidate_flows = [f for f in flows if not _is_link_flow(f)]
    crossing_ids = set()

    # ── Heuristic 2: lane-spanning ────────────────────────────────────────────
    # A cross-lane flow skipping ≥2 intermediate lanes may visually overlap
    # elements in those skipped lanes. BUT: only flag it if the skipped lanes
    # actually contain elements in the column range between source and target.
    # If the intermediate lanes are empty (or their elements are outside the
    # column range), the flow crosses an empty strip — no visual problem.
    if lane_assignment and pool and pool.lanes:
        lane_index = {lane.id: idx for idx, lane in enumerate(pool.lanes)}

        # Build a set of (lane_id, col_x) for every element that has a shape
        # so we can quickly check if a lane has elements in a column range
        lane_col_x = {}  # lane_id → set of element centre-x values
        for eid, shp in shapes.items():
            lid = lane_assignment.get(eid)
            if lid:
                cx = shp[0] + shp[2] / 2
                lane_col_x.setdefault(lid, set()).add(cx)

        for f in candidate_flows:
            src_lid = lane_assignment.get(f.source)
            tgt_lid = lane_assignment.get(f.target)
            if not src_lid or not tgt_lid or src_lid == tgt_lid:
                continue
            si = lane_index.get(src_lid, -1)
            ti = lane_index.get(tgt_lid, -1)
            if si < 0 or ti < 0:
                continue
            if abs(si - ti) < 2:
                continue   # adjacent lanes: no intermediate to check

            # Determine the X range covered by this flow
            src_shp = shapes.get(f.source)
            tgt_shp = shapes.get(f.target)
            if not src_shp or not tgt_shp:
                crossing_ids.add(f.id)   # conservative: flag if no shape data
                continue

            x_min = min(src_shp[0] + src_shp[2] / 2, tgt_shp[0] + tgt_shp[2] / 2)
            x_max = max(src_shp[0] + src_shp[2] / 2, tgt_shp[0] + tgt_shp[2] / 2)

            # Check each skipped (intermediate) lane for elements in range
            lo, hi = min(si, ti), max(si, ti)
            skipped_lane_ids = [
                lane.id for lane in pool.lanes
                if lo < lane_index[lane.id] < hi
            ]
            has_elements_in_range = any(
                any(x_min - 50 <= cx <= x_max + 50
                    for cx in lane_col_x.get(lid, set()))
                for lid in skipped_lane_ids
            )
            if has_elements_in_range:
                crossing_ids.add(f.id)

    # ── Heuristic 3: large horizontal span on cross-lane flows ────────────────
    # A cross-lane flow that travels far to the right (≥ 2 task-column widths
    # past its source) draws a long diagonal that visually cuts through other
    # flows in the same lane, even when no strict geometric intersection exists.
    #
    # This catches cases like:
    #   S01 (col 1, lane A)  →  S05 (col 5, lane B)
    # where S01 also has outgoing flows to S02, S03, S04 in lane A at cols 2–4,
    # and the diagonal S01→S05 visually crosses those outgoing flows.
    #
    # Threshold: target is ≥ 2 column-widths (≈ 320 px) to the right of the
    # source's RIGHT edge. This means the flow is not a simple adjacent-column
    # hop but a genuine long-range connection.
    LONG_CROSS_PX = 320   # ≈ 2 × (TASK_W=160) + some H_GAP
    if lane_assignment and pool:
        for f in candidate_flows:
            if f.id in crossing_ids:
                continue   # already flagged
            src_lid = lane_assignment.get(f.source)
            tgt_lid = lane_assignment.get(f.target)
            if not src_lid or not tgt_lid or src_lid == tgt_lid:
                continue   # same-lane flows don't draw cross-lane diagonals
            src_shape = shapes.get(f.source)
            tgt_shape = shapes.get(f.target)
            if not src_shape or not tgt_shape:
                continue
            # Distance from the right edge of source to left edge of target
            src_right = src_shape[0] + src_shape[2]
            tgt_left  = tgt_shape[0]
            if (tgt_left - src_right) >= LONG_CROSS_PX:
                crossing_ids.add(f.id)

    # ── Heuristic 4: backward cross-lane flows ────────────────────────────────
    # A flow that returns to an earlier column while also crossing a lane
    # boundary draws a long backward diagonal that will geometrically cross
    # every forward flow occupying the same horizontal range.
    #
    # Example: S07 (col 6, Gestores) → S03 (col 3, Auditoria)
    # This diagonal cuts across sf_004 (S04→S05) and others in the overlap zone.
    #
    # Detection rule: target's left edge is to the LEFT of source's left edge
    # (target_x < source_x) AND the two endpoints are in different lanes.
    if lane_assignment and pool:
        for f in candidate_flows:
            if f.id in crossing_ids:
                continue   # already flagged
            src_lid = lane_assignment.get(f.source)
            tgt_lid = lane_assignment.get(f.target)
            if not src_lid or not tgt_lid or src_lid == tgt_lid:
                continue   # same-lane loops don't cross other lanes
            src_shape = shapes.get(f.source)
            tgt_shape = shapes.get(f.target)
            if not src_shape or not tgt_shape:
                continue
            # Backward: target starts to the left of where source starts
            if tgt_shape[0] < src_shape[0]:
                crossing_ids.add(f.id)

    return crossing_ids


def _lane_of(element_id, lane_assignment, pools):
    """Return the BpmnLane object for a given element id, or None."""
    lid = lane_assignment.get(element_id)
    if not lid or not pools:
        return None
    for lane in pools[0].lanes:
        if lane.id == lid:
            return lane
    return None


def _apply_link_events(bpmn, lane_assignment, shapes):
    """
    Detect crossing edges and replace each one with a Link Event pair.

    For a crossing flow  A ──────────────────────> B
    we inject:
        A ──> [throw_link_N]     (in A's lane)
              [catch_link_N] ──> B   (in B's lane)

    The throw and catch events are added to bpmn.elements and
    bpmn.pools[0].lanes[*].element_ids.  The original flow is removed
    and two replacement flows are added.

    Returns True if any substitution was made (so caller can recompute
    layout), False otherwise.
    """
    pool_obj = bpmn.pools[0] if bpmn.pools else None
    crossing_ids = _detect_crossings(bpmn.flows, shapes, lane_assignment, pool_obj)
    if not crossing_ids:
        return False

    flows_by_id  = {f.id: f for f in bpmn.flows}
    el_lane      = {eid: lid for eid, lid in lane_assignment.items()}
    lane_by_id   = {}
    if bpmn.pools:
        for lane in bpmn.pools[0].lanes:
            lane_by_id[lane.id] = lane

    new_elements = list(bpmn.elements)
    new_flows    = []
    link_counter = [0]   # mutable so nested helper can increment

    for flow in bpmn.flows:
        if flow.id not in crossing_ids:
            new_flows.append(flow)
            continue

        link_counter[0] += 1
        n      = link_counter[0]
        label  = flow.name or f"L{n}"   # human-readable link name shown on the event

        throw_id = f"lnk_throw_{n}"
        catch_id = f"lnk_catch_{n}"

        # ── Throw event in source's lane ──────────────────────────────────────
        src_lane_id = el_lane.get(flow.source)
        throw_el = BpmnElement(
            id=throw_id,
            name=label,
            type="intermediateThrowEvent",
            event_type="link",
            lane=lane_by_id[src_lane_id].name if src_lane_id in lane_by_id else None,
            actor=None,
        )

        # ── Catch event in target's lane ──────────────────────────────────────
        tgt_lane_id = el_lane.get(flow.target)
        catch_el = BpmnElement(
            id=catch_id,
            name=label,
            type="intermediateCatchEvent",
            event_type="link",
            lane=lane_by_id[tgt_lane_id].name if tgt_lane_id in lane_by_id else None,
            actor=None,
        )

        new_elements.extend([throw_el, catch_el])

        # ── Register in lane membership ────────────────────────────────────────
        if src_lane_id and src_lane_id in lane_by_id:
            lane_by_id[src_lane_id].element_ids.append(throw_id)
            lane_assignment[throw_id] = src_lane_id
        if tgt_lane_id and tgt_lane_id in lane_by_id:
            lane_by_id[tgt_lane_id].element_ids.append(catch_id)
            lane_assignment[catch_id] = tgt_lane_id

        # ── Replace the crossing flow with two short flows ─────────────────────
        new_flows.append(SequenceFlow(
            id=flow.id + "_a",
            source=flow.source,
            target=throw_id,
            name="",
            condition=flow.condition if hasattr(flow, "condition") else "",
        ))
        new_flows.append(SequenceFlow(
            id=flow.id + "_b",
            source=catch_id,
            target=flow.target,
            name="",
        ))

    bpmn.elements = new_elements
    bpmn.flows    = new_flows
    return True


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
    3. Link events (lnk_throw_N, lnk_catch_N) are treated like regular
       elements for column assignment — they inherit depth from their
       predecessors/successors. Their X position is then fine-tuned in
       _compute_layout to avoid overlapping regular elements in the same
       lane and column.

    Returns dict {element_id: column_index}
    """
    id_set   = set(order)
    preds_of = {eid: [] for eid in order}
    for f in flows:
        if f.source in id_set and f.target in id_set:
            preds_of[f.target].append(f.source)

    col = {}
    for eid in order:
        preds = [p for p in preds_of[eid] if p in col]
        col[eid] = (max(col[p] for p in preds) + 1) if preds else 0

    return col


def _align_parallel_branches(col: dict, flows: list) -> dict:
    """
    Post-pass alignment for parallel branches of unequal length.

    Problem: when a parallel split has branches with different numbers of
    steps, the shorter branch finishes several columns before the join
    gateway.  bpmn-js then draws a long diagonal arrow from the short
    branch's terminal step to the join, spanning empty column slots and
    making the diagram visually confusing.

    Fix: for each node that is the *terminal step* of a branch (its only
    successor is a join gateway with ≥2 incoming edges), snap its column
    to join_col − 1 when it currently sits further left.

    Safety conditions (all must hold before moving a node):
      - The node has exactly one successor (the join) — so moving it right
        cannot violate ordering with other downstream nodes.
      - The node's natural column is strictly less than join_col − 1.
      - Moving the node does not place it before any of its own predecessors
        (col[node] stays > max(col[pred])).

    The function mutates `col` in-place and returns it.
    """
    id_set = set(col.keys())
    succs: dict[str, list[str]] = {eid: [] for eid in id_set}
    preds: dict[str, list[str]] = {eid: [] for eid in id_set}
    for f in flows:
        if f.source in id_set and f.target in id_set:
            succs[f.source].append(f.target)
            preds[f.target].append(f.source)

    # Identify join nodes: more than one incoming edge
    joins = {eid for eid in id_set if len(preds[eid]) > 1}

    for join_id in joins:
        join_col = col[join_id]
        target_col = join_col - 1
        for pred_id in preds[join_id]:
            if col[pred_id] >= target_col:
                continue                    # already aligned
            if len(succs[pred_id]) != 1:
                continue                    # feeds other nodes too — don't touch
            # Ensure the move doesn't place pred before any of its own preds
            own_pred_max = max(
                (col[p] for p in preds[pred_id] if p in col), default=-1
            )
            if target_col <= own_pred_max:
                continue                    # would violate topological order
            col[pred_id] = target_col

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
        col_of = _align_parallel_branches(col_of, bpmn.flows)

        # Fix lnk_catch_N columns: catch events have no incoming flows so
        # _assign_columns gives them col=0.  Place them at the same column as
        # their target so they stack cleanly in the target lane rather than
        # appearing at the diagram's left edge alongside the start event.
        for f in bpmn.flows:
            if f.source.startswith("lnk_catch_") and f.target in col_of:
                col_of[f.source] = col_of[f.target]

        # Fix lnk_throw_N columns: _assign_columns places the throw event at
        # col[source]+1 (its natural topological depth).  That +1 column is often
        # shared by cross-lane forward flows (e.g. S07→S08 in the same column),
        # whose diagonal waypoints then geometrically intersect the short
        # source→throw flow.  Placing the throw event at col[source] instead
        # makes the source→throw flow a short vertical arrow within the same
        # column, which lies to the left of the cross-lane diagonal and never
        # intersects it.  Nothing else depends on lnk_throw_N as a predecessor
        # in the sequence flows, so this reassignment is always safe.
        for f in bpmn.flows:
            if f.target.startswith("lnk_throw_") and f.source in col_of:
                col_of[f.target] = col_of[f.source]

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
        # A lane needs enough vertical space to stack all elements that share
        # the same column slot without overlapping each other.
        #
        # Algorithm:
        #   1. For each lane, group its elements by column.
        #   2. Count how many elements share each column (parallel stack depth).
        #   3. Lane height = V_PAD*2 + sum of heights in the tallest column stack,
        #      with V_GAP between stacked items.
        #   4. Enforce MIN_LANE_H.
        #
        # This makes lanes with parallel branches (multiple elements per column)
        # automatically taller than lanes with purely sequential flows.
        V_GAP = 20   # vertical gap between stacked elements in the same column

        lane_h = {}
        for lane in pool.lanes:
            eids_in_lane = [eid for eid in lane_order[lane.id] if eid in el_map]
            if not eids_in_lane:
                lane_h[lane.id] = MIN_LANE_H
                continue

            # Group by column
            col_groups = {}
            for eid in eids_in_lane:
                c = col_of.get(eid, 0)
                col_groups.setdefault(c, []).append(eid)

            # Height needed for the tallest column stack
            max_stack_h = 0
            for c, eids_in_col in col_groups.items():
                stack_h = sum(_el_size(el_map[eid])[1] for eid in eids_in_col)
                stack_h += V_GAP * (len(eids_in_col) - 1)
                max_stack_h = max(max_stack_h, stack_h)

            lane_h[lane.id] = max(MIN_LANE_H, max_stack_h + V_PAD * 2)

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

            # Group elements in this lane by column, preserving topo order
            eids_in_lane = [eid for eid in lane_order[lane.id] if eid in el_map]
            col_groups   = {}
            for eid in eids_in_lane:
                c = col_of.get(eid, 0)
                col_groups.setdefault(c, []).append(eid)

            for eid in eids_in_lane:
                el   = el_map[eid]
                w, h = _el_size(el)
                c    = col_of.get(eid, 0)

                # X: centred within the column slot
                col_slot_w = col_widths.get(c, TASK_W)
                x = _col_x(c, col_widths, base_x) + (col_slot_w - w) // 2

                # Y: distribute elements sharing the same column vertically
                stack = col_groups[c]
                stack_total_h = sum(_el_size(el_map[s])[1] for s in stack)
                stack_total_h += V_GAP * (len(stack) - 1)
                stack_top_y   = cur_y + (lh - stack_total_h) // 2  # centred in lane

                y_offset = 0
                for s in stack:
                    if s == eid:
                        break
                    y_offset += _el_size(el_map[s])[1] + V_GAP

                y = stack_top_y + y_offset
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

    # ── Step 7: reposition lnk_throw events to avoid passing through stacked elements ──
    # When a lnk_throw event ends up in the same column as its source, the
    # vertical flow source_bottom → throw_top may cross other elements stacked
    # in that column.  Fix: move the throw event to just right of the source
    # (in the inter-column gap) so the routing becomes a short horizontal hop.
    if bpmn.pools:
        _la_inner = _assign_lanes(bpmn)
        for f in bpmn.flows:
            if not f.target.startswith("lnk_throw_"):
                continue
            src_id   = f.source
            throw_id = f.target
            if src_id not in shapes or throw_id not in shapes:
                continue
            sx, sy, sw, sh = shapes[src_id]
            tx, ty, tw, th = shapes[throw_id]
            # Only relevant when they x-overlap (same column → vertical routing)
            if not ((sx < tx + tw) and (sx + sw > tx)):
                continue
            # Check whether any element sits between source_bottom and throw_top
            src_bottom = sy + sh
            throw_top  = ty
            src_lid    = _la_inner.get(src_id)
            blocked    = any(
                oid not in (src_id, throw_id)
                and _la_inner.get(oid) == src_lid
                and (ox < tx + tw) and (ox + ow > tx)   # x-overlaps throw
                and oy < throw_top and (oy + oh) > src_bottom
                for oid, (ox, oy, ow, oh) in shapes.items()
            )
            if blocked:
                # Reposition throw to the right of source at source's y level
                new_x = sx + sw + H_GAP // 4
                new_y = sy + (sh - th) // 2
                shapes[throw_id] = (int(new_x), int(new_y), tw, th)

    return shapes, pool_shapes


# ── DI builder ────────────────────────────────────────────────────────────────

def _wp(edge, x, y):
    wp = _sub(edge, DDI + "waypoint")
    wp.set("x", str(int(x)))
    wp.set("y", str(int(y)))


def _route_waypoints(sx, sy, sw, sh, tx, ty, tw, th,
                     src_lid, tgt_lid, lane_bounds):
    """
    Compute the waypoint list for a sequence flow.

    Strategy matrix
    ───────────────
    x_overlap + source above target  → vertical down  (bottom-centre → top-centre)
    x_overlap + source below target  → vertical up    (top-centre → bottom-centre)
    backward  same-lane              → U-path in lane bottom margin
    backward  cross-lane             → U-path below both elements
    forward   cross-lane             → L-shape: horizontal at source y, vertical at target x
    forward   same-lane skip         → top-of-lane detour (avoids intermediate elements)
    default   (adjacent, same lane)  → right-centre → left-centre
    """
    x_overlap   = (sx < tx + tw) and (sx + sw > tx)
    is_backward = (not x_overlap) and (sx > tx)
    is_cross    = bool(src_lid and tgt_lid and src_lid != tgt_lid)

    # ── Vertically stacked in same column ─────────────────────────────────────
    if x_overlap and (sy + sh) <= ty:
        return [(sx + sw / 2, sy + sh), (tx + tw / 2, ty)]

    if x_overlap and sy >= (ty + th):
        return [(sx + sw / 2, sy), (tx + tw / 2, ty + th)]

    # ── Backward flows ────────────────────────────────────────────────────────
    if is_backward:
        if not is_cross and src_lid and src_lid in lane_bounds:
            # Same-lane backward: U-path in the bottom margin of the lane.
            # V_PAD=55 guarantees clear space below the element row.
            _, lane_bottom = lane_bounds[src_lid]
            route_y = lane_bottom - 10
        else:
            # Cross-lane backward (should have been caught by link-event pass,
            # but keep a safe fallback).
            route_y = max(sy + sh, ty + th) + 25
        return [
            (sx + sw, sy + sh / 2),
            (sx + sw, route_y),
            (tx,      route_y),
            (tx,      ty + th / 2),
        ]

    # ── Forward cross-lane ────────────────────────────────────────────────────
    # Short jump (adjacent columns): L-shape — horizontal at source y, then
    # vertical at target x.  Works cleanly when no elements block the horizontal.
    #
    # Long jump (> one column-slot): routing at source y risks piercing elements
    # that sit at that y in intermediate columns.  Use a 4-point lane-boundary
    # path instead: rise/fall to the shared boundary, cross horizontally there
    # (above/below all elements), then continue to the target.
    min_skip_px = TASK_W + H_GAP + 10   # ≈ one column + gap
    if is_cross:
        mid_y = sy + sh / 2
        if (tx - (sx + sw)) > min_skip_px and src_lid in lane_bounds:
            src_top, src_bottom = lane_bounds[src_lid]
            tgt_top = lane_bounds.get(tgt_lid, (ty, ty + th))[0]
            # boundary_y sits just inside the source lane, near the shared edge
            if src_top > tgt_top:          # source is the lower lane
                boundary_y = src_top + 10
            else:                          # source is the upper lane
                boundary_y = src_bottom - 10
            return [
                (sx + sw, mid_y),
                (sx + sw, boundary_y),
                (tx,      boundary_y),
                (tx,      ty + th / 2),
            ]
        return [
            (sx + sw, mid_y),
            (tx,      mid_y),
            (tx,      ty + th / 2),
        ]

    # ── Same-lane forward skip ────────────────────────────────────────────────
    # If target is more than one column-slot away, a straight line would pass
    # through intermediate elements at the same y.
    #
    # Routing direction depends on which lane we are in:
    # • Topmost lane (lane_top ≈ 0): detour via lane top (+10) — free space
    #   above elements, away from the inter-lane boundary.
    # • Lower lanes: detour via lane bottom (−10) — avoids conflicting with
    #   cross-lane vertical flows that rise through the upper portion of the lane.
    if (tx - (sx + sw)) > min_skip_px and src_lid and src_lid in lane_bounds:
        lane_top, lane_bottom = lane_bounds[src_lid]
        if lane_top < 10:                  # topmost lane
            route_y = lane_top + 10
        else:                              # lower lane — use bottom margin
            route_y = lane_bottom - 10
        return [
            (sx + sw, sy + sh / 2),
            (sx + sw, route_y),
            (tx,      route_y),
            (tx,      ty + th / 2),
        ]

    # ── Default: adjacent columns, straight line ──────────────────────────────
    return [(sx + sw, sy + sh / 2), (tx, ty + th / 2)]


def _label_pos(wps):
    """
    Return (x, y) for a BPMNLabel Bounds origin, placed at the midpoint of the
    longest segment in the waypoint list.
    """
    if len(wps) < 2:
        return (int(wps[0][0]) - 30 if wps else 0, 0)
    best_len, best_mid = 0, wps[0]
    for i in range(len(wps) - 1):
        x1, y1 = wps[i]
        x2, y2 = wps[i + 1]
        seg_len = abs(x2 - x1) + abs(y2 - y1)
        if seg_len > best_len:
            best_len = seg_len
            best_mid = ((x1 + x2) / 2, (y1 + y2) / 2)
    return (int(best_mid[0]) - 30, int(best_mid[1]) - 16)


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
        # Label placement strategy:
        # • Events (small circles): label above, extra width so text doesn't clip
        # • Gateways (diamonds): label below, wider area for longer names
        # • Tasks / sub-processes: bounds match shape — bpmn-js word-wraps inside
        _event_types   = ("startEvent", "endEvent",
                          "intermediateThrowEvent", "intermediateCatchEvent")
        _gateway_types = ("exclusiveGateway", "parallelGateway", "inclusiveGateway",
                          "eventBasedGateway", "complexGateway")
        if el.type in _event_types:
            lb.set("x", str(int(x - 15))); lb.set("y", str(int(y - 30)))
            lb.set("width",  str(int(w + 30))); lb.set("height", "28")
        elif el.type in _gateway_types:
            lb.set("x", str(int(x - 10))); lb.set("y", str(int(y + h + 2)))
            lb.set("width",  str(int(w + 20))); lb.set("height", "30")
        else:
            lb.set("x", str(int(x))); lb.set("y", str(int(y)))
            lb.set("width",  str(int(w))); lb.set("height", str(int(h)))

    # ── Lane bounds for smart routing ─────────────────────────────────────────
    _la = _assign_lanes(bpmn)
    _lb: dict = {}   # {lane_id: (y_top, y_bottom)}
    if bpmn.pools:
        for _lane in bpmn.pools[0].lanes:
            if _lane.id in pool_shapes:
                _lx, _ly, _lw, _lh = pool_shapes[_lane.id]
                _lb[_lane.id] = (_ly, _ly + _lh)

    for flow in bpmn.flows:
        src = shapes.get(flow.source)
        tgt = shapes.get(flow.target)
        if not src or not tgt or not _valid(src) or not _valid(tgt):
            continue
        edge = _sub(plane, DI + "BPMNEdge",
                    {"id": flow.id + "_di", "bpmnElement": flow.id})
        sx, sy, sw, sh = src
        tx, ty, tw, th = tgt

        wps = _route_waypoints(sx, sy, sw, sh, tx, ty, tw, th,
                               _la.get(flow.source), _la.get(flow.target), _lb)
        for wx, wy in wps:
            _wp(edge, wx, wy)

        if flow.name:
            lx, ly = _label_pos(wps)
            lbl = _sub(edge, DI + "BPMNLabel")
            _sub(lbl, DC + "Bounds", {
                "x": str(lx), "y": str(ly),
                "width": "60", "height": "20",
            })


def analyse_bpmn_crossings(bpmn: BpmnProcess) -> dict:
    """
    Analyse a BpmnProcess for sequence-flow crossing problems and return
    a structured report.  Call this *before* generate_bpmn_xml to get a
    preview of what the link-event elimination pass will fix.

    Returns
    -------
    {
      "total_flows":          int,
      "cross_lane_flows":     [ {id, source, source_name, target, target_name,
                                 src_lane, tgt_lane, lane_span} ],
      "geometric_crossings":  [ {flow_a, name_a, flow_b, name_b} ],
      "lane_spanning":        [ {id, source, source_name, target, target_name,
                                 src_lane, tgt_lane, lane_span} ],
      "element_lane_issues":  [ {element_id, name, lane, issue} ],
      "will_use_link_events": bool,
      "link_pairs_needed":    int,
      "summary":              str    # human-readable, pt-BR
    }
    """
    lane_assignment = _assign_lanes(bpmn)
    non_boundary    = [e for e in bpmn.elements if e.type != "boundaryEvent"]
    el_map          = {e.id: e for e in bpmn.elements}

    # Compute layout so we have real coordinates
    shapes, _ = _compute_layout(bpmn, lane_assignment)

    pool       = bpmn.pools[0] if bpmn.pools else None
    lanes      = pool.lanes    if pool       else []
    lane_index = {lane.id: idx for idx, lane in enumerate(lanes)}
    lane_name  = {lane.id: lane.name for lane in lanes}

    def el_name(eid):
        return el_map[eid].name if eid in el_map else eid

    # ── Cross-lane flows ──────────────────────────────────────────────────────
    cross_lane_flows = []
    for f in bpmn.flows:
        src_lid = lane_assignment.get(f.source)
        tgt_lid = lane_assignment.get(f.target)
        if not src_lid or not tgt_lid or src_lid == tgt_lid:
            continue
        si   = lane_index.get(src_lid, -1)
        ti   = lane_index.get(tgt_lid, -1)
        span = abs(si - ti) if (si >= 0 and ti >= 0) else 1
        cross_lane_flows.append({
            "id":          f.id,
            "source":      f.source,
            "source_name": el_name(f.source),
            "target":      f.target,
            "target_name": el_name(f.target),
            "name":        f.name or "",
            "src_lane":    lane_name.get(src_lid, src_lid),
            "tgt_lane":    lane_name.get(tgt_lid, tgt_lid),
            "lane_span":   span,
        })

    # ── Geometric crossings ───────────────────────────────────────────────────
    segs = {}
    for f in bpmn.flows:
        s = _edge_segment(f, shapes)
        if s:
            segs[f.id] = s

    geometric_pairs = []
    flist = list(segs.items())
    for i in range(len(flist)):
        fid_a, seg_a = flist[i]
        for j in range(i + 1, len(flist)):
            fid_b, seg_b = flist[j]
            if _segments_intersect(seg_a, seg_b):
                fa = next((f for f in bpmn.flows if f.id == fid_a), None)
                fb = next((f for f in bpmn.flows if f.id == fid_b), None)
                geometric_pairs.append({
                    "flow_a":  fid_a,
                    "name_a":  f"{el_name(fa.source)} → {el_name(fa.target)}" if fa else fid_a,
                    "flow_b":  fid_b,
                    "name_b":  f"{el_name(fb.source)} → {el_name(fb.target)}" if fb else fid_b,
                })

    # ── Lane-spanning flows (visual overlaps) ─────────────────────────────────
    lane_spanning = [f for f in cross_lane_flows if f["lane_span"] >= 2]

    # ── Element lane issues ───────────────────────────────────────────────────
    # Flag elements that are likely in the wrong lane:
    #   • endEvent not in the last lane used by majority of terminal elements
    #   • startEvent not in the first lane
    #   • Any element whose assigned lane differs from its declared .lane field
    element_lane_issues = []
    for el in bpmn.elements:
        if el.type == "boundaryEvent":
            continue
        assigned_lid = lane_assignment.get(el.id)
        if not assigned_lid:
            continue
        assigned_lane_name = lane_name.get(assigned_lid, assigned_lid)

        # Check declared lane on element vs assigned lane
        declared = (el.lane or "").strip().lower()
        assigned  = assigned_lane_name.strip().lower()
        if declared and declared != assigned:
            element_lane_issues.append({
                "element_id": el.id,
                "name":       el.name,
                "type":       el.type,
                "declared_lane":  el.lane,
                "assigned_lane":  assigned_lane_name,
                "issue": f"Elemento declarado na lane '{el.lane}' mas atribuído a '{assigned_lane_name}'",
            })

        # Additional: end/start events in unexpected lanes
        if el.type == "endEvent":
            # Find what lane the majority of the last few elements are in
            predecessors = [f.source for f in bpmn.flows if f.target == el.id]
            if predecessors:
                pred_lanes = [lane_assignment.get(p) for p in predecessors if lane_assignment.get(p)]
                if pred_lanes and assigned_lid not in pred_lanes:
                    pred_names = [lane_name.get(l, l) for l in pred_lanes]
                    element_lane_issues.append({
                        "element_id": el.id,
                        "name":       el.name,
                        "type":       el.type,
                        "declared_lane":  el.lane,
                        "assigned_lane":  assigned_lane_name,
                        "issue": f"End Event na lane '{assigned_lane_name}' mas predecessores estão em {pred_names}",
                    })

    # ── What link-event pass will flag ────────────────────────────────────────
    crossing_ids = _detect_crossings(bpmn.flows, shapes, lane_assignment, pool)
    link_pairs   = len(crossing_ids)

    # ── Human-readable summary ────────────────────────────────────────────────
    lines = []
    lines.append(
        f"Diagrama contém {len(bpmn.flows)} sequence flows, "
        f"{len(cross_lane_flows)} cross-lane e "
        f"{len(non_boundary)} elementos."
    )

    # Geometric crossings
    if geometric_pairs:
        lines.append(f"\n🔴 {len(geometric_pairs)} cruzamento(s) geométrico(s) — segmentos que se intersectam fisicamente:")
        for p in geometric_pairs:
            lines.append(f"   • {p['name_a']}   ✕   {p['name_b']}")
    else:
        lines.append("\n✅ Nenhum cruzamento geométrico estrito detectado.")

    # Lane-spanning
    if lane_spanning:
        lines.append(
            f"\n🟡 {len(lane_spanning)} flow(s) com sobreposição visual "
            f"(pulam lane intermediária, span ≥ 2):"
        )
        for f in lane_spanning:
            direction = "↓" if lane_index.get(lane_assignment.get(bpmn.flows[0].source if bpmn.flows else ""), 0) <= \
                                lane_index.get(lane_assignment.get(bpmn.flows[0].target if bpmn.flows else ""), 0) \
                                else "↑"
            si = lane_index.get(lane_assignment.get(f["source"], ""), -1)
            ti = lane_index.get(lane_assignment.get(f["target"], ""), -1)
            arrow = "↓" if ti >= si else "↑"
            lines.append(
                f"   • {f['source_name']} → {f['target_name']}"
                f"  ({f['src_lane']} {arrow} {f['tgt_lane']}, span={f['lane_span']})"
            )
    else:
        lines.append("\n✅ Nenhuma sobreposição visual por lane-spanning detectada.")

    # Element lane issues
    seen_issues = set()
    unique_issues = []
    for issue in element_lane_issues:
        key = (issue["element_id"], issue["issue"])
        if key not in seen_issues:
            seen_issues.add(key)
            unique_issues.append(issue)
    element_lane_issues = unique_issues

    if element_lane_issues:
        lines.append(f"\n⚠️  {len(element_lane_issues)} elemento(s) com lane suspeita:")
        for iss in element_lane_issues:
            lines.append(f"   • [{iss['type']}] \"{iss['name']}\": {iss['issue']}")

    # Link events outcome
    if link_pairs:
        lines.append(
            f"\n🔧 Ação: {link_pairs} flow(s) serão substituídos por pares de "
            f"Link Events (intermediateThrowEvent + intermediateCatchEvent) "
            f"para eliminar cruzamentos visuais."
        )
    else:
        lines.append("\n✅ Nenhuma substituição por Link Events necessária.")

    return {
        "total_flows":          len(bpmn.flows),
        "cross_lane_flows":     cross_lane_flows,
        "geometric_crossings":  geometric_pairs,
        "lane_spanning":        lane_spanning,
        "element_lane_issues":  element_lane_issues,
        "will_use_link_events": link_pairs > 0,
        "link_pairs_needed":    link_pairs,
        "summary":              "\n".join(lines),
    }


def _make_defs():
    """
    Create the root <bpmn:definitions> element.

    ET.register_namespace already causes Python to emit xmlns:bpmn,
    xmlns:bpmndi, xmlns:dc, xmlns:di automatically on serialisation.
    We must NOT also add them as explicit attributes or they appear twice
    (which is well-formed XML but rejected by strict parsers like lxml /
    Python's own ET.fromstring).

    We only declare:
      • xmlns  = default namespace (needed so un-prefixed refs resolve)
      • xmlns:xsi (not registered via register_namespace)
    """
    return ET.Element(B + "definitions", {
        "xmlns":           _NS["bpmn"],     # default ns — not auto-emitted
        "xmlns:xsi":       _NS["xsi"],      # xsi not registered separately
        "targetNamespace": "http://process2diagram.io/bpmn",
        "id":              "definitions_1",
        "exporter":        "Process2Diagram",
        "exporterVersion": "3.0",
    })


def _build_process_xml(defs, bpmn, process_id, lane_assignment):
    """Build and append the <process> element (and laneSet) to defs."""
    proc = _sub(defs, B + "process", {
        "id": process_id, "name": bpmn.name,
        "isExecutable": "false", "processType": "None",
    })
    if bpmn.documentation:
        _sub(proc, B + "documentation", {}).text = bpmn.documentation

    if bpmn.pools:
        pool = bpmn.pools[0]
        # Exclude synthetic layout lanes from the BPMN process XML
        real_lanes = [l for l in pool.lanes if not l.id.endswith(_SYN_LANE_SUFFIX)]
        if real_lanes:
            lset = _sub(proc, B + "laneSet", {"id": pool.id + "_lset"})
            lane_members = {lane.id: [] for lane in real_lanes}
            for eid, lid in lane_assignment.items():
                if lid in lane_members:
                    lane_members[lid].append(eid)
            for lane in real_lanes:
                ln = _sub(lset, B + "lane", {"id": lane.id, "name": lane.name})
                for eid in lane_members[lane.id]:
                    _sub(ln, B + "flowNodeRef", {}).text = eid

    for el in bpmn.elements:
        _build_el(proc, el)
    for flow in bpmn.flows:
        _build_flow(proc, flow)
    return proc


def _is_multi_pool(bpmn: BpmnProcess) -> bool:
    """True when each pool carries its own elements/flows (collaboration mode)."""
    return bool(bpmn.pools) and any(pool.elements for pool in bpmn.pools)


_SYN_LANE_SUFFIX = "_syn_main"   # synthetic single-lane marker for pools without lanes


def _pool_as_process(pool: BpmnPool) -> BpmnProcess:
    """
    Wrap a single pool's elements + flows in a thin BpmnProcess so that the
    existing _assign_lanes / _compute_layout / _apply_link_events functions,
    which all operate on BpmnProcess, work without modification per-pool.

    When the pool has no lanes, a synthetic single lane is injected so that
    _compute_layout (which requires at least one lane to position elements)
    produces valid coordinates.  The synthetic lane is NOT emitted in the DI
    output — it is identified by the _SYN_LANE_SUFFIX marker.
    """
    lanes = pool.lanes
    if not lanes and pool.elements:
        syn_lane = BpmnLane(
            id=pool.id + _SYN_LANE_SUFFIX,
            name="",
            element_ids=[el.id for el in pool.elements
                         if el.type != "boundaryEvent"],
        )
        lanes = [syn_lane]
    return BpmnProcess(
        name=pool.name,
        elements=pool.elements,   # intentional reference — mutations propagate
        flows=pool.flows,         # intentional reference
        pools=[BpmnPool(id=pool.id, name=pool.name, lanes=lanes)],
    )


def _generate_bpmn_xml_multi(bpmn: BpmnProcess) -> str:
    """
    Generate BPMN 2.0 XML for a collaboration with N pools stacked vertically.

    Pipeline per pool
    -----------------
    1. Assign lanes  (per pool, using existing _assign_lanes)
    2. Compute column-based layout
    3. Link-event crossing elimination (within each pool's sequence flows)
    4. Apply y_offset so pools don't overlap vertically

    Message flows are rendered as dashed BPMNEdge entries in the DI section.
    """
    collab_id = "collab_1"

    # ── Per-pool bookkeeping ──────────────────────────────────────────────────
    pool_procs:         list[BpmnProcess]       = []
    lane_assignments:   list[dict]              = []
    process_ids:        list[str]               = []

    for i, pool in enumerate(bpmn.pools):
        pool_proc  = _pool_as_process(pool)
        process_id = f"process_{i + 1}"
        la         = _assign_lanes(pool_proc)
        pool_procs.append(pool_proc)
        lane_assignments.append(la)
        process_ids.append(process_id)

    # ── Pass 1: build XML skeleton ────────────────────────────────────────────
    defs   = _make_defs()
    collab = _sub(defs, B + "collaboration", {"id": collab_id})
    for i, pool in enumerate(bpmn.pools):
        _build_process_xml(defs, pool_procs[i], process_ids[i], lane_assignments[i])
        _sub(collab, B + "participant", {
            "id": pool.id, "name": pool.name, "processRef": process_ids[i],
        })
    for mf in bpmn.message_flows:
        mf_el = _sub(collab, B + "messageFlow", {
            "id": mf.id, "sourceRef": mf.source, "targetRef": mf.target,
        })
        if mf.name:
            mf_el.set("name", mf.name)

    # ── Pass 2: layout + crossing elimination per pool ────────────────────────
    all_shapes:      dict = {}   # element_id → (x, y, w, h) absolute
    all_pool_shapes: dict = {}   # pool_id / lane_id → (x, y, w, h) absolute
    MAX_ITERATIONS = 3
    y_offset = 0

    for i, pool in enumerate(bpmn.pools):
        pp = pool_procs[i]
        la = lane_assignments[i]

        shapes, pool_shapes = _compute_layout(pp, la)
        for _iter in range(MAX_ITERATIONS):
            if not _apply_link_events(pp, la, shapes):
                break
            shapes, pool_shapes = _compute_layout(pp, la)

        # Synchronise pool.elements / pool.flows after link-event injection
        pool.elements = pp.elements
        pool.flows    = pp.flows

        # Compute this pool's total height
        pool_h = pool_shapes.get(pool.id, (0, 0, 0, MIN_LANE_H))[3]

        # Apply y_offset
        for eid, (x, y, w, h) in shapes.items():
            all_shapes[eid] = (x, y + y_offset, w, h)
        for pid, (x, y, w, h) in pool_shapes.items():
            all_pool_shapes[pid] = (x, y + y_offset, w, h)

        y_offset += pool_h + POOL_GAP

    # ── Pass 3: rebuild defs with updated elements (link events added) ────────
    defs   = _make_defs()
    collab = _sub(defs, B + "collaboration", {"id": collab_id})
    for i, pool in enumerate(bpmn.pools):
        _build_process_xml(defs, pool_procs[i], process_ids[i], lane_assignments[i])
        _sub(collab, B + "participant", {
            "id": pool.id, "name": pool.name, "processRef": process_ids[i],
        })
    for mf in bpmn.message_flows:
        mf_el = _sub(collab, B + "messageFlow", {
            "id": mf.id, "sourceRef": mf.source, "targetRef": mf.target,
        })
        if mf.name:
            mf_el.set("name", mf.name)

    # ── Pass 4: build DI ──────────────────────────────────────────────────────
    diagram = _sub(defs, DI + "BPMNDiagram", {"id": "diagram_1"})
    plane   = _sub(diagram, DI + "BPMNPlane",
                   {"id": "plane_1", "bpmnElement": collab_id})

    # Synthetic lanes are not real BPMN lanes — skip them in DI
    real_lane_ids = {lane.id for pool in bpmn.pools for lane in pool.lanes}
    _event_types  = ("startEvent", "endEvent",
                     "intermediateThrowEvent", "intermediateCatchEvent")

    # Pool and lane shapes
    for eid, (x, y, w, h) in all_pool_shapes.items():
        if eid.endswith(_SYN_LANE_SUFFIX):
            continue   # synthetic layout lane — not a real BPMN lane
        is_lane = eid in real_lane_ids
        shape   = _sub(plane, DI + "BPMNShape",
                       {"id": eid + "_di", "bpmnElement": eid,
                        "isHorizontal": "true"})
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
    all_elements = [el for pool in bpmn.pools for el in pool.elements]
    for el in all_elements:
        if el.id not in all_shapes:
            continue
        coords = all_shapes[el.id]
        if not _valid(coords):
            continue
        x, y, w, h = coords
        shape = _sub(plane, DI + "BPMNShape",
                     {"id": el.id + "_di", "bpmnElement": el.id})
        b = _sub(shape, DC + "Bounds")
        b.set("x", str(int(x))); b.set("y", str(int(y)))
        b.set("width", str(int(w))); b.set("height", str(int(h)))
        lbl = _sub(shape, DI + "BPMNLabel")
        lb  = _sub(lbl, DC + "Bounds")
        if el.type in _event_types:
            lb.set("x", str(int(x - 15))); lb.set("y", str(int(y - 30)))
            lb.set("width",  str(int(w + 30))); lb.set("height", "28")
        elif "Gateway" in el.type:
            lb.set("x", str(int(x - 10))); lb.set("y", str(int(y + h + 2)))
            lb.set("width",  str(int(w + 20))); lb.set("height", "30")
        else:
            lb.set("x", str(int(x))); lb.set("y", str(int(y)))
            lb.set("width",  str(int(w))); lb.set("height", str(int(h)))

    # ── Lane bounds for smart routing (multi-pool) ────────────────────────────
    _all_la: dict = {}
    for la in lane_assignments:
        _all_la.update(la)
    _all_lb: dict = {}   # {lane_id: (y_top, y_bottom)} with y_offset applied
    real_lane_ids_set = {lane.id for pool in bpmn.pools for lane in pool.lanes
                         if not lane.id.endswith(_SYN_LANE_SUFFIX)}
    for lid in real_lane_ids_set:
        if lid in all_pool_shapes:
            _lx, _ly, _lw, _lh = all_pool_shapes[lid]
            _all_lb[lid] = (_ly, _ly + _lh)

    # Sequence flow edges (per pool)
    all_flows = [f for pool in bpmn.pools for f in pool.flows]
    for flow in all_flows:
        src = all_shapes.get(flow.source)
        tgt = all_shapes.get(flow.target)
        if not src or not tgt or not _valid(src) or not _valid(tgt):
            continue
        edge = _sub(plane, DI + "BPMNEdge",
                    {"id": flow.id + "_di", "bpmnElement": flow.id})
        sx, sy, sw, sh = src
        tx, ty, tw, th = tgt

        wps = _route_waypoints(sx, sy, sw, sh, tx, ty, tw, th,
                               _all_la.get(flow.source), _all_la.get(flow.target),
                               _all_lb)
        for wx, wy in wps:
            _wp(edge, wx, wy)

        if flow.name:
            lx, ly = _label_pos(wps)
            lbl = _sub(edge, DI + "BPMNLabel")
            _sub(lbl, DC + "Bounds", {
                "x": str(lx), "y": str(ly),
                "width": "60", "height": "20",
            })

    # Message flow edges — vertical routing between pools
    for mf in bpmn.message_flows:
        src = all_shapes.get(mf.source)
        tgt = all_shapes.get(mf.target)
        if not src or not tgt or not _valid(src) or not _valid(tgt):
            continue
        edge = _sub(plane, DI + "BPMNEdge",
                    {"id": mf.id + "_di", "bpmnElement": mf.id})
        sx, sy, sw, sh = src
        tx, ty, tw, th = tgt
        # Route bottom→top or top→bottom depending on pool order
        if sy < ty:
            _wp(edge, sx + sw / 2, sy + sh)    # source bottom-centre
            _wp(edge, tx + tw / 2, ty)          # target top-centre
        else:
            _wp(edge, sx + sw / 2, sy)          # source top-centre
            _wp(edge, tx + tw / 2, ty + th)     # target bottom-centre
        if mf.name:
            mid_x = int((sx + sw / 2 + tx + tw / 2) / 2) - 40
            mid_y = int((sy + ty) / 2) - 10
            lbl = _sub(edge, DI + "BPMNLabel")
            _sub(lbl, DC + "Bounds", {
                "x": str(mid_x), "y": str(mid_y),
                "width": "80", "height": "20",
            })

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + \
           ET.tostring(defs, encoding="unicode")


def generate_bpmn_xml(bpmn: BpmnProcess) -> str:
    """
    Generate BPMN 2.0 XML string.
    Save with .bpmn extension to open in Camunda, Bizagi, draw.io, bpmn.io.

    Dispatches to multi-pool path when pools carry their own elements/flows
    (collaboration mode produced by AgentBPMN for multi-participant transcripts).

    Single-pool pipeline
    --------------------
    1. Assign lanes
    2. Build process XML (first pass)
    3. Compute column-based layout → concrete shapes
    4. Iteratively detect crossing edges → replace with Link Event pairs
       (repeat until no new crossings found, max 3 iterations)
    5. Build DI (diagram interchange)
    """
    if _is_multi_pool(bpmn):
        return _generate_bpmn_xml_multi(bpmn)

    process_id = "process_1"
    lane_assignment = _assign_lanes(bpmn)

    # ── Pass 1: build XML skeleton ────────────────────────────────────────────
    defs = _make_defs()

    _build_process_xml(defs, bpmn, process_id, lane_assignment)

    collab_id = None
    if bpmn.pools:
        pool      = bpmn.pools[0]
        collab_id = "collab_1"
        collab    = _sub(defs, B + "collaboration", {"id": collab_id})
        _sub(collab, B + "participant",
             {"id": pool.id, "name": pool.name, "processRef": process_id})

    # ── Pass 2: compute layout ────────────────────────────────────────────────
    shapes, pool_shapes = _compute_layout(bpmn, lane_assignment)

    # ── Pass 3: link-event crossing elimination ──────────────────────────────
    MAX_ITERATIONS = 3
    for _iteration in range(MAX_ITERATIONS):
        if not _apply_link_events(bpmn, lane_assignment, shapes):
            break   # converged — no new crossings

        # Rebuild defs from scratch (avoids duplicate namespace declarations)
        defs = _make_defs()
        _build_process_xml(defs, bpmn, process_id, lane_assignment)

        if collab_id:
            pool   = bpmn.pools[0]
            collab = _sub(defs, B + "collaboration", {"id": collab_id})
            _sub(collab, B + "participant",
                 {"id": pool.id, "name": pool.name, "processRef": process_id})

        shapes, pool_shapes = _compute_layout(bpmn, lane_assignment)

    # ── Pass 4: diagram interchange ───────────────────────────────────────────
    plane_ref = collab_id if collab_id else process_id
    diagram   = _sub(defs, DI + "BPMNDiagram", {"id": "diagram_1"})
    _build_di(diagram, plane_ref, shapes, pool_shapes, bpmn)

    return '<?xml version="1.0" encoding="UTF-8"?>\n' + \
           ET.tostring(defs, encoding="unicode")
