# Roadmap — Process2Diagram

Histórico completo de entregas por ciclo de projeto.

---

### PC118-B — Concluído (v5.15 / 2026-07-04) — 2 checks estruturais adicionais: split implícito e cobertura de message flow

**Contexto:** com PC118 (checks 9–11) e o fix do cache do torneio já em produção, o usuário gerou um novo diagrama no BPMN Studio para a mesma descrição complexa — desta vez com 2 pools genuínas, densidade correta por pool (6 e 7 nós) e nenhum beco sem saída, confirmando que os fixes anteriores funcionaram. Uma segunda análise cruzada (revisão externa do diagrama + conferência contra `skill_bpmn.md`) revelou 2 lacunas novas, ainda sem cobertura: (1) `p1_S04` (sendTask "Enviar Escopo Definido") não tinha nenhum `message_flow` associado — só existia 1 message_flow no XML inteiro; e (2) `p2_S02` (callActivity) bifurcava em 2 arestas sem gateway, que reconvergiam num `parallelGateway` de join explícito — um split implícito sem simetria com o join, o espelho do Check 5 (split sem join) já existente.

- [x] `modules/bpmn_structural_validator.py` — 2 novos checks determinísticos:
  - **Check 12:** nó não-gateway com ≥2 arestas de saída cujos ramos reconvergem (via BFS de alcançabilidade) num `parallelGateway`/`inclusiveGateway` com múltiplas entradas → erro, citando a Regra de Sincronização Split↔Join (Passo 4). Não dispara em fan-out que reconverge em nós comuns (padrão XOR implícito, explicitamente permitido pelo skill) nem quando o próprio nó de fan-out já é um gateway (já coberto pelo Check 5).
  - **Check 13 (`_check_message_flow_coverage`):** em colaboração com ≥2 pools, todo `sendTask`/`receiveTask` precisa aparecer em algum `message_flow` como source/target — senão, erro citando o checklist do Passo 6. Só roda com 2+ pools (colaboração de 1 pool já é tratada pelo Check 11 do PC118).
- [x] Verificado com reconstrução exata do XML relatado pelo usuário: os 2 checks disparam corretamente (`p2_S02` fan-out sem gateway + `p1_S04`/`p2_S04` sem message_flow), derrubando `structural` de 10.0 para 2.5.
- [x] 7 testes novos (`TestImplicitSplit` × 3, `TestMessageFlowCoverage` × 4) + `message_flow()` factory helper adicionado a `tests/conftest.py`; 1 teste do PC118 (`test_two_pools_with_send_receive_task_not_flagged`) ajustado para incluir um message_flow real, já que agora é coberto pelo Check 13.
- [x] 365/365 testes passando (7 novos)

### PC118 — Concluído (v5.15 / 2026-07-04) — AgentValidator ganha 3 checks estruturais que faltavam para o torneio pegar violações "nunca" do skill_bpmn.md

**Achado do usuário:** mesmo após PC116-D (torneio + AgentValidator no BPMN Studio), um novo XML gerado ainda apresentava exatamente os defeitos que o torneio deveria evitar — pool única simulando uma segunda organização via sendTask/receiveTask, um nível 1 com ~20 nós (limite do método é 10), e (achado numa segunda análise cruzada com uma revisão externa do diagrama) um nó terminal ("Reabrir Concorrência") sem nenhuma aresta de saída, um beco sem saída silencioso. Investigação confirmou: as 5 dimensões de `AgentValidator.score()` (granularidade, tipo de tarefa, gateways, estrutural, semântica) não tinham NENHUM check para essas 3 violações — `_score_granularity` só compara contagem de tarefas × tamanho do texto (cego a hierarquia), e `bpmn_structural_validator.py` só verifica balanceamento de message flow quando `message_flows_data` não está vazio (com 1 pool só, nunca há message flow, então o check nunca dispara). Conclusão: o torneio protege contra ruído aleatório entre execuções, mas não contra um viés sistemático que as N execuções compartilham — porque o scorer não consegue distinguir um candidato conforme de um não-conforme nessas 3 dimensões.

- [x] `modules/bpmn_structural_validator.py` — 3 novos checks determinísticos, puro Python, sem LLM:
  - **Check 9 (dead-end):** um sink (0 arestas de saída) só é sinalizado como erro se o modelo já declara um evento de fim explícito em outro lugar — evita falso positivo no padrão comum onde o passo terminal não tem tipo explícito e o gerador injeta um "Fim" sintético depois dele.
  - **Check 10 (densidade):** nível 1 com mais de 10 nós (Bruce Silver) → warning (11–15) ou error (16+), citando a Regra de Densidade Cognitiva do Passo 0.1.
  - **Check 11 (`_check_single_pool_choreography`):** collaboration com exatamente 1 participant que ainda usa sendTask/receiveTask → error por step — pega exatamente o defeito "pool única fingindo colaboração" que a Regra 3 do skill proíbe.
- [x] `agents/agent_validator.py::_score_semantic` — penalidade de gateway-com-verbo-de-atividade subiu de -2.5 para -4.0 por ocorrência; uma única violação sobrevivia ao torneio com pontuação "boa o suficiente" nas outras dimensões — essa é uma regra "nunca" do skill e deveria dominar a dimensão semântica quase sozinha.
- [x] Verificado com reconstrução exata do XML relatado pelo usuário (script standalone, não fixture de teste): as 3 novas checks disparam corretamente (9 issues estruturais, incluindo os 6 sendTask/receiveTask + o dead-end + a densidade), derrubando `structural` de um score "aceitável" para 0.0 e o `weighted` final para 4.44 — esse candidato agora perde decisivamente contra qualquer alternativa do torneio que evite ao menos parte dos defeitos.
- [x] 22 testes novos em `tests/test_bpmn_structural_validator.py` (3 classes: `TestDeadEndNode`, `TestDensityLimit`, `TestSinglePoolChoreography`) — nenhuma fixture existente usa sendTask/receiveTask, >10 nós, ou declara evento de fim explícito, então as 3 checks novas têm zero risco de falso positivo nos testes anteriores.
- [x] 354/354 testes passando (22 novos + todos os anteriores, incluindo o ajuste de `test_multiple_gateway_verbs_cumulate` para o novo valor de penalidade)

### PC116-D — Concluído (v5.15 / 2026-07-04) — BPMN Studio ganha o mesmo torneio + AgentValidator do pipeline principal

**Achado do usuário:** ao inspecionar o XML gerado para a descrição complexa do guia, duas organizações citadas nominalmente ("Contratante" e "TechAdvisor Ltda") viraram só uma pool — a interação com a segunda foi representada via sendTask/receiveTask dentro do mesmo pool, sem o segundo participante que `skill_bpmn.md` (Regra 3 — Especificidade de Co-Participantes) exige para terceiros nomeados. Um sub-ciclo detalhado no texto (validar relatório → corrigir se incompleto → aprovar → pagar) foi colapsado num único `callActivity` opaco. A pergunta do usuário — "estamos usando o mesmo rigor... as mesmas ferramentas?" — expôs que a resposta era não: PC116-B (`max_attempts`) só reiniciava a mesma chamada única do zero em caso de EXCEÇÃO; não havia comparação de qualidade entre execuções alternativas, então uma extração "válida mas estruturalmente pobre" (sem lançar exceção) passava direto, sem chance de ser substituída por uma melhor.

- [x] `agents/agent_bpmn_studio.py::generate_bpmn_from_description()` — substitui o retry simples pelo MESMO mecanismo de `core/pipeline.py` quando `n_bpmn_runs > 1` (o caminho padrão do pipeline, já que `n_bpmn_runs=3` por default): roda `n_runs` execuções independentes do `AgentBPMN`, pontua cada uma com `AgentValidator` (granularidade, tipo de tarefa, gateways, estrutural, semântica) e retorna a de maior `.weighted`. Uma execução que lança exceção é descartada do torneio sem abortar as demais.
- [x] `pages/BpmnStudio.py` — lê `st.session_state.n_bpmn_runs`/`bpmn_weights` (mesmas chaves do pipeline principal, não uma config paralela) e exibe o score da versão vencedora após gerar.
- [x] Verificado com dois cenários mockados: torneio de 3 execuções com qualidades propositalmente diferentes confirma que a de maior `.weighted` é sempre a retornada (não a primeira, não a última — a de maior score); tolerância a falha parcial (1 de 3 execuções lança exceção) confirma que o torneio completa normalmente com as 2 restantes em vez de abortar.
- [x] 345/345 testes passando

### PC116-C — Concluído (v5.15 / 2026-07-03) — BPMN Viewer: zoom com roda do mouse + arrasto + fix do botão "Janela"

**Pedido do usuário:** a área do diagrama BPMN deveria ter as mesmas funcionalidades de mouse que o diagrama Mermaid já tem (zoom com a roda, arrasto com clique+arraste), e o botão "↗ Janela" abria uma nova aba onde os botões da toolbar não respondiam.

- [x] `modules/bpmn_viewer.py` — zoom com roda do mouse (`wheel` listener em `#bpmn-container`, `canvas.zoom(scale, {x,y})` centrado no cursor) e arrasto com clique (`mousedown`/`mousemove`/`mouseup`, `canvas.scroll()`) — mesmo modelo de interação do `mermaid_renderer.py`. Aplicado nos dois templates (`_TEMPLATE` e `_TEMPLATE_CDN_FALLBACK`).
- [x] Fix do botão "Janela": a causa provável era capturar `document.documentElement.outerHTML` **depois** do bpmn-js já ter renderizado o SVG no container — a nova aba reexecuta o script e chama `importXML()` de novo sobre um container que já contém elementos/marcadores SVG com os mesmos ids (colisão). Corrigido capturando um snapshot do documento **antes** de qualquer renderização (`_pristineHtml`, no topo do script) e usando esse snapshot no popup.
- [x] Verificado por inspeção de código + renderização funcional dos dois templates via `.format()` (sem erros de chave/placeholder); sem browser automatizado disponível neste ambiente para clique real — pendente de confirmação do usuário em produção.
- [x] 345/345 testes passando

### PC116-B — Concluído (v5.15 / 2026-07-03) — resiliência da geração no BPMN Studio (retry de tentativa completa)

**Achado em uso real:** primeiro teste com a descrição de processo complexa do guia (`Orientacoes_BpmnStudio.py`, 2 organizações + paralelismo + 2 decisões com loop-back) falhou: `[bpmn] Failed after 3 attempts. Last error: ValueError("Incomplete BPMN: pool 'Contratante' has 20 steps but 0 edges — sequence flows missing.")`. Causa: o pipeline normal tem duas redes de segurança que o BPMN Studio v1 ("modo simples", por decisão deliberada do plano original) não tem — torneio `n_bpmn_runs=3` + LangGraph adaptativo (até 5 tentativas). O Studio dependia só do retry interno do `AgentBPMN` (3 tentativas), que reforça a MESMA correção sobre a MESMA extração — se o modelo fica preso num padrão de falha, as 3 tentativas falham identicamente (exatamente o que aconteceu).

- [x] `agents/agent_bpmn_studio.py::generate_bpmn_from_description()` — novo parâmetro `max_attempts=2`: reinicia a chamada inteira ao `AgentBPMN` do zero (pedido "limpo", sem o histórico da correção que não funcionou) em vez de só confiar no retry interno. Cada tentativa opera sobre `copy.copy(hub)` — isola estado parcial de tentativas malsucedidas.
- [x] Verificado com dois cenários mockados na fronteira de rede: (1) 1ª tentativa completa falha 3/3 identicamente (reproduz o bug relatado), 2ª tentativa sucede — `hub.bpmn.ready=True`; (2) todas as tentativas falham — levanta a exceção da última tentativa normalmente, sem mascarar erro real.
- [x] 345/345 testes passando

### PC116 — Concluído (v5.15 / 2026-07-03) — BPMN Studio

Plano em `melhorias/bpmn-studio.md` implementado: nova página `pages/BpmnStudio.py` (grupo Pipeline) com dois modos —

- **Gerar** (descrição → BPMN + Mermaid): `agents/agent_bpmn_studio.py::generate_bpmn_from_description()` monta um `KnowledgeHub` sintético (`transcript_clean = descrição`), roda `NLPChunker` opcionalmente e reaproveita `AgentBPMN` sem alteração — não é um agente novo, é um wrapper fino. Salva via `save_bpmn_from_hub()` com vínculo a reunião opcional (selectbox) ou como processo autônomo.
- **Descrever** (BPMN → descrição textual): lógica de `AssistantToolExecutor.describe_bpmn_process()` extraída para `modules/bpmn_describer.py::describe_bpmn_from_xml()` — pura, sem acesso a banco, funciona com qualquer XML colado ou salvo. `describe_bpmn_process()` passou a delegar para essa função (refatoração verificada byte-a-byte idêntica ao comportamento anterior).

**Migração de schema necessária e aplicada:** `bpmn_versions.meeting_id` era `NOT NULL`, impossibilitando salvar uma versão sem reunião vinculada — bloqueador real identificado no plano. `setup/supabase_migration_bpmn_studio.sql` (`ALTER TABLE ... DROP NOT NULL`) executada em produção. `save_bpmn_from_hub()` e `_find_or_create_bpmn_process()` aceitam `meeting_id=None`; guard adicionado para não sobrescrever `last_meeting_id` com `None` ao salvar uma versão sem reunião.

- [x] `core/agent_registry.py` — entrada `bpmn_studio` on-demand (`pipeline_step: None`, `authority_level: "draft"`, reaproveita `skills/skill_bpmn.md`)
- [x] `app.py` — página registrada no grupo Pipeline
- [x] Verificação ponta-a-ponta com chamada LLM mockada na fronteira de rede (sem chave de API real disponível fora da sessão Streamlit ao vivo): hub sintético → NLPChunker → AgentBPMN → XML/Mermaid válidos → encadeado com sucesso em `describe_bpmn_from_xml()`
- [x] 345/345 testes passando

### PC117 — Concluído (v5.14 / 2026-07-03) — fix diagrama BPMN volta ao anterior após reprocessar + salvar (Modo B)

**Diagnóstico:** No Modo B (Reunião Existente), o botão "Salvar" chamava `save_bpmn_from_hub()` sem `bpmn_process_id`, caindo sempre na resolução por `slug(hub.bpmn.name)`. Reprocessar o agente BPMN pode mudar o nome inferido do processo o suficiente para o slug não bater mais com o processo já vinculado à reunião — criando um `bpmn_processes` órfão e uma segunda linha `is_current=True` para a mesma reunião. `load_meeting_as_hub()` fazia `.limit(1)` sem `ORDER BY`, então qual das duas linhas "current" voltava ao recarregar era não-determinístico. Diagnóstico em produção: **14 de 32 reuniões com `bpmn_versions` duplicadas em `is_current=True`** (uma com 4 linhas).

- [x] **`core/knowledge_hub.py`** — `BPMNModel.db_process_id` (novo campo) + guard em `migrate()`
- [x] **`core/project_store.py`** — `load_meeting_as_hub()` popula `db_process_id`; query de BPMN ganha `ORDER BY created_at DESC` antes do `LIMIT 1` (hardening — neutraliza o sintoma mesmo para as 14 reuniões já afetadas, sem migração de dados)
- [x] **`pages/Pipeline.py`** — Modo B passa `bpmn_process_id=hub.bpmn.db_process_id` explicitamente ao salvar, eliminando a resolução por slug para reuniões com processo já conhecido
- [x] 345/345 testes passando

### PC116 — Plano (não implementado, 2026-07-02) — BPMN Studio

Plano de melhoria em `melhorias/bpmn-studio.md`: gerar BPMN 2.0 + Mermaid a partir de descrição de processo em texto livre (fora do fluxo de reunião), com opção de salvar versionado e vincular a uma reunião existente; caminho inverso (BPMN → descrição textual). Levantamento técnico já identifica reaproveitamento de `AgentBPMN` via hub sintético e um bloqueador real de schema (`bpmn_versions.meeting_id` `NOT NULL` — impede salvar sem reunião vinculada).

### PC115 — Concluído (v5.14 / 2026-07-02) — split de core/assistant_tools.py em 7 módulos por domínio

`core/assistant_tools.py` (13.827 linhas) dividido: `AssistantToolExecutor` passa a herdar de 7 mixins em `core/tools/` (tools_meetings_requirements, tools_bpmn_sbvr, tools_meeting_ops_calendar, tools_admin_charts_entities, tools_documents_ibis_diagrams, tools_knowledge_requirements2, tools_executive_advanced), cada um com seus métodos + schemas OpenAI (`*_SCHEMAS`) correspondentes. Arquivo principal caiu para ~830 linhas (só `__init__`, `execute()` dispatch, e getters de schema/catálogo). Split feito por script (AST-driven), não manual. Efeito colateral: removidos 2 métodos mortos (`rename_meeting`/`batch_rename_meetings` definidos duas vezes na mesma classe — a segunda definição sempre sobrescrevia a primeira silenciosamente).

- [x] Reorganização de pastas da raiz (`notes/`, `test-scenarios/`) + limpeza de `.pyc` versionados e worktree órfão
- [x] Exportação HTML da conversa do Assistente passa a incluir diagramas BPMN/Mermaid e demais widgets A2UI (antes só texto + gráficos Plotly)
- [x] Generalização de material comercial (`static/apresentacao-geral.html`, `outputs/apresentacao_executiva_p2d.html` — ex-FGV) para uso com qualquer cliente

### PC113–PC114 — Concluído (v5.13 / 2026-06-30 a 2026-07-01) — Infraestrutura Google Cloud + Governança v5.11

PC113: `Dockerfile` multi-stage (builder + runtime, Python 3.13-slim, spaCy lg baked, non-root), `.dockerignore`, `infra/cloudrun/service.yaml` (Cloud Run declarativo, Secret Manager, probes), `infra/cloudrun/env.template.yaml`, `infra/cloudbuild.yaml` (CI/CD: build → push Artifact Registry → deploy Cloud Run).

PC114: API Google Cloud completa — Secret Manager 4 camadas, Cloud Tasks com fallback síncrono, endpoints `/api/v1/projects` + `/api/v1/process` + `/internal/run`, `Dockerfile` usando `requirements.api.txt`, 345 testes passando.

Governança v5.11: `COLLABORATIVE_MANIFESTO.md` assinado por 5 agentes (30/06/2026) — n8n formalizado como Agente 4, modelo de negócio definido (Starter/Pro/Enterprise), hierarquia LLM com custos reais BRL.

---

### PC112-K — Concluído (v5.12 / 2026-06-30) — fix setIn ao carregar reunião: mermaid bloqueante

**Diagnóstico:** `render_mermaid_block()` fazia 2 chamadas HTTP sequenciais para `mermaid.ink`
(timeout 15s cada = até 30s de bloqueio no thread do script). Na primeira renderização do hub após
carregar reunião do banco, o WebSocket ficava ocioso durante o bloqueio. Se a conexão caía e o
cliente reconectava com árvore vazia, o servidor continuava enviando deltas a partir do índice 2+
→ `Bad 'setIn' index 2 (should be between [0, 0])`.

**Correções:**
- [x] **`modules/mermaid_renderer.py`**:
  - Timeout reduzido de 15s → 5s por fetch (fail-fast)
  - Fetches paralelos via `ThreadPoolExecutor(max_workers=2)` — bloqueio máximo 5s (era 30s)
  - Cache em `st.session_state` por hash MD5 do mermaid_text — reruns seguintes: 0ms
- [x] **`modules/bpmn_viewer.py`**:
  - `_load_bpmn_assets()`: lê `static/bpmn-viewer.production.min.js` se presente → elimina
    fetch de 500KB do internet na primeira renderização (era ~8s)
  - CSS ainda fetched do CDN em paralelo (3 arquivos pequenos, rápido)

---

### PC88 — Concluído (v4.79 / 2026-06-28) — PC83+PC84 compliance nos agentes pipeline restantes

- [x] **`core/output_schemas.py`** — 4 novos schemas Pydantic v2 (fail-open, extra='allow'):
  - `ArgumentationOutputSchema` (+ `IBISQuestionSchema`, `IBISAlternativeSchema`, `IBISResolutionSchema`)
  - `CommunicationNoiseOutputSchema` (+ `AmbiguityItemSchema`, `CommunicationGapSchema`)
  - `KnowledgeExtractorOutputSchema` (+ `KHEntitySchema`, `KHProcessSchema`, `KHFactSchema`, `KHContradictionSchema`)
  - `QuerySummaryOutputSchema` (+ `PerspectiveSummarySchema`)

- [x] **`agents/agent_argumentation.py`** — `required_hub_fields = ["transcript_clean"]` + `output_schema = ArgumentationOutputSchema`
- [x] **`agents/agent_communication_noise.py`** — `required_hub_fields = ["transcript_clean"]` + `output_schema = CommunicationNoiseOutputSchema`
- [x] **`agents/agent_knowledge_extractor.py`** — `required_hub_fields = ["transcript_clean"]` + `output_schema = KnowledgeExtractorOutputSchema`
- [x] **`agents/agent_query_summarizer.py`** — `required_hub_fields = []` + `output_schema = QuerySummaryOutputSchema`
- [x] **`agents/agent_ckf_updater.py`** — `required_hub_fields = []` (Markdown output — sem output_schema)

Agentes isentos (padrão não-padrão):
- `agent_bpmn_reviewer` — Markdown output, on-demand, `_MinimalHub` stub
- `agent_contradiction_detector` / `agent_entity_consolidator` — entry points próprios, hub stubs internos
- `agent_meeting_namer` / `agent_req_reconciler` — `skill_path = None`, prompts inline

**Resultado:** 56/56 testes existentes passando; 4 novos schemas + 5 agentes com compliance completa.

---

### PC102 — Concluído (v4.78 / 2026-06-28) — skill improvements batch 4: query_summarizer, ner, analyst, context_template

- [x] **`skills/skill_query_summarizer.md`** v1.0 → v1.1: move `{output_language}` to Rules section; add perspective differentiation guide table
- [x] **`skills/skill_ner.md`** v1.0 → v1.1: add difficult cases guide (pronouns, company names, ASR distortion, name deduplication)
- [x] **`skills/skill_analyst.md`** v1.0 → v1.1: add tool call efficiency rule, quality criteria section (evidence/facts/specificity)
- [x] **`skills/skill_context_template.md`**: add YAML frontmatter v1.0 (user-editable template — content unchanged)

---

### PC101 — Concluído (v4.77 / 2026-06-28) — skill improvements batch 3: document_extractor, cross_doc_analyzer

- [x] **`skills/skill_document_extractor.md`** v1.0 → v1.1: add 5-pass extraction method; harmonize `req_type`/`priority` to PT pipeline schema (Funcional/Não-Funcional/Negócio/Restrição/Qualidade and Alta/Média/Baixa); add `{output_language}` in Rules with 7 formal rules
- [x] **`skills/skill_cross_doc_analyzer.md`** v1.0 → v1.1: add Rules section with `{output_language}` and 5 formal rules; clarify `gaps` key requirements

---

### PC100 — Concluído (v4.76 / 2026-06-28) — skill improvements batch 2: knowledge_extractor, contradiction_detector, communication_noise, document_analyzer

- [x] **`skills/skill_knowledge_extractor.md`** v1.0 → v1.1: add calibration table (include vs omit per entity/fact type); Regras section with `{output_language}`
- [x] **`skills/skill_contradiction_detector.md`** v1.0 → v1.1: add Regras section with `{output_language}` + 7 formal rules
- [x] **`skills/skill_communication_noise.md`** v1.0 → v1.1: add per-type examples table for ambiguities and gaps
- [x] **`skills/skill_document_analyzer.md`** v1.0 → v1.1: add 6-step analysis method (inventory → req mapping → process alignment → stakeholders → decisions → synthesis)

---

### PC99 — Concluído (v4.75 / 2026-06-28) — skill improvements batch 1: transcript_quality, argumentation, ckf_updater, entity_consolidator

- [x] **`skills/skill_transcript_quality.md`** v1.0 → v2.0: add `overall_score`, `grade`, `artifact_ratio`, `metadata_issues` to JSON schema; add Weighted Score Formula section; add `{output_language}` in Rules
- [x] **`skills/skill_argumentation.md`** v1.0 → v2.0: fix all missing Portuguese accents throughout; add signal recognition table, meeting type calibration table, `## Regras` section with `{output_language}`; add `confidence` field to each question
- [x] **`skills/skill_ckf_updater.md`** v1.0 → v2.0: full rewrite — section-by-section guidance for all 7 CKF sections, conflict handling table (5 scenarios), update conventions, 5-item checklist
- [x] **`skills/skill_entity_consolidator.md`** v1.0 → v2.0: full rewrite — similarity scoring table, 0.80 fusion threshold, edge case guide, examples table, `confidence` field in output

---

### PC98 — Concluído (v4.74 / 2026-06-28) — skill_sbvr.md v2.1 — SBVR vs DMN, enforcement, Exemplo C

- [x] **`skills/skill_sbvr.md`** — v2.0 (518 linhas) → v2.1 (662 linhas), edições cirúrgicas
  - Fronteira SBVR vs DMN: tabela detalhada com 5 padrões e regra prática ("3+ variações → avalie DMN")
  - Campo `enforcement` (opcional): automated / manual / contractual / regulatory com orientação de preenchimento
  - Campo `bmm_policy_ref` documentado: quando e como usar para rastreabilidade SBVR↔BMM
  - Seção `## Regras` adicionada; `{output_language}` solto removido do final
  - JSON schema atualizado com `enforcement` como campo opcional
  - Checklist expandido com 3 novos itens (DMN boundary, enforcement, bmm_policy_ref)
  - Exemplo C: kickoff técnico com regras regulatórias (BACEN 4.557, LGPD, KMS, DPO) demonstrando enforcement regulatory/automated/manual e a decisão de NÃO extrair a regra de score como SBVR (→ DMN)

---

### PC97 — Concluído (v4.73 / 2026-06-28) — skill_bmm.md v2.1 — Cadeia BMM, modal, deadline, Exemplo C

- [x] **`skills/skill_bmm.md`** — v2.0 (446 linhas) → v2.1 (586 linhas), edições cirúrgicas
  - Seção "Cadeia de Rastreabilidade BMM" explicando por que `supports` é obrigatório (diagrama Fins←Meios)
  - Campo opcional `deadline` para metas com prazo explícito na transcrição
  - Campo `modal` obrigatório em políticas: `must` / `must_not` / `may` com tabela de exemplos
  - Seção `## Regras` adicionada com output_language e regras de conservadorismo
  - `{output_language}` removido do final solto — integrado à seção Regras
  - JSON schema atualizado com `deadline` em goals e `modal` em policies
  - Exemplo C — kickoff estratégico (Meridional-style): visão explícita, 4 metas mistas, 3 políticas com modals distintos, 1 influenciador weakness quantificado; com notas explicando cada decisão de classificação

---

### PC96 — Concluído (v4.72 / 2026-06-27) — SKILL_SYNTHESIZER.md v3.0 — Narrativa Executiva Calibrada

- [x] **`skills/SKILL_SYNTHESIZER.md`** — reescrito de v2.0 (77 linhas) para v3.0 (208 linhas)
  - Persona expandida com audiência explícita (diretores/gestores não-presentes)
  - Tabela de inputs com coluna "quando presente, priorize" (antes: coluna "obrigatória")
  - Método de síntese em 4 passos: inventário, temas transversais, calibração por riqueza, ordem de redação
  - Calibração por riqueza: tabela com 5 cenários (BPMN isolado → todos os 6 inputs)
  - Checklist pré-retorno de 6 itens
  - Guia por campo com estrutura de parágrafos para `executive_summary` (5 §)
  - Arc narrativo para `process_narrative` (abertura, corpo, fechamento, exceções)
  - Taxonomia de insights em 7 categorias com exemplos concretos
  - Guia de recomendações SMART com exemplos ✗/✓
  - Integração SBVR: usar termos do domínio no corpo do texto (não listar separado)
  - Integração BMM: §1 do summary + key_insights de alinhamento + recomendações coerentes
  - Anti-padrões: tabela de termos proibidos + estruturas de insight proibidas

---

### PC95 — Concluído (v4.71 / 2026-06-27) — skill_bpmn.md v9.1 — Anti-Omissão: Alçada, Timer, Notificação, Log

- [x] **`skills/skill_bpmn.md`** — v9.0 (952 linhas) → v9.1 (1002 linhas)
  - Diagnóstico por regressão real (transcrição Grupo Meridional / Projeto AURORA)
  - Gateway de alçada adicionado à tabela 4.1 de detecção de gateways faltantes
  - Seção 3e "Padrões Implícitos de Alta Frequência" (4 padrões sistemáticos):
    - SLA de tarefa ("em menos de 30s") → `boundaryTimerEvent` com exemplo JSON
    - Notificações ("enviar e-mail/SMS") → tarefa explícita antes do End Event
    - Logs de auditoria ("log auditável", "audit trail") → `serviceTask` de registro
    - Regras de alçada ("até R$X / de R$X a R$Y") → gateway com N saídas por nível
  - Checklist Passo 6 "Completude e Fechamento": 4 novos itens (alçada, SLA, notificação, log)
  - Checklist Passo 7.2 "Perguntas de integridade": 4 novos itens correspondentes

---

### PC94 — Concluído (v4.70 / 2026-06-27) — skill_bpmn.md v9.0 — Cobertura BPMN 2.0 OMG §10 Completa

- [x] **`skills/skill_bpmn.md`** — v8.0 (873 linhas) → v9.0 (952 linhas), edições cirúrgicas
  - `description:` adicionado ao frontmatter
  - Signal events na tabela de eventos: `intermediateCatchSignalEvent`, `intermediateThrowSignalEvent`, `escalationBoundaryEvent`
  - `subProcess` e `eventSubProcess` na tabela de task_types
  - Nova seção 3d: `subProcess` vs `callActivity` — distinção crítica com tabela de critérios
  - Black box pool documentado: pool com entidade externa sem processo conhecido (`steps: []`)
  - `is_interrupting: false` documentado com campo JSON e exemplo de boundary não-interrompente
  - Distinção crítica XOR vs OR (`exclusiveGateway` vs `inclusiveGateway`) com tabela de critérios e regra rápida
  - OR join obrigatório: `inclusiveGateway` split exige join que sincroniza apenas caminhos ativos
  - Exemplo concreto de `eventBasedGateway` com JSON e armadilha documentada
  - Checklist expandido com 6 novos itens (subProcess, is_interrupting, OR vs XOR, signal pairs, black box)

---

### PC93 — Concluído (v4.69 / 2026-06-27) — SKILL_REQUIREMENTS.md v2.0 — Cobertura IEEE 830 / ISO/IEC 29148

- [x] **`skills/SKILL_REQUIREMENTS.md`** — reescrito de v1.0 (100 linhas) para v2.0 (201 linhas)
  - Persona com fronteiras explícitas de escopo (✅ extrai / ❌ não extrai)
  - Convenção de iniciais de participantes (padrão compartilhado com skill_minutes.md)
  - Método de extração em 5 passos: leitura completa, domínio, classificação, IEEE 830, checklist
  - 6 tipos de requisito (adiciona `integration`) com tabela de sinais típicos
  - Tabela distinção crítica `validation` vs `business_rule` com teste diagnóstico
  - Tabela distinção crítica `functional` vs `non_functional`
  - Regra de atomicidade com exemplos de decomposição (campo CNPJ → 4 requisitos)
  - Tabela "O que NÃO Extrair" (6 linhas: BPMN/SBVR/BMM/ata/action items/problemas)
  - Documentação de campos `sphere` e `business_rule_refs` (antes implícitos)
  - Critérios de qualidade IEEE 830: específico, verificável, rastreável, não-ambíguo
  - Checklist final (5 itens) no Passo 4

---

### PC92 — Concluído (v4.68 / 2026-06-27) — skill_minutes.md v2.0

- [x] **`skills/skill_minutes.md`** — reescrito de v1.0 (190 linhas) para v2.0 (244 linhas)
  - Método de extração em 5 passos sequenciais
  - Passo 0: leitura completa obrigatória + tabela de tipos de reunião (8 tipos) com calibração de ênfase
  - Passo 3: formulação padrão de decisões (declarativa/passado) com exemplos ✓/✗
  - Tabela de distinção crítica Decisão vs Action Item (natureza, responsável, tempo, verificação)
  - Regra de não-duplicação entre decisões e action items
  - Calibração de densidade do resumo por contexto (4 cenários)
  - Antipadrões em formato de tabela com coluna "como identificar"
  - Regra 6 explícita: sem duplicação entre campos

---

### PC91 — Concluído (v4.67 / 2026-06-27) — skill_bpmn_reviewer.md v2.0

- [x] **`skills/skill_bpmn_reviewer.md`** — reescrito de v1.0 (242 linhas) para v2.0 (328 linhas)
  - Português com acentos corretos (v1.0 sem acentos)
  - 3 níveis de severidade: 🔴 Crítico (−2 pts), ❌ Violação (−0,5 pt), ⚠️ Atenção
  - Cálculo explícito do score com regra: score_max=5 se houver qualquer crítico
  - Checklist expandido de 25 → 38 itens em 8 seções (adiciona Eventos, Colaboração)
  - Novos itens críticos: gateway com 1 saída, AND-fork sem AND-join, dead end, elemento órfão
  - Novos itens de violação: sendTask/receiveTask fora de pools, message_flow dentro do mesmo pool, coreografia desbalanceada, End Event na lane errada em aprovações, Traceability Label Rule
  - Seção "Quando NÃO gerar JSON" (> 5 críticos, intenção não inferível, colaboração complexa)
  - Checklist pré-retorno do JSON na Fase 4

---

### PC90 — Concluído (v4.66 / 2026-06-27) — skill_sbvr.md v2.0 — Cobertura Normativa SBVR 1.5

- [x] **`skills/skill_sbvr.md`** — reescrito de v1.0 (111 linhas, inglês) para v2.0 (517 linhas, PT)
  - Tabela de distinções SBVR vs BMM vs DMN vs BPMN com regra de ouro
  - 5 categorias de vocabulário: concept, fact_type, role, process, **individual** (novo)
  - 5 padrões formais de formulação SBVR com templates: obrigação, proibição, permissão, condicional, estrutural
  - Regra de atomicidade com exemplos de decomposição de afirmações compostas
  - 5 `rule_type`: constraint, permission, behavioral, structural, **conditional** (novo)
  - Tabela expandida de `short_title` com 5 exemplos de inferência
  - Checklist de qualidade (12 critérios) em 3 categorias
  - 2 exemplos anotados completos: compras/fornecedores e contratos/compliance

---

### PC89 — Concluído (v4.65 / 2026-06-27) — skill_bmm.md v2.0 — Cobertura Normativa BMM 1.3

- [x] **`skills/skill_bmm.md`** — reescrito de v1.0 (83 linhas, inglês) para v2.0 (445 linhas, PT)
  - Tabela de construtos BMM: Fins (Visão/Missão/Meta) e Meios (Estratégia/Política)
  - 4 distinções críticas com anti-padrões: Vision vs Mission, Meta vs Estratégia, Estratégia vs Política, Política vs SBVR
  - Método de extração em 6 passos com sinais de reconhecimento por artefato
  - `category` de políticas expandido de 4 para 6 (adiciona `strategic` e `people`)
  - Campo `influencers` (opcional, SWOT) com tipos e `impact_on` (extra=allow no schema)
  - Checklist de qualidade (15 critérios): integridade, distinções, conservadorismo
  - 2 exemplos anotados: planejamento estratégico completo e reunião operacional

---

### PC88 — Concluído (v4.64 / 2026-06-27) — skill_dmn.md v2.0 — Cobertura Normativa DMN 1.4

- [x] **`skills/skill_dmn.md`** — reescrito de v1.1 (115 linhas) para v2.0 (569 linhas)
  - Todas as 11 variantes de hit policy: U, A, F, P, R, C, C+, C<, C>, C#, O com semântica exata
  - Árvore de decisão para seleção de hit policy
  - Referência completa FEEL: intervalos `[N..M]`/`(N..M]`, listas (OR), negação, wildcard
  - Regras de completude e sobreposição para hit policy U
  - DRD: campo `depends_on` para decisões em cadeia
  - Multi-output: campo `outputs` (lista) para tabelas com 2+ colunas de output
  - Checklist de qualidade (15 critérios) por categoria
  - 4 exemplos anotados: F com exceção, U multi-output, C+ acumulativo, DRD em cadeia

---

### PC84 — Concluído (v4.62 / 2026-06-27) — Output Schemas com Pydantic v2

- [x] **`core/output_schemas.py`** — 7 schemas Pydantic v2 fail-open (`_PermissiveModel` com `extra='allow'`):
  - `BPMNOutputSchema` — `name` obrigatório; suporta flat (`steps`/`edges`/`lanes`) e collaboration (`pools`/`message_flows`)
  - `MinutesOutputSchema` — todos os campos opcionais com defaults
  - `RequirementsOutputSchema` — `requirements` obrigatório e não-vazio
  - `SBVROutputSchema` — `vocabulary` + `rules` com listas
  - `BMMOutputSchema` — visão/missão/metas/estratégias/políticas
  - `TranscriptQualityOutputSchema` — `criteria` obrigatório; `grade` validado em A–E
  - `SynthesizerOutputSchema` — `executive_summary` obrigatório
- [x] **`agents/base_agent.py`** — `output_schema = None` class attr; `_call_with_retry()` chama `schema.model_validate(data)` e `warnings.warn()` em falha — pipeline nunca bloqueado
- [x] **7 agentes** — `output_schema = XxxOutputSchema` + import de `core.output_schemas`
- [x] **`requirements.txt`** — `pydantic==2.12.5` fixado explicitamente

---

### PC83 — Concluído (v4.61 / 2026-06-27) — Skill Version em Telemetria + Pré-condições

- [x] **`services/llm_telemetry.py`** — `TelemetryRecord.skill_version: Optional[str]`; campo incluído em `_write()` e `query()` select
- [x] **`setup/supabase_migration_skill_version.sql`** — `ALTER TABLE llm_telemetry ADD COLUMN IF NOT EXISTS skill_version TEXT` + índice parcial — **migração executada**
- [x] **`agents/base_agent.py`** — `self.skill_version` setado por `_load_skill()` via parse de `version:` no YAML frontmatter; passado ao `TelemetryRecord` em `_call_with_retry()`
- [x] **Pré-condições** — `required_hub_fields: list = []` class attr; `_check_preconditions(hub)` valida dot-paths (`transcript_clean`, `bpmn.ready`) antes de `run()`; 7 agentes com seus campos declarados

---

### PC82 — Concluído (v4.60 / 2026-06-27) — Pseudonimização Reversível de Nomes (Tier-2 PII)

**Contexto:** Decisão de design anterior mantinha nomes reais nas chamadas LLM (necessários para lanes BPMN). PC82 implementa pseudonimização reversível com iniciais — nomes não saem no wire para APIs externas, mas são restaurados nos artefatos antes de qualquer persistência (RAG preservado).

- [x] **`modules/pii_sanitizer.py`** — Tier-2 adicionado ao módulo existente (backward-compat total):
  - `detect_names(text) -> dict[str, str]` — spaCy `pt_core_news_lg` NER; apenas nomes com >=2 palavras; desambiguação de colisões de iniciais (PG -> PGOMES -> PG2); cap 50k chars; fail-open (retorna {} se spaCy indisponível)
  - `sanitize(text, name_map=None)` — novo arg opcional; nomes substituídos antes de PII estruturado (longest-match first); variantes título+sobrenome ("Sr. Gentil" -> [PESSOA:PG]); token_map unificado Tier1+Tier2
  - Token format `[PESSOA:XX]` — >95% de preservação pelo LLM vs ~70% para `{}`
  - `desanitize()` inalterado — já lida com ambos os tipos de token
- [x] **`core/knowledge_hub.py`** — `SessionMetadata.name_map: dict` (token -> nome original); guard em `migrate()` para sessões existentes
- [x] **`agents/base_agent.py`** — `_call_llm()` integrado: lê `hub.meta.name_map` (fail-safe getattr); passa para `sanitize()`; injeta `_NOME_INSTRUCTION` no system prompt quando name_map não-vazio; guard idempotente `_NOME_PRIVACY_MARKER` previne duplicação em retries
- [x] **`pages/Pipeline.py`** — `detect_names(hub.transcript_clean)` chamado uma vez antes de `run_pipeline()`; resultado salvo em `hub.meta.name_map`; fail-open

**Fluxo:** transcript (nomes reais) -> detect_names() -> hub.meta.name_map -> por chamada LLM: sanitize(user, name_map) -> API externa vê [PESSOA:PG] -> desanitize(raw, token_map) -> artefatos com nomes reais -> Supabase (RAG preservado)

**Decisões de design:** mapa em memória apenas (nunca persiste no Supabase); nomes reais no banco (RAG funciona); nomes parciais (primeiro nome isolado) fora do MVP (ambíguos para regex segura)

---

### PC81 — Concluído (v4.59) — LGPD Compliance Layer (Sprint 1 + 2)
- [x] `modules/compliance/` package: `detector.py`, `audit.py`, `consent.py`, `__init__.py`
- [x] `detector.py` — PII classification only (CPF, CNPJ, EMAIL, TEL, VALOR via regex + NOME_PESSOA via spaCy NER); no anonymization; `PIIDetectionResult` with `risk_level` (low/medium/high)
- [x] `audit.py` — async daemon thread write to `compliance_audit` table; fail-open; supports: `pipeline_run`, `consent_granted`, `data_accessed`, `data_deleted`, `pii_detected`
- [x] `consent.py` — post-pipeline LGPD consent panel (`render_consent_panel()`); legal basis dropdown (4 options); participant type radio; retention slider (30–365 days); saves to `compliance_consent` + triggers audit event
- [x] `pages/Pipeline.py` — two hooks: (1) after `save_meeting_artifacts()`: runs `detect_pii()`, caches result in session_state, logs `pipeline_run` audit; (2) before tabs: renders `render_consent_panel()` (fail-open wrapper)
- [x] `setup/supabase_migration_compliance.sql` — `compliance_consent` + `compliance_audit` tables with FK cascade, indexes, COMMENT metadata
- Architecture: consent form shown AFTER pipeline saves (meeting_id available) — solves chicken-and-egg; spaCy reuses same lazy-load cache pattern as nlp_chunker; panel is non-blocking (expander, expanded only on high-risk); all compliance ops fail-open

---

### PC1 — Concluído (v3.4)
- [x] Pipeline sequencial: Quality → Preprocessor → NLP → BPMN → Minutes → Requirements → Synthesizer
- [x] BPMN 2.0 XML com layout absoluto, pools/lanes, Link Events
- [x] `_enforce_rules()` — defesa programática contra erros LLM de lane/gateway
- [x] Backward-flow U-routing em `_build_di` — sem invasão visual de elementos
- [x] `AgentRequirements` — 5 tipos IEEE 830, speaker attribution por citação
- [x] `AgentTranscriptQuality` — grade A–E, critérios ponderados, recomendação
- [x] `AgentSynthesizer` — relatório executivo HTML interativo (sidebar, colapsável, filtros, comentários, localStorage)
- [x] Minutes com transcrição completa + iniciais de participantes
- [x] Export da Ata em Markdown, Word (.docx) e PDF
- [x] `KnowledgeHub.migrate()` para evolução de schema sem quebrar sessões
- [x] `_load_skill()` com path absoluto — resolve CWD e case-sensitivity no Linux

### PC2 — Concluído (v4.6 → v4.7)
- [x] `AgentValidator` — pure-Python BPMN quality scorer (granularity, task type, gateways)
- [x] Multi-run BPMN optimization (1/3/5 passes, weighted scoring, best candidate selection)
- [x] UI modularizada: `ui/sidebar.py`, `ui/input_area.py`, `ui/tabs/*`, `ui/components/*`
- [x] `core/pipeline.py`, `core/session_state.py`, `core/rerun_handlers.py` — separação de responsabilidades
- [x] `services/` package — export_service, file_ingest, preprocessor_service
- [x] Re-execução individual de agentes (sidebar + corpo principal)
- [x] `MermaidGenerator` classe — sanitização robusta, sem LLM
- [x] `modules/mermaid_renderer.py` — `render_mermaid_block()` compartilhado (pan/zoom/fit, TD/LR toggle)
- [x] `modules/requirements_mindmap.py` + `modules/mindmap_interactive.py` — mind map interativo de requisitos
- [x] `pages/Diagramas.py` — visualizador full-screen multi-diagrama (BPMN, Mermaid, Mind Map)
- [x] `modules/bpmn_diagnostics.py` — painel de diagnóstico BPMN isolado
- [x] Upload suporta `.txt`, `.docx`, `.pdf`
- [x] Pré-processamento com curadoria editável antes de executar o pipeline

### PC2.1 — Melhorias BPMN (v4.7)
- [x] Mermaid edge label syntax corrigido (`-->|label|` em vez de `-- label -->`) em single e multi-pool
- [x] `_enforce_rules` Rule 2 expandida para todos os tipos de gateway, não só `is_decision`
- [x] `_infer_lane_name` — três prioridades: actor fields → NLP actors → regex; recebe `hub.nlp.actors`
- [x] `modules/bpmn_structural_validator.py` — 6 verificações estruturais (dangling refs, isolated/unreachable nodes, XOR sem labels, AND/OR sem join, gateway com saída única)
- [x] Diagnóstico estrutural exibido no tab BPMN como expander com severidade (error/warning/info)
- [x] `_align_parallel_branches` no gerador de layout — elimina setas longas em branches paralelas desiguais
- [x] `AgentMinutes` + `AgentRequirements` executados em paralelo via `ThreadPoolExecutor` — hub shallow-copied com `meta` isolado por worker; deltas de token mergeados; fallback automático para sequencial; `threading.Lock` protege o progress callback

### PC3 — Concluído
- [x] `AgentSBVR` — OMG SBVR extraction: business vocabulary (5–15 terms) + business rules (3–10); default OFF; skills/skill_sbvr.md
- [x] `AgentBMM` — OMG BMM extraction: vision, mission, goals, strategies (with goal links), policies; default OFF; skills/skill_bmm.md
- [x] Suite de testes automatizados — 106 tests, 0 LLM calls; covers auto-repair, structural validator, AgentValidator, MermaidGenerator
- [x] LangGraph integration — adaptive BPMN retry loop (`core/lg_pipeline.py`); opt-in "🔄 Adaptive Retry" checkbox (single-pass mode only); configurable quality threshold (0–10, default 6.0) and max retries (1/2/3/5, default 3); best-scoring candidate committed to hub; `hub.bpmn.lg_attempts` + `hub.bpmn.lg_final_score` shown in BPMN tab

### PC4 — Concluído (v4.8 → v4.11)
- [x] **Authentication layer** — `modules/auth.py` + `ui/auth_gate.py`; SHA-256 session-based login gate; all pages protected; credentials hardcoded (no secrets.toml dependency for auth)
- [x] **Supabase integration** — `modules/supabase_client.py` + `core/project_store.py`; CRUD for projects, meetings, requirements, transcript chunks; fail-open when unconfigured
- [x] **Embedding pipeline** — `modules/embeddings.py`; `chunk_text()` + `embed_text()` + `embed_batch()`; Google Gemini (`gemini-embedding-001`) and OpenAI (`text-embedding-3-small`); 1536 dims; auto-retry on 429 with extracted retry_delay; 1.2s inter-call delay for free tier
- [x] **Supabase schema** — `setup/supabase_schema_transcript_chunks.sql`; `transcript_chunks` table with `vector(1536)` column; `ivfflat` cosine index; `match_transcript_chunks()` SQL function for semantic search
- [x] **`pages/Assistente.py`** — RAG-powered Q&A over meeting transcripts; keyword search + semantic search via `match_transcript_chunks`; embedding generation; re-edit feature (✏️ button, history truncation, `_resubmit_question` pattern)
- [x] **Tool-use mode** — `core/assistant_tools.py`; `AssistantToolExecutor` with 10 tools; `get_tool_schemas_openai()` + `get_tool_schemas_anthropic()`; `AgentAssistant.chat_with_tools()` with ≤5-round loop; automatic fallback to classic RAG on exception
- [x] **RAG quality improvement** — `project_store._extract_minutes_summary()` injects Participantes/Pauta/Decisões unconditionally in `format_context()`
- [x] **`pages/BatchRunner.py`**, **`pages/BpmnBackfill.py`**, **`pages/ReqTracker.py`**, **`pages/TranscriptBackfill.py`**, **`pages/CostEstimator.py`**
- [x] **`ui/project_selector.py`**, **`ui/assistant_diagram.py`**, **`modules/cost_estimator.py`**, **`modules/text_utils.py`**, **`modules/reqtracker_exporter.py`**
- [x] **Google Gemini SDK migration** — `google-generativeai` for `embed_content()` + `list_models()`; `google-genai` kept as secondary

### PC5 — Concluído (v4.12)
- [x] **ROI-TR sensível ao tipo de reunião** — `modules/meeting_roi_calculator.py` v2; 11 tipos, TYPE_WEIGHTS matrix; DC ponderado substitui fórmula linear fixa
- [x] **`classify_meeting_type()`** — classificação LLM; 1 chamada por reunião; JSON `{type, confidence}`; fallback heurístico; resultado persistido em `meetings.meeting_type`
- [x] **`fulfillment_score`** — indicador 0–1: DC gerado / DC mínimo esperado para o tipo
- [x] **`MeetingROIData` v2** — campos: `meeting_type`, `meeting_type_confidence`, `fulfillment_score`, `n_sbvr`, `n_bpmn_procs`
- [x] **`compute_project_roi()` v2** — busca SBVR + BPMN por meeting; retrocompatível sem coluna `meeting_type`
- [x] **`pages/MeetingROI.py` v2** — sidebar com classificação IA; 6 KPIs; gráfico de Fulfillment; pesos por artefato no detalhe
- [x] **`delete_meeting` fix** — cascade limpo: `requirement_versions` → nullify FK → `sbvr_terms/rules/transcript_chunks` → `bpmn_versions` → `bpmn_processes` → `meetings`
- [x] **SQL migração** — `ALTER TABLE meetings ADD COLUMN IF NOT EXISTS meeting_type TEXT`

### PC6 — Concluído (v4.13)
- [x] **Navegação reestruturada** — `app.py` migrado para `st.navigation()` com 4 grupos; pipeline movido para `pages/Pipeline.py`
- [x] **Sidebar simplificada** — opções avançadas em `st.expander("⚙️ Configuração Avançada")`; apenas provider + API key + idioma sempre visíveis
- [x] **Tabs do Pipeline reorganizadas** — abas primárias + "🔬 Análise Avançada" em expander; re-run buttons exclusivos na sidebar
- [x] **DatabaseOverview** — health score panel, KPI cards, 5 expanders de correção inline
- [x] **DatabaseOverview — aba 🔮 Embeddings** — gestão completa: cobertura por projeto, geração em lote, drill-down por reunião, teste de gravação
- [x] **RBAC no Assistente** — `is_admin()` aceita `admin` e `master`; admin gate em `AssistantToolExecutor.execute()`
- [x] **3 novas ferramentas admin** — `get_database_integrity()`, `fix_missing_llm_provider()`, `generate_meeting_embeddings()`
- [x] **Tool catalog em Configurações** — expander em Settings → aba Assistente
- [x] **Streamlit 1.42.0 → 1.45.1** — fix "Bad message format"
- [x] **Fix `st.page_link("app.py")`** — corrigido para `pages/Pipeline.py`

### PC7 — Concluído (v4.14)
- [x] **`pages/Home.py`** — header (nome, role badge, tenant, data), 4 KPIs globais, guia de 4 etapas, acesso rápido, reuniões recentes com links contextuais; `@st.cache_data(ttl=60)`
- [x] **`pages/BpmnEditor.py`** — bpmn-js Modeler; seletores projeto/processo/versão; histórico em dataframe; session-state-first paste pattern; salva via `save_bpmn_new_version()`
- [x] **`modules/bpmn_editor.py`** — `editor_from_xml(xml, height)` HTML self-contained; toolbar Ajustar/Desfazer/Refazer/Exportar; `navigator.clipboard` + fallback manual
- [x] **`core/project_store.py` novas funções** — `get_global_stats()`, `list_recent_meetings()`, `list_bpmn_processes()`, `list_bpmn_versions()`, `save_bpmn_new_version()`, `get_bpmn_version()`
- [x] **Navegação atualizada** — grupo "Início" como primeiro; BpmnEditor.py no grupo Pipeline

### PC8 — Concluído (v4.15 / 2026-05-03)
- [x] **`modules/calendar_client.py`** — 8 funções públicas; `_load_calendar_id(project_id)` resolve: Supabase → secrets → arquivo → "primary"
- [x] **9 ferramentas de calendário no Assistente** — `calendar_list_events`, `calendar_get_event`, `calendar_suggest_time` (todos); `calendar_create_event`, `calendar_schedule_action_items`, `calendar_share_with_user`, `calendar_revoke_access`, `calendar_diagnose` (admin)
- [x] **Multi-projeto Google Calendar** — tabela `project_calendar_config`; `get/set/delete/list_project_calendar_id()` em `project_store.py`
- [x] **Compartilhamento de agenda** — `calendar_share_with_user()` via ACL API; requer permissão "owner" da Service Account
- [x] **Contas de integração por usuário** — `tenant_users.google_account` + `tenant_users.ms_teams_account`; `update_user_accounts()` em `tenant_auth.py`
- [x] **Google Calendar embed na Home** — iframe via `_load_calendar_id()`; fallback caption
- [x] **MCP Google Calendar** (`mcp/google_calendar_server.py`) — servidor MCP (8 tools via FastMCP/stdio); timezone bug corrigido (UTC→Sao_Paulo)
- [x] **Documentação de integrações** — `mcp/integration_guide.html`; `CLAUDE_MS365.md`
- [ ] **Microsoft 365 (Outlook + Teams)** — PENDENTE: bloqueado por Azure AD admin consent; plano em `CLAUDE_MS365.md`

### PC9 — Concluído (v4.16 / 2026-05-09)
- [x] **`modules/bpmn_viewer.py` rewrite** — server-side asset fetch via `urllib` + `lru_cache`; bpmn-js native zoom; CDN fallback template
- [x] **`ui/components/copy_button.py` fix** — `navigator.clipboard.writeText()` + execCommand fallback dentro do mesmo user-gesture
- [x] **`ui/components/page_header.py`** (novo) — `render_page_header(icon, title, caption)` com amber accent HR
- [x] **`pages/Pipeline.py`** — progress via `st.status()` context manager
- [x] **`ui/sidebar.py`** — agent checkboxes agrupados; SBVR + BMM rerun buttons; `st.code` → `st.caption` para model display
- [x] **`app.py`** — role-aware navigation; Manutenção + admin pages só quando `is_admin()`
- [x] **BatchRunner reprocess** — `_reprocess_one()` em `core/batch_pipeline.py`; ferramenta `reprocess_meeting_full`

### PC10 — Concluído (v4.17 / 2026-05-11)
- [x] **Gráficos interativos no Assistente** — 5 ferramentas Plotly: `generate_requirements_chart`, `generate_meetings_timeline`, `generate_action_items_chart`, `generate_roi_chart`, `generate_custom_chart`; figs como `fig.to_dict()` em `_pending_charts`; retornadas como 4º elemento de `chat_with_tools()`; renderizadas com `st.plotly_chart()`
- [x] **Paleta de cores configurável** — `core/chart_config.py` (zero imports); 6 paletas nomeadas; `AssistantToolExecutor.__init__` lê `chart_palette` de `llm_config`; selectbox + swatches na sidebar do Assistente
- [x] **`core/chart_config.py`** — arquivo independente; evita ImportError ao importar `core.assistant_tools` no nível de módulo; chaves ASCII-only

### PC11 — Concluído (v4.18 / 2026-05-12)
- [x] **Projeto de trabalho global** — `active_project_id` + `active_project_name` em `st.session_state`; set only via Home.py ou `set_active_project` tool
- [x] **`require_active_project()`** — retorna `(project_id, project_name)` ou exibe warning + `st.page_link("pages/Home.py")` + `st.stop()`; chamada no topo de Assistente, ReqTracker, BpmnEditor, MeetingROI, ValidationHub
- [x] **Home.py — seletor de projeto** — auto-seleciona com 1 projeto; badge `st.success` + botão "Trocar" quando ativo; seta `prefix` = `sigla + "_"`
- [x] **`set_active_project` tool** — match parcial de nome (case-insensitive); atualiza `session_state["active_project_id/name/prefix"]`
- [x] **`delete_meeting` cascade fix** — Step 1: deleta `requirement_versions` por `meeting_id` (FK direto que bloqueava exclusão); `preview_meeting_deletion` atualizado
- [x] **Assistente chat styling** — user: fundo `#0d2a4a`, borda-esq azul; assistant: fundo `#0f2235`, borda-esq âmbar; chat input: fundo preto
- [x] **BPMN viewer timing fix** — `canvas.zoom('fit-viewport')` via `setTimeout(fn, 150)`; guard duplo width/height > 0

### PC18 — Concluído (v4.20+ / 2026-05-19)
- [x] **`api_key_alias` — chave compartilhada entre providers** — `modules/config.py`: `DeepSeek V4 Pro` e `DeepSeek V4 Flash (Thinking)` recebem `api_key_alias="DeepSeek"`; `session_security.py`: `render_api_key_gate` exibe "Key active (via DeepSeek)" sem pedir nova entrada; `get_session_llm_client` e `render_api_key_readonly` resolvem via alias — zero re-digitação de chave
- [x] **Settings "Status de todas as chaves"** — coluna Uso (Pipeline/Assistente/Embeddings); alias providers mostram `✅ Via DeepSeek`; linhas extras para `asst_api_key` (Assistente LLM) e `asst_embed_key` (Embeddings) — OpenAI configurada para embeddings aparece corretamente
- [x] **CostEstimator** — paleta de cores cíclica (10 cores) no gráfico de barras; data de preços atualizada para mai/2026; caption menciona DeepSeek V4 Flash + cache semântico
- [x] **CLAUDE.md** — padrão `api_key_alias` documentado na seção LLM Providers; tabela de providers atualizada com V4 Flash, V4 Pro, Thinking e Grok; nota sobre `reasoning_effort` e `api_key_alias`
- [x] **Decisão documentada** — reprocessamento de reuniões NÃO necessário: `deepseek-chat` aponta para `deepseek-v4-flash` durante o período de transição (até 24/07/2026); artefatos existentes válidos; cache semântico será repovoado naturalmente

### PC17 — Concluído (v4.20+ / 2026-05-19)
- [x] **Migração DeepSeek V4** — `modules/config.py`: `deepseek-chat` → `deepseek-v4-flash` (deprecated 24/07/2026); novo provider `DeepSeek V4 Pro` (`deepseek-v4-pro`, $0.435/1M, 1M context); novo provider `DeepSeek V4 Flash (Thinking)` com `reasoning_effort=high`, `supports_json_mode=False`, sem `temperature`
- [x] **Thinking mode em `_call_openai`** — se `provider_cfg["reasoning_effort"]` presente: passa `reasoning_effort` + `extra_body={"thinking":{"type":"enabled"}}`, remove `temperature` (não suportado); zero impacto nos outros providers
- [x] **`modules/cost_estimator.py`** — preços DeepSeek atualizados ($0.14/$0.28); entradas V4 Pro e Thinking adicionadas
- [x] **Fallbacks limpos** — `agents/agent_analyst.py` e `pages/Assistente.py`: `deepseek-chat` → `deepseek-v4-flash`

### PC16 — Concluído (v4.20+ / 2026-05-19)
- [x] **FASE 2 — Long Context Handler** — `services/context_analyzer.py`: `estimate_tokens()` (tiktoken cl100k_base + fallback len/4), `should_use_long_context()` (threshold 50k tokens), `inject_long_context_instruction()`, `LONG_CONTEXT_AGENTS={bpmn,sbvr,bmm}`
- [x] **`agents/base_agent.py`** — `_call_llm()` detecta transcrições longas: modifica system prompt (instrução de contexto completo), aumenta `max_tokens` de saída (8192), aumenta timeout (180s); `_call_openai`/`_call_anthropic` recebem `timeout` e `long_context` params; `hub.meta.long_context_calls` rastreado
- [x] **`core/session_state.py`** — `enable_long_context = True` padrão
- [x] **`core/knowledge_hub.py`** — `long_context_calls: int = 0` em `SessionMetadata`; migrate guard v4.26
- [x] **`ui/sidebar.py`** — checkbox "📄 Contexto Longo (BPMN/SBVR/BMM)" na Configuração Avançada
- [x] **`pages/Pipeline.py`** — banner `st.info` exibe número de agentes com contexto longo ativado
- [x] **`pages/MeetingROI.py`** — seção "📄 Contexto Longo (sessão atual)" no tab Cache LLM
- [x] **`tests/test_context_analyzer.py`** — 16 unit tests (TestEstimateTokens, TestShouldUseLongContext, TestInjectLongContextInstruction, TestLongContextAgentsSet); zero LLM/Supabase calls

### PC24 — Concluído (v4.24 / 2026-05-22)
- [x] **Renomeação ReqTracker → Central de Artefatos** — `pages/ReqTracker.py` → `pages/Artefatos.py` (git mv); título "Central de Artefatos" icon 🗂️; referências atualizadas em `app.py`, `pages/Home.py`, `core/assistant_tools.py`; nome de página mais amplo e em pt-br, cobrindo os 9+ tipos de artefato
- [x] **B) Badges de origem nos artefatos** — CSS `.badge-transcricao` (azul) + `.badge-documento` (verde); helpers `doc_map`, `doc_label()`, `_origin_badge()`; Tab Requisitos: 4º filtro "Origem" (Todas/Transcrição/Documento) + badge em cada card + fonte adaptada (mostra nome do documento quando origin=documento); Tab SBVR: badge de origem em termos e regras com fonte correta
- [x] **A) Nova aba Rastreabilidade (10ª)** — matriz consolidada: Requisitos + Termos SBVR + Regras SBVR; filtros tipo × origem; colunas Tipo/ID/Título/Origem/Fonte/Status/Prio.; KPIs (total/transcrições/documentos); exportação CSV
- [x] **C) KPI Documentos no Home** — `get_global_stats()` inclui `n_documents` (count de `meeting_documents`); Home.py: 5ª coluna KPI "Documentos" (rosa, ícone 📄, 5 colunas); métricas da Central de Artefatos: segunda linha agora com 4 métricas fixas incluindo Documentos

### PC23 — Concluído (v4.23 / 2026-05-22)
- [x] **`setup/supabase_migration_artifact_origin.sql`** — adiciona `origin TEXT DEFAULT 'transcricao'` e `doc_ref UUID REFERENCES meeting_documents(id)` às tabelas `requirements`, `requirement_versions`, `sbvr_terms`, `sbvr_rules`; remove NOT NULL de `first_meeting_id`/`last_meeting_id`/`meeting_id` para permitir artefatos sem reunião; 8 índices (`idx_*_origin`, `idx_*_doc_ref`)
- [x] **`core/knowledge_hub.py`** — campos `origin: str = "transcricao"` + `doc_ref: Optional[str] = None` adicionados a 7 dataclasses: `RequirementItem`, `BusinessTerm`, `BusinessRule`, `BMMGoal`, `BMMStrategy`, `BMMPolicy`, `DMNDecision`; guards `migrate()` v4.23 iterando sobre listas de artefatos
- [x] **`core/project_store.py`** — `save_new_requirement`: `meeting_id` agora nullable; `base_req`/`base_ver` condicionais (omitem meeting FK quando None); `origin`/`doc_ref` incluídos no attempt-1 payload (fallback transparente); `save_requirements_from_hub`: passa `origin`/`doc_ref` de cada item; `save_sbvr_from_hub`: refatorado com two-attempt pattern para origin/doc_ref, `meeting_id` nullable; nova função `save_artifacts_from_document(project_id, doc_id, extracted)`: salva todos os tipos de artefato (req/termos/regras SBVR/BMM e DMN via document metadata)
- [x] **`skills/skill_document_extractor.md`** — system prompt para extração de artefatos de documentos; JSON schema completo: requirements (title/description/req_type/priority/source_quote), sbvr_terms (term/definition/category), sbvr_rules (id/statement/rule_type/source/short_title), bmm_goals, bmm_strategies (com `supports`), bmm_policies, dmn_decisions (com confidence 0–1); guidelines por tipo de artefato
- [x] **`agents/agent_document_extractor.py`** — `DocumentExtractorAgent(BaseAgent)`; standalone on-demand; `extract(doc_title, doc_content, output_language) → Optional[dict]`; truncagem inteligente (head 8000 + tail 2000 chars); `_MinimalHub` stub satisfaz interface de hub sem necessitar pipeline completo
- [x] **`pages/DocumentManager.py`** — expandido de 4 para 5 abas; nova aba ⚗️ Extrair Artefatos: seleciona documento → run `DocumentExtractorAgent` → KPI row (7 métricas) → preview por tipo em expanders → download JSON → botão "Salvar no projeto" (chama `save_artifacts_from_document`)
- [x] **Pendente:** executar `setup/supabase_migration_artifact_origin.sql` no Supabase SQL Editor

### PC22 — Concluído (v4.22 / 2026-05-22)
- [x] **`setup/supabase_migration_documents.sql`** — 3 tabelas: `document_types` (taxonomia pré-populada com 53 tipos em 9 categorias), `meeting_documents`, `document_chunks` (`vector(1536)`); função pgvector `match_document_chunks()` para busca semântica filtrada por projeto; indexes; triggers updated_at; RLS desabilitado
- [x] **Taxonomia de documentos** — 53 tipos cobrindo: Iniciação e Planejamento (TAP/PGP/EAP/RACI), Requisitos (BRD/SRS/Backlog/User Stories/Casos de Uso), Processos (AS-IS/TO-BE/POP/SIPOC/VSM/Fluxograma/BPMN), Governança (Ata/Status Report/Riscos/Issues/Change Request/Lições), Análise de Negócio (SWOT/BMC/VPC/BIA/Business Case), Técnico (Arquitetura/API Spec/DER/C4/Runbook), Qualidade (Plano Teste/DoD/Checklist), Contratos e Acordos (Contrato/SLA/MOU/NDA/Proposta), Normas e Políticas (Política/ISO/Código de Conduta)
- [x] **`modules/document_store.py`** — CRUD fail-open: `upload_document`, `get_document`, `list_documents`, `delete_document`, `update_document_meta`; pipeline de embedding: `embed_document` (reusa `chunk_text`+`embed_batch` de `modules/embeddings.py`, inserts em batches de 50), `get_chunks_count`; busca: `search_documents_semantic` (pgvector via RPC), `search_documents_keyword` (ilike title+content, deduplica); `get_types_by_category` para UI
- [x] **`skills/skill_document_analyzer.md`** — system prompt para análise cruzada; JSON schema completo com: document_summary, alignment_score (0–100 com rubrica), aligned/conflicting/undocumented_requirements, process_alignment, process_gaps, stakeholders_mentioned, decisions_referenced (status: confirmed/conflicts/new/partial), implied_actions, temporal_analysis, key_insights, recommendations
- [x] **`agents/agent_document_analyzer.py`** — `DocumentAnalyzerAgent(BaseAgent)`; standalone on-demand (não entra no pipeline automático); `analyze(doc_title, doc_content, hub, output_language) → Optional[dict]`; conteúdo truncado inteligente (head 4500 + tail 1000 chars); `build_prompt` injeta minutos/requisitos/BPMN do hub formatados
- [x] **`pages/DocumentManager.py`** — 4 abas: (1) 📤 Enviar: seleção por categoria→tipo (53 tipos), vinculação opcional a reunião, upload .txt/.pdf/.docx ou paste, embed automático com spinner + contagem de chunks; (2) 📚 Biblioteca: busca keyword ou semântica, filtro por tipo, prévia de conteúdo, re-indexar, excluir; (3) 🔍 Análise Cruzada: seleciona doc+reunião+idioma → `DocumentAnalyzerAgent.analyze()` → score colorido + insights + expanders por seção (requisitos/processo/decisões/ações/stakeholders) + export JSON; (4) 🏷️ Taxonomia: tabela paginada por categoria
- [x] **`core/assistant_tools.py`** — 4 novas ferramentas: `list_meeting_documents` (filtra por reunião/tipo), `get_document_content` (conteúdo completo cap 8k), `search_documents` (semantic/keyword), `get_document_types` (taxonomia completa); métodos executor; entradas em `_TOOL_CATEGORIES`
- [x] **`app.py`** — `pages/DocumentManager.py` registrado no grupo Análise (icon 📄)
- [x] **Pendente:** executar `setup/supabase_migration_documents.sql` no Supabase SQL Editor

### PC21 — Concluído (v4.21 / 2026-05-22)
- [x] **`modules/billing.py`** — `Plan` dataclass + `PLANS` catálogo (5 planos: R$10/15cr, R$20/40cr destaque, R$35/80cr, R$50/120cr, R$80/ilimitado); CRUD Supabase fail-open: `get_user_credits`, `upsert_credits`, `set_contribuidor`, `reset_trial`, `log_payment`, `list_users_credits`, `list_payments`
- [x] **`setup/supabase_migration_billing.sql`** — tabela `user_credits` (user_id UNIQUE, creditos_restantes, degustacao_ativa, data_expiracao_degustacao, is_contribuidor, plano) + trigger updated_at + índices; tabela `pagamentos` (log imutável: user_id, email, valor, plano, creditos, status, external_id) + índices; RLS desabilitado
- [x] **`pages/PaymentAdmin.py`** — 4 abas admin: (1) Preview das mensagens: simulação interativa do banner de doação (PIX QR + agradecimento) + modal de plano pago (QR + balloons) + mensagem "pagamento não encontrado" + badge contribuidor; (2) Simular Pagamento: form com user/email/plano → `upsert_credits` + `log_payment(status='simulated')` + download SQL migration; (3) Usuários e Créditos: DataFrame + ações inline (delta créditos, toggle contribuidor, reset trial); (4) Log de Transações: DataFrame + 4 KPIs (total pago, créditos distribuídos, contribuidores, simulações)
- [x] **`app.py`** — `pages/PaymentAdmin.py` registrado no grupo Manutenção (admin only, icon 💳)
- [x] **Pendente:** executar `setup/supabase_migration_billing.sql` no Supabase SQL Editor

### PC20 — Concluído (v4.20+ / 2026-05-19)
- [x] **`ui/sidebar.py`** — `st.expander("Pesos de Seleção")` aninhado em `st.expander("⚙️ Configuração Avançada")` → substituído por `st.caption()` (Streamlit proíbe expanders aninhados; causava `StreamlitAPIException` ao mudar Passes de Otimização)
- [x] **`core/session_state.py`** — `run_query_summarizer` default `False` → `True`; `n_bpmn_runs` default `1` → `3`
- [x] **`modules/tenant_config.py`** — `PROVIDER_KEY_MAP` + `"Grok (xAI)": "grok_key"` (faltava no mapeamento de domínio)
- [x] **`pages/Settings.py`** aba Domínio — lista de provedores derivada de `AVAILABLE_PROVIDERS` (única fonte de verdade); alias providers ignorados automaticamente; ícone 🟡 para chave em sessão não salva no domínio; modelo visível no header
- [x] **`pages/Orientacoes_CKF.py`** seção 5 — diagrama CKF Evolutivo redesenhado: box AgentCKFUpdater, leituras alinhadas com labels dim, dois outputs em colunas (hub.context_skill / Supabase)

### PC35 — Concluído (v4.27 / 2026-06-06)
- [x] **`ensino/modulo_07_reunioes_eficazes/guia.md`** — guia de facilitação: 5 dimensões do Quality Inspector, 5 comportamentos de maior impacto (com exemplos ruim vs. bom), scripts de abertura/fechamento, tabela de linguagem processável vs. ambígua (7 situações), exercício passo a passo, dois checklists de bolso (facilitador + participante)
- [x] **`ensino/modulo_07_reunioes_eficazes/transcricao_07a_reuniao_ruim.txt`** — RetailPro, kick-off módulo de estoque, sem speaker ID, decisões implícitas, action items sem dono/prazo; esperado Grau D/E no Quality Inspector
- [x] **`ensino/modulo_07_reunioes_eficazes/transcricao_07b_reuniao_eficaz.txt`** — mesma reunião com facilitação estruturada: script de abertura, speakers identificados, processo descrito com gatilho→condição→exceção, 4 encaminhamentos com nome+tarefa+prazo, resumo de fechamento; esperado Grau A
- [x] **`ensino/PLANO_DO_CURSO.md`** — Módulo 7 adicionado à tabela de estrutura; total 14h→15h; seção completa com descrição dos dois cenários e exercício central
- [x] **`pages/Capacitacao.py`** — Módulo 7 adicionado a `_MODULES` (2 cenários: 7A e 7B); isolamento de contexto por usuário: botão "▶ Carregar" agora chama `_get_or_create_course_project()` que cria/resolve o projeto "Curso P2D - {usuario}" no Supabase antes de redirecionar ao Pipeline — evita mistura com projetos reais da empresa; fail-open quando Supabase não configurado

### PC47 — Concluído (sem PC / 2026-06-16)
- [x] **BPMN quality — regra de gateway com saída única** (`skill_bpmn.md` v7.3 + `agents/agent_validator.py`)
  - `skill_bpmn.md` v7.3: nova **REGRA CRÍTICA** em Passo 4 — todo gateway exige ≥ 2 sequence flows de saída; gateway com 1 saída indica ramificação omitida; exemplo explícito (Valor Abaixo do Limite? — 2 caminhos obrigatórios); checklist item adicionado em Passo 6
  - `agents/agent_validator.py` — `_score_gateways()`: new single-exit guard antes dos checks de XOR/AND; qualquer gateway com `len(out_edges) < 2` recebe `scores.append(0.0)` e `continue`; condição de XOR/AND corrigida para `if len > 1` implícito via continue

### PC46 — Concluído (sem PC / 2026-06-16)
- [x] **LangGraph expandido — Minutes + Requirements com adaptive retry** (`core/lg_pipeline.py`, `core/pipeline.py`, `core/knowledge_hub.py`, `agents/orchestrator.py`, `ui/sidebar.py`, `ui/tabs/bpmn_tabs.py`, `core/session_state.py`, `pages/Pipeline.py`)
  - `LGFullPipelineRunner` com 8 nós: bpmn → validate_bpmn → commit_bpmn → minutes → validate_minutes → requirements → validate_req → coordinator → END
  - Coordinator node: fuzzy word-overlap lanes ↔ participants + coverage check; notas em `hub.validation.lg_coordination_notes`
  - `ValidationReport` estendido: `lg_minutes_retries`, `lg_req_retries`, `lg_coordination_notes`
  - Bug fix (❌ icons): progress messages padronizadas para "running (...)" / "done (...)"
  - Bug fix (double preprocessing): `run_prereqs=True` param em `Orchestrator.run()`; Step 3 passa `run_prereqs=False`
  - Bug fix (identical scores): `_lg_skip_cache` instance attr em `BaseAgent._call_llm()`; setado True em retentativas > 1
  - Sidebar: 2 novos selectboxes `max_minutes_retries` + `max_req_retries` quando LG ativo
  - BPMN tab: banner expandido mostra retentativas Minutes/Req + expander coordination notes

### PC45 — Concluído (sem PC / 2026-06-16)
- [x] **Agent Cards — metadados semânticos por agente** (`skills/agent_cards/*.yaml`, `core/agent_registry.py`, `core/assistant_tools.py`, `pages/MasterAdmin.py`)
  - 18 YAML cards cobrindo todos os agentes: transcript_quality, bpmn, mermaid, minutes, requirements, sbvr, bmm, dmn, argumentation, synthesizer, query_summarizer, knowledge_extractor, contradiction_detector, communication_noise, ckf_updater, validator, document_analyzer, document_extractor
  - `core/agent_registry.py`: `get_agent_cards()` (lru_cache), `get_agent_card(name)`, `get_pipeline_agents()`, `get_on_demand_agents()`, `format_card_summary()`; ordenado por pipeline_phase
  - `get_system_capabilities()` atualizado para usar registry; agrupa por fase
  - `pages/MasterAdmin.py` Seção 6 — visualizador elegante: 4 KPIs, filtros phase/mode, grid CSS 3 colunas com hover, badges coloridos por fase, painel de inspeção de detalhe

### PC44 — Concluído (sem PC / 2026-06-14)
- [x] **`core/assistant_tools.py`** (`5b02b1c`) — `generate_ibis_map` corrigido:
  - Labels Q-nodes globalmente únicos: `"Q1<br>R9"` em vez de `"Q1"` local por reunião — elimina ambiguidade de leitura horizontal
  - Tooltip de A-nodes inclui `"— R{mnum}"` para rastreabilidade
  - Anotações de cabeçalho de reunião migradas para `yref="paper"` — sempre visíveis no topo independente do range de dados Y; badge navy com borda azul (`bgcolor="#1e3a5f"`, `bordercolor="#2563eb"`)
  - Margem superior 80 → 100px para acomodar os badges de reunião

### PC43 — Concluído (sem PC / 2026-06-14)
- [x] **`pages/Orientacoes_Assistente.py`** (`6f267ab`) — nova seção "Exportação da conversa" com tip-box documentando `⬇️ Markdown` e `⬇️ HTML`, gráficos Plotly interativos e nota sobre CDN

### PC42 — Concluído (sem PC / 2026-06-14)
- [x] **`pages/Assistente.py`** (`b452f22`) — exportação da conversa como HTML auto-contido:
  - `_export_chat_to_html(messages, project_name, provider) → str` — percorre `assistant_history`, renderiza mensagens user/assistant com dark-navy CSS, embute gráficos Plotly via `Plotly.js` CDN (incluído somente quando há charts), renderiza Markdown client-side via `marked.js` CDN, badges de ferramentas por mensagem, tabelas/código/blockquotes estilizados
  - `_html_escape(text)` + `_html_escape_attr(text)` — helpers de sanitização HTML segura
  - Toolbar atualizada: `⬇️ Markdown` (texto simples) + `⬇️ HTML` (auto-contido com gráficos) lado a lado

### PC41 — Concluído (sem PC / 2026-06-14)
- [x] **`ui/assistant_diagram.py`** — novo subgrupo `TD` "🗺️ Debates IBIS" com `search_ibis_debates`, `get_ibis_timeline`, `generate_ibis_map`; contador 35 → 38 ferramentas
- [x] **`ui/comms_diagram.py`** — novo `TG4` "🗺️ Debates IBIS" (3 tools); aresta `TG4 → MSBC` adicionada; contador 35 → 38 ferramentas

### PC40 — Concluído (sem PC / 2026-06-14)
- [x] **`pages/Orientacoes_Assistente.py`** — Guia do Assistente atualizado com 3 cards IBIS: `search_ibis_debates` (aba Análise, seção "Debates argumentativos — IBIS") + `get_ibis_timeline` e `generate_ibis_map` (aba Gráficos, seção "Debates argumentativos — IBIS"); inclui prompt canônico, campos `proposed_by/supported_by/opposed_by` e filtro de resolução documentados
- [x] **`CLAUDE.md`** — `search_ibis_debates`, `get_ibis_timeline`, `generate_ibis_map` adicionadas à lista Non-admin; nova seção "IBIS tools (3)" com campos, filtros, helper interno e prompt exemplo

### PC39 — Concluído (sem PC / 2026-06-14)
- [x] **`core/assistant_tools.py`** — `search_ibis_debates` agora inclui `proposed_by`, `supported_by` e `opposed_by` por alternativa — alinhado com o nível de detalhe da aba IBIS da Central de Artefatos

### PC38 — Concluído (sem PC / 2026-06-13)
- [x] **`core/assistant_tools.py`** — 3 novas ferramentas IBIS no `AssistantToolExecutor`:
  - `_load_ibis_questions(topic_filter, meeting_number)` — helper privado; query `meetings.argumentation_json` por projeto; parseia JSON; injeta `_mid/_mnum/_mtitle/_mdate`; filtra por Jaccard PT-BR (stop-word filtered tokens)
  - `search_ibis_debates(query, meeting_number?, resolution_filter?)` — busca keyword; grupos por reunião; formata Markdown estruturado com enunciado, raised_by, alternativas completas, resolução e ressalvas; filtro `all|decided|deferred|unresolved`
  - `get_ibis_timeline(topic?)` — Plotly stacked bar (decidido/adiado/em aberto por reunião número); `self._pending_charts`
  - `generate_ibis_map(topic?)` — Plotly hierárquico: Q-nodes círculo (cor por status: verde/âmbar/vermelho), A-nodes diamante (verde=eleita, azul=alternativa); colunas por reunião; arestas Q→A; legenda via traces invisíveis; appended como `fig.to_dict()` em `_pending_charts`
  - Schemas OpenAI + Anthropic, `_TOOL_CATEGORIES` (consulta/grafico), dispatch em `execute_tool()` todos conectados

### PC37 — Concluído (sem PC / 2026-06-13)
- [x] **`pages/DmnBackfill.py`** (novo) — página Manutenção dedicada ao DMN; `_missing(m) = not m.get("dmn_json")`; SELECT inclui apenas `dmn_json`; executa somente `AgentDMN`; tabela de resultados com "Decisões DMN"; session keys `dmn_bf_*`
- [x] **`pages/IbisBackfill.py`** (novo) — página Manutenção dedicada ao IBIS; `_missing(m) = not m.get("argumentation_json")`; SELECT inclui apenas `argumentation_json`; executa somente `AgentArgumentation`; tabela de resultados com "Questões IBIS"; session keys `ibis_bf_*`
- [x] **`pages/DmnIbisBackfill.py`** — removido via `git rm` (substituído pelas duas páginas acima)
- [x] **`app.py`** — Manutenção: entrada única `DmnIbisBackfill` substituída por `DmnBackfill.py` (icon ⚖️) + `IbisBackfill.py` (icon 🗺️)
- [x] **`pages/Artefatos.py`** — Mapa Visual IBIS com paridade do KnowledgeGraph: toolbar (⏸/▶ física, ＋/－ zoom, ⊡ Fit, 💾 Imagem, ⛶ Nova aba), focus mode (click node → dim não-vizinhos + bring-to-front via remove+re-add), `_ibis_physics` toggle + `_ibis_height` select_slider no expander de opções, tooltip CSS `white-space:pre-line`, legenda como badges Markdown `st.markdown` acima de `components.html()`

### PC36 — Concluído (v4.28 / 2026-06-06)
- [x] **`ensino/modulo_07_reunioes_eficazes/guia.md`** — enriquecimento baseado em análise dos capítulos 8 e 9 de "Business Modeling: A Practical Guide" (Bridgeland & Zahavi): tabela de 7 perfis de participantes desafiadores (Mouse→Otter) com comportamento + efeito na transcrição + resposta do facilitador; tabela de 7 antipadrões de reunião processável (Participante Ausente, Multitarefa, Patrocinador Ausente, Compromisso Condicional, Proxy Sem Autonomia, Facilitador Viesado, Modelo Rejeitado) com manifestação + impacto + prevenção; 6º comportamento "Verbalization Echoing" (facilitador resume + aguarda confirmação verbal, criando o rastro de confirmação mais rastreável da transcrição); "Declarar o escopo na abertura" como 2º comportamento; exercício expandido em 3 passos (comparação de pipeline, identificação de antipadrões na 7A, sessão de verificação dos artefatos da 7B); checklist do facilitador atualizado com 11 itens; atualização da tabela do Quality Inspector para mostrar as 7 dimensões (6 ASR + 1 Condução)
- [x] **`skills/skill_transcript_quality.md`** — 7º critério "Condução da Reunião" (Weight: 15%): avalia 5 práticas (A: identificação de speakers, B: verbalização de decisões, C: action items nome+tarefa+prazo, D: estrutura de processo gatilho→sequência→condições, E: verbalization echoing com confirmação); guia de pontuação 0/5→5/5 práticas; pesos redistribuídos (Coerência 20→15%, Vocabulário 15→10%, Pontuação 10→5%, Condução 0→15%); output JSON atualizado com 7 entradas; regra "exactly 7 entries" atualizada
- [x] **`agents/agent_transcript_quality.py`** — `_CRITERIA_WEIGHTS` atualizado com 7 critérios (soma 1.0); `_CONDUCAO_DEFAULT_SCORE = 50` para respostas em cache sem o 7º critério (evita penalizar transcrições antigas)
- [x] **`core/knowledge_hub.py`** — `MinutesModel.meeting_antipatterns: list[dict]` (cada item: `{type, description, examples}`); `migrate()` guard v4.28
- [x] **`skills/skill_minutes.md`** — seção "Detecção de Antipadrões de Reunião": 7 antipadrões a detectar (Participante Ausente, Compromisso Condicional, Proxy Sem Autonomia, Multitarefa, Patrocinador Ausente, Facilitador Viesado, Decisão Implícita); campo `meeting_antipatterns` adicionado ao schema JSON de saída
- [x] **`agents/agent_minutes.py`** — `_EMBEDDED_SKILL` atualizado com seção de antipadrões + schema JSON; `_build_model()` parseia `meeting_antipatterns`; `to_markdown()` inclui seção "⚠️ Alertas de Condução" quando antipadrões detectados; novo método estático `to_verification_report(minutes)` — gera roteiro de verificação em Markdown (header + decisões com checkbox + action items com confirmação + perguntas em aberto + riscos + alertas de condução + encerramento)
- [x] **`ui/tabs/export_tab.py`** — botão "⬇️ Roteiro de Verificação (.md)" na seção Meeting Minutes (usa `AgentMinutes.to_verification_report()`, `make_filename("verificacao", "md", ...)`)

### PC35 — Concluído (v4.27 / 2026-06-06)
- [x] **`ensino/modulo_07_reunioes_eficazes/`** — Módulo 7 "Reuniões que Geram Conhecimento Rastreável" criado do zero: `guia.md` (5 comportamentos, guia do facilitador, padrões de linguagem, exercício passo a passo, checklists); `transcricao_07a_reuniao_ruim.txt` (RetailPro kick-off, sem identificação de speaker, decisões vagas, Grau D esperado); `transcricao_07b_reuniao_eficaz.txt` (mesma pauta, Adriana Lemos como facilitadora com script de abertura, verbalization echoing, 4 encaminhamentos com nome+tarefa+prazo, fechamento explícito, Grau A esperado)
- [x] **`pages/Capacitacao.py`** — Módulo 7 adicionado ao `_MODULES` com 2 cenários (7A e 7B); importações `get_current_user` e `list_contexts/create_context` adicionadas; função `_get_or_create_course_project()` cria/resolve projeto Supabase "Curso P2D - {usuario}" fail-open; botão "▶ Carregar" atualizado para resolver projeto antes de injetar transcrição e redirecionar
- [x] **`ensino/PLANO_DO_CURSO.md`** — Módulo 7 adicionado na estrutura (tabela de módulos + seção detalhada); duração total 14h→15h

### PC34 — Concluído (v4.27 / 2026-06-06)
- [x] **`ensino/PLANO_DO_CURSO.md`** — narrativa reposicionada com chave "conhecimento rastreável": subtítulo, seção Sobre o Curso (distinção ata vs. conhecimento rastreável, pergunta de valor), Módulo 0 item 1 reformulado, item 5 de rastreabilidade na prática adicionado; Público-Alvo expandido com coluna "Quem é e o que enfrenta" (definição de papel + dor específica para cada um dos 7 perfis)
- [x] **`ensino/ativo-intangivel-de-maior-impacto-tangivel.md`** — "conhecimento rastreável" inserido como conceito-âncora: Tese Central ("transformar em conhecimento rastreável" + parágrafo de definição), Parte III subtítulo "Da conversa ao conhecimento rastreável" + frase "cada artefato sabe de onde veio" + coluna da tabela renomeada; Conclusão com parágrafo que distingue a categoria ("não é documentação melhorada") + citação final reforçada

### PC33 — Concluído (v4.27 / 2026-06-06)
- [x] **`ensino/ativo-intangivel-de-maior-impacto-tangivel.md`** — white paper completo reescrito: 6 partes estruturadas (O Ativo, Amnésia Corporativa, Tangibilização, ROI-TR/TRC, Implementação, Críticas); Parte VI incorpora análise crítica independente (Manuis AI) com 5 objeções respondidas diretamente (qualidade de entrada, resistência cultural, complexidade, privacidade/LGPD, dependência tecnológica); síntese "IA com limitações gerenciáveis vs. caos institucional crônico"

### PC32 — Concluído (v4.27 / 2026-06-06)
- [x] **`ensino/`** — curso de aplicações corporativas com 7 módulos + 8 transcrições fictícias realistas:
  - `PLANO_DO_CURSO.md` — visão geral, público-alvo, 14h de conteúdo, 3 formatos de entrega
  - `modulo_00_fundamentos/guia.md` — configuração, Quality Inspector, primeiro pipeline
  - `modulo_01_mapeamento_processos/` — guia + 3 transcrições (aprovação fornecedor, crédito pessoal, onboarding); exercícios de Check 7/Pass 5/Check 8
  - `modulo_02_rastreabilidade_requisitos/` — guia + kickoff portal cliente (requisitos IEEE 830, LGPD, Assistente RAG)
  - `modulo_03_auditoria_compliance/` — guia + comitê de contratos R$ 2,3M (SBVR, ata, dossiê de auditoria)
  - `modulo_04_gestao_conhecimento/` — guia + captura de especialista (conciliação SAP×Salesforce, Knowledge Graph)
  - `modulo_05_governanca_roi/` — guia + retrospectiva de sprint (ROI-TR, CommunicationNoise, TRC)
  - `modulo_06_estrategia_bmm/` — guia + planejamento estratégico anual (BMM, IBIS, rastreabilidade vertical)
- [x] **`pages/Capacitacao.py`** — página Streamlit no grupo Ajuda (🎓 Curso Corporativo): cards por módulo com guia inline, botão "▶ Carregar" injeta transcrição em `session_state.transcript_text` e redireciona para Pipeline, preview + download .txt
- [x] **`app.py`** — `Capacitacao.py` registrada no grupo Ajuda

### PC31 — Concluído (v4.27 / 2026-06-04)
- [x] **`ui/architecture_diagram.py`** — LLM providers 5→8 (DeepSeek V4 Pro, Thinking, Grok xAI adicionados); pipeline estendido com A9(DMN), A10(Argumentation/IBIS), A11(CommunicationNoise/CKF), A12(Synthesizer); artefatos 7→10 (R8 DMN, R9 Argumentação, R10 Análise de Ruído); ASST "21 ferramentas" → "35 ferramentas"
- [x] **`ui/assistant_diagram.py`** — TOOLS subgraph "21→35 Ferramentas"; TA: `list_bpmn_versions` adicionada após `list_bpmn_processes`; TC Admin: `★ delete_bpmn_version` adicionada
- [x] **`ui/comms_diagram.py`** — header "22→35 ferramentas"; TG1 "11→12 tools" + `list_bpmn_versions`; TG2 corrigido "7→8 tools"; TG3 "4→5 tools" + `★ delete_bpmn_version`
- [x] **`pages/Orientacoes_Arquiteturas.py`** — texto "22 ferramentas" → "35 ferramentas"

### PC30 — Concluído (v4.26 / 2026-06-04)
- [x] **`core/project_store.py`** — `delete_bpmn_version(version_id)`: exclui versão BPMN com segurança (recusa única versão; promove versão anterior se is_current; atualiza version_count)
- [x] **`core/assistant_tools.py`** — `list_bpmn_versions` (consulta): lista versões de um processo por nome com ID, status, reunião e notas; `delete_bpmn_version` (admin): exclui versão pelo version_id; ambas registradas em schemas OpenAI/Anthropic, `_TOOL_CATEGORIES`, `_ADMIN_TOOLS` e dispatcher
- [x] **`CLAUDE.md`** + **`pages/Orientacoes_Assistente.py`** — documentação atualizada: tool list e cards do Guia de Ferramentas com `list_bpmn_versions` e `delete_bpmn_version`
- [x] **Check 8** (`bpmn_structural_validator.py`): detecta coreografia desbalanceada em colaborações — sender não-sendTask ou receiver não-receiveTask em message flows; `skill_bpmn.md` atualizado com regra de balanceamento sendTask↔receiveTask

### PC29 — Concluído (v4.26 / 2026-06-04)
- [x] **`skills/skill_bpmn.md`** — XOR join promovido de "Recomendada" para "Obrigatória"; checklist atualizado para exigir join em AND/OR/XOR/complex splits
- [x] **`modules/bpmn_structural_validator.py` Check 7** — detecta task com `in_degree >= 2` cujos predecessores são todos não-gateway (fan-in direto); emite `warning` recomendando XOR join explícito
- [x] **`modules/bpmn_auto_repair.py` Pass 5** — insere `exclusiveGateway` join automaticamente quando branches de um XOR split convergem diretamente em uma task; algoritmo de ancestral-comum-2-hops evita falsos positivos em AND/OR; gateway anônimo inserido na mesma lane da task alvo

### PC28 — Concluído (v4.26 / 2026-06-04)
- [x] **`AgentCommunicationNoise`** — novo agente não-fatal (default OFF) que detecta 4 tipos de ambiguidade (lexical, referencial, vague_commitment, sintática) e 4 tipos de lacuna (unanswered_question, abandoned_topic, implicit_disagreement, missing_info); `noise_score` 0–10
- [x] **`core/knowledge_hub.py`** — `AmbiguityItem`, `CommunicationGap`, `CommunicationNoiseModel` dataclasses; campo `communication_noise` no `KnowledgeHub`; `migrate()` guard
- [x] **`skills/skill_communication_noise.md`** — skill com taxonomia de 8 tipos de ruído e tabela de pontuação
- [x] **`ui/tabs/communication_noise_tab.py`** — 4 KPIs, cards expandíveis por ambiguidade (confiança, interpretações, sugestão) e lacuna (impacto, recomendação, evidência)
- [x] **Pipeline step 6e** — `run_communication_noise` em `orchestrator.py`, `pipeline.py`, `rerun_handlers.py`, `sidebar.py` e `Pipeline.py`
- [x] **`pages/BpmnEditor.py`** — expander "Reconverter com Method & Style v7.0": re-executa `AgentBPMN` sobre a transcrição da versão selecionada e carrega o XML gerado no editor para revisão antes de salvar

### PC27a — Concluído (v4.25 / 2026-05-31)
- [x] **`skills/skill_bpmn.md` v7.0** — rewrite completo seguindo a metodologia Top-Down de Bruce Silver (*BPMN Method and Style*):
  - **Passo 0** (novo): definir escopo — identificar trigger, end states e volume de atividades antes de modelar
  - **Regra de Densidade Cognitiva**: sequências lineares com > 10 atividades são proibidas; `callActivity` obrigatório para agrupar fases lógicas (máx 10 nós por nível)
  - **Passo 2** (novo): High-Level Map — 3–7 fases com `callActivity` quando processo tem > 10 atividades
  - **Novos `task_type`**: `callActivity` (fase agrupadora), `loopTask` (repetição embutida), `multiInstanceTask` (para cada item de coleção), `boundaryTimerEvent`, `boundaryErrorEvent` (exceções durante tarefas)
  - **Nomenclatura estrita**: todos os títulos seguem `[Verbo Infinitivo] + [Objeto]` — noun-phrases são falha de qualidade
  - **Checklist expandido**: 20 itens cobrindo estrutura, hierarquia, semântica e padrões especiais (vs 12 itens anteriores)
  - **Dois exemplos**: processo flat simples + processo hierárquico com `callActivity`
- [x] **`agents/agent_bpmn.py`** — `_TASK_TYPE_MAP` expandido: `callActivity` (renderiza com dupla borda no bpmn-js), `sendTask`, `receiveTask`, `eventBasedGateway`, `complexGateway`, `loopTask`, `multiInstanceTask`, `boundaryTimerEvent`, `boundaryErrorEvent`; tipos não-nativos do gerador mapeiam para `userTask` até PC27b
- [x] **`claude_guideline/acceptance_criteria.md`** — AgentBPMN expandido com critérios Silver Level 1: densidade (callActivity obrigatório > 10 atividades), nomenclatura Verbo+Objeto, end states distintos, padrões de iteração e boundary events

### PC26 — Concluído (v4.25 / 2026-05-31)
- [x] **`claude_guideline/acceptance_criteria.md`** (novo) — Quality Contract: critérios testáveis por agente (TranscriptQuality, NLPChunker, BPMN, Mermaid, Minutes, Requirements, SBVR, BMM, Synthesizer, Validator) + critérios de Pipeline Integration, Supabase/Persistência e UI/Streamlit; referenciado em CLAUDE.md
- [x] **`core/knowledge_hub.py`** — `AgentOutcomeScore` dataclass (`agent_name`, `passed`, `score 0–10`, `checks dict`, `warnings list`); `ValidationReport.agent_scores: dict`; `migrate()` guard v4.26
- [x] **`agents/agent_validator.py`** — `validate_all(hub, weights) → dict[str, AgentOutcomeScore]`; 8 validadores fail-open: `_validate_quality`, `_validate_nlp`, `_validate_bpmn_outcomes`, `_validate_mermaid`, `_validate_minutes`, `_validate_requirements`, `_validate_sbvr`, `_validate_bmm`; helper `_make_score()`; método `score()` (torneio multi-run) intocado
- [x] **`agents/orchestrator.py`** — Step 8 (fail-open): após synthesizer, chama `AgentValidator().validate_all(hub, bpmn_weights)` e persiste em `hub.validation.agent_scores`
- [x] **`ui/components/quality_badge.py`** (novo) — `render_quality_badge(hub, agent_name)`: lê `hub.validation.agent_scores`, exibe badge colorido (✅ ≥ 8.0 / ⚠️ 6–8 / ❌ < 6) com `st.popover` listando checks individuais; silencioso se `agent_scores` ausente
- [x] **Badges nas tabs do Pipeline** — `bpmn_tabs.py`, `quality_tab.py`, `minutes_tab.py`, `requirements_tab.py`, `sbvr_tab.py`, `bmm_tab.py`: cada tab recebeu header em duas colunas com `render_quality_badge(hub, agent_name)` à direita
- [x] **Fix `pages/Home.py`** — "Reuniões recentes" filtradas por `active_project_id`; `list_recent_meetings()` aceita `project_id` opcional; join `projects(name)` inválido removido (tabela é `contexts`); `@st.cache_data` usa `project_id` como cache key

### PC25 — Concluído (v4.25 / 2026-05-23 + 2026-05-31)
- [x] **`modules/transcript_time_parser.py`** — pure-Python parser de timestamps ASR; detecta 6 formatos (`[HH:MM:SS] Speaker:`, `Speaker (HH:MM):`, `HH:MM:SS - Speaker:`, etc.); computa `duration_seconds` e `speaker_times` (dict nome→segundos); fallback `estimate_timings_from_wordcount()` quando sem timestamps; `format_duration()` + `format_speaker_table()` para display
- [x] **`MeetingTimeModel`** em `core/knowledge_hub.py` — `has_timestamps`, `format_detected`, `duration_seconds`, `speaker_times`, `speaker_turns`, `ready`; propriedade `duration_minutes`; `migrate()` guard v4.25
- [x] **Orchestrator Step 1.5** — `parse_transcript_timings()` + fallback `estimate_timings_from_wordcount()` após NLP Chunker; popula `hub.meeting_time`; fail-open (não quebra pipeline)
- [x] **`setup/supabase_migration_meeting_time.sql`** — colunas `duration_minutes INTEGER` e `speaker_times JSONB` na tabela `meetings`
- [x] **`core/project_store.py`** — `save_meeting_artifacts()` persiste `duration_minutes` e `speaker_times` quando disponíveis
- [x] **`pages/Pipeline.py`** — painel "⏱️ Tempo de reunião e fala por participante" (expander): `st.metric` duração + `st.dataframe` breakdown por participante (tempo, turnos, %); indicação de fonte (timestamp vs estimativa); sugestão de título do agente de ata com botão "Usar este título" + `update_meeting_title()` automático
- [x] **Fix ícone de pipeline** — `pages/Pipeline.py`: status `"skipped"` exibe `⏭️` em vez de `❌`; `❌` reservado exclusivamente para erros reais (resolve ambiguidade reportada em `duvidas/gerar_insights.md`)
- [x] **`core/cost_model.py`** (novo) — `ModelPricing`, `AgentTokenProfile`, `ScenarioConfig`, `ScenarioResult`; `PRICING_CATALOG` (17 modelos / 6 provedores: DeepSeek, Claude, OpenAI, Groq, Gemini, Grok); `DEFAULT_TOKEN_PROFILES` (9 agentes com perfis heurísticos e `context_multiplier`); `project_cost(scenario, word_count, catalog) → ScenarioResult` — cálculo 100% local, sem LLM, sem rede (NF-1, NF-3); `get_effective_catalog(overrides)`, `cheapest_model()`, `best_quality_model()`, `estimate_tokens()`
- [x] **`pages/CostBenefitScenarios.py`** (novo) — página no grupo Análise; layout coluna única; status de cenário ativo no topo com badge + ações; Cenário Default somente-leitura (espelha provider/modelo global atual); editor de até 5 cenários em tabs com nome editável, 3 presets (Custo Mínimo / Qualidade Máx. / Balanceado), selectboxes provedor→modelo por agente com custo parcial via `st.metric`; botão "Aplicar ao Pipeline" por aba; backup de cenário anterior + "Restaurar 'X'" + "Voltar ao Default"; gráfico barras empilhadas custo/agente; scatter Custo×Qualidade com zona ideal; tabela resumo; catálogo editável via `st.data_editor` persistido em `session_state["cost_catalog_overrides"]`
- [x] **`agents/base_agent.py`** — `_call_llm()`: lê `st.session_state["scenario_assignments"]` (dict `agent_name→model_id`) e sobrescreve `model` antes do cache lookup; fail-open se ausente (NF-5); não altera `client_type` nem `api_key`
- [x] **`pages/Pipeline.py`** — badge informativo `st.info` quando `scenario_assignments` ativo (nome do cenário + até 4 pares agente:modelo)
- [x] **`core/session_state.py`** — `asst_embed_provider` default corrigido de `"Google Gemini"` para `"OpenAI"` (alinha com configuração de uso real)

### PC19 — Concluído (v4.20+ / 2026-05-19)
- [x] **`services/llm_telemetry.py`** — `TelemetryRecord` dataclass; `LLMTelemetry` (async daemon thread, fail-open Supabase write); `run_benchmark_call()` (timed raw LLM call, sem cache/PII/hub); `BENCHMARK_TASKS` (5 agentes: bpmn/minutes/requirements/sbvr/bmm com prompts representativos); `TRANSCRIPTS` (short ~150w / medium ~350w); `_telemetry` singleton
- [x] **`agents/base_agent.py`** — `_call_openai`/`_call_anthropic` retornam `(raw, tokens_in, tokens_out)`; `_call_llm` desempacota e registra `TelemetryRecord` por chamada (latency_ms, input/output tokens, provider, model, long_context, from_cache=False, benchmark_run=False); thinking mode: `reasoning_effort` → `extra_body={"thinking":{"type":"enabled"}}` + sem temperature
- [x] **`pages/LLMBenchmark.py`** — duas abas: (1) 🧪 Benchmark On-Demand: multi-select providers (só configurados) + agentes, N runs slider, seleção de transcrição, save_to_db checkbox, progress bar por tarefa, tabela de resultados + bar charts de latência e throughput; (2) 📊 Telemetria Real: filtros (provider/agente/dias/cache/benchmark), 4 KPIs, 4 sub-tabs: Latência (box plot p5/p25/mediana/p75/p95), Throughput (bar agrupado tokens/s), Histórico (line chart por dia), Heatmap (agente × provider latência mediana)
- [x] **`setup/supabase_migration_llm_telemetry.sql`** — tabela `llm_telemetry` + 4 índices + `delete_old_llm_telemetry()` PL/pgSQL (90 dias)
- [x] **`app.py`** — `pages/LLMBenchmark.py` registrado em Sistema group (icon ⚡)

### PC15 — Concluído (v4.20+ / 2026-05-19)
- [x] **`pages/Orientacoes_Assistente.py`** — guia completo de ferramentas do Assistente em Ajuda → 💬 Ferramentas do Assistente; dark-navy CSS; modos Assistente (tool-use/RAG) vs Análise Autônoma; 6 abas: Reuniões / Análise / Gráficos / Calendário / Knowledge Hub / Admin; 33 tool cards com badge colorido por categoria (consulta/escrita/grafico/calendario/admin) + descrição + 2–3 exemplos de prompt; registrada em `app.py` Ajuda entre "Como Iniciar" e "Glossário"

### PC14 — Concluído (v4.20+ / 2026-05-19)
- [x] **Cache hit indicator no Pipeline** — `st.status()` label exibe `⚡ N cache hit(s)`; banner verde pré-abas com tokens economizados + ~USD; `st.metric(help=...)` ⓘ explica cache semântico + PII token_map + link para ROI-TR → Cache LLM
- [x] **Ferramentas do Assistente para cache** — `get_cache_stats(agent_name?)`: Markdown table com entradas/hits/tokens/USD + breakdown por agente; `clear_llm_cache(agent_name?)`: invalida cache (admin only); wired em schema OpenAI/Anthropic, `_TOOL_CATEGORIES`, `_ADMIN_TOOLS`, dispatcher

### PC13 — Concluído (v4.20+ / 2026-05-19)
- [x] **Semantic LLM Cache** — `services/semantic_cache.py`: `SemanticCache` com SHA256(provider|model|system|sanitized_user); armazena raw output pré-desanitize; na recuperação aplica `desanitize(cached_raw, token_map_atual)` — PII-safe entre sessões; `get_stats()` + `invalidate()`; fail-open em todo lugar
- [x] **`setup/supabase_migration_llm_cache.sql`** — tabela `llm_cache` + índices + `delete_expired_llm_cache()` PL/pgSQL
- [x] **`agents/base_agent.py`** — `_call_llm()` integra cache antes de chamar API; armazena resultado após; `skip_cache=True` param; `hub.meta.cache_hits` + `tokens_saved` rastreados
- [x] **`core/knowledge_hub.py`** — `cache_hits` + `tokens_saved` em `SessionMetadata`; migrate() guard v4.25
- [x] **`pages/MeetingROI.py`** — nova aba "💾 Cache LLM": 4 KPIs, breakdown por agente, economia USD estimada, limpar cache (admin)

### PC12 — Concluído (v4.20+ / 2026-05-18–19)
- [x] **Phase F — AgentQuerySummarizer** — `agents/agent_query_summarizer.py` + `skills/skill_query_summarizer.md`; 4 perspectivas (Executivo, Técnico, Gestor, Conformidade); `QuerySummaryModel` + `PerspectiveSummary` em `knowledge_hub.py`; `ui/tabs/query_summary_tab.py` (icon + headline blockquote + highlights + open_items + actions); Orchestrator Step 6d; sidebar checkbox + re-run button; export Markdown; `migrate()` guard v4.24; default False
- [x] **Multi-sphere SBVR (Fase G)** — `BusinessRule` com `sphere`, `sphere_owner`, `bmm_policy_ref`, `speaker_quote`; `RequirementItem` com `business_rule_refs: list` + `sphere: Optional[str]`; `_VALID_SPHERES` frozenset; **SBVR reordenado para Step 2.5** (antes de Minutes+Requirements) para rastreabilidade de BR-IDs; `skill_sbvr.md` atualizado com tabela de esferas; `sbvr_tab.py` reescrito com métricas, agrupamento por esfera, filtro, speaker_quote, bmm_policy_ref, requisitos vinculados
- [x] **Glossário** — `pages/Orientacoes_Glossario.py`; 6 abas de categoria (BPMN/Process, Requisitos, Linguagem de Negócio, Qualidade, Tecnologia, Metodologia) + aba Referências (16 specs/libs); CSS dark-navy matching outras páginas Orientações; registrado em `app.py` Ajuda após "Como Iniciar"
- [x] **Cobertura completa de reprocessamento** — `run_knowledge_extractor` + `run_query_summarizer` adicionados aos 3 caminhos: `core/batch_pipeline.py _reprocess_one()`, `core/assistant_tools.py reprocess_meeting_full()`, `pages/BatchRunner.py` (seção batch + expander reprocessar); UI expandida para 12 colunas com 🕸️ Grafo + 🔎 Sumário

### PC79 — Concluído (v4.60 / 2026-06-26)

**Precisão do Assistente — keyword search robusto + regras de paginação/contagem**

- [x] **`core/assistant_tools.py` — `get_requirements` keyword search**:
  - Corrigida busca por `req_number`: comparação type-safe (`int` e `str`) — resolve bug onde `REQ-229` não era encontrado quando `req_number` era string no banco
  - Adicionado `cited_by` ao filtro de keyword — permite buscar "quem sugeriu" diretamente
- [x] **`agents/agent_assistant.py` — `_SYSTEM_TOOLS_TEMPLATE`**: nova seção "BUSCA E LISTAGEM DE REQUISITOS" com regras explícitas:
  - Fluxo de busca por REQ-NNN (keyword → cited_by → fallback ReqTracker)
  - Paginação: nunca somar itens de uma página como total; iterar `page+1` se houver mais
  - Autoria: `cited_by` disponível no retorno de `get_requirements(keyword="REQ-NNN")`
  - Reforço: `count_artifacts` obrigatório para totais, nunca `get_requirements` sem filtros
- [x] **`melhorias/estrategia_para_precisao.md`** → `melhorias/arquivados/`

---

### PC78 — Concluído (v4.59 / 2026-06-26)

**Housekeeping — arquivamento de 22 propostas implementadas**

- [x] `git mv` de 22 arquivos de `melhorias/` → `melhorias/arquivados/` (histórico preservado)
- [x] Propostas arquivadas: BPMN (skill v7.9, method-and-style, AgentBPMNReviewer), Assistente (xlsx, UI, chat export, 4 novas ferramentas), Glossário, ATA Engine, Knowledge Hub Persistente, SemanticCache + ContextAnalyzer, migração DeepSeek v4-flash, ClaudeCodeWorkflow, BMIF Strategic Plan
- [x] Mantidos em `melhorias/`: propostas futuras não implementadas (Jira, LGPD, multi-esfera 2.0, MCP/A2A, PII, Grok multi-agent, precisão Assistente)

---

### PC77 — Concluído (v4.59 / 2026-06-26)

**AgentValidator — 5ª dimensão de scoring: semântica de nomenclatura BPMN**

- [x] **`agents/agent_validator.py`** — nova dimensão `semantic` (0–10, pure Python, sem LLM):
  - Constantes: `_ACTIVITY_VERBS` (23 verbos PT), `_GENERIC_START_NAMES`, `_GENERIC_END_NAMES`
  - Penalizações: gateway com verbo de atividade (−2.5/viol), task terminando com `?` (−2.0), evento Start/End genérico (−1.0)
  - `_score_semantic(steps) → tuple[float, int]`; peso via `weights.get("semantic", 5)` — fail-open
- [x] **`core/knowledge_hub.py`** — `BPMNValidationScore`: campos `semantic: float` + `n_semantic_violations: int`; `migrate()` guard v4.59
- [x] **`core/session_state.py`** — `bpmn_weights` default inclui `"semantic": 5`
- [x] **`ui/sidebar.py`** — slider "Semântico" adicionado ao bloco de pesos do torneio
- [x] **`modules/i18n.py`** — chave `"semantic"` em pt-BR e en-US
- [x] **`tests/test_agent_validator.py`** — 9 novos testes em `TestSemantic`; constantes `WEIGHTS_*_ONLY` atualizadas com `"semantic": 0`

---

### PC76 — Concluído (v4.58 / 2026-06-26)

**skill_bpmn_reviewer v1.1 — emojis na tabela de violações**

- [x] `skills/skill_bpmn_reviewer.md` — tabela de violações com emojis de severidade

---

### PC75 — Concluído (v4.58 / 2026-06-26)

**AgentBPMNReviewer completo — apply_bpmn_corrections + agent LLM + DB tables**

- [x] **`agents/agent_bpmn_reviewer.py`** (novo) — agente LLM standalone (padrão `_MinimalHub`):
  - `review(bpmn_xml, process_name)` → str — relatório Markdown completo em 4 fases via `skill_bpmn_reviewer.md`; chama `_call_llm` diretamente (resposta Markdown, não JSON)
  - `apply_corrections(bpmn_xml, process_name, corrections)` → dict | None — aplica lista de correções cirúrgicas; prompt focado em JSON puro (retorna formato AgentBPMN flat); usa `_call_with_retry` (3 tentativas)
- [x] **`apply_bpmn_corrections(process_name, corrections, version_notes?)`** — ferramenta admin no Assistente:
  - Obtém XML atual do banco; chama `AgentBPMNReviewer.apply_corrections()`; constrói `BPMNModel` via `AgentBPMN._build_model()` + `_enforce_rules()` + `_generate_bpmn_xml()`; salva como nova versão via `save_bpmn_new_version()`; loga em `bpmn_review_log` (fail-open)
  - Ações suportadas: `convert_to_task`, `convert_to_gateway`, `rename`, `add_edge_labels`, `add_missing_gateway`
- [x] **`setup/supabase_migration_bpmn_review.sql`** — 2 novas tabelas:
  - `bpmn_process_descriptions`: armazena descrição Markdown por processo/versão (`process_id FK`, `version_id FK nullable`, `description_md`, `generated_by`)
  - `bpmn_review_log`: audit log de correções (`project_id`, `process_name`, `version_before/after`, `issues_found/corrected`, `review_report jsonb`, `user_approved`)
- [x] **`core/project_store.py`** — `save_bpmn_review_log()` fail-open; insere em `bpmn_review_log`
- [x] **`core/assistant_tools.py`** — schema OpenAI, categoria "admin", `_ADMIN_TOOLS`, executor `apply_bpmn_corrections()`, dispatch
- [x] **Fluxo completo implementado:** `suggest_bpmn_corrections` → usuário confirma → `apply_bpmn_corrections` → nova versão BPMN salva → log de auditoria

---

### PC74 — Concluído (v4.57 / 2026-06-26)

**BPMN + Assistente — describe_bpmn_process + suggest_bpmn_corrections + Rule 4 + process_type/description_md**

- [x] **`describe_bpmn_process(process_name)`** — gera descrição textual estruturada do processo a partir do XML BPMN; parse puro Python (`xml.etree`); extrai participantes (pools/lanes), fluxo numerado em ordem topológica (BFS), rótulos de saída de gateways, resultados possíveis (endEvents); escopo "consulta"
- [x] **`suggest_bpmn_corrections(process_name)`** — plano de correção estruturado sem aplicar alterações; detecta: gateways com verbos de atividade → propõe conversão para userTask + novo gateway; tasks com `?` → propõe conversão para gateway; XOR sem labels → sugere "Sim"/"Não" ou "Caminho N"; eventos genéricos → sugere nomes de trigger/resultado; escopo "consulta"
- [x] **`core/assistant_tools.py`** — schemas OpenAI, categorias, implementações e dispatch para as 2 novas ferramentas
- [x] **Rule 4 (`_enforce_rules`)** — XOR gateways com arestas sem rótulo recebem labels padrão automaticamente: 2 saídas → "Sim"/"Não"; N saídas → "Caminho 1..N" (só preenche lacunas, não sobrescreve labels existentes)
- [x] **`BPMNModel.process_type`** — campo opcional `"flat"|"hierarchical"|"collaboration"` (LLM-supplied via skill v7.9); `migrate()` guard v4.57
- [x] **`BPMNModel.process_description_md`** — campo Markdown para descrição textual do processo (AgentBPMN ou revisor); `migrate()` guard v4.57

---

### PC73 — Concluído (v4.56 / 2026-06-26)

**skill_bpmn v7.9 + AgentBPMNReviewer + review_bpmn_diagram + save_bpmn_revision**

- [x] **`skills/skill_bpmn.md` v7.9** — 11 melhorias de prompt engineering: CKF Injection Awareness, Passo 0.5 (padrões estruturais), §1.1 Lane vs Ator Descartável, §1.2 Regra do Nome Exato, Rótulo Refletido (traceability label), Data Objects §8.5.1, §4.1 Detecção de Gateways Faltantes, Join Flexível de XOR, checklist "Gateway NÃO tem verbo", Passo 7 (Validação de Cobertura + Regra do Espelho), `process_type` no JSON de saída
- [x] **`skills/skill_bpmn_reviewer.md`** (novo) — skill completo do AgentBPMNReviewer: 4 fases (parse → auditoria 25 regras → reelaboração textual → JSON); checklists: nomenclatura (R1–R7), gateway (R8–R12), tasks (R13–R16), fluxos (R17–R20), pools/lanes (R21–R23), hierarquia (R24–R25)
- [x] **`review_bpmn_diagram(process_name)`** — auditoria pura Python via `xml.etree`; detecta: gateways com verbos, tasks como gateways, eventos genéricos, lanes genéricas, fluxos XOR sem rótulo, elementos órfãos; score /10; escopo "consulta"
- [x] **`save_bpmn_revision(process_name, bpmn_xml, ...)`** — salva nova versão via `save_bpmn_new_version`; persiste `process_description` em `bpmn_processes` (best-effort); escopo "admin"

---

### PC72 — Concluído (v4.55 / 2026-06-26)

**Assistente — 3 novas ferramentas de edição de req/SBVR**

- [x] **`update_requirement_text(req_number, new_description, new_title, change_note)`** — atualiza título e/ou descrição completa de um requisito pelo número; registra versão em `requirement_versions` com `change_type='text_edit'`; resolve o caso de aspas simples que `apply_text_correction` não suportava; escopo "escrita"
- [x] **`update_sbvr_rule(rule_id, new_statement, new_rule_type)`** — atualiza enunciado de uma regra SBVR pelo ID (ex: BR002, BR006); escopo "escrita"
- [x] **`update_sbvr_term_by_id(term_id, new_definition, new_category)`** — atualiza termo SBVR pelo UUID; necessário quando múltiplos termos têm o mesmo nome; escopo "escrita"
- [x] **`core/assistant_tools.py`** — schemas OpenAI, categorias, implementações e dispatch para as 3 ferramentas

---

### PC71 — Concluído (v4.54 / 2026-06-26)

**Assistente — novas ferramentas: resolve_contradiction + delete_contradiction**

- [x] **`resolve_contradiction`** — marca contradição como resolvida (ou esclarecida/descartada); identifica por busca parcial na descrição; registra `resolution_note` + `resolved_by` + novo `status`; chama `knowledge_store.resolve_contradiction()`; escopo "escrita" (todos os perfis)
- [x] **`delete_contradiction`** — exclua permanentemente uma contradição; requer `confirm=true`; identifica por busca parcial; delete direto via Supabase; escopo "escrita"
- [x] **Proteção multi-match** — se a query ambígua retorna >1 contradição, lista até 5 candidatos e pede refinamento; sem exclusão/resolução acidental
- [x] **`core/assistant_tools.py`** — schemas OpenAI (+ dispatch), permissões no `_TOOL_PERMISSION_MAP`, implementações `resolve_contradiction()` + `delete_contradiction()`
- [x] **`update_requirement_status`** — já existia (PC anterior); confirmado funcional — trigger: "Evolua o status do requisito X para Y"

---

### PC70 — Concluído (v4.53 / 2026-06-26)

**skill_bpmn.md v7.8 — Todo pool em colaboração deve ter startEvent/endEvent explícitos**

- [x] **Causa raiz** — Example C, pool_1 (Cliente) só tinha `sendTask`/`receiveTask` sem `noneStartEvent`/`noneEndEvent` → gerador injetava "Início"/"Fim" genéricos violando a regra de nomenclatura
- [x] **Example C — pool_1 atualizado** — adicionados S00 (`noneStartEvent` = "Necessidade de Crédito Identificada") e S03 (`noneEndEvent` = "Resultado de Crédito Recebido"); edges atualizadas: S00→S01→S02→S03; message_flows inalterados (continuam em S01/S02)
- [x] **Nova regra em Passo 3** — "REGRA CRÍTICA — Formato colaboração: todo pool deve ter Start Event e End Event explícitos"; estrutura mínima S00 (noneStartEvent) … Sm (noneEndEvent) documentada com exemplos ✓/✗
- [x] **Nota de rodapé atualizada** — observações do Example C reforçam que `sendTask`/`receiveTask` NÃO dispensam os eventos explícitos
- [x] **`skills/skill_bpmn.md`** — versão v7.8

---

### PC69 — Concluído (v4.52 / 2026-06-26)

**BPMN — fix validação cega a steps/edges sob sub-chave "process"**

- [x] **Causa raiz identificada** — `_build_model_multi` lê steps/edges de `pool["process"]["steps"]` mas a validação lia de `pool["steps"]` (top level); quando o LLM aninha steps sob `"process"` a validação via `_p.get("steps")` retornava `[]`, `_p_steps = 0`, condição `_p_steps > 2` ficava `False` → validação nunca disparava → pool 2 com 15 steps e 0 edges (sequence flows ausentes) passava intacto
- [x] **Fix 1 — Validação** (`_bpmn_call_with_retry`) — helper `_pf(p, key)` busca o campo primeiro no top-level do pool, depois em `pool["process"]`; total_steps/total_edges e per-pool check usam `_pf` em vez de `_p.get()`
- [x] **Fix 2 — Model builder** (`_build_model_multi`) — `raw_steps/edges/lanes` agora usam `proc.get() or pool_data.get() or []`; aceita tanto o formato `pool.process.steps` quanto `pool.steps` sem perder dados
- [x] **`agents/agent_bpmn.py`** — ambas as correções aplicadas

**Problema resolvido:** "15 nós isolados — no incoming or outgoing edges" no pool "Grupo Meridional S.A." — o LLM retornava steps corretamente aninhados sob `"process"` mas sem edges (ou edges no nível errado); validação era cega a esse caso e modelo ficava sem sequenceFlows.

---

### PC68 — Concluído (v4.51 / 2026-06-25)

**Pipeline.py — Fix widget-tree desync (setIn index N, should be between [0, 0])**

- [x] **Root cause identified** — during background-agent polling, `st.rerun()` at line 521 stopped Python execution before the hub section (tabs), leaving the client with a "no-tabs" widget tree. After 660 s of 1-second reruns, the WebSocket desync caused `setIn index 134 (should be between [0, 0])` on completion, resulting in a blank screen
- [x] **Fix: hub section moved BEFORE rerun handler + polling block** — hub now renders on every Streamlit render cycle (including during polling), keeping the widget tree structurally identical throughout; the polling info (`st.info`) appears at the bottom of the page and disappears cleanly when the agent completes
- [x] **sleep(2) instead of sleep(1)** — halved polling frequency to reduce WebSocket stress during extended LLM calls (LangGraph + PC67 validation can run 10+ min)
- [x] **`pages/Pipeline.py`** — reordered: deferred messages → hub section → rerun handler → polling block → footer

**Problema resolvido:** re-execução do agente BPMN (com PC67 validações + LangGraph retries) rodava em múltiplos ciclos longos; ao final o cliente tinha widget-tree desync e mostrava tela em branco.

---

### PC67 — Concluído (v4.50 / 2026-06-25)

**BPMN — validação de message_flows órfãos + skill v7.7**

- [x] **`agents/agent_bpmn.py` — validação de message_flows órfãos** — após validação de edges por pool, verifica que todo `endMessageEvent` e `sendTask` em cada pool tem uma entrada correspondente em `message_flows` com `source.pool/step` apontando para ele; se qualquer um estiver sem message_flow → `ValueError` com lista dos elementos órfãos → retry com `_retry_suffix` semântico que preserva multi-pool e cita os elementos específicos; `endMessageEvent` sem message_flow = evento mudo (não comunica nada)
- [x] **`skills/skill_bpmn.md` v7.7 — Instrução Final** — adicionada verificação obrigatória pré-retorno: contar N `endMessageEvent` + N `sendTask` que iniciam comunicação → deve haver N entradas cobrindo-os em `message_flows`

**Problema resolvido:** o LLM gerava endMessageEvents corretos no banco (recusa automática, recusa manual, aprovação) mas omitia os message_flows correspondentes para o cliente — a coreografia ficava incompleta, p1_S03 (receiveTask) sem nenhum message_flow de entrada.

---

### PC66 — Concluído (v4.49 / 2026-06-25)

**skill_bpmn v7.6 — Exemplo C reescrito + regras de colaboração/gateways/lanes fortalecidas**

- [x] **Exemplo C reescrito completamente** — causa raiz identificada: o exemplo anterior tinha (1) aresta combinando "≥700 ou <500" em uma só saída de gateway, ensinando o LLM que 2 branches bastam para 3 intervalos; (2) único `endMessageEvent "Notificar Cliente"` servindo tanto recusa quanto aprovação; (3) 2 lanes apenas; (4) nome "Banco Meridional" contraditório com a regra de nomenclatura na linha 67. Novo Exemplo C: gateway S04 com 3 saídas distintas ("< 500", "500-699", ">= 700"), gateway S07 com 2 saídas fechadas (Não → End Event específico; Sim → Formalizar), 3 End Events distintos nomeados por resultado, 6 message flows cobrindo toda comunicação, 2 lanes, pool "Banco ABC" (nome fictício genérico)
- [x] **Colaboração obrigatória — triggers explícitos** — adicionado após tabela flat/pools no Passo 1: lista de sinais que tornam pools OBRIGATÓRIO (entidade externa, órgão nomeado, comunicação interorganizacional, troca formal de docs); regra de desempate "quando em dúvida → sempre prefira pools"; "formato flat é PROIBIDO quando há entidade externa"
- [x] **Lanes obrigatórias** — adicionado após regra de ordenação de lanes: "Lanes são OBRIGATÓRIAS quando o pool tem 2+ papéis com responsabilidades distintas — nunca omita lanes para simplificar"
- [x] **Density rule por pool** — adicionado ao Passo 0: "em formato pools, a contagem é feita por pool — cada pool aplica a regra de densidade independentemente"
- [x] **Gateways obrigatórios** — adicionado após regra de labels no Passo 4: triggers explícitos para quando gateway é obrigatório (threshold numérico com N intervalos → N saídas, alçada escalonada → N saídas, aprovação/rejeição em pontos distintos → gateways separados); "nunca combine intervalos distintos numa única aresta"
- [x] **Checklist** — novo item: "Em formato pools, message_flows cobre TODOS os pontos de comunicação interorganizacional? Pool sem message_flow = pool isolado (erro)"

**Causa raiz do problema:** o Exemplo C era o principal professor do LLM e ensinava padrões errados — gateway com branches combinadas, End Event único para resultados distintos, poucas lanes, nome contraditório.

---

### PC65 — Concluído (v4.48 / 2026-06-25)

**BPMN — prevenção de format escape: detecção proativa de colaboração + hints separados por tipo de erro**

- [x] **`agents/agent_bpmn.py` — detecção proativa de colaboração** — calcula `_collaboration_expected` combinando dois sinais: `hub.nlp.actors >= 2` (NLP estruturado) + scan de keywords no transcript (≥2 hits: cliente, fornecedor, banco, bureau, serasa, quod, receita federal, parceiro, externo, contratante, contratado, prestador, tomador); quando positivo, injeta diretiva `## MANDATORY FORMAT — COLLABORATION` com template multi-pool no system prompt ANTES da chamada LLM
- [x] **Hints separados por tipo de erro em `_bpmn_call_with_retry`** — `ValueError` (validação semântica: pool sem edges) → `_retry_suffix` semântico que preserva estrutura multi-pool e cita o erro específico; nunca menciona flat format quando `_collaboration_expected`; `KeyError` (parse JSON) → `_flat_hint` contextualizado (quando colaboração esperada, proíbe explicitamente formato flat)
- [x] **`_flat_hint` context-aware** — quando `_collaboration_expected`, o hint de parse também proíbe flat; quando não, mantém comportamento original (escolha baseada no transcript)
- [x] **Detecção de format escape + logging** — após `_build_model()`, se colaboração era esperada mas LLM retornou flat: `WARNING [AgentBPMN] Format escape detected`; registrado em `execution_log["collaboration"]` com `expected`, `nlp_actors`, `keyword_hits`, `format_escape`
- [x] **`execution_log["collaboration"]`** — novo bloco de diagnóstico adicionado ao log de execução para rastreabilidade de fugas de formato

**Problema resolvido:** o hint `_flat_hint` era injetado em TODOS os retries (incluindo `ValueError` de validação semântica); o LLM explorava a menção de flat format para escapar do per-pool check, gerando diagramas sem pools/gateways/raias que passavam silenciosamente em todas as validações.

---

### PC64 — Concluído (v4.47 / 2026-06-24)

**Assistente — tool `compare_meeting_transcripts` (detecção de duplicatas)**

- [x] **`core/assistant_tools.py`** — nova tool `compare_meeting_transcripts(meeting_numbers: list[int])`: compara pares de transcrições por similaridade de texto; score ponderado = `char_sim × 0.50 + jaccard × 0.35 + len_ratio × 0.15`; veredictos: DUPLICATA (≥80%), MUITO SIMILAR (≥60%), PARCIALMENTE SIMILAR (≥35%), DISTINTOS; evidências: até 4 trechos comuns com ≥80 chars
- [x] `SequenceMatcher` char-level (amostra 12k chars), Jaccard sobre palavras >3 chars sem stopwords PT, razão de comprimento; aceita 2–5 reuniões; schema + categoria `"consulta"` + roteamento duplo (non-admin + admin dispatch)

---

### PC63 — Concluído (v4.46 / 2026-06-24)

**Renomear título de reunião — UI + assistente**

- [x] **`pages/Pipeline.py`** (Modo B) — expander "✏️ Renomear reunião" com `text_input` + botão "💾 Salvar"; chama `update_meeting_title(meeting_id, new_title)`; atualiza `st.session_state["load_meet_select"]` para manter seleção sincronizada; atualiza `hub.minutes.title` se disponível
- [x] **`core/assistant_tools.py`** — nova tool `rename_meeting(meeting_number, new_title)`: localiza reunião via `_find_meeting`, chama `update_meeting_title`, invalida cache; retorna diff de título; categoria `"escrita"` + roteamento duplo

---

### PC62 — Concluído (v4.45 / 2026-06-24)

**Assistente — tool `render_mermaid_code` (geração de diagramas Mermaid)**

- [x] **`core/assistant_tools.py`** — nova tool `render_mermaid_code`: o LLM gera código Mermaid válido como parâmetro da chamada; o executor faz `_pending_widgets.append({type: mermaid, code: ...})` para renderização inline no chat; funciona com qualquer tipo Mermaid (`flowchart`, `sequenceDiagram`, `classDiagram`, `stateDiagram-v2`, etc.)
- [x] Schema registrado em `get_tool_schemas_openai()` (Anthropic derivado automaticamente); categoria `"consulta"` em `_TOOL_CATEGORIES`; roteamento no executor
- **Diferença de `show_mermaid_diagram`:** essa tool busca Mermaid salvo no banco para uma reunião existente; `render_mermaid_code` renderiza qualquer Mermaid gerado sob-demanda pelo LLM — inclui diagramas de sequência, estado, etc.

---

### PC61 — Concluído (v4.44 / 2026-06-24)

**UI — diagnóstico estrutural BPMN não roda em hub carregado do DB**

- [x] **`ui/tabs/bpmn_tabs.py`** — guard `if not hub.bpmn.steps:` envolve chamada ao `validate_bpmn_structure`; quando hub carregado do banco (`steps` vazio), exibe nota informativa em vez do falso "✅ Nenhum problema estrutural detectado"
- **Root cause:** `load_meeting_as_hub` persiste apenas `bpmn_xml`, não os campos estruturados `steps/edges/lanes`; o validador iterava sobre lista vazia e reportava zero issues (falso positivo enganoso)

---

### PC60 — Concluído (v4.43 / 2026-06-24)

**BPMN skill — Exemplo C (colaboração multi-pool) + corrige retry hint**

- [x] **`skills/skill_bpmn.md`** — adicionado Exemplo C mostrando colaboração com 3 pools (Cliente, Banco Meridional com 2 lanes internas, Bureaus de Crédito); nota explícita: "Receita Federal/Serasa → pool separado, NUNCA lane interna do banco"; dá ao LLM template concreto para processos multi-organização
- [x] **`agents/agent_bpmn.py`** — `_flat_hint` no retry corrigido: antes proibia pools mesmo em processos multi-org; agora instrui o LLM a escolher o formato correto baseado na transcrição
- **Root cause da regressão:** LLM gerou flat format porque não havia exemplo de colaboração no skill; o retry hint reforçava o erro ao dizer "DO NOT use pools format"

---

### PC59 — Concluído (v4.42 / 2026-06-24)

**BPMN viewer auto-repair + Pass F waypoint ordering**

- [x] **`modules/bpmn_viewer.py` `preview_from_xml`** — aplica `reformat_bpmn_labels` automaticamente antes de renderizar; garante que XMLs carregados do banco (salvos antes das correções de waypoints) recebam reparos completos (Pass F + Pass G); elimina o problema de sequence flows saindo do centro dos elementos em todas as visualizações (pipeline, Diagramas.py, meetings existentes)
- [x] **`modules/bpmn_auto_repair.py` Pass F** — waypoints sintéticos inseridos com `_edge.insert(0, wp1)` / `_edge.insert(1, wp2)` ao invés de `_ET.SubElement`; garante que waypoints precedam qualquer `BPMNLabel` existente no `BPMNEdge` (exigência da spec BPMN DI); fix aplica-se tanto a `sequenceFlow` quanto a `messageFlow`
- **Root cause:** quando um edge tinha `BPMNLabel` filho mas zero waypoints (ex: `p2_sf_004`, `sf_end`), `SubElement` appendava os waypoints *após* o label; bpmn-js ignorava a ordem inválida e renderizava center-to-center; com `insert(0, ...)` os waypoints ficam antes do label e bpmn-js usa-os corretamente como border-to-border

---

### PC58 — Concluído (v4.41 / 2026-06-23)

**BPMN generator — resolução de conflito de coluna em retorno cross-lane**

- [x] **`modules/bpmn_generator.py` `_compute_layout`** — novo post-pass após `_align_parallel_branches`: detecta quando um flow cross-lane (source em lane diferente do target) aterrissa o target na mesma coluna que outro elemento na lane do target; empurra o target (e todos os seus successores downstream) uma coluna à frente; repete até estável
- **Root cause:** no padrão "detour cross-lane" (S04→S07[Gerente]→S08[Aurora] em paralelo com S04→S05→S06[Aurora]), `_assign_columns` atribuía S06 e S08 à mesma coluna 5 em Sistema AURORA; end event circle (36px) ficava centrado dentro do range horizontal da callActivity (160px), com apenas 20px de gap vertical — visual de sobreposição
- **Resultado após fix:** S06 fica sozinho na coluna 5 (width=36px); S08 vai para coluna 6; S05→S06 fica horizontal perfeito (ambos centrados em y=425 na lane); pool 2% mais largo mas layout muito mais limpo

---

### PC57 — Concluído (v4.40 / 2026-06-23)

**BPMN auto-repair — Pass D: threshold 70px + isenção de messageFlow**

- [x] **`modules/bpmn_auto_repair.py` Pass D** — threshold de detecção de diagonais alterado de 1px para 70px (`_DIAG_THRESHOLD = 70`, ≈ H_GAP); flows com `|Δy| ≤ 70px` são preservados (misalignment legítimo de lane por diferença de altura entre elemento: `endEvent` 36×36 vs `task` 90×90)
- [x] **Isenção de messageFlow em Pass D** — `_eid in _mf_map` pula o check diagonal; evita que Pass D remova os waypoints verticais recém-gerados por Pass F
- **Root cause identificada:** `p2_sf_004` (dy≈-12 por port offset de gateway), `p2_sf_006` (dy=-55), `p2_sf_008` (dy=-28) e `mf_1` (diagonal vertical entre pools) eram todos removidos pelo threshold=1px; cross-lane flows têm `|Δy| ≥ 100px`, logo threshold=70px distingue corretamente os dois casos

---

### PC56 — Concluído (v4.39 / 2026-06-23)

**BPMN auto-repair — Pass F cobre messageFlow BPMNEdges (bpmn-comparativa-v3)**

- [x] **`modules/bpmn_auto_repair.py`** — Pass F agora constrói `_mf_map` indexando `messageFlow` além de `sequenceFlow`; BPMNEdge de message flow sem waypoints recebe 2 waypoints sintéticos com roteamento vertical entre pools: `bottom-centre → top-centre` se source acima de target, reverso caso contrário; contadores e log separados por tipo

---

### PC55 — Concluído (v4.38 / 2026-06-23)

**BPMN — Start/End Event com nomes descritivos (bpmn-comparativa-001.md)**

- [x] **`core/knowledge_hub.py`** — novos campos `process_trigger: str` e `process_outcomes: list[str]` em `BPMNModel`; guard em `migrate()` v4.37
- [x] **`agents/agent_bpmn.py`** — `_build_model_flat()` parseia `process_trigger`/`process_outcomes` do JSON LLM; Rule 0 captura `title` dos steps de evento antes de removê-los (fallback sem mudança no JSON); `_generate_bpmn_xml_single()` usa `_start_name`/`_end_name` em vez de strings fixas "Início"/"Fim"
- [x] **`skills/skill_bpmn.md` v7.5** — schema flat atualizado com campos `process_trigger` + `process_outcomes`; regra de nomenclatura obrigatória com exemplos corretos/incorretos
- [x] **`modules/bpmn_diagnostics.py`** — `_build_single_process()` usa campos do `BPMNModel` em vez de hardcodes
- **Itens não implementados (justificativa):** Boundary Events (item 🔴 2 do doc) — generator tem placeholder PC27b; é trabalho arquitetural separado. Múltiplos End Events distintos — requer mudança no algoritmo de terminal detection do generator.

---

### PC54 — Concluído (v4.37 / 2026-06-23)

**BPMN — 3 melhorias de qualidade de análise (inspeção inspecao-bpmn.md)**

- [x] **`modules/bpmn_auto_repair.py` — import Pass 5 para nível de módulo** — `BPMNStep`/`BPMNEdge` importados uma única vez no topo do módulo com `try/except ImportError`; eliminado re-import a cada execução de `_repair_pool()` (melhora legibilidade + evita overhead repetido)
- [x] **`modules/bpmn_structural_validator.py` — Check 8: eventBasedGateway** — valida que todos os flows saintes de `eventBasedGateway` apontam para `intermediateTimerCatchEvent`, `intermediateMessageCatchEvent` ou `receiveTask`; emite `BPMNIssue("warning")` com referência à OMG BPMN 2.0 §13.2.1 para qualquer violação
- [x] **`modules/bpmn_diagnostics.py` — suporte multi-pool** — refatorado `_build_bpmn_process()` em dispatcher + `_build_single_process()` (lógica original) + `_build_collaboration_process()` (nova, itera `pool_models`, gera IDs com namespace por pool: `ev_start_{pool_id}`, `lane_{pool_id}_...`); diagnóstico BPMN agora funciona corretamente em modelos de colaboração

---

### PC53 — Concluído (v4.36 / 2026-06-22)

**BPMN auto-repair — 3 fixes de qualidade visual (Pass C/F/G)**

- [x] **Pass C — stagger 15 → 30 px** — flows em skip channel sobrepostos agora têm separação mínima de 30px (era 15px), evitando sobreposição visual mesmo em canais próximos ao topo do pool
- [x] **Pass F (novo) — waypoints sintéticos para edges vazias** — detecta `BPMNEdge` com zero waypoints (bug gerado pelo LLM ao não emitir `<bpmndi:BPMNEdge>` corretamente); constrói mapa `bpmnElement→Bounds` + mapa `sequenceFlow→(sourceRef,targetRef)`; adiciona 2 waypoints (right-center da shape source → left-center da shape target) garantindo que bpmn-js renderize o conector
- [x] **Pass G (novo) — separar saídas sobrepostas** — detecta grupos de flows com os mesmos 2 primeiros waypoints (mesma shape source, mesmo ponto intermediário); ordena por Y final (flows que vão para cima recebem offset negativo); aplica offset `±(n-1)/2 × 18px` em `wp[0].y` e `wp[1].y` para criar fan-out visível direto da shape source
- [x] **`core/assistant_tools.py`** — fix `get_bpmn_execution_log`: lê hub de `st.session_state.get("hub")` em vez de `self.hub` inexistente (AttributeError silencioso causava retorno "log não disponível")

---

### PC52 — Concluído (v4.35 / 2026-06-21)

**BPMN — Labels explicitamente centrados + Log de execução do agente**

**Fix label: centrado determinístico (modules/bpmn_generator.py + bpmn_auto_repair.py)**
- [x] **Causa raiz** — generator emitia `<bpmndi:BPMNLabel />` vazio confiando no auto-centering do bpmn-js; para `callActivity` o marcador "+" reduz a área de texto e o auto-centering falha; em re-render o texto aparece fora da forma
- [x] **`modules/bpmn_generator.py`** — constantes `_LBL_PAD_X=10` / `_LBL_PAD_Y=8` adicionadas; ambos os loops DI (single-pool e multi-pool) agora emitem `dc:Bounds` explícitos centrados para todo tipo task/subprocess/callActivity (events e gateways mantêm posicionamento externo)
- [x] **`modules/bpmn_auto_repair.py` — Pass B reescrito** — em vez de remover bounds, insere/corrige `dc:Bounds` centrados com `SNAP_TOL=1px` (atualiza apenas se fora de tolerância); cobre XML gerado por versões antigas sem bounds ou com bounds incorretos
- [x] **Resultado** — labels sempre dentro da forma, centrados, independentemente do tipo de task ou comportamento do viewer bpmn-js

**Log de execução do agente BPMN**
- [x] **`core/knowledge_hub.py`** — campo `execution_log: Optional[dict] = None` adicionado a `BPMNModel`; guard em `migrate()` (v4.35)
- [x] **`agents/agent_bpmn.py`** — log capturado após cada run: fonte (`llm_call`), provider/model/tokens/cache/latência, alterações de `_enforce_rules`, `repair_bpmn` passes, `reformat_bpmn_labels` passes, métricas (steps/edges/lanes/gateways/tipos de task, alert de títulos >35 chars)
- [x] **`core/rerun_handlers.py`** — fast-path rerun também atualiza `execution_log` com fonte `fast_path_rerun` e métricas do diagrama regenerado
- [x] **`core/assistant_tools.py`** — nova tool `get_bpmn_execution_log` (schema + executor + dispatch + categoria `consulta`); lê `hub.bpmn.execution_log` da sessão atual; formata relatório Markdown com todas as seções do log
- [x] **149 testes passando**, zero regressões

---

### PC51 — Concluído (v4.34 / 2026-06-21)

**BPMN — Fix visual: fluxos cruzados, skip sobrepostos e labels fora do pool**

- [x] **`modules/bpmn_auto_repair.py` — Pass C** — detecta flows com 4 waypoints e segmento horizontal no mesmo y-channel; os ordena por comprimento de span (menor fica, maiores recebem +15px por nível); elimina sobreposição visual de múltiplos skip flows em `reformat_bpmn_labels`
- [x] **`modules/bpmn_auto_repair.py` — Pass D** — detecta BPMNEdge com exatamente 2 waypoints diagonais (Δx≠0 e Δy≠0); remove waypoints → bpmn-js aplica roteamento Manhattan (L-shaped) que elimina cruzamentos em X ao convergir no mesmo alvo (padrão sf_end/sf_end_1)
- [x] **`modules/bpmn_auto_repair.py` — Pass E** — clamp de labels de sequências com y < 5 para y=5; impede labels invisíveis fora dos limites do pool (situação anterior: skip a y=10 → label a y=-6 não renderizado)
- [x] **`modules/bpmn_generator.py` — `_label_pos()`** — adicionado `max(5, ...)` para garantir label y ≥ 5 em todos os diagramas gerados; previne y=-6 em novos XMLs desde a geração
- [x] **Resultado** — labels de fluxos de sequência visíveis no viewer; flows de skip paralelos em canais distintos; flows diagonais convergentes deixam de se cruzar em X; "Ajustar Labels" agora relata as correções feitas em vez de falso positivo
- [x] **84 testes passando**, zero regressões

**`skill_bpmn.md` v7.4 — 4 correções de qualidade**

- [x] **Limite de caracteres harmonizado** — corpo e checklist alinhados em `≤ 35 chars` (antes: corpo dizia 30, checklist dizia 40, absoluto dizia 35 — 3 valores conflitantes)
- [x] **Critério de coesão para `callActivity`** — adicionado critério primário "coesão, não contagem": 4 critérios qualitativos de Bruce Silver (fase de negócio distinta, compreensível isoladamente, lógica interna complexa, terceirizável); proíbe explicitamente fragmentar só para reduzir contagem
- [x] **Boundary Events completos** — tabela do Passo 3c ampliada com `boundaryMessageEvent` ("cliente cancela durante análise") e `boundaryConditionalEvent` ("mudança de regulação em vigor"); adicionada distinção interrompente vs. não-interrompente
- [x] **Regra End Event ↔ label de gateway** — novo item no checklist do Passo 6: nome do End Event deve corresponder ao label do gateway que o precede (estilo de rastreabilidade visual de Bruce Silver)

---

### PC50 — Concluído (v4.33 / 2026-06-20)

**Pipeline — Background Thread para Reexecução de Agentes (fix "CONNECTING")**

- [x] **Causa raiz** — `handle_rerun()` era chamado sincronamente no script thread do Streamlit; LLM calls de 60–180s bloqueavam o WebSocket → browser mostrava "CONNECTING" / "Página sem Resposta"
- [x] **`core/rerun_handlers.py`** — removidos todos `st.info()` / `st.warning()` da função; substituídos por `messages.append((level, text))`; retorno alterado de `hub` para `(hub, messages)` — função agora thread-safe
- [x] **`pages/Pipeline.py`** — handler síncrono substituído por `threading.Thread(daemon=True)` + polling de 1s (`sleep(1)` + `st.rerun()`); WebSocket permanece vivo durante toda a execução; mensagens exibidas no main thread após conclusão
- [x] **Resultado** — reprocessamento de qualquer agente (especialmente BPMN) não causa mais "CONNECTING"; progresso visível com spinner "⏳ Executando agente…"

**Reexecução BPMN — Fix DeepSeek retornando conteúdo vazio**

- [x] **Causa raiz** — `_lg_skip_cache = True` adicionado a todos os agentes em `handle_rerun()` para forçar chamadas frescas à API; chamadas DeepSeek a partir do background thread retornavam conteúdo vazio (sem ScriptRunContext); resultado: `ValueError: No JSON object found in LLM response` após 3 tentativas
- [x] **`agents/base_agent.py`** — guard `and raw` em `_cache.set()`: respostas vazias nunca persistidas no cache semântico (previne cache poisoning)
- [x] **`agents/base_agent.py`** — `_call_openai` levanta `ValueError` descritivo com `finish_reason` quando conteúdo é `None`/vazio (diagnóstico mais claro em logs)
- [x] **`core/rerun_handlers.py`** — `_lg_skip_cache = True` removido de todos os 11 agentes; cache semântico reutilizado no rerun (respostas válidas do pipeline inicial disponíveis imediatamente); guard `and raw` garante que falhas anteriores não contaminem o cache
- [x] **Resultado** — reexecução do agente BPMN via DeepSeek restaurada; rerun retorna do cache quando disponível (instantâneo) ou faz chamada fresca quando necessário

**BPMN — Labels de Tasks Centrados (fix "Ajustar Labels")**

- [x] **Problema** — `reformat_bpmn_labels()` (Pass B) removia `dc:Bounds` deixando `<bpmndi:BPMNLabel />` vazio; bpmn-js renderizava label abaixo do shape em vez de centralizado; função reportava falso positivo "labels já centralizados" para shapes 160×90
- [x] **`modules/bpmn_auto_repair.py`** — Pass B reescrito: em vez de remover bounds, insere `dc:Bounds` explícitos centrados (`exp_lx = sx + PAD_X=10`, `exp_ly = sy + PAD_Y=8`, largura/altura inset); "já centralizados" agora só reportado quando todos os bounds estão dentro de 1px de tolerância (`SNAP_TOL`)
- [x] **`modules/bpmn_generator.py`** — ambos os geradores (single-pool e multi-pool) passaram a emitir `dc:Bounds` explícitos centrados para tasks desde a geração (`_LBL_PAD_X=10`, `_LBL_PAD_Y=8`), eliminando a necessidade de repair posterior

---

### PC49 — Concluído (v4.33 / 2026-06-20)

**BPMN — Gateway Port Assignment + Parallel Edge Gap (Melhoria A+B)**

- [x] **`_GATEWAY_TYPES`** — frozenset centralizado em `modules/bpmn_generator.py` com os 5 tipos de gateway
- [x] **`_compute_gateway_exits(flows, el_map, shapes)`** — para gateways com ≥2 saídas, distribui exits no right edge com Y-spread de ±12px (total 24px para n=3), ordenados por target-centre-Y; retorna `{flow_id: (exit_x, exit_y)}`
- [x] **`_route_waypoints(..., src_exit=None)`** — novo parâmetro opcional; quando fornecido, substitui o ponto de partida `(sx+sw, sy+sh/2)` sem alterar nenhuma das 7 estratégias de roteamento (cross-lane, backward, skip, default)
- [x] **Integração nos dois loops de DI** — `_build_di` (single-pool) e `_generate_bpmn_xml_multi` (multi-pool) computam `_gw_exits` antes do loop de flows e passam `src_exit` ao roteador
- [x] **Resultado visual** — 3 saídas do mesmo gateway passam de `y=235, 235, 235` para `y=223, 235, 247` (fanning); labels de condição ficam separados visualmente
- [x] **149 testes passando**, zero regressões

**BPMN Viewer — Parallel Asset Fetch (hotfix)**

- [x] **`modules/bpmn_viewer.py`** — `_load_bpmn_assets()` buscava 4 URLs sequencialmente (timeout 20s cada → até 80s bloqueando o servidor Python); isso causava "CONNECTING" no browser e "Página sem Resposta" no Windows
- [x] **Fix:** fetch paralelo via `ThreadPoolExecutor(max_workers=4)`; timeout reduzido 20s → 8s; `@lru_cache` movido de `_fetch_text` para `_load_bpmn_assets`; worst-case blocking 80s → 8s
- [x] **Resultado:** aba BPMN carrega normalmente após reprocessamento de agente

**CLAUDE.md — Redução de tamanho (37.8k)**

- [x] **CLAUDE.md** reduzido de 42.4k → 37.8k chars (−11%); 12 blocos de descrição de grupos de ferramentas do Assistente migrados para `claude_guideline/architecture_details.md §Tool list`
- [x] **`claude_guideline/architecture_details.md`** — nova seção `## Tool list — Assistente (core/assistant_tools.py)` com todos os 14 grupos de ferramentas

---

### PC48 — Concluído (v4.33 / 2026-06-19)

**Top-10 Ferramentas do Assistente — Fases 1–4** (`melhorias/top-10-ferramamentas-assistente.md`)

#### Fase 1 — Plantonista e Diagnóstico (pré-sessão)
- [x] **`sugestoes_plantonista`** — ferramenta não-admin em `core/assistant_tools.py`; analisa atas + requisitos pendentes + IBIS sem resposta + encaminhamentos vencidos; retorna lista priorizada de sugestões de ação para o usuário
- [x] **`diagnostico_projeto`** — ferramenta não-admin; varre cobertura de artefatos por reunião (BPMN, ata, DMN, IBIS, relatório), contagem de requisitos por status, score ROI-TR médio, pendências IBIS abertas; retorna relatório de saúde consolidado em Markdown
- [x] **Plantonista auto-trigger** — `pages/Assistente.py` exibe sugestões automaticamente ao abrir o Assistente com projeto ativo, sem precisar digitar comando

#### Fase 2 — Editor Estrutural
- [x] **`reordenar_requisitos`** — ferramenta de escrita; aceita `nova_ordem: array[str]` (lista de req_numbers) ou `agrupar_por: enum[tipo,prioridade]`; atualiza campo `sort_order` na tabela `requirements` via Supabase; retorna confirmação com nova sequência
- [x] **`inserir_secao_ata`** — ferramenta admin; aceita `meeting_number`, `titulo`, `conteudo`, `posicao: enum[inicio,fim,antes_X,apos_X]`; faz parse do `minutes_md`, injeta nova seção `## titulo`, persiste no Supabase
- [x] **`vincular_regra_debate`** — ferramenta de escrita; faz upsert na tabela `sbvr_ibis_links` (rule_id, ibis_question_id, relacao: justifica|contradiz|limita); cria rastreabilidade bidirecional SBVR ↔ IBIS
- [x] **`mesclar_reunioes`** — ferramenta admin; modo `preview=True` (padrão) mostra impacto antes de executar; modo execute reassigna requisitos/SBVR/BPMN/chunks da reunião absorvida, concatena atas, deleta meeting absorvida; parâmetro `razao` registrado nos metadados
- [x] **`sincronizar_calendario`** — ferramenta admin; lê action items das atas, cria eventos Google Calendar via `modules/calendar_client.py create_event()`; rastreia status em `calendar_sync_items`; suporta `direction: to_calendar|from_calendar|bidirectional`; parâmetros de janela de trabalho (`default_work_start/end`)
- [x] **Migration SQL** — `setup/supabase_migration_fase2.sql`: coluna `sort_order INTEGER` em `requirements`; tabela `sbvr_ibis_links` (project_id, rule_id, ibis_question_id, relacao, created_at); tabela `calendar_sync_items` (project_id, meeting_id, action_text, google_event_id, sync_direction, status, last_sync_at); ambas com `ENABLE ROW LEVEL SECURITY` (service_role ignora RLS; bloqueia anon/authenticated); índices em project_id e meeting_id — **migration executada com sucesso**

#### Fase 3 — Rastreabilidade, What-If e Conformidade
- [x] **`mapa_rastreabilidade`** — ferramenta de consulta; coordena `search_transcript()`, `list_bpmn_processes()`, `get_sbvr_rules()`, `_load_ibis_questions()` para construir mapa Markdown de rastreabilidade de um requisito ou tópico; flags booleanas `include_transcript|bpmn|sbvr|ibis` controlam escopo; sem SQL novo (usa tabelas existentes)
- [x] **`simular_cenario`** — ferramenta de consulta; recebe `descricao` + `requisitos_afetados: array` + `restricoes: object`; agrega requisitos + regras SBVR + contradições do KnowledgeGraph; chama LLM via `_llm_call()` para análise de impacto; fallback heurístico automático se LLM falhar; sem SQL novo
- [x] **`verificar_conformidade`** — ferramenta de consulta; keyword-match de títulos/descrições de requisitos contra conteúdo de documento (`meeting_documents` + `document_chunks`); classifica Coberto/Parcial/Não Mapeado por threshold configurável; retorna relatório de lacunas; suporta `mode: keyword|llm`; sem SQL novo

#### Fase 4 — Geração de Documentos Estratégicos
- [x] **`sugerir_processos`** — ferramenta de consulta; single-linkage clustering de questões IBIS por overlap Jaccard de keywords; filtra clusters com ≥ `min_reunioes` reuniões; verifica contra BPMNs existentes para evitar duplicatas; infere etapas das alternativas IBIS escolhidas; sem LLM (algoritmo determinístico)
- [x] **`gerar_deck_executivo`** — ferramenta de consulta; coleta BMM, CKF, breakdown de requisitos, processos BPMN, ROI-TR, encaminhamentos; chama LLM para gerar deck de 7 slides em Markdown (`incluir_secoes` configurável); suporta `tema_cores` para personalização visual
- [x] **`gerar_project_charter`** — ferramenta de consulta; agrega todos os artefatos do projeto; chama LLM para gerar Project Charter formal PMO em Markdown (10 seções); flags booleanas `incluir_riscos|cronograma|stakeholders|escopo`
- [x] **`_llm_call()` helper** — método privado compartilhado em `AssistantToolExecutor`; roteamento OpenAI-compat / Anthropic; evita duplicação de código entre `simular_cenario`, `gerar_deck_executivo` e `gerar_project_charter`
- [x] **`_ADMIN_TOOLS` atualizado** — `inserir_secao_ata`, `mesclar_reunioes`, `sincronizar_calendario` adicionados ao frozenset; perfil não-admin vê apenas ferramentas de consulta e escrita leve
- [x] **`_TOOL_CATEGORIES` atualizado** — todas as 10 novas ferramentas categorizadas: Fase 2 escrita/admin, Fases 3–4 como consulta
