---
version: 1.0
agent: context_template
description: Template editável pelo usuário para o CKF (Context Knowledge File) do projeto
---

# Context Knowledge File (CKF)
# ─────────────────────────────────────────────────────────────────────────────
# Este arquivo é injetado no prompt de todos os agentes como contexto adicional.
# Edite as seções abaixo com informações específicas deste contexto/projeto.
# Seções não preenchidas podem ser deixadas em branco — o agente as ignorará.
# ─────────────────────────────────────────────────────────────────────────────

## Visão Geral do Contexto

<!-- Descreva brevemente o escopo, objetivo e área de negócio deste contexto. -->
<!-- Exemplo: "Projeto de digitalização dos processos de RH da empresa XYZ.
     Foco em onboarding, folha de pagamento e avaliação de desempenho." -->


## Participantes Frequentes

<!-- Liste os participantes habituais e seus papéis para melhorar a atribuição
     de falas e o agrupamento em raias (lanes) do BPMN. -->
<!-- Formato: "Nome Completo — Cargo / Departamento" -->


## Glossário e Termos Técnicos

<!-- Defina termos, acrônimos e jargões específicos deste contexto para que os
     agentes os interpretem corretamente. -->
<!-- Formato: "SIGLA: significado completo" ou "Termo: definição curta" -->


## Processos de Negócio Conhecidos

<!-- Descreva os processos principais já mapeados ou relevantes neste contexto.
     Isso orienta o AgentBPMN na identificação de raias e atividades. -->


## Regras de Negócio Permanentes

<!-- Liste regras que se aplicam sempre neste contexto, independentemente da
     reunião. O AgentSBVR usará estas regras como base. -->


## Objetivos Estratégicos

<!-- Metas de médio/longo prazo deste contexto. Orientam o AgentBMM na
     extração de visão, missão e metas do BMM. -->


## Notas Adicionais para os Agentes

<!-- Instruções livres: formatos preferidos, convenções de nomenclatura,
     idioma obrigatório, restrições específicas, etc. -->
