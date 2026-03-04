# Process2Diagram — Architecture v2

## Overview

Multi-provider LLM pipeline that converts meeting transcripts into process diagrams.
Supports DeepSeek, Claude, OpenAI, Groq, and Gemini via a unified interface.

---

## Project Structure

```
process2diagram/
│
├── app.py                    # Streamlit UI + orchestration
├── requirements.txt
│
└── modules/
    ├── config.py             # ★ Provider registry — add new LLMs here
    ├── session_security.py   # ★ API key security (session-only storage)
    ├── schema.py             # Process data model (Steps, Edges, Decisions)
    ├── ingest.py             # Transcript input handling
    ├── preprocess.py         # Text cleaning
    ├── extract_llm.py        # ★ Multi-LLM routing + extraction
    ├── diagram_mermaid.py    # Mermaid flowchart generator
    ├── diagram_drawio.py     # Draw.io XML generator
    └── utils.py              # JSON export
```

---

## Adding a New LLM Provider

Edit `modules/config.py` only. Add an entry:

```python
"My Provider": {
    "default_model": "my-model-name",
    "base_url": "https://api.myprovider.com/v1",   # None for Anthropic
    "api_key_label": "My Provider API Key",
    "api_key_help": "Get your key at myprovider.com",
    "api_key_prefix": "sk-",
    "client_type": "openai_compatible",  # or "anthropic"
    "cost_hint": "$X / $Y per 1M tokens",
    "supports_json_mode": True,
    "supports_system_prompt": True,
},
```

If the provider uses the OpenAI-compatible API format → works automatically.
If it uses a custom SDK → add a handler in `extract_llm.py → call_llm()`.

---

## API Key Security Model

### Strategy: Session-state isolation

Keys are stored **only** in `st.session_state`, which is:
- Server-side RAM for a single user's browser session
- Destroyed when the tab closes or session expires
- Never written to disk, database, logs, or environment variables

### What this means in practice

| Threat | Protected? |
|---|---|
| Another user on Streamlit Cloud sees your key | ✅ Yes — session state is isolated per user |
| Key persists after tab close | ✅ No persistence |
| Key appears in server logs | ✅ Never logged |
| Key sent to third parties | ✅ Only sent to the chosen LLM provider |
| Compromised Streamlit Cloud server | ❌ Not protected (use st.secrets for that) |

### For higher-security deployments

Use a backend proxy pattern:
```
User → Your Backend (holds key in st.secrets) → LLM Provider
```
The frontend never sees the key at all.

---

## Running Locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploying to Streamlit Cloud

1. Push to GitHub
2. Go to share.streamlit.io → New app
3. Select repo, set `Main file: app.py`
4. Deploy — no secrets config needed (users enter their own keys)
