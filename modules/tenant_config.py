# modules/tenant_config.py
# ─────────────────────────────────────────────────────────────────────────────
# Gerenciamento de configurações por tenant (API keys, preferências).
#
# As configurações ficam na tabela tenant_config (Supabase).
# Após login, apply_config_to_session() popula st.session_state com as API
# keys do tenant — o sidebar lê exatamente esses mesmos keys, sem alteração.
#
# Para evoluir para criptografia (AES-256), alterar apenas _encode()/_decode().
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from modules.supabase_client import get_supabase_client

# Mapeamento: nome do provider na app → config_key no banco
PROVIDER_KEY_MAP: dict[str, str] = {
    "DeepSeek":  "deepseek_key",
    "OpenAI":    "openai_key",
    "Groq":      "groq_key",
    "Anthropic": "anthropic_key",
    "Gemini":    "gemini_key",
    "Embedding": "embedding_key",
}


# ── Hooks de criptografia (plaintext por ora — trocar por AES-256 em produção) ─

def _encode(value: str) -> str:
    """Prepara o valor para armazenar no banco. Substituir por encrypt() em produção."""
    return value


def _decode(value: str) -> str:
    """Recupera o valor armazenado no banco. Substituir por decrypt() em produção."""
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
            {
                "tenant_id":    tenant_id,
                "config_key":   key,
                "config_value": _encode(value),
                "updated_at":   "now()",
            },
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
        (
            client.table("tenant_config")
            .delete()
            .eq("tenant_id", tenant_id)
            .eq("config_key", key)
            .execute()
        )
        return True
    except Exception:
        return False


# ── Integração com session_state ──────────────────────────────────────────────

def apply_config_to_session(config: dict[str, str]) -> None:
    """Popula st.session_state com as API keys do tenant.

    Deve ser chamado imediatamente após login_tenant() bem-sucedido.
    O sidebar lê st.session_state["api_key_{Provider}"] — sem alteração no sidebar.
    """
    import streamlit as st

    for provider, key_name in PROVIDER_KEY_MAP.items():
        value = config.get(key_name, "")
        if value:
            st.session_state[f"api_key_{provider}"] = value

    # Embedding key também alimenta o campo de embedding do Assistente
    embed_key = config.get("embedding_key") or config.get("gemini_key", "")
    if embed_key:
        st.session_state["asst_embed_key"] = embed_key


def mask_key(value: str) -> str:
    """Mascara uma API key para exibição: mostra apenas os 4 primeiros e 4 últimos chars."""
    if not value:
        return ""
    if len(value) <= 12:
        return "*" * len(value)
    return value[:4] + "•" * (len(value) - 8) + value[-4:]
