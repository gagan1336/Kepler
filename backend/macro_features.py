"""
KEPLER — Macro & Regime Features (Phase C-r)
=============================================
Downloads and caches daily macro data from yfinance:
  - India VIX        (^INDIAVIX)
  - USD/INR spot     (USDINR=X)
  - Brent crude      (BZ=F)
  - Nifty 50 index   (^NSEI) — used for market breadth

Features produced per date (merged into the training DataFrame):
  india_vix         : VIX level (higher = fear)
  vix_5d_change     : VIX change over last 5 trading days
  usd_inr_1d_ret    : INR daily return (positive = rupee weakened)
  crude_1d_ret      : Brent crude daily return
  market_breadth    : % of Nifty200 stocks above their 20d SMA
                      (computed from the per-stock feature DataFrame,
                      not from a separate download)

Point-in-time safety
--------------------
All macro series are aligned to their *announcement* date (no forward fill
beyond 5 trading days). If a date has no macro data, features default to
their rolling 30-day median — never to a future value.

Usage
-----
    from macro_features import build_macro_df, merge_macro

    # Download + cache macro data
    macro_df = build_macro_df(start="2016-01-01")

    # Merge into training dataset (date column must exist)
    train_df = merge_macro(train_df, macro_df)
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from loguru import logger

warnings.filterwarnings("ignore")

_BACKEND_DIR = Path(__file__).parent
_CACHE_DIR   = _BACKEND_DIR / ".cache" / "macro"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_CACHE_FILE  = _CACHE_DIR / "macro_daily.pkl"

# Macro feature columns added to training DataFrame
MACRO_FEATURE_COLS = [
    "india_vix",
    "vix_5d_change",
    "usd_inr_1d_ret",
    "crude_1d_ret",
    "market_breadth",   # computed from per-stock data, not downloaded
]

_TICKERS = {
    "india_vix":  "^INDIAVIX",
    "usd_inr":    "USDINR=X",
    "brent":      "BZ=F",
}


def _download_series(ticker: str, start: str, end: str | None = None) -> pd.Series:
    """Download a single yfinance ticker's Close series."""
    try:
        df = yf.Ticker(ticker).history(start=start, end=end, interval="1d",
                                       auto_adjust=True)
        if df.empty:
            return pd.Series(dtype=float)
        s = df["Close"].dropna()
        s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
        return s
    except Exception as e:
        logger.debug(f"Macro fetch failed for {ticker}: {e}")
        return pd.Series(dtype=float)


def build_macro_df(
    start: str = "2016-01-01",
    end: str | None = None,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """
    Download and cache macro time series.
    Returns a DataFrame indexed by date with columns: india_vix,
    vix_5d_change, usd_inr_1d_ret, crude_1d_ret.
    (market_breadth is added later by merge_macro from the training data.)

    Uses a disk cache (.cache/macro/macro_daily.pkl) — only refreshes if
    stale (>2 days old) or force_refresh=True.
    """
    if _CACHE_FILE.exists() and not force_refresh:
        try:
            cached = pd.read_pickle(_CACHE_FILE)
            age_days = (pd.Timestamp.utcnow().tz_localize(None) -
                        cached.index.max()).days
            if age_days <= 2:
                logger.info(f"  📦 Macro cache fresh ({age_days}d old)")
                return cached
            logger.info(f"  📦 Macro cache stale ({age_days}d) — refreshing…")
        except Exception:
            pass

    logger.info("📡 Downloading macro data (VIX, USDINR, Brent)…")

    vix_s    = _download_series("^INDIAVIX", start, end)
    usdinr_s = _download_series("USDINR=X",  start, end)
    brent_s  = _download_series("BZ=F",      start, end)

    macro = pd.DataFrame(index=pd.date_range(
        start=start, end=end or pd.Timestamp.today(), freq="B"
    ))
    macro.index = macro.index.normalize()

    def _align(s: pd.Series, name: str) -> pd.Series:
        return s.reindex(macro.index, method="ffill", limit=5).rename(name)

    macro["india_vix"]  = _align(vix_s,    "india_vix")
    macro["usd_inr"]    = _align(usdinr_s, "usd_inr")
    macro["brent"]      = _align(brent_s,  "brent")

    # Derived features
    macro["vix_5d_change"]  = macro["india_vix"].pct_change(5).fillna(0) * 100
    macro["usd_inr_1d_ret"] = macro["usd_inr"].pct_change(1).fillna(0) * 100
    macro["crude_1d_ret"]   = macro["brent"].pct_change(1).fillna(0) * 100

    # Fill remaining NaNs with rolling 30-day median
    for col in ["india_vix", "vix_5d_change", "usd_inr_1d_ret", "crude_1d_ret"]:
        rolling_med = macro[col].rolling(30, min_periods=1).median()
        macro[col]  = macro[col].fillna(rolling_med)

    # Keep only derived columns (not raw vix/usdinr/brent levels for training)
    out = macro[["india_vix", "vix_5d_change", "usd_inr_1d_ret", "crude_1d_ret"]]
    out.to_pickle(_CACHE_FILE)
    logger.info(f"  ✅ Macro data: {len(out):,} trading days | "
                f"VIX range {out['india_vix'].min():.1f}–{out['india_vix'].max():.1f}")
    return out


def compute_market_breadth(df: pd.DataFrame) -> pd.Series:
    """
    Compute market breadth per date: fraction of stocks in the dataset
    whose close is above their 20-day SMA on that date.

    Parameters
    ----------
    df : training DataFrame with columns [date, symbol, pct_vs_sma20]
         pct_vs_sma20 > 0 means stock is above its 20d SMA

    Returns
    -------
    pd.Series indexed by date, values in [0, 1]
    """
    if "pct_vs_sma20" not in df.columns or "date" not in df.columns:
        return pd.Series(dtype=float)

    df_copy = df[["date", "symbol", "pct_vs_sma20"]].copy()
    df_copy["above_sma20"] = (df_copy["pct_vs_sma20"] > 0).astype(float)
    breadth = df_copy.groupby("date")["above_sma20"].mean()
    breadth.index = pd.to_datetime(breadth.index).normalize()
    return breadth


def merge_macro(
    df: pd.DataFrame,
    macro_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Merge macro features into the training DataFrame.
    Also computes market_breadth from pct_vs_sma20 in df.

    Parameters
    ----------
    df       : training DataFrame (must have 'date' column)
    macro_df : output of build_macro_df()

    Returns
    -------
    df with MACRO_FEATURE_COLS added (fills 0 where macro data unavailable)
    """
    df = df.copy()
    # Strip timezone info: generate_labels() produces Asia/Kolkata tz-aware dates,
    # but macro_df index is tz-naive. Normalize to plain date for consistent lookup.
    dates = pd.to_datetime(df["date"]).dt.tz_localize(None).dt.normalize()

    # Ensure macro_df index is also tz-naive (guard against future cache changes)
    macro_idx = macro_df.index
    if macro_idx.tz is not None:
        macro_df = macro_df.copy()
        macro_df.index = macro_idx.tz_localize(None)

    # reindex() with method="ffill" requires a monotonic (sorted) index.
    # The training DataFrame is shuffled, so we must:
    #   1. Get the sorted unique dates
    #   2. Forward-fill on that sorted index
    #   3. Map the filled values back to the original (shuffled) row order
    unique_dates_sorted = dates.drop_duplicates().sort_values()
    macro_on_uniq = macro_df.reindex(unique_dates_sorted, method="ffill", limit=3)
    # Build a lookup Series: date -> value for each macro column
    for col in ["india_vix", "vix_5d_change", "usd_inr_1d_ret", "crude_1d_ret"]:
        lookup = macro_on_uniq[col]
        df[col] = dates.map(lookup).fillna(0).values

    # Market breadth — computed from the DataFrame itself
    breadth = compute_market_breadth(df)
    # breadth is indexed by sorted dates already (from groupby), safe to map
    df["market_breadth"] = dates.map(breadth).fillna(0.5).values

    n_filled = (df["india_vix"] != 0).sum()
    logger.info(
        f"  📊 Macro merged: {n_filled:,}/{len(df):,} rows have VIX data "
        f"| breadth mean={df['market_breadth'].mean():.1%}"
    )
    return df


# ── CLI: download and inspect macro data ─────────────────────────────────────
if __name__ == "__main__":
    import sys
    logger.remove()
    logger.add(sys.stderr, level="INFO",
               format="<green>{time:HH:mm:ss}</green> | {message}")

    macro = build_macro_df(start="2018-01-01", force_refresh=True)
    print(macro.tail(10).to_string())
    print(f"\nMacro feature stats:\n{macro.describe().round(3).to_string()}")
