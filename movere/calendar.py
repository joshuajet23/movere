"""Fetch and create Google Calendar events, categorized by project."""

import re
from datetime import datetime, timedelta, timezone, date
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from . import config

# Read+write so we can create events from chat
_SCOPES = ["https://www.googleapis.com/auth/calendar"]

_CAREER_KEYWORDS = re.compile(
    r"interview|application|job\b|career|recruiter|offer|resume|linkedin|networking|hiring|cover letter|salary",
    re.IGNORECASE,
)
_MENTORING_KEYWORDS = re.compile(
    r"mentor|mentee|coaching|1:1|one.on.one|advising|advisor|check.in|weekly sync",
    re.IGNORECASE,
)
_FITNESS_KEYWORDS = re.compile(
    r"\brace\b|running|run\b|gym|workout|swim|cycling|bike\b|crossfit|yoga|climb|lifting|training|marathon|5k|10k|half marathon|spartan|triathlon",
    re.IGNORECASE,
)
_PROJECT_KEYWORDS = re.compile(
    r"essay|study|writing|write\b|practice|deep work|focus block|work block|reading block|project time",
    re.IGNORECASE,
)


def _get_service(cfg: dict):
    root = Path(__file__).parent.parent
    token_path = root / cfg["google"]["token_file"]
    creds_path = root / cfg["google"]["credentials_file"]

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), _SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), _SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def _format_event(event: dict) -> dict:
    start = event.get("start", {})
    dt_str = start.get("dateTime") or start.get("date", "")
    all_day = "dateTime" not in start
    try:
        dt = datetime.fromisoformat(dt_str)
        formatted = dt.strftime("%a %b %-d (all day)") if all_day else dt.strftime("%a %b %-d, %-I:%M %p")
    except ValueError:
        formatted = dt_str

    return {
        "title": event.get("summary", "(no title)"),
        "datetime": formatted,
        "all_day": all_day,
        "id": event.get("id"),
    }


def _categorize(event: dict) -> str:
    text = f"{event.get('summary', '')} {event.get('description', '') or ''}"
    if _CAREER_KEYWORDS.search(text):
        return "career"
    if _MENTORING_KEYWORDS.search(text):
        return "mentoring"
    if _FITNESS_KEYWORDS.search(text):
        return "fitness"
    if _PROJECT_KEYWORDS.search(text):
        return "project"
    return "general"


def fetch(cfg: dict, lookahead_days: int = 7) -> dict:
    service = _get_service(cfg)

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    lookahead_end = now + timedelta(days=lookahead_days)

    def _list_events(time_min, time_max):
        all_events = []
        for cal_id in cfg["google"]["calendar_ids"]:
            result = (
                service.events()
                .list(
                    calendarId=cal_id,
                    timeMin=time_min.isoformat(),
                    timeMax=time_max.isoformat(),
                    singleEvents=True,
                    orderBy="startTime",
                    maxResults=50,
                )
                .execute()
            )
            all_events.extend(result.get("items", []))
        return all_events

    today_raw = _list_events(today_start, today_end)
    upcoming_raw = _list_events(today_end, lookahead_end)

    today_events = [_format_event(e) for e in today_raw]

    buckets: dict[str, list] = {"career": [], "mentoring": [], "fitness": [], "project": [], "general": []}
    for event in upcoming_raw:
        cat = _categorize(event)
        buckets[cat].append(_format_event(event))

    return {
        "today": today_events,
        "career": {"events": buckets["career"]},
        "mentoring": {"events": buckets["mentoring"]},
        "fitness": {"events": buckets["fitness"]},
        "project": {"events": buckets["project"]},
        "general": {"events": buckets["general"]},
    }


def create_event(cfg: dict, title: str, event_date: str, time: str | None = None,
                 duration_minutes: int = 60, description: str = "") -> dict:
    """Create a Google Calendar event. event_date is YYYY-MM-DD, time is HH:MM (24h) or None for all-day."""
    service = _get_service(cfg)
    cal_id = cfg["google"]["calendar_ids"][0]

    if time:
        start_dt = datetime.fromisoformat(f"{event_date}T{time}:00")
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        event_body = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start_dt.isoformat(), "timeZone": cfg["schedule"]["timezone"]},
            "end": {"dateTime": end_dt.isoformat(), "timeZone": cfg["schedule"]["timezone"]},
        }
    else:
        event_body = {
            "summary": title,
            "description": description,
            "start": {"date": event_date},
            "end": {"date": event_date},
        }

    created = service.events().insert(calendarId=cal_id, body=event_body).execute()
    return {"id": created.get("id"), "title": title, "date": event_date, "time": time}
