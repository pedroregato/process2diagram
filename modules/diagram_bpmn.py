def generate_bpmn_preview(bpmn: BpmnProcess) -> str:
    """HTML with bpmn-js viewer and improved lane labels."""
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
    
    /* IMPROVED: Lane label styling */
    .djs-shape[data-element-type="lane"] .djs-label {{
      font-size: 12px !important;
      font-weight: 600 !important;
      fill: #1e293b !important;
      text-transform: uppercase !important;
      letter-spacing: 0.5px !important;
      dominant-baseline: middle !important;
      text-anchor: middle !important;
    }}
    
    /* Ensure lane header has proper background */
    .djs-shape[data-element-type="lane"] .djs-visual rect {{
      fill: #f1f5f9 !important;
      stroke: #94a3b8 !important;
      stroke-dasharray: 4 2 !important;
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
          
          // Force a small delay to ensure labels are rendered
          setTimeout(() => {{
            canvas.zoom('fit-viewport');
            updateZoomLabel();
            
            // Force repaint of lane labels
            const elements = viewer.get('elementRegistry');
            const lanes = elements.filter((el) => el.type === 'lane');
            lanes.forEach(lane => {{
              const gfx = elements.getGraphics(lane.id);
              if (gfx) {{
                // Trigger repaint
                viewer.get('graphicsFactory').update('shape', lane, gfx);
              }}
            }});
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
