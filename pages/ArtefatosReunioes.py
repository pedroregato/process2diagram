# pages/ArtefatosReunioes.py
# ─────────────────────────────────────────────────────────────────────────────
# Seção Artefatos (PC208) — assunto "Reuniões": Reuniões, Rastreabilidade de
# Origem e Comparação de Reuniões.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
from concurrent.futures import ThreadPoolExecutor as _TPE

from ui.auth_gate import apply_auth_gate
from modules.supabase_client import supabase_configured
from services.export_service import format_date_suffix
from ui.project_selector import require_active_project
from ui.components.artifact_feedback import render_artifact_feedback
from ui.artefatos_shared import (
    inject_artefatos_css, render_artefatos_nav,
    dmn_session_key, ibis_session_key,
    _load_meetings, _load_requirements, _load_sbvr_terms, _load_sbvr_rules,
    _load_bpmn_procs, _load_documents, _load_asset_meta_map,
    make_meet_label, make_doc_label, _origin_badge, make_promote_widget,
)

apply_auth_gate()
inject_artefatos_css()

st.markdown("# 🗓️ Artefatos — Reuniões")

if not supabase_configured():
    st.error("⚙️ Supabase não configurado. Adicione as credenciais em Settings → Secrets.")
    st.stop()

project_id, project_name = require_active_project()
render_artefatos_nav("pages/ArtefatosReunioes.py")

_col_proj, _col_change = st.columns([5, 1])
with _col_proj:
    st.success(f"📁 **Contexto:** {project_name}")
with _col_change:
    st.page_link("pages/Home.py", label="Trocar")

from core.project_store import list_meetings_pii_summary

with _TPE(max_workers=6) as _pool:
    _f_meetings     = _pool.submit(_load_meetings, project_id)
    _f_requirements = _pool.submit(_load_requirements, project_id)
    _f_sbvr_terms   = _pool.submit(_load_sbvr_terms, project_id)
    _f_sbvr_rules   = _pool.submit(_load_sbvr_rules, project_id)
    _f_bpmn_procs   = _pool.submit(_load_bpmn_procs, project_id)
    _f_documents    = _pool.submit(_load_documents, project_id)
    _f_asset_meta   = _pool.submit(_load_asset_meta_map, project_id)
    _f_pii          = _pool.submit(list_meetings_pii_summary, project_id)

    meetings       = _f_meetings.result()
    requirements   = _f_requirements.result()
    sbvr_terms     = _f_sbvr_terms.result()
    sbvr_rules     = _f_sbvr_rules.result()
    bpmn_procs     = _f_bpmn_procs.result()
    documents      = _f_documents.result()
    asset_meta_map = _f_asset_meta.result()
    pii_map        = {p["id"]: p for p in _f_pii.result()}

# 🟢🟡🔴 badge rápido de leitura na listagem + card de detalhe por reunião
# (categoria + contagem, não um score único — ver
# melhorias/parciais/classificador-pii-transcricoes.md). ⚪ = ainda não
# reprocessada desde que a coluna existe, distinto de "risco baixo confirmado".
from modules.compliance import PII_CATEGORY_LABELS as _PII_CATEGORY_LABEL, PII_RISK_BADGE as _PII_BADGE

# DMN/IBIS: leitura somente-leitura do cache de sessão das outras páginas da
# seção (Modelagem Formal / Debates) — a aba Comparar usa as contagens quando
# disponíveis e degrada graciosamente (conta 0) quando ainda não visitadas
# nesta sessão, mesmo comportamento lazy de antes do PC208.
dmn_decisions  = st.session_state.get(dmn_session_key(project_id), None)
ibis_questions = st.session_state.get(ibis_session_key(project_id), None)

meet_map = {m["id"]: m for m in meetings}
doc_map  = {d["id"]: d for d in documents}
meet_label      = make_meet_label(meet_map)
doc_label       = make_doc_label(doc_map)
_promote_widget = make_promote_widget(project_id, asset_meta_map)

st.markdown("---")

tab_meet, tab_trace, tab_comp = st.tabs([
    "🗓️ Reuniões",
    "🔗 Rastreabilidade",
    "🔄 Comparar",
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — REUNIÕES
# ════════════════════════════════════════════════════════════════════════════
with tab_meet:
    st.caption(
        "**Reuniões** — índice de todas as reuniões do projeto com seus artefatos consolidados: "
        "participantes, decisões, itens de ação e resumo executivo. "
        "Use esta aba como ponto de entrada para revisar o conteúdo de uma reunião específica "
        "sem precisar reabrir o pipeline."
    )
    if not meetings:
        st.info("Nenhuma reunião registrada para este projeto.")
    else:
        # PC160 — melhorias/templates-ata-por-contexto.md: modelo de ata
        # ativo do contexto, carregado uma vez para todas as reuniões da
        # aba (não por reunião). Fail-open: None quando não configurado.
        _atatpl_spec = None
        try:
            from core.project_store import get_active_ata_template
            _atatpl_active = get_active_ata_template(project_id)
            if _atatpl_active:
                _atatpl_spec = {
                    "accent_color": (_atatpl_active.get("style_spec") or {}).get("accent_color"),
                    "assets": _atatpl_active.get("assets") or [],
                    "sections": (_atatpl_active.get("style_spec") or {}).get("sections") or [],
                }
        except Exception:
            pass

        for m in meetings:
            num   = m.get("meeting_number", "?")
            title = m.get("title", "")
            dt    = m.get("meeting_date") or "—"
            tok   = m.get("total_tokens") or 0
            prov  = m.get("llm_provider") or "—"
            pii   = pii_map.get(m["id"])
            pii_badge = _PII_BADGE.get(pii["pii_risk_level"], "⚪") if pii else "⚪"

            with st.expander(f"{pii_badge} **Reunião {num}** — {title} · {dt}"):
                c1, c2, c3 = st.columns(3)
                c1.metric("Tokens usados", f"{tok:,}")
                c2.metric("Provedor LLM", prov)
                c3.metric("Data", str(dt))

                st.markdown("---")
                if pii and pii["pii_risk_level"]:
                    _cats = pii["pii_categories"]
                    _breakdown = " · ".join(
                        f"{_PII_CATEGORY_LABEL.get(k, k)}: {v}"
                        for k, v in sorted(_cats.items(), key=lambda kv: -kv[1])
                    ) or "nenhuma categoria"
                    st.markdown(
                        f"**{pii_badge} Dados sensíveis detectados na transcrição:** {_breakdown} "
                        f"— **{pii['pii_total']} informação(ões) sensível(eis) no total**."
                    )
                else:
                    st.caption("⚪ Esta reunião ainda não foi analisada quanto a dados sensíveis (reprocesse pra classificar).")

                reqs_originated = [
                    r for r in requirements
                    if r.get("first_meeting_id") == m["id"]
                ]
                # Aproximação: requisitos cuja última versão foi nesta reunião
                # (sem join de requirement_versions para manter a query leve)
                reqs_touched = [
                    r for r in requirements
                    if r.get("first_meeting_id") != m["id"]
                    and r.get("last_meeting_id") == m["id"]
                ]
                if reqs_originated:
                    st.markdown(f"**{len(reqs_originated)} requisito(s) originado(s) nesta reunião:**")
                    for r in reqs_originated:
                        st.markdown(f"- `REQ-{r['req_number']:03d}` {r.get('title','')}")
                if reqs_touched:
                    st.markdown(f"**{len(reqs_touched)} requisito(s) revisado(s)/confirmado(s) nesta reunião:**")
                    for r in reqs_touched:
                        status = r.get("status", "active")
                        icon = "🔄" if status == "revised" else "⚠️" if status == "contradicted" else "✅"
                        st.markdown(f"- {icon} `REQ-{r['req_number']:03d}` {r.get('title','')}")

                terms_here = [t for t in sbvr_terms if t.get("meeting_id") == m["id"]]
                rules_here = [r for r in sbvr_rules if r.get("meeting_id") == m["id"]]
                if terms_here or rules_here:
                    st.markdown(f"**SBVR:** {len(terms_here)} termo(s) · {len(rules_here)} regra(s)")

                minutes_md = m.get("minutes_md") or ""
                if minutes_md:
                    st.markdown("---")
                    toggle_key = f"_show_minutes_{m['id']}"
                    # PC159: sufixo de data é o da REUNIÃO, não o dia do
                    # download — dá pra identificar de qual reunião é o
                    # arquivo só pelo nome, mesmo baixado meses depois.
                    _date_suffix = format_date_suffix(m.get("meeting_date"))
                    col_btn, col_dl_md, col_dl_docx = st.columns([2, 1, 1])
                    with col_btn:
                        label = "🙈 Ocultar Ata" if st.session_state.get(toggle_key) else "📄 Ver Ata Completa"
                        if st.button(label, key=f"btn_minutes_{m['id']}", use_container_width=True):
                            st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)
                            st.rerun()
                    with col_dl_md:
                        st.download_button(
                            "⬇️ Ata (.md)",
                            data=minutes_md.encode("utf-8"),
                            file_name=f"ata_reuniao_{num}_{_date_suffix}.md",
                            mime="text/markdown",
                            key=f"dl_minutes_{m['id']}",
                            use_container_width=True,
                        )
                    with col_dl_docx:
                        try:
                            from modules.minutes_exporter import to_docx as _minutes_to_docx
                            from core.knowledge_hub import MinutesModel as _MinutesModel
                            _mm = _MinutesModel(
                                title=m.get("title") or f"Reunião {num}",
                                date=str(m.get("meeting_date") or ""),
                                minutes_md=minutes_md,
                                ready=True,
                            )
                            st.download_button(
                                "⬇️ Ata (.docx)",
                                data=_minutes_to_docx(_mm, template_spec=_atatpl_spec),
                                file_name=f"ata_reuniao_{num}_{_date_suffix}.docx",
                                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                key=f"dl_minutes_docx_{m['id']}",
                                use_container_width=True,
                            )
                        except Exception as _exc:
                            st.caption(f"⚠️ Word indisponível: {_exc}")
                    # Slot único e estável: o toggle acima muda entre 0 e 1
                    # elemento aqui a cada rerun — sem um container próprio
                    # isso desalinha a contagem de filhos do expander da
                    # reunião e quebra o frontend com "Bad 'setIn' index"
                    # (mesma causa raiz do PC174, ver CLAUDE.md pitfalls).
                    with st.container():
                        if st.session_state.get(toggle_key):
                            st.markdown(minutes_md)
                    _promote_widget("meeting_minutes", m["id"], f"Ata — Reunião {num} ({dt})")
                    if render_artifact_feedback(
                        project_id, "meeting_minutes", m["id"], key_suffix=m["id"],
                        meeting_id=m["id"],
                        created_by=st.session_state.get("_usuario_login", ""),
                    ):
                        st.rerun()
                else:
                    st.caption("_Ata não disponível para esta reunião._")

# ════════════════════════════════════════════════════════════════════════════
# TAB 10 — RASTREABILIDADE DE ORIGEM
# ════════════════════════════════════════════════════════════════════════════

with tab_trace:
    st.subheader("Matriz de Rastreabilidade de Origem")
    st.caption(
        "Visão consolidada de todos os artefatos com sua fonte de origem: "
        "reunião (transcrição) ou documento. "
        "Use os filtros para localizar artefatos por tipo ou origem."
    )

    # ── Filtros ────────────────────────────────────────────────────────────────
    tf1, tf2 = st.columns(2)
    with tf1:
        sel_trace_tipo = st.selectbox(
            "Tipo de artefato",
            ["Todos", "Requisito", "Termo SBVR", "Regra SBVR"],
            key="trace_tipo",
        )
    with tf2:
        sel_trace_origin = st.selectbox(
            "Origem",
            ["Todas", "Transcrição", "Documento"],
            key="trace_origin",
        )

    # ── Montar linhas da matriz ────────────────────────────────────────────────
    import pandas as pd

    rows = []

    if sel_trace_tipo in ("Todos", "Requisito"):
        for r in requirements:
            orig = r.get("origin", "transcricao")
            if sel_trace_origin == "Transcrição" and orig == "documento":
                continue
            if sel_trace_origin == "Documento" and orig != "documento":
                continue
            num = r.get("req_number", 0)
            if orig == "documento":
                fonte = doc_label(r.get("doc_ref"))
                origem_txt = "📄 Documento"
            else:
                mid = r.get("first_meeting_id")
                fonte = meet_label(mid) if mid else "—"
                origem_txt = "🎙️ Transcrição"
            rows.append({
                "Tipo":    "Requisito",
                "ID":      f"REQ-{num:03d}",
                "Título":  r.get("title", "—"),
                "Origem":  origem_txt,
                "Fonte":   fonte,
                "Status":  r.get("status", "—"),
                "Prio.":   r.get("priority", "—"),
            })

    if sel_trace_tipo in ("Todos", "Termo SBVR"):
        for t in sbvr_terms:
            orig = t.get("origin", "transcricao")
            if sel_trace_origin == "Transcrição" and orig == "documento":
                continue
            if sel_trace_origin == "Documento" and orig != "documento":
                continue
            if orig == "documento":
                fonte = doc_label(t.get("doc_ref"))
                origem_txt = "📄 Documento"
            else:
                meet_info = t.get("meetings") or {}
                m_num = meet_info.get("meeting_number")
                fonte = f"Reunião {m_num}" if m_num else "Assistente"
                origem_txt = "🎙️ Transcrição"
            rows.append({
                "Tipo":    "Termo SBVR",
                "ID":      "—",
                "Título":  t.get("term", "—"),
                "Origem":  origem_txt,
                "Fonte":   fonte,
                "Status":  t.get("category", "—"),
                "Prio.":   "—",
            })

    if sel_trace_tipo in ("Todos", "Regra SBVR"):
        for idx, r in enumerate(sbvr_rules, 1):
            orig = r.get("origin", "transcricao")
            if sel_trace_origin == "Transcrição" and orig == "documento":
                continue
            if sel_trace_origin == "Documento" and orig != "documento":
                continue
            if orig == "documento":
                fonte = doc_label(r.get("doc_ref"))
                origem_txt = "📄 Documento"
            else:
                meet_info = r.get("meetings") or {}
                m_num = meet_info.get("meeting_number")
                fonte = f"Reunião {m_num}" if m_num else "Assistente"
                origem_txt = "🎙️ Transcrição"
            rows.append({
                "Tipo":    "Regra SBVR",
                "ID":      r.get("rule_id") or f"BR-{idx:03d}",
                "Título":  r.get("nucleo_nominal") or r.get("statement", "—")[:80],
                "Origem":  origem_txt,
                "Fonte":   fonte,
                "Status":  r.get("rule_type", "—"),
                "Prio.":   "—",
            })

    if not rows:
        st.info("Nenhum artefato encontrado para os filtros selecionados.")
    else:
        # KPIs de rastreabilidade
        n_doc_rows = sum(1 for row in rows if row["Origem"].startswith("📄"))
        n_tra_rows = len(rows) - n_doc_rows
        tk1, tk2, tk3 = st.columns(3)
        tk1.metric("Total de artefatos", len(rows))
        tk2.metric("🎙️ De transcrições", n_tra_rows)
        tk3.metric("📄 De documentos", n_doc_rows)
        st.markdown("")

        df_trace = pd.DataFrame(rows)
        st.dataframe(
            df_trace,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Tipo":   st.column_config.TextColumn(width="small"),
                "ID":     st.column_config.TextColumn(width="small"),
                "Título": st.column_config.TextColumn(width="large"),
                "Origem": st.column_config.TextColumn(width="medium"),
                "Fonte":  st.column_config.TextColumn(width="large"),
                "Status": st.column_config.TextColumn(width="small"),
                "Prio.":  st.column_config.TextColumn(width="small"),
            },
        )

        # Download CSV
        st.download_button(
            label="⬇️ Exportar CSV",
            data=df_trace.to_csv(index=False).encode("utf-8"),
            file_name=f"rastreabilidade_{project_name.replace(' ', '_')}.csv",
            mime="text/csv",
            key="trace_csv",
        )

# ════════════════════════════════════════════════════════════════════════════
# TAB 13 — COMPARAÇÃO DE REUNIÕES
# ════════════════════════════════════════════════════════════════════════════
with tab_comp:
    st.caption(
        "Compare dois momentos do projeto lado a lado: requisitos, SBVR, BPMN, "
        "decisões DMN e debates IBIS. Os deltas indicam crescimento ou redução entre "
        "a reunião A e a reunião B."
    )

    if len(meetings) < 2:
        st.info("São necessárias ao menos 2 reuniões no projeto para usar a comparação.")
    else:
        _meet_opts = {
            f"Reunião {m.get('meeting_number', '?')} — {m.get('title', '(sem título)')[:50]}": m
            for m in meetings
        }
        _meet_labels = list(_meet_opts.keys())

        _cc1, _cc2 = st.columns(2)
        with _cc1:
            _sel_a = st.selectbox("Reunião A (base)", _meet_labels,
                                  index=0, key="comp_meet_a")
        with _cc2:
            _sel_b = st.selectbox("Reunião B (comparação)", _meet_labels,
                                  index=min(1, len(_meet_labels) - 1), key="comp_meet_b")

        _meet_a = _meet_opts[_sel_a]
        _meet_b = _meet_opts[_sel_b]

        # ── Build per-meeting aggregates from already-loaded data ────────────
        def _comp_stats(m: dict) -> dict:
            mid = m.get("id", "")
            mnum = m.get("meeting_number", 0)
            _reqs  = [r for r in requirements if r.get("meeting_id") == mid]
            _terms = [t for t in sbvr_terms if t.get("meeting_id") == mid]
            _rules = [r for r in sbvr_rules if r.get("meeting_id") == mid]
            _procs = [p for p in bpmn_procs
                      if p.get("first_meeting_id") == mid or str(mnum) in str(p.get("meeting_numbers", ""))]
            # DMN and IBIS counts (only if loaded)
            _dmn_n = sum(1 for d in (dmn_decisions or []) if d.get("_meeting_id") == mid)
            _ibis_n = sum(1 for q in (ibis_questions or []) if q.get("_meeting_id") == mid)
            # Minutes sections
            mins_md = m.get("minutes_md") or ""
            import re as _re
            _decisions = [ln.strip() for ln in _re.sub(r'##\s*\w[^\n]*\n', '\n', mins_md).splitlines()
                          if ln.strip().startswith(("-", "*", "•"))] if mins_md else []
            _decisions_sec = _re.search(r'##\s*Decis[oõ]es[^\n]*\n([\s\S]*?)(?=\n##|\Z)', mins_md, _re.I)
            n_dec = len(_decisions_sec.group(1).strip().splitlines()) if _decisions_sec else 0
            _actions_sec = _re.search(r'##\s*(Itens de A[çc][aã]o|Action Items|A[çc][oõ]es)[^\n]*\n([\s\S]*?)(?=\n##|\Z)', mins_md, _re.I)
            n_act = len([ln for ln in (_actions_sec.group(2).splitlines() if _actions_sec else []) if ln.strip()]) if _actions_sec else 0
            return {
                "reqs": len(_reqs), "terms": len(_terms), "rules": len(_rules),
                "procs": len(_procs), "dmn": _dmn_n, "ibis": _ibis_n,
                "decisions": n_dec, "actions": n_act,
            }

        _sa = _comp_stats(_meet_a)
        _sb = _comp_stats(_meet_b)

        def _delta_icon(va: int, vb: int) -> str:
            if vb > va:   return f"<span style='color:#34d399'>▲ +{vb-va}</span>"
            if vb < va:   return f"<span style='color:#f87171'>▼ -{va-vb}</span>"
            return "<span style='color:#64748b'>= 0</span>"

        _METRICS = [
            ("📝 Requisitos",      "reqs"),
            ("📖 Termos SBVR",     "terms"),
            ("📏 Regras SBVR",     "rules"),
            ("📐 Processos BPMN",  "procs"),
            ("⚖️ Decisões DMN",    "dmn"),
            ("🗺️ Debates IBIS",    "ibis"),
            ("✅ Decisões (ata)",  "decisions"),
            ("📋 Encaminhamentos", "actions"),
        ]

        _rows_html = ""
        for _lbl, _key in _METRICS:
            _va, _vb = _sa[_key], _sb[_key]
            _rows_html += (
                f"<tr>"
                f"<td style='padding:6px 12px;color:#94a3b8;font-size:.82rem'>{_lbl}</td>"
                f"<td style='padding:6px 12px;text-align:center;font-weight:700;color:#f1f5f9'>{_va}</td>"
                f"<td style='padding:6px 12px;text-align:center;font-weight:700;color:#f1f5f9'>{_vb}</td>"
                f"<td style='padding:6px 12px;text-align:center'>{_delta_icon(_va, _vb)}</td>"
                f"</tr>"
            )

        _tit_a = _meet_a.get("title", "")[:32] or _sel_a.split("—")[0].strip()
        _tit_b = _meet_b.get("title", "")[:32] or _sel_b.split("—")[0].strip()
        _date_a = _meet_a.get("meeting_date", "—")
        _date_b = _meet_b.get("meeting_date", "—")

        st.markdown(f"""
<table style="width:100%;border-collapse:collapse;background:#0A1A32;border-radius:10px;overflow:hidden">
  <thead>
    <tr style="background:#0d2244;border-bottom:2px solid #1e3a55">
      <th style="padding:10px 12px;text-align:left;color:#C97B1A;font-size:.78rem;letter-spacing:.08em">MÉTRICA</th>
      <th style="padding:10px 12px;text-align:center;color:#60a5fa;font-size:.78rem">
        🅰 {_tit_a}<br><span style="font-weight:400;color:#475569;font-size:.72rem">{_date_a}</span>
      </th>
      <th style="padding:10px 12px;text-align:center;color:#a78bfa;font-size:.78rem">
        🅱 {_tit_b}<br><span style="font-weight:400;color:#475569;font-size:.72rem">{_date_b}</span>
      </th>
      <th style="padding:10px 12px;text-align:center;color:#94a3b8;font-size:.78rem">DELTA B-A</th>
    </tr>
  </thead>
  <tbody>{_rows_html}</tbody>
</table>
""", unsafe_allow_html=True)

        # ── Plotly radar ──────────────────────────────────────────────────────
        try:
            import plotly.graph_objects as go
            _radar_keys   = ["reqs", "terms", "rules", "procs", "dmn", "ibis"]
            _radar_labels = ["Requisitos", "Termos SBVR", "Regras SBVR", "BPMN", "DMN", "IBIS"]
            _max_vals = [max(1, max(_sa[k], _sb[k])) for k in _radar_keys]
            _norm_a = [_sa[k] / _max_vals[i] * 10 for i, k in enumerate(_radar_keys)]
            _norm_b = [_sb[k] / _max_vals[i] * 10 for i, k in enumerate(_radar_keys)]

            _fig_radar = go.Figure()
            _fig_radar.add_trace(go.Scatterpolar(
                r=_norm_a + [_norm_a[0]], theta=_radar_labels + [_radar_labels[0]],
                fill="toself", name=f"A: {_tit_a}",
                line=dict(color="#60a5fa", width=2), fillcolor="rgba(96,165,250,0.12)",
            ))
            _fig_radar.add_trace(go.Scatterpolar(
                r=_norm_b + [_norm_b[0]], theta=_radar_labels + [_radar_labels[0]],
                fill="toself", name=f"B: {_tit_b}",
                line=dict(color="#a78bfa", width=2), fillcolor="rgba(167,139,250,0.12)",
            ))
            _fig_radar.update_layout(
                polar=dict(
                    bgcolor="#0A1A32",
                    angularaxis=dict(color="#64748b", linecolor="#1e3a55"),
                    radialaxis=dict(visible=True, range=[0, 10], color="#64748b",
                                   gridcolor="#1e3a55", showticklabels=False),
                ),
                paper_bgcolor="#0d1b2a", plot_bgcolor="#0d1b2a",
                font=dict(color="#94a3b8", size=11),
                legend=dict(bgcolor="#0A1A32", bordercolor="#1e3a55",
                            font=dict(color="#94a3b8")),
                margin=dict(t=30, b=20, l=30, r=30),
                height=340,
            )
            st.plotly_chart(_fig_radar, use_container_width=True, key="comp_radar")
        except Exception:
            pass  # plotly não disponível — tabela já exibe os dados
