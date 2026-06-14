# pages/Orientacoes_Assistente.py
# ─────────────────────────────────────────────────────────────────────────────
# Guia de ferramentas do Assistente — documentação completa com exemplos de uso
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
    margin: 1.6rem 0 .8rem;
}
.g-section-hdr::after {
    content: ""; flex: 1; height: 1px;
    background: linear-gradient(90deg, #1e3a55 0%, transparent 100%);
}

/* ── Tool card ── */
.tool-card {
    background: #080F1E;
    border: 1px solid #1A2E48;
    border-left: 4px solid var(--tc-color, #2563EB);
    border-radius: 10px;
    padding: 1rem 1.2rem 0.8rem;
    margin-bottom: .9rem;
}
.tc-header {
    display: flex; align-items: center; gap: .6rem;
    margin-bottom: .45rem; flex-wrap: wrap;
}
.tc-name {
    font-family: 'Courier New', monospace;
    font-size: .88rem; font-weight: 700;
    color: #D4E1F5; letter-spacing: .01em;
}
.tc-badge {
    display: inline-block;
    font-size: .62rem; font-weight: 800;
    letter-spacing: .09em; text-transform: uppercase;
    padding: .18rem .55rem; border-radius: 4px;
}
.tc-badge--consulta  { background: #0E2A4A; color: #60A5FA; border: 1px solid #1D4A80; }
.tc-badge--escrita   { background: #2A1A02; color: #FBBF24; border: 1px solid #6B4A08; }
.tc-badge--grafico   { background: #0A2210; color: #4ADE80; border: 1px solid #1A4A28; }
.tc-badge--calendario{ background: #1A0A2E; color: #A78BFA; border: 1px solid #3D1A6A; }
.tc-badge--admin     { background: #2A0A0A; color: #F87171; border: 1px solid #6A1A1A; }
.tc-desc {
    font-size: .80rem; color: #8A9EBA;
    line-height: 1.55; margin-bottom: .6rem;
}
.tc-examples-label {
    font-size: .62rem; font-weight: 700; color: #4A6A8A;
    letter-spacing: .09em; text-transform: uppercase;
    margin-bottom: .35rem;
}
.prompt-pill {
    display: inline-block;
    background: #0A1A32;
    border: 1px solid #C97B1A44;
    border-radius: 6px;
    padding: .28rem .7rem;
    font-size: .76rem; color: #D4A850;
    margin: .2rem .2rem .2rem 0;
    font-style: italic;
}

/* ── Mode cards ── */
.mode-card {
    background: #0A1628;
    border: 1px solid #1A3050;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    height: 100%;
}
.mode-card .mc-title { font-size: .95rem; font-weight: 700; color: #FAFAF8; margin-bottom: .4rem; }
.mode-card .mc-body  { font-size: .80rem; color: #8A9EBA; line-height: 1.55; }

/* ── Tip box ── */
.tip-box {
    background: #0A1628;
    border: 1px solid #1A3050;
    border-left: 3px solid #C97B1A;
    border-radius: 8px;
    padding: .75rem 1rem;
    font-size: .78rem; color: #9AAABB;
    margin: .8rem 0;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="guide-header">
  <div class="gh-title">💬 Guia do Assistente — Ferramentas Disponíveis</div>
  <div class="gh-sub">
    Referência completa das ferramentas do Assistente com exemplos de prompts.
    As ferramentas marcadas como <strong style="color:#F87171">admin</strong>
    exigem perfil administrador.
  </div>
</div>
""", unsafe_allow_html=True)


# ── Modos de operação ─────────────────────────────────────────────────────────
st.markdown('<div class="g-section-hdr">Modos de operação</div>', unsafe_allow_html=True)

col_a, col_b = st.columns(2)
with col_a:
    st.markdown("""
    <div class="mode-card">
      <div class="mc-title">💬 Assistente (padrão)</div>
      <div class="mc-body">
        Modo conversacional com histórico. O LLM decide quais ferramentas chamar
        para responder à pergunta — até 8 rodadas de tool-use por mensagem.
        Ideal para consultas, relatórios e perguntas sobre reuniões específicas.
        <br><br>
        <strong style="color:#FAFAF8">Submodo A — Tool-use</strong> (padrão):
        LLM acessa o Supabase diretamente via ferramentas.<br>
        <strong style="color:#FAFAF8">Submodo B — RAG Clássico</strong>:
        busca por palavras-chave + vetores semânticos (fallback).
      </div>
    </div>
    """, unsafe_allow_html=True)

with col_b:
    st.markdown("""
    <div class="mode-card">
      <div class="mc-title">🔬 Análise Autônoma</div>
      <div class="mc-body">
        Agente autônomo com até 15 rodadas de raciocínio (ReAct loop).
        Produz um relatório estruturado com conclusão, tabelas e cadeia de
        pensamento auditável. Exportável em Markdown, PDF e HTML.<br><br>
        Ideal para análises profundas: "Identifique todos os gargalos do
        processo", "Analise a cobertura de requisitos das últimas 5 reuniões".
      </div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("""
<div class="tip-box">
  <strong>Como o Assistente decide qual ferramenta usar?</strong><br>
  Você não precisa mencionar o nome da ferramenta. Basta perguntar em linguagem
  natural — o LLM identifica a intenção e escolhe a ferramenta adequada.
  Os exemplos abaixo mostram prompts que ativam cada ferramenta.
</div>
""", unsafe_allow_html=True)

st.markdown('<div class="g-section-hdr">Exportação da conversa</div>', unsafe_allow_html=True)

st.markdown("""
<div class="tip-box">
  <strong>⬇️ Markdown</strong> &nbsp;·&nbsp; <strong>⬇️ HTML</strong> &nbsp;—
  botões disponíveis na barra acima do chat quando há mensagens.<br><br>
  <strong>Markdown</strong>: texto simples com todas as perguntas e respostas —
  útil para arquivamento, edição ou compartilhamento por e-mail.<br><br>
  <strong>HTML</strong>: arquivo auto-contido com estilo visual completo e
  <strong>gráficos Plotly interativos</strong> (zoom, pan, hover, download PNG)
  incorporados diretamente no arquivo.
  Abre em qualquer navegador sem dependência de servidor.
  Ideal para apresentações, auditorias e registros formais.<br><br>
  <em>Requer conexão para renderizar Markdown e gráficos na primeira abertura
  (marked.js + Plotly.js via CDN).</em>
</div>
""", unsafe_allow_html=True)


# ── Utilitário de card ─────────────────────────────────────────────────────────

def _card(name: str, category: str, desc: str, examples: list[str]) -> str:
    badge = f'<span class="tc-badge tc-badge--{category}">{category}</span>'
    pills = "".join(f'<span class="prompt-pill">"{ex}"</span>' for ex in examples)
    return f"""
    <div class="tool-card" style="--tc-color: {'#2563EB' if category=='consulta'
        else '#F59E0B' if category=='escrita'
        else '#22C55E' if category=='grafico'
        else '#8B5CF6' if category=='calendario'
        else '#EF4444'}">
      <div class="tc-header">
        {badge}
        <span class="tc-name">{name}</span>
      </div>
      <div class="tc-desc">{desc}</div>
      <div class="tc-examples-label">Exemplos de prompt</div>
      <div>{pills}</div>
    </div>"""


# ── Tabs por categoria ─────────────────────────────────────────────────────────
tab_reunioes, tab_analise, tab_graficos, tab_calendario, tab_hub, tab_admin = st.tabs([
    "🗂️ Reuniões",
    "📋 Análise",
    "📈 Gráficos",
    "📅 Calendário",
    "🧠 Knowledge Hub",
    "🛡️ Admin & Sistema",
])


# ── Tab 1: Reuniões ───────────────────────────────────────────────────────────
with tab_reunioes:
    st.markdown('<div class="g-section-hdr">Consulta de dados de reuniões</div>', unsafe_allow_html=True)

    st.markdown(_card(
        "get_meeting_list", "consulta",
        "Lista todas as reuniões do projeto com número, título, data, e indica se "
        "possuem ata e transcrição armazenadas.",
        [
            "Liste todas as reuniões do projeto",
            "Quais reuniões já foram processadas?",
            "Mostre o histórico de reuniões com data e título",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "get_meeting_summary", "consulta",
        "Retorna a ata completa de uma reunião: participantes, pauta, resumo, "
        "decisões e itens de ação.",
        [
            "Mostre o resumo da reunião 3",
            "Qual foi a pauta da última reunião?",
            "Me dê a ata completa da reunião de kickoff",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "get_meeting_participants", "consulta",
        "Retorna a lista completa de participantes de uma reunião específica, "
        "extraída da ata gerada pelo pipeline.",
        [
            "Quem participou da reunião 2?",
            "Liste os presentes na reunião de requisitos",
            "Quantas pessoas estavam na reunião 5?",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "get_meeting_decisions", "consulta",
        "Retorna as decisões formais tomadas em uma reunião específica.",
        [
            "Quais decisões foram tomadas na reunião 4?",
            "Liste as deliberações da reunião de arquitetura",
            "O que ficou decidido na última reunião?",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "get_meeting_action_items", "consulta",
        "Retorna os itens de ação (tarefas) definidos em uma reunião. "
        "Pode filtrar por responsável.",
        [
            "Quais são os encaminhamentos da reunião 3?",
            "Mostre as tarefas atribuídas ao João na reunião 2",
            "Liste todos os itens de ação com prazo",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "get_meeting_metadata", "consulta",
        "Retorna metadados e status de uma reunião: presença de transcrição, ata, "
        "requisitos, BPMN, SBVR e embeddings. Útil para verificar o que foi gerado.",
        [
            "A reunião 3 tem BPMN gerado?",
            "Quais artefatos foram produzidos na reunião 1?",
            "Verifique o status completo da reunião 5",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "get_speaker_contributions", "consulta",
        "Busca TODAS as contribuições de um participante: trechos de transcrição, "
        "requisitos propostos e regras de negócio SBVR. Aceita nome, iniciais ou sobrenome.",
        [
            "Quais foram as contribuições da Ana em todas as reuniões?",
            "O que o Pedro propôs durante o projeto?",
            "Mostre os requisitos levantados pela Maria",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "calculate_meeting_roi", "consulta",
        "Calcula o ROI-TR (Retorno sobre Investimento de Tempo de Reunião) — pondera "
        "decisões, requisitos, BPMN e ata pelo tipo de reunião detectado.",
        [
            "Qual é o ROI da reunião 2?",
            "Calcule o retorno de todas as reuniões do projeto",
            "A reunião de ontem foi produtiva? Calcule o ROI-TR",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "get_recurring_topics", "consulta",
        "Detecta tópicos discutidos em múltiplas reuniões sem resolução definitiva — "
        "o padrão de 'patinação' que gera desperdício de tempo.",
        [
            "Quais temas se repetem sem resolução?",
            "Identifique os assuntos recorrentes do projeto",
            "O que a equipe discute sem chegar a conclusão?",
        ]
    ), unsafe_allow_html=True)


# ── Tab 2: Análise ────────────────────────────────────────────────────────────
with tab_analise:
    st.markdown('<div class="g-section-hdr">Transcrições, requisitos e modelos</div>', unsafe_allow_html=True)

    st.markdown(_card(
        "search_transcript", "consulta",
        "Busca trechos relevantes nas transcrições usando palavras-chave. "
        "Use quando precisar de falas, discussões ou contexto detalhado sobre um tema.",
        [
            "O que foi dito sobre autenticação nas reuniões?",
            "Busque menções à LGPD nas transcrições",
            "Quem falou sobre prazo de entrega?",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "get_requirements", "consulta",
        "Retorna os requisitos formalizados do projeto (IEEE 830): funcionais, "
        "não-funcionais, restrições, regras de negócio. Pode filtrar por tipo.",
        [
            "Liste todos os requisitos funcionais",
            "Quais são os requisitos de segurança?",
            "Mostre os requisitos de alta prioridade",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "update_requirement_status", "escrita",
        "Atualiza o status de um ou mais requisitos (active → approved, rejected, "
        "deferred, implemented). Cria versão de histórico automaticamente.",
        [
            "Marque o REQ-005 como aprovado",
            "Adie os requisitos REQ-010 e REQ-011",
            "O requisito de relatório foi implementado — atualize o status",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "list_bpmn_processes", "consulta",
        "Lista os processos BPMN registrados no projeto com número de versões "
        "e data da última atualização.",
        [
            "Quais processos BPMN foram mapeados?",
            "Liste os diagramas de processo do projeto",
            "Quantas versões o processo de onboarding tem?",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "list_bpmn_versions", "consulta",
        "Lista todas as versões de um processo BPMN pelo nome, mostrando ID único, "
        "número de versão, status (atual ✅ ou histórico), reunião de origem e notas "
        "de alteração. Use antes de delete_bpmn_version para obter o version_id correto.",
        [
            "Liste as versões do processo 'Validação de Catálogo'",
            "Quais versões existem do processo de onboarding?",
            "Mostre o histórico de versões do diagrama de aprovação",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "get_sbvr_terms", "consulta",
        "Retorna o vocabulário SBVR do projeto: termos de negócio com definição, "
        "sinônimos e referência à fonte.",
        [
            "Quais são os termos de negócio definidos?",
            "O que significa 'Documento de Auditoria' no contexto do projeto?",
            "Liste o glossário SBVR completo",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "get_sbvr_rules", "consulta",
        "Retorna as regras de negócio SBVR formalizadas, com esfera organizacional, "
        "dono e referência a políticas BMM.",
        [
            "Quais são as regras de negócio do projeto?",
            "Liste as regras da esfera jurídica",
            "Mostre as regras vinculadas à política de conformidade",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "add_sbvr_term", "escrita",
        "Adiciona um novo termo ao vocabulário SBVR do projeto, com definição "
        "e sinônimos opcionais.",
        [
            "Adicione o termo 'Nota Fiscal Eletrônica' com a definição: documento fiscal digital emitido pelo contribuinte",
            "Crie o termo SBVR 'SLA' significando Acordo de Nível de Serviço",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "add_sbvr_rule", "escrita",
        "Adiciona uma nova regra de negócio ao modelo SBVR do projeto.",
        [
            "Adicione a regra: todo documento deve ser aprovado por um gestor antes da publicação",
            "Crie a regra SBVR: o prazo de resposta máximo é de 5 dias úteis",
        ]
    ), unsafe_allow_html=True)

    st.markdown('<div class="g-section-hdr">Debates argumentativos — IBIS</div>', unsafe_allow_html=True)

    st.markdown(_card(
        "search_ibis_debates", "consulta",
        "Busca questões argumentativas (IBIS) por palavra-chave. Retorna, para cada "
        "questão encontrada: enunciado, quem levantou, alternativas avaliadas com "
        "<em>proposta por</em>, prós, contras, apoiadores e opositores, resolução e "
        "ressalvas. Filtrável por status: <code>all | decided | deferred | unresolved</code>.",
        [
            "Pesquise nos debates IBIS tudo que foi discutido sobre 'Catálogo Mestre' com detalhes completos",
            "Liste as questões IBIS decididas sobre autenticação",
            "O que foi debatido sobre prazo de entrega? Mostre alternativas e prós/contras",
            "Quais questões sobre o módulo de relatórios ainda estão em aberto?",
        ]
    ), unsafe_allow_html=True)


# ── Tab 3: Gráficos ───────────────────────────────────────────────────────────
with tab_graficos:
    st.markdown('<div class="g-section-hdr">Visualizações interativas (Plotly)</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="tip-box">
      Os gráficos são gerados com <strong>Plotly</strong> e renderizados diretamente
      no chat. Use paletas de cor nomeadas: <em>azul</em>, <em>verde</em>,
      <em>âmbar</em>, <em>roxo</em>, <em>vermelho</em>, <em>cinza</em>.
    </div>
    """, unsafe_allow_html=True)

    st.markdown(_card(
        "generate_requirements_chart", "grafico",
        "Gera gráfico de barras com distribuição de requisitos por tipo (Funcional, "
        "Não-Funcional, Restrição, etc.) e/ou por prioridade.",
        [
            "Mostre um gráfico com a distribuição de requisitos por tipo",
            "Gere um gráfico de requisitos por prioridade em verde",
            "Quantos requisitos de cada tipo temos? Visualize em barras",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "generate_meetings_timeline", "grafico",
        "Gera linha do tempo interativa das reuniões do projeto com ROI-TR e "
        "contagem de artefatos por reunião.",
        [
            "Mostre a linha do tempo das reuniões",
            "Gere um gráfico temporal das reuniões com ROI",
            "Visualize a evolução do projeto em uma timeline",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "generate_action_items_chart", "grafico",
        "Gera gráfico de itens de ação por responsável e/ou por status "
        "(pendente, concluído, atrasado).",
        [
            "Mostre os encaminhamentos por responsável em gráfico",
            "Gere um gráfico de tarefas por status",
            "Quem tem mais itens de ação? Visualize em barras",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "generate_roi_chart", "grafico",
        "Gera gráfico de barras horizontais com o ROI-TR de cada reunião, "
        "ordenado por valor.",
        [
            "Visualize o ROI de todas as reuniões em gráfico",
            "Gere um gráfico comparando o retorno de cada reunião",
            "Quais reuniões tiveram melhor ROI? Mostre em barras",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "generate_custom_chart", "grafico",
        "Gera um gráfico personalizado (barras, linhas, pizza, dispersão) a partir "
        "de dados fornecidos pelo usuário ou extraídos de outra ferramenta.",
        [
            "Crie um gráfico de pizza com a distribuição de tipos de reunião",
            "Plote um gráfico de linha com o número de requisitos por reunião",
            "Gere um gráfico de dispersão de ROI vs. duração das reuniões",
        ]
    ), unsafe_allow_html=True)

    st.markdown('<div class="g-section-hdr">Debates argumentativos — IBIS</div>', unsafe_allow_html=True)

    st.markdown(_card(
        "get_ibis_timeline", "grafico",
        "Gera gráfico de barras empilhadas com a evolução temporal dos debates IBIS "
        "por reunião — separados por status (✅ Decidida, ⏳ Adiada, ❓ Em aberto). "
        "Aceita filtro por tema para focar em um conjunto de questões.",
        [
            "Mostre a evolução dos debates IBIS por reunião",
            "Gere um gráfico temporal dos debates sobre 'Catálogo Mestre'",
            "Como os debates sobre integração evoluíram ao longo das reuniões?",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "generate_ibis_map", "grafico",
        "Gera mapa argumentativo hierárquico em Plotly: questões (Q) como nós "
        "circulares coloridos por status e alternativas (A) como diamantes — "
        "verde se eleita, azul se descartada. Colunas por reunião, arestas Q→A. "
        "Aceita filtro por tema.",
        [
            "Mostre o mapa argumentativo IBIS de todo o projeto",
            "Gere um mapa visual das questões sobre 'Catálogo Mestre' com alternativas",
            "Visualize os debates IBIS sobre autenticação em formato de mapa",
            "Liste tudo que foi debatido sobre 'Catálogo Mestre', decisões e ideias, relate temporalmente por reunião mostrando um Mapa Visual",
        ]
    ), unsafe_allow_html=True)


# ── Tab 4: Calendário ─────────────────────────────────────────────────────────
with tab_calendario:
    st.markdown('<div class="g-section-hdr">Google Calendar — consulta</div>', unsafe_allow_html=True)

    st.markdown(_card(
        "calendar_list_events", "calendario",
        "Lista os próximos eventos do Google Calendar do projeto. "
        "Pode filtrar por período e por texto.",
        [
            "Quais reuniões estão agendadas esta semana?",
            "Mostre os eventos do calendário do projeto em maio",
            "Há algum evento agendado com o cliente?",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "calendar_get_event", "calendario",
        "Retorna os detalhes completos de um evento do Google Calendar pelo seu ID.",
        [
            "Me dê os detalhes do evento de revisão de sprint",
            "Qual é o link da reunião de amanhã?",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "calendar_suggest_time", "calendario",
        "Sugere horários livres para uma reunião consultando a API freebusy "
        "do Google Calendar.",
        [
            "Qual é o melhor horário para reunir a equipe esta semana?",
            "Encontre 1 hora livre na próxima semana para um alinhamento",
            "Quando todos estão disponíveis na quarta-feira?",
        ]
    ), unsafe_allow_html=True)

    st.markdown('<div class="g-section-hdr">Google Calendar — ações (admin)</div>', unsafe_allow_html=True)

    st.markdown(_card(
        "calendar_create_event", "admin",
        "Cria um novo evento no Google Calendar do projeto com título, descrição, "
        "data/hora, duração e convidados.",
        [
            "Agende uma revisão de requisitos para sexta às 14h com Ana e Pedro",
            "Crie um evento de follow-up da reunião 3 para a próxima terça",
            "Marque uma retrospectiva de 1 hora para o final do mês",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "calendar_schedule_action_items", "admin",
        "Cria automaticamente eventos no Google Calendar para cada item de ação "
        "de uma reunião, usando responsável e prazo da ata.",
        [
            "Agende todos os encaminhamentos da reunião 4 no calendário",
            "Crie lembretes para os itens de ação da última reunião",
            "Coloque os encaminhamentos da reunião 2 na agenda",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "calendar_share_with_user", "admin",
        "Compartilha a agenda do projeto com um e-mail Google, com permissão "
        "de visualização ou edição.",
        [
            "Compartilhe o calendário do projeto com joao@empresa.com",
            "Dê acesso de visualização da agenda para o cliente",
            "Adicione maria@empresa.com como editora do calendário",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "calendar_revoke_access", "admin",
        "Remove o acesso de um e-mail Google à agenda do projeto.",
        [
            "Remova o acesso do joao@empresa.com ao calendário",
            "Revogue a permissão da maria@empresa.com na agenda",
        ]
    ), unsafe_allow_html=True)


# ── Tab 5: Knowledge Hub ──────────────────────────────────────────────────────
with tab_hub:
    st.markdown('<div class="g-section-hdr">Entidades e grafo de conhecimento</div>', unsafe_allow_html=True)

    st.markdown(_card(
        "lookup_entity", "consulta",
        "Consulta uma entidade no Knowledge Hub por nome. Retorna tipo, aliases, "
        "número de ocorrências, descrição e reuniões onde apareceu.",
        [
            "O que é o sistema SIGED no contexto do projeto?",
            "Mostre as informações sobre a entidade Departamento de TI",
            "Em quais reuniões o processo de homologação foi mencionado?",
        ]
    ), unsafe_allow_html=True)

    st.markdown('<div class="g-section-hdr">Cache semântico de LLM</div>', unsafe_allow_html=True)

    st.markdown(_card(
        "get_cache_stats", "consulta",
        "Retorna estatísticas do cache semântico: total de entradas, hits acumulados, "
        "tokens economizados e custo estimado em USD, com breakdown por agente.",
        [
            "Qual é o hit ratio do cache LLM?",
            "Quanto economizamos de API com o cache?",
            "Mostre as estatísticas de cache por agente",
            "Qual agente mais se beneficia do cache?",
        ]
    ), unsafe_allow_html=True)

    st.markdown('<div class="g-section-hdr">Entidades — ações (admin)</div>', unsafe_allow_html=True)

    st.markdown(_card(
        "resolve_entity_ambiguity", "admin",
        "Funde entidades duplicadas em uma entidade canônica. Use quando duas "
        "entidades representam o mesmo objeto real (ex: 'TI' e 'Departamento de TI').",
        [
            "Funde as entidades 'TI' e 'Departamento de TI' — são a mesma coisa",
            "Mescle 'SIGED' e 'Sistema SIGED' em uma entidade canônica",
            "Resolva a ambiguidade entre 'Ana' e 'Ana Lima'",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "delete_entity", "admin",
        "Remove permanentemente uma entidade espúria do Knowledge Hub. Use quando "
        "a entidade é ruído de ASR ou erro de extração, e NÃO um duplicado.",
        [
            "Remova a entidade 'Hmm' — é ruído de transcrição",
            "Delete a entidade 'Sistema' — é genérica demais para ser útil",
            "Apague 'um' do grafo — foi capturado por erro",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "delete_bpmn_version", "admin",
        "Exclui permanentemente uma versão específica de um diagrama BPMN. "
        "Seguro: recusa excluir a única versão de um processo; se a versão excluída "
        "for a atual, promove automaticamente a versão anterior. "
        "Use list_bpmn_versions primeiro para obter o version_id.",
        [
            "Delete a versão 2 do processo 'Validação de Catálogo' — foi gerada com erro",
            "Remova as versões antigas do processo de onboarding, mantendo apenas a atual",
            "Exclua a versão 1 do diagrama de aprovação — era um rascunho",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "clear_llm_cache", "admin",
        "Invalida entradas do cache semântico de LLM. Use quando o prompt de um "
        "agente foi atualizado e as respostas cacheadas estão desatualizadas.",
        [
            "Limpa o cache do agente SBVR — o prompt foi atualizado",
            "Invalide todo o cache LLM para forçar reprocessamento limpo",
            "Limpe o cache do BPMN apenas",
        ]
    ), unsafe_allow_html=True)


# ── Tab 6: Admin & Sistema ────────────────────────────────────────────────────
with tab_admin:
    st.markdown('<div class="g-section-hdr">Sistema e capacidades</div>', unsafe_allow_html=True)

    st.markdown(_card(
        "get_system_capabilities", "consulta",
        "Retorna a lista completa de funcionalidades, integrações e operações "
        "disponíveis no sistema — incluindo status do Google Calendar.",
        [
            "O que o assistente consegue fazer?",
            "Quais integrações estão ativas no sistema?",
            "Liste todas as funcionalidades disponíveis",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "get_cache_stats", "consulta",
        "Retorna estatísticas globais do cache LLM — disponível para todos os perfis. "
        "Ver aba Knowledge Hub para detalhes.",
        [
            "Qual a economia de API acumulada?",
            "Mostre o custo evitado com cache desde o início do projeto",
        ]
    ), unsafe_allow_html=True)

    st.markdown('<div class="g-section-hdr">Banco de dados — admin</div>', unsafe_allow_html=True)

    st.markdown(_card(
        "get_database_integrity", "admin",
        "Verifica a integridade do banco de dados: reuniões sem provedor LLM, "
        "sem embeddings, processos BPMN órfãos, e outros problemas.",
        [
            "Verifique a integridade do banco de dados",
            "Há reuniões sem embeddings gerados?",
            "Mostre os problemas encontrados no Supabase",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "generate_meeting_embeddings", "admin",
        "Gera ou regenera os embeddings vetoriais de uma reunião, necessários para "
        "a busca semântica no Assistente.",
        [
            "Gere os embeddings da reunião 3",
            "A reunião 5 não aparece nas buscas — regenere os embeddings",
            "Gere embeddings para todas as reuniões sem cobertura",
        ]
    ), unsafe_allow_html=True)

    st.markdown('<div class="g-section-hdr">Reprocessamento — admin</div>', unsafe_allow_html=True)

    st.markdown(_card(
        "reprocess_meeting_full", "admin",
        "Re-executa o pipeline completo em uma reunião existente, regenerando todos "
        "os artefatos: ata, requisitos, SBVR, BMM, BPMN, grafo e sumário.",
        [
            "Reprocesse a reunião 3 com todos os agentes",
            "Regenere todos os artefatos da reunião de kickoff",
            "Rode o pipeline completo novamente na reunião 1",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_card(
        "delete_meeting", "admin",
        "Remove uma reunião e todos os seus artefatos do banco de dados "
        "(cascata completa: requisitos, BPMN, SBVR, embeddings, etc.).",
        [
            "Delete a reunião 7 — foi processada com transcrição errada",
            "Remova a reunião de teste do projeto",
            "Exclua permanentemente a reunião 2 e todos seus dados",
        ]
    ), unsafe_allow_html=True)

    st.markdown('<div class="g-section-hdr">Projeto ativo</div>', unsafe_allow_html=True)

    st.markdown(_card(
        "set_active_project", "escrita",
        "Define o projeto ativo para todas as páginas de análise. "
        "Aceita nome parcial (case-insensitive).",
        [
            "Mude o projeto ativo para SDEA",
            "Ative o projeto de auditoria",
            "Troque para o projeto do cliente X",
        ]
    ), unsafe_allow_html=True)

# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption(
    "As ferramentas são invocadas automaticamente pelo LLM com base na intenção do prompt. "
    "Ferramentas admin exigem login com perfil administrador. "
    "Configurações em Sistema → Configurações → aba Assistente."
)
