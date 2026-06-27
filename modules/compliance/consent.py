# modules/compliance/consent.py
# ─────────────────────────────────────────────────────────────────────────────
# Post-pipeline LGPD consent panel (PC81).
#
# render_consent_panel() is called from pages/Pipeline.py AFTER the meeting
# is created and saved — this solves the chicken-and-egg problem (meeting_id
# is available, pipeline results are already persisted).
#
# The panel is non-blocking: it appears as an expander alongside results.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

import streamlit as st

from modules.compliance.detector import PIIDetectionResult
from modules.compliance.audit import log_audit_event


_LEGAL_BASIS_OPTIONS: dict[str, str] = {
    "legitimo_interesse": "Legítimo Interesse (Art. 7°, IX)",
    "consentimento":      "Consentimento Explícito (Art. 7°, I)",
    "contrato":           "Execução de Contrato (Art. 7°, V)",
    "obrigacao_legal":    "Obrigação Legal (Art. 7°, II)",
}

_RISK_ICON = {"low": "🟢", "medium": "🟡", "high": "🔴"}
_RISK_LABEL = {"low": "Baixo", "medium": "Médio", "high": "Alto"}

_CAT_LABELS: dict[str, str] = {
    "CPF":        "CPFs",
    "CNPJ":       "CNPJs",
    "EMAIL":      "E-mails",
    "TEL":        "Telefones",
    "VALOR":      "Valores monetários",
    "NOME_PESSOA": "Nomes de pessoas",
}


def render_consent_panel(
    meeting_id: str,
    pii_result: PIIDetectionResult,
    project_id: Optional[str] = None,
    user_login: Optional[str] = None,
) -> bool:
    """
    Render the LGPD compliance consent panel in the Pipeline page.

    Call this AFTER create_meeting() and save_meeting_artifacts() so that
    meeting_id is available and the transcript is already stored.

    Parameters
    ----------
    meeting_id  : UUID of the newly created meeting.
    pii_result  : output of detect_pii(hub.transcript_raw).
    project_id  : active project UUID (optional, stored in consent record).
    user_login  : username from auth.get_current_user().

    Returns
    -------
    bool — True if consent is already recorded for this meeting in this session.
    """
    _session_key = f"_consent_granted_{meeting_id}"

    if st.session_state.get(_session_key):
        st.success("Conformidade LGPD registrada para esta reunião.", icon="🔒")
        return True

    risk_icon  = _RISK_ICON.get(pii_result.risk_level, "🟡")
    risk_label = _RISK_LABEL.get(pii_result.risk_level, "Médio")
    header     = f"🔒 Conformidade LGPD — {risk_icon} Risco {risk_label}"

    with st.expander(header, expanded=pii_result.risk_level == "high"):
        st.caption(
            "Registre a base legal para o tratamento dos dados pessoais identificados "
            "nesta transcrição (LGPD Art. 7°). O registro fica na trilha de auditoria."
        )

        if pii_result.has_pii:
            _render_pii_summary(pii_result)
        else:
            st.info(
                "Nenhum dado pessoal estruturado detectado (CPF, e-mail, etc.).",
                icon="ℹ️",
            )

        with st.form(key=f"lgpd_consent_{meeting_id}"):
            legal_basis = st.selectbox(
                "Base legal para o tratamento",
                options=list(_LEGAL_BASIS_OPTIONS.keys()),
                format_func=lambda k: _LEGAL_BASIS_OPTIONS[k],
                index=0,
            )
            participant_type = st.radio(
                "Perfil dos participantes",
                options=["interno", "externo", "misto"],
                format_func=lambda x: {
                    "interno": "Interno (funcionários / pesquisadores)",
                    "externo": "Externo (clientes / convidados)",
                    "misto":   "Misto (internos e externos)",
                }[x],
                horizontal=True,
            )
            if participant_type in ("externo", "misto"):
                st.warning(
                    "Participantes externos requerem **Consentimento explícito** (Art. 7°, I). "
                    "Selecione a base legal correspondente acima.",
                    icon="⚠️",
                )

            retention_days = st.select_slider(
                "Prazo de retenção",
                options=[30, 60, 90, 180, 365],
                value=60,
                format_func=lambda x: f"{x} dias",
            )
            notes = st.text_area(
                "Observações (opcional)",
                height=68,
                max_chars=500,
                placeholder="Ex.: reunião autorizada pelo DPO em 2026-01-10",
            )

            if st.form_submit_button("Registrar Consentimento", type="primary"):
                _persist_consent(
                    meeting_id=meeting_id,
                    project_id=project_id,
                    user_login=user_login,
                    legal_basis=legal_basis,
                    participant_type=participant_type,
                    retention_days=retention_days,
                    pii_result=pii_result,
                    notes=notes,
                )
                st.session_state[_session_key] = True
                st.success("Consentimento LGPD registrado.", icon="🔒")
                return True

    return bool(st.session_state.get(_session_key))


# ── Internal helpers ──────────────────────────────────────────────────────────

def _render_pii_summary(pii_result: PIIDetectionResult) -> None:
    items = list(pii_result.categories.items())
    cols  = st.columns(min(len(items), 3) or 1)
    for i, (cat, count) in enumerate(items):
        cols[i % len(cols)].metric(_CAT_LABELS.get(cat, cat), count)

    if pii_result.persons_detected:
        with st.expander("Nomes identificados (NER — somente para ciência)"):
            st.caption(
                "Detectados via análise linguística (spaCy NER). "
                "Estes nomes **não foram anonimizados** — certifique-se de que a "
                "base legal selecionada cobre o tratamento desses dados."
            )
            st.write(", ".join(pii_result.persons_detected))


def _persist_consent(
    *,
    meeting_id: str,
    project_id: Optional[str],
    user_login: Optional[str],
    legal_basis: str,
    participant_type: str,
    retention_days: int,
    pii_result: PIIDetectionResult,
    notes: str,
) -> None:
    """Write consent record to DB and log audit event. Fail-open."""
    expires_at = (
        datetime.now(timezone.utc) + timedelta(days=retention_days)
    ).isoformat()

    try:
        from modules.supabase_client import get_supabase_client
        sb = get_supabase_client()
        if sb:
            row: dict = {
                "meeting_id":      meeting_id,
                "granted_by":      user_login or "unknown",
                "legal_basis":     legal_basis,
                "participant_type": participant_type,
                "retention_days":  retention_days,
                "pii_detected":    pii_result.summary,
                "expires_at":      expires_at,
                "notes":           notes,
            }
            if project_id:
                row["project_id"] = project_id
            sb.table("compliance_consent").insert(row).execute()
    except Exception:
        pass  # fail-open

    log_audit_event(
        "consent_granted",
        meeting_id=meeting_id,
        project_id=project_id,
        user_login=user_login,
        details={
            "legal_basis":      legal_basis,
            "participant_type": participant_type,
            "retention_days":   retention_days,
            "pii_risk_level":   pii_result.risk_level,
            "pii_categories":   list(pii_result.categories.keys()),
        },
    )
