# ui/components/quality_badge.py
# ─────────────────────────────────────────────────────────────────────────────
# Renderiza badge de qualidade de outcome por agente.
# Usa hub.validation.agent_scores (populado por AgentValidator.validate_all).
# Exibido como st.popover com detalhe de cada check.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations
import streamlit as st


def render_quality_badge(hub, agent_name: str) -> None:
    """
    Exibe um badge colorido com score do agente e popover de detalhes.
    Silencioso quando agent_scores não foi populado (pipeline antigo ou sem execução).
    """
    scores = getattr(getattr(hub, "validation", None), "agent_scores", {})
    outcome = scores.get(agent_name)
    if outcome is None:
        return

    score = outcome.score
    passed = outcome.passed

    if score >= 8.0:
        color, icon = "#16a34a", "✅"
    elif score >= 6.0:
        color, icon = "#ca8a04", "⚠️"
    else:
        color, icon = "#dc2626", "❌"

    label = f"{icon} {score:.1f}/10"

    with st.popover(label, use_container_width=False):
        st.markdown(f"**Outcome — {agent_name}**")
        if outcome.checks:
            for check_label, ok in outcome.checks.items():
                if check_label == "agent_skipped":
                    st.caption("⏭️ Agente não executado nesta sessão.")
                    continue
                status_icon = "✅" if ok else "❌"
                st.markdown(f"{status_icon} {check_label}")
        if outcome.warnings:
            st.markdown("---")
            for w in outcome.warnings:
                st.warning(w, icon="⚠️")
        if passed:
            st.success("Todos os critérios obrigatórios passaram.", icon="✅")
        else:
            st.error("Um ou mais critérios falharam.", icon="❌")
