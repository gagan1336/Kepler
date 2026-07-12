"""
ANTIGRAVITY — Email Service
All email sequences via Resend API:
  Day 1 welcome, Day 2, Day 3, Day 5, Day 7, Monthly summary, Cancellation.
Also: payment failed alert.
"""
from datetime import datetime
from typing import Optional
from loguru import logger
import resend

from config import settings

resend.api_key = settings.resend_api_key


def _send(to: str, subject: str, html: str) -> bool:
    """Send an email via Resend. Returns True on success."""
    if not settings.resend_api_key:
        logger.warning(f"RESEND_API_KEY not set — skipping email to {to}")
        return False
    try:
        resp = resend.Emails.send({
            "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
            "to": [to],
            "subject": subject,
            "html": html,
        })
        logger.info(f"Email sent: '{subject}' → {to} (id: {resp.get('id', 'unknown')})")
        return True
    except Exception as e:
        logger.error(f"Email send failed to {to}: {e}")
        return False


def _base_template(content: str, preheader: str = "") -> str:
    """Wrap content in a clean dark email template."""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Antigravity</title>
<style>
  body {{ margin:0; padding:0; background:#0a0a0a; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }}
  .container {{ max-width:600px; margin:0 auto; background:#111; border-radius:12px; overflow:hidden; }}
  .header {{ background:#111; padding:32px 40px 24px; border-bottom:1px solid #1e1e1e; }}
  .logo {{ font-size:22px; font-weight:700; color:#00C48C; letter-spacing:2px; }}
  .body {{ padding:32px 40px; color:#e0e0e0; line-height:1.7; font-size:15px; }}
  .body h2 {{ color:#fff; font-size:22px; margin-top:0; }}
  .body p {{ color:#b0b0b0; }}
  .body a {{ color:#00C48C; text-decoration:none; }}
  .cta {{ display:inline-block; margin:24px 0; padding:14px 32px; background:#00C48C; color:#000 !important; font-weight:700; border-radius:8px; text-decoration:none; font-size:15px; }}
  .footer {{ padding:24px 40px; background:#0a0a0a; color:#555; font-size:12px; border-top:1px solid #1a1a1a; }}
  .disclaimer {{ background:#1a1a1a; border-left:3px solid #333; padding:12px 16px; margin:24px 0; font-size:12px; color:#666; border-radius:0 4px 4px 0; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="logo">ANTIGRAVITY</div>
  </div>
  <div class="body">
    {content}
    <div class="disclaimer">
      Antigravity provides market analysis and educational content only. We are not SEBI registered investment advisers.
      This is not investment advice. Please do your own research before making any investment decisions.
    </div>
  </div>
  <div class="footer">
    <p>You're receiving this because you signed up for Antigravity.</p>
    <p>© {datetime.now().year} Antigravity. All rights reserved.</p>
    <p>To unsubscribe, <a href="#" style="color:#555">click here</a>.</p>
  </div>
</div>
</body>
</html>
"""


# ── Day 1: Welcome ────────────────────────────────────────────────────────────
def send_welcome_email(to_email: str) -> bool:
    content = """
<h2>Welcome to Antigravity 👋</h2>
<p>Your free 7-day trial has started. Here's what to expect:</p>
<p><strong>Every weekday at 8 AM IST</strong>, you'll receive an AI-curated morning digest — filtered, summarised, and scored for importance. No noise. No tips. Just clean research.</p>
<p><strong>What you have access to:</strong></p>
<ul>
  <li>📰 Daily AI-filtered market digest (top 3 items on free plan)</li>
  <li>🏭 Latest sector report (free for all users)</li>
  <li>📊 Latest IPO brief (free for all users)</li>
</ul>
<p><strong>What Antigravity is not:</strong></p>
<ul>
  <li>❌ Not a tip service</li>
  <li>❌ Not SEBI registered advice</li>
  <li>❌ Not a stock recommendation service</li>
</ul>
<p>We help you understand markets better — what you do with that understanding is entirely your decision.</p>
<a href="https://antigravity.in/dashboard" class="cta">Go to Your Dashboard →</a>
<p style="color:#555; font-size:13px">Questions? Just reply to this email. I read every reply.</p>
"""
    return _send(to_email, "Welcome to Antigravity — here's how to get started", _base_template(content))


def send_subscription_welcome(to_email: str, plan: str) -> bool:
    plan_title = plan.replace("_", " ").title()
    content = f"""
<h2>You're now on {plan_title} 🎉</h2>
<p>Your subscription is active. Here's everything you now have access to:</p>
<p><strong>Pro Plan includes:</strong></p>
<ul>
  <li>📰 Full morning digest — all items, every day</li>
  <li>📊 Breakout watchlist — pre-breakout technical setups</li>
  <li>🏭 Sector reports — weekly analysis + 12-week history</li>
  <li>📋 Full IPO briefs + archive</li>
  <li>📁 Deep dive list + summaries</li>
</ul>
<p><strong>The optimal routine:</strong></p>
<ol>
  <li>Read the morning digest at 8 AM — takes 5 minutes</li>
  <li>Check the breakout watchlist for technically interesting setups</li>
  <li>Read the sector report every Tuesday</li>
</ol>
<a href="https://antigravity.in/dashboard" class="cta">Open Your Dashboard →</a>
"""
    return _send(to_email, f"Your Antigravity {plan_title} is active", _base_template(content))


# ── Day 2 ─────────────────────────────────────────────────────────────────────
def send_day2_email(to_email: str) -> bool:
    content = """
<h2>Our 3 best reports — read these first</h2>
<p>Before the market opens today, here are three pieces of analysis our members found most useful:</p>
<p><strong>1. Banking Sector Spotlight</strong><br>
How the RBI rate pause is affecting private banks, PSU banks, and NBFCs differently. Which metrics actually matter right now.</p>
<p><strong>2. IT Sector: Reading the Deal Wins Data</strong><br>
Why deal announcements don't always translate to revenue, and which numbers to track instead.</p>
<p><strong>3. How to Use the Breakout Watchlist</strong><br>
A quick guide to what the technical criteria actually mean, and how to do your own research from there.</p>
<a href="https://antigravity.in/sample" class="cta">Read Sample Reports →</a>
"""
    return _send(to_email, "Our 3 best reports — read these first", _base_template(content))


# ── Day 3 ─────────────────────────────────────────────────────────────────────
def send_day3_email(to_email: str) -> bool:
    content = """
<h2>How Pro members use Antigravity in 10 minutes each morning</h2>
<p>This is the exact routine most of our Pro members follow:</p>
<p><strong>8:00 AM — Morning digest arrives in Telegram</strong><br>
Scan the headlines. Read the 2-3 items relevant to your portfolio or watchlist. Takes 3 minutes.</p>
<p><strong>8:05 AM — Check the breakout watchlist</strong><br>
Look for setups that match stocks you were already watching. Don't act on setups you don't understand.</p>
<p><strong>Tuesdays at 8:00 AM — Sector report</strong><br>
Read the full sector report. It provides the macro context that makes individual stock moves make sense.</p>
<p>That's it. 10 minutes. You're better informed than 95% of retail traders who spend hours consuming noise.</p>
<a href="https://antigravity.in/dashboard" class="cta">Open Dashboard →</a>
"""
    return _send(to_email, "How Pro members use Antigravity in 10 minutes each morning", _base_template(content))


# ── Day 5 ─────────────────────────────────────────────────────────────────────
def send_day5_email(to_email: str) -> bool:
    content = """
<h2>How's your first week going?</h2>
<p>You've had access to Antigravity for five days now.</p>
<p>I'm curious — is the morning digest format working for you? Too long, too short? Is there something you expected to see that you're not finding?</p>
<p>Reply to this email. I read every reply personally, and your feedback directly shapes what we build next.</p>
<p>If everything is going well — great. I just wanted to check in.</p>
<p style="color:#888; font-size:13px">— Antigravity Team</p>
"""
    return _send(to_email, "How's your first week going?", _base_template(content))


# ── Day 7 ─────────────────────────────────────────────────────────────────────
def send_day7_email(to_email: str, digest_count: int = 5, chart_count: int = 5) -> bool:
    content = f"""
<h2>Your first week on Antigravity</h2>
<p>Here's what you received in your first seven days:</p>
<ul>
  <li>📰 <strong>{digest_count} morning digests</strong> — AI-filtered, scored, and summarised</li>
  <li>📊 <strong>{chart_count} breakout setups</strong> — pre-breakout technical setups from the Nifty 500</li>
  <li>🏭 <strong>1 sector report</strong> — this week's sector spotlight</li>
</ul>
<p>Your trial continues. Everything keeps running exactly as it has been.</p>
<p>If you're finding this useful, the Pro plan is ₹799/month — less than a single brokerage consultation.</p>
<a href="https://antigravity.in/pricing" class="cta">View Pricing →</a>
<p style="color:#555; font-size:13px">No pressure. Your free access continues regardless.</p>
"""
    return _send(to_email, "Your first week on Antigravity", _base_template(content))


# ── Monthly summary ───────────────────────────────────────────────────────────
def send_monthly_summary(to_email: str, month: str, digest_count: int, chart_count: int, sector_count: int) -> bool:
    content = f"""
<h2>Your Antigravity summary — {month}</h2>
<p>Here's what you received this month:</p>
<ul>
  <li>📰 <strong>{digest_count} morning digests</strong></li>
  <li>📊 <strong>{chart_count} chart analyses</strong> from the breakout scanner</li>
  <li>🏭 <strong>{sector_count} sector reports</strong></li>
</ul>
<p>Thank you for being part of Antigravity. The platform is only useful if it actually helps you make better-informed decisions — and the best way to tell us is to reply to this email.</p>
<a href="https://antigravity.in/dashboard" class="cta">Open Dashboard →</a>
"""
    return _send(to_email, f"Your Antigravity summary — {month}", _base_template(content))


# ── Cancellation ──────────────────────────────────────────────────────────────
def send_cancellation_email(to_email: str, access_until=None) -> bool:
    access_str = str(access_until.date()) if access_until else "the end of your billing period"
    content = f"""
<h2>Your subscription has been cancelled</h2>
<p>No guilt, no pressure. Your cancellation has been processed.</p>
<p><strong>Your access continues until {access_str}.</strong> You'll continue to receive the morning digest and all Pro features until then.</p>
<p>Your account stays active. You can rejoin anytime — everything will be exactly where you left it.</p>
<p style="color:#555; font-size:13px">If there's something we could have done better, we'd genuinely like to know. Reply to this email.</p>
"""
    return _send(to_email, f"Your access continues until {access_str}", _base_template(content))


# ── Payment failed ────────────────────────────────────────────────────────────
def send_payment_failed_email(to_email: str) -> bool:
    content = """
<h2>Your payment didn't go through</h2>
<p>We tried to process your subscription renewal but the payment failed.</p>
<p>This can happen if your card expired, had insufficient balance, or was blocked by your bank.</p>
<p><strong>To continue your access:</strong></p>
<ol>
  <li>Go to your account settings</li>
  <li>Update your payment method</li>
  <li>Your subscription will renew automatically</li>
</ol>
<a href="https://antigravity.in/dashboard" class="cta">Update Payment Method →</a>
<p style="color:#555; font-size:13px">Your access is still active for now. Please update within 7 days to avoid interruption.</p>
"""
    return _send(to_email, "Your payment failed — please update your payment method", _base_template(content))
