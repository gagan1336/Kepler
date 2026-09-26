"""
KEPLER — Order Flow Feature Ablation
======================================
Evaluates the impact of Phase-D order-flow features on the frozen 42-stock
holdout set. Produces an honest comparison of AUC and net expectancy with
vs. without the new features, plus a feature importance ranking so we can
see whether order blocks, FVGs, and sweeps earn their place next to
india_vix and the existing cross-sectional rank features.

Usage
-----
    cd backend
    python ablation_order_flow.py [--history-years 5] [--forward-days 10]

Output
------
  stdout: ablation table (AUC, net expectancy, precision @ threshold)
          + feature importance ranking for order-flow columns only
  models/ablation_order_flow_<timestamp>.json : full results for later review
"""

import argparse
import json
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
import yaml

warnings.filterwarnings("ignore")

_BACKEND = Path(__file__).parent
sys.path.insert(0, str(_BACKEND))

from ml_features import generate_labels, FEATURE_COLUMNS  # noqa: E402
from order_flow import ORDER_FLOW_COLUMNS                  # noqa: E402

# ── Paths ─────────────────────────────────────────────────────────────────────
_HOLDOUT_YAML = _BACKEND / "configs" / "frozen_holdout.yaml"
_MODELS_DIR   = _BACKEND / "models"
MODEL_PATH    = _MODELS_DIR / "kepler_model.pkl"
SCALER_PATH   = _MODELS_DIR / "kepler_scaler.pkl"
META_PATH     = _MODELS_DIR / "kepler_meta.json"


def load_holdout_tickers() -> List[str]:
    with open(_HOLDOUT_YAML) as f:
        data = yaml.safe_load(f)
    return data["tickers"]


def collect_holdout_data(
    symbols: List[str],
    forward_days: int,
    history_years: int,
    max_workers: int = 6,
) -> pd.DataFrame:
    print(f"\n[1/4] Downloading holdout data ({len(symbols)} stocks, {history_years}y history)…")
    t0 = time.time()
    frames: List[pd.DataFrame] = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(
                generate_labels, sym, forward_days, 5.0, f"{history_years}y"
            ): sym
            for sym in symbols
        }
        for i, fut in enumerate(as_completed(futures), 1):
            sym = futures[fut]
            try:
                df = fut.result()
                if df is not None and len(df) > 0:
                    frames.append(df)
                    print(f"  [{i:>2}/{len(symbols)}] {sym:<20} {len(df):>5} rows")
                else:
                    print(f"  [{i:>2}/{len(symbols)}] {sym:<20} — skipped (no data)")
            except Exception as e:
                print(f"  [{i:>2}/{len(symbols)}] {sym:<20} — error: {e}")

    if not frames:
        raise RuntimeError("No holdout data could be collected.")

    combined = pd.concat(frames, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"])
    combined = combined.sort_values("date").reset_index(drop=True)
    print(f"  -> {len(combined):,} total rows | {time.time()-t0:.0f}s")
    return combined


def _compute_metrics(
    model,
    scaler,
    X: np.ndarray,
    y: np.ndarray,
    fwd_ret: np.ndarray,
    max_gain: np.ndarray,
    max_loss: np.ndarray,
    label: str,
) -> Dict:
    """Compute ROC-AUC, net expectancy, and precision at 60% threshold."""
    from sklearn.metrics import roc_auc_score

    X_scaled = scaler.transform(X)
    proba    = model.predict_proba(X_scaled)[:, 1]

    auc = float(roc_auc_score(y, proba))

    # Net expectancy: for all bars where model says "buy" (prob >= 0.5)
    buy_mask = proba >= 0.5
    if buy_mask.sum() > 0:
        wins    = (fwd_ret[buy_mask] >= 5.0).mean()
        avg_win  = fwd_ret[buy_mask & (fwd_ret >= 5.0)].mean() if (fwd_ret[buy_mask] >= 5.0).any() else 0.0
        avg_loss = fwd_ret[buy_mask & (fwd_ret <  5.0)].mean() if (fwd_ret[buy_mask] < 5.0).any()  else 0.0
        expectancy = wins * avg_win + (1 - wins) * avg_loss
    else:
        expectancy = 0.0

    # Precision at 60% confidence
    conf60_mask = proba >= 0.60
    prec60 = float(y[conf60_mask].mean()) if conf60_mask.sum() > 0 else 0.0

    return {
        "label":       label,
        "n_samples":   len(y),
        "n_buy_signals": int(buy_mask.sum()),
        "auc":         round(auc, 4),
        "expectancy":  round(float(expectancy), 3),
        "precision_60": round(prec60, 4),
        "pos_rate":    round(float(y.mean()), 4),
    }


def run_ablation(
    forward_days: int = 10,
    history_years: int = 5,
    max_workers: int = 6,
):
    print("=" * 62)
    print("  KEPLER -- Order Flow Ablation on Frozen 42-Stock Holdout")
    print("=" * 62)

    # ── Load model + scaler ────────────────────────────────────────────────
    if not MODEL_PATH.exists():
        print(f"\nModel not found at {MODEL_PATH}")
        print("   Run: python train_model.py --universe nifty200")
        sys.exit(1)

    print(f"\n[0/4] Loading model from {MODEL_PATH.name}...")
    model  = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)

    # Determine feature count from scaler
    n_scaler_features = scaler.n_features_in_
    print(f"  Model trained on {n_scaler_features} features")

    # ── Load holdout tickers ───────────────────────────────────────────────
    symbols = load_holdout_tickers()
    print(f"  Holdout: {len(symbols)} stocks from frozen_holdout.yaml")

    # ── Download holdout data (includes order-flow features) ───────────────
    df = collect_holdout_data(symbols, forward_days, history_years, max_workers)

    # ── Build feature matrices ─────────────────────────────────────────────
    print(f"\n[2/4] Building feature matrices...")

    # Baseline: all FEATURE_COLUMNS except Phase-D order-flow
    baseline_cols = [c for c in FEATURE_COLUMNS if c not in ORDER_FLOW_COLUMNS]
    full_cols     = FEATURE_COLUMNS

    # Ensure all columns exist (fill missing with zero / neutral)
    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            neutral = 1.0 if col == "bias_daily" else (
                60.0 if col == "fvg_bars_since" else (
                    5.0 if col in ("ob_dist_above_atr", "ob_dist_below_atr") else 0.0
                )
            )
            df[col] = neutral

    df[FEATURE_COLUMNS] = df[FEATURE_COLUMNS].fillna(0).astype(float)

    y        = df["label"].values.astype(int)
    fwd_ret  = df["fwd_ret_raw"].values
    max_gain = df["max_fwd_gain"].values
    max_loss = df["max_fwd_loss"].values

    X_baseline = df[baseline_cols].values
    X_full     = df[full_cols].values

    print(f"  Baseline features:  {len(baseline_cols)}")
    print(f"  Full features:      {len(full_cols)} (+{len(ORDER_FLOW_COLUMNS)} order-flow)")
    print(f"  Holdout samples:    {len(y):,}")
    print(f"  Positive rate:      {y.mean():.1%}")

    # ── Evaluate ───────────────────────────────────────────────────────────
    print(f"\n[3/4] Evaluating model on holdout...")

    # The production model was trained on n_scaler_features features.
    # We re-fit a NEW scaler on just this data for a fair head-to-head
    # comparison (otherwise baseline vs full use different scalers).
    import lightgbm as lgb

    def _roc_auc_fast(y_true: np.ndarray, y_score: np.ndarray) -> float:
        """
        Fast vectorised ROC-AUC using rank sum — avoids sklearn's pairwise
        distances module which has a corrupted Cython extension on this system.
        Identical result to sklearn.metrics.roc_auc_score for binary labels.
        """
        from scipy.stats import rankdata
        n_pos = int((y_true == 1).sum())
        n_neg = int((y_true == 0).sum())
        if n_pos == 0 or n_neg == 0:
            return 0.5
        ranks = rankdata(y_score)
        rank_sum = ranks[y_true == 1].sum()
        return float((rank_sum - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))

    def _roc_auc(y_true, y_score):
        try:
            from sklearn.metrics import roc_auc_score
            return float(roc_auc_score(y_true, y_score))
        except Exception:
            return _roc_auc_fast(y_true, y_score)

    def _train_and_eval(X_train: np.ndarray, label: str) -> Dict:
        from sklearn.preprocessing import StandardScaler
        sc = StandardScaler().fit(X_train)
        X_sc = sc.transform(X_train)

        # Simple LightGBM (fast, no tuning — same config as production baseline)
        pos_count = int(y.sum())
        neg_count = int(len(y) - pos_count)
        clf = lgb.LGBMClassifier(
            n_estimators=400,
            learning_rate=0.05,
            num_leaves=31,
            scale_pos_weight=neg_count / max(pos_count, 1),
            random_state=42,
            verbose=-1,
        )

        # 80/20 temporal split (last 20% is eval)
        split_idx = int(len(X_sc) * 0.80)
        X_tr, X_ev = X_sc[:split_idx], X_sc[split_idx:]
        y_tr, y_ev = y[:split_idx], y[split_idx:]
        fr_ev  = fwd_ret[split_idx:]

        clf.fit(X_tr, y_tr)

        proba = clf.predict_proba(X_ev)[:, 1]
        auc   = _roc_auc(y_ev, proba)

        buy_mask = proba >= 0.5
        if buy_mask.sum() > 0:
            buy_returns = fr_ev[buy_mask]
            win_cond    = buy_returns >= 5.0
            avg_win     = float(buy_returns[win_cond].mean())  if win_cond.any()   else 0.0
            avg_loss    = float(buy_returns[~win_cond].mean()) if (~win_cond).any() else 0.0
            win_rate    = float(win_cond.mean())
            expectancy  = win_rate * avg_win + (1 - win_rate) * avg_loss
        else:
            expectancy, win_rate = 0.0, 0.0

        conf60_mask = proba >= 0.60
        prec60 = float(y_ev[conf60_mask].mean()) if conf60_mask.sum() > 0 else 0.0

        # Feature importance (only for order-flow features)
        imp = dict(zip(
            [f"feat_{j}" for j in range(X_train.shape[1])],
            clf.feature_importances_,
        ))

        return {
            "label":        label,
            "n_train":      split_idx,
            "n_eval":       len(y_ev),
            "auc":          round(auc, 4),
            "expectancy":   round(float(expectancy), 3),
            "win_rate":     round(win_rate, 4),
            "precision_60": round(prec60, 4),
            "pos_rate":     round(float(y_ev.mean()), 4),
            "n_buy_signals": int(buy_mask.sum()),
            "feature_importances": clf.feature_importances_.tolist(),
            "feature_names": list(
                baseline_cols if label == "baseline" else full_cols
            ),
        }

    res_baseline = _train_and_eval(X_baseline, "baseline")
    res_full     = _train_and_eval(X_full,     "full")

    # ── Print ablation table ───────────────────────────────────────────────
    print(f"\n[4/4] Results\n")
    print("=" * 62)
    print(f"  ABLATION: Order Flow Features vs Baseline (Phase C-r)")
    print(f"  Frozen holdout | forward_days={forward_days} | threshold=5%")
    print("=" * 62)
    print(f"  {'Metric':<25}  {'Baseline':>10}  {'+ OrderFlow':>12}  {'Delta':>8}")
    print("  " + "-" * 58)

    def _delta(a, b, pct=False):
        d = b - a
        sign = "+" if d >= 0 else ""
        if pct:
            return f"{sign}{d*100:.2f}pp"
        return f"{sign}{d:.4f}"

    metrics = [
        ("ROC-AUC",        "auc",          False),
        ("Net Expectancy", "expectancy",    False),
        ("Precision @60%", "precision_60",  False),
        ("Win Rate",        "win_rate",     False),
    ]
    for name, key, pct in metrics:
        bv = res_baseline[key]
        fv = res_full[key]
        dv = _delta(bv, fv, pct)
        print(f"  {name:<25}  {bv:>10.4f}  {fv:>12.4f}  {dv:>8}")

    print(f"  {'Buy Signals':<25}  {res_baseline['n_buy_signals']:>10}  "
          f"{res_full['n_buy_signals']:>12}")

    # ── Feature importance for order-flow features ─────────────────────────
    print(f"\n  Order-Flow Feature Importance (within full model):")
    print("  " + "-" * 58)
    imp_full  = np.array(res_full["feature_importances"])
    names_full = res_full["feature_names"]
    ranked = sorted(
        zip(names_full, imp_full),
        key=lambda x: -x[1]
    )
    total_imp = imp_full.sum()
    of_set    = set(ORDER_FLOW_COLUMNS)
    all_ranks = {name: rank + 1 for rank, (name, _) in enumerate(ranked)}

    print(f"  {'Feature':<26}  {'Rank':>6}  {'Importance':>12}  {'Share':>8}")
    print("  " + "-" * 58)
    for name, imp_val in ranked:
        if name in of_set:
            share = imp_val / total_imp if total_imp > 0 else 0
            rank  = all_ranks[name]
            print(f"  {name:<26}  {rank:>6}  {imp_val:>12.1f}  {share:>7.2%}")

    print(f"\n  (Total features in full model: {len(names_full)})")
    print("=" * 62)

    # Verdict
    auc_delta = res_full["auc"] - res_baseline["auc"]
    exp_delta = res_full["expectancy"] - res_baseline["expectancy"]
    if auc_delta > 0.005 or exp_delta > 0.5:
        verdict = "[LIFT] Order-flow features show meaningful lift -- recommend including in next retrain."
    elif auc_delta > 0 and exp_delta > 0:
        verdict = "[MARGINAL] Marginal lift -- include but monitor; may need more training data to confirm."
    elif auc_delta > -0.005:
        verdict = "[NEUTRAL] Features add no harm but no clear benefit. Re-evaluate after full retrain."
    else:
        verdict = "[DROP] Order-flow features hurt performance -- exclude from production until further study."

    print(f"\n  Verdict: {verdict}\n")

    # ── Save results ───────────────────────────────────────────────────────
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path  = _MODELS_DIR / f"ablation_order_flow_{timestamp}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({
            "run_at":       timestamp,
            "forward_days": forward_days,
            "history_years": history_years,
            "holdout_n":    len(symbols),
            "baseline":     res_baseline,
            "full":         res_full,
            "auc_delta":    round(auc_delta, 4),
            "exp_delta":    round(exp_delta, 3),
            "verdict":      verdict,
        }, f, indent=2)
    print(f"  Full results saved to: {out_path.name}\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Order flow feature ablation on frozen holdout")
    parser.add_argument("--history-years", type=int, default=5,
                        help="Years of price history per stock (default: 5)")
    parser.add_argument("--forward-days",  type=int, default=10,
                        help="Forward return horizon in days (default: 10)")
    parser.add_argument("--workers",       type=int, default=6,
                        help="Parallel download workers (default: 6)")
    args = parser.parse_args()

    run_ablation(
        forward_days=args.forward_days,
        history_years=args.history_years,
        max_workers=args.workers,
    )
