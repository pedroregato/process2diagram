# Business Meeting Intelligence Framework — Plano Estratégico P2D
**Versão:** 1.0 — Maio 2026
**Autoria:** Análise Claude Code sobre proposta ChatGPT + estado atual do sistema

---

## 1. Avaliação critica da analise do ChatGPT

A resposta do ChatGPT e academicamente solida, mas apresenta tres limitacoes importantes para o nosso contexto:

### 1.1 O que o ChatGPT nao sabe sobre o P2D

O ChatGPT partiu de uma tela em branco. O Process2Diagram **ja implementa** uma parcela significativa do framework que ele propoe:

| Camada sugerida | Equivalente no P2D | Status |
|---|---|---|
| Artifact Generation — BPMN | `AgentBPMN` + `bpmn_generator.py` + viewer/editor | Completo (OMG 2.0) |
| Artifact Generation — SBVR | `AgentSBVR` + `skill_sbvr.md` | Completo (OMG) |
| Artifact Generation — BMM | `AgentBMM` + `skill_bmm.md` | Completo (OMG) |
| Decision & Requirement Layer | `AgentRequirements` (IEEE 29148, 5 tipos) | Completo |
| Business Entity Extraction | `AgentKnowledgeExtractor` — kh_entities, kh_processes, kh_facts | Completo |
| Argumentation & Conflict | `AgentContradictionDetector` — kh_contradictions | Parcial (contradicoes, nao argumentacao) |
| Meeting type awareness | `classify_meeting_type()`, 11 tipos, TYPE_WEIGHTS | Unico no mercado |
| Quality scoring | `AgentTranscriptQuality`, `AgentValidator`, `MeetingROI` | Completo |
| Cross-meeting knowledge | `cross_meeting_analyzer`, Knowledge Hub persistente | Completo |
| Elicitation output (BABOK) | Decisoes, itens de acao, participantes em `AgentMinutes` | Parcial |

**Conclusao:** o P2D ja esta na Camada 3-5 do framework proposto. A maioria das lacunas reais esta nas Camadas 2 (Atos de Dialogo) e 4 (Argumentacao), e em um formato especifico da Camada 5 (DMN).

---

### 1.2 Criticas tecnicas as sugestoes do ChatGPT

**ISO 24617-2 (Atos de Dialogo)**
O padrao e correto como referencia, mas impraticavel na forma sugerida. A anotacao DiAML foi projetada para anotadores humanos especializados, nao para LLMs em pipeline. Anotar cada utterance individualmente multiplicaria o custo de tokens por 10-50x. A alternativa realista e uma classificacao simplificada por **segmento de fala** (paragrafo/trecho), nao por frase — cobrindo os atos de negocio mais valiosos: decisao, compromisso, objecao, pergunta aberta, risco identificado.

**RDF / OWL (Grafo Semantico)**
A proposta e tecnicamente interessante mas arquiteturalmente incompativel com o P2D. O Knowledge Hub ja prove rastreabilidade relacional via Supabase (`kh_facts.source_meeting_ids`, `requirements.cited_by`, `bpmn_processes`). Serializar isso em RDF/Turtle nao agrega valor pratico para o usuario corporativo — ele nao vai consultar SPARQL. O que agrega valor e uma **visualizacao interativa do grafo** sobre os dados ja existentes.

**CMMN (Case Management Model and Notation)**
Valido em sistemas de BPM dedicados. Irrelevante para analise de transcricoes — o conteudo de reunioes corporativas nao se presta naturalmente a notacao CMMN. Baixissima prioridade.

**IBIS / Dialogue Mapping**
Esta e a sugestao mais subvalorizada do ChatGPT. Capturar **por que** uma decisao foi tomada — as alternativas consideradas, os argumentos pro/contra, as objecoes nao resolvidas — e radicalmente mais valioso do que a ata da decisao em si. E a unica camada que nenhum produto de mercado entrega bem. Alta prioridade.

**DMN (Decision Model and Notation)**
A lacuna mais evidente do P2D. Extraimos decisoes como texto (`kh_facts.type=decision`, `MinutesModel.decisions`) mas nunca as formalizamos como tabelas de decisao DMN. E o complemento natural do BPMN ja implementado — mesma familia OMG, mesmo grau de formalismo.

---

## 2. Posicionamento competitivo atual

Ferramentas de mercado (Otter.ai, Fireflies, Grain, Fathom) entregam:
- Transcricao
- Resumo
- Action items
- Analise de sentimento basica

O P2D ja entrega tudo isso **mais**:
- BPMN 2.0 gerado automaticamente
- SBVR + BMM (vocabulario e motivacao de negocio)
- Requisitos IEEE 29148 com speaker attribution
- Knowledge Hub cross-meeting com deteccao de contradicoes
- Classificacao de tipo de reuniao + ROI-TR ponderado

**A lacuna real** esta em duas dimensoes ainda inexploradas pelo mercado:
1. A camada de *argumentacao* — o raciocinio que levou as decisoes
2. A formalizacao de *decisoes* como modelos DMN consultaveis

---

## 3. Plano estrategico — Fases priorizadas

### Criterios de priorizacao
- **Valor de negocio**: impacto direto no usuario corporativo
- **Diferencialidade**: ausente nos concorrentes
- **Esforco de implementacao**: semanas-homem estimadas na arquitetura atual
- **Coerencia arquitetural**: uso dos padroes ja implementados (BaseAgent, KnowledgeHub, Supabase)

---

### FASE A — DMN: Formalizacao de Decisoes (Alta prioridade)
**Referencia:** OMG Decision Model and Notation 1.4
**Esforco estimado:** medio (2-3 semanas)

**Racional:**
Decisoes sao o artefato mais valioso de uma reuniao executiva. Hoje o P2D as captura como texto livre em `MinutesModel.decisions` e como `kh_facts` do tipo `decision`. O passo natural e formaliza-las como **tabelas DMN** — o mesmo padrao OMG do BPMN ja implementado.

**O que implementar:**
- `AgentDMN` — extrai decisoes com condicoes de entrada, saida e regras de decisao
- `modules/dmn_generator.py` — gera XML DMN 1.4 a partir do modelo estruturado
- `modules/dmn_viewer.py` — renderizacao de tabela DMN no Streamlit (HTML/CSS puro, sem biblioteca externa)
- Novo tab `DMN` no Pipeline e em `pages/Diagramas.py`
- Export DMN XML no `export_tab.py`

**Estrutura do modelo:**
```
DMNModel:
  decisions: List[DMNDecision]
    - id: str
    - name: str                # nome da decisao
    - question: str            # pergunta que a decisao responde
    - inputs: List[DMNInput]   # condicoes de entrada (quem, quando, valor, tipo)
    - outputs: List[DMNOutput] # resultado da decisao
    - rules: List[DMNRule]     # linhas da tabela: input -> output
    - rationale: str           # contexto e justificativa (texto livre)
    - decided_by: List[str]    # participantes que tomaram a decisao
    - meeting_ref: str         # reuniao de origem
    - confidence: float
```

**Conexao com existente:**
`AgentDMN` le `hub.minutes.decisions` e `hub.transcript_clean`. As decisoes formalizadas em DMN ficam linkadas com os `kh_facts` correspondentes via `meeting_ref`.

---

### FASE B — Camada de Atos de Dialogo Simplificada (Alta prioridade)
**Referencia:** ISO 24617-2 (versao pragmatica, nao o DiAML completo)
**Esforco estimado:** medio (2-3 semanas)

**Racional:**
Saber *o que foi dito* e menos valioso do que saber *o que cada fala fez*. Uma objecao nao resolvida e mais importante do que tres confirmacoes. Um risco identificado informalmente e depois ignorado e um problema latente. Essa camada enriquece todos os outros agentes.

**Nao implementar:** anotacao por utterance (custo de tokens inviavel).
**Implementar:** classificacao por **segmento tematico** do transcript, enriquecendo os `kh_facts`.

**Atos de dialogo relevantes para reunioes corporativas:**

| Ato | Codigo | Exemplo |
|---|---|---|
| Decisao confirmada | `decision` | "Entao ficou definido que..." |
| Compromisso assumido | `commitment` | "Eu me comprometo a entregar ate..." |
| Objecao levantada | `objection` | "Acho que isso nao vai funcionar porque..." |
| Risco identificado | `risk` | "Existe o risco de que..." |
| Pergunta em aberto | `open_question` | "Mas quem e responsavel por isso?" |
| Confirmacao/acordo | `agreement` | "Concordo, faz sentido" |
| Excecao operacional | `exception` | "Na pratica o usuario faz diferente" |
| Revisao de decisao anterior | `revision` | "Na reuniao passada combinamos X, mas agora..." |

**O que implementar:**
- Enriquecer `AgentKnowledgeExtractor` com campo `dialogue_act` em cada `kh_facts`
- Alternativa mais leve: novo campo `utterance_type` na skill existente (sem novo agente)
- UI: filtro por tipo de ato no Knowledge Hub
- Metrica na `ContextHealth`: distribuicao de atos — identifica reunioes dominadas por objecoes ou perguntas em aberto (sinal de baixa resolucao)

**Impacto em outros agentes:**
`AgentRequirements` ja faz speaker attribution. Com atos de dialogo, seria possivel distinguir requisitos que vieram de uma *decisao confirmada* vs. de uma *sugestao informal* — diferenca de confiabilidade crucial.

---

### FASE C — Mapa de Argumentacao IBIS (Media-alta prioridade)
**Referencia:** IBIS (Issue-Based Information System) + Dialogue Mapping
**Esforco estimado:** alto (3-4 semanas)

**Racional:**
Esta e a camada mais diferenciadora possivel — nenhum concorrente a entrega. O valor nao esta na decisao final, mas no mapa de tensoes que levou a ela: quais alternativas foram consideradas, quem defendeu o que, que objecoes ficaram sem resposta, que premissas sustentam a decisao.

**Estrutura IBIS:**
```
ArgumentationMap:
  questions: List[IBISQuestion]      # questoes em disputa na reuniao
    - id: str
    - statement: str                 # "Como deve ser feita a triagem?"
    - raised_by: str                 # participante que trouxe a questao
    - alternatives: List[IBISAlternative]
        - id: str
        - description: str           # alternativa proposta
        - proposed_by: str
        - pros: List[str]            # argumentos a favor
        - cons: List[str]            # argumentos contra
        - supported_by: List[str]    # participantes a favor
        - opposed_by: List[str]      # participantes contra
    - resolution: IBISResolution | None
        - type: "decided" | "deferred" | "unresolved"
        - chosen_alternative: str | None
        - rationale: str
        - with_caveats: List[str]    # ressalvas registradas
```

**O que implementar:**
- `AgentArgumentation` — extrai o mapa IBIS da transcricao
- `skills/skill_argumentation.md` — prompt especializado em raciocinio argumentativo
- `modules/argumentation_renderer.py` — visualizacao interativa (expanders aninhados ou grafo)
- Tab `Argumentacao` no Pipeline (dentro de "Analise Avancada")
- Integracao com `kh_facts`: decisoes do IBIS linkadas com `kh_facts.type=decision`
- Metrica `ContextHealth`: porcentagem de questoes com resolucao vs. em aberto

**Conexao IBIS -> DMN:**
Uma `IBISQuestion` resolvida com `type=decided` e um candidato natural a uma tabela DMN. Os dois agentes podem trabalhar em sequencia: IBIS captura o raciocinio, DMN formaliza a decisao resultante.

---

### FASE D — Visualizacao de Grafo de Conhecimento (Media prioridade)
**Referencia:** inspiracao em RDF/OWL, implementado sobre Supabase existente
**Esforco estimado:** medio (2 semanas)

**Racional:**
Nao implementar RDF/OWL. Os dados ja existem em estrutura relacional no Knowledge Hub. O valor real e uma **visualizacao interativa** que mostre as conexoes entre participantes, fatos, decisoes, requisitos e contradicoes — sem mudar o banco.

**O que implementar:**
- Tab "Grafo" em `pages/KnowledgeHub.py`
- Biblioteca `pyvis` (compativel com Streamlit via `components.html`) ou D3.js inline
- Nos: participantes, fatos, requisitos, decisoes, processos BPMN
- Arestas: `afirmou`, `decidiu`, `gerou_requisito`, `contradiz`, `executa_processo`
- Filtros: por reuniao, por tipo de no, por participante
- Fonte de dados: joins sobre `kh_facts`, `kh_entities`, `requirements`, `bpmn_processes`

**Nao implementar:** serializacao RDF/Turtle, SPARQL endpoint, OWL reasoner. Zero valor pratico para o usuario corporativo.

---

### FASE E — Enriquecimento BABOK da Ata (Baixa-media prioridade)
**Referencia:** BABOK Guide v3 — Elicitation and Collaboration
**Esforco estimado:** baixo (1 semana)

**Racional:**
`AgentMinutes` ja captura decisoes, action items e participantes. Com pequenos ajustes ao skill, capturaria explicitamente as demais entidades BABOK que hoje ficam implicitas.

**Campos a adicionar em `MinutesModel`:**
- `assumptions` — premissas declaradas na reuniao
- `risks` — riscos mencionados (distintos de requisitos de qualidade)
- `open_questions` — perguntas sem resposta ao final da reuniao
- `dependencies` — dependencias entre times/sistemas identificadas
- `stakeholder_needs` — necessidades de stakeholder expressas informalmente

Esses campos ja existem implicitamente nos `kh_facts` — a questao e surfaca-los na ata para exportacao (DOCX/PDF) e no ROI-TR.

---

### FASE F — Query-based Summarization (Baixa prioridade)
**Referencia:** QMSum — Query-based Multi-domain Meeting Summarization
**Esforco estimado:** baixo (ja parcialmente implementado)

**Racional:**
O Assistente ja faz Q&A sobre transcricoes via RAG. O que falta e formalizar uma interface de "resumo orientado por consulta" — o usuario define o angulo (ex: "resuma sob a perspectiva do time de TI") e o sistema gera um resumo direcionado com fontes tracadas.

Isso e incremental sobre o Assistente existente — nao requer novo agente, apenas um template de prompt especializado e uma UI dedicada.

---

## 4. Resumo executivo e roadmap

| Fase | Feature | Padrao | Prioridade | Esforco |
|---|---|---|---|---|
| A | AgentDMN + DMN viewer | OMG DMN 1.4 | Alta | Medio |
| B | Dialogue Acts em kh_facts | ISO 24617-2 simplificado | Alta | Medio |
| C | AgentArgumentation + IBIS map | IBIS / Dialogue Mapping | Media-alta | Alto |
| D | Knowledge Graph visualization | Dados Supabase, visual D3/pyvis | Media | Medio |
| E | Enriquecimento BABOK da ata | BABOK Guide v3 | Media | Baixo |
| F | Query-based summarization | QMSum | Baixa | Baixo |

**Fases NAO recomendadas:**
- CMMN — niche, custo/beneficio negativo para analise de reunioes
- RDF/OWL serializacao — overcomplexo, zero valor pratico para usuario corporativo
- ISO 24617-2 completo (DiAML por utterance) — custo de tokens inviavel em producao

---

## 5. Impacto esperado no posicionamento

Apos Fases A-C implementadas, o P2D seria o unico produto do mercado capaz de:

> Transformar uma reuniao em **seis artefatos formais inter-relacionados**:
> BPMN (processo) · DMN (decisoes) · SBVR (regras) · BMM (motivacao) · Requisitos IEEE 29148 · Mapa IBIS (argumentacao)
> — com rastreabilidade cruzada entre reunioes e deteccao automatica de contradicoes.

Isso seria uma diferenciacao defensavel como **Business Meeting Intelligence Framework (BMIF)** — exatamente a lacuna que o ChatGPT identificou como "quase especificacao ainda nao existente no mercado".

---

## 6. Proximos passos

1. Revisar e ajustar este plano (prioridades, escopo de cada fase)
2. Definir ordem de implementacao (sugestao: A -> B -> C)
3. Para cada fase aprovada: criar arquivo de especificacao detalhada em `melhorias/`
4. Implementar iterativamente com commits por feature
