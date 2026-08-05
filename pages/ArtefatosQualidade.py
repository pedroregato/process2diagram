# pages/ArtefatosQualidade.py
# ─────────────────────────────────────────────────────────────────────────────
# Seção Artefatos (PC208) — assunto "Qualidade & Sinais": Ruídos de
# Comunicação e Provocações (PC190).
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
from core.project_store import update_provocation_status
from ui.project_selector import require_active_project
from ui.artefatos_shared import (
    inject_artefatos_css, render_artefatos_nav, noise_session_key,
    _load_meetings, _load_noise, _load_provocations,
)

apply_auth_gate()
inject_artefatos_css()

st.markdown("# 🔎 Artefatos — Qualidade & Sinais")

if not supabase_configured():
    st.error("⚙️ Supabase não configurado. Adicione as credenciais em Settings → Secrets.")
    st.stop()

project_id, project_name = require_active_project()
render_artefatos_nav("pages/ArtefatosQualidade.py")

_col_proj, _col_change = st.columns([5, 1])
with _col_proj:
    st.success(f"📁 **Contexto:** {project_name}")
with _col_change:
    st.page_link("pages/Home.py", label="Trocar")

meetings     = _load_meetings(project_id)
provocations = _load_provocations(project_id)  # tabela dedicada — leve, carrega sempre (PC190)

# Ruídos: lê do session_state se já carregado nesta sessão.
_NOISE_SS = noise_session_key(project_id)
noise_items = st.session_state.get(_NOISE_SS, None)

st.markdown("---")

tab_noise, tab_prov = st.tabs([
    f"🔊 Ruídos ({len(noise_items) if noise_items is not None else '…'})",
    f"🎭 Provocações ({len(provocations)})",
])

# ════════════════════════════════════════════════════════════════════════════
# TAB 11 — RUÍDOS DE COMUNICAÇÃO
# ════════════════════════════════════════════════════════════════════════════

_NOISE_AMB_LABELS = {
    "lexical":          ("🔤 Lexical",          "#6f42c1"),
    "referential":      ("👤 Referencial",       "#0d6efd"),
    "vague_commitment": ("⏳ Compromisso vago",  "#fd7e14"),
    "syntactic":        ("🔀 Sintático",         "#20c997"),
}
_NOISE_GAP_LABELS = {
    "unanswered_question":   ("❓ Pergunta sem resposta",    "#dc3545"),
    "abandoned_topic":       ("🚪 Tópico abandonado",       "#fd7e14"),
    "implicit_disagreement": ("⚡ Divergência implícita",   "#ffc107"),
    "missing_info":          ("📭 Informação ausente",       "#6c757d"),
}


def _noise_score_label(score: float) -> tuple[str, str]:
    for lo, hi, color, label in [
        (0, 2,  "#28a745", "Excelente"),
        (2, 4,  "#5cb85c", "Boa"),
        (4, 6,  "#ffc107", "Moderada"),
        (6, 8,  "#fd7e14", "Alta"),
        (8, 10, "#dc3545", "Crítica"),
    ]:
        if lo <= score < hi:
            return color, label
    return "#dc3545", "Crítica"


with tab_noise:
    st.caption(
        "**Ruídos de Comunicação** identificam **ambiguidades** (termos com múltiplas interpretações, "
        "compromissos vagos) e **lacunas** (perguntas sem resposta, tópicos abandonados, divergências implícitas) "
        "que podem gerar mal-entendidos ou retrabalho."
    )

    if _NOISE_SS not in st.session_state:
        with st.spinner("Buscando análise de ruídos..."):
            st.session_state[_NOISE_SS] = _load_noise(project_id)
        st.rerun()
    noise_items = st.session_state[_NOISE_SS]

    if st.button("🔄 Atualizar Ruídos", key="art_noise_refresh"):
        st.session_state.pop(_NOISE_SS, None)
        _load_noise.clear()
        st.rerun()

    if not noise_items:
        st.info("Nenhuma análise de ruídos registrada. Execute o pipeline com o agente Ruídos habilitado.")
    else:
        total_amb  = sum(len(n.get("ambiguities", [])) for n in noise_items)
        total_gap  = sum(len(n.get("gaps", [])) for n in noise_items)
        scores     = [n.get("noise_score", 0.0) for n in noise_items]
        avg_score  = sum(scores) / len(scores) if scores else 0.0
        _, avg_label = _noise_score_label(avg_score)

        kn1, kn2, kn3, kn4 = st.columns(4)
        kn1.metric("Reuniões analisadas", len(noise_items))
        kn2.metric("Índice médio de ruído", f"{avg_score:.1f} / 10")
        kn3.metric("Total de ambiguidades", total_amb)
        kn4.metric("Total de lacunas", total_gap)

        st.markdown("---")

        for _n in noise_items:
            _m_num   = _n.get("_meeting_number", "?")
            _m_title = _n.get("_meeting_title", "—")
            _score   = _n.get("noise_score", 0.0)
            _sc_color, _sc_label = _noise_score_label(_score)
            _ambs = _n.get("ambiguities", [])
            _gaps = _n.get("gaps", [])

            with st.expander(
                f"Reunião {_m_num} — {_m_title}  |  Ruído: {_score:.1f}/10 ({_sc_label})",
                expanded=False,
            ):
                if _n.get("summary"):
                    st.markdown(
                        f'<div style="background:#1e2939;border-left:3px solid {_sc_color};'
                        f'padding:10px 14px;border-radius:4px;margin:8px 0 12px 0;">'
                        f'{_n["summary"]}</div>',
                        unsafe_allow_html=True,
                    )

                _ca, _cg = st.columns(2)
                _ca.metric("Ambiguidades", len(_ambs))
                _cg.metric("Lacunas", len(_gaps))

                if _ambs:
                    st.markdown("**🔍 Ambiguidades**")
                    for _i, _amb in enumerate(_ambs, 1):
                        _badge, _bcol = _NOISE_AMB_LABELS.get(
                            _amb.get("ambiguity_type", ""), ("❔ Outro", "#888")
                        )
                        _txt = _amb.get("text", "")
                        _preview = _txt[:80] + ("…" if len(_txt) > 80 else "")
                        st.markdown(
                            f'<div style="border-left:3px solid {_bcol};padding:6px 10px;'
                            f'margin:4px 0;border-radius:0 4px 4px 0;">'
                            f'<span style="background:{_bcol}22;color:{_bcol};padding:1px 6px;'
                            f'border-radius:3px;font-size:0.8em;">{_badge}</span>'
                            f'&nbsp; <em>"{_preview}"</em>',
                            unsafe_allow_html=True,
                        )
                        if _amb.get("speaker"):
                            st.caption(f"Falante: **{_amb['speaker']}**")
                        _interps = _amb.get("possible_interpretations", [])
                        if _interps:
                            st.markdown("Interpretações possíveis:")
                            for _idx, _interp in enumerate(_interps, 1):
                                st.markdown(f"&nbsp;&nbsp;{_idx}. {_interp}")
                        if _amb.get("suggestion"):
                            st.info(f"Sugestão: {_amb['suggestion']}")

                if _gaps:
                    st.markdown("**🕳️ Lacunas**")
                    for _i, _gap in enumerate(_gaps, 1):
                        _badge, _bcol = _NOISE_GAP_LABELS.get(
                            _gap.get("gap_type", ""), ("❔ Outro", "#888")
                        )
                        _desc = _gap.get("description", "")
                        _preview = _desc[:80] + ("…" if len(_desc) > 80 else "")
                        st.markdown(
                            f'<div style="border-left:3px solid {_bcol};padding:6px 10px;'
                            f'margin:4px 0;border-radius:0 4px 4px 0;">'
                            f'<span style="background:{_bcol}22;color:{_bcol};padding:1px 6px;'
                            f'border-radius:3px;font-size:0.8em;">{_badge}</span>'
                            f'&nbsp; {_preview}',
                            unsafe_allow_html=True,
                        )
                        _meta = []
                        if _gap.get("raised_by") and _gap["raised_by"] != "–":
                            _meta.append(f"Levantado por: **{_gap['raised_by']}**")
                        if _gap.get("topic"):
                            _meta.append(f"Tema: **{_gap['topic']}**")
                        if _meta:
                            st.caption("  |  ".join(_meta))
                        if _gap.get("evidence_quote"):
                            st.markdown(
                                f'<blockquote style="border-left:3px solid #555;padding:6px 12px;'
                                f'color:#aaa;font-style:italic;">"{_gap["evidence_quote"]}"</blockquote>',
                                unsafe_allow_html=True,
                            )
                        _gi1, _gi2 = st.columns(2)
                        if _gap.get("impact"):
                            _gi1.warning(f"Impacto: {_gap['impact']}")
                        if _gap.get("recommendation"):
                            _gi2.success(f"Recomendação: {_gap['recommendation']}")

# ════════════════════════════════════════════════════════════════════════════
# TAB 12 — PROVOCAÇÕES (PC190, melhorias/arquivados/agente-de-provocacoes.md)
# ════════════════════════════════════════════════════════════════════════════
with tab_prov:
    st.caption(
        "**Provocações** — observações sobre o que ficou fechado numa reunião sem ter sido "
        "examinado: tema ausente, objeção sem resposta, afirmação categórica aceita sem "
        "contestação, ou contradição com uma reunião anterior. Cada uma carrega evidência "
        "verificável — citação com timestamp conferida por um validador determinístico, ou "
        "referência a uma contradição já detectada entre duas reuniões — nenhuma sai sem lastro."
    )

    if not st.session_state.get("run_provocations", True):
        st.info(
            "🎭 A geração de provocações está desligada para esta sessão. Ative em "
            "**Pipeline → ⚙️ Configuração Avançada → 🎭 Gerar Provocações** (ligado por padrão) "
            "para que novas reuniões processadas produzam provocações automaticamente.",
            icon="ℹ️",
        )

    _prov_kind_label = {
        "absence": "Ausente estrutural", "asymmetry": "Assimetria discursiva",
        "contradiction": "Contradição no tempo", "premise": "Premissa não examinada",
        "analogy": "Analogia estrutural",
    }
    _prov_conf_color = {"high": "#1a7f5a", "medium": "#c97b1a"}
    _prov_status_label = {
        "new": "Nova", "accepted": "Aceita", "discarded": "Descartada",
        "became_divergence": "Virou divergência",
    }
    _meeting_num_by_id = {m["id"]: m.get("meeting_number", "?") for m in meetings}

    _prov_filter = st.radio(
        "Filtro", ["Novas", "Aceitas", "Descartadas", "Todas"],
        horizontal=True, label_visibility="collapsed", key="prov_filter",
    )
    _status_map = {"Novas": "new", "Aceitas": "accepted", "Descartadas": "discarded", "Todas": None}
    _wanted_status = _status_map[_prov_filter]
    _visible = provocations if _wanted_status is None else [
        p for p in provocations if p.get("status") == _wanted_status
    ]

    if not provocations:
        st.success(
            "Nenhuma provocação gerada ainda neste projeto. Isso pode significar que ainda não "
            "há reuniões processadas com o recurso ativo — ou que as reuniões existentes não "
            "tinham nada com lastro suficiente para apontar, o que também é um resultado válido.",
            icon="🎭",
        )
    elif not _visible:
        st.info(f"Nenhuma provocação com status **{_prov_filter.lower()}**.", icon="🎭")
    else:
        for p in _visible:
            _kind = p.get("kind", "")
            _conf = p.get("confidence", "medium")
            _status = p.get("status", "new")
            _num = _meeting_num_by_id.get(p.get("meeting_id"), "?")
            _ccolor = _prov_conf_color.get(_conf, "#8a8070")

            with st.expander(f"**{p.get('title', '(sem título)')}** — Reunião {_num}"):
                _b1, _b2, _b3 = st.columns(3)
                _b1.caption(f"Tipo: **{_prov_kind_label.get(_kind, _kind)}**")
                _b2.markdown(
                    f'<span style="background:{_ccolor}22;color:{_ccolor};padding:1px 8px;'
                    f'border-radius:3px;font-size:0.85em;">Confiança: {_conf}</span>',
                    unsafe_allow_html=True,
                )
                _b3.caption(f"Status: **{_prov_status_label.get(_status, _status)}**")

                st.markdown(p.get("body", ""))
                st.info(f"❓ {p.get('question', '')}")

                _grounding = p.get("grounding") or {}
                if _kind == "contradiction":
                    # Bridge determinístico a partir de kh_contradictions — sem
                    # citação transcript-literal (a evidência é a linha de
                    # contradição já detectada por AgentContradictionDetector).
                    _num_a = _meeting_num_by_id.get(_grounding.get("meeting_a_id"), "?")
                    _num_b = _meeting_num_by_id.get(_grounding.get("meeting_b_id"), "?")
                    st.caption(
                        f"**Lastro:** contradição entre **Reunião {_num_a}** e "
                        f"**Reunião {_num_b}** — tipo `{_grounding.get('relation_type','—')}` "
                        f"(detectada por AgentContradictionDetector, ver aba Knowledge Hub)."
                    )
                    if _grounding.get("suggested_rewrite"):
                        st.markdown(f"💡 Sugestão de reescrita: _{_grounding['suggested_rewrite']}_")
                else:
                    _refs = _grounding.get("references") or []
                    _absent = (_grounding.get("absence_check") or {}).get("terms") or []
                    _markers = _grounding.get("premise_markers") or []
                    if _refs or _absent or _markers:
                        st.caption("**Lastro:**")
                        for _r in _refs:
                            st.markdown(
                                f'<blockquote style="border-left:3px solid #555;padding:4px 10px;'
                                f'color:#888;font-style:italic;font-size:0.9em;">'
                                f'[{_r.get("timestamp","")}] {_r.get("speaker","")}: '
                                f'"{_r.get("excerpt","")}"</blockquote>',
                                unsafe_allow_html=True,
                            )
                        if _absent:
                            _span_desc = (
                                "em toda a transcrição" if _kind == "absence"
                                else "entre os dois momentos citados acima"
                            )
                            st.caption(f"Termos verificados, sem ocorrência {_span_desc}: " + ", ".join(_absent))
                        if _markers:
                            st.caption("Marcador de assertiva categórica identificado: " + ", ".join(_markers))

                if _status == "new":
                    _a1, _a2 = st.columns(2)
                    if _a1.button("✅ Aceitar", key=f"prov_acc_{p['id']}", use_container_width=True):
                        if update_provocation_status(p["id"], "accepted"):
                            _load_provocations.clear()
                            st.toast("Provocação aceita.", icon="✅")
                            st.rerun()
                        else:
                            st.error("Erro ao atualizar — tente novamente.")
                    if _a2.button("🗑️ Descartar", key=f"prov_disc_{p['id']}", use_container_width=True):
                        if update_provocation_status(p["id"], "discarded"):
                            _load_provocations.clear()
                            st.toast("Provocação descartada.", icon="🗑️")
                            st.rerun()
                        else:
                            st.error("Erro ao atualizar — tente novamente.")

