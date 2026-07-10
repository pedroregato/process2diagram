# ui/components/promote_asset.py
# ─────────────────────────────────────────────────────────────────────────────
# Componente reutilizável de promoção a Ativo de Negócio
# (melhorias/promocao-ativos-negocio.md, Fase A) — usado em pages/Artefatos.py
# (Requisitos/BPMN/SBVR/Reuniões), pages/DocumentManager.py (Fase B) e
# pages/Assistente.py (Fase C).
#
# Uso:
#   from ui.components.promote_asset import render_promote_button
#   if render_promote_button(project_id, "requirement", req["id"],
#                             title=f"{req['req_number']} — {req['title']}",
#                             key_suffix=req["id"], already_promoted=req["id"] in promoted_ids):
#       st.rerun()
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import streamlit as st

from core.project_store import (
    promote_to_business_asset,
    promote_assistant_output_to_asset,
    BUSINESS_INTEREST_OPTIONS,
    BUSINESS_PERSPECTIVE_OPTIONS,
    FORMAL_CLASSIFICATION_OPTIONS,
)

INTEREST_LABELS = {
    "estrategico": "🎯 Estratégico",
    "tatico": "📐 Tático",
    "operacional": "⚙️ Operacional",
}

PERSPECTIVE_LABELS = {
    "comercial": "Comercial",
    "compliance": "Compliance",
    "compras_suprimentos": "Compras e Suprimentos",
    "contabilidade": "Contabilidade",
    "financeiro": "Financeiro",
    "governanca": "Governança",
    "juridico": "Jurídico",
    "logistica": "Logística",
    "marketing": "Marketing",
    "operacoes": "Operações",
    "rh": "RH",
    "ti": "TI/Tecnologia",
}

FORMAL_CLASSIFICATION_LABELS = {
    "AN-01": "AN-01 · Ativos Estratégicos",
    "AN-02": "AN-02 · Ativos de Capacidade",
    "AN-03": "AN-03 · Ativos de Processo",
    "AN-04": "AN-04 · Ativos de Produto e Serviço",
    "AN-05": "AN-05 · Ativos de Informação e Dados",
    "AN-06": "AN-06 · Ativos Digitais e Tecnológicos",
    "AN-07": "AN-07 · Ativos Documentais e Normativos",
    "AN-08": "AN-08 · Ativos Contratuais e Relacionais",
    "AN-09": "AN-09 · Ativos Organizacionais e Humanos",
    "AN-10": "AN-10 · Ativos Financeiros e de Performance",
    "AN-11": "AN-11 · Ativos de Governança, Risco e Conformidade",
    "AN-12": "AN-12 · Ativos de Conhecimento, IA e Automação",
}

NO_CLASSIFICATION = "— (não classificar agora)"


def render_classification_fields(
    key_prefix: str,
    default_formal_classification: str | None = None,
    *,
    default_interest: str | None = None,
    default_perspective: list[str] | None = None,
    default_justification: str = "",
):
    """Renderiza os 4 campos de classificação da promoção (Interesse,
    Perspectiva, Classificação Formal, Justificativa) sem os envolver num
    `st.form` — usado por `render_promote_button()` (item único, sem
    defaults — promoção nova), pela promoção em lote em `pages/Artefatos.py`
    (mesmos campos, aplicados a vários itens de uma vez) e pela edição de um
    ativo já promovido em `pages/AtivosDeNegocio.py` (com defaults = valores
    já salvos, permitindo reclassificar sem perder o que já foi escolhido).

    Retorna (interest, perspective, classification_or_None, justification).
    """
    interest = st.selectbox(
        "Interesse para o Negócio *",
        BUSINESS_INTEREST_OPTIONS,
        index=BUSINESS_INTEREST_OPTIONS.index(default_interest) if default_interest in BUSINESS_INTEREST_OPTIONS else 0,
        format_func=lambda v: INTEREST_LABELS.get(v, v),
        key=f"{key_prefix}_interest",
    )
    perspective = st.multiselect(
        "Perspectiva * (uma ou mais áreas)",
        BUSINESS_PERSPECTIVE_OPTIONS,
        default=[p for p in (default_perspective or []) if p in BUSINESS_PERSPECTIVE_OPTIONS],
        format_func=lambda v: PERSPECTIVE_LABELS.get(v, v),
        key=f"{key_prefix}_perspective",
    )
    classification_options = [NO_CLASSIFICATION] + FORMAL_CLASSIFICATION_OPTIONS
    default_idx = (
        classification_options.index(default_formal_classification)
        if default_formal_classification in FORMAL_CLASSIFICATION_OPTIONS
        else 0
    )
    classification = st.selectbox(
        "Classificação Formal (opcional)",
        classification_options,
        index=default_idx,
        format_func=lambda v: FORMAL_CLASSIFICATION_LABELS.get(v, v),
        key=f"{key_prefix}_classification",
    )
    justification = st.text_area(
        "Justificativa * — por que este ativo interessa ao negócio como um todo?",
        value=default_justification,
        key=f"{key_prefix}_justification",
    )
    return (
        interest,
        perspective,
        classification if classification != NO_CLASSIFICATION else None,
        justification,
    )


def render_promote_button(
    project_id: str,
    artifact_type: str,
    artifact_id: str,
    *,
    title: str,
    key_suffix: str,
    already_promoted: bool = False,
    default_formal_classification: str | None = None,
    created_by: str | None = None,
) -> bool:
    """Renderiza o gesto de promoção a Ativo de Negócio para um artefato.

    Se `already_promoted` for True, mostra só um badge informativo (a edição
    de metadados de um ativo já promovido acontece na Central de Ativos, não
    aqui — evita duas telas fazendo a mesma coisa). Caso contrário, mostra o
    formulário de promoção com as 3 classificações obrigatórias + Justificativa.

    `default_formal_classification` — pré-seleção sugerida (ex.: derivada de
    `document_types.category` para documentos, Fase B); o usuário sempre pode
    trocar, nunca é forçado.

    Retorna True se uma promoção foi concluída nesta execução — o chamador
    deve reagir com `st.rerun()` para a lista refletir o novo estado.
    """
    form_key = f"promote_form_{artifact_type}_{key_suffix}"
    toggle_key = f"{form_key}_show"

    # Slot único e estável: do ponto de vista do container-pai, esta função
    # sempre contribui exatamente 1 elemento (este st.container()), não
    # importa qual ramo (já promovido / toggle fechado / toggle aberto com
    # formulário) é renderizado dentro dele. Sem isso, a contagem de filhos
    # na árvore muda entre reruns (1 elemento fechado vs vários com o
    # formulário aberto) e o frontend do Streamlit quebra com
    # "Bad 'setIn' index" ao tentar reaplicar deltas numa árvore que mudou
    # de forma — mesmo padrão já documentado em ui/tabs/bpmn_tabs.py.
    with st.container():
        if already_promoted:
            st.caption("✅ Já é um ativo de negócio — edite a classificação na Central de Ativos.")
            return False

        # Toggle em vez de st.expander — vários chamadores (Reuniões/SBVR em
        # Artefatos.py, Biblioteca em DocumentManager.py) já renderizam este
        # botão de dentro de um st.expander próprio; Streamlit não permite
        # expander aninhado (StreamlitAPIException).
        if st.button(f"⭐ Promover a Ativo de Negócio", key=f"{form_key}_toggle_btn"):
            st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)

        if not st.session_state.get(toggle_key):
            return False

        st.markdown(f"**⭐ Promover a Ativo de Negócio — {title}**")
        with st.form(form_key):
            interest, perspective, classification, justification = render_classification_fields(
                form_key, default_formal_classification,
            )
            col_owner, col_tags = st.columns(2)
            with col_owner:
                owner = st.text_input("Responsável", key=f"{form_key}_owner")
            with col_tags:
                tags_raw = st.text_input("Tags (separadas por vírgula)", key=f"{form_key}_tags")

            if st.form_submit_button("⭐ Promover", type="primary"):
                if not interest or not perspective or not justification.strip():
                    st.error("Interesse, Perspectiva e Justificativa são obrigatórios.")
                    return False
                tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()]
                result = promote_to_business_asset(
                    project_id, artifact_type, artifact_id,
                    business_interest=interest,
                    business_perspective=perspective,
                    promotion_justification=justification.strip(),
                    formal_classification=classification,
                    owner=owner.strip() or None,
                    tags=tags_list,
                    created_by=created_by,
                )
                if result:
                    st.session_state[toggle_key] = False
                    st.success("Ativo promovido com sucesso.")
                    return True
                st.error("Erro ao promover — tente novamente.")
                return False
    return False


def render_promote_assistant_content_button(
    project_id: str,
    title: str,
    content_markdown: str,
    *,
    key_suffix: str,
    source_tool: str | None = None,
    meeting_id: str | None = None,
    created_by: str | None = None,
) -> bool:
    """Promoção de conteúdo gerado pelo Assistente (Fase C,
    melhorias/promocao-ativos-negocio.md §6) — diferente de
    `render_promote_button()`, aqui não existe uma linha de origem: a
    promoção CRIA o snapshot em `assistant_artifacts` e promove numa única
    chamada (`promote_assistant_output_to_asset`).

    `title` pré-preenche o campo (editável — a primeira linha da resposta do
    Assistente raramente é um bom título por si só). Retorna True se
    promovido nesta execução — o chamador deve reagir com `st.rerun()`.
    """
    form_key = f"promote_assistant_form_{key_suffix}"
    # Toggle em vez de st.expander — mesmo motivo de render_promote_button():
    # nunca assumir que o chamador não está dentro de outro expander.
    toggle_key = f"{form_key}_show"

    # Slot único e estável — mesmo motivo de render_promote_button(): evita
    # "Bad 'setIn' index" no frontend quando a contagem de filhos muda entre
    # reruns (toggle fechado vs formulário aberto).
    with st.container():
        if st.button("⭐ Promover esta resposta a Ativo de Negócio", key=f"{form_key}_toggle_btn"):
            st.session_state[toggle_key] = not st.session_state.get(toggle_key, False)

        if not st.session_state.get(toggle_key):
            return False

        with st.form(form_key):
            asset_title = st.text_input("Título do ativo *", value=title, key=f"{form_key}_title")
            interest, perspective, classification, justification = render_classification_fields(form_key)

            if st.form_submit_button("⭐ Promover", type="primary"):
                if not asset_title.strip() or not interest or not perspective or not justification.strip():
                    st.error("Título, Interesse, Perspectiva e Justificativa são obrigatórios.")
                    return False
                result = promote_assistant_output_to_asset(
                    project_id, asset_title.strip(), content_markdown,
                    business_interest=interest,
                    business_perspective=perspective,
                    promotion_justification=justification.strip(),
                    formal_classification=classification,
                    source_tool=source_tool,
                    meeting_id=meeting_id,
                    created_by=created_by,
                )
                if result:
                    st.session_state[toggle_key] = False
                    st.success("Conteúdo salvo e promovido a ativo de negócio.")
                    return True
                st.error("Erro ao promover — tente novamente.")
                return False
    return False
