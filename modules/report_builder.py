# modules/report_builder.py
# ─────────────────────────────────────────────────────────────────────────────
# Standalone executive report generator.
#
# Reconstructs a KnowledgeHub from Supabase data and runs only
# AgentSynthesizer — no full pipeline reprocessing required.
#
# Compatible with the full KnowledgeHub schema (v4.19+):
#   requirements  → RequirementsModel / RequirementItem
#   sbvr          → SBVRModel / BusinessTerm / BusinessRule
#   bmm           → BMMModel
#   synthesizer   → SynthesizerModel
#   transcript_quality → TranscriptQualityModel (ROI / grade)
#
# Supabase FK schema:
#   requirements  → project_id + first_meeting_id
#   sbvr_terms    → meeting_id (direct)
#   sbvr_rules    → meeting_id (direct)
#   bpmn_processes → meeting_id → bpmn_versions (is_current)
#   meetings.meeting_type → used to populate quality grade for ROI
#
# Public API:
#   build_report_for_meeting(meeting_id, llm_config, output_language) -> ReportResult
#   build_reports_for_project(project_id, llm_config, output_language, callback) -> list[ReportResult]
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from dataclasses import dataclass
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
    Persists the result to meetings.report_html.
    """
    from core.project_store import get_supabase_client, save_report_html
    from core.knowledge_hub import (
        KnowledgeHub,
        RequirementsModel, RequirementItem,
        SBVRModel, BusinessTerm, BusinessRule,
        BMMModel,
        TranscriptQualityModel, CriterionScore,
        MinutesModel, ActionItem,
    )
    from agents.agent_synthesizer import AgentSynthesizer

    client = get_supabase_client()
    if client is None:
        return ReportResult(
            meeting_id=meeting_id, meeting_number=0, meeting_title="",
            success=False, error="Supabase não configurado."
        )

    # ── 1. Load meeting ───────────────────────────────────────────────────────
    try:
        mtg = (
            client.table("meetings")
            .select(
                "id, meeting_number, title, minutes_md, transcript_clean, "
                "project_id, meeting_type, total_tokens, llm_provider"
            )
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
    project_id     = mtg.get("project_id", "")

    # ── 2. Build KnowledgeHub ─────────────────────────────────────────────────
    hub = KnowledgeHub.new()
    hub.transcript_clean = mtg.get("transcript_clean") or ""
    hub.transcript_raw   = hub.transcript_clean
    hub.loaded_from_db   = True

    # Provider/model metadata
    hub.meta.llm_provider = mtg.get("llm_provider") or llm_config.get("provider_name", "")
    hub.meta.total_tokens_used = mtg.get("total_tokens") or 0

    # ── Minutes ───────────────────────────────────────────────────────────────
    minutes_md = mtg.get("minutes_md") or ""
    if minutes_md:
        hub.minutes = _parse_minutes_from_md(minutes_md)

    # ── Requirements (project_id + first_meeting_id) ──────────────────────────
    if project_id:
        try:
            reqs_data = (
                client.table("requirements")
                .select(
                    "req_number, title, description, req_type, priority, "
                    "status, cited_by, source_quote"
                )
                .eq("project_id", project_id)
                .eq("first_meeting_id", meeting_id)
                .order("req_number")
                .execute()
            ).data or []

            if reqs_data:
                model = RequirementsModel()
                model.session_title = meeting_title
                for r in reqs_data:
                    n = r.get("req_number")
                    try:
                        item = RequirementItem(
                            id=f"REQ-{n:03d}" if isinstance(n, int) else str(n or ""),
                            title=r.get("title", ""),
                            description=r.get("description", ""),
                            type=r.get("req_type", "functional"),
                            priority=r.get("priority", "unspecified"),
                            status=r.get("status", "active"),
                            source_quote=r.get("source_quote", ""),
                            speaker=r.get("cited_by", ""),
                        )
                        model.requirements.append(item)
                    except Exception:
                        pass
                if model.requirements:
                    model.ready = True
                hub.requirements = model
        except Exception:
            pass

    # ── SBVR ──────────────────────────────────────────────────────────────────
    try:
        terms_data = (
            client.table("sbvr_terms")
            .select("term, definition, category")
            .eq("meeting_id", meeting_id)
            .execute()
        ).data or []

        rules_data = (
            client.table("sbvr_rules")
            .select("rule_id, statement, nucleo_nominal, rule_type, source")
            .eq("meeting_id", meeting_id)
            .execute()
        ).data or []

        if terms_data or rules_data:
            sbvr = SBVRModel()
            for t in terms_data:
                try:
                    sbvr.vocabulary.append(BusinessTerm(
                        term=t.get("term", ""),
                        definition=t.get("definition", ""),
                        category=t.get("category", "concept"),
                    ))
                except Exception:
                    pass
            for r in rules_data:
                try:
                    sbvr.rules.append(BusinessRule(
                        id=r.get("rule_id", ""),
                        statement=r.get("statement", ""),
                        short_title=r.get("nucleo_nominal", ""),
                        rule_type=r.get("rule_type", "constraint"),
                        source=r.get("source", ""),
                    ))
                except Exception:
                    pass
            sbvr.ready = bool(sbvr.vocabulary or sbvr.rules)
            hub.sbvr = sbvr
    except Exception:
        pass

    # ── BMM ───────────────────────────────────────────────────────────────────
    # BMM is not stored in a dedicated table — it is regenerated by AgentSynthesizer
    # using the transcript + minutes. Leave hub.bmm as default (empty, not ready).

    # ── BPMN (bpmn_processes → bpmn_versions) ────────────────────────────────
    try:
        proc_rows = (
            client.table("bpmn_processes")
            .select("id, process_name")
            .eq("meeting_id", meeting_id)
            .limit(1)
            .execute()
        ).data or []

        if proc_rows:
            proc_id   = proc_rows[0]["id"]
            proc_name = proc_rows[0].get("process_name", "")

            # Try current version first, fallback to most recent
            ver_rows = (
                client.table("bpmn_versions")
                .select("bpmn_xml, mermaid_code")
                .eq("process_id", proc_id)
                .eq("is_current", True)
                .limit(1)
                .execute()
            ).data or []

            if not ver_rows:
                ver_rows = (
                    client.table("bpmn_versions")
                    .select("bpmn_xml, mermaid_code")
                    .eq("process_id", proc_id)
                    .order("created_at", desc=True)
                    .limit(1)
                    .execute()
                ).data or []

            if ver_rows:
                hub.bpmn.bpmn_xml = ver_rows[0].get("bpmn_xml") or ""
                hub.bpmn.mermaid  = ver_rows[0].get("mermaid_code") or ""
                hub.bpmn.name     = proc_name
                if hub.bpmn.bpmn_xml:
                    hub.bpmn.ready = True
    except Exception:
        pass

    # ── Transcript quality / ROI grade ────────────────────────────────────────
    # Populate a minimal TranscriptQualityModel so the Synthesizer can show
    # the meeting type and ROI grade in the report header.
    try:
        meeting_type = mtg.get("meeting_type") or ""
        if meeting_type:
            hub.transcript_quality.overall_summary = f"Tipo de reunião: {meeting_type}"
            hub.transcript_quality.ready = True

        # Load ROI from meeting_roi_calculator if available
        try:
            from modules.meeting_roi_calculator import compute_project_roi, MeetingROIData
            if project_id:
                roi_data_list = compute_project_roi(project_id)
                for roi_item in roi_data_list:
                    if hasattr(roi_item, "meeting_id") and roi_item.meeting_id == meeting_id:
                        hub.transcript_quality.overall_score = getattr(roi_item, "roi_tr", 0) * 10
                        hub.transcript_quality.grade = _roi_to_grade(getattr(roi_item, "roi_tr", 0))
                        hub.transcript_quality.recommendation = (
                            f"ROI-TR: {getattr(roi_item, 'roi_tr', 0):.1f}/10 · "
                            f"Tipo: {getattr(roi_item, 'meeting_type', meeting_type)}"
                        )
                        hub.transcript_quality.ready = True
                        break
        except Exception:
            pass
    except Exception:
        pass

    # ── 3. Run AgentSynthesizer ───────────────────────────────────────────────
    try:
        provider_cfg = llm_config.get("provider_cfg", llm_config)
        client_info  = {"api_key": llm_config.get("api_key", "")}

        synthesizer = AgentSynthesizer(client_info, provider_cfg)
        hub = synthesizer.run(hub, output_language=output_language)
    except Exception as e:
        return ReportResult(
            meeting_id=meeting_id,
            meeting_number=meeting_number,
            meeting_title=meeting_title,
            success=False,
            error=f"AgentSynthesizer falhou: {e}",
        )

    report_html = hub.synthesizer.html if hub.synthesizer.ready else ""

    if not report_html:
        return ReportResult(
            meeting_id=meeting_id,
            meeting_number=meeting_number,
            meeting_title=meeting_title,
            success=False,
            error="AgentSynthesizer concluiu mas não gerou HTML.",
        )

    # ── 4. Persist ────────────────────────────────────────────────────────────
    provider_name = llm_config.get("provider_name", "")
    save_report_html(meeting_id, report_html, provider_name)

    return ReportResult(
        meeting_id=meeting_id,
        meeting_number=meeting_number,
        meeting_title=meeting_title,
        success=True,
        html=report_html,
        tokens_used=hub.meta.total_tokens_used or 0,
        provider=provider_name,
    )


def build_reports_for_project(
    project_id: str,
    llm_config: dict,
    output_language: str = "Portuguese (BR)",
    callback: Optional[Callable[[int, int, ReportResult], None]] = None,
    skip_existing: bool = True,
) -> list[ReportResult]:
    """Generate reports for all meetings in a project."""
    from core.project_store import get_supabase_client

    client = get_supabase_client()
    if client is None:
        return []

    try:
        rows = (
            client.table("meetings")
            .select("id, meeting_number, title, report_html")
            .eq("project_id", project_id)
            .order("meeting_number")
            .execute()
        ).data or []
    except Exception:
        return []

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
    """Reconstruct MinutesModel from stored minutes_md. No LLM required."""
    from core.knowledge_hub import MinutesModel, ActionItem

    m = MinutesModel()
    m.minutes_md = minutes_md
    m.ready      = True

    lines   = minutes_md.splitlines()
    section = None

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        low = stripped.lower()

        # Section detection by Markdown headers
        if stripped.startswith("#"):
            if "decisão" in low or "decisões" in low:
                section = "decisions"
            elif "ação" in low or "ações" in low or "action" in low:
                section = "actions"
            elif "participante" in low:
                section = "participants"
            elif "pauta" in low or "agenda" in low:
                section = "agenda"
            elif "resumo" in low or "summary" in low:
                section = "summary"
            else:
                section = None
            continue

        # Bullet items
        if stripped.startswith(("- ", "* ", "• ")):
            content = stripped[2:].strip()
            if not content:
                continue
            if section == "decisions":
                m.decisions.append(content)
            elif section == "participants":
                m.participants.append(content)
            elif section == "agenda":
                m.agenda.append(content)
            elif section == "actions":
                # Parse "task | responsible | deadline" if pipe-separated
                parts = [p.strip() for p in content.split("|")]
                task       = parts[0] if parts else content
                responsible = parts[1] if len(parts) > 1 else "A definir"
                deadline    = parts[2] if len(parts) > 2 else None
                m.action_items.append(ActionItem(
                    task=task,
                    responsible=responsible,
                    deadline=deadline,
                ))

    return m


def _roi_to_grade(roi_tr: float) -> str:
    """Convert ROI-TR (0–10) to letter grade A–E."""
    if roi_tr >= 8.0:
        return "A"
    if roi_tr >= 6.5:
        return "B"
    if roi_tr >= 5.0:
        return "C"
    if roi_tr >= 3.0:
        return "D"
    return "E"

