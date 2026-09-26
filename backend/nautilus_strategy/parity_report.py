"""
nautilus_strategy.parity_report
=================================
Side-by-side comparison of the custom backtester (expectancy.py) output vs the
NautilusTrader/fallback backtester output.

Usage
-----
    python -m nautilus_strategy.parity_report \\
        --custom   configs/experiment_runs/expectancy_<ts>.json \\
        --nautilus configs/experiment_runs/nautilus_backtest_<ts>.json

    # Auto-find the latest files
    python -m nautilus_strategy.parity_report --auto

Output
------
A human-readable table plus a JSON diff file at:
    configs/experiment_runs/parity_report_<ts>.json

Parity criteria (tolerances)
-----------------------------
Metric               Tolerance     Rationale
───────────────────────────────────────────────────────────────────────────
hit_rate             ± 3.0 pp      Position mgmt: NT skips overlapping signals
net_expectancy       ± 0.20 pp     Cost model is the same; small fill-price δ
AUC-equivalent       ± 0.01        Score distribution is identical (same model)
cost_pct             ± 0.05 pp     Same formula; rounding only
n_trades             ± 10%         Position management prevents re-entry during hold

Known discrepancy sources (always reported explicitly)
------------------------------------------------------
D1  N_TRADES DELTA
    The custom backtester scores ALL bars (including overlapping windows) with
    no position constraint.  The NT/fallback runner enforces "one open position
    per symbol at a time".  This reduces trade count by up to ~10%.

D2  FILL PRICE DELTA
    Custom backtester: fwd_ret_raw computed from bar i's close to bar i+N's close.
    NT mode: fills at bar-open of the next bar (one-bar slippage).
    Fallback mode: uses the same fwd_ret_raw as custom, so fill price matches.

D3  COST MODEL DELTA
    Custom backtester: flat cost_pct subtracted from expectancy formula.
    NT mode: per-order Money deduction by NSEFeeModel.get_commission().
    Fallback mode: identical flat cost_pct subtraction — should match exactly.

D4  MACRO / RANK FEATURES
    Both backtester paths zero-fill macro and cross-sectional rank features
    (expectancy.py fallback path).  No delta expected here.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

_BACKEND_DIR  = Path(__file__).parent.parent
_CONFIGS_DIR  = _BACKEND_DIR / "configs" / "experiment_runs"

if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _latest(prefix: str) -> Optional[Path]:
    """Return the newest JSON file in experiment_runs/ matching prefix."""
    files = sorted(_CONFIGS_DIR.glob(f"{prefix}*.json"), key=lambda p: p.stat().st_mtime)
    return files[-1] if files else None


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _auc_equivalent(sweep: List[dict]) -> float:
    """
    Approximate ROC-AUC from the threshold sweep as a trapezoidal integral over
    (hit_rate, threshold) — a proxy that lets us compare the two backtests on
    the same axis as the model's validation AUC.

    Specifically: AUC-proxy = mean(hit_rate) across all threshold levels.
    This is NOT the same as sklearn roc_auc_score but it is directly comparable
    between two runs using the same threshold grid.
    """
    if not sweep:
        return 0.0
    return round(sum(r["hit_rate"] for r in sweep) / len(sweep), 4)


def _flag(delta: float, tol: float) -> str:
    return "✅" if abs(delta) <= tol else "❌ OUTSIDE TOLERANCE"


# ── Main comparison ───────────────────────────────────────────────────────────

def compare(custom_path: Path, nautilus_path: Path) -> dict:
    """
    Compare custom backtester output vs NT/fallback output.
    Returns a dict with 'table', 'discrepancies', and 'pass'.
    """
    cust = _load(custom_path)
    nt   = _load(nautilus_path)

    # ── Pull numbers from each ────────────────────────────────────────────────
    # Custom: uses primary_expectancy rows (no meta filter), matching NT default
    cust_sweep = cust.get("primary_expectancy", cust.get("threshold_sweep", []))
    nt_sweep   = nt.get("threshold_sweep", [])

    # Map by threshold for aligned comparison
    cust_by_thr = {r["threshold"]: r for r in cust_sweep}
    nt_by_thr   = {r["threshold"]: r for r in nt_sweep}
    common_thrs = sorted(set(cust_by_thr) & set(nt_by_thr))

    # Overall summary numbers at default threshold (0.35)
    def _get(d, thr, key, fallback=0.0):
        row = d.get(thr, {})
        return float(row.get(key, fallback)) if row else fallback

    thr_main = 0.35

    cust_hit   = _get(cust_by_thr, thr_main, "hit_rate")
    nt_hit     = _get(nt_by_thr,  thr_main, "hit_rate")

    cust_net   = _get(cust_by_thr, thr_main, "net_exp")
    nt_net     = _get(nt_by_thr,  thr_main, "net_exp")

    cust_gross = _get(cust_by_thr, thr_main, "gross_exp")
    nt_gross   = _get(nt_by_thr,  thr_main, "gross_exp")

    cust_cost  = float(cust.get("cost_pct", 0.0))
    nt_cost    = float(nt.get("cost_pct", 0.0))

    cust_n     = _get(cust_by_thr, thr_main, "n_trades")
    nt_n       = _get(nt_by_thr,  thr_main, "n_trades")

    cust_auc   = _auc_equivalent(cust_sweep)
    nt_auc     = _auc_equivalent(nt_sweep)

    # Tolerances (see module docstring)
    TOLERANCES = {
        "hit_rate":    0.03,
        "net_exp":     0.20,
        "auc_equiv":   0.01,
        "cost_pct":    0.0005,   # 0.05 pp
        "n_trades_pct": 0.10,    # 10% relative
    }

    n_trades_rel_delta = abs(cust_n - nt_n) / max(cust_n, 1)

    rows = [
        {
            "metric":   f"Hit rate (thr={thr_main})",
            "custom":   f"{cust_hit:.1%}",
            "nautilus": f"{nt_hit:.1%}",
            "delta":    f"{nt_hit - cust_hit:+.1%}",
            "flag":     _flag(abs(nt_hit - cust_hit), TOLERANCES["hit_rate"]),
        },
        {
            "metric":   f"Net expectancy (thr={thr_main})",
            "custom":   f"{cust_net:+.3f}%",
            "nautilus": f"{nt_net:+.3f}%",
            "delta":    f"{nt_net - cust_net:+.3f}%",
            "flag":     _flag(abs(nt_net - cust_net), TOLERANCES["net_exp"]),
        },
        {
            "metric":   f"Gross expectancy (thr={thr_main})",
            "custom":   f"{cust_gross:+.3f}%",
            "nautilus": f"{nt_gross:+.3f}%",
            "delta":    f"{nt_gross - cust_gross:+.3f}%",
            "flag":     _flag(abs(nt_gross - cust_gross), TOLERANCES["net_exp"]),
        },
        {
            "metric":   "Cost per trade (round-trip)",
            "custom":   f"{cust_cost:.3f}%",
            "nautilus": f"{nt_cost:.3f}%",
            "delta":    f"{nt_cost - cust_cost:+.4f}%",
            "flag":     _flag(abs(nt_cost - cust_cost), TOLERANCES["cost_pct"]),
        },
        {
            "metric":   f"AUC-equivalent (sweep mean hit rate)",
            "custom":   f"{cust_auc:.4f}",
            "nautilus": f"{nt_auc:.4f}",
            "delta":    f"{nt_auc - cust_auc:+.4f}",
            "flag":     _flag(abs(nt_auc - cust_auc), TOLERANCES["auc_equiv"]),
        },
        {
            "metric":   f"N trades (thr={thr_main})",
            "custom":   f"{int(cust_n):,}",
            "nautilus": f"{int(nt_n):,}",
            "delta":    f"{int(nt_n - cust_n):+,}",
            "flag":     _flag(n_trades_rel_delta, TOLERANCES["n_trades_pct"]),
        },
    ]

    # ── Per-threshold sweep table ─────────────────────────────────────────────
    sweep_rows = []
    for thr in common_thrs:
        cr = cust_by_thr[thr]
        nr = nt_by_thr[thr]
        sweep_rows.append({
            "threshold":       thr,
            "custom_hit":      cr.get("hit_rate"),
            "nt_hit":          nr.get("hit_rate"),
            "delta_hit":       round(nr.get("hit_rate", 0) - cr.get("hit_rate", 0), 4),
            "custom_net_exp":  cr.get("net_exp"),
            "nt_net_exp":      nr.get("net_exp"),
            "delta_net_exp":   round(nr.get("net_exp", 0) - cr.get("net_exp", 0), 4),
            "custom_n":        cr.get("n_trades"),
            "nt_n":            nr.get("n_trades"),
        })

    # ── Known discrepancy explanations ────────────────────────────────────────
    nt_mode = nt.get("mode", "unknown")
    discrepancies = {
        "D1_n_trades_delta": {
            "description": (
                "Custom backtester scores all bars including overlapping windows "
                "(no position constraint). NT/fallback enforces one open position "
                "per symbol — signals during an open position are skipped. "
                f"Observed delta: {int(nt_n - cust_n):+,} trades at thr={thr_main}."
            ),
            "in_tolerance": _flag(n_trades_rel_delta, TOLERANCES["n_trades_pct"]) == "✅",
        },
        "D2_fill_price_delta": {
            "description": (
                "Custom: fwd_ret_raw = close[i+N] / close[i] - 1. "
                "NT full mode: fills at next bar open (one-bar slippage). "
                f"Fallback mode ({nt_mode}): uses same fwd_ret_raw as custom — "
                "no fill-price delta expected in fallback mode."
            ),
            "applies_to": "nautilus full mode only",
        },
        "D3_cost_model_delta": {
            "description": (
                "Custom: flat round-trip % subtracted. "
                "NT full mode: per-order Money deduction via NSEFeeModel. "
                f"Fallback: identical flat % — delta should be 0. "
                f"Observed cost_pct delta: {nt_cost - cust_cost:+.4f}%."
            ),
            "in_tolerance": _flag(abs(nt_cost - cust_cost), TOLERANCES["cost_pct"]) == "✅",
        },
        "D4_macro_rank_features": {
            "description": (
                "Both paths zero-fill macro and cross-sectional rank features. "
                "No scoring delta expected here."
            ),
            "in_tolerance": True,
        },
    }

    all_pass = all(r["flag"] == "✅" for r in rows)

    return {
        "custom_file":    str(custom_path),
        "nautilus_file":  str(nautilus_path),
        "nt_mode":        nt_mode,
        "summary_table":  rows,
        "sweep_table":    sweep_rows,
        "discrepancies":  discrepancies,
        "parity_pass":    all_pass,
    }


def print_report(report: dict) -> None:
    logger.info(f"\n{'═'*76}")
    logger.info(f"  KEPLER BACKTEST PARITY REPORT  [{report['nt_mode']}]")
    logger.info(f"{'═'*76}")
    logger.info(f"  Custom   : {Path(report['custom_file']).name}")
    logger.info(f"  Nautilus : {Path(report['nautilus_file']).name}")
    logger.info(f"  {'─'*72}")
    logger.info(f"  {'Metric':<38} {'Custom':>10} {'Nautilus':>10} {'Δ':>9}  Status")
    logger.info(f"  {'─'*72}")
    for r in report["summary_table"]:
        logger.info(
            f"  {r['metric']:<38} {r['custom']:>10} {r['nautilus']:>10} "
            f"{r['delta']:>9}  {r['flag']}"
        )
    logger.info(f"  {'─'*72}")

    logger.info("\n  THRESHOLD SWEEP (common thresholds):")
    logger.info(f"  {'Thr':>5} {'CustHit%':>9} {'NT Hit%':>9} {'ΔHit':>7} "
                f"{'CustNet%':>9} {'NT Net%':>9} {'ΔNet':>7}")
    for r in report["sweep_table"]:
        logger.info(
            f"  {r['threshold']:>5.2f} "
            f"{r['custom_hit']:>8.1%}  {r['nt_hit']:>8.1%}  "
            f"{r['delta_hit']:>+6.3f}  "
            f"{r['custom_net_exp']:>+8.3f}%  {r['nt_net_exp']:>+8.3f}%  "
            f"{r['delta_net_exp']:>+6.3f}%"
        )

    logger.info("\n  KNOWN DISCREPANCY EXPLANATIONS:")
    for key, val in report["discrepancies"].items():
        in_tol = val.get("in_tolerance", "N/A")
        tol_str = f"[in_tol={in_tol}]" if isinstance(in_tol, bool) else ""
        logger.info(f"  {key} {tol_str}")
        logger.info(f"    {val['description']}")

    verdict = "✅ PARITY PASS" if report["parity_pass"] else "❌ PARITY FAIL — investigate flagged metrics"
    logger.info(f"\n  {verdict}")
    logger.info(f"{'═'*76}\n")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kepler Backtest Parity Report",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--custom",   default=None,
                        help="Path to expectancy_<ts>.json (auto-detect if omitted)")
    parser.add_argument("--nautilus", default=None,
                        help="Path to nautilus_backtest_<ts>.json (auto-detect if omitted)")
    parser.add_argument("--auto",     action="store_true",
                        help="Auto-find latest files in experiment_runs/")
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="INFO",
               format="<green>{time:HH:mm:ss}</green> | {message}")

    custom_path   = Path(args.custom)   if args.custom   else _latest("expectancy_")
    nautilus_path = Path(args.nautilus) if args.nautilus else _latest("nautilus_backtest_")

    if custom_path is None or not custom_path.exists():
        logger.error("Custom backtester output not found. Run: python expectancy.py first.")
        sys.exit(1)
    if nautilus_path is None or not nautilus_path.exists():
        logger.error("Nautilus backtest output not found. Run: python -m nautilus_strategy.backtest_runner first.")
        sys.exit(1)

    report = compare(custom_path, nautilus_path)
    print_report(report)

    # Save JSON report
    ts       = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out_path = _CONFIGS_DIR / f"parity_report_{ts}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str))
    logger.info(f"💾 Parity report saved → {out_path}")

    sys.exit(0 if report["parity_pass"] else 1)


if __name__ == "__main__":
    main()
