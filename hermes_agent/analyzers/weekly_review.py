"""
analyzers/weekly_review.py
Aggregates the past week's trades + daily notes and generates
a comprehensive weekly review written to the vault.
"""

from pathlib import Path
from datetime import date, timedelta

from vault_reader import load_trades, load_daily_notes
import hermes_client as hermes
import writer


def _get_week_label() -> str:
    today = date.today()
    start = today - timedelta(days=today.weekday() + 1)  # Last Monday
    end = start + timedelta(days=4)  # Friday
    return f"{start.strftime('%d %b')} – {end.strftime('%d %b %Y')}"


def _collect_week_data() -> str:
    """Build a single text block from last week's trades + daily notes."""
    today = date.today()
    # Include Mon–Sun of the last completed week
    week_end = today - timedelta(days=today.weekday() + 1)
    week_start = week_end - timedelta(days=6)

    sections = []

    # --- Trades ---
    all_trades = load_trades()
    week_trades = []
    for t in all_trades:
        date_str = t["metadata"].get("date") or t["filename"][:10]
        try:
            td = date.fromisoformat(str(date_str))
            if week_start <= td <= week_end:
                week_trades.append(t)
        except ValueError:
            pass

    if week_trades:
        trade_lines = []
        total_pnl = 0.0
        wins = losses = 0
        for t in week_trades:
            m = t["metadata"]
            pnl_raw = m.get("pnl", 0)
            try:
                pnl_val = float(str(pnl_raw).replace(",", ""))
                total_pnl += pnl_val
            except ValueError:
                pnl_val = 0
            result = str(m.get("result", "")).lower()
            if "win" in result:
                wins += 1
            elif "loss" in result:
                losses += 1
            trade_lines.append(
                f"  {m.get('date','?')} | {m.get('stock','?')} | "
                f"{m.get('trade_type','?')} | Entry ₹{m.get('entry_price','?')} | "
                f"Exit ₹{m.get('exit_price','?')} | P&L ₹{pnl_raw} | {m.get('result','?')}"
            )
        total = wins + losses
        wr = f"{wins/total*100:.0f}%" if total > 0 else "N/A"
        sections.append(
            f"TRADES THIS WEEK ({len(week_trades)} total):\n"
            f"Net P&L: ₹{total_pnl:,.0f} | Wins: {wins} | Losses: {losses} | Win Rate: {wr}\n"
            + "\n".join(trade_lines)
        )
    else:
        sections.append("TRADES THIS WEEK: No trades logged.")

    # --- Daily notes ---
    all_daily = load_daily_notes()
    week_dailies = []
    for n in all_daily:
        try:
            nd = date.fromisoformat(n["filename"])
            if week_start <= nd <= week_end:
                week_dailies.append(n)
        except ValueError:
            pass

    if week_dailies:
        journal_block = "DAILY JOURNAL ENTRIES:\n"
        for n in week_dailies:
            journal_block += f"\n-- {n['filename']} --\n{n['body'][:800]}\n"
        sections.append(journal_block)
    else:
        sections.append("DAILY JOURNAL ENTRIES: No daily notes found for this week.")

    return "\n\n".join(sections)


def run() -> Path:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    console = Console()

    week_label = _get_week_label()
    console.print(f"[cyan]📝 Generating weekly review for [bold]{week_label}[/bold][/cyan]")

    context = _collect_week_data()

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as p:
        p.add_task("🧠 Hermes is writing your weekly review...", total=None)
        review = hermes.generate_weekly_review(context, week_label)

    out_path = writer.write_weekly_review(week_label, review)
    console.print(f"[green]✅ Weekly review written → [bold]{out_path.name}[/bold][/green]")
    return out_path
