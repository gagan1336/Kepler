"""
KEPLER — Cross-Sectional Rank Features (Phase C-r)
====================================================
Takes a concatenated multi-stock training DataFrame and adds
sector-relative and market-relative rank percentiles per date.

Why rank features generalise better than absolute indicators
-------------------------------------------------------------
A RSI of 64 could mean "overbought" in a sideways market or "barely warm"
during a bull run. RSI rank of 0.82 (82nd percentile in sector, today) is
always meaningful: this stock has stronger momentum than 82% of its peers
right now, regardless of market regime.

The shift from ema_50 (absolute) → pct_from_52l (relative) was the
biggest single feature improvement in Phase 1. This module extends that
pattern to six new dimensions.

Rank feature columns (all in [0, 1] — higher = stronger/calmer/larger):
  sector_rsi_rank     RSI percentile within sector
  sector_mom_rank     20d return percentile within sector
  sector_vol_rank     1 - (ATR/price rank) → higher = CALMER than sector peers
  mkt_mom_rank        20d return percentile across full Nifty200 universe
  mkt_vol_rank        1 - (ATR/price rank) across full universe
  vol_vs_own_hist     today's volume vs own 60-bar rolling percentile

Point-in-time safety
--------------------
Ranks are computed strictly per calendar date using only stocks in the
*training* universe. Frozen holdout stocks are NEVER included when
computing training-set ranks — their features are computed independently
at evaluation time using the rank cache or last available snapshot.

Usage
-----
    from cross_sectional_features import add_cross_sectional_ranks

    # After building the full training dataset:
    train_df = add_cross_sectional_ranks(train_df, sector_map)

    # At inference time (live scan):
    rank_cache = load_rank_cache(today)       # yesterday's precomputed snapshot
    live_df    = apply_rank_cache(live_df, rank_cache)
"""
from __future__ import annotations

import pickle
from datetime import date
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd
from loguru import logger

_BACKEND_DIR = Path(__file__).parent
_RANK_CACHE_DIR = _BACKEND_DIR / ".cache" / "rank_snapshots"
_RANK_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# New rank feature columns (added to FEATURE_COLUMNS in ml_features.py)
RANK_FEATURE_COLS = [
    "sector_rsi_rank",
    "sector_mom_rank",
    "sector_vol_rank",
    "mkt_mom_rank",
    "mkt_vol_rank",
    "vol_vs_own_hist",
]

# NSE sector mapping for Nifty200 symbols
# (simplified — expand as universe grows)
SECTOR_MAP: Dict[str, str] = {
    # Banking / Finance
    "HDFCBANK": "Banking", "ICICIBANK": "Banking", "SBIN": "Banking",
    "KOTAKBANK": "Banking", "AXISBANK": "Banking", "INDUSINDBK": "Banking",
    "BANDHANBNK": "Banking", "FEDERALBNK": "Banking", "IDFCFIRSTB": "Banking",
    "PNB": "Banking", "BANKBARODA": "Banking", "CANBK": "Banking",
    "UNIONBANK": "Banking", "YESBANK": "Banking", "AUBANK": "Banking",
    "DCBBANK": "Banking", "RBLBANK": "Banking", "KARNATAKA": "Banking",
    "BAJFINANCE": "NBFC", "BAJAJFINSV": "NBFC", "SHRIRAMFIN": "NBFC",
    "CHOLAFIN": "NBFC", "MUTHOOTFIN": "NBFC", "LTFINANCE": "NBFC",
    "M&MFIN": "NBFC", "MANAPPURAM": "NBFC",
    "HDFCLIFE": "Insurance", "SBILIFE": "Insurance", "ICICIGI": "Insurance",
    "ICICIPRU": "Insurance",
    # IT
    "TCS": "IT", "INFY": "IT", "HCLTECH": "IT", "WIPRO": "IT",
    "TECHM": "IT", "LTIM": "IT", "MPHASIS": "IT", "COFORGE": "IT",
    "PERSISTENT": "IT", "LTIMINDTREE": "IT", "OFSS": "IT",
    # Pharma
    "SUNPHARMA": "Pharma", "DRREDDY": "Pharma", "CIPLA": "Pharma",
    "DIVISLAB": "Pharma", "TORNTPHARM": "Pharma", "AUROPHARMA": "Pharma",
    "LUPIN": "Pharma", "ALKEM": "Pharma", "IPCALAB": "Pharma",
    "ABBOTINDIA": "Pharma", "SANOFI": "Pharma",
    # Auto
    "MARUTI": "Auto", "TATAMOTORS": "Auto", "M&M": "Auto",
    "BAJAJ-AUTO": "Auto", "HEROMOTOCO": "Auto", "EICHERMOT": "Auto",
    "TVSMOTOR": "Auto", "ASHOKLEY": "Auto", "BALKRISIND": "Auto",
    "EXIDEIND": "Auto", "MOTHERSON": "Auto",
    # Energy
    "RELIANCE": "Energy", "ONGC": "Energy", "BPCL": "Energy",
    "IOC": "Energy", "NTPC": "Energy", "POWERGRID": "Energy",
    "ADANIGREEN": "Energy", "TATAPOWER": "Energy", "TORNTPOWER": "Energy",
    "ADANIPORTS": "Industrials",
    # FMCG
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG",
    "BRITANNIA": "FMCG", "DABUR": "FMCG", "MARICO": "FMCG",
    "GODREJCP": "FMCG", "COLPAL": "FMCG", "EMAMILTD": "FMCG",
    "TATACONSUM": "FMCG",
    # Industrials / Capital Goods
    "LT": "Industrials", "SIEMENS": "Industrials", "ABB": "Industrials",
    "HAVELLS": "Industrials", "VOLTAS": "Industrials", "BEL": "Industrials",
    "HAL": "Industrials", "BHEL": "Industrials", "CUMMINSIND": "Industrials",
    "SCHAEFFLER": "Industrials", "GRINDWELL": "Industrials",
    # Metals
    "JSWSTEEL": "Metals", "TATASTEEL": "Metals", "HINDALCO": "Metals",
    "COALINDIA": "Metals", "SAIL": "Metals", "NMDC": "Metals",
    "VEDL": "Metals", "WELCORP": "Metals", "JINDALSTEL": "Metals",
    # Consumer
    "TITAN": "Consumer", "TRENT": "Consumer", "DMART": "Consumer",
    "ASIANPAINT": "Consumer", "BERGER": "Consumer", "PIDILITIND": "Consumer",
    "WHIRLPOOL": "Consumer",
    # Telecom
    "BHARTIARTL": "Telecom",
    # Cement
    "ULTRACEMCO": "Cement", "GRASIM": "Cement", "SHREECEM": "Cement",
    "AMBUJACEM": "Cement", "ACCLTD": "Cement",
}
_DEFAULT_SECTOR = "Other"


def _sector_of(symbol: str) -> str:
    return SECTOR_MAP.get(symbol.upper().replace(".NS", ""), _DEFAULT_SECTOR)


def _rank_pct(series: pd.Series) -> pd.Series:
    """Return fractional rank [0, 1] — ties broken by average rank."""
    if len(series) <= 1:
        return pd.Series([0.5] * len(series), index=series.index)
    return series.rank(pct=True, method="average")


def add_cross_sectional_ranks(
    df: pd.DataFrame,
    sector_map: Optional[Dict[str, str]] = None,
    min_sector_peers: int = 3,
) -> pd.DataFrame:
    """
    Add 6 cross-sectional rank features to a multi-stock training DataFrame.

    This is a batch operation: df must contain ALL training stocks for all
    dates so that ranks are computed correctly per date.

    Parameters
    ----------
    df               : DataFrame with columns including date, symbol,
                       rsi_14, roc_20, hl_ratio, atr_14, volume_ratio
    sector_map       : {symbol: sector} — defaults to built-in SECTOR_MAP
    min_sector_peers : minimum peers needed to compute sector rank
                       (defaults to 0.5 for sectors with fewer stocks)

    Returns
    -------
    df with RANK_FEATURE_COLS added
    """
    if sector_map is None:
        sector_map = SECTOR_MAP

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["_sector"] = df["symbol"].map(
        lambda s: sector_map.get(s.upper().replace(".NS", ""), _DEFAULT_SECTOR)
    )

    # Volatility proxy: atr_14 / close-proxy = hl_ratio (already normalised)
    # Higher hl_ratio = more volatile. For vol_rank we want 1-rank (calmer = higher score)
    if "hl_ratio" not in df.columns:
        df["hl_ratio"] = 0.0

    logger.info(f"  📐 Computing cross-sectional ranks for {df['date'].nunique():,} dates "
                f"× {df['symbol'].nunique()} symbols…")

    # Initialise rank columns
    for col in RANK_FEATURE_COLS:
        df[col] = 0.5  # neutral default

    # ── Market-wide ranks (per date) ────────────────────────────────────────
    for col_raw, col_rank, invert in [
        ("roc_20",  "mkt_mom_rank", False),
        ("hl_ratio","mkt_vol_rank",  True),   # calmer = better → invert
    ]:
        if col_raw not in df.columns:
            continue
        grouped = df.groupby("date")[col_raw].transform(_rank_pct)
        df[col_rank] = (1 - grouped) if invert else grouped

    # ── Sector ranks (per date × sector) ────────────────────────────────────
    for (col_raw, col_rank, invert) in [
        ("rsi_14",  "sector_rsi_rank", False),
        ("roc_20",  "sector_mom_rank", False),
        ("hl_ratio","sector_vol_rank",  True),
    ]:
        if col_raw not in df.columns:
            continue

        def _sector_rank(group: pd.DataFrame) -> pd.Series:
            if len(group) < min_sector_peers:
                return pd.Series(0.5, index=group.index)
            r = _rank_pct(group[col_raw])
            return (1 - r) if invert else r

        ranked = df.groupby(["date", "_sector"], group_keys=False).apply(
            _sector_rank
        )
        # apply may return MultiIndex — flatten back to df.index
        if isinstance(ranked.index, pd.MultiIndex):
            ranked = ranked.reset_index(level=[0, 1], drop=True)
        df[col_rank] = ranked.reindex(df.index).fillna(0.5)

    # ── Volume vs own history (per symbol, rolling 60-bar percentile) ────────
    if "volume_ratio" in df.columns:
        df = df.sort_values(["symbol", "date"])

        def _own_vol_rank(grp: pd.DataFrame) -> pd.Series:
            vol = grp["volume_ratio"]
            # Rolling 60-bar rank: at each point, what percentile is today's vol?
            ranks = []
            vals  = vol.values
            for i in range(len(vals)):
                window = vals[max(0, i - 59): i + 1]
                r = float(np.mean(window <= vals[i])) if len(window) > 1 else 0.5
                ranks.append(r)
            return pd.Series(ranks, index=grp.index)

        df["vol_vs_own_hist"] = df.groupby("symbol", group_keys=False).apply(
            _own_vol_rank
        ).reindex(df.index).fillna(0.5)
    else:
        df["vol_vs_own_hist"] = 0.5

    df = df.drop(columns=["_sector"])
    logger.info(
        f"  ✅ Rank features added | "
        f"mkt_mom_rank mean={df['mkt_mom_rank'].mean():.3f} "
        f"| sector_rsi_rank mean={df['sector_rsi_rank'].mean():.3f}"
    )
    return df


# ── Rank cache for live inference ─────────────────────────────────────────────

def save_rank_cache(
    df: pd.DataFrame,
    snapshot_date: date | None = None,
) -> Path:
    """
    Save the latest-date rank snapshot to disk.
    Called at the end of a live batch scan so single-stock inference
    can use yesterday's ranks without recomputing.
    """
    if snapshot_date is None:
        snapshot_date = pd.to_datetime(df["date"]).max().date()

    latest = df[pd.to_datetime(df["date"]).dt.date == snapshot_date]
    rank_snap = latest[["symbol"] + RANK_FEATURE_COLS].set_index("symbol")

    path = _RANK_CACHE_DIR / f"rank_{snapshot_date}.pkl"
    rank_snap.to_pickle(path)
    logger.info(f"  💾 Rank snapshot saved → {path} ({len(rank_snap)} symbols)")
    return path


def load_rank_cache(
    as_of: date | None = None,
) -> Optional[pd.DataFrame]:
    """
    Load the most recent rank snapshot (default: most recent available).
    Returns None if no cache exists.
    """
    caches = sorted(_RANK_CACHE_DIR.glob("rank_*.pkl"), reverse=True)
    if not caches:
        return None

    # If as_of specified, find the most recent cache on or before that date
    if as_of is not None:
        caches = [
            c for c in caches
            if c.stem.replace("rank_", "") <= str(as_of)
        ]
        if not caches:
            return None

    path = caches[0]
    try:
        snap = pd.read_pickle(path)
        logger.debug(f"  Rank cache loaded: {path.name} ({len(snap)} symbols)")
        return snap
    except Exception as e:
        logger.debug(f"  Rank cache load failed: {e}")
        return None


def apply_rank_cache(
    df: pd.DataFrame,
    rank_cache: Optional[pd.DataFrame],
) -> pd.DataFrame:
    """
    Apply a pre-computed rank snapshot to a live inference DataFrame.
    Fills rank features with cache values; falls back to 0.5 if symbol missing.
    """
    df = df.copy()
    for col in RANK_FEATURE_COLS:
        df[col] = 0.5  # default neutral

    if rank_cache is None:
        return df

    if "symbol" not in df.columns:
        return df

    for col in RANK_FEATURE_COLS:
        if col not in rank_cache.columns:
            continue
        df[col] = df["symbol"].map(rank_cache[col]).fillna(0.5)

    return df
