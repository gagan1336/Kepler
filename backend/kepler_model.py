"""
KEPLER — ML Live Inference Module
===================================
Loads the trained XGBoost model and provides:
  - predict_proba()     → score a pre-built feature DataFrame
  - score_symbol()      → end-to-end single-stock scoring
  - get_top_picks()     → batch feature extraction + scoring + ranking

The model and scaler are loaded once on first use and cached in memory.
If the model file doesn't exist, all functions degrade gracefully (returns None / []).
"""
import json
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger

# Must import CalibratedXGBModel so joblib can deserialise the saved pkl
# (pickle requires the class to be importable from the module it was defined in)
try:
    from ml_features import CalibratedXGBModel  # noqa: F401
except ImportError:
    pass  # ml_features not present — load_model() will catch this


# ── Paths ─────────────────────────────────────────────────────────────────────────────
_BACKEND_DIR      = Path(__file__).parent
_MODELS_DIR       = _BACKEND_DIR / "models"
MODEL_PATH        = _MODELS_DIR / "kepler_model.pkl"
SCALER_PATH       = _MODELS_DIR / "kepler_scaler.pkl"
META_PATH         = _MODELS_DIR / "kepler_meta.json"
# Meta-label model (Phase D)
META_MODEL_PATH   = _MODELS_DIR / "meta_model.pkl"
META_SCALER_PATH  = _MODELS_DIR / "meta_scaler.pkl"
META_META_PATH    = _MODELS_DIR / "meta_model_meta.json"

# ── In-memory cache ──────────────────────────────────────────────────────────────────
_model  = None
_scaler = None
_meta:   Dict = {}
_lock   = threading.Lock()
# Meta-label model
_meta_model  = None
_meta_scaler = None
_meta_info:  Dict = {}
_meta_lock   = threading.Lock()


def load_model(force_reload: bool = False) -> bool:
    """
    Load model + scaler into memory (thread-safe, singleton).
    Returns True if model is ready, False if not found.
    """
    global _model, _scaler, _meta

    with _lock:
        if _model is not None and not force_reload:
            return True

        if not MODEL_PATH.exists() or not SCALER_PATH.exists():
            logger.warning(
                f"⚠️  Kepler model not found at {MODEL_PATH}. "
                "Run `python train_model.py` to train the model first."
            )
            return False

        try:
            import joblib
            _model  = joblib.load(MODEL_PATH)
            _scaler = joblib.load(SCALER_PATH)
            if META_PATH.exists():
                with open(META_PATH) as f:
                    _meta = json.load(f)
            trained_at = _meta.get("trained_at", "unknown")
            auc = _meta.get("metrics", {}).get("val_auc", "n/a")
            logger.info(
                f"✅ Kepler model loaded | AUC={auc} | trained={trained_at}"
            )
            return True
        except Exception as e:
            logger.error(f"❌ Failed to load Kepler model: {e}")
            _model  = None
            _scaler = None
            return False


def load_meta_model(force_reload: bool = False) -> bool:
    """
    Lazily load the Phase-D meta-label model (optional, degrades gracefully).
    Returns True if meta model is available, False otherwise.
    """
    global _meta_model, _meta_scaler, _meta_info
    with _meta_lock:
        if _meta_model is not None and not force_reload:
            return True
        if not META_MODEL_PATH.exists():
            return False
        try:
            import joblib
            _meta_model  = joblib.load(META_MODEL_PATH)
            _meta_scaler = joblib.load(META_SCALER_PATH)
            if META_META_PATH.exists():
                _meta_info = json.loads(META_META_PATH.read_text())
            logger.info(
                f"✅ Meta-label model loaded | "
                f"AUC={_meta_info.get('meta_auc','n/a')} | "
                f"AP={_meta_info.get('meta_ap','n/a')}"
            )
            return True
        except Exception as e:
            logger.debug(f"Meta model load failed: {e}")
            _meta_model = None
            return False


def _meta_score(features: Dict) -> float:
    """
    Score a feature dict through the meta-label model.
    Returns a confidence float in [0,1], or 0.5 if meta model unavailable.
    """
    if _meta_model is None and not load_meta_model():
        return 0.5   # neutral — no filter applied

    from meta_label import META_FEATURE_COLS
    import pandas as pd
    row = {col: float(features.get(col, 0.0)) for col in META_FEATURE_COLS}
    row["primary_prob"] = float(features.get("_primary_prob", 0.5))
    X = pd.DataFrame([row])[META_FEATURE_COLS].fillna(0).values
    X_sc = _meta_scaler.transform(X)
    return float(_meta_model.predict_proba(X_sc)[0, 1])


def is_model_ready() -> bool:
    """Check whether the model is loaded and ready for inference."""
    return _model is not None and _scaler is not None


def get_model_info() -> Dict[str, Any]:
    """Return model metadata (AUC, training date, feature importances)."""
    if not is_model_ready() and not load_model():
        return {"status": "model_not_found", "message": "Run python train_model.py to train the model"}
    return {
        "status": "ready",
        "model_path": str(MODEL_PATH),
        "trained_at": _meta.get("trained_at"),
        "universe": _meta.get("universe"),
        "n_symbols": _meta.get("n_symbols"),
        "n_train_rows": _meta.get("n_train_rows"),
        "forward_days": _meta.get("forward_days"),
        "threshold_pct": _meta.get("threshold_pct"),
        "n_features": _meta.get("n_features"),
        "metrics": _meta.get("metrics", {}),
        "top_features": dict(
            list((_meta.get("feature_importances") or {}).items())[:10]
        ),
    }


def predict_proba(features_df: pd.DataFrame) -> np.ndarray:
    """
    Score a DataFrame of features (columns must include all FEATURE_COLUMNS).
    Returns a 1-D numpy array of buy probabilities in [0, 1].
    Caller is responsible for ensuring the model is loaded.
    """
    from ml_features import FEATURE_COLUMNS

    if not is_model_ready():
        raise RuntimeError("Model not loaded. Call load_model() first.")

    # Align columns to training feature order, fill missing with 0
    for col in FEATURE_COLUMNS:
        if col not in features_df.columns:
            features_df[col] = 0.0

    X = features_df[FEATURE_COLUMNS].fillna(0).astype(float).values
    X_scaled = _scaler.transform(X)
    proba = _model.predict_proba(X_scaled)[:, 1]
    return proba


def score_symbol(
    symbol: str,
    digest_sentiment: Dict[str, int] = None,
    apex_scores: Dict[str, float] = None,
    sector_scores: Dict[str, float] = None,
    digest_mentions: set = None,
) -> Optional[Dict[str, Any]]:
    """
    Extract features for a single symbol and return its ML score + metadata.
    Returns None if model not loaded or feature extraction fails.
    """
    if not is_model_ready() and not load_model():
        return None

    from ml_features import extract_features, FEATURE_COLUMNS

    feat = extract_features(
        symbol,
        digest_sentiment=digest_sentiment,
        apex_scores=apex_scores,
        sector_scores=sector_scores,
        digest_mentions=digest_mentions,
    )
    if feat is None:
        return None

    # Strip metadata fields before inference
    meta_keys = {k for k in feat if k.startswith("_")}
    feat_clean = {k: v for k, v in feat.items() if k not in meta_keys}

    df = pd.DataFrame([feat_clean])
    try:
        proba = predict_proba(df)[0]
    except Exception as e:
        logger.debug(f"Inference failed for {symbol}: {e}")
        return None

    buy_prob = round(float(proba), 4)
    base_rate = _meta.get("positive_rate", 0.186)

    # Meta-label score (Phase D) — how confident is the meta-filter?
    feat["_primary_prob"] = buy_prob
    meta_prob = _meta_score(feat)

    return {
        "symbol":     feat.get("_symbol", symbol.replace(".NS", "")),
        "name":       feat.get("_name", ""),
        "sector":     feat.get("_sector", ""),
        "price":      feat.get("_price", 0.0),
        "atr":        feat.get("_atr", 0.0),
        "buy_prob":   buy_prob,
        "meta_prob":  round(meta_prob, 4),
        "signal":     _classify_signal(buy_prob, base_rate),
        "features": {
            "rsi_14":        feat.get("rsi_14"),
            "macd_hist":     feat.get("macd_hist"),
            "volume_ratio":  feat.get("volume_ratio"),
            "adx_14":        feat.get("adx_14"),
            "bb_pct_b":      feat.get("bb_pct_b"),
            "pct_from_52l":  feat.get("pct_from_52l"),
            "roc_20":        feat.get("roc_20"),
        },
    }


def _classify_signal(prob: float, base_rate: float = 0.186) -> str:
    """
    Convert buy probability to a signal label, relative to the model's
    training base rate (default 18.6% for Nifty 200 10d/5% label).

    Thresholds are multiples of base_rate so signals scale correctly
    regardless of how imbalanced the training label distribution is.

      STRONG_BUY : prob >= 2.0x base_rate  (e.g. >= 0.37 @ 18.6% base)
      BUY        : prob >= 1.5x base_rate  (e.g. >= 0.28)
      WATCH      : prob >= 1.2x base_rate  (e.g. >= 0.22)
      NEUTRAL    : prob >= 1.0x base_rate  (e.g. >= 0.19)
      AVOID      : below base_rate
    """
    if prob >= base_rate * 2.0:
        return "STRONG_BUY"
    elif prob >= base_rate * 1.5:
        return "BUY"
    elif prob >= base_rate * 1.2:
        return "WATCH"
    elif prob >= base_rate * 1.0:
        return "NEUTRAL"
    else:
        return "AVOID"



def get_top_picks(
    symbols: List[str],
    n: int = 20,
    min_prob: float = 0.0,
    meta_threshold: float = 0.0,    # Phase D: set > 0 to apply meta-label filter
    digest_sentiment: Dict[str, int] = None,
    apex_scores: Dict[str, float] = None,
    sector_scores: Dict[str, float] = None,
    digest_mentions: set = None,
    max_workers: int = 8,
) -> List[Dict[str, Any]]:
    """
    Batch end-to-end pipeline: extract features → score → meta-filter → rank.
    Returns top-N picks sorted by buy_prob descending.

    Parameters
    ----------
    meta_threshold : float
        When > 0, only return stocks where meta_prob >= meta_threshold.
        Use 0.65–0.70 for higher-precision but fewer signals.
        Use 0.0 (default) to skip meta-filtering.
    """
    if not is_model_ready() and not load_model():
        logger.warning("Kepler model not available — returning empty picks")
        return []

    from concurrent.futures import ThreadPoolExecutor, as_completed
    from ml_features import extract_features_batch, features_to_df, FEATURE_COLUMNS

    logger.info(f"🔍 Kepler ML scan: scoring {len(symbols)} stocks…")
    t0 = time.time()

    # Extract all features in parallel
    feature_dicts = extract_features_batch(
        symbols=symbols,
        digest_sentiment=digest_sentiment,
        apex_scores=apex_scores,
        sector_scores=sector_scores,
        digest_mentions=digest_mentions,
        max_workers=max_workers,
    )

    if not feature_dicts:
        return []

    # Pull metadata out before inference
    meta_rows = [
        {
            "symbol":  d.get("_symbol", ""),
            "name":    d.get("_name", ""),
            "sector":  d.get("_sector", ""),
            "price":   d.get("_price", 0.0),
            "atr":     d.get("_atr", 0.0),
        }
        for d in feature_dicts
    ]

    # Build feature matrix
    df = features_to_df(feature_dicts)

    # Score
    try:
        probas = predict_proba(df)
    except Exception as e:
        logger.error(f"Batch inference failed: {e}")
        return []

    # Assemble results
    results = []
    load_meta_model()   # warm meta model (no-op if unavailable)
    for i, (meta_row, prob) in enumerate(zip(meta_rows, probas)):
        if prob < min_prob:
            continue
        fd = feature_dicts[i]
        fd["_primary_prob"] = float(prob)
        meta_prob = _meta_score(fd)
        if meta_threshold > 0 and meta_prob < meta_threshold:
            continue
        results.append({
            **meta_row,
            "buy_prob":    round(float(prob), 4),
            "meta_prob":   round(meta_prob, 4),
            "signal":      _classify_signal(prob),
            "rsi_14":      round(fd.get("rsi_14", 0), 1),
            "macd_hist":   round(fd.get("macd_hist", 0), 4),
            "volume_ratio": round(fd.get("volume_ratio", 1), 2),
            "adx_14":      round(fd.get("adx_14", 0), 1),
            "bb_pct_b":    round(fd.get("bb_pct_b", 0), 3),
            "pct_from_52l": round(fd.get("pct_from_52l", 0), 1),
            "roc_20":      round(fd.get("roc_20", 0), 2),
            "apex_score":  round(fd.get("apex_score", 50), 1),
            "news_sentiment": int(fd.get("news_sentiment", 0)),
        })

    results.sort(key=lambda x: -x["buy_prob"])
    top = results[:n]

    elapsed = time.time() - t0
    logger.info(
        f"✅ Kepler ML scan complete: {len(top)} picks "
        f"(min_prob={min_prob}) in {elapsed:.1f}s"
    )
    return top


# ── Auto-load on import (non-blocking) ───────────────────────────────────────
def _bg_load():
    load_model()

threading.Thread(target=_bg_load, daemon=True, name="KeplerModelLoader").start()
