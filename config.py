# modules/config.py

AVAILABLE_PROVIDERS = {
    "deepseek": {
        "name": "DeepSeek",
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com/v1",
        "client_type": "openai_compat",
        "key_hint": "sk-...",
        "docs_url": "https://platform.deepseek.com/api_keys",
    },
    "claude": {
        "name": "Claude (Anthropic)",
        "model": "claude-sonnet-4-20250514",
        "base_url": None,
        "client_type": "anthropic",
        "key_hint": "sk-ant-...",
        "docs_url": "https://console.anthropic.com/settings/keys",
    },
    "openai": {
        "name": "OpenAI",
        "model": "gpt-4o-mini",
        "base_url": None,
        "client_type": "openai_compat",
        "key_hint": "sk-...",
        "docs_url": "https://platform.openai.com/api-keys",
    },
    "groq": {
        "name": "Groq",
        "model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "client_type": "openai_compat",
        "key_hint": "gsk_...",
        "docs_url": "https://console.groq.com/keys",
    },
    "gemini": {
        "name": "Gemini (Google)",
        "model": "gemini-2.0-flash",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "client_type": "openai_compat",
        "key_hint": "AIza...",
        "docs_url": "https://aistudio.google.com/app/apikey",
    },
}

DEFAULT_PROVIDER = "deepseek"
