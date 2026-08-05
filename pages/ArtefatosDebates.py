# pages/ArtefatosDebates.py
# ─────────────────────────────────────────────────────────────────────────────
# Seção Artefatos (PC208) — assunto "Debates (IBIS)": única aba original que
# virou página própria sozinha — feature coesa de ~1160 linhas (métricas,
# evolução temporal, força de argumentos, filtros, exportação MD, lista + mapa
# visual pyvis) sem dependentes externos.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import sys
from pathlib import Path

root_dir = Path(__file__).parent.parent.absolute()
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st

from ui.auth_gate import apply_auth_gate
from modules.supabase_client import supabase_configured
from ui.project_selector import require_active_project
from ui.artefatos_shared import (
    inject_artefatos_css, render_artefatos_nav, ibis_session_key,
    _load_meetings, _load_argumentation,
    make_meet_label,
)

apply_auth_gate()
inject_artefatos_css()

st.markdown("# 🗺️ Artefatos — Debates (IBIS)")

if not supabase_configured():
    st.error("⚙️ Supabase não configurado. Adicione as credenciais em Settings → Secrets.")
    st.stop()

project_id, project_name = require_active_project()
render_artefatos_nav("pages/ArtefatosDebates.py")

_col_proj, _col_change = st.columns([5, 1])
with _col_proj:
    st.success(f"📁 **Contexto:** {project_name}")
with _col_change:
    st.page_link("pages/Home.py", label="Trocar")

meetings = _load_meetings(project_id)
meet_map = {m["id"]: m for m in meetings}
meet_label = make_meet_label(meet_map)

# IBIS: lê do session_state se já carregado nesta sessão. None = ainda não
# carregado (primeira visita). [] = carregado, sem dados.
_IBIS_SS = ibis_session_key(project_id)
ibis_questions = st.session_state.get(_IBIS_SS, None)

st.markdown("---")

# Assunto único nesta página — st.container() no lugar de st.tabs() evita uma
# barra de aba única sem sentido, preservando a indentação `with tab_ibis:`
# do corpo original movido de pages/Artefatos.py (zero risco de dedent numa
# seção com HTML/JS embutido sensível a espaçamento).
tab_ibis = st.container()

# ════════════════════════════════════════════════════════════════════════════
# TAB 9 — IBIS / ARGUMENTAÇÃO
# ════════════════════════════════════════════════════════════════════════════
_RESOLUTION_BADGE = {
    "decided":    ("ibis-badge-decided",    "✅ Decidida"),
    "deferred":   ("ibis-badge-deferred",   "⏳ Adiada"),
    "unresolved": ("ibis-badge-unresolved", "❓ Em aberto"),
}

with tab_ibis:
    st.caption(
        "**IBIS (Issue-Based Information System)** é uma metodologia de argumentação estruturada "
        "que organiza as discussões de uma reunião em **questões** (Issues), "
        "**alternativas** (Positions) com prós e contras, e **resoluções**. "
        "Permite entender não apenas o que foi decidido, mas por que — "
        "registrando o raciocínio coletivo da equipe."
    )
    # Carregamento sob demanda: só busca do Supabase se ainda não foi feito nesta sessão
    if _IBIS_SS not in st.session_state:
        with st.spinner("Buscando questões IBIS..."):
            st.session_state[_IBIS_SS] = _load_argumentation(project_id)
        st.rerun()  # re-renderiza para atualizar contador no cabeçalho e métricas
    ibis_questions = st.session_state[_IBIS_SS]  # agora é lista (pode ser [])

    if st.button("🔄 Atualizar IBIS", key="art_ibis_refresh"):
        st.session_state.pop(_IBIS_SS, None)
        _load_argumentation.clear()
        st.rerun()

    if not ibis_questions:
        st.info("Nenhum mapa argumentativo IBIS registrado. Execute o pipeline com o agente Argumentação habilitado.")
    else:
        n_decided    = sum(1 for q in ibis_questions if q.get("resolution", {}).get("type") == "decided")
        n_deferred   = sum(1 for q in ibis_questions if q.get("resolution", {}).get("type") == "deferred")
        n_unresolved = sum(1 for q in ibis_questions if q.get("resolution", {}).get("type") == "unresolved")

        ki1, ki2, ki3, ki4 = st.columns(4)
        ki1.metric("Total de Questões", len(ibis_questions))
        ki2.metric("✅ Decididas", n_decided)
        ki3.metric("⏳ Adiadas", n_deferred)
        ki4.metric("❓ Em aberto", n_unresolved)

        # ── Fase 1b: Métricas detalhadas do debate ────────────────────────────
        n_total_alts = sum(len(q.get("alternatives", [])) for q in ibis_questions)
        n_total_args = sum(
            len(a.get("pros", [])) + len(a.get("cons", []))
            for q in ibis_questions
            for a in q.get("alternatives", [])
        )
        taxa_res = round(n_decided / len(ibis_questions) * 100) if ibis_questions else 0
        q_mais_debatida = max(
            ibis_questions,
            key=lambda q: len(q.get("alternatives", [])),
            default=None,
        )

        with st.expander("📊 Análise do Debate", expanded=True):
            ma1, ma2, ma3 = st.columns(3)
            ma1.metric("Alternativas avaliadas", n_total_alts)
            ma2.metric("Argumentos registrados", n_total_args)
            ma3.metric("Taxa de resolução", f"{taxa_res}%")

            if q_mais_debatida:
                n_alt_max = len(q_mais_debatida.get("alternatives", []))
                stmt_preview = q_mais_debatida.get("statement", "")[:110]
                if len(q_mais_debatida.get("statement", "")) > 110:
                    stmt_preview += "…"
                st.caption(
                    f"🔥 **Questão mais debatida:** {stmt_preview} "
                    f"({n_alt_max} alternativas · Reunião {q_mais_debatida.get('_meeting_number', '?')})"
                )

            # ── Fase 1c: Participação por ator ────────────────────────────────
            _actor: dict[str, dict] = {}

            def _ensure(name: str) -> None:
                if name and name not in _actor:
                    _actor[name] = {
                        "Questões levantadas": 0,
                        "Alternativas propostas": 0,
                        "Posições vencedoras": 0,
                        "A favor (votos)": 0,
                        "Contra (votos)": 0,
                    }

            for _q in ibis_questions:
                _rb = (_q.get("raised_by") or "").strip()
                if _rb:
                    _ensure(_rb)
                    _actor[_rb]["Questões levantadas"] += 1
                for _alt in _q.get("alternatives", []):
                    _pb = (_alt.get("proposed_by") or "").strip()
                    if _pb:
                        _ensure(_pb)
                        _actor[_pb]["Alternativas propostas"] += 1
                        if _alt.get("was_chosen"):
                            _actor[_pb]["Posições vencedoras"] += 1
                    for _s in (_alt.get("supported_by") or []):
                        _s = (_s or "").strip()
                        if _s:
                            _ensure(_s)
                            _actor[_s]["A favor (votos)"] += 1
                    for _o in (_alt.get("opposed_by") or []):
                        _o = (_o or "").strip()
                        if _o:
                            _ensure(_o)
                            _actor[_o]["Contra (votos)"] += 1

            if _actor:
                import pandas as _pd_ibis
                st.markdown("---")
                st.markdown("**👥 Participação por Ator**")
                _df_actor = (
                    _pd_ibis.DataFrame.from_dict(_actor, orient="index")
                    .fillna(0)
                    .astype(int)
                )
                _df_actor.index.name = "Participante"
                _df_actor = _df_actor.sort_values(
                    ["Questões levantadas", "Alternativas propostas"], ascending=False
                )
                # Adiciona coluna de influência total
                _df_actor["Influência total"] = (
                    _df_actor["Questões levantadas"] * 2
                    + _df_actor["Alternativas propostas"]
                    + _df_actor["Posições vencedoras"] * 3
                    + _df_actor["A favor (votos)"]
                    + _df_actor["Contra (votos)"]
                )
                _df_actor = _df_actor.sort_values("Influência total", ascending=False)
                st.dataframe(_df_actor, use_container_width=True)
                st.caption(
                    "Influência total = 2 × questões levantadas + alternativas propostas "
                    "+ 3 × posições vencedoras + votos a favor + votos contra."
                )

        # ── Fase 3b: Evolução Temporal de Debates ────────────────────────────
        with st.expander("📅 Evolução Temporal de Debates", expanded=False):
            st.caption(
                "Agrupa questões similares de reuniões diferentes em **threads de debate** "
                "e exibe a linha do tempo de cada tema — mostrando como foi tratado ao longo do projeto "
                "(adiado repetidamente, reaberto após decisão, etc.)."
            )

            _evo_thresh = st.slider(
                "Limiar de similaridade",
                min_value=0.10, max_value=0.50, value=0.22, step=0.03,
                key="ibis_evo_thresh",
                help="Jaccard sobre tokens PT-BR. Menor = mais threads detectadas.",
            )

            # ── Stop words e similaridade ──────────────────────────────────
            import re as _re_evo
            _EVO_STOP = {
                "a","o","as","os","de","do","da","dos","das","em","no","na",
                "nos","nas","para","que","um","uma","uns","umas","e","ou","se",
                "com","por","mas","é","ser","ter","ao","à","aos","às","não",
                "como","mais","deve","há","esta","este","seu","sua","seus",
                "suas","foi","sido","sendo","está","estão","são","faz","fazer",
                "pode","deve","devem","podem","será","vai","vão",
                "the","of","to","in","is","it","be","as","at","or","an","and",
            }

            def _evo_tok(text: str) -> set:
                words = _re_evo.sub(r"[^\w\sáéíóúâêôãç]", " ", text.lower()).split()
                return {w for w in words if w not in _EVO_STOP and len(w) > 2}

            def _evo_jac(a: str, b: str) -> float:
                wa, wb = _evo_tok(a), _evo_tok(b)
                if not wa or not wb:
                    return 0.0
                return len(wa & wb) / len(wa | wb)

            # ── Union-Find sobre TODAS as questões do projeto ──────────────
            _n = len(ibis_questions)
            _uf = list(range(_n))

            def _uf_find(p: list, x: int) -> int:
                while p[x] != x:
                    p[x] = p[p[x]]
                    x = p[x]
                return x

            def _uf_union(p: list, x: int, y: int) -> None:
                rx, ry = _uf_find(p, x), _uf_find(p, y)
                if rx != ry:
                    p[ry] = rx

            for _ea in range(_n):
                for _eb in range(_ea + 1, _n):
                    _qa = ibis_questions[_ea]
                    _qb = ibis_questions[_eb]
                    if _qa.get("_meeting_id") == _qb.get("_meeting_id"):
                        continue
                    if _evo_jac(_qa.get("statement", ""), _qb.get("statement", "")) >= _evo_thresh:
                        _uf_union(_uf, _ea, _eb)

            # ── Agrupar em componentes ─────────────────────────────────────
            from collections import defaultdict as _dd_evo
            _comp: dict = _dd_evo(list)
            for _ei, _eq in enumerate(ibis_questions):
                _comp[_uf_find(_uf, _ei)].append(_eq)

            # Manter só componentes com 2+ reuniões distintas
            _threads: list[list] = []
            for _root, _qs in _comp.items():
                _mids_in = {q.get("_meeting_id") for q in _qs}
                if len(_mids_in) >= 2:
                    _threads.append(
                        sorted(_qs, key=lambda q: (q.get("_meeting_number") or 0))
                    )
            _threads.sort(key=lambda t: t[0].get("_meeting_number") or 0)

            if not _threads:
                st.info(
                    "Nenhum debate recorrente detectado com este limiar. "
                    "Tente reduzir o valor do slider."
                )
            else:
                _res_cfg = {
                    "decided":    ("✅", "Decidida",  "#14532d", "#4ade80"),
                    "deferred":   ("⏳", "Adiada",    "#451a03", "#fbbf24"),
                    "unresolved": ("❓", "Em aberto", "#450a0a", "#f87171"),
                }
                st.success(f"**{len(_threads)} debate(s) recorrente(s)** identificado(s) no projeto.")
                st.markdown("")

                for _ti, _thread in enumerate(_threads, 1):
                    _rep = _thread[0].get("statement", "")
                    _preview = _rep[:90] + ("…" if len(_rep) > 90 else "")
                    st.markdown(f"**Debate #{_ti}** — {_preview}")

                    # Cabeçalho de reuniões com seta entre elas
                    _ncols = min(len(_thread), 6)
                    _thread_show = _thread[:6]
                    if len(_thread) > 6:
                        st.caption(f"(Exibindo primeiras 6 de {len(_thread)} ocorrências)")

                    _tcols = st.columns(_ncols)
                    for _tci, (_col, _tq) in enumerate(zip(_tcols, _thread_show)):
                        _t_mnum  = _tq.get("_meeting_number", "?")
                        _t_mdate = str(_tq.get("_meeting_date") or "")[:10]
                        _t_stmt  = _tq.get("statement", "")
                        _t_res   = (_tq.get("resolution") or {}).get("type", "unresolved")
                        _t_rat   = (_tq.get("resolution") or {}).get("rationale", "")
                        _t_cav   = (_tq.get("resolution") or {}).get("with_caveats") or []
                        _emoji, _label, _bg, _border = _res_cfg.get(_t_res, _res_cfg["unresolved"])

                        with _col:
                            st.markdown(
                                f"<div style='background:{_bg};border:1px solid {_border};"
                                "border-radius:8px;padding:8px 10px;font-size:12px;"
                                "color:#f1f5f9;min-height:110px'>"
                                f"<b>Reunião {_t_mnum}</b>"
                                + (f"<br><span style='color:#94a3b8;font-size:10px'>{_t_mdate}</span>" if _t_mdate else "")
                                + f"<br><br>{_emoji} <b>{_label}</b>"
                                + (f"<br><span style='font-size:10px;color:#cbd5e1'>{_t_stmt[:60]}…</span>" if len(_t_stmt) > 60 else f"<br><span style='font-size:10px;color:#cbd5e1'>{_t_stmt}</span>")
                                + "</div>",
                                unsafe_allow_html=True,
                            )
                            if _t_rat or _t_cav:
                                with st.popover("ℹ️"):
                                    st.markdown(f"**Questão:** {_t_stmt}")
                                    if _t_rat:
                                        st.info(f"**Resolução:** {_t_rat}")
                                    for _cav in _t_cav:
                                        st.warning(f"Ressalva: {_cav}")

                    # Linha de progresso visual
                    _statuses = [
                        (_tq.get("resolution") or {}).get("type", "unresolved")
                        for _tq in _thread_show
                    ]
                    _decided_at = next(
                        (i + 1 for i, s in enumerate(_statuses) if s == "decided"), None
                    )
                    if _decided_at:
                        _pct = int(_decided_at / len(_statuses) * 100)
                        _note = (
                            f"Decidido na {_decided_at}ª ocorrência"
                            if _decided_at > 1
                            else "Decidido na primeira ocorrência"
                        )
                        if _decided_at < len(_statuses):
                            _note += " — reaberto depois"
                        st.caption(f"🔁 {_note}")
                    elif all(s == "deferred" for s in _statuses):
                        st.caption("⏳ Adiado em todas as ocorrências — ainda sem decisão")
                    elif all(s == "unresolved" for s in _statuses):
                        st.caption("❓ Permanece sem resolução ao longo do projeto")

                    st.markdown("---")

        # ── Fase 3c: Força dos Argumentos ────────────────────────────────────
        with st.expander("⚖️ Força dos Argumentos", expanded=False):
            st.caption(
                "Quantifica o **balanço argumentativo** de cada alternativa (prós − contras) "
                "e identifica **decisões vulneráveis** — escolhas cuja alternativa eleita "
                "tinha mais contras do que prós registrados na reunião, sinalizando "
                "possíveis riscos não endereçados."
            )

            _force_rows = []
            for _fq in ibis_questions:
                _fres      = _fq.get("resolution") or {}
                _chosen_id = _fres.get("chosen_alternative_id", "")
                _mid       = _fq.get("_meeting_id", "")
                _stmt      = _fq.get("statement", "")
                _mnum      = meet_label(_mid) if _mid else "?"
                for _falt in _fq.get("alternatives", []):
                    _aid  = _falt.get("id", "")
                    _pros = len(_falt.get("pros") or [])
                    _cons = len(_falt.get("cons") or [])
                    _force_rows.append({
                        "reunião":     _mnum,
                        "questão":     _stmt[:70] + ("…" if len(_stmt) > 70 else ""),
                        "alternativa": (_falt.get("description") or "")[:55],
                        "prós":        _pros,
                        "contras":     _cons,
                        "balanço":     _pros - _cons,
                        "eleita":      _aid == _chosen_id,
                    })

            if not _force_rows:
                st.info("Sem alternativas com prós/contras para analisar.")
            else:
                import pandas as _pd_force
                import plotly.graph_objects as _go_force

                _df_force  = _pd_force.DataFrame(_force_rows)
                _chosen_df = _df_force[_df_force["eleita"]]
                _vuln_df   = _chosen_df[_chosen_df["balanço"] <= 0]

                _kf1, _kf2, _kf3 = st.columns(3)
                _kf1.metric("Alternativas analisadas", len(_df_force))
                _kf2.metric(
                    "Decisões vulneráveis", len(_vuln_df),
                    help="Alternativas eleitas com balanço prós−contras ≤ 0",
                )
                _total_ch = max(len(_chosen_df), 1)
                _kf3.metric(
                    "Decisões bem fundamentadas",
                    f"{round((_total_ch - len(_vuln_df)) / _total_ch * 100)}%",
                )

                if not _vuln_df.empty:
                    st.markdown("---")
                    st.markdown("**⚠️ Decisões vulneráveis**")
                    for _, _vr in _vuln_df.iterrows():
                        _sign = "0" if _vr["balanço"] == 0 else str(int(_vr["balanço"]))
                        st.warning(
                            f"**{_vr['reunião']}** · _{_vr['questão']}_  \n"
                            f"Alternativa eleita: *{_vr['alternativa']}* — "
                            f"{int(_vr['prós'])} prós / {int(_vr['contras'])} contras "
                            f"(balanço {_sign})"
                        )

                st.markdown("---")
                st.markdown("**📊 Balanço Argumentativo por Alternativa**")
                st.caption(
                    "🟢 Verde = mais prós · 🔴 Vermelho = mais contras · "
                    "⚪ Cinza = empatado · ✅ = alternativa eleita"
                )

                _df_plot = _df_force.sort_values(
                    ["reunião", "questão", "balanço"],
                    ascending=[True, True, False],
                ).reset_index(drop=True)

                _flabels = [
                    f"{r['reunião']} | {r['alternativa']}" + (" ✅" if r["eleita"] else "")
                    for _, r in _df_plot.iterrows()
                ]
                _fscores = _df_plot["balanço"].tolist()
                _fcolors = [
                    "#22c55e" if s > 0 else ("#f87171" if s < 0 else "#94a3b8")
                    for s in _fscores
                ]

                _fig_f = _go_force.Figure(_go_force.Bar(
                    x=_fscores,
                    y=_flabels,
                    orientation="h",
                    marker_color=_fcolors,
                    text=[f"+{s}" if s > 0 else str(s) for s in _fscores],
                    textposition="outside",
                    hovertemplate="%{y}<br>Balanço: %{x}<extra></extra>",
                ))
                _fig_f.update_layout(
                    paper_bgcolor="#0d1b2a",
                    plot_bgcolor="#0d1b2a",
                    font_color="#e2e8f0",
                    xaxis=dict(
                        title="Balanço (prós − contras)",
                        zeroline=True,
                        zerolinecolor="#475569",
                        gridcolor="#1e3a5f",
                    ),
                    yaxis=dict(autorange="reversed"),
                    height=max(300, len(_flabels) * 34),
                    margin=dict(l=10, r=80, t=10, b=40),
                    showlegend=False,
                )
                st.plotly_chart(_fig_f, use_container_width=True)

        st.markdown("---")

        # Filtro por reunião
        meet_ids_ibis = sorted({q["_meeting_id"] for q in ibis_questions})
        meet_labels_ibis = {"Todas as reuniões": None}
        for mid in meet_ids_ibis:
            meet_labels_ibis[meet_label(mid)] = mid
        sel_meet_ibis = st.selectbox("Filtrar por reunião", list(meet_labels_ibis.keys()), key="ibis_meet_filter")

        # Filtro por resolução
        sel_res = st.selectbox(
            "Filtrar por resolução",
            ["Todas", "decided", "deferred", "unresolved"],
            format_func=lambda x: {"Todas": "Todas", "decided": "✅ Decididas",
                                    "deferred": "⏳ Adiadas", "unresolved": "❓ Em aberto"}.get(x, x),
            key="ibis_res_filter",
        )

        filtered_ibis = ibis_questions
        if meet_labels_ibis[sel_meet_ibis]:
            filtered_ibis = [q for q in filtered_ibis if q["_meeting_id"] == meet_labels_ibis[sel_meet_ibis]]
        if sel_res != "Todas":
            filtered_ibis = [q for q in filtered_ibis if q.get("resolution", {}).get("type") == sel_res]

        # ── Fase 5: Filtros avançados — busca por texto + ator ───────────────
        _f5c1, _f5c2 = st.columns([3, 2])
        _ibis_search = _f5c1.text_input(
            "Buscar nas questões",
            key="ibis_text_search",
            placeholder="🔍 palavra-chave…",
            label_visibility="collapsed",
        )
        _all_ibis_actors = sorted({
            _name
            for _q2 in ibis_questions
            for _name in (
                [_q2.get("raised_by") or ""]
                + [_a2.get("proposed_by") or "" for _a2 in _q2.get("alternatives", [])]
                + [_s for _a2 in _q2.get("alternatives", []) for _s in (_a2.get("supported_by") or [])]
                + [_o for _a2 in _q2.get("alternatives", []) for _o in (_a2.get("opposed_by") or [])]
            )
            if _name
        })
        _sel_actor = _f5c2.selectbox(
            "Filtrar por ator",
            ["Todos os atores"] + _all_ibis_actors,
            key="ibis_actor_filter",
            label_visibility="collapsed",
        )

        if _ibis_search:
            _kw = _ibis_search.lower()
            filtered_ibis = [
                q for q in filtered_ibis
                if _kw in q.get("statement", "").lower()
                or any(_kw in (_a.get("description") or "").lower() for _a in q.get("alternatives", []))
                or any(_kw in _p.lower() for _a in q.get("alternatives", []) for _p in (_a.get("pros") or []))
                or any(_kw in _c.lower() for _a in q.get("alternatives", []) for _c in (_a.get("cons") or []))
            ]

        if _sel_actor != "Todos os atores":
            def _q_has_actor(_q3, _actor):
                if (_q3.get("raised_by") or "") == _actor:
                    return True
                for _a3 in _q3.get("alternatives", []):
                    if (_a3.get("proposed_by") or "") == _actor:
                        return True
                    if _actor in (_a3.get("supported_by") or []):
                        return True
                    if _actor in (_a3.get("opposed_by") or []):
                        return True
                return False
            filtered_ibis = [q for q in filtered_ibis if _q_has_actor(q, _sel_actor)]

        # ── Fase 4: Exportar Relatório IBIS (.md) ────────────────────────────
        def _ibis_to_markdown(questions: list) -> str:
            _res_lbl = {
                "decided":    "✅ Decidida",
                "deferred":   "⏳ Adiada",
                "unresolved": "❓ Em aberto",
            }
            _lines = ["# Mapa Argumentativo IBIS\n"]
            _lines.append(f"**Total de questões:** {len(questions)}\n")
            for _q4 in questions:
                _res4  = _q4.get("resolution") or {}
                _rt4   = _res4.get("type", "unresolved")
                _mnum4 = _q4.get("_meeting_number", "?")
                _lines.append(f"\n## {_q4.get('id', '?')} — {_q4.get('statement', '')}")
                _lines.append(f"\n**Reunião:** {_mnum4}  ")
                if _q4.get("raised_by"):
                    _lines.append(f"**Levantada por:** {_q4['raised_by']}  ")
                _lines.append(f"**Status:** {_res_lbl.get(_rt4, _rt4)}\n")
                for _alt4 in _q4.get("alternatives", []):
                    _chosen4 = " ✅ *(escolhida)*" if _alt4.get("was_chosen") else ""
                    _lines.append(
                        f"\n### {_alt4.get('id', '?')}{_chosen4} — {_alt4.get('description', '')}"
                    )
                    if _alt4.get("proposed_by"):
                        _lines.append(f"\n*Proposta por: {_alt4['proposed_by']}*\n")
                    if _alt4.get("pros"):
                        _lines.append("\n**A favor:**")
                        _lines.extend(f"- {_p}" for _p in _alt4["pros"])
                    if _alt4.get("cons"):
                        _lines.append("\n**Contra:**")
                        _lines.extend(f"- {_c}" for _c in _alt4["cons"])
                    _sup4 = ", ".join(_alt4.get("supported_by") or [])
                    _opp4 = ", ".join(_alt4.get("opposed_by") or [])
                    if _sup4:
                        _lines.append(f"\n*A favor: {_sup4}*")
                    if _opp4:
                        _lines.append(f"\n*Contra: {_opp4}*")
                if _res4.get("rationale"):
                    _lines.append(f"\n**Resolução:** {_res4['rationale']}")
                if _res4.get("with_caveats"):
                    _lines.append("\n**Ressalvas:**")
                    _lines.extend(f"- {_cav}" for _cav in _res4["with_caveats"])
                _lines.append("\n---")
            return "\n".join(_lines)

        st.download_button(
            "📥 Exportar Relatório IBIS (.md)",
            data=_ibis_to_markdown(filtered_ibis),
            file_name="ibis_debate_map.md",
            mime="text/markdown",
            key="ibis_export_md",
            help="Baixa o mapa argumentativo filtrado como Markdown estruturado",
        )

        # ── Toggle de visualização ────────────────────────────────────────────
        ibis_view = st.radio(
            "Visualização",
            ["📋 Lista", "🕸️ Mapa Visual"],
            horizontal=True,
            key="ibis_view_toggle",
            label_visibility="collapsed",
        )

        st.caption(f"Exibindo {len(filtered_ibis)} questão(ões)")

        # ════════════════════════════════════════════════════════════════════
        # MODO LISTA (existente)
        # ════════════════════════════════════════════════════════════════════
        if ibis_view == "📋 Lista":
            st.markdown("")
            for q in filtered_ibis:
                q_id        = q.get("id", "—")
                statement   = q.get("statement", "—")
                raised_by   = q.get("raised_by", "")
                alternatives = q.get("alternatives", [])
                resolution  = q.get("resolution", {})
                res_type    = resolution.get("type", "unresolved")
                badge_cls, badge_txt = _RESOLUTION_BADGE.get(res_type, ("ibis-badge-unresolved", "❓"))
                m_num = q.get("_meeting_number")
                origin = f"🗓️ Reunião {m_num}" if m_num else "—"

                with st.expander(
                    f"**{q_id}** — {statement[:80]}{'…' if len(statement) > 80 else ''}  ·  {origin}",
                    expanded=(res_type == "unresolved"),
                ):
                    col_s, col_b = st.columns([4, 1])
                    with col_s:
                        st.markdown(f"**{statement}**")
                        if raised_by:
                            st.caption(f"👤 Levantada por: **{raised_by}**")
                    with col_b:
                        st.markdown(
                            f'<span class="badge {badge_cls}">{badge_txt}</span>',
                            unsafe_allow_html=True,
                        )

                    if alternatives:
                        st.markdown("**Alternativas avaliadas:**")
                        for alt in alternatives:
                            chosen_mark = " ✅ **(escolhida)**" if alt.get("was_chosen") else ""
                            st.markdown(f"**{alt.get('id', '—')}** — {alt.get('description', '—')}{chosen_mark}")
                            if alt.get("proposed_by"):
                                st.caption(f"Proposta por: {alt['proposed_by']}")
                            cols_arg = st.columns(2)
                            if alt.get("pros"):
                                cols_arg[0].success("**A favor:**\n" + "\n".join(f"- {p}" for p in alt["pros"]))
                            if alt.get("cons"):
                                cols_arg[1].error("**Contra:**\n" + "\n".join(f"- {c}" for c in alt["cons"]))
                            supporters = ", ".join(alt.get("supported_by", []))
                            opposers   = ", ".join(alt.get("opposed_by", []))
                            parts = []
                            if supporters:
                                parts.append(f"A favor: {supporters}")
                            if opposers:
                                parts.append(f"Contra: {opposers}")
                            if parts:
                                st.caption(" | ".join(parts))
                            st.markdown("---")

                    if res_type != "unresolved":
                        if resolution.get("rationale"):
                            st.info(f"**Resolução:** {resolution['rationale']}")
                        if resolution.get("with_caveats"):
                            st.warning("**Ressalvas:**\n" + "\n".join(f"- {c}" for c in resolution["with_caveats"]))
                    else:
                        st.error("Questão sem resolução ao final da reunião.")

        # ════════════════════════════════════════════════════════════════════
        # MODO MAPA VISUAL (pyvis)
        # ════════════════════════════════════════════════════════════════════
        else:
            _RES_BORDER = {
                "decided":    "#22c55e",   # verde
                "deferred":   "#fbbf24",   # âmbar
                "unresolved": "#f87171",   # vermelho
            }
            _GRAPH_H = 680

            # Opções do grafo
            with st.expander("⚙️ Opções do grafo", expanded=False):
                _g_col1, _g_col2 = st.columns(2)
                _cross_thresh = _g_col1.slider(
                    "Limiar de similaridade (cross-links entre reuniões)",
                    min_value=0.10, max_value=0.55, value=0.22, step=0.03,
                    key="ibis_cross_thresh",
                    help="Jaccard sobre tokens PT-BR. Menor valor = mais conexões; maior valor = só os debates mais parecidos.",
                )
                _show_args = _g_col2.checkbox(
                    "Mostrar argumentos (prós/contras) no grafo",
                    value=True, key="ibis_show_args",
                )
                _g_col3, _g_col4 = st.columns(2)
                _ibis_physics = _g_col3.toggle(
                    "Simulação física (Barnes-Hut)",
                    value=True,
                    key="ibis_physics",
                    help="Organiza os nós automaticamente. Desative para fixar o layout após arrastar.",
                )
                _ibis_height = _g_col4.select_slider(
                    "Altura do grafo",
                    options=[480, 600, 680, 860, 1000],
                    value=680,
                    key="ibis_graph_height",
                )

            if len(filtered_ibis) > 60:
                st.warning(
                    f"O filtro retornou {len(filtered_ibis)} questões. "
                    "Considere filtrar por reunião para um grafo mais legível."
                )

            try:
                import streamlit.components.v1 as _comp_ibis
                from pyvis.network import Network as _IbisNet

                _net = _IbisNet(
                    height=f"{_GRAPH_H}px",
                    width="100%",
                    bgcolor="#0d1b2a",
                    font_color="#f1f5f9",
                )

                for _q in filtered_ibis:
                    _qid     = _q.get("id", "Q?")
                    _stmt    = _q.get("statement", "")
                    _rb      = _q.get("raised_by", "")
                    _mnum    = _q.get("_meeting_number", "?")
                    _rt      = (_q.get("resolution") or {}).get("type", "unresolved")
                    _rationale = (_q.get("resolution") or {}).get("rationale", "")
                    _nid_q   = f"Q_{_mnum}_{_qid}"

                    _q_label = _stmt[:32] + ("…" if len(_stmt) > 32 else "")
                    _q_tip   = (
                        f"<b>{_qid}</b> · Reunião {_mnum}<br>"
                        f"{_stmt}<br><br>"
                        + (f"Levantada por: {_rb}<br>" if _rb else "")
                        + f"Status: {_rt}"
                        + (f"<br><i>{_rationale[:120]}</i>" if _rationale else "")
                    )
                    _net.add_node(
                        _nid_q,
                        label=_q_label,
                        title=_q_tip,
                        shape="ellipse",
                        size=22,
                        color={
                            "background": "#f97316",
                            "border":     _RES_BORDER.get(_rt, "#f87171"),
                            "highlight":  {"background": "#fb923c", "border": "#fff"},
                        },
                        font={"size": 11, "color": "#fff", "bold": True},
                        borderWidth=3,
                    )

                    for _alt in (_q.get("alternatives") or []):
                        _aid    = _alt.get("id", "A?")
                        _adesc  = _alt.get("description", "")
                        _pb     = _alt.get("proposed_by", "")
                        _chosen = _alt.get("was_chosen", False)
                        _nid_a  = f"A_{_mnum}_{_qid}_{_aid}"

                        _a_label = _adesc[:28] + ("…" if len(_adesc) > 28 else "")
                        _a_tip   = (
                            f"<b>{_aid}</b>"
                            + (" ✅ escolhida" if _chosen else "")
                            + f"<br>{_adesc}"
                            + (f"<br>Proposta por: {_pb}" if _pb else "")
                        )
                        _net.add_node(
                            _nid_a,
                            label=_a_label,
                            title=_a_tip,
                            shape="diamond",
                            size=16,
                            color={
                                "background": "#2563eb" if not _chosen else "#1d4ed8",
                                "border":     "#fbbf24" if _chosen else "#60a5fa",
                                "highlight":  {"background": "#3b82f6", "border": "#fff"},
                            },
                            font={"size": 10, "color": "#dbeafe"},
                            borderWidth=2 if not _chosen else 3,
                        )
                        _net.add_edge(
                            _nid_q, _nid_a,
                            color={"color": "#94a3b8", "highlight": "#fff"},
                            width=1.5,
                            arrows="to",
                            title="Alternativa proposta",
                        )

                        if _show_args:
                            for _i, _pro in enumerate(_alt.get("pros") or []):
                                _nid_p = f"P_{_mnum}_{_qid}_{_aid}_{_i}"
                                _p_label = str(_pro)[:26] + ("…" if len(str(_pro)) > 26 else "")
                                _net.add_node(
                                    _nid_p,
                                    label=_p_label,
                                    title=f"<b>A favor:</b> {_pro}",
                                    shape="dot",
                                    size=9,
                                    color={
                                        "background": "#16a34a",
                                        "border":     "#4ade80",
                                        "highlight":  {"background": "#22c55e", "border": "#fff"},
                                    },
                                    font={"size": 9, "color": "#dcfce7"},
                                    borderWidth=1,
                                )
                                _net.add_edge(
                                    _nid_a, _nid_p,
                                    color={"color": "#4ade80", "highlight": "#fff"},
                                    width=1,
                                    arrows="to",
                                    dashes=True,
                                    title="Argumento a favor",
                                )

                            for _j, _con in enumerate(_alt.get("cons") or []):
                                _nid_c = f"C_{_mnum}_{_qid}_{_aid}_{_j}"
                                _c_label = str(_con)[:26] + ("…" if len(str(_con)) > 26 else "")
                                _net.add_node(
                                    _nid_c,
                                    label=_c_label,
                                    title=f"<b>Contra:</b> {_con}",
                                    shape="dot",
                                    size=9,
                                    color={
                                        "background": "#b91c1c",
                                        "border":     "#f87171",
                                        "highlight":  {"background": "#ef4444", "border": "#fff"},
                                    },
                                    font={"size": 9, "color": "#fee2e2"},
                                    borderWidth=1,
                                )
                                _net.add_edge(
                                    _nid_a, _nid_c,
                                    color={"color": "#f87171", "highlight": "#fff"},
                                    width=1,
                                    arrows="to",
                                    dashes=True,
                                    title="Argumento contra",
                                )

                # ── Fase 2b: Cross-links entre reuniões ──────────────────────
                import re as _re_ibis
                import json as _json_ibis

                _IBIS_STOP = {
                    "a","o","as","os","de","do","da","dos","das","em","no","na",
                    "nos","nas","para","que","um","uma","uns","umas","e","ou","se",
                    "com","por","mas","é","ser","ter","ao","à","aos","às","não",
                    "como","mais","deve","há","esta","este","seu","sua","seus",
                    "suas","foi","ser","sido","sendo","está","estão","são","faz",
                    "fazer","pode","deve","devem","podem","será","vai","vão","use",
                    "the","of","to","in","is","it","be","as","at","or","an","and",
                }

                def _ibis_tokens(text: str) -> set:
                    words = _re_ibis.sub(r"[^\w\sáéíóúâêôãç]", " ", text.lower()).split()
                    return {w for w in words if w not in _IBIS_STOP and len(w) > 2}

                def _ibis_jaccard(a: str, b: str) -> float:
                    wa, wb = _ibis_tokens(a), _ibis_tokens(b)
                    if not wa or not wb:
                        return 0.0
                    return len(wa & wb) / len(wa | wb)

                # Índice de nós-questão para cross-link
                _q_idx: list[tuple] = []   # (nid, statement, meeting_id, meeting_num, q_id)
                for _q2 in filtered_ibis:
                    _qid2   = _q2.get("id", "Q?")
                    _mnum2  = _q2.get("_meeting_number", "?")
                    _mid2   = _q2.get("_meeting_id", "")
                    _stmt2  = _q2.get("statement", "")
                    _mtitle2 = _q2.get("_meeting_title", f"Reunião {_mnum2}")
                    _q_idx.append((f"Q_{_mnum2}_{_qid2}", _stmt2, _mid2, _mnum2, _mtitle2))

                _cross_found: list[dict] = []
                _seen_pairs: set = set()
                for _ia in range(len(_q_idx)):
                    for _ib in range(_ia + 1, len(_q_idx)):
                        _na, _sa, _mida, _mnuma, _mtitlea = _q_idx[_ia]
                        _nb, _sb, _midb, _mnumb, _mtitleb = _q_idx[_ib]
                        if _mida == _midb:
                            continue   # mesma reunião
                        _pair_key = tuple(sorted([_na, _nb]))
                        if _pair_key in _seen_pairs:
                            continue
                        _seen_pairs.add(_pair_key)
                        _sim = _ibis_jaccard(_sa, _sb)
                        if _sim >= _cross_thresh:
                            _cross_found.append({
                                "nid_a": _na, "nid_b": _nb,
                                "sim": _sim,
                                "stmt_a": _sa, "stmt_b": _sb,
                                "mnum_a": _mnuma, "mnum_b": _mnumb,
                                "mtitle_a": _mtitlea, "mtitle_b": _mtitleb,
                            })

                for _cl in _cross_found:
                    _w = max(1.5, _cl["sim"] * 6)
                    _net.add_edge(
                        _cl["nid_a"], _cl["nid_b"],
                        color={"color": "#a855f7", "highlight": "#d8b4fe"},
                        width=_w,
                        arrows="",
                        dashes=[6, 4],
                        title=(
                            f"<b>Debate recorrente</b> ({_cl['sim']:.0%} similaridade)<br>"
                            f"Reunião {_cl['mnum_a']}: {_cl['stmt_a'][:80]}<br>"
                            f"Reunião {_cl['mnum_b']}: {_cl['stmt_b'][:80]}"
                        ),
                    )

                # ── Opções de física ─────────────────────────────────────────
                _net.set_options(_json_ibis.dumps({
                    "physics": {
                        "enabled": _ibis_physics,
                        "solver": "barnesHut",
                        "barnesHut": {
                            "gravitationalConstant": -9000,
                            "centralGravity":        0.25,
                            "springLength":          130,
                            "springConstant":        0.035,
                            "damping":               0.12,
                            "avoidOverlap":          0.4,
                        },
                        "maxVelocity": 50,
                        "minVelocity": 0.75,
                        "stabilization": {
                            "enabled":        True,
                            "iterations":     250,
                            "updateInterval": 25,
                            "fit":            True,
                        },
                    },
                    "interaction": {
                        "hover":             True,
                        "tooltipDelay":      80,
                        "navigationButtons": False,
                        "keyboard":          False,
                        "zoomView":          True,
                        "dragView":          True,
                        "dragNodes":         True,
                        "multiselect":       False,
                    },
                    "edges": {
                        "smooth":         {"type": "dynamic"},
                        "arrows":         {"to": {"enabled": False}},
                        "hoverWidth":     2,
                        "selectionWidth": 2,
                    },
                    "nodes": {
                        "borderWidth":         2,
                        "borderWidthSelected": 3,
                        "scaling":             {"min": 8, "max": 28},
                    },
                }))

                _html_ibis = _net.generate_html(local=False)

                # ── Tooltip CSS + toolbar CSS ─────────────────────────────────
                _html_ibis = _html_ibis.replace(
                    "</style>",
                    ".vis-tooltip{white-space:pre-line!important;"
                    "font-family:'Segoe UI',system-ui,sans-serif!important;"
                    "font-size:13px!important;line-height:1.6!important;"
                    "max-width:420px!important;max-height:none!important;"
                    "overflow:visible!important;word-break:break-word!important;"
                    "box-shadow:0 4px 16px rgba(0,0,0,.6)!important;"
                    "border-radius:8px!important;padding:10px 14px!important;}"
                    "#ibis-toolbar{display:flex;gap:5px;padding:8px 10px;"
                    "background:#1e293b;border-bottom:1px solid #334155;"
                    "flex-wrap:wrap;align-items:center;"
                    "font-family:'Segoe UI',system-ui,sans-serif;}"
                    ".itb-btn{background:#334155;color:#f1f5f9;border:1px solid #475569;"
                    "border-radius:6px;padding:5px 11px;font-size:12px;cursor:pointer;"
                    "white-space:nowrap;transition:background .15s;}"
                    ".itb-btn:hover{background:#475569;}"
                    "#ibis-btnClearFocus{display:none;background:#1d4ed8;border-color:#1e40af;}"
                    "#ibis-btnClearFocus:hover{background:#2563eb;}"
                    ".itb-sep{width:1px;background:#475569;height:22px;margin:0 3px;flex-shrink:0;}"
                    "#ibis-status{font-size:11px;color:#94a3b8;margin-left:6px;flex:1;}"
                    "#ibis-hint{font-size:10px;color:#64748b;margin-left:auto;}"
                    "</style>",
                    1,
                )

                # ── Toolbar HTML ──────────────────────────────────────────────
                _phys_init_js = "true" if _ibis_physics else "false"
                _itoolbar = (
                    '<div id="ibis-toolbar">'
                    '<button id="ibis-btnPhysics" class="itb-btn" onclick="ibisTogglePhysics()">⏸ Pausar</button>'
                    '<div class="itb-sep"></div>'
                    '<button class="itb-btn" onclick="ibisZoomIn()" title="Zoom in">＋</button>'
                    '<button class="itb-btn" onclick="ibisZoomOut()" title="Zoom out">－</button>'
                    '<button class="itb-btn" onclick="ibisFit()" title="Ajustar ao ecrã">⊡ Fit</button>'
                    '<div class="itb-sep"></div>'
                    '<button class="itb-btn" onclick="ibisSaveImg()" title="Salvar como PNG">💾 Imagem</button>'
                    '<button class="itb-btn" onclick="ibisNewTab()" title="Abrir em nova aba">⛶ Nova aba</button>'
                    '<div class="itb-sep"></div>'
                    '<button id="ibis-btnClearFocus" class="itb-btn" onclick="ibisClearFocus()">✕ Limpar foco</button>'
                    '<span id="ibis-status"></span>'
                    '<span id="ibis-hint">Clique em um nó para focar</span>'
                    '</div>'
                )
                _html_ibis = _html_ibis.replace('<div id="mynetwork"', _itoolbar + '<div id="mynetwork"', 1)

                # ── Focus mode + toolbar JS ───────────────────────────────────
                _itoolbar_js = f"""
<script>
var _ibisPhysicsOn   = {_phys_init_js};
var _ibisFocusMode   = false;
var _ibisFocusedNode = null;
var _ibisSnNodes     = {{}};
var _ibisSnEdges     = {{}};

var _IDIM_NODE = {{
    background:'#0d1520',border:'#1a2535',
    highlight:{{background:'#0d1520',border:'#1e2d42'}},
    hover:{{background:'#0d1520',border:'#1e2d42'}}
}};
var _IDIM_FONT = {{color:'#1e293b'}};
var _IDIM_EDGE = {{color:'rgba(15,23,42,0.10)',highlight:'rgba(15,23,42,0.10)',hover:'rgba(15,23,42,0.10)'}};

function _ibisSnap() {{
    if (Object.keys(_ibisSnNodes).length > 0) return;
    network.body.data.nodes.get().forEach(function(n) {{
        _ibisSnNodes[n.id] = {{
            color: JSON.parse(JSON.stringify(n.color || {{}})),
            font:  JSON.parse(JSON.stringify(n.font  || {{}}))
        }};
    }});
    network.body.data.edges.get().forEach(function(e) {{
        _ibisSnEdges[e.id] = {{color: JSON.parse(JSON.stringify(e.color || {{}}))}};
    }});
}}

function ibisFocusNode(nid) {{
    _ibisSnap();
    _ibisFocusMode   = true;
    _ibisFocusedNode = nid;
    var conn  = new Set(network.getConnectedNodes(nid));
    conn.add(nid);
    var connE = new Set(network.getConnectedEdges(nid));

    var dimUpd = [], focIds = [];
    network.body.data.nodes.get().forEach(function(n) {{
        if (conn.has(n.id)) focIds.push(n.id);
        else dimUpd.push({{id:n.id,color:_IDIM_NODE,font:_IDIM_FONT,zIndex:-1}});
    }});
    if (dimUpd.length) network.body.data.nodes.update(dimUpd);

    var focPos  = network.getPositions(focIds);
    var focData = focIds.map(function(fid) {{
        var s = _ibisSnNodes[fid] || {{}};
        var n = network.body.data.nodes.get(fid);
        return Object.assign({{}}, n, {{color:s.color,font:s.font,zIndex:10}});
    }});
    network.body.data.nodes.remove(focIds);
    network.body.data.nodes.add(focData);
    focIds.forEach(function(fid) {{
        var p = focPos[fid]; if (p) network.moveNode(fid, p.x, p.y);
    }});

    network.body.data.edges.update(
        network.body.data.edges.get().map(function(e) {{
            if (connE.has(e.id)) {{
                var s = _ibisSnEdges[e.id] || {{}};
                return {{id:e.id,color:s.color}};
            }}
            return {{id:e.id,color:_IDIM_EDGE}};
        }})
    );

    var lbl   = (network.body.data.nodes.get(nid)||{{}}).label || nid;
    var nConn = conn.size - 1;
    document.getElementById('ibis-status').textContent =
        '🔍 ' + lbl + ' — ' + nConn + ' conex' + (nConn===1?'ão':'ões');
    document.getElementById('ibis-hint').style.display = 'none';
    document.getElementById('ibis-btnClearFocus').style.display = '';
}}

function ibisClearFocus() {{
    if (!_ibisFocusMode) return;
    _ibisFocusMode = false; _ibisFocusedNode = null;
    network.body.data.nodes.update(
        network.body.data.nodes.get().map(function(n) {{
            var s = _ibisSnNodes[n.id] || {{}};
            return {{id:n.id,color:s.color,font:s.font,zIndex:0}};
        }})
    );
    network.body.data.edges.update(
        network.body.data.edges.get().map(function(e) {{
            var s = _ibisSnEdges[e.id] || {{}};
            return {{id:e.id,color:s.color}};
        }})
    );
    document.getElementById('ibis-status').textContent = '';
    document.getElementById('ibis-hint').style.display = '';
    document.getElementById('ibis-btnClearFocus').style.display = 'none';
}}

network.on('click', function(p) {{
    if (p.nodes.length > 0) {{
        var nid = p.nodes[0];
        if (_ibisFocusMode && _ibisFocusedNode === nid) ibisClearFocus();
        else ibisFocusNode(nid);
    }} else if (p.edges.length === 0) {{
        ibisClearFocus();
    }}
}});

function _ibisSetPhysBtn() {{
    var btn = document.getElementById('ibis-btnPhysics');
    if (_ibisPhysicsOn) {{
        btn.innerHTML='⏸ Pausar'; btn.style.background=''; btn.style.borderColor='';
    }} else {{
        btn.innerHTML='▶ Retomar'; btn.style.background='#16a34a'; btn.style.borderColor='#15803d';
    }}
}}

function ibisTogglePhysics() {{
    _ibisPhysicsOn = !_ibisPhysicsOn;
    network.setOptions({{physics:{{enabled:_ibisPhysicsOn}}}});
    if (!_ibisPhysicsOn) network.stopSimulation();
    _ibisSetPhysBtn();
}}

function ibisZoomIn()  {{ network.moveTo({{scale:network.getScale()*1.3,animation:{{duration:200,easingFunction:'easeInOutQuad'}}}}); }}
function ibisZoomOut() {{ network.moveTo({{scale:network.getScale()/1.3,animation:{{duration:200,easingFunction:'easeInOutQuad'}}}}); }}
function ibisFit()     {{ network.fit({{animation:{{duration:500,easingFunction:'easeInOutQuad'}}}}); }}

function ibisSaveImg() {{
    try {{
        var src = network.getCanvas();
        var dst = document.createElement('canvas');
        dst.width=src.width; dst.height=src.height;
        var ctx=dst.getContext('2d');
        ctx.fillStyle='#0d1b2a'; ctx.fillRect(0,0,dst.width,dst.height);
        ctx.drawImage(src,0,0);
        var a=document.createElement('a');
        a.href=dst.toDataURL('image/png'); a.download='ibis_debate_map.png';
        document.body.appendChild(a); a.click(); document.body.removeChild(a);
    }} catch(e) {{ alert('Erro ao salvar: '+e.message); }}
}}

function ibisNewTab() {{
    try {{
        var blob=new Blob(['<!DOCTYPE html>'+document.documentElement.outerHTML],
            {{type:'text/html;charset=utf-8'}});
        window.open(URL.createObjectURL(blob),'_blank');
    }} catch(e) {{ alert('Permita pop-ups para esta página.'); }}
}}

network.on('stabilizationIterationsDone', function() {{
    _ibisSnap();
    if (_ibisPhysicsOn) {{
        _ibisPhysicsOn = false;
        network.stopSimulation();
        _ibisSetPhysBtn();
        var s = document.getElementById('ibis-status');
        s.textContent = '✓ Estabilizado';
        setTimeout(function(){{ if (!_ibisFocusMode) s.textContent=''; }}, 2500);
    }}
}});
</script>
"""
                _html_ibis = _html_ibis.replace("</body>", _itoolbar_js + "</body>", 1)

                # ── Legenda como badges acima do grafo ───────────────────────
                _has_cross = bool(_cross_found)
                _ibis_badges = [
                    '<span style="background:#f97316;color:#fff;padding:3px 10px;border-radius:12px;margin:2px 3px;font-size:12px;font-family:Segoe UI,system-ui,sans-serif;display:inline-block">⬬ Questão</span>',
                    '<span style="background:#2563eb;color:#dbeafe;padding:3px 10px;border-radius:12px;margin:2px 3px;font-size:12px;font-family:Segoe UI,system-ui,sans-serif;display:inline-block">◆ Alternativa</span>',
                    '<span style="background:#16a34a;color:#dcfce7;padding:3px 10px;border-radius:12px;margin:2px 3px;font-size:12px;font-family:Segoe UI,system-ui,sans-serif;display:inline-block">● A favor</span>',
                    '<span style="background:#b91c1c;color:#fee2e2;padding:3px 10px;border-radius:12px;margin:2px 3px;font-size:12px;font-family:Segoe UI,system-ui,sans-serif;display:inline-block">● Contra</span>',
                    '<span style="background:#14532d;color:#4ade80;padding:3px 10px;border-radius:12px;margin:2px 3px;font-size:12px;font-family:Segoe UI,system-ui,sans-serif;display:inline-block">▏ Decidida</span>',
                    '<span style="background:#451a03;color:#fbbf24;padding:3px 10px;border-radius:12px;margin:2px 3px;font-size:12px;font-family:Segoe UI,system-ui,sans-serif;display:inline-block">▏ Adiada</span>',
                    '<span style="background:#450a0a;color:#f87171;padding:3px 10px;border-radius:12px;margin:2px 3px;font-size:12px;font-family:Segoe UI,system-ui,sans-serif;display:inline-block">▏ Em aberto</span>',
                ]
                if _has_cross:
                    _ibis_badges.append(
                        '<span style="background:#581c87;color:#d8b4fe;padding:3px 10px;border-radius:12px;margin:2px 3px;font-size:12px;font-family:Segoe UI,system-ui,sans-serif;display:inline-block">╌ Debate recorrente</span>'
                    )
                st.markdown(
                    '<div style="margin-bottom:6px">' + "".join(_ibis_badges) + "</div>",
                    unsafe_allow_html=True,
                )

                _comp_ibis.html(_html_ibis, height=_ibis_height + 80, scrolling=False)

                # ── Tabela de cross-links detectados ─────────────────────────
                if _cross_found:
                    _cross_sorted = sorted(_cross_found, key=lambda x: x["sim"], reverse=True)
                    with st.expander(
                        f"🔗 {len(_cross_found)} debate(s) recorrente(s) detectado(s) entre reuniões",
                        expanded=True,
                    ):
                        st.caption(
                            "Questões com alto grau de similaridade textual em reuniões diferentes — "
                            "indício de um tema não resolvido que reaparece ao longo do projeto."
                        )
                        import pandas as _pd_cl
                        _cl_rows = []
                        for _cl in _cross_sorted:
                            _cl_rows.append({
                                "Reunião A": f"Reunião {_cl['mnum_a']}",
                                "Questão A": _cl["stmt_a"][:90] + ("…" if len(_cl["stmt_a"]) > 90 else ""),
                                "Reunião B": f"Reunião {_cl['mnum_b']}",
                                "Questão B": _cl["stmt_b"][:90] + ("…" if len(_cl["stmt_b"]) > 90 else ""),
                                "Similaridade": f"{_cl['sim']:.0%}",
                            })
                        st.dataframe(
                            _pd_cl.DataFrame(_cl_rows),
                            use_container_width=True,
                            hide_index=True,
                        )
                elif _cross_thresh <= 0.30:
                    st.caption(
                        f"Nenhum debate recorrente detectado com limiar {_cross_thresh:.0%}. "
                        "Tente reduzir o limiar nas opções do grafo."
                    )

            except ImportError:
                st.error(
                    "A biblioteca **pyvis** não está instalada. "
                    "Adicione `pyvis` ao `requirements.txt` e faça redeploy."
                )


