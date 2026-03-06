import xml.etree.ElementTree as ET
from modules.schema import BpmnProcess, BpmnElement, BpmnLane, BpmnPool, SequenceFlow

# ── Namespaces ────────────────────────────────────────────────────────────────
_NS = {
    "bpmn":   "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
    "dc":      "http://www.omg.org/spec/DD/20100524/DC",
    "di":      "http://www.omg.org/spec/DD/20100524/DI",
    "xsi":     "http://www.w3.org/2001/XMLSchema-instance",
}
for _p, _u in _NS.items():
    ET.register_namespace(_p, _u)

B   = "{%s}" % _NS["bpmn"]
DI  = "{%s}" % _NS["bpmndi"]
DC  = "{%s}" % _NS["dc"]
DDI = "{%s}" % _NS["di"]

# ── Layout constants ──────────────────────────────────────────────────────────
TASK_W,  TASK_H   = 120, 80
GW_W,    GW_H     = 50,  50
EV_W,    EV_H     = 36,  36
H_GAP             = 80
V_PAD             = 40
LANE_HEADER_W     = 30
POOL_HEADER_W     = 30
FIRST_X           = 50 
MIN_LANE_H        = 120

def _sub(parent, tag, attribs=None):
    return ET.SubElement(parent, tag, attribs or {})

def _el_size(el):
    t = el.type
    if t in ("startEvent", "endEvent", "intermediateThrowEvent", "intermediateCatchEvent", "boundaryEvent"):
        return EV_W, EV_H
    if "Gateway" in t:
        return GW_W, GW_H
    return TASK_W, TASK_H

# (Nota: As funções _ev_def, _assign_lanes, _build_el, _build_flow, _topo_sort, 
# _sort_lane_elements, _valid e _wp permanecem iguais às suas originais para 
# garantir compatibilidade com seu schema).

def _compute_layout(bpmn, lane_assignment):
    shapes = {}
    pool_shapes = {}
    el_map = {e.id: e for e in bpmn.elements}
    
    if not bpmn.pools:
        # Layout vertical simples
        cur_y = V_PAD
        for e in bpmn.elements:
            if e.type != "boundaryEvent":
                w, h = _el_size(e)
                shapes[e.id] = (FIRST_X, cur_y, w, h)
                cur_y += h + H_GAP
        return shapes, pool_shapes

    pool = bpmn.pools[0]
    lane_order = {lane.id: [] for lane in pool.lanes}
    non_boundary = [e for e in bpmn.elements if e.type != "boundaryEvent"]
    total_order = _topo_sort([e.id for e in non_boundary], bpmn.flows)
    
    for eid in total_order:
        lid = lane_assignment.get(eid)
        if lid in lane_order: lane_order[lid].append(eid)

    max_w = 700
    cur_y = 0
    for lane in pool.lanes:
        eids = _sort_lane_elements(lane_order[lane.id], el_map, bpmn.flows)
        lane_h = max(MIN_LANE_H, TASK_H + (V_PAD * 2))
        
        pool_shapes[lane.id] = (POOL_HEADER_W, cur_y, 2000, lane_h) # Largura dinâmica ideal
        
        cur_x = POOL_HEADER_W + LANE_HEADER_W + FIRST_X
        for eid in eids:
            el = el_map[eid]
            ew, eh = _el_size(el)
            shapes[eid] = (int(cur_x), int(cur_y + (lane_h - eh) / 2), ew, eh)
            cur_x += ew + H_GAP
        cur_y += lane_h
        
    pool_shapes[pool.id] = (0, 0, cur_x + FIRST_X, cur_y)
    return shapes, pool_shapes

def generate_bpmn_xml(bpmn: BpmnProcess) -> str:
    """Gera o XML BPMN 2.0 padrão."""
    defs = ET.Element(B + "definitions", {"targetNamespace": "http://bpmn.io/schema/bpmn"})
    proc = _sub(defs, B + "process", {"id": "process_1", "isExecutable": "false"})
    
    lane_assignment = _assign_lanes(bpmn)
    
    # Adicionar elementos e fluxos
    for el in bpmn.elements: _build_el(proc, el)
    for flow in bpmn.flows: _build_flow(proc, flow)
    
    # Adicionar DI (Diagram Interchange)
    shapes, pool_shapes = _compute_layout(bpmn, lane_assignment)
    diagram = _sub(defs, DI + "BPMNDiagram", {"id": "diagram_1"})
    _build_di(diagram, "process_1", shapes, pool_shapes, bpmn)
    
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(defs, encoding="unicode")

# A função _build_di permanece a mesma da sua versão original, 
# pois é ela quem traduz o dict 'shapes' para o XML de DI.
