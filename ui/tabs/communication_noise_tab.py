# ui/tabs/communication_noise_tab.py
import streamlit as st

_AMBIGUITY_LABELS = {
    "lexical":          ("🔤 Lexical",          "#6f42c1"),
    "referential":      ("👤 Referencial",       "#0d6efd"),
    "vague_commitment": ("⏳ Compromisso vago",  "#fd7e14"),
    "syntactic":        ("🔀 Sintático",         "#20c997"),
}

_GAP_LABELS = {
    "unanswered_question":   ("❓ Pergunta sem resposta",    "#dc3545"),
    "abandoned_topic":       ("🚪 Tópico abandonado",       "#fd7e14"),
    "implicit_disagreement": ("⚡ Divergência implícita",   "#ffc107"),
    "missing_info":          ("📭 Informação ausente",       "#6c757d"),
    "interrupted_resumed":       ("✂️ Turno interrompido",      "#dc3545"),
    "repeated_unresolved_topic": ("🔁 Tema repetido e rejeitado", "#fd7e14"),
    "speaker_disqualification":  ("🚫 Desqualificação de falante", "#dc3545"),
}

_STRICT_GAP_KINDS = {"interrupted_resumed", "repeated_unresolved_topic", "speaker_disqualification"}

_SCORE_COLOR = [
    (0, 2,  "#28a745", "Excelente"),
    (2, 4,  "#5cb85c", "Boa"),
    (4, 6,  "#ffc107", "Moderada"),
    (6, 8,  "#fd7e14", "Alta"),
    (8, 10, "#dc3545", "Crítica"),
]


def _score_label(score: float) -> tuple[str, str]:
    for lo, hi, color, label in _SCORE_COLOR:
        if lo <= score < hi:
            return color, label
    return "#dc3545", "Crítica"


def render(hub, prefix=None, suffix=None):
    noise = getattr(hub, "communication_noise", None)
    if not noise or not noise.ready:
        st.info("Análise de ruídos de comunicação não disponível para esta reunião.")
        return

    n_amb = len(noise.ambiguities)
    n_gap = len(noise.gaps)
    score_color, score_label = _score_label(noise.noise_score)

    st.markdown("### Análise de Ruídos de Comunicação")
    st.caption(
        "Identifica **ambiguidades** (termos ou compromissos com múltiplas interpretações), "
        "**lacunas** (perguntas sem resposta, tópicos abandonados, divergências implícitas) e "
        "**dinâmica de turno** (dominância de fala, turnos interrompidos, temas repetidos e "
        "rejeitados, desqualificação de falantes) que podem causar mal-entendidos, retrabalho "
        "ou indicar disfunção na condução da reunião."
    )

    # KPI strip
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Índice de Ruído", f"{noise.noise_score:.1f} / 10")
    k2.metric("Qualidade geral", score_label)
    k3.metric("Ambiguidades", n_amb)
    k4.metric("Lacunas", n_gap)

    if noise.summary:
        st.markdown(
            f'<div style="background:#1e2939;border-left:3px solid {score_color};'
            f'padding:10px 14px;border-radius:4px;margin:8px 0;">'
            f'{noise.summary}</div>',
            unsafe_allow_html=True,
        )

    if noise.rejected_count:
        st.caption(
            f"🔍 {noise.rejected_count} sinal(is) de dinâmica de turno descartado(s) por falta de "
            f"evidência verificável (não aparece na lista abaixo)."
        )

    st.markdown("---")

    # ── Dominância de Fala ───────────────────────────────────────────────────
    dominance = getattr(noise, "dominance", None) or []
    if dominance:
        st.markdown("#### 🗣️ Dominância de Fala")
        st.caption(
            "Calculado por código a partir de tempo/turnos de fala reais — sem LLM. "
            "Falante em destaque concentra uma parcela desproporcional da conversa."
        )
        cols = st.columns(len(dominance))
        for col, d in zip(cols, dominance):
            label = f"⚠️ {d.speaker}" if d.dominant else d.speaker
            col.metric(label, f"{d.word_share_pct:.0f}% das palavras", f"{d.turns} turnos")
        if any(d.dominant for d in dominance):
            top = dominance[0]
            st.warning(
                f"**{top.speaker}** concentrou **{top.word_share_pct:.0f}%** das palavras da reunião "
                f"— acima do limiar de dominância (65%)."
            )
        st.markdown("---")

    # ── Risco de Atribuição de Falante ───────────────────────────────────────
    attribution_risks = getattr(noise, "attribution_risks", None) or []
    if attribution_risks:
        st.markdown("#### 🎙️ Risco de Atribuição de Falante")
        st.caption(
            "Participante mencionado na reunião mas sem nenhum turno próprio na transcrição — "
            "sinal de que a fala pode ter sido registrada sob outro rótulo (ex.: dispositivo/"
            "microfone compartilhado). Isto é um alerta de qualidade de dado, não uma correção: "
            "não é possível reatribuir falas com confiança só a partir do texto."
        )
        for risk in attribution_risks:
            st.warning(
                f"**{risk.mentioned_name}** é mencionado(a) mas nenhum turno está atribuído a "
                f"ela/ele na transcrição"
                + (f" — possivelmente misturado(a) com **{risk.possibly_merged_into}**"
                   if risk.possibly_merged_into else "")
                + f".\n\n*Evidência:* \"{risk.mentioned_context}\""
            )
        st.markdown("---")

    # ── Ambiguidades ─────────────────────────────────────────────────────────
    st.markdown(f"#### 🔍 Ambiguidades ({n_amb})")

    if not noise.ambiguities:
        st.success("Nenhuma ambiguidade relevante detectada.")
    else:
        for i, amb in enumerate(noise.ambiguities, 1):
            badge_text, badge_color = _AMBIGUITY_LABELS.get(
                amb.ambiguity_type, ("❔ Outro", "#888")
            )
            preview = amb.text[:70] + ("…" if len(amb.text) > 70 else "")
            with st.expander(f"{i}. {badge_text} — \"{preview}\"", expanded=False):
                cols = st.columns([3, 1])
                with cols[0]:
                    st.markdown(
                        f'<span style="background:{badge_color}22;color:{badge_color};'
                        f'padding:2px 8px;border-radius:3px;font-size:0.85em;">'
                        f'{badge_text}</span>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**Trecho:** *\"{amb.text}\"*")
                    if amb.speaker:
                        st.caption(f"Falante: **{amb.speaker}**")
                with cols[1]:
                    conf_pct = int(amb.confidence * 100)
                    st.metric("Confiança", f"{conf_pct}%")

                if amb.possible_interpretations:
                    st.markdown("**Interpretações possíveis:**")
                    for idx, interp in enumerate(amb.possible_interpretations, 1):
                        st.markdown(f"{idx}. {interp}")

                if amb.suggestion:
                    st.info(f"**Sugestão de esclarecimento:** {amb.suggestion}")

    st.markdown("---")

    # ── Lacunas ───────────────────────────────────────────────────────────────
    st.markdown(f"#### 🕳️ Lacunas de Comunicação ({n_gap})")

    if not noise.gaps:
        st.success("Nenhuma lacuna de comunicação relevante detectada.")
    else:
        for i, gap in enumerate(noise.gaps, 1):
            badge_text, badge_color = _GAP_LABELS.get(
                gap.gap_type, ("❔ Outro", "#888")
            )
            preview = gap.description[:70] + ("…" if len(gap.description) > 70 else "")
            with st.expander(f"{i}. {badge_text} — {preview}", expanded=False):
                st.markdown(
                    f'<span style="background:{badge_color}22;color:{badge_color};'
                    f'padding:2px 8px;border-radius:3px;font-size:0.85em;">'
                    f'{badge_text}</span>',
                    unsafe_allow_html=True,
                )
                st.markdown(f"**Descrição:** {gap.description}")

                meta_parts = []
                if gap.raised_by and gap.raised_by != "–":
                    meta_parts.append(f"Levantado por: **{gap.raised_by}**")
                if gap.topic:
                    meta_parts.append(f"Tema: **{gap.topic}**")
                if getattr(gap, "target_speaker", ""):
                    meta_parts.append(f"Falante afetado: **{gap.target_speaker}**")
                if getattr(gap, "confidence", ""):
                    meta_parts.append(f"Confiança: **{gap.confidence}**")
                if meta_parts:
                    st.caption("  |  ".join(meta_parts))

                references = getattr(gap, "references", None) or []
                if gap.gap_type in _STRICT_GAP_KINDS and references:
                    # Multi-quote grounding, verified verbatim against the transcript —
                    # show each reference in order instead of a single evidence_quote.
                    for ref in references:
                        ts = ref.get("timestamp", "")
                        spk = ref.get("speaker", "")
                        excerpt = ref.get("excerpt", "")
                        label = " — ".join(p for p in (ts, spk) if p)
                        st.markdown(
                            f'<div style="margin-bottom:4px;">'
                            f'<span style="color:#888;font-size:0.8em;">{label}</span><br>'
                            f'<blockquote style="border-left:3px solid #555;'
                            f'padding:6px 12px;color:#aaa;font-style:italic;margin:2px 0;">'
                            f'"{excerpt}"</blockquote></div>',
                            unsafe_allow_html=True,
                        )
                elif gap.evidence_quote:
                    st.markdown(
                        f'<blockquote style="border-left:3px solid #555;'
                        f'padding:6px 12px;color:#aaa;font-style:italic;">'
                        f'"{gap.evidence_quote}"</blockquote>',
                        unsafe_allow_html=True,
                    )

                impact_col, rec_col = st.columns(2)
                if gap.impact:
                    impact_col.warning(f"**Impacto potencial:** {gap.impact}")
                if gap.recommendation:
                    rec_col.success(f"**Recomendação:** {gap.recommendation}")
