# Acceptance Criteria (Outcomes) — Process2Diagram

> This section defines what "done" looks like for each agent and subsystem.
> Claude Code must verify these criteria after any change that touches the
> relevant module. If a criterion cannot be verified automatically, flag it
> explicitly before closing the task.
>
> These criteria are enforced at runtime by `AgentValidator.validate_all()`
> (pure Python, no LLM) and surfaced as quality badges in the Pipeline UI
> via `hub.validation.agent_scores`.

---

## AgentTranscriptQuality

- Returns a grade in `{"A","B","C","D","E"}` stored in `hub.transcript_quality.grade`
- `hub.transcript_quality.criteria` is a non-empty list
- Grade `D` or `E` must surface a warning in the Pipeline UI (not silently pass)

## NLPChunker

- `hub.nlp.segments` is non-empty for any transcript longer than 50 words
- `hub.nlp.actors` contains at least one entry when participant names appear in transcript
- `hub.nlp.language_detected` is set (never `None` or empty string)
- No LLM call is made — pure Python/spaCy only

## AgentBPMN

- `hub.bpmn.steps` has at least 3 items
- `hub.bpmn.lanes` has at least 1 item with a non-generic name (not `"usuário"`, `"sistema"`, `"validador"`)
- `hub.bpmn.bpmn_xml` is valid XML parseable by `xml.etree.ElementTree`
- `hub.bpmn.bpmn_xml` contains a `<bpmndi:BPMNDiagram>` element
- Exactly one `startEvent` and at least one `endEvent` present in XML
- `_enforce_rules()` has been applied (no raw LLM output bypasses it)
- If `n_bpmn_runs > 1`: `hub.validation.ready` is `True` and winning score is stored

## AgentMermaid (MermaidGenerator — pure Python)

- `hub.bpmn.mermaid_code` starts with `flowchart TD` or `flowchart LR`
- No node ID uses reserved words (`END`, `start`, `end`)
- Decision nodes use `{}` syntax (not `{{}}`)
- No quoted labels inside `{}` nodes
- SVG renders without error when submitted to `mermaid.ink`

## AgentMinutes

- `hub.minutes.participants` has at least 1 entry
- `hub.minutes.decisions` has at least 1 entry for any substantive meeting
- `hub.minutes.action_items` entries each have `responsible` and `deadline` fields (may be `"TBD"`)
- Markdown export (`AgentMinutes.to_markdown()`) produces a non-empty string
- DOCX export completes without exception

## AgentRequirements

- `hub.requirements.items` has at least 1 entry for any meeting with stated objectives
- Each requirement has `id`, `description`, `type`, and `speaker` fields populated
- `type` values are constrained to IEEE 830 categories: `functional`, `non_functional`, `constraint`, `business_rule`
- JSON export is valid and parseable

## AgentSBVR (optional — default OFF)

- `hub.sbvr.vocabulary` has 5–15 terms, each with `term`, `category`, and `definition`
- `hub.sbvr.rules` has 3–10 rules, each with `statement` and `rule_type`
- No term appears in `vocabulary` without a `definition`
- `rule_type` values limited to OMG SBVR categories

## AgentBMM (optional — default OFF)

- `hub.bmm.vision` and `hub.bmm.mission` are non-empty strings
- `hub.bmm.goals` has at least 1 entry
- `hub.bmm.strategies` entries each reference at least one goal via `goal_links`
- JSON export is valid and parseable

## AgentSynthesizer (optional — default OFF)

- Returns a self-contained HTML string (no broken external CDN dependencies)
- Contains all 6 sections in order: Sumário Executivo, Visão do Processo, BPMN, Mermaid, Ata, Requisitos
- BPMN diagram renders inside the iframe `srcdoc` without JS errors
- Sidebar nav `data-target` links scroll correctly (no `href="#id"` pattern)

## AgentValidator

- `hub.validation.scores` contains entries for all runs when `n_bpmn_runs > 1`
- `hub.validation.winner_index` points to the highest `weighted` score
- Three dimensions scored: `granularity`, `task_type`, `gateways` (each 0–10)
- Pure Python — no LLM call
- `hub.validation.agent_scores` populated after every pipeline run (not only multi-run)

---

## Pipeline Integration Criteria

- `run_pipeline()` completes without unhandled exception for any transcript ≥ 50 words
- `KnowledgeHub.migrate(hub)` is the only place backward-compat field guards are added
- No agent is instantiated directly from `app.py` or `pages/Pipeline.py` — always via `Orchestrator` or `handle_rerun()`
- `ThreadPoolExecutor` parallel branch (Minutes + Requirements) falls back to sequential without crashing on any exception
- All `st.download_button` outputs are pre-computed and stored in `st.session_state` before rendering — never inside the generate block

## Supabase / Persistence Criteria

- All `core/project_store.py` functions are fail-open: return `[]` or `None` when Supabase is unconfigured, never raise
- `save_bpmn_new_version()` demotes the previous `is_current=True` version before inserting
- Embedding generation respects 1.2s inter-call delay for free-tier rate limits

## UI / Streamlit Criteria

- No `href="#id"` pattern in generated HTML (causes parent frame navigation)
- `st.page_link()` arguments reference only registered page files, never `app.py`
- CSP constraint: no external CDN `eval()` calls inside `components.html` iframes
- bpmn-js 17 injected inline — never loaded from CDN inside an iframe
