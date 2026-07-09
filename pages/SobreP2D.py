# pages/SobreP2D.py
# ─────────────────────────────────────────────────────────────────────────────
# Sobre o Process2Diagram — autor, filosofia do produto e aprofundamento técnico
# (CKF, Multi-LLM). Estatísticas de mercado, ROI e a lista completa de
# artefatos vivem em pages/ApresentacaoGeral.py — não duplicar aqui (PC136).
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

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
:root {
  --navy:  #0B1F3A;
  --navy2: #112848;
  --gold:  #C9973A;
  --gold2: #E8B84B;
  --white: #F0F4FA;
  --muted: #A8B8D8;
  --green: #2ECC71;
  --red:   #E74C3C;
  --blue:  #3498DB;
  --bg:    #060E1C;
  --text:  #CDD8EC;
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
  font-size: 12px; font-weight: 700; letter-spacing: 2.5px;
  color: var(--gold); text-transform: uppercase; margin-bottom: 12px;
}

/* ── Tipografia ── */
.slide-card h1 { font-size: 44px; font-weight: 700; line-height: 1.15; color: var(--white); }
.slide-card h1 span { color: var(--gold2); }
.slide-card h2 { font-size: 28px; font-weight: 700; color: var(--white); margin-bottom: 8px; }
.slide-card h3 { font-size: 19px; font-weight: 600; color: var(--gold2); margin-bottom: 10px; }
.slide-card p  { font-size: 16px; color: var(--text); line-height: 1.7; }
.slide-card ul { padding-left: 20px; }
.slide-card li { font-size: 16px; color: var(--text); line-height: 1.7; margin-bottom: 6px; }

/* ── Motto ── */
.motto {
  font-size: 20px; font-style: italic; color: var(--gold2);
  line-height: 1.6; margin: 20px 0 28px;
  border-left: 3px solid var(--gold); padding-left: 20px;
}

/* ── Cover line ── */
.cover-line { height: 3px; width: 80px; background: var(--gold); margin: 20px 0; }

/* ── Tag / badge ── */
.tag {
  display: inline-block; font-size: 12px; font-weight: 700;
  padding: 5px 12px; border-radius: 12px; letter-spacing: .5px; margin: 3px 2px;
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
  border-radius: 10px; padding: 22px 18px; text-align: center;
}
.stat .number { font-size: 36px; font-weight: 800; color: var(--gold2); line-height: 1; }
.stat .unit   { font-size: 14px; color: var(--gold); margin-top: 4px; }
.stat .desc   { font-size: 13px; color: var(--muted); margin-top: 10px; line-height: 1.5; }

/* ── Card ── */
.card {
  background: #0D1F38; border: 1px solid #1E3456;
  border-radius: 10px; padding: 20px 22px;
}
.card.gold-border { border-color: var(--gold); }
.card.red-border  { border-color: var(--red); }
.card p { font-size: 15px; color: var(--text); line-height: 1.7; margin: 0; }

/* ── Pipeline ── */
.pipeline {
  display: flex; align-items: center; gap: 6px;
  flex-wrap: wrap; margin-top: 18px;
}
.pipe-step {
  background: #0D1F38; border: 1px solid #1E3456;
  border-radius: 8px; padding: 9px 15px;
  font-size: 13px; color: var(--text); white-space: nowrap;
}
.pipe-step.highlight { border-color: var(--gold); color: var(--gold2); }
.pipe-arrow { color: var(--gold); font-size: 18px; }

/* ── ROI bar ── */
.roi-row { margin-bottom: 16px; }
.roi-label {
  display: flex; justify-content: space-between;
  font-size: 14px; color: var(--text); margin-bottom: 6px;
}
.roi-bar-bg { height: 10px; background: #0D1F38; border-radius: 5px; }
.roi-bar    { height: 10px; border-radius: 5px;
              background: linear-gradient(90deg, var(--gold), var(--gold2)); }

/* ── Divider ── */
.divider { height: 1px; background: #1E3456; margin: 22px 0; }

/* ── Autor ── */
.autor-block {
  display: flex; gap: 44px; align-items: flex-start; margin-top: 10px;
}
.autor-col-left { flex-shrink: 0; text-align: center; width: 170px; }
.autor-col-left img {
  width: 140px; height: 140px; border-radius: 50%;
  object-fit: cover; border: 3px solid var(--gold);
  display: block; margin: 0 auto;
}
.autor-col-left .a-name {
  font-size: 15px; font-weight: 700; color: var(--white);
  margin-top: 14px; line-height: 1.4;
}
.autor-col-left .a-role {
  font-size: 13px; color: var(--gold2); margin-top: 6px;
}
.autor-col-left .a-bio {
  font-size: 12px; color: var(--muted); margin-top: 10px; line-height: 1.6;
}
.autor-col-right { flex: 1; }

/* ── Watermark ── */
.watermark {
  text-align: right; margin-top: 24px;
  font-size: 12px; color: #1E3456; font-weight: 700; letter-spacing: 2px;
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
  <p style="color:var(--muted); font-size:16px; max-width:540px;">
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
    <span class="tag gray">Busca Semântica Avançada</span>
  </div>
  <div class="watermark">P2D v5.15</div>
</div>
""", unsafe_allow_html=True)


# ── SLIDE 2 — CRIADOR ────────────────────────────────────────────────────────
_photo_html = (
    f'<img src="{_PHOTO_SRC}" alt="Pedro Gentil Regato de Oliveira Soares">'
    if _PHOTO_SRC
    else '<div style="width:140px;height:140px;border-radius:50%;background:#0D1F38;'
         'border:3px solid var(--gold);display:flex;align-items:center;justify-content:center;'
         'font-size:2rem;font-weight:800;color:var(--gold);margin:0 auto;">PGR</div>'
)
st.markdown(f"""
<div class="slide-card" style="background:linear-gradient(135deg,#0D1F38 0%,#0B1F3A 100%);border-color:var(--gold);">
  <div class="label">Criador</div>
  <div class="autor-block">
    <div class="autor-col-left">
      {_photo_html}
      <div class="a-name">Pedro Gentil Regato<br>de Oliveira Soares</div>
      <div class="a-role">Estatístico &amp; BPM Sênior</div>
      <div class="a-bio">Da automação de processos<br>à IA em produção —<br>soluções que integram<br>modelo, fluxo e sistema.</div>
    </div>
    <div class="autor-col-right">
      <div class="card gold-border" style="margin-bottom:20px;">
        <p style="color:var(--white);font-size:16px;">
          O <strong style="color:var(--gold2);">Process2Diagram</strong> é resultado exclusivo de
          <strong>esforço pessoal</strong> de estudo, investigação e experimentação contínuas —
          nascido da convicção de que o conhecimento gerado em reuniões corporativas é o ativo
          estratégico mais desperdiçado das organizações modernas.<br><br>
          Cada linha de código, cada agente, cada ferramenta foi construída com a crença de que
          <em style="color:var(--gold2);">a IA generativa, quando bem orientada por padrões formais,
          transforma conversa em governança</em>.
        </p>
      </div>
      <h3 style="margin-bottom:14px;">O que orienta o desenvolvimento</h3>
      <p style="margin-bottom:20px;">
        Rigor metodológico — BPMN 2.0, IEEE 830, SBVR, DMN, BMM, todos padrões formais
        OMG/IEEE — aplicado com o mesmo cuidado dedicado a cada linha de prompt de IA.
        Não se trata de gerar diagramas bonitos; trata-se de gerar artefatos que resistem
        a uma auditoria.
      </p>
      <div class="cols-2" style="gap:12px;">
        <div class="card" style="padding:14px 16px;">
          <p style="font-size:14px;">🧠 <strong style="color:var(--white);">Memória corporativa persistente</strong><br>Conhecimento não se perde quando pessoas saem — fica indexado e consultável.</p>
        </div>
        <div class="card" style="padding:14px 16px;">
          <p style="font-size:14px;">⚖️ <strong style="color:var(--white);">Governança e compliance</strong><br>Trilha de auditoria completa: decisão → requisito → processo → regra DMN.</p>
        </div>
        <div class="card" style="padding:14px 16px;">
          <p style="font-size:14px;">🎯 <strong style="color:var(--white);">Reuniões mais eficientes</strong><br>Pauta gerada automaticamente a partir de pendências reais — sem repetição.</p>
        </div>
        <div class="card" style="padding:14px 16px;">
          <p style="font-size:14px;">🔍 <strong style="color:var(--white);">Detecção proativa de riscos</strong><br>Contradições identificadas antes de virarem problemas em produção.</p>
        </div>
      </div>
      <div class="divider"></div>
      <p style="font-size:14px;color:var(--muted);margin-top:0;">pedro.regato@gmail.com &nbsp;·&nbsp; P2D v5.15</p>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ── SLIDE 3 — O QUE É ────────────────────────────────────────────────────────
st.markdown("""
<div class="slide-card">
  <div class="label">O que é o Process2Diagram</div>
  <h2>Da transcrição ao artefato formal — em minutos</h2>
  <p style="margin-top:14px; max-width:680px;">
    O P2D é um pipeline de inteligência artificial multi-agente que processa transcrições
    de reuniões e gera automaticamente todos os artefatos de análise de processos exigidos
    por frameworks de governança corporativa.
  </p>
  <div class="pipeline" style="margin-top:24px;">
    <div class="pipe-step">📄 Transcrição</div>
    <span class="pipe-arrow">→</span>
    <div class="pipe-step highlight">🤖 IA Multi-Agente</div>
    <span class="pipe-arrow">→</span>
    <div class="pipe-step highlight">📐 Diagramas e Documentos Formais</div>
    <span class="pipe-arrow">→</span>
    <div class="pipe-step highlight">🧠 Base de Conhecimento</div>
  </div>
  <div class="cols-3" style="margin-top:26px;">
    <div class="card gold-border">
      <h3>Input</h3>
      <p>Texto bruto, .txt, .docx ou .pdf — transcrição de qualquer ferramenta
      (Teams, Zoom, Google Meet, manual).</p>
    </div>
    <div class="card">
      <h3>Processamento</h3>
      <p>Múltiplos agentes de IA especializados, com verificação automática de
      qualidade e revisão adaptativa até atingir o padrão exigido.</p>
    </div>
    <div class="card gold-border">
      <h3>Output</h3>
      <p>BPMN 2.0 · Mermaid · Ata Word/PDF · Requisitos IEEE 830 · SBVR · BMM ·
      DMN · Relatório HTML · Grafo de Conhecimento.</p>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ── SLIDE 4 — CTA PARA LISTA COMPLETA DE ARTEFATOS ────────────────────────────
st.markdown("""
<div class="slide-card" style="text-align:center;">
  <div class="label">Capacidades</div>
  <h2>12 artefatos formais gerados automaticamente por reunião</h2>
  <p style="margin-top:14px; max-width:640px; margin-left:auto; margin-right:auto;">
    BPMN 2.0 · Mermaid · Ata Word/PDF · Requisitos IEEE 830 · SBVR · BMM ·
    DMN · Mapa de Requisitos · Relatório Executivo · Grafo de Conhecimento ·
    Assistente Conversacional · CKF atualizado.
  </p>
  <p style="margin-top:10px; color:var(--muted);">
    A lista completa, com descrição de cada artefato, está na Apresentação Geral ↓
  </p>
</div>
""", unsafe_allow_html=True)
st.page_link("pages/ApresentacaoGeral.py", label="→ Ver os 12 artefatos em detalhe na Apresentação Geral", icon="🎯")


# ── SLIDE 5 — CKF ────────────────────────────────────────────────────────────
st.markdown("""
<div class="slide-card">
  <div class="label">Context Knowledge File — Memória Institucional</div>
  <h2>O sistema que aprende com cada reunião processada</h2>
  <p style="margin-top:14px; max-width:740px;">
    O <strong>CKF (Context Knowledge File)</strong> é a memória institucional viva do P2D — um documento
    Markdown associado a cada projeto que evolui automaticamente após cada reunião processada.
    Todos os agentes consultam o CKF antes de analisar qualquer transcrição, tornando cada análise
    progressivamente mais precisa, contextualizada e alinhada ao vocabulário da organização.
  </p>
  <div class="cols-2" style="margin-top:24px;">
    <div>
      <h3>Como funciona o ciclo evolutivo</h3>
      <div class="card" style="margin-bottom:12px;">
        <p style="font-size:15px;"><strong style="color:var(--gold2);">1. Contexto inicial</strong><br>
        O usuário preenche o CKF com informações permanentes do negócio: participantes-chave,
        termos técnicos, processos existentes e objetivos estratégicos.</p>
      </div>
      <div class="card" style="margin-bottom:12px;">
        <p style="font-size:15px;"><strong style="color:var(--gold2);">2. Pipeline usa o CKF</strong><br>
        Todos os agentes recebem o CKF como contexto adicional — extraem termos corretos,
        reconhecem unidades organizacionais e respeitam regras já documentadas.</p>
      </div>
      <div class="card" style="margin-bottom:12px;">
        <p style="font-size:15px;"><strong style="color:var(--gold2);">3. CKF é enriquecido automaticamente</strong><br>
        O <em>AgentCKFUpdater</em> adiciona ao CKF os aprendizados de cada reunião —
        novos participantes, termos e processos — sem remover o que o usuário escreveu.</p>
      </div>
      <div class="card gold-border">
        <p style="font-size:15px;color:var(--white);"><strong style="color:var(--gold2);">Resultado:</strong>
        o P2D acumula conhecimento organizacional ao longo do tempo — tornando-se um especialista
        no negócio do cliente a cada ciclo de reuniões. O <strong style="color:var(--gold2);">Catálogo
        do Domínio</strong> leva essa memória além de um projeto isolado: ativos de negócio
        (requisitos, processos, regras) ficam descobríveis em todos os contextos da organização.</p>
      </div>
    </div>
    <div>
      <h3>Seções do CKF</h3>
      <div style="display:flex;flex-direction:column;gap:10px;">
        <div class="card gold-border" style="padding:12px 16px;">
          <p style="font-size:14px;">🏢 <strong style="color:var(--white);">Visão Geral do Contexto</strong><br>Propósito do projeto, área de negócio e escopo das reuniões.</p>
        </div>
        <div class="card" style="padding:12px 16px;">
          <p style="font-size:14px;">👥 <strong style="color:var(--white);">Participantes Frequentes</strong><br>Nomes, cargos e iniciais dos participantes habituais do contexto.</p>
        </div>
        <div class="card" style="padding:12px 16px;">
          <p style="font-size:14px;">📖 <strong style="color:var(--white);">Glossário e Termos Técnicos</strong><br>Vocabulário específico da organização — siglas, acrônimos, jargões internos.</p>
        </div>
        <div class="card" style="padding:12px 16px;">
          <p style="font-size:14px;">⚙️ <strong style="color:var(--white);">Processos de Negócio Conhecidos</strong><br>Fluxos e processos já mapeados que os agentes devem reconhecer.</p>
        </div>
        <div class="card" style="padding:12px 16px;">
          <p style="font-size:14px;">📐 <strong style="color:var(--white);">Regras de Negócio Permanentes</strong><br>Políticas e restrições aplicáveis a todos os processos do contexto.</p>
        </div>
        <div class="card gold-border" style="padding:12px 16px;">
          <p style="font-size:14px;">🎯 <strong style="color:var(--white);">Objetivos Estratégicos</strong><br>Visão, missão e metas que orientam a priorização de requisitos e decisões.</p>
        </div>
      </div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)


# ── SLIDE 6 — PROVEDORES LLM ──────────────────────────────────────────────────
st.markdown("""
<div class="slide-card">
  <div class="label">Infraestrutura de IA</div>
  <h2>Multi-LLM — cada agente usa o melhor modelo para seu papel</h2>
  <div class="cols-2" style="margin-top:22px;">
    <div>
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <thead>
          <tr>
            <th style="background:#0D1F38;color:var(--gold);font-weight:700;padding:11px 14px;
                       text-align:left;border-bottom:2px solid #1E3456;font-size:12px;
                       letter-spacing:1px;text-transform:uppercase;">Provedor</th>
            <th style="background:#0D1F38;color:var(--gold);font-weight:700;padding:11px 14px;
                       text-align:left;border-bottom:2px solid #1E3456;font-size:12px;
                       letter-spacing:1px;text-transform:uppercase;">Modelo padrão</th>
            <th style="background:#0D1F38;color:var(--gold);font-weight:700;padding:11px 14px;
                       text-align:left;border-bottom:2px solid #1E3456;font-size:12px;
                       letter-spacing:1px;text-transform:uppercase;">Contexto</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td style="padding:10px 14px;border-bottom:1px solid #141F30;color:var(--white);font-weight:600;">DeepSeek V4 Flash ⭐</td>
            <td style="padding:10px 14px;border-bottom:1px solid #141F30;color:var(--text);">deepseek-v4-flash</td>
            <td style="padding:10px 14px;border-bottom:1px solid #141F30;color:var(--text);">1M tokens</td>
          </tr>
          <tr>
            <td style="padding:10px 14px;border-bottom:1px solid #141F30;color:var(--white);font-weight:600;">DeepSeek V4 Pro</td>
            <td style="padding:10px 14px;border-bottom:1px solid #141F30;color:var(--text);">deepseek-v4-pro</td>
            <td style="padding:10px 14px;border-bottom:1px solid #141F30;color:var(--text);">1M tokens</td>
          </tr>
          <tr>
            <td style="padding:10px 14px;border-bottom:1px solid #141F30;color:var(--white);font-weight:600;">Claude (Anthropic)</td>
            <td style="padding:10px 14px;border-bottom:1px solid #141F30;color:var(--text);">claude-sonnet-4</td>
            <td style="padding:10px 14px;border-bottom:1px solid #141F30;color:var(--text);">200K tokens</td>
          </tr>
          <tr>
            <td style="padding:10px 14px;border-bottom:1px solid #141F30;color:var(--white);font-weight:600;">OpenAI</td>
            <td style="padding:10px 14px;border-bottom:1px solid #141F30;color:var(--text);">gpt-4o-mini</td>
            <td style="padding:10px 14px;border-bottom:1px solid #141F30;color:var(--text);">128K tokens</td>
          </tr>
          <tr>
            <td style="padding:10px 14px;border-bottom:1px solid #141F30;color:var(--white);font-weight:600;">Groq (Llama)</td>
            <td style="padding:10px 14px;border-bottom:1px solid #141F30;color:var(--text);">llama-3.3-70b</td>
            <td style="padding:10px 14px;border-bottom:1px solid #141F30;color:var(--text);">128K tokens</td>
          </tr>
          <tr>
            <td style="padding:10px 14px;border-bottom:1px solid #141F30;color:var(--white);font-weight:600;">Google Gemini</td>
            <td style="padding:10px 14px;border-bottom:1px solid #141F30;color:var(--text);">gemini-2.0-flash</td>
            <td style="padding:10px 14px;border-bottom:1px solid #141F30;color:var(--text);">1M tokens</td>
          </tr>
          <tr>
            <td style="padding:10px 14px;color:var(--white);font-weight:600;">Grok (xAI)</td>
            <td style="padding:10px 14px;color:var(--text);">grok-4-1-fast</td>
            <td style="padding:10px 14px;color:var(--text);">2M tokens</td>
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
        <h3>Cache Inteligente</h3>
        <p>Respostas de reprocessamentos idênticos são reaproveitadas — evita chamadas
        duplicadas e reduz custo.</p>
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
