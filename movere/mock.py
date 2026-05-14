"""Stub data for --mock runs — lets you test the full pipeline without live API calls."""

from datetime import date, timedelta


def fitness() -> dict:
    return {
        "date": (date.today() - timedelta(days=1)).isoformat(),
        "steps": 9_842,
        "sleep_hours": 7.2,
        "hrv": 48,
        "body_battery": 74,
        "activity": "Running (5.3 km)",
    }


def screentime() -> dict:
    return {
        "date": (date.today() - timedelta(days=1)).isoformat(),
        "total_minutes": 247.0,
        "total_hours": 4.1,
        "phone_minutes": 162.0,
        "mac_minutes": 85.0,
        "goal_minutes": 180,
        "over_goal": True,
        "devices": {
            "Joshua's iPhone": {
                "total_minutes": 162.0,
                "top_apps": [
                    {"name": "Safari", "minutes": 48.0},
                    {"name": "Instagram", "minutes": 34.0},
                    {"name": "Messages", "minutes": 28.0},
                    {"name": "Reddit", "minutes": 22.0},
                    {"name": "Mail", "minutes": 14.0},
                ],
                "by_category": {"browser": 48.0, "social": 56.0, "communication": 42.0, "other": 16.0},
            },
            "Joshua's MacBook Pro": {
                "total_minutes": 85.0,
                "top_apps": [
                    {"name": "Arc", "minutes": 41.0},
                    {"name": "Code", "minutes": 22.0},
                    {"name": "Slack", "minutes": 14.0},
                    {"name": "Terminal", "minutes": 8.0},
                ],
                "by_category": {"browser": 41.0, "productivity": 30.0, "communication": 14.0},
            },
        },
        "error": None,
    }


def yesterday_log() -> dict:
    return {
        "date": (date.today() - timedelta(days=1)).isoformat(),
        "by_project": {
            "reading": ["read 6 pages of Atomic Habits"],
            "career-applications": ["applied to Acme Corp", "sent follow-up to recruiter at TechCorp"],
        },
        "missed": [
            {"id": "learn-spanish", "name": "Learn Spanish", "goal": "30 min/day"},
        ],
        "total_entries": 3,
    }


def calendar() -> dict:
    tomorrow = (date.today() + timedelta(days=1)).strftime("%a %b %-d, %-I:%M %p")
    in_three = (date.today() + timedelta(days=3)).strftime("%a %b %-d, %-I:%M %p")
    in_five = (date.today() + timedelta(days=5)).strftime("%a %b %-d (all day)")
    return {
        "career": {
            "events": [
                {"title": "Phone screen — Acme Corp", "datetime": tomorrow},
                {"title": "Follow-up: send portfolio to recruiter", "datetime": in_three},
            ]
        },
        "mentoring": {
            "events": [
                {"title": "Mentoring session — weekly check-in", "datetime": in_five},
            ]
        },
    }
