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

# ── Cabeçalho ─────────────────────────────────────────────────────────────────
st.markdown("# 📖 Como Iniciar")
st.caption("Guia de referência rápida — leia antes de usar o Process2Diagram pela primeira vez.")

st.markdown("---")

# ── O que é ───────────────────────────────────────────────────────────────────
st.markdown("## 🧭 O que é o Process2Diagram?")
st.markdown(
    """
**Process2Diagram** transforma transcrições de reuniões em artefatos profissionais de análise de processos,
usando um pipeline de múltiplos agentes LLM encadeados:

- 📐 **Diagrama BPMN 2.0** — fluxo de processo com pools, lanes e gateways
- 📊 **Fluxograma Mermaid** — visualização alternativa leve
- 📋 **Ata de Reunião** — participantes, decisões, itens de ação (Markdown / Word / PDF)
- 📝 **Requisitos** — extração IEEE 830 (funcional, não-funcional, regra de negócio...)
- 📖 **Vocabulário SBVR** — termos e regras de negócio formais
- 🎯 **BMM** — visão, missão, objetivos e estratégias
- 📄 **Relatório Executivo HTML** — síntese interativa de todos os artefatos
"""
)

st.markdown("---")

# ── Pré-requisitos ─────────────────────────────────────────────────────────────
st.markdown("## ✅ Pré-requisitos")

col1, col2 = st.columns(2)

with col1:
    st.markdown("### 🔑 API Key LLM (obrigatório)")
    st.markdown(
        """
Escolha **um** dos provedores e obtenha sua chave:

| Provedor | Onde obter | Custo |
|---|---|---|
| **DeepSeek** *(recomendado)* | platform.deepseek.com | Muito baixo |
| **Claude (Anthropic)** | console.anthropic.com | Médio |
| **OpenAI** | platform.openai.com/api-keys | Médio |
| **Groq (Llama)** | console.groq.com | Gratuito (limits) |
| **Google Gemini** | aistudio.google.com | Gratuito (limits) |

> 💡 Para começar sem custo: use **Groq** ou **Google Gemini** no tier gratuito.
"""
    )

with col2:
    st.markdown("### 🗄️ Supabase (opcional)")
    st.markdown(
        """
O Supabase é necessário para funcionalidades avançadas:

- 💬 **Assistente** — Q&A sobre reuniões passadas
- 📋 **Req. Tracker** — acompanhe requisitos ao longo do tempo
- 🔄 **Batch Runner** — processe e persista múltiplas transcrições
- 📈 **Histórico** — compare reuniões e detecte contradições em requisitos

**Sem Supabase:** o pipeline principal (BPMN, Ata, Requisitos, Relatório)
funciona 100% — os resultados ficam na sessão atual.

Para configurar: crie um projeto gratuito em **supabase.com** e adicione
`url` e `key` em *Settings → Secrets* no Streamlit Cloud.
"""
    )

st.markdown("---")

# ── Fluxo de trabalho ─────────────────────────────────────────────────────────
st.markdown("## 🚀 Primeiros passos — Pipeline Principal")

steps = [
    ("1️⃣", "Configure o provedor LLM",
     "Na sidebar esquerda, selecione o provedor (ex: DeepSeek) e insira sua API Key. "
     "A chave fica apenas na memória da sessão — nunca é gravada em disco."),
    ("2️⃣", "Cole ou faça upload da transcrição",
     "Na página **Processar Transcrição**, cole o texto diretamente no campo de texto "
     "ou faça upload de um arquivo **.txt**, **.docx** ou **.pdf**. "
     "O botão **Pré-processar** remove ruídos do ASR sem usar LLM — útil para revisar antes de processar."),
    ("3️⃣", "(Opcional) Selecione o projeto no Supabase",
     "Se o Supabase estiver configurado, escolha ou crie um projeto e informe o título e data da reunião. "
     "Os artefatos gerados serão salvos automaticamente ao final do pipeline."),
    ("4️⃣", "Escolha os agentes e clique em Gerar Insights",
     "Na sidebar, habilite/desabilite agentes conforme necessário. "
     "BPMN, Ata e Requisitos são os mais usados. SBVR, BMM e Relatório Executivo são opcionais. "
     "Clique em **🚀 Gerar Insights** para iniciar o processamento."),
    ("5️⃣", "Explore os resultados nas abas",
     "Os resultados aparecem nas abas abaixo do pipeline: BPMN 2.0, Mermaid, Ata, Requisitos, etc. "
     "Use **📊 Diagramas** (menu lateral) para visualização em tela cheia com pan/zoom."),
    ("6️⃣", "(Supabase) Gere embeddings e use o Assistente",
     "Após salvar reuniões, vá em **Assistente** → clique em **⚡ Gerar Embeddings** "
     "com uma chave do Google Gemini (gratuito) ou OpenAI. "
     "Em seguida, faça perguntas como 'Quais foram as decisões da Reunião 3?' ou "
     "'Liste todos os requisitos funcionais sobre autenticação.'"),
]

for icon, title, desc in steps:
    with st.expander(f"{icon} {title}", expanded=False):
        st.markdown(desc)

st.markdown("---")

# ── Páginas disponíveis ────────────────────────────────────────────────────────
st.markdown("## 📚 Páginas disponíveis")

pages_info = [
    ("🚀", "Processar Transcrição", "Pipeline",
     "Pipeline principal. Cole ou faça upload de uma transcrição e gere todos os artefatos."),
    ("📊", "Diagramas", "Pipeline",
     "Visualizador full-screen: BPMN 2.0 (bpmn-js), Mermaid (pan/zoom) e Mind Map de requisitos."),
    ("💬", "Assistente", "Análise & Dados",
     "Chat Q&A sobre todas as reuniões do projeto. Usa tool-use (LLM decide quais ferramentas chamar) "
     "ou RAG clássico (busca semântica por pgvector). Requer Supabase + embeddings gerados."),
    ("📋", "Req. Tracker", "Análise & Dados",
     "Quadro de acompanhamento de requisitos: status, contradições, exportação Excel/CSV. Requer Supabase."),
    ("🔄", "Batch Runner", "Operações",
     "Processa múltiplas transcrições em sequência. Útil para indexar reuniões passadas de uma vez."),
    ("🔧", "BPMN Backfill", "Operações",
     "Gera BPMN para reuniões já salvas no Supabase que ainda não têm diagrama."),
    ("📝", "Transcript Backfill", "Operações",
     "Salva transcrições para reuniões já no banco que têm ata mas não têm texto de transcrição."),
    ("💰", "Estimativa de Custo", "Operações",
     "Calcule o custo estimado de tokens antes de processar, por provedor e agente."),
]

for icon, name, section, desc in pages_info:
    col_ic, col_info = st.columns([1, 9])
    with col_ic:
        st.markdown(f"## {icon}")
    with col_info:
        st.markdown(f"**{name}** `{section}`")
        st.caption(desc)
    st.markdown("")

st.markdown("---")

# ── Configurações da sidebar ──────────────────────────────────────────────────
st.markdown("## ⚙️ Configurações da sidebar (Pipeline Principal)")

col_a, col_b = st.columns(2)

with col_a:
    st.markdown(
        """
**Agentes disponíveis**
- 🔬 **Qualidade da Transcrição** — grade A–E com critérios
- 📐 **BPMN** — diagrama de processo (core)
- 📋 **Ata de Reunião** — minutes completa
- 📝 **Requisitos** — extração IEEE 830
- 📖 **SBVR** — vocabulário e regras de negócio
- 🎯 **BMM** — modelo de motivação
- 📄 **Relatório Executivo** — síntese HTML

**Otimização BPMN**
- **1 pass** — execução única (padrão)
- **3 ou 5 passes** — torneio: melhor candidato selecionado por pontuação
- **Adaptive Retry (LangGraph)** — retenta até atingir nota mínima
"""
    )

with col_b:
    st.markdown(
        """
**Idioma de saída**
- Auto-detect — detecta o idioma da transcrição
- Português, Inglês, Espanhol, etc.

**Prefixo / Sufixo**
- Adicionados aos nomes dos arquivos exportados
- Ex: `ACME_` + `processo_v1` → `ACME_processo_2026-04-12.bpmn`

**Modo Desenvolvedor**
- Exibe aba *Dev Tools* com o KnowledgeHub JSON completo
- Útil para depurar o que cada agente produziu
"""
    )

st.markdown("---")

# ── Dicas de qualidade ────────────────────────────────────────────────────────
st.markdown("## 💡 Dicas para melhores resultados")

tips = [
    "**Transcrições mais longas e detalhadas** geram diagramas BPMN mais ricos. "
    "Procure incluir pelo menos os momentos de decisão e transições entre responsáveis.",

    "**Identifique os participantes** na transcrição com padrão `Nome: fala` ou `NOME: fala`. "
    "O agente de ata extrai participantes e o de BPMN usa os nomes para definir as lanes.",

    "**Pré-processe antes de processar** se a transcrição tiver ruídos de ASR "
    "(repetições, hesitações, palavras cortadas). O botão *Pré-processar* remove esses artefatos.",

    "**Use múltiplas passes BPMN** (3 ou 5) quando o diagrama gerado parecer incompleto "
    "ou com pouca granularidade — o torneio seleciona o melhor candidato.",

    "**O Assistente no modo tool-use** responde melhor a perguntas estruturadas "
    "('Quais são os participantes?', 'Liste as decisões') do que a perguntas abertas. "
    "Para buscas em texto de transcrição, ambos os modos funcionam bem.",

    "**Gere embeddings imediatamente** após salvar uma reunião enquanto a chave do "
    "Google Gemini está disponível — o processo demora alguns minutos por reunião "
    "por conta do rate limit do tier gratuito (1.2s entre chamadas).",
]

for i, tip in enumerate(tips, 1):
    st.markdown(f"**{i}.** {tip}")

st.markdown("---")
st.caption("Process2Diagram · Guia de Início Rápido")
