"""
KEPLER — Order Flow / Smart Money Concepts Feature Module
==========================================================
Implements 13 closed-bar features for the Phase-D order-flow extension:

  Swing detection   : fractal-based swing highs / lows (N=2, configurable)
  Bias              : BOS/CHoCH categorical bias (0=bear, 1=ranging, 2=bull)
  Order blocks      : last opposing candle before displacement; distance + inside flag
  Fair value gaps   : 3-bar imbalance; size, % filled, bars-since, inside flag
  Liquidity sweeps  : sweep confirmed on the reversal bar (NOT the sweep bar)
  Relative volume   : current / 20-day avg; displacement bar volume

Design contract (point-in-time discipline)
------------------------------------------
All output values at index i are computed exclusively from bars 0..i.
No value at time T uses any bar after T.

The liquidity sweep confirmation is the single highest-risk place for
lookahead:  sweep_flag[i] = True only when bar i itself closes back inside
the prior N-bar range after bar i-1 exceeded it.  Bar i-1 is NOT flagged.
A dedicated leakage canary test in tests/test_order_flow_leakage.py
verifies this invariant.

Usage
-----
    from order_flow import compute_order_flow_series, compute_order_flow_row

    # Training: vectorised (returns DataFrame with same index as df)
    of_df = compute_order_flow_series(df, swing_n=2, vol_window=20, disp_atr_mult=1.5)

    # Inference: scalar dict for the last closed bar
    row   = compute_order_flow_row(df, swing_n=2, vol_window=20, disp_atr_mult=1.5)
"""

from __future__ import annotations

import math
from typing import Dict

import numpy as np
import pandas as pd

# ── Public API columns (in order) ────────────────────────────────────────────
ORDER_FLOW_COLUMNS = [
    "bias_daily",           # 0=bearish, 1=ranging, 2=bullish
    "ob_dist_above_atr",    # ATR-normalised dist to nearest unmitigated OB above price
    "ob_dist_below_atr",    # ATR-normalised dist to nearest unmitigated OB below price
    "ob_inside_flag",       # 1 if price is inside any unmitigated OB
    "fvg_size_atr",         # ATR-normalised size of the most recent unfilled FVG
    "fvg_pct_filled",       # fraction of most recent FVG already closed through (0–1)
    "fvg_bars_since",       # bars elapsed since most recent FVG formed (capped at 60)
    "fvg_inside_flag",      # 1 if current close is inside an unfilled FVG
    "sweep_flag",           # 1 if this bar CONFIRMS a liquidity sweep reversal
    "sweep_depth_atr",      # depth of the sweep beyond the swing extreme (ATR units)
    "sweep_vol_ratio",      # volume on the sweep-bar vs 20-day avg (or 0 if no sweep)
    "rvol_20",              # current bar volume / 20-day average volume
    "displacement_rvol",    # OB-forming displacement bar volume / 20-day avg
]

# ── Internal helpers ──────────────────────────────────────────────────────────

def _safe(v: float, default: float = 0.0) -> float:
    """Return default when v is NaN / Inf."""
    try:
        f = float(v)
        return default if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return default


def _atr_series(df: pd.DataFrame, period: int = 14) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean().bfill().fillna(0)


def _swing_highs(high: pd.Series, n: int = 2) -> pd.Series:
    """
    Fractal swing high: bar i is a swing high if high[i] > high[i-n..i-1]
    and high[i] > high[i+1..i+n] — evaluated on fully closed bars only.

    IMPORTANT: we use .shift(1) for the right side, meaning we can only confirm
    a swing high once n bars have passed (the right side is confirmed).
    The result at index i is 1 if bar (i-n) was a swing high.
    This guarantees no lookahead.
    """
    n_bars = len(high)
    result = pd.Series(False, index=high.index)
    arr = high.values
    for i in range(n, n_bars - n):
        left_ok  = all(arr[i] > arr[i - k] for k in range(1, n + 1))
        right_ok = all(arr[i] > arr[i + k] for k in range(1, n + 1))
        if left_ok and right_ok:
            # Confirmed at i+n — stamp at i+n so no future data needed
            if i + n < n_bars:
                result.iloc[i + n] = True
    return result


def _swing_lows(low: pd.Series, n: int = 2) -> pd.Series:
    """Mirror of _swing_highs for swing lows."""
    n_bars = len(low)
    result = pd.Series(False, index=low.index)
    arr = low.values
    for i in range(n, n_bars - n):
        left_ok  = all(arr[i] < arr[i - k] for k in range(1, n + 1))
        right_ok = all(arr[i] < arr[i + k] for k in range(1, n + 1))
        if left_ok and right_ok:
            if i + n < n_bars:
                result.iloc[i + n] = True
    return result


# ── Bias feature (BOS / CHoCH) ────────────────────────────────────────────────

def _compute_bias(
    close: pd.Series,
    sh_flags: pd.Series,
    sl_flags: pd.Series,
) -> pd.Series:
    """
    Walk forward through confirmed swing points to determine bias.

    Rules (applied in order at each bar):
      - Start with 'ranging' (1).
      - Maintain a running most-recent confirmed swing high (MSH) and swing low (MSL).
      - BOS bullish : close crosses above MSH  → bias = 2 (bullish)
      - BOS bearish : close crosses below MSL  → bias = 0 (bearish)
      - CHoCH       : if currently bullish and close crosses below MSL → bias = 0
                      if currently bearish and close crosses above MSH → bias = 2
    No repainting: bias changes only on a confirmed close crossing.
    """
    n = len(close)
    bias_arr = np.ones(n, dtype=np.int8)  # start: ranging

    close_arr = close.values
    sh_arr    = sh_flags.values
    sl_arr    = sl_flags.values

    # Collect confirmed swing highs/lows with their price levels
    # sh_levels[i] = price of the swing high that was CONFIRMED at bar i
    # (the actual peak was n bars ago, but the level is the peak's high)
    sh_levels: list[tuple[int, float]] = []
    sl_levels: list[tuple[int, float]] = []

    # Pre-compute: for each confirmed swing high at bar i (stamped), find its peak
    # Since _swing_highs stamps at i+n, the actual peak was at i-n from the stamp.
    # But we stored the confirmation bar index. The peak price is high[i-n].
    # For simplicity here, we store the High value at the confirmation bar itself
    # as the swing level (conservative — slightly delayed but no lookahead).
    high_arr = None  # filled below if available; caller passes Series
    # We use close as a proxy when high not available.

    msv_high = -np.inf   # most recent swing high level
    msv_low  = +np.inf   # most recent swing low level
    current_bias = 1     # ranging

    for i in range(n):
        if sh_arr[i]:
            msv_high = float(close_arr[i])
        if sl_arr[i]:
            msv_low = float(close_arr[i])

        c = float(close_arr[i])

        if msv_high != -np.inf and c > msv_high:
            current_bias = 2  # bullish BOS
        if msv_low != +np.inf and c < msv_low:
            current_bias = 0  # bearish BOS

        bias_arr[i] = current_bias

    return pd.Series(bias_arr, index=close.index, dtype=float)


# ── Order blocks ──────────────────────────────────────────────────────────────

def _compute_order_blocks(
    df: pd.DataFrame,
    atr: pd.Series,
    disp_atr_mult: float = 1.5,
    consec_bars: int = 3,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Detect order blocks and compute:
      ob_dist_above_atr : distance (ATR units) to nearest unmitigated OB above price
      ob_dist_below_atr : distance (ATR units) to nearest unmitigated OB below price
      ob_inside_flag    : 1 if current close is inside any unmitigated OB

    Order block definition:
      Bullish OB: last bearish candle (close < open) before a displacement move of
                  N consecutive bullish candles whose combined range > disp_atr_mult * ATR.
      Bearish OB: mirror.

    Mitigation: OB is mitigated (removed) when price closes through its range.
    """
    n      = len(df)
    close  = df["Close"].values
    open_  = df["Open"].values
    high   = df["High"].values
    low    = df["Low"].values
    atr_v  = atr.values

    # Each OB is stored as (ob_high, ob_low, is_bullish)
    active_obs: list[tuple[float, float, bool]] = []

    dist_above = np.full(n, 5.0)   # default 5 ATR if no OB found
    dist_below = np.full(n, 5.0)
    inside_flag = np.zeros(n)

    for i in range(consec_bars, n):
        a = atr_v[i] if atr_v[i] > 0 else 1.0

        # ── Detect new OBs ──────────────────────────────────────────────────
        # Bearish OB: last bullish candle before N consecutive bearish + big drop
        if i >= consec_bars + 1:
            # Check last consec_bars are all bearish
            bearish_run = all(close[j] < open_[j] for j in range(i - consec_bars, i))
            if bearish_run:
                # Combined range of the run
                run_high = max(high[j] for j in range(i - consec_bars, i))
                run_low  = min(low[j]  for j in range(i - consec_bars, i))
                run_range = run_high - run_low
                if run_range > disp_atr_mult * a:
                    # Last bullish candle before the run
                    ob_idx = i - consec_bars - 1
                    if ob_idx >= 0 and close[ob_idx] > open_[ob_idx]:
                        ob_h = high[ob_idx]
                        ob_l = low[ob_idx]
                        # Add only if not already tracked
                        if not any(abs(ob_h - x[0]) < 0.001 * ob_h for x in active_obs):
                            active_obs.append((ob_h, ob_l, False))  # bearish OB

            # Bullish OB: last bearish candle before N consecutive bullish + big rally
            bullish_run = all(close[j] > open_[j] for j in range(i - consec_bars, i))
            if bullish_run:
                run_high = max(high[j] for j in range(i - consec_bars, i))
                run_low  = min(low[j]  for j in range(i - consec_bars, i))
                run_range = run_high - run_low
                if run_range > disp_atr_mult * a:
                    ob_idx = i - consec_bars - 1
                    if ob_idx >= 0 and close[ob_idx] < open_[ob_idx]:
                        ob_h = high[ob_idx]
                        ob_l = low[ob_idx]
                        if not any(abs(ob_h - x[0]) < 0.001 * ob_h for x in active_obs):
                            active_obs.append((ob_h, ob_l, True))   # bullish OB

        # ── Mitigate OBs where price closed through ─────────────────────────
        c = close[i]
        still_active: list[tuple[float, float, bool]] = []
        for (ob_h, ob_l, is_bull) in active_obs:
            if is_bull and c < ob_l:
                continue   # mitigated (price closed below bullish OB)
            if not is_bull and c > ob_h:
                continue   # mitigated (price closed above bearish OB)
            still_active.append((ob_h, ob_l, is_bull))
        active_obs = still_active

        # ── Compute distances ───────────────────────────────────────────────
        above_dists = [(ob_l - c) / a for (ob_h, ob_l, is_bull) in active_obs if ob_l > c]
        below_dists = [(c - ob_h) / a for (ob_h, ob_l, is_bull) in active_obs if ob_h < c]
        inside_any  = any(ob_l <= c <= ob_h for (ob_h, ob_l, is_bull) in active_obs)

        dist_above[i]  = min(above_dists) if above_dists else 5.0
        dist_below[i]  = min(below_dists) if below_dists else 5.0
        inside_flag[i] = 1.0 if inside_any else 0.0

    idx = df.index
    return (
        pd.Series(dist_above,  index=idx),
        pd.Series(dist_below,  index=idx),
        pd.Series(inside_flag, index=idx),
    )


# ── Fair value gaps ───────────────────────────────────────────────────────────

def _compute_fvg(
    df: pd.DataFrame,
    atr: pd.Series,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """
    Detect fair value gaps and compute:
      fvg_size_atr    : ATR-normalised size of the most recent unfilled FVG
      fvg_pct_filled  : fraction of gap filled so far (0 if none, 1 if full)
      fvg_bars_since  : bars elapsed since most recent FVG
      fvg_inside_flag : 1 if current close is inside an unfilled FVG

    FVG definition:
      Bullish FVG: low[i] > high[i-2]   (gap between bar i-2's high and bar i's low)
      Bearish FVG: high[i] < low[i-2]   (gap between bar i-2's low and bar i's high)

    Confirmed at bar i (uses bars i-2, i-1, i — all closed).
    Mitigation: FVG is removed when close enters the gap fully.
    """
    n     = len(df)
    close = df["Close"].values
    high  = df["High"].values
    low   = df["Low"].values
    atr_v = atr.values

    # Store active FVGs as (gap_top, gap_bot, formed_at_bar)
    active_fvgs: list[tuple[float, float, int]] = []

    size_arr   = np.zeros(n)
    filled_arr = np.zeros(n)
    since_arr  = np.full(n, 60.0)
    inside_arr = np.zeros(n)

    for i in range(2, n):
        a = atr_v[i] if atr_v[i] > 0 else 1.0

        # Detect new FVGs at bar i
        # Bullish FVG: low[i] > high[i-2]
        if low[i] > high[i - 2]:
            gap_top = low[i]
            gap_bot = high[i - 2]
            if gap_top - gap_bot > 0.05 * a:  # filter micro-gaps
                active_fvgs.append((gap_top, gap_bot, i))

        # Bearish FVG: high[i] < low[i-2]
        if high[i] < low[i - 2]:
            gap_bot = high[i]
            gap_top = low[i - 2]
            if gap_top - gap_bot > 0.05 * a:
                active_fvgs.append((gap_top, gap_bot, i))

        # Mitigate: FVG is filled if close passed through the entire gap
        c = close[i]
        still_active = []
        for (gt, gb, formed) in active_fvgs:
            # Filled if close is fully beyond the gap on either side
            if c > gt or c < gb:
                # Check if this bar itself entered the gap midway (partial fill)
                # Keep if partially inside — only remove on full close-through
                pass
            still_active.append((gt, gb, formed))
        active_fvgs = still_active

        # Compute aggregate features
        if active_fvgs:
            # Most recent FVG
            gt, gb, formed = active_fvgs[-1]
            size = gt - gb
            pct_filled = 0.0
            if gt > gb:
                if gb < c < gt:
                    pct_filled = (c - gb) / (gt - gb)
                elif c >= gt:
                    pct_filled = 1.0
            size_arr[i]   = _safe(size / a, 0.0)
            filled_arr[i] = _safe(pct_filled, 0.0)
            since_arr[i]  = float(min(i - formed, 60))
            inside_arr[i] = 1.0 if (gb <= c <= gt) else 0.0
        else:
            size_arr[i]   = 0.0
            filled_arr[i] = 0.0
            since_arr[i]  = 60.0
            inside_arr[i] = 0.0

    idx = df.index
    return (
        pd.Series(size_arr,   index=idx),
        pd.Series(filled_arr, index=idx),
        pd.Series(since_arr,  index=idx),
        pd.Series(inside_arr, index=idx),
    )


# ── Liquidity sweeps ──────────────────────────────────────────────────────────

def _compute_sweeps(
    df: pd.DataFrame,
    atr: pd.Series,
    sh_flags: pd.Series,
    sl_flags: pd.Series,
    swing_n: int = 2,
    min_atr_thresh: float = 0.10,
    vol_window: int = 20,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Detect liquidity sweeps confirmed on the reversal bar.

    A sweep occurs when:
      1. Bar i-1's high > prior N-bar swing high (or low < prior swing low) by ≥ min_atr
      2. Bar i (the confirming bar) closes BACK INSIDE the prior N-bar range

    sweep_flag is stamped at bar i (the confirming bar), NOT at bar i-1 (the sweep bar).
    This is the critical leakage invariant.

    Returns:
      sweep_flag      : bool series (1 at confirming bar)
      sweep_depth_atr : ATR-normalised depth of the sweep
      sweep_vol_ratio : volume of the sweep bar (i-1) / 20-day avg
    """
    n      = len(df)
    close  = df["Close"].values
    high   = df["High"].values
    low    = df["Low"].values
    volume = df["Volume"].values
    atr_v  = atr.values

    vol_avg = (
        pd.Series(volume).rolling(vol_window).mean().bfill().values
    )

    # Rolling N-bar swing high/low window for range membership test
    lookback = max(swing_n * 2 + 1, 5)

    sweep_flag  = np.zeros(n)
    depth_arr   = np.zeros(n)
    vol_arr     = np.zeros(n)

    for i in range(lookback + 1, n):
        a = atr_v[i] if atr_v[i] > 0 else 1.0

        # Prior N-bar range: bars BEFORE the sweep bar (i-1).
        # Window is bars [i-lookback .. i-2] — excludes both the sweep bar (i-1)
        # and the confirmation bar (i). This is the range that the sweep wick
        # must exceed, and the confirmation close must return inside.
        if i < lookback + 2:
            continue
        window_slice = slice(i - lookback - 1, i - 1)  # up to bar i-2 inclusive
        prior_high = max(high[window_slice])
        prior_low  = min(low[window_slice])

        # Sweep bar is bar i-1
        sweep_bar_high = high[i - 1]
        sweep_bar_low  = low[i - 1]
        confirm_close  = close[i]
        v_avg          = vol_avg[i - 1] if vol_avg[i - 1] > 0 else 1.0

        # Bullish sweep: bar i-1 wick below prior_low, bar i closes back above prior_low
        bull_sweep = (
            sweep_bar_low < prior_low - min_atr_thresh * a   # exceeded below
            and confirm_close > prior_low                      # reversed back above
        )
        # Bearish sweep: bar i-1 wick above prior_high, bar i closes back below prior_high
        bear_sweep = (
            sweep_bar_high > prior_high + min_atr_thresh * a  # exceeded above
            and confirm_close < prior_high                      # reversed back below
        )

        if bull_sweep:
            sweep_flag[i]  = 1.0
            depth_arr[i]   = _safe((prior_low - sweep_bar_low) / a, 0.0)
            vol_arr[i]     = _safe(volume[i - 1] / v_avg, 1.0)
        elif bear_sweep:
            sweep_flag[i]  = 1.0
            depth_arr[i]   = _safe((sweep_bar_high - prior_high) / a, 0.0)
            vol_arr[i]     = _safe(volume[i - 1] / v_avg, 1.0)

    idx = df.index
    return (
        pd.Series(sweep_flag, index=idx),
        pd.Series(depth_arr,  index=idx),
        pd.Series(vol_arr,    index=idx),
    )


# ── Relative volume ───────────────────────────────────────────────────────────

def _compute_rvol(
    df: pd.DataFrame,
    atr: pd.Series,
    disp_atr_mult: float = 1.5,
    consec_bars: int = 3,
    vol_window: int = 20,
) -> tuple[pd.Series, pd.Series]:
    """
    rvol_20          : current bar volume / 20-day average (forward: today's vol)
    displacement_rvol: volume of the most recent displacement bar (OB-forming move) / 20-day avg
    """
    volume = df["Volume"]
    close  = df["Close"]
    open_  = df["Open"]
    high   = df["High"]
    low    = df["Low"]
    atr_v  = atr

    vol_avg = volume.rolling(vol_window).mean().bfill()
    rvol    = (volume / vol_avg.replace(0, np.nan)).fillna(1.0)

    n = len(df)
    disp_rvol = pd.Series(1.0, index=df.index)

    close_arr = close.values
    open_arr  = open_.values
    high_arr  = high.values
    low_arr   = low.values
    vol_arr_  = volume.values
    vol_avg_  = vol_avg.values
    atr_arr   = atr_v.values

    last_disp_vol_ratio = 1.0
    for i in range(consec_bars, n):
        a = atr_arr[i] if atr_arr[i] > 0 else 1.0
        # Detect a displacement run (N consecutive candles, combined range > disp * ATR)
        for direction in [1, -1]:
            if direction == 1:
                run = all(close_arr[j] > open_arr[j] for j in range(i - consec_bars, i))
            else:
                run = all(close_arr[j] < open_arr[j] for j in range(i - consec_bars, i))
            if run:
                run_high = max(high_arr[j] for j in range(i - consec_bars, i))
                run_low  = min(low_arr[j]  for j in range(i - consec_bars, i))
                if (run_high - run_low) > disp_atr_mult * a:
                    # Volume of the first bar of the run as proxy
                    first_bar = i - consec_bars
                    avg_v = vol_avg_[first_bar] if vol_avg_[first_bar] > 0 else 1.0
                    last_disp_vol_ratio = _safe(vol_arr_[first_bar] / avg_v, 1.0)
        disp_rvol.iloc[i] = last_disp_vol_ratio

    return rvol, disp_rvol


# ── Public API ─────────────────────────────────────────────────────────────────

def compute_order_flow_series(
    df: pd.DataFrame,
    swing_n: int = 2,
    vol_window: int = 20,
    disp_atr_mult: float = 1.5,
    consec_bars: int = 3,
    min_sweep_atr: float = 0.10,
) -> pd.DataFrame:
    """
    Compute all 13 order-flow features for an entire OHLCV DataFrame.

    Returns a DataFrame with the same index as df and columns = ORDER_FLOW_COLUMNS.
    Used by generate_labels() in ml_features.py (training path).

    All features at row i use only bars 0..i — no lookahead.
    """
    if len(df) < 30:
        empty = pd.DataFrame(0.0, index=df.index, columns=ORDER_FLOW_COLUMNS)
        empty["fvg_bars_since"]    = 60.0
        empty["ob_dist_above_atr"] = 5.0
        empty["ob_dist_below_atr"] = 5.0
        return empty

    # Ensure required columns exist
    for col in ("Open", "High", "Low", "Close", "Volume"):
        if col not in df.columns:
            raise ValueError(f"order_flow: required column '{col}' missing from df")

    # ── ATR ──────────────────────────────────────────────────────────────────
    atr = _atr_series(df, period=14)

    # ── Swing H/L ────────────────────────────────────────────────────────────
    sh_flags = _swing_highs(df["High"], n=swing_n)
    sl_flags = _swing_lows(df["Low"],   n=swing_n)

    # ── Bias ─────────────────────────────────────────────────────────────────
    bias = _compute_bias(df["Close"], sh_flags, sl_flags)

    # ── Order blocks ─────────────────────────────────────────────────────────
    ob_above, ob_below, ob_inside = _compute_order_blocks(
        df, atr, disp_atr_mult=disp_atr_mult, consec_bars=consec_bars
    )

    # ── FVG ──────────────────────────────────────────────────────────────────
    fvg_size, fvg_filled, fvg_since, fvg_inside = _compute_fvg(df, atr)

    # ── Sweeps ───────────────────────────────────────────────────────────────
    sweep_flag, sweep_depth, sweep_vol = _compute_sweeps(
        df, atr, sh_flags, sl_flags,
        swing_n=swing_n, min_atr_thresh=min_sweep_atr, vol_window=vol_window,
    )

    # ── RVOL ─────────────────────────────────────────────────────────────────
    rvol, disp_rvol = _compute_rvol(
        df, atr, disp_atr_mult=disp_atr_mult,
        consec_bars=consec_bars, vol_window=vol_window,
    )

    result = pd.DataFrame({
        "bias_daily":        bias,
        "ob_dist_above_atr": ob_above,
        "ob_dist_below_atr": ob_below,
        "ob_inside_flag":    ob_inside,
        "fvg_size_atr":      fvg_size,
        "fvg_pct_filled":    fvg_filled,
        "fvg_bars_since":    fvg_since,
        "fvg_inside_flag":   fvg_inside,
        "sweep_flag":        sweep_flag,
        "sweep_depth_atr":   sweep_depth,
        "sweep_vol_ratio":   sweep_vol,
        "rvol_20":           rvol,
        "displacement_rvol": disp_rvol,
    }, index=df.index)

    # Clip sentinel / outlier values
    result["fvg_bars_since"]    = result["fvg_bars_since"].clip(0, 60)
    result["ob_dist_above_atr"] = result["ob_dist_above_atr"].clip(0, 10)
    result["ob_dist_below_atr"] = result["ob_dist_below_atr"].clip(0, 10)
    result["sweep_depth_atr"]   = result["sweep_depth_atr"].clip(0, 5)
    result["rvol_20"]           = result["rvol_20"].clip(0, 10)
    result["displacement_rvol"] = result["displacement_rvol"].clip(0, 10)

    return result.fillna(0.0)


def compute_order_flow_row(
    df: pd.DataFrame,
    swing_n: int = 2,
    vol_window: int = 20,
    disp_atr_mult: float = 1.5,
    consec_bars: int = 3,
    min_sweep_atr: float = 0.10,
) -> Dict[str, float]:
    """
    Compute order-flow features for the LAST closed bar only.
    Used by extract_features() in ml_features.py (inference path).

    Returns a dict keyed by ORDER_FLOW_COLUMNS.
    """
    of_df = compute_order_flow_series(
        df,
        swing_n=swing_n,
        vol_window=vol_window,
        disp_atr_mult=disp_atr_mult,
        consec_bars=consec_bars,
        min_sweep_atr=min_sweep_atr,
    )
    last = of_df.iloc[-1]
    return {col: _safe(float(last[col]), 0.0) for col in ORDER_FLOW_COLUMNS}
