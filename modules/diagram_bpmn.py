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
TASK_W,  TASK_H   = 120, 80  # Aumentado H para melhor proporção
GW_W,    GW_H     = 50,  50
EV_W,    EV_H     = 36,  36
H_GAP             = 80
V_PAD             = 40
LANE_HEADER_W     = 30
POOL_HEADER_W     = 30
FIRST_X           = 50 
MIN_LANE_H        = 120

def _el_size(el):
    t = el.type
    if t in ("startEvent", "endEvent", "intermediateThrowEvent", 
             "intermediateCatchEvent", "boundaryEvent"):
        return EV_W, EV_H
    if "Gateway" in t:
        return GW_W, GW_H
    return TASK_W, TASK_H

# ... (Mantenha as funções _sub, _ev_def, _assign_lanes, _build_el, _build_flow, _topo_sort, _sort_lane_elements inalteradas) ...

def _compute_layout(bpmn, lane_assignment):
    shapes = {}
    pool_shapes = {}
    el_map = {e.id: e for e in bpmn.elements}
    
    if not bpmn.pools:
        # Layout simplificado para processos sem pools (mantenha sua lógica original ou adapte)
        return shapes, pool_shapes

    pool = bpmn.pools[0]
    lane_order = {lane.id: [] for lane in pool.lanes}
    
    # Ordenação dos elementos por lane
    non_boundary = [e for e in bpmn.elements if e.type != "boundaryEvent"]
    total_order = _topo_sort([e.id for e in non_boundary], bpmn.flows)
    
    for eid in total_order:
        lid = lane_assignment.get(eid)
        if lid in lane_order:
            lane_order[lid].append(eid)

    # Cálculo de dimensões
    max_lane_width = 0
    lane_heights = {}
    
    for lane in pool.lanes:
        eids = _sort_lane_elements(lane_order[lane.id], el_map, bpmn.flows)
        lane_order[lane.id] = eids # Atualiza com a ordem correta
        
        current_lane_w = POOL_HEADER_W + LANE_HEADER_W + FIRST_X
        for eid in eids:
            ew, _ = _el_size(el_map[eid])
            current_lane_w += ew + H_GAP
        
        max_lane_width = max(max_lane_width, current_lane_w + FIRST_X)
        lane_heights[lane.id] = max(MIN_LANE_H, TASK_H + (V_PAD * 2))

    total_pool_h = sum(lane_heights.values())
    pool_shapes[pool.id] = (0, 0, max_lane_width, total_pool_h)

    # Posicionamento
    current_y = 0
    for lane in pool.lanes:
        lh = lane_heights[lane.id]
        pool_shapes[lane.id] = (POOL_HEADER_W, current_y, max_lane_width - POOL_HEADER_W, lh)
        
        current_x = POOL_HEADER_W + LANE_HEADER_W + FIRST_X
        for eid in lane_order[lane.id]:
            el = el_map[eid]
            ew, eh = _el_size(el)
            # Centralização vertical perfeita na lane
            shapes[eid] = (current_x, current_y + (lh - eh) / 2, ew, eh)
            current_x += ew + H_GAP
            
        current_y += lh

    # Boundary Events (ajustado para colar na borda inferior da task)
    for el in bpmn.elements:
        if el.type == "boundaryEvent" and el.attached_to:
            host = shapes.get(el.attached_to)
            if host:
                hx, hy, hw, hh = host
                shapes[el.id] = (hx + (hw/2), hy + hh - (EV_H/2), EV_W, EV_H)

    return shapes, pool_shapes

# ── Preview Melhorado ─────────────────────────────────────────────────────────

def generate_bpmn_preview(bpmn: BpmnProcess) -> str:
    xml = generate_bpmn_xml(bpmn)
    xml_js = xml.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")

    return f"""<!DOCTYPE html>
<html>
<head>
  <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17/dist/assets/diagram-js.css">
  <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17/dist/assets/bpmn-font/css/bpmn.css">
  <style>
    body, html {{ margin: 0; height: 100%; width: 100%; background: #F4F7F9; overflow: hidden; }}
    #canvas {{ width: 100%; height: 100%; }}
    .buttons {{ position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%); display: flex; gap: 10px; z-index: 1000; }}
    button {{ padding: 8px 16px; border-radius: 8px; border: none; background: #2D3748; color: white; cursor: pointer; font-family: sans-serif; box-shadow: 0 2px 10px rgba(0,0,0,0.2); }}
    button:hover {{ background: #4A5568; }}
  </style>
</head>
<body>
  <div id="canvas"></div>
  <div class="buttons">
    <button onclick="window.bpmnViewer.get('canvas').zoom('fit-viewport')">Resetar Vista</button>
  </div>
  <script src="https://unpkg.com/bpmn-js@17/dist/bpmn-viewer.development.js"></script>
  <script>
    const xml = `{xml_js}`;
    const viewer = new BpmnJS({{ container: '#canvas' }});
    window.bpmnViewer = viewer;

    async function openDiagram() {{
      try {{
        await viewer.importXML(xml);
        viewer.get('canvas').zoom('fit-viewport');
      }} catch (err) {{
        console.error('Erro ao renderizar:', err);
      }}
    }}
    openDiagram();
  </script>
</body>
</html>"""
