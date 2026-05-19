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

### PC12 — Concluído (v4.20+ / 2026-05-18–19)
- [x] **Phase F — AgentQuerySummarizer** — `agents/agent_query_summarizer.py` + `skills/skill_query_summarizer.md`; 4 perspectivas (Executivo, Técnico, Gestor, Conformidade); `QuerySummaryModel` + `PerspectiveSummary` em `knowledge_hub.py`; `ui/tabs/query_summary_tab.py` (icon + headline blockquote + highlights + open_items + actions); Orchestrator Step 6d; sidebar checkbox + re-run button; export Markdown; `migrate()` guard v4.24; default False
- [x] **Multi-sphere SBVR (Fase G)** — `BusinessRule` com `sphere`, `sphere_owner`, `bmm_policy_ref`, `speaker_quote`; `RequirementItem` com `business_rule_refs: list` + `sphere: Optional[str]`; `_VALID_SPHERES` frozenset; **SBVR reordenado para Step 2.5** (antes de Minutes+Requirements) para rastreabilidade de BR-IDs; `skill_sbvr.md` atualizado com tabela de esferas; `sbvr_tab.py` reescrito com métricas, agrupamento por esfera, filtro, speaker_quote, bmm_policy_ref, requisitos vinculados
- [x] **Glossário** — `pages/Orientacoes_Glossario.py`; 6 abas de categoria (BPMN/Process, Requisitos, Linguagem de Negócio, Qualidade, Tecnologia, Metodologia) + aba Referências (16 specs/libs); CSS dark-navy matching outras páginas Orientações; registrado em `app.py` Ajuda após "Como Iniciar"
- [x] **Cobertura completa de reprocessamento** — `run_knowledge_extractor` + `run_query_summarizer` adicionados aos 3 caminhos: `core/batch_pipeline.py _reprocess_one()`, `core/assistant_tools.py reprocess_meeting_full()`, `pages/BatchRunner.py` (seção batch + expander reprocessar); UI expandida para 12 colunas com 🕸️ Grafo + 🔎 Sumário
