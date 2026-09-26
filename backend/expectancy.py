"""
KEPLER — Expectancy & Transaction Cost Analysis
=================================================
Answers the question the precision table cannot: does this strategy make money?

  Expectancy = (hit_rate × avg_win%) − (miss_rate × avg_loss%)

If expectancy is positive, the strategy has an edge in ₹ terms, not just hit-rate terms.
If it's negative, a 33% hit rate means the wins are too small vs. the losses.

Also models realistic NSE transaction costs (STT, brokerage, slippage) to compute
net expectancy after friction — the real go/no-go number before paper trading.

Usage
-----
    python expectancy.py --holdout-yaml configs/frozen_holdout.yaml
    python expectancy.py --oof-pkl configs/experiment_runs/oof_predictions.pkl

Output
------
    Table printed to console + saved to configs/experiment_runs/expectancy_<ts>.json
"""

from __future__ import annotations

import json
import sys
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from loguru import logger

warnings.filterwarnings("ignore")

_BACKEND_DIR = Path(__file__).parent
_CONFIGS_DIR = _BACKEND_DIR / "configs" / "experiment_runs"
_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH  = _BACKEND_DIR / "models" / "kepler_model.pkl"
SCALER_PATH = _BACKEND_DIR / "models" / "kepler_scaler.pkl"
META_MODEL  = _BACKEND_DIR / "models" / "meta_model.pkl"
META_SCALER = _BACKEND_DIR / "models" / "meta_scaler.pkl"


# ── NSE Transaction Cost Model ───────────────────────────────────────────────
# Sources: NSE circular, Zerodha fee schedule (2024), typical mid-cap spreads
# All figures are one-way per trade as a % of trade value, unless noted

NSE_COSTS = {
    # STT: 0.1% on delivery sell (buy side exempt for delivery)
    "stt_delivery_sell_pct":   0.001,
    # STT: 0.025% both sides for intraday — we model swing (delivery)
    # Exchange + SEBI transaction charges
    "exchange_charges_pct":    0.0000345,  # NSE: 0.00345% (0.0000345 of turnover)
    "sebi_charges_pct":        0.000001,   # ₹10/crore = 0.000001%
    # GST on brokerage (18%)
    # Brokerage: flat ₹20/trade or 0.03% whichever lower (Zerodha/Groww model)
    "brokerage_flat_inr":      20.0,       # per leg (buy + sell = ₹40 total)
    "brokerage_pct_cap":       0.0003,     # 0.03% of trade value per leg
    # Stamp duty (0.015% on buy side only, delivery)
    "stamp_duty_buy_pct":      0.00015,
    # Slippage (bid-ask spread + market impact, estimated for Nifty200 mid-caps)
    "slippage_pct":            0.001,      # 0.10% one-way (conservative for liquid mid-caps)
}

# Total round-trip cost estimate for a ₹50,000 trade:
# Buy leg:  stamp(0.015%) + exchange(0.00345%) + SEBI + brokerage(min ₹20) + slippage(0.1%)
# Sell leg: STT(0.1%) + exchange(0.00345%) + SEBI + brokerage(min ₹20) + slippage(0.1%)
# ≈ 0.001+0.001+0.0000345+0.000001+0.0003+0.00015+0.0000345+0.000001+0.0003 ≈ 0.0038 = 0.38%
# + 2×slippage = 0.20% → total ≈ 0.58% round-trip for a ₹50k trade


def compute_round_trip_cost_pct(
    trade_value_inr: float = 50_000,
    costs: dict = None,
) -> float:
    """
    Compute total round-trip transaction cost as a % of trade value.
    Includes STT, exchange charges, SEBI fee, stamp duty, brokerage, slippage.
    """
    if costs is None:
        costs = NSE_COSTS

    # Buy leg
    brokerage_buy = min(
        costs["brokerage_flat_inr"],
        trade_value_inr * costs["brokerage_pct_cap"],
    )
    buy_cost = (
        trade_value_inr * costs["stamp_duty_buy_pct"]
        + trade_value_inr * costs["exchange_charges_pct"]
        + trade_value_inr * costs["sebi_charges_pct"]
        + brokerage_buy * 1.18  # GST on brokerage
        + trade_value_inr * costs["slippage_pct"]
    )

    # Sell leg
    brokerage_sell = min(
        costs["brokerage_flat_inr"],
        trade_value_inr * costs["brokerage_pct_cap"],
    )
    sell_cost = (
        trade_value_inr * costs["stt_delivery_sell_pct"]
        + trade_value_inr * costs["exchange_charges_pct"]
        + trade_value_inr * costs["sebi_charges_pct"]
        + brokerage_sell * 1.18
        + trade_value_inr * costs["slippage_pct"]
    )

    total_cost_inr = buy_cost + sell_cost
    return (total_cost_inr / trade_value_inr) * 100   # as a % of trade value


def expectancy_table(
    df: pd.DataFrame,
    thresholds: list[float] = None,
    trade_value_inr: float = 50_000,
    score_col: str = "y_score",
    ret_col: str = "fwd_ret_raw",
    label_col: str = "y_true",
) -> list[dict]:
    """
    Compute expectancy at each confidence threshold, before and after costs.

    For rows where model score >= threshold:
      hit_rate      = fraction where label == 1
      avg_win_pct   = mean(fwd_ret_raw | label == 1)   [wins only]
      avg_loss_pct  = mean(fwd_ret_raw | label == 0)   [losses only, negative]
      gross_exp     = hit_rate * avg_win + (1-hit_rate) * avg_loss
      cost_pct      = round-trip transaction cost %
      net_exp       = gross_exp - cost_pct

    Parameters
    ----------
    df            : DataFrame with score_col, ret_col, label_col
    thresholds    : list of probability thresholds to sweep
    trade_value_inr: typical position size for cost calculation
    """
    if thresholds is None:
        thresholds = [0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]

    cost_pct = compute_round_trip_cost_pct(trade_value_inr)

    rows = []
    for thr in thresholds:
        mask = df[score_col] >= thr
        subset = df[mask]
        if len(subset) < 10:
            continue

        wins   = subset[subset[label_col] == 1]
        losses = subset[subset[label_col] == 0]

        hit_rate   = len(wins) / len(subset)
        avg_win    = float(wins[ret_col].mean())    if len(wins)   > 0 else 0.0
        avg_loss   = float(losses[ret_col].mean())  if len(losses) > 0 else 0.0
        gross_exp  = hit_rate * avg_win + (1 - hit_rate) * avg_loss
        net_exp    = gross_exp - cost_pct

        rows.append({
            "threshold":   thr,
            "n_trades":    int(len(subset)),
            "hit_rate":    round(hit_rate, 4),
            "avg_win_pct": round(avg_win, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "gross_exp":   round(gross_exp, 3),
            "cost_pct":    round(cost_pct, 3),
            "net_exp":     round(net_exp, 3),
            "verdict":     "✅ Edge" if net_exp > 0 else "🔴 No edge after costs",
        })

    return rows


def print_expectancy_table(rows: list[dict], base_rate: float) -> None:
    logger.info(f"\n{'═'*80}")
    logger.info("  EXPECTANCY TABLE — Clean Holdout (after NSE transaction costs)")
    logger.info(f"{'═'*80}")
    logger.info(
        f"  {'Thr':>4}  {'N':>7}  {'Hit%':>6}  {'AvgWin':>7}  "
        f"{'AvgLoss':>8}  {'GrossExp':>9}  {'Cost':>5}  {'NetExp':>7}  {'Verdict'}"
    )
    logger.info(f"  {'─'*76}")
    for r in rows:
        logger.info(
            f"  {r['threshold']:>4.2f}  {r['n_trades']:>7,}  {r['hit_rate']:>5.1%}  "
            f"  {r['avg_win_pct']:>+6.2f}%  {r['avg_loss_pct']:>+7.2f}%  "
            f"  {r['gross_exp']:>+8.3f}%  {r['cost_pct']:>4.2f}%  "
            f"  {r['net_exp']:>+6.3f}%  {r['verdict']}"
        )
    logger.info(f"  {'─'*76}")
    logger.info(f"  Base rate (random pick): {base_rate:.1%}")
    logger.info(f"  Cost model: NSE delivery, ₹50k trade ≈ 0.58% round-trip")
    logger.info(f"{'═'*80}\n")


def collect_holdout_with_returns(
    symbols: list[str],
    history: str = "8y",
    max_workers: int = 8,
) -> pd.DataFrame:
    """
    Collect scored predictions for frozen holdout symbols,
    including fwd_ret_raw for expectancy calculation.
    """
    import joblib
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from ml_features import generate_labels, FEATURE_COLUMNS

    model  = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)

    # Optionally load meta-model
    meta_model = meta_scaler = None
    if META_MODEL.exists() and META_SCALER.exists():
        meta_model  = joblib.load(META_MODEL)
        meta_scaler = joblib.load(META_SCALER)
        logger.info("  Meta-model loaded — will compute meta_prob per signal")

    logger.info(f"📊 Collecting expectancy data for {len(symbols)} frozen symbols…")
    frames = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(generate_labels, sym, 10, 5.0, history): sym
            for sym in symbols
        }
        for i, fut in enumerate(as_completed(futures), 1):
            sym = futures[fut]
            try:
                df = fut.result()
                if df is not None and len(df) > 10:
                    frames.append(df)
                    if i % 10 == 0:
                        logger.info(f"  [{i}/{len(symbols)}]")
            except Exception as e:
                logger.debug(f"  {sym}: {e}")

    if not frames:
        raise RuntimeError("No data collected")

    combined = pd.concat(frames, ignore_index=True)
    logger.info(f"✅ {len(combined):,} rows from {len(frames)} symbols")

    # ── Apply Phase C-r pipeline ─────────────────────────────────────────────
    try:
        from macro_features import build_macro_df, merge_macro
        macro_df = build_macro_df(start="2016-01-01")
        combined = merge_macro(combined, macro_df)
    except Exception as e:
        logger.warning(f"  ⚠️  Macro features skipped: {e}")
        for col in ["india_vix", "vix_5d_change", "usd_inr_1d_ret", "crude_1d_ret", "market_breadth"]:
            combined[col] = 0.0

    try:
        from cross_sectional_features import add_cross_sectional_ranks
        combined = add_cross_sectional_ranks(combined)
    except Exception as e:
        logger.warning(f"  ⚠️  Rank features skipped: {e}")
        for col in ["sector_rsi_rank", "sector_mom_rank", "sector_vol_rank",
                    "mkt_mom_rank", "mkt_vol_rank", "vol_vs_own_hist"]:
            combined[col] = 0.5

    # Primary model score — use only the feature columns that exist in the
    # combined DataFrame (mirrors the train_model.py `feature_cols` filter)
    feature_cols = [c for c in FEATURE_COLUMNS if c in combined.columns]
    logger.info(f"  🔢 Scoring with {len(feature_cols)}/{len(FEATURE_COLUMNS)} feature columns")
    X      = combined[feature_cols].fillna(0).astype(float).values
    X_sc   = scaler.transform(X)
    combined["y_score"] = model.predict_proba(X_sc)[:, 1]
    combined["y_true"]  = combined["label"].astype(int)

    # Meta-model score (if available)
    if meta_model is not None:
        from meta_label import META_FEATURE_COLS
        meta_feats = combined[
            [c for c in META_FEATURE_COLS if c in combined.columns]
        ].fillna(0)
        # Add primary_prob as meta feature
        meta_feats = meta_feats.copy()
        meta_feats["primary_prob"] = combined["y_score"].values
        if "primary_prob" in META_FEATURE_COLS:
            X_meta = meta_feats[META_FEATURE_COLS].fillna(0).values
        else:
            X_meta = meta_feats.fillna(0).values
        X_meta_sc = meta_scaler.transform(X_meta)
        combined["meta_score"] = meta_model.predict_proba(X_meta_sc)[:, 1]

    return combined


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Kepler Expectancy & Transaction Cost Analysis",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--holdout-yaml", default="configs/frozen_holdout.yaml")
    parser.add_argument("--trade-value", type=float, default=50_000,
                        help="Typical position size in INR (for cost calculation)")
    parser.add_argument("--history", default="8y")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="INFO",
               format="<green>{time:HH:mm:ss}</green> | {message}")

    # ── Load frozen symbols ────────────────────────────────────────────────────
    yaml_path = _BACKEND_DIR / args.holdout_yaml
    with open(yaml_path) as f:
        holdout_data = yaml.safe_load(f)
    symbols = [t for t in holdout_data.get("tickers", []) if isinstance(t, str)]
    logger.info(f"🔒 Frozen holdout: {len(symbols)} symbols")

    # ── Collect data ───────────────────────────────────────────────────────────
    df = collect_holdout_with_returns(symbols, history=args.history,
                                      max_workers=args.workers)

    # ── Transaction cost ───────────────────────────────────────────────────────
    cost_pct = compute_round_trip_cost_pct(args.trade_value)
    logger.info(f"\n💸 NSE round-trip cost @ ₹{args.trade_value:,.0f}: {cost_pct:.3f}%")
    logger.info(f"   (STT + exchange + SEBI + brokerage + slippage)")

    # ── Primary model expectancy ───────────────────────────────────────────────
    logger.info("\n── PRIMARY MODEL (no meta-filter) ──")
    rows_primary = expectancy_table(
        df, score_col="y_score", trade_value_inr=args.trade_value
    )
    print_expectancy_table(rows_primary, base_rate=df["y_true"].mean())

    # ── Meta-filter expectancy (if meta_score available) ──────────────────────
    if "meta_score" in df.columns:
        logger.info("── WITH META-FILTER (primary_prob AND meta_score >= threshold) ──")
        # Combined filter: primary >= 0.35 AND meta >= threshold
        df["combined_score"] = df["y_score"] * df["meta_score"]
        rows_meta = expectancy_table(
            df, score_col="combined_score",
            thresholds=[0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40],
            trade_value_inr=args.trade_value,
        )
        print_expectancy_table(rows_meta, base_rate=df["y_true"].mean())
    else:
        logger.warning("Meta-model not found — run meta_label.py --train first for combined table")

    # ── Save results ───────────────────────────────────────────────────────────
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out = {
        "generated_at":     datetime.utcnow().isoformat() + "Z",
        "holdout_symbols":  len(symbols),
        "holdout_rows":     int(len(df)),
        "positive_rate":    round(float(df["y_true"].mean()), 4),
        "trade_value_inr":  args.trade_value,
        "cost_pct":         round(cost_pct, 4),
        "primary_expectancy": rows_primary,
        "meta_expectancy":  rows_meta if "meta_score" in df.columns else [],
    }
    path = _CONFIGS_DIR / f"expectancy_{ts}.json"
    path.write_text(json.dumps(out, indent=2))
    logger.info(f"💾 Results saved → {path}")
