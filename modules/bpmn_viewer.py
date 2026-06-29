# modules/bpmn_viewer.py
# ─────────────────────────────────────────────────────────────────────────────
# BPMN interactive viewer — presentation layer only, zero business logic.
#
# Public API:
#   generate_bpmn_preview(bpmn: BpmnProcess) -> str   (HTML string)
#   preview_from_xml(xml: str)              -> str   (HTML string, raw XML in)
#
# Rendering strategy
# ──────────────────
# bpmn-js JS + CSS are fetched server-side (Python urllib) on first call and
# cached in memory (functools.lru_cache).  The HTML template receives them as
# inline <style> / <script> blocks — no CDN URL inside the iframe at all.
# This avoids the Streamlit Cloud sandbox restriction that blocks external
# <script src="…"> requests from inside components.html() iframes.
#
# Pan/zoom uses bpmn-js's own canvas API (canvas.zoom / moveCanvas) rather
# than a CSS-transform wrapper, which previously conflicted with bpmn-js's
# internal viewport management.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations
import functools
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from modules.schema import BpmnProcess
from modules.bpmn_generator import generate_bpmn_xml

# ── Asset fetching ────────────────────────────────────────────────────────────

_BPMN_JS_URL  = "https://unpkg.com/bpmn-js@17/dist/bpmn-viewer.production.min.js"
_CSS_URLS = [
    "https://unpkg.com/bpmn-js@17/dist/assets/bpmn-js.css",
    "https://unpkg.com/bpmn-js@17/dist/assets/diagram-js.css",
    "https://unpkg.com/bpmn-js@17/dist/assets/bpmn-font/css/bpmn-embedded.css",
]
_FETCH_TIMEOUT = 8   # seconds per request — 4 parallel fetches → max 8s blocking


def _fetch_text(url: str) -> str:
    """Fetch a single URL server-side. Not cached here; _load_bpmn_assets is cached."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "process2diagram/1.0"})
        with urllib.request.urlopen(req, timeout=_FETCH_TIMEOUT) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception:
        return ""


@functools.lru_cache(maxsize=None)
def _load_bpmn_assets() -> tuple[str, str]:
    """Fetch bpmn-js JS + CSS in parallel; cached after first call.

    All 4 URLs are requested concurrently so worst-case blocking is
    _FETCH_TIMEOUT seconds (not 4×_FETCH_TIMEOUT as in the sequential case).
    Falls back to CDN when any individual fetch fails.
    """
    all_urls = [_BPMN_JS_URL] + _CSS_URLS
    results: dict[str, str] = {}

    def _fetch(url: str) -> tuple[str, str]:
        return url, _fetch_text(url)

    with ThreadPoolExecutor(max_workers=len(all_urls)) as pool:
        for url, content in pool.map(_fetch, all_urls):
            results[url] = content

    js  = results.get(_BPMN_JS_URL, "")
    css = "\n".join(results.get(u, "") for u in _CSS_URLS)
    return js, css


# ── HTML template ─────────────────────────────────────────────────────────────
# {js_inline}  — full bpmn-viewer.production.min.js content
# {css_inline} — concatenated bpmn-js + diagram-js + bpmn-embedded CSS
# {xml_js}     — BPMN XML, JS-escaped (backticks / $ escaped)

_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body, html {{ width:100%; height:100%; overflow:hidden; background:#f8fafc; }}

/* bpmn-js manages its own SVG — container must fill the iframe */
#bpmn-container {{
  position: absolute;
  top: 0; left: 0; right: 0; bottom: 42px;   /* leave room for toolbar */
  background: #f8fafc;
}}

#toolbar {{
  position: fixed; bottom: 0; left: 0; right: 0;
  height: 40px;
  display: flex; align-items: center; gap: 4px;
  padding: 0 8px;
  background: rgba(248,250,252,0.95);
  border-top: 1px solid #e2e8f0;
  z-index: 100;
}}
.tb-btn {{
  height: 28px; min-width: 28px; padding: 0 8px;
  border: 1px solid #cbd5e1; background: #fff;
  border-radius: 6px; cursor: pointer; font-size: 13px;
  display: flex; align-items: center; justify-content: center;
  color: #475569; transition: all 0.12s;
  white-space: nowrap;
}}
.tb-btn:hover {{ background: #f1f5f9; border-color: #94a3b8; }}
#zoom-label {{
  color: #94a3b8; font-size: 11px; font-family: monospace;
  min-width: 40px; text-align: center; user-select: none;
}}
.tb-sep {{ width: 1px; height: 20px; background: #e2e8f0; margin: 0 2px; }}
.tb-pan {{ min-width: 24px; padding: 0 5px; font-size: 15px; }}
.tb-hint {{
  margin-left: auto; font-size: 10px; color: #cbd5e1;
  font-family: sans-serif; white-space: nowrap;
}}

#loading {{
  position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%);
  background: white; padding: 12px 24px; border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,.1); color: #64748b;
  font-family: sans-serif; font-size: 14px; z-index: 200;
}}
#err {{
  display: none; position: absolute; top: 16px; left: 50%;
  transform: translateX(-50%);
  background: white; border: 1px solid #fca5a5; border-radius: 8px;
  padding: 16px 24px; max-width: 600px; font-family: monospace; font-size: 12px;
  color: #dc2626; box-shadow: 0 4px 24px rgba(0,0,0,.15); z-index: 300;
}}

/* bpmn-js overrides */
.bjs-powered-by {{ display: none !important; }}
.djs-palette      {{ display: none !important; }}   /* viewer has no palette */
</style>

<!-- bpmn-js CSS inlined server-side — no CDN dependency in iframe -->
<style>{css_inline}</style>
</head>
<body>

<div id="loading">Carregando diagrama BPMN...</div>
<div id="err"></div>

<div id="bpmn-container"></div>

<div id="toolbar">
  <button class="tb-btn" id="btn-fit"   title="Ajustar à tela (tecla 0)">⊞ Ajustar</button>
  <div class="tb-sep"></div>
  <button class="tb-btn" id="btn-in"    title="Zoom in (+)">+</button>
  <span   id="zoom-label">100%</span>
  <button class="tb-btn" id="btn-out"   title="Zoom out (-)">−</button>
  <div class="tb-sep"></div>
  <button class="tb-btn" id="btn-reset" title="Redefinir zoom">↺</button>
  <div class="tb-sep"></div>
  <button class="tb-btn tb-pan" id="btn-left"  title="Mover esquerda (←)">←</button>
  <button class="tb-btn tb-pan" id="btn-up"    title="Mover para cima (↑)">↑</button>
  <button class="tb-btn tb-pan" id="btn-down"  title="Mover para baixo (↓)">↓</button>
  <button class="tb-btn tb-pan" id="btn-right" title="Mover direita (→)">→</button>
  <div class="tb-sep"></div>
  <button class="tb-btn" id="btn-new" title="Abrir em nova janela">↗ Janela</button>
  <span class="tb-hint">Arraste ou setas: mover &nbsp;·&nbsp; Scroll: zoom &nbsp;·&nbsp; 0: ajustar</span>
</div>

<!-- bpmn-js JS inlined server-side — no CDN dependency in iframe -->
<script>{js_inline}</script>

<script>
(function() {{
  const xml     = `{xml_js}`;
  const loading = document.getElementById('loading');
  const errDiv  = document.getElementById('err');
  const zoomLbl = document.getElementById('zoom-label');

  // ── Instantiate viewer ──────────────────────────────────────────────────
  const viewer = new BpmnJS({{
    container: '#bpmn-container',
    // keyboard handled manually below
    keyboard: {{ bindTo: window }},
  }});

  // ── Zoom label helper ───────────────────────────────────────────────────
  function refreshLabel() {{
    try {{
      const z = viewer.get('canvas').zoom();
      zoomLbl.textContent = Math.round(z * 100) + '%';
    }} catch(_) {{}}
  }}

  // ── Import & fit ────────────────────────────────────────────────────────
  viewer.importXML(xml)
    .then(function(result) {{
      loading.style.display = 'none';
      if (result.warnings && result.warnings.length) {{
        console.warn('bpmn-js import warnings:', result.warnings);
      }}
      // Defer fit-viewport until the iframe container has computed dimensions.
      // Calling canvas.zoom('fit-viewport') synchronously inside importXML.then()
      // can fire before the browser has laid out the container (outerW/H = 0),
      // producing scale = diagramW/0 = Infinity → SVGMatrix non-finite error.
      const canvas = viewer.get('canvas');
      setTimeout(function() {{
        try {{
          const vb    = canvas.viewbox();
          const inn   = vb && vb.inner;
          const outer = vb && vb.outer;
          if (inn && outer &&
              isFinite(inn.width) && isFinite(inn.height) &&
              isFinite(outer.width) && isFinite(outer.height) &&
              inn.width > 0 && inn.height > 0 &&
              outer.width > 0 && outer.height > 0) {{
            canvas.zoom('fit-viewport');
          }} else {{
            canvas.zoom(0.75);
          }}
        }} catch(zoomErr) {{
          try {{ canvas.zoom(0.75); }} catch(_) {{}}
        }}
        refreshLabel();
      }}, 150);
    }})
    .catch(function(err) {{
      loading.style.display = 'none';
      errDiv.style.display  = 'block';
      errDiv.innerHTML      = '<b>Erro ao renderizar BPMN:</b><br>' +
                              (err.message || String(err));
    }});

  // ── Keep label in sync with user pan/zoom ───────────────────────────────
  try {{
    viewer.get('eventBus').on('canvas.viewbox.changed', refreshLabel);
  }} catch(_) {{}}

  // ── Toolbar buttons ─────────────────────────────────────────────────────
  function safeZoom(factor) {{
    try {{
      const canvas = viewer.get('canvas');
      canvas.zoom(canvas.zoom() * factor, 'auto');
      refreshLabel();
    }} catch(_) {{}}
  }}
  function fitView() {{
    try {{
      viewer.get('canvas').zoom('fit-viewport');
      refreshLabel();
    }} catch(_) {{}}
  }}
  function safePan(dx, dy) {{
    try {{ viewer.get('canvas').scroll({{ dx: dx, dy: dy }}); }} catch(_) {{}}
  }}
  const PAN_STEP = 120;

  document.getElementById('btn-fit').onclick   = fitView;
  document.getElementById('btn-reset').onclick = fitView;
  document.getElementById('btn-in').onclick    = function() {{ safeZoom(1.2); }};
  document.getElementById('btn-out').onclick   = function() {{ safeZoom(0.8); }};
  document.getElementById('btn-left').onclick  = function() {{ safePan( PAN_STEP, 0); }};
  document.getElementById('btn-right').onclick = function() {{ safePan(-PAN_STEP, 0); }};
  document.getElementById('btn-up').onclick    = function() {{ safePan(0,  PAN_STEP); }};
  document.getElementById('btn-down').onclick  = function() {{ safePan(0, -PAN_STEP); }};
  document.getElementById('btn-new').onclick   = function() {{
    var html='<!DOCTYPE html>'+document.documentElement.outerHTML;
    var blob=new Blob([html],{{type:'text/html;charset=utf-8'}});
    var url=URL.createObjectURL(blob);
    var w=(window.top||window).open(url,'_blank');
    if(!w)window.open(url,'_blank');
  }};

  // ── Keyboard shortcuts ──────────────────────────────────────────────────
  window.addEventListener('keydown', function(e) {{
    if (e.key === '0')                   {{ fitView(); e.preventDefault(); }}
    if (e.key === '+' || e.key === '=')  {{ safeZoom(1.15); e.preventDefault(); }}
    if (e.key === '-')                   {{ safeZoom(0.87); e.preventDefault(); }}
    if (e.key === 'ArrowLeft')           {{ safePan( PAN_STEP, 0); e.preventDefault(); }}
    if (e.key === 'ArrowRight')          {{ safePan(-PAN_STEP, 0); e.preventDefault(); }}
    if (e.key === 'ArrowUp')             {{ safePan(0,  PAN_STEP); e.preventDefault(); }}
    if (e.key === 'ArrowDown')           {{ safePan(0, -PAN_STEP); e.preventDefault(); }}
  }});
}})();
</script>
</body>
</html>"""


# ── Fallback template (CDN) ───────────────────────────────────────────────────
# Used only when server-side fetch of bpmn-js fails (network error, timeout).
# In this case the iframe must still try to load from CDN.

_TEMPLATE_CDN_FALLBACK = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body, html {{ width:100%; height:100%; overflow:hidden; background:#f8fafc; }}
#bpmn-container {{ position:absolute; top:0; left:0; right:0; bottom:42px; background:#f8fafc; }}
#toolbar {{
  position:fixed; bottom:0; left:0; right:0; height:40px;
  display:flex; align-items:center; gap:4px; padding:0 8px;
  background:rgba(248,250,252,.95); border-top:1px solid #e2e8f0; z-index:100;
}}
.tb-btn {{
  height:28px; min-width:28px; padding:0 8px; border:1px solid #cbd5e1;
  background:#fff; border-radius:6px; cursor:pointer; font-size:13px;
  display:flex; align-items:center; justify-content:center; color:#475569;
}}
.tb-btn:hover {{ background:#f1f5f9; }}
#zoom-label {{ color:#94a3b8; font-size:11px; font-family:monospace; min-width:40px; text-align:center; }}
.bjs-powered-by,.djs-palette {{ display:none !important; }}
#loading {{
  position:absolute; top:50%; left:50%; transform:translate(-50%,-50%);
  background:white; padding:12px 24px; border-radius:8px;
  box-shadow:0 2px 8px rgba(0,0,0,.1); color:#64748b; font-family:sans-serif; z-index:200;
}}
</style>
<link rel="stylesheet" href="https://unpkg.com/bpmn-js@17/dist/assets/bpmn-js.css">
<link rel="stylesheet" href="https://unpkg.com/bpmn-js@17/dist/assets/diagram-js.css">
<link rel="stylesheet" href="https://unpkg.com/bpmn-js@17/dist/assets/bpmn-font/css/bpmn-embedded.css">
</head>
<body>
<div id="loading">Carregando diagrama BPMN...</div>
<div id="bpmn-container"></div>
<div id="toolbar">
  <button class="tb-btn" id="btn-fit">⊞ Ajustar</button>
  <button class="tb-btn" id="btn-in">+</button>
  <span id="zoom-label">100%</span>
  <button class="tb-btn" id="btn-out">−</button>
  <button class="tb-btn" id="btn-left"  title="←">←</button>
  <button class="tb-btn" id="btn-up"    title="↑">↑</button>
  <button class="tb-btn" id="btn-down"  title="↓">↓</button>
  <button class="tb-btn" id="btn-right" title="→">→</button>
  <button class="tb-btn" id="btn-new" title="Abrir em nova janela">↗ Janela</button>
</div>
<script src="https://unpkg.com/bpmn-js@17/dist/bpmn-viewer.production.min.js"></script>
<script>
(function(){{
  const xml = `{xml_js}`;
  const viewer = new BpmnJS({{ container:'#bpmn-container', keyboard:{{bindTo:window}} }});
  function refreshLabel(){{ try{{ document.getElementById('zoom-label').textContent = Math.round(viewer.get('canvas').zoom()*100)+'%'; }}catch(_){{}} }}
  function fitView(){{ try{{ var c=viewer.get('canvas'),vb=c.viewbox(),inn=vb&&vb.inner,outer=vb&&vb.outer; if(inn&&outer&&isFinite(inn.width)&&isFinite(inn.height)&&isFinite(outer.width)&&isFinite(outer.height)&&inn.width>0&&inn.height>0&&outer.width>0&&outer.height>0){{c.zoom('fit-viewport');}}else{{c.zoom(0.75);}} refreshLabel(); }}catch(_){{try{{viewer.get('canvas').zoom(0.75);}}catch(__){{}}}} }}
  viewer.importXML(xml).then(function(){{
    document.getElementById('loading').style.display='none';
    setTimeout(fitView,150);
    try{{ viewer.get('eventBus').on('canvas.viewbox.changed',refreshLabel); }}catch(_){{}}
  }}).catch(function(e){{
    document.getElementById('loading').style.display='none';
    document.getElementById('bpmn-container').innerHTML='<p style="color:red;padding:20px">Erro: '+e.message+'</p>';
  }});
  function safePan(dx,dy){{ try{{ viewer.get('canvas').scroll({{dx:dx,dy:dy}}); }}catch(_){{}} }}
  var PS=120;
  document.getElementById('btn-fit').onclick=fitView;
  document.getElementById('btn-in').onclick=function(){{ try{{ var c=viewer.get('canvas'); c.zoom(c.zoom()*1.2,'auto'); refreshLabel(); }}catch(_){{}} }};
  document.getElementById('btn-out').onclick=function(){{ try{{ var c=viewer.get('canvas'); c.zoom(c.zoom()*0.8,'auto'); refreshLabel(); }}catch(_){{}} }};
  document.getElementById('btn-left').onclick=function(){{ safePan(PS,0); }};
  document.getElementById('btn-right').onclick=function(){{ safePan(-PS,0); }};
  document.getElementById('btn-up').onclick=function(){{ safePan(0,PS); }};
  document.getElementById('btn-down').onclick=function(){{ safePan(0,-PS); }};
  document.getElementById('btn-new').onclick=function(){{
    var html='<!DOCTYPE html>'+document.documentElement.outerHTML;
    var blob=new Blob([html],{{type:'text/html;charset=utf-8'}});
    var url=URL.createObjectURL(blob);
    var w=(window.top||window).open(url,'_blank');
    if(!w)window.open(url,'_blank');
  }};
  window.addEventListener('keydown',function(e){{
    if(e.key==='0'){{fitView();e.preventDefault();}}
    if(e.key==='ArrowLeft'){{safePan(PS,0);e.preventDefault();}}
    if(e.key==='ArrowRight'){{safePan(-PS,0);e.preventDefault();}}
    if(e.key==='ArrowUp'){{safePan(0,PS);e.preventDefault();}}
    if(e.key==='ArrowDown'){{safePan(0,-PS);e.preventDefault();}}
  }});
}})();
</script>
</body>
</html>"""


# ── Public API ────────────────────────────────────────────────────────────────

def _escape_xml_for_js(xml: str) -> str:
    """Escape BPMN XML for embedding inside a JS template literal.

    Order matters:
      1. Backslashes first (must precede other escapes).
      2. Backtick / $ — template-literal special chars.
      3. </script> variants — the HTML parser terminates any <script> block at the
         first </script> it sees, regardless of whether it's inside a JS string.
         If BPMN XML contains "</script>" in a task label or attribute, it will
         close the enclosing <script> block mid-parse, producing a SyntaxError in
         the remaining text (which the browser then tries to parse as JavaScript).
    """
    return (
        xml
        .replace("\\", "\\\\")
        .replace("`",  "\\`")
        .replace("$",  "\\$")
        .replace("</script>",  "<\\/script>")
        .replace("</Script>",  "<\\/Script>")
        .replace("</SCRIPT>",  "<\\/SCRIPT>")
    )


def preview_from_xml(xml: str) -> str:
    """Generate interactive HTML viewer from a raw BPMN XML string.

    bpmn-js assets are fetched server-side on first call (cached).
    Falls back to CDN URLs if server-side fetch fails.

    Always applies reformat_bpmn_labels before rendering so that:
    • Missing waypoints are filled with synthetic border-to-border points
      (including messageFlow edges) — prevents bpmn-js from drawing
      sequence flows from the centre of elements.
    • Task label dc:Bounds are ensured to be centred inside shape boxes.
    This guarantees a correct visual regardless of whether the stored XML
    was saved before or after the repair passes were introduced.
    """
    try:
        from modules.bpmn_auto_repair import reformat_bpmn_labels as _rl
        _fixed, _changes = _rl(xml)
        if not any(c.startswith("[ERRO]") for c in _changes):
            xml = _fixed
    except Exception:
        pass

    xml_js = _escape_xml_for_js(xml)

    js, css = _load_bpmn_assets()

    if js:
        # Happy path: assets available inline — no CDN in iframe
        return _TEMPLATE.format(js_inline=js, css_inline=css, xml_js=xml_js)
    else:
        # Fallback: let the iframe try CDN directly
        return _TEMPLATE_CDN_FALLBACK.format(xml_js=xml_js)


def generate_bpmn_preview(bpmn: BpmnProcess) -> str:
    """Generate interactive HTML viewer from a BpmnProcess object."""
    xml = generate_bpmn_xml(bpmn)
    return preview_from_xml(xml)
