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
- **Current version:** v4.27

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
│   ├── Home.py                   # Landing page — project selector, KPIs, recent meetings
│   ├── Pipeline.py               # Main pipeline — dual-mode (Nova transcrição / Reunião existente)
│   ├── Diagramas.py              # Full-screen diagram viewer (BPMN, Mermaid, Mind Map)
│   ├── BpmnEditor.py             # BPMN editor — bpmn-js Modeler, version history, Supabase save
│   ├── Assistente.py             # RAG assistant — conversational Q&A over transcripts
│   ├── Artefatos.py              # Central de Artefatos — 10 abas: req, mind map, contradições, histórico, reuniões, SBVR, BPMN, DMN, IBIS, rastreabilidade
│   ├── KnowledgeGraph.py         # Knowledge graph — pyvis physics (Obsidian-like), entity/contradiction viz
│   ├── MeetingROI.py             # ROI-TR dashboard — type-aware quality indicators
│   ├── DocumentManager.py        # Document management — 5 tabs: upload, library, extract artifacts, cross-ref, taxonomy
│   ├── CostBenefitScenarios.py   # Cenários de Custo-Benefício — compara até 5 combinações agente→modelo, presets, gráficos Plotly, apply ao pipeline
│   ├── Settings.py               # Central settings — LLM providers, API keys, tool catalog
│   ├── DatabaseOverview.py       # Database health — record counts, embeddings, integrity fixes
│   ├── CostEstimator.py          # LLM cost estimator
│   ├── LLMBenchmark.py           # LLM Benchmark & Telemetria — on-demand benchmark + passive telemetry analysis
│   ├── Orientacoes_ComoIniciar.py   # Guia de início rápido
│   ├── Orientacoes_Assistente.py    # Guia de ferramentas do Assistente (33 tools + exemplos)
│   ├── Orientacoes_Glossario.py     # Glossário interativo (components.v1.html — busca + filtros + índice alfabético)
│   ├── Orientacoes_Arquiteturas.py  # Arquiteturas do sistema
│   ├── Orientacoes_CKF.py           # Guia CKF
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
│   ├── assistant_tools.py        # Tool schemas + AssistantToolExecutor
│   ├── chart_config.py           # CHART_PALETTES + DEFAULT_PALETTE (zero-dependency)
│   ├── cost_model.py             # ModelPricing, AgentTokenProfile, ScenarioConfig, ScenarioResult, PRICING_CATALOG, project_cost()
│   └── schema.py                 # Legacy schemas
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
│   └── agent_document_extractor.py # On-demand: extracts req/SBVR/BMM/DMN artifacts from a document
│
├── modules/
│   ├── config.py                 # LLM provider registry — add new providers here
│   ├── session_security.py       # API keys in st.session_state only
│   ├── bpmn_generator.py         # BPMN 2.0 XML generator (absolute coordinates)
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
│   └── tabs/
│       ├── bpmn_tabs.py          # render_bpmn(), render_mermaid(), render_validation()
│       ├── quality_tab.py        # transcript quality results
│       ├── minutes_tab.py        # meeting minutes display
│       ├── requirements_tab.py   # requirements table + mindmap
│       ├── sbvr_tab.py           # SBVR vocabulary + rules + JSON export
│       ├── bmm_tab.py            # BMM vision/mission/goals/strategies/policies
│       ├── synthesizer_tab.py    # executive HTML report
│       ├── export_tab.py         # all download buttons
│       └── dev_tools_tab.py      # KnowledgeHub JSON debug panel
│
├── services/
│   ├── export_service.py         # make_filename(base, ext, prefix, suffix) → str
│   ├── file_ingest.py            # load_transcript() wrapper
│   ├── preprocessor_service.py  # preprocess_transcript() wrapper
│   ├── semantic_cache.py        # SemanticCache — SHA256 LLM response cache (Supabase llm_cache)
│   ├── context_analyzer.py     # estimate_tokens(), should_use_long_context(), LONG_CONTEXT_AGENTS
│   └── llm_telemetry.py        # LLMTelemetry (async Supabase write), run_benchmark_call(), BENCHMARK_TASKS, _telemetry singleton
│
├── skills/
│   ├── skill_bpmn.md             # AgentBPMN system prompt (lowercase)
│   ├── skill_minutes.md          # AgentMinutes system prompt (lowercase)
│   ├── skill_transcript_quality.md
│   ├── skill_sbvr.md
│   ├── skill_bmm.md
│   ├── skill_document_analyzer.md   # DocumentAnalyzerAgent — cross-reference analysis
│   ├── skill_document_extractor.md  # DocumentExtractorAgent — artifact extraction from docs
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
└── claude_guideline/
    ├── roadmap.md                # PC1–PC11 full history
    ├── architecture_details.md   # BPMN generator internals, RAG details, ROI-TR formulas
    └── pitfalls.md               # Known pitfalls with full code examples
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
| **Pipeline** | Pipeline.py, Diagramas.py, BpmnEditor.py | Todos |
| **Análise** | Assistente.py, Artefatos.py, ValidationHub.py, MeetingROI.py, DocumentManager.py, CostBenefitScenarios.py | Todos |
| **Sistema** | Settings.py, CostEstimator.py, LLMBenchmark.py [+ MasterAdmin.py, DatabaseOverview.py] | Todos [admin extra] |
| **Ajuda** | ComoIniciar, Assistente (tool guide), Glossário, Arquiteturas, CKF | Todos |
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

`BaseAgent` provides: `_call_llm()`, `_parse_json()`, `_load_skill()` (absolute path, CWD-independent), up to 3 JSON retries, token tracking in `hub.meta.total_tokens_used`. `_call_llm()` flow: (1) PII sanitize, (2) long context detection via `services/context_analyzer` (injects instruction into system, increases max_tokens to 8192 and timeout to 180s for LONG_CONTEXT_AGENTS={bpmn,sbvr,bmm} when transcript >50k tokens), (3) cache hash of modified system, (4) check `services/semantic_cache.SemanticCache` (stores raw pre-desanitize; on hit applies current `token_map` — PII-safe), (5) API call, (6) record telemetry via `services/llm_telemetry._telemetry` (async, fail-open — latency_ms, tokens_in/out, provider, model, long_context, benchmark_run=False), (7) cache store, (8) desanitize. `hub.meta.cache_hits` + `tokens_saved` + `long_context_calls` tracked per session. `skip_cache=True` to bypass cache. `_call_openai`/`_call_anthropic` return `(raw, tokens_in, tokens_out)`.

Provider routing in `_call_llm()`: `"openai_compatible"` → OpenAI SDK with custom `base_url`; `"anthropic"` → native Anthropic SDK.

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
| Groq (Llama) | `llama-3.3-70b-versatile` | `openai_compatible` | Fastest |
| Google Gemini | `gemini-2.0-flash` | `openai_compatible` | Free tier |
| Grok (xAI) | `grok-4-1-fast-reasoning` | `openai_compatible` | 2M context |

To add a new provider: edit `AVAILABLE_PROVIDERS`. If `client_type` is new, add routing in `BaseAgent._call_llm()`. To enable thinking mode: add `reasoning_effort: "high"` to the provider entry — `_call_openai` handles the rest (passes `extra_body={"thinking": {"type": "enabled"}}`, drops `temperature`). To share an API key with another provider (e.g. model variants): add `api_key_alias: "<provider_name>"` — `session_security` resolves the key from the aliased provider automatically; no re-entry needed.

---

## LLM Telemetry (`services/llm_telemetry.py`)

Passive telemetry is recorded automatically by `BaseAgent._call_llm()` on every real API call (not cache hits). Records are written asynchronously via a daemon thread — never blocks the pipeline. Stored in Supabase `llm_telemetry` table (90-day auto-cleanup).

**`TelemetryRecord` fields:** `agent_name`, `provider`, `model`, `latency_ms`, `input_tokens`, `output_tokens`, `total_tokens`, `from_cache`, `long_context`, `is_error`, `benchmark_run`.

**`run_benchmark_call(provider_name, provider_cfg, api_key, system, user)`** — standalone timed call (no hub/cache/PII). Used by `pages/LLMBenchmark.py` for on-demand benchmarks.

**`BENCHMARK_TASKS`** — 5 representative tasks: `bpmn`, `minutes`, `requirements`, `sbvr`, `bmm`. Each has a concise `system` + `user` prompt with `{transcript}` placeholder.

**`TRANSCRIPTS`** — 2 synthetic transcripts: `"Curta (~150 palavras)"` / `"Media (~350 palavras)"`.

**`pages/LLMBenchmark.py`** (Sistema group) — two tabs:
- **🧪 Benchmark On-Demand:** multi-select configured providers + agents, N runs slider, transcript selector, progress bar, results table, latency bar chart, throughput bar chart.
- **📊 Telemetria Real:** filters (provider/agent/days/include_cache/include_benchmark), 4 KPIs, 4 sub-tabs: Latência (box plot p5/p25/median/p75/p95), Throughput (tokens/s grouped bar), Histórico (line chart by day), Heatmap (agent × provider median latency).

**Migration:** `setup/supabase_migration_llm_telemetry.sql` — ✅ EXECUTADO (2026-05-23).

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

bpmn-js 17 injected inline (server-side asset fetch + `lru_cache`, no CDN). `canvas.zoom('fit-viewport')` deferred via `setTimeout(fn, 150)` — prevents SVGMatrix non-finite error on zero-dimension container. CDN fallback when server-side fetch fails.

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

### Tool list (`core/assistant_tools.py`)

**Non-admin:** `get_meeting_list`, `get_meeting_participants`, `get_meeting_decisions`, `get_meeting_action_items`, `get_meeting_summary`, `search_transcript`, `get_requirements`, `list_bpmn_processes`, `list_bpmn_versions`, `get_sbvr_terms`, `get_sbvr_rules`, `calendar_list_events`, `calendar_get_event`, `calendar_suggest_time`, `get_system_capabilities`, `lookup_entity`, `get_cache_stats`, `list_meeting_documents`, `get_document_content`, `search_documents`, `get_document_types`, `search_glossary`.

**Admin only (`is_admin()`):** `get_database_integrity`, `fix_missing_llm_provider`, `generate_meeting_embeddings`, `reprocess_meeting_full`, `calendar_create_event`, `calendar_schedule_action_items`, `calendar_share_with_user`, `calendar_revoke_access`, `calendar_diagnose`, `delete_entity`, `resolve_entity_ambiguity`, `clear_llm_cache`, `delete_bpmn_version`, write/generate tools.

**KnowledgeGraph entity tools (3):** `lookup_entity` — investiga entidade (tipo, aliases, reuniões); `delete_entity` — remove entidade (3-tier match: exact → name-substring → alias-substring, para se houver ambiguidade); `resolve_entity_ambiguity` — funde duplicatas via `merge_entities()`.

**Cache tools (2):** `get_cache_stats(agent_name?)` — estatísticas do cache LLM (entradas, hits, tokens economizados, USD por agente); `clear_llm_cache(agent_name?)` — invalida entradas (admin). Cache em `services/semantic_cache.py`; tabela `llm_cache` no Supabase (`setup/supabase_migration_llm_cache.sql`).

**BPMN version tools (2):** `list_bpmn_versions(process_name)` — lista versões de um processo por nome (ID, status atual, reunião, notas); `delete_bpmn_version(version_id, reason?)` — exclui versão pelo UUID (admin); recusa única versão; promove anterior se is_current; atualiza version_count. Fluxo: chamar `list_bpmn_versions` primeiro para obter o version_id.

**Document tools (4):** `list_meeting_documents(meeting_number?, doc_type?)` — lista documentos do projeto com filtro opcional; `get_document_content(doc_id)` — conteúdo completo (cap 8k chars); `search_documents(query, mode)` — busca semantic|keyword nos documentos; `get_document_types()` — taxonomia completa (53 tipos / 9 categorias). Tabelas: `meeting_documents`, `document_chunks vector(1536)`; migration: `setup/supabase_migration_documents.sql`.

**Glossário tool (1):** `search_glossary(query, tag?)` — busca os 80 verbetes do glossário técnico por termo, definição, exemplo ou termos relacionados. `tag` filtra por categoria: `bpmn` | `req` | `ai` | `dev` | `neg`. Dados em `modules/glossary_data.py` (sem Supabase — busca local em memória). Use quando o usuário perguntar o significado de siglas ou conceitos (BPMN, SBVR, RAG, NER, ROI-TR, CKF etc.).

**Chart tools (5):** `generate_requirements_chart`, `generate_meetings_timeline`, `generate_action_items_chart`, `generate_roi_chart`, `generate_custom_chart` — Plotly figs returned as 4th element of `chat_with_tools()`, rendered via `st.plotly_chart()`. Palettes defined in `core/chart_config.py`.

Tool schemas: `get_tool_schemas_openai()` / `get_tool_schemas_anthropic()`.

### Embedding pipeline

- `chunk_text(transcript, chunk_size=500, overlap=80)` → chunks stored in `transcript_chunks` table (`vector(1536)`)
- Provider padrão: OpenAI `text-embedding-3-small` (default em `asst_embed_provider`); alternativas: Google Gemini `gemini-embedding-001` (`output_dimensionality=1536`, fallback `gemini-embedding-2-preview` on 404), Grok `grok-embedding-small`
- Rate limit: 1.2s delay between calls, 5 retries on 429
- Search via `match_transcript_chunks()` SQL (pgvector cosine)

> Full architecture diagrams (Mode A/B flow, re-edit feature, embedding UI): `claude_guideline/architecture_details.md`

---

## ROI-TR Dashboard (`pages/MeetingROI.py`)

Type-aware quality system — 11 meeting types, each with a weight matrix across 5 artefact dimensions (req/dec/act/sbvr/bpmn). `classify_meeting_type()` uses LLM (1 call/meeting) or heuristic fallback. Results persisted to `meetings.meeting_type`. No new Supabase tables required.

> Full formulas, TYPE_WEIGHTS matrix: `claude_guideline/architecture_details.md`

---

## Document Management (`pages/DocumentManager.py`)

5 tabs: **📤 Enviar** (upload .txt/.pdf/.docx or paste, category→type taxonomy, auto-embed) · **📚 Biblioteca** (keyword + semantic search, preview, delete, re-index) · **⚗️ Extrair Artefatos** (run `DocumentExtractorAgent` → preview 7 artifact types → save via `save_artifacts_from_document()`) · **🔍 Análise Cruzada** (doc × meeting hub → `DocumentAnalyzerAgent` → alignment score 0–100 + report) · **🏷️ Taxonomia** (53 types / 9 categories).

**`modules/document_store.py`** — CRUD + embedding pipeline + search. Key functions: `upload_document`, `embed_document` (chunks 500/80 via `chunk_text`+`embed_batch`), `search_documents_semantic` (pgvector RPC), `search_documents_keyword`, `update_document_meta`.

**Artifact origin traceability (PC23):** all analytical artifacts have `origin: str = "transcricao"|"documento"` + `doc_ref: Optional[str]` (UUID of `meeting_documents`). Pipeline artifacts always have `origin="transcricao"`. Document-extracted artifacts have `origin="documento"` + `doc_ref=<doc_id>`. `save_artifacts_from_document(project_id, doc_id, extracted)` persists req/SBVR/BMM/DMN; `meeting_id` is nullable for document-sourced artifacts.

**SQL migrations:** `setup/supabase_migration_documents.sql` + `setup/supabase_migration_artifact_origin.sql` — ✅ EXECUTADOS.

---

## Core Modules (`core/`)

- `session_state.init_session_state()` — idempotent, call immediately after `st.set_page_config()`. Defaults: provider=DeepSeek, embed_provider=OpenAI, run_quality/bpmn/minutes/requirements=True, run_sbvr/bmm/synthesizer/dmn/argumentation/ckf_updater/query_summarizer=True, n_bpmn_runs=3, use_langgraph=True, enable_long_context=True.
- `pipeline.run_pipeline(hub, config, callback)` — 3 paths: multi-run tournament / LangGraph / standard. Raises on error (caller catches).
- `rerun_handlers.handle_rerun(agent_name, ...)` — re-runs one agent: `"quality"`, `"bpmn"`, `"minutes"`, `"requirements"`, `"sbvr"`, `"bmm"`, `"synthesizer"`. BPMN re-run invalidates `hub.synthesizer`.
- `cost_model.py` — modelo de dados para Cenários de Custo-Benefício (sem Streamlit, sem rede). Exporta: `ModelPricing`, `AgentTokenProfile`, `ScenarioConfig`, `ScenarioResult`, `PRICING_CATALOG` (17 modelos / 6 provedores), `DEFAULT_TOKEN_PROFILES` (9 agentes com perfis heurísticos), `project_cost(scenario, word_count, catalog) → ScenarioResult`. Catálogo editável via `st.session_state["cost_catalog_overrides"]`; cenário ativo em `st.session_state["scenario_assignments"]` (dict agent_name→model_id) — lido por `BaseAgent._call_llm()` para sobrescrever `model` por agente (fail-open se ausente).
- `project_store` — Supabase CRUD; fail-open (returns `[]`/`None` when unconfigured). Key functions: `load_meeting_as_hub(meeting_id, project_id)` → reconstructs KnowledgeHub from DB (transcript, BPMN, minutes, requirements, SBVR, BMM, DMN, IBIS); `list_dmn_by_project(project_id)` → flat list of DMN decisions; `list_argumentation_by_project(project_id)` → flat list of IBIS questions; `save_artifacts_from_document(project_id, doc_id, extracted)` → persists all artifact types extracted from a document. Full function list in `claude_guideline/architecture_details.md`.

---

## Security Model

API keys: `st.session_state` only — never logged, written to disk, or persisted.

**Auth:** `apply_auth_gate()` + SHA-256 hashed credentials in `modules/auth.py → USUARIOS`. Roles: `master > admin > user`. `is_admin()` returns True for both `admin` and `master`. `_role` stored in session_state on login.

**Supabase:** `st.secrets["supabase"]["url"]` + `["key"]`. Fail-open when absent.

**Database (DDL / migrations):** `st.secrets["database"]["connection_string"]` — direct PostgreSQL via `psycopg2`. Password is URL-encoded (special chars: `?`→`%3F`, `#`→`%23`, `/`→`%2F`). Use this for running migrations programmatically (`conn.autocommit = True`). Only in local `secrets.toml` — never deployed to Streamlit Cloud.

**Google Calendar secrets:** `st.secrets["google_calendar"]["calendar_id"]` + `["credentials_json"]`. Always use `'''` (triple-single-quotes) for `credentials_json` in TOML — `"""` corrupts the private key. Resolution order per call: Supabase `project_calendar_config` → secrets → local file → `"primary"`.

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
| **Gemini embedding model 404** | Use `gemini-embedding-001` with `output_dimensionality=1536`; fallback to `gemini-embedding-2-preview` |
| **Gemini free tier rate limit** | 1.2s delay + 5 retries + extract `retry_delay` from 429 body |
| **pgvector ivfflat > 2000 dims** | Always use `output_dimensionality=1536`; column must be `vector(1536)` |
| **Pages import path on Cloud** | Add project root to `sys.path` manually in each page file |
| **Google Calendar TOML encoding** | Use `'''` not `"""` for `credentials_json` |
| **delete_meeting cascade order** | `requirement_versions` → FK nullify → SBVR/chunks → bpmn_versions → bpmn_processes → meetings |
| **Anthropic no json_mode** | Enforce JSON via system prompt only — never pass `response_format` to Anthropic SDK |
| **Nested `st.expander`** | Streamlit raises `StreamlitAPIException` if an expander is inside another expander (e.g. sidebar Configuração Avançada). Use `st.caption()` or `st.markdown()` as section header instead |
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
