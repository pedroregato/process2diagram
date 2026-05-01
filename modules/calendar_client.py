# modules/calendar_client.py
# ─────────────────────────────────────────────────────────────────────────────
# Google Calendar API v3 client for the P2D Assistente.
#
# Credentials are read from st.secrets["google_calendar"] when available
# (Streamlit Cloud / local dev with secrets.toml), falling back to the
# local file used by the MCP server in pure-local mode.
#
# Secrets expected:
#   [google_calendar]
#   calendar_id      = "...@group.calendar.google.com"
#   credentials_json = '{"type": "service_account", ...}'   # full JSON as string
#
# Local fallback (dev without secrets.toml):
#   mcp/google_console/*.json           ← first JSON file found
#   mcp/google_console/.google-calendar ← calendar ID
# ─────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

_SP = ZoneInfo("America/Sao_Paulo")
_SCOPES = ["https://www.googleapis.com/auth/calendar"]

# ── Credential loading ────────────────────────────────────────────────────────

def _load_credentials_info() -> dict | None:
    """Return service-account credentials dict or None if unavailable."""
    # 1) Streamlit secrets
    try:
        import streamlit as st
        raw = st.secrets["google_calendar"]["credentials_json"]
        return json.loads(raw) if isinstance(raw, str) else dict(raw)
    except Exception:
        pass

    # 2) Local file fallback (dev)
    try:
        base = Path(__file__).parent.parent / "mcp" / "google_console"
        for f in base.glob("*.json"):
            return json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        pass

    return None


def _load_calendar_id() -> str:
    """Return the calendar ID or 'primary' as fallback."""
    # 1) Streamlit secrets
    try:
        import streamlit as st
        return st.secrets["google_calendar"]["calendar_id"]
    except Exception:
        pass

    # 2) Local file fallback
    try:
        cal_file = Path(__file__).parent.parent / "mcp" / "google_console" / ".google-calendar"
        for line in cal_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("id-da-agenda="):
                return line.split("=", 1)[1].strip()
    except Exception:
        pass

    return "primary"


def calendar_configured() -> bool:
    """True when credentials are available (secrets or local file)."""
    return _load_credentials_info() is not None


def _get_service():
    """Build an authenticated Google Calendar service, or raise RuntimeError."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ImportError:
        raise RuntimeError(
            "Dependências Google Calendar não instaladas. "
            "Execute: pip install -r mcp/requirements.txt"
        )

    info = _load_credentials_info()
    if info is None:
        raise RuntimeError(
            "Credenciais do Google Calendar não encontradas. "
            "Configure st.secrets[google_calendar][credentials_json] ou "
            "coloque o arquivo JSON em mcp/google_console/."
        )

    creds = service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dt(value: str) -> dict:
    """Convert ISO datetime string to Google Calendar dateTime dict.

    Naive datetimes (no tz) are treated as America/Sao_Paulo.
    """
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_SP)
        return {"dateTime": dt.isoformat(), "timeZone": "America/Sao_Paulo"}
    except ValueError:
        return {"date": value}


def _event_summary(event: dict) -> dict:
    """Extract the most useful fields from a raw event dict."""
    start = event.get("start", {})
    end   = event.get("end", {})
    return {
        "id":          event.get("id"),
        "summary":     event.get("summary", "(sem título)"),
        "description": event.get("description", ""),
        "location":    event.get("location", ""),
        "start":       start.get("dateTime") or start.get("date"),
        "end":         end.get("dateTime") or end.get("date"),
        "status":      event.get("status"),
        "htmlLink":    event.get("htmlLink"),
        "attendees": [
            {"email": a.get("email"), "responseStatus": a.get("responseStatus")}
            for a in event.get("attendees", [])
        ],
        "creator":     event.get("creator", {}).get("email"),
        "organizer":   event.get("organizer", {}).get("email"),
    }


def _format_event_text(ev: dict) -> str:
    """Format a single event summary dict as a human-readable text block."""
    lines = [
        f"  ID:       {ev['id']}",
        f"  Título:   {ev['summary']}",
        f"  Início:   {ev['start']}",
        f"  Fim:      {ev['end']}",
    ]
    if ev.get("location"):
        lines.append(f"  Local:    {ev['location']}")
    if ev.get("description"):
        desc = ev["description"][:200] + ("…" if len(ev["description"]) > 200 else "")
        lines.append(f"  Descrição: {desc}")
    if ev.get("attendees"):
        emails = ", ".join(a["email"] for a in ev["attendees"] if a.get("email"))
        if emails:
            lines.append(f"  Participantes: {emails}")
    if ev.get("htmlLink"):
        lines.append(f"  Link:     {ev['htmlLink']}")
    return "\n".join(lines)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Public API ────────────────────────────────────────────────────────────────

def list_events(
    max_results: int = 10,
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    query: Optional[str] = None,
    calendar_id: Optional[str] = None,
) -> str:
    """List upcoming calendar events as formatted text."""
    try:
        svc    = _get_service()
        cal_id = calendar_id or _load_calendar_id()
        t_min  = time_min or _now_iso()

        params: dict = {
            "calendarId":   cal_id,
            "maxResults":   min(max_results, 50),
            "singleEvents": True,
            "orderBy":      "startTime",
            "timeMin":      t_min,
        }
        if time_max:
            params["timeMax"] = time_max
        if query:
            params["q"] = query

        result = svc.events().list(**params).execute()
        events = [_event_summary(e) for e in result.get("items", [])]

        if not events:
            return "Nenhum evento encontrado no período especificado."

        lines = [f"Eventos do Google Calendar ({len(events)} encontrado(s)):\n"]
        for i, ev in enumerate(events, 1):
            lines.append(f"[{i}]")
            lines.append(_format_event_text(ev))
            lines.append("")
        return "\n".join(lines)

    except RuntimeError as exc:
        return f"❌ Configuração: {exc}"
    except Exception as exc:
        return f"❌ Erro ao listar eventos: {exc}"


def get_event(event_id: str, calendar_id: Optional[str] = None) -> str:
    """Return full details of a single calendar event as formatted text."""
    try:
        svc    = _get_service()
        cal_id = calendar_id or _load_calendar_id()
        event  = svc.events().get(calendarId=cal_id, eventId=event_id).execute()
        ev     = _event_summary(event)
        return f"Evento encontrado:\n{_format_event_text(ev)}"
    except RuntimeError as exc:
        return f"❌ Configuração: {exc}"
    except Exception as exc:
        return f"❌ Erro ao buscar evento '{event_id}': {exc}"


def create_event(
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: Optional[str] = None,
    location: Optional[str] = None,
    attendees: Optional[str] = None,
    calendar_id: Optional[str] = None,
) -> str:
    """Create a new Google Calendar event and return confirmation text."""
    try:
        svc    = _get_service()
        cal_id = calendar_id or _load_calendar_id()

        body: dict = {
            "summary": summary,
            "start":   _dt(start_datetime),
            "end":     _dt(end_datetime),
        }
        if description:
            body["description"] = description
        if location:
            body["location"] = location
        if attendees:
            body["attendees"] = [
                {"email": e.strip()} for e in attendees.split(",") if e.strip()
            ]

        event = (
            svc.events()
            .insert(calendarId=cal_id, body=body, sendUpdates="all")
            .execute()
        )
        ev = _event_summary(event)
        return (
            f"✅ Evento criado com sucesso!\n{_format_event_text(ev)}"
        )
    except RuntimeError as exc:
        return f"❌ Configuração: {exc}"
    except Exception as exc:
        return f"❌ Erro ao criar evento: {exc}"


def suggest_time(
    duration_minutes: int = 60,
    attendees: Optional[str] = None,
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    max_suggestions: int = 3,
) -> str:
    """Find available time slots via freebusy API, returned as formatted text."""
    try:
        svc  = _get_service()
        now  = datetime.now(timezone.utc)
        t_min = datetime.fromisoformat(time_min) if time_min else now
        t_max = (
            datetime.fromisoformat(time_max)
            if time_max
            else now + timedelta(days=7)
        )
        if t_min.tzinfo is None:
            t_min = t_min.replace(tzinfo=timezone.utc)
        if t_max.tzinfo is None:
            t_max = t_max.replace(tzinfo=timezone.utc)

        items = []
        if attendees:
            for email in attendees.split(","):
                email = email.strip()
                if email:
                    items.append({"id": email})
        if not items:
            items.append({"id": _load_calendar_id()})

        body = {
            "timeMin": t_min.isoformat(),
            "timeMax": t_max.isoformat(),
            "items":   items,
        }
        result = svc.freebusy().query(body=body).execute()

        # Collect all busy intervals
        busy: list[tuple[datetime, datetime]] = []
        for cal_data in result.get("calendars", {}).values():
            for slot in cal_data.get("busy", []):
                busy.append((
                    datetime.fromisoformat(slot["start"]),
                    datetime.fromisoformat(slot["end"]),
                ))
        busy.sort(key=lambda x: x[0])

        # Walk window in 30-min steps
        duration = timedelta(minutes=duration_minutes)
        step     = timedelta(minutes=30)
        slots    = []
        cursor   = t_min

        while cursor + duration <= t_max and len(slots) < max_suggestions:
            slot_end = cursor + duration
            conflict = any(
                not (slot_end <= b_start or cursor >= b_end)
                for b_start, b_end in busy
            )
            if not conflict:
                # Convert to Sao Paulo for display
                start_sp = cursor.astimezone(_SP)
                end_sp   = slot_end.astimezone(_SP)
                slots.append((start_sp, end_sp))
                cursor = slot_end
            else:
                cursor += step

        if not slots:
            return (
                f"Nenhum horário livre encontrado para {duration_minutes} minutos "
                f"no período consultado."
            )

        lines = [
            f"Horários disponíveis para {duration_minutes} min "
            f"({len(slots)} sugestão(ões)):\n"
        ]
        for i, (s, e) in enumerate(slots, 1):
            fmt = "%d/%m/%Y %H:%M"
            lines.append(
                f"  [{i}] {s.strftime(fmt)} → {e.strftime(fmt)} (Brasília)"
            )
        lines.append(
            "\nPara agendar, diga: 'Crie um evento no horário [N]' "
            "com o título e participantes desejados."
        )
        return "\n".join(lines)

    except RuntimeError as exc:
        return f"❌ Configuração: {exc}"
    except Exception as exc:
        return f"❌ Erro ao consultar disponibilidade: {exc}"


def schedule_action_items(
    action_items_text: str,
    meeting_title: str,
    default_date: str,
    duration_minutes: int = 30,
    calendar_id: Optional[str] = None,
) -> str:
    """Create one calendar event per action item that has a responsible person.

    action_items_text: raw text of the action items section from minutes_md
    default_date:      ISO date/datetime used for items without explicit deadlines
    """
    import re

    lines = [
        l.strip() for l in action_items_text.splitlines()
        if l.strip() and l.strip()[0:1] in ("-", "•", "*", "|") or
           (l.strip() and l.strip()[0:1].isdigit() and "." in l.strip()[:3])
    ]
    if not lines:
        return "Nenhum item de ação identificado no texto fornecido."

    # Parse default start datetime
    try:
        default_dt = datetime.fromisoformat(default_date)
        if default_dt.tzinfo is None:
            default_dt = default_dt.replace(tzinfo=_SP)
    except ValueError:
        return f"❌ Data padrão inválida: '{default_date}'. Use formato ISO (ex: 2026-05-20T10:00:00)."

    default_end_dt = (default_dt + timedelta(minutes=duration_minutes)).isoformat()

    created: list[str] = []
    skipped: list[str] = []

    # Regex to detect responsavel (e.g. "Resp: João" or "João" after "-")
    _RESP_RE = re.compile(
        r'\b(?:resp(?:onsável)?[:\s]+|por:\s*)([A-ZÁÉÍÓÚÃÕÂÊÔÜÇ][a-záéíóúãõâêôüç]+)',
        re.IGNORECASE,
    )

    for raw in lines:
        text = re.sub(r'^[-•*|]\s*|\d+\.\s*', '', raw).strip()
        if len(text) < 5:
            continue

        resp_match = _RESP_RE.search(text)
        responsible = resp_match.group(1) if resp_match else None

        description = f"Reunião de origem: {meeting_title}\n\nItem de ação:\n{text}"
        summary     = (
            f"[Ação] {text[:60]}{'…' if len(text) > 60 else ''}"
            if not responsible
            else f"[Ação/{responsible}] {text[:55]}{'…' if len(text) > 55 else ''}"
        )

        result = create_event(
            summary        = summary,
            start_datetime = default_dt.isoformat(),
            end_datetime   = default_end_dt,
            description    = description,
            calendar_id    = calendar_id,
        )
        if result.startswith("✅"):
            created.append(f"  ✅ {text[:80]}")
        else:
            skipped.append(f"  ❌ {text[:80]} — {result}")

    lines_out = [
        f"Agendamento de itens de ação — {meeting_title}",
        f"Data base: {default_dt.strftime('%d/%m/%Y %H:%M')} (Brasília)",
        f"Total identificado: {len(lines)} | Criados: {len(created)} | Erros: {len(skipped)}",
        "",
    ]
    if created:
        lines_out.append("Criados:")
        lines_out.extend(created)
    if skipped:
        lines_out.append("\nErros:")
        lines_out.extend(skipped)
    return "\n".join(lines_out)
