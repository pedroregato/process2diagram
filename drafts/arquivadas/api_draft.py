# api_draft.py
# ─────────────────────────────────────────────────────────────────────────────
# Process2Diagram — FastAPI async wrapper (RASCUNHO CONCEITUAL)
#
# Objetivo: expor o pipeline multiagente como API REST assíncrona,
# preservando todas as regras de governança do CLAUDE.md:
#   • Fail-open em todo acesso ao Supabase
#   • Nenhum agente instanciado diretamente — sempre via Orchestrator
#   • KnowledgeHub como único estado canônico por execução
#   • PII Sanitization transparente (herdada do BaseAgent._call_llm)
#   • API keys nunca persistidas — transmitidas por header, vivem apenas
#     na thread de execução do job
#
# ── Instalação das dependências extras ───────────────────────────────────────
#   pip install fastapi==0.115.0 uvicorn[standard]==0.30.0 python-multipart==0.0.9
#
# ── Execução local ───────────────────────────────────────────────────────────
#   uvicorn api_draft:app --reload --port 8000
#   → http://localhost:8000/docs  (Swagger UI automático)
#
# ── NÃO substitui o app Streamlit ────────────────────────────────────────────
# Este arquivo é um rascunho para explorar a API surface antes de uma decisão
# arquitetural. O pipeline Streamlit (app.py) permanece a entrypoint principal.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import asyncio
import io
import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Any, Optional

from fastapi import FastAPI, File, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ── Executor compartilhado ────────────────────────────────────────────────────
# O Orchestrator é CPU-bound + I/O-bound (LLM calls).
# max_workers=4 evita saturar o event loop; ajustar conforme hardware.
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="p2d_pipeline")


# ─────────────────────────────────────────────────────────────────────────────
# Job Store (em memória — para produção: migrar para Supabase ou Redis)
# ─────────────────────────────────────────────────────────────────────────────

class JobStatus(str, Enum):
    QUEUED  = "queued"
    RUNNING = "running"
    DONE    = "done"
    ERROR   = "error"


class JobRecord(BaseModel):
    job_id:      str
    status:      JobStatus        = JobStatus.QUEUED
    progress:    int              = 0          # 0–100
    created_at:  float            = Field(default_factory=time.time)
    updated_at:  float            = Field(default_factory=time.time)
    error:       Optional[str]    = None
    result:      Optional[dict]   = None       # resumo de artefatos ao concluir


# Singleton simples — em produção substituir por TTLCache ou tabela Supabase
_JOBS: dict[str, JobRecord] = {}

def _get_job(job_id: str) -> JobRecord:
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' não encontrado.")
    return job


# ─────────────────────────────────────────────────────────────────────────────
# Modelos de Request / Response (Pydantic v2)
# ─────────────────────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    """Retorno do endpoint /upload."""
    job_id:     str  = Field(..., description="Identificador único do job criado.")
    char_count: int  = Field(..., description="Tamanho do texto extraído em caracteres.")
    message:    str  = "Transcrição recebida. Use /pipeline/run com este job_id."


class PipelineConfig(BaseModel):
    """
    Configuração do pipeline — espelha os parâmetros de core/session_state.py.
    Todos os campos têm defaults alinhados com os padrões do CLAUDE.md.
    """
    job_id:           str            = Field(..., description="ID retornado pelo /upload.")
    provider:         str            = Field("DeepSeek", description="Provedor LLM principal.")
    model:            Optional[str]  = Field(None, description="Modelo específico; None = default do provedor.")
    run_quality:      bool           = True
    run_bpmn:         bool           = True
    run_minutes:      bool           = True
    run_requirements: bool           = True
    run_sbvr:         bool           = True
    run_bmm:          bool           = True
    run_synthesizer:  bool           = True
    n_bpmn_runs:      int            = Field(3, ge=1, le=5, description="Nº de runs do AgentBPMN (tournament).")
    use_langgraph:    bool           = True
    output_language:  str            = "Auto-detect"
    project_id:       Optional[str]  = Field(None, description="UUID do projeto Supabase para persistência.")


class PipelineRunResponse(BaseModel):
    """Retorno imediato do /pipeline/run (fire-and-forget assíncrono)."""
    job_id:  str
    status:  JobStatus = JobStatus.QUEUED
    message: str       = "Pipeline enfileirado. Consulte /status/{job_id} para acompanhar."


class StatusResponse(BaseModel):
    """Retorno do /status/{job_id}."""
    job_id:     str
    status:     JobStatus
    progress:   int
    created_at: float
    updated_at: float
    error:      Optional[str]
    result:     Optional[dict]   # populado apenas quando status == DONE


# ─────────────────────────────────────────────────────────────────────────────
# Aplicação FastAPI
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Process2Diagram API",
    version="0.1.0-draft",
    description=(
        "API REST assíncrona para o pipeline multiagente Process2Diagram. "
        "Converte transcrições de reuniões em BPMN, Mermaid, ata e requisitos. "
        "**Rascunho conceitual** — não para uso em produção sem revisão adicional."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — ajustar origins para produção
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # restringir em produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Helper de autenticação
# ─────────────────────────────────────────────────────────────────────────────

def _extract_api_key(authorization: Optional[str]) -> str:
    """
    Extrai a API key do header Authorization: Bearer <key>.

    Regra de governança (CLAUDE.md §Security):
    API keys vivem APENAS em memória da thread de execução — nunca logadas,
    nunca persistidas. O header chega, a key é repassada ao Orchestrator, e
    descartada ao final da thread.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header 'Authorization: Bearer <api_key>' obrigatório.",
        )
    return authorization.removeprefix("Bearer ").strip()


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 1 — POST /upload
# ─────────────────────────────────────────────────────────────────────────────

@app.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload de transcrição",
    description=(
        "Recebe uma transcrição como texto plain ou arquivo (.txt, .docx, .pdf). "
        "Cria um job_id e armazena o texto extraído. "
        "Retorna o job_id para uso em /pipeline/run."
    ),
    tags=["Pipeline"],
)
async def upload_transcript(
    text: Optional[str]             = None,
    file: Optional[UploadFile]      = File(None, description="Arquivo .txt, .docx ou .pdf."),
) -> UploadResponse:
    """
    Dois modos de ingestão (espelha ui/input_area.py):
    - `text`: transcrição colada diretamente no body como form field
    - `file`: upload de arquivo; extração via modules.ingest.load_transcript()

    Um job_id é gerado e o texto extraído é armazenado em _JOBS.
    Nenhuma chamada LLM ocorre aqui.
    """
    extracted: str = ""

    if file is not None:
        # ── Extração de arquivo (.txt / .docx / .pdf) ─────────────────────────
        # Reutiliza o ingestor existente — sem duplicação de lógica
        try:
            from modules.ingest import load_transcript  # type: ignore
            raw_bytes = await file.read()
            # load_transcript aceita file-like com atributo .name
            fake_file = io.BytesIO(raw_bytes)
            fake_file.name = file.filename or "upload.txt"  # type: ignore[attr-defined]
            extracted = load_transcript(fake_file) or ""
        except ImportError:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Módulo 'modules.ingest' não encontrado. Verifique PYTHONPATH.",
            )
        except Exception as exc:
            logger.error("upload: erro ao extrair arquivo: %s", exc)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Falha ao extrair texto do arquivo: {exc}",
            )
    elif text:
        extracted = text.strip()
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Forneça 'text' (form field) ou 'file' (upload).",
        )

    if len(extracted) < 50:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Transcrição muito curta ({len(extracted)} chars). Mínimo: 50 caracteres.",
        )

    job_id = str(uuid.uuid4())
    _JOBS[job_id] = JobRecord(
        job_id=job_id,
        # Guarda o texto no campo result temporariamente até /pipeline/run
        result={"_transcript_raw": extracted},
    )

    logger.info("upload: job_id=%s chars=%d", job_id, len(extracted))
    return UploadResponse(job_id=job_id, char_count=len(extracted))


# ─────────────────────────────────────────────────────────────────────────────
# Worker síncrono — executado na ThreadPool (NÃO no event loop)
# ─────────────────────────────────────────────────────────────────────────────

def _run_pipeline_sync(
    job_id:     str,
    transcript: str,
    config:     PipelineConfig,
    api_key:    str,
) -> None:
    """
    Executa o pipeline completo numa thread isolada.

    Segue o padrão do CLAUDE.md §Agent Pattern:
    1. Monta pipeline_cfg compatível com o que Orchestrator espera
    2. Chama run_pipeline(hub, config, callback)
    3. Atualiza _JOBS[job_id] com progresso e resultado
    4. Nunca deixa exceção vazar — fail-open → status ERROR

    NOTA IMPORTANTE: O Orchestrator e BaseAgent leem st.session_state para
    resolver API keys e provider config. Em ambiente API (sem Streamlit), é
    necessário injetar os valores via um mock de session_state ou refatorar
    BaseAgent para aceitar um `config dict` explícito.
    Esta implementação usa uma abordagem de patch mínimo documentado abaixo —
    a refatoração definitiva é um item de roadmap separado.
    """
    job = _JOBS[job_id]

    def _progress(pct: int, msg: str = "") -> None:
        """Callback de progresso para run_pipeline()."""
        job.progress   = pct
        job.updated_at = time.time()
        if msg:
            logger.info("job %s [%d%%] %s", job_id, pct, msg)

    try:
        job.status    = JobStatus.RUNNING
        job.updated_at = time.time()
        _progress(5, "Inicializando KnowledgeHub")

        # ── 1. Injetar config no session_state para compatibilidade com BaseAgent ──
        # TODO (roadmap): refatorar BaseAgent para aceitar config dict explícito,
        # eliminando a dependência de st.session_state em contexto API.
        try:
            import streamlit as st  # type: ignore
            _session_patch: dict[str, Any] = {
                "provider":             config.provider,
                "model":                config.model or "",
                "api_key":              api_key,
                "run_quality":          config.run_quality,
                "run_bpmn":             config.run_bpmn,
                "run_minutes":          config.run_minutes,
                "run_requirements":     config.run_requirements,
                "run_sbvr":             config.run_sbvr,
                "run_bmm":              config.run_bmm,
                "run_synthesizer":      config.run_synthesizer,
                "n_bpmn_runs":          config.n_bpmn_runs,
                "use_langgraph":        config.use_langgraph,
                "enable_long_context":  True,
                "asst_embed_provider":  "OpenAI",
                "asst_embed_key":       api_key,
            }
            for k, v in _session_patch.items():
                if k not in st.session_state:
                    st.session_state[k] = v
        except Exception:
            # Streamlit não está rodando — session_state inacessível.
            # Alternativa: passar config diretamente ao Orchestrator (roadmap).
            logger.warning("job %s: st.session_state inacessível — operando sem patch", job_id)

        # ── 2. Inicializar KnowledgeHub ───────────────────────────────────────
        _progress(10, "Construindo KnowledgeHub")
        from core.knowledge_hub import KnowledgeHub  # type: ignore
        hub = KnowledgeHub.new(transcript_raw=transcript)

        # ── 3. Montar pipeline config dict ────────────────────────────────────
        pipeline_cfg: dict[str, Any] = {
            "provider":         config.provider,
            "model":            config.model,
            "run_quality":      config.run_quality,
            "run_bpmn":         config.run_bpmn,
            "run_minutes":      config.run_minutes,
            "run_requirements": config.run_requirements,
            "run_sbvr":         config.run_sbvr,
            "run_bmm":          config.run_bmm,
            "run_synthesizer":  config.run_synthesizer,
            "n_bpmn_runs":      config.n_bpmn_runs,
            "use_langgraph":    config.use_langgraph,
            "output_language":  config.output_language,
        }

        # ── 4. Executar pipeline via run_pipeline() ───────────────────────────
        # Regra CLAUDE.md: "never instantiate agents directly — always go
        # through Orchestrator or handle_rerun"
        _progress(15, "Executando pipeline")
        from core.pipeline import run_pipeline  # type: ignore

        hub = run_pipeline(
            hub,
            pipeline_cfg,
            lambda pct, msg="": _progress(15 + int(pct * 0.80), msg),
        )

        # ── 5. Extrair resumo de artefatos do KnowledgeHub ────────────────────
        _progress(96, "Extraindo resumo de artefatos")
        result_summary = _extract_hub_summary(hub)

        # ── 6. Persistir no Supabase se project_id fornecido ─────────────────
        if config.project_id and hub:
            _progress(98, "Persistindo no Supabase")
            _persist_hub(hub, config.project_id)

        job.status     = JobStatus.DONE
        job.progress   = 100
        job.result     = result_summary
        job.updated_at = time.time()
        logger.info("job %s: concluído com sucesso", job_id)

    except Exception as exc:
        logger.error("job %s: erro no pipeline: %s", job_id, exc, exc_info=True)
        job.status     = JobStatus.ERROR
        job.error      = str(exc)
        job.updated_at = time.time()


def _extract_hub_summary(hub: Any) -> dict:
    """
    Extrai um resumo serializado do KnowledgeHub para retornar via API.
    Fail-open: nunca lança exceção — retorna o que conseguiu coletar.
    """
    summary: dict[str, Any] = {}
    try:
        if hub.bpmn:
            summary["bpmn"] = {
                "steps_count": len(getattr(hub.bpmn, "steps",  []) or []),
                "lanes":       list(getattr(hub.bpmn, "lanes",  []) or []),
                "has_mermaid": bool(getattr(hub.bpmn, "mermaid", "")),
                "has_xml":     bool(getattr(hub.bpmn, "xml",    "")),
            }
    except Exception:
        pass
    try:
        if hub.minutes:
            summary["minutes"] = {
                "participants": len(getattr(hub.minutes, "participants", []) or []),
                "decisions":    len(getattr(hub.minutes, "decisions",    []) or []),
                "action_items": len(getattr(hub.minutes, "action_items", []) or []),
            }
    except Exception:
        pass
    try:
        if hub.requirements:
            reqs = getattr(hub.requirements, "requirements", []) or []
            summary["requirements"] = {
                "count":      len(reqs),
                "functional": sum(1 for r in reqs if getattr(r, "type", "") == "functional"),
            }
    except Exception:
        pass
    try:
        summary["meta"] = {
            "version":      getattr(hub, "version", 0),
            "hub_id":       str(getattr(hub.meta, "hub_id",    "") or ""),
            "agents_run":   list(getattr(hub.meta, "agents_run", set()) or set()),
            "cache_hits":   getattr(hub.meta, "cache_hits",   0),
            "tokens_saved": getattr(hub.meta, "tokens_saved", 0),
        }
    except Exception:
        pass
    return summary


def _persist_hub(hub: Any, project_id: str) -> None:
    """
    Persiste os artefatos do hub no Supabase.
    Fail-open: loga e retorna silenciosamente em qualquer erro.

    TODO: implementar save_hub_to_db(hub, project_id) em core/project_store.py
    equivalente ao que Pipeline.py faz após a execução Streamlit.
    """
    try:
        from core import project_store  # type: ignore  # noqa: F401
        # project_store.save_hub_to_db(hub, project_id)  # a implementar
        logger.info("_persist_hub: project_id=%s (stub — implementar save_hub_to_db)", project_id)
    except Exception as exc:
        logger.warning("_persist_hub: falha silenciosa — %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 2 — POST /pipeline/run
# ─────────────────────────────────────────────────────────────────────────────

@app.post(
    "/pipeline/run",
    response_model=PipelineRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Executa o pipeline multiagente",
    description=(
        "Enfileira a execução do pipeline para o job_id retornado pelo /upload. "
        "Retorna imediatamente com status 'queued'. "
        "Acompanhe o progresso em GET /status/{job_id}. "
        "A API key do provedor LLM deve ser enviada no header Authorization."
    ),
    tags=["Pipeline"],
)
async def run_pipeline_endpoint(
    config:        PipelineConfig,
    authorization: Optional[str] = Header(None),
) -> PipelineRunResponse:
    """
    Fire-and-forget assíncrono:
    1. Valida job_id e recupera transcrição armazenada pelo /upload
    2. Extrai API key do header Authorization (nunca persistida)
    3. Submete _run_pipeline_sync() ao ThreadPoolExecutor
    4. Retorna 202 Accepted imediatamente — sem bloquear o event loop
    """
    api_key = _extract_api_key(authorization)
    job     = _get_job(config.job_id)

    if job.status not in (JobStatus.QUEUED, JobStatus.ERROR):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Job '{config.job_id}' já está em status '{job.status}'. "
                "Crie um novo job via /upload para re-executar."
            ),
        )

    # Recupera a transcrição armazenada pelo /upload
    transcript_raw = (job.result or {}).get("_transcript_raw", "")
    if not transcript_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transcrição não encontrada para este job_id. O /upload foi chamado?",
        )

    # Limpa o campo interno antes de enfileirar
    job.result = None

    # Enfileira na ThreadPool — não bloqueia o event loop do FastAPI
    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        _EXECUTOR,
        _run_pipeline_sync,
        config.job_id,
        transcript_raw,
        config,
        api_key,
    )

    logger.info("pipeline/run: job_id=%s provider=%s", config.job_id, config.provider)
    return PipelineRunResponse(job_id=config.job_id)


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 3 — GET /status/{job_id}
# ─────────────────────────────────────────────────────────────────────────────

@app.get(
    "/status/{job_id}",
    response_model=StatusResponse,
    summary="Consulta status do job",
    description=(
        "Retorna o status atual do job: queued / running / done / error. "
        "O campo 'progress' vai de 0 a 100. "
        "Quando status == 'done', 'result' contém o resumo dos artefatos gerados."
    ),
    tags=["Pipeline"],
)
async def get_job_status(job_id: str) -> StatusResponse:
    job = _get_job(job_id)
    return StatusResponse(
        job_id     = job.job_id,
        status     = job.status,
        progress   = job.progress,
        created_at = job.created_at,
        updated_at = job.updated_at,
        error      = job.error,
        # result só exposto quando concluído — evita vazar dados parciais
        result     = job.result if job.status == JobStatus.DONE else None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint auxiliar — GET /health
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Infra"])
async def health_check() -> dict:
    """Liveness probe — verifica conectividade Supabase e workers disponíveis."""
    supabase_ok = False
    try:
        from modules.supabase_client import supabase_configured  # type: ignore
        supabase_ok = supabase_configured()
    except Exception:
        pass

    return {
        "status":           "ok",
        "version":          "0.1.0-draft",
        "supabase":         "configured" if supabase_ok else "not_configured",
        "active_jobs":      sum(1 for j in _JOBS.values() if j.status == JobStatus.RUNNING),
        "queued_jobs":      sum(1 for j in _JOBS.values() if j.status == JobStatus.QUEUED),
        "executor_threads": _EXECUTOR._max_workers,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Entry point direto
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_draft:app", host="0.0.0.0", port=8000, reload=True)
