"""
KEPLER -- IPO Intelligence Analyzer
Triggered manually when a new IPO is announced.
Calls Gemini 1.5 Pro for a neutral 350-400 word analysis brief.
"""
from datetime import date, datetime
from typing import Optional

import google.generativeai as genai
from loguru import logger
from sqlalchemy.orm import Session
from tenacity import retry, stop_after_attempt, wait_fixed

from config import settings
from models import IPOBrief

IPO_PROMPT = """
Write a neutral IPO analysis brief for {company_name}.
Industry: {industry} | Price band: {price_band}
Open: {open_date} | Close: {close_date}

Cover in 350-400 words:
1. WHAT THEY DO: Business model in simple terms
2. FINANCIALS: Revenue trend, profitability, debt levels
3. VALUATION: P/E vs listed peers in same sector
4. PROMOTER BACKGROUND: Brief note on management credibility
5. RED FLAGS: Any risks, litigation, related-party transactions
6. GREY MARKET PREMIUM: Note GMP if available (state source)

Be neutral. Do not recommend applying or avoiding.
Let the reader decide. End with this exact disclaimer:

"This analysis is for educational and informational purposes only.
Not investment advice. We are not SEBI registered investment advisers.
GMP data is sourced from unofficial channels and is not verified.
Please read the Red Herring Prospectus (RHP) before making any decisions."
"""


@retry(stop=stop_after_attempt(2), wait=wait_fixed(15))
def _call_gemini_pro(prompt: str) -> str:
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-1.5-pro")
    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(temperature=0.3, max_output_tokens=2048),
    )
    return response.text


def analyze_ipo(
    db: Session,
    company_name: str,
    open_date: date,
    close_date: date,
    price_band: str,
    industry: str,
) -> Optional[IPOBrief]:
    """
    Generate and save an IPO analysis brief.
    """
    logger.info(f"=== IPO analysis started: {company_name} ===")

    if not settings.gemini_api_key:
        logger.error("GEMINI_API_KEY not set — cannot generate IPO analysis")
        return None

    prompt = IPO_PROMPT.format(
        company_name=company_name,
        industry=industry,
        price_band=price_band,
        open_date=str(open_date),
        close_date=str(close_date),
    )

    try:
        content = _call_gemini_pro(prompt)
        logger.info(f"IPO brief generated: {len(content)} chars")
    except Exception as e:
        logger.error(f"Gemini Pro IPO analysis failed: {e}")
        content = f"""
**{company_name} IPO Brief**

Price Band: {price_band}
Open: {open_date} | Close: {close_date}
Industry: {industry}

Analysis generation failed. Please refer to the official Red Herring Prospectus (RHP)
filed with SEBI for complete information about this IPO.

*This is a placeholder. Detailed analysis will be added shortly.*

---
*This analysis is for educational and informational purposes only.
Not investment advice. We are not SEBI registered investment advisers.
Please read the Red Herring Prospectus (RHP) before making any decisions.*
"""

    ipo_brief = IPOBrief(
        company_name=company_name,
        open_date=open_date,
        close_date=close_date,
        price_band=price_band,
        industry=industry,
        content=content,
    )
    db.add(ipo_brief)
    db.commit()
    db.refresh(ipo_brief)

    logger.info(f"✅ IPO brief saved: {company_name} (id={ipo_brief.id})")
    return ipo_brief


if __name__ == "__main__":
    from database import SessionLocal
    db = SessionLocal()
    try:
        result = analyze_ipo(
            db=db,
            company_name="Example Technologies Ltd",
            open_date=date(2025, 2, 1),
            close_date=date(2025, 2, 3),
            price_band="₹150-160",
            industry="Technology",
        )
        if result:
            print(f"\nIPO Brief created: {result.id}")
            print(result.content[:400])
    finally:
        db.close()
