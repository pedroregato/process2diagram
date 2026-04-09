# modules/supabase_client.py
# ─────────────────────────────────────────────────────────────────────────────
# Singleton do cliente Supabase.
#
# Lê credenciais de st.secrets["supabase"] (Streamlit Cloud / local dev).
# Retorna None se não configurado — funcionalidades de projeto ficam
# desabilitadas sem quebrar o pipeline principal.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import streamlit as st

_client = None  # singleton em memória durante a sessão


def get_supabase_client():
    """Retorna o cliente Supabase ou None se não configurado."""
    global _client
    if _client is not None:
        return _client

    try:
        url = st.secrets["supabase"]["url"]
        key = st.secrets["supabase"]["key"]
    except Exception:
        return None  # Supabase não configurado — modo sem persistência

    try:
        from supabase import create_client
        _client = create_client(url, key)
        return _client
    except Exception as exc:
        st.warning(f"⚠️ Supabase indisponível: {exc}")
        return None


def supabase_configured() -> bool:
    """True quando as credenciais Supabase estão presentes."""
    try:
        st.secrets["supabase"]["url"]
        st.secrets["supabase"]["key"]
        return True
    except Exception:
        return False
