"""
nautilus_strategy.data_loader
==============================
Convert yfinance OHLCV history into NautilusTrader Bar objects.

The same yfinance data source is used by ml_features.generate_labels() and
expectancy.py, so bar-by-bar prices seen by KeplerStrategy match exactly the
prices the custom backtester evaluated.

Public API
----------
    load_holdout_bars(symbols, period, max_workers)
        → dict[symbol_str, pd.DataFrame]          (raw OHLCV)

    ohlcv_to_nt_bars(symbol, ohlcv_df, venue)
        → list[nautilus_trader.model.data.Bar]     (NT Bar objects)

    load_instrument(symbol, venue, currency)
        → nautilus_trader.model.instruments.Equity

Design notes
------------
- NSE equities trade in INR, whole rupees (price_precision=2),
  whole shares (size_precision=0).
- All timestamps are converted to UTC nanoseconds (NT requires int64 nanos).
- Bars are typed DAILY / EXTERNAL — the strategy receives them as-is from
  the engine, not aggregated from ticks.
- If a symbol has < 60 rows of history it is skipped (matches generate_labels).
"""
from __future__ import annotations

import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yfinance as yf
from loguru import logger

warnings.filterwarnings("ignore", category=FutureWarning)


# ── yfinance download ─────────────────────────────────────────────────────────

def load_holdout_bars(
    symbols: List[str],
    period: str = "8y",
    max_workers: int = 8,
) -> Dict[str, pd.DataFrame]:
    """
    Download OHLCV history for a list of NSE symbols (bare ticker without .NS).

    Returns a dict {symbol: ohlcv_df} for symbols that returned >= 60 rows.
    Mirrors the yfinance call inside ml_features.generate_labels() exactly:
        period=period, interval="1d", auto_adjust=True

    Parameters
    ----------
    symbols : list[str]
        NSE tickers without .NS suffix (e.g. "RELIANCE").
    period : str
        yfinance period string, default "8y" (matches expectancy.py).
    max_workers : int
        Thread-pool size for parallel downloads.

    Returns
    -------
    dict[str, pd.DataFrame]
        Keyed by bare symbol (no .NS).  DataFrame has columns:
        Open, High, Low, Close, Volume with DatetimeIndex (UTC).
    """
    logger.info(f"📥 Downloading {len(symbols)} symbols from yfinance (period={period})…")
    result: Dict[str, pd.DataFrame] = {}

    def _fetch(sym: str) -> Optional[tuple]:
        ticker_sym = sym if sym.endswith(".NS") else f"{sym}.NS"
        try:
            df = yf.Ticker(ticker_sym).history(
                period=period, interval="1d", auto_adjust=True
            ).dropna(subset=["Close"])
            if len(df) < 60:
                logger.debug(f"  {sym}: only {len(df)} rows — skipping")
                return None
            df.index = pd.DatetimeIndex(df.index).tz_localize(None).tz_localize("UTC")
            return sym, df[["Open", "High", "Low", "Close", "Volume"]]
        except Exception as e:
            logger.debug(f"  {sym}: fetch error — {e}")
            return None

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_fetch, s): s for s in symbols}
        for i, fut in enumerate(as_completed(futures), 1):
            r = fut.result()
            if r is not None:
                sym, df = r
                result[sym] = df
            if i % 10 == 0:
                logger.info(f"  [{i}/{len(symbols)}] fetched")

    logger.info(f"✅ {len(result)}/{len(symbols)} symbols ready ({period} history)")
    return result


# ── OHLCV → NT Bars ──────────────────────────────────────────────────────────

def ohlcv_to_nt_bars(
    symbol: str,
    ohlcv_df: pd.DataFrame,
    venue: str = "NSE",
) -> list:
    """
    Convert a yfinance OHLCV DataFrame into a list of NautilusTrader Bar objects.

    Parameters
    ----------
    symbol : str
        Bare NSE ticker (no .NS), e.g. "RELIANCE".
    ohlcv_df : pd.DataFrame
        UTC-indexed DataFrame with columns Open/High/Low/Close/Volume.
    venue : str
        Venue identifier string (default "NSE").

    Returns
    -------
    list[Bar]
        NT Bar objects sorted by ts_init ascending.
    """
    from nautilus_trader.model.data import Bar, BarSpecification, BarType
    from nautilus_trader.model.enums import AggregationSource, BarAggregation, PriceType
    from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
    from nautilus_trader.model.objects import Price, Quantity

    instrument_id = InstrumentId(Symbol(symbol), Venue(venue))
    bar_spec = BarSpecification(1, BarAggregation.DAY, PriceType.LAST)
    bar_type = BarType(instrument_id, bar_spec, AggregationSource.EXTERNAL)

    bars = []
    for ts, row in ohlcv_df.iterrows():
        # ts_event: timestamp of the bar's close (UTC nanos)
        ts_ns = int(pd.Timestamp(ts).value)  # already in nanos

        bar = Bar(
            bar_type=bar_type,
            open=Price(float(row["Open"]),   precision=2),
            high=Price(float(row["High"]),   precision=2),
            low=Price(float(row["Low"]),     precision=2),
            close=Price(float(row["Close"]), precision=2),
            volume=Quantity(max(float(row["Volume"]), 0.0), precision=0),
            ts_event=ts_ns,
            ts_init=ts_ns,
        )
        bars.append(bar)

    return bars


# ── NT Equity instrument factory ──────────────────────────────────────────────

def load_instrument(
    symbol: str,
    venue: str = "NSE",
    currency: str = "INR",
):
    """
    Build a minimal NautilusTrader Equity instrument for an NSE stock.

    NSE equities:
        price_precision = 2  (rupees to paisa, i.e. 2 decimal places)
        size_precision  = 0  (whole shares only)
        lot_size        = 1  (delivery equity — no minimum lot)
        multiplier      = 1

    Parameters
    ----------
    symbol : str
        Bare NSE ticker (no .NS), e.g. "RELIANCE".
    venue : str
        Venue string (default "NSE").
    currency : str
        Quote currency (default "INR").

    Returns
    -------
    nautilus_trader.model.instruments.Equity
    """
    from nautilus_trader.model.currencies import Currency
    from nautilus_trader.model.identifiers import InstrumentId, Symbol, Venue
    from nautilus_trader.model.instruments import Equity
    from nautilus_trader.model.objects import Price, Quantity

    instrument_id = InstrumentId(Symbol(symbol), Venue(venue))
    inr = Currency.from_str(currency)

    return Equity(
        instrument_id=instrument_id,
        raw_symbol=Symbol(symbol),
        currency=inr,
        price_precision=2,
        price_increment=Price(0.01, precision=2),
        lot_size=Quantity(1, precision=0),
        ts_event=0,
        ts_init=0,
    )
