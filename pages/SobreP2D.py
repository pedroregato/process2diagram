# pages/SobreP2D.py
# ─────────────────────────────────────────────────────────────────────────────
# Sobre o Process2Diagram — design fiel à apresentação executiva (FGV)
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import base64
import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from ui.auth_gate import apply_auth_gate

apply_auth_gate()

# ── Foto do autor em base64 ───────────────────────────────────────────────────
_PHOTO_PATH = root_dir / "assets" / "pedro_regato.png"
_PHOTO_B64 = ""
if _PHOTO_PATH.exists():
    _PHOTO_B64 = base64.b64encode(_PHOTO_PATH.read_bytes()).decode()

_PHOTO_SRC = (
    f"data:image/png;base64,{_PHOTO_B64}"
    if _PHOTO_B64
    else ""
)

# ── CSS — mesmo design da apresentação FGV ────────────────────────────────────
st.markdown("""
<style>
:root {
  --navy:  #0B1F3A;
  --navy2: #112848;
  --gold:  #C9973A;
  --gold2: #E8B84B;
  --white: #F4F6FA;
  --muted: #8A9BC4;
  --green: #2ECC71;
  --red:   #E74C3C;
  --blue:  #3498DB;
  --bg:    #060E1C;
}

/* Fundo da página */
.stApp { background: var(--bg) !important; }

/* ── Slide card ── */
.slide-card {
  background: var(--navy);
  border: 1px solid #1E3456;
  border-radius: 14px;
  padding: 48px 56px;
  margin-bottom: 24px;
  box-shadow: 0 20px 60px rgba(0,0,0,.5);
}

/* ── Label ── */
.label {
  font-size: 11px; font-weight: 700; letter-spacing: 2.5px;
  color: var(--gold); text-transform: uppercase; margin-bottom: 10px;
}

/* ── Tipografia ── */
.slide-card h1 { font-size: 42px; font-weight: 700; line-height: 1.15; color: var(--white); }
.slide-card h1 span { color: var(--gold2); }
.slide-card h2 { font-size: 26px; font-weight: 700; color: var(--white); margin-bottom: 6px; }
.slide-card h3 { font-size: 17px; font-weight: 600; color: var(--gold2); margin-bottom: 8px; }
.slide-card p  { font-size: 15px; color: #BDC8E0; line-height: 1.65; }
.slide-card ul { padding-left: 20px; }
.slide-card li { font-size: 15px; color: #BDC8E0; line-height: 1.65; margin-bottom: 6px; }

/* ── Motto ── */
.motto {
  font-size: 18px; font-style: italic; color: var(--gold2);
  line-height: 1.55; margin: 18px 0 26px;
  border-left: 3px solid var(--gold); padding-left: 18px;
}

/* ── Cover line ── */
.cover-line { height: 3px; width: 80px; background: var(--gold); margin: 20px 0; }

/* ── Tag / badge ── */
.tag {
  display: inline-block; font-size: 11px; font-weight: 700;
  padding: 4px 10px; border-radius: 12px; letter-spacing: .5px; margin: 3px 2px;
}
.tag.blue  { background:#1A4070; color:#7EC8F5; }
.tag.gold  { background:#3A2900; color:var(--gold2); }
.tag.green { background:#0D3020; color:#5DE8A0; }
.tag.red   { background:#3A0D0D; color:#F59B9B; }
.tag.gray  { background:#1A2436; color:var(--muted); }

/* ── Stat box ── */
.cols-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-top: 28px; }
.cols-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-top: 20px; }
.cols-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 22px; margin-top: 20px; }
.stat {
  background: #0D1F38; border: 1px solid #1E3456;
  border-radius: 10px; padding: 20px 18px; text-align: center;
}
.stat .number { font-size: 34px; font-weight: 800; color: var(--gold2); line-height: 1; }
.stat .unit   { font-size: 13px; color: var(--gold); margin-top: 2px; }
.stat .desc   { font-size: 12px; color: var(--muted); margin-top: 8px; line-height: 1.4; }

/* ── Card ── */
.card {
  background: #0D1F38; border: 1px solid #1E3456;
  border-radius: 10px; padding: 18px 20px;
}
.card.gold-border { border-color: var(--gold); }
.card.red-border  { border-color: var(--red); }
.card p { font-size: 14px; color: #BDC8E0; line-height: 1.65; margin: 0; }

/* ── Pipeline ── */
.pipeline {
  display: flex; align-items: center; gap: 6px;
  flex-wrap: wrap; margin-top: 18px;
}
.pipe-step {
  background: #0D1F38; border: 1px solid #1E3456;
  border-radius: 8px; padding: 8px 14px;
  font-size: 12px; color: #BDC8E0; white-space: nowrap;
}
.pipe-step.highlight { border-color: var(--gold); color: var(--gold2); }
.pipe-arrow { color: var(--gold); font-size: 18px; }

/* ── ROI bar ── */
.roi-row { margin-bottom: 14px; }
.roi-label {
  display: flex; justify-content: space-between;
  font-size: 13px; color: #BDC8E0; margin-bottom: 5px;
}
.roi-bar-bg { height: 10px; background: #0D1F38; border-radius: 5px; }
.roi-bar    { height: 10px; border-radius: 5px;
              background: linear-gradient(90deg, var(--gold), var(--gold2)); }

/* ── Divider ── */
.divider { height: 1px; background: #1E3456; margin: 20px 0; }

/* ── Autor ── */
.autor-block {
  display: flex; gap: 40px; align-items: flex-start; margin-top: 8px;
}
.autor-col-left { flex-shrink: 0; text-align: center; width: 160px; }
.autor-col-left img {
  width: 130px; height: 130px; border-radius: 50%;
  object-fit: cover; border: 3px solid var(--gold);
  display: block; margin: 0 auto;
}
.autor-col-left .a-name {
  font-size: 14px; font-weight: 700; color: var(--white);
  margin-top: 14px; line-height: 1.35;
}
.autor-col-left .a-role {
  font-size: 11px; color: var(--gold2); margin-top: 5px;
}
.autor-col-left .a-bio {
  font-size: 10px; color: var(--muted); margin-top: 8px; line-height: 1.5;
}
.autor-col-right { flex: 1; }

/* ── Watermark ── */
.watermark {
  text-align: right; margin-top: 24px;
  font-size: 11px; color: #1E3456; font-weight: 700; letter-spacing: 2px;
}
</style>
""", unsafe_allow_html=True)


# ── SLIDE 1 — CAPA ────────────────────────────────────────────────────────────
st.markdown("""
<div class="slide-card" style="background:linear-gradient(135deg,#0B1F3A 0%,#071428 60%,#0D1F38 100%);">
  <div class="label">Plataforma de Inteligência Artificial — Visão Geral</div>
  <h1>Process<span>2</span>Diagram</h1>
  <div class="cover-line"></div>
  <div class="motto">
    "Reunião — o ativo intangível que gera<br>maior impacto tangível nas corporações."
  </div>
  <p style="color:var(--muted); font-size:14px; max-width:520px;">
    Uma plataforma de Inteligência Artificial que transforma o conhecimento gerado
    em reuniões em artefatos formais, rastreáveis e auditáveis — em minutos.
  </p>
  <div style="margin-top:24px; display:flex; gap:8px; flex-wrap:wrap;">
    <span class="tag blue">BPMN 2.0</span>
    <span class="tag gold">Requisitos IEEE 830</span>
    <span class="tag green">Governança</span>
    <span class="tag blue">IA Generativa</span>
    <span class="tag gold">Grafo de Conhecimento</span>
    <span class="tag green">Auditoria</span>
    <span class="tag gray">Multi-LLM</span>
    <span class="tag gray">Supabase + pgvector</span>
  </div>
  <div class="watermark">P2D v4.32</div>
</div>
""", unsafe_allow_html=True)


# ── SLIDE 2 — O PARADOXO ──────────────────────────────────────────────────────
st.markdown("""
<div class="slide-card">
  <div class="label">O paradoxo corporativo</div>
  <h2>O ativo mais caro da empresa é o menos documentado</h2>
  <p style="margin-top:14px; max-width:700px;">
    Reuniões executivas concentram as decisões mais estratégicas de uma organização.
    São o momento onde estratégia vira compromisso, onde requisitos são definidos,
    onde processos são redesenhados. E, paradoxalmente, onde o conhecimento mais evapora.
  </p>

  <div class="cols-4">
    <div class="stat">
      <div class="number">71%</div>
      <div class="unit">das decisões</div>
      <div class="desc">estratégicas nascem em reuniões corporativas</div>
    </div>
    <div class="stat">
      <div class="number">R$&nbsp;8.2k</div>
      <div class="unit">por hora</div>
      <div class="desc">custo médio de 1h de reunião executiva no Brasil</div>
    </div>
    <div class="stat">
      <div class="number">2,3h</div>
      <div class="unit">por dia</div>
      <div class="desc">tempo médio de executivos em reuniões (Harvard)</div>
    </div>
    <div class="stat">
      <div class="number">67%</div>
      <div class="unit">do conhecimento</div>
      <div class="desc">gerado em reuniões nunca é formalizado (Gartner)</div>
    </div>
  </div>

  <div class="card red-border" style="margin-top:22px;">
    <p style="color:#F59B9B; font-weight:600;">
      ⚠️ Uma organização com 50 executivos que se reúnem 2h/dia gasta
      <strong style="color:var(--white);">R$ 3,5 milhões/ano em reuniões</strong> —
      e documenta menos de <strong style="color:var(--white);">33% do conhecimento gerado</strong>.
    </p>
  </div>
</div>
""", unsafe_allow_html=True)


# ── SLIDE 3 — O QUE É ────────────────────────────────────────────────────────
st.markdown("""
<div class="slide-card">
  <div class="label">O que é o Process2Diagram</div>
  <h2>Da transcrição ao artefato formal — em minutos</h2>

  <p style="margin-top:14px; max-width:680px;">
    O P2D é um pipeline de múltiplos agentes LLM encadeados que processa transcrições
    de reuniões e gera automaticamente todos os artefatos de análise de processos exigidos
    por frameworks de governança corporativa.
  </p>

  <div class="pipeline" style="margin-top:24px;">
    <div class="pipe-step">📄 Transcrição</div>
    <span class="pipe-arrow">→</span>
    <div class="pipe-step">🔬 Qualidade</div>
    <span class="pipe-arrow">→</span>
    <div class="pipe-step">🧹 Pré-proc.</div>
    <span class="pipe-arrow">→</span>
    <div class="pipe-step">🔍 NLP / NER</div>
    <span class="pipe-arrow">→</span>
    <div class="pipe-step highlight">📐 AgentBPMN</div>
    <span class="pipe-arrow">→</span>
    <div class="pipe-step">📋 Ata + Req.</div>
    <span class="pipe-arrow">→</span>
    <div class="pipe-step">📖 SBVR + BMM</div>
    <span class="pipe-arrow">→</span>
    <div class="pipe-step highlight">🧠 KnowledgeHub</div>
  </div>

  <div class="cols-3" style="margin-top:26px;">
    <div class="card gold-border">
      <h3>Input</h3>
      <p>Texto bruto, .txt, .docx ou .pdf — transcrição de qualquer ferramenta
      (Teams, Zoom, Google Meet, manual).</p>
    </div>
    <div class="card">
      <h3>Processamento</h3>
      <p>8 agentes especializados em sequência e paralelo, com retry adaptativo
      via LangGraph e torneio multi-pass para BPMN.</p>
    </div>
    <div class="card gold-border">
      <h3>Output</h3>
      <p>BPMN 2.0 · Mermaid · Ata Word/PDF · Requisitos IEEE 830 · SBVR · BMM ·
      DMN · Relatório HTML · Grafo de Conhecimento.</p>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ── SLIDE 4 — CAPACIDADES ─────────────────────────────────────────────────────
st.markdown("""
<div class="slide-card">
  <div class="label">Capacidades</div>
  <h2>12 artefatos gerados automaticamente</h2>

  <div class="cols-3" style="margin-top:22px;">
    <div class="card">
      <h3>📐 BPMN 2.0</h3>
      <p>Diagrama com lanes, gateways e eventos. Visualizador bpmn-js embutido
      com pan, zoom, editor visual e histórico de versões.</p>
    </div>
    <div class="card">
      <h3>📋 Ata de Reunião</h3>
      <p>Minuta estruturada com participantes, pauta, decisões e encaminhamentos.
      Exportável em Markdown, Word (.docx) e PDF.</p>
    </div>
    <div class="card">
      <h3>📝 Requisitos IEEE 830</h3>
      <p>Extração estruturada com código, tipo, prioridade e rastreabilidade
      por reunião. Rastreados ao longo do projeto.</p>
    </div>
    <div class="card">
      <h3>📖 Vocabulário SBVR</h3>
      <p>Termos de negócio e regras formais no padrão OMG SBVR —
      base para governança e compliance.</p>
    </div>
    <div class="card">
      <h3>🎯 Modelo BMM</h3>
      <p>Visão, missão, objetivos, estratégias e políticas no padrão OMG BMM —
      alinha processos à estratégia corporativa.</p>
    </div>
    <div class="card">
      <h3>⚖️ Tabelas DMN</h3>
      <p>Regras de negócio no padrão OMG DMN 1.4 com DRD topológico e
      renderizador dark-theme embutido.</p>
    </div>
    <div class="card">
      <h3>📄 Relatório Executivo</h3>
      <p>Síntese HTML auto-contido com métricas e destaques —
      pronto para enviar a stakeholders sem instalação.</p>
    </div>
    <div class="card">
      <h3>💬 Assistente RAG</h3>
      <p>Chat com 90+ ferramentas de consulta ao banco —
      tool-use ou RAG clássico com pgvector.</p>
    </div>
    <div class="card">
      <h3>🕸️ Grafo de Conhecimento</h3>
      <p>Entidades, contradições e fatos indexados de múltiplas reuniões —
      visualização Obsidian com física pyvis.</p>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ── SLIDE 5 — PROVEDORES LLM ──────────────────────────────────────────────────
st.markdown("""
<div class="slide-card">
  <div class="label">Infraestrutura de IA</div>
  <h2>Multi-LLM — cada agente usa o melhor modelo para seu papel</h2>

  <div class="cols-2" style="margin-top:22px;">
    <div>
      <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <thead>
          <tr>
            <th style="background:#0D1F38;color:var(--gold);font-weight:700;padding:10px 14px;
                       text-align:left;border-bottom:2px solid #1E3456;font-size:11px;
                       letter-spacing:1px;text-transform:uppercase;">Provedor</th>
            <th style="background:#0D1F38;color:var(--gold);font-weight:700;padding:10px 14px;
                       text-align:left;border-bottom:2px solid #1E3456;font-size:11px;
                       letter-spacing:1px;text-transform:uppercase;">Modelo padrão</th>
            <th style="background:#0D1F38;color:var(--gold);font-weight:700;padding:10px 14px;
                       text-align:left;border-bottom:2px solid #1E3456;font-size:11px;
                       letter-spacing:1px;text-transform:uppercase;">Contexto</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style="padding:9px 14px;border-bottom:1px solid #141F30;color:var(--white);font-weight:600;">DeepSeek V4 Flash ⭐</td>
            <td style="padding:9px 14px;border-bottom:1px solid #141F30;color:#BDC8E0;">deepseek-v4-flash</td>
            <td style="padding:9px 14px;border-bottom:1px solid #141F30;color:#BDC8E0;">1M tokens</td>
          </tr>
          <tr>
            <td style="padding:9px 14px;border-bottom:1px solid #141F30;color:var(--white);font-weight:600;">DeepSeek V4 Pro</td>
            <td style="padding:9px 14px;border-bottom:1px solid #141F30;color:#BDC8E0;">deepseek-v4-pro</td>
            <td style="padding:9px 14px;border-bottom:1px solid #141F30;color:#BDC8E0;">1M tokens</td>
          </tr>
          <tr>
            <td style="padding:9px 14px;border-bottom:1px solid #141F30;color:var(--white);font-weight:600;">Claude (Anthropic)</td>
            <td style="padding:9px 14px;border-bottom:1px solid #141F30;color:#BDC8E0;">claude-sonnet-4</td>
            <td style="padding:9px 14px;border-bottom:1px solid #141F30;color:#BDC8E0;">200K tokens</td>
          </tr>
          <tr>
            <td style="padding:9px 14px;border-bottom:1px solid #141F30;color:var(--white);font-weight:600;">OpenAI</td>
            <td style="padding:9px 14px;border-bottom:1px solid #141F30;color:#BDC8E0;">gpt-4o-mini</td>
            <td style="padding:9px 14px;border-bottom:1px solid #141F30;color:#BDC8E0;">128K tokens</td>
          </tr>
          <tr>
            <td style="padding:9px 14px;border-bottom:1px solid #141F30;color:var(--white);font-weight:600;">Groq (Llama)</td>
            <td style="padding:9px 14px;border-bottom:1px solid #141F30;color:#BDC8E0;">llama-3.3-70b</td>
            <td style="padding:9px 14px;border-bottom:1px solid #141F30;color:#BDC8E0;">128K tokens</td>
          </tr>
          <tr>
            <td style="padding:9px 14px;border-bottom:1px solid #141F30;color:var(--white);font-weight:600;">Google Gemini</td>
            <td style="padding:9px 14px;border-bottom:1px solid #141F30;color:#BDC8E0;">gemini-2.0-flash</td>
            <td style="padding:9px 14px;border-bottom:1px solid #141F30;color:#BDC8E0;">1M tokens</td>
          </tr>
          <tr>
            <td style="padding:9px 14px;color:var(--white);font-weight:600;">Grok (xAI)</td>
            <td style="padding:9px 14px;color:#BDC8E0;">grok-4-1-fast</td>
            <td style="padding:9px 14px;color:#BDC8E0;">2M tokens</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div style="display:flex;flex-direction:column;gap:14px;">
      <div class="card gold-border">
        <h3>Cenários de Custo-Benefício</h3>
        <p>Cada agente pode usar um provedor diferente. Compare combinações de
        modelos e selecione o perfil ideal por agente antes de processar.</p>
      </div>
      <div class="card">
        <h3>Cache Semântico</h3>
        <p>Respostas cacheadas via SHA-256 no Supabase — evita chamadas
        duplicadas e reduz custo em reprocessamentos.</p>
      </div>
      <div class="card">
        <h3>Long Context</h3>
        <p>Detecção automática de transcrições longas (&gt;50k tokens) —
        ajusta <code>max_tokens</code> e timeout por agente.</p>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ── SLIDE 6 — CRÉDITO / AGRADECIMENTOS ───────────────────────────────────────
_photo_html = (
    f'<img src="{_PHOTO_SRC}" alt="Pedro Gentil Regato de Oliveira Soares">'
    if _PHOTO_SRC
    else '<div style="width:130px;height:130px;border-radius:50%;background:#0D1F38;'
         'border:3px solid var(--gold);display:flex;align-items:center;justify-content:center;'
         'font-size:2rem;font-weight:800;color:var(--gold);margin:0 auto;">PGR</div>'
)

st.markdown(f"""
<div class="slide-card">
  <div class="label">Criador</div>

  <div class="autor-block">

    <!-- Coluna esquerda: autor -->
    <div class="autor-col-left">
      {_photo_html}
      <div class="a-name">Pedro Gentil Regato<br>de Oliveira Soares</div>
      <div class="a-role">Estatístico &amp; BPM Sênior</div>
      <div class="a-bio">
        Da automação de processos<br>à IA em produção —<br>
        soluções que integram<br>modelo, fluxo e sistema.
      </div>
    </div>

    <!-- Coluna direita -->
    <div class="autor-col-right">

      <div class="card gold-border" style="margin-bottom:18px;">
        <p style="color:var(--white);">
          O <strong style="color:var(--gold2);">Process2Diagram</strong> é resultado exclusivo de
          <strong>esforço pessoal</strong> de estudo, investigação e experimentação contínuas —
          nascido da convicção de que o conhecimento gerado em reuniões corporativas é o ativo
          estratégico mais desperdiçado das organizações modernas.<br><br>
          Cada linha de código, cada agente, cada ferramenta foi construída com a crença de que
          <em style="color:var(--gold2);">a IA generativa, quando bem orientada por padrões formais,
          transforma conversa em governança</em>.
        </p>
      </div>

      <h3 style="margin-bottom:12px;">Valor concreto para a organização que adotar o P2D</h3>

      <div class="cols-2" style="gap:10px;">
        <div>
          <div class="roi-row">
            <div class="roi-label">
              <span>⏱️ Formalização de processos</span>
              <span style="color:var(--gold2);">−90%</span>
            </div>
            <div class="roi-bar-bg"><div class="roi-bar" style="width:90%"></div></div>
          </div>
          <div class="roi-row">
            <div class="roi-label">
              <span>🔁 Retrabalho por falta de documentação</span>
              <span style="color:var(--gold2);">−35%</span>
            </div>
            <div class="roi-bar-bg"><div class="roi-bar" style="width:35%"></div></div>
          </div>
          <div class="roi-row">
            <div class="roi-label">
              <span>🚀 Onboarding de novos membros</span>
              <span style="color:var(--gold2);">+80%</span>
            </div>
            <div class="roi-bar-bg"><div class="roi-bar" style="width:80%"></div></div>
          </div>
          <div class="roi-row">
            <div class="roi-label">
              <span>📐 Cobertura de artefatos por reunião</span>
              <span style="color:var(--gold2);">+320%</span>
            </div>
            <div class="roi-bar-bg"><div class="roi-bar" style="width:95%"></div></div>
          </div>
        </div>
        <div style="display:flex;flex-direction:column;gap:8px;">
          <div class="card" style="padding:12px 14px;">
            <p style="font-size:12px;">
              🧠 <strong style="color:var(--white);">Memória corporativa persistente</strong><br>
              Conhecimento não se perde quando pessoas saem — fica indexado e consultável.
            </p>
          </div>
          <div class="card" style="padding:12px 14px;">
            <p style="font-size:12px;">
              ⚖️ <strong style="color:var(--white);">Governança e compliance</strong><br>
              Trilha de auditoria completa: decisão → requisito → processo → regra DMN.
            </p>
          </div>
          <div class="card" style="padding:12px 14px;">
            <p style="font-size:12px;">
              🎯 <strong style="color:var(--white);">Reuniões mais eficientes</strong><br>
              Pauta gerada automaticamente a partir de pendências reais — sem repetição.
            </p>
          </div>
          <div class="card" style="padding:12px 14px;">
            <p style="font-size:12px;">
              🔍 <strong style="color:var(--white);">Detecção proativa de riscos</strong><br>
              Contradições identificadas antes de virarem problemas em produção.
            </p>
          </div>
        </div>
      </div>

      <div class="divider"></div>
      <p style="font-size:12px;color:var(--muted);margin-top:0;">
        pedro.regato@gmail.com &nbsp;·&nbsp; P2D v4.32 &nbsp;·&nbsp; Streamlit Cloud
      </p>

    </div>
  </div>
</div>
""", unsafe_allow_html=True)
