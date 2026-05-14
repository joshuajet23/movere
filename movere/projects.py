"""Manage personal projects — the Brian Little layer."""

import json
import re
from datetime import date
from pathlib import Path

from . import config


def _path() -> Path:
    return config.data_dir() / "projects.json"


def _load() -> dict:
    p = _path()
    if not p.exists():
        return {"projects": []}
    return json.loads(p.read_text())


def _save(data: dict) -> None:
    _path().write_text(json.dumps(data, indent=2))


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def all_active() -> list[dict]:
    return [p for p in _load()["projects"] if p.get("active", True)]


def add(name: str, goal: str | None = None) -> dict:
    data = _load()
    slug = _slug(name)

    existing = next((p for p in data["projects"] if p["id"] == slug), None)
    if existing:
        if not existing.get("active", True):
            existing["active"] = True
            existing["name"] = name
            if goal:
                existing["goal"] = goal
            _save(data)
            return existing
        raise ValueError(f"Project '{name}' already exists.")

    project = {
        "id": slug,
        "name": name,
        "goal": goal,
        "created": date.today().isoformat(),
        "active": True,
    }
    data["projects"].append(project)
    _save(data)
    return project


def remove(name: str) -> dict:
    data = _load()
    slug = _slug(name)
    project = next((p for p in data["projects"] if p["id"] == slug or p["name"].lower() == name.lower()), None)
    if not project:
        raise ValueError(f"Project '{name}' not found.")
    project["active"] = False
    _save(data)
    return project


def match(note: str) -> str | None:
    """Best-effort: return the project id whose name best matches the note text."""
    note_lower = note.lower()
    projects = all_active()
    for p in projects:
        if p["name"].lower() in note_lower or p["id"] in note_lower:
            return p["id"]
    return None
