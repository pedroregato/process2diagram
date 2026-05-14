# modules/report_builder.py
# ─────────────────────────────────────────────────────────────────────────────
# Standalone executive report generator.
#
# Reconstructs a minimal KnowledgeHub from Supabase data and runs only
# AgentSynthesizer — no full pipeline reprocessing required.
#
# Public API:
#   build_report_for_meeting(meeting_id, llm_config, output_language) -> ReportResult
#   build_reports_for_project(project_id, llm_config, output_language, callback) -> list[ReportResult]
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class ReportResult:
    meeting_id: str
    meeting_number: int
    meeting_title: str
    success: bool
    html: str = ""
    error: str = ""
    tokens_used: int = 0
    provider: str = ""


def build_report_for_meeting(
    meeting_id: str,
    llm_config: dict,
    output_language: str = "Portuguese (BR)",
) -> ReportResult:
    """
    Generate an executive HTML report for a single meeting.

    Reads from Supabase:
      meetings         → title, number, minutes_md, transcript_clean, meeting_type
      requirements     → list of requirements
      sbvr_terms       → vocabulary terms
      sbvr_rules       → business rules
      bpmn_processes   → BPMN XML (latest version)

    Builds a minimal KnowledgeHub and runs AgentSynthesizer only.
    Persists the result back to meetings.report_html.
    """
    from core.project_store import (
        get_supabase_client, save_report_html
    )
    from core.knowledge_hub import (
        KnowledgeHub, MinutesModel, RequirementsModel, Requirement,
        SBVREnvelope, SBVRTerm, SBVRRule, BMMEnvelope, BPMNModel,
        SynthesizerEnvelope
    )
    from agents.agent_synthesizer import AgentSynthesizer

    client = get_supabase_client()
    if client is None:
        return ReportResult(
            meeting_id=meeting_id, meeting_number=0, meeting_title="",
            success=False, error="Supabase não configurado."
        )

    # ── 1. Load meeting base data ─────────────────────────────────────────────
    try:
        mtg = (
            client.table("meetings")
            .select("id, meeting_number, title, minutes_md, transcript_clean, meeting_type")
            .eq("id", meeting_id)
            .single()
            .execute()
        ).data
    except Exception as e:
        return ReportResult(
            meeting_id=meeting_id, meeting_number=0, meeting_title="",
            success=False, error=f"Erro ao buscar reunião: {e}"
        )

    meeting_number = mtg.get("meeting_number", 0)
    meeting_title  = mtg.get("title", "")

    # ── 2. Build minimal KnowledgeHub ─────────────────────────────────────────
    hub = KnowledgeHub.new()
    hub.transcript_clean = mtg.get("transcript_clean") or ""
    hub.transcript_raw   = hub.transcript_clean

    # Minutes — parse from minutes_md stored text
    minutes_md = mtg.get("minutes_md") or ""
    if minutes_md:
        hub.minutes = _parse_minutes_from_md(minutes_md)

    # Requirements
    try:
        reqs_data = (
            client.table("requirements")
            .select("req_id, title, description, req_type, priority, status, source_speaker")
            .eq("meeting_id", meeting_id)
            .execute()
        ).data or []
        hub.requirements = _build_requirements_model(reqs_data)
    except Exception:
        hub.requirements = RequirementsModel()

    # SBVR
    try:
        terms_data = (
            client.table("sbvr_terms")
            .select("term, definition, category")
            .eq("meeting_id", meeting_id)
            .execute()
        ).data or []
        rules_data = (
            client.table("sbvr_rules")
            .select("rule_text, rule_type, source")
            .eq("meeting_id", meeting_id)
            .execute()
        ).data or []
        hub.sbvr = _build_sbvr_envelope(terms_data, rules_data)
    except Exception:
        hub.sbvr = SBVREnvelope()

    # BPMN — latest version
    try:
        bpmn_rows = (
            client.table("bpmn_processes")
            .select("bpmn_xml, mermaid_code, process_name")
            .eq("meeting_id", meeting_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        ).data or []
        if bpmn_rows:
            hub.bpmn = _build_bpmn_model(bpmn_rows[0])
    except Exception:
        hub.bpmn = BPMNModel()

    # ── 3. Run AgentSynthesizer only ──────────────────────────────────────────
    try:
        synthesizer = AgentSynthesizer(
            client_info={},
            provider_cfg=llm_config,
        )
        hub = synthesizer.run(hub, output_language=output_language)
    except Exception as e:
        return ReportResult(
            meeting_id=meeting_id,
            meeting_number=meeting_number,
            meeting_title=meeting_title,
            success=False,
            error=f"AgentSynthesizer falhou: {e}",
        )

    if not hub.synthesizer.ready or not hub.synthesizer.html:
        return ReportResult(
            meeting_id=meeting_id,
            meeting_number=meeting_number,
            meeting_title=meeting_title,
            success=False,
            error="AgentSynthesizer concluiu mas não gerou HTML.",
        )

    # ── 4. Persist ────────────────────────────────────────────────────────────
    provider_name = llm_config.get("provider_name", "")
    save_report_html(meeting_id, hub.synthesizer.html, provider_name)

    return ReportResult(
        meeting_id=meeting_id,
        meeting_number=meeting_number,
        meeting_title=meeting_title,
        success=True,
        html=hub.synthesizer.html,
        tokens_used=hub.meta.total_tokens_used,
        provider=provider_name,
    )


def build_reports_for_project(
    project_id: str,
    llm_config: dict,
    output_language: str = "Portuguese (BR)",
    callback: Optional[Callable[[int, int, ReportResult], None]] = None,
    skip_existing: bool = True,
) -> list[ReportResult]:
    """
    Generate reports for all meetings in a project.

    Parameters
    ----------
    skip_existing : bool
        If True, skip meetings that already have report_html populated.
    callback : callable(current_idx, total, result)
        Progress callback for Streamlit progress bar.
    """
    from core.project_store import get_supabase_client

    client = get_supabase_client()
    if client is None:
        return []

    select_cols = "id, meeting_number, title, report_html"
    rows = (
        client.table("meetings")
        .select(select_cols)
        .eq("project_id", project_id)
        .order("meeting_number")
        .execute()
    ).data or []

    if skip_existing:
        rows = [r for r in rows if not r.get("report_html")]

    results = []
    total = len(rows)
    for idx, row in enumerate(rows):
        result = build_report_for_meeting(row["id"], llm_config, output_language)
        results.append(result)
        if callback:
            callback(idx + 1, total, result)

    return results


# ── Private helpers ───────────────────────────────────────────────────────────

def _parse_minutes_from_md(minutes_md: str):
    """
    Reconstruct a MinutesModel from the stored minutes_md text.
    Uses simple line parsing — does not require an LLM.
    """
    from core.knowledge_hub import MinutesModel, ActionItem
    m = MinutesModel()
    m.full_text = minutes_md
    m.ready = True

    lines = minutes_md.splitlines()
    section = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Detect sections by Markdown headers
        low = line.lower()
        if "decisão" in low or "decisões" in low:
            section = "decisions"
        elif "ação" in low or "ações" in low or "action" in low:
            section = "actions"
        elif "participante" in low:
            section = "participants"
        elif "pauta" in low or "agenda" in low:
            section = "agenda"
        elif line.startswith("- ") or line.startswith("* "):
            content = line[2:].strip()
            if section == "decisions" and content:
                m.decisions.append(content)
            elif section == "participants" and content:
                m.participants.append(content)
            elif section == "agenda" and content:
                m.agenda_items.append(content)
            elif section == "actions" and content:
                ai = ActionItem(description=content)
                m.action_items.append(ai)

    return m


def _build_requirements_model(reqs_data: list[dict]):
    from core.knowledge_hub import RequirementsModel, Requirement
    model = RequirementsModel()
    for r in reqs_data:
        req = Requirement(
            req_id=r.get("req_id", ""),
            title=r.get("title", ""),
            description=r.get("description", ""),
            req_type=r.get("req_type", "functional"),
            priority=r.get("priority", "medium"),
            status=r.get("status", "identified"),
            source_speaker=r.get("source_speaker", ""),
        )
        model.items.append(req)
    if model.items:
        model.ready = True
    return model


def _build_sbvr_envelope(terms_data: list[dict], rules_data: list[dict]):
    from core.knowledge_hub import SBVREnvelope, SBVRTerm, SBVRRule
    env = SBVREnvelope()
    for t in terms_data:
        env.terms.append(SBVRTerm(
            term=t.get("term", ""),
            definition=t.get("definition", ""),
            category=t.get("category", "concept"),
        ))
    for r in rules_data:
        env.rules.append(SBVRRule(
            rule_text=r.get("rule_text", ""),
            rule_type=r.get("rule_type", "operative"),
            source=r.get("source", ""),
        ))
    env.ready = bool(env.terms or env.rules)
    return env


def _build_bpmn_model(row: dict):
    from core.knowledge_hub import BPMNModel
    m = BPMNModel()
    m.bpmn_xml = row.get("bpmn_xml") or ""
    m.mermaid  = row.get("mermaid_code") or ""
    m.name     = row.get("process_name") or ""
    m.ready    = bool(m.bpmn_xml)
    return m
  
