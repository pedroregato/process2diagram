# LangChain, LangGraph e Cache Semântico no P2D — resposta técnica

> Escrito em 2026-08-05. Toda afirmação verificada direto no código e no histórico de commits real do projeto — inclusive achei um commit que eu não conhecia (`2190742`) que documenta exatamente por que o LangChain saiu.

---

## 1. Por que não usamos LangChain

**Usamos, no início — e tiramos, com um motivo técnico concreto, não por preferência de estilo.**

Histórico real (`git log -- adapters/langchain_tools.py`):

- **15/05/2026, commit `47246a3`:** o "Agente de Análise Autônomo" (modo investigativo do Assistente) foi implementado com LangChain — padrão ReAct, usando `adapters/langchain_tools.py` pra expor as tools do sistema no formato que o LangChain espera.
- **15/05/2026, commit `2190742`, mesmo dia:** removido. Mensagem do commit, literal:

  > *"Removes langchain, langchain-openai, langchain-anthropic packages that conflicted with openai==1.65.0 (langchain-openai requires openai>=2.26.0). AgentAnalyst now uses the same openai/anthropic SDK already in use by AgentAssistant, with a manual tool-calling loop up to 15 iterations."*

**O problema real:** `langchain-openai` exigia `openai>=2.26.0`, mas o projeto inteiro já estava pinado em `openai==1.65.0` — versão usada por todos os outros agentes, que chamam a SDK da OpenAI/Anthropic diretamente (não via LangChain). Forçar o upgrade da SDK só pra sustentar o LangChain nesse único agente arriscava quebrar todos os outros agentes que dependiam do comportamento da versão 1.65 — um trade-off ruim: puxar uma dependência pesada e opinativa pra resolver um problema (chamar LLM + tools) que a SDK nativa já resolve sozinha, ao custo de arriscar a estabilidade do resto do sistema.

**A troca:** o agente passou a usar um loop manual de tool-calling (até 15 iterações), reaproveitando a mesma SDK e o mesmo padrão de `AssistantToolExecutor` que o Assistente de chat já usava. `adapters/langchain_tools.py` ficou como um stub de 7 linhas, mantido só por compatibilidade de import — hoje não importa nada do LangChain (`grep import langchain` no projeto inteiro: zero resultados).

**Nuance importante pra não confundir:** o `LangGraph` (que a gente usa, ver seção 3) depende internamente de `langchain-core` — isso é um detalhe de empacotamento do ecossistema, não significa que o P2D chama API do LangChain. `requirements.txt` documenta isso: `langgraph==1.2.0` está pinado especificamente porque uma versão mais nova de `langchain` (transitivo) exigiria `langgraph<1.3.0`. É dependência de dependência, não uso direto.

---

## 2. Por que não usamos cache semântico (por embedding/similaridade)

**Porque já existe um cache — só que por hash exato, e a decisão de NÃO evoluir pra embedding foi deliberada, avaliada e documentada, não esquecimento.**

O que já existe em produção: `services/semantic_cache.py` (tabela `llm_cache`), plugado em `agents/base_agent.py::_call_llm()` — **global**, todos os agentes passam por ele, não só um. Chave de cache: `SHA-256` do prompt normalizado. **PII-safe** por construção: o texto é sanitizado (nomes/CPF/valores viram token) *antes* de qualquer chamada ao LLM, então o hash — e o que fica cacheado — nunca contém dado sensível cru.

Em julho/2026, avaliei uma spec trazida de fora propondo evoluir isso pra cache semântico de verdade (embedding + `pgvector`, matching por similaridade). Contra o código real, achei 3 problemas:

1. **Parte da spec pressupunha infraestrutura que não existe** — um classificador de trecho de transcrição rodando dentro do orquestrador, decidindo cache por pedaço. O pipeline real roda agente completo sobre a transcrição inteira, não faz triagem por trecho.
2. **O risco de falso positivo é assimétrico e real.** Cache semântico errado numa tarefa de classificação é barato (reclassifica, sem dano). Cache semântico errado numa tarefa de **geração de artefato** (BPMN, ata) entrega ao usuário o diagrama ou a ata de uma transcrição **diferente** — não é "resposta subótima", é "resposta errada apresentada como certa". Isso muda completamente o cálculo de risco/benefício.
3. **Custo em toda chamada, benefício não comprovado.** Cache por similaridade custa 1 chamada de embedding em **toda** requisição — hit ou miss — pra tentar economizar um caso que eu não tinha nenhuma evidência real de estar acontecendo em produção ("reprocessar transcrição quase-idêntica" nunca apareceu como dor real).

**Decisão (junto com o usuário, via pergunta estruturada — não escolhi sozinho):** não construir a camada de embedding. Implementei só o ajuste barato que resolvia a motivação nº1 real da spec (revisão marginal do mesmo texto virando cache miss por diferença de formatação): normalizar espaço em branco antes de fazer o hash. Zero custo de embedding, zero risco novo de falso-positivo, resolve o problema que de fato existia.

**O padrão que isso demonstra:** dizer não a uma solução mais sofisticada quando o ganho não está demonstrado é tão parte de engenharia de IA em produção quanto saber implementar a versão sofisticada quando ela é a resposta certa.

---

## 3. Qual é o papel do LangGraph

**Um só, deliberadamente estreito: retry adaptativo de qualidade na geração de BPMN — não é o orquestrador geral do pipeline.**

Localização: `core/lg_pipeline.py::LGBPMNRunner`, opt-in via flag (`use_langgraph`), não é o caminho padrão obrigatório.

Fluxo: gera o diagrama BPMN → pontua com `AgentValidator` (**determinístico, sem LLM** — Python puro avaliando granularidade, tipo de tarefa, cobertura de gateways) → se a nota ficar abaixo do piso, tenta de novo, injetando o motivo da nota baixa de volta no prompt → até N iterações.

**Por que esse ponto específico é o único que usa LangGraph:** é o único lugar do pipeline onde o fluxo genuinamente tem formato de grafo — "gerar → avaliar → decidir se repete, com base num resultado que só existe em runtime" é exatamente o problema que um `StateGraph` resolve bem (branching condicional sobre estado). O resto do pipeline (`agents/orchestrator.py`) é uma sequência fixa de 15 agentes, conhecida em tempo de design (`_PLAN`), com um único ponto de paralelismo manual (`ThreadPoolExecutor` pra Minutes+Requirements) — não precisa de roteamento dinâmico, então usar LangGraph ali seria complexidade sem ganho.

---

## Síntese — o princípio por trás das 3 respostas

As três decisões seguem a mesma régua: **adotar um framework externo só onde o formato do problema genuinamente pede o que o framework resolve — não por hype, não por currículo.**

- LangChain foi tirado quando o custo real (conflito de dependência arriscando o resto do sistema) superou o benefício de uma abstração que uma SDK nativa + loop manual já cobriam.
- Cache semântico não foi construído porque o risco concreto (entregar artefato errado) superava um ganho que nunca teve evidência real de ser um problema.
- LangGraph foi mantido, mas só onde o problema é genuinamente um grafo com decisão condicional em runtime — em vez de forçado no pipeline inteiro só porque "orquestração multi-agente com LangGraph" soa mais impressionante no currículo.

**Versão curta pra falar em entrevista:**

> "Eu uso framework externo onde ele resolve um problema real que eu já testei e comprovei — não por padrão. Tirei o LangChain de um agente porque ele criava conflito de versão de dependência com o resto do sistema, e um loop manual de tool-calling resolvia igual, com menos risco. Avaliei cache semântico por embedding e decidi não construir, porque pra geração de artefato o risco de falso-positivo é entregar o resultado errado pro usuário, e eu não tinha evidência real de que precisava disso. E uso LangGraph só num lugar — um loop de retry adaptativo de qualidade do BPMN — porque ali o problema é genuinamente um grafo com decisão condicional, e forçar isso no resto de um pipeline sequencial seria complexidade sem ganho."
