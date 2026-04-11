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
from core.project_store import list_projects, create_project, list_bpmn_processes


_NEW  = "➕  Novo projeto"
_AUTO = "🔄  Auto-detectar (recomendado)"
_NEW_PROC = "➕  Novo processo"


def _init():
    for key, default in [
        ("project_id",                  None),
        ("project_name",                ""),
        ("meeting_title",               ""),
        ("meeting_date",                date.today()),
        ("current_meeting_id",          None),
        ("project_confirmed",           False),
        # BPMN process selector (Option B)
        ("bpmn_process_id",             None),   # None = auto slug matching
        ("bpmn_process_override_name",  ""),     # non-empty = create new with this name
        ("bpmn_process_display",        ""),     # label shown in confirmed badge
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

    # Reseta seleção de processo BPMN ao trocar de projeto/reunião
    st.session_state.bpmn_process_id            = None
    st.session_state.bpmn_process_override_name = ""
    st.session_state.bpmn_process_display       = ""

    st.rerun()


def render_bpmn_process_selector() -> None:
    """Seletor opcional de processo BPMN — Opção B (curadoria humana).

    Permite que o usuário vincule explicitamente a reunião atual a um processo
    BPMN já existente ou defina um nome para um novo processo.

    Aparece apenas quando:
    - Supabase está configurado
    - Projeto já foi confirmado (``project_confirmed = True``)

    Se o usuário não interagir, o sistema usa detecção automática por slug
    (Opção A) ao salvar o BPMN.
    """
    if not supabase_configured():
        return
    if not st.session_state.get("project_confirmed"):
        return

    project_id = st.session_state.project_id
    processes  = list_bpmn_processes(project_id)

    # Badge compacto quando já há uma seleção explícita
    if st.session_state.bpmn_process_display:
        col_info, col_btn = st.columns([5, 1])
        with col_info:
            st.info(f"📐 Processo BPMN: **{st.session_state.bpmn_process_display}**")
        with col_btn:
            if st.button("Alterar", key="change_bpmn_proc_btn"):
                st.session_state.bpmn_process_id            = None
                st.session_state.bpmn_process_override_name = ""
                st.session_state.bpmn_process_display       = ""
                st.rerun()
        return

    with st.expander("📐 Processo BPMN — vincular explicitamente (opcional)", expanded=False):
        st.caption(
            "Por padrão o sistema identifica o processo automaticamente pelo nome do diagrama. "
            "Use esta seleção apenas quando quiser vincular ou criar um processo manualmente."
        )

        proc_options = [_AUTO] + [p["name"] for p in processes] + [_NEW_PROC]
        sel_proc = st.selectbox(
            "Processo BPMN",
            proc_options,
            key="bpmn_proc_sel",
            help="Selecione um processo existente, crie um novo ou deixe o sistema decidir.",
        )

        new_proc_name = ""
        if sel_proc == _NEW_PROC:
            new_proc_name = st.text_input(
                "Nome do novo processo *",
                key="bpmn_new_proc_name",
                placeholder="Ex: Gestão de Contratos, Onboarding de Clientes…",
            )

        if st.button("✅ Confirmar processo", key="confirm_bpmn_proc_btn"):
            if sel_proc == _AUTO:
                st.session_state.bpmn_process_id            = None
                st.session_state.bpmn_process_override_name = ""
                st.session_state.bpmn_process_display       = "Auto-detectar"
            elif sel_proc == _NEW_PROC:
                if not new_proc_name.strip():
                    st.error("Informe o nome do novo processo.")
                    return
                st.session_state.bpmn_process_id            = None
                st.session_state.bpmn_process_override_name = new_proc_name.strip()
                st.session_state.bpmn_process_display       = new_proc_name.strip()
            else:
                proc = next((p for p in processes if p["name"] == sel_proc), None)
                if not proc:
                    st.error("Processo não encontrado.")
                    return
                st.session_state.bpmn_process_id            = proc["id"]
                st.session_state.bpmn_process_override_name = ""
                st.session_state.bpmn_process_display       = proc["name"]
            st.rerun()
