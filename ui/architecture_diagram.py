# ui/architecture_diagram.py
# ─────────────────────────────────────────────────────────────────────────────
# Splash architecture diagram shown at the top of the app.
#
# Uses a Mermaid flowchart TD rendered via mermaid.ink.
# The SVG is fetched once and cached with @st.cache_data — zero network
# overhead on subsequent Streamlit reruns.
#
# Entry point: render_architecture_diagram()
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import base64
import re
import urllib.request

import streamlit as st
import streamlit.components.v1 as components


# ── Diagram source ─────────────────────────────────────────────────────────────
#
# Mermaid flowchart TD chosen because:
#   - Shows sequential pipeline flow naturally (top → bottom)
#   - direction LR in sub-groups lets providers and outputs spread horizontally
#   - Nested subgraph (PAR inside PIPE) makes the parallel step visually obvious
#   - classDef palette matches the Process2Diagram brand colours

ARCHITECTURE_DIAGRAM = """\
flowchart TD
    classDef iCls  fill:#0B1E3D,stroke:none,color:#FFFFFF,font-weight:600
    classDef lCls  fill:#C97B1A,stroke:#8C5510,color:#FFFFFF
    classDef aCls  fill:#1A4B8C,stroke:#0B1E3D,color:#FFFFFF
    classDef optCls fill:#6B3FA0,stroke:#4A2870,color:#FFFFFF
    classDef rCls  fill:#1A7F5A,stroke:#0F5A3A,color:#FFFFFF

    IN(["📄 Transcrição de Reunião\\n.txt · .docx · .pdf · texto colado"]):::iCls

    subgraph LLM["🤖 5 LLM Providers — configure o de sua preferência"]
        direction LR
        P1["DeepSeek\\nDefault"]:::lCls
        P2["Claude\\nAnthropic"]:::lCls
        P3["OpenAI\\nGPT-4o"]:::lCls
        P4["Groq\\nLlama"]:::lCls
        P5["Gemini\\nGoogle"]:::lCls
    end

    subgraph PIPE["⚙️ Pipeline Multi-Agente — KnowledgeHub como estado central"]
        direction TB
        A1["🔬 Quality Inspector\\nGrade A–E · critérios ponderados"]:::aCls
        A2["🧹 Preprocessor\\nRemove ASR, fillers e ruído"]:::aCls
        A3["🔤 NLP Chunker\\nspaCy · NER · atores detectados"]:::aCls
        A4["📐 BPMN Architect\\n⟳ LangGraph Adaptive Retry"]:::aCls
        subgraph PAR["🔀 Execução Paralela — ThreadPoolExecutor"]
            direction LR
            A5["📋 Meeting\\nMinutes"]:::aCls
            A6["📝 Requirements\\nIEEE 830"]:::aCls
        end
        A7["📖 SBVR\\nVocabulário · Regras de Negócio"]:::optCls
        A8["🎯 BMM\\nVisão · Metas · Estratégias"]:::optCls
        A9["📄 Executive\\nSynthesizer"]:::optCls
        A1 --> A2 --> A3 --> A4 --> PAR --> A7 --> A8 --> A9
    end

    subgraph OUTS["📦 7 Artefatos Gerados Automaticamente"]
        direction LR
        R1["📐 BPMN 2.0\\nXML + bpmn-js"]:::rCls
        R2["📊 Mermaid\\nFlowchart"]:::rCls
        R3["📋 Ata\\n.md · .docx · .pdf"]:::rCls
        R4["📝 Requisitos\\nJSON + Mind Map"]:::rCls
        R5["📖 Vocabulário\\nSBVR"]:::rCls
        R6["🎯 Motivação\\nBMM"]:::rCls
        R7["📄 Relatório\\nExecutivo HTML"]:::rCls
    end

    IN --> A1
    LLM -.->|"REST API"| PIPE
    A4 --> R1
    A4 --> R2
    A5 --> R3
    A6 --> R4
    A7 --> R5
    A8 --> R6
    A9 --> R7\
"""


# ── SVG fetch (cached) ────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _fetch_arch_svg(diagram_code: str) -> tuple[str | None, str | None]:
    """Fetch architecture SVG from mermaid.ink — cached for the server lifetime."""
    try:
        encoded = base64.urlsafe_b64encode(diagram_code.encode("utf-8")).decode("ascii")
        url = f"https://mermaid.ink/svg/{encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "Process2Diagram/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
        if not raw or "<svg" not in raw.lower():
            return None, "Resposta sem SVG"

        # Remove fixed dimensions so the SVG scales with its container
        tag_m = re.search(r"<svg[^>]*>", raw)
        if tag_m:
            tag = tag_m.group(0)
            w_m = re.search(r'width="([\d.]+)', tag)
            h_m = re.search(r'height="([\d.]+)', tag)
            has_vb = "viewBox" in tag or "viewbox" in tag
            if w_m and h_m and not has_vb:
                vb = f'viewBox="0 0 {w_m.group(1)} {h_m.group(1)}"'
                tag = tag.replace("<svg", f"<svg {vb}", 1)
            tag = re.sub(r'\s*width="[^"]*"',  "", tag)
            tag = re.sub(r'\s*height="[^"]*"', "", tag)
            tag = tag.replace("<svg", '<svg width="100%" height="100%"', 1)
            raw = raw.replace(tag_m.group(0), tag, 1)

        return raw, None
    except Exception as exc:
        return None, str(exc)


# ── Interactive viewer component ──────────────────────────────────────────────

def _arch_viewer_html(svg: str, height: int) -> str:
    """Build a self-contained HTML viewer with pan/zoom/fit for the architecture SVG."""
    svg_safe = svg.replace("</script>", "<\\/script>")
    return f"""<!DOCTYPE html>
<html><head><style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{background:#F4F7FB;overflow:hidden;
     font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
#wrap{{width:100%;height:100vh;position:relative}}
.tb{{position:absolute;top:10px;right:10px;z-index:100;
     display:flex;flex-direction:column;gap:4px}}
.tb button{{
  width:34px;height:34px;border:1px solid #CBD5E1;border-radius:8px;
  background:#fff;cursor:pointer;font-size:15px;
  display:flex;align-items:center;justify-content:center;
  color:#475569;transition:background .12s,border-color .12s;
  box-shadow:0 1px 3px rgba(0,0,0,.08)}}
.tb button:hover{{background:#F1F5F9;border-color:#94A3B8}}
#hint{{position:absolute;bottom:8px;left:12px;z-index:100;
       font-size:11px;color:#94A3B8;pointer-events:none}}
#stage{{width:100%;height:100vh;overflow:hidden;cursor:grab;
        border-radius:10px;border:1px solid #D5E3F5}}
#stage:active{{cursor:grabbing}}
#vp{{transform-origin:0 0;position:absolute;top:0;left:0;will-change:transform}}
</style></head><body>
<div id="wrap">
  <div class="tb">
    <button onclick="zoomIn()"  title="Zoom in">+</button>
    <button onclick="zoomOut()" title="Zoom out">&minus;</button>
    <button onclick="fit()"     title="Ajustar">&#8865;</button>
    <button onclick="reset()"   title="Resetar">&#8634;</button>
  </div>
  <div id="hint">Scroll: zoom · Drag: mover</div>
  <div id="stage"><div id="vp">{svg_safe}</div></div>
</div>
<script>
(function(){{
  var sc=1,px=0,py=0,drag=false,sx=0,sy=0;
  var MIN=0.08,MAX=6;
  var stage=document.getElementById('stage');
  var vp=document.getElementById('vp');
  function apply(){{
    vp.style.transform='translate('+px+'px,'+py+'px) scale('+sc+')';
    document.getElementById('hint').textContent=
      Math.round(sc*100)+'% · Scroll: zoom · Drag: mover';
  }}
  window.zoomIn =function(){{sc=Math.min(sc*1.25,MAX);apply()}};
  window.zoomOut=function(){{sc=Math.max(sc/1.25,MIN);apply()}};
  window.reset  =function(){{sc=1;px=0;py=0;apply()}};
  window.fit=function(){{
    var s=vp.querySelector('svg');if(!s)return;
    var vb=s.viewBox?s.viewBox.baseVal:null;
    var w=0,h=0;
    if(vb&&vb.width>0){{w=vb.width;h=vb.height}}
    else{{try{{var bb=s.getBBox();w=bb.width;h=bb.height}}catch(e){{}}}}
    if(!w||!h){{w=s.scrollWidth||900;h=s.scrollHeight||700}}
    s.style.width=w+'px';s.style.height=h+'px';
    s.setAttribute('width',w);s.setAttribute('height',h);
    var cW=stage.clientWidth,cH=stage.clientHeight;
    sc=Math.min(cW/w,cH/h,2)*0.90;
    px=(cW-w*sc)/2;py=(cH-h*sc)/2;apply();
  }};
  stage.addEventListener('wheel',function(e){{
    e.preventDefault();
    var r=stage.getBoundingClientRect();
    var mx=e.clientX-r.left,my=e.clientY-r.top,os=sc;
    var f=e.deltaY<0?1.13:1/1.13;
    sc=Math.min(Math.max(sc*f,MIN),MAX);
    px=mx-(mx-px)*(sc/os);py=my-(my-py)*(sc/os);apply();
  }},{{passive:false}});
  stage.addEventListener('mousedown',function(e){{
    drag=true;sx=e.clientX-px;sy=e.clientY-py;
  }});
  window.addEventListener('mousemove',function(e){{
    if(!drag)return;px=e.clientX-sx;py=e.clientY-sy;apply();
  }});
  window.addEventListener('mouseup',function(){{drag=false}});
  function robustFit(){{
    var s=vp.querySelector('svg');
    if(!s){{setTimeout(robustFit,100);return}}
    var vb=s.viewBox?s.viewBox.baseVal:null;
    var w=(vb&&vb.width>0)?vb.width:s.scrollWidth;
    if(!w||w<10){{setTimeout(robustFit,100);return}}
    fit();
  }}
  if(document.readyState==='complete'){{setTimeout(robustFit,100)}}
  else{{window.addEventListener('load',function(){{setTimeout(robustFit,100)}})}}
}})();
</script></body></html>"""


# ── Public entry point ─────────────────────────────────────────────────────────

def render_architecture_diagram(height: int = 720) -> None:
    """
    Render the Process2Diagram architecture diagram as a splash/intro section.

    The SVG is fetched from mermaid.ink once and cached for the Streamlit
    server lifetime (@st.cache_data).  Subsequent reruns use the cached copy
    — no additional network call.

    Args:
        height: iframe height in pixels (default 720).
    """
    svg, err = _fetch_arch_svg(ARCHITECTURE_DIAGRAM)

    if svg:
        viewer = _arch_viewer_html(svg, height)
        components.html(viewer, height=height, scrolling=False)
    else:
        # Graceful fallback: link to mermaid.live
        st.warning(f"⚠️ Não foi possível renderizar o diagrama: {err}")
        encoded = base64.urlsafe_b64encode(
            ARCHITECTURE_DIAGRAM.encode("utf-8")
        ).decode("ascii")
        st.markdown(
            f"[🔗 Abrir no Mermaid Live](https://mermaid.live/edit#{encoded})",
            unsafe_allow_html=False,
        )
        with st.expander("📝 Código Mermaid", expanded=False):
            st.code(ARCHITECTURE_DIAGRAM, language="text")
