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

    parts.append(f"**Fitness (yesterday):** steps={fitness.get('steps')}, "
                 f"sleep={fitness.get('sleep_hours')}h, sleep score={fitness.get('sleep_score')}, "
                 f"avg stress={fitness.get('stress')}, resting HR={fitness.get('resting_hr')} bpm, "
                 f"VO2 max={fitness.get('vo2_max')}, activity={fitness.get('activity') or 'none logged'}")

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

    career_events = calendar_data["career"]["events"]
    mentoring_events = calendar_data["mentoring"]["events"]

    if career_events:
        titles = ", ".join(e["title"] for e in career_events[:3])
        parts.append(f"**Career (upcoming):** {titles}")
    else:
        parts.append("**Career:** No upcoming career events.")

    if mentoring_events:
        titles = ", ".join(e["title"] for e in mentoring_events[:3])
        parts.append(f"**Mentoring (upcoming):** {titles}")
    else:
        parts.append("**Mentoring:** No upcoming mentoring sessions.")

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
        career=calendar_data["career"],
        mentoring=calendar_data["mentoring"],
        lookahead_days=lookahead_days,
        week_stats=week_stats,
    )
