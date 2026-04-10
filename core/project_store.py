# core/project_store.py
# ─────────────────────────────────────────────────────────────────────────────
# CRUD de Projetos e Reuniões no Supabase.
#
# Todas as funções retornam None / [] em vez de lançar exceção quando o
# Supabase não está configurado ou ocorre erro de rede — o pipeline
# principal continua funcionando sem persistência nesses casos.
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

from datetime import date
from typing import Any

from modules.supabase_client import get_supabase_client


# ── helpers internos ──────────────────────────────────────────────────────────

def _db():
    return get_supabase_client()


def _ok(response) -> list[dict]:
    """Extrai dados de uma resposta Supabase ou retorna []."""
    try:
        return response.data or []
    except Exception:
        return []


# ── Projetos ──────────────────────────────────────────────────────────────────

def list_projects() -> list[dict]:
    """Retorna todos os projetos ordenados por nome."""
    db = _db()
    if not db:
        return []
    try:
        return _ok(db.table("projects").select("*").order("name").execute())
    except Exception:
        return []


def get_project(project_id: str) -> dict | None:
    """Retorna um projeto pelo ID."""
    db = _db()
    if not db:
        return None
    try:
        rows = _ok(db.table("projects").select("*").eq("id", project_id).execute())
        return rows[0] if rows else None
    except Exception:
        return None


def create_project(name: str, description: str = "") -> dict | None:
    """Cria e retorna um novo projeto."""
    db = _db()
    if not db:
        return None
    try:
        rows = _ok(
            db.table("projects")
            .insert({"name": name.strip(), "description": description.strip()})
            .execute()
        )
        return rows[0] if rows else None
    except Exception:
        return None


# ── Reuniões ──────────────────────────────────────────────────────────────────

def list_meetings(project_id: str) -> list[dict]:
    """Retorna as reuniões de um projeto, ordenadas por número."""
    db = _db()
    if not db:
        return []
    try:
        return _ok(
            db.table("meetings")
            .select("id, title, meeting_date, meeting_number, created_at, llm_provider, total_tokens")
            .eq("project_id", project_id)
            .order("meeting_number")
            .execute()
        )
    except Exception:
        return []


def _next_meeting_number(project_id: str) -> int:
    db = _db()
    if not db:
        return 1
    try:
        rows = _ok(
            db.table("meetings")
            .select("meeting_number")
            .eq("project_id", project_id)
            .order("meeting_number", desc=True)
            .limit(1)
            .execute()
        )
        return (rows[0]["meeting_number"] or 0) + 1 if rows else 1
    except Exception:
        return 1


def create_meeting(
    project_id: str,
    title: str,
    meeting_date: date | None = None,
) -> dict | None:
    """Cria uma nova reunião e retorna o registro."""
    db = _db()
    if not db:
        return None
    try:
        number = _next_meeting_number(project_id)
        payload: dict[str, Any] = {
            "project_id": project_id,
            "title": title.strip(),
            "meeting_number": number,
            "meeting_date": meeting_date.isoformat() if meeting_date else None,
        }
        rows = _ok(db.table("meetings").insert(payload).execute())
        return rows[0] if rows else None
    except Exception:
        return None


def save_meeting_tokens(meeting_id: str, total_tokens: int, llm_provider: str) -> bool:
    """Atualiza apenas tokens e provedor — payload mínimo, nunca falha por tamanho."""
    db = _db()
    if not db:
        return False
    try:
        db.table("meetings").update({
            "total_tokens": total_tokens,
            "llm_provider": llm_provider,
        }).eq("id", meeting_id).execute()
        return True
    except Exception:
        return False


def save_meeting_artifacts(meeting_id: str, hub) -> bool:
    """Persiste os artefatos gerados pelo pipeline na reunião."""
    db = _db()
    if not db:
        return False
    try:
        payload: dict[str, Any] = {
            "transcript_raw":   getattr(hub, "transcript_raw", None),
            "transcript_clean": getattr(hub, "transcript_clean", None),
            "llm_provider":     getattr(hub.meta, "llm_provider", None) if hasattr(hub, "meta") else None,
            "total_tokens":     getattr(hub.meta, "total_tokens_used", 0) if hasattr(hub, "meta") else 0,
        }
        if hasattr(hub, "bpmn") and hub.bpmn.ready:
            payload["bpmn_xml"]     = hub.bpmn.xml
            payload["mermaid_code"] = hub.bpmn.mermaid
        if hasattr(hub, "minutes") and hub.minutes.ready:
            payload["minutes_md"] = hub.minutes.full_text
        if hasattr(hub, "synthesizer") and hub.synthesizer.ready:
            payload["report_html"] = hub.synthesizer.html

        db.table("meetings").update(payload).eq("id", meeting_id).execute()
        return True
    except Exception:
        return False


# ── Requisitos ────────────────────────────────────────────────────────────────

def next_req_number(project_id: str) -> int:
    """Retorna o próximo número disponível para REQ- no projeto."""
    db = _db()
    if not db:
        return 1
    try:
        rows = _ok(
            db.rpc("next_req_number", {"p_project_id": project_id}).execute()
        )
        return rows[0] if isinstance(rows, list) and rows else 1
    except Exception:
        return 1


def save_new_requirement(
    project_id: str,
    meeting_id: str,
    req_number: int,
    title: str,
    description: str,
    req_type: str = "",
    priority: str = "",
) -> dict | None:
    """Insere um requisito novo (primeira aparição) e sua versão inicial."""
    db = _db()
    if not db:
        return None
    try:
        req_rows = _ok(
            db.table("requirements").insert({
                "project_id":      project_id,
                "req_number":      req_number,
                "title":           title,
                "description":     description,
                "req_type":        req_type,
                "priority":        priority,
                "status":          "active",
                "first_meeting_id": meeting_id,
                "last_meeting_id": meeting_id,
            }).execute()
        )
        if not req_rows:
            return None
        req = req_rows[0]

        db.table("requirement_versions").insert({
            "requirement_id": req["id"],
            "meeting_id":     meeting_id,
            "version":        1,
            "title":          title,
            "description":    description,
            "req_type":       req_type,
            "priority":       priority,
            "change_type":    "new",
        }).execute()

        return req
    except Exception:
        return None


def list_requirements(project_id: str) -> list[dict]:
    """Retorna todos os requisitos de um projeto com suas versões."""
    db = _db()
    if not db:
        return []
    try:
        return _ok(
            db.table("requirements")
            .select("*, requirement_versions(*)")
            .eq("project_id", project_id)
            .order("req_number")
            .execute()
        )
    except Exception:
        return []


def add_requirement_version(
    requirement_id: str,
    meeting_id: str,
    version: int,
    title: str,
    description: str,
    req_type: str,
    priority: str,
    change_type: str,
    change_summary: str = "",
    contradiction_flag: bool = False,
    contradiction_detail: str = "",
) -> bool:
    """Adiciona uma nova versão a um requisito existente."""
    db = _db()
    if not db:
        return False
    try:
        db.table("requirement_versions").insert({
            "requirement_id":      requirement_id,
            "meeting_id":          meeting_id,
            "version":             version,
            "title":               title,
            "description":         description,
            "req_type":            req_type,
            "priority":            priority,
            "change_type":         change_type,
            "change_summary":      change_summary,
            "contradiction_flag":  contradiction_flag,
            "contradiction_detail": contradiction_detail,
        }).execute()
        return True
    except Exception:
        return False


def update_requirement(
    requirement_id: str,
    status: str | None = None,
    last_meeting_id: str | None = None,
    title: str | None = None,
    description: str | None = None,
) -> bool:
    """Atualiza campos do registro mestre de um requisito."""
    db = _db()
    if not db:
        return False
    payload: dict[str, Any] = {"updated_at": "NOW()"}
    if status is not None:
        payload["status"] = status
    if last_meeting_id is not None:
        payload["last_meeting_id"] = last_meeting_id
    if title is not None:
        payload["title"] = title
    if description is not None:
        payload["description"] = description
    try:
        db.table("requirements").update(payload).eq("id", requirement_id).execute()
        return True
    except Exception:
        return False


def save_requirements_from_hub(meeting_id: str, project_id: str, hub) -> int:
    """Persiste todos os requisitos de hub.requirements no Supabase.

    Atribui numeração incremental por projeto (REQ-001, REQ-002...).
    Retorna o número de requisitos salvos.
    """
    db = _db()
    if not db:
        return 0
    if not hasattr(hub, "requirements") or not hub.requirements.ready:
        return 0

    items = hub.requirements.requirements
    if not items:
        return 0

    saved = 0
    next_num = next_req_number(project_id)

    for item in items:
        result = save_new_requirement(
            project_id=project_id,
            meeting_id=meeting_id,
            req_number=next_num,
            title=item.title,
            description=item.description,
            req_type=getattr(item, "type", ""),
            priority=getattr(item, "priority", ""),
        )
        if result:
            next_num += 1
            saved += 1

    return saved


# ── SBVR ──────────────────────────────────────────────────────────────────────

def save_sbvr_from_hub(meeting_id: str, project_id: str, hub) -> tuple[int, int]:
    """Persiste termos e regras SBVR do hub no Supabase.

    Retorna (n_terms, n_rules) salvos.
    """
    db = _db()
    if not db:
        return 0, 0
    if not hasattr(hub, "sbvr") or not hub.sbvr.ready:
        return 0, 0

    n_terms = n_rules = 0

    for t in hub.sbvr.vocabulary:
        try:
            db.table("sbvr_terms").insert({
                "meeting_id": meeting_id,
                "project_id": project_id,
                "term":       t.term,
                "definition": t.definition,
                "category":   t.category,
            }).execute()
            n_terms += 1
        except Exception:
            pass

    for r in hub.sbvr.rules:
        try:
            db.table("sbvr_rules").insert({
                "meeting_id": meeting_id,
                "project_id": project_id,
                "rule_id":    r.id,
                "statement":  r.statement,
                "rule_type":  r.rule_type,
                "source":     r.source,
            }).execute()
            n_rules += 1
        except Exception:
            pass

    return n_terms, n_rules


def list_sbvr_terms(project_id: str) -> list[dict]:
    """Retorna todos os termos SBVR do projeto, com reunião de origem."""
    db = _db()
    if not db:
        return []
    try:
        return _ok(
            db.table("sbvr_terms")
            .select("*, meetings(meeting_number, title, meeting_date)")
            .eq("project_id", project_id)
            .order("created_at")
            .execute()
        )
    except Exception:
        return []


def list_sbvr_rules(project_id: str) -> list[dict]:
    """Retorna todas as regras SBVR do projeto, com reunião de origem."""
    db = _db()
    if not db:
        return []
    try:
        return _ok(
            db.table("sbvr_rules")
            .select("*, meetings(meeting_number, title, meeting_date)")
            .eq("project_id", project_id)
            .order("created_at")
            .execute()
        )
    except Exception:
        return []


# ── Batch Log ─────────────────────────────────────────────────────────────────

def is_file_processed(project_id: str, file_hash: str) -> bool:
    """Retorna True se este arquivo já foi processado com sucesso neste projeto."""
    db = _db()
    if not db:
        return False
    try:
        rows = _ok(
            db.table("batch_log")
            .select("id")
            .eq("project_id", project_id)
            .eq("file_hash", file_hash)
            .eq("status", "done")
            .limit(1)
            .execute()
        )
        return bool(rows)
    except Exception:
        return False


def log_batch_file(
    project_id: str,
    meeting_id: str | None,
    filename: str,
    file_hash: str,
    status: str,
    req_counts: dict,
    n_terms: int,
    n_rules: int,
    error_detail: str,
) -> None:
    """Registra o resultado do processamento de um arquivo no batch_log."""
    db = _db()
    if not db:
        return
    try:
        db.table("batch_log").insert({
            "project_id":       project_id,
            "meeting_id":       meeting_id,
            "filename":         filename,
            "file_hash":        file_hash,
            "status":           status,
            "req_new":          req_counts.get("new", 0),
            "req_revised":      req_counts.get("revised", 0),
            "req_contradicted": req_counts.get("contradicted", 0),
            "req_confirmed":    req_counts.get("confirmed", 0),
            "n_terms":          n_terms,
            "n_rules":          n_rules,
            "error_detail":     (error_detail or "")[:500],
        }).execute()
    except Exception:
        pass


def list_batch_log(project_id: str) -> list[dict]:
    """Retorna o histórico de arquivos processados em lote para o projeto."""
    db = _db()
    if not db:
        return []
    try:
        return _ok(
            db.table("batch_log")
            .select("*")
            .eq("project_id", project_id)
            .order("processed_at", desc=True)
            .execute()
        )
    except Exception:
        return []


def list_contradictions(project_id: str) -> list[dict]:
    """Retorna versões de requisitos com contradições ativas no projeto."""
    db = _db()
    if not db:
        return []
    try:
        return _ok(
            db.table("requirement_versions")
            .select("*, requirements!inner(project_id, req_number, title, status)")
            .eq("requirements.project_id", project_id)
            .eq("contradiction_flag", True)
            .order("created_at", desc=True)
            .execute()
        )
    except Exception:
        return []
