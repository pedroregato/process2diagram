# Guia de Entrevista Técnica — Pulse Client Experts (Engenheiro de IA)

> Preparado em 2026-08-04. Todo dado técnico sobre o P2D neste guia foi verificado direto no código nesta sessão — nada aqui é "de memória". Formato pensado pra entrevista por voz (IA no WhatsApp): frases prontas pra falar, não parágrafos de relatório pra ler.

---

## 0. Como usar este guia

- **Seção 5 (NLP + LLM) é a mais importante** — a recrutadora avisou que é o que mais vai pesar nos primeiros meses, por causa da solução de coach pros agentes do Contact Center.
- As respostas da Seção 6 estão em tamanho de fala real (30–90s). Não decore palavra por palavra — decore a **estrutura** (abertura → exemplo concreto → número/evidência → fechamento).
- Toda vez que a resposta honesta é "não uso X, mas uso Y equivalente", isso está marcado explicitamente. **Não inventar Spark/Databricks/PyTorch** — se perguntarem direto, a resposta é a da Seção 2, não uma invenção.

---

## 1. A vaga em 1 parágrafo

Engenheira/o de IA no time de **Inteligência de Dados** da Pulse (consultoria interna de dados pras áreas de atendimento), Rio de Janeiro, híbrido. Empresa do Grupo Santander, canal remoto de atendimento (0800/chat), 8.600 colaboradores em 4 unidades. O trabalho: pipelines de IA ponta a ponta, NLP + IA Generativa pra **análise de interações e automação de feedback** no Contact Center, ligado a KPIs de atendimento (TMO, ABS, taxa de conversão, rechamadas, transferências, CSAT). Vaga pede Python/SQL/Spark(Databricks), deploy+monitoramento de ML, frameworks de ML clássico (PyTorch/Scikit-Learn/TensorFlow/XGBoost) e frameworks de GenAI/NLP (spaCy/NLTK/LangChain) + prompt engineering.

**O gatilho específico que a recrutadora citou:** solução de **coach para os agentes do Contact Center**, que precisa de uma camada de NLP + LLM. Isso é o ponto de maior alinhamento real com o P2D — ver Seção 5.

---

## 2. Mapeamento honesto — o que a vaga pede vs. o que o P2D demonstra

| Pedido na vaga | Situação real no P2D | Como responder se perguntarem direto |
|---|---|---|
| Python | ✅ Forte — todo o projeto, ~50k+ linhas, 1010 testes automatizados (`pytest`) | Sem ressalva |
| SQL | ✅ Real — Postgres via Supabase, queries diretas, migrations SQL escritas à mão (não só ORM) | Sem ressalva |
| Spark / Databricks | ❌ Não usado no P2D | "Não tive Databricks/Spark nesse projeto específico — o volume de dados do P2D não pede processamento distribuído, é OLTP em Postgres. Mas tenho base sólida de SQL e de pipeline de dados versionado, e Spark é uma camada de execução que eu pegaria rápido em cima disso." |
| ML clássico (PyTorch/Scikit-Learn/TensorFlow/XGBoost) | ❌ Não usado — o P2D não treina modelo preditivo próprio, é orquestração de LLMs de terceiros via API | "O P2D é um projeto de orquestração de LLM, não de ML clássico treinado — não tenho modelo próprio em produção com PyTorch/XGBoost nesse projeto. O que eu tenho de equivalente é a disciplina de ML em produção: validação de saída, monitoramento de erro por provider, versionamento de prompt como se fosse versionamento de modelo. É a mesma disciplina de engenharia, aplicada a um tipo de 'modelo' diferente (LLM via API em vez de modelo treinado in-house)." |
| Deploy + monitoramento de modelo em produção | 🟡 Parcial, mas real | Ver Seção 5.7 — telemetria de LLM em produção é um dos pontos mais fortes do projeto |
| NLP — spaCy | ✅ Real, ativo | `agents/nlp_chunker.py`, `modules/ner_extractor.py`, `modules/pii_sanitizer.py` |
| NLP — NLTK | ❌ Não usado no P2D | Não inventar — se perguntarem, "não usei NLTK nesse projeto, usei spaCy pra NER/segmentação" |
| GenAI — LangChain | ❌ Não usado (existe um arquivo stub morto, mantido só por compatibilidade de import) | Não dizer "uso LangChain". Dizer "não uso a biblioteca LangChain nesse projeto — uso LangGraph num ponto específico (retry adaptativo), e o resto da orquestração é uma classe Python própria" |
| GenAI — LangGraph | ✅ Real, mas escopo estreito (1 função: retry adaptativo de qualidade do BPMN) | Ver explicação pronta na Seção 6 |
| Prompt Engineering | ✅ Muito forte — é o coração do projeto | Ver Seção 5.3 |
| IA Generativa / LLM em geral | ✅ Muito forte — 8 providers, multi-agente, RAG, cache, custo, telemetria | Esse é o argumento central da entrevista |

**Regra de ouro pra entrevista de voz:** nunca inflar Spark/Databricks/PyTorch. É fácil de checar depois e mina a credibilidade do resto. O ponto forte de verdade é GenAI/NLP/LLM em produção — é pra lá que toda resposta deve convergir.

---

## 3. O projeto em 60 segundos (pitch pronto)

> "O Process2Diagram é um sistema que eu construí sozinho, que transforma transcrição de reunião em artefatos formais de negócio — BPMN, ata, requisitos, glossário de regras de negócio — usando um pipeline de mais de 15 agentes de LLM especializados, orquestrados em Python. Ele já processa mais de mil linhas de teste automatizado, tem um provedor de LLM plugável — hoje suporta 8, incluindo DeepSeek, Claude, OpenAI, Gemini —, faz RAG sobre o histórico de reuniões com embeddings e pgvector, e tem uma camada de observabilidade real: telemetria de erro por provider, taxa de validação de schema de saída, cache semântico. É basicamente um projeto de engenharia de IA em produção de ponta a ponta, só que o domínio é 'reunião corporativa' em vez de 'ligação de contact center' — e a estrutura do pipeline é a mesma que eu usaria pro desafio de vocês."

---

## 4. Arquitetura e tecnologias por camada

| Camada | Tecnologia real | Detalhe que vale citar |
|---|---|---|
| Linguagem | Python 3.13 | Todo o backend, agentes, pipeline |
| Orquestração multi-agente | Classe própria (`Orchestrator`) | Sequência fixa de agentes + 1 paralelização manual (`ThreadPoolExecutor`) — ver Seção 6 |
| LLM (providers) | DeepSeek (padrão), Claude/Anthropic, OpenAI, Azure OpenAI, Groq, Google Gemini, Grok (xAI) | 8 provedores plugáveis, roteamento por config, chave compartilhada por alias |
| NLP determinístico | spaCy 3.8 (`pt_core_news_lg`) | NER, segmentação, detecção de ator — sem custo de LLM |
| Banco de dados | PostgreSQL via Supabase | RLS, migrations SQL versionadas, ~40 tabelas |
| Busca vetorial | pgvector | Embeddings 512-dim (Matryoshka, OpenAI `text-embedding-3-small`) |
| Frontend | Streamlit | ~50 páginas, RAG assistant conversacional com 150+ tools |
| API comercial | FastAPI | Auth por API key (hash SHA-256), rate limiting, controle de concorrência |
| Infra / Deploy | Streamlit Cloud (produção real) + Docker/Cloud Run/Cloud Build (infra-as-code pronta pro GCP) | |
| Testes | pytest | 1010 testes automatizados, suite completa roda em ~2min |
| Validação de schema | Pydantic v2 | Saída de LLM validada contra schema tipado, fail-open com telemetria de taxa de sucesso |
| Observabilidade | Telemetria própria (Supabase) | Latência, erro por provider, cache hit rate, taxa de validação de schema — dashboard próprio |
| Segurança de dados | Sanitização de PII em 2 camadas | Ver Seção 5.6 — muito relevante pro domínio de vocês (dados de cliente de banco) |
| Versionamento | Git | Commits atômicos, testes antes de cada commit, CI implícito via suite local |

---

## 5. NLP + LLM em profundidade (a parte que a entrevistadora disse que mais pesa)

Esta seção é o argumento principal da entrevista. A tese: **o P2D já resolve, no domínio de "reunião corporativa", exatamente o mesmo problema de forma que a Pulse quer resolver no domínio de "ligação de Contact Center"** — transformar interação falada/transcrita em sinal estruturado, verificável e acionável, em produção, com custo e qualidade monitorados.

### 5.1 — Arquitetura multi-agente (não é 1 prompt gigante)

O pipeline não é "manda tudo pro GPT e reza". É uma cadeia de **15+ agentes especializados**, cada um com um prompt próprio, versionado (front-matter com `version:`), e uma responsabilidade única — um agente extrai BPMN, outro extrai requisitos, outro faz ata, outro detecta contradição entre reuniões, outro detecta ambiguidade de comunicação. Cada agente tem `output_schema` (Pydantic) que valida a resposta do LLM antes dela seguir no pipeline.

**Por que isso importa pra vaga:** um "coach de agente de Contact Center" não é 1 prompt — é: transcrever → limpar artefato de ASR → extrair o que foi dito → checar aderência a script/compliance → detectar sinais de risco (objeção não respondida, informação contraditória) → gerar feedback estruturado pro supervisor. Isso é literalmente a forma do pipeline que já existe no P2D.

### 5.2 — NLP determinístico vs. LLM (onde usar cada um)

Nem tudo passa por LLM — isso é uma decisão de custo/qualidade deliberada. `NLPChunker` usa spaCy (sem custo de API) pra segmentação, NER e detecção de atores **antes** de qualquer chamada de LLM — assim o LLM recebe texto já estruturado, em vez de ter que fazer NER dentro do prompt (mais barato, mais confiável, mais rápido). `AgentValidator` pontua qualidade de um BPMN gerado **sem LLM nenhum** — é lógica determinística em Python, usada num torneio onde o pipeline gera o mesmo artefato 3x com o LLM e escolhe o melhor pela pontuação determinística.

**Ponte pra vaga:** essa é exatamente a arquitetura certa pra um coach de Contact Center em escala — spaCy pra sinais baratos e determinísticos (nome do cliente, produto mencionado, sentimento básico), LLM só pra julgamento que precisa de linguagem natural real (qualidade do atendimento, tom, se a objeção foi bem tratada). Rodar tudo em LLM sacrifica custo à toa.

### 5.3 — Prompt Engineering real (não "digitar uma pergunta boa")

Cada agente tem um arquivo de skill (`skills/skill_*.md`) — prompt versionado com metadado de versão, testado (`tests/test_skill_files.py` valida integridade de todos), com regras explícitas de formato de saída, exemplos positivos e negativos, e uma "restrição central" declarada no próprio prompt (ex: no agente de detecção de contradição, "toda contradição carrega evidência verificável ou não é emitida"). Retry automático em até 3 tentativas com re-injeção de erro de parsing no prompt. Roteamento de "modo pensamento" (`reasoning_effort=high`) pra tarefas que precisam de raciocínio mais lento, contra "modo rápido" pra tarefas simples — decisão de custo/latência por agente.

### 5.4 — RAG e busca semântica

Toda reunião processada gera embeddings (`text-embedding-3-small`, truncado pra 512 dimensões via Matryoshka — 66% menos custo de storage sem perda relevante de qualidade, decisão deliberada, não default ingênuo) e chunks salvos em `pgvector`. O assistente conversacional busca por similaridade de cosseno + busca por palavra-chave em paralelo (modo híbrido), com fallback pra keyword puro quando não há embedding configurado (fail-open).

### 5.5 — Cache semântico (decisão de engenharia, não "usei porque é hype")

Existe um cache de resposta de LLM — mas é **hash exato (SHA-256)**, não embedding/similaridade. Essa foi uma decisão deliberada: avaliei uma proposta de cache por embedding e decidi não implementar, porque o risco de falso-positivo (entregar o BPMN errado pra uma transcrição parecida mas diferente) supera o ganho, sem custo/risco demonstrado que justifique. Isso é um bom exemplo de maturidade de engenharia pra citar: **saber quando NÃO usar a solução mais sofisticada.**

### 5.6 — PII e segurança de dado sensível em pipeline de LLM (crítico pro contexto bancário)

Isso é extremamente relevante pro domínio de vocês (dados de cliente de banco, Contact Center). O P2D sanitiza dado sensível em **duas camadas** antes de qualquer chamada a um provider de LLM externo:
- **Tier 1 (estruturado):** CPF, CNPJ, e-mail, telefone, valores monetários → tokens `@LABEL_NNN` via regex, sem custo.
- **Tier 2 (nomes):** detecção de nome próprio via spaCy, substituído por `[PESSOA:XX]` no que vai pro LLM — e **desanitizado só depois**, antes de salvar no banco (o dado real fica no seu próprio banco, nunca no provider externo).
- Existe também uma camada de compliance separada (LGPD): detecção de PII pós-pipeline, painel de consentimento com base legal (Art. 7º), trilha de auditoria.

**Ponte pra vaga:** um coach de Contact Center do Santander processa CPF, dados financeiros, tudo em ligação real de cliente de banco — mandar isso cru pra uma API de LLM externa é risco regulatório real. Esse é o tipo de arquitetura que evita isso sem abrir mão de usar LLM de terceiro.

### 5.7 — Observabilidade / "ML em produção" pro mundo de LLM

Esse é o ponto que substitui "MLOps clássico" (que a vaga também cobra, via PyTorch/monitoramento). Toda chamada real de LLM gera telemetria assíncrona: latência, tokens, provider, erro (`is_error` + mensagem, capturado mesmo quando a chamada "funciona" mas retorna conteúdo vazio — bug real e intermitente de um dos providers que eu rastreei e hoje aparece como alerta, não como silêncio). Existe também **taxa de validação de schema por agente ao longo do tempo** — ou seja, "% de vezes que o LLM respondeu no formato esperado" como métrica de qualidade contínua, igual se monitora drift de um modelo clássico.

### 5.8 — Detecção de sinal de qualidade em conversa — o ponto mais direto com a vaga

O agente mais novo do projeto (`AgentProvocations`) detecta, numa reunião, **o que ficou sem resposta ou sem exame**: uma objeção levantada e nunca respondida (`asymmetry`), uma afirmação categórica que ninguém questionou (`premise`), um tema que devia ter sido tocado e nunca foi (`absence`), uma contradição entre o que foi dito numa reunião e o que tinha sido decidido antes (`contradiction`). Cada achado é validado **deterministicamente** contra o texto real antes de ser mostrado — nunca aprova por omissão, sempre exige citação literal com timestamp.

**Isso é, quase palavra por palavra, o que um coach de agente de Contact Center precisa fazer:** "o agente prometeu retorno em 24h e não anotou isso em nenhum sistema" (assimetria), "o agente afirmou uma política que pode estar errada e ninguém confirmou" (premissa não examinada), "o script pedia confirmação de dados e isso não aconteceu nessa ligação" (ausência), "o agente disse algo que contradiz o que foi dito 3 ligações atrás com o mesmo cliente" (contradição). O domínio muda de "reunião" pra "ligação", mas o **formato do problema é idêntico**, e eu já validei essa arquitetura numa POC real essa semana.

---

## 6. Perguntas prováveis + respostas prontas (tamanho de fala)

**"Me conta sobre um projeto de IA que você construiu do zero."**
> Use o pitch da Seção 3, depois puxe direto pra 5.8 se der abertura.

**"Como você orquestra múltiplos agentes de LLM? Usa LangGraph, CrewAI, algum framework?"**
> "Não uso framework de orquestração multi-agente pronto — construí um orquestrador próprio em Python: uma sequência fixa de agentes que compartilham um objeto de estado central, com paralelização manual via `ThreadPoolExecutor` pra dois agentes que não dependem um do outro. Eu uso LangGraph, mas só num ponto específico — um loop de retry adaptativo de qualidade, onde o problema realmente tem formato de grafo com decisão condicional em runtime. Pro resto do pipeline, que é uma sequência conhecida em tempo de design, um framework de grafo seria complexidade desnecessária. Foi decisão de engenharia, não desconhecimento da ferramenta."

**"Como você garante que a saída do LLM está correta / não é alucinação?"**
> "Em duas camadas. Primeiro, saída estruturada: todo agente valida a resposta do LLM contra um schema Pydantic antes de qualquer coisa seguir no pipeline, e eu meço a taxa de validação ao longo do tempo como métrica de qualidade. Segundo, e mais importante pro tipo de achado que exige confiança alta: um validador determinístico, sem LLM, que confere cada alegação contra o texto original antes de aprovar — por exemplo, se o sistema diz 'essa objeção nunca foi respondida', ele confere programaticamente se o termo realmente não aparece no trecho relevante da transcrição. Nunca aprovo por omissão."

**"Qual sua experiência com Databricks/Spark?"**
> Resposta da Seção 2 — honesta, sem inventar, pivotando pra SQL/pipeline de dados.

**"E com PyTorch/Scikit-Learn/modelo de ML clássico?"**
> Resposta da Seção 2 — honesta, pivotando pra disciplina de produção equivalente.

**"Como você lida com custo de LLM em produção?"**
> "Multi-provider com roteamento configurável — o DeepSeek é o padrão por ser mais barato, mas cada agente pode rodar num provider diferente dependendo da tarefa. Tenho um módulo de simulação de cenário que projeta custo por combinação de agente e modelo antes de aplicar em produção. E cache exato por hash SHA-256 evita rechamar o LLM pra entrada idêntica — decisão consciente de não usar cache por similaridade/embedding, porque avaliei o risco de falso-positivo como maior que o ganho."

**"Como você trata dado sensível/PII antes de mandar pro LLM?"**
> Resposta da Seção 5.6, dita naturalmente.

**"Por que você acha que esse projeto é relevante pra essa vaga especificamente?"**
> "Porque o problema central da vaga — pegar interação de cliente, processar com NLP e LLM, e gerar sinal estruturado e acionável pra melhorar atendimento — é estruturalmente o mesmo problema que eu resolvo há meses no meu projeto, só que no domínio de reunião corporativa em vez de ligação de Contact Center. Migrar o pipeline de domínio é trabalho real, mas a arquitetura — orquestração de agentes, validação determinística de saída de LLM, observabilidade, proteção de dado sensível antes de sair pra um provider externo — já está testada e em produção."

---

## 7. Perguntas pra fazer de volta (mostra que você já pensou no problema real)

- "A camada de coach vai atuar em tempo real (durante a ligação) ou pós-ligação (análise assíncrona)? Isso muda bastante a arquitetura de latência."
- "Hoje as transcrições de ligação já passam por algum pré-processamento — remoção de artefato de ASR, diarização de falante — ou isso ainda está em aberto?"
- "Existe alguma exigência de que o processamento de dado de cliente fique num ambiente específico (não sair pra API de LLM externa), dado que é dado de cliente de banco?"
- "O time já tem alguma definição de KPI de qualidade pro output da IA (ex: quantas sugestões de coach o supervisor aceita de fato), ou isso é algo que eu ajudaria a desenhar?"

---

## 8. Lembretes finais antes da entrevista

- **Não inflar Spark/Databricks/PyTorch/TensorFlow/XGBoost.** Zero uso real no P2D. Responder honestamente + pivotar pra disciplina equivalente é mais forte do que fingir familiaridade que não resiste a uma pergunta de acompanhamento.
- **Não dizer "uso LangChain".** É stub morto, não é usado. Se perguntarem, a resposta certa é sobre LangGraph, escopo estreito, decisão deliberada.
- **O argumento mais forte é a Seção 5.8** — a ponte direta entre "detectar o que ficou sem resposta numa reunião" e "detectar o que ficou sem resposta numa ligação". Não deixar de mencionar isso, é literalmente o problema que a vaga quer resolver.
- Números concretos pra citar quando fizer sentido: **1010 testes automatizados**, **8 provedores de LLM**, **15+ agentes especializados**, **512 dimensões de embedding** (com a razão da escolha), **2 camadas de sanitização de PII**.
