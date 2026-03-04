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
    """
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


def get_session_llm_client(provider: str) -> dict | None:
    """
    Returns a dict with the API key and provider config if the key is set,
    or None if the user hasn't entered a key yet.

    The caller (extract_llm.py) uses this dict to build the actual client.
    The raw key never leaves this module except to the LLM SDK call.
    """
    sk = _session_key(provider)
    api_key = st.session_state.get(sk)
    if not api_key:
        return None
    return {"api_key": api_key, "provider": provider}
