# ui/project_selector.py
# ─────────────────────────────────────────────────────────────────────────────
# Seleção / criação de projeto e metadados da reunião.
# Renderiza um expander compacto acima da área de input.
# Armazena a seleção em st.session_state (project_id, project_name,
# meeting_title, meeting_date). Não bloqueia o pipeline se o Supabase
# não estiver configurado.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from datetime import date

import streamlit as st

from modules.supabase_client import supabase_configured
from core.project_store import list_projects, create_project


_NEW = "➕  Novo projeto"


def _init():
    for key, default in [
        ("project_id",        None),
        ("project_name",      ""),
        ("meeting_title",     ""),
        ("meeting_date",      date.today()),
        ("current_meeting_id", None),
        ("project_confirmed", False),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default


def render_project_selector() -> None:
    """Renderiza o seletor de projeto/reunião.

    - Se Supabase não configurado: exibe aviso e retorna (pipeline não bloqueado).
    - Se já confirmado: exibe badge compacto com opção de trocar.
    - Caso contrário: exibe formulário de seleção/criação.
    """
    _init()

    if not supabase_configured():
        st.info("💡 Supabase não configurado — execução sem persistência de projeto.", icon="ℹ️")
        return

    # ── Já confirmado: badge compacto ────────────────────────────────────────
    if st.session_state.project_confirmed:
        col_info, col_btn = st.columns([5, 1])
        with col_info:
            sigla_badge = f"`{st.session_state.prefix.rstrip('_')}` · " if st.session_state.get("prefix", "P2D_") != "P2D_" else ""
            st.success(
                f"📁 {sigla_badge}**{st.session_state.project_name}** · "
                f"📝 {st.session_state.meeting_title or '(sem título)'} · "
                f"📅 {st.session_state.meeting_date}"
            )
        with col_btn:
            if st.button("Trocar", key="change_project_btn"):
                st.session_state.project_confirmed = False
                st.session_state.current_meeting_id = None
                st.rerun()
        return

    # ── Formulário de seleção ────────────────────────────────────────────────
    with st.expander("📁 Projeto / Reunião — obrigatório para salvar resultados",
                     expanded=True):

        projects = list_projects()
        project_names = [p["name"] for p in projects]
        options = project_names + [_NEW]

        col_proj, col_title, col_date = st.columns([2, 2, 1])

        with col_proj:
            sel = st.selectbox("Projeto / Iniciativa", options,
                               key="proj_sel",
                               help="Selecione um projeto existente ou crie um novo")

        with col_title:
            title = st.text_input("Título da reunião",
                                  key="meeting_title_input",
                                  placeholder="Ex: Kickoff, Sprint 3, Homologação...")

        with col_date:
            meeting_dt = st.date_input("Data", value=date.today(), key="meeting_date_input")

        # Campos extras para novo projeto
        new_name = new_sigla = new_desc = ""
        if sel == _NEW:
            col_n, col_s, col_d = st.columns([2, 1, 2])
            with col_n:
                new_name = st.text_input("Nome do projeto *", key="new_proj_name",
                                         placeholder="Nome completo do projeto")
            with col_s:
                new_sigla = st.text_input("Sigla *", key="new_proj_sigla",
                                           placeholder="Ex: SDEA",
                                           max_chars=10,
                                           help="Sigla em maiúsculas — usada como prefixo nos artefatos exportados")
            with col_d:
                new_desc = st.text_input("Descrição (opcional)", key="new_proj_desc",
                                          placeholder="Contexto ou objetivo do projeto")

        if st.button("✅ Confirmar projeto", key="confirm_project_btn",
                     type="primary", use_container_width=True):
            _handle_confirm(projects, sel, new_name, new_sigla, new_desc, title, meeting_dt)


def _handle_confirm(projects, sel, new_name, new_sigla, new_desc, title, meeting_dt):
    if not title.strip():
        st.error("Informe o título da reunião.")
        return

    if sel == _NEW:
        if not new_name.strip():
            st.error("Informe o nome do novo projeto.")
            return
        if not new_sigla.strip():
            st.error("Informe a sigla do projeto.")
            return
        project = create_project(new_name.strip(), new_desc.strip(), new_sigla.strip())
        if not project:
            st.error("Erro ao criar projeto no Supabase.")
            return
    else:
        project = next((p for p in projects if p["name"] == sel), None)
        if not project:
            st.error("Projeto não encontrado.")
            return

    st.session_state.project_id        = project["id"]
    st.session_state.project_name      = project["name"]
    st.session_state.meeting_title     = title.strip()
    st.session_state.meeting_date      = meeting_dt
    st.session_state.project_confirmed = True

    # Auto-prefixo: sigla do projeto → prefixo dos artefatos exportados
    sigla = project.get("sigla", "").strip()
    if sigla:
        st.session_state.prefix = sigla + "_"

    st.rerun()
