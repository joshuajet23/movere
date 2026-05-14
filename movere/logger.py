"""Daily log — write and read progress entries against personal projects."""

import json
from datetime import date, timedelta
from pathlib import Path

from . import config
from . import projects as proj_store


def _log_dir() -> Path:
    d = config.data_dir() / "log"
    d.mkdir(exist_ok=True)
    return d


def _log_path(for_date: date) -> Path:
    return _log_dir() / f"{for_date.isoformat()}.json"


def _load(for_date: date) -> dict:
    p = _log_path(for_date)
    if not p.exists():
        return {"date": for_date.isoformat(), "entries": []}
    return json.loads(p.read_text())


def _save(data: dict, for_date: date) -> None:
    _log_path(for_date).write_text(json.dumps(data, indent=2))


def add_entry(note: str, project_id: str | None = None, for_date: date | None = None) -> dict:
    today = for_date or date.today()
    data = _load(today)

    if not project_id:
        project_id = proj_store.match(note)

    from datetime import datetime
    entry = {
        "project": project_id,
        "note": note,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    data["entries"].append(entry)
    _save(data, today)
    return entry


def get_entries(for_date: date) -> list[dict]:
    return _load(for_date)["entries"]


def status_today() -> dict:
    today = date.today()
    entries = get_entries(today)
    projects = proj_store.all_active()

    logged_ids = {e["project"] for e in entries if e.get("project")}
    unlogged = [p for p in projects if p["id"] not in logged_ids]

    return {
        "date": today.isoformat(),
        "entries": entries,
        "projects": projects,
        "unlogged": unlogged,
    }


def week_history(days: int = 7) -> list[dict]:
    """Return a list of daily summaries for the past N days, most recent first."""
    today = date.today()
    history = []
    for i in range(days):
        d = today - timedelta(days=i)
        entries = get_entries(d)
        by_project: dict[str, list[str]] = {}
        for e in entries:
            pid = e.get("project") or "general"
            by_project.setdefault(pid, []).append(e["note"])
        history.append({
            "date": d.isoformat(),
            "day": d.strftime("%A"),
            "entries": entries,
            "by_project": by_project,
        })
    return history


def yesterday_summary() -> dict:
    yesterday = date.today() - timedelta(days=1)
    entries = get_entries(yesterday)
    projects = proj_store.all_active()

    by_project: dict[str, list[str]] = {}
    for e in entries:
        pid = e.get("project") or "general"
        by_project.setdefault(pid, []).append(e["note"])

    logged_ids = set(by_project.keys())
    missed = [p for p in projects if p["id"] not in logged_ids]

    return {
        "date": yesterday.isoformat(),
        "by_project": by_project,
        "missed": missed,
        "total_entries": len(entries),
    }
