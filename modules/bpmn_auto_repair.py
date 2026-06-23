# modules/bpmn_auto_repair.py
# ─────────────────────────────────────────────────────────────────────────────
# Deterministic structural repairs for BPMNModel.
#
# Applied after _enforce_rules() in AgentBPMN.run(), before XML/Mermaid gen.
# Mutates model in-place; returns a RepairReport describing every fix.
#
# Repairs performed:
#   Pass 1 — Remove dangling edges  (source/target references a missing step)
#   Pass 2 — Remove isolated nodes  (no incoming AND no outgoing edges) — loop
#   Pass 3 — Label XOR edges        (infer Sim/Não or generic Opção N)
#   Pass 4 — Bypass redundant GW    (single-in, single-out gateway) — loop
#   Pass 5 — Insert XOR join GW     (task fan-in from common XOR ancestor)
#
# Safety rules:
#   - Never runs if model has ≤ 2 steps (too sparse to repair safely)
#   - Never raises — outer try/except returns empty RepairReport on failure
#   - Collaboration models are repaired pool-by-pool
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.knowledge_hub import BPMNModel, BPMNStep, BPMNEdge

# Runtime import for Pass 5 (XOR join insertion) — placed at module level so
# it picks up sys.path modifications made before the module is imported, and
# fails loudly in development instead of silently skipping the pass.
try:
    from core.knowledge_hub import BPMNStep as _BPMNStep, BPMNEdge as _BPMNEdge
except ImportError:  # pragma: no cover — only occurs outside the app context
    _BPMNStep = None  # type: ignore[assignment]
    _BPMNEdge = None  # type: ignore[assignment]

_GATEWAY_TYPES = {
    "exclusiveGateway", "parallelGateway", "inclusiveGateway",
    "eventBasedGateway", "complexGateway", "gateway",
}

# Keywords used to infer the complementary XOR label
_YES_WORDS = ("sim", "yes", "aprovad", "ok", "true", "valid", "aceito", "sucesso")
_NO_WORDS  = ("não", "nao", "no", "negad", "false", "rejeit", "recusad", "falha")


@dataclass
class RepairReport:
    """Summary of all structural repairs applied to a BPMNModel."""
    repairs: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.repairs)

    def __bool__(self) -> bool:
        return bool(self.repairs)


# ── Public API ────────────────────────────────────────────────────────────────

def repair_bpmn(model: "BPMNModel") -> RepairReport:
    """
    Apply all structural repairs to *model* in-place.
    Returns a RepairReport. Never raises.
    """
    try:
        report = RepairReport()
        if model.is_collaboration:
            for pool in model.pool_models:
                _repair_pool(pool.steps, pool.edges, report,
                             prefix=f"[{pool.name}] ")
        else:
            _repair_pool(model.steps, model.edges, report)
        return report
    except Exception:
        return RepairReport()


# ── Internal repair engine ────────────────────────────────────────────────────

def _repair_pool(
    steps: list,
    edges: list,
    report: RepairReport,
    prefix: str = "",
) -> None:
    """
    Repair one pool (or a single-pool model) in-place.
    *steps* and *edges* are the live list objects from the model/pool —
    modifications via slice assignment propagate back to the caller.
    """
    # ── Pass 1: Remove dangling edges ─────────────────────────────────────────
    step_ids = {s.id for s in steps}
    valid = [e for e in edges if e.source in step_ids and e.target in step_ids]
    removed = len(edges) - len(valid)
    if removed:
        report.repairs.append(
            f"{prefix}Removed {removed} dangling edge(s) "
            f"referencing non-existent step(s)"
        )
        edges[:] = valid

    # ── Pass 2: Remove isolated nodes (loop until stable) ─────────────────────
    while len(steps) > 2:
        out_cnt = {s.id: 0 for s in steps}
        in_cnt  = {s.id: 0 for s in steps}
        for e in edges:
            if e.source in out_cnt:
                out_cnt[e.source] += 1
            if e.target in in_cnt:
                in_cnt[e.target]  += 1

        isolated = [s for s in steps if out_cnt[s.id] == 0 and in_cnt[s.id] == 0]
        if not isolated:
            break
        isolated_ids = {s.id for s in isolated}
        for s in isolated:
            report.repairs.append(
                f"{prefix}Removed isolated node '{s.title}' ({s.id})"
            )
        steps[:] = [s for s in steps if s.id not in isolated_ids]

    # ── Pass 3: Label unlabeled XOR outgoing edges ─────────────────────────────
    out_edges: dict[str, list] = {s.id: [] for s in steps}
    for e in edges:
        if e.source in out_edges:
            out_edges[e.source].append(e)

    for s in steps:
        is_xor = s.is_decision or s.task_type == "exclusiveGateway"
        outs = out_edges.get(s.id, [])
        if not is_xor or len(outs) < 2:
            continue
        unlabeled = [e for e in outs if not (e.label or "").strip()]
        if not unlabeled:
            continue

        labeled = [e for e in outs if (e.label or "").strip()]
        if len(outs) == 2:
            if labeled:
                existing = labeled[0].label.strip().lower()
                if any(w in existing for w in _YES_WORDS):
                    unlabeled[0].label = "Não"
                elif any(w in existing for w in _NO_WORDS):
                    unlabeled[0].label = "Sim"
                else:
                    unlabeled[0].label = "Outro"
            else:
                unlabeled[0].label = "Sim"
                unlabeled[1].label = "Não"
        else:
            # 3+ branches: add generic labels to the unlabeled ones
            start = len(labeled) + 1
            for i, e in enumerate(unlabeled):
                e.label = f"Opção {start + i}"

        report.repairs.append(
            f"{prefix}Added missing XOR label(s) on '{s.title}' ({s.id})"
        )

    # ── Pass 4: Bypass single-in / single-out redundant gateways (loop) ───────
    changed = True
    while changed:
        changed = False

        # Rebuild adjacency from current edges/steps
        out_map: dict[str, list] = {s.id: [] for s in steps}
        in_map:  dict[str, list] = {s.id: [] for s in steps}
        for e in edges:
            if e.source in out_map and e.target in in_map:
                out_map[e.source].append(e)
                in_map[e.target].append(e.source)

        for s in steps:
            is_gw = s.is_decision or s.task_type in _GATEWAY_TYPES
            if not is_gw:
                continue
            ins  = in_map.get(s.id, [])
            outs = out_map.get(s.id, [])
            # Only bypass when exactly 1 predecessor AND 1 successor
            if len(ins) != 1 or len(outs) != 1:
                continue

            gw_id        = s.id
            successor_id = outs[0].target

            # Redirect the predecessor's edge to the successor; drop gateway edges
            new_edges: list = []
            for e in edges:
                if e.target == gw_id:
                    ne = copy.copy(e)
                    ne.target = successor_id
                    new_edges.append(ne)
                elif e.source == gw_id:
                    pass   # drop — replaced by redirected edge above
                else:
                    new_edges.append(e)

            edges[:] = new_edges
            steps[:] = [s2 for s2 in steps if s2.id != gw_id]
            report.repairs.append(
                f"{prefix}Bypassed redundant gateway '{s.title}' ({gw_id})"
            )
            changed = True
            break   # restart loop with fresh adjacency

    # ── Pass 5: Insert XOR join gateway for task fan-in ───────────────────────
    # Pattern: non-gateway step N with in_degree >= 2, where ALL predecessors
    # are non-gateway tasks that share a single common XOR-gateway grandparent.
    # In that case, insert an explicit XOR-join between the branch tasks and N.
    #
    # Algorithm (conservative — only fires on clean 2-hop XOR pattern):
    #   predecessors(N) = [T1, T2, …]     ← all non-gateway
    #   grandparents(Ti) for each Ti       ← set of Ti's predecessors
    #   common_gp = ∩ grandparents(Ti)
    #   if common_gp contains exactly one XOR gateway → insert join
    #
    # Skips AND/OR fan-in (grandparent would be parallelGateway/inclusiveGateway)
    # and any mixed or multi-source patterns.
    _EVENT_TASK_TYPES = {
        "noneStartEvent", "startEvent", "start",
        "noneEndEvent", "endEvent", "end",
        "startMessageEvent", "startTimerEvent",
        "errorEndEvent", "endMessageEvent",
        "intermediateTimerCatchEvent", "intermediateMessageCatchEvent",
        "intermediateMessageThrowEvent",
    }
    _XOR_TYPES = {"exclusiveGateway", "gateway"}

    if _BPMNStep is not None:
        _pass5_changed = True
        while _pass5_changed:
            _pass5_changed = False

            # Rebuild adjacency
            _s_by_id: dict[str, object] = {s.id: s for s in steps}
            _in5:  dict[str, list[str]] = {s.id: [] for s in steps}
            _out5: dict[str, list[str]] = {s.id: [] for s in steps}
            for e in edges:
                if e.source in _in5 and e.target in _in5:
                    _out5[e.source].append(e.target)
                    _in5[e.target].append(e.source)

            for s in list(steps):
                # Must be a non-gateway, non-event task with fan-in >= 2
                if s.task_type in _EVENT_TASK_TYPES:
                    continue
                is_gw = s.is_decision or s.task_type in _GATEWAY_TYPES
                if is_gw:
                    continue
                preds = _in5.get(s.id, [])
                if len(preds) < 2:
                    continue

                # All predecessors must be non-gateway (task-level fan-in)
                if any(
                    (_s_by_id[p].is_decision if p in _s_by_id else False)
                    or (_s_by_id[p].task_type in _GATEWAY_TYPES if p in _s_by_id else False)
                    for p in preds
                ):
                    continue

                # Compute grandparents for each predecessor
                gp_sets = [set(_in5.get(p, [])) for p in preds]
                if not gp_sets:
                    continue
                common_gp = gp_sets[0].intersection(*gp_sets[1:])

                # Must be exactly one common grandparent and it must be XOR
                if len(common_gp) != 1:
                    continue
                gp_id = next(iter(common_gp))
                gp = _s_by_id.get(gp_id)
                if gp is None:
                    continue
                is_xor_gp = gp.is_decision or gp.task_type in _XOR_TYPES
                if not is_xor_gp:
                    continue

                # ── Insert XOR join gateway ──────────────────────────────────
                join_id = f"gw_join_{s.id}"
                if join_id in _s_by_id:
                    continue  # already exists (safety guard)

                join_gw = _BPMNStep(
                    id=join_id,
                    title="",               # join gateways are anonymous per OMG style
                    description="",
                    is_decision=True,
                    task_type="exclusiveGateway",
                    lane=s.lane,
                )

                # Insert join_gw just before target step s in the steps list
                target_idx = next(
                    (i for i, st in enumerate(steps) if st.id == s.id), len(steps)
                )
                steps.insert(target_idx, join_gw)

                # Reroute: pred → s  becomes  pred → join_gw
                # Add: join_gw → s
                new_edges: list = []
                join_edge_added = False
                for e in edges:
                    if e.target == s.id and e.source in preds:
                        ne = copy.copy(e)
                        ne.target = join_id
                        new_edges.append(ne)
                    else:
                        new_edges.append(e)
                    if not join_edge_added and e.target == s.id and e.source in preds:
                        pass  # will add the join→target edge once after loop

                # Add the single edge from join_gw to s
                new_edges.append(_BPMNEdge(source=join_id, target=s.id, label=""))
                edges[:] = new_edges

                report.repairs.append(
                    f"{prefix}Inserted XOR join gateway '{join_id}' before "
                    f"'{s.title}' ({s.id}) — {len(preds)} branches from "
                    f"'{gp.title}' ({gp_id}) now converge properly"
                )
                _pass5_changed = True
                break  # restart with fresh adjacency


# ── DI reformatters (deterministic, no LLM) ──────────────────────────────────

def _bpmn_parse(xml_str: str):
    """Register namespaces + parse. Returns (root, ET module). Raises on error."""
    import io
    import xml.etree.ElementTree as ET

    # Register canonical BPMN prefixes FIRST (including "" for the default
    # namespace) so serialization never produces ns0:/ns1: mangling.
    _CANONICAL = [
        ("",       "http://www.omg.org/spec/BPMN/20100524/MODEL"),
        ("bpmndi", "http://www.omg.org/spec/BPMN/20100524/DI"),
        ("dc",     "http://www.omg.org/spec/DD/20100524/DC"),
        ("di",     "http://www.omg.org/spec/DD/20100524/DI"),
    ]
    for pfx, uri in _CANONICAL:
        ET.register_namespace(pfx, uri)

    # Register any additional namespaces declared in the document
    for _, (pfx, uri) in ET.iterparse(io.StringIO(xml_str), events=["start-ns"]):
        try:
            ET.register_namespace(pfx, uri)
        except ValueError:
            pass  # skip reserved prefixes (xml, xmlns, …)

    return ET.fromstring(xml_str), ET


def _bpmn_serialize(root, xml_str: str, ET) -> str:
    """Serialize root to string, re-attaching original XML declaration."""
    import io
    buf = io.StringIO()
    ET.ElementTree(root).write(buf, encoding="unicode", xml_declaration=False)
    fixed = buf.getvalue()
    stripped = xml_str.lstrip()
    if stripped.startswith("<?xml"):
        decl_end = stripped.index("?>") + 2
        fixed = stripped[:decl_end] + "\n" + fixed
    return fixed


def reformat_bpmn_labels(xml_str: str) -> tuple[str, list[str]]:
    """
    Ensure every task BPMNShape has a BPMNLabel with dc:Bounds centered inside
    the shape box, so bpmn-js renders text inside task boxes regardless of viewer.
    Also normalizes task shape dimensions from old generator constants to the
    current standard (160×90), giving more room for long task names.

    Skips: pools / lanes (isHorizontal="true"), events (~36px), gateways (~50px).
    Task width heuristic: 100px ≤ width ≤ 400px AND not isHorizontal.

    Returns (fixed_xml, changes). Never raises — returns (xml_str, [error]) on error.
    """
    import xml.etree.ElementTree as _ET

    _BPMNDI     = "http://www.omg.org/spec/BPMN/20100524/DI"
    _DC         = "http://www.omg.org/spec/DD/20100524/DC"
    _DI         = "http://www.omg.org/spec/DD/20100524/DI"
    _SHAPE      = f"{{{_BPMNDI}}}BPMNShape"
    _LABEL      = f"{{{_BPMNDI}}}BPMNLabel"
    _BOUNDS     = f"{{{_DC}}}Bounds"
    _EDGE       = f"{{{_BPMNDI}}}BPMNEdge"
    _WAYPOINT   = f"{{{_DI}}}waypoint"
    _TASK_MIN_W = 100
    _TASK_MAX_W = 400   # pools/lanes are much wider (1000-2000px)

    # Known old generator dimension pairs (w, h) → upgrade to current standard
    _STD_W    = 160
    _STD_H    = 90
    _OLD_DIMS = {(150, 80), (120, 60)}

    try:
        root, ET = _bpmn_parse(xml_str)
        fixes:    list[str] = []   # actual structural changes
        verified: int       = 0    # task shapes successfully checked

        # Detect namespace mangling from previous serializations
        if "ns0:" in xml_str or "xmlns:ns0=" in xml_str:
            fixes.append("Namespaces XML normalizados (ns0: → padrão BPMN)")

        for shape in root.iter(_SHAPE):
            # Skip pools and lanes — they carry isHorizontal="true"
            if shape.get("isHorizontal") == "true":
                continue

            bounds = shape.find(_BOUNDS)
            if bounds is None:
                continue
            try:
                w = float(bounds.get("width", "0"))
            except ValueError:
                continue
            if not (_TASK_MIN_W <= w <= _TASK_MAX_W):
                continue  # too narrow (event/gateway) or too wide (pool/lane fallback)

            verified += 1
            elem_id = shape.get("bpmnElement", shape.get("id", "?"))

            # ── Pass A: Normalize old shape dimensions to current standard ────
            try:
                h = float(bounds.get("height", "0"))
            except ValueError:
                h = 0.0
            if (round(w), round(h)) in _OLD_DIMS:
                old_x = float(bounds.get("x", "0"))
                old_y = float(bounds.get("y", "0"))
                # Keep center: shift top-left corner by half the size increase
                bounds.set("x",      str(old_x - (_STD_W - w) / 2))
                bounds.set("y",      str(old_y - (_STD_H - h) / 2))
                bounds.set("width",  str(_STD_W))
                bounds.set("height", str(_STD_H))
                fixes.append(
                    f"Dimensões normalizadas {int(w)}×{int(h)}→{_STD_W}×{_STD_H}: '{elem_id}'"
                )

            # ── Pass B: ensure BPMNLabel has explicit centered dc:Bounds ─────
            # Deterministic centering: explicit dc:Bounds set to shape interior
            # with _LBL_PAD_X/Y inset.  Does NOT rely on bpmn-js auto-centering,
            # which fails for callActivity (the "+" marker reduces text area) and
            # on re-render after XML edits.
            # SNAP_TOL=1px: skip update when bounds are already correct.
            _LBL_PAD_X = 10
            _LBL_PAD_Y = 8
            _SNAP_TOL  = 1
            try:
                _sx = float(bounds.get("x", "0"))
                _sy = float(bounds.get("y", "0"))
                _sw = float(bounds.get("width", "0"))
                _sh = float(bounds.get("height", "0"))
            except ValueError:
                _sx = _sy = _sw = _sh = 0.0
            _exp_lx = int(_sx + _LBL_PAD_X)
            _exp_ly = int(_sy + _LBL_PAD_Y)
            _exp_lw = int(_sw - 2 * _LBL_PAD_X)
            _exp_lh = int(_sh - 2 * _LBL_PAD_Y)

            label = shape.find(_LABEL)
            if label is None:
                label = _ET.SubElement(shape, _LABEL)
                lb = _ET.SubElement(label, _BOUNDS)
                lb.set("x", str(_exp_lx)); lb.set("y", str(_exp_ly))
                lb.set("width", str(_exp_lw)); lb.set("height", str(_exp_lh))
                fixes.append(f"BPMNLabel centrado adicionado: '{elem_id}'")
            else:
                label_bounds = label.find(_BOUNDS)
                if label_bounds is None:
                    lb = _ET.SubElement(label, _BOUNDS)
                    lb.set("x", str(_exp_lx)); lb.set("y", str(_exp_ly))
                    lb.set("width", str(_exp_lw)); lb.set("height", str(_exp_lh))
                    fixes.append(f"Bounds centrados adicionados: '{elem_id}'")
                else:
                    try:
                        _ok = (
                            abs(float(label_bounds.get("x","0"))      - _exp_lx) <= _SNAP_TOL
                            and abs(float(label_bounds.get("y","0"))   - _exp_ly) <= _SNAP_TOL
                            and abs(float(label_bounds.get("width","0"))- _exp_lw) <= _SNAP_TOL
                            and abs(float(label_bounds.get("height","0"))- _exp_lh) <= _SNAP_TOL
                        )
                    except ValueError:
                        _ok = False
                    if not _ok:
                        label_bounds.set("x", str(_exp_lx)); label_bounds.set("y", str(_exp_ly))
                        label_bounds.set("width", str(_exp_lw)); label_bounds.set("height", str(_exp_lh))
                        fixes.append(f"Bounds de label corrigidos para centrado: '{elem_id}'")

        # ── Pass C: Stagger overlapping same-channel skip flows ──────────────
        # Flows with 4 waypoints where wp[1].y ≈ wp[2].y (horizontal detour
        # near the top/bottom of a lane) may overlap when multiple flows share
        # the same y-channel.  Sort by span length (shorter stays, longer gets
        # offset +15 px each) so the skip routes are visually distinct.
        skip_groups: dict[float, list] = {}
        for _edge in root.iter(_EDGE):
            _wps = _edge.findall(_WAYPOINT)
            if len(_wps) != 4:
                continue
            try:
                _y1 = float(_wps[1].get("y", "nan"))
                _y2 = float(_wps[2].get("y", "nan"))
            except ValueError:
                continue
            if abs(_y1 - _y2) < 1:  # horizontal skip segment
                _xa = min(float(_wps[1].get("x", "0")), float(_wps[2].get("x", "0")))
                _xb = max(float(_wps[1].get("x", "0")), float(_wps[2].get("x", "0")))
                skip_groups.setdefault(_y1, []).append((_edge, _wps, _xa, _xb))

        for _skip_y, _group in skip_groups.items():
            if len(_group) < 2:
                continue
            # Sort ascending by horizontal span (shortest stays at original y)
            _group.sort(key=lambda g: g[3] - g[2])
            for _i, (_edge, _wps, _xa, _xb) in enumerate(_group):
                _offset = _i * 30   # 30 px between adjacent skip channels (was 15)
                if _offset == 0:
                    continue
                _new_y = str(int(_skip_y) + _offset)
                _wps[1].set("y", _new_y)
                _wps[2].set("y", _new_y)
                _eid = _edge.get("bpmnElement", _edge.get("id", "?"))
                fixes.append(f"Canal de skip escalonado +{_offset}px: '{_eid}'")

        # ── Pass E: Clamp edge label y inside pool bounds ─────────────────────
        # Skip-channel flows place their label 16 px above the skip line.
        # If the skip line is at y=10 (topmost lane), the label ends up at y=-6
        # — outside the pool bounding box and invisible in bpmn-js.
        # Clamp any edge label y < 5 to y=5.
        _clamp_count = 0
        for _edge in root.iter(_EDGE):
            _lbl = _edge.find(f"{{{_BPMNDI}}}BPMNLabel")
            if _lbl is None:
                continue
            _lb = _lbl.find(f"{{{_DC}}}Bounds")
            if _lb is None:
                continue
            try:
                _ly = float(_lb.get("y", "0"))
            except ValueError:
                continue
            if _ly < 5:
                _lb.set("y", "5")
                _clamp_count += 1
        if _clamp_count:
            fixes.append(
                f"Labels de sequência reposicionados: {_clamp_count} fora dos limites do pool"
            )

        # ── Pass F: Synthetic waypoints for empty BPMNEdges ──────────────────
        # bpmn-js cannot render BPMNEdge elements with zero waypoints.
        # Build a shape-bounds map + sequenceFlow lookup to generate two
        # minimal connection points: right-center of source → left-center of target.
        _BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
        _shape_pos: dict[str, tuple[float, float, float, float]] = {}
        for _shp in root.iter(_SHAPE):
            if _shp.get("isHorizontal") == "true":
                continue
            _bid = _shp.get("bpmnElement")
            _b   = _shp.find(_BOUNDS)
            if not _bid or _b is None:
                continue
            try:
                _shape_pos[_bid] = (
                    float(_b.get("x", "0")), float(_b.get("y", "0")),
                    float(_b.get("width",  "0")), float(_b.get("height", "0")),
                )
            except ValueError:
                pass

        _sf_map: dict[str, tuple[str, str]] = {}
        for _sf in root.iter(f"{{{_BPMN_NS}}}sequenceFlow"):
            _sid = _sf.get("id")
            _sr  = _sf.get("sourceRef")
            _tr  = _sf.get("targetRef")
            if _sid and _sr and _tr:
                _sf_map[_sid] = (_sr, _tr)

        _empty_fixed = 0
        for _edge in root.iter(_EDGE):
            if _edge.findall(_WAYPOINT):
                continue  # already has waypoints
            _sfid = _edge.get("bpmnElement")
            if not _sfid or _sfid not in _sf_map:
                continue
            _src_id, _tgt_id = _sf_map[_sfid]
            _sb = _shape_pos.get(_src_id)
            _tb = _shape_pos.get(_tgt_id)
            if _sb is None or _tb is None:
                continue
            # Right-center of source shape → left-center of target shape
            _wp1 = _ET.SubElement(_edge, _WAYPOINT)
            _wp1.set("x", str(int(_sb[0] + _sb[2])))
            _wp1.set("y", str(int(_sb[1] + _sb[3] / 2)))
            _wp2 = _ET.SubElement(_edge, _WAYPOINT)
            _wp2.set("x", str(int(_tb[0])))
            _wp2.set("y", str(int(_tb[1] + _tb[3] / 2)))
            _empty_fixed += 1
        if _empty_fixed:
            fixes.append(f"Waypoints sintéticos: {_empty_fixed} edge(s) vazia(s) corrigida(s)")

        # ── Pass D: Auto-route diagonal 2-point sequence flows ───────────────
        # Runs AFTER Pass F so that synthetic waypoints added to previously-empty
        # edges are also auto-routed when diagonal (e.g. sf_end / sf_end_1).
        # A BPMNEdge with exactly 2 waypoints where Δx ≠ 0 AND Δy ≠ 0 is a
        # straight diagonal line.  Removing the waypoints lets bpmn-js Manhattan
        # router produce L-shaped paths that avoid crossings.
        # Pure horizontal/vertical 2-point edges (Δx=0 or Δy=0) are preserved.
        _diag_count = 0
        for _edge in root.iter(_EDGE):
            _wps = _edge.findall(_WAYPOINT)
            if len(_wps) != 2:
                continue
            try:
                _x1 = float(_wps[0].get("x", "0")); _y1 = float(_wps[0].get("y", "0"))
                _x2 = float(_wps[1].get("x", "0")); _y2 = float(_wps[1].get("y", "0"))
            except ValueError:
                continue
            if abs(_x2 - _x1) > 1 and abs(_y2 - _y1) > 1:
                for _wp in _wps:
                    _edge.remove(_wp)
                _diag_count += 1
        if _diag_count:
            fixes.append(
                f"Roteamento automático: {_diag_count} fluxo(s) diagonal(is) → bpmn-js L-path"
            )

        # ── Pass G: Separate overlapping exit flows ───────────────────────────
        # When 2+ flows share the same source waypoint AND the same second
        # waypoint, they look like a single arrow until they diverge.
        # Key = (wp0.x, wp0.y, wp1.x, wp1.y) rounded to nearest pixel.
        # Sort overlapping group by final waypoint Y (ascending = going up first),
        # then offset BOTH wp[0].y and wp[1].y by ±SPREAD/2 to fan out from source.
        _exit_groups: dict[tuple[int, int, int, int], list] = {}
        for _edge in root.iter(_EDGE):
            _wps = _edge.findall(_WAYPOINT)
            if len(_wps) < 3:
                continue  # need at least 3 waypoints: source, mid, target
            try:
                _k: tuple[int, int, int, int] = (
                    round(float(_wps[0].get("x", "nan"))),
                    round(float(_wps[0].get("y", "nan"))),
                    round(float(_wps[1].get("x", "nan"))),
                    round(float(_wps[1].get("y", "nan"))),
                )
            except ValueError:
                continue
            _exit_groups.setdefault(_k, []).append((_edge, _wps))

        _overlap_fixed = 0
        for _k, _grp in _exit_groups.items():
            if len(_grp) < 2:
                continue
            # Sort by final waypoint Y so flows going up get negative offset
            _grp.sort(key=lambda pair: float(pair[1][-1].get("y", "0")))
            _n = len(_grp)
            _SPREAD = 18  # px between adjacent overlapping flows
            for _i, (_edge, _wps) in enumerate(_grp):
                _off = int((_i - (_n - 1) / 2) * _SPREAD)
                if _off == 0:
                    continue
                try:
                    _wps[0].set("y", str(int(float(_wps[0].get("y", "0")) + _off)))
                    _wps[1].set("y", str(int(float(_wps[1].get("y", "0")) + _off)))
                    _overlap_fixed += 1
                except ValueError:
                    pass
        if _overlap_fixed:
            fixes.append(f"Saídas sobrepostas separadas: {_overlap_fixed} fluxo(s) ajustado(s)")

        # Always re-serialize: ensures canonical namespaces are applied even
        # when no label fixes were needed (prevents stale ns0: and guarantees
        # bpmn-js receives clean, standardized XML).
        fixed = _bpmn_serialize(root, xml_str, ET)
        if fixes:
            changes = fixes
        else:
            changes = [f"[OK] {verified} task(s) verificada(s) — labels já centralizados"]
        return fixed, changes

    except Exception as exc:
        return xml_str, [f"[ERRO] reformat_bpmn_labels: {exc}"]


def reformat_bpmn_flows(xml_str: str) -> tuple[str, list[str]]:
    """
    Remove waypoints from BPMNEdge elements that have exactly 2 waypoints
    (straight start→end line). bpmn-js Manhattan router then takes over,
    producing L-shaped paths that avoid element collisions and may reduce crossings.
    Edges with 3+ waypoints are preserved (intentional lane-crossing routes).

    NOTE: results vary by diagram — use manually via the "Ajustar Sequências"
    button rather than applying automatically in the pipeline.

    Returns (fixed_xml, changes). Never raises — returns (xml_str, []) on error.
    """
    _BPMNDI   = "http://www.omg.org/spec/BPMN/20100524/DI"
    _DI       = "http://www.omg.org/spec/DD/20100524/DI"
    _EDGE     = f"{{{_BPMNDI}}}BPMNEdge"
    _WAYPOINT = f"{{{_DI}}}waypoint"

    try:
        root, ET = _bpmn_parse(xml_str)
        changes: list[str] = []

        for edge in root.iter(_EDGE):
            waypoints = edge.findall(_WAYPOINT)
            if len(waypoints) != 2:
                continue  # 0 = already auto-routed; 3+ = intentional path
            for wp in waypoints:
                edge.remove(wp)
            elem_id = edge.get("bpmnElement", edge.get("id", "?"))
            changes.append(f"Roteamento automático: '{elem_id}'")

        if not changes:
            return xml_str, []
        return _bpmn_serialize(root, xml_str, ET), changes

    except Exception:
        return xml_str, []


# kept for backwards compatibility — calls labels only (flows is manual-only)
def reformat_bpmn_di(xml_str: str) -> tuple[str, list[str]]:
    return reformat_bpmn_labels(xml_str)
