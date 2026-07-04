# pages/Orientacoes_BpmnStudio.py
# ─────────────────────────────────────────────────────────────────────────────
# Guia de uso do BPMN Studio (PC116) — pages/BpmnStudio.py
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
    "🧩", "Guia — BPMN Studio",
    "Como gerar um diagrama BPMN 2.0 + Mermaid a partir de uma descrição de processo em "
    "texto livre, e como obter a descrição textual de um BPMN já existente.",
)

# ═════════════════════════════════════════════════════════════════════════════
# O que é
# ═════════════════════════════════════════════════════════════════════════════
st.markdown("## 🧭 O que é o BPMN Studio")
st.markdown(
    """
Até aqui, gerar um BPMN no P2D exigia processar a transcrição completa de uma
reunião pelo pipeline principal. O **BPMN Studio** (menu **Pipeline → 🏗️ BPMN
Studio**) abre um segundo caminho, independente de reunião: você **descreve o
processo em texto livre** e o sistema gera o diagrama diretamente — útil para
documentar processos que você já conhece bem, sem precisar gravar e transcrever
uma reunião só para isso.

A página tem duas abas:

- **🧩 Gerar** — descrição de processo → BPMN 2.0 + Mermaid, com opção de salvar
  (versionado, como qualquer outro processo do projeto) e vincular a uma reunião
  existente, se fizer sentido.
- **📖 Descrever** — caminho inverso: cole (ou envie) o XML de um BPMN e receba
  a descrição textual estruturada do processo — participantes, fluxo numerado
  passo a passo e resultados possíveis.
"""
)

st.markdown("---")

# ═════════════════════════════════════════════════════════════════════════════
# Passo a passo — Gerar
# ═════════════════════════════════════════════════════════════════════════════
st.markdown("## 🧩 Passo a passo — aba Gerar")

st.markdown(
    """
**1. Escreva a descrição do processo.** Não precisa ser uma transcrição — pode
ser um parágrafo direto descrevendo quem faz o quê, em que ordem, e o que
acontece nas decisões e exceções. Quanto mais específico, melhor o resultado
(veja as dicas abaixo e o exemplo completo mais adiante).

**2. Deixe marcada a opção "Detectar atores automaticamente".** Ela roda uma
análise leve de texto (sem custo de LLM) antes da geração, para nomear melhor
as lanes/organizações do diagrama.

**3. Clique em "Gerar BPMN".** Isso faz uma chamada real ao provedor de LLM
configurado (mesmo custo de uma execução normal do pipeline) — o resultado
aparece em duas abas: **Diagrama BPMN** (visualizador interativo) e **Mermaid**
(fluxograma alternativo).

**4. Revise e, se quiser, salve.** Você pode ajustar o nome do processo,
vincular a reunião existente do projeto (opcional — não é obrigatório) e
escolher salvar como processo novo ou como nova versão de um processo já
existente. O processo salvo aparece normalmente no **Editor BPMN**, com
histórico de versões como qualquer outro.
"""
)

with st.expander("💡 Dicas para uma boa descrição", expanded=False):
    st.markdown(
        """
- **Nomeie os papéis/áreas envolvidos** (ex: "o Financeiro aprova", não "alguém aprova")
  — isso vira o nome das lanes no diagrama.
- **Se houver uma organização externa** (fornecedor, cliente, órgão público, parceiro),
  **cite o nome dela** — o sistema detecta automaticamente quando há 2+ organizações
  distintas e gera um diagrama de colaboração com pools separados, em vez de lanes
  dentro de um único pool.
- **Descreva as decisões explicitamente**: "se a documentação estiver incompleta,
  retorna para o solicitante" gera um gateway de decisão com os dois caminhos
  corretos — sem isso, o sistema pode gerar um fluxo linear simplificado demais.
- **Atividades em paralelo** ("enquanto X faz A, Y faz B") são reconhecidas e
  geram um gateway paralelo (fork/join) no diagrama.
- **Evite descrições curtas demais** (uma ou duas frases) — o resultado tende a
  ficar genérico. O exemplo completo abaixo é um bom parâmetro de tamanho/detalhe.
"""
    )

st.markdown("---")

# ═════════════════════════════════════════════════════════════════════════════
# Passo a passo — Descrever
# ═════════════════════════════════════════════════════════════════════════════
st.markdown("## 📖 Passo a passo — aba Descrever")
st.markdown(
    """
**1. Cole o XML de um BPMN 2.0** — pode ser de um processo já salvo neste
projeto (exportado pelo **Editor BPMN**) ou de qualquer outra origem — ou envie
um arquivo `.bpmn`/`.xml` diretamente.

**2. Clique em "Gerar descrição".** O sistema lê o XML (sem chamada a LLM —
é um parser determinístico) e monta um texto estruturado: participantes
(pools/lanes), fluxo numerado passo a passo com o tipo de cada elemento
(tarefa, decisão, gateway paralelo, evento...), e os resultados possíveis do
processo.

**3. Baixe o resultado** em Markdown (`.md`) pelo botão de download, se quiser
documentar o processo externamente.
"""
)

st.markdown("---")

# ═════════════════════════════════════════════════════════════════════════════
# Exemplo completo — processo complexo
# ═════════════════════════════════════════════════════════════════════════════
st.markdown("## 📋 Exemplo — descrição de processo complexo")
st.markdown(
    """
O exemplo abaixo é inspirado em processos reais de contratação de consultoria
(ver [exemplos de diagramas BPMN 2.0 — HEFLO](https://www.heflo.com/blog/examples-of-bpmn-2-0-diagrams))
e foi escrito de propósito para exercitar as capacidades mais avançadas do
BPMN Studio: **duas organizações distintas** (colaboração multi-pool), **duas
decisões com retorno de fluxo** (loop-back), e **atividades em paralelo**.
Copie o texto e cole na aba **Gerar** para testar.
"""
)

EXEMPLO_COMPLEXO = """A empresa Contratante identifica a necessidade de uma consultoria especializada em transformação digital e abre uma solicitação de contratação de serviço no sistema interno. O Departamento de Compras recebe a solicitação e elabora o termo de referência, encaminhando-o para fornecedores pré-qualificados, entre eles a consultoria TechAdvisor Ltda.

A TechAdvisor Ltda analisa o termo de referência e envia uma proposta técnica e comercial. O Departamento de Compras recebe as propostas e realiza a análise comparativa. Se a proposta da TechAdvisor Ltda for aprovada, o Departamento Jurídico da Contratante elabora o contrato e o envia para assinatura da TechAdvisor Ltda. Se nenhuma proposta for aprovada, o processo retorna ao Departamento de Compras para reabertura da concorrência.

Após a assinatura do contrato pela TechAdvisor Ltda, o Gerente do Projeto na Contratante e o Consultor Responsável na TechAdvisor Ltda realizam, em paralelo, a definição do escopo detalhado do projeto e o planejamento do cronograma de entregas. Concluídas as duas atividades, a TechAdvisor Ltda inicia a execução da consultoria, entregando relatórios parciais mensalmente.

A cada entrega, o Gerente do Projeto valida o relatório recebido. Se o relatório estiver incompleto ou não atender aos critérios definidos no contrato, ele é devolvido à TechAdvisor Ltda para correção. Se o relatório for aprovado, o Financeiro da Contratante processa o pagamento da parcela correspondente e notifica a TechAdvisor Ltda.

Ao final do contrato, o Gerente do Projeto realiza a avaliação final do fornecedor e encerra o processo, arquivando toda a documentação no sistema de gestão de contratos."""

st.text_area(
    "Descrição de exemplo (copie e cole na aba Gerar do BPMN Studio)",
    value=EXEMPLO_COMPLEXO,
    height=280,
    key="orient_bpmns_example",
    label_visibility="collapsed",
)
copy_button(EXEMPLO_COMPLEXO, key="orient_bpmns_example", label="📋 Copiar exemplo")

st.markdown(
    """
**O que esperar do resultado:** duas pools separadas — **Contratante**
(com lanes Departamento de Compras, Departamento Jurídico, Gerente do Projeto e
Financeiro) e **TechAdvisor Ltda** — conectadas por mensagens entre as
organizações; dois gateways de decisão exclusiva com retorno de fluxo
(reabertura de concorrência e devolução de relatório); e um gateway paralelo
para definição de escopo + planejamento de cronograma.
"""
)

st.markdown("---")
st.page_link("pages/BpmnStudio.py", label="→ Ir para o BPMN Studio", icon="🏗️")
