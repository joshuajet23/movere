"""Movere CLI — personal project OS."""

import argparse
from datetime import date
from pathlib import Path

from . import config, digest, email_sender, garmin, screentime, chat, server as web_server
from . import projects as proj_store
from . import logger
from .calendar import fetch as fetch_calendar


# ── digest helpers ────────────────────────────────────────────────────────────

def _print_summary(today: str, coaching_note: str, fitness: dict, calendar_data: dict,
                   screen: dict, yesterday_log: dict) -> None:
    sep = "─" * 60
    print(f"\n{sep}")
    print(f"  MOVERE — {today}")
    print(sep)

    print("\n[ Coaching Note ]")
    print(coaching_note)

    print("\n[ Fitness ]")
    for key, label in [("steps", "Steps"), ("sleep_hours", "Sleep (hrs)"),
                       ("hrv", "HRV"), ("body_battery", "Body Battery"), ("activity", "Activity")]:
        val = fitness.get(key)
        if val is not None:
            print(f"  {label}: {val}")

    print("\n[ Screen Time ]")
    if screen.get("error"):
        print(f"  {screen['error']}")
    else:
        goal = screen["goal_minutes"]
        total = screen["total_minutes"]
        over = "⚠ over goal" if screen["over_goal"] else "✓ under goal"
        print(f"  Phone: {screen.get('phone_minutes', '—')} min  |  Goal: {goal} min  {over}")
        print(f"  Mac:   {screen.get('mac_minutes', '—')} min  (informational)")

    print("\n[ Personal Projects ]")
    projects = proj_store.all_active()
    if not projects:
        print("  No projects yet. Run: movere project add 'your project'")
    else:
        by_proj = yesterday_log.get("by_project", {})
        missed = {p["id"] for p in yesterday_log.get("missed", [])}
        for p in projects:
            entries = by_proj.get(p["id"], [])
            goal_str = f"  [{p['goal']}]" if p.get("goal") else ""
            status = "✓" if entries else ("✗" if p["id"] in missed else "·")
            print(f"  {status} {p['name']}{goal_str}")
            for note in entries:
                print(f"      → {note}")

    for project, label in [("career", "Career Applications"), ("mentoring", "Mentoring")]:
        events = calendar_data[project]["events"]
        print(f"\n[ {label} — Upcoming ]")
        if events:
            for e in events:
                print(f"  • {e['title']}  —  {e['datetime']}")
        else:
            print("  No upcoming events.")

    print(f"\n{sep}\n")


# ── subcommands ───────────────────────────────────────────────────────────────

def cmd_project(args: argparse.Namespace) -> None:
    if args.project_cmd == "add":
        try:
            p = proj_store.add(args.name, goal=args.goal)
            goal_str = f" (goal: {p['goal']})" if p.get("goal") else ""
            print(f"✓ Added project: {p['name']}{goal_str}")
        except ValueError as e:
            print(f"✗ {e}")

    elif args.project_cmd == "list":
        projects = proj_store.all_active()
        if not projects:
            print("No active projects. Add one: movere project add 'your project'")
        else:
            print(f"\n{'Project':<28} {'Goal':<24} {'Since'}")
            print("─" * 60)
            for p in projects:
                print(f"  {p['name']:<26} {p.get('goal') or '—':<24} {p['created']}")
            print()

    elif args.project_cmd == "remove":
        try:
            p = proj_store.remove(args.name)
            print(f"✓ Archived project: {p['name']}")
        except ValueError as e:
            print(f"✗ {e}")


def cmd_log(args: argparse.Namespace) -> None:
    entry = logger.add_entry(args.note, project_id=args.project or None)
    proj_label = entry.get("project") or "general"
    print(f"✓ Logged [{proj_label}]: {args.note}")


def cmd_status(_args: argparse.Namespace) -> None:
    s = logger.status_today()
    today_str = date.today().strftime("%A, %B %-d")
    print(f"\nMovere — {today_str}")
    print("─" * 40)

    if not s["entries"]:
        print("Nothing logged today yet.")
    else:
        for e in s["entries"]:
            proj = e.get("project") or "—"
            print(f"  [{proj}] {e['note']}")

    if s["unlogged"]:
        print("\nNot yet logged today:")
        for p in s["unlogged"]:
            goal_str = f" ({p['goal']})" if p.get("goal") else ""
            print(f"  · {p['name']}{goal_str}")
    print()


# ── digest command ────────────────────────────────────────────────────────────

def cmd_digest(args: argparse.Namespace) -> None:
    cfg = config.load()
    lookahead = cfg["schedule"].get("calendar_lookahead_days", 7)
    today = date.today().strftime("%A, %B %-d, %Y")

    if args.mock:
        from . import mock
        print("Using mock data (no live API calls).")
        fitness = mock.fitness()
        calendar_data = mock.calendar()
        screen = mock.screentime()
        yesterday_log = mock.yesterday_log()
    else:
        print("Fetching Garmin data...")
        fitness = garmin.fetch(cfg)

        print("Fetching Google Calendar events...")
        calendar_data = fetch_calendar(cfg, lookahead_days=lookahead)

        print("Fetching screen time data...")
        screen = screentime.fetch(cfg)

        yesterday_log = logger.yesterday_summary()

    week_stats = logger.week_stats()

    print("Generating AI coaching note...")
    coaching_note = digest.generate_coaching_note(cfg, fitness, calendar_data, screen, yesterday_log, week_stats)

    print("Rendering email...")
    html = digest.render_html(today, coaching_note, fitness, calendar_data, screen, yesterday_log, lookahead, week_stats)

    if args.dry_run or args.mock:
        _print_summary(today, coaching_note, fitness, calendar_data, screen, yesterday_log)
        preview_path = config.data_dir() / "preview.html"
        preview_path.write_text(html)
        print(f"HTML preview saved → {preview_path}")
        print("(dry run — no email sent)")
    else:
        subject = f"Movere — {today}"
        print(f"Sending digest to {cfg['email']['recipient']}...")
        email_sender.send(cfg, subject, html)
        print("Done.")


# ── entrypoint ────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="movere",
        description="Movere — Personal Project OS",
    )
    sub = parser.add_subparsers(dest="cmd")

    # movere project add/list/remove
    p_project = sub.add_parser("project", help="Manage personal projects")
    p_project_sub = p_project.add_subparsers(dest="project_cmd")

    p_add = p_project_sub.add_parser("add", help="Add a new project")
    p_add.add_argument("name", help="Project name")
    p_add.add_argument("--goal", help="Daily or weekly goal (e.g. '5 pages/day')")

    p_list = p_project_sub.add_parser("list", help="List active projects")  # noqa: F841

    p_remove = p_project_sub.add_parser("remove", help="Archive a project")
    p_remove.add_argument("name", help="Project name to archive")

    # movere log
    p_log = sub.add_parser("log", help="Log progress on a project")
    p_log.add_argument("note", help="What you did")
    p_log.add_argument("--project", "-p", help="Project name (auto-detected if omitted)")

    # movere status
    sub.add_parser("status", help="Show today's log")

    # movere chat
    p_chat = sub.add_parser("chat", help="Talk to Movere in plain English")
    p_chat.add_argument("message", help="What you want to say or do")

    # movere server
    p_server = sub.add_parser("server", help="Start the local chat web interface")
    p_server.add_argument("--port", type=int, default=web_server.PORT, help="Port to listen on")

    # movere (default — run digest)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print to terminal and save HTML preview; skip email.")
    parser.add_argument("--mock", action="store_true",
                        help="Use stubbed data instead of live APIs (implies --dry-run).")

    args = parser.parse_args()

    if args.cmd == "project":
        cmd_project(args)
    elif args.cmd == "log":
        cmd_log(args)
    elif args.cmd == "status":
        cmd_status(args)
    elif args.cmd == "chat":
        chat.run(args.message, config.load())
    elif args.cmd == "server":
        web_server.run(port=args.port)
    else:
        if args.mock:
            args.dry_run = True
        cmd_digest(args)


if __name__ == "__main__":
    main()
