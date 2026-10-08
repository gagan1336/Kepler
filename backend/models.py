"""
KEPLER -- SQLAlchemy ORM Models
SQLite-compatible (local dev) + PostgreSQL-compatible (production).
Uses JSON instead of JSONB, String instead of PostgreSQL UUID.
"""
import uuid
from datetime import datetime, date
from sqlalchemy import (
    Column, String, Boolean, DateTime, Date, Text, Integer,
    ForeignKey, Float, Index, func, JSON,
)
from sqlalchemy.orm import relationship
from database import Base


def gen_uuid():
    return str(uuid.uuid4())


# ── Users ─────────────────────────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(Text, nullable=True)  # nullable for OAuth / Supabase users
    supabase_id = Column(String(255), nullable=True, unique=True, index=True)  # Supabase Auth UUID
    plan = Column(String(20), default="free", nullable=False)
    razorpay_subscription_id = Column(String(255), nullable=True)
    telegram_id = Column(String(100), nullable=True)
    trial_end_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    google_id = Column(String(255), nullable=True, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    content_logs = relationship("ContentLog", back_populates="user", cascade="all, delete-orphan")


# ── Daily Digests ─────────────────────────────────────────────────────────────
class DailyDigest(Base):
    __tablename__ = "daily_digests"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    date = Column(Date, unique=True, nullable=False, index=True)
    items = Column(JSON, nullable=False, default=list)
    market_mood = Column(String(20), nullable=True)   # BULLISH / BEARISH / NEUTRAL
    status = Column(String(20), default="published", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ── Breakout Watchlist ────────────────────────────────────────────────────────
class BreakoutWatchlist(Base):
    __tablename__ = "breakout_watchlist"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    date = Column(Date, nullable=False, index=True)
    symbol = Column(String(20), nullable=False)
    company_name = Column(String(255), nullable=True)
    setup_description = Column(Text, nullable=True)
    technical_data = Column(JSON, nullable=True)   # RSI, EMA20/50, vol_ratio, etc.
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ── Sector Reports ────────────────────────────────────────────────────────────
class SectorReport(Base):
    __tablename__ = "sector_reports"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    date = Column(Date, nullable=False, index=True)
    sector_name = Column(String(100), nullable=True)
    content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ── Subscriptions ─────────────────────────────────────────────────────────────
class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    plan = Column(String(20), nullable=False)
    razorpay_subscription_id = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False)   # active / cancelled / expired
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    invoice_url = Column(Text, nullable=True)     # GST invoice PDF URL
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="subscriptions")


# ── Content Log ───────────────────────────────────────────────────────────────
class ContentLog(Base):
    __tablename__ = "content_log"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    content_type = Column(String(50), nullable=False)   # digest / breakout / sector / ipo / deepdive
    content_id = Column(String(100), nullable=True)
    viewed_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    user = relationship("User", back_populates="content_logs")


# ── IPO Briefs ────────────────────────────────────────────────────────────────
class IPOBrief(Base):
    __tablename__ = "ipo_briefs"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    company_name = Column(String(255), nullable=False)
    open_date = Column(Date, nullable=True)
    close_date = Column(Date, nullable=True)
    price_band = Column(String(50), nullable=True)
    industry = Column(String(100), nullable=True)
    content = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ── Deep Dives ────────────────────────────────────────────────────────────────
class DeepDive(Base):
    __tablename__ = "deep_dives"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=True)          # Legacy plain-text (kept for compat)
    sections = Column(JSON, nullable=True)         # Structured sections array (new)
    tier = Column(String(20), default="elite", nullable=False)  # elite only
    summary = Column(Text, nullable=True)          # teaser for pro users
    # Stock-specific fields
    symbol = Column(String(20), nullable=True, index=True)        # NSE symbol e.g. "RELIANCE"
    sector = Column(String(100), nullable=True)
    verdict = Column(String(10), nullable=True)    # BUY / HOLD / AVOID
    risk_rating = Column(String(10), nullable=True)  # LOW / MEDIUM / HIGH
    price_target_12m = Column(Float, nullable=True)
    metrics_snapshot = Column(JSON, nullable=True) # PE, ROE, D/E, mktcap etc at time of writing
    tags = Column(JSON, nullable=True, default=list)  # e.g. ["largecap", "banking", "value"]
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ── Market Updates (GST/RBI/SEBI/TAX/POLICY) ─────────────────────────────────
class MarketUpdate(Base):
    __tablename__ = "market_updates"

    id = Column(String(36), primary_key=True, default=gen_uuid)
    title = Column(String(500), nullable=False)
    update_type = Column(String(20), nullable=False)  # GST / RBI / SEBI / TAX / POLICY / OTHER
    summary = Column(Text, nullable=True)
    effective_date = Column(Date, nullable=True)
    affected_entities = Column(JSON, nullable=True, default=list)  # sectors/stocks
    importance = Column(String(10), default="MEDIUM", nullable=False)  # HIGH / MEDIUM / LOW
    source = Column(String(100), nullable=True)
    source_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


# ── Explicit indexes (only for columns that don't already have index=True) ────
# User.email, DailyDigest.date, BreakoutWatchlist.date, SectorReport.date
# already have index=True on the column definition — no need to duplicate.
Index("ix_market_updates_type", MarketUpdate.update_type)
Index("ix_market_updates_created", MarketUpdate.created_at)


# ── Stock Signals (Manual Chart Research) ─────────────────────────────────────
class StockSignal(Base):
    __tablename__ = "stock_signals"

    id               = Column(String(36), primary_key=True, default=gen_uuid)
    symbol           = Column(String(20),  nullable=False)                    # NSE symbol e.g. "RELIANCE"
    title            = Column(String(255), nullable=False)                    # e.g. "Bullish Cup & Handle breakout"
    description      = Column(Text,        nullable=True)                     # Analyst notes on the setup
    timeframe        = Column(String(20),  nullable=True)                     # "Daily" / "Weekly" / "15m" etc.
    signal_type      = Column(String(10),  nullable=False, default="NEUTRAL") # BULLISH / BEARISH / NEUTRAL
    support          = Column(Float,       nullable=True)                     # Key support level ₹
    resistance       = Column(Float,       nullable=True)                     # Key resistance level ₹
    target           = Column(Float,       nullable=True)                     # Price target ₹
    stoploss         = Column(Float,       nullable=True)                     # Stop loss level ₹
    image_filename   = Column(String(255), nullable=False)                    # Stored filename on disk
    plan_required    = Column(String(20),  nullable=False, default="pro")     # free / pro / elite
    is_published     = Column(Boolean,     default=True,   nullable=False)
    created_at       = Column(DateTime,    default=datetime.utcnow, nullable=False)

Index("ix_stock_signals_created", StockSignal.created_at)
Index("ix_stock_signals_symbol",  StockSignal.symbol)  # single definition — no index=True on column


# -- AI Quota Tracking -------------------------------------------------------
class AIQuota(Base):
    """Per-user, per-day, per-endpoint AI call counter for Gemini quota enforcement."""
    __tablename__ = "ai_quotas"

    id           = Column(String(36), primary_key=True, default=gen_uuid)
    user_id      = Column(String(36), ForeignKey("users.id"), nullable=False)
    quota_date   = Column(Date, nullable=False)
    endpoint     = Column(String(50), nullable=False)
    call_count   = Column(Integer, nullable=False, default=0)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user         = relationship("User")


Index("ix_ai_quotas_lookup", AIQuota.user_id, AIQuota.quota_date, AIQuota.endpoint)


# -- Audit Log ---------------------------------------------------------------
class AuditLog(Base):
    """Append-only security event trail. Never updated, only inserted."""
    __tablename__ = "audit_logs"

    id           = Column(String(36), primary_key=True, default=gen_uuid)
    user_id      = Column(String(36), ForeignKey("users.id"), nullable=True)
    user_email   = Column(String(255), nullable=True)
    event        = Column(String(100), nullable=False)
    path         = Column(String(500), nullable=True)
    ip_address   = Column(String(45), nullable=True)
    details      = Column(JSON, nullable=True, default=dict)
    success      = Column(Boolean, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow, nullable=False)


Index("ix_audit_logs_user",    AuditLog.user_id)
Index("ix_audit_logs_event",   AuditLog.event)
Index("ix_audit_logs_created", AuditLog.created_at)


# -- Push Tokens -------------------------------------------------------------
class PushToken(Base):
    """Expo push notification tokens, one per user+device pair."""
    __tablename__ = "push_tokens"

    id         = Column(String(36), primary_key=True, default=gen_uuid)
    user_id    = Column(String(36), ForeignKey("users.id"), nullable=False)
    token      = Column(String(255), nullable=False, unique=True)
    platform   = Column(String(10), nullable=True)
    is_active  = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user       = relationship("User")


Index("ix_push_tokens_user", PushToken.user_id)
