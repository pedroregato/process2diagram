# ─────────────────────────────────────────────────────────────────────────────
# PATCH — core/project_store.py
#
# Adicione as duas funções abaixo ao final do arquivo, antes do bloco
# de Analytics (função get_roster_attendance_summary).
# ─────────────────────────────────────────────────────────────────────────────


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
