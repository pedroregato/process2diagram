# modules/mindmap_interactive.py
# ─────────────────────────────────────────────────────────────────────────────
# Interactive collapsible mindmap renderer — pure vanilla JS/SVG.
#
# No external dependencies. Works inside Streamlit Cloud iframes.
# Renders a left-to-right tree with:
#   - Click type-group nodes to expand/collapse children
#   - Expand All / Collapse All toolbar buttons
#   - Pan / Zoom / Fit (same UX as mermaid_renderer)
#   - Color-coded by requirement type and priority
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json


def render_interactive_mindmap(tree: dict, *, height: int = 620) -> None:
    """
    Render an interactive collapsible mindmap inside a Streamlit component.

    Args:
        tree:   Hierarchical dict from requirements_mindmap.build_mindmap_tree().
        height: Component height in pixels.
    """
    import streamlit.components.v1 as components

    if not tree:
        import streamlit as st
        st.info("Nenhum dado disponível para o mind map.")
        return

    data_json = json.dumps(tree, ensure_ascii=False)

    html = _build_html(data_json)
    components.html(html, height=height, scrolling=False)


# ── HTML builder ──────────────────────────────────────────────────────────────

def _build_html(data_json: str) -> str:
    return """<!DOCTYPE html>
<html><head><style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#f8fafc;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,sans-serif}
.toolbar{position:absolute;top:8px;right:8px;z-index:100;display:flex;gap:4px;align-items:center}
.toolbar button{height:28px;padding:0 9px;border:1px solid #cbd5e1;border-radius:6px;
  background:#fff;cursor:pointer;font-size:12px;color:#475569;transition:all .15s;white-space:nowrap}
.toolbar button:hover{background:#f1f5f9;border-color:#94a3b8}
.tb-sep{width:1px;height:20px;background:#e2e8f0;margin:0 2px}
#container{width:100%;height:100vh;overflow:hidden;cursor:grab;position:relative;background:#f8fafc}
#container:active{cursor:grabbing}
#vp{transform-origin:0 0;position:absolute;top:0;left:0;will-change:transform}
.hint{position:absolute;bottom:8px;left:8px;z-index:100;font-size:11px;color:#94a3b8;pointer-events:none}
</style></head><body>
<div style="width:100%;height:100vh;position:relative">
<div class="toolbar">
  <button onclick="expandAll()">⊞ Expandir</button>
  <button onclick="collapseAll()">⊟ Retrair</button>
  <div class="tb-sep"></div>
  <button onclick="zoomIn()">+</button>
  <button onclick="zoomOut()">&minus;</button>
  <button onclick="fitToScreen()">&#8865;</button>
  <button onclick="resetView()">&#8634;</button>
</div>
<div class="hint" id="hint">Scroll: zoom &nbsp;|&nbsp; Drag: mover &nbsp;|&nbsp; Clique nos grupos para expandir/retrair</div>
<div id="container"><div id="vp"><svg id="mm"></svg></div></div>
</div>
<script>
(function(){
const TREE=""" + data_json + """;

/* ── Layout constants ── */
const ROOT_W=170,ROOT_H=65,TYPE_W=155,TYPE_H=40,REQ_W=205,REQ_H=34;
const H_GAP=52,V_GAP=8;

/* ── Palette ── */
const TC={ui_field:'#3b82f6',validation:'#22c55e',business_rule:'#8b5cf6',
          functional:'#0891b2',non_functional:'#f97316'};
const PBG={high:'#fee2e2',medium:'#fef9c3',low:'#dcfce7',unspecified:'#f1f5f9'};
const PBD={high:'#ef4444',medium:'#eab308',low:'#22c55e',unspecified:'#cbd5e1'};
const PDT={high:'#ef4444',medium:'#eab308',low:'#22c55e',unspecified:'#94a3b8'};

/* ── State ── */
const CL={};

/* ── Helpers ── */
function svg(tag,attrs){
  const el=document.createElementNS('http://www.w3.org/2000/svg',tag);
  for(const[k,v]of Object.entries(attrs||{}))el.setAttribute(k,String(v));
  return el;
}
function trunc(s,n){return(s||'').length>n?(s||'').slice(0,n)+'\u2026':s||''}
function nwh(n){
  if(n.kind==='root')return[ROOT_W,ROOT_H];
  if(n.kind==='type')return[TYPE_W,TYPE_H];
  return[REQ_W,REQ_H];
}

/* ── Tree height (visible) ── */
function th(n){
  const[,h]=nwh(n);
  if(!n.children||!n.children.length||CL[n.id])return h;
  let t=0;n.children.forEach((c,i)=>{t+=th(c)+(i?V_GAP:0);});
  return Math.max(h,t);
}

/* ── Layout ── */
function lay(n,x,yc){
  const[w]=nwh(n);n.lx=x;n.ly=yc;
  if(!n.children||!n.children.length||CL[n.id])return;
  const tot=th(n);let y=yc-tot/2;
  n.children.forEach(c=>{const ch=th(c);lay(c,x+w+H_GAP,y+ch/2);y+=ch+V_GAP;});
}

function allV(n,arr){
  arr=arr||[];arr.push(n);
  if(n.children&&!CL[n.id])n.children.forEach(c=>allV(c,arr));
  return arr;
}

/* ── Draw edge ── */
function edge(S,p,c){
  const[pw]=nwh(p);const[cw]=nwh(c);
  const x1=p.lx+pw/2,y1=p.ly,x2=c.lx-cw/2,y2=c.ly,mx=(x1+x2)/2;
  const col=p.kind==='type'?(TC[p.colorKey]||'#94a3b8'):'#94a3b8';
  const path=svg('path',{d:`M${x1},${y1}C${mx},${y1} ${mx},${y2} ${x2},${y2}`,
    fill:'none',stroke:col,'stroke-width':p.kind==='root'?2:1.5,opacity:0.5});
  S.insertBefore(path,S.firstChild||null);
}

/* ── Wrap text into lines ── */
function wrap(str,maxch){
  const out=[];
  str.split('\\n').forEach(seg=>{
    if(seg.length<=maxch){out.push(seg);return;}
    let cur='';
    seg.split(' ').forEach(w=>{
      const test=(cur?cur+' ':'')+w;
      if(test.length>maxch&&cur){out.push(cur);cur=w;}else{cur=test;}
    });
    if(cur)out.push(cur);
  });
  return out;
}

/* ── Draw node ── */
function drawN(S,n){
  const[w,h]=nwh(n);const x=n.lx-w/2,y=n.ly-h/2;
  const hc=n.children&&n.children.length>0;
  const g=svg('g');if(hc)g.style.cursor='pointer';

  let fill,stroke,tc;
  if(n.kind==='root'){fill='#0f172a';stroke='#0f172a';tc='#f8fafc';}
  else if(n.kind==='type'){fill=TC[n.colorKey]||'#64748b';stroke=fill;tc='#fff';}
  else{fill=PBG[n.priority]||'#f1f5f9';stroke=PBD[n.priority]||'#cbd5e1';tc='#1e293b';}

  g.appendChild(svg('rect',{x,y,width:w,height:h,rx:8,ry:8,fill,stroke,'stroke-width':1.5}));

  if(n.kind==='req'){
    /* ID (bold monospace, line 1) */
    const t1=svg('text',{x:x+8,y:n.ly-5,'font-size':11,'font-weight':'700',
      'font-family':'monospace',fill:tc,'pointer-events':'none'});
    t1.textContent=n.id;g.appendChild(t1);
    /* Title (normal, line 2) */
    const t2=svg('text',{x:x+8,y:n.ly+9,'font-size':10,fill:tc,
      'font-family':'sans-serif','pointer-events':'none'});
    t2.textContent=trunc(n.title,28);g.appendChild(t2);
    /* Priority dot */
    g.appendChild(svg('circle',{cx:x+w-10,cy:n.ly,r:5,fill:PDT[n.priority]||'#94a3b8','pointer-events':'none'}));
  } else {
    const maxch=n.kind==='root'?20:17;
    const lines=wrap(n.label||'',maxch).slice(0,3);
    const lh=14,sy=n.ly-(lines.length-1)*lh/2;
    lines.forEach((line,i)=>{
      const t=svg('text',{x:n.lx,y:sy+i*lh,'text-anchor':'middle',
        'dominant-baseline':'middle','font-size':n.kind==='root'?13:12,
        'font-weight':'600',fill:tc,'pointer-events':'none'});
      t.textContent=line;g.appendChild(t);
    });
  }

  /* +/− toggle */
  if(hc){
    const ix=x+w+1;
    g.appendChild(svg('circle',{cx:ix,cy:n.ly,r:9,fill:'#fff',stroke:fill,'stroke-width':1.5}));
    const it=svg('text',{x:ix,y:n.ly+4.5,'text-anchor':'middle','font-size':14,
      'font-weight':'700',fill:fill,'pointer-events':'none'});
    it.textContent=CL[n.id]?'+':'\u2212';g.appendChild(it);
    g.addEventListener('click',()=>{CL[n.id]=!CL[n.id];redraw();});
  }

  S.appendChild(g);
  if(n.children&&!CL[n.id]){n.children.forEach(c=>{edge(S,n,c);drawN(S,c);});}
}

/* ── Redraw ── */
function redraw(){
  const S=document.getElementById('mm');S.innerHTML='';
  const root_th=th(TREE);
  lay(TREE,30,root_th/2+20);
  const nodes=allV(TREE);
  const maxX=Math.max(...nodes.map(n=>n.lx+nwh(n)[0]/2))+24;
  const maxY=Math.max(...nodes.map(n=>n.ly+nwh(n)[1]/2))+24;
  S.setAttribute('width',maxX);S.setAttribute('height',maxY);
  S.setAttribute('viewBox',`0 0 ${maxX} ${maxY}`);
  drawN(S,TREE);
}

/* ── Pan/zoom ── */
var sc=1,px=0,py=0,drag=false,sx=0,sy=0;
const MIN=0.08,MAX=6;
const cont=document.getElementById('container');
const vp=document.getElementById('vp');

function ap(){
  vp.style.transform=`translate(${px}px,${py}px) scale(${sc})`;
  const h=document.getElementById('hint');
  if(h)h.textContent=Math.round(sc*100)+'% | Scroll: zoom | Drag: mover | Clique nos grupos para expandir/retrair';
}
window.zoomIn=()=>{sc=Math.min(sc*1.25,MAX);ap();};
window.zoomOut=()=>{sc=Math.max(sc/1.25,MIN);ap();};
window.resetView=()=>{sc=1;px=0;py=0;ap();};
window.fitToScreen=function(){
  const S=document.getElementById('mm');
  const w=parseFloat(S.getAttribute('width')||800);
  const h=parseFloat(S.getAttribute('height')||600);
  const cW=cont.clientWidth,cH=cont.clientHeight;
  sc=Math.min(cW/w,cH/h,2)*0.92;
  px=(cW-w*sc)/2;py=(cH-h*sc)/2;ap();
};
window.expandAll=()=>{Object.keys(CL).forEach(k=>delete CL[k]);redraw();setTimeout(fitToScreen,50);};
window.collapseAll=()=>{
  (TREE.children||[]).forEach(c=>{if(c.kind==='type')CL[c.id]=true;});
  redraw();setTimeout(fitToScreen,50);
};

cont.addEventListener('wheel',e=>{
  e.preventDefault();
  const r=cont.getBoundingClientRect();
  const mx=e.clientX-r.left,my=e.clientY-r.top,os=sc;
  const f=e.deltaY<0?1.12:1/1.12;
  sc=Math.min(Math.max(sc*f,MIN),MAX);
  px=mx-(mx-px)*(sc/os);py=my-(my-py)*(sc/os);ap();
},{passive:false});
cont.addEventListener('mousedown',e=>{drag=true;sx=e.clientX-px;sy=e.clientY-py;});
window.addEventListener('mousemove',e=>{if(!drag)return;px=e.clientX-sx;py=e.clientY-sy;ap();});
window.addEventListener('mouseup',()=>{drag=false;});

/* ── Boot ── */
redraw();
setTimeout(fitToScreen,80);
})();
</script></body></html>"""
