"""
KEPLER — Walk-Forward Split Engine
====================================
Provides time-series safe train/test splits with purge + embargo gaps
to prevent label leakage across fold boundaries.

Key concepts
------------
  purge   : rows *in the training set* whose label horizon extends past the
            fold boundary are removed. With a 10-day forward label, any
            training row within 10 days before the test start has a label
            that "looks at" data in the test period → must be purged.

  embargo : rows *at the start of the test set* that are "contaminated" by
            the last training bars (e.g. EMA, ATR) that use test data in
            their rolling windows. A 5-day embargo after the boundary is
            usually enough for daily features with a 14-day lookback.

            Combined purge+embargo = label_horizon * 1.5 days (configurable).

Usage
-----
    from walk_forward import generate_wf_splits, print_split_summary

    splits = generate_wf_splits(
        df,                       # must have a 'date' column
        n_folds=5,
        embargo_days=15,          # purge+embargo window in trading days
        min_train_rows=5000,      # skip fold if training set is too small
    )
    for fold_idx, (train_idx, test_idx) in enumerate(splits):
        X_train, y_train = X[train_idx], y[train_idx]
        X_test,  y_test  = X[test_idx],  y[test_idx]

Unit-testable via:
    python walk_forward.py
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
from loguru import logger


# ── Data structure for one fold ───────────────────────────────────────────────
@dataclass
class FoldInfo:
    fold_idx: int
    train_start: date
    train_end: date          # last date in training set (after purge)
    test_start: date         # first date in test set (after embargo)
    test_end: date
    n_train: int
    n_test: int
    embargo_days_applied: int
    skipped: bool = False
    skip_reason: str = ""


# ── Core split generator ──────────────────────────────────────────────────────
def generate_wf_splits(
    df: pd.DataFrame,
    n_folds: int = 5,
    embargo_days: int = 15,
    min_train_rows: int = 3000,
    expanding: bool = True,
) -> List[Tuple[np.ndarray, np.ndarray]]:
    """
    Generate walk-forward train/test index arrays from a time-ordered DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain a 'date' column (datetime-like). Rows should be sorted
        by date already; if not, they will be sorted internally.
    n_folds : int
        Number of walk-forward folds to create.
    embargo_days : int
        Total gap (in trading rows) applied around each boundary:
          - Last `embargo_days // 2` rows of train are purged
          - First `embargo_days - embargo_days // 2` rows of test are skipped
        This separates purge (train side) from embargo (test side).
    min_train_rows : int
        Minimum training rows required; fold is skipped if not met.
    expanding : bool
        If True  → expanding window (each fold's train starts from date 0).
        If False → rolling window (train window size is fixed).

    Returns
    -------
    List of (train_idx, test_idx) integer index arrays (into df).
    Empty list if no valid folds can be created.
    """
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    n = len(df)
    if n == 0:
        logger.error("walk_forward: empty dataframe")
        return []

    fold_infos: List[FoldInfo] = []

    # Work in date-space, not row-space, to handle multi-stock panels
    # (many rows can share the same date)
    unique_dates = df["date"].drop_duplicates().sort_values().reset_index(drop=True)
    n_dates = len(unique_dates)

    if n_dates < n_folds + 2:
        logger.error(f"walk_forward: only {n_dates} unique dates — need at least {n_folds + 2}")
        return []

    # Divide unique dates into (n_folds + 1) equal buckets
    bucket_size = n_dates // (n_folds + 1)
    if bucket_size < 1:
        logger.error(f"walk_forward: not enough dates ({n_dates}) for {n_folds} folds")
        return []

    splits: List[Tuple[np.ndarray, np.ndarray]] = []
    
    purge_rows   = embargo_days // 2
    embargo_rows = embargo_days - purge_rows

    for k in range(n_folds):
        # Test window: date bucket (k+1)
        test_bucket_start_date_idx = (k + 1) * bucket_size
        test_bucket_end_date_idx   = min(test_bucket_start_date_idx + bucket_size - 1, n_dates - 1)

        # Apply embargo: skip first `embargo_rows` UNIQUE DATES of test window
        test_date_start_idx = test_bucket_start_date_idx + embargo_rows
        if test_date_start_idx > test_bucket_end_date_idx:
            fi = FoldInfo(
                fold_idx=k,
                train_start=unique_dates.iloc[0].date(),
                train_end=unique_dates.iloc[max(0, test_bucket_start_date_idx - 1)].date(),
                test_start=unique_dates.iloc[test_bucket_start_date_idx].date(),
                test_end=unique_dates.iloc[test_bucket_end_date_idx].date(),
                n_train=0, n_test=0,
                embargo_days_applied=embargo_days,
                skipped=True, skip_reason="embargo larger than test window",
            )
            fold_infos.append(fi)
            continue

        # Train window: all dates strictly BEFORE the test bucket starts
        # Apply purge: drop last `purge_rows` unique dates from training side
        train_date_end_idx = test_bucket_start_date_idx - 1 - purge_rows
        if train_date_end_idx < 0:
            fi = FoldInfo(
                fold_idx=k,
                train_start=unique_dates.iloc[0].date(),
                train_end=unique_dates.iloc[0].date(),
                test_start=unique_dates.iloc[test_date_start_idx].date(),
                test_end=unique_dates.iloc[test_bucket_end_date_idx].date(),
                n_train=0, n_test=0,
                embargo_days_applied=embargo_days,
                skipped=True, skip_reason="purge larger than training window",
            )
            fold_infos.append(fi)
            continue

        train_date_start_idx = 0 if expanding else max(0, train_date_end_idx - bucket_size * n_folds + 1)

        # Convert date indices back to date values
        train_date_start = unique_dates.iloc[train_date_start_idx]
        train_date_end   = unique_dates.iloc[train_date_end_idx]
        test_date_start  = unique_dates.iloc[test_date_start_idx]
        test_date_end    = unique_dates.iloc[test_bucket_end_date_idx]

        # Strict temporal gap check
        assert train_date_end < test_date_start, (
            f"Fold {k+1}: train_date_end={train_date_end} >= test_date_start={test_date_start}"
        )

        # Row index arrays for all rows in each date window
        train_mask = (df["date"] >= train_date_start) & (df["date"] <= train_date_end)
        test_mask  = (df["date"] >= test_date_start)  & (df["date"] <= test_date_end)
        train_idx  = df.index[train_mask].values
        test_idx   = df.index[test_mask].values

        fi = FoldInfo(
            fold_idx=k,
            train_start=train_date_start.date(),
            train_end=train_date_end.date(),
            test_start=test_date_start.date(),
            test_end=test_date_end.date(),
            n_train=len(train_idx),
            n_test=len(test_idx),
            embargo_days_applied=embargo_days,
        )

        if len(train_idx) < min_train_rows:
            fi.skipped = True
            fi.skip_reason = f"n_train={len(train_idx)} < min_train_rows={min_train_rows}"
            fold_infos.append(fi)
            continue

        fold_infos.append(fi)
        splits.append((train_idx, test_idx))

    _log_split_summary(fold_infos)
    return splits


def fold_date_range(
    df: pd.DataFrame,
    idx: np.ndarray,
) -> Tuple[str, str]:
    """Return (min_date_str, max_date_str) for a set of row indices."""
    dates = df["date"].iloc[idx]
    return str(dates.min().date()), str(dates.max().date())


def _log_split_summary(fold_infos: List[FoldInfo]) -> None:
    """Pretty-print split summary to the logger."""
    logger.info("─" * 70)
    logger.info(f"{'Fold':<6} {'Train start':<14} {'Train end':<14} "
                f"{'Test start':<14} {'Test end':<14} {'N_train':>8} {'N_test':>7}")
    logger.info("─" * 70)
    for fi in fold_infos:
        status = " [SKIP]" if fi.skipped else ""
        reason = f" ← {fi.skip_reason}" if fi.skip_reason else ""
        logger.info(
            f"{fi.fold_idx + 1:<6} "
            f"{str(fi.train_start):<14} {str(fi.train_end):<14} "
            f"{str(fi.test_start):<14} {str(fi.test_end):<14} "
            f"{fi.n_train:>8,} {fi.n_test:>7,}"
            f"{status}{reason}"
        )
    logger.info("─" * 70)
    valid = [fi for fi in fold_infos if not fi.skipped]
    logger.info(f"Walk-forward: {len(valid)}/{len(fold_infos)} folds valid")


def embargo_check(train_idx: np.ndarray, test_idx: np.ndarray) -> bool:
    """
    Assert that train and test index arrays have no overlap.
    Returns True if clean, False if contaminated.
    """
    overlap = np.intersect1d(train_idx, test_idx)
    if len(overlap) > 0:
        logger.error(f"embargo_check FAILED: {len(overlap)} overlapping rows!")
        return False
    return True


# ── Convenience: get date range for a fold's test window ─────────────────────
def fold_date_range(df: pd.DataFrame, test_idx: np.ndarray) -> Tuple[date, date]:
    """Return (test_start_date, test_end_date) for a given test index array."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    dates = df["date"].iloc[test_idx]
    return dates.min().date(), dates.max().date()


# ── Unit test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | {message}")

    # Synthetic dataset: 1000 stocks × 500 days
    logger.info("=== Walk-Forward Unit Test ===")

    n_rows = 50_000
    rng = np.random.default_rng(42)
    dates = pd.date_range("2018-01-01", periods=500, freq="B").repeat(100)
    synth = pd.DataFrame({
        "date":   dates[:n_rows],
        "symbol": [f"SYM{i % 100}" for i in range(n_rows)],
        "feat_a": rng.standard_normal(n_rows),
        "label":  (rng.random(n_rows) > 0.82).astype(int),
    })

    splits = generate_wf_splits(synth, n_folds=5, embargo_days=15, min_train_rows=1000)

    assert len(splits) > 0, "No valid folds!"
    errors = 0
    for k, (tr_idx, te_idx) in enumerate(splits):
        ok = embargo_check(tr_idx, te_idx)
        if not ok:
            errors += 1
        # Temporal check: all train dates < all test dates
        train_max = synth["date"].iloc[tr_idx].max()
        test_min  = synth["date"].iloc[te_idx].min()
        if train_max >= test_min:
            logger.error(f"Fold {k+1}: temporal order violated! train_max={train_max}, test_min={test_min}")
            errors += 1
        else:
            logger.info(f"Fold {k+1}: ✅ temporal order OK (gap = {(test_min - train_max).days}d)")

    if errors == 0:
        logger.info("✅ All assertions passed — walk_forward.py is leakage-free")
        sys.exit(0)
    else:
        logger.error(f"❌ {errors} assertion(s) failed")
        sys.exit(1)
