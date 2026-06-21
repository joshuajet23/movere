"""Fetch yesterday's health metrics from Garmin Connect."""

import json
import time
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
        client = None
        last_err = None
        for attempt in range(3):
            try:
                if attempt == 0:
                    c = Garmin()
                    c.login(tokenstore=token_dir)
                else:
                    c = Garmin(cfg["garmin"]["email"], cfg["garmin"]["password"])
                    c.login(tokenstore=token_dir)
                client = c
                break
            except Exception as e:
                last_err = e
                if attempt < 2:
                    time.sleep(10 * (attempt + 1))
        if client is None:
            raise last_err

        date_str = yesterday.isoformat()
        today_str = date.today().isoformat()

        steps_data = client.get_steps_data(date_str)
        sleep_data = client.get_sleep_data(today_str)   # sleep is stored under wake-up date
        stress_data = client.get_stress_data(date_str)
        max_metrics = client.get_max_metrics(date_str)
        race_preds = client.get_race_predictions()
        activities = client.get_activities_by_date(date_str, date_str)

        total_steps = sum(s.get("steps", 0) for s in steps_data) if steps_data else 0

        sleep_hours = None
        sleep_score = None
        if sleep_data and "dailySleepDTO" in sleep_data:
            dto = sleep_data["dailySleepDTO"]
            seconds = dto.get("sleepTimeSeconds", 0)
            sleep_hours = round(seconds / 3600, 1)
            sleep_score = (dto.get("sleepScores") or {}).get("overall", {}).get("value")

        stress_value = None
        if stress_data:
            stress_value = stress_data.get("avgStressLevel")

        resting_hr = None
        if sleep_data:
            resting_hr = sleep_data.get("restingHeartRate")

        vo2_max = None
        if max_metrics and isinstance(max_metrics, list) and max_metrics:
            vo2_max = (max_metrics[0].get("generic") or {}).get("vo2MaxValue")

        projected_5k = None
        projected_5k_seconds = None
        if race_preds and isinstance(race_preds, dict):
            secs = race_preds.get("time5K")
            if secs:
                projected_5k_seconds = secs
                projected_5k = f"{secs // 60}:{secs % 60:02d}"

        activity_name = None
        if activities:
            a = activities[0]
            activity_name = f"{a.get('activityName', 'Workout')} ({round(a.get('distance', 0) / 1000, 1)} km)"

        result = {
            "date": date_str,
            "steps": total_steps,
            "sleep_hours": sleep_hours,
            "sleep_score": sleep_score,
            "stress": stress_value,
            "resting_hr": resting_hr,
            "vo2_max": vo2_max,
            "projected_5k": projected_5k,
            "projected_5k_seconds": projected_5k_seconds,
            "activity": activity_name,
        }

        if cache:
            cache_path.write_text(json.dumps(result, indent=2))

        return result

    except Exception as e:
        fallback = _latest_cache(config.data_dir())
        if fallback and fallback.get("date") == yesterday.isoformat():
            return fallback  # same-day cache, no problem
        if fallback:
            fallback["stale"] = True
            fallback["error"] = f"⚠ Garmin unavailable — showing data from {fallback['date']} (not yesterday)"
            return fallback
        return {"error": str(e), "steps": None, "sleep_hours": None, "sleep_score": None, "stress": None, "resting_hr": None, "vo2_max": None, "projected_5k": None, "projected_5k_seconds": None, "activity": None}
