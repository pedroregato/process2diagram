# pages/EntityRecognition.py
# ─────────────────────────────────────────────────────────────────────────────
# Reconhecimento de Entidades — extrai e cataloga pessoas, áreas, unidades
# organizacionais e cargos mencionados nas transcrições de reuniões.
#
# Fluxo:
#   1. Seleciona projeto
#   2. Tab Extração  — seleciona reuniões e executa NER (spaCy + regex + dicionário)
#   3. Tab Entidades — visualiza e filtra entidades extraídas
#   4. Tab Dicionário — gerencia entidades conhecidas do projeto
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import pandas as pd
import streamlit as st

from ui.auth_gate import apply_auth_gate
from modules.supabase_client import supabase_configured, get_supabase_client
from core.project_store import list_projects

apply_auth_gate()

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("# 🔍 Reconhecimento de Entidades")
st.caption(
    "Identifica automaticamente pessoas, áreas, unidades organizacionais e cargos "
    "mencionados nas transcrições de reuniões usando spaCy + padrões linguísticos + dicionário."
)

if not supabase_configured():
    st.error("⚙️ Supabase não configurado.")
    st.stop()

db = get_supabase_client()
if not db:
    st.error("Não foi possível conectar ao Supabase.")
    st.stop()

# ── Verificar se as tabelas existem ──────────────────────────────────────────
def _entities_tables_exist() -> bool:
    try:
        db.table("meeting_entities").select("id").limit(1).execute()
        db.table("entity_dictionary").select("id").limit(1).execute()
        return True
    except Exception:
        return False

if not _entities_tables_exist():
    st.error("⚠️ Tabelas de entidades ainda não foram criadas no banco de dados.")
    st.info(
        "Execute `setup/supabase_schema_entities.sql` no SQL Editor do Supabase "
        "e recarregue a página (F5)."
    )
    st.stop()

# ── Projeto ───────────────────────────────────────────────────────────────────
projects = list_projects()
if not projects:
    st.warning("Nenhum projeto encontrado no banco de dados.")
    st.stop()

proj_map        = {p["name"]: p for p in projects}
sel_proj        = st.selectbox("Projeto", list(proj_map.keys()), key="er_proj")
project_id: str = proj_map[sel_proj]["id"]

st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_extract, tab_view, tab_dict = st.tabs([
    "📊 Extração",
    "🔍 Entidades",
    "📚 Dicionário",
])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Extração
# ─────────────────────────────────────────────────────────────────────────────
with tab_extract:
    st.markdown("## 1️⃣ Reuniões")

    try:
        all_meetings = (
            db.table("meetings")
            .select("id, meeting_number, title, meeting_date, transcript_clean, transcript_raw")
            .eq("project_id", project_id)
            .order("meeting_number")
            .execute()
            .data or []
        )
    except Exception as e:
        st.error(f"Erro ao carregar reuniões: {e}")
        st.stop()

    # Verificar quais já têm entidades
    try:
        existing_ids = {
            row["meeting_id"]
            for row in (
                db.table("meeting_entities")
                .select("meeting_id")
                .eq("project_id", project_id)
                .execute()
                .data or []
            )
        }
    except Exception:
        existing_ids = set()

    with_transcript = [
        m for m in all_meetings
        if (m.get("transcript_clean") or m.get("transcript_raw") or "").strip()
    ]

    if not with_transcript:
        st.warning("Nenhuma reunião com transcrição neste projeto.")
        st.stop()

    n_with_entities    = sum(1 for m in with_transcript if m["id"] in existing_ids)
    n_without_entities = len(with_transcript) - n_with_entities

    col1, col2, col3 = st.columns(3)
    col1.metric("📋 Total com transcrição", len(with_transcript))
    col2.metric("✅ Já extraídas",           n_with_entities)
    col3.metric("🆕 Sem extração",           n_without_entities)

    # Tabela de preview
    preview_rows = []
    for m in with_transcript:
        transcript = m.get("transcript_clean") or m.get("transcript_raw") or ""
        preview_rows.append({
            "Nº":        m.get("meeting_number") or "—",
            "Título":    m.get("title") or "(sem título)",
            "Data":      str(m.get("meeting_date") or "—"),
            "Entidades": "✅ extraídas" if m["id"] in existing_ids else "🆕 pendente",
            "Chars":     f"{len(transcript):,}",
        })

    st.dataframe(
        pd.DataFrame(preview_rows),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")
    st.markdown("## 2️⃣ Seleção")

    all_labels = [
        f"#{m.get('meeting_number','?')} — {m.get('title','(sem título)')} ({m.get('meeting_date','—')})"
        for m in with_transcript
    ]

    _filter_mode = st.radio(
        "Filtrar reuniões",
        ["Todas", "Apenas sem extração", "Selecionar manualmente"],
        horizontal=True,
        key="er_filter",
    )

    if _filter_mode == "Todas":
        selected_meetings = with_transcript
    elif _filter_mode == "Apenas sem extração":
        selected_meetings = [m for m in with_transcript if m["id"] not in existing_ids]
        if not selected_meetings:
            st.info("✅ Todas as reuniões já possuem entidades extraídas.")
            selected_meetings = []
    else:
        selected_labels = st.multiselect(
            "Reuniões a processar",
            options=all_labels,
            default=all_labels,
            key="er_sel",
        )
        label_to_meeting = dict(zip(all_labels, with_transcript))
        selected_meetings = [label_to_meeting[lbl] for lbl in selected_labels if lbl in label_to_meeting]

    if not selected_meetings:
        st.warning("Nenhuma reunião selecionada.")
        st.stop()

    st.markdown(f"**{len(selected_meetings)} reunião(ões) selecionada(s)**")

    st.markdown("---")
    st.markdown("## 3️⃣ Execução")

    if st.button(
        f"▶️ Extrair entidades de {len(selected_meetings)} reunião(ões)",
        type="primary",
        key="er_run",
    ):
        from modules.ner_extractor import EntityRecognizer, save_entities

        # Carrega dicionário uma única vez para o projeto
        rec = EntityRecognizer()
        n_dict = rec.load_dictionary(project_id)

        progress_bar = st.progress(0.0)
        status_area  = st.empty()
        total        = len(selected_meetings)
        results: list[dict] = []

        for i, meeting in enumerate(selected_meetings):
            mid   = meeting["id"]
            title = meeting.get("title") or "(sem título)"
            num   = meeting.get("meeting_number") or "?"
            transcript = (
                meeting.get("transcript_clean") or
                meeting.get("transcript_raw") or ""
            )

            status_area.info(f"⏳ **{i + 1}/{total}** — Reunião {num}: `{title}`")

            try:
                entities = rec.extract(transcript)
                n_saved, err = save_entities(mid, project_id, entities)

                by_type = {}
                for e in entities:
                    by_type[e["type"]] = by_type.get(e["type"], 0) + 1

                results.append({
                    "Nº":        num,
                    "Título":    title,
                    "Status":    "✅ OK" if not err else f"⚠️ {err[:60]}",
                    "Total":     n_saved,
                    "Pessoas":   by_type.get("PESSOA", 0),
                    "Áreas":     by_type.get("AREA", 0),
                    "Unidades":  by_type.get("UNIDADE", 0),
                    "Cargos":    by_type.get("CARGO", 0),
                })

            except Exception as exc:
                results.append({
                    "Nº":       num,
                    "Título":   title,
                    "Status":   f"❌ {str(exc)[:80]}",
                    "Total":    0,
                    "Pessoas":  0,
                    "Áreas":    0,
                    "Unidades": 0,
                    "Cargos":   0,
                })

            progress_bar.progress((i + 1) / total)

        status_area.empty()
        st.markdown("### Resultado")

        n_ok  = sum(1 for r in results if r["Status"].startswith("✅"))
        n_err = len(results) - n_ok
        total_ent = sum(r["Total"] for r in results)

        c1, c2, c3 = st.columns(3)
        c1.metric("✅ Reuniões processadas", n_ok)
        c2.metric("❌ Erros",               n_err)
        c3.metric("🔍 Entidades salvas",    total_ent)
        if n_dict:
            st.caption(f"ℹ️ Dicionário do projeto: {n_dict} entidade(s) conhecida(s) usadas na extração.")

        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)

        if n_ok:
            st.success("💡 Entidades salvas. Acesse a aba **🔍 Entidades** para visualizar.")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Visualização de entidades
# ─────────────────────────────────────────────────────────────────────────────
with tab_view:
    st.markdown("## 🔍 Entidades Extraídas")

    # Filtros
    col_type, col_src, col_search = st.columns([2, 2, 3])
    with col_type:
        filter_type = st.selectbox(
            "Tipo",
            ["TODOS", "PESSOA", "AREA", "UNIDADE", "CARGO"],
            key="er_vtype",
        )
    with col_src:
        filter_src = st.selectbox(
            "Fonte",
            ["TODAS", "spacy", "regex", "dictionary"],
            key="er_vsrc",
        )
    with col_search:
        search_text = st.text_input(
            "Buscar por texto",
            placeholder="João Silva…",
            key="er_vsearch",
        )

    if st.button("🔄 Carregar entidades", key="er_vload"):
        try:
            q = (
                db.table("meeting_entities")
                .select(
                    "entity_text, entity_type, normalized_name, confidence_score, "
                    "source, context, meeting_id"
                )
                .eq("project_id", project_id)
                .order("entity_type")
                .limit(500)
            )
            if filter_type != "TODOS":
                q = q.eq("entity_type", filter_type)
            if filter_src != "TODAS":
                q = q.eq("source", filter_src)

            rows = q.execute().data or []

            if search_text.strip():
                rows = [
                    r for r in rows
                    if search_text.lower() in (r.get("entity_text") or "").lower()
                    or search_text.lower() in (r.get("normalized_name") or "").lower()
                ]

            st.session_state["er_view_rows"] = rows
        except Exception as e:
            st.error(f"Erro ao carregar entidades: {e}")

    rows = st.session_state.get("er_view_rows")
    if rows is not None:
        if not rows:
            st.info("Nenhuma entidade encontrada com os filtros selecionados.")
        else:
            df = pd.DataFrame([{
                "Tipo":       r.get("entity_type", ""),
                "Entidade":   r.get("entity_text", ""),
                "Normalizado":r.get("normalized_name", ""),
                "Confiança":  round(r.get("confidence_score") or 0, 2),
                "Fonte":      r.get("source", ""),
                "Contexto":   (r.get("context") or "")[:120],
            } for r in rows])

            st.caption(f"**{len(df)} entidade(s)** encontrada(s)")
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Gráfico de distribuição por tipo
            if len(df) > 0:
                st.markdown("### Distribuição por tipo")
                dist = df["Tipo"].value_counts().reset_index()
                dist.columns = ["Tipo", "Quantidade"]
                st.bar_chart(dist.set_index("Tipo"))

            # Download CSV
            csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "⬇️ Baixar CSV",
                data=csv_bytes,
                file_name=f"entidades_{sel_proj.replace(' ', '_')}.csv",
                mime="text/csv",
                key="er_csv",
            )
    else:
        st.info("Clique em **🔄 Carregar entidades** para visualizar.")


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Dicionário de entidades conhecidas
# ─────────────────────────────────────────────────────────────────────────────
with tab_dict:
    st.markdown("## 📚 Dicionário do Projeto")
    st.caption(
        "Entidades cadastradas aqui são reconhecidas com alta confiança (0.95) "
        "na próxima extração. Use para nomes de pessoas, áreas e unidades específicas "
        "do seu contexto."
    )

    # Formulário de adição
    with st.expander("➕ Adicionar entidade ao dicionário", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            new_text  = st.text_input("Nome da entidade",   key="er_dnew_text",
                                       placeholder="Ex: Auditoria Interna")
            new_type  = st.selectbox("Tipo",
                                      ["PESSOA", "AREA", "UNIDADE", "CARGO"],
                                      key="er_dnew_type")
        with col2:
            new_norm  = st.text_input("Nome normalizado (opcional)",
                                       key="er_dnew_norm",
                                       placeholder="Ex: AUDITORIA INTERNA")
            new_cat   = st.selectbox("Categoria",
                                      ["INTERNO", "EXTERNO", "CLIENTE", "FORNECEDOR"],
                                      key="er_dnew_cat")

        if st.button("💾 Salvar no dicionário", key="er_dsave"):
            if not new_text.strip():
                st.error("Informe o nome da entidade.")
            else:
                from modules.ner_extractor import normalize_entity
                norm_final = new_norm.strip().upper() if new_norm.strip() \
                    else normalize_entity(new_text.strip(), new_type)
                try:
                    db.table("entity_dictionary").upsert(
                        {
                            "project_id":      project_id,
                            "entity_text":     new_text.strip(),
                            "normalized_name": norm_final,
                            "entity_type":     new_type,
                            "category":        new_cat,
                        },
                        on_conflict="project_id,entity_text,entity_type",
                    ).execute()
                    st.success(f"✅ `{new_text.strip()}` salvo como {new_type}.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Erro ao salvar: {exc}")

    # Listar entidades do dicionário
    st.markdown("### Entidades cadastradas")

    try:
        dict_rows = (
            db.table("entity_dictionary")
            .select("id, entity_text, entity_type, normalized_name, category, created_at")
            .eq("project_id", project_id)
            .order("entity_type")
            .execute()
            .data or []
        )
    except Exception as e:
        st.error(f"Erro ao carregar dicionário: {e}")
        dict_rows = []

    if not dict_rows:
        st.info(
            "Dicionário vazio. Adicione entidades conhecidas do projeto para melhorar "
            "a precisão da extração."
        )
    else:
        filter_dict_type = st.selectbox(
            "Filtrar por tipo",
            ["TODOS", "PESSOA", "AREA", "UNIDADE", "CARGO"],
            key="er_dtype",
        )

        shown = dict_rows if filter_dict_type == "TODOS" else [
            r for r in dict_rows if r["entity_type"] == filter_dict_type
        ]

        df_dict = pd.DataFrame([{
            "Tipo":       r.get("entity_type", ""),
            "Entidade":   r.get("entity_text", ""),
            "Normalizado":r.get("normalized_name", ""),
            "Categoria":  r.get("category", ""),
            "ID":         r.get("id", ""),
        } for r in shown])

        st.caption(f"**{len(df_dict)} entidade(s)** no dicionário")
        st.dataframe(
            df_dict[["Tipo", "Entidade", "Normalizado", "Categoria"]],
            use_container_width=True,
            hide_index=True,
        )

        # Exclusão individual
        with st.expander("🗑️ Remover entidade do dicionário"):
            del_text = st.selectbox(
                "Entidade a remover",
                options=[""] + [r["entity_text"] for r in shown],
                key="er_ddel_sel",
            )
            if del_text and st.button("Remover", key="er_ddel_btn", type="secondary"):
                try:
                    db.table("entity_dictionary") \
                        .delete() \
                        .eq("project_id", project_id) \
                        .eq("entity_text", del_text) \
                        .execute()
                    st.success(f"✅ `{del_text}` removida do dicionário.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Erro ao remover: {exc}")
