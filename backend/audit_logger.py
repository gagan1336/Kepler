"""
ANTIGRAVITY — Audit Logging
Append-only security event trail stored in PostgreSQL.

Events are written synchronously (fast) using a fire-and-forget pattern on failure.
Never raises exceptions — audit logging must never break the main request flow.

Event naming convention:  category.action
Examples:
  auth.login_success, auth.login_failure
  admin.signal_upload, admin.trigger_news_pipeline
  payment.webhook_received, payment.subscription_activated
  security.quota_exceeded, security.rate_limited
  content.deepdive_viewed, content.deepdive_generate
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from loguru import logger
from sqlalchemy.orm import Session

from models import AuditLog


def audit(
    db: Session,
    event: str,
    *,
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    path: Optional[str] = None,
    ip_address: Optional[str] = None,
    details: Optional[dict] = None,
    success: Optional[bool] = None,
) -> None:
    """
    Write a security event to the audit log.

    Never raises. If DB write fails, falls back to structured logger output.

    Args:
        db: SQLAlchemy session (will be committed immediately)
        event: dot-separated event name, e.g. "admin.signal_upload"
        user_id: The user's internal UUID (None for unauthenticated events)
        user_email: User email (denormalized for readability)
        path: The API path that triggered the event
        ip_address: Client IP address
        details: Any extra JSON-serializable context
        success: True=success, False=failure/rejection, None=neutral
    """
    try:
        entry = AuditLog(
            user_id=user_id,
            user_email=user_email,
            event=event,
            path=path,
            ip_address=ip_address,
            details=details or {},
            success=success,
        )
        db.add(entry)
        db.commit()
    except Exception as exc:
        # Never let audit logging break the main request
        logger.error(
            f"[AUDIT WRITE FAILED] event={event} user={user_email} "
            f"path={path} success={success} — {exc}"
        )
        try:
            db.rollback()
        except Exception:
            pass

    # Also emit as structured log for external SIEM/log aggregator
    _level = "WARNING" if success is False else "INFO"
    logger.log(
        _level,
        f"[AUDIT] event={event} user={user_email or 'anonymous'} "
        f"ip={ip_address} path={path} success={success} details={details}",
    )


def audit_admin_action(
    db: Session,
    event: str,
    user,          # User ORM object
    request,       # FastAPI Request
    details: Optional[dict] = None,
) -> None:
    """Convenience wrapper for admin action audit events."""
    audit(
        db,
        event,
        user_id=user.id,
        user_email=user.email,
        path=str(request.url.path),
        ip_address=_get_ip(request),
        details=details,
        success=True,
    )


def audit_payment_event(
    db: Session,
    event: str,
    *,
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    payment_id: Optional[str] = None,
    amount: Optional[float] = None,
    plan: Optional[str] = None,
    success: Optional[bool] = None,
) -> None:
    """Convenience wrapper for payment audit events."""
    audit(
        db,
        event,
        user_id=user_id,
        user_email=user_email,
        details={
            "payment_id": payment_id,
            "amount": amount,
            "plan": plan,
        },
        success=success,
    )


def audit_security_event(
    db: Session,
    event: str,
    *,
    request,
    user=None,
    details: Optional[dict] = None,
) -> None:
    """Convenience wrapper for security-relevant events (quota exceeded, rate limited, etc.)."""
    audit(
        db,
        event,
        user_id=user.id if user else None,
        user_email=user.email if user else None,
        path=str(request.url.path),
        ip_address=_get_ip(request),
        details=details,
        success=False,
    )


def _get_ip(request) -> str:
    """Extract real client IP, respecting X-Forwarded-For from reverse proxy."""
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        # Take the first IP (the original client), not the proxy chain
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
