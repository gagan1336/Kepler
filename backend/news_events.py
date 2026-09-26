"""
KEPLER — NLP Event Layer (Phase E)
=====================================
Fetches NSE/BSE corporate announcements and financial news headlines
per ticker, classifies them via Gemini, and returns structured event
features for use in the training pipeline and live inference.

Key design constraints
----------------------
  Point-in-time safe: every announcement is stored with its published_at
  timestamp. At training time, ONLY events with published_at < bar_date
  are used — never forward-looking information.

  Graceful degradation: if the event cache is missing or the LLM call
  fails, all event features default to 0. The model trains and runs
  normally without news data — news adds signal on top.

Event taxonomy
--------------
  regulatory_approval   +1   USFDA/CDSCO drug approval, order win
  regulatory_rejection  -1   USFDA CRL, import alert, ban
  earnings_beat         +1   Quarterly results above estimates
  earnings_miss         -1   Results below estimates
  management_change      0   CEO/CFO change (direction unknown)
  buyback               +1   Share buyback announcement
  merger_acquisition     0   Acquisition / merger announced
  dividend              +1   Dividend declared
  legal_issue           -1   Fraud, SEBI action, court order against
  other                  0   Anything else

Output features per (symbol, date)
-----------------------------------
  event_polarity_7d    weighted sum of event polarity in last 7 days
  event_polarity_30d   weighted sum of event polarity in last 30 days
  n_events_7d          count of events in last 7 days
  has_regulatory       1 if any regulatory event in last 30 days
  earnings_proximity   days until next quarterly result (30 if unknown)

Usage
-----
  from news_events import get_event_features, warm_cache

  # Warm the cache for a set of tickers (do once before training)
  warm_cache(symbols, lookback_days=400)

  # Get features for one ticker at one date (training + inference)
  feats = get_event_features("SUNPHARMA", as_of_date="2024-06-15")
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from loguru import logger

# ── Paths ─────────────────────────────────────────────────────────────────────
_BACKEND_DIR = Path(__file__).parent
_CACHE_DIR   = _BACKEND_DIR / ".cache" / "news_events"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Event taxonomy ─────────────────────────────────────────────────────────────
EVENT_TAXONOMY = {
    "regulatory_approval":   +1,
    "regulatory_rejection":  -1,
    "earnings_beat":         +1,
    "earnings_miss":         -1,
    "management_change":      0,
    "buyback":               +1,
    "merger_acquisition":     0,
    "dividend":              +1,
    "legal_issue":           -1,
    "other":                  0,
}

# Feature column names (must match FEATURE_COLUMNS addition in ml_features.py)
EVENT_FEATURE_COLS = [
    "event_polarity_7d",
    "event_polarity_30d",
    "n_events_7d",
    "has_regulatory",
    "earnings_proximity",
]

_ZERO_FEATURES = {col: 0.0 for col in EVENT_FEATURE_COLS}


# ── NSE announcement fetcher ──────────────────────────────────────────────────
def _fetch_nse_announcements(symbol: str, from_date: str, to_date: str) -> List[Dict]:
    """
    Pull corporate announcements from NSE public API.
    Returns list of {headline, published_at, category} dicts.
    """
    url = (
        "https://www.nseindia.com/api/corp-info"
        f"?symbol={symbol}&corpType=announcements"
        f"&market=equities&from={from_date}&to={to_date}"
    )
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept":     "application/json",
        "Referer":    "https://www.nseindia.com/",
    }
    try:
        # NSE requires a session cookie — fetch homepage first
        sess = requests.Session()
        sess.get("https://www.nseindia.com", headers=headers, timeout=10)
        time.sleep(0.5)
        resp = sess.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        announcements = data.get("data", [])
        events = []
        for ann in announcements:
            headline = ann.get("subject", "") or ann.get("desc", "")
            date_str = ann.get("bflag", "") or ann.get("date", "")
            if headline and date_str:
                try:
                    pub_at = pd.to_datetime(date_str, dayfirst=True)
                    events.append({
                        "symbol":       symbol,
                        "headline":     headline[:500],
                        "published_at": pub_at.isoformat(),
                        "source":       "NSE",
                    })
                except Exception:
                    pass
        return events
    except Exception as e:
        logger.debug(f"NSE fetch failed for {symbol}: {e}")
        return []


# ── LLM classifier ────────────────────────────────────────────────────────────
def _classify_events_batch(events: List[Dict]) -> List[Dict]:
    """
    Classify a batch of events using Google Gemini.
    Returns the same list with 'event_type' and 'confidence' added.

    Falls back to keyword classification if Gemini is unavailable.
    """
    if not events:
        return events

    # Try Gemini first
    try:
        import google.generativeai as genai
        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if api_key:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel("gemini-2.0-flash-exp")

            headlines = "\n".join(
                f"{i+1}. {e['headline']}" for i, e in enumerate(events)
            )
            taxonomy_str = ", ".join(EVENT_TAXONOMY.keys())
            prompt = f"""Classify each NSE corporate announcement headline below into exactly one event type.

Event types: {taxonomy_str}

Headlines:
{headlines}

Return ONLY a JSON array of objects, one per headline, in order:
[{{"index": 1, "event_type": "...", "confidence": 0.0-1.0}}, ...]

Rules:
- Use "other" when the headline doesn't clearly match a specific type.
- Confidence = how certain you are (0.5 = unsure, 1.0 = certain).
- Do not add explanation, just the JSON array."""

            resp = model.generate_content(prompt)
            raw  = resp.text.strip()
            # Extract JSON array from response
            match = re.search(r'\[.*\]', raw, re.DOTALL)
            if match:
                classifications = json.loads(match.group())
                for item in classifications:
                    idx = item.get("index", 0) - 1
                    if 0 <= idx < len(events):
                        et = item.get("event_type", "other")
                        if et not in EVENT_TAXONOMY:
                            et = "other"
                        events[idx]["event_type"]  = et
                        events[idx]["confidence"]   = float(item.get("confidence", 0.7))
                        events[idx]["polarity"]     = EVENT_TAXONOMY[et]
                return events
    except Exception as e:
        logger.debug(f"Gemini classification failed: {e} — falling back to keywords")

    # Keyword fallback (no LLM)
    for event in events:
        event["event_type"], event["polarity"], event["confidence"] = (
            _keyword_classify(event["headline"])
        )
    return events


def _keyword_classify(headline: str) -> Tuple[str, int, float]:
    """Simple keyword-based classifier used when Gemini is unavailable."""
    h = headline.lower()
    rules = [
        (["approval", "approved", "usfda ok", "cdsco", "order win", "wins order"],
         "regulatory_approval", +1),
        (["reject", "crl", "import alert", "warning letter", "ban", "sebi penalt"],
         "regulatory_rejection", -1),
        (["quarterly result", "q1 result", "q2 result", "q3 result", "q4 result",
          "profit up", "revenue up", "beat estimate"],
         "earnings_beat", +1),
        (["profit down", "loss", "miss estimate", "below estimate", "revenue decline"],
         "earnings_miss", -1),
        (["buyback", "buy-back", "share repurchase"],
         "buyback", +1),
        (["dividend", "final dividend", "interim dividend"],
         "dividend", +1),
        (["ceo", "cfo", "md resign", "managing director", "appoints"],
         "management_change", 0),
        (["acqui", "merger", "amalgamat", "takeover"],
         "merger_acquisition", 0),
        (["fraud", "scam", "arrest", "fir ", "court order against", "sebi action"],
         "legal_issue", -1),
    ]
    for keywords, event_type, polarity in rules:
        if any(kw in h for kw in keywords):
            return event_type, polarity, 0.6
    return "other", 0, 0.4


# ── Cache management ──────────────────────────────────────────────────────────
def _cache_path(symbol: str) -> Path:
    return _CACHE_DIR / f"{symbol.upper().replace('&', '_')}.json"


def _load_cache(symbol: str) -> List[Dict]:
    p = _cache_path(symbol)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            return []
    return []


def _save_cache(symbol: str, events: List[Dict]) -> None:
    _cache_path(symbol).write_text(json.dumps(events, indent=2))


def warm_cache(
    symbols: List[str],
    lookback_days: int = 400,
    force_refresh: bool = False,
) -> None:
    """
    Pre-fetch and classify announcements for a list of symbols.
    Results are cached to .cache/news_events/<SYMBOL>.json.
    Safe to call multiple times — skips symbols with fresh caches.
    """
    to_date   = datetime.utcnow().strftime("%d-%m-%Y")
    from_date = (datetime.utcnow() - timedelta(days=lookback_days)).strftime("%d-%m-%Y")

    for i, sym in enumerate(symbols):
        cache = _load_cache(sym)
        if cache and not force_refresh:
            # Check if cache covers the period
            latest_cached = max(
                (e["published_at"] for e in cache if "published_at" in e),
                default="1970-01-01",
            )
            days_stale = (datetime.utcnow() - pd.Timestamp(latest_cached)).days
            if days_stale < 3:
                logger.debug(f"  {sym}: cache fresh ({days_stale}d old), skipping")
                continue

        logger.info(f"  [{i+1}/{len(symbols)}] Fetching announcements for {sym}…")
        raw_events = _fetch_nse_announcements(sym, from_date, to_date)

        if raw_events:
            classified = _classify_events_batch(raw_events)
            _save_cache(sym, classified)
            logger.info(f"    {sym}: {len(classified)} events classified + cached")
        else:
            logger.debug(f"    {sym}: no announcements found")
        time.sleep(0.3)  # polite rate limiting


# ── Feature extraction ─────────────────────────────────────────────────────────
def get_event_features(
    symbol: str,
    as_of_date: str,
) -> Dict[str, float]:
    """
    Return event features for a symbol as of a given date.
    Only uses events with published_at < as_of_date (point-in-time safe).

    Parameters
    ----------
    symbol      : NSE ticker symbol
    as_of_date  : 'YYYY-MM-DD' — the bar date in the training dataset

    Returns
    -------
    Dict with keys matching EVENT_FEATURE_COLS, all floats.
    Returns zero-filled dict if no cache exists.
    """
    events = _load_cache(symbol)
    if not events:
        return dict(_ZERO_FEATURES)

    cutoff = pd.Timestamp(as_of_date)
    window_7d  = cutoff - timedelta(days=7)
    window_30d = cutoff - timedelta(days=30)

    polarity_7d  = 0.0
    polarity_30d = 0.0
    n_events_7d  = 0
    has_regulatory = 0.0

    for ev in events:
        pub_at = pd.Timestamp(ev.get("published_at", "1970-01-01"))
        if pub_at >= cutoff:
            continue   # future event — strict point-in-time enforcement

        polarity   = float(ev.get("polarity", 0))
        confidence = float(ev.get("confidence", 0.5))
        weighted   = polarity * confidence
        ev_type    = ev.get("event_type", "other")

        if pub_at >= window_30d:
            polarity_30d += weighted
            if ev_type in ("regulatory_approval", "regulatory_rejection"):
                has_regulatory = 1.0

        if pub_at >= window_7d:
            polarity_7d += weighted
            n_events_7d += 1

    # Days until next quarterly result — approximate from last earnings event
    earnings_events = [
        pd.Timestamp(e["published_at"])
        for e in events
        if e.get("event_type") in ("earnings_beat", "earnings_miss")
        and pd.Timestamp(e["published_at"]) < cutoff
    ]
    if earnings_events:
        last_earnings = max(earnings_events)
        # Indian corporates report quarterly — next result ~90 days after last
        days_since_last = (cutoff - last_earnings).days
        earnings_proximity = max(0, 90 - days_since_last)
    else:
        earnings_proximity = 30.0  # unknown — use midpoint

    return {
        "event_polarity_7d":  round(polarity_7d,  4),
        "event_polarity_30d": round(polarity_30d, 4),
        "n_events_7d":        float(n_events_7d),
        "has_regulatory":     has_regulatory,
        "earnings_proximity": float(earnings_proximity),
    }


def get_event_features_bulk(
    symbol: str,
    dates: pd.Series,
) -> pd.DataFrame:
    """
    Vectorised version of get_event_features for all dates of a symbol.
    Used during training dataset construction (much faster than calling
    get_event_features row-by-row).

    Returns a DataFrame with EVENT_FEATURE_COLS, indexed same as dates.
    """
    events = _load_cache(symbol)
    if not events:
        return pd.DataFrame(
            [_ZERO_FEATURES] * len(dates),
            index=dates.index,
        )

    # Build a sorted event DataFrame for fast window queries
    ev_df = pd.DataFrame(events)
    if ev_df.empty or "published_at" not in ev_df.columns:
        return pd.DataFrame([_ZERO_FEATURES] * len(dates), index=dates.index)

    ev_df["published_at"] = pd.to_datetime(ev_df["published_at"], utc=False)
    ev_df["polarity"]     = ev_df.get("polarity", pd.Series([0]*len(ev_df)))
    ev_df["confidence"]   = ev_df.get("confidence", pd.Series([0.5]*len(ev_df)))
    ev_df["weighted"]     = ev_df["polarity"] * ev_df["confidence"]
    ev_df = ev_df.sort_values("published_at").reset_index(drop=True)

    rows = []
    for bar_date in pd.to_datetime(dates):
        past = ev_df[ev_df["published_at"] < bar_date]
        w7d  = past[past["published_at"] >= bar_date - timedelta(days=7)]
        w30d = past[past["published_at"] >= bar_date - timedelta(days=30)]

        reg_types  = ("regulatory_approval", "regulatory_rejection")
        has_reg    = float(w30d["event_type"].isin(reg_types).any()) if len(w30d) else 0.0

        earnings_past = past[past["event_type"].isin(("earnings_beat", "earnings_miss"))]
        if len(earnings_past):
            last_earn = earnings_past["published_at"].max()
            prox = max(0, 90 - (bar_date - last_earn).days)
        else:
            prox = 30.0

        rows.append({
            "event_polarity_7d":  float(w7d["weighted"].sum()),
            "event_polarity_30d": float(w30d["weighted"].sum()),
            "n_events_7d":        float(len(w7d)),
            "has_regulatory":     has_reg,
            "earnings_proximity": float(prox),
        })

    return pd.DataFrame(rows, index=dates.index)


# ── CLI: warm cache for common universes ──────────────────────────────────────
if __name__ == "__main__":
    import argparse, sys

    parser = argparse.ArgumentParser(description="Kepler NLP Event Layer — cache warmer")
    parser.add_argument("--symbols", nargs="+", help="Specific symbols to warm")
    parser.add_argument("--universe", default="nifty200",
                        choices=["nifty50", "nifty200", "nifty500"])
    parser.add_argument("--lookback-days", type=int, default=400)
    parser.add_argument("--force-refresh", action="store_true")
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr, level="INFO",
               format="<green>{time:HH:mm:ss}</green> | {message}")

    if args.symbols:
        symbols = args.symbols
    else:
        from train_model import UNIVERSES
        symbols = UNIVERSES.get(args.universe, [])

    logger.info(f"🔥 Warming event cache for {len(symbols)} symbols "
                f"(lookback={args.lookback_days}d)…")
    warm_cache(symbols, lookback_days=args.lookback_days,
               force_refresh=args.force_refresh)
    logger.info("✅ Cache warm complete.")
