# Architecture Details — Process2Diagram

Detalhes técnicos de implementação para referência pontual. Consulte ao modificar os módulos listados.

---

## BPMN Generator — Internals (`modules/bpmn_generator.py`)

### Column layout algorithm

`_assign_columns(steps, edges)` — topological sort + BFS:
1. Nodes with no predecessors → column 0
2. Each node's column = `max(col[predecessors]) + 1`
3. Backward edges (cycles) ignored during column assignment

### Parallel branch alignment (`_align_parallel_branches`)

Post-pass called immediately after `_assign_columns` in `_compute_layout`.

**Problem:** split gateway with branches of unequal length → shorter branch finishes early → long diagonal arrow spanning empty columns.

**Fix:** for each node that is terminal step of a branch (only successor = a join with ≥ 2 incoming edges), snap column to `join_col − 1` if currently sitting further left.

Safety conditions (all must hold before moving):
- Exactly one successor (the join)
- Current column strictly less than `join_col − 1`
- New column strictly greater than `max(col[predecessor])` — topological order preserved

### Waypoint routing (`_build_di`)

Emits waypoints for every sequence flow:
- **Normal flow** (forward, no overlap): right-centre → left-centre (2 points)
- **Stacked elements** (same column, x-ranges overlap): bottom-centre → top-centre (2 points)
- **Backward flow** (source column > target column, same lane): U-path with 4 waypoints below elements:
  `source_right → source_below → target_below → target_left`
  Horizontal segment routed 25 px below tallest element in path, within the empty lower portion of the lane.

### Lane-crossing elimination

Single-pass algorithm:
1. Column layout assigns `(x, y, w, h)` to all elements
2. Flows with source/target separated by ≥ 2 lane boundaries → flagged
3. Adjacent-lane flows (span = 1) left as direct arrows — bpmn-js routes natively
4. Flagged flows → replaced with throw/catch Intermediate Link Events

### Layout constants

```python
TASK_W = 120
TASK_H = 60
GW_W = 50       # gateway diamond width
H_GAP = 70      # horizontal gap between columns
LANE_HEADER_W = 100
V_PAD = 20      # vertical padding within lane
```

`BPMNPlane` must reference `collab_id` (not `process_id`) when a collaboration element exists.

---

## BPMN Viewer — Implementation Notes (`modules/bpmn_viewer.py`)

- bpmn-js JS (~1.2 MB) + CSS fetched server-side via `urllib.request` on first call, cached with `@functools.lru_cache(maxsize=None)`, inlined as `<style>`/`<script>` blocks.
- Why no CDN: Streamlit Cloud sandbox blocks external `<script src>` in `components.html()` iframes.
- `canvas.zoom('fit-viewport')` deferred via `setTimeout(fn, 150)` — synchronous call fires before browser has computed container dimensions, producing `SVGMatrix non-finite` error.
- Zoom label synced via `viewer.get('eventBus').on('canvas.viewbox.changed', refreshLabel)`.
- `_TEMPLATE_CDN_FALLBACK` used when server-side fetch fails.
- Public API: `preview_from_xml(xml: str) -> str`, `generate_bpmn_preview(bpmn: BpmnProcess) -> str`.

---

## Mermaid Renderer — Implementation Notes (`modules/mermaid_renderer.py`)

`render_mermaid_block(mermaid_text, *, show_code, key_suffix, height)`:
- Fetches TD and LR SVGs server-side from `mermaid.ink/svg/{base64}` — no external CDN in iframe.
- Both SVGs injected inline; client-side JS toggles between them (no Streamlit rerun).
- `robustFit` polling handles SVG dimension timing (SVG may report zero dimensions at DOMContentLoaded).
- Direction toggle hidden for non-flowchart diagrams (mindmap, etc.).
- Pan/zoom/fit: mouse drag + scroll wheel.

---

## RAG Assistant — Architecture Details (`pages/Assistente.py`)

### Mode A: Tool-use — Full flow

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
                ▼  [loop ≤ MAX_TOOL_ROUNDS = 8]
           ┌─────────────────────────────────────────────┐
           │  Tool calls from LLM                        │
           │  AssistantToolExecutor.execute(name, args)  │
           │  ─── admin gate ──────────────────────────  │
           │  Non-admin tools:                           │
           │    get_meeting_list()                       │
           │    get_meeting_participants(meeting_number) │
           │    get_meeting_decisions(meeting_number)    │
           │    get_meeting_action_items(meeting_number) │
           │    get_meeting_summary(meeting_number)      │
           │    search_transcript(query, meeting_number?)│
           │    get_requirements(keyword?, req_type?, …) │
           │    list_bpmn_processes()                    │
           │    get_sbvr_terms(keyword?)                 │
           │    get_sbvr_rules(keyword?)                 │
           │  Admin-only tools:                          │
           │    get_database_integrity()                 │
           │    fix_missing_llm_provider(provider)       │
           │    generate_meeting_embeddings(api_key, …)  │
           │    reprocess_meeting_full(meeting_id)       │
           │    calendar_* (8 tools)                     │
           │    set_active_project(name)                 │
           └─────────────────────────────────────────────┘
                │
                ▼  stop_reason = "end_turn" / "stop"
           Final answer → chat UI
```

**Message format differences:**
- OpenAI: `finish_reason == "tool_calls"` → results as `{"role": "tool", "tool_call_id": id, "content": text}`
- Anthropic: `stop_reason == "tool_use"` → assistant turn appends full `content` list; results as `{"role": "user", "content": [{"type": "tool_result", "tool_use_id": id, "content": text}]}`

### Mode B: RAG Clássico — Full flow

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

- `st.session_state["_edit_idx"]` — index of message being edited
- `st.session_state["_edit_draft"]` — current draft text
- `st.session_state["_resubmit_question"]` — populated on "🔄 Reenviar", consumed on next rerun
- On resubmit: history truncated to `history[:_edit_idx]`; `chat_input` disabled while editing

### Embedding management UI

Lives in **Banco de Dados → aba 🔮 Embeddings**:
- Coverage table per project
- Batch generation with progress bar (all meetings in selected project)
- Per-meeting drill-down: normalization preview, chunk count, individual "🔄 Gerar" button
- "🧪 Testar gravação no banco" — INSERT/SELECT/DELETE probe without embedding API call

Error/success messages persisted in `st.session_state` before `st.rerun()`. Keys: `_emb_tab_result`, `_emb_tab_single_result`, `_emb_tab_err_{meeting_id}`.

---

## ROI-TR — Formulas and Type Weights

### Formulas

```
DC_ponderado = n_dec×w[dec] + n_act_done×w[act] + n_reqs×w[req] + n_sbvr×w[sbvr] + min(1,n_bpmn)×w[bpmn]
fulfillment  = min(1.0, DC_ponderado / min_dc)
ROI-TR       = min(10, DC_ponderado × 1000 / (n_part × dur_h × custo_h) × 1.5)
TRC          = min(100, (n_cycle_signals / (word_count / 500)) × 20)
```

`fulfillment` is a separate display metric — does not multiply into ROI-TR.

### TYPE_WEIGHTS examples

```python
"Tomada de Decisão":         {"req": 0.5, "dec": 3.0, "act": 2.0, "sbvr": 0.0, "bpmn": 0.0, "min_dc": 6.0}
"Levantamento de Requisitos":{"req": 3.0, "dec": 1.0, "act": 1.5, "sbvr": 2.0, "bpmn": 1.0, "min_dc": 4.5}
```

11 types total in `MEETING_TYPES`. `classify_meeting_type()`: LLM path → 1 call, JSON `{"type": str, "confidence": float}`; heuristic fallback → keyword matching + artefact counts → `"Híbrida"` (confidence 0.30).

`compute_project_roi()` catches `Exception` on `meeting_type` select (column may not exist) and retries without it — safe before SQL migration.

---

## Orchestrator — Parallel Execution Details

`Orchestrator._run_minutes_requirements_parallel()` via `ThreadPoolExecutor(max_workers=2)`:

- Each worker receives `copy.copy(hub)` with `meta = copy.copy(hub.meta)` and `meta.agents_run = list(...)`
- Minutes and Requirements each write only to their own hub section — no shared writes
- Both copies start from `tokens_base = hub.meta.total_tokens_used`
- After join: `hub.meta.total_tokens_used += delta_m + delta_r`
- `Orchestrator._progress(name, status)` acquires `threading.Lock()` before calling callback
- Falls back to sequential on any `ThreadPoolExecutor` exception, with `(sequencial)` label

Why `ThreadPoolExecutor` not `asyncio`: Streamlit's synchronous run model is incompatible with `asyncio.gather()`.

---

## AgentValidator — Scoring Details

`agents/agent_validator.py` — no LLM. Scores a `BPMNModel` on three dimensions (each 0–10):

- **Granularity** — activity count vs transcript word count (target: 1 task per 40–100 words)
- **Task type** — specificity of `task_type` assignments vs keyword heuristics
- **Gateways** — XOR edges labeled; AND/OR gateways have matching join

Weighted via `bpmn_weights = {"granularity": int, "task_type": int, "gateways": int}` (configurable in sidebar). Best candidate → `hub.bpmn`; all scores → `hub.validation`.

---

## Executive HTML Report — Section List

Generated by `AgentSynthesizer` → `generate_executive_html(hub, narrative) → str`.

Sections in order:
1. Sumário Executivo (LLM narrative)
2. Visão do Processo (LLM narrative + BPMN stats)
3. Diagrama BPMN (iframe srcdoc with bpmn-js)
4. Fluxograma Mermaid (SVG fetched server-side from mermaid.ink)
5. Ata de Reunião (decisions, action items with localStorage status)
6. Especificação de Requisitos (filterable table by type + priority)
7. Vocabulário e Regras de Negócio SBVR (shown only when `hub.sbvr.ready`)
8. Modelo de Motivação do Negócio BMM (shown only when `hub.bmm.ready`)
9. Qualidade da Transcrição (grade badge + criteria progress bars)
10. Insights e Recomendações (LLM key_insights + recommendations)

Interactive features: collapsible cards, action item status (localStorage `p2d_ai_{session_id}`), requirements filter, comments per action item (localStorage `p2d_cmt_{session_id}`).

Visibility: `opacity:1` by default; `.will-animate` added only via JS when IntersectionObserver supported and viewport > 300 px — prevents blank content inside Streamlit iframe.

Displayed via `components.html(syn.html, height=900, scrolling=True)`.

---

## project_store — Full Function Reference

Key Supabase CRUD functions in `core/project_store.py`:

| Function | Description |
|---|---|
| `list_projects()` | All projects |
| `list_meetings(project_id)` | Meetings for a project |
| `get_global_stats()` | KPI counts (projects, meetings, requirements, decisions) for Home page |
| `list_recent_meetings(limit)` | Last N meetings across all projects |
| `list_bpmn_processes(project_id)` | BPMN processes for a project |
| `list_bpmn_versions(process_id)` | Version history for a process |
| `save_bpmn_new_version(...)` | Saves edited XML, demotes previous current version |
| `get_bpmn_version(version_id)` | Fetch specific version |
| `save_transcript_embeddings(...)` | Upsert chunks by `(meeting_id, chunk_index)` |
| `search_transcript_chunks(...)` | pgvector cosine similarity search |
| `get_global_stats()` | Counts for Home KPI strip |
| `preview_meeting_deletion(meeting_id)` | Lists all records to be deleted (non-destructive) |
| `delete_meeting(meeting_id)` | Cascade delete: `requirement_versions` → FK nullify → SBVR/chunks → BPMN versions/processes → meeting |

All functions fail-open: return `[]` or `None` when Supabase is unconfigured.

---

## UI Package — Detailed Description

### `ui/sidebar.py` — `render_sidebar()`

Always visible: provider selector + API key gate + output language selector.

Inside `st.expander("⚙️ Configuração Avançada")` (collapsed by default):
- Prefix/suffix for file naming
- Agent enable/disable checkboxes grouped: Análise de Reunião (Quality, Minutes, Requirements) / Diagramas (BPMN) / Análise de Negócio (SBVR, BMM, Synthesizer)
- BPMN passes slider (1/3/5) + weight sliders (only when n > 1)
- **🔄 Adaptive Retry (LangGraph)** checkbox + Quality Threshold slider + Max Retries selector (only when n_bpmn_runs == 1)
- Developer Mode toggle

Re-run buttons for all agents appear below the expander after a pipeline run.

### `ui/input_area.py` — `render_input_area()`

- `st.text_area` for pasting transcript
- File uploader (`.txt`, `.docx`, `.pdf`) via `services/file_ingest.py`
- "Pre-process" button (no LLM) — side-by-side original vs. cleaned with stats
- Editable cleaned text area (`curated_clean`) — "Use curated text" button
- Returns `True` when "🚀 Generate Insights" is clicked

### `ui/architecture_diagram.py` — `render_architecture_diagram()`

`flowchart TD` Mermaid diagram as splash at startup. SVG fetched once via `@st.cache_data`. Expander starts expanded when no hub in session_state, collapsed after pipeline run.

### Pipeline result tabs

**Primary tabs:** `📋 Ata de Reunião · 📝 Requisitos · 📐 BPMN 2.0 · 📊 Mermaid · 📄 Relatório Executivo · 📦 Exportar`

**Secondary tabs** inside `st.expander("🔬 Análise Avançada", expanded=False)`:
`🔬 Qualidade · 📖 SBVR · 🎯 BMM · 🏆 Validação BPMN · 🔍 Dev Tools`
