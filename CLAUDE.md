# CLAUDE.md — Process2Diagram

> Read this file in full before making any changes to the codebase.

## Project Overview

**Process2Diagram** converts meeting transcriptions into professional process diagrams using a multi-LLM pipeline.

- **Input:** raw text transcript (paste or `.txt` upload)
- **Outputs:** BPMN 2.0 XML, Mermaid flowchart, meeting minutes (Markdown), and requirements analysis (JSON/Markdown)
- **Deploy:** Streamlit Cloud — auto-deploy on push to `main` branch (`github.com/pedroregato/process2diagram`)
- **Dev environment:** PyCharm on Windows; Python 3.13

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
├── app.py                    # Streamlit entry point — UI, progress bar, multi-tab results
│
├── core/
│   ├── knowledge_hub.py      # KnowledgeHub: central session state shared by all agents
│   └── schema.py             # Legacy schemas (Process, Step, Edge, BpmnProcess…)
│
├── agents/
│   ├── base_agent.py         # Abstract base — LLM routing, JSON retry, token tracking
│   ├── orchestrator.py       # Sequences NLP → BPMN → Minutes → Requirements; accepts progress_callback
│   ├── nlp_chunker.py        # Pure Python/spaCy preprocessor — no LLM
│   ├── agent_bpmn.py         # BPMN extraction + _enforce_rules() post-processing + generators
│   ├── agent_minutes.py      # Meeting minutes extraction (full transcript, initials convention)
│   └── agent_requirements.py # Requirements extraction (IEEE 830 adapted; speaker attribution)
│
├── modules/
│   ├── config.py             # LLM provider registry — add new providers here
│   ├── session_security.py   # API keys in st.session_state only, never persisted
│   ├── bpmn_generator.py     # OMG BPMN 2.0 XML generator (absolute coordinates layout)
│   ├── bpmn_viewer.py        # BPMN viewer component (bpmn-js 17 injected inline)
│   ├── diagram_mermaid.py    # Mermaid flowchart generator
│   ├── diagram_bpmn.py       # Legacy BPMN generator (kept for compatibility)
│   ├── extract_llm.py        # Legacy LLM adapter (used by app.py v1 flow)
│   ├── extract_heuristic.py  # Heuristic extractor (no-LLM fallback)
│   ├── ingest.py             # .txt file loader
│   ├── preprocess.py         # Basic text cleaning
│   └── utils.py              # Helpers (process_to_json, etc.)
│
├── skills/
│   ├── SKILL_BPMN.md         # System prompt for AgentBPMN
│   ├── SKILL_MINUTES.md      # System prompt for AgentMinutes
│   └── SKILL_REQUIREMENTS.md # System prompt for AgentRequirements
│
├── requirements.txt          # streamlit, anthropic, openai (pinned versions)
└── CLAUDE.md                 # This file
```

> **Linux / Streamlit Cloud:** filesystem is case-sensitive.
> Import names must match filenames exactly. `skill_bpmn.md` ≠ `SKILL_BPMN.md`.

---

## Architecture

### Data Flow

```
Transcript (user input)
        │
        ▼
  NLPChunker              ← no LLM; spaCy NER, segmentation, actor detection
        │  hub.nlp.ready = True
        ▼
   AgentBPMN              ← LLM; extracts steps/edges/lanes → BPMN XML, Mermaid
        │  _enforce_rules() post-processes: generic lanes, service-task lanes,
        │  correction-loop redirect, redundant event steps
        │  hub.bpmn.ready = True
        ▼
  AgentMinutes            ← LLM; full transcript; initials convention (MF, PG…)
        │  extracts decisions, action items (raised_by), participants with initials
        │  hub.minutes.ready = True
        ▼
 AgentRequirements        ← LLM; IEEE 830 adapted; speaker attribution per requirement
        │  extracts ui_field, validation, business_rule, functional, non_functional
        │  hub.requirements.ready = True
        ▼
   KnowledgeHub           ← fully populated; stored in st.session_state["hub"]
```

### KnowledgeHub — Central State

A pure Python dataclass living in `st.session_state["hub"]`. Each agent reads only what it needs and writes only to its own section. Version counter is bumped after every write.

```python
@dataclass
class KnowledgeHub:
    version: int                   # bumped on every .bump() call
    transcript_raw: str
    transcript_clean: str
    nlp: NLPEnvelope               # written by NLPChunker
    bpmn: BPMNModel                # written by AgentBPMN
    minutes: MinutesModel          # written by AgentMinutes
    requirements: RequirementsModel # written by AgentRequirements
    validation: ValidationReport   # reserved for PC2 AgentValidator
    meta: SessionMetadata          # tokens, timing, provider info
```

**Schema evolution:** `KnowledgeHub.migrate(hub)` is the single point for backward-compatibility fixes when fields are added. Always add new field guards here instead of scattered `hasattr` checks in `app.py`.

**Golden rule:** never instantiate an agent directly from `app.py`. Always go through `Orchestrator`.

### Agent Pattern

Every agent in `agents/` inherits from `BaseAgent`:

```python
class MyAgent(BaseAgent):
    name = "my_agent"
    skill_path = "skills/SKILL_MY.md"   # loaded once at __init__

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

Provider routing in `BaseAgent._call_llm()`: reads `client_type` from config — `"openai_compatible"` uses the OpenAI SDK with a custom `base_url`; `"anthropic"` uses the native Anthropic SDK.

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

### Waypoint routing

`_build_di` emits waypoints for every sequence flow:
- **Normal flow** (forward, no overlap): right-centre → left-centre (2 points)
- **Stacked elements** (same column, x-ranges overlap): bottom-centre → top-centre (2 points)
- **Backward flow** (source column > target column, same lane): U-path with 4 waypoints below elements: `source_right → source_below → target_below → target_left`. The horizontal segment is routed 25 px below the tallest element in the path, within the empty lower portion of the lane.

### Post-extraction rule enforcement (`_enforce_rules`)

Applied in `agent_bpmn.py` after LLM extraction, before generators. Mutates the model in-place:

- **Rule 0** — removes steps the LLM declared as `startEvent`/`endEvent` (generator adds these)
- **Rule 1** — `serviceTask` with unnamed system actor → `lane = None` (OMG §7.4)
- **Rule 1b** — generic lane names (`usuário`, `validador`, `sistema`…) → scans step descriptions for capitalized organizational noun phrases; replaces with the most frequent candidate
- **Rule 2** — correction loop pointing back to gateway → redirected to the upstream work step that feeds the gateway

### Rules the LLM must follow (enforced by `SKILL_BPMN.md`)

- The LLM **must not declare** Link Intermediate Events — the generator handles them.
- Start/End Event lane assignment follows the direct predecessor/successor.
- System lanes must not receive Start/End Events.
- Lane ordering: primary initiating actor at the top.
- End Event inherits the lane of its direct predecessor (Rule 8).
- Lane names must be organizational units, never generic roles (`usuário`, `sistema`, etc.).

---

## BPMN Viewer (`modules/bpmn_viewer.py`)

- Rendered via `streamlit.components.v1.html` with **bpmn-js 17** injected inline (no external CDN).
- Toolbar positioned top-right (light theme).
- `MutationObserver` triggers auto-fit when the SVG is inserted into the DOM.
- `getBoundingClientRect()` returns zero before paint — use `fitWhenReady` polling loop.

---

## Mermaid Viewer

- SVG fetched **server-side** from `mermaid.ink/svg/{base64_payload}` and injected into `components.html` via JavaScript — no external CDN dependency inside the iframe.
- Both `TD` (top-down) and `LR` (left-right) variants are pre-fetched for instant client-side toggling.
- `robustFit` polling function handles SVG dimension availability timing.

**Why no CDN in the iframe?**
Streamlit Cloud sandbox blocks external script loading inside `components.html`.
All JS dependencies must be resolved server-side or injected inline.

---

## Streamlit Session State

**Critical issue:** clicking any `st.download_button` triggers a full app rerun, wiping any local variable.

**Required pattern:**

```python
# app.py — correct pattern
if generate_btn:
    hub = orchestrator.run(hub)
    st.session_state["hub"] = hub   # ← store BEFORE rendering any widget

# Render block lives OUTSIDE the if generate_btn: block
if "hub" in st.session_state:
    hub = st.session_state["hub"]
    # render tabs, download buttons, viewers...
```

**Rule:** any state that must survive reruns (hub, generated outputs) must be written to `st.session_state` before the first widget that could trigger a rerun.

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
4. Add tab / download button in `app.py`

### Adding a new agent

1. Create `agents/agent_new.py` inheriting from `BaseAgent`
2. Implement `build_prompt(hub)` and `run(hub)`
3. Create `skills/SKILL_NEW.md` with the system prompt
4. Add field to `KnowledgeHub` in `core/knowledge_hub.py`
5. Register in `agents/orchestrator.py → _PLAN` list
6. Update `app.py` to render the new output

### Modifying BPMN layout

- Coordinates are absolute — no direction parameter exists.
- Layout changes affect the constants at the top of `bpmn_generator.py`: `TASK_W`, `H_GAP`, `V_PAD`.
- After layout changes, always verify the crossing-elimination heuristic still behaves correctly.

---

## Security Model

API keys are stored exclusively in `st.session_state` (server-side, per-session memory in Streamlit). They are never logged, written to disk, or persisted across sessions.

- `session_security.render_api_key_gate(provider)` — renders the key input in the sidebar
- `session_security.get_session_llm_client(provider)` — retrieves the live client or `None`

---

## Roadmap

### PC1 — Concluído (v3.3)
- [x] Pipeline sequencial NLP → BPMN → Minutes → Requirements
- [x] BPMN 2.0 XML com layout absoluto, pools/lanes, Link Events
- [x] `_enforce_rules()` — defesa programática contra erros LLM de lane/gateway
- [x] Backward-flow U-routing em `_build_di` — sem invasão visual de elementos
- [x] `AgentRequirements` — 5 tipos IEEE 830, speaker attribution por citação
- [x] Minutes com transcrição completa + iniciais de participantes
- [x] `KnowledgeHub.migrate()` para evolução de schema sem quebrar sessões

### PC2 — Planejado
- [ ] Parallel agent execution with `asyncio.gather()` in the Orchestrator
- [ ] `AgentValidator` post-generation quality scoring
- [ ] `AgentSBVR` and `AgentBMM` for semantic business modeling
- [ ] LangGraph integration for conditional re-routing on validation failures
- [ ] Suite de testes automatizados por cenário

---

## Technical References

| Resource | Location |
|---|---|
| BPMN 2.0 Spec (OMG) | ISO/IEC 19510 / OMG formal/2013-12-09 |
| bpmn-js | github.com/bpmn-io/bpmn-js (v17) |
| mermaid.ink SVG endpoint | mermaid.ink |
| Streamlit session state | docs.streamlit.io/library/api-reference/session-state |
