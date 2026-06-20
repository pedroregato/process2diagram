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
    save_sbvr_from_hub, save_bpmn_from_hub, save_requirements_from_hub,
    list_contexts as list_projects, list_meetings, load_meeting_as_hub,
)
from agents.agent_req_reconciler import AgentReqReconciler
from modules.supabase_client import supabase_configured
from ui.tabs import (
    render_quality, render_bpmn, render_mermaid, render_validation,
    render_minutes, render_requirements, render_sbvr, render_bmm,
    render_synthesizer, render_export, render_dev_tools,
    render_dmn, render_argumentation, render_query_summary,
)
try:
    from ui.tabs import render_communication_noise
except ImportError:
    def render_communication_noise(hub, prefix=None, suffix=None):  # type: ignore[misc]
        import streamlit as st
        st.info("Análise de ruídos indisponível nesta versão.")
from modules.session_security import get_session_llm_client
from modules.i18n import t

apply_auth_gate()

# Sidebar (específica do pipeline)
render_sidebar()

# ── Cabeçalho ─────────────────────────────────────────────────────────────────
from ui.components.page_header import render_page_header
render_page_header(
    "🚀", t("pipeline_title"),
    t("pipeline_caption"),
)

# ── Badge de cenário ativo ────────────────────────────────────────────────────
_active_assignments = st.session_state.get("scenario_assignments")
if _active_assignments:
    _scen_name = st.session_state.get("scenario_name", "Cenário ativo")
    _badge_parts = " | ".join(
        f"{k}: `{v}`" for k, v in list(_active_assignments.items())[:4]
    )
    _more = f" + {len(_active_assignments) - 4} mais" if len(_active_assignments) > 4 else ""
    st.info(
        f"**Cenário ativo: \"{_scen_name}\"** — {_badge_parts}{_more}",
        icon="ℹ️",
    )

# ─────────────────────────────────────────────────────────────────────────────
# MODO: Nova transcrição vs. Reunião existente
# ─────────────────────────────────────────────────────────────────────────────
_db_available = supabase_configured()

_MODE_NEW = t("mode_new")
_MODE_LOAD = t("mode_load")

if _db_available:
    pipeline_mode = st.radio(
        t("operation_mode"),
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

    # ── Botão Nova Transcrição — aparece quando resultados já estão na tela ──
    if "hub" in st.session_state:
        _nc_col, _ = st.columns([1, 5])
        if _nc_col.button("🆕 Nova Transcrição", key="btn_nova_transcricao",
                          help="Limpa a transcrição atual e os resultados para processar uma nova"):
            for _k in ["hub", "curated_clean", "pp_result",
                       "_last_uploaded_file", "current_meeting_id"]:
                st.session_state.pop(_k, None)
            st.session_state["transcript_text"] = ""
            st.rerun()

    # Área de entrada e curadoria
    start_process = render_input_area()

    # Verificação de API key
    if not get_session_llm_client(st.session_state.selected_provider):
        st.warning(t("insert_api_key"))
        st.stop()

    # ── Pipeline principal ────────────────────────────────────────────────────
    if start_process and st.session_state.transcript_text.strip():
        if not any([st.session_state.run_quality, st.session_state.run_bpmn,
                    st.session_state.run_minutes, st.session_state.run_requirements,
                    st.session_state.run_synthesizer]):
            st.warning(t("select_one_agent"))
            st.stop()

        client_info = get_session_llm_client(st.session_state.selected_provider)
        if not client_info:
            st.error(t("api_key_missing"))
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
            "run_communication_noise": st.session_state.get("run_communication_noise", False),
            "run_bmm": st.session_state.run_bmm,
            "run_synthesizer": st.session_state.run_synthesizer,
            "n_bpmn_runs": st.session_state.n_bpmn_runs,
            "bpmn_weights": st.session_state.bpmn_weights,
            "use_langgraph": st.session_state.use_langgraph,
            "validation_threshold": st.session_state.validation_threshold,
            "max_bpmn_retries":     st.session_state.max_bpmn_retries,
            "max_minutes_retries":    st.session_state.get("max_minutes_retries", 2),
            "max_req_retries":        st.session_state.get("max_req_retries", 2),
            "max_delegation_rounds":  st.session_state.get("max_delegation_rounds", 1),
            "project_id":         st.session_state.get("project_id", ""),
            "active_project_id":  st.session_state.get("active_project_id", ""),
            "project_slug":       _ata_slug,
            "meeting_location":   "Videoconferência",
            "run_ckf_updater":           st.session_state.run_ckf_updater,
            "run_knowledge_extractor":   st.session_state.get("run_knowledge_extractor", True),
            "run_query_summarizer":      st.session_state.get("run_query_summarizer", False),
        }

        with st.status(t("pipeline_running"), expanded=True) as _pipeline_status:
            def update_progress(step, status):
                if "done" in status:
                    icon = "✅"
                elif "running" in status:
                    icon = "⏳"
                elif "skipped" in status:
                    icon = "⏭️"
                else:
                    icon = "❌"
                st.write(f"{icon} **{step}** — {status}")
            try:
                hub = run_pipeline(hub, config, update_progress)
                st.session_state.hub = hub
                _cache_hits = getattr(hub.meta, "cache_hits", 0)
                _cache_label = (
                    f" · ⚡ {_cache_hits} cache hit(s)"
                    if _cache_hits else ""
                )
                _pipeline_status.update(
                    label=(
                        t("pipeline_done", tokens=hub.meta.total_tokens_used)
                        + _cache_label
                    ),
                    state="complete",
                    expanded=False,
                )
            except Exception as e:
                _pipeline_status.update(label=t("pipeline_error"), state="error", expanded=True)
                st.error(f"{t('pipeline_error')}: {e}")
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
                            pass

                    if hub.requirements.ready:
                        save_requirements_from_hub(meeting_id, st.session_state.project_id, hub)

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

        # FIX: st.rerun() removido — causava re-avaliação do file_uploader
        # que apagava o hub do session_state antes de renderizar as abas.
        # O Streamlit já re-renderiza naturalmente após o bloco if start_process.

# ─────────────────────────────────────────────────────────────────────────────
# MODO B — REUNIÃO EXISTENTE
# ─────────────────────────────────────────────────────────────────────────────
else:
    st.markdown(t("load_meeting"))

    # Contexto vem da Central de Operações (Home) — nunca mostramos selectbox aqui.
    selected_proj_id = st.session_state.get("active_project_id")
    if not selected_proj_id:
        st.warning(
            "Nenhum contexto ativo. Selecione um contexto na **Central de Operações** antes de carregar uma reunião.",
            icon="⚠️",
        )
        st.stop()

    # Mostra o contexto ativo como informação (somente leitura)
    _projects = list_projects()
    _active_proj = next((p for p in _projects if p["id"] == selected_proj_id), None)
    if _active_proj:
        st.caption(f"Contexto ativo: **{_active_proj['name']}**")

    meetings = list_meetings(selected_proj_id)
    if not meetings:
        st.info(t("no_meetings_ctx"))
        st.stop()

    def _fmt_meeting(m: dict) -> str:
        date = (m.get("meeting_date") or "")[:10]
        title = m.get("title") or m.get("id", "")[:8]
        return f"{date}  {title}" if date else title

    meet_labels = [_fmt_meeting(m) for m in meetings]
    meet_ids    = [m["id"] for m in meetings]

    selected_meet_label = st.selectbox(
        t("meeting_selector"),
        meet_labels,
        key="load_meet_select",
    )
    selected_meet_id = meet_ids[meet_labels.index(selected_meet_label)]

    col_load, col_gap = st.columns([1, 4])
    load_clicked = col_load.button(t("load"), type="primary", key="btn_load_meeting")

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

    if "hub" in st.session_state and st.session_state.hub.loaded_from_db:
        _lhub = st.session_state.hub
        _mid  = st.session_state.get("_loaded_meeting_id")
        _pid  = st.session_state.get("_loaded_project_id")
        if _mid and _pid:
            st.markdown("---")
            if st.button(t("save_back"), key="btn_save_back"):
                with st.spinner("Salvando..."):
                    try:
                        save_meeting_artifacts(_mid, _lhub)
                        if _lhub.bpmn.ready:
                            save_bpmn_from_hub(
                                meeting_id=_mid,
                                project_id=_pid,
                                hub=_lhub,
                            )
                        if _lhub.requirements.ready:
                            save_requirements_from_hub(_mid, _pid, _lhub)
                        if _lhub.sbvr.ready:
                            save_sbvr_from_hub(_mid, _pid, _lhub)
                        st.toast("💾 Alterações salvas.", icon="✅")
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")

# ─────────────────────────────────────────────────────────────────────────────
# HANDLER DE REEXECUÇÃO (ambos os modos)
# ─────────────────────────────────────────────────────────────────────────────
if "rerun_agent" in st.session_state:
    import threading as _threading
    import copy as _copy
    import time as _time
    _agent_name = st.session_state.pop("rerun_agent")
    # Guard: não inicia novo thread se já existe um em execução
    _existing = st.session_state.get("_rr_thread")
    if _existing is not None and _existing.is_alive():
        _running_agent = st.session_state.get("_rr_agent", _agent_name)
        st.warning(f"⏳ Agente **{_running_agent}** já está em execução. Aguarde a conclusão.")
    else:
        _hub = st.session_state.get("hub")
        if _hub:
            _client_info = get_session_llm_client(st.session_state.selected_provider)
            if _client_info:
                _task = {"hub": None, "messages": [], "error": None}
                st.session_state["_rr_task"] = _task
                st.session_state["_rr_agent"] = _agent_name
                st.session_state["_rr_start"] = _time.time()
                _pcfg = st.session_state.provider_cfg
                _olang = st.session_state.output_language
                _hub_copy = _copy.copy(_hub)
                def _rr_worker(_t=_task, _a=_agent_name, _h=_hub_copy, _c=_client_info, _p=_pcfg, _o=_olang):
                    try:
                        _t["hub"], _t["messages"] = handle_rerun(_a, _h, _c, _p, _o)
                    except Exception as _e:
                        _t["error"] = str(_e)
                _rr_thread = _threading.Thread(target=_rr_worker, daemon=True)
                st.session_state["_rr_thread"] = _rr_thread
                _rr_thread.start()
                st.rerun()
            else:
                st.error("Chave de API não encontrada.")
        else:
            st.error("Nenhuma sessão ativa. Execute o pipeline primeiro.")

# POLLING — mantém WebSocket vivo enquanto o agente roda em background
# Usa thread.is_alive() como fonte de verdade (evita problemas de referência de dict no session_state)
_rr_thread = st.session_state.get("_rr_thread")
if _rr_thread is not None:
    import time as _time
    _rr_agent = st.session_state.get("_rr_agent", "agente")
    _rr_task = st.session_state.get("_rr_task", {})
    if not _rr_thread.is_alive():
        _rr_start = st.session_state.pop("_rr_start", None)
        st.session_state.pop("_rr_thread", None)
        st.session_state.pop("_rr_task", None)
        st.session_state.pop("_rr_agent", None)
        if _rr_task.get("hub") is not None:
            st.session_state.hub = _rr_task["hub"]
            st.success(f"✅ {_rr_agent.capitalize()} re‑executado com sucesso.")
            for _lvl, _msg in (_rr_task.get("messages") or []):
                if _lvl == "info":
                    st.info(_msg)
                elif _lvl == "warning":
                    st.warning(_msg)
                elif _lvl == "error":
                    st.error(_msg)
        elif _rr_task.get("error"):
            st.error(f"Erro na reexecução: {_rr_task['error']}")
        else:
            st.error("Reexecução falhou sem retornar resultado.")
    else:
        _elapsed = int(_time.time() - st.session_state.get("_rr_start", _time.time()))
        st.info(f"⏳ Executando agente **{_rr_agent}**… aguarde. ({_elapsed}s)")
        _time.sleep(1)
        st.rerun()

# ─────────────────────────────────────────────────────────────────────────────
# EXIBIÇÃO DOS RESULTADOS (ambos os modos)
# ─────────────────────────────────────────────────────────────────────────────
if "hub" in st.session_state:
    hub = st.session_state.hub
    prefix = st.session_state.prefix
    suffix = st.session_state.suffix

    # ── Cache hit indicator ───────────────────────────────────────────────────
    _hits = getattr(getattr(hub, "meta", None), "cache_hits", 0)
    _saved = getattr(getattr(hub, "meta", None), "tokens_saved", 0)
    if _hits > 0:
        _usd = _saved / 1_000_000 * 0.27
        _col_msg, _col_help = st.columns([10, 1])
        _col_msg.success(t("cache_hits", hits=_hits, tokens=_saved, usd=_usd))
        _col_help.metric(
            label=" ",
            value="ⓘ",
            help=(
                "**Cache semântico de LLM**\n\n"
                "Quando o mesmo agente recebe uma transcrição já processada anteriormente, "
                "a resposta é recuperada diretamente do banco de dados (sem chamar a API). "
                "O resultado é idêntico ao original — o token_map de PII é reaplicado "
                "corretamente para cada sessão.\n\n"
                "Configure TTL e veja estatísticas em **Qualidade ROI-TR → 💾 Cache LLM**."
            ),
        )

    # ── Long context indicator ────────────────────────────────────────────────
    _lc_calls = getattr(getattr(hub, "meta", None), "long_context_calls", 0)
    if _lc_calls > 0:
        st.info(t("long_ctx_info", calls=_lc_calls), icon="📄")
    # ─────────────────────────────────────────────────────────────────────────

    # ── Sugestão de título ────────────────────────────────────────────────────
    _suggested_title = ""
    if hub.minutes.ready and hub.minutes.title:
        _suggested_title = hub.minutes.title.strip()
    _current_title = st.session_state.get("meeting_title", "").strip()

    if _suggested_title and _suggested_title.lower() != _current_title.lower():
        with st.container(border=True):
            _tc, _tb = st.columns([5, 1])
            _tc.markdown(
                f"{t('suggested_title')}  \n> {_suggested_title}"
            )
            if _tb.button(t("use_this_title"), key="btn_use_suggested_title", use_container_width=True):
                st.session_state.meeting_title = _suggested_title
                _mid_for_title = st.session_state.get("current_meeting_id")
                if _mid_for_title:
                    try:
                        from core.project_store import update_meeting_title
                        update_meeting_title(_mid_for_title, _suggested_title)
                    except Exception:
                        pass
                st.rerun()

    # ── Tempo de reunião + fala por participante ───────────────────────────────
    _mt = getattr(hub, "meeting_time", None)
    if _mt and _mt.ready and (_mt.duration_seconds or _mt.speaker_times):
        from modules.transcript_time_parser import format_duration, format_speaker_table
        import pandas as pd
        with st.expander("⏱️ Tempo de reunião e fala por participante", expanded=False):
            _source_label = (
                "extraído de timestamps da transcrição"
                if _mt.has_timestamps
                else "estimado por contagem de palavras (sem timestamps detectados)"
            )
            _dur_col, _note_col = st.columns([1, 3])
            _dur_col.metric("Duração total", format_duration(_mt))
            _note_col.caption(f"Fonte: {_source_label}")

            if _mt.speaker_times:
                _rows = format_speaker_table(_mt)
                st.dataframe(
                    pd.DataFrame(_rows),
                    use_container_width=True,
                    hide_index=True,
                )

    # ─────────────────────────────────────────────────────────────────────────

    tab_labels = {
        "minutes":             t("tab_minutes"),
        "requirements":        t("tab_requirements"),
        "bpmn":                t("tab_bpmn"),
        "mermaid":             t("tab_mermaid"),
        "synthesizer":         t("tab_synthesizer"),
        "query_summary":       t("tab_query_summary"),
        "export":              t("tab_export"),
        "quality":             t("tab_quality"),
        "sbvr":                t("tab_sbvr"),
        "bmm":                 t("tab_bmm"),
        "validation":          t("tab_validation"),
        "dmn":                 t("tab_dmn"),
        "argumentation":       t("tab_argumentation"),
        "communication_noise": t("tab_comm_noise"),
        "devtools":            t("tab_devtools"),
    }

    # ── Monta lista única de abas na ordem desejada ───────────────────────────
    all_tabs = []

    if hub.minutes.ready:
        all_tabs.append("minutes")
    if hub.requirements.ready:
        all_tabs.append("requirements")
    if hub.bpmn.ready:
        all_tabs.append("bpmn")
        all_tabs.append("mermaid")
    if hub.synthesizer.ready:
        all_tabs.append("synthesizer")
    if getattr(hub, 'query_summary', None) and hub.query_summary.ready:
        all_tabs.append("query_summary")
    all_tabs.append("export")

    if hub.transcript_quality.ready:
        all_tabs.append("quality")
    if hub.sbvr.ready:
        all_tabs.append("sbvr")
    if hub.bmm.ready:
        all_tabs.append("bmm")
    if getattr(hub, 'dmn', None) and hub.dmn.ready:
        all_tabs.append("dmn")
    if getattr(hub, 'argumentation', None) and hub.argumentation.ready:
        all_tabs.append("argumentation")
    if getattr(hub, 'communication_noise', None) and hub.communication_noise.ready:
        all_tabs.append("communication_noise")
    if hub.validation.ready and hub.validation.n_bpmn_runs > 1:
        all_tabs.append("validation")
    if st.session_state.show_dev_tools:
        all_tabs.append("devtools")

    def _render_tab(tab_id):
        if tab_id == "minutes":        render_minutes(hub, prefix, suffix)
        elif tab_id == "requirements": render_requirements(hub, prefix, suffix)
        elif tab_id == "bpmn":         render_bpmn(hub, prefix, suffix)
        elif tab_id == "mermaid":      render_mermaid(hub, prefix, suffix)
        elif tab_id == "synthesizer":  render_synthesizer(hub, prefix, suffix)
        elif tab_id == "export":       render_export(hub, prefix, suffix)
        elif tab_id == "quality":      render_quality(hub, prefix, suffix)
        elif tab_id == "sbvr":         render_sbvr(hub, prefix, suffix)
        elif tab_id == "bmm":          render_bmm(hub, prefix, suffix)
        elif tab_id == "validation":   render_validation(hub)
        elif tab_id == "dmn":          render_dmn(hub, prefix, suffix)
        elif tab_id == "argumentation": render_argumentation(hub, prefix, suffix)
        elif tab_id == "query_summary": render_query_summary(hub)
        elif tab_id == "communication_noise": render_communication_noise(hub, prefix, suffix)
        elif tab_id == "devtools":     render_dev_tools(hub, st.session_state.show_raw_json)

    tabs = st.tabs([tab_labels[t] for t in all_tabs])
    for idx, tab_id in enumerate(all_tabs):
        with tabs[idx]:
            _render_tab(tab_id)

# Rodapé
st.markdown("---")
st.caption("Process2Diagram v4.13 — Arquitetura Multi‑Agente Modular")
