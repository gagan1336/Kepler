"""
KEPLER -- Ticker Validator
Cross-references AI-extracted tickers against the live Nifty 500 list.
Fuzzy-matches common wrong extractions (e.g. TATAMOTORS → TATAMOTORS, WIPRO → WIPRO).
Falls back to hardcoded set if NSE fetch fails.
"""
import time
from difflib import get_close_matches
from typing import List, Set, Optional
from loguru import logger

# Cached Nifty 500 symbols
_valid_symbols: Optional[Set[str]] = None
_last_fetch_ts: float = 0
_CACHE_TTL = 86400  # 24 hours


def _load_nifty500_symbols() -> Set[str]:
    """Fetch live Nifty 500 list from NSE. Falls back to hardcoded set."""
    global _valid_symbols, _last_fetch_ts

    now = time.time()
    if _valid_symbols and (now - _last_fetch_ts) < _CACHE_TTL:
        return _valid_symbols

    try:
        import requests
        resp = requests.get(
            "https://archives.nseindia.com/content/indices/ind_nifty500list.csv",
            timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        if resp.status_code == 200:
            lines = resp.text.strip().split("\n")
            symbols = set()
            for line in lines[1:]:
                parts = line.split(",")
                if len(parts) >= 3:
                    sym = parts[2].strip().strip('"').upper()
                    if sym:
                        symbols.add(sym)
            if symbols:
                _valid_symbols = symbols
                _last_fetch_ts = now
                logger.info(f"Ticker validator: loaded {len(symbols)} symbols from NSE")
                return _valid_symbols
    except Exception as e:
        logger.warning(f"Ticker validator: could not fetch live Nifty 500 ({e}) — using fallback")

    # Hardcoded fallback (top 100 most-mentioned NSE symbols)
    _valid_symbols = {
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "BHARTIARTL", "ICICIBANK", "KOTAKBANK",
        "HINDUNILVR", "ITC", "LT", "SBIN", "BAJFINANCE", "ASIANPAINT", "MARUTI",
        "AXISBANK", "SUNPHARMA", "TITAN", "WIPRO", "ULTRACEMCO", "NESTLEIND",
        "POWERGRID", "NTPC", "ONGC", "COALINDIA", "TECHM", "HCLTECH", "DRREDDY",
        "BAJAJFINSV", "GRASIM", "ADANIENT", "JSWSTEEL", "TATASTEEL", "HINDALCO",
        "CIPLA", "EICHERMOT", "M&M", "TATACONSUM", "BRITANNIA", "DMART", "DIVISLAB",
        "APOLLOHOSP", "DABUR", "PIDILITIND", "SIEMENS", "HAVELLS", "BERGEPAINT",
        "GODREJCP", "COLPAL", "MOTHERSON", "TORNTPHARM", "LUPIN", "BOSCHLTD",
        "MUTHOOTFIN", "LICHSGFIN", "PNB", "CANBK", "BANKBARODA", "FEDERALBNK",
        "IDFCFIRSTB", "INDUSINDBK", "RBLBANK", "YESBANK", "ADANIPORTS", "ADANIPOWER",
        "ADANIGREEN", "ZOMATO", "NYKAA", "PAYTM", "HDFCLIFE", "SBILIFE", "ICICIPRULI",
        "TATAPOWER", "TRENT", "VEDL", "IRCTC", "CONCOR", "UPL", "PIIND", "COROMANDEL",
        "OFSS", "MPHASIS", "LTIM", "PERSISTENT", "COFORGE", "ASTRAL", "POLYCAB", "KEI",
        "CHOLAFIN", "MANAPPURAM", "BAJAJ-AUTO", "HEROMOTOCO", "TVSMOTORS", "ASHOKLEY",
        "TIINDIA", "BHARATFORG", "ZYDUSLIFE", "ALKEM", "AUROPHARMA", "IPCALAB",
        "JKCEMENT", "RAMCOCEM", "SHREECEM", "AMBUJACEM", "ACC", "SAIL", "NMDC",
        "PAGEIND", "VOLTAS", "JUBLFOOD", "INDIGO", "DIXON", "AMBER", "FORTIS",
        "GODREJPROP", "OBEROIRLTY", "PRESTIGE", "DLF", "BANDHANBNK", "TATAMOTORS",
    }
    _last_fetch_ts = now
    return _valid_symbols


def validate_tickers(extracted: List[str]) -> List[str]:
    """
    Validate and clean a list of AI-extracted NSE tickers.
    - Normalizes to uppercase
    - Drops empty or non-alphabetic symbols
    - Exact-matches against Nifty 500 list
    - Fuzzy-matches close misses (e.g. 'TATAMTR' → 'TATAMOTORS')
    - Returns only valid, unique symbols
    """
    if not extracted:
        return []

    valid = _load_nifty500_symbols()
    result = []
    seen = set()

    for raw in extracted:
        if not raw:
            continue

        sym = raw.upper().strip().replace(".NS", "").replace(".BO", "")

        # Skip obviously wrong extractions
        if len(sym) < 2 or len(sym) > 20:
            continue
        if not any(c.isalpha() for c in sym):
            continue
        if sym in seen:
            continue

        # Exact match
        if sym in valid:
            result.append(sym)
            seen.add(sym)
            continue

        # Fuzzy match (cutoff 0.82 = tolerates 1-2 char typos)
        close = get_close_matches(sym, valid, n=1, cutoff=0.82)
        if close:
            matched = close[0]
            if matched not in seen:
                logger.debug(f"Ticker fuzzy match: {sym} → {matched}")
                result.append(matched)
                seen.add(matched)
        else:
            logger.debug(f"Ticker dropped (no match): {sym}")

    return result


if __name__ == "__main__":
    tests = ["TATAMOTORS", "TATAMTR", "RELIANCE", "HDFC BANK", "RELI", "INFY", "FAKE123", "TCS"]
    print("Validation results:")
    for t in tests:
        res = validate_tickers([t])
        print(f"  {t!r:20} → {res}")
