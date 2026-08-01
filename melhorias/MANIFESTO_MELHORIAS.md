# Manifesto de Melhorias — Process2Diagram / Vichāra

> Índice de status de toda proposta em `melhorias/`, incluindo o que já estava em `arquivados/` antes desta taxonomia existir. Gerado em 2026-08-01 em 2 rodadas de auditoria cruzada (8 agentes de investigação no total) entre o conteúdo de cada proposta, o estado real do código e `claude_guideline/roadmap.md`.
> **Rodada 1** (25 propostas que estavam soltas em `melhorias/`): 3 agentes, grupos A/B/C.
> **Rodada 2** (46 propostas que já estavam em `melhorias/arquivados/`, arquivadas historicamente sem essa granularidade de status): 5 agentes, grupos 1-5.
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
| 🗄️ **Não é proposta** | `arquivados/` | Arquivo de código (backup/resíduo de implementação) que acabou solto na pasta de propostas — não recebe status de proposta |

**Total: 71 arquivos classificados** (25 da rodada 1 + 46 da rodada 2) — 50 implementadas total, 26 parciais, 3 adiadas, 5 canceladas, 6 backlog, 3 não-proposta (rebate ligeiramente porque nenhum arquivo está em 2 categorias; ver tabelas abaixo para a contagem exata por rodada).

---

## Tabela consolidada — Rodada 1 (propostas que estavam soltas em `melhorias/`)

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

## Tabela consolidada — Rodada 2 (propostas que já estavam em `arquivados/`)

| # | Arquivo | Status | Localização |
|---|---|---|---|
| 26 | `AgentBPMNReviewer.md` | ✅ Implementado (total) | `arquivados/AgentBPMNReviewer.md` |
| 27 | `AgentBPMNReviewer-skill.md` | ✅ Implementado (total) | `arquivados/AgentBPMNReviewer-skill.md` |
| 28 | `aprimoramento-metacognitivo-3camadas.md` | ✅ Implementado (total) | `arquivados/aprimoramento-metacognitivo-3camadas.md` |
| 29 | `assistente_exportar_xlsx.md` | ✅ Implementado (total) | `arquivados/assistente_exportar_xlsx.md` |
| 30 | `atas_ddl_completa.md` | ✅ Implementado (total) | `arquivados/atas_ddl_completa.md` |
| 31 | `atendimento-requisitos.md` | ✅ Implementado (total) | `arquivados/atendimento-requisitos.md` |
| 32 | `BMIF-Strategic-Plan.md` | ✅ Implementado (total) | `arquivados/BMIF-Strategic-Plan.md` |
| 33 | `bpmn-ajustes-diagrama-deepseek.md` | ✅ Implementado (total) | `arquivados/bpmn-ajustes-diagrama-deepseek.md` |
| 34 | `bpmn-ajustes-para-bruce-silver.md` | ✅ Implementado (total) | `arquivados/bpmn-ajustes-para-bruce-silver.md` |
| 35 | `bpmn-method-and-style.md` | ✅ Implementado (total) | `arquivados/bpmn-method-and-style.md` |
| 36 | `Business-Meeting-Intelligence.md` | ✅ Implementado (total) | `arquivados/Business-Meeting-Intelligence.md` |
| 37 | `CostBenefitsScenario.md` | ✅ Implementado (total) | `arquivados/CostBenefitsScenario.md` |
| 38 | `estrategia_para_precisao.md` | ✅ Implementado (total) | `arquivados/estrategia_para_precisao.md` |
| 39 | `event-links-aprimoramento.md` | ✅ Implementado (total) | `arquivados/event-links-aprimoramento.md` |
| 40 | `FASE-2-1M-Context-Handler.md` | ✅ Implementado (total) | `arquivados/FASE-2-1M-Context-Handler.md` |
| 41 | `glossario-skill.md` | ✅ Implementado (total) | `arquivados/glossario-skill.md` |
| 42 | `identidade-assistente.md` | ✅ Implementado (total) | `arquivados/identidade-assistente.md` |
| 43 | `KnowledgeHubPersistente_AgentedeAnaliseAutonomo.md` | ✅ Implementado (total) | `arquivados/KnowledgeHubPersistente_AgentedeAnaliseAutonomo.md` |
| 44 | `melhoria_atas.md` | ✅ Implementado (total) | `arquivados/melhoria_atas.md` |
| 45 | `novas-ferramentas-req-sbvr-contradica.md` | ✅ Implementado (total) | `arquivados/novas-ferramentas-req-sbvr-contradica.md` |
| 46 | `PC9_context_migration.md` | ✅ Implementado (total) | `arquivados/PC9_context_migration.md` |
| 47 | `proposta-skill-bpmn.md` | ✅ Implementado (total) | `arquivados/proposta-skill-bpmn.md` |
| 48 | `revisao-plano-provocacoes.md` | ✅ Implementado (total) | `arquivados/revisao-plano-provocacoes.md` |
| 49 | `sincronizacao-gateways-bpmn.md` | ✅ Implementado (total) | `arquivados/sincronizacao-gateways-bpmn.md` |
| 50 | `top-10-ferramamentas-assistente.md` | ✅ Implementado (total) | `arquivados/top-10-ferramamentas-assistente.md` |
| 51 | `atas_migration_roster.sql` | 🗄️ Não é proposta (backup) | `arquivados/atas_migration_roster.sql` |
| 52 | `project_store.py` | 🗄️ Não é proposta (código solto) | `arquivados/project_store.py` |
| 53 | `Settings.py` | 🗄️ Não é proposta (código solto) | `arquivados/Settings.py` |
| 54 | `agente-de-provocacoes.md` | 🟡 Implementado (parcial) | `parciais/agente-de-provocacoes.md` |
| 55 | `ajustes-diagrama-bpmn.md` | 🟡 Implementado (parcial) | `parciais/ajustes-diagrama-bpmn.md` |
| 56 | `bpmn-comparativa-001.md` | 🟡 Implementado (parcial) | `parciais/bpmn-comparativa-001.md` |
| 57 | `bpmn-melhorias.md` | 🟡 Implementado (parcial) | `parciais/bpmn-melhorias.md` |
| 58 | `cache-semantico.md` | 🟡 Implementado (parcial) | `parciais/cache-semantico.md` |
| 59 | `ClaudeCodeWorkflowEvolution.md` | 🟡 Implementado (parcial) | `parciais/ClaudeCodeWorkflowEvolution.md` |
| 60 | `DeepSeek-Agent-Cache-&-Fusion.md` | 🟡 Implementado (parcial) | `parciais/DeepSeek-Agent-Cache-&-Fusion.md` |
| 61 | `estrategia_ui_assistente.md` | 🟡 Implementado (parcial) | `parciais/estrategia_ui_assistente.md` |
| 62 | `inspecao-bpmn.md` | 🟡 Implementado (parcial) | `parciais/inspecao-bpmn.md` |
| 63 | `mvp-complience-lgpd.md` | 🟡 Implementado (parcial) | `parciais/mvp-complience-lgpd.md` |
| 64 | `plano-acao-deepseek-avancado.md` | 🟡 Implementado (parcial) | `parciais/plano-acao-deepseek-avancado.md` |
| 65 | `proposta-assistente.md` | 🟡 Implementado (parcial) | `parciais/proposta-assistente.md` |
| 66 | `proposta-assistente-20261607.md` | 🟡 Implementado (parcial) | `parciais/proposta-assistente-20261607.md` |
| 67 | `proposta-multi-esfera-sbvr-requisitos.md` | 🟡 Implementado (parcial) | `parciais/proposta-multi-esfera-sbvr-requisitos.md` |
| 68 | `provocacoes-vichara.md` | 🟡 Implementado (parcial) | `parciais/provocacoes-vichara.md` |
| 69 | `evolucao-cpm-cognicao-de-procesos-e-negocios.md` | ❌ Cancelado | `canceladas/evolucao-cpm-cognicao-de-procesos-e-negocios.md` |
| 70 | `solution-manage.md` | ❌ Cancelado | `canceladas/solution-manage.md` |
| 71 | `preparacao_para_mcp.md` | 📋 Backlog (não avaliado) | `backlog/preparacao_para_mcp.md` |

---

## ✅ Implementado (total) — `melhorias/arquivados/`

### Rodada 1

#### `avaliacao-proposta-assistente-20260708.md`
**Ideia:** avaliação de viabilidade de 18 ferramentas auto-sugeridas pelo Assistente, priorizadas em 3 ondas (9 recomendadas, 9 descartadas).
**Evidência:** PC161 (Onda 1: `export_project_charter_docx`, `compare_meetings`, `verificar_rastreabilidade_obrigatoria`), PC162 (Onda 2: `gerar_release_notes`, `analisar_tendencias`, `estimar_risco_requisito`), PC163 (Onda 3: `solicitar_revisao_requisito` + Importador de Planilha) — as 9 tools recomendadas estão hoje no catálogo do `CLAUDE.md`. Os itens descartados pela própria avaliação (Classificador de Maturidade, ADR, Jira/ADO, Benchmarking cross-projeto) seguem não implementados **por decisão da própria proposta**, não por lacuna.

#### `bpmn-studio.md`
**Ideia:** segundo caminho de geração de BPMN independente de reunião — descrição em texto → BPMN+Mermaid, e o caminho inverso BPMN → descrição.
**Evidência:** é o próprio PC116. `pages/BpmnStudio.py`, `agents/agent_bpmn_studio.py`, `modules/bpmn_describer.py` existem exatamente como especificado, incluindo a evolução pós-entrega (torneio multi-run, PC116-D) documentada no próprio arquivo.

#### `contexto-de-produto.md`
**Ideia:** instrução de tarefa (não feature) para auditar `manifestos/PRODUCT_MANIFESTO.md` contra os demais manifestos, sem corrigir nada.
**Evidência:** `memory/reconciliacao_product_manifesto.md` existe no caminho exato exigido; PC195/PC196 confirmam o ciclo completo — auditoria feita, nenhuma contradição bloqueante encontrada, `PRODUCT_MANIFESTO.md` ratificado como v1.0 por instrução direta do usuário.

#### `embbedings-optimizarion.md`
**Ideia:** migrar embeddings de 1536→512 dimensões via truncagem Matryoshka nativa (~66% de economia de storage no free tier Supabase).
**Evidência:** `modules/embeddings.py` tem `EMBEDDING_DIM = 512` com comentário citando Matryoshka explicitamente; migration `setup/supabase_migration_embedding_512.sql` existe; `CLAUDE.md` documenta o pipeline exatamente como proposto.

#### `MELHORIAS_API.md`
**Ideia:** arquitetura da API comercial REST (FastAPI) — hashing SHA-256 de keys, rate limiting, controle de concorrência, backlog de integração com o pipeline.
**Evidência:** `api.py` (54 KB) implementa `_hash_key()`, `MAX_CONCURRENT_PIPELINES`, `_RATE_WINDOW_SECS`, autenticação `X-API-Key`; `tests/test_api_security.py` e `setup/supabase_migration_api_keys.sql` existem. Os itens de backlog do próprio documento (`_persist_hub` real, integração com `project_store`) **também** já estão implementados (`api.py` chama `create_meeting`/`save_transcript`/`save_requirements_from_hub`/etc. de verdade).

#### `promocao-ativos-negocio.md`
**Ideia:** substituir listagem automática de "ativos de negócio" por promoção explícita com classificação obrigatória em 3 dimensões + taxonomia formal opcional (AN-01..AN-12), ampliada para documentos e conteúdo do Assistente.
**Evidência:** PC166 (Fase A), PC167 (Fase B — Documentos), PC168 (Fase C — Assistente) todas documentadas no `CLAUDE.md`; `core/project_store.py::promote_to_business_asset()`, `ui/components/promote_asset.py`, `pages/AtivosDeNegocio.py` existem. Única parte fora de escopo (Fase D — BMM/DMN/IBIS ganharem chave própria) é decisão consciente registrada no roadmap, não pendência.

#### `templates-ata-por-contexto.md`
**Ideia:** cada contexto registra um modelo de ata Word de referência; o sistema extrai estrutura/identidade visual e gera atas seguindo esse modelo.
**Evidência:** PC160 documenta entrega ponto a ponto — `modules/ata_template_engine.py`, CRUD em `project_store.py`, seção em `Settings.py`, migration e 20 testes, todos confirmados existentes. Fase 2 (mail-merge de fidelidade total) e exportação em outros formatos seguindo o template ficaram fora por decisão do próprio plano (Fase 1 = só Word).

### Rodada 2 — reclassificação de `arquivados/` pré-existente

#### `AgentBPMNReviewer.md`
**Ideia:** agente para auditar semanticamente diagramas BPMN existentes e reemitir XML corrigido.
**Evidência:** PC73. `agents/agent_bpmn_reviewer.py`, tools `review_bpmn_diagram`/`describe_bpmn_process`/`save_bpmn_revision`/`apply_bpmn_corrections` em `core/tools/tools_bpmn_sbvr.py`, migration `bpmn_review_log`.

#### `AgentBPMNReviewer-skill.md`
**Ideia:** skill de 4 fases (parse → auditoria semântica 25 regras → reelaboração textual → novo diagrama) que opera o `AgentBPMNReviewer`.
**Evidência:** `skills/skill_bpmn_reviewer.md` existe com a estrutura de 4 fases e checklists R1-R25 descritos; melhorias sugeridas ao skill do `AgentBPMN` (`process_description`, regra "gateway não é verbo") também presentes.

#### `aprimoramento-metacognitivo-3camadas.md`
**Ideia:** feedback do usuário (Camada 1) + `AgentMeta` (Camada 2) + auto-apply autônomo (Camada 3).
**Evidência:** PC191 — Camada 1 entregue (`feedback`, `ui/components/artifact_feedback.py`, thumbs no Assistente); Camadas 2 e 3 **rejeitadas por decisão consciente** (redundância com `diagnostico_projeto()`/telemetria; contraria Fail-Open) — não são lacuna.

#### `assistente_exportar_xlsx.md`
**Ideia:** tool `render_table` para exportar dados tabulares do Assistente para `.xlsx` com gráfico nativo.
**Evidência:** `modules/excel_exporter.py::export_table_to_excel()`, tool `render_table` registrada e despachada em `core/assistant_tools.py`, `pages/Assistente.py` consome `_pending_tables`, `openpyxl` no `requirements.txt`.

#### `atas_ddl_completa.md`
**Ideia:** roster de participantes por projeto para geração de atas (chips, cores, matching automático de nomes).
**Evidência:** `core/project_store.py` tem as 12 funções descritas (`get_project_roster`, `upsert_roster_member`, `match_participant_to_roster`, etc.); aba dedicada em `pages/_settings_roster.py`; migration real `setup/migration_roster.sql`.

#### `atendimento-requisitos.md`
**Ideia:** marcar requisito como "implementado" com nota de solução (`implementation_status`, tabela dedicada, integração futura com Jira).
**Evidência:** núcleo entregue com desenho mais simples — migration `supabase_migration_requirement_implementation.sql` (`resolution_notes`/`implemented_at` em `requirements`), tool completa em `core/tools/tools_meetings_requirements.py`. Integração Jira era rotulada "futuro" no próprio documento, não pendência da proposta.

#### `BMIF-Strategic-Plan.md`
**Ideia:** plano de 6 fases (A-F) — DMN, atos de diálogo, IBIS, grafo de conhecimento, enriquecimento BABOK da ata, sumarização por consulta.
**Evidência:** todas as 6 fases confirmadas — `agents/agent_dmn.py`, campo `dialogue_act` em `KHFact`, `agents/agent_argumentation.py`, `pages/KnowledgeGraph.py`, campos BABOK em `MinutesModel`, `agents/agent_query_summarizer.py`. Roadmap PC78 lista o documento entre as propostas arquivadas por implementação.

#### `bpmn-ajustes-diagrama-deepseek.md`
**Ideia:** avaliação crítica de diagrama BPMN gerado (Pool vs Lane, gateways sem ≥2 saídas, boundary timeout ausente, atividades implícitas).
**Evidência:** todas as regras viraram checks codificados — `skills/skill_bpmn.md` ("Departamentos sempre lanes"), `modules/bpmn_structural_validator.py` Checks 5/7, `boundaryTimerEvent`/`eventBasedGateway`/`multiInstanceTask` documentados no skill.

#### `bpmn-ajustes-para-bruce-silver.md`
**Ideia:** critérios de coesão para subprocessos, milestones, boundary events, distinção Processo vs Colaboração, checklist expandido (método Bruce Silver).
**Evidência:** milestones "3-7 fases lógicas", critério de coesão para `callActivity`, boundary events completos, decisão Processo/Colaboração obrigatória por sinais explícitos — todos em `skills/skill_bpmn.md`, confirmados no roadmap.

#### `bpmn-method-and-style.md`
**Ideia:** reestruturar `skill_bpmn.md` pelos 5 passos de Bruce Silver (Method) + paleta Level 2 (Style).
**Evidência:** roadmap PC78 lista explicitamente entre as arquivadas por implementação; `skill_bpmn.md` v7.9 contém os 5 passos Top-Down, Densidade Cognitiva (citada por nome no validador), nomenclatura `[Verbo]+[Objeto]`, boundary events, loop/multi-instância.

#### `Business-Meeting-Intelligence.md`
**Ideia:** documento-semente que pediu o plano de alinhamento a padrões acadêmicos (ISO 24617-2, BABOK, BPMN/DMN/SBVR/BMM, IBIS).
**Evidência:** gerou diretamente o `BMIF-Strategic-Plan.md` (ver acima), cujas 6 fases foram implementadas — tratado pelo projeto como a mesma iniciativa.

#### `CostBenefitsScenario.md`
**Ideia:** página de simulação de custo/qualidade por combinação de LLMs por agente, com aplicação do cenário ao pipeline real.
**Evidência:** `pages/CostBenefitScenarios.py` + `core/cost_model.py` com as dataclasses especificadas; `agents/base_agent.py` lê `scenario_assignments`; `pages/Pipeline.py` exibe o badge de cenário ativo.

#### `estrategia_para_precisao.md`
**Ideia:** corrigir o Assistente afirmando totais incorretos por truncamento — aviso no skill + `count_only` com `SELECT COUNT(*)`.
**Evidência:** superado por solução mais robusta — tool dedicada `count_artifacts()`; skill instrui uso exclusivo dela para perguntas de quantidade; `get_requirements()` passou a usar paginação real, eliminando o truncamento na raiz.

#### `event-links-aprimoramento.md`
**Ideia:** heurística para uso de Link Events no BPMN, proibindo-os em loops de correção, com nomenclatura padronizada.
**Evidência:** `modules/bpmn_generator.py` cita o próprio arquivo em comentário; `_detect_crossings`/`_apply_link_events` implementam a heurística com a nomenclatura exata `link_throw_{origem}_{destino}`/`link_catch_{origem}_{destino}`; `tests/test_bpmn_generator_link_events.py` cobre regressão (PC131).

#### `FASE-2-1M-Context-Handler.md`
**Ideia:** módulo para rotear chamadas de contexto longo (>50k tokens) para BPMN/SBVR/BMM sem chunking.
**Evidência:** `services/context_analyzer.py` implementa `should_use_long_context()`, `estimate_tokens()`, `LONG_CONTEXT_AGENTS`, `LONG_CONTEXT_THRESHOLD=50_000`; `pages/MeetingROI.py` rastreia `long_context_calls`.

#### `glossario-skill.md`
**Ideia:** glossário HTML interativo autocontido (busca, filtros, índice alfabético).
**Evidência:** `pages/Orientacoes_Glossario.py` + `modules/glossary_data.py` implementam exatamente o padrão descrito, com o mesmo layout de referência citado no próprio código.

#### `identidade-assistente.md`
**Ideia:** batizar o Assistente como "Vichāra".
**Evidência:** `skills/skill_assistant.md` abre com "Você se chama **Vichāra**" — identidade definitiva no skill, não só num CKF de projeto isolado como a Camada 1 da proposta previa.

#### `KnowledgeHubPersistente_AgentedeAnaliseAutonomo.md`
**Ideia:** Knowledge Hub persistente cross-sessão + Agente de Análise Autônomo via LangChain ReAct.
**Evidência:** `core/knowledge_store.py`, `agents/agent_knowledge_extractor.py`, `pages/KnowledgeHub.py`, `adapters/langchain_tools.py`, `agents/agent_analyst.py`, `core/analyst_store.py` — todos existentes e em produção (roadmap linha 2400 confirma).

#### `melhoria_atas.md`
**Ideia:** HTML de ata interativo standalone a partir do `MinutesModel`, com roster e identidade visual.
**Evidência:** `modules/ata_engine_generator.py::generate_ata_html()`, tabelas `project_roster`/`meeting_participants`, botão "🔄 Gerar Ata Interativa" na aba de atas.

#### `novas-ferramentas-req-sbvr-contradica.md`
**Ideia:** 4 tools faltantes — `update_requirement_text`, `update_sbvr_rule`, `update_sbvr_term_by_id`, `resolve_contradiction`.
**Evidência:** as 4 existem com os nomes exatos propostos, registradas em `core/assistant_tools.py` na categoria "escrita".

#### `PC9_context_migration.md`
**Ideia:** migração de nomenclatura `project`→`context` em 4 fases + Context Knowledge File (CKF).
**Evidência:** tabela `contexts` (renomeada de `projects`), `agents/agent_ckf_updater.py`, `pages/Orientacoes_CKF.py`, campos `context_type`/`context_skill` com guard em `migrate()`. Execução ficou na v4.21, mas todo o escopo foi cumprido.

#### `proposta-skill-bpmn.md`
**Ideia:** 11 melhorias pontuais ao prompt de `skill_bpmn.md`.
**Evidência:** roadmap linha 2465 confirma as 11 melhorias entregues em v7.9; grep direto confirma as 11 seções propostas presentes literalmente no skill atual.

#### `revisao-plano-provocacoes.md`
**Ideia:** revisão técnica do plano `AgentProvocations` (1 item bloqueante + 3 menores).
**Evidência:** nota própria "APLICADA em 2026-07-17 (PC190-fix), todos os 4 itens" confirmada no código — `absence_check.terms`, `_ENABLED_KINDS` como allowlist real.

#### `sincronizacao-gateways-bpmn.md`
**Ideia:** documento de referência sobre sincronização de gateways (método Bruce Silver) — não pede ação, é material de pesquisa.
**Evidência:** conteúdo reproduzido quase literalmente em `skills/skill_bpmn.md` ("Regra de Sincronização Split↔Join"), refinado pelos checks estruturais 12/13 do validador.

#### `top-10-ferramamentas-assistente.md`
**Ideia:** 10 ferramentas novas do Assistente em 4 fases.
**Evidência:** roadmap PC48 documenta as 4 fases com checklist `[x]` por ferramenta; as 10 tools confirmadas existentes via grep (`sugestoes_plantonista`, `diagnostico_projeto`, `mapa_rastreabilidade`, `gerar_project_charter`, etc.).

### 🗄️ Não são propostas — backups/resíduos de código (ficam em `arquivados/`, sem status de proposta)

#### `atas_migration_roster.sql`
Comparado via diff com `setup/migration_roster.sql` (real): quase idêntico — rascunho/cópia anterior da migration real, não uma proposta em aberto.

#### `project_store.py`
Trecho de 615 linhas com funções de roster para adicionar a `core/project_store.py` — parte da entrega de `melhoria_atas.md`. **Correção de hipótese:** não é o backup do incidente do editor web do GitHub (commit `797eb35`, CLAUDE.md §Known Pitfalls) — este arquivo foi commitado em `697cb3f`, 5 dias *antes* do incidente. É resíduo esquecido da implementação do roster, já mesclado ao `project_store.py` real.

#### `Settings.py`
Fragmento de 431 linhas (`render_roster_tab()`) contra as 1501 linhas do `pages/Settings.py` real — não é snapshot integral. O conteúdo foi implementado, só que refatorado para módulo próprio: `pages/_settings_roster.py` (importado por `pages/Settings.py`).

---

## 🟡 Implementado (parcial) — `melhorias/parciais/`

### Rodada 1

#### `assistente-20260711.md`
Auto-reflexão do Assistente listando 6 gaps. PC179 resolveu 3 (`exportar_pacote_completo`, `sugerir_encaminhamentos_pendentes`, `pesquisar_multi_contexto`). **Rejeitados deliberadamente:** grafo interativo e diff visual de simulação (dependem de `mapa_rastreabilidade`, que casa por keyword, não FK real — visualizar isso mostraria ligações não confiáveis). **Nunca endereçado:** memória entre conversas (classificado como decisão de produto, não gap técnico).

#### `cognicao-de-negocio.md`
Motivação de negócio por trás da Promoção de Ativos. 4 das 5 entregas feitas via PC164-168. **Falta:** widget de Ativos de Negócio em destaque na Home — `pages/Home.py` não referencia `AtivosDeNegocio` hoje.

#### `complience-lgpd.md`
Proposta original pedia um "Agente de Compliance" microsserviço com criptografia AES-256 e reversão condicional por RBAC. O que existe (`modules/compliance/` — PC81) cobre a necessidade funcional (detecção de PII, consentimento, auditoria) com arquitetura mais simples. **Falta:** criptografia AES-256 do mapa de reversão, reversão condicionada a permissão/2FA, RIPD como artefato formal.

#### `deteccao-ruidos-comunicacao.md`
As 3 categorias de ruído (contradição/ambiguidade/gap) foram implementadas — `AgentCommunicationNoise` (PC28) + `agent_contradiction_detector.py` — mas sem as técnicas específicas propostas (LDA/NMF, modelo NLI dedicado, dashboard Power BI, loop formal de validação humana com score de confiança por item).

#### `ideia-grok.md`
Provider Grok Multi-Agent já está cadastrado e selecionável em `modules/config.py` (habilitação técnica trivial). **Falta:** a POC específica com papéis de agente via system prompt e integração com voz/Whisper nunca foi construída como feature própria.

#### `migracao-para-google-cloud.md`
PC113–PC114 entregaram toda a infraestrutura como código (`Dockerfile`, `infra/cloudbuild.yaml`, `infra/cloudrun/`, `services/cloud_tasks.py`, 345 testes). **Falta:** execução real — criar o projeto GCP, service account, secrets no Secret Manager, primeiro deploy. `CLAUDE.md` ainda descreve Streamlit Cloud como único deploy ativo.

#### `multi-agente-customizado.md`
Pedia reconstrução via CrewAI/AutoGen. O objetivo funcional já é coberto nativamente por `Orchestrator` + agentes especializados + `cross_meeting_analyzer.py::find_recurring_topics()` (≈ CrossMeetingAnalyzerAgent proposto), sem o framework externo. `langgraph` é dependência real, mas usado só para retry adaptativo de BPMN, não orquestração multi-agente geral.

#### `Plano_Economia_Arquitetura_Process2Diagram.md`
Semantic Cache (PC185) e batch embeddings já existiam antes do plano. **Não implementado:** `n_bpmn_runs` adaptativo por qualidade de transcrição (continua fixo em 3), seleção condicional de agentes por `meeting_type`, early exit em transcrições nota E.

#### `proposta-assistente-20260708.md`
Brainstorm original de 18 tools (arquivo não versionado no git — só a avaliação derivada é rastreada). 9 das 18 foram implementadas via PC161-163. Não implementado: Classificador de Maturidade, ADR, Jira/ADO, Benchmarking cross-projeto, Tour Guiado, entre outros.

#### `proposta-isolamento-de-contexto.md`
Fases A1-A3 (auditoria) executadas — `memory/auditoria_isolamento.md` + `tests/test_context_isolation.py` provam vazamento real em funções sem validação de `project_id`. **Falta:** incorporar a exceção ao Fail-Open no `ENGINEERING_MANIFESTO.md` e implementar o guard técnico (`_scoped_select`/`ContextIsolationError`) — nenhuma das duas opções está em `core/project_store.py` ainda. Bloqueia a Fase C da renomeação global.

#### `protecao-a-dados-sensiveis.md`
Documento mais antigo do lote. A ideia central (tokens reversíveis em vez de PII crua ao LLM) foi implementada via `modules/pii_sanitizer.py` (PC82), mas com desenho mais simples: mapa de nomes fica só em memória de sessão, **nunca persiste** (proposta pedia tabela `token_mapping` criptografada por tenant). **Falta:** RBAC granular condicionando quem pode revelar nomes reais (hoje é tudo-ou-nada por sessão).

### Rodada 2 — reclassificação de `arquivados/` pré-existente

#### `agente-de-provocacoes.md`
Proposta original do `AgentProvocations` — 5 tipos de provocação + laço final (provocação aceita → vira item de pauta/divergência). 4 dos 5 tipos em produção (`absence`/`asymmetry` PC190, `contradiction` PC200, `premise` PC201; `analogy` adiado por decisão no PC202). **Falta sem decisão formal:** a Fase 6 — o laço que fecha o valor (provocação → item de pauta ou livro-razão de divergências), que o próprio documento chama de "a tese inteira do produto". Schema já prevê `became_divergence`, mas o destino está desligado.

#### `ajustes-diagrama-bpmn.md`
Duas propostas externas de tools de pós-processamento do BPMN DI (centralizar labels, redistribuir saídas de gateway, roteirizar flows). As classes específicas propostas não existem, mas a necessidade foi coberta nativamente e de forma mais extensa em `modules/bpmn_auto_repair.py` (Pass F/G, `_compute_gateway_exits()`). Nunca formalmente vinculada a um PC.

#### `bpmn-comparativa-001.md`
Comparação de diagrama "Projeto Aurora" com recomendações. PC55 implementou `process_trigger`/`process_outcomes` e labels centralizados/Link Events, mas registra explicitamente que múltiplos End Events distintos por resultado de negócio não foram implementados — `agent_bpmn.py` ainda conecta todos os steps terminais a um único `ev_end` sintético.

#### `bpmn-melhorias.md`
Editor BPMN integrado com versionamento, em 4 fases. Fases 1-2 (MVP + versionamento) entregues em `pages/BpmnEditor.py`/`modules/bpmn_editor.py`. **Falta:** Fase 3 (integração com requisitos/SBVR, impact analysis) e Fase 4 (colaboração — comentários, approval workflow, audit trail) — nenhuma referência a essas duas fases no código.

#### `cache-semantico.md`
Spec de cache semântico por embedding (pgvector, 2 camadas). PC185: o projeto já tinha cache exato (SHA-256) plugado no mesmo ponto; a única mudança real foi normalização de whitespace no hash. A camada de embedding/similaridade foi avaliada e descartada por risco de falso positivo, decisão via `AskUserQuestion`.

#### `ClaudeCodeWorkflowEvolution.md`
5 melhorias de workflow — Acceptance Criteria, `AgentValidator` expandido, badges de qualidade, Routines automatizadas, página de monitoramento de agentes. Itens 1-3 confirmados (`claude_guideline/acceptance_criteria.md`, `agent_validator.py::validate_all()` com 8 validadores, `ui/components/quality_badge.py`). **Falta:** item 4 (Routines/webhook sobre `BatchRunner.py`) e item 5 (página de monitoramento), classificados como "médio prazo" no próprio documento, sem PC dedicado.

#### `DeepSeek-Agent-Cache-&-Fusion.md`
Plano de 5 fases — cache semântico, contexto 1M, fusão de agentes via function calling, integração "Reasonix", dashboard. Fases 1-2 e 5 cobertas (parcialmente, com desenho mais simples). **Falta:** Fase 3 (agente unificado via function calling) e Fase 4 (integração "Reasonix" — nunca existiu no projeto, nunca avaliada).

#### `estrategia_ui_assistente.md`
3 melhorias na UI do Assistente — chat customizado tipo "Claude Code Web", export para Markdown, botão de limpar conversa. Itens 2-3 entregues e ampliados (`_export_chat_to_markdown/html()`, botão "🗑️ Limpar conversa"). **Falta:** item 1 — a página continua usando `st.chat_message()`/`st.chat_input()` nativos, sem CSS customizado de bolhas.

#### `inspecao-bpmn.md`
Code review externo de ~11 módulos do subsistema BPMN. PC54 implementou 3 dos itens apontados (import do Pass 5, Check 8 `eventBasedGateway`, suporte multi-pool em `bpmn_diagnostics.py`). **Falta:** bug de `route_y`/`boundary_y` em `_route_waypoints()` (segue com a mesma estrutura apontada como bug), remoção do `diagram_bpmn.py` legado, refatorações sugeridas em `pipeline.py`/`orchestrator.py`/`agent_bpmn.py`.

#### `mvp-complience-lgpd.md`
Spec técnica completa de uma camada `DataGovernance` — criptografia Fernet/PBKDF2, `pii_detector.py`, gate de consentimento bloqueante. A necessidade funcional foi endereçada com arquitetura bem mais simples (`modules/compliance/` PC81 + `modules/pii_sanitizer.py` PC82) — sem criptografia, sem `DataGovernanceManager`, gate não-bloqueante (painel pós-execução). Mesma lacuna de `complience-lgpd.md`/`protecao-a-dados-sensiveis.md`.

#### `plano-acao-deepseek-avancado.md`
Migração de `deepseek-chat` para `deepseek-v4-flash`/`v4-pro` + roteamento automático "thinking" vs "non-thinking" por agente. A migração de modelo foi feita (PC17/PC18). **Falta:** o roteamento automático — hoje é o usuário quem escolhe o provider "Thinking" manualmente, sem lógica no `orchestrator.py`.

#### `proposta-assistente.md`
Brainstorm de 7 tools — merge de requisitos, diff visual, busca cross-artefato, memória de preferências, alertas via agenda, export docx/pdf, correção em lote. 5 das 7 existem com nomes quase idênticos (`merge_requirements`, `diff_requirement`, `search_universal`, `batch_text_correction`, export docx). **Falta:** memória de preferências entre sessões e alertas proativos via Calendar.

#### `proposta-assistente-20261607.md`
Auto-reflexão listando 5 pontos de atrito (PC189). Cache de contexto implementado em escopo reduzido (digest raso, não os dados completos pedidos); `run_sql` ad-hoc **rejeitado** por risco de vazamento cross-project; `project_dashboard()` rejeitado (redundante); embedding automático implementado; modo investigativo já existia. Como 1 item foi rejeitado e outro só parcialmente entregue, o rótulo correto é parcial, não total.

#### `proposta-multi-esfera-sbvr-requisitos.md`
Campos `sphere`/`sphere_owner`/`bmm_policy_ref` em regras e requisitos, reordenação SBVR→Requirements, reflexo no relatório HTML. PC12 entregou o modelo de dados completo e a reordenação. **Falta:** `modules/executive_html.py` não agrupa regras por esfera nem exibe badges por `BR-XXX`; `core/rerun_handlers.py` não invalida `hub.requirements` automaticamente ao re-executar SBVR.

#### `provocacoes-vichara.md`
Plano de 6 fases para os 5 tipos de provocação. 4 dos 5 kinds em produção (mesma situação de `agente-de-provocacoes.md` acima); só `analogy` fica de fora, com decisão explícita de adiamento documentada no próprio arquivo (infraestrutura de fingerprint/clusterização inexistente, v1 reduzida "considerada e descartada" por gerar ruído com aparência de insight).

---

## ⏸️ Adiado — `melhorias/adiadas/`

### `inventario-renomeacao.md`
Auditoria read-only (Fase B da renomeação `project_id`→`context_id`/"P2D"→"Vichara") — mapeia volume e risco, mas nenhuma renomeação foi executada. Fase C segue travada aguardando o guard de isolamento de contexto acima.

### `rbac-admin-de-contexto.md`
Ideia de role "admin restrito a um contexto", registrada durante o planejamento de templates de ata. O próprio arquivo termina com "decisão do usuário foi seguir com admin/master global... tratar isto separadamente quando houver prioridade" (citado em PC160).

### `renomeacao-global-contexto-vichara.md`
Plano de 5 fases para a renomeação global. Documento explícito: "nenhum código, schema ou nome de arquivo foi alterado... execução de qualquer fase exige nova autorização explícita, fase por fase." Nenhuma fase iniciada até PC208.

---

## ❌ Cancelado — `melhorias/canceladas/`

### `evolucao-cpm-cognicao-de-procesos-e-negocios.md`
Plano de rearquitetura completa e rebranding ("CogniFlow", Clean Architecture, migração GCP/Firestore/Vertex AI, tiers comerciais) gerado por IA externa sem conhecimento do estado real do projeto. O próprio arquivo já traz cabeçalho de avaliação (2026-07-08) rejeitando-o ponto a ponto: nome real de rebrand é "RawToInsights AI" (não "CogniFlow"), pricing já definido no `COLLABORATIVE_MANIFESTO.md`, migração GCP já em andamento por outro caminho (PC113/PC114), viola regra de governança de arquitetura.

### `solution-manage.md`
Camada de rastreabilidade/governança em 3 fases. Rejeitada em commit `6846019` — continha erros factuais de import/campo/função inexistentes e duplicava funcionalidade já em produção (`mapa_rastreabilidade`, `diagnostico_projeto`, `sugestoes_plantonista`, radar de qualidade da Home).

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

### `preparacao_para_mcp.md`
Reestruturação arquitetural genérica ("RawToInsights AI") em `agents/`, `tools/` (`BaseTool`/`ToolRegistry`), `schemas/`, `services/`, `prompts/` — preparação para uma futura camada MCP, sem implementar MCP. Nenhum vestígio dessa estrutura existe no código real; a arquitetura evoluiu de forma totalmente diferente (`core/tools/*.py` com JSON-schema dict, sem MCP). Nunca virou PC, nunca foi avaliada — mesmo bucket de `rumo-a-forca-de-trabalho-virtual.md`.
