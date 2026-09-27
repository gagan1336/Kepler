"""
KEPLER -- Picks Engine
"High-Conviction Stock Picks" powered by multi-factor scoring.

Combines 5 signal layers:
  1. APEX Score  (technical breakout quality)        — from breakout_scanner
  2. Swing Score (10 preset screener composite)      — from swing_screener
  3. Fundamentals (PE, ROE, promoter, revenue CAGR)  — from fundamentals_fetcher
  4. Momentum    (RS vs Nifty, volume surge, RSI)    — computed inline
  5. AI Thesis   (Gemini Flash structured analysis)  — per pick

Output: Top 12 high-conviction picks, categorised by timeframe:
  - SWING      : 1–3 weeks  (technical setup firing)
  - MOMENTUM   : 3–8 weeks  (strong RS + EMA stack)
  - POSITIONAL : 2–4 months (fundamentals + trend aligned)
  - VALUE      : 3–6 months (undervalued vs sector, quality business)

Conviction Score: 0–100 composite
  - VERY HIGH ≥ 80 (all 5 factors aligned)
  - HIGH      ≥ 65
  - MODERATE  ≥ 50
  - WATCHLIST < 50

DISCLAIMER: This is a data-driven quantitative analysis tool.
NO investment is guaranteed. Past technical signals do NOT guarantee
future returns. Always do your own research.
"""

import copy
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import google.generativeai as genai
import numpy as np
import pandas as pd
import yfinance as yf
from loguru import logger

from config import settings

# ── Cache ──────────────────────────────────────────────────────────────────────
_picks_cache: Dict[str, Any] = {}
_PICKS_TTL = 4 * 3600   # 4-hour refresh (picks are daily-ish)
_CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
os.makedirs(_CACHE_DIR, exist_ok=True)
_PICKS_CACHE_FILE = os.path.join(_CACHE_DIR, "kepler_picks.json")

# ── Candidate pool — best 120 stocks from full universe ───────────────────────
# Mix of quality, liquidity, and trend potential across all major sectors
PICKS_UNIVERSE = [
    # Banking & NBFC
    "HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "SBIN.NS",
    "BAJFINANCE.NS", "BAJAJFINSV.NS", "CHOLAFIN.NS", "MUTHOOTFIN.NS", "ANGELONE.NS",
    "SHRIRAMFIN.NS", "CDSL.NS", "BSE.NS",
    # IT
    "TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS", "LTIM.NS",
    "PERSISTENT.NS", "COFORGE.NS", "MPHASIS.NS", "LTTS.NS", "TATAELXSI.NS",
    "KPITTECH.NS", "OFSS.NS",
    # Pharma & Health
    "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS", "LUPIN.NS",
    "AUROPHARMA.NS", "ALKEM.NS", "ZYDUSLIFE.NS", "MAXHEALTH.NS", "FORTIS.NS",
    "LALPATHLAB.NS", "SYNGENE.NS", "NATCOPHARM.NS",
    # Auto
    "MARUTI.NS", "TATAMOTORS.NS", "BAJAJ-AUTO.NS", "HEROMOTOCO.NS", "TVSMOTORS.NS",
    "EICHERMOT.NS", "M&M.NS", "TIINDIA.NS", "MOTHERSON.NS", "BALKRISIND.NS",
    # Capital Goods & Infra
    "LT.NS", "SIEMENS.NS", "HAVELLS.NS", "ABB.NS", "POLYCAB.NS", "KEI.NS",
    "RECLTD.NS", "PFC.NS", "IRFC.NS", "KEC.NS", "CUMMINSIND.NS",
    # Defence
    "HAL.NS", "BEL.NS", "SOLARINDS.NS", "COCHINSHIP.NS", "MAZDOCK.NS",
    # Power & Energy
    "POWERGRID.NS", "NTPC.NS", "TATAPOWER.NS", "ADANIGREEN.NS", "NHPC.NS",
    "SJVN.NS", "INOXWIND.NS", "TORNTPOWER.NS",
    # Metals
    "TATASTEEL.NS", "JSWSTEEL.NS", "HINDALCO.NS", "COALINDIA.NS", "NMDC.NS", "VEDL.NS",
    # FMCG & Retail
    "HINDUNILVR.NS", "ITC.NS", "NESTLEIND.NS", "BRITANNIA.NS", "MARICO.NS",
    "TRENT.NS", "DMART.NS", "TITAN.NS", "JUBLFOOD.NS", "KALYANKJIL.NS",
    # Real Estate
    "DLF.NS", "GODREJPROP.NS", "PRESTIGE.NS", "OBEROIRLTY.NS",
    # Chemicals
    "DEEPAKNTR.NS", "SRF.NS", "PIIND.NS", "SOLARINDS.NS",
    # Telecom
    "BHARTIARTL.NS",
    # Paints & Consumer
    "ASIANPAINT.NS", "PIDILITIND.NS",
    # Railways & Logistics
    "IRCTC.NS", "CONCOR.NS",
    # Electronics
    "DIXON.NS", "KAYNES.NS", "AMBER.NS",
    # Internet
    "ZOMATO.NS", "NAUKRI.NS", "INDIAMART.NS",
]

SECTOR_MAP = {
    "HDFCBANK.NS": "Banking", "ICICIBANK.NS": "Banking", "KOTAKBANK.NS": "Banking",
    "AXISBANK.NS": "Banking", "SBIN.NS": "Banking", "BAJFINANCE.NS": "NBFC",
    "BAJAJFINSV.NS": "NBFC", "CHOLAFIN.NS": "NBFC", "MUTHOOTFIN.NS": "NBFC",
    "ANGELONE.NS": "Broking", "SHRIRAMFIN.NS": "NBFC", "CDSL.NS": "Exchange",
    "BSE.NS": "Exchange", "TCS.NS": "IT", "INFY.NS": "IT", "HCLTECH.NS": "IT",
    "WIPRO.NS": "IT", "TECHM.NS": "IT", "LTIM.NS": "IT", "PERSISTENT.NS": "IT",
    "COFORGE.NS": "IT", "MPHASIS.NS": "IT", "LTTS.NS": "IT", "TATAELXSI.NS": "IT",
    "KPITTECH.NS": "IT", "OFSS.NS": "IT", "SUNPHARMA.NS": "Pharma",
    "DRREDDY.NS": "Pharma", "CIPLA.NS": "Pharma", "DIVISLAB.NS": "Pharma",
    "LUPIN.NS": "Pharma", "AUROPHARMA.NS": "Pharma", "ALKEM.NS": "Pharma",
    "ZYDUSLIFE.NS": "Pharma", "MAXHEALTH.NS": "Healthcare", "FORTIS.NS": "Healthcare",
    "LALPATHLAB.NS": "Diagnostics", "SYNGENE.NS": "Pharma", "NATCOPHARM.NS": "Pharma",
    "MARUTI.NS": "Auto", "TATAMOTORS.NS": "Auto", "BAJAJ-AUTO.NS": "Auto",
    "HEROMOTOCO.NS": "Auto", "TVSMOTORS.NS": "Auto", "EICHERMOT.NS": "Auto",
    "M&M.NS": "Auto", "TIINDIA.NS": "Auto Ancillary", "MOTHERSON.NS": "Auto Ancillary",
    "BALKRISIND.NS": "Auto", "LT.NS": "Capital Goods", "SIEMENS.NS": "Capital Goods",
    "HAVELLS.NS": "Capital Goods", "ABB.NS": "Capital Goods", "POLYCAB.NS": "Cables",
    "KEI.NS": "Cables", "RECLTD.NS": "Finance", "PFC.NS": "Finance",
    "IRFC.NS": "Finance", "KEC.NS": "Capital Goods", "CUMMINSIND.NS": "Capital Goods",
    "HAL.NS": "Defence", "BEL.NS": "Defence", "SOLARINDS.NS": "Defence",
    "COCHINSHIP.NS": "Defence", "MAZDOCK.NS": "Defence", "POWERGRID.NS": "Power",
    "NTPC.NS": "Power", "TATAPOWER.NS": "Power", "ADANIGREEN.NS": "Power",
    "NHPC.NS": "Power", "SJVN.NS": "Power", "INOXWIND.NS": "Wind Energy",
    "TORNTPOWER.NS": "Power", "TATASTEEL.NS": "Metals", "JSWSTEEL.NS": "Metals",
    "HINDALCO.NS": "Metals", "COALINDIA.NS": "Metals", "NMDC.NS": "Metals",
    "VEDL.NS": "Metals", "HINDUNILVR.NS": "FMCG", "ITC.NS": "FMCG",
    "NESTLEIND.NS": "FMCG", "BRITANNIA.NS": "FMCG", "MARICO.NS": "FMCG",
    "TRENT.NS": "Retail", "DMART.NS": "Retail", "TITAN.NS": "Jewellery",
    "JUBLFOOD.NS": "QSR", "KALYANKJIL.NS": "Jewellery", "DLF.NS": "Real Estate",
    "GODREJPROP.NS": "Real Estate", "PRESTIGE.NS": "Real Estate",
    "OBEROIRLTY.NS": "Real Estate", "DEEPAKNTR.NS": "Chemicals",
    "SRF.NS": "Chemicals", "PIIND.NS": "Agrochem", "BHARTIARTL.NS": "Telecom",
    "ASIANPAINT.NS": "Paints", "PIDILITIND.NS": "Chemicals", "IRCTC.NS": "Railways",
    "CONCOR.NS": "Logistics", "DIXON.NS": "Electronics", "KAYNES.NS": "Electronics",
    "AMBER.NS": "Electronics", "ZOMATO.NS": "Internet", "NAUKRI.NS": "Internet",
    "INDIAMART.NS": "Internet",
}


# ── Helpers ────────────────────────────────────────────────────────────────────

def _sf(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        f = float(v)
        return None if (f != f or f == float("inf") or f == float("-inf")) else f
    except Exception:
        return None


def _safe(v: Any, default=None):
    r = _sf(v)
    return r if r is not None else default


# ── Per-stock technical analysis ───────────────────────────────────────────────

def _analyse_stock(symbol: str, nifty_ret_30d: float) -> Optional[Dict]:
    """
    Full technical analysis on a single stock.
    Returns a structured dict with all signals needed for conviction scoring.
    """
    try:
        df = yf.download(symbol, period="1y", interval="1d", progress=False, auto_adjust=True)
        if df is None or len(df) < 50:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        close  = df["Close"].dropna()
        volume = df["Volume"].dropna()
        high   = df["High"].dropna()
        low    = df["Low"].dropna()

        if len(close) < 50:
            return None

        price = _sf(close.iloc[-1])
        if not price:
            return None

        # ── EMA / DMA ─────────────────────────────────────────────────────────
        ema20  = _sf(close.ewm(span=20,  adjust=False).mean().iloc[-1])
        ema50  = _sf(close.ewm(span=50,  adjust=False).mean().iloc[-1])
        ema200 = _sf(close.ewm(span=200, adjust=False).mean().iloc[-1]) if len(close) >= 200 else None

        # ── RSI(14) ───────────────────────────────────────────────────────────
        delta = close.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, float("nan"))
        rsi_series = 100 - (100 / (1 + rs))
        rsi = _sf(rsi_series.iloc[-1]) or 50.0

        # ── MACD ──────────────────────────────────────────────────────────────
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        macd_sig  = macd_line.ewm(span=9, adjust=False).mean()
        macd = _sf(macd_line.iloc[-1]) or 0.0
        macd_signal_val = _sf(macd_sig.iloc[-1]) or 0.0
        macd_above = macd > macd_signal_val

        # ── 52-Week metrics ───────────────────────────────────────────────────
        high_52w = _sf(close.max())
        low_52w  = _sf(close.min())
        pct_from_52h = round((high_52w - price) / high_52w * 100, 2) if high_52w else 100.0
        pct_from_52l = round((price - low_52w) / low_52w * 100, 2) if low_52w and low_52w > 0 else 0.0

        # ── Volume ────────────────────────────────────────────────────────────
        vol_today = _sf(volume.iloc[-1]) or 0
        vol_avg10 = _sf(volume.iloc[-11:-1].mean()) or 1
        vol_ratio = round(vol_today / vol_avg10, 2) if vol_avg10 > 0 else 1.0

        # ── Stock 30d return ──────────────────────────────────────────────────
        ret_30d = round((close.iloc[-1] / close.iloc[-22] - 1) * 100, 2) if len(close) >= 22 else 0.0

        # ── Relative Strength vs Nifty ────────────────────────────────────────
        rs_vs_nifty = round(ret_30d - nifty_ret_30d, 2)

        # ── VCP (Volatility Contraction Pattern) ──────────────────────────────
        if len(close) >= 35:
            recent_std = float(close.iloc[-10:].std())
            prior_std  = float(close.iloc[-30:-10].std())
            vcp_ratio  = round(recent_std / prior_std, 3) if prior_std > 0 else 1.0
        else:
            vcp_ratio = 1.0
        vcp_tightening = vcp_ratio < 0.6  # tight consolidation

        # ── ATR (for stop loss calculation) ──────────────────────────────────
        tr = pd.concat([
            high - low,
            (high - close.shift()).abs(),
            (low  - close.shift()).abs(),
        ], axis=1).max(axis=1)
        atr = _sf(tr.ewm(span=14, adjust=False).mean().iloc[-1]) or price * 0.02

        # ── EMA structure check ───────────────────────────────────────────────
        ema_perfect = (ema20 and ema50 and ema200 and
                       price > ema20 > ema50 > ema200)
        ema_above_50_200 = (ema50 and ema200 and price > ema50 > ema200)
        golden_cross = (ema50 and ema200 and ema50 > ema200 and
                        _sf(close.ewm(span=50, adjust=False).mean().iloc[-6]) is not None and
                        _sf(close.ewm(span=50, adjust=False).mean().iloc[-6]) < ema200)

        # ── Detect patterns ───────────────────────────────────────────────────
        patterns = []
        if pct_from_52h <= 2:
            patterns.append("52W Breakout")
        if pct_from_52h <= 5:
            patterns.append("Near 52W High")
        if vcp_tightening and pct_from_52h <= 15:
            patterns.append("VCP Setup")
        if vol_ratio >= 2.5:
            patterns.append("Volume Surge")
        if ema_perfect:
            patterns.append("EMA Stack ✅")
        if golden_cross:
            patterns.append("Golden Cross")
        if 55 <= rsi <= 70 and ema_above_50_200:
            patterns.append("RSI Momentum")
        if rs_vs_nifty > 5:
            patterns.append(f"High RS (+{rs_vs_nifty:.1f}% vs Nifty)")

        return {
            "symbol":         symbol.replace(".NS", ""),
            "symbol_ns":      symbol,
            "sector":         SECTOR_MAP.get(symbol, "Diversified"),
            "price":          round(price, 2),
            "ema20":          round(ema20, 2) if ema20 else None,
            "ema50":          round(ema50, 2) if ema50 else None,
            "ema200":         round(ema200, 2) if ema200 else None,
            "rsi":            round(rsi, 1),
            "macd":           round(macd, 3),
            "macd_signal":    round(macd_signal_val, 3),
            "macd_above":     macd_above,
            "high_52w":       round(high_52w, 2) if high_52w else None,
            "low_52w":        round(low_52w, 2) if low_52w else None,
            "pct_from_52h":   pct_from_52h,
            "pct_from_52l":   pct_from_52l,
            "vol_ratio":      vol_ratio,
            "ret_30d":        round(ret_30d, 2),
            "rs_vs_nifty":    rs_vs_nifty,
            "vcp_ratio":      vcp_ratio,
            "vcp_tightening": vcp_tightening,
            "atr":            round(atr, 2),
            "ema_perfect":    ema_perfect,
            "ema_above_50_200": ema_above_50_200,
            "golden_cross":   golden_cross,
            "patterns":       patterns,
        }
    except Exception as e:
        logger.debug(f"Stock analysis failed for {symbol}: {e}")
        return None


# ── Conviction Score ───────────────────────────────────────────────────────────

def _compute_conviction(stock: Dict, fundamentals: Optional[Dict] = None) -> Dict:
    """
    Compute a 0-100 conviction score across 5 dimensions.
    Returns the score + dimension breakdown + category + timeframe.
    """
    # ── 1. Technical Score (0-30) — EMA structure, RSI, MACD ─────────────────
    tech = 0
    if stock.get("ema_perfect"):       tech += 12
    elif stock.get("ema_above_50_200"): tech += 7
    rsi = stock.get("rsi", 50)
    if 55 <= rsi <= 70:   tech += 8  # sweet spot
    elif 45 <= rsi < 55:  tech += 4
    elif rsi > 75:        tech += 2  # overbought — less upside
    if stock.get("macd_above"):        tech += 6
    if stock.get("golden_cross"):      tech += 4
    tech = min(tech, 30)

    # ── 2. Momentum Score (0-25) — RS, volume, 30d return ────────────────────
    mom = 0
    rs = stock.get("rs_vs_nifty", 0)
    if rs > 10:   mom += 12
    elif rs > 5:  mom += 8
    elif rs > 0:  mom += 4
    elif rs < -5: mom -= 3

    vol = stock.get("vol_ratio", 1)
    if vol >= 3:    mom += 7
    elif vol >= 2:  mom += 4
    elif vol >= 1.5: mom += 2

    ret = stock.get("ret_30d", 0)
    if ret > 15:  mom += 6
    elif ret > 8: mom += 4
    elif ret > 3: mom += 2
    elif ret < -5: mom -= 2
    mom = min(max(mom, 0), 25)

    # ── 3. Pattern Score (0-20) — technical setups ────────────────────────────
    patterns = stock.get("patterns", [])
    pattern_weights = {
        "52W Breakout": 10, "VCP Setup": 9, "EMA Stack ✅": 8,
        "Golden Cross": 7, "Near 52W High": 6, "Volume Surge": 5,
        "RSI Momentum": 5, "High RS": 4,
    }
    pat_score = 0
    for p in patterns:
        for k, w in pattern_weights.items():
            if k in p:
                pat_score += w
                break
    pat_score = min(pat_score, 20)

    # ── 4. Fundamentals Score (0-15) — if available ───────────────────────────
    fund = 0
    if fundamentals:
        pe  = fundamentals.get("pe_ratio")
        roe = fundamentals.get("roe")
        rev_growth = fundamentals.get("revenue_cagr_3y")
        promoter = fundamentals.get("promoter_holding")
        debt_eq = fundamentals.get("debt_to_equity")

        if pe and 0 < pe < 30:   fund += 4
        elif pe and 30 <= pe < 50: fund += 2

        if roe and roe > 20:      fund += 4
        elif roe and roe > 12:    fund += 2

        if rev_growth and rev_growth > 15: fund += 3
        elif rev_growth and rev_growth > 8: fund += 1

        if promoter and promoter > 50:  fund += 2
        if debt_eq is not None and debt_eq < 0.5: fund += 2
    else:
        fund = 7   # neutral when no data
    fund = min(fund, 15)

    # ── 5. Setup Quality (0-10) — proximity to 52W high, VCP ─────────────────
    setup = 0
    pct_from_52h = stock.get("pct_from_52h", 50)
    if pct_from_52h <= 2:    setup += 6
    elif pct_from_52h <= 5:  setup += 4
    elif pct_from_52h <= 10: setup += 2
    if stock.get("vcp_tightening"): setup += 4
    setup = min(setup, 10)

    # ── Composite ─────────────────────────────────────────────────────────────
    composite = tech + mom + pat_score + fund + setup
    composite = min(max(composite, 0), 100)

    # ── Conviction label ──────────────────────────────────────────────────────
    if composite >= 80:
        conviction = "VERY_HIGH"
        conviction_label = "Very High Conviction"
        conviction_color = "#10b981"
    elif composite >= 65:
        conviction = "HIGH"
        conviction_label = "High Conviction"
        conviction_color = "#22c55e"
    elif composite >= 50:
        conviction = "MODERATE"
        conviction_label = "Moderate Conviction"
        conviction_color = "#f59e0b"
    else:
        conviction = "WATCHLIST"
        conviction_label = "Watchlist"
        conviction_color = "#64748b"

    # ── Category ──────────────────────────────────────────────────────────────
    if "52W Breakout" in patterns or "VCP Setup" in patterns:
        category = "SWING"
        timeframe = "1–3 weeks"
        timeframe_icon = "⚡"
    elif stock.get("ema_perfect") and rs > 5:
        category = "MOMENTUM"
        timeframe = "3–8 weeks"
        timeframe_icon = "🚀"
    elif fundamentals and fundamentals.get("pe_ratio") and fundamentals["pe_ratio"] < 20:
        category = "VALUE"
        timeframe = "3–6 months"
        timeframe_icon = "💎"
    else:
        category = "POSITIONAL"
        timeframe = "2–4 months"
        timeframe_icon = "📈"

    # ── Entry / Target / Stop Loss ────────────────────────────────────────────
    price = stock.get("price", 0)
    atr   = stock.get("atr", price * 0.02)

    entry_low  = round(price * 0.99, 2)       # ~1% below CMP for limit
    entry_high = round(price * 1.005, 2)      # CMP to 0.5% above
    stop_loss  = round(price - (1.5 * atr), 2)
    sl_pct     = round((price - stop_loss) / price * 100, 1)

    # Target: based on conviction + momentum
    if composite >= 80:
        target_mult = 1.18   # 18% upside
    elif composite >= 65:
        target_mult = 1.12   # 12% upside
    else:
        target_mult = 1.08   # 8% upside

    target1 = round(price * target_mult, 2)
    target2 = round(price * (target_mult + 0.07), 2)
    rr_ratio = round((target1 - price) / (price - stop_loss), 2) if price > stop_loss else 0

    return {
        "conviction":       conviction,
        "conviction_label": conviction_label,
        "conviction_color": conviction_color,
        "conviction_score": composite,
        "category":         category,
        "timeframe":        timeframe,
        "timeframe_icon":   timeframe_icon,
        "tech_score":       tech,
        "momentum_score":   mom,
        "pattern_score":    pat_score,
        "fund_score":       fund,
        "setup_score":      setup,
        "entry_low":        entry_low,
        "entry_high":       entry_high,
        "stop_loss":        stop_loss,
        "sl_pct":           sl_pct,
        "target1":          target1,
        "target2":          target2,
        "rr_ratio":         rr_ratio,
    }


# ── AI Thesis Generator ────────────────────────────────────────────────────────

_thesis_cache: Dict[str, Dict] = {}

def _generate_thesis(stock: Dict, conviction: Dict, fundamentals: Optional[Dict]) -> Dict:
    """Generate a structured AI thesis for each pick via Gemini Flash."""
    cache_key = f"{stock['symbol']}_{datetime.now().strftime('%Y-%m-%d')}"
    if cache_key in _thesis_cache:
        return _thesis_cache[cache_key]

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")

        fund_str = ""
        if fundamentals:
            pe  = fundamentals.get("pe_ratio")
            roe = fundamentals.get("roe")
            mkt = fundamentals.get("market_cap_cr")
            div = fundamentals.get("dividend_yield")
            fund_str = f"""
Fundamentals:
- P/E: {pe:.1f}x | ROE: {roe:.1f}% | Market Cap: ₹{mkt:,.0f}Cr
- Dividend Yield: {div:.2f}% | Debt/Equity: {fundamentals.get('debt_to_equity', 'N/A')}
- Revenue CAGR 3Y: {fundamentals.get('revenue_cagr_3y', 'N/A')}%
- Promoter Holding: {fundamentals.get('promoter_holding', 'N/A')}%
"""

        prompt = f"""
You are a senior equity research analyst at a top Indian institutional fund.
Analyse this high-conviction stock pick and generate a structured thesis.

Stock: {stock['symbol']} ({stock['sector']})
CMP: ₹{stock['price']}
Timeframe: {conviction['timeframe']} ({conviction['category']})
Conviction: {conviction['conviction_label']} ({conviction['conviction_score']}/100)

Technical signals:
- RSI(14): {stock['rsi']} | EMA structure: {'Perfect 20>50>200' if stock.get('ema_perfect') else 'Above 50&200' if stock.get('ema_above_50_200') else 'Mixed'}
- Volume ratio: {stock['vol_ratio']}x (10d avg) | MACD: {'Above signal ✅' if stock.get('macd_above') else 'Below signal'}
- 30d RS vs Nifty: {stock['rs_vs_nifty']:+.1f}% | 30d return: {stock['ret_30d']:+.1f}%
- Proximity to 52W high: {stock['pct_from_52h']:.1f}% below
- Patterns: {', '.join(stock['patterns']) if stock['patterns'] else 'None detected'}
{fund_str}
Entry: ₹{conviction['entry_low']}–{conviction['entry_high']} | Target: ₹{conviction['target1']} (T1) / ₹{conviction['target2']} (T2) | SL: ₹{conviction['stop_loss']} ({conviction['sl_pct']}% below CMP)

Respond in EXACTLY this JSON format (no markdown):
{{
  "thesis": "2-3 sentence conviction thesis explaining WHY this stock is worth buying NOW",
  "key_strengths": ["strength 1", "strength 2", "strength 3"],
  "key_risks": ["risk 1", "risk 2"],
  "catalyst": "The primary near-term catalyst or technical trigger to watch",
  "invalidation": "What would invalidate this trade (price level or event)"
}}
"""
        resp = model.generate_content(prompt, generation_config={"temperature": 0.4})
        raw = resp.text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        result = {
            "thesis":      str(data.get("thesis", "")),
            "strengths":   list(data.get("key_strengths", []))[:3],
            "risks":       list(data.get("key_risks", []))[:2],
            "catalyst":    str(data.get("catalyst", "")),
            "invalidation": str(data.get("invalidation", "")),
        }
        _thesis_cache[cache_key] = result
        return result
    except Exception as e:
        logger.debug(f"AI thesis failed for {stock['symbol']}: {e}")
        # Fallback rule-based thesis
        patterns = stock.get("patterns", [])
        return {
            "thesis": f"{stock['symbol']} shows {', '.join(patterns[:2]) if patterns else 'positive technical signals'} with {stock['ret_30d']:+.1f}% 30-day performance vs Nifty ({stock['rs_vs_nifty']:+.1f}% RS). EMA structure is {'perfect — all three EMAs aligned bullishly' if stock.get('ema_perfect') else 'supportive above key moving averages'}.",
            "strengths": patterns[:3] or [f"RSI at {stock['rsi']:.0f}", f"Volume {stock['vol_ratio']}x average", f"{stock['ret_30d']:+.1f}% 30d return"],
            "risks": ["Market-wide correction could invalidate setup", f"Stop loss at ₹{conviction['stop_loss']} ({conviction['sl_pct']}% risk)"],
            "catalyst": f"Watch for sustained volume above {stock['vol_ratio']:.1f}x and RSI holding above 55",
            "invalidation": f"Close below ₹{conviction['stop_loss']} invalidates the bullish thesis",
        }


# ── Main Engine ────────────────────────────────────────────────────────────────

def _load_picks_cache() -> Optional[Dict]:
    try:
        if os.path.exists(_PICKS_CACHE_FILE):
            with open(_PICKS_CACHE_FILE, encoding="utf-8") as f:
                data = json.load(f)
            if time.time() - data.get("fetched_at", 0) < _PICKS_TTL:
                return data
    except Exception:
        pass
    return None


def _save_picks_cache(data: Dict):
    try:
        with open(_PICKS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
    except Exception:
        pass


def _build_picks() -> Dict:
    """
    Main engine: scan universe, score, filter, generate thesis, return top picks.
    Now integrates:
      - Win Probability scoring (ML + strategy + news + fundamentals)
      - News sentiment fusion per stock
      - Strategy backtest leaderboard
      - Sorted by win_probability DESC
    """
    t0 = time.time()
    logger.info("Kepler Picks: scanning universe…")

    # ── Load backtest data (cached, weekly refresh) ───────────────────────────
    backtest_data: Optional[Dict] = None
    try:
        from strategy_backtester import get_backtest_results, get_strategy_leaderboard
        backtest_data = get_backtest_results()
        strategy_leaderboard = get_strategy_leaderboard(top_n=14)
        logger.info(f"Backtest data loaded: {backtest_data.get('active_count', 0)} active strategies")
    except Exception as e:
        logger.warning(f"Backtest data unavailable: {e}")
        strategy_leaderboard = []

    # ── Nifty 30d return for RS calculation ──────────────────────────────────
    nifty_ret_30d = 0.0
    try:
        nifty_df = yf.download("^NSEI", period="40d", interval="1d", progress=False, auto_adjust=True)
        if len(nifty_df) >= 22:
            closes = nifty_df["Close"].dropna()
            nifty_ret_30d = float((closes.iloc[-1] / closes.iloc[-22] - 1) * 100)
    except Exception as e:
        logger.debug(f"Nifty fetch failed: {e}")

    # ── Phase 1: Technical analysis on all stocks in parallel ─────────────────
    raw_stocks: List[Dict] = []
    with ThreadPoolExecutor(max_workers=10, thread_name_prefix="picks") as pool:
        futures = {pool.submit(_analyse_stock, sym, nifty_ret_30d): sym for sym in PICKS_UNIVERSE}
        for fut in as_completed(futures, timeout=120):
            try:
                result = fut.result()
                if result:
                    raw_stocks.append(result)
            except Exception:
                pass

    logger.info(f"Kepler Picks: {len(raw_stocks)}/{len(PICKS_UNIVERSE)} stocks analysed")

    # ── Phase 2: Pre-filter ────────────────────────────────────────────────────
    candidates = [
        s for s in raw_stocks
        if (s.get("ema_above_50_200") or s.get("rs_vs_nifty", -99) > 0 or s.get("patterns"))
        and s.get("rsi", 0) < 80
        and s.get("pct_from_52h", 100) <= 25
    ]
    logger.info(f"Kepler Picks: {len(candidates)} candidates after pre-filter")

    # ── Phase 3: Conviction scoring ───────────────────────────────────────────
    scored = []
    for s in candidates:
        conv = _compute_conviction(s, fundamentals=None)
        scored.append({**s, **conv})
    scored.sort(key=lambda x: x["conviction_score"], reverse=True)

    # ── Phase 4: Top 20 — fetch fundamentals + re-score ───────────────────────
    top20 = scored[:20]
    fund_map: Dict[str, Dict] = {}
    try:
        from fundamentals_fetcher import fetch_fundamentals
        with ThreadPoolExecutor(max_workers=5, thread_name_prefix="fund") as pool:
            futures = {pool.submit(fetch_fundamentals, s["symbol_ns"]): s["symbol_ns"] for s in top20}
            for fut in as_completed(futures, timeout=60):
                sym = futures[fut]
                try:
                    fund_map[sym] = fut.result()
                except Exception:
                    pass
        logger.info(f"Kepler Picks: fundamentals fetched for {len(fund_map)} stocks")
        re_scored = []
        for s in top20:
            fund = fund_map.get(s["symbol_ns"])
            conv = _compute_conviction(s, fundamentals=fund)
            re_scored.append({**s, **conv, "fundamentals": fund})
        re_scored.sort(key=lambda x: x["conviction_score"], reverse=True)
    except Exception as e:
        logger.warning(f"Fundamentals phase failed: {e}")
        re_scored = [{**s, "fundamentals": None} for s in top20]

    # ── Phase 5: News sentiment (batch, single RSS fetch) ─────────────────────
    sentiments_map: Dict[str, Dict] = {}
    try:
        from news_sentiment_engine import get_batch_sentiment
        sentiments_map = get_batch_sentiment(re_scored[:15], workers=4)
        logger.info(f"Kepler Picks: sentiment fetched for {len(sentiments_map)} stocks")
    except Exception as e:
        logger.warning(f"News sentiment phase failed: {e}")

    # ── Phase 6: Win Probability scoring ──────────────────────────────────────
    try:
        from swing_probability import batch_compute_probabilities
        prob_enriched = batch_compute_probabilities(
            re_scored[:15],
            fundamentals_map=fund_map,
            sentiments_map=sentiments_map,
            backtest_data=backtest_data,
        )
        logger.info(f"Kepler Picks: probability scored {len(prob_enriched)} stocks")
    except Exception as e:
        logger.warning(f"Probability phase failed: {e}")
        prob_enriched = re_scored[:15]

    # ── Phase 7: Top 12 — generate AI thesis ──────────────────────────────────
    top12 = prob_enriched[:12]
    final_picks = []
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="thesis") as pool:
        futures = {
            pool.submit(_generate_thesis, s, s, s.get("fundamentals")): s
            for s in top12
        }
        for fut in as_completed(futures, timeout=120):
            stock = futures[fut]
            try:
                thesis = fut.result()
            except Exception:
                thesis = {"thesis": "AI analysis unavailable.", "strengths": [], "risks": [], "catalyst": "", "invalidation": ""}

            # Attach news sentiment inline
            sym_ns = stock.get("symbol_ns", stock.get("symbol", "") + ".NS")
            sent   = sentiments_map.get(sym_ns, {})
            final_picks.append({
                **stock,
                "ai_thesis":       thesis,
                "news_sentiment":  sent.get("sentiment_label", "NEUTRAL"),
                "news_score":      sent.get("sentiment_score", 0.0),
                "news_catalyst":   sent.get("news_catalyst", False),
                "news_risk":       sent.get("news_risk", False),
                "news_headline":   sent.get("top_headline"),
            })

    # Sort final by win_probability DESC (falls back to conviction_score)
    final_picks.sort(
        key=lambda x: (x.get("win_probability") or x.get("conviction_score", 0)),
        reverse=True,
    )

    elapsed = round(time.time() - t0, 1)
    logger.info(f"Kepler Picks: {len(final_picks)} picks generated in {elapsed}s")

    cats = {
        "swing":      sum(1 for p in final_picks if p.get("category") == "SWING"),
        "momentum":   sum(1 for p in final_picks if p.get("category") == "MOMENTUM"),
        "positional": sum(1 for p in final_picks if p.get("category") == "POSITIONAL"),
        "value":      sum(1 for p in final_picks if p.get("category") == "VALUE"),
    }

    # Summary stats
    prob_values = [p.get("win_probability") for p in final_picks if p.get("win_probability")]
    avg_prob = round(sum(prob_values) / len(prob_values), 1) if prob_values else None
    high_prob_count = sum(1 for p in prob_values if p >= 65)

    return {
        "picks":               final_picks,
        "total":               len(final_picks),
        "category_counts":     cats,
        "nifty_ret_30d":       round(nifty_ret_30d, 2),
        "universe_scanned":    len(PICKS_UNIVERSE),
        "candidates_found":    len(candidates),
        "avg_win_probability": avg_prob,
        "high_prob_picks":     high_prob_count,
        "strategy_leaderboard": strategy_leaderboard,
        "generated_at":        datetime.now().isoformat(),
        "fetched_at":          time.time(),
    }


def get_kepler_picks(force_refresh: bool = False) -> Dict:
    """Public API — returns cached picks or builds fresh."""
    # Try disk cache first
    if not force_refresh:
        cached = _load_picks_cache()
        if cached:
            age = time.time() - cached.get("fetched_at", 0)
            cached["cache_age_s"]   = round(age)
            cached["next_refresh_in"] = max(0, int(_PICKS_TTL - age))
            cached["stale"] = False
            return cached

    # In-memory stale check
    if "picks" in _picks_cache:
        age = time.time() - _picks_cache.get("fetched_at", 0)
        if not force_refresh and age < _PICKS_TTL:
            out = copy.deepcopy(_picks_cache)
            out["cache_age_s"] = round(age)
            out["next_refresh_in"] = max(0, int(_PICKS_TTL - age))
            return out

    fresh = _build_picks()
    _picks_cache.update(fresh)
    _save_picks_cache(fresh)

    out = copy.deepcopy(fresh)
    out["cache_age_s"] = 0
    out["next_refresh_in"] = _PICKS_TTL
    out["stale"] = False
    return out
