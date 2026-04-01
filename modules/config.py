# modules/config.py
# ─────────────────────────────────────────────────────────────────────────────
# Central registry of all supported LLM providers.
# To add a new provider: add an entry to AVAILABLE_PROVIDERS.
# The adapter in extract_llm.py reads this config to route requests.
# ─────────────────────────────────────────────────────────────────────────────

AVAILABLE_PROVIDERS: dict = {

    "DeepSeek": {
        "default_model": "deepseek-chat",          # DeepSeek-V3.2
        "base_url": "https://api.deepseek.com/v1",
        "api_key_label": "DeepSeek API Key",
        "api_key_help": "Get your key at platform.deepseek.com",
        "api_key_prefix": "sk-",                   # for visual hint only
        "client_type": "openai_compatible",        # uses OpenAI SDK with custom base_url
        "cost_hint": "$0.28 / $0.42 per 1M tokens",
        "supports_json_mode": True,
        "supports_system_prompt": True,
        "max_tokens": 8192,
    },

    "Claude (Anthropic)": {
        "default_model": "claude-sonnet-4-20250514",
        "base_url": None,                          # uses native Anthropic SDK
        "api_key_label": "Anthropic API Key",
        "api_key_help": "Get your key at console.anthropic.com",
        "api_key_prefix": "sk-ant-",
        "client_type": "anthropic",
        "cost_hint": "$3 / $15 per 1M tokens",
        "supports_json_mode": False,               # use prompt-based JSON enforcement
        "supports_system_prompt": True,
        "max_tokens": 8192,
    },

    "OpenAI": {
        "default_model": "gpt-4o-mini",
        "base_url": "https://api.openai.com/v1",
        "api_key_label": "OpenAI API Key",
        "api_key_help": "Get your key at platform.openai.com",
        "api_key_prefix": "sk-",
        "client_type": "openai_compatible",
        "cost_hint": "$0.15 / $0.60 per 1M tokens (4o-mini)",
        "supports_json_mode": True,
        "supports_system_prompt": True,
        "max_tokens": 8192,
    },

    "Groq (Llama)": {
        "default_model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_label": "Groq API Key",
        "api_key_help": "Get your key at console.groq.com",
        "api_key_prefix": "gsk_",
        "client_type": "openai_compatible",
        "cost_hint": "~$0.06 / $0.06 per 1M tokens",
        "supports_json_mode": True,
        "supports_system_prompt": True,
        "max_tokens": 8192,
    },

    "Google Gemini": {
        "default_model": "gemini-2.0-flash",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key_label": "Google AI Studio Key",
        "api_key_help": "Get your key at aistudio.google.com",
        "api_key_prefix": "AIza",
        "client_type": "openai_compatible",        # Gemini supports OpenAI-compatible endpoint
        "cost_hint": "Free tier available",
        "supports_json_mode": True,
        "supports_system_prompt": True,
        "max_tokens": 8192,
    },

}

# Default provider shown on startup
DEFAULT_PROVIDER = "DeepSeek"
