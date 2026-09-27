"""
KEPLER -- Stock Universe Module
====================================
Provides a COMPLETE searchable database of all NSE-listed + popular BSE stocks.

Strategy (in priority order):
1. Download official NSE EQUITY_L.csv (~2000 stocks) at startup, cache on disk for 24h
2. Merge with curated sector tags from our own mapping
3. For any query not found locally → yfinance Search API fallback (covers BSE + global)
4. Any valid NSE/BSE ticker works even if not in our database (direct yfinance lookup)

Key functions:
  search_universe(query, limit)   → list of {symbol, name, sector, exchange}
  get_symbol_info(symbol)         → {name, sector, exchange} or None
  is_valid_nse_symbol(symbol)     → bool (tries yfinance fast_info)
"""

import csv
import io
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

import requests
import yfinance as yf
from loguru import logger

# ── Paths ─────────────────────────────────────────────────────────────────────
_DIR = os.path.dirname(os.path.abspath(__file__))
_CACHE_DIR = os.path.join(_DIR, "__pycache__")
_NSE_CACHE_FILE = os.path.join(_CACHE_DIR, "nse_equity_list.json")
_NSE_CACHE_TTL_HOURS = 24

# ── HTTP session ───────────────────────────────────────────────────────────────
_session = requests.Session()
_session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
})

# ── In-memory stock universe ───────────────────────────────────────────────────
# symbol → {name, sector, exchange}
_universe: Dict[str, Dict[str, str]] = {}
_universe_loaded = False

# ── Sector tag map (symbol → sector) for well-known stocks ────────────────────
# This enriches the plain NSE CSV data (which has no sector column)
_SECTOR_TAGS: Dict[str, str] = {
    # Nifty 50
    "RELIANCE": "Energy", "TCS": "IT", "HDFCBANK": "Banking", "BHARTIARTL": "Telecom",
    "ICICIBANK": "Banking", "INFY": "IT", "SBIN": "Banking", "HINDUNILVR": "FMCG",
    "ITC": "FMCG", "KOTAKBANK": "Banking", "LT": "Infrastructure", "AXISBANK": "Banking",
    "ASIANPAINT": "Paints", "MARUTI": "Auto", "SUNPHARMA": "Pharma", "ULTRACEMCO": "Cement",
    "BAJFINANCE": "NBFC", "TITAN": "Consumer", "WIPRO": "IT", "NESTLEIND": "FMCG",
    "TATAMOTORS": "Auto", "TATASTEEL": "Metals", "HCLTECH": "IT", "POWERGRID": "Utilities",
    "NTPC": "Utilities", "COALINDIA": "Mining", "ONGC": "Energy", "ADANIENT": "Conglomerate",
    "ADANIPORTS": "Infrastructure", "JSWSTEEL": "Metals", "BAJAJFINSV": "Financial Services",
    "HDFCLIFE": "Insurance", "SBILIFE": "Insurance", "DIVISLAB": "Pharma",
    "DRREDDY": "Pharma", "CIPLA": "Pharma", "EICHERMOT": "Auto", "BAJAJ-AUTO": "Auto",
    "HEROMOTOCO": "Auto", "GRASIM": "Diversified", "INDUSINDBK": "Banking", "TECHM": "IT",
    "UPL": "Agrochemicals", "APOLLOHOSP": "Healthcare", "TATACONSUM": "FMCG",
    "M&M": "Auto", "BRITANNIA": "FMCG",
    # Banking
    "BANKBARODA": "Banking", "PNB": "Banking", "CANBK": "Banking", "FEDERALBNK": "Banking",
    "BANDHANBNK": "Banking", "IDFCFIRSTB": "Banking", "RBLBANK": "Banking",
    "YESBANK": "Banking", "KARURVYSYA": "Banking", "AUBANK": "Banking",
    "DCBBANK": "Banking", "UJJIVANSFB": "Banking", "EQUITASBNK": "Banking",
    "ESAFSFB": "Banking", "MAHABANK": "Banking", "CSBBANK": "Banking",
    "SOUTHBANK": "Banking", "CENTRALBK": "Banking", "UNIONBANK": "Banking",
    "INDIANB": "Banking", "IOB": "Banking", "UCOBANK": "Banking",
    # NBFC
    "LICHSGFIN": "NBFC", "CHOLAFIN": "NBFC", "MUTHOOTFIN": "NBFC", "MANAPPURAM": "NBFC",
    "BAJAJHFL": "NBFC", "PNBHOUSING": "NBFC", "SHRIRAMFIN": "NBFC", "AAVAS": "NBFC",
    "CREDITACC": "NBFC", "SPANDANA": "NBFC", "FUSION": "NBFC", "FIVESTAR": "NBFC",
    # IT
    "LTIM": "IT", "MPHASIS": "IT", "PERSISTENT": "IT", "COFORGE": "IT",
    "HAPPSTMNDS": "IT", "OFSS": "IT", "KPIT": "IT", "TATAELXSI": "IT",
    "BIRLASOFT": "IT", "CYIENT": "IT", "MASTEK": "IT", "HEXAWARE": "IT",
    "TATATECH": "IT", "AFFLE": "IT", "LATENTVIEW": "IT", "RATEGAIN": "IT",
    "NEWGEN": "IT", "INTELLECT": "IT", "TANLA": "IT", "ROUTE": "IT",
    "KPITTECH": "IT", "ZENSARTECH": "IT", "SASKEN": "IT",
    # Pharma
    "LUPIN": "Pharma", "AUROPHARMA": "Pharma", "IPCALAB": "Pharma", "ALKEM": "Pharma",
    "TORNTPHARM": "Pharma", "GLENMARK": "Pharma", "ZYDUSLIFE": "Pharma", "BIOCON": "Pharma",
    "GRANULES": "Pharma", "NATCOPHARM": "Pharma", "LAURUSLABS": "Pharma",
    "JBCHEPHARM": "Pharma", "CAPLIPOINT": "Pharma", "MARKSANS": "Pharma",
    "SEQUENT": "Pharma", "JUBILANT": "Pharma",
    # Auto
    "ASHOKLEY": "Auto", "TVSMOTORS": "Auto", "ESCORTS": "Auto", "VSTTILLERS": "Auto",
    # Auto Ancillary
    "MOTHERSON": "Auto Ancillary", "BOSCHLTD": "Auto Ancillary", "BHARATFORG": "Auto Ancillary",
    "TIINDIA": "Auto Ancillary", "SUNDRMFAST": "Auto Ancillary", "EXIDEIND": "Auto Ancillary",
    "AMARAJABAT": "Auto Ancillary", "APOLLOTYRE": "Auto Ancillary", "MRF": "Auto Ancillary",
    "BALKRISIND": "Auto Ancillary", "CEATLTD": "Auto Ancillary", "JKTYRE": "Auto Ancillary",
    "SONACOMS": "Auto Ancillary", "ENDURANCE": "Auto Ancillary",
    # Metals
    "HINDALCO": "Metals", "VEDL": "Metals", "NMDC": "Metals", "SAIL": "Metals",
    "TATASTEEL": "Metals", "JSWSTEEL": "Metals", "NATIONALUM": "Metals",
    "RATNAMANI": "Metals", "HINDCOPPER": "Metals", "WELCORP": "Metals",
    "JINDALSAW": "Metals", "JSL": "Metals", "SHYAMMETL": "Metals",
    # Energy & Power
    "BPCL": "Energy", "IOC": "Energy", "HPCL": "Energy", "GAIL": "Energy",
    "OIL": "Energy", "TATAPOWER": "Utilities", "NTPC": "Utilities",
    "ADANIGREEN": "Utilities", "ADANIPOWER": "Utilities", "NHPC": "Utilities",
    "SJVN": "Utilities", "TORNTPOWER": "Utilities", "CESC": "Utilities",
    "WAAREE": "Utilities", "PREMIER": "Utilities", "WEBSOL": "Utilities",
    # Chemicals
    "AARTIIND": "Chemicals", "SRF": "Chemicals", "DEEPAKNTR": "Chemicals",
    "NAVINFLUOR": "Chemicals", "PIDILITIND": "Chemicals", "VINATIORG": "Chemicals",
    "ALKYLAMINE": "Chemicals", "FINEORG": "Chemicals", "ROSSARI": "Chemicals",
    "PCBL": "Chemicals", "SUDARSCHEM": "Chemicals", "ATUL": "Chemicals",
    "HIKAL": "Chemicals", "BALAJIAM": "Chemicals", "JUBLINGREA": "Chemicals",
    "LAXMIONLINE": "Chemicals",
    # Cement
    "AMBUJACEM": "Cement", "ACC": "Cement", "SHREECEM": "Cement", "RAMCOCEM": "Cement",
    "JKCEMENT": "Cement", "DALMIACEM": "Cement", "BIRLACORP": "Cement",
    "HEIDELBERG": "Cement", "NUVOCO": "Cement", "INDIACEM": "Cement",
    # Defence
    "HAL": "Defence", "BEL": "Defence", "SOLARINDS": "Defence", "DATAPATTNS": "Defence",
    "MAZDOCK": "Defence", "GESHIP": "Defence", "COCHINSHIP": "Defence",
    "BEML": "Defence", "MTAR": "Defence", "ZEN": "Defence", "CENTUM": "Defence",
    "APOLLOMICRO": "Defence", "HBLPOWER": "Defence", "IDEAFORGE": "Defence",
    # Infrastructure
    "RVNL": "Infrastructure", "IRCON": "Infrastructure", "RITES": "Infrastructure",
    "NBCC": "Infrastructure", "PNCINFRA": "Infrastructure", "KNRCON": "Infrastructure",
    "KALPATPOWR": "Infrastructure", "HGINFRA": "Infrastructure", "IRFC": "Finance",
    # Real Estate
    "DLF": "Real Estate", "GODREJPROP": "Real Estate", "PRESTIGE": "Real Estate",
    "OBEROIRLTY": "Real Estate", "PHOENIXLTD": "Real Estate", "SOBHA": "Real Estate",
    "BRIGADE": "Real Estate", "MACROTECH": "Real Estate", "ANANTRAJ": "Real Estate",
    # Consumer Tech
    "ZOMATO": "Consumer Tech", "PAYTM": "Fintech", "NYKAA": "Consumer Tech",
    "POLICYBZR": "Fintech", "DELHIVERY": "Logistics", "SWIGGY": "Consumer Tech",
    "INFOEDGE": "Consumer Tech", "JUSTDIAL": "Consumer Tech",
    # Media & Entertainment
    "SUNTV": "Media", "ZEEL": "Media", "PVR": "Entertainment", "SAREGAMA": "Media",
    "NAZARA": "Gaming", "DELTACORP": "Entertainment",
    # Misc popular swing stocks
    "INOXWIND": "Capital Goods", "JPPOWER": "Utilities", "IREDA": "Finance",
    "MSTCLTD": "Financial Services", "VBL": "Beverages", "AVANTIFEED": "Food",
    "BALRAMCHIN": "Sugar", "RENUKA": "Sugar", "TRIVENI": "Sugar",
    "RAYMOND": "Textiles", "ARVIND": "Textiles", "VARDHMAN": "Textiles",
    "WELSPUNIND": "Textiles", "MANYAVAR": "Textiles",
    "BATAINDIA": "Consumer", "RELAXO": "Consumer", "METRO": "Consumer",
    "IHCLTD": "Hospitality", "LEMONTREE": "Hospitality", "CHALET": "Hospitality",
    "WONDERLA": "Entertainment", "IRCTC": "Tourism", "MHRIL": "Tourism",
    "AEGISLOG": "Logistics", "CONCOR": "Logistics", "TCIEXP": "Logistics",
    "INDIGO": "Aviation", "SPICEJET": "Aviation",
    "CAMS": "Financial Services", "CDSL": "Financial Services", "BSE": "Financial Services",
    "MCX": "Financial Services", "ANGELONE": "Broking", "MOTILALOFS": "Broking",
}


def _load_nse_csv_from_web() -> Dict[str, Dict[str, str]]:
    """Download the complete NSE equity list CSV and parse it."""
    # Official NSE equity list — all ~2000 listed companies
    NSE_EQUITY_URL = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"

    try:
        logger.info("Downloading NSE equity list from nseindia.com...")
        # NSE requires a referer cookie — first hit the main page
        _session.get("https://www.nseindia.com", timeout=5)
        resp = _session.get(NSE_EQUITY_URL, timeout=15)
        resp.raise_for_status()

        stocks: Dict[str, Dict[str, str]] = {}
        reader = csv.DictReader(io.StringIO(resp.text))
        for row in reader:
            symbol = (row.get("SYMBOL") or "").strip().upper()
            name = (row.get("NAME OF COMPANY") or row.get(" NAME OF COMPANY") or "").strip()
            if symbol and name:
                sector = _SECTOR_TAGS.get(symbol, "NSE Listed")
                stocks[symbol] = {"name": name, "sector": sector, "exchange": "NSE"}

        logger.info(f"NSE equity list loaded: {len(stocks)} stocks")
        return stocks

    except Exception as e:
        logger.warning(f"NSE CSV download failed: {e}")
        return {}


def _save_cache(data: Dict[str, Dict[str, str]]) -> None:
    """Save the stock universe to disk cache."""
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        payload = {
            "fetched_at": datetime.utcnow().isoformat(),
            "stocks": data,
        }
        with open(_NSE_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)
        logger.info(f"Stock universe cached to disk: {len(data)} stocks")
    except Exception as e:
        logger.warning(f"Could not save stock universe cache: {e}")


def _load_cache() -> Optional[Dict[str, Dict[str, str]]]:
    """Load stock universe from disk cache if fresh (< 24h old)."""
    try:
        if not os.path.exists(_NSE_CACHE_FILE):
            return None
        with open(_NSE_CACHE_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
        fetched_at = datetime.fromisoformat(payload["fetched_at"])
        age_hours = (datetime.utcnow() - fetched_at).total_seconds() / 3600
        if age_hours > _NSE_CACHE_TTL_HOURS:
            logger.info(f"Stock universe cache expired ({age_hours:.1f}h old), will refresh")
            return None
        stocks = payload["stocks"]
        logger.info(f"Stock universe loaded from disk cache: {len(stocks)} stocks ({age_hours:.1f}h old)")
        return stocks
    except Exception as e:
        logger.warning(f"Could not load stock universe cache: {e}")
        return None


def _build_fallback_universe() -> Dict[str, Dict[str, str]]:
    """Build a minimal fallback universe from our sector tags map."""
    stocks = {}
    for sym, sector in _SECTOR_TAGS.items():
        stocks[sym] = {"name": sym, "sector": sector, "exchange": "NSE"}
    logger.info(f"Using fallback sector-tags universe: {len(stocks)} stocks")
    return stocks


def load_universe(force_refresh: bool = False) -> None:
    """
    Load the complete stock universe into memory.
    Called once at startup. Non-blocking if cache exists.
    """
    global _universe, _universe_loaded

    # 1. Try disk cache first
    if not force_refresh:
        cached = _load_cache()
        if cached:
            _universe = cached
            # Overlay our sector tags for known stocks
            for sym, sector in _SECTOR_TAGS.items():
                if sym in _universe:
                    _universe[sym]["sector"] = sector
            _universe_loaded = True
            return

    # 2. Download fresh from NSE
    fresh = _load_nse_csv_from_web()
    if fresh:
        # Overlay our sector tags
        for sym, sector in _SECTOR_TAGS.items():
            if sym in fresh:
                fresh[sym]["sector"] = sector
            else:
                # Add any tagged stock not in NSE list (BSE only, etc.)
                fresh[sym] = {"name": sym, "sector": sector, "exchange": "NSE"}
        _universe = fresh
        _save_cache(fresh)
        _universe_loaded = True
        return

    # 3. Fallback to sector tags only
    _universe = _build_fallback_universe()
    _universe_loaded = True


def _ensure_loaded() -> None:
    """Lazy-load the universe if not already loaded."""
    global _universe_loaded
    if not _universe_loaded:
        load_universe()


def get_symbol_info(symbol: str) -> Optional[Dict[str, str]]:
    """Return {name, sector, exchange} for a symbol, or None if unknown."""
    _ensure_loaded()
    return _universe.get(symbol.upper().replace(".NS", "").replace(".BO", ""))


def search_universe(query: str, limit: int = 12) -> List[Dict[str, str]]:
    """
    Search the complete stock universe.

    Supports:
      - Exact symbol: "INOXWIND"
      - Partial symbol: "INOX"
      - Multi-word name: "inox wind", "jp power", "jaiprakash power"
      - Single word name fragment: "jaiprakash"
      - yfinance Search API fallback for anything else

    Returns list of {symbol, name, sector, exchange}
    """
    _ensure_loaded()

    if not query or not query.strip():
        return []

    q_raw = query.strip()
    q = q_raw.upper()
    q_lower = q_raw.lower()
    q_no_spaces = q.replace(" ", "")
    # Split into tokens for multi-word matching
    tokens = [t for t in q_lower.split() if t]

    # Score each stock — higher = better match
    scored: List[tuple] = []  # (score, symbol, info)

    for symbol, info in _universe.items():
        name_lower = info["name"].lower()
        name_upper = info["name"].upper()
        score = 0

        # Exact symbol match (with or without spaces)
        if symbol == q or symbol == q_no_spaces:
            score = 1000
        # Symbol starts with query (with or without spaces)
        elif symbol.startswith(q) or symbol.startswith(q_no_spaces):
            score = 800
        # Query is inside symbol
        elif q in symbol or q_no_spaces in symbol:
            score = 600
        # Multi-word: all tokens present in the name
        elif len(tokens) > 1 and all(t in name_lower for t in tokens):
            # Score by how long the matching tokens are (longer = more specific)
            score = 400 + sum(len(t) for t in tokens)
        # Single word in name
        elif len(tokens) == 1 and tokens[0] in name_lower:
            idx = name_lower.find(tokens[0])
            score = 300 if idx == 0 else 200
        # Partial: any token in name for multi-word queries
        elif len(tokens) > 1 and any(t in name_lower for t in tokens if len(t) > 2):
            score = 100

        if score > 0:
            scored.append((score, symbol, info))

    # Sort by score descending, then alphabetically
    scored.sort(key=lambda x: (-x[0], x[1]))
    seen = set()
    local_results: List[Dict] = []
    for _, symbol, info in scored:
        if symbol not in seen:
            local_results.append({"symbol": symbol, **info})
            seen.add(symbol)
        if len(local_results) >= limit:
            break

    # ── yfinance Search API fallback ─────────────────────────────────────────
    # Fires when local results are thin — finds any NSE/BSE stock by name
    if len(local_results) < 3:
        try:
            yf_results = _yfinance_search(query, limit=max(3, limit - len(local_results)))
            for r in yf_results:
                if r["symbol"] not in seen:
                    local_results.append(r)
                    seen.add(r["symbol"])
                    # Add to our in-memory universe for future queries
                    _universe[r["symbol"]] = {
                        "name": r["name"],
                        "sector": r.get("sector", "NSE Listed"),
                        "exchange": r.get("exchange", "NSE"),
                    }
        except Exception as e:
            logger.debug(f"yfinance search fallback failed for '{query}': {e}")

    return local_results[:limit]


def _yfinance_search(query: str, limit: int = 8) -> List[Dict[str, str]]:
    """
    Use yfinance's Search API to find stocks by name or symbol.
    Filters to Indian exchanges (NSE/BSE/NMS/BSE).
    """
    results = []
    try:
        search = yf.Search(query, max_results=20, news_count=0)
        quotes = search.quotes or []
        indian_exchanges = {"NSI", "NSE", "BSE", "BOM", "NMS", "BSE"}

        for q in quotes:
            exch = (q.get("exchange") or q.get("fullExchangeName") or "").upper()
            sym_raw = q.get("symbol") or ""
            # Normalise: strip .NS and .BO suffixes
            if sym_raw.endswith(".NS"):
                symbol = sym_raw[:-3]
                exchange = "NSE"
            elif sym_raw.endswith(".BO"):
                symbol = sym_raw[:-3]
                exchange = "BSE"
            elif exch in indian_exchanges:
                symbol = sym_raw
                exchange = "NSE" if "NS" in exch else "BSE"
            else:
                continue  # skip non-Indian stocks

            name = (q.get("longname") or q.get("shortname") or symbol).strip()
            sector = _SECTOR_TAGS.get(symbol, q.get("sector") or "NSE Listed")
            results.append({
                "symbol": symbol,
                "name": name,
                "sector": sector,
                "exchange": exchange,
            })
            if len(results) >= limit:
                break

    except Exception as e:
        logger.debug(f"yfinance Search API failed for '{query}': {e}")

    return results


def is_valid_symbol(symbol: str) -> bool:
    """
    Check if a symbol is a valid NSE stock by pinging yfinance fast_info.
    Used for the "load directly" feature when user types an exact ticker.
    """
    symbol = symbol.upper().replace(".NS", "").replace(".BO", "")
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        price = getattr(ticker.fast_info, "last_price", None)
        if price and float(price) > 0:
            return True
        # Try BSE
        ticker2 = yf.Ticker(f"{symbol}.BO")
        price2 = getattr(ticker2.fast_info, "last_price", None)
        return bool(price2 and float(price2) > 0)
    except Exception:
        return False


def universe_size() -> int:
    """Return the number of stocks currently in the universe."""
    _ensure_loaded()
    return len(_universe)
