# ui/tabs/minutes_tab.py
import streamlit as st
from agents.agent_minutes import AgentMinutes
from services.export_service import make_filename

def render(hub, prefix, suffix):
    from ui.components.quality_badge import render_quality_badge
    _c1, _c2 = st.columns([8, 2])
    _c1.markdown("### 📝 Ata da Reunião")
    with _c2:
        render_quality_badge(hub, "minutes")
    m = hub.minutes

    # When loaded from DB, structured fields may be empty — render raw markdown
    _has_structured = bool(m.decisions or m.action_items or m.participants or m.summary)
    if not _has_structured and getattr(m, "minutes_md", ""):
        st.markdown(m.minutes_md)
        st.markdown("---")
        st.markdown("### Export")
        _md = m.minutes_md
        st.download_button(
            "⬇️ .md", data=_md,
            file_name=make_filename("minutes", "md", prefix, suffix),
            key="minutes_md_raw",
        )
        try:
            from modules.minutes_exporter import to_html
            st.download_button(
                "⬇️ .html",
                data=to_html(m).encode("utf-8"),
                file_name=make_filename("minutes", "html", prefix, suffix),
                mime="text/html",
                key="minutes_html_raw",
            )
        except Exception as _exc:
            st.caption(f"⚠️ Export HTML indisponível: {_exc}")
        return

    st.markdown(f"## {m.title}")
    col1, col2, col3 = st.columns(3)
    col1.markdown(f"**Date:** {m.date or 'N/A'}")
    col2.markdown(f"**Location:** {m.location or 'N/A'}")
    col3.markdown(f"**Participants:** {len(m.participants)}")
    if m.agenda:
        st.markdown("### Agenda")
        for i, item in enumerate(m.agenda, 1):
            st.markdown(f"{i}. {item}")
    if m.summary:
        st.markdown("### Summary")
        for block in m.summary:
            st.markdown(f"**{block.get('topic','')}**")
            st.markdown(block.get("content",""))
    if m.decisions:
        st.markdown("### Decisions")
        for d in m.decisions:
            st.markdown(f"- {d}")
    if m.action_items:
        st.markdown("### Action Items")
        rows = []
        for ai in m.action_items:
            rows.append({
                "Priority": ai.priority,
                "Task": ai.task,
                "Owner": ai.responsible,
                "Deadline": ai.deadline or "—"
            })
        st.dataframe(rows, use_container_width=True)
    # ── BABOK fields ──────────────────────────────────────────────────────────
    _babok_fields = [
        (getattr(m, "assumptions", []),       "Premissas (Assumptions)"),
        (getattr(m, "risks_identified", []),  "Riscos Identificados"),
        (getattr(m, "dependencies", []),      "Dependencias"),
        (getattr(m, "open_questions", []),    "Questoes em Aberto"),
        (getattr(m, "stakeholder_needs", []), "Necessidades dos Stakeholders"),
    ]
    _has_babok = any(lst for lst, _ in _babok_fields)
    if _has_babok:
        with st.expander("Analise BABOK", expanded=False):
            st.caption(
                "Campos extraidos com base no BABOK Guide v3 — Elicitation & Collaboration. "
                "Captura premissas, riscos, dependencias, questoes abertas e necessidades dos stakeholders."
            )
            cols = st.columns(2)
            for i, (lst, label) in enumerate(_babok_fields):
                if lst:
                    with cols[i % 2]:
                        st.markdown(f"**{label}**")
                        for item in lst:
                            st.markdown(f"- {item}")

    st.markdown("---")

    # ── ATA Engine HTML interativo ────────────────────────────────────────────
    ata_html = getattr(m, "ata_html", "")
    ata_err  = getattr(m, "ata_html_error", "")
    if ata_html:
        with st.expander("Ata Interativa — ATA Engine", expanded=True):
            st.caption(
                "HTML standalone com chips por participante, tabela de pendencias "
                "editavel, persistencia local e exportacao encadeavel (file://)."
            )
            st.download_button(
                label="Baixar HTML Interativo",
                data=ata_html.encode("utf-8"),
                file_name=make_filename("ATA", "html", prefix, suffix),
                mime="text/html",
                key="dl_ata_html",
            )
    elif ata_err:
        st.warning(f"Nao foi possivel gerar a ata interativa: {ata_err}")
    elif _has_structured:
        # PC155: sem HTML salvo (reunião antiga sem a coluna preenchida, ou
        # ata_html ficou desatualizado após um rerun do agente de Ata) mas
        # os campos estruturados estão presentes no hub — regeneração manual
        # é possível (ATA Engine é puro Python, sem chamada de LLM).
        st.caption("Ata Interativa ainda não gerada para esta versão da ata.")
        if st.button("🔄 Gerar Ata Interativa", key="btn_regen_ata_html"):
            try:
                from modules.ata_engine_generator import generate_ata_html
                from datetime import date as _d
                _mtg_date = _d.today()
                if m.date:
                    try:
                        _mtg_date = _d.fromisoformat(str(m.date)[:10])
                    except ValueError:
                        pass
                _slug = (prefix or "p2d_").rstrip("_").lower() or "p2d"
                m.ata_html = generate_ata_html(
                    minutes      = m,
                    project_id   = st.session_state.get("project_id", ""),
                    meeting_id   = st.session_state.get("current_meeting_id", ""),
                    project_slug = _slug,
                    meeting_date = _mtg_date,
                    local        = m.location or "Videoconferência",
                )
                m.ata_html_error = ""
                st.session_state["hub"] = hub
                _mid = st.session_state.get("current_meeting_id", "")
                if _mid:
                    try:
                        from core.project_store import save_meeting_artifacts
                        save_meeting_artifacts(_mid, hub)
                    except Exception:
                        pass  # regenerado na tela mesmo se o save falhar
                st.rerun()
            except Exception as _exc:
                st.error(f"Falha ao gerar a ata interativa: {_exc}")

    st.markdown("### Export Minutes")
    md_content = AgentMinutes.to_markdown(m)
    
    # Dentro da função render, substitua os st.download_button
    st.download_button(
        "⬇️ .md",
        data=md_content,
        file_name=make_filename("minutes", "md", prefix, suffix),
        key="minutes_md"
    )
    try:
        from modules.minutes_exporter import to_docx
        st.download_button(
            "⬇️ .docx",
            data=to_docx(m),
            file_name=make_filename("minutes", "docx", prefix, suffix),
            key="minutes_docx"
        )
    except Exception:
        pass
    try:
        from modules.minutes_exporter import to_pdf
        st.download_button(
            "⬇️ .pdf",
            data=to_pdf(m),
            file_name=make_filename("minutes", "pdf", prefix, suffix),
            key="minutes_pdf"
        )
    except Exception:
        pass
    try:
        from modules.minutes_exporter import to_html
        st.download_button(
            "⬇️ .html",
            data=to_html(m).encode("utf-8"),
            file_name=make_filename("minutes", "html", prefix, suffix),
            mime="text/html",
            key="minutes_html"
        )
    except Exception as _exc:
        st.caption(f"⚠️ Export HTML indisponível: {_exc}")
