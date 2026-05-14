"""Fetch yesterday's health metrics from Garmin Connect."""

import json
from datetime import date, timedelta
from pathlib import Path

from garminconnect import Garmin

from . import config


def _latest_cache(data_dir: Path) -> dict | None:
    """Return the most recent cached Garmin result, or None if no cache exists."""
    files = sorted(data_dir.glob("garmin_*.json"), reverse=True)
    if files:
        return json.loads(files[0].read_text())
    return None


def fetch(cfg: dict, cache: bool = True) -> dict:
    yesterday = date.today() - timedelta(days=1)
    cache_path = config.data_dir() / f"garmin_{yesterday}.json"

    if cache and cache_path.exists():
        return json.loads(cache_path.read_text())

    try:
        token_dir = str(config.data_dir() / "garmin_tokens")
        try:
            client = Garmin()
            client.login(tokenstore=token_dir)
        except Exception:
            client = Garmin(cfg["garmin"]["email"], cfg["garmin"]["password"])
            client.login(tokenstore=token_dir)

        date_str = yesterday.isoformat()

        steps_data = client.get_steps_data(date_str)
        sleep_data = client.get_sleep_data(date_str)
        hrv_data = client.get_hrv_data(date_str)
        body_battery = client.get_body_battery(date_str)
        activities = client.get_activities_by_date(date_str, date_str)

        total_steps = sum(s.get("steps", 0) for s in steps_data) if steps_data else 0

        sleep_hours = None
        sleep_score = None
        if sleep_data and "dailySleepDTO" in sleep_data:
            dto = sleep_data["dailySleepDTO"]
            seconds = dto.get("sleepTimeSeconds", 0)
            sleep_hours = round(seconds / 3600, 1)
            sleep_score = (dto.get("sleepScores") or {}).get("overall", {}).get("value")

        hrv_value = None
        if hrv_data and "hrvSummary" in hrv_data:
            hrv_value = hrv_data["hrvSummary"].get("lastNight")

        battery_value = None
        if body_battery:
            charged = [b for b in body_battery if b.get("charged")]
            if charged:
                battery_value = charged[-1].get("level")

        activity_name = None
        if activities:
            a = activities[0]
            activity_name = f"{a.get('activityName', 'Workout')} ({round(a.get('distance', 0) / 1000, 1)} km)"

        result = {
            "date": date_str,
            "steps": total_steps,
            "sleep_hours": sleep_hours,
            "sleep_score": sleep_score,
            "hrv": hrv_value,
            "body_battery": battery_value,
            "activity": activity_name,
        }

        if cache:
            cache_path.write_text(json.dumps(result, indent=2))

        return result

    except Exception as e:
        fallback = _latest_cache(config.data_dir())
        if fallback:
            fallback["error"] = f"Garmin unavailable ({e}); showing cached data from {fallback['date']}"
            return fallback
        return {"error": str(e), "steps": None, "sleep_hours": None, "hrv": None, "body_battery": None, "activity": None}
