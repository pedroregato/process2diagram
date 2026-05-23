# pages/DocumentManager.py
# ─────────────────────────────────────────────────────────────────────────────
# Document Manager — upload, index, search, and cross-reference meeting documents.
#
# 5 tabs:
#   📤 Enviar       — upload + embed document
#   📚 Biblioteca   — list, search, preview, delete
#   ⚗️ Extrair      — extract requirements / SBVR / BMM / DMN from document (LLM)
#   🔍 Análise      — cross-reference document vs meeting artifacts (LLM agent)
#   🏷️ Taxonomia    — browse the document type taxonomy
# ─────────────────────────────────────────────────────────────────────────────

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from ui.project_selector import require_active_project
from ui.components.page_header import render_page_header

from modules.document_store import (
    get_document_types,
    get_types_by_category,
    list_documents,
    upload_document,
    embed_document,
    get_document_content,
    delete_document,
    update_document_meta,
    search_documents_semantic,
    search_documents_keyword,
    get_chunks_count,
)


# ── Project context ────────────────────────────────────────────────────────────

require_active_project()
project_id   = st.session_state.get("active_project_id", "")
project_name = st.session_state.get("active_project_name", "Projeto")

render_page_header("📄", "Documentos de Reunião", f"Projeto: {project_name}")

if not project_id:
    st.warning("Selecione um projeto ativo para gerenciar documentos.")
    st.stop()


# ── Helpers ───────────────────────────────────────────────────────────────────

@st.cache_data(ttl=120)
def _cached_doc_types():
    return get_document_types()

@st.cache_data(ttl=120)
def _cached_types_by_category():
    return get_types_by_category()

def _list_meetings() -> list[dict]:
    """Fetch project meetings for linking documents."""
    try:
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return []
        return (
            db.table("meetings")
            .select("id, title, created_at")
            .eq("project_id", project_id)
            .order("created_at", desc=True)
            .limit(100)
            .execute().data or []
        )
    except Exception:
        return []

def _score_color(score: int) -> str:
    if score >= 70:
        return "green"
    if score >= 40:
        return "orange"
    return "red"

def _get_agent():
    """Instantiate DocumentAnalyzerAgent using current session provider."""
    from modules.config import AVAILABLE_PROVIDERS
    from modules.session_security import get_api_key
    provider_name = st.session_state.get("selected_provider", "DeepSeek")
    provider_cfg  = AVAILABLE_PROVIDERS.get(provider_name, {})
    api_key       = get_api_key(provider_name)
    from agents.agent_document_analyzer import DocumentAnalyzerAgent
    return DocumentAnalyzerAgent(
        client_info  = {"api_key": api_key},
        provider_cfg = provider_cfg,
    )

def _get_extractor():
    """Instantiate DocumentExtractorAgent using current session provider."""
    from modules.config import AVAILABLE_PROVIDERS
    from modules.session_security import get_api_key
    provider_name = st.session_state.get("selected_provider", "DeepSeek")
    provider_cfg  = AVAILABLE_PROVIDERS.get(provider_name, {})
    api_key       = get_api_key(provider_name)
    from agents.agent_document_extractor import DocumentExtractorAgent
    return DocumentExtractorAgent(
        client_info  = {"api_key": api_key},
        provider_cfg = provider_cfg,
    )

def _load_file_content(uploaded_file) -> str:
    """Extract plain text from uploaded .txt / .pdf / .docx file."""
    try:
        from services.file_ingest import load_transcript
        return load_transcript(uploaded_file) or ""
    except Exception:
        try:
            return uploaded_file.read().decode("utf-8", errors="replace")
        except Exception:
            return ""


# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_upload, tab_library, tab_extract, tab_analysis, tab_taxonomy = st.tabs([
    "📤 Enviar Documento",
    "📚 Biblioteca",
    "⚗️ Extrair Artefatos",
    "🔍 Análise Cruzada",
    "🏷️ Taxonomia",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — UPLOAD
# ══════════════════════════════════════════════════════════════════════════════

with tab_upload:
    st.subheader("Adicionar documento")
    st.caption(
        "Faça upload de documentos apresentados em reuniões (contratos, requisitos, "
        "especificações, fluxogramas, etc.). O documento será indexado com embeddings "
        "para buscas semânticas e análise cruzada com artefatos de reunião."
    )

    types_by_cat = _cached_types_by_category()
    all_types    = _cached_doc_types()
    meetings     = _list_meetings()

    col_meta, col_source = st.columns([1, 1], gap="large")

    with col_meta:
        doc_title = st.text_input("Título do documento *", placeholder="Ex.: SRS do Módulo de Cadastro v2.1")

        categories = list(types_by_cat.keys())
        category   = st.selectbox("Categoria", categories)
        types_in_cat = types_by_cat.get(category, [])
        doc_type_code = st.selectbox(
            "Tipo de documento *",
            options=[t["code"] for t in types_in_cat],
            format_func=lambda c: next(
                (t["label"] for t in types_in_cat if t["code"] == c), c
            ),
        )
        if types_in_cat:
            selected_type = next((t for t in types_in_cat if t["code"] == doc_type_code), None)
            if selected_type and selected_type.get("description"):
                st.caption(selected_type["description"])

        meeting_options = ["(nenhuma — documento independente)"] + [
            m["id"] for m in meetings
        ]
        meeting_fmt = {m["id"]: f"{m['title']} ({m['created_at'][:10]})" for m in meetings}
        linked_meeting_raw = st.selectbox(
            "Vincular à reunião",
            meeting_options,
            format_func=lambda v: meeting_fmt.get(v, v),
        )
        linked_meeting_id = None if linked_meeting_raw.startswith("(") else linked_meeting_raw

        st.markdown("**Data de referência do documento**")
        _date_col, _est_col = st.columns([1, 1])
        with _date_col:
            doc_date_input = st.date_input(
                "Data exata",
                value=None,
                help="Data de publicação, emissão ou referência do documento.",
            )
        with _est_col:
            doc_date_estimated_input = st.text_input(
                "Data estimada",
                placeholder='Ex.: "Meados de 2023", "Q2 2022"',
                help="Preencha quando a data exata não é conhecida.",
            )

    with col_source:
        input_mode = st.radio(
            "Fonte do conteúdo",
            ["Upload de arquivo", "Colar texto"],
            horizontal=True,
        )
        doc_content = ""
        file_name   = ""

        if input_mode == "Upload de arquivo":
            uploaded = st.file_uploader(
                "Arquivo (.txt, .pdf, .docx)",
                type=["txt", "pdf", "docx"],
                help="O texto será extraído automaticamente.",
            )
            if uploaded:
                file_name   = uploaded.name
                doc_content = _load_file_content(uploaded)
                char_count  = len(doc_content)
                if doc_content:
                    st.success(f"Arquivo carregado — {char_count:,} caracteres")
                    with st.expander("Prévia do texto extraído"):
                        st.text(doc_content[:1500] + ("..." if char_count > 1500 else ""))
                else:
                    st.error("Não foi possível extrair texto. Verifique o arquivo.")
        else:
            doc_content = st.text_area(
                "Conteúdo do documento",
                height=280,
                placeholder="Cole o texto completo aqui...",
            )

    st.divider()
    col_btn, col_status = st.columns([1, 3])
    with col_btn:
        save_btn = st.button("💾 Salvar e indexar", type="primary", use_container_width=True)

    if save_btn:
        if not doc_title.strip():
            st.error("O título é obrigatório.")
        elif not doc_content.strip():
            st.error("O conteúdo do documento está vazio.")
        else:
            user_label = st.session_state.get("username", "")
            with st.spinner("Salvando documento..."):
                doc_id = upload_document(
                    project_id          = project_id,
                    title               = doc_title.strip(),
                    doc_type            = doc_type_code,
                    content_text        = doc_content,
                    file_name           = file_name,
                    meeting_id          = linked_meeting_id,
                    created_by          = user_label,
                    doc_date            = str(doc_date_input) if doc_date_input else None,
                    doc_date_estimated  = doc_date_estimated_input.strip() or None,
                )
            if not doc_id:
                st.error("Erro ao salvar o documento. Verifique a conexão com o banco de dados.")
            else:
                gemini_key = st.session_state.get("google_gemini_key", "")
                if not gemini_key:
                    st.warning(
                        f"Documento salvo (ID: `{doc_id[:8]}...`), mas **embeddings não foram gerados** "
                        "porque a chave Google Gemini não está configurada. "
                        "Configure em Configurações → Google Gemini para habilitar busca semântica."
                    )
                else:
                    with st.spinner("Gerando embeddings (pode demorar alguns segundos)..."):
                        ok = embed_document(doc_id, doc_content)
                    n_chunks = get_chunks_count(doc_id)
                    if ok and n_chunks:
                        st.success(
                            f"Documento salvo e indexado com sucesso!\n\n"
                            f"**ID:** `{doc_id}`  |  **Chunks:** {n_chunks}"
                        )
                    else:
                        st.warning(
                            f"Documento salvo (ID: `{doc_id}`), mas a indexação de embeddings falhou. "
                            "Verifique a chave Google Gemini e tente re-indexar na aba Biblioteca."
                        )
                # Clear caches so Library tab refreshes
                st.cache_data.clear()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — LIBRARY
# ══════════════════════════════════════════════════════════════════════════════

with tab_library:
    st.subheader("Documentos do projeto")

    all_types_flat = _cached_doc_types()
    type_label_map = {t["code"]: t["label"] for t in all_types_flat}

    # ── Search & filter bar ────────────────────────────────────────────────
    col_search, col_mode, col_type = st.columns([3, 1, 2])
    with col_search:
        lib_query = st.text_input("Buscar", placeholder="Palavra-chave ou frase...", label_visibility="collapsed")
    with col_mode:
        lib_mode = st.selectbox("Modo", ["Palavra-chave", "Semântico"], label_visibility="collapsed")
    with col_type:
        all_type_codes = ["(todos)"] + [t["code"] for t in all_types_flat]
        filter_type = st.selectbox(
            "Tipo",
            all_type_codes,
            format_func=lambda c: "Todos os tipos" if c == "(todos)" else type_label_map.get(c, c),
            label_visibility="collapsed",
        )

    # ── Fetch documents ────────────────────────────────────────────────────
    if lib_query:
        if lib_mode == "Semântico":
            raw_results = search_documents_semantic(lib_query, project_id, limit=10)
            # Convert semantic results to document-like dicts
            docs = []
            seen_ids: set[str] = set()
            for r in raw_results:
                if r["document_id"] not in seen_ids:
                    seen_ids.add(r["document_id"])
                    docs.append({
                        "id":         r["document_id"],
                        "title":      r["doc_title"],
                        "doc_type":   r["doc_type"],
                        "file_name":  r.get("doc_file_name", ""),
                        "created_at": "",
                        "_similarity": round(r["similarity"], 3),
                        "_matched_chunk": r["content"][:300],
                    })
        else:
            docs = search_documents_keyword(lib_query, project_id)
    else:
        doc_type_filter = None if filter_type == "(todos)" else filter_type
        docs = list_documents(project_id, doc_type=doc_type_filter)

    if not docs:
        st.info("Nenhum documento encontrado. Use a aba **Enviar Documento** para adicionar.")
    else:
        st.caption(f"{len(docs)} documento(s) encontrado(s)")

        for doc in docs:
            doc_id    = doc["id"]
            doc_label = type_label_map.get(doc.get("doc_type", ""), doc.get("doc_type", "—"))
            date_str  = doc.get("created_at", "")[:10] if doc.get("created_at") else ""
            sim_badge = f" · sim {doc.get('_similarity', '')}" if "_similarity" in doc else ""
            header    = f"**{doc['title']}** · {doc_label} · {date_str}{sim_badge}"

            with st.expander(header):
                col_info, col_actions = st.columns([3, 1])

                with col_info:
                    if doc.get("file_name"):
                        st.caption(f"Arquivo: `{doc['file_name']}`")
                    if doc.get("meeting_id"):
                        st.caption(f"Reunião vinculada: `{doc['meeting_id'][:8]}...`")
                    if doc.get("doc_date"):
                        st.caption(f"Data do documento: {doc['doc_date']}")
                    elif doc.get("doc_date_estimated"):
                        st.caption(f"Data estimada: {doc['doc_date_estimated']}")

                    # Semantic match snippet
                    if "_matched_chunk" in doc:
                        st.markdown("**Trecho correspondente:**")
                        st.text(doc["_matched_chunk"])
                    else:
                        # Show content preview
                        full_content = get_document_content(doc_id)
                        if full_content:
                            st.markdown("**Prévia:**")
                            st.text(full_content[:500] + ("..." if len(full_content) > 500 else ""))
                            n_chunks = get_chunks_count(doc_id)
                            st.caption(f"Tamanho: {len(full_content):,} chars · {n_chunks} chunks indexados")

                with col_actions:
                    if st.button("🗑️ Excluir", key=f"del_{doc_id}", use_container_width=True):
                        if delete_document(doc_id):
                            st.success("Documento excluído.")
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error("Falha ao excluir.")

                    if st.button("♻️ Re-indexar", key=f"reindex_{doc_id}", use_container_width=True,
                                 help="Regenera embeddings para este documento"):
                        full_content = get_document_content(doc_id)
                        if full_content:
                            with st.spinner("Re-indexando..."):
                                ok = embed_document(doc_id, full_content)
                            if ok:
                                n = get_chunks_count(doc_id)
                                st.success(f"{n} chunks indexados.")
                            else:
                                st.error("Falha na indexação.")
                        else:
                            st.error("Conteúdo não encontrado.")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — EXTRACT ARTIFACTS
# ══════════════════════════════════════════════════════════════════════════════

with tab_extract:
    st.subheader("Extrair artefatos de documento")
    st.caption(
        "Leia um documento e extraia automaticamente requisitos, termos SBVR, "
        "regras de negócio, metas BMM, estratégias, políticas e decisões DMN."
    )

    docs_ext = list_documents(project_id)
    if not docs_ext:
        st.info("Nenhum documento disponível. Envie um documento na aba **📤 Enviar Documento**.")
        st.stop()

    # Document selector
    doc_options_ext = {d["title"]: d["id"] for d in docs_ext}
    selected_doc_label_ext = st.selectbox(
        "Documento",
        list(doc_options_ext.keys()),
        key="ext_doc_select",
    )
    selected_doc_id_ext = doc_options_ext[selected_doc_label_ext]

    ext_lang = st.selectbox(
        "Idioma dos artefatos extraídos",
        ["Auto-detect", "Português (Brasil)", "English"],
        index=0,
        key="ext_lang",
    )

    extract_btn = st.button("⚗️ Extrair Artefatos", type="primary", key="ext_btn")

    if extract_btn:
        doc_content_ext = get_document_content(selected_doc_id_ext)
        if not doc_content_ext or not doc_content_ext.strip():
            st.error("O documento selecionado não tem conteúdo armazenado.")
            st.stop()

        with st.spinner("Extraindo artefatos (LLM)... isso pode levar 20–40 segundos."):
            try:
                extractor = _get_extractor()
                extracted = extractor.extract(selected_doc_label_ext, doc_content_ext, ext_lang)
            except Exception as exc:
                extracted = None
                st.error(f"Erro no agente extrator: {exc}")

        if not extracted:
            st.error("A extração não retornou resultado. Verifique a chave da API e tente novamente.")
            st.stop()

        st.session_state["_ext_result"]    = extracted
        st.session_state["_ext_doc_id"]    = selected_doc_id_ext
        st.session_state["_ext_doc_title"] = selected_doc_label_ext

    # ── Preview & Save ─────────────────────────────────────────────────────────
    if st.session_state.get("_ext_result"):
        extracted   = st.session_state["_ext_result"]
        ext_doc_id  = st.session_state["_ext_doc_id"]
        ext_doc_ttl = st.session_state["_ext_doc_title"]

        st.success(f"Extração concluída para: **{ext_doc_ttl}**")
        st.divider()

        # Summary counts
        n_req   = len(extracted.get("requirements", []))
        n_terms = len(extracted.get("sbvr_terms", []))
        n_rules = len(extracted.get("sbvr_rules", []))
        n_goals = len(extracted.get("bmm_goals", []))
        n_strat = len(extracted.get("bmm_strategies", []))
        n_pol   = len(extracted.get("bmm_policies", []))
        n_dmn   = len(extracted.get("dmn_decisions", []))

        cols_kpi = st.columns(7)
        for col, label, val in zip(
            cols_kpi,
            ["Requisitos", "Termos SBVR", "Regras SBVR", "Metas BMM", "Estratégias", "Políticas", "Decisões DMN"],
            [n_req, n_terms, n_rules, n_goals, n_strat, n_pol, n_dmn],
        ):
            col.metric(label, val)

        st.divider()

        # Preview per artifact type
        if n_req:
            with st.expander(f"📋 Requisitos ({n_req})"):
                import pandas as pd
                df_req = pd.DataFrame([
                    {
                        "Título": r.get("title", ""),
                        "Tipo": r.get("req_type", ""),
                        "Prioridade": r.get("priority", ""),
                        "Descrição": r.get("description", ""),
                    }
                    for r in extracted["requirements"]
                ])
                st.dataframe(df_req, use_container_width=True, hide_index=True)

        if n_terms:
            with st.expander(f"📖 Termos SBVR ({n_terms})"):
                import pandas as pd
                df_terms = pd.DataFrame([
                    {"Termo": t.get("term", ""), "Categoria": t.get("category", ""), "Definição": t.get("definition", "")}
                    for t in extracted["sbvr_terms"]
                ])
                st.dataframe(df_terms, use_container_width=True, hide_index=True)

        if n_rules:
            with st.expander(f"⚖️ Regras SBVR ({n_rules})"):
                import pandas as pd
                df_rules = pd.DataFrame([
                    {"ID": r.get("id", ""), "Tipo": r.get("rule_type", ""), "Enunciado": r.get("statement", "")}
                    for r in extracted["sbvr_rules"]
                ])
                st.dataframe(df_rules, use_container_width=True, hide_index=True)

        if n_goals or n_strat or n_pol:
            with st.expander(f"🎯 BMM — Metas / Estratégias / Políticas ({n_goals + n_strat + n_pol})"):
                if n_goals:
                    st.markdown("**Metas**")
                    for g in extracted["bmm_goals"]:
                        st.markdown(f"- **{g.get('id', '')}** {g.get('description', '')}")
                if n_strat:
                    st.markdown("**Estratégias**")
                    for s in extracted["bmm_strategies"]:
                        st.markdown(f"- **{s.get('id', '')}** {s.get('description', '')} _(suporta {s.get('supports', '—')})_")
                if n_pol:
                    st.markdown("**Políticas**")
                    for p in extracted["bmm_policies"]:
                        st.markdown(f"- **{p.get('id', '')}** {p.get('description', '')}")

        if n_dmn:
            with st.expander(f"🔀 Decisões DMN ({n_dmn})"):
                import pandas as pd
                df_dmn = pd.DataFrame([
                    {"ID": d.get("id", ""), "Nome": d.get("name", ""), "Pergunta": d.get("question", ""), "Resultado": d.get("outcome", "")}
                    for d in extracted["dmn_decisions"]
                ])
                st.dataframe(df_dmn, use_container_width=True, hide_index=True)

        st.divider()

        # JSON download
        import json
        st.download_button(
            label="⬇️ Baixar JSON completo",
            data=json.dumps(extracted, ensure_ascii=False, indent=2),
            file_name=f"artefatos_{ext_doc_ttl[:40].replace(' ', '_')}.json",
            mime="application/json",
        )

        # Save to project
        if st.button("💾 Salvar artefatos no projeto", type="primary", key="ext_save_btn"):
            with st.spinner("Salvando no Supabase..."):
                try:
                    from core.project_store import save_artifacts_from_document
                    counts = save_artifacts_from_document(project_id, ext_doc_id, extracted)
                    st.success(
                        f"Salvo: {counts['requirements']} requisitos · "
                        f"{counts['terms']} termos SBVR · "
                        f"{counts['rules']} regras SBVR"
                        + (" · BMM" if counts.get("bmm") else "")
                        + (" · DMN" if counts.get("dmn") else "")
                    )
                    # Clear cached results so button disappears
                    st.session_state.pop("_ext_result", None)
                    st.session_state.pop("_ext_doc_id", None)
                    st.session_state.pop("_ext_doc_title", None)
                    st.rerun()
                except Exception as exc:
                    st.error(f"Erro ao salvar: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — CROSS-REFERENCE ANALYSIS
# ══════════════════════════════════════════════════════════════════════════════

with tab_analysis:
    st.subheader("Análise cruzada: Documento × Reunião")
    st.caption(
        "O agente DocumentAnalyzer lê o documento e os artefatos da reunião (ata, requisitos, BPMN) "
        "e produz um relatório de alinhamento, conflitos, lacunas e recomendações."
    )

    docs_all  = list_documents(project_id, limit=200)
    meetings_all = _list_meetings()

    if not docs_all:
        st.info("Nenhum documento disponível. Faça upload na aba **Enviar Documento**.")
        st.stop()

    if not meetings_all:
        st.info("Nenhuma reunião processada neste projeto. Execute o pipeline primeiro.")
        st.stop()

    col_doc, col_mtg = st.columns(2)
    type_label_map2 = {t["code"]: t["label"] for t in _cached_doc_types()}

    with col_doc:
        selected_doc_id = st.selectbox(
            "Documento",
            [d["id"] for d in docs_all],
            format_func=lambda did: next(
                (f"{d['title']} [{type_label_map2.get(d.get('doc_type',''), d.get('doc_type',''))}]"
                 for d in docs_all if d["id"] == did), did
            ),
        )

    with col_mtg:
        selected_mtg_id = st.selectbox(
            "Reunião",
            [m["id"] for m in meetings_all],
            format_func=lambda mid: next(
                (f"{m['title']} ({m['created_at'][:10]})" for m in meetings_all if m["id"] == mid),
                mid,
            ),
        )

    output_lang = st.selectbox(
        "Idioma do relatório",
        ["Auto-detect", "Português (Brasil)", "English"],
        index=0,
    )

    analyze_btn = st.button("🔬 Analisar", type="primary")

    if analyze_btn:
        # Load document content
        doc_content = get_document_content(selected_doc_id)
        doc_meta    = next((d for d in docs_all if d["id"] == selected_doc_id), {})
        doc_title   = doc_meta.get("title", "Documento")

        if not doc_content or not doc_content.strip():
            st.error("O documento selecionado não tem conteúdo armazenado.")
            st.stop()

        # Load meeting artifacts
        with st.spinner("Carregando artefatos da reunião..."):
            try:
                from core.project_store import load_meeting_as_hub
                hub = load_meeting_as_hub(selected_mtg_id, project_id)
            except Exception as exc:
                hub = None
                st.error(f"Erro ao carregar reunião: {exc}")

        if hub is None:
            st.error("Não foi possível carregar os artefatos desta reunião. Verifique se o pipeline foi executado.")
            st.stop()

        # Run agent
        with st.spinner("Analisando documento (LLM)... isso pode levar 20–30 segundos."):
            try:
                agent  = _get_agent()
                result = agent.analyze(doc_title, doc_content, hub, output_lang)
            except Exception as exc:
                result = None
                st.error(f"Erro no agente: {exc}")

        if not result:
            st.error("A análise não retornou resultado. Verifique a chave da API e tente novamente.")
            st.stop()

        # ── Display results ────────────────────────────────────────────────
        score = result.get("alignment_score", 0)
        color = _score_color(score)

        st.markdown(f"### Relatório de Análise: {doc_title}")
        st.markdown(f"**Reunião:** {next((m['title'] for m in meetings_all if m['id'] == selected_mtg_id), '')}")
        st.divider()

        # Score + summary
        c1, c2 = st.columns([1, 3])
        with c1:
            st.markdown(
                f"<div style='text-align:center;font-size:3rem;font-weight:bold;color:{color};'>"
                f"{score}<span style='font-size:1.5rem;'>/100</span></div>"
                "<div style='text-align:center;color:gray;font-size:0.85rem;'>Score de Alinhamento</div>",
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(f"**Resumo do documento:**\n\n{result.get('document_summary', '—')}")
            temporal = result.get("temporal_analysis", {})
            if temporal:
                st.caption(
                    f"Data estimada: {temporal.get('document_date', '—')} — "
                    f"{temporal.get('notes', '')}"
                )

        st.divider()

        # Key insights + recommendations
        insights = result.get("key_insights", [])
        recs     = result.get("recommendations", [])
        if insights or recs:
            col_i, col_r = st.columns(2)
            with col_i:
                if insights:
                    st.markdown("**Insights Principais**")
                    for item in insights:
                        st.info(item)
            with col_r:
                if recs:
                    st.markdown("**Recomendações**")
                    for item in recs:
                        st.warning(item)

        # Aligned requirements
        aligned_reqs = result.get("aligned_requirements", [])
        conflict_reqs = result.get("conflicting_requirements", [])
        undoc_reqs    = result.get("undocumented_requirements", [])
        if aligned_reqs or conflict_reqs or undoc_reqs:
            st.markdown("#### Requisitos")
            if aligned_reqs:
                with st.expander(f"✅ Alinhados ({len(aligned_reqs)})"):
                    for r in aligned_reqs:
                        st.markdown(
                            f"**{r.get('req_id', '—')}** — {r.get('req_title', '')}\n\n"
                            f"Doc: `{r.get('doc_reference', '—')}`  \n{r.get('alignment_note', '')}"
                        )
                        st.divider()
            if conflict_reqs:
                with st.expander(f"⚡ Conflitantes ({len(conflict_reqs)})"):
                    for r in conflict_reqs:
                        st.markdown(
                            f"**{r.get('req_id', '—')}** — {r.get('req_title', '')}\n\n"
                            f"Doc: `{r.get('doc_reference', '—')}`  \n{r.get('conflict_description', '')}"
                        )
                        st.divider()
            if undoc_reqs:
                with st.expander(f"⬜ Sem cobertura no documento ({len(undoc_reqs)})"):
                    for r in undoc_reqs:
                        st.markdown(f"**{r.get('req_id', '—')}** — {r.get('req_title', '')}  \n{r.get('note', '')}")

        # Process alignment + gaps
        proc_aligned = result.get("process_alignment", [])
        proc_gaps    = result.get("process_gaps", [])
        if proc_aligned or proc_gaps:
            st.markdown("#### Processo BPMN")
            if proc_aligned:
                with st.expander(f"✅ Etapas alinhadas ({len(proc_aligned)})"):
                    for p in proc_aligned:
                        st.markdown(
                            f"**{p.get('bpmn_step', '—')}**  \n"
                            f"Doc: `{p.get('doc_reference', '—')}`  \n{p.get('alignment_note', '')}"
                        )
                        st.divider()
            if proc_gaps:
                with st.expander(f"⚠️ Lacunas identificadas ({len(proc_gaps)})"):
                    for g in proc_gaps:
                        st.markdown(
                            f"**{g.get('gap_description', '—')}**  \n"
                            f"Doc: `{g.get('doc_reference', '—')}`  \n"
                            f"Recomendação: {g.get('recommendation', '')}"
                        )
                        st.divider()

        # Decisions
        decisions = result.get("decisions_referenced", [])
        if decisions:
            with st.expander(f"🔵 Decisões referenciadas ({len(decisions)})"):
                for d in decisions:
                    status_icon = {"confirmed": "✅", "conflicts": "⚡", "new": "🆕", "partial": "🟡"}.get(
                        d.get("status", ""), "•"
                    )
                    st.markdown(
                        f"{status_icon} **{d.get('decision', '—')}**  \n"
                        f"Posição no documento: {d.get('document_position', '—')}"
                    )

        # Implied actions
        implied = result.get("implied_actions", [])
        if implied:
            with st.expander(f"📌 Ações implícitas no documento ({len(implied)})"):
                for a in implied:
                    st.markdown(
                        f"**{a.get('action', '—')}**  \n"
                        f"Responsável: {a.get('responsible', '—')} · "
                        f"Prazo: {a.get('deadline', '—')}"
                    )

        # Stakeholders
        stakeholders = result.get("stakeholders_mentioned", [])
        if stakeholders:
            with st.expander(f"👤 Partes interessadas mencionadas ({len(stakeholders)})"):
                for s in stakeholders:
                    st.markdown(
                        f"**{s.get('name', '—')}** ({s.get('role', '—')})  \n{s.get('context', '')}"
                    )

        # Raw JSON export
        import json
        with st.expander("📥 Exportar resultado (JSON)"):
            report_json = json.dumps(result, ensure_ascii=False, indent=2)
            st.download_button(
                label="⬇️ Download JSON",
                data=report_json,
                file_name=f"analise_{doc_title[:30].replace(' ', '_')}.json",
                mime="application/json",
            )
            st.code(report_json[:2000] + ("..." if len(report_json) > 2000 else ""), language="json")

        # Store result in session for convenience
        st.session_state["last_doc_analysis"] = result


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — TAXONOMY
# ══════════════════════════════════════════════════════════════════════════════

with tab_taxonomy:
    st.subheader("Taxonomia de documentos")
    st.caption(
        "Classificação baseada nas metodologias PMBOK, IEEE 830, OMG BPMN, Scrum / SAFe, "
        "Six Sigma, Lean, BM Canvas e normas ISO."
    )

    types_by_cat = _cached_types_by_category()
    if not types_by_cat:
        st.info("Taxonomia não carregada. Execute a migration SQL em Supabase.")
        st.stop()

    for category, types in types_by_cat.items():
        st.markdown(f"#### {category}")
        rows = [
            {
                "Código": t["code"],
                "Tipo": t["label"],
                "Descrição": t.get("description", ""),
            }
            for t in types
        ]
        import pandas as pd
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            column_config={
                "Código":    st.column_config.TextColumn(width="small"),
                "Tipo":      st.column_config.TextColumn(width="medium"),
                "Descrição": st.column_config.TextColumn(width="large"),
            },
        )
        st.markdown("")
