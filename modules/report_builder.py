# modules/report_builder.py
# ─────────────────────────────────────────────────────────────────────────────
# Standalone executive report generator.
#
# Uses run_pipeline() with run_synthesizer=True and all other agents enabled
# (same as a normal pipeline run) but does NOT create a new meeting row —
# it regenerates artefacts in-place and persists only report_html.
#
# This guarantees the report is generated with the exact same hub state
# as a normal pipeline run: full requirements, SBVR, BMM, BPMN, minutes.
#
# Public API:
#   build_report_for_meeting(meeting_id, llm_config, output_language) -> ReportResult
#   build_reports_for_project(project_id, llm_config, output_language, callback) -> list[ReportResult]
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional


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

    Runs the full pipeline (Minutes + Requirements + SBVR + BMM + Synthesizer)
    on the stored transcript — identical to a normal pipeline run.
    Persists only report_html, report_generated_at, report_provider.
    Does NOT create a new meeting row or overwrite other artefacts.
    """
    from core.project_store import get_supabase_client, save_report_html
    from core.knowledge_hub import KnowledgeHub
    from core.pipeline import run_pipeline

    client = get_supabase_client()
    if client is None:
        return ReportResult(
            meeting_id=meeting_id, meeting_number=0, meeting_title="",
            success=False, error="Supabase não configurado."
        )

    # ── 1. Load meeting transcript ────────────────────────────────────────────
    try:
        mtg = (
            client.table("meetings")
            .select("id, meeting_number, title, transcript_clean, transcript_raw")
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
    transcript     = (mtg.get("transcript_clean") or mtg.get("transcript_raw") or "").strip()

    if not transcript:
        return ReportResult(
            meeting_id=meeting_id,
            meeting_number=meeting_number,
            meeting_title=meeting_title,
            success=False,
            error="Reunião sem transcrição armazenada. Use TranscriptBackfill primeiro.",
        )

    # ── 2. Build hub and run pipeline ─────────────────────────────────────────
    hub = KnowledgeHub.new()
    hub.set_transcript(transcript)
    hub.meta.llm_provider = llm_config.get("provider_name", "")

    # Extract client_info and provider_cfg from llm_config
    # llm_config may be a flat dict (from ReportBackfill) or nested
    api_key = llm_config.get("api_key", "")
    client_info = {"api_key": api_key}

    # provider_cfg: everything except api_key and provider_name
    provider_cfg = {
        k: v for k, v in llm_config.items()
        if k not in ("api_key", "provider_name")
    }
    # Ensure provider_cfg has the required fields BaseAgent expects
    if not provider_cfg.get("client_type"):
        # llm_config is already the provider_cfg (flat structure from AVAILABLE_PROVIDERS)
        provider_cfg = llm_config

    pipeline_config: dict[str, Any] = {
        "client_info":          client_info,
        "provider_cfg":         provider_cfg,
        "output_language":      output_language,
        "run_quality":          False,   # skip — not needed for report
        "run_bpmn":             True,    # needed for BPMN section in report
        "run_minutes":          True,    # needed for minutes section
        "run_requirements":     True,    # needed for requirements section
        "run_sbvr":             True,    # needed for SBVR section
        "run_bmm":              True,    # needed for BMM section
        "run_synthesizer":      True,    # the whole point
        "n_bpmn_runs":          1,
        "bpmn_weights":         {"granularity": 5, "task_type": 5,
                                 "gateways": 5, "structural": 5},
        "use_langgraph":        False,
        "validation_threshold": 6.0,
        "max_bpmn_retries":     3,
    }

    try:
        hub = run_pipeline(hub, pipeline_config, lambda *_: None)
    except Exception as e:
        return ReportResult(
            meeting_id=meeting_id,
            meeting_number=meeting_number,
            meeting_title=meeting_title,
            success=False,
            error=f"Pipeline falhou: {e}",
        )

    # ── 3. Extract HTML ───────────────────────────────────────────────────────
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

    # ── 4. Persist only report_html (do not overwrite other artefacts) ────────
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
