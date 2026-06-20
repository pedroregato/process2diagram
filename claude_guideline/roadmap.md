# Roadmap — Process2Diagram

Histórico completo de entregas por ciclo de projeto.

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
