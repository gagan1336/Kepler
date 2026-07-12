"""
ANTIGRAVITY — AI Processor (Enhanced)
Uses Gemini 2.0 Flash for fastest, highest-quality digest generation.
- Upgraded prompt with deeper analysis, GST/policy context, trading impact
- Richer JSON schema with action_signals, key_levels, catalyst_type
- Market updates summarizer for GST/RBI/SEBI notifications
- Fallback to Gemini 1.5 Pro if Flash unavailable
"""
import json
import re
from datetime import date, datetime
from typing import List, Dict, Any, Optional

import google.generativeai as genai
from loguru import logger
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_fixed

from config import settings
from models import DailyDigest
from ticker_validator import validate_tickers

# ── Master System Prompt ──────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are a senior equity research analyst and financial journalist for a premium Indian stock market intelligence platform. You serve a mix of swing traders, long-term investors, and working professionals who want only high-signal, actionable information.

Your job: Transform a raw list of news articles into a structured, insightful daily market digest.

═══════════════════════════════════════════════════════
STEP 1 — CLASSIFICATION
═══════════════════════════════════════════════════════
Classify each article as exactly ONE of:
  • MACRO     — RBI policy, interest rates, inflation (CPI/WPI), IIP, GDP, fiscal deficit, global central banks affecting India
  • SECTOR    — Industry-wide developments: IT exports, auto sales, pharma pricing, banking credit growth
  • STOCK     — Company-specific: earnings, management change, deal win/loss, capacity expansion, regulatory action
  • RESULT    — Quarterly earnings reports: revenue, EBITDA, PAT, margins, guidance
  • GLOBAL    — US Fed, crude oil, China PMI, US jobs data, DXY — anything with direct India market impact
  • POLICY    — Government policy: budget announcements, PLI schemes, import duties, DPIIT, ministry decisions
  • GST       — GST council decisions, GST rate changes, e-invoicing, GSTN portal updates, compliance deadlines
  • RBI_SEBI  — RBI circulars, SEBI regulations, IRDAI guidelines, PFRDA rules, exchange notifications

═══════════════════════════════════════════════════════
STEP 2 — IMPORTANCE SCORING (1-10)
═══════════════════════════════════════════════════════
Score purely on market-moving potential:
  10 = Major policy change, surprise earnings, RBI rate decision, budget — index-moving
   9 = Significant macro data, big deal, large FII flow, SEBI enforcement action
   8 = Sector-wide trend, strong quarterly result, key policy initiative
   7 = Moderate company news, predictable macro, useful sector data
   6 = Minor corporate update, soft macro reading — borderline useful
   1-5 = Noise — irrelevant to markets, entertainment, unverified, old news

FILTER RULE: Keep ONLY articles scoring 7 or above.
MINIMUM: Return at least 5 items. If fewer than 5 score ≥7, lower threshold to 6.

═══════════════════════════════════════════════════════
STEP 3 — DEEP SUMMARY (3-4 sentences)
═══════════════════════════════════════════════════════
Write each summary to answer: What happened? Why does it matter for investors? What sectors/stocks are impacted?
Rules:
  • Plain English — zero unexplained jargon. If you must use a term (e.g., "EBITDA"), define it in the same sentence.
  • Numbers matter: include %, ₹ crore, basis points where available from the article.
  • Mention the specific catalyst and its likely market direction.
  • Do NOT editorialize or give buy/sell advice.
  • Example: "HDFC Bank reported Q3 net profit of ₹17,200 crore, up 18% year-on-year, beating estimates by 6%. Net interest margins held steady at 3.4% despite deposit cost pressure. The result signals continued strength in the private banking sector."

═══════════════════════════════════════════════════════
STEP 4 — EXTRACT METADATA
═══════════════════════════════════════════════════════
  • affected_sectors: List specific sector names (e.g., "Private Banking", "IT Services", "Pharma - CRAMS")
  • affected_stocks: List NSE ticker symbols ONLY if explicitly mentioned in the article
  • catalyst_type: "EARNINGS" | "POLICY" | "MACRO_DATA" | "DEAL" | "REGULATORY" | "MANAGEMENT" | "GLOBAL" | "GST" | "OTHER"
  • time_sensitivity: "TODAY" (act within session) | "SHORT_TERM" (1-5 days) | "MEDIUM_TERM" (weeks) | "LONG_TERM" (months)

═══════════════════════════════════════════════════════
STEP 5 — SENTIMENT
═══════════════════════════════════════════════════════
  BULLISH = net positive for Indian equity markets
  BEARISH = net negative
  NEUTRAL = mixed or no clear directional impact

═══════════════════════════════════════════════════════
OUTPUT FORMAT — STRICT JSON ARRAY
═══════════════════════════════════════════════════════
Return ONLY a valid JSON array. No preamble, no markdown, no explanation.

[{
  "title": "original or cleaned title",
  "category": "MACRO",
  "importance_score": 8,
  "summary": "3-4 sentence plain English summary with numbers",
  "affected_sectors": ["Private Banking", "NBFC"],
  "affected_stocks": ["HDFCBANK", "ICICIBANK"],
  "sentiment": "BULLISH",
  "catalyst_type": "EARNINGS",
  "time_sensitivity": "TODAY",
  "source_url": "https://..."
}]
"""

# ── Market Updates Summarizer Prompt ─────────────────────────────────────────
MARKET_UPDATES_PROMPT = """
You are an expert in Indian financial regulations and policy.
Analyze the following official notifications/news from SEBI, RBI, GST Council, Income Tax Department, and PIB.

Create a concise, actionable summary of the most important updates for Indian investors and traders.

For each significant update, provide:
1. What changed
2. Who is affected (which sectors, companies, or investor categories)
3. When it takes effect
4. What action (if any) investors or traders should be aware of

Focus on: GST rate changes, RBI policy circulars, SEBI regulations, corporate tax changes, FII/FDI rules.
Write in plain English. 3-4 sentences per update.

Return JSON array:
[{
  "title": "concise title",
  "update_type": "GST" | "RBI" | "SEBI" | "TAX" | "POLICY" | "OTHER",
  "summary": "3-4 sentences",
  "effective_date": "date if mentioned, else null",
  "affected_entities": ["sectors or companies"],
  "importance": "HIGH" | "MEDIUM" | "LOW",
  "source": "source name",
  "source_url": "url"
}]
"""

# ── JSON Output Schema ────────────────────────────────────────────────────────
DIGEST_ITEM_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "title":            {"type": "string"},
            "category":         {"type": "string", "enum": ["MACRO", "SECTOR", "STOCK", "RESULT", "GLOBAL", "POLICY", "GST", "RBI_SEBI"]},
            "importance_score": {"type": "integer"},
            "summary":          {"type": "string"},
            "affected_sectors": {"type": "array", "items": {"type": "string"}},
            "affected_stocks":  {"type": "array", "items": {"type": "string"}},
            "sentiment":        {"type": "string", "enum": ["BULLISH", "BEARISH", "NEUTRAL"]},
            "catalyst_type":    {"type": "string", "enum": ["EARNINGS", "POLICY", "MACRO_DATA", "DEAL", "REGULATORY", "MANAGEMENT", "GLOBAL", "GST", "OTHER"]},
            "time_sensitivity": {"type": "string", "enum": ["TODAY", "SHORT_TERM", "MEDIUM_TERM", "LONG_TERM"]},
            "source_url":       {"type": "string"},
        },
        "required": ["title", "category", "importance_score", "summary", "sentiment"],
    },
}

MARKET_UPDATES_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "title":             {"type": "string"},
            "update_type":       {"type": "string", "enum": ["GST", "RBI", "SEBI", "TAX", "POLICY", "OTHER"]},
            "summary":           {"type": "string"},
            "effective_date":    {"type": "string"},
            "affected_entities": {"type": "array", "items": {"type": "string"}},
            "importance":        {"type": "string", "enum": ["HIGH", "MEDIUM", "LOW"]},
            "source":            {"type": "string"},
            "source_url":        {"type": "string"},
        },
        "required": ["title", "update_type", "summary", "importance"],
    },
}


def _configure_gemini():
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY is not set")
    genai.configure(api_key=settings.gemini_api_key)


def _format_articles_for_prompt(articles: List[Dict[str, Any]]) -> str:
    """Format raw articles as a numbered list for the Gemini prompt."""
    lines = []
    for i, a in enumerate(articles, 1):
        priority_tag = ""
        source = a.get("source", "")
        # Flag high-priority official sources
        if source in ("SEBI", "RBI", "GST Portal", "PIB Finance", "Income Tax India"):
            priority_tag = " [OFFICIAL SOURCE - HIGH PRIORITY]"
        lines.append(
            f"{i}. TITLE: {a.get('title', '')}\n"
            f"   SOURCE: {source}{priority_tag}\n"
            f"   DESCRIPTION: {a.get('description', '')[:400]}\n"
            f"   URL: {a.get('url', '')}\n"
        )
    return "\n".join(lines)


def _extract_json(text: str) -> Optional[List[Dict]]:
    """Extract JSON array from Gemini response, handling markdown code blocks."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown code fences
    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find first [ to last ]
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None


def _calculate_market_mood(items: List[Dict]) -> str:
    """Calculate overall market mood from sentiment distribution (importance-weighted)."""
    total_weight = 0
    bullish_weight = 0
    bearish_weight = 0

    for item in items:
        weight = item.get("importance_score", 5)
        sentiment = item.get("sentiment", "NEUTRAL")
        total_weight += weight
        if sentiment == "BULLISH":
            bullish_weight += weight
        elif sentiment == "BEARISH":
            bearish_weight += weight

    if total_weight == 0:
        return "NEUTRAL"

    bullish_ratio = bullish_weight / total_weight
    bearish_ratio = bearish_weight / total_weight

    if bullish_ratio >= 0.55:
        return "BULLISH"
    if bearish_ratio >= 0.45:
        return "BEARISH"
    return "NEUTRAL"


# ── Gemini API Calls ──────────────────────────────────────────────────────────
@retry(stop=stop_after_attempt(2), wait=wait_fixed(10))
def _call_gemini_flash(articles_text: str) -> str:
    """Call Gemini 2.0 Flash — fastest, most cost-effective, high quality."""
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=SYSTEM_PROMPT,
    )
    response = model.generate_content(
        articles_text,
        generation_config=genai.types.GenerationConfig(
            temperature=0.15,  # Very low for consistent, factual output
            max_output_tokens=8192,
            response_mime_type="application/json",
            response_schema=DIGEST_ITEM_SCHEMA,
        ),
    )
    return response.text


@retry(stop=stop_after_attempt(2), wait=wait_fixed(15))
def _call_gemini_pro_fallback(articles_text: str) -> str:
    """Fallback to Gemini 1.5 Pro if Flash is unavailable."""
    model = genai.GenerativeModel(
        model_name="gemini-1.5-pro",
        system_instruction=SYSTEM_PROMPT,
    )
    response = model.generate_content(
        articles_text,
        generation_config=genai.types.GenerationConfig(
            temperature=0.2,
            max_output_tokens=8192,
            response_mime_type="application/json",
            response_schema=DIGEST_ITEM_SCHEMA,
        ),
    )
    return response.text


@retry(stop=stop_after_attempt(2), wait=wait_fixed(10))
def _call_gemini_for_updates(updates_text: str) -> str:
    """Process official notifications (GST/RBI/SEBI) with specialized prompt."""
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=MARKET_UPDATES_PROMPT,
    )
    response = model.generate_content(
        updates_text,
        generation_config=genai.types.GenerationConfig(
            temperature=0.1,
            max_output_tokens=4096,
            response_mime_type="application/json",
            response_schema=MARKET_UPDATES_SCHEMA,
        ),
    )
    return response.text


def _call_gemini(articles_text: str) -> str:
    """Try Flash first, fall back to Pro."""
    try:
        return _call_gemini_flash(articles_text)
    except Exception as e:
        logger.warning(f"Gemini Flash failed ({e}), falling back to Gemini 1.5 Pro")
        return _call_gemini_pro_fallback(articles_text)


def process_news(
    articles: List[Dict[str, Any]],
    db: Session,
    target_date: Optional[date] = None,
) -> Optional[DailyDigest]:
    """
    Main entry point. Process raw articles, save digest to DB.
    Skips processing if digest already exists for today (cache).
    Separates official regulatory updates from general market news.
    """
    target_date = target_date or date.today()

    # Check cache — never reprocess
    existing = db.query(DailyDigest).filter(DailyDigest.date == target_date).first()
    if existing:
        logger.info(f"Digest for {target_date} already exists — skipping Gemini call")
        return existing

    if not articles:
        logger.warning("No articles to process")
        return None

    # Separate official regulatory articles from general news
    official_sources = {"SEBI", "RBI", "GST Portal", "PIB Finance", "Income Tax India"}
    official_articles = [a for a in articles if a.get("source", "") in official_sources]
    general_articles = [a for a in articles if a.get("source", "") not in official_sources]

    logger.info(f"Processing {len(general_articles)} general + {len(official_articles)} official articles")

    try:
        _configure_gemini()

        # Process general market news
        general_text = _format_articles_for_prompt(general_articles[:80])  # up to 80 articles
        raw_response = _call_gemini(general_text)
        logger.debug(f"Gemini response length: {len(raw_response)} chars")

        items = _extract_json(raw_response)
        if not items:
            logger.error("Could not parse Gemini JSON response — saving empty digest")
            items = []

        # Process official regulatory updates separately and merge
        if official_articles:
            try:
                official_text = _format_articles_for_prompt(official_articles)
                # Add official articles to general batch with HIGH PRIORITY tag
                # They'll be picked up by the main AI with higher importance scoring
                official_as_items = []
                for art in official_articles[:10]:
                    official_as_items.append({
                        "title": art.get("title", ""),
                        "category": _guess_official_category(art.get("source", "")),
                        "importance_score": 9,  # Official sources default high
                        "summary": art.get("description", "")[:400] or art.get("title", ""),
                        "affected_sectors": [],
                        "affected_stocks": [],
                        "sentiment": "NEUTRAL",
                        "catalyst_type": "REGULATORY",
                        "time_sensitivity": "SHORT_TERM",
                        "source_url": art.get("url", ""),
                    })
                # Run official articles through AI for proper summarization
                if official_text.strip():
                    official_resp = _call_gemini(official_text)
                    official_items = _extract_json(official_resp)
                    if official_items:
                        items = official_items + items  # Official items first
            except Exception as e:
                logger.warning(f"Official article processing failed: {e}")

        # Validate and clean each item
        validated_items = []
        seen_titles = set()
        for item in items:
            if isinstance(item, dict) and item.get("title") and item.get("summary"):
                title = item.get("title", "")
                # Skip duplicates in AI output
                if title in seen_titles:
                    continue
                seen_titles.add(title)

                # Validate and clean AI-extracted stock tickers
                raw_stocks = item.get("affected_stocks", [])
                item["affected_stocks"] = validate_tickers(raw_stocks)

                # Ensure all new fields have defaults
                item.setdefault("catalyst_type", "OTHER")
                item.setdefault("time_sensitivity", "SHORT_TERM")

                validated_items.append(item)

        # Sort by importance score desc
        validated_items.sort(key=lambda x: x.get("importance_score", 0), reverse=True)

        market_mood = _calculate_market_mood(validated_items)
        logger.info(f"Digest: {len(validated_items)} items, mood: {market_mood}")

    except Exception as e:
        logger.error(f"Gemini processing failed: {e}")
        validated_items = []
        market_mood = "NEUTRAL"

    # Save to DB
    digest = DailyDigest(
        date=target_date,
        items=validated_items,
        market_mood=market_mood,
        status="published",
    )
    db.add(digest)
    db.commit()
    db.refresh(digest)

    logger.info(f"✅ Digest saved for {target_date}: {len(validated_items)} items, mood={market_mood}")
    return digest


def _guess_official_category(source: str) -> str:
    """Map official source to appropriate category."""
    mapping = {
        "SEBI": "RBI_SEBI",
        "RBI": "RBI_SEBI",
        "GST Portal": "GST",
        "PIB Finance": "POLICY",
        "Income Tax India": "POLICY",
    }
    return mapping.get(source, "POLICY")


def process_market_updates_only(
    official_articles: List[Dict[str, Any]],
    db: Session,
) -> List[Dict[str, Any]]:
    """
    Process ONLY official regulatory articles (GST/RBI/SEBI) with specialized prompt.
    Returns structured market update items for the /news/market-updates endpoint.
    """
    if not official_articles:
        return []

    try:
        _configure_gemini()
        text = _format_articles_for_prompt(official_articles[:30])
        raw_response = _call_gemini_for_updates(text)
        updates = _extract_json(raw_response)
        if updates:
            return updates
    except Exception as e:
        logger.error(f"Market updates processing failed: {e}")

    return []


if __name__ == "__main__":
    from database import SessionLocal
    from news_collector import collect_all_news

    db = SessionLocal()
    try:
        articles = collect_all_news(
            newsapi_key=settings.newsapi_key,
            gnews_api_key=settings.gnews_api_key,
        )
        print(f"Testing with {len(articles)} articles...")
        digest = process_news(articles, db)
        if digest:
            print(f"✅ Digest created: {len(digest.items)} items, mood={digest.market_mood}")
            for item in digest.items[:5]:
                cat = item.get("category", "?")
                score = item.get("importance_score", "?")
                title = item.get("title", "")[:70]
                print(f"  [{cat}] [{score}] {title}")
    finally:
        db.close()
