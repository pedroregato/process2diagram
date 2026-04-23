# modules/bpmn_editor.py
# ─────────────────────────────────────────────────────────────────────────────
# BPMN interactive editor — bpmn-js Modeler injected via CDN.
#
# Public API:
#   editor_from_xml(xml: str, height: int = 700) -> str
#       Returns a self-contained HTML string for use with
#       streamlit.components.v1.html().
#
# Communication strategy:
#   bpmn-js runs inside a sandboxed iframe (st.components.v1.html).
#   There is no direct Python→JS callback channel in Streamlit.
#   The "Export XML" button inside the modeler copies the current XML into
#   a <textarea> displayed below the canvas.  The user copies from there and
#   pastes into a st.text_area outside the iframe.
# ─────────────────────────────────────────────────────────────────────────────

_EDITOR_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    * {{ margin:0; padding:0; box-sizing:border-box; }}
    body, html {{ width:100%; height:100%; background:#f0f4f8; font-family:'Segoe UI',sans-serif; }}

    #toolbar {{
      display:flex; align-items:center; gap:6px;
      padding:6px 10px;
      background:#1e3a5f; border-bottom:2px solid #c97b1a;
    }}
    .tb-btn {{
      padding:4px 12px; border:none; border-radius:5px; cursor:pointer;
      font-size:12px; font-weight:600; transition:background .15s;
    }}
    .tb-btn-primary {{ background:#c97b1a; color:#fff; }}
    .tb-btn-primary:hover {{ background:#e8941a; }}
    .tb-btn-default {{ background:#334e68; color:#d0e0f0; }}
    .tb-btn-default:hover {{ background:#486581; }}
    #tb-title {{ color:#d0e0f0; font-size:12px; flex:1; }}
    #zoom-info {{ color:#8899aa; font-size:11px; font-family:monospace; }}

    #canvas {{
      position:relative;
      width:100%;
      height:{canvas_height}px;
      overflow:hidden;
    }}

    /* bpmn-js modeler container */
    #modeler-container {{
      width:100%; height:100%;
    }}

    /* Style bpmn-js built-in properties */
    .bjs-powered-by {{ display:none !important; }}

    #xml-panel {{
      display:none;
      padding:10px;
      background:#0f2040;
      border-top:2px solid #c97b1a;
    }}
    #xml-panel label {{
      display:block; color:#8bafd0; font-size:11px; font-weight:600;
      letter-spacing:.06em; text-transform:uppercase; margin-bottom:4px;
    }}
    #xml-output {{
      width:100%; height:160px;
      background:#0a1628; color:#a8d8ea;
      border:1px solid #1e3a55; border-radius:5px;
      font-family:'Courier New',monospace; font-size:11px;
      padding:8px; resize:vertical;
    }}
    #xml-hint {{
      color:#5a7a9a; font-size:10px; margin-top:4px;
    }}

    #err-panel {{
      display:none; padding:10px;
      background:#4a0d0d; color:#f87171; font-size:12px;
      border-top:2px solid #dc2626;
    }}
    #loading-overlay {{
      position:absolute; top:0; left:0; right:0; bottom:0;
      background:rgba(10,22,40,.85); display:flex;
      align-items:center; justify-content:center;
      color:#8bafd0; font-size:14px; z-index:1000;
    }}
  </style>

  <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17/dist/assets/bpmn-js.css">
  <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17/dist/assets/diagram-js.css">
  <link rel="stylesheet" href="https://unpkg.com/bpmn-js@17/dist/assets/bpmn-font/css/bpmn-embedded.css">
</head>
<body>

<div id="toolbar">
  <span id="tb-title">🎨 Editor BPMN — edite os elementos e exporte o XML</span>
  <button class="tb-btn tb-btn-default" id="btn-fit" title="Ajustar ao ecrã">⊞ Ajustar</button>
  <button class="tb-btn tb-btn-default" id="btn-undo" title="Desfazer">↩ Desfazer</button>
  <button class="tb-btn tb-btn-default" id="btn-redo" title="Refazer">↪ Refazer</button>
  <button class="tb-btn tb-btn-primary" id="btn-export" title="Exportar XML para copiar">📋 Exportar XML</button>
</div>

<div id="canvas">
  <div id="modeler-container"></div>
  <div id="loading-overlay">Carregando editor BPMN…</div>
</div>

<div id="xml-panel">
  <label>XML exportado — copie e cole no campo abaixo do editor:</label>
  <textarea id="xml-output" readonly spellcheck="false"></textarea>
  <div id="xml-hint">✅ Selecione todo o texto (Ctrl+A) e copie (Ctrl+C), depois cole no campo "XML editado" abaixo.</div>
</div>

<div id="err-panel"></div>

<script src="https://unpkg.com/bpmn-js@17/dist/bpmn-modeler.development.js"></script>
<script>
(function() {{
  const xml      = `{xml_js}`;
  const loading  = document.getElementById('loading-overlay');
  const errPanel = document.getElementById('err-panel');
  const xmlPanel = document.getElementById('xml-panel');
  const xmlOut   = document.getElementById('xml-output');

  const modeler = new BpmnJS({{
    container: '#modeler-container',
    keyboard: {{ bindTo: window }},
  }});

  modeler.importXML(xml)
    .then(() => {{
      loading.style.display = 'none';
      const canvas = modeler.get('canvas');
      canvas.zoom('fit-viewport', 'auto');
    }})
    .catch(err => {{
      loading.style.display = 'none';
      errPanel.style.display = 'block';
      errPanel.textContent = '❌ Erro ao carregar BPMN: ' + err.message;
    }});

  document.getElementById('btn-fit').onclick = () => {{
    try {{ modeler.get('canvas').zoom('fit-viewport', 'auto'); }} catch(_) {{}}
  }};

  document.getElementById('btn-undo').onclick = () => {{
    try {{ modeler.get('commandStack').undo(); }} catch(_) {{}}
  }};

  document.getElementById('btn-redo').onclick = () => {{
    try {{ modeler.get('commandStack').redo(); }} catch(_) {{}}
  }};

  document.getElementById('btn-export').onclick = async () => {{
    try {{
      const {{ xml: exportedXml }} = await modeler.saveXML({{ format: true }});
      xmlOut.value = exportedXml;
      xmlPanel.style.display = 'block';
      xmlOut.focus();
      xmlOut.select();
    }} catch(err) {{
      errPanel.style.display = 'block';
      errPanel.textContent = '❌ Erro ao exportar XML: ' + err.message;
    }}
  }};
}})();
</script>
</body>
</html>"""


def editor_from_xml(xml: str, height: int = 700) -> str:
    """Return a self-contained HTML string for the bpmn-js Modeler.

    Renders inside ``streamlit.components.v1.html(html, height=height+260)``.
    The extra 260px accounts for the toolbar (40px), the XML export panel
    (200px) and padding.
    """
    xml_js = xml.replace("\\", "\\\\").replace("`", "\\`").replace("$", "\\$")
    return _EDITOR_TEMPLATE.format(xml_js=xml_js, canvas_height=height)
