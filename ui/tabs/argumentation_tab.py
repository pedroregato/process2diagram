# ui/tabs/argumentation_tab.py
import streamlit as st


_RESOLUTION_BADGE = {
    "decided":    ("✅ Decidida",   "#28a745"),
    "deferred":   ("⏳ Adiada",    "#ffc107"),
    "unresolved": ("❓ Em aberto", "#dc3545"),
}


def render(hub, prefix=None, suffix=None):
    arg = hub.argumentation
    if not arg or not arg.ready:
        st.info("Nenhum mapa argumentativo disponivel para esta reuniao.")
        return

    total  = len(arg.questions)
    dec    = arg.resolved_count
    unres  = arg.unresolved_count
    defer_ = total - dec - unres

    st.markdown("### Mapa de Argumentacao IBIS")
    st.caption(
        "Captura o **raciocinio** por tras das decisoes: quais alternativas foram consideradas, "
        "quem defendeu cada posicao, os argumentos levantados e as questoes que ficaram em aberto. "
        "Baseado na metodologia **IBIS — Issue-Based Information System**."
    )

    # KPI strip
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Questoes", total)
    k2.metric("Decididas", dec)
    k3.metric("Adiadas", defer_)
    k4.metric("Em aberto", unres)

    st.markdown("---")

    for q in arg.questions:
        badge_text, badge_color = _RESOLUTION_BADGE.get(
            q.resolution.type, ("?", "#888")
        )
        label = (
            f'<span style="color:{badge_color};font-weight:600;">{badge_text}</span> '
            f'— {q.statement[:90]}{"…" if len(q.statement) > 90 else ""}'
        )
        with st.expander(f"{q.id}: {q.statement[:80]}…" if len(q.statement) > 80 else f"{q.id}: {q.statement}", expanded=False):
            if q.raised_by:
                st.caption(f"Levantada por: **{q.raised_by}**")

            # Alternatives
            if q.alternatives:
                st.markdown("**Alternativas avaliadas:**")
                for alt in q.alternatives:
                    chosen_mark = " ✅ **(escolhida)**" if alt.was_chosen else ""
                    st.markdown(f"**{alt.id}** — {alt.description}{chosen_mark}")
                    if alt.proposed_by:
                        st.caption(f"Proposta por: {alt.proposed_by}")

                    cols_arg = st.columns(2)
                    if alt.pros:
                        cols_arg[0].success("**Pontos a favor:**\n" + "\n".join(f"- {p}" for p in alt.pros))
                    if alt.cons:
                        cols_arg[1].error("**Pontos contra:**\n" + "\n".join(f"- {c}" for c in alt.cons))

                    supporters = ", ".join(alt.supported_by) if alt.supported_by else None
                    opposers   = ", ".join(alt.opposed_by)   if alt.opposed_by   else None
                    if supporters or opposers:
                        sup_txt = f"A favor: {supporters}" if supporters else ""
                        opp_txt = f"Contra: {opposers}"    if opposers   else ""
                        st.caption(" | ".join(filter(None, [sup_txt, opp_txt])))

                    st.markdown("---")

            # Resolution
            res = q.resolution
            if res.type != "unresolved":
                st.markdown(f"**Resolucao:** {badge_text}")
                if res.rationale:
                    st.info(res.rationale)
                if res.with_caveats:
                    st.warning("**Ressalvas registradas:**\n" + "\n".join(f"- {c}" for c in res.with_caveats))
            else:
                st.error("Questao sem resolucao ao final da reuniao.")
