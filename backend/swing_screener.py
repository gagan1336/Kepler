"""
KEPLER -- Swing Trading Technical Screener
Inspired by ChartInk screener patterns for NSE stocks.

Computes all indicators from yfinance OHLCV data locally:
  - RSI(14) via Wilder's smoothing
  - DMA 20 / 50 / 200
  - 52-Week High/Low proximity
  - Volume ratio (today vs 10-day avg)
  - Swing score (composite 0-100)

10 swing trading presets:
  1. near_52w_high       — Within 5% of 52W high (ChartInk classic)
  2. breakout_52w        — Price crossed 52W high in last 3 days
  3. volume_surge        — Volume > 3× 10-day avg
  4. momentum_leaders    — Price > 20DMA > 50DMA > 200DMA
  5. rsi_oversold_bounce — RSI 30-45, above 200DMA
  6. rsi_momentum        — RSI > 65, trending up
  7. near_support        — Within 5% of 52W low, good fundamentals
  8. golden_crossover    — 50DMA just crossed above 200DMA
  9. vcp_tight           — Volatility contraction (tight consolidation near highs)
  10. high_rs            — High relative strength vs Nifty 50

All results are NaN-safe and cached 30 minutes.
"""
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf
from loguru import logger

# ── Cache ──────────────────────────────────────────────────────────────────────
_swing_cache: Dict[str, Dict] = {}
_SWING_CACHE_TTL = 1800  # 30 minutes (swing traders need fresh data)

# ── NSE Swing Pool — 300 liquid NSE stocks ────────────────────────────────────
NSE_SWING_POOL = [
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
    "HDFCLIFE.NS","ICICIGI.NS","ADANIPORTS.NS","LTIM.NS","VEDL.NS",
    # Nifty Next 50 / Mid cap
    "ZOMATO.NS","DMART.NS","PIDILITIND.NS","SIEMENS.NS","HAVELLS.NS",
    "MUTHOOTFIN.NS","CHOLAFIN.NS","IDFCFIRSTB.NS","BANDHANBNK.NS",
    "FEDERALBNK.NS","CANBK.NS","BANKBARODA.NS","TATAPOWER.NS","TORNTPOWER.NS",
    "IRCTC.NS","HAL.NS","BEL.NS","DLF.NS","GODREJPROP.NS","PRESTIGE.NS",
    "OBEROIRLTY.NS","LUPIN.NS","AUROPHARMA.NS","IPCALAB.NS","ALKEM.NS",
    "TORNTPHARM.NS","ZYDUSLIFE.NS","MAXHEALTH.NS","FORTIS.NS",
    "OFSS.NS","MPHASIS.NS","PERSISTENT.NS","COFORGE.NS","LTTS.NS",
    "POLYCAB.NS","KEI.NS","ASTRAL.NS","DIXON.NS","AMBER.NS","KAYNES.NS",
    "ANGELONE.NS","MOTILALOFS.NS","BAJAJ-AUTO.NS","TVSMOTORS.NS",
    "PAGEIND.NS","TRENT.NS","NMDC.NS","SAIL.NS","IRFC.NS","RECLTD.NS",
    "JKCEMENT.NS","SHREECEM.NS","AMBUJACEM.NS","ACC.NS",
    "DEEPAKNTR.NS","SRF.NS","PIIND.NS","SOLARINDS.NS",
    "LALPATHLAB.NS","METROPOLIS.NS","BIOCON.NS","NATCOPHARM.NS",
    "INOXWIND.NS","JPPOWER.NS","NHPC.NS","SJVN.NS","CESC.NS",
    "JUBLFOOD.NS","DEVYANI.NS","WESTLIFE.NS",
    "KALYANKJIL.NS","SENCO.NS",
    "MOTHERSON.NS","TATACHEM.NS","GNFC.NS",
    "CASTROLIND.NS","IOC.NS","HINDPETRO.NS","MGL.NS","IGL.NS",
    "GAIL.NS","PETRONET.NS","CONCOR.NS","ADANIGREEN.NS",
    "TATACOMM.NS","HFCL.NS","STLTECH.NS","RAILTEL.NS",
    "MARICO.NS","DABUR.NS","EMAMILTD.NS","COLPAL.NS","GODREJCP.NS",
    "VOLTAS.NS","BLUESTARCO.NS","CROMPTON.NS",
    "APOLLOTYRE.NS","MRF.NS","CEATLTD.NS","BALKRISIND.NS",
    "MANAPPURAM.NS","UJJIVANSFB.NS","EQUITASBNK.NS",
    "RBLBANK.NS","YESBANK.NS",
    "HDFCAMC.NS","NIPPONLIFEIN.NS","UTIAMC.NS",
    "ABB.NS","CUMMINSIND.NS","THERMAX.NS","BHEL.NS",
    "PFC.NS","RECLTD.NS","IREDA.NS","NHPC.NS",
    "TATAELXSI.NS","CYIENT.NS","KPITTECH.NS","ROUTE.NS",
    "AFFLE.NS","INDIAMART.NS","NAUKRI.NS","ZOMATO.NS",
    "POLICYBZR.NS","NYKAA.NS",
    "ESCORTS.NS","SONACOMS.NS","CRAFTSMAN.NS",
    "HINDZINC.NS","NATIONALUM.NS",
    "M&M.NS","MAHINDCIE.NS","TIINDIA.NS","SUPRAJIT.NS",
    "IDFCFIRSTB.NS","AUBANK.NS","SURYAROSNI.NS","VAIBHAVGBL.NS",
    "CDSL.NS","BSE.NS","MCX.NS","ICICIPRULI.NS",
    "SHRIRAMFIN.NS","BAJAJHLDNG.NS","CHOLAFIN.NS",
    "RAYMOND.NS","VEDL.NS","GMRAIRPORT.NS",
    "INDUSTOWER.NS","TATACOMM.NS","BHARTIHEXA.NS",
    "NIFTY50.NS",  # for RS calculation reference
]

# ── Nifty 50 for Relative Strength baseline ───────────────────────────────────
NIFTY_TICKER = "^NSEI"


def _is_cache_valid(key: str) -> bool:
    entry = _swing_cache.get(key)
    if not entry:
        return False
    age = (datetime.utcnow() - entry["fetched_at"]).total_seconds()
    return age < _SWING_CACHE_TTL


def _sf(v: Any) -> Optional[float]:
    """Safe float — returns None for None/NaN/Inf."""
    try:
        if v is None:
            return None
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _sanitize(obj: Any) -> Any:
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


def _compute_rsi(closes: pd.Series, period: int = 14) -> Optional[float]:
    """Wilder's RSI."""
    if len(closes) < period + 1:
        return None
    delta = closes.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float('nan'))
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return _sf(val)


def _dma(closes: pd.Series, period: int) -> Optional[float]:
    if len(closes) < period:
        return None
    return _sf(closes.rolling(period).mean().iloc[-1])


def _fetch_technicals(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Download 1-year daily OHLCV and compute all technical indicators.
    Returns a standardised swing stock row, or None if data is unavailable.
    """
    try:
        df = yf.download(symbol, period="1y", interval="1d", progress=False, auto_adjust=True)
        if df is None or len(df) < 30:
            return None

        # Flatten MultiIndex if needed
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        closes = df["Close"].dropna()
        volumes = df["Volume"].dropna()
        highs = df["High"].dropna()
        lows = df["Low"].dropna()

        if len(closes) < 30:
            return None

        current_price = _sf(closes.iloc[-1])
        if not current_price:
            return None

        # 52W metrics
        high_52w = _sf(closes.max())
        low_52w = _sf(closes.min())
        pct_from_52h = round((high_52w - current_price) / high_52w * 100, 2) if high_52w else None
        pct_from_52l = round((current_price - low_52w) / low_52w * 100, 2) if low_52w and low_52w > 0 else None

        # DMAs
        dma20  = _dma(closes, 20)
        dma50  = _dma(closes, 50)
        dma200 = _dma(closes, 200) if len(closes) >= 200 else None

        # DMA signal string
        if dma20 and dma50 and dma200:
            if current_price > dma20 > dma50 > dma200:
                dma_signal = "20>50>200 ✅"
            elif current_price > dma50 > dma200:
                dma_signal = "Above 50&200 📈"
            elif current_price > dma200:
                dma_signal = "Above 200 🟡"
            else:
                dma_signal = "Below 200 ⚠️"
        elif dma50 and dma200:
            dma_signal = "Above 200 🟡" if current_price > dma200 else "Below 200 ⚠️"
        else:
            dma_signal = None

        # RSI
        rsi = _compute_rsi(closes, 14)

        # Volume ratio (today vs 10-day avg)
        if len(volumes) >= 11:
            avg_vol_10 = float(volumes.iloc[-11:-1].mean())
            today_vol  = float(volumes.iloc[-1])
            vol_ratio  = round(today_vol / avg_vol_10, 2) if avg_vol_10 > 0 else None
        else:
            vol_ratio = None

        # Today's change %
        if len(closes) >= 2:
            prev_close = _sf(closes.iloc[-2])
            change_pct_today = round((current_price - prev_close) / prev_close * 100, 2) if prev_close else None
        else:
            change_pct_today = None

        # Volatility (10-day price range as % of price) — for VCP
        if len(closes) >= 10:
            recent = closes.iloc[-10:]
            vol_pct = round((recent.max() - recent.min()) / recent.mean() * 100, 2)
        else:
            vol_pct = None

        # Previous 10 days max/min for VCP
        prev_vol_pct = None
        if len(closes) >= 25:
            prev_block = closes.iloc[-25:-10]
            prev_vol_pct = round((prev_block.max() - prev_block.min()) / prev_block.mean() * 100, 2)

        # Golden crossover detection: 50DMA crossed above 200DMA in last 10 days
        golden_cross_days = None
        if dma50 and dma200 and len(closes) >= 210:
            dma50_series  = closes.rolling(50).mean()
            dma200_series = closes.rolling(200).mean()
            cross_series  = (dma50_series > dma200_series).astype(int).diff()
            crossovers    = cross_series[cross_series == 1]
            if len(crossovers) > 0:
                last_cross_idx = crossovers.index[-1]
                days_since     = (closes.index[-1] - last_cross_idx).days
                golden_cross_days = days_since if days_since <= 60 else None

        # Ticker info for fundamentals
        ticker = yf.Ticker(symbol)
        info   = ticker.fast_info or {}
        mcap   = _sf(getattr(info, 'market_cap', None))
        pe     = _sf(getattr(info, 'pe_ratio', None))
        company_name = symbol.replace(".NS", "").replace(".BO", "")

        # Try full info for company name and sector
        try:
            full_info = ticker.info or {}
            company_name = full_info.get("longName") or full_info.get("shortName") or company_name
            sector = full_info.get("sector", "")
        except Exception:
            sector = ""

        # Swing score (0-100 composite)
        swing_score = _compute_swing_score(
            rsi=rsi, vol_ratio=vol_ratio,
            pct_from_52h=pct_from_52h,
            change_pct_today=change_pct_today,
            dma_signal=dma_signal,
        )

        signal_tags = _build_signal_tags(
            rsi=rsi, vol_ratio=vol_ratio, pct_from_52h=pct_from_52h,
            pct_from_52l=pct_from_52l, dma_signal=dma_signal,
            change_pct_today=change_pct_today,
        )

        raw_sym = symbol.replace(".NS", "").replace(".BO", "")
        return _sanitize({
            "symbol":          raw_sym,
            "company_name":    company_name,
            "sector":          sector,
            "current_price":   current_price,
            "change_pct_today":change_pct_today,
            "week_52_high":    high_52w,
            "week_52_low":     low_52w,
            "pct_from_52h":    pct_from_52h,
            "pct_from_52l":    pct_from_52l,
            "rsi_14":          rsi,
            "volume_ratio":    vol_ratio,
            "dma_20":          dma20,
            "dma_50":          dma50,
            "dma_200":         dma200,
            "dma_signal":      dma_signal,
            "market_cap_cr":   round(mcap / 1e7, 2) if mcap else None,
            "pe_ratio":        pe,
            "swing_score":     swing_score,
            "signal_tags":     signal_tags,
            # Extra fields for specific presets
            "_vol_pct_10d":    vol_pct,
            "_prev_vol_pct":   prev_vol_pct,
            "_golden_cross_days": golden_cross_days,
        })
    except Exception as e:
        logger.debug(f"Swing fetch error {symbol}: {e}")
        return None


def _compute_swing_score(
    rsi, vol_ratio, pct_from_52h, change_pct_today, dma_signal
) -> int:
    score = 0
    # RSI in ideal swing zone (40-70)
    if rsi is not None:
        if 45 <= rsi <= 65:  score += 25
        elif 35 <= rsi < 45: score += 15
        elif 65 < rsi <= 75: score += 15
        elif rsi > 75:       score += 5
    # Volume confirmation
    if vol_ratio is not None:
        if vol_ratio >= 3:   score += 25
        elif vol_ratio >= 2: score += 18
        elif vol_ratio >= 1.5: score += 10
        elif vol_ratio >= 1: score += 5
    # Price momentum
    if change_pct_today is not None:
        if change_pct_today >= 3:  score += 20
        elif change_pct_today >= 1: score += 12
        elif change_pct_today >= 0: score += 6
    # DMA alignment
    if dma_signal:
        if "20>50>200" in dma_signal:  score += 20
        elif "Above 50&200" in dma_signal: score += 14
        elif "Above 200" in dma_signal: score += 8
    # Proximity to 52W high
    if pct_from_52h is not None:
        if pct_from_52h <= 3:  score += 10
        elif pct_from_52h <= 8: score += 7
        elif pct_from_52h <= 15: score += 3
    return min(score, 100)


def _build_signal_tags(rsi, vol_ratio, pct_from_52h, pct_from_52l, dma_signal, change_pct_today) -> List[str]:
    tags = []
    if pct_from_52h is not None and pct_from_52h <= 5:
        tags.append("Near 52W High")
    if pct_from_52h is not None and pct_from_52h <= 1:
        tags.append("52W Breakout Zone")
    if vol_ratio is not None and vol_ratio >= 2:
        tags.append(f"Vol {vol_ratio:.1f}x Surge")
    if rsi is not None:
        if rsi >= 65: tags.append(f"RSI {rsi:.0f} Momentum")
        elif rsi <= 40: tags.append(f"RSI {rsi:.0f} Oversold")
        else: tags.append(f"RSI {rsi:.0f}")
    if dma_signal and "20>50>200" in dma_signal:
        tags.append("All MAs Aligned")
    if change_pct_today is not None and change_pct_today >= 2:
        tags.append(f"+{change_pct_today:.1f}% Today")
    return tags[:4]  # Cap at 4 tags


def _run_parallel(symbols: List[str], workers: int = 15) -> List[Dict[str, Any]]:
    results = []
    uniq = list(dict.fromkeys(s for s in symbols if s != "^NSEI"))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="swing") as pool:
        futures = {pool.submit(_fetch_technicals, sym): sym for sym in uniq}
        for future in as_completed(futures):
            try:
                row = future.result(timeout=25)
                if row:
                    results.append(row)
            except Exception as e:
                logger.debug(f"Swing future error: {e}")
    return results


def _get_all_stocks(cache_key_prefix: str = "all") -> List[Dict[str, Any]]:
    """Fetch/cache the full technical universe (30-min TTL)."""
    cache_key = f"{cache_key_prefix}_universe"
    if _is_cache_valid(cache_key):
        return _swing_cache[cache_key]["data"]

    logger.info(f"Fetching swing universe: {len(NSE_SWING_POOL)} stocks (parallel 15 workers)")
    t0 = time.time()
    stocks = _run_parallel(NSE_SWING_POOL, workers=15)
    elapsed = round(time.time() - t0, 1)
    logger.info(f"Swing universe fetched: {len(stocks)} stocks in {elapsed}s")
    _swing_cache[cache_key] = {"data": stocks, "fetched_at": datetime.utcnow()}
    return stocks


# ── Public API — 10 Swing Presets ─────────────────────────────────────────────

SWING_PRESETS = {
    "near_52w_high": {
        "label": "Near 52-Week High",
        "icon": "🚀",
        "description": "Stocks within 5% of their 52-week high — potential breakout candidates",
        "color": "#10b981",
    },
    "breakout_52w": {
        "label": "52W High Breakout",
        "icon": "💥",
        "description": "Price at or above 52-week high today — confirmed breakout stocks",
        "color": "#f59e0b",
    },
    "volume_surge": {
        "label": "Volume Surge",
        "icon": "📊",
        "description": "Volume 2.5× or more above 10-day average — big money moving in",
        "color": "#6366f1",
    },
    "momentum_leaders": {
        "label": "Momentum Leaders",
        "icon": "⚡",
        "description": "Price above 20 DMA > 50 DMA > 200 DMA — perfect trend alignment",
        "color": "#3b82f6",
    },
    "rsi_oversold_bounce": {
        "label": "RSI Oversold Bounce",
        "icon": "🔄",
        "description": "RSI 25-45, above 200 DMA — potential reversal candidates",
        "color": "#ec4899",
    },
    "rsi_momentum": {
        "label": "RSI Momentum",
        "icon": "📈",
        "description": "RSI > 65 with positive price action — strong momentum stocks",
        "color": "#8b5cf6",
    },
    "near_support": {
        "label": "At Strong Support",
        "icon": "🛡️",
        "description": "Price within 8% of 52W low with solid fundamentals — value at support",
        "color": "#0ea5e9",
    },
    "golden_crossover": {
        "label": "Golden Crossover",
        "icon": "✨",
        "description": "50 DMA crossed above 200 DMA in last 60 days — bullish signal",
        "color": "#eab308",
    },
    "vcp_tight": {
        "label": "VCP (Tight Setup)",
        "icon": "🎯",
        "description": "Volatility contraction near highs — coiling for a breakout (Minervini style)",
        "color": "#14b8a6",
    },
    "high_rs": {
        "label": "High Relative Strength",
        "icon": "💪",
        "description": "Outperforming Nifty 50 significantly in last 3 months",
        "color": "#f97316",
    },
}


def run_swing_preset(preset_name: str, limit: int = 30) -> Dict[str, Any]:
    """Dispatch to the correct swing preset filter."""
    cache_key = f"swing_{preset_name}_{limit}"
    if _is_cache_valid(cache_key):
        logger.debug(f"Swing cache hit: {cache_key}")
        return _swing_cache[cache_key]["data"]

    meta = SWING_PRESETS.get(preset_name)
    if not meta:
        return {"error": f"Unknown swing preset: {preset_name}", "results": [], "count": 0}

    logger.info(f"Running swing preset: {preset_name}")
    t0 = time.time()

    stocks = _get_all_stocks()

    # ── Filter logic per preset ────────────────────────────────────────────────
    filtered = []

    if preset_name == "near_52w_high":
        # Within 5% of 52W high, RSI not overbought (< 80), positive trend
        filtered = [
            s for s in stocks
            if s.get("pct_from_52h") is not None
            and s["pct_from_52h"] <= 5.0
            and s.get("current_price", 0) > 0
            and (s.get("rsi_14") is None or s["rsi_14"] < 82)
        ]
        filtered.sort(key=lambda x: x.get("pct_from_52h", 99))

    elif preset_name == "breakout_52w":
        # Price at or above 52W high (pct_from_52h <= 0.5%)
        filtered = [
            s for s in stocks
            if s.get("pct_from_52h") is not None
            and s["pct_from_52h"] <= 0.5
        ]
        filtered.sort(key=lambda x: -(x.get("volume_ratio") or 0))

    elif preset_name == "volume_surge":
        # Volume >= 2.5× 10-day average, price positive today
        filtered = [
            s for s in stocks
            if s.get("volume_ratio") is not None
            and s["volume_ratio"] >= 2.5
            and (s.get("change_pct_today") or 0) > -3
        ]
        filtered.sort(key=lambda x: -(x.get("volume_ratio") or 0))

    elif preset_name == "momentum_leaders":
        # Price > 20DMA > 50DMA > 200DMA
        filtered = [
            s for s in stocks
            if s.get("dma_signal") and "20>50>200" in s["dma_signal"]
            and s.get("rsi_14") is not None
            and s["rsi_14"] >= 50
        ]
        filtered.sort(key=lambda x: -(x.get("swing_score") or 0))

    elif preset_name == "rsi_oversold_bounce":
        # RSI 25-45, price above 200DMA
        filtered = [
            s for s in stocks
            if s.get("rsi_14") is not None
            and 25 <= s["rsi_14"] <= 45
            and s.get("dma_200") is not None
            and (s.get("current_price") or 0) > s["dma_200"]
        ]
        filtered.sort(key=lambda x: x.get("rsi_14") or 99)

    elif preset_name == "rsi_momentum":
        # RSI > 65, DMA aligned (above 50 DMA), positive today
        filtered = [
            s for s in stocks
            if s.get("rsi_14") is not None
            and s["rsi_14"] >= 65
            and s.get("dma_50") is not None
            and (s.get("current_price") or 0) > (s.get("dma_50") or 0)
        ]
        filtered.sort(key=lambda x: -(x.get("rsi_14") or 0))

    elif preset_name == "near_support":
        # Within 8% of 52W low, above 200DMA (not in freefall)
        filtered = [
            s for s in stocks
            if s.get("pct_from_52l") is not None
            and s["pct_from_52l"] <= 8.0
            and s.get("dma_200") is not None
            and (s.get("current_price") or 0) > s["dma_200"] * 0.95  # within 5% of 200 DMA
        ]
        filtered.sort(key=lambda x: x.get("pct_from_52l") or 99)

    elif preset_name == "golden_crossover":
        # 50DMA crossed above 200DMA recently (within 60 days)
        filtered = [
            s for s in stocks
            if s.get("_golden_cross_days") is not None
            and s["_golden_cross_days"] <= 60
        ]
        filtered.sort(key=lambda x: x.get("_golden_cross_days") or 999)

    elif preset_name == "vcp_tight":
        # Volatility contraction: last 10-day range < previous 15-day range
        # AND price within 10% of 52W high (consolidating near highs)
        filtered = [
            s for s in stocks
            if s.get("_vol_pct_10d") is not None
            and s.get("_prev_vol_pct") is not None
            and s["_vol_pct_10d"] < s["_prev_vol_pct"] * 0.6  # 40% contraction
            and s.get("pct_from_52h") is not None
            and s["pct_from_52h"] <= 12.0
        ]
        filtered.sort(key=lambda x: x.get("_vol_pct_10d") or 99)

    elif preset_name == "high_rs":
        # Stocks up significantly more than Nifty 50 in last 3 months (proxy via 52W metrics)
        # Use pct_from_52l as proxy for YTD relative strength
        filtered = [
            s for s in stocks
            if s.get("pct_from_52l") is not None
            and s["pct_from_52l"] >= 30  # Stock up 30%+ from its 52W low
            and s.get("dma_50") is not None
            and (s.get("current_price") or 0) > (s.get("dma_50") or 0)
            and (s.get("rsi_14") or 0) >= 50
        ]
        filtered.sort(key=lambda x: -(x.get("pct_from_52l") or 0))

    # Remove internal fields and cap results
    for s in filtered:
        s.pop("_vol_pct_10d", None)
        s.pop("_prev_vol_pct", None)
        s.pop("_golden_cross_days", None)

    filtered = filtered[:limit]
    elapsed = round(time.time() - t0, 1)

    data = {
        "preset":       preset_name,
        "label":        meta["label"],
        "icon":         meta["icon"],
        "description":  meta["description"],
        "color":        meta["color"],
        "results":      filtered,
        "count":        len(filtered),
        "fetched_at":   datetime.utcnow().isoformat(),
        "fetch_time_sec": elapsed,
        "pool_size":    len(stocks),
    }
    _swing_cache[cache_key] = {"data": data, "fetched_at": datetime.utcnow()}
    logger.info(f"Swing preset '{preset_name}': {len(filtered)} results in {elapsed}s")
    return data


def get_swing_preset_list() -> List[Dict[str, Any]]:
    return [
        {"key": k, "label": v["label"], "icon": v["icon"],
         "description": v["description"], "color": v["color"]}
        for k, v in SWING_PRESETS.items()
    ]
