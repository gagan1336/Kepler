"""
scheduler.py
Runs Hermes analyses on a daily and weekly schedule.
Daily: 6:00 PM — daily debrief for today's journal
Weekly: Sunday 8:00 PM — full weekly review
"""

import schedule
import time
from datetime import date
from rich.console import Console

console = Console()


def _run_daily():
    console.rule("[bold cyan]⏰ Scheduled Daily Debrief[/bold cyan]")
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from analyzers.journal_analyzer import run_daily_debrief
    run_daily_debrief(date.today().isoformat())


def _run_weekly():
    console.rule("[bold cyan]⏰ Scheduled Weekly Review[/bold cyan]")
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from analyzers.weekly_review import run
    run()


def start():
    console.print("[bold green]🤖 Hermes Scheduler started.[/bold green]")
    console.print("   Daily debrief  → [bold]6:00 PM every weekday[/bold]")
    console.print("   Weekly review  → [bold]8:00 PM every Sunday[/bold]")
    console.print("   Press [bold]Ctrl+C[/bold] to stop.\n")

    schedule.every().monday.at("18:00").do(_run_daily)
    schedule.every().tuesday.at("18:00").do(_run_daily)
    schedule.every().wednesday.at("18:00").do(_run_daily)
    schedule.every().thursday.at("18:00").do(_run_daily)
    schedule.every().friday.at("18:00").do(_run_daily)
    schedule.every().sunday.at("20:00").do(_run_weekly)

    while True:
        schedule.run_pending()
        time.sleep(30)
