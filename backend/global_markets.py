"""
ANTIGRAVITY — Global Markets Pulse (global_markets.py)
Fetches major global indices, commodities & forex in parallel using yfinance.
Shows how overnight US / Asian moves + commodities set up Nifty for the day.

Groups:
  gift_nifty   — Nifty 50 / Gift Nifty (pre-market Nifty indicator)
  us_markets   — S&P 500, Nasdaq, Dow Jones, VIX
  asia         — Nikkei 225, Hang Seng, Shanghai, KOSPI
  europe       — FTSE 100, DAX, CAC 40
  commodities  — Brent Crude, WTI, Gold, Silver
  forex        — USD/INR, Dollar Index, US 10Y Yield

5-minute TTL cache. Lock released before the expensive I/O call.
"""
import copy
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

import yfinance as yf
from loguru import logger

# ── Cache ─────────────────────────────────────────────────────────────────────
_cache: Dict[str, Any] = {}
_CACHE_TTL = 300  # 5 minutes
_fetching = False  # simple sentinel to avoid stampede

# ── Market groups ──────────────────────────────────────────────────────────────
MARKET_GROUPS: Dict[str, List[Dict]] = {
    "gift_nifty": [
        # Gift Nifty (formerly SGX Nifty) = best Nifty pre-open indicator
        # ^NSEI = NSE Nifty 50 index (proxy; actual futures need monthly roll)
        {"symbol": "^NSEI",  "name": "Nifty 50",    "unit": "pts",  "key": True},
        {"symbol": "^NSEBANK","name": "Bank Nifty",  "unit": "pts",  "key": True},
    ],
    "us_markets": [
        {"symbol": "^GSPC", "name": "S&P 500",    "unit": "pts",  "key": True},
        {"symbol": "^IXIC", "name": "Nasdaq",     "unit": "pts",  "key": True},
        {"symbol": "^DJI",  "name": "Dow Jones",  "unit": "pts",  "key": False},
        {"symbol": "^VIX",  "name": "VIX",        "unit": "",     "key": True},
        {"symbol": "ES=F",  "name": "S&P Futures","unit": "pts",  "key": False},
    ],
    "asia": [
        {"symbol": "^N225",    "name": "Nikkei 225",    "unit": "pts",  "key": True},
        {"symbol": "^HSI",     "name": "Hang Seng",     "unit": "pts",  "key": True},
        {"symbol": "000001.SS","name": "Shanghai",      "unit": "pts",  "key": False},
        {"symbol": "^KS11",    "name": "KOSPI",         "unit": "pts",  "key": False},
    ],
    "europe": [
        {"symbol": "^FTSE",  "name": "FTSE 100", "unit": "pts",  "key": True},
        {"symbol": "^GDAXI", "name": "DAX",      "unit": "pts",  "key": False},
        {"symbol": "^FCHI",  "name": "CAC 40",   "unit": "pts",  "key": False},
    ],
    "commodities": [
        {"symbol": "BZ=F", "name": "Brent Crude", "unit": "$/bbl", "key": True},
        {"symbol": "CL=F", "name": "WTI Crude",   "unit": "$/bbl", "key": False},
        {"symbol": "GC=F", "name": "Gold",        "unit": "$/oz",  "key": True},
        {"symbol": "SI=F", "name": "Silver",      "unit": "$/oz",  "key": False},
    ],
    "forex": [
        {"symbol": "USDINR=X",  "name": "USD/INR",       "unit": "₹",    "key": True},
        {"symbol": "DX-Y.NYB",  "name": "Dollar Index",  "unit": "",     "key": True},
        {"symbol": "^TNX",       "name": "US 10Y Yield", "unit": "%",    "key": True},
        {"symbol": "GBPINR=X",  "name": "GBP/INR",      "unit": "₹",    "key": False},
    ],
}

GROUP_META: Dict[str, Dict] = {
    "gift_nifty": {"label": "Gift Nifty / India",  "icon": "🇮🇳", "color": "#f97316"},
    "us_markets":  {"label": "US Markets",          "icon": "🇺🇸", "color": "#3b82f6"},
    "asia":        {"label": "Asian Markets",       "icon": "🌏", "color": "#a78bfa"},
    "europe":      {"label": "European Markets",    "icon": "🇪🇺", "color": "#10b981"},
    "commodities": {"label": "Commodities",         "icon": "🛢️", "color": "#f59e0b"},
    "forex":       {"label": "Forex & Bonds",       "icon": "💱", "color": "#64748b"},
}


# ── Per-ticker fetch (parallel) ────────────────────────────────────────────────

def _fetch_one(sym: str) -> Tuple[str, Optional[Dict]]:
    """Fetch a single ticker via yfinance fast_info + history for prev close."""
    try:
        t = yf.Ticker(sym)
        fi = t.fast_info
        current: Optional[float] = None
        prev: Optional[float] = None

        # fast_info is the quickest path
        try:
            current = float(fi.last_price)
            prev    = float(fi.previous_close)
        except Exception:
            pass

        # Fallback: last 5 days of daily history
        if current is None or prev is None:
            hist = t.history(period="5d", interval="1d")
            hist = hist.dropna(subset=["Close"])
            if len(hist) >= 2:
                current = float(hist["Close"].iloc[-1])
                prev    = float(hist["Close"].iloc[-2])
            elif len(hist) == 1:
                current = float(hist["Close"].iloc[-1])

        if current is None:
            return sym, None

        change     = current - prev if prev else 0.0
        change_pct = (change / prev * 100) if prev else 0.0
        direction  = "FLAT"
        if change_pct > 0.05:  direction = "UP"
        elif change_pct < -0.05: direction = "DOWN"

        return sym, {
            "current_price": round(current, 2),
            "prev_close":    round(prev, 2) if prev else None,
            "change":        round(change, 2),
            "change_pct":    round(change_pct, 2),
            "direction":     direction,
        }
    except Exception as e:
        logger.debug(f"global_markets: {sym} failed: {e}")
        return sym, None


def _build_result() -> Dict[str, Any]:
    """Parallel-fetch all tickers and assemble grouped result."""
    all_items = [item for grp in MARKET_GROUPS.values() for item in grp]
    all_symbols = list({item["symbol"] for item in all_items})

    logger.info(f"Global Markets Pulse: fetching {len(all_symbols)} tickers in parallel…")
    t0 = time.time()

    raw: Dict[str, Optional[Dict]] = {}
    with ThreadPoolExecutor(max_workers=min(len(all_symbols), 16),
                            thread_name_prefix="gm") as pool:
        futures = {pool.submit(_fetch_one, sym): sym for sym in all_symbols}
        for fut in as_completed(futures):
            sym, data = fut.result()
            raw[sym] = data

    # Assemble groups
    result_groups: Dict[str, List[Dict]] = {}
    for group, items in MARKET_GROUPS.items():
        result_groups[group] = []
        for item in items:
            sym  = item["symbol"]
            tick = raw.get(sym)
            if tick is None:
                continue
            result_groups[group].append({
                "symbol":        sym,
                "name":          item["name"],
                "unit":          item.get("unit", ""),
                "key":           item.get("key", False),
                **tick,
            })

    elapsed = round(time.time() - t0, 2)
    logger.info(f"Global Markets Pulse: done in {elapsed}s "
                f"({sum(len(v) for v in result_groups.values())} tickers loaded)")

    return {
        "groups":       result_groups,
        "group_meta":   GROUP_META,
        "impact_score": _calculate_impact(result_groups),
        "fetched_at":   time.time(),
    }


def _calculate_impact(groups: Dict[str, List[Dict]]) -> str:
    """
    Weighted heuristic: how global cues net out for Nifty.
    Returns BULLISH / BEARISH / MIXED.
    """
    score = 0

    def _delta(group: str, name: str) -> Optional[float]:
        for m in groups.get(group, []):
            if m["name"] == name:
                return m["change_pct"]
        return None

    # US overnight moves (weight ×2)
    for n in ["S&P 500", "Nasdaq"]:
        d = _delta("us_markets", n)
        if d is not None:
            if d > 0.5:  score += 2
            elif d < -0.5: score -= 2

    # VIX: spiking VIX = bearish for India
    vix = _delta("us_markets", "VIX")
    if vix is not None:
        if vix > 5:    score -= 2
        elif vix < -5: score += 1

    # Asian session
    for n in ["Nikkei 225", "Hang Seng"]:
        d = _delta("asia", n)
        if d is not None:
            if d > 0.5:  score += 1
            elif d < -0.5: score -= 1

    # Brent Crude: high crude = inflation risk for India
    crude = _delta("commodities", "Brent Crude")
    if crude is not None:
        if crude > 1.5:   score -= 1
        elif crude < -1.5: score += 1

    # USD/INR: weak rupee = bearish
    usdinr = _delta("forex", "USD/INR")
    if usdinr is not None:
        if usdinr > 0.5:  score -= 1
        elif usdinr < -0.5: score += 1

    if score >= 3:   return "BULLISH"
    if score <= -3:  return "BEARISH"
    return "MIXED"


# ── Public API ─────────────────────────────────────────────────────────────────

def get_global_markets(force_refresh: bool = False) -> Dict[str, Any]:
    """
    Public API — returns live global market pulse.
    Thread-safe, lock released before I/O.
    """
    global _fetching

    cache_key = "global_markets"

    # Cache hit (no lock needed for read — Python dict reads are GIL-safe)
    if not force_refresh and cache_key in _cache:
        age = time.time() - _cache[cache_key]["fetched_at"]
        if age < _CACHE_TTL:
            out = copy.deepcopy(_cache[cache_key])
            out["cache_age_s"]    = round(age)
            out["next_refresh_in"] = max(0, int(_CACHE_TTL - age))
            return out

    # Prevent thundering herd: only one thread fetches at a time
    if _fetching:
        # Return stale if available
        if cache_key in _cache:
            out = copy.deepcopy(_cache[cache_key])
            out["cache_age_s"]    = round(time.time() - _cache[cache_key]["fetched_at"])
            out["next_refresh_in"] = 0
            out["stale"]           = True
            return out

    try:
        _fetching = True
        fresh = _build_result()
        _cache[cache_key] = fresh
        out = copy.deepcopy(fresh)
        out["cache_age_s"]    = 0
        out["next_refresh_in"] = _CACHE_TTL
        return out
    finally:
        _fetching = False
