# Business Meeting Intelligence

## Nossa visão:
Nossa solução process2diagram deve estar o mais alinhada possível com as melhores práticas de mercado e acadêmicas.
O seu papel agora, Claude Code, é criar uma estratégia para alinhar ao máximo nossa solução a estes padrões.

Em uma pesquisa com o Chat GPT, ele nos forneceu estas informações relevantes abaixo. Leia, critique, pesquise mais a fundo e crie um plano para nós propondo um markdown com o plano na 
pasta de melhorias. Depois que eu analisar e fazer ajustes ao plano nós vamos implementar.

## Respoista do Chat GPT:


Não encontrei uma **especificação técnica única, reconhecida e consolidada**, que trate “Reuniões de Negócio” exatamente como você descreveu: uma estrutura formal para analisar fatos, papéis, perspectivas, confusões, semântica, contradições, decisões e extração de valor a partir da fala coletiva.

O que existe é um **conjunto de padrões, corpos de conhecimento, benchmarks e linhas acadêmicas** que, combinados, formam uma base muito sólida para construir essa especificação. Em outras palavras: **o campo existe em partes, mas ainda não parece existir como uma norma unificada de “Business Meeting Intelligence”**.

A melhor base técnica que encontrei seria uma composição destas camadas:

1. **Análise da fala e atos comunicativos**
2. **Análise de requisitos e entendimento de stakeholders**
3. **Modelagem de decisões, regras e processos**
4. **Mapeamento de questões, argumentos e controvérsias**
5. **Representação semântica em grafo**
6. **Extração de atas, decisões, tarefas e resumos orientados a valor**

---



## 1. O padrão mais próximo para “entender o que cada fala faz”: ISO 24617-2

O padrão mais diretamente relacionado à análise semântica de diálogos é o **ISO 24617-2**, voltado à anotação de atos de diálogo. Ele define conceitos para anotar segmentos de diálogo, uma linguagem formal chamada **DiAML** e um método para segmentar diálogos em unidades semânticas. Isso permite classificar contribuições como pergunta, resposta, confirmação, discordância, feedback, compromisso, pedido, sugestão etc. ([ISO][1])

Para o seu caso, isso é muito importante porque uma reunião não é apenas “texto transcrito”. Cada fala tem uma **função pragmática**:

| Fala na reunião                          | Interpretação técnica possível              |
| ---------------------------------------- | ------------------------------------------- |
| “Acho que isso não vai funcionar”        | objeção / avaliação negativa                |
| “Então ficou combinado que…”             | decisão / consolidação                      |
| “Quem cuida disso?”                      | abertura de item de ação                    |
| “Mas na reunião passada era diferente”   | possível conflito / contradição             |
| “Na prática o usuário faz outro caminho” | evidência operacional / exceção de processo |

A ISO 24617-2 não resolve sozinha a análise de negócio, mas é uma excelente camada para classificar o **ato comunicativo** de cada trecho da fala.

---

## 2. O corpo de conhecimento mais próximo para “extrair entendimento de negócio”: BABOK / IIBA

Do lado de análise de negócios, o **BABOK Guide**, do IIBA, é uma referência reconhecida. Ele organiza a prática de análise de negócios em áreas como **Elicitação e Colaboração**, **Gerenciamento do Ciclo de Vida dos Requisitos**, **Análise Estratégica**, **Análise de Requisitos e Definição de Design**, entre outras. ([IIBA][2])

A área de **Elicitation and Collaboration** descreve atividades como preparar elicitação, conduzir elicitação, confirmar resultados, comunicar informações de análise de negócios e gerenciar colaboração com stakeholders. ([IIBA][3])

Isso casa fortemente com a sua ideia, porque reuniões de negócio frequentemente são sessões de elicitação informal. Só que, na prática, elas vêm cheias de ruído: opiniões, mal-entendidos, memórias divergentes, interesses distintos, prioridades conflitantes e decisões implícitas.

O BABOK ajuda a responder: **o que deve ser extraído da reunião do ponto de vista de análise de negócio?**

Exemplos:

* necessidades de stakeholders;
* requisitos funcionais e não funcionais;
* restrições;
* premissas;
* riscos;
* decisões;
* regras de negócio;
* conflitos;
* pendências;
* lacunas de entendimento;
* dependências;
* impactos organizacionais.

---

## 3. Para requisitos formais: ISO/IEC/IEEE 29148

O padrão **ISO/IEC/IEEE 29148:2018** é uma referência forte para engenharia de requisitos. Ele trata dos processos e produtos relacionados a requisitos ao longo do ciclo de vida de sistemas e software, define características de bons requisitos e discute a aplicação iterativa dos processos de requisitos. ([IEEE Standards Association][4])

Esse padrão é relevante porque uma reunião pode gerar afirmações vagas como:

> “O sistema precisa ser mais rápido.”

Mas uma análise técnica deveria transformar isso em algo como:

> “O sistema deve retornar a consulta de documentos em até 3 segundos para 95% das requisições em horário comercial.”

Ou, quando não for possível formalizar:

> “Requisito candidato identificado, mas ainda ambíguo. Requer esclarecimento sobre métrica de desempenho, volume esperado e cenário de uso.”

Então, para um agente especializado, a ISO/IEC/IEEE 29148 pode servir como base para avaliar se uma fala virou um **bom requisito**, um requisito incompleto, uma premissa, uma regra, uma restrição ou apenas uma intenção genérica.

---

## 4. Para decisões, regras e processos: OMG BPMN, DMN, SBVR, BMM e CMMN

Aqui entra uma família muito útil da OMG.

O **BPMN** é o padrão de fato para diagramas de processos de negócio, voltado a stakeholders que desenham, gerenciam e realizam processos, mas com precisão suficiente para tradução em componentes de software. ([OMG][5])

O **DMN** é uma linguagem para especificação precisa de decisões de negócio e regras de decisão. Ele foi criado para ser compreensível por pessoas de negócio, analistas e desenvolvedores envolvidos em decisões automatizáveis. ([OMG][6])

O **CMMN** define uma notação e metamodelo para modelagem de casos, útil quando o trabalho é menos previsível, mais orientado a conhecimento e menos linear que um processo BPMN tradicional. ([OMG][7])

O **BMM**, Business Motivation Model, fornece uma estrutura para desenvolver, comunicar e gerenciar planos de negócio, incluindo elementos de motivação, objetivos, estratégias e fatores que influenciam planos empresariais. ([OMG][8])

Essas especificações não analisam reuniões diretamente, mas são excelentes **destinos estruturados** para aquilo que uma reunião produz:

| Conteúdo extraído da reunião         | Especificação de destino |
| ------------------------------------ | ------------------------ |
| Fluxo operacional                    | BPMN                     |
| Decisão de negócio                   | DMN                      |
| Regra de negócio                     | SBVR / DMN               |
| Caso flexível ou exceção operacional | CMMN                     |
| Objetivo, motivação, estratégia      | BMM                      |
| Requisito                            | ISO/IEC/IEEE 29148       |
| Entendimento de stakeholder          | BABOK                    |

---

## 5. Para mapear confusão, divergência e argumentação: IBIS e Dialogue Mapping

Uma descoberta especialmente relevante é o **IBIS — Issue-Based Information System**. Ele é uma abordagem baseada em argumentação para estruturar problemas complexos e mal definidos, envolvendo múltiplos stakeholders. A notação trabalha com questões, posições/ideias e argumentos pró ou contra. ([Wikipedia][9])

Isso é muito próximo da sua formulação: “o caos da fala conjunta e entendimentos/confusões oriundos de variadas perspectivas”.

Em uma reunião real, muitas vezes o valor não está apenas na decisão final, mas no mapa de tensões:

* Qual era a questão em disputa?
* Quais alternativas foram colocadas?
* Quem defendeu cada alternativa?
* Quais argumentos apareceram?
* Quais objeções não foram resolvidas?
* Qual decisão foi tomada mesmo com ressalvas?
* Que premissas sustentaram essa decisão?

IBIS e Dialogue Mapping seriam ótimos para transformar uma reunião em uma estrutura como:

```text
Questão: Como deve ser feita a triagem dos documentos?

Alternativa A: Triagem manual pela equipe
  Prós: mais controle, menor risco inicial
  Contras: alto esforço, gargalo operacional

Alternativa B: Triagem automática com IA
  Prós: escala, rapidez, rastreabilidade
  Contras: precisa auditoria, risco de erro em classes raras

Decisão provisória:
  Usar IA com auditoria humana por amostragem.
```

Essa camada é diferente de BPMN/DMN. Ela captura o **raciocínio social e argumentativo** que levou a um artefato de negócio.

---

## 6. Para benchmarks de reuniões: AMI, ICSI/MRDA, QMSum e pesquisas recentes

Há datasets e benchmarks importantes para reunião como objeto de pesquisa.

O **AMI Meeting Corpus** contém cerca de 100 horas de gravações de reuniões multimodais, com parte dos dados baseada em cenários de equipes com papéis em um projeto de design e parte composta por reuniões reais de diferentes domínios. ([Informatics Group Pages][10])

O **MRDA Corpus**, baseado no ICSI Meeting Corpus, contém mais de 180 mil tags de atos de diálogo anotadas manualmente em aproximadamente 72 horas de fala de 75 reuniões naturais. ([ResearchGate][11])

O **QMSum** é um benchmark de sumarização de reuniões orientada por consulta, com 1.808 pares pergunta-resumo sobre 232 reuniões em múltiplos domínios. Ele foi criado justamente porque uma única ata curta raramente atende a todos os tipos de usuários interessados em uma reunião longa e multiassunto. ([ACL Anthology][12])

Também encontrei pesquisa recente sobre **Conversation Analysis na era dos LLMs**, apontando que a área ainda é fragmentada e que boa parte dos trabalhos se concentra em elementos superficiais da conversa, enquanto tarefas mais sofisticadas — causalidade, estratégia, atribuição e valor de negócio — ainda estão em amadurecimento. ([arXiv][13])

Isso reforça a oportunidade: há pesquisa em meeting summarization, dialogue acts e extraction, mas ainda existe espaço para uma camada de **Business Meeting Intelligence** mais orientada a artefatos de negócio.

---

## 7. Para representar o conhecimento extraído: RDF, OWL e grafos semânticos

Para guardar a reunião analisada como uma rede de fatos, falas, decisões, pessoas, papéis, requisitos e contradições, os padrões do W3C são muito relevantes.

O **RDF** é um modelo padrão de intercâmbio de dados na Web baseado em grafos, útil para combinar informações mesmo quando os esquemas de origem são diferentes. ([W3C][14])

O **OWL** é uma linguagem de ontologias da Web Semântica projetada para representar conhecimento complexo sobre coisas, grupos de coisas e relações entre elas, permitindo inclusive verificação de consistência e inferência de conhecimento implícito. ([W3C][15])

Para o seu caso, isso permitiria criar um grafo como:

```text
Pessoa A --afirmou--> Fato 1
Pessoa B --discordou_de--> Fato 1
Fato 1 --gera--> Requisito Candidato 3
Requisito Candidato 3 --conflita_com--> Regra de Negócio 7
Decisão 2 --resolve_parcialmente--> Questão 5
Ação 4 --responsável--> Pessoa C
Ação 4 --prazo--> Data X
```

Essa abordagem é muito mais rica do que gerar apenas uma ata textual.

---

# Minha síntese: existe uma “quase especificação” distribuída

A resposta mais precisa seria:

> Não existe, aparentemente, uma especificação técnica única e reconhecida chamada algo como “Business Meeting Semantic Analysis Specification”. Mas existem padrões reconhecidos suficientes para construir uma especificação robusta e defensável.

Eu estruturaria uma especificação própria em camadas:

## Camada 1 — Registro bruto da reunião

Entradas:

* áudio;
* vídeo, se houver;
* transcrição;
* identificação de falantes;
* timestamps;
* documentos compartilhados;
* chat;
* pauta;
* participantes.

## Camada 2 — Segmentação comunicativa

Base provável:

* ISO 24617-2;
* dialogue acts;
* turn-taking;
* perguntas, respostas, objeções, confirmações, decisões, sugestões.

Saída:

```json
{
  "speaker": "Participante A",
  "utterance": "Acho que esse fluxo não cobre exceções de matrícula trancada.",
  "dialogue_act": ["objection", "risk_identification"],
  "target": "fluxo proposto de matrícula",
  "confidence": 0.84
}
```

## Camada 3 — Extração de elementos de negócio

Base provável:

* BABOK;
* ISO/IEC/IEEE 29148;
* análise de requisitos;
* análise de stakeholders.

Entidades extraídas:

* requisito;
* regra;
* restrição;
* exceção;
* problema;
* oportunidade;
* risco;
* premissa;
* dependência;
* decisão;
* pendência;
* responsável;
* stakeholder;
* dor operacional.

## Camada 4 — Modelagem de raciocínio e controvérsia

Base provável:

* IBIS;
* argumentation schemes;
* dialogue mapping.

Objetivo:

* mapear questões abertas;
* alternativas;
* argumentos;
* discordâncias;
* decisões;
* pontos sem consenso;
* contradições entre reuniões.

## Camada 5 — Transformação em artefatos formais

Base provável:

* BPMN para processos;
* DMN para decisões;
* SBVR/DMN para regras;
* BMM para objetivos e motivadores;
* CMMN para casos flexíveis;
* ISO/IEC/IEEE 29148 para requisitos.

## Camada 6 — Grafo de conhecimento e rastreabilidade

Base provável:

* RDF;
* OWL;
* PROV-O;
* ontologia própria de reuniões.

Objetivo:

* saber quem disse o quê;
* de onde veio cada requisito;
* qual fala sustenta cada decisão;
* quais conflitos existem;
* quais decisões mudaram ao longo do tempo;
* quais pontos ainda dependem de confirmação.

---

# Nome possível para essa especificação

Para o seu projeto, eu sugeriria criar internamente algo como:

**Business Meeting Intelligence Framework — BMIF**

Ou, mais alinhado ao RawToInsights AI:

**RawToInsights Meeting Semantics Framework**

Com módulos:

1. **Meeting Capture Model**
2. **Dialogue Act Layer**
3. **Business Entity Extraction Layer**
4. **Argumentation & Conflict Layer**
5. **Decision & Requirement Layer**
6. **Artifact Generation Layer**
7. **Traceability & Provenance Layer**
8. **Knowledge Graph Layer**

---

## Minha avaliação final

A lacuna que você está enxergando é real e promissora.

Hoje existem ferramentas que fazem:

* transcrição;
* resumo;
* ata;
* action items;
* sentiment analysis;
* extração simples de decisões.

Mas a visão mais sofisticada seria:

> transformar uma reunião em uma estrutura semântica auditável, rastreável e reutilizável, capaz de gerar requisitos, decisões, regras, processos, riscos, contradições, responsabilidades e conhecimento organizacional.

Isso seria muito mais valioso do que “resumir reunião”. Seria uma espécie de **engenharia reversa do entendimento coletivo**.

A base técnica mais forte para começar seria:

**ISO 24617-2 + BABOK + ISO/IEC/IEEE 29148 + BPMN/DMN/SBVR/BMM/CMMN + IBIS + RDF/OWL.**

[1]: https://www.iso.org/standard/51967.html?utm_source=chatgpt.com "ISO 24617-2:2012 - Language resource management"
[2]: https://www.iiba.org/knowledgehub/business-analysis-body-of-knowledge-babok-guide/?utm_source=chatgpt.com "A Guide to the Business Analysis Body of Knowledge®"
[3]: https://www.iiba.org/knowledgehub/business-analysis-body-of-knowledge-babok-guide/4-elicitation-and-collaboration/?utm_source=chatgpt.com "4.0 Introduction | BABOK® Guide"
[4]: https://standards.ieee.org/standard/29148-2018.html?utm_source=chatgpt.com "IEEE SA - IEEE/ISO/IEC 29148-2018"
[5]: https://www.omg.org/spec/BPMN/2.0.2/About-BPMN?utm_source=chatgpt.com "BPMN™ — Business Process Model and Notation"
[6]: https://www.omg.org/dmn/?utm_source=chatgpt.com "Decision Model and Notation™ (DMN™)"
[7]: https://www.omg.org/cmmn/?utm_source=chatgpt.com "Case Management Model and Notation™ (CMMN™)"
[8]: https://www.omg.org/spec/BMM/1.3/About-BMM?utm_source=chatgpt.com "About the Business Motivation Model Specification Version ..."
[9]: https://en.wikipedia.org/wiki/Issue-based_information_system?utm_source=chatgpt.com "Issue-based information system"
[10]: https://groups.inf.ed.ac.uk/ami/corpus/?utm_source=chatgpt.com "AMI Corpus"
[11]: https://www.researchgate.net/publication/2904172_The_ICSI_meeting_recorder_dialogue_act_MRDA_corpus?utm_source=chatgpt.com "The ICSI meeting recorder dialogue act (MRDA) corpus"
[12]: https://aclanthology.org/2021.naacl-main.472/?utm_source=chatgpt.com "A New Benchmark for Query-based Multi-domain Meeting ..."
[13]: https://arxiv.org/abs/2409.14195?utm_source=chatgpt.com "The Imperative of Conversation Analysis in the Era of LLMs: A Survey of Tasks, Techniques, and Trends"
[14]: https://www.w3.org/RDF/?utm_source=chatgpt.com "RDF - Semantic Web Standards"
[15]: https://www.w3.org/OWL/?utm_source=chatgpt.com "OWL - Semantic Web Standards"
