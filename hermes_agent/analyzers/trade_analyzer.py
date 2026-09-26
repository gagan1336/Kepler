"""
analyzers/trade_analyzer.py
Reads all trade journal entries, formats them into a rich context string,
calls Hermes for pattern analysis, updates memory, and writes results.
"""

import json
import re
from pathlib import Path

from vault_reader import load_trades, load_memory, save_memory
import hermes_client as hermes
import writer


MEMORY_PATH = Path(__file__).parent.parent / "memory.json"


def _summarize_trade(note: dict) -> str:
    """Convert a trade note dict into a compact text block for the LLM."""
    meta = note["metadata"]
    body = note["body"]

    # Pull frontmatter fields
    stock    = meta.get("stock", note["filename"])
    date     = meta.get("date", "unknown date")
    trade_t  = meta.get("trade_type", "?")
    qty      = meta.get("quantity", "?")
    entry    = meta.get("entry_price", "?")
    exit_p   = meta.get("exit_price", "?")
    pnl      = meta.get("pnl", "?")
    result   = meta.get("result", "?")
    strategy = meta.get("strategy", "?")

    # Extract free-text sections from body (Lessons Learned, Execution)
    lessons_match = re.search(
        r"##\s*.*Lessons Learned.*?\n(.*?)(?=\n##|\Z)", body, re.S | re.I
    )
    exec_match = re.search(
        r"##\s*.*Execution Review.*?\n(.*?)(?=\n##|\Z)", body, re.S | re.I
    )
    lessons = lessons_match.group(1).strip() if lessons_match else ""
    execution = exec_match.group(1).strip() if exec_match else ""

    return (
        f"TRADE: {stock} | {date} | {trade_t} | Qty: {qty} | "
        f"Entry: ₹{entry} | Exit: ₹{exit_p} | P&L: ₹{pnl} | {result} | Strategy: {strategy}\n"
        f"Execution: {execution}\nLessons: {lessons}\n"
        "---"
    )


def run() -> Path:
    """Main entry point — analyse all trades and write insights to vault."""
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn
    console = Console()

    trades = load_trades()
    if not trades:
        console.print("[yellow]⚠️  No trade notes found in the vault yet.[/yellow]")
        console.print("   Add trades using the Trade Log Template first.")
        return None

    console.print(f"[cyan]📓 Found {len(trades)} trade note(s)[/cyan]")

    # Build context block
    summaries = [_summarize_trade(t) for t in trades]
    context = f"Total trades: {len(trades)}\n\n" + "\n".join(summaries)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        task = progress.add_task("🧠 Hermes is analysing your trade patterns...", total=None)
        analysis = hermes.analyze_trade_patterns(context)

    # Write analysis to vault
    out_path = writer.write_pattern_analysis(analysis)
    console.print(f"[green]✅ Pattern analysis written → [bold]{out_path.name}[/bold][/green]")

    # Update memory
    memory = load_memory(MEMORY_PATH)
    memory["total_trades_seen"] = len(trades)

    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), transient=True) as progress:
        progress.add_task("🧠 Updating Hermes memory...", total=None)
        raw_patterns = hermes.update_memory_insights(memory, context)

    # Parse the JSON array Hermes returns
    try:
        new_patterns = json.loads(raw_patterns)
        if isinstance(new_patterns, list):
            # Merge with existing, deduplicate
            all_patterns = list(dict.fromkeys(memory["patterns"] + new_patterns))
            memory["patterns"] = all_patterns[:20]  # cap at 20
    except Exception:
        pass  # If Hermes returns non-JSON, skip silently

    save_memory(memory, MEMORY_PATH)
    mem_path = writer.write_memory_summary(memory)
    console.print(f"[green]✅ Memory updated → [bold]{mem_path.name}[/bold][/green]")

    return out_path
