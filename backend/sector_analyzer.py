"""
ANTIGRAVITY — Enhanced Sector Analyzer
Runs every Tuesday + Friday. Covers 15 NSE sector indices.
Uses Gemini 2.0 Flash for richer, more analytical sector spotlights.
"""
import json
from datetime import date, datetime, timedelta
from typing import List, Dict, Any, Optional

import google.generativeai as genai
import yfinance as yf
from loguru import logger
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_fixed

from config import settings
from models import SectorReport, DailyDigest

# ── Expanded NSE Sector Indices ───────────────────────────────────────────────
NSE_SECTOR_INDICES = {
    "Banking (Private)":    "^NSEBANK",
    "IT & Technology":      "^CNXIT",
    "Pharma & Healthcare":  "^CNXPHARMA",
    "Auto & EV":            "^CNXAUTO",
    "FMCG":                 "^CNXFMCG",
    "Realty":               "^CNXREALTY",
    "Metal & Mining":       "^CNXMETAL",
    "Energy & Oil/Gas":     "^CNXENERGY",
    "Infrastructure":       "^CNXINFRA",
    "Media & Entertainment":"^CNXMEDIA",
    "PSU Banks":            "^CNXPSUBANK",
    "Financial Services":   "^CNXFIN",
    "Midcap 100":           "^NSMIDCP100",
    "Smallcap 250":         "^CNXSC",
    "Consumption":          "^CNXCONSUM",
}

# ── Nifty Broad Indices ───────────────────────────────────────────────────────
BROAD_INDICES = {
    "Nifty 50":    "^NSEI",
    "Sensex":      "^BSESN",
    "Nifty 500":   "^CRSLDX",
}

# ── Enhanced Sector Report Prompt ─────────────────────────────────────────────
SECTOR_REPORT_PROMPT = """
You are a senior equity analyst writing a weekly sector spotlight for a premium Indian investment research platform. Your readers are sophisticated — active traders, long-term investors, and finance professionals who want depth, not generic commentary.

Based on the following sector performance data, broad market context, and recent news:

{data}

Write a 500-600 word sector spotlight report structured EXACTLY as follows:

**SECTOR SPOTLIGHT — {date}**

**FEATURED SECTOR: [Sector Name]**
[One sentence — what's the key story this week]

---

**WHY THIS SECTOR IS IN FOCUS**
[80-100 words. Be specific. What data points (performance %, news, policy, FII flow, earnings) make this sector the most interesting this week? Avoid vague statements like "there is momentum."]

**THE MACRO TAILWINDS (AND HEADWINDS)**
[80-100 words. What policy, global, or domestic macro factors are driving or threatening this sector? Mention specific government initiatives, RBI decisions, global commodity prices, currency moves — whatever is most relevant to this sector.]

**STOCKS WORTH DEEPER RESEARCH**
List 4-6 specific NSE-listed stocks in this sector. For each, give ONE specific reason why it's worth researching (a recent catalyst, an interesting valuation metric, or a structural story). Format:
• **TICKER (Company Name)** — reason

[Important: Do not give price targets or buy/sell recommendations.]

**KEY RISKS TO MONITOR**
[60-80 words. 3 specific, quantifiable risks. Not generic "global uncertainty." Examples: "Crude above $95/barrel would compress EBITDA margins by ~200bps for major refiners" or "Any reversal in FII flows could pressure PSU bank valuations given high FII ownership."]

**POSITIONING CONTEXT**
[60-80 words. How does this sector fit into the current broader market cycle? Is it early innings, peak, or showing reversal signs? What is the risk-reward for a 3-6 month horizon?]

---
*Disclaimer: This analysis is for educational purposes only. Not investment advice. Not SEBI registered. Do your own research.*

WRITING RULES:
- Use specific numbers from the data provided (%, ₹ crore, basis points)
- Confident but not prescriptive
- No buy/sell/hold language
- Plain English — if you use a term like "EBITDA" or "NIM", define it once
- Reference specific news items from the data where relevant
"""


def _fetch_sector_performance() -> Dict[str, Dict[str, float]]:
    """Fetch 5-day and 1-month performance for each NSE sector index."""
    performance = {}
    for sector_name, symbol in {**NSE_SECTOR_INDICES, **BROAD_INDICES}.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="35d")  # extra buffer for weekends/holidays
            if hist is None or hist.empty or len(hist) < 2:
                logger.warning(f"No data for {sector_name} ({symbol})")
                continue

            close = hist["Close"].dropna()
            if len(close) < 2:
                continue

            latest = float(close.iloc[-1])
            one_day_ago = float(close.iloc[-2]) if len(close) >= 2 else latest
            five_days_ago = float(close.iloc[-min(5, len(close))])
            twenty_days_ago = float(close.iloc[-min(20, len(close))])

            day_change_pct = ((latest - one_day_ago) / one_day_ago) * 100
            week_change_pct = ((latest - five_days_ago) / five_days_ago) * 100
            month_change_pct = ((latest - twenty_days_ago) / twenty_days_ago) * 100

            performance[sector_name] = {
                "current": round(latest, 2),
                "day_change_pct": round(day_change_pct, 2),
                "week_change_pct": round(week_change_pct, 2),
                "month_change_pct": round(month_change_pct, 2),
            }
        except Exception as e:
            logger.warning(f"Could not fetch {sector_name} ({symbol}): {e}")

    logger.info(f"Fetched performance for {len(performance)} indices")
    return performance


def _get_sector_news(db: Session, days_back: int = 7) -> List[str]:
    """Pull SECTOR/POLICY/GST-tagged news from recent digests."""
    cutoff = date.today() - timedelta(days=days_back)
    recent_digests = (
        db.query(DailyDigest)
        .filter(DailyDigest.date >= cutoff)
        .order_by(DailyDigest.date.desc())
        .all()
    )

    sector_news = []
    for digest in recent_digests:
        for item in (digest.items or []):
            cat = item.get("category", "")
            if cat in ("SECTOR", "MACRO", "POLICY", "GST", "RBI_SEBI", "RESULT"):
                importance = item.get("importance_score", 5)
                sentiment = item.get("sentiment", "NEUTRAL")
                sector_news.append(
                    f"[{cat}][Score:{importance}][{sentiment}] "
                    f"{item.get('title', '')} — {item.get('summary', '')[:250]}"
                )

    # Sort by importance (embedded in string, approximate)
    sector_news.sort(key=lambda x: "Score:9" in x or "Score:10" in x or "Score:8" in x, reverse=True)

    logger.info(f"Found {len(sector_news)} relevant news items from last {days_back} days")
    return sector_news[:25]  # cap at 25 items for prompt efficiency


def _build_analysis_data(performance: Dict, news: List[str]) -> str:
    """Format sector performance + news for the prompt."""
    lines = []

    # Separate broad indices from sector indices
    broad_names = set(BROAD_INDICES.keys())
    sector_perf = {k: v for k, v in performance.items() if k not in broad_names}
    broad_perf = {k: v for k, v in performance.items() if k in broad_names}

    # Broad market context
    if broad_perf:
        lines.append("BROAD MARKET CONTEXT:\n")
        for name, data in broad_perf.items():
            arrow_d = "▲" if data["day_change_pct"] >= 0 else "▼"
            arrow_w = "▲" if data["week_change_pct"] >= 0 else "▼"
            lines.append(
                f"  {name}: {data['current']:,.0f} pts | "
                f"{arrow_d} {abs(data['day_change_pct']):.2f}% today | "
                f"{arrow_w} {abs(data['week_change_pct']):.2f}% this week"
            )

    # Sector performance table
    lines.append("\nSECTOR PERFORMANCE (this week vs today vs last month):\n")
    sorted_sectors = sorted(sector_perf.items(), key=lambda x: x[1]["week_change_pct"], reverse=True)

    lines.append(f"{'Sector':<28} {'Week':>8} {'Today':>8} {'Month':>8}")
    lines.append("-" * 56)
    for sector, data in sorted_sectors:
        arrow_w = "▲" if data["week_change_pct"] >= 0 else "▼"
        arrow_d = "▲" if data["day_change_pct"] >= 0 else "▼"
        arrow_m = "▲" if data["month_change_pct"] >= 0 else "▼"
        lines.append(
            f"  {sector:<26} "
            f"{arrow_w}{abs(data['week_change_pct']):.1f}%    "
            f"{arrow_d}{abs(data['day_change_pct']):.1f}%    "
            f"{arrow_m}{abs(data['month_change_pct']):.1f}%"
        )

    if news:
        lines.append("\nKEY MARKET NEWS THIS WEEK:\n")
        for item in news:
            lines.append(f"  • {item}")

    return "\n".join(lines)


@retry(stop=stop_after_attempt(2), wait=wait_fixed(15))
def _call_gemini_flash(data_str: str, report_date: str) -> str:
    """Try Gemini 2.0 Flash first for sector report."""
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-2.0-flash")
    prompt = SECTOR_REPORT_PROMPT.format(data=data_str, date=report_date)
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.35,
            max_output_tokens=3000,
        ),
    )
    return response.text


@retry(stop=stop_after_attempt(2), wait=wait_fixed(15))
def _call_gemini_pro(data_str: str, report_date: str) -> str:
    """Fallback to Gemini 1.5 Pro."""
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-1.5-pro")
    prompt = SECTOR_REPORT_PROMPT.format(data=data_str, date=report_date)
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(temperature=0.4, max_output_tokens=3000),
    )
    return response.text


def _call_gemini(data_str: str) -> str:
    """Try Flash first, fall back to Pro."""
    report_date = date.today().strftime("%B %d, %Y")
    try:
        return _call_gemini_flash(data_str, report_date)
    except Exception as e:
        logger.warning(f"Gemini Flash failed for sector report ({e}), falling back to Pro")
        return _call_gemini_pro(data_str, report_date)


def generate_sector_report(db: Session) -> Optional[SectorReport]:
    """
    Main entry point. Generates and saves weekly sector report.
    Idempotent — won't duplicate if run multiple times same day.
    """
    today = date.today()
    logger.info(f"=== Sector analysis started for {today} ===")

    # Check if already generated today
    existing = db.query(SectorReport).filter(SectorReport.date == today).first()
    if existing:
        logger.info(f"Sector report for {today} already exists — skipping")
        return existing

    performance = _fetch_sector_performance()
    news = _get_sector_news(db)

    if not performance and not news:
        logger.warning("No sector data available — skipping report generation")
        return None

    data_str = _build_analysis_data(performance, news)

    # Identify top performing sector for report metadata
    sector_only_perf = {k: v for k, v in performance.items() if k not in BROAD_INDICES}
    if sector_only_perf:
        top_sector = max(sector_only_perf.items(), key=lambda x: x[1]["week_change_pct"])[0]
    else:
        top_sector = "Mixed"

    try:
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not set")
        content = _call_gemini(data_str)
        logger.info(f"Gemini generated sector report: {len(content)} chars for {top_sector}")
    except Exception as e:
        logger.error(f"Gemini sector analysis failed: {e}")
        content = _fallback_content(performance, top_sector)

    report = SectorReport(
        date=today,
        sector_name=top_sector,
        content=content,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    logger.info(f"✅ Sector report saved: {top_sector}")
    return report


def _fallback_content(performance: Dict, top_sector: str) -> str:
    """Structured fallback if Gemini call fails."""
    today_str = date.today().strftime("%B %d, %Y")
    lines = [
        f"**SECTOR SPOTLIGHT — {today_str}**\n",
        f"**FEATURED SECTOR: {top_sector}**\n\n",
        "**SECTOR PERFORMANCE THIS WEEK:**\n",
    ]
    sorted_sectors = sorted(performance.items(), key=lambda x: x[1]["week_change_pct"], reverse=True)
    for sector, data in sorted_sectors:
        arrow = "▲" if data["week_change_pct"] >= 0 else "▼"
        lines.append(
            f"• {sector}: {arrow} {abs(data['week_change_pct']):.1f}% this week, "
            f"{'▲' if data['day_change_pct'] >= 0 else '▼'} {abs(data['day_change_pct']):.1f}% today\n"
        )
    lines.append(
        "\n---\n*This analysis is for educational and informational purposes only. "
        "Not investment advice. We are not SEBI registered advisers. "
        "Please do your own research before making any investment decisions.*"
    )
    return "".join(lines)


if __name__ == "__main__":
    from database import SessionLocal
    db = SessionLocal()
    try:
        report = generate_sector_report(db)
        if report:
            print(f"\n{'='*60}")
            print(f"Sector Report: {report.sector_name}")
            print(f"{'='*60}")
            print(report.content[:800])
    finally:
        db.close()
