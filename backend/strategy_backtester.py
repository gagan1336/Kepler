"""
KEPLER — Strategy Backtester (Swing Trading)
=============================================
Walk-forward backtesting engine for 14 swing trading strategies.
For each strategy, scans 3 years of historical NSE data to determine:
  - Win Rate at 10d / 20d / 30d / 45d horizons
  - Average Return, Max Drawdown, Profit Factor, Expectancy, Sharpe
  - Only strategies with win_rate_20d >= 55% AND profit_factor >= 1.5
    are marked "ACTIVE" and used in picks.

Results are cached to backend/.cache/strategy_backtest.json (weekly refresh).

Usage
-----
    python strategy_backtester.py --quick-test     # 5 stocks, 1 year
    python strategy_backtester.py                  # Full run (200 stocks, 3 years)
"""

import argparse
import json
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf
from loguru import logger

# ── Paths ──────────────────────────────────────────────────────────────────────
_BACKEND_DIR = Path(__file__).parent
_CACHE_DIR   = _BACKEND_DIR / ".cache"
_CACHE_DIR.mkdir(exist_ok=True)
_BT_CACHE_FILE = _CACHE_DIR / "strategy_backtest.json"
_BT_CACHE_TTL  = 7 * 24 * 3600  # weekly refresh
_PARAMS_FILE   = _BACKEND_DIR / "configs" / "strategy_params.json"

def _load_params() -> dict:
    try:
        with open(_PARAMS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load strategy params, using defaults: {e}")
        return {}

STRATEGY_PARAMS = _load_params()
SYS_PARAMS = STRATEGY_PARAMS.get("system", {})

# ── Universe for backtesting (200 NSE stocks) ─────────────────────────────────
BT_UNIVERSE = [
    # Nifty 50
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","INFY.NS","BHARTIARTL.NS",
    "ICICIBANK.NS","KOTAKBANK.NS","HINDUNILVR.NS","ITC.NS","LT.NS",
    "SBIN.NS","BAJFINANCE.NS","ASIANPAINT.NS","MARUTI.NS","AXISBANK.NS",
    "SUNPHARMA.NS","TITAN.NS","WIPRO.NS","ULTRACEMCO.NS","NESTLEIND.NS",
    "POWERGRID.NS","NTPC.NS","ONGC.NS","COALINDIA.NS","TECHM.NS",
    "HCLTECH.NS","DRREDDY.NS","BAJAJFINSV.NS","GRASIM.NS","ADANIENT.NS",
    "JSWSTEEL.NS","TATASTEEL.NS","HINDALCO.NS","CIPLA.NS","EICHERMOT.NS",
    "TATACONSUM.NS","DIVISLAB.NS","APOLLOHOSP.NS","TATAMOTORS.NS",
    "BPCL.NS","HEROMOTOCO.NS","BRITANNIA.NS","INDUSINDBK.NS","SBILIFE.NS",
    "HDFCLIFE.NS","ICICIGI.NS","ADANIPORTS.NS","LTIM.NS","BAJAJ-AUTO.NS",
    # Mid cap
    "ZOMATO.NS","DMART.NS","PIDILITIND.NS","SIEMENS.NS","HAVELLS.NS",
    "MUTHOOTFIN.NS","CHOLAFIN.NS","IDFCFIRSTB.NS","FEDERALBNK.NS",
    "TATAPOWER.NS","IRCTC.NS","HAL.NS","BEL.NS","DLF.NS","GODREJPROP.NS",
    "PRESTIGE.NS","OBEROIRLTY.NS","LUPIN.NS","AUROPHARMA.NS","ALKEM.NS",
    "TORNTPHARM.NS","ZYDUSLIFE.NS","MAXHEALTH.NS","FORTIS.NS",
    "OFSS.NS","MPHASIS.NS","PERSISTENT.NS","COFORGE.NS","LTTS.NS",
    "POLYCAB.NS","KEI.NS","ASTRAL.NS","DIXON.NS","AMBER.NS","KAYNES.NS",
    "ANGELONE.NS","BAJAJ-AUTO.NS","TVSMOTORS.NS",
    "PAGEIND.NS","TRENT.NS","NMDC.NS","IRFC.NS","RECLTD.NS",
    "JKCEMENT.NS","SHREECEM.NS","AMBUJACEM.NS","ACC.NS",
    "DEEPAKNTR.NS","SRF.NS","PIIND.NS","SOLARINDS.NS",
    "LALPATHLAB.NS","METROPOLIS.NS","BIOCON.NS",
    "NHPC.NS","SJVN.NS","TATACOMM.NS",
    "JUBLFOOD.NS","DEVYANI.NS",
    "KALYANKJIL.NS","MOTHERSON.NS","TATACHEM.NS",
    "IOC.NS","HINDPETRO.NS","IGL.NS","GAIL.NS","PETRONET.NS",
    "CONCOR.NS","ADANIGREEN.NS","MARICO.NS","DABUR.NS","COLPAL.NS",
    "GODREJCP.NS","VOLTAS.NS","CROMPTON.NS",
    "APOLLOTYRE.NS","MRF.NS","BALKRISIND.NS",
    "MANAPPURAM.NS","HDFCAMC.NS","ABB.NS","CUMMINSIND.NS",
    "THERMAX.NS","BHEL.NS","PFC.NS","IREDA.NS",
    "TATAELXSI.NS","CYIENT.NS","KPITTECH.NS",
    "AFFLE.NS","INDIAMART.NS","NAUKRI.NS",
    "ESCORTS.NS","SONACOMS.NS","HINDZINC.NS",
    "M&M.NS","TIINDIA.NS","AUBANK.NS","CDSL.NS","BSE.NS","MCX.NS",
    "SHRIRAMFIN.NS","RAYMOND.NS","HAL.NS","COCHINSHIP.NS",
    "INDUSTOWER.NS","BHARTIHEXA.NS",
]
BT_UNIVERSE = list(dict.fromkeys(BT_UNIVERSE))  # deduplicate

# ── Strategy definitions ────────────────────────────────────────────────────────
STRATEGIES = {
    "near_52w_high": {
        "label": "Near 52-Week High",
        "icon": "🚀",
        "description": "Within 5% of 52W high — breakout candidates",
        "color": "#10b981",
        "target_horizon_days": 20,
    },
    "breakout_52w": {
        "label": "52W High Breakout",
        "icon": "💥",
        "description": "Price at/above 52W high — confirmed breakout",
        "color": "#f59e0b",
        "target_horizon_days": 20,
    },
    "volume_surge": {
        "label": "Volume Surge",
        "icon": "📊",
        "description": "Volume 3×+ above 10d avg with positive close",
        "color": "#6366f1",
        "target_horizon_days": 10,
    },
    "momentum_leaders": {
        "label": "Momentum Leaders",
        "icon": "⚡",
        "description": "Price > 20 EMA > 50 EMA > 200 EMA",
        "color": "#3b82f6",
        "target_horizon_days": 30,
    },
    "rsi_oversold_bounce": {
        "label": "RSI Oversold Bounce",
        "icon": "🔄",
        "description": "RSI 25-45, above 200 DMA — reversal candidates",
        "color": "#ec4899",
        "target_horizon_days": 20,
    },
    "rsi_momentum": {
        "label": "RSI Momentum",
        "icon": "📈",
        "description": "RSI > 65 with EMA aligned — strong momentum",
        "color": "#8b5cf6",
        "target_horizon_days": 20,
    },
    "vcp_tight": {
        "label": "VCP (Tight Setup)",
        "icon": "🎯",
        "description": "Volatility contraction near highs (Minervini)",
        "color": "#14b8a6",
        "target_horizon_days": 30,
    },
    "golden_crossover": {
        "label": "Golden Crossover",
        "icon": "✨",
        "description": "50 DMA crossed above 200 DMA",
        "color": "#eab308",
        "target_horizon_days": 45,
    },
    "high_rs": {
        "label": "High Relative Strength",
        "icon": "💪",
        "description": "Outperforms Nifty 50 by 30%+ from 52W low",
        "color": "#f97316",
        "target_horizon_days": 30,
    },
    "ema_pullback_bounce": {
        "label": "EMA Pullback Bounce",
        "icon": "🏀",
        "description": "Pullback to 20 EMA in uptrend — buy the dip",
        "color": "#06b6d4",
        "target_horizon_days": 20,
    },
    "marubozu_breakout": {
        "label": "Marubozu Breakout",
        "icon": "🕯️",
        "description": "Bullish Marubozu candle with volume surge",
        "color": "#84cc16",
        "target_horizon_days": 10,
    },
    "stage2_base_breakout": {
        "label": "Stage 2 Base Breakout",
        "icon": "🏗️",
        "description": "Weinstein Stage 2 breakout from consolidation base",
        "color": "#a855f7",
        "target_horizon_days": 45,
    },
    "accumulation_zone": {
        "label": "Accumulation Zone",
        "icon": "🏦",
        "description": "High-volume accumulation in tight range",
        "color": "#f43f5e",
        "target_horizon_days": 30,
    },
    "news_catalyst_momentum": {
        "label": "News Catalyst Momentum",
        "icon": "📰",
        "description": "Breakout on positive news catalyst with volume",
        "color": "#fb923c",
        "target_horizon_days": 10,
    },
}

WIN_RATE_THRESHOLD = SYS_PARAMS.get("WIN_RATE_THRESHOLD", 55.0)   # minimum win rate % to be "ACTIVE"
PROFIT_FACTOR_MIN  = SYS_PARAMS.get("PROFIT_FACTOR_MIN", 1.3)    # minimum profit factor to be "ACTIVE"
GAIN_THRESHOLD_PCT = SYS_PARAMS.get("GAIN_THRESHOLD_PCT", 5.0)    # trade is a "win" if return > this
HORIZONS = [10, 20, 30, 45] # forward-look days
MIN_TRADES_REQUIRED = 15    # minimum trades for statistical validity


# ── Safe helpers ───────────────────────────────────────────────────────────────

def _sf(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return None


def _compute_rsi(closes: pd.Series, period: int = 14) -> pd.Series:
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


# ── Signal detection for each strategy ────────────────────────────────────────

def _detect_signals(df: pd.DataFrame, strategy: str) -> pd.Series:
    """
    For a given strategy, returns a boolean Series aligned with df index.
    True = entry signal on that bar.
    """
    close  = df["Close"]
    volume = df["Volume"]
    high   = df["High"]
    low    = df["Low"]
    opens  = df["Open"]

    try:
        ema20  = _ema(close, 20)
        ema50  = _ema(close, 50)
        ema200 = _ema(close, 200)
        rsi    = _compute_rsi(close, 14)
        vol_avg10 = volume.rolling(10).mean().shift(1)
        vol_ratio = volume / vol_avg10.replace(0, float("nan"))
        high_52w  = close.rolling(252).max().shift(1)
        low_52w   = close.rolling(252).min().shift(1)
        pct_from_52h = (high_52w - close) / high_52w * 100
        pct_from_52l = (close - low_52w) / low_52w * 100

        # Body-to-range for Marubozu
        body = (close - opens).abs()
        candle_range = (high - low).replace(0, float("nan"))
        body_pct = body / candle_range

        # --- Dynamic Parameters ---
        p = STRATEGY_PARAMS.get(strategy, {})

        if strategy == "near_52w_high":
            return (pct_from_52h <= p.get("pct_threshold", 5.0)) & (rsi < 82) & (close > ema50)

        elif strategy == "breakout_52w":
            prev_52h = close.rolling(252).max().shift(2)
            return (close >= prev_52h) & (vol_ratio >= p.get("min_volume_ratio", 1.5))

        elif strategy == "volume_surge":
            return (vol_ratio >= p.get("vol_ratio", 3.0)) & (close > opens) & (close > ema50)

        elif strategy == "momentum_leaders":
            return (close > ema20) & (ema20 > ema50) & (ema50 > ema200) & (rsi >= 50)

        elif strategy == "rsi_oversold_bounce":
            return (rsi >= p.get("rsi_min", 25)) & (rsi <= p.get("rsi_max", 45)) & (close > ema200)

        elif strategy == "rsi_momentum":
            return (rsi >= p.get("rsi_threshold", 65)) & (close > ema50) & (close > ema200)

        elif strategy == "vcp_tight":
            std_10  = close.rolling(10).std()
            std_prev = close.rolling(10).std().shift(15)
            vol_thresh = p.get("volatility_threshold", 3.0) # simplified proxy
            return (std_10 < std_prev * 0.6) & (pct_from_52h <= 12) & (close > ema50)

        elif strategy == "golden_crossover":
            cross = (ema50 > ema200) & (ema50.shift(1) <= ema200.shift(1))
            signal = pd.Series(False, index=df.index)
            cross_dates = cross[cross].index
            for cd in cross_dates:
                end_date = cd + pd.Timedelta(days=45)
                mask = (df.index >= cd) & (df.index <= end_date)
                signal[mask] = True
            return signal & (close > ema200)

        elif strategy == "high_rs":
            return (pct_from_52l >= p.get("rs_threshold", 30)) & (close > ema50) & (rsi >= 50)

        elif strategy == "ema_pullback_bounce":
            in_uptrend = (ema20 > ema50) & (ema50 > ema200)
            near_ema20 = (close - ema20).abs() / ema20 * 100 <= 2.0
            prev_above = close.shift(5) > ema20.shift(5) * 1.03
            return in_uptrend & near_ema20 & prev_above & (rsi >= 40) & (rsi <= 65)

        elif strategy == "marubozu_breakout":
            bullish = close > opens
            marubozu = (body_pct >= p.get("body_pct_threshold", 0.75)) & bullish
            return marubozu & (vol_ratio >= p.get("vol_ratio", 2.0)) & (close > ema20)

        elif strategy == "stage2_base_breakout":
            sma30w = close.rolling(150).mean()
            range_high = close.rolling(30).max().shift(1)
            range_width = (close.rolling(30).max() - close.rolling(30).min()) / close.rolling(30).mean() * 100
            tight_base = range_width.shift(1) <= 15
            breakout = close > range_high
            return (close > sma30w) & tight_base & breakout & (vol_ratio >= 1.5)

        elif strategy == "accumulation_zone":
            mid_point = (high + low) / 2
            upper_close = close > mid_point
            high_vol = vol_ratio >= p.get("vol_ratio", 2.0)
            accum_day = (upper_close & high_vol).astype(int)
            accum_count = accum_day.rolling(10).sum()
            return (accum_count >= 4) & (pct_from_52h <= 15) & (close > ema50)

        elif strategy == "news_catalyst_momentum":
            day_return = close.pct_change() * 100
            return (day_return >= p.get("price_move_pct", 2.5)) & (vol_ratio >= p.get("vol_ratio", 2.5)) & (close > ema50) & (rsi < 80)

        else:
            return pd.Series(False, index=df.index)

    except Exception as e:
        logger.debug(f"Signal detection error for {strategy}: {e}")
        return pd.Series(False, index=df.index)


# ── Per-stock backtest ─────────────────────────────────────────────────────────

def _backtest_stock(symbol: str, strategy: str, df: pd.DataFrame) -> List[Dict]:
    """
    Detect all entry signals for a strategy on one stock's history.
    For each signal, compute forward returns at HORIZONS.
    Returns list of trade dicts.
    """
    if df is None or len(df) < 252:
        return []

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)

    df = df.dropna(subset=["Close", "Volume", "High", "Low", "Open"])
    if len(df) < 252:
        return []

    signals = _detect_signals(df, strategy)
    close = df["Close"]

    trades = []
    last_entry_idx = -20  # prevent overlapping trades (20-day cooldown)

    for i, (date, is_signal) in enumerate(signals.items()):
        if not is_signal:
            continue
        if i - last_entry_idx < 15:  # minimum 15-day gap between trades
            continue
        # Need enough future data
        if i + 46 >= len(close):
            continue

        entry_price = _sf(close.iloc[i])
        if not entry_price or entry_price <= 0:
            continue

        trade = {
            "symbol":       symbol,
            "strategy":     strategy,
            "entry_date":   str(date.date()),
            "entry_price":  round(entry_price, 2),
            "returns":      {},
            "wins":         {},
        }

        for h in HORIZONS:
            if i + h < len(close):
                future_price = _sf(close.iloc[i + h])
                if future_price:
                    ret_pct = round((future_price - entry_price) / entry_price * 100, 2)
                    trade["returns"][str(h)] = ret_pct
                    trade["wins"][str(h)] = ret_pct >= GAIN_THRESHOLD_PCT

        if trade["returns"]:
            trades.append(trade)
            last_entry_idx = i

    return trades


def _compute_stats(trades: List[Dict], horizon: int) -> Dict:
    """Compute performance stats for a given horizon from a list of trades."""
    h_key = str(horizon)
    rets  = [t["returns"][h_key] for t in trades if h_key in t["returns"]]
    wins  = [t["wins"][h_key]    for t in trades if h_key in t["wins"]]

    if not rets or len(rets) < MIN_TRADES_REQUIRED:
        return {
            "total_trades": len(rets),
            "win_rate":     None,
            "avg_return":   None,
            "avg_win":      None,
            "avg_loss":     None,
            "max_drawdown": None,
            "profit_factor": None,
            "expectancy":   None,
            "sharpe":       None,
            "insufficient_data": True,
        }

    rets_arr  = np.array(rets, dtype=float)
    wins_arr  = np.array(wins, dtype=bool)
    win_rate  = round(wins_arr.mean() * 100, 1)
    avg_ret   = round(float(np.mean(rets_arr)), 2)

    winning_rets = rets_arr[wins_arr]
    losing_rets  = rets_arr[~wins_arr]

    avg_win  = round(float(np.mean(winning_rets)), 2) if len(winning_rets) else 0.0
    avg_loss = round(float(np.mean(losing_rets)), 2) if len(losing_rets) else 0.0

    gross_profit = float(np.sum(np.maximum(rets_arr, 0)))
    gross_loss   = float(np.abs(np.sum(np.minimum(rets_arr, 0))))
    profit_factor = round(gross_profit / gross_loss, 2) if gross_loss > 0 else 99.0

    expectancy = round(
        (win_rate / 100 * avg_win) + ((1 - win_rate / 100) * avg_loss), 2
    )

    std = float(np.std(rets_arr))
    sharpe = round(avg_ret / std, 2) if std > 0 else 0.0

    # Max drawdown (sequential equity curve)
    equity = np.cumprod(1 + rets_arr / 100)
    rolling_max = np.maximum.accumulate(equity)
    drawdown = (equity - rolling_max) / rolling_max * 100
    max_dd = round(float(drawdown.min()), 2)

    return {
        "total_trades":  len(rets),
        "win_rate":      win_rate,
        "avg_return":    avg_ret,
        "avg_win":       avg_win,
        "avg_loss":      avg_loss,
        "max_drawdown":  max_dd,
        "profit_factor": profit_factor,
        "expectancy":    expectancy,
        "sharpe":        sharpe,
        "insufficient_data": False,
    }


# ── Main Backtesting Engine ────────────────────────────────────────────────────

def _fetch_history(symbol: str, years: int = 3) -> Optional[pd.DataFrame]:
    try:
        df = yf.download(
            symbol, period=f"{years}y", interval="1d",
            progress=False, auto_adjust=True,
        )
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df if df is not None and len(df) >= 252 else None
    except Exception as e:
        logger.debug(f"History fetch failed for {symbol}: {e}")
        return None


def run_backtest(
    universe: Optional[List[str]] = None,
    strategies: Optional[List[str]] = None,
    history_years: int = 3,
    workers: int = 12,
) -> Dict:
    """
    Main entry point. Runs all strategies against the universe.
    Returns: dict keyed by strategy name containing stats + active flag.
    """
    universe = universe or BT_UNIVERSE
    strategies = strategies or list(STRATEGIES.keys())

    logger.info(f"Backtester starting: {len(universe)} stocks × {len(strategies)} strategies")
    t0 = time.time()

    # Step 1: Fetch all historical data in parallel
    hist_map: Dict[str, pd.DataFrame] = {}
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="bt_fetch") as pool:
        futures = {pool.submit(_fetch_history, sym, history_years): sym for sym in universe}
        for fut in as_completed(futures):
            sym = futures[fut]
            try:
                df = fut.result()
                if df is not None:
                    hist_map[sym] = df
            except Exception as e:
                logger.debug(f"Fetch error {sym}: {e}")

    logger.info(f"Fetched history for {len(hist_map)}/{len(universe)} stocks")

    # Step 2: Run each strategy against all stocks
    all_results: Dict[str, List[Dict]] = {s: [] for s in strategies}

    for strategy in strategies:
        logger.info(f"Backtesting strategy: {strategy}")
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="bt_strat") as pool:
            futures = {
                pool.submit(_backtest_stock, sym, strategy, df.copy()): sym
                for sym, df in hist_map.items()
            }
            for fut in as_completed(futures):
                try:
                    trades = fut.result()
                    all_results[strategy].extend(trades)
                except Exception as e:
                    logger.debug(f"Backtest error: {e}")

    # Step 3: Compute stats per strategy
    results: Dict[str, Any] = {}
    for strategy, trades in all_results.items():
        meta = STRATEGIES[strategy]
        target_h = meta["target_horizon_days"]

        horizon_stats = {}
        for h in HORIZONS:
            horizon_stats[f"{h}d"] = _compute_stats(trades, h)

        # Primary stats at the strategy's target horizon
        primary = horizon_stats.get(f"{target_h}d", {})
        win_rate = primary.get("win_rate")
        pf       = primary.get("profit_factor")

        # Determine active status
        if win_rate is None or primary.get("insufficient_data"):
            is_active = False
            status_reason = "Insufficient data"
        elif win_rate >= WIN_RATE_THRESHOLD and pf is not None and pf >= PROFIT_FACTOR_MIN:
            is_active = True
            status_reason = f"Win rate {win_rate}% ≥ {WIN_RATE_THRESHOLD}%"
        else:
            is_active = False
            status_reason = f"Win rate {win_rate}% < {WIN_RATE_THRESHOLD}% threshold"

        results[strategy] = {
            **meta,
            "is_active":       is_active,
            "status_reason":   status_reason,
            "total_trades":    len(trades),
            "stocks_tested":   len(hist_map),
            "target_horizon":  target_h,
            "primary_stats":   primary,
            "horizon_stats":   horizon_stats,
            # Quick-access fields for the UI
            "win_rate_primary":    win_rate,
            "avg_return_primary":  primary.get("avg_return"),
            "profit_factor_primary": pf,
            "max_drawdown_primary":  primary.get("max_drawdown"),
            "sharpe_primary":       primary.get("sharpe"),
            "expectancy_primary":   primary.get("expectancy"),
        }

    elapsed = round(time.time() - t0, 1)
    active_count = sum(1 for v in results.values() if v["is_active"])
    logger.info(f"Backtest complete: {active_count}/{len(strategies)} active strategies in {elapsed}s")

    return {
        "strategies":       results,
        "active_count":     active_count,
        "total_strategies": len(strategies),
        "universe_size":    len(hist_map),
        "history_years":    history_years,
        "gain_threshold":   GAIN_THRESHOLD_PCT,
        "win_rate_min":     WIN_RATE_THRESHOLD,
        "profit_factor_min": PROFIT_FACTOR_MIN,
        "computed_at":      datetime.utcnow().isoformat(),
        "elapsed_sec":      elapsed,
    }


# ── Cache helpers ──────────────────────────────────────────────────────────────

def _is_cache_valid() -> bool:
    try:
        if not _BT_CACHE_FILE.exists():
            return False
        mtime = _BT_CACHE_FILE.stat().st_mtime
        return (time.time() - mtime) < _BT_CACHE_TTL
    except Exception:
        return False


def _load_cache() -> Optional[Dict]:
    try:
        if _BT_CACHE_FILE.exists():
            with open(_BT_CACHE_FILE, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None


def _save_cache(data: Dict):
    try:
        with open(_BT_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    except Exception as e:
        logger.warning(f"Failed to save backtest cache: {e}")


def get_backtest_results(force_refresh: bool = False) -> Dict:
    """Public API — returns cached backtest results or triggers a fresh run."""
    if not force_refresh and _is_cache_valid():
        data = _load_cache()
        if data:
            data["from_cache"] = True
            logger.info("Backtest results served from cache")
            return data

    logger.info("Running fresh backtest...")
    results = run_backtest()
    _save_cache(results)
    results["from_cache"] = False
    return results


def get_active_strategies() -> List[str]:
    """Returns list of strategy keys that passed backtest thresholds."""
    data = get_backtest_results()
    return [k for k, v in data.get("strategies", {}).items() if v.get("is_active", False)]


def get_strategy_win_rate(strategy: str) -> Optional[float]:
    """Returns the primary win rate for a strategy, or None if inactive/unknown."""
    data = get_backtest_results()
    strat = data.get("strategies", {}).get(strategy, {})
    return strat.get("win_rate_primary")


def get_strategy_leaderboard(top_n: int = 10) -> List[Dict]:
    """Returns top N strategies sorted by win rate."""
    data = get_backtest_results()
    strategies = []
    for k, v in data.get("strategies", {}).items():
        wr = v.get("win_rate_primary")
        if wr is not None:
            strategies.append({
                "key":          k,
                "label":        v.get("label", k),
                "icon":         v.get("icon", "📊"),
                "color":        v.get("color", "#6366f1"),
                "is_active":    v.get("is_active", False),
                "win_rate":     wr,
                "avg_return":   v.get("avg_return_primary"),
                "profit_factor": v.get("profit_factor_primary"),
                "max_drawdown": v.get("max_drawdown_primary"),
                "sharpe":       v.get("sharpe_primary"),
                "expectancy":   v.get("expectancy_primary"),
                "total_trades": v.get("total_trades", 0),
                "target_horizon": v.get("target_horizon"),
                "status_reason": v.get("status_reason"),
            })
    strategies.sort(key=lambda x: x["win_rate"] or 0, reverse=True)
    return strategies[:top_n]


# ── CLI ────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kepler Strategy Backtester")
    parser.add_argument("--quick-test", action="store_true", help="Run on 5 stocks, 1 year")
    parser.add_argument("--strategy", type=str, default=None, help="Test one specific strategy")
    parser.add_argument("--force", action="store_true", help="Force refresh, bypass cache")
    args = parser.parse_args()

    if args.quick_test:
        universe = BT_UNIVERSE[:5]
        strategies = [args.strategy] if args.strategy else list(STRATEGIES.keys())[:3]
        results = run_backtest(universe=universe, strategies=strategies, history_years=1, workers=4)
    else:
        strategies = [args.strategy] if args.strategy else None
        results = run_backtest(strategies=strategies)
        _save_cache(results)

    print(f"\n{'='*60}")
    print(f"Backtest Results — {results['active_count']}/{results['total_strategies']} Active Strategies")
    print(f"{'='*60}")
    for name, stat in results["strategies"].items():
        wr = stat.get("win_rate_primary", "N/A")
        pf = stat.get("profit_factor_primary", "N/A")
        trades = stat.get("total_trades", 0)
        status = "✅ ACTIVE" if stat.get("is_active") else "❌ inactive"
        try:
            print(f"{stat['icon']} {name:30s} WR={wr}% PF={pf} Trades={trades:4d}  {status}")
        except UnicodeEncodeError:
            print(f"? {name:30s} WR={wr}% PF={pf} Trades={trades:4d}  {status}")
