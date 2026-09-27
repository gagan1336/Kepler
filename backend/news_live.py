"""
KEPLER -- Live Market News Engine
Fetches RSS from 14 curated Indian finance feeds in parallel,
scores each article for market impact, auto-categorizes into 8 buckets,
deduplicates, and caches for 10 minutes.

Categories:
  BREAKING  — HIGH impact across any domain
  MARKETS   — Nifty/Sensex, FII/DII flows, index moves
  STOCKS    — Corporate results, deals, buybacks, insider activity
  RBI       — Monetary policy, inflation data, banking circulars
  SEBI      — SEBI circulars, exchange notifications, regulations
  GST_TAX   — GST council, CBDT, income tax, TDS
  IPO       — IPO open/close, listing gains, allotment
  GLOBAL    — Fed/ECB, crude oil, dollar index, global macro
"""
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple
from email.utils import parsedate_to_datetime

import feedparser
from loguru import logger

# ── 10-minute cache ───────────────────────────────────────────────────────────
_news_cache: Dict[str, Any] = {}
_CACHE_TTL = 600  # 10 minutes

# ── RSS Feed Registry ─────────────────────────────────────────────────────────
FEEDS = [
    # Tier 1 — Primary market intel
    {"url": "https://economictimes.indiatimes.com/markets/rss.cms",
     "source": "Economic Times Markets", "weight": 10},
    {"url": "https://www.moneycontrol.com/rss/marketreports.xml",
     "source": "Moneycontrol", "weight": 10},
    {"url": "https://www.livemint.com/rss/markets",
     "source": "LiveMint Markets", "weight": 9},
    {"url": "https://www.business-standard.com/rss/markets-106.rss",
     "source": "Business Standard", "weight": 9},
    # Tier 2 — Companies / results
    {"url": "https://www.livemint.com/rss/companies",
     "source": "LiveMint Companies", "weight": 8},
    {"url": "https://economictimes.indiatimes.com/industry/rss.cms",
     "source": "ET Industry", "weight": 8},
    {"url": "https://www.financialexpress.com/market/feed/",
     "source": "Financial Express", "weight": 7},
    # Tier 3 — Policy & Macro
    {"url": "https://economictimes.indiatimes.com/economy/policy/rss.cms",
     "source": "ET Policy", "weight": 9},
    {"url": "https://economictimes.indiatimes.com/economy/finance/rss.cms",
     "source": "ET Finance", "weight": 8},
    {"url": "https://www.business-standard.com/rss/economy-policy-102.rss",
     "source": "BS Economy", "weight": 8},
    # Tier 4 — Forex & global
    {"url": "https://economictimes.indiatimes.com/markets/forex/rss.cms",
     "source": "ET Forex", "weight": 7},
    # Tier 5 — Official regulatory
    {"url": "https://www.sebi.gov.in/sebi_data/attachdocs/rss/rss.xml",
     "source": "SEBI Official", "weight": 10},
    {"url": "https://rbi.org.in/rss/rss.aspx",
     "source": "RBI Official", "weight": 10},
    {"url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",
     "source": "PIB Finance", "weight": 9},
]

# ── Categorization keyword maps ───────────────────────────────────────────────
CATEGORY_RULES: List[Tuple[str, List[str], int]] = [
    # (category, keywords, minimum_hits)  — ordered by specificity
    ("IPO", [
        "ipo", "initial public offer", "listing gain", "allotment", "gmp",
        "grey market", "oversubscribed", "subscription", "mainboard", "sme ipo",
        "listing price", "listing day", "nfo", "new fund offer",
    ], 1),
    ("GLOBAL", [
        "fed ", "federal reserve", "us interest rate", "ecb ", "bank of england",
        "crude oil", "brent", "wti", "dollar index", "dxy", "china gdp",
        "us inflation", "us cpi", "global market", "wall street", "nasdaq",
        "dow jones", "s&p 500", "yen", "yuan", "euro ", "ftse",
        "opec", "gold price", "silver price", "comex",
    ], 1),
    ("RBI", [
        "rbi ", "reserve bank", "monetary policy", "mpc ", "repo rate",
        "reverse repo", "iip data", "gdp growth", "gdp data",
        "credit policy", "rbi circular", "rbi notification", "banking regulation",
        "nbfc", "crr ", "slr ", "rbi governor", "shaktikanta", "sanjay malhotra",
        "rate hike", "rate cut", "inflation target",
    ], 1),
    ("SEBI", [
        "sebi ", "securities exchange board", "sebi circular", "sebi regulation",
        "insider trading", "takeover code", "mutual fund regulation",
        "demat", "fpi registration", "alternative investment fund",
        "sebi notice", "sebi order", "sebi penalty", "sebi ban",
        "securities law", "stock exchange regulation",
    ], 1),
    ("GST_TAX", [
        "gst ", "goods and services tax", "gst council", "gst rate",
        "gst collection", "cbdt", "income tax", "tds ", "advance tax",
        "tax amendment", "direct tax", "indirect tax", "income tax return",
        "faceless", "tax evasion", "tax notice", "gst revenue",
        "goods tax", "service tax", "customs duty",
    ], 1),
    ("STOCKS", [
        "quarterly result", "q1 result", "q2 result", "q3 result", "q4 result",
        "annual result", "earnings result", "net profit", "revenue grew",
        "buyback", "dividend declared", "bonus share", "stock split",
        "acquisition", "merger approved", "deal signed", "order win", "contract won",
        "promoter", "insider buy", "block deal", "bulk deal", "qip",
        "rights issue", "fundraise", "fy25", "fy26",
    ], 2),
    ("MARKETS", [
        "nifty", "sensex", "bse", "nse", "fii", "dii", "foreign investor",
        "institutional", "market rally", "market crash", "market update",
        "trading session", "intraday", "mcap", "advance decline",
        "market cap", "indices", "small cap", "mid cap", "large cap",
        "market breadth", "circuit breaker", "upper circuit", "lower circuit",
    ], 1),
]

# ── Impact scoring keyword maps ───────────────────────────────────────────────
HIGH_IMPACT_SIGNALS = [
    # Policy moves
    "rate cut", "rate hike", "repo rate changed", "rbi raises", "rbi cuts",
    "mpc decision", "monetary policy decision", "emergency", "crisis",
    "market crash", "circuit breaker", "trading halt", "market closed",
    "rate cut today", "rate hike today", "mpc meeting outcome",
    # Corporate big moves
    "quarterly result", "q1 result", "q2 result", "q3 result", "q4 result",
    "profit jumps", "profit plunges", "revenue surge", "revenue falls",
    "record profit", "record loss", "bankruptcy", "insolvency", "nclt",
    "merger approved", "acquisition completed", "hostile takeover",
    "sebi ban", "sebi penalty", "insider trading caught",
    "upper circuit", "lower circuit",
    # Macro shocks
    "union budget", "gdp contraction", "recession", "stagflation",
    "rupee falls", "rupee hits low", "rupee all time low",
    "crude surges", "crude crashes", "gold hits record", "gold all time high",
    "fii sell heavily", "fii buying", "net inflow record",
    # Regulatory
    "sebi circular", "rbi circular", "gst council meeting", "gst rate change",
    "tax amendment", "cbdt notification", "budget 2025", "budget 2026",
    # Market events
    "sensex crashes", "nifty crashes", "sensex rally", "nifty rally",
    "all time high", "52 week high", "52 week low",
]

MEDIUM_IMPACT_SIGNALS = [
    "result", "earnings", "growth", "expansion", "forecast", "outlook",
    "guidance", "quarterly", "quarterly result", "annual result",
    "q1 result", "q2 result", "q3 result", "q4 result",
    "fy25", "fy26", "fy27", "fy2",
    "contract", "order", "deal", "order win", "contract win",
    "fii data", "dii data", "iip", "pmi", "inflation data",
    "interest rate", "bank credit", "trade deficit",
    "upper circuit", "lower circuit",
    "bulk deal", "block deal", "qip", "rights issue",
    "fundraise", "promoter", "insider buy",
    "acquisition", "merger", "demerger", "spin-off",
    "ipo open", "ipo close", "listing gain", "listing price",
    "net profit", "revenue grew", "profit up", "profit down",
    "dividend", "bonus share", "stock split", "buyback",
]

LOW_IMPACT_NOISE = [
    "cricket", "bollywood", "celebrity", "fashion", "food", "travel",
    "lifestyle", "recipe", "health tip", "horoscope", "astrology",
    "movie review", "sports result", "entertainment", "reality show",
]


def _safe_date(entry: Any) -> datetime:
    """Parse feedparser entry date → UTC datetime, fallback to now."""
    for attr in ("published", "updated", "created"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                dt = parsedate_to_datetime(raw)
                return dt.astimezone(timezone.utc).replace(tzinfo=None)
            except Exception:
                pass
    return datetime.utcnow()


def _time_ago(dt: datetime) -> str:
    """Convert datetime → '5 min ago' style string."""
    delta = datetime.utcnow() - dt
    secs = int(delta.total_seconds())
    if secs < 60:
        return "just now"
    if secs < 3600:
        return f"{secs // 60}m ago"
    if secs < 86400:
        return f"{secs // 3600}h ago"
    return f"{secs // 86400}d ago"


def _clean_html(text: str) -> str:
    """Strip HTML tags from summary."""
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:400]


def _score_impact(title: str, desc: str) -> str:
    """Return HIGH / MEDIUM / LOW based on keyword signals."""
    text = (title + " " + desc).lower()
    # Check noise first
    if any(kw in text for kw in LOW_IMPACT_NOISE):
        return "LOW"
    if any(kw in text for kw in HIGH_IMPACT_SIGNALS):
        return "HIGH"
    if any(kw in text for kw in MEDIUM_IMPACT_SIGNALS):
        return "MEDIUM"
    return "LOW"


def _categorize(title: str, desc: str, source: str) -> str:
    """
    3-pass categorizer:
    Pass 1 — Title-only (high precision, catches 'RBI cuts repo rate')
    Pass 2 — Full text with threshold matching
    Pass 3 — Full text single-keyword fallback
    """
    title_l = title.lower()
    text    = (title + " " + (desc or "")).lower()
    src     = source.lower()

    # Source shortcuts for official feeds
    if "sebi" in src:
        return "SEBI"
    if "rbi" in src:
        return "RBI"
    if "pib" in src or "gst" in src:
        return "GST_TAX"

    # Pass 1 — Title-only strong signals (single word is enough in title)
    # IMPORTANT: GLOBAL checked FIRST — gold/silver/oil/foreign stocks must not
    # fall into RBI or STOCKS categories.
    TITLE_SIGNALS = [
        ("GLOBAL",  [
            # Foreign markets
            "us fed", "federal reserve", "wall street", "nasdaq", "dow jones",
            "s&p 500", "us market", "us stock", "us economy", "us gdp",
            # Commodities
            "gold price", "silver price", "comex gold", "comex silver",
            "gold rate", "silver rate", "gold today", "silver today",
            "gold falls", "gold rises", "gold hits", "gold slips",
            "crude oil", "brent crude", "wti crude", "oil price",
            "oil falls", "oil rises", "oil hits",
            # Dollar / Forex global
            "dollar index", "dxy ", "yen ", "yuan ", "euro ",
            # Foreign companies / indices
            "nike ", "apple ", "tesla ", "google ", "amazon ", "microsoft ",
            "meta ", "nvidia ", "ftse ", "nikkei ", "hang seng",
            # Global macro
            "imf ", "world bank", "opec ", "china gdp", "us inflation",
            "us cpi", "us jobs", "us payroll",
        ]),
        ("IPO",     [
            "ipo ", " ipo", "allotment", "listing gain", "gmp ",
            "grey market", "oversubscribed", "sme ipo", "mainboard ipo",
            "nfo ", "new fund offer",
        ]),
        ("RBI",     [
            "rbi ", "reserve bank", "repo rate", "monetary policy", "mpc ",
            "inflation data", "cpi data", "wpi data", "gdp data",
            "gdp growth", "iip data", "gdp q", "rbi governor",
        ]),
        ("SEBI",    [
            "sebi ", "sebi circular", "sebi order", "sebi ban", "sebi notice",
            "insider trading", "mutual fund sebi", "ipo sebi",
        ]),
        ("GST_TAX", [
            "gst council", "gst rate", "gst collection", "income tax",
            "cbdt ", "tds ", "gst ", "advance tax", "tax slab",
            "customs duty", "service tax",
        ]),
    ]
    for cat, sigs in TITLE_SIGNALS:
        if any(sig in title_l for sig in sigs):
            return cat

    # Pass 2 — Full text with threshold
    for category, keywords, threshold in CATEGORY_RULES:
        hits = sum(1 for kw in keywords if kw in text)
        if hits >= threshold:
            return category

    # Pass 3 — Full text single-keyword fallback
    for category, keywords, _ in CATEGORY_RULES:
        if any(kw in text for kw in keywords):
            return category

    return "MARKETS"  # default


def _extract_image(entry: Any) -> Optional[str]:
    """Try to extract a thumbnail URL from the feed entry."""
    # Try media:thumbnail
    media = getattr(entry, "media_thumbnail", None)
    if media and isinstance(media, list) and media[0].get("url"):
        return media[0]["url"]
    # Try enclosures
    for enc in getattr(entry, "enclosures", []):
        if enc.get("type", "").startswith("image"):
            return enc.get("href")
    return None


def _is_duplicate(title: str, seen: List[str], threshold: float = 0.82) -> bool:
    for existing in seen:
        ratio = SequenceMatcher(None, title.lower(), existing.lower()).ratio()
        if ratio >= threshold:
            return True
    return False


def _fetch_feed(feed_info: Dict) -> List[Dict]:
    """Fetch one RSS feed and return normalized articles."""
    articles = []
    try:
        feed = feedparser.parse(
            feed_info["url"],
            request_headers={
                "User-Agent": "KEPLER/2.0 AI Stock Research (+https://kepler.in)",
                "Accept": "application/rss+xml, application/xml, text/xml",
            }
        )
        for entry in feed.entries[:20]:
            title = getattr(entry, "title", "").strip()
            if not title or len(title) < 12:
                continue
            desc  = _clean_html(getattr(entry, "summary", "") or getattr(entry, "description", ""))
            url   = getattr(entry, "link", "")
            if not url:
                continue
            pub_dt = _safe_date(entry)
            # Ignore items older than 24 hours
            if (datetime.utcnow() - pub_dt).total_seconds() > 86400:
                continue
            source   = feed_info["source"]
            category = _categorize(title, desc, source)
            impact   = _score_impact(title, desc)
            image    = _extract_image(entry)

            articles.append({
                "id":           f"{hash(url):x}",
                "title":        title,
                "description":  desc,
                "url":          url,
                "source":       source,
                "category":     category,
                "impact":       impact,
                "published_at": pub_dt.isoformat(),
                "time_ago":     _time_ago(pub_dt),
                "image":        image,
                "weight":       feed_info.get("weight", 5),
                "_ts":          pub_dt.timestamp(),
            })
    except Exception as e:
        logger.warning(f"Feed fetch error [{feed_info['source']}]: {e}")
    return articles


def _compute_sort_score(article: Dict) -> float:
    """Higher = show first. Combines recency + impact + source weight."""
    age_hours = (time.time() - article["_ts"]) / 3600
    recency   = max(0, 24 - age_hours) / 24          # 0-1, higher = newer
    impact_v  = {"HIGH": 1.0, "MEDIUM": 0.5, "LOW": 0.1}[article["impact"]]
    weight    = article["weight"] / 10                  # 0-1
    return (impact_v * 0.5) + (recency * 0.35) + (weight * 0.15)


def fetch_all_news(force: bool = False) -> List[Dict]:
    """
    Fetch all RSS feeds in parallel, deduplicate, score, and cache.
    Returns articles sorted by impact + recency.
    """
    cache_key = "live_news"
    if not force and cache_key in _news_cache:
        age = time.time() - _news_cache[cache_key]["ts"]
        if age < _CACHE_TTL:
            logger.debug(f"Live news cache hit (age={age:.0f}s)")
            return _news_cache[cache_key]["data"]

    logger.info(f"Fetching live news from {len(FEEDS)} feeds (parallel)")
    t0 = time.time()

    all_articles: List[Dict] = []
    with ThreadPoolExecutor(max_workers=min(len(FEEDS), 12), thread_name_prefix="news") as pool:
        futures = {pool.submit(_fetch_feed, f): f for f in FEEDS}
        for future in as_completed(futures):
            try:
                all_articles.extend(future.result(timeout=15))
            except Exception as e:
                logger.debug(f"News feed future error: {e}")

    # Deduplicate
    seen_titles: List[str] = []
    unique: List[Dict] = []
    # Sort by impact first so HIGH impact survives dedup
    all_articles.sort(key=lambda x: ({"HIGH": 0, "MEDIUM": 1, "LOW": 2}[x["impact"]], -x["_ts"]))
    for art in all_articles:
        if not _is_duplicate(art["title"], seen_titles):
            seen_titles.append(art["title"])
            unique.append(art)

    # Sort final result by composite score
    unique.sort(key=_compute_sort_score, reverse=True)

    # Remove internal fields
    for art in unique:
        art.pop("_ts", None)
        art.pop("weight", None)

    elapsed = round(time.time() - t0, 1)
    _news_cache[cache_key] = {"data": unique, "ts": time.time()}
    logger.info(f"Live news: {len(unique)} unique articles in {elapsed}s "
                f"({sum(1 for a in unique if a['impact']=='HIGH')} HIGH, "
                f"{sum(1 for a in unique if a['impact']=='MEDIUM')} MEDIUM)")
    return unique


def get_live_news(
    category: Optional[str] = None,
    impact: Optional[str] = None,
    limit: int = 50,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """Public API — returns filtered, categorized live news."""
    articles = fetch_all_news(force=force_refresh)

    if category and category.upper() != "ALL":
        if category.upper() == "BREAKING":
            # BREAKING = HIGH impact from any category
            articles = [a for a in articles if a["impact"] == "HIGH"]
        else:
            articles = [a for a in articles if a["category"] == category.upper()]

    if impact:
        articles = [a for a in articles if a["impact"] == impact.upper()]

    # Stats
    all_arts = fetch_all_news()
    stats = {
        "total": len(all_arts),
        "high_impact": sum(1 for a in all_arts if a["impact"] == "HIGH"),
        "medium_impact": sum(1 for a in all_arts if a["impact"] == "MEDIUM"),
        "categories": {
            "BREAKING":  sum(1 for a in all_arts if a["impact"] == "HIGH"),
            "MARKETS":   sum(1 for a in all_arts if a["category"] == "MARKETS"),
            "STOCKS":    sum(1 for a in all_arts if a["category"] == "STOCKS"),
            "RBI":       sum(1 for a in all_arts if a["category"] == "RBI"),
            "SEBI":      sum(1 for a in all_arts if a["category"] == "SEBI"),
            "GST_TAX":   sum(1 for a in all_arts if a["category"] == "GST_TAX"),
            "IPO":       sum(1 for a in all_arts if a["category"] == "IPO"),
            "GLOBAL":    sum(1 for a in all_arts if a["category"] == "GLOBAL"),
        },
    }

    return {
        "articles":    articles[:limit],
        "count":       len(articles[:limit]),
        "stats":       stats,
        "fetched_at":  datetime.utcnow().isoformat(),
        "cache_age_s": round(time.time() - _news_cache.get("live_news", {}).get("ts", time.time())),
        "next_refresh_in": max(0, _CACHE_TTL - round(time.time() - _news_cache.get("live_news", {}).get("ts", time.time()))),
    }


CATEGORY_META = [
    {"id": "ALL",     "label": "All News",     "icon": "📡", "color": "#00C48C"},
    {"id": "BREAKING","label": "Breaking",     "icon": "🔴", "color": "#ef4444"},
    {"id": "MARKETS", "label": "Markets",      "icon": "📈", "color": "#10b981"},
    {"id": "STOCKS",  "label": "Stocks",       "icon": "💼", "color": "#3b82f6"},
    {"id": "RBI",     "label": "RBI / Macro",  "icon": "🏦", "color": "#8b5cf6"},
    {"id": "SEBI",    "label": "SEBI / Regs",  "icon": "⚖️", "color": "#a78bfa"},
    {"id": "GST_TAX", "label": "GST & Tax",    "icon": "💰", "color": "#f59e0b"},
    {"id": "IPO",     "label": "IPO",          "icon": "🚀", "color": "#ec4899"},
    {"id": "GLOBAL",  "label": "Global",       "icon": "🌐", "color": "#64748b"},
]
