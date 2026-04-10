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
            create_meeting, save_meeting_artifacts, save_meeting_tokens,
            save_sbvr_from_hub, log_batch_file, is_file_processed,
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

            save_meeting_artifacts(meeting_id, hub)
            # Garante tokens mesmo se save_meeting_artifacts falhou com payload grande
            save_meeting_tokens(
                meeting_id,
                getattr(hub.meta, "total_tokens_used", 0),
                getattr(hub.meta, "llm_provider", ""),
            )

            n_terms, n_rules = 0, 0
            if getattr(hub, "sbvr", None) and hub.sbvr.ready:
                n_terms, n_rules = save_sbvr_from_hub(meeting_id, project_id, hub)

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
