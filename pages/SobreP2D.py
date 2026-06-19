# pages/SobreP2D.py
# ─────────────────────────────────────────────────────────────────────────────
# Sobre o Process2Diagram — visao geral, arquitetura, tecnologias e credito
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from ui.auth_gate import apply_auth_gate

apply_auth_gate()

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Hero ── */
.sobre-hero {
    background: linear-gradient(135deg, #050E1F 0%, #071428 50%, #0B1E3D 100%);
    border-bottom: 3px solid #C97B1A;
    border-radius: 14px;
    padding: 2rem 2.4rem 1.6rem;
    margin-bottom: 1.8rem;
    box-shadow: 0 6px 32px rgba(0,0,0,.45);
    position: relative;
    overflow: hidden;
}
.sobre-hero::before {
    content: "";
    position: absolute; top: -40px; right: -40px;
    width: 220px; height: 220px; border-radius: 50%;
    background: radial-gradient(circle, rgba(201,123,26,.10) 0%, transparent 70%);
}
.sobre-hero .hero-badge {
    display: inline-block;
    background: rgba(201,123,26,.15); border: 1px solid rgba(201,123,26,.35);
    border-radius: 20px; padding: .22rem .8rem;
    font-size: .68rem; font-weight: 700; color: #C97B1A;
    letter-spacing: .10em; text-transform: uppercase;
    margin-bottom: .7rem;
}
.sobre-hero .hero-title {
    font-size: 2rem; font-weight: 800; color: #FAFAF8;
    line-height: 1.15; margin-bottom: .5rem;
}
.sobre-hero .hero-title span { color: #C97B1A; }
.sobre-hero .hero-sub {
    font-size: .92rem; color: #7A8EA8; line-height: 1.6;
    max-width: 680px;
}
.sobre-hero .hero-version {
    display: inline-block; margin-top: .9rem;
    background: rgba(59,130,246,.12); border: 1px solid rgba(59,130,246,.25);
    border-radius: 20px; padding: .22rem .8rem;
    font-size: .70rem; font-weight: 700; color: #60a5fa;
    letter-spacing: .06em;
}

/* ── Section header ── */
.s-hdr {
    display: flex; align-items: center; gap: .6rem;
    font-size: .72rem; font-weight: 700; color: #6A7E98;
    letter-spacing: .12em; text-transform: uppercase;
    margin: 2rem 0 .9rem;
}
.s-hdr::after {
    content: ""; flex: 1; height: 1px;
    background: linear-gradient(90deg, #1e3a55 0%, transparent 100%);
}

/* ── Capability cards ── */
.cap-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: .7rem; margin-bottom: .5rem;
}
.cap-card {
    background: #080F1F;
    border: 1px solid #1A3050;
    border-radius: 12px;
    padding: 1rem 1.1rem;
    box-shadow: 0 2px 12px rgba(0,0,0,.22);
    transition: border-color .2s;
}
.cap-card:hover { border-color: #2a4a70; }
.cap-card .cc-icon { font-size: 1.5rem; margin-bottom: .5rem; }
.cap-card .cc-title { font-size: .88rem; font-weight: 700; color: #FAFAF8; margin-bottom: .3rem; }
.cap-card .cc-desc  { font-size: .75rem; color: #7A8EA8; line-height: 1.5; }

/* ── Pipeline steps ── */
.pipe-row {
    display: flex; align-items: flex-start; gap: 1rem;
    background: #080F1F; border: 1px solid #1A3050;
    border-radius: 10px; padding: .85rem 1rem;
    margin-bottom: .5rem;
}
.pipe-row .pr-num {
    display: inline-flex; align-items: center; justify-content: center;
    width: 28px; height: 28px; min-width: 28px;
    border-radius: 50%; background: #C97B1A;
    color: #fff; font-size: .72rem; font-weight: 800; flex-shrink: 0;
}
.pipe-row .pr-body { flex: 1; }
.pipe-row .pr-title { font-size: .88rem; font-weight: 700; color: #FAFAF8; margin-bottom: .2rem; }
.pipe-row .pr-desc  { font-size: .78rem; color: #7A8EA8; line-height: 1.5; }
.pipe-row .pr-tag {
    display: inline-block; padding: 1px 8px; border-radius: 10px;
    font-size: .60rem; font-weight: 700; letter-spacing: .05em;
    background: rgba(201,123,26,.12); color: #C97B1A;
    border: 1px solid rgba(201,123,26,.25); margin-right: .3rem;
}
.pipe-row .pr-tag.blue {
    background: rgba(59,130,246,.12); color: #60a5fa;
    border-color: rgba(59,130,246,.25);
}
.pipe-row .pr-tag.green {
    background: rgba(16,185,129,.10); color: #34d399;
    border-color: rgba(16,185,129,.25);
}

/* ── Tech pills ── */
.tech-grid {
    display: flex; flex-wrap: wrap; gap: .45rem; margin-bottom: .5rem;
}
.tech-pill {
    display: inline-flex; align-items: center; gap: .3rem;
    background: #080F1F; border: 1px solid #1A3050;
    border-radius: 20px; padding: .28rem .8rem;
    font-size: .74rem; color: #FAFAF8;
}
.tech-pill .tp-dot {
    width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0;
}

/* ── Info box ── */
.info-box {
    background: #080F1F; border: 1px solid #1A3050;
    border-radius: 12px; padding: 1rem 1.2rem; margin-bottom: .8rem;
}
.info-box .ib-title {
    font-size: .75rem; font-weight: 700; color: #C97B1A;
    letter-spacing: .08em; text-transform: uppercase; margin-bottom: .55rem;
}

/* ── Credit card ── */
.credit-card {
    background: linear-gradient(135deg, #080F1F 0%, #0B1528 100%);
    border: 1px solid #1A3050;
    border-radius: 14px;
    padding: 1.5rem 1.8rem;
    margin-top: 1.2rem;
    display: flex; align-items: center; gap: 1.4rem;
    box-shadow: 0 4px 20px rgba(0,0,0,.3);
}
.credit-avatar {
    width: 80px; height: 80px; min-width: 80px; border-radius: 50%;
    background: linear-gradient(135deg, #0B1E3D 0%, #142d52 100%);
    border: 2px solid #C97B1A;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.5rem; font-weight: 800; color: #C97B1A;
    letter-spacing: .02em; flex-shrink: 0;
}
.credit-info .ci-name {
    font-size: 1rem; font-weight: 700; color: #FAFAF8; margin-bottom: .25rem;
}
.credit-info .ci-role {
    font-size: .80rem; color: #C97B1A; margin-bottom: .35rem;
}
.credit-info .ci-bio {
    font-size: .77rem; color: #7A8EA8; line-height: 1.55; margin-bottom: .45rem;
}
.credit-info .ci-contact {
    font-size: .70rem; color: #4A6080; letter-spacing: .03em;
}
</style>
""", unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="sobre-hero">
  <div class="hero-badge">Sobre o Produto</div>
  <div class="hero-title">Process2Diagram<br><span>Da fala ao diagrama.</span></div>
  <div class="hero-sub">
    Plataforma de inteligencia artificial que converte transcricoes de reunioes em artefatos
    profissionais de analise de processos — diagramas BPMN, atas, requisitos, vocabulario de
    negocios e relatorios executivos — usando um pipeline de multiplos agentes LLM encadeados.
  </div>
  <span class="hero-version">v4.32 &nbsp;·&nbsp; Streamlit Cloud &nbsp;·&nbsp; Python 3.13</span>
</div>
""", unsafe_allow_html=True)

# ── O problema que resolve ─────────────────────────────────────────────────────
st.markdown('<div class="s-hdr">O problema que resolve</div>', unsafe_allow_html=True)

col_prob, col_sol = st.columns(2)

with col_prob:
    st.markdown("""
<div class="info-box">
<div class="ib-title">Antes do P2D</div>
<ul style="font-size:.80rem;color:#9AAABB;margin:0;padding-left:1.2rem;line-height:1.9">
  <li>Analistas transcrevem reunioes manualmente</li>
  <li>Diagramas BPMN criados do zero em ferramentas separadas</li>
  <li>Requisitos identificados informalmente, sem rastreamento</li>
  <li>Atas nao padronizadas e sujeitas a erros de interpretacao</li>
  <li>Decisoes e acoes dispersas em e-mails e arquivos</li>
  <li>Semanas de trabalho para documentar um projeto</li>
</ul>
</div>
""", unsafe_allow_html=True)

with col_sol:
    st.markdown("""
<div class="info-box">
<div class="ib-title">Com o P2D</div>
<ul style="font-size:.80rem;color:#9AAABB;margin:0;padding-left:1.2rem;line-height:1.9">
  <li>Cole a transcricao &rarr; clique em Gerar &rarr; artefatos prontos</li>
  <li>Diagrama BPMN 2.0 gerado automaticamente, pronto para editar</li>
  <li>Requisitos estruturados IEEE&nbsp;830 com rastreabilidade</li>
  <li>Ata padronizada com participantes, decisoes e acoes</li>
  <li>Vocabulario SBVR e modelo BMM integrados</li>
  <li>Pipeline completo em minutos, nao em semanas</li>
</ul>
</div>
""", unsafe_allow_html=True)

# ── Capacidades ───────────────────────────────────────────────────────────────
st.markdown('<div class="s-hdr">Capacidades principais</div>', unsafe_allow_html=True)

_CAPS = [
    ("📐", "BPMN 2.0",
     "Diagrama de processo com lanes, gateways, eventos e fluxos de sequencia. "
     "Visualizador bpmn-js embutido com pan, zoom e setas de navegacao."),
    ("📊", "Fluxograma Mermaid",
     "Representacao alternativa do mesmo processo em sintaxe Mermaid, "
     "com renderizacao SVG e opcoes horizontal/vertical."),
    ("📋", "Ata de Reuniao",
     "Minuta estruturada com participantes, pauta, decisoes, encaminhamentos "
     "e proximos passos. Exportavel em Markdown, Word e PDF."),
    ("📝", "Requisitos IEEE 830",
     "Extração estruturada de requisitos funcionais e nao funcionais com "
     "codigo, tipo, prioridade, descricao e rastreabilidade por reuniao."),
    ("📖", "Vocabulario SBVR",
     "Termos de negocio, definicoes e regras de negocio no padrao OMG SBVR, "
     "com exportacao JSON e visualizacao por categoria."),
    ("🎯", "Modelo BMM",
     "Visao, missao, objetivos, estrategias e politicas no padrao OMG Business "
     "Motivation Model — alinha processos a estrategia corporativa."),
    ("⚖️", "Tabelas de Decisao DMN",
     "Regras de negocio extraidas no padrao OMG DMN 1.4 com renderizacao "
     "dark-theme, hit-policy badge e DRD topologico."),
    ("💬", "Assistente RAG",
     "Chat conversacional com historico e ate 90 ferramentas de consulta ao "
     "banco de dados — tool-use ou RAG classico com pgvector."),
    ("📄", "Relatorio Executivo",
     "Sintese HTML auto-contido com graficos, metricas e destaques — "
     "pronto para enviar a stakeholders sem nenhuma instalacao."),
    ("📈", "Dashboard ROI-TR",
     "Qualidade e retorno sobre investimento por tipo de reuniao (11 tipos), "
     "com pesos por dimensao de artefato e historico comparativo."),
    ("🕸️", "Grafo de Conhecimento",
     "Visualizacao interativa de entidades, contradicoes e fatos extraidos "
     "de multiplas reunioes — estilo Obsidian com fisicas pyvis."),
    ("📅", "Google Calendar",
     "Agendamento de itens de acao e sugestao de horarios diretamente "
     "pelo Assistente, integrado ao calendario do projeto."),
]

caps_html = ""
for icon, title, desc in _CAPS:
    caps_html += (
        f'<div class="cap-card">'
        f'<div class="cc-icon">{icon}</div>'
        f'<div class="cc-title">{title}</div>'
        f'<div class="cc-desc">{desc}</div>'
        f'</div>'
    )
st.markdown(f'<div class="cap-grid">{caps_html}</div>', unsafe_allow_html=True)

# ── Pipeline ──────────────────────────────────────────────────────────────────
st.markdown('<div class="s-hdr">Como funciona — Pipeline de agentes</div>', unsafe_allow_html=True)

_PIPE = [
    ("Qualidade da Transcricao", "Avalia a transcricao com grade A-E e identifica lacunas antes de processar.", "LLM", None, None),
    ("Pre-processamento", "Remove ruidos de ASR (repeticoes, hesitacoes, artefatos) sem usar LLM.", "Sem LLM", None, None),
    ("NLP Chunker", "Segmentacao, deteccao de atores e NER via spaCy — identifica participantes e papeis.", "spaCy", None, None),
    ("Agente BPMN", "Extrai steps, edges e lanes da transcricao e gera XML BPMN 2.0 + Mermaid. "
     "Suporta torneio multi-pass (1/3/5 candidatos) e retry adaptativo via LangGraph.", "LLM", "Core", None),
    ("Agente de Ata + Requisitos", "Execucao paralela via ThreadPoolExecutor. Extrai minuta estruturada "
     "e requisitos IEEE 830 simultaneamente.", "LLM", "Paralelo", "green"),
    ("Agentes de Enriquecimento", "SBVR, BMM, DMN, Sintetizador e Ruidos de Comunicacao — todos opcionais, "
     "executados em sequencia apos o nucleo.", "LLM", "Opcional", "blue"),
    ("KnowledgeHub", "Todos os artefatos convergemm para o hub central (dataclass). "
     "Persistido no Supabase e disponivel para o Assistente.", None, "Estado", "blue"),
]

for i, (title, desc, tag, tag2, tag_color) in enumerate(_PIPE, 1):
    tags_html = ""
    if tag:
        tags_html += f'<span class="pr-tag">{tag}</span>'
    if tag2:
        color_cls = f" {tag_color}" if tag_color else ""
        tags_html += f'<span class="pr-tag{color_cls}">{tag2}</span>'
    st.markdown(
        f'<div class="pipe-row">'
        f'<span class="pr-num">{i}</span>'
        f'<div class="pr-body">'
        f'<div class="pr-title">{title} &nbsp;{tags_html}</div>'
        f'<div class="pr-desc">{desc}</div>'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ── Tecnologias ────────────────────────────────────────────────────────────────
st.markdown('<div class="s-hdr">Tecnologias</div>', unsafe_allow_html=True)

_TECHS = [
    ("#C97B1A", "Python 3.13"),
    ("#3b82f6", "Streamlit 1.45"),
    ("#10b981", "LangGraph"),
    ("#8b5cf6", "bpmn-js 17"),
    ("#C97B1A", "Supabase + pgvector"),
    ("#3b82f6", "DeepSeek V4"),
    ("#10b981", "Claude Sonnet 4"),
    ("#8b5cf6", "OpenAI GPT-4o"),
    ("#C97B1A", "Google Gemini 2.0"),
    ("#3b82f6", "Groq Llama 3.3"),
    ("#10b981", "Grok xAI"),
    ("#8b5cf6", "spaCy NER"),
    ("#C97B1A", "Mermaid.ink"),
    ("#3b82f6", "Plotly"),
    ("#10b981", "python-docx"),
    ("#8b5cf6", "fpdf2"),
    ("#C97B1A", "pyvis"),
    ("#3b82f6", "Google Calendar API"),
]

pills_html = ""
for color, label in _TECHS:
    pills_html += (
        f'<span class="tech-pill">'
        f'<span class="tp-dot" style="background:{color}"></span>'
        f'{label}'
        f'</span>'
    )
st.markdown(f'<div class="tech-grid">{pills_html}</div>', unsafe_allow_html=True)

# ── Provedores LLM ──────────────────────────────────────────────────────────
st.markdown('<div class="s-hdr">Provedores LLM suportados</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
<div class="info-box">
<div class="ib-title">Producao e Baixo Custo</div>
<ul style="font-size:.80rem;color:#9AAABB;margin:0;padding-left:1.2rem;line-height:1.9">
  <li><strong style="color:#FAFAF8">DeepSeek V4 Flash</strong> — padrao; contexto 1M; custo minimo</li>
  <li><strong style="color:#FAFAF8">DeepSeek V4 Pro</strong> — premium; mais preciso para BPMN complexo</li>
  <li><strong style="color:#FAFAF8">DeepSeek V4 Flash (Thinking)</strong> — modo raciocinio chain-of-thought</li>
  <li><strong style="color:#FAFAF8">Groq (Llama 3.3 70B)</strong> — mais rapido; tier gratuito disponivel</li>
  <li><strong style="color:#FAFAF8">Google Gemini 2.0</strong> — gratuito no tier free; contexto longo</li>
</ul>
</div>
""", unsafe_allow_html=True)

with col2:
    st.markdown("""
<div class="info-box">
<div class="ib-title">Alta Qualidade</div>
<ul style="font-size:.80rem;color:#9AAABB;margin:0;padding-left:1.2rem;line-height:1.9">
  <li><strong style="color:#FAFAF8">Claude Sonnet 4 (Anthropic)</strong> — excelente para SBVR e BMM</li>
  <li><strong style="color:#FAFAF8">OpenAI GPT-4o / GPT-4o-mini</strong> — balanco qualidade/custo</li>
  <li><strong style="color:#FAFAF8">Grok 4 (xAI)</strong> — contexto 2M; raciocinio avancado</li>
</ul>
<div style="margin-top:.7rem;padding:.6rem .8rem;background:rgba(201,123,26,.07);
            border-left:2px solid #C97B1A;border-radius:4px;
            font-size:.74rem;color:#C9A060;line-height:1.5">
  Cada agente pode usar um provedor diferente via
  <strong>Cenarios de Custo-Beneficio</strong>.
</div>
</div>
""", unsafe_allow_html=True)

# ── Deploy ───────────────────────────────────────────────────────────────────
st.markdown('<div class="s-hdr">Implantacao</div>', unsafe_allow_html=True)

st.markdown("""
<div class="info-box">
<div class="ib-title">Opcoes de Deploy</div>
<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:.7rem;margin-top:.3rem">
  <div style="padding:.7rem .9rem;background:#0A1528;border:1px solid #1A3050;border-radius:8px">
    <div style="font-size:.80rem;font-weight:700;color:#FAFAF8;margin-bottom:.3rem">Streamlit Cloud</div>
    <div style="font-size:.74rem;color:#7A8EA8">Deploy automatico via push para GitHub. Sem infraestrutura para gerenciar.</div>
  </div>
  <div style="padding:.7rem .9rem;background:#0A1528;border:1px solid #1A3050;border-radius:8px">
    <div style="font-size:.80rem;font-weight:700;color:#FAFAF8;margin-bottom:.3rem">Docker / VPS</div>
    <div style="font-size:.74rem;color:#7A8EA8">Containerizacao simples com <code>streamlit run app.py</code>. Sem build step.</div>
  </div>
  <div style="padding:.7rem .9rem;background:#0A1528;border:1px solid #1A3050;border-radius:8px">
    <div style="font-size:.80rem;font-weight:700;color:#FAFAF8;margin-bottom:.3rem">On-Premises</div>
    <div style="font-size:.74rem;color:#7A8EA8">Dados 100% na infraestrutura do cliente. Supabase self-hosted disponivel.</div>
  </div>
  <div style="padding:.7rem .9rem;background:#0A1528;border:1px solid #1A3050;border-radius:8px">
    <div style="font-size:.80rem;font-weight:700;color:#FAFAF8;margin-bottom:.3rem">Implantacao em 1 dia</div>
    <div style="font-size:.74rem;color:#7A8EA8">Sem instalacao de cliente. Suporte a qualquer provedor LLM ja contratado.</div>
  </div>
</div>
</div>
""", unsafe_allow_html=True)

# ── Credito ───────────────────────────────────────────────────────────────────
st.markdown('<div class="s-hdr">Criador</div>', unsafe_allow_html=True)

st.markdown("""
<div class="credit-card">
  <div class="credit-avatar">PGR</div>
  <div class="credit-info">
    <div class="ci-name">Pedro Gentil Regato de Oliveira Soares</div>
    <div class="ci-role">Estatistico e BPM Senior</div>
    <div class="ci-bio">
      Da automacao de processos a IA em producao &mdash;
      solucoes que integram modelo, fluxo e sistema.
    </div>
    <div class="ci-contact">pedro.regato@gmail.com &nbsp;&middot;&nbsp; P2D v4.32</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Rodape ───────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='margin-top:2.5rem;padding-top:.8rem;border-top:1px solid #1A3050;"
    "text-align:center;font-size:.68rem;color:#3A5070;letter-spacing:.04em'>"
    "Process2Diagram v4.32 &nbsp;&middot;&nbsp; Sobre o Produto"
    "</div>",
    unsafe_allow_html=True,
)
