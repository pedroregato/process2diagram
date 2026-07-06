# pages/Orientacoes_Graficos.py
# ─────────────────────────────────────────────────────────────────────────────
# Guia de gráficos do Assistente — o que cada visualização mostra, para que
# tipo de apresentação ela serve, e exemplos de prompt para gerá-la.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from ui.auth_gate import apply_auth_gate
from ui.components.page_header import render_page_header
from ui.components.copy_button import copy_button

apply_auth_gate()

render_page_header(
    "📈", "Guia — Gráficos do Assistente",
    "O que cada visualização mostra, para qual tipo de apresentação ela é mais "
    "indicada, e exemplos de prompt para pedir ao Assistente.",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
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
.chart-card {
    background: #080F1E;
    border: 1px solid #1A2E48;
    border-left: 4px solid var(--cc-color, #2563EB);
    border-radius: 10px;
    padding: 1rem 1.2rem 0.9rem;
    margin-bottom: 1rem;
}
.cc-header {
    display: flex; align-items: center; gap: .6rem;
    margin-bottom: .5rem; flex-wrap: wrap;
}
.cc-name {
    font-family: 'Courier New', monospace;
    font-size: .88rem; font-weight: 700;
    color: #D4E1F5; letter-spacing: .01em;
}
.cc-badge {
    display: inline-block;
    font-size: .62rem; font-weight: 800;
    letter-spacing: .09em; text-transform: uppercase;
    padding: .18rem .55rem; border-radius: 4px;
    background: #0A2210; color: #4ADE80; border: 1px solid #1A4A28;
}
.cc-label {
    font-size: .62rem; font-weight: 700; color: #4A6A8A;
    letter-spacing: .09em; text-transform: uppercase;
    margin: .55rem 0 .3rem;
}
.cc-desc  { font-size: .82rem; color: #B9C6DA; line-height: 1.55; }
.cc-best  { font-size: .82rem; color: #D4A850; line-height: 1.55; font-style: italic; }
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
.tip-box {
    background: #0A1628;
    border: 1px solid #1A3050;
    border-left: 3px solid #C97B1A;
    border-radius: 8px;
    padding: .75rem 1rem;
    font-size: .8rem; color: #9AAABB;
    margin: .8rem 0;
}
</style>
""", unsafe_allow_html=True)


def _chart_card(name: str, color: str, desc: str, best_for: str, examples: list[str]) -> str:
    pills = "".join(f'<span class="prompt-pill">"{ex}"</span>' for ex in examples)
    return f"""
    <div class="chart-card" style="--cc-color: {color}">
      <div class="cc-header">
        <span class="cc-badge">gráfico</span>
        <span class="cc-name">{name}</span>
      </div>
      <div class="cc-desc">{desc}</div>
      <div class="cc-label">Melhor para</div>
      <div class="cc-best">{best_for}</div>
      <div class="cc-label">Exemplos de prompt</div>
      <div>{pills}</div>
    </div>"""


# ═════════════════════════════════════════════════════════════════════════════
# Como funciona
# ═════════════════════════════════════════════════════════════════════════════
st.markdown("## 🧭 Como funciona")
st.markdown(
    """
Basta pedir em linguagem natural, no **Assistente** (menu **Análise → 💬 Assistente**).
O LLM decide sozinho qual ferramenta de gráfico chamar com base no que você pediu —
não é necessário citar o nome técnico da ferramenta. Os gráficos são gerados com
**Plotly** e aparecem diretamente no chat, com zoom, pan, hover e download em PNG.

Você pode pedir a paleta de cor por nome: *azul*, *verde*, *âmbar*, *roxo*,
*vermelho*, *cinza*. E ao final da conversa, o botão **⬇️ HTML** na barra do chat
exporta tudo — incluindo os gráficos interativos — em um único arquivo
auto-contido, pronto para enviar por e-mail ou anexar a uma apresentação.
"""
)
st.markdown(
    """
<div class="tip-box">
  Todas as ferramentas abaixo funcionam escopadas ao <strong>contexto (projeto)
  ativo</strong> no momento — troque de projeto na barra lateral antes de pedir
  o gráfico, se necessário.
</div>
""", unsafe_allow_html=True)

st.markdown("---")

# ═════════════════════════════════════════════════════════════════════════════
# Tabs por família de gráfico
# ═════════════════════════════════════════════════════════════════════════════
tab_fund, tab_fluxo, tab_cruz, tab_multi, tab_plan, tab_ibis, tab_custom = st.tabs([
    "📊 Fundamentais",
    "🌊 Fluxo & Hierarquia",
    "🔥 Cruzamentos",
    "🫧 Multi-dimensional",
    "🗓️ Planejamento",
    "💬 Argumentação (IBIS)",
    "🎨 Personalizado",
])

# ── Fundamentais ───────────────────────────────────────────────────────────────
with tab_fund:
    st.markdown('<div class="g-section-hdr">Distribuição, evolução e produtividade</div>', unsafe_allow_html=True)

    st.markdown(_chart_card(
        "generate_requirements_chart", "#2563EB",
        "Gráfico de barras com a distribuição de requisitos por tipo (Funcional, "
        "Não-Funcional, Restrição...) e/ou por prioridade. A visão mais básica e "
        "direta do backlog de requisitos.",
        "Reuniões de status, refinamento de backlog, visão geral rápida para "
        "stakeholders técnicos que já conhecem o vocabulário IEEE 830.",
        [
            "Mostre um gráfico com a distribuição de requisitos por tipo",
            "Gere um gráfico de requisitos por prioridade em verde",
            "Quantos requisitos de cada tipo temos na reunião 3? Visualize em barras",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_chart_card(
        "generate_meetings_timeline", "#2563EB",
        "Barras agrupadas mostrando, reunião a reunião, o volume de requisitos, "
        "decisões e ações extraídos das atas.",
        "Retrospectiva de projeto, prestação de contas de produtividade ao longo "
        "do tempo, identificar reuniões particularmente densas ou vazias.",
        [
            "Mostre a linha do tempo das reuniões com requisitos, decisões e ações",
            "Gere um gráfico temporal do volume de decisões por reunião",
            "Visualize a evolução do projeto reunião a reunião",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_chart_card(
        "generate_action_items_chart", "#2563EB",
        "Gráfico de itens de ação por responsável e/ou por status (pendente, "
        "concluído, atrasado).",
        "Reunião de acompanhamento (follow-up), dailies/weeklies, cobrança de "
        "responsáveis antes de uma reunião de status.",
        [
            "Mostre os encaminhamentos por responsável em gráfico",
            "Gere um gráfico de tarefas por status",
            "Quem tem mais itens de ação pendentes? Visualize em barras",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_chart_card(
        "generate_roi_chart", "#2563EB",
        "Barras horizontais com o indicador ROI-TR (Retorno sobre Investimento de "
        "Tempo de Reunião) de cada reunião, ordenadas por valor.",
        "Justificar o valor gerado pelas reuniões a um comitê de eficiência "
        "operacional, ou decidir quais formatos de reunião merecem continuar.",
        [
            "Visualize o ROI de todas as reuniões em gráfico",
            "Gere um gráfico comparando o retorno de cada reunião",
            "Quais reuniões tiveram melhor ROI? Mostre em barras",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_chart_card(
        "generate_requirements_waterfall", "#2563EB",
        "Gráfico de cascata (waterfall) mostrando quantos requisitos foram "
        "adicionados em cada reunião e quantos saíram de 'ativo' (contraditados "
        "ou depreciados), até o saldo líquido final.",
        "Relatório de fechamento de fase — mostrar o saldo real de escopo ao "
        "longo do projeto, distinguindo crescimento de escopo de mera repactuação.",
        [
            "Como o total de requisitos ativos evoluiu ao longo do projeto?",
            "Gere um waterfall do saldo de requisitos por reunião",
            "Mostre quantos requisitos foram descartados vs. mantidos, reunião a reunião",
        ]
    ), unsafe_allow_html=True)

# ── Fluxo & Hierarquia ─────────────────────────────────────────────────────────
with tab_fluxo:
    st.markdown('<div class="g-section-hdr">Sankey, Treemap e Sunburst</div>', unsafe_allow_html=True)

    st.markdown(_chart_card(
        "generate_requirements_flow_chart", "#22C55E",
        "Visualiza a hierarquia <strong>Tipo → Prioridade → Status</strong> dos "
        "requisitos como <strong>Sankey</strong> (fluxo entre categorias, revela "
        "gargalos), <strong>Treemap</strong> (blocos proporcionais aninhados) ou "
        "<strong>Sunburst</strong> (anéis concêntricos). Escolha a view no prompt.",
        "Apresentação de comitê executivo — é o tipo de gráfico de maior impacto "
        "visual do repertório; substitui 3 gráficos de barra separados por um "
        "único golpe de vista. Ótimo para abrir uma seção de 'panorama de requisitos'.",
        [
            "Visualize o fluxo dos requisitos por tipo, prioridade e status em Sankey",
            "Gere um treemap dos requisitos da reunião 2",
            "Mostre a distribuição hierárquica de requisitos em sunburst",
        ]
    ), unsafe_allow_html=True)

# ── Cruzamentos ─────────────────────────────────────────────────────────────────
with tab_cruz:
    st.markdown('<div class="g-section-hdr">Mapa de calor cruzado</div>', unsafe_allow_html=True)

    st.markdown(_chart_card(
        "generate_requirements_heatmap", "#EF4444",
        "Matriz de calor <strong>Reunião × Tipo/Prioridade/Status</strong> de "
        "requisitos, montada automaticamente a partir do banco — você só escolhe "
        "a dimensão a cruzar com a reunião.",
        "Retrospectiva multi-reunião — identificar rapidamente em qual reunião "
        "se concentrou determinado tipo de requisito (ex: 'a R1 levantou muitos "
        "requisitos funcionais, a R2 muitos não-funcionais').",
        [
            "Gere um heatmap de requisitos por reunião e tipo",
            "Qual reunião teve mais requisitos de prioridade alta? Mostre em mapa de calor",
            "Cruze reunião e status dos requisitos em um heatmap",
        ]
    ), unsafe_allow_html=True)

# ── Multi-dimensional ────────────────────────────────────────────────────────────
with tab_multi:
    st.markdown('<div class="g-section-hdr">Bolhas e radar — várias dimensões em um só gráfico</div>', unsafe_allow_html=True)

    st.markdown(_chart_card(
        "generate_requirements_bubble_chart", "#8B5CF6",
        "Gráfico de bolhas: eixo X = reunião, eixo Y = prioridade média "
        "(1 = baixa, 3 = alta), tamanho da bolha = quantidade de requisitos. "
        "3 dimensões em um único gráfico compacto.",
        "Status report semanal ou dashboard executivo com pouco espaço na tela "
        "— resume volume e criticidade de cada reunião num único elemento visual.",
        [
            "Gere um gráfico de bolhas de requisitos por reunião",
            "Compare volume e prioridade média de requisitos entre as reuniões",
            "Mostre um bubble chart do backlog do projeto",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_chart_card(
        "generate_meeting_radar_chart", "#8B5CF6",
        "Radar (teia) comparando de 2 a 6 reuniões em 4 eixos: Decisões, Ações, "
        "Requisitos e Participantes — contagens brutas extraídas das atas.",
        "Comparar a 'densidade' de várias reuniões de uma só vez — retrospectivas "
        "comparativas, avaliar se um novo formato de reunião foi mais produtivo "
        "que o anterior.",
        [
            "Compare as reuniões 1, 2 e 3 em um radar",
            "Gere um gráfico radar comparando as últimas reuniões do projeto",
            "Quais reuniões foram mais densas em decisões e ações? Mostre em teia",
        ]
    ), unsafe_allow_html=True)

# ── Planejamento ─────────────────────────────────────────────────────────────────
with tab_plan:
    st.markdown('<div class="g-section-hdr">Cronograma</div>', unsafe_allow_html=True)

    st.markdown(_chart_card(
        "generate_gantt_chart", "#F59E0B",
        "Cronograma (Gantt) a partir de fases/marcos que você informa explicitamente "
        "no prompt — o sistema não tem um modelo nativo de planejamento com datas, "
        "então o LLM monta as fases a partir do que for descrito (ou estimado com "
        "base nas datas das reuniões já realizadas).",
        "Apresentação de cronograma/roadmap a um patrocinador (sponsor), kickoff "
        "de projeto, ou visualizar retroativamente as fases já percorridas.",
        [
            "Mostre o cronograma com a Fase 1 (Descoberta), Fase 2 (Requisitos) e Fase 3 (Modelagem)",
            "Gere um Gantt com as fases do projeto com base nas datas das reuniões",
            "Crie um cronograma marcando a fase de validação como atrasada",
        ]
    ), unsafe_allow_html=True)

# ── IBIS ─────────────────────────────────────────────────────────────────────────
with tab_ibis:
    st.markdown('<div class="g-section-hdr">Debates argumentativos</div>', unsafe_allow_html=True)

    st.markdown(_chart_card(
        "get_ibis_timeline", "#A78BFA",
        "Barras empilhadas com a evolução temporal dos debates IBIS por reunião "
        "— separados por status (✅ Decidida, ⏳ Adiada, ❓ Em aberto). Aceita "
        "filtro por tema.",
        "Auditoria de governança de decisões — mostrar que o processo decisório "
        "converge ao longo do tempo (menos questões em aberto a cada reunião).",
        [
            "Mostre a evolução dos debates IBIS por reunião",
            "Gere um gráfico temporal dos debates sobre 'Catálogo Mestre'",
            "Como os debates sobre integração evoluíram ao longo das reuniões?",
        ]
    ), unsafe_allow_html=True)

    st.markdown(_chart_card(
        "generate_ibis_map", "#A78BFA",
        "Mapa argumentativo hierárquico: questões (Q) como nós circulares "
        "coloridos por status, alternativas (A) como diamantes — verde se "
        "eleita, azul se descartada. Colunas por reunião, arestas Q→A.",
        "Justificar uma decisão arquitetural/de negócio a um comitê técnico — "
        "mostra não só a decisão final, mas quais alternativas foram consideradas "
        "e descartadas, e em qual reunião a discussão ocorreu.",
        [
            "Mostre o mapa argumentativo IBIS de todo o projeto",
            "Gere um mapa visual das questões sobre 'Catálogo Mestre' com alternativas",
            "Visualize os debates sobre autenticação em formato de mapa",
        ]
    ), unsafe_allow_html=True)

# ── Personalizado ─────────────────────────────────────────────────────────────────
with tab_custom:
    st.markdown('<div class="g-section-hdr">Quando nenhum gráfico pronto serve</div>', unsafe_allow_html=True)

    st.markdown(_chart_card(
        "generate_custom_chart", "#64748B",
        "Gráfico personalizado (barras, linha, pizza, dispersão, funil ou "
        "heatmap) a partir de dados fornecidos pelo LLM — use quando o pedido "
        "não se encaixa em nenhuma das ferramentas pré-definidas acima.",
        "Pedidos ad-hoc e não padronizados — quando você sabe exatamente que "
        "dado quer plotar, mas ele não corresponde a nenhum dos gráficos prontos.",
        [
            "Crie um gráfico de pizza com a distribuição de tipos de reunião",
            "Plote um gráfico de linha com o número de requisitos por reunião",
            "Gere um gráfico de dispersão de ROI vs. duração das reuniões",
        ]
    ), unsafe_allow_html=True)

st.markdown("---")

# ═════════════════════════════════════════════════════════════════════════════
# Prompt complexo — resumo executivo completo
# ═════════════════════════════════════════════════════════════════════════════
st.markdown("## 🎯 Prompt complexo — resumo executivo completo")
st.markdown(
    """
O prompt abaixo pede ao Assistente para montar, em uma única resposta, uma
**apresentação executiva completa** do projeto — explorando praticamente todo
o repertório visual descrito acima, na ordem em que faria sentido apresentar a
um comitê: panorama de requisitos → cruzamentos → comparação entre reuniões →
evolução → cronograma → decisões. Copie, cole no Assistente e ajuste os nomes
de fase do cronograma para o seu projeto.
"""
)

PROMPT_EXECUTIVO = """Preciso de um resumo executivo completo deste projeto para apresentar ao comitê. Monte a apresentação na seguinte ordem, um gráfico por vez, com uma frase de contexto antes de cada um:

1. Um gráfico de barras com a distribuição de requisitos por tipo e prioridade.
2. Um Sankey mostrando o fluxo Tipo → Prioridade → Status de todos os requisitos do projeto.
3. Um heatmap cruzando reunião × tipo de requisito.
4. Um gráfico de bolhas comparando volume e prioridade média de requisitos por reunião.
5. Um waterfall mostrando a evolução líquida de requisitos ativos ao longo do projeto.
6. Um radar comparando as reuniões do projeto em decisões, ações, requisitos e participantes.
7. Um gráfico de ROI-TR de todas as reuniões, ordenado por valor.
8. Um cronograma (Gantt) com as fases do projeto — estime as fases e datas com base nas reuniões já realizadas (ex: Descoberta, Levantamento de Requisitos, Modelagem BPMN, Validação, Encerramento).
9. O mapa argumentativo IBIS de todo o projeto, se houver debates registrados.

Ao final, escreva um parágrafo de síntese executiva interpretando os gráficos em conjunto — riscos, gargalos e recomendações. Depois disso eu vou exportar esta conversa em HTML para enviar ao comitê."""

st.text_area(
    "Prompt de resumo executivo (copie e cole no Assistente)",
    value=PROMPT_EXECUTIVO,
    height=320,
    key="orient_graficos_prompt_executivo",
    label_visibility="collapsed",
)
copy_button(PROMPT_EXECUTIVO, key="orient_graficos_prompt_executivo", label="📋 Copiar prompt")

st.markdown(
    """
**O que esperar do resultado:** uma sequência de 6 a 9 gráficos interativos no
chat (dependendo de quanto dado o projeto já tem — ex: sem debates IBIS
registrados, o item 9 é pulado), seguidos de um parágrafo de síntese. Use o
botão **⬇️ HTML** da barra do chat ao final para exportar tudo — inclusive os
gráficos Plotly, que continuam interativos no arquivo exportado — em um único
documento auto-contido pronto para o comitê.
"""
)

st.markdown("---")
st.page_link("pages/Assistente.py", label="→ Ir para o Assistente", icon="💬")
