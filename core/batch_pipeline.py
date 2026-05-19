# core/batch_pipeline.py
# ─────────────────────────────────────────────────────────────────────────────
# BatchPipeline — processa uma lista de transcrições em lote.
#
# Responsabilidades:
#   1. Deduplicação via hash SHA-256 do conteúdo (não reprocessa o mesmo arquivo)
#   2. Extração de data: filename → texto → LLM (em ordem de custo crescente)
#   3. Sugestão de título via AgentMeetingNamer (LLM)
#   4. Execução do pipeline: Minutes + Requirements + SBVR + BMM (BPMN opcional)
#   5. Persistência: meeting, artefatos, SBVR, reconciliação de requisitos
#   6. Registro de auditoria em batch_log
#
# Este módulo é puramente Python — sem imports de Streamlit.
# A UI vive em pages/BatchRunner.py.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Optional


# ── Extração de data ──────────────────────────────────────────────────────────

_ISO_RE       = re.compile(r'\b(20\d{2})-(0[1-9]|1[0-2])-([0-2]\d|3[01])\b')
_BR_SLASH_RE  = re.compile(r'\b([0-2]\d|3[01])/(0[1-9]|1[0-2])/(20\d{2})\b')
_BR_DOT_RE    = re.compile(r'\b([0-2]\d|3[01])\.(0[1-9]|1[0-2])\.(20\d{2})\b')
_BR_DASH_RE   = re.compile(r'\b([0-2]\d|3[01])-(0[1-9]|1[0-2])-(20\d{2})\b')
_COMPACT_RE   = re.compile(r'\b(20\d{2})(0[1-9]|1[0-2])([0-2]\d|3[01])\b')

_PT_MONTHS = {
    'janeiro': 1, 'fevereiro': 2, 'março': 3, 'abril': 4,
    'maio': 5,   'junho': 6,     'julho': 7,  'agosto': 8,
    'setembro': 9, 'outubro': 10, 'novembro': 11, 'dezembro': 12,
}
_PT_WRITTEN_RE = re.compile(
    r'(\d{1,2})\s+de\s+(' + '|'.join(_PT_MONTHS) + r')\s+de\s+(20\d{2})',
    re.IGNORECASE,
)
_PT_MONTH_YEAR_RE = re.compile(
    r'\b(' + '|'.join(_PT_MONTHS) + r')\s+de\s+(20\d{2})\b',
    re.IGNORECASE,
)


def _safe_date(year: int, month: int, day: int) -> Optional[date]:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def extract_date_from_text(text: str) -> Optional[date]:
    """Extrai data dos primeiros 2000 caracteres do texto. Retorna None se não encontrar."""
    sample = text[:2000]

    m = _ISO_RE.search(sample)
    if m:
        return _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    m = _BR_SLASH_RE.search(sample)
    if m:
        return _safe_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))

    m = _BR_DOT_RE.search(sample)
    if m:
        return _safe_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))

    m = _PT_WRITTEN_RE.search(sample)
    if m:
        return _safe_date(int(m.group(3)), _PT_MONTHS[m.group(2).lower()], int(m.group(1)))

    m = _PT_MONTH_YEAR_RE.search(sample)
    if m:
        return _safe_date(int(m.group(2)), _PT_MONTHS[m.group(1).lower()], 1)

    m = _BR_DASH_RE.search(sample)
    if m:
        return _safe_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))

    m = _COMPACT_RE.search(sample)
    if m:
        return _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    return None


def extract_date_from_filename(filename: str) -> Optional[date]:
    """Tenta extrair data diretamente do nome do arquivo."""
    name = Path(filename).stem

    m = _ISO_RE.search(name)
    if m:
        return _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    m = _BR_SLASH_RE.search(name)
    if m:
        return _safe_date(int(m.group(3)), int(m.group(2)), int(m.group(1)))

    m = _COMPACT_RE.search(name)
    if m:
        return _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))

    return None


def file_hash(content: str) -> str:
    """SHA-256 parcial do conteúdo (16 chars) para deduplicação."""
    return hashlib.sha256(content.encode("utf-8", errors="replace")).hexdigest()[:16]


# ── BPMN pre-loader (reprocess path) ─────────────────────────────────────────

def _preload_bpmn_from_db(hub, meeting_id: str) -> None:
    """Pre-populate hub.bpmn from the stored BPMN when not re-running the agent.

    Loads XML + Mermaid from bpmn_versions (or bpmn_xml column fallback) and
    parses the XML to reconstruct lanes and task steps so generate_executive_html
    can render the full process table and diagram sections.
    Fail-open: any exception is silently swallowed.
    """
    try:
        from modules.supabase_client import get_supabase_client
        db = get_supabase_client()
        if not db:
            return

        bv_rows = (
            db.table("bpmn_versions")
            .select("bpmn_xml, mermaid_code, bpmn_processes(name)")
            .eq("meeting_id", meeting_id)
            .eq("is_current", True)
            .limit(1)
            .execute().data or []
        )
        if not bv_rows:
            bv_rows = (
                db.table("bpmn_versions")
                .select("bpmn_xml, mermaid_code, bpmn_processes(name)")
                .eq("meeting_id", meeting_id)
                .order("version", desc=True)
                .limit(1)
                .execute().data or []
            )
        if not bv_rows:
            return

        bpmn_xml     = (bv_rows[0].get("bpmn_xml")     or "").strip()
        mermaid_code = (bv_rows[0].get("mermaid_code") or "").strip()
        proc_name    = ((bv_rows[0].get("bpmn_processes") or {}).get("name") or "").strip()
        if not bpmn_xml:
            return

        hub.bpmn.bpmn_xml = bpmn_xml
        hub.bpmn.mermaid  = mermaid_code
        hub.bpmn.name     = proc_name
        hub.bpmn.ready    = True

        _parse_bpmn_xml_into_hub(bpmn_xml, hub)
    except Exception:
        pass


_BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"

_TASK_TAGS = {
    f"{{{_BPMN_NS}}}task":        "task",
    f"{{{_BPMN_NS}}}userTask":    "userTask",
    f"{{{_BPMN_NS}}}serviceTask": "serviceTask",
    f"{{{_BPMN_NS}}}manualTask":  "manualTask",
    f"{{{_BPMN_NS}}}businessRuleTask": "businessRuleTask",
    f"{{{_BPMN_NS}}}scriptTask":  "scriptTask",
    f"{{{_BPMN_NS}}}sendTask":    "sendTask",
    f"{{{_BPMN_NS}}}receiveTask": "receiveTask",
}

_GW_TAGS = {
    f"{{{_BPMN_NS}}}exclusiveGateway",
    f"{{{_BPMN_NS}}}inclusiveGateway",
    f"{{{_BPMN_NS}}}parallelGateway",
    f"{{{_BPMN_NS}}}complexGateway",
    f"{{{_BPMN_NS}}}eventBasedGateway",
}


def _parse_bpmn_xml_into_hub(bpmn_xml: str, hub) -> None:
    """Parse stored BPMN XML to populate hub.bpmn.lanes and hub.bpmn.steps."""
    import xml.etree.ElementTree as ET
    from core.knowledge_hub import BPMNStep

    try:
        root = ET.fromstring(bpmn_xml)

        # Map element IDs → lane name
        elem_to_lane: dict[str, str] = {}
        lanes: list[str] = []
        for lane in root.iter(f"{{{_BPMN_NS}}}lane"):
            lane_name = (lane.get("name") or "").strip()
            if lane_name and lane_name not in lanes:
                lanes.append(lane_name)
            for child in lane:
                ref = (child.text or "").strip()
                if ref and lane_name:
                    elem_to_lane[ref] = lane_name
        hub.bpmn.lanes = lanes

        # Collect tasks and gateways as BPMNStep entries
        steps: list[BPMNStep] = []
        for elem in root.iter():
            task_type = _TASK_TAGS.get(elem.tag)
            is_gw = elem.tag in _GW_TAGS
            if task_type is None and not is_gw:
                continue
            eid  = elem.get("id") or ""
            name = (elem.get("name") or "").strip()
            if not name:
                continue
            lane_name = elem_to_lane.get(eid, "")
            steps.append(BPMNStep(
                id=eid,
                title=name,
                actor=lane_name or None,
                lane=lane_name or None,
                is_decision=is_gw,
                task_type=task_type or "exclusiveGateway",
            ))
        hub.bpmn.steps = steps
    except Exception:
        pass


# ── Resultado por arquivo ─────────────────────────────────────────────────────

@dataclass
class FileResult:
    filename: str
    status: str              # done | failed | duplicate
    meeting_id: str = ""
    meeting_title: str = ""
    meeting_date: Optional[date] = None
    date_source: str = ""    # filename | text | llm | none
    req_counts: dict = field(default_factory=dict)
    n_terms: int = 0
    n_rules: int = 0
    error: str = ""

    @property
    def req_new(self) -> int:         return self.req_counts.get("new", 0)
    @property
    def req_revised(self) -> int:     return self.req_counts.get("revised", 0)
    @property
    def req_contradicted(self) -> int: return self.req_counts.get("contradicted", 0)
    @property
    def req_confirmed(self) -> int:   return self.req_counts.get("confirmed", 0)


# ── BatchPipeline ─────────────────────────────────────────────────────────────

class BatchPipeline:
    """Processa uma lista de transcrições em lote contra um projeto Supabase.

    Uso:
        pipeline = BatchPipeline(client_info, provider_cfg, output_language)
        results  = pipeline.run_all(files, project_id, agents_config, progress_cb)

    `files` é uma lista de (filename: str, content: str).
    `agents_config` controla quais agentes rodar (run_minutes, run_requirements, etc.).
    `progress_cb(filename, status)` é chamado antes e após cada arquivo.
    """

    def __init__(
        self,
        client_info: dict,
        provider_cfg: dict,
        output_language: str = "Auto-detect",
    ):
        self.client_info = client_info
        self.provider_cfg = provider_cfg
        self.output_language = output_language

    # ── Ponto de entrada público ──────────────────────────────────────────────

    def run_all(
        self,
        files: list[tuple[str, str]],
        project_id: str,
        agents_config: dict,
        progress_cb: Callable[[str, str], None] | None = None,
    ) -> list[FileResult]:
        """Processa todos os arquivos sequencialmente."""
        results: list[FileResult] = []
        for filename, content in files:
            if progress_cb:
                progress_cb(filename, "processing")
            result = self._run_one(filename, content, project_id, agents_config)
            results.append(result)
            if progress_cb:
                progress_cb(filename, result.status)
        return results

    # ── Processamento de um único arquivo ────────────────────────────────────

    def _run_one(
        self,
        filename: str,
        content: str,
        project_id: str,
        agents_config: dict,
    ) -> FileResult:
        from core.project_store import (
            create_meeting, save_transcript, save_meeting_artifacts, save_meeting_tokens,
            save_sbvr_from_hub, save_bpmn_from_hub, log_batch_file, is_file_processed,
        )
        from core.pipeline import run_pipeline
        from core.knowledge_hub import KnowledgeHub

        fhash = file_hash(content)

        # 1. Deduplicação: arquivo já processado com sucesso neste projeto?
        if is_file_processed(project_id, fhash):
            log_batch_file(project_id, None, filename, fhash,
                           "duplicate", {}, 0, 0, "")
            return FileResult(
                filename=filename,
                status="duplicate",
                error="Arquivo já processado anteriormente neste projeto.",
            )

        # 2. Hub inicial
        hub = KnowledgeHub.new()
        hub.set_transcript(content)
        hub.meta.llm_provider = self.provider_cfg.get("api_key_label", "")

        # 3. Resolve data e título (uma chamada LLM para ambos)
        meeting_title, meeting_date, date_source = self._resolve_meta(
            content, filename, hub
        )

        # 4. Pipeline principal
        pipeline_config: dict[str, Any] = {
            "client_info":          self.client_info,
            "provider_cfg":         self.provider_cfg,
            "output_language":      self.output_language,
            "run_quality":          agents_config.get("run_quality", False),
            "run_bpmn":             agents_config.get("run_bpmn", False),
            "run_minutes":          agents_config.get("run_minutes", True),
            "run_requirements":     agents_config.get("run_requirements", True),
            "run_sbvr":             agents_config.get("run_sbvr", True),
            "run_bmm":              agents_config.get("run_bmm", True),
            "run_dmn":              agents_config.get("run_dmn", False),
            "run_argumentation":    agents_config.get("run_argumentation", False),
            "run_synthesizer":      agents_config.get("run_synthesizer", False),
            "n_bpmn_runs":          1,
            "bpmn_weights":         {"granularity": 5, "task_type": 5,
                                     "gateways": 5, "structural": 5},
            "use_langgraph":        False,
            "validation_threshold": 6.0,
            "max_bpmn_retries":     3,
        }

        try:
            hub = run_pipeline(hub, pipeline_config, lambda *_: None)
        except Exception as exc:
            log_batch_file(project_id, None, filename, fhash,
                           "failed", {}, 0, 0, str(exc)[:500])
            return FileResult(filename=filename, status="failed", error=str(exc))

        # 5. Persistência
        try:
            meeting = create_meeting(project_id, meeting_title, meeting_date)
            if not meeting:
                raise RuntimeError("Falha ao criar reunião no Supabase")
            meeting_id = meeting["id"]

            save_transcript(meeting_id, hub)        # leve — sempre primeiro
            save_meeting_artifacts(meeting_id, hub)  # artefatos em chamadas separadas
            # Garante tokens mesmo se save_meeting_artifacts falhou
            save_meeting_tokens(
                meeting_id,
                getattr(hub.meta, "total_tokens_used", 0),
                getattr(hub.meta, "llm_provider", ""),
            )

            n_terms, n_rules = 0, 0
            if getattr(hub, "sbvr", None) and hub.sbvr.ready:
                n_terms, n_rules = save_sbvr_from_hub(meeting_id, project_id, hub)

            # Persiste BPMN (opção A: slug automático, sem curadoria humana)
            if getattr(hub, "bpmn", None) and hub.bpmn.ready:
                save_bpmn_from_hub(meeting_id, project_id, hub)

            req_counts: dict[str, int] = {}
            if getattr(hub, "requirements", None) and hub.requirements.ready:
                from agents.agent_req_reconciler import AgentReqReconciler
                reconciler = AgentReqReconciler(self.client_info, self.provider_cfg)
                req_counts = reconciler.run(hub, project_id, meeting_id, self.output_language)

            log_batch_file(project_id, meeting_id, filename, fhash,
                           "done", req_counts, n_terms, n_rules, "")

            return FileResult(
                filename=filename,
                status="done",
                meeting_id=meeting_id,
                meeting_title=meeting_title,
                meeting_date=meeting_date,
                date_source=date_source,
                req_counts=req_counts,
                n_terms=n_terms,
                n_rules=n_rules,
            )

        except Exception as exc:
            log_batch_file(project_id, None, filename, fhash,
                           "failed", {}, 0, 0, str(exc)[:500])
            return FileResult(filename=filename, status="failed", error=str(exc))

    def _reprocess_one(
        self,
        meeting: dict,
        project_id: str,
        agents_config: dict,
    ) -> FileResult:
        """Re-run the pipeline on an existing meeting using its stored transcript.

        Updates artifacts in-place (no new meeting row created).
        Always saves total_tokens and llm_provider back to meetings table.
        """
        from core.project_store import (
            save_meeting_artifacts, save_meeting_tokens,
            save_sbvr_from_hub, save_bpmn_from_hub,
        )
        from core.pipeline import run_pipeline
        from core.knowledge_hub import KnowledgeHub

        meeting_id = meeting["id"]
        meeting_number = meeting.get("meeting_number", "?")
        title = meeting.get("title") or f"Reunião {meeting_number}"
        transcript = (meeting.get("transcript_clean") or meeting.get("transcript_raw") or "").strip()

        if not transcript:
            return FileResult(
                filename=title,
                status="failed",
                error="Sem transcrição armazenada — use TranscriptBackfill primeiro.",
            )

        hub = KnowledgeHub.new()
        hub.set_transcript(transcript)
        hub.meta.llm_provider = self.provider_cfg.get("api_key_label", "")

        # Pre-load stored BPMN when not re-running the BPMN agent so the
        # synthesizer can produce a rich report (diagram, process table, etc.)
        if not agents_config.get("run_bpmn", True):
            _preload_bpmn_from_db(hub, meeting_id)

        pipeline_config: dict[str, Any] = {
            "client_info":          self.client_info,
            "provider_cfg":         self.provider_cfg,
            "output_language":      self.output_language,
            # IDs necessários para Knowledge Extractor, CKF e Contradiction Detector
            "meeting_id":           meeting_id,
            "project_id":           project_id,
            "active_project_id":    project_id,
            # Defaults completos — reprocessamento deve ser exaustivo
            "run_quality":          agents_config.get("run_quality",      True),
            "run_bpmn":             agents_config.get("run_bpmn",         True),
            "run_minutes":          agents_config.get("run_minutes",       True),
            "run_requirements":     agents_config.get("run_requirements",  True),
            "run_sbvr":             agents_config.get("run_sbvr",          True),
            "run_bmm":              agents_config.get("run_bmm",           True),
            "run_dmn":              agents_config.get("run_dmn",           True),
            "run_argumentation":    agents_config.get("run_argumentation", True),
            "run_synthesizer":         agents_config.get("run_synthesizer",         True),
            "run_ckf_updater":         agents_config.get("run_ckf_updater",         True),
            "run_query_summarizer":    agents_config.get("run_query_summarizer",    True),
            "run_knowledge_extractor": agents_config.get("run_knowledge_extractor", True),
            "n_bpmn_runs":          1,
            "bpmn_weights":         {"granularity": 5, "task_type": 5,
                                     "gateways": 5, "structural": 5},
            # LangGraph adaptive retry: opt-in via agents_config (lento em batch)
            "use_langgraph":        agents_config.get("use_langgraph",     False),
            "validation_threshold": 6.0,
            "max_bpmn_retries":     3,
        }

        try:
            hub = run_pipeline(hub, pipeline_config, lambda *_: None)
        except Exception as exc:
            return FileResult(filename=title, status="failed", error=str(exc))

        try:
            save_meeting_artifacts(meeting_id, hub)
            save_meeting_tokens(
                meeting_id,
                getattr(hub.meta, "total_tokens_used", 0),
                getattr(hub.meta, "llm_provider", ""),
            )

            n_terms, n_rules = 0, 0
            if getattr(hub, "sbvr", None) and hub.sbvr.ready:
                n_terms, n_rules = save_sbvr_from_hub(meeting_id, project_id, hub)

            if getattr(hub, "bpmn", None) and hub.bpmn.ready:
                save_bpmn_from_hub(meeting_id, project_id, hub)

            req_counts: dict[str, int] = {}
            if getattr(hub, "requirements", None) and hub.requirements.ready:
                from agents.agent_req_reconciler import AgentReqReconciler
                reconciler = AgentReqReconciler(self.client_info, self.provider_cfg)
                req_counts = reconciler.run(hub, project_id, meeting_id, self.output_language)

            return FileResult(
                filename=title,
                status="done",
                meeting_id=meeting_id,
                meeting_title=title,
                req_counts=req_counts,
                n_terms=n_terms,
                n_rules=n_rules,
            )

        except Exception as exc:
            return FileResult(filename=title, status="failed", error=str(exc))

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _resolve_meta(
        self,
        content: str,
        filename: str,
        hub,
    ) -> tuple[str, Optional[date], str]:
        """Retorna (title, meeting_date, date_source).

        Estratégia de data (ordem crescente de custo):
          1. Regex no nome do arquivo (zero custo)
          2. Regex nos primeiros 2000 chars do texto (zero custo)
          3. LLM — mesmo call que sugere o título (um token por arquivo)
        """
        meeting_date: Optional[date] = None
        date_source = "none"

        # Tentativas sem LLM
        d = extract_date_from_filename(filename)
        if d:
            meeting_date, date_source = d, "filename"
        else:
            d = extract_date_from_text(content)
            if d:
                meeting_date, date_source = d, "text"

        # LLM: título + data (quando data ainda não encontrada)
        title_fallback = (
            Path(filename).stem.replace("_", " ").replace("-", " ").title()
        )
        try:
            from agents.agent_meeting_namer import AgentMeetingNamer
            namer = AgentMeetingNamer(self.client_info, self.provider_cfg)
            suggestion = namer.suggest(content, filename, hub)

            title = suggestion.get("title") or title_fallback

            if not meeting_date and suggestion.get("date"):
                try:
                    meeting_date = datetime.strptime(
                        suggestion["date"], "%Y-%m-%d"
                    ).date()
                    date_source = "llm"
                except Exception:
                    pass

            return title, meeting_date, date_source

        except Exception:
            return title_fallback, meeting_date, date_source
