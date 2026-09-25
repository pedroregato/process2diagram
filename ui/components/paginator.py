# ui/components/paginator.py
# ─────────────────────────────────────────────────────────────────────────────
# Paginação reutilizável (NAV-09, melhorias/parciais/navegabilidade.md).
#
# Extraído da lógica que existia duplicada em pages/ArtefatosModelagem.py
# (PC178 — paginação SBVR) e pages/ValidationHub.py::_paginate (PC212/NAV-03).
# Ambos foram refatorados pra usar este componente.
#
# Por que isso importa: st.tabs()/expanders renderizados sem limite escalam
# com o volume de dados do contexto, não com o que cabe na tela — um
# contexto grande (ex.: SDEA, 751 termos SBVR / 2.252 artefatos de
# Validação) gerava milhares de widgets numa página só, correlacionado com
# quedas de sessão e "Bad 'setIn' index" no frontend (PC176-178, PC212).
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import streamlit as st

_DEFAULT_PAGE_SIZES = (25, 50, 100)


def paginate(
    items: list,
    key_prefix: str,
    filter_sig: str = "",
    page_sizes: tuple[int, ...] = _DEFAULT_PAGE_SIZES,
    show_size_selector: bool = True,
) -> list:
    """Pagina uma lista já filtrada. Renderiza navegação ← Anterior / Próximo →
    com legenda "X–Y de N · Pág. P/N" só quando há mais de 1 página, e
    (opcionalmente) um seletor de itens-por-página.

    Args:
        items: lista já filtrada (meeting/status/o que for) — a paginação
            em si não filtra nada, só fatia.
        key_prefix: prefixo único pros widgets e chaves de session_state
            desta paginação (ex. "req", "sbvr_t") — precisa ser único por
            aba/seção na mesma página.
        filter_sig: assinatura textual dos filtros ativos (ex.
            f"{project_id}|{status}"). Quando muda em relação à última
            renderização, a página volta pra 0 automaticamente. Vazio
            (padrão) = a paginação nunca reseta sozinha.
        page_sizes: tamanhos de página oferecidos no seletor (o primeiro é
            o padrão inicial).
        show_size_selector: False renderiza só a navegação, sem seletor de
            tamanho — usa page_sizes[0] fixo (mesmo comportamento do padrão
            SBVR original, PC178).

    Returns:
        A fatia de `items` correspondente à página atual.
    """
    sig_key = f"_pg_last_filter_{key_prefix}"
    if filter_sig and st.session_state.get(sig_key) != filter_sig:
        st.session_state[f"pg_page_{key_prefix}"] = 0
        st.session_state[sig_key] = filter_sig

    page_key = f"pg_page_{key_prefix}"
    size_key = f"pg_size_{key_prefix}"
    n = len(items)

    if show_size_selector:
        c_size, c_nav = st.columns([1, 3])
        with c_size:
            page_size = st.selectbox(
                "Itens por página", list(page_sizes),
                index=list(page_sizes).index(st.session_state.get(size_key, page_sizes[0])),
                key=size_key,
            )
    else:
        page_size = page_sizes[0]
        c_nav = st.container()

    n_pages = max(1, (n + page_size - 1) // page_size)
    page  = min(st.session_state.get(page_key, 0), n_pages - 1)
    start = page * page_size
    end   = min(start + page_size, n)

    if n > page_size:
        with c_nav:
            nv1, nv2, nv3 = st.columns([1, 1, 2])
            with nv1:
                if st.button("← Anterior", key=f"{key_prefix}_prev", disabled=(page == 0)):
                    st.session_state[page_key] = page - 1
                    st.rerun()
            with nv2:
                if st.button("Próximo →", key=f"{key_prefix}_next", disabled=(page == n_pages - 1)):
                    st.session_state[page_key] = page + 1
                    st.rerun()
            with nv3:
                st.caption(f"**{start + 1}–{end}** de **{n}** · Pág. **{page + 1}/{n_pages}**")

    return items[start:end]
