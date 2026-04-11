# ui/assistant_diagram.py
# ─────────────────────────────────────────────────────────────────────────────
# Architecture diagram for the Assistente page.
#
# Shows the full RAG pipeline: question → keyword/semantic retrieval →
# Supabase sources → AgentAssistant (P2D guide + context) → LLM → response.
#
# Entry point: render_assistant_diagram(height)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import base64
import re
import urllib.request

import streamlit as st
import streamlit.components.v1 as components


# ── Diagram source ────────────────────────────────────────────────────────────

ASSISTANT_DIAGRAM = """\
flowchart TD
    classDef iCls  fill:#0B1E3D,stroke:none,color:#FFFFFF,font-weight:600
    classDef aCls  fill:#1A4B8C,stroke:#0B1E3D,color:#FFFFFF
    classDef lCls  fill:#C97B1A,stroke:#8C5510,color:#FFFFFF
    classDef dCls  fill:#1A7F5A,stroke:#0F5A3A,color:#FFFFFF
    classDef sCls  fill:#6B3FA0,stroke:#4A2870,color:#FFFFFF
    classDef rCls  fill:#14532D,stroke:#052E16,color:#FFFFFF
    classDef gCls  fill:#1e3a5f,stroke:#0B1E3D,color:#FFFFFF

    Q(["❓ Pergunta do Usuário"]):::iCls
    H[("💬 Histórico\\nda Conversa")]:::gCls

    subgraph SEARCH["🔍 Recuperação de Contexto (RAG)"]
        direction LR
        subgraph KW_BOX["🔑 Busca por Keyword  (padrão)"]
            K1["Extração de\\npalavras-chave PT"]:::aCls
        end
        subgraph SEM_BOX["🔮 Busca Semântica  (pgvector — opcional)"]
            S1["Embedding da pergunta\\n(Gemini · OpenAI)"]:::sCls
            S2["Cosine similarity\\ntranscript_chunks"]:::sCls
            S1 --> S2
        end
    end

    subgraph DB["🗄️ Supabase — Fontes de Dados"]
        direction LR
        T1[("📝 Transcrições\\nmeetings")]:::dCls
        T2[("📋 Requisitos")]:::dCls
        T3[("📐 Processos\\nBPMN")]:::dCls
        T4[("📖 Vocabulário\\nSBVR")]:::dCls
        T5[("📊 Resumo\\ndo Projeto")]:::dCls
    end

    CTX["📋 Contexto RAG\\nPassagens · Requisitos · BPMN · SBVR · Resumo de Dados"]:::aCls

    subgraph AGENT["🤖 AgentAssistant"]
        direction TB
        G["📘 Guia P2D\\nskill_assistant.md\\n(páginas · pipeline · schema)"]:::aCls
        SP["System Prompt\\n= Guia P2D + Contexto RAG"]:::aCls
        MH["Messages\\n= Histórico + Pergunta atual"]:::aCls
        G --> SP
    end

    subgraph LLM["⚡ LLM Providers — OpenAI-compatible ou Anthropic"]
        direction LR
        L1["DeepSeek\\n(padrão)"]:::lCls
        L2["Claude\\nAnthropic"]:::lCls
        L3["OpenAI\\nGPT-4o"]:::lCls
        L4["Groq\\nLlama"]:::lCls
        L5["Gemini\\nGoogle"]:::lCls
    end

    R(["💬 Resposta com Citações\\nde reuniões e fontes"]):::rCls

    Q --> KW_BOX
    Q --> SEM_BOX
    K1 --> T1 & T2 & T3 & T4
    S2 --> T1
    T5 -.->|sempre| CTX
    T1 & T2 & T3 & T4 --> CTX
    CTX --> SP
    H --> MH
    Q --> MH
    SP --> LLM
    MH --> LLM
    LLM --> R\
"""


# ── SVG fetch (cached) ────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _fetch_assistant_svg(diagram_code: str) -> tuple[str | None, str | None]:
    """Fetch assistant architecture SVG from mermaid.ink — cached for server lifetime."""
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

def _viewer_html(svg: str, height: int) -> str:
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


# ── Public entry point ────────────────────────────────────────────────────────

def render_assistant_diagram(height: int = 660) -> None:
    """
    Render the Assistente architecture diagram.

    SVG is fetched from mermaid.ink once and cached for the Streamlit server
    lifetime. Subsequent reruns use the cached copy — no additional network call.
    """
    svg, err = _fetch_assistant_svg(ASSISTANT_DIAGRAM)

    if svg:
        viewer = _viewer_html(svg, height)
        components.html(viewer, height=height, scrolling=False)
    else:
        st.warning(f"⚠️ Não foi possível renderizar o diagrama: {err}")
        encoded = base64.urlsafe_b64encode(
            ASSISTANT_DIAGRAM.encode("utf-8")
        ).decode("ascii")
        st.markdown(
            f"[🔗 Abrir no Mermaid Live](https://mermaid.live/edit#{encoded})",
            unsafe_allow_html=False,
        )
        with st.expander("📝 Código Mermaid", expanded=False):
            st.code(ASSISTANT_DIAGRAM, language="text")
