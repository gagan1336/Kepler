"""
analyzers/journal_analyzer.py
Reads the most recent daily notes and generates a concise daily debrief.
Can also identify emotional trends over the past N days.
"""

from pathlib import Path
from datetime import date, timedelta

from vault_reader import load_daily_notes, load_memory, save_memory
import hermes_client as hermes
import writer


MEMORY_PATH = Path(__file__).parent.parent / "memory.json"


def _get_recent_notes(days: int = 7) -> list[dict]:
    """Return daily notes from the last N days."""
    all_notes = load_daily_notes()
    cutoff = date.today() - timedelta(days=days)
    recent = []
    for note in all_notes:
        try:
            note_date = date.fromisoformat(note["filename"])
            if note_date >= cutoff:
                recent.append(note)
        except ValueError:
            pass
    return recent


def run_daily_debrief(target_date: str = None) -> Path:
    """
    Generate a debrief for a specific date (default: today).
    Finds the matching daily note and asks Hermes to summarise it.
    """
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    console = Console()

    if target_date is None:
        target_date = date.today().isoformat()

    all_notes = load_daily_notes()
    note = next((n for n in all_notes if n["filename"] == target_date), None)

    if not note:
        console.print(f"[yellow]⚠️  No daily note found for {target_date}.[/yellow]")
        console.print(f"   Create one at: 📅 Daily Notes/{target_date}.md")
        return None

    console.print(f"[cyan]📅 Generating debrief for {target_date}[/cyan]")

    context = f"Date: {target_date}\n\n{note['body']}"

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as p:
        p.add_task("🧠 Hermes is reading your journal...", total=None)
        debrief = hermes.analyze_daily_journal(context, target_date)

    out_path = writer.write_daily_debrief(target_date, debrief)
    console.print(f"[green]✅ Daily debrief written → [bold]{out_path.name}[/bold][/green]")

    # Scan for emotional keywords and update memory
    _update_emotional_memory(note["body"])

    return out_path


def _update_emotional_memory(body: str) -> None:
    """Scan journal body for emotional flags and persist to memory."""
    emotion_keywords = {
        "anxious": "anxiety noted",
        "fomo": "FOMO noted",
        "revenge": "revenge trading noted",
        "overconfident": "overconfidence noted",
        "fear": "fear noted",
        "greedy": "greed noted",
        "stressed": "stress noted",
        "frustrated": "frustration noted",
    }
    body_lower = body.lower()
    memory = load_memory(MEMORY_PATH)
    flags = memory.get("emotional_flags", [])
    today = date.today().isoformat()

    for kw, label in emotion_keywords.items():
        if kw in body_lower:
            entry = f"{today}: {label}"
            if entry not in flags:
                flags.append(entry)

    memory["emotional_flags"] = flags[-30:]  # keep last 30 entries
    save_memory(memory, MEMORY_PATH)
