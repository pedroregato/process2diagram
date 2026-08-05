# pages/ArtefatosModelagem.py
# ─────────────────────────────────────────────────────────────────────────────
# Seção Artefatos (PC208) — assunto "Modelagem Formal": SBVR, Processos BPMN
# e DMN — os 3 artefatos formais estilo OMG.
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
from modules.text_utils import rule_keyword_pt
from core.project_store import load_meeting_as_hub, save_bpmn_from_hub, bpmn_tables_exist
from ui.project_selector import require_active_project
from ui.components.artifact_feedback import render_artifact_feedback
from ui.artefatos_shared import (
    inject_artefatos_css, render_artefatos_nav, dmn_session_key,
    _load_meetings, _load_sbvr_terms, _load_sbvr_rules,
    _load_bpmn_procs, _load_bpmn_versions, _load_documents, _load_asset_meta_map,
    _load_dmn,
    make_meet_label, make_doc_label, _origin_badge, make_promote_widget,
)

apply_auth_gate()
inject_artefatos_css()

st.markdown("# 📐 Artefatos — Modelagem Formal")

if not supabase_configured():
    st.error("⚙️ Supabase não configurado. Adicione as credenciais em Settings → Secrets.")
    st.stop()

project_id, project_name = require_active_project()
render_artefatos_nav("pages/ArtefatosModelagem.py")

_col_proj, _col_change = st.columns([5, 1])
with _col_proj:
    st.success(f"📁 **Contexto:** {project_name}")
with _col_change:
    st.page_link("pages/Home.py", label="Trocar")

with _TPE(max_workers=5) as _pool:
    _f_meetings   = _pool.submit(_load_meetings, project_id)
    _f_sbvr_terms = _pool.submit(_load_sbvr_terms, project_id)
    _f_sbvr_rules = _pool.submit(_load_sbvr_rules, project_id)
    _f_bpmn_procs = _pool.submit(_load_bpmn_procs, project_id)
    _f_documents  = _pool.submit(_load_documents, project_id)
    _f_asset_meta = _pool.submit(_load_asset_meta_map, project_id)

    meetings       = _f_meetings.result()
    sbvr_terms     = _f_sbvr_terms.result()
    sbvr_rules     = _f_sbvr_rules.result()
    bpmn_procs     = _f_bpmn_procs.result()
    documents      = _f_documents.result()
    asset_meta_map = _f_asset_meta.result()

# DMN: lê do session_state se já carregado nesta sessão (visita anterior a
# esta página). None = ainda não carregado. [] = carregado, sem dados.
_DMN_SS = dmn_session_key(project_id)
dmn_decisions = st.session_state.get(_DMN_SS, None)

meet_map = {m["id"]: m for m in meetings}
doc_map  = {d["id"]: d for d in documents}
meet_label      = make_meet_label(meet_map)
doc_label       = make_doc_label(doc_map)
_promote_widget = make_promote_widget(project_id, asset_meta_map)

st.markdown("---")

tab_sbvr, tab_bpmn, tab_dmn = st.tabs([
    f"📖 SBVR ({len(sbvr_terms)}T · {len(sbvr_rules)}R)",
    f"📐 Processos BPMN ({len(bpmn_procs)})",
    f"⚖️ DMN ({len(dmn_decisions) if dmn_decisions is not None else '…'})",
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 6 — SBVR
# ════════════════════════════════════════════════════════════════════════════
_CATEGORY_BADGE = {
    "concept":   ("badge-new",       "Conceito"),
    "fact_type": ("badge-confirmed",  "Tipo de Fato"),
    "role":      ("badge-revised",    "Papel"),
    "process":   ("badge-active",     "Processo"),
}
_RULE_BADGE = {
    "constraint":   ("badge-contradicted", "Restrição"),
    "operational":  ("badge-active",       "Operacional"),
    "behavioral":   ("badge-revised",      "Comportamental"),
    "structural":   ("badge-new",          "Estrutural"),
}
_SBVR_PAGE_SIZE = 25  # mesma paginação da aba Requisitos — contextos grandes (ex: 751 termos)
                      # renderizavam TODOS os expanders de uma vez, mesmo sem essa aba estar
                      # visível (st.tabs() executa o corpo de todas as abas a cada rerun)

with tab_sbvr:
    st.caption(
        "**SBVR (Semantics of Business Vocabulary and Rules)** é um padrão OMG para formalizar "
        "o vocabulário e as regras de negócio de um domínio em linguagem não-ambígua. "
        "Os **termos** definem os conceitos do negócio; as **regras** expressam obrigações, "
        "proibições e permissões que governam o processo — cada uma rastreável à reunião e ao falante de origem."
    )
    if not sbvr_terms and not sbvr_rules:
        st.info("Nenhum dado SBVR registrado. Execute o pipeline com o agente SBVR habilitado.")
    else:
        col_t, col_r = st.columns(2)

        with col_t:
            st.markdown(f"### 📚 Vocabulário ({len(sbvr_terms)} termos)")
            meet_ids = sorted({t.get("meeting_id") for t in sbvr_terms if t.get("meeting_id")})
            meet_labels_sbvr = {"Todas": None}
            for mid in meet_ids:
                meet_labels_sbvr[meet_label(mid)] = mid
            sel_meet_t = st.selectbox("Reunião", list(meet_labels_sbvr.keys()), key="sbvr_meet_t")
            filtered_terms = sbvr_terms if not meet_labels_sbvr[sel_meet_t] else [
                t for t in sbvr_terms if t.get("meeting_id") == meet_labels_sbvr[sel_meet_t]
            ]
            cats = sorted({t.get("category", "") for t in filtered_terms if t.get("category")})
            sel_cat = st.selectbox("Categoria", ["Todas"] + cats, key="sbvr_cat")
            if sel_cat != "Todas":
                filtered_terms = [t for t in filtered_terms if t.get("category") == sel_cat]
            n_filtered_t = len(filtered_terms)
            st.caption(f"{n_filtered_t} termo(s)")
            st.markdown("")

            # ── Paginação — reset ao mudar filtros ─────────────────────────
            _t_filter_sig = f"{project_id}|{sel_meet_t}|{sel_cat}"
            if st.session_state.get("_sbvr_t_last_filter") != _t_filter_sig:
                st.session_state["sbvr_t_page"] = 0
                st.session_state["_sbvr_t_last_filter"] = _t_filter_sig
            _t_page       = min(st.session_state.get("sbvr_t_page", 0),
                                max(0, (n_filtered_t - 1) // _SBVR_PAGE_SIZE))
            _t_n_pages    = max(1, (n_filtered_t + _SBVR_PAGE_SIZE - 1) // _SBVR_PAGE_SIZE)
            _t_page_start = _t_page * _SBVR_PAGE_SIZE
            _t_page_end   = min(_t_page_start + _SBVR_PAGE_SIZE, n_filtered_t)
            page_terms    = filtered_terms[_t_page_start:_t_page_end]

            if n_filtered_t > _SBVR_PAGE_SIZE:
                _tnav1, _tnav2, _tnav3 = st.columns([1, 1, 2])
                with _tnav1:
                    if st.button("← Anterior", key="sbvr_t_prev", disabled=(_t_page == 0)):
                        st.session_state["sbvr_t_page"] = _t_page - 1
                        st.rerun()
                with _tnav2:
                    if st.button("Próximo →", key="sbvr_t_next", disabled=(_t_page == _t_n_pages - 1)):
                        st.session_state["sbvr_t_page"] = _t_page + 1
                        st.rerun()
                with _tnav3:
                    st.caption(
                        f"**{_t_page_start + 1}–{_t_page_end}** de **{n_filtered_t}** "
                        f"· Pág. **{_t_page + 1}/{_t_n_pages}**"
                    )

            for t in page_terms:
                cat = t.get("category", "concept")
                badge_cls, badge_txt = _CATEGORY_BADGE.get(cat, ("badge-active", cat))
                meet_info = t.get("meetings") or {}
                m_num = meet_info.get("meeting_number")
                t_origin = t.get("origin", "transcricao")
                if t_origin == "documento":
                    source_label = f"📄 {doc_label(t.get('doc_ref'))}"
                elif t.get("source") == "assistente" or not m_num:
                    source_label = "🤖 Assistente"
                else:
                    source_label = f"🗓️ Reunião {m_num}"
                with st.expander(f"**{t.get('term', '—')}**", expanded=False):
                    st.markdown(
                        f'<span class="badge {badge_cls}">{badge_txt}</span> '
                        f'{_origin_badge(t_origin)}',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**Definição:** {t.get('definition', '—')}")
                    st.caption(source_label)
                    _promote_widget("sbvr_term", t["id"], t.get("term", "—"))

        with col_r:
            st.markdown(f"### 📋 Regras de Negócio ({len(sbvr_rules)} regras)")
            meet_ids_r = sorted({r.get("meeting_id") for r in sbvr_rules if r.get("meeting_id")})
            meet_labels_sbvr_r = {"Todas": None}
            for mid in meet_ids_r:
                meet_labels_sbvr_r[meet_label(mid)] = mid
            sel_meet_r = st.selectbox("Reunião", list(meet_labels_sbvr_r.keys()), key="sbvr_meet_r")
            filtered_rules = sbvr_rules if not meet_labels_sbvr_r[sel_meet_r] else [
                r for r in sbvr_rules if r.get("meeting_id") == meet_labels_sbvr_r[sel_meet_r]
            ]
            types = sorted({r.get("rule_type", "") for r in filtered_rules if r.get("rule_type")})
            sel_rtype = st.selectbox("Tipo", ["Todos"] + types, key="sbvr_rtype")
            if sel_rtype != "Todos":
                filtered_rules = [r for r in filtered_rules if r.get("rule_type") == sel_rtype]
            n_filtered_r = len(filtered_rules)
            st.caption(f"{n_filtered_r} regra(s)")
            st.markdown("")

            # ── Paginação — reset ao mudar filtros ─────────────────────────
            _r_filter_sig = f"{project_id}|{sel_meet_r}|{sel_rtype}"
            if st.session_state.get("_sbvr_r_last_filter") != _r_filter_sig:
                st.session_state["sbvr_r_page"] = 0
                st.session_state["_sbvr_r_last_filter"] = _r_filter_sig
            _r_page       = min(st.session_state.get("sbvr_r_page", 0),
                                max(0, (n_filtered_r - 1) // _SBVR_PAGE_SIZE))
            _r_n_pages    = max(1, (n_filtered_r + _SBVR_PAGE_SIZE - 1) // _SBVR_PAGE_SIZE)
            _r_page_start = _r_page * _SBVR_PAGE_SIZE
            _r_page_end   = min(_r_page_start + _SBVR_PAGE_SIZE, n_filtered_r)
            page_rules    = filtered_rules[_r_page_start:_r_page_end]

            if n_filtered_r > _SBVR_PAGE_SIZE:
                _rnav1, _rnav2, _rnav3 = st.columns([1, 1, 2])
                with _rnav1:
                    if st.button("← Anterior", key="sbvr_r_prev", disabled=(_r_page == 0)):
                        st.session_state["sbvr_r_page"] = _r_page - 1
                        st.rerun()
                with _rnav2:
                    if st.button("Próximo →", key="sbvr_r_next", disabled=(_r_page == _r_n_pages - 1)):
                        st.session_state["sbvr_r_page"] = _r_page + 1
                        st.rerun()
                with _rnav3:
                    st.caption(
                        f"**{_r_page_start + 1}–{_r_page_end}** de **{n_filtered_r}** "
                        f"· Pág. **{_r_page + 1}/{_r_n_pages}**"
                    )

            for idx, r in enumerate(page_rules, _r_page_start + 1):
                rtype = r.get("rule_type", "constraint")
                badge_cls, badge_txt = _RULE_BADGE.get(rtype, ("badge-active", rtype))
                rule_id = r.get("rule_id") or f"BR-{idx:03d}"
                meet_info = r.get("meetings") or {}
                m_num = meet_info.get("meeting_number")
                r_origin = r.get("origin", "transcricao")
                kw = r.get("nucleo_nominal") or rule_keyword_pt(r.get("statement", ""))
                label = f"**{rule_id}**  —  {kw}" if kw else f"**{rule_id}**"
                with st.expander(label, expanded=False):
                    st.markdown(
                        f'<span class="badge {badge_cls}">{badge_txt}</span> '
                        f'{_origin_badge(r_origin)}',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"{r.get('statement', '—')}")
                    if r_origin == "documento":
                        footer = f"📄 {doc_label(r.get('doc_ref'))}"
                    elif m_num:
                        footer = f"🗓️ Reunião {m_num}"
                    else:
                        footer = "🤖 Assistente"
                    if r.get("source") and r["source"] not in ("manual", "assistente"):
                        footer += f" · 👤 {r['source']}"
                    st.caption(footer)
                    _promote_widget("sbvr_rule", r["id"], rule_id)

# ════════════════════════════════════════════════════════════════════════════
# TAB 7 — PROCESSOS BPMN
# ════════════════════════════════════════════════════════════════════════════
import streamlit.components.v1 as components


def _do_bpmn_reconvert(process_id: str, meeting_id: str, project_id: str) -> None:
    """Re-run AgentBPMN (skill v7.0) sobre uma reunião e salva como nova versão."""
    from modules.session_security import get_session_llm_client

    client_info  = get_session_llm_client(st.session_state.get("selected_provider", ""))
    provider_cfg = st.session_state.get("provider_cfg") or {}

    if not client_info:
        st.error("Configure um provedor LLM em **Sistema → Configurações** antes de reconverter.")
        return

    with st.spinner("Carregando transcrição da reunião..."):
        hub = load_meeting_as_hub(meeting_id, project_id)

    if not hub:
        st.error("Reunião não encontrada no banco de dados.")
        return

    transcript = (hub.transcript_clean or hub.transcript_raw or "").strip()
    if len(transcript) < 50:
        st.error(
            "Transcrição não disponível ou muito curta para esta reunião. "
            "Reprocesse a transcrição pelo Pipeline antes de reconverter."
        )
        return

    with st.spinner("Reconvertendo com AgentBPMN (Method & Style v7.0)..."):
        try:
            from agents.agent_bpmn import AgentBPMN
            agent = AgentBPMN(client_info, provider_cfg)
            hub   = agent.run(hub)
        except Exception as exc:
            st.error(f"Erro na reconversão: {exc}")
            return

    if not getattr(hub.bpmn, "ready", False):
        st.error("O agente não produziu um modelo BPMN válido.")
        return

    n_steps    = len(hub.bpmn.steps)
    n_call_act = sum(1 for s in hub.bpmn.steps if s.task_type == "callActivity")
    n_loops    = sum(1 for s in hub.bpmn.steps if s.task_type in ("loopTask", "multiInstanceTask"))

    with st.spinner("Salvando nova versão..."):
        saved = save_bpmn_from_hub(meeting_id, project_id, hub, bpmn_process_id=process_id)

    if saved:
        st.success("Diagrama reconvertido e salvo como nova versão!")
        c1, c2, c3 = st.columns(3)
        c1.metric("Nós no nível 1", n_steps,
                  help="Steps + gateways no nível principal do diagrama")
        c2.metric("callActivities", n_call_act,
                  help="Fases agrupadas pela regra de densidade Silver Level 1 (>10 atividades)")
        c3.metric("Loop / Multi-instance", n_loops,
                  help="Tarefas loopTask ou multiInstanceTask identificadas")
        if hub.bpmn.repair_log:
            st.caption(f"Reparos automáticos aplicados: {len(hub.bpmn.repair_log)}")
        _load_bpmn_versions.clear()
        _load_bpmn_procs.clear()
        st.rerun()
    else:
        st.error("Erro ao salvar a nova versão. Verifique a conexão com o banco de dados.")
from modules.bpmn_viewer import preview_from_xml
from modules.mermaid_renderer import render_mermaid_block

_STATUS_PROC_BADGE = {
    "active":   ("badge-active",    "Ativo"),
    "archived": ("badge-deprecated","Arquivado"),
}

with tab_bpmn:
    st.caption(
        "**BPMN 2.0 (Business Process Model and Notation)** é o padrão ISO/OMG para modelagem "
        "de processos de negócio. Os diagramas gerados mostram o fluxo de tarefas, decisões "
        "(gateways), raias por responsável (lanes) e eventos de início/fim — "
        "exportáveis como XML para ferramentas como Camunda, Bizagi ou Signavio."
    )
    if not bpmn_procs:
        if not bpmn_tables_exist():
            st.warning(
                "⚠️ Tabelas BPMN ainda não criadas. "
                "Execute `setup/supabase_schema_bpmn_processes.sql` no Supabase."
            )
        else:
            st.info(
                "Nenhum processo BPMN registrado para este projeto. "
                "Execute o pipeline com BPMN habilitado ou use o **📐 BPMN Backfill**."
            )
    else:
        # ── Reordena processos por número de reunião (ascendente) ─────────
        def _proc_meet_num(p):
            mid = p.get("first_meeting_id") or p.get("last_meeting_id")
            if mid and mid in meet_map:
                return meet_map[mid].get("meeting_number") or 9999
            return 9999

        bpmn_procs_sorted = sorted(bpmn_procs, key=_proc_meet_num)
        total_vers = sum(p.get("version_count") or 0 for p in bpmn_procs_sorted)

        st.caption(
            f"**{len(bpmn_procs_sorted)} processo(s)** · "
            f"**{total_vers} versão(ões)** no total."
        )

        # ── Tabela-resumo (colapsável) ────────────────────────────────────
        with st.expander("Ver lista de todos os processos", expanded=False):
            _tbl_rows = []
            for _i, _p in enumerate(bpmn_procs_sorted, 1):
                _mid = _p.get("first_meeting_id") or _p.get("last_meeting_id")
                _m   = meet_map.get(_mid or "", {})
                _mnum = _m.get("meeting_number", "—")
                _status_cls, _status_txt = _STATUS_PROC_BADGE.get(
                    _p.get("status", "active"), ("badge-active", "Ativo")
                )
                _tbl_rows.append(
                    f"<tr>"
                    f"<td style='padding:3px 8px;color:#64748b'>{_i}</td>"
                    f"<td style='padding:3px 8px;white-space:nowrap'>Reunião {_mnum}</td>"
                    f"<td style='padding:3px 8px'><b>{_p.get('name') or '—'}</b></td>"
                    f"<td style='padding:3px 8px'>{_p.get('version_count') or 0}</td>"
                    f"<td style='padding:3px 8px'>"
                    f"<span class='badge {_status_cls}'>{_status_txt}</span></td>"
                    f"</tr>"
                )
            st.markdown(
                "<table style='width:100%;font-size:0.83em;border-collapse:collapse'>"
                "<thead><tr style='border-bottom:1px solid #334155'>"
                "<th style='padding:3px 8px;color:#64748b'>#</th>"
                "<th align='left' style='padding:3px 8px'>Reunião</th>"
                "<th align='left' style='padding:3px 8px'>Processo</th>"
                "<th align='left' style='padding:3px 8px'>Versões</th>"
                "<th align='left' style='padding:3px 8px'>Status</th>"
                "</tr></thead><tbody>"
                + "".join(_tbl_rows)
                + "</tbody></table>",
                unsafe_allow_html=True,
            )

        st.markdown("")

        # ── Seletor por reunião (ordem numérica) ──────────────────────────
        _proc_sel_labels = []
        _proc_sel_map    = {}
        for _p in bpmn_procs_sorted:
            _mid  = _p.get("first_meeting_id") or _p.get("last_meeting_id")
            _m    = meet_map.get(_mid or "", {})
            _mnum = _m.get("meeting_number", "?")
            _mtit = _m.get("title", "") or _p.get("name") or ""
            _mdt  = _m.get("meeting_date", "") or ""
            _lbl  = f"Reunião {_mnum} — {_mtit}"
            if _mdt:
                _lbl += f"  ({_mdt})"
            # garante unicidade de label em caso de colisão
            if _lbl in _proc_sel_map:
                _lbl += f"  [{_p['id'][:6]}]"
            _proc_sel_labels.append(_lbl)
            _proc_sel_map[_lbl] = _p

        _sel_proc_lbl = st.selectbox(
            "Selecionar reunião",
            _proc_sel_labels,
            key="bpmn_proc_selector",
            help="Lista ordenada por número de reunião.",
        )
        sel_proc = _proc_sel_map[_sel_proc_lbl]
        pid      = sel_proc["id"]
        slug     = sel_proc.get("slug", "")

        _promote_widget("bpmn_process", pid, sel_proc.get("name") or _sel_proc_lbl)
        if render_artifact_feedback(
            project_id, "bpmn_process", pid, key_suffix=pid,
            meeting_id=sel_proc.get("first_meeting_id") or sel_proc.get("last_meeting_id"),
            created_by=st.session_state.get("_usuario_login", ""),
        ):
            st.rerun()

        st.markdown("---")

        # ── Versões do processo selecionado (1 query) ────────────────────
        versions = _load_bpmn_versions(pid)
        if not versions:
            st.info("Nenhuma versão registrada ainda para este processo.")
        else:
            ver_options = {}
            for v in versions:
                m_info = v.get("meetings") or {}
                m_num  = m_info.get("meeting_number", "?")
                m_tit  = m_info.get("title", "")
                m_dt   = m_info.get("meeting_date", "")
                lbl    = f"v{v['version']}  ·  Reunião {m_num} — {m_tit} ({m_dt})"
                if v.get("is_current"):
                    lbl = "⭐ " + lbl + "  (atual)"
                ver_options[lbl] = v

            sel_ver_lbl = st.selectbox(
                "Versão", list(ver_options.keys()), key=f"bpmn_ver_sel_{pid}"
            )
            sel_ver      = ver_options[sel_ver_lbl]
            bpmn_xml     = sel_ver.get("bpmn_xml") or ""
            mermaid_code = sel_ver.get("mermaid_code") or ""

            # ── Diagramas ────────────────────────────────────────────────
            if bpmn_xml or mermaid_code:
                sub_bpmn, sub_mermaid = st.tabs(["📐 BPMN 2.0", "📊 Mermaid"])
                with sub_bpmn:
                    if bpmn_xml:
                        st.download_button(
                            "⬇️ Download BPMN XML",
                            data=bpmn_xml.encode("utf-8"),
                            file_name=f"{slug}_v{sel_ver['version']}.bpmn",
                            mime="application/xml",
                            key=f"dl_bpmn_{pid}_{sel_ver['version']}",
                        )
                        _bpmn_show = st.toggle(
                            "Visualizar diagrama interativo",
                            key=f"bpmn_show_{pid}_{sel_ver['version']}",
                        )
                        # Slot único e estável: o toggle acima variava entre 0
                        # e 1 elemento aqui (e o elemento, quando presente, é
                        # um components.html() com a lib bpmn-js inteira
                        # embutida — payload grande) — mesma causa raiz do
                        # PC174/175 ("Bad 'setIn' index"), ver CLAUDE.md pitfalls.
                        with st.container():
                            if _bpmn_show:
                                try:
                                    bpmn_html = preview_from_xml(bpmn_xml)
                                    components.html(bpmn_html, height=700, scrolling=False)
                                except Exception as e:
                                    st.error(f"Erro ao renderizar BPMN: {e}")
                    else:
                        st.info("XML BPMN não disponível para esta versão.")
                with sub_mermaid:
                    if mermaid_code:
                        render_mermaid_block(
                            mermaid_code,
                            show_code=False,
                            key_suffix=f"rt_mmd_{pid}_{sel_ver['version']}",
                            height=500,
                        )
                    else:
                        st.info("Código Mermaid não disponível para esta versão.")
            else:
                st.info("Esta versão não possui diagrama armazenado. Use a reconversão abaixo para gerar um novo.")

            # ── Reconversão Method & Style v7.0 ──────────────────────────
            st.markdown("---")
            st.markdown("##### Reconverter com Method & Style v7.0")
            st.caption(
                "Re-executa o AgentBPMN aplicando a metodologia Top-Down de Bruce Silver "
                "(skill v7.0): regra de densidade, callActivity, Verbo+Objeto, boundary events. "
                "Salva como nova versão — a versão atual é preservada no histórico."
            )
            _reconv_mid = sel_ver.get("meeting_id")
            if _reconv_mid:
                st.caption(
                    f"Origem: {meet_label(_reconv_mid)}  "
                    f"·  versão selecionada: v{sel_ver['version']}"
                )
                if st.button(
                    "Reconverter este diagrama",
                    key=f"reconvert_{pid}_{sel_ver['version']}",
                    type="primary",
                    use_container_width=True,
                ):
                    _do_bpmn_reconvert(pid, _reconv_mid, project_id)
            else:
                st.warning("Reunião origem não identificada nesta versão.")

# ════════════════════════════════════════════════════════════════════════════
# TAB 8 — DMN
# ════════════════════════════════════════════════════════════════════════════
with tab_dmn:
    st.caption(
        "**DMN (Decision Model and Notation)** é o padrão OMG para formalizar decisões de negócio "
        "como tabelas de regras (decision tables). Cada tabela define as entradas (condições), "
        "as saídas (ações/resultados) e a política de acerto (UNIQUE, ANY, FIRST…), "
        "tornando as regras auditáveis, testáveis e integráveis a motores de regras como Drools."
    )
    # Carregamento sob demanda: só busca do Supabase se ainda não foi feito nesta sessão
    if _DMN_SS not in st.session_state:
        with st.spinner("Buscando decisões DMN..."):
            st.session_state[_DMN_SS] = _load_dmn(project_id)
        st.rerun()  # re-renderiza para atualizar contador no cabeçalho e métricas
    dmn_decisions = st.session_state[_DMN_SS]  # agora é lista (pode ser [])

    if st.button("🔄 Atualizar DMN", key="art_dmn_refresh"):
        st.session_state.pop(_DMN_SS, None)
        _load_dmn.clear()
        st.rerun()

    if not dmn_decisions:
        st.info("Nenhuma tabela de decisão DMN registrada. Execute o pipeline com o agente DMN habilitado.")
        # ── Diagnóstico temporário ────────────────────────────────────────────
        with st.expander("🔍 Diagnóstico DMN (temporário)", expanded=False):
            try:
                from modules.supabase_client import get_supabase_client as _sc
                _db_diag = _sc()
                if _db_diag:
                    _rows = _db_diag.table("meetings").select(
                        "id, meeting_number, dmn_json"
                    ).eq("project_id", project_id).execute().data or []
                    st.write(f"**Rows retornadas:** {len(_rows)}")
                    for _r in _rows[:3]:
                        _raw = _r.get("dmn_json") or ""
                        st.write(f"Reunião #{_r.get('meeting_number')} — `dmn_json` len={len(_raw)} — preview: `{_raw[:120]}`")
                else:
                    st.warning("Supabase não conectado.")
            except Exception as _exc:
                st.error(f"Erro no diagnóstico: {_exc}")
    else:
        st.caption(
            f"**{len(dmn_decisions)} decisão(ões)** extraídas de {len({d['_meeting_id'] for d in dmn_decisions})} reunião(ões). "
            "Cada decisão representa uma tabela de regras DMN 1.4."
        )

        # Filtro por reunião
        meet_ids_dmn = sorted({d["_meeting_id"] for d in dmn_decisions})
        meet_labels_dmn = {"Todas as reuniões": None}
        for mid in meet_ids_dmn:
            meet_labels_dmn[meet_label(mid)] = mid
        sel_meet_dmn = st.selectbox("Filtrar por reunião", list(meet_labels_dmn.keys()), key="dmn_meet_filter")
        filtered_dmn = dmn_decisions if not meet_labels_dmn[sel_meet_dmn] else [
            d for d in dmn_decisions if d["_meeting_id"] == meet_labels_dmn[sel_meet_dmn]
        ]

        _dmn_sub_tables, _dmn_sub_drd = st.tabs(["📋 Tabelas de Decisão", "🔗 DRD"])

        with _dmn_sub_tables:
            from modules.dmn_viewer import render_dmn_page, estimate_height
            page_html = render_dmn_page(filtered_dmn, show_origin=True)
            h = estimate_height(filtered_dmn)
            components.html(page_html, height=h, scrolling=True)

        with _dmn_sub_drd:
            st.caption(
                "**DRD — Diagrama de Requisitos de Decisão**: mostra como o resultado "
                "de uma decisão alimenta a entrada de outra. "
                "Dependências detectadas automaticamente por correspondência de labels."
            )
            from modules.dmn_viewer import render_drd, estimate_drd_height
            drd_html = render_drd(filtered_dmn)
            components.html(drd_html, height=estimate_drd_height(filtered_dmn), scrolling=False)

        # ── Export buttons ────────────────────────────────────────────────────
        import json as _json_dmn
        _ecol1, _ecol2 = st.columns(2)

        # JSON export
        _dmn_export_data = {"decisions": [
            {k: v for k, v in d.items() if not k.startswith("_")}
            for d in filtered_dmn
        ]}
        _ecol1.download_button(
            "⬇️ Exportar JSON",
            data=_json_dmn.dumps(_dmn_export_data, ensure_ascii=False, indent=2),
            file_name=f"dmn_{sel_meet_dmn.replace(' ', '_') if meet_labels_dmn[sel_meet_dmn] else 'projeto'}.json",
            mime="application/json",
            key="art_dmn_json",
        )

        # XML export (converts dicts → DMNModel → XML)
        try:
            from modules.dmn_viewer import dmn_to_xml
            from core.knowledge_hub import DMNModel, DMNDecision, DMNInput, DMNOutput, DMNRule
            _decisions_dc = []
            for _d in filtered_dmn:
                _decisions_dc.append(DMNDecision(
                    id=_d.get("id", "D?"),
                    name=_d.get("name", ""),
                    question=_d.get("question", ""),
                    rationale=_d.get("rationale", ""),
                    decided_by=_d.get("decided_by") or [],
                    hit_policy=_d.get("hit_policy", "U"),
                    confidence=float(_d.get("confidence") or 1.0),
                    inputs=[DMNInput(label=i.get("label",""), expression=i.get("expression",""))
                            for i in (_d.get("inputs") or [])],
                    outputs=[DMNOutput(label=o.get("label",""), value=o.get("value",""))
                             for o in (_d.get("outputs") or [])],
                    rules=[DMNRule(inputs=r.get("inputs") or [], output=r.get("output",""),
                                  annotation=r.get("annotation",""))
                           for r in (_d.get("rules") or [])],
                ))
            _dmn_model_export = DMNModel(decisions=_decisions_dc, ready=True)
            _ecol2.download_button(
                "⬇️ Exportar XML (DMN 1.4)",
                data=dmn_to_xml(_dmn_model_export).encode("utf-8"),
                file_name=f"dmn_{sel_meet_dmn.replace(' ', '_') if meet_labels_dmn[sel_meet_dmn] else 'projeto'}.dmn",
                mime="application/xml",
                key="art_dmn_xml",
            )
        except Exception:
            pass

