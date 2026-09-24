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
    list_meetings,
    list_meetings_quality,
    list_requirements_light,
    list_sbvr_terms, list_sbvr_rules, list_bpmn_processes,
    list_dmn_by_project,
    validate_artifact, update_artifact_content,
    count_validation_status,
)
from ui.project_selector import require_active_project

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


# ── Cache de leitura (NAV-03) ─────────────────────────────────────────────────
# A página renderizava todos os artefatos de uma vez (contexto com 2.252
# artefatos → ~2.490 botões, 42s + queda de sessão). O fix real é a paginação
# abaixo; este cache evita reconsultar o Supabase a cada rerun (ex.: clique
# de paginação) dentro da mesma janela de 60s.
@st.cache_data(ttl=60, show_spinner=False)
def _load_artifacts(pid: str):
    return (
        list_requirements_light(pid),
        list_sbvr_terms(pid),
        list_sbvr_rules(pid),
        list_bpmn_processes(pid),
    )


@st.cache_data(ttl=60, show_spinner=False)
def _load_status_counts(pid: str):
    return count_validation_status(pid)


def _invalidate_caches() -> None:
    _load_artifacts.clear()
    _load_status_counts.clear()


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

# ── Projeto de trabalho ativo + seletores ─────────────────────────────────────
proj_id, proj_name = require_active_project()
_col_p, _col_ch = st.columns([5, 1])
with _col_p:
    st.success(f"📁 **Contexto:** {proj_name}")
with _col_ch:
    st.page_link("pages/Home.py", label="Trocar")

col_meet, col_status = st.columns(2)

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
    sel_filter  = st.selectbox(
        "Filtro de status", filter_opts,
        index=filter_opts.index("Pendentes"),  # NAV-03: padrão era "Todos"
        key="vhub_filter",
    )

# ── Carrega artefatos (cache 60s — NAV-03) ─────────────────────────────────────
all_reqs, all_terms, all_rules, all_bpmn = _load_artifacts(proj_id)

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

# Assinatura dos filtros ativos — usada por _paginate() para resetar a página
# de cada aba quando reunião/status mudam (NAV-03).
_filter_sig = f"{proj_id}|{sel_meet_lbl}|{sel_filter}"

# ── Métricas (contagem agregada — NAV-03) ─────────────────────────────────────
# Antes: len() sobre as 4 listas completas já carregadas para renderizar a
# página. Agora: count="exact" no Supabase, sem transferir nenhuma linha de
# conteúdo — ver core/project_store.py::count_validation_status().
tc         = _load_status_counts(proj_id)
n_total    = sum(tc.values())
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

# ── Paginação e edição em lote (NAV-03) ────────────────────────────────────────
_PAGE_SIZE_OPTS = [25, 50, 100]


def _paginate(items: list[dict], tab_key: str, filter_sig: str) -> list[dict]:
    """Pagina uma lista já filtrada por reunião/status; navegação + seletor de
    tamanho, com estado em session_state por aba (vh_page_<tab_key>)."""
    sig_key = f"_vh_last_filter_{tab_key}"
    if st.session_state.get(sig_key) != filter_sig:
        st.session_state[f"vh_page_{tab_key}"] = 0
        st.session_state[sig_key] = filter_sig

    size_key = f"vh_pagesize_{tab_key}"
    page_key = f"vh_page_{tab_key}"
    n = len(items)

    c_size, c_nav = st.columns([1, 3])
    with c_size:
        page_size = st.selectbox(
            "Itens por página", _PAGE_SIZE_OPTS,
            index=_PAGE_SIZE_OPTS.index(st.session_state.get(size_key, 25)),
            key=size_key,
        )

    n_pages = max(1, (n + page_size - 1) // page_size)
    page  = min(st.session_state.get(page_key, 0), n_pages - 1)
    start = page * page_size
    end   = min(start + page_size, n)

    if n > page_size:
        with c_nav:
            nv1, nv2, nv3 = st.columns([1, 1, 2])
            with nv1:
                if st.button("← Anterior", key=f"{tab_key}_prev", disabled=(page == 0)):
                    st.session_state[page_key] = page - 1
                    st.rerun()
            with nv2:
                if st.button("Próximo →", key=f"{tab_key}_next", disabled=(page == n_pages - 1)):
                    st.session_state[page_key] = page + 1
                    st.rerun()
            with nv3:
                st.caption(f"**{start + 1}–{end}** de **{n}** · Pág. **{page + 1}/{n_pages}**")

    return items[start:end]


def _status_editor(table: str, page_items: list[dict], label_fn, key_pfx: str) -> None:
    """Grade de edição em lote do Status da página atual — substitui os 3
    botões por item (Validar/Em Revisão/Rejeitar). Grava só as linhas cuja
    coluna Status foi alterada (delta de st.data_editor via `edited_rows`)."""
    if not page_items:
        return
    editor_key = f"vh_editor_{key_pfx}"
    rows = [
        {"Item": label_fn(it), "Status": (it.get("validation_status") or "proposto")}
        for it in page_items
    ]
    st.data_editor(
        rows,
        column_config={
            "Item":   st.column_config.TextColumn("Item", disabled=True),
            "Status": st.column_config.SelectboxColumn("Status", options=list(_VS.keys()), required=True),
        },
        column_order=["Item", "Status"],
        hide_index=True,
        use_container_width=True,
        key=editor_key,
    )
    if st.button("💾 Salvar alterações", key=f"vh_save_{key_pfx}"):
        edited = st.session_state.get(editor_key, {}).get("edited_rows", {})
        changed = {int(i): c["Status"] for i, c in edited.items() if "Status" in c}
        if not changed:
            st.info("Nenhuma alteração de status para salvar.")
        else:
            for row_idx, new_status in changed.items():
                validate_artifact(table, page_items[row_idx]["id"], new_status, _me)
            _invalidate_caches()
            st.session_state["_vhub_msg"] = ("success", f"💾 {len(changed)} artefato(s) atualizado(s).")
            st.rerun()


def _edit_form_req(req: dict) -> None:
    with st.popover("✏️ Editar conteúdo"):
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
            _invalidate_caches()
            st.session_state["_vhub_msg"] = ("success", "🔧 Requisito ajustado e validado.")
            st.rerun()
        if save_only:
            update_artifact_content("requirements", req["id"], {"title": new_title, "description": new_desc})
            if new_notes:
                validate_artifact("requirements", req["id"], req.get("validation_status") or "proposto", _me, new_notes)
            _invalidate_caches()
            st.session_state["_vhub_msg"] = ("info", "💾 Conteúdo salvo.")
            st.rerun()


def _edit_form_term(term: dict) -> None:
    with st.popover("✏️ Editar conteúdo"):
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
            _invalidate_caches()
            st.session_state["_vhub_msg"] = ("success", "🔧 Termo ajustado e validado.")
            st.rerun()
        if save_only:
            update_artifact_content("sbvr_terms", term["id"], {"term": new_term, "definition": new_def})
            if new_notes:
                validate_artifact("sbvr_terms", term["id"], term.get("validation_status") or "proposto", _me, new_notes)
            _invalidate_caches()
            st.session_state["_vhub_msg"] = ("info", "💾 Conteúdo salvo.")
            st.rerun()


def _edit_form_rule(rule: dict) -> None:
    with st.popover("✏️ Editar conteúdo"):
        with st.form(f"form_rule_{rule['id']}"):
            new_stmt  = st.text_area("Enunciado da regra", value=rule.get("statement") or "", height=100)
            new_notes = st.text_input("Nota de validação", value=rule.get("validation_notes") or "")
            c1, c2 = st.columns(2)
            save_adj  = c1.form_submit_button("💾 Salvar como Ajustado", use_container_width=True)
            save_only = c2.form_submit_button("💾 Salvar sem validar",  use_container_width=True)
        if save_adj:
            update_artifact_content("sbvr_rules", rule["id"], {"statement": new_stmt})
            validate_artifact("sbvr_rules", rule["id"], "ajustado", _me, new_notes)
            _invalidate_caches()
            st.session_state["_vhub_msg"] = ("success", "🔧 Regra ajustada e validada.")
            st.rerun()
        if save_only:
            update_artifact_content("sbvr_rules", rule["id"], {"statement": new_stmt})
            if new_notes:
                validate_artifact("sbvr_rules", rule["id"], rule.get("validation_status") or "proposto", _me, new_notes)
            _invalidate_caches()
            st.session_state["_vhub_msg"] = ("info", "💾 Conteúdo salvo.")
            st.rerun()


def _edit_form_bpmn(proc: dict) -> None:
    with st.popover("✏️ Editar nome do processo"):
        with st.form(f"form_bpmn_{proc['id']}"):
            new_name  = st.text_input("Nome do processo", value=proc.get("name") or "")
            new_notes = st.text_input("Nota de validação", value=proc.get("validation_notes") or "")
            c1, c2 = st.columns(2)
            save_adj  = c1.form_submit_button("💾 Salvar como Ajustado", use_container_width=True)
            save_only = c2.form_submit_button("💾 Salvar sem validar",  use_container_width=True)
        if save_adj:
            update_artifact_content("bpmn_processes", proc["id"], {"name": new_name})
            validate_artifact("bpmn_processes", proc["id"], "ajustado", _me, new_notes)
            _invalidate_caches()
            st.session_state["_vhub_msg"] = ("success", "🔧 Processo ajustado e validado.")
            st.rerun()
        if save_only:
            update_artifact_content("bpmn_processes", proc["id"], {"name": new_name})
            if new_notes:
                validate_artifact("bpmn_processes", proc["id"], proc.get("validation_status") or "proposto", _me, new_notes)
            _invalidate_caches()
            st.session_state["_vhub_msg"] = ("info", "💾 Conteúdo salvo.")
            st.rerun()


def _bulk_validate(table: str, items: list[dict], key: str) -> None:
    pending = [i for i in items if (i.get("validation_status") or "proposto") in ("proposto", "em_revisão")]
    if not pending:
        return
    if st.button(f"✅ Validar todos pendentes ({len(pending)})", key=key):
        for item in pending:
            validate_artifact(table, item["id"], "validado", _me)
        _invalidate_caches()
        st.session_state["_vhub_msg"] = ("success", f"✅ {len(pending)} artefato(s) validado(s).")
        st.rerun()


def _render_group(items: list[dict], pending: bool, render_fn) -> None:
    """Renderiza um grupo (pendentes ou concluídos) com cabeçalho simples."""
    label = "⏳ Aguardando Validação" if pending else "✅ Concluídos"
    group = [i for i in items if ((i.get("validation_status") or "proposto") in ("proposto", "em_revisão")) == pending]
    if not group:
        return
    icon = "⏳" if pending else "✅"
    st.markdown(f"#### {icon} {label} ({len(group)})")
    for item in group:
        render_fn(item)
        st.divider()
    if not pending:
        st.markdown("")  # espaço visual após grupo de concluídos


# ═══════════════════════════════════════════════════════════════════════════════
# TABS PRINCIPAIS
# ═══════════════════════════════════════════════════════════════════════════════
tab_health, tab_req, tab_terms, tab_rules, tab_bpmn = st.tabs([
    "📊 Saúde do Pipeline",
    f"📝 Requisitos ({len(reqs)})",
    f"📖 Termos SBVR ({len(terms)})",
    f"📋 Regras SBVR ({len(rules)})",
    f"📐 BPMN ({len(bpmn)})",
])

# ── TAB: Saúde do Pipeline ────────────────────────────────────────────────────
with tab_health:
    st.caption(
        "Cobertura de artefatos por reunião — quais agentes do pipeline produziram "
        "saída válida para cada reunião do projeto."
    )

    @st.cache_data(ttl=120, show_spinner=False)
    def _load_health(pid):
        mq  = list_meetings_quality(pid)
        rqs = list_requirements_light(pid)
        trms = list_sbvr_terms(pid)
        dmns = list_dmn_by_project(pid)
        return mq, rqs, trms, dmns

    _mq, _rqs, _trms, _dmns = _load_health(proj_id)

    if not _mq:
        st.info("Nenhuma reunião encontrada para este projeto.")
    else:
        # Aggregate counts per meeting
        _req_count  = {}
        for r in _rqs:
            _mid = r.get("first_meeting_id")
            if _mid:
                _req_count[_mid] = _req_count.get(_mid, 0) + 1
        _term_count = {}
        for t in _trms:
            _mid = t.get("meeting_id")
            if _mid:
                _term_count[_mid] = _term_count.get(_mid, 0) + 1
        _dmn_count  = {}
        for d in _dmns:
            _mid = d.get("_meeting_id")
            if _mid:
                _dmn_count[_mid] = _dmn_count.get(_mid, 0) + 1

        # ── Coverage KPIs ─────────────────────────────────────────────────────
        _n = len(_mq)
        _kc1, _kc2, _kc3, _kc4, _kc5, _kc6 = st.columns(6)
        _kc1.metric("Reuniões",    _n)
        _kc2.metric("🗺️ BPMN",     sum(1 for m in _mq if m["has_bpmn"]),      delta=f"/{_n}")
        _kc3.metric("📋 Ata",      sum(1 for m in _mq if m["has_minutes"]),    delta=f"/{_n}")
        _kc4.metric("⚖️ DMN",      sum(1 for m in _mq if m["has_dmn"]),        delta=f"/{_n}")
        _kc5.metric("🗣️ IBIS",     sum(1 for m in _mq if m["has_ibis"]),       delta=f"/{_n}")
        _kc6.metric("📄 Relatório",sum(1 for m in _mq if m["has_synthesizer"]),delta=f"/{_n}")

        st.markdown("")

        # ── Coverage table ────────────────────────────────────────────────────
        _CHECK, _CROSS = "✅", "❌"
        _rows = []
        for m in _mq:
            _mid = m["id"]
            _rows.append({
                "Reunião":    f"#{m['meeting_number']} — {m['title']}",
                "Data":       m["meeting_date"],
                "BPMN":       _CHECK if m["has_bpmn"] else _CROSS,
                "Ata":        _CHECK if m["has_minutes"] else _CROSS,
                "Requisitos": _req_count.get(_mid, 0),
                "Termos SBVR":_term_count.get(_mid, 0),
                "DMN":        _CHECK if m["has_dmn"] else _CROSS,
                "Decisões DMN":_dmn_count.get(_mid, 0),
                "IBIS":       _CHECK if m["has_ibis"] else _CROSS,
                "Relatório":  _CHECK if m["has_synthesizer"] else _CROSS,
                "Tokens":     m["total_tokens"],
                "Provider":   m["llm_provider"],
            })
        st.dataframe(_rows, use_container_width=True, hide_index=True)

        # ── Coverage bar chart (Plotly) ───────────────────────────────────────
        try:
            import plotly.graph_objects as go
            _agents  = ["BPMN", "Ata", "DMN", "IBIS", "Relatório"]
            _fields  = ["has_bpmn", "has_minutes", "has_dmn", "has_ibis", "has_synthesizer"]
            _labels  = [f"#{m['meeting_number']}" for m in _mq]
            _fig = go.Figure()
            _colors = ["#2563eb", "#16a34a", "#b45309", "#7c3aed", "#0369a1"]
            for _ag, _fld, _col in zip(_agents, _fields, _colors):
                _fig.add_trace(go.Bar(
                    name=_ag,
                    x=_labels,
                    y=[1 if m[_fld] else 0 for m in _mq],
                    marker_color=_col,
                ))
            _fig.update_layout(
                barmode="group",
                title="Cobertura de Artefatos por Reunião",
                plot_bgcolor="#0d1b2a",
                paper_bgcolor="#0d1b2a",
                font={"color": "#e2e8f0"},
                legend={"font": {"color": "#e2e8f0"}},
                xaxis={"gridcolor": "#1e3a55"},
                yaxis={"gridcolor": "#1e3a55", "tickvals": [0, 1],
                       "ticktext": ["❌ Ausente", "✅ Presente"]},
                height=340,
                margin={"t": 40, "b": 20, "l": 20, "r": 20},
            )
            st.plotly_chart(_fig, use_container_width=True)
        except ImportError:
            pass

        if st.button("🔄 Atualizar dados de saúde", key="health_refresh"):
            _load_health.clear()
            st.rerun()

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
        page_reqs = _paginate(reqs, "req", _filter_sig)
        _status_editor(
            "requirements", page_reqs,
            lambda r: f"REQ-{r.get('req_number', 0):03d} — {r.get('title', '—')}",
            "req",
        )
        st.markdown("")

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
            _edit_form_req(r)

        _render_group(page_reqs, pending=True,  render_fn=_render_req)
        _render_group(page_reqs, pending=False, render_fn=_render_req)

# ── TAB: Termos SBVR ─────────────────────────────────────────────────────────
_CAT_COLORS = {"concept": "#1e3a6e", "fact_type": "#0d4f2e", "role": "#4a3000", "process": "#134e4a"}

with tab_terms:
    if not terms:
        st.info("Nenhum termo SBVR para exibir com os filtros selecionados.")
    else:
        _bulk_validate("sbvr_terms", terms, "bulk_terms")
        page_terms = _paginate(terms, "terms", _filter_sig)
        _status_editor("sbvr_terms", page_terms, lambda t: t.get("term", "—"), "terms")
        st.markdown("")

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
            _edit_form_term(t)

        _render_group(page_terms, pending=True,  render_fn=_render_term)
        _render_group(page_terms, pending=False, render_fn=_render_term)

# ── TAB: Regras SBVR ─────────────────────────────────────────────────────────
_RULE_COLORS = {"constraint": "#4a0d0d", "operational": "#0d4f2e",
                "behavioral": "#4a3000", "structural": "#1e3a6e"}

with tab_rules:
    if not rules:
        st.info("Nenhuma regra SBVR para exibir com os filtros selecionados.")
    else:
        _bulk_validate("sbvr_rules", rules, "bulk_rules")
        page_rules = _paginate(rules, "rules", _filter_sig)
        _status_editor(
            "sbvr_rules", page_rules,
            lambda r: (r.get("rule_id") or "BR-?") + (f" — {r['nucleo_nominal']}" if r.get("nucleo_nominal") else ""),
            "rules",
        )
        st.markdown("")

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
            _edit_form_rule(r)

        _render_group(page_rules, pending=True,  render_fn=_render_rule)
        _render_group(page_rules, pending=False, render_fn=_render_rule)

# ── TAB: Processos BPMN ───────────────────────────────────────────────────────
with tab_bpmn:
    if not bpmn:
        st.info("Nenhum processo BPMN para exibir com os filtros selecionados.")
    else:
        _bulk_validate("bpmn_processes", bpmn, "bulk_bpmn")
        page_bpmn = _paginate(bpmn, "bpmn", _filter_sig)
        _status_editor("bpmn_processes", page_bpmn, lambda p: p.get("name", "—"), "bpmn")
        st.markdown("")

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
            _edit_form_bpmn(p)

        _render_group(page_bpmn, pending=True,  render_fn=_render_bpmn_proc)
        _render_group(page_bpmn, pending=False, render_fn=_render_bpmn_proc)

# ── Rodapé ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("Process2Diagram v5.15 — Validação de Artefatos")
