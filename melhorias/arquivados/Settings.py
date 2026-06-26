# pages/Settings.py — trecho a adicionar na aba "👥 Participantes"
# =============================================================================
# ATA Engine Integration — UI de Cadastro de Roster
# FGV/DTI · Equipe SOLCORP · Maio 2026
# =============================================================================
# Adicionar esta aba ao bloco de tabs existente em Settings.py.
# Pré-requisito: projeto selecionado em st.session_state["selected_project_id"].
#
# Padrão de mensagens persistidas (evita desaparecer com st.rerun()):
#   st.session_state["_roster_msg"] = ("success" | "error", "texto")
# =============================================================================

import re
import streamlit as st

from core.project_store import (
    get_project_roster,
    upsert_roster_member,
    deactivate_roster_member,
    reorder_roster,
    get_roster_attendance_summary,
    ATA_ENGINE_COLORS,
)
from modules.auth import is_admin

# Cores sugeridas como swatches — padrão do ATA Engine Design System
_COLOR_SWATCHES = [
    {"label": "Navy — cliente",    "hex": "0B1E3D"},
    {"label": "Blue — cliente",    "hex": "1A4B8C"},
    {"label": "Green — interno",   "hex": "1A7F5A"},
    {"label": "Amber — interno",   "hex": "C97B1A"},
    {"label": "Purple — interno",  "hex": "6B3FA0"},
    {"label": "Accent — neutro",   "hex": "2E7FD9"},
]


def render_roster_tab() -> None:
    """
    Renderiza a aba '👥 Participantes' em Settings.py.
    Deve ser chamada dentro do bloco de tabs de Settings:

        tab_proj, tab_roster, tab_db, ... = st.tabs([..., "👥 Participantes", ...])
        with tab_roster:
            render_roster_tab()
    """
    # ── Exibir mensagem persistida (pós-rerun) ───────────────────────────────
    if "_roster_msg" in st.session_state:
        level, text = st.session_state.pop("_roster_msg")
        if level == "success":
            st.success(text)
        else:
            st.error(text)

    # ── Verificar projeto selecionado ────────────────────────────────────────
    project_id = st.session_state.get("selected_project_id")
    if not project_id:
        st.info("Selecione um projeto na aba **Projeto** para gerenciar participantes.")
        return

    project_name = st.session_state.get("selected_project_name", project_id)

    st.markdown(
        f"Roster de participantes do projeto **{project_name}**. "
        "Esses cadastros alimentam automaticamente os chips das atas geradas pelo pipeline."
    )

    # ── Carregar roster ──────────────────────────────────────────────────────
    roster = get_project_roster(project_id, include_inactive=False)

    # ── Seção 1: Membros atuais ──────────────────────────────────────────────
    _render_roster_table(roster, project_id)

    st.divider()

    # ── Seção 2: Adicionar novo membro ───────────────────────────────────────
    if is_admin():
        _render_add_member_form(project_id, roster)
    else:
        st.caption("Apenas administradores podem adicionar ou remover participantes.")

    st.divider()

    # ── Seção 3: Resumo de presença (analytics) ──────────────────────────────
    with st.expander("📊 Histórico de presença", expanded=False):
        _render_attendance_summary(project_id)


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 1 — TABELA DE MEMBROS ATUAIS
# ─────────────────────────────────────────────────────────────────────────────

def _render_roster_table(roster: list[dict], project_id: str) -> None:
    """Exibe a tabela de membros do roster com ações inline de edição/desativação."""

    st.markdown("##### Membros cadastrados")

    if not roster:
        st.caption("Nenhum participante cadastrado. Use o formulário abaixo para adicionar.")
        return

    # Cabeçalho da tabela
    col_ini, col_nome, col_area, col_cor, col_aliases, col_actions = st.columns(
        [1, 2.5, 2, 1.2, 2.5, 1.5]
    )
    col_ini.markdown("**Sigla**")
    col_nome.markdown("**Nome completo**")
    col_area.markdown("**Área**")
    col_cor.markdown("**Cor**")
    col_aliases.markdown("**Aliases na transcrição**")
    col_actions.markdown("**Ações**")

    for member in roster:
        _render_roster_row(member, project_id)


def _render_roster_row(member: dict, project_id: str) -> None:
    """Renderiza uma linha da tabela com modo de visualização e edição inline."""

    edit_key = f"_roster_edit_{member['id']}"
    is_editing = st.session_state.get(edit_key, False)

    col_ini, col_nome, col_area, col_cor, col_aliases, col_actions = st.columns(
        [1, 2.5, 2, 1.2, 2.5, 1.5]
    )

    color_hex = member.get("color_hex", "8496B0")
    aliases_str = ", ".join(member.get("name_aliases") or [])

    if not is_editing:
        # ── Modo visualização ────────────────────────────────────────────────
        col_ini.markdown(
            f'<span style="display:inline-block;background:#{color_hex};'
            f'color:white;padding:2px 8px;border-radius:4px;'
            f'font-weight:700;font-family:monospace;font-size:13px;">'
            f'{member["initials"]}</span>',
            unsafe_allow_html=True,
        )
        col_nome.write(member["full_name"])
        col_area.write(member.get("area") or "—")
        col_cor.markdown(
            f'<div style="display:flex;align-items:center;gap:6px;">'
            f'<div style="width:18px;height:18px;border-radius:3px;'
            f'background:#{color_hex};border:1px solid #ccc;"></div>'
            f'<code style="font-size:11px;">#{color_hex}</code></div>',
            unsafe_allow_html=True,
        )
        col_aliases.caption(aliases_str or "—")

        with col_actions:
            btn_col1, btn_col2 = st.columns(2)
            if is_admin():
                if btn_col1.button("✏️", key=f"edit_{member['id']}", help="Editar"):
                    st.session_state[edit_key] = True
                    st.rerun()
                if btn_col2.button("🗑️", key=f"del_{member['id']}", help="Desativar"):
                    ok = deactivate_roster_member(member["id"])
                    if ok:
                        st.session_state["_roster_msg"] = (
                            "success",
                            f"Participante {member['initials']} desativado."
                        )
                    else:
                        st.session_state["_roster_msg"] = (
                            "error",
                            f"Erro ao desativar {member['initials']}."
                        )
                    st.rerun()

    else:
        # ── Modo edição inline ───────────────────────────────────────────────
        with st.container():
            st.markdown(f"**Editando: {member['initials']} — {member['full_name']}**")

            ec1, ec2 = st.columns(2)
            new_name = ec1.text_input(
                "Nome completo",
                value=member["full_name"],
                key=f"e_name_{member['id']}",
            )
            new_area = ec2.text_input(
                "Área / Equipe",
                value=member.get("area") or "",
                key=f"e_area_{member['id']}",
            )

            ec3, ec4 = st.columns(2)
            new_aliases_raw = ec3.text_input(
                "Aliases (separados por vírgula)",
                value=aliases_str,
                key=f"e_aliases_{member['id']}",
                help="Variações do nome como aparecem na transcrição",
            )
            new_color = ec4.text_input(
                "Cor hex (sem #)",
                value=color_hex,
                max_chars=6,
                key=f"e_color_{member['id']}",
            )

            _render_color_swatches(f"sw_{member['id']}", f"e_color_{member['id']}")

            save_col, cancel_col = st.columns([1, 3])
            if save_col.button("💾 Salvar", key=f"save_{member['id']}"):
                new_aliases = [
                    a.strip() for a in new_aliases_raw.split(",") if a.strip()
                ]
                try:
                    result = upsert_roster_member(project_id, {
                        "initials":     member["initials"],
                        "full_name":    new_name,
                        "area":         new_area,
                        "color_hex":    new_color,
                        "name_aliases": new_aliases,
                        "sort_order":   member.get("sort_order", 0),
                    })
                    if result:
                        st.session_state["_roster_msg"] = (
                            "success",
                            f"Participante {member['initials']} atualizado."
                        )
                        st.session_state.pop(edit_key, None)
                    else:
                        st.session_state["_roster_msg"] = (
                            "error",
                            "Falha ao salvar. Verifique o console."
                        )
                except ValueError as e:
                    st.session_state["_roster_msg"] = ("error", str(e))
                st.rerun()

            if cancel_col.button("Cancelar", key=f"cancel_{member['id']}"):
                st.session_state.pop(edit_key, None)
                st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 2 — FORMULÁRIO DE NOVO MEMBRO
# ─────────────────────────────────────────────────────────────────────────────

def _render_add_member_form(project_id: str, existing_roster: list[dict]) -> None:
    """Formulário para adicionar novo membro ao roster."""

    existing_initials = {m["initials"] for m in existing_roster}
    next_sort = len(existing_roster)

    with st.expander("➕ Adicionar participante", expanded=False):
        st.markdown(
            "Cadastre aqui as pessoas que podem aparecer como participantes nas reuniões "
            "deste projeto. O pipeline usará este cadastro para gerar os chips da ata automaticamente."
        )

        fc1, fc2 = st.columns(2)
        new_ini = fc1.text_input(
            "Sigla *",
            max_chars=4,
            placeholder="MF",
            help="1 a 4 letras maiúsculas — ex: MF, JL, NC, PG",
            key="new_ini",
        ).upper().strip()
        new_name = fc2.text_input(
            "Nome completo *",
            placeholder="Maria de Fátima Duarte Moura",
            key="new_name",
        ).strip()

        fc3, fc4 = st.columns(2)
        new_area = fc3.text_input(
            "Área / Equipe",
            placeholder="Auditoria, DTI/SOLCORP, …",
            key="new_area",
        ).strip()
        new_color = fc4.text_input(
            "Cor hex (sem #) *",
            placeholder="0B1E3D",
            max_chars=6,
            key="new_color",
            help="Tons escuros para cliente, médios para equipe interna",
        ).upper().strip()

        st.caption("Sugestões de cor:")
        _render_color_swatches("sw_new", "new_color")

        new_aliases_raw = st.text_input(
            "Aliases na transcrição (separados por vírgula)",
            placeholder="Maria, Fátima, Maria de Fátima",
            key="new_aliases",
            help="Variações do nome como podem aparecer nas transcrições de reuniões",
        )

        # Validação em tempo real
        errors = []
        if new_ini and not re.match(r"^[A-Z]{1,4}$", new_ini):
            errors.append("Sigla deve ter 1 a 4 letras maiúsculas.")
        if new_ini and new_ini in existing_initials:
            errors.append(f"Sigla '{new_ini}' já existe no roster deste projeto.")
        if new_color and not re.match(r"^[0-9A-Fa-f]{6}$", new_color):
            errors.append("Cor deve ser um hex de 6 caracteres (ex: 0B1E3D).")

        for err in errors:
            st.warning(err)

        btn_disabled = bool(
            errors or not new_ini or not new_name or not new_color
        )

        if st.button("Adicionar participante", disabled=btn_disabled, type="primary"):
            aliases = [a.strip() for a in new_aliases_raw.split(",") if a.strip()]
            try:
                result = upsert_roster_member(project_id, {
                    "initials":     new_ini,
                    "full_name":    new_name,
                    "area":         new_area,
                    "color_hex":    new_color,
                    "name_aliases": aliases,
                    "sort_order":   next_sort,
                    "is_active":    True,
                })
                if result:
                    st.session_state["_roster_msg"] = (
                        "success",
                        f"✓ Participante {new_ini} — {new_name} adicionado ao roster."
                    )
                    # Limpar campos do formulário
                    for k in ["new_ini", "new_name", "new_area", "new_color", "new_aliases"]:
                        st.session_state.pop(k, None)
                else:
                    st.session_state["_roster_msg"] = (
                        "error",
                        "Falha ao adicionar participante. Verifique o console."
                    )
            except ValueError as e:
                st.session_state["_roster_msg"] = ("error", str(e))
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# SEÇÃO 3 — RESUMO DE PRESENÇA
# ─────────────────────────────────────────────────────────────────────────────

def _render_attendance_summary(project_id: str) -> None:
    """Exibe quantas reuniões cada participante esteve presente."""

    summary = get_roster_attendance_summary(project_id)

    if not summary:
        st.caption("Nenhum dado de presença disponível.")
        return

    st.markdown("Participação acumulada por membro do roster:")

    for item in summary:
        color_hex = item.get("color_hex", "8496B0")
        col_badge, col_name, col_bar = st.columns([1, 3, 4])

        col_badge.markdown(
            f'<span style="display:inline-block;background:#{color_hex};'
            f'color:white;padding:2px 8px;border-radius:4px;'
            f'font-weight:700;font-family:monospace;font-size:13px;">'
            f'{item["initials"]}</span>',
            unsafe_allow_html=True,
        )
        col_name.write(item["full_name"])
        col_bar.progress(
            min(1.0, item["confirmed_meetings"] / max(1, item["total_meetings"])),
            text=f'{item["confirmed_meetings"]} reunião(ões)',
        )


# ─────────────────────────────────────────────────────────────────────────────
# HELPER: swatches de cor
# ─────────────────────────────────────────────────────────────────────────────

def _render_color_swatches(key_prefix: str, target_input_key: str) -> None:
    """
    Renderiza swatches clicáveis das cores padrão do ATA Engine.
    Ao clicar, preenche o campo `target_input_key` com o hex correspondente.
    """
    cols = st.columns(len(_COLOR_SWATCHES))
    for i, swatch in enumerate(_COLOR_SWATCHES):
        with cols[i]:
            st.markdown(
                f'<div title="{swatch["label"]}" style="'
                f'width:24px;height:24px;border-radius:4px;'
                f'background:#{swatch["hex"]};'
                f'border:1px solid #ccc;margin:auto;"></div>',
                unsafe_allow_html=True,
            )
            if st.button(
                swatch["hex"],
                key=f"{key_prefix}_{swatch['hex']}",
                help=swatch["label"],
            ):
                st.session_state[target_input_key] = swatch["hex"]
                st.rerun()


# =============================================================================
# INTEGRAÇÃO EM Settings.py — como adicionar esta aba
# =============================================================================
#
# No bloco de tabs existente em pages/Settings.py, adicionar:
#
#   from pages._settings_roster import render_roster_tab
#
#   tab_llm, tab_proj, tab_roster, tab_db, tab_asst = st.tabs([
#       "🤖 Modelos",
#       "📁 Projeto",
#       "👥 Participantes",   # ← nova aba
#       "🗄️ Banco de Dados",
#       "💬 Assistente",
#   ])
#
#   with tab_roster:
#       render_roster_tab()
#
# Também adicionar ao seletor de projeto em tab_proj:
#
#   ata_slug = st.text_input(
#       "Slug da ata (para localStorage)",
#       value=project.get("ata_slug") or "",
#       placeholder="sdea",
#       help="Usado nas chaves localStorage das atas: {slug}_{ano}_{mes}_{dia}_v1",
#   )
#   meeting_location = st.text_input(
#       "Local padrão das reuniões",
#       value=project.get("meeting_location") or "Videoconferência",
#   )
#   # Salvar ao clicar em "Atualizar projeto":
#   # client.table("projects").update({"ata_slug": ata_slug, ...}).eq("id", project_id).execute()
#
# =============================================================================
