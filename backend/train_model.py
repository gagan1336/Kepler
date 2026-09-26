"""
KEPLER — ML Model Training Pipeline  (Phase 4: Walk-Forward Edition)
======================================================================
Trains a LightGBM (or XGBoost) binary classifier on NSE stocks using
proper walk-forward validation with purge + embargo gaps to prevent
label leakage from overlapping forward returns.

Usage
-----
    cd backend

    # Smoke test (fast, Nifty50, 3 folds, 3-year history)
    python train_model.py --universe nifty50 --n-folds 3 --history-years 3

    # Full training (Nifty200, 5 folds, 8-year history, LightGBM)
    python train_model.py --universe nifty200 --n-folds 5 --history-years 8

    # XGBoost comparison run
    python train_model.py --universe nifty200 --model xgb

    # With Optuna hyperparameter tuning
    python train_model.py --universe nifty200 --tune

Outputs (saved to backend/models/)
-----------------------------------
    kepler_model.pkl    — final model (LightGBM or XGBoost wrapper)
    kepler_scaler.pkl   — fitted StandardScaler
    kepler_meta.json    — metadata: AUC, feature importances, fold metrics,
                          training date, walk-forward config

Experiment logs (saved to backend/configs/experiment_runs/<timestamp>/)
------------------------------------------------------------------------
    fold_01.json … fold_N.json  — per-fold metrics
    summary.json                — mean ± std across folds + config
"""

import argparse
import json
import math
import os
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from loguru import logger

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# ── Pickle-safe wrappers (defined in ml_features so they always deserialise) ──
from ml_features import CalibratedXGBModel, CalibratedLGBMModel  # noqa: F401

# ── Walk-forward split engine ─────────────────────────────────────────────────
from walk_forward import generate_wf_splits, embargo_check

# ── Paths ─────────────────────────────────────────────────────────────────────
_BACKEND_DIR   = Path(__file__).parent
_MODELS_DIR    = _BACKEND_DIR / "models"
_CONFIGS_DIR   = _BACKEND_DIR / "configs" / "experiment_runs"
_MODELS_DIR.mkdir(exist_ok=True)
_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH  = _MODELS_DIR / "kepler_model.pkl"
SCALER_PATH = _MODELS_DIR / "kepler_scaler.pkl"
META_PATH   = _MODELS_DIR / "kepler_meta.json"

# ── Nifty universe lists ───────────────────────────────────────────────────────
NIFTY_50 = [
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
]

NIFTY_200_EXTRA = [
    # Banking & Finance
    "BANKBARODA", "FEDERALBNK", "PNB", "CANBK", "UNIONBANK",
    "IDFCFIRSTB", "BANDHANBNK", "AUBANK", "RBLBANK", "YESBANK",
    "MUTHOOTFIN", "BAJAJHLDNG", "CHOLAFIN", "MANAPPURAM", "ABCAPITAL",
    # IT
    "LTIMINDTECH", "PERSISTENT", "COFORGE", "MPHASIS", "OFSS", "KPITTECH",
    # Pharma
    "TORNTPHARM", "AUROPHARMA", "ALKEM", "LUPIN", "BIOCON",
    "IPCALAB", "ABBOTINDIA", "PFIZER", "SANOFI",
    # Auto
    "TATAMOTORS", "TVSMOTOR", "MOTHERSON", "BOSCHLTD", "EXIDEIND",
    "MRF", "CEATLTD", "BALKRISIND",
    # FMCG / Consumer
    "GODREJCP", "DABUR", "MARICO", "COLPAL", "VBL",
    "RADICO", "UNITDSPR", "MCDOWELL-N",
    # Energy / Power
    "ADANIGREEN", "ADANITRANS", "TORNTPOWER", "TATAPOWER",
    "CESC", "NHPC", "SJVN", "RECLTD", "PFC",
    # Infrastructure / Capital Goods
    "SIEMENS", "ABB", "HAVELLS", "SCHAEFFLER", "CUMMINSIND",
    "GRINDWELL", "THERMAX", "BHEL", "AIAENG",
    # Metals & Mining
    "VEDL", "HINDZINC", "SAIL", "NMDC", "WELCORP",
    "JINDALSTEL", "RATNAMANI",
    # Real Estate
    "DLF", "GODREJPROP", "OBEROIRLTY", "PRESTIGE", "BRIGADE",
    # Retail / Lifestyle
    "DMART", "NYKAA", "ETERNAL", "DEVYANI", "SAPPHIRE",  # ETERNAL = Zomato post-renament
    # Cement
    "SHREECEM", "AMBUJACEM", "ACC", "RAMCOCEM",
    # Chemicals
    "PIDILITIND", "ASTRAL", "SUPREME", "SRF", "AAVAS", "ALKYLAMINE",
    # Telecom
    "IDEA", "INDUSTOWER",
    # Misc
    "IRCTC", "HAL", "BDL", "MAZDOCK", "POLYCAB", "DIXON",
    "LATENTVIEW", "HAPPYMNDS",
]

NIFTY_500_EXTRA = [
    # NOTE: this list is intentionally empty.
    # All former Nifty500 extra stocks are now in configs/frozen_holdout.yaml
    # and must NEVER be added back here or to any training universe.
    # See tests/test_no_holdout_leakage.py — adding them will fail the build.
    #
    # To expand the training universe beyond Nifty200, source NEW stocks that
    # are NOT in frozen_holdout.yaml. Do NOT re-use the holdout set.
]


UNIVERSES: Dict[str, List[str]] = {
    "nifty50":  NIFTY_50,
    "nifty200": NIFTY_50 + NIFTY_200_EXTRA,
    "nifty500": NIFTY_50 + NIFTY_200_EXTRA + NIFTY_500_EXTRA,
}


# ── Data collection ────────────────────────────────────────────────────────────
def build_training_dataset(
    symbols: List[str],
    forward_days: int = 10,
    threshold_pct: float = 5.0,
    history_years: int = 8,
    max_workers: int = 8,
) -> pd.DataFrame:
    """
    Collect walk-forward labelled rows for all symbols in parallel.
    Returns a concatenated, date-sorted DataFrame ready for training.
    """
    from ml_features import generate_labels, FEATURE_COLUMNS

    period = f"{history_years}y"
    all_frames: List[pd.DataFrame] = []
    failed = 0

    logger.info(
        f"📊 Collecting labels for {len(symbols)} symbols "
        f"(forward={forward_days}d, threshold={threshold_pct}%, history={period})…"
    )
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(generate_labels, sym, forward_days, threshold_pct, period): sym
            for sym in symbols
        }
        for i, fut in enumerate(as_completed(futures), 1):
            sym = futures[fut]
            try:
                df = fut.result()
                if df is not None and len(df) > 0:
                    all_frames.append(df)
                    pos_rate = df["label"].mean() * 100
                    if i % 20 == 0 or i == len(symbols):
                        elapsed = time.time() - t0
                        logger.info(
                            f"  [{i}/{len(symbols)}] {sym}: "
                            f"{len(df)} rows, {pos_rate:.1f}% positive — "
                            f"{elapsed:.0f}s elapsed"
                        )
                else:
                    failed += 1
            except Exception as e:
                logger.debug(f"  Label gen failed {sym}: {e}")
                failed += 1

    if not all_frames:
        raise RuntimeError("No training data collected — check internet / yfinance access")

    combined = pd.concat(all_frames, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"])
    combined = combined.sort_values("date").reset_index(drop=True)

    total_rows = len(combined)
    pos_rate   = combined["label"].mean() * 100
    date_min   = combined["date"].min().date()
    date_max   = combined["date"].max().date()
    logger.info(
        f"✅ Dataset built: {total_rows:,} rows from {len(all_frames)} symbols "
        f"({failed} failed) | positive class: {pos_rate:.1f}% | "
        f"date range: {date_min} → {date_max}"
    )
    return combined


# ── Model factories ───────────────────────────────────────────────────────────
def _default_lgbm_params(pos_count: int, neg_count: int) -> Dict:
    """Return conservative LightGBM defaults for imbalanced classification."""
    return {
        "n_estimators":     800,
        "learning_rate":    0.03,
        "num_leaves":       63,
        "max_depth":        -1,            # LightGBM: -1 = no limit
        "min_child_samples": 30,
        "subsample":        0.8,
        "colsample_bytree": 0.8,
        "reg_alpha":        0.1,
        "reg_lambda":       1.0,
        "scale_pos_weight": neg_count / max(pos_count, 1),
        "class_weight":     None,          # using scale_pos_weight instead
        "random_state":     42,
        "n_jobs":           -1,
        "verbose":          -1,
    }


def _default_xgb_params(pos_count: int, neg_count: int) -> Dict:
    """Return conservative XGBoost defaults for comparison runs."""
    return {
        "n_estimators":    400,
        "max_depth":       6,
        "learning_rate":   0.05,
        "subsample":       0.8,
        "colsample_bytree": 0.8,
        "min_child_weight": 5,
        "gamma":           1.0,
        "reg_alpha":       0.1,
        "reg_lambda":      1.0,
        "scale_pos_weight": neg_count / max(pos_count, 1),
    }


def _build_lgbm(params: Dict, X_train, y_train, X_val, y_val):
    """Train a LightGBM classifier with early stopping."""
    from lightgbm import LGBMClassifier, early_stopping, log_evaluation
    model = LGBMClassifier(**params)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[
            early_stopping(stopping_rounds=60, verbose=False),
            log_evaluation(period=100),
        ],
    )
    return model


def _build_xgb(params: Dict, X_train, y_train, X_val, y_val):
    """Train an XGBoost classifier with early stopping."""
    from xgboost import XGBClassifier
    model = XGBClassifier(
        **params,
        tree_method="hist",
        eval_metric="auc",
        early_stopping_rounds=60,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    return model


# ── Per-fold evaluation ────────────────────────────────────────────────────────
def _evaluate_fold(model, X_val, y_val, fold_idx: int, date_range: Tuple) -> Dict:
    """Compute all metrics for one fold's test window."""
    from sklearn.metrics import (
        roc_auc_score, precision_score, recall_score,
        f1_score, average_precision_score,
    )
    proba = model.predict_proba(X_val)[:, 1]
    y_pred = (proba >= 0.5).astype(int)

    base_rate   = y_val.mean()
    auc  = float(roc_auc_score(y_val, proba)) if y_val.sum() > 0 else 0.0
    ap   = float(average_precision_score(y_val, proba)) if y_val.sum() > 0 else 0.0
    prec = float(precision_score(y_val, y_pred, zero_division=0))
    rec  = float(recall_score(y_val, y_pred, zero_division=0))
    f1   = float(f1_score(y_val, y_pred, zero_division=0))
    n_pos = int(y_val.sum())
    n_neg = int(len(y_val) - n_pos)

    metrics = {
        "fold":      fold_idx + 1,
        "test_start": str(date_range[0]),
        "test_end":   str(date_range[1]),
        "n_test":     len(y_val),
        "n_positive": n_pos,
        "n_negative": n_neg,
        "base_rate":  round(base_rate, 4),
        "auc":        round(auc,  4),
        "avg_prec":   round(ap,   4),
        "precision":  round(prec, 4),
        "recall":     round(rec,  4),
        "f1":         round(f1,   4),
    }
    logger.info(
        f"  Fold {fold_idx+1}: AUC={auc:.4f}  AP={ap:.4f}  "
        f"Prec={prec:.4f}  Rec={rec:.4f}  F1={f1:.4f}  "
        f"[{date_range[0]} → {date_range[1]}]"
    )
    return metrics


# ── Main training pipeline ────────────────────────────────────────────────────
def train(
    universe:      str   = "nifty200",
    forward_days:  int   = 10,
    threshold_pct: float = 5.0,
    n_folds:       int   = 5,
    embargo_days:  int   = 15,
    history_years: int   = 8,
    model_backend: str   = "lgbm",       # "lgbm" or "xgb"
    use_smote:     bool  = True,
    tune_hyperparams: bool = False,
    max_workers:   int   = 8,
    run_coverage:  bool  = True,
) -> Dict:
    """
    Full walk-forward training pipeline. Returns evaluation metrics dict.
    """
    from ml_features import FEATURE_COLUMNS
    from walk_forward import fold_date_range

    run_ts  = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_dir = _CONFIGS_DIR / run_ts
    run_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"📁 Experiment run dir: {run_dir}")

    # ── 1. Optional coverage report ──────────────────────────────────────────
    symbols = UNIVERSES.get(universe, UNIVERSES["nifty200"])
    logger.info(f"🎯 Universe: {universe} ({len(symbols)} stocks)")

    if run_coverage:
        from ml_features import coverage_report
        cov = coverage_report(symbols, period=f"{history_years}y", max_workers=max_workers)
        # Use only tickers with sufficient history for training
        good_symbols = set(cov["ok"] + [s for g in cov["gapped"] if g["coverage_pct"] >= 50
                                        for s in [g["symbol"]]])
        # Always include Nifty50 regardless of coverage
        symbols = [s for s in symbols if s in good_symbols or s in NIFTY_50]
        logger.info(f"📊 After coverage filter: {len(symbols)} symbols retained")
        (run_dir / "coverage_report.json").write_text(
            json.dumps(cov, indent=2, default=str)
        )

    # ── 2. Collect data ──────────────────────────────────────────────────────
    raw_df = build_training_dataset(
        symbols, forward_days, threshold_pct, history_years, max_workers
    )

    # ── 2a. Liquidity filter ─────────────────────────────────────────────────
    # Exclude stocks with insufficient trading volume.
    # avg_daily_turnover = avg_volume × avg_close. Since generate_labels doesn't
    # store absolute price/volume, we use volume_ratio × a proxy.
    # Full turnover filter is applied at universe level; here we just log.
    try:
        import yaml as _yaml
        _liq_cfg = _BACKEND_DIR / "configs" / "liquidity_config.yaml"
        if _liq_cfg.exists():
            _liq = _yaml.safe_load(_liq_cfg.read_text()).get("liquidity_filter", {})
            min_turnover = _liq.get("min_avg_daily_turnover_cr", 10)
            logger.info(f"  💧 Liquidity filter: min ₹{min_turnover}cr avg daily turnover")
            # Flag low-volume rows: volume_ratio < 0.3 for >50% of rows per symbol = thin
            if "volume_ratio" in raw_df.columns:
                sym_avg_vol = raw_df.groupby("symbol")["volume_ratio"].mean()
                liquid_syms = sym_avg_vol[sym_avg_vol >= 0.3].index
                before = raw_df["symbol"].nunique()
                raw_df = raw_df[raw_df["symbol"].isin(liquid_syms)]
                after  = raw_df["symbol"].nunique()
                if before > after:
                    logger.info(f"  💧 Removed {before-after} low-volume symbols "
                                f"({before} → {after})")
    except Exception as e:
        logger.debug(f"  Liquidity filter skipped: {e}")

    # ── 2b. Macro / regime features ──────────────────────────────────────────
    try:
        from macro_features import build_macro_df, merge_macro
        logger.info("  📡 Merging macro features (VIX, USDINR, Brent)…")
        macro_df = build_macro_df(start="2016-01-01")
        raw_df   = merge_macro(raw_df, macro_df)
    except Exception as e:
        logger.warning(f"  ⚠️  Macro features unavailable ({e}) — training without them")

    # ── 2c. Cross-sectional rank features ────────────────────────────────────
    try:
        from cross_sectional_features import add_cross_sectional_ranks
        logger.info("  📐 Computing cross-sectional rank features…")
        raw_df = add_cross_sectional_ranks(raw_df)
    except Exception as e:
        logger.warning(f"  ⚠️  Rank features unavailable ({e}) — training without them")

    # ── 3. Feature matrix ────────────────────────────────────────────────────
    feature_cols = [c for c in FEATURE_COLUMNS if c in raw_df.columns]
    X = raw_df[feature_cols].fillna(0).astype(float).values
    y = raw_df["label"].astype(int).values

    logger.info(
        f"📐 Feature matrix: {X.shape[0]:,} rows × {X.shape[1]} features | "
        f"date range: {raw_df['date'].min().date()} → {raw_df['date'].max().date()}"
    )


    # ── 4. Scale (fit on ALL data — scaler is saved separately) ─────────────
    from sklearn.preprocessing import StandardScaler
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # ── 5. Walk-forward splits ───────────────────────────────────────────────
    embargo_rows = embargo_days if embargo_days else max(forward_days + 5, 15)
    splits = generate_wf_splits(
        raw_df,
        n_folds=n_folds,
        embargo_days=embargo_rows,
        min_train_rows=3000,
        expanding=True,
    )

    if not splits:
        raise RuntimeError(
            "No valid walk-forward folds generated — dataset may be too small. "
            "Try --n-folds 3 or a longer --history-years."
        )

    # ── 6. Walk-forward loop ─────────────────────────────────────────────────
    fold_metrics: List[Dict] = []
    fold_importances: List[np.ndarray] = []
    best_params = None

    pos_total = y.sum()
    neg_total = len(y) - pos_total

    for fold_idx, (tr_idx, te_idx) in enumerate(splits):
        logger.info(f"\n{'═' * 60}")
        logger.info(f"  FOLD {fold_idx + 1} / {len(splits)}")
        logger.info(f"{'═' * 60}")

        assert embargo_check(tr_idx, te_idx), f"Fold {fold_idx+1}: embargo violation!"

        X_train, y_train = X_scaled[tr_idx], y[tr_idx]
        X_val,   y_val   = X_scaled[te_idx], y[te_idx]

        pos_rate = y_train.mean()
        pos_cnt  = y_train.sum()
        neg_cnt  = len(y_train) - pos_cnt

        # ── Optional SMOTE on training portion only ──────────────────────────
        if use_smote and pos_rate < 0.35:
            try:
                from imblearn.over_sampling import SMOTE
                smote = SMOTE(
                    random_state=42 + fold_idx,
                    k_neighbors=min(5, pos_cnt - 1),
                    sampling_strategy=0.5,
                )
                X_train, y_train = smote.fit_resample(X_train, y_train)
                logger.info(
                    f"  🔄 SMOTE: {len(X_train):,} samples "
                    f"({y_train.sum()} pos, was {pos_cnt})"
                )
            except Exception as e:
                logger.warning(f"  SMOTE skipped: {e}")

        # ── Hyperparameter tuning (first fold only if --tune) ────────────────
        if tune_hyperparams and fold_idx == 0:
            best_params = _tune(model_backend, X_train, y_train, X_val, y_val)
            logger.info(f"🔬 Tuned params: {best_params}")

        # ── Build params for this fold ────────────────────────────────────────
        pos_cnt_cur  = int(y_train.sum())
        neg_cnt_cur  = int(len(y_train) - pos_cnt_cur)

        if best_params:
            params = best_params.copy()
        elif model_backend == "lgbm":
            params = _default_lgbm_params(pos_cnt_cur, neg_cnt_cur)
        else:
            params = _default_xgb_params(pos_cnt_cur, neg_cnt_cur)

        # When SMOTE is active the class ratio is already balanced → reset weight
        if use_smote and pos_rate < 0.35:
            params["scale_pos_weight"] = 1.0

        # ── Train ─────────────────────────────────────────────────────────────
        logger.info(
            f"  🚂 Training {model_backend.upper()} "
            f"(n_train={len(X_train):,}, n_val={len(X_val):,})…"
        )
        if model_backend == "lgbm":
            model = _build_lgbm(params, X_train, y_train, X_val, y_val)
        else:
            model = _build_xgb(params, X_train, y_train, X_val, y_val)

        # ── Evaluate ──────────────────────────────────────────────────────────
        test_dr = fold_date_range(raw_df, te_idx)
        metrics = _evaluate_fold(model, X_val, y_val, fold_idx, test_dr)
        metrics["n_train"] = len(X_train)
        fold_metrics.append(metrics)

        # Save feature importances
        try:
            fold_importances.append(model.feature_importances_)
        except Exception:
            pass

        # ── Write per-fold JSON ───────────────────────────────────────────────
        fold_json = run_dir / f"fold_{fold_idx + 1:02d}.json"
        fold_json.write_text(json.dumps(metrics, indent=2))
        logger.info(f"  💾 Fold log → {fold_json.name}")

    # ── 7. Aggregate metrics ──────────────────────────────────────────────────
    auc_vals  = [m["auc"]       for m in fold_metrics]
    ap_vals   = [m["avg_prec"]  for m in fold_metrics]
    prec_vals = [m["precision"] for m in fold_metrics]
    rec_vals  = [m["recall"]    for m in fold_metrics]
    f1_vals   = [m["f1"]        for m in fold_metrics]

    aggregate = {
        "n_folds":       len(fold_metrics),
        "auc_mean":      round(float(np.mean(auc_vals)),  4),
        "auc_std":       round(float(np.std(auc_vals)),   4),
        "ap_mean":       round(float(np.mean(ap_vals)),   4),
        "ap_std":        round(float(np.std(ap_vals)),    4),
        "prec_mean":     round(float(np.mean(prec_vals)), 4),
        "rec_mean":      round(float(np.mean(rec_vals)),  4),
        "f1_mean":       round(float(np.mean(f1_vals)),   4),
    }

    logger.info(f"\n{'=' * 60}")
    logger.info("  WALK-FORWARD AGGREGATE METRICS")
    logger.info(f"{'=' * 60}")
    logger.info(f"  Folds:          {aggregate['n_folds']}")
    logger.info(f"  AUC-ROC:        {aggregate['auc_mean']:.4f} ± {aggregate['auc_std']:.4f}")
    logger.info(f"  Avg Precision:  {aggregate['ap_mean']:.4f} ± {aggregate['ap_std']:.4f}")
    logger.info(f"  Precision@0.5:  {aggregate['prec_mean']:.4f}")
    logger.info(f"  Recall@0.5:     {aggregate['rec_mean']:.4f}")
    logger.info(f"  F1@0.5:         {aggregate['f1_mean']:.4f}")
    logger.info(f"{'=' * 60}\n")

    # ── 8. Average feature importances across folds ────────────────────────
    importances: Dict[str, float] = {}
    if fold_importances:
        avg_imp = np.mean(np.stack(fold_importances), axis=0)
        importances = {
            feat: round(float(v), 6)
            for feat, v in zip(feature_cols, avg_imp)
        }
        top10 = sorted(importances.items(), key=lambda x: -x[1])[:10]
        logger.info("🔑 Top-10 avg feature importances (across folds):")
        for feat, imp in top10:
            logger.info(f"   {feat:<25} {imp:.4f}")

    # ── 9. Final model: retrain on ALL data using averaged params ─────────
    logger.info("\n🏋️  Retraining final model on full dataset…")
    pos_cnt_final = int(y.sum())
    neg_cnt_final = int(len(y) - pos_cnt_final)

    if best_params:
        final_params = best_params.copy()
    elif model_backend == "lgbm":
        final_params = _default_lgbm_params(pos_cnt_final, neg_cnt_final)
    else:
        final_params = _default_xgb_params(pos_cnt_final, neg_cnt_final)

    # Final model trains on 100% of data — no val set for early stopping
    # → use a fixed n_estimators from the best params (no early stopping callback)
    X_final = X_scaled
    y_final = y

    if use_smote and (pos_cnt_final / len(y_final)) < 0.35:
        try:
            from imblearn.over_sampling import SMOTE
            smote = SMOTE(
                random_state=42,
                k_neighbors=min(5, pos_cnt_final - 1),
                sampling_strategy=0.5,
            )
            X_final, y_final = smote.fit_resample(X_final, y_final)
            final_params["scale_pos_weight"] = 1.0
            logger.info(f"🔄 Final SMOTE: {len(X_final):,} samples")
        except Exception as e:
            logger.warning(f"Final SMOTE skipped: {e}")

    if model_backend == "lgbm":
        from lightgbm import LGBMClassifier
        # No early stopping on full data — remove stopping rounds if present
        fp = {k: v for k, v in final_params.items() if k not in ("callbacks",)}
        final_model = LGBMClassifier(**fp)
        final_model.fit(X_final, y_final)
        wrapped = CalibratedLGBMModel(final_model)
    else:
        from xgboost import XGBClassifier
        fp = {k: v for k, v in final_params.items()}
        final_model = XGBClassifier(
            **fp, tree_method="hist", eval_metric="auc",
            random_state=42, n_jobs=-1,
        )
        final_model.fit(X_final, y_final)
        wrapped = final_model  # raw XGB (no calibration — same as v1)

    # ── 10. Save artifacts ────────────────────────────────────────────────────
    joblib.dump(wrapped, MODEL_PATH)
    joblib.dump(scaler,  SCALER_PATH)

    meta = {
        "trained_at":       datetime.utcnow().isoformat() + "Z",
        "universe":         universe,
        "model_backend":    model_backend,
        "n_symbols":        len(symbols),
        "n_total_rows":     int(len(X)),
        "history_years":    history_years,
        "forward_days":     forward_days,
        "threshold_pct":    threshold_pct,
        "positive_rate":    round(float(y.mean()), 4),
        "walk_forward":     True,
        "n_folds":          len(fold_metrics),
        "embargo_days":     embargo_rows,
        "feature_columns":  feature_cols,
        "n_features":       len(feature_cols),
        "metrics": {
            "val_auc":   aggregate["auc_mean"],   # kept for backward-compat with kepler_model.py
            "val_ap":    aggregate["ap_mean"],
            "val_prec":  aggregate["prec_mean"],
            "val_rec":   aggregate["rec_mean"],
            "val_f1":    aggregate["f1_mean"],
            "auc_std":   aggregate["auc_std"],
        },
        "fold_metrics":     fold_metrics,
        "aggregate":        aggregate,
        "feature_importances": dict(
            sorted(importances.items(), key=lambda x: -x[1])[:20]
        ),
        "experiment_run_dir": str(run_dir),
    }

    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2)

    # ── Write experiment summary ──────────────────────────────────────────────
    summary = {
        "run_id":        run_ts,
        "universe":      universe,
        "model_backend": model_backend,
        "history_years": history_years,
        "n_folds":       len(fold_metrics),
        "embargo_days":  embargo_rows,
        "aggregate":     aggregate,
        "fold_metrics":  fold_metrics,
        "top_features":  dict(sorted(importances.items(), key=lambda x: -x[1])[:10]),
        "config": {
            "forward_days":  forward_days,
            "threshold_pct": threshold_pct,
            "use_smote":     use_smote,
            "tune_hyperparams": tune_hyperparams,
        },
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    logger.info(f"💾 Model saved    → {MODEL_PATH}")
    logger.info(f"💾 Scaler saved   → {SCALER_PATH}")
    logger.info(f"💾 Metadata saved → {META_PATH}")
    logger.info(f"💾 Experiment log → {run_dir / 'summary.json'}")

    return meta


# ── Optional Optuna tuning ─────────────────────────────────────────────────────
def _tune(backend: str, X_train, y_train, X_val, y_val) -> Dict:
    """Run Optuna on the first fold and return best params."""
    import optuna
    from sklearn.metrics import roc_auc_score

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    logger.info("🔬 Optuna tuning (40 trials, 5 min max)…")

    def objective(trial):
        if backend == "lgbm":
            from lightgbm import LGBMClassifier, early_stopping, log_evaluation
            params = {
                "n_estimators":      trial.suggest_int("n_estimators", 400, 1200),
                "learning_rate":     trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
                "num_leaves":        trial.suggest_int("num_leaves", 31, 127),
                "min_child_samples": trial.suggest_int("min_child_samples", 10, 50),
                "subsample":         trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree":  trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "reg_alpha":         trial.suggest_float("reg_alpha", 1e-4, 1.0, log=True),
                "reg_lambda":        trial.suggest_float("reg_lambda", 1e-4, 10.0, log=True),
                "scale_pos_weight":  trial.suggest_float("scale_pos_weight", 1.0, 6.0),
                "random_state": 42, "n_jobs": -1, "verbose": -1,
            }
            m = LGBMClassifier(**params)
            m.fit(X_train, y_train,
                  eval_set=[(X_val, y_val)],
                  callbacks=[early_stopping(30, verbose=False), log_evaluation(-1)])
        else:
            from xgboost import XGBClassifier
            params = {
                "n_estimators":    trial.suggest_int("n_estimators", 200, 600),
                "max_depth":       trial.suggest_int("max_depth", 3, 8),
                "learning_rate":   trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
                "subsample":       trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
                "gamma":           trial.suggest_float("gamma", 0, 5),
                "reg_alpha":       trial.suggest_float("reg_alpha", 1e-4, 1.0, log=True),
                "reg_lambda":      trial.suggest_float("reg_lambda", 1e-4, 10.0, log=True),
                "tree_method": "hist", "eval_metric": "auc",
                "random_state": 42, "n_jobs": -1,
            }
            m = XGBClassifier(**params, early_stopping_rounds=30)
            m.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

        proba = m.predict_proba(X_val)[:, 1]
        return roc_auc_score(y_val, proba)

    study = optuna.create_study(direction="maximize")
    study.optimize(objective, n_trials=40, timeout=300)
    logger.info(f"🔬 Optuna best AUC: {study.best_value:.4f}")
    return study.best_params


# ── CLI entrypoint ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Kepler ML Walk-Forward Training Pipeline",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--universe", choices=["nifty50", "nifty200", "nifty500"],
        default="nifty200",
        help="Stock universe to train on",
    )
    parser.add_argument(
        "--forward-days", type=int, default=10,
        help="Days ahead for return label (e.g. 10 = next 10 trading days)",
    )
    parser.add_argument(
        "--threshold", type=float, default=5.0,
        help="Minimum %% gain to label as 'Buy' (positive class)",
    )
    parser.add_argument(
        "--n-folds", type=int, default=5,
        help="Number of walk-forward folds (default 5 → ~19-month test windows at 8y)",
    )
    parser.add_argument(
        "--embargo-days", type=int, default=15,
        help="Purge+embargo gap in trading rows around each fold boundary",
    )
    parser.add_argument(
        "--history-years", type=int, default=8,
        help="Years of OHLCV history to pull per ticker (best-effort via yfinance)",
    )
    parser.add_argument(
        "--model", choices=["lgbm", "xgb"], default="lgbm",
        help="Model backend: lgbm (LightGBM, default) or xgb (XGBoost)",
    )
    parser.add_argument(
        "--workers", type=int, default=8,
        help="Parallel workers for data collection",
    )
    parser.add_argument(
        "--tune", action="store_true",
        help="Run Optuna hyperparameter tuning on first fold (adds ~5 min)",
    )
    parser.add_argument(
        "--no-smote", action="store_true",
        help="Disable SMOTE oversampling",
    )
    parser.add_argument(
        "--no-coverage", action="store_true",
        help="Skip coverage report (faster startup)",
    )
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | {message}")

    t_start = time.time()
    logger.info("=" * 62)
    logger.info("   KEPLER WALK-FORWARD TRAINING PIPELINE")
    logger.info(f"   universe={args.universe}  model={args.model}  "
                f"folds={args.n_folds}  history={args.history_years}y")
    logger.info("=" * 62)

    meta = train(
        universe=args.universe,
        forward_days=args.forward_days,
        threshold_pct=args.threshold,
        n_folds=args.n_folds,
        embargo_days=args.embargo_days,
        history_years=args.history_years,
        model_backend=args.model,
        use_smote=not args.no_smote,
        tune_hyperparams=args.tune,
        max_workers=args.workers,
        run_coverage=not args.no_coverage,
    )

    elapsed = time.time() - t_start
    logger.info(f"\n🏁 Training complete in {elapsed / 60:.1f} min")
    logger.info(f"   Mean AUC: {meta['metrics']['val_auc']} ± {meta['metrics']['auc_std']}")
    logger.info(f"   Model:    {MODEL_PATH}")
    logger.info(f"   Folds:    {meta['n_folds']}")
    logger.info(f"   Logs:     {meta['experiment_run_dir']}")
