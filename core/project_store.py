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
from modules.text_utils import rule_keyword_pt


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

def list_contexts() -> list[dict]:
    """Retorna todos os contextos ordenados por nome."""
    db = _db()
    if not db:
        return []
    try:
        return _ok(db.table("contexts").select("*").order("name").execute())
    except Exception:
        return []


def get_context(context_id: str) -> dict | None:
    """Retorna um contexto pelo ID."""
    db = _db()
    if not db:
        return None
    try:
        rows = _ok(db.table("contexts").select("*").eq("id", context_id).execute())
        return rows[0] if rows else None
    except Exception:
        return None


def create_context(name: str, description: str = "", sigla: str = "",
                   context_type: str = "project") -> dict | None:
    """Cria e retorna um novo contexto."""
    db = _db()
    if not db:
        return None
    payload: dict = {
        "name":         name.strip(),
        "description":  description.strip(),
        "context_type": context_type,
    }
    if sigla:
        payload["sigla"] = sigla.strip().upper()
    try:
        rows = _ok(db.table("contexts").insert(payload).execute())
        return rows[0] if rows else None
    except Exception:
        # Retry without optional columns in case migration hasn't run yet
        try:
            payload.pop("sigla", None)
            payload.pop("context_type", None)
            rows = _ok(db.table("contexts").insert(payload).execute())
            return rows[0] if rows else None
        except Exception:
            return None


def get_context_skill(context_id: str) -> str | None:
    """Fetch the Context Knowledge File (skill_md) for a context."""
    client = get_supabase_client()
    if not client:
        return None
    try:
        res = client.table("contexts").select("skill_md").eq("id", context_id).single().execute()
        return res.data.get("skill_md") if res.data else None
    except Exception:
        return None


def save_context_skill(context_id: str, skill_md: str) -> bool:
    """Persist the Context Knowledge File for a context. Returns True on success."""
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.table("contexts").update({"skill_md": skill_md}).eq("id", context_id).execute()
        return True
    except Exception:
        return False


# ── Context Files ─────────────────────────────────────────────────────────────

def list_context_files(context_id: str) -> list[dict]:
    """List all uploaded reference files for a context, newest first."""
    db = _db()
    if not db:
        return []
    try:
        return _ok(
            db.table("context_files")
            .select("id, filename, file_type, file_size, uploaded_at, uploaded_by")
            .eq("context_id", context_id)
            .order("uploaded_at", desc=True)
            .execute()
        )
    except Exception:
        return []


def save_context_file(context_id: str, filename: str, file_type: str,
                      content_text: str, file_size: int,
                      uploaded_by: str = "") -> dict | None:
    """Persist an uploaded context file (extracted text). Returns the new row or None."""
    db = _db()
    if not db:
        return None
    try:
        rows = _ok(
            db.table("context_files").insert({
                "context_id":   context_id,
                "filename":     filename,
                "file_type":    file_type,
                "content_text": content_text,
                "file_size":    file_size,
                "uploaded_by":  uploaded_by,
            }).execute()
        )
        return rows[0] if rows else None
    except Exception:
        return None


def delete_context_file(file_id: str) -> bool:
    """Delete a context file by ID. Returns True on success."""
    db = _db()
    if not db:
        return False
    try:
        db.table("context_files").delete().eq("id", file_id).execute()
        return True
    except Exception:
        return False


def get_context_files_text(context_id: str) -> str:
    """Return combined extracted text from all context files for a context."""
    db = _db()
    if not db:
        return ""
    try:
        rows = _ok(
            db.table("context_files")
            .select("filename, file_type, content_text")
            .eq("context_id", context_id)
            .order("uploaded_at", desc=True)
            .execute()
        )
        parts = []
        for r in rows:
            text = (r.get("content_text") or "").strip()
            if text:
                parts.append(f"### {r['filename']}\n\n{text}")
        return "\n\n---\n\n".join(parts)
    except Exception:
        return ""


# ── Compatibility aliases (remove after v4.21 rollout confirmed) ──────────────
list_projects  = list_contexts
get_project    = get_context
create_project = create_context
			
# ── User / Tenant query functions ──────────────────────────────────────────

def list_users_by_domain(domain: str) -> list[dict]:
    """Return all users whose tenant matches the domain slug or display_name."""
    client = get_supabase_client()
    if client is None:
        return []
    try:
        # Busca o tenant pelo domain_slug
        tenant_res = (
            client.table("tenants")
            .select("id, domain_slug, display_name")
            .ilike("domain_slug", f"%{domain}%")
            .execute()
        )
        tenants = tenant_res.data or []

        # Se não achou pelo slug, tenta pelo display_name
        if not tenants:
            tenant_res = (
                client.table("tenants")
                .select("id, domain_slug, display_name")
                .ilike("display_name", f"%{domain}%")
                .execute()
            )
            tenants = tenant_res.data or []

        if not tenants:
            return []

        # Busca usuários de cada tenant encontrado
        all_users = []
        for t in tenants:
            res = (
                client.table("tenant_users")
                .select("id, login, display_name, role, tenant_id")
                .eq("tenant_id", t["id"])
                .order("display_name")
                .execute()
            )
            tenant_name = t.get("display_name") or t.get("domain_slug") or domain
            for u in (res.data or []):
                u["tenant_name"] = tenant_name
                all_users.append(u)

        return all_users
    except Exception:
        return []

def list_all_domains() -> list[dict]:
    """Return all tenants (domains) with user count."""
    client = get_supabase_client()
    if client is None:
        return []
    try:
        tenants_res = (
            client.table("tenants")
            .select("id, domain_slug, display_name")
            .order("display_name")
            .execute()
        )
        tenants = tenants_res.data or []
        if not tenants:
            return []

        result = []
        for t in tenants:
            try:
                users_res = (
                    client.table("tenant_users")
                    .select("id", count="exact")
                    .eq("tenant_id", t["id"])
                    .execute()
                )
                count = users_res.count or 0
            except Exception:
                count = 0
            result.append({
                "domain":       t.get("domain_slug") or t.get("display_name") or "—",
                "display_name": t.get("display_name") or t.get("domain_slug") or "—",
                "tenant_id":    t["id"],
                "user_count":   count,
            })
        return result
    except Exception:
        return []


def list_users_by_project(project_id: str | None = None) -> list[dict]:
    """Return users grouped by project via tenant linkage.

    Since there is no direct project→tenant FK yet, groups users by tenant
    and lists all projects of matching sigla/name as context.
    Falls back to listing all tenants with their users when project_id is None.
    """
    client = get_supabase_client()
    if client is None:
        return []
    try:
        # Get all tenants
        tenants_res = (
            client.table("tenants")
            .select("id, domain_slug, display_name")
            .order("display_name")
            .execute()
        )
        tenants = tenants_res.data or []

        # Get all contexts
        projects_res = (
            client.table("contexts")
            .select("id, name, sigla, description")
            .execute()
        )
        projects = projects_res.data or []

        result = []
        for t in tenants:
            tid = t["id"]
            tenant_label = t.get("display_name") or t.get("domain_slug") or tid

            users_res = (
                client.table("tenant_users")
                .select("id, login, display_name, role")
                .eq("tenant_id", tid)
                .order("display_name")
                .execute()
            )
            users = users_res.data or []

            # Try to match projects by sigla or name containing domain slug
            slug = (t.get("domain_slug") or "").lower()
            related_projects = [
                p for p in projects
                if slug and (
                    slug in (p.get("sigla") or "").lower()
                    or slug in (p.get("name") or "").lower()
                )
            ]

            entry = {
                "project_name": tenant_label,
                "tenant_id":    tid,
                "domain_slug":  t.get("domain_slug") or "",
                "user_count":   len(users),
                "users": [
                    {
                        "login": u.get("login", ""),
                        "nome":  u.get("display_name") or u.get("login", "?"),
                        "role":  u.get("role", "user"),
                    }
                    for u in users
                ],
                "related_projects": [p.get("name") for p in related_projects],
            }
            result.append(entry)

        return result
    except Exception:
        return []

# ── Reuniões ──────────────────────────────────────────────────────────────────

def list_meetings(project_id: str) -> list[dict]:
    """Retorna as reuniões de um projeto, ordenadas por número."""
    db = _db()
    if not db:
        return []
    try:
        return _ok(
            db.table("meetings")
            .select(
                "id, title, meeting_date, meeting_number, created_at, "
                "llm_provider, total_tokens, minutes_md, "
                "transcript_raw, transcript_clean"
            )
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


def update_meeting_title(meeting_id: str, new_title: str) -> bool:
    """Atualiza o título de uma reunião pelo seu ID."""
    db = _db()
    if not db:
        return False
    try:
        db.table("meetings").update({"title": new_title.strip()}).eq("id", meeting_id).execute()
        return True
    except Exception:
        return False


def save_transcript(meeting_id: str, hub) -> bool:
    """Persiste apenas as transcrições da reunião — chamada leve e isolada.

    Estratégia de economia de espaço (desejável):
    - Prefere ``transcript_clean`` (já sem fillers/artefatos ASR, ~30-50 % menor).
    - Armazena ``transcript_raw`` apenas se for diferente do clean E tiver ≤ 100 000 chars;
      caso contrário omite o raw (o clean já é suficiente para re-processar).
    - Nunca trunca o clean — ele é a fonte primária para re-processamento.
    """
    db = _db()
    if not db:
        return False
    try:
        raw   = getattr(hub, "transcript_raw",   None) or ""
        clean = getattr(hub, "transcript_clean", None) or ""

        payload: dict[str, Any] = {}
        if clean:
            payload["transcript_clean"] = clean
            # raw só vale a pena armazenar se acrescentar informação
            if raw and raw != clean and len(raw) <= 100_000:
                payload["transcript_raw"] = raw
        elif raw:
            # sem clean: guarda raw (truncado se necessário)
            payload["transcript_raw"] = raw[:100_000]

        if not payload:
            return False

        db.table("meetings").update(payload).eq("id", meeting_id).execute()
        return True
    except Exception:
        return False


def save_transcript_text(meeting_id: str, text: str) -> bool:
    """Salva texto de transcrição diretamente (sem KnowledgeHub).

    Usado pelo Transcript Backfill para reuniões cujo transcript_clean é NULL.
    Salva como transcript_clean (sempre) e transcript_raw somente se ≤ 100 000 chars.
    """
    db = _db()
    if not db or not text or not text.strip():
        return False
    try:
        payload: dict[str, Any] = {"transcript_clean": text}
        if len(text) <= 100_000:
            payload["transcript_raw"] = text
        db.table("meetings").update(payload).eq("id", meeting_id).execute()
        return True
    except Exception:
        return False


def list_meetings_without_transcript(project_id: str) -> list[dict]:
    """Retorna reuniões do projeto que não têm transcrição armazenada."""
    db = _db()
    if not db:
        return []
    try:
        rows = _ok(
            db.table("meetings")
            .select("id, meeting_number, title, meeting_date")
            .eq("project_id", project_id)
            .is_("transcript_clean", "null")
            .order("meeting_number")
            .execute()
        )
        return rows
    except Exception:
        return []


def save_meeting_artifacts(meeting_id: str, hub) -> bool:
    """Persiste os artefatos gerados pelo pipeline na reunião.

    Divide o save em três chamadas independentes para evitar estouro do limite
    de payload do PostgREST (~512 KB):
      1. Metadados leves + BPMN + Mermaid + Ata  (nunca falha por tamanho)
      2. Relatório HTML executivo                 (grande; falha isolada)
    As transcrições NÃO são salvas aqui — use save_transcript() separadamente.
    """
    db = _db()
    if not db:
        return False

    # ── Chamada 1: metadados + artefatos leves ────────────────────────────────
    try:
        payload1: dict[str, Any] = {
            "llm_provider": getattr(hub.meta, "llm_provider", None) if hasattr(hub, "meta") else None,
            "total_tokens": getattr(hub.meta, "total_tokens_used", 0) if hasattr(hub, "meta") else 0,
        }
        if hasattr(hub, "bpmn") and hub.bpmn.ready:
            payload1["bpmn_xml"]     = hub.bpmn.bpmn_xml
            payload1["mermaid_code"] = hub.bpmn.mermaid
        if hasattr(hub, "minutes") and hub.minutes.ready:
            payload1["minutes_md"] = hub.minutes.minutes_md or ""
            import json as _json
            _m = hub.minutes
            for _field in ("assumptions", "open_questions", "risks_identified", "dependencies", "stakeholder_needs"):
                _val = getattr(_m, _field, None)
                if _val:
                    payload1[_field] = _json.dumps(_val, ensure_ascii=False)
        if hasattr(hub, "bmm") and hub.bmm.ready:
            import json, dataclasses
            try:
                payload1["bmm_json"] = json.dumps(dataclasses.asdict(hub.bmm))
            except Exception:
                pass
        if hasattr(hub, "dmn") and hub.dmn.ready:
            import json as _json_dmn, dataclasses as _dc_dmn
            try:
                payload1["dmn_json"] = _json_dmn.dumps(_dc_dmn.asdict(hub.dmn))
            except Exception:
                pass
        if hasattr(hub, "argumentation") and hub.argumentation.ready:
            import json as _json_arg, dataclasses as _dc_arg
            try:
                payload1["argumentation_json"] = _json_arg.dumps(_dc_arg.asdict(hub.argumentation))
            except Exception:
                pass
        if hasattr(hub, "meeting_time") and hub.meeting_time.ready:
            import json as _json2
            _mt = hub.meeting_time
            if _mt.duration_minutes is not None:
                payload1["duration_minutes"] = _mt.duration_minutes
            if _mt.speaker_times:
                payload1["speaker_times"] = _json2.dumps(_mt.speaker_times, ensure_ascii=False)
        db.table("meetings").update(payload1).eq("id", meeting_id).execute()
    except Exception:
        return False

    # ── Chamada 2: relatório HTML (pesado — falha não bloqueia) ───────────────
    if hasattr(hub, "synthesizer") and hub.synthesizer.ready:
        try:
            db.table("meetings").update(
                {"report_html": hub.synthesizer.html}
            ).eq("id", meeting_id).execute()
        except Exception:
            pass   # HTML indisponível mas o restante foi salvo

    return True


def load_meeting_as_hub(meeting_id: str, project_id: str):
    """Reconstrói um KnowledgeHub a partir dos artefatos salvos de uma reunião.

    Popula os campos disponíveis no banco — transcript, minutes (markdown),
    BPMN XML + Mermaid, requirements, SBVR, BMM, DMN, Argumentation,
    synthesizer HTML.
    Campos que não são persistidos (quality scores, NLP) ficam vazios.

    Retorna None se a reunião não for encontrada ou Supabase não estiver
    configurado.
    """
    from core.knowledge_hub import (
        KnowledgeHub, MinutesModel, RequirementsModel, RequirementItem,
        BPMNModel, SBVRModel, BusinessTerm, BusinessRule,
        # NEW
        DMNModel, DMNDecision, DMNInput, DMNOutput, DMNRule,
        ArgumentationMap, IBISQuestion, IBISAlternative, IBISResolution,
    )
    db = _db()
    if not db:
        return None

    # ── 1. Reunião base ───────────────────────────────────────────────────────
    rows = _ok(
        db.table("meetings")
        .select(
            "id, title, meeting_date, meeting_number, "
            "transcript_clean, transcript_raw, minutes_md, "
            "bpmn_xml, mermaid_code, report_html, bmm_json, "
            "dmn_json, argumentation_json, "          # NEW
            "total_tokens, llm_provider"
        )
        .eq("id", meeting_id)
        .limit(1)
        .execute()
    )
    if not rows:
        return None
    m = rows[0]

    hub = KnowledgeHub.new()
    hub.loaded_from_db = True

    # ── Transcrição ───────────────────────────────────────────────────────────
    hub.transcript_raw   = (m.get("transcript_raw")   or "").strip()
    hub.transcript_clean = (m.get("transcript_clean") or "").strip() or hub.transcript_raw

    # ── Metadados ─────────────────────────────────────────────────────────────
    hub.meta.llm_provider      = m.get("llm_provider") or ""
    hub.meta.total_tokens_used = m.get("total_tokens") or 0

    # ── Ata (minutes) ─────────────────────────────────────────────────────────
    minutes_md_text = (m.get("minutes_md") or "").strip()
    if minutes_md_text:
        hub.minutes.minutes_md = minutes_md_text
        hub.minutes.title      = m.get("title") or ""
        hub.minutes.date       = str(m.get("meeting_date") or "")
        hub.minutes.ready      = True

    # ── BPMN — prefere bpmn_versions (mais recente), fallback meetings.bpmn_xml ─
    bpmn_xml     = ""
    mermaid_code = ""
    proc_name    = ""
    try:
        bv_rows = _ok(
            db.table("bpmn_versions")
            .select("bpmn_xml, mermaid_code, bpmn_processes(name)")
            .eq("meeting_id", meeting_id)
            .eq("is_current", True)
            .limit(1)
            .execute()
        )
        if not bv_rows:
            bv_rows = _ok(
                db.table("bpmn_versions")
                .select("bpmn_xml, mermaid_code, bpmn_processes(name)")
                .eq("meeting_id", meeting_id)
                .order("version", desc=True)
                .limit(1)
                .execute()
            )
        if bv_rows:
            bpmn_xml     = (bv_rows[0].get("bpmn_xml")     or "").strip()
            mermaid_code = (bv_rows[0].get("mermaid_code") or "").strip()
            proc_name    = ((bv_rows[0].get("bpmn_processes") or {}).get("name") or "").strip()
    except Exception:
        pass

    if not bpmn_xml:
        bpmn_xml     = (m.get("bpmn_xml")     or "").strip()
        mermaid_code = (m.get("mermaid_code") or "").strip()

    if bpmn_xml:
        hub.bpmn.bpmn_xml = bpmn_xml
        hub.bpmn.mermaid  = mermaid_code
        hub.bpmn.name     = proc_name or (m.get("title") or "")
        hub.bpmn.ready    = True

    # ── Requisitos ────────────────────────────────────────────────────────────
    try:
        req_rows = _ok(
            db.table("requirements")
            .select("req_number, title, description, req_type, priority, status, cited_by, source_quote, actor, process_step")
            .eq("project_id", project_id)
            .or_(f"first_meeting_id.eq.{meeting_id},last_meeting_id.eq.{meeting_id}")
            .order("req_number")
            .execute()
        )
        if req_rows:
            hub.requirements.requirements = [
                RequirementItem(
                    id=f"REQ-{r.get('req_number', i + 1):03d}",
                    title=r.get("title") or "",
                    description=r.get("description") or "",
                    type=r.get("req_type") or "functional",
                    priority=r.get("priority") or "unspecified",
                    status=r.get("status") or "active",
                    source_quote=r.get("source_quote") or "",
                    speaker=r.get("cited_by") or None,
                    actor=r.get("actor") or None,
                    process_step=r.get("process_step") or None,
                )
                for i, r in enumerate(req_rows)
            ]
            hub.requirements.name          = m.get("title") or ""
            hub.requirements.session_title = m.get("title") or ""
            hub.requirements.ready         = True
    except Exception:
        pass

    # ── SBVR ──────────────────────────────────────────────────────────────────
    try:
        term_rows = _ok(
            db.table("sbvr_terms")
            .select("term, definition, category")
            .eq("meeting_id", meeting_id)
            .execute()
        )
        rule_rows = _ok(
            db.table("sbvr_rules")
            .select("rule_id, statement, nucleo_nominal, rule_type, source")
            .eq("meeting_id", meeting_id)
            .execute()
        )
        if term_rows or rule_rows:
            hub.sbvr.vocabulary = [
                BusinessTerm(
                    term=t.get("term", ""),
                    definition=t.get("definition", ""),
                    category=t.get("category", "concept"),
                )
                for t in term_rows
            ]
            hub.sbvr.rules = [
                BusinessRule(
                    id=r.get("rule_id", ""),
                    statement=r.get("statement", ""),
                    short_title=r.get("nucleo_nominal", ""),
                    rule_type=r.get("rule_type", "constraint"),
                    source=r.get("source", ""),
                )
                for r in rule_rows
            ]
            hub.sbvr.ready = True
    except Exception:
        pass

    # ── BMM ───────────────────────────────────────────────────────────────────
    bmm_raw = (m.get("bmm_json") or "").strip()
    if bmm_raw:
        try:
            import json as _json
            from core.knowledge_hub import BMMGoal, BMMStrategy, BMMPolicy, BMMModel
            bmm_data = _json.loads(bmm_raw)
            hub.bmm.vision     = bmm_data.get("vision", "")
            hub.bmm.mission    = bmm_data.get("mission", "")
            hub.bmm.goals      = [BMMGoal(**g)      for g in bmm_data.get("goals", [])]
            hub.bmm.strategies = [BMMStrategy(**s)  for s in bmm_data.get("strategies", [])]
            hub.bmm.policies   = [BMMPolicy(**p)    for p in bmm_data.get("policies", [])]
            hub.bmm.ready      = True
        except Exception:
            pass

    # NEW ── DMN ───────────────────────────────────────────────────────────────
    dmn_raw = (m.get("dmn_json") or "").strip()
    if dmn_raw:
        try:
            import json as _json
            dmn_data = _json.loads(dmn_raw)
            decisions = []
            for d in dmn_data.get("decisions", []):
                decisions.append(DMNDecision(
                    id=d.get("id", ""),
                    name=d.get("name", ""),
                    question=d.get("question", ""),
                    rationale=d.get("rationale", ""),
                    decided_by=d.get("decided_by", []),
                    inputs=[DMNInput(**i) for i in d.get("inputs", [])],
                    outputs=[DMNOutput(**o) for o in d.get("outputs", [])],
                    rules=[DMNRule(**r) for r in d.get("rules", [])],
                    hit_policy=d.get("hit_policy", "U"),
                    confidence=d.get("confidence", 1.0),
                ))
            hub.dmn.decisions = decisions
            hub.dmn.ready     = True
        except Exception:
            pass

    # NEW ── Argumentation / IBIS ──────────────────────────────────────────────
    arg_raw = (m.get("argumentation_json") or "").strip()
    if arg_raw:
        try:
            import json as _json
            arg_data = _json.loads(arg_raw)
            questions = []
            for q in arg_data.get("questions", []):
                alternatives = [
                    IBISAlternative(
                        id=a.get("id", ""),
                        description=a.get("description", ""),
                        proposed_by=a.get("proposed_by", ""),
                        pros=a.get("pros", []),
                        cons=a.get("cons", []),
                        supported_by=a.get("supported_by", []),
                        opposed_by=a.get("opposed_by", []),
                        was_chosen=a.get("was_chosen", False),
                    )
                    for a in q.get("alternatives", [])
                ]
                res_data = q.get("resolution", {})
                resolution = IBISResolution(
                    type=res_data.get("type", "unresolved"),
                    chosen_alternative_id=res_data.get("chosen_alternative_id", ""),
                    rationale=res_data.get("rationale", ""),
                    with_caveats=res_data.get("with_caveats", []),
                )
                questions.append(IBISQuestion(
                    id=q.get("id", ""),
                    statement=q.get("statement", ""),
                    raised_by=q.get("raised_by", ""),
                    alternatives=alternatives,
                    resolution=resolution,
                ))
            hub.argumentation.questions = questions
            hub.argumentation.ready     = True
        except Exception:
            pass

    # ── Relatório HTML ────────────────────────────────────────────────────────
    report_html = (m.get("report_html") or "").strip()
    if report_html:
        hub.synthesizer.html  = report_html
        hub.synthesizer.ready = True

    hub.bump()
    return hub


# ── Requisitos ────────────────────────────────────────────────────────────────

def next_req_number(project_id: str) -> int:
    """Retorna o próximo número disponível para REQ- no projeto."""
    db = _db()
    if not db:
        return 1
    try:
        data = db.rpc("next_req_number", {"p_project_id": project_id}).execute().data
        # PostgREST returns a scalar int for RETURNS INTEGER functions;
        # some client versions may wrap it in a list — handle both.
        if isinstance(data, int):
            return data
        if isinstance(data, list) and data:
            return data[0] if isinstance(data[0], int) else 1
        return 1
    except Exception:
        return 1


def save_new_requirement(
    project_id: str,
    meeting_id,           # str | None — None when origin='documento'
    req_number: int,
    title: str,
    description: str,
    req_type: str = "",
    priority: str = "",
    source_quote: str = "",
    cited_by: str = "",
    actor: str = "",
    process_step: str = "",
    origin: str = "transcricao",
    doc_ref=None,         # str | None — UUID of meeting_document
) -> dict | None:
    """Insere um requisito novo (primeira aparição) e sua versão inicial.

    source_quote — frase verbatim da transcrição que motivou o requisito.
    cited_by     — iniciais do participante que originou a afirmação (ex: "PG").

    Tenta salvar com os novos campos primeiro; se as colunas ainda não
    existirem na tabela (migration pendente), salva sem eles para não
    bloquear o pipeline.

    NOTA: NÃO usa _ok() internamente — deixa exceções propagarem para que
    o bloco de fallback possa capturá-las corretamente.
    """
    db = _db()
    if not db:
        return None

    base_req = {
        "project_id":  project_id,
        "req_number":  req_number,
        "title":       title,
        "description": description,
        "req_type":    req_type,
        "priority":    priority,
        "status":      "active",
    }
    if meeting_id:
        base_req["first_meeting_id"] = meeting_id
        base_req["last_meeting_id"]  = meeting_id

    base_ver = {
        "version":     1,
        "title":       title,
        "description": description,
        "req_type":    req_type,
        "priority":    priority,
        "change_type": "new",
    }
    if meeting_id:
        base_ver["meeting_id"] = meeting_id

    req_row: dict | None = None

    # ── Attempt 1: with traceability fields; Attempt 2: without (fallback) ────
    for use_new_fields in (True, False):
        req_payload = dict(base_req)
        if use_new_fields:
            req_payload["source_quote"] = source_quote or None
            req_payload["cited_by"]     = cited_by or None
            req_payload["actor"]        = actor or None
            req_payload["process_step"] = process_step or None
            req_payload["origin"]       = origin
            if doc_ref:
                req_payload["doc_ref"]  = doc_ref
        try:
            # Do NOT wrap in _ok() — let PostgREST errors raise so the except
            # below can trigger the fallback instead of silently returning None.
            result = db.table("requirements").insert(req_payload).execute()
            rows   = result.data or []
            if rows:
                req_row = rows[0]
                break   # inserted successfully
            # Empty data: shouldn't happen with Supabase, but try fallback
        except Exception:
            if not use_new_fields:
                return None  # both attempts failed
            # First attempt failed (likely missing columns) — try fallback
            continue

    if not req_row:
        return None

    # ── Insert the corresponding version record ────────────────────────────────
    for use_new_fields in (True, False):
        ver_payload = dict(base_ver)
        ver_payload["requirement_id"] = req_row["id"]
        if use_new_fields:
            ver_payload["source_quote"] = source_quote or None
            ver_payload["cited_by"]     = cited_by or None
            ver_payload["origin"]       = origin
            if doc_ref:
                ver_payload["doc_ref"]  = doc_ref
        try:
            db.table("requirement_versions").insert(ver_payload).execute()
            break   # version saved
        except Exception:
            if not use_new_fields:
                break  # version failed on both — requirement still saved; acceptable
            continue

    return req_row


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


def list_requirements_light(project_id: str) -> list[dict]:
    """Retorna requisitos sem histórico de versões — query leve para listagem.

    Ideal para painéis que só precisam de metadados (título, status, tipo, prioridade).
    Use list_requirement_versions(req_id) para carregar versões sob demanda.
    """
    db = _db()
    if not db:
        return []
    try:
        return _ok(
            db.table("requirements")
            .select(
                "id, req_number, title, description, req_type, priority, status, "
                "origin, doc_ref, first_meeting_id, last_meeting_id, "
                "owner, status_note, cited_by, source_quote, project_id"
            )
            .eq("project_id", project_id)
            .order("req_number")
            .execute()
        )
    except Exception:
        return []


def list_requirement_versions(requirement_id: str) -> list[dict]:
    """Retorna todas as versões de um requisito específico, ordenadas cronologicamente."""
    db = _db()
    if not db:
        return []
    try:
        return _ok(
            db.table("requirement_versions")
            .select("*")
            .eq("requirement_id", requirement_id)
            .order("version")
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
    source_quote: str = "",
    cited_by: str = "",
) -> bool:
    """Adiciona uma nova versão a um requisito existente.

    source_quote — frase verbatim da transcrição que motivou esta versão.
    cited_by     — iniciais do participante que originou a afirmação.

    Tenta salvar com os novos campos primeiro; se as colunas ainda não
    existirem na tabela (migration pendente), salva sem eles.
    """
    db = _db()
    if not db:
        return False

    base_payload = {
        "requirement_id":       requirement_id,
        "meeting_id":           meeting_id,
        "version":              version,
        "title":                title,
        "description":          description,
        "req_type":             req_type,
        "priority":             priority,
        "change_type":          change_type,
        "change_summary":       change_summary,
        "contradiction_flag":   contradiction_flag,
        "contradiction_detail": contradiction_detail,
    }

    for use_new_fields in (True, False):
        payload = dict(base_payload)
        if use_new_fields:
            payload["source_quote"] = source_quote or None
            payload["cited_by"]     = cited_by or None
        try:
            db.table("requirement_versions").insert(payload).execute()
            return True
        except Exception:
            if not use_new_fields:
                return False
            continue

    return False


def update_requirement(
    requirement_id: str,
    status: str | None = None,
    last_meeting_id: str | None = None,
    title: str | None = None,
    description: str | None = None,
    owner: str | None = None,
    status_note: str | None = None,
) -> bool:
    """Atualiza campos do registro mestre de um requisito.

    owner       — responsável pelo requisito (pessoa ou equipe).
    status_note — nota sobre a mudança de status atual.

    Tenta salvar com os novos campos; se as colunas ainda não existirem
    (migration pendente), salva apenas os campos legados.
    """
    db = _db()
    if not db:
        return False

    base_payload: dict[str, Any] = {"updated_at": "NOW()"}
    if status is not None:
        base_payload["status"] = status
    if last_meeting_id is not None:
        base_payload["last_meeting_id"] = last_meeting_id
    if title is not None:
        base_payload["title"] = title
    if description is not None:
        base_payload["description"] = description

    for use_new_fields in (True, False):
        payload = dict(base_payload)
        if use_new_fields:
            if owner is not None:
                payload["owner"] = owner
            if status_note is not None:
                payload["status_note"] = status_note
        try:
            db.table("requirements").update(payload).eq("id", requirement_id).execute()
            return True
        except Exception:
            if not use_new_fields:
                return False
            continue

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
            source_quote=getattr(item, "source_quote", "") or "",
            cited_by=getattr(item, "speaker", "") or "",
            actor=getattr(item, "actor", "") or "",
            process_step=getattr(item, "process_step", "") or "",
            origin=getattr(item, "origin", "transcricao"),
            doc_ref=getattr(item, "doc_ref", None),
        )
        if result:
            next_num += 1
            saved += 1

    return saved


# ── SBVR ──────────────────────────────────────────────────────────────────────

def save_sbvr_from_hub(meeting_id, project_id: str, hub) -> tuple[int, int]:
    """Persiste termos e regras SBVR do hub no Supabase.

    meeting_id — str | None (None quando origin='documento').
    Retorna (n_terms, n_rules) salvos.
    """
    db = _db()
    if not db:
        return 0, 0
    if not hasattr(hub, "sbvr") or not hub.sbvr.ready:
        return 0, 0

    n_terms = n_rules = 0

    for t in hub.sbvr.vocabulary:
        t_origin  = getattr(t, "origin", "transcricao")
        t_doc_ref = getattr(t, "doc_ref", None)
        base = {
            "project_id": project_id,
            "term":       t.term,
            "definition": t.definition,
            "category":   t.category,
        }
        if meeting_id:
            base["meeting_id"] = meeting_id
        for use_new_fields in (True, False):
            payload = dict(base)
            if use_new_fields:
                payload["origin"] = t_origin
                if t_doc_ref:
                    payload["doc_ref"] = t_doc_ref
            try:
                db.table("sbvr_terms").insert(payload).execute()
                n_terms += 1
                break
            except Exception:
                if not use_new_fields:
                    break
                continue

    for r in hub.sbvr.rules:
        r_origin  = getattr(r, "origin", "transcricao")
        r_doc_ref = getattr(r, "doc_ref", None)
        # nucleo_nominal: LLM short_title preferred; heuristic fallback
        nucleo = getattr(r, "short_title", "").strip() or rule_keyword_pt(r.statement)
        base = {
            "project_id":     project_id,
            "rule_id":        r.id,
            "statement":      r.statement,
            "nucleo_nominal": nucleo,
            "rule_type":      r.rule_type,
            "source":         r.source,
        }
        if meeting_id:
            base["meeting_id"] = meeting_id
        for use_new_fields in (True, False):
            payload = dict(base)
            if use_new_fields:
                payload["origin"] = r_origin
                if r_doc_ref:
                    payload["doc_ref"] = r_doc_ref
            try:
                db.table("sbvr_rules").insert(payload).execute()
                n_rules += 1
                break
            except Exception:
                if not use_new_fields:
                    break
                continue

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


# ── BPMN Processos e Versões ──────────────────────────────────────────────────

def bpmn_tables_exist() -> bool:
    """Verifica se as tabelas bpmn_processes e bpmn_versions existem no banco."""
    db = _db()
    if not db:
        return False
    try:
        db.table("bpmn_versions").select("id").limit(1).execute()
        db.table("bpmn_processes").select("id").limit(1).execute()
        return True
    except Exception:
        return False


def list_meetings_without_bpmn(project_id: str) -> list[dict]:
    """Retorna TODAS as reuniões do projeto que ainda não têm versão BPMN registrada.

    Inclui reuniões sem transcrição armazenada (transcript_raw / transcript_clean nulos)
    — o campo `has_transcript` é adicionado ao dict para que a UI possa informar
    o usuário sobre quais reuniões precisam de upload manual.

    Presume que as tabelas bpmn_versions e bpmn_processes já existem.
    Use bpmn_tables_exist() para verificar antes de chamar esta função.
    """
    db = _db()
    if not db:
        return []
    try:
        all_meetings = _ok(
            db.table("meetings")
            .select("id, title, meeting_date, meeting_number, transcript_raw, transcript_clean")
            .eq("project_id", project_id)
            .order("meeting_number")
            .execute()
        )
        try:
            bpmn_rows = _ok(
                db.table("bpmn_versions")
                .select("meeting_id")
                .eq("project_id", project_id)
                .execute()
            )
            covered = {r["meeting_id"] for r in bpmn_rows}
        except Exception:
            covered = set()   # tabela ainda não existe → trata todas como pendentes

        result = []
        for m in all_meetings:
            if m["id"] in covered:
                continue
            has_transcript = bool(m.get("transcript_clean") or m.get("transcript_raw"))
            m["has_transcript"] = has_transcript
            result.append(m)
        return result
    except Exception:
        return []


def list_bpmn_processes(project_id: str) -> list[dict]:
    """Retorna todos os processos BPMN do projeto ordenados por nome.

    Inclui numero e titulo da reuniao de origem via last_meeting_id -> meetings.
    """
    db = _db()
    if not db:
        return []
    try:
        return _ok(
            db.table("bpmn_processes")
            .select("*, meetings!last_meeting_id(meeting_number, title)")
            .eq("project_id", project_id)
            .order("name")
            .execute()
        )
    except Exception:
        try:
            return _ok(
                db.table("bpmn_processes")
                .select("*")
                .eq("project_id", project_id)
                .order("name")
                .execute()
            )
        except Exception:
            return []


def get_bpmn_process(process_id: str) -> dict | None:
    """Retorna um processo BPMN pelo ID."""
    db = _db()
    if not db:
        return None
    try:
        rows = _ok(
            db.table("bpmn_processes")
            .select("*")
            .eq("id", process_id)
            .limit(1)
            .execute()
        )
        return rows[0] if rows else None
    except Exception:
        return None


def _find_or_create_bpmn_process(
    project_id: str,
    process_name: str,
    first_meeting_id: str,
) -> dict | None:
    """Localiza um processo pelo slug ou cria um novo (Opção A — automático)."""
    from modules.text_utils import process_slug
    slug = process_slug(process_name)
    db = _db()
    if not db:
        return None
    try:
        rows = _ok(
            db.table("bpmn_processes")
            .select("*")
            .eq("project_id", project_id)
            .eq("slug", slug)
            .limit(1)
            .execute()
        )
        if rows:
            return rows[0]
        rows = _ok(
            db.table("bpmn_processes")
            .insert({
                "project_id":       project_id,
                "name":             process_name,
                "slug":             slug,
                "version_count":    0,
                "first_meeting_id": first_meeting_id,
                "last_meeting_id":  first_meeting_id,
            })
            .execute()
        )
        return rows[0] if rows else None
    except Exception:
        return None


def list_bpmn_versions(process_id: str) -> list[dict]:
    """Retorna todas as versões de um processo ordenadas da mais recente."""
    db = _db()
    if not db:
        return []
    try:
        return _ok(
            db.table("bpmn_versions")
            .select("*, meetings(title, meeting_date, meeting_number)")
            .eq("process_id", process_id)
            .order("version", desc=True)
            .execute()
        )
    except Exception:
        return []


def save_bpmn_from_hub(
    meeting_id: str,
    project_id: str,
    hub,
    bpmn_process_id: str | None = None,
    bpmn_process_override_name: str = "",
) -> str | None:
    """Persiste o BPMN do hub como nova versão de um processo.

    Estratégia de resolução do processo destino:
      1. ``bpmn_process_id`` fornecido → usa o processo existente (Opção B).
      2. ``bpmn_process_override_name`` fornecido → cria processo com esse nome.
      3. Nenhum → slug normalizado de ``hub.bpmn.name`` (Opção A automática).

    Retorna o ``process_id`` salvo, ou ``None`` em caso de erro / BPMN ausente.
    """
    if not hasattr(hub, "bpmn") or not hub.bpmn.ready:
        return None

    db = _db()
    if not db:
        return None

    process_name = hub.bpmn.name or "Processo"

    # Resolve processo destino
    if bpmn_process_id:
        process = get_bpmn_process(bpmn_process_id)
    elif bpmn_process_override_name.strip():
        process = _find_or_create_bpmn_process(
            project_id, bpmn_process_override_name.strip(), meeting_id
        )
    else:
        process = _find_or_create_bpmn_process(project_id, process_name, meeting_id)

    if not process:
        return None

    pid = process["id"]
    version = (process.get("version_count") or 0) + 1

    try:
        # Desmarca versão atual anterior
        db.table("bpmn_versions").update({"is_current": False}).eq("process_id", pid).execute()

        # Insere nova versão
        db.table("bpmn_versions").insert({
            "process_id":    pid,
            "meeting_id":    meeting_id,
            "project_id":    project_id,
            "version":       version,
            "bpmn_xml":      getattr(hub.bpmn, "bpmn_xml", "") or "",
            "mermaid_code":  getattr(hub.bpmn, "mermaid", "") or "",
            "is_current":    True,
        }).execute()

        # Atualiza metadados do processo
        db.table("bpmn_processes").update({
            "version_count":   version,
            "last_meeting_id": meeting_id,
            "updated_at":      "NOW()",
        }).eq("id", pid).execute()

        return pid
    except Exception:
        return None


def save_bpmn_new_version(
    process_id: str,
    meeting_id: str,
    project_id: str,
    bpmn_xml: str,
    mermaid_code: str = "",
    version_notes: str = "",
    created_by: str = "",
) -> bool:
    """Salva o XML editado manualmente como nova versão de um processo BPMN.

    Desmarca ``is_current`` em todas as versões anteriores do processo e
    insere uma nova versão com ``is_current=True``.  Atualiza ``version_count``
    e ``updated_at`` no registro de ``bpmn_processes``.

    Retorna ``True`` em caso de sucesso, ``False`` em caso de erro.
    """
    if not bpmn_xml or not bpmn_xml.strip():
        return False

    db = _db()
    if not db:
        return False

    try:
        proc = get_bpmn_process(process_id)
        if not proc:
            return False

        version = (proc.get("version_count") or 0) + 1

        # Desmarca versão atual
        db.table("bpmn_versions").update({"is_current": False}).eq("process_id", process_id).execute()

        # Insere nova versão
        change_note_text = version_notes.strip() if version_notes else ""
        if created_by:
            change_note_text = f"[{created_by.strip()}] {change_note_text}".strip()

        payload: dict = {
            "process_id":   process_id,
            "meeting_id":   meeting_id,
            "project_id":   project_id,
            "version":      version,
            "bpmn_xml":     bpmn_xml.strip(),
            "mermaid_code": mermaid_code or "",
            "is_current":   True,
        }
        if change_note_text:
            payload["change_notes"] = change_note_text

        try:
            db.table("bpmn_versions").insert(payload).execute()
        except Exception:
            # Retry without optional columns that may not exist yet
            payload.pop("change_notes", None)
            db.table("bpmn_versions").insert(payload).execute()

        # Atualiza metadados do processo
        db.table("bpmn_processes").update({
            "version_count":   version,
            "last_meeting_id": meeting_id,
        }).eq("id", process_id).execute()

        return True
    except Exception:
        return False


def get_bpmn_version(version_id: str) -> dict | None:
    """Retorna uma versão BPMN pelo ID."""
    db = _db()
    if not db:
        return None
    try:
        rows = _ok(
            db.table("bpmn_versions")
            .select("*, bpmn_processes(name, project_id), meetings(title, meeting_number)")
            .eq("id", version_id)
            .limit(1)
            .execute()
        )
        return rows[0] if rows else None
    except Exception:
        return None


def delete_bpmn_version(version_id: str) -> dict:
    """
    Exclui uma versão BPMN pelo ID.

    Regras de segurança:
    - Recusa se for a única versão do processo (evita processo órfão).
    - Se for is_current=True, promove a versão mais recente restante como atual.
    - Atualiza version_count em bpmn_processes.

    Retorna dict com: ok (bool), message (str).
    """
    db = _db()
    if not db:
        return {"ok": False, "message": "Banco de dados não disponível."}
    try:
        version = get_bpmn_version(version_id)
        if not version:
            return {"ok": False, "message": f"Versão '{version_id}' não encontrada."}

        process_id  = version["process_id"]
        is_current  = version.get("is_current", False)
        ver_num     = version.get("version", "?")

        all_versions = list_bpmn_versions(process_id)
        if len(all_versions) <= 1:
            return {
                "ok": False,
                "message": (
                    "Não é possível excluir a única versão de um processo. "
                    "Delete o processo inteiro se necessário."
                ),
            }

        # Se for a versão atual, promove a próxima mais recente
        promoted_ver: dict | None = None
        if is_current:
            promoted_ver = next(
                (v for v in all_versions if v["id"] != version_id), None
            )
            if promoted_ver:
                db.table("bpmn_versions").update({"is_current": True}).eq(
                    "id", promoted_ver["id"]
                ).execute()

        db.table("bpmn_versions").delete().eq("id", version_id).execute()

        remaining = len(all_versions) - 1
        db.table("bpmn_processes").update({"version_count": remaining}).eq(
            "id", process_id
        ).execute()

        proc      = get_bpmn_process(process_id)
        proc_name = (proc or {}).get("name", process_id)

        msg = f"Versão v{ver_num} do processo '{proc_name}' excluída."
        if is_current and promoted_ver:
            msg += f" Versão v{promoted_ver.get('version', '?')} promovida como atual."

        return {"ok": True, "message": msg}
    except Exception as exc:
        return {"ok": False, "message": f"Erro ao excluir versão: {exc}"}


# ── RAG context retrieval ─────────────────────────────────────────────────────

_PT_STOPWORDS = {
    "o", "a", "os", "as", "e", "de", "do", "da", "dos", "das", "em", "no",
    "na", "nos", "nas", "para", "com", "que", "não", "se", "por", "mais",
    "mas", "foi", "foram", "ser", "estar", "está", "estão", "um", "uma",
    "como", "ao", "aos", "ou", "já", "também", "este", "esta", "esse",
    "essa", "isso", "qual", "quais", "quando", "onde", "quem", "sobre",
    "reunião", "reuniões", "teve", "tiveram", "pode", "podem", "seria",
    "fazer", "feito", "dever", "deve", "devem", "tinha", "tinham",
    "ter", "tem", "têm", "temos", "tenho", "há", "haver", "houve",
    "seu", "sua", "seus", "suas", "meu", "minha", "meus", "minhas",
    "nosso", "nossa", "nossos", "nossas", "pelo", "pela", "pelos", "pelas",
    "num", "numa", "nuns", "numas", "dum", "duma", "duns", "dumas",
    "me", "te", "lhe", "nos", "vos", "lhes", "ele", "ela", "eles", "elas",
    "eu", "tu", "nós", "vós", "você", "vocês", "muito", "muita", "muitos",
    "muitas", "todo", "toda", "todos", "todas", "algum", "alguma", "alguns",
    "algumas", "nenhum", "nenhuma", "cada", "qualquer", "quaisquer",
}


def _extract_minutes_summary(minutes_md: str, max_chars: int = 700) -> str:
    """
    Extract a compact summary from a minutes markdown document.

    Always includes the 'Participantes' section (critical metadata).
    Adds 'Decisões' if space allows.
    Strips the running summary body to keep context compact.

    Returns a plain-text string suitable for injection into the LLM context.
    """
    import re
    if not minutes_md or not minutes_md.strip():
        return ""

    lines: list[str] = []

    # Extract Participantes section (##  Participantes or ## Participantes)
    m_part = re.search(
        r'##\s*Participantes\s*\n([\s\S]*?)(?=\n##|\Z)',
        minutes_md,
        re.IGNORECASE,
    )
    if m_part:
        participants_text = m_part.group(1).strip()
        lines.append("Participantes:")
        lines.append(participants_text)

    # Extract Pauta / Agenda section (compact)
    m_pauta = re.search(
        r'##\s*Pauta\s*\n([\s\S]*?)(?=\n##|\Z)',
        minutes_md,
        re.IGNORECASE,
    )
    if m_pauta:
        pauta_text = m_pauta.group(1).strip()
        lines.append("Pauta:")
        lines.append(pauta_text)

    # Extract Decisões section
    m_dec = re.search(
        r'##\s*Decis[õo]es\s*\n([\s\S]*?)(?=\n##|\Z)',
        minutes_md,
        re.IGNORECASE,
    )
    if m_dec:
        dec_text = m_dec.group(1).strip()
        lines.append("Decisões:")
        lines.append(dec_text)

    result = "\n".join(lines)
    if len(result) > max_chars:
        result = result[:max_chars] + "…"
    return result


def _extract_keywords(question: str) -> list[str]:
    """
    Split question into lowercase word tokens, remove Portuguese stopwords,
    and keep only tokens with length > 2.
    """
    import re
    tokens = re.findall(r'\w+', question.lower())
    return [t for t in tokens if len(t) > 2 and t not in _PT_STOPWORDS]


def _extract_passages(
    transcript: str,
    keywords: list[str],
    context_lines: int = 4,
    max_passages: int = 6,
) -> list[str]:
    """
    Find lines in the transcript that contain any of the keywords and return
    surrounding passages (context_lines before and after each match).

    Consecutive matching regions (gap <= 2 lines) are merged into a single passage.
    Returns up to max_passages passages as strings.
    """
    if not keywords or not transcript:
        return []

    lines = [ln for ln in transcript.splitlines() if ln.strip()]
    if not lines:
        return []

    # Find indices of lines containing any keyword
    matching_indices: set[int] = set()
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(kw in line_lower for kw in keywords):
            matching_indices.add(i)

    if not matching_indices:
        return []

    # Expand each match with context
    expanded: set[int] = set()
    for idx in matching_indices:
        for offset in range(-context_lines, context_lines + 1):
            neighbor = idx + offset
            if 0 <= neighbor < len(lines):
                expanded.add(neighbor)

    # Sort and group into consecutive runs (gap <= 2)
    sorted_indices = sorted(expanded)
    groups: list[list[int]] = []
    current_group: list[int] = [sorted_indices[0]]
    for idx in sorted_indices[1:]:
        if idx - current_group[-1] <= 2:
            current_group.append(idx)
        else:
            groups.append(current_group)
            current_group = [idx]
    groups.append(current_group)

    # Build passage strings, limited to max_passages
    passages = []
    for group in groups[:max_passages]:
        passage_lines = [lines[i] for i in group]
        passages.append("\n".join(passage_lines))

    return passages


def retrieve_context_for_question(project_id: str, question: str) -> dict:
    """
    Retrieve relevant context from Supabase for a RAG-based question.

    Returns a dict with:
      - meetings_passages: list of {meeting_number, title, meeting_date, passages}
      - requirements: list of {req_number, title, description, req_type, status}
      - processes: list of {name, version_count}
      - sbvr_terms: list of {term, definition}
      - sbvr_rules: list of {rule_id, statement, nucleo_nominal}
      - meetings_without_transcript: list of titles with no stored transcript
    """
    db = _db()
    keywords = _extract_keywords(question)

    result: dict = {
        "meetings_passages": [],
        "requirements": [],
        "processes": [],
        "sbvr_terms": [],
        "sbvr_rules": [],
        "meetings_without_transcript": [],
        "data_summary": retrieve_data_summary(project_id),
    }

    # ── Meetings + transcripts ─────────────────────────────────────────────────
    if db:
        try:
            meeting_rows = _ok(
                db.table("meetings")
                .select("id, title, meeting_date, meeting_number, transcript_clean, transcript_raw, minutes_md")
                .eq("project_id", project_id)
                .order("meeting_number")
                .execute()
            )
        except Exception:
            meeting_rows = []

        for m in meeting_rows:
            transcript = m.get("transcript_clean") or m.get("transcript_raw") or ""
            title = m.get("title") or ""
            meeting_date = str(m.get("meeting_date") or "")
            meeting_number = m.get("meeting_number") or 0
            minutes_summary = _extract_minutes_summary(m.get("minutes_md") or "")

            if not transcript:
                result["meetings_without_transcript"].append(title)
                # Still include minutes summary even without transcript
                if minutes_summary:
                    result["meetings_passages"].append({
                        "meeting_number": meeting_number,
                        "title": title,
                        "meeting_date": meeting_date,
                        "passages": [],
                        "minutes_summary": minutes_summary,
                    })
                continue

            if keywords:
                passages = _extract_passages(transcript, keywords)
            else:
                # No keywords — return first passage as overview
                passages = _extract_passages(transcript, [], context_lines=0, max_passages=0)

            if passages or minutes_summary:
                result["meetings_passages"].append({
                    "meeting_number": meeting_number,
                    "title": title,
                    "meeting_date": meeting_date,
                    "passages": passages,
                    "minutes_summary": minutes_summary,
                })

    # ── Requirements ──────────────────────────────────────────────────────────
    if db and keywords:
        try:
            all_reqs = _ok(
                db.table("requirements")
                .select("req_number, title, description, req_type, status")
                .eq("project_id", project_id)
                .order("req_number")
                .execute()
            )
            for req in all_reqs:
                title = (req.get("title") or "").lower()
                description = (req.get("description") or "").lower()
                combined = title + " " + description
                if any(kw in combined for kw in keywords):
                    result["requirements"].append({
                        "req_number": req.get("req_number"),
                        "title": req.get("title") or "",
                        "description": req.get("description") or "",
                        "req_type": req.get("req_type") or "",
                        "status": req.get("status") or "",
                    })
        except Exception:
            pass

    # ── BPMN processes ────────────────────────────────────────────────────────
    if db:
        try:
            proc_rows = _ok(
                db.table("bpmn_processes")
                .select("name, version_count")
                .eq("project_id", project_id)
                .order("name")
                .execute()
            )
            for p in proc_rows:
                result["processes"].append({
                    "name": p.get("name") or "",
                    "version_count": p.get("version_count") or 0,
                })
        except Exception:
            pass

    # ── SBVR terms ────────────────────────────────────────────────────────────
    if db and keywords:
        try:
            all_terms = _ok(
                db.table("sbvr_terms")
                .select("term, definition")
                .eq("project_id", project_id)
                .execute()
            )
            for t in all_terms:
                term = (t.get("term") or "").lower()
                definition = (t.get("definition") or "").lower()
                combined = term + " " + definition
                if any(kw in combined for kw in keywords):
                    result["sbvr_terms"].append({
                        "term": t.get("term") or "",
                        "definition": t.get("definition") or "",
                    })
        except Exception:
            pass

    # ── SBVR rules ────────────────────────────────────────────────────────────
    if db and keywords:
        try:
            all_rules = _ok(
                db.table("sbvr_rules")
                .select("rule_id, statement, nucleo_nominal")
                .eq("project_id", project_id)
                .execute()
            )
            for r in all_rules:
                statement = (r.get("statement") or "").lower()
                nucleo = (r.get("nucleo_nominal") or "").lower()
                combined = statement + " " + nucleo
                if any(kw in combined for kw in keywords):
                    result["sbvr_rules"].append({
                        "rule_id": r.get("rule_id") or "",
                        "statement": r.get("statement") or "",
                        "nucleo_nominal": r.get("nucleo_nominal") or "",
                    })
        except Exception:
            pass

    return result


def format_context(ctx: dict, project_name: str) -> str:
    """
    Format a context dict (from retrieve_context_for_question) into a readable
    string suitable for injection into the LLM system prompt.
    """
    lines: list[str] = []

    lines.append(f"═══ PROJETO: {project_name} ═══")
    lines.append("")

    # ── Data summary (sempre presente) ────────────────────────────────────────
    ds = ctx.get("data_summary") or {}
    if ds:
        lines.append("── RESUMO DOS DADOS DO PROJETO ──")

        # Reuniões
        meetings_list = ds.get("meetings") or []
        lines.append(f"Total de reuniões: {len(meetings_list)}")
        for m in meetings_list:
            transcript_flag = "✓ transcrição" if m.get("has_transcript") else "✗ sem transcrição"
            lines.append(
                f"  • Reunião {m.get('number','?')} — {m.get('title')} ({m.get('date')}) [{transcript_flag}]"
            )

        # Requisitos
        req_total = ds.get("req_total", 0)
        lines.append(f"Total de requisitos: {req_total}")
        by_type = ds.get("req_by_type") or {}
        if by_type:
            lines.append("  Por tipo: " + ", ".join(f"{k}={v}" for k, v in sorted(by_type.items())))
        by_status = ds.get("req_by_status") or {}
        if by_status:
            lines.append("  Por status: " + ", ".join(f"{k}={v}" for k, v in sorted(by_status.items())))
        by_priority = ds.get("req_by_priority") or {}
        if by_priority:
            lines.append("  Por prioridade: " + ", ".join(f"{k}={v}" for k, v in sorted(by_priority.items())))

        # SBVR
        n_terms = ds.get("n_sbvr_terms", 0)
        n_rules = ds.get("n_sbvr_rules", 0)
        lines.append(f"SBVR: {n_terms} termo(s) de domínio, {n_rules} regra(s) de negócio")

        # BPMN
        bpmn_procs = ds.get("bpmn_processes") or []
        n_versions = ds.get("n_bpmn_versions", 0)
        lines.append(f"Processos BPMN: {len(bpmn_procs)} processo(s), {n_versions} versão(ões) total")
        for p in bpmn_procs:
            lines.append(f"  • {p['name']} — {p['version_count']} versão(ões) [{p['status']}]")

        # Busca semântica
        n_chunks = ds.get("n_chunks_indexed", 0)
        if n_chunks:
            lines.append(f"Embeddings indexados: {n_chunks} chunks")

        lines.append("")

    # ── Minutes summaries (always injected — participants, decisions, agenda) ──
    meetings_passages = ctx.get("meetings_passages") or []
    minutes_sections = [mp for mp in meetings_passages if mp.get("minutes_summary")]
    if minutes_sections:
        lines.append("── ATAS DAS REUNIÕES (PARTICIPANTES, PAUTA E DECISÕES) ──")
        lines.append("")
        for mp in minutes_sections:
            n = mp.get("meeting_number", "?")
            title = mp.get("title", "")
            date = mp.get("meeting_date", "")
            date_str = f" ({date})" if date else ""
            lines.append(f"[Reunião {n} — {title}{date_str}]")
            lines.append(mp["minutes_summary"])
            lines.append("")
        lines.append("")

    # ── Transcript passages ───────────────────────────────────────────────────
    lines.append("── TRECHOS DE TRANSCRIÇÃO RELEVANTES ──")
    lines.append("")

    if meetings_passages:
        for mp in meetings_passages:
            passages = mp.get("passages") or []
            if not passages:
                continue
            n = mp.get("meeting_number", "?")
            title = mp.get("title", "")
            date = mp.get("meeting_date", "")
            date_str = f" ({date})" if date else ""
            lines.append(f"[Reunião {n} — {title}{date_str}]")
            for i, passage in enumerate(passages):
                lines.append(passage)
                if i < len(passages) - 1:
                    lines.append("---")
            lines.append("")
    else:
        lines.append("Nenhum trecho de transcrição encontrado para esta consulta.")
        lines.append("")

    # ── Requirements ─────────────────────────────────────────────────────────
    lines.append("── REQUISITOS RELACIONADOS ──")
    requirements = ctx.get("requirements") or []
    if requirements:
        for req in requirements:
            n = req.get("req_number")
            req_id = f"REQ-{n:03d}" if isinstance(n, int) else "REQ-???"
            req_type = req.get("req_type") or ""
            status = req.get("status") or ""
            title = req.get("title") or ""
            description = req.get("description") or ""
            desc_preview = description[:120] + ("..." if len(description) > 120 else "")
            type_status = f"{req_type}/{status}" if req_type or status else ""
            bracket = f" [{type_status}]" if type_status else ""
            lines.append(f"• {req_id}{bracket}: {title} — {desc_preview}")
    else:
        lines.append("Nenhum requisito relacionado encontrado.")
    lines.append("")

    # ── BPMN processes ────────────────────────────────────────────────────────
    lines.append("── PROCESSOS BPMN ──")
    processes = ctx.get("processes") or []
    if processes:
        for p in processes:
            name = p.get("name") or ""
            vc = p.get("version_count") or 0
            lines.append(f"• {name} ({vc} versão(ões))")
    else:
        lines.append("Nenhum processo BPMN registrado.")
    lines.append("")

    # ── SBVR ─────────────────────────────────────────────────────────────────
    lines.append("── VOCABULÁRIO E REGRAS SBVR ──")
    sbvr_terms = ctx.get("sbvr_terms") or []
    sbvr_rules = ctx.get("sbvr_rules") or []

    if sbvr_terms or sbvr_rules:
        if sbvr_terms:
            terms_str = " | ".join(
                f"{t['term']}: {t['definition']}" for t in sbvr_terms
            )
            lines.append(f"Termos: {terms_str}")
        if sbvr_rules:
            rules_str = " | ".join(
                f"{r['nucleo_nominal']} — {r['statement'][:100]}"
                + ("..." if len(r.get("statement", "")) > 100 else "")
                for r in sbvr_rules
            )
            lines.append(f"Regras: {rules_str}")
    else:
        lines.append("Nenhum dado SBVR relacionado encontrado.")
    lines.append("")

    # ── Meetings without transcript ───────────────────────────────────────────
    no_transcript = ctx.get("meetings_without_transcript") or []
    if no_transcript:
        lines.append("── REUNIÕES SEM TRANSCRIÇÃO ARMAZENADA ──")
        lines.append(
            "As seguintes reuniões não têm transcrição armazenada e não podem ser pesquisadas:"
        )
        lines.append(", ".join(no_transcript))
        lines.append("")

    return "\n".join(lines)


# ── Resumo da estrutura de dados do projeto ──────────────────────────────────

def retrieve_data_summary(project_id: str) -> dict:
    """
    Retorna um resumo quantitativo e estrutural dos dados do projeto:
    contagens por tabela, lista de reuniões, distribuição de requisitos por tipo/status,
    processos BPMN registrados, termos SBVR e elementos BMM.

    Sempre retorna um dict — nunca lança exceção.
    """
    db = _db()
    summary: dict = {
        "meetings": [],
        "req_total": 0,
        "req_by_type": {},
        "req_by_status": {},
        "req_by_priority": {},
        "n_sbvr_terms": 0,
        "n_sbvr_rules": 0,
        "bpmn_processes": [],
        "n_bpmn_versions": 0,
        "n_chunks_indexed": 0,
    }
    if not db:
        return summary

    # Meetings
    try:
        rows = _ok(
            db.table("meetings")
            .select("id, meeting_number, title, meeting_date, transcript_clean")
            .eq("project_id", project_id)
            .order("meeting_number")
            .execute()
        )
        summary["meetings"] = [
            {
                "number":     r.get("meeting_number"),
                "title":      r.get("title") or "(sem título)",
                "date":       str(r.get("meeting_date") or "—"),
                "has_transcript": bool(r.get("transcript_clean")),
            }
            for r in rows
        ]
    except Exception:
        pass

    # Requirements — contagens
    try:
        all_reqs = _ok(
            db.table("requirements")
            .select("req_number, req_type, status, priority")
            .eq("project_id", project_id)
            .execute()
        )
        summary["req_total"] = len(all_reqs)
        by_type: dict = {}
        by_status: dict = {}
        by_priority: dict = {}
        for r in all_reqs:
            t = r.get("req_type") or "não classificado"
            s = r.get("status") or "indefinido"
            p = r.get("priority") or "—"
            by_type[t]      = by_type.get(t, 0) + 1
            by_status[s]    = by_status.get(s, 0) + 1
            by_priority[p]  = by_priority.get(p, 0) + 1
        summary["req_by_type"]     = by_type
        summary["req_by_status"]   = by_status
        summary["req_by_priority"] = by_priority
    except Exception:
        pass

    # SBVR
    try:
        summary["n_sbvr_terms"] = len(_ok(
            db.table("sbvr_terms").select("id").eq("project_id", project_id).execute()
        ))
    except Exception:
        pass
    try:
        summary["n_sbvr_rules"] = len(_ok(
            db.table("sbvr_rules").select("id").eq("project_id", project_id).execute()
        ))
    except Exception:
        pass

    # BPMN processes
    try:
        proc_rows = _ok(
            db.table("bpmn_processes")
            .select("name, version_count, status")
            .eq("project_id", project_id)
            .order("name")
            .execute()
        )
        summary["bpmn_processes"] = [
            {
                "name":          p.get("name") or "—",
                "version_count": p.get("version_count") or 0,
                "status":        p.get("status") or "—",
            }
            for p in proc_rows
        ]
    except Exception:
        pass

    # BPMN versions total
    try:
        ver_rows = _ok(
            db.table("bpmn_versions")
            .select("id")
            .eq("project_id", project_id)
            .execute()
        )
        summary["n_bpmn_versions"] = len(ver_rows)
    except Exception:
        pass

    # Chunks indexados (busca semântica) — usa count="exact" para evitar truncagem a 1000
    try:
        _cr = (
            db.table("transcript_chunks")
            .select("*", count="exact")
            .eq("project_id", project_id)
            .limit(1)
            .execute()
        )
        summary["n_chunks_indexed"] = _cr.count or 0
    except Exception:
        pass

    return summary


def get_global_stats() -> dict:
    """Retorna contagens globais (todos os projetos) para o dashboard inicial.

    Sempre retorna um dict com chaves definidas — nunca lança exceção.
    """
    base: dict = {
        "n_projects":   0,
        "n_meetings":   0,
        "n_reqs":       0,
        "n_bpmn_procs": 0,
        "n_documents":  0,
        "available":    False,
    }
    db = _db()
    if not db:
        return base
    try:
        base["n_projects"] = len(_ok(db.table("contexts").select("id").execute()))
        base["n_meetings"] = len(_ok(db.table("meetings").select("id").execute()))
        base["available"]  = True
    except Exception:
        return base
    try:
        base["n_reqs"] = len(_ok(db.table("requirements").select("id").execute()))
    except Exception:
        pass
    try:
        base["n_bpmn_procs"] = len(_ok(db.table("bpmn_processes").select("id").execute()))
    except Exception:
        pass
    try:
        base["n_documents"] = len(_ok(db.table("meeting_documents").select("id").execute()))
    except Exception:
        pass
    return base


def list_recent_meetings(limit: int = 6, project_id: str | None = None) -> list[dict]:
    """Retorna as N reuniões mais recentes, opcionalmente filtradas por projeto."""
    db = _db()
    if not db:
        return []
    try:
        q = (
            db.table("meetings")
            .select("id, title, meeting_date, meeting_number, project_id")
            .order("created_at", desc=True)
            .limit(limit)
        )
        if project_id:
            q = q.eq("project_id", project_id)
        rows = _ok(q.execute())
        return [
            {
                "id":             r.get("id"),
                "title":          r.get("title") or "(sem título)",
                "meeting_date":   str(r.get("meeting_date") or "—"),
                "meeting_number": r.get("meeting_number"),
                "project_id":     r.get("project_id"),
            }
            for r in rows
        ]
    except Exception:
        return []


# ── Embeddings / Busca Semântica ──────────────────────────────────────────────

def transcript_chunks_table_exists() -> bool:
    """Verifica se a tabela transcript_chunks existe no banco."""
    db = _db()
    if not db:
        return False
    try:
        db.table("transcript_chunks").select("id").limit(1).execute()
        return True
    except Exception:
        return False


def test_db_chunk_insert(meeting_id: str, project_id: str) -> dict:
    """
    Insere uma linha dummy em transcript_chunks (embedding zerado, chunk_index=-1),
    verifica se foi persistida e apaga a linha de teste.

    Usado para diagnosticar problemas de permissão/serialização sem chamar nenhuma API.

    Returns:
        dict com campos: insert_ok, verify_count, delete_ok, error
    """
    from modules.embeddings import EMBEDDING_DIM

    db = _db()
    if not db:
        return {"insert_ok": False, "verify_count": 0, "delete_ok": False,
                "error": "Supabase não configurado."}

    dummy_row = {
        "meeting_id":  meeting_id,
        "project_id":  project_id,
        "chunk_index": -1,
        "chunk_text":  "__TEST_CHUNK__",
        "embedding":   [0.0] * EMBEDDING_DIM,
    }

    result = {"insert_ok": False, "verify_count": 0, "delete_ok": False, "error": None}

    try:
        db.table("transcript_chunks").upsert(
            dummy_row, on_conflict="meeting_id,chunk_index"
        ).execute()
        result["insert_ok"] = True
    except Exception as exc:
        result["error"] = f"INSERT falhou: {exc}"
        return result

    try:
        resp = (
            db.table("transcript_chunks")
            .select("id", count="exact")
            .eq("meeting_id", meeting_id)
            .eq("chunk_index", -1)
            .execute()
        )
        result["verify_count"] = resp.count or 0
    except Exception as exc:
        result["error"] = f"SELECT de verificação falhou: {exc}"

    try:
        db.table("transcript_chunks") \
            .delete() \
            .eq("meeting_id", meeting_id) \
            .eq("chunk_index", -1) \
            .execute()
        result["delete_ok"] = True
    except Exception as exc:
        result["error"] = (result["error"] or "") + f" | DELETE falhou: {exc}"

    return result


def save_transcript_embeddings(
    meeting_id: str,
    project_id: str,
    transcript: str,
    api_key: str,
    provider: str,
    fallback_text: str = "",
) -> int:
    """
    Normaliza, divide em chunks, gera embeddings e salva na tabela transcript_chunks.

    Fluxo:
      1. Normaliza `transcript` (remove lixo ASR/SRT).
      2. Se normalizado for vazio/curto (< 80 chars), tenta `fallback_text`
         (geralmente `minutes_md`) com a mesma normalização.
      3. Gera embeddings em batch.
      4. Upsert idempotente por (meeting_id, chunk_index).

    Returns:
        Número de chunks salvos (0 quando fonte é inviável ou API falha).
    """
    db = _db()
    if not db:
        return 0

    from modules.embeddings import chunk_text, embed_batch, normalize_for_embedding, EMBEDDING_PROVIDERS

    # 1. Normaliza a transcrição principal
    source_text = normalize_for_embedding(transcript or "")

    # 2. Fallback para minutes_md se transcrição for insuficiente após normalização
    if len(source_text.strip()) < 80 and fallback_text:
        source_text = normalize_for_embedding(fallback_text)

    if not source_text.strip():
        raise ValueError(
            f"Texto vazio após normalização "
            f"(transcript={len(transcript or '')} chars, fallback={len(fallback_text)} chars)."
        )

    # 3. Gera chunks
    chunks = chunk_text(source_text)
    if not chunks:
        raise ValueError(
            f"chunk_text retornou 0 chunks para texto de {len(source_text)} chars. "
            f"Verifique se a transcrição contém texto real."
        )

    # 4. Gera embeddings em batch (lança exceção se a API key for inválida, etc.)
    vectors = embed_batch(chunks, api_key, provider)

    if len(vectors) != len(chunks):
        raise ValueError(
            f"Mismatch embed_batch: {len(chunks)} chunks → {len(vectors)} vetores."
        )

    # 5. Upsert — idempotente por (meeting_id, chunk_index).
    emb_model = EMBEDDING_PROVIDERS.get(provider, {}).get("model")
    rows = [
        {
            "meeting_id":        meeting_id,
            "project_id":        project_id,
            "chunk_index":       i,
            "chunk_text":        chunk,
            "embedding":         vector,
            "embedding_provider": provider,
            "embedding_model":   emb_model,
        }
        for i, (chunk, vector) in enumerate(zip(chunks, vectors))
    ]

    # Upsert em lotes de 50 para evitar payload overflow
    batch_size = 50
    for start in range(0, len(rows), batch_size):
        db.table("transcript_chunks").upsert(
            rows[start:start + batch_size],
            on_conflict="meeting_id,chunk_index",
        ).execute()

    # Verificação real: conta o que efetivamente foi gravado no banco.
    # Retornar len(rows) seria otimista — o upsert pode completar sem erro
    # mas não gravar nada quando RLS bloqueia silenciosamente.
    verify = db.table("transcript_chunks") \
        .select("chunk_index", count="exact") \
        .eq("meeting_id", meeting_id) \
        .execute()
    actual = verify.count or 0

    if actual == 0 and len(rows) > 0:
        raise RuntimeError(
            f"Upsert aparentemente bem-sucedido ({len(rows)} chunks gerados) mas "
            f"0 linhas encontradas no banco após a gravação. "
            f"Verifique as políticas RLS da tabela transcript_chunks no Supabase "
            f"(permissões INSERT/UPDATE para o role anon ou authenticated)."
        )

    return actual


def search_semantic(
    project_id: str,
    question: str,
    api_key: str,
    provider: str,
    top_k: int = 8,
) -> list[dict]:
    """
    Busca semântica nos chunks de transcrição do projeto usando pgvector.

    Returns:
        Lista de dicts com: meeting_id, chunk_text, similarity
        Ordenada por similarity descendente.
    """
    db = _db()
    if not db:
        return []

    try:
        from modules.embeddings import embed_text

        # 1. Embed da pergunta
        query_vector = embed_text(question, api_key, provider)

        # 2. Chama a função SQL match_transcript_chunks
        rows = _ok(
            db.rpc(
                "match_transcript_chunks",
                {
                    "query_embedding":    query_vector,
                    "filter_project_id": project_id,
                    "match_count":       top_k,
                },
            ).execute()
        )

        return rows

    except Exception:
        return []


def retrieve_context_semantic(
    project_id: str,
    question: str,
    api_key: str,
    provider: str,
    top_k: int = 8,
) -> dict:
    """
    Versão semântica de retrieve_context_for_question().

    Substitui a busca por keyword nas transcrições por busca pgvector.
    Os demais dados estruturados (requisitos, BPMN, SBVR) continuam sendo
    recuperados por keyword — eles já são precisos e compactos.

    Returns:
        Mesmo formato de retrieve_context_for_question().
    """
    db = _db()
    keywords = _extract_keywords(question)

    result: dict = {
        "meetings_passages": [],
        "requirements": [],
        "processes": [],
        "sbvr_terms": [],
        "sbvr_rules": [],
        "meetings_without_transcript": [],
        "search_mode": "semantic",
        "data_summary": retrieve_data_summary(project_id),
    }

    # ── Busca semântica nas transcrições ──────────────────────────────────────
    semantic_chunks = search_semantic(project_id, question, api_key, provider, top_k)

    # Fallback automático: sem chunks (embeddings não gerados ou erro de API)
    # → usa busca por keyword para as transcrições, mantém dados estruturados via
    #   o caminho semântico abaixo. Sinaliza o modo para a UI mostrar aviso correto.
    if not semantic_chunks:
        fallback = retrieve_context_for_question(project_id, question)
        fallback["search_mode"] = "keyword_fallback"
        fallback["data_summary"] = result["data_summary"]  # reutiliza o já calculado
        return fallback

    if semantic_chunks:
        # Agrupa chunks por meeting_id para montar passagens por reunião
        from collections import defaultdict
        chunk_map: dict[str, list[dict]] = defaultdict(list)
        for chunk in semantic_chunks:
            chunk_map[chunk["meeting_id"]].append(chunk)

        # Busca metadados das reuniões referenciadas
        meeting_ids = list(chunk_map.keys())
        if db and meeting_ids:
            try:
                meeting_rows = _ok(
                    db.table("meetings")
                    .select("id, title, meeting_date, meeting_number, minutes_md")
                    .in_("id", meeting_ids)
                    .order("meeting_number")
                    .execute()
                )
            except Exception:
                meeting_rows = []

            meeting_meta = {m["id"]: m for m in meeting_rows}

            for mid, chunks in chunk_map.items():
                meta = meeting_meta.get(mid, {})
                passages = [c["chunk_text"] for c in chunks]
                minutes_summary = _extract_minutes_summary(meta.get("minutes_md") or "")
                result["meetings_passages"].append({
                    "meeting_number": meta.get("meeting_number") or 0,
                    "title":          meta.get("title") or "",
                    "meeting_date":   str(meta.get("meeting_date") or ""),
                    "passages":       passages,
                    "minutes_summary": minutes_summary,
                })

    # Inclui resumo de atas para reuniões NÃO retornadas pela busca semântica
    # (garante que participantes/decisões de todas as reuniões do projeto sejam
    #  injetados — não apenas as que tiveram chunks mais similares)
    if db:
        try:
            all_meetings = _ok(
                db.table("meetings")
                .select("id, title, meeting_date, meeting_number, minutes_md")
                .eq("project_id", project_id)
                .order("meeting_number")
                .execute()
            )
            indexed_ids = {
                c["meeting_id"] for c in semantic_chunks
            } if semantic_chunks else set()

            # IDs já incluídos via semantic chunks
            already_in_passages = {
                c["meeting_id"] for c in semantic_chunks
            } if semantic_chunks else set()

            for m in all_meetings:
                title = m.get("title") or m["id"]
                minutes_summary = _extract_minutes_summary(m.get("minutes_md") or "")

                if m["id"] not in indexed_ids:
                    # Meeting has no matching chunks — check if it has any chunks at all
                    try:
                        chunk_count = _ok(
                            db.table("transcript_chunks")
                            .select("id")
                            .eq("meeting_id", m["id"])
                            .limit(1)
                            .execute()
                        )
                        if not chunk_count:
                            result["meetings_without_transcript"].append(title)
                    except Exception:
                        pass

                # Always inject minutes summary for meetings not yet included via chunks
                if m["id"] not in already_in_passages and minutes_summary:
                    result["meetings_passages"].append({
                        "meeting_number": m.get("meeting_number") or 0,
                        "title":          title,
                        "meeting_date":   str(m.get("meeting_date") or ""),
                        "passages":       [],
                        "minutes_summary": minutes_summary,
                    })
        except Exception:
            pass

    # ── Dados estruturados (keyword-based, inalterado) ─────────────────────────
    if db and keywords:
        # Requirements
        try:
            all_reqs = _ok(
                db.table("requirements")
                .select("req_number, title, description, req_type, status")
                .eq("project_id", project_id)
                .order("req_number")
                .execute()
            )
            for req in all_reqs:
                combined = (
                    (req.get("title") or "") + " " + (req.get("description") or "")
                ).lower()
                if any(kw in combined for kw in keywords):
                    result["requirements"].append(req)
        except Exception:
            pass

        # SBVR terms
        try:
            all_terms = _ok(
                db.table("sbvr_terms")
                .select("term, definition")
                .eq("project_id", project_id)
                .execute()
            )
            for t in all_terms:
                combined = (
                    (t.get("term") or "") + " " + (t.get("definition") or "")
                ).lower()
                if any(kw in combined for kw in keywords):
                    result["sbvr_terms"].append(t)
        except Exception:
            pass

        # SBVR rules
        try:
            all_rules = _ok(
                db.table("sbvr_rules")
                .select("rule_id, statement, nucleo_nominal")
                .eq("project_id", project_id)
                .execute()
            )
            for r in all_rules:
                combined = (
                    (r.get("statement") or "") + " " + (r.get("nucleo_nominal") or "")
                ).lower()
                if any(kw in combined for kw in keywords):
                    result["sbvr_rules"].append(r)
        except Exception:
            pass

    # BPMN processes (always)
    if db:
        try:
            proc_rows = _ok(
                db.table("bpmn_processes")
                .select("name, version_count")
                .eq("project_id", project_id)
                .order("name")
                .execute()
            )
            result["processes"] = [
                {"name": p.get("name") or "", "version_count": p.get("version_count") or 0}
                for p in proc_rows
            ]
        except Exception:
            pass

    return result


def _fetch_all_chunks_paginated(db, project_id: str, select: str = "meeting_id") -> list[dict]:
    """
    Busca todos os chunks de um projeto usando paginação de 1000 em 1000.
    Necessário porque o Supabase tem um limite server-side de 1000 linhas por request
    que não pode ser sobreposto com .limit() no cliente.
    """
    results: list[dict] = []
    page_size = 1000
    offset = 0
    while True:
        batch = (
            db.table("transcript_chunks")
            .select(select)
            .eq("project_id", project_id)
            .range(offset, offset + page_size - 1)
            .execute().data or []
        )
        results.extend(batch)
        if len(batch) < page_size:
            break
        offset += page_size
    return results


def get_embedding_coverage(project_id: str) -> dict:
    """
    Retorna estatísticas de cobertura de embeddings do projeto.

    Returns:
        {total_meetings, indexed_meetings, total_chunks, providers_used}
    """
    db = _db()
    if not db:
        return {"total_meetings": 0, "indexed_meetings": 0, "total_chunks": 0, "providers_used": []}

    try:
        total_meetings = len(_ok(
            db.table("meetings")
            .select("id")
            .eq("project_id", project_id)
            .execute()
        ))

        # count="exact" com limit(1) retorna o total real sem buscar todas as linhas
        count_resp = (
            db.table("transcript_chunks")
            .select("*", count="exact")
            .eq("project_id", project_id)
            .limit(1)
            .execute()
        )
        total_chunks = count_resp.count or 0

        # Paginação para obter meeting_ids e provedores de todos os chunks
        chunk_rows = _fetch_all_chunks_paginated(
            db, project_id, "meeting_id, embedding_provider, embedding_model"
        )
        indexed_meetings = len({r["meeting_id"] for r in chunk_rows})

        # Combinações distintas de (provider, model)
        providers_used: list[dict] = []
        seen: set[tuple] = set()
        for r in chunk_rows:
            key = (r.get("embedding_provider") or "desconhecido", r.get("embedding_model") or "desconhecido")
            if key not in seen:
                seen.add(key)
                providers_used.append({"provider": key[0], "model": key[1]})

        return {
            "total_meetings":   total_meetings,
            "indexed_meetings": indexed_meetings,
            "total_chunks":     total_chunks,
            "providers_used":   providers_used,
        }
    except Exception:
        return {"total_meetings": 0, "indexed_meetings": 0, "total_chunks": 0, "providers_used": []}


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


# ── Validação de artefatos ────────────────────────────────────────────────────

def validate_artifact(table: str, artifact_id: str, validation_status: str,
                      validated_by: str = "", notes: str = "") -> bool:
    """Atualiza validation_status de qualquer artefato.

    Para status finais (validado/ajustado/rejeitado) grava também
    validated_by e validated_at com o timestamp atual.
    """
    db = _db()
    if not db:
        return False
    try:
        from datetime import datetime, timezone
        payload: dict = {"validation_status": validation_status}
        if validation_status in ("validado", "ajustado", "rejeitado"):
            payload["validated_by"] = validated_by or None
            payload["validated_at"] = datetime.now(timezone.utc).isoformat()
        if notes:
            payload["validation_notes"] = notes
        db.table(table).update(payload).eq("id", artifact_id).execute()
        return True
    except Exception:
        return False


def update_artifact_content(table: str, artifact_id: str, updates: dict) -> bool:
    """Edição inline de campos de conteúdo (title, description, statement, etc.)."""
    db = _db()
    if not db:
        return False
    try:
        db.table(table).update(updates).eq("id", artifact_id).execute()
        return True
    except Exception:
        return False


# ── Auditoria de login ────────────────────────────────────────────────────────

def log_login_event(
    login: str,
    domain: str = "local",
    tenant_id: str | None = None,
    role: str | None = None,
    success: bool = True,
    fail_reason: str = "",
) -> None:
    """Registra um evento de login (sucesso ou falha). Fire-and-forget — nunca lança exceção."""
    db = _db()
    if not db:
        return
    try:
        payload: dict = {
            "login":       login or "?",
            "domain":      domain or "local",
            "tenant_id":   tenant_id or None,
            "role":        role or None,
            "success":     success,
            "fail_reason": fail_reason or None,
        }
        db.table("login_logs").insert(payload).execute()
    except Exception:
        pass  # auditoria nunca deve bloquear o fluxo de login


# ── Google Calendar per project ───────────────────────────────────────────────

def get_project_calendar_id(project_id: str) -> str | None:
    """Return the calendar_id configured for this project, or None if not set."""
    db = _db()
    if not db or not project_id:
        return None
    try:
        rows = _ok(
            db.table("project_calendar_config")
            .select("calendar_id")
            .eq("project_id", project_id)
            .limit(1)
            .execute()
        )
        return rows[0]["calendar_id"] if rows else None
    except Exception:
        return None


def set_project_calendar_id(project_id: str, calendar_id: str) -> bool:
    """Upsert the calendar_id for a project. Returns True on success."""
    db = _db()
    if not db:
        return False
    from datetime import datetime, timezone
    try:
        db.table("project_calendar_config").upsert({
            "project_id":  project_id,
            "calendar_id": calendar_id.strip(),
            "updated_at":  datetime.now(timezone.utc).isoformat(),
        }).execute()
        return True
    except Exception:
        return False


def delete_project_calendar_id(project_id: str) -> bool:
    """Remove the calendar_id override for a project."""
    db = _db()
    if not db:
        return False
    try:
        db.table("project_calendar_config").delete().eq("project_id", project_id).execute()
        return True
    except Exception:
        return False


def list_project_calendar_configs() -> list[dict]:
    """Return all project calendar configs joined with project name."""
    db = _db()
    if not db:
        return []
    try:
        rows = _ok(
            db.table("project_calendar_config")
            .select("project_id, calendar_id, updated_at, projects(name)")
            .execute()
        )
        result = []
        for r in rows:
            proj = r.get("projects") or {}
            result.append({
                "project_id":   r["project_id"],
                "project_name": proj.get("name", "—"),
                "calendar_id":  r["calendar_id"],
                "updated_at":   r.get("updated_at", ""),
            })
        return result
    except Exception:
        return []


def list_login_logs(
    domain: str | None = None,
    success: bool | None = None,
    limit: int = 200,
) -> list[dict]:
    """Retorna eventos de login mais recentes, opcionalmente filtrados."""
    db = _db()
    if not db:
        return []
    try:
        q = db.table("login_logs").select("*").order("logged_at", desc=True).limit(limit)
        if domain:
            q = q.eq("domain", domain)
        if success is not None:
            q = q.eq("success", success)
        return _ok(q.execute())
    except Exception:
        return []


# =============================================================================
# ATA ENGINE — ROSTER DE PARTICIPANTES
# =============================================================================
# Funções de leitura/escrita para project_roster e meeting_participants.
# Padrão: fail-open — retornam [] / None / False sem levantar exceção para o caller.
# =============================================================================

import re as _re
import logging as _logging

_roster_log = _logging.getLogger(__name__)

# Cores padrão do ATA Engine — usadas como swatches na UI e como fallback
ATA_ENGINE_COLORS = {
    "navy":   "0B1E3D",
    "blue":   "1A4B8C",
    "green":  "1A7F5A",
    "amber":  "C97B1A",
    "purple": "6B3FA0",
    "muted":  "8496B0",
}
FALLBACK_COLOR = ATA_ENGINE_COLORS["muted"]


# ── Roster — leitura ──────────────────────────────────────────────────────────

def get_project_roster(project_id: str, include_inactive: bool = False) -> list[dict]:
    """Retorna membros do roster de um projeto ordenados por sort_order."""
    db = get_supabase_client()
    if not db:
        return []
    try:
        q = (
            db.table("project_roster")
            .select("id, initials, full_name, area, color_hex, name_aliases, "
                    "project_slug, is_active, sort_order, created_at, updated_at")
            .eq("project_id", project_id)
            .order("sort_order")
            .order("initials")
        )
        if not include_inactive:
            q = q.eq("is_active", True)
        return _ok(q.execute())
    except Exception as e:
        _roster_log.error("get_project_roster(%s): %s", project_id, e)
        return []


def get_roster_member_by_initials(project_id: str, initials: str) -> dict | None:
    """Retorna um membro do roster pelas iniciais dentro de um projeto."""
    db = get_supabase_client()
    if not db:
        return None
    try:
        result = (
            db.table("project_roster")
            .select("*")
            .eq("project_id", project_id)
            .eq("initials", initials.upper())
            .single()
            .execute()
        )
        return result.data
    except Exception as e:
        _roster_log.error("get_roster_member_by_initials(%s, %s): %s", project_id, initials, e)
        return None


# ── Roster — escrita ──────────────────────────────────────────────────────────

def upsert_roster_member(project_id: str, member: dict) -> dict | None:
    """Cria ou atualiza um membro no roster. Levanta ValueError se formato inválido."""
    required = ["initials", "full_name", "color_hex"]
    missing = [f for f in required if not member.get(f)]
    if missing:
        raise ValueError(f"Campos obrigatórios ausentes: {missing}")

    initials = member["initials"].upper().strip()
    if not _re.match(r"^[A-Z]{1,4}$", initials):
        raise ValueError(f"Iniciais invalidas: '{initials}' — use 1 a 4 letras maiusculas")

    color_hex = member["color_hex"].lstrip("#").upper()
    if not _re.match(r"^[0-9A-F]{6}$", color_hex):
        raise ValueError(f"Cor invalida: '{color_hex}' — use hex de 6 caracteres sem #")

    db = get_supabase_client()
    if not db:
        return None

    payload = {
        "project_id":   project_id,
        "initials":     initials,
        "full_name":    member["full_name"].strip(),
        "area":         (member.get("area") or "").strip() or None,
        "color_hex":    color_hex,
        "name_aliases": member.get("name_aliases") or [],
        "project_slug": member.get("project_slug") or None,
        "sort_order":   member.get("sort_order", 0),
        "is_active":    member.get("is_active", True),
    }
    try:
        result = (
            db.table("project_roster")
            .upsert(payload, on_conflict="project_id,initials")
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        _roster_log.error("upsert_roster_member(%s, %s): %s", project_id, initials, e)
        return None


def deactivate_roster_member(roster_id: str) -> bool:
    """Soft delete de um membro do roster (preserva histórico)."""
    db = get_supabase_client()
    if not db:
        return False
    try:
        db.table("project_roster").update({"is_active": False}).eq("id", roster_id).execute()
        return True
    except Exception as e:
        _roster_log.error("deactivate_roster_member(%s): %s", roster_id, e)
        return False


# ── Participantes de reunião ──────────────────────────────────────────────────

def get_meeting_participants_roster(meeting_id: str) -> list[dict]:
    """Retorna participantes confirmados de uma reunião via RPC do Supabase."""
    db = get_supabase_client()
    if not db:
        return []
    try:
        result = db.rpc("get_meeting_participants_full", {"p_meeting_id": meeting_id}).execute()
        return result.data or []
    except Exception as e:
        _roster_log.error("get_meeting_participants_roster(%s): %s", meeting_id, e)
        return []


def save_meeting_participants(
    meeting_id: str,
    roster_ids: list[str],
    source: str = "auto",
    confirmed: bool = True,
) -> bool:
    """Persiste participantes de uma reunião (upsert idempotente)."""
    if not roster_ids:
        return True
    db = get_supabase_client()
    if not db:
        return False
    payload = [
        {"meeting_id": meeting_id, "roster_id": rid, "confirmed": confirmed, "source": source}
        for rid in roster_ids
    ]
    try:
        db.table("meeting_participants").upsert(payload, on_conflict="meeting_id,roster_id").execute()
        return True
    except Exception as e:
        _roster_log.error("save_meeting_participants(%s): %s", meeting_id, e)
        return False


def clear_meeting_participants(meeting_id: str) -> bool:
    """Remove todos os participantes de uma reunião (antes de re-inferir)."""
    db = get_supabase_client()
    if not db:
        return False
    try:
        db.table("meeting_participants").delete().eq("meeting_id", meeting_id).execute()
        return True
    except Exception as e:
        _roster_log.error("clear_meeting_participants(%s): %s", meeting_id, e)
        return False


# ── Matching: nome da transcrição → roster ────────────────────────────────────

def match_participant_to_roster(name: str, roster: list[dict]) -> dict | None:
    """Casa um nome da transcrição com o roster em 3 passes: full_name, initials, aliases."""
    if not name or not roster:
        return None
    name_lower = name.lower().strip()
    for member in roster:
        if member["full_name"].lower() == name_lower:
            return member
    for member in roster:
        if member["initials"].lower() == name_lower:
            return member
    for member in roster:
        aliases = [a.lower() for a in (member.get("name_aliases") or [])]
        for alias in aliases:
            if name_lower == alias or name_lower in alias or alias in name_lower:
                return member
    return None


def infer_and_save_participants(
    names_from_transcript: list[str],
    project_id: str,
    meeting_id: str,
) -> list[dict]:
    """Infere participantes a partir de nomes da transcrição, cruza com roster e persiste."""
    roster = get_project_roster(project_id)
    resolved: list[dict] = []
    matched_ids: list[str] = []

    for name in names_from_transcript:
        member = match_participant_to_roster(name, roster)
        if member and member["id"] not in matched_ids:
            matched_ids.append(member["id"])
            resolved.append(member)
        elif not member:
            parts = name.strip().split()
            if len(parts) >= 2:
                ini = (parts[0][0] + parts[1][0]).upper()
            elif len(parts) == 1 and len(parts[0]) >= 2:
                ini = parts[0][:2].upper()
            else:
                ini = "??"
            resolved.append({
                "id": None, "initials": ini, "full_name": name,
                "area": None, "color_hex": FALLBACK_COLOR,
                "name_aliases": [], "sort_order": 999,
                "confirmed": True, "source": "auto",
            })

    if matched_ids:
        save_meeting_participants(meeting_id, matched_ids, source="auto")

    resolved.sort(key=lambda p: (p.get("sort_order") or 999, p["initials"]))
    return resolved


# ── Analytics ─────────────────────────────────────────────────────────────────

def get_roster_attendance_summary(project_id: str) -> list[dict]:
    """Resumo de presença: quantas reuniões cada membro do roster participou."""
    db = get_supabase_client()
    if not db:
        return []
    try:
        roster = get_project_roster(project_id)
        if not roster:
            return []
        mp_result = db.table("meeting_participants").select("roster_id, confirmed").execute()
        mp_rows = mp_result.data or []
        counts: dict[str, dict] = {}
        for row in mp_rows:
            rid = row["roster_id"]
            if rid not in counts:
                counts[rid] = {"total": 0, "confirmed": 0}
            counts[rid]["total"] += 1
            if row["confirmed"]:
                counts[rid]["confirmed"] += 1
        summary = []
        for m in roster:
            c = counts.get(m["id"], {"total": 0, "confirmed": 0})
            summary.append({
                "roster_id": m["id"], "initials": m["initials"],
                "full_name": m["full_name"], "area": m["area"],
                "color_hex": m["color_hex"],
                "total_meetings": c["total"], "confirmed_meetings": c["confirmed"],
            })
        summary.sort(key=lambda x: x["confirmed_meetings"], reverse=True)
        return summary
    except Exception as e:
        _roster_log.error("get_roster_attendance_summary(%s): %s", project_id, e)
        return []


# ── Extração automática de participantes ──────────────────────────────────────

def extract_participants_from_project(
    project_id: str,
    meeting_numbers: list | None = None,
) -> dict:
    """
    Varre minutes_md de todas as reuniões (ou um subconjunto) do projeto e extrai
    nomes únicos de participantes. Retorna candidatos com iniciais, cores e aliases
    gerados automaticamente — sem gravar nada no banco.

    Retorna:
        {
            "candidates": [{"full_name", "initials", "color_hex", "name_aliases", "meetings_count"}, ...],
            "existing_initials": set[str],
            "meetings_scanned": int,
            "meetings_with_participants": int,
        }
    """
    import re as _re2
    import unicodedata

    _STOP = {
        'de','da','do','dos','das','e','a','o','as','os','em','por',
        'para','com','na','no','nas','nos','ao','aos','um','uma',
    }
    _COLOR_CYCLE = ["0B1E3D", "1A4B8C", "1A7F5A", "C97B1A", "6B3FA0"]

    def _parse_names_from_md(md: str) -> list:
        names = []
        in_section = False
        for line in md.splitlines():
            stripped = line.strip()
            if _re2.match(r'^#{1,4}\s*Participantes?', stripped, _re2.IGNORECASE):
                in_section = True
                continue
            if in_section and _re2.match(r'^#{1,4}\s', stripped):
                in_section = False
                continue
            if in_section and _re2.match(r'^[-*]\s+', stripped):
                name = _re2.sub(r'^[-*]\s+', '', stripped).strip()
                if len(name) >= 3 and not _re2.search(r'\d', name):
                    names.append(name)
        return names

    def _generate_initials(name: str, taken: set) -> str:
        words = [w for w in name.strip().split() if w.lower() not in _STOP and len(w) > 1]
        if not words:
            words = name.strip().split()[:2] or [name]
        candidates = []
        if len(words) >= 2:
            candidates.append("".join(w[0].upper() for w in words[:2]))
        elif words:
            candidates.append(words[0][:2].upper())
        if len(words) >= 3:
            candidates.append("".join(w[0].upper() for w in words[:3]))
        if len(words) >= 2:
            opt = (words[0][0] + words[-1][:2]).upper()
            if len(opt) <= 4:
                candidates.append(opt)
        if len(words) >= 4:
            candidates.append("".join(w[0].upper() for w in words[:4]))
        candidates.append(words[0][:4].upper())
        seen_c: set = set()
        for c in candidates:
            if c and _re2.match(r'^[A-Z]{1,4}$', c) and c not in seen_c:
                seen_c.add(c)
                if c not in taken:
                    return c
        base = candidates[0][:2] if candidates else "XX"
        for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            opt = (base + ch)[:4]
            if opt not in taken and _re2.match(r'^[A-Z]{1,4}$', opt):
                return opt
        return base

    def _build_aliases(name: str) -> list:
        aliases = []
        parts = name.strip().split()
        if parts:
            aliases.append(parts[0])
        if name not in aliases:
            aliases.append(name)
        try:
            norm = unicodedata.normalize('NFD', name)
            ascii_name = ''.join(c for c in norm if unicodedata.category(c) != 'Mn')
            if ascii_name != name and ascii_name not in aliases:
                aliases.append(ascii_name)
        except Exception:
            pass
        return aliases

    meetings = list_meetings(project_id)
    if meeting_numbers:
        meetings = [m for m in meetings if m.get("meeting_number") in meeting_numbers]

    name_counts: dict = {}
    meetings_with_participants = 0

    for meeting in meetings:
        md = meeting.get("minutes_md") or ""
        if not md:
            continue
        names = _parse_names_from_md(md)
        if names:
            meetings_with_participants += 1
        for name in names:
            key = name.strip()
            if key:
                name_counts[key] = name_counts.get(key, 0) + 1

    roster = get_project_roster(project_id, include_inactive=True)
    existing_initials: set = {m["initials"] for m in roster}
    existing_names_lower: set = {m["full_name"].lower() for m in roster}

    taken_initials: set = set(existing_initials)
    candidates = []
    color_idx = len(roster)

    for name, count in sorted(name_counts.items(), key=lambda x: -x[1]):
        if name.lower() in existing_names_lower:
            continue
        initials = _generate_initials(name, taken_initials)
        taken_initials.add(initials)
        color_hex = _COLOR_CYCLE[color_idx % len(_COLOR_CYCLE)]
        color_idx += 1
        candidates.append({
            "full_name":      name,
            "initials":       initials,
            "color_hex":      color_hex,
            "name_aliases":   _build_aliases(name),
            "meetings_count": count,
        })

    return {
        "candidates":                 candidates,
        "existing_initials":          existing_initials,
        "meetings_scanned":           len(meetings),
        "meetings_with_participants": meetings_with_participants,
    }

# ----- Persistência do relatório executivo da reunião em html

def save_report_html(
    meeting_id: str,
    report_html: str,
    provider: str = "",
) -> bool:
    client = get_supabase_client()
    if client is None:
        return False
    try:
        from datetime import datetime, timezone
        client.table("meetings").update({
            "report_html":         report_html,
            "report_generated_at": datetime.now(timezone.utc).isoformat(),
            "report_provider":     provider,
        }).eq("id", meeting_id).execute()
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"save_report_html failed: {e}")
        return False


def get_report_html(meeting_id: str) -> str | None:
    client = get_supabase_client()
    if client is None:
        return None
    try:
        result = (
            client.table("meetings")
            .select("report_html")
            .eq("id", meeting_id)
            .single()
            .execute()
        )
        return result.data.get("report_html") or None
    except Exception:
        return None


def list_dmn_by_project(project_id: str) -> list[dict]:
    """Retorna todas as decisões DMN de todas as reuniões do projeto.

    Lê dmn_json de cada reunião e desnormaliza em uma lista plana de decisões,
    cada uma enriquecida com meeting_number e meeting_title para exibição.

    Retorna [] se nenhuma reunião tiver dmn_json ou Supabase não configurado.
    """
    db = _db()
    if not db:
        return []
    try:
        rows = _ok(
            db.table("meetings")
            .select("id, meeting_number, title, meeting_date, dmn_json")
            .eq("project_id", project_id)
            .not_.is_("dmn_json", "null")
            .order("meeting_number")
            .execute()
        )
    except Exception:
        return []

    import json as _json
    result = []
    for m in rows:
        raw = (m.get("dmn_json") or "").strip()
        if not raw:
            continue
        try:
            data = _json.loads(raw)
            decisions = data.get("decisions", [])
            for d in decisions:
                d["_meeting_id"]     = m["id"]
                d["_meeting_number"] = m.get("meeting_number")
                d["_meeting_title"]  = m.get("title", "")
                d["_meeting_date"]   = str(m.get("meeting_date") or "")
                result.append(d)
        except Exception:
            continue
    return result


def save_artifacts_from_document(
    project_id: str,
    doc_id: str,
    extracted: dict,
) -> dict:
    """Persiste artefatos extraídos de um documento (DocumentExtractorAgent).

    extracted — dict retornado pelo agente com chaves opcionais:
        requirements    list[dict]  — title, description, req_type, priority, source_quote
        sbvr_terms      list[dict]  — term, definition, category
        sbvr_rules      list[dict]  — id, statement, rule_type, source, short_title
        bmm_goals       list[dict]  — (armazenados no metadata do documento, não em tabela)
        bmm_strategies  list[dict]  — idem
        bmm_policies    list[dict]  — idem
        dmn_decisions   list[dict]  — idem

    BMM e DMN não têm tabelas dedicadas: persistidos via update_document_meta().
    Retorna {"requirements": n, "terms": n, "rules": n, "bmm": bool, "dmn": bool}.
    """
    db = _db()
    if not db:
        return {"requirements": 0, "terms": 0, "rules": 0, "bmm": False, "dmn": False}

    n_req = n_terms = n_rules = 0

    # ── Requirements ───────────────────────────────────────────────────────────
    next_num = next_req_number(project_id)
    for item in (extracted.get("requirements") or []):
        result = save_new_requirement(
            project_id=project_id,
            meeting_id=None,
            req_number=next_num,
            title=item.get("title", ""),
            description=item.get("description", ""),
            req_type=item.get("req_type", ""),
            priority=item.get("priority", ""),
            source_quote=item.get("source_quote", "") or "",
            origin="documento",
            doc_ref=doc_id,
        )
        if result:
            next_num += 1
            n_req += 1

    # ── SBVR Terms ─────────────────────────────────────────────────────────────
    for t in (extracted.get("sbvr_terms") or []):
        base = {
            "project_id": project_id,
            "term":       t.get("term", ""),
            "definition": t.get("definition", ""),
            "category":   t.get("category", ""),
        }
        for use_new_fields in (True, False):
            payload = dict(base)
            if use_new_fields:
                payload["origin"] = "documento"
                payload["doc_ref"] = doc_id
            try:
                db.table("sbvr_terms").insert(payload).execute()
                n_terms += 1
                break
            except Exception:
                if not use_new_fields:
                    break
                continue

    # ── SBVR Rules ─────────────────────────────────────────────────────────────
    for r in (extracted.get("sbvr_rules") or []):
        nucleo = r.get("short_title", "").strip() or rule_keyword_pt(r.get("statement", ""))
        base = {
            "project_id":     project_id,
            "rule_id":        r.get("id", ""),
            "statement":      r.get("statement", ""),
            "nucleo_nominal": nucleo,
            "rule_type":      r.get("rule_type", ""),
            "source":         r.get("source", ""),
        }
        for use_new_fields in (True, False):
            payload = dict(base)
            if use_new_fields:
                payload["origin"] = "documento"
                payload["doc_ref"] = doc_id
            try:
                db.table("sbvr_rules").insert(payload).execute()
                n_rules += 1
                break
            except Exception:
                if not use_new_fields:
                    break
                continue

    # ── BMM + DMN: store in document metadata ─────────────────────────────────
    has_bmm = bool(
        extracted.get("bmm_goals")
        or extracted.get("bmm_strategies")
        or extracted.get("bmm_policies")
    )
    has_dmn = bool(extracted.get("dmn_decisions"))

    if has_bmm or has_dmn:
        try:
            from modules.document_store import update_document_meta
            meta_patch = {}
            if has_bmm:
                meta_patch["bmm"] = {
                    "goals":      extracted.get("bmm_goals", []),
                    "strategies": extracted.get("bmm_strategies", []),
                    "policies":   extracted.get("bmm_policies", []),
                }
            if has_dmn:
                meta_patch["dmn_decisions"] = extracted.get("dmn_decisions", [])
            update_document_meta(doc_id, meta_patch)
        except Exception:
            pass

    return {"requirements": n_req, "terms": n_terms, "rules": n_rules,
            "bmm": has_bmm, "dmn": has_dmn}


def list_argumentation_by_project(project_id: str) -> list[dict]:
    """Retorna todas as questões IBIS de todas as reuniões do projeto.

    Lê argumentation_json de cada reunião e desnormaliza em uma lista plana
    de questões, cada uma enriquecida com meeting_number e meeting_title.

    Retorna [] se nenhuma reunião tiver argumentation_json ou Supabase não
    configurado.
    """
    db = _db()
    if not db:
        return []
    try:
        rows = _ok(
            db.table("meetings")
            .select("id, meeting_number, title, meeting_date, argumentation_json")
            .eq("project_id", project_id)
            .not_.is_("argumentation_json", "null")
            .order("meeting_number")
            .execute()
        )
    except Exception:
        return []

    import json as _json
    result = []
    for m in rows:
        raw = (m.get("argumentation_json") or "").strip()
        if not raw:
            continue
        try:
            data = _json.loads(raw)
            questions = data.get("questions", [])
            for q in questions:
                q["_meeting_id"]     = m["id"]
                q["_meeting_number"] = m.get("meeting_number")
                q["_meeting_title"]  = m.get("title", "")
                q["_meeting_date"]   = str(m.get("meeting_date") or "")
                result.append(q)
        except Exception:
            continue
    return result

