"""
ANTIGRAVITY — Backtesting Stats
Calculates historical performance of past Breakout Watchlist entries.
Looks up the price N days after a setup was published and determines
what % of setups went on to gain > threshold%.
"""
import time
from datetime import date, timedelta
from typing import Dict, Any, List, Optional

import yfinance as yf
from loguru import logger
from sqlalchemy.orm import Session

from models import BreakoutWatchlist


# ── Config ─────────────────────────────────────────────────────────────────────
LOOKFORWARD_DAYS = [5, 10, 20]   # check price after 5, 10, 20 trading days
GAIN_THRESHOLD   = 5.0           # % gain = "success"


def _get_price_n_days_later(symbol: str, from_date: date, n: int) -> Optional[float]:
    """Fetch closing price ~n trading days after from_date using yfinance."""
    try:
        target = from_date + timedelta(days=n + 5)  # +5 buffer for weekends/holidays
        ticker = yf.Ticker(f"{symbol}.NS")
        hist = ticker.history(start=from_date.isoformat(), end=target.isoformat(), auto_adjust=True)
        if hist is None or hist.empty or len(hist) < n:
            return None
        # Take the nth available trading day
        return float(hist["Close"].iloc[min(n - 1, len(hist) - 1)])
    except Exception as e:
        logger.debug(f"Price fetch error [{symbol}] +{n}d: {e}")
        return None


def calculate_breakout_stats(db: Session, days_back: int = 90) -> Dict[str, Any]:
    """
    Main entry point.
    Looks at all breakout setups published in the last `days_back` days
    that are old enough to have N-day forward prices available.
    Returns win rates at 5, 10, 20-day horizons.
    """
    cutoff = date.today() - timedelta(days=days_back)
    # Only evaluate setups at least 25 days old (enough time for 20-day lookforward)
    max_date = date.today() - timedelta(days=25)

    setups: List[BreakoutWatchlist] = (
        db.query(BreakoutWatchlist)
        .filter(
            BreakoutWatchlist.date >= cutoff,
            BreakoutWatchlist.date <= max_date,
        )
        .all()
    )

    logger.info(f"Backtesting {len(setups)} setups from last {days_back} days")

    if not setups:
        return _empty_stats(days_back)

    results_by_horizon: Dict[int, List[bool]] = {n: [] for n in LOOKFORWARD_DAYS}
    total_processed = 0

    for setup in setups:
        tech = setup.technical_data or {}
        entry_price = tech.get("current_price")
        if not entry_price:
            continue

        for n in LOOKFORWARD_DAYS:
            future_price = _get_price_n_days_later(setup.symbol, setup.date, n)
            if future_price is None:
                continue
            gain_pct = ((future_price - entry_price) / entry_price) * 100
            results_by_horizon[n].append(gain_pct >= GAIN_THRESHOLD)

        total_processed += 1
        time.sleep(0.15)  # gentle rate limit

    # Compute win rates
    win_rates = {}
    for n in LOOKFORWARD_DAYS:
        outcomes = results_by_horizon[n]
        if outcomes:
            win_rates[f"{n}d"] = {
                "win_rate": round(sum(outcomes) / len(outcomes) * 100, 1),
                "total":    len(outcomes),
                "wins":     sum(outcomes),
            }

    # Average entry stats
    avg_rsi = None
    avg_vol_ratio = None
    if setups:
        rsi_vals = [s.technical_data.get("rsi") for s in setups if s.technical_data and s.technical_data.get("rsi")]
        vol_vals = [s.technical_data.get("volume_ratio") for s in setups if s.technical_data and s.technical_data.get("volume_ratio")]
        avg_rsi = round(sum(rsi_vals) / len(rsi_vals), 1) if rsi_vals else None
        avg_vol_ratio = round(sum(vol_vals) / len(vol_vals), 2) if vol_vals else None

    return {
        "period_days":      days_back,
        "total_setups":     len(setups),
        "evaluated":        total_processed,
        "gain_threshold":   GAIN_THRESHOLD,
        "win_rates":        win_rates,
        "avg_rsi":          avg_rsi,
        "avg_volume_ratio": avg_vol_ratio,
        "note":             f"Setups that gained >{GAIN_THRESHOLD}% within the window are counted as wins.",
    }


def _empty_stats(days_back: int) -> Dict[str, Any]:
    return {
        "period_days":    days_back,
        "total_setups":   0,
        "evaluated":      0,
        "gain_threshold": GAIN_THRESHOLD,
        "win_rates":      {},
        "avg_rsi":        None,
        "avg_volume_ratio": None,
        "note":           "Not enough historical data yet. Stats will populate after 25+ days of operation.",
    }


if __name__ == "__main__":
    from database import SessionLocal
    db = SessionLocal()
    try:
        stats = calculate_breakout_stats(db, days_back=90)
        print(f"\nBacktest Results (last 90 days):")
        print(f"  Setups analysed: {stats['evaluated']}")
        for horizon, data in stats["win_rates"].items():
            print(f"  {horizon} win rate: {data['win_rate']}% ({data['wins']}/{data['total']})")
    finally:
        db.close()
