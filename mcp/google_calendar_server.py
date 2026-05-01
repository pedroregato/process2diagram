"""
MCP Server — Google Calendar
Exposes Google Calendar operations via a Service Account.
Server name: claude_ai_Google_Calendar
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# sys.path fix — prevent the local 'mcp/' directory from shadowing the
# installed 'mcp' PyPI package when the server is run from the project root.
# ---------------------------------------------------------------------------
import os as _os
import sys as _sys

_proj_root = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_sys.path = [
    p for p in _sys.path
    if _os.path.normcase(_os.path.abspath(p)) != _os.path.normcase(_proj_root)
    and p not in ("", ".")
]
# ---------------------------------------------------------------------------

import json
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mcp.server.fastmcp import FastMCP

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_BASE = Path(__file__).parent
_CREDS_FILE = _BASE / "google_console" / "process2diagram-a7aa3604e7aa.json"
_CAL_FILE = _BASE / "google_console" / ".google-calendar"

_SCOPES = ["https://www.googleapis.com/auth/calendar"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _calendar_id() -> str:
    """Read calendar ID from .google-calendar file."""
    for line in _CAL_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("id-da-agenda="):
            return line.split("=", 1)[1].strip()
    return "primary"


def _service():
    """Build authenticated Google Calendar service."""
    creds = service_account.Credentials.from_service_account_file(
        str(_CREDS_FILE), scopes=_SCOPES
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


CALENDAR_ID = _calendar_id()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_SP = ZoneInfo("America/Sao_Paulo")


def _dt(value: str) -> dict:
    """Convert ISO datetime string to Google Calendar dateTime dict."""
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=_SP)
        return {"dateTime": dt.isoformat(), "timeZone": "America/Sao_Paulo"}
    except ValueError:
        # Treat as all-day date
        return {"date": value}


def _event_summary(event: dict) -> dict:
    """Extract the most useful fields from a raw event dict."""
    start = event.get("start", {})
    end = event.get("end", {})
    return {
        "id": event.get("id"),
        "summary": event.get("summary", "(sem título)"),
        "description": event.get("description", ""),
        "location": event.get("location", ""),
        "start": start.get("dateTime") or start.get("date"),
        "end": end.get("dateTime") or end.get("date"),
        "status": event.get("status"),
        "htmlLink": event.get("htmlLink"),
        "attendees": [
            {"email": a.get("email"), "responseStatus": a.get("responseStatus")}
            for a in event.get("attendees", [])
        ],
        "creator": event.get("creator", {}).get("email"),
        "organizer": event.get("organizer", {}).get("email"),
    }


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP("claude_ai_Google_Calendar")


# ---------------------------------------------------------------------------
# Tool: list_events
# ---------------------------------------------------------------------------

@mcp.tool()
def list_events(
    max_results: int = 10,
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    query: Optional[str] = None,
    calendar_id: Optional[str] = None,
) -> str:
    """List upcoming events from the Google Calendar.

    Args:
        max_results: Maximum number of events to return (default 10, max 250).
        time_min: Lower bound for event start time (ISO 8601). Defaults to now.
        time_max: Upper bound for event start time (ISO 8601). Optional.
        query: Free-text search query to filter events.
        calendar_id: Calendar ID to query. Defaults to the project calendar.

    Returns:
        JSON list of events with id, summary, start, end, location, attendees.
    """
    cal_id = calendar_id or CALENDAR_ID
    t_min = time_min or _now_iso()

    params: dict = {
        "calendarId": cal_id,
        "maxResults": min(max_results, 250),
        "singleEvents": True,
        "orderBy": "startTime",
        "timeMin": t_min,
    }
    if time_max:
        params["timeMax"] = time_max
    if query:
        params["q"] = query

    try:
        result = _service().events().list(**params).execute()
        events = [_event_summary(e) for e in result.get("items", [])]
        return json.dumps(events, ensure_ascii=False, indent=2)
    except HttpError as exc:
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Tool: get_event
# ---------------------------------------------------------------------------

@mcp.tool()
def get_event(
    event_id: str,
    calendar_id: Optional[str] = None,
) -> str:
    """Get full details of a single calendar event.

    Args:
        event_id: The event ID (from list_events).
        calendar_id: Calendar ID. Defaults to the project calendar.

    Returns:
        JSON object with full event details.
    """
    cal_id = calendar_id or CALENDAR_ID
    try:
        event = _service().events().get(calendarId=cal_id, eventId=event_id).execute()
        return json.dumps(_event_summary(event), ensure_ascii=False, indent=2)
    except HttpError as exc:
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Tool: create_event
# ---------------------------------------------------------------------------

@mcp.tool()
def create_event(
    summary: str,
    start_datetime: str,
    end_datetime: str,
    description: Optional[str] = None,
    location: Optional[str] = None,
    attendees: Optional[str] = None,
    calendar_id: Optional[str] = None,
) -> str:
    """Create a new event on the Google Calendar.

    Args:
        summary: Event title.
        start_datetime: Start date/time in ISO 8601 (e.g. "2026-05-10T14:00:00").
        end_datetime: End date/time in ISO 8601 (e.g. "2026-05-10T15:00:00").
        description: Optional event description / agenda.
        location: Optional location or Meet link.
        attendees: Optional comma-separated list of attendee email addresses.
        calendar_id: Calendar ID. Defaults to the project calendar.

    Returns:
        JSON object with the created event id and htmlLink.
    """
    cal_id = calendar_id or CALENDAR_ID

    body: dict = {
        "summary": summary,
        "start": _dt(start_datetime),
        "end": _dt(end_datetime),
    }
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    if attendees:
        body["attendees"] = [
            {"email": e.strip()} for e in attendees.split(",") if e.strip()
        ]

    try:
        event = (
            _service()
            .events()
            .insert(calendarId=cal_id, body=body, sendUpdates="all")
            .execute()
        )
        return json.dumps(
            {"id": event["id"], "htmlLink": event.get("htmlLink"), "summary": event.get("summary")},
            ensure_ascii=False,
        )
    except HttpError as exc:
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Tool: update_event
# ---------------------------------------------------------------------------

@mcp.tool()
def update_event(
    event_id: str,
    summary: Optional[str] = None,
    start_datetime: Optional[str] = None,
    end_datetime: Optional[str] = None,
    description: Optional[str] = None,
    location: Optional[str] = None,
    calendar_id: Optional[str] = None,
) -> str:
    """Update an existing calendar event (patch — only provided fields are changed).

    Args:
        event_id: The event ID to update.
        summary: New event title (optional).
        start_datetime: New start date/time ISO 8601 (optional).
        end_datetime: New end date/time ISO 8601 (optional).
        description: New description (optional).
        location: New location (optional).
        calendar_id: Calendar ID. Defaults to the project calendar.

    Returns:
        JSON object with updated event id and htmlLink.
    """
    cal_id = calendar_id or CALENDAR_ID

    patch: dict = {}
    if summary is not None:
        patch["summary"] = summary
    if start_datetime is not None:
        patch["start"] = _dt(start_datetime)
    if end_datetime is not None:
        patch["end"] = _dt(end_datetime)
    if description is not None:
        patch["description"] = description
    if location is not None:
        patch["location"] = location

    if not patch:
        return json.dumps({"error": "No fields provided to update."})

    try:
        event = (
            _service()
            .events()
            .patch(calendarId=cal_id, eventId=event_id, body=patch, sendUpdates="all")
            .execute()
        )
        return json.dumps(
            {"id": event["id"], "htmlLink": event.get("htmlLink"), "summary": event.get("summary")},
            ensure_ascii=False,
        )
    except HttpError as exc:
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Tool: delete_event
# ---------------------------------------------------------------------------

@mcp.tool()
def delete_event(
    event_id: str,
    calendar_id: Optional[str] = None,
) -> str:
    """Delete a calendar event.

    Args:
        event_id: The event ID to delete.
        calendar_id: Calendar ID. Defaults to the project calendar.

    Returns:
        JSON confirmation or error.
    """
    cal_id = calendar_id or CALENDAR_ID
    try:
        _service().events().delete(
            calendarId=cal_id, eventId=event_id, sendUpdates="all"
        ).execute()
        return json.dumps({"status": "deleted", "event_id": event_id})
    except HttpError as exc:
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Tool: list_calendars
# ---------------------------------------------------------------------------

@mcp.tool()
def list_calendars() -> str:
    """List all calendars accessible to the service account.

    Returns:
        JSON list of calendars with id, summary, accessRole.
    """
    try:
        result = _service().calendarList().list().execute()
        calendars = [
            {
                "id": c.get("id"),
                "summary": c.get("summary"),
                "accessRole": c.get("accessRole"),
                "primary": c.get("primary", False),
            }
            for c in result.get("items", [])
        ]
        return json.dumps(calendars, ensure_ascii=False, indent=2)
    except HttpError as exc:
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Tool: respond_to_event
# ---------------------------------------------------------------------------

@mcp.tool()
def respond_to_event(
    event_id: str,
    response: str,
    attendee_email: Optional[str] = None,
    calendar_id: Optional[str] = None,
) -> str:
    """Update the RSVP status for an attendee on a calendar event.

    Args:
        event_id: The event ID.
        response: One of "accepted", "declined", "tentative", "needsAction".
        attendee_email: Email of the attendee to update. If omitted, updates
                        the service account's own entry (p2d-calendar-sa@...).
        calendar_id: Calendar ID. Defaults to the project calendar.

    Returns:
        JSON with updated attendee list or error.
    """
    cal_id = calendar_id or CALENDAR_ID
    valid = {"accepted", "declined", "tentative", "needsAction"}
    if response not in valid:
        return json.dumps({"error": f"response must be one of {sorted(valid)}"})

    svc = _service()
    try:
        event = svc.events().get(calendarId=cal_id, eventId=event_id).execute()
    except HttpError as exc:
        return json.dumps({"error": str(exc)})

    attendees = event.get("attendees", [])
    target = attendee_email or "p2d-calendar-sa@process2diagram.iam.gserviceaccount.com"
    updated = False
    for att in attendees:
        if att.get("email") == target:
            att["responseStatus"] = response
            updated = True
            break

    if not updated:
        attendees.append({"email": target, "responseStatus": response})

    try:
        result = svc.events().patch(
            calendarId=cal_id,
            eventId=event_id,
            body={"attendees": attendees},
        ).execute()
        return json.dumps(
            {
                "status": "updated",
                "attendees": [
                    {"email": a.get("email"), "responseStatus": a.get("responseStatus")}
                    for a in result.get("attendees", [])
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    except HttpError as exc:
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Tool: suggest_time
# ---------------------------------------------------------------------------

@mcp.tool()
def suggest_time(
    duration_minutes: int = 60,
    attendees: Optional[str] = None,
    time_min: Optional[str] = None,
    time_max: Optional[str] = None,
    max_suggestions: int = 3,
) -> str:
    """Find available time slots using the Google Calendar freebusy API.

    Args:
        duration_minutes: Required meeting duration in minutes (default 60).
        attendees: Comma-separated email list to check availability for.
                   Defaults to the project calendar.
        time_min: Search window start (ISO 8601). Defaults to now.
        time_max: Search window end (ISO 8601). Defaults to +7 days.
        max_suggestions: Maximum number of free slots to return (default 3).

    Returns:
        JSON list of available slot objects with start and end datetimes.
    """
    now = datetime.now(timezone.utc)
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
        items.append({"id": CALENDAR_ID})

    body = {
        "timeMin": t_min.isoformat(),
        "timeMax": t_max.isoformat(),
        "items": items,
    }

    try:
        result = _service().freebusy().query(body=body).execute()
    except HttpError as exc:
        return json.dumps({"error": str(exc)})

    # Collect all busy intervals
    busy_intervals: list[tuple[datetime, datetime]] = []
    for cal_data in result.get("calendars", {}).values():
        for slot in cal_data.get("busy", []):
            busy_intervals.append(
                (
                    datetime.fromisoformat(slot["start"]),
                    datetime.fromisoformat(slot["end"]),
                )
            )
    busy_intervals.sort(key=lambda x: x[0])

    # Walk the window in 30-min increments and find free slots
    duration = timedelta(minutes=duration_minutes)
    step = timedelta(minutes=30)
    suggestions = []
    cursor = t_min

    while cursor + duration <= t_max and len(suggestions) < max_suggestions:
        slot_end = cursor + duration
        conflict = any(
            not (slot_end <= b_start or cursor >= b_end)
            for b_start, b_end in busy_intervals
        )
        if not conflict:
            suggestions.append(
                {
                    "start": cursor.isoformat(),
                    "end": slot_end.isoformat(),
                    "duration_minutes": duration_minutes,
                }
            )
            cursor = slot_end  # jump past this slot
        else:
            cursor += step

    return json.dumps(suggestions, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
