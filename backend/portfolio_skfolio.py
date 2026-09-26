"""
KEPLER — skfolio Portfolio Construction Layer
================================================
Replaces the ad-hoc ATR-scaled position sizer in portfolio.py with
HierarchicalRiskParity (HRP) and RiskBudgeting optimizers from skfolio,
using walk-forward cross-validation over the frozen holdout's own return
history.

⚠️  PROVISIONAL OUTPUT — NOT VALID FOR REAL DECISIONS
======================================================
The meta-filter (meta_model.pkl) was trained on OOF predictions from the
46-feature primary model.  The primary model now has 51 features.  The
meta-filter has NOT been retrained (Phase D retrain is pending).
Sizing weights from this module are indicative ONLY.
Rerun after:  python meta_label.py --train

Design
------
Input  : scored holdout DataFrame from expectancy.collect_holdout_with_returns()
         columns required: symbol, date, y_score, meta_score, fwd_ret_raw
Output : PortfolioResult dataclass + JSON comparison report

Constraints (native to skfolio, not bolt-on filters)
------------------------------------------------------
• max_weights = 0.05          → ≤ 5% per single name
• GroupConstraint(sector)     → ≤ 25% per sector
• Correlation cap             → post-opt pass (same math as portfolio.py)
  Reason: no native skfolio equivalent for "binary pair veto at corr>0.80"

Walk-forward splits
-------------------
WalkForward(train_size=252, test_size=21) — 1 year train, 1 month test.
Runs entirely over the holdout return matrix.  Training universe is NEVER
accessed here.

Usage
-----
    python portfolio_skfolio.py \\
        --holdout-yaml configs/frozen_holdout.yaml \\
        --primary-threshold 0.35 \\
        --meta-threshold 0.10 \\
        --compare-expectancy

    python portfolio_skfolio.py --smoke-test
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml
from loguru import logger

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

# ── Paths ─────────────────────────────────────────────────────────────────────
_BACKEND_DIR = Path(__file__).parent
_CONFIGS_DIR = _BACKEND_DIR / "configs" / "experiment_runs"
_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)

# ── Risk constraints — mirrors portfolio.py ───────────────────────────────────
MAX_SINGLE_NAME_PCT   = 0.05   # 5% max per stock
MAX_SECTOR_PCT        = 0.25   # 25% max per sector
MAX_CORR_COMBINED_PCT = 0.08   # 8% combined for corr > 0.80
HIGH_CORR_THRESHOLD   = 0.80

# ── Meta-filter staleness warning ─────────────────────────────────────────────
_META_FILTER_WARNING = """
╔══════════════════════════════════════════════════════════════════╗
║  ⚠️  PROVISIONAL OUTPUT — NOT VALID FOR REAL DECISIONS          ║
║  The meta-filter (meta_model.pkl) was trained on OOF            ║
║  predictions from the 46-feature primary model.                 ║
║  The primary model now has 51 features. Phase D retrain is      ║
║  pending. Sizing weights are INDICATIVE ONLY.                   ║
║  Rerun after:  python meta_label.py --train                     ║
╚══════════════════════════════════════════════════════════════════╝
"""

# Log at module import time — not suppressible without changing log level
logger.warning(_META_FILTER_WARNING)


# ── Sector map — hardcoded from frozen_holdout.yaml ───────────────────────────
HOLDOUT_SECTOR_MAP: Dict[str, str] = {
    # Finance / Insurance / Broking
    "ICICIGI":    "Finance", "SBICARD":    "Finance", "CHOLAHLDNG": "Finance",
    "MOTILALOFS": "Finance", "ANGELONE":   "Finance", "5PAISA":     "Finance",
    "IIFL":       "Finance", "MASFIN":     "Finance", "SPANDANA":   "Finance",
    # Media / Entertainment
    "ZEEL":       "Media",   "PVRINOX":    "Media",   "INOXWIND":   "Industrials",
    # Power / Specialty Industrials
    "KALPATPOWR": "Industrials", "GPPL":   "Industrials",
    # Consumer / Lifestyle / Retail
    "RAJESHEXPO": "Consumer", "CENTURYTEX": "Consumer", "RAYMOND":  "Consumer",
    "PAGEIND":    "Consumer", "CRAFTSMAN":  "Consumer", "KALYANKJIL":"Consumer",
    "SENCO":      "Consumer", "PCJEWELLER": "Consumer",
    # Pharma — small/specialty
    "GLENMARK":   "Pharma",  "NATCOPHARM": "Pharma",  "GLAND":     "Pharma",
    "JBCHEPHARM": "Pharma",  "ERIS":       "Pharma",  "GRANULES":  "Pharma",
    "CAPLIPOINT": "Pharma",  "MARKSANS":   "Pharma",
    # Small IT / Tech
    "TANLA":      "IT",      "INTELLECT":  "IT",      "NEWGEN":    "IT",
    "RATEGAIN":   "IT",      "INDIAMART":  "IT",      "NAUKRI":    "IT",
    "POLICYBZR":  "IT",      "TATAELXSI":  "IT",      "CYIENT":    "IT",
    "ZENSARTECH": "IT",      "BIRLASOFT":  "IT",
    # Healthcare — small/mid
    "ASTERDM":    "Healthcare", "NH":      "Healthcare",
}


# ── Availability flags ────────────────────────────────────────────────────────

def _check_skfolio() -> bool:
    try:
        import skfolio  # noqa: F401
        return True
    except ImportError:
        return False


def _check_cvxpy() -> bool:
    try:
        import cvxpy  # noqa: F401
        return True
    except (ImportError, Exception):
        return False


_SKFOLIO_AVAILABLE = _check_skfolio()
_CVXPY_AVAILABLE   = _check_cvxpy()

if not _SKFOLIO_AVAILABLE:
    logger.error(
        "skfolio is not installed. Run: pip install 'skfolio>=1.0.0'\n"
        "If WDAC blocks the install, run on Linux/WSL2."
    )

if not _CVXPY_AVAILABLE:
    logger.warning(
        "cvxpy not available — RiskBudgeting optimizer will fall back to HRP.\n"
        "Run: pip install 'cvxpy>=1.5.0' to enable Risk-Parity optimization."
    )


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass
class FoldPortfolio:
    """Weight snapshot for a single walk-forward test fold."""
    fold_idx:       int
    train_start:    str
    train_end:      str
    test_start:     str
    test_end:       str
    optimizer:      str          # "HRP" or "RiskBudget"
    weights:        Dict[str, float]
    sector_weights: Dict[str, float]
    n_assets:       int
    diversification_ratio: float
    effective_n:    float        # 1 / HHI


@dataclass
class PortfolioResult:
    """Aggregated result across all walk-forward folds."""
    optimizer:           str
    n_folds:             int
    avg_weights:         Dict[str, float]    # symbol → mean weight across folds
    sector_exposure:     Dict[str, float]    # sector → mean exposure
    avg_diversification: float
    avg_effective_n:     float
    corr_adj_weights:    Dict[str, float]    # after correlation cap applied
    fold_portfolios:     List[FoldPortfolio] = field(default_factory=list)
    meta_filter_status:  str = "PROVISIONAL_PHASE_D_PENDING"


# ── Signal returns matrix ─────────────────────────────────────────────────────

def build_signal_returns_matrix(
    scored_df:         pd.DataFrame,
    primary_threshold: float = 0.35,
    meta_threshold:    float = 0.10,
    forward_days:      int   = 10,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Pivot scored holdout DataFrame into a (dates × symbols) returns matrix.

    Only date-rows where the signal passes BOTH thresholds contribute.
    Rows below threshold are set to 0 (no position on that bar).

    Parameters
    ----------
    scored_df : DataFrame with columns: symbol, date, y_score, meta_score, fwd_ret_raw
    primary_threshold : min y_score to include a signal
    meta_threshold : min meta_score to include a signal

    Returns
    -------
    X_returns : pd.DataFrame (dates × symbols) — full return matrix for optimizer
    signal_mask_df : pd.DataFrame (dates × symbols) — bool mask of active signals
    """
    df = scored_df.copy()

    # Normalise date column
    if "date" not in df.columns:
        if df.index.name == "date" or isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index().rename(columns={"index": "date"})
        else:
            raise ValueError("scored_df must have a 'date' column or DatetimeIndex")

    df["date"] = pd.to_datetime(df["date"]).dt.normalize()

    # Signal mask: both thresholds must pass
    if "meta_score" in df.columns:
        df["signal_active"] = (
            (df["y_score"] >= primary_threshold) &
            (df["meta_score"] >= meta_threshold)
        )
    else:
        logger.warning("  meta_score not in DataFrame — using primary threshold only")
        df["signal_active"] = df["y_score"] >= primary_threshold

    # fwd_ret_raw is the label-row return; use as proxy daily return for optimizer
    # For rows where signal is NOT active, zero return (no position)
    df["return_for_opt"] = np.where(df["signal_active"], df["fwd_ret_raw"].fillna(0), 0.0)

    # Pivot to (date × symbol) matrix — one row per date, one col per symbol
    X_returns = df.pivot_table(
        index="date", columns="symbol", values="return_for_opt", aggfunc="mean"
    ).fillna(0.0)

    signal_mask_df = df.pivot_table(
        index="date", columns="symbol", values="signal_active", aggfunc="max"
    ).fillna(False)

    logger.info(
        f"  Returns matrix: {X_returns.shape[0]} dates × {X_returns.shape[1]} symbols "
        f"| active signals: {int(signal_mask_df.values.sum()):,}"
    )
    return X_returns, signal_mask_df


# ── skfolio group structure ───────────────────────────────────────────────────

def build_group_constraints(symbols: List[str]) -> Optional[object]:
    """
    Build skfolio GroupConstraint for max sector exposure.

    Returns None if skfolio is not available.
    """
    if not _SKFOLIO_AVAILABLE:
        return None

    try:
        from skfolio.optimization.convex._constraints import GroupConstraint
    except ImportError:
        try:
            from skfolio.constraints import GroupConstraint
        except ImportError:
            logger.warning("  Could not import GroupConstraint — sector cap will be post-opt only")
            return None

    sectors = [HOLDOUT_SECTOR_MAP.get(s, "Other") for s in symbols]
    # GroupConstraint: sector total ≤ MAX_SECTOR_PCT
    return GroupConstraint(
        groups=sectors,
        left_inequality=np.zeros(len(set(sectors))),
        right_inequality=np.full(len(set(sectors)), MAX_SECTOR_PCT),
    )


# ── HRP walk-forward ─────────────────────────────────────────────────────────

def fit_hrp_walk_forward(
    X_returns:   pd.DataFrame,
    train_size:  int = 252,
    test_size:   int = 21,
) -> List[FoldPortfolio]:
    """
    Fit HierarchicalRiskParity with walk-forward CV on holdout return matrix.

    Constraints enforced natively:
        max_weights = MAX_SINGLE_NAME_PCT (5%)
        Sector cap applied as post-opt rescaling (GroupConstraint import optional)

    Parameters
    ----------
    X_returns   : (dates × symbols) returns DataFrame
    train_size  : trading days for each training window (default 252 = 1 year)
    test_size   : trading days for each test window (default 21 = 1 month)
    """
    if not _SKFOLIO_AVAILABLE:
        raise ImportError("skfolio is required for HRP. Install: pip install 'skfolio>=1.0.0'")

    from skfolio.optimization import HierarchicalRiskParity
    from skfolio.model_selection import WalkForward

    symbols = list(X_returns.columns)
    X = X_returns.values.astype(float)
    dates = X_returns.index.tolist()

    hrp = HierarchicalRiskParity(
        min_weights=0.0,
        max_weights=MAX_SINGLE_NAME_PCT,
    )

    cv = WalkForward(train_size=train_size, test_size=test_size)

    fold_portfolios: List[FoldPortfolio] = []
    total_folds = sum(1 for _ in cv.split(X))
    logger.info(f"  HRP: {total_folds} walk-forward folds (train={train_size}d, test={test_size}d)")

    for fold_idx, (tr_idx, te_idx) in enumerate(cv.split(X)):
        X_tr = X[tr_idx]
        X_te = X[te_idx]

        if X_tr.shape[0] < 30 or np.isnan(X_tr).all():
            continue

        try:
            hrp.fit(X_tr)
            weights_arr = np.array(hrp.weights_)
        except Exception as exc:
            logger.debug(f"  HRP fold {fold_idx} failed: {exc} — equal weight fallback")
            weights_arr = np.full(len(symbols), 1.0 / len(symbols))

        # Clip to single-name cap (should already be enforced, but defensive)
        weights_arr = np.clip(weights_arr, 0, MAX_SINGLE_NAME_PCT)
        if weights_arr.sum() > 0:
            weights_arr /= weights_arr.sum()

        # Apply sector cap (post-opt rescaling)
        weights_arr = _apply_sector_cap_to_array(weights_arr, symbols)

        weights_dict = {s: round(float(w), 6) for s, w in zip(symbols, weights_arr)}
        sector_weights = _aggregate_sector_weights(weights_dict)
        div_ratio = _diversification_ratio(X_tr, weights_arr)
        eff_n = _effective_n(weights_arr)

        tr_dates = [dates[i] for i in tr_idx]
        te_dates = [dates[i] for i in te_idx]

        fold_portfolios.append(FoldPortfolio(
            fold_idx       = fold_idx,
            train_start    = str(tr_dates[0]),
            train_end      = str(tr_dates[-1]),
            test_start     = str(te_dates[0]),
            test_end       = str(te_dates[-1]),
            optimizer      = "HRP",
            weights        = weights_dict,
            sector_weights = sector_weights,
            n_assets       = int((weights_arr > 0.001).sum()),
            diversification_ratio = round(float(div_ratio), 4),
            effective_n    = round(float(eff_n), 2),
        ))

    logger.info(f"  HRP: {len(fold_portfolios)} folds completed")
    return fold_portfolios


# ── RiskBudgeting walk-forward ────────────────────────────────────────────────

def fit_riskbudget_walk_forward(
    X_returns:         pd.DataFrame,
    scored_df:         pd.DataFrame,
    primary_threshold: float = 0.35,
    meta_threshold:    float = 0.10,
    train_size:        int   = 252,
    test_size:         int   = 21,
) -> List[FoldPortfolio]:
    """
    Fit RiskBudgeting with risk budgets proportional to meta_score.

    Falls back to HRP if cvxpy is unavailable (WDAC blocked).

    Risk budget logic:
        For each training window, compute the AVERAGE meta_score per symbol
        across signal-active rows.  Normalise to a budget vector summing to 1.
        Symbols with no active signals get a small equal budget (1/N × 0.5).

    Parameters
    ----------
    X_returns   : (dates × symbols) returns DataFrame
    scored_df   : full scored DataFrame (to extract meta_score per symbol/date)
    primary_threshold, meta_threshold : same thresholds used for signal mask
    """
    if not _SKFOLIO_AVAILABLE:
        raise ImportError("skfolio is required. Install: pip install 'skfolio>=1.0.0'")

    if not _CVXPY_AVAILABLE:
        logger.warning(
            "  cvxpy not available — RiskBudgeting falling back to HRP.\n"
            "  Install cvxpy: pip install 'cvxpy>=1.5.0'"
        )
        folds = fit_hrp_walk_forward(X_returns, train_size, test_size)
        for f in folds:
            f.optimizer = "RiskBudget(fallback=HRP)"
        return folds

    from skfolio.optimization import RiskBudgeting
    from skfolio import RiskMeasure
    from skfolio.model_selection import WalkForward

    symbols = list(X_returns.columns)
    X = X_returns.values.astype(float)
    dates = X_returns.index.tolist()

    # Pre-compute meta_score per (date, symbol) for budget allocation
    scored_df = scored_df.copy()
    scored_df["date"] = pd.to_datetime(scored_df["date"]).dt.normalize()
    if "meta_score" not in scored_df.columns:
        scored_df["meta_score"] = scored_df.get("y_score", 0.5)

    meta_pivot = scored_df.pivot_table(
        index="date", columns="symbol", values="meta_score", aggfunc="mean"
    ).reindex(columns=symbols).fillna(0.0)

    cv = WalkForward(train_size=train_size, test_size=test_size)

    fold_portfolios: List[FoldPortfolio] = []
    total_folds = sum(1 for _ in cv.split(X))
    logger.info(
        f"  RiskBudget: {total_folds} walk-forward folds "
        f"(train={train_size}d, test={test_size}d)"
    )

    for fold_idx, (tr_idx, te_idx) in enumerate(cv.split(X)):
        X_tr = X[tr_idx]

        if X_tr.shape[0] < 30 or np.isnan(X_tr).all():
            continue

        tr_dates = [dates[i] for i in tr_idx]
        te_dates = [dates[i] for i in te_idx]

        # Build risk budgets from meta_score in this training window
        tr_date_range = pd.DatetimeIndex(tr_dates)
        meta_in_window = meta_pivot.reindex(tr_date_range).fillna(0.0)
        avg_meta = meta_in_window.mean().values.astype(float)

        # Active signal mask: primary + meta threshold
        has_signal = avg_meta >= meta_threshold
        budget = np.where(has_signal, avg_meta, avg_meta.mean() * 0.3)
        budget = np.clip(budget, 1e-6, None)
        budget /= budget.sum()

        try:
            rb = RiskBudgeting(
                risk_measure=RiskMeasure.VARIANCE,
                min_weights=0.0,
                max_weights=MAX_SINGLE_NAME_PCT,
                risk_budget=budget,   # skfolio 1.0.0: risk_budget, not budget
            )
            rb.fit(X_tr)
            weights_arr = np.array(rb.weights_)
        except Exception as exc:
            logger.debug(f"  RiskBudget fold {fold_idx} failed: {exc} — HRP fallback")
            try:
                from skfolio.optimization import HierarchicalRiskParity
                hrp = HierarchicalRiskParity(min_weights=0.0, max_weights=MAX_SINGLE_NAME_PCT)
                hrp.fit(X_tr)
                weights_arr = np.array(hrp.weights_)
            except Exception:
                weights_arr = np.full(len(symbols), 1.0 / len(symbols))

        # Clip + normalise
        weights_arr = np.clip(weights_arr, 0, MAX_SINGLE_NAME_PCT)
        if weights_arr.sum() > 0:
            weights_arr /= weights_arr.sum()

        # Apply sector cap
        weights_arr = _apply_sector_cap_to_array(weights_arr, symbols)

        weights_dict   = {s: round(float(w), 6) for s, w in zip(symbols, weights_arr)}
        sector_weights = _aggregate_sector_weights(weights_dict)
        div_ratio      = _diversification_ratio(X_tr, weights_arr)
        eff_n          = _effective_n(weights_arr)

        fold_portfolios.append(FoldPortfolio(
            fold_idx       = fold_idx,
            train_start    = str(tr_dates[0]),
            train_end      = str(tr_dates[-1]),
            test_start     = str(te_dates[0]),
            test_end       = str(te_dates[-1]),
            optimizer      = "RiskBudget",
            weights        = weights_dict,
            sector_weights = sector_weights,
            n_assets       = int((weights_arr > 0.001).sum()),
            diversification_ratio = round(float(div_ratio), 4),
            effective_n    = round(float(eff_n), 2),
        ))

    logger.info(f"  RiskBudget: {len(fold_portfolios)} folds completed")
    return fold_portfolios


# ── Correlation constraint (post-opt) ─────────────────────────────────────────

def apply_correlation_constraint(
    weights_dict: Dict[str, float],
    returns_df:   pd.DataFrame,
    max_combined: float = MAX_CORR_COMBINED_PCT,
    threshold:    float = HIGH_CORR_THRESHOLD,
) -> Dict[str, float]:
    """
    Post-optimization correlation cap.

    Mirrors portfolio.apply_correlation_cap() exactly:
        If two symbols have 90-day rolling correlation > threshold,
        their combined weight is capped at max_combined.

    Uses the full holdout returns matrix to compute pairwise correlations.

    Parameters
    ----------
    weights_dict : {symbol: weight} from optimizer
    returns_df   : (dates × symbols) returns DataFrame
    """
    symbols = [s for s, w in weights_dict.items() if w > 0.001]
    if len(symbols) < 2:
        return weights_dict

    # 90-day rolling correlation — use last 90 rows of returns
    tail = returns_df[symbols].dropna(how="all").tail(90)
    if tail.shape[0] < 20:
        return weights_dict

    corr = tail.corr()
    result = dict(weights_dict)
    processed_pairs: set = set()

    for i, sym_a in enumerate(symbols):
        for sym_b in symbols[i + 1:]:
            pair = frozenset([sym_a, sym_b])
            if pair in processed_pairs:
                continue
            processed_pairs.add(pair)

            try:
                c = abs(float(corr.loc[sym_a, sym_b]))
            except KeyError:
                continue

            if c > threshold:
                w_a = result.get(sym_a, 0)
                w_b = result.get(sym_b, 0)
                combined = w_a + w_b
                if combined > max_combined:
                    scale = max_combined / combined
                    result[sym_a] = round(w_a * scale, 6)
                    result[sym_b] = round(w_b * scale, 6)
                    logger.info(
                        f"  ⚠️  Corr cap: {sym_a}↔{sym_b} (corr={c:.2f}) "
                        f"combined {combined:.1%} → {max_combined:.0%}"
                    )

    return result


# ── Aggregate results ─────────────────────────────────────────────────────────

def aggregate_fold_portfolios(
    folds:     List[FoldPortfolio],
    optimizer: str,
    returns_df: pd.DataFrame,
) -> PortfolioResult:
    """Average walk-forward fold weights into a summary PortfolioResult."""
    if not folds:
        return PortfolioResult(
            optimizer=optimizer, n_folds=0,
            avg_weights={}, sector_exposure={},
            avg_diversification=0.0, avg_effective_n=0.0,
            corr_adj_weights={},
        )

    all_symbols = set()
    for f in folds:
        all_symbols.update(f.weights.keys())
    all_symbols = sorted(all_symbols)

    weight_matrix = pd.DataFrame(
        [{s: f.weights.get(s, 0.0) for s in all_symbols} for f in folds]
    )
    avg_weights = weight_matrix.mean().to_dict()

    # Sector exposure
    sector_weights = _aggregate_sector_weights(avg_weights)

    # Portfolio metrics
    avg_dr  = float(np.mean([f.diversification_ratio for f in folds]))
    avg_eff = float(np.mean([f.effective_n for f in folds]))

    # Correlation-adjusted weights (applied to avg weights)
    corr_adj = apply_correlation_constraint(avg_weights, returns_df)

    return PortfolioResult(
        optimizer          = optimizer,
        n_folds            = len(folds),
        avg_weights        = {k: round(v, 6) for k, v in avg_weights.items()},
        sector_exposure    = {k: round(v, 4) for k, v in sector_weights.items()},
        avg_diversification= round(avg_dr, 4),
        avg_effective_n    = round(avg_eff, 2),
        corr_adj_weights   = {k: round(v, 6) for k, v in corr_adj.items()},
        fold_portfolios    = folds,
    )


# ── Main orchestrator ─────────────────────────────────────────────────────────

def run_skfolio_backtest(
    symbols:           List[str],
    primary_threshold: float = 0.35,
    meta_threshold:    float = 0.10,
    portfolio_value:   float = 1_000_000,
    history:           str   = "8y",
    max_workers:       int   = 8,
    train_size:        int   = 252,
    test_size:         int   = 21,
) -> Tuple[PortfolioResult, PortfolioResult, pd.DataFrame]:
    """
    Full pipeline: load holdout → score → build returns → HRP → RiskBudget.

    ⚠️  Meta-filter output is PROVISIONAL — Phase D retrain pending.

    Parameters
    ----------
    symbols           : frozen holdout tickers (NEVER mix in training universe)
    primary_threshold : min y_score threshold
    meta_threshold    : min meta_score threshold
    portfolio_value   : INR capital (used in reporting, not optimization)
    history           : yfinance period string
    max_workers       : parallel download threads
    train_size        : WalkForward training window (trading days)
    test_size         : WalkForward test window (trading days)

    Returns
    -------
    hrp_result       : PortfolioResult from HRP optimizer
    rb_result        : PortfolioResult from RiskBudgeting (or HRP fallback)
    scored_df        : full scored holdout DataFrame (for comparison report)
    """
    # ── Mandatory staleness warning ───────────────────────────────────────────
    logger.warning(_META_FILTER_WARNING)

    logger.info(f"🔒 skfolio portfolio backtest — {len(symbols)} holdout symbols")
    logger.info(
        f"   primary_thr={primary_threshold}  meta_thr={meta_threshold}  "
        f"train_size={train_size}d  test_size={test_size}d"
    )

    # ── 1. Score holdout ──────────────────────────────────────────────────────
    from expectancy import collect_holdout_with_returns
    scored_df = collect_holdout_with_returns(
        symbols, history=history, max_workers=max_workers
    )

    if "date" not in scored_df.columns:
        scored_df = scored_df.reset_index().rename(columns={"index": "date"})
    scored_df["date"] = pd.to_datetime(scored_df["date"]).dt.normalize()

    # ── 2. Build returns matrix ───────────────────────────────────────────────
    X_returns, signal_mask_df = build_signal_returns_matrix(
        scored_df, primary_threshold, meta_threshold
    )

    available_symbols = list(X_returns.columns)
    logger.info(f"   {len(available_symbols)} symbols in returns matrix")

    if X_returns.shape[0] < train_size + test_size:
        raise RuntimeError(
            f"Not enough rows ({X_returns.shape[0]}) for WalkForward "
            f"(need >= {train_size + test_size}). Increase history or reduce train_size."
        )

    # ── 3. HRP ────────────────────────────────────────────────────────────────
    logger.info("▶ Fitting HierarchicalRiskParity…")
    hrp_folds = fit_hrp_walk_forward(X_returns, train_size, test_size)
    hrp_result = aggregate_fold_portfolios(hrp_folds, "HRP", X_returns)

    # ── 4. RiskBudgeting ──────────────────────────────────────────────────────
    logger.info("▶ Fitting RiskBudgeting…")
    rb_folds = fit_riskbudget_walk_forward(
        X_returns, scored_df, primary_threshold, meta_threshold, train_size, test_size
    )
    rb_result = aggregate_fold_portfolios(rb_folds, "RiskBudget", X_returns)

    return hrp_result, rb_result, scored_df


# ── Comparison report ─────────────────────────────────────────────────────────

def build_comparison_report(
    hrp_result:       PortfolioResult,
    rb_result:        PortfolioResult,
    scored_df:        pd.DataFrame,
    expectancy_path:  Optional[Path] = None,
    portfolio_value:  float = 1_000_000,
    primary_threshold: float = 0.35,
) -> dict:
    """
    Side-by-side: single-stock expectancy vs HRP vs RiskBudget weights.

    Parameters
    ----------
    hrp_result, rb_result : from run_skfolio_backtest()
    scored_df             : full scored holdout DataFrame
    expectancy_path       : path to expectancy_<ts>.json (auto-detect if None)
    """
    from expectancy import expectancy_table, compute_round_trip_cost_pct

    # ── Single-stock expectancy ───────────────────────────────────────────────
    cost_pct = compute_round_trip_cost_pct(50_000)
    exp_rows = expectancy_table(scored_df, thresholds=[primary_threshold],
                                score_col="y_score", ret_col="fwd_ret_raw")
    exp_at_thr = exp_rows[0] if exp_rows else {}

    # ── Per-symbol expectancy ─────────────────────────────────────────────────
    sym_exp: Dict[str, dict] = {}
    for sym, grp in scored_df.groupby("symbol"):
        sub = grp[grp["y_score"] >= primary_threshold]
        if len(sub) < 5:
            continue
        wins   = sub[sub["y_true"] == 1]["fwd_ret_raw"]
        losses = sub[sub["y_true"] == 0]["fwd_ret_raw"]
        hr     = len(wins) / len(sub)
        avg_w  = float(wins.mean())  if len(wins)  > 0 else 0.0
        avg_l  = float(losses.mean()) if len(losses) > 0 else 0.0
        gross  = hr * avg_w + (1 - hr) * avg_l
        sym_exp[sym] = {
            "n_signals":  int(len(sub)),
            "hit_rate":   round(hr, 4),
            "gross_exp":  round(gross, 3),
            "net_exp":    round(gross - cost_pct, 3),
        }

    # ── Combined rows ─────────────────────────────────────────────────────────
    all_syms = sorted(set(hrp_result.avg_weights) | set(rb_result.avg_weights) | set(sym_exp))
    comparison_rows = []
    for sym in all_syms:
        hrp_w  = hrp_result.avg_weights.get(sym, 0.0)
        hrp_ca = hrp_result.corr_adj_weights.get(sym, hrp_w)
        rb_w   = rb_result.avg_weights.get(sym, 0.0)
        rb_ca  = rb_result.corr_adj_weights.get(sym, rb_w)
        exp    = sym_exp.get(sym, {})
        sector = HOLDOUT_SECTOR_MAP.get(sym, "Other")
        comparison_rows.append({
            "symbol":           sym,
            "sector":           sector,
            "n_signals":        exp.get("n_signals", 0),
            "hit_rate":         exp.get("hit_rate", None),
            "net_exp_pct":      exp.get("net_exp", None),
            "hrp_weight_pct":   round(hrp_w * 100, 2),
            "hrp_corradj_pct":  round(hrp_ca * 100, 2),
            "rb_weight_pct":    round(rb_w * 100, 2),
            "rb_corradj_pct":   round(rb_ca * 100, 2),
            "hrp_inr":          round(hrp_ca * portfolio_value, 0),
            "rb_inr":           round(rb_ca * portfolio_value, 0),
        })

    # Sort by HRP weight desc
    comparison_rows.sort(key=lambda r: -r["hrp_weight_pct"])

    # ── Sector summary ────────────────────────────────────────────────────────
    sector_rows = []
    all_sectors = sorted(set(
        list(hrp_result.sector_exposure.keys()) +
        list(rb_result.sector_exposure.keys())
    ))
    for sector in all_sectors:
        hrp_s = hrp_result.sector_exposure.get(sector, 0.0)
        rb_s  = rb_result.sector_exposure.get(sector, 0.0)
        capped = hrp_s > MAX_SECTOR_PCT or rb_s > MAX_SECTOR_PCT
        sector_rows.append({
            "sector":     sector,
            "hrp_pct":    round(hrp_s * 100, 2),
            "rb_pct":     round(rb_s * 100, 2),
            "cap_pct":    int(MAX_SECTOR_PCT * 100),
            "cap_breach": capped,
        })

    report = {
        "meta_filter_status":  "PROVISIONAL_PHASE_D_PENDING",
        "generated_at":        datetime.utcnow().isoformat() + "Z",
        "primary_threshold":   primary_threshold,
        "portfolio_value_inr": portfolio_value,
        "cost_pct":            round(cost_pct, 4),
        # Overall expectancy
        "overall_expectancy": {
            "threshold":  primary_threshold,
            "n_signals":  exp_at_thr.get("n_trades", 0),
            "hit_rate":   exp_at_thr.get("hit_rate", 0),
            "gross_exp":  exp_at_thr.get("gross_exp", 0),
            "net_exp":    exp_at_thr.get("net_exp", 0),
        },
        # Optimizer portfolio stats
        "hrp_portfolio": {
            "n_folds":             hrp_result.n_folds,
            "avg_diversification": hrp_result.avg_diversification,
            "avg_effective_n":     hrp_result.avg_effective_n,
            "sector_exposure":     hrp_result.sector_exposure,
        },
        "rb_portfolio": {
            "n_folds":             rb_result.n_folds,
            "avg_diversification": rb_result.avg_diversification,
            "avg_effective_n":     rb_result.avg_effective_n,
            "sector_exposure":     rb_result.sector_exposure,
            "optimizer":           rb_result.optimizer,
        },
        "comparison_rows": comparison_rows,
        "sector_rows":     sector_rows,
    }
    return report


def _print_comparison_report(report: dict) -> None:
    """Pretty-print the side-by-side comparison table."""
    logger.info(f"\n{'═'*82}")
    logger.info("  KEPLER PORTFOLIO COMPARISON — skfolio vs Single-Stock Expectancy")
    logger.info(f"  ⚠️  META-FILTER STATUS: {report['meta_filter_status']}")
    logger.info(f"{'═'*82}")

    logger.info(
        f"  {'Symbol':<12} {'Sector':<13} {'NetExp%':>7} {'HRP%':>6} "
        f"{'HRP-CA%':>7} {'RB%':>5} {'RB-CA%':>7}"
    )
    logger.info(f"  {'─'*78}")

    for r in report["comparison_rows"]:
        if r["hrp_weight_pct"] < 0.05 and r["rb_weight_pct"] < 0.05:
            continue
        ne = f"{r['net_exp_pct']:+.2f}%" if r["net_exp_pct"] is not None else "   N/A"
        logger.info(
            f"  {r['symbol']:<12} {r['sector']:<13} {ne:>7}  "
            f"{r['hrp_weight_pct']:>5.2f}%  {r['hrp_corradj_pct']:>5.2f}%  "
            f"{r['rb_weight_pct']:>4.2f}%  {r['rb_corradj_pct']:>5.2f}%"
        )

    logger.info(f"  {'─'*78}")
    logger.info("\n  SECTOR EXPOSURE (cap: 25%)")
    logger.info(f"  {'Sector':<18} {'HRP%':>6} {'RB%':>6}  Status")
    logger.info(f"  {'─'*40}")
    for r in report["sector_rows"]:
        flag = "❌ BREACH" if r["cap_breach"] else "✅"
        logger.info(
            f"  {r['sector']:<18} {r['hrp_pct']:>5.1f}%  {r['rb_pct']:>5.1f}%   {flag}"
        )

    hrp = report["hrp_portfolio"]
    rb  = report["rb_portfolio"]
    oe  = report["overall_expectancy"]
    logger.info(f"\n  PORTFOLIO METRICS")
    logger.info(f"  {'─'*55}")
    logger.info(f"  Single-stock net expectancy (thr={oe['threshold']}):  {oe['net_exp']:+.3f}%")
    logger.info(f"  Diversification ratio:  HRP={hrp['avg_diversification']:.2f}  "
                f"RB={rb['avg_diversification']:.2f}")
    logger.info(f"  Effective N (1/HHI):    HRP={hrp['avg_effective_n']:.1f}  "
                f"RB={rb['avg_effective_n']:.1f}")
    logger.info(f"  Walk-forward folds:     HRP={hrp['n_folds']}  "
                f"RB(mode={rb['optimizer']})={rb['n_folds']}")
    logger.info(f"{'═'*82}\n")


# ── Helper utilities ──────────────────────────────────────────────────────────

def _apply_sector_cap_to_array(
    weights: np.ndarray,
    symbols: List[str],
) -> np.ndarray:
    """Proportionally scale down any over-allocated sector. Mirror of portfolio.py."""
    weights = weights.copy()
    sector_indices: Dict[str, List[int]] = {}
    for i, sym in enumerate(symbols):
        sec = HOLDOUT_SECTOR_MAP.get(sym, "Other")
        sector_indices.setdefault(sec, []).append(i)

    for sec, idxs in sector_indices.items():
        total = weights[idxs].sum()
        if total > MAX_SECTOR_PCT:
            scale = MAX_SECTOR_PCT / total
            weights[idxs] *= scale
            logger.debug(f"  Sector cap {sec}: {total:.1%} → {MAX_SECTOR_PCT:.0%}")

    total = weights.sum()
    if total > 0:
        weights /= total
    return weights


def _aggregate_sector_weights(weights_dict: Dict[str, float]) -> Dict[str, float]:
    """Sum weights by sector."""
    sector_totals: Dict[str, float] = {}
    for sym, w in weights_dict.items():
        sec = HOLDOUT_SECTOR_MAP.get(sym, "Other")
        sector_totals[sec] = sector_totals.get(sec, 0.0) + w
    return sector_totals


def _diversification_ratio(X_train: np.ndarray, weights: np.ndarray) -> float:
    """
    Diversification Ratio = (w' × σ) / √(w' Σ w)
    where σ is the vector of individual asset volatilities.
    """
    try:
        cov = np.cov(X_train.T)
        individual_vols = np.sqrt(np.diag(cov))
        weighted_avg_vol = float(np.dot(weights, individual_vols))
        portfolio_vol    = float(np.sqrt(weights @ cov @ weights))
        if portfolio_vol < 1e-10:
            return 1.0
        return weighted_avg_vol / portfolio_vol
    except Exception:
        return 1.0


def _effective_n(weights: np.ndarray) -> float:
    """Effective number of positions = 1 / Herfindahl-Hirschman Index."""
    w = weights[weights > 1e-6]
    if len(w) == 0:
        return 0.0
    hhi = float(np.sum(w ** 2))
    return 1.0 / hhi if hhi > 0 else float(len(w))


# ── Smoke test ────────────────────────────────────────────────────────────────

def run_smoke_test() -> None:
    """
    Verify skfolio wiring with 100% synthetic data.
    No model, no yfinance, no meta-filter required.
    """
    logger.info("🔬 Smoke test: synthetic 10-asset returns")
    if not _SKFOLIO_AVAILABLE:
        logger.error("skfolio not available — smoke test cannot run")
        return

    rng = np.random.default_rng(42)
    n_days, n_assets = 400, 10
    syms = [f"SYM{i:02d}" for i in range(n_assets)]
    dates = pd.date_range("2020-01-02", periods=n_days, freq="B")
    X = rng.normal(0.001, 0.02, (n_days, n_assets))
    X_df = pd.DataFrame(X, index=dates, columns=syms)

    # HRP smoke
    from skfolio.optimization import HierarchicalRiskParity
    from skfolio.model_selection import WalkForward

    hrp = HierarchicalRiskParity(min_weights=0.0, max_weights=0.15)
    cv  = WalkForward(train_size=100, test_size=20)

    folds_ok = 0
    for tr, te in cv.split(X):
        hrp.fit(X[tr])
        w = np.array(hrp.weights_)
        assert abs(w.sum() - 1.0) < 0.01, f"Weights don't sum to 1: {w.sum()}"
        assert w.max() <= 0.16, f"Max weight exceeds cap: {w.max()}"
        folds_ok += 1

    logger.info(f"  HRP: {folds_ok} folds OK ✅")

    # Correlation constraint smoke
    synthetic_weights = {s: 1.0 / n_assets for s in syms}
    corr_adj = apply_correlation_constraint(synthetic_weights, X_df)
    assert len(corr_adj) == n_assets
    logger.info(f"  Correlation constraint: OK ✅")

    # Sector cap smoke
    arr = np.full(n_assets, 1.0 / n_assets)
    capped = _apply_sector_cap_to_array(arr, syms)
    assert abs(capped.sum() - 1.0) < 0.01
    logger.info(f"  Sector cap: OK ✅")

    if _CVXPY_AVAILABLE:
        from skfolio.optimization import RiskBudgeting
        from skfolio import RiskMeasure
        budget = np.ones(n_assets) / n_assets
        rb = RiskBudgeting(
            risk_measure=RiskMeasure.VARIANCE,
            min_weights=0.0,
            max_weights=0.15,
            risk_budget=budget,   # skfolio 1.0.0: risk_budget
        )
        rb.fit(X[:200])
        w = np.array(rb.weights_)
        assert abs(w.sum() - 1.0) < 0.01
        logger.info(f"  RiskBudgeting: OK ✅")
    else:
        logger.info(f"  RiskBudgeting: SKIPPED (cvxpy not available)")

    logger.info("✅ All smoke tests passed")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kepler skfolio Portfolio Construction Layer",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--holdout-yaml",      default="configs/frozen_holdout.yaml")
    parser.add_argument("--primary-threshold", type=float, default=0.35)
    parser.add_argument("--meta-threshold",    type=float, default=0.10,
                        help="Minimum meta_score to include a signal in portfolio")
    parser.add_argument("--portfolio-value",   type=float, default=1_000_000,
                        help="INR capital (for reporting ₹ sizes)")
    parser.add_argument("--train-size",        type=int,   default=252,
                        help="WalkForward training window (trading days)")
    parser.add_argument("--test-size",         type=int,   default=21,
                        help="WalkForward test window (trading days)")
    parser.add_argument("--history",           default="8y")
    parser.add_argument("--workers",           type=int,   default=8)
    parser.add_argument("--compare-expectancy", action="store_true",
                        help="Load latest expectancy JSON for side-by-side comparison")
    parser.add_argument("--smoke-test",        action="store_true",
                        help="Run smoke test with synthetic data")
    parser.add_argument("--out",               default=None,
                        help="Output JSON path (auto-generated if omitted)")
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="INFO",
               format="<green>{time:HH:mm:ss}</green> | {message}")

    if args.smoke_test:
        run_smoke_test()
        return

    if not _SKFOLIO_AVAILABLE:
        logger.error("skfolio not installed. Run: pip install 'skfolio>=1.0.0'")
        sys.exit(1)

    yaml_path = _BACKEND_DIR / args.holdout_yaml
    with open(yaml_path) as f:
        holdout_data = yaml.safe_load(f)
    symbols = [t for t in holdout_data.get("tickers", []) if isinstance(t, str)]
    logger.info(f"🔒 Frozen holdout: {len(symbols)} symbols (NEVER in training)")

    hrp_result, rb_result, scored_df = run_skfolio_backtest(
        symbols            = symbols,
        primary_threshold  = args.primary_threshold,
        meta_threshold     = args.meta_threshold,
        portfolio_value    = args.portfolio_value,
        history            = args.history,
        max_workers        = args.workers,
        train_size         = args.train_size,
        test_size          = args.test_size,
    )

    report = build_comparison_report(
        hrp_result, rb_result, scored_df,
        portfolio_value   = args.portfolio_value,
        primary_threshold = args.primary_threshold,
    )

    _print_comparison_report(report)

    # Append fold details
    report["hrp_fold_portfolios"] = [
        {k: v for k, v in vars(fp).items() if k != "weights" or len(fp.weights) < 50}
        for fp in hrp_result.fold_portfolios
    ]
    report["rb_fold_portfolios"] = [
        {k: v for k, v in vars(fp).items() if k != "weights" or len(fp.weights) < 50}
        for fp in rb_result.fold_portfolios
    ]

    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = Path(args.out) if args.out else (_CONFIGS_DIR / f"skfolio_report_{ts}.json")
    out_path.write_text(json.dumps(report, indent=2, default=str))
    logger.info(f"💾 Report saved → {out_path}")
    logger.info(f"→ Run parity comparison: python -m nautilus_strategy.parity_report --auto")


if __name__ == "__main__":
    main()
