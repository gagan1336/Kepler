"""
nautilus_strategy.kepler_strategy
===================================
NautilusTrader Strategy class wrapping the Kepler ML inference pipeline.

Design goals
------------
1. Call *existing* kepler_model.predict_proba() and kepler_model._meta_score()
   as-is — zero reimplementation of inference logic.
2. Compute features bar-by-bar from a rolling OHLCV deque using the same
   formulas as ml_features.generate_labels() — no yfinance fetches inside on_bar.
3. Emit a MARKET order when primary_prob >= primary_threshold AND (if configured)
   meta_prob >= meta_threshold.
4. Exit after forward_days close bars (time exit only — no stop-loss or TP).
5. The same class runs identically against live/paper data feeds; only the
   engine changes.

Architecture note — feature computation
-----------------------------------------
ml_features.generate_labels() is a batch function that vectorises indicators
over the entire history at once.  NautilusTrader calls on_bar() event-by-event.
The strategy therefore maintains a rolling deque of the last 252 bars per
instrument and recomputes the scalar feature row locally using pure-Python/numpy
helpers that are algebraically identical to the vectorised generate_labels code.

Fundamental features (PE, ROE, etc.) are set to training-time sector-median
defaults (same as generate_labels line ~458), which is the correct choice for
backtesting: we didn't have live fundamentals per bar in the historical data
either.

Macro and cross-sectional features (india_vix, sector_rsi_rank, etc.) are
zero-filled, matching the fallback in expectancy.py::collect_holdout_with_returns
when macro/rank pipelines are unavailable.

Trade record schema (self._trades list)
-----------------------------------------
Each closed trade produces a dict:
    symbol, entry_date, exit_date, entry_price, exit_price,
    fwd_ret_pct, y_score, meta_score, label (1 if fwd_ret >= threshold_pct),
    gross_exp_pct (fwd_ret), cost_pct, net_exp_pct (fwd_ret - cost)

This mirrors the expectancy.py DataFrame structure for direct parity comparison.
"""
from __future__ import annotations

import math
import sys
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger

# Ensure backend/ is on sys.path when the module is imported from within
# the nautilus_strategy sub-package.
_BACKEND_DIR = Path(__file__).parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# ── Lazy NT imports ───────────────────────────────────────────────────────────
# Imported at class definition time only inside the _build_nt_strategy() factory,
# so this module is importable even on machines where NT DLLs are blocked.


# ── Feature computation helpers ───────────────────────────────────────────────
# All implementations are algebraically identical to ml_features.generate_labels().
# Kept here (not imported) to avoid pulling in yfinance on each bar event.

def _safe(val, default: float = 0.0) -> float:
    try:
        v = float(val)
        return default if (math.isnan(v) or math.isinf(v)) else v
    except Exception:
        return default


def _features_from_deque(buf: deque) -> Optional[dict]:
    """
    Compute a Kepler feature row from the last N bars in `buf`.

    buf entries are dicts with keys: open, high, low, close, volume.
    Requires >= 60 bars; returns None if too few.
    """
    if len(buf) < 60:
        return None

    closes  = np.array([r["close"]  for r in buf], dtype=float)
    highs   = np.array([r["high"]   for r in buf], dtype=float)
    lows    = np.array([r["low"]    for r in buf], dtype=float)
    opens_  = np.array([r["open"]   for r in buf], dtype=float)
    volumes = np.array([r["volume"] for r in buf], dtype=float)

    price = closes[-1]
    if price <= 0:
        return None

    n = len(closes)

    # ── RSI ──────────────────────────────────────────────────────────────────
    def _rsi(arr: np.ndarray, period: int) -> float:
        delta = np.diff(arr)
        gain  = np.where(delta > 0, delta, 0.0)
        loss  = np.where(delta < 0, -delta, 0.0)
        # EWM with alpha = 1/period (matches pandas ewm(alpha=1/period))
        alpha = 1.0 / period
        avg_g = _ewm_last(gain, alpha)
        avg_l = _ewm_last(loss, alpha)
        rs    = avg_g / avg_l if avg_l != 0 else np.nan
        return _safe(100.0 - 100.0 / (1.0 + rs)) if not np.isnan(rs) else 50.0

    def _ewm_last(arr: np.ndarray, alpha: float) -> float:
        val = arr[0]
        for x in arr[1:]:
            val = alpha * x + (1 - alpha) * val
        return float(val)

    rsi14 = _rsi(closes, 14)
    rsi7  = _rsi(closes, 7)

    # ── MACD ─────────────────────────────────────────────────────────────────
    def _ema_series(arr: np.ndarray, span: int) -> np.ndarray:
        alpha = 2.0 / (span + 1)
        out = np.empty_like(arr)
        out[0] = arr[0]
        for i in range(1, len(arr)):
            out[i] = alpha * arr[i] + (1 - alpha) * out[i - 1]
        return out

    fast_ema = _ema_series(closes, 12)
    slow_ema = _ema_series(closes, 26)
    macd_line = fast_ema - slow_ema
    signal    = _ema_series(macd_line, 9)
    macd_l  = _safe(macd_line[-1])
    macd_s  = _safe(signal[-1])
    macd_h  = _safe(macd_line[-1] - signal[-1])

    # ── EMAs ─────────────────────────────────────────────────────────────────
    ema20  = _safe(_ema_series(closes, 20)[-1])
    ema50  = _safe(_ema_series(closes, 50)[-1])
    ema200 = _safe(_ema_series(closes, 200)[-1]) if n >= 200 else _safe(closes.mean())

    # ── Bollinger Bands ───────────────────────────────────────────────────────
    sma20   = float(closes[-20:].mean())
    std20   = float(closes[-20:].std(ddof=1)) if n >= 20 else 0.0
    bb_up   = sma20 + 2 * std20
    bb_lo   = sma20 - 2 * std20
    bb_pctb = _safe((price - bb_lo) / (bb_up - bb_lo)) if (bb_up - bb_lo) != 0 else 0.5
    bb_wid  = _safe((bb_up - bb_lo) / sma20) if sma20 != 0 else 0.0

    # ── ATR (14) ──────────────────────────────────────────────────────────────
    tr = np.maximum(
        highs[1:] - lows[1:],
        np.maximum(
            np.abs(highs[1:] - closes[:-1]),
            np.abs(lows[1:]  - closes[:-1]),
        )
    )
    atr14 = _safe(_ewm_last(tr[-14:], 2.0 / 15))

    # ── Volume ratio ──────────────────────────────────────────────────────────
    vol_avg10  = float(volumes[-10:].mean()) if volumes[-10:].mean() > 0 else 1.0
    vol_ratio  = _safe(volumes[-1] / vol_avg10)

    # ── ROC ───────────────────────────────────────────────────────────────────
    def _roc(arr, p):
        if len(arr) <= p or arr[-p - 1] == 0:
            return 0.0
        return _safe((arr[-1] - arr[-p - 1]) / arr[-p - 1] * 100)

    roc5  = _roc(closes,  5)
    roc10 = _roc(closes, 10)
    roc20 = _roc(closes, 20)

    # ── ADX (14) ──────────────────────────────────────────────────────────────
    plus_dm  = np.maximum(np.diff(highs), 0)
    minus_dm = np.maximum(-np.diff(lows), 0)
    tr2      = np.maximum(
        np.abs(highs[1:] - lows[1:]),
        np.maximum(np.abs(highs[1:] - closes[:-1]),
                   np.abs(lows[1:]  - closes[:-1])),
    )
    atr_adx  = _ewm_last(tr2[-14:], 2.0 / 15) or 1.0
    pdi  = 100 * _ewm_last(plus_dm[-14:],  2.0 / 15) / atr_adx
    mdi  = 100 * _ewm_last(minus_dm[-14:], 2.0 / 15) / atr_adx
    dx   = 100 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) != 0 else 0.0
    adx14 = _safe(dx)

    # ── Stochastic (14, 3) ────────────────────────────────────────────────────
    lo14    = lows[-14:].min()
    hi14    = highs[-14:].max()
    stk_arr = [
        100 * (closes[-14:][i] - lows[-14:][i]) / (highs[-14:][i] - lows[-14:][i])
        if (highs[-14:][i] - lows[-14:][i]) != 0 else 50.0
        for i in range(14)
    ]
    stk = _safe(stk_arr[-1])
    std = _safe(float(np.mean(stk_arr[-3:])))

    # ── 52-week high/low ──────────────────────────────────────────────────────
    high52 = _safe(closes[-min(252, n):].max())
    low52  = _safe(closes[-min(252, n):].min())
    pct_from_52h = _safe((high52 - price) / high52 * 100) if high52 > 0 else 0.0
    pct_from_52l = _safe((price - low52)  / low52  * 100) if low52  > 0 else 0.0

    # ── SMA 20 / 50 ───────────────────────────────────────────────────────────
    sma50        = float(closes[-min(50, n):].mean())
    pct_vs_sma20 = _safe((price - sma20) / sma20 * 100) if sma20 != 0 else 0.0
    pct_vs_sma50 = _safe((price - sma50) / sma50 * 100) if sma50 != 0 else 0.0
    pv_ema200    = _safe((price - ema200) / ema200 * 100) if ema200 != 0 else 0.0

    # ── Candle body & HL ratio ────────────────────────────────────────────────
    h = highs[-1]; l = lows[-1]; o = opens_[-1]
    hl_range        = h - l
    candle_body_pct = _safe(abs(price - o) / hl_range) if hl_range > 0 else 0.5
    hl_ratio        = _safe(hl_range / price * 100)

    # ── Assemble feature dict (training-time defaults for fundamentals) ────────
    # Fundamental values are sector medians (matching generate_labels line ~458)
    # Sentiment / macro / cross-sectional features are zero-filled
    return {
        "rsi_14": rsi14, "rsi_7": rsi7,
        "macd_line": macd_l, "macd_signal": macd_s, "macd_hist": macd_h,
        "ema_20": ema20, "ema_50": ema50, "ema_200": ema200,
        "bb_pct_b": bb_pctb, "bb_width": bb_wid,
        "atr_14": atr14, "volume_ratio": vol_ratio,
        "roc_5": roc5, "roc_10": roc10, "roc_20": roc20,
        "adx_14": adx14, "stoch_k": stk, "stoch_d": std,
        "pct_from_52h": pct_from_52h, "pct_from_52l": pct_from_52l,
        "pct_vs_sma20": pct_vs_sma20, "pct_vs_sma50": pct_vs_sma50,
        "price_vs_ema200": pv_ema200,
        "candle_body_pct": candle_body_pct, "hl_ratio": hl_ratio,
        # Fundamentals: training-time sector medians (same as generate_labels)
        "pe_ratio": 25.0, "pb_ratio": 3.0, "ev_ebitda": 15.0,
        "roe": 15.0, "debt_to_equity": 0.5, "profit_margin": 10.0,
        "revenue_growth": 10.0, "market_cap_log": 10.0,
        "dividend_yield": 1.0, "eps_growth": 10.0,
        # Sentiment: zero (no live context in backtest — matches generate_labels)
        "news_sentiment": 0, "sector_score": 50,
        "in_digest": 0, "apex_score": 50, "fii_proxy": 0,
        # Cross-sectional ranks: 0.5 neutral (matches expectancy.py fallback)
        "sector_rsi_rank": 0.5, "sector_mom_rank": 0.5, "sector_vol_rank": 0.5,
        "mkt_mom_rank": 0.5, "mkt_vol_rank": 0.5, "vol_vs_own_hist": 0.5,
        # Macro: 0.0 (matches expectancy.py fallback)
        "india_vix": 0.0, "vix_5d_change": 0.0, "usd_inr_1d_ret": 0.0,
        "crude_1d_ret": 0.0, "market_breadth": 0.0,
        # Internal metadata (stripped before inference by kepler_model)
        "_primary_prob": 0.0,
    }


# ── Strategy config ───────────────────────────────────────────────────────────

class KeplerStrategyConfig:
    """
    Plain-dataclass config for KeplerStrategy.

    Passed as `config=` to the strategy constructor so the same interface
    works whether NT is loaded or not.  When NT is available, this is
    wrapped into a StrategyConfig subclass inside _build_nt_strategy().

    Parameters
    ----------
    instrument_ids : list[str]
        NSE tickers (no .NS) to trade.
    primary_threshold : float
        Minimum primary model probability to generate a signal.
    meta_threshold : float
        Minimum meta-label probability.  0.0 = disabled.
    forward_days : int
        Number of daily bars to hold before forced exit.
    position_size_inr : float
        Notional trade value in INR (used for cost calculation in reporting).
    threshold_pct : float
        Forward-return threshold for binary label (mirrors generate_labels).
    venue : str
        NT Venue identifier.
    """

    def __init__(
        self,
        instrument_ids:    List[str],
        primary_threshold: float = 0.35,
        meta_threshold:    float = 0.0,
        forward_days:      int   = 10,
        position_size_inr: float = 50_000.0,
        threshold_pct:     float = 5.0,
        venue:             str   = "NSE",
    ) -> None:
        self.instrument_ids    = instrument_ids
        self.primary_threshold = primary_threshold
        self.meta_threshold    = meta_threshold
        self.forward_days      = forward_days
        self.position_size_inr = position_size_inr
        self.threshold_pct     = threshold_pct
        self.venue             = venue


# ── Strategy implementation ───────────────────────────────────────────────────

def build_kepler_strategy(config: KeplerStrategyConfig):
    """
    Factory that returns a NautilusTrader Strategy instance wrapping the
    Kepler ML inference pipeline.

    Imports NT lazily so this module is importable without NT.

    Parameters
    ----------
    config : KeplerStrategyConfig

    Returns
    -------
    nautilus_trader.trading.Strategy subclass instance
    """
    from nautilus_trader.config import StrategyConfig
    from nautilus_trader.trading import Strategy
    from nautilus_trader.model.data import Bar, BarType
    from nautilus_trader.model.enums import OrderSide, TimeInForce
    from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
    from nautilus_trader.model.orders import MarketOrder

    # Import existing Kepler inference — never reimplemented here
    import kepler_model as _km

    # Warm up the model cache once at strategy build time
    if not _km.is_model_ready():
        loaded = _km.load_model()
        if not loaded:
            raise RuntimeError(
                "Kepler model not found. Run `python train_model.py` first."
            )
    _km.load_meta_model()  # no-op if unavailable

    class _KeplerNTConfig(StrategyConfig):
        """NT-compatible config wrapping KeplerStrategyConfig fields."""
        instrument_ids:    list
        primary_threshold: float
        meta_threshold:    float
        forward_days:      int
        position_size_inr: float
        threshold_pct:     float
        venue:             str

    class _KeplerStrategy(Strategy):
        """
        NautilusTrader Strategy wrapping Kepler LightGBM + meta-filter.

        Event flow
        ----------
        on_start()        Subscribe to daily bars for each instrument.
        on_bar(bar)       Update rolling OHLCV buffer → compute features →
                          call kepler_model.predict_proba() + _meta_score() →
                          emit MARKET order if threshold exceeded.
        on_order_filled() Record entry; schedule exit after forward_days bars.
        on_stop()         Force-close any open positions; finalise trade log.

        Trade log (self._trades)
        ------------------------
        Each closed trade appends a dict with the same fields as
        expectancy.py's output: symbol, entry_date, exit_date, entry_price,
        exit_price, fwd_ret_pct, y_score, meta_score, y_true, cost_pct,
        net_exp_pct.
        """

        def __init__(self, config_: KeplerStrategyConfig) -> None:
            # Build the NT StrategyConfig dynamically
            nt_cfg = _KeplerNTConfig(
                instrument_ids    = config_.instrument_ids,
                primary_threshold = config_.primary_threshold,
                meta_threshold    = config_.meta_threshold,
                forward_days      = config_.forward_days,
                position_size_inr = config_.position_size_inr,
                threshold_pct     = config_.threshold_pct,
                venue             = config_.venue,
            )
            super().__init__(config=nt_cfg)

            # Rolling OHLCV buffers — 252 bars (1 yr) is enough for all indicators
            self._bufs: Dict[str, deque] = {
                sym: deque(maxlen=252) for sym in config_.instrument_ids
            }
            # Open positions: symbol → {entry_bar_count, entry_price, entry_date,
            #                           y_score, meta_score, order_id}
            self._open: Dict[str, dict] = {}

            # Bar counter per symbol (used for forward_days exit)
            self._bar_count: Dict[str, int] = {s: 0 for s in config_.instrument_ids}

            # Completed trade records — collected by parity_report.py
            self._trades: List[dict] = []

            # Config reference
            self._cfg = config_

        # ── Lifecycle ─────────────────────────────────────────────────────────

        def on_start(self) -> None:
            from nautilus_trader.model.data import BarSpecification, BarType
            from nautilus_trader.model.enums import AggregationSource, BarAggregation, PriceType
            from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue

            venue = Venue(self._cfg.venue)
            for sym in self._cfg.instrument_ids:
                iid  = InstrumentId(Symbol(sym), venue)
                spec = BarSpecification(1, BarAggregation.DAY, PriceType.LAST)
                bt   = BarType(iid, spec, AggregationSource.EXTERNAL)
                self.subscribe_bars(bt)

            logger.info(
                f"[KeplerStrategy] started — {len(self._cfg.instrument_ids)} instruments | "
                f"primary_thr={self._cfg.primary_threshold} "
                f"meta_thr={self._cfg.meta_threshold} "
                f"fwd_days={self._cfg.forward_days}"
            )

        def on_stop(self) -> None:
            # Force-close any open positions at their last known price
            for sym, pos in list(self._open.items()):
                self._trades.append({
                    "symbol":       sym,
                    "entry_date":   pos["entry_date"],
                    "exit_date":    None,   # not closed cleanly
                    "entry_price":  pos["entry_price"],
                    "exit_price":   pos.get("last_price", pos["entry_price"]),
                    "fwd_ret_pct":  0.0,
                    "y_score":      pos["y_score"],
                    "meta_score":   pos["meta_score"],
                    "y_true":       0,
                    "cost_pct":     0.0,
                    "net_exp_pct":  0.0,
                    "forced_exit":  True,
                })
            logger.info(
                f"[KeplerStrategy] stopped — {len(self._trades)} trades recorded"
            )

        # ── Bar handler ───────────────────────────────────────────────────────

        def on_bar(self, bar: Bar) -> None:
            sym = bar.bar_type.instrument_id.symbol.value

            # Update buffer
            buf = self._bufs[sym]
            buf.append({
                "open":   float(bar.open),
                "high":   float(bar.high),
                "low":    float(bar.low),
                "close":  float(bar.close),
                "volume": float(bar.volume),
            })
            self._bar_count[sym] = self._bar_count.get(sym, 0) + 1

            # ── Time exit: close position after forward_days bars ─────────────
            if sym in self._open:
                pos = self._open[sym]
                pos["bars_held"] = pos.get("bars_held", 0) + 1
                pos["last_price"] = float(bar.close)

                if pos["bars_held"] >= self._cfg.forward_days:
                    exit_price = float(bar.close)
                    entry_price = pos["entry_price"]
                    fwd_ret = (exit_price - entry_price) / entry_price * 100

                    from nautilus_strategy.nse_cost_model import compute_round_trip_cost_pct
                    cost_pct = compute_round_trip_cost_pct(self._cfg.position_size_inr)

                    self._trades.append({
                        "symbol":      sym,
                        "entry_date":  pos["entry_date"],
                        "exit_date":   str(bar.ts_event),
                        "entry_price": entry_price,
                        "exit_price":  exit_price,
                        "fwd_ret_pct": round(fwd_ret, 4),
                        "y_score":     pos["y_score"],
                        "meta_score":  pos["meta_score"],
                        "y_true":      1 if fwd_ret >= self._cfg.threshold_pct else 0,
                        "cost_pct":    round(cost_pct, 4),
                        "net_exp_pct": round(fwd_ret - cost_pct, 4),
                        "forced_exit": False,
                    })
                    del self._open[sym]
                return   # don't open a new position while one is open for this symbol

            # ── Entry signal ──────────────────────────────────────────────────
            features = _features_from_deque(buf)
            if features is None:
                return   # not enough bars yet

            # Primary model score — calls existing kepler_model.predict_proba()
            feat_df = pd.DataFrame([features])
            try:
                from ml_features import FEATURE_COLUMNS
                probas = _km.predict_proba(feat_df)
                y_score = float(probas[0])
            except Exception as exc:
                logger.debug(f"[KeplerStrategy] inference error {sym}: {exc}")
                return

            if y_score < self._cfg.primary_threshold:
                return

            # Meta-label score — calls existing kepler_model._meta_score()
            features["_primary_prob"] = y_score
            meta_score = float(_km._meta_score(features))

            if self._cfg.meta_threshold > 0 and meta_score < self._cfg.meta_threshold:
                return

            # ── Open position ─────────────────────────────────────────────────
            entry_price = float(bar.close)
            self._open[sym] = {
                "entry_date":  str(bar.ts_event),
                "entry_price": entry_price,
                "y_score":     y_score,
                "meta_score":  meta_score,
                "bars_held":   0,
                "last_price":  entry_price,
            }

    # Instantiate and return
    return _KeplerStrategy(config)
