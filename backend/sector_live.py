"""
KEPLER -- Sector Intelligence Hub

Provides live, all-sectors data for the Sector Hub dashboard.
Thinking like a swing trader + investor — covers everything that moves sectors:
  • Performance vs Nifty (1D / 1W / 1M / YTD)
  • Relative strength vs broad market
  • Top movers within the sector (day %)
  • Sector-specific macro signals
  • Filtered live news per sector
  • Sentiment (BULLISH / BEARISH / MIXED) from RS + momentum

15-minute TTL cache. Parallel fetch via ThreadPoolExecutor.
"""
import copy
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import yfinance as yf
from loguru import logger

# ═══════════════════════════════════════════════════════════════════════════════
# SECTOR UNIVERSE CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

# NSE sector indices
NSE_SECTOR_INDICES: Dict[str, str] = {
    "Banking":          "^NSEBANK",
    "IT & Technology":  "^CNXIT",
    "Pharma":           "^CNXPHARMA",
    "Auto & EV":        "^CNXAUTO",
    "FMCG":             "^CNXFMCG",
    "Realty":           "^CNXREALTY",
    "Metals":           "^CNXMETAL",
    "Energy":           "^CNXENERGY",
    "Infrastructure":   "^CNXINFRA",
    "PSU Banks":        "^CNXPSUBANK",
    "Fin Services":     "^CNXFIN",
    "Midcap 100":       "^NSMIDCP100",
    "Smallcap":         "^CNXSC",
    "Consumption":      "^CNXCONSUM",
    "Media":            "^CNXMEDIA",
}

# Top liquid stocks per sector for movers (by market cap / liquidity)
SECTOR_TOP_STOCKS: Dict[str, List[str]] = {
    "Banking":         ["HDFCBANK", "ICICIBANK", "KOTAKBANK", "AXISBANK", "SBIN", "INDUSINDBK"],
    "IT & Technology": ["TCS", "INFY", "HCLTECH", "WIPRO", "TECHM", "LTIM"],
    "Pharma":          ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB", "LUPIN", "APOLLOHOSP"],
    "Auto & EV":       ["MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO", "EICHERMOT", "HEROMOTOCO"],
    "FMCG":            ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "DABUR", "MARICO"],
    "Realty":          ["DLF", "GODREJPROP", "OBEROIRLTY", "PRESTIGE", "PHOENIXLTD"],
    "Metals":          ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "SAIL", "NMDC"],
    "Energy":          ["RELIANCE", "ONGC", "BPCL", "TATAPOWER", "NTPC", "ADANIGREEN"],
    "Infrastructure":  ["LT", "SIEMENS", "HAL", "BEL", "IRCTC", "POLYCAB"],
    "PSU Banks":       ["SBIN", "BANKBARODA", "CANBK", "PNB", "UNIONBANK"],
    "Fin Services":    ["BAJFINANCE", "BAJAJFINSV", "CHOLAFIN", "MUTHOOTFIN", "HDFCAMC"],
    "Midcap 100":      ["DIXON", "PERSISTENT", "COFORGE", "KAYNES", "TRENT"],
    "Smallcap":        ["RVNL", "IRFC", "RAILTEL", "IRCON", "HFCL"],
    "Consumption":     ["TITAN", "DMART", "TRENT", "JUBLFOOD", "KALYANKJIL"],
    "Media":           ["SUNTV", "ZEEL", "PVR", "INOXLEISUR"],
}

# Per-sector macro signal labels (what a pro trader tracks)
SECTOR_MACRO_CONFIG: Dict[str, Dict] = {
    "Banking": {
        "icon": "🏦",
        "color": "#3b82f6",
        "watch": ["RBI repo rate", "Credit growth YoY", "GNPA ratio", "FII flows"],
        "global_peer": "KBW Bank Index / US 10Y Yield",
        "sensitivity": "Rate-sensitive: holds benefit from rate cuts; high NPA = risk",
    },
    "IT & Technology": {
        "icon": "💻",
        "color": "#8b5cf6",
        "watch": ["USD/INR rate", "NASDAQ performance", "US tech spending", "H1B policy"],
        "global_peer": "NASDAQ / Accenture / Cognizant",
        "sensitivity": "USD strength = earnings boost; US recession fear = demand risk",
    },
    "Pharma": {
        "icon": "💊",
        "color": "#10b981",
        "watch": ["US FDA inspections", "USFDA import alerts", "API prices (China)", "INR/USD"],
        "global_peer": "S&P Pharma ETF / US generic drug pricing",
        "sensitivity": "Rupee depreciation boosts export earnings; USFDA warnings = risk",
    },
    "Auto & EV": {
        "icon": "🚗",
        "color": "#f59e0b",
        "watch": ["Vahan monthly sales", "EV penetration %", "Commodity input costs", "Rural income"],
        "global_peer": "Tesla / Global EV sales data",
        "sensitivity": "High commodity prices compress margins; rural recovery drives 2W sales",
    },
    "FMCG": {
        "icon": "🛒",
        "color": "#ec4899",
        "watch": ["Rural demand index", "Monsoon progress", "Input cost inflation", "CPI data"],
        "global_peer": "Unilever / P&G / Nestlé global",
        "sensitivity": "Good monsoon = rural demand surge; crude-based input costs hurt margins",
    },
    "Realty": {
        "icon": "🏙️",
        "color": "#f97316",
        "watch": ["Home loan rates (repo)", "Registration data", "Unsold inventory", "NRI buying"],
        "global_peer": "US 30Y mortgage rates / Global housing PMI",
        "sensitivity": "Rate cuts are rocket fuel; rising rates kill affordability",
    },
    "Metals": {
        "icon": "⚙️",
        "color": "#94a3b8",
        "watch": ["LME steel/copper prices", "China PMI/demand", "Iron ore prices", "Coking coal"],
        "global_peer": "LME / China steel futures",
        "sensitivity": "China slowdown = metals crash; infrastructure spend = demand boom",
    },
    "Energy": {
        "icon": "⚡",
        "color": "#fbbf24",
        "watch": ["Brent crude ($/bbl)", "Natural gas prices", "INR/USD", "OPEC decisions"],
        "global_peer": "Brent / WTI crude futures",
        "sensitivity": "Crude above $90 = refiner margin squeeze; renewable policy = NTPC tailwind",
    },
    "Infrastructure": {
        "icon": "🏗️",
        "color": "#06b6d4",
        "watch": ["Govt capex budget", "PLI scheme progress", "Order book growth", "Interest rates"],
        "global_peer": "US Infrastructure spending / Global capex cycle",
        "sensitivity": "Govt capex = direct revenue; any budget cut = earnings risk",
    },
    "PSU Banks": {
        "icon": "🏛️",
        "color": "#64748b",
        "watch": ["RBI guidelines", "Govt recapitalization", "Credit growth", "GNPA cleanup"],
        "global_peer": "Peer PSU bank ROEs vs private banks",
        "sensitivity": "Policy-driven; elections and budget determine risk appetite",
    },
    "Fin Services": {
        "icon": "💰",
        "color": "#a78bfa",
        "watch": ["RBI NBFC regulations", "Cost of funds", "AUM growth", "Gold prices (Muthoot)"],
        "global_peer": "Global fintech multiples / credit cycle",
        "sensitivity": "Liquidity conditions critical; regulatory tightening = re-rating risk",
    },
    "Midcap 100": {
        "icon": "📈",
        "color": "#00C48C",
        "watch": ["FII vs DII flows", "Liquidity in small/mid", "Earnings growth differential"],
        "global_peer": "Russell 2000 (US small caps)",
        "sensitivity": "Risk-on environment = midcap outperformance; global risk-off = underperformance",
    },
    "Smallcap": {
        "icon": "🔬",
        "color": "#f43f5e",
        "watch": ["Market breadth", "Retail investor flows", "SIP data", "Promoter buying"],
        "global_peer": "Domestic liquidity driven — watch SIP + retail flows",
        "sensitivity": "High beta to market; corrections are deep; recoveries are fast",
    },
    "Consumption": {
        "icon": "🛍️",
        "color": "#fb923c",
        "watch": ["Disposable income growth", "GST collections", "Festive season data", "EMI rates"],
        "global_peer": "Consumer discretionary ETF (US)",
        "sensitivity": "Urban consumption recovering; rural stress = near-term risk",
    },
    "Media": {
        "icon": "📺",
        "color": "#e879f9",
        "watch": ["Ad revenue trends", "OTT subscriber growth", "Box office collections"],
        "global_peer": "Netflix / Disney / WB Discovery",
        "sensitivity": "Ad-spend linked to GDP; OTT disruption = secular headwind for TV",
    },
}

# Per-sector news filter keywords (used to route RSS articles to sectors)
SECTOR_KEYWORDS: Dict[str, List[str]] = {
    "Banking":         ["rbi", "bank", "credit growth", "npa", "hdfc bank", "icici", "axis bank", "kotak", "repo rate", "crar", "net interest"],
    "IT & Technology": ["tcs", "infosys", "wipro", "hcl tech", "tech mahindra", "software", "it sector", "h1b", "dollar", "deal win", "attrition", "nasscom"],
    "Pharma":          ["usfda", "fda", "pharma", "drug", "api", "clinical trial", "sunpharma", "drreddy", "cipla", "approval", "warning letter", "health"],
    "Auto & EV":       ["vahan", "auto sales", "ev", "electric vehicle", "maruti", "tata motors", "mahindra", "two wheeler", "passenger vehicle", "automobile"],
    "FMCG":            ["fmcg", "consumer", "rural demand", "monsoon", "hindustan unilever", "itc", "nestle", "dabur", "marico", "inflation", "volume growth"],
    "Realty":          ["real estate", "realty", "housing", "dlf", "home loan", "property", "registration", "affordable housing", "godrej prop"],
    "Metals":          ["steel", "metal", "aluminium", "copper", "iron ore", "lme", "jsw steel", "tata steel", "hindalco", "coking coal", "china demand"],
    "Energy":          ["crude", "brent", "oil", "gas", "ongc", "reliance", "bpcl", "petroleum", "opec", "refinery", "natural gas", "renewable", "ntpc"],
    "Infrastructure":  ["capex", "infrastructure", "pli", "l&t", "siemens", "roads", "railways", "defence", "hal", "bel", "order book", "government spending"],
    "PSU Banks":       ["sbi", "bank of baroda", "pnb", "canara bank", "psu bank", "public sector bank", "recapitalization"],
    "Fin Services":    ["nbfc", "bajaj finance", "microfinance", "gold loan", "muthoot", "amc", "mutual fund", "rbi regulation", "asset management"],
    "Midcap 100":      ["midcap", "mid cap", "nifty midcap", "emerging companies"],
    "Smallcap":        ["smallcap", "small cap", "sme", "promoter buying", "retail investor"],
    "Consumption":     ["consumption", "retail", "titan", "dmart", "jewellery", "festive", "gst collection", "urban consumption", "premium"],
    "Media":           ["media", "ott", "streaming", "zee", "sun tv", "bollywood", "box office", "advertising revenue", "pvr", "multiplex"],
}


# ═══════════════════════════════════════════════════════════════════════════════
# CACHE
# ═══════════════════════════════════════════════════════════════════════════════

_cache: Dict[str, Any] = {}
_CACHE_TTL = 900  # 15 minutes
_fetching = False


# ═══════════════════════════════════════════════════════════════════════════════
# FETCH HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_index_perf(name: str, symbol: str, nifty_hist: Any) -> Tuple[str, Optional[Dict]]:
    """Fetch performance for one sector index."""
    try:
        ticker = yf.Ticker(symbol)
        hist   = ticker.history(period="1y", interval="1d").dropna(subset=["Close"])
        if len(hist) < 5:
            return name, None

        close = hist["Close"]
        latest    = float(close.iloc[-1])
        prev_day  = float(close.iloc[-2])
        week_ago  = float(close.iloc[-min(6, len(close)-1)])
        month_ago = float(close.iloc[-min(22, len(close)-1)])
        year_ago  = float(close.iloc[0])

        day_pct   = ((latest - prev_day)  / prev_day)  * 100
        week_pct  = ((latest - week_ago)  / week_ago)  * 100
        month_pct = ((latest - month_ago) / month_ago) * 100
        ytd_pct   = ((latest - year_ago)  / year_ago)  * 100

        # Relative strength vs Nifty (30-day)
        rs = 1.0
        try:
            nifty_close = nifty_hist["Close"].dropna()
            nifty_30d   = float(nifty_close.iloc[-1])
            nifty_30d_b = float(nifty_close.iloc[-min(22, len(nifty_close)-1)])
            nifty_m_ret = (nifty_30d - nifty_30d_b) / nifty_30d_b
            sector_m_ret = (latest - month_ago) / month_ago
            rs = round((1 + sector_m_ret) / (1 + nifty_m_ret), 3)
        except Exception:
            pass

        # Sentiment
        if week_pct > 1.5 and rs > 1.01:
            sentiment = "BULLISH"
        elif week_pct < -1.5 or rs < 0.97:
            sentiment = "BEARISH"
        else:
            sentiment = "MIXED"

        return name, {
            "name":      name,
            "symbol":    symbol,
            "current":   round(latest, 0),
            "day_pct":   round(day_pct, 2),
            "week_pct":  round(week_pct, 2),
            "month_pct": round(month_pct, 2),
            "ytd_pct":   round(ytd_pct, 2),
            "rs_nifty":  rs,
            "sentiment": sentiment,
        }
    except Exception as e:
        logger.debug(f"Index fetch failed for {name} ({symbol}): {e}")
        return name, None


def _fetch_stock_day(symbol: str) -> Tuple[str, Optional[Dict]]:
    """Fetch 1-day change for a single stock."""
    try:
        fi = yf.Ticker(f"{symbol}.NS").fast_info
        price = float(fi.last_price)
        prev  = float(fi.previous_close)
        chg   = ((price - prev) / prev) * 100
        return symbol, {"price": round(price, 2), "change_pct": round(chg, 2)}
    except Exception:
        return symbol, None


def _get_top_movers(sector: str) -> List[Dict]:
    """Parallel fetch day % for top stocks in the sector, return sorted list."""
    stocks = SECTOR_TOP_STOCKS.get(sector, [])
    if not stocks:
        return []
    results = []
    with ThreadPoolExecutor(max_workers=min(len(stocks), 6), thread_name_prefix="mover") as pool:
        futures = {pool.submit(_fetch_stock_day, s): s for s in stocks}
        for fut in as_completed(futures):
            sym, data = fut.result()
            if data:
                results.append({"symbol": sym, **data})
    results.sort(key=lambda x: abs(x["change_pct"]), reverse=True)
    return results[:5]


def _filter_news_for_sector(sector: str, all_articles: List[Dict]) -> List[Dict]:
    """Filter RSS articles by sector-specific keywords."""
    keywords = [k.lower() for k in SECTOR_KEYWORDS.get(sector, [])]
    if not keywords:
        return []
    matched = []
    for art in all_articles:
        text = (art.get("title", "") + " " + art.get("summary", "")).lower()
        if any(kw in text for kw in keywords):
            matched.append({
                "title":   art.get("title", ""),
                "url":     art.get("url", ""),
                "source":  art.get("source", ""),
                "impact":  art.get("impact", "MEDIUM"),
                "published": art.get("published", ""),
            })
    # Sort by impact
    impact_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    matched.sort(key=lambda x: impact_order.get(x.get("impact", "MEDIUM"), 1))
    return matched[:6]


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN BUILD FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════

def _build_all_sectors() -> Dict[str, Any]:
    """Fetch and assemble live data for all sectors in parallel."""
    t0 = time.time()
    logger.info("Sector Hub: building live data…")

    # 1. Nifty baseline
    nifty_hist = {}
    try:
        nifty_ticker = yf.Ticker("^NSEI")
        nifty_hist = nifty_ticker.history(period="60d", interval="1d")
    except Exception as e:
        logger.warning(f"Could not fetch Nifty baseline: {e}")

    # 2. Parallel fetch all sector indices
    sector_perf: Dict[str, Optional[Dict]] = {}
    with ThreadPoolExecutor(max_workers=min(len(NSE_SECTOR_INDICES), 15), thread_name_prefix="secidx") as pool:
        futures = {pool.submit(_fetch_index_perf, name, sym, nifty_hist): name
                   for name, sym in NSE_SECTOR_INDICES.items()}
        for fut in as_completed(futures):
            name, data = fut.result()
            sector_perf[name] = data

    # 3. Parallel fetch top movers for all sectors
    sector_movers: Dict[str, List] = {}
    with ThreadPoolExecutor(max_workers=8, thread_name_prefix="movers") as pool:
        futures = {pool.submit(_get_top_movers, s): s for s in NSE_SECTOR_INDICES.keys()}
        for fut in as_completed(futures):
            sec = futures[fut]
            sector_movers[sec] = fut.result()

    # 4. Get live news articles (use cached if available)
    all_articles: List[Dict] = []
    try:
        from news_live import get_live_news
        news_result = get_live_news(limit=100)
        all_articles = news_result.get("articles", [])
    except Exception as e:
        logger.warning(f"Could not fetch live news for sectors: {e}")

    # 5. Assemble sector objects
    sectors = []
    for name in NSE_SECTOR_INDICES:
        perf    = sector_perf.get(name)
        movers  = sector_movers.get(name, [])
        news    = _filter_news_for_sector(name, all_articles)
        meta    = SECTOR_MACRO_CONFIG.get(name, {"icon": "📊", "color": "#64748b", "watch": [], "global_peer": ""})

        if perf is None:
            continue

        sectors.append({
            **perf,
            "top_movers":   movers,
            "news":         news,
            "macro_watch":  meta.get("watch", []),
            "global_peer":  meta.get("global_peer", ""),
            "sensitivity":  meta.get("sensitivity", ""),
            "icon":         meta.get("icon", "📊"),
            "color":        meta.get("color", "#64748b"),
            "news_count":   len(news),
        })

    # Sort by absolute 1-day move (most active first by default)
    sectors.sort(key=lambda x: abs(x["day_pct"]), reverse=True)

    elapsed = round(time.time() - t0, 2)
    logger.info(f"Sector Hub: {len(sectors)} sectors assembled in {elapsed}s")

    return {
        "sectors":    sectors,
        "fetched_at": time.time(),
        "news_total": len(all_articles),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_sectors_live(force_refresh: bool = False) -> Dict[str, Any]:
    """Public API: returns live sector hub data. 15-minute cache."""
    global _fetching

    cache_key = "sector_hub"

    # Cache hit
    if not force_refresh and cache_key in _cache:
        age = time.time() - _cache[cache_key]["fetched_at"]
        if age < _CACHE_TTL:
            out = copy.deepcopy(_cache[cache_key])
            out["cache_age_s"]    = round(age)
            out["next_refresh_in"] = max(0, int(_CACHE_TTL - age))
            return out

    # Thundering herd protection
    if _fetching and cache_key in _cache:
        out = copy.deepcopy(_cache[cache_key])
        out["stale"] = True
        return out

    try:
        _fetching = True
        fresh = _build_all_sectors()
        _cache[cache_key] = fresh
        out = copy.deepcopy(fresh)
        out["cache_age_s"]    = 0
        out["next_refresh_in"] = _CACHE_TTL
        return out
    finally:
        _fetching = False
