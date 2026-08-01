# Manifesto de Melhorias — Process2Diagram / Vichāra

> Índice de status de toda proposta viva em `melhorias/`. Gerado em 2026-08-01 por auditoria cruzada (3 agentes de investigação) entre o conteúdo de cada proposta, o estado real do código e `claude_guideline/roadmap.md`.
> **Taxonomia de pastas:** cada status listado abaixo corresponde a uma subpasta física de `melhorias/` — ver [`README.md`](README.md) para a tabela completa. Ao mudar o status de uma proposta, mova o arquivo (`git mv`) para a pasta correspondente **e** atualize a linha dela nesta tabela — o manifesto é o índice, a pasta é a fonte de verdade.
> Reavaliar este manifesto sempre que uma proposta listada como parcial/adiada/backlog ganhar um PC novo no roadmap.

## Legenda de status

| Status | Pasta | Significado |
|---|---|---|
| ✅ **Implementado (total)** | `arquivados/` | Tudo que a proposta pedia foi entregue (ou o que ficou de fora foi decisão consciente documentada no próprio PC, não uma lacuna) |
| 🟡 **Implementado (parcial)** | `parciais/` | Parte real do código existe e resolve a necessidade, mas falta escopo que a proposta original pedia e que segue sem PC dedicado |
| ⏸️ **Adiado** | `adiadas/` | Avaliado, decisão explícita de não fazer agora — plano existe, execução aguarda gatilho/prioridade |
| ❌ **Cancelado** | `canceladas/` | Avaliado e rejeitado — decisão de não fazer, sem previsão de retomada |
| 📋 **Backlog (não avaliado)** | `backlog/` | Nunca virou PC, nunca foi formalmente avaliada/descartada — ideia crua |

---

## Tabela consolidada

| # | Arquivo | Status | Localização |
|---|---|---|---|
| 1 | `avaliacao-proposta-assistente-20260708.md` | ✅ Implementado (total) | `arquivados/avaliacao-proposta-assistente-20260708.md` |
| 2 | `bpmn-studio.md` | ✅ Implementado (total) | `arquivados/bpmn-studio.md` |
| 3 | `contexto-de-produto.md` | ✅ Implementado (total) | `arquivados/contexto-de-produto.md` |
| 4 | `embbedings-optimizarion.md` | ✅ Implementado (total) | `arquivados/embbedings-optimizarion.md` |
| 5 | `MELHORIAS_API.md` | ✅ Implementado (total) | `arquivados/MELHORIAS_API.md` |
| 6 | `promocao-ativos-negocio.md` | ✅ Implementado (total) | `arquivados/promocao-ativos-negocio.md` |
| 7 | `templates-ata-por-contexto.md` | ✅ Implementado (total) | `arquivados/templates-ata-por-contexto.md` |
| 8 | `assistente-20260711.md` | 🟡 Implementado (parcial) | `parciais/assistente-20260711.md` |
| 9 | `cognicao-de-negocio.md` | 🟡 Implementado (parcial) | `parciais/cognicao-de-negocio.md` |
| 10 | `complience-lgpd.md` | 🟡 Implementado (parcial) | `parciais/complience-lgpd.md` |
| 11 | `deteccao-ruidos-comunicacao.md` | 🟡 Implementado (parcial) | `parciais/deteccao-ruidos-comunicacao.md` |
| 12 | `ideia-grok.md` | 🟡 Implementado (parcial) | `parciais/ideia-grok.md` |
| 13 | `migracao-para-google-cloud.md` | 🟡 Implementado (parcial) | `parciais/migracao-para-google-cloud.md` |
| 14 | `multi-agente-customizado.md` | 🟡 Implementado (parcial) | `parciais/multi-agente-customizado.md` |
| 15 | `Plano_Economia_Arquitetura_Process2Diagram.md` | 🟡 Implementado (parcial) | `parciais/Plano_Economia_Arquitetura_Process2Diagram.md` |
| 16 | `proposta-assistente-20260708.md` | 🟡 Implementado (parcial) | `parciais/proposta-assistente-20260708.md` |
| 17 | `proposta-isolamento-de-contexto.md` | 🟡 Implementado (parcial) | `parciais/proposta-isolamento-de-contexto.md` |
| 18 | `protecao-a-dados-sensiveis.md` | 🟡 Implementado (parcial) | `parciais/protecao-a-dados-sensiveis.md` |
| 19 | `inventario-renomeacao.md` | ⏸️ Adiado | `adiadas/inventario-renomeacao.md` |
| 20 | `rbac-admin-de-contexto.md` | ⏸️ Adiado | `adiadas/rbac-admin-de-contexto.md` |
| 21 | `renomeacao-global-contexto-vichara.md` | ⏸️ Adiado | `adiadas/renomeacao-global-contexto-vichara.md` |
| 22 | `Agent-Skills.md` | 📋 Backlog (não avaliado) | `backlog/Agent-Skills.md` |
| 23 | `integracao-Jira.md` | 📋 Backlog (não avaliado) | `backlog/integracao-Jira.md` |
| 24 | `pipeline-metrics.md` | 📋 Backlog (não avaliado) | `backlog/pipeline-metrics.md` |
| 25 | `rumo-a-forca-de-trabalho-virtual.md` | 📋 Backlog (não avaliado) | `backlog/rumo-a-forca-de-trabalho-virtual.md` |

Nenhuma proposta foi classificada como **Cancelada** no nível do arquivo inteiro nesta rodada — quando algo foi rejeitado, foi sub-item dentro de uma proposta parcialmente implementada (ver detalhes abaixo). A pasta `canceladas/` existe pronta para receber a primeira, ver seu `README.md`.

---

## ✅ Implementado (total) — `melhorias/arquivados/`

### `avaliacao-proposta-assistente-20260708.md`
**Ideia:** avaliação de viabilidade de 18 ferramentas auto-sugeridas pelo Assistente, priorizadas em 3 ondas (9 recomendadas, 9 descartadas).
**Evidência:** PC161 (Onda 1: `export_project_charter_docx`, `compare_meetings`, `verificar_rastreabilidade_obrigatoria`), PC162 (Onda 2: `gerar_release_notes`, `analisar_tendencias`, `estimar_risco_requisito`), PC163 (Onda 3: `solicitar_revisao_requisito` + Importador de Planilha) — as 9 tools recomendadas estão hoje no catálogo do `CLAUDE.md`. Os itens descartados pela própria avaliação (Classificador de Maturidade, ADR, Jira/ADO, Benchmarking cross-projeto) seguem não implementados **por decisão da própria proposta**, não por lacuna.

### `bpmn-studio.md`
**Ideia:** segundo caminho de geração de BPMN independente de reunião — descrição em texto → BPMN+Mermaid, e o caminho inverso BPMN → descrição.
**Evidência:** é o próprio PC116. `pages/BpmnStudio.py`, `agents/agent_bpmn_studio.py`, `modules/bpmn_describer.py` existem exatamente como especificado, incluindo a evolução pós-entrega (torneio multi-run, PC116-D) documentada no próprio arquivo.

### `contexto-de-produto.md`
**Ideia:** instrução de tarefa (não feature) para auditar `manifestos/PRODUCT_MANIFESTO.md` contra os demais manifestos, sem corrigir nada.
**Evidência:** `memory/reconciliacao_product_manifesto.md` existe no caminho exato exigido; PC195/PC196 confirmam o ciclo completo — auditoria feita, nenhuma contradição bloqueante encontrada, `PRODUCT_MANIFESTO.md` ratificado como v1.0 por instrução direta do usuário.

### `embbedings-optimizarion.md`
**Ideia:** migrar embeddings de 1536→512 dimensões via truncagem Matryoshka nativa (~66% de economia de storage no free tier Supabase).
**Evidência:** `modules/embeddings.py` tem `EMBEDDING_DIM = 512` com comentário citando Matryoshka explicitamente; migration `setup/supabase_migration_embedding_512.sql` existe; `CLAUDE.md` documenta o pipeline exatamente como proposto.

### `MELHORIAS_API.md`
**Ideia:** arquitetura da API comercial REST (FastAPI) — hashing SHA-256 de keys, rate limiting, controle de concorrência, backlog de integração com o pipeline.
**Evidência:** `api.py` (54 KB) implementa `_hash_key()`, `MAX_CONCURRENT_PIPELINES`, `_RATE_WINDOW_SECS`, autenticação `X-API-Key`; `tests/test_api_security.py` e `setup/supabase_migration_api_keys.sql` existem. Os itens de backlog do próprio documento (`_persist_hub` real, integração com `project_store`) **também** já estão implementados (`api.py` chama `create_meeting`/`save_transcript`/`save_requirements_from_hub`/etc. de verdade).

### `promocao-ativos-negocio.md`
**Ideia:** substituir listagem automática de "ativos de negócio" por promoção explícita com classificação obrigatória em 3 dimensões + taxonomia formal opcional (AN-01..AN-12), ampliada para documentos e conteúdo do Assistente.
**Evidência:** PC166 (Fase A), PC167 (Fase B — Documentos), PC168 (Fase C — Assistente) todas documentadas no `CLAUDE.md`; `core/project_store.py::promote_to_business_asset()`, `ui/components/promote_asset.py`, `pages/AtivosDeNegocio.py` existem. Única parte fora de escopo (Fase D — BMM/DMN/IBIS ganharem chave própria) é decisão consciente registrada no roadmap, não pendência.

### `templates-ata-por-contexto.md`
**Ideia:** cada contexto registra um modelo de ata Word de referência; o sistema extrai estrutura/identidade visual e gera atas seguindo esse modelo.
**Evidência:** PC160 documenta entrega ponto a ponto — `modules/ata_template_engine.py`, CRUD em `project_store.py`, seção em `Settings.py`, migration e 20 testes, todos confirmados existentes. Fase 2 (mail-merge de fidelidade total) e exportação em outros formatos seguindo o template ficaram fora por decisão do próprio plano (Fase 1 = só Word).

---

## 🟡 Implementado (parcial) — `melhorias/parciais/`

### `assistente-20260711.md`
Auto-reflexão do Assistente listando 6 gaps. PC179 resolveu 3 (`exportar_pacote_completo`, `sugerir_encaminhamentos_pendentes`, `pesquisar_multi_contexto`). **Rejeitados deliberadamente:** grafo interativo e diff visual de simulação (dependem de `mapa_rastreabilidade`, que casa por keyword, não FK real — visualizar isso mostraria ligações não confiáveis). **Nunca endereçado:** memória entre conversas (classificado como decisão de produto, não gap técnico).

### `cognicao-de-negocio.md`
Motivação de negócio por trás da Promoção de Ativos. 4 das 5 entregas feitas via PC164-168. **Falta:** widget de Ativos de Negócio em destaque na Home — `pages/Home.py` não referencia `AtivosDeNegocio` hoje.

### `complience-lgpd.md`
Proposta original pedia um "Agente de Compliance" microsserviço com criptografia AES-256 e reversão condicional por RBAC. O que existe (`modules/compliance/` — PC81) cobre a necessidade funcional (detecção de PII, consentimento, auditoria) com arquitetura mais simples. **Falta:** criptografia AES-256 do mapa de reversão, reversão condicionada a permissão/2FA, RIPD como artefato formal.

### `deteccao-ruidos-comunicacao.md`
As 3 categorias de ruído (contradição/ambiguidade/gap) foram implementadas — `AgentCommunicationNoise` (PC28) + `agent_contradiction_detector.py` — mas sem as técnicas específicas propostas (LDA/NMF, modelo NLI dedicado, dashboard Power BI, loop formal de validação humana com score de confiança por item).

### `ideia-grok.md`
Provider Grok Multi-Agent já está cadastrado e selecionável em `modules/config.py` (habilitação técnica trivial). **Falta:** a POC específica com papéis de agente via system prompt e integração com voz/Whisper nunca foi construída como feature própria.

### `migracao-para-google-cloud.md`
PC113–PC114 entregaram toda a infraestrutura como código (`Dockerfile`, `infra/cloudbuild.yaml`, `infra/cloudrun/`, `services/cloud_tasks.py`, 345 testes). **Falta:** execução real — criar o projeto GCP, service account, secrets no Secret Manager, primeiro deploy. `CLAUDE.md` ainda descreve Streamlit Cloud como único deploy ativo.

### `multi-agente-customizado.md`
Pedia reconstrução via CrewAI/AutoGen. O objetivo funcional já é coberto nativamente por `Orchestrator` + agentes especializados + `cross_meeting_analyzer.py::find_recurring_topics()` (≈ CrossMeetingAnalyzerAgent proposto), sem o framework externo. `langgraph` é dependência real, mas usado só para retry adaptativo de BPMN, não orquestração multi-agente geral.

### `Plano_Economia_Arquitetura_Process2Diagram.md`
Semantic Cache (PC185) e batch embeddings já existiam antes do plano. **Não implementado:** `n_bpmn_runs` adaptativo por qualidade de transcrição (continua fixo em 3), seleção condicional de agentes por `meeting_type`, early exit em transcrições nota E.

### `proposta-assistente-20260708.md`
Brainstorm original de 18 tools (arquivo não versionado no git — só a avaliação derivada é rastreada). 9 das 18 foram implementadas via PC161-163. Não implementado: Classificador de Maturidade, ADR, Jira/ADO, Benchmarking cross-projeto, Tour Guiado, entre outros.

### `proposta-isolamento-de-contexto.md`
Fases A1-A3 (auditoria) executadas — `memory/auditoria_isolamento.md` + `tests/test_context_isolation.py` provam vazamento real em funções sem validação de `project_id`. **Falta:** incorporar a exceção ao Fail-Open no `ENGINEERING_MANIFESTO.md` e implementar o guard técnico (`_scoped_select`/`ContextIsolationError`) — nenhuma das duas opções está em `core/project_store.py` ainda. Bloqueia a Fase C da renomeação global.

### `protecao-a-dados-sensiveis.md`
Documento mais antigo do lote. A ideia central (tokens reversíveis em vez de PII crua ao LLM) foi implementada via `modules/pii_sanitizer.py` (PC82), mas com desenho mais simples: mapa de nomes fica só em memória de sessão, **nunca persiste** (proposta pedia tabela `token_mapping` criptografada por tenant). **Falta:** RBAC granular condicionando quem pode revelar nomes reais (hoje é tudo-ou-nada por sessão).

---

## ⏸️ Adiado — `melhorias/adiadas/`

### `inventario-renomeacao.md`
Auditoria read-only (Fase B da renomeação `project_id`→`context_id`/"P2D"→"Vichara") — mapeia volume e risco, mas nenhuma renomeação foi executada. Fase C segue travada aguardando o guard de isolamento de contexto acima.

### `rbac-admin-de-contexto.md`
Ideia de role "admin restrito a um contexto", registrada durante o planejamento de templates de ata. O próprio arquivo termina com "decisão do usuário foi seguir com admin/master global... tratar isto separadamente quando houver prioridade" (citado em PC160).

### `renomeacao-global-contexto-vichara.md`
Plano de 5 fases para a renomeação global. Documento explícito: "nenhum código, schema ou nome de arquivo foi alterado... execução de qualquer fase exige nova autorização explícita, fase por fase." Nenhuma fase iniciada até PC208.

---

## 📋 Backlog (não avaliado) — `melhorias/backlog/`

### `Agent-Skills.md`
Reestruturar `skills/*.md` para o padrão "Agent Skills" de produção (pastas próprias, `SKILL.md`, `references/`/`scripts/`/`assets/`). Nunca virou PC, nunca foi formalmente avaliada.

### `integracao-Jira.md`
Camada "Agile Bridge" para exportar requisitos ao Jira via API REST v3. Listada em PC163/PC78 como "sem plano de execução — aguardando demanda". Mistura contexto de uma arquitetura (Firestore/GCP) que não é a real.

### `pipeline-metrics.md`
Proposta de instrumentar um suposto módulo "Live Transcription" (Extractor/Synthesizer agents, tabela `pipeline_metrics`) que **não existe e nunca existiu** no código real — gerada especulativamente, sem checar o codebase. O que ela realmente busca (observabilidade de degradação por tenant) já existe com nomes reais diferentes em `services/llm_telemetry.py` (PC183/PC207).

### `rumo-a-forca-de-trabalho-virtual.md`
Migrar tools "bespoke" para protocolos abertos (MCP para ferramentas, A2A para agentes negociarem entre si, A2UI para UI declarativa). Listada em PC78 como proposta futura sem plano. O `mcp/google_calendar_server.py` existente é infraestrutura paralela restrita a um domínio, não uma implementação desta proposta.

---

## ❌ Cancelado — `melhorias/canceladas/`

Vazio nesta rodada. Ver critério em [`canceladas/README.md`](canceladas/README.md).
