# modules/mermaid_renderer.py
# ─────────────────────────────────────────────────────────────────────────────
# Shared Mermaid rendering utility — used by app.py and pages/Diagramas.py.
#
# render_mermaid_block():
#   Fetches both TD and LR SVGs from mermaid.ink server-side, injects them
#   inline in a self-contained HTML component with pan/zoom/fit and a
#   vertical/horizontal toggle (no external CDN, no Streamlit rerun).
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import re
import base64
import urllib.request

import streamlit.components.v1 as components


# ── SVG helpers ───────────────────────────────────────────────────────────────

def _fix_svg(svg_raw: str) -> str:
    """Remove fixed width/height; add viewBox for vector scaling."""
    tag_m = re.search(r"<svg[^>]*>", svg_raw)
    if not tag_m:
        return svg_raw
    tag = tag_m.group(0)
    w_m = re.search(r'width="([\d.]+)', tag)
    h_m = re.search(r'height="([\d.]+)', tag)
    has_vb = "viewBox" in tag or "viewbox" in tag
    if w_m and h_m and not has_vb:
        vb = f'viewBox="0 0 {w_m.group(1)} {h_m.group(1)}"'
        tag = tag.replace("<svg", f"<svg {vb}", 1)
    tag_clean = re.sub(r'\s*width="[^"]*"', "", tag)
    tag_clean = re.sub(r'\s*height="[^"]*"', "", tag_clean)
    tag_clean = tag_clean.replace("<svg", '<svg width="100%" height="100%"', 1)
    return svg_raw.replace(tag_m.group(0), tag_clean, 1)


def _fetch_svg(mermaid_code: str) -> tuple[str | None, str | None]:
    """Fetch SVG from mermaid.ink. Returns (svg_string, error_string)."""
    try:
        p = base64.urlsafe_b64encode(mermaid_code.encode("utf-8")).decode("ascii")
        url = f"https://mermaid.ink/svg/{p}"
        req = urllib.request.Request(url, headers={"User-Agent": "Process2Diagram/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            svg = resp.read().decode("utf-8")
        if svg and "<svg" in svg.lower():
            return _fix_svg(svg), None
        return None, "Resposta sem SVG"
    except Exception as exc:
        return None, str(exc)


# ── Public renderer ───────────────────────────────────────────────────────────

def render_mermaid_block(
    mermaid_text: str,
    *,
    show_code: bool = True,
    key_suffix: str = "",
    height: int = 620,
) -> None:
    """
    Render a Mermaid diagram with interactive pan/zoom/fit and TD/LR toggle.

    Both SVGs are fetched server-side and embedded inline — no external CDN
    inside the iframe (required for Streamlit Cloud sandbox).

    Args:
        mermaid_text: Raw Mermaid source (flowchart, mindmap, etc.).
        show_code:    Whether to show a collapsible code block below.
        key_suffix:   Unique suffix to avoid Streamlit component key collisions.
        height:       iframe height in pixels.
    """
    import streamlit as st

    if not mermaid_text or not mermaid_text.strip():
        st.warning("Nenhum diagrama Mermaid disponível.")
        return

    # For mindmap and other non-flowchart diagrams, skip the TD/LR swap
    is_flowchart = bool(re.match(r"^\s*flowchart\s", mermaid_text, re.IGNORECASE))

    if is_flowchart:
        mermaid_td = re.sub(
            r"^(flowchart\s+)(LR|RL|TB|TD)", r"\1TD",
            mermaid_text, count=1, flags=re.MULTILINE,
        )
        mermaid_lr = re.sub(
            r"^(flowchart\s+)(LR|RL|TB|TD)", r"\1LR",
            mermaid_text, count=1, flags=re.MULTILINE,
        )
        is_lr = bool(re.search(r"^flowchart\s+LR", mermaid_text, re.MULTILINE))
        default_dir = "lr" if is_lr else "td"
    else:
        # mindmap / other — fetch once, no direction toggle
        mermaid_td = mermaid_text
        mermaid_lr = mermaid_text
        default_dir = "td"

    svg_td, err_td = _fetch_svg(mermaid_td)
    svg_lr, err_lr = _fetch_svg(mermaid_lr)

    if svg_td or svg_lr:
        svg_td_safe = (svg_td or "<p>Erro ao gerar vertical</p>").replace("</script>", "<\\/script>")
        svg_lr_safe = (svg_lr or "<p>Erro ao gerar horizontal</p>").replace("</script>", "<\\/script>")

        show_toggle = "flex" if is_flowchart else "none"

        html_code = (
            """<!DOCTYPE html>
<html><head><style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#fff;overflow:hidden;font-family:-apple-system,BlinkMacSystemFont,sans-serif}
.toolbar{position:absolute;top:8px;right:8px;z-index:100;display:flex;gap:4px}
.toolbar button{width:32px;height:32px;border:1px solid #cbd5e1;border-radius:6px;
background:#fff;cursor:pointer;font-size:14px;display:flex;align-items:center;
justify-content:center;color:#475569;transition:all .15s}
.toolbar button:hover{background:#f1f5f9;border-color:#94a3b8}
.toolbar button.active{background:#e0e7ff;border-color:#6366f1;color:#4338ca}
#container{width:100%;height:100vh;overflow:hidden;cursor:grab;position:relative;
background:#fafafa;border:1px solid #e2e8f0;border-radius:8px}
#container:active{cursor:grabbing}
#viewport{transform-origin:0 0;position:absolute;top:0;left:0;will-change:transform}
#viewport svg{display:block;max-width:none}
.zoom-hint{position:absolute;bottom:8px;left:8px;z-index:100;font-size:11px;
color:#94a3b8;pointer-events:none}
</style></head><body>
<div style="width:100%;height:100vh;position:relative">
<div class="toolbar">
<button onclick="setDir('td')" id="btnTD" title="Vertical" style="display:"""
            + show_toggle
            + """">&#8595;</button>
<button onclick="setDir('lr')" id="btnLR" title="Horizontal" style="display:"""
            + show_toggle
            + """">&#8594;</button>
<button onclick="zoomIn()" title="Zoom in">+</button>
<button onclick="zoomOut()" title="Zoom out">&minus;</button>
<button onclick="fitToScreen()" title="Fit">&#8865;</button>
<button onclick="resetView()" title="Reset">&#8634;</button>
</div>
<div class="zoom-hint" id="zoomHint">Scroll: zoom | Drag: mover</div>
<div id="container"><div id="viewport"></div></div>
</div>
<div id="svg-td" style="display:none">"""
            + svg_td_safe
            + """</div>
<div id="svg-lr" style="display:none">"""
            + svg_lr_safe
            + """</div>
<script>
(function(){
var scale=1,panX=0,panY=0,dragging=false,startX=0,startY=0;
var MIN=0.1,MAX=5;
var c=document.getElementById("container"),v=document.getElementById("viewport");
var currentDir='"""
            + default_dir
            + """';
function apply(){
v.style.transform="translate("+panX+"px,"+panY+"px) scale("+scale+")";
var h=document.getElementById("zoomHint");
if(h) h.textContent=Math.round(scale*100)+"% | Scroll: zoom | Drag: mover";
}
window.setDir=function(d){
currentDir=d;
v.innerHTML=document.getElementById("svg-"+d).innerHTML;
var btnTD=document.getElementById("btnTD"),btnLR=document.getElementById("btnLR");
if(btnTD) btnTD.className=d==="td"?"active":"";
if(btnLR) btnLR.className=d==="lr"?"active":"";
setTimeout(fitToScreen,50);
};
window.zoomIn=function(){scale=Math.min(scale*1.25,MAX);apply()};
window.zoomOut=function(){scale=Math.max(scale/1.25,MIN);apply()};
window.resetView=function(){scale=1;panX=0;panY=0;apply()};
window.fitToScreen=function(){
var s=v.querySelector("svg");if(!s)return;
var vb=s.viewBox?s.viewBox.baseVal:null;
var w=0,h=0;
if(vb&&vb.width>0){w=vb.width;h=vb.height}
else{try{var bb=s.getBBox();w=bb.width;h=bb.height}catch(e){}}
if(!w||!h){w=s.scrollWidth||800;h=s.scrollHeight||600}
s.style.width=w+"px";s.style.height=h+"px";
s.setAttribute("width",w);s.setAttribute("height",h);
var cW=c.clientWidth,cH=c.clientHeight;
scale=Math.min(cW/w,cH/h,2)*0.92;
panX=(cW-w*scale)/2;panY=(cH-h*scale)/2;apply();
};
c.addEventListener("wheel",function(e){
e.preventDefault();var r=c.getBoundingClientRect();
var mx=e.clientX-r.left,my=e.clientY-r.top,os=scale;
var f=e.deltaY<0?1.12:1/1.12;
scale=Math.min(Math.max(scale*f,MIN),MAX);
panX=mx-(mx-panX)*(scale/os);panY=my-(my-panY)*(scale/os);apply();
},{passive:false});
c.addEventListener("mousedown",function(e){dragging=true;startX=e.clientX-panX;startY=e.clientY-panY});
window.addEventListener("mousemove",function(e){if(!dragging)return;panX=e.clientX-startX;panY=e.clientY-startY;apply()});
window.addEventListener("mouseup",function(){dragging=false});
setDir(currentDir);
function robustFit(){
var s=v.querySelector("svg");
if(!s){setTimeout(robustFit,100);return}
var vb=s.viewBox?s.viewBox.baseVal:null;
var w=(vb&&vb.width>0)?vb.width:s.scrollWidth;
if(!w||w<10){setTimeout(robustFit,100);return}
fitToScreen();
}
if(document.readyState==="complete"){setTimeout(robustFit,80)}
else{window.addEventListener("load",function(){setTimeout(robustFit,80)})}
})();
</script></body></html>"""
        )

        components.html(html_code, height=height, scrolling=False)

    else:
        import streamlit as st
        st.warning(f"⚠️ Não foi possível obter SVG: {err_td}")
        try:
            payload = base64.urlsafe_b64encode(mermaid_text.encode("utf-8")).decode("ascii")
            st.image(f"https://mermaid.ink/img/{payload}", use_container_width=True)
        except Exception:
            st.error("Cole o código abaixo em [mermaid.live](https://mermaid.live).")

    if show_code:
        import streamlit as st
        with st.expander("📝 Código Mermaid", expanded=False):
            st.code(mermaid_text, language="text")
