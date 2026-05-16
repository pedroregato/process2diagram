# pages/Pipeline.py
# ─────────────────────────────────────────────────────────────────────────────
# Pipeline Principal — Processar Transcrição / Carregar Reunião Existente
# Conteúdo movido de app.py na reestruturação de navegação (v4.12).
# Modo "Reunião existente" adicionado em v4.13.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from ui.auth_gate import apply_auth_gate
from ui.sidebar import render_sidebar
from ui.input_area import render_input_area
from ui.project_selector import render_project_selector, render_bpmn_process_selector
from core.pipeline import run_pipeline
from core.rerun_handlers import handle_rerun
from core.project_store import (
    create_meeting, save_transcript, save_meeting_artifacts,
    save_sbvr_from_hub, save_bpmn_from_hub,
    list_contexts as list_projects, list_meetings, load_meeting_as_hub,
)
from agents.agent_req_reconciler import AgentReqReconciler
from modules.supabase_client import supabase_configured
from ui.tabs import (
    render_quality, render_bpmn, render_mermaid, render_validation,
    render_minutes, render_requirements, render_sbvr, render_bmm,
    render_synthesizer, render_export, render_dev_tools,
    render_dmn, render_argumentation,
)
from modules.session_security import get_session_llm_client

apply_auth_gate()

# Sidebar (específica do pipeline)
render_sidebar()

# ── Cabeçalho ─────────────────────────────────────────────────────────────────
from ui.components.page_header import render_page_header
render_page_header(
    "🚀", "Processar Transcrição",
    "Cole ou faça upload de uma transcrição e execute o pipeline de agentes LLM.",
)

# ─────────────────────────────────────────────────────────────────────────────
# MODO: Nova transcrição vs. Reunião existente
# ─────────────────────────────────────────────────────────────────────────────
_db_available = supabase_configured()

_MODE_NEW = "🆕 Nova transcrição"
_MODE_LOAD = "📂 Reunião existente"

if _db_available:
    pipeline_mode = st.radio(
        "Modo de operação",
        [_MODE_NEW, _MODE_LOAD],
        horizontal=True,
        key="pipeline_mode_radio",
    )
else:
    pipeline_mode = _MODE_NEW

# Clear hub when the user switches modes so stale results don't bleed through
_prev_mode = st.session_state.get("_last_pipeline_mode")
if _prev_mode and _prev_mode != pipeline_mode:
    st.session_state.pop("hub", None)
    st.session_state.pop("_loaded_meeting_id", None)
    st.session_state.pop("_loaded_project_id", None)
st.session_state["_last_pipeline_mode"] = pipeline_mode

# ─────────────────────────────────────────────────────────────────────────────
# MODO A — NOVA TRANSCRIÇÃO
# ─────────────────────────────────────────────────────────────────────────────
if pipeline_mode == _MODE_NEW:

    # ── Contexto / Reunião ────────────────────────────────────────────────────
    render_project_selector()
    render_bpmn_process_selector()

    # Área de entrada e curadoria
    start_process = render_input_area()

    # Verificação de API key
    if not get_session_llm_client(st.session_state.selected_provider):
        st.warning("👈 Insira sua API key na sidebar para continuar.")
        st.stop()

    # ── Pipeline principal ────────────────────────────────────────────────────
    if start_process and st.session_state.transcript_text.strip():
        if not any([st.session_state.run_quality, st.session_state.run_bpmn,
                    st.session_state.run_minutes, st.session_state.run_requirements,
                    st.session_state.run_synthesizer]):
            st.warning("Selecione ao menos um agente na sidebar.")
            st.stop()

        client_info = get_session_llm_client(st.session_state.selected_provider)
        if not client_info:
            st.error("API key ausente.")
            st.stop()

        from core.knowledge_hub import KnowledgeHub
        hub = KnowledgeHub.new()
        hub.set_transcript(st.session_state.transcript_text)
        if st.session_state.get("curated_clean") and st.session_state.curated_clean != st.session_state.transcript_text:
            hub.transcript_clean = st.session_state.curated_clean
        hub.meta.llm_provider = st.session_state.selected_provider

        # Load Context Knowledge File (CKF) and reference files from active context
        _ctx_id = st.session_state.get("active_project_id") or st.session_state.get("project_id")
        if _ctx_id:
            try:
                from core.project_store import get_context_skill, get_context_files_text
                _ckf = get_context_skill(_ctx_id)
                if _ckf:
                    hub.context_skill = _ckf
                _ctx_files_text = get_context_files_text(_ctx_id)
                if _ctx_files_text:
                    hub.context_files_text = _ctx_files_text
            except Exception:
                pass

        # Derive project slug from prefix (e.g. "SDEA_" → "sdea")
        _ata_slug = st.session_state.get("prefix", "p2d_").rstrip("_").lower() or "p2d"

        config = {
            "client_info": client_info,
            "provider_cfg": st.session_state.provider_cfg,
            "output_language": st.session_state.output_language,
            "run_quality": st.session_state.run_quality,
            "run_bpmn": st.session_state.run_bpmn,
            "run_minutes": st.session_state.run_minutes,
            "run_requirements": st.session_state.run_requirements,
            "run_sbvr": st.session_state.run_sbvr,
            "run_dmn": st.session_state.get("run_dmn", False),
            "run_argumentation": st.session_state.get("run_argumentation", False),
            "run_bmm": st.session_state.run_bmm,
            "run_synthesizer": st.session_state.run_synthesizer,
            "n_bpmn_runs": st.session_state.n_bpmn_runs,
            "bpmn_weights": st.session_state.bpmn_weights,
            "use_langgraph": st.session_state.use_langgraph,
            "validation_threshold": st.session_state.validation_threshold,
            "max_bpmn_retries": st.session_state.max_bpmn_retries,
            # ATA Engine context — meeting_id left empty until Supabase creates the record
            "project_id":         st.session_state.get("project_id", ""),
            "active_project_id":  st.session_state.get("active_project_id", ""),
            "project_slug":       _ata_slug,
            "meeting_location":   "Videoconferência",
            "run_ckf_updater":    st.session_state.run_ckf_updater,
        }

        with st.status("⏳ Executando pipeline de agentes...", expanded=True) as _pipeline_status:
            def update_progress(step, status):
                icon = "✅" if "done" in status else "⏳" if "running" in status else "❌"
                st.write(f"{icon} **{step}** — {status}")
            try:
                hub = run_pipeline(hub, config, update_progress)
                st.session_state.hub = hub
                _pipeline_status.update(
                    label=f"✅ Pipeline concluído · {hub.meta.total_tokens_used:,} tokens usados",
                    state="complete",
                    expanded=False,
                )
            except Exception as e:
                _pipeline_status.update(label="❌ Erro no pipeline", state="error", expanded=True)
                st.error(f"Erro no pipeline: {e}")
                st.stop()

        # ── Persistência no Supabase + reconciliação de requisitos ───────────
        if supabase_configured() and st.session_state.get("project_confirmed"):
            try:
                meeting = create_meeting(
                    project_id=st.session_state.project_id,
                    title=st.session_state.meeting_title,
                    meeting_date=st.session_state.meeting_date,
                )
                if meeting:
                    meeting_id = meeting["id"]
                    st.session_state.current_meeting_id = meeting_id
                    save_transcript(meeting_id, hub)
                    save_meeting_artifacts(meeting_id, hub)

                    # Regenerate ATA HTML with actual meeting_id so the roster
                    # matching and participant persistence work correctly
                    if hub.minutes.ready:
                        try:
                            from modules.ata_engine_generator import generate_ata_html
                            from datetime import date as _d
                            _mtg_date = st.session_state.get("meeting_date") or _d.today()
                            if isinstance(_mtg_date, str):
                                from datetime import date as _date
                                try:
                                    _mtg_date = _date.fromisoformat(_mtg_date)
                                except ValueError:
                                    _mtg_date = _d.today()
                            hub.minutes.ata_html = generate_ata_html(
                                minutes      = hub.minutes,
                                project_id   = st.session_state.get("project_id", ""),
                                meeting_id   = meeting_id,
                                project_slug = _ata_slug,
                                meeting_date = _mtg_date,
                                local        = "Videoconferência",
                            )
                            st.session_state.hub = hub
                        except Exception:
                            pass  # non-fatal — first-pass ATA HTML still available

                    if hub.sbvr.ready:
                        save_sbvr_from_hub(meeting_id, st.session_state.project_id, hub)

                    if hub.bpmn.ready:
                        save_bpmn_from_hub(
                            meeting_id=meeting_id,
                            project_id=st.session_state.project_id,
                            hub=hub,
                            bpmn_process_id=st.session_state.get("bpmn_process_id"),
                            bpmn_process_override_name=st.session_state.get(
                                "bpmn_process_override_name", ""
                            ),
                        )

                    with st.spinner("🔍 Reconciliando requisitos com histórico do projeto..."):
                        reconciler = AgentReqReconciler(client_info, st.session_state.provider_cfg)
                        counts = reconciler.run(
                            hub,
                            project_id=st.session_state.project_id,
                            meeting_id=meeting_id,
                        )
                    total = sum(counts.values())
                    parts = []
                    if counts.get("new"):
                        parts.append(f"{counts['new']} novo(s)")
                    if counts.get("revised"):
                        parts.append(f"{counts['revised']} revisado(s)")
                    if counts.get("contradicted"):
                        parts.append(f"⚠️ {counts['contradicted']} contradição(ões)")
                    if counts.get("confirmed"):
                        parts.append(f"{counts['confirmed']} confirmado(s)")
                    summary = " · ".join(parts) if parts else f"{total} requisito(s)"
                    st.toast(f"💾 Reunião salva · {summary}", icon="✅")
            except Exception as e:
                st.warning(f"⚠️ Erro ao salvar no Supabase: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# MODO B — REUNIÃO EXISTENTE
# ─────────────────────────────────────────────────────────────────────────────
else:
    st.markdown("### Carregar reunião processada")

    projects = list_projects()
    if not projects:
        st.info("Nenhum contexto encontrado no banco de dados.")
        st.stop()

    # Context selector
    proj_options = {p["name"]: p["id"] for p in projects}
    selected_proj_name = st.selectbox(
        "Contexto",
        list(proj_options.keys()),
        key="load_proj_select",
    )
    selected_proj_id = proj_options[selected_proj_name]

    # Meeting selector
    meetings = list_meetings(selected_proj_id)
    if not meetings:
        st.info("Nenhuma reunião encontrada para este contexto.")
        st.stop()

    def _fmt_meeting(m: dict) -> str:
        date = (m.get("meeting_date") or "")[:10]
        title = m.get("title") or m.get("id", "")[:8]
        return f"{date}  {title}" if date else title

    meet_labels = [_fmt_meeting(m) for m in meetings]
    meet_ids    = [m["id"] for m in meetings]

    selected_meet_label = st.selectbox(
        "Reunião",
        meet_labels,
        key="load_meet_select",
    )
    selected_meet_id = meet_ids[meet_labels.index(selected_meet_label)]

    col_load, col_gap = st.columns([1, 4])
    load_clicked = col_load.button("📂 Carregar", type="primary", key="btn_load_meeting")

    if load_clicked:
        with st.spinner("Carregando artefatos da reunião..."):
            loaded_hub = load_meeting_as_hub(selected_meet_id, selected_proj_id)
        if loaded_hub is None:
            st.error("Falha ao carregar a reunião. Verifique o banco de dados.")
            st.stop()
        st.session_state.hub = loaded_hub
        st.session_state["_loaded_meeting_id"] = selected_meet_id
        st.session_state["_loaded_project_id"] = selected_proj_id
        st.rerun()

    # Info banner for currently loaded meeting
    _loaded_id = st.session_state.get("_loaded_meeting_id")
    if _loaded_id and _loaded_id == selected_meet_id and "hub" in st.session_state:
        _lhub = st.session_state.hub
        _meeting_obj = next((m for m in meetings if m["id"] == _loaded_id), None)
        _title = (_meeting_obj or {}).get("title", "—")
        _date  = ((_meeting_obj or {}).get("meeting_date") or "")[:10]
        _prov  = getattr(getattr(_lhub, "meta", None), "llm_provider", "") or "—"
        _tok   = getattr(getattr(_lhub, "meta", None), "total_tokens_used", 0) or 0
        st.success(
            f"**{_title}** · {_date}  |  provedor: `{_prov}`  |  tokens originais: {_tok:,}"
        )

    # Save-back button (shown after re-run when hub is from DB)
    if "hub" in st.session_state and st.session_state.hub.loaded_from_db:
        _lhub = st.session_state.hub
        _mid  = st.session_state.get("_loaded_meeting_id")
        _pid  = st.session_state.get("_loaded_project_id")
        if _mid and _pid:
            st.markdown("---")
            if st.button("💾 Salvar alterações no banco", key="btn_save_back"):
                with st.spinner("Salvando..."):
                    try:
                        save_meeting_artifacts(_mid, _lhub)
                        if _lhub.bpmn.ready:
                            save_bpmn_from_hub(
                                meeting_id=_mid,
                                project_id=_pid,
                                hub=_lhub,
                            )
                        if _lhub.sbvr.ready:
                            save_sbvr_from_hub(_mid, _pid, _lhub)
                        st.toast("💾 Alterações salvas.", icon="✅")
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# HANDLER DE REEXECUÇÃO (ambos os modos)
# ─────────────────────────────────────────────────────────────────────────────
if "rerun_agent" in st.session_state:
    agent = st.session_state.pop("rerun_agent")
    hub = st.session_state.get("hub")
    if hub:
        client_info = get_session_llm_client(st.session_state.selected_provider)
        if client_info:
            try:
                hub = handle_rerun(agent, hub, client_info,
                                   st.session_state.provider_cfg,
                                   st.session_state.output_language)
                st.session_state.hub = hub
                st.success(f"✅ {agent.capitalize()} re‑executado com sucesso.")
            except Exception as e:
                st.error(f"Erro na reexecução: {e}")
        else:
            st.error("Chave de API não encontrada.")
    else:
        st.error("Nenhuma sessão ativa. Execute o pipeline primeiro.")

# ─────────────────────────────────────────────────────────────────────────────
# EXIBIÇÃO DOS RESULTADOS (ambos os modos)
# ─────────────────────────────────────────────────────────────────────────────
if "hub" in st.session_state:
    hub = st.session_state.hub
    prefix = st.session_state.prefix
    suffix = st.session_state.suffix

    # ── Abas primárias (resultados principais) ────────────────────────────────
    primary = []
    if hub.minutes.ready:
        primary.append("minutes")
    if hub.requirements.ready:
        primary.append("requirements")
    if hub.bpmn.ready:
        primary.append("bpmn")
        primary.append("mermaid")
    if hub.synthesizer.ready:
        primary.append("synthesizer")
    primary.append("export")

    # ── Abas avançadas (análise complementar) ─────────────────────────────────
    advanced = []
    if hub.transcript_quality.ready:
        advanced.append("quality")
    if hub.sbvr.ready:
        advanced.append("sbvr")
    if hub.bmm.ready:
        advanced.append("bmm")
    if getattr(hub, 'dmn', None) and hub.dmn.ready:
        advanced.append("dmn")
    if getattr(hub, 'argumentation', None) and hub.argumentation.ready:
        advanced.append("argumentation")
    if hub.validation.ready and hub.validation.n_bpmn_runs > 1:
        advanced.append("validation")
    if st.session_state.show_dev_tools:
        advanced.append("devtools")

    tab_labels = {
        "minutes":      "📋 Ata de Reunião",
        "requirements": "📝 Requisitos",
        "bpmn":         "📐 BPMN 2.0",
        "mermaid":      "📊 Mermaid",
        "synthesizer":  "📄 Relatório Executivo",
        "export":       "📦 Exportar",
        "quality":      "🔬 Qualidade da Transcrição",
        "sbvr":         "📖 SBVR",
        "bmm":          "🎯 BMM",
        "validation":   "🏆 Validação BPMN",
        "dmn":          "⚖️ DMN",
        "argumentation": "🗺️ IBIS / Argumentação",
        "devtools":     "🔍 Dev Tools",
    }

    def _render_tab(tab_id):
        if tab_id == "minutes":       render_minutes(hub, prefix, suffix)
        elif tab_id == "requirements": render_requirements(hub, prefix, suffix)
        elif tab_id == "bpmn":        render_bpmn(hub, prefix, suffix)
        elif tab_id == "mermaid":     render_mermaid(hub, prefix, suffix)
        elif tab_id == "synthesizer": render_synthesizer(hub, prefix, suffix)
        elif tab_id == "export":      render_export(hub, prefix, suffix)
        elif tab_id == "quality":     render_quality(hub, prefix, suffix)
        elif tab_id == "sbvr":        render_sbvr(hub, prefix, suffix)
        elif tab_id == "bmm":         render_bmm(hub, prefix, suffix)
        elif tab_id == "validation":  render_validation(hub)
        elif tab_id == "dmn":          render_dmn(hub, prefix, suffix)
        elif tab_id == "argumentation": render_argumentation(hub, prefix, suffix)
        elif tab_id == "devtools":    render_dev_tools(hub, st.session_state.show_raw_json)

    # Renderiza abas primárias
    tabs = st.tabs([tab_labels[t] for t in primary])
    for idx, tab_id in enumerate(primary):
        with tabs[idx]:
            _render_tab(tab_id)

    # Renderiza abas avançadas em expander, se houver conteúdo
    if advanced:
        with st.expander("🔬 Análise Avançada", expanded=False):
            adv_tabs = st.tabs([tab_labels[t] for t in advanced])
            for idx, tab_id in enumerate(advanced):
                with adv_tabs[idx]:
                    _render_tab(tab_id)

# Rodapé
st.markdown("---")
st.caption("Process2Diagram v4.13 — Arquitetura Multi‑Agente Modular")
