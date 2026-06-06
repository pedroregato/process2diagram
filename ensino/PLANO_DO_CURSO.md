# Curso Process2Diagram — Aplicações Corporativas

> Como resolver problemas reais do mundo corporativo com o Process2Diagram.

---

## Sobre o Curso

Este curso ensina analistas, gestores e equipes de TI a usar o Process2Diagram para
resolver problemas concretos: documentar processos, rastrear requisitos, preparar
auditorias, preservar conhecimento e medir o retorno das reuniões.

Cada módulo parte de um **problema real** → mostra **como o P2D resolve** →
entrega um **artefato concreto** que o participante pode usar no trabalho imediatamente.

As transcrições de exemplo neste curso são ficcionais, mas baseadas em situações
corporativas reais. Use-as diretamente no pipeline do P2D para ver os artefatos
sendo gerados.

---

## Público-Alvo

| Perfil | Módulos prioritários |
|---|---|
| Analista de Negócios / BA | 1, 2, 6 |
| Gerente de Projetos / PM | 2, 5 |
| Analista de Processos | 1, 3 |
| Compliance / Auditoria | 3 |
| Gestão do Conhecimento | 4 |
| Liderança / C-Level | 5, 6 |
| TI / Desenvolvimento | 0, 2 |

---

## Estrutura do Curso

| Módulo | Tema | Duração sugerida |
|---|---|---|
| **0 — Fundamentos** | Configuração e primeiros passos | 1h |
| **1 — Mapeamento de Processos** | BPMN sem consultor | 3h |
| **2 — Rastreabilidade de Requisitos** | De reunião a IEEE 830 | 2h |
| **3 — Auditoria e Compliance** | Evidências e regras de negócio | 2h |
| **4 — Gestão do Conhecimento** | Preservar o saber institucional | 2h |
| **5 — Governança e ROI** | Medir o retorno das reuniões | 2h |
| **6 — Análise Estratégica** | BMM, IBIS e alinhamento estratégico | 2h |

**Total:** ~14h (workshop de 2 dias ou trilha de 6 semanas)

---

## Módulo 0 — Fundamentos (1h)

**Objetivo:** Dominar a interface e entender o que o pipeline faz em cada etapa.

### Conteúdo
1. O problema: reuniões acontecem, documentação não
2. Visão geral do pipeline: Quality → Preprocessor → NLP → BPMN → Requisitos → SBVR → BMM → Synthesizer
3. Configuração inicial: provider LLM, API key, projeto Supabase
4. O que é uma boa transcrição? Como interpretar o Grau A–E
5. Hands-on: rodar a transcrição de exemplo do Módulo 1

### Resultado esperado
Participante sabe configurar o sistema, entende o significado de cada artefato
e consegue rodar um pipeline completo.

---

## Módulo 1 — Mapeamento de Processos sem Consultor (3h)

**Problema corporativo:** A empresa precisa documentar processos para certificação
(ISO, SOC 2, LGPD) mas não tem analista de processos disponível ou o custo de
consultoria é proibitivo.

### Cenários

**Cenário 1A — Aprovação de Fornecedor** (`transcricao_01a_aprovacao_fornecedor.txt`)
Reunião de levantamento do processo de homologação de fornecedores com três áreas:
Compras, Financeiro e Jurídico. O P2D gera BPMN com três lanes, gateways XOR para
valor do contrato e execução paralela das análises financeira e jurídica.

**Cenário 1B — Aprovação de Crédito** (`transcricao_01b_aprovacao_credito.txt`)
Mapeamento do processo de concessão de crédito em uma financeira. Gateways XOR
para faixas de valor e score de risco. Exercício de validação automática (Check 7 e Pass 5).

**Cenário 1C — Onboarding de Funcionário** (`transcricao_01c_onboarding_funcionario.txt`)
Processo de integração de novos colaboradores envolvendo RH, TI e Facilities.
Exercício de colaboração com message flows entre departamentos.

### Artefato entregue
BPMN 2.0 XML pronto para importar no Bizagi, Camunda ou Signavio.

### Discussão
- Quantos gateways o LLM gerou? Fazem sentido?
- As lanes refletem os departamentos corretos?
- O diagrama de Mermaid confirma a estrutura do BPMN?

---

## Módulo 2 — Rastreabilidade de Requisitos em Projetos de TI (2h)

**Problema corporativo:** O time de TI implementou funcionalidades que ninguém pediu
e não consegue mostrar a origem de cada requisito quando o cliente questiona o escopo.

### Cenário — Kick-off do Portal do Cliente (`transcricao_02_kickoff_portal_cliente.txt`)
Reunião de abertura de projeto de portal de autoatendimento. O P2D gera requisitos
IEEE 830 com citação direta das falas dos participantes, mind map interativo e
rastreabilidade por responsável.

### Exercícios
1. Rodar o pipeline e verificar os requisitos gerados na aba Requisitos
2. Usar o Assistente RAG para responder: "Quem aprovou o requisito de autenticação biométrica?"
3. Exportar a planilha de rastreabilidade e revisar com o grupo

### Artefato entregue
Lista de requisitos com origem, responsável e data — pronta para o backlog.

---

## Módulo 3 — Auditoria e Compliance (2h)

**Problema corporativo:** A auditoria interna exige evidências de que decisões foram
tomadas e documentadas. Reconstituir isso de e-mails e chats leva semanas.

### Cenário — Comitê de Aprovação de Contratos (`transcricao_03_comite_contratos.txt`)
Reunião do comitê executivo de aprovação de contratos com foco em compliance e LGPD.
O P2D gera ata formal, regras SBVR e requisitos de conformidade.

### Exercícios
1. Comparar a ata gerada automaticamente com o que seria feito manualmente
2. Identificar as regras SBVR extraídas e validá-las com um especialista jurídico
3. Usar a aba de Contradições para simular dois comitês com decisões conflitantes

### Artefato entregue
Dossiê de auditoria: ata em PDF + vocabulário SBVR + rastreabilidade de decisões.

---

## Módulo 4 — Gestão do Conhecimento e Onboarding (2h)

**Problema corporativo:** Quando um especialista sai da empresa, o conhecimento vai
junto. Novos colaboradores levam meses para entender como as coisas funcionam.

### Cenário — Captura de Conhecimento de Especialista (`transcricao_04_captura_conhecimento.txt`)
Sessão de entrevista com especialista prestes a se aposentar, detalhando o processo
de integração entre o ERP legado e o novo CRM. O P2D estrutura o conhecimento em
BPMN, requisitos e vocabulário técnico (SBVR).

### Exercícios
1. Gerar o BPMN e verificar se o especialista reconhece o fluxo
2. Usar o Assistente RAG após indexar a reunião para simular perguntas de um novo funcionário
3. Explorar o Knowledge Graph com as entidades extraídas

### Artefato entregue
Base de conhecimento consultável + BPMN do processo legado.

---

## Módulo 5 — Governança de Projetos e ROI de Reuniões (2h)

**Problema corporativo:** A empresa investe horas de reunião sem saber se está
gerando valor. Gestores não conseguem medir o retorno das reuniões de planejamento.

### Cenário — Retrospectiva de Sprint com Métricas (`transcricao_05_retrospectiva_sprint.txt`)
Sprint review e planning com análise de métricas de qualidade e ROI. O P2D mede o
Decision Capital, Action Capital e Fulfillment Score da reunião.

### Exercícios
1. Abrir a aba ROI-TR e interpretar os indicadores
2. Usar o AgentCommunicationNoise para identificar compromissos vagos na transcrição
3. Comparar o ROI de diferentes tipos de reunião no mesmo projeto

### Artefato entregue
Dashboard de qualidade de reuniões + relatório de ROI em HTML.

---

## Módulo 6 — Análise Estratégica com BMM e IBIS (2h)

**Problema corporativo:** Reuniões de planejamento estratégico produzem slides
bonitos, mas os objetivos raramente são rastreados até as iniciativas operacionais.

### Cenário — Planejamento Estratégico Anual (`transcricao_06_planejamento_estrategico.txt`)
Reunião do comitê executivo para definição das diretrizes do próximo triênio.
O P2D extrai visão, missão, metas (BMM), argumentos e posições (IBIS) e conecta
as decisões estratégicas aos requisitos operacionais.

### Exercícios
1. Revisar o BMM gerado: visão, missão, metas e estratégias estão corretos?
2. Usar o Assistente para responder: "Qual decisão estratégica originou a meta de digitalização?"
3. Cruzar a transcrição do planejamento com um documento de política corporativa
   (aba Análise Cruzada no Gerenciador de Documentos)

### Artefato entregue
BMM documentado + mapa IBIS das principais decisões + relatório executivo HTML.

---

## Formatos de Entrega

| Formato | Duração | Configuração |
|---|---|---|
| **Workshop presencial intensivo** | 2 dias | Grupos de 4–6 pessoas, 1 laptop por grupo |
| **Curso online assíncrono** | 6 semanas (1 módulo/semana) | Acesso individual ao P2D |
| **Trilha corporativa in company** | 6 sessões de 2h | Times completos + gestores |

---

## Materiais por Módulo

Cada pasta de módulo contém:
- `guia.md` — instruções passo a passo, contexto do cenário e perguntas de discussão
- `transcricao_XX*.txt` — transcrição realista pronta para colar no pipeline do P2D

---

*Versão 1.0 — Process2Diagram v4.27*
