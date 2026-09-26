"""
vault_reader.py
Scans the Obsidian vault and parses markdown files + YAML frontmatter
into structured Python dicts for the analyzers.
"""

import os
import re
from pathlib import Path
from datetime import datetime
from typing import Optional

import frontmatter


VAULT_ROOT = Path(__file__).parent.parent / "ObsidianVault"

FOLDERS = {
    "trades":    VAULT_ROOT / "📓 Trade Journal",
    "daily":     VAULT_ROOT / "📅 Daily Notes",
    "portfolio": VAULT_ROOT / "💼 Portfolio",
    "watchlist": VAULT_ROOT / "👁️ Watchlist",
    "research":  VAULT_ROOT / "📚 Research",
    "insights":  VAULT_ROOT / "🤖 AI Insights",
}


def _read_md(path: Path) -> dict:
    """Parse a single markdown file, return frontmatter + body."""
    try:
        post = frontmatter.load(str(path))
        return {
            "path": str(path),
            "filename": path.stem,
            "metadata": dict(post.metadata),
            "body": post.content,
        }
    except Exception:
        # Fallback: return raw text with no frontmatter
        try:
            text = path.read_text(encoding="utf-8")
            return {"path": str(path), "filename": path.stem, "metadata": {}, "body": text}
        except Exception:
            return {"path": str(path), "filename": path.stem, "metadata": {}, "body": ""}


def load_trades() -> list[dict]:
    """Return all trade journal notes (excluding README)."""
    folder = FOLDERS["trades"]
    if not folder.exists():
        return []
    notes = []
    for f in sorted(folder.glob("*.md")):
        if f.stem.upper() == "README":
            continue
        notes.append(_read_md(f))
    return notes


def load_daily_notes() -> list[dict]:
    """Return all daily journal notes (YYYY-MM-DD.md), sorted by date."""
    folder = FOLDERS["daily"]
    if not folder.exists():
        return []
    notes = []
    for f in sorted(folder.glob("????-??-??.md")):
        notes.append(_read_md(f))
    return notes


def load_watchlist() -> dict:
    """Return the watchlist note."""
    path = FOLDERS["watchlist"] / "Watchlist.md"
    if not path.exists():
        return {}
    return _read_md(path)


def load_portfolio() -> dict:
    """Return the portfolio tracker note."""
    path = FOLDERS["portfolio"] / "Portfolio Tracker.md"
    if not path.exists():
        return {}
    return _read_md(path)


def load_memory(memory_path: Path) -> dict:
    """Load persisted Hermes memory JSON, or return empty skeleton."""
    import json
    if memory_path.exists():
        try:
            return json.loads(memory_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "total_trades_seen": 0,
        "patterns": [],
        "emotional_flags": [],
        "best_setups": [],
        "worst_setups": [],
        "last_updated": None,
    }


def save_memory(memory: dict, memory_path: Path) -> None:
    import json
    memory["last_updated"] = datetime.now().isoformat()
    memory_path.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")


def extract_table_rows(body: str, header_hint: str) -> list[list[str]]:
    """
    Very lightweight markdown table parser.
    Finds the first table whose header contains `header_hint` and returns rows.
    """
    lines = body.splitlines()
    in_table = False
    rows = []
    for line in lines:
        stripped = line.strip()
        if not in_table:
            if "|" in stripped and header_hint.lower() in stripped.lower():
                in_table = True
                continue  # skip header
        else:
            if not stripped.startswith("|"):
                break
            if re.match(r"^\|[-| ]+\|$", stripped):
                continue  # separator row
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            rows.append(cells)
    return rows


def ensure_insights_folder() -> Path:
    folder = FOLDERS["insights"]
    folder.mkdir(parents=True, exist_ok=True)
    return folder
