"""
KEPLER — Telegram Publisher
Formats and sends morning digest to Pro and Elite channels at 8 AM IST.
Sends admin alerts on pipeline failures.
"""
import asyncio
from datetime import date, datetime
from typing import Optional, List, Dict, Any

from loguru import logger
from telegram import Bot
from telegram.error import TelegramError

from config import settings

CATEGORY_EMOJIS = {
    "MACRO":  "🏛️",
    "SECTOR": "🏭",
    "STOCK":  "📈",
    "RESULT": "📋",
    "GLOBAL": "🌍",
    "POLICY": "📜",
}

MOOD_EMOJIS = {
    "BULLISH": "🟢",
    "BEARISH": "🔴",
    "NEUTRAL": "🟡",
}

DISCLAIMER = (
    "⚠️ For educational purposes only. "
    "Not SEBI registered. Not investment advice. "
    "Please do your own research."
)


def _format_digest_message(
    digest_date: date,
    market_mood: str,
    items: List[Dict[str, Any]],
    breakouts: List[Dict[str, Any]],
    sector_report_summary: Optional[str] = None,
) -> str:
    """Format the morning digest message."""
    mood_emoji = MOOD_EMOJIS.get(market_mood, "🟡")
    date_str = digest_date.strftime("%A, %d %B %Y")

    lines = [
        f"🌅 *KEPLER MORNING BRIEF*",
        f"{date_str} | Market Mood: {mood_emoji} {market_mood}",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    # News items
    for item in items[:8]:  # max 8 items to stay within Telegram limits
        cat = item.get("category", "STOCK")
        emoji = CATEGORY_EMOJIS.get(cat, "📌")
        title = item.get("title", "")
        summary = item.get("summary", "")
        sentiment = item.get("sentiment", "NEUTRAL")
        sent_emoji = MOOD_EMOJIS.get(sentiment, "🟡")

        lines.append(f"{emoji} *{cat}* {sent_emoji}")
        lines.append(f"_{title}_")
        lines.append(summary)
        lines.append("")

    # Breakout setups
    if breakouts:
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("📊 *BREAKOUT SETUPS TO WATCH*")
        lines.append("")
        for b in breakouts[:6]:  # max 6 setups
            symbol = b.get("symbol", "")
            desc = b.get("setup_description", "")
            if desc:
                # Truncate long descriptions
                short_desc = desc[:150] + "..." if len(desc) > 150 else desc
                lines.append(f"▸ *{symbol}*: {short_desc}")

    # Sector report summary (Elite only)
    if sector_report_summary:
        lines.append("")
        lines.append("━━━━━━━━━━━━━━━━━━━━")
        lines.append("🏭 *SECTOR SPOTLIGHT*")
        lines.append("")
        lines.append(sector_report_summary[:500] + "...")

    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(DISCLAIMER)

    return "\n".join(lines)


def _extract_sector_summary(sector_content: str) -> str:
    """Extract first paragraph from sector report for Telegram."""
    if not sector_content:
        return ""
    paragraphs = [p.strip() for p in sector_content.split("\n\n") if p.strip()]
    # Skip header lines
    for p in paragraphs:
        if len(p) > 100 and not p.startswith("#"):
            return p[:400]
    return sector_content[:400]


async def send_to_channel(bot: Bot, channel_id: str, message: str) -> bool:
    """Send a message to a Telegram channel."""
    try:
        await bot.send_message(
            chat_id=channel_id,
            text=message,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        logger.info(f"Message sent to channel {channel_id}")
        return True
    except TelegramError as e:
        logger.error(f"Telegram send error to {channel_id}: {e}")
        return False


async def send_admin_alert(message: str) -> bool:
    """Send an alert message to the admin."""
    if not settings.telegram_bot_token or not settings.admin_telegram_id:
        logger.warning("Telegram not configured — cannot send admin alert")
        return False

    try:
        bot = Bot(token=settings.telegram_bot_token)
        await bot.send_message(
            chat_id=settings.admin_telegram_id,
            text=message,
            parse_mode="Markdown",
        )
        return True
    except TelegramError as e:
        logger.error(f"Admin alert failed: {e}")
        return False


async def add_user_to_channel(telegram_user_id: str, channel_id: str) -> bool:
    """Invite a user to a private Telegram channel via bot."""
    if not settings.telegram_bot_token:
        return False
    try:
        bot = Bot(token=settings.telegram_bot_token)
        # Note: Bot must be admin in channel with invite permissions
        link = await bot.create_chat_invite_link(
            chat_id=channel_id,
            member_limit=1,
            expire_date=None,
        )
        await bot.send_message(
            chat_id=telegram_user_id,
            text=(
                f"🎉 Welcome to KEPLER!\n\n"
                f"Here is your exclusive channel invite link:\n{link.invite_link}\n\n"
                f"This link is for your use only and expires after one use."
            ),
        )
        return True
    except TelegramError as e:
        logger.error(f"Could not add user {telegram_user_id} to channel: {e}")
        return False


async def publish_morning_digest(db=None) -> bool:
    """
    Main entry point. Fetches today's digest and breakouts from DB,
    formats the message, and sends to Pro and Elite channels.
    """
    if not settings.telegram_bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — skipping Telegram publish")
        return False

    if not settings.telegram_pro_channel_id and not settings.telegram_elite_channel_id:
        logger.warning("No Telegram channel IDs configured — skipping")
        return False

    logger.info("=== Telegram publish started ===")

    # Import here to avoid circular imports
    from database import SessionLocal
    from models import DailyDigest, BreakoutWatchlist, SectorReport

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        today = date.today()

        digest = db.query(DailyDigest).filter(DailyDigest.date == today).first()
        if not digest:
            logger.warning("No digest found for today — skipping publish")
            return False

        breakouts = (
            db.query(BreakoutWatchlist)
            .filter(BreakoutWatchlist.date == today)
            .all()
        )
        breakout_dicts = [
            {"symbol": b.symbol, "setup_description": b.setup_description}
            for b in breakouts
        ]

        latest_sector = db.query(SectorReport).order_by(SectorReport.date.desc()).first()

        bot = Bot(token=settings.telegram_bot_token)
        success = True

        # ── Pro channel ───────────────────────────────────────────────────────
        if settings.telegram_pro_channel_id:
            pro_message = _format_digest_message(
                digest_date=today,
                market_mood=digest.market_mood or "NEUTRAL",
                items=digest.items or [],
                breakouts=breakout_dicts,
            )
            ok = await send_to_channel(bot, settings.telegram_pro_channel_id, pro_message)
            success = success and ok

        # ── Elite channel (includes sector report) ────────────────────────────
        if settings.telegram_elite_channel_id:
            sector_summary = None
            if latest_sector and latest_sector.content:
                sector_summary = _extract_sector_summary(latest_sector.content)

            elite_message = _format_digest_message(
                digest_date=today,
                market_mood=digest.market_mood or "NEUTRAL",
                items=digest.items or [],
                breakouts=breakout_dicts,
                sector_report_summary=sector_summary,
            )
            ok = await send_to_channel(bot, settings.telegram_elite_channel_id, elite_message)
            success = success and ok

        if success:
            logger.info("✅ Morning digest published to all channels")
        else:
            await send_admin_alert(
                f"❌ Telegram publish had errors at {datetime.now().strftime('%H:%M IST')}. "
                f"Check logs immediately."
            )

        return success

    except Exception as e:
        logger.error(f"Telegram publish failed: {e}")
        try:
            await send_admin_alert(f"❌ Telegram publish failed at {datetime.now().strftime('%H:%M')}: {str(e)[:200]}")
        except Exception:
            pass
        return False
    finally:
        if close_db:
            db.close()


def run_publish():
    """Synchronous wrapper for APScheduler."""
    asyncio.run(publish_morning_digest())


if __name__ == "__main__":
    asyncio.run(publish_morning_digest())
