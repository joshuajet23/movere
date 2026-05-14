"""Persist chat context notes for inclusion in the next morning's digest."""

import json
from datetime import datetime, timedelta
from pathlib import Path

from . import config


def _path() -> Path:
    return config.data_dir() / "chat_context.json"


def save(note: str) -> None:
    p = _path()
    data = json.loads(p.read_text()) if p.exists() else {"notes": []}
    data["notes"].append({"note": note, "saved_at": datetime.now().isoformat(timespec="seconds")})
    p.write_text(json.dumps(data, indent=2))


def load_recent(hours: int = 36) -> list[str]:
    """Return notes saved in the past N hours."""
    p = _path()
    if not p.exists():
        return []
    cutoff = datetime.now() - timedelta(hours=hours)
    data = json.loads(p.read_text())
    return [
        n["note"] for n in data.get("notes", [])
        if datetime.fromisoformat(n["saved_at"]) >= cutoff
    ]


def clear() -> None:
    p = _path()
    if p.exists():
        p.write_text(json.dumps({"notes": []}, indent=2))
