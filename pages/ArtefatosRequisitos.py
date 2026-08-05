# pages/ArtefatosRequisitos.py
# ─────────────────────────────────────────────────────────────────────────────
# Seção Artefatos (PC208) — assunto "Requisitos": Requisitos, Mind Map,
# Contradições (conflitos entre requisitos) e Histórico (inclui a seção
# "Governança de Requisitos" do PC199).
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from concurrent.futures import ThreadPoolExecutor as _TPE

from ui.auth_gate import apply_auth_gate
from modules.supabase_client import supabase_configured
from modules.text_utils import rule_keyword_pt  # noqa: F401 (mantido por paridade com o módulo original)
from core.project_store import promote_to_business_asset
from ui.project_selector import require_active_project
from ui.components.promote_asset import render_classification_fields
from ui.artefatos_shared import (
    inject_artefatos_css, render_artefatos_nav,
    _load_meetings, _load_requirements, _load_contradictions, _load_documents,
    _load_asset_meta_map, _load_req_versions, _load_req_versions_all,
    make_meet_label, make_doc_label, _origin_badge, make_promote_widget,
)

apply_auth_gate()
inject_artefatos_css()

st.markdown("# 📝 Artefatos — Requisitos")

if not supabase_configured():
    st.error("⚙️ Supabase não configurado. Adicione as credenciais em Settings → Secrets.")
    st.stop()

project_id, project_name = require_active_project()
render_artefatos_nav("pages/ArtefatosRequisitos.py")

_col_proj, _col_change = st.columns([5, 1])
with _col_proj:
    st.success(f"📁 **Contexto:** {project_name}")
with _col_change:
    st.page_link("pages/Home.py", label="Trocar")

with _TPE(max_workers=5) as _pool:
    _f_meetings       = _pool.submit(_load_meetings, project_id)
    _f_requirements   = _pool.submit(_load_requirements, project_id)
    _f_contradictions = _pool.submit(_load_contradictions, project_id)
    _f_documents      = _pool.submit(_load_documents, project_id)
    _f_asset_meta     = _pool.submit(_load_asset_meta_map, project_id)

    meetings       = _f_meetings.result()
    requirements   = _f_requirements.result()
    contradictions = _f_contradictions.result()
    documents      = _f_documents.result()
    asset_meta_map = _f_asset_meta.result()

meet_map = {m["id"]: m for m in meetings}
doc_map  = {d["id"]: d for d in documents}
meet_label      = make_meet_label(meet_map)
doc_label       = make_doc_label(doc_map)
_promote_widget = make_promote_widget(project_id, asset_meta_map)

n_total        = len(requirements)
n_contradicted = sum(1 for r in requirements if r.get("status") == "contradicted")

st.markdown("---")

tab_req, tab_mindmap, tab_contra, tab_hist = st.tabs([
    "📝 Requisitos",
    "🗺️ Mind Map",
    f"⚠️ Contradições ({len(contradictions)})",
    "📅 Histórico",
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — REQUISITOS
# ════════════════════════════════════════════════════════════════════════════
_STATUS_BADGE = {
    "backlog":      ("badge-backlog",      "Backlog"),
    "active":       ("badge-active",       "Ativo"),
    "approved":     ("badge-approved",     "Aprovado"),
    "in_progress":  ("badge-in-progress",  "Em Desenvolvimento"),
    "implemented":  ("badge-implemented",  "Implementado"),
    "revised":      ("badge-revised",      "Revisado"),
    "contradicted": ("badge-contradicted", "Contradição"),
    "deprecated":   ("badge-deprecated",   "Depreciado"),
    "rejected":     ("badge-rejected",     "Rejeitado"),
}
_DOT_COLOR = {
    "new":          "#60a5fa",
    "confirmed":    "#34d399",
    "revised":      "#fbbf24",
    "contradicted": "#f87171",
}
_REQ_PAGE_SIZE = 25

with tab_req:
    st.caption(
        "**Requisitos** são condições ou capacidades que o sistema ou processo deve satisfazer, "
        "extraídos das transcrições pela IA seguindo o padrão IEEE 830. "
        "Cada requisito tem tipo (funcional, não-funcional, regra de negócio…), prioridade e rastreabilidade até a reunião de origem."
    )
    if not requirements:
        st.info("Nenhum requisito registrado para este projeto.")
    else:
        # ── Filtros ──────────────────────────────────────────────────────
        col_f1, col_f2, col_f3, col_f4, col_f5 = st.columns(5)
        with col_f1:
            sel_status = st.selectbox(
                "Status",
                ["Todos", "backlog", "active", "approved", "in_progress",
                 "implemented", "revised", "contradicted", "deprecated", "rejected"],
                key="rt_status",
            )
        with col_f2:
            _types = sorted({r.get("req_type", "") for r in requirements if r.get("req_type")})
            sel_type = st.selectbox("Tipo", ["Todos"] + _types, key="rt_type")
        with col_f3:
            _prios = sorted({r.get("priority", "") for r in requirements if r.get("priority")})
            sel_prio = st.selectbox("Prioridade", ["Todos"] + _prios, key="rt_prio")
        with col_f4:
            sel_origin_req = st.selectbox(
                "Origem", ["Todas", "Transcrição", "Documento"], key="rt_origin"
            )
        with col_f5:
            sel_search = st.text_input(
                "Buscar", placeholder="título ou descrição…", key="rt_search"
            )

        # ── Aplicar filtros ───────────────────────────────────────────────
        filtered = requirements
        if sel_status != "Todos":
            filtered = [r for r in filtered if r.get("status") == sel_status]
        if sel_type != "Todos":
            filtered = [r for r in filtered if r.get("req_type") == sel_type]
        if sel_prio != "Todos":
            filtered = [r for r in filtered if r.get("priority") == sel_prio]
        if sel_origin_req == "Transcrição":
            filtered = [r for r in filtered if r.get("origin", "transcricao") != "documento"]
        elif sel_origin_req == "Documento":
            filtered = [r for r in filtered if r.get("origin") == "documento"]
        if sel_search:
            _q = sel_search.lower()
            filtered = [
                r for r in filtered
                if _q in (r.get("title") or "").lower()
                or _q in (r.get("description") or "").lower()
            ]

        n_filtered = len(filtered)

        # ── Paginação — reset ao mudar filtros ou projeto ─────────────────
        _filter_sig = f"{project_id}|{sel_status}|{sel_type}|{sel_prio}|{sel_origin_req}|{sel_search}"
        if st.session_state.get("_rt_last_filter") != _filter_sig:
            st.session_state["rt_page"] = 0
            st.session_state["_rt_last_filter"] = _filter_sig

        _page       = min(st.session_state.get("rt_page", 0),
                          max(0, (n_filtered - 1) // _REQ_PAGE_SIZE))
        _n_pages    = max(1, (n_filtered + _REQ_PAGE_SIZE - 1) // _REQ_PAGE_SIZE)
        _page_start = _page * _REQ_PAGE_SIZE
        _page_end   = min(_page_start + _REQ_PAGE_SIZE, n_filtered)
        page_items  = filtered[_page_start:_page_end]

        # ── Navegação de página (topo) ────────────────────────────────────
        _nav1, _nav2, _nav3, _nav4 = st.columns([1, 1, 4, 1])
        with _nav1:
            if st.button("← Anterior", key="rt_prev", disabled=(_page == 0)):
                st.session_state["rt_page"] = _page - 1
                st.rerun()
        with _nav2:
            if st.button("Próximo →", key="rt_next", disabled=(_page == _n_pages - 1)):
                st.session_state["rt_page"] = _page + 1
                st.rerun()
        with _nav3:
            st.caption(
                f"Itens **{_page_start + 1}–{_page_end}** de **{n_filtered}** "
                f"· Página **{_page + 1}** de **{_n_pages}**"
                + (f"  ·  *(filtro ativo)*" if n_filtered < n_total else "")
            )
        with _nav4:
            _go = st.number_input(
                "Ir para", min_value=1, max_value=_n_pages, value=_page + 1,
                step=1, key="rt_goto", label_visibility="collapsed",
            )
            if _go - 1 != _page:
                st.session_state["rt_page"] = int(_go) - 1
                st.rerun()

        # ── Tabela compacta ───────────────────────────────────────────────
        _rows_html = ""
        for _idx, _r in enumerate(page_items, start=_page_start + 1):
            _num   = _r.get("req_number", 0)
            _title = (_r.get("title") or "—")[:60]
            _rtype = _r.get("req_type") or "—"
            _prio  = _r.get("priority") or "—"
            _st    = _r.get("status", "active")
            _bc, _bt = _STATUS_BADGE.get(_st, ("badge-active", _st))
            _orig_icon = "📄" if _r.get("origin") == "documento" else "🎙️"
            _rows_html += (
                f"<tr>"
                f"<td style='color:#64748b;text-align:right;padding:4px 6px'>{_idx}</td>"
                f"<td style='padding:4px 8px'><code>REQ-{_num:03d}</code></td>"
                f"<td style='padding:4px 8px'>{_title}</td>"
                f"<td style='padding:4px 8px;white-space:nowrap'>{_rtype}</td>"
                f"<td style='padding:4px 8px'><span class='badge {_bc}'>{_bt}</span></td>"
                f"<td style='padding:4px 8px;white-space:nowrap'>{_prio}</td>"
                f"<td style='padding:4px 8px;text-align:center'>{_orig_icon}</td>"
                f"</tr>"
            )
        st.markdown(
            "<table style='width:100%;font-size:0.83em;border-collapse:collapse'>"
            "<thead><tr style='border-bottom:1px solid #334155'>"
            "<th style='padding:4px 6px;color:#64748b;text-align:right'>#</th>"
            "<th align='left' style='padding:4px 8px'>ID</th>"
            "<th align='left' style='padding:4px 8px'>Título</th>"
            "<th align='left' style='padding:4px 8px'>Tipo</th>"
            "<th align='left' style='padding:4px 8px'>Status</th>"
            "<th align='left' style='padding:4px 8px'>Prioridade</th>"
            "<th align='center' style='padding:4px 8px'>Origem</th>"
            "</tr></thead>"
            f"<tbody>{_rows_html}</tbody></table>",
            unsafe_allow_html=True,
        )

        # ── Promoção em lote (melhorias/promocao-ativos-negocio.md §6 Fase A) ──
        # Elevada da proposta original de "Fase D, não incluída" para dentro da
        # Fase A — exige mostrar a lista COMPLETA dos itens do lote antes de
        # confirmar (decisão do usuário), nunca promove sem revisão explícita.
        with st.expander("📦 Promoção em Lote a Ativo de Negócio", expanded=False):
            st.caption(
                "Selecione vários requisitos (respeita os filtros acima) e promova todos de "
                "uma vez, com a mesma classificação. A lista completa aparece abaixo antes de "
                "confirmar — nada é promovido sem revisão explícita."
            )
            _bulk_opts = {
                f"REQ-{r['req_number']:03d} — {r['title']}": r
                for r in filtered
                if ("requirement", r["id"]) not in asset_meta_map
            }
            if not _bulk_opts:
                st.caption("Nenhum requisito elegível — os requisitos filtrados já são ativos de negócio, ou não há requisitos filtrados.")
            else:
                _bulk_sel_labels = st.multiselect(
                    "Requisitos a promover", list(_bulk_opts.keys()), key="rt_bulk_sel",
                )
                if _bulk_sel_labels:
                    st.markdown(f"**Revisão — {len(_bulk_sel_labels)} item(ns) selecionado(s) para promoção:**")
                    st.table([
                        {
                            "ID": lbl.split(" — ")[0],
                            "Título": _bulk_opts[lbl].get("title", ""),
                            "Status": _bulk_opts[lbl].get("status", ""),
                        }
                        for lbl in _bulk_sel_labels
                    ])
                    with st.form("rt_bulk_form"):
                        st.caption("Esta classificação será aplicada a **todos** os itens revisados acima.")
                        _bi, _bp, _bc, _bj = render_classification_fields("rt_bulk")
                        if st.form_submit_button(f"⭐ Promover {len(_bulk_sel_labels)} requisito(s)", type="primary"):
                            if not _bi or not _bp or not _bj.strip():
                                st.error("Interesse, Perspectiva e Justificativa são obrigatórios.")
                            else:
                                _ok_count = 0
                                for _lbl in _bulk_sel_labels:
                                    _r_bulk = _bulk_opts[_lbl]
                                    _result = promote_to_business_asset(
                                        project_id, "requirement", _r_bulk["id"],
                                        business_interest=_bi,
                                        business_perspective=_bp,
                                        promotion_justification=_bj.strip(),
                                        formal_classification=_bc,
                                        created_by=st.session_state.get("_usuario_login", ""),
                                    )
                                    if _result:
                                        _ok_count += 1
                                if _ok_count == len(_bulk_sel_labels):
                                    st.success(f"{_ok_count} requisito(s) promovido(s) com sucesso.")
                                else:
                                    st.warning(f"{_ok_count}/{len(_bulk_sel_labels)} promovido(s) — verifique erros.")
                                _load_asset_meta_map.clear()
                                st.rerun()

        # ── Painel de detalhes (um requisito por vez) ─────────────────────
        st.markdown("---")
        st.markdown("##### Detalhes do requisito")
        st.caption(
            "Selecione um requisito para ver descrição completa e histórico de versões. "
            "O histórico é carregado do banco de dados apenas quando solicitado."
        )

        _detail_opts = {
            f"REQ-{r['req_number']:03d} — {r['title']}": r
            for r in filtered
        }
        if _detail_opts:
            _sel_det_lbl = st.selectbox(
                "Selecionar requisito",
                list(_detail_opts.keys()),
                key="rt_detail_sel",
            )
            _det_req = _detail_opts[_sel_det_lbl]
            _det_status = _det_req.get("status", "active")
            _det_bc, _det_bt = _STATUS_BADGE.get(_det_status, ("badge-active", _det_status))

            _dd1, _dd2 = st.columns([3, 1])
            with _dd1:
                st.markdown(
                    f'<span class="badge {_det_bc}">{_det_bt}</span> '
                    f'{_origin_badge(_det_req.get("origin"))}',
                    unsafe_allow_html=True,
                )
                st.markdown(f"**Descrição:** {_det_req.get('description') or '—'}")
                if _det_req.get("cited_by"):
                    st.caption(f"👤 Proponente: **{_det_req['cited_by']}**")
                if _det_req.get("source_quote"):
                    st.caption(f'💬 *"{_det_req["source_quote"]}"*')
                if _det_req.get("status_note"):
                    st.caption(f"📝 {_det_req['status_note']}")
                if _det_req.get("resolution_notes"):
                    _impl_date = (_det_req.get("implemented_at") or "")[:10]
                    _impl_label = f"✅ Solução implementada" + (f" ({_impl_date})" if _impl_date else "")
                    st.success(f"**{_impl_label}:** {_det_req['resolution_notes']}")
            with _dd2:
                if _det_req.get("origin") == "documento":
                    st.caption(f"📄 {doc_label(_det_req.get('doc_ref'))}")
                else:
                    st.caption(f"🏁 {meet_label(_det_req.get('first_meeting_id'))}")
                    st.caption(f"🔄 {meet_label(_det_req.get('last_meeting_id'))}")
                if _det_req.get("owner"):
                    st.caption(f"🙋 {_det_req['owner']}")

            # Histórico de versões — carregado sob demanda (1 query por seleção)
            _det_vers = _load_req_versions(_det_req["id"])
            if _det_vers:
                with st.expander(f"📋 Histórico de versões ({len(_det_vers)})", expanded=False):
                    for _v in _det_vers:
                        _ct  = _v.get("change_type", "")
                        _dot = _DOT_COLOR.get(_ct, "#aaa")
                        _flag = " ⚠️" if _v.get("contradiction_flag") else ""
                        st.markdown(
                            f'<span class="version-dot" style="background:{_dot}"></span>'
                            f'**v{_v.get("version","?")}** — {meet_label(_v.get("meeting_id"))} '
                            f'· `{_ct}`{_flag}',
                            unsafe_allow_html=True,
                        )
                        if _v.get("change_summary"):
                            st.caption(f"   ↳ {_v['change_summary']}")
                        if _v.get("cited_by"):
                            st.caption(f"   👤 {_v['cited_by']}")
                        if _v.get("source_quote"):
                            st.caption(f'   💬 *"{_v["source_quote"]}"*')
                        if _v.get("contradiction_detail"):
                            st.error(_v["contradiction_detail"])

            _promote_widget("requirement", _det_req["id"], f"REQ-{_det_req['req_number']:03d} — {_det_req['title']}")
        else:
            st.info("Nenhum requisito corresponde aos filtros aplicados.")

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — MIND MAP
# ════════════════════════════════════════════════════════════════════════════
with tab_mindmap:
    st.caption(
        "**Mind Map de Requisitos** — visualização hierárquica interativa que agrupa os requisitos "
        "por tipo (funcional, não-funcional, regra de negócio…). "
        "Permite navegar, colapsar ramos e exportar como imagem para apresentações."
    )
    if not requirements:
        st.info("Nenhum requisito registrado para este projeto.")
    else:
        try:
            from modules.requirements_mindmap import build_mindmap_tree_from_dicts
            from modules.mindmap_interactive import render_interactive_mindmap
            _mindmap_ok = True
        except Exception as _mm_err:
            st.error(f"Erro ao carregar módulo de mind map: {_mm_err}")
            _mindmap_ok = False

        col_mm1, col_mm2, col_mm3 = st.columns([2, 2, 2])
        with col_mm1:
            mm_status = st.selectbox(
                "Filtrar por status",
                ["Todos", "backlog", "active", "approved", "in_progress",
                 "implemented", "revised", "contradicted", "deprecated", "rejected"],
                key="mm_status",
            )
        with col_mm2:
            mm_types = sorted({r.get("req_type", "") for r in requirements if r.get("req_type")})
            mm_type = st.selectbox("Filtrar por tipo", ["Todos"] + mm_types, key="mm_type")
        with col_mm3:
            mm_height = st.slider("Altura (px)", 500, 1200, 700, 50, key="mm_height")

        mm_reqs = requirements
        if mm_status != "Todos":
            mm_reqs = [r for r in mm_reqs if r.get("status") == mm_status]
        if mm_type != "Todos":
            mm_reqs = [r for r in mm_reqs if r.get("req_type") == mm_type]

        if not mm_reqs:
            st.info("Nenhum requisito corresponde aos filtros selecionados.")
        elif _mindmap_ok:
            st.caption(f"Exibindo {len(mm_reqs)} requisito(s) no mind map.")
            tree = build_mindmap_tree_from_dicts(mm_reqs, project_name)
            if tree.get("children"):
                render_interactive_mindmap(tree, height=mm_height)
            else:
                st.info("Não foi possível gerar o mind map para os requisitos selecionados.")

# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — CONTRADIÇÕES
# ════════════════════════════════════════════════════════════════════════════
with tab_contra:
    st.caption(
        "**Contradições** são conflitos detectados entre requisitos de reuniões diferentes — "
        "situações em que duas afirmações se opõem ou se excluem mutuamente. "
        "A detecção usa similaridade semântica (embeddings) e análise de antônimos; "
        "cada conflito traz os trechos originais e uma explicação gerada pela IA."
    )
    if not contradictions:
        st.success("✅ Nenhuma contradição detectada neste projeto.")
    else:
        st.warning(f"**{len(contradictions)} contradição(ões) ativa(s)** requerem atenção.")
        st.markdown("")

        for c in contradictions:
            req_info = c.get("requirements") or {}
            num      = req_info.get("req_number", "?")
            title    = req_info.get("title", "")
            meet     = meet_label(c.get("meeting_id"))

            with st.expander(f"⚠️ REQ-{num:03d} — {title}", expanded=True):
                st.markdown(
                    f'<div class="contradiction-box">'
                    f'<strong>Reunião que gerou a contradição:</strong> {meet}<br>'
                    f'<strong>Nova definição:</strong> {c.get("description", "—")}<br><br>'
                    f'<strong>Análise:</strong> {c.get("contradiction_detail", "—")}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                if c.get("change_summary"):
                    st.info(f"📝 Resumo da mudança: {c['change_summary']}")

# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — HISTÓRICO POR REQUISITO
# ════════════════════════════════════════════════════════════════════════════
with tab_hist:
    st.caption(
        "**Histórico de Requisitos** — linha do tempo de como cada requisito evoluiu entre reuniões. "
        "Cada versão registra a descrição, prioridade e status vigentes naquele momento, "
        "permitindo auditar mudanças de escopo ao longo do projeto."
    )

    # ── Governança de Requisitos — visão agregada (PC199) ──────────────────
    # Consolida em um só lugar 3 sinais hoje espalhados em tools de chat
    # (get_requirement_history, generate_requirements_waterfall, analisar_tendencias):
    # instabilidade (nº de revisões), contradição não resolvida e evolução por reunião.
    # Usa apenas o sistema de contradição de requirement_versions/requirements.status —
    # kh_contradictions (Knowledge Hub) é um mecanismo separado, não relacionado.
    if requirements:
        st.markdown("#### 🏛️ Governança de Requisitos")
        st.caption(
            "Quais requisitos mudaram mais e quais têm contradição em aberto — "
            "sinal de risco para revisão de escopo, não coberto pelas outras abas."
        )
        _gov_versions = _load_req_versions_all(project_id)

        _GOV_CHANGE_LABEL = {
            "new": "Nova", "confirmed": "Confirmada",
            "revised": "Revisada", "contradicted": "Contradição",
        }
        _version_count: dict[str, int] = {}
        _last_change: dict[str, str] = {}
        for _v in _gov_versions:
            _rid = _v.get("requirement_id")
            if not _rid:
                continue
            _version_count[_rid] = _version_count.get(_rid, 0) + 1
            _last_change[_rid] = _v.get("change_type", "—")

        _n_revised_once = sum(1 for r in requirements if _version_count.get(r["id"], 0) > 1)
        _n_unstable = sum(1 for r in requirements if _version_count.get(r["id"], 0) >= 3)
        _pct_revised = (_n_revised_once / n_total * 100) if n_total else 0.0

        _gc1, _gc2, _gc3, _gc4 = st.columns(4)
        _gc1.metric("Requisitos", n_total)
        _gc2.metric("Com ≥1 revisão", _n_revised_once, delta=f"{_pct_revised:.0f}%")
        _gc3.metric("⚠️ Instáveis (≥3 revisões)", _n_unstable,
                    delta_color="off" if _n_unstable == 0 else "inverse")
        _gc4.metric("⚠️ Contradições não resolvidas", n_contradicted,
                    delta_color="off" if n_contradicted == 0 else "inverse")

        _gov_rows = [
            {
                "REQ": f"REQ-{r['req_number']:03d}",
                "Título": (r.get("title") or "—")[:60],
                "Revisões": _version_count.get(r["id"], 0),
                "Última mudança": _GOV_CHANGE_LABEL.get(_last_change.get(r["id"]), "—"),
                "Status": _STATUS_BADGE.get(r.get("status", "active"), ("", r.get("status", "—")))[1],
                "⚠️": "⚠️" if r.get("status") == "contradicted" else "",
            }
            for r in requirements
            if _version_count.get(r["id"], 0) > 1
        ]
        _gov_rows.sort(key=lambda x: x["Revisões"], reverse=True)

        if not _gov_rows:
            st.info("Nenhum requisito foi revisado mais de uma vez neste projeto ainda.")
        else:
            st.markdown("**Requisitos que mais mudaram**")
            _GOV_TOP_N = 20
            st.dataframe(_gov_rows[:_GOV_TOP_N], use_container_width=True, hide_index=True)
            if len(_gov_rows) > _GOV_TOP_N:
                st.caption(f"Mostrando {_GOV_TOP_N} de {len(_gov_rows)} requisitos com ≥2 revisões.")

            # ── Evolução líquida de requisitos ativos por reunião ───────────
            _added: dict[int, int] = {}
            _removed: dict[int, int] = {}
            for r in requirements:
                _mid = r.get("first_meeting_id")
                if not _mid or _mid not in meet_map:
                    continue
                _mnum = meet_map[_mid].get("meeting_number")
                if _mnum is None:
                    continue
                _added[_mnum] = _added.get(_mnum, 0) + 1
                if (r.get("status") or "").strip().lower() in {"contradicted", "deprecated"}:
                    _removed[_mnum] = _removed.get(_mnum, 0) + 1

            _meeting_nums = sorted(_added.keys())
            if _meeting_nums:
                try:
                    import plotly.graph_objects as go
                    _wx, _wy, _measure, _text = [], [], [], []
                    for _n in _meeting_nums:
                        _net = _added[_n] - _removed.get(_n, 0)
                        _wx.append(f"Reunião {_n}")
                        _wy.append(_net)
                        _measure.append("relative")
                        _text.append(f"+{_added[_n]}" + (f" -{_removed[_n]}" if _removed.get(_n) else ""))
                    _wx.append("Total")
                    _wy.append(0)
                    _measure.append("total")
                    _text.append("")
                    _gov_fig = go.Figure(go.Waterfall(
                        x=_wx, y=_wy, measure=_measure, text=_text, textposition="outside",
                        increasing={"marker": {"color": "#10b981"}},
                        decreasing={"marker": {"color": "#ef4444"}},
                        totals={"marker": {"color": "#2563eb"}},
                    ))
                    _gov_fig.update_layout(
                        title="Evolução líquida de requisitos ativos por reunião",
                        plot_bgcolor="#0d1b2a",
                        paper_bgcolor="#0d1b2a",
                        font={"color": "#e2e8f0"},
                        showlegend=False,
                        xaxis={"gridcolor": "#1e3a55"},
                        yaxis={"gridcolor": "#1e3a55"},
                        height=340,
                        margin={"t": 40, "b": 20, "l": 20, "r": 20},
                    )
                    st.plotly_chart(_gov_fig, use_container_width=True)
                except ImportError:
                    pass

        if st.button("🔄 Atualizar dados de governança", key="gov_refresh"):
            _load_req_versions_all.clear()
            st.rerun()

        st.markdown("---")

    if not requirements:
        st.info("Nenhum requisito registrado.")
    else:
        req_options = {
            f"REQ-{r['req_number']:03d} — {r['title']}": r
            for r in requirements
        }
        sel_req_label = st.selectbox("Selecione o requisito", list(req_options.keys()),
                                     key="rt_hist_sel")
        sel_req = req_options[sel_req_label]
        versions = _load_req_versions(sel_req["id"])

        if not versions:
            st.info("Nenhuma versão registrada.")
        else:
            st.markdown(f"### Linha do tempo — REQ-{sel_req['req_number']:03d}")
            _DOT_COLOR = {
                "new":          "#60a5fa",
                "confirmed":    "#34d399",
                "revised":      "#fbbf24",
                "contradicted": "#f87171",
            }
            for v in versions:
                ct    = v.get("change_type", "new")
                color = _DOT_COLOR.get(ct, "#aaa")
                flag  = " ⚠️ **CONTRADIÇÃO**" if v.get("contradiction_flag") else ""
                m_lbl = meet_label(v.get("meeting_id"))

                st.markdown(
                    f'<div style="border-left:3px solid {color};padding:.6rem 1rem;'
                    f'margin-bottom:.5rem;border-radius:0 6px 6px 0;'
                    f'background:rgba(15,32,64,.6)">'
                    f'<strong>v{v.get("version","?")} · {m_lbl}</strong>'
                    f'<span style="color:{color};margin-left:8px">[{ct}]</span>{flag}<br>'
                    f'<strong>Título:</strong> {v.get("title","—")}<br>'
                    f'<strong>Descrição:</strong> {v.get("description","—")}',
                    unsafe_allow_html=True,
                )
                if v.get("change_summary"):
                    st.markdown(
                        f'<span style="color:#fbbf24">↳ {v["change_summary"]}</span>',
                        unsafe_allow_html=True,
                    )
                if v.get("cited_by"):
                    st.markdown(
                        f'<span style="color:#93c5fd">👤 Proponente: <strong>{v["cited_by"]}</strong></span>',
                        unsafe_allow_html=True,
                    )
                if v.get("source_quote"):
                    st.markdown(
                        f'<span style="color:#d1d5db">💬 <em>"{v["source_quote"]}"</em></span>',
                        unsafe_allow_html=True,
                    )
                if v.get("contradiction_detail"):
                    st.markdown(
                        f'<span style="color:#f87171">⚠️ {v["contradiction_detail"]}</span>',
                        unsafe_allow_html=True,
                    )
                st.markdown("</div>", unsafe_allow_html=True)

