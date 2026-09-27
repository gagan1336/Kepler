"""
KEPLER -- AI Deep Dive Generator
AI-powered research report engine for Indian equities.

Pipeline:
  1. Fetch live fundamentals via fundamentals_fetcher (PE, ROE, ROCE, D/E, etc.)
  2. Fetch current stock price and technicals via yfinance
  3. Pull recent company-specific news from cache
  4. Call Gemini 2.0 Flash with a structured Indian equity research prompt
  5. Return a fully typed DeepDive dict (sections, metrics, verdict, price target)

Output JSON structure:
  {
    "symbol": "RELIANCE",
    "company_name": "Reliance Industries Ltd",
    "sector": "Energy",
    "verdict": "BUY",            # BUY / HOLD / AVOID
    "risk_rating": "MEDIUM",     # LOW / MEDIUM / HIGH
    "price_target_12m": 3200,
    "summary": "2-3 sentence executive summary",
    "sections": [ {id, title, content, flags?, metrics?, data?}, ... ],
    "metrics_snapshot": { pe, pb, roe, roce, de, mktcap_cr, ... },
    "tags": ["largecap", "energy", "conglomerate"]
  }
"""

import json
import re
from datetime import datetime
from typing import Dict, Any, Optional, List

import yfinance as yf
import google.generativeai as genai
from loguru import logger

from config import settings
from fundamentals_fetcher import fetch_fundamentals


# ── Deep Dive System Prompt ────────────────────────────────────────────────────
_SYSTEM_PROMPT = """
You are a senior equity research analyst at a top Indian brokerage firm (think Motilal Oswal, Kotak Institutional Equities). You write deep-dive research reports for serious Indian investors — both retail and institutional.

Your reports are:
- Data-driven and India-specific (NSE/BSE context, SEBI regulations, RBI policy impact)
- Written in plain English — no unnecessary jargon
- Honest about risks — especially Indian-market-specific risks like promoter pledging, regulatory exposure, related-party transactions
- Action-oriented — investors need to know whether to BUY, HOLD, or AVOID

You will receive:
1. A stock symbol and company name
2. Live fundamental metrics (PE, PB, ROE, ROCE, D/E, margins, growth, shareholding)
3. Current market price and 52W range
4. Recent news about the company

You will produce a STRUCTURED JSON deep dive report. No markdown, no preamble. Return ONLY the JSON object.
"""

_USER_PROMPT_TEMPLATE = """
Generate a comprehensive deep dive report for:

COMPANY: {company_name} ({symbol})
SECTOR: {sector}
INDUSTRY: {industry}

=== LIVE FUNDAMENTALS ===
Current Price: ₹{current_price}
52W High: ₹{high_52w} | 52W Low: ₹{low_52w}
Market Cap: ₹{market_cap_cr} Cr
Enterprise Value: ₹{ev_cr} Cr

Valuation:
  PE Ratio (TTM): {pe_ratio}
  Forward PE: {forward_pe}
  PB Ratio: {pb_ratio}
  PEG Ratio: {peg_ratio}
  EV/EBITDA: {ev_ebitda}

Profitability:
  ROE: {roe}%
  ROCE: {roce}%
  ROA: {roa}%
  Operating Margin: {operating_margin}%
  Net Profit Margin: {profit_margin}%
  Gross Margin: {gross_margin}%

Financial Safety:
  Debt/Equity: {debt_to_equity}
  Current Ratio: {current_ratio}
  Quick Ratio: {quick_ratio}
  Free Cash Flow: ₹{fcf_cr} Cr

Growth (CAGR):
  Revenue Growth 3yr: {revenue_growth_3yr}%
  PAT Growth 3yr: {profit_growth_3yr}%
  Revenue Growth 1yr: {revenue_growth_1yr}%
  EPS: ₹{eps}

Dividends:
  Dividend Yield: {dividend_yield}%
  Payout Ratio: {payout_ratio}%

Shareholding:
  Promoter Holding: {promoter_holding}%
  FII Holding: {fii_holding}%
  DII Holding: {dii_holding}%
  Public Float: {public_float}%
  Beta: {beta}

=== RECENT NEWS ===
{news_summary}

=== OUTPUT FORMAT (return ONLY this JSON, no other text) ===
{{
  "symbol": "{symbol}",
  "company_name": "Full official company name",
  "sector": "Sector name",
  "verdict": "BUY" | "HOLD" | "AVOID",
  "risk_rating": "LOW" | "MEDIUM" | "HIGH",
  "price_target_12m": <number — 12-month price target in INR>,
  "summary": "2-3 sentence executive summary — what this company does, why this verdict",
  "tags": ["largecap/midcap/smallcap", "sector_tag", "theme_tag"],
  "sections": [
    {{
      "id": "business_overview",
      "title": "Business Overview",
      "content": "4-6 sentences. What the company does, revenue mix, key business segments, competitive moat. Be specific about India operations."
    }},
    {{
      "id": "financial_health",
      "title": "Financial Health",
      "content": "4-6 sentences. Analyse the revenue/PAT growth trajectory, margin trends, ROCE vs cost of capital, cash generation. Call out any deterioration.",
      "highlights": [
        {{"label": "3yr Revenue CAGR", "value": "X%", "signal": "POSITIVE"|"NEUTRAL"|"NEGATIVE"}},
        {{"label": "3yr PAT CAGR", "value": "X%", "signal": "POSITIVE"|"NEUTRAL"|"NEGATIVE"}},
        {{"label": "ROCE", "value": "X%", "signal": "POSITIVE"|"NEUTRAL"|"NEGATIVE"}},
        {{"label": "D/E Ratio", "value": "X.Xx", "signal": "POSITIVE"|"NEUTRAL"|"NEGATIVE"}},
        {{"label": "Net Margin", "value": "X%", "signal": "POSITIVE"|"NEUTRAL"|"NEGATIVE"}}
      ]
    }},
    {{
      "id": "shareholding_analysis",
      "title": "Shareholding & Governance",
      "content": "3-5 sentences. Analyse promoter holding, pledging risk (flag if unknown), FII vs DII trend, insider buying/selling patterns. Flag any governance concerns specific to Indian markets.",
      "flags": []  // e.g. ["Promoter pledging data unavailable", "FII ownership declining"]
    }},
    {{
      "id": "valuation",
      "title": "Valuation Analysis",
      "content": "4-5 sentences. PE vs sector average, PEG ratio interpretation, EV/EBITDA multiple, PB vs historical range. Is this stock expensive, fair, or cheap vs its own history and peers?",
      "highlights": [
        {{"label": "PE Ratio", "value": "Xx", "signal": "POSITIVE"|"NEUTRAL"|"NEGATIVE"}},
        {{"label": "PB Ratio", "value": "X.Xx", "signal": "POSITIVE"|"NEUTRAL"|"NEGATIVE"}},
        {{"label": "EV/EBITDA", "value": "Xx", "signal": "POSITIVE"|"NEUTRAL"|"NEGATIVE"}}
      ]
    }},
    {{
      "id": "india_specific_risks",
      "title": "India-Specific Risk Factors",
      "content": "4-6 sentences covering risks specific to Indian market context.",
      "risk_flags": [
        // List 3-6 specific risks — be honest. E.g.:
        // "Promoter pledging: data unavailable — verify on BSE filings"
        // "SEBI investigation history"
        // "Concentrated revenue from single customer"
        // "Currency risk from import dependency"
        // "Regulatory price caps (pharma/utility)"
        // "State election cycle impact on infrastructure ordering"
        "Risk 1",
        "Risk 2",
        "Risk 3"
      ]
    }},
    {{
      "id": "catalysts",
      "title": "Catalyst Watch — 6-12 Months",
      "content": "3-5 sentences. What events/triggers could re-rate this stock? Be specific about Indian market catalysts.",
      "catalysts": [
        // List 3-5 positive catalysts
        "Catalyst 1",
        "Catalyst 2"
      ]
    }},
    {{
      "id": "verdict",
      "title": "Investment Verdict",
      "content": "4-6 sentences. Clear buy/hold/avoid with reasoning. Include entry strategy (buy on dips? accumulate? wait for trigger?), price target basis (X times FY26 PE, DCF-based, etc.), and stop-loss logic. Write for a serious retail investor.",
      "price_target_12m": <same number as top-level>,
      "stop_loss": <suggested stop-loss price as number>,
      "verdict": "BUY" | "HOLD" | "AVOID"
    }}
  ]
}}
"""


# ── JSON Schema for structured output ─────────────────────────────────────────
_DEEP_DIVE_SCHEMA = {
    "type": "object",
    "properties": {
        "symbol":          {"type": "string"},
        "company_name":    {"type": "string"},
        "sector":          {"type": "string"},
        "verdict":         {"type": "string", "enum": ["BUY", "HOLD", "AVOID"]},
        "risk_rating":     {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]},
        "price_target_12m": {"type": "number"},
        "summary":         {"type": "string"},
        "tags":            {"type": "array", "items": {"type": "string"}},
        "sections":        {"type": "array", "items": {"type": "object"}},
    },
    "required": ["symbol", "company_name", "verdict", "risk_rating",
                 "price_target_12m", "summary", "sections"],
}


def _configure_gemini():
    if not settings.gemini_api_key:
        raise ValueError("GEMINI_API_KEY not set")
    genai.configure(api_key=settings.gemini_api_key)


def _safe_fmt(val, suffix="", default="N/A", multiplier=1.0) -> str:
    """Format a number for the prompt, returning 'N/A' if None."""
    if val is None:
        return default
    try:
        return f"{float(val) * multiplier:.2f}{suffix}"
    except (TypeError, ValueError):
        return default


def _crore(val_inr) -> str:
    """Convert raw INR value to ₹ Crore string."""
    if val_inr is None:
        return "N/A"
    try:
        return f"{float(val_inr) / 1e7:.0f}"
    except (TypeError, ValueError):
        return "N/A"


def _fetch_price_data(symbol: str) -> Dict[str, Any]:
    """Fetch current price and 52W high/low from yfinance."""
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        info = ticker.info or {}
        return {
            "current_price": info.get("currentPrice") or info.get("regularMarketPrice"),
            "high_52w":  info.get("fiftyTwoWeekHigh"),
            "low_52w":   info.get("fiftyTwoWeekLow"),
        }
    except Exception as e:
        logger.warning(f"Could not fetch price data for {symbol}: {e}")
        return {"current_price": None, "high_52w": None, "low_52w": None}


def _fetch_recent_news(symbol: str, company_name: str) -> str:
    """
    Pull recent news about this stock from the in-memory news cache.
    Falls back to a generic message if cache is unavailable.
    """
    news_lines = []
    try:
        from news_live import get_cached_news
        all_news = get_cached_news() or []
        sym_lower = symbol.lower()
        co_lower = (company_name or "").lower().split()[0]  # first word of company name

        for article in all_news[:200]:
            title = (article.get("title") or "").lower()
            desc  = (article.get("description") or "").lower()
            if sym_lower in title or co_lower in title or sym_lower in desc:
                pub = article.get("published_at", "")[:10]
                news_lines.append(f"- [{pub}] {article.get('title', '')}")
                if len(news_lines) >= 8:
                    break
    except Exception as e:
        logger.debug(f"News fetch for deep dive failed: {e}")

    if not news_lines:
        return "No recent specific news found in cache. Base analysis on fundamentals."
    return "\n".join(news_lines)


def _extract_json(text: str) -> Optional[Dict]:
    """Extract JSON object from Gemini response."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Strip markdown fences
    text = re.sub(r"```(?:json)?", "", text).strip().rstrip("```").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Find first { to last }
    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end != -1:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


def generate_deep_dive(symbol: str) -> Dict[str, Any]:
    """
    Main entry point. Generate a structured deep dive report for an NSE stock.

    Args:
        symbol: NSE ticker symbol (e.g. "RELIANCE", "TCS")

    Returns:
        dict with all deep dive fields ready to be saved to the DeepDive model.

    Raises:
        ValueError: if Gemini key missing or symbol is invalid
        RuntimeError: if AI generation fails after retries
    """
    symbol = symbol.upper().strip().replace(".NS", "").replace(".BO", "")
    logger.info(f"Generating deep dive for {symbol}")

    # ── 1. Fetch fundamentals ─────────────────────────────────────────────────
    logger.info(f"[{symbol}] Fetching fundamentals...")
    fund = fetch_fundamentals(symbol)
    company_name = fund.get("company_name") or symbol
    sector = fund.get("sector") or "Unknown"

    # ── 2. Fetch price data ────────────────────────────────────────────────────
    logger.info(f"[{symbol}] Fetching price data...")
    price_data = _fetch_price_data(symbol)

    # ── 3. Fetch recent news ───────────────────────────────────────────────────
    logger.info(f"[{symbol}] Fetching recent news...")
    news_summary = _fetch_recent_news(symbol, company_name)

    # ── 4. Calculate derived fields ────────────────────────────────────────────
    promoter = fund.get("promoter_holding")
    fii      = fund.get("fii_holding")
    dii      = fund.get("dii_holding")
    public_float = None
    if promoter is not None and fii is not None and dii is not None:
        public_float = round(max(0, 100 - promoter - fii - dii), 2)

    # ── 5. Build prompt ────────────────────────────────────────────────────────
    prompt = _USER_PROMPT_TEMPLATE.format(
        symbol=symbol,
        company_name=company_name,
        sector=sector,
        industry=fund.get("industry") or sector,
        current_price=_safe_fmt(price_data.get("current_price")),
        high_52w=_safe_fmt(price_data.get("high_52w")),
        low_52w=_safe_fmt(price_data.get("low_52w")),
        market_cap_cr=_crore(fund.get("market_cap")),
        ev_cr=_crore(fund.get("enterprise_value")),
        pe_ratio=_safe_fmt(fund.get("pe_ratio")),
        forward_pe=_safe_fmt(fund.get("forward_pe")),
        pb_ratio=_safe_fmt(fund.get("pb_ratio")),
        peg_ratio=_safe_fmt(fund.get("peg_ratio")),
        ev_ebitda=_safe_fmt(fund.get("ev_ebitda")),
        roe=_safe_fmt(fund.get("roe")),
        roce=_safe_fmt(fund.get("roce")),
        roa=_safe_fmt(fund.get("roa")),
        operating_margin=_safe_fmt(fund.get("operating_margin")),
        profit_margin=_safe_fmt(fund.get("profit_margin")),
        gross_margin=_safe_fmt(fund.get("gross_margin")),
        debt_to_equity=_safe_fmt(fund.get("debt_to_equity")),
        current_ratio=_safe_fmt(fund.get("current_ratio")),
        quick_ratio=_safe_fmt(fund.get("quick_ratio")),
        fcf_cr=_crore(fund.get("free_cash_flow")),
        revenue_growth_3yr=_safe_fmt(fund.get("revenue_growth_3yr")),
        profit_growth_3yr=_safe_fmt(fund.get("profit_growth_3yr")),
        revenue_growth_1yr=_safe_fmt(fund.get("revenue_growth_1yr")),
        eps=_safe_fmt(fund.get("eps")),
        dividend_yield=_safe_fmt(fund.get("dividend_yield")),
        payout_ratio=_safe_fmt(fund.get("payout_ratio")),
        promoter_holding=_safe_fmt(promoter),
        fii_holding=_safe_fmt(fii),
        dii_holding=_safe_fmt(dii),
        public_float=_safe_fmt(public_float),
        beta=_safe_fmt(fund.get("beta")),
        news_summary=news_summary,
    )

    # ── 6. Call Gemini ─────────────────────────────────────────────────────────
    logger.info(f"[{symbol}] Calling Gemini 2.0 Flash for deep dive generation...")
    _configure_gemini()

    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=_SYSTEM_PROMPT,
    )
    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=0.2,
                max_output_tokens=8192,
                response_mime_type="application/json",
            ),
        )
        raw_text = response.text
    except Exception as e:
        logger.error(f"[{symbol}] Gemini call failed: {e}")
        raise RuntimeError(f"AI generation failed for {symbol}: {e}")

    # ── 7. Parse response ──────────────────────────────────────────────────────
    result = _extract_json(raw_text)
    if not result:
        logger.error(f"[{symbol}] Could not parse Gemini JSON. Raw: {raw_text[:300]}")
        raise RuntimeError(f"Could not parse AI response for {symbol}")

    logger.info(f"[{symbol}] Deep dive generated — verdict={result.get('verdict')}, "
                f"target=₹{result.get('price_target_12m')}")

    # ── 8. Build metrics_snapshot ──────────────────────────────────────────────
    metrics_snapshot = {
        "pe_ratio":           fund.get("pe_ratio"),
        "pb_ratio":           fund.get("pb_ratio"),
        "roe":                fund.get("roe"),
        "roce":               fund.get("roce"),
        "debt_to_equity":     fund.get("debt_to_equity"),
        "profit_margin":      fund.get("profit_margin"),
        "operating_margin":   fund.get("operating_margin"),
        "revenue_growth_3yr": fund.get("revenue_growth_3yr"),
        "profit_growth_3yr":  fund.get("profit_growth_3yr"),
        "promoter_holding":   fund.get("promoter_holding"),
        "fii_holding":        fund.get("fii_holding"),
        "dii_holding":        fund.get("dii_holding"),
        "market_cap_cr":      round(float(fund["market_cap"]) / 1e7, 0)
                              if fund.get("market_cap") else None,
        "current_price":      price_data.get("current_price"),
        "high_52w":           price_data.get("high_52w"),
        "low_52w":            price_data.get("low_52w"),
        "dividend_yield":     fund.get("dividend_yield"),
        "eps":                fund.get("eps"),
        "beta":               fund.get("beta"),
        "ev_ebitda":          fund.get("ev_ebitda"),
        "snapshot_date":      datetime.utcnow().isoformat(),
    }

    # ── 9. Determine size tag from market cap ──────────────────────────────────
    tags = result.get("tags") or []
    mktcap_cr = metrics_snapshot.get("market_cap_cr") or 0
    if mktcap_cr > 100000:
        size_tag = "megacap"
    elif mktcap_cr > 20000:
        size_tag = "largecap"
    elif mktcap_cr > 5000:
        size_tag = "midcap"
    else:
        size_tag = "smallcap"
    if size_tag not in tags:
        tags.insert(0, size_tag)

    # ── 10. Return assembled deep dive dict ────────────────────────────────────
    return {
        "symbol":          symbol,
        "company_name":    result.get("company_name") or company_name,
        "sector":          result.get("sector") or sector,
        "verdict":         result.get("verdict", "HOLD"),
        "risk_rating":     result.get("risk_rating", "MEDIUM"),
        "price_target_12m": result.get("price_target_12m"),
        "summary":         result.get("summary", ""),
        "sections":        result.get("sections", []),
        "metrics_snapshot": metrics_snapshot,
        "tags":            tags,
        # Build a title for the deep dive
        "title": f"{result.get('company_name') or company_name} ({symbol}) — Deep Dive",
        # Legacy content field: join section content for backward compatibility
        "content": "\n\n".join(
            f"## {s.get('title', '')}\n{s.get('content', '')}"
            for s in result.get("sections", [])
        ),
    }


if __name__ == "__main__":
    # Test standalone
    import sys
    sym = sys.argv[1] if len(sys.argv) > 1 else "TITAN"
    result = generate_deep_dive(sym)
    print(f"\n{'='*60}")
    print(f"  {result['title']}")
    print(f"  Verdict: {result['verdict']} | Risk: {result['risk_rating']}")
    print(f"  Price Target: ₹{result['price_target_12m']}")
    print(f"  Tags: {', '.join(result['tags'])}")
    print(f"  Summary: {result['summary'][:200]}...")
    print(f"\n  Sections generated: {len(result['sections'])}")
    for s in result['sections']:
        print(f"    - {s.get('id')}: {s.get('title')}")
