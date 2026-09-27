"""
KEPLER — FastAPI Main Application
All API endpoints: auth, content, subscriptions, public, webhooks.
Rate limiting, CORS, error handling all configured.
"""
import hashlib
import hmac
import json
import uuid
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any

import razorpay
import os
import shutil
from pathlib import Path
from fastapi import (
    FastAPI, Depends, HTTPException, Request, status,
    BackgroundTasks, Query, UploadFile, File, Form,
)
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from pydantic import BaseModel, EmailStr
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import func, text
from sqlalchemy.orm import Session
import resend

from config import settings
from database import get_db, init_db
from models import (
    User, DailyDigest, BreakoutWatchlist, SectorReport,
    Subscription, ContentLog, IPOBrief, DeepDive, MarketUpdate,
    StockSignal,
)
from auth import (
    hash_password, get_user_by_email,
    get_current_user, get_current_user_optional, require_plan,
)

# ── App setup ─────────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="KEPLER API",
    description="AI-powered market intelligence platform for Indian traders",
    version="1.0.0",
    docs_url="/docs" if not settings.is_production else None,
    redoc_url=None,
)

# ── Static files — serves uploaded signal chart images ────────────────────────
_STATIC_DIR = Path(__file__).parent / "static"
_SIGNALS_DIR = _STATIC_DIR / "signals"
_SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

# ── Stock universe: load complete NSE list at startup ──────────────────────────
import stock_universe as _su
import threading

def _bg_load_universe():
    try:
        _su.load_universe()
        logger.info(f"✅ Stock universe loaded: {_su.universe_size()} stocks")
    except Exception as e:
        logger.warning(f"Stock universe background load failed: {e}")

threading.Thread(target=_bg_load_universe, daemon=True, name="UniverseLoader").start()



app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Razorpay client
rp_client = razorpay.Client(
    auth=(settings.razorpay_key_id, settings.razorpay_key_secret)
) if settings.razorpay_key_id else None

# Resend
resend.api_key = settings.resend_api_key

# Plan IDs (populated on startup)
RAZORPAY_PLAN_IDS: Dict[str, str] = {}

# ── NaN-safe JSON encoder ──────────────────────────────────────────────────────
# yfinance often returns NaN/Infinity for illiquid/SME stocks.
# Python's json module raises ValueError on these, crashing the response.
# Fix: override FastAPI's default encoder to convert them to null.
import math
import json as _json
from starlette.responses import JSONResponse as _BaseJSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as _StarletteRequest


def _sanitize_nan(obj):
    """Recursively replace NaN/Inf floats with None for JSON safety."""
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize_nan(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_nan(v) for v in obj]
    return obj


class NaNSafeJSONResponse(_BaseJSONResponse):
    """JSONResponse that converts NaN/Infinity to null."""
    def render(self, content) -> bytes:
        return _json.dumps(
            _sanitize_nan(content),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")


# Patch the app's default response class so ALL endpoints use it
from fastapi.routing import APIRoute as _APIRoute
_APIRoute.get_response_class = lambda self: NaNSafeJSONResponse  # type: ignore
app.router.default_response_class = NaNSafeJSONResponse




# ═══════════════════════════════════════════════════════════════════════════════
# PYDANTIC SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


class RefreshRequest(BaseModel):
    refresh_token: str


class GoogleAuthRequest(BaseModel):
    access_token: str  # Google access token from frontend OAuth flow


class UserResponse(BaseModel):
    id: str
    email: str
    plan: str
    trial_end_date: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class SubscriptionCreateRequest(BaseModel):
    plan: str   # pro_monthly | pro_annual | elite_monthly | elite_annual


class IPOCreateRequest(BaseModel):
    company_name: str
    open_date: date
    close_date: date
    price_band: str
    industry: str


# ═══════════════════════════════════════════════════════════════════════════════
# STARTUP / SHUTDOWN
# ═══════════════════════════════════════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 KEPLER API starting up...")
    try:
        init_db()
        logger.info("✅ Database connected")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")

    # Create Razorpay plans if keys are set
    if rp_client and settings.razorpay_key_id:
        await create_razorpay_plans()

    # Start APScheduler (all pipeline jobs)
    try:
        from scheduler import start_scheduler
        start_scheduler()
        logger.info("✅ Scheduler started")
    except Exception as e:
        logger.error(f"❌ Scheduler failed to start: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 KEPLER API shutting down...")
    try:
        from scheduler import stop_scheduler
        stop_scheduler()
    except Exception:
        pass


async def create_razorpay_plans():
    """Create the 4 subscription plans on Razorpay if they don't exist."""
    plans_config = [
        {"key": "pro_monthly",    "name": "KEPLER Pro Monthly",   "amount": 79900,  "period": "monthly",  "interval": 1},
        {"key": "pro_annual",     "name": "KEPLER Pro Annual",    "amount": 749900, "period": "yearly",   "interval": 1},
        {"key": "elite_monthly",  "name": "KEPLER Elite Monthly", "amount": 199900, "period": "monthly",  "interval": 1},
        {"key": "elite_annual",   "name": "KEPLER Elite Annual",  "amount": 1799900,"period": "yearly",   "interval": 1},
    ]
    for plan in plans_config:
        try:
            rp_plan = rp_client.plan.create({
                "period": plan["period"],
                "interval": plan["interval"],
                "item": {
                    "name": plan["name"],
                    "amount": plan["amount"],
                    "currency": "INR",
                },
            })
            RAZORPAY_PLAN_IDS[plan["key"]] = rp_plan["id"]
            logger.info(f"Razorpay plan ready: {plan['name']} → {rp_plan['id']}")
        except Exception as e:
            logger.warning(f"Could not create Razorpay plan {plan['name']}: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/health")
def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH ENDPOINTS
# Register / Login / Google OAuth are now handled by Supabase Auth on the frontend.
# The backend only needs /auth/me to fetch / upsert the local user profile.
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/auth/me")
def get_me(current_user: User = Depends(get_current_user)):
    """Return the current authenticated user's profile. Creates the local record on first call."""
    return _user_dict(current_user)


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/public/stats")
@limiter.limit("30/minute")
def public_stats(request: Request, db: Session = Depends(get_db)):
    """Platform stats — shown on homepage."""
    total_members = db.query(func.count(User.id)).scalar() or 0
    pro_count = db.query(func.count(User.id)).filter(User.plan == "pro").scalar() or 0
    elite_count = db.query(func.count(User.id)).filter(User.plan == "elite").scalar() or 0

    PRO_SEATS_TOTAL = 500
    ELITE_SEATS_TOTAL = 100
    ELITE_WAITLIST_FAKE = max(0, elite_count - ELITE_SEATS_TOTAL)

    return {
        "total_members": total_members,
        "pro_seats_remaining": max(0, PRO_SEATS_TOTAL - pro_count),
        "elite_seats_remaining": max(0, ELITE_SEATS_TOTAL - elite_count),
        "elite_waitlist_count": ELITE_WAITLIST_FAKE,
    }


@app.get("/public/sample")
@limiter.limit("30/minute")
def public_sample(request: Request, db: Session = Depends(get_db)):
    """3 best past digests + 1 sector report — no auth required."""
    digests = (
        db.query(DailyDigest)
        .filter(DailyDigest.status == "published")
        .order_by(DailyDigest.date.desc())
        .limit(3)
        .all()
    )
    sector = (
        db.query(SectorReport)
        .order_by(SectorReport.date.desc())
        .first()
    )

    # Use hardcoded samples if DB is empty (freshly deployed)
    digest_data = [_digest_dict(d) for d in digests] if digests else _sample_digests()
    sector_data = _sector_dict(sector) if sector else _sample_sector()

    return {"digests": digest_data, "sector_report": sector_data}


# ═══════════════════════════════════════════════════════════════════════════════
# CONTENT ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/digest/today")
def digest_today(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Today's digest. Free users get first 3 items only."""
    today = date.today()
    digest = db.query(DailyDigest).filter(DailyDigest.date == today).first()

    if not digest:
        # Try yesterday
        yesterday = today - timedelta(days=1)
        digest = db.query(DailyDigest).filter(DailyDigest.date == yesterday).first()

    if not digest:
        raise HTTPException(status_code=404, detail="No digest available yet. Check back after 8 AM IST.")

    items = digest.items or []
    is_restricted = current_user.plan == "free"
    visible_items = items[:3] if is_restricted else items
    blurred_count = max(0, len(items) - 3) if is_restricted else 0

    # Log content view
    _log_content_view(db, current_user.id, "digest", digest.id)

    return {
        "date": str(digest.date),
        "market_mood": digest.market_mood,
        "items": visible_items,
        "total_items": len(items),
        "blurred_count": blurred_count,
        "is_restricted": is_restricted,
    }


@app.get("/digest/history")
def digest_history(
    limit: int = Query(default=30, le=90),
    current_user: User = Depends(require_plan("pro")),
    db: Session = Depends(get_db),
):
    """Last N digests — pro/elite only."""
    digests = (
        db.query(DailyDigest)
        .filter(DailyDigest.status == "published")
        .order_by(DailyDigest.date.desc())
        .limit(limit)
        .all()
    )
    return [_digest_dict(d) for d in digests]


@app.get("/breakout/today")
def breakout_today(
    current_user: User = Depends(require_plan("pro")),
    db: Session = Depends(get_db),
):
    """Today's breakout watchlist — pro/elite only."""
    today = date.today()
    breakouts = (
        db.query(BreakoutWatchlist)
        .filter(BreakoutWatchlist.date == today)
        .order_by(BreakoutWatchlist.created_at.desc())
        .all()
    )
    if not breakouts:
        # Try last available
        last = (
            db.query(BreakoutWatchlist)
            .order_by(BreakoutWatchlist.date.desc())
            .first()
        )
        if last:
            breakouts = db.query(BreakoutWatchlist).filter(
                BreakoutWatchlist.date == last.date
            ).all()

    return [_breakout_dict(b) for b in breakouts]


@app.get("/breakout/stats")
def breakout_stats(
    days: int = Query(default=90, le=180, ge=30),
    current_user: User = Depends(require_plan("pro")),
    db: Session = Depends(get_db),
):
    """Historical backtesting win rates for the breakout scanner — pro/elite only."""
    from backtesting import calculate_breakout_stats
    try:
        stats = calculate_breakout_stats(db, days_back=days)
        return stats
    except Exception as e:
        logger.error(f"Backtesting stats failed: {e}")
        raise HTTPException(status_code=500, detail="Could not calculate stats")


@app.get("/sector/latest")
def sector_latest(
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """Latest sector report — visible to all users."""
    report = db.query(SectorReport).order_by(SectorReport.date.desc()).first()
    if not report:
        raise HTTPException(status_code=404, detail="No sector report available yet.")
    return _sector_dict(report)


@app.get("/sector/history")
def sector_history(
    limit: int = Query(default=12, le=52),
    current_user: User = Depends(require_plan("pro")),
    db: Session = Depends(get_db),
):
    """Sector report history — pro/elite only."""
    reports = (
        db.query(SectorReport)
        .order_by(SectorReport.date.desc())
        .limit(limit)
        .all()
    )
    return [_sector_dict(r) for r in reports]


# ── Live Market News Endpoints ─────────────────────────────────────────────────

@app.get("/news/live")
@limiter.limit("60/minute")
def news_live(
    request: Request,
    category: Optional[str] = Query(default=None, description="ALL, BREAKING, MARKETS, STOCKS, RBI, SEBI, GST_TAX, IPO, GLOBAL"),
    impact:   Optional[str] = Query(default=None, description="HIGH, MEDIUM, LOW"),
    limit:    int            = Query(default=50, le=100),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Live market news from 14 RSS feeds — auto-refreshed every 10 minutes.
    Returns articles scored for market impact and categorized into 8 buckets.
    Public endpoint — no auth required.
    """
    try:
        from news_live import get_live_news
        result = get_live_news(category=category, impact=impact, limit=limit)
        return NaNSafeJSONResponse(content=result)
    except Exception as e:
        logger.error(f"Live news error: {e}")
        raise HTTPException(status_code=500, detail=f"News fetch failed: {str(e)[:120]}")


@app.get("/news/live/categories")
def news_live_categories(request: Request):
    """Available news categories with metadata."""
    from news_live import CATEGORY_META
    return {"categories": CATEGORY_META}


@app.post("/news/live/refresh")
@limiter.limit("5/minute")
def news_live_refresh(
    request: Request,
    current_user: User = Depends(require_plan("pro")),
):
    """Force refresh the live news cache (Pro only). Returns fresh articles."""
    try:
        from news_live import get_live_news
        result = get_live_news(force_refresh=True)
        return NaNSafeJSONResponse(content=result)
    except Exception as e:
        logger.error(f"News refresh error: {e}")
        raise HTTPException(status_code=500, detail="Refresh failed")


# ── Global Markets Pulse Endpoint ──────────────────────────────────────────────

@app.get("/markets/global")
@limiter.limit("60/minute")
def markets_global(request: Request, force_refresh: bool = Query(default=False)):
    """
    Live Global Markets Pulse (Gift Nifty, US, Asia, Europe, Commodities, Forex).
    Public endpoint, 5-minute cache.
    """
    try:
        from global_markets import get_global_markets
        result = get_global_markets(force_refresh=force_refresh)
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        return NaNSafeJSONResponse(content=result)
    except Exception as e:
        logger.error(f"Global markets fetch error: {e}")
        raise HTTPException(status_code=500, detail="Global markets fetch failed")


@app.get("/news/market-updates")
@limiter.limit("30/minute")
def market_updates(
    request: Request,
    limit: int = Query(default=20, le=50),
    update_type: Optional[str] = Query(default=None, description="Filter: GST, RBI, SEBI, TAX, POLICY"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Latest important market updates: GST council decisions, RBI circulars,
    SEBI notifications, tax changes, economic data releases.
    Public endpoint — authenticated users get more detail.
    """
    query = db.query(MarketUpdate).order_by(MarketUpdate.created_at.desc())
    if update_type:
        query = query.filter(MarketUpdate.update_type == update_type.upper())
    updates = query.limit(limit).all()

    if not updates:
        # Return curated sample data if DB is empty
        return _sample_market_updates()

    return [
        {
            "id": u.id,
            "title": u.title,
            "update_type": u.update_type,
            "summary": u.summary,
            "effective_date": str(u.effective_date) if u.effective_date else None,
            "affected_entities": u.affected_entities,
            "importance": u.importance,
            "source": u.source,
            "source_url": u.source_url,
            "created_at": str(u.created_at),
        }
        for u in updates
    ]


@app.get("/news/market-updates/types")
def market_update_types():
    """Available market update categories."""
    return {
        "types": [
            {"id": "GST",    "label": "GST Council",       "icon": "📋", "desc": "GST rates, council decisions, e-invoicing"},
            {"id": "RBI",    "label": "RBI Circulars",     "icon": "🏦", "desc": "RBI policy, circulars, forex, banking rules"},
            {"id": "SEBI",   "label": "SEBI Regulations",  "icon": "⚖️", "desc": "SEBI circulars, exchange notifications"},
            {"id": "TAX",    "label": "Tax Updates",       "icon": "💰", "desc": "Income tax, TDS, advance tax, CBDT"},
            {"id": "POLICY", "label": "Govt Policy",       "icon": "🏛️", "desc": "Ministry announcements, PLI, budget"},
            {"id": "OTHER",  "label": "Other",             "icon": "📌", "desc": "Economic data, IMF/World Bank, global macro"},
        ]
    }


# ═══════════════════════════════════════════════════════════════════════════════
# IPO INTELLIGENCE HUB
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/ipo/hub")
@limiter.limit("20/minute")
def ipo_hub(request: Request, force_refresh: bool = Query(default=False)):
    """
    Live IPO Intelligence Hub — all upcoming/open/closed/listed IPOs with GMP,
    subscription status, and AI verdict. Public. 30-min cache.
    """
    try:
        from ipo_live import get_ipo_hub
        result = get_ipo_hub(force_refresh=force_refresh)
        return NaNSafeJSONResponse(content=result)
    except Exception as e:
        logger.error(f"IPO Hub error: {e}")
        raise HTTPException(status_code=500, detail="IPO Hub data fetch failed")


@app.get("/ipo/latest")
def ipo_latest(db: Session = Depends(get_db)):
    """Latest IPO brief — visible to all."""
    ipo = db.query(IPOBrief).order_by(IPOBrief.created_at.desc()).first()
    if not ipo:
        raise HTTPException(status_code=404, detail="No IPO brief available.")
    return _ipo_dict(ipo, full=False)


@app.get("/ipo/{ipo_id}")
def ipo_detail(
    ipo_id: str,
    current_user: User = Depends(require_plan("pro")),
    db: Session = Depends(get_db),
):
    """Full IPO analysis — pro/elite only."""
    ipo = db.query(IPOBrief).filter(IPOBrief.id == ipo_id).first()
    if not ipo:
        raise HTTPException(status_code=404, detail="IPO brief not found.")
    return _ipo_dict(ipo, full=True)


@app.post("/ipo/create")
def ipo_create(
    body: IPOCreateRequest,
    current_user: User = Depends(require_plan("elite")),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Trigger IPO analysis — elite only (admin trigger)."""
    background_tasks.add_task(_run_ipo_analysis, body.dict(), db)
    return {"message": "IPO analysis queued"}


def _run_ipo_analysis(data: dict, db: Session):
    try:
        from ipo_analyzer import analyze_ipo
        analyze_ipo(db=db, **data)
    except Exception as e:
        logger.error(f"IPO analysis failed: {e}")


@app.get("/deepdive/list")
def deepdive_list(
    current_user: User = Depends(require_plan("pro")),
    db: Session = Depends(get_db),
):
    """List deep dives — pro/elite see metadata cards. No full content."""
    dives = db.query(DeepDive).order_by(DeepDive.created_at.desc()).all()
    return [
        {
            "id":               d.id,
            "title":            d.title,
            "summary":          d.summary,
            "tier":             d.tier,
            "symbol":           d.symbol,
            "sector":           d.sector,
            "verdict":          d.verdict,
            "risk_rating":      d.risk_rating,
            "price_target_12m": d.price_target_12m,
            "tags":             d.tags or [],
            "metrics_snapshot": d.metrics_snapshot or {},
            "created_at":       str(d.created_at),
        }
        for d in dives
    ]


@app.get("/deepdive/{dive_id}")
def deepdive_detail(
    dive_id: str,
    current_user: User = Depends(require_plan("elite")),
    db: Session = Depends(get_db),
):
    """Full deep dive — elite only. Returns structured sections + all metadata."""
    dive = db.query(DeepDive).filter(DeepDive.id == dive_id).first()
    if not dive:
        raise HTTPException(status_code=404, detail="Deep dive not found.")
    _log_content_view(db, current_user.id, "deepdive", dive_id)
    return {
        "id":               dive.id,
        "title":            dive.title,
        "summary":          dive.summary,
        "content":          dive.content,      # legacy plain-text fallback
        "sections":         dive.sections or [],
        "tier":             dive.tier,
        "symbol":           dive.symbol,
        "sector":           dive.sector,
        "verdict":          dive.verdict,
        "risk_rating":      dive.risk_rating,
        "price_target_12m": dive.price_target_12m,
        "tags":             dive.tags or [],
        "metrics_snapshot": dive.metrics_snapshot or {},
        "created_at":       str(dive.created_at),
    }


class DeepDiveGenerateRequest(BaseModel):
    symbol: str          # NSE ticker e.g. "RELIANCE"
    tier: str = "elite"  # which plan can read this


@app.post("/deepdive/generate")
def deepdive_generate(
    body: DeepDiveGenerateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_plan("elite")),
    db: Session = Depends(get_db),
):
    """
    Trigger AI-powered deep dive generation for an NSE stock — Elite admin only.
    Runs in background; the deep dive is saved to DB when complete.
    Returns a job token immediately.
    """
    symbol = body.symbol.upper().strip().replace(".NS", "")
    if not symbol or len(symbol) > 20:
        raise HTTPException(status_code=400, detail="Invalid symbol")

    # Create a placeholder DeepDive row so frontend can poll / list it
    placeholder = DeepDive(
        title=f"{symbol} — Deep Dive (Generating...)",
        summary="AI is analysing this stock. Check back in ~60 seconds.",
        symbol=symbol,
        tier=body.tier,
        content=None,
        sections=None,
        verdict=None,
    )
    db.add(placeholder)
    db.commit()
    db.refresh(placeholder)
    dive_id = placeholder.id

    def _run_generation(did: str, sym: str, tier: str):
        from database import SessionLocal
        _db = SessionLocal()
        try:
            from deep_dive_generator import generate_deep_dive
            result = generate_deep_dive(sym)

            dive = _db.query(DeepDive).filter(DeepDive.id == did).first()
            if dive:
                dive.title          = result["title"]
                dive.summary        = result["summary"]
                dive.content        = result["content"]
                dive.sections       = result["sections"]
                dive.symbol         = result["symbol"]
                dive.sector         = result["sector"]
                dive.verdict        = result["verdict"]
                dive.risk_rating    = result["risk_rating"]
                dive.price_target_12m = result["price_target_12m"]
                dive.metrics_snapshot = result["metrics_snapshot"]
                dive.tags           = result["tags"]
                dive.tier           = tier
                _db.commit()
                logger.info(f"Deep dive {did} generated for {sym}: verdict={result['verdict']}")
        except Exception as e:
            logger.error(f"Deep dive generation failed for {sym}: {e}")
            # Mark the placeholder as failed
            dive = _db.query(DeepDive).filter(DeepDive.id == did).first()
            if dive:
                dive.title   = f"{sym} — Deep Dive (Generation Failed)"
                dive.summary = f"AI generation failed: {str(e)[:200]}"
                _db.commit()
        finally:
            _db.close()

    background_tasks.add_task(_run_generation, dive_id, symbol, body.tier)
    logger.info(f"Deep dive generation queued: {symbol} by {current_user.email}")
    return {
        "id":      dive_id,
        "symbol":  symbol,
        "message": f"Deep dive generation started for {symbol}. Refresh in ~60-90 seconds.",
    }


@app.get("/dashboard/stats")
def dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Member dashboard statistics."""
    now = datetime.utcnow()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    digests_this_month = (
        db.query(func.count(DailyDigest.id))
        .filter(DailyDigest.created_at >= month_start)
        .scalar() or 0
    )
    sector_reports_this_month = (
        db.query(func.count(SectorReport.id))
        .filter(SectorReport.created_at >= month_start)
        .scalar() or 0
    )
    # Chart analyses approximated by breakout scans published this month
    chart_analyses_this_month = (
        db.query(func.count(BreakoutWatchlist.id))
        .filter(BreakoutWatchlist.created_at >= month_start)
        .scalar() or 0
    )

    # Active subscription
    sub = (
        db.query(Subscription)
        .filter(Subscription.user_id == current_user.id, Subscription.status == "active")
        .order_by(Subscription.created_at.desc())
        .first()
    )

    return {
        "digests_this_month": digests_this_month,
        "chart_analyses_this_month": chart_analyses_this_month,
        "sector_reports_this_month": sector_reports_this_month,
        "member_since": str(current_user.created_at.date()),
        "plan": current_user.plan,
        "trial_ends": str(current_user.trial_end_date.date()) if current_user.trial_end_date else None,
        "next_billing": str(sub.end_date.date()) if sub and sub.end_date else None,
        "invoices": _get_invoices(db, current_user.id),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SUBSCRIPTION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/subscription/create")
def subscription_create(
    body: SubscriptionCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a Razorpay subscription for the user."""
    if not rp_client:
        raise HTTPException(status_code=503, detail="Payment system not configured")

    plan_id = RAZORPAY_PLAN_IDS.get(body.plan)
    if not plan_id:
        raise HTTPException(status_code=400, detail=f"Unknown plan: {body.plan}")

    try:
        rp_sub = rp_client.subscription.create({
            "plan_id": plan_id,
            "customer_notify": 1,
            "total_count": 12 if "monthly" in body.plan else 1,
            "notes": {"user_id": current_user.id, "email": current_user.email},
        })
        return {
            "subscription_id": rp_sub["id"],
            "razorpay_key": settings.razorpay_key_id,
            "plan": body.plan,
        }
    except Exception as e:
        logger.error(f"Razorpay subscription creation failed: {e}")
        raise HTTPException(status_code=500, detail="Could not create subscription")


@app.get("/subscription/status")
def subscription_status(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Current subscription status."""
    sub = (
        db.query(Subscription)
        .filter(Subscription.user_id == current_user.id)
        .order_by(Subscription.created_at.desc())
        .first()
    )
    return {
        "plan": current_user.plan,
        "status": sub.status if sub else "none",
        "start_date": str(sub.start_date) if sub and sub.start_date else None,
        "end_date": str(sub.end_date) if sub and sub.end_date else None,
        "trial_end_date": str(current_user.trial_end_date) if current_user.trial_end_date else None,
    }


@app.post("/subscription/cancel")
def subscription_cancel(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Cancel subscription at period end — one click, no friction."""
    sub = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == current_user.id,
            Subscription.status == "active",
        )
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="No active subscription found")

    # Cancel on Razorpay
    if rp_client and sub.razorpay_subscription_id:
        try:
            rp_client.subscription.cancel(
                sub.razorpay_subscription_id,
                {"cancel_at_cycle_end": 1},
            )
        except Exception as e:
            logger.warning(f"Razorpay cancel call failed: {e}")

    sub.status = "cancelled"
    db.commit()

    # Send cancellation email
    try:
        from email_service import send_cancellation_email
        send_cancellation_email(current_user.email, sub.end_date)
    except Exception as e:
        logger.warning(f"Could not send cancellation email: {e}")

    return {
        "message": "Subscription cancelled. Your access continues until the end of the billing period.",
        "access_until": str(sub.end_date) if sub.end_date else "unknown",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# RAZORPAY WEBHOOK
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/webhooks/razorpay")
async def razorpay_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle all Razorpay webhook events with signature verification."""
    body_bytes = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")

    # Verify signature
    if settings.razorpay_webhook_secret:
        expected = hmac.new(
            key=settings.razorpay_webhook_secret.encode(),
            msg=body_bytes,
            digestmod=hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            logger.warning("Razorpay webhook signature mismatch")
            raise HTTPException(status_code=400, detail="Invalid signature")

    try:
        payload = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    event = payload.get("event")
    entity = payload.get("payload", {}).get("subscription", {}).get("entity", {})

    logger.info(f"Razorpay webhook: {event}")

    if event == "subscription.activated":
        await _handle_subscription_activated(db, entity, payload)
    elif event == "subscription.cancelled":
        await _handle_subscription_cancelled(db, entity)
    elif event == "payment.failed":
        await _handle_payment_failed(db, payload)
    elif event == "subscription.completed":
        await _handle_subscription_cancelled(db, entity)

    return {"status": "ok"}


async def _handle_subscription_activated(db: Session, entity: dict, payload: dict):
    """Upgrade user plan when subscription activates."""
    try:
        notes = entity.get("notes", {})
        user_id = notes.get("user_id")
        rp_sub_id = entity.get("id")
        plan_id = entity.get("plan_id")

        # Map Razorpay plan_id → our plan name
        plan_name = "pro"
        for key, pid in RAZORPAY_PLAN_IDS.items():
            if pid == plan_id:
                plan_name = "elite" if "elite" in key else "pro"
                break

        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"Webhook: user {user_id} not found")
            return

        # Update user plan
        user.plan = plan_name
        user.razorpay_subscription_id = rp_sub_id

        # Upsert subscription record
        start_at = datetime.utcfromtimestamp(entity.get("start_at", datetime.utcnow().timestamp()))
        end_at = datetime.utcfromtimestamp(entity.get("end_at", (datetime.utcnow() + timedelta(days=30)).timestamp()))

        sub = Subscription(
            user_id=user.id,
            plan=plan_name,
            razorpay_subscription_id=rp_sub_id,
            status="active",
            start_date=start_at,
            end_date=end_at,
        )
        db.add(sub)
        db.commit()

        logger.info(f"User {user.email} upgraded to {plan_name}")

        # Trigger Day 1 email
        try:
            from email_service import send_subscription_welcome
            send_subscription_welcome(user.email, plan_name)
        except Exception as e:
            logger.warning(f"Could not send welcome email: {e}")

    except Exception as e:
        logger.error(f"subscription.activated handler error: {e}")


async def _handle_subscription_cancelled(db: Session, entity: dict):
    """Mark subscription cancelled but keep access until period end."""
    try:
        rp_sub_id = entity.get("id")
        sub = db.query(Subscription).filter(
            Subscription.razorpay_subscription_id == rp_sub_id
        ).first()
        if sub:
            sub.status = "cancelled"
            db.commit()
            user = db.query(User).filter(User.id == sub.user_id).first()
            if user:
                try:
                    from email_service import send_cancellation_email
                    send_cancellation_email(user.email, sub.end_date)
                except Exception as e:
                    logger.warning(f"Cancellation email failed: {e}")
    except Exception as e:
        logger.error(f"subscription.cancelled handler error: {e}")


async def _handle_payment_failed(db: Session, payload: dict):
    """Alert admin and email user on payment failure."""
    try:
        payment = payload.get("payload", {}).get("payment", {}).get("entity", {})
        email = payment.get("email", "")
        if email:
            from email_service import send_payment_failed_email
            send_payment_failed_email(email)
    except Exception as e:
        logger.error(f"payment.failed handler error: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def _user_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "plan": user.plan,
        "trial_end_date": str(user.trial_end_date) if user.trial_end_date else None,
        "created_at": str(user.created_at),
    }


def _digest_dict(d: DailyDigest) -> dict:
    return {
        "id": d.id,
        "date": str(d.date),
        "market_mood": d.market_mood,
        "items": d.items,
        "status": d.status,
        "created_at": str(d.created_at),
    }


def _breakout_dict(b: BreakoutWatchlist) -> dict:
    return {
        "id": b.id,
        "date": str(b.date),
        "symbol": b.symbol,
        "company_name": b.company_name,
        "setup_description": b.setup_description,
        "technical_data": b.technical_data,
        "created_at": str(b.created_at),
    }


def _sector_dict(r: SectorReport) -> dict:
    return {
        "id": r.id,
        "date": str(r.date),
        "sector_name": r.sector_name,
        "content": r.content,
        "created_at": str(r.created_at),
    }


def _ipo_dict(ipo: IPOBrief, full: bool = True) -> dict:
    return {
        "id": ipo.id,
        "company_name": ipo.company_name,
        "open_date": str(ipo.open_date) if ipo.open_date else None,
        "close_date": str(ipo.close_date) if ipo.close_date else None,
        "price_band": ipo.price_band,
        "industry": ipo.industry,
        "content": ipo.content if full else (ipo.content[:300] + "..." if ipo.content else None),
        "created_at": str(ipo.created_at),
    }


def _log_content_view(db: Session, user_id: str, content_type: str, content_id: str):
    try:
        log = ContentLog(user_id=user_id, content_type=content_type, content_id=content_id)
        db.add(log)
        db.commit()
    except Exception:
        pass


def _get_invoices(db: Session, user_id: str) -> list:
    subs = (
        db.query(Subscription)
        .filter(Subscription.user_id == user_id, Subscription.invoice_url != None)
        .order_by(Subscription.created_at.desc())
        .all()
    )
    return [
        {"date": str(s.start_date), "plan": s.plan, "url": s.invoice_url}
        for s in subs
    ]


def _sample_digests() -> list:
    """Hardcoded sample digests for freshly deployed instances."""
    return [
        {
            "id": "sample-1",
            "date": "2025-01-15",
            "market_mood": "BULLISH",
            "items": [
                {
                    "title": "RBI MPC Cuts Repo Rate by 25bps to 6.25% — First Cut in 4 Years",
                    "category": "RBI_SEBI",
                    "importance_score": 10,
                    "summary": "The Reserve Bank of India's Monetary Policy Committee voted 4-2 to cut the repo rate (the rate at which RBI lends to banks overnight) by 25 basis points to 6.25%, its first reduction since May 2020. Governor Sanjay Malhotra cited easing inflation at 4.2% and slowing growth at 6.4% GDP as the key reasons. Rate-sensitive sectors — real estate, NBFCs, and banking — are expected to benefit most as borrowing costs fall across the economy.",
                    "affected_sectors": ["Private Banking", "NBFC", "Real Estate", "Auto"],
                    "affected_stocks": ["HDFCBANK", "ICICIBANK", "SBIN", "BAJFINANCE", "DLF"],
                    "sentiment": "BULLISH",
                    "catalyst_type": "POLICY",
                    "time_sensitivity": "TODAY",
                    "source_url": "https://rbi.org.in",
                },
                {
                    "title": "GST Council Slashes Tax on EV Batteries to 5% from 18% — Auto & Energy Sector Boost",
                    "category": "GST",
                    "importance_score": 9,
                    "summary": "The GST Council, chaired by Finance Minister Nirmala Sitharaman, approved a major reduction in GST (Goods and Services Tax) on electric vehicle batteries from 18% to 5%, effective April 1st. This directly lowers the total cost of EVs by approximately ₹30,000-₹80,000 for popular price segments. Tata Motors, M&M, and Ola Electric are the biggest beneficiaries, while the move also boosts battery manufacturers and the broader clean-energy supply chain.",
                    "affected_sectors": ["Auto & EV", "Energy", "Clean Energy"],
                    "affected_stocks": ["TATAMOTORS", "M&M", "EXIDEIND", "AMARON"],
                    "sentiment": "BULLISH",
                    "catalyst_type": "GST",
                    "time_sensitivity": "MEDIUM_TERM",
                    "source_url": "https://gst.gov.in",
                },
                {
                    "title": "TCS Q3 FY25: Net Profit ₹12,380 Crore (+12% YoY), Deal Wins at $10.2 Billion",
                    "category": "RESULT",
                    "importance_score": 9,
                    "summary": "Tata Consultancy Services reported Q3 revenue of ₹63,973 crore, up 5.6% year-on-year, with net profit at ₹12,380 crore — in line with analyst estimates. EBIT margin (operating profit as % of revenue) improved 30 basis points to 24.5%. The highlight was record deal wins of $10.2 billion, with strong momentum in BFSI (banking & financial services) and North America. Management guided for sequential revenue growth acceleration in Q4, a positive signal for the broader IT sector.",
                    "affected_sectors": ["IT Services", "Technology"],
                    "affected_stocks": ["TCS", "INFY", "WIPRO", "HCLTECH"],
                    "sentiment": "BULLISH",
                    "catalyst_type": "EARNINGS",
                    "time_sensitivity": "SHORT_TERM",
                    "source_url": "https://tcs.com",
                },
                {
                    "title": "SEBI Tightens F&O Rules: Minimum Contract Size Raised to ₹15 Lakh",
                    "category": "RBI_SEBI",
                    "importance_score": 8,
                    "summary": "SEBI (Securities and Exchange Board of India) issued a circular raising the minimum lot size for F&O (Futures & Options) contracts from ₹5 lakh to ₹15 lakh, effective January 1st. The move aims to curb retail speculation after a study showed 90% of F&O traders lost money. Trading volumes on NSE may drop 25-35% in the near term, directly impacting brokers like Zerodha, Angel One, and 5Paisa. Long-term, analysts view this as positive for market stability.",
                    "affected_sectors": ["Capital Markets", "Broking"],
                    "affected_stocks": ["ANGELONE", "5PAISA"],
                    "sentiment": "NEUTRAL",
                    "catalyst_type": "REGULATORY",
                    "time_sensitivity": "SHORT_TERM",
                    "source_url": "https://sebi.gov.in",
                },
                {
                    "title": "FII Inflows ₹12,400 Crore in 5 Sessions — Emerging Market Rotation Underway",
                    "category": "MACRO",
                    "importance_score": 8,
                    "summary": "Foreign Institutional Investors (FIIs) have been net buyers of Indian equities for five consecutive sessions, pumping ₹12,400 crore into the market. The inflows are being driven by India's relative strength — GDP growth of 6.4% vs. China's 4.8% — and the recent RBI rate cut making equities more attractive vs. fixed income. Large-cap banking, IT, and consumer stocks have absorbed the bulk of FII buying, supporting index-level outperformance.",
                    "affected_sectors": ["Broad Market", "Large Cap", "Private Banking"],
                    "affected_stocks": [],
                    "sentiment": "BULLISH",
                    "catalyst_type": "MACRO_DATA",
                    "time_sensitivity": "SHORT_TERM",
                    "source_url": "https://nsdl.co.in",
                },
            ],
        }
    ]


def _sample_sector() -> dict:
    return {
        "id": "sample-sector-1",
        "date": "2025-01-14",
        "sector_name": "Banking & Financial Services",
        "content": """**BANKING SECTOR SPOTLIGHT — WEEK OF JANUARY 14, 2025**

**THE HEADLINE**
The banking sector continues to be the most compelling story in Indian markets this week. With the RBI holding rates steady and credit growth running at 14% year-on-year, the setup for private banks looks particularly interesting heading into Q3 results.

**WHAT IS DRIVING IT**
Three factors are converging. First, the rate pause reduces the mark-to-market pressure on bond portfolios that banks carry. Second, deposit mobilisation has improved after the festive season, easing funding costs. Third, asset quality data from recent RBI publications shows gross NPAs at decade-low levels — a structural improvement, not a cyclical one.

**STOCKS WORTH RESEARCHING**
HDFC Bank has been consolidating near its 52-week high after its post-merger integration concerns have begun to fade. ICICI Bank's consistent ROE improvement over the past eight quarters is worth noting. SBI's rural credit book is expanding at a pace that warrants closer attention from investors focused on long-duration stories.

**RISKS TO WATCH**
Global liquidity tightening remains a risk — any unexpected Fed action could trigger FII outflows that would pressure banking stocks disproportionately. Second, unsecured lending growth in the microfinance and personal loan segments is showing early stress signals that regulators are watching. Third, a drought or poor rabi crop could increase rural NPAs in the second half of the fiscal year.

**BROADER CONTEXT**
Banking has historically led market recoveries in India, and the current cycle appears consistent with that pattern. The sector is trading at a modest premium to its 5-year average P/B, which is justifiable given the improved return ratios. The risk-reward for patient, research-driven investors appears balanced.

---
*This analysis is for educational and informational purposes only. Not investment advice. We are not SEBI registered advisers. Please do your own research before making any investment decisions.*""",
        "created_at": "2025-01-14T07:30:00",
    }



def _sample_market_updates() -> list:
    """Curated sample market updates for freshly deployed instances."""
    return [
        {
            "id": "sample-mu-1",
            "title": "GST Council 55th Meeting: EV Battery GST Cut to 5%, Life Insurance Exempted",
            "update_type": "GST",
            "summary": "The 55th GST Council meeting, chaired by Finance Minister Nirmala Sitharaman, announced a reduction in GST on EV batteries from 18% to 5%, effective April 1st 2025. Life insurance premiums are now GST-exempt for policies under ₹5 lakh annual premium. Health insurance premiums for senior citizens are also fully exempted. These changes are expected to boost EV adoption and make insurance more accessible.",
            "effective_date": "2025-04-01",
            "affected_entities": ["Auto & EV", "Insurance", "TATAMOTORS", "STARHEALTH"],
            "importance": "HIGH",
            "source": "GST Council",
            "source_url": "https://gst.gov.in",
            "created_at": "2025-01-15T10:00:00",
        },
        {
            "id": "sample-mu-2",
            "title": "RBI Circular: New TReDS Guidelines for MSME Invoice Financing",
            "update_type": "RBI",
            "summary": "RBI has issued revised guidelines for Trade Receivables Discounting System (TReDS) platforms, enabling MSMEs to finance their invoices at competitive rates. Large corporates with turnover above ₹500 crore are now mandated to onboard TReDS platforms. This opens a ₹40,000 crore annual opportunity for fintech lenders and NBFC-factors. The change takes effect from April 1st, 2025.",
            "effective_date": "2025-04-01",
            "affected_entities": ["NBFC", "Fintech", "MSME", "Banking"],
            "importance": "HIGH",
            "source": "RBI",
            "source_url": "https://rbi.org.in",
            "created_at": "2025-01-14T09:00:00",
        },
        {
            "id": "sample-mu-3",
            "title": "SEBI Circular: Direct Market Access Norms Extended to Algo Trading",
            "update_type": "SEBI",
            "summary": "SEBI has extended Direct Market Access (DMA) norms to cover API-based algorithmic trading by retail investors. Brokers must now register, test, and certify all retail algo strategies. Systems with more than 10 orders per second require SEBI registration. The move provides regulatory clarity for India's rapidly growing retail quant trading community, while ensuring market stability.",
            "effective_date": "2025-03-01",
            "affected_entities": ["Broking", "Fintech", "Capital Markets"],
            "importance": "HIGH",
            "source": "SEBI",
            "source_url": "https://sebi.gov.in",
            "created_at": "2025-01-13T11:00:00",
        },
        {
            "id": "sample-mu-4",
            "title": "CBDT: New TDS Rates on Dividend Income Above ₹5,000 — Effective Immediately",
            "update_type": "TAX",
            "summary": "The Central Board of Direct Taxes (CBDT) has clarified that TDS (Tax Deducted at Source) at 10% will apply on dividend income exceeding ₹5,000 per financial year from any single company. Investors with multiple dividend-paying stocks should note that the ₹5,000 threshold applies per company, not in aggregate. Mutual fund dividends above ₹5,000 will attract 10% TDS from the fund house. No action required unless you need to file Form 15G/15H to avoid TDS deduction.",
            "effective_date": "2025-01-01",
            "affected_entities": ["Equity Investors", "Mutual Funds", "Dividend Stocks"],
            "importance": "MEDIUM",
            "source": "Income Tax India",
            "source_url": "https://incometaxindia.gov.in",
            "created_at": "2025-01-10T08:00:00",
        },
        {
            "id": "sample-mu-5",
            "title": "India CPI Inflation Eases to 4.2% in December — Lowest in 9 Months",
            "update_type": "OTHER",
            "summary": "India's Consumer Price Index (CPI) inflation — the primary metric tracking retail price changes — eased to 4.2% year-on-year in December 2024, from 5.48% in November. Food inflation fell sharply to 4.8% on good kharif harvest arrivals. This is now within RBI's 4% target band (±2%) and strengthens the case for further interest rate cuts. Lower inflation is broadly positive for equity markets, as it reduces input cost pressure for companies and boosts real consumer spending power.",
            "effective_date": None,
            "affected_entities": ["Broad Market", "FMCG", "Banking", "Real Estate"],
            "importance": "HIGH",
            "source": "MOSPI",
            "source_url": "https://mospi.gov.in",
            "created_at": "2025-01-13T17:00:00",
        },
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# STOCK SEARCH ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/stock/search")
@limiter.limit("30/minute")
def stock_search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=30, description="Search query: symbol or company name"),
    limit: int = Query(default=8, le=15),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Autocomplete search for Indian stocks.
    Returns matching symbols + company names from curated NSE list.
    Public endpoint — no auth required.
    """
    try:
        from stock_lookup import search_stocks
        results = search_stocks(q.strip(), limit=limit)
        return {"results": results, "query": q}
    except Exception as e:
        logger.error(f"Stock search error for '{q}': {e}")
        raise HTTPException(status_code=500, detail="Stock search failed")

@app.get("/stock/{symbol}")
@limiter.limit("20/minute")
def stock_detail(
    request: Request,
    symbol: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Full stock detail: live price, fundamentals, shareholding,
    FII/DII data, institutional holders, recent news, analyst verdict.
    Requires login (any plan). Cached 4 hours per symbol.
    """
    symbol = symbol.upper().strip()
    if len(symbol) > 20 or not symbol.replace("-", "").replace("&", "").replace(".", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid symbol format")

    try:
        from stock_lookup import get_stock_detail
        data = get_stock_detail(symbol)
        _log_content_view(db, current_user.id, "stock_search", symbol)
        # Use NaN-safe response to prevent serialization crashes on illiquid stocks
        return NaNSafeJSONResponse(content=data)
    except Exception as e:
        logger.error(f"Stock detail error for '{symbol}': {e}")
        raise HTTPException(status_code=500, detail=f"Could not fetch data for {symbol}")


@app.get("/stock/{symbol}/live")
@limiter.limit("60/minute")
def stock_live_price(
    request: Request,
    symbol: str,
    current_user: User = Depends(get_current_user),
):
    """
    Lightweight real-time price-only endpoint via yfinance fast_info.
    Bypasses the 4-hour full detail cache. Used for live price refresh.
    Requires login (any plan). Rate limited: 60/minute.
    """
    symbol = symbol.upper().strip().replace(".NS", "")
    if len(symbol) > 20 or not symbol.replace("-", "").replace("&", "").replace(".", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid symbol format")
    try:
        from stock_lookup import get_live_price
        data = get_live_price(symbol)
        return NaNSafeJSONResponse(content=data)
    except Exception as e:
        logger.error(f"Live price error for '{symbol}': {e}")
        raise HTTPException(status_code=500, detail=f"Could not fetch live price for {symbol}")



# ═══════════════════════════════════════════════════════════════════════════════
# NEW LISTINGS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/new-listings")
@limiter.limit("20/minute")
def get_new_listings(
    request: Request,
    days: int = Query(default=90, ge=7, le=365, description="Look back this many days"),
    refresh: bool = Query(default=False, description="Force refresh cache"),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Stocks recently listed on NSE and BSE.
    Includes live price, listing date, issue price, and gain since listing.
    Public endpoint — no auth required.
    """
    try:
        from new_listings import fetch_new_listings
        listings = fetch_new_listings(days=days, force_refresh=refresh)
        return {"listings": listings, "count": len(listings), "days": days}
    except Exception as e:
        logger.error(f"New listings fetch error: {e}")
        raise HTTPException(status_code=500, detail="Could not fetch new listings")


# ═══════════════════════════════════════════════════════════════════════════════

class ScreenerFilterRequest(BaseModel):
    min_pe:               Optional[float] = None
    max_pe:               Optional[float] = None
    min_roe:              Optional[float] = None   # e.g. 15 = 15%
    max_de:               Optional[float] = None   # Debt/Equity
    min_market_cap_cr:    Optional[float] = None   # Market cap in Crore
    max_market_cap_cr:    Optional[float] = None
    min_div_yield:        Optional[float] = None   # e.g. 2 = 2%
    min_revenue_growth:   Optional[float] = None   # YoY %
    min_profit_margin:    Optional[float] = None   # %
    max_pb:               Optional[float] = None
    sectors:              Optional[List[str]] = None
    sort_by:              str = "market_cap_cr"
    sort_desc:            bool = True
    limit:                int = 30


@app.get("/screener/presets")
@limiter.limit("30/minute")
def screener_presets(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Returns list of available preset screens (most active, gainers, value, etc.).
    Public endpoint — no auth required.
    """
    from yf_screener import get_preset_list
    return {"presets": get_preset_list()}


@app.get("/screener/preset/{screen_name}")
@limiter.limit("15/minute")
def screener_run_preset(
    request: Request,
    screen_name: str,
    limit: int = Query(default=25, le=100),
    current_user: User = Depends(get_current_user),
):
    """
    Run a predefined Yahoo Finance screen (global equities).
    Requires login. Results cached 1 hour.

    Available presets: most_actives, day_gainers, day_losers,
    undervalued_growth, growth_technology, aggressive_small_caps,
    small_cap_gainers, undervalued_large_caps
    """
    try:
        from yf_screener import run_preset_screen
        result = run_preset_screen(screen_name, limit=limit)
        return NaNSafeJSONResponse(content=result)
    except Exception as e:
        logger.error(f"Preset screen '{screen_name}' error: {e}")
        raise HTTPException(status_code=500, detail=f"Screen failed: {str(e)[:120]}")


@app.post("/screener/custom")
@limiter.limit("10/minute")
def screener_custom(
    request: Request,
    body: ScreenerFilterRequest,
    current_user: User = Depends(require_plan("pro")),
):
    """
    Custom NSE fundamental screener — Pro/Elite only.
    Filters NSE 500 pool by PE, ROE, D/E, market cap, dividend yield,
    growth, margin, sector, and more. Results cached 1 hour.

    All numeric filter fields are optional — only applied if provided.
    Returns matched stocks sorted by chosen metric with quality scores.
    """
    try:
        from yf_screener import run_custom_screen
        result = run_custom_screen(
            min_pe               = body.min_pe,
            max_pe               = body.max_pe,
            min_roe              = body.min_roe,
            max_de               = body.max_de,
            min_market_cap_cr    = body.min_market_cap_cr,
            max_market_cap_cr    = body.max_market_cap_cr,
            min_div_yield        = body.min_div_yield,
            min_revenue_growth   = body.min_revenue_growth,
            min_profit_margin    = body.min_profit_margin,
            max_pb               = body.max_pb,
            sectors              = body.sectors,
            sort_by              = body.sort_by,
            sort_desc            = body.sort_desc,
            limit                = min(body.limit, 50),
        )
        return NaNSafeJSONResponse(content=result)
    except Exception as e:
        logger.error(f"Custom screener error: {e}")
        raise HTTPException(status_code=500, detail=f"Custom screen failed: {str(e)[:120]}")


@app.get("/screener/quality")
@limiter.limit("10/minute")
def screener_quality(
    request: Request,
    limit: int = Query(default=20, le=50),
    current_user: User = Depends(require_plan("pro")),
):
    """
    KEPLER Quality Compounders screen — Pro/Elite only.
    ROE > 15%, D/E < 1.0, PE < 50, positive growth. Sorted by ROE.
    """
    try:
        from yf_screener import get_nse_quality_picks
        result = get_nse_quality_picks(limit=limit)
        return NaNSafeJSONResponse(content=result)
    except Exception as e:
        logger.error(f"Quality screen error: {e}")
        raise HTTPException(status_code=500, detail="Quality screen failed")


@app.get("/screener/value")
@limiter.limit("10/minute")
def screener_value(
    request: Request,
    limit: int = Query(default=20, le=50),
    current_user: User = Depends(require_plan("pro")),
):
    """
    Value picks screen — Pro/Elite only.
    PE < 20, PB < 3, ROE > 8%, D/E < 1.5. Sorted by PE ascending.
    """
    try:
        from yf_screener import get_nse_value_picks
        result = get_nse_value_picks(limit=limit)
        return NaNSafeJSONResponse(content=result)
    except Exception as e:
        logger.error(f"Value screen error: {e}")
        raise HTTPException(status_code=500, detail="Value screen failed")


@app.get("/screener/dividend")
@limiter.limit("10/minute")
def screener_dividend(
    request: Request,
    limit: int = Query(default=20, le=50),
    current_user: User = Depends(require_plan("pro")),
):
    """
    High dividend yield screen — Pro/Elite only.
    Dividend yield > 2%, PE < 30, profit margin > 5%.
    Sorted by dividend yield descending.
    """
    try:
        from yf_screener import get_nse_dividend_picks
        result = get_nse_dividend_picks(limit=limit)
        return NaNSafeJSONResponse(content=result)
    except Exception as e:
        logger.error(f"Dividend screen error: {e}")
        raise HTTPException(status_code=500, detail="Dividend screen failed")


# ── Swing Trading Screener Endpoints ──────────────────────────────────────────

@app.get("/screener/swing")
@limiter.limit("30/minute")
def swing_preset_list(
    request: Request,
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    List all available swing trading preset screens with metadata.
    Public endpoint — no auth required.
    """
    from swing_screener import get_swing_preset_list
    return {"presets": get_swing_preset_list()}


@app.get("/screener/swing/{preset_name}")
@limiter.limit("10/minute")
def swing_preset_run(
    request: Request,
    preset_name: str,
    limit: int = Query(default=30, le=60),
    current_user: User = Depends(require_plan("pro")),
):
    """
    Run a swing trading technical preset screen — Pro/Elite only.
    Uses 1-year OHLCV data to compute RSI, DMAs, volume ratio, 52W proximity.
    Results cached 30 minutes (fresher than fundamental screens).

    Available presets:
      near_52w_high, breakout_52w, volume_surge, momentum_leaders,
      rsi_oversold_bounce, rsi_momentum, near_support, golden_crossover,
      vcp_tight, high_rs
    """
    try:
        from swing_screener import run_swing_preset
        result = run_swing_preset(preset_name, limit=limit)
        if "error" in result and result.get("count", 0) == 0:
            raise HTTPException(status_code=404, detail=result["error"])
        return NaNSafeJSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Swing preset '{preset_name}' error: {e}")
        raise HTTPException(status_code=500, detail=f"Swing screen failed: {str(e)[:120]}")


@app.get("/screener/fundamentals/{symbol}")
@limiter.limit("20/minute")
def screener_fundamentals(
    request: Request,
    symbol: str,
    current_user: User = Depends(get_current_user),
):
    """
    Fetch enriched fundamental data for a single NSE stock via yfinance.
    Returns PE, PB, ROE, ROCE, D/E, margins, growth, shareholding, dividends.
    Requires login. Cached 24 hours per symbol.
    """
    symbol = symbol.upper().strip().replace(".NS", "")
    if len(symbol) > 20:
        raise HTTPException(status_code=400, detail="Invalid symbol")
    try:
        from fundamentals_fetcher import fetch_fundamentals, get_cache_stats
        data = fetch_fundamentals(symbol)
        return data
    except Exception as e:
        logger.error(f"Fundamentals fetch error for '{symbol}': {e}")
        raise HTTPException(status_code=500, detail=f"Could not fetch fundamentals for {symbol}")


@app.get("/screener/cache-stats")
def screener_cache_stats(current_user: User = Depends(require_plan("elite"))):
    """Cache stats for monitoring — Elite only."""
    from fundamentals_fetcher import get_cache_stats as fund_stats
    from yf_screener import _screen_cache
    return {
        "fundamentals_cache":  fund_stats(),
        "screener_cache_size": len(_screen_cache),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ADMIN ENDPOINTS (Elite only)
# ═══════════════════════════════════════════════════════════════════════════════

class DeepDiveCreateRequest(BaseModel):
    title: str
    summary: Optional[str] = None
    content: Optional[str] = None
    tier: str = "elite"
    symbol: Optional[str] = None
    sector: Optional[str] = None
    verdict: Optional[str] = None
    risk_rating: Optional[str] = None
    price_target_12m: Optional[float] = None
    tags: Optional[List[str]] = None


@app.post("/admin/deepdive")
def admin_create_deepdive(
    body: DeepDiveCreateRequest,
    current_user: User = Depends(require_plan("elite")),
    db: Session = Depends(get_db),
):
    """Publish a new Deep Dive report manually — Elite admin only."""
    dive = DeepDive(
        title=body.title,
        summary=body.summary,
        content=body.content,
        tier=body.tier,
        symbol=body.symbol.upper().strip() if body.symbol else None,
        sector=body.sector,
        verdict=body.verdict,
        risk_rating=body.risk_rating,
        price_target_12m=body.price_target_12m,
        tags=body.tags or [],
    )
    db.add(dive)
    db.commit()
    db.refresh(dive)
    logger.info(f"Deep dive published by {current_user.email}: {dive.title}")
    return {"id": dive.id, "title": dive.title, "symbol": dive.symbol,
            "verdict": dive.verdict, "tier": dive.tier, "created_at": str(dive.created_at)}


@app.post("/admin/trigger/news-pipeline")
def admin_trigger_news(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_plan("elite")),
    db: Session = Depends(get_db),
):
    """Manually trigger the news + AI pipeline — Elite only (admin use)."""
    def _run():
        from news_collector import collect_all_news
        from ai_processor import process_news
        articles = collect_all_news(settings.newsapi_key, settings.gnews_api_key)
        from database import SessionLocal
        _db = SessionLocal()
        try:
            process_news(articles, _db)
        finally:
            _db.close()

    background_tasks.add_task(_run)
    logger.info(f"News pipeline manually triggered by {current_user.email}")
    return {"message": "News + AI pipeline started in background"}


@app.post("/admin/trigger/breakout-scan")
def admin_trigger_breakout(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_plan("elite")),
):
    """Manually trigger the breakout scanner — Elite only (admin use)."""
    def _run():
        from breakout_scanner import scan_breakouts
        from database import SessionLocal
        _db = SessionLocal()
        try:
            results = scan_breakouts(_db)
            logger.info(f"Admin breakout scan complete: {len(results)} setups")
        finally:
            _db.close()

    background_tasks.add_task(_run)
    logger.info(f"Breakout scan manually triggered by {current_user.email}")
    return {"message": "Breakout scanner started in background"}




# ═══════════════════════════════════════════════════════════════════════════════
# SECTOR INTELLIGENCE HUB
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/sectors/live")
@limiter.limit("30/minute")
def sectors_live(request: Request, force_refresh: bool = Query(default=False)):
    """Live sector hub data — all 15 sectors, movers, news, macro signals. Public."""
    try:
        from sector_live import get_all_sectors_live
        result = get_all_sectors_live(force_refresh=force_refresh)
        return NaNSafeJSONResponse(content=result)
    except Exception as e:
        logger.error(f"Sector hub error: {e}")
        raise HTTPException(status_code=500, detail="Sector data fetch failed")


# ═══════════════════════════════════════════════════════════════════════════════
# STOCK SIGNALS  — Manual chart research uploads
# ═══════════════════════════════════════════════════════════════════════════════

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
MAX_IMAGE_BYTES = 15 * 1024 * 1024   # 15 MB
ADMIN_EMAIL     = "gagansolanki293@gmail.com"   # Only this account can manage signals


def _is_admin(user: User) -> bool:
    return user.email.lower() == ADMIN_EMAIL.lower()


def _signal_dict(s: StockSignal, base_url: str) -> dict:
    return {
        "id":           s.id,
        "symbol":       s.symbol,
        "title":        s.title,
        "description":  s.description,
        "timeframe":    s.timeframe,
        "signal_type":  s.signal_type,
        "support":      s.support,
        "resistance":   s.resistance,
        "target":       s.target,
        "stoploss":     s.stoploss,
        "image_url":    f"{base_url}/static/signals/{s.image_filename}",
        "plan_required":s.plan_required,
        "is_published": s.is_published,
        "created_at":   s.created_at.isoformat(),
    }


@app.post("/signals/upload")
async def upload_signal(
    request: Request,
    symbol:       str        = Form(...),
    title:        str        = Form(...),
    description:  str        = Form(default=""),
    timeframe:    str        = Form(default="Daily"),
    signal_type:  str        = Form(default="NEUTRAL"),
    support:      Optional[float] = Form(default=None),
    resistance:   Optional[float] = Form(default=None),
    target:       Optional[float] = Form(default=None),
    stoploss:     Optional[float] = Form(default=None),
    plan_required:str        = Form(default="pro"),
    image:        UploadFile = File(...),
    current_user: User       = Depends(get_current_user),
    db: Session              = Depends(get_db),
):
    """Upload a manual stock signal chart image — elite admin only."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Validate content type
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, WebP or GIF images are allowed")

    # Read and size-check
    data = await image.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="Image must be under 15 MB")

    # Build a unique filename: {timestamp}_{symbol}_{uuid}.ext
    ext = Path(image.filename or "img").suffix.lower() or ".jpg"
    filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{symbol.upper()}_{uuid.uuid4().hex[:8]}{ext}"
    dest = _SIGNALS_DIR / filename
    dest.write_bytes(data)

    # Persist record
    sig = StockSignal(
        symbol=symbol.upper().strip(),
        title=title.strip(),
        description=description.strip(),
        timeframe=timeframe,
        signal_type=signal_type.upper(),
        support=support,
        resistance=resistance,
        target=target,
        stoploss=stoploss,
        image_filename=filename,
        plan_required=plan_required,
        is_published=True,
    )
    db.add(sig)
    db.commit()
    db.refresh(sig)

    base = str(request.base_url).rstrip("/")
    logger.info(f"Signal uploaded: {sig.symbol} — {sig.title} by {current_user.email}")
    return {"ok": True, "signal": _signal_dict(sig, base)}


@app.get("/signals")
def list_signals(
    request:  Request,
    page:     int           = Query(default=1, ge=1),
    limit:    int           = Query(default=20, le=50),
    symbol:   Optional[str] = Query(default=None),
    current_user: User      = Depends(get_current_user),
    db: Session             = Depends(get_db),
):
    """List published signals — all auth users can see metadata; image visible by plan."""
    q = db.query(StockSignal).filter(StockSignal.is_published == True)
    if symbol:
        q = q.filter(StockSignal.symbol == symbol.upper())
    total = q.count()
    signals = q.order_by(StockSignal.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

    base = str(request.base_url).rstrip("/")
    user_plan = current_user.plan  # free / pro / elite
    plan_rank = {"free": 0, "pro": 1, "elite": 2}

    results = []
    for idx, s in enumerate(signals):
        d = _signal_dict(s, base)
        required_rank = plan_rank.get(s.plan_required, 1)
        user_rank     = plan_rank.get(user_plan, 0)
        # Free users: first 2 signals visible, rest have image_url nulled out
        if user_rank < required_rank and idx >= 2:
            d["image_url"]   = None
            d["description"] = None
            d["locked"]      = True
        else:
            d["locked"] = False
        results.append(d)

    return {"signals": results, "total": total, "page": page, "limit": limit}


@app.delete("/signals/{signal_id}")
def delete_signal(
    signal_id: str,
    current_user: User = Depends(get_current_user),
    db: Session        = Depends(get_db),
):
    """Delete a signal and its image — admin only."""
    if not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    sig = db.query(StockSignal).filter(StockSignal.id == signal_id).first()
    if not sig:
        raise HTTPException(status_code=404, detail="Signal not found")
    # Remove image file
    img_path = _SIGNALS_DIR / sig.image_filename
    if img_path.exists():
        img_path.unlink()
    db.delete(sig)
    db.commit()
    return {"ok": True, "deleted_id": signal_id}


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=not settings.is_production,
        workers=1 if not settings.is_production else 4,
    )
