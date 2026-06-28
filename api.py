# api.py
# ─────────────────────────────────────────────────────────────────────────────
# Process2Diagram — FastAPI Commercial API  v1.0.0
#
# Expoe o pipeline multiagente como API REST assíncrona.
# Governança (CLAUDE.md §Security):
#   • API keys NUNCA logadas, escritas em disco ou mantidas em estado global
#   • Somente o SHA-256 da key trafega além da thread de validação
#   • Fail-open em toda chamada de infraestrutura (Supabase indisponível = warn+allow)
#   • Agentes instanciados sempre via Orchestrator (nunca diretamente)
#   • KnowledgeHub como único estado canônico por execução
#
# ── Dependências extras (além do requirements.txt) ────────────────────────────
#   pip install fastapi==0.115.0 uvicorn[standard]==0.30.0 python-multipart==0.0.9 httpx==0.27.0
#
# ── Execução local ────────────────────────────────────────────────────────────
#   uvicorn api:app --reload --port 8000
#   → http://localhost:8000/docs  (Swagger UI automático)
#
# ── Variáveis de ambiente necessárias ────────────────────────────────────────
#   SUPABASE_URL   — URL do projeto Supabase
#   SUPABASE_KEY   — service_role key (nunca a anon key em produção)
#
# ── Tabela Supabase necessária ────────────────────────────────────────────────
#   Executar: setup/supabase_migration_api_keys.sql
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import os
import threading
import time
import uuid
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from typing import Any, Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ── Mapeamento provider → variável de ambiente da LLM key ─────────────────────
# O servidor usa chaves próprias (server-side) para cada provedor LLM.
# Fallback genérico: LLM_API_KEY cobre qualquer provedor não mapeado.
_PROVIDER_ENV_VARS: dict[str, str] = {
    "DeepSeek":                     "DEEPSEEK_API_KEY",
    "DeepSeek V4 Pro":              "DEEPSEEK_API_KEY",
    "DeepSeek V4 Flash (Thinking)": "DEEPSEEK_API_KEY",
    "Claude (Anthropic)":           "ANTHROPIC_API_KEY",
    "OpenAI":                       "OPENAI_API_KEY",
    "Groq (Llama)":                 "GROQ_API_KEY",
    "Google Gemini":                "GOOGLE_API_KEY",
    "Grok (xAI)":                   "XAI_API_KEY",
}


def _get_llm_api_key(provider: str) -> str:
    """
    Resolve a API key do provedor LLM a partir de variáveis de ambiente.
    Resolution order: env var específico do provedor → LLM_API_KEY → ""
    Fail-open: retorna "" se nenhuma variável encontrada (pipeline falhará no LLM call).
    """
    env_var = _PROVIDER_ENV_VARS.get(provider, "")
    key = (env_var and os.environ.get(env_var, "")) or os.environ.get("LLM_API_KEY", "")
    if not key:
        logger.warning(
            "_get_llm_api_key: nenhuma LLM key encontrada para provider='%s' "
            "(defina %s ou LLM_API_KEY)",
            provider,
            env_var or "LLM_API_KEY",
        )
    return key


# ── Executor compartilhado ─────────────────────────────────────────────────────
# Pipeline é CPU-bound + I/O-bound (LLM calls via ThreadPoolExecutor do Orchestrator).
# max_workers conservador para não saturar o servidor; ajustar conforme hardware.
_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="p2d_pipeline")


# ─────────────────────────────────────────────────────────────────────────────
# Job Store (em memória — para produção: migrar para Supabase ou Redis com TTL)
# ─────────────────────────────────────────────────────────────────────────────

class JobStatus(str, Enum):
    QUEUED  = "queued"
    RUNNING = "running"
    DONE    = "done"
    ERROR   = "error"


class JobRecord(BaseModel):
    job_id:     str
    status:     JobStatus     = JobStatus.QUEUED
    progress:   int           = 0
    created_at: float         = Field(default_factory=time.time)
    updated_at: float         = Field(default_factory=time.time)
    error:      Optional[str] = None
    result:     Optional[dict] = None


_JOBS: dict[str, JobRecord] = {}


def _get_job(job_id: str) -> JobRecord:
    job = _JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' não encontrado.")
    return job


# ─────────────────────────────────────────────────────────────────────────────
# Supabase client para contexto API (sem dependência de st.secrets / Streamlit)
# ─────────────────────────────────────────────────────────────────────────────

_api_supabase: Any = None
_api_supabase_init: bool = False


def _get_api_supabase() -> Any:
    """
    Retorna cliente Supabase para uso na API (sem Streamlit).
    Lê SUPABASE_URL e SUPABASE_KEY de variáveis de ambiente.
    Fail-open: retorna None se não configurado.
    """
    global _api_supabase, _api_supabase_init
    if _api_supabase_init:
        return _api_supabase
    _api_supabase_init = True
    try:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_KEY"]
        from supabase import create_client  # type: ignore
        _api_supabase = create_client(url, key)
        logger.info("API Supabase client: inicializado")
    except KeyError:
        logger.warning("API Supabase client: SUPABASE_URL/KEY não definidos — modo fail-open")
    except Exception as exc:
        logger.warning("API Supabase client: falha na inicialização (%s) — modo fail-open", exc)
    return _api_supabase


# ─────────────────────────────────────────────────────────────────────────────
# CAMADA 1 — Validação de API Key
# ─────────────────────────────────────────────────────────────────────────────

def _hash_key(raw_key: str) -> str:
    """SHA-256 da raw key. Nunca logar o raw_key."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def require_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """
    Dependência FastAPI — extrai e valida X-API-Key contra a tabela api_keys.

    Regras de segurança (CLAUDE.md §Security):
    - A raw key NUNCA é logada, salva em disco ou armazenada em estado global
    - Apenas o SHA-256 é comparado contra o banco
    - Fail-open: se Supabase indisponível, emite warning e libera o request
    - Chave inativa ou não encontrada → 403 (não 401, para não vazar existência)

    Schema esperado (setup/supabase_migration_api_keys.sql):
        api_keys(key_hash text UNIQUE, name text, is_active bool, last_used_at timestamptz)
    """
    if not x_api_key or not x_api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Header 'X-API-Key' obrigatório.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    key_hash = _hash_key(x_api_key.strip())

    db = _get_api_supabase()
    if db is None:
        # Fail-open: Supabase não configurado — permite, registra prefixo do hash (não da key)
        logger.warning(
            "require_api_key: Supabase indisponível — fail-open (hash_prefix=%s...)",
            key_hash[:8],
        )
        return key_hash

    try:
        resp = (
            db.table("api_keys")
            .select("name, is_active")
            .eq("key_hash", key_hash)
            .maybe_single()
            .execute()
        )
        row = resp.data if resp else None

        if not row:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API key inválida ou não reconhecida.",
            )
        if not row.get("is_active", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="API key revogada ou inativa.",
            )

        # Atualiza last_used_at de forma fire-and-forget (fail-open)
        try:
            db.table("api_keys").update(
                {"last_used_at": "now()"}
            ).eq("key_hash", key_hash).execute()
        except Exception:
            pass

        logger.info(
            "require_api_key: autenticado client='%s' hash_prefix=%s...",
            row.get("name", "?"),
            key_hash[:8],
        )

    except HTTPException:
        raise
    except Exception as exc:
        # Fail-open: erro de DB — permite, registra causa
        logger.warning(
            "require_api_key: erro de DB (%s) — fail-open (hash_prefix=%s...)",
            exc,
            key_hash[:8],
        )

    return key_hash


# ─────────────────────────────────────────────────────────────────────────────
# CAMADA 2 — Controle de Concorrência e Rate Limiting
# ─────────────────────────────────────────────────────────────────────────────

# Contador global de pipelines ativos — proteção contra abuso de concorrência.
# Chamadas LLM são pesadas (ThreadPoolExecutor + latência de API); limitar
# jobs simultâneos evita saturação de memória e timeouts em cascata.
MAX_CONCURRENT_PIPELINES: int = 4
_active_pipeline_count: int = 0
_active_pipeline_lock = threading.Lock()

# Sliding window por key: máximo de _RATE_MAX_REQUESTS starts em _RATE_WINDOW_SECS.
# Usando deque de timestamps para expiração O(1).
_RATE_WINDOW_SECS: int = 60
_RATE_MAX_REQUESTS: int = 10
_key_windows: dict[str, deque] = {}
_key_windows_lock = threading.Lock()


async def check_rate_limit(key_hash: str = Depends(require_api_key)) -> str:
    """
    Dependência FastAPI — duas camadas de proteção em memória volátil:

    1. Cap global de concorrência: se _active_pipeline_count >= MAX_CONCURRENT_PIPELINES
       → 429. Protege contra rajadas simultâneas de pipelines pesados.
       O contador é decrementado em _run_pipeline_sync (finally block).

    2. Sliding window por key: máximo _RATE_MAX_REQUESTS starts em _RATE_WINDOW_SECS.
       Expiração O(1) via deque. Reseta ao reiniciar o processo (volátil por design).

    Fail-open: qualquer erro inesperado de tracking libera o request.
    """
    try:
        # ── 1. Cap global ────────────────────────────────────────────────────
        with _active_pipeline_lock:
            if _active_pipeline_count >= MAX_CONCURRENT_PIPELINES:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Servidor no limite de {MAX_CONCURRENT_PIPELINES} pipelines "
                        "simultâneos. Tente novamente em instantes."
                    ),
                    headers={"Retry-After": "10"},
                )

        # ── 2. Sliding window por key ────────────────────────────────────────
        now = time.monotonic()
        with _key_windows_lock:
            window = _key_windows.setdefault(key_hash, deque())
            # Expira entradas fora da janela
            while window and now - window[0] > _RATE_WINDOW_SECS:
                window.popleft()
            if len(window) >= _RATE_MAX_REQUESTS:
                retry_after = max(1, int(_RATE_WINDOW_SECS - (now - window[0])) + 1)
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=(
                        f"Limite de {_RATE_MAX_REQUESTS} requisições por "
                        f"{_RATE_WINDOW_SECS}s atingido. "
                        f"Tente novamente em {retry_after}s."
                    ),
                    headers={"Retry-After": str(retry_after)},
                )
            window.append(now)

    except HTTPException:
        raise
    except Exception as exc:
        # Fail-open: erro no tracking — libera o request
        logger.warning("check_rate_limit: erro inesperado (%s) — fail-open", exc)

    return key_hash


# ─────────────────────────────────────────────────────────────────────────────
# Modelos de Request / Response (Pydantic v2)
# ─────────────────────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    job_id:     str = Field(..., description="Identificador único do job criado.")
    char_count: int = Field(..., description="Tamanho do texto extraído em caracteres.")
    message:    str = "Transcrição recebida. Use /pipeline/run com este job_id."


class PipelineConfig(BaseModel):
    """Configuração do pipeline — espelha os parâmetros de core/session_state.py."""
    job_id:           str           = Field(..., description="ID retornado pelo /upload.")
    provider:         str           = Field("DeepSeek", description="Provedor LLM.")
    model:            Optional[str] = Field(None, description="Modelo; None = default do provedor.")
    run_quality:      bool          = True
    run_bpmn:         bool          = True
    run_minutes:      bool          = True
    run_requirements: bool          = True
    run_sbvr:         bool          = True
    run_bmm:          bool          = True
    run_synthesizer:  bool          = True
    n_bpmn_runs:      int           = Field(3, ge=1, le=5)
    use_langgraph:    bool          = True
    output_language:  str           = "Auto-detect"
    project_id:       Optional[str] = Field(None, description="UUID do projeto Supabase.")


class PipelineRunResponse(BaseModel):
    job_id:  str
    status:  JobStatus = JobStatus.QUEUED
    message: str       = "Pipeline enfileirado. Consulte /status/{job_id} para acompanhar."


class StatusResponse(BaseModel):
    job_id:     str
    status:     JobStatus
    progress:   int
    created_at: float
    updated_at: float
    error:      Optional[str]
    result:     Optional[dict]


# ─────────────────────────────────────────────────────────────────────────────
# FastAPI app
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Process2Diagram API",
    version="1.0.0",
    description=(
        "API REST assíncrona para o pipeline multiagente Process2Diagram. "
        "Converte transcrições de reuniões em BPMN, Mermaid, ata e requisitos."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # restringir em produção
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 1 — POST /upload  (sem autenticação — ingestão pública de transcrição)
# ─────────────────────────────────────────────────────────────────────────────

@app.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload de transcrição",
    tags=["Pipeline"],
)
async def upload_transcript(
    text: Optional[str]        = Form(None),
    file: Optional[UploadFile] = File(None),
) -> UploadResponse:
    """
    Recebe transcrição como texto (form field) ou arquivo (.txt / .docx / .pdf).
    Cria um job_id e armazena o texto extraído. Nenhuma chamada LLM ocorre aqui.
    """
    extracted: str = ""

    if file is not None:
        try:
            from modules.ingest import load_transcript  # type: ignore
            raw_bytes = await file.read()
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
        result={"_transcript_raw": extracted},
    )

    logger.info("upload: job_id=%s chars=%d", job_id, len(extracted))
    return UploadResponse(job_id=job_id, char_count=len(extracted))


# ─────────────────────────────────────────────────────────────────────────────
# Worker síncrono — executa na ThreadPool (fora do event loop)
# ─────────────────────────────────────────────────────────────────────────────

def _run_pipeline_sync(
    job_id:     str,
    transcript: str,
    config:     PipelineConfig,
) -> None:
    """
    Executa o pipeline completo em thread isolada.
    Segue CLAUDE.md §Agent Pattern: always go through Orchestrator.
    Fail-open: qualquer exceção → status ERROR (nunca propaga para o event loop).
    Decrementa _active_pipeline_count no finally (par com check_rate_limit).
    A LLM API key é resolvida internamente via _get_llm_api_key() (env vars).
    """
    global _active_pipeline_count

    job = _JOBS[job_id]

    def _progress(pct: int, msg: str = "") -> None:
        job.progress   = pct
        job.updated_at = time.time()
        if msg:
            logger.info("job %s [%d%%] %s", job_id, pct, msg)

    # Incrementa contador de pipelines ativos (decrementado no finally)
    with _active_pipeline_lock:
        _active_pipeline_count += 1

    try:
        job.status     = JobStatus.RUNNING
        job.updated_at = time.time()
        _progress(5, "Inicializando KnowledgeHub")

        # ── Construir client_info explícito (sem st.session_state) ────────────
        # Após a refatoração de BaseAgent._call_llm(), client_info é a única
        # fonte de verdade para configuração do agente no contexto API.
        # "enable_long_context" e "scenario_assignments" são lidos de client_info
        # com prioridade sobre st.session_state — eliminando a dependência Streamlit.
        from modules.config import AVAILABLE_PROVIDERS  # type: ignore

        provider_name = config.provider
        provider_cfg  = dict(AVAILABLE_PROVIDERS.get(provider_name, AVAILABLE_PROVIDERS["DeepSeek"]))

        # Sobrescreve modelo se especificado explicitamente no request
        if config.model:
            provider_cfg["default_model"] = config.model

        llm_api_key = _get_llm_api_key(provider_name)
        client_info: dict[str, Any] = {
            "api_key":             llm_api_key,
            "provider":            provider_name,
            "enable_long_context": True,       # BaseAgent lê daqui (sem st.session_state)
            "scenario_assignments": {},        # BaseAgent lê daqui (sem st.session_state)
        }

        # ── Inicializar KnowledgeHub ────────────────────────────────────────
        _progress(10, "Construindo KnowledgeHub")
        from core.knowledge_hub import KnowledgeHub  # type: ignore
        hub = KnowledgeHub.new(transcript_raw=transcript)

        # ── Montar pipeline config completo ────────────────────────────────────
        # Inclui client_info e provider_cfg explícitos — core/pipeline.py os lê
        # diretamente sem tocar em st.session_state.
        pipeline_cfg: dict[str, Any] = {
            "client_info":          client_info,
            "provider_cfg":         provider_cfg,
            "output_language":      config.output_language,
            "run_quality":          config.run_quality,
            "run_bpmn":             config.run_bpmn,
            "run_minutes":          config.run_minutes,
            "run_requirements":     config.run_requirements,
            "run_sbvr":             config.run_sbvr,
            "run_bmm":              config.run_bmm,
            "run_synthesizer":      config.run_synthesizer,
            "n_bpmn_runs":          config.n_bpmn_runs,
            "use_langgraph":        config.use_langgraph,
            "bpmn_weights":         {},
            "project_id":           config.project_id or "",
            "run_knowledge_extractor": False,  # desabilitado na API por padrão
        }

        # ── Executar pipeline via run_pipeline() — nunca instanciar agentes ─
        _progress(15, "Executando pipeline")
        from core.pipeline import run_pipeline  # type: ignore

        hub = run_pipeline(
            hub,
            pipeline_cfg,
            lambda pct, msg="": _progress(15 + int(pct * 0.80), msg),
        )

        _progress(96, "Extraindo resumo de artefatos")
        result_summary = _extract_hub_summary(hub)

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

    finally:
        # Sempre decrementa — garante que o contador não vaze mesmo em erro
        with _active_pipeline_lock:
            _active_pipeline_count = max(0, _active_pipeline_count - 1)


def _extract_hub_summary(hub: Any) -> dict:
    """
    Extrai resumo serializado do KnowledgeHub.
    Fail-open: nunca lança exceção — retorna o que conseguiu coletar.
    """
    summary: dict[str, Any] = {}
    try:
        if hub.bpmn:
            summary["bpmn"] = {
                "steps_count": len(getattr(hub.bpmn, "steps", []) or []),
                "lanes":       list(getattr(hub.bpmn, "lanes", []) or []),
                "has_mermaid": bool(getattr(hub.bpmn, "mermaid", "")),
                "has_xml":     bool(getattr(hub.bpmn, "xml", "")),
            }
    except Exception:
        pass
    try:
        if hub.minutes:
            summary["minutes"] = {
                "participants": len(getattr(hub.minutes, "participants", []) or []),
                "decisions":    len(getattr(hub.minutes, "decisions", []) or []),
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
            "hub_id":       str(getattr(hub.meta, "hub_id", "") or ""),
            "agents_run":   list(getattr(hub.meta, "agents_run", set()) or set()),
            "cache_hits":   getattr(hub.meta, "cache_hits", 0),
            "tokens_saved": getattr(hub.meta, "tokens_saved", 0),
        }
    except Exception:
        pass
    return summary


def _persist_hub(hub: Any, project_id: str) -> None:
    """
    Persiste artefatos do hub no Supabase.
    Fail-open: loga e retorna silenciosamente em qualquer erro.
    """
    try:
        from core import project_store  # type: ignore  # noqa: F401
        # project_store.save_hub_to_db(hub, project_id)  # TODO: implementar
        logger.info("_persist_hub: stub — project_id=%s (implementar save_hub_to_db)", project_id)
    except Exception as exc:
        logger.warning("_persist_hub: falha silenciosa — %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 2 — POST /pipeline/run  (autenticado + rate limited)
# ─────────────────────────────────────────────────────────────────────────────

@app.post(
    "/pipeline/run",
    response_model=PipelineRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Executa o pipeline multiagente",
    tags=["Pipeline"],
)
async def run_pipeline_endpoint(
    config:   PipelineConfig,
    key_hash: str = Depends(check_rate_limit),
) -> PipelineRunResponse:
    """
    Fire-and-forget assíncrono:
    1. Valida job_id e recupera transcrição armazenada pelo /upload
    2. Submete _run_pipeline_sync() ao ThreadPoolExecutor
    3. Retorna 202 Accepted imediatamente

    A X-API-Key é validada pela dependência check_rate_limit (que inclui require_api_key).
    A key bruta é transmitida ao worker apenas como variável de thread — nunca persiste.
    """
    job = _get_job(config.job_id)

    if job.status not in (JobStatus.QUEUED, JobStatus.ERROR):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Job '{config.job_id}' já está em status '{job.status}'. "
                "Crie um novo job via /upload para re-executar."
            ),
        )

    transcript_raw = (job.result or {}).get("_transcript_raw", "")
    if not transcript_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transcrição não encontrada para este job_id. O /upload foi chamado?",
        )

    # Limpa armazenamento temporário antes de enfileirar
    job.result = None

    # Enfileira na ThreadPool — não bloqueia o event loop
    loop = asyncio.get_running_loop()
    loop.run_in_executor(
        _EXECUTOR,
        _run_pipeline_sync,
        config.job_id,
        transcript_raw,
        config,
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
    tags=["Pipeline"],
)
async def get_job_status(job_id: str) -> StatusResponse:
    """Retorna status, progresso e resultado (quando done) do job."""
    job = _get_job(job_id)
    return StatusResponse(
        job_id     = job.job_id,
        status     = job.status,
        progress   = job.progress,
        created_at = job.created_at,
        updated_at = job.updated_at,
        error      = job.error,
        result     = job.result if job.status == JobStatus.DONE else None,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint 4 — GET /health
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Infra"])
async def health_check() -> dict:
    """Liveness probe — verifica Supabase, workers e pipelines ativos."""
    supabase_ok = _get_api_supabase() is not None
    with _active_pipeline_lock:
        active = _active_pipeline_count

    return {
        "status":               "ok",
        "version":              "1.0.0",
        "supabase":             "configured" if supabase_ok else "not_configured",
        "active_pipelines":     active,
        "max_pipelines":        MAX_CONCURRENT_PIPELINES,
        "queued_jobs":          sum(1 for j in _JOBS.values() if j.status == JobStatus.QUEUED),
        "executor_max_workers": _EXECUTOR._max_workers,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
