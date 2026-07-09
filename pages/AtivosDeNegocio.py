# pages/AtivosDeNegocio.py
# ─────────────────────────────────────────────────────────────────────────────
# Ativos de Negócio — Etapas 1 (Visão Agregada) + 2 (Metadados)
#
# Lista unificada de todos os artefatos gerados pelo pipeline em todas as
# reuniões do projeto ativo, com governança de status/tags/owner/notas para
# os 5 tipos que têm linha própria no banco (Requisitos, BPMN, SBVR Termos,
# SBVR Regras, Atas). BMM/DMN/IBIS/Relatórios são somente-leitura — só
# existem como JSON dentro de meetings.*_json, sem artifact_id de linha
# própria para governança hoje (ver melhorias/cognicao-de-negocio.md).
#
# Escopo de visualização (toggle "Escopo"): além do contexto ativo, a página
# oferece o "Catálogo do Domínio" — mesma lista agregada, mas somando todos
# os contextos do tenant logado (reuso cross-contexto, ver
# melhorias/cognicao-de-negocio.md §2/§8). Cada ativo carrega seu próprio
# context_id no modo domínio, então o formulário de metadados grava sempre
# no projeto de origem do item, nunca no contexto ativo da sessão.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st

from ui.auth_gate import apply_auth_gate
from ui.project_selector import require_active_project
from modules.supabase_client import supabase_configured
from core.project_store import (
    list_all_business_assets,
    list_all_business_assets_for_domain,
    upsert_asset_metadata,
)

apply_auth_gate()

from ui.components.page_header import render_page_header
render_page_header(
    "📦", "Ativos de Negócio",
    "Visão agregada de todos os artefatos gerados pelo pipeline — requisitos, BPMN, SBVR, "
    "atas, BMM, DMN, IBIS e relatórios — com governança de status, tags e responsável.",
)

if not supabase_configured():
    st.error("⚙️ Supabase não configurado. Adicione as credenciais em Configurações → Secrets.")
    st.stop()

project_id, project_name = require_active_project()

# ── Escopo: contexto ativo x catálogo do domínio (todos os contextos) ───────
_SCOPE_CONTEXT = "📁 Este contexto"
_SCOPE_DOMAIN  = "🌐 Catálogo do Domínio (todos os contextos)"
scope = st.radio(
    "Escopo",
    [_SCOPE_CONTEXT, _SCOPE_DOMAIN],
    horizontal=True,
    key="ativos_scope",
    label_visibility="collapsed",
)

# ── Metadados por tipo (label, ícone) ────────────────────────────────────────
_TYPE_META = {
    "requirement":     ("Requisitos",       "📋"),
    "bpmn_process":    ("Processos BPMN",   "📐"),
    "sbvr_term":       ("SBVR — Termos",    "📖"),
    "sbvr_rule":       ("SBVR — Regras",    "⚖️"),
    "meeting_minutes": ("Atas",             "📝"),
    "bmm":             ("BMM",              "🎯"),
    "dmn":             ("DMN",              "🔀"),
    "ibis":            ("IBIS",             "💬"),
    "report":          ("Relatórios",       "📄"),
}
_STATUS_OPTIONS = ["rascunho", "ativo", "arquivado"]
_STATUS_ICON = {"rascunho": "📝", "ativo": "✅", "arquivado": "🗄️"}

is_domain_scope = scope == _SCOPE_DOMAIN

if is_domain_scope:
    tenant_id = st.session_state.get("_tenant_id")
    with st.spinner("Carregando ativos de todos os contextos do domínio..."):
        assets = list_all_business_assets_for_domain(tenant_id)
    total_items = sum(len(v) for v in assets.values())
    domain_label = st.session_state.get("_tenant_name") or "Domínio"
    n_contexts = len({i.get("context_id") for items in assets.values() for i in items if i.get("context_id")})
    st.caption(f"🌐 **{domain_label}** · {total_items} artefato(s) em {n_contexts} contexto(s)")
else:
    with st.spinner("Carregando ativos do projeto..."):
        assets = list_all_business_assets(project_id)
    total_items = sum(len(v) for v in assets.values())
    st.caption(f"📁 **{project_name}** · {total_items} artefato(s) no total")

# ── Filtros ───────────────────────────────────────────────────────────────────
if is_domain_scope:
    col_type, col_ctx, col_search = st.columns([2, 2, 3])
else:
    col_type, col_search = st.columns([2, 3])
    col_ctx = None
with col_type:
    selected_types = st.multiselect(
        "Tipo de artefato",
        options=list(_TYPE_META.keys()),
        default=list(_TYPE_META.keys()),
        format_func=lambda t: f"{_TYPE_META[t][1]} {_TYPE_META[t][0]}",
    )
selected_contexts = None
if col_ctx is not None:
    with col_ctx:
        context_names = sorted({i.get("context_name") for items in assets.values() for i in items if i.get("context_name")})
        selected_contexts = st.multiselect(
            "Contexto", options=context_names, default=context_names,
        )
with col_search:
    search_term = st.text_input("🔎 Buscar por título", placeholder="Digite parte do título...")

st.divider()

if total_items == 0:
    empty_msg = (
        "Nenhum artefato encontrado em nenhum contexto do domínio ainda."
        if is_domain_scope else
        "Nenhum artefato encontrado neste projeto ainda. Processe uma reunião no Pipeline para começar."
    )
    st.info(empty_msg)
    st.stop()

# ── Renderização por tipo ────────────────────────────────────────────────────
for artifact_type in _TYPE_META:
    if artifact_type not in selected_types:
        continue
    items = assets.get(artifact_type, [])
    if search_term.strip():
        needle = search_term.strip().lower()
        items = [i for i in items if needle in (i.get("title") or "").lower()]
    if selected_contexts is not None:
        items = [i for i in items if i.get("context_name") in selected_contexts]
    if not items:
        continue

    label, icon = _TYPE_META[artifact_type]
    st.subheader(f"{icon} {label} ({len(items)})")

    for item in items:
        title = item.get("title") or "(sem título)"
        meeting_ref = item.get("meeting_ref") or ""
        meeting_date = item.get("meeting_date") or ""
        context_name = item.get("context_name") or ""
        item_project_id = item.get("context_id") or project_id
        subtitle = " · ".join(x for x in [context_name, meeting_ref, meeting_date] if x)

        if not item.get("has_metadata_support"):
            with st.container(border=True):
                st.markdown(f"**{title}**")
                if subtitle:
                    st.caption(subtitle)
                st.caption("🔒 Metadados indisponíveis — este tipo não tem identificador de linha próprio no banco hoje.")
            continue

        meta = item.get("metadata") or {}
        current_status = meta.get("status", "rascunho")
        current_tags = ", ".join(meta.get("tags") or [])
        current_owner = meta.get("owner") or ""
        current_notes = meta.get("notes") or ""

        with st.expander(f"{_STATUS_ICON.get(current_status, '📝')} {title}" + (f" — {subtitle}" if subtitle else "")):
            form_key = f"asset_form_{artifact_type}_{item['artifact_id']}"
            with st.form(form_key):
                col_status, col_owner = st.columns(2)
                with col_status:
                    new_status = st.selectbox(
                        "Status", _STATUS_OPTIONS,
                        index=_STATUS_OPTIONS.index(current_status) if current_status in _STATUS_OPTIONS else 0,
                        key=f"{form_key}_status",
                    )
                with col_owner:
                    new_owner = st.text_input("Responsável", value=current_owner, key=f"{form_key}_owner")
                new_tags = st.text_input(
                    "Tags (separadas por vírgula)", value=current_tags, key=f"{form_key}_tags",
                )
                new_notes = st.text_area("Notas", value=current_notes, key=f"{form_key}_notes")

                if st.form_submit_button("💾 Salvar"):
                    tags_list = [t.strip() for t in new_tags.split(",") if t.strip()]
                    result = upsert_asset_metadata(
                        item_project_id, artifact_type, item["artifact_id"],
                        status=new_status, tags=tags_list,
                        owner=new_owner.strip() or None,
                        notes=new_notes.strip() or None,
                    )
                    if result:
                        st.success("Metadados salvos.")
                        st.rerun()
                    else:
                        st.error("Erro ao salvar metadados.")
