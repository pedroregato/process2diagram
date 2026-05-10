# ui/comms_diagram.py
# ─────────────────────────────────────────────────────────────────────────────
# Communication & integration architecture diagram for Process2Diagram.
#
# Shows the full topology: Streamlit layers → integration modules →
# external services, with the two independent paths to Google Calendar
# (Streamlit via calendar_client.py and Claude Code CLI via MCP server).
#
# Entry point: render_comms_diagram(height)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import base64
import re
import urllib.request

import streamlit as st
import streamlit.components.v1 as components


# ── Diagram source ────────────────────────────────────────────────────────────

COMMS_DIAGRAM = """\
flowchart TD
    classDef stCls   fill:#1A4B8C,stroke:#0B1E3D,color:#FFFFFF
    classDef modCls  fill:#1e3a5f,stroke:#0B1E3D,color:#FFFFFF
    classDef extCls  fill:#1A7F5A,stroke:#0F5A3A,color:#FFFFFF
    classDef lCls    fill:#C97B1A,stroke:#8C5510,color:#FFFFFF
    classDef sCls    fill:#6B3FA0,stroke:#4A2870,color:#FFFFFF
    classDef tCls    fill:#7C2D12,stroke:#4A1A07,color:#FFFFFF
    classDef mcpCls  fill:#4A2870,stroke:#6B3FA0,color:#FFFFFF
    classDef authCls fill:#374151,stroke:#1F2937,color:#FFFFFF

    subgraph APP["🖥️ Streamlit App — Process2Diagram"]
        direction TB

        subgraph APAGES["📄 Pages & Agentes"]
            direction LR
            PA["🚀 Pipeline · 📐 Diagramas\\n✏️ BpmnEditor · 🏠 Home\\n🔄 BatchRunner · 📊 MeetingROI"]:::stCls
            PB["💬 Assistente\\nAgentAssistant\\nchat_with_tools()"]:::stCls
            PC["⚙️ Settings\\n🗄️ DatabaseOverview\\nEmbedding Management"]:::stCls
        end

        subgraph AAUTH["🔐 Autenticação — SHA-256 / session"]
            direction LR
            ROLE["session_state\\n_role · _autenticado"]:::authCls
            GATE["is_admin()\\nadmin gate"]:::authCls
            ROLE --> GATE
        end

        subgraph ATOOLS["🛠️ AssistantToolExecutor — 22 ferramentas"]
            direction LR
            TG1["📊 Dados das Reuniões\\n11 tools — meeting_list · participants\\ndecisions · action_items · summary\\nsearch_transcript · requirements\\nlist_bpmn_processes · sbvr_terms\\nsbvr_rules · get_system_capabilities"]:::tCls
            TG2["📅 Google Calendar\\n7 tools\\nlist_events · get_event · suggest_time\\n★ create_event · ★ schedule_action_items\\n★ share_with_user · ★ revoke_access\\n★ calendar_diagnose"]:::tCls
            TG3["🔒 Admin\\n4 tools\\n★ get_database_integrity\\n★ fix_missing_llm_provider\\n★ generate_meeting_embeddings\\n★ reprocess_meeting_full"]:::tCls
        end

        GATE -.->|"admin check"| TG2 & TG3
        PB --> TG1 & TG2 & TG3
    end

    subgraph MOD["⚙️ Módulos de Integração"]
        direction LR
        MLLM["🤖 base_agent.py\\nOpenAI SDK compat · Anthropic SDK\\nJSON retry · token tracking"]:::modCls
        MCAL["📅 calendar_client.py\\n_load_calendar_id(project_id)\\nproject_calendar_config → st.secrets\\n→ arquivo local → primary\\nService Account JWT"]:::modCls
        MSBC["🗄️ supabase_client.py\\nsingleton client\\nproject_store.py CRUD\\npgvector cosine search"]:::modCls
        MEMB["🧮 embeddings.py\\ngemini-embedding-001\\nvector(1536) · auto-retry 429\\n1.2 s delay · free 100 req/min"]:::modCls
    end

    subgraph EXT["🌐 Serviços Externos"]
        direction LR
        GCAL["📅 Google Calendar API\\nACL · Events · FreeBusy\\nOAuth2 service account JWT\\nrequer owner ACL p/ share/revoke"]:::extCls
        SB["🗄️ Supabase\\nPostgreSQL + pgvector RLS\\nproject_calendar_config\\ntranscript_chunks vector(1536)"]:::extCls
        GGEMB["🧮 Gemini Embedding API\\ngemini-embedding-001\\n1536 dims (output_dimensionality)"]:::sCls
        PROV["⚡ LLM Providers\\nDeepSeek · Claude · OpenAI\\nGroq · Gemini\\nHTTPS REST API"]:::lCls
    end

    subgraph MCP["🔌 MCP Server — Claude Code CLI (dev only)"]
        direction LR
        CLI["Claude Code CLI\\n/mcp google-calendar"]:::mcpCls
        SRV["google_calendar_server.py\\nFastMCP · stdio transport\\n8 tools · timezone UTC→Sao_Paulo"]:::mcpCls
        CLI <-->|"MCP protocol\\n(stdio)"| SRV
    end

    PA & PB --> MLLM
    TG1 & TG3 --> MSBC
    TG2 --> MCAL
    PB & PC --> MEMB
    PC --> MSBC

    MLLM      -->|"HTTPS REST"| PROV
    MCAL      -->|"REST · JWT Bearer"| GCAL
    MCAL      -.->|"calendar_id resolution"| SB
    MSBC      -->|"PostgREST · HTTPS"| SB
    MEMB      -->|"HTTPS REST"| GGEMB
    SRV       -->|"REST · JWT Bearer\\n(caminho independente)"| GCAL\
"""


# ── SVG fetch (cached) ────────────────────────────────────────────────────────

@st.cache_data(show_spinner=False)
def _fetch_comms_svg(diagram_code: str) -> tuple[str | None, str | None]:
    """Fetch comms architecture SVG from mermaid.ink — cached for server lifetime."""
    try:
        encoded = base64.urlsafe_b64encode(diagram_code.encode("utf-8")).decode("ascii")
        url = f"https://mermaid.ink/svg/{encoded}"
        req = urllib.request.Request(url, headers={"User-Agent": "Process2Diagram/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
        if not raw or "<svg" not in raw.lower():
            return None, "Resposta sem SVG"

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
    <button onclick="zoomIn()"     title="Zoom in">+</button>
    <button onclick="zoomOut()"    title="Zoom out">&minus;</button>
    <button onclick="fit()"        title="Ajustar">&#8865;</button>
    <button onclick="reset()"      title="Resetar">&#8634;</button>
    <button onclick="openNewTab()" title="Abrir em nova janela" style="font-size:11px;letter-spacing:-.5px">&#10696;</button>
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
  window.openNewTab=function(){{
    var html='<!DOCTYPE html>'+document.documentElement.outerHTML;
    var blob=new Blob([html],{{type:'text/html;charset=utf-8'}});
    var url=URL.createObjectURL(blob);
    var w=(window.top||window).open(url,'_blank');
    if(!w)window.open(url,'_blank');
  }};
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

def render_comms_diagram(height: int = 760) -> None:
    """
    Render the communication & integration architecture diagram.

    SVG is fetched from mermaid.ink once and cached for the Streamlit server
    lifetime. Subsequent reruns use the cached copy — no additional network call.
    """
    svg, err = _fetch_comms_svg(COMMS_DIAGRAM)

    if svg:
        viewer = _viewer_html(svg, height)
        components.html(viewer, height=height, scrolling=False)
    else:
        st.warning(f"⚠️ Não foi possível renderizar o diagrama: {err}")
        encoded = base64.urlsafe_b64encode(
            COMMS_DIAGRAM.encode("utf-8")
        ).decode("ascii")
        st.markdown(
            f"[🔗 Abrir no Mermaid Live](https://mermaid.live/edit#{encoded})",
            unsafe_allow_html=False,
        )
        with st.expander("📝 Código Mermaid", expanded=False):
            st.code(COMMS_DIAGRAM, language="text")
