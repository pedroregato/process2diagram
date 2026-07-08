# ui/tabs/export_tab.py
import json
import streamlit as st
from agents.agent_minutes import AgentMinutes
from agents.agent_mermaid import generate_mermaid
from services.export_service import make_filename

def render(hub, prefix, suffix):
    st.markdown("### 📦 Export Assets")
    if hub.bpmn.ready:
        st.markdown("**Process Models**")
        if hub.bpmn.bpmn_xml:
            st.download_button(
                "⬇️ .bpmn",
                data=hub.bpmn.bpmn_xml,
                file_name=make_filename("process", "bpmn", prefix, suffix),
                key="export_bpmn"
            )
        st.download_button(
            "⬇️ .mermaid",
            data=generate_mermaid(hub.bpmn),
            file_name=make_filename("process", "mmd", prefix, suffix),
            key="export_mermaid"
        )
        st.markdown("---")
    if hub.minutes.ready:
        st.markdown("**Meeting Minutes**")
        md = AgentMinutes.to_markdown(hub.minutes)
        st.download_button(
            "⬇️ .md",
            data=md,
            file_name=make_filename("minutes", "md", prefix, suffix),
            key="export_minutes_md"
        )
        try:
            from modules.minutes_exporter import to_docx, to_pdf
            st.download_button(
                "⬇️ .docx",
                data=to_docx(hub.minutes),
                file_name=make_filename("minutes", "docx", prefix, suffix),
                key="export_minutes_docx"
            )
            st.download_button(
                "⬇️ .pdf",
                data=to_pdf(hub.minutes),
                file_name=make_filename("minutes", "pdf", prefix, suffix),
                key="export_minutes_pdf"
            )
        except Exception:
            pass
        try:
            from modules.minutes_exporter import to_html
            st.download_button(
                "⬇️ .html",
                data=to_html(hub.minutes).encode("utf-8"),
                file_name=make_filename("minutes", "html", prefix, suffix),
                mime="text/html",
                key="export_minutes_html"
            )
        except Exception as _exc:
            st.caption(f"⚠️ Export HTML indisponível: {_exc}")
        verification_md = AgentMinutes.to_verification_report(hub.minutes)
        st.download_button(
            "⬇️ Roteiro de Verificação (.md)",
            data=verification_md,
            file_name=make_filename("verificacao", "md", prefix, suffix),
            key="export_verification_report",
            help="Checklist estruturado para apresentar os artefatos de volta aos participantes e validá-los",
        )
        st.markdown("---")
    if hub.requirements.ready:
        st.markdown("**Requirements**")
        st.download_button(
            "⬇️ .md",
            data=hub.requirements.markdown,
            file_name=make_filename("requirements", "md", prefix, suffix),
            key="export_req_md"
        )
        req_json = json.dumps(
            {"name": hub.requirements.name, "requirements": [r.__dict__ for r in hub.requirements.requirements]},
            ensure_ascii=False, indent=2
        )
        st.download_button(
            "⬇️ .json",
            data=req_json,
            file_name=make_filename("requirements", "json", prefix, suffix),
            key="export_req_json"
        )
        st.markdown("---")

    if getattr(hub, 'dmn', None) and hub.dmn.ready:
        st.markdown("**Decision Tables (DMN)**")
        try:
            from modules.dmn_viewer import dmn_to_xml
            import json as _json
            st.download_button(
                "⬇️ DMN 1.4 (.xml)",
                data=dmn_to_xml(hub.dmn).encode("utf-8"),
                file_name=make_filename("decisions", "dmn", prefix, suffix),
                mime="application/xml",
                key="export_tab_dmn_xml",
            )
            decisions_list = [
                {"id": d.id, "name": d.name, "question": d.question,
                 "rationale": d.rationale, "decided_by": d.decided_by,
                 "rules": [{"inputs": r.inputs, "output": r.output} for r in d.rules]}
                for d in hub.dmn.decisions
            ]
            st.download_button(
                "⬇️ DMN JSON",
                data=_json.dumps({"decisions": decisions_list}, ensure_ascii=False, indent=2),
                file_name=make_filename("decisions", "json", prefix, suffix),
                key="export_tab_dmn_json",
            )
        except Exception:
            pass
        st.markdown("---")

    if getattr(hub, 'argumentation', None) and hub.argumentation.ready:
        import json as _json2, dataclasses
        st.markdown("**Argumentation Map (IBIS)**")
        ibis_data = {"questions": [dataclasses.asdict(q) for q in hub.argumentation.questions]}
        # Build Markdown report
        _res_lbl_ex = {"decided": "✅ Decidida", "deferred": "⏳ Adiada", "unresolved": "❓ Em aberto"}
        _md_lines = [f"# Mapa Argumentativo IBIS\n\n**Total:** {len(hub.argumentation.questions)} questão(ões)\n"]
        for _q in hub.argumentation.questions:
            _qd  = dataclasses.asdict(_q)
            _rq  = _qd.get("resolution") or {}
            _rtq = _rq.get("type", "unresolved")
            _md_lines.append(f"\n## {_qd.get('id','?')} — {_qd.get('statement','')}")
            if _qd.get("raised_by"):
                _md_lines.append(f"\n*Levantada por: {_qd['raised_by']}*  ")
            _md_lines.append(f"**Status:** {_res_lbl_ex.get(_rtq, _rtq)}\n")
            for _alt in _qd.get("alternatives", []):
                _ch = " ✅ *(escolhida)*" if _alt.get("was_chosen") else ""
                _md_lines.append(f"\n### {_alt.get('id','?')}{_ch} — {_alt.get('description','')}")
                if _alt.get("pros"):
                    _md_lines.append("\n**A favor:**")
                    _md_lines.extend(f"- {p}" for p in _alt["pros"])
                if _alt.get("cons"):
                    _md_lines.append("\n**Contra:**")
                    _md_lines.extend(f"- {c}" for c in _alt["cons"])
            if _rq.get("rationale"):
                _md_lines.append(f"\n**Resolução:** {_rq['rationale']}")
            if _rq.get("with_caveats"):
                _md_lines.append("\n**Ressalvas:**")
                _md_lines.extend(f"- {c}" for c in _rq["with_caveats"])
            _md_lines.append("\n---")
        st.download_button(
            "⬇️ IBIS Markdown (.md)",
            data="\n".join(_md_lines),
            file_name=make_filename("argumentation", "md", prefix, suffix),
            key="export_tab_ibis_md",
        )
        st.download_button(
            "⬇️ IBIS JSON",
            data=_json2.dumps(ibis_data, ensure_ascii=False, indent=2),
            file_name=make_filename("argumentation", "json", prefix, suffix),
            key="export_tab_ibis_json",
        )
        st.markdown("---")
    if hub.synthesizer.ready:
        st.markdown("**Executive Report**")
        st.download_button(
            "⬇️ .html",
            data=hub.synthesizer.html,
            file_name=make_filename("executive_report", "html", prefix, suffix),
            key="export_report_html"
        )
        st.markdown("---")

    if getattr(hub, 'query_summary', None) and hub.query_summary.ready:
        st.markdown("**Sumário por Perspectiva**")
        _icons = {"executive": "🏛️", "technical": "⚙️", "project_manager": "📋", "compliance": "⚖️"}
        _lines = []
        for _ps in hub.query_summary.perspectives:
            _icon = _icons.get(_ps.perspective, "📌")
            _lines.append(f"## {_icon} {_ps.label}\n")
            if _ps.headline:
                _lines.append(f"> {_ps.headline}\n")
            if _ps.highlights:
                _lines.append("### Destaques\n" + "\n".join(f"- {h}" for h in _ps.highlights))
            if _ps.open_items:
                _lines.append("### Pontos em aberto\n" + "\n".join(f"- {o}" for o in _ps.open_items))
            if _ps.recommended_actions:
                _lines.append("### Ações recomendadas\n" + "\n".join(f"- {a}" for a in _ps.recommended_actions))
            _lines.append("")
        _qs_md = "\n\n".join(_lines)
        st.download_button(
            "⬇️ Sumário Perspectivas (.md)",
            data=_qs_md,
            file_name=make_filename("summary_perspectives", "md", prefix, suffix),
            key="export_query_summary_md",
        )
