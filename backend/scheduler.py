"""
KEPLER -- APScheduler Job Scheduler
All pipeline jobs wired with Asia/Kolkata timezone.
Failure handling: log traceback + log alert + 15-minute retry.
"""
import asyncio
import traceback
from datetime import datetime, timedelta

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from config import settings

IST = pytz.timezone("Asia/Kolkata")


def _send_admin_alert(message: str):
    """Log admin alert. Telegram disabled -- wire to push/email when ready."""
    logger.warning(f"[ADMIN ALERT] {message}")


def _run_with_retry(job_name: str, job_fn, *args, **kwargs):
    """Execute a job. On failure: log, alert admin, retry once after 15 min."""
    try:
        logger.info(f"▶  {job_name} started")
        job_fn(*args, **kwargs)
        logger.info(f"✅ {job_name} completed successfully")
    except Exception as e:
        tb = traceback.format_exc()
        now = datetime.now(IST).strftime("%H:%M IST")
        logger.error(f"❌ {job_name} FAILED at {now}:\n{tb}")

        alert = f"❌ *{job_name}* failed at {now}\n`{str(e)[:200]}`\nRetrying in 15 minutes."
        _send_admin_alert(alert)

        # Schedule a one-time retry after 15 minutes
        def retry():
            try:
                logger.info(f"🔄 Retrying {job_name}...")
                job_fn(*args, **kwargs)
                logger.info(f"✅ {job_name} retry succeeded")
            except Exception as retry_e:
                logger.error(f"❌ {job_name} retry also FAILED: {retry_e}")
                _send_admin_alert(f"❌ *{job_name}* retry also failed.\n`{str(retry_e)[:200]}`")

        import threading
        timer = threading.Timer(15 * 60, retry)
        timer.daemon = True
        timer.start()


# ── Individual job wrappers ───────────────────────────────────────────────────

def job_news_and_ai():
    """Collect news and run AI processing pipeline."""
    from database import SessionLocal
    from news_collector import collect_all_news
    from ai_processor import process_news

    db = SessionLocal()
    try:
        articles = collect_all_news(
            newsapi_key=settings.newsapi_key,
            gnews_api_key=settings.gnews_api_key,
        )
        process_news(articles, db)
    finally:
        db.close()


def job_breakout_scan():
    """Run Nifty 500 breakout scanner."""
    from database import SessionLocal
    from breakout_scanner import scan_breakouts

    db = SessionLocal()
    try:
        results = scan_breakouts(db)
        logger.info(f"Breakout scan complete: {len(results)} setups saved")
    finally:
        db.close()


def job_telegram_publish():
    """Telegram publish -- DISABLED. Re-enable when Telegram is configured."""
    logger.info("Telegram publish skipped (Telegram not configured).")


def job_sector_analysis():
    """Generate weekly sector report (runs every Tuesday + Friday)."""
    from database import SessionLocal
    from sector_analyzer import generate_sector_report

    db = SessionLocal()
    try:
        report = generate_sector_report(db)
        if report:
            logger.info(f"Sector report generated: {report.sector_name}")
    finally:
        db.close()


def job_market_updates():
    """
    Collect official regulatory updates (GST/RBI/SEBI/Tax/PIB)
    and process them through the AI for structured summaries.
    Runs daily Mon-Fri at 7:00 AM IST.
    """
    from database import SessionLocal
    from news_collector import collect_official_feeds
    from ai_processor import process_market_updates_only
    from models import MarketUpdate
    from datetime import date

    db = SessionLocal()
    try:
        official_articles = collect_official_feeds()
        if not official_articles:
            logger.info("Market updates: no new official articles collected")
            return

        updates = process_market_updates_only(official_articles, db)

        saved = 0
        for update in updates:
            if not update.get("title") or not update.get("summary"):
                continue
            # Skip if already saved (dedup by title)
            exists = db.query(MarketUpdate).filter(
                MarketUpdate.title == update["title"]
            ).first()
            if exists:
                continue

            effective = None
            if update.get("effective_date"):
                try:
                    from datetime import datetime
                    effective = datetime.strptime(update["effective_date"][:10], "%Y-%m-%d").date()
                except Exception:
                    pass

            mu = MarketUpdate(
                title=update["title"],
                update_type=update.get("update_type", "OTHER"),
                summary=update["summary"],
                effective_date=effective,
                affected_entities=update.get("affected_entities", []),
                importance=update.get("importance", "MEDIUM"),
                source=update.get("source", ""),
                source_url=update.get("source_url", ""),
            )
            db.add(mu)
            saved += 1

        if saved:
            db.commit()
            logger.info(f"Market updates: {saved} new updates saved")
    except Exception as e:
        logger.error(f"Market updates job failed: {e}")
        db.rollback()
    finally:
        db.close()


def job_cleanup_old_logs():
    """Delete content_log entries older than 90 days."""
    from database import SessionLocal
    from models import ContentLog
    from sqlalchemy import and_

    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(days=90)
        deleted = (
            db.query(ContentLog)
            .filter(ContentLog.viewed_at < cutoff)
            .delete()
        )
        db.commit()
        logger.info(f"Cleanup: deleted {deleted} old content log entries")
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")
        db.rollback()
    finally:
        db.close()


def job_email_sequences():
    """
    Check which users need Day 2/3/5/7 emails and monthly summaries.
    Runs daily at 9 AM IST.
    """
    from database import SessionLocal
    from models import User
    from email_service import (
        send_day2_email, send_day3_email,
        send_day5_email, send_day7_email,
        send_monthly_summary,
    )

    db = SessionLocal()
    try:
        now = datetime.utcnow()
        users = db.query(User).filter(User.is_active == True).all()

        for user in users:
            days_since = (now - user.created_at).days

            try:
                if days_since == 1:
                    send_day2_email(user.email)
                elif days_since == 2:
                    send_day3_email(user.email)
                elif days_since == 4:
                    send_day5_email(user.email)
                elif days_since == 6:
                    send_day7_email(user.email)
                elif days_since > 0 and now.day == 1:
                    # Monthly summary on the 1st
                    month_name = now.strftime("%B %Y")
                    from sqlalchemy import func, extract
                    from models import DailyDigest, BreakoutWatchlist, SectorReport
                    last_month = now.month - 1 if now.month > 1 else 12
                    last_month_year = now.year if now.month > 1 else now.year - 1

                    digest_count = db.query(func.count(DailyDigest.id)).filter(
                        extract("month", DailyDigest.created_at) == last_month,
                        extract("year", DailyDigest.created_at) == last_month_year,
                    ).scalar() or 0

                    breakout_count = db.query(func.count(BreakoutWatchlist.id)).filter(
                        extract("month", BreakoutWatchlist.created_at) == last_month,
                        extract("year", BreakoutWatchlist.created_at) == last_month_year,
                    ).scalar() or 0

                    sector_count = db.query(func.count(SectorReport.id)).filter(
                        extract("month", SectorReport.created_at) == last_month,
                        extract("year", SectorReport.created_at) == last_month_year,
                    ).scalar() or 0

                    send_monthly_summary(
                        user.email,
                        month=now.strftime("%B %Y"),
                        digest_count=digest_count,
                        chart_count=breakout_count,
                        sector_count=sector_count,
                    )
            except Exception as e:
                logger.warning(f"Email sequence error for {user.email}: {e}")

    finally:
        db.close()


# ── Scheduler setup ───────────────────────────────────────────────────────────

def create_scheduler() -> BackgroundScheduler:
    """
    Create and configure the APScheduler instance.
    All times in Asia/Kolkata (IST = UTC+5:30).
    """
    scheduler = BackgroundScheduler(timezone=IST)

    # Mon-Fri 06:00, 09:00, 12:00, 15:00, 18:00 IST — News collection + AI processing
    # 5x/day: pre-market, market open, midday, pre-close, post-close
    scheduler.add_job(
        func=lambda: _run_with_retry("News+AI Pipeline", job_news_and_ai),
        trigger=CronTrigger(day_of_week="mon-fri", hour="6,9,12,15,18", minute=0, timezone=IST),
        id="news_and_ai",
        name="News Collection + AI Processing",
        replace_existing=True,
    )

    # Mon-Fri 07:00 and 13:00 IST — Breakout scanner (pre-market + mid-session)
    scheduler.add_job(
        func=lambda: _run_with_retry("Breakout Scanner", job_breakout_scan),
        trigger=CronTrigger(day_of_week="mon-fri", hour="7,13", minute=0, timezone=IST),
        id="breakout_scan",
        name="Breakout Scanner",
        replace_existing=True,
    )

    # Mon-Fri 08:00 IST — Telegram publish
    scheduler.add_job(
        func=lambda: _run_with_retry("Telegram Publisher", job_telegram_publish),
        trigger=CronTrigger(day_of_week="mon-fri", hour=8, minute=0, timezone=IST),
        id="telegram_publish",
        name="Telegram Morning Digest",
        replace_existing=True,
    )

    # Every Tuesday + Friday 07:30 IST — Sector analysis (twice weekly for freshness)
    scheduler.add_job(
        func=lambda: _run_with_retry("Sector Analyzer", job_sector_analysis),
        trigger=CronTrigger(day_of_week="tue,fri", hour=7, minute=30, timezone=IST),
        id="sector_analysis",
        name="Weekly Sector Analysis (Tue+Fri)",
        replace_existing=True,
    )

    # Mon-Fri 07:00 IST — Market updates (GST, RBI, SEBI, Tax)
    scheduler.add_job(
        func=lambda: _run_with_retry("Market Updates Pipeline", job_market_updates),
        trigger=CronTrigger(day_of_week="mon-fri", hour=7, minute=0, timezone=IST),
        id="market_updates",
        name="Market Updates (GST/RBI/SEBI/Tax)",
        replace_existing=True,
    )

    # Daily 09:00 IST — Email sequences
    scheduler.add_job(
        func=lambda: _run_with_retry("Email Sequences", job_email_sequences),
        trigger=CronTrigger(hour=9, minute=0, timezone=IST),
        id="email_sequences",
        name="Email Sequences",
        replace_existing=True,
    )

    # Daily 23:00 IST — Cleanup
    scheduler.add_job(
        func=lambda: _run_with_retry("Log Cleanup", job_cleanup_old_logs),
        trigger=CronTrigger(hour=23, minute=0, timezone=IST),
        id="cleanup",
        name="Log Cleanup",
        replace_existing=True,
    )

    # ── ONE-TIME: Today at 11:15 IST — Manual scrape trigger ─────────────────
    scheduler.add_job(
        func=lambda: _run_with_retry("News+AI Pipeline (11:15 manual)", job_news_and_ai),
        trigger=CronTrigger(hour=11, minute=15, timezone=IST),
        id="news_and_ai_1115",
        name="News+AI Pipeline [11:15 Manual]",
        replace_existing=True,
    )
    scheduler.add_job(
        func=lambda: _run_with_retry("Breakout Scanner (11:15 manual)", job_breakout_scan),
        trigger=CronTrigger(hour=11, minute=15, timezone=IST),
        id="breakout_scan_1115",
        name="Breakout Scanner [11:15 Manual]",
        replace_existing=True,
    )
    scheduler.add_job(
        func=lambda: _run_with_retry("Market Updates (11:15 manual)", job_market_updates),
        trigger=CronTrigger(hour=11, minute=15, timezone=IST),
        id="market_updates_1115",
        name="Market Updates [11:15 Manual]",
        replace_existing=True,
    )

    return scheduler


# ── Start/stop ────────────────────────────────────────────────────────────────

_scheduler: BackgroundScheduler = None


def start_scheduler():
    global _scheduler
    _scheduler = create_scheduler()
    _scheduler.start()
    logger.info("⏰ APScheduler started (Asia/Kolkata timezone)")
    logger.info("Scheduled jobs:")
    for job in _scheduler.get_jobs():
        logger.info(f"  • {job.name}: {job.next_run_time}")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")


if __name__ == "__main__":
    # Test mode — run all jobs immediately with 1-minute intervals
    import time

    logger.info("=== SCHEDULER TEST MODE ===")
    logger.info("Running news+AI pipeline immediately...")

    _run_with_retry("News+AI Pipeline", job_news_and_ai)

    logger.info("Scheduler test complete. In production, start via main.py startup event.")
