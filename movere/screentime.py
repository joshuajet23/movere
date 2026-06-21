"""Read daily screen time from an iOS Shortcut (phone) and macOS knowledgeC.db (Mac).

iPhone: a Shortcut saves {"total_minutes": <number>} to
  ~/Library/Mobile Documents/com~apple~CloudDocs/Movere/phone_screentime.json
  at ~5:45 AM daily. Movere reads it at digest time, stamps it with today's
  run date, and archives it for trend tracking.

Mac data requires Terminal to have Full Disk Access:
  System Settings → Privacy & Security → Full Disk Access → add Terminal.app
"""

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from . import config

_ICLOUD_SCREENTIME = (
    Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Movere/phone_screentime.json"
)

_CD_EPOCH = 978307200

_DB = Path.home() / "Library/Application Support/Knowledge/knowledgeC.db"

_CATEGORY_KEYWORDS = {
    "social": ["twitter", "instagram", "tiktok", "facebook", "snapchat", "reddit", "linkedin", "mastodon", "threads"],
    "productivity": ["notion", "obsidian", "vscode", "xcode", "terminal", "code", "word", "excel", "pages", "numbers"],
    "entertainment": ["youtube", "netflix", "spotify", "vlc", "plex", "twitch", "disney"],
    "communication": ["mail", "messages", "slack", "teams", "zoom", "facetime", "discord", "telegram", "whatsapp"],
    "browser": ["safari", "chrome", "firefox", "arc", "edge", "brave"],
}


# ── phone history (iCloud Shortcut) ──────────────────────────────────────────

def _phone_history_path(d: date) -> Path:
    return config.data_dir() / f"screentime_phone_{d}.json"


def _read_icloud_phone() -> float | None:
    """Read total_minutes from the iCloud Shortcut file. No date expected in the file."""
    try:
        if not _ICLOUD_SCREENTIME.exists():
            return None
        data = json.loads(_ICLOUD_SCREENTIME.read_text())
        val = data.get("total_minutes")
        return float(val) if val is not None else None
    except Exception:
        return None


def _save_phone_history(run_date: date, minutes: float) -> None:
    try:
        _phone_history_path(run_date).write_text(
            json.dumps({"date": run_date.isoformat(), "total_minutes": minutes})
        )
    except Exception:
        pass


def _load_phone_trend(exclude: date, days: int = 7) -> dict:
    """Average phone minutes over the last `days` days, not counting `exclude`."""
    entries = []
    for i in range(1, days + 1):
        p = _phone_history_path(exclude - timedelta(days=i))
        if p.exists():
            try:
                entries.append(float(json.loads(p.read_text())["total_minutes"]))
            except Exception:
                pass
    if not entries:
        return {"avg": None, "days": 0}
    return {"avg": round(sum(entries) / len(entries), 1), "days": len(entries)}


# ── Mac screen time (knowledgeC.db) ──────────────────────────────────────────

def _to_cd(d: date) -> float:
    import calendar
    import datetime
    dt = datetime.datetime(d.year, d.month, d.day)
    return calendar.timegm(dt.timetuple()) - _CD_EPOCH


def _categorize(bundle_or_name: str) -> str:
    name = bundle_or_name.lower()
    for cat, keywords in _CATEGORY_KEYWORDS.items():
        if any(k in name for k in keywords):
            return cat
    return "other"


def _friendly_name(bundle: str) -> str:
    parts = bundle.split(".")
    if len(parts) >= 3:
        return parts[-1].replace("-", " ").title()
    return bundle.title()


def _fetch_mac_minutes(yesterday: date) -> tuple[float, dict]:
    """Return (mac_total_minutes, devices_dict) from knowledgeC.db."""
    if not _DB.exists():
        return 0.0, {}
    start_cd = _to_cd(yesterday)
    end_cd = _to_cd(date.today())
    try:
        con = sqlite3.connect(f"file:{_DB}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return 0.0, {}

    with con:
        rows = con.execute(
            """
            SELECT
                o.ZVALUESTRING,
                s.ZDEVICEID,
                SUM(MAX(o.ZENDDATE, o.ZSTARTDATE) - o.ZSTARTDATE) AS secs
            FROM ZOBJECT o
            LEFT JOIN ZSOURCE s ON o.ZSOURCE = s.Z_PK
            WHERE o.ZSTREAMNAME = '/app/usage'
              AND o.ZSTARTDATE >= ?
              AND o.ZSTARTDATE <  ?
              AND o.ZVALUESTRING IS NOT NULL
            GROUP BY o.ZVALUESTRING, s.ZDEVICEID
            ORDER BY secs DESC
            """,
            (start_cd, end_cd),
        ).fetchall()

    devices: dict[str, dict] = {}
    total_secs = 0.0
    for bundle, device_id, secs in rows:
        label = device_id or "Mac"
        if label not in devices:
            devices[label] = {"total_minutes": 0.0, "top_apps": [], "by_category": {}}
        minutes = secs / 60
        devices[label]["total_minutes"] = round(devices[label]["total_minutes"] + minutes, 1)
        devices[label]["top_apps"].append({"name": _friendly_name(bundle), "minutes": round(minutes, 1)})
        cat = _categorize(bundle)
        devices[label]["by_category"][cat] = round(devices[label]["by_category"].get(cat, 0) + minutes, 1)
        total_secs += secs

    for d in devices.values():
        d["top_apps"] = sorted(d["top_apps"], key=lambda x: x["minutes"], reverse=True)[:5]

    mac_minutes = round(sum(d["total_minutes"] for d in devices.values()), 1)
    return mac_minutes, devices


# ── public fetch ──────────────────────────────────────────────────────────────

def fetch(cfg: dict | None = None) -> dict:
    today = date.today()
    yesterday = today - timedelta(days=1)
    goal_minutes = (cfg or {}).get("screentime", {}).get("daily_goal_minutes", 180)

    # Phone: read iCloud file, persist for trend tracking
    icloud_mins = _read_icloud_phone()
    if icloud_mins is not None:
        _save_phone_history(today, icloud_mins)
        phone_minutes: float | None = round(icloud_mins, 1)
        phone_source = "shortcut"
    else:
        phone_minutes = None
        phone_source = "unavailable"

    phone_trend = _load_phone_trend(exclude=today)

    over_goal = (phone_minutes or 0.0) > goal_minutes

    # Mac: knowledgeC.db (best-effort, not critical)
    try:
        mac_minutes, devices = _fetch_mac_minutes(yesterday)
    except Exception:
        mac_minutes, devices = 0.0, {}

    return {
        "date": today.isoformat(),
        "phone_minutes": phone_minutes,
        "phone_source": phone_source,
        "phone_trend": phone_trend,
        "mac_minutes": mac_minutes,
        "goal_minutes": goal_minutes,
        "over_goal": over_goal,
        "devices": devices,
        "error": None,
    }
