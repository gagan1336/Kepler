"""
KEPLER — Bootstrap Confidence Interval on Clean Holdout AUC
=============================================================
Re-samples the frozen holdout with replacement 1000 times, recomputes
AUC each time, and reports the 5th/95th percentile interval.

If the interval includes 0.50, the signal may not be real — we cannot
confidently claim the model is better than random on unseen stocks.

Usage
-----
    python bootstrap_ci.py --holdout-yaml configs/frozen_holdout.yaml

Output
------
    Printed summary + saved to configs/experiment_runs/bootstrap_ci_<ts>.json
"""

from __future__ import annotations

import argparse
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


def load_frozen_symbols(holdout_yaml: Path) -> list[str]:
    with open(holdout_yaml) as f:
        data = yaml.safe_load(f)
    return [t for t in data.get("tickers", []) if isinstance(t, str)]


def collect_holdout_scores(
    symbols: list[str],
    forward_days: int = 10,
    threshold_pct: float = 5.0,
    history: str = "8y",
    max_workers: int = 8,
) -> pd.DataFrame:
    """
    Fetch features + labels for all frozen holdout symbols,
    score them through the current model, and return a DataFrame with:
      y_true  : actual label (1 = hit threshold in forward_days)
      y_score : primary model predicted probability
    """
    import joblib
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from ml_features import generate_labels, FEATURE_COLUMNS

    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Model not found at {MODEL_PATH}")

    model  = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)

    logger.info(f"📊 Collecting holdout data for {len(symbols)} frozen symbols…")
    frames = []
    failed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(generate_labels, sym, forward_days, threshold_pct, history): sym
            for sym in symbols
        }
        for i, fut in enumerate(as_completed(futures), 1):
            sym = futures[fut]
            try:
                df = fut.result()
                if df is not None and len(df) > 10:
                    frames.append(df)
                    if i % 10 == 0:
                        logger.info(f"  [{i}/{len(symbols)}] collected")
                else:
                    failed += 1
            except Exception as e:
                logger.debug(f"  {sym} failed: {e}")
                failed += 1

    if not frames:
        raise RuntimeError("No holdout data collected — check internet connectivity")

    combined = pd.concat(frames, ignore_index=True)
    logger.info(f"✅ {len(combined):,} holdout rows from {len(frames)} symbols ({failed} failed)")

    # ── Apply Phase C-r pipeline (same as train_model.py) ───────────────────
    # NOTE on rank features: ranks are computed within the holdout set (~40 stocks)
    # rather than within the full training universe (~150 stocks). This gives a
    # conservative estimate — the ranking signal is weaker on a smaller set, so
    # holdout AUC may be slightly understated vs. a live scan where all peers are present.
    try:
        from macro_features import build_macro_df, merge_macro
        macro_df = build_macro_df(start="2016-01-01")
        combined = merge_macro(combined, macro_df)
        logger.info("  📡 Macro features merged")
    except Exception as e:
        logger.warning(f"  ⚠️  Macro features skipped: {e}")
        for col in ["india_vix", "vix_5d_change", "usd_inr_1d_ret", "crude_1d_ret", "market_breadth"]:
            combined[col] = 0.0

    try:
        from cross_sectional_features import add_cross_sectional_ranks
        combined = add_cross_sectional_ranks(combined)
        logger.info("  📐 Cross-sectional rank features added (within holdout set)")
    except Exception as e:
        logger.warning(f"  ⚠️  Rank features skipped: {e}")
        for col in ["sector_rsi_rank", "sector_mom_rank", "sector_vol_rank",
                    "mkt_mom_rank", "mkt_vol_rank", "vol_vs_own_hist"]:
            combined[col] = 0.5

    # Score through model — use only the feature columns that exist in the
    # combined DataFrame (mirrors the train_model.py `feature_cols` filter)
    feature_cols = [c for c in FEATURE_COLUMNS if c in combined.columns]
    logger.info(f"  🔢 Scoring with {len(feature_cols)}/{len(FEATURE_COLUMNS)} feature columns")
    X = combined[feature_cols].fillna(0).astype(float).values
    X_sc = scaler.transform(X)
    combined["y_score"] = model.predict_proba(X_sc)[:, 1]
    combined["y_true"]  = combined["label"].astype(int)
    return combined[["y_true", "y_score", "symbol", "date"]]


def bootstrap_auc(
    y_true: np.ndarray,
    y_score: np.ndarray,
    n_boot: int = 1000,
    ci_low: float = 5.0,
    ci_high: float = 95.0,
    seed: int = 42,
) -> dict:
    """
    Bootstrap confidence interval on AUC-ROC.
    Returns dict with point_auc, ci_low, ci_high, n_boot, p_above_05.
    """
    from sklearn.metrics import roc_auc_score

    rng  = np.random.default_rng(seed)
    n    = len(y_true)
    aucs = []

    for _ in range(n_boot):
        idx  = rng.integers(0, n, size=n)
        yt   = y_true[idx]
        ys   = y_score[idx]
        # Skip degenerate samples (all same class)
        if len(np.unique(yt)) < 2:
            continue
        try:
            aucs.append(roc_auc_score(yt, ys))
        except Exception:
            pass

    aucs = np.array(aucs)
    point = roc_auc_score(y_true, y_score)

    return {
        "point_auc":     round(float(point), 4),
        "ci_low_pct":    round(float(np.percentile(aucs, ci_low)), 4),
        "ci_high_pct":   round(float(np.percentile(aucs, ci_high)), 4),
        "n_bootstrap":   len(aucs),
        "p_above_0_50":  round(float(np.mean(aucs > 0.50)), 4),
        "signal_real":   bool(np.percentile(aucs, ci_low) > 0.50),
    }


def precision_at_threshold(y_true, y_score, thresholds=None,
                           min_samples: int = 200) -> list[dict]:
    """Compute precision and recall at a sweep of probability thresholds.
    
    Stops reporting once fewer than min_samples trades remain — sample
    too thin for reliable statistics.
    """
    if thresholds is None:
        thresholds = [0.25, 0.30, 0.35, 0.40, 0.45, 0.50,
                      0.55, 0.60, 0.65, 0.70]
    rows = []
    n_pos = y_true.sum()
    for thr in thresholds:
        pred = (y_score >= thr).astype(int)
        n    = int(pred.sum())
        if n < min_samples:
            rows.append({
                "threshold": thr,
                "n_trades":  n,
                "precision": None,
                "recall":    None,
                "note":      f"< {min_samples} samples — not reported",
            })
            continue
        tp   = int((pred & y_true).sum())
        fp   = int((pred & ~y_true.astype(bool)).sum())
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec  = tp / n_pos if n_pos > 0 else 0.0
        rows.append({
            "threshold": thr,
            "n_trades":  n,
            "precision": round(prec, 4),
            "recall":    round(rec, 4),
            "note":      "",
        })
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Bootstrap CI on frozen holdout AUC",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--holdout-yaml",
                        default="configs/frozen_holdout.yaml")
    parser.add_argument("--n-boot", type=int, default=1000)
    parser.add_argument("--history", default="8y")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="INFO",
               format="<green>{time:HH:mm:ss}</green> | {message}")

    yaml_path = _BACKEND_DIR / args.holdout_yaml
    symbols   = load_frozen_symbols(yaml_path)
    logger.info(f"🔒 Frozen holdout: {len(symbols)} symbols from {yaml_path.name}")

    # 1. Collect data + scores
    df = collect_holdout_scores(
        symbols, history=args.history, max_workers=args.workers
    )

    y_true  = df["y_true"].values.astype(int)
    y_score = df["y_score"].values

    # 2. Bootstrap CI
    logger.info(f"\n🔁 Running {args.n_boot}-sample bootstrap CI…")
    ci = bootstrap_auc(y_true, y_score, n_boot=args.n_boot)

    logger.info(f"\n{'═'*52}")
    logger.info(f"  FROZEN HOLDOUT — BOOTSTRAP AUC RESULTS")
    logger.info(f"{'═'*52}")
    logger.info(f"  Holdout symbols  : {len(symbols)}")
    logger.info(f"  Holdout rows     : {len(df):,}")
    logger.info(f"  Positive rate    : {y_true.mean():.1%}")
    logger.info(f"  Point AUC        : {ci['point_auc']:.4f}")
    logger.info(f"  90% CI           : [{ci['ci_low_pct']:.4f}, {ci['ci_high_pct']:.4f}]")
    logger.info(f"  P(AUC > 0.50)    : {ci['p_above_0_50']:.1%}")
    signal_str = "✅ REAL SIGNAL — CI excludes 0.50" if ci['signal_real'] \
                 else "⚠️  UNCERTAIN — CI includes 0.50 (may be noise)"
    logger.info(f"  Verdict          : {signal_str}")
    logger.info(f"{'═'*52}")

    # 3. Precision sweep
    logger.info(f"\n{'─'*50}")
    logger.info(f"{'Threshold':>11} {'N trades':>9} {'Precision':>10} {'Recall':>8}")
    logger.info(f"{'─'*50}")
    prec_rows = precision_at_threshold(y_true, y_score)
    for r in prec_rows:
        logger.info(
            f"  {r['threshold']:>9.2f}  {r['n_trades']:>8,}  "
            f"{r['precision']:>9.1%}  {r['recall']:>7.1%}"
        )
    logger.info(f"{'─'*50}")
    logger.info(f"  Base rate (random): {y_true.mean():.1%}")

    # 4. Save
    result = {
        "generated_at":  datetime.utcnow().isoformat() + "Z",
        "holdout_file":  str(yaml_path),
        "n_symbols":     len(symbols),
        "n_rows":        int(len(df)),
        "positive_rate": round(float(y_true.mean()), 4),
        "bootstrap_ci":  ci,
        "precision_sweep": prec_rows,
    }
    ts   = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    path = _CONFIGS_DIR / f"bootstrap_ci_{ts}.json"
    path.write_text(json.dumps(result, indent=2))
    logger.info(f"\n💾 Results saved → {path}")
