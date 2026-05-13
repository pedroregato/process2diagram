# core/project_store.py  (trecho de adição — adicionar ao arquivo existente)
# =============================================================================
# ATA Engine Integration — Funções de Roster e Participantes de Reunião
# FGV/DTI · Equipe SOLCORP · Maio 2026
# =============================================================================
# Adicionar estas funções ao project_store.py existente, logo após as funções
# de gerenciamento de projetos e reuniões.
#
# Padrão do arquivo:
#   - Todas as funções são fail-open: retornam [] / None / False quando
#     o Supabase não está configurado ou ocorre erro.
#   - Nenhuma função levanta exceção para o caller; erros são logados.
#   - Tipos de retorno são dicts planos (não dataclasses) para compatibilidade
#     com st.session_state e JSON serialization.
# =============================================================================

from __future__ import annotations

import logging
import re
from typing import Optional

# get_supabase_client() já importado no topo do project_store.py existente
# from modules.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

# Cores padrão do ATA Engine — usadas como swatches na UI e como fallback
ATA_ENGINE_COLORS = {
    "navy":   "0B1E3D",   # área cliente (escuro)
    "blue":   "1A4B8C",   # área cliente (médio-escuro)
    "green":  "1A7F5A",   # equipe interna
    "amber":  "C97B1A",   # equipe interna
    "purple": "6B3FA0",   # equipe interna
    "muted":  "8496B0",   # participante temporário / não identificado
}

# Cor atribuída a participantes extraídos da transcrição sem correspondência no roster
FALLBACK_COLOR = ATA_ENGINE_COLORS["muted"]


# ─────────────────────────────────────────────────────────────────────────────
# ROSTER — LEITURA
# ─────────────────────────────────────────────────────────────────────────────

def get_project_roster(project_id: str, include_inactive: bool = False) -> list[dict]:
    """
    Retorna os membros do roster de um projeto, ordenados por sort_order.

    Args:
        project_id:       UUID do projeto.
        include_inactive: Se True, inclui membros com is_active=False.

    Returns:
        Lista de dicts com campos: id, initials, full_name, area, color_hex,
        name_aliases, project_slug, is_active, sort_order.
        Retorna [] se Supabase não configurado ou erro.
    """
    client = get_supabase_client()
    if not client:
        return []
    try:
        query = (
            client.table("project_roster")
            .select("id, initials, full_name, area, color_hex, name_aliases, "
                    "project_slug, is_active, sort_order, created_at, updated_at")
            .eq("project_id", project_id)
            .order("sort_order")
            .order("initials")
        )
        if not include_inactive:
            query = query.eq("is_active", True)
        result = query.execute()
        return result.data or []
    except Exception as e:
        logger.error("get_project_roster(%s): %s", project_id, e)
        return []


def get_roster_member(roster_id: str) -> Optional[dict]:
    """
    Retorna um membro específico do roster pelo seu UUID.

    Returns:
        Dict com todos os campos do roster, ou None se não encontrado.
    """
    client = get_supabase_client()
    if not client:
        return None
    try:
        result = (
            client.table("project_roster")
            .select("*")
            .eq("id", roster_id)
            .single()
            .execute()
        )
        return result.data
    except Exception as e:
        logger.error("get_roster_member(%s): %s", roster_id, e)
        return None


def get_roster_member_by_initials(project_id: str, initials: str) -> Optional[dict]:
    """
    Retorna um membro do roster pelas iniciais dentro de um projeto.

    Args:
        project_id: UUID do projeto.
        initials:   Iniciais em maiúsculas (ex: "MF").

    Returns:
        Dict do membro ou None se não encontrado.
    """
    client = get_supabase_client()
    if not client:
        return None
    try:
        result = (
            client.table("project_roster")
            .select("*")
            .eq("project_id", project_id)
            .eq("initials", initials.upper())
            .single()
            .execute()
        )
        return result.data
    except Exception as e:
        logger.error("get_roster_member_by_initials(%s, %s): %s", project_id, initials, e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# ROSTER — ESCRITA
# ─────────────────────────────────────────────────────────────────────────────

def upsert_roster_member(project_id: str, member: dict) -> Optional[dict]:
    """
    Cria ou atualiza um membro no roster de um projeto.

    Args:
        project_id: UUID do projeto.
        member: Dict com campos obrigatórios (initials, full_name, color_hex)
                e opcionais (area, name_aliases, project_slug, sort_order, is_active).

    Returns:
        Dict do membro criado/atualizado, ou None em caso de erro.

    Raises:
        ValueError: se campos obrigatórios ausentes ou formato inválido.
    """
    # Validação de campos obrigatórios
    required = ["initials", "full_name", "color_hex"]
    missing = [f for f in required if not member.get(f)]
    if missing:
        raise ValueError(f"Campos obrigatórios ausentes: {missing}")

    # Validação de formato
    initials = member["initials"].upper().strip()
    if not re.match(r"^[A-Z]{1,4}$", initials):
        raise ValueError(f"Iniciais inválidas: '{initials}' — use 1 a 4 letras maiúsculas")

    color_hex = member["color_hex"].lstrip("#").upper()
    if not re.match(r"^[0-9A-F]{6}$", color_hex):
        raise ValueError(f"Cor inválida: '{color_hex}' — use hex de 6 caracteres sem #")

    client = get_supabase_client()
    if not client:
        return None

    payload = {
        "project_id":   project_id,
        "initials":     initials,
        "full_name":    member["full_name"].strip(),
        "area":         member.get("area", "").strip() or None,
        "color_hex":    color_hex,
        "name_aliases": member.get("name_aliases") or [],
        "project_slug": member.get("project_slug") or None,
        "sort_order":   member.get("sort_order", 0),
        "is_active":    member.get("is_active", True),
    }

    try:
        result = (
            client.table("project_roster")
            .upsert(payload, on_conflict="project_id,initials")
            .execute()
        )
        return result.data[0] if result.data else None
    except Exception as e:
        logger.error("upsert_roster_member(%s, %s): %s", project_id, initials, e)
        return None


def deactivate_roster_member(roster_id: str) -> bool:
    """
    Desativa (soft delete) um membro do roster.
    Membros desativados não aparecem nos chips da ata, mas preservam
    o vínculo histórico com meeting_participants.

    Returns:
        True se bem-sucedido, False em caso de erro.
    """
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.table("project_roster").update({"is_active": False}).eq("id", roster_id).execute()
        return True
    except Exception as e:
        logger.error("deactivate_roster_member(%s): %s", roster_id, e)
        return False


def reorder_roster(project_id: str, ordered_ids: list[str]) -> bool:
    """
    Reordena os membros do roster de um projeto.

    Args:
        project_id:  UUID do projeto (para validação).
        ordered_ids: Lista de roster_ids na nova ordem desejada.

    Returns:
        True se bem-sucedido, False em caso de erro.
    """
    client = get_supabase_client()
    if not client:
        return False
    try:
        for i, roster_id in enumerate(ordered_ids):
            client.table("project_roster").update({"sort_order": i}).eq("id", roster_id).execute()
        return True
    except Exception as e:
        logger.error("reorder_roster(%s): %s", project_id, e)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# PARTICIPANTES DE REUNIÃO — LEITURA
# ─────────────────────────────────────────────────────────────────────────────

def get_meeting_participants(meeting_id: str) -> list[dict]:
    """
    Retorna participantes confirmados de uma reunião com dados completos do roster.
    Usa a função SQL get_meeting_participants_full() para evitar múltiplos round-trips.

    Returns:
        Lista de dicts com campos do roster + confirmed + source.
        Retorna [] se não houver participantes ou em caso de erro.
    """
    client = get_supabase_client()
    if not client:
        return []
    try:
        result = client.rpc(
            "get_meeting_participants_full",
            {"p_meeting_id": meeting_id}
        ).execute()
        return result.data or []
    except Exception as e:
        logger.error("get_meeting_participants(%s): %s", meeting_id, e)
        return []


def get_meetings_without_participants(project_id: str) -> list[dict]:
    """
    Retorna reuniões do projeto que não têm nenhum participante registrado.
    Útil para identificar reuniões que precisam de backfill.

    Returns:
        Lista de dicts com id, title, meeting_date das reuniões sem participantes.
    """
    client = get_supabase_client()
    if not client:
        return []
    try:
        # Busca todos os meeting_ids do projeto que têm participantes
        mp_result = (
            client.table("meeting_participants")
            .select("meeting_id")
            .execute()
        )
        ids_with_participants = {r["meeting_id"] for r in (mp_result.data or [])}

        # Busca todas as reuniões do projeto
        meetings_result = (
            client.table("meetings")
            .select("id, title, meeting_date")
            .eq("project_id", project_id)
            .order("meeting_date", desc=True)
            .execute()
        )
        meetings = meetings_result.data or []

        return [m for m in meetings if m["id"] not in ids_with_participants]
    except Exception as e:
        logger.error("get_meetings_without_participants(%s): %s", project_id, e)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# PARTICIPANTES DE REUNIÃO — ESCRITA
# ─────────────────────────────────────────────────────────────────────────────

def save_meeting_participants(
    meeting_id: str,
    roster_ids: list[str],
    source: str = "auto",
    confirmed: bool = True,
) -> bool:
    """
    Persiste a lista de participantes de uma reunião.
    Operação idempotente: faz upsert — não duplica se já existir.

    Args:
        meeting_id: UUID da reunião.
        roster_ids: Lista de UUIDs do project_roster.
        source:     'auto' (AgentMinutes), 'manual' (operador), 'import' (backfill).
        confirmed:  Se True, marca como presença confirmada.

    Returns:
        True se bem-sucedido, False em caso de erro.
    """
    if not roster_ids:
        return True  # nada a fazer

    client = get_supabase_client()
    if not client:
        return False

    payload = [
        {
            "meeting_id": meeting_id,
            "roster_id":  rid,
            "confirmed":  confirmed,
            "source":     source,
        }
        for rid in roster_ids
    ]

    try:
        client.table("meeting_participants").upsert(
            payload,
            on_conflict="meeting_id,roster_id"
        ).execute()
        return True
    except Exception as e:
        logger.error("save_meeting_participants(%s): %s", meeting_id, e)
        return False


def remove_meeting_participant(meeting_id: str, roster_id: str) -> bool:
    """
    Remove um participante específico de uma reunião.

    Returns:
        True se bem-sucedido, False em caso de erro.
    """
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.table("meeting_participants").delete().match(
            {"meeting_id": meeting_id, "roster_id": roster_id}
        ).execute()
        return True
    except Exception as e:
        logger.error("remove_meeting_participant(%s, %s): %s", meeting_id, roster_id, e)
        return False


def clear_meeting_participants(meeting_id: str) -> bool:
    """
    Remove todos os participantes de uma reunião.
    Usado antes de re-inferir participantes (ex: após re-processar transcrição).

    Returns:
        True se bem-sucedido, False em caso de erro.
    """
    client = get_supabase_client()
    if not client:
        return False
    try:
        client.table("meeting_participants").delete().eq("meeting_id", meeting_id).execute()
        return True
    except Exception as e:
        logger.error("clear_meeting_participants(%s): %s", meeting_id, e)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# MATCHING: nome da transcrição → roster
# ─────────────────────────────────────────────────────────────────────────────

def match_participant_to_roster(
    name: str,
    roster: list[dict],
) -> Optional[dict]:
    """
    Tenta casar um nome extraído da transcrição com um membro do roster.

    Estratégia em três passes (ordem de precedência):
        1. Match exato em full_name (case-insensitive)
        2. Match exato em initials (case-insensitive)
        3. Match parcial em name_aliases (substring em ambas as direções)

    Args:
        name:   Nome como aparece na transcrição (ex: "Fátima", "MF", "João Luís").
        roster: Lista de dicts do roster (output de get_project_roster).

    Returns:
        Dict do membro do roster, ou None se nenhum match encontrado.
    """
    if not name or not roster:
        return None

    name_lower = name.lower().strip()

    # Passe 1: full_name exato
    for member in roster:
        if member["full_name"].lower() == name_lower:
            return member

    # Passe 2: iniciais exatas
    for member in roster:
        if member["initials"].lower() == name_lower:
            return member

    # Passe 3: aliases (substring bidirecional)
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
    """
    Infere participantes a partir de nomes extraídos da transcrição,
    cruza com o roster do projeto, persiste o resultado e retorna
    a lista de participantes resolvidos (incluindo temporários).

    Participantes sem correspondência no roster recebem um registro
    temporário com cor FALLBACK_COLOR — não são persistidos no roster.

    Args:
        names_from_transcript: Nomes como aparecem na transcrição.
        project_id:            UUID do projeto.
        meeting_id:            UUID da reunião.

    Returns:
        Lista de dicts prontos para o gerador de ata (initials, full_name,
        area, color_hex). Ordenados por sort_order do roster; temporários
        vão ao final.
    """
    roster = get_project_roster(project_id)
    resolved: list[dict] = []
    unmatched_names: list[str] = []
    matched_roster_ids: list[str] = []

    for name in names_from_transcript:
        member = match_participant_to_roster(name, roster)
        if member:
            # Evitar duplicatas (mesmo nome mencionado duas vezes)
            if member["id"] not in matched_roster_ids:
                matched_roster_ids.append(member["id"])
                resolved.append(member)
        else:
            unmatched_names.append(name)

    # Persistir participantes confirmados do roster
    if matched_roster_ids:
        save_meeting_participants(meeting_id, matched_roster_ids, source="auto")

    # Construir registros temporários para não-identificados
    for name in unmatched_names:
        initials = _generate_initials(name)
        resolved.append({
            "id":           None,            # temporário — não persiste no roster
            "initials":     initials,
            "full_name":    name,
            "area":         None,
            "color_hex":    FALLBACK_COLOR,
            "name_aliases": [],
            "sort_order":   999,             # vai ao final
            "confirmed":    True,
            "source":       "auto",
        })
        logger.warning(
            "infer_participants: nome '%s' não encontrado no roster do projeto %s — "
            "criando participante temporário com iniciais '%s'",
            name, project_id, initials
        )

    # Ordenar: membros do roster primeiro (por sort_order), temporários ao final
    resolved.sort(key=lambda p: (p.get("sort_order") or 999, p["initials"]))
    return resolved


def _generate_initials(full_name: str) -> str:
    """
    Gera iniciais a partir de um nome completo.
    Ex: "Ana Beatriz Souza" → "AB"
        "Carlos" → "CA"

    Returns:
        String de 2 letras maiúsculas.
    """
    parts = full_name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    elif len(parts) == 1 and len(parts[0]) >= 2:
        return parts[0][:2].upper()
    return "??"


# ─────────────────────────────────────────────────────────────────────────────
# ANALYTICS: queries cruzadas roster × reuniões
# ─────────────────────────────────────────────────────────────────────────────

def get_participant_meeting_history(
    roster_id: str,
    project_id: str,
) -> list[dict]:
    """
    Retorna todas as reuniões em que um participante esteve presente.

    Returns:
        Lista de dicts com id, title, meeting_date, confirmed.
    """
    client = get_supabase_client()
    if not client:
        return []
    try:
        result = (
            client.table("meeting_participants")
            .select("confirmed, source, meetings(id, title, meeting_date)")
            .eq("roster_id", roster_id)
            .execute()
        )
        rows = result.data or []
        return [
            {
                "id":           r["meetings"]["id"],
                "title":        r["meetings"]["title"],
                "meeting_date": r["meetings"]["meeting_date"],
                "confirmed":    r["confirmed"],
                "source":       r["source"],
            }
            for r in rows
            if r.get("meetings")
        ]
    except Exception as e:
        logger.error("get_participant_meeting_history(%s): %s", roster_id, e)
        return []


def get_roster_attendance_summary(project_id: str) -> list[dict]:
    """
    Retorna um resumo de presença para cada membro do roster:
    quantas reuniões do projeto cada pessoa participou.

    Returns:
        Lista de dicts com initials, full_name, area, color_hex,
        total_meetings, confirmed_meetings.
    """
    client = get_supabase_client()
    if not client:
        return []
    try:
        roster = get_project_roster(project_id)
        if not roster:
            return []

        # Contar reuniões por roster_id via meeting_participants
        mp_result = (
            client.table("meeting_participants")
            .select("roster_id, confirmed")
            .execute()
        )
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
        for member in roster:
            c = counts.get(member["id"], {"total": 0, "confirmed": 0})
            summary.append({
                "roster_id":          member["id"],
                "initials":           member["initials"],
                "full_name":          member["full_name"],
                "area":               member["area"],
                "color_hex":          member["color_hex"],
                "total_meetings":     c["total"],
                "confirmed_meetings": c["confirmed"],
            })

        summary.sort(key=lambda x: x["confirmed_meetings"], reverse=True)
        return summary
    except Exception as e:
        logger.error("get_roster_attendance_summary(%s): %s", project_id, e)
        return []
