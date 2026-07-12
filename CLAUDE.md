# CLAUDE.md — Process2Diagram

> Read this file before making changes to the codebase.
> Detailed references: `claude_guideline/architecture_details.md`, `claude_guideline/pitfalls.md`, `claude_guideline/roadmap.md`
> Critérios de aceite por agente (outcomes): `claude_guideline/acceptance_criteria.md`

## Project Overview

**Process2Diagram** converts meeting transcriptions into professional process diagrams using a multi-LLM pipeline.

- **Input:** raw text transcript (paste, `.txt`, `.docx`, or `.pdf` upload)
- **Outputs:** BPMN 2.0 XML, Mermaid flowchart, meeting minutes (Markdown / Word / PDF), requirements analysis (JSON/Markdown), executive HTML report, interactive requirements mind map
- **Deploy:** Streamlit Cloud — auto-deploy on push to `main` branch (`github.com/pedroregato/process2diagram`)
- **Dev environment:** PyCharm on Windows; Python 3.13
- **Current version:** v5.15

Supported LLM providers: DeepSeek V4 Flash (default), DeepSeek V4 Pro, DeepSeek V4 Flash (Thinking), Claude (Anthropic), OpenAI, Groq, Google Gemini, Grok (xAI).

---

## Running the App

```bash
pip install -r requirements.txt
python -m spacy download pt_core_news_lg
streamlit run app.py
# → http://localhost:8501
```

No build step, no test suite, no Makefile.

---

## Repository Structure

```
process2diagram/
├── app.py                        # Streamlit entry point — st.navigation() with 5 groups
│
├── pages/
│   ├── Home.py                   # Landing page — project selector, KPIs, recent meetings, radar de qualidade, export ZIP
│   ├── Pipeline.py               # Main pipeline — dual-mode (Nova transcrição / Reunião existente)
│   ├── Diagramas.py              # Full-screen diagram viewer (BPMN, Mermaid, Mind Map)
│   ├── BpmnEditor.py             # BPMN editor — bpmn-js Modeler, version history, Supabase save
│   ├── BpmnStudio.py             # BPMN Studio (PC116) — descrição → BPMN+Mermaid (sem reunião) + BPMN → descrição
│   ├── Assistente.py             # RAG assistant — conversational Q&A over transcripts
│   ├── Artefatos.py              # Central de Artefatos — 12 abas: req, mind map, contradições, histórico, reuniões, SBVR, BPMN, DMN, IBIS, rastreabilidade, ruídos, comparar
│   ├── KnowledgeGraph.py         # Knowledge graph — pyvis physics (Obsidian-like), entity/contradiction viz, timeline heatmap, JSON-LD export
│   ├── MeetingROI.py             # ROI-TR dashboard — type-aware quality indicators
│   ├── DocumentManager.py        # Document management — 7 tabs: upload, library, extract artifacts, cross-ref, doc×doc, taxonomy, import spreadsheet; aba Biblioteca tem botão de promoção a Ativo de Negócio (PC167, Classificação Formal pré-sugerida por document_types.category)
│   ├── CostBenefitScenarios.py   # Cenários de Custo-Benefício — compara até 5 combinações agente→modelo, presets, gráficos Plotly, apply ao pipeline
│   ├── AtivosDeNegocio.py        # Ativos de Negócio (PC164-168) — só ativos PROMOVIDOS explicitamente (Artefatos.py + DocumentManager.py + Assistente.py); classificação em 3 dimensões (Interesse/Perspectiva/Classificação Formal AN-01..AN-12) + governança (status/tags/owner/notas); toggle de escopo Contexto x Catálogo do Domínio; 7 tipos governáveis (req/BPMN/SBVR termo/SBVR regra/ata/documento/conteúdo do Assistente) + 4 somente-leitura
│   ├── Settings.py               # Central settings — LLM providers, API keys, tool catalog
│   ├── DatabaseOverview.py       # Database health — record counts, embeddings, integrity fixes
│   ├── CostEstimator.py          # LLM cost estimator
│   ├── LLMBenchmark.py           # LLM Benchmark & Telemetria — on-demand benchmark + passive telemetry analysis
│   ├── Orientacoes_ComoIniciar.py   # Guia de início rápido
│   ├── Orientacoes_CasosDeUso.py    # Casos de Uso — Valor de Negócio: 15 cenários (Cenário → Pergunta → Entrega → Valor) em 5 categorias, fonte única alimenta Streamlit + botão de export HTML autocontido (PC181)
│   ├── Orientacoes_Assistente.py    # Guia de ferramentas do Assistente (151 tools + exemplos)
│   ├── Orientacoes_Glossario.py     # Glossário interativo (components.v1.html — busca + filtros + índice alfabético)
│   ├── Orientacoes_Arquiteturas.py  # Arquiteturas do sistema
│   ├── Orientacoes_CKF.py           # Guia CKF
│   ├── Orientacoes_BpmnStudio.py    # Guia BPMN Studio — passo a passo + exemplo de descrição complexa (multi-pool)
│   ├── Orientacoes_Graficos.py      # Guia dos 13 gráficos do Assistente — o que são, melhor uso, prompts + resumo executivo (PC143)
│   ├── BatchRunner.py            # Batch pipeline (Manutenção)
│   ├── BpmnBackfill.py           # Backfill BPMN XML (Manutenção)
│   ├── TranscriptBackfill.py     # Backfill transcript embeddings (Manutenção)
│   └── MinutesBackfill.py        # Backfill meeting minutes (Manutenção)
│
├── core/
│   ├── knowledge_hub.py          # KnowledgeHub dataclass — central session state
│   ├── pipeline.py               # run_pipeline() — multi-run / LangGraph / standard
│   ├── lg_pipeline.py            # LGBPMNRunner — LangGraph adaptive BPMN retry
│   ├── session_state.py          # init_session_state() — all st.session_state defaults
│   ├── rerun_handlers.py         # handle_rerun() — re-executes a single named agent
│   ├── assistant_tools.py        # get_tool_schemas_openai/anthropic/catalog() + AssistantToolExecutor(*mixins) — thin composition root, see core/tools/
│   ├── tools/                    # AssistantToolExecutor split by domain (PC115) — each file = 1 mixin class + its OpenAI schemas
│   │   ├── _shared.py                        # _compute_initials, _PT_NAME_PREPS
│   │   ├── tools_meetings_requirements.py    # meeting queries + requirement text/status updates
│   │   ├── tools_bpmn_sbvr.py                # BPMN describe/suggest/save/apply + SBVR CRUD
│   │   ├── tools_meeting_ops_calendar.py     # meeting admin ops (rename/reprocess/roi) + calendar read/create
│   │   ├── tools_admin_charts_entities.py    # calendar admin, DB integrity, embeddings, charts, entity resolution
│   │   ├── tools_documents_ibis_diagrams.py  # DocumentManager tools, IBIS, diagram rendering
│   │   ├── tools_knowledge_requirements2.py  # KnowledgeHub entities/contradictions, requirement merge/diff
│   │   └── tools_executive_advanced.py       # PC-era synthesis tools (deck, charter, simulação, conformidade...)
│   ├── chart_config.py           # CHART_PALETTES + DEFAULT_PALETTE (zero-dependency)
│   ├── cost_model.py             # ModelPricing, AgentTokenProfile, ScenarioConfig, ScenarioResult, PRICING_CATALOG, project_cost()
│   ├── schema.py                 # Legacy schemas
│   └── output_schemas.py         # Pydantic v2 output schemas (7 agents, fail-open, PC84)
│
├── agents/
│   ├── base_agent.py             # Abstract base — LLM routing, JSON retry, token tracking
│   ├── orchestrator.py           # Sequences all agents; Minutes+Requirements parallel
│   ├── nlp_chunker.py            # spaCy NER, segmentation, actor detection (no LLM)
│   ├── agent_transcript_quality.py  # Grade A–E transcript quality gate
│   ├── agent_bpmn.py             # BPMN extraction + _enforce_rules() + generators
│   ├── agent_mermaid.py          # MermaidGenerator — pure Python, no LLM
│   ├── agent_minutes.py          # Meeting minutes extraction
│   ├── agent_requirements.py     # Requirements extraction (IEEE 830)
│   ├── agent_sbvr.py             # OMG SBVR vocabulary + rules
│   ├── agent_bmm.py              # OMG BMM vision/mission/goals/strategies/policies
│   ├── agent_synthesizer.py      # Executive HTML report synthesis
│   ├── agent_validator.py        # Pure Python BPMN quality scorer (no LLM)
│   ├── agent_document_analyzer.py  # On-demand: cross-references a document vs meeting artifacts
│   ├── agent_document_extractor.py # On-demand: extracts req/SBVR/BMM/DMN artifacts from a document
│   ├── agent_bpmn_studio.py      # On-demand (PC116): generate_bpmn_from_description() — hub sintético + AgentBPMN, sem reunião
│   └── agent_bpmn_analyst.py     # On-demand (PC135): answer(process_name, bpmn_xml, question) — free-form Q&A over an existing BPMN diagram
│
├── modules/
│   ├── config.py                 # LLM provider registry — add new providers here
│   ├── session_security.py       # API keys in st.session_state only
│   ├── bpmn_generator.py         # BPMN 2.0 XML generator (absolute coordinates)
│   ├── bpmn_describer.py         # BPMN XML → descrição textual (PC116) — describe_bpmn_from_xml(), sem I/O
│   ├── bpmn_viewer.py            # bpmn-js 17 viewer (server-side assets, no CDN)
│   ├── bpmn_editor.py            # bpmn-js Modeler HTML template
│   ├── bpmn_auto_repair.py       # repair_bpmn() — 4-pass deterministic repair
│   ├── bpmn_structural_validator.py  # 6 structural checks, severity levels
│   ├── bpmn_diagnostics.py       # BPMN diagnostic panel for Streamlit
│   ├── mermaid_renderer.py       # render_mermaid_block() — shared SVG renderer
│   ├── requirements_mindmap.py   # Mermaid mindmap string + tree builder
│   ├── mindmap_interactive.py    # Interactive SVG mindmap (collapse/expand, pan/zoom)
│   ├── executive_html.py         # Executive HTML report generator
│   ├── minutes_exporter.py       # MinutesModel → Word (.docx) and PDF
│   ├── transcript_preprocessor.py  # ASR artefact cleaner
│   ├── auth.py                   # SHA-256 session login, is_authenticated(), is_admin()
│   ├── supabase_client.py        # get_supabase_client() singleton
│   ├── embeddings.py             # chunk_text(), embed_text(), embed_batch() — 1536 dims
│   ├── meeting_roi_calculator.py # ROI-TR v2 — type weights, classify_meeting_type()
│   ├── cross_meeting_analyzer.py # find_recurring_topics() — pgvector + keyword
│   ├── calendar_client.py        # Google Calendar API — 8 public functions
│   ├── cost_estimator.py         # PROVIDER_PRICING table + estimate_cost()
│   ├── ingest.py                 # .txt/.docx/.pdf file loader
│   ├── text_utils.py             # rule_keyword_pt() — Portuguese text utils
│   ├── reqtracker_exporter.py    # RequirementsModel → HTML/PDF (usado por Artefatos.py)
│   ├── glossary_data.py          # 80 verbetes do glossário técnico + search_glossary() + TAG_META
│   └── document_store.py         # Document CRUD + embedding + semantic/keyword search (Supabase)
│
├── ui/
│   ├── sidebar.py                # render_sidebar() — provider, agents, re-run buttons
│   ├── input_area.py             # render_input_area() — text area, upload, pre-process
│   ├── auth_gate.py              # apply_auth_gate() — login wall
│   ├── project_selector.py       # require_active_project() — global project context
│   ├── components/
│   │   ├── copy_button.py        # clipboard copy (navigator.clipboard + execCommand)
│   │   ├── download_button.py    # styled download wrapper
│   │   └── page_header.py        # render_page_header(icon, title, caption)
│   └── tabs/                 # bpmn, quality, minutes, requirements, sbvr, bmm, synthesizer, export, dev_tools
│
├── services/
│   ├── export_service.py         # make_filename(base, ext, prefix, suffix) → str
│   ├── file_ingest.py            # load_transcript() wrapper
│   ├── preprocessor_service.py  # preprocess_transcript() wrapper
│   ├── semantic_cache.py        # SemanticCache — SHA256 LLM response cache (Supabase llm_cache)
│   ├── context_analyzer.py     # estimate_tokens(), should_use_long_context(), LONG_CONTEXT_AGENTS
│   └── llm_telemetry.py        # LLMTelemetry (async Supabase write), run_benchmark_call(), BENCHMARK_TASKS, _telemetry singleton
│
├── adapters/
│   └── langchain_tools.py        # Exposes assistant tools as LangChain-compatible tools
│
├── mcp/
│   ├── google_calendar_server.py # MCP server — Google Calendar tools
│   ├── integration_guide.html
│   └── mcp_testing_guide.html
│
├── skills/
│   ├── skill_bpmn.md             # AgentBPMN system prompt (lowercase)
│   ├── skill_minutes.md          # AgentMinutes system prompt (lowercase)
│   ├── skill_transcript_quality.md
│   ├── skill_sbvr.md
│   ├── skill_bmm.md
│   ├── skill_document_analyzer.md   # DocumentAnalyzerAgent — cross-reference analysis
│   ├── skill_document_extractor.md  # DocumentExtractorAgent — artifact extraction from docs
│   ├── skill_bpmn_analyst.md     # AgentBPMNAnalyst — free-form Q&A over an existing BPMN diagram
│   ├── SKILL_REQUIREMENTS.md     # uppercase — git-tracked name
│   └── SKILL_SYNTHESIZER.md      # uppercase — git-tracked name
│
├── tests/
│   ├── conftest.py
│   ├── test_bpmn_auto_repair.py  # 36 tests
│   ├── test_bpmn_structural_validator.py  # 22 tests
│   ├── test_agent_validator.py   # 22 tests
│   └── test_mermaid_generator.py # 26 tests
│
├── claude_guideline/
│   ├── roadmap.md                # PC1–PC11 full history
│   ├── architecture_details.md   # BPMN generator internals, RAG details, ROI-TR formulas
│   └── pitfalls.md               # Known pitfalls with full code examples
│
├── notes/                        # Scratch notes, debates, planos de correção — não faz parte do app
│   ├── ajustes/ · bpmn-ideias/ · commercial/ · corrigir/ · discussions/
│   └── duvidas/ · erros/ · html-referencia/ · metodologia/ · reference-library/
│
└── test-scenarios/               # Execuções de teste ponta-a-ponta salvas para regressão manual
    ├── cenario-teste-001/
    └── cenario-teste-002/
```

> **Linux / Streamlit Cloud — filesystem is case-sensitive.**
> Skill file names in `skill_path` must match the git-tracked filename exactly.
> **Always verify with `git ls-files skills/` before adding a new skill reference.**

---

## Architecture

### Data Flow

```
Transcript (user input)
        │
        ▼
AgentTranscriptQuality   ← LLM; grades transcript A–E; non-fatal if fails
        │
        ▼
Transcript Preprocessor  ← no LLM; removes ASR fillers/artefacts/repetitions
        │
        ▼
  NLPChunker             ← no LLM; spaCy NER, segmentation, actor detection
        │
        ▼
   AgentBPMN             ← LLM; extracts steps/edges/lanes → BPMN XML, Mermaid
        │  _enforce_rules() + repair_bpmn() post-process
        │  (if n_bpmn_runs > 1) → AgentValidator tournament
        │  (if use_langgraph)   → LGBPMNRunner adaptive retry
        ▼
  AgentMinutes  ┐  parallel via ThreadPoolExecutor (when both enabled)
AgentRequirements┘
        ▼
   AgentSBVR → AgentBMM → AgentSynthesizer   (all optional)
        ▼
   KnowledgeHub  ← fully populated; stored in st.session_state["hub"]
```

### Navigation Groups (`app.py`)

| Group | Pages | Visibility |
|---|---|---|
| **Início** | Home.py (default) | Todos |
| **Pipeline** | Pipeline.py, Diagramas.py, BpmnEditor.py, BpmnStudio.py | Todos |
| **Análise** | Assistente.py, Artefatos.py, ValidationHub.py, MeetingROI.py, DocumentManager.py, CostBenefitScenarios.py, AtivosDeNegocio.py | Todos |
| **Sistema** | Settings.py, CostEstimator.py, LLMBenchmark.py [+ MasterAdmin.py, DatabaseOverview.py] | Todos [admin extra] |
| **Ajuda** | ComoIniciar, CasosDeUso (valor de negócio), Assistente (tool guide), Glossário, Arquiteturas, CKF, BpmnStudio (guia), Gráficos (guia) | Todos |
| **Manutenção** | BatchRunner.py, BpmnBackfill.py, MinutesBackfill.py, TranscriptBackfill.py | Admin only |

`app.py` renders no content — only calls `st.navigation(pages).run()`. Groups rebuilt every rerun (menu updates immediately after login).

**Important:** `st.page_link()` must reference registered page files (e.g. `"pages/Pipeline.py"`), never `"app.py"` — raises `StreamlitPageNotFoundError`.

### KnowledgeHub — Central State

```python
@dataclass
class KnowledgeHub:
    version: int                      # bumped on every .bump() call
    transcript_raw: str
    transcript_clean: str
    transcript_quality: TranscriptQualityModel
    preprocessing: PreprocessingModel
    nlp: NLPEnvelope
    bpmn: BPMNModel
    minutes: MinutesModel
    requirements: RequirementsModel
    synthesizer: SynthesizerModel
    validation: ValidationReport
    meta: SessionMetadata
```

**Schema evolution:** always add new fields via `KnowledgeHub.migrate(hub)` — never scattered `hasattr` checks.
**Golden rule:** never instantiate agents directly from `app.py` — always go through `Orchestrator` or `handle_rerun`.

### Agent Pattern

```python
class MyAgent(BaseAgent):
    name = "my_agent"
    skill_path = "skills/skill_my.md"   # must match git ls-files exactly

    def build_prompt(self, hub, output_language="Auto-detect") -> tuple[str, str]:
        ...

    def run(self, hub, output_language="Auto-detect") -> KnowledgeHub:
        system, user = self.build_prompt(hub, output_language)
        data = self._call_with_retry(system, user, hub)
        hub.mark_agent_run(self.name)
        hub.bump()
        return hub
```

`BaseAgent` provides: `_call_llm()`, `_parse_json()`, `_load_skill()` (absolute path, CWD-independent), 3 JSON retries, token tracking. **Output schemas (PC84):** `output_schema = XxxOutputSchema` class attr → `_call_with_retry()` calls `schema.model_validate(data)` after parse, emits `warnings.warn()` on failure — pipeline never blocked. **Pre-conditions (PC83):** `required_hub_fields` list (dot-paths) validated by `_check_preconditions(hub)` before `run()`. **Skill version (PC83):** `_load_skill()` parses `version:` from YAML frontmatter; persisted in `llm_telemetry.skill_version`. `_call_llm()` flow: PII sanitize Tier-1 (CPF/CNPJ/email/tel/valores → `@LABEL_NNN`) + Tier-2 nomes (`hub.meta.name_map` → `[PESSOA:XX]`; `_NOME_INSTRUCTION` injetada no system prompt quando não-vazio) → long context detection (LONG_CONTEXT_AGENTS={bpmn,sbvr,bmm}, >50k tokens → max_tokens=8192, timeout=180s) → cache hash → `SemanticCache` check (PII-safe) → API call → telemetry (async) → cache store → desanitize (restaura Tier-1 + Tier-2 antes de retornar ao caller). `hub.meta.cache_hits/tokens_saved/long_context_calls/name_map` tracked. Provider routing: `"openai_compatible"` → OpenAI SDK + custom `base_url`; `"anthropic"` → native SDK.

### Orchestrator + AgentValidator

Minutes + Requirements run via `ThreadPoolExecutor(max_workers=2)` — each worker gets isolated `copy.copy(hub)`. Token deltas merged after join. Falls back to sequential on any exception.

`agent_validator.py` — no LLM. Scores granularity / task_type / gateways (each 0–10, weighted). Used when `n_bpmn_runs > 1`. Best candidate → `hub.bpmn`; all scores → `hub.validation`.

> Full parallel execution and scoring details: `claude_guideline/architecture_details.md`

---

## LLM Providers

Configured in `modules/config.py → AVAILABLE_PROVIDERS`:

| Provider | Default model | client_type | Notes |
|---|---|---|---|
| **DeepSeek** (default) | `deepseek-v4-flash` | `openai_compatible` | Cheapest; 1M context; `deepseek-chat` deprecated 24/07/2026 |
| DeepSeek V4 Pro | `deepseek-v4-pro` | `openai_compatible` | Premium; 1M context; $0.435/1M input |
| DeepSeek V4 Flash (Thinking) | `deepseek-v4-flash` | `openai_compatible` | thinking mode via `reasoning_effort=high`; no `json_mode`; no `temperature` |
| Claude (Anthropic) | `claude-sonnet-4-20250514` | `anthropic` | No `json_mode` — enforce via prompt |
| OpenAI | `gpt-4o-mini` | `openai_compatible` | |
| Azure OpenAI | `gpt-4o-mini` (= deployment name) | `azure_openai` | Requer `extra_fields` (endpoint + deployment name, ver Settings/sidebar); rota por deployment, não por model id |
| Groq (Llama) | `llama-3.3-70b-versatile` | `openai_compatible` | Fastest |
| Google Gemini | `gemini-2.0-flash` | `openai_compatible` | Free tier |
| Grok (xAI) | `grok-4-1-fast-reasoning` | `openai_compatible` | 2M context |

To add a provider: edit `AVAILABLE_PROVIDERS`; new `client_type` → add routing in `_call_llm()`. Thinking mode: `reasoning_effort: "high"` → `_call_openai` passes `extra_body={"thinking":{"type":"enabled"}}`, drops `temperature`. Shared API key: `api_key_alias: "<provider_name>"` — `session_security` resolves automatically. **`extra_fields`** (PC184): a provider can declare non-secret config fields beyond the API key (e.g. Azure OpenAI's per-resource endpoint URL) — `[{"key","label","placeholder","help"}]`, rendered by `session_security.render_extra_fields()` (called from `ui/sidebar.py` and `pages/Settings.py`), read back via `session_security.get_extra_field(provider, key)`. `BaseAgent._call_azure_openai()` and `_run_openai_chat()` (shared with `_call_openai`) implement the Azure client; `run_benchmark_call()` in `services/llm_telemetry.py` has its own parallel Azure branch for the On-Demand Benchmark tab.

---

## LLM Telemetry (`services/llm_telemetry.py`)

Telemetria passiva em todo `_call_llm()` real (não cache); daemon thread assíncrono; tabela `llm_telemetry` (90d cleanup). `TelemetryRecord`: agent_name, provider, model, latency_ms, tokens_in/out, from_cache, long_context, is_error, error_message, benchmark_run, skill_version, is_validation_event, schema_valid. `run_benchmark_call()` para benchmarks on-demand. `BENCHMARK_TASKS` (5 agentes) + `TRANSCRIPTS` (curta/média). `pages/LLMBenchmark.py`: 🧪 Benchmark On-Demand + 📊 Telemetria Real (box plot latência, throughput, histórico, heatmap, versões, 🚨 alertas, ✅ qualidade). Migration: `setup/supabase_migration_llm_telemetry.sql` ✅ + `setup/supabase_migration_llm_telemetry_pc183.sql` ✅.

**PC183 — erro por provider + qualidade de schema:** `_call_llm()` agora envolve a chamada real ao provider em `try/except`: falha grava `TelemetryRecord(is_error=True, error_message=...)` e relança a exceção original (retry/escalação de `_call_with_retry()` intocados) — antes disso, `is_error` era hard-coded `False` e nenhuma falha real (ex.: DeepSeek "conteúdo vazio") deixava rastro. `_call_with_retry()` persiste o resultado de `output_schema.model_validate()` (PC84) via `_telemetry.record_validation()` — antes só existia como `warnings.warn()` efêmero. `LLMTelemetry`: `query_error_rate_by_provider(hours)`, `detect_error_anomalies(hours, min_calls, error_rate_threshold)`, `query_recent_errors(hours, limit)`, `query_schema_validation_rate(days, agent_name)`, `record_validation(agent_name, skill_version, valid)`.

---

## BPMN Generator (`modules/bpmn_generator.py`)

**Layout:** absolute coordinates — no direction parameter. Constants: `TASK_W=120`, `TASK_H=60`, `GW_W=50`, `H_GAP=70`, `LANE_HEADER_W=100`. Elements without a lane assignment crash the viewer.

**Lane-crossing:** flows spanning ≥ 2 lane boundaries → replaced with throw/catch Link Events. Adjacent-lane flows left as direct arrows.

**Parallel branch alignment:** `_align_parallel_branches` snaps shorter branch terminal to `join_col − 1` — eliminates long diagonal arrows on unequal parallel branches.

> Full column algorithm, waypoint routing, lane-crossing details: `claude_guideline/architecture_details.md`

### Post-extraction rule enforcement (`_enforce_rules`)

Applied in `agent_bpmn.py` after LLM extraction, before generators. Receives `hub.nlp.actors`.

- **Rule 0** — removes LLM-declared `startEvent`/`endEvent` steps (generator adds these)
- **Rule 1** — `serviceTask` with unnamed system actor → `lane = None` (OMG §7.4)
- **Rule 1b** — generic lane names (`usuário`, `validador`, `sistema`…) → infers real org name: (1) step actor fields, (2) NLP actors, (3) regex over step descriptions
- **Rule 2** — correction loop → any gateway type → redirected to upstream work step

### Rules the LLM must follow (`skill_bpmn.md`)

- Must not declare Link Intermediate Events (generator handles them)
- Lane names must be organizational units, never generic roles
- System lanes must not receive Start/End Events
- End Event inherits the lane of its direct predecessor

---

## Mermaid Generator (`agents/agent_mermaid.py`)

Pure Python, no LLM. `sanitize_text()` → `format_node()` (`{}` decisions, `[]` tasks) → `format_edge()` (`-->|label|` syntax) → `generate()` (`flowchart LR`).
Entry point: `generate_mermaid(model: BPMNModel) -> str`.

---

## BPMN Viewer (`modules/bpmn_viewer.py`)

bpmn-js 17 injected inline (server-side asset fetch + `lru_cache`, no CDN). `canvas.zoom('fit-viewport')` deferred via `setTimeout(fn, 150)` — prevents SVGMatrix non-finite error on zero-dimension container. CDN fallback when server-side fetch fails. Mouse wheel zoom (toward cursor position via `canvas.zoom(scale, {x,y})`) and click-drag pan (via `canvas.scroll()`) bound directly on `#bpmn-container`, matching `mermaid_renderer.py`'s interaction model. "↗ Janela" button opens a pristine pre-render snapshot of the document (captured before `importXML()` runs) — using the post-render `outerHTML` here left stale rendered SVG/marker ids in the container the popup's own `importXML()` call then collided with.

> Full implementation notes + JS pattern: `claude_guideline/pitfalls.md §bpmn-js fit-viewport`

---

## Mermaid Renderer (`modules/mermaid_renderer.py`)

`render_mermaid_block(mermaid_text, *, show_code, key_suffix, height)` — fetches TD/LR SVGs server-side from `mermaid.ink`, injects inline, client-side JS toggles direction. Pan/zoom/fit. No CDN inside iframe (Streamlit Cloud sandbox blocks external scripts in `components.html`).

---

## Requirements Mind Map

- `modules/requirements_mindmap.py` → Mermaid mindmap string + hierarchical tree dict
- `modules/mindmap_interactive.py` → interactive SVG mindmap (collapse/expand, pan/zoom)

Hierarchy: `root → Type group → REQ-ID — Title (priority dot)`. Also rendered in `pages/Diagramas.py` under "🗺️ Mind Map" tab.

---

## RAG Assistant (`pages/Assistente.py`)

| Mode | Description |
|---|---|
| **💬 Assistente** | Interactive Q&A, history-aware, up to 8 tool rounds |
| **🔬 Análise Autônoma** | Autonomous agent, up to 15 rounds, structured report |

Within Assistente mode, sidebar toggle `asst_use_tools`:
- **Modo A: Tool-use** (default) — LLM calls tools against Supabase directly
- **Modo B: RAG Clássico** — keyword + semantic vector search fallback

### Tool list (`core/assistant_tools.py` + `core/tools/`)

**PC115 split:** `AssistantToolExecutor` is composed via multiple inheritance from 7 domain mixins in `core/tools/` (see Repository Structure above); `core/assistant_tools.py` itself only holds `__init__`, `execute()` (name→method dispatch dict), and the schema/catalog getters that concatenate each mixin file's `*_SCHEMAS` constant. **To add a new tool:** implement the method on the mixin matching its domain (or `tools_executive_advanced.py` as a default), add its OpenAI schema dict to that same file's `*_SCHEMAS` list, then register the dispatch entry in `AssistantToolExecutor.execute()`. Never add methods directly to `core/assistant_tools.py`.

**Non-admin:** `get_meeting_list`, `get_meeting_participants`, `get_meeting_decisions`, `get_meeting_action_items`, `get_meeting_processing_history`, `get_meeting_summary`, `search_transcript`, `get_requirements`, `get_requirement_history`, `update_requirement_text`, `sample_requirements`, `analyze_requirement_quality`, `map_transcript_to_requirements`, `cluster_similar_requirements`, `list_bpmn_processes`, `list_bpmn_versions`, `review_bpmn_diagram`, `describe_bpmn_process`, `ask_bpmn_diagram`, `generate_bpmn_diagram`, `suggest_bpmn_corrections`, `get_sbvr_terms`, `get_sbvr_rules`, `update_sbvr_rule`, `update_sbvr_term_by_id`, `get_bmm`, `get_ckf`, `calendar_list_events`, `calendar_get_event`, `calendar_suggest_time`, `get_system_capabilities`, `lookup_entity`, `get_cache_stats`, `list_meeting_documents`, `get_document_content`, `search_documents`, `get_document_types`, `search_glossary`, `read_skill_reference`, `search_ibis_debates`, `get_ibis_timeline`, `generate_ibis_map`, `generate_requirements_flow_chart`, `generate_requirements_heatmap`, `generate_requirements_bubble_chart`, `generate_requirements_waterfall`, `generate_meeting_radar_chart`, `generate_gantt_chart`, `list_kh_entities`, `list_kh_contradictions`, `resolve_contradiction`, `delete_contradiction`, `list_kh_facts`, `cluster_topic_decisions`, `generate_next_agenda`, `sugestoes_plantonista`, `diagnostico_projeto`, `reordenar_requisitos`, `vincular_regra_debate`, `mapa_rastreabilidade`, `simular_cenario`, `verificar_conformidade`, `sugerir_processos`, `gerar_deck_executivo`, `gerar_project_charter`, `export_project_charter_docx`, `compare_meetings`, `verificar_rastreabilidade_obrigatoria`, `gerar_release_notes`, `analisar_tendencias`, `estimar_risco_requisito`, `promover_ativo_negocio`, `gerar_variacao_apresentacao`, `exportar_pacote_completo`, `sugerir_encaminhamentos_pendentes`, `pesquisar_multi_contexto`.

**Admin only (`is_admin()`):** `get_database_integrity`, `fix_missing_llm_provider`, `generate_meeting_embeddings`, `reprocess_meeting_full`, `calendar_create_event`, `calendar_schedule_action_items`, `calendar_share_with_user`, `calendar_revoke_access`, `calendar_diagnose`, `delete_entity`, `resolve_entity_ambiguity`, `clear_llm_cache`, `delete_bpmn_version`, `save_bpmn_revision`, `save_generated_bpmn`, `apply_bpmn_corrections`, `inserir_secao_ata`, `mesclar_reunioes`, `sincronizar_calendario`, write/generate tools.

Detalhes de parâmetros e comportamento por grupo de ferramentas: `claude_guideline/architecture_details.md §Tool list`.

### Exportação da conversa

Chat toolbar: **⬇️ Markdown** (texto simples) e **⬇️ HTML** (auto-contido dark-navy, marked.js + Plotly.js CDN, gráficos interativos embutidos). Helpers `_html_escape()` + `_html_escape_attr()` para sanitização.

### Embedding pipeline

`chunk_text(transcript, 500, 80)` → `transcript_chunks vector(512)`. Default: OpenAI `text-embedding-3-small` (`dimensions=512`, Matryoshka native); alternativas: Gemini `gemini-embedding-001` (`output_dimensionality=512`), Grok `grok-embedding-small` (slice manual). Rate limit: 1.2s + 5 retries. Search: `match_transcript_chunks()` pgvector cosine. Migration: `setup/supabase_migration_embedding_512.sql`.

> Full details: `claude_guideline/architecture_details.md`

---

## DMN Viewer (`modules/dmn_viewer.py`)

Dark-theme renderer for OMG DMN 1.4. Key functions:
- `render_dmn_page(decisions: list[dict], show_origin=True) → str` — dark HTML page for `components.html()`; hit-policy badge, row pinning JS. Used in Artefatos DMN tab.
- `render_drd(decisions: list[dict]) → str` — SVG DRD with topological depth layout; heuristic dependency detection (output label ⊆ input label); colored boxes per hit policy.
- `estimate_height(decisions) → int` / `estimate_drd_height(decisions) → int` — auto height calculation.
- `_model_to_dicts(model: DMNModel)` — bridge dataclass→dict. `render_dmn_model(model)` delegates to dark renderer. `dmn_to_xml(model)` — unchanged XML export.

Artefatos DMN tab: sub-tabs **📋 Tabelas** + **🔗 DRD** + download buttons (JSON + XML).

---

## Agent Skills (v5.11)

**Frontmatter stripping** — `BaseAgent._load_skill()` strips YAML `---...---` from 15/25 skill files (~80–200 tokens saved per agent call).

**`AGENT_REGISTRY`** (`core/agent_registry.py`) — governance dict (14 agents): `authority_level` (`read|draft|act`), `skill_path`, `pipeline_step`, `default_enabled`, `tags`. Sets: `READ_AGENTS`, `DRAFT_AGENTS`, `ACTION_AGENTS`.

**`tests/test_skill_files.py`** — 24 tests: `skill_path` existence (Linux case-sensitivity), registry integrity, authority disjointness, frontmatter strip.

---

## ValidationHub, KnowledgeGraph, Home (v4.30–v4.31)

**ValidationHub** — first tab **"📊 Saúde do Pipeline"**: `_load_health(pid)` `ttl=120` via `list_meetings_quality`; 6 KPIs; coverage dataframe ✅/❌; Plotly grouped bar chart; refresh button.

**KnowledgeGraph** — added **🕐 Timeline** tab: Plotly heatmap entity×meeting (top 40, `#2563eb` = present); `meeting_map` added to `_load_graph_data()`. Exportar tab: JSON-LD download (schema.org, `urn:p2d:entity:{id}` URNs, `@type` per entity type).

**Home** (v4.31) — shown when active project set:
- **Radar de Qualidade**: Plotly Scatterpolar 5 dims (BPMN/Ata/DMN/IBIS/Relatório) em % cobertura; usa `list_meetings_quality`.
- **Export ZIP**: `io.BytesIO` + `zipfile.ZipFile` — BPMNs (.xml), atas (.md via `list_meetings`), requisitos (.json via `list_requirements_light`), README. Importante: usar `list_meetings` (não `list_meetings_quality`) para obter `minutes_md`.

---

## ROI-TR Dashboard (`pages/MeetingROI.py`)

Type-aware quality system — 11 meeting types, each with a weight matrix across 5 artefact dimensions (req/dec/act/sbvr/bpmn). `classify_meeting_type()` uses LLM (1 call/meeting) or heuristic fallback. Results persisted to `meetings.meeting_type`. No new Supabase tables required.

> Full formulas, TYPE_WEIGHTS matrix: `claude_guideline/architecture_details.md`

---

## Document Management (`pages/DocumentManager.py`)

7 tabs: **📤 Enviar** (upload .txt/.pdf/.docx or paste, category→type taxonomy, auto-embed) · **📚 Biblioteca** (keyword + semantic search, preview, delete, re-index) · **⚗️ Extrair Artefatos** (run `DocumentExtractorAgent` → preview 7 artifact types → save via `save_artifacts_from_document()`) · **🔍 Análise Cruzada** (doc × meeting hub → `DocumentAnalyzerAgent` → alignment score 0–100 + report) · **🔗 Doc × Doc** (cross-reference two documents) · **🏷️ Taxonomia** (53 types / 9 categories) · **📊 Importar Planilha** (PC163 — .xlsx de requisitos legados → mapeamento interativo de coluna → checagem leve de duplicata (`difflib`, sem LLM) → `import_requirements_from_rows()`, mesma rastreabilidade `origin="documento"`/`doc_ref` da extração via LLM).

**`modules/document_store.py`** — CRUD + embedding pipeline + search. Key functions: `upload_document`, `embed_document` (chunks 500/80 via `chunk_text`+`embed_batch`), `search_documents_semantic` (pgvector RPC), `search_documents_keyword`, `update_document_meta`.

**Artifact origin traceability (PC23):** all analytical artifacts have `origin: str = "transcricao"|"documento"` + `doc_ref: Optional[str]` (UUID of `meeting_documents`). Pipeline artifacts always have `origin="transcricao"`. Document-extracted artifacts have `origin="documento"` + `doc_ref=<doc_id>`. `save_artifacts_from_document(project_id, doc_id, extracted)` persists req/SBVR/BMM/DMN; `meeting_id` is nullable for document-sourced artifacts.

**SQL migrations:** `setup/supabase_migration_documents.sql` + `setup/supabase_migration_artifact_origin.sql` — ✅ EXECUTADOS.

---

## Core Modules (`core/`)

- `session_state.init_session_state()` — idempotent, call immediately after `st.set_page_config()`. Defaults: provider=DeepSeek, embed_provider=OpenAI, run_quality/bpmn/minutes/requirements=True, run_sbvr/bmm/synthesizer/dmn/argumentation/ckf_updater/query_summarizer=True, n_bpmn_runs=3, use_langgraph=True, enable_long_context=True.
- `pipeline.run_pipeline(hub, config, callback)` — 3 paths: multi-run tournament / LangGraph / standard. Raises on error (caller catches).
- `rerun_handlers.handle_rerun(agent_name, ...)` — re-runs one agent: `"quality"`, `"bpmn"`, `"minutes"`, `"requirements"`, `"sbvr"`, `"bmm"`, `"synthesizer"`. BPMN re-run invalidates `hub.synthesizer`.
- `cost_model.py` — modelo de dados para Cenários de Custo-Benefício (sem Streamlit, sem rede). Exporta: `ModelPricing`, `AgentTokenProfile`, `ScenarioConfig`, `ScenarioResult`, `PRICING_CATALOG` (17 modelos / 6 provedores), `DEFAULT_TOKEN_PROFILES` (9 agentes com perfis heurísticos), `project_cost(scenario, word_count, catalog) → ScenarioResult`. Catálogo editável via `st.session_state["cost_catalog_overrides"]`; cenário ativo em `st.session_state["scenario_assignments"]` (dict agent_name→model_id) — lido por `BaseAgent._call_llm()` para sobrescrever `model` por agente (fail-open se ausente).
- `project_store` — Supabase CRUD; fail-open (returns `[]`/`None` when unconfigured). Key functions: `load_meeting_as_hub(meeting_id, project_id)` → reconstructs KnowledgeHub from DB (transcript, BPMN, minutes, requirements, SBVR, BMM, DMN, IBIS); `list_dmn_by_project(project_id)` → flat list of DMN decisions; `list_argumentation_by_project(project_id)` → flat list of IBIS questions; `save_artifacts_from_document(project_id, doc_id, extracted)` → persists all artifact types extracted from a document; `list_meetings_quality(project_id)` → per-meeting artifact coverage flags (has_bpmn/minutes/dmn/ibis/synthesizer) — usado em ValidationHub health tab e Home radar; `log_meeting_processing(meeting_id, project_id, processing_type, ...)` / `get_meeting_processing_history(meeting_id)` / `count_meeting_processings(meeting_id)` (PC152) → registram e consultam a tabela `meeting_processing_log` (data efetiva + contagem de processamentos/reprocessamentos por reunião — `new`/`reprocess_full`/`reprocess_agent`), hookado em `pages/Pipeline.py` (nova transcrição + rerun de agente único) e `core/batch_pipeline.py` (`_run_one`/`_reprocess_one`); `import_requirements_from_rows(project_id, rows, doc_id)` / `find_similar_existing_requirements(project_id, title, threshold=0.75)` (PC163) → Importador de Planilha em `DocumentManager.py`, mesmo padrão de rastreabilidade `origin="documento"`/`doc_ref` de `save_artifacts_from_document`; `list_all_business_assets(project_id)` / `get_asset_metadata_map(project_id)` / `upsert_asset_metadata(project_id, artifact_type, artifact_id, status=, tags=, owner=, notes=)` / `list_bmm_by_project(project_id)` / `list_reports_by_project(project_id)` (PC164) → agregação de todos os tipos de artefato + governança polimórfica (tabela `asset_metadata`) para `pages/AtivosDeNegocio.py`; `ASSET_TYPES_WITH_METADATA` = os 5 tipos com linha própria no banco (`requirement`/`bpmn_process`/`sbvr_term`/`sbvr_rule`/`meeting_minutes`) — BMM/DMN/IBIS/Relatórios ficam somente-leitura (só existem como JSON em `meetings.*_json`, sem `artifact_id` de linha própria); `list_all_business_assets_for_domain(tenant_id)` (PC165) → Catálogo do Domínio, reaproveita `list_contexts(tenant_id)` + `list_all_business_assets(project_id)` por contexto do tenant, mesclando os 9 tipos com `context_id`/`context_name` em cada item — usado pelo toggle "🌐 Catálogo do Domínio" de `pages/AtivosDeNegocio.py`; `upsert_asset_metadata` sempre grava no `context_id` do próprio item, nunca no contexto ativo da sessão. **PC166 — Promoção Explícita** (`melhorias/promocao-ativos-negocio.md`): `list_all_business_assets()` reescrita — uma linha em `asset_metadata` passa a SER a definição de "é um ativo" (antes: toda linha das tabelas de origem era auto-listada, com ou sem metadata). `promote_to_business_asset(project_id, artifact_type, artifact_id, business_interest=, business_perspective=, promotion_justification=, formal_classification=None, ...)` exige as 3 classificações (Interesse Estratégico/Tático/Operacional; Perspectiva multi-valor — área/departamento; Justificativa texto livre) + Classificação Formal opcional (taxonomia `AN-01`..`AN-12`, ISO 55000/APQC PCF/BIZBOK/TOGAF); `upsert_asset_metadata()` recusa criar linha nova sem essas 3 classificações (só editar uma já promovida continua livre). `demote_business_asset()` move `status` para `arquivado` (nunca apaga, mantém histórico). UI: `ui/components/promote_asset.py` (botão de promoção + campos de classificação reutilizáveis), plugado em `pages/Artefatos.py` (Requisitos/BPMN/SBVR/Reuniões, com promoção em lote na aba Requisitos). **PC167 — Fase B (Documentos):** `document` entra em `ASSET_TYPES_WITH_METADATA`; `suggest_formal_classification_for_document(doc_type)` — único tipo com sugestão automática de Classificação Formal, via `DOCUMENT_CATEGORY_TO_FORMAL_CLASSIFICATION` (categoria de `document_types` → classe AN); botão de promoção plugado em `pages/DocumentManager.py` (aba Biblioteca). **PC168 — Fase C (conteúdo do Assistente):** `assistant_artifact` entra em `ASSET_TYPES_WITH_METADATA` (7 tipos governáveis agora); nova tabela `assistant_artifacts` (persiste snapshots — hoje nada do que o Assistente gera sob demanda sobrevive ao fechar a conversa); `promote_assistant_output_to_asset()` grava o snapshot + a linha de `asset_metadata` numa única chamada (único `artifact_type` cuja promoção CRIA a própria linha de origem); `list_assistant_artifacts_by_project()`. Tool de chat `promover_ativo_negocio` (`core/tools/tools_executive_advanced.py`) permite promoção por linguagem natural, sem gate de admin. `pages/Assistente.py::assistant_history` grava `tools_used` por mensagem — só respostas com tool de síntese (`generate_*`/`gerar_*`/`simular_cenario`/etc., não simples consulta) ganham o botão de promoção no chat. Full function list in `claude_guideline/architecture_details.md`.

---

## Security Model

API keys: `st.session_state` only — never logged, written to disk, or persisted.

**Auth:** `apply_auth_gate()` + SHA-256 hashed credentials in `modules/auth.py → USUARIOS`. Roles: `master > admin > user`. `is_admin()` returns True for both `admin` and `master`. `_role` stored in session_state on login.

**Supabase:** `st.secrets["supabase"]["url"]` + `["key"]`. Fail-open when absent.

**Database (DDL / migrations):** `st.secrets["database"]["connection_string"]` — direct PostgreSQL via `psycopg2`. Password is URL-encoded (special chars: `?`→`%3F`, `#`→`%23`, `/`→`%2F`). Use this for running migrations programmatically (`conn.autocommit = True`). Only in local `secrets.toml` — never deployed to Streamlit Cloud.

**Google Calendar secrets:** `st.secrets["google_calendar"]["calendar_id"]` + `["credentials_json"]`. Always use `'''` (triple-single-quotes) for `credentials_json` in TOML — `"""` corrupts the private key. Resolution order per call: Supabase `project_calendar_config` → secrets → local file → `"primary"`.

**PII Sanitization (`modules/pii_sanitizer.py`) — dois tiers:**
- **Tier 1 — Estruturado** (per-call, stateless): CPF, CNPJ, email, telefone, valores monetários → tokens `@LABEL_NNN`.
- **Tier 2 — Nomes** (session-wide, `hub.meta.name_map`): `detect_names(transcript)` chamado uma vez em `Pipeline.py` antes de `run_pipeline()`; todos os agentes usam o mapa via `_call_llm()`; nomes substituídos por `[PESSOA:XX]` no wire; desanitizados antes de salvar no Supabase (nomes reais no banco — RAG preservado). Token `[PESSOA:XX]` escolhido por robustez LLM (>95% preservação vs ~70% para `{}`). Mapa em memória apenas — nunca persiste (a chave de reversão é dado pessoal).
- **Camada LGPD** (`modules/compliance/`): detecção de PII pós-pipeline, painel de consentimento, trilha de auditoria. Tabelas: `compliance_consent`, `compliance_audit`.

**MS365 integration:** PENDING — blocked by Azure AD admin consent. Plan in `CLAUDE_MS365.md`.

---

## Streamlit Session State

**Critical:** `st.download_button` triggers full rerun — store hub before rendering any widget.

```python
if generate_btn:
    hub = run_pipeline(hub, config, callback)
    st.session_state["hub"] = hub   # BEFORE any widget

if "hub" in st.session_state:
    hub = st.session_state["hub"]
    # render tabs, buttons...
```

**Re-run pattern:** buttons write `st.session_state.rerun_agent = "bpmn"` → `handle_rerun()` picks it up via `.pop()` on next Streamlit run.

**Pipeline dual-mode:** `pipeline_mode` radio (`_MODE_NEW` / `_MODE_LOAD`). Modo B calls `load_meeting_as_hub(meeting_id, project_id)` and sets `hub.loaded_from_db = True`. Hub is cleared when modes switch (`_last_pipeline_mode` guard). `st.rerun()` NOT called after pipeline (would erase hub before tab render).

**File uploader guard:** `ui/input_area.py` uses `_last_uploaded_file = f"{name}_{size}"` to detect genuinely new uploads — prevents hub from being erased on every Streamlit rerun after pipeline execution.

---

## Mermaid Syntax Constraints

- Decision nodes: `{}` not `{{}}`. No quoted labels inside `{}` braces.
- Avoid reserved node IDs: `END`, `START`, `default`.
- Non-ASCII characters in subgraph IDs must be normalized.
- Mermaid version 10 is in use.

---

## Dependencies

```
streamlit==1.45.1
anthropic==0.49.0
openai==1.65.0
python-docx==1.1.2
fpdf2==2.8.2
google-generativeai>=0.8.0
google-genai>=1.0.0
supabase>=2.4.0
langgraph>=1.0
```

Always pin exact versions for Streamlit Cloud reproducibility. Append with pinned version when adding new dependencies — no version ranges.

---

## Deploy Flow

```
Local edit (PyCharm / Windows)
    → git add . && git commit -m "description"
    → git push origin main
    → Streamlit Cloud detects push → automatic rebuild
```

Never edit multi-hundred-line files in the GitHub web editor — corrupts complex files on paste.

### 📂 Pasta `manifestos/` — Governança Macro

Documentos de governança e princípios arquiteturais vivem em `manifestos/`. Leitura obrigatória ao iniciar qualquer nova sessão ou tarefa complexa:

| Arquivo | Propósito |
|---|---|
| `manifestos/COLLABORATIVE_MANIFESTO.md` | Papéis (Antigravity / Claude Code / Humano), fluxo de rascunhos, memória cross-session |
| `manifestos/ENGINEERING_MANIFESTO.md` | 9 princípios arquiteturais: Fail-Open, Isolamento de Estado, LGPD, API Auth, Padrão PC83/PC84 |
| `manifestos/CONTINUIDADE_ARQUITETURAL.md` | Blindagem contra SPOF — protocolo de substituição do Arquiteto Sênior quando APIs indisponíveis |

### 🔄 Fluxo Co-Agente de Rascunhos (Drafts)
- **Criação de Blueprints (Antigravity/Arquitetura):** Todo arquivo conceitual, rascunho de endpoint ou esqueleto de novo módulo DEVE ser criado exclusivamente dentro do diretório `drafts/` (ex: `drafts/api_draft.py`). Nunca na raiz.
- **Implementação e Arquivamento (Claude Code/Engenharia):** Ao assumir um rascunho de `drafts/` para transformá-lo em código de produção oficial no core do sistema, o Claude Code DEVE:
  1. Implementar a lógica real nos módulos finais.
  2. Mover o arquivo de rascunho original para `drafts/arquivadas/` mantendo o histórico de design.
  3. Nunca deletar rascunhos antigos diretamente sem consentimento humano.

---

## Extending the System

### Adding a new agent

1. Create `agents/agent_new.py` inheriting from `BaseAgent`
2. Create `skills/skill_new.md` — **use lowercase filename**; verify with `git ls-files skills/`
3. Add field + migrate guard in `core/knowledge_hub.py`
4. Register in `agents/orchestrator.py → _PLAN` and `run()` parameters
5. Add checkbox in `ui/sidebar.py`
6. Add to `core/rerun_handlers.py`
7. Create tab in `ui/tabs/` and register in `ui/tabs/__init__.py`
8. Add export in `ui/tabs/export_tab.py` if it generates a new artefact

### Adding a new diagram format

1. Create `modules/diagram_newformat.py` → `generate_newformat(bpmn: BPMNModel) -> str`
2. Add field to `BPMNModel` in `core/knowledge_hub.py`
3. Call generator in `agents/agent_bpmn.py` after JSON extraction
4. Add tab module + register in `ui/tabs/__init__.py`

### Modifying BPMN layout

Coordinates are absolute. Edit constants at top of `bpmn_generator.py`: `TASK_W`, `H_GAP`, `V_PAD`. Verify crossing-elimination heuristic after changes.

---

## Known Pitfalls

> Full code examples for all pitfalls: `claude_guideline/pitfalls.md`

| Pitfall | Fix |
|---|---|
| **Skill file case sensitivity (Linux)** | Verify with `git ls-files skills/` — `_load_skill()` uses absolute path |
| **Stale `.pyc` on Streamlit Cloud** | Use `hasattr` guards + `try/except ImportError` in `migrate()` |
| **`st.page_link("app.py")`** | Use `"pages/Pipeline.py"` — `app.py` is not a registered page |
| **GitHub web editor on large files** | Replaces entire file with clipboard content silently — `project_store.py` (3556 lines) was replaced with a 93-line stub (commit 797eb35). Always use PyCharm/CLI for multi-hundred-line files |
| **Login HTML as code block** | Keep `st.markdown(unsafe_allow_html=True)` HTML at zero indentation |
| **`st.error()` before `st.rerun()`** | Persist message in `st.session_state`; pop+display after rerun |
| **bpmn-js SVGMatrix non-finite** | Defer `canvas.zoom('fit-viewport')` via `setTimeout(fn, 150)` with dimension guards |
| **Active-project fragmentation** | Call `require_active_project()` — never add local project selectbox to analysis pages |
| **`href="#id"` in components.html** | Use `data-target` + JS `scrollIntoView` — anchor hrefs navigate the Streamlit parent frame |
| **Gemini embedding model 404** | Use `gemini-embedding-001` with `output_dimensionality=512`; fallback to `gemini-embedding-2-preview` |
| **Gemini free tier rate limit** | 1.2s delay + 5 retries + extract `retry_delay` from 429 body |
| **pgvector ivfflat > 2000 dims** | Use `output_dimensionality=EMBEDDING_DIM` (512); column must be `vector(512)`; migration `supabase_migration_embedding_512.sql` |
| **Pages import path on Cloud** | Add project root to `sys.path` manually in each page file |
| **Google Calendar TOML encoding** | Use `'''` not `"""` for `credentials_json` |
| **delete_meeting cascade order** | `requirement_versions` → FK nullify → SBVR/chunks → bpmn_versions → bpmn_processes → meetings |
| **Anthropic no json_mode** | Enforce JSON via system prompt only — never pass `response_format` to Anthropic SDK |
| **Nested `st.expander`** | Streamlit raises `StreamlitAPIException` if an expander is inside another expander (e.g. sidebar Configuração Avançada). Use `st.caption()` or `st.markdown()` as section header instead |
| **Variable child count in a shared UI component** | A reusable component whose rendered element count changes between reruns (e.g. a `st.button()` toggle that conditionally renders a form) breaks the frontend with `Uncaught Error: Bad 'setIn' index N (should be between [0, 0])` when called from a context whose sibling count matters (loops, other containers). Fix: wrap the whole component body in a single `st.container()` (or `st.empty()`) so the parent always sees exactly one child from the component, regardless of internal branch — see `ui/tabs/bpmn_tabs.py`'s `_main = st.empty()` comment and `ui/components/promote_asset.py`'s `render_promote_button()` |
| **Settings Domínio tab provider list** | Must iterate `AVAILABLE_PROVIDERS` (not `PROVIDER_KEY_MAP`) and skip providers with `api_key_alias` — `PROVIDER_KEY_MAP` is only the Supabase storage schema, not the source of truth for which providers exist |

---

## Technical References

| Resource | Location |
|---|---|
| BPMN 2.0 Spec | ISO/IEC 19510 / OMG formal/2013-12-09 |
| bpmn-js | github.com/bpmn-io/bpmn-js (v17) |
| mermaid.ink SVG endpoint | mermaid.ink |
| pgvector | github.com/pgvector/pgvector — ivfflat max 2000 dims |
| google-generativeai | pypi.org/project/google-generativeai |
| Supabase Python client | supabase.com/docs/reference/python |

---

## Decisões Padrão (não perguntar)

- Novos agentes: sempre herdar de BaseAgent, seguir padrão §Agent Pattern
- Novos campos em KnowledgeHub: sempre adicionar guard em migrate()
- Skill files: sempre lowercase, verificar com git ls-files antes de commitar
- Supabase: sempre fail-open (retornar [] ou None, nunca deixar exceção vazar)
- UI: nunca adicionar selectbox de projeto nas páginas de análise (usar require_active_project())
- Streamlit: nunca usar href="#id" em components.html — usar data-target + scrollIntoView

## Checklist de Entrega

Antes de marcar uma feature como concluída:
- [ ] migrate() atualizado se KnowledgeHub foi modificado
- [ ] Skill file com nome correto (git ls-files)
- [ ] Agente registrado no Orchestrator._PLAN e rerun_handlers
- [ ] Tab registrada em ui/tabs/__init__.py
- [ ] Export adicionado em export_tab.py se gera novo artefato
- [ ] Versão registrada em `claude_guideline/roadmap.md`

## Planos de Implementação
Planos HTML detalhados para features em desenvolvimento: `claude_guideline/plans/`
