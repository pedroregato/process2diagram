# modules/tenant_config.py
# ─────────────────────────────────────────────────────────────────────────────
# Gerenciamento de configurações por tenant (API keys + preferências).
#
# Tudo persiste na tabela tenant_config (Supabase) como pares chave/valor texto.
# Ao fazer login, apply_config_to_session() recarrega tudo no st.session_state.
#
# Para evoluir para criptografia (AES-256), alterar apenas _encode()/_decode().
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from modules.supabase_client import get_supabase_client

# ── Mapeamentos de chaves ──────────────────────────────────────────────────────

# Provedores LLM: nome exato em AVAILABLE_PROVIDERS → config_key no banco
PROVIDER_KEY_MAP: dict[str, str] = {
    "DeepSeek":           "deepseek_key",
    "Claude (Anthropic)": "anthropic_key",
    "OpenAI":             "openai_key",
    "Groq (Llama)":       "groq_key",
    "Google Gemini":      "gemini_key",
}

# Chaves extras de API (não vinculadas a provider do pipeline)
EXTRA_KEY_MAP: dict[str, str] = {
    "asst_api_key":   "assistant_key",
    "asst_embed_key": "embedding_key",
}

# Preferências da sessão: session_state_key → (config_key_no_banco, tipo)
# Tipos suportados: "str" | "bool" | "int"
PREFS_MAP: dict[str, tuple[str, str]] = {
    # Provedores selecionados
    "selected_provider":    ("pref_llm_provider",     "str"),
    "asst_provider":        ("pref_asst_provider",    "str"),
    "asst_embed_provider":  ("pref_embed_provider",   "str"),
    # Toggles do Assistente
    "asst_use_semantic":    ("pref_use_semantic",     "bool"),
    "asst_use_tools":       ("pref_use_tools",        "bool"),
    # Preferências gerais
    "output_language":      ("pref_output_language",  "str"),
    "prefix":               ("pref_prefix",           "str"),
    "suffix":               ("pref_suffix",           "str"),
    # Pipeline BPMN
    "n_bpmn_runs":          ("pref_n_bpmn_runs",      "int"),
    # Agentes padrão do pipeline
    "run_quality":          ("pref_run_quality",      "bool"),
    "run_bpmn":             ("pref_run_bpmn",         "bool"),
    "run_minutes":          ("pref_run_minutes",      "bool"),
    "run_requirements":     ("pref_run_requirements", "bool"),
    "run_sbvr":             ("pref_run_sbvr",         "bool"),
    "run_bmm":              ("pref_run_bmm",          "bool"),
    "run_synthesizer":      ("pref_run_synthesizer",  "bool"),
}

# Labels legíveis para exibição na UI
PREFS_LABELS: dict[str, str] = {
    "selected_provider":    "LLM Principal",
    "asst_provider":        "LLM Assistente",
    "asst_embed_provider":  "Provedor de Embedding",
    "asst_use_semantic":    "Busca semântica (pgvector)",
    "asst_use_tools":       "Modo Tool-Use no Assistente",
    "output_language":      "Idioma dos artefatos",
    "prefix":               "Prefixo de arquivos",
    "suffix":               "Sufixo de arquivos",
    "n_bpmn_runs":          "Optimization Passes (BPMN)",
    "run_quality":          "Agente: Quality Inspector",
    "run_bpmn":             "Agente: BPMN Architect",
    "run_minutes":          "Agente: Meeting Minutes",
    "run_requirements":     "Agente: Requirements",
    "run_sbvr":             "Agente: SBVR",
    "run_bmm":              "Agente: BMM",
    "run_synthesizer":      "Agente: Executive Report",
}


# ── Hooks de criptografia (plaintext por ora — trocar por AES-256 em produção) ─

def _encode(value: str) -> str:
    return value

def _decode(value: str) -> str:
    return value


# ── CRUD ───────────────────────────────────────────────────────────────────────

def load_all_config(tenant_id: str) -> dict[str, str]:
    """Retorna todas as configurações do tenant como {config_key: value}."""
    client = get_supabase_client()
    if client is None:
        return {}
    try:
        resp = (
            client.table("tenant_config")
            .select("config_key, config_value")
            .eq("tenant_id", tenant_id)
            .execute()
        )
        return {
            row["config_key"]: _decode(row["config_value"])
            for row in (resp.data or [])
            if row.get("config_value")
        }
    except Exception:
        return {}


def save_config(tenant_id: str, key: str, value: str) -> bool:
    """Upsert de uma configuração. Retorna True em caso de sucesso."""
    client = get_supabase_client()
    if client is None:
        return False
    try:
        client.table("tenant_config").upsert(
            {"tenant_id": tenant_id, "config_key": key, "config_value": _encode(value)},
            on_conflict="tenant_id,config_key",
        ).execute()
        return True
    except Exception:
        return False


def delete_config(tenant_id: str, key: str) -> bool:
    """Remove uma configuração do tenant."""
    client = get_supabase_client()
    if client is None:
        return False
    try:
        client.table("tenant_config").delete().eq("tenant_id", tenant_id).eq("config_key", key).execute()
        return True
    except Exception:
        return False


def save_all_prefs(tenant_id: str) -> tuple[int, int]:
    """Salva todas as preferências atuais do st.session_state no banco.

    Retorna (salvos, falhas).
    """
    import streamlit as st
    saved = failed = 0
    for state_key, (config_key, type_) in PREFS_MAP.items():
        val = st.session_state.get(state_key)
        if val is None:
            continue
        if save_config(tenant_id, config_key, str(val)):
            saved += 1
        else:
            failed += 1
    return saved, failed


# ── Carregamento no session_state ─────────────────────────────────────────────

def apply_config_to_session(config: dict[str, str]) -> None:
    """Popula st.session_state com API keys + preferências do tenant.

    Chamado logo após login_tenant() bem-sucedido.
    """
    import streamlit as st
    from modules.session_security import _session_key

    # API keys dos provedores LLM
    for provider, key_name in PROVIDER_KEY_MAP.items():
        value = config.get(key_name, "")
        if value:
            st.session_state[_session_key(provider)] = value

    # API keys extras (Assistente + Embedding)
    for state_key, config_key in EXTRA_KEY_MAP.items():
        value = config.get(config_key, "")
        if value:
            st.session_state[state_key] = value

    # Fallback: asst_embed_key ← gemini_key se embedding_key não existir
    if not st.session_state.get("asst_embed_key"):
        gemini = config.get("gemini_key", "")
        if gemini:
            st.session_state["asst_embed_key"] = gemini

    # Preferências da sessão
    _apply_prefs_to_session(config)


def _apply_prefs_to_session(config: dict[str, str]) -> None:
    """Carrega preferências persistidas no banco de volta ao session_state."""
    import streamlit as st
    for state_key, (config_key, type_) in PREFS_MAP.items():
        raw = config.get(config_key, "")
        if not raw:
            continue
        if type_ == "bool":
            st.session_state[state_key] = raw.lower() == "true"
        elif type_ == "int":
            try:
                st.session_state[state_key] = int(raw)
            except ValueError:
                pass
        else:
            st.session_state[state_key] = raw


def mask_key(value: str) -> str:
    """Mascara uma API key para exibição."""
    if not value:
        return ""
    if len(value) <= 12:
        return "*" * len(value)
    return value[:4] + "•" * (len(value) - 8) + value[-4:]
