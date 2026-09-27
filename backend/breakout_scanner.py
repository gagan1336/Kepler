"""
KEPLER -- Breakout Scanner
Scans 250 curated NSE stocks for professional-grade breakout setups.

APEX Score™ Framework (0–100) — inspired by how India's legendary traders think:
  A (0-20) — Accumulation   : Volume surge = smart money entering silently
  P (0-20) — Price Action   : VCP pattern + proximity to 52W high
  E (0-20) — EMA Structure  : Full 20 > 50 > 200 alignment (trend confirmation)
  X (0-20) — Xtra Momentum  : RSI sweet spot + MACD signal line cross
  S (0-20) — Sector Score   : 30-day outperformance vs Nifty 50

APEX ≥ 75 = HIGH CONVICTION
APEX 55–74 = MODERATE SETUP
APEX < 55  = WATCHLIST ONLY

Patterns detected:
  52W Breakout, VCP (Volatility Contraction), EMA Stack, Volume Surge,
  Momentum, Golden Cross

Uses Gemini 1.5 Flash for structured analysis with support/resistance/stop levels.
"""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import google.generativeai as genai
import numpy as np
import pandas as pd
import yfinance as yf
from loguru import logger
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_fixed

from config import settings
from models import BreakoutWatchlist

try:
    import pandas_ta as ta
    PANDAS_TA_AVAILABLE = True
except ImportError:
    PANDAS_TA_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════════════
# CURATED STOCK UNIVERSE — 250 quality stocks across all key themes
# Organized by sector for the sector heatmap feature
# ═══════════════════════════════════════════════════════════════════════════════

SECTOR_MAP: Dict[str, str] = {}  # symbol → sector (populated at module load)

def _register(sector: str, symbols: List[str]):
    for s in symbols:
        SECTOR_MAP[s] = sector

_register("Banking", [
    "HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN", "INDUSINDBK",
    "BANKBARODA", "CANBK", "PNB", "FEDERALBNK", "IDFCFIRSTB", "BANDHANBNK",
    "RBLBANK", "YESBANK", "UJJIVANSFB", "EQUITASBNK",
])
_register("NBFC", [
    "BAJFINANCE", "BAJAJFINSV", "CHOLAFIN", "MUTHOOTFIN", "MANAPPURAM",
    "LICHSGFIN", "HDFCAMC", "NIPPONLIFEIN", "UTIAMC", "ANGELONE", "MOTILALOFS",
])
_register("IT", [
    "TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "MPHASIS",
    "PERSISTENT", "COFORGE", "LTTS", "OFSS", "TATAELXSI", "KPIT",
])
_register("Pharma", [
    "SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "LUPIN", "AUROPHARMA",
    "ALKEM", "IPCALAB", "TORNTPHARM", "ZYDUSLIFE", "BIOCON", "NATCOPHARM",
    "LALPATHLAB", "METROPOLIS", "MAXHEALTH", "FORTIS", "SYNGENE", "ABBOTINDIA",
    "GLENMARK",
])
_register("Auto", [
    "MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "HEROMOTOCO", "TVSMOTORS",
    "EICHERMOT", "ASHOKLEY", "BOSCHLTD", "MOTHERSON", "TIINDIA", "BHARATFORG",
    "APOLLOTYRE", "MRF", "CEATLTD", "BALKRISIND",
])
_register("FMCG", [
    "HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO",
    "COLPAL", "GODREJCP", "EMAMILTD", "TATACONSUM", "PATANJALI",
])
_register("Retail", [
    "DMART", "TRENT", "ABFRL", "KALYANKJIL", "SENCO", "TITAN", "JUBLFOOD",
    "WESTLIFE", "DEVYANI",
])
_register("Oil & Gas", [
    "RELIANCE", "ONGC", "BPCL", "IOC", "HINDPETRO", "GAIL", "PETRONET",
    "MGL", "IGL", "CASTROLIND",
])
_register("Metals", [
    "TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "SAIL", "NMDC",
    "HINDZINC", "NATIONALUM", "COALINDIA",
])
_register("Cement", [
    "ULTRACEMCO", "SHREECEM", "AMBUJACEM", "ACC", "JKCEMENT", "RAMCOCEM",
    "DALMIACHIN",
])
_register("Capital Goods", [
    "LT", "SIEMENS", "HAVELLS", "ABB", "BHEL", "POLYCAB", "KEI",
    "KALPATPOWR", "KEC", "NCC", "NBCC", "PFC", "RECLTD", "IRFC",
])
_register("Defence", [
    "HAL", "BEL", "BHEL", "BEML", "GRSE", "COCHINSHIP", "MAZDOCK",
    "SOLARINDS",
])
_register("Railways", [
    "IRCTC", "CONCOR", "RVNL", "RAILTEL", "IRCON",
])
_register("Power", [
    "POWERGRID", "NTPC", "TATAPOWER", "TORNTPOWER", "CESC", "ADANIPOWER",
    "ADANITRANS", "NHPC", "SJVN", "JPPOWER", "INOXWIND",
])
_register("Real Estate", [
    "DLF", "GODREJPROP", "OBEROIRLTY", "PRESTIGE", "PHOENIXLTD",
])
_register("Chemicals", [
    "DEEPAKNTR", "SRF", "PIIND", "GNFC", "AARTI", "TATACHEM", "UPL",
    "COROMANDEL", "BALRAMCHIN",
])
_register("Consumer Electronics", [
    "DIXON", "AMBER", "KAYNES", "VOLTAS", "BLUESTARCO", "CROMPTON",
    "WHIRLPOOL",
])
_register("Telecom", [
    "BHARTIARTL", "TATACOMM", "HFCL", "STLTECH", "RAILTEL",
])
_register("Paints", [
    "ASIANPAINT", "BERGEPAINT", "PIDILITIND",
])
_register("Conglomerate", [
    "ADANIENT", "ADANIPORTS", "ADANIGREEN", "GRASIM", "TATACHEM",
])

# Full universe — all registered symbols
UNIVERSE: List[str] = list(SECTOR_MAP.keys())
logger.debug(f"Breakout universe: {len(UNIVERSE)} stocks across {len(set(SECTOR_MAP.values()))} sectors")


# ═══════════════════════════════════════════════════════════════════════════════
# INDICATOR ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def _rsi(close: pd.Series, period: int = 14) -> float:
    """Wilder's smoothing RSI."""
    delta = close.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta.clip(upper=0))
    avg_g = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_l = loss.ewm(com=period - 1, min_periods=period).mean()
    rs    = avg_g / avg_l.replace(0, np.nan)
    rsi_s = 100 - (100 / (1 + rs))
    v = rsi_s.iloc[-1]
    return float(v) if not pd.isna(v) else 50.0


def _atr(df: pd.DataFrame, period: int = 14) -> float:
    """Average True Range."""
    high  = df["High"]
    low   = df["Low"]
    close = df["Close"]
    tr    = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low  - close.shift()).abs(),
    ], axis=1).max(axis=1)
    atr_v = tr.ewm(com=period - 1, min_periods=period).mean().iloc[-1]
    return float(atr_v) if not pd.isna(atr_v) else 0.0


def _macd(close: pd.Series) -> Tuple[float, float, bool]:
    """MACD (12,26,9). Returns (macd_line, signal_line, is_above_signal)."""
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line   = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    m  = float(macd_line.iloc[-1])
    s  = float(signal_line.iloc[-1])
    return m, s, m > s


def _vcp_score(close: pd.Series) -> float:
    """
    Volatility Contraction Pattern score.
    Ratio of recent 10-bar std-dev to prior 20-bar std-dev.
    Lower = tighter consolidation = better VCP.
    """
    if len(close) < 35:
        return 1.0
    recent_std = float(close.iloc[-10:].std())
    prior_std  = float(close.iloc[-30:-10].std())
    if prior_std == 0:
        return 1.0
    return round(recent_std / prior_std, 3)


def _calculate_indicators(df: pd.DataFrame, nifty_return_30d: float) -> Optional[Dict[str, Any]]:
    """
    Compute all APEX indicators from OHLCV data.
    Returns None if data is insufficient.
    """
    if df is None or len(df) < 70:
        return None

    try:
        close  = df["Close"].dropna()
        volume = df["Volume"].dropna()
        high   = df["High"].dropna()
        low    = df["Low"].dropna()

        if len(close) < 60:
            return None

        current_price = float(close.iloc[-1])

        # ── Price / 52W metrics ──────────────────────────────────────────────
        high_52w = float(high.tail(252).max())
        low_52w  = float(low.tail(252).min())
        pct_from_52w_high = ((high_52w - current_price) / high_52w) * 100

        # ── Volume ───────────────────────────────────────────────────────────
        avg_vol_20   = float(volume.tail(20).mean())
        today_vol    = float(volume.iloc[-1])
        volume_ratio = today_vol / avg_vol_20 if avg_vol_20 > 0 else 0

        # ── EMAs ─────────────────────────────────────────────────────────────
        ema20  = float(close.ewm(span=20,  adjust=False).mean().iloc[-1])
        ema50  = float(close.ewm(span=50,  adjust=False).mean().iloc[-1])
        ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1])

        # ── RSI, ATR, MACD, VCP ──────────────────────────────────────────────
        rsi = _rsi(close)
        atr = _atr(df)
        macd_val, macd_sig, macd_above = _macd(close)
        vcp = _vcp_score(close)

        # ── Relative strength vs Nifty (30-day) ─────────────────────────────
        stock_return_30d = 0.0
        if len(close) >= 31:
            stock_return_30d = ((float(close.iloc[-1]) - float(close.iloc[-31])) / float(close.iloc[-31])) * 100

        sector_rs = 1.0
        if nifty_return_30d != 0:
            sector_rs = round((1 + stock_return_30d / 100) / (1 + nifty_return_30d / 100), 3)

        # ── Stop loss level (1.5 × ATR below current price) ──────────────────
        stop_loss = round(current_price - 1.5 * atr, 2)

        # ── Golden Cross detection (50DMA crossed 200DMA in last 10 sessions) ─
        ema50_series  = close.ewm(span=50,  adjust=False).mean()
        ema200_series = close.ewm(span=200, adjust=False).mean()
        golden_cross = False
        if len(ema50_series) >= 11:
            prev_diff = float(ema50_series.iloc[-11]) - float(ema200_series.iloc[-11])
            curr_diff = float(ema50_series.iloc[-1])  - float(ema200_series.iloc[-1])
            golden_cross = prev_diff < 0 and curr_diff > 0

        return {
            "current_price":     round(current_price, 2),
            "high_52w":          round(high_52w, 2),
            "low_52w":           round(low_52w, 2),
            "pct_from_52w_high": round(pct_from_52w_high, 2),
            "volume_ratio":      round(volume_ratio, 2),
            "avg_vol_20":        int(avg_vol_20),
            "today_vol":         int(today_vol),
            "rsi":               round(rsi, 1),
            "ema20":             round(ema20, 2),
            "ema50":             round(ema50, 2),
            "ema200":            round(ema200, 2),
            "atr":               round(atr, 2),
            "macd":              round(macd_val, 4),
            "macd_signal":       round(macd_sig, 4),
            "macd_above_signal": macd_above,
            "vcp_score":         vcp,
            "stock_return_30d":  round(stock_return_30d, 2),
            "sector_rs":         sector_rs,
            "stop_loss":         stop_loss,
            "golden_cross":      golden_cross,
        }
    except Exception as e:
        logger.debug(f"Indicator error: {e}")
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# APEX SCORE COMPUTATION
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_apex(ind: Dict[str, Any]) -> Tuple[int, Dict[str, int], List[str]]:
    """
    Compute APEX score (0-100) and pattern tags.
    Returns (apex_score, breakdown_dict, pattern_tags).
    """
    breakdown = {"A": 0, "P": 0, "E": 0, "X": 0, "S": 0}
    patterns: List[str] = []

    # ── A: Accumulation (Volume surge) ──────────────────────────────────────
    vr = ind["volume_ratio"]
    if vr >= 3.0:   breakdown["A"] = 20
    elif vr >= 2.0: breakdown["A"] = 16
    elif vr >= 1.5: breakdown["A"] = 12
    elif vr >= 1.2: breakdown["A"] = 7
    if vr >= 2.5:
        patterns.append("Volume Surge")

    # ── P: Price Action (52W proximity + VCP) ───────────────────────────────
    dist = ind["pct_from_52w_high"]
    vcp  = ind["vcp_score"]
    if dist <= 0.5:    breakdown["P"] = 18
    elif dist <= 1.5:  breakdown["P"] = 15
    elif dist <= 3.0:  breakdown["P"] = 11
    elif dist <= 5.0:  breakdown["P"] = 7
    elif dist <= 8.0:  breakdown["P"] = 3
    # VCP bonus (tight consolidation near highs)
    if vcp < 0.35 and dist <= 5.0:
        breakdown["P"] = min(20, breakdown["P"] + 5)
        patterns.append("VCP")
    if dist <= 1.0:
        patterns.append("52W Breakout")

    # ── E: EMA Structure ────────────────────────────────────────────────────
    cp   = ind["current_price"]
    e20  = ind["ema20"]
    e50  = ind["ema50"]
    e200 = ind["ema200"]
    if cp > e20 > e50 > e200:
        breakdown["E"] = 20
        patterns.append("EMA Stack")
    elif cp > e20 > e50:
        breakdown["E"] = 13
    elif cp > e20:
        breakdown["E"] = 7

    # Golden Cross bonus
    if ind.get("golden_cross"):
        breakdown["E"] = min(20, breakdown["E"] + 4)
        patterns.append("Golden Cross")

    # ── X: Xtra Momentum (RSI + MACD) ───────────────────────────────────────
    rsi = ind["rsi"]
    if 62 <= rsi <= 72:   breakdown["X"] = 15   # ideal momentum zone
    elif 55 <= rsi < 62:  breakdown["X"] = 11
    elif 50 <= rsi < 55:  breakdown["X"] = 7
    elif 45 <= rsi < 50:  breakdown["X"] = 3
    if ind["macd_above_signal"]:
        breakdown["X"] = min(20, breakdown["X"] + 5)
    if rsi >= 65 and ind["macd_above_signal"]:
        patterns.append("Momentum")

    # ── S: Sector/Relative Strength ─────────────────────────────────────────
    rs = ind["sector_rs"]
    if rs >= 1.08:    breakdown["S"] = 20
    elif rs >= 1.04:  breakdown["S"] = 14
    elif rs >= 1.01:  breakdown["S"] = 8
    elif rs >= 0.98:  breakdown["S"] = 3

    apex = sum(breakdown.values())

    # APEX conviction tier
    if apex >= 75:
        conviction = "HIGH"
    elif apex >= 55:
        conviction = "MODERATE"
    else:
        conviction = "WATCHLIST"

    return apex, breakdown, patterns, conviction


# ═══════════════════════════════════════════════════════════════════════════════
# FILTER
# ═══════════════════════════════════════════════════════════════════════════════

def _passes_filter(ind: Dict[str, Any], apex: int) -> bool:
    """
    Minimum bar for inclusion in the watchlist.
    APEX ≥ 40 + price above EMA20 + within 10% of 52W high + RSI > 40.
    """
    return (
        apex >= 40
        and ind["pct_from_52w_high"] <= 10.0
        and ind["current_price"] > ind["ema20"]
        and ind["rsi"] >= 42
        and ind["volume_ratio"] >= 1.1
    )


# ═══════════════════════════════════════════════════════════════════════════════
# GEMINI ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════

def _build_apex_prompt(candidates: List[Tuple]) -> str:
    lines = [
        "You are a professional Indian stock market technical analyst.\n"
        "Analyze each stock setup below. For EACH stock produce a concise 3-sentence analysis:\n"
        "  Sentence 1: Describe the chart pattern and what it signals about accumulation / momentum.\n"
        "  Sentence 2: State the key support level and the resistance level to watch for breakout confirmation.\n"
        "  Sentence 3: State what would INVALIDATE this setup (a close below which level signals risk).\n\n"
        "STRICT RULES:\n"
        "  - NEVER use: buy, sell, purchase, invest, profit, guaranteed, target price\n"
        "  - All analysis is purely educational, not financial advice\n"
        "  - Mention specific price levels (₹) from the data provided\n\n"
        "Return a JSON array ONLY — no markdown, no explanation:\n"
        '[{"symbol":"X","analysis":"...","pattern_name":"..."}]\n\n'
        "STOCKS:\n"
    ]
    for symbol, company, ind, apex, breakdown, patterns, conviction, sector in candidates:
        lines.append(
            f"Symbol: {symbol} | Company: {company} | Sector: {sector}\n"
            f"APEX Score: {apex}/100 ({conviction}) | Patterns: {', '.join(patterns) or 'None'}\n"
            f"Price: ₹{ind['current_price']} | 52W High: ₹{ind['high_52w']} | Distance: {ind['pct_from_52w_high']}%\n"
            f"RSI: {ind['rsi']} | Volume: {ind['volume_ratio']}× avg | MACD above signal: {ind['macd_above_signal']}\n"
            f"EMA20: ₹{ind['ema20']} | EMA50: ₹{ind['ema50']} | EMA200: ₹{ind['ema200']}\n"
            f"ATR: ₹{ind['atr']} | Suggested stop: ₹{ind['stop_loss']} | VCP score: {ind['vcp_score']}\n"
            f"30-day return: {ind['stock_return_30d']}% | Nifty RS: {ind['sector_rs']}×\n\n"
        )
    return "".join(lines)


@retry(stop=stop_after_attempt(2), wait=wait_fixed(15))
def _call_gemini(prompt: str) -> str:
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(temperature=0.25, max_output_tokens=6000),
    )
    return response.text


def _parse_gemini(raw: str, candidates: List[Tuple]) -> Dict[str, Dict]:
    raw = raw.strip()
    try:
        items = json.loads(raw)
    except Exception:
        raw = re.sub(r"```(?:json)?", "", raw).strip()
        start, end = raw.find("["), raw.rfind("]")
        try:
            items = json.loads(raw[start:end + 1]) if start != -1 else []
        except Exception:
            items = []

    mapping: Dict[str, Dict] = {}
    for item in items:
        if isinstance(item, dict):
            sym = item.get("symbol", "").upper().replace(".NS", "")
            analysis = item.get("analysis", "")
            pattern_name = item.get("pattern_name", "")
            if sym and analysis:
                mapping[sym] = {"analysis": analysis, "pattern_name": pattern_name}

    # Fallback for any missing
    for symbol, company, ind, apex, breakdown, patterns, conviction, sector in candidates:
        if symbol not in mapping:
            mapping[symbol] = {
                "analysis": (
                    f"{company} is trading at ₹{ind['current_price']}, within "
                    f"{ind['pct_from_52w_high']:.1f}% of its 52-week high of ₹{ind['high_52w']}, "
                    f"with volume at {ind['volume_ratio']:.1f}× the 20-day average — suggesting "
                    f"accumulation. Key resistance is the 52W high at ₹{ind['high_52w']}; "
                    f"support sits near EMA20 at ₹{ind['ema20']:.0f}. "
                    f"A close below ₹{ind['stop_loss']} would invalidate the current setup. "
                    "⚠️ Educational analysis only — not investment advice."
                ),
                "pattern_name": ", ".join(patterns) if patterns else "Pre-Breakout",
            }
    return mapping


# ═══════════════════════════════════════════════════════════════════════════════
# PARALLEL FETCH
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_one(symbol: str, nifty_return_30d: float) -> Tuple[str, Optional[Dict]]:
    """Fetch + compute indicators for one symbol."""
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        df = ticker.history(period="1y", auto_adjust=True)
        if df is None or df.empty or len(df) < 70:
            return symbol, None
        return symbol, _calculate_indicators(df, nifty_return_30d)
    except Exception as e:
        logger.debug(f"{symbol}: fetch failed — {e}")
        return symbol, None


def _fetch_nifty_return() -> float:
    """Get Nifty 50's 30-day return for relative strength calculation."""
    try:
        nifty = yf.Ticker("^NSEI")
        hist  = nifty.history(period="35d", interval="1d").dropna(subset=["Close"])
        if len(hist) >= 31:
            r30 = ((float(hist["Close"].iloc[-1]) - float(hist["Close"].iloc[-31])) /
                   float(hist["Close"].iloc[-31])) * 100
            logger.info(f"Nifty 30-day return: {r30:.2f}%")
            return r30
    except Exception as e:
        logger.warning(f"Could not fetch Nifty return: {e}")
    return 5.0  # assume modest positive return as fallback


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SCANNER
# ═══════════════════════════════════════════════════════════════════════════════

def scan_breakouts(db: Session, test_mode: bool = False) -> List[BreakoutWatchlist]:
    """
    Main entry point. Parallel scan → APEX scoring → Gemini analysis → DB save.
    """
    today = date.today()
    logger.info(f"=== APEX Breakout Scan started — {today} ===")

    symbols = list(UNIVERSE)
    if test_mode:
        symbols = symbols[:30]
        logger.info("TEST MODE: scanning first 30 symbols")

    # Step 1: Get Nifty 30-day return for relative strength
    nifty_return = _fetch_nifty_return()

    # Step 2: Parallel fetch all tickers
    logger.info(f"Fetching {len(symbols)} stocks in parallel…")
    t0 = time.time()
    raw_results: Dict[str, Optional[Dict]] = {}

    with ThreadPoolExecutor(max_workers=min(len(symbols), 20), thread_name_prefix="bkout") as pool:
        futures = {pool.submit(_fetch_one, sym, nifty_return): sym for sym in symbols}
        done = 0
        for fut in as_completed(futures):
            sym, data = fut.result()
            raw_results[sym] = data
            done += 1
            if done % 30 == 0:
                logger.info(f"  … {done}/{len(symbols)} fetched")

    elapsed = round(time.time() - t0, 1)
    logger.info(f"Fetched {len(raw_results)} stocks in {elapsed}s")

    # Step 3: Compute APEX scores and filter
    candidates = []
    for symbol, ind in raw_results.items():
        if ind is None:
            continue
        apex, breakdown, patterns, conviction = _compute_apex(ind)
        if _passes_filter(ind, apex):
            sector = SECTOR_MAP.get(symbol, "Other")
            candidates.append((symbol, symbol, ind, apex, breakdown, patterns, conviction, sector))

    logger.info(f"APEX filter: {len(candidates)} candidates passed (from {len([v for v in raw_results.values() if v])} valid stocks)")

    # Sort by APEX score descending
    candidates.sort(key=lambda x: x[3], reverse=True)
    # Cap at top 30 setups
    candidates = candidates[:30]

    # Step 4: Fetch company names for top candidates
    for i, (symbol, _, ind, apex, breakdown, patterns, conviction, sector) in enumerate(candidates):
        try:
            info = yf.Ticker(f"{symbol}.NS").info
            company_name = info.get("longName") or info.get("shortName") or symbol
            candidates[i] = (symbol, company_name, ind, apex, breakdown, patterns, conviction, sector)
        except Exception:
            pass

    # Step 5: Gemini analysis (single batched call)
    ai_results: Dict[str, Dict] = {}
    if settings.gemini_api_key and candidates:
        try:
            prompt = _build_apex_prompt(candidates)
            raw = _call_gemini(prompt)
            ai_results = _parse_gemini(raw, candidates)
            logger.info(f"Gemini analysis done: {len(ai_results)} descriptions")
        except Exception as e:
            logger.error(f"Gemini call failed: {e} — using fallback descriptions")
            ai_results = _parse_gemini("", candidates)

    # Step 6: Save to DB
    # Delete today's existing entries first to avoid duplicates on re-run
    db.query(BreakoutWatchlist).filter(BreakoutWatchlist.date == today).delete()
    db.commit()

    saved = []
    for symbol, company_name, ind, apex, breakdown, patterns, conviction, sector in candidates:
        ai = ai_results.get(symbol, {})
        technical_data = {
            **ind,
            "apex_score":    apex,
            "apex_breakdown": breakdown,
            "apex_conviction": conviction,
            "pattern_tags":  patterns,
            "sector":        sector,
            "ai_pattern_name": ai.get("pattern_name", ", ".join(patterns) if patterns else "Pre-Breakout"),
        }
        entry = BreakoutWatchlist(
            date=today,
            symbol=symbol,
            company_name=company_name,
            setup_description=ai.get("analysis", "") + "\n\n⚠️ Educational analysis only — not investment advice. Consult a SEBI-registered investment advisor.",
            technical_data=technical_data,
        )
        db.add(entry)
        saved.append(entry)

    db.commit()
    logger.info(f"✅ Saved {len(saved)} APEX breakout setups")
    logger.info(f"   HIGH: {sum(1 for _, _, _, a, *_ in candidates if a >= 75)} | "
                f"MODERATE: {sum(1 for _, _, _, a, *_ in candidates if 55 <= a < 75)} | "
                f"WATCHLIST: {sum(1 for _, _, _, a, *_ in candidates if a < 55)}")
    return saved


# ═══════════════════════════════════════════════════════════════════════════════
# CLI TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from database import SessionLocal
    db = SessionLocal()
    try:
        results = scan_breakouts(db, test_mode=True)
        print(f"\n{'='*70}")
        print(f"APEX Breakout Scan Complete — {len(results)} setups")
        print(f"{'='*70}")
        for r in results:
            tech = r.technical_data or {}
            apex = tech.get("apex_score", 0)
            conv = tech.get("apex_conviction", "?")
            tag  = ", ".join(tech.get("pattern_tags", []))
            print(f"\n[{apex:3d}/100 {conv:8s}] {r.symbol:15s} {r.company_name[:30]}")
            print(f"  Sector: {tech.get('sector')} | Patterns: {tag}")
            print(f"  Price: ₹{tech.get('current_price')} | 52W High: ₹{tech.get('high_52w')} | Stop: ₹{tech.get('stop_loss')}")
            print(f"  RSI: {tech.get('rsi')} | Vol: {tech.get('volume_ratio')}x | VCP: {tech.get('vcp_score')}")
            if r.setup_description:
                print(f"  Analysis: {r.setup_description[:150]}…")
    finally:
        db.close()
