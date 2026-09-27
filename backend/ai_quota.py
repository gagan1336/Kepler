"""
KEPLER -- AI Quota Enforcement
Prevents per-user Gemini API cost abuse by tracking daily call counts.

Quotas (calls per day):
  - free:  0  (no AI access)
  - pro:   10 per endpoint group
  - elite: 50 per endpoint group
  - admin: unlimited
"""
from datetime import date
from typing import Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session
from loguru import logger

from models import AIQuota, User
from config import settings


# ── Daily limits per plan ─────────────────────────────────────────────────────
_QUOTAS: dict[str, dict[str, int]] = {
    # endpoint_group -> {plan -> daily_limit}
    "deepdive": {
        "free":  0,
        "pro":   0,   # pro can view but not generate
        "elite": 5,   # 5 AI deep dive generations per day
    },
    "swing_scan": {
        "free":  0,
        "pro":   3,
        "elite": 20,
    },
    "ml_radar": {
        "free":  0,
        "pro":   10,
        "elite": 30,
    },
    "ml_score": {
        "free":  0,
        "pro":   20,
        "elite": 60,
    },
    "news_pipeline": {
        "free":  0,
        "pro":   0,
        "elite": 3,
    },
    "correlation": {
        "free":  0,
        "pro":   2,
        "elite": 10,
    },
}


def check_and_increment_quota(
    db: Session,
    user: User,
    endpoint_group: str,
    admin_email: str = "",
) -> None:
    """
    Check if the user has remaining quota for today.
    Increments the counter atomically.
    Raises HTTP 429 if over the daily limit.

    Args:
        db: SQLAlchemy session
        user: The authenticated User object
        endpoint_group: One of the keys in _QUOTAS (e.g. "ml_radar")
        admin_email: The admin email from settings (unlimited quota)

    Raises:
        HTTPException(429): If daily quota exceeded
    """
    # Admins are never quota-limited
    if admin_email and user.email.lower() == admin_email.strip().lower():
        return

    plan = user.plan or "free"
    quota_limits = _QUOTAS.get(endpoint_group, {})
    daily_limit = quota_limits.get(plan, 0)

    # Free plan or unknown endpoint: no AI access at all
    if daily_limit == 0:
        raise HTTPException(
            status_code=403,
            detail=f"Your {plan} plan does not include AI-powered {endpoint_group} access. Upgrade to unlock.",
        )

    today = date.today()

    # Get or create today's quota record
    quota = (
        db.query(AIQuota)
        .filter(
            AIQuota.user_id == user.id,
            AIQuota.quota_date == today,
            AIQuota.endpoint == endpoint_group,
        )
        .first()
    )

    if quota is None:
        quota = AIQuota(
            user_id=user.id,
            quota_date=today,
            endpoint=endpoint_group,
            call_count=0,
        )
        db.add(quota)

    if quota.call_count >= daily_limit:
        logger.warning(
            f"AI quota exceeded: user={user.email} plan={plan} "
            f"endpoint={endpoint_group} count={quota.call_count}/{daily_limit}"
        )
        raise HTTPException(
            status_code=429,
            detail=(
                f"Daily AI limit reached for {endpoint_group} "
                f"({quota.call_count}/{daily_limit} calls used). "
                f"Resets at midnight UTC."
            ),
        )

    # Increment and commit
    quota.call_count += 1
    db.commit()

    remaining = daily_limit - quota.call_count
    logger.debug(
        f"AI quota used: user={user.email} endpoint={endpoint_group} "
        f"{quota.call_count}/{daily_limit} ({remaining} remaining)"
    )


def get_quota_status(db: Session, user: User) -> dict:
    """Return a summary of the user's AI quota usage for today."""
    today = date.today()
    plan = user.plan or "free"
    result = {}

    for endpoint_group, limits in _QUOTAS.items():
        daily_limit = limits.get(plan, 0)
        quota = (
            db.query(AIQuota)
            .filter(
                AIQuota.user_id == user.id,
                AIQuota.quota_date == today,
                AIQuota.endpoint == endpoint_group,
            )
            .first()
        )
        used = quota.call_count if quota else 0
        result[endpoint_group] = {
            "used": used,
            "limit": daily_limit,
            "remaining": max(0, daily_limit - used),
            "exhausted": used >= daily_limit if daily_limit > 0 else True,
        }

    return {"date": today.isoformat(), "plan": plan, "quotas": result}
