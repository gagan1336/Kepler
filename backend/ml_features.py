"""
KEPLER — ML Feature Engineering Engine
Computes a 40-feature vector per NSE stock:
  - 25 Technical indicators (RSI, MACD, EMA, ATR, Bollinger, Volume, etc.)
  - 10 Fundamental metrics (PE, ROE, DE, growth, margins, etc.)
  -  5 Sentiment/context features (news, sector, APEX score)

All features are NaN-safe and normalised to comparable scales.

Also defines CalibratedXGBModel here (not in train_model.py) so the class
pickles with module='ml_features' and can always be deserialised correctly,
regardless of whether train_model.py was run as __main__ or imported.
"""
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf
from loguru import logger

# ── Feature column order (must match training) ─────────────────────────────────
FEATURE_COLUMNS = [
    # Technical (25)
    "rsi_14", "rsi_7",
    "macd_line", "macd_signal", "macd_hist",
    "ema_20", "ema_50", "ema_200",
    "bb_pct_b", "bb_width",
    "atr_14",
    "volume_ratio",
    "roc_5", "roc_10", "roc_20",
    "adx_14",
    "stoch_k", "stoch_d",
    "pct_from_52h", "pct_from_52l",
    "pct_vs_sma20", "pct_vs_sma50",
    "price_vs_ema200",
    "candle_body_pct",
    "hl_ratio",
    # Fundamental (10)
    "pe_ratio", "pb_ratio", "ev_ebitda",
    "roe", "debt_to_equity",
    "profit_margin", "revenue_growth",
    "market_cap_log",
    "dividend_yield",
    "eps_growth",
    # Sentiment (5)
    "news_sentiment",
    "sector_score",
    "in_digest",
    "apex_score",
    "fii_proxy",
    # ── Phase C-r: Cross-sectional rank features (6) ──────────────────────────
    # All in [0,1] — computed across peers on the same date.
    # Zero-filled at inference time if rank cache unavailable.
    "sector_rsi_rank",      # RSI percentile within sector
    "sector_mom_rank",      # 20d momentum percentile within sector
    "sector_vol_rank",      # 1 - volatility rank (higher = calmer than peers)
    "mkt_mom_rank",         # 20d momentum percentile vs full universe
    "mkt_vol_rank",         # 1 - volatility rank vs full universe
    "vol_vs_own_hist",      # today's volume vs own 60-bar rolling percentile
    # ── Phase C-r: Macro / regime features (5) ───────────────────────────────
    # Orthogonal to price — information the OHLCV model cannot infer alone.
    "india_vix",            # India VIX level (fear gauge)
    "vix_5d_change",        # VIX 5-day change (regime shift indicator)
    "usd_inr_1d_ret",       # INR daily return (proxy for FII flows)
    "crude_1d_ret",         # Brent crude daily return
    "market_breadth",       # % Nifty200 stocks above 20d SMA
    # ── Phase D: Order Flow / Smart Money Concepts (13) ──────────────────────
    # Closed-bar only — no lookahead.  See order_flow.py for definitions.
    "bias_daily",           # 0=bearish, 1=ranging, 2=bullish (BOS/CHoCH)
    "ob_dist_above_atr",    # ATR-normalised dist to nearest unmitigated OB above
    "ob_dist_below_atr",    # ATR-normalised dist to nearest unmitigated OB below
    "ob_inside_flag",       # 1 if price is inside any unmitigated order block
    "fvg_size_atr",         # ATR-normalised size of most recent unfilled FVG
    "fvg_pct_filled",       # fraction of most recent FVG already filled (0–1)
    "fvg_bars_since",       # bars elapsed since most recent FVG formed (cap 60)
    "fvg_inside_flag",      # 1 if current close is inside an unfilled FVG
    "sweep_flag",           # 1 if this bar confirms a liquidity sweep reversal
    "sweep_depth_atr",      # depth of sweep beyond swing extreme (ATR units)
    "sweep_vol_ratio",      # volume on sweep bar vs 20-day avg
    "rvol_20",              # current bar volume / 20-day average volume
    "displacement_rvol",    # OB-forming displacement bar volume / 20-day avg
]



def _safe(val, default=0.0) -> float:
    try:
        v = float(val)
        return default if (math.isnan(v) or math.isinf(v)) else v
    except Exception:
        return default


def _rsi(series: pd.Series, period: int = 14) -> float:
    delta = series.diff().dropna()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return _safe(rsi.iloc[-1])


def _atr(df: pd.DataFrame, period: int = 14) -> float:
    high, low, close = df["High"], df["Low"], df["Close"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return _safe(tr.ewm(span=period, adjust=False).mean().iloc[-1])


def _adx(df: pd.DataFrame, period: int = 14) -> float:
    high, low, close = df["High"], df["Low"], df["Close"]
    plus_dm = (high.diff()).clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
    atr_s = tr.ewm(span=period, adjust=False).mean()
    plus_di  = 100 * (plus_dm.ewm(span=period, adjust=False).mean() / atr_s.replace(0, np.nan))
    minus_di = 100 * (minus_dm.ewm(span=period, adjust=False).mean() / atr_s.replace(0, np.nan))
    dx = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
    return _safe(dx.ewm(span=period, adjust=False).mean().iloc[-1])


def _stochastic(df: pd.DataFrame, k: int = 14, d: int = 3) -> Tuple[float, float]:
    low_min  = df["Low"].rolling(k).min()
    high_max = df["High"].rolling(k).max()
    stoch_k  = 100 * ((df["Close"] - low_min) / (high_max - low_min).replace(0, np.nan))
    stoch_d  = stoch_k.rolling(d).mean()
    return _safe(stoch_k.iloc[-1]), _safe(stoch_d.iloc[-1])


def _bollinger(series: pd.Series, period: int = 20, std: float = 2.0) -> Tuple[float, float]:
    sma = series.rolling(period).mean()
    std_dev = series.rolling(period).std()
    upper = sma + std * std_dev
    lower = sma - std * std_dev
    pct_b = (series - lower) / (upper - lower).replace(0, np.nan)
    width = (upper - lower) / sma.replace(0, np.nan)
    return _safe(pct_b.iloc[-1]), _safe(width.iloc[-1])


def _macd(series: pd.Series) -> Tuple[float, float, float]:
    fast   = series.ewm(span=12, adjust=False).mean()
    slow   = series.ewm(span=26, adjust=False).mean()
    line   = fast - slow
    signal = line.ewm(span=9, adjust=False).mean()
    hist   = line - signal
    return _safe(line.iloc[-1]), _safe(signal.iloc[-1]), _safe(hist.iloc[-1])


def _roc(series: pd.Series, period: int) -> float:
    if len(series) <= period:
        return 0.0
    old = series.iloc[-period - 1]
    return _safe((series.iloc[-1] - old) / old * 100) if old != 0 else 0.0


# ── Order-flow inference helper ───────────────────────────────────────────────
_OF_DEFAULTS = {
    "bias_daily": 1.0, "ob_dist_above_atr": 5.0,
    "ob_dist_below_atr": 5.0, "ob_inside_flag": 0.0,
    "fvg_size_atr": 0.0, "fvg_pct_filled": 0.0,
    "fvg_bars_since": 60.0, "fvg_inside_flag": 0.0,
    "sweep_flag": 0.0, "sweep_depth_atr": 0.0,
    "sweep_vol_ratio": 0.0, "rvol_20": 1.0,
    "displacement_rvol": 1.0,
}

def _get_order_flow_inference(df: pd.DataFrame) -> dict:
    """
    Compute order-flow features for the last closed bar of df.
    Returns neutral defaults if order_flow module is unavailable.
    """
    try:
        from order_flow import compute_order_flow_row
        return compute_order_flow_row(df)
    except Exception:
        return dict(_OF_DEFAULTS)



def extract_features(
    symbol: str,
    digest_sentiment: Dict[str, int] = None,
    apex_scores: Dict[str, float] = None,
    sector_scores: Dict[str, float] = None,
    digest_mentions: set = None,
) -> Optional[Dict[str, Any]]:
    ticker_sym = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
    try:
        ticker = yf.Ticker(ticker_sym)
        df = ticker.history(period="1y", interval="1d", auto_adjust=True)
        if df is None or len(df) < 60:
            return None
        df = df.dropna(subset=["Close", "High", "Low", "Volume"])
        close = df["Close"]
        price = _safe(close.iloc[-1])
        if price <= 0:
            return None

        # ── Technical ──────────────────────────────────────────────────────
        rsi14 = _rsi(close, 14)
        rsi7  = _rsi(close, 7)
        macd_l, macd_s, macd_h = _macd(close)
        ema20  = _safe(close.ewm(span=20,  adjust=False).mean().iloc[-1])
        ema50  = _safe(close.ewm(span=50,  adjust=False).mean().iloc[-1])
        ema200 = _safe(close.ewm(span=200, adjust=False).mean().iloc[-1])
        bb_pctb, bb_width = _bollinger(close)
        atr14  = _atr(df)
        vol_avg10 = _safe(df["Volume"].rolling(10).mean().iloc[-1])
        vol_ratio = _safe(df["Volume"].iloc[-1] / vol_avg10) if vol_avg10 > 0 else 1.0
        roc5, roc10, roc20 = _roc(close, 5), _roc(close, 10), _roc(close, 20)
        adx14  = _adx(df)
        stk, std_ = _stochastic(df)
        high52 = _safe(close.rolling(252).max().iloc[-1])
        low52  = _safe(close.rolling(252).min().iloc[-1])
        pct_from_52h = _safe((high52 - price) / high52 * 100) if high52 > 0 else 0.0
        pct_from_52l = _safe((price - low52) / low52 * 100)   if low52  > 0 else 0.0
        sma20 = _safe(close.rolling(20).mean().iloc[-1])
        sma50 = _safe(close.rolling(50).mean().iloc[-1])
        pct_vs_sma20 = _safe((price - sma20) / sma20 * 100) if sma20 > 0 else 0.0
        pct_vs_sma50 = _safe((price - sma50) / sma50 * 100) if sma50 > 0 else 0.0
        pv_ema200    = _safe((price - ema200) / ema200 * 100) if ema200 > 0 else 0.0
        o = _safe(df["Open"].iloc[-1]); h = _safe(df["High"].iloc[-1]); l = _safe(df["Low"].iloc[-1])
        candle_body_pct = _safe(abs(price - o) / (h - l)) if (h - l) > 0 else 0.5
        hl_ratio = _safe((h - l) / price * 100)

        # ── Fundamentals ───────────────────────────────────────────────────
        info = {}
        try:
            info = ticker.info or {}
        except Exception:
            pass

        pe      = _safe(info.get("trailingPE") or info.get("forwardPE"), 25.0)
        pb      = _safe(info.get("priceToBook"), 3.0)
        ev_ebit = _safe(info.get("enterpriseToEbitda"), 15.0)
        roe     = _safe((info.get("returnOnEquity") or 0.12) * 100)
        de      = _safe(info.get("debtToEquity", 0.5))
        margin  = _safe((info.get("profitMargins") or 0) * 100)
        rev_gr  = _safe((info.get("revenueGrowth") or 0) * 100)
        mktcap  = _safe(info.get("marketCap", 1e10))
        mktcap_log = math.log10(max(mktcap, 1))
        div_yld = _safe((info.get("dividendYield") or 0) * 100)
        eps_gr  = _safe((info.get("earningsGrowth") or 0) * 100)

        # ── Sentiment ──────────────────────────────────────────────────────
        clean  = symbol.replace(".NS", "")
        sector = info.get("sector", "Unknown")
        return {
            "rsi_14": rsi14, "rsi_7": rsi7,
            "macd_line": macd_l, "macd_signal": macd_s, "macd_hist": macd_h,
            "ema_20": ema20, "ema_50": ema50, "ema_200": ema200,
            "bb_pct_b": bb_pctb, "bb_width": bb_width,
            "atr_14": atr14, "volume_ratio": vol_ratio,
            "roc_5": roc5, "roc_10": roc10, "roc_20": roc20,
            "adx_14": adx14, "stoch_k": stk, "stoch_d": std_,
            "pct_from_52h": pct_from_52h, "pct_from_52l": pct_from_52l,
            "pct_vs_sma20": pct_vs_sma20, "pct_vs_sma50": pct_vs_sma50,
            "price_vs_ema200": pv_ema200,
            "candle_body_pct": candle_body_pct, "hl_ratio": hl_ratio,
            "pe_ratio": min(pe, 200), "pb_ratio": min(pb, 50),
            "ev_ebitda": min(ev_ebit, 100), "roe": roe,
            "debt_to_equity": min(de, 10), "profit_margin": margin,
            "revenue_growth": rev_gr, "market_cap_log": mktcap_log,
            "dividend_yield": div_yld, "eps_growth": min(max(eps_gr, -100), 200),
            "news_sentiment": _safe((digest_sentiment or {}).get(clean, 0)),
            "sector_score":   _safe((sector_scores or {}).get(sector, 50)),
            "in_digest":      1.0 if clean in (digest_mentions or set()) else 0.0,
            "apex_score":     _safe((apex_scores or {}).get(clean, 50)),
            "fii_proxy":      _safe((info.get("heldPercentInstitutions") or 0) * 100 - 20),
            # ── Phase D: Order flow (last closed bar) ────────────────────
            **_get_order_flow_inference(df),
            # Metadata (stripped before model inference)
            "_symbol": clean, "_price": price, "_atr": atr14,
            "_sector": sector, "_name": info.get("longName", clean),
        }
    except Exception as e:
        logger.debug(f"Feature extraction failed {symbol}: {e}")
        return None


def extract_features_batch(
    symbols: List[str],
    digest_sentiment: Dict[str, int] = None,
    apex_scores: Dict[str, float] = None,
    sector_scores: Dict[str, float] = None,
    digest_mentions: set = None,
    max_workers: int = 8,
) -> List[Dict[str, Any]]:
    results = []
    t0 = time.time()
    logger.info(f"Extracting features for {len(symbols)} symbols...")
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(extract_features, sym, digest_sentiment, apex_scores, sector_scores, digest_mentions): sym
            for sym in symbols
        }
        for fut in as_completed(futures):
            r = fut.result()
            if r:
                results.append(r)
    logger.info(f"Features done: {len(results)}/{len(symbols)} in {time.time()-t0:.1f}s")
    return results


def features_to_df(feature_dicts: List[Dict]) -> pd.DataFrame:
    df = pd.DataFrame(feature_dicts)
    for col in FEATURE_COLUMNS:
        if col not in df.columns:
            df[col] = 0.0
    df[FEATURE_COLUMNS] = df[FEATURE_COLUMNS].fillna(0).astype(float)
    return df


# ── Historical label generation (for training) ────────────────────────────────
def generate_labels(
    symbol: str,
    forward_days: int = 10,
    threshold_pct: float = 5.0,
    period: str = "8y",
) -> Optional[pd.DataFrame]:
    """
    Download 2y OHLCV and create labelled rows for walk-forward training.

    Vectorised implementation: all indicators are computed once as full Series
    over the entire history, then sampled row-by-row. This is ~50-100x faster
    than the previous approach which recomputed all indicators from scratch per row.
    """
    ticker_sym = symbol if symbol.endswith(".NS") else f"{symbol}.NS"
    try:
        df = yf.Ticker(ticker_sym).history(period=period, interval="1d", auto_adjust=True).dropna(subset=["Close"])
        if len(df) < forward_days + 60:
            return None

        close  = df["Close"]
        high   = df["High"]
        low    = df["Low"]
        volume = df["Volume"]
        opens  = df["Open"]

        # ── Compute all indicators vectorised over full history ──────────────

        # RSI (14 & 7)
        def _rsi_series(s: pd.Series, period: int) -> pd.Series:
            delta = s.diff()
            gain  = delta.clip(lower=0)
            loss  = -delta.clip(upper=0)
            avg_g = gain.ewm(alpha=1 / period, adjust=False).mean()
            avg_l = loss.ewm(alpha=1 / period, adjust=False).mean()
            rs    = avg_g / avg_l.replace(0, np.nan)
            return (100 - 100 / (1 + rs)).fillna(50)

        rsi14_s = _rsi_series(close, 14)
        rsi7_s  = _rsi_series(close, 7)

        # MACD
        fast_s   = close.ewm(span=12, adjust=False).mean()
        slow_s   = close.ewm(span=26, adjust=False).mean()
        macd_l_s = fast_s - slow_s
        macd_sig_s = macd_l_s.ewm(span=9, adjust=False).mean()
        macd_h_s   = macd_l_s - macd_sig_s

        # EMAs
        ema20_s  = close.ewm(span=20,  adjust=False).mean()
        ema50_s  = close.ewm(span=50,  adjust=False).mean()
        ema200_s = close.ewm(span=200, adjust=False).mean()

        # Bollinger Bands
        sma20_s   = close.rolling(20).mean()
        std20_s   = close.rolling(20).std()
        bb_upper  = sma20_s + 2 * std20_s
        bb_lower  = sma20_s - 2 * std20_s
        bb_pctb_s = ((close - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)).fillna(0.5)
        bb_width_s = ((bb_upper - bb_lower) / sma20_s.replace(0, np.nan)).fillna(0)

        # ATR (14)
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low  - close.shift()).abs(),
        ], axis=1).max(axis=1)
        atr14_s = tr.ewm(span=14, adjust=False).mean().fillna(0)

        # Volume ratio (vs 10-day avg)
        vol_avg10_s = volume.rolling(10).mean().replace(0, np.nan)
        vol_ratio_s = (volume / vol_avg10_s).fillna(1.0)

        # Rate of change
        def _roc_series(s: pd.Series, p: int) -> pd.Series:
            old = s.shift(p)
            return ((s - old) / old.replace(0, np.nan) * 100).fillna(0)

        roc5_s  = _roc_series(close, 5)
        roc10_s = _roc_series(close, 10)
        roc20_s = _roc_series(close, 20)

        # ADX (14) — vectorised
        plus_dm  = (high.diff()).clip(lower=0)
        minus_dm = (-low.diff()).clip(lower=0)
        atr_adx  = tr.ewm(span=14, adjust=False).mean().replace(0, np.nan)
        plus_di  = 100 * (plus_dm.ewm(span=14, adjust=False).mean() / atr_adx)
        minus_di = 100 * (minus_dm.ewm(span=14, adjust=False).mean() / atr_adx)
        dx       = 100 * ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan))
        adx14_s  = dx.ewm(span=14, adjust=False).mean().fillna(25)

        # Stochastic (14, 3)
        low_min14  = low.rolling(14).min()
        high_max14 = high.rolling(14).max()
        stk_s = (100 * (close - low_min14) / (high_max14 - low_min14).replace(0, np.nan)).fillna(50)
        std_s = stk_s.rolling(3).mean().fillna(50)

        # 52-week high/low (rolling 252)
        high52_s = close.rolling(252, min_periods=1).max()
        low52_s  = close.rolling(252, min_periods=1).min()
        pct_from_52h_s = ((high52_s - close) / high52_s.replace(0, np.nan) * 100).fillna(0)
        pct_from_52l_s = ((close - low52_s)  / low52_s.replace(0, np.nan)  * 100).fillna(0)

        # SMA 20/50
        sma50_s      = close.rolling(50).mean()
        pct_vs_sma20 = ((close - sma20_s) / sma20_s.replace(0, np.nan) * 100).fillna(0)
        pct_vs_sma50 = ((close - sma50_s) / sma50_s.replace(0, np.nan) * 100).fillna(0)

        # Price vs EMA200
        pv_ema200_s  = ((close - ema200_s) / ema200_s.replace(0, np.nan) * 100).fillna(0)

        # Candle body % and HL ratio
        hl_range     = (high - low).replace(0, np.nan)
        candle_pct_s = (abs(close - opens) / hl_range).fillna(0.5)
        hl_ratio_s   = (hl_range / close.replace(0, np.nan) * 100).fillna(0)

        # ── Phase D: Order Flow features (vectorised over full history) ─────
        of_series = None
        try:
            from order_flow import compute_order_flow_series
            of_series = compute_order_flow_series(df)
        except Exception as e:
            logger.debug(f"Order flow series failed for {symbol}: {e}")

        # ── Forward return labels ────────────────────────────────────────────
        fwd_close = close.shift(-forward_days)
        fwd_ret   = ((fwd_close - close) / close.replace(0, np.nan) * 100)
        label_s   = (fwd_ret >= threshold_pct).astype(int)

        # ── Triple-barrier exit tracking (for expectancy calculation) ────────
        # For each bar, track:
        #   fwd_ret_raw  : actual % return at forward_days (can be negative)
        #   max_fwd_gain : max % gain achieved at ANY point during the window
        #   max_fwd_loss : max % drawdown during the window
        # This lets us compute avg_win and avg_loss separately from the binary label.
        max_gain_s = pd.Series(index=close.index, dtype=float)
        max_loss_s = pd.Series(index=close.index, dtype=float)
        for i in range(len(close) - forward_days):
            c0   = close.iloc[i]
            if c0 <= 0:
                max_gain_s.iloc[i] = 0.0
                max_loss_s.iloc[i] = 0.0
                continue
            window   = close.iloc[i + 1: i + forward_days + 1]
            rets     = (window - c0) / c0 * 100
            max_gain_s.iloc[i] = float(rets.max()) if len(rets) else 0.0
            max_loss_s.iloc[i] = float(rets.min()) if len(rets) else 0.0

        # ── Assemble rows (only valid window 60 to end-forward_days) ────────
        idx_range = range(60, len(df) - forward_days)

        records = []
        for i in idx_range:
            cp = _safe(close.iloc[i])
            if cp <= 0:
                continue
            records.append({
                "rsi_14":       _safe(rsi14_s.iloc[i]),
                "rsi_7":        _safe(rsi7_s.iloc[i]),
                "macd_line":    _safe(macd_l_s.iloc[i]),
                "macd_signal":  _safe(macd_sig_s.iloc[i]),
                "macd_hist":    _safe(macd_h_s.iloc[i]),
                "ema_20":       _safe(ema20_s.iloc[i]),
                "ema_50":       _safe(ema50_s.iloc[i]),
                "ema_200":      _safe(ema200_s.iloc[i]),
                "bb_pct_b":     _safe(bb_pctb_s.iloc[i]),
                "bb_width":     _safe(bb_width_s.iloc[i]),
                "atr_14":       _safe(atr14_s.iloc[i]),
                "volume_ratio": _safe(vol_ratio_s.iloc[i]),
                "roc_5":        _safe(roc5_s.iloc[i]),
                "roc_10":       _safe(roc10_s.iloc[i]),
                "roc_20":       _safe(roc20_s.iloc[i]),
                "adx_14":       _safe(adx14_s.iloc[i]),
                "stoch_k":      _safe(stk_s.iloc[i]),
                "stoch_d":      _safe(std_s.iloc[i]),
                "pct_from_52h": _safe(pct_from_52h_s.iloc[i]),
                "pct_from_52l": _safe(pct_from_52l_s.iloc[i]),
                "pct_vs_sma20": _safe(pct_vs_sma20.iloc[i]),
                "pct_vs_sma50": _safe(pct_vs_sma50.iloc[i]),
                "price_vs_ema200": _safe(pv_ema200_s.iloc[i]),
                "candle_body_pct": _safe(candle_pct_s.iloc[i]),
                "hl_ratio":     _safe(hl_ratio_s.iloc[i]),
                # Fundamentals: use sector medians as placeholders
                # (live inference uses real yfinance .info values)
                "pe_ratio": 25.0, "pb_ratio": 3.0, "ev_ebitda": 15.0,
                "roe": 15.0, "debt_to_equity": 0.5, "profit_margin": 10.0,
                "revenue_growth": 10.0, "market_cap_log": 10.0,
                "dividend_yield": 1.0, "eps_growth": 10.0,
                # Sentiment: zero at training time (no live context)
                "news_sentiment": 0, "sector_score": 50,
                "in_digest": 0, "apex_score": 50, "fii_proxy": 0,
                # ── Phase D: Order flow (sampled from pre-computed series) ─────
                **({
                    col: _safe(float(of_series[col].iloc[i]))
                    for col in [
                        "bias_daily", "ob_dist_above_atr", "ob_dist_below_atr",
                        "ob_inside_flag", "fvg_size_atr", "fvg_pct_filled",
                        "fvg_bars_since", "fvg_inside_flag",
                        "sweep_flag", "sweep_depth_atr", "sweep_vol_ratio",
                        "rvol_20", "displacement_rvol",
                    ]
                } if of_series is not None else {
                    "bias_daily": 1.0, "ob_dist_above_atr": 5.0,
                    "ob_dist_below_atr": 5.0, "ob_inside_flag": 0.0,
                    "fvg_size_atr": 0.0, "fvg_pct_filled": 0.0,
                    "fvg_bars_since": 60.0, "fvg_inside_flag": 0.0,
                    "sweep_flag": 0.0, "sweep_depth_atr": 0.0,
                    "sweep_vol_ratio": 0.0, "rvol_20": 1.0,
                    "displacement_rvol": 1.0,
                }),
                # Binary training label (unchanged)
                "label": int(label_s.iloc[i]),
                # ── Expectancy tracking columns (NOT used as training features) ──
                "fwd_ret_raw":  round(float(fwd_ret.iloc[i]), 4),
                "max_fwd_gain": round(float(max_gain_s.iloc[i]), 4),
                "max_fwd_loss": round(float(max_loss_s.iloc[i]), 4),
                # ──────────────────────────────────────────────────────────────
                "date": df.index[i],
                "symbol": symbol.replace(".NS", ""),
            })

        return pd.DataFrame(records) if records else None

    except Exception as e:
        logger.debug(f"Label generation failed {symbol}: {e}")
        return None



# ── Calibration wrappers ─────────────────────────────────────────────────────
# Defined HERE (ml_features.py) — NOT in train_model.py — so joblib always
# pickles/unpickles with a stable module path, regardless of __main__ vs import.

class CalibratedXGBModel:
    """
    Wraps an XGBoost classifier + a probability calibrator.
    Supports:
      - method='sigmoid' : LogisticRegression (Platt scaling) — preserves score spread
      - method='isotonic': IsotonicRegression                  — step function, legacy
    Exposes a sklearn-compatible predict_proba() interface for kepler_model.py.
    """
    def __init__(self, xgb_model, calibrator, method: str = "sigmoid"):
        self.xgb_model  = xgb_model
        self.calibrator = calibrator
        self.method     = method

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        raw = self.xgb_model.predict_proba(X)[:, 1]
        if self.method == "sigmoid":
            cal = self.calibrator.predict_proba(raw.reshape(-1, 1))[:, 1]
        else:  # isotonic
            cal = self.calibrator.predict(raw)
        return np.column_stack([1 - cal, cal])

    @property
    def feature_importances_(self) -> np.ndarray:
        return self.xgb_model.feature_importances_


class CalibratedLGBMModel:
    """
    Wraps a LightGBM classifier so it exposes the same duck-typed interface
    as CalibratedXGBModel. Kepler inference code calls predict_proba() on
    whatever is pickled — this makes LGBM a drop-in replacement.
    """
    def __init__(self, lgbm_model):
        self.lgbm_model = lgbm_model

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        # LightGBM returns shape (n, n_classes) for binary classification
        proba = self.lgbm_model.predict_proba(X)
        if proba.ndim == 1:
            # Fallback: raw predict() was used
            return np.column_stack([1 - proba, proba])
        return proba

    @property
    def feature_importances_(self) -> np.ndarray:
        return self.lgbm_model.feature_importances_


# ── Coverage report ───────────────────────────────────────────────────────────
def coverage_report(
    symbols: List[str],
    period: str = "8y",
    min_coverage_pct: float = 80.0,
    max_workers: int = 8,
) -> Dict[str, Any]:
    """
    Download date ranges for all symbols and report coverage gaps.
    Flags tickers with < min_coverage_pct of the expected trading days.

    Returns a dict with:
      'ok'      : list of symbols with sufficient coverage
      'gapped'  : list of dicts {symbol, coverage_pct, n_days, expected_days}
      'failed'  : list of symbols that could not be fetched
      'summary' : human-readable string
    """
    # Approximate expected trading days for common period strings
    _expected_map = {
        "1y": 252, "2y": 504, "3y": 756, "5y": 1260,
        "8y": 2016, "10y": 2520, "max": 5000,
    }
    expected_days = _expected_map.get(period, 2016)

    ok_list: List[str] = []
    gapped_list: List[Dict] = []
    failed_list: List[str] = []

    def _check(sym: str) -> Dict:
        ticker_sym = sym if sym.endswith(".NS") else f"{sym}.NS"
        try:
            df = yf.Ticker(ticker_sym).history(period=period, interval="1d", auto_adjust=True)
            if df is None or df.empty:
                return {"symbol": sym, "status": "failed", "n_days": 0}
            n_days = len(df)
            pct = n_days / expected_days * 100
            return {"symbol": sym, "status": "ok" if pct >= min_coverage_pct else "gapped",
                    "n_days": n_days, "coverage_pct": round(pct, 1)}
        except Exception:
            return {"symbol": sym, "status": "failed", "n_days": 0}

    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_check, s): s for s in symbols}
        for fut in as_completed(futures):
            result = fut.result()
            if result["status"] == "ok":
                ok_list.append(result["symbol"])
            elif result["status"] == "gapped":
                gapped_list.append(result)
            else:
                failed_list.append(result["symbol"])

    gapped_list.sort(key=lambda x: x["coverage_pct"])
    summary = (
        f"Coverage report ({period}): {len(ok_list)} OK, "
        f"{len(gapped_list)} gapped (<{min_coverage_pct}%), "
        f"{len(failed_list)} failed"
    )
    logger.info(summary)
    if gapped_list:
        logger.warning("Gapped tickers (consider excluding from training):")
        for g in gapped_list[:10]:
            logger.warning(f"  {g['symbol']:<20} {g['coverage_pct']}% ({g['n_days']} days)")
        if len(gapped_list) > 10:
            logger.warning(f"  ... and {len(gapped_list) - 10} more")

    return {
        "ok": ok_list,
        "gapped": gapped_list,
        "failed": failed_list,
        "summary": summary,
    }

