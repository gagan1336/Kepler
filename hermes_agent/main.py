"""
main.py — Hermes AI Agent CLI
Usage:
  python main.py analyze          — analyse all trades + update memory
  python main.py debrief          — generate today's daily debrief
  python main.py debrief 2026-08-26  — debrief for a specific date
  python main.py weekly           — generate last week's review
  python main.py watch            — start the auto-scheduler (daily + weekly)
  python main.py status           — show memory summary
"""

import sys
import os

# Allow imports from this directory
sys.path.insert(0, os.path.dirname(__file__))

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

console = Console()


BANNER = """
██╗  ██╗███████╗██████╗ ███╗   ███╗███████╗███████╗
██║  ██║██╔════╝██╔══██╗████╗ ████║██╔════╝██╔════╝
███████║█████╗  ██████╔╝██╔████╔██║█████╗  ███████╗
██╔══██║██╔══╝  ██╔══██╗██║╚██╔╝██║██╔══╝  ╚════██║
██║  ██║███████╗██║  ██║██║ ╚═╝ ██║███████╗███████║
╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚══════╝
"""


def print_banner():
    console.print(Text(BANNER, style="bold cyan"))
    console.print(Panel(
        "[bold white]🤖 Hermes AI — Your Self-Learning Trading Coach[/bold white]\n"
        "[dim]Powered by Nous Hermes 3 via Ollama | 100% Local[/dim]",
        border_style="cyan",
    ))


def cmd_analyze():
    from analyzers.trade_analyzer import run
    run()


def cmd_debrief(target_date: str = None):
    from analyzers.journal_analyzer import run_daily_debrief
    run_daily_debrief(target_date)


def cmd_weekly():
    from analyzers.weekly_review import run
    run()


def cmd_watch():
    from scheduler import start
    start()


def cmd_status():
    from pathlib import Path
    from vault_reader import load_memory
    from writer import write_memory_summary

    memory_path = Path(__file__).parent / "memory.json"
    memory = load_memory(memory_path)

    console.print(Panel(
        f"[bold]Trades analysed:[/bold] {memory.get('total_trades_seen', 0)}\n"
        f"[bold]Patterns learned:[/bold] {len(memory.get('patterns', []))}\n"
        f"[bold]Emotional flags:[/bold] {len(memory.get('emotional_flags', []))}\n"
        f"[bold]Last updated:[/bold] {memory.get('last_updated', 'Never')}",
        title="🧠 Hermes Memory Status",
        border_style="green",
    ))

    if memory.get("patterns"):
        console.print("\n[bold cyan]Patterns I know about you:[/bold cyan]")
        for p in memory["patterns"]:
            console.print(f"  • {p}")

    out = write_memory_summary(memory)
    console.print(f"\n[dim]Memory note updated: {out}[/dim]")


def main():
    print_banner()

    args = sys.argv[1:]
    if not args:
        console.print("[bold yellow]Usage:[/bold yellow]")
        console.print("  python main.py [bold]analyze[/bold]          — Analyse all trades")
        console.print("  python main.py [bold]debrief[/bold]          — Today's journal debrief")
        console.print("  python main.py [bold]debrief 2026-08-26[/bold] — Debrief for a date")
        console.print("  python main.py [bold]weekly[/bold]           — Last week's review")
        console.print("  python main.py [bold]watch[/bold]            — Auto-schedule (daily + weekly)")
        console.print("  python main.py [bold]status[/bold]           — Show memory summary")
        return

    command = args[0].lower()

    if command == "analyze":
        cmd_analyze()

    elif command == "debrief":
        date_arg = args[1] if len(args) > 1 else None
        cmd_debrief(date_arg)

    elif command == "weekly":
        cmd_weekly()

    elif command == "watch":
        cmd_watch()

    elif command == "status":
        cmd_status()

    else:
        console.print(f"[red]Unknown command:[/red] {command}")
        console.print("Run [bold]python main.py[/bold] to see available commands.")


if __name__ == "__main__":
    main()
