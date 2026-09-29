# ui/components/safe_page_link.py
# ─────────────────────────────────────────────────────────────────────────────
# st.page_link() que nunca derruba a página com StreamlitPageNotFoundError
# (UX-01, achado em auditoria de produção 2026-09-28 — melhorias/ux-amigabilidade-e-elegancia.md).
#
# app.py monta st.navigation(pages) com base em is_admin() calculado ANTES
# de apply_auth_gate() — numa restauração de sessão (NAV-05), a MESMA
# execução pode ter session_state já com o papel correto (is_admin()==True
# em qualquer página) enquanto o menu registrado nesta passada ainda reflete
# o papel ANTIGO. A causa raiz foi corrigida em ui/auth_gate.py (rerun
# forçado logo após restaurar a sessão), mas um link pra uma página
# admin-only nunca deveria derrubar a tela pro usuário mesmo assim — esta é
# a camada de defesa, não o fix principal.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import streamlit as st
from streamlit.errors import StreamlitPageNotFoundError


def safe_page_link(page: str, *, label: str, icon: str | None = None,
                    use_container_width: bool = False, help: str | None = None) -> None:
    """Como st.page_link(), mas nunca lança StreamlitPageNotFoundError — cai
    num st.caption() desabilitado se a página ainda não estiver registrada
    no st.navigation() desta execução (ex.: janela de 1 rerun logo após uma
    sessão persistente ser restaurada, antes do menu se realinhar)."""
    try:
        st.page_link(page, label=label, icon=icon,
                     use_container_width=use_container_width, help=help)
    except StreamlitPageNotFoundError:
        st.caption(f"{icon or ''} {label} — carregando menu…".strip())
