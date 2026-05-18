# pages/KnowledgeHub.py
# ─────────────────────────────────────────────────────────────────────────────
# Knowledge Hub — visualização do conhecimento persistente acumulado
# por projeto: entidades, processos, fatos e contradições.
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
from ui.components.page_header import render_page_header
from modules.supabase_client import supabase_configured

apply_auth_gate()

render_page_header("🧠", "Knowledge Hub", "Conhecimento acumulado cross-session por projeto")

if not supabase_configured():
    st.warning("⚙️ Supabase não configurado.")
    st.stop()

project_id, project_name = require_active_project()

# ── Check tables exist ────────────────────────────────────────────────────────
from core.knowledge_store import kh_tables_exist

if not kh_tables_exist():
    st.error(
        "As tabelas do Knowledge Hub ainda não foram criadas no Supabase. "
        "Execute o script `setup/supabase_schema_knowledge_hub.sql` no SQL Editor do Supabase."
    )
    with st.expander("Ver instruções"):
        st.markdown("""
1. Acesse o **Supabase Dashboard → SQL Editor**
2. Clique em **New query**
3. Cole o conteúdo de `setup/supabase_schema_knowledge_hub.sql`
4. Clique em **Run**
5. Recarregue esta página
        """)
    st.stop()

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_entities, tab_processes, tab_facts, tab_contradictions, tab_analyses = st.tabs([
    "👥 Entidades",
    "⚙️ Processos",
    "📌 Fatos",
    "⚠️ Contradições",
    "📜 Análises Anteriores",
])

# ── Tab: Entidades ────────────────────────────────────────────────────────────
with tab_entities:
    from core.knowledge_store import get_entities

    st.markdown(
        "Entidades organizacionais (pessoas, times, sistemas, departamentos) "
        "identificadas automaticamente nas reuniões do projeto."
    )

    _type_filter = st.selectbox(
        "Filtrar por tipo",
        ["Todos", "person", "team", "system", "department", "process", "other"],
        key="kh_entity_type",
    )
    etype = None if _type_filter == "Todos" else _type_filter
    entities = get_entities(project_id, entity_type=etype, limit=200)

    # ── Consolidação de duplicatas (admin) ────────────────────────────────────
    from modules.auth import is_admin
    if is_admin():
        with st.expander("🔁 Consolidar Entidades Duplicadas"):
            st.caption(
                "O extrator pode criar variações do mesmo objeto (ex: 'SDEA' e 'Portal SDEA'). "
                "Este agente usa LLM para identificar e fundir duplicatas, "
                "somando ocorrências e unindo aliases."
            )
            from modules.session_security import get_session_llm_client
            from modules.config import AVAILABLE_PROVIDERS
            _cons_provider = st.session_state.get("selected_provider", "")
            _cons_client   = get_session_llm_client(_cons_provider) if _cons_provider else None
            _prov_cfg      = AVAILABLE_PROVIDERS.get(_cons_provider, {})
            if not _cons_client:
                st.warning("Configure e salve uma API key na sidebar antes de consolidar.")
            elif st.button("🔁 Consolidar agora", key="kh_consolidate_btn", use_container_width=False):
                with st.spinner("Analisando duplicatas com LLM…"):
                    from agents.agent_entity_consolidator import AgentEntityConsolidator
                    _agent = AgentEntityConsolidator(
                        {"api_key": _cons_client["api_key"]}, _prov_cfg
                    )
                    _stats = _agent.consolidate(project_id)
                    if _stats.get("error"):
                        st.error(f"Erro: {_stats['error']}")
                    elif _stats["merges_done"] == 0:
                        st.success("Nenhuma duplicata detectada — base já está consolidada.")
                    else:
                        st.success(
                            f"Consolidação concluída: **{_stats['merges_done']}** grupo(s) fundido(s), "
                            f"**{_stats['entities_removed']}** entidade(s) removida(s)."
                        )
                        st.rerun()

    if not entities:
        st.info("Nenhuma entidade encontrada. Execute o pipeline em uma reunião para popular o Knowledge Hub.")
    else:
        st.caption(f"{len(entities)} entidade(s) encontrada(s)")

        _TYPE_COLORS = {
            "person":     "#1A4B8C",
            "team":       "#1A7F5A",
            "system":     "#6B3FA0",
            "department": "#C97B1A",
            "process":    "#0B1E3D",
            "other":      "#8496B0",
        }

        for ent in entities:
            etype_label = ent.get("entity_type", "other")
            color = _TYPE_COLORS.get(etype_label, "#8496B0")
            aliases = ent.get("aliases") or []
            alias_str = ", ".join(aliases[:5]) if aliases else "—"
            count = ent.get("occurrence_count", 1)

            col_badge, col_name, col_aliases, col_count = st.columns([1.2, 3, 4, 1])
            col_badge.markdown(
                f'<span style="display:inline-block;background:{color};color:white;'
                f'padding:2px 10px;border-radius:4px;font-size:12px;font-weight:600;">'
                f'{etype_label}</span>',
                unsafe_allow_html=True,
            )
            col_name.markdown(f"**{ent['canonical_name']}**")
            col_aliases.caption(alias_str)
            col_count.metric("", f"{count}x", label_visibility="collapsed")


# ── Tab: Processos ────────────────────────────────────────────────────────────
with tab_processes:
    from core.knowledge_store import get_processes

    st.markdown("Processos de negócio identificados e rastreados ao longo das reuniões.")

    _status_filter = st.selectbox(
        "Filtrar por status",
        ["Todos", "active", "deprecated", "merged"],
        key="kh_proc_status",
    )
    pstatus = None if _status_filter == "Todos" else _status_filter
    processes = get_processes(project_id, status=pstatus)

    if not processes:
        st.info("Nenhum processo identificado ainda.")
    else:
        st.caption(f"{len(processes)} processo(s)")
        for proc in processes:
            with st.container():
                col_name, col_vers, col_status = st.columns([5, 1, 1])
                col_name.markdown(f"**{proc['process_name']}**")
                col_vers.metric("Versões", proc.get("version_count", 1), label_visibility="visible")
                _s = proc.get("status", "active")
                _s_color = {"active": "🟢", "deprecated": "🔴", "merged": "🟡"}.get(_s, "⚪")
                col_status.markdown(f"{_s_color} {_s}")
                if proc.get("description"):
                    st.caption(proc["description"])
                st.divider()


# ── Tab: Fatos ────────────────────────────────────────────────────────────────
with tab_facts:
    from core.knowledge_store import get_facts

    st.markdown(
        "Fatos, regras e decisões consolidados extraídos das reuniões. "
        "Formam a memória de longo prazo do projeto."
    )

    col_f1, col_f2 = st.columns(2)
    _fact_type = col_f1.selectbox(
        "Tipo",
        ["Todos", "rule", "decision", "constraint", "nomenclature", "insight"],
        key="kh_fact_type",
    )
    _active_only = col_f2.checkbox("Apenas ativos", value=True, key="kh_fact_active")

    ftype = None if _fact_type == "Todos" else _fact_type
    facts = get_facts(project_id, fact_type=ftype, active_only=_active_only, limit=100)

    _FACT_ICONS = {
        "rule":         "📏",
        "decision":     "✅",
        "constraint":   "🚧",
        "nomenclature": "🏷️",
        "insight":      "💡",
    }
    _FACT_COLORS = {
        "rule":         "#1A4B8C",
        "decision":     "#1A7F5A",
        "constraint":   "#C97B1A",
        "nomenclature": "#6B3FA0",
        "insight":      "#0B1E3D",
    }

    if not facts:
        st.info("Nenhum fato encontrado com os filtros selecionados.")
    else:
        st.caption(f"{len(facts)} fato(s)")
        for fact in facts:
            ftype_label = fact.get("fact_type", "decision")
            icon  = _FACT_ICONS.get(ftype_label, "📌")
            color = _FACT_COLORS.get(ftype_label, "#8496B0")
            conf  = fact.get("confidence", 1.0)
            conf_str = f" · confiança {conf:.0%}" if conf < 0.9 else ""

            st.markdown(
                f'<div style="border-left:3px solid {color};padding:6px 12px;'
                f'margin-bottom:8px;border-radius:0 6px 6px 0;">'
                f'<span style="background:{color};color:white;padding:1px 8px;'
                f'border-radius:3px;font-size:11px;font-weight:600;">'
                f'{icon} {ftype_label}</span>'
                f'<span style="font-size:11px;color:#888;">{conf_str}</span><br>'
                f'<span style="font-size:14px;">{fact["content"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ── Tab: Contradições ─────────────────────────────────────────────────────────
with tab_contradictions:
    from core.knowledge_store import get_contradictions, resolve_contradiction
    from modules.auth import is_admin

    st.markdown(
        "Contradições detectadas automaticamente entre versões de processos ou decisões. "
        "Revise e marque como resolvidas ou falso positivo."
    )

    col_cs1, col_cs2 = st.columns(2)
    _contra_status = col_cs1.selectbox(
        "Status",
        ["open", "resolved", "false_positive", "Todos"],
        key="kh_contra_status",
    )
    _relation_filter = col_cs2.selectbox(
        "Tipo de relação",
        ["Todos", "contradiction_direct", "contradiction_conditional",
         "contradiction_temporal", "contradiction_responsibility",
         "exception", "superseded", "ambiguous"],
        key="kh_contra_relation",
    )
    cstatus = None if _contra_status == "Todos" else _contra_status
    contradictions = get_contradictions(project_id, status=cstatus, limit=100)

    # Client-side relation filter
    if _relation_filter != "Todos":
        contradictions = [c for c in contradictions
                          if c.get("relation_type") == _relation_filter]

    _SEV_COLORS = {
        "low":      "#1A7F5A",
        "medium":   "#C97B1A",
        "high":     "#d97706",
        "critical": "#dc2626",
    }

    _RELATION_LABELS = {
        "contradiction_direct":         ("🔴", "Contradição Direta"),
        "contradiction_conditional":    ("🟠", "Contradição Condicional"),
        "contradiction_temporal":       ("🟡", "Contradição Temporal"),
        "contradiction_responsibility": ("🔴", "Conflito de Responsabilidade"),
        "exception":                    ("🔵", "Exceção não formalizada"),
        "superseded":                   ("⚪", "Decisão substituída"),
        "ambiguous":                    ("🟣", "Ambígua"),
    }

    # ── Full Scan (admin only) ────────────────────────────────────────────────
    if is_admin():
        with st.expander("🔍 Reprocessar Contradições (Full Scan)", expanded=False):
            st.caption(
                "Analisa todos os fatos do projeto com o agente LLM e insere novas contradições detectadas. "
                "Use após importar novas reuniões ou para atualizar descrições existentes."
            )
            from modules.session_security import get_session_llm_client
            from modules.config import AVAILABLE_PROVIDERS
            _scan_provider = st.session_state.get("selected_provider", "")
            _scan_client   = get_session_llm_client(_scan_provider) if _scan_provider else None
            if not _scan_client:
                st.warning("Configure e salve uma API key na sidebar antes de executar o Full Scan.")
            else:
                if st.button("▶️ Executar Full Scan", key="kh_full_scan_btn", type="primary"):
                    _provider_cfg = AVAILABLE_PROVIDERS.get(_scan_provider, {})
                    from agents.agent_contradiction_detector import AgentContradictionDetector
                    with st.spinner("Analisando fatos do projeto… pode levar alguns segundos."):
                        try:
                            _agent = AgentContradictionDetector(
                                {"api_key": _scan_client["api_key"]},
                                _provider_cfg,
                            )
                            _n = _agent.run_full_scan(project_id)
                            st.session_state["_contra_msg"] = (
                                "success",
                                f"Full Scan concluído — {_n} nova(s) contradição(ões) inserida(s).",
                            )
                        except Exception as _e:
                            st.session_state["_contra_msg"] = ("error", f"Erro no Full Scan: {_e}")
                    st.rerun()

    if "_contra_msg" in st.session_state:
        level, text = st.session_state.pop("_contra_msg")
        (st.success if level == "success" else st.error)(text)

    if not contradictions:
        if _contra_status == "open":
            st.success("✅ Nenhuma contradição aberta detectada.")
        else:
            st.info("Nenhuma contradição encontrada com os filtros selecionados.")
    else:
        st.caption(f"{len(contradictions)} item(ns)")
        for c in contradictions:
            sev          = c.get("severity", "medium")
            color        = _SEV_COLORS.get(sev, "#8496B0")
            status       = c.get("status", "open")
            rel_type     = c.get("relation_type") or ""
            rel_icon, rel_label = _RELATION_LABELS.get(rel_type, ("⚪", rel_type or "—"))
            confidence   = c.get("confidence")
            conf_str     = f" · {confidence:.0%}" if confidence is not None else ""

            with st.container():
                col_sev, col_desc, col_actions = st.columns([1.4, 5.6, 2])

                # Severity + relation badges
                col_sev.markdown(
                    f'<span style="background:{color};color:white;padding:2px 8px;'
                    f'border-radius:4px;font-size:11px;font-weight:600;">{sev}</span>',
                    unsafe_allow_html=True,
                )
                if rel_type:
                    col_sev.caption(f"{rel_icon} {rel_label}{conf_str}")

                # Description
                if c.get("process_name"):
                    col_desc.markdown(f"**{c['process_name']}** — {c['description']}")
                else:
                    col_desc.markdown(c["description"])

                # Clarifying question + suggested rewrite in expander
                has_extra = c.get("clarifying_question") or c.get("suggested_rewrite")
                if has_extra:
                    with col_desc:
                        with st.expander("Ver análise detalhada"):
                            if c.get("clarifying_question"):
                                st.markdown(f"**❓ Pergunta para esclarecimento**")
                                st.info(c["clarifying_question"])
                            if c.get("suggested_rewrite"):
                                st.markdown(f"**✏️ Reescrita sugerida**")
                                st.success(c["suggested_rewrite"])

                # Actions
                if status == "open" and is_admin():
                    with col_actions:
                        btn_res, btn_fp = st.columns(2)
                        if btn_res.button("✅", key=f"res_{c['id']}", help="Marcar como resolvida"):
                            user = st.session_state.get("_usuario_login", "admin")
                            ok = resolve_contradiction(c["id"], user, "Resolvida via KnowledgeHub", "resolved")
                            st.session_state["_contra_msg"] = (
                                ("success", "Contradição marcada como resolvida.")
                                if ok else ("error", "Erro ao resolver.")
                            )
                            st.rerun()
                        if btn_fp.button("🚫", key=f"fp_{c['id']}", help="Falso positivo"):
                            user = st.session_state.get("_usuario_login", "admin")
                            ok = resolve_contradiction(c["id"], user, "Falso positivo", "false_positive")
                            st.session_state["_contra_msg"] = (
                                ("success", "Marcada como falso positivo.")
                                if ok else ("error", "Erro.")
                            )
                            st.rerun()
                elif status != "open":
                    col_actions.caption(f"_{status}_")
                    if c.get("resolution_note"):
                        col_actions.caption(c["resolution_note"][:60])

                st.divider()


# ── Tab: Análises Anteriores ───────────────────────────────────────────────────
with tab_analyses:
    from core.analyst_store import get_analyses, get_analysis, analyses_table_exists

    st.markdown(
        "Análises autônomas geradas pelo AgentAnalyst (modo 🔬 Análise Autônoma no Assistente). "
        "Salvas permanentemente para reuso sem re-executar o LLM."
    )

    if not analyses_table_exists():
        st.warning(
            "Tabela `kh_analyses` não encontrada. "
            "Execute `setup/supabase_migration_kh_analyses.sql` no Supabase Dashboard."
        )
    else:
        _show_failed = st.checkbox("Incluir análises com erro", value=False, key="kh_anal_show_failed")
        analyses_list = get_analyses(project_id, limit=30, success_only=not _show_failed)

        if not analyses_list:
            st.info(
                "Nenhuma análise salva para este projeto. "
                "Execute uma análise no modo 🔬 e clique em '💾 Salvar análise'."
            )
        else:
            st.caption(f"{len(analyses_list)} análise(s) encontrada(s)")

            for anal in analyses_list:
                _aid       = anal["id"]
                _obj       = (anal.get("objective") or "—")[:120]
                _steps     = anal.get("step_count", 0)
                _dur       = anal.get("duration_s") or 0
                _created   = (anal.get("created_at") or "")[:10]
                _by        = anal.get("created_by") or "—"
                _ok_flag   = anal.get("success", True)
                _status_icon = "✅" if _ok_flag else "❌"

                with st.expander(f"{_status_icon} {_obj}", expanded=False):
                    col_meta, col_btn = st.columns([5, 2])
                    col_meta.caption(
                        f"Data: **{_created}** · Usuário: **{_by}** · "
                        f"Passos: **{_steps}** · Tempo: **{_dur:.1f}s**"
                    )
                    if col_btn.button("↩️ Reabrir", key=f"kh_anal_open_{_aid}"):
                        st.session_state["_kh_anal_detail"] = _aid
                        st.rerun()

            # ── Detail view ───────────────────────────────────────────────────
            if "_kh_anal_detail" in st.session_state:
                detail_id = st.session_state["_kh_anal_detail"]
                detail    = get_analysis(detail_id)

                if detail:
                    st.markdown("---")
                    st.markdown(f"**Objetivo:** {detail.get('objective', '—')}")
                    conclusion = detail.get("conclusion") or ""
                    if conclusion:
                        st.markdown("#### Conclusão")
                        st.markdown(conclusion)

                    tables = detail.get("tables_json") or []
                    if tables:
                        st.markdown("#### Tabelas")
                        for tbl in tables:
                            cols = tbl.get("columns", [])
                            rows = tbl.get("rows", [])
                            if cols and rows:
                                import pandas as pd
                                df = pd.DataFrame(rows, columns=cols)
                                st.markdown(f"**{tbl.get('title', 'Tabela')}**")
                                st.dataframe(df, use_container_width=True)

                    steps = detail.get("steps_json") or []
                    if steps:
                        with st.expander(
                            f"🧠 Cadeia de raciocínio ({len(steps)} passos)", expanded=False
                        ):
                            for i, s in enumerate(steps, 1):
                                icon = {"action": "🛠️", "conclusion": "✅", "error": "❌"}.get(
                                    s.get("type", ""), "🔍"
                                )
                                st.markdown(f"**{icon} Passo {i} — {s.get('label', '')}**")
                                if s.get("content"):
                                    st.markdown(s["content"])
                                if s.get("observation"):
                                    st.caption(f"Observação: {s['observation'][:400]}")
                                st.divider()

                    if st.button("✖️ Fechar", key="kh_anal_close"):
                        st.session_state.pop("_kh_anal_detail", None)
                        st.rerun()
                else:
                    st.error("Análise não encontrada.")
                    st.session_state.pop("_kh_anal_detail", None)
