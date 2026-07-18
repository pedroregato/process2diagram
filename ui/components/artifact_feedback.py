# ui/components/artifact_feedback.py
# ─────────────────────────────────────────────────────────────────────────────
# Componente reutilizável de avaliação leve de artefato
# (melhorias/arquivados/aprimoramento-metacognitivo-3camadas.md, Camada 1,
# PC191) — usado em pages/Artefatos.py (BPMN, Reuniões).
#
# Uso:
#   from ui.components.artifact_feedback import render_artifact_feedback
#   if render_artifact_feedback(project_id, "bpmn_process", pid, key_suffix=pid):
#       st.rerun()
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import streamlit as st

from core.project_store import save_feedback


def render_artifact_feedback(
    project_id: str,
    artifact_type: str,
    artifact_id: str,
    *,
    key_suffix: str,
    meeting_id: str | None = None,
    created_by: str | None = None,
) -> bool:
    """Renderiza o gesto de avaliação (⭐ 1-5 + "aceitável?" + comentário
    opcional) para um artefato gerado (processo BPMN, ata de reunião).

    Segue o mesmo padrão de `ui/components/promote_asset.py::render_promote_button()`:
    toggle via `st.button()` (não `st.expander()` — vários chamadores já
    renderizam este componente de dentro de um expander próprio, e Streamlit
    não permite expander aninhado) envolvido num único `st.container()` —
    contribui exatamente 1 elemento ao pai independente do ramo renderizado,
    evitando o "Bad 'setIn' index" já documentado em CLAUDE.md.

    Retorna True se uma avaliação foi registrada nesta execução — o chamador
    deve reagir com `st.rerun()` para o estado refletir a mudança.
    """
    form_key = f"feedback_form_{artifact_type}_{key_suffix}"
    toggle_key = f"{form_key}_show"

    with st.container():
        if st.button("⭐ Avaliar", key=f"{form_key}_toggle_btn"):
            st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)

        if not st.session_state.get(toggle_key):
            return False

        with st.form(form_key):
            stars = st.feedback("stars", key=f"{form_key}_stars")
            acceptable = st.checkbox("✅ Aceitável para uso", key=f"{form_key}_acceptable")
            comment = st.text_area("Comentário (opcional)", key=f"{form_key}_comment")

            if st.form_submit_button("Enviar avaliação", type="primary"):
                if stars is None:
                    st.error("Selecione uma nota antes de enviar.")
                    return False
                rating = stars + 1  # st.feedback("stars") retorna índice 0-4
                ok = save_feedback(
                    project_id, artifact_type, artifact_id, rating,
                    is_acceptable=acceptable,
                    comment=comment,
                    meeting_id=meeting_id,
                    created_by=created_by or "",
                )
                if ok:
                    st.session_state[toggle_key] = False
                    st.success("Avaliação registrada. Obrigado!")
                    return True
                st.error("Erro ao registrar avaliação — tente novamente.")
                return False
    return False
