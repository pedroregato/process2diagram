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


def create_project(name: str, description: str = "", sigla: str = "") -> dict | None:
    """Cria e retorna um novo projeto."""
    db = _db()
    if not db:
        return None
    try:
        rows = _ok(
            db.table("projects")
            .insert({
                "name":        name.strip(),
                "sigla":       sigla.strip().upper(),
                "description": description.strip(),
            })
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
            payload1["bpmn_xml"]     = hub.bpmn.xml
            payload1["mermaid_code"] = hub.bpmn.mermaid
        if hasattr(hub, "minutes") and hub.minutes.ready:
            payload1["minutes_md"] = hub.minutes.full_text
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
            # nucleo_nominal: LLM short_title preferred; heuristic fallback
            nucleo = getattr(r, "short_title", "").strip() or rule_keyword_pt(r.statement)
            db.table("sbvr_rules").insert({
                "meeting_id":     meeting_id,
                "project_id":     project_id,
                "rule_id":        r.id,
                "statement":      r.statement,
                "nucleo_nominal": nucleo,
                "rule_type":      r.rule_type,
                "source":         r.source,
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
    """Retorna todos os processos BPMN do projeto ordenados por nome."""
    db = _db()
    if not db:
        return []
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
                .select("id, title, meeting_date, meeting_number, transcript_clean, transcript_raw")
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

            if not transcript:
                result["meetings_without_transcript"].append(title)
                continue

            if keywords:
                passages = _extract_passages(transcript, keywords)
            else:
                # No keywords — return first passage as overview
                passages = _extract_passages(transcript, [], context_lines=0, max_passages=0)

            if passages:
                result["meetings_passages"].append({
                    "meeting_number": meeting_number,
                    "title": title,
                    "meeting_date": meeting_date,
                    "passages": passages,
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

    # ── Transcript passages ───────────────────────────────────────────────────
    lines.append("── TRECHOS DE TRANSCRIÇÃO RELEVANTES ──")
    lines.append("")

    meetings_passages = ctx.get("meetings_passages") or []
    if meetings_passages:
        for mp in meetings_passages:
            n = mp.get("meeting_number", "?")
            title = mp.get("title", "")
            date = mp.get("meeting_date", "")
            date_str = f" ({date})" if date else ""
            lines.append(f"[Reunião {n} — {title}{date_str}]")
            passages = mp.get("passages") or []
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

    # Chunks indexados (busca semântica)
    try:
        chunk_rows = _ok(
            db.table("transcript_chunks")
            .select("id")
            .eq("project_id", project_id)
            .execute()
        )
        summary["n_chunks_indexed"] = len(chunk_rows)
    except Exception:
        pass

    return summary


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


def save_transcript_embeddings(
    meeting_id: str,
    project_id: str,
    transcript: str,
    api_key: str,
    provider: str,
) -> int:
    """
    Divide a transcrição em chunks, gera embeddings e salva na tabela transcript_chunks.

    Apaga os chunks anteriores da reunião antes de inserir novos (idempotente).

    Returns:
        Número de chunks salvos (0 em caso de erro).
    """
    db = _db()
    if not db or not transcript or not transcript.strip():
        return 0

    try:
        from modules.embeddings import chunk_text, embed_batch

        # 1. Gera chunks
        chunks = chunk_text(transcript)
        if not chunks:
            return 0

        # 2. Gera embeddings em batch
        vectors = embed_batch(chunks, api_key, provider)

        # 3. Remove chunks anteriores desta reunião
        try:
            db.table("transcript_chunks").delete().eq("meeting_id", meeting_id).execute()
        except Exception:
            pass

        # 4. Insere novos chunks
        rows = [
            {
                "meeting_id":   meeting_id,
                "project_id":   project_id,
                "chunk_index":  i,
                "chunk_text":   chunk,
                "embedding":    vector,
            }
            for i, (chunk, vector) in enumerate(zip(chunks, vectors))
        ]

        # Insere em lotes de 50 para evitar payload overflow
        batch_size = 50
        for start in range(0, len(rows), batch_size):
            db.table("transcript_chunks").insert(rows[start:start + batch_size]).execute()

        return len(rows)

    except Exception:
        return 0


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
                    .select("id, title, meeting_date, meeting_number")
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
                result["meetings_passages"].append({
                    "meeting_number": meta.get("meeting_number") or 0,
                    "title":          meta.get("title") or "",
                    "meeting_date":   str(meta.get("meeting_date") or ""),
                    "passages":       passages,
                })

    # Verifica reuniões sem chunks (sem transcript indexado)
    if db:
        try:
            all_meetings = _ok(
                db.table("meetings")
                .select("id, title")
                .eq("project_id", project_id)
                .execute()
            )
            indexed_ids = {
                c["meeting_id"] for c in semantic_chunks
            } if semantic_chunks else set()

            for m in all_meetings:
                if m["id"] not in indexed_ids:
                    # Verifica se tem transcript mas não está indexado
                    try:
                        chunk_count = _ok(
                            db.table("transcript_chunks")
                            .select("id")
                            .eq("meeting_id", m["id"])
                            .limit(1)
                            .execute()
                        )
                        if not chunk_count:
                            result["meetings_without_transcript"].append(
                                m.get("title") or m["id"]
                            )
                    except Exception:
                        pass
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


def get_embedding_coverage(project_id: str) -> dict:
    """
    Retorna estatísticas de cobertura de embeddings do projeto.

    Returns:
        {total_meetings, indexed_meetings, total_chunks}
    """
    db = _db()
    if not db:
        return {"total_meetings": 0, "indexed_meetings": 0, "total_chunks": 0}

    try:
        total_meetings = len(_ok(
            db.table("meetings")
            .select("id")
            .eq("project_id", project_id)
            .execute()
        ))
        chunk_rows = _ok(
            db.table("transcript_chunks")
            .select("meeting_id")
            .eq("project_id", project_id)
            .execute()
        )
        total_chunks = len(chunk_rows)
        indexed_meetings = len({r["meeting_id"] for r in chunk_rows})
        return {
            "total_meetings":   total_meetings,
            "indexed_meetings": indexed_meetings,
            "total_chunks":     total_chunks,
        }
    except Exception:
        return {"total_meetings": 0, "indexed_meetings": 0, "total_chunks": 0}


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
