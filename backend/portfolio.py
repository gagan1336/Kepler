"""
KEPLER — Portfolio & Risk Layer (Phase G)
==========================================
Given a list of model signals (buy probabilities + meta probabilities),
constructs a position-sized portfolio respecting:

  • ATR-scaled position sizing — risk 1% of capital per trade
  • Max 5% per single name
  • Max 25% per sector
  • Correlation cap — two stocks with 90d correlation > 0.80 share a
    combined position limit
  • Stress tests — P&L impact of rate-hike, crude-spike, INR-depreciation

This module is NOT a trading system — it produces a SIZING PLAN.
All execution decisions remain with the user.

Usage
-----
    from portfolio import build_portfolio, stress_test_portfolio

    plan = build_portfolio(
        signals,            # DataFrame: symbol, sector, buy_prob, meta_prob, atr
        portfolio_value=1_000_000,
        meta_threshold=0.65,
    )
    stress_test_portfolio(plan, portfolio_value=1_000_000)
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_RISK_PER_TRADE     = 0.01   # 1% of portfolio per trade (ATR-based)
MAX_SINGLE_NAME_PCT    = 0.05   # 5% max in any single stock
MAX_SECTOR_PCT         = 0.25   # 25% max in any one sector
MAX_CORR_COMBINED_PCT  = 0.08   # if two stocks corr > 0.80, their COMBINED size ≤ 8%
HIGH_CORR_THRESHOLD    = 0.80   # 90-day correlation above this = "same bet"

_BACKEND_DIR = Path(__file__).parent
_CONFIGS_DIR = _BACKEND_DIR / "configs" / "experiment_runs"
_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Sector beta assumptions for stress tests ──────────────────────────────────
# Impact on expected 10-day return for each scenario (rough empirical estimates
# for NSE mid/large caps — NOT backtested, use for directional risk awareness only)
STRESS_SCENARIOS = {
    "rate_hike_200bps": {
        # RBI surprise 200bps hike — historically hits NBFCs, real estate hard,
        # benefits short-duration banks modestly
        "sector_betas": {
            "Banking":     -0.05,
            "NBFC":        -0.12,
            "Real_Estate": -0.15,
            "IT":          -0.03,
            "Pharma":       0.00,
            "Auto":        -0.06,
            "Energy":      -0.02,
            "FMCG":        -0.03,
            "Industrials": -0.04,
            "default":     -0.05,
        },
        "description": "RBI surprise rate hike +200bps",
    },
    "crude_spike_30pct": {
        # Brent crude +30% in 1 month
        "sector_betas": {
            "Banking":      0.00,
            "NBFC":         0.00,
            "Real_Estate":  0.00,
            "IT":          -0.02,
            "Pharma":      -0.01,
            "Auto":        -0.10,  # input cost / demand hit
            "Energy":      +0.15,  # upstream oil gainers
            "FMCG":        -0.04,  # logistics cost
            "Industrials": -0.05,
            "default":     -0.03,
        },
        "description": "Brent crude price +30%",
    },
    "inr_depreciation_10pct": {
        # USD/INR moves from ~84 to ~92
        "sector_betas": {
            "Banking":      0.00,
            "NBFC":         0.00,
            "Real_Estate": -0.03,
            "IT":          +0.12,  # USD revenue exporters benefit
            "Pharma":      +0.08,  # export-heavy benefit
            "Auto":        -0.05,  # imported components cost up
            "Energy":      -0.08,  # crude import cost up (INR terms)
            "FMCG":        -0.03,
            "Industrials": -0.03,
            "default":      0.00,
        },
        "description": "INR depreciates 10% vs USD",
    },
}


# ── ATR-based position sizing ─────────────────────────────────────────────────
def size_positions(
    signals: pd.DataFrame,
    portfolio_value: float,
    atr_col: str = "atr_14",
    price_col: str = "close",
) -> pd.DataFrame:
    """
    Compute ATR-scaled position sizes.

    For each signal:
      risk_amount     = portfolio_value * MAX_RISK_PER_TRADE
      stop_distance   = atr_14 * 2  (2-ATR stop loss)
      raw_shares      = risk_amount / stop_distance
      raw_position    = raw_shares * price
      position_pct    = min(raw_position / portfolio_value, MAX_SINGLE_NAME_PCT)

    Parameters
    ----------
    signals         : DataFrame with columns [symbol, sector, buy_prob,
                      atr_14 (or atr_col), close (or price_col)]
    portfolio_value : Total portfolio capital in INR
    """
    df = signals.copy()

    # Ensure required columns exist
    for col in [atr_col, price_col]:
        if col not in df.columns:
            df[col] = np.nan

    df["stop_distance"] = df[atr_col].fillna(df[price_col] * 0.02) * 2
    df["risk_amount"]   = portfolio_value * MAX_RISK_PER_TRADE
    df["raw_shares"]    = (df["risk_amount"] / df["stop_distance"]).clip(lower=0)
    df["raw_position"]  = df["raw_shares"] * df[price_col].fillna(100)
    df["raw_pct"]       = (df["raw_position"] / portfolio_value).clip(0, MAX_SINGLE_NAME_PCT)

    # Confidence-scale: multiply by min(buy_prob * 2, 1.0) if meta_prob present
    if "meta_prob" in df.columns:
        confidence_scale = (df["meta_prob"] * 1.5).clip(0, 1.0)
        df["position_pct"] = (df["raw_pct"] * confidence_scale).clip(0, MAX_SINGLE_NAME_PCT)
    else:
        df["position_pct"] = df["raw_pct"]

    df["position_inr"] = (df["position_pct"] * portfolio_value).round(0)
    return df


def apply_sector_cap(df: pd.DataFrame, portfolio_value: float) -> pd.DataFrame:
    """
    Scale down positions so no sector exceeds MAX_SECTOR_PCT.
    Scales all positions in an over-allocated sector proportionally.
    """
    df = df.copy()
    if "sector" not in df.columns:
        return df

    for sector, group in df.groupby("sector"):
        total_pct = group["position_pct"].sum()
        if total_pct > MAX_SECTOR_PCT:
            scale = MAX_SECTOR_PCT / total_pct
            df.loc[group.index, "position_pct"] *= scale
            logger.info(
                f"  ⚠️  Sector cap: {sector} was {total_pct:.1%} → scaled to {MAX_SECTOR_PCT:.0%}"
            )

    df["position_inr"] = (df["position_pct"] * portfolio_value).round(0)
    return df


def apply_correlation_cap(
    df: pd.DataFrame,
    corr_matrix: Optional[pd.DataFrame],
    portfolio_value: float,
) -> pd.DataFrame:
    """
    If two selected stocks have 90-day correlation > HIGH_CORR_THRESHOLD,
    their COMBINED position is capped at MAX_CORR_COMBINED_PCT.

    corr_matrix : square DataFrame of (symbol × symbol) correlations.
                  If None, skip this step.
    """
    if corr_matrix is None or corr_matrix.empty:
        return df

    df = df.copy()
    symbols = df["symbol"].tolist()
    processed_pairs = set()

    for i, sym_a in enumerate(symbols):
        for sym_b in symbols[i+1:]:
            pair = frozenset([sym_a, sym_b])
            if pair in processed_pairs:
                continue
            processed_pairs.add(pair)

            try:
                corr = corr_matrix.loc[sym_a, sym_b]
            except KeyError:
                continue

            if abs(corr) > HIGH_CORR_THRESHOLD:
                idx_a = df[df["symbol"] == sym_a].index
                idx_b = df[df["symbol"] == sym_b].index
                if len(idx_a) == 0 or len(idx_b) == 0:
                    continue
                combined = df.loc[idx_a[0], "position_pct"] + df.loc[idx_b[0], "position_pct"]
                if combined > MAX_CORR_COMBINED_PCT:
                    scale = MAX_CORR_COMBINED_PCT / combined
                    df.loc[idx_a[0], "position_pct"] *= scale
                    df.loc[idx_b[0], "position_pct"] *= scale
                    logger.info(
                        f"  ⚠️  Corr cap: {sym_a}↔{sym_b} (corr={corr:.2f}) "
                        f"combined {combined:.1%} → {MAX_CORR_COMBINED_PCT:.0%}"
                    )

    df["position_inr"] = (df["position_pct"] * portfolio_value).round(0)
    return df


# ── Stress testing ────────────────────────────────────────────────────────────
def stress_test_portfolio(
    df: pd.DataFrame,
    portfolio_value: float,
    save: bool = True,
) -> Dict:
    """
    Estimate portfolio P&L impact under each macro stress scenario.
    Uses sector-level beta assumptions (see STRESS_SCENARIOS).

    Returns dict of {scenario_name: {pnl_inr, pnl_pct, per_stock}} 
    and prints a summary table.
    """
    results = {}

    logger.info(f"\n{'═'*60}")
    logger.info("  STRESS TEST RESULTS")
    logger.info(f"  Portfolio value: ₹{portfolio_value:,.0f}")
    logger.info(f"{'═'*60}")

    for scenario_name, scenario in STRESS_SCENARIOS.items():
        betas    = scenario["sector_betas"]
        desc     = scenario["description"]
        per_stock = []
        total_pnl = 0.0

        for _, row in df.iterrows():
            sector    = row.get("sector", "default")
            beta      = betas.get(sector, betas.get("default", 0.0))
            pos_inr   = float(row.get("position_inr", 0))
            pnl_stock = pos_inr * beta
            total_pnl += pnl_stock
            per_stock.append({
                "symbol":    row.get("symbol", "?"),
                "sector":    sector,
                "pos_inr":   round(pos_inr, 0),
                "beta":      beta,
                "pnl_inr":   round(pnl_stock, 0),
            })

        pnl_pct = (total_pnl / portfolio_value) * 100
        results[scenario_name] = {
            "description": desc,
            "pnl_inr":     round(total_pnl, 0),
            "pnl_pct":     round(pnl_pct, 2),
            "per_stock":   per_stock,
        }

        impact_str = f"₹{total_pnl:+,.0f} ({pnl_pct:+.1f}%)"
        flag = "🟢" if pnl_pct > -3 else ("🟡" if pnl_pct > -7 else "🔴")
        logger.info(f"  {flag} {desc:<40} {impact_str}")

    logger.info(f"{'═'*60}\n")

    if save:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = _CONFIGS_DIR / f"stress_{ts}.json"
        path.write_text(json.dumps(results, indent=2))
        logger.info(f"💾 Stress test saved → {path}")

    return results


# ── End-to-end portfolio builder ──────────────────────────────────────────────
def build_portfolio(
    signals: pd.DataFrame,
    portfolio_value: float = 1_000_000,
    meta_threshold: float = 0.65,
    primary_threshold: float = 0.40,
    corr_matrix: Optional[pd.DataFrame] = None,
    run_stress: bool = True,
) -> pd.DataFrame:
    """
    Full pipeline: signals → filter → size → sector cap → corr cap → stress test.

    Parameters
    ----------
    signals             : DataFrame with at minimum:
                          symbol, sector, buy_prob, [meta_prob], atr_14, close
    portfolio_value     : INR capital to deploy
    meta_threshold      : only include signals where meta_prob >= this
    primary_threshold   : only include signals where buy_prob >= this
    corr_matrix         : optional (symbol×symbol) correlation matrix
    run_stress          : whether to print + save stress test results

    Returns
    -------
    DataFrame with sizing plan — one row per trade to consider.
    """
    df = signals.copy()

    # ── 1. Filter by thresholds ────────────────────────────────────────────────
    mask = df["buy_prob"] >= primary_threshold
    if "meta_prob" in df.columns:
        mask &= df["meta_prob"] >= meta_threshold
    df = df[mask].copy()

    if df.empty:
        logger.warning("No signals pass the thresholds — try lowering primary/meta thresholds")
        return df

    logger.info(f"📋 {len(df)} signals pass thresholds "
                f"(primary≥{primary_threshold}, meta≥{meta_threshold})")

    # ── 2. Sort by combined confidence ────────────────────────────────────────
    if "meta_prob" in df.columns:
        df["combined_score"] = df["buy_prob"] * df["meta_prob"]
    else:
        df["combined_score"] = df["buy_prob"]
    df = df.sort_values("combined_score", ascending=False).reset_index(drop=True)

    # ── 3. Size positions ──────────────────────────────────────────────────────
    df = size_positions(df, portfolio_value)

    # ── 4. Sector cap ─────────────────────────────────────────────────────────
    df = apply_sector_cap(df, portfolio_value)

    # ── 5. Correlation cap ────────────────────────────────────────────────────
    df = apply_correlation_cap(df, corr_matrix, portfolio_value)

    # ── 6. Final total check ──────────────────────────────────────────────────
    total_deployed = df["position_pct"].sum()
    if total_deployed > 0.95:
        # Scale entire portfolio to leave 5% cash buffer
        scale = 0.95 / total_deployed
        df["position_pct"] *= scale
        df["position_inr"]  = (df["position_pct"] * portfolio_value).round(0)
        logger.info(f"  📉 Total deployment {total_deployed:.1%} → scaled to 95% (5% cash buffer)")

    logger.info(f"\n{'─'*55}")
    logger.info(f"{'Symbol':<15} {'Sector':<14} {'Score':>6} {'Size%':>6} {'₹ Size':>10}")
    logger.info(f"{'─'*55}")
    for _, row in df.iterrows():
        logger.info(
            f"  {row.get('symbol','?'):<13} {row.get('sector','?'):<14} "
            f"  {row.get('combined_score',0):.3f}  {row['position_pct']:.1%}  "
            f"  ₹{row['position_inr']:>8,.0f}"
        )
    logger.info(f"{'─'*55}")
    logger.info(f"  Total deployed: {df['position_pct'].sum():.1%} "
                f"(₹{df['position_inr'].sum():,.0f})")

    # ── 7. Stress test ────────────────────────────────────────────────────────
    if run_stress and len(df) > 0:
        stress_test_portfolio(df, portfolio_value)

    return df


# ── CLI demo ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from loguru import logger as log

    log.remove()
    log.add(sys.stderr, level="INFO",
            format="<green>{time:HH:mm:ss}</green> | {message}")

    # Demo with synthetic signals
    demo_signals = pd.DataFrame([
        {"symbol": "PERSISTENT",  "sector": "IT",          "buy_prob": 0.72, "meta_prob": 0.68, "atr_14": 45,  "close": 5800},
        {"symbol": "BANKBARODA",  "sector": "Banking",     "buy_prob": 0.65, "meta_prob": 0.71, "atr_14": 6,   "close": 245},
        {"symbol": "TORNTPHARM",  "sector": "Pharma",      "buy_prob": 0.61, "meta_prob": 0.66, "atr_14": 25,  "close": 3100},
        {"symbol": "TVSMOTOR",    "sector": "Auto",        "buy_prob": 0.69, "meta_prob": 0.73, "atr_14": 35,  "close": 2400},
        {"symbol": "ADANIGREEN",  "sector": "Energy",      "buy_prob": 0.58, "meta_prob": 0.65, "atr_14": 30,  "close": 1100},
        {"symbol": "FEDERALBNK",  "sector": "Banking",     "buy_prob": 0.63, "meta_prob": 0.67, "atr_14": 3,   "close": 180},
        {"symbol": "COFORGE",     "sector": "IT",          "buy_prob": 0.71, "meta_prob": 0.69, "atr_14": 80,  "close": 8900},
        {"symbol": "HAVELLS",     "sector": "Industrials", "buy_prob": 0.67, "meta_prob": 0.70, "atr_14": 28,  "close": 1950},
    ])

    log.info("=" * 60)
    log.info("  KEPLER PORTFOLIO BUILDER — Demo")
    log.info("=" * 60)

    plan = build_portfolio(
        demo_signals,
        portfolio_value=1_000_000,
        meta_threshold=0.65,
        primary_threshold=0.40,
    )
