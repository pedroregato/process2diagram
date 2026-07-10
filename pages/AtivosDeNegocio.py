# pages/AtivosDeNegocio.py
# ─────────────────────────────────────────────────────────────────────────────
# Ativos de Negócio — Promoção Explícita + Classificação em 3 Dimensões
# (melhorias/promocao-ativos-negocio.md, Fase A)
#
# A partir desta versão, um artefato só aparece aqui depois de ser PROMOVIDO
# explicitamente (em pages/Artefatos.py) — existir uma linha em asset_metadata
# é a própria definição de "é um ativo de negócio" (ver core/project_store.py
# ::list_all_business_assets()). Deixou de listar automaticamente tudo que
# existe no projeto (comportamento da Etapa 1 original, PC164).
#
# Toda promoção carrega 3 classificações obrigatórias — Interesse para o
# Negócio (Estratégico/Tático/Operacional), Perspectiva (área/departamento,
# multi-valor) e Justificativa (texto livre) — mais Classificação Formal
# opcional (taxonomia AN-01..AN-12, ISO 55000/APQC PCF/BIZBOK/TOGAF). Esta
# página permite reclassificar um ativo já promovido, filtrar por qualquer
# uma das 3 dimensões, e despromover (status="arquivado", nunca apaga).
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
    demote_business_asset,
    BUSINESS_INTEREST_OPTIONS,
    BUSINESS_PERSPECTIVE_OPTIONS,
    FORMAL_CLASSIFICATION_OPTIONS,
)
from ui.components.promote_asset import (
    render_classification_fields,
    INTEREST_LABELS,
    PERSPECTIVE_LABELS,
    FORMAL_CLASSIFICATION_LABELS,
)

apply_auth_gate()

from ui.components.page_header import render_page_header
render_page_header(
    "📦", "Ativos de Negócio",
    "Artefatos promovidos explicitamente a ativo de negócio — com classificação de "
    "Interesse, Perspectiva e Classificação Formal, governança de status/tags/responsável.",
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
    "document":        ("Documentos",       "🗂️"),
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
    st.caption(f"🌐 **{domain_label}** · {total_items} ativo(s) promovido(s) em {n_contexts} contexto(s)")
else:
    with st.spinner("Carregando ativos do projeto..."):
        assets = list_all_business_assets(project_id)
    total_items = sum(len(v) for v in assets.values())
    st.caption(f"📁 **{project_name}** · {total_items} ativo(s) promovido(s)")

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

col_interest, col_perspective, col_classification, col_archived = st.columns([2, 3, 3, 2])
with col_interest:
    selected_interests = st.multiselect(
        "Interesse", BUSINESS_INTEREST_OPTIONS,
        default=BUSINESS_INTEREST_OPTIONS,
        format_func=lambda v: INTEREST_LABELS.get(v, v),
    )
with col_perspective:
    selected_perspectives = st.multiselect(
        "Perspectiva", BUSINESS_PERSPECTIVE_OPTIONS,
        format_func=lambda v: PERSPECTIVE_LABELS.get(v, v),
        help="Vazio = não filtra por perspectiva.",
    )
with col_classification:
    selected_classifications = st.multiselect(
        "Classificação Formal", FORMAL_CLASSIFICATION_OPTIONS,
        format_func=lambda v: FORMAL_CLASSIFICATION_LABELS.get(v, v),
        help="Vazio = não filtra por classificação formal.",
    )
with col_archived:
    show_archived = st.checkbox("Mostrar arquivados", value=False, key="ativos_show_archived")

st.divider()

if total_items == 0:
    empty_msg = (
        "Nenhum ativo promovido em nenhum contexto do domínio ainda."
        if is_domain_scope else
        "Nenhum ativo de negócio promovido neste projeto ainda."
    )
    st.info(
        f"{empty_msg} Um artefato só vira ativo de negócio quando é promovido explicitamente "
        "— acesse a **Central de Artefatos** (Requisitos, BPMN, SBVR ou Reuniões) e use o botão "
        "**⭐ Promover a Ativo de Negócio** no item desejado."
    )
    st.page_link("pages/Artefatos.py", label="→ Ir para a Central de Artefatos")
    st.stop()

# ── Renderização por tipo ────────────────────────────────────────────────────
_any_rendered = False
for artifact_type in _TYPE_META:
    if artifact_type not in selected_types:
        continue
    items = assets.get(artifact_type, [])
    if search_term.strip():
        needle = search_term.strip().lower()
        items = [i for i in items if needle in (i.get("title") or "").lower()]
    if selected_contexts is not None:
        items = [i for i in items if i.get("context_name") in selected_contexts]
    if items and items[0].get("has_metadata_support"):
        # Filtros de classificação só se aplicam aos tipos promovíveis —
        # os 4 somente-leitura (bmm/dmn/ibis/report) não têm essas 3 dimensões.
        if not show_archived:
            items = [i for i in items if (i.get("metadata") or {}).get("status") != "arquivado"]
        items = [
            i for i in items
            if (i.get("metadata") or {}).get("business_interest", "operacional") in selected_interests
        ]
        if selected_perspectives:
            items = [
                i for i in items
                if set((i.get("metadata") or {}).get("business_perspective") or [])
                & set(selected_perspectives)
            ]
        if selected_classifications:
            items = [
                i for i in items
                if (i.get("metadata") or {}).get("formal_classification") in selected_classifications
            ]
    if not items:
        continue
    _any_rendered = True

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
        current_interest = meta.get("business_interest", "operacional")
        current_perspective = meta.get("business_perspective") or []
        current_classification = meta.get("formal_classification")
        current_justification = meta.get("promotion_justification") or ""

        _badges = " ".join(
            f"`{PERSPECTIVE_LABELS.get(p, p)}`" for p in current_perspective
        )
        header = f"{_STATUS_ICON.get(current_status, '📝')} {INTEREST_LABELS.get(current_interest, current_interest)} — {title}"
        if subtitle:
            header += f" — {subtitle}"

        with st.expander(header):
            if _badges:
                st.markdown(f"**Perspectiva:** {_badges}")
            if current_classification:
                st.caption(f"🏷️ {FORMAL_CLASSIFICATION_LABELS.get(current_classification, current_classification)}")
            if current_justification:
                st.caption(f"💬 *{current_justification}*")

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

                st.markdown("**Reclassificar**")
                new_interest, new_perspective, new_classification, new_justification = render_classification_fields(
                    form_key,
                    current_classification,
                    default_interest=current_interest,
                    default_perspective=current_perspective,
                    default_justification=current_justification,
                )

                if st.form_submit_button("💾 Salvar"):
                    if not new_interest or not new_perspective or not new_justification.strip():
                        st.error("Interesse, Perspectiva e Justificativa não podem ficar vazios.")
                    else:
                        tags_list = [t.strip() for t in new_tags.split(",") if t.strip()]
                        result = upsert_asset_metadata(
                            item_project_id, artifact_type, item["artifact_id"],
                            status=new_status, tags=tags_list,
                            owner=new_owner.strip() or None,
                            notes=new_notes.strip() or None,
                            business_interest=new_interest,
                            business_perspective=new_perspective,
                            formal_classification=new_classification,
                            promotion_justification=new_justification.strip(),
                        )
                        if result:
                            st.success("Metadados salvos.")
                            st.rerun()
                        else:
                            st.error("Erro ao salvar metadados.")

            if current_status != "arquivado":
                if st.button("🗄️ Despromover", key=f"{form_key}_demote"):
                    if demote_business_asset(item_project_id, artifact_type, item["artifact_id"]):
                        st.success("Ativo despromovido — status movido para arquivado (histórico preservado).")
                        st.rerun()
                    else:
                        st.error("Erro ao despromover.")

if not _any_rendered:
    st.info("Nenhum ativo corresponde aos filtros aplicados.")
