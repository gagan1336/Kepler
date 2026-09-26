"""
KEPLER — News Sentiment Engine
================================
Fetches the last 48-hour news for a list of NSE stock symbols,
runs Gemini Flash sentiment scoring, and returns per-stock:
  - sentiment_score  : -1.0 to +1.0
  - sentiment_label  : "BULLISH" / "BEARISH" / "NEUTRAL"
  - news_catalyst    : bool — positive news aligned with technicals
  - news_risk        : bool — negative news could invalidate setup
  - top_headline     : most relevant headline
  - sentiment_boost  : probability adjustment (+/- percentage points)

Caches results per symbol for 4 hours.
"""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import feedparser
import httpx
from loguru import logger

try:
    import google.generativeai as genai
    _GENAI_AVAILABLE = True
except ImportError:
    _GENAI_AVAILABLE = False

try:
    from config import settings
    _HAS_SETTINGS = True
except ImportError:
    _HAS_SETTINGS = False

# ── Cache ──────────────────────────────────────────────────────────────────────
_sentiment_cache: Dict[str, Dict] = {}
_SENTIMENT_TTL = 4 * 3600   # 4 hours

# ── RSS feeds for Indian financial news ───────────────────────────────────────
NEWS_FEEDS = [
    "https://economictimes.indiatimes.com/markets/rss.cms",
    "https://www.moneycontrol.com/rss/marketreports.xml",
    "https://www.livemint.com/rss/markets",
    "https://www.business-standard.com/rss/markets-106.rss",
    "https://www.livemint.com/rss/companies",
]

# ── Keyword sentiment maps (fast fallback) ────────────────────────────────────
BULLISH_KEYWORDS = [
    "record high","all-time high","52-week high","breakout","surge","rally",
    "beats estimates","strong results","profit jumps","revenue growth",
    "upgrade","buy","outperform","positive","bullish","gains","rises",
    "acquisition","merger","expansion","new contract","order win",
    "dividend","buyback","bonus","split","demerger",
]
BEARISH_KEYWORDS = [
    "crash","plunge","fall","decline","loss","misses estimates","below expectation",
    "downgrade","sell","underperform","negative","bearish","drops","slumps",
    "regulatory","sebi notice","probe","fraud","insolvency","debt","default",
    "management change","ceo resign","plant shutdown","strike",
]


def _is_cache_valid(symbol: str) -> bool:
    entry = _sentiment_cache.get(symbol)
    if not entry:
        return False
    age = (datetime.utcnow() - entry["fetched_at"]).total_seconds()
    return age < _SENTIMENT_TTL


def _fetch_rss_headlines(timeout: int = 8) -> List[Dict]:
    """Fetch headlines from all RSS feeds (combined, last 48h)."""
    all_articles = []
    cutoff = datetime.utcnow() - timedelta(hours=48)

    for feed_url in NEWS_FEEDS:
        try:
            with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                resp = client.get(feed_url, headers={"User-Agent": "Mozilla/5.0"})
                feed = feedparser.parse(resp.text)
            for entry in feed.entries[:30]:
                title   = getattr(entry, "title", "")
                summary = getattr(entry, "summary", "")
                link    = getattr(entry, "link", "")
                # Parse date
                pub_dt = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        pub_dt = datetime(*entry.published_parsed[:6])
                    except Exception:
                        pass
                # Include only recent
                if pub_dt and pub_dt < cutoff:
                    continue
                all_articles.append({
                    "title":   title,
                    "summary": summary,
                    "link":    link,
                    "pub_dt":  pub_dt,
                })
        except Exception as e:
            logger.debug(f"RSS fetch failed for {feed_url}: {e}")

    return all_articles


def _filter_articles_for_symbol(
    articles: List[Dict], symbol: str, company_name: str = ""
) -> List[Dict]:
    """Return articles mentioning this stock symbol or company name."""
    raw_sym = symbol.replace(".NS", "").replace(".BO", "").upper()
    keywords = [raw_sym]
    if company_name:
        # Extract first meaningful word from company name
        parts = company_name.split()[:2]
        keywords += [p.upper() for p in parts if len(p) > 3]

    matched = []
    for art in articles:
        text = (art["title"] + " " + art.get("summary", "")).upper()
        if any(kw in text for kw in keywords):
            matched.append(art)

    return matched[:10]  # max 10 articles per stock


def _keyword_sentiment(articles: List[Dict]) -> float:
    """Fast keyword-based sentiment score (-1 to +1)."""
    if not articles:
        return 0.0

    score = 0.0
    for art in articles:
        text = (art["title"] + " " + art.get("summary", "")).lower()
        bull = sum(1 for kw in BULLISH_KEYWORDS if kw in text)
        bear = sum(1 for kw in BEARISH_KEYWORDS if kw in text)
        score += (bull - bear) * 0.2

    return max(-1.0, min(1.0, score / len(articles)))


def _gemini_sentiment(symbol: str, articles: List[Dict]) -> Optional[Dict]:
    """Use Gemini Flash to score sentiment for a stock's news articles."""
    if not _GENAI_AVAILABLE or not _HAS_SETTINGS:
        return None

    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")

        headlines = "\n".join(
            [f"- {a['title']}" for a in articles[:6]]
        )
        prompt = f"""You are a quantitative analyst evaluating news sentiment for a swing trade.

Stock: {symbol.replace('.NS','')}
Recent headlines (last 48 hours):
{headlines}

Rate the overall sentiment impact on this stock for a 2-4 week swing trade.

Respond ONLY in this exact JSON format (no markdown):
{{
  "sentiment_score": <float -1.0 to 1.0>,
  "sentiment_label": "<BULLISH|BEARISH|NEUTRAL>",
  "news_catalyst": <true|false>,
  "news_risk": <true|false>,
  "top_headline": "<most impactful headline>",
  "reasoning": "<1 sentence>"
}}

Where:
- sentiment_score: -1.0 = very bearish, 0 = neutral, +1.0 = very bullish
- news_catalyst: true if positive news is a clear near-term catalyst
- news_risk: true if negative news could invalidate a bullish trade setup
"""
        resp = model.generate_content(prompt, generation_config={"temperature": 0.2})
        raw = resp.text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        return {
            "sentiment_score": float(data.get("sentiment_score", 0.0)),
            "sentiment_label": str(data.get("sentiment_label", "NEUTRAL")),
            "news_catalyst":   bool(data.get("news_catalyst", False)),
            "news_risk":       bool(data.get("news_risk", False)),
            "top_headline":    str(data.get("top_headline", "")),
            "reasoning":       str(data.get("reasoning", "")),
            "source":          "gemini",
        }
    except Exception as e:
        logger.debug(f"Gemini sentiment failed for {symbol}: {e}")
        return None


def _sentiment_boost(score: float) -> float:
    """Convert sentiment score (-1 to +1) → probability boost/penalty in pp."""
    # Max boost: +8pp for very bullish, max penalty: -10pp for very bearish
    if score > 0:
        return round(score * 8.0, 1)
    else:
        return round(score * 10.0, 1)


def get_stock_sentiment(
    symbol: str,
    company_name: str = "",
    all_articles: Optional[List[Dict]] = None,
) -> Dict:
    """
    Main public API — returns sentiment dict for a single stock.
    If all_articles is passed (pre-fetched RSS), skips re-fetching.
    """
    if _is_cache_valid(symbol):
        return _sentiment_cache[symbol]["data"]

    # Fetch articles if not provided
    if all_articles is None:
        all_articles = _fetch_rss_headlines()

    matched = _filter_articles_for_symbol(all_articles, symbol, company_name)

    if not matched:
        result = {
            "symbol":          symbol,
            "sentiment_score": 0.0,
            "sentiment_label": "NEUTRAL",
            "news_catalyst":   False,
            "news_risk":       False,
            "top_headline":    None,
            "reasoning":       "No recent news found",
            "article_count":   0,
            "sentiment_boost": 0.0,
            "source":          "no_news",
        }
        _sentiment_cache[symbol] = {"data": result, "fetched_at": datetime.utcnow()}
        return result

    # Try Gemini first, fall back to keyword scoring
    gemini_result = _gemini_sentiment(symbol, matched)

    if gemini_result:
        score = gemini_result["sentiment_score"]
        result = {
            "symbol":          symbol,
            "sentiment_score": score,
            "sentiment_label": gemini_result["sentiment_label"],
            "news_catalyst":   gemini_result["news_catalyst"],
            "news_risk":       gemini_result["news_risk"],
            "top_headline":    gemini_result.get("top_headline") or matched[0]["title"],
            "reasoning":       gemini_result.get("reasoning", ""),
            "article_count":   len(matched),
            "sentiment_boost": _sentiment_boost(score),
            "source":          "gemini",
        }
    else:
        # Keyword fallback
        score = _keyword_sentiment(matched)
        if score >= 0.3:
            label = "BULLISH"
        elif score <= -0.3:
            label = "BEARISH"
        else:
            label = "NEUTRAL"

        result = {
            "symbol":          symbol,
            "sentiment_score": score,
            "sentiment_label": label,
            "news_catalyst":   score >= 0.5,
            "news_risk":       score <= -0.5,
            "top_headline":    matched[0]["title"] if matched else None,
            "reasoning":       "Keyword-based sentiment analysis",
            "article_count":   len(matched),
            "sentiment_boost": _sentiment_boost(score),
            "source":          "keywords",
        }

    _sentiment_cache[symbol] = {"data": result, "fetched_at": datetime.utcnow()}
    return result


def get_batch_sentiment(
    stocks: List[Dict],
    workers: int = 5,
) -> Dict[str, Dict]:
    """
    Fetch sentiment for a list of stocks (each dict must have 'symbol' key).
    Fetches RSS once, then processes all stocks in parallel.
    Returns dict: symbol -> sentiment_result
    """
    logger.info(f"Fetching news sentiment for {len(stocks)} stocks")
    t0 = time.time()

    # Pre-fetch all RSS articles once
    all_articles = _fetch_rss_headlines()
    logger.info(f"Fetched {len(all_articles)} RSS articles")

    results: Dict[str, Dict] = {}

    def _process(stock: Dict) -> tuple:
        sym = stock.get("symbol", "")
        if not sym.endswith(".NS"):
            sym = sym + ".NS"
        name = stock.get("company_name", "")
        sentiment = get_stock_sentiment(sym, name, all_articles)
        return sym, sentiment

    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="sentiment") as pool:
        futures = {pool.submit(_process, s): s for s in stocks}
        for fut in as_completed(futures):
            try:
                sym, sentiment = fut.result()
                results[sym] = sentiment
            except Exception as e:
                logger.debug(f"Sentiment error: {e}")

    elapsed = round(time.time() - t0, 1)
    logger.info(f"Sentiment done: {len(results)} stocks in {elapsed}s")
    return results


if __name__ == "__main__":
    # Quick test
    test_stocks = [
        {"symbol": "RELIANCE.NS", "company_name": "Reliance Industries"},
        {"symbol": "TCS.NS",      "company_name": "Tata Consultancy Services"},
        {"symbol": "HDFCBANK.NS", "company_name": "HDFC Bank"},
    ]
    results = get_batch_sentiment(test_stocks)
    for sym, sent in results.items():
        print(f"\n{sym}: {sent['sentiment_label']} ({sent['sentiment_score']:.2f})")
        print(f"  Headline: {sent.get('top_headline', 'N/A')}")
        print(f"  Catalyst: {sent['news_catalyst']} | Risk: {sent['news_risk']}")
        print(f"  Boost:    {sent['sentiment_boost']:+.1f}pp")
