"""Generate the AI coaching note and render the HTML digest."""

import anthropic
from jinja2 import Environment, FileSystemLoader

from . import config, context as ctx
from . import logger


def _build_coaching_prompt(fitness: dict, calendar_data: dict, screen: dict, yesterday_log: dict,
                           week_stats: dict | None = None) -> str:
    from datetime import date as _date
    today = _date.today()
    tomorrow = today + __import__("datetime").timedelta(days=1)
    day_context = f"Today is {today.strftime('%A, %B %-d')}. Tomorrow is {tomorrow.strftime('%A')}."

    parts = ["You are a warm, direct personal coach. Write a single short paragraph (3-5 sentences) as a coaching note."]
    parts.append("Be specific — reference the actual data below. Avoid generic platitudes.")
    parts.append(f"\n## Context\n{day_context}")

    chat_notes = ctx.load_recent()
    if chat_notes:
        parts.append("**Notes from yesterday's conversations:** " + " | ".join(chat_notes))

    parts.append("\n## Data for today\n")

    p5k = fitness.get("projected_5k")
    p5k_secs = fitness.get("projected_5k_seconds")
    goal_secs = 20 * 60
    p5k_gap = f"{abs(p5k_secs - goal_secs)}s {'over' if p5k_secs > goal_secs else 'under'} goal" if p5k_secs else ""
    parts.append(f"**Fitness (yesterday):** steps={fitness.get('steps')}, "
                 f"sleep={fitness.get('sleep_hours')}h, sleep score={fitness.get('sleep_score')}, "
                 f"avg stress={fitness.get('stress')}, resting HR={fitness.get('resting_hr')} bpm, "
                 f"VO2 max={fitness.get('vo2_max')}, projected 5K={p5k or '—'} ({p5k_gap}), "
                 f"goal=sub-20:00 5K, activity={fitness.get('activity') or 'none logged'}")

    if not screen.get("error") and screen.get("phone_minutes") is not None:
        goal = screen["goal_minutes"]
        phone = screen["phone_minutes"]
        over = phone - goal
        top_apps = []
        for device_name, data in screen.get("devices", {}).items():
            if any(k in device_name.lower() for k in ["iphone", "phone"]):
                top_apps.extend(data.get("top_apps", [])[:3])
        top_apps_str = ", ".join(f"{a['name']} ({a['minutes']}m)" for a in top_apps[:4])
        status = f"{over:+.0f} min vs {goal} min goal" if screen["over_goal"] else f"{abs(over):.0f} min under {goal} min goal"
        parts.append(f"**Phone screen time (yesterday):** {phone} min ({status}). Top apps: {top_apps_str}. Goal: reduce phone usage.")

    # Personal projects
    by_proj = yesterday_log.get("by_project", {})
    missed = [p["name"] for p in yesterday_log.get("missed", [])]
    if by_proj or missed:
        parts.append("**Personal projects (yesterday):**")
        for pid, notes in by_proj.items():
            parts.append(f"  - {pid}: {'; '.join(notes)}")
        if missed:
            parts.append(f"  - Not logged (missed?): {', '.join(missed)}")

    today_events = calendar_data.get("today", [])
    if today_events:
        titles = ", ".join(e["title"] for e in today_events[:5])
        parts.append(f"**Today's schedule:** {titles}")
    else:
        parts.append("**Today's schedule:** Nothing on the calendar today.")

    for key, label in [("career", "Career"), ("mentoring", "Mentoring"),
                       ("fitness", "Fitness events"), ("project", "Blocked project time")]:
        events = calendar_data.get(key, {}).get("events", [])
        if events:
            titles = ", ".join(e["title"] for e in events[:3])
            parts.append(f"**{label} (upcoming):** {titles}")
        elif key in ("career", "mentoring"):
            parts.append(f"**{label}:** No upcoming events.")

    if week_stats and week_stats.get("hit_rate"):
        hr = week_stats["hit_rate"]
        days = week_stats["days_counted"]
        hr_str = ", ".join(f"{pid.replace('-', ' ')}: {pct}%" for pid, pct in hr.items())
        parts.append(f"**This week ({days} days):** project completion rate — {hr_str}")

    parts.append("\nWrite the coaching note now. Do not use bullet points or headers — just flowing prose.")
    return "\n".join(parts)


def generate_coaching_note(cfg: dict, fitness: dict, calendar_data: dict,
                           screen: dict | None = None, yesterday_log: dict | None = None,
                           week_stats: dict | None = None) -> str:
    client = anthropic.Anthropic(api_key=cfg["anthropic"]["api_key"])
    prompt = _build_coaching_prompt(fitness, calendar_data, screen or {}, yesterday_log or {}, week_stats)

    message = client.messages.create(
        model=cfg["anthropic"]["model"],
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}],
    )
    ctx.clear()
    return message.content[0].text.strip()


def _chat_url() -> str:
    import socket, os
    if os.environ.get("CI"):
        return "http://localhost:7842/"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        return f"http://{ip}:7842/"
    except Exception:
        return "http://localhost:7842/"


def render_html(date_str: str, coaching_note: str, fitness: dict, calendar_data: dict,
                screen: dict, yesterday_log: dict, lookahead_days: int,
                week_stats: dict | None = None) -> str:
    env = Environment(loader=FileSystemLoader(str(config.templates_dir())))
    template = env.get_template("daily_digest.html")

    return template.render(
        date=date_str,
        coaching_note=coaching_note,
        fitness=fitness,
        screen=screen,
        yesterday_log=yesterday_log,
        today_events=calendar_data.get("today", []),
        career=calendar_data["career"],
        mentoring=calendar_data["mentoring"],
        fitness_events=calendar_data.get("fitness", {"events": []}),
        project_events=calendar_data.get("project", {"events": []}),
        general_events=calendar_data.get("general", {"events": []}),
        lookahead_days=lookahead_days,
        week_stats=week_stats,
        chat_url=_chat_url(),
    )
