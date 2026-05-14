"""Movere entrypoint — fetch data, generate digest, send email."""

from datetime import date

from . import config, digest, email_sender, garmin
from .calendar import fetch as fetch_calendar


def main() -> None:
    cfg = config.load()
    lookahead = cfg["schedule"].get("calendar_lookahead_days", 7)
    today = date.today().strftime("%A, %B %-d, %Y")

    print("Fetching Garmin data...")
    fitness = garmin.fetch(cfg)

    print("Fetching Google Calendar events...")
    calendar_data = fetch_calendar(cfg, lookahead_days=lookahead)

    print("Generating AI coaching note...")
    coaching_note = digest.generate_coaching_note(cfg, fitness, calendar_data)

    print("Rendering email...")
    html = digest.render_html(today, coaching_note, fitness, calendar_data, lookahead)

    subject = f"Movere — {today}"
    print(f"Sending digest to {cfg['email']['recipient']}...")
    email_sender.send(cfg, subject, html)

    print("Done.")


if __name__ == "__main__":
    main()
