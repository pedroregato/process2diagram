# ui/components/deep_links.py
# ─────────────────────────────────────────────────────────────────────────────
# NAV-12 (melhorias/parciais/navegabilidade.md) — deep links entre páginas.
#
# Dois mecanismos combinados:
#   1. st.query_params (?ctx=&meeting=&process=&v=) — sobrevive a um F5 e a
#      um link aberto direto no navegador (sessão nova, sem session_state
#      prévio) — é o que torna a URL "compartilhável"/"favoritável".
#   2. st.session_state["_pending_*"] — usado junto de st.switch_page() para
#      navegação DENTRO da mesma sessão (ex.: cards de "Reuniões recentes"
#      da Central) — mais direto que depender só da URL nesse caso, e
#      funciona mesmo se o valor não for serializável em texto de URL.
#
# resolve_context_from_query_params() reforça NAV-01: uma ?ctx= que não
# pertence ao tenant da sessão atual é ignorada, e o bloqueio é registrado
# no log — nunca ativa contexto de outro tenant a partir de um link externo.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import logging

import streamlit as st

logger = logging.getLogger(__name__)


def resolve_context_from_query_params() -> None:
    """Se a URL tiver ?ctx=<sigla>, ativa esse contexto — desde que a sigla
    pertença ao tenant da sessão atual. Sem ?ctx= ou sem tenant/sigla
    correspondente: não faz nada (fail-open, nunca bloqueia a página)."""
    sigla = st.query_params.get("ctx")
    if not sigla:
        return

    from core.project_store import list_contexts

    tenant_id = st.session_state.get("_tenant_id")
    try:
        contexts = list_contexts(tenant_id=tenant_id)
    except Exception:
        return

    match = next(
        (c for c in contexts if (c.get("sigla") or "").strip().upper() == sigla.strip().upper()),
        None,
    )
    if not match:
        logger.warning(
            "NAV-12: link com ?ctx=%s ignorado — sigla nao encontrada no tenant ativo (tenant_id=%s)",
            sigla, tenant_id,
        )
        return

    if st.session_state.get("active_project_id") != match["id"]:
        from ui.project_selector import activate_context
        activate_context(match)


def get_query_param_int(name: str) -> int | None:
    """Lê ?<name>= da URL como inteiro. None se ausente ou não-numérico."""
    raw = st.query_params.get(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def get_query_param_str(name: str) -> str | None:
    return st.query_params.get(name) or None


def pop_pending(key: str):
    """Consome (uma vez) um valor de navegação DENTRO da sessão, deixado
    por um st.switch_page() disparado de outra página (ex.: Home.py)."""
    return st.session_state.pop(f"_pending_{key}", None)


def active_context_sigla() -> str:
    """Sigla do contexto ativo, derivada de session_state.prefix (mesma
    fonte usada por ui/project_selector.py para o prefixo de exportação).
    String vazia se não houver contexto ativo ou sigla configurada."""
    prefix = st.session_state.get("prefix", "") or ""
    return prefix.rstrip("_")
