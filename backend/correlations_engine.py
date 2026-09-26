"""
Kepler Radar — AI Correlations Engine
Cross-reads today's digest items and generates causal chain intelligence:
- Thematic groupings (Crude Oil, FII Flow, RBI Policy, China Slowdown, etc.)
- Causal chains showing how one event ripples through sectors
- Bullish/Bearish sector impact map with magnitude ratings
- Stock-level predicted movers with reasoning and confidence
- Time horizons: TODAY / SHORT_TERM / MEDIUM_TERM

Runs AFTER digest is generated, uses processed items as input (not raw articles).
Writes result to DailyDigest.correlations JSON column.
"""
import json
import re
from datetime import datetime, date
from typing import List, Dict, Any, Optional

import google.generativeai as genai
from loguru import logger
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_fixed

from config import settings
from models import DailyDigest


# ── Correlation Analysis Prompt ────────────────────────────────────────────────
RADAR_SYSTEM_PROMPT = """
You are a senior macro strategist and quantitative analyst at a top Indian equity research firm.
Your specialty: identifying hidden linkages between seemingly unrelated news events and predicting their combined market impact.

⚠️ CRITICAL LANGUAGE RULE: ALL output MUST be in English ONLY.
- All themes, headlines, causal chains, sector names, stock names, and reasoning must be in English.
- If input contains Hindi or regional language content, translate and summarise it in English.
- This rule has ZERO exceptions — no Hindi, no regional scripts.


You will be given today's processed digest — a structured list of market news items with their categories, sentiments and affected sectors.

Your job: Perform CROSS-NEWS CORRELATION ANALYSIS to identify causal chains and second-order effects.

═══════════════════════════════════════════════════════
STEP 1 — THEME DETECTION
═══════════════════════════════════════════════════════
Group news items into macro themes. Common Indian market themes:
• Crude Oil & Energy: OPEC, Brent crude, ATF, OMC, petrochemicals
• RBI / Interest Rates: monetary policy, repo rate, liquidity, bank credit
• FII / Global Flows: US Fed, DXY, FII buy/sell, global risk-on/off
• China Macro: China PMI, China demand, commodity imports, competition
• INR / Forex: rupee depreciation/appreciation, USDINR, forex reserves
• Government Capex: PLI schemes, infrastructure spending, defense orders
• Earnings Season: quarterly results, guidance revisions, analyst targets
• Inflation / Input Costs: WPI, CPI, commodity prices, margin pressure
• Technology & IT: US tech spending, deal wins, NASSCOM, visa policy
• Banking & Credit: NPA, credit growth, GNPA, RBI norms, CASA

═══════════════════════════════════════════════════════
STEP 2 — CAUSAL CHAIN ANALYSIS
═══════════════════════════════════════════════════════
For each identified theme, trace the CAUSAL CHAIN:
Event → Intermediate Effect → First-order Impact → Second-order Impact

Example:
"Brent crude rises 3%" 
→ India's import bill increases
→ OMC margins squeezed (BEARISH: IOCL, BPCL, HINDPETRO)
→ Aviation fuel costs rise (BEARISH: INDIGO, SPICEJET)  
→ Tyre/paint raw material costs rise (BEARISH: MRF, ASIANPAINT)
→ BUT upstream E&P benefits (BULLISH: ONGC, OIL)
→ Currency pressure on INR adds to import inflation

═══════════════════════════════════════════════════════
STEP 3 — SECTOR IMPACT SCORING
═══════════════════════════════════════════════════════
For each sector affected, provide:
- Direction: BULLISH / BEARISH / NEUTRAL
- Magnitude: HIGH / MEDIUM / LOW (based on how directly impacted)
- Reasoning: 1-2 sentence explanation
- Representative NSE tickers: 2-4 specific stocks

═══════════════════════════════════════════════════════
STEP 4 — CONFIDENCE & HORIZON
═══════════════════════════════════════════════════════
- Confidence: HIGH (3+ corroborating news items), MEDIUM (2 items), LOW (single item / indirect)
- Time Horizon: TODAY (intraday), SHORT_TERM (1-5 days), MEDIUM_TERM (1-4 weeks)

═══════════════════════════════════════════════════════
OUTPUT — STRICT JSON
═══════════════════════════════════════════════════════
Return ONLY valid JSON. No markdown, no explanation.

{
  "generated_at": "ISO timestamp",
  "market_mood_reasoning": "2-sentence overall market explanation from cross-reading all news",
  "dominant_theme": "The single most important macro theme today",
  "total_correlations": N,
  "correlations": [
    {
      "id": "unique-slug",
      "theme": "Theme Name",
      "theme_icon": "single emoji",
      "headline": "One-line summary of the correlation discovered",
      "trigger_headlines": ["headline 1 from digest", "headline 2"],
      "causal_chain": "Event A → Effect B → Impact C on sector X → Second-order effect D",
      "impact_sectors": [
        {
          "name": "Sector Name",
          "ticker_examples": ["TICK1", "TICK2"],
          "direction": "BEARISH",
          "magnitude": "HIGH",
          "reason": "1 sentence why"
        }
      ],
      "beneficiary_sectors": [
        {
          "name": "Sector Name",
          "ticker_examples": ["TICK1"],
          "direction": "BULLISH",
          "magnitude": "MEDIUM",
          "reason": "1 sentence why"
        }
      ],
      "key_stocks_to_watch": [
        {
          "symbol": "NSETICKER",
          "company": "Company Name",
          "direction": "BULLISH",
          "reason": "1 sentence catalyst",
          "confidence": "HIGH"
        }
      ],
      "confidence": "HIGH",
      "time_horizon": "SHORT_TERM",
      "sentiment": "BEARISH",
      "supporting_news_count": 3
    }
  ]
}
"""

RADAR_SCHEMA = {
    "type": "object",
    "properties": {
        "generated_at":          {"type": "string"},
        "market_mood_reasoning": {"type": "string"},
        "dominant_theme":        {"type": "string"},
        "total_correlations":    {"type": "integer"},
        "correlations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id":               {"type": "string"},
                    "theme":            {"type": "string"},
                    "theme_icon":       {"type": "string"},
                    "headline":         {"type": "string"},
                    "trigger_headlines": {"type": "array", "items": {"type": "string"}},
                    "causal_chain":     {"type": "string"},
                    "impact_sectors": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name":           {"type": "string"},
                                "ticker_examples": {"type": "array", "items": {"type": "string"}},
                                "direction":      {"type": "string"},
                                "magnitude":      {"type": "string"},
                                "reason":         {"type": "string"},
                            },
                            "required": ["name", "direction", "magnitude", "reason"],
                        },
                    },
                    "beneficiary_sectors": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name":           {"type": "string"},
                                "ticker_examples": {"type": "array", "items": {"type": "string"}},
                                "direction":      {"type": "string"},
                                "magnitude":      {"type": "string"},
                                "reason":         {"type": "string"},
                            },
                            "required": ["name", "direction", "magnitude"],
                        },
                    },
                    "key_stocks_to_watch": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "symbol":     {"type": "string"},
                                "company":    {"type": "string"},
                                "direction":  {"type": "string"},
                                "reason":     {"type": "string"},
                                "confidence": {"type": "string"},
                            },
                            "required": ["symbol", "direction", "reason"],
                        },
                    },
                    "confidence":            {"type": "string"},
                    "time_horizon":          {"type": "string"},
                    "sentiment":             {"type": "string"},
                    "supporting_news_count": {"type": "integer"},
                },
                "required": ["id", "theme", "headline", "causal_chain", "confidence", "sentiment"],
            },
        },
    },
    "required": ["market_mood_reasoning", "correlations"],
}


def _configure_gemini():
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY not configured")
    genai.configure(api_key=settings.gemini_api_key)


def _format_digest_for_radar(items: List[Dict[str, Any]]) -> str:
    """Format digest items as structured text for the correlation prompt."""
    lines = ["TODAY'S MARKET DIGEST — For cross-correlation analysis:\n"]
    for i, item in enumerate(items, 1):
        lines.append(
            f"[{i}] CATEGORY: {item.get('category', 'UNKNOWN')} | "
            f"SENTIMENT: {item.get('sentiment', 'NEUTRAL')} | "
            f"SCORE: {item.get('importance_score', '?')}/10\n"
            f"    TITLE: {item.get('title', '')}\n"
            f"    SUMMARY: {item.get('summary', '')[:300]}\n"
            f"    SECTORS: {', '.join(item.get('affected_sectors', []))}\n"
            f"    STOCKS: {', '.join(item.get('affected_stocks', []))}\n"
        )
    return "\n".join(lines)


def _extract_json(text: str) -> Optional[Dict]:
    """Extract JSON object from Gemini response."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    text = re.sub(r"```(?:json)?", "", text).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    return None


@retry(stop=stop_after_attempt(2), wait=wait_fixed(5))
def _call_gemini_radar(digest_text: str) -> str:
    """Call Gemini 2.5 Flash for correlation analysis."""
    model = genai.GenerativeModel(
        model_name="gemini-2.5-flash",
        system_instruction=RADAR_SYSTEM_PROMPT,
    )
    response = model.generate_content(
        digest_text,
        generation_config=genai.types.GenerationConfig(
            temperature=0.25,       # Slightly higher — correlation analysis benefits from creativity
            max_output_tokens=8192,
            response_mime_type="application/json",
            response_schema=RADAR_SCHEMA,
        ),
    )
    return response.text


def generate_correlations(
    digest_items: List[Dict[str, Any]],
    db: Session,
    digest_id: str,
) -> Optional[Dict]:
    """
    Main entry point. Takes processed digest items, calls Gemini, stores correlations.
    Called as a background task after digest is generated.
    
    Args:
        digest_items: List of digest item dicts (already processed by ai_processor)
        db: SQLAlchemy session
        digest_id: ID of the DailyDigest row to update
        
    Returns:
        The correlations dict, or None on failure.
    """
    if not digest_items:
        logger.warning("Kepler Radar: No digest items to correlate")
        return None

    if len(digest_items) < 3:
        logger.warning(f"Kepler Radar: Only {len(digest_items)} items — skipping (need ≥3)")
        return None

    logger.info(f"🛰 Kepler Radar: Generating correlations for digest {digest_id} ({len(digest_items)} items)")

    try:
        _configure_gemini()
        digest_text = _format_digest_for_radar(digest_items)
        raw_response = _call_gemini_radar(digest_text)

        correlations = _extract_json(raw_response)
        if not correlations:
            logger.error("Kepler Radar: Failed to parse Gemini response")
            return None

        # Enrich with metadata
        correlations["generated_at"] = datetime.utcnow().isoformat()
        correlations["digest_id"] = digest_id
        correlations["total_correlations"] = len(correlations.get("correlations", []))

        # Persist to DailyDigest
        digest = db.query(DailyDigest).filter(DailyDigest.id == digest_id).first()
        if digest:
            digest.correlations = correlations
            digest.correlations_generated_at = datetime.utcnow()
            db.commit()
            logger.info(
                f"✅ Kepler Radar: {correlations['total_correlations']} correlations saved "
                f"for digest {digest_id}"
            )
        else:
            logger.warning(f"Kepler Radar: Digest {digest_id} not found — cannot save correlations")

        return correlations

    except Exception as e:
        logger.error(f"❌ Kepler Radar: Correlation generation failed: {e}")
        return None


def regenerate_for_today(db: Session) -> Optional[Dict]:
    """
    Admin utility: Force regenerate correlations for today's digest.
    """
    today = date.today()
    digest = db.query(DailyDigest).filter(DailyDigest.date == today).first()
    if not digest:
        logger.warning("Kepler Radar: No digest found for today")
        return None
    return generate_correlations(digest.items or [], db, digest.id)
