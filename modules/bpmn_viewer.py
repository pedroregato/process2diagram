# modules/bpmn_viewer.py
# ─────────────────────────────────────────────────────────────────────────────
# BPMN interactive viewer — presentation layer only, zero business logic.
#
# Extracted from diagram_bpmn.py (original by Pedro Gentil).
# Depends on bpmn_generator.generate_bpmn_xml() for the XML source.
#
# Public API:
#   generate_bpmn_preview(bpmn: BpmnProcess) -> str   (HTML string)
#   preview_from_xml(xml: str)              -> str   (HTML string, raw XML in)
#
# The second entry point allows the viewer to be used independently —
# e.g. loading a .bpmn file from disk without going through the generator.
# ─────────────────────────────────────────────────────────────────────────────

from modules.schema import BpmnProcess
from modules.bpmn_generator import generate_bpmn_xml


# ── HTML/JS template ──────────────────────────────────────────────────────────

_TEMPLATE = """\
<!DOCTYPE html>
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
      position: fixed; top: 8px; right: 8px;
      display: flex; align-items: center; gap: 4px;
      z-index: 100;
    }}
    .tb-btn {{
      width:32px; height:32px; border:1px solid #cbd5e1; background:#fff;
      border-radius:6px; cursor:pointer; font-size:14px;
      display:flex; align-items:center; justify-content:center;
      color:#475569; transition: all 0.15s;
    }}
    .tb-btn:hover {{ background:#f1f5f9; border-color:#94a3b8; }}
    #zoom-label {{ color:#94a3b8; font-size:11px; font-family:monospace; min-width:40px; text-align:center; }}

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
  <button class="tb-btn" id="btn-in"    title="Zoom in">&#43;</button>
  <button class="tb-btn" id="btn-out"   title="Zoom out">&#8722;</button>
  <button class="tb-btn" id="btn-fit"   title="Fit to screen">&#8865;</button>
  <button class="tb-btn" id="btn-reset" title="Reset view">&#8634;</button>
</div>
<div id="zoom-label" style="position:fixed;bottom:8px;left:8px;z-index:100;font-size:11px;color:#94a3b8;pointer-events:none">100% | Scroll: zoom | Drag: mover</div>
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
    zoomLbl.textContent = Math.round(scale * 100) + '% | Scroll: zoom | Drag: mover';
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
    else if (n > 0) {{ setTimeout(() => fitWhenReady(n - 1), 200); }}
  }}

  // Watch for SVG insertion and auto-fit as soon as it's ready
  const observer = new MutationObserver(() => {{
    const svg = document.querySelector('#bpmn-container svg');
    if (svg) {{
      observer.disconnect();
      // Wait for bpmn-js to finish laying out elements
      let attempts = 0;
      const checkAndFit = () => {{
        const vb = svg.viewBox && svg.viewBox.baseVal;
        if (vb && vb.width > 10 && vb.height > 10) {{
          fitToScreen();
        }} else if (attempts < 20) {{
          attempts++;
          setTimeout(checkAndFit, 150);
        }}
      }};
      setTimeout(checkAndFit, 100);
    }}
  }});
  observer.observe(document.getElementById('bpmn-container'), {{ childList: true, subtree: true }});

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
      try {{ viewer.get('zoomScroll')._enabled = false; }} catch(_) {{}}
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


# ── Public API ────────────────────────────────────────────────────────────────

def generate_bpmn_preview(bpmn: BpmnProcess) -> str:
    """
    Generate interactive HTML viewer from a BpmnProcess object.
    Internally calls generate_bpmn_xml() to produce the XML source.
    """
    xml = generate_bpmn_xml(bpmn)
    return preview_from_xml(xml)


def preview_from_xml(xml: str) -> str:
    """
    Generate interactive HTML viewer from a raw BPMN XML string.
    Use this when loading an existing .bpmn file from disk.

    Example:
        xml = Path("process.bpmn").read_text()
        html = preview_from_xml(xml)
    """
    xml_js = xml.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    return _TEMPLATE.format(xml_js=xml_js)
  
