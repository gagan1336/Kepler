"""
ANTIGRAVITY — IPO Intelligence Hub (ipo_live.py)

Primary data source: ipopremium.in (publicly accessible, no auth required)
  → Provides: IPO calendar, GMP, price band, dates, lot size, issue size

Secondary: chittorgarh.com for supplementary detail
AI verdicts: Gemini Flash (structured JSON, 7-day disk cache)

30-minute TTL memory cache.
"""
import copy
import hashlib
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from loguru import logger

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

_CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
os.makedirs(_CACHE_DIR, exist_ok=True)

_CACHE_TTL = 1800          # 30 min memory cache
_VERDICT_TTL_DAYS = 7      # 7-day disk cache for AI verdicts
_AI_VERDICT_CACHE_FILE = os.path.join(_CACHE_DIR, "ipo_verdicts.json")

_cache: Dict[str, Any] = {}
_fetching = False

# ═══════════════════════════════════════════════════════════════════════════════
# DATE / STATUS HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _parse_date(s: Any) -> Optional[date]:
    if not s:
        return None
    if isinstance(s, date):
        return s
    s = str(s).strip()
    for fmt in ("%b %d, %Y", "%d-%b-%Y", "%Y-%m-%d", "%d/%m/%Y", "%d %b %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _ipo_status(open_d: Optional[date], close_d: Optional[date],
                listing_d: Optional[date]) -> str:
    today = date.today()
    if listing_d and today >= listing_d:
        return "LISTED"
    if close_d and today > close_d:
        return "ALLOTMENT"
    if open_d and close_d and open_d <= today <= close_d:
        return "OPEN"
    if open_d and today < open_d:
        return "UPCOMING"
    return "UNKNOWN"


def _days_until(d: Optional[date]) -> Optional[int]:
    if not d:
        return None
    return (d - date.today()).days


def _clean_company_name(raw: str) -> str:
    """Strip exchange/type suffixes from IPO company names."""
    name = re.sub(r"\s*\(MAINBOARD\).*$", "", raw, flags=re.IGNORECASE)
    name = re.sub(r"\s*\(NSE SME\).*$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*\(BSE SME\).*$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*\(SME\).*$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*\(Tentative.*?\).*$", "", name, flags=re.IGNORECASE)
    return name.strip()


def _parse_price_band(raw: str):
    """Parse '398–419' or '₹140-148' → (min, max, formatted_string)."""
    raw = raw.replace("–", "-").replace("—", "-").strip()
    raw_clean = re.sub(r"[^\d.\-]", "", raw)
    nums = re.findall(r"[\d.]+", raw_clean)
    if len(nums) >= 2:
        lo, hi = float(nums[0]), float(nums[-1])
        return lo, hi, f"₹{int(lo)}–{int(hi)}"
    elif len(nums) == 1:
        v = float(nums[0])
        return v, v, f"₹{int(v)}"
    return None, None, raw


# ═══════════════════════════════════════════════════════════════════════════════
# PRIMARY SOURCE: ipopremium.in
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_ipopremium() -> List[Dict]:
    """
    Scrape ipopremium.in — the best free IPO data source.

    Table 1 columns (verified 2026-07-03):
    Company Name | Type | GMP (₹) | Open | Close | Price Band (₹) | Listing Date
    """
    url = "https://ipopremium.in/"
    ipos = []
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=20)
        resp.raise_for_status()
        # Force UTF-8 for rupee symbol
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "lxml")
        tables = soup.find_all("table")

        if len(tables) < 2:
            logger.warning("ipopremium.in: expected ≥2 tables, got fewer")
            return []

        # Table 1 is the main IPO list
        tbl = tables[1]
        rows = tbl.find_all("tr")
        if not rows:
            return []

        # Parse header to determine column positions
        hdr = [c.get_text(strip=True).lower() for c in rows[0].find_all(["th", "td"])]
        logger.debug(f"ipopremium header: {hdr}")

        # Expected: company | type | gmp | open | close | price band | listing date
        for row in rows[1:]:
            cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if len(cols) < 4:
                continue

            # Map by position (robust to minor layout changes)
            raw_name    = cols[0] if len(cols) > 0 else ""
            raw_type    = cols[1] if len(cols) > 1 else "EQ"
            raw_gmp     = cols[2] if len(cols) > 2 else "0"
            raw_open    = cols[3] if len(cols) > 3 else ""
            raw_close   = cols[4] if len(cols) > 4 else ""
            raw_price   = cols[5] if len(cols) > 5 else ""
            raw_listing = cols[6] if len(cols) > 6 else ""

            company_name = _clean_company_name(raw_name)
            if not company_name:
                continue

            # Determine exchange from type/name
            exchange = "NSE,BSE"
            if "NSE SME" in raw_name or raw_type.upper() == "SME":
                exchange = "NSE SME"
            elif "BSE SME" in raw_name:
                exchange = "BSE SME"

            issue_type = "SME" if raw_type.upper() == "SME" else "Book Built"

            # GMP
            gmp_price = None
            try:
                gmp_raw = re.sub(r"[^\d.\-]", "", raw_gmp)
                gmp_price = float(gmp_raw) if gmp_raw else 0.0
            except (ValueError, TypeError):
                gmp_price = 0.0

            # Dates
            open_d    = _parse_date(raw_open)
            close_d   = _parse_date(raw_close)
            listing_d = _parse_date(raw_listing)
            status    = _ipo_status(open_d, close_d, listing_d)

            # Price band
            pb_min, pb_max, pb_str = _parse_price_band(raw_price)

            # GMP premium % (calculated from price band max)
            gmp_pct = None
            if pb_max and gmp_price is not None and pb_max > 0:
                gmp_pct = round((gmp_price / pb_max) * 100, 1)

            # Est. listing from GMP
            est_listing = None
            if pb_max and gmp_price is not None:
                est_listing = round(pb_max + gmp_price, 1)

            uid = hashlib.md5(company_name.encode("utf-8")).hexdigest()[:10]

            ipo = {
                "id": uid,
                "company_name": company_name,
                "symbol": "",
                "industry": "",
                "price_band": pb_str,
                "price_band_min": pb_min,
                "price_band_max": pb_max,
                "lot_size": None,
                "min_investment": None,
                "issue_size_cr": None,
                "issue_type": issue_type,
                "exchange": exchange,
                "registrar": "",
                "open_date": str(open_d) if open_d else None,
                "close_date": str(close_d) if close_d else None,
                "allotment_date": None,
                "listing_date": str(listing_d) if listing_d else None,
                "days_to_open": _days_until(open_d),
                "days_to_close": _days_until(close_d),
                "days_to_listing": _days_until(listing_d),
                "status": status,
                "rhp_url": "https://www.nseindia.com/market-data/all-upcoming-issues-ipo",
                "drhp_url": "",
                "source": "ipopremium.in",
                "gmp": {
                    "gmp_price": gmp_price,
                    "premium_pct": gmp_pct,
                    "est_listing": est_listing,
                    "source": "ipopremium.in (grey market, unofficial)",
                } if gmp_price is not None else None,
            }
            ipos.append(ipo)

        logger.info(f"ipopremium.in: {len(ipos)} IPOs parsed")
    except Exception as e:
        logger.error(f"ipopremium.in scrape failed: {e}")

    return ipos


# ═══════════════════════════════════════════════════════════════════════════════
# SECONDARY: chittorgarh.com — supplement with lot size / registrar info
# ═══════════════════════════════════════════════════════════════════════════════

def _fetch_chittorgarh_detail() -> Dict[str, Dict]:
    """
    Scrape chittorgarh.com for additional IPO detail (lot size, registrar, etc.)
    Returns dict keyed by first word of company name (for fuzzy matching).
    """
    detail: Dict[str, Dict] = {}
    try:
        resp = requests.get("https://www.chittorgarh.com/ipo/", headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")
        # Try to find individual IPO links to enrich data
        # For now just return empty — chittorgarh page doesn't have lot size in list view
    except Exception as e:
        logger.debug(f"Chittorgarh supplement failed: {e}")
    return detail


# ═══════════════════════════════════════════════════════════════════════════════
# AI VERDICT — Gemini Flash structured output
# ═══════════════════════════════════════════════════════════════════════════════

def _load_verdict_cache() -> Dict:
    try:
        if os.path.exists(_AI_VERDICT_CACHE_FILE):
            with open(_AI_VERDICT_CACHE_FILE, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _save_verdict_cache(cache: Dict):
    try:
        with open(_AI_VERDICT_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _generate_ai_verdict(ipo: Dict) -> Dict:
    """Generate structured APPLY/CAUTIOUS/AVOID verdict via Gemini Flash."""
    verdict_cache = _load_verdict_cache()
    cache_key = ipo["id"]

    # Return cached verdict if fresh
    if cache_key in verdict_cache:
        cached = verdict_cache[cache_key]
        age_days = (time.time() - cached.get("_ts", 0)) / 86400
        if age_days < _VERDICT_TTL_DAYS:
            return cached.get("verdict", _fallback_verdict())

    try:
        from config import settings
        import google.generativeai as genai

        if not getattr(settings, "gemini_api_key", None):
            return _fallback_verdict()

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")

        gmp_info = ""
        if ipo.get("gmp") and ipo["gmp"].get("gmp_price") is not None:
            g = ipo["gmp"]
            gmp_info = (
                f"GMP: ₹{g['gmp_price']} "
                f"({'+'  if g['gmp_price'] >= 0 else ''}{g.get('premium_pct', 'N/A')}% premium)"
            )
            if g.get("est_listing"):
                gmp_info += f", Est. listing ₹{g['est_listing']}"

        prompt = f"""You are an expert Indian equity analyst reviewing an IPO for retail investors.

IPO Details:
- Company: {ipo['company_name']}
- Industry: {ipo.get('industry') or 'Not specified'}
- Price Band: {ipo.get('price_band', 'N/A')}
- Issue Size: {f"₹{ipo['issue_size_cr']} Cr" if ipo.get('issue_size_cr') else 'Not disclosed'}
- Exchange: {ipo.get('exchange', 'NSE/BSE')}
- Issue Type: {ipo.get('issue_type', 'Book Built')}
- Open: {ipo.get('open_date', 'N/A')} | Close: {ipo.get('close_date', 'N/A')}
- Listing: {ipo.get('listing_date', 'N/A')}
{gmp_info}

Provide a retail investor verdict. Respond ONLY in this exact JSON format (no markdown):
{{
  "verdict": "CAUTIOUS",
  "confidence": "MEDIUM",
  "summary": "One-sentence verdict.",
  "reasons": ["Reason 1", "Reason 2", "Reason 3"],
  "risks": ["Risk 1", "Risk 2"],
  "listing_outlook": "NEUTRAL"
}}

Rules:
- verdict: APPLY, CAUTIOUS, or AVOID only
- confidence: HIGH, MEDIUM, or LOW only
- listing_outlook: POSITIVE, NEUTRAL, or NEGATIVE only
- reasons: 3 specific points supporting your verdict
- risks: 2 key risks investors should know
- If GMP > 15%: lean APPLY. If GMP < 0%: lean AVOID.
- Be specific. Mention GMP data if available."""

        resp = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.2, max_output_tokens=400),
        )
        text = resp.text.strip()

        json_match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
        if json_match:
            data = json.loads(json_match.group())
            if data.get("verdict") not in ("APPLY", "CAUTIOUS", "AVOID"):
                data["verdict"] = "CAUTIOUS"
            if data.get("confidence") not in ("HIGH", "MEDIUM", "LOW"):
                data["confidence"] = "MEDIUM"
            if data.get("listing_outlook") not in ("POSITIVE", "NEUTRAL", "NEGATIVE"):
                data["listing_outlook"] = "NEUTRAL"
            verdict_cache[cache_key] = {"verdict": data, "_ts": time.time()}
            _save_verdict_cache(verdict_cache)
            return data

    except Exception as e:
        logger.warning(f"AI verdict failed for {ipo.get('company_name')}: {e}")

    # Use GMP to give a basic verdict even without Gemini
    return _gmp_based_verdict(ipo)


def _gmp_based_verdict(ipo: Dict) -> Dict:
    """Simple rule-based verdict using GMP when Gemini is unavailable."""
    gmp = ipo.get("gmp")
    gmp_price = gmp.get("gmp_price", 0) if gmp else 0
    gmp_pct = gmp.get("premium_pct", 0) if gmp else 0

    if gmp_pct is not None and gmp_pct >= 15:
        return {
            "verdict": "APPLY",
            "confidence": "MEDIUM",
            "summary": f"Strong grey market demand with GMP of ₹{gmp_price} (+{gmp_pct}%). Apply for listing gains.",
            "reasons": [
                f"GMP of ₹{gmp_price} suggests {gmp_pct}% listing gain potential",
                "Positive grey market sentiment indicates strong investor demand",
                "Consider applying for short-term listing gains",
            ],
            "risks": [
                "GMP is unofficial and can change rapidly before listing",
                "Market conditions on listing day may differ from grey market expectations",
            ],
            "listing_outlook": "POSITIVE",
        }
    elif gmp_pct is not None and gmp_pct < 0:
        return {
            "verdict": "AVOID",
            "confidence": "MEDIUM",
            "summary": f"Negative GMP of ₹{gmp_price} suggests weak demand. Listing gain unlikely.",
            "reasons": [
                f"Negative GMP of ₹{gmp_price} indicates potential listing below issue price",
                "Weak grey market sentiment suggests poor demand",
                "Risk of capital loss on listing day",
            ],
            "risks": [
                "May list below issue price, resulting in immediate loss",
                "GMP data is speculative but typically directionally correct",
            ],
            "listing_outlook": "NEGATIVE",
        }
    else:
        return {
            "verdict": "CAUTIOUS",
            "confidence": "LOW",
            "summary": "Insufficient data for confident verdict. Review the RHP carefully before applying.",
            "reasons": [
                "Limited public data available at this stage",
                "Please refer to the Red Herring Prospectus (RHP) for financials",
                "Consult a SEBI-registered advisor before applying",
            ],
            "risks": [
                "Market conditions may affect listing performance",
                "Grey market premium data may not be available or reliable",
            ],
            "listing_outlook": "NEUTRAL",
        }


def _fallback_verdict() -> Dict:
    return {
        "verdict": "CAUTIOUS",
        "confidence": "LOW",
        "summary": "Refer to the Red Herring Prospectus (RHP) for full details before applying.",
        "reasons": [
            "Limited financial data available at this stage",
            "Read the Red Herring Prospectus (RHP) before investing",
            "Consult a SEBI-registered investment advisor",
        ],
        "risks": [
            "Market conditions may affect listing performance",
            "Past IPO performance does not guarantee future gains",
        ],
        "listing_outlook": "NEUTRAL",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ASSEMBLE IPO HUB
# ═══════════════════════════════════════════════════════════════════════════════

def _build_ipo_hub() -> Dict[str, Any]:
    t0 = time.time()
    logger.info("IPO Hub: fetching from ipopremium.in…")

    # Fetch primary data
    ipos = _fetch_ipopremium()

    if not ipos:
        logger.error("ipopremium.in returned 0 IPOs — check scraper")
        ipos = []

    # Generate AI verdicts in parallel (max 3 workers to avoid rate limits)
    def _enrich(ipo: Dict) -> Dict:
        enriched = dict(ipo)
        enriched["ai_verdict"] = _generate_ai_verdict(enriched)
        return enriched

    if ipos:
        enriched_ipos = []
        with ThreadPoolExecutor(max_workers=3, thread_name_prefix="verdict") as pool:
            futures = {pool.submit(_enrich, ipo): ipo for ipo in ipos}
            for fut in as_completed(futures, timeout=90):
                try:
                    enriched_ipos.append(fut.result())
                except Exception as e:
                    logger.debug(f"Enrich failed: {e}")
                    enriched_ipos.append(futures[fut])
    else:
        enriched_ipos = []

    # Sort: OPEN → UPCOMING → ALLOTMENT → LISTED
    _order = {"OPEN": 0, "UPCOMING": 1, "ALLOTMENT": 2, "LISTED": 3, "UNKNOWN": 4}
    enriched_ipos.sort(key=lambda x: (
        _order.get(x.get("status", "UNKNOWN"), 4),
        x.get("open_date") or "9999"
    ))

    elapsed = round(time.time() - t0, 2)
    statuses = [i.get("status", "UNKNOWN") for i in enriched_ipos]
    stats = {
        "total": len(enriched_ipos),
        "open": statuses.count("OPEN"),
        "upcoming": statuses.count("UPCOMING"),
        "allotment": statuses.count("ALLOTMENT"),
        "listed": statuses.count("LISTED"),
    }
    gmp_count = sum(1 for i in enriched_ipos if i.get("gmp"))

    logger.info(f"IPO Hub: {len(enriched_ipos)} IPOs assembled in {elapsed}s | stats={stats}")

    return {
        "ipos": enriched_ipos,
        "stats": stats,
        "gmp_count": gmp_count,
        "fetched_at": time.time(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def get_ipo_hub(force_refresh: bool = False) -> Dict[str, Any]:
    """Returns full IPO hub data. 30-minute in-memory cache."""
    global _fetching
    cache_key = "ipo_hub"

    if not force_refresh and cache_key in _cache:
        age = time.time() - _cache[cache_key].get("fetched_at", 0)
        if age < _CACHE_TTL:
            out = copy.deepcopy(_cache[cache_key])
            out["cache_age_s"] = round(age)
            out["next_refresh_in"] = max(0, int(_CACHE_TTL - age))
            out["stale"] = False
            return out

    if _fetching and cache_key in _cache:
        out = copy.deepcopy(_cache[cache_key])
        out["stale"] = True
        out["cache_age_s"] = round(time.time() - _cache[cache_key].get("fetched_at", 0))
        out["next_refresh_in"] = 0
        return out

    try:
        _fetching = True
        fresh = _build_ipo_hub()
        _cache[cache_key] = fresh
        out = copy.deepcopy(fresh)
        out["cache_age_s"] = 0
        out["next_refresh_in"] = _CACHE_TTL
        out["stale"] = False
        return out
    finally:
        _fetching = False
