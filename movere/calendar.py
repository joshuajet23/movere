"""Fetch upcoming Google Calendar events and categorize them by project."""

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from . import config

_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

# Keywords used to route events to projects
_CAREER_KEYWORDS = re.compile(
    r"interview|application|job|career|recruiter|offer|resume|linkedin|networking",
    re.IGNORECASE,
)
_MENTORING_KEYWORDS = re.compile(
    r"mentor|mentee|coaching|1:1|one.on.one|advising|advisor",
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
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), _SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def _format_event(event: dict) -> dict:
    start = event.get("start", {})
    dt_str = start.get("dateTime") or start.get("date", "")
    try:
        if "T" in dt_str:
            dt = datetime.fromisoformat(dt_str)
            formatted = dt.strftime("%a %b %-d, %-I:%M %p")
        else:
            dt = datetime.fromisoformat(dt_str)
            formatted = dt.strftime("%a %b %-d (all day)")
    except ValueError:
        formatted = dt_str

    return {"title": event.get("summary", "(no title)"), "datetime": formatted}


def fetch(cfg: dict, lookahead_days: int = 7) -> dict:
    service = _get_service(cfg)

    now = datetime.now(timezone.utc)
    end = now + timedelta(days=lookahead_days)

    all_events = []
    for cal_id in cfg["google"]["calendar_ids"]:
        result = (
            service.events()
            .list(
                calendarId=cal_id,
                timeMin=now.isoformat(),
                timeMax=end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=50,
            )
            .execute()
        )
        all_events.extend(result.get("items", []))

    career_events, mentoring_events = [], []
    for event in all_events:
        title = event.get("summary", "")
        desc = event.get("description", "") or ""
        text = f"{title} {desc}"
        if _CAREER_KEYWORDS.search(text):
            career_events.append(_format_event(event))
        elif _MENTORING_KEYWORDS.search(text):
            mentoring_events.append(_format_event(event))

    return {
        "career": {"events": career_events},
        "mentoring": {"events": mentoring_events},
    }
