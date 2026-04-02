# modules/mindmap_interactive.py
# Versão corrigida – sem redeclaração de variáveis e com fallback silencioso

import json
import streamlit.components.v1 as components

def render_mindmap_from_requirements(model, *, session_title: str = "", height: int = 620):
    """Renderiza o mindmap interativo ou fallback para Mermaid."""
    try:
        from modules.requirements_mindmap import build_mindmap_tree
        tree = build_mindmap_tree(model, session_title)
        if not tree or not tree.get("children"):
            raise ValueError("Árvore vazia")
        render_interactive_mindmap(tree, height=height)
    except Exception as e:
        import streamlit as st
        st.warning(f"Mindmap interativo indisponível: {e}. Exibindo código Mermaid.")
        from modules.requirements_mindmap import generate_requirements_mindmap
        code = generate_requirements_mindmap(model)
        if code:
            st.code(code, language="mermaid")
        else:
            st.info("Nenhum requisito para gerar mindmap.")

def render_interactive_mindmap(tree: dict, *, height: int = 620):
    if not tree:
        return
    data_json = json.dumps(tree, ensure_ascii=False)
    html = _build_html(data_json)
    components.html(html, height=height, scrolling=False)

def _build_html(data_json: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#f8fafc;overflow:hidden;font-family:system-ui,sans-serif}}
.toolbar{{position:absolute;top:8px;right:8px;z-index:100;display:flex;gap:4px;align-items:center}}
.toolbar button{{height:28px;padding:0 9px;border:1px solid #cbd5e1;border-radius:6px;
  background:#fff;cursor:pointer;font-size:12px;color:#475569;transition:all .15s}}
.toolbar button:hover{{background:#f1f5f9;border-color:#94a3b8}}
.tb-sep{{width:1px;height:20px;background:#e2e8f0;margin:0 2px}}
#container{{width:100%;height:100vh;overflow:hidden;cursor:grab;position:relative;background:#f8fafc}}
#container:active{{cursor:grabbing}}
#vp{{transform-origin:0 0;position:absolute;top:0;left:0;will-change:transform}}
.hint{{position:absolute;bottom:8px;left:8px;z-index:100;font-size:11px;color:#94a3b8;pointer-events:none}}
</style></head><body>
<div style="width:100%;height:100vh;position:relative">
<div class="toolbar">
  <button id="btnExpand">⊞ Expandir</button>
  <button id="btnCollapse">⊟ Retrair</button>
  <div class="tb-sep"></div>
  <button id="btnZoomIn">+</button>
  <button id="btnZoomOut">&minus;</button>
  <button id="btnFit">&#8865;</button>
  <button id="btnReset">&#8634;</button>
</div>
<div class="hint" id="hint">Scroll: zoom | Drag: mover | Clique nos grupos para expandir/retrair</div>
<div id="container"><div id="vp"><svg id="mm"></svg></div></div>
</div>
<script>
(function(){{
const TREE = {data_json};

// Layout constants
const ROOT_W=170, ROOT_H=65, TYPE_W=155, TYPE_H=40, REQ_W=205, REQ_H=34;
const H_GAP=52, V_GAP=8;
const TC={{ui_field:'#3b82f6', validation:'#22c55e', business_rule:'#8b5cf6',
          functional:'#0891b2', non_functional:'#f97316'}};
const PBG={{high:'#fee2e2', medium:'#fef9c3', low:'#dcfce7', unspecified:'#f1f5f9'}};
const PBD={{high:'#ef4444', medium:'#eab308', low:'#22c55e', unspecified:'#cbd5e1'}};
const PDT={{high:'#ef4444', medium:'#eab308', low:'#22c55e', unspecified:'#94a3b8'}};

let collapsed = {{}}; // estado de colapso

function nwh(n){{
  if(n.kind==='root') return [ROOT_W,ROOT_H];
  if(n.kind==='type') return [TYPE_W,TYPE_H];
  return [REQ_W,REQ_H];
}}

function th(n){{
  const[,h]=nwh(n);
  if(!n.children||!n.children.length||collapsed[n.id]) return h;
  let total=0;
  n.children.forEach((c,i)=>{{ total+=th(c)+(i?V_GAP:0); }});
  return Math.max(h,total);
}}

function lay(n,x,yc){{
  const[w]=nwh(n);
  n.lx=x; n.ly=yc;
  if(!n.children||!n.children.length||collapsed[n.id]) return;
  const tot=th(n);
  let y=yc-tot/2;
  n.children.forEach(c=>{{
    const ch=th(c);
    lay(c,x+w+H_GAP,y+ch/2);
    y+=ch+V_GAP;
  }});
}}

function allNodes(n,arr){{
  arr.push(n);
  if(n.children&&!collapsed[n.id]) n.children.forEach(c=>allNodes(c,arr));
  return arr;
}}

function drawEdge(S,p,c){{
  const[pw]=nwh(p); const[cw]=nwh(c);
  const x1=p.lx+pw/2, y1=p.ly, x2=c.lx-cw/2, y2=c.ly, mx=(x1+x2)/2;
  const col=p.kind==='type'?(TC[p.colorKey]||'#94a3b8'):'#94a3b8';
  const path=document.createElementNS('http://www.w3.org/2000/svg','path');
  path.setAttribute('d',`M${{x1}},${{y1}}C${{mx}},${{y1}} ${{mx}},${{y2}} ${{x2}},${{y2}}`);
  path.setAttribute('fill','none');
  path.setAttribute('stroke',col);
  path.setAttribute('stroke-width',p.kind==='root'?2:1.5);
  path.setAttribute('opacity','0.5');
  S.insertBefore(path,S.firstChild||null);
}}

function wrap(str,maxch){{
  const out=[];
  str.split('\\n').forEach(seg=>{{
    if(seg.length<=maxch) out.push(seg);
    else{{
      let cur='';
      seg.split(' ').forEach(w=>{{
        const test=cur?(cur+' '):''+w;
        if(test.length>maxch&&cur){{out.push(cur); cur=w;}} else cur=test;
      }});
      if(cur) out.push(cur);
    }}
  }});
  return out;
}}

function drawNode(S,n){{
  const[w,h]=nwh(n), x=n.lx-w/2, y=n.ly-h/2;
  const hc=n.children&&n.children.length>0;
  const g=document.createElementNS('http://www.w3.org/2000/svg','g');
  if(hc) g.style.cursor='pointer';

  let fill,stroke,tc;
  if(n.kind==='root'){{fill='#0f172a';stroke='#0f172a';tc='#f8fafc';}}
  else if(n.kind==='type'){{fill=TC[n.colorKey]||'#64748b';stroke=fill;tc='#fff';}}
  else{{fill=PBG[n.priority]||'#f1f5f9';stroke=PBD[n.priority]||'#cbd5e1';tc='#1e293b';}}

  const rect=document.createElementNS('http://www.w3.org/2000/svg','rect');
  rect.setAttribute('x',x); rect.setAttribute('y',y);
  rect.setAttribute('width',w); rect.setAttribute('height',h);
  rect.setAttribute('rx','8'); rect.setAttribute('ry','8');
  rect.setAttribute('fill',fill); rect.setAttribute('stroke',stroke);
  rect.setAttribute('stroke-width','1.5');
  g.appendChild(rect);

  if(n.kind==='req'){{
    const idText=document.createElementNS('http://www.w3.org/2000/svg','text');
    idText.setAttribute('x',x+8); idText.setAttribute('y',n.ly-5);
    idText.setAttribute('font-size','11'); idText.setAttribute('font-weight','700');
    idText.setAttribute('font-family','monospace'); idText.setAttribute('fill',tc);
    idText.textContent=n.id; g.appendChild(idText);
    const titleText=document.createElementNS('http://www.w3.org/2000/svg','text');
    titleText.setAttribute('x',x+8); titleText.setAttribute('y',n.ly+9);
    titleText.setAttribute('font-size','10'); titleText.setAttribute('fill',tc);
    titleText.textContent=(n.title||'').slice(0,28); g.appendChild(titleText);
    const circle=document.createElementNS('http://www.w3.org/2000/svg','circle');
    circle.setAttribute('cx',x+w-10); circle.setAttribute('cy',n.ly);
    circle.setAttribute('r','5'); circle.setAttribute('fill',PDT[n.priority]||'#94a3b8');
    g.appendChild(circle);
  }}else{{
    const maxch=n.kind==='root'?20:17;
    const lines=wrap(n.label||'',maxch).slice(0,3);
    const lh=14, sy=n.ly-(lines.length-1)*lh/2;
    lines.forEach((line,i)=>{{
      const t=document.createElementNS('http://www.w3.org/2000/svg','text');
      t.setAttribute('x',n.lx); t.setAttribute('y',sy+i*lh);
      t.setAttribute('text-anchor','middle'); t.setAttribute('dominant-baseline','middle');
      t.setAttribute('font-size',n.kind==='root'?13:12);
      t.setAttribute('font-weight','600'); t.setAttribute('fill',tc);
      t.textContent=line; g.appendChild(t);
    }});
  }}

  if(hc){{
    const ix=x+w+1;
    const circ=document.createElementNS('http://www.w3.org/2000/svg','circle');
    circ.setAttribute('cx',ix); circ.setAttribute('cy',n.ly);
    circ.setAttribute('r','9'); circ.setAttribute('fill','#fff'); circ.setAttribute('stroke',fill);
    circ.setAttribute('stroke-width','1.5');
    g.appendChild(circ);
    const sym=document.createElementNS('http://www.w3.org/2000/svg','text');
    sym.setAttribute('x',ix); sym.setAttribute('y',n.ly+4.5);
    sym.setAttribute('text-anchor','middle'); sym.setAttribute('font-size','14');
    sym.setAttribute('font-weight','700'); sym.setAttribute('fill',fill);
    sym.textContent=collapsed[n.id]?'+':'\u2212';
    g.appendChild(sym);
    g.addEventListener('click',()=>{{
      collapsed[n.id]=!collapsed[n.id];
      redraw();
    }});
  }}
  S.appendChild(g);
  if(n.children&&!collapsed[n.id]){{
    n.children.forEach(c=>{{ drawEdge(S,n,c); drawNode(S,c); }});
  }}
}}

function redraw(){{
  const S=document.getElementById('mm');
  S.innerHTML='';
  const root_th=th(TREE);
  lay(TREE, 50, root_th/2+40);
  const nodes=allNodes(TREE,[]);
  const maxX=Math.max(...nodes.map(n=>n.lx+nwh(n)[0]/2))+40;
  const maxY=Math.max(...nodes.map(n=>n.ly+nwh(n)[1]/2))+40;
  S.setAttribute('width',maxX); S.setAttribute('height',maxY);
  S.setAttribute('viewBox',`0 0 ${{maxX}} ${{maxY}}`);
  drawNode(S,TREE);
}}

// Pan/zoom
let sc=1, px=0, py=0, drag=false, sx=0, sy=0;
const MIN=0.08, MAX=6;
const cont=document.getElementById('container');
const vp=document.getElementById('vp');
function ap(){{
  vp.style.transform=`translate(${{px}}px, ${{py}}px) scale(${{sc}})`;
  document.getElementById('hint').innerText=Math.round(sc*100)+'% | Scroll: zoom | Drag: mover';
}}
function zoomIn(){{ sc=Math.min(sc*1.25,MAX); ap(); }}
function zoomOut(){{ sc=Math.max(sc/1.25,MIN); ap(); }}
function resetView(){{ sc=1; px=0; py=0; ap(); }}
function fitToScreen(){{
  const S=document.getElementById('mm');
  const w=parseFloat(S.getAttribute('width')||800);
  const h=parseFloat(S.getAttribute('height')||600);
  const cW=cont.clientWidth, cH=cont.clientHeight;
  const padding=40;
  sc=Math.min((cW-padding)/w,(cH-padding)/h,2)*0.92;
  px=(cW-w*sc)/2; py=(cH-h*sc)/2;
  ap();
}}
function expandAll(){{ collapsed={{}}; redraw(); setTimeout(fitToScreen,50); }}
function collapseAll(){{
  (TREE.children||[]).forEach(c=>{{ if(c.kind==='type') collapsed[c.id]=true; }});
  redraw(); setTimeout(fitToScreen,50);
}}

// Bind buttons
document.getElementById('btnExpand').onclick=expandAll;
document.getElementById('btnCollapse').onclick=collapseAll;
document.getElementById('btnZoomIn').onclick=zoomIn;
document.getElementById('btnZoomOut').onclick=zoomOut;
document.getElementById('btnFit').onclick=fitToScreen;
document.getElementById('btnReset').onclick=resetView;

// Mouse events
cont.addEventListener('wheel',e=>{{
  e.preventDefault();
  const r=cont.getBoundingClientRect();
  const mx=e.clientX-r.left, my=e.clientY-r.top, os=sc;
  const f=e.deltaY<0?1.12:1/1.12;
  sc=Math.min(Math.max(sc*f,MIN),MAX);
  px=mx-(mx-px)*(sc/os); py=my-(my-py)*(sc/os);
  ap();
}},{{passive:false}});
cont.addEventListener('mousedown',e=>{{ drag=true; sx=e.clientX-px; sy=e.clientY-py; }});
window.addEventListener('mousemove',e=>{{ if(!drag) return; px=e.clientX-sx; py=e.clientY-sy; ap(); }});
window.addEventListener('mouseup',()=>{{ drag=false; }});

redraw();
setTimeout(fitToScreen,80);
}})();
</script></body></html>"""
