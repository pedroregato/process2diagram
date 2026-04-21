# pages/ValidationHub.py
# ─────────────────────────────────────────────────────────────────────────────
# Validação Humana de Artefatos — revisão e aprovação dos elementos extraídos
# pelo pipeline: requisitos, termos SBVR, regras SBVR e processos BPMN.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from ui.auth_gate import apply_auth_gate
from modules.supabase_client import supabase_configured
from core.project_store import (
    list_projects, list_meetings,
    list_requirements, list_sbvr_terms, list_sbvr_rules, list_bpmn_processes,
    validate_artifact, update_artifact_content,
)

apply_auth_gate()

# ── Paleta de status de validação ─────────────────────────────────────────────
_VS: dict[str, dict] = {
    "proposto":   {"bg": "#0d2f4f", "fg": "#60a5fa", "label": "Proposto",   "icon": "💡"},
    "em_revisão": {"bg": "#4a3000", "fg": "#fbbf24", "label": "Em Revisão", "icon": "🔄"},
    "validado":   {"bg": "#064e3b", "fg": "#6ee7b7", "label": "Validado",   "icon": "✅"},
    "ajustado":   {"bg": "#0d3f1f", "fg": "#4ade80", "label": "Ajustado",   "icon": "🔧"},
    "rejeitado":  {"bg": "#4a0d0d", "fg": "#f87171", "label": "Rejeitado",  "icon": "❌"},
}
_PENDING  = ("proposto", "em_revisão", None)
_DONE     = ("validado", "ajustado", "rejeitado")


def _vs_badge(status: str | None) -> str:
    cfg = _VS.get(status or "proposto", _VS["proposto"])
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:20px;'
        f'font-size:.72rem;font-weight:600;background:{cfg["bg"]};color:{cfg["fg"]}">'
        f'{cfg["icon"]} {cfg["label"]}</span>'
    )


def _type_badge(label: str, color: str = "#1e293b") -> str:
    return (
        f'<span style="display:inline-block;padding:2px 8px;border-radius:20px;'
        f'font-size:.68rem;font-weight:600;background:{color};color:#e2e8f0;'
        f'margin-left:6px">{label}</span>'
    )


_me = st.session_state.get("_usuario_nome") or st.session_state.get("_usuario_login", "sistema")

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# ✅ Validação de Artefatos")

if not supabase_configured():
    st.error("⚙️ Supabase não configurado. Adicione as credenciais em Configurações.")
    st.stop()

# ── Feedback de ações anteriores ──────────────────────────────────────────────
if "_vhub_msg" in st.session_state:
    kind, msg = st.session_state.pop("_vhub_msg")
    getattr(st, kind)(msg)

# ── Seletores ─────────────────────────────────────────────────────────────────
projects = list_projects()
if not projects:
    st.info("Nenhum projeto encontrado.")
    st.stop()

col_proj, col_meet, col_status = st.columns(3)

with col_proj:
    proj_map = {p["name"]: p for p in projects}
    sel_proj = st.selectbox("Projeto", list(proj_map.keys()), key="vhub_proj")
    project  = proj_map[sel_proj]
    proj_id  = project["id"]

with col_meet:
    meetings   = list_meetings(proj_id)
    meet_map   = {"Todas as reuniões": None}
    for m in meetings:
        dt  = (m.get("meeting_date") or "")[:10]
        lbl = f"Reunião {m.get('meeting_number','?')} — {m.get('title','')} ({dt})"
        meet_map[lbl] = m["id"]
    sel_meet_lbl = st.selectbox("Reunião", list(meet_map.keys()), key="vhub_meet")
    sel_meet_id  = meet_map[sel_meet_lbl]

with col_status:
    filter_opts = ["Todos", "Pendentes", "Concluídos", "Rejeitados"]
    sel_filter  = st.selectbox("Filtro de status", filter_opts, key="vhub_filter")

# ── Carrega artefatos ──────────────────────────────────────────────────────────
all_reqs  = list_requirements(proj_id)
all_terms = list_sbvr_terms(proj_id)
all_rules = list_sbvr_rules(proj_id)
all_bpmn  = list_bpmn_processes(proj_id)

# Aplica filtro de reunião
def _meet_filter(items: list[dict], field: str) -> list[dict]:
    if not sel_meet_id:
        return items
    return [i for i in items if i.get(field) == sel_meet_id]

reqs  = _meet_filter(all_reqs,  "first_meeting_id")
terms = _meet_filter(all_terms, "meeting_id")
rules = _meet_filter(all_rules, "meeting_id")
bpmn  = _meet_filter(all_bpmn,  "first_meeting_id")

# Aplica filtro de validation_status
def _status_filter(items: list[dict]) -> list[dict]:
    if sel_filter == "Pendentes":
        return [i for i in items if (i.get("validation_status") or "proposto") in ("proposto", "em_revisão")]
    if sel_filter == "Concluídos":
        return [i for i in items if (i.get("validation_status") or "proposto") in ("validado", "ajustado")]
    if sel_filter == "Rejeitados":
        return [i for i in items if (i.get("validation_status") or "proposto") == "rejeitado"]
    return items

reqs  = _status_filter(reqs)
terms = _status_filter(terms)
rules = _status_filter(rules)
bpmn  = _status_filter(bpmn)

# ── Métricas ──────────────────────────────────────────────────────────────────
def _counts(items: list[dict]) -> dict:
    c = {"proposto": 0, "em_revisão": 0, "validado": 0, "ajustado": 0, "rejeitado": 0}
    for i in items:
        s = i.get("validation_status") or "proposto"
        if s in c:
            c[s] += 1
        else:
            c["proposto"] += 1
    return c

all_items = all_reqs + all_terms + all_rules + all_bpmn
tc = _counts(all_items)
n_total    = len(all_items)
n_done     = tc["validado"] + tc["ajustado"]
n_pending  = tc["proposto"] + tc["em_revisão"]
n_rejected = tc["rejeitado"]
pct        = int(n_done / n_total * 100) if n_total else 0

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Total de artefatos", n_total)
m2.metric("✅ Concluídos",      n_done,     delta=f"{pct}%")
m3.metric("💡 Pendentes",       n_pending)
m4.metric("🔄 Em Revisão",      tc["em_revisão"])
m5.metric("❌ Rejeitados",      n_rejected)

st.markdown("---")

# ── Helpers de card ───────────────────────────────────────────────────────────
def _quick_actions(table: str, art_id: str, current_vs: str | None, key_pfx: str) -> None:
    """Botões de ação rápida — validar, em_revisão, rejeitar."""
    vs = current_vs or "proposto"
    c1, c2, c3, _ = st.columns([1, 1, 1, 5])
    with c1:
        if vs not in ("validado", "ajustado") and st.button(
            "✅ Validar", key=f"{key_pfx}_val", use_container_width=True
        ):
            validate_artifact(table, art_id, "validado", _me)
            st.session_state["_vhub_msg"] = ("success", "✅ Artefato validado.")
            st.rerun()
    with c2:
        if vs not in ("em_revisão",) and st.button(
            "🔄 Em Revisão", key=f"{key_pfx}_rev", use_container_width=True
        ):
            validate_artifact(table, art_id, "em_revisão", _me)
            st.session_state["_vhub_msg"] = ("info", "🔄 Marcado para revisão.")
            st.rerun()
    with c3:
        if vs != "rejeitado" and st.button(
            "❌ Rejeitar", key=f"{key_pfx}_rej", use_container_width=True
        ):
            validate_artifact(table, art_id, "rejeitado", _me)
            st.session_state["_vhub_msg"] = ("warning", "❌ Artefato rejeitado.")
            st.rerun()


def _edit_form_req(req: dict) -> None:
    with st.expander("✏️ Editar conteúdo", expanded=False):
        with st.form(f"form_req_{req['id']}"):
            new_title = st.text_input("Título", value=req.get("title") or "")
            new_desc  = st.text_area("Descrição", value=req.get("description") or "", height=100)
            new_notes = st.text_input("Nota de validação", value=req.get("validation_notes") or "")
            c1, c2 = st.columns(2)
            save_adj = c1.form_submit_button("💾 Salvar como Ajustado", use_container_width=True)
            save_only = c2.form_submit_button("💾 Salvar sem validar",  use_container_width=True)
        if save_adj:
            update_artifact_content("requirements", req["id"], {"title": new_title, "description": new_desc})
            validate_artifact("requirements", req["id"], "ajustado", _me, new_notes)
            st.session_state["_vhub_msg"] = ("success", "🔧 Requisito ajustado e validado.")
            st.rerun()
        if save_only:
            update_artifact_content("requirements", req["id"], {"title": new_title, "description": new_desc})
            if new_notes:
                validate_artifact("requirements", req["id"], req.get("validation_status") or "proposto", _me, new_notes)
            st.session_state["_vhub_msg"] = ("info", "💾 Conteúdo salvo.")
            st.rerun()


def _edit_form_term(term: dict) -> None:
    with st.expander("✏️ Editar conteúdo", expanded=False):
        with st.form(f"form_term_{term['id']}"):
            new_term = st.text_input("Termo", value=term.get("term") or "")
            new_def  = st.text_area("Definição", value=term.get("definition") or "", height=100)
            new_notes = st.text_input("Nota de validação", value=term.get("validation_notes") or "")
            c1, c2 = st.columns(2)
            save_adj  = c1.form_submit_button("💾 Salvar como Ajustado", use_container_width=True)
            save_only = c2.form_submit_button("💾 Salvar sem validar",  use_container_width=True)
        if save_adj:
            update_artifact_content("sbvr_terms", term["id"], {"term": new_term, "definition": new_def})
            validate_artifact("sbvr_terms", term["id"], "ajustado", _me, new_notes)
            st.session_state["_vhub_msg"] = ("success", "🔧 Termo ajustado e validado.")
            st.rerun()
        if save_only:
            update_artifact_content("sbvr_terms", term["id"], {"term": new_term, "definition": new_def})
            if new_notes:
                validate_artifact("sbvr_terms", term["id"], term.get("validation_status") or "proposto", _me, new_notes)
            st.session_state["_vhub_msg"] = ("info", "💾 Conteúdo salvo.")
            st.rerun()


def _edit_form_rule(rule: dict) -> None:
    with st.expander("✏️ Editar conteúdo", expanded=False):
        with st.form(f"form_rule_{rule['id']}"):
            new_stmt  = st.text_area("Enunciado da regra", value=rule.get("statement") or "", height=100)
            new_notes = st.text_input("Nota de validação", value=rule.get("validation_notes") or "")
            c1, c2 = st.columns(2)
            save_adj  = c1.form_submit_button("💾 Salvar como Ajustado", use_container_width=True)
            save_only = c2.form_submit_button("💾 Salvar sem validar",  use_container_width=True)
        if save_adj:
            update_artifact_content("sbvr_rules", rule["id"], {"statement": new_stmt})
            validate_artifact("sbvr_rules", rule["id"], "ajustado", _me, new_notes)
            st.session_state["_vhub_msg"] = ("success", "🔧 Regra ajustada e validada.")
            st.rerun()
        if save_only:
            update_artifact_content("sbvr_rules", rule["id"], {"statement": new_stmt})
            if new_notes:
                validate_artifact("sbvr_rules", rule["id"], rule.get("validation_status") or "proposto", _me, new_notes)
            st.session_state["_vhub_msg"] = ("info", "💾 Conteúdo salvo.")
            st.rerun()


def _edit_form_bpmn(proc: dict) -> None:
    with st.expander("✏️ Editar nome do processo", expanded=False):
        with st.form(f"form_bpmn_{proc['id']}"):
            new_name  = st.text_input("Nome do processo", value=proc.get("name") or "")
            new_notes = st.text_input("Nota de validação", value=proc.get("validation_notes") or "")
            c1, c2 = st.columns(2)
            save_adj  = c1.form_submit_button("💾 Salvar como Ajustado", use_container_width=True)
            save_only = c2.form_submit_button("💾 Salvar sem validar",  use_container_width=True)
        if save_adj:
            update_artifact_content("bpmn_processes", proc["id"], {"name": new_name})
            validate_artifact("bpmn_processes", proc["id"], "ajustado", _me, new_notes)
            st.session_state["_vhub_msg"] = ("success", "🔧 Processo ajustado e validado.")
            st.rerun()
        if save_only:
            update_artifact_content("bpmn_processes", proc["id"], {"name": new_name})
            if new_notes:
                validate_artifact("bpmn_processes", proc["id"], proc.get("validation_status") or "proposto", _me, new_notes)
            st.session_state["_vhub_msg"] = ("info", "💾 Conteúdo salvo.")
            st.rerun()


def _bulk_validate(table: str, items: list[dict], key: str) -> None:
    pending = [i for i in items if (i.get("validation_status") or "proposto") in ("proposto", "em_revisão")]
    if not pending:
        return
    if st.button(f"✅ Validar todos pendentes ({len(pending)})", key=key):
        for item in pending:
            validate_artifact(table, item["id"], "validado", _me)
        st.session_state["_vhub_msg"] = ("success", f"✅ {len(pending)} artefato(s) validado(s).")
        st.rerun()


def _render_group(items: list[dict], pending: bool, render_fn) -> None:
    """Renderiza um grupo (pendentes ou concluídos) com expander."""
    label = "⏳ Aguardando Validação" if pending else "✅ Concluídos"
    group = [i for i in items if ((i.get("validation_status") or "proposto") in ("proposto", "em_revisão")) == pending]
    if not group:
        return
    with st.expander(f"**{label}** ({len(group)})", expanded=pending):
        for item in group:
            render_fn(item)
            st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# TABS PRINCIPAIS
# ═══════════════════════════════════════════════════════════════════════════════
tab_req, tab_terms, tab_rules, tab_bpmn = st.tabs([
    f"📝 Requisitos ({len(reqs)})",
    f"📖 Termos SBVR ({len(terms)})",
    f"📋 Regras SBVR ({len(rules)})",
    f"📐 BPMN ({len(bpmn)})",
])

# ── TAB: Requisitos ───────────────────────────────────────────────────────────
_TYPE_COLORS = {
    "functional":    "#1e3a6e", "non_functional": "#2d1e6e",
    "business_rule": "#0d4f2e", "validation":     "#4a3000", "ui_field": "#134e4a",
}
_PRIO_ICON = {"high": "🔴", "medium": "🟡", "low": "🟢"}

with tab_req:
    if not reqs:
        st.info("Nenhum requisito para exibir com os filtros selecionados.")
    else:
        _bulk_validate("requirements", reqs, "bulk_req")

        def _render_req(r: dict) -> None:
            vs   = r.get("validation_status") or "proposto"
            num  = r.get("req_number", 0)
            rtype = r.get("req_type", "")
            prio  = r.get("priority", "")
            st.markdown(
                f'**REQ-{num:03d}** — {r.get("title","—")}  '
                + _vs_badge(vs)
                + _type_badge(rtype, _TYPE_COLORS.get(rtype, "#1e293b"))
                + (f' {_PRIO_ICON.get(prio,"")} {prio}' if prio else ""),
                unsafe_allow_html=True,
            )
            if r.get("description"):
                st.caption(r["description"])
            if r.get("cited_by"):
                st.caption(f"👤 Proponente: **{r['cited_by']}**")
            if r.get("source_quote"):
                st.caption(f'💬 *"{r["source_quote"]}"*')
            if r.get("validation_notes"):
                st.caption(f"📝 Nota: {r['validation_notes']}")
            _quick_actions("requirements", r["id"], vs, f"req_{r['id']}")
            _edit_form_req(r)

        _render_group(reqs, pending=True,  render_fn=_render_req)
        _render_group(reqs, pending=False, render_fn=_render_req)

# ── TAB: Termos SBVR ─────────────────────────────────────────────────────────
_CAT_COLORS = {"concept": "#1e3a6e", "fact_type": "#0d4f2e", "role": "#4a3000", "process": "#134e4a"}

with tab_terms:
    if not terms:
        st.info("Nenhum termo SBVR para exibir com os filtros selecionados.")
    else:
        _bulk_validate("sbvr_terms", terms, "bulk_terms")

        def _render_term(t: dict) -> None:
            vs  = t.get("validation_status") or "proposto"
            cat = t.get("category", "concept")
            meet_info = t.get("meetings") or {}
            m_num = meet_info.get("meeting_number")
            origin = f"🗓️ Reunião {m_num}" if m_num else "🤖 Assistente"
            st.markdown(
                f'**{t.get("term","—")}**  '
                + _vs_badge(vs)
                + _type_badge(cat, _CAT_COLORS.get(cat, "#1e293b")),
                unsafe_allow_html=True,
            )
            if t.get("definition"):
                st.caption(t["definition"])
            st.caption(origin)
            if t.get("validation_notes"):
                st.caption(f"📝 Nota: {t['validation_notes']}")
            _quick_actions("sbvr_terms", t["id"], vs, f"term_{t['id']}")
            _edit_form_term(t)

        _render_group(terms, pending=True,  render_fn=_render_term)
        _render_group(terms, pending=False, render_fn=_render_term)

# ── TAB: Regras SBVR ─────────────────────────────────────────────────────────
_RULE_COLORS = {"constraint": "#4a0d0d", "operational": "#0d4f2e",
                "behavioral": "#4a3000", "structural": "#1e3a6e"}

with tab_rules:
    if not rules:
        st.info("Nenhuma regra SBVR para exibir com os filtros selecionados.")
    else:
        _bulk_validate("sbvr_rules", rules, "bulk_rules")

        def _render_rule(r: dict) -> None:
            vs    = r.get("validation_status") or "proposto"
            rtype = r.get("rule_type", "constraint")
            rid   = r.get("rule_id") or "BR-?"
            kw    = r.get("nucleo_nominal") or ""
            lbl   = f"{rid} — {kw}" if kw else rid
            meet_info = r.get("meetings") or {}
            m_num = meet_info.get("meeting_number")
            origin = f"🗓️ Reunião {m_num}" if m_num else "🤖 Assistente"
            st.markdown(
                f'**{lbl}**  '
                + _vs_badge(vs)
                + _type_badge(rtype, _RULE_COLORS.get(rtype, "#1e293b")),
                unsafe_allow_html=True,
            )
            if r.get("statement"):
                st.caption(r["statement"])
            st.caption(origin)
            if r.get("validation_notes"):
                st.caption(f"📝 Nota: {r['validation_notes']}")
            _quick_actions("sbvr_rules", r["id"], vs, f"rule_{r['id']}")
            _edit_form_rule(r)

        _render_group(rules, pending=True,  render_fn=_render_rule)
        _render_group(rules, pending=False, render_fn=_render_rule)

# ── TAB: Processos BPMN ───────────────────────────────────────────────────────
with tab_bpmn:
    if not bpmn:
        st.info("Nenhum processo BPMN para exibir com os filtros selecionados.")
    else:
        _bulk_validate("bpmn_processes", bpmn, "bulk_bpmn")

        def _render_bpmn_proc(p: dict) -> None:
            vs     = p.get("validation_status") or "proposto"
            status = p.get("status", "active")
            n_ver  = p.get("version_count") or 0
            st.markdown(
                f'**{p.get("name","—")}**  '
                + _vs_badge(vs)
                + _type_badge(status, "#1e3a6e"),
                unsafe_allow_html=True,
            )
            st.caption(f"🔑 `{p.get('slug','')}` · {n_ver} versão(ões)")
            if p.get("validation_notes"):
                st.caption(f"📝 Nota: {p['validation_notes']}")
            _quick_actions("bpmn_processes", p["id"], vs, f"bpmn_{p['id']}")
            _edit_form_bpmn(p)

        _render_group(bpmn, pending=True,  render_fn=_render_bpmn_proc)
        _render_group(bpmn, pending=False, render_fn=_render_bpmn_proc)

# ── Rodapé ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("Process2Diagram v4.13 — Validação de Artefatos")
