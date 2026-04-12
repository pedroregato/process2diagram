# CLAUDE.md — Process2Diagram

> Read this file in full before making any changes to the codebase.

## Project Overview

**Process2Diagram** converts meeting transcriptions into professional process diagrams using a multi-LLM pipeline.

- **Input:** raw text transcript (paste, `.txt`, `.docx`, or `.pdf` upload)
- **Outputs:** BPMN 2.0 XML, Mermaid flowchart, meeting minutes (Markdown / Word / PDF), requirements analysis (JSON/Markdown), executive HTML report, interactive requirements mind map
- **Deploy:** Streamlit Cloud — auto-deploy on push to `main` branch (`github.com/pedroregato/process2diagram`)
- **Dev environment:** PyCharm on Windows; Python 3.13
- **Current version:** v4.11

Supported LLM providers: DeepSeek (default), Claude (Anthropic), OpenAI, Groq, Google Gemini.

---

## Running the App

```bash
pip install -r requirements.txt

# Required once — Portuguese NLP model
python -m spacy download pt_core_news_lg

streamlit run app.py
# → http://localhost:8501
```

No build step, no test suite, no Makefile.

---

## Repository Structure

```
process2diagram/
├── app.py                        # Streamlit entry point — slim orchestrator; delegates to ui/ and core/
│
├── pages/
│   ├── Settings.py               # ⚙️ Central settings — LLM providers, API keys, embedding, search, preferences
│   ├── Diagramas.py              # Full-screen multi-page diagram viewer (BPMN, Mermaid, Mind Map)
│   ├── Assistente.py             # RAG-powered assistant — semantic Q&A over meeting transcripts
│   ├── BatchRunner.py            # Batch pipeline — runs the full pipeline on multiple transcripts
│   ├── BpmnBackfill.py           # Backfill BPMN XML for meetings stored in Supabase (no re-transcription)
│   ├── ReqTracker.py             # Requirements tracker — Supabase-backed requirement status board
│   ├── TranscriptBackfill.py     # Backfill transcript embeddings for existing meetings in Supabase
│   ├── CostEstimator.py          # LLM cost estimator — interactive breakdown per provider/agent
│   └── DatabaseOverview.py       # Database health dashboard — consolidated record counts and integrity check
│
├── core/
│   ├── knowledge_hub.py          # KnowledgeHub: central session state shared by all agents
│   ├── pipeline.py               # run_pipeline() — executes orchestrator with multi-run BPMN support
│   ├── lg_pipeline.py            # LGBPMNRunner — LangGraph adaptive BPMN retry loop
│   ├── session_state.py          # init_session_state() — initializes all st.session_state keys
│   ├── rerun_handlers.py         # handle_rerun() — re-executes a single named agent
│   ├── assistant_tools.py        # Tool schemas + AssistantToolExecutor for AgentAssistant tool-use mode
│   └── schema.py                 # Legacy schemas (Process, Step, Edge, BpmnProcess…)
│
├── agents/
│   ├── base_agent.py             # Abstract base — LLM routing, JSON retry, token tracking
│   ├── orchestrator.py           # Sequences all agents; Minutes+Requirements run in parallel via ThreadPoolExecutor
│   ├── nlp_chunker.py            # Pure Python/spaCy preprocessor — no LLM
│   ├── agent_transcript_quality.py  # Transcript quality gate (grade A–E, criteria)
│   ├── agent_bpmn.py             # BPMN extraction + _enforce_rules() + generators
│   ├── agent_mermaid.py          # MermaidGenerator class — pure Python, no LLM
│   ├── agent_minutes.py          # Meeting minutes extraction (full transcript, initials)
│   ├── agent_requirements.py     # Requirements extraction (IEEE 830; speaker attribution)
│   ├── agent_sbvr.py             # AgentSBVR — OMG SBVR vocabulary (5–15 terms) + rules (3–10)
│   ├── agent_bmm.py              # AgentBMM — OMG BMM vision/mission/goals/strategies/policies
│   ├── agent_synthesizer.py      # Executive HTML report synthesis (narrative + HTML gen)
│   └── agent_validator.py        # AgentValidator — pure Python BPMN quality scorer, no LLM
│
├── modules/
│   ├── config.py                 # LLM provider registry — add new providers here
│   ├── session_security.py       # API keys in st.session_state only, never persisted
│   ├── bpmn_generator.py         # OMG BPMN 2.0 XML generator (absolute coordinates layout)
│   ├── bpmn_viewer.py            # BPMN viewer component (bpmn-js 17 injected inline)
│   ├── bpmn_auto_repair.py       # repair_bpmn() — 4-pass deterministic repair engine (no LLM)
│   ├── bpmn_structural_validator.py  # validate_bpmn_structure() — 6 structural checks, severity levels
│   ├── bpmn_diagnostics.py       # render_bpmn_diagnostics() — BPMN diagnostic panel for Streamlit
│   ├── mermaid_renderer.py       # render_mermaid_block() — shared Mermaid SVG renderer (pan/zoom/fit)
│   ├── requirements_mindmap.py   # generate_requirements_mindmap() + build_mindmap_tree()
│   ├── mindmap_interactive.py    # render_mindmap_from_requirements() — interactive SVG mindmap
│   ├── diagram_mermaid.py        # Mermaid flowchart generator (legacy)
│   ├── executive_html.py         # Executive HTML report generator (self-contained, interactive)
│   ├── minutes_exporter.py       # Export MinutesModel → Word (.docx) and PDF via fpdf2
│   ├── transcript_preprocessor.py  # Cleans ASR artefacts, fillers, repetitions
│   ├── diagram_bpmn.py           # Legacy BPMN generator (kept for compatibility)
│   ├── extract_llm.py            # Legacy LLM adapter (used by app.py v1 flow)
│   ├── extract_heuristic.py      # Heuristic extractor (no-LLM fallback)
│   ├── ingest.py                 # .txt/.docx/.pdf file loader
│   ├── preprocess.py             # Basic text cleaning
│   ├── utils.py                  # Helpers (process_to_json, etc.)
│   ├── auth.py                   # Session-based login — SHA-256 credential validation, is_authenticated()
│   ├── supabase_client.py        # get_supabase_client() — singleton Supabase client from st.secrets
│   ├── reqtracker_exporter.py    # Export RequirementsModel to Excel/CSV for ReqTracker page
│   ├── text_utils.py             # rule_keyword_pt() — Portuguese keyword normalisation helpers
│   ├── cost_estimator.py         # Pure-Python LLM cost calculator — PROVIDER_PRICING table, estimate_cost()
│   └── embeddings.py             # chunk_text(), embed_text(), embed_batch() — Gemini/OpenAI embeddings (1536 dims)
│
├── ui/
│   ├── sidebar.py                # render_sidebar() — provider, config, agent toggles, re-run buttons
│   ├── input_area.py             # render_input_area() — transcript text area + file upload + pre-process
│   ├── architecture_diagram.py   # render_architecture_diagram() — splash flowchart TD (cached SVG)
│   ├── auth_gate.py              # apply_auth_gate() / render_login_page() — login wall; st.stop() if unauthenticated
│   ├── assistant_diagram.py      # render_assistant_diagram() — RAG pipeline architecture splash (Assistente page)
│   ├── project_selector.py       # render_project_selector() — Supabase project/meeting picker widget
│   ├── components/
│   │   ├── copy_button.py        # Copy-to-clipboard button component
│   │   ├── download_button.py    # Styled download button wrapper
│   │   └── transcript_highlighter.py  # Transcript text highlighter component
│   └── tabs/
│       ├── bpmn_tabs.py          # render_bpmn(), render_mermaid(), render_validation()
│       ├── quality_tab.py        # render() — transcript quality results
│       ├── minutes_tab.py        # render() — meeting minutes display
│       ├── requirements_tab.py   # render() — requirements table + mindmap
│       ├── sbvr_tab.py           # render() — SBVR vocabulary table + rules list + JSON export
│       ├── bmm_tab.py            # render() — BMM vision/mission/goals/strategies/policies
│       ├── synthesizer_tab.py    # render() — executive HTML report
│       ├── export_tab.py         # render() — all download buttons grouped
│       └── dev_tools_tab.py      # render() — KnowledgeHub JSON debug panel
│
├── services/
│   ├── export_service.py         # make_filename(base, ext, prefix, suffix) → str
│   ├── file_ingest.py            # load_transcript() wrapper over modules/ingest.py
│   └── preprocessor_service.py  # preprocess_transcript() wrapper over transcript_preprocessor
│
├── setup/
│   ├── setup_v3.py               # Setup helpers
│   └── supabase_schema_transcript_chunks.sql  # DDL: transcript_chunks table (vector(1536), ivfflat), match_transcript_chunks()
│
├── skills/
│   ├── skill_bpmn.md             # System prompt for AgentBPMN (lowercase)
│   ├── skill_minutes.md          # System prompt for AgentMinutes (lowercase — SKILL_MINUTES.md also exists, legacy)
│   ├── skill_transcript_quality.md  # System prompt for AgentTranscriptQuality (lowercase)
│   ├── skill_sbvr.md             # System prompt for AgentSBVR (lowercase)
│   ├── skill_bmm.md              # System prompt for AgentBMM (lowercase)
│   ├── SKILL_REQUIREMENTS.md     # System prompt for AgentRequirements (uppercase — git-tracked name)
│   └── SKILL_SYNTHESIZER.md      # System prompt for AgentSynthesizer (uppercase — git-tracked name)
│
├── tests/
│   ├── conftest.py               # Shared factory helpers (step, edge, model, pool, collab)
│   ├── test_bpmn_auto_repair.py  # 36 tests — dangling edges, isolated nodes, XOR labels, gateway bypass
│   ├── test_bpmn_structural_validator.py  # 22 tests — all 6 structural checks + collaboration
│   ├── test_agent_validator.py   # 22 tests — granularity, task type, gateways, structural, weighted
│   └── test_mermaid_generator.py # 26 tests — sanitize, format_node, format_edge, single/multi generate
│
├── requirements.txt              # pinned versions (streamlit, anthropic, openai, python-docx, fpdf2, google-genai…)
└── CLAUDE.md                     # This file
```

> **Linux / Streamlit Cloud — filesystem is case-sensitive.**
> Skill file names in `skill_path` must match the git-tracked filename exactly.
> `git ls-files skills/` shows the authoritative names.
> Mixed-case examples: `skill_bpmn.md` (lowercase) vs `SKILL_REQUIREMENTS.md` (uppercase).
> **Always verify with `git ls-files skills/` before adding a new skill reference.**

---

## Architecture

### Data Flow

```
Transcript (user input)
        │
        ▼
AgentTranscriptQuality   ← LLM; grades transcript A–E; non-fatal if fails
        │  hub.transcript_quality.ready = True
        ▼
Transcript Preprocessor  ← no LLM; removes ASR fillers/artefacts/repetitions
        │  hub.transcript_clean = cleaned text
        ▼
  NLPChunker             ← no LLM; spaCy NER, segmentation, actor detection
        │  hub.nlp.ready = True
        ▼
   AgentBPMN             ← LLM; extracts steps/edges/lanes → BPMN XML, Mermaid
        │  _enforce_rules() post-processes: generic lanes, service-task lanes,
        │  correction-loop redirect, redundant event steps
        │  repair_bpmn() auto-repairs 4 structural issue classes (no LLM)
        │  hub.bpmn.ready = True
        │
        │  (if n_bpmn_runs > 1)  → AgentValidator tournament; best candidate selected
        │  (if use_langgraph)     → LGBPMNRunner adaptive retry until score ≥ threshold
        │  hub.validation.ready = True (tournament) / hub.bpmn.lg_attempts (LangGraph)
        ▼
  AgentMinutes  ┐  parallel via ThreadPoolExecutor (when both enabled)
AgentRequirements┘  each reads hub.transcript_clean (read-only); writes own section
        │  hub.minutes.ready = True; hub.requirements.ready = True
        ▼
   AgentSBVR            ← LLM (optional); OMG SBVR; domain vocabulary + business rules
        │  hub.sbvr.ready = True
        ▼
   AgentBMM             ← LLM (optional); OMG BMM; vision/mission/goals/strategies/policies
        │  hub.bmm.ready = True
        ▼
AgentSynthesizer         ← LLM (optional); reads all hub artifacts incl. SBVR + BMM;
        │  executive narrative (JSON) + calls generate_executive_html()
        │  hub.synthesizer.ready = True; hub.synthesizer.html = full HTML
        ▼
   KnowledgeHub          ← fully populated; stored in st.session_state["hub"]
```

### App.py — Slim Entry Point

`app.py` (v4.11) no longer contains UI rendering logic. It delegates to:

- `ui.auth_gate.apply_auth_gate()` — login wall; called immediately after `st.set_page_config()`; calls `st.stop()` if unauthenticated
- `core.session_state.init_session_state()` — initializes all `st.session_state` keys with defaults
- `ui.sidebar.render_sidebar()` — sidebar panel (always visible)
- `ui.input_area.render_input_area()` — transcript input + file upload + pre-processing
- `core.pipeline.run_pipeline(hub, config, callback)` — executes the full pipeline
- `core.rerun_handlers.handle_rerun(agent, hub, …)` — re-executes a named agent
- `ui.tabs.*` — renders each result tab by delegating to dedicated tab modules

The re-run pattern (sidebar + main body buttons) writes `st.session_state.rerun_agent` which is then consumed by `handle_rerun()` on the next Streamlit run cycle.

### KnowledgeHub — Central State

A pure Python dataclass living in `st.session_state["hub"]`. Each agent reads only what it needs and writes only to its own section. Version counter is bumped after every write.

```python
@dataclass
class KnowledgeHub:
    version: int                      # bumped on every .bump() call
    transcript_raw: str
    transcript_clean: str
    transcript_quality: TranscriptQualityModel  # written by AgentTranscriptQuality
    preprocessing: PreprocessingModel           # written by Transcript Preprocessor
    nlp: NLPEnvelope                  # written by NLPChunker
    bpmn: BPMNModel                   # written by AgentBPMN
    minutes: MinutesModel             # written by AgentMinutes
    requirements: RequirementsModel   # written by AgentRequirements
    synthesizer: SynthesizerModel     # written by AgentSynthesizer
    validation: ValidationReport      # written by AgentValidator (multi-run BPMN)
    meta: SessionMetadata             # tokens, timing, provider info
```

**Schema evolution:** `KnowledgeHub.migrate(hub)` is the single point for backward-compatibility fixes when fields are added. Always add new field guards here instead of scattered `hasattr` checks in `app.py`.

**Golden rule:** never instantiate an agent directly from `app.py`. Always go through `Orchestrator` (via `run_pipeline`) or `handle_rerun`.

### Orchestrator parallel execution

When both `run_minutes=True` and `run_requirements=True`, `Orchestrator._run_minutes_requirements_parallel()` runs both agents concurrently via `ThreadPoolExecutor(max_workers=2)`.

**Why ThreadPoolExecutor, not asyncio?** Streamlit's synchronous run model is incompatible with `asyncio.gather()`. CPython's threading module works correctly inside a Streamlit session.

**Race-condition isolation:** each worker receives `copy.copy(hub)` with `meta = copy.copy(hub.meta)` and `meta.agents_run = list(...)`. Minutes and Requirements each write only to their own section of the hub. No hub field is written by both workers.

**Token merge:** both copies start from `tokens_base = hub.meta.total_tokens_used`. After join: `hub.meta.total_tokens_used += delta_m + delta_r`.

**Thread-safe progress:** `Orchestrator._progress(name, status)` acquires `threading.Lock()` before calling the raw callback — prevents concurrent Streamlit placeholder writes.

**Automatic fallback:** if `ThreadPoolExecutor` raises any exception, execution falls back to sequential Minutes → Requirements with a `(sequencial)` status label.

### Agent Pattern

Every LLM agent in `agents/` inherits from `BaseAgent`:

```python
class MyAgent(BaseAgent):
    name = "my_agent"
    skill_path = "skills/skill_my.md"   # must match git ls-files exactly

    def build_prompt(self, hub, output_language="Auto-detect") -> tuple[str, str]:
        # returns (system_prompt, user_prompt)
        ...

    def run(self, hub, output_language="Auto-detect") -> KnowledgeHub:
        system, user = self.build_prompt(hub, output_language)
        data = self._call_with_retry(system, user, hub)  # handles JSON, retry, tokens
        # populate hub.bpmn / hub.minutes / etc.
        hub.mark_agent_run(self.name)
        hub.bump()
        return hub
```

`BaseAgent` provides: `_call_llm()`, `_parse_json()`, `_load_skill()`, up to 3 retries on JSON parse failure, and token tracking in `hub.meta.total_tokens_used`.

**`_load_skill()` uses absolute path** based on `Path(__file__).parent.parent / skill_path` so it works correctly regardless of the process CWD (local, PyCharm, Streamlit Cloud). Never rely on CWD for file resolution in agents.

Provider routing in `BaseAgent._call_llm()`: reads `client_type` from config — `"openai_compatible"` uses the OpenAI SDK with a custom `base_url`; `"anthropic"` uses the native Anthropic SDK.

### AgentValidator — Pure Python BPMN Scorer

`agents/agent_validator.py` — no LLM call. Used by `core/pipeline.py` when `n_bpmn_runs > 1`.

Scores a `BPMNModel` on three dimensions (each 0–10):
- **Granularity** — activity count relative to transcript word count (target: 1 task per 40–100 words)
- **Task type** — specificity of `task_type` assignments vs. keyword heuristics
- **Gateways** — XOR edges labeled; AND/OR gateways have matching join

Each dimension is weighted via `bpmn_weights = {"granularity": int, "task_type": int, "gateways": int}` (configurable in sidebar). The candidate with highest `weighted` score is selected and stored in `hub.bpmn`; all scores stored in `hub.validation`.

### Multi-run BPMN Optimization

Controlled by `n_bpmn_runs` (sidebar slider: 1, 3, or 5):

1. Run Quality + NLP (pre-requisites) once
2. Run `AgentBPMN` N times on separate `hub` copies
3. `AgentValidator.score()` each candidate
4. Best-scoring BPMN written to `hub.bpmn`; all scores in `hub.validation`
5. Continue with Minutes → Requirements → Synthesizer

A "Validação BPMN" tab appears in results when `hub.validation.ready` and `n_bpmn_runs > 1`.

---

## LLM Providers

Configured in `modules/config.py → AVAILABLE_PROVIDERS`:

| Provider | Default model | client_type | Notes |
|---|---|---|---|
| **DeepSeek** (default) | `deepseek-chat` | `openai_compatible` | Cheapest option |
| Claude (Anthropic) | `claude-sonnet-4-20250514` | `anthropic` | No `json_mode`; use prompt enforcement |
| OpenAI | `gpt-4o-mini` | `openai_compatible` | |
| Groq (Llama) | `llama-3.3-70b-versatile` | `openai_compatible` | Fastest |
| Google Gemini | `gemini-2.0-flash` | `openai_compatible` | Free tier available |

**Anthropic** does not support `json_mode` — enforce JSON output via the system prompt only.

---

## BPMN Generator (`modules/bpmn_generator.py`)

### Layout system

- Uses **absolute coordinates** — there is no declarative direction parameter like Mermaid's `TD`/`LR`.
- Layout constants at top of file: `TASK_W=120`, `TASK_H=60`, `GW_W=50`, `H_GAP=70`, `LANE_HEADER_W=100`.
- `BPMNPlane` must reference `collab_id` (not `process_id`) when a collaboration element exists.
- Elements without a lane assignment produce non-finite SVG coordinates → viewer crash.

### Lane-crossing elimination algorithm

`bpmn_generator.py` runs a single-pass algorithm:

1. **Column layout** — assigns concrete `(x, y, w, h)` positions to all elements
2. **Lane-spanning detection** — flags flows whose source and target are separated by **≥ 2 lane boundaries**. Adjacent-lane flows (span = 1) are intentionally left as direct arrows — bpmn-js routes them natively.
3. **Link Event injection** — replaces each flagged flow with throw/catch Intermediate Link Events.

### Parallel branch alignment (`_align_parallel_branches`)

Post-pass over column assignments, called immediately after `_assign_columns` in `_compute_layout`.

**Problem:** when a split gateway has branches with different numbers of steps, the shorter branch finishes several columns before the join, producing a long diagonal arrow that spans empty column slots.

**Fix:** for each node that is the *terminal step* of a branch (its only successor is a join with ≥ 2 incoming edges), snap its column to `join_col − 1` when it currently sits further left.

Safety conditions that must all hold before a node is moved:
- Exactly one successor (the join) — so moving right cannot conflict with other downstream nodes
- Current column strictly less than `join_col − 1`
- The new column stays strictly greater than `max(col[predecessor])` — topological order preserved

This turns long diagonal arrows into single-column hops without affecting any other layout logic.

### Waypoint routing

`_build_di` emits waypoints for every sequence flow:
- **Normal flow** (forward, no overlap): right-centre → left-centre (2 points)
- **Stacked elements** (same column, x-ranges overlap): bottom-centre → top-centre (2 points)
- **Backward flow** (source column > target column, same lane): U-path with 4 waypoints below elements: `source_right → source_below → target_below → target_left`. The horizontal segment is routed 25 px below the tallest element in the path, within the empty lower portion of the lane.

### Post-extraction rule enforcement (`_enforce_rules`)

Applied in `agent_bpmn.py` after LLM extraction, before generators. Mutates the model in-place.
Receives `nlp_actors` from `hub.nlp.actors` to improve lane inference.

- **Rule 0** — removes steps the LLM declared as `startEvent`/`endEvent` (generator adds these)
- **Rule 1** — `serviceTask` with unnamed system actor → `lane = None` (OMG §7.4)
- **Rule 1b** — generic lane names (`usuário`, `validador`, `sistema`…) → infers real organizational name using three-priority lookup: (1) step `actor` fields for that lane, (2) NLP actors appearing in step texts, (3) regex over step descriptions
- **Rule 2** — correction loop pointing back to **any gateway type** (`exclusiveGateway`, `parallelGateway`, `inclusiveGateway`, `eventBasedGateway`, `complexGateway`) → redirected to the upstream work step that feeds the gateway

### Rules the LLM must follow (enforced by `skill_bpmn.md`)

- The LLM **must not declare** Link Intermediate Events — the generator handles them.
- Start/End Event lane assignment follows the direct predecessor/successor.
- System lanes must not receive Start/End Events.
- Lane ordering: primary initiating actor at the top.
- End Event inherits the lane of its direct predecessor (Rule 8).
- Lane names must be organizational units, never generic roles (`usuário`, `sistema`, etc.).

---

## Mermaid Generator (`agents/agent_mermaid.py`)

`MermaidGenerator` is a pure-Python class (no LLM) that converts a `BPMNModel` to Mermaid flowchart syntax:

- `sanitize_text(text)` — replaces accented chars, removes Mermaid-breaking punctuation
- `format_node(step)` — `{}` for decisions, `[]` for tasks; always uses quoted labels
- `format_edge(edge)` — pipe syntax `-->|label|` for labeled edges
- `generate(model)` — `flowchart LR` with decision node styling

**Entry point:** `generate_mermaid(model: BPMNModel) -> str` (module-level convenience function).

---

## BPMN Viewer (`modules/bpmn_viewer.py`)

- Rendered via `streamlit.components.v1.html` with **bpmn-js 17** injected inline (no external CDN).
- Toolbar positioned top-right (light theme).
- `MutationObserver` triggers auto-fit when the SVG is inserted into the DOM.
- `getBoundingClientRect()` returns zero before paint — use `fitWhenReady` polling loop.

---

## Mermaid Renderer (`modules/mermaid_renderer.py`)

Shared rendering utility used by both `app.py` tabs and `pages/Diagramas.py`.

`render_mermaid_block(mermaid_text, *, show_code, key_suffix, height)`:
- Fetches both TD and LR SVGs **server-side** from `mermaid.ink/svg/{base64}` — no external CDN inside the iframe.
- Injects both SVGs inline; client-side JS toggles between them (no Streamlit rerun).
- Pan/zoom/fit with mouse drag and scroll wheel.
- For non-flowchart diagrams (mindmap, etc.) the direction toggle is hidden.
- `robustFit` polling handles SVG dimension timing.

**Why no CDN in the iframe?**
Streamlit Cloud sandbox blocks external script loading inside `components.html`.
All JS dependencies must be resolved server-side or injected inline.

---

## Requirements Mind Map

Two modules cooperate:

- `modules/requirements_mindmap.py` — `generate_requirements_mindmap(model)` → Mermaid mindmap string; `build_mindmap_tree(model)` → hierarchical dict for the interactive renderer.
- `modules/mindmap_interactive.py` — `render_mindmap_from_requirements(model, *, session_title, height)` — renders an interactive SVG mind map (pure JS, pan/zoom, collapse/expand per type group). Falls back to Mermaid code block if tree is empty.

Hierarchy: `root((Process Name)) → Type group → REQ-ID — Title (priority dot)`.

The `pages/Diagramas.py` page also renders this mind map under a "🗺️ Mind Map" tab.

---

## Multi-Page App (`pages/Diagramas.py`)

Streamlit multi-page app — accessible via sidebar navigation or `st.page_link`.

- Shares `st.session_state["hub"]` with `app.py` — no re-processing needed.
- Calls `KnowledgeHub.migrate(hub)` for schema compatibility.
- Renders three tabs dynamically (only if data is available): **BPMN 2.0** (bpmn-js, 900px), **Mermaid** (render_mermaid_block, 820px), **Mind Map** (interactive, 840px).
- Page config: `layout="wide"`, `initial_sidebar_state="collapsed"`.

---

## RAG Assistant (`pages/Assistente.py`)

Semantic Q&A over meeting transcripts stored in Supabase. Two modes, selectable via "🔧 Modo Ferramentas" sidebar toggle (`asst_use_tools`, default `True`).

### Architecture — Modo A: Tool-use (padrão)

```
User question + History
        │
        ▼
AgentAssistant.chat_with_tools(history, question, project_id)
        │
        ├── _build_system_prompt_tools()
        │       retrieve_data_summary(project_id)      ← compact project overview
        │       skill_assistant.md                     ← P2D guide
        │
        └── LLM (tool_choice="auto")
                │
                ▼  [loop ≤ MAX_TOOL_ROUNDS = 5]
           ┌────────────────────────────────────────────────┐
           │  Tool calls from LLM                           │
           │  AssistantToolExecutor.execute(name, args)     │
           │                                                │
           │  get_meeting_list()                            │
           │  get_meeting_participants(meeting_number)      │
           │  get_meeting_decisions(meeting_number)         │
           │  get_meeting_action_items(meeting_number)      │
           │  get_meeting_summary(meeting_number)           │
           │  search_transcript(query, meeting_number?)     │
           │  get_requirements(keyword?, req_type?, status?)│
           │  list_bpmn_processes()                         │
           │  get_sbvr_terms(keyword?)                      │
           │  get_sbvr_rules(keyword?)                      │
           │         │                                      │
           │         └─► direct Supabase queries            │
           │             meetings · requirements ·          │
           │             bpmn_processes · sbvr_*            │
           └────────────────────────────────────────────────┘
                │
                ▼  stop_reason = "end_turn" / "stop"
           Final answer → chat UI
```

**Tool schemas** live in `core/assistant_tools.py` in two formats:
- `get_tool_schemas_openai()` — OpenAI/DeepSeek/Groq function-calling format
- `get_tool_schemas_anthropic()` — Anthropic `tool_use` format (derived from OpenAI schemas)

**Message format differences:**
- OpenAI: `finish_reason == "tool_calls"` → tool results as `{"role": "tool", "tool_call_id": id, "content": text}`
- Anthropic: `stop_reason == "tool_use"` → assistant turn appends full `content` list; tool results as `{"role": "user", "content": [{"type": "tool_result", "tool_use_id": id, "content": text}]}`

**Fallback:** any exception in `chat_with_tools()` → automatically falls back to Mode B with keyword search.

### Architecture — Modo B: RAG Clássico (fallback / opt-out)

```
User question
      │
      ├── Keyword search  ──► retrieve_context_for_question(project_id, query)
      │                       ILIKE match on transcripts + minutes_md injection
      │
      └── Semantic search ──► embed_text(query, api_key, "Google Gemini")
                               └─► search_transcript_chunks(project_id, embedding, k=8)
                                   match_transcript_chunks() SQL (cosine similarity)
                                          │
                                          ▼
                              Retrieved chunks + minutes summaries
                                          │
                                          ▼
                              AgentAssistant.chat()
                              system: P2D guide + format_context() RAG string
                              user:   question
                                          │
                                          ▼
                              Answer displayed in chat UI
```

### Re-edit feature

Users can edit a previous question via the `✏️` button on any user message:
- `st.session_state["_edit_idx"]` — index of the message being edited
- `st.session_state["_edit_draft"]` — current draft text
- `st.session_state["_resubmit_question"]` — populated on "🔄 Reenviar", consumed on next rerun
- On resubmit: history is truncated to `history[:_edit_idx]`; `chat_input` is disabled while editing

### Embedding pipeline

- Chunks created by `chunk_text(transcript, chunk_size=500, overlap=80)`
- Each chunk embedded via `embed_text(chunk, api_key, provider)`
- Embeddings stored in `transcript_chunks` table (`vector(1536)`)
- `save_transcript_embeddings(meeting_id, project_id, chunks, embeddings)` — upserts by `(meeting_id, chunk_index)`
- Provider: **Google Gemini** (`models/gemini-embedding-001`, `output_dimensionality=1536`) — free tier; 1.2s delay between calls; auto-retry on 429
- Fallback model: `models/gemini-embedding-2-preview` (tried if 404 on primary)
- Diagnostic: "🔍 Testar chave" button calls `list_gemini_embedding_models(api_key)` to list available models

### Error handling

Errors and success messages from the embedding generation flow are persisted in `st.session_state["_embed_error"]` / `["_embed_success"]` before `st.rerun()` and displayed+popped immediately after rerun — prevents the instant-disappear bug caused by `st.error()` before `st.rerun()`.

---

## UI Package (`ui/`)

All Streamlit UI code lives in `ui/` — `app.py` only coordinates flow.

### `ui/sidebar.py` — `render_sidebar()`
- Provider selector + API key gate
- Output language selector
- Prefix/suffix for file naming
- Agent enable/disable checkboxes (Quality, BPMN, Minutes, Requirements, SBVR, BMM, Executive Report)
- BPMN optimization passes slider (1/3/5) + weight sliders (only when n > 1)
- **🔄 Adaptive Retry (LangGraph)** checkbox + Quality Threshold slider + Max Retries selector (only when n_bpmn_runs == 1)
- Developer Mode toggle (shows Dev Tools tab + Raw JSON option)
- Re-run buttons for all agents (appear after first pipeline run)

### `ui/input_area.py` — `render_input_area()`
- `st.text_area` for pasting transcript
- File uploader (`.txt`, `.docx`, `.pdf`) via `services/file_ingest.py`
- "Pre-process" button (no LLM) — shows side-by-side original vs. cleaned with stats
- Editable cleaned text area (`curated_clean`) — "Use curated text" button sets it as main input
- Returns `True` when "🚀 Generate Insights" is clicked

### `ui/architecture_diagram.py` — `render_architecture_diagram()`
- Displays a `flowchart TD` Mermaid architecture diagram as a splash section at app startup.
- SVG fetched once from mermaid.ink via `@st.cache_data` — zero network overhead on reruns.
- Pan/zoom/fit viewer injected via `components.html`. No external CDN inside the iframe.
- Shown in `st.expander` that starts **expanded** when no pipeline results exist yet (`"hub"` not in session state) and collapsed automatically afterwards — no UX friction for repeat users.
- `ARCHITECTURE_DIAGRAM` constant: `flowchart TD` with nested subgraphs, `classDef` palette matching brand colours (navy=input, amber=LLM, blue=core agents, purple=optional, green=outputs).

### `ui/tabs/`
Each tab is a standalone module with a `render(hub, prefix, suffix)` function (or variant):
- `bpmn_tabs.py` — `render_bpmn()` (structural diagnostics + auto-repair log + LangGraph badge), `render_mermaid()`, `render_validation()`
- `quality_tab.py`, `minutes_tab.py`, `requirements_tab.py`, `synthesizer_tab.py`
- `sbvr_tab.py` — vocabulary dataframe (term/category/definition) + rules list with type badges + JSON export
- `bmm_tab.py` — vision/mission columns + goals/strategies expanders with type badges + policies list
- `export_tab.py` — all download buttons (BPMN XML, Mermaid, Minutes MD/DOCX/PDF, Requirements MD/JSON, SBVR JSON, BMM JSON, Executive HTML)
- `dev_tools_tab.py` — KnowledgeHub metadata + optional raw JSON + Hub JSON download

---

## Services Package (`services/`)

Thin wrappers that decouple `ui/` from `modules/`:

- `export_service.make_filename(base, ext, prefix, suffix) → str` — e.g. `P2D_process_2026-04-04.bpmn`
- `file_ingest.load_transcript(uploaded_file)` — delegates to `modules/ingest.py`
- `preprocessor_service.preprocess_transcript(text)` — delegates to `modules/transcript_preprocessor.preprocess()`

---

## Core Modules (`core/`)

- `session_state.init_session_state()` — idempotent initialization of all `st.session_state` keys. Must be called immediately after `st.set_page_config()`. Defaults: provider=DeepSeek, run_quality/bpmn/minutes/requirements=True, run_sbvr/bmm/synthesizer=False, n_bpmn_runs=1, use_langgraph=False, validation_threshold=6.0, max_bpmn_retries=3.
- `pipeline.run_pipeline(hub, config, progress_callback)` — single entry point for pipeline execution. Three paths: (1) multi-run tournament (`n_bpmn_runs > 1`), (2) LangGraph adaptive retry (`use_langgraph=True`), (3) standard single-run. Raises on error (caller catches).
- `lg_pipeline.LGBPMNRunner` — LangGraph `StateGraph` with BPMN→validate→(retry|proceed) loop. `@st.cache_data` not used here; graph is compiled per run instance. `hub.bpmn.lg_attempts` and `hub.bpmn.lg_final_score` written after completion.
- `rerun_handlers.handle_rerun(agent_name, hub, client_info, provider_cfg, output_language)` — re-executes one named agent (`"quality"`, `"bpmn"`, `"minutes"`, `"requirements"`, `"sbvr"`, `"bmm"`, `"synthesizer"`). When BPMN is re-run, invalidates `hub.synthesizer`.
- `project_store` — Supabase CRUD for projects, meetings, requirements, and transcript embeddings. Functions: `list_projects()`, `list_meetings(project_id)`, `save_transcript_embeddings(meeting_id, project_id, chunks, embeddings)`, `search_transcript_chunks(project_id, query_embedding, match_count)`. Fail-open: returns `[]`/`None` when Supabase is unconfigured.
- `batch_pipeline.run_batch(transcripts, config, callback)` — runs the full pipeline on a list of transcripts sequentially, accumulating results.

---

## Executive HTML Report (`modules/executive_html.py`)

Generated by `AgentSynthesizer` → `generate_executive_html(hub, narrative) → str`.

- **Self-contained HTML** — Google Fonts via CDN (works in browser download), no other external deps.
- **Sidebar nav** — `data-target` + JS `scrollIntoView` (never `href="#id"` which navigates the Streamlit parent frame).
- **Sections built from hub (in order):**
  1. Sumário Executivo (LLM narrative)
  2. Visão do Processo (LLM narrative + BPMN stats)
  3. Diagrama BPMN (iframe srcdoc with bpmn-js)
  4. Fluxograma Mermaid (SVG fetched server-side from mermaid.ink)
  5. Ata de Reunião (decisions, action items with localStorage status)
  6. Especificação de Requisitos (filterable table by type + priority)
  7. **Vocabulário e Regras de Negócio (SBVR)** — two-column: vocabulary table + rules list with type badges (shown only when `hub.sbvr.ready`)
  8. **Modelo de Motivação do Negócio (BMM)** — vision/mission banner + goals + strategies with goal links + policies (shown only when `hub.bmm.ready`)
  9. Qualidade da Transcrição (grade badge + criteria progress bars)
  10. Insights e Recomendações (LLM key_insights + recommendations)
- **Stats bar** includes SBVR term/rule counts and BMM goal count when available.
- **Interactive features:** collapsible cards, action item status (localStorage `p2d_ai_{session_id}`), requirements filter by type + priority, comments per action item (localStorage `p2d_cmt_{session_id}`).
- **Visibility:** cards default to `opacity:1`; animation (`.will-animate`) added only via JS when IntersectionObserver is supported and viewport > 300 px — prevents blank content inside Streamlit iframe.
- **Displayed in app** via `components.html(syn.html, height=900, scrolling=True)` and downloadable as `.html`.

---

## Minutes Export (`modules/minutes_exporter.py`)

`to_docx(minutes: MinutesModel) -> bytes` — uses `python-docx`:
- Navy title (20pt bold), accent underline section headings, List Bullet/Number styles.
- Action items table with navy header row, 10pt body text.

`to_pdf(minutes: MinutesModel) -> bytes` — uses `fpdf2` (pure Python, no GTK):
- Navy fill title block, accent section headers, two-column participants, alternating-row action items table with priority colors.

Both return raw bytes ready for `st.download_button`.

---

## Streamlit Session State

**Critical issue:** clicking any `st.download_button` triggers a full app rerun, wiping any local variable.

**Required pattern:**

```python
# app.py — correct pattern
if generate_btn:
    hub = run_pipeline(hub, config, callback)
    st.session_state["hub"] = hub   # ← store BEFORE rendering any widget

# Render block lives OUTSIDE the if block
if "hub" in st.session_state:
    hub = st.session_state["hub"]
    # render tabs, download buttons, viewers...
```

**Rule:** any state that must survive reruns (hub, generated outputs) must be written to `st.session_state` before the first widget that could trigger a rerun.

**Re-run pattern:** sidebar/body buttons write `st.session_state.rerun_agent = "bpmn"`. On next Streamlit run, `handle_rerun()` picks it up via `st.session_state.pop("rerun_agent")` and re-executes the agent.

---

## Mermaid Syntax Constraints

- Decision nodes: `{}` — not `{{}}`.
- No quoted labels inside `{}` braces.
- Avoid reserved words as node IDs: `END`, `START`, `default`.
- Non-ASCII characters in subgraph IDs must be normalized before use.
- Mermaid **version 10** is in use.

---

## Dependencies

```
streamlit==1.42.0
anthropic==0.49.0
openai==1.65.0
python-docx==1.1.2          # Word export (pure Python)
fpdf2==2.8.2                # PDF export (pure Python, no GTK)
google-generativeai>=0.8.0  # list_models() diagnostic + embed_content() for embeddings
google-genai>=1.0.0         # newer Google GenAI SDK (kept for future migration)
supabase>=2.4.0             # Supabase Python client
langgraph>=1.0              # LangGraph BPMN adaptive retry
```

Always pin exact versions for Streamlit Cloud reproducibility.
When adding a new dependency, append it with a pinned version — no version ranges.

---

## Deploy Flow

```
Local edit (PyCharm / Windows)
        │
        ▼
git add . && git commit -m "description"
        │
        ▼
git push origin main
        │
        ▼
Streamlit Cloud detects push → automatic rebuild
```

**Warning:** the GitHub web editor corrupts complex files during copy/paste.
Always push programmatically via terminal or PyCharm — never edit multi-hundred-line files in the GitHub UI.

---

## Extending the System

### Adding a new LLM provider

Edit `modules/config.py` — add an entry to `AVAILABLE_PROVIDERS`:

```python
"Provider Name": {
    "default_model": "model-id",
    "base_url": "https://api.example.com/v1",  # None for Anthropic native SDK
    "client_type": "openai_compatible",         # or "anthropic"
    "supports_json_mode": True,
    "supports_system_prompt": True,
    "api_key_label": "...",
    "api_key_help": "...",
    "api_key_prefix": "...",
    "cost_hint": "...",
}
```

If `client_type` is new, add a routing branch in `BaseAgent._call_llm()`.

### Adding a new diagram format

1. Create `modules/diagram_newformat.py` → `generate_newformat(bpmn: BPMNModel) -> str`
2. Add field to `BPMNModel` in `core/knowledge_hub.py`
3. Call generator in `agents/agent_bpmn.py` after JSON extraction
4. Add tab module in `ui/tabs/` and register in `ui/tabs/__init__.py`
5. Add tab to the dynamic tab list in `app.py`

### Adding a new agent

1. Create `agents/agent_new.py` inheriting from `BaseAgent`
2. Implement `build_prompt(hub)` and `run(hub)`
3. Create `skills/skill_new.md` with the system prompt — **use lowercase filename**
4. Run `git ls-files skills/` to confirm the exact tracked name, then set `skill_path` to match
5. Add field to `KnowledgeHub` in `core/knowledge_hub.py`
6. Add migrate guard in `KnowledgeHub.migrate()` for the new field
7. Register in `agents/orchestrator.py → _PLAN` list and `run()` parameters
8. Add checkbox in `ui/sidebar.py`
9. Add to `core/rerun_handlers.py` if individual re-run is desired
10. Create tab module in `ui/tabs/` and register in `ui/tabs/__init__.py`

### Modifying BPMN layout

- Coordinates are absolute — no direction parameter exists.
- Layout changes affect the constants at the top of `bpmn_generator.py`: `TASK_W`, `H_GAP`, `V_PAD`.
- After layout changes, always verify the crossing-elimination heuristic still behaves correctly.

---

## Known Pitfalls

### Skill file case sensitivity (Linux)

Streamlit Cloud runs on Linux (case-sensitive filesystem). A `skill_path` that works on Windows
(case-insensitive) may silently fail on Linux if the case doesn't match the git-tracked name.

**Diagnosis:** open Knowledge Hub tab → Skills section or Diagnóstico expander.
**Fix:** always verify with `git ls-files skills/` and match exactly.
**Rule:** `_load_skill()` uses `Path(__file__).parent.parent / skill_path` — never CWD-relative.

### Stale `.pyc` cache on Streamlit Cloud

When a new symbol is added to an existing module, a stale cached `.pyc` on the server may not
include it, causing `ImportError`. Use belt-and-suspenders guards in `app.py`:

```python
if not hasattr(hub, 'new_field'):
    try:
        from core.knowledge_hub import NewModel
        hub.new_field = NewModel()
    except ImportError:
        hub.new_field = <inline fallback>
```

### Streamlit sidebar `href="#id"` navigates parent frame

Inside `components.html()`, anchor links with `href="#section-id"` navigate the **parent** Streamlit
frame, not the iframe. Use `data-target` + JS `scrollIntoView` instead:

```html
<a data-target="sec-foo" href="javascript:void(0)">...</a>
<script>
  document.querySelectorAll('.sb-link[data-target]').forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      document.getElementById(link.dataset.target)?.scrollIntoView({behavior:'smooth'});
    });
  });
</script>
```

### Pages import path on Streamlit Cloud

`pages/Diagramas.py` adds the project root to `sys.path` manually:

```python
root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
```

This is required because Streamlit multi-page apps run page files in a different working directory context.

### Gemini embedding model availability per API key

Not all `text-embedding-*` models are available to every AI Studio key. The model namespace varies silently — `text-embedding-004` may return 404 even though Google documentation mentions it. Use the diagnostic button "🔍 Testar chave" in `pages/Assistente.py` which calls `list_gemini_embedding_models(api_key)` to enumerate models that actually respond to `embedContent` for the provided key.

**Confirmed working models (for keys that don't have text-embedding-004):**
- `models/gemini-embedding-001` — 1536 dims via `output_dimensionality=1536` (primary)
- `models/gemini-embedding-2-preview` — fallback

`_embed_gemini()` tries `gemini-embedding-001` first and falls back to `gemini-embedding-2-preview` on 404.

### Gemini embedding rate limits (free tier: 100 req/min)

The free AI Studio tier allows 100 requests/minute for `gemini-embedding-1.0`. With one API call per chunk, large transcripts easily exceed this.

**Mitigations in `modules/embeddings.py`:**
- `_GEMINI_RATE_DELAY = 1.2` seconds between batch calls (~50 req/min sustained)
- `_GEMINI_MAX_RETRIES = 5` automatic retries on 429
- Retry wait extracts `retry_delay { seconds: N }` from the error body via regex (`r"seconds[\"':\s]+(\d+)"`) and adds a 10-second buffer

### pgvector dimension limit (ivfflat ≤ 2000 dims)

PostgreSQL `ivfflat` index cannot handle vectors with more than 2000 dimensions. `gemini-embedding-001` natively produces 3072 dims. Always use `output_dimensionality=1536` when calling the Gemini embedding API, and create the Supabase column as `vector(1536)`. The SQL schema is in `setup/supabase_schema_transcript_chunks.sql`.

### Login page HTML rendered as code block

In `ui/auth_gate.py`, HTML injected via `st.markdown(unsafe_allow_html=True)` **must not be indented ≥ 4 spaces after a blank line** — Markdown treats that as a code fence and shows raw HTML. Keep the f-string HTML at zero indentation. Extract labels (`<div class="l-label">`) to separate `st.markdown` calls to avoid the blank-line-from-empty-interpolation trap.

### st.error() / st.success() disappear before st.rerun()

Any `st.error()` or `st.success()` call made immediately before `st.rerun()` is never rendered. The widget is drawn but the rerun clears it before the browser paints.

**Pattern:** persist the message in `st.session_state` before rerunning; pop and display it after the rerun:
```python
st.session_state["_embed_error"] = "❌ Falha ao gerar embeddings: ..."
st.rerun()
# --- next run ---
if "_embed_error" in st.session_state:
    st.error(st.session_state.pop("_embed_error"))
```

---

## Security Model

API keys are stored exclusively in `st.session_state` (server-side, per-session memory in Streamlit). They are never logged, written to disk, or persisted across sessions.

- `session_security.render_api_key_gate(provider)` — renders the key input in the sidebar
- `session_security.get_session_llm_client(provider)` — retrieves the live client or `None`

### Login Gate

All pages begin with `ui.auth_gate.apply_auth_gate()` immediately after `st.set_page_config()`. If the user is not authenticated, `render_login_page()` is called and `st.stop()` prevents the rest of the page from rendering.

- Credentials are SHA-256 hashed in `modules/auth.py → USUARIOS` (hardcoded — no `secrets.toml` dependency)
- Session state keys: `_autenticado` (bool), `_usuario_login` (str), `_usuario_nome` (str)
- `is_authenticated()` checks `st.session_state.get("_autenticado", False)`
- `login_valido(uname, senha)` hashes the input with SHA-256 and compares against stored hash
- Login page HTML pitfall: any content indented ≥ 4 spaces after a blank line inside an `st.markdown(unsafe_allow_html=True)` block is rendered as a Markdown code block — keep HTML zero-indented in the f-string.

### Supabase Secrets

`modules/supabase_client.py` reads `st.secrets["supabase"]["url"]` and `st.secrets["supabase"]["key"]`. If secrets are absent (local dev without `.streamlit/secrets.toml`), `get_supabase_client()` returns `None` and all `project_store` functions fail-open.

---

## Roadmap

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
- [x] **`pages/Assistente.py`** — RAG-powered Q&A over meeting transcripts; keyword search + semantic search via `match_transcript_chunks`; embedding generation with "⚡ Gerar Embeddings" + "🔍 Testar chave" diagnostic; errors persisted in `session_state` to survive `st.rerun()`; re-edit feature (✏️ button, history truncation, `_resubmit_question` pattern)
- [x] **Tool-use mode** — `core/assistant_tools.py`; `AssistantToolExecutor` with 10 tools mapping to direct Supabase queries; `get_tool_schemas_openai()` + `get_tool_schemas_anthropic()`; `AgentAssistant.chat_with_tools()` with ≤5-round loop; automatic fallback to classic RAG on exception; `asst_use_tools` sidebar toggle (default `True`); tools called shown in response caption
- [x] **RAG quality improvement** — `project_store._extract_minutes_summary()` extracts Participantes/Pauta/Decisões from `minutes_md`; injected unconditionally in `format_context()` for all meetings regardless of transcript availability
- [x] **`pages/BatchRunner.py`** — batch pipeline over multiple transcripts via `core/batch_pipeline.py`
- [x] **`pages/BpmnBackfill.py`** — retroactive BPMN generation for meetings already stored in Supabase
- [x] **`pages/ReqTracker.py`** — requirement status board backed by Supabase
- [x] **`pages/TranscriptBackfill.py`** — retroactive embedding generation for meetings already in Supabase
- [x] **`pages/CostEstimator.py`** — interactive LLM cost calculator using `modules/cost_estimator.py` pricing table
- [x] **`ui/project_selector.py`** — Supabase project/meeting picker widget shared by Assistente and ReqTracker
- [x] **`ui/assistant_diagram.py`** — RAG architecture splash diagram (Mermaid, cached SVG) for Assistente page
- [x] **`modules/cost_estimator.py`** — `PROVIDER_PRICING` table + `estimate_cost()` — pure Python, no LLM calls
- [x] **`modules/text_utils.py`** — `rule_keyword_pt()` and other Portuguese text utilities
- [x] **`modules/reqtracker_exporter.py`** — Excel/CSV export for ReqTracker
- [x] **Google Gemini SDK migration** — use `google-generativeai` (stable) for `embed_content()` + `list_models()`; `google-genai` kept as secondary dependency

---

## Technical References

| Resource | Location |
|---|---|
| BPMN 2.0 Spec (OMG) | ISO/IEC 19510 / OMG formal/2013-12-09 |
| bpmn-js | github.com/bpmn-io/bpmn-js (v17) |
| mermaid.ink SVG endpoint | mermaid.ink |
| Streamlit session state | docs.streamlit.io/library/api-reference/session-state |
| Streamlit multi-page apps | docs.streamlit.io/library/advanced-features/multipage-apps |
| python-docx | python-docx.readthedocs.io |
| fpdf2 | py-pdf.github.io/fpdf2 |
| pgvector | github.com/pgvector/pgvector — ivfflat index, max 2000 dims |
| google-generativeai | pypi.org/project/google-generativeai — embed_content(), list_models() |
| Supabase Python client | supabase.com/docs/reference/python |
