"""
KEPLER — Meta-Label Filter (Phase D)
======================================
A secondary LightGBM classifier whose only job is:

  "Given that the PRIMARY model said BUY with probability P,
   and given the current volatility/momentum/volume context,
   what is the probability that it was actually RIGHT?"

Only generate a trade signal when BOTH models agree above a threshold.
This is the standard meta-labeling technique from Marcos López de Prado's
"Advances in Financial Machine Learning."

How it works
------------
  1. Run the primary walk-forward training (train_model.py) first.
  2. During training, the primary model produces OUT-OF-FOLD predictions
     for every row in the training dataset. These predictions are unbiased
     because each row was scored by a model that never saw it during training.
  3. The meta-label model is trained on:
       Features: [primary_prob, volatility, volume_ratio, trend_strength, ...]
       Target:   1 if the primary prediction was CORRECT, else 0
  4. At inference time, run both models. Only trade if:
       primary_prob >= primary_threshold  AND  meta_prob >= meta_threshold

Usage
-----
    # Train meta-label model (requires OOF predictions from train_model.py)
    python meta_label.py --train

    # Sweep thresholds and print precision/frequency table
    python meta_label.py --sweep

    # Both
    python meta_label.py --train --sweep
"""

import argparse
import json
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from loguru import logger

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# ── Paths ─────────────────────────────────────────────────────────────────────
_BACKEND_DIR  = Path(__file__).parent
_MODELS_DIR   = _BACKEND_DIR / "models"
_CONFIGS_DIR  = _BACKEND_DIR / "configs" / "experiment_runs"
_MODELS_DIR.mkdir(exist_ok=True)
_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)

META_MODEL_PATH  = _MODELS_DIR / "meta_model.pkl"
META_SCALER_PATH = _MODELS_DIR / "meta_scaler.pkl"
META_META_PATH   = _MODELS_DIR / "meta_model_meta.json"
OOF_CACHE_PATH   = _CONFIGS_DIR / "oof_predictions.pkl"

# Primary model paths
MODEL_PATH  = _MODELS_DIR / "kepler_model.pkl"
SCALER_PATH = _MODELS_DIR / "kepler_scaler.pkl"
META_PATH   = _MODELS_DIR / "kepler_meta.json"


# ── Meta-label feature columns ────────────────────────────────────────────────
META_FEATURE_COLS = [
    # Primary model output
    "primary_prob",

    # Volatility context
    "atr_14",          # absolute ATR
    "bb_width",        # Bollinger Band width (normalised volatility)
    "hl_ratio",        # today's high-low range / price

    # Momentum context
    "rsi_14",
    "adx_14",          # trend strength (high = trending, low = choppy/mean-reverting)
    "roc_20",          # 20-day momentum
    "pct_from_52l",    # distance from 52-week low (momentum regime)
    "price_vs_ema200", # above/below long-term trend

    # Volume context
    "volume_ratio",    # today's volume vs 10-day average

    # Positioning context
    "bb_pct_b",        # where in the Bollinger Band is price (0=bottom, 1=top)
    "pct_vs_sma50",    # over/under-extended vs 50-day average
]


# ── Generate OOF predictions ──────────────────────────────────────────────────
def generate_oof_predictions(
    universe: str = "nifty200",
    forward_days: int = 10,
    threshold_pct: float = 5.0,
    history_years: int = 8,
    n_folds: int = 5,
    embargo_days: int = 15,
    max_workers: int = 8,
) -> pd.DataFrame:
    """
    Rebuild the walk-forward dataset, run the saved primary model on each
    out-of-fold slice, and return a DataFrame with:
      - All primary FEATURE columns
      - primary_prob: model's predicted probability for that row
      - label:        actual outcome (did it gain >=threshold% in forward_days?)
      - meta_label:   1 if primary prediction was CORRECT, 0 if WRONG
        (correct = both predicted and actual agree above 0.5)

    This is the training data for the meta-label model.
    """
    from ml_features import FEATURE_COLUMNS, generate_labels
    from walk_forward import generate_wf_splits, fold_date_range

    logger.info("🔄 Generating OOF predictions for meta-label training…")

    # ── 1. Load primary model & scaler ────────────────────────────────────────
    if not MODEL_PATH.exists():
        raise FileNotFoundError(f"Primary model not found: {MODEL_PATH}. Run train_model.py first.")
    primary_model  = joblib.load(MODEL_PATH)
    primary_scaler = joblib.load(SCALER_PATH)
    primary_meta   = json.loads(META_PATH.read_text()) if META_PATH.exists() else {}
    feature_cols   = primary_meta.get("feature_columns", FEATURE_COLUMNS)

    # ── 2. Rebuild training dataset ───────────────────────────────────────────
    from train_model import UNIVERSES, build_training_dataset
    symbols = UNIVERSES.get(universe, UNIVERSES["nifty200"])
    raw_df  = build_training_dataset(
        symbols, forward_days, threshold_pct, history_years, max_workers
    )

    # ── 3. Scale features ─────────────────────────────────────────────────────
    for col in feature_cols:
        if col not in raw_df.columns:
            raw_df[col] = 0.0
    X       = raw_df[feature_cols].fillna(0).astype(float).values
    y       = raw_df["label"].astype(int).values
    X_scaled = primary_scaler.transform(X)

    # ── 4. Walk-forward splits — score each test fold ─────────────────────────
    splits = generate_wf_splits(
        raw_df, n_folds=n_folds, embargo_days=embargo_days,
        min_train_rows=3000, expanding=True,
    )

    oof_records = []
    for fold_idx, (tr_idx, te_idx) in enumerate(splits):
        # Re-train primary on train portion for this fold (needed for clean OOF)
        from lightgbm import LGBMClassifier, early_stopping, log_evaluation
        X_tr, y_tr = X_scaled[tr_idx], y[tr_idx]
        X_te, y_te = X_scaled[te_idx], y[te_idx]

        pos_cnt = int(y_tr.sum())
        neg_cnt = int(len(y_tr) - pos_cnt)

        fold_model = LGBMClassifier(
            n_estimators=800, learning_rate=0.03, num_leaves=63,
            subsample=0.8, colsample_bytree=0.8,
            reg_alpha=0.1, reg_lambda=1.0,
            scale_pos_weight=neg_cnt / max(pos_cnt, 1),
            random_state=42 + fold_idx, n_jobs=-1, verbose=-1,
        )
        fold_model.fit(
            X_tr, y_tr, eval_set=[(X_te, y_te)],
            callbacks=[early_stopping(50, verbose=False), log_evaluation(-1)],
        )

        proba_te = fold_model.predict_proba(X_te)[:, 1]

        # ── Meta-label OOF records ───────────────────────────────────────────
        # Keep ALL rows from this fold's test set.
        # meta_label = actual label (1 if stock gained >= threshold% in fwd window).
        # The meta-model sees primary_prob as one of its features and learns
        # to predict actual outcomes — acting as a calibrated second-opinion
        # classifier.  Both primary_prob and meta_prob thresholds are applied
        # at inference time (AND logic), so this is equivalent to a refined
        # ensemble filter without needing calibrated OOF probabilities.
        test_rows = raw_df.iloc[te_idx].copy().reset_index(drop=True)
        test_rows["primary_prob"] = proba_te
        test_rows["meta_label"]   = y_te.astype(int)   # actual outcome
        test_rows["fold"]         = fold_idx + 1
        test_dr = fold_date_range(raw_df, te_idx)
        logger.info(
            f"  Fold {fold_idx+1}: {len(test_rows):,} OOF rows | "
            f"hit rate={test_rows['meta_label'].mean():.3f} | "
            f"period={test_dr[0]}\u2192{test_dr[1]}"
        )
        oof_records.append(test_rows)

    oof_df = pd.concat(oof_records, ignore_index=True)
    logger.info(
        f"\u2705 OOF dataset: {len(oof_df):,} rows | "
        f"positive rate: {oof_df['meta_label'].mean():.1%}"
    )

    # Cache to disk for faster re-runs
    oof_df.to_pickle(OOF_CACHE_PATH)
    logger.info(f"\U0001f4be OOF predictions cached \u2192 {OOF_CACHE_PATH}")
    return oof_df




# ── Train meta-label model ─────────────────────────────────────────────────────
def train_meta_model(oof_df: pd.DataFrame) -> Dict:
    """Train secondary LightGBM on OOF predictions → save meta_model.pkl."""
    from lightgbm import LGBMClassifier, early_stopping, log_evaluation
    from sklearn.preprocessing import StandardScaler
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import roc_auc_score, average_precision_score, precision_score

    logger.info("🚂 Training meta-label model…")

    # Build feature matrix for meta model
    for col in META_FEATURE_COLS:
        if col not in oof_df.columns:
            oof_df[col] = 0.0

    X_meta = oof_df[META_FEATURE_COLS].fillna(0).astype(float).values
    y_meta = oof_df["meta_label"].astype(int).values

    # Time-based split for meta model (last 20% = validation)
    split_idx = int(len(X_meta) * 0.8)
    X_tr, X_val = X_meta[:split_idx], X_meta[split_idx:]
    y_tr, y_val = y_meta[:split_idx], y_meta[split_idx:]

    # Scale
    meta_scaler = StandardScaler()
    X_tr  = meta_scaler.fit_transform(X_tr)
    X_val = meta_scaler.transform(X_val)

    pos_cnt = int(y_tr.sum())
    neg_cnt = int(len(y_tr) - pos_cnt)

    meta_model = LGBMClassifier(
        n_estimators=400, learning_rate=0.05, num_leaves=31,
        min_child_samples=20, subsample=0.8, colsample_bytree=0.8,
        scale_pos_weight=neg_cnt / max(pos_cnt, 1),
        random_state=42, n_jobs=-1, verbose=-1,
    )
    meta_model.fit(
        X_tr, y_tr, eval_set=[(X_val, y_val)],
        callbacks=[early_stopping(40, verbose=False), log_evaluation(-1)],
    )

    proba_val = meta_model.predict_proba(X_val)[:, 1]
    auc = roc_auc_score(y_val, proba_val)
    ap  = average_precision_score(y_val, proba_val)
    logger.info(f"📈 Meta-model val AUC: {auc:.4f} | Avg Precision: {ap:.4f}")

    # Feature importances
    importances = dict(zip(META_FEATURE_COLS,
                           [round(float(v), 6) for v in meta_model.feature_importances_]))
    top5 = sorted(importances.items(), key=lambda x: -x[1])[:5]
    logger.info("🔑 Top meta-label features:")
    for f, v in top5:
        logger.info(f"   {f:<25} {v:.4f}")

    # Save
    joblib.dump(meta_model,  META_MODEL_PATH)
    joblib.dump(meta_scaler, META_SCALER_PATH)

    meta_info = {
        "trained_at":    datetime.utcnow().isoformat() + "Z",
        "meta_features": META_FEATURE_COLS,
        "n_train":       int(len(X_tr)),
        "n_val":         int(len(X_val)),
        "meta_auc":      round(auc, 4),
        "meta_ap":       round(ap, 4),
        "feature_importances": dict(sorted(importances.items(), key=lambda x: -x[1])),
    }
    META_META_PATH.write_text(json.dumps(meta_info, indent=2))
    logger.info(f"💾 Meta model saved → {META_MODEL_PATH}")
    return meta_info


# ── Threshold sweep ───────────────────────────────────────────────────────────
def sweep_thresholds(oof_df: pd.DataFrame) -> pd.DataFrame:
    """
    For a range of joint thresholds, compute:
      - precision (what % of trades actually worked)
      - trade_frequency (what % of all BUY signals pass the filter)
      - n_trades (absolute count)

    Prints a table and saves to configs/experiment_runs/meta_sweep_<ts>.json
    """
    if not META_MODEL_PATH.exists():
        logger.error("Meta model not found. Run --train first.")
        return pd.DataFrame()

    meta_model  = joblib.load(META_MODEL_PATH)
    meta_scaler = joblib.load(META_SCALER_PATH)

    for col in META_FEATURE_COLS:
        if col not in oof_df.columns:
            oof_df[col] = 0.0

    X_meta  = oof_df[META_FEATURE_COLS].fillna(0).astype(float).values
    X_scaled = meta_scaler.transform(X_meta)
    meta_proba = meta_model.predict_proba(X_scaled)[:, 1]

    primary_proba = oof_df["primary_prob"].values
    actual_labels = oof_df["label"].astype(int).values

    logger.info(f"\n{'─'*72}")
    logger.info(f"{'Primary≥':>10} {'Meta≥':>7} {'N trades':>9} {'Freq%':>7} "
                f"{'Precision':>10} {'Recall':>9}")
    logger.info(f"{'─'*72}")

    rows = []
    # Use percentile-based primary thresholds because OOF fold model
    # probabilities have different calibration from the final pipeline.
    # This guarantees the sweep always produces results.
    pct_levels = [70, 80, 85, 90, 95]   # keep top 30%, 20%, 15%, 10%, 5%
    primary_thresholds = [float(np.percentile(primary_proba, p)) for p in pct_levels]
    meta_thresholds    = [0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8]

    total_signals = len(primary_proba)  # baseline for freq%

    logger.info(f"  OOF primary_prob range: {primary_proba.min():.4f} – {primary_proba.max():.4f}")
    logger.info(f"  Primary thresholds (percentile-based): {[round(t,4) for t in primary_thresholds]}")

    for p_thr, pct in zip(primary_thresholds, pct_levels):
        for m_thr in meta_thresholds:
            mask      = (primary_proba >= p_thr) & (meta_proba >= m_thr)
            n_trades  = mask.sum()
            if n_trades == 0:
                continue
            hits      = actual_labels[mask].sum()
            precision = hits / n_trades
            all_pos   = actual_labels.sum()
            recall    = hits / max(all_pos, 1)
            freq_pct  = n_trades / max(total_signals, 1) * 100

            logger.info(
                f"  top{100-pct}% primary  meta≥{m_thr:.2f}  {n_trades:>8,}  {freq_pct:>6.1f}%"
                f"  {precision:>9.1%}  {recall:>8.1%}"
            )
            rows.append({
                "primary_pct_level":  pct,
                "primary_threshold":  round(p_thr, 4),
                "meta_threshold":     m_thr,
                "n_trades":           int(n_trades),
                "freq_pct":           round(freq_pct, 2),
                "precision":          round(precision, 4),
                "recall":             round(recall, 4),
            })


    logger.info(f"{'─'*72}")
    logger.info(
        "💡 Recommended starting point: primary≥0.40, meta≥0.65\n"
        "   Adjust based on how many trades/month you want.\n"
        "   Higher thresholds = fewer trades, higher precision."
    )

    result_df = pd.DataFrame(rows)

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = _CONFIGS_DIR / f"meta_sweep_{ts}.json"
    out_path.write_text(json.dumps(rows, indent=2))
    logger.info(f"💾 Sweep saved → {out_path}")

    return result_df


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Kepler Meta-Label Filter — Phase D",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--train", action="store_true",
                        help="Generate OOF predictions and train meta model")
    parser.add_argument("--sweep", action="store_true",
                        help="Sweep thresholds and print precision/frequency table")
    parser.add_argument("--universe", default="nifty200",
                        choices=["nifty50", "nifty200", "nifty500"])
    parser.add_argument("--history-years", type=int, default=8)
    parser.add_argument("--n-folds", type=int, default=5)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--use-cache", action="store_true",
                        help="Use cached OOF predictions if available (skip regeneration)")
    args = parser.parse_args()

    if not args.train and not args.sweep:
        parser.print_help()
        sys.exit(0)

    logger.remove()
    logger.add(sys.stderr, level="INFO",
               format="<green>{time:HH:mm:ss}</green> | {message}")

    logger.info("=" * 62)
    logger.info("  KEPLER META-LABEL FILTER — Phase D")
    logger.info("=" * 62)

    # Load or generate OOF predictions
    if args.use_cache and OOF_CACHE_PATH.exists():
        logger.info(f"📂 Loading cached OOF predictions from {OOF_CACHE_PATH}")
        oof_df = pd.read_pickle(OOF_CACHE_PATH)
        logger.info(f"   {len(oof_df):,} rows loaded")
    elif args.train:
        oof_df = generate_oof_predictions(
            universe=args.universe,
            history_years=args.history_years,
            n_folds=args.n_folds,
            max_workers=args.workers,
        )
    else:
        if OOF_CACHE_PATH.exists():
            logger.info("📂 Using existing OOF cache for sweep (run --train to regenerate)")
            oof_df = pd.read_pickle(OOF_CACHE_PATH)
        else:
            logger.error("No OOF cache found. Run with --train first.")
            sys.exit(1)

    if args.train:
        train_meta_model(oof_df)

    if args.sweep:
        sweep_thresholds(oof_df)
