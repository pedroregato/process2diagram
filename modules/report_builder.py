# modules/report_builder.py
# ─────────────────────────────────────────────────────────────────────────────
# Standalone executive report generator.
#
# Loads all stored artefacts (BPMN, minutes, requirements, SBVR, BMM) via
# load_meeting_as_hub() and runs only AgentSynthesizer — much faster than
# re-running the full pipeline and consistent with canonical stored data.
# Persists only report_html; never overwrites other meeting artefacts.
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

    Loads all existing artefacts (BPMN, minutes, requirements, SBVR, BMM)
    via load_meeting_as_hub() and runs only AgentSynthesizer — much faster
    than re-running the full pipeline and consistent with canonical stored data.
    Persists only report_html, report_generated_at, report_provider.
    Does NOT create a new meeting row or overwrite other artefacts.
    """
    from core.project_store import get_supabase_client, save_report_html, load_meeting_as_hub

    client = get_supabase_client()
    if client is None:
        return ReportResult(
            meeting_id=meeting_id, meeting_number=0, meeting_title="",
            success=False, error="Supabase não configurado."
        )

    # ── 1. Load meeting metadata ──────────────────────────────────────────────
    try:
        mtg = (
            client.table("meetings")
            .select("id, meeting_number, title, project_id")
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

    # ── 2. Load all stored artefacts into a hub ───────────────────────────────
    try:
        hub = load_meeting_as_hub(meeting_id, project_id)
    except Exception as e:
        return ReportResult(
            meeting_id=meeting_id,
            meeting_number=meeting_number,
            meeting_title=meeting_title,
            success=False,
            error=f"Erro ao carregar artefatos da reunião: {e}",
        )

    if hub is None:
        return ReportResult(
            meeting_id=meeting_id,
            meeting_number=meeting_number,
            meeting_title=meeting_title,
            success=False,
            error="Não foi possível carregar os dados da reunião do Supabase.",
        )

    hub.meta.llm_provider = llm_config.get("provider_name", "")

    # ── 3. Build client/provider config ──────────────────────────────────────
    api_key      = llm_config.get("api_key", "")
    client_info  = {"api_key": api_key}
    provider_cfg = {k: v for k, v in llm_config.items() if k not in ("api_key", "provider_name")}
    if not provider_cfg.get("client_type"):
        provider_cfg = llm_config

    # ── 4. Run only AgentSynthesizer ─────────────────────────────────────────
    try:
        from agents.agent_synthesizer import AgentSynthesizer
        agent = AgentSynthesizer(client_info, provider_cfg)
        hub   = agent.run(hub, output_language)
    except Exception as e:
        return ReportResult(
            meeting_id=meeting_id,
            meeting_number=meeting_number,
            meeting_title=meeting_title,
            success=False,
            error=f"AgentSynthesizer falhou: {e}",
        )

    # ── 5. Extract HTML ───────────────────────────────────────────────────────
    report_html = ""
    if hasattr(hub, "synthesizer") and hub.synthesizer.ready:
        report_html = hub.synthesizer.html or ""

    if not report_html:
        return ReportResult(
            meeting_id=meeting_id,
            meeting_number=meeting_number,
            meeting_title=meeting_title,
            success=False,
            error="AgentSynthesizer concluiu mas não gerou HTML.",
        )

    # ── 6. Persist only report_html (do not overwrite other artefacts) ────────
    provider_name = llm_config.get("provider_name", "")
    save_report_html(meeting_id, report_html, provider_name)

    tokens_used = getattr(hub.meta, "total_tokens_used", 0) or 0

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
