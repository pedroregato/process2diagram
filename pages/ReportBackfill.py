"""
Backfill executivo — gera/regenera o Relatório Executivo HTML
para uma reunião específica ou para todas as reuniões de um projeto.
"""

import streamlit as st
import streamlit.components.v1 as components
from ui.auth_gate import apply_auth_gate
from modules.config import AVAILABLE_PROVIDERS
from core.project_store import get_supabase_client

apply_auth_gate()

st.title("📄 Backfill — Relatório Executivo")
st.caption(
    "Gera o Relatório Executivo HTML para reuniões existentes sem reprocessar o pipeline completo. "
    "Apenas o AgentSynthesizer é executado, usando os dados já armazenados no Supabase."
)

# ── Provider e API key da sessão global ───────────────────────────────────────
provider = st.session_state.get("asst_provider", "DeepSeek")
api_key  = st.session_state.get("asst_api_key", "")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuração")
    language = st.selectbox("Idioma do relatório", ["Portuguese (BR)", "English"], key="rb_lang")
    st.info(f"🤖 Provedor: **{provider}**")
    if not api_key:
        st.warning("⚠️ API key não configurada. Acesse Configurações → LLM Assistente.")
    st.markdown("---")
    preview_height = st.slider(
        "Altura da visualização (px)", min_value=400, max_value=1200,
        value=700, step=100, key="rb_preview_height"
    )

# ── Project + meeting selector ────────────────────────────────────────────────
project_id   = st.session_state.get("active_project_id")
project_name = st.session_state.get("active_project_name", "")

if not project_id:
    st.warning("Nenhum projeto de trabalho ativo. Selecione um projeto na Central de Operações.")
    st.page_link("pages/Home.py", label="← Ir para a Central de Operações")
    st.stop()

if not api_key:
    st.warning("⚠️ API key não configurada. Acesse **Configurações → LLM Assistente** e salve a chave.")
    st.stop()

st.info(f"📁 Contexto: **{project_name}**")

# ── Meeting selector ──────────────────────────────────────────────────────────
meeting_id = None
_db = get_supabase_client()
if _db:
    try:
        _meetings = (
            _db.table("meetings")
            .select("id, meeting_number, title")
            .eq("project_id", project_id)
            .order("meeting_number")
            .execute()
        ).data or []
        if _meetings:
            _opts      = {f"Reunião {m['meeting_number']} — {m['title']}": m["id"] for m in _meetings}
            _sel       = st.selectbox("Selecionar reunião", list(_opts.keys()), key="rb_meeting_sel")
            meeting_id = _opts.get(_sel)
    except Exception as _e:
        st.error(f"Erro ao carregar reuniões: {_e}")

# ── Build LLM config ──────────────────────────────────────────────────────────
prov_cfg   = AVAILABLE_PROVIDERS.get(provider, {})
llm_config = {
    **prov_cfg,
    "api_key":       api_key,
    "provider_name": provider,
}

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_single, tab_batch = st.tabs(["📋 Reunião Única", "📦 Todas as Reuniões"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB: Single meeting
# ─────────────────────────────────────────────────────────────────────────────
with tab_single:

    if not meeting_id:
        st.info("Selecione uma reunião no seletor acima.")
    else:
        client     = get_supabase_client()
        existing   = None
        mtg_number = 0
        mtg_label  = "Reunião selecionada"
        gen_at     = ""
        gen_prov   = ""

        if client:
            try:
                row = (
                    client.table("meetings")
                    .select("report_html, report_generated_at, report_provider, title, meeting_number")
                    .eq("id", meeting_id)
                    .single()
                    .execute()
                ).data
                existing   = row.get("report_html")
                mtg_number = row.get("meeting_number", 0)
                mtg_label  = f"Reunião {mtg_number} — {row.get('title', '')}"
                gen_at     = (row.get("report_generated_at") or "")[:16].replace("T", " ")
                gen_prov   = row.get("report_provider") or ""
            except Exception:
                pass

        st.markdown(f"### {mtg_label}")

        if existing:
            _cache_key = f"rb_html_{meeting_id}"
            if _cache_key not in st.session_state:
                st.session_state[_cache_key] = existing.encode()

            meta_col, dl_col, regen_col = st.columns([3, 1.2, 1.5])
            with meta_col:
                st.success(f"✅ Gerado em **{gen_at}** · Provedor: **{gen_prov}**")
            with dl_col:
                st.download_button(
                    "⬇️ Baixar HTML",
                    data=st.session_state[_cache_key],
                    file_name=f"relatorio_executivo_reuniao_{mtg_number}.html",
                    mime="text/html",
                    key="btn_dl_existing",
                )
            with regen_col:
                regenerate = st.button("🔄 Regenerar", key="btn_regen_single",
                                       help="Regenerar e sobrescrever o relatório existente")

            st.markdown("#### 👁️ Visualização")
            components.html(existing, height=preview_height, scrolling=True)

        else:
            st.warning("⚠️ Esta reunião ainda não tem relatório executivo.")
            regenerate = st.button(
                "▶️ Gerar Relatório Executivo", key="btn_gen_single", type="primary"
            )

        if "regenerate" in dir() and regenerate:
            with st.spinner("Gerando relatório executivo... (pode levar 1-2 minutos)"):
                from modules.report_builder import build_report_for_meeting
                result = build_report_for_meeting(meeting_id, llm_config, language)

            if result.success:
                st.success(
                    f"✅ Relatório gerado! "
                    f"({result.tokens_used:,} tokens · {result.provider})"
                )
                _cache_key = f"rb_html_{meeting_id}"
                st.session_state[_cache_key] = result.html.encode()
                st.download_button(
                    "⬇️ Baixar Relatório Executivo",
                    data=st.session_state[_cache_key],
                    file_name=f"relatorio_executivo_reuniao_{result.meeting_number}.html",
                    mime="text/html",
                    key="btn_dl_result",
                )
                st.markdown("#### 👁️ Visualização")
                components.html(result.html, height=preview_height, scrolling=True)
            else:
                st.error(f"❌ Falha ao gerar relatório:")
                st.code(result.error, language="text")
                st.info(
                    "💡 Dica: verifique se a reunião possui transcrição armazenada. "
                    "Se não, use **Manutenção → Transcript Backfill** primeiro."
                )

# ─────────────────────────────────────────────────────────────────────────────
# TAB: All meetings in project
# ─────────────────────────────────────────────────────────────────────────────
with tab_batch:
    st.subheader("Gerar relatório para todas as reuniões do projeto")

    client = get_supabase_client()
    rows   = []
    if client:
        try:
            rows = (
                client.table("meetings")
                .select("meeting_number, title, report_html, report_generated_at, report_provider")
                .eq("project_id", project_id)
                .order("meeting_number")
                .execute()
            ).data or []
        except Exception:
            rows = []

    if rows:
        import pandas as pd
        df = pd.DataFrame([{
            "Nº":        r.get("meeting_number"),
            "Título":    r.get("title", ""),
            "Relatório": "✅ Gerado" if r.get("report_html") else "❌ Pendente",
            "Gerado em": (r.get("report_generated_at") or "")[:16].replace("T", " "),
            "Provedor":  r.get("report_provider") or "",
        } for r in rows])
        st.dataframe(df, use_container_width=True, hide_index=True)

        pending = sum(1 for r in rows if not r.get("report_html"))
        total   = len(rows)
        st.write(
            f"**{total - pending}** de **{total}** reuniões com relatório gerado. "
            f"**{pending}** pendentes."
        )

    st.markdown("---")

    skip_existing = st.checkbox(
        "Pular reuniões que já têm relatório (recomendado)",
        value=True, key="rb_skip_existing"
    )

    if st.button("▶️ Gerar Relatórios em Lote", key="btn_batch", type="primary"):
        from modules.report_builder import build_reports_for_project

        progress_bar = st.progress(0)
        status_text  = st.empty()
        errors_found = []

        def _callback(current, total, result):
            progress_bar.progress(current / total)
            icon = "✅" if result.success else "❌"
            status_text.text(
                f"{icon} [{current}/{total}] "
                f"Reunião {result.meeting_number} — {result.meeting_title}"
            )
            if not result.success:
                errors_found.append(result)

        with st.spinner("Processando... (pode levar vários minutos)"):
            results = build_reports_for_project(
                project_id=project_id,
                llm_config=llm_config,
                output_language=language,
                callback=_callback,
                skip_existing=skip_existing,
            )

        progress_bar.progress(1.0)
        success_count = sum(1 for r in results if r.success)
        fail_count    = sum(1 for r in results if not r.success)

        if success_count:
            st.success(f"✅ {success_count} relatório(s) gerado(s) com sucesso.")
        if fail_count:
            st.error(f"❌ {fail_count} falha(s).")
            for r in errors_found:
                with st.expander(f"Reunião {r.meeting_number} — erro"):
                    st.code(r.error, language="text")

        total_tokens = sum(r.tokens_used for r in results)
        if total_tokens:
            st.info(f"Total de tokens usados: {total_tokens:,}")

        st.rerun()
