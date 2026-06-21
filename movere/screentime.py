"""Read daily screen time from macOS knowledgeC.db (Mac) and an iCloud Drive
JSON file written by an iOS Shortcut (iPhone).

iPhone setup: create a Shortcut that runs at ~5:45 AM daily and saves a JSON
file to iCloud Drive/Movere/phone_screentime.json with the format:
  {"date": "YYYY-MM-DD", "total_minutes": <number>}

Mac data: requires Terminal (or your Python binary) to have Full Disk Access:
  System Settings → Privacy & Security → Full Disk Access → add Terminal.app
"""

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

_ICLOUD_SCREENTIME = (
    Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/Movere/phone_screentime.json"
)

# Core Data epoch offset: seconds between 2001-01-01 and 1970-01-01
_CD_EPOCH = 978307200

_DB = Path.home() / "Library/Application Support/Knowledge/knowledgeC.db"

_CATEGORY_KEYWORDS = {
    "social": ["twitter", "instagram", "tiktok", "facebook", "snapchat", "reddit", "linkedin", "mastodon", "threads"],
    "productivity": ["notion", "obsidian", "vscode", "xcode", "terminal", "code", "word", "excel", "pages", "numbers"],
    "entertainment": ["youtube", "netflix", "spotify", "vlc", "plex", "twitch", "disney"],
    "communication": ["mail", "messages", "slack", "teams", "zoom", "facetime", "discord", "telegram", "whatsapp"],
    "browser": ["safari", "chrome", "firefox", "arc", "edge", "brave"],
}


def _read_icloud_phone(yesterday: date) -> float | None:
    """Return phone minutes from the iCloud Shortcut file, or None if absent/stale."""
    try:
        if not _ICLOUD_SCREENTIME.exists():
            return None
        data = json.loads(_ICLOUD_SCREENTIME.read_text())
        if data.get("date") == yesterday.isoformat():
            return float(data["total_minutes"])
    except Exception:
        pass
    return None


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
    # com.apple.Safari → Safari, com.google.Chrome → Chrome
    if len(parts) >= 3:
        return parts[-1].replace("-", " ").title()
    return bundle.title()


def fetch(cfg: dict | None = None) -> dict:
    if not _DB.exists():
        import os, json as _json, base64
        cached = os.environ.get("SCREENTIME_CACHE_B64")
        if cached:
            try:
                return _json.loads(base64.b64decode(cached))
            except Exception:
                pass
        return {"error": "knowledgeC.db not found", "total_minutes": None, "devices": {}}

    yesterday = date.today() - timedelta(days=1)
    start_cd = _to_cd(yesterday)
    end_cd = _to_cd(date.today())

    goal_minutes = (cfg or {}).get("screentime", {}).get("daily_goal_minutes", 180)

    try:
        con = sqlite3.connect(f"file:{_DB}?mode=ro", uri=True)
    except sqlite3.OperationalError as e:
        return {"error": str(e), "total_minutes": None, "devices": {}}

    with con:
        # App usage rows with device identifier (ZDEVICEID is in ZSOURCE, not ZOBJECT)
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

        device_names: dict[str, str] = {}

    # Aggregate by device
    devices: dict[str, dict] = {}
    total_secs = 0.0

    for bundle, device_id, secs in rows:
        label = device_names.get(device_id or "", device_id or "Mac")
        if label not in devices:
            devices[label] = {"total_minutes": 0.0, "top_apps": [], "by_category": {}}

        minutes = secs / 60
        devices[label]["total_minutes"] = round(devices[label]["total_minutes"] + minutes, 1)
        devices[label]["top_apps"].append({"name": _friendly_name(bundle), "minutes": round(minutes, 1)})
        cat = _categorize(bundle)
        devices[label]["by_category"][cat] = round(
            devices[label]["by_category"].get(cat, 0) + minutes, 1
        )
        total_secs += secs

    # Sort top apps per device, keep top 5
    for d in devices.values():
        d["top_apps"] = sorted(d["top_apps"], key=lambda x: x["minutes"], reverse=True)[:5]

    total_minutes = round(total_secs / 60, 1)

    # Mac = everything in knowledgeC.db (ZDEVICEID is always null on Mac-only sync)
    mac_minutes = round(sum(d["total_minutes"] for d in devices.values()), 1)

    # Phone = iCloud Drive file written by iOS Shortcut; falls back to 0 if absent
    icloud_phone = _read_icloud_phone(yesterday)
    phone_minutes = round(icloud_phone, 1) if icloud_phone is not None else 0.0
    phone_source = "shortcut" if icloud_phone is not None else "unavailable"
    over_goal = phone_minutes > goal_minutes

    return {
        "date": yesterday.isoformat(),
        "total_minutes": total_minutes,
        "total_hours": round(total_minutes / 60, 1),
        "phone_minutes": phone_minutes,
        "phone_source": phone_source,
        "mac_minutes": mac_minutes,
        "goal_minutes": goal_minutes,
        "over_goal": over_goal,
        "devices": devices,
        "error": None,
    }
