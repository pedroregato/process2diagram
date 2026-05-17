# Known Pitfalls — Process2Diagram

Problemas recorrentes com causa-raiz e solução completa (incluindo exemplos de código).

---

## Skill file case sensitivity (Linux)

Streamlit Cloud runs on Linux (case-sensitive filesystem). A `skill_path` that works on Windows may silently fail on Linux if the case doesn't match the git-tracked name.

**Diagnosis:** Knowledge Hub tab → Skills section or Diagnóstico expander.
**Fix:** always verify with `git ls-files skills/` and match exactly.
**Rule:** `_load_skill()` uses `Path(__file__).parent.parent / skill_path` — never CWD-relative.

Examples: `skill_bpmn.md` (lowercase) vs `SKILL_REQUIREMENTS.md` (uppercase).

---

## Stale `.pyc` cache on Streamlit Cloud

When a new symbol is added to an existing module, a stale cached `.pyc` on the server may not include it, causing `ImportError`.

**Pattern:** belt-and-suspenders guards in `migrate()`:

```python
if not hasattr(hub, 'new_field'):
    try:
        from core.knowledge_hub import NewModel
        hub.new_field = NewModel()
    except ImportError:
        hub.new_field = <inline fallback>
```

---

## st.page_link() with app.py raises StreamlitPageNotFoundError

`app.py` is the navigation host — not a registered page. `st.page_link("app.py", ...)` raises `StreamlitPageNotFoundError`.

```python
# Wrong
st.page_link("app.py", label="← Voltar")

# Correct
st.page_link("pages/Pipeline.py", label="← Voltar")
```

---

## Login page HTML rendered as code block

In `ui/auth_gate.py`, HTML injected via `st.markdown(unsafe_allow_html=True)` must not be indented ≥ 4 spaces after a blank line — Markdown treats that as a code fence and renders raw HTML.

**Fix:** keep the f-string HTML at zero indentation. Extract dynamic labels to separate `st.markdown` calls to avoid the blank-line-from-empty-interpolation trap.

---

## st.error() / st.success() disappear before st.rerun()

Any `st.error()` or `st.success()` call made immediately before `st.rerun()` is never rendered. The widget is drawn but the rerun clears it before the browser paints.

**Pattern:** persist in `st.session_state` before rerunning; pop and display after the rerun:

```python
st.session_state["_embed_error"] = "❌ Falha ao gerar embeddings: ..."
st.rerun()

# --- next run ---
if "_embed_error" in st.session_state:
    st.error(st.session_state.pop("_embed_error"))
```

Keys used in embedding flow: `_emb_tab_result`, `_emb_tab_single_result`, `_emb_tab_err_{meeting_id}`.

---

## bpmn-js fit-viewport SVGMatrix non-finite error

**Symptom:** `Failed to execute 'scale' on 'SVGMatrix': The provided float value is non-finite` when rendering BPMN diagrams.

**Root cause:** `canvas.zoom('fit-viewport')` called synchronously inside `importXML().then()` fires before the browser has computed iframe container dimensions. `outerW = 0` → `diagramW/0 = Infinity`.

**Fix (in `modules/bpmn_viewer.py`):** defer via `setTimeout(fn, 150)` and validate dimensions:

```javascript
setTimeout(function() {
  var vb = canvas.viewbox();
  var inn = vb && vb.inner, outer = vb && vb.outer;
  if (inn && outer &&
      isFinite(inn.width) && inn.width > 0 &&
      isFinite(outer.width) && outer.width > 0) {
    canvas.zoom('fit-viewport');
  } else {
    canvas.zoom(0.75);
  }
}, 150);
```

Applies to **both** the main inline template and `_TEMPLATE_CDN_FALLBACK`.

---

## Global active-project context fragmentation

`active_project_id` and `active_project_name` in `st.session_state` are the single source of truth. Set only from Home.py or `set_active_project` tool.

All analysis pages (Assistente, ReqTracker, BpmnEditor, MeetingROI, ValidationHub) must call `require_active_project()` at the top of their render flow.

**Do NOT** add a local project selectbox to these pages — it would fragment the context.

```python
# Correct pattern for analysis pages
from ui.project_selector import require_active_project
project_id, project_name = require_active_project()
```

---

## Streamlit sidebar href="#id" navigates parent frame

Inside `components.html()`, anchor links with `href="#section-id"` navigate the **parent** Streamlit frame, not the iframe.

**Fix:** use `data-target` + JS `scrollIntoView`:

```html
<a data-target="sec-foo" href="javascript:void(0)">Link</a>
<script>
  document.querySelectorAll('[data-target]').forEach(link => {
    link.addEventListener('click', e => {
      e.preventDefault();
      document.getElementById(link.dataset.target)?.scrollIntoView({behavior:'smooth'});
    });
  });
</script>
```

---

## Gemini embedding model availability per API key

Not all `text-embedding-*` models are available to every AI Studio key. `text-embedding-004` may return 404 even though documented.

**Diagnosis:** Settings → Embeddings & Busca → "🔍 Testar chave" → `list_gemini_embedding_models(api_key)`.

**Confirmed working models:**
- `models/gemini-embedding-001` — 1536 dims via `output_dimensionality=1536` (primary)
- `models/gemini-embedding-2-preview` — fallback on 404

`_embed_gemini()` tries `gemini-embedding-001` first, falls back automatically.

---

## Gemini embedding rate limits (free tier: 100 req/min)

Large transcripts easily exceed the free tier limit with one API call per chunk.

**Mitigations in `modules/embeddings.py`:**
- `_GEMINI_RATE_DELAY = 1.2` seconds between batch calls (~50 req/min sustained)
- `_GEMINI_MAX_RETRIES = 5` automatic retries on 429
- Retry wait extracted from error body via regex `r"seconds[\"':\s]+(\d+)"` + 10-second buffer

---

## pgvector dimension limit (ivfflat ≤ 2000 dims)

PostgreSQL `ivfflat` index cannot handle vectors with more than 2000 dimensions. `gemini-embedding-001` natively produces 3072 dims.

**Fix:** always use `output_dimensionality=1536` when calling the Gemini embedding API. Column must be `vector(1536)`. Schema in `setup/supabase_schema_transcript_chunks.sql`.

---

## Pages import path on Streamlit Cloud

`pages/Diagramas.py` (and other pages) must add the project root to `sys.path` manually:

```python
root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
```

Streamlit multi-page apps run page files in a different working directory context.

---

## Google Calendar secrets — TOML encoding

`credentials_json` in `secrets.toml` must use `'''` (literal triple-single-quotes), not `"""`.

```toml
# Correct
[google_calendar]
credentials_json = '''{"type": "service_account", "private_key": "-----BEGIN RSA..."}'''

# Wrong — Python processes \n escape sequences, corrupting the private key
credentials_json = """{"type": "service_account", "private_key": "-----BEGIN RSA..."}"""
```

---

## delete_meeting cascade order

Must delete in this exact order to avoid FK violations:

1. Delete `requirement_versions` WHERE `meeting_id = X` (direct FK, discovered v4.18)
2. Nullify `requirements.first_meeting_id` and `last_meeting_id`
3. Delete `sbvr_terms`, `sbvr_rules`, `transcript_chunks`
4. Fetch `bpmn_processes` IDs → delete `bpmn_versions` → delete `bpmn_processes`
5. Delete the `meetings` record

`preview_meeting_deletion(meeting_id)` lists all affected records before destructive action.

---

## Anthropic provider — no json_mode

Claude (Anthropic) does not support `json_mode`. Enforce JSON output via system prompt only — never pass `response_format={"type": "json_object"}` to Anthropic SDK.

```python
# In skill file or build_prompt:
# "Respond ONLY with valid JSON matching the schema below. No markdown, no explanation."
```

`BaseAgent._call_llm()` routes on `client_type`: `"anthropic"` uses native Anthropic SDK; `"openai_compatible"` uses OpenAI SDK with custom `base_url`.
