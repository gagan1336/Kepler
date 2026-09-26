"""
nautilus_strategy.backtest_runner
===================================
BacktestEngine wiring + CLI runner for Kepler parity validation.

Two execution modes
-------------------
1. NautilusTrader mode (default)
   Requires NT DLLs to be loadable (WDAC policy permitting).
   Full event-driven simulation with NSE fee/fill/latency models.

2. Fallback pure-Python mode (--fallback flag, or auto when NT blocked)
   Uses the same scored DataFrame produced by expectancy.py's
   collect_holdout_with_returns(), simulates the identical time-exit logic
   in pure Python, and applies the same NSE cost model.
   This mode is *not* a reimplementation of inference — it scores all bars
   upfront using kepler_model.predict_proba() (same as expectancy.py) and
   then steps through them chronologically to simulate realistic position
   management (no simultaneous open positions per symbol, forward_days exit).

   The fallback mode exists specifically because this machine's WDAC policy
   blocks PyArrow DLLs required by NT's Cython core.

Output
------
    configs/experiment_runs/nautilus_backtest_<ts>.json

    Fields:
        mode            : "nautilus" | "fallback_python"
        generated_at    : ISO timestamp
        holdout_symbols : count
        primary_threshold, meta_threshold, forward_days
        cost_pct        : NSE round-trip %
        n_trades        : total trades generated
        hit_rate        : fraction with y_true == 1
        avg_win_pct     : mean fwd_ret_pct | y_true==1
        avg_loss_pct    : mean fwd_ret_pct | y_true==0
        gross_exp       : hit_rate * avg_win + (1-hit_rate) * avg_loss
        net_exp         : gross_exp - cost_pct
        threshold_sweep : list of per-threshold rows (same schema as expectancy.py)
        trade_records   : full trade log (symbol, dates, prices, scores, ret)

Usage
-----
    cd backend

    # NautilusTrader mode (WDAC must allow PyArrow)
    python -m nautilus_strategy.backtest_runner \\
        --holdout-yaml configs/frozen_holdout.yaml \\
        --primary-threshold 0.35

    # Fallback pure-Python mode (works even under WDAC restrictions)
    python -m nautilus_strategy.backtest_runner \\
        --holdout-yaml configs/frozen_holdout.yaml \\
        --fallback

    # Smoke test (no model, no yfinance — synthetic data)
    python -m nautilus_strategy.backtest_runner --smoke-test
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yaml
from loguru import logger

warnings.filterwarnings("ignore")

_BACKEND_DIR  = Path(__file__).parent.parent
_CONFIGS_DIR  = _BACKEND_DIR / "configs" / "experiment_runs"
_CONFIGS_DIR.mkdir(parents=True, exist_ok=True)

if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))


# ── Shared helpers ────────────────────────────────────────────────────────────

def _load_holdout_symbols(yaml_path: Path) -> List[str]:
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    return [t for t in data.get("tickers", []) if isinstance(t, str)]


def _threshold_sweep(
    trades: List[dict],
    thresholds: List[float],
    cost_pct:   float,
    score_col:  str = "y_score",
) -> List[dict]:
    """
    Replicate expectancy_table() logic on NT trade records.
    Only trades with score >= threshold are included at each level.
    """
    df = pd.DataFrame(trades)
    if df.empty or score_col not in df.columns:
        return []

    rows = []
    for thr in thresholds:
        subset = df[df[score_col] >= thr]
        if len(subset) < 10:
            continue
        wins   = subset[subset["y_true"] == 1]
        losses = subset[subset["y_true"] == 0]
        hit_rate  = len(wins) / len(subset)
        avg_win   = float(wins["fwd_ret_pct"].mean())  if len(wins)   > 0 else 0.0
        avg_loss  = float(losses["fwd_ret_pct"].mean()) if len(losses) > 0 else 0.0
        gross_exp = hit_rate * avg_win + (1 - hit_rate) * avg_loss
        net_exp   = gross_exp - cost_pct
        rows.append({
            "threshold":    thr,
            "n_trades":     int(len(subset)),
            "hit_rate":     round(hit_rate, 4),
            "avg_win_pct":  round(avg_win, 2),
            "avg_loss_pct": round(avg_loss, 2),
            "gross_exp":    round(gross_exp, 3),
            "cost_pct":     round(cost_pct, 3),
            "net_exp":      round(net_exp, 3),
            "verdict":      "✅ Edge" if net_exp > 0 else "🔴 No edge after costs",
        })
    return rows


# ── Fallback pure-Python backtester ──────────────────────────────────────────

def run_fallback_backtest(
    symbols:           List[str],
    primary_threshold: float = 0.35,
    meta_threshold:    float = 0.0,
    forward_days:      int   = 10,
    position_size_inr: float = 50_000.0,
    threshold_pct:     float = 5.0,
    history:           str   = "8y",
    max_workers:       int   = 8,
) -> Dict:
    """
    Pure-Python backtest that replicates the NT event loop without NT.

    Produces TWO trade lists for complete parity analysis:

    A) overlapping_signals   — Every scored bar-row where score >= threshold,
       including overlapping windows.  This matches expectancy.py exactly
       (same inference pipeline, same DataFrame, same threshold logic).
       Use this list for apples-to-apples comparison against expectancy.py.

    B) simulated_trades      — Chronological position-constrained simulation:
       one open position per symbol at a time, closed after forward_days bars.
       This is what the NT event-loop would produce.  Hit rate and net_exp
       computed here reflect realistic position management, not the statistical
       expectancy estimate.

    The parity report compares against (A); (B) is reported as the
    "NT simulation" column showing the position-management discount.

    This mode is NOT a reimplementation — it reuses collect_holdout_with_returns()
    from expectancy.py (same inference pipeline, same data).
    """
    from expectancy import collect_holdout_with_returns
    from nautilus_strategy.nse_cost_model import compute_round_trip_cost_pct

    logger.info("▶ Running fallback pure-Python backtest…")
    logger.info(f"  primary_threshold={primary_threshold}  "
                f"meta_threshold={meta_threshold}  "
                f"forward_days={forward_days}")

    df = collect_holdout_with_returns(symbols, history=history, max_workers=max_workers)

    cost_pct = compute_round_trip_cost_pct(position_size_inr)
    logger.info(f"  NSE round-trip cost @ ₹{position_size_inr:,.0f}: {cost_pct:.3f}%")

    # Determine score column
    if "meta_score" in df.columns and meta_threshold > 0:
        df["combined_score"] = df["y_score"] * df["meta_score"]
        score_col = "combined_score"
    else:
        score_col = "y_score"

    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    # ── A: Overlapping signals (same as expectancy.py) ────────────────────────
    # Every row where score >= threshold is a "signal" — windows may overlap.
    # This is the correct basis for comparing against expectancy.py output.
    signal_mask = df[score_col] >= primary_threshold
    if meta_threshold > 0 and score_col == "y_score" and "meta_score" in df.columns:
        signal_mask &= df["meta_score"] >= meta_threshold

    signals_df = df[signal_mask].copy()
    overlapping_signals: List[dict] = []
    for _, row in signals_df.iterrows():
        fwd_ret = float(row.get("fwd_ret_raw", 0.0))
        overlapping_signals.append({
            "symbol":      row.get("symbol", ""),
            "entry_date":  str(row.get("date", "")),
            "exit_date":   None,
            "entry_price": 1.0,  # relative — fwd_ret_raw is the return
            "exit_price":  1.0 + fwd_ret / 100,
            "fwd_ret_pct": round(fwd_ret, 4),
            "y_score":     float(row.get("y_score", 0.0)),
            "meta_score":  float(row.get("meta_score", 0.5)) if "meta_score" in df.columns else 0.5,
            "y_true":      int(row.get("y_true", 0)),
            "cost_pct":    round(cost_pct, 4),
            "net_exp_pct": round(fwd_ret - cost_pct, 4),
            "forced_exit": False,
            "mode":        "overlapping_signal",
        })

    logger.info(f"  A) Overlapping signals: {len(overlapping_signals):,} at thr={primary_threshold}")

    # ── B: Position-constrained simulation (NT-equivalent) ───────────────────
    # One open position per symbol; skip signals while position is open.
    # This is what the NT event-loop produces.
    simulated_trades: List[dict] = []
    for sym, grp in df.groupby("symbol"):
        grp = grp.reset_index(drop=True)
        open_pos: Optional[dict] = None
        bars_held_counter = 0

        for i, row in grp.iterrows():
            # Time exit check
            if open_pos is not None:
                bars_held_counter += 1
                if bars_held_counter >= forward_days:
                    fwd_ret = float(row.get("fwd_ret_raw", 0.0))
                    simulated_trades.append({
                        "symbol":      sym,
                        "entry_date":  open_pos["entry_date"],
                        "exit_date":   str(row.get("date", "")),
                        "entry_price": 1.0,
                        "exit_price":  1.0 + fwd_ret / 100,
                        "fwd_ret_pct": round(fwd_ret, 4),
                        "y_score":     open_pos["y_score"],
                        "meta_score":  open_pos.get("meta_score", 0.5),
                        "y_true":      1 if fwd_ret >= threshold_pct else 0,
                        "cost_pct":    round(cost_pct, 4),
                        "net_exp_pct": round(fwd_ret - cost_pct, 4),
                        "forced_exit": False,
                        "mode":        "simulated_position",
                    })
                    open_pos = None
                    bars_held_counter = 0
                continue   # skip entry while in position

            # Entry signal
            score = float(row.get(score_col, 0.0))
            if score < primary_threshold:
                continue
            if meta_threshold > 0 and score_col == "y_score" and "meta_score" in df.columns:
                if float(row.get("meta_score", 0.0)) < meta_threshold:
                    continue

            open_pos = {
                "entry_date":  str(row.get("date", "")),
                "y_score":     float(row.get("y_score", 0.0)),
                "meta_score":  float(row.get("meta_score", 0.5)) if "meta_score" in df.columns else 0.5,
            }
            bars_held_counter = 0

    logger.info(f"  B) Simulated trades:    {len(simulated_trades):,} at thr={primary_threshold}")
    logger.info(f"  Position-management discount: "
                f"{(1 - len(simulated_trades)/max(len(overlapping_signals),1))*100:.1f}% fewer trades")

    # Return overlapping signals as primary 'trades' for parity comparison
    # Simulated trades stored separately under 'simulated_trade_records'
    return {
        "trades":                 overlapping_signals,          # for expectancy.py parity
        "simulated_trade_records": simulated_trades,            # for NT simulation parity
        "cost_pct":               cost_pct,
        "mode":                   "fallback_python",
        "n_overlapping_signals":  len(overlapping_signals),
        "n_simulated_trades":     len(simulated_trades),
    }



# ── NautilusTrader backtest ───────────────────────────────────────────────────

def run_nautilus_backtest(
    symbols:           List[str],
    primary_threshold: float = 0.35,
    meta_threshold:    float = 0.0,
    forward_days:      int   = 10,
    position_size_inr: float = 50_000.0,
    threshold_pct:     float = 5.0,
    history:           str   = "8y",
    max_workers:       int   = 8,
    slippage_pct:      float = 0.001,
) -> Dict:
    """
    Full NautilusTrader BacktestEngine run against the 42-stock holdout.
    """
    from nautilus_trader.backtest.engine import BacktestEngine
    from nautilus_trader.backtest.config import BacktestEngineConfig
    from nautilus_trader.model.enums import AccountType, OmsType
    from nautilus_trader.model.identifiers import Venue
    from nautilus_trader.model.objects import Money
    from nautilus_trader.model.currencies import Currency

    from nautilus_strategy.data_loader import load_holdout_bars, ohlcv_to_nt_bars, load_instrument
    from nautilus_strategy.nse_cost_model import (
        NSEFeeModel, NSEFillModel, NSELatencyModel, compute_round_trip_cost_pct
    )
    from nautilus_strategy.kepler_strategy import KeplerStrategyConfig, build_kepler_strategy

    logger.info("▶ Running NautilusTrader backtest…")

    # ── 1. Configure engine ───────────────────────────────────────────────────
    cfg = BacktestEngineConfig(
        trader_id="KEPLER-BACKTEST-001",
        logging={"log_level": "ERROR"},   # suppress NT verbose logs
    )
    engine = BacktestEngine(config=cfg)

    # ── 2. Add venue ──────────────────────────────────────────────────────────
    inr = Currency.from_str("INR")
    engine.add_venue(
        venue=Venue("NSE"),
        oms_type=OmsType.NETTING,
        account_type=AccountType.CASH,
        base_currency=inr,
        starting_balances=[Money(10_000_000, inr)],   # ₹1 Cr starting capital
        fee_model=NSEFeeModel(),
        fill_model=NSEFillModel(slippage_pct=slippage_pct),
        latency_model=NSELatencyModel(),
    )

    # ── 3. Load and add data ──────────────────────────────────────────────────
    ohlcv_by_sym = load_holdout_bars(symbols, period=history, max_workers=max_workers)
    for sym, ohlcv_df in ohlcv_by_sym.items():
        instrument = load_instrument(sym)
        engine.add_instrument(instrument)
        bars = ohlcv_to_nt_bars(sym, ohlcv_df)
        engine.add_data(bars)
        logger.debug(f"  {sym}: {len(bars)} bars added")

    logger.info(f"  {len(ohlcv_by_sym)} instruments loaded")

    # ── 4. Build and add strategy ─────────────────────────────────────────────
    strat_cfg = KeplerStrategyConfig(
        instrument_ids    = list(ohlcv_by_sym.keys()),
        primary_threshold = primary_threshold,
        meta_threshold    = meta_threshold,
        forward_days      = forward_days,
        position_size_inr = position_size_inr,
        threshold_pct     = threshold_pct,
    )
    strategy = build_kepler_strategy(strat_cfg)
    engine.add_strategy(strategy)

    # ── 5. Run ────────────────────────────────────────────────────────────────
    logger.info("  Running engine…")
    engine.run()
    logger.info("  Engine run complete")

    cost_pct = compute_round_trip_cost_pct(position_size_inr, slippage_pct)
    trades   = strategy._trades

    logger.info(f"  ✅ {len(trades)} trades recorded")
    engine.dispose()
    return {"trades": trades, "cost_pct": cost_pct, "mode": "nautilus"}


# ── Smoke test ────────────────────────────────────────────────────────────────

def run_smoke_test() -> None:
    """
    Verify engine wiring with synthetic OHLCV data.
    Does not require a trained model or yfinance.
    """
    logger.info("🔬 Smoke test: synthetic data, no model required")

    try:
        from nautilus_trader.backtest.engine import BacktestEngine
        from nautilus_trader.backtest.config import BacktestEngineConfig
        from nautilus_trader.model.enums import AccountType, OmsType
        from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
        from nautilus_trader.model.objects import Money, Price, Quantity
        from nautilus_trader.model.currencies import Currency
        from nautilus_trader.model.data import Bar, BarSpecification, BarType
        from nautilus_trader.model.enums import AggregationSource, BarAggregation, PriceType
        from nautilus_trader.model.instruments import Equity

        logger.info("  NautilusTrader imports OK ✅")

        cfg = BacktestEngineConfig(trader_id="SMOKE-001",
                                   logging={"log_level": "ERROR"})
        engine = BacktestEngine(config=cfg)
        inr    = Currency.from_str("INR")
        engine.add_venue(
            venue=Venue("NSE"),
            oms_type=OmsType.NETTING,
            account_type=AccountType.CASH,
            base_currency=inr,
            starting_balances=[Money(1_000_000, inr)],
        )

        # Synthetic instrument
        sym  = "TESTSTOCK"
        iid  = InstrumentId(Symbol(sym), Venue("NSE"))
        inst = Equity(
            instrument_id   = iid,
            raw_symbol      = Symbol(sym),
            currency        = inr,
            price_precision = 2,
            price_increment = Price(0.01, precision=2),
            lot_size        = Quantity(1, precision=0),
            ts_event        = 0,
            ts_init         = 0,
        )
        engine.add_instrument(inst)

        # Synthetic bars (100 days)
        spec = BarSpecification(1, BarAggregation.DAY, PriceType.LAST)
        bt   = BarType(iid, spec, AggregationSource.EXTERNAL)
        import pandas as pd
        import numpy as np
        dates = pd.date_range("2020-01-02", periods=100, freq="B", tz="UTC")
        rng   = np.random.default_rng(42)
        prices = 100.0 * np.cumprod(1 + rng.normal(0, 0.01, 100))
        bars = [
            Bar(bt,
                open   = Price(round(p * 0.99, 2), precision=2),
                high   = Price(round(p * 1.01, 2), precision=2),
                low    = Price(round(p * 0.98, 2), precision=2),
                close  = Price(round(p, 2),         precision=2),
                volume = Quantity(10_000, precision=0),
                ts_event = int(d.value),
                ts_init  = int(d.value),
            )
            for p, d in zip(prices, dates)
        ]
        engine.add_data(bars)
        engine.run()
        engine.dispose()
        logger.info("  BacktestEngine smoke test PASSED ✅")

    except ImportError as exc:
        if "Application Control" in str(exc) or "DLL load failed" in str(exc):
            logger.warning(
                "  ⚠️  NautilusTrader blocked by WDAC policy.\n"
                "  Use --fallback mode for parity validation on this machine.\n"
                f"  Details: {exc}"
            )
        else:
            raise


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Kepler × NautilusTrader Parity Backtest Runner",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--holdout-yaml",      default="configs/frozen_holdout.yaml")
    parser.add_argument("--primary-threshold", type=float, default=0.35)
    parser.add_argument("--meta-threshold",    type=float, default=0.0,
                        help="Meta-filter threshold (0 = disabled)")
    parser.add_argument("--forward-days",      type=int,   default=10)
    parser.add_argument("--position-size",     type=float, default=50_000.0,
                        help="Notional trade value INR (for cost model)")
    parser.add_argument("--slippage-pct",      type=float, default=0.001,
                        help="One-way slippage fraction (default 0.001 = 0.10%%)")
    parser.add_argument("--history",           default="8y")
    parser.add_argument("--workers",           type=int,   default=8)
    parser.add_argument("--fallback",          action="store_true",
                        help="Use pure-Python fallback (skips NT engine)")
    parser.add_argument("--smoke-test",        action="store_true",
                        help="Run engine smoke test with synthetic data (no model)")
    parser.add_argument("--out",               default=None,
                        help="Output JSON path (auto-generated if omitted)")
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="INFO",
               format="<green>{time:HH:mm:ss}</green> | {message}")

    if args.smoke_test:
        run_smoke_test()
        return

    yaml_path = _BACKEND_DIR / args.holdout_yaml
    symbols   = _load_holdout_symbols(yaml_path)
    logger.info(f"🔒 Frozen holdout: {len(symbols)} symbols")

    # Auto-fallback if NT blocked
    if not args.fallback:
        try:
            import pyarrow  # noqa: F401 — triggers WDAC check early
        except ImportError:
            logger.warning(
                "⚠️  PyArrow blocked by WDAC — automatically switching to --fallback mode.\n"
                "   Re-run on a machine without Application Control restrictions for full NT mode."
            )
            args.fallback = True

    if args.fallback:
        result = run_fallback_backtest(
            symbols           = symbols,
            primary_threshold = args.primary_threshold,
            meta_threshold    = args.meta_threshold,
            forward_days      = args.forward_days,
            position_size_inr = args.position_size,
            history           = args.history,
            max_workers       = args.workers,
        )
    else:
        result = run_nautilus_backtest(
            symbols           = symbols,
            primary_threshold = args.primary_threshold,
            meta_threshold    = args.meta_threshold,
            forward_days      = args.forward_days,
            position_size_inr = args.position_size,
            threshold_pct     = 5.0,
            history           = args.history,
            max_workers       = args.workers,
            slippage_pct      = args.slippage_pct,
        )

    trades   = result["trades"]
    cost_pct = result["cost_pct"]
    mode     = result["mode"]

    # ── Compute summary metrics ───────────────────────────────────────────────
    thresholds = [0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60]
    sweep = _threshold_sweep(trades, thresholds, cost_pct)

    df_trades = pd.DataFrame(trades) if trades else pd.DataFrame()
    if not df_trades.empty and "y_true" in df_trades.columns:
        hit_rate  = float(df_trades["y_true"].mean())
        wins      = df_trades[df_trades["y_true"] == 1]["fwd_ret_pct"]
        losses    = df_trades[df_trades["y_true"] == 0]["fwd_ret_pct"]
        avg_win   = float(wins.mean())  if len(wins)   > 0 else 0.0
        avg_loss  = float(losses.mean()) if len(losses) > 0 else 0.0
        gross_exp = hit_rate * avg_win + (1 - hit_rate) * avg_loss
        net_exp   = gross_exp - cost_pct
    else:
        hit_rate = avg_win = avg_loss = gross_exp = net_exp = 0.0

    # ── Build output ──────────────────────────────────────────────────────────
    ts  = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    out = {
        "mode":              mode,
        "generated_at":      datetime.utcnow().isoformat() + "Z",
        "holdout_symbols":   len(symbols),
        "primary_threshold": args.primary_threshold,
        "meta_threshold":    args.meta_threshold,
        "forward_days":      args.forward_days,
        "position_size_inr": args.position_size,
        "cost_pct":          round(cost_pct, 4),
        # Overlapping-window stats (comparable to expectancy.py)
        "n_overlapping_signals":  result.get("n_overlapping_signals", len(trades)),
        "n_simulated_trades":     result.get("n_simulated_trades", 0),
        "n_trades":          len(trades),
        "hit_rate":          round(hit_rate, 4),
        "avg_win_pct":       round(avg_win, 2),
        "avg_loss_pct":      round(avg_loss, 2),
        "gross_exp":         round(gross_exp, 3),
        "net_exp":           round(net_exp, 3),
        "threshold_sweep":   sweep,
        "trade_records":     trades,
        # Position-constrained simulation records (NT-equivalent)
        "simulated_trade_records": result.get("simulated_trade_records", []),
    }

    out_path = Path(args.out) if args.out else (
        _CONFIGS_DIR / f"nautilus_backtest_{ts}.json"
    )
    out_path.write_text(json.dumps(out, indent=2, default=str))
    logger.info(f"💾 Results saved → {out_path}")

    # ── Print summary ─────────────────────────────────────────────────────────
    logger.info(f"\n{'═'*70}")
    logger.info(f"  NAUTILUS BACKTEST SUMMARY  [{mode}]")
    logger.info(f"{'═'*70}")
    logger.info(f"  Holdout symbols : {len(symbols)}")
    logger.info(f"  Total trades    : {len(trades)}")
    logger.info(f"  Hit rate        : {hit_rate:.1%}")
    logger.info(f"  Avg win         : {avg_win:+.2f}%")
    logger.info(f"  Avg loss        : {avg_loss:+.2f}%")
    logger.info(f"  Gross exp       : {gross_exp:+.3f}%")
    logger.info(f"  Cost (round-trip): {cost_pct:.3f}%")
    logger.info(f"  Net expectancy  : {net_exp:+.3f}%  "
                f"{'✅ Edge' if net_exp > 0 else '🔴 No edge'}")
    logger.info(f"{'═'*70}\n")
    logger.info(f"→ Run parity report: python -m nautilus_strategy.parity_report "
                f"--nautilus {out_path}")


if __name__ == "__main__":
    main()
