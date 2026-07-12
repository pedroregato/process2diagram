# modules/config.py
# ─────────────────────────────────────────────────────────────────────────────
# Central registry of all supported LLM providers.
# To add a new provider: add an entry to AVAILABLE_PROVIDERS.
# The adapter in extract_llm.py reads this config to route requests.
# ─────────────────────────────────────────────────────────────────────────────

AVAILABLE_PROVIDERS: dict = {

    "DeepSeek": {
        "default_model": "deepseek-v4-flash",      # DeepSeek V4 Flash (deepseek-chat deprecated 24/07/2026)
        "base_url": "https://api.deepseek.com/v1",
        "api_key_label": "DeepSeek API Key",
        "api_key_help": "Get your key at platform.deepseek.com",
        "api_key_prefix": "sk-",
        "client_type": "openai_compatible",
        "cost_hint": "$0.14 / $0.28 per 1M tokens (1M context)",
        "supports_json_mode": True,
        "supports_system_prompt": True,
        "max_tokens": 8192,
        "long_context_max_tokens": 32768,
    },

    "DeepSeek V4 Pro": {
        "default_model": "deepseek-v4-pro",
        "base_url": "https://api.deepseek.com/v1",
        "api_key_label": "DeepSeek API Key",
        "api_key_help": "Get your key at platform.deepseek.com",
        "api_key_prefix": "sk-",
        "client_type": "openai_compatible",
        "cost_hint": "$0.435 / $0.87 per 1M tokens (1M context, premium)",
        "supports_json_mode": True,
        "supports_system_prompt": True,
        "max_tokens": 8192,
        "long_context_max_tokens": 32768,
        "api_key_alias": "DeepSeek",       # compartilha a mesma API key do DeepSeek
    },

    "DeepSeek V4 Flash (Thinking)": {
        "default_model": "deepseek-v4-flash",
        "base_url": "https://api.deepseek.com/v1",
        "api_key_label": "DeepSeek API Key",
        "api_key_help": "Get your key at platform.deepseek.com",
        "api_key_prefix": "sk-",
        "client_type": "openai_compatible",
        "cost_hint": "$0.14 / $0.28 per 1M tokens + thinking tokens",
        "supports_json_mode": False,       # não suportado em thinking mode
        "supports_system_prompt": True,
        "max_tokens": 16384,               # inclui tokens de raciocínio interno
        "long_context_max_tokens": 32768,
        "reasoning_effort": "high",        # ativa modo de pensamento (thinking)
        "api_key_alias": "DeepSeek",       # compartilha a mesma API key do DeepSeek
    },

    "Claude (Anthropic)": {
        "default_model": "claude-sonnet-4-20250514",
        "base_url": None,
        "api_key_label": "Anthropic API Key",
        "api_key_help": "Get your key at console.anthropic.com",
        "api_key_prefix": "sk-ant-",
        "client_type": "anthropic",
        "cost_hint": "$3 / $15 per 1M tokens",
        "supports_json_mode": False,
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

    "Azure OpenAI": {
        # `default_model` is the Azure *deployment name*, not a model id —
        # Azure OpenAI routes by deployment, so this must match whatever the
        # user named their deployment in Azure AI Foundry / Azure Portal.
        "default_model": "gpt-4o-mini",
        "base_url": None,               # unused — Azure uses azure_endpoint (extra_fields) instead
        "api_key_label": "Azure OpenAI API Key",
        "api_key_help": "Get your key at portal.azure.com — recurso Azure OpenAI > Keys and Endpoint",
        "api_key_prefix": "",
        "client_type": "azure_openai",
        "cost_hint": "Preço definido pelo seu contrato/região Azure (varia por SKU e deployment)",
        "supports_json_mode": True,
        "supports_system_prompt": True,
        "max_tokens": 8192,
        "api_version": "2024-10-21",
        "extra_fields": [
            {
                "key": "azure_endpoint",
                "label": "Azure Endpoint",
                "placeholder": "https://<seu-recurso>.openai.azure.com",
                "help": "Azure Portal > seu recurso Azure OpenAI > Keys and Endpoint.",
            },
            {
                "key": "deployment_name",
                "label": "Deployment Name (opcional)",
                "placeholder": "ex: gpt-4o-mini-prod",
                "help": "Azure roteia por nome de deployment, não por model id. "
                        "Deixe em branco para usar 'gpt-4o-mini' (padrão acima) — "
                        "preencha se o seu deployment tem outro nome.",
            },
        ],
        "note": "Requer endpoint próprio do recurso Azure (campos adicionais abaixo).",
    },

    "Groq (Llama)": {
        "default_model": "llama-3.3-70b-versatile",
        "base_url": "https://api.groq.com/openai/v1",
        "api_key_label": "Groq API Key",
        "api_key_help": "Get your key at console.groq.com",
        "api_key_prefix": "gsk_",
        "client_type": "openai_compatible",
        "cost_hint": "$0.59 / $0.79 per 1M tokens",
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
        "client_type": "openai_compatible",
        "cost_hint": "Free tier available",
        "supports_json_mode": True,
        "supports_system_prompt": True,
        "max_tokens": 8192,
    },

    # ── Grok (xAI) ─────────────────────────────────────────────────────
    "Grok (xAI)": {
        "default_model": "grok-4-1-fast-reasoning",   # Recomendado para começar (bom custo + contexto 2M)
        "base_url": "https://api.x.ai/v1",
        "api_key_label": "xAI Grok API Key",
        "api_key_help": "Get your key at console.x.ai",
        "api_key_prefix": "xai-",
        "client_type": "openai_compatible",
        "cost_hint": "$0.20 / $0.50 per 1M tokens (Grok 4.1 Fast - 2M context)",
        "supports_json_mode": True,
        "supports_system_prompt": True,
        "max_tokens": 32768,   # limite prático de saída
        "note": "Contexto de até 2.000.000 tokens - ideal para transcrições longas",
    },

    "Grok 4.20 Multi-Agent (xAI)": {
        "default_model": "grok-4.20-multi-agent",     # ou "grok-4.20-multi-agent-0309"
        "base_url": "https://api.x.ai/v1",
        "api_key_label": "xAI Grok API Key",
        "api_key_help": "Mesma chave da xAI (console.x.ai)",
        "api_key_prefix": "xai-",
        "client_type": "openai_compatible",
        "cost_hint": "$2.00 / $6.00 per 1M tokens",
        "supports_json_mode": True,
        "supports_system_prompt": True,
        "max_tokens": 32768,
        "note": "Suporte nativo a multi-agente (4+ agentes em paralelo) - perfeito para análise de reuniões",
    },

}

# Default provider shown on startup
DEFAULT_PROVIDER = "Grok (xAI)"