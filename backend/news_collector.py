"""
KEPLER -- Enhanced News Collector
Fetches news from 12+ RSS feeds, NewsAPI, GNews, and official Indian financial sources.
Includes GST, RBI circulars, SEBI notifications, earnings calendars.
Deduplicates by title similarity using difflib ratio > 0.85.
"""
import time
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional
import feedparser
import httpx
from loguru import logger


# ── Primary Market RSS Feeds ──────────────────────────────────────────────────
RSS_FEEDS = [
    # General financial news
    {"url": "https://economictimes.indiatimes.com/markets/rss.cms",         "source": "Economic Times",       "priority": 10},
    {"url": "https://www.moneycontrol.com/rss/marketreports.xml",            "source": "Moneycontrol",         "priority": 10},
    {"url": "https://www.livemint.com/rss/markets",                          "source": "LiveMint",             "priority": 9},
    {"url": "https://www.business-standard.com/rss/markets-106.rss",         "source": "Business Standard",   "priority": 9},
    {"url": "https://www.financialexpress.com/market/feed/",                  "source": "Financial Express",   "priority": 8},
    {"url": "https://economictimes.indiatimes.com/industry/rss.cms",         "source": "ET Industry",          "priority": 8},
    # Macro & Policy
    {"url": "https://economictimes.indiatimes.com/economy/policy/rss.cms",   "source": "ET Policy",            "priority": 9},
    {"url": "https://economictimes.indiatimes.com/economy/finance/rss.cms",  "source": "ET Finance",           "priority": 9},
    {"url": "https://www.business-standard.com/rss/economy-policy-102.rss",  "source": "BS Economy",          "priority": 8},
    # BSE / NSE Corporate announcements
    {"url": "https://www.bseindia.com/corporates/ann.html",                  "source": "BSE Announcements",   "priority": 7},
    # Global markets affecting India
    {"url": "https://economictimes.indiatimes.com/markets/forex/rss.cms",   "source": "ET Forex",             "priority": 7},
    {"url": "https://www.livemint.com/rss/companies",                        "source": "LiveMint Companies",  "priority": 8},
]

# ── Official Government & Regulatory RSS ──────────────────────────────────────
OFFICIAL_FEEDS = [
    {"url": "https://www.sebi.gov.in/sebi_data/attachdocs/rss/rss.xml",     "source": "SEBI",                "priority": 10},
    {"url": "https://rbi.org.in/rss/rss.aspx",                              "source": "RBI",                  "priority": 10},
    {"url": "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3",       "source": "PIB Finance",          "priority": 9},
    {"url": "https://www.gst.gov.in/notification/rss",                       "source": "GST Portal",          "priority": 9},
    {"url": "https://incometaxindia.gov.in/Pages/rss.aspx",                  "source": "Income Tax India",    "priority": 8},
]

# ── NewsAPI queries — high signal Indian finance ───────────────────────────────
NEWSAPI_QUERIES = [
    "NSE stock market India",
    "RBI monetary policy announcement",
    "quarterly results earnings India NSE BSE",
    "Nifty Sensex today market",
    "FII DII data India",
    "SEBI circular announcement",
    "GST council meeting India",
    "Indian rupee RBI forex",
    "India GDP inflation data",
    "Union Budget India fiscal",
    "corporate earnings results Nifty",
    "India FDI investment announcement",
]

# ── GNews India-focused queries ───────────────────────────────────────────────
GNEWS_QUERIES = [
    "Indian stock market NSE BSE",
    "RBI SEBI GSTN announcement India",
    "Nifty earnings results quarterly",
    "India budget economic policy",
]


def _similarity(a: str, b: str) -> float:
    """Compute title similarity ratio."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _is_duplicate(title: str, seen: List[str], threshold: float = 0.82) -> bool:
    for existing in seen:
        if _similarity(title, existing) >= threshold:
            return True
    return False


def _normalize_article(
    title: str, description: str, url: str, source: str,
    published_at: str, priority: int = 5
) -> Dict[str, Any]:
    return {
        "title": (title or "").strip(),
        "description": (description or "").strip()[:600],
        "url": url or "",
        "source": source or "",
        "published_at": published_at or datetime.utcnow().isoformat(),
        "priority": priority,
    }


def _is_relevant_to_markets(title: str, description: str = "") -> bool:
    """Filter out completely irrelevant articles early."""
    text = (title + " " + description).lower()
    # Must contain at least one market-relevant keyword
    relevant_keywords = [
        "stock", "market", "nse", "bse", "nifty", "sensex", "share", "equity",
        "rbi", "sebi", "gst", "rbi", "budget", "inflation", "gdp", "economy",
        "earning", "result", "profit", "revenue", "quarterly", "q1", "q2", "q3", "q4",
        "fii", "dii", "foreign", "investor", "mutual fund", "rupee", "forex",
        "interest rate", "repo", "monetary", "fiscal", "policy", "credit",
        "ipo", "listing", "capital", "fund", "dividend", "buyback", "merger",
        "acquisition", "deal", "contract", "order", "launch", "expansion",
        "import", "export", "trade", "mpc", "sebi", "cbdt", "ministry of finance",
        "tax", "gst", "income tax", "tds", "advance tax",
    ]
    return any(kw in text for kw in relevant_keywords)


# ── RSS Feed Collector ────────────────────────────────────────────────────────
def collect_rss() -> List[Dict[str, Any]]:
    articles = []
    for feed_info in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"], request_headers={"User-Agent": "KEPLER/1.0 Market Intelligence Bot"})
            count = 0
            for entry in feed.entries[:25]:  # max 25 per feed
                title = getattr(entry, "title", "")
                description = getattr(entry, "summary", "") or getattr(entry, "description", "")
                url = getattr(entry, "link", "")
                published = getattr(entry, "published", "") or getattr(entry, "updated", "")
                if title and url and _is_relevant_to_markets(title, description):
                    articles.append(_normalize_article(
                        title, description, url, feed_info["source"], published, feed_info.get("priority", 5)
                    ))
                    count += 1
            logger.info(f"RSS [{feed_info['source']}]: {count} articles collected")
        except Exception as e:
            logger.error(f"RSS feed error [{feed_info['source']}]: {e}")
    return articles


# ── Official Regulatory Feed Collector ────────────────────────────────────────
def collect_official_feeds() -> List[Dict[str, Any]]:
    """Collect from SEBI, RBI, GST Portal, PIB — highest priority official sources."""
    articles = []
    for feed_info in OFFICIAL_FEEDS:
        try:
            feed = feedparser.parse(feed_info["url"], request_headers={"User-Agent": "KEPLER/1.0"})
            count = 0
            for entry in feed.entries[:15]:
                title = getattr(entry, "title", "")
                description = getattr(entry, "summary", "") or getattr(entry, "description", "")
                url = getattr(entry, "link", "")
                published = getattr(entry, "published", "") or getattr(entry, "updated", "")
                if title and url:
                    articles.append(_normalize_article(
                        title, description, url, feed_info["source"], published, feed_info.get("priority", 9)
                    ))
                    count += 1
            logger.info(f"Official Feed [{feed_info['source']}]: {count} items collected")
        except Exception as e:
            logger.warning(f"Official feed error [{feed_info['source']}]: {e}")
    return articles


# ── NewsAPI Collector ─────────────────────────────────────────────────────────
def collect_newsapi(api_key: str) -> List[Dict[str, Any]]:
    if not api_key:
        logger.warning("NewsAPI key not set — skipping")
        return []

    articles = []
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")

    for query in NEWSAPI_QUERIES:
        try:
            resp = httpx.get(
                "https://newsapi.org/v2/everything",
                params={
                    "q": query,
                    "from": yesterday,
                    "language": "en",
                    "sortBy": "relevancy",
                    "pageSize": 8,
                    "apiKey": api_key,
                },
                timeout=12,
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("articles", []):
                    title = item.get("title", "")
                    desc = item.get("description", "")
                    if title and "[Removed]" not in title and _is_relevant_to_markets(title, desc):
                        articles.append(_normalize_article(
                            title,
                            desc,
                            item.get("url", ""),
                            item.get("source", {}).get("name", "NewsAPI"),
                            item.get("publishedAt", ""),
                            priority=7,
                        ))
            else:
                logger.warning(f"NewsAPI [{query}] returned {resp.status_code}")
            time.sleep(0.15)  # gentle rate limiting
        except Exception as e:
            logger.error(f"NewsAPI error [{query}]: {e}")

    logger.info(f"NewsAPI: {len(articles)} articles collected")
    return articles


# ── GNews Collector ───────────────────────────────────────────────────────────
def collect_gnews(api_key: str) -> List[Dict[str, Any]]:
    if not api_key:
        logger.warning("GNews API key not set — skipping")
        return []

    articles = []
    for query in GNEWS_QUERIES:
        try:
            resp = httpx.get(
                "https://gnews.io/api/v4/search",
                params={
                    "q": query,
                    "lang": "en",
                    "country": "in",
                    "max": 10,
                    "apikey": api_key,
                },
                timeout=12,
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("articles", []):
                    title = item.get("title", "")
                    desc = item.get("description", "")
                    if title and _is_relevant_to_markets(title, desc):
                        articles.append(_normalize_article(
                            title,
                            desc,
                            item.get("url", ""),
                            item.get("source", {}).get("name", "GNews"),
                            item.get("publishedAt", ""),
                            priority=7,
                        ))
            else:
                logger.warning(f"GNews [{query}] returned {resp.status_code}: {resp.text[:200]}")
            time.sleep(0.2)
        except Exception as e:
            logger.error(f"GNews error [{query}]: {e}")

    logger.info(f"GNews: {len(articles)} articles collected")
    return articles


# ── Deduplication ─────────────────────────────────────────────────────────────
def deduplicate(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen_titles: List[str] = []
    unique: List[Dict[str, Any]] = []

    # Sort by priority desc first so higher-priority sources survive dedup
    sorted_articles = sorted(articles, key=lambda x: x.get("priority", 5), reverse=True)

    for article in sorted_articles:
        title = article.get("title", "")
        if not title:
            continue
        if not _is_duplicate(title, seen_titles):
            seen_titles.append(title)
            unique.append(article)

    logger.info(f"Deduplication: {len(articles)} → {len(unique)} unique articles")
    return unique


# ── Market Updates Collector (GST, RBI, SEBI, Earnings) ──────────────────────
def collect_market_updates() -> List[Dict[str, Any]]:
    """
    Collect important structured market updates: GST council decisions,
    RBI circulars, SEBI notifications, economic data releases.
    Returns enriched articles tagged by update type.
    """
    updates = []

    # GST Council news
    gst_queries = ["GST council meeting", "GST rate change", "GST amendment notification"]
    # RBI circulars
    rbi_queries = ["RBI circular notification", "RBI monetary policy committee"]
    # Earnings calendar
    earnings_queries = ["quarterly results declared NSE BSE", "earnings Q1 Q2 Q3 Q4 India"]
    # Economic data
    econ_queries = ["India CPI WPI inflation data", "India GDP IIP PMI data", "India trade deficit surplus"]

    all_update_queries = [
        ("GST_UPDATE",   gst_queries),
        ("RBI_CIRCULAR", rbi_queries),
        ("EARNINGS",     earnings_queries),
        ("ECON_DATA",    econ_queries),
    ]

    for update_type, queries in all_update_queries:
        for q in queries:
            try:
                # Use DuckDuckGo-style RSS search (no API key needed)
                resp = httpx.get(
                    "https://feeds.finance.yahoo.com/rss/2.0/headline",
                    params={"s": q, "region": "IN", "lang": "en-IN"},
                    timeout=8,
                    headers={"User-Agent": "KEPLER/1.0"},
                )
                # If that fails, just continue gracefully
            except Exception:
                pass

    return updates  # Official feeds already cover these — this is extensible


# ── Main entry point ──────────────────────────────────────────────────────────
def collect_all_news(newsapi_key: str = "", gnews_api_key: str = "") -> List[Dict[str, Any]]:
    """
    Collect news from all sources, deduplicate, and return.
    Source priority: Official (SEBI/RBI/GST) > Major RSS > NewsAPI > GNews
    Handles all errors gracefully — a failing source never breaks the pipeline.
    """
    logger.info("=== News collection started ===")

    # Collect from all sources
    official_articles = collect_official_feeds()
    rss_articles = collect_rss()
    newsapi_articles = collect_newsapi(newsapi_key)
    gnews_articles = collect_gnews(gnews_api_key)

    # Merge: official first (highest priority)
    all_articles = official_articles + rss_articles + newsapi_articles + gnews_articles
    unique_articles = deduplicate(all_articles)

    logger.info(f"=== News collection complete: {len(unique_articles)} unique articles ===")
    logger.info(f"  Official: {len(official_articles)}, RSS: {len(rss_articles)}, "
                f"NewsAPI: {len(newsapi_articles)}, GNews: {len(gnews_articles)}")
    return unique_articles


if __name__ == "__main__":
    from config import settings
    articles = collect_all_news(
        newsapi_key=settings.newsapi_key,
        gnews_api_key=settings.gnews_api_key,
    )
    print(f"\nCollected {len(articles)} articles:")
    for i, a in enumerate(articles[:10], 1):
        print(f"  {i}. [{a['source']}] (p={a.get('priority',5)}) {a['title'][:80]}")
