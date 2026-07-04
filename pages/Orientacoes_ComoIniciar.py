# pages/Orientacoes_ComoIniciar.py
# ─────────────────────────────────────────────────────────────────────────────
# Guia de início rápido — Process2Diagram
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
/* ── Page header ── */
.guide-header {
    background: linear-gradient(135deg, #071428 0%, #0B1E3D 55%, #122848 100%);
    border-bottom: 3px solid #C97B1A;
    border-radius: 12px;
    padding: 1.4rem 2rem;
    margin-bottom: 1.6rem;
    box-shadow: 0 4px 24px rgba(0,0,0,.35);
}
.guide-header .gh-title { font-size: 1.5rem; font-weight: 700; color: #FAFAF8; }
.guide-header .gh-sub   { font-size: .80rem; color: #7A8EA8; margin-top: .3rem; }

/* ── Section header ── */
.g-section-hdr {
    display: flex; align-items: center; gap: .6rem;
    font-size: .72rem; font-weight: 700; color: #6A7E98;
    letter-spacing: .12em; text-transform: uppercase;
    margin: 1.8rem 0 .8rem;
}
.g-section-hdr::after {
    content: ""; flex: 1; height: 1px;
    background: linear-gradient(90deg, #1e3a55 0%, transparent 100%);
}

/* ── Feature pill ── */
.feat-pill {
    display: inline-flex; align-items: center; gap: .35rem;
    background: #0A1A32; border: 1px solid #1A3050;
    border-radius: 20px; padding: .28rem .75rem;
    font-size: .75rem; color: #FAFAF8;
    margin: .2rem .2rem;
}
.feat-pill .fp-icon { font-size: .95rem; }

/* ── Step cards ── */
.step-card {
    background: #0A1A32;
    border: 1px solid #1A3050;
    border-left: 4px solid var(--step-color, #C97B1A);
    border-radius: 10px;
    padding: 1rem 1.2rem;
    margin-bottom: .8rem;
    box-shadow: 0 2px 10px rgba(0,0,0,.2);
}
.step-card .sc-header {
    display: flex; align-items: center; gap: .6rem;
    margin-bottom: .5rem;
}
.step-card .sc-num {
    display: inline-flex; align-items: center; justify-content: center;
    width: 26px; height: 26px; border-radius: 50%;
    background: var(--step-color, #C97B1A);
    color: #fff; font-size: .72rem; font-weight: 800;
    flex-shrink: 0;
}
.step-card .sc-title { font-size: .95rem; font-weight: 700; color: #FAFAF8; }
.step-card .sc-body  { font-size: .82rem; color: #9AAABB; line-height: 1.55; }
.step-card .sc-tip {
    margin-top: .6rem; padding: .4rem .7rem;
    background: rgba(201,123,26,.08);
    border-left: 2px solid #C97B1A;
    border-radius: 4px;
    font-size: .76rem; color: #C9A060;
}

/* ── Page grid ── */
.page-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: .7rem;
    margin-bottom: .5rem;
}
.page-item {
    background: #0A1A32;
    border: 1px solid #1A3050;
    border-radius: 10px;
    padding: .85rem 1rem;
    box-shadow: 0 2px 8px rgba(0,0,0,.18);
}
.page-item .pi-header {
    display: flex; align-items: center; gap: .5rem;
    margin-bottom: .35rem;
}
.page-item .pi-icon   { font-size: 1.15rem; }
.page-item .pi-name   { font-size: .88rem; font-weight: 700; color: #FAFAF8; }
.page-item .pi-group  {
    font-size: .63rem; font-weight: 700; color: #C97B1A;
    letter-spacing: .08em; text-transform: uppercase;
    background: rgba(201,123,26,.12); border-radius: 10px;
    padding: 1px 7px; margin-left: auto;
}
.page-item .pi-desc   { font-size: .74rem; color: #7A8EA8; line-height: 1.45; }

/* ── Info box ── */
.info-box {
    background: #0A1A32; border: 1px solid #1A3050;
    border-radius: 10px; padding: 1rem 1.2rem;
    margin-bottom: .8rem;
}
.info-box .ib-title {
    font-size: .80rem; font-weight: 700; color: #C97B1A;
    letter-spacing: .07em; text-transform: uppercase;
    margin-bottom: .5rem;
}

/* ── Tip list ── */
.tip-row {
    display: flex; gap: .8rem; align-items: flex-start;
    background: #0A1A32; border: 1px solid #1A3050;
    border-radius: 10px; padding: .75rem 1rem;
    margin-bottom: .5rem;
}
.tip-row .tip-num {
    display: inline-flex; align-items: center; justify-content: center;
    width: 22px; height: 22px; min-width: 22px;
    border-radius: 50%; background: #1A3050;
    color: #C97B1A; font-size: .70rem; font-weight: 800; flex-shrink: 0;
}
.tip-row .tip-txt { font-size: .80rem; color: #9AAABB; line-height: 1.5; }

/* ── New badge ── */
.new-badge {
    display: inline-block; padding: 1px 7px; border-radius: 10px;
    font-size: .60rem; font-weight: 700; letter-spacing: .06em;
    background: rgba(16,185,129,.15); color: #10b981;
    border: 1px solid rgba(16,185,129,.3); margin-left: .4rem;
    vertical-align: middle;
}
</style>
""", unsafe_allow_html=True)

# ── Cabeçalho ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="guide-header">
  <div class="gh-title">📖 Como Iniciar</div>
  <div class="gh-sub">Guia de referência rápida — leia antes de usar o Process2Diagram pela primeira vez.</div>
</div>
""", unsafe_allow_html=True)

# ── O que é ───────────────────────────────────────────────────────────────────
st.markdown('<div class="g-section-hdr">O que é o Process2Diagram?</div>', unsafe_allow_html=True)
st.markdown(
    "**Process2Diagram** transforma transcrições de reuniões em artefatos profissionais de análise de processos, "
    "usando um pipeline de múltiplos agentes LLM encadeados. "
    "Cada agente é especializado e opera sobre o mesmo hub de conhecimento compartilhado."
)

_FEATURES = [
    ("📐", "Diagrama BPMN 2.0"),
    ("📊", "Fluxograma Mermaid"),
    ("📋", "Ata de Reunião"),
    ("📝", "Requisitos IEEE 830"),
    ("📖", "Vocabulário SBVR"),
    ("🎯", "Modelo BMM"),
    ("📄", "Relatório Executivo HTML"),
    ("💬", "Assistente RAG"),
    ("✅", "Validação & Rastreamento"),
    ("📅", "Google Calendar"),
    ("📈", "Dashboard ROI-TR"),
    ("📊", "Graficos Interativos"),
]
pills_html = "".join(
    f'<span class="feat-pill"><span class="fp-icon">{ic}</span>{lb}</span>'
    for ic, lb in _FEATURES
)
st.markdown(f'<div style="margin:.4rem 0 .6rem">{pills_html}</div>', unsafe_allow_html=True)

# ── Pré-requisitos ─────────────────────────────────────────────────────────────
st.markdown('<div class="g-section-hdr">Pré-requisitos</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.markdown("""
<div class="info-box">
<div class="ib-title">🔑 API Key LLM (obrigatório)</div>
<p style="font-size:.80rem;color:#9AAABB;margin-bottom:.6rem">
Escolha <strong>um</strong> dos provedores e obtenha sua chave:
</p>

| Provedor | Onde obter | Custo |
|---|---|---|
| **DeepSeek** *(recomendado)* | platform.deepseek.com | Muito baixo |
| **Claude (Anthropic)** | console.anthropic.com | Médio |
| **OpenAI** | platform.openai.com | Médio |
| **Groq (Llama)** | console.groq.com | Gratuito* |
| **Google Gemini** | aistudio.google.com | Gratuito* |

<p style="font-size:.74rem;color:#C9A060;margin-top:.4rem">
💡 Para começar sem custo: use <strong>Groq</strong> ou <strong>Google Gemini</strong> no tier gratuito.
</p>
</div>
""", unsafe_allow_html=True)

with col2:
    st.markdown("""
<div class="info-box">
<div class="ib-title">🗄️ Supabase (opcional, recomendado)</div>
<p style="font-size:.80rem;color:#9AAABB;margin-bottom:.5rem">
O Supabase é necessário para funcionalidades avançadas:
</p>
<ul style="font-size:.80rem;color:#9AAABB;margin:0;padding-left:1.2rem;line-height:1.7">
  <li>💬 <strong>Assistente</strong> — Q&A semântico sobre reuniões passadas</li>
  <li>📋 <strong>Req. Tracker</strong> — acompanhe requisitos ao longo do tempo</li>
  <li>🔄 <strong>Batch Runner</strong> — processe e persista múltiplas transcrições</li>
  <li>📈 <strong>Histórico e ROI-TR</strong> — compare reuniões e detecte contradições</li>
  <li>📅 <strong>Google Calendar</strong> — agende ações diretamente pelo Assistente</li>
</ul>
<p style="font-size:.74rem;color:#6A7E98;margin-top:.5rem">
<strong>Sem Supabase:</strong> o pipeline principal funciona 100% — resultados ficam na sessão.
</p>
</div>
""", unsafe_allow_html=True)

# ── Primeiros passos ──────────────────────────────────────────────────────────
st.markdown('<div class="g-section-hdr">Primeiros passos — Pipeline principal</div>', unsafe_allow_html=True)

_STEPS = [
    ("#C97B1A", "1", "Configure o provedor LLM",
     "Na sidebar esquerda, selecione o provedor (ex: DeepSeek) e insira sua API Key. "
     "A chave fica <strong>apenas na memória da sessão</strong> — nunca é gravada em disco.",
     "Dica: comece com DeepSeek para custo mínimo ou Groq para velocidade máxima."),
    ("#3b82f6", "2", "Cole ou faça upload da transcrição",
     "Na página <strong>Processar Transcrição</strong>, cole o texto diretamente ou faça upload de "
     "um arquivo <code>.txt</code>, <code>.docx</code> ou <code>.pdf</code>. "
     "O botão <em>Pré-processar</em> remove ruídos de ASR sem usar LLM — útil para revisar antes de processar.",
     "Identifique participantes com o padrão <code>Nome: fala</code> — o BPMN usa esses nomes nas lanes."),
    ("#10b981", "3", "(Opcional) Selecione o projeto no Supabase",
     "Se o Supabase estiver configurado, escolha ou crie um projeto e informe o título e data da reunião. "
     "Os artefatos gerados serão salvos automaticamente ao final do pipeline.",
     "Sem projeto selecionado, os resultados ficam disponíveis apenas na sessão atual."),
    ("#8b5cf6", "4", "Escolha os agentes e clique em Gerar Insights",
     "Na sidebar, habilite/desabilite agentes conforme necessário. "
     "BPMN, Ata e Requisitos são os mais usados. "
     "SBVR, BMM e Relatório Executivo são opcionais e aumentam o custo de tokens.",
     "Use 3 ou 5 passes BPMN quando quiser o melhor diagrama possível — o torneio seleciona o candidato com maior pontuação."),
    ("#C97B1A", "5", "Explore os resultados nas abas",
     "Os resultados aparecem nas abas abaixo do pipeline: BPMN 2.0, Mermaid, Ata, Requisitos, etc. "
     "Use <strong>📐 Diagramas</strong> no menu lateral para visualização em tela cheia com pan/zoom e mind map.",
     "A aba <em>Análise Avançada</em> (expander) contém Qualidade, SBVR, BMM, Validação e Dev Tools."),
    ("#3b82f6", "6", "(Supabase) Gere embeddings e use o Assistente",
     "Após salvar reuniões, vá em <strong>Banco de Dados → aba Embeddings</strong> e gere os vetores "
     "com uma chave do Google Gemini (gratuito) ou OpenAI. "
     "Em seguida, use o <strong>Assistente</strong> para perguntas como "
     "<em>'Quais foram as decisões da Reunião 3?'</em> ou <em>'Liste os requisitos de autenticação.'</em>",
     "O Assistente no modo tool-use decide automaticamente quais ferramentas chamar — sem necessidade de embeddings para perguntas estruturadas."),
]

for color, num, title, body, tip in _STEPS:
    st.markdown(
        f'<div class="step-card" style="--step-color:{color}">'
        f'<div class="sc-header">'
        f'  <span class="sc-num">{num}</span>'
        f'  <span class="sc-title">{title}</span>'
        f'</div>'
        f'<div class="sc-body">{body}</div>'
        f'<div class="sc-tip">💡 {tip}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ── Páginas disponíveis ────────────────────────────────────────────────────────
st.markdown('<div class="g-section-hdr">Páginas disponíveis</div>', unsafe_allow_html=True)

_PAGES = [
    # Pipeline
    ("🚀", "Processar Transcrição", "Pipeline",
     "Pipeline principal. Cole ou faça upload de uma transcrição e gere todos os artefatos."),
    ("📐", "Diagramas", "Pipeline",
     "Visualizador full-screen: BPMN 2.0 (bpmn-js), Mermaid (pan/zoom) e Mind Map de requisitos."),
    ("✏️", "Editor BPMN", "Pipeline",
     "Editor visual bpmn-js com histórico de versões e salvamento no Supabase."),
    # Análise
    ("💬", "Assistente", "Análise",
     "Chat Q&A sobre todas as reuniões do projeto. Tool-use ou RAG clássico com busca semântica (pgvector). Requer Supabase."),
    ("✅", "Validação", "Análise",
     "Hub de validação de requisitos e artefatos gerados pelo pipeline."),
    ("📋", "Req. Tracker", "Análise",
     "Quadro de acompanhamento de requisitos: status, contradições, exportação Excel/CSV. Requer Supabase."),
    ("📊", "ROI-TR", "Análise",
     "Dashboard de qualidade e retorno sobre investimento por tipo de reunião (11 tipos, pesos por artefato)."),
    ("🏷️", "Entity Recognition", "Análise",
     "Reconhecimento de entidades nomeadas na transcrição via spaCy (NER)."),
    # Sistema
    ("⚙️", "Configurações", "Sistema",
     "Central de configurações: provedores LLM, embeddings, banco de dados, Google Calendar por projeto."),
    ("💰", "Estimativa de Custo", "Sistema",
     "Calcule o custo estimado de tokens antes de processar, por provedor e agente."),
    ("🗄️", "Banco de Dados", "Sistema (admin)",
     "Health score, KPIs de integridade, gestão de embeddings e correções inline. Requer perfil admin."),
    ("🛡️", "Master Admin", "Sistema (admin)",
     "Gestão de usuários, roles, contas de integração (Google, MS Teams). Requer perfil master."),
    # Manutenção
    ("🔄", "Batch Runner", "Manutenção",
     "Processa múltiplas transcrições em sequência e persiste no Supabase."),
    ("🔧", "BPMN Backfill", "Manutenção",
     "Gera BPMN para reuniões já salvas no Supabase que ainda não têm diagrama."),
    ("📝", "Transcript Backfill", "Manutenção",
     "Salva transcrições para reuniões já no banco que têm ata mas não têm texto."),
    ("📋", "Minutes Backfill", "Manutenção",
     "Regenera atas de reuniões já armazenadas no Supabase."),
]

# render grid
items_html = ""
for icon, name, group, desc in _PAGES:
    items_html += (
        f'<div class="page-item">'
        f'<div class="pi-header">'
        f'  <span class="pi-icon">{icon}</span>'
        f'  <span class="pi-name">{name}</span>'
        f'  <span class="pi-group">{group}</span>'
        f'</div>'
        f'<div class="pi-desc">{desc}</div>'
        f'</div>'
    )
st.markdown(f'<div class="page-grid">{items_html}</div>', unsafe_allow_html=True)

# ── Configurações da sidebar ──────────────────────────────────────────────────
st.markdown('<div class="g-section-hdr">Configurações da sidebar (Pipeline)</div>', unsafe_allow_html=True)

col_a, col_b = st.columns(2)

with col_a:
    st.markdown("""
<div class="info-box">
<div class="ib-title">Agentes disponíveis</div>
<ul style="font-size:.80rem;color:#9AAABB;margin:0;padding-left:1.2rem;line-height:1.8">
  <li>🔬 <strong>Qualidade da Transcrição</strong> — grade A–E</li>
  <li>📐 <strong>BPMN</strong> — diagrama de processo <em>(core)</em></li>
  <li>📋 <strong>Ata de Reunião</strong> — minutes completa</li>
  <li>📝 <strong>Requisitos</strong> — extração IEEE 830</li>
  <li>📖 <strong>SBVR</strong> — vocabulário e regras de negócio</li>
  <li>🎯 <strong>BMM</strong> — modelo de motivação</li>
  <li>📄 <strong>Relatório Executivo</strong> — síntese HTML</li>
</ul>
<div class="ib-title" style="margin-top:.8rem">Otimização BPMN</div>
<ul style="font-size:.80rem;color:#9AAABB;margin:0;padding-left:1.2rem;line-height:1.8">
  <li><strong>1 pass</strong> — execução única (padrão)</li>
  <li><strong>3 ou 5 passes</strong> — torneio: melhor candidato por pontuação</li>
  <li><strong>Adaptive Retry (LangGraph)</strong> — retenta até nota mínima</li>
</ul>
</div>
""", unsafe_allow_html=True)

with col_b:
    st.markdown("""
<div class="info-box">
<div class="ib-title">Idioma de saída</div>
<p style="font-size:.80rem;color:#9AAABB;margin-bottom:.5rem">
Auto-detect detecta o idioma da transcrição. Também disponível: Português, Inglês, Espanhol, etc.
</p>
<div class="ib-title">Prefixo / Sufixo</div>
<p style="font-size:.80rem;color:#9AAABB;margin-bottom:.5rem">
Adicionados aos nomes dos arquivos exportados.<br>
Ex: <code>ACME_</code> + <code>v1</code> → <code>ACME_processo_2026-05-11_v1.bpmn</code>
</p>
<div class="ib-title">Modo Desenvolvedor</div>
<p style="font-size:.80rem;color:#9AAABB;margin-bottom:0">
Exibe aba <em>Dev Tools</em> com o KnowledgeHub JSON completo — útil para depurar o que cada agente produziu.
</p>
</div>
""", unsafe_allow_html=True)

# ── Novidades (v4.16) ─────────────────────────────────────────────────────────
st.markdown(
    '<div class="g-section-hdr">Novidades recentes'
    '<span class="new-badge">v4.17</span>'
    '</div>',
    unsafe_allow_html=True,
)

_NEWS = [
    ("📊", "Graficos interativos no Assistente",
     "Peca graficos diretamente no chat do Assistente: barras de requisitos por tipo ou prioridade, "
     "linha do tempo de artefatos por reuniao, pizza de status de acoes, ROI-TR por reuniao e graficos "
     "customizados com dados informados na conversa. Selecione a paleta de cores na sidebar "
     "(<em>Graficos → Paleta de cores</em>) e repita o pedido para aplicar as novas cores."),
    ("📅", "Google Calendar integrado",
     "O Assistente pode listar eventos, sugerir horários e agendar itens de ação diretamente nas agendas do projeto. "
     "Cada projeto pode ter um calendário Google dedicado, configurável em Configurações → Banco de Dados."),
    ("🔒", "Segurança RLS no Supabase",
     "Row Level Security habilitado em todas as tabelas — os dados de cada projeto ficam isolados por política de acesso."),
    ("✏️", "Editor BPMN com histórico de versões",
     "O Editor BPMN agora salva cada edição como nova versão no Supabase, com navegação entre versões e notas de revisão."),
    ("🏠", "Central de Operações renovada",
     "A página inicial ganhou KPIs coloridos, cards de fluxo com cores por etapa, e acesso rápido reorganizado por área."),
    ("📐", "SysML v2 — análise e proposta de integração",
     "Documentação inicial sobre a integração futura com SysML v2 disponível em <code>SysMLv2/</code> no repositório "
     "(ideiaManus.md e referencia.md)."),
]

for icon, title, desc in _NEWS:
    st.markdown(
        f'<div class="step-card" style="--step-color:#10b981">'
        f'<div class="sc-header">'
        f'  <span class="sc-num" style="background:#10b981;font-size:.85rem">{icon}</span>'
        f'  <span class="sc-title">{title}</span>'
        f'</div>'
        f'<div class="sc-body">{desc}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

# ── Dicas de qualidade ────────────────────────────────────────────────────────
st.markdown('<div class="g-section-hdr">Dicas para melhores resultados</div>', unsafe_allow_html=True)

_TIPS = [
    "**Transcrições mais longas e detalhadas** geram diagramas BPMN mais ricos. "
    "Procure incluir pelo menos os momentos de decisão e transições entre responsáveis.",

    "**Identifique os participantes** com o padrão <code>Nome: fala</code> ou <code>NOME: fala</code>. "
    "O agente de ata extrai participantes e o BPMN usa os nomes para definir as lanes.",

    "**Pré-processe antes de processar** se a transcrição tiver ruídos de ASR "
    "(repetições, hesitações, palavras cortadas). O botão <em>Pré-processar</em> remove esses artefatos sem LLM.",

    "**Use múltiplas passes BPMN** (3 ou 5) quando o diagrama gerado parecer incompleto "
    "ou com pouca granularidade — o torneio seleciona o melhor candidato.",

    "**O Assistente no modo tool-use** responde melhor a perguntas estruturadas "
    "(<em>'Quais são os participantes?'</em>, <em>'Liste as decisões'</em>) do que perguntas abertas. "
    "Para buscas em texto de transcrição, ambos os modos funcionam bem.",

    "**Gere embeddings imediatamente** após salvar uma reunião enquanto a chave do "
    "Google Gemini está disponível — o processo demora alguns minutos por conta do rate limit "
    "do tier gratuito (1,2s entre chamadas, 100 req/min).",

    "**Configure o Google Calendar** em Configurações → Banco de Dados para que o Assistente "
    "possa agendar itens de ação e sugerir horários de reunião diretamente da conversa.",

    "**Gere graficos no Assistente** pedindo diretamente no chat: <em>'Gere um grafico de requisitos por tipo'</em>, "
    "<em>'Mostre o ROI-TR das reunioes'</em> ou <em>'Crie um grafico de pizza com: Aprovado 45, Pendente 30'</em>. "
    "Se algum texto ficar ilegivel por contraste de cores, troque a paleta na sidebar "
    "(<em>Graficos → Paleta de cores</em>) e repita o pedido.",
]

tips_html = ""
for i, tip in enumerate(_TIPS, 1):
    tips_html += (
        f'<div class="tip-row">'
        f'<span class="tip-num">{i}</span>'
        f'<span class="tip-txt">{tip}</span>'
        f'</div>'
    )
st.markdown(tips_html, unsafe_allow_html=True)

# ── Rodapé ─────────────────────────────────────────────────────────────────────
st.markdown(
    "<div style='margin-top:2rem;padding-top:.8rem;border-top:1px solid #1A3050;"
    "text-align:center;font-size:.68rem;color:#3A5070;letter-spacing:.04em'>"
    "Process2Diagram v5.15 &nbsp;·&nbsp; Guia de Inicio Rapido"
    "</div>",
    unsafe_allow_html=True,
)
