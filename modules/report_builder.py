# modules/report_builder.py
# ─────────────────────────────────────────────────────────────────────────────
# Standalone executive report generator.
#
# Reconstructs a minimal KnowledgeHub from Supabase data and runs only
# AgentSynthesizer — no full pipeline reprocessing required.
#
# Compatible with KnowledgeHub PC1+ (uses hasattr guards for optional fields).
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

    Reads from Supabase:
      meetings       → title, number, minutes_md, transcript_clean
      requirements   → list of requirements (if table exists)
      sbvr_terms     → vocabulary terms (if table exists)
      sbvr_rules     → business rules (if table exists)
      bpmn_processes → BPMN XML latest version (if table exists)

    Builds a minimal KnowledgeHub using only fields that exist in the
    current version and runs AgentSynthesizer only.
    Persists the result back to meetings.report_html.
    """
    from core.project_store import get_supabase_client, save_report_html
    from core.knowledge_hub import KnowledgeHub
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
            .select("id, meeting_number, title, minutes_md, transcript_clean")
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

    # Minutes — parse from stored minutes_md
    minutes_md = mtg.get("minutes_md") or ""
    if minutes_md:
        hub.minutes = _parse_minutes_from_md(minutes_md)

    # Requirements — only if hub supports it
    if hasattr(hub, "requirements"):
        try:
            reqs_data = (
                client.table("requirements")
                .select("req_id, title, description, req_type, priority, status, source_speaker")
                .eq("meeting_id", meeting_id)
                .execute()
            ).data or []
            hub.requirements = _build_requirements_model(reqs_data)
        except Exception:
            pass

    # SBVR — only if hub supports it
    if hasattr(hub, "sbvr"):
        try:
            terms_data = (
                client.table("sbvr_terms")
                .select("term, definition, category")
                .eq("meeting_id", meeting_id)
                .execute()
            ).data or []
            rules_data = (
                client.table("sbvr_rules")
                .select("statement, rule_type, source")
                .eq("meeting_id", meeting_id)
                .execute()
            ).data or []
            hub.sbvr = _build_sbvr_envelope(terms_data, rules_data)
        except Exception:
            pass

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
            row = bpmn_rows[0]
            hub.bpmn.bpmn_xml = row.get("bpmn_xml") or ""
            hub.bpmn.mermaid  = row.get("mermaid_code") or ""
            hub.bpmn.name     = row.get("process_name") or ""
            if hub.bpmn.bpmn_xml:
                hub.bpmn.ready = True
    except Exception:
        pass

    # ── 3. Run AgentSynthesizer only ──────────────────────────────────────────
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

    # ── 4. Extract HTML from hub ──────────────────────────────────────────────
    report_html = ""
    if hasattr(hub, "synthesizer") and hasattr(hub.synthesizer, "html"):
        report_html = hub.synthesizer.html or ""
    elif hasattr(hub, "report_html"):
        report_html = hub.report_html or ""

    if not report_html:
        return ReportResult(
            meeting_id=meeting_id,
            meeting_number=meeting_number,
            meeting_title=meeting_title,
            success=False,
            error="AgentSynthesizer concluiu mas não gerou HTML.",
        )

    # ── 5. Persist ────────────────────────────────────────────────────────────
    provider_name = llm_config.get("provider_name", "")
    save_report_html(meeting_id, report_html, provider_name)

    tokens_used = 0
    if hasattr(hub, "meta") and hasattr(hub.meta, "total_tokens_used"):
        tokens_used = hub.meta.total_tokens_used or 0

    return ReportResult(
        meeting_id=meeting_id,
        meeting_number=meeting_number,
        meeting_title=meeting_title,
        success=True,
        html=report_html,
        tokens_used=tokens_used,
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

    try:
        rows = (
            client.table("meetings")
            .select("id, meeting_number, title, report_html")
            .eq("project_id", project_id)
            .order("meeting_number")
            .execute()
        ).data or []
    except Exception as e:
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
    """Reconstruct a MinutesModel from stored minutes_md. No LLM required."""
    from core.knowledge_hub import MinutesModel
    m = MinutesModel()
    m.full_text = minutes_md
    m.ready = True

    # ActionItem may or may not exist — use hasattr guard
    try:
        from core.knowledge_hub import ActionItem
        _has_action_item = True
    except ImportError:
        _has_action_item = False

    lines = minutes_md.splitlines()
    section = None

    for line in lines:
        line = line.strip()
        if not line:
            continue
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
            if not content:
                continue
            if section == "decisions" and hasattr(m, "decisions"):
                m.decisions.append(content)
            elif section == "participants" and hasattr(m, "participants"):
                m.participants.append(content)
            elif section == "agenda" and hasattr(m, "agenda_items"):
                m.agenda_items.append(content)
            elif section == "actions" and hasattr(m, "action_items"):
                if _has_action_item:
                    from core.knowledge_hub import ActionItem
                    m.action_items.append(ActionItem(description=content))
                else:
                    m.action_items.append({"description": content})

    return m


def _build_requirements_model(reqs_data: list[dict]):
    """Build RequirementsModel if available, else return a plain object."""
    try:
        from core.knowledge_hub import RequirementsModel, Requirement
        model = RequirementsModel()
        for r in reqs_data:
            try:
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
            except Exception:
                pass
        if model.items:
            model.ready = True
        return model
    except ImportError:
        return None


def _build_sbvr_envelope(terms_data: list[dict], rules_data: list[dict]):
    """Build SBVREnvelope if available, else return None."""
    try:
        from core.knowledge_hub import SBVREnvelope, SBVRTerm, SBVRRule
        env = SBVREnvelope()
        for t in terms_data:
            try:
                env.terms.append(SBVRTerm(
                    term=t.get("term", ""),
                    definition=t.get("definition", ""),
                    category=t.get("category", "concept"),
                ))
            except Exception:
                pass
        for r in rules_data:
            try:
                env.rules.append(SBVRRule(
                    rule_text=r.get("statement", r.get("rule_text", "")),
                    rule_type=r.get("rule_type", "operative"),
                    source=r.get("source", ""),
                ))
            except Exception:
                pass
        env.ready = bool(env.terms or env.rules)
        return env
    except ImportError:
        return None
