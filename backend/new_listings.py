"""
new_listings.py — Recently listed stocks on NSE and BSE
=========================================================
Data pipeline:
  1. NSE EQUITY_L.csv  → symbols + listing dates (100+ entries, 90-day window)
  2. ipopremium.in     → issue_price (price band max), GMP for post-listing stocks
  3. yfinance          → live price, change%, market cap (parallel, top 60)

Cache: 6-hour disk cache.
"""
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
import yfinance as yf
from bs4 import BeautifulSoup
from loguru import logger

# ── Constants ─────────────────────────────────────────────────────────────────

_CACHE_FILE = os.path.join(os.path.dirname(__file__), ".cache", "new_listings.json")
_CACHE_TTL_HOURS = 6

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

_session = requests.Session()
_session.headers.update(_HEADERS)


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — NSE EQUITY_L.CSV (primary listing source)
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_listing_date(raw: str) -> Optional[datetime]:
    for fmt in ("%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt)
        except ValueError:
            continue
    return None


def _fetch_nse_equity_list(days: int = 90) -> List[Dict]:
    """Download NSE EQUITY_L.csv and return stocks listed within `days` days."""
    results = []
    try:
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        resp = _session.get(url, timeout=20)
        if resp.status_code != 200:
            logger.warning(f"NSE EQUITY_L.csv returned {resp.status_code}")
            return []

        cutoff = datetime.now() - timedelta(days=days)
        lines = resp.text.strip().split("\n")
        # CSV header: SYMBOL,NAME OF COMPANY,SERIES,DATE OF LISTING,PAID UP VALUE,...
        for line in lines[1:]:
            parts = [p.strip().strip('"') for p in line.split(",")]
            if len(parts) < 5:
                continue
            symbol = parts[0].upper()
            company = parts[1]
            series = parts[2]
            date_raw = parts[3]

            if series not in ("EQ", "SM", "ST", "BE"):
                continue
            if not symbol or len(symbol) > 15:
                continue

            listing_dt = _parse_listing_date(date_raw)
            if listing_dt and listing_dt >= cutoff:
                results.append({
                    "symbol": symbol,
                    "company_name": company,
                    "listing_date": date_raw,
                    "listing_dt": listing_dt.isoformat(),
                    "exchange": "NSE",
                    "series": series,
                    "issue_price": None,
                    "gmp_price": None,
                    "gmp_pct": None,
                })

        logger.info(f"NSE EQUITY_L: {len(results)} listings in last {days} days")
    except Exception as e:
        logger.error(f"NSE EQUITY_L fetch failed: {e}")

    return sorted(results, key=lambda x: x.get("listing_dt", ""), reverse=True)


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — IPOPREMIUM.IN (issue price + GMP for post-listing stocks)
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_ipopremium_prices() -> Dict[str, Dict]:
    """
    Scrape ipopremium.in for issue price (price band) and GMP.
    Returns dict keyed by cleaned company-name keywords for fuzzy matching.
    Also returns a list format for matching by company name fragments.
    """
    result: Dict[str, Dict] = {}
    try:
        resp = requests.get("https://ipopremium.in/", headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")
        tables = soup.find_all("table")

        if len(tables) < 2:
            return result

        tbl = tables[1]  # Main IPO table
        rows = tbl.find_all("tr")

        for row in rows[1:]:
            cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if len(cols) < 6:
                continue

            raw_name    = cols[0]
            raw_gmp     = cols[2] if len(cols) > 2 else "0"
            raw_price   = cols[5] if len(cols) > 5 else ""

            # Clean company name — remove exchange suffix
            name = re.sub(r"\s*\((?:MAINBOARD|NSE SME|BSE SME|SME|Tentative.*?)\).*$", "",
                          raw_name, flags=re.IGNORECASE).strip().lower()
            if not name:
                continue

            # Parse price band → use upper bound as issue price
            pb_nums = re.findall(r"[\d.]+", re.sub(r"[^\d.\-–]", "-", raw_price))
            issue_price = float(pb_nums[-1]) if pb_nums else None

            # GMP
            gmp_price = None
            gmp_pct = None
            try:
                gmp_raw = re.sub(r"[^\d.\-]", "", raw_gmp)
                gmp_price = float(gmp_raw) if gmp_raw else 0.0
                if issue_price and issue_price > 0 and gmp_price is not None:
                    gmp_pct = round((gmp_price / issue_price) * 100, 1)
            except (ValueError, TypeError):
                pass

            # Build keyword set for fuzzy matching
            STOPWORDS = {
                "limited", "private", "india", "technologies", "solutions",
                "enterprises", "industries", "services", "international", "infra",
                "infratech", "tech", "corp", "group", "venture", "ventures",
                "capital", "finance", "financial", "holdings", "holding",
                "engineering", "manufactur", "packaging", "energy",
            }
            keywords = set(
                w for w in re.sub(r"[^a-z0-9 ]", "", name).split()
                if len(w) > 2 and w not in STOPWORDS
            )
            result[name] = {
                "issue_price": issue_price,
                "gmp_price": gmp_price,
                "gmp_pct": gmp_pct,
                "keywords": keywords,
            }

        logger.info(f"ipopremium.in: {len(result)} IPO prices scraped for enrichment")
    except Exception as e:
        logger.warning(f"ipopremium.in price fetch failed: {e}")
    return result


def _fuzzy_match_company(company_name: str, ipo_prices: Dict[str, Dict]) -> Optional[Dict]:
    """Match a NSE listing company name to ipopremium data."""
    if not company_name or not ipo_prices:
        return None
    name_lower = company_name.lower()
    name_clean = re.sub(r"[^a-z0-9 ]", "", name_lower)
    name_words = set(w for w in name_clean.split() if len(w) > 2)

    STOPWORDS = {
        "limited", "private", "india", "technologies", "solutions",
        "enterprises", "industries", "services", "international",
        "tech", "corp", "group", "capital", "finance", "financial",
        "holdings", "holding", "engineering", "packaging", "energy",
    }
    sig_words = name_words - STOPWORDS

    best_match = None
    best_score = 0

    for key, val in ipo_prices.items():
        key_clean = re.sub(r"[^a-z0-9 ]", "", key)
        # Direct containment check
        if key_clean in name_clean or name_clean in key_clean:
            return val
        # Word overlap
        key_words = val.get("keywords", set())
        overlap = len(sig_words & key_words)
        if overlap > best_score:
            best_score = overlap
            best_match = val

    # Lower threshold: even 1 significant word is enough for short names
    threshold = 1 if len(sig_words) <= 2 else 2
    return best_match if best_score >= threshold else None


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — YFINANCE live price enrichment (parallel)
# ═══════════════════════════════════════════════════════════════════════════════

def _enrich_one(item: Dict) -> Dict:
    """Fetch live price for one listing via yfinance."""
    symbol = item.get("symbol", "")
    enriched = dict(item)
    enriched.setdefault("current_price", None)
    enriched.setdefault("change_pct", None)
    enriched.setdefault("listing_gain_pct", None)
    enriched.setdefault("market_cap", None)

    for suffix in [".NS", ".BO"]:
        try:
            fi = yf.Ticker(f"{symbol}{suffix}").fast_info
            price = getattr(fi, "last_price", None) or getattr(fi, "regularMarketPrice", None)
            if price and float(price) > 0:
                enriched["current_price"] = round(float(price), 2)
                prev = getattr(fi, "previous_close", None)
                if prev and float(prev) > 0:
                    enriched["change_pct"] = round(
                        ((enriched["current_price"] - float(prev)) / float(prev)) * 100, 2
                    )
                mc = getattr(fi, "market_cap", None)
                if mc:
                    enriched["market_cap"] = int(mc)
                break
        except Exception:
            continue

    # Compute gain from issue price
    issue_price = enriched.get("issue_price")
    current_price = enriched.get("current_price")
    if current_price and issue_price and float(issue_price) > 0:
        enriched["listing_gain_pct"] = round(
            ((current_price - float(issue_price)) / float(issue_price)) * 100, 2
        )

    return enriched


def _enrich_with_live_prices(listings: List[Dict]) -> List[Dict]:
    """Parallel yfinance enrichment for all listings (max 8 workers)."""
    enriched = []
    with ThreadPoolExecutor(max_workers=8, thread_name_prefix="yf") as pool:
        futures = {pool.submit(_enrich_one, item): item for item in listings}
        for fut in as_completed(futures, timeout=90):
            try:
                enriched.append(fut.result())
            except Exception:
                enriched.append(futures[fut])
    # Re-sort by listing date
    enriched.sort(key=lambda x: x.get("listing_dt", ""), reverse=True)
    return enriched


# ═══════════════════════════════════════════════════════════════════════════════
# CACHE
# ═══════════════════════════════════════════════════════════════════════════════

def _load_cache(days: int = 90) -> Optional[List[Dict]]:
    try:
        if not os.path.exists(_CACHE_FILE):
            return None
        with open(_CACHE_FILE, encoding="utf-8") as f:
            cached = json.load(f)
        age_h = (time.time() - cached.get("timestamp", 0)) / 3600
        if age_h < _CACHE_TTL_HOURS:
            listings = cached.get("listings", [])
            cutoff = datetime.now() - timedelta(days=days)
            filtered = [
                l for l in listings
                if not l.get("listing_dt") or
                   datetime.fromisoformat(l["listing_dt"]) >= cutoff
            ]
            logger.info(f"New listings loaded from cache: {len(filtered)} items ({age_h:.1f}h old)")
            return filtered
    except Exception as e:
        logger.warning(f"New listings cache load failed: {e}")
    return None


def _save_cache(listings: List[Dict]) -> None:
    try:
        os.makedirs(os.path.dirname(_CACHE_FILE), exist_ok=True)
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {"timestamp": time.time(), "listings": listings},
                f, ensure_ascii=False, default=str
            )
        logger.info(f"New listings cache saved: {len(listings)} items")
    except Exception as e:
        logger.warning(f"New listings cache save failed: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_new_listings(days: int = 90, force_refresh: bool = False) -> List[Dict]:
    """
    Fetch stocks recently listed on NSE/BSE with live prices and IPO metrics.

    Returns list of:
      symbol, company_name, listing_date, listing_dt, exchange, series,
      issue_price, gmp_price, gmp_pct,
      current_price, change_pct, listing_gain_pct, market_cap
    """
    if not force_refresh:
        cached = _load_cache(days)
        if cached is not None:
            return cached

    logger.info(f"Fetching fresh new listings (last {days} days)…")

    # 1. Get listing symbols from NSE (always 90 days to cache maximum)
    listings = _fetch_nse_equity_list(days=90)

    # 2. Enrich with issue price + GMP from ipopremium.in
    try:
        ipo_prices = _fetch_ipopremium_prices()
        if ipo_prices:
            for item in listings:
                match = _fuzzy_match_company(item.get("company_name", ""), ipo_prices)
                if match:
                    item["issue_price"] = match.get("issue_price")
                    item["gmp_price"] = match.get("gmp_price")
                    item["gmp_pct"] = match.get("gmp_pct")
            matched = sum(1 for l in listings if l.get("issue_price"))
            logger.info(f"Issue price enrichment: {matched}/{len(listings)} matched from ipopremium")
    except Exception as e:
        logger.warning(f"IPO price enrichment failed: {e}")

    # 3. Filter by requested days then take top 60
    cutoff = datetime.now() - timedelta(days=days)
    filtered = [
        l for l in listings
        if not l.get("listing_dt") or
           datetime.fromisoformat(l["listing_dt"]) >= cutoff
    ][:60]

    # 4. Live price enrichment via yfinance (parallel)
    enriched = _enrich_with_live_prices(filtered)

    _save_cache(enriched)
    return enriched
