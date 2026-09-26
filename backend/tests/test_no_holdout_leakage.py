"""
KEPLER — Holdout Leakage Prevention Test
==========================================
Automated check that NONE of the tickers in configs/frozen_holdout.yaml
ever appear in any training data source.

Run with:
    python -m pytest tests/test_no_holdout_leakage.py -v

This test MUST pass before every training run. If it fails, a frozen ticker
has leaked into training — find and remove it before proceeding.

Why this exists
---------------
The same "OOD becomes in-sample" trap occurred twice:
  1. Sector tests contaminated by Nifty50 training stocks (fixed Phase 0)
  2. Nifty200 Extra reported as "OOD" after being added to training (Phase 1)

This test prevents it happening again automatically.
"""

import re
import sys
from pathlib import Path

import pytest
import yaml

# ── Locate key files ──────────────────────────────────────────────────────────
_BACKEND   = Path(__file__).parent.parent
_HOLDOUT_F = _BACKEND / "configs" / "frozen_holdout.yaml"
_TRAIN_F   = _BACKEND / "train_model.py"
_TEST_F    = _BACKEND / "test_model.py"

# Any file that feeds training — extend this list if new data sources are added
TRAINING_SOURCE_FILES = [
    _BACKEND / "train_model.py",
    _BACKEND / "ml_features.py",
    _BACKEND / "walk_forward.py",
]


# ── Load frozen holdout ───────────────────────────────────────────────────────
def load_frozen_tickers() -> set:
    if not _HOLDOUT_F.exists():
        pytest.fail(f"Frozen holdout file not found: {_HOLDOUT_F}")
    with open(_HOLDOUT_F) as f:
        data = yaml.safe_load(f)
    tickers = set(data.get("tickers", []))
    assert tickers, "Frozen holdout file exists but has no tickers!"
    return tickers


# ── Helpers ───────────────────────────────────────────────────────────────────
def _tickers_in_file(filepath: Path) -> set:
    """
    Return the set of frozen tickers found as Python string literals
    inside the given source file.
    Matches: "TICKER", 'TICKER', both with/without .NS suffix.
    """
    if not filepath.exists():
        return set()
    text = filepath.read_text(encoding="utf-8")
    # Find all quoted strings that look like NSE tickers
    quoted = re.findall(r"""["']([A-Z0-9&\-]{2,16})(?:\.NS)?["']""", text)
    return set(quoted)


def _training_universe_symbols() -> set:
    """
    Parse NIFTY_50, NIFTY_200_EXTRA, NIFTY_500_EXTRA from train_model.py
    by extracting all quoted uppercase strings.
    """
    return _tickers_in_file(_TRAIN_F)


# ── Tests ─────────────────────────────────────────────────────────────────────
class TestNoHoldoutLeakage:

    @classmethod
    def setup_class(cls):
        cls.frozen = load_frozen_tickers()

    def test_holdout_file_exists(self):
        """The frozen holdout config file must exist."""
        assert _HOLDOUT_F.exists(), (
            f"configs/frozen_holdout.yaml missing — create it before training"
        )

    def test_holdout_has_minimum_stocks(self):
        """Frozen holdout must have at least 30 stocks to be a meaningful holdout."""
        assert len(self.frozen) >= 30, (
            f"Frozen holdout too small: {len(self.frozen)} tickers. "
            "Need ≥30 for statistical power."
        )

    def test_no_frozen_ticker_in_training_universe(self):
        """
        CRITICAL: None of the frozen tickers may appear in train_model.py's
        universe lists (NIFTY_50, NIFTY_200_EXTRA, NIFTY_500_EXTRA).
        """
        training_symbols = _training_universe_symbols()
        leaks = self.frozen & training_symbols
        assert not leaks, (
            f"\n{'='*60}\n"
            f"HOLDOUT LEAK DETECTED — {len(leaks)} frozen ticker(s) "
            f"found in training universe:\n"
            + "\n".join(f"  ❌ {t}" for t in sorted(leaks))
            + f"\n\nRemove them from train_model.py NIFTY_* lists before training.\n"
            f"{'='*60}"
        )

    def test_no_frozen_ticker_in_training_source_files(self):
        """
        Broader check: frozen tickers should not appear as string literals
        in any file that directly feeds the training pipeline.
        Allows appearances in comments/test files — only training source files checked.
        """
        all_leaks = {}
        for fpath in TRAINING_SOURCE_FILES:
            found = self.frozen & _tickers_in_file(fpath)
            if found:
                all_leaks[fpath.name] = sorted(found)

        if all_leaks:
            msg = "\n".join(
                f"  {fname}: {tickers}"
                for fname, tickers in all_leaks.items()
            )
            pytest.fail(
                f"\n{'='*60}\n"
                f"HOLDOUT LEAK in training source files:\n{msg}\n"
                f"{'='*60}"
            )

    def test_holdout_not_contaminated_by_nifty50(self):
        """
        Sanity check: frozen holdout should not contain Nifty50 stocks
        (they're in-sample for a different reason — being large-cap).
        """
        nifty50 = {
            "RELIANCE", "TCS", "HDFCBANK", "BHARTIARTL", "ICICIBANK",
            "INFY", "SBIN", "HINDUNILVR", "ITC", "KOTAKBANK",
            "LT", "AXISBANK", "BAJFINANCE", "MARUTI", "ASIANPAINT",
            "HCLTECH", "SUNPHARMA", "NTPC", "POWERGRID", "ONGC",
            "ULTRACEMCO", "WIPRO", "NESTLEIND", "M&M", "TECHM",
            "TITAN", "JSWSTEEL", "TATASTEEL", "INDUSINDBK", "HINDALCO",
            "ADANIENT", "ADANIPORTS", "COALINDIA", "BAJAJFINSV", "DRREDDY",
            "CIPLA", "EICHERMOT", "HEROMOTOCO", "BPCL", "GRASIM",
            "BRITANNIA", "DIVISLAB", "APOLLOHOSP", "TATACONSUM", "SBILIFE",
            "HDFCLIFE", "SHRIRAMFIN", "BEL", "TRENT", "BAJAJ-AUTO",
        }
        cross = self.frozen & nifty50
        assert not cross, (
            f"Frozen holdout contains Nifty50 stocks (these are in training): "
            f"{sorted(cross)}"
        )

    def test_training_universe_does_not_overlap_with_holdout(self):
        """
        Explicit check between the nifty500 universe used in training
        and the frozen holdout — zero overlap required.
        """
        # Read NIFTY_500_EXTRA from train_model.py as source of truth
        text = _TRAIN_F.read_text(encoding="utf-8") if _TRAIN_F.exists() else ""
        # Extract NIFTY_500_EXTRA block
        match = re.search(
            r'NIFTY_500_EXTRA\s*=\s*\[(.*?)\]',
            text, re.DOTALL
        )
        if not match:
            return   # Can't parse — skip this check
        block    = match.group(1)
        symbols  = set(re.findall(r'"([A-Z0-9&\-]{2,16})"', block))
        overlap  = self.frozen & symbols
        assert not overlap, (
            f"NIFTY_500_EXTRA in train_model.py contains frozen holdout stocks:\n"
            + "\n".join(f"  ❌ {t}" for t in sorted(overlap))
            + "\nRemove these from NIFTY_500_EXTRA."
        )
