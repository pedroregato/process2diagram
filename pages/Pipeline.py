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

        # ── Tier-2 PII: detectar nomes antes do pipeline (PC82) ──────────────
        # Constrói hub.meta.name_map uma vez a partir da transcrição para que
        # todos os agentes compartilhem o mesmo esquema de pseudonimização via
        # BaseAgent._call_llm(). Executado antes de run_pipeline() para que
        # toda chamada LLM da sessão já receba name_map preenchido.
        # Fail-open: qualquer erro aqui não bloqueia o pipeline.
        try:
            from modules.pii_sanitizer import detect_names as _detect_names
            _nm = _detect_names(hub.transcript_clean or hub.transcript_raw)
            if _nm:
                hub.meta.name_map = _nm
        except Exception:
            pass
        # ─────────────────────────────────────────────────────────────────────

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

                    # LGPD audit — log pipeline run (async, fail-open)
                    try:
                        from modules.compliance import log_audit_event, detect_pii
                        from modules.auth import get_current_user as _get_user
                        _pii = detect_pii(hub.transcript_raw or "")
                        st.session_state[f"_pii_result_{meeting_id}"] = _pii
                        log_audit_event(
                            "pipeline_run",
                            meeting_id=meeting_id,
                            project_id=st.session_state.get("project_id"),
                            user_login=_get_user(),
                            details=_pii.summary,
                        )
                    except Exception:
                        pass

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

    meet_ids = [m["id"] for m in meetings]

    # Use index-based selectbox so duplicate labels never map to the wrong meeting
    _meet_idx = st.selectbox(
        t("meeting_selector"),
        options=range(len(meetings)),
        format_func=lambda i: _fmt_meeting(meetings[i]),
        key="load_meet_select_idx",
    )
    selected_meet_id = meet_ids[_meet_idx]

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

        # ── Renomear reunião ──────────────────────────────────────────────────
        with st.expander("✏️ Renomear reunião", expanded=False):
            _ri_col, _rb_col = st.columns([5, 1])
            _new_title_val = _ri_col.text_input(
                "Novo título",
                value=_title,
                key="rename_title_input",
                max_chars=200,
                label_visibility="collapsed",
            )
            if _rb_col.button("💾 Salvar", key="btn_rename_meeting", use_container_width=True):
                _clean_title = _new_title_val.strip()
                if _clean_title and _clean_title != _title:
                    from core.project_store import update_meeting_title
                    if update_meeting_title(_loaded_id, _clean_title):
                        # Update minutes title in loaded hub
                        if hasattr(st.session_state.hub.minutes, "title"):
                            st.session_state.hub.minutes.title = _clean_title
                        st.toast(f"✅ Título alterado para «{_clean_title}»", icon="✏️")
                    else:
                        st.error("Erro ao atualizar o título no banco de dados.")
                elif not _clean_title:
                    st.warning("O título não pode ser vazio.")
                else:
                    st.info("Nenhuma alteração detectada.")

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
# HANDLER DE REEXECUÇÃO — PC112-I
#
# Fluxo em 2 script runs separadas:
#   Run 1 (rerun_agent presente):
#     • st.status() mostra "RUNNING" → fast path (PC112-H) conclui em <1s
#     • hub stored + pending_messages stored → st.rerun() imediato
#     • Script run curta: WS não cai durante execução (<1s)
#   Run 2 (rerun_agent ausente, hub atualizado):
#     • Pending messages consumidas como toast
#     • Hub section renderiza normalmente, idêntico ao load inicial
#     • st.rerun() CONTROLADO pelo Streamlit → árvore sincronizada
#     • Sem WS drop mid-render → sem setIn
#
# Por que st.rerun() é seguro agora:
#   PC112-F tinha st.rerun() mas o handler ainda chamava o LLM (minutos).
#   PC112-H adicionou o fast path (<1s). Com handler <1s, o WS nunca cai
#   durante a Run 1. O rerun é controlado, não fruto de WS drop aleatório.
#
# Por que PC112-G (sem st.rerun()) falhou:
#   O hub inteiro (todos os tabs, BPMN viewer, atas em markdown, requisitos)
#   renderizava na MESMA script run do handler → centenas de deltas → WS
#   fechava mid-render → cliente com árvore parcial → setIn na reconexão.
# ─────────────────────────────────────────────────────────────────────────────

# Consome mensagens diferidas da run anterior (fail-open).
for _lvl, _msg in st.session_state.pop("_rr_pending_messages", []):
    _icon = {"success": "✅", "info": "ℹ️", "warning": "⚠️"}.get(_lvl, "❌")
    st.toast(_msg, icon=_icon)

if "rerun_agent" in st.session_state:
    import copy as _copy
    _agent_name = st.session_state.pop("rerun_agent")
    # Limpa estado legado de thread/polling (migração PC112-E/F → PC112-G/I)
    for _k in ("_rr_thread", "_rr_task", "_rr_agent", "_rr_start", "_frozen_tabs"):
        st.session_state.pop(_k, None)
    _hub = st.session_state.get("hub")
    if _hub:
        _needs_transcript = _agent_name in ("bpmn", "minutes", "requirements", "sbvr", "bmm", "quality")
        _has_transcript   = bool(getattr(_hub, "transcript_clean", "") or getattr(_hub, "transcript_raw", ""))
        if _needs_transcript and not _has_transcript:
            st.error(
                f"⚠️ Transcrição não encontrada no hub. "
                f"Para reexecutar **{_agent_name}**, carregue a reunião em Modo B "
                f"(a transcrição precisa estar salva no banco) ou execute o pipeline completo."
            )
        else:
            _client_info = get_session_llm_client(st.session_state.selected_provider)
            if _client_info:
                with st.status(f"⏳ Reprocessando agente **{_agent_name}**…", expanded=True) as _rr_status:
                    st.write(f"Executando **{_agent_name}**…")
                    try:
                        _hub_copy = _copy.copy(_hub)
                        _result_hub, _messages = handle_rerun(
                            _agent_name, _hub_copy,
                            _client_info,
                            st.session_state.provider_cfg,
                            st.session_state.output_language,
                        )
                        # Armazena hub + mensagens ANTES do rerun.
                        # O hub renderiza na PRÓXIMA script run (limpa) — não aqui.
                        st.session_state.hub = _result_hub
                        st.session_state["_rr_pending_messages"] = [
                            ("success", f"✅ {_agent_name.capitalize()} re‑executado com sucesso."),
                        ] + list(_messages or [])
                        _rr_status.update(
                            label=f"✅ {_agent_name.capitalize()} concluído. Recarregando…",
                            state="complete",
                            expanded=False,
                        )
                    except Exception as _e:
                        _rr_status.update(label="❌ Erro na reexecução.", state="error", expanded=True)
                        st.write(f"Erro: {str(_e)}")
                        st.session_state["_rr_pending_messages"] = [("error", f"❌ Erro: {str(_e)}")]
                # st.rerun() controlado — handler já concluiu (<1s via fast path PC112-H).
                # Streamlit sincroniza a árvore cliente-servidor de forma limpa.
                st.rerun()
            else:
                st.error("Chave de API não encontrada.")
    else:
        st.error("Nenhuma sessão ativa. Execute o pipeline primeiro.")

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

    def _render_transcript_tab(hub):
        from ui.components.copy_button import copy_button
        from services.export_service import make_filename

        clean = (hub.transcript_clean or "").strip()
        raw   = (hub.transcript_raw  or "").strip()
        text  = clean or raw
        if not text:
            st.warning("Transcrição não disponível.")
            return
        wc = len(text.split())
        cc = len(text)
        version = "processada" if clean else "original"

        _hdr, _act1, _act2 = st.columns([6, 1, 1])
        _hdr.caption(f"**Transcrição {version}** · {wc:,} palavras · {cc:,} caracteres")
        with _act1:
            copy_button(text, key="tr_clean", label="📋 Copiar", compact=True)
        with _act2:
            st.download_button(
                "⬇️ .txt",
                data=text.encode("utf-8"),
                file_name=make_filename("transcricao", "txt", prefix, suffix),
                mime="text/plain",
                key="dl_transcript_clean",
                use_container_width=True,
            )
        st.text_area(
            label="transcrição",
            value=text,
            height=520,
            disabled=True,
            key="ta_pipeline_transcript_clean",
            label_visibility="collapsed",
        )
        if raw and clean and raw != clean:
            with st.expander("📄 Transcrição original (antes do pré-processamento)", expanded=False):
                wc_r = len(raw.split())
                cc_r = len(raw)
                _hdr2, _a1, _a2 = st.columns([6, 1, 1])
                _hdr2.caption(f"{wc_r:,} palavras · {cc_r:,} caracteres")
                with _a1:
                    copy_button(raw, key="tr_raw", label="📋 Copiar", compact=True)
                with _a2:
                    st.download_button(
                        "⬇️ .txt",
                        data=raw.encode("utf-8"),
                        file_name=make_filename("transcricao_original", "txt", prefix, suffix),
                        mime="text/plain",
                        key="dl_transcript_raw",
                        use_container_width=True,
                    )
                st.text_area(
                    label="transcrição bruta",
                    value=raw,
                    height=400,
                    disabled=True,
                    key="ta_pipeline_transcript_raw",
                    label_visibility="collapsed",
                )

    # ─────────────────────────────────────────────────────────────────────────

    # ── LGPD Compliance Panel ─────────────────────────────────────────────────
    _compliance_mid = st.session_state.get("current_meeting_id")
    if _compliance_mid and supabase_configured():
        try:
            from modules.compliance import detect_pii, render_consent_panel
            from modules.auth import get_current_user as _lgpd_get_user
            _pii_key = f"_pii_result_{_compliance_mid}"
            if _pii_key not in st.session_state:
                st.session_state[_pii_key] = detect_pii(hub.transcript_raw or "")
            render_consent_panel(
                meeting_id=_compliance_mid,
                pii_result=st.session_state[_pii_key],
                project_id=st.session_state.get("project_id"),
                user_login=_lgpd_get_user(),
            )
        except Exception:
            pass  # compliance panel must never block the pipeline UI
    # ─────────────────────────────────────────────────────────────────────────

    tab_labels = {
        "transcript":          t("tab_transcript"),
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
    _v_minutes  = hub.minutes.ready
    _v_req      = hub.requirements.ready
    _v_bpmn     = hub.bpmn.ready
    _v_synth    = hub.synthesizer.ready
    _v_qs       = bool(getattr(hub, 'query_summary', None) and hub.query_summary.ready)
    _v_quality  = hub.transcript_quality.ready
    _v_sbvr     = hub.sbvr.ready
    _v_bmm      = hub.bmm.ready
    _v_dmn      = bool(getattr(hub, 'dmn', None) and hub.dmn.ready)
    _v_arg      = bool(getattr(hub, 'argumentation', None) and hub.argumentation.ready)
    _v_noise    = bool(getattr(hub, 'communication_noise', None) and hub.communication_noise.ready)

    all_tabs = []

    if hub.transcript_clean or hub.transcript_raw:
        all_tabs.append("transcript")
    if _v_minutes:
        all_tabs.append("minutes")
    if _v_req:
        all_tabs.append("requirements")
    if _v_bpmn:
        all_tabs.append("bpmn")
        all_tabs.append("mermaid")
    if _v_synth:
        all_tabs.append("synthesizer")
    if _v_qs:
        all_tabs.append("query_summary")
    all_tabs.append("export")

    if _v_quality:
        all_tabs.append("quality")
    if _v_sbvr:
        all_tabs.append("sbvr")
    if _v_bmm:
        all_tabs.append("bmm")
    if _v_dmn:
        all_tabs.append("dmn")
    if _v_arg:
        all_tabs.append("argumentation")
    if _v_noise:
        all_tabs.append("communication_noise")
    if hub.validation.ready and hub.validation.n_bpmn_runs > 1:
        all_tabs.append("validation")
    if st.session_state.show_dev_tools:
        all_tabs.append("devtools")

    def _render_tab(tab_id):
        if tab_id == "transcript":
            _render_transcript_tab(hub)
        elif tab_id == "minutes":      render_minutes(hub, prefix, suffix)
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

    st.session_state["_diagram_is_loading"] = False

    tabs = st.tabs([tab_labels[t] for t in all_tabs])
    for idx, tab_id in enumerate(all_tabs):
        with tabs[idx]:
            _render_tab(tab_id)



# Rodapé
st.markdown("---")
st.caption("Process2Diagram v4.13 — Arquitetura Multi‑Agente Modular")
