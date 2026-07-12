# modules/session_security.py
# ─────────────────────────────────────────────────────────────────────────────
# Security strategy: API keys are stored ONLY in st.session_state.
#
# Why this is safe for Streamlit Cloud:
#   • st.session_state lives in the server-side session for a single user tab.
#   • It is never written to disk, logs, or any database.
#   • When the tab is closed or the session expires, the key is gone.
#   • Keys are never echoed in the UI (type="password" + masked display).
#   • No key is sent to any third party except the chosen LLM provider directly.
#
# What this does NOT protect against:
#   • A compromised Streamlit Cloud server (use st.secrets for server-side keys).
#   • The user accidentally sharing their screen while entering the key.
#
# For production multi-user deployments, consider:
#   • OAuth login + encrypted vault per user (e.g. AWS Secrets Manager).
#   • Proxy pattern: backend holds the key, frontend never sees it.
# ─────────────────────────────────────────────────────────────────────────────

import streamlit as st


_SESSION_KEY_PREFIX = "_llm_apikey_"  # namespace in session_state


def _session_key(provider: str) -> str:
    """Returns the session_state key for a given provider's API key."""
    return f"{_SESSION_KEY_PREFIX}{provider.replace(' ', '_').lower()}"


def render_api_key_gate(provider: str, provider_cfg: dict) -> None:
    """
    Renders the API key input in the sidebar.
    The key is stored exclusively in st.session_state — never in a file or DB.
    If provider_cfg has 'api_key_alias', uses that provider's stored key instead
    of asking for a new one (shared key pattern for provider variants).
    """
    alias = provider_cfg.get("api_key_alias")
    if alias:
        # This provider shares an API key with another provider — don't ask again.
        sk = _session_key(alias)
        stored = st.session_state.get(sk, "")
        st.markdown("### 🔑 API Key")
        if stored:
            masked = stored[:8] + "••••••••" + stored[-4:] if len(stored) > 12 else "••••••••"
            st.success(f"Key active (via **{alias}**): `{masked}`")
        else:
            st.warning(f"Chave não configurada. Configure em **{alias}** — esta variante compartilha a mesma API key.")
        return

    sk = _session_key(provider)
    stored = st.session_state.get(sk, "")

    st.markdown(f"### 🔑 API Key")

    if stored:
        # Show masked version + clear button
        masked = stored[:8] + "••••••••" + stored[-4:] if len(stored) > 12 else "••••••••"
        st.success(f"Key active: `{masked}`")
        if st.button("🗑 Clear key", key=f"clear_{provider}"):
            del st.session_state[sk]
            st.rerun()
    else:
        key_input = st.text_input(
            provider_cfg["api_key_label"],
            type="password",
            placeholder=f"{provider_cfg['api_key_prefix']}...",
            help=provider_cfg["api_key_help"],
            key=f"input_{provider}",
        )
        if st.button("✅ Save key for this session", key=f"save_{provider}"):
            if key_input and len(key_input.strip()) > 10:
                st.session_state[sk] = key_input.strip()
                st.rerun()
            else:
                st.error("Key seems too short. Check and try again.")


def _extra_field_key(provider: str, field_key: str) -> str:
    """Session key for a provider-specific non-secret config field (e.g. an
    Azure OpenAI endpoint URL) — separate namespace from _session_key(),
    which is reserved for the API key itself."""
    return f"_llm_extra_{provider.replace(' ', '_').lower()}_{field_key}"


def render_extra_fields(provider: str, provider_cfg: dict) -> None:
    """
    Renders any additional (non-secret) config fields a provider needs beyond
    a single API key — e.g. Azure OpenAI needs a per-resource endpoint URL,
    since (unlike every other provider here) that URL isn't the same for
    every user of the app. Declared via provider_cfg["extra_fields"]:
    a list of {"key", "label", "placeholder", "help"} dicts. No-op for
    providers that don't declare any (i.e. everyone except Azure OpenAI today).
    """
    for field in provider_cfg.get("extra_fields", []):
        sk = _extra_field_key(provider, field["key"])
        # key=sk makes the widget itself the persistence store — Streamlit
        # keeps st.session_state[sk] in sync across reruns automatically.
        st.text_input(
            field["label"],
            placeholder=field.get("placeholder", ""),
            help=field.get("help", ""),
            key=sk,
        )


def get_extra_field(provider: str, field_key: str) -> str:
    """Reads a provider-specific extra field saved by render_extra_fields()."""
    return st.session_state.get(_extra_field_key(provider, field_key), "")


def render_api_key_readonly(provider: str) -> str:
    """
    Displays the API key status for the given provider (read-only).
    Reads from the canonical session_state key set by Settings.
    If the provider has api_key_alias, reads from the aliased provider's key.
    Returns the stored key value (or "" if not configured).
    """
    from modules.config import AVAILABLE_PROVIDERS
    pcfg = AVAILABLE_PROVIDERS.get(provider, {})
    key_provider = pcfg.get("api_key_alias", provider)
    sk = _session_key(key_provider)
    stored = st.session_state.get(sk, "")
    if stored:
        masked = stored[:6] + "••••••••" + stored[-4:] if len(stored) > 10 else "••••••••"
        st.success(f"🔑 Chave ativa: `{masked}`")
    else:
        st.warning("🔑 Chave não configurada.")
        st.caption("Configure em **⚙️ Configurações** antes de prosseguir.")
    return stored


def render_session_key_readonly(state_key: str, label: str = "API Key") -> str:
    """
    Displays the key status for an arbitrary session_state key (read-only).
    Used for non-provider keys like 'asst_api_key' and 'asst_embed_key'.
    Returns the stored key value (or "" if not configured).
    """
    stored = st.session_state.get(state_key, "")
    if stored:
        masked = stored[:6] + "••••••••" + stored[-4:] if len(stored) > 10 else "••••••••"
        st.success(f"🔑 {label} ativa: `{masked}`")
    else:
        st.warning(f"🔑 {label} não configurada.")
        st.caption("Configure em **⚙️ Configurações** antes de prosseguir.")
    return stored


def get_session_llm_client(provider: str) -> dict | None:
    """
    Returns a dict with the API key and provider config if the key is set,
    or None if the user hasn't entered a key yet.

    If the provider has api_key_alias in AVAILABLE_PROVIDERS, the aliased
    provider's session key is used (shared key for provider variants).

    The caller (extract_llm.py) uses this dict to build the actual client.
    The raw key never leaves this module except to the LLM SDK call.
    """
    from modules.config import AVAILABLE_PROVIDERS
    pcfg = AVAILABLE_PROVIDERS.get(provider, {})
    key_provider = pcfg.get("api_key_alias", provider)
    sk = _session_key(key_provider)
    api_key = st.session_state.get(sk)
    if not api_key:
        return None
    return {"api_key": api_key, "provider": provider}
