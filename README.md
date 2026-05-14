# Movere

> *movere* (Latin) — to move, to motivate, to set in motion

Movere is a Personal Project OS inspired by Brian Little's **Personal Projects Theory** — the idea that what makes life meaningful is not just who we are, but what we are trying to do. Our core personal projects give life structure, direction, and vitality.

## What it does

Movere tracks your most important life projects and sends a **daily AI-generated coaching email** each morning. It pulls real data from your life — workouts, calendar events, and application pipelines — synthesizes it, and delivers a personalized digest that helps you show up intentionally every day.

### Projects tracked

| Project | Data source | What's tracked |
|---|---|---|
| **Fitness** | Garmin Connect | Steps, sleep, HRV, workouts, recovery |
| **Career Applications** | Google Calendar + local data | Application deadlines, interviews, follow-ups |
| **Mentoring** | Google Calendar | Upcoming sessions, notes, action items |

## Daily digest

Each morning you receive an email with:

- **Yesterday's recap** — fitness metrics, meetings, progress made
- **Today's focus** — what matters most across all three projects
- **AI coaching note** — a short, personalized nudge written by Claude based on your data
- **Week-at-a-glance** — upcoming calendar events and deadlines

## Project structure

```
movere/
├── data/           # Cached API responses and local project data
├── templates/      # Jinja2 HTML email templates
├── config/         # API keys, credentials, and project settings
└── movere/         # Core Python package
    ├── garmin.py       # Garmin Connect data fetcher
    ├── calendar.py     # Google Calendar integration
    ├── digest.py       # AI digest generation (Claude API)
    ├── email_sender.py # Email delivery via SMTP/SendGrid
    └── main.py         # Orchestration entrypoint
```

## Inspiration

> "Personal projects are extended sets of personally relevant action that you are currently working on."
> — Brian R. Little, *Me, Myself, and Us* (2014)

Little found that people who actively pursue meaningful personal projects — and feel they are making progress on them — report significantly higher well-being. Movere is built on that insight: small daily awareness of your projects compounds into a life deliberately lived.

## Setup

```bash
# Clone and install
git clone <repo>
cd movere
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Configure
cp config/settings.example.toml config/settings.toml
# Fill in API keys in config/settings.toml

# Run once to test
python -m movere.main

# Schedule daily (e.g., 7am)
# Add to crontab: 0 7 * * * /path/to/.venv/bin/python -m movere.main
```

## Requirements

- Python 3.11+
- Garmin Connect account
- Google Calendar API credentials
- Anthropic API key (Claude)
- SMTP credentials or SendGrid API key
