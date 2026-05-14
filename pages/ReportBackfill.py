"""
Backfill executivo — gera/regenera o Relatório Executivo HTML
para uma reunião específica ou para todas as reuniões de um projeto.
"""

import streamlit as st
from ui.auth_gate import apply_auth_gate
from modules.config import AVAILABLE_PROVIDERS
from core.project_store import get_supabase_client

apply_auth_gate()

st.title("📄 Backfill — Relatório Executivo")
st.caption(
    "Gera o Relatório Executivo HTML para reuniões existentes sem reprocessar o pipeline completo. "
    "Apenas o AgentSynthesizer é executado, usando os dados já armazenados no Supabase."
)

# ── Sidebar: provider + API key ───────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuração")
    provider = st.selectbox("Provedor LLM", list(AVAILABLE_PROVIDERS.keys()), key="rb_provider")
    api_key  = st.text_input(
        AVAILABLE_PROVIDERS[provider]["api_key_label"],
        type="password", key="rb_api_key"
    )
    language = st.selectbox("Idioma do relatório", ["Portuguese (BR)", "English"], key="rb_lang")

    if not api_key:
        st.warning("⚠️ Insira a API key para continuar.")

# ── Project + meeting selector ────────────────────────────────────────────────
project_id = st.session_state.get("active_project_id")
project_name = st.session_state.get("active_project_name", "")

if not project_id:
    st.warning("Nenhum projeto de trabalho ativo. Selecione um projeto na Central de Operações.")
    st.page_link("pages/Home.py", label="← Ir para a Central de Operações")
    st.stop()

st.info(f"📁 Projeto: **{project_name}**")

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
            _opts = {f"Reunião {m['meeting_number']} — {m['title']}": m["id"] for m in _meetings}
            _sel = st.selectbox("Selecionar reunião", list(_opts.keys()), key="rb_meeting_sel")
            meeting_id = _opts.get(_sel)
    except Exception as _e:
        st.error(f"Erro ao carregar reuniões: {_e}")

# ── Build LLM config ──────────────────────────────────────────────────────────
prov_cfg = AVAILABLE_PROVIDERS.get(provider, {})
llm_config = {
    **prov_cfg,
    "api_key": api_key,
    "provider_name": provider,
}

# ── Tabs: single meeting / all project ───────────────────────────────────────
tab_single, tab_batch = st.tabs(["📋 Reunião Única", "📦 Todas as Reuniões"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB: Single meeting
# ─────────────────────────────────────────────────────────────────────────────
with tab_single:
    st.subheader("Gerar relatório para uma reunião")

    if not meeting_id:
        st.info("Selecione um projeto e uma reunião no seletor acima.")
    elif not api_key:
        st.warning("Configure a API key na sidebar.")
    else:
        # Check if report already exists
        client = get_supabase_client()
        existing = None
        if client:
            try:
                row = (
                    client.table("meetings")
                    .select("report_html, report_generated_at, report_provider, title, meeting_number")
                    .eq("id", meeting_id)
                    .single()
                    .execute()
                ).data
                existing = row.get("report_html")
                mtg_label = f"Reunião {row.get('meeting_number')} — {row.get('title', '')}"
            except Exception:
                mtg_label = "Reunião selecionada"

        st.write(f"**{mtg_label}**")

        if existing:
            st.success("✅ Esta reunião já possui relatório executivo gerado.")
            col1, col2 = st.columns([1, 1])
            with col1:
                # Persist bytes before button renders (survive rerun)
                if "rb_existing_html" not in st.session_state:
                    st.session_state["rb_existing_html"] = existing.encode()
                st.download_button(
                    "⬇️ Baixar relatório existente",
                    data=st.session_state["rb_existing_html"],
                    file_name=f"relatorio_executivo_reuniao.html",
                    mime="text/html",
                    key="btn_dl_existing",
                )
            with col2:
                regenerate = st.button("🔄 Regenerar (sobrescrever)", key="btn_regen_single")
        else:
            st.warning("⚠️ Esta reunião ainda não tem relatório executivo.")
            regenerate = st.button("▶️ Gerar Relatório Executivo", key="btn_gen_single", type="primary")

        if "regenerate" in dir() and regenerate:
            with st.spinner("Gerando relatório executivo..."):
                from modules.report_builder import build_report_for_meeting
                result = build_report_for_meeting(meeting_id, llm_config, language)

            if result.success:
                st.success(f"✅ Relatório gerado com sucesso! ({result.tokens_used:,} tokens · {result.provider})")
                st.session_state["rb_result_html"] = result.html.encode()
                st.download_button(
                    "⬇️ Baixar Relatório Executivo",
                    data=st.session_state["rb_result_html"],
                    file_name=f"relatorio_executivo_reuniao_{result.meeting_number}.html",
                    mime="text/html",
                    key="btn_dl_result",
                )
                with st.expander("👁️ Pré-visualizar", expanded=False):
                    import streamlit.components.v1 as components
                    components.html(result.html, height=600, scrolling=True)
            else:
                st.error(f"❌ Falha: {result.error}")

# ─────────────────────────────────────────────────────────────────────────────
# TAB: All meetings in project
# ─────────────────────────────────────────────────────────────────────────────
with tab_batch:
    st.subheader("Gerar relatório para todas as reuniões do projeto")

    if not project_id:
        st.info("Selecione um projeto no seletor acima.")
    elif not api_key:
        st.warning("Configure a API key na sidebar.")
    else:
        # Show coverage table
        client = get_supabase_client()
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
                    "Nº": r.get("meeting_number"),
                    "Título": r.get("title", ""),
                    "Relatório": "✅ Gerado" if r.get("report_html") else "❌ Pendente",
                    "Gerado em": (r.get("report_generated_at") or "")[:16].replace("T", " "),
                    "Provedor": r.get("report_provider") or "",
                } for r in rows])
                st.dataframe(df, use_container_width=True, hide_index=True)

                pending = sum(1 for r in rows if not r.get("report_html"))
                total   = len(rows)
                st.write(f"**{total - pending}** de **{total}** reuniões com relatório gerado. **{pending}** pendentes.")

        skip_existing = st.checkbox(
            "Pular reuniões que já têm relatório (recomendado)",
            value=True, key="rb_skip_existing"
        )

        if st.button("▶️ Gerar Relatórios em Lote", key="btn_batch", type="primary",
                     disabled=not project_id or not api_key):
            from modules.report_builder import build_reports_for_project

            progress_bar = st.progress(0)
            status_text  = st.empty()
            results_list = []

            def _callback(current, total, result):
                progress_bar.progress(current / total)
                icon = "✅" if result.success else "❌"
                status_text.text(
                    f"{icon} [{current}/{total}] Reunião {result.meeting_number} — {result.meeting_title}"
                )
                results_list.append(result)

            with st.spinner("Processando..."):
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

            st.success(f"✅ {success_count} relatórios gerados com sucesso.")
            if fail_count:
                st.error(f"❌ {fail_count} falhas.")
                for r in results:
                    if not r.success:
                        st.write(f"- Reunião {r.meeting_number}: {r.error}")

            total_tokens = sum(r.tokens_used for r in results)
            st.info(f"Total de tokens usados: {total_tokens:,}")
