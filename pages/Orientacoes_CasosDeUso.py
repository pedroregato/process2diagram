# pages/Orientacoes_CasosDeUso.py
# ─────────────────────────────────────────────────────────────────────────────
# Casos de Uso do Assistente — cenários de negócio reais, a pergunta literal
# que o usuário faz no chat, o que o Assistente entrega, e o valor concreto
# gerado. Foco em demonstrar VALOR DE NEGÓCIO, não documentação técnica de
# API (isso já existe em Orientacoes_Assistente.py).
#
# Fonte única de conteúdo (_SCENARIOS) alimenta dois renderizadores:
#   1. Streamlit — cards em abas, dentro do app.
#   2. HTML autocontido — botão "⬇️ Exportar HTML" gera o mesmo conteúdo
#      como página standalone, sem depender de manter 2 arquivos em sincronia
#      (diferente do par ApresentacaoGeral.py/apresentacao-geral.html).
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from ui.auth_gate import apply_auth_gate
from ui.components.page_header import render_page_header

apply_auth_gate()

render_page_header(
    "💼", "Casos de Uso — Valor de Negócio",
    "Cenários reais de uso do Assistente: a pergunta que você faz, o que ele entrega, "
    "e o ganho concreto para o negócio — não é referência técnica de API.",
)

# ── Conteúdo (fonte única) ───────────────────────────────────────────────────
# Cada categoria é uma lista de cenários: tool (nome técnico, opcional pra
# quem quiser ir direto), cenario (situação real que motiva a pergunta),
# pergunta (prompt literal, copiável), resposta (o que o Assistente faz/
# entrega), valor (o ganho de negócio em termos concretos — tempo, risco,
# qualidade, dinheiro).
_SCENARIOS: dict[str, list[dict]] = {
    "📤 Comunicação & Entrega": [
        {
            "tool": "exportar_pacote_completo",
            "cenario": "O cliente pediu \"me manda tudo que vocês levantaram até agora\" — "
                       "hoje isso significa abrir 6 telas diferentes e exportar cada artefato "
                       "na mão.",
            "pergunta": "Exporte tudo do projeto num único documento Word pra eu mandar pro cliente.",
            "resposta": "Um único .docx com Ata + Requisitos + SBVR + BMM + BPMN + IBIS, "
                        "sumário no topo e numeração de página — pronto pra anexar num e-mail.",
            "valor": "O que levaria ~1h reunindo e formatando manualmente vira 1 pedido no chat. "
                     "Menos risco de esquecer um artefato ou mandar uma versão desatualizada.",
        },
        {
            "tool": "gerar_deck_executivo",
            "cenario": "Reunião de comitê em 20 minutos e ninguém preparou slides — o patrocinador "
                       "só quer o resumo executivo do estado do projeto.",
            "pergunta": "Gere um deck executivo com visão geral, métricas e próximos passos.",
            "resposta": "7 slides em Markdown estruturado: visão/missão, métricas, requisitos, "
                        "processos, ROI-TR, pendências e próximos passos priorizados.",
            "valor": "Substitui horas de trabalho manual de PM/BA montando slide por slide — "
                     "o material sai direto dos dados reais do projeto, não de memória.",
        },
        {
            "tool": "gerar_variacao_apresentacao",
            "cenario": "O material comercial padrão é genérico, mas o próximo lead é do setor "
                       "de saúde e precisa de uma versão com essa lente.",
            "pergunta": "Gere uma variação da apresentação focada em clientes de saúde, "
                        "com ênfase em conformidade regulatória.",
            "resposta": "Uma nova versão em HTML autocontido, mesma identidade visual, "
                        "conteúdo adaptado — sem tocar no material oficial.",
            "valor": "Personalização de material de vendas sem depender de design/marketing "
                     "pra cada lead — minutos em vez de dias.",
        },
    ],
    "🚦 Acompanhamento & Gestão": [
        {
            "tool": "sugerir_encaminhamentos_pendentes",
            "cenario": "Depois de uma reunião longa, é fácil uma decisão importante ficar sem "
                       "um responsável e um prazo definidos — e isso só aparece quando já é tarde.",
            "pergunta": "Essa última reunião teve alguma decisão sem encaminhamento? "
                        "Tem algo vencido?",
            "resposta": "O Assistente compara decisões e encaminhamentos da ata e aponta "
                        "exatamente quais decisões ficaram órfãs e quais prazos já passaram.",
            "valor": "Detecção proativa de gaps de execução — o tipo de coisa que normalmente "
                     "só aparece numa auditoria, semanas depois, quando o custo de corrigir é maior.",
        },
        {
            "tool": "sugestoes_plantonista",
            "cenario": "Você assume um projeto no meio do caminho e precisa de contexto rápido "
                       "antes de qualquer reunião.",
            "pergunta": "Me dá um raio-x do projeto — o que está pendente?",
            "resposta": "Briefing instantâneo: reuniões sem ata, contradições abertas, "
                        "tópicos recorrentes sem resolução, encaminhamentos pendentes.",
            "valor": "Onboarding de um novo membro de equipe (ou retomada após período afastado) "
                     "em minutos, não em uma tarde inteira lendo atas antigas.",
        },
        {
            "tool": "compare_meetings",
            "cenario": "Duas reuniões de revisão de requisito, um mês de intervalo — o patrocinador "
                       "quer saber exatamente o que mudou de posição.",
            "pergunta": "Compare a reunião 3 com a reunião 8 — o que mudou nas decisões e "
                        "nos participantes?",
            "resposta": "Diff estruturado: quem entrou/saiu, decisões novas, encaminhamentos "
                        "que mudaram de status — sem precisar reler as duas atas na mão.",
            "valor": "Evita a pergunta constrangedora \"isso não tinha sido decidido diferente?\" "
                     "numa reunião com o cliente — a resposta já vem com evidência.",
        },
    ],
    "🔍 Auditoria & Rastreabilidade": [
        {
            "tool": "mapa_rastreabilidade",
            "cenario": "Um auditor pergunta \"de onde veio esse requisito, quem pediu, tem "
                       "respaldo na transcrição?\" — e a resposta precisa ser rastreável, não "
                       "\"eu acho que foi discutido em algum momento\".",
            "pergunta": "De onde veio o REQ-042? Mostre a fala original e onde ele aparece "
                        "no BPMN e no SBVR.",
            "resposta": "Cadeia de rastreamento: trecho literal da transcrição, processo BPMN "
                        "relacionado, regra SBVR vinculada — tudo com origem citada.",
            "valor": "Evidência auditável sob demanda, em segundos — essencial em setores "
                     "regulados (auditoria, compliance, jurídico) onde \"não lembro\" não é aceitável.",
        },
        {
            "tool": "verificar_rastreabilidade_obrigatoria",
            "cenario": "Antes de fechar uma fase do projeto, alguém precisa garantir que nada "
                       "ficou sem justificativa registrada — hoje isso é uma checagem manual, "
                       "item por item.",
            "pergunta": "Verifique se tem requisito sem citação de origem ou processo BPMN "
                        "sem descrição.",
            "resposta": "Varredura completa do projeto: requisitos sem `source_quote`, debates "
                        "IBIS sem resolução, processos sem descrição — com contagem e lista de IDs.",
            "valor": "Gate de qualidade automatizado antes de entregar uma fase — reduz risco "
                     "de retrabalho por gap encontrado tarde demais.",
        },
        {
            "tool": "verificar_conformidade",
            "cenario": "Uma norma interna ou regulatória mudou — alguém precisa descobrir "
                       "rápido o que no projeto é afetado, sem reler tudo do zero.",
            "pergunta": "Esse novo documento de política de dados afeta algum requisito "
                        "já aprovado?",
            "resposta": "Cruzamento entre o conteúdo do documento normativo e os requisitos "
                        "do projeto, apontando conflitos e pontos de atenção.",
            "valor": "Resposta em minutos a uma pergunta que, feita manualmente, exigiria "
                     "reler dezenas de requisitos contra o texto normativo inteiro.",
        },
    ],
    "🎲 Simulação & Risco": [
        {
            "tool": "simular_cenario",
            "cenario": "O cliente quer cortar escopo pra economizar prazo — mas ninguém sabe, "
                       "de cabeça, o efeito cascata de remover um requisito específico.",
            "pergunta": "E se removermos o REQ-042? O que mais é impactado?",
            "resposta": "Análise de impacto: requisitos relacionados, regras SBVR a revisar, "
                        "riscos da mudança, recomendação — tudo antes de decidir de fato.",
            "valor": "Decisão de escopo informada em vez de \"achismo\" — evita descobrir "
                     "o efeito colateral só depois que o corte já foi feito.",
        },
        {
            "tool": "estimar_risco_requisito",
            "cenario": "Com centenas de requisitos, é impossível revisar todos com o mesmo "
                       "nível de atenção antes de uma entrega — é preciso saber onde focar.",
            "pergunta": "Quais requisitos têm maior risco no projeto?",
            "resposta": "Score de risco por requisito, cruzando contradições abertas, número "
                        "de revisões e ligação com processos BPMN.",
            "valor": "Prioriza a atenção da equipe de QA/revisão pros pontos que realmente "
                     "importam, em vez de revisão uniforme e ineficiente.",
        },
        {
            "tool": "analisar_tendencias",
            "cenario": "O patrocinador quer saber se o projeto está \"instável\" — muitos "
                       "requisitos mudando de ideia — antes de comprometer um prazo final.",
            "pergunta": "Quais requisitos mais mudam de versão? Onde tem mais debate?",
            "resposta": "Rankings agregados de instabilidade, volume de debate e revisão — "
                        "sinal objetivo de onde o escopo ainda não estabilizou.",
            "valor": "Argumento baseado em dado, não em percepção, pra negociar prazo ou "
                     "pedir mais tempo de descoberta antes de travar o cronograma.",
        },
    ],
    "🌐 Conhecimento Organizacional": [
        {
            "tool": "pesquisar_multi_contexto",
            "cenario": "Um projeto novo levanta uma dúvida técnica que \"parece familiar\" — "
                       "provavelmente já foi discutida em outro cliente/projeto, mas ninguém "
                       "lembra qual.",
            "pergunta": "Algum outro contexto já discutiu integração com Core Banking?",
            "resposta": "Busca em todas as reuniões de todos os contextos do domínio, agrupada "
                        "por projeto — não só o contexto ativo no momento.",
            "valor": "Reaproveita conhecimento organizacional já pago (discutido, decidido) "
                     "em vez de redescobrir a mesma coisa do zero em cada cliente novo.",
        },
        {
            "tool": "promover_ativo_negocio",
            "cenario": "Uma análise valiosa foi gerada numa conversa do chat — mas por padrão "
                       "ela some quando a conversa fecha, junto com o esforço de produzi-la.",
            "pergunta": "Promova essa análise de tendências a Ativo de Negócio, "
                        "interesse tático, área de TI.",
            "resposta": "O conteúdo é persistido de verdade e passa a aparecer na Central de "
                        "Ativos de Negócio — visível em qualquer contexto que precisar dele.",
            "valor": "Transforma trabalho de análise pontual (que hoje se perde) em ativo "
                     "reutilizável da organização, com classificação e rastreabilidade formais.",
        },
        {
            "tool": "sugerir_processos",
            "cenario": "Um novo cliente descreve um processo de negócio parecido com algo que "
                       "já foi modelado antes — mas achar isso manualmente exigiria vasculhar "
                       "diagramas antigos.",
            "pergunta": "Esse processo de aprovação de crédito se parece com algum outro "
                        "já modelado no projeto?",
            "resposta": "Sugestão de processos BPMN já existentes com padrão semelhante, "
                        "como ponto de partida em vez de modelar do zero.",
            "valor": "Acelera modelagem reaproveitando trabalho já validado, e aumenta a "
                     "consistência entre processos parecidos no mesmo projeto.",
        },
    ],
}


def _scenario_card_html(s: dict) -> str:
    tool_badge = f'<span class="uc-tool">{s["tool"]}</span>' if s.get("tool") else ""
    return f"""
    <div class="uc-card">
      <div class="uc-row">
        <div class="uc-label">Cenário</div>
        <div class="uc-text">{s['cenario']}</div>
      </div>
      <div class="uc-row">
        <div class="uc-label">Pergunta no chat</div>
        <div class="uc-prompt">"{s['pergunta']}"</div>
      </div>
      <div class="uc-row">
        <div class="uc-label">O que o Assistente entrega</div>
        <div class="uc-text">{s['resposta']}</div>
      </div>
      <div class="uc-row uc-value">
        <div class="uc-label">💰 Valor de negócio</div>
        <div class="uc-text uc-value-text">{s['valor']}</div>
      </div>
      {tool_badge}
    </div>"""


_CSS = """
<style>
.uc-section-hdr {
    display: flex; align-items: center; gap: .6rem;
    font-size: .78rem; font-weight: 700; color: #6A7E98;
    letter-spacing: .10em; text-transform: uppercase;
    margin: 1.6rem 0 .9rem;
}
.uc-section-hdr::after {
    content: ""; flex: 1; height: 1px;
    background: linear-gradient(90deg, #1e3a55 0%, transparent 100%);
}
.uc-card {
    background: #080F1E;
    border: 1px solid #1A2E48;
    border-left: 4px solid #C97B1A;
    border-radius: 10px;
    padding: 1.1rem 1.3rem 1rem;
    margin-bottom: 1.1rem;
}
.uc-row { margin-bottom: .7rem; }
.uc-label {
    font-size: .64rem; font-weight: 700; color: #4A6A8A;
    letter-spacing: .09em; text-transform: uppercase;
    margin-bottom: .25rem;
}
.uc-text { font-size: .86rem; color: #C4D0E2; line-height: 1.6; }
.uc-prompt {
    display: inline-block;
    background: #0A1A32;
    border: 1px solid #C97B1A55;
    border-radius: 6px;
    padding: .4rem .8rem;
    font-size: .84rem; color: #E8B84B;
    font-style: italic;
}
.uc-value {
    background: #0A1F14;
    border-radius: 8px;
    padding: .6rem .8rem;
    margin-top: .9rem;
    margin-bottom: 0;
}
.uc-value .uc-label { color: #4ADE80; }
.uc-value-text { color: #D4E8DC; }
.uc-tool {
    display: inline-block; margin-top: .8rem;
    font-family: 'Courier New', monospace;
    font-size: .68rem; color: #6A7E98;
    background: #0D1B30; border: 1px solid #1A2E48;
    border-radius: 4px; padding: .15rem .5rem;
}
</style>
"""

st.markdown(_CSS, unsafe_allow_html=True)

# ── Export HTML autocontido (mesma fonte de dados) ───────────────────────────
def _build_standalone_html() -> str:
    sections_html = ""
    for name, scenarios in _SCENARIOS.items():
        cards = "".join(_scenario_card_html(s) for s in scenarios)
        sections_html += f'<div class="uc-section-hdr">{name}</div>{cards}'

    return f"""<!doctype html>
<html lang="pt-BR"><head>
<meta charset="utf-8">
<title>Casos de Uso — Process2Diagram</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{
      background: #060E1C; color: #C4D0E2;
      font-family: -apple-system, "Segoe UI", Roboto, sans-serif;
      max-width: 900px; margin: 0 auto; padding: 2.5rem 1.5rem 4rem;
  }}
  h1 {{ color: #F0F4FA; font-size: 1.8rem; margin-bottom: .3rem; }}
  .uc-subtitle {{ color: #8FA2BE; font-size: .95rem; margin-bottom: .5rem; }}
  .uc-footer {{ color: #4A6A8A; font-size: .78rem; margin-top: 3rem; text-align: center; }}
  {_CSS.replace("<style>", "").replace("</style>", "")}
</style>
</head><body>
<h1>💼 Casos de Uso — Valor de Negócio</h1>
<div class="uc-subtitle">
  Cenários reais de uso do Assistente do Process2Diagram: a pergunta, o que ele entrega,
  e o ganho concreto para o negócio.
</div>
{sections_html}
<div class="uc-footer">Gerado em {date.today().strftime('%d/%m/%Y')} · Process2Diagram</div>
</body></html>"""


st.markdown(
    """
Cada card abaixo parte de uma situação real de negócio — não de um recurso técnico.
A pergunta é literal: pode copiar e colar direto no **Assistente** (menu **Análise → 💬 Assistente**).
"""
)

_intro_spacer, _dl_btn = st.columns([5, 1])
with _dl_btn:
    st.download_button(
        "⬇️ Exportar HTML",
        data=_build_standalone_html().encode("utf-8"),
        file_name=f"casos_de_uso_p2d_{date.today().isoformat()}.html",
        mime="text/html",
        key="dl_casos_uso_html",
    )

st.markdown("---")

_tab_names = list(_SCENARIOS.keys())
_tabs = st.tabs(_tab_names)
for _tab, _name in zip(_tabs, _tab_names):
    with _tab:
        st.markdown(f'<div class="uc-section-hdr">{_name}</div>', unsafe_allow_html=True)
        for _s in _SCENARIOS[_name]:
            st.markdown(_scenario_card_html(_s), unsafe_allow_html=True)
