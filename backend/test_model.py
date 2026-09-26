"""
KEPLER — Multi-Dataset Model Evaluation
=========================================
Tests the trained kepler_model.pkl against 8 distinct evaluation sets to
measure generalisation across:
  1. In-universe stocks      (Nifty50 — training set)
  2. Out-of-universe stocks  (Nifty200 extras — never seen during training)
  3. Small/mid cap           (Nifty500 extras — lowest liquidity tier)
  4. Sector slices           (IT, Banking, Pharma, Auto, Energy)
  5. Volatility regime       (high-vol vs low-vol sub-periods)

Usage
-----
    cd backend
    python test_model.py                        # all 8 test sets
    python test_model.py --quick                # only 5 fast sets (skip vol regimes)
    python test_model.py --workers 12           # more parallel fetches

Output
------
    Console: comparison table (AUC, AP, Prec, Rec, N_samples)
    File:    configs/experiment_runs/eval_<timestamp>.json
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
_BACKEND_DIR = Path(__file__).parent
_MODELS_DIR  = _BACKEND_DIR / "models"
_CONFIGS_DIR = _BACKEND_DIR / "configs" / "experiment_runs"
MODEL_PATH   = _MODELS_DIR / "kepler_model.pkl"
SCALER_PATH  = _MODELS_DIR / "kepler_scaler.pkl"
META_PATH    = _MODELS_DIR / "kepler_meta.json"

# ── Universe definitions (mirrors train_model.py) ─────────────────────────────
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
    "BANKBARODA", "FEDERALBNK", "PNB", "CANBK", "UNIONBANK",
    "IDFCFIRSTB", "BANDHANBNK", "AUBANK", "RBLBANK", "YESBANK",
    "MUTHOOTFIN", "BAJAJHLDNG", "CHOLAFIN", "MANAPPURAM", "ABCAPITAL",
    "LTIMINDTECH", "PERSISTENT", "COFORGE", "MPHASIS", "OFSS", "KPITTECH",
    "TORNTPHARM", "AUROPHARMA", "ALKEM", "LUPIN", "BIOCON",
    "IPCALAB", "ABBOTINDIA", "PFIZER", "SANOFI",
    "TATAMOTORS", "TVSMOTOR", "MOTHERSON", "BOSCHLTD", "EXIDEIND",
    "MRF", "CEATLTD", "BALKRISIND",
    "GODREJCP", "DABUR", "MARICO", "COLPAL", "VBL",
    "ADANIGREEN", "TORNTPOWER", "TATAPOWER", "NHPC", "RECLTD", "PFC",
    "SIEMENS", "ABB", "HAVELLS", "CUMMINSIND", "THERMAX", "BHEL",
    "VEDL", "HINDZINC", "SAIL", "NMDC", "JINDALSTEL",
    "DLF", "GODREJPROP", "OBEROIRLTY",
    "DMART", "ETERNAL", "NYKAA",    # ETERNAL = Zomato post-rename
    "SHREECEM", "AMBUJACEM", "ACC",
    "PIDILITIND", "ASTRAL", "SRF",
    "IRCTC", "HAL", "POLYCAB", "DIXON",
]

NIFTY_500_EXTRA = [
    "ICICIGI", "SBICARD", "ANGELONE", "IIFL",
    "ZEEL", "PVRINOX", "INOXWIND",
    "GLENMARK", "NATCOPHARM", "GLAND", "ERIS", "GRANULES",
    "TANLA", "INTELLECT", "NEWGEN", "RATEGAIN", "INDIAMART",
    "TATAELXSI", "CYIENT", "ZENSARTECH", "BIRLASOFT",
    "ASTERDM", "NH",   # NH = Narayana Hrudayalaya
]

# ── Sector test slices — OOD ONLY (zero overlap with Nifty50 training set) ──────
# Each list below contains ONLY stocks NOT present in NIFTY_50.
# This ensures sector AUCs are honest out-of-distribution measurements.
NIFTY50_SET = {
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
}

SECTOR_SETS = {
    # IT — OOD only (TCS, INFY, HCLTECH, WIPRO, TECHM removed — all in Nifty50)
    "IT (OOD-only)": [
        "LTIMINDTECH", "PERSISTENT", "COFORGE", "MPHASIS", "OFSS",
        "KPITTECH", "TATAELXSI", "CYIENT",
    ],
    # Banking — OOD only (HDFCBANK, ICICIBANK, SBIN, KOTAKBANK, AXISBANK, INDUSINDBK removed)
    "Banking (OOD-only)": [
        "BANKBARODA", "FEDERALBNK", "PNB", "CANBK", "UNIONBANK",
        "IDFCFIRSTB", "BANDHANBNK", "AUBANK", "RBLBANK", "YESBANK",
    ],
    # Pharma — OOD only (SUNPHARMA, DRREDDY, CIPLA, DIVISLAB, APOLLOHOSP removed)
    "Pharma (OOD-only)": [
        "TORNTPHARM", "AUROPHARMA", "ALKEM", "LUPIN", "BIOCON",
        "ABBOTINDIA", "PFIZER", "GLENMARK", "GLAND",
    ],
    # Auto — OOD only (MARUTI, M&M, EICHERMOT, HEROMOTOCO, BAJAJ-AUTO removed)
    "Auto (OOD-only)": [
        "TVSMOTOR", "BOSCHLTD", "MRF", "MOTHERSON", "EXIDEIND",
        "CEATLTD", "BALKRISIND",
    ],
    # Energy — OOD only (ONGC, BPCL, NTPC, POWERGRID, COALINDIA removed)
    "Energy (OOD-only)": [
        "ADANIGREEN", "TATAPOWER", "NHPC", "RECLTD", "PFC", "TORNTPOWER",
    ],
    # Bonus: FMCG/Consumer — all OOD (none of these are in Nifty50)
    "FMCG (OOD-only)": [
        "GODREJCP", "DABUR", "MARICO", "COLPAL", "VBL", "RADICO",
    ],
    # Bonus: Industrials/Capital Goods — all OOD
    "Industrials (OOD-only)": [
        "SIEMENS", "ABB", "HAVELLS", "CUMMINSIND", "THERMAX", "POLYCAB",
    ],
}


# ── Data loading ──────────────────────────────────────────────────────────────
def load_model_artifacts():
    """Load model + scaler + metadata from disk."""
    if not MODEL_PATH.exists() or not SCALER_PATH.exists():
        logger.error(f"Model not found at {MODEL_PATH}. Run train_model.py first.")
        sys.exit(1)
    model  = joblib.load(MODEL_PATH)
    scaler = joblib.load(SCALER_PATH)
    meta   = json.loads(META_PATH.read_text()) if META_PATH.exists() else {}
    logger.info(
        f"✅ Model loaded | backend={meta.get('model_backend','?')} | "
        f"trained={meta.get('trained_at','?')[:10]} | "
        f"train_auc={meta.get('metrics',{}).get('val_auc','?')}"
    )
    return model, scaler, meta


def fetch_labeled_data(
    symbols: List[str],
    forward_days: int = 10,
    threshold_pct: float = 5.0,
    period: str = "2y",
    max_workers: int = 8,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
) -> Optional[pd.DataFrame]:
    """
    Pull labeled rows for a list of symbols.
    Optional date_start/date_end filters apply a time slice to stress-test
    the model on a specific market period.
    """
    from ml_features import generate_labels, FEATURE_COLUMNS

    frames = []
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(generate_labels, sym, forward_days, threshold_pct, period): sym
            for sym in symbols
        }
        for fut in as_completed(futures):
            try:
                df = fut.result()
                if df is not None and len(df) > 0:
                    frames.append(df)
            except Exception:
                pass

    if not frames:
        return None

    combined = pd.concat(frames, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"])
    # yfinance returns IST-aware timestamps; strip tz to allow naive comparisons
    if hasattr(combined["date"].dt, "tz") and combined["date"].dt.tz is not None:
        combined["date"] = combined["date"].dt.tz_localize(None)

    # Apply optional time slice
    if date_start:
        combined = combined[combined["date"] >= pd.Timestamp(date_start)]
    if date_end:
        combined = combined[combined["date"] <= pd.Timestamp(date_end)]

    return combined if len(combined) > 0 else None


# ── Evaluation core ───────────────────────────────────────────────────────────
def evaluate(
    df: pd.DataFrame,
    model,
    scaler,
    feature_cols: List[str],
    label: str,
) -> Dict:
    """Score a labeled DataFrame and return evaluation metrics."""
    from sklearn.metrics import (
        roc_auc_score, precision_score, recall_score,
        f1_score, average_precision_score,
    )

    # Align features
    for col in feature_cols:
        if col not in df.columns:
            df[col] = 0.0

    X = df[feature_cols].fillna(0).astype(float).values
    y = df["label"].astype(int).values

    if y.sum() == 0 or len(y) - y.sum() == 0:
        return {
            "label": label, "n_samples": len(y), "n_positive": int(y.sum()),
            "base_rate": round(float(y.mean()), 4),
            "auc": None, "avg_prec": None,
            "prec": None, "rec": None, "f1": None,
            "note": "single class — AUC undefined",
        }

    X_scaled = scaler.transform(X)
    proba = model.predict_proba(X_scaled)[:, 1]
    y_pred = (proba >= 0.5).astype(int)

    base_rate = float(y.mean())
    # Adaptive threshold at 1.5x base_rate (mirrors _classify_signal)
    adaptive_thresh = min(base_rate * 1.5, 0.6)
    y_pred_adaptive = (proba >= adaptive_thresh).astype(int)

    return {
        "label":       label,
        "n_samples":   len(y),
        "n_positive":  int(y.sum()),
        "base_rate":   round(base_rate, 4),
        "auc":         round(float(roc_auc_score(y, proba)), 4),
        "avg_prec":    round(float(average_precision_score(y, proba)), 4),
        "prec_0.5":    round(float(precision_score(y, y_pred, zero_division=0)), 4),
        "rec_0.5":     round(float(recall_score(y, y_pred, zero_division=0)), 4),
        "f1_0.5":      round(float(f1_score(y, y_pred, zero_division=0)), 4),
        "prec_adaptive": round(float(precision_score(y, y_pred_adaptive, zero_division=0)), 4),
        "rec_adaptive":  round(float(recall_score(y, y_pred_adaptive, zero_division=0)), 4),
        "f1_adaptive":   round(float(f1_score(y, y_pred_adaptive, zero_division=0)), 4),
        "adaptive_thresh": round(adaptive_thresh, 4),
        "score_mean":  round(float(proba.mean()), 4),
        "score_std":   round(float(proba.std()), 4),
        "score_p75":   round(float(np.percentile(proba, 75)), 4),
        "score_p90":   round(float(np.percentile(proba, 90)), 4),
    }


# ── Pretty printer ────────────────────────────────────────────────────────────
def print_results_table(results: List[Dict]) -> None:
    """Print a clean comparison table to the console."""
    header = (
        f"\n{'─'*100}\n"
        f"{'Test Set':<28} {'N':>6} {'Pos%':>6} {'AUC':>7} {'AvgP':>7} "
        f"{'Prec@0.5':>9} {'Rec@0.5':>8} {'Prec@adp':>9} {'Rec@adp':>8}\n"
        f"{'─'*100}"
    )
    logger.info(header)
    for r in results:
        if r.get("n_samples", 0) == 0:
            logger.info(f"  {r['label']:<26} {'— no data —':>60}")
            continue
        auc  = f"{r['auc']:.4f}"  if r.get("auc")  is not None else "  N/A  "
        ap   = f"{r['avg_prec']:.4f}" if r.get("avg_prec") is not None else "  N/A  "
        p05  = f"{r.get('prec_0.5', 0):.4f}"
        r05  = f"{r.get('rec_0.5', 0):.4f}"
        padp = f"{r.get('prec_adaptive', 0):.4f}"
        radp = f"{r.get('rec_adaptive', 0):.4f}"
        base = r.get("base_rate", 0) * 100
        logger.info(
            f"  {r['label']:<26} {r['n_samples']:>6,} {base:>5.1f}% "
            f"{auc:>7} {ap:>7} {p05:>9} {r05:>8} {padp:>9} {radp:>8}"
        )
    logger.info(f"{'─'*100}\n")


# ── Main evaluation runner ────────────────────────────────────────────────────
def run_evaluation(args) -> List[Dict]:
    model, scaler, meta = load_model_artifacts()
    feature_cols = meta.get("feature_columns", [])
    if not feature_cols:
        from ml_features import FEATURE_COLUMNS
        feature_cols = FEATURE_COLUMNS

    fwd   = meta.get("forward_days", 10)
    thr   = meta.get("threshold_pct", 5.0)
    period = "2y"    # use recent 2y for all eval sets (fast + comparable)

    results: List[Dict] = []
    all_sets = []

    # ── Test sets 1–3: Universe tiers ─────────────────────────────────────────
    all_sets.append(("Nifty50 (in-universe)",    NIFTY_50,         period, None,         None))
    all_sets.append(("Nifty200 Extra (OOD)",     NIFTY_200_EXTRA,  period, None,         None))
    all_sets.append(("Nifty500 Extra (small/mid)", NIFTY_500_EXTRA, period, None,         None))

    # ── Test sets 4–8: Sector slices ──────────────────────────────────────────
    for sector_name, sector_syms in SECTOR_SETS.items():
        all_sets.append((f"Sector — {sector_name}", sector_syms, period, None, None))

    # ── Volatility regime slices (optional — requires date filtering) ─────────
    if not args.quick:
        # Recent bull: Jan 2024 – Sep 2024 (Nifty ATH rally) — need 3y to reach Jan 2024
        all_sets.append(("Regime — Bull 2024",   NIFTY_50, "3y", "2024-01-01", "2024-09-30"))
        # Post-tariff: Apr 2025 – Aug 2025
        all_sets.append(("Regime — Tariff shock", NIFTY_50, "3y", "2025-04-01", "2025-08-31"))

    logger.info(f"\n📋 Running {len(all_sets)} test sets…\n")
    t0 = time.time()

    for label, symbols, p, d_start, d_end in all_sets:
        logger.info(f"⏳ {label} ({len(symbols)} stocks)…")
        t1 = time.time()

        df = fetch_labeled_data(
            symbols, forward_days=fwd, threshold_pct=thr,
            period=p, max_workers=args.workers,
            date_start=d_start, date_end=d_end,
        )

        if df is None or len(df) == 0:
            logger.warning(f"  ⚠️  No data for {label} — skipping")
            results.append({"label": label, "n_samples": 0, "note": "no data"})
            continue

        result = evaluate(df, model, scaler, feature_cols, label)
        results.append(result)
        auc_str = f"AUC={result['auc']}" if result.get("auc") else "AUC=N/A"
        logger.info(f"  ✅ {auc_str}  N={result['n_samples']:,}  ({time.time()-t1:.0f}s)")

    # ── Summary table ─────────────────────────────────────────────────────────
    logger.info(f"\n{'═'*60}")
    logger.info("  MULTI-DATASET EVALUATION RESULTS")
    logger.info(f"  Model trained: {meta.get('trained_at','?')[:10]}  "
                f"| Universe: {meta.get('universe','?')}  "
                f"| Backend: {meta.get('model_backend','?')}")
    logger.info(f"{'═'*60}")
    print_results_table(results)

    # ── AUC consistency check ─────────────────────────────────────────────────
    valid_aucs = [r["auc"] for r in results if r.get("auc") is not None]
    if valid_aucs:
        auc_mean = np.mean(valid_aucs)
        auc_min  = min(valid_aucs)
        auc_max  = max(valid_aucs)
        auc_std  = np.std(valid_aucs)
        logger.info(f"📊 AUC summary across {len(valid_aucs)} sets:")
        logger.info(f"   Mean:  {auc_mean:.4f}")
        logger.info(f"   Std:   {auc_std:.4f}")
        logger.info(f"   Range: {auc_min:.4f} → {auc_max:.4f}")
        # Warn if generalisation gap is large
        in_uni  = next((r["auc"] for r in results if "in-universe" in r["label"]), None)
        out_uni = next((r["auc"] for r in results if "OOD" in r["label"]), None)
        if in_uni and out_uni:
            gap = in_uni - out_uni
            logger.info(f"   Generalisation gap (Nifty50 vs OOD): {gap:+.4f}")
            if abs(gap) > 0.05:
                logger.warning(
                    f"   ⚠️  Gap > 0.05 — model may be overfitting to Nifty50 patterns. "
                    f"Consider retraining on nifty200."
                )
            else:
                logger.info(f"   ✅ Gap ≤ 0.05 — model generalises well across universes.")

    # ── Save JSON ─────────────────────────────────────────────────────────────
    _CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = _CONFIGS_DIR / f"eval_{ts}.json"
    out_path.write_text(json.dumps({
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
        "model_trained_at": meta.get("trained_at"),
        "model_universe":   meta.get("universe"),
        "model_backend":    meta.get("model_backend"),
        "model_auc_train":  meta.get("metrics", {}).get("val_auc"),
        "forward_days":     fwd,
        "threshold_pct":    thr,
        "test_sets":        results,
        "auc_summary": {
            "mean": round(float(auc_mean), 4) if valid_aucs else None,
            "std":  round(float(auc_std),  4) if valid_aucs else None,
            "min":  round(float(auc_min),  4) if valid_aucs else None,
            "max":  round(float(auc_max),  4) if valid_aucs else None,
        } if valid_aucs else {},
    }, indent=2))

    elapsed = time.time() - t0
    logger.info(f"\n🏁 Evaluation complete in {elapsed/60:.1f} min")
    logger.info(f"💾 Results saved → {out_path}")
    return results


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Kepler multi-dataset model evaluation",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--workers", type=int, default=8, help="Parallel fetch workers")
    parser.add_argument(
        "--quick", action="store_true",
        help="Skip volatility regime slices (faster, only universe + sector tests)",
    )
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="INFO", format="<green>{time:HH:mm:ss}</green> | {message}")

    logger.info("=" * 62)
    logger.info("  KEPLER — MULTI-DATASET EVALUATION")
    logger.info("=" * 62)
    run_evaluation(args)
